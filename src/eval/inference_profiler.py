#!/usr/bin/env python3
"""
inference_profiler.py — GR00T N1.6-3B inference latency profiler.

Breaks down end-to-end latency into 9 components across preprocessing,
vision encoder, transformer, action head, and postprocessing stages.
Generates an HTML report with SVG charts for cross-platform comparison.

Usage:
    # Mock mode (no server needed)
    python src/eval/inference_profiler.py --mock

    # Specific GPU profile
    python src/eval/inference_profiler.py --mock --gpu A10 --output /tmp/inference_profiler.html

    # Custom seed
    python src/eval/inference_profiler.py --mock --seed 123 --output /tmp/profiler.html
"""

import argparse
import json
import random
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class ProfileComponent:
    name: str
    category: str                     # preprocessing/encoder/transformer/action_head/postprocessing
    latency_ms_mean: float
    latency_ms_std: float
    latency_ms_p95: float
    memory_mb: float
    flops_billion: Optional[float]    # nullable
    optimizable: bool
    optimization_hint: str


# ── Simulation ────────────────────────────────────────────────────────────────

# Base latency profiles (ms) per GPU for each component
_GPU_PROFILES = {
    "A100-80G": {
        "image_resize":           (2.5,  0.3),
        "image_normalize":        (5.5,  0.6),
        "vision_encoder":         (35.0, 3.0),
        "language_tokenize":      (1.2,  0.2),
        "transformer_12layers":   (140.0, 8.0),
        "action_head_decoder":    (20.0, 2.0),
        "action_denormalize":     (0.8,  0.1),
        "action_chunk_sample":    (1.0,  0.1),
    },
    "A10": {
        "image_resize":           (3.5,  0.5),
        "image_normalize":        (7.5,  0.8),
        "vision_encoder":         (55.0, 5.0),
        "language_tokenize":      (1.8,  0.3),
        "transformer_12layers":   (280.0, 15.0),
        "action_head_decoder":    (35.0, 3.5),
        "action_denormalize":     (1.2,  0.2),
        "action_chunk_sample":    (1.5,  0.2),
    },
    "Jetson-AGX": {
        "image_resize":           (8.0,  2.0),
        "image_normalize":        (18.0, 3.0),
        "vision_encoder":         (120.0, 20.0),
        "language_tokenize":      (4.5,  1.0),
        "transformer_12layers":   (450.0, 40.0),
        "action_head_decoder":    (75.0, 10.0),
        "action_denormalize":     (2.5,  0.5),
        "action_chunk_sample":    (3.0,  0.5),
    },
}

# Memory footprint per component (MB) — GPU-independent model weights
_COMPONENT_MEMORY = {
    "image_resize":         12.0,
    "image_normalize":      24.0,
    "vision_encoder":       1300.0,
    "language_tokenize":    8.0,
    "transformer_12layers": 6200.0,
    "action_head_decoder":  480.0,
    "action_denormalize":   4.0,
    "action_chunk_sample":  6.0,
    "total_pipeline":       8034.0,
}

_COMPONENT_FLOPS = {
    "image_resize":         0.02,
    "image_normalize":      0.05,
    "vision_encoder":       18.4,
    "language_tokenize":    None,
    "transformer_12layers": 142.8,
    "action_head_decoder":  9.6,
    "action_denormalize":   None,
    "action_chunk_sample":  None,
    "total_pipeline":       170.9,
}

_COMPONENT_CATEGORIES = {
    "image_resize":         "preprocessing",
    "image_normalize":      "preprocessing",
    "vision_encoder":       "encoder",
    "language_tokenize":    "preprocessing",
    "transformer_12layers": "transformer",
    "action_head_decoder":  "action_head",
    "action_denormalize":   "postprocessing",
    "action_chunk_sample":  "postprocessing",
    "total_pipeline":       "postprocessing",
}

_OPTIMIZATION_HINTS = {
    "image_resize":         "CUDA kernel batching → -30%",
    "image_normalize":      "Fuse with resize into single CUDA kernel → -40%",
    "vision_encoder":       "TensorRT FP8 → -45%; reduce resolution 256→128 → -50%",
    "language_tokenize":    "Pre-tokenize static prompts → -80% on repeated tasks",
    "transformer_12layers": "TensorRT-LLM FP8 quantization → -38%; H100 SXM5 → -42%",
    "action_head_decoder":  "Reduce chunk size 16→8 → -45%; distilled 1B head → -60%",
    "action_denormalize":   "Already fast; no significant optimization needed",
    "action_chunk_sample":  "Already fast; no significant optimization needed",
    "total_pipeline":       "Combined TensorRT + FP8 + fused kernels → projected -40%",
}

_OPTIMIZABLE = {
    "image_resize":         True,
    "image_normalize":      True,
    "vision_encoder":       True,
    "language_tokenize":    True,
    "transformer_12layers": True,
    "action_head_decoder":  True,
    "action_denormalize":   False,
    "action_chunk_sample":  False,
    "total_pipeline":       True,
}


def _normal_positive(rng_state: random.Random, mean: float, std: float) -> float:
    """Sample from normal, clamped to positive."""
    val = rng_state.gauss(mean, std)
    return max(val, mean * 0.3)


def simulate_profile(
    gpu_type: str = "A100-80G",
    batch_size: int = 1,
    seed: int = 42,
    n_samples: int = 200,
) -> Dict[str, ProfileComponent]:
    """
    Simulate realistic inference latency profiles for the given GPU and batch size.

    Returns a dict mapping component name → ProfileComponent.
    Transformer latency scales sub-linearly with batch size (memory bandwidth bound).
    """
    if gpu_type not in _GPU_PROFILES:
        raise ValueError(f"Unknown GPU type '{gpu_type}'. Choose from: {list(_GPU_PROFILES)}")

    rng = random.Random(seed)
    profile = _GPU_PROFILES[gpu_type]

    # Batch scaling factors: transformer/encoder are memory-BW bound, near-linear but not quite
    def batch_scale(component: str, bs: int) -> float:
        if bs == 1:
            return 1.0
        if component in ("transformer_12layers", "vision_encoder", "action_head_decoder"):
            return 1.0 + (bs - 1) * 0.65   # sub-linear
        return 1.0 + (bs - 1) * 0.1        # preprocessing barely scales

    components: Dict[str, ProfileComponent] = {}
    total_samples = []

    # Collect per-component samples
    comp_samples: Dict[str, List[float]] = {k: [] for k in profile}

    for _ in range(n_samples):
        step_total = 0.0
        for comp_name, (mean, std) in profile.items():
            scaled_mean = mean * batch_scale(comp_name, batch_size)
            scaled_std = std * batch_scale(comp_name, batch_size) ** 0.5
            sample = _normal_positive(rng, scaled_mean, scaled_std)
            comp_samples[comp_name].append(sample)
            step_total += sample
        total_samples.append(step_total)

    def p95(samples: List[float]) -> float:
        s = sorted(samples)
        idx = int(len(s) * 0.95)
        return s[min(idx, len(s) - 1)]

    def mean(samples: List[float]) -> float:
        return sum(samples) / len(samples)

    def std(samples: List[float]) -> float:
        m = mean(samples)
        return (sum((x - m) ** 2 for x in samples) / len(samples)) ** 0.5

    for comp_name, samples in comp_samples.items():
        components[comp_name] = ProfileComponent(
            name=comp_name,
            category=_COMPONENT_CATEGORIES[comp_name],
            latency_ms_mean=round(mean(samples), 2),
            latency_ms_std=round(std(samples), 2),
            latency_ms_p95=round(p95(samples), 2),
            memory_mb=_COMPONENT_MEMORY[comp_name],
            flops_billion=_COMPONENT_FLOPS[comp_name],
            optimizable=_OPTIMIZABLE[comp_name],
            optimization_hint=_OPTIMIZATION_HINTS[comp_name],
        )

    # Synthesize total_pipeline entry
    total_mean = mean(total_samples)
    total_std = std(total_samples)
    total_p95 = p95(total_samples)
    components["total_pipeline"] = ProfileComponent(
        name="total_pipeline",
        category="postprocessing",
        latency_ms_mean=round(total_mean, 2),
        latency_ms_std=round(total_std, 2),
        latency_ms_p95=round(total_p95, 2),
        memory_mb=_COMPONENT_MEMORY["total_pipeline"],
        flops_billion=_COMPONENT_FLOPS["total_pipeline"],
        optimizable=True,
        optimization_hint=_OPTIMIZATION_HINTS["total_pipeline"],
    )

    return components


def run_comparison(
    batch_sizes: List[int] = None,
    seed: int = 42,
) -> Dict[str, Dict[int, ProfileComponent]]:
    """
    Benchmark total_pipeline latency across batch sizes for A100, A10, Jetson.

    Returns: {gpu_type: {batch_size: ProfileComponent(total_pipeline)}}
    """
    if batch_sizes is None:
        batch_sizes = [1, 2, 4, 8]

    results: Dict[str, Dict[int, ProfileComponent]] = {}
    for gpu in ("A100-80G", "A10", "Jetson-AGX"):
        results[gpu] = {}
        for bs in batch_sizes:
            profile = simulate_profile(gpu_type=gpu, batch_size=bs, seed=seed)
            results[gpu][bs] = profile["total_pipeline"]

    return results


# ── SVG helpers ───────────────────────────────────────────────────────────────

_COMP_COLORS = {
    "image_resize":         "#64748B",
    "image_normalize":      "#94A3B8",
    "vision_encoder":       "#F59E0B",
    "language_tokenize":    "#10B981",
    "transformer_12layers": "#1D4ED8",
    "action_head_decoder":  "#C74634",
    "action_denormalize":   "#7C3AED",
    "action_chunk_sample":  "#0284C7",
    "total_pipeline":       "#E05A44",
}

_GPU_LINE_COLORS = {
    "A100-80G":   "#10B981",
    "A10":        "#F59E0B",
    "Jetson-AGX": "#EF4444",
}

_ORDERED_COMPONENTS = [
    "image_resize", "image_normalize", "language_tokenize",
    "vision_encoder", "transformer_12layers", "action_head_decoder",
    "action_denormalize", "action_chunk_sample",
]


def _svg_stacked_bar(profiles: Dict[str, Dict[str, ProfileComponent]]) -> str:
    """
    SVG stacked bar chart: 3 GPU groups side by side, 8 stacked component colors.
    profiles: {gpu_label: {comp_name: ProfileComponent}}
    """
    gpus = ["A100-80G", "A10", "Jetson-AGX"]
    svg_w, svg_h = 680, 320
    margin = {"top": 20, "right": 20, "bottom": 60, "left": 55}
    chart_w = svg_w - margin["left"] - margin["right"]
    chart_h = svg_h - margin["top"] - margin["bottom"]

    # Find max total latency for Y scale
    max_total = max(
        sum(profiles[g][c].latency_ms_mean for c in _ORDERED_COMPONENTS if c in profiles[g])
        for g in gpus if g in profiles
    )
    y_max = max_total * 1.1

    group_w = chart_w / len(gpus)
    bar_w = group_w * 0.55
    bar_x_offset = (group_w - bar_w) / 2

    def scale_y(val: float) -> float:
        return chart_h - (val / y_max * chart_h)

    bars_svg = ""
    # Y grid lines
    y_ticks = 5
    for i in range(y_ticks + 1):
        tick_val = y_max * i / y_ticks
        y = scale_y(tick_val)
        bars_svg += (
            f'<line x1="0" y1="{y:.1f}" x2="{chart_w}" y2="{y:.1f}" '
            f'stroke="#334155" stroke-width="1" stroke-dasharray="4,3"/>'
            f'<text x="-8" y="{y + 4:.1f}" text-anchor="end" fill="#64748B" font-size="10">'
            f'{tick_val:.0f}</text>'
        )

    for gi, gpu in enumerate(gpus):
        if gpu not in profiles:
            continue
        x_base = gi * group_w + bar_x_offset
        y_cursor = chart_h  # stack from bottom
        for comp in _ORDERED_COMPONENTS:
            if comp not in profiles[gpu]:
                continue
            val = profiles[gpu][comp].latency_ms_mean
            bar_h = val / y_max * chart_h
            color = _COMP_COLORS[comp]
            y_cursor -= bar_h
            bars_svg += (
                f'<rect x="{x_base:.1f}" y="{y_cursor:.1f}" '
                f'width="{bar_w:.1f}" height="{bar_h:.1f}" fill="{color}" opacity="0.9">'
                f'<title>{comp}: {val:.1f}ms</title></rect>'
            )

        # X axis label
        label = gpu.replace("-", " ")
        label_y = chart_h + 20
        bars_svg += (
            f'<text x="{x_base + bar_w / 2:.1f}" y="{label_y}" '
            f'text-anchor="middle" fill="#94A3B8" font-size="12">{label}</text>'
        )

    # Y axis label
    y_axis_label = (
        f'<text transform="rotate(-90)" x="{-chart_h / 2:.1f}" y="-42" '
        f'text-anchor="middle" fill="#64748B" font-size="11">Latency (ms)</text>'
    )

    # Legend
    legend_items = ""
    for i, comp in enumerate(_ORDERED_COMPONENTS):
        lx = (i % 4) * 155
        ly = chart_h + 42 + (i // 4) * 16
        legend_items += (
            f'<rect x="{lx}" y="{ly - 9}" width="10" height="10" fill="{_COMP_COLORS[comp]}"/>'
            f'<text x="{lx + 14}" y="{ly}" fill="#94A3B8" font-size="10">'
            f'{comp.replace("_", " ")}</text>'
        )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{svg_w}" height="{svg_h + 20}" '
        f'style="background:#1e293b;border-radius:8px">'
        f'<g transform="translate({margin["left"]},{margin["top"]})">'
        f'{bars_svg}{y_axis_label}{legend_items}'
        f'</g></svg>'
    )


def _svg_throughput_line(comparison: Dict[str, Dict[int, ProfileComponent]]) -> str:
    """
    SVG line chart: throughput (req/s) vs batch size for A100, A10, Jetson.
    """
    batch_sizes = sorted(next(iter(comparison.values())).keys())
    svg_w, svg_h = 580, 280
    margin = {"top": 20, "right": 30, "bottom": 55, "left": 60}
    chart_w = svg_w - margin["left"] - margin["right"]
    chart_h = svg_h - margin["top"] - margin["bottom"]

    # Compute throughput = batch_size / (latency_ms / 1000)
    all_throughputs = [
        bs / (comparison[gpu][bs].latency_ms_mean / 1000.0)
        for gpu in comparison
        for bs in batch_sizes
    ]
    y_max = max(all_throughputs) * 1.15
    x_max = max(batch_sizes)

    def sx(bs: int) -> float:
        return (batch_sizes.index(bs) / (len(batch_sizes) - 1)) * chart_w

    def sy(tp: float) -> float:
        return chart_h - (tp / y_max * chart_h)

    grid_svg = ""
    # Y grid
    for i in range(5):
        tick = y_max * i / 4
        y = sy(tick)
        grid_svg += (
            f'<line x1="0" y1="{y:.1f}" x2="{chart_w}" y2="{y:.1f}" '
            f'stroke="#334155" stroke-width="1" stroke-dasharray="4,3"/>'
            f'<text x="-8" y="{y + 4:.1f}" text-anchor="end" fill="#64748B" font-size="10">'
            f'{tick:.1f}</text>'
        )

    # X labels
    for bs in batch_sizes:
        x = sx(bs)
        grid_svg += (
            f'<text x="{x:.1f}" y="{chart_h + 18}" text-anchor="middle" '
            f'fill="#94A3B8" font-size="11">{bs}</text>'
        )

    # Axis labels
    grid_svg += (
        f'<text x="{chart_w / 2:.1f}" y="{chart_h + 36}" text-anchor="middle" '
        f'fill="#64748B" font-size="11">Batch Size</text>'
        f'<text transform="rotate(-90)" x="{-chart_h / 2:.1f}" y="-46" '
        f'text-anchor="middle" fill="#64748B" font-size="11">Throughput (req/s)</text>'
    )

    lines_svg = ""
    legend_svg = ""
    for li, (gpu, gpu_data) in enumerate(comparison.items()):
        color = _GPU_LINE_COLORS.get(gpu, "#888")
        points = [
            (sx(bs), sy(bs / (gpu_data[bs].latency_ms_mean / 1000.0)))
            for bs in batch_sizes
        ]
        polyline_pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
        lines_svg += (
            f'<polyline points="{polyline_pts}" fill="none" stroke="{color}" '
            f'stroke-width="2.5" stroke-linejoin="round"/>'
        )
        for x, y in points:
            lines_svg += f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="{color}"/>'

        lx = li * 160
        legend_svg += (
            f'<line x1="{lx}" y1="{chart_h + 48}" x2="{lx + 22}" y2="{chart_h + 48}" '
            f'stroke="{color}" stroke-width="2.5"/>'
            f'<text x="{lx + 26}" y="{chart_h + 52}" fill="#94A3B8" font-size="11">'
            f'{gpu}</text>'
        )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{svg_w}" height="{svg_h}" '
        f'style="background:#1e293b;border-radius:8px">'
        f'<g transform="translate({margin["left"]},{margin["top"]})">'
        f'{grid_svg}{lines_svg}{legend_svg}'
        f'</g></svg>'
    )


# ── HTML report ───────────────────────────────────────────────────────────────

def make_report(
    profiles: Dict[str, Dict[str, ProfileComponent]],
    comparison: Dict[str, Dict[int, ProfileComponent]],
    gpu_type: str,
    output_path: str,
) -> None:
    """Generate HTML report with KPI cards, SVG charts, and optimization table."""
    a100 = profiles.get("A100-80G", {})
    current = profiles.get(gpu_type, a100)
    total = current.get("total_pipeline")

    # KPI values
    p50 = total.latency_ms_mean if total else 0.0
    p95 = total.latency_ms_p95 if total else 0.0
    throughput = 1000.0 / comparison["A100-80G"][1].latency_ms_mean if comparison.get("A100-80G") else 0.0
    mem_peak = total.memory_mb / 1024.0 if total else 0.0

    p95_color = "#10B981" if p95 < 300 else "#EF4444"
    tp_str = f"{throughput:.2f}"
    mem_str = f"{mem_peak:.1f} GB"

    # Optimization table rows
    opt_rows = ""
    for comp in _ORDERED_COMPONENTS:
        if comp not in current:
            continue
        c = current[comp]
        opt_icon = "Yes" if c.optimizable else "No"
        opt_color = "#10B981" if c.optimizable else "#64748B"
        mem_disp = f"{c.memory_mb:.0f} MB" if c.memory_mb > 0 else "—"
        flops_disp = f"{c.flops_billion:.1f}B" if c.flops_billion else "—"
        opt_rows += (
            f"<tr>"
            f"<td><span style='display:inline-block;width:10px;height:10px;border-radius:2px;"
            f"background:{_COMP_COLORS[comp]};margin-right:6px;vertical-align:middle'></span>"
            f"{comp.replace('_', ' ')}</td>"
            f"<td>{c.category}</td>"
            f"<td>{c.latency_ms_mean:.1f}ms</td>"
            f"<td>{c.latency_ms_p95:.1f}ms</td>"
            f"<td>{mem_disp}</td>"
            f"<td>{flops_disp}</td>"
            f"<td style='color:{opt_color}'>{opt_icon}</td>"
            f"<td style='color:#93C5FD;font-size:.82em'>{c.optimization_hint}</td>"
            f"</tr>"
        )

    bar_svg = _svg_stacked_bar(profiles)
    line_svg = _svg_throughput_line(comparison)

    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>GR00T Inference Profiler — OCI Robot Cloud</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Segoe UI',system-ui,sans-serif;background:#1e293b;color:#e2e8f0;padding:28px 36px}}
h1{{color:#C74634;font-size:1.6em;margin-bottom:4px}}
.subtitle{{color:#64748B;font-size:.88em;margin-bottom:24px}}
h2{{color:#C74634;font-size:.82em;text-transform:uppercase;letter-spacing:.1em;
    border-bottom:1px solid #334155;padding-bottom:5px;margin:28px 0 14px}}
.kpi-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:8px}}
.kpi{{background:#0f172a;border-radius:10px;padding:16px 14px;text-align:center;border:1px solid #334155}}
.kpi-val{{font-size:1.9em;font-weight:700;line-height:1.15}}
.kpi-lbl{{color:#64748B;font-size:.76em;margin-top:4px;text-transform:uppercase;letter-spacing:.06em}}
.charts{{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin:10px 0}}
.chart-wrap{{background:#0f172a;border-radius:10px;padding:16px;border:1px solid #334155}}
.chart-title{{color:#94A3B8;font-size:.82em;text-transform:uppercase;letter-spacing:.07em;margin-bottom:12px}}
table{{width:100%;border-collapse:collapse;font-size:.85em}}
th{{background:#0f172a;color:#94A3B8;padding:8px 10px;text-align:left;
    font-size:.78em;text-transform:uppercase;letter-spacing:.07em;border-bottom:2px solid #334155}}
td{{padding:7px 10px;border-bottom:1px solid #1e3352}}
tr:hover td{{background:#162032}}
.badge{{display:inline-block;padding:2px 8px;border-radius:4px;font-size:.78em;font-weight:600}}
footer{{color:#334155;font-size:.78em;margin-top:32px;text-align:center}}
</style>
</head>
<body>

<h1>GR00T N1.6-3B Inference Profiler</h1>
<p class="subtitle">OCI Robot Cloud &middot; GPU: {gpu_type} &middot; Simulated profile &middot; Generated {ts}</p>

<h2>Key Performance Indicators</h2>
<div class="kpi-grid">
  <div class="kpi">
    <div class="kpi-val">{p50:.0f}ms</div>
    <div class="kpi-lbl">Total Latency p50</div>
  </div>
  <div class="kpi">
    <div class="kpi-val" style="color:{p95_color}">{p95:.0f}ms</div>
    <div class="kpi-lbl">Total Latency p95</div>
  </div>
  <div class="kpi">
    <div class="kpi-val" style="color:#10B981">{tp_str}</div>
    <div class="kpi-lbl">Throughput req/s (A100 bs=1)</div>
  </div>
  <div class="kpi">
    <div class="kpi-val">{mem_str}</div>
    <div class="kpi-lbl">Peak Memory (pipeline)</div>
  </div>
</div>

<h2>Latency Breakdown by Platform</h2>
<div class="chart-wrap">
  <div class="chart-title">Stacked component latency &mdash; A100 vs A10 vs Jetson AGX (ms)</div>
  {bar_svg}
</div>

<h2>Throughput vs Batch Size</h2>
<div class="chart-wrap">
  <div class="chart-title">Effective throughput (req/s) across batch sizes</div>
  {line_svg}
</div>

<h2>Component Optimization Analysis</h2>
<table>
  <thead>
    <tr>
      <th>Component</th>
      <th>Category</th>
      <th>Mean Latency</th>
      <th>p95 Latency</th>
      <th>Memory</th>
      <th>FLOPs</th>
      <th>Optimizable</th>
      <th>Optimization Hint</th>
    </tr>
  </thead>
  <tbody>
    {opt_rows}
  </tbody>
</table>

<footer>OCI Robot Cloud &mdash; github.com/qianjun22/roboticsai &mdash; Oracle Confidential</footer>
</body>
</html>"""

    Path(output_path).write_text(html)


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="GR00T inference latency profiler")
    parser.add_argument("--mock", action="store_true", default=True,
                        help="Use simulated data (default: True; no server required)")
    parser.add_argument("--gpu", default="A100-80G",
                        choices=list(_GPU_PROFILES.keys()),
                        help="GPU type for primary profile")
    parser.add_argument("--output", default="/tmp/inference_profiler.html",
                        help="Output HTML report path")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed for simulation reproducibility")
    args = parser.parse_args()

    print(f"[profiler] Simulating GR00T inference profile (gpu={args.gpu}, seed={args.seed})")

    # Build per-GPU profiles for chart (all 3 GPUs)
    profiles: Dict[str, Dict[str, ProfileComponent]] = {}
    for gpu in _GPU_PROFILES:
        print(f"[profiler]   profiling {gpu} ...")
        profiles[gpu] = simulate_profile(gpu_type=gpu, batch_size=1, seed=args.seed)

    # Batch size comparison
    print("[profiler] Running batch size comparison (bs=1,2,4,8) ...")
    comparison = run_comparison(batch_sizes=[1, 2, 4, 8], seed=args.seed)

    # Print summary to stdout
    primary = profiles[args.gpu]
    total = primary["total_pipeline"]
    print(f"\n[profiler] {args.gpu} results:")
    print(f"  total mean:  {total.latency_ms_mean:.1f}ms")
    print(f"  total p95:   {total.latency_ms_p95:.1f}ms")
    slo = "Met" if total.latency_ms_p95 < 300 else "MISSED"
    print(f"  SLO <300ms:  {slo}")
    print(f"  memory peak: {total.memory_mb / 1024:.2f} GB")
    print()

    print("[profiler] Component breakdown:")
    for comp in _ORDERED_COMPONENTS:
        if comp in primary:
            c = primary[comp]
            opt = "[opt]" if c.optimizable else "     "
            print(f"  {opt} {c.name:<30} mean={c.latency_ms_mean:>7.1f}ms  p95={c.latency_ms_p95:>7.1f}ms  mem={c.memory_mb:>7.0f}MB")

    # Generate HTML
    make_report(profiles, comparison, args.gpu, args.output)
    print(f"\n[profiler] Report written: {args.output}")

    # Write JSON alongside
    json_path = Path(args.output).with_suffix(".json")
    out_data = {
        gpu: {
            comp: {
                "category": c.category,
                "latency_ms_mean": c.latency_ms_mean,
                "latency_ms_std": c.latency_ms_std,
                "latency_ms_p95": c.latency_ms_p95,
                "memory_mb": c.memory_mb,
                "flops_billion": c.flops_billion,
                "optimizable": c.optimizable,
                "optimization_hint": c.optimization_hint,
            }
            for comp, c in gpu_profile.items()
        }
        for gpu, gpu_profile in profiles.items()
    }
    json_path.write_text(json.dumps(out_data, indent=2))
    print(f"[profiler] JSON written:   {json_path}")


if __name__ == "__main__":
    main()
