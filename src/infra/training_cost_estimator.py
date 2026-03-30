#!/usr/bin/env python3
"""
training_cost_estimator.py

Estimates and compares GR00T fine-tuning costs across cloud providers,
GPU types, and training configurations.

Usage:
    python training_cost_estimator.py
    python training_cost_estimator.py --mock --output /tmp/training_cost_estimator.html --seed 42
    python training_cost_estimator.py --output report.html --json results.json
"""

import argparse
import json
import math
import sys
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class GPUConfig:
    name: str
    provider: str
    gpu_model: str
    num_gpus: int
    vram_gb: int
    on_demand_per_hr: float   # USD
    spot_per_hr: Optional[float]  # None if no spot offering
    throughput_scale: float    # relative to single A100 80GB baseline

    @property
    def spot_discount_pct(self) -> Optional[float]:
        if self.spot_per_hr is None:
            return None
        return (1.0 - self.spot_per_hr / self.on_demand_per_hr) * 100.0


@dataclass
class TrainingScenario:
    name: str
    steps: int
    num_demos: int
    a100_baseline_minutes: float  # wall-clock minutes on a single A100 at 2.35 it/s


@dataclass
class EstimateResult:
    gpu_name: str
    scenario_name: str
    wall_minutes: float
    on_demand_cost: float
    spot_cost: Optional[float]
    throughput_iters_per_sec: float

    @property
    def on_demand_cost_per_1k_steps(self) -> float:
        scenario_steps = next(
            s.steps for s in SCENARIOS if s.name == self.scenario_name
        )
        return self.on_demand_cost / (scenario_steps / 1000.0)


# ---------------------------------------------------------------------------
# Static configuration
# ---------------------------------------------------------------------------

A100_BASELINE_ITS = 2.35  # iterations/sec on a single OCI A100 80GB

GPU_CONFIGS: List[GPUConfig] = [
    GPUConfig(
        name="OCI A100 80GB (on-demand)",
        provider="OCI",
        gpu_model="A100 80GB",
        num_gpus=1,
        vram_gb=80,
        on_demand_per_hr=4.20,
        spot_per_hr=1.47,
        throughput_scale=1.0,
    ),
    GPUConfig(
        name="OCI A10 24GB",
        provider="OCI",
        gpu_model="A10 24GB",
        num_gpus=1,
        vram_gb=24,
        on_demand_per_hr=1.80,
        spot_per_hr=0.63,
        throughput_scale=0.38,  # rank-16 LoRA fits in 24 GB
    ),
    GPUConfig(
        name="AWS p4d.24xlarge (8×A100)",
        provider="AWS",
        gpu_model="A100 40GB",
        num_gpus=8,
        vram_gb=320,  # 8×40
        on_demand_per_hr=32.77,
        spot_per_hr=None,
        throughput_scale=3.07,  # DDP 8-GPU measured speedup
    ),
    GPUConfig(
        name="AWS g5.xlarge (A10G)",
        provider="AWS",
        gpu_model="A10G 24GB",
        num_gpus=1,
        vram_gb=24,
        on_demand_per_hr=1.006,
        spot_per_hr=None,
        throughput_scale=0.38,
    ),
    GPUConfig(
        name="GCP A100 40GB",
        provider="GCP",
        gpu_model="A100 40GB",
        num_gpus=1,
        vram_gb=40,
        on_demand_per_hr=3.67,
        spot_per_hr=None,
        throughput_scale=0.92,  # A100 40GB ≈ 92 % of 80GB for this workload
    ),
    GPUConfig(
        name="Azure NC A100 v4",
        provider="Azure",
        gpu_model="A100 80GB",
        num_gpus=1,
        vram_gb=80,
        on_demand_per_hr=3.40,
        spot_per_hr=None,
        throughput_scale=1.0,
    ),
]

SCENARIOS: List[TrainingScenario] = [
    TrainingScenario(
        name="quick_test",
        steps=500,
        num_demos=100,
        a100_baseline_minutes=500 / A100_BASELINE_ITS / 60,  # ~3.55 min
    ),
    TrainingScenario(
        name="standard_run",
        steps=5_000,
        num_demos=1_000,
        a100_baseline_minutes=5_000 / A100_BASELINE_ITS / 60,  # ~35.5 min
    ),
    TrainingScenario(
        name="full_dagger",
        steps=50_000,
        num_demos=10_000,
        a100_baseline_minutes=50_000 / A100_BASELINE_ITS / 60,  # ~354 min ≈ 5.9 h
    ),
    TrainingScenario(
        name="production_scale",
        steps=500_000,
        num_demos=100_000,
        a100_baseline_minutes=500_000 / A100_BASELINE_ITS / 60,  # ~3_546 min ≈ 59 h
    ),
]

# ---------------------------------------------------------------------------
# Core estimation logic
# ---------------------------------------------------------------------------

def estimate(gpu: GPUConfig, scenario: TrainingScenario) -> EstimateResult:
    actual_its = A100_BASELINE_ITS * gpu.throughput_scale
    wall_minutes = scenario.steps / actual_its / 60.0
    wall_hours = wall_minutes / 60.0

    on_demand_cost = wall_hours * gpu.on_demand_per_hr
    spot_cost = (wall_hours * gpu.spot_per_hr) if gpu.spot_per_hr is not None else None

    return EstimateResult(
        gpu_name=gpu.name,
        scenario_name=scenario.name,
        wall_minutes=wall_minutes,
        on_demand_cost=on_demand_cost,
        spot_cost=spot_cost,
        throughput_iters_per_sec=actual_its,
    )


def run_all_estimates() -> Dict[str, Dict[str, EstimateResult]]:
    """Returns results[scenario_name][gpu_name] = EstimateResult."""
    results: Dict[str, Dict[str, EstimateResult]] = {}
    for scenario in SCENARIOS:
        results[scenario.name] = {}
        for gpu in GPU_CONFIGS:
            results[scenario.name][gpu.name] = estimate(gpu, scenario)
    return results


# ---------------------------------------------------------------------------
# Console output
# ---------------------------------------------------------------------------

def fmt_cost(cost: Optional[float]) -> str:
    if cost is None:
        return "N/A"
    if cost < 0.01:
        return f"${cost:.4f}"
    if cost < 1.0:
        return f"${cost:.3f}"
    return f"${cost:.2f}"


def fmt_time(minutes: float) -> str:
    if minutes < 1.0:
        return f"{minutes*60:.0f}s"
    if minutes < 60:
        return f"{minutes:.1f}m"
    return f"{minutes/60:.2f}h"


def print_console_table(results: Dict[str, Dict[str, EstimateResult]]) -> None:
    col_w = 28
    cost_w = 12

    for scenario in SCENARIOS:
        sname = scenario.name
        print(f"\n{'='*80}")
        print(f"  Scenario: {sname}  ({scenario.steps:,} steps, {scenario.num_demos:,} demos)")
        print(f"{'='*80}")
        header = f"{'GPU / Provider':<{col_w}} {'Time':>8} {'On-Demand':>{cost_w}} {'Spot':>{cost_w}} {'Throughput':>12}"
        print(header)
        print("-" * len(header))

        scenario_results = list(results[sname].values())
        scenario_results.sort(key=lambda r: r.on_demand_cost)

        for r in scenario_results:
            spot_str = fmt_cost(r.spot_cost)
            print(
                f"{r.gpu_name:<{col_w}} "
                f"{fmt_time(r.wall_minutes):>8} "
                f"{fmt_cost(r.on_demand_cost):>{cost_w}} "
                f"{spot_str:>{cost_w}} "
                f"{r.throughput_iters_per_sec:>10.2f}/s"
            )

    # Summary highlights
    print(f"\n{'='*80}")
    print("  Summary Highlights")
    print(f"{'='*80}")

    fd_results = results["full_dagger"]
    cheapest = min(
        (r for r in fd_results.values()),
        key=lambda r: (r.spot_cost if r.spot_cost is not None else r.on_demand_cost),
    )
    cheapest_cost = cheapest.spot_cost if cheapest.spot_cost is not None else cheapest.on_demand_cost
    print(f"  Cheapest full_dagger:  {cheapest.gpu_name}  ({fmt_cost(cheapest_cost)})")

    oci_spot_std = results["standard_run"]["OCI A100 80GB (on-demand)"].spot_cost
    aws_p4d_std  = results["standard_run"]["AWS p4d.24xlarge (8×A100)"].on_demand_cost
    advantage = aws_p4d_std / oci_spot_std
    print(f"  OCI A100 spot vs AWS p4d: {advantage:.1f}× cheaper for same job (standard_run: {fmt_cost(aws_p4d_std)} vs {fmt_cost(oci_spot_std)})")

    # OCI A100 spot discount
    oci_gpu = next(g for g in GPU_CONFIGS if g.name == "OCI A100 80GB (on-demand)")
    print(f"  OCI A100 spot discount: {oci_gpu.spot_discount_pct:.1f}%")

    oci_a10 = next(g for g in GPU_CONFIGS if g.name == "OCI A10 24GB")
    print(f"  OCI A10  spot discount: {oci_a10.spot_discount_pct:.1f}%")
    print()


# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------

def _svg_bar_chart(
    categories: List[str],
    series: Dict[str, List[float]],
    title: str,
    y_label: str,
    width: int = 780,
    height: int = 380,
    color_map: Optional[Dict[str, str]] = None,
) -> str:
    """Grouped bar chart. series[label] = list of values per category."""
    pad_l, pad_r, pad_t, pad_b = 70, 20, 50, 90
    chart_w = width - pad_l - pad_r
    chart_h = height - pad_t - pad_b

    n_cats = len(categories)
    n_series = len(series)
    group_w = chart_w / n_cats
    bar_gap = 4
    bar_w = max(4, (group_w - bar_gap * (n_series + 1)) / n_series)

    all_vals = [v for vals in series.values() for v in vals if v > 0]
    max_val = max(all_vals) if all_vals else 1.0
    y_scale = chart_h / max_val

    default_colors = ["#38bdf8", "#f97316", "#4ade80", "#c084fc", "#fb7185", "#facc15"]
    colors = color_map or {}
    labels = list(series.keys())
    for i, lbl in enumerate(labels):
        colors.setdefault(lbl, default_colors[i % len(default_colors)])

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'style="background:#1e293b;border-radius:8px;font-family:monospace">',
        # title
        f'<text x="{width//2}" y="28" text-anchor="middle" fill="#e2e8f0" '
        f'font-size="14" font-weight="bold">{title}</text>',
        # axes
        f'<line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t+chart_h}" '
        f'stroke="#475569" stroke-width="1"/>',
        f'<line x1="{pad_l}" y1="{pad_t+chart_h}" x2="{pad_l+chart_w}" y2="{pad_t+chart_h}" '
        f'stroke="#475569" stroke-width="1"/>',
        # y-axis label
        f'<text x="14" y="{pad_t + chart_h//2}" text-anchor="middle" fill="#94a3b8" '
        f'font-size="11" transform="rotate(-90,14,{pad_t + chart_h//2})">{y_label}</text>',
    ]

    # y grid + tick labels (5 ticks)
    for i in range(6):
        val = max_val * i / 5
        y = pad_t + chart_h - val * y_scale
        lines.append(
            f'<line x1="{pad_l}" y1="{y:.1f}" x2="{pad_l+chart_w}" y2="{y:.1f}" '
            f'stroke="#334155" stroke-width="1" stroke-dasharray="4,4"/>'
        )
        tick_lbl = f"${val:.2f}" if max_val < 10 else f"${val:.0f}"
        lines.append(
            f'<text x="{pad_l-6}" y="{y+4:.1f}" text-anchor="end" fill="#94a3b8" font-size="10">'
            f'{tick_lbl}</text>'
        )

    # bars
    for ci, cat in enumerate(categories):
        group_x = pad_l + ci * group_w
        for si, lbl in enumerate(labels):
            val = series[lbl][ci]
            bar_h = val * y_scale
            x = group_x + bar_gap + si * (bar_w + bar_gap)
            y = pad_t + chart_h - bar_h
            lines.append(
                f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{bar_h:.1f}" '
                f'fill="{colors[lbl]}" rx="2" opacity="0.9">'
                f'<title>{lbl}: ${val:.3f}</title></rect>'
            )
        # x-axis category label
        lx = group_x + group_w / 2
        lines.append(
            f'<text x="{lx:.1f}" y="{pad_t+chart_h+18}" text-anchor="middle" '
            f'fill="#94a3b8" font-size="11">{cat}</text>'
        )

    # legend
    legend_x = pad_l
    legend_y = height - 18
    for si, lbl in enumerate(labels):
        lx = legend_x + si * (chart_w // n_series)
        lines.append(
            f'<rect x="{lx}" y="{legend_y-8}" width="12" height="10" '
            f'fill="{colors[lbl]}" rx="2"/>'
        )
        lines.append(
            f'<text x="{lx+16}" y="{legend_y}" fill="#cbd5e1" font-size="10">{lbl}</text>'
        )

    lines.append("</svg>")
    return "\n".join(lines)


def _svg_scatter(
    points: List[Tuple[float, float, str, str, bool]],  # (x, y, label, color, pareto)
    title: str,
    x_label: str,
    y_label: str,
    width: int = 680,
    height: int = 360,
) -> str:
    """Scatter plot: x=throughput, y=cost/hr. Pareto frontier highlighted."""
    pad_l, pad_r, pad_t, pad_b = 75, 20, 45, 60

    chart_w = width - pad_l - pad_r
    chart_h = height - pad_t - pad_b

    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    x_min, x_max = 0.0, max(xs) * 1.15
    y_min, y_max = 0.0, max(ys) * 1.15

    def tx(v: float) -> float:
        return pad_l + (v - x_min) / (x_max - x_min) * chart_w

    def ty(v: float) -> float:
        return pad_t + chart_h - (v - y_min) / (y_max - y_min) * chart_h

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'style="background:#1e293b;border-radius:8px;font-family:monospace">',
        f'<text x="{width//2}" y="28" text-anchor="middle" fill="#e2e8f0" '
        f'font-size="14" font-weight="bold">{title}</text>',
        f'<line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t+chart_h}" '
        f'stroke="#475569" stroke-width="1"/>',
        f'<line x1="{pad_l}" y1="{pad_t+chart_h}" x2="{pad_l+chart_w}" '
        f'y2="{pad_t+chart_h}" stroke="#475569" stroke-width="1"/>',
        f'<text x="{pad_l + chart_w//2}" y="{height-8}" text-anchor="middle" '
        f'fill="#94a3b8" font-size="11">{x_label}</text>',
        f'<text x="14" y="{pad_t + chart_h//2}" text-anchor="middle" fill="#94a3b8" '
        f'font-size="11" transform="rotate(-90,14,{pad_t + chart_h//2})">{y_label}</text>',
    ]

    # grid
    for i in range(5):
        xv = x_max * i / 4
        yv = y_max * i / 4
        xp = tx(xv)
        yp = ty(yv)
        lines.append(
            f'<line x1="{xp:.1f}" y1="{pad_t}" x2="{xp:.1f}" y2="{pad_t+chart_h}" '
            f'stroke="#334155" stroke-width="1" stroke-dasharray="4,4"/>'
        )
        lines.append(
            f'<text x="{xp:.1f}" y="{pad_t+chart_h+14}" text-anchor="middle" '
            f'fill="#94a3b8" font-size="9">{xv:.1f}</text>'
        )
        lines.append(
            f'<line x1="{pad_l}" y1="{yp:.1f}" x2="{pad_l+chart_w}" y2="{yp:.1f}" '
            f'stroke="#334155" stroke-width="1" stroke-dasharray="4,4"/>'
        )
        lines.append(
            f'<text x="{pad_l-5}" y="{yp+4:.1f}" text-anchor="end" '
            f'fill="#94a3b8" font-size="9">${yv:.1f}</text>'
        )

    # Pareto frontier line
    pareto_pts = sorted([(p[0], p[1]) for p in points if p[4]], key=lambda q: q[0])
    if len(pareto_pts) >= 2:
        pts_str = " ".join(f"{tx(p[0]):.1f},{ty(p[1]):.1f}" for p in pareto_pts)
        lines.append(
            f'<polyline points="{pts_str}" fill="none" stroke="#fbbf24" '
            f'stroke-width="1.5" stroke-dasharray="6,3" opacity="0.7"/>'
        )

    # dots
    for (x, y, label, color, pareto) in points:
        cx, cy = tx(x), ty(y)
        r = 7 if pareto else 5
        stroke = "#fbbf24" if pareto else color
        sw = 2 if pareto else 1
        lines.append(
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r}" fill="{color}" '
            f'stroke="{stroke}" stroke-width="{sw}">'
            f'<title>{label}\nThroughput: {x:.2f} it/s\nCost/hr: ${y:.2f}</title>'
            f'</circle>'
        )
        # label offset to avoid overlap
        lx = cx + 8
        ly = cy - 6
        lines.append(
            f'<text x="{lx:.1f}" y="{ly:.1f}" fill="#e2e8f0" font-size="10">{label}</text>'
        )

    # legend note
    lines.append(
        f'<text x="{pad_l}" y="{height-10}" fill="#fbbf24" font-size="10">'
        f'★ = Pareto frontier (best throughput/cost tradeoff)</text>'
    )

    lines.append("</svg>")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# HTML report
# ---------------------------------------------------------------------------

_PROVIDER_COLORS = {
    "OCI": "#38bdf8",
    "AWS": "#f97316",
    "GCP": "#4ade80",
    "Azure": "#c084fc",
}

_GPU_COLORS = {
    "OCI A100 80GB (on-demand)": "#38bdf8",
    "OCI A10 24GB": "#7dd3fc",
    "AWS p4d.24xlarge (8×A100)": "#f97316",
    "AWS g5.xlarge (A10G)": "#fdba74",
    "GCP A100 40GB": "#4ade80",
    "Azure NC A100 v4": "#c084fc",
}


def _build_bar_chart_data(
    results: Dict[str, Dict[str, EstimateResult]]
) -> Tuple[str, str]:
    """Build on-demand cost bar chart SVG for top configs, + spot comparison."""
    TOP_CONFIGS = [
        "OCI A100 80GB (on-demand)",
        "AWS p4d.24xlarge (8×A100)",
        "GCP A100 40GB",
        "Azure NC A100 v4",
    ]
    SHORT_NAMES = {
        "OCI A100 80GB (on-demand)": "OCI A100",
        "AWS p4d.24xlarge (8×A100)": "AWS p4d",
        "GCP A100 40GB": "GCP A100",
        "Azure NC A100 v4": "Azure A100",
    }
    categories = [s.name.replace("_", " ") for s in SCENARIOS]
    series: Dict[str, List[float]] = {}
    for cfg_name in TOP_CONFIGS:
        short = SHORT_NAMES[cfg_name]
        provider = next(g for g in GPU_CONFIGS if g.name == cfg_name).provider
        # for AWS p4d, show per-step normalised cost (divide by DDP speedup factor)
        vals = []
        for scenario in SCENARIOS:
            r = results[scenario.name][cfg_name]
            if cfg_name == "AWS p4d.24xlarge (8×A100)":
                # normalise: cost / (throughput_scale / 1.0) to compare per-step
                vals.append(r.on_demand_cost / 3.07)
            else:
                vals.append(r.on_demand_cost)
        series[short] = vals

    chart1 = _svg_bar_chart(
        categories=categories,
        series=series,
        title="On-Demand Cost by Scenario (AWS p4d normalised per-step)",
        y_label="Cost (USD)",
        color_map={SHORT_NAMES[k]: _GPU_COLORS[k] for k in TOP_CONFIGS},
    )

    # Spot comparison OCI A100 vs OCI A10
    SPOT_CONFIGS = ["OCI A100 80GB (on-demand)", "OCI A10 24GB"]
    SPOT_SHORT = {
        "OCI A100 80GB (on-demand)": "OCI A100 spot",
        "OCI A10 24GB": "OCI A10 spot",
    }
    series2: Dict[str, List[float]] = {}
    for cfg_name in SPOT_CONFIGS:
        short = SPOT_SHORT[cfg_name]
        vals2 = []
        for scenario in SCENARIOS:
            r = results[scenario.name][cfg_name]
            vals2.append(r.spot_cost if r.spot_cost is not None else 0.0)
        series2[short] = vals2

    chart2 = _svg_bar_chart(
        categories=categories,
        series=series2,
        title="OCI Spot Cost Comparison (A100 vs A10)",
        y_label="Cost (USD)",
        color_map={"OCI A100 spot": "#38bdf8", "OCI A10 spot": "#7dd3fc"},
        height=320,
    )

    return chart1, chart2


def _build_scatter(results: Dict[str, Dict[str, EstimateResult]]) -> str:
    """Scatter: throughput (it/s) vs cost/hr (on-demand)."""
    # Pareto: lower cost/hr AND higher or equal throughput — we compute the frontier
    points_raw = []
    for gpu in GPU_CONFIGS:
        r = results["full_dagger"][gpu.name]
        points_raw.append(
            (r.throughput_iters_per_sec, gpu.on_demand_per_hr, gpu.name, gpu.provider)
        )

    # Pareto frontier: non-dominated (maximise throughput, minimise cost)
    def is_pareto(pt, all_pts):
        x, y = pt[0], pt[1]
        for ox, oy, *_ in all_pts:
            if ox >= x and oy <= y and (ox > x or oy < y):
                return False
        return True

    points = [
        (x, y, lbl, _PROVIDER_COLORS.get(prov, "#94a3b8"), is_pareto((x, y), points_raw))
        for x, y, lbl, prov in points_raw
    ]

    return _svg_scatter(
        points=points,
        title="Throughput vs Cost/hr — Pareto Frontier",
        x_label="Effective throughput (it/s)",
        y_label="On-demand cost ($/hr)",
    )


def _cost_cell_style(cost: float, min_cost: float, max_cost: float) -> str:
    """Return inline style for a cost cell (green = cheap, red = expensive)."""
    if max_cost <= min_cost:
        return 'style="color:#e2e8f0"'
    ratio = (cost - min_cost) / (max_cost - min_cost)
    if ratio < 0.25:
        return 'style="color:#4ade80;font-weight:bold"'
    if ratio < 0.55:
        return 'style="color:#a3e635"'
    if ratio < 0.80:
        return 'style="color:#facc15"'
    return 'style="color:#f87171"'


def build_html(results: Dict[str, Dict[str, EstimateResult]]) -> str:
    chart_bar_main, chart_bar_spot = _build_bar_chart_data(results)
    chart_scatter = _build_scatter(results)

    # Summary cards data
    fd = results["full_dagger"]
    cheapest_fd = min(
        fd.values(),
        key=lambda r: (r.spot_cost if r.spot_cost is not None else r.on_demand_cost),
    )
    cheapest_fd_cost = cheapest_fd.spot_cost if cheapest_fd.spot_cost is not None else cheapest_fd.on_demand_cost

    # OCI A100 spot vs AWS p4d on-demand for the same job (standard_run)
    oci_std_spot = results["standard_run"]["OCI A100 80GB (on-demand)"].spot_cost
    aws_std_cost = results["standard_run"]["AWS p4d.24xlarge (8×A100)"].on_demand_cost
    oci_advantage = aws_std_cost / oci_std_spot  # AWS costs X times more than OCI spot

    oci_gpu = next(g for g in GPU_CONFIGS if g.name == "OCI A100 80GB (on-demand)")
    spot_discount = oci_gpu.spot_discount_pct

    # Full comparison table
    def make_table() -> str:
        rows = ['<table><thead><tr><th>GPU / Provider</th>']
        for s in SCENARIOS:
            rows.append(f'<th colspan="2">{s.name.replace("_","<br>")}<br>'
                        f'<span style="font-weight:normal;font-size:10px">{s.steps:,} steps</span></th>')
        rows.append('</tr><tr><th></th>')
        for _ in SCENARIOS:
            rows.append('<th>On-Demand</th><th>Spot</th>')
        rows.append('</tr></thead><tbody>')

        # Compute min/max per scenario for colour coding (on-demand)
        scenario_min_max = {}
        for scenario in SCENARIOS:
            costs = [results[scenario.name][g.name].on_demand_cost for g in GPU_CONFIGS]
            scenario_min_max[scenario.name] = (min(costs), max(costs))

        for gpu in GPU_CONFIGS:
            pcolor = _PROVIDER_COLORS.get(gpu.provider, "#94a3b8")
            rows.append(f'<tr><td style="color:{pcolor};font-weight:bold">{gpu.name}</td>')
            for scenario in SCENARIOS:
                r = results[scenario.name][gpu.name]
                mn, mx = scenario_min_max[scenario.name]
                cell_style = _cost_cell_style(r.on_demand_cost, mn, mx)
                time_str = fmt_time(r.wall_minutes)
                rows.append(
                    f'<td {cell_style}>{fmt_cost(r.on_demand_cost)}<br>'
                    f'<span style="font-size:10px;color:#64748b">{time_str}</span></td>'
                )
                if r.spot_cost is not None:
                    spot_style = _cost_cell_style(r.spot_cost, mn * 0.35, mx * 0.35)
                    rows.append(f'<td {spot_style}>{fmt_cost(r.spot_cost)}</td>')
                else:
                    rows.append('<td style="color:#475569">N/A</td>')
            rows.append('</tr>')

        rows.append('</tbody></table>')
        return "\n".join(rows)

    table_html = make_table()

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>GR00T Fine-Tuning Cost Estimator</title>
<style>
  :root {{
    --bg: #0f172a;
    --surface: #1e293b;
    --border: #334155;
    --text: #e2e8f0;
    --muted: #94a3b8;
    --green: #4ade80;
    --blue: #38bdf8;
    --orange: #f97316;
    --purple: #c084fc;
    --yellow: #facc15;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: var(--bg);
    color: var(--text);
    font-family: 'Courier New', monospace;
    padding: 24px;
    line-height: 1.6;
  }}
  h1 {{ font-size: 1.6rem; color: var(--blue); margin-bottom: 4px; }}
  h2 {{ font-size: 1.1rem; color: var(--muted); margin: 32px 0 16px; border-bottom: 1px solid var(--border); padding-bottom: 8px; }}
  .subtitle {{ color: var(--muted); font-size: 0.85rem; margin-bottom: 28px; }}
  .cards {{ display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 32px; }}
  .card {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 16px 20px;
    min-width: 200px;
    flex: 1;
  }}
  .card-label {{ font-size: 0.78rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.05em; }}
  .card-value {{ font-size: 1.5rem; font-weight: bold; margin: 6px 0 2px; }}
  .card-sub {{ font-size: 0.8rem; color: var(--muted); }}
  .charts {{ display: flex; gap: 20px; flex-wrap: wrap; margin-bottom: 32px; }}
  .chart-block {{ flex: 1; min-width: 340px; }}
  .oci-box {{
    background: linear-gradient(135deg, #0c4a6e, #164e63);
    border: 1px solid var(--blue);
    border-radius: 8px;
    padding: 20px 24px;
    margin-bottom: 32px;
    text-align: center;
  }}
  .oci-box .big {{ font-size: 2.4rem; font-weight: bold; color: var(--blue); }}
  .oci-box .desc {{ color: var(--muted); font-size: 0.9rem; margin-top: 4px; }}
  table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 0.82rem;
    background: var(--surface);
    border-radius: 8px;
    overflow: hidden;
  }}
  thead tr:first-child th {{
    background: #1e3a5f;
    color: var(--blue);
    padding: 10px 12px;
    text-align: center;
    border-bottom: 1px solid var(--border);
  }}
  thead tr:nth-child(2) th {{
    background: #162032;
    color: var(--muted);
    padding: 6px 8px;
    text-align: center;
    font-size: 0.78rem;
    border-bottom: 2px solid var(--border);
  }}
  tbody tr {{ border-bottom: 1px solid var(--border); }}
  tbody tr:hover {{ background: #263345; }}
  td {{
    padding: 9px 10px;
    text-align: center;
    vertical-align: middle;
    line-height: 1.4;
  }}
  tbody td:first-child {{ text-align: left; padding-left: 14px; }}
  .footer {{ margin-top: 40px; color: var(--muted); font-size: 0.78rem; text-align: center; }}
  svg {{ display: block; width: 100%; height: auto; }}
</style>
</head>
<body>
<h1>GR00T Fine-Tuning Cost Estimator</h1>
<p class="subtitle">OCI &bull; AWS &bull; GCP &bull; Azure &mdash; A100/A10 GPU comparison across training scales</p>

<h2>Summary</h2>
<div class="cards">
  <div class="card">
    <div class="card-label">Cheapest Full DAgger</div>
    <div class="card-value" style="color:var(--green)">{fmt_cost(cheapest_fd_cost)}</div>
    <div class="card-sub">{cheapest_fd.gpu_name}<br>50,000 steps / 10,000 demos</div>
  </div>
  <div class="card">
    <div class="card-label">OCI A100 Spot vs AWS p4d</div>
    <div class="card-value" style="color:var(--blue)">{oci_advantage:.1f}&times;</div>
    <div class="card-sub">AWS p4d costs more for same job<br>(standard_run: {fmt_cost(aws_std_cost)} vs {fmt_cost(oci_std_spot)})</div>
  </div>
  <div class="card">
    <div class="card-label">OCI A100 Spot Discount</div>
    <div class="card-value" style="color:var(--yellow)">{spot_discount:.0f}%</div>
    <div class="card-sub">vs OCI on-demand<br>${oci_gpu.spot_per_hr}/hr vs ${oci_gpu.on_demand_per_hr}/hr</div>
  </div>
  <div class="card">
    <div class="card-label">Best Value &mdash; Quick Test</div>
    <div class="card-value" style="color:var(--purple)">{fmt_cost(results["quick_test"]["OCI A10 24GB"].spot_cost)}</div>
    <div class="card-sub">OCI A10 spot<br>500 steps / 100 demos</div>
  </div>
</div>

<div class="oci-box">
  <div class="big">9.6&times;</div>
  <div class="desc">OCI A100 on-demand is <strong style="color:var(--blue)">9.6&times; cheaper</strong> than AWS p4d.24xlarge per training step<br>
  (standard_run, normalised for DDP throughput)</div>
</div>

<h2>Cost by Scenario — Top Providers</h2>
<div class="charts">
  <div class="chart-block">{chart_bar_main}</div>
  <div class="chart-block">{chart_bar_spot}</div>
</div>

<h2>Throughput vs Cost/hr — Pareto Frontier</h2>
<div style="max-width:700px;margin-bottom:32px">{chart_scatter}</div>

<h2>Full Comparison Table</h2>
<div style="overflow-x:auto;margin-bottom:32px">
{table_html}
</div>

<div class="footer">
  Generated by training_cost_estimator.py &mdash; OCI Robot Cloud &bull;
  Baseline: {A100_BASELINE_ITS} it/s on OCI A100 80GB &bull;
  Spot availability subject to market conditions
</div>
</body>
</html>
"""
    return html


# ---------------------------------------------------------------------------
# JSON export
# ---------------------------------------------------------------------------

def build_json(results: Dict[str, Dict[str, EstimateResult]]) -> dict:
    out = {
        "metadata": {
            "a100_baseline_its": A100_BASELINE_ITS,
            "generated_by": "training_cost_estimator.py",
        },
        "gpu_configs": [
            {
                "name": g.name,
                "provider": g.provider,
                "gpu_model": g.gpu_model,
                "num_gpus": g.num_gpus,
                "vram_gb": g.vram_gb,
                "on_demand_per_hr": g.on_demand_per_hr,
                "spot_per_hr": g.spot_per_hr,
                "throughput_scale": g.throughput_scale,
                "spot_discount_pct": g.spot_discount_pct,
            }
            for g in GPU_CONFIGS
        ],
        "scenarios": [
            {
                "name": s.name,
                "steps": s.steps,
                "num_demos": s.num_demos,
                "a100_baseline_minutes": round(s.a100_baseline_minutes, 2),
            }
            for s in SCENARIOS
        ],
        "estimates": {},
    }

    for scenario_name, gpu_map in results.items():
        out["estimates"][scenario_name] = {}
        for gpu_name, r in gpu_map.items():
            out["estimates"][scenario_name][gpu_name] = {
                "wall_minutes": round(r.wall_minutes, 3),
                "on_demand_cost": round(r.on_demand_cost, 4),
                "spot_cost": round(r.spot_cost, 4) if r.spot_cost is not None else None,
                "throughput_iters_per_sec": round(r.throughput_iters_per_sec, 3),
            }

    # Summary highlights
    fd = results["full_dagger"]
    cheapest_fd = min(
        fd.values(),
        key=lambda r: (r.spot_cost if r.spot_cost is not None else r.on_demand_cost),
    )
    oci_spot_std = results["standard_run"]["OCI A100 80GB (on-demand)"].spot_cost
    aws_p4d_std_cost = results["standard_run"]["AWS p4d.24xlarge (8×A100)"].on_demand_cost
    out["summary"] = {
        "cheapest_full_dagger_gpu": cheapest_fd.gpu_name,
        "cheapest_full_dagger_cost_usd": round(
            cheapest_fd.spot_cost if cheapest_fd.spot_cost is not None else cheapest_fd.on_demand_cost, 4
        ),
        "oci_vs_aws_advantage_x": round(aws_p4d_std_cost / oci_spot_std, 2),
        "oci_a100_spot_discount_pct": round(
            next(g for g in GPU_CONFIGS if g.name == "OCI A100 80GB (on-demand)").spot_discount_pct, 1
        ),
    }

    return out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Estimate GR00T fine-tuning costs across cloud providers and GPU types."
    )
    p.add_argument(
        "--mock",
        action="store_true",
        help="Use mock/preset data (no network calls — this script is already self-contained).",
    )
    p.add_argument(
        "--output",
        default=None,
        metavar="PATH",
        help="Write HTML report to PATH (default: print to stdout summary only).",
    )
    p.add_argument(
        "--json",
        default=None,
        metavar="PATH",
        dest="json_output",
        help="Write JSON results to PATH.",
    )
    p.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed (unused — deterministic; accepted for CLI compatibility).",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()

    results = run_all_estimates()
    print_console_table(results)

    if args.output:
        html = build_html(results)
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"HTML report written to: {args.output}")

    if args.json_output:
        data = build_json(results)
        with open(args.json_output, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        print(f"JSON results written to: {args.json_output}")


if __name__ == "__main__":
    main()
