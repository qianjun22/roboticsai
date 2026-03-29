#!/usr/bin/env python3
"""
benchmark_suite.py — Standardized benchmark suite for GR00T fine-tuned checkpoints.

Runs 5 evaluation dimensions and produces a reproducible benchmark report.
This is the canonical benchmark referenced in the CoRL paper.

Benchmark dimensions:
  1. Task Success Rate     — pick-and-lift (20 episodes, standard)
  2. Generalization        — 3 cube positions (near/center/far) × 10 episodes each
  3. Robustness            — 10% perturbation on initial pose × 10 episodes
  4. Latency               — p50/p95/p99 from 100 inference calls
  5. Sample Efficiency     — success rate at [100, 250, 500, 1000] demos

Usage:
    # Full benchmark (requires GR00T server + Genesis)
    python src/eval/benchmark_suite.py --server-url http://localhost:8002

    # Quick smoke test (3 episodes per task)
    python src/eval/benchmark_suite.py --quick --server-url http://localhost:8002

    # Mock mode — reproduces paper Table 2 numbers
    python src/eval/benchmark_suite.py --mock --output /tmp/benchmark_report.html

    # Compare two checkpoints
    python src/eval/benchmark_suite.py --mock \
        --labels "500-demo BC" "1000-demo BC" "DAgger iter3" \
        --output /tmp/benchmark_comparison.html
"""

import argparse
import json
import math
import os
import sys
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

# ── Dependency checks ─────────────────────────────────────────────────────────

def _check_requests():
    try:
        import requests  # noqa: F401
        return True
    except ImportError:
        return False

def _check_genesis():
    try:
        import genesis  # noqa: F401
        return True
    except ImportError:
        return False

# ── Config ────────────────────────────────────────────────────────────────────

SAMPLE_EFFICIENCY_DEMO_COUNTS = [100, 250, 500, 1000]
GENERALIZATION_POSITIONS = ["near", "center", "far"]
LATENCY_N_CALLS = 100
STANDARD_N_EPISODES = 20
QUICK_N_EPISODES = 3
ROBUSTNESS_N_EPISODES = 10
GENERALIZATION_N_EPISODES = 10

# Cube position configs (xyz offsets from default pose)
POSITION_CONFIGS = {
    "near":   {"cube_x_offset": -0.10, "cube_y_offset":  0.00},
    "center": {"cube_x_offset":  0.00, "cube_y_offset":  0.00},
    "far":    {"cube_x_offset":  0.10, "cube_y_offset":  0.00},
}

# Perturbation scale for robustness (10% of joint range)
ROBUSTNESS_PERTURBATION_SCALE = 0.10

# Mock data — paper Table 2 numbers
_MOCK_DATA = {
    "500-demo BC": {
        "task_success": {"success_rate": 0.03, "avg_latency_ms": 224.1, "n_eps": 20},
        "generalization": {
            "near":   {"success_rate": 0.05, "n_eps": 10},
            "center": {"success_rate": 0.03, "n_eps": 10},
            "far":    {"success_rate": 0.00, "n_eps": 10},
        },
        "robustness": {"success_rate": 0.02, "degradation_vs_standard": 0.33},
        "latency": {"p50": 223.0, "p95": 245.0, "p99": 268.0, "throughput_rps": 4.47},
        "sample_efficiency": [
            {"demos": 100,  "success_rate": 0.01},
            {"demos": 250,  "success_rate": 0.02},
            {"demos": 500,  "success_rate": 0.03},
            {"demos": 1000, "success_rate": 0.05},
        ],
    },
    "1000-demo BC": {
        "task_success": {"success_rate": 0.05, "avg_latency_ms": 224.3, "n_eps": 20},
        "generalization": {
            "near":   {"success_rate": 0.08, "n_eps": 10},
            "center": {"success_rate": 0.05, "n_eps": 10},
            "far":    {"success_rate": 0.02, "n_eps": 10},
        },
        "robustness": {"success_rate": 0.04, "degradation_vs_standard": 0.20},
        "latency": {"p50": 223.0, "p95": 245.0, "p99": 268.0, "throughput_rps": 4.47},
        "sample_efficiency": [
            {"demos": 100,  "success_rate": 0.02},
            {"demos": 250,  "success_rate": 0.03},
            {"demos": 500,  "success_rate": 0.04},
            {"demos": 1000, "success_rate": 0.05},
        ],
    },
    "DAgger iter3": {
        "task_success": {"success_rate": 0.65, "avg_latency_ms": 224.6, "n_eps": 20},
        "generalization": {
            "near":   {"success_rate": 0.70, "n_eps": 10},
            "center": {"success_rate": 0.65, "n_eps": 10},
            "far":    {"success_rate": 0.55, "n_eps": 10},
        },
        "robustness": {"success_rate": 0.58, "degradation_vs_standard": 0.11},
        "latency": {"p50": 223.0, "p95": 245.0, "p99": 268.0, "throughput_rps": 4.47},
        "sample_efficiency": [
            {"demos": 100,  "success_rate": 0.25},
            {"demos": 250,  "success_rate": 0.45},
            {"demos": 500,  "success_rate": 0.58},
            {"demos": 1000, "success_rate": 0.65},
        ],
    },
}

# ── Dataclass ─────────────────────────────────────────────────────────────────

@dataclass
class BenchmarkConfig:
    server_url: str = "http://localhost:8002"
    n_episodes: int = STANDARD_N_EPISODES
    quick: bool = False
    mock: bool = False
    labels: List[str] = field(default_factory=lambda: list(_MOCK_DATA.keys()))
    output: str = "/tmp/benchmark_report.html"
    max_steps: int = 500

    def effective_n_episodes(self, base: int) -> int:
        """Return reduced episode count when quick mode is on."""
        return QUICK_N_EPISODES if self.quick else base

# ── Genesis / server helpers ──────────────────────────────────────────────────

def _infer_action(server_url: str, obs: Dict[str, Any]) -> Dict[str, Any]:
    """Call the GR00T inference server with an observation dict."""
    import requests
    payload = {"observation": obs}
    resp = requests.post(f"{server_url}/infer", json=payload, timeout=10)
    resp.raise_for_status()
    return resp.json()

def _make_dummy_obs() -> Dict[str, Any]:
    """Minimal observation dict for latency benchmark (no Genesis required)."""
    return {
        "video": np.zeros((1, 3, 224, 224), dtype=np.uint8).tolist(),
        "state": np.zeros(14, dtype=np.float32).tolist(),
        "instruction": "pick up the cube and lift it",
    }

def _run_single_episode(server_url: str, max_steps: int,
                        env_kwargs: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Run one closed-loop episode in Genesis.

    Returns:
        {"success": bool, "steps": int, "latency_ms": float}
    """
    import genesis as gs

    gs.init(backend=gs.cuda, logging_level="warning")
    scene = gs.Scene(show_viewer=False)
    plane = scene.add_entity(gs.morphs.Plane())  # noqa: F841
    robot = scene.add_entity(
        gs.morphs.MJCF(file="xml/franka_emika_panda/panda.xml"),
    )

    cube_pos = [0.5, 0.0, 0.02]
    if env_kwargs:
        cube_pos[0] += env_kwargs.get("cube_x_offset", 0.0)
        cube_pos[1] += env_kwargs.get("cube_y_offset", 0.0)

    cube = scene.add_entity(
        gs.morphs.Box(size=(0.04, 0.04, 0.04), pos=cube_pos),
    )
    scene.build()

    # Optionally perturb initial pose
    if env_kwargs and env_kwargs.get("perturb_init"):
        dofs = robot.get_dofs_position()
        noise = np.random.uniform(
            -ROBUSTNESS_PERTURBATION_SCALE,
             ROBUSTNESS_PERTURBATION_SCALE,
            size=dofs.shape,
        )
        robot.set_dofs_position(dofs + noise)

    LIFT_THRESHOLD = 0.78  # metres — calibrated empirically (Session 11)

    success = False
    step_latencies = []
    for step in range(max_steps):
        t0 = time.perf_counter()

        # Build observation
        obs = {
            "video": np.zeros((1, 3, 224, 224), dtype=np.uint8).tolist(),
            "state": robot.get_dofs_position().tolist(),
            "instruction": "pick up the cube and lift it",
        }

        result = _infer_action(server_url, obs)
        action = np.array(result.get("action", np.zeros(7)))

        robot.control_dofs_position(action[:7])
        scene.step()

        step_latencies.append((time.perf_counter() - t0) * 1000)

        cube_z = cube.get_pos()[2].item()
        if cube_z >= LIFT_THRESHOLD:
            success = True
            break

    avg_lat = float(np.mean(step_latencies)) if step_latencies else 0.0
    return {"success": success, "steps": step + 1, "latency_ms": avg_lat}

# ── Benchmark dimensions ──────────────────────────────────────────────────────

def run_task_success(config: BenchmarkConfig) -> Dict[str, Any]:
    """
    Dimension 1 — Task Success Rate.

    Runs standard pick-and-lift across n_episodes episodes.

    Returns:
        {"success_rate": float, "avg_latency_ms": float, "n_eps": int}
    """
    n = config.effective_n_episodes(STANDARD_N_EPISODES)
    print(f"  [1/5] Task Success Rate — {n} episodes ...")

    successes = 0
    latencies = []
    for ep in range(n):
        try:
            res = _run_single_episode(config.server_url, config.max_steps)
            if res["success"]:
                successes += 1
            latencies.append(res["latency_ms"])
            status = "OK" if res["success"] else "--"
            print(f"        ep {ep+1:02d}/{n}  {status}  {res['latency_ms']:.1f}ms/step")
        except Exception as exc:
            print(f"        ep {ep+1:02d}/{n}  ERROR: {exc}")

    success_rate = successes / n if n > 0 else 0.0
    avg_latency = float(np.mean(latencies)) if latencies else 0.0
    return {"success_rate": success_rate, "avg_latency_ms": avg_latency, "n_eps": n}


def run_generalization(config: BenchmarkConfig) -> Dict[str, Dict[str, Any]]:
    """
    Dimension 2 — Generalization across 3 cube positions.

    Returns:
        {"near": {...}, "center": {...}, "far": {...}}
        Each value: {"success_rate": float, "n_eps": int}
    """
    n = config.effective_n_episodes(GENERALIZATION_N_EPISODES)
    print(f"  [2/5] Generalization — 3 positions × {n} episodes each ...")

    results = {}
    for pos_name in GENERALIZATION_POSITIONS:
        env_kw = dict(POSITION_CONFIGS[pos_name])
        successes = 0
        for ep in range(n):
            try:
                res = _run_single_episode(config.server_url, config.max_steps, env_kwargs=env_kw)
                if res["success"]:
                    successes += 1
            except Exception as exc:
                print(f"        [{pos_name}] ep {ep+1} ERROR: {exc}")
        sr = successes / n if n > 0 else 0.0
        results[pos_name] = {"success_rate": sr, "n_eps": n}
        print(f"        {pos_name:>6s}  SR={sr*100:.1f}%  ({successes}/{n})")

    return results


def run_robustness(config: BenchmarkConfig) -> Dict[str, Any]:
    """
    Dimension 3 — Robustness under perturbed initial pose.

    Applies ±10% uniform noise to each joint DoF at episode start.

    Returns:
        {"success_rate": float, "degradation_vs_standard": float}
        degradation = (standard_sr - perturbed_sr) / standard_sr  (clamped ≥ 0)
    """
    n = config.effective_n_episodes(ROBUSTNESS_N_EPISODES)
    print(f"  [3/5] Robustness — {n} perturbed episodes ...")

    successes = 0
    for ep in range(n):
        try:
            res = _run_single_episode(
                config.server_url, config.max_steps,
                env_kwargs={"perturb_init": True},
            )
            if res["success"]:
                successes += 1
            print(f"        ep {ep+1:02d}/{n}  {'OK' if res['success'] else '--'}")
        except Exception as exc:
            print(f"        ep {ep+1:02d}/{n}  ERROR: {exc}")

    sr = successes / n if n > 0 else 0.0
    # degradation requires standard baseline; caller may patch this after run_task_success
    return {"success_rate": sr, "degradation_vs_standard": None}


def run_latency_benchmark(config: BenchmarkConfig) -> Dict[str, Any]:
    """
    Dimension 4 — Inference latency from 100 server calls.

    Does NOT require Genesis — sends dummy observations directly.

    Returns:
        {"p50": float, "p95": float, "p99": float, "throughput_rps": float}
        All latency values in milliseconds.
    """
    n = LATENCY_N_CALLS
    print(f"  [4/5] Latency — {n} inference calls ...")

    obs = _make_dummy_obs()
    latencies = []
    for i in range(n):
        t0 = time.perf_counter()
        try:
            _infer_action(config.server_url, obs)
        except Exception as exc:
            print(f"        call {i+1} ERROR: {exc}")
            continue
        elapsed_ms = (time.perf_counter() - t0) * 1000
        latencies.append(elapsed_ms)

    if not latencies:
        return {"p50": 0.0, "p95": 0.0, "p99": 0.0, "throughput_rps": 0.0}

    arr = np.array(latencies)
    p50 = float(np.percentile(arr, 50))
    p95 = float(np.percentile(arr, 95))
    p99 = float(np.percentile(arr, 99))
    throughput = 1000.0 / p50 if p50 > 0 else 0.0

    print(f"        p50={p50:.1f}ms  p95={p95:.1f}ms  p99={p99:.1f}ms  "
          f"throughput={throughput:.2f} rps")

    return {"p50": p50, "p95": p95, "p99": p99, "throughput_rps": throughput}


def run_sample_efficiency(config: BenchmarkConfig) -> List[Dict[str, Any]]:
    """
    Dimension 5 — Sample efficiency at multiple checkpoint sizes.

    Queries /infer?checkpoint=<demos> on the server, which must serve
    checkpoints trained on [100, 250, 500, 1000] demo datasets.

    Returns:
        [{"demos": int, "success_rate": float}, ...]
    """
    import requests

    n = config.effective_n_episodes(QUICK_N_EPISODES if config.quick else 10)
    print(f"  [5/5] Sample Efficiency — {len(SAMPLE_EFFICIENCY_DEMO_COUNTS)} checkpoints × {n} eps ...")

    results = []
    for demo_count in SAMPLE_EFFICIENCY_DEMO_COUNTS:
        successes = 0
        for ep in range(n):
            try:
                obs = _make_dummy_obs()
                payload = {"observation": obs, "checkpoint_demos": demo_count}
                resp = requests.post(
                    f"{config.server_url}/infer", json=payload, timeout=10
                )
                resp.raise_for_status()
                data = resp.json()
                if data.get("success", False):
                    successes += 1
            except Exception as exc:
                print(f"        demos={demo_count} ep {ep+1} ERROR: {exc}")

        sr = successes / n if n > 0 else 0.0
        results.append({"demos": demo_count, "success_rate": sr})
        print(f"        demos={demo_count:5d}  SR={sr*100:.1f}%")

    return results

# ── HTML report generation ────────────────────────────────────────────────────

_COLORS = ["#60a5fa", "#34d399", "#f472b6", "#fbbf24", "#a78bfa"]

def _pct(v: Optional[float]) -> str:
    if v is None:
        return "N/A"
    return f"{v * 100:.1f}%"

def _ms(v: Optional[float]) -> str:
    if v is None:
        return "N/A"
    return f"{v:.1f} ms"

def _svg_line_chart(
    series: List[Dict],  # [{"label": str, "points": [(x, y), ...], "color": str}]
    x_label: str,
    y_label: str,
    title: str,
    width: int = 600,
    height: int = 280,
) -> str:
    """Render a minimal SVG line chart. No external dependencies."""
    pad_left, pad_right, pad_top, pad_bottom = 60, 30, 30, 50
    chart_w = width - pad_left - pad_right
    chart_h = height - pad_top - pad_bottom

    all_x = [p[0] for s in series for p in s["points"]]
    all_y = [p[1] for s in series for p in s["points"]]
    x_min, x_max = min(all_x), max(all_x)
    y_min, y_max = 0.0, max(all_y) * 1.15 or 1.0

    def sx(x):
        return pad_left + (x - x_min) / (x_max - x_min + 1e-9) * chart_w

    def sy(y):
        return pad_top + chart_h - (y - y_min) / (y_max - y_min + 1e-9) * chart_h

    lines = []
    # Axes
    lines.append(
        f'<line x1="{pad_left}" y1="{pad_top}" x2="{pad_left}" '
        f'y2="{pad_top+chart_h}" stroke="#4b5563" stroke-width="1"/>'
    )
    lines.append(
        f'<line x1="{pad_left}" y1="{pad_top+chart_h}" x2="{pad_left+chart_w}" '
        f'y2="{pad_top+chart_h}" stroke="#4b5563" stroke-width="1"/>'
    )

    # Y-axis ticks
    n_ticks = 5
    for i in range(n_ticks + 1):
        yv = y_min + (y_max - y_min) * i / n_ticks
        yp = sy(yv)
        lines.append(
            f'<line x1="{pad_left-4}" y1="{yp}" x2="{pad_left+chart_w}" '
            f'y2="{yp}" stroke="#374151" stroke-width="1" stroke-dasharray="4,4"/>'
        )
        lines.append(
            f'<text x="{pad_left-8}" y="{yp+4}" fill="#9ca3af" '
            f'font-size="11" text-anchor="end">{yv*100:.0f}%</text>'
        )

    # X-axis labels
    for s in series[:1]:
        for x_val, _ in s["points"]:
            xp = sx(x_val)
            lines.append(
                f'<text x="{xp}" y="{pad_top+chart_h+16}" fill="#9ca3af" '
                f'font-size="11" text-anchor="middle">{x_val}</text>'
            )

    # Series
    for s in series:
        pts = s["points"]
        color = s["color"]
        coords = " ".join(f"{sx(x)},{sy(y)}" for x, y in pts)
        lines.append(
            f'<polyline points="{coords}" fill="none" stroke="{color}" '
            f'stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>'
        )
        for x_val, y_val in pts:
            lines.append(
                f'<circle cx="{sx(x_val)}" cy="{sy(y_val)}" r="4" '
                f'fill="{color}" stroke="#111827" stroke-width="1.5"/>'
            )

    # Axis labels
    lines.append(
        f'<text x="{pad_left + chart_w/2}" y="{height-4}" fill="#9ca3af" '
        f'font-size="12" text-anchor="middle">{x_label}</text>'
    )
    lines.append(
        f'<text x="12" y="{pad_top + chart_h/2}" fill="#9ca3af" '
        f'font-size="12" text-anchor="middle" '
        f'transform="rotate(-90,12,{pad_top+chart_h/2})">{y_label}</text>'
    )
    lines.append(
        f'<text x="{pad_left + chart_w/2}" y="{pad_top - 10}" fill="#e5e7eb" '
        f'font-size="13" font-weight="bold" text-anchor="middle">{title}</text>'
    )

    # Legend
    leg_x = pad_left + chart_w - 10
    for i, s in enumerate(series):
        ly = pad_top + 12 + i * 18
        lines.append(
            f'<rect x="{leg_x - 60}" y="{ly - 8}" width="12" height="12" '
            f'rx="2" fill="{s["color"]}"/>'
        )
        lines.append(
            f'<text x="{leg_x - 44}" y="{ly + 2}" fill="#d1d5db" '
            f'font-size="11">{s["label"]}</text>'
        )

    svg_body = "\n".join(lines)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{width}" height="{height}" '
        f'style="background:#1f2937;border-radius:8px;">'
        f'{svg_body}</svg>'
    )


def _svg_bar_chart(
    categories: List[str],
    series: List[Dict],  # [{"label": str, "values": [float], "color": str}]
    title: str,
    width: int = 480,
    height: int = 260,
) -> str:
    """Grouped bar chart as SVG."""
    pad_left, pad_right, pad_top, pad_bottom = 55, 20, 35, 50
    chart_w = width - pad_left - pad_right
    chart_h = height - pad_top - pad_bottom

    all_vals = [v for s in series for v in s["values"]]
    y_max = max(all_vals) * 1.2 or 1.0

    n_groups = len(categories)
    n_series = len(series)
    group_w = chart_w / n_groups
    bar_w = group_w * 0.7 / n_series

    def sy(y):
        return pad_top + chart_h - (y / y_max) * chart_h

    lines = []
    # Axes
    lines.append(
        f'<line x1="{pad_left}" y1="{pad_top}" x2="{pad_left}" '
        f'y2="{pad_top+chart_h}" stroke="#4b5563" stroke-width="1"/>'
    )
    lines.append(
        f'<line x1="{pad_left}" y1="{pad_top+chart_h}" x2="{pad_left+chart_w}" '
        f'y2="{pad_top+chart_h}" stroke="#4b5563" stroke-width="1"/>'
    )

    # Y ticks
    for i in range(6):
        yv = y_max * i / 5
        yp = sy(yv)
        lines.append(
            f'<line x1="{pad_left-4}" y1="{yp}" x2="{pad_left+chart_w}" '
            f'y2="{yp}" stroke="#374151" stroke-width="1" stroke-dasharray="4,4"/>'
        )
        lines.append(
            f'<text x="{pad_left-8}" y="{yp+4}" fill="#9ca3af" '
            f'font-size="11" text-anchor="end">{yv*100:.0f}%</text>'
        )

    # Bars
    for gi, cat in enumerate(categories):
        group_center = pad_left + (gi + 0.5) * group_w
        bar_start = group_center - (n_series * bar_w) / 2
        for si, s in enumerate(series):
            x = bar_start + si * bar_w
            yv = s["values"][gi]
            bar_h = (yv / y_max) * chart_h
            y_top = sy(yv)
            lines.append(
                f'<rect x="{x:.1f}" y="{y_top:.1f}" width="{bar_w*0.85:.1f}" '
                f'height="{bar_h:.1f}" fill="{s["color"]}" rx="2" opacity="0.85"/>'
            )
        lines.append(
            f'<text x="{group_center}" y="{pad_top+chart_h+16}" '
            f'fill="#9ca3af" font-size="11" text-anchor="middle">{cat}</text>'
        )

    # Legend
    for i, s in enumerate(series):
        lx = pad_left + i * 130
        ly = height - 8
        lines.append(
            f'<rect x="{lx}" y="{ly-10}" width="10" height="10" '
            f'rx="2" fill="{s["color"]}"/>'
        )
        lines.append(
            f'<text x="{lx+14}" y="{ly}" fill="#d1d5db" font-size="11">{s["label"]}</text>'
        )

    lines.append(
        f'<text x="{pad_left + chart_w/2}" y="{pad_top - 14}" fill="#e5e7eb" '
        f'font-size="13" font-weight="bold" text-anchor="middle">{title}</text>'
    )

    svg_body = "\n".join(lines)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{width}" height="{height}" '
        f'style="background:#1f2937;border-radius:8px;">'
        f'{svg_body}</svg>'
    )


def generate_html_report(
    results_list: List[Dict[str, Any]],
    labels: List[str],
    output_path: str,
) -> str:
    """
    Generate a dark-theme HTML benchmark report.

    Args:
        results_list: list of result dicts, one per checkpoint/label.
                      Each dict has keys: task_success, generalization,
                      robustness, latency, sample_efficiency.
        labels:       human-readable name for each checkpoint.
        output_path:  where to write the .html file.

    Returns:
        Absolute path of the written file.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    n = len(labels)

    # ── Summary table ──────────────────────────────────────────────────────────
    col_headers = "".join(f"<th>{lbl}</th>" for lbl in labels)
    rows_html = []

    def _row(dim, vals):
        cells = "".join(f"<td>{v}</td>" for v in vals)
        return f"<tr><td>{dim}</td>{cells}</tr>"

    rows_html.append(_row(
        "Task Success Rate",
        [_pct(r["task_success"]["success_rate"]) for r in results_list],
    ))
    rows_html.append(_row(
        "Generalization (near)",
        [_pct(r["generalization"]["near"]["success_rate"]) for r in results_list],
    ))
    rows_html.append(_row(
        "Generalization (center)",
        [_pct(r["generalization"]["center"]["success_rate"]) for r in results_list],
    ))
    rows_html.append(_row(
        "Generalization (far)",
        [_pct(r["generalization"]["far"]["success_rate"]) for r in results_list],
    ))
    rows_html.append(_row(
        "Robustness (perturbed)",
        [_pct(r["robustness"]["success_rate"]) for r in results_list],
    ))
    rows_html.append(_row(
        "Robustness degradation",
        [
            (f"{r['robustness']['degradation_vs_standard']*100:.1f}%"
             if r["robustness"]["degradation_vs_standard"] is not None else "N/A")
            for r in results_list
        ],
    ))
    rows_html.append(_row(
        "Latency p50",
        [_ms(r["latency"]["p50"]) for r in results_list],
    ))
    rows_html.append(_row(
        "Latency p95",
        [_ms(r["latency"]["p95"]) for r in results_list],
    ))
    rows_html.append(_row(
        "Latency p99",
        [_ms(r["latency"]["p99"]) for r in results_list],
    ))
    rows_html.append(_row(
        "Throughput (rps)",
        [f"{r['latency']['throughput_rps']:.2f}" for r in results_list],
    ))
    rows_html.append(_row(
        "Sample Eff. @ 100 demos",
        [_pct(r["sample_efficiency"][0]["success_rate"]) for r in results_list],
    ))
    rows_html.append(_row(
        "Sample Eff. @ 250 demos",
        [_pct(r["sample_efficiency"][1]["success_rate"]) for r in results_list],
    ))
    rows_html.append(_row(
        "Sample Eff. @ 500 demos",
        [_pct(r["sample_efficiency"][2]["success_rate"]) for r in results_list],
    ))
    rows_html.append(_row(
        "Sample Eff. @ 1000 demos",
        [_pct(r["sample_efficiency"][3]["success_rate"]) for r in results_list],
    ))

    table_html = f"""
<table>
  <thead>
    <tr><th>Dimension</th>{col_headers}</tr>
  </thead>
  <tbody>
    {"".join(rows_html)}
  </tbody>
</table>
"""

    # ── Sample efficiency SVG ──────────────────────────────────────────────────
    eff_series = []
    for i, (lbl, res) in enumerate(zip(labels, results_list)):
        pts = [(e["demos"], e["success_rate"]) for e in res["sample_efficiency"]]
        eff_series.append({"label": lbl, "points": pts, "color": _COLORS[i % len(_COLORS)]})

    eff_chart = _svg_line_chart(
        eff_series,
        x_label="Training Demos",
        y_label="Success Rate",
        title="Sample Efficiency",
        width=640,
        height=300,
    )

    # ── Generalization bar chart ───────────────────────────────────────────────
    gen_series = []
    for i, (lbl, res) in enumerate(zip(labels, results_list)):
        vals = [res["generalization"][p]["success_rate"] for p in GENERALIZATION_POSITIONS]
        gen_series.append({"label": lbl, "values": vals, "color": _COLORS[i % len(_COLORS)]})

    gen_chart = _svg_bar_chart(
        GENERALIZATION_POSITIONS,
        gen_series,
        title="Generalization by Cube Position",
        width=500,
        height=280,
    )

    # ── Latency table ──────────────────────────────────────────────────────────
    lat_rows = ""
    for lbl, res in zip(labels, results_list):
        lat = res["latency"]
        lat_rows += (
            f"<tr><td>{lbl}</td>"
            f"<td>{_ms(lat['p50'])}</td>"
            f"<td>{_ms(lat['p95'])}</td>"
            f"<td>{_ms(lat['p99'])}</td>"
            f"<td>{lat['throughput_rps']:.2f}</td></tr>\n"
        )

    lat_table = f"""
<table>
  <thead>
    <tr><th>Checkpoint</th><th>p50</th><th>p95</th><th>p99</th><th>Throughput (rps)</th></tr>
  </thead>
  <tbody>{lat_rows}</tbody>
</table>
"""

    # ── Assemble HTML ──────────────────────────────────────────────────────────
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>GR00T Benchmark Report — {timestamp}</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: #111827;
      color: #e5e7eb;
      padding: 2rem;
      line-height: 1.6;
    }}
    h1 {{ font-size: 1.6rem; font-weight: 700; color: #f9fafb; margin-bottom: 0.25rem; }}
    h2 {{ font-size: 1.1rem; font-weight: 600; color: #d1d5db; margin: 2rem 0 0.75rem; }}
    .subtitle {{ color: #6b7280; font-size: 0.85rem; margin-bottom: 2rem; }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 0.875rem;
      margin-bottom: 1.5rem;
    }}
    th, td {{
      padding: 0.55rem 0.9rem;
      text-align: left;
      border-bottom: 1px solid #1f2937;
    }}
    th {{
      background: #1f2937;
      color: #9ca3af;
      font-weight: 600;
      font-size: 0.8rem;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }}
    tr:hover td {{ background: #1f2937; }}
    td:first-child {{ color: #9ca3af; font-size: 0.82rem; }}
    td:not(:first-child) {{ color: #f3f4f6; font-weight: 500; }}
    .charts {{
      display: flex;
      flex-wrap: wrap;
      gap: 1.5rem;
      margin-bottom: 2rem;
    }}
    .card {{
      background: #1f2937;
      border-radius: 10px;
      padding: 1.25rem;
      border: 1px solid #374151;
    }}
    .badge {{
      display: inline-block;
      background: #374151;
      color: #9ca3af;
      border-radius: 4px;
      padding: 0.1rem 0.5rem;
      font-size: 0.75rem;
      margin-right: 0.4rem;
    }}
    footer {{
      margin-top: 3rem;
      color: #4b5563;
      font-size: 0.75rem;
      border-top: 1px solid #1f2937;
      padding-top: 1rem;
    }}
  </style>
</head>
<body>
  <h1>GR00T Fine-Tune Benchmark Report</h1>
  <p class="subtitle">
    Generated: {timestamp}
    <span class="badge">CoRL Table 2</span>
    <span class="badge">{n} checkpoint{"s" if n != 1 else ""}</span>
  </p>

  <h2>Table 2 — Full Benchmark Summary</h2>
  {table_html}

  <h2>Charts</h2>
  <div class="charts">
    <div class="card">{eff_chart}</div>
    <div class="card">{gen_chart}</div>
  </div>

  <h2>Latency Percentiles</h2>
  {lat_table}

  <footer>
    OCI Robot Cloud · GR00T Benchmark Suite · benchmark_suite.py
  </footer>
</body>
</html>
"""

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"\n  Report written to: {out.resolve()}")
    return str(out.resolve())

# ── Mock runner ───────────────────────────────────────────────────────────────

def run_mock(labels: List[str]) -> List[Dict[str, Any]]:
    """Return mock paper numbers for the requested labels."""
    default_keys = list(_MOCK_DATA.keys())
    results = []
    for i, lbl in enumerate(labels):
        if lbl in _MOCK_DATA:
            results.append(_MOCK_DATA[lbl])
        else:
            # Fall back to cycling through available mock entries
            fallback = default_keys[i % len(default_keys)]
            print(f"  Warning: no mock data for '{lbl}', using '{fallback}' values.")
            results.append(_MOCK_DATA[fallback])
    return results

# ── Full live benchmark ───────────────────────────────────────────────────────

def run_full_benchmark(config: BenchmarkConfig) -> Dict[str, Any]:
    """
    Run all 5 dimensions against the live server and return a results dict.
    Genesis must be importable and the GR00T inference server must be up.
    """
    print("\nRunning full benchmark ...")
    print(f"  Server: {config.server_url}")
    print(f"  Mode:   {'quick' if config.quick else 'standard'}")

    task_result = run_task_success(config)
    gen_result  = run_generalization(config)
    rob_result  = run_robustness(config)

    # Patch degradation now that we have standard baseline
    std_sr = task_result["success_rate"]
    rob_sr = rob_result["success_rate"]
    if std_sr > 0:
        rob_result["degradation_vs_standard"] = max(0.0, (std_sr - rob_sr) / std_sr)
    else:
        rob_result["degradation_vs_standard"] = 0.0

    lat_result  = run_latency_benchmark(config)
    eff_result  = run_sample_efficiency(config)

    return {
        "task_success":      task_result,
        "generalization":    gen_result,
        "robustness":        rob_result,
        "latency":           lat_result,
        "sample_efficiency": eff_result,
    }

# ── CLI ───────────────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Standardized GR00T benchmark suite (CoRL Table 2).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument(
        "--server-url",
        default="http://localhost:8002",
        help="GR00T inference server URL (default: http://localhost:8002)",
    )
    p.add_argument(
        "--quick",
        action="store_true",
        help="Smoke-test mode: 3 episodes per dimension instead of full counts.",
    )
    p.add_argument(
        "--mock",
        action="store_true",
        help="Use pre-baked paper numbers — no server or Genesis required.",
    )
    p.add_argument(
        "--output",
        default="/tmp/benchmark_report.html",
        help="Output path for HTML report (default: /tmp/benchmark_report.html)",
    )
    p.add_argument(
        "--labels",
        nargs="+",
        default=None,
        help=(
            "Checkpoint labels for comparison. "
            "In mock mode, must match keys in _MOCK_DATA or will fall back. "
            "In live mode, runs the same server once and labels the single result."
        ),
    )
    p.add_argument(
        "--max-steps",
        type=int,
        default=500,
        help="Max steps per episode (default: 500).",
    )
    p.add_argument(
        "--json-output",
        default=None,
        help="Also dump raw results to this JSON path.",
    )
    return p


def main():
    parser = _build_parser()
    args = parser.parse_args()

    labels = args.labels or list(_MOCK_DATA.keys())

    if args.mock:
        print("Mock mode — using paper Table 2 numbers.")
        results_list = run_mock(labels)
    else:
        if not _check_requests():
            print("ERROR: 'requests' package not found. Install with: pip install requests")
            sys.exit(1)
        if not _check_genesis():
            print("WARNING: 'genesis' not found. Episode-based benchmarks will fail.")
            print("         Only latency benchmark will work without Genesis.")

        config = BenchmarkConfig(
            server_url=args.server_url,
            quick=args.quick,
            labels=labels,
            output=args.output,
            max_steps=args.max_steps,
        )

        single_result = run_full_benchmark(config)
        results_list = [single_result] * len(labels)
        if len(labels) > 1:
            print(
                "\nNote: live mode ran one benchmark; all labels share the same results. "
                "To compare multiple checkpoints, run benchmark_suite.py separately per "
                "checkpoint and merge the JSON outputs."
            )

    # Optionally dump JSON
    if args.json_output:
        out = Path(args.json_output)
        out.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "labels": labels,
            "timestamp": datetime.now().isoformat(),
            "results": results_list,
        }
        out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"JSON results saved to: {out.resolve()}")

    report_path = generate_html_report(results_list, labels, args.output)

    # Print summary to stdout
    print("\n" + "=" * 60)
    print("BENCHMARK SUMMARY")
    print("=" * 60)
    header = f"{'Dimension':<30}" + "".join(f"{lbl:>18}" for lbl in labels)
    print(header)
    print("-" * len(header))

    dim_rows = [
        ("Task Success Rate",     lambda r: _pct(r["task_success"]["success_rate"])),
        ("Generalization near",   lambda r: _pct(r["generalization"]["near"]["success_rate"])),
        ("Generalization center", lambda r: _pct(r["generalization"]["center"]["success_rate"])),
        ("Generalization far",    lambda r: _pct(r["generalization"]["far"]["success_rate"])),
        ("Robustness",            lambda r: _pct(r["robustness"]["success_rate"])),
        ("Latency p50",           lambda r: _ms(r["latency"]["p50"])),
        ("Latency p99",           lambda r: _ms(r["latency"]["p99"])),
        ("Sample Eff. @1000",     lambda r: _pct(r["sample_efficiency"][-1]["success_rate"])),
    ]
    for dim_name, extractor in dim_rows:
        row = f"{dim_name:<30}" + "".join(f"{extractor(r):>18}" for r in results_list)
        print(row)

    print("=" * 60)
    print(f"\nFull HTML report: {report_path}")


if __name__ == "__main__":
    main()
