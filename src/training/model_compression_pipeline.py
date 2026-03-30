"""
GR00T model compression pipeline: FP16 → LoRA reduction → pruning → INT8 → ONNX/TensorRT
for edge deployment.
"""

import argparse
import json
import os
import random
from dataclasses import dataclass, field
from typing import List


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class CompressionStage:
    stage_name: str
    input_size_mb: float
    output_size_mb: float
    mae: float
    sr: float
    latency_ms: float
    vram_mb: float
    compression_ratio: float


@dataclass
class TargetDevice:
    name: str
    vram_gb: float
    max_latency_ms: float
    passes: bool


@dataclass
class CompressionReport:
    target_device: TargetDevice
    final_size_mb: float
    final_mae: float
    final_sr: float
    final_latency_ms: float
    meets_all_targets: bool
    stages: List[CompressionStage] = field(default_factory=list)
    device_results: List[TargetDevice] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Pipeline simulation
# ---------------------------------------------------------------------------

BASELINE_SIZE_MB = 6700.0
BASELINE_LATENCY_MS = 226.0
BASELINE_MAE = 0.013  # from session 5 fine-tune result
BASELINE_SR = 0.62    # success rate baseline post fine-tune


def simulate_stages(seed: int = 42) -> List[CompressionStage]:
    """Simulate 5 compression stages for GR00T."""
    rng = random.Random(seed)

    def jitter(v: float, pct: float = 0.005) -> float:
        return v * (1.0 + rng.uniform(-pct, pct))

    stages_raw = [
        # (name, out_mb, latency_ms, delta_mae, delta_sr)
        ("FP32 → FP16",                   3350.0, 201.0, 0.0008, -0.005),
        ("LoRA rank reduction (32 → 16)", 2800.0, 195.0, 0.0004, -0.002),
        ("Magnitude pruning 20%",          2240.0, 182.0, 0.0020, -0.010),
        ("INT8 quantization",               560.0, 131.0, 0.0030, -0.015),
        ("ONNX export + TensorRT",          520.0, 118.0, 0.0010, -0.005),
    ]

    results: List[CompressionStage] = []
    prev_size = BASELINE_SIZE_MB
    prev_latency = BASELINE_LATENCY_MS
    cumulative_mae = BASELINE_MAE
    cumulative_sr = BASELINE_SR

    for name, out_mb, lat_ms, d_mae, d_sr in stages_raw:
        out_mb = jitter(out_mb, 0.003)
        lat_ms = jitter(lat_ms, 0.003)
        cumulative_mae += d_mae
        cumulative_sr = max(0.0, cumulative_sr + d_sr)
        ratio = BASELINE_SIZE_MB / out_mb
        # VRAM roughly tracks model size with ~1.4× overhead for activations
        vram_mb = out_mb * 1.4

        stage = CompressionStage(
            stage_name=name,
            input_size_mb=round(prev_size, 1),
            output_size_mb=round(out_mb, 1),
            mae=round(cumulative_mae, 5),
            sr=round(cumulative_sr, 4),
            latency_ms=round(lat_ms, 1),
            vram_mb=round(vram_mb, 1),
            compression_ratio=round(ratio, 2),
        )
        results.append(stage)
        prev_size = out_mb
        prev_latency = lat_ms

    return results


# ---------------------------------------------------------------------------
# Device compatibility check
# ---------------------------------------------------------------------------

DEVICES = [
    # (name,                vram_gb, max_latency_ms, passes_after_stage_index)
    ("Jetson Orin",         8.0,     200.0,          3),  # stage index 3 = INT8
    ("Jetson AGX Xavier",   8.0,     300.0,          2),  # stage index 2 = pruning
    ("Jetson Nano",         4.0,     500.0,          3),  # stage index 3 = INT8
    ("OCI A100 (80GB)",    80.0,     300.0,          -1), # passes at baseline
    ("OCI A10 (24GB)",     24.0,     300.0,          1),  # stage index 1 = LoRA
]


def evaluate_devices(stages: List[CompressionStage]) -> List[TargetDevice]:
    """
    Return a TargetDevice per device with passes=True if the final stage meets constraints.
    The final stage is always the last one simulated.
    """
    final = stages[-1]
    results = []
    for name, vram_gb, max_lat_ms, _ in DEVICES:
        vram_ok = (final.vram_mb / 1024.0) <= vram_gb
        lat_ok = final.latency_ms <= max_lat_ms
        results.append(TargetDevice(
            name=name,
            vram_gb=vram_gb,
            max_latency_ms=max_lat_ms,
            passes=vram_ok and lat_ok,
        ))
    return results


def build_device_stage_matrix(stages: List[CompressionStage]) -> List[List[bool]]:
    """
    Returns a matrix[device_idx][stage_idx] = True if device passes at that stage.
    Includes baseline as stage 0.
    """
    # baseline pseudo-stage
    all_stages = [
        CompressionStage(
            stage_name="Baseline (FP32)",
            input_size_mb=BASELINE_SIZE_MB,
            output_size_mb=BASELINE_SIZE_MB,
            mae=BASELINE_MAE,
            sr=BASELINE_SR,
            latency_ms=BASELINE_LATENCY_MS,
            vram_mb=BASELINE_SIZE_MB * 1.4,
            compression_ratio=1.0,
        )
    ] + stages

    matrix = []
    for name, vram_gb, max_lat_ms, _ in DEVICES:
        row = []
        for s in all_stages:
            vram_ok = (s.vram_mb / 1024.0) <= vram_gb
            lat_ok = s.latency_ms <= max_lat_ms
            row.append(vram_ok and lat_ok)
        matrix.append(row)
    return matrix


# ---------------------------------------------------------------------------
# Build report
# ---------------------------------------------------------------------------

def build_report(stages: List[CompressionStage], device_results: List[TargetDevice]) -> CompressionReport:
    final = stages[-1]
    passes_count = sum(1 for d in device_results if d.passes)
    # primary target device = Jetson Orin
    primary_device = next(d for d in device_results if "Orin" in d.name)
    return CompressionReport(
        target_device=primary_device,
        final_size_mb=final.output_size_mb,
        final_mae=final.mae,
        final_sr=final.sr,
        final_latency_ms=final.latency_ms,
        meets_all_targets=primary_device.passes,
        stages=stages,
        device_results=device_results,
    )


# ---------------------------------------------------------------------------
# Stdout table
# ---------------------------------------------------------------------------

def print_stage_table(stages: List[CompressionStage]) -> None:
    header = f"{'Stage':<32} {'In MB':>8} {'Out MB':>8} {'Ratio':>6} {'MAE':>8} {'SR':>6} {'Lat ms':>8} {'VRAM MB':>9}"
    sep = "-" * len(header)
    print()
    print("GR00T Model Compression Pipeline — Stage Summary")
    print(sep)
    print(header)
    print(sep)
    for s in stages:
        print(
            f"{s.stage_name:<32} {s.input_size_mb:>8.1f} {s.output_size_mb:>8.1f} "
            f"{s.compression_ratio:>6.2f}x {s.mae:>8.5f} {s.sr:>6.3f} "
            f"{s.latency_ms:>8.1f} {s.vram_mb:>9.1f}"
        )
    print(sep)
    final = stages[-1]
    total_ratio = round(BASELINE_SIZE_MB / final.output_size_mb, 2)
    print(
        f"{'TOTAL REDUCTION':<32} {BASELINE_SIZE_MB:>8.1f} {final.output_size_mb:>8.1f} "
        f"{total_ratio:>6.2f}x {final.mae:>8.5f} {final.sr:>6.3f} "
        f"{final.latency_ms:>8.1f} {final.vram_mb:>9.1f}"
    )
    print()


# ---------------------------------------------------------------------------
# HTML / SVG generation
# ---------------------------------------------------------------------------

ORACLE_RED = "#C74634"
BG_DARK = "#1e293b"
BG_CARD = "#0f172a"
BG_SURFACE = "#1e2d40"
TEXT_PRIMARY = "#f1f5f9"
TEXT_SECONDARY = "#94a3b8"
ACCENT_GREEN = "#22c55e"
ACCENT_BLUE = "#38bdf8"
ACCENT_AMBER = "#fbbf24"


def _svg_waterfall(stages: List[CompressionStage]) -> str:
    """SVG waterfall chart: horizontal bars showing size at each stage."""
    chart_w = 700
    bar_h = 36
    gap = 14
    padding_left = 190
    padding_top = 30
    padding_bottom = 30
    max_size = BASELINE_SIZE_MB

    all_labels = ["Baseline (FP32)"] + [s.stage_name for s in stages]
    all_sizes = [BASELINE_SIZE_MB] + [s.output_size_mb for s in stages]
    n = len(all_labels)
    chart_h = padding_top + n * (bar_h + gap) + padding_bottom

    scale = (chart_w - padding_left - 20) / max_size

    colors = [TEXT_SECONDARY, ORACLE_RED, "#e07a5f", ACCENT_AMBER, ACCENT_BLUE, ACCENT_GREEN]

    bars = []
    for i, (label, size) in enumerate(zip(all_labels, all_sizes)):
        y = padding_top + i * (bar_h + gap)
        w = size * scale
        color = colors[min(i, len(colors) - 1)]
        bars.append(
            f'  <rect x="{padding_left}" y="{y}" width="{w:.1f}" height="{bar_h}" '
            f'fill="{color}" rx="4"/>'
        )
        bars.append(
            f'  <text x="{padding_left - 8}" y="{y + bar_h / 2 + 5}" '
            f'fill="{TEXT_PRIMARY}" font-size="12" text-anchor="end">{label}</text>'
        )
        size_label = f"{size:.0f} MB" if size < 1000 else f"{size/1024:.2f} GB"
        bars.append(
            f'  <text x="{padding_left + w + 6}" y="{y + bar_h / 2 + 5}" '
            f'fill="{TEXT_SECONDARY}" font-size="11">{size_label}</text>'
        )

    return (
        f'<svg width="{chart_w}" height="{chart_h}" xmlns="http://www.w3.org/2000/svg" '
        f'style="background:{BG_SURFACE};border-radius:8px">\n'
        + "\n".join(bars)
        + "\n</svg>"
    )


def _svg_mae_chart(stages: List[CompressionStage]) -> str:
    """SVG stacked bar chart showing cumulative MAE after each stage."""
    chart_w = 700
    bar_w = 70
    gap = 28
    padding_left = 60
    padding_top = 20
    padding_bottom = 50
    max_mae = stages[-1].mae * 1.2

    n = len(stages)
    chart_h = 260
    usable_h = chart_h - padding_top - padding_bottom

    scale = usable_h / max_mae

    bars = []
    for i, s in enumerate(stages):
        x = padding_left + i * (bar_w + gap)
        bar_height = s.mae * scale
        y = padding_top + (usable_h - bar_height)
        bars.append(
            f'  <rect x="{x}" y="{y:.1f}" width="{bar_w}" height="{bar_height:.1f}" '
            f'fill="{ORACLE_RED}" rx="4" opacity="0.85"/>'
        )
        bars.append(
            f'  <text x="{x + bar_w / 2}" y="{y - 6:.1f}" fill="{TEXT_PRIMARY}" '
            f'font-size="11" text-anchor="middle">{s.mae:.5f}</text>'
        )
        short = s.stage_name.replace("→", "→\n")
        label_lines = s.stage_name.split(" ")
        mid = len(label_lines) // 2
        line1 = " ".join(label_lines[:mid]) or s.stage_name
        line2 = " ".join(label_lines[mid:])
        label_y = chart_h - padding_bottom + 16
        bars.append(
            f'  <text x="{x + bar_w / 2}" y="{label_y}" fill="{TEXT_SECONDARY}" '
            f'font-size="10" text-anchor="middle">{line1}</text>'
        )
        if line2:
            bars.append(
                f'  <text x="{x + bar_w / 2}" y="{label_y + 13}" fill="{TEXT_SECONDARY}" '
                f'font-size="10" text-anchor="middle">{line2}</text>'
            )

    # y-axis label
    bars.append(
        f'  <text x="14" y="{chart_h // 2}" fill="{TEXT_SECONDARY}" font-size="11" '
        f'text-anchor="middle" transform="rotate(-90,14,{chart_h // 2})">Cumulative MAE</text>'
    )

    total_w = padding_left + n * (bar_w + gap) + 20
    return (
        f'<svg width="{total_w}" height="{chart_h}" xmlns="http://www.w3.org/2000/svg" '
        f'style="background:{BG_SURFACE};border-radius:8px">\n'
        + "\n".join(bars)
        + "\n</svg>"
    )


def _svg_latency_chart(stages: List[CompressionStage]) -> str:
    """SVG bar chart: latency at each stage including baseline."""
    all_labels = ["Baseline"] + [s.stage_name for s in stages]
    all_latencies = [BASELINE_LATENCY_MS] + [s.latency_ms for s in stages]

    chart_w = 760
    bar_w = 70
    gap = 20
    padding_left = 60
    padding_top = 20
    padding_bottom = 50
    chart_h = 260
    usable_h = chart_h - padding_top - padding_bottom
    max_lat = BASELINE_LATENCY_MS * 1.1
    scale = usable_h / max_lat

    colors = [TEXT_SECONDARY, ORACLE_RED, "#e07a5f", ACCENT_AMBER, ACCENT_BLUE, ACCENT_GREEN]

    bars = []
    for i, (label, lat) in enumerate(zip(all_labels, all_latencies)):
        x = padding_left + i * (bar_w + gap)
        bar_h = lat * scale
        y = padding_top + (usable_h - bar_h)
        color = colors[min(i, len(colors) - 1)]
        bars.append(
            f'  <rect x="{x}" y="{y:.1f}" width="{bar_w}" height="{bar_h:.1f}" '
            f'fill="{color}" rx="4" opacity="0.85"/>'
        )
        bars.append(
            f'  <text x="{x + bar_w / 2}" y="{y - 6:.1f}" fill="{TEXT_PRIMARY}" '
            f'font-size="11" text-anchor="middle">{lat:.0f}ms</text>'
        )
        label_lines = label.split(" ")
        mid = max(1, len(label_lines) // 2)
        line1 = " ".join(label_lines[:mid])
        line2 = " ".join(label_lines[mid:])
        label_y = chart_h - padding_bottom + 16
        bars.append(
            f'  <text x="{x + bar_w / 2}" y="{label_y}" fill="{TEXT_SECONDARY}" '
            f'font-size="10" text-anchor="middle">{line1}</text>'
        )
        if line2:
            bars.append(
                f'  <text x="{x + bar_w / 2}" y="{label_y + 13}" fill="{TEXT_SECONDARY}" '
                f'font-size="10" text-anchor="middle">{line2}</text>'
            )

    bars.append(
        f'  <text x="14" y="{chart_h // 2}" fill="{TEXT_SECONDARY}" font-size="11" '
        f'text-anchor="middle" transform="rotate(-90,14,{chart_h // 2})">Latency (ms)</text>'
    )

    total_w = padding_left + len(all_labels) * (bar_w + gap) + 20
    return (
        f'<svg width="{total_w}" height="{chart_h}" xmlns="http://www.w3.org/2000/svg" '
        f'style="background:{BG_SURFACE};border-radius:8px">\n'
        + "\n".join(bars)
        + "\n</svg>"
    )


def _check_cell(ok: bool) -> str:
    if ok:
        return '<td style="text-align:center;padding:8px 12px"><span style="color:#22c55e;font-size:18px">&#10003;</span></td>'
    return '<td style="text-align:center;padding:8px 12px"><span style="color:#ef4444;font-size:18px">&#10007;</span></td>'


def _device_matrix_html(stages: List[CompressionStage]) -> str:
    """HTML table: 5 devices × (baseline + 5 stages), showing checkmarks."""
    matrix = build_device_stage_matrix(stages)
    device_names = [d[0] for d in DEVICES]
    col_headers = ["Baseline (FP32)"] + [s.stage_name for s in stages]

    rows = []
    for di, device_row in enumerate(matrix):
        cells = "".join(_check_cell(ok) for ok in device_row)
        vram = DEVICES[di][1]
        lat = DEVICES[di][2]
        rows.append(
            f"<tr><td style='padding:8px 14px;font-weight:600;color:{TEXT_PRIMARY};white-space:nowrap'>"
            f"{device_names[di]}</td>"
            f"<td style='padding:8px 12px;color:{TEXT_SECONDARY};text-align:center'>{int(vram)}GB</td>"
            f"<td style='padding:8px 12px;color:{TEXT_SECONDARY};text-align:center'>{int(lat)}ms</td>"
            f"{cells}</tr>"
        )

    headers = "".join(
        f"<th style='padding:10px 12px;color:{ORACLE_RED};font-weight:600;font-size:12px;text-transform:uppercase'>{h}</th>"
        for h in col_headers
    )

    return f"""
<div style="overflow-x:auto">
<table style="border-collapse:collapse;width:100%;background:{BG_CARD};border-radius:8px;overflow:hidden">
  <thead>
    <tr>
      <th style='padding:10px 14px;color:{ORACLE_RED};font-weight:600;font-size:12px;text-align:left;text-transform:uppercase'>Device</th>
      <th style='padding:10px 12px;color:{ORACLE_RED};font-weight:600;font-size:12px;text-transform:uppercase'>VRAM</th>
      <th style='padding:10px 12px;color:{ORACLE_RED};font-weight:600;font-size:12px;text-transform:uppercase'>Max Lat</th>
      {headers}
    </tr>
  </thead>
  <tbody style="font-size:14px">
    {"".join(rows)}
  </tbody>
</table>
</div>"""


def _stage_table_html(stages: List[CompressionStage]) -> str:
    rows = []
    for i, s in enumerate(stages):
        rows.append(f"""
    <tr style="border-bottom:1px solid #2d3f55">
      <td style="padding:10px 14px;color:{TEXT_PRIMARY};font-weight:500">{i+1}. {s.stage_name}</td>
      <td style="padding:10px 12px;color:{TEXT_SECONDARY};text-align:right">{s.input_size_mb:.0f}</td>
      <td style="padding:10px 12px;color:{TEXT_PRIMARY};text-align:right;font-weight:600">{s.output_size_mb:.0f}</td>
      <td style="padding:10px 12px;color:{ACCENT_AMBER};text-align:right">{s.compression_ratio:.2f}×</td>
      <td style="padding:10px 12px;color:{TEXT_SECONDARY};text-align:right">{s.mae:.5f}</td>
      <td style="padding:10px 12px;color:{ACCENT_GREEN};text-align:right">{s.sr:.3f}</td>
      <td style="padding:10px 12px;color:{ACCENT_BLUE};text-align:right">{s.latency_ms:.1f}</td>
      <td style="padding:10px 12px;color:{TEXT_SECONDARY};text-align:right">{s.vram_mb:.0f}</td>
    </tr>""")

    return f"""
<table style="border-collapse:collapse;width:100%;background:{BG_CARD};border-radius:8px;overflow:hidden">
  <thead>
    <tr style="background:{BG_SURFACE}">
      <th style="padding:12px 14px;color:{ORACLE_RED};font-size:12px;text-transform:uppercase;text-align:left">Stage</th>
      <th style="padding:12px 12px;color:{ORACLE_RED};font-size:12px;text-transform:uppercase;text-align:right">In MB</th>
      <th style="padding:12px 12px;color:{ORACLE_RED};font-size:12px;text-transform:uppercase;text-align:right">Out MB</th>
      <th style="padding:12px 12px;color:{ORACLE_RED};font-size:12px;text-transform:uppercase;text-align:right">Ratio</th>
      <th style="padding:12px 12px;color:{ORACLE_RED};font-size:12px;text-transform:uppercase;text-align:right">MAE</th>
      <th style="padding:12px 12px;color:{ORACLE_RED};font-size:12px;text-transform:uppercase;text-align:right">SR</th>
      <th style="padding:12px 12px;color:{ORACLE_RED};font-size:12px;text-transform:uppercase;text-align:right">Lat ms</th>
      <th style="padding:12px 12px;color:{ORACLE_RED};font-size:12px;text-transform:uppercase;text-align:right">VRAM MB</th>
    </tr>
  </thead>
  <tbody style="font-size:14px">
    {"".join(rows)}
  </tbody>
</table>"""


def generate_html_report(report: CompressionReport) -> str:
    stages = report.stages
    final = stages[-1]
    total_ratio = round(BASELINE_SIZE_MB / final.output_size_mb, 2)
    passes_count = sum(1 for d in report.device_results if d.passes)

    waterfall_svg = _svg_waterfall(stages)
    mae_svg = _svg_mae_chart(stages)
    latency_svg = _svg_latency_chart(stages)
    stage_table = _stage_table_html(stages)
    device_matrix = _device_matrix_html(stages)

    stat_cards = f"""
<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:32px">
  <div style="background:{BG_CARD};border-radius:10px;padding:20px;border-left:4px solid {ORACLE_RED}">
    <div style="font-size:12px;color:{TEXT_SECONDARY};text-transform:uppercase;letter-spacing:1px;margin-bottom:8px">Final Size</div>
    <div style="font-size:28px;font-weight:700;color:{TEXT_PRIMARY}">{final.output_size_mb:.0f} <span style="font-size:16px;color:{TEXT_SECONDARY}">MB</span></div>
    <div style="font-size:12px;color:{TEXT_SECONDARY};margin-top:4px">from {BASELINE_SIZE_MB/1024:.1f} GB baseline</div>
  </div>
  <div style="background:{BG_CARD};border-radius:10px;padding:20px;border-left:4px solid {ACCENT_AMBER}">
    <div style="font-size:12px;color:{TEXT_SECONDARY};text-transform:uppercase;letter-spacing:1px;margin-bottom:8px">Compression Ratio</div>
    <div style="font-size:28px;font-weight:700;color:{TEXT_PRIMARY}">{total_ratio}<span style="font-size:16px;color:{TEXT_SECONDARY}">×</span></div>
    <div style="font-size:12px;color:{TEXT_SECONDARY};margin-top:4px">vs FP32 baseline</div>
  </div>
  <div style="background:{BG_CARD};border-radius:10px;padding:20px;border-left:4px solid {ACCENT_BLUE}">
    <div style="font-size:12px;color:{TEXT_SECONDARY};text-transform:uppercase;letter-spacing:1px;margin-bottom:8px">Final Latency</div>
    <div style="font-size:28px;font-weight:700;color:{TEXT_PRIMARY}">{final.latency_ms:.0f} <span style="font-size:16px;color:{TEXT_SECONDARY}">ms</span></div>
    <div style="font-size:12px;color:{TEXT_SECONDARY};margin-top:4px">from {BASELINE_LATENCY_MS:.0f}ms baseline</div>
  </div>
  <div style="background:{BG_CARD};border-radius:10px;padding:20px;border-left:4px solid {ACCENT_GREEN}">
    <div style="font-size:12px;color:{TEXT_SECONDARY};text-transform:uppercase;letter-spacing:1px;margin-bottom:8px">Devices Passing</div>
    <div style="font-size:28px;font-weight:700;color:{TEXT_PRIMARY}">{passes_count}<span style="font-size:16px;color:{TEXT_SECONDARY}">/{len(report.device_results)}</span></div>
    <div style="font-size:12px;color:{TEXT_SECONDARY};margin-top:4px">after full pipeline</div>
  </div>
</div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>GR00T Model Compression Pipeline Report</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: {BG_DARK}; color: {TEXT_PRIMARY}; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; padding: 32px; }}
    h1 {{ font-size: 24px; font-weight: 700; margin-bottom: 4px; }}
    h2 {{ font-size: 16px; font-weight: 600; color: {TEXT_SECONDARY}; margin-bottom: 24px; }}
    h3 {{ font-size: 15px; font-weight: 600; color: {TEXT_PRIMARY}; margin-bottom: 16px; text-transform: uppercase; letter-spacing: 1px; }}
    .section {{ margin-bottom: 40px; }}
    .oracle-badge {{ display:inline-block; background:{ORACLE_RED}; color:#fff; font-size:11px; font-weight:700; padding:3px 10px; border-radius:4px; letter-spacing:1px; text-transform:uppercase; margin-right:10px; vertical-align:middle; }}
    svg {{ max-width: 100%; }}
  </style>
</head>
<body>
  <div style="max-width:1100px;margin:0 auto">
    <div style="margin-bottom:28px">
      <span class="oracle-badge">OCI Robot Cloud</span>
      <h1 style="display:inline;vertical-align:middle">GR00T Model Compression Pipeline</h1>
      <h2 style="margin-top:8px">FP16 → LoRA Reduction → Magnitude Pruning → INT8 → ONNX/TensorRT &nbsp;|&nbsp; GR00T N1.6 Edge Deployment</h2>
    </div>

    <div class="section">
      {stat_cards}
    </div>

    <div class="section">
      <h3>Model Size — Waterfall</h3>
      {waterfall_svg}
    </div>

    <div class="section" style="display:grid;grid-template-columns:1fr 1fr;gap:32px">
      <div>
        <h3>MAE Degradation (Cumulative)</h3>
        {mae_svg}
      </div>
      <div>
        <h3>Latency Reduction per Stage</h3>
        {latency_svg}
      </div>
    </div>

    <div class="section">
      <h3>Stage Details</h3>
      {stage_table}
    </div>

    <div class="section">
      <h3>Device Compatibility Matrix</h3>
      {device_matrix}
    </div>

    <div style="font-size:12px;color:{TEXT_SECONDARY};margin-top:24px;text-align:center">
      Generated by OCI Robot Cloud · GR00T N1.6 · Baseline: 6.7GB FP32 · 226ms inference
    </div>
  </div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="GR00T model compression pipeline: FP16 → LoRA → pruning → INT8 → ONNX/TensorRT"
    )
    parser.add_argument("--mock", action="store_true", default=True,
                        help="Run in simulation mode (no real model required)")
    parser.add_argument("--output", default="/tmp/model_compression_pipeline.html",
                        help="Path for HTML report output")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed for simulation jitter")
    args = parser.parse_args()

    print(f"\nRunning GR00T model compression pipeline (seed={args.seed}) ...")
    print(f"Baseline: {BASELINE_SIZE_MB/1024:.2f}GB FP32 | {BASELINE_LATENCY_MS}ms | MAE {BASELINE_MAE}")

    # Run pipeline
    stages = simulate_stages(seed=args.seed)
    device_results = evaluate_devices(stages)
    report = build_report(stages, device_results)

    # Stdout table
    print_stage_table(stages)

    # Device summary
    print("Device Compatibility (after full pipeline):")
    for d in report.device_results:
        status = "PASS" if d.passes else "FAIL"
        color_flag = "" if d.passes else " [needs earlier stage]"
        print(f"  {d.name:<22} {d.vram_gb:.0f}GB VRAM  {d.max_latency_ms:.0f}ms target  → {status}{color_flag}")
    print()

    # HTML report
    html = generate_html_report(report)
    out_path = os.path.abspath(args.output)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)

    final = stages[-1]
    total_ratio = BASELINE_SIZE_MB / final.output_size_mb
    passes_count = sum(1 for d in report.device_results if d.passes)
    print(f"Compression complete:")
    print(f"  Size:    {BASELINE_SIZE_MB:.0f}MB → {final.output_size_mb:.0f}MB  ({total_ratio:.1f}× smaller)")
    print(f"  Latency: {BASELINE_LATENCY_MS:.0f}ms → {final.latency_ms:.0f}ms")
    print(f"  MAE:     {BASELINE_MAE:.5f} → {final.mae:.5f}  (+{final.mae - BASELINE_MAE:.5f})")
    print(f"  Devices passing: {passes_count}/{len(report.device_results)}")
    print(f"\nHTML report saved to: {out_path}\n")


if __name__ == "__main__":
    main()
