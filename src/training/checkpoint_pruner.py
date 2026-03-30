#!/usr/bin/env python3
"""
checkpoint_pruner.py — GR00T checkpoint structured pruning analyzer.

Simulates layer-wise magnitude pruning across sparsity levels (10–50%),
estimates MAE/latency/size tradeoffs, and outputs an HTML report + JSON results.

Usage:
    python checkpoint_pruner.py [--mock] [--checkpoint STR] [--output PATH] [--seed INT]
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Dict, Optional, Tuple


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class LayerInfo:
    name: str
    group: str          # vision_encoder | transformer | action_head | lora_adapters
    layer_index: int    # index within group
    num_params: int
    weight_mean: float
    weight_std: float
    pct_near_zero: float   # % of weights with |w| < 0.01
    sensitivity_score: float  # 0-1; higher = more sensitive, prune less

@dataclass
class PruneConfig:
    sparsity: float        # 0.0 – 1.0
    skip_groups: List[str] = field(default_factory=list)
    aggressive_groups: List[str] = field(default_factory=list)

@dataclass
class SparsityResult:
    sparsity_pct: int
    mae_delta_pct: float
    latency_delta_pct: float   # negative = faster
    size_gb: float
    size_delta_pct: float      # negative = smaller
    per_layer_sparsity: Dict[str, float]
    recommendation: str        # "optimal" | "acceptable" | "degraded"

@dataclass
class PrunerReport:
    checkpoint: str
    original_size_gb: float
    baseline_mae: float        # ~0.013 from session notes
    baseline_latency_ms: float # ~226ms from session notes
    sweep: List[SparsityResult]
    optimal_sparsity_pct: int
    optimal_size_gb: float
    quantized_size_gb: float   # additional INT8 on top of optimal
    quantized_latency_ms: float


# ---------------------------------------------------------------------------
# Layer catalog
# ---------------------------------------------------------------------------

# Impact multipliers: how much pruning a layer at full sparsity hurts MAE (relative)
_GROUP_SENSITIVITY_BASE = {
    "vision_encoder": 0.55,
    "transformer":    0.45,
    "action_head":    0.90,
    "lora_adapters":  0.70,
}

_GROUP_PARAM_COUNTS = {
    "vision_encoder": [28_000_000] * 12,
    "transformer":    [40_000_000] * 12,
    "action_head":    [8_000_000,  4_000_000],
    "lora_adapters":  [500_000]   * 8,
}

_GROUP_LAYER_COUNTS = {
    "vision_encoder": 12,
    "transformer":    12,
    "action_head":    2,
    "lora_adapters":  8,
}


def build_layer_catalog(seed: int) -> List[LayerInfo]:
    rng = random.Random(seed)
    layers: List[LayerInfo] = []

    for group, param_list in _GROUP_PARAM_COUNTS.items():
        base_sensitivity = _GROUP_SENSITIVITY_BASE[group]
        n = len(param_list)

        for idx, num_params in enumerate(param_list):
            # Vary sensitivity across layer indices
            # Early and late layers are generally more sensitive
            pos = idx / max(n - 1, 1)  # 0.0 at first, 1.0 at last
            sensitivity_curve = 1.0 - 4 * pos * (1 - pos)  # parabola, peaks at edges
            sensitivity = min(1.0, max(0.0,
                base_sensitivity * (0.7 + 0.6 * sensitivity_curve) + rng.gauss(0, 0.04)
            ))

            weight_mean = rng.gauss(0.0, 0.01)
            weight_std = rng.uniform(0.04, 0.15)
            # Near-zero percentage correlates inversely with std
            pct_near_zero = max(0.02, min(0.45, 0.25 - weight_std * 0.8 + rng.gauss(0, 0.03)))

            layers.append(LayerInfo(
                name=f"{group}.layer_{idx:02d}",
                group=group,
                layer_index=idx,
                num_params=num_params,
                weight_mean=weight_mean,
                weight_std=weight_std,
                pct_near_zero=pct_near_zero,
                sensitivity_score=round(sensitivity, 4),
            ))

    return layers


# ---------------------------------------------------------------------------
# Pruning strategy
# ---------------------------------------------------------------------------

# Ground-truth impact table (global, not per-layer)
_IMPACT_TABLE: Dict[int, Tuple[float, float, float]] = {
    # sparsity_pct: (mae_delta_pct, latency_delta_pct, size_delta_pct)
    10: (+2.0,  -8.0,  -8.0),
    20: (+5.0,  -15.0, -17.0),
    30: (+9.0,  -22.0, -26.0),
    40: (+18.0, -30.0, -34.0),
    50: (+35.0, -38.0, -43.0),
}

ORIGINAL_SIZE_GB = 2.9
ORIGINAL_LATENCY_MS = 226.0
BASELINE_MAE = 0.013
SKIP_GROUPS = ["lora_adapters"]
AGGRESSIVE_GROUPS = ["transformer"]  # mid-layers pruned more


def compute_per_layer_sparsity(
    layers: List[LayerInfo],
    global_sparsity: float,
    skip_groups: List[str],
    aggressive_groups: List[str],
    rng: random.Random,
) -> Dict[str, float]:
    """
    Distribute global target sparsity across layers using sensitivity scores.
    Skipped groups get 0. Aggressive groups (mid-layers) get boosted.
    """
    result: Dict[str, float] = {}

    eligible = [l for l in layers if l.group not in skip_groups]
    if not eligible:
        return {l.name: 0.0 for l in layers}

    # Compute raw allocation: inversely proportional to sensitivity
    raw: Dict[str, float] = {}
    for l in eligible:
        boost = 1.0
        if l.group in aggressive_groups:
            n = _GROUP_LAYER_COUNTS[l.group]
            pos = l.layer_index / max(n - 1, 1)
            # Mid-layers are pruned more
            mid_boost = 1.0 + 0.5 * (1 - abs(pos - 0.5) * 2)
            boost = mid_boost
        raw[l.name] = (1.0 - l.sensitivity_score) * boost

    total_raw = sum(raw.values())
    # Scale so that weighted average sparsity ≈ global_sparsity
    total_params_eligible = sum(l.num_params for l in eligible)
    total_params_all = sum(l.num_params for l in layers)
    coverage = total_params_eligible / total_params_all

    # Adjust target to account for skipped layers
    adjusted_target = global_sparsity / coverage if coverage > 0 else global_sparsity

    for l in eligible:
        s = (raw[l.name] / total_raw) * adjusted_target * len(eligible) * 0.5
        s = min(s * 2, 0.75)  # cap at 75%
        noise = rng.gauss(0, 0.01)
        result[l.name] = round(max(0.0, min(0.75, s + noise)), 4)

    for l in layers:
        if l.group in skip_groups:
            result[l.name] = 0.0

    return result


def simulate_sweep(layers: List[LayerInfo], seed: int) -> List[SparsityResult]:
    rng = random.Random(seed + 1)
    results: List[SparsityResult] = []

    for sparsity_pct, (mae_delta, latency_delta, size_delta) in sorted(_IMPACT_TABLE.items()):
        per_layer = compute_per_layer_sparsity(
            layers,
            global_sparsity=sparsity_pct / 100.0,
            skip_groups=SKIP_GROUPS,
            aggressive_groups=AGGRESSIVE_GROUPS,
            rng=rng,
        )

        size_gb = round(ORIGINAL_SIZE_GB * (1 + size_delta / 100.0), 2)

        if mae_delta <= 5.0:
            rec = "optimal"
        elif mae_delta <= 12.0:
            rec = "acceptable"
        else:
            rec = "degraded"

        results.append(SparsityResult(
            sparsity_pct=sparsity_pct,
            mae_delta_pct=mae_delta,
            latency_delta_pct=latency_delta,
            size_gb=size_gb,
            size_delta_pct=size_delta,
            per_layer_sparsity=per_layer,
            recommendation=rec,
        ))

    return results


def build_report(checkpoint: str, layers: List[LayerInfo], seed: int) -> PrunerReport:
    sweep = simulate_sweep(layers, seed)

    # Optimal: 20% sparsity
    optimal_sparsity_pct = 20
    optimal = next(r for r in sweep if r.sparsity_pct == optimal_sparsity_pct)

    # INT8 on top: additional 30% size reduction
    quantized_size_gb = round(optimal.size_gb * 0.70, 2)
    # Latency improvement: pruning saves + quantization INT8 kernel speedup ~15%
    pruned_latency_ms = ORIGINAL_LATENCY_MS * (1 + optimal.latency_delta_pct / 100.0)
    quantized_latency_ms = round(pruned_latency_ms * 0.85, 1)

    return PrunerReport(
        checkpoint=checkpoint,
        original_size_gb=ORIGINAL_SIZE_GB,
        baseline_mae=BASELINE_MAE,
        baseline_latency_ms=ORIGINAL_LATENCY_MS,
        sweep=sweep,
        optimal_sparsity_pct=optimal_sparsity_pct,
        optimal_size_gb=optimal.size_gb,
        quantized_size_gb=quantized_size_gb,
        quantized_latency_ms=quantized_latency_ms,
    )


# ---------------------------------------------------------------------------
# Console output
# ---------------------------------------------------------------------------

def print_sweep_table(report: PrunerReport) -> None:
    col = {
        "sparsity%": 10, "mae_delta%": 12, "latency%": 12,
        "size_gb": 10, "recommendation": 14,
    }
    header = (
        f"{'sparsity%':<{col['sparsity%']}}"
        f"{'mae_delta%':<{col['mae_delta%']}}"
        f"{'latency%':<{col['latency%']}}"
        f"{'size_gb':<{col['size_gb']}}"
        f"{'recommendation':<{col['recommendation']}}"
    )
    sep = "-" * sum(col.values())

    print()
    print("=" * sum(col.values()))
    print(f"  GR00T Checkpoint Pruning Sweep — {report.checkpoint}")
    print("=" * sum(col.values()))
    print(f"  Baseline: {report.original_size_gb}GB | {report.baseline_latency_ms}ms | MAE {report.baseline_mae:.3f}")
    print(sep)
    print(header)
    print(sep)

    for r in report.sweep:
        flag = " *" if r.sparsity_pct == report.optimal_sparsity_pct else "  "
        print(
            f"{r.sparsity_pct:<{col['sparsity%']}}"
            f"{r.mae_delta_pct:+.1f}%{'':<{col['mae_delta%']-7}}"
            f"{r.latency_delta_pct:+.1f}%{'':<{col['latency%']-7}}"
            f"{r.size_gb:<{col['size_gb']}.2f}"
            f"{r.recommendation:<{col['recommendation']}}"
            f"{flag}"
        )

    print(sep)
    print(f"  * Optimal: {report.optimal_sparsity_pct}% sparse")
    print(f"  INT8 quantized: {report.quantized_size_gb}GB, {report.quantized_latency_ms}ms")
    print()


# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------

def _svg_pareto_chart(sweep: List[SparsityResult], optimal_pct: int) -> str:
    """SVG scatter plot: x=size_gb, y=mae_delta_pct. Pareto frontier highlighted."""
    W, H = 480, 300
    pad_l, pad_r, pad_t, pad_b = 55, 20, 20, 45

    sizes = [r.size_gb for r in sweep]
    maes  = [r.mae_delta_pct for r in sweep]
    x_min, x_max = min(sizes) - 0.05, ORIGINAL_SIZE_GB + 0.1
    y_min, y_max = -2, max(maes) + 4

    def tx(v: float) -> float:
        return pad_l + (v - x_min) / (x_max - x_min) * (W - pad_l - pad_r)

    def ty(v: float) -> float:
        return H - pad_b - (v - y_min) / (y_max - y_min) * (H - pad_t - pad_b)

    # Pareto frontier: sort by size asc, keep points where mae is non-increasing
    sorted_by_size = sorted(sweep, key=lambda r: r.size_gb)
    pareto: List[SparsityResult] = []
    min_mae = float("inf")
    for r in sorted_by_size:
        if r.mae_delta_pct <= min_mae:
            pareto.append(r)
            min_mae = r.mae_delta_pct

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'style="background:#1e1e2e;border-radius:8px;">',
        # Axes
        f'<line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{H-pad_b}" stroke="#555" stroke-width="1"/>',
        f'<line x1="{pad_l}" y1="{H-pad_b}" x2="{W-pad_r}" y2="{H-pad_b}" stroke="#555" stroke-width="1"/>',
        # Axis labels
        f'<text x="{W//2}" y="{H-8}" fill="#aaa" font-size="11" text-anchor="middle">Size (GB)</text>',
        f'<text x="12" y="{H//2}" fill="#aaa" font-size="11" text-anchor="middle" '
        f'transform="rotate(-90,12,{H//2})">MAE Delta (%)</text>',
        # Title
        f'<text x="{W//2}" y="14" fill="#cdd6f4" font-size="12" text-anchor="middle" font-weight="bold">'
        f'Size vs MAE Pareto Chart</text>',
    ]

    # Y grid lines
    for y_val in range(0, int(y_max) + 1, 10):
        yp = ty(y_val)
        lines.append(
            f'<line x1="{pad_l}" y1="{yp:.1f}" x2="{W-pad_r}" y2="{yp:.1f}" '
            f'stroke="#333" stroke-width="1" stroke-dasharray="3,3"/>'
            f'<text x="{pad_l-6}" y="{yp+4:.1f}" fill="#777" font-size="9" text-anchor="end">{y_val}</text>'
        )

    # X tick labels
    for x_val in [2.0, 2.2, 2.4, 2.6, 2.8]:
        xp = tx(x_val)
        lines.append(
            f'<text x="{xp:.1f}" y="{H-pad_b+14}" fill="#777" font-size="9" text-anchor="middle">{x_val:.1f}</text>'
        )

    # Pareto frontier line
    if len(pareto) >= 2:
        pts = " ".join(f"{tx(r.size_gb):.1f},{ty(r.mae_delta_pct):.1f}" for r in pareto)
        lines.append(
            f'<polyline points="{pts}" fill="none" stroke="#f38ba8" stroke-width="1.5" stroke-dasharray="4,3"/>'
        )

    # Baseline dot
    bx, by = tx(ORIGINAL_SIZE_GB), ty(0.0)
    lines.append(
        f'<circle cx="{bx:.1f}" cy="{by:.1f}" r="6" fill="#585b70" stroke="#a6e3a1" stroke-width="1.5"/>'
        f'<text x="{bx+8:.1f}" y="{by-6:.1f}" fill="#a6e3a1" font-size="9">baseline</text>'
    )

    # Sparsity dots
    colors = {10: "#89b4fa", 20: "#a6e3a1", 30: "#fab387", 40: "#f9e2af", 50: "#f38ba8"}
    for r in sweep:
        cx, cy = tx(r.size_gb), ty(r.mae_delta_pct)
        is_optimal = (r.sparsity_pct == optimal_pct)
        c = colors.get(r.sparsity_pct, "#cdd6f4")
        r_size = 8 if is_optimal else 5
        stroke = "#fff" if is_optimal else "none"
        lines.append(
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r_size}" fill="{c}" stroke="{stroke}" stroke-width="1.5"/>'
            f'<text x="{cx+10:.1f}" y="{cy+4:.1f}" fill="{c}" font-size="9">{r.sparsity_pct}%</text>'
        )

    # Legend
    legend_x = W - pad_r - 80
    lines.append(
        f'<text x="{legend_x}" y="{pad_t+12}" fill="#f38ba8" font-size="9">-- Pareto frontier</text>'
    )

    lines.append("</svg>")
    return "\n".join(lines)


def _svg_layer_bar_chart(per_layer: Dict[str, float]) -> str:
    """Horizontal bar chart showing per-layer sparsity at recommended 20%."""
    items = sorted(per_layer.items(), key=lambda kv: -kv[1])
    n = len(items)
    bar_h = 14
    gap = 3
    pad_l, pad_r, pad_t, pad_b = 155, 60, 30, 20
    W = 520
    H = pad_t + n * (bar_h + gap) + pad_b

    x_max = 0.30  # display up to 30% for readability

    def bw(v: float) -> float:
        return (W - pad_l - pad_r) * min(v, x_max) / x_max

    group_colors = {
        "vision_encoder": "#89b4fa",
        "transformer":    "#a6e3a1",
        "action_head":    "#fab387",
        "lora_adapters":  "#585b70",
    }

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'style="background:#1e1e2e;border-radius:8px;">',
        f'<text x="{W//2}" y="18" fill="#cdd6f4" font-size="12" text-anchor="middle" font-weight="bold">'
        f'Per-Layer Sparsity Applied (20% Global)</text>',
    ]

    # X axis
    lines.append(
        f'<line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{H-pad_b}" stroke="#555" stroke-width="1"/>'
    )
    for v in [0.0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30]:
        xp = pad_l + bw(v)
        lines.append(
            f'<line x1="{xp:.1f}" y1="{pad_t}" x2="{xp:.1f}" y2="{H-pad_b}" '
            f'stroke="#333" stroke-width="1" stroke-dasharray="3,3"/>'
            f'<text x="{xp:.1f}" y="{H-pad_b+12}" fill="#777" font-size="8" text-anchor="middle">'
            f'{int(v*100)}%</text>'
        )

    for i, (name, sparsity) in enumerate(items):
        y = pad_t + i * (bar_h + gap)
        group = name.split(".")[0]
        color = group_colors.get(group, "#cdd6f4")
        w = bw(sparsity)

        lines.append(
            f'<text x="{pad_l-4}" y="{y+bar_h-3}" fill="#aaa" font-size="8" text-anchor="end">'
            f'{name}</text>'
            f'<rect x="{pad_l}" y="{y}" width="{w:.1f}" height="{bar_h}" fill="{color}" opacity="0.85" rx="2"/>'
            f'<text x="{pad_l+w+4:.1f}" y="{y+bar_h-3}" fill="{color}" font-size="8">'
            f'{sparsity*100:.1f}%</text>'
        )

    # Legend
    lx = W - pad_r - 10
    ly_start = pad_t
    for gi, (grp, col) in enumerate(group_colors.items()):
        ly = ly_start + gi * 16
        lines.append(
            f'<rect x="{lx-55}" y="{ly}" width="10" height="10" fill="{col}" rx="2"/>'
            f'<text x="{lx-42}" y="{ly+9}" fill="{col}" font-size="8">{grp}</text>'
        )

    lines.append("</svg>")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# HTML report
# ---------------------------------------------------------------------------

def _rec_color(rec: str) -> str:
    return {"optimal": "#a6e3a1", "acceptable": "#f9e2af", "degraded": "#f38ba8"}.get(rec, "#cdd6f4")


def render_html(report: PrunerReport, layers: List[LayerInfo]) -> str:
    optimal = next(r for r in report.sweep if r.sparsity_pct == report.optimal_sparsity_pct)
    pareto_svg = _svg_pareto_chart(report.sweep, report.optimal_sparsity_pct)
    bar_svg = _svg_layer_bar_chart(optimal.per_layer_sparsity)

    # Summary cards
    speedup = round(
        (report.baseline_latency_ms - report.quantized_latency_ms) / report.baseline_latency_ms * 100, 1
    )

    cards_html = f"""
    <div class="cards">
      <div class="card">
        <div class="card-label">Original Size</div>
        <div class="card-value">{report.original_size_gb} GB</div>
        <div class="card-sub">GR00T N1.6 base</div>
      </div>
      <div class="card">
        <div class="card-label">Optimal Pruned (20%)</div>
        <div class="card-value">{report.optimal_size_gb} GB</div>
        <div class="card-sub">sparse only</div>
      </div>
      <div class="card">
        <div class="card-label">Pruned + INT8</div>
        <div class="card-value">{report.quantized_size_gb} GB</div>
        <div class="card-sub">additional 30% reduction</div>
      </div>
      <div class="card">
        <div class="card-label">Latency Improvement</div>
        <div class="card-value">{speedup}%</div>
        <div class="card-sub">{report.baseline_latency_ms:.0f}ms → {report.quantized_latency_ms:.0f}ms</div>
      </div>
      <div class="card">
        <div class="card-label">MAE Impact</div>
        <div class="card-value">+{optimal.mae_delta_pct:.0f}%</div>
        <div class="card-sub">at 20% sparsity</div>
      </div>
    </div>
    """

    # Sweep table rows
    table_rows = ""
    for r in report.sweep:
        color = _rec_color(r.recommendation)
        is_opt = r.sparsity_pct == report.optimal_sparsity_pct
        row_style = 'style="background:#2a2a3e;"' if is_opt else ""
        star = " ★" if is_opt else ""
        table_rows += f"""
        <tr {row_style}>
          <td>{r.sparsity_pct}%{star}</td>
          <td style="color:#89b4fa;">{r.mae_delta_pct:+.1f}%</td>
          <td style="color:#a6e3a1;">{r.latency_delta_pct:+.1f}%</td>
          <td>{r.size_gb:.2f} GB</td>
          <td style="color:{color};">{r.recommendation}</td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>GR00T Checkpoint Pruner — {report.checkpoint}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: #11111b;
    color: #cdd6f4;
    font-family: 'Segoe UI', system-ui, sans-serif;
    font-size: 14px;
    padding: 24px;
  }}
  h1 {{ font-size: 22px; color: #cba6f7; margin-bottom: 4px; }}
  h2 {{ font-size: 16px; color: #89b4fa; margin: 24px 0 10px; }}
  .subtitle {{ color: #6c7086; font-size: 12px; margin-bottom: 20px; }}
  .cards {{
    display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 24px;
  }}
  .card {{
    background: #1e1e2e; border: 1px solid #313244; border-radius: 8px;
    padding: 14px 18px; min-width: 150px;
  }}
  .card-label {{ color: #6c7086; font-size: 11px; text-transform: uppercase; letter-spacing: .5px; }}
  .card-value {{ color: #cba6f7; font-size: 26px; font-weight: 700; margin: 4px 0; }}
  .card-sub {{ color: #585b70; font-size: 11px; }}
  table {{
    width: 100%; border-collapse: collapse; margin-top: 8px;
    background: #1e1e2e; border-radius: 8px; overflow: hidden;
  }}
  th {{
    background: #181825; color: #89b4fa; font-size: 12px;
    text-transform: uppercase; letter-spacing: .5px;
    padding: 10px 14px; text-align: left;
  }}
  td {{ padding: 9px 14px; border-bottom: 1px solid #313244; }}
  tr:last-child td {{ border-bottom: none; }}
  tr:hover td {{ background: #252535; }}
  .rec-box {{
    background: #1e1e2e; border: 2px solid #a6e3a1;
    border-radius: 8px; padding: 16px 20px; margin-top: 24px;
  }}
  .rec-box h3 {{ color: #a6e3a1; font-size: 14px; margin-bottom: 6px; }}
  .rec-box .rec-text {{ color: #cdd6f4; font-size: 15px; font-weight: 600; }}
  .rec-box .rec-detail {{ color: #6c7086; font-size: 12px; margin-top: 6px; }}
  .charts {{ display: flex; flex-wrap: wrap; gap: 16px; margin-top: 8px; }}
  .chart-wrap {{ overflow-x: auto; }}
  footer {{ color: #313244; font-size: 11px; margin-top: 32px; text-align: center; }}
</style>
</head>
<body>
<h1>GR00T Checkpoint Pruner</h1>
<div class="subtitle">Checkpoint: {report.checkpoint} &nbsp;|&nbsp;
  Baseline: {report.original_size_gb}GB &nbsp;|&nbsp;
  Latency: {report.baseline_latency_ms:.0f}ms &nbsp;|&nbsp;
  MAE: {report.baseline_mae:.3f}
</div>

{cards_html}

<h2>Sparsity Sweep</h2>
<table>
  <thead>
    <tr>
      <th>Sparsity</th>
      <th>MAE Delta</th>
      <th>Latency Delta</th>
      <th>Size</th>
      <th>Recommendation</th>
    </tr>
  </thead>
  <tbody>{table_rows}</tbody>
</table>

<h2>Charts</h2>
<div class="charts">
  <div class="chart-wrap">{pareto_svg}</div>
  <div class="chart-wrap">{bar_svg}</div>
</div>

<div class="rec-box">
  <h3>Recommendation</h3>
  <div class="rec-text">
    Deploy 20% sparse + INT8 &rarr; {report.quantized_size_gb}GB,
    {report.baseline_latency_ms:.0f}ms &rarr; {report.quantized_latency_ms:.0f}ms,
    MAE +{optimal.mae_delta_pct:.0f}%
  </div>
  <div class="rec-detail">
    Skip LoRA adapters (preserve fine-tune quality). Prune transformer mid-layers
    most aggressively (lower sensitivity). Apply INT8 quantization post-prune
    for additional 30% size reduction. Total pipeline: sparse mask &rarr; INT8 PTQ
    &rarr; TensorRT export.
  </div>
</div>

<footer>Generated by checkpoint_pruner.py &mdash; OCI Robot Cloud</footer>
</body>
</html>"""
    return html


# ---------------------------------------------------------------------------
# JSON serialization
# ---------------------------------------------------------------------------

def report_to_json(report: PrunerReport) -> dict:
    return {
        "checkpoint": report.checkpoint,
        "original_size_gb": report.original_size_gb,
        "baseline_mae": report.baseline_mae,
        "baseline_latency_ms": report.baseline_latency_ms,
        "optimal_sparsity_pct": report.optimal_sparsity_pct,
        "optimal_size_gb": report.optimal_size_gb,
        "quantized_size_gb": report.quantized_size_gb,
        "quantized_latency_ms": report.quantized_latency_ms,
        "recommendation": (
            f"Deploy {report.optimal_sparsity_pct}% sparse + INT8 → "
            f"{report.quantized_size_gb}GB, "
            f"{report.baseline_latency_ms:.0f}ms→{report.quantized_latency_ms:.0f}ms, "
            f"MAE +5%"
        ),
        "sweep": [
            {
                "sparsity_pct": r.sparsity_pct,
                "mae_delta_pct": r.mae_delta_pct,
                "latency_delta_pct": r.latency_delta_pct,
                "size_gb": r.size_gb,
                "size_delta_pct": r.size_delta_pct,
                "recommendation": r.recommendation,
                "per_layer_sparsity": r.per_layer_sparsity,
            }
            for r in report.sweep
        ],
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="GR00T checkpoint pruning analyzer — simulate structured sparsity sweep."
    )
    p.add_argument("--mock", action="store_true", default=True,
                   help="Use mock/simulated data (default: True)")
    p.add_argument("--no-mock", dest="mock", action="store_false",
                   help="Attempt real checkpoint loading (not yet implemented)")
    p.add_argument("--checkpoint", default="dagger_run9/checkpoint_5000",
                   help="Checkpoint identifier string (default: dagger_run9/checkpoint_5000)")
    p.add_argument("--output", default="/tmp/checkpoint_pruner.html",
                   help="HTML report output path (default: /tmp/checkpoint_pruner.html)")
    p.add_argument("--seed", type=int, default=42,
                   help="Random seed for reproducibility (default: 42)")
    return p.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)

    if not args.mock:
        print("WARNING: Real checkpoint loading not implemented. Falling back to mock mode.")

    print(f"[checkpoint_pruner] checkpoint={args.checkpoint}  seed={args.seed}  mock=True")
    print("[checkpoint_pruner] Building layer catalog...")

    layers = build_layer_catalog(seed=args.seed)
    total_params = sum(l.num_params for l in layers)
    print(f"[checkpoint_pruner] {len(layers)} layers, {total_params/1e9:.2f}B parameters")

    print("[checkpoint_pruner] Running sparsity sweep (10%–50%)...")
    report = build_report(args.checkpoint, layers, seed=args.seed)

    # Console table
    print_sweep_table(report)

    # HTML
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    html = render_html(report, layers)
    output_path.write_text(html, encoding="utf-8")
    print(f"[checkpoint_pruner] HTML report written → {output_path}")

    # JSON (same stem, .json extension)
    json_path = output_path.with_suffix(".json")
    json_path.write_text(json.dumps(report_to_json(report), indent=2), encoding="utf-8")
    print(f"[checkpoint_pruner] JSON results written → {json_path}")

    print()
    print(
        f"[checkpoint_pruner] RECOMMENDATION: Deploy {report.optimal_sparsity_pct}% sparse + INT8 → "
        f"{report.quantized_size_gb}GB, "
        f"{report.baseline_latency_ms:.0f}ms → {report.quantized_latency_ms:.0f}ms, MAE +5%"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
