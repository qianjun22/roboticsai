#!/usr/bin/env python3
"""
multi_gpu_profiler.py — GR00T Fine-Tuning Multi-GPU Bottleneck Profiler

Profiles multi-GPU training runs across 1/2/4/8×A100 configurations.
Identifies bottlenecks in: data loading, forward pass, backward pass,
gradient sync (AllReduce), and optimizer step.

Usage:
    python multi_gpu_profiler.py [--mock] [--output PATH] [--seed INT]
"""

import argparse
import json
import math
import random
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Dict, Optional


# ---------------------------------------------------------------------------
# Data Structures
# ---------------------------------------------------------------------------

@dataclass
class StepTimingMs:
    """Per-step timing breakdown in milliseconds."""
    data_load: float
    forward_pass: float
    backward_pass: float
    grad_sync: float
    optimizer_step: float

    @property
    def total_step(self) -> float:
        return (self.data_load + self.forward_pass + self.backward_pass
                + self.grad_sync + self.optimizer_step)


@dataclass
class GpuMetrics:
    """Per-device utilization and memory stats."""
    device_id: int
    utilization_pct: float   # 0–100
    memory_used_gb: float
    memory_total_gb: float   # 80 GB for A100-80G


@dataclass
class ConfigProfile:
    """Full profiling result for one GPU configuration."""
    gpu_count: int
    steps_per_sec: float
    scaling_efficiency_pct: float          # vs ideal linear from 1-GPU baseline
    compute_comm_ratio: float              # (forward+backward) / grad_sync
    timing: StepTimingMs
    gpu_metrics: List[GpuMetrics]
    bottleneck_phases: List[str]           # phases exceeding 30% of total
    step_samples: List[Dict]              # raw sample data (list of dicts)


# ---------------------------------------------------------------------------
# Simulation
# ---------------------------------------------------------------------------

# Ground-truth throughput numbers from prior benchmark runs (session5/session6)
_THROUGHPUT = {
    1: 2.35,
    2: 4.41,
    4: 7.85,
    8: 12.70,
}

_IDEAL_THROUGHPUT = {n: 2.35 * n for n in [1, 2, 4, 8]}

# Empirical mean timings (ms) per phase for each GPU count.
# Data loading doesn't shrink with more GPUs (DDP bottleneck).
# grad_sync grows super-linearly beyond 4 GPUs (PCIe topology).
_MEAN_TIMINGS = {
    #           data   fwd    bwd    gsync  opt
    1:  StepTimingMs(38.0,  82.0, 148.0,  0.0,  8.0),
    2:  StepTimingMs(42.0,  80.0, 145.0, 18.5,  8.0),
    4:  StepTimingMs(45.0,  79.0, 143.0, 32.0,  8.0),
    8:  StepTimingMs(52.0,  78.0, 141.0, 68.0,  8.0),
}

# Per-device utilisation (%) for each configuration
_UTILIZATION = {
    1: [87.0],
    2: [86.0, 85.0],
    4: [85.0, 84.0, 83.0, 84.0],
    8: [82.0, 81.0, 80.0, 81.0, 79.0, 80.0, 82.0, 81.0],
}

# Per-device memory used (GB) — A100-80G
_MEMORY_GB = {
    1: [46.2],
    2: [44.8, 44.6],
    4: [44.1, 43.9, 44.0, 43.8],
    8: [43.5, 43.4, 43.3, 43.6, 43.2, 43.5, 43.4, 43.3],
}

_BOTTLENECK_THRESHOLD_PCT = 30.0
_N_SAMPLES = 50  # simulated steps per config


def simulate_config(gpu_count: int, rng: random.Random) -> ConfigProfile:
    """Simulate profiling data for a single GPU count configuration."""
    mean = _MEAN_TIMINGS[gpu_count]

    # Generate per-step samples with light Gaussian noise
    samples: List[Dict] = []
    for _ in range(_N_SAMPLES):
        s = {
            "data_load":     max(1.0, rng.gauss(mean.data_load,    mean.data_load    * 0.05)),
            "forward_pass":  max(1.0, rng.gauss(mean.forward_pass,  mean.forward_pass * 0.04)),
            "backward_pass": max(1.0, rng.gauss(mean.backward_pass, mean.backward_pass * 0.04)),
            "grad_sync":     max(0.0, rng.gauss(mean.grad_sync,     max(1.0, mean.grad_sync * 0.08))),
            "optimizer_step":max(1.0, rng.gauss(mean.optimizer_step,mean.optimizer_step * 0.03)),
        }
        s["total_step"] = sum(s.values())
        samples.append(s)

    # Average timing
    avg = StepTimingMs(
        data_load=sum(s["data_load"]     for s in samples) / _N_SAMPLES,
        forward_pass=sum(s["forward_pass"]  for s in samples) / _N_SAMPLES,
        backward_pass=sum(s["backward_pass"] for s in samples) / _N_SAMPLES,
        grad_sync=sum(s["grad_sync"]     for s in samples) / _N_SAMPLES,
        optimizer_step=sum(s["optimizer_step"] for s in samples) / _N_SAMPLES,
    )

    steps_per_sec = _THROUGHPUT[gpu_count]
    ideal = _IDEAL_THROUGHPUT[gpu_count]
    scaling_eff = (steps_per_sec / ideal) * 100.0

    compute = avg.forward_pass + avg.backward_pass
    comm = avg.grad_sync if avg.grad_sync > 0 else 0.001
    cc_ratio = compute / comm

    # GPU metrics
    gpu_metrics = [
        GpuMetrics(
            device_id=i,
            utilization_pct=_UTILIZATION[gpu_count][i] + rng.gauss(0, 0.5),
            memory_used_gb=_MEMORY_GB[gpu_count][i]   + rng.gauss(0, 0.1),
            memory_total_gb=80.0,
        )
        for i in range(gpu_count)
    ]

    # Bottleneck detection
    total = avg.total_step
    phase_map = {
        "data_load":     avg.data_load,
        "forward_pass":  avg.forward_pass,
        "backward_pass": avg.backward_pass,
        "grad_sync":     avg.grad_sync,
        "optimizer_step":avg.optimizer_step,
    }
    bottlenecks = [
        phase for phase, t in phase_map.items()
        if (t / total * 100.0) > _BOTTLENECK_THRESHOLD_PCT
    ]

    return ConfigProfile(
        gpu_count=gpu_count,
        steps_per_sec=steps_per_sec,
        scaling_efficiency_pct=scaling_eff,
        compute_comm_ratio=cc_ratio,
        timing=avg,
        gpu_metrics=gpu_metrics,
        bottleneck_phases=bottlenecks,
        step_samples=samples,
    )


def simulate_all(seed: int = 42) -> List[ConfigProfile]:
    rng = random.Random(seed)
    return [simulate_config(n, rng) for n in [1, 2, 4, 8]]


# ---------------------------------------------------------------------------
# Console Output
# ---------------------------------------------------------------------------

def _bar(val: float, max_val: float, width: int = 20) -> str:
    filled = int(round(val / max_val * width))
    return "█" * filled + "░" * (width - filled)


def print_table(profiles: List[ConfigProfile]) -> None:
    SEP = "─" * 100
    HEADER = (
        f"{'GPUs':>6}  {'it/s':>7}  {'ScaleEff%':>9}  "
        f"{'CC-Ratio':>8}  {'DataLD ms':>9}  {'Fwd ms':>6}  "
        f"{'Bwd ms':>6}  {'GSync ms':>8}  {'Opt ms':>6}  {'Total ms':>8}  Bottlenecks"
    )

    print()
    print("  GR00T Multi-GPU Training Profiler — Bottleneck Analysis")
    print(SEP)
    print(HEADER)
    print(SEP)

    for p in profiles:
        t = p.timing
        bn = ", ".join(p.bottleneck_phases) if p.bottleneck_phases else "none"
        row = (
            f"{p.gpu_count:>6}  "
            f"{p.steps_per_sec:>7.2f}  "
            f"{p.scaling_efficiency_pct:>9.1f}  "
            f"{p.compute_comm_ratio:>8.1f}  "
            f"{t.data_load:>9.1f}  "
            f"{t.forward_pass:>6.1f}  "
            f"{t.backward_pass:>6.1f}  "
            f"{t.grad_sync:>8.1f}  "
            f"{t.optimizer_step:>6.1f}  "
            f"{t.total_step:>8.1f}  "
            f"{bn}"
        )
        print(row)

    print(SEP)

    print("\n  Throughput scaling bars (baseline: 1×A100 = 2.35 it/s):")
    max_tp = max(p.steps_per_sec for p in profiles)
    for p in profiles:
        bar = _bar(p.steps_per_sec, max_tp)
        print(f"  {p.gpu_count:>2}×A100  {bar}  {p.steps_per_sec:.2f} it/s")

    print()


# ---------------------------------------------------------------------------
# HTML Report
# ---------------------------------------------------------------------------

_PHASES = ["data_load", "forward_pass", "backward_pass", "grad_sync", "optimizer_step"]
_PHASE_LABELS = ["Data Load", "Forward", "Backward", "Grad Sync", "Optimizer"]
_PHASE_COLORS = ["#38bdf8", "#4ade80", "#a78bfa", "#f87171", "#fbbf24"]

# Oracle red + dark theme palette
_BG = "#1e293b"
_CARD_BG = "#0f172a"
_TEXT = "#f1f5f9"
_MUTED = "#94a3b8"
_ORACLE_RED = "#C74634"
_BORDER = "#334155"


def _phase_val(timing: StepTimingMs, phase: str) -> float:
    return getattr(timing, phase)


def _svg_stacked_bar(profiles: List[ConfigProfile]) -> str:
    """SVG stacked bar chart: step time breakdown by phase for each GPU count."""
    W, H = 680, 300
    margin = {"top": 30, "right": 20, "bottom": 50, "left": 65}
    chart_w = W - margin["left"] - margin["right"]
    chart_h = H - margin["top"] - margin["bottom"]

    max_total = max(p.timing.total_step for p in profiles)
    y_max = math.ceil(max_total / 50) * 50   # round up to nearest 50 ms

    bar_width = chart_w / len(profiles) * 0.55
    bar_gap   = chart_w / len(profiles)

    bars_svg = []
    for idx, p in enumerate(profiles):
        x_center = margin["left"] + idx * bar_gap + bar_gap * 0.5
        x_bar = x_center - bar_width / 2
        y_cursor = 0.0
        for phase, color in zip(_PHASES, _PHASE_COLORS):
            val = _phase_val(p.timing, phase)
            bar_h = (val / y_max) * chart_h
            y_pos = margin["top"] + chart_h - (y_cursor + val) / y_max * chart_h
            bars_svg.append(
                f'<rect x="{x_bar:.1f}" y="{y_pos:.1f}" '
                f'width="{bar_width:.1f}" height="{bar_h:.1f}" '
                f'fill="{color}" opacity="0.9">'
                f'<title>{phase}: {val:.1f} ms</title></rect>'
            )
            y_cursor += val
        # x-axis label
        bars_svg.append(
            f'<text x="{x_center:.1f}" y="{margin["top"] + chart_h + 20}" '
            f'fill="{_TEXT}" font-size="13" text-anchor="middle">{p.gpu_count}×A100</text>'
        )
        # total label on top
        total = p.timing.total_step
        ty = margin["top"] + chart_h - total / y_max * chart_h - 6
        bars_svg.append(
            f'<text x="{x_center:.1f}" y="{ty:.1f}" '
            f'fill="{_MUTED}" font-size="11" text-anchor="middle">{total:.0f}ms</text>'
        )

    # Y-axis ticks
    y_ticks_svg = []
    n_ticks = 5
    for i in range(n_ticks + 1):
        val = y_max * i / n_ticks
        y_pos = margin["top"] + chart_h - (val / y_max) * chart_h
        y_ticks_svg.append(
            f'<line x1="{margin["left"]}" y1="{y_pos:.1f}" '
            f'x2="{margin["left"] + chart_w}" y2="{y_pos:.1f}" '
            f'stroke="{_BORDER}" stroke-width="1" stroke-dasharray="4,4"/>'
        )
        y_ticks_svg.append(
            f'<text x="{margin["left"] - 8}" y="{y_pos + 4:.1f}" '
            f'fill="{_MUTED}" font-size="11" text-anchor="end">{val:.0f}</text>'
        )

    # Legend
    legend_svg = []
    lx = margin["left"]
    ly = H - 10
    for i, (label, color) in enumerate(zip(_PHASE_LABELS, _PHASE_COLORS)):
        legend_svg.append(
            f'<rect x="{lx + i*125}" y="{ly - 12}" width="12" height="12" fill="{color}"/>'
        )
        legend_svg.append(
            f'<text x="{lx + i*125 + 16}" y="{ly}" fill="{_MUTED}" font-size="11">{label}</text>'
        )

    # Y-axis title
    y_title = (
        f'<text transform="rotate(-90)" x="{-(margin["top"] + chart_h/2):.0f}" '
        f'y="14" fill="{_MUTED}" font-size="12" text-anchor="middle">Time (ms)</text>'
    )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'style="background:{_CARD_BG};border-radius:8px;">'
        + y_title
        + "\n".join(y_ticks_svg)
        + "\n".join(bars_svg)
        + "\n".join(legend_svg)
        + "</svg>"
    )


def _svg_scaling_line(profiles: List[ConfigProfile]) -> str:
    """SVG line chart: actual vs ideal throughput scaling."""
    W, H = 560, 280
    margin = {"top": 30, "right": 30, "bottom": 50, "left": 65}
    chart_w = W - margin["left"] - margin["right"]
    chart_h = H - margin["top"] - margin["bottom"]

    gpu_counts = [p.gpu_count for p in profiles]
    max_x = 8
    max_y = math.ceil(_IDEAL_THROUGHPUT[8] / 5) * 5  # 20

    def px(n):
        return margin["left"] + math.log2(n) / math.log2(max_x) * chart_w

    def py(v):
        return margin["top"] + chart_h - (v / max_y) * chart_h

    # Gridlines
    grid = []
    for v in range(0, int(max_y) + 1, 5):
        y = py(v)
        grid.append(
            f'<line x1="{margin["left"]}" y1="{y:.1f}" '
            f'x2="{margin["left"]+chart_w}" y2="{y:.1f}" '
            f'stroke="{_BORDER}" stroke-width="1" stroke-dasharray="4,4"/>'
        )
        grid.append(
            f'<text x="{margin["left"]-8}" y="{y+4:.1f}" '
            f'fill="{_MUTED}" font-size="11" text-anchor="end">{v}</text>'
        )

    # Ideal line (dashed white)
    ideal_pts = [(px(n), py(_IDEAL_THROUGHPUT[n])) for n in gpu_counts]
    ideal_path = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in ideal_pts)

    # Actual line (Oracle red)
    actual_pts = [(px(p.gpu_count), py(p.steps_per_sec)) for p in profiles]
    actual_path = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in actual_pts)

    # Dots + labels
    dots = []
    for p, (ax, ay) in zip(profiles, actual_pts):
        dots.append(f'<circle cx="{ax:.1f}" cy="{ay:.1f}" r="5" fill="{_ORACLE_RED}"/>')
        dots.append(
            f'<text x="{ax:.1f}" y="{ay - 10:.1f}" fill="{_TEXT}" font-size="11" '
            f'text-anchor="middle">{p.steps_per_sec:.2f}</text>'
        )

    # X-axis labels
    x_labels = []
    for n in gpu_counts:
        x_labels.append(
            f'<text x="{px(n):.1f}" y="{margin["top"]+chart_h+20}" '
            f'fill="{_TEXT}" font-size="12" text-anchor="middle">{n}×A100</text>'
        )

    # Legend
    legend = (
        f'<rect x="{margin["left"]}" y="{H-12}" width="12" height="3" fill="white" opacity="0.4"/>'
        f'<text x="{margin["left"]+16}" y="{H-4}" fill="{_MUTED}" font-size="11">Ideal Linear</text>'
        f'<rect x="{margin["left"]+120}" y="{H-14}" width="12" height="12" rx="6" fill="{_ORACLE_RED}"/>'
        f'<text x="{margin["left"]+136}" y="{H-4}" fill="{_MUTED}" font-size="11">Actual</text>'
    )

    # Y-axis title
    y_title = (
        f'<text transform="rotate(-90)" x="{-(margin["top"]+chart_h/2):.0f}" '
        f'y="14" fill="{_MUTED}" font-size="12" text-anchor="middle">Throughput (it/s)</text>'
    )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'style="background:{_CARD_BG};border-radius:8px;">'
        + y_title
        + "\n".join(grid)
        + f'<path d="{ideal_path}" stroke="white" stroke-width="2" stroke-dasharray="6,4" '
          f'fill="none" opacity="0.35"/>'
        + f'<path d="{actual_path}" stroke="{_ORACLE_RED}" stroke-width="2.5" fill="none"/>'
        + "\n".join(dots)
        + "\n".join(x_labels)
        + legend
        + "</svg>"
    )


def _svg_utilization_heatmap(profiles: List[ConfigProfile]) -> str:
    """SVG heatmap: GPU utilization per device per config (up to 4×4 shown as coloured cells)."""
    W, H = 480, 260
    margin = {"top": 40, "right": 20, "bottom": 50, "left": 80}
    chart_w = W - margin["left"] - margin["right"]
    chart_h = H - margin["top"] - margin["bottom"]

    n_configs = 4   # 1/2/4/8 GPU
    n_devices = 4   # show first 4 device slots (blank if config has fewer)

    cell_w = chart_w / n_configs
    cell_h = chart_h / n_devices

    def util_color(u: Optional[float]) -> str:
        if u is None:
            return _BORDER
        # Map 70–100% → blue→green
        t = max(0.0, min(1.0, (u - 70) / 30))
        r = int(56  + t * (74  - 56))
        g = int(189 + t * (222 - 189))
        b = int(248 + t * (128 - 248))
        return f"rgb({r},{g},{b})"

    cells = []
    for ci, p in enumerate(profiles):
        utils = [m.utilization_pct for m in p.gpu_metrics]
        for di in range(n_devices):
            u = utils[di] if di < len(utils) else None
            x = margin["left"] + ci * cell_w + 2
            y = margin["top"] + di * cell_h + 2
            w = cell_w - 4
            h = cell_h - 4
            color = util_color(u)
            title_txt = f"GPU {di}, {p.gpu_count}×A100: {u:.1f}%" if u is not None else f"GPU {di}, {p.gpu_count}×A100: N/A"
            cells.append(
                f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" '
                f'rx="4" fill="{color}">'
                f'<title>{title_txt}</title></rect>'
            )
            if u is not None:
                cells.append(
                    f'<text x="{x+w/2:.1f}" y="{y+h/2+5:.1f}" '
                    f'fill="{_BG}" font-size="12" text-anchor="middle" font-weight="bold">'
                    f'{u:.0f}%</text>'
                )

    # Column headers
    col_headers = []
    for ci, p in enumerate(profiles):
        cx = margin["left"] + ci * cell_w + cell_w / 2
        col_headers.append(
            f'<text x="{cx:.1f}" y="{margin["top"]-10}" '
            f'fill="{_TEXT}" font-size="12" text-anchor="middle">{p.gpu_count}×A100</text>'
        )

    # Row labels
    row_labels = []
    for di in range(n_devices):
        ry = margin["top"] + di * cell_h + cell_h / 2 + 5
        row_labels.append(
            f'<text x="{margin["left"]-10}" y="{ry:.1f}" '
            f'fill="{_MUTED}" font-size="11" text-anchor="end">GPU {di}</text>'
        )

    # Gradient legend
    lx = margin["left"]
    ly = H - 20
    legend = (
        f'<defs><linearGradient id="utilGrad" x1="0" x2="1" y1="0" y2="0">'
        f'<stop offset="0%" stop-color="rgb(56,189,248)"/>'
        f'<stop offset="100%" stop-color="rgb(74,222,128)"/>'
        f'</linearGradient></defs>'
        f'<rect x="{lx}" y="{ly-10}" width="120" height="10" rx="3" fill="url(#utilGrad)"/>'
        f'<text x="{lx}" y="{ly+8}" fill="{_MUTED}" font-size="10">70%</text>'
        f'<text x="{lx+120}" y="{ly+8}" fill="{_MUTED}" font-size="10" text-anchor="end">100%</text>'
        f'<text x="{lx+60}" y="{ly+8}" fill="{_MUTED}" font-size="10" text-anchor="middle">GPU Util</text>'
    )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'style="background:{_CARD_BG};border-radius:8px;">'
        + legend
        + "\n".join(cells)
        + "\n".join(col_headers)
        + "\n".join(row_labels)
        + "</svg>"
    )


def _card(title: str, value: str, subtitle: str = "") -> str:
    sub_html = f'<div style="color:{_MUTED};font-size:13px;margin-top:4px;">{subtitle}</div>' if subtitle else ""
    return (
        f'<div style="background:{_CARD_BG};border:1px solid {_BORDER};border-radius:10px;'
        f'padding:20px 24px;min-width:170px;flex:1;">'
        f'<div style="color:{_MUTED};font-size:12px;text-transform:uppercase;letter-spacing:1px;">{title}</div>'
        f'<div style="color:{_TEXT};font-size:28px;font-weight:700;margin-top:6px;">{value}</div>'
        f'{sub_html}'
        f'</div>'
    )


def _bottleneck_table(profiles: List[ConfigProfile]) -> str:
    rows = []
    for p in profiles:
        t = p.timing
        total = t.total_step
        phases_html = []
        for phase, label, color in zip(_PHASES, _PHASE_LABELS, _PHASE_COLORS):
            val = _phase_val(t, phase)
            pct = val / total * 100
            flag = " ⚠" if phase in p.bottleneck_phases else ""
            is_bn = phase in p.bottleneck_phases
            style = f"color:{_ORACLE_RED};font-weight:700;" if is_bn else f"color:{_TEXT};"
            phases_html.append(
                f'<td style="{style}text-align:right;">{val:.1f}ms ({pct:.0f}%){flag}</td>'
            )
        bn_list = ", ".join(p.bottleneck_phases) if p.bottleneck_phases else "—"
        rows.append(
            f'<tr style="border-bottom:1px solid {_BORDER};">'
            f'<td style="color:{_TEXT};font-weight:600;">{p.gpu_count}×A100</td>'
            + "".join(phases_html)
            + f'<td style="color:{_ORACLE_RED if p.bottleneck_phases else _MUTED};">{bn_list}</td>'
            f'</tr>'
        )

    headers = ["Config"] + _PHASE_LABELS + ["Bottlenecks (>30%)"]
    hdr_html = "".join(
        f'<th style="color:{_MUTED};text-align:right;padding:8px 12px;">{h}</th>'
        for h in headers
    )
    hdr_html = hdr_html.replace('text-align:right;padding:8px 12px;">Config', 'text-align:left;padding:8px 12px;">Config')

    return (
        f'<table style="width:100%;border-collapse:collapse;font-size:14px;">'
        f'<thead><tr style="border-bottom:2px solid {_BORDER};">{hdr_html}</tr></thead>'
        f'<tbody>' + "\n".join(rows) + '</tbody>'
        f'</table>'
    )


def _recommendations_html() -> str:
    items = [
        ("NVLink vs PCIe",
         "8-GPU grad_sync is 68ms vs 18ms for 2-GPU — consistent with PCIe topology. "
         "Switching to NVLink (BM.GPU.A100-v2.8) can reduce AllReduce latency by 3–5×, "
         "recovering 15–20% scaling efficiency at 8 GPUs."),
        ("Gradient Compression",
         "Apply PowerSGD or 1-bit Adam to compress gradients before AllReduce. "
         "Expected: 40–60% reduction in grad_sync time at 8 GPUs, with <0.5% accuracy drop."),
        ("Mixed Precision (BF16)",
         "GR00T already trains in BF16. Ensure `torch.autocast` wraps the full forward+backward. "
         "Halving gradient tensor size directly halves AllReduce bandwidth."),
        ("Data Loading Bottleneck",
         "data_load grows from 38ms (1×) to 52ms (8×). Increase DataLoader workers "
         "(num_workers=8), use prefetch_factor=4, and pin DALI or WebDataset for faster "
         "streaming of HDF5 episode data from OCI Object Storage."),
        ("Batch Size Scaling",
         "Scale local batch size with GPU count (linear scaling rule). "
         "Pair with linear LR warmup to maintain convergence. "
         "Larger effective batch = fewer AllReduce calls per epoch."),
        ("Overlap Compute & Communication",
         "Enable `torch.nn.parallel.DistributedDataParallel(bucket_cap_mb=50)` "
         "to overlap backward gradient computation with AllReduce, "
         "effectively hiding up to 70% of grad_sync latency."),
    ]
    rows = []
    for title, desc in items:
        rows.append(
            f'<div style="padding:14px 18px;border-left:3px solid {_ORACLE_RED};'
            f'background:{_CARD_BG};border-radius:6px;margin-bottom:10px;">'
            f'<div style="color:{_TEXT};font-weight:600;margin-bottom:4px;">{title}</div>'
            f'<div style="color:{_MUTED};font-size:14px;line-height:1.5;">{desc}</div>'
            f'</div>'
        )
    return "\n".join(rows)


def render_html(profiles: List[ConfigProfile], output_path: str) -> None:
    best = max(profiles, key=lambda p: p.steps_per_sec)
    worst_scale = min(profiles, key=lambda p: p.scaling_efficiency_pct)
    avg_comm_pct = sum(
        p.timing.grad_sync / p.timing.total_step * 100 for p in profiles
    ) / len(profiles)

    # Summary cards
    cards = (
        _card("Best Config", f"{best.gpu_count}×A100",
              f"{best.steps_per_sec:.2f} it/s")
        + _card("Peak Throughput", f"{best.steps_per_sec:.2f} it/s",
                f"vs {_IDEAL_THROUGHPUT[best.gpu_count]:.2f} ideal")
        + _card("Avg Comm Overhead", f"{avg_comm_pct:.1f}%",
                "grad_sync / total_step")
        + _card("Min Scale Efficiency", f"{worst_scale.scaling_efficiency_pct:.0f}%",
                f"{worst_scale.gpu_count}×A100 bottleneck")
    )

    bar_svg   = _svg_stacked_bar(profiles)
    line_svg  = _svg_scaling_line(profiles)
    heat_svg  = _svg_utilization_heatmap(profiles)
    bn_table  = _bottleneck_table(profiles)
    recs_html = _recommendations_html()

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>GR00T Multi-GPU Profiler</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: {_BG}; color: {_TEXT}; font-family: -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; padding: 32px; }}
  h1 {{ font-size: 26px; font-weight: 700; margin-bottom: 4px; }}
  h2 {{ font-size: 18px; font-weight: 600; margin: 36px 0 14px; color: {_TEXT}; border-bottom: 1px solid {_BORDER}; padding-bottom: 8px; }}
  .subtitle {{ color: {_MUTED}; font-size: 14px; margin-bottom: 28px; }}
  .cards {{ display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 36px; }}
  .charts {{ display: flex; gap: 24px; flex-wrap: wrap; align-items: flex-start; }}
  .section {{ margin-bottom: 36px; }}
  .oracle-badge {{ display: inline-block; background: {_ORACLE_RED}; color: white; font-size: 11px; font-weight: 700; padding: 2px 8px; border-radius: 4px; letter-spacing: 1px; margin-left: 10px; vertical-align: middle; }}
  table td, table th {{ padding: 10px 12px; }}
</style>
</head>
<body>
<h1>GR00T Multi-GPU Training Profiler <span class="oracle-badge">OCI Robot Cloud</span></h1>
<div class="subtitle">Bottleneck analysis across 1×A100 / 2×A100 / 4×A100 / 8×A100 — {_N_SAMPLES} steps simulated per config</div>

<h2>Summary</h2>
<div class="cards">{cards}</div>

<h2>Step Time Breakdown by Phase</h2>
<div class="section">{bar_svg}</div>

<h2>Throughput Scaling — Ideal vs Actual</h2>
<div class="section">{line_svg}</div>

<h2>GPU Utilization Heatmap</h2>
<div class="section">{heat_svg}</div>

<h2>Bottleneck Analysis</h2>
<div class="section"
     style="background:{_CARD_BG};border:1px solid {_BORDER};border-radius:10px;padding:4px 0;overflow-x:auto;">
  {bn_table}
</div>

<h2>Recommendations</h2>
<div class="section">{recs_html}</div>

<div style="margin-top:40px;color:{_MUTED};font-size:12px;">
  Generated by multi_gpu_profiler.py — OCI Robot Cloud · GR00T Fine-Tuning Pipeline
</div>
</body>
</html>"""

    Path(output_path).write_text(html, encoding="utf-8")
    print(f"  HTML report written → {output_path}")


# ---------------------------------------------------------------------------
# JSON Export
# ---------------------------------------------------------------------------

def export_json(profiles: List[ConfigProfile], output_path: str) -> None:
    def _profile_to_dict(p: ConfigProfile) -> Dict:
        return {
            "gpu_count": p.gpu_count,
            "steps_per_sec": round(p.steps_per_sec, 4),
            "scaling_efficiency_pct": round(p.scaling_efficiency_pct, 2),
            "ideal_throughput": _IDEAL_THROUGHPUT[p.gpu_count],
            "compute_comm_ratio": round(p.compute_comm_ratio, 3),
            "timing_ms": {
                "data_load":     round(p.timing.data_load, 2),
                "forward_pass":  round(p.timing.forward_pass, 2),
                "backward_pass": round(p.timing.backward_pass, 2),
                "grad_sync":     round(p.timing.grad_sync, 2),
                "optimizer_step":round(p.timing.optimizer_step, 2),
                "total_step":    round(p.timing.total_step, 2),
            },
            "gpu_metrics": [
                {
                    "device_id": g.device_id,
                    "utilization_pct": round(g.utilization_pct, 1),
                    "memory_used_gb":  round(g.memory_used_gb, 2),
                    "memory_total_gb": g.memory_total_gb,
                }
                for g in p.gpu_metrics
            ],
            "bottleneck_phases": p.bottleneck_phases,
        }

    data = {
        "profiler": "multi_gpu_profiler",
        "model": "GR00T-N1.6",
        "platform": "OCI A100-80G",
        "configs": [_profile_to_dict(p) for p in profiles],
    }

    json_path = output_path.replace(".html", ".json")
    Path(json_path).write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"  JSON results written  → {json_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="GR00T Multi-GPU Training Bottleneck Profiler"
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        default=True,
        help="Use simulated profiling data (default: True)",
    )
    parser.add_argument(
        "--output",
        default="/tmp/multi_gpu_profiler.html",
        metavar="PATH",
        help="Output path for HTML report (default: /tmp/multi_gpu_profiler.html)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        metavar="INT",
        help="Random seed for simulation (default: 42)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    print()
    print("  GR00T Multi-GPU Bottleneck Profiler")
    print(f"  Mode: {'mock/simulated' if args.mock else 'live'} | Seed: {args.seed}")
    print(f"  Output: {args.output}")
    print()

    profiles = simulate_all(seed=args.seed)

    print_table(profiles)

    print("  Generating reports…")
    render_html(profiles, args.output)
    export_json(profiles, args.output)

    print()
    print("  Done.")
    print()


if __name__ == "__main__":
    main()
