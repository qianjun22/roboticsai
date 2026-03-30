"""
End-to-end inference latency breakdown for GR00T on OCI A100, A10, and Jetson Orin.
Identifies bottlenecks for optimization.
"""

import argparse
import json
import math
import random
import sys
from dataclasses import dataclass, field, asdict


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class LatencyComponent:
    name: str
    p50_ms: float
    p95_ms: float
    p99_ms: float
    pct_of_total: float
    is_bottleneck: bool


@dataclass
class LatencyProfile:
    hardware: str
    total_p50: float
    total_p95: float
    total_p99: float
    components: list  # list[LatencyComponent]
    meets_200ms_sla: bool


@dataclass
class LatencyReport:
    best_hardware: str
    fastest_p50_ms: float
    components: list  # list[str] — component names in breakdown order
    hardware_profiles: list  # list[LatencyProfile]


# ---------------------------------------------------------------------------
# Simulation
# ---------------------------------------------------------------------------

# Base latencies (ms) per component per hardware
# Format: {component: (oci_a100, oci_a10, jetson_orin)}
COMPONENT_BASE_LATENCY = {
    "image_capture":     (5,  8,  15),
    "image_preprocess":  (3,  5,   8),
    "tokenize":          (8, 12,  18),
    "vision_encoder":    (45, 72,  95),
    "language_grounding":(12, 18,  28),
    "policy_head":       (38, 58,  88),
    "action_decode":     (5,  8,  12),
    "network_latency":   (2,  2,  18),
    "robot_controller":  (8,  8,  12),
}

HARDWARE_CONFIGS = ["oci_a100", "oci_a10", "jetson_orin"]
HW_INDEX = {hw: i for i, hw in enumerate(HARDWARE_CONFIGS)}

SLA_MS = 200.0
N_SAMPLES = 1000


def _gaussian_noise(base: float, rng: random.Random, rel_std: float = 0.05) -> float:
    """Return base + gaussian noise with relative std."""
    noise = rng.gauss(0, base * rel_std)
    return max(base * 0.5, base + noise)


def _percentile(data: list, pct: float) -> float:
    data_sorted = sorted(data)
    idx = (pct / 100.0) * (len(data_sorted) - 1)
    lo = int(idx)
    hi = min(lo + 1, len(data_sorted) - 1)
    frac = idx - lo
    return data_sorted[lo] * (1 - frac) + data_sorted[hi] * frac


def simulate_hardware(hw: str, rng: random.Random) -> LatencyProfile:
    idx = HW_INDEX[hw]

    # Per-component samples
    component_samples: dict[str, list[float]] = {c: [] for c in COMPONENT_BASE_LATENCY}
    total_samples: list[float] = [0.0] * N_SAMPLES

    for i in range(N_SAMPLES):
        run_total = 0.0
        for comp, bases in COMPONENT_BASE_LATENCY.items():
            base = bases[idx]
            val = _gaussian_noise(base, rng)
            component_samples[comp].append(val)
            run_total += val
        total_samples[i] = run_total

    total_p50 = _percentile(total_samples, 50)
    total_p95 = _percentile(total_samples, 95)
    total_p99 = _percentile(total_samples, 99)

    # Build LatencyComponent list
    components = []
    max_p50 = -1.0
    bottleneck_name = ""
    comp_p50s = {}
    for comp in COMPONENT_BASE_LATENCY:
        cp50 = _percentile(component_samples[comp], 50)
        cp95 = _percentile(component_samples[comp], 95)
        cp99 = _percentile(component_samples[comp], 99)
        comp_p50s[comp] = cp50
        if cp50 > max_p50:
            max_p50 = cp50
            bottleneck_name = comp

    for comp in COMPONENT_BASE_LATENCY:
        cp50 = comp_p50s[comp]
        cp95 = _percentile(component_samples[comp], 95)
        cp99 = _percentile(component_samples[comp], 99)
        pct = round(cp50 / total_p50 * 100, 1) if total_p50 > 0 else 0.0
        components.append(LatencyComponent(
            name=comp,
            p50_ms=round(cp50, 2),
            p95_ms=round(cp95, 2),
            p99_ms=round(cp99, 2),
            pct_of_total=pct,
            is_bottleneck=(comp == bottleneck_name),
        ))

    return LatencyProfile(
        hardware=hw,
        total_p50=round(total_p50, 2),
        total_p95=round(total_p95, 2),
        total_p99=round(total_p99, 2),
        components=components,
        meets_200ms_sla=(total_p50 <= SLA_MS),
    )


def build_report(profiles: list) -> LatencyReport:
    best = min(profiles, key=lambda p: p.total_p50)
    return LatencyReport(
        best_hardware=best.hardware,
        fastest_p50_ms=best.total_p50,
        components=list(COMPONENT_BASE_LATENCY.keys()),
        hardware_profiles=profiles,
    )


# ---------------------------------------------------------------------------
# Stdout table
# ---------------------------------------------------------------------------

def print_component_table(report: LatencyReport) -> None:
    hw_labels = {
        "oci_a100": "OCI A100",
        "oci_a10":  "OCI A10",
        "jetson_orin": "Jetson Orin",
    }
    comp_names = report.components

    print("\n" + "=" * 80)
    print("  GR00T End-to-End Latency Breakdown (p50 ms)")
    print("=" * 80)
    header = f"{'Component':<22}" + "".join(f"{hw_labels[p.hardware]:>14}" for p in report.hardware_profiles)
    print(header)
    print("-" * 80)
    for comp in comp_names:
        row = f"{comp:<22}"
        for profile in report.hardware_profiles:
            matched = next((c for c in profile.components if c.name == comp), None)
            if matched:
                mark = " *" if matched.is_bottleneck else "  "
                row += f"{matched.p50_ms:>12.1f}{mark}"
            else:
                row += f"{'N/A':>14}"
        print(row)
    print("-" * 80)
    totals = f"{'TOTAL p50':<22}"
    for p in report.hardware_profiles:
        sla = " SLA" if p.meets_200ms_sla else " !SLA"
        totals += f"{p.total_p50:>9.1f}{sla:>5}"
    print(totals)
    print("=" * 80)
    print("  * = bottleneck component for that hardware target")
    print(f"\n  Best hardware: {report.best_hardware}  ({report.fastest_p50_ms:.1f} ms p50)")
    sla_pass = sum(1 for p in report.hardware_profiles if p.meets_200ms_sla)
    print(f"  SLA compliance ({SLA_MS}ms): {sla_pass}/{len(report.hardware_profiles)} hardware configs")

    a100 = next((p for p in report.hardware_profiles if p.hardware == "oci_a100"), None)
    jetson = next((p for p in report.hardware_profiles if p.hardware == "jetson_orin"), None)
    if a100 and jetson:
        ratio = jetson.total_p50 / a100.total_p50
        print(f"  Jetson / A100 ratio: {ratio:.2f}x")
    print()


# ---------------------------------------------------------------------------
# HTML report
# ---------------------------------------------------------------------------

COLORS = [
    "#C74634", "#e07b2e", "#f5c242", "#4caf50",
    "#2196f3", "#9c27b0", "#00bcd4", "#ff5722", "#607d8b",
]
HW_COLORS = {
    "oci_a100":    "#4caf50",
    "oci_a10":     "#2196f3",
    "jetson_orin": "#e07b2e",
}
HW_DISPLAY = {
    "oci_a100":    "OCI A100",
    "oci_a10":     "OCI A10 G",
    "jetson_orin": "Jetson Orin",
}


def _stacked_bar_svg(profiles: list, comp_names: list) -> str:
    max_total = max(p.total_p50 for p in profiles) * 1.15
    W, H = 700, 220
    margin_left, margin_right, margin_top, margin_bottom = 110, 80, 20, 20
    bar_area_w = W - margin_left - margin_right
    bar_height = 44
    bar_gap = 22
    total_bars = len(profiles)
    needed_h = margin_top + margin_bottom + total_bars * (bar_height + bar_gap)
    H = max(H, needed_h)

    lines = [
        f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg" '
        f'style="background:#1e293b;border-radius:8px;">',
    ]

    # Legend
    legend_x = margin_left
    legend_y = H - margin_bottom + 2
    for i, comp in enumerate(comp_names):
        col = COLORS[i % len(COLORS)]
        lx = legend_x + (i % 5) * 130
        ly = legend_y + (i // 5) * 16
        lines.append(f'<rect x="{lx}" y="{ly}" width="12" height="10" fill="{col}" rx="2"/>')
        label = comp.replace("_", " ")
        lines.append(
            f'<text x="{lx+15}" y="{ly+9}" fill="#94a3b8" font-size="9" font-family="monospace">{label}</text>'
        )

    # Bars
    for row_idx, profile in enumerate(profiles):
        y = margin_top + row_idx * (bar_height + bar_gap)
        hw_label = HW_DISPLAY.get(profile.hardware, profile.hardware)
        lines.append(
            f'<text x="{margin_left - 6}" y="{y + bar_height // 2 + 4}" '
            f'fill="#e2e8f0" font-size="11" font-family="sans-serif" text-anchor="end">{hw_label}</text>'
        )
        x_cursor = margin_left
        for ci, comp in enumerate(comp_names):
            matched = next((c for c in profile.components if c.name == comp), None)
            if not matched:
                continue
            w = (matched.p50_ms / max_total) * bar_area_w
            col = COLORS[ci % len(COLORS)]
            lines.append(
                f'<rect x="{x_cursor:.1f}" y="{y}" width="{w:.1f}" height="{bar_height}" fill="{col}" />'
            )
            if w > 20:
                tx = x_cursor + w / 2
                ty = y + bar_height / 2 + 4
                lines.append(
                    f'<text x="{tx:.1f}" y="{ty:.1f}" fill="#fff" font-size="8" '
                    f'font-family="monospace" text-anchor="middle">{matched.p50_ms:.0f}</text>'
                )
            x_cursor += w
        # Total label
        sla_mark = " ✓" if profile.meets_200ms_sla else " ✗"
        sla_col = "#4caf50" if profile.meets_200ms_sla else "#C74634"
        lines.append(
            f'<text x="{x_cursor + 6:.1f}" y="{y + bar_height // 2 + 4}" '
            f'fill="{sla_col}" font-size="11" font-family="monospace">'
            f'{profile.total_p50:.0f}ms{sla_mark}</text>'
        )

    lines.append("</svg>")
    return "\n".join(lines)


def _donut_svg(profile: LatencyProfile, comp_names: list) -> str:
    W, H = 400, 320
    cx, cy, r_outer, r_inner = 180, 155, 110, 58
    total = sum(c.p50_ms for c in profile.components)
    start_angle = -math.pi / 2

    lines = [
        f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg" '
        f'style="background:#1e293b;border-radius:8px;">',
        f'<text x="{cx}" y="20" fill="#e2e8f0" font-size="13" font-family="sans-serif" '
        f'text-anchor="middle" font-weight="bold">OCI A100 Component Breakdown</text>',
    ]

    for ci, comp in enumerate(comp_names):
        matched = next((c for c in profile.components if c.name == comp), None)
        if not matched or total == 0:
            continue
        sweep = (matched.p50_ms / total) * 2 * math.pi
        end_angle = start_angle + sweep
        x1 = cx + r_outer * math.cos(start_angle)
        y1 = cy + r_outer * math.sin(start_angle)
        x2 = cx + r_outer * math.cos(end_angle)
        y2 = cy + r_outer * math.sin(end_angle)
        xi1 = cx + r_inner * math.cos(end_angle)
        yi1 = cy + r_inner * math.sin(end_angle)
        xi2 = cx + r_inner * math.cos(start_angle)
        yi2 = cy + r_inner * math.sin(start_angle)
        large_arc = 1 if sweep > math.pi else 0
        col = COLORS[ci % len(COLORS)]
        d = (
            f"M {x1:.2f} {y1:.2f} "
            f"A {r_outer} {r_outer} 0 {large_arc} 1 {x2:.2f} {y2:.2f} "
            f"L {xi1:.2f} {yi1:.2f} "
            f"A {r_inner} {r_inner} 0 {large_arc} 0 {xi2:.2f} {yi2:.2f} Z"
        )
        lines.append(f'<path d="{d}" fill="{col}" stroke="#1e293b" stroke-width="1.5"/>')
        # Label for slices > 5%
        if matched.pct_of_total > 5:
            mid_angle = start_angle + sweep / 2
            lx = cx + (r_inner + (r_outer - r_inner) * 0.55) * math.cos(mid_angle)
            ly = cy + (r_inner + (r_outer - r_inner) * 0.55) * math.sin(mid_angle)
            lines.append(
                f'<text x="{lx:.1f}" y="{ly:.1f}" fill="#fff" font-size="9" '
                f'font-family="monospace" text-anchor="middle">{matched.pct_of_total:.0f}%</text>'
            )
        start_angle = end_angle

    # Centre text
    lines.append(
        f'<text x="{cx}" y="{cy - 6}" fill="#e2e8f0" font-size="14" '
        f'font-family="sans-serif" text-anchor="middle" font-weight="bold">'
        f'{profile.total_p50:.0f}ms</text>'
    )
    lines.append(
        f'<text x="{cx}" y="{cy + 12}" fill="#94a3b8" font-size="10" '
        f'font-family="sans-serif" text-anchor="middle">total p50</text>'
    )

    # Legend (right side)
    lx0, ly0 = 300, 40
    for ci, comp in enumerate(comp_names):
        matched = next((c for c in profile.components if c.name == comp), None)
        col = COLORS[ci % len(COLORS)]
        ly = ly0 + ci * 20
        label = comp.replace("_", " ")
        lines.append(f'<rect x="{lx0}" y="{ly}" width="10" height="10" fill="{col}" rx="2"/>')
        lines.append(
            f'<text x="{lx0 + 14}" y="{ly + 9}" fill="#94a3b8" font-size="9" '
            f'font-family="monospace">{label}</text>'
        )
        if matched:
            lines.append(
                f'<text x="{lx0 + 14}" y="{ly + 18}" fill="#64748b" font-size="8" '
                f'font-family="monospace">{matched.p50_ms:.1f}ms</text>'
            )

    lines.append("</svg>")
    return "\n".join(lines)


OPTIMIZATION_TIPS = {
    "oci_a100": [
        ("vision_encoder", "Use INT8/FP8 quantization on encoder — can shave ~10ms"),
        ("policy_head", "Compile policy head with torch.compile() for ~15% speedup"),
        ("tokenize", "Cache tokenizer output for repeated prompts"),
    ],
    "oci_a10": [
        ("vision_encoder", "Switch to TensorRT engine for vision encoder — ~20ms savings"),
        ("policy_head", "Enable CUDA graphs to reduce kernel-launch overhead"),
        ("language_grounding", "Reduce grounding model to 1B params for non-critical tasks"),
    ],
    "jetson_orin": [
        ("network_latency", "Move to PCIe-attached camera or GigE to cut USB latency"),
        ("vision_encoder", "Use GR00T-nano (distilled) — encoder drops from 95ms to ~40ms"),
        ("policy_head", "Deploy policy head in DLA (Deep Learning Accelerator) — offload from GPU"),
    ],
}


def generate_html(report: LatencyReport) -> str:
    profiles = report.hardware_profiles
    comp_names = report.components

    a100 = next((p for p in profiles if p.hardware == "oci_a100"), profiles[0])
    jetson = next((p for p in profiles if p.hardware == "jetson_orin"), profiles[-1])
    ratio = jetson.total_p50 / a100.total_p50 if a100.total_p50 > 0 else 0
    sla_count = sum(1 for p in profiles if p.meets_200ms_sla)

    bottleneck_comp = next(
        (c.name for c in a100.components if c.is_bottleneck), "vision_encoder"
    )
    bottleneck_ms = next(
        (c.p50_ms for c in a100.components if c.is_bottleneck), 0
    )

    stacked_bar = _stacked_bar_svg(profiles, comp_names)
    donut = _donut_svg(a100, comp_names)

    # Hardware table rows
    table_rows = ""
    for p in profiles:
        bn = next((c.name.replace("_", " ") for c in p.components if c.is_bottleneck), "—")
        sla_cell = (
            '<span style="color:#4caf50;font-weight:bold">PASS</span>'
            if p.meets_200ms_sla
            else '<span style="color:#C74634;font-weight:bold">FAIL</span>'
        )
        table_rows += f"""
        <tr>
          <td>{HW_DISPLAY.get(p.hardware, p.hardware)}</td>
          <td>{p.total_p50:.1f} ms</td>
          <td>{p.total_p95:.1f} ms</td>
          <td>{p.total_p99:.1f} ms</td>
          <td>{sla_cell}</td>
          <td style="color:#f5c242">{bn}</td>
        </tr>"""

    # Optimization cards
    opt_cards = ""
    for hw, tips in OPTIMIZATION_TIPS.items():
        hw_label = HW_DISPLAY.get(hw, hw)
        hw_color = HW_COLORS.get(hw, "#C74634")
        items = "".join(
            f'<li><span style="color:#f5c242">{comp.replace("_"," ")}</span>: {tip}</li>'
            for comp, tip in tips
        )
        opt_cards += f"""
        <div class="opt-card">
          <h3 style="color:{hw_color};margin:0 0 8px 0">{hw_label}</h3>
          <ul style="margin:0;padding-left:18px;line-height:1.8">{items}</ul>
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <title>GR00T Latency Breakdown Profiler</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; }}
    body {{
      margin: 0; padding: 24px;
      background: #0f172a; color: #e2e8f0;
      font-family: 'Segoe UI', system-ui, sans-serif;
      font-size: 14px;
    }}
    h1 {{ color: #C74634; margin: 0 0 4px 0; font-size: 22px; }}
    .subtitle {{ color: #64748b; margin: 0 0 24px 0; font-size: 13px; }}
    .stat-grid {{
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 16px;
      margin-bottom: 28px;
    }}
    .stat-card {{
      background: #1e293b;
      border: 1px solid #334155;
      border-radius: 10px;
      padding: 16px 18px;
    }}
    .stat-label {{ color: #64748b; font-size: 11px; text-transform: uppercase; letter-spacing: .05em; }}
    .stat-value {{ color: #e2e8f0; font-size: 26px; font-weight: 700; margin: 6px 0 2px; }}
    .stat-sub {{ color: #94a3b8; font-size: 11px; }}
    .section {{ margin-bottom: 28px; }}
    .section-title {{
      color: #94a3b8;
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: .08em;
      margin: 0 0 10px 0;
      border-bottom: 1px solid #334155;
      padding-bottom: 6px;
    }}
    .charts {{ display: flex; gap: 20px; flex-wrap: wrap; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th {{
      background: #334155; color: #94a3b8;
      font-size: 11px; text-transform: uppercase; letter-spacing: .05em;
      padding: 10px 14px; text-align: left;
    }}
    td {{ padding: 10px 14px; border-bottom: 1px solid #1e293b; color: #e2e8f0; }}
    tr:hover td {{ background: #1e293b; }}
    .opt-grid {{
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 16px;
    }}
    .opt-card {{
      background: #1e293b;
      border: 1px solid #334155;
      border-radius: 8px;
      padding: 16px;
      font-size: 13px;
    }}
    .footer {{
      margin-top: 32px;
      color: #475569;
      font-size: 11px;
      text-align: center;
    }}
  </style>
</head>
<body>
  <h1>GR00T Inference Latency Breakdown</h1>
  <p class="subtitle">End-to-end profiling: image capture → robot action delivery &nbsp;|&nbsp;
     SLA target: {SLA_MS:.0f} ms p50 &nbsp;|&nbsp; {len(profiles)} hardware configs</p>

  <!-- Stat cards -->
  <div class="stat-grid">
    <div class="stat-card">
      <div class="stat-label">Fastest p50</div>
      <div class="stat-value" style="color:#4caf50">{report.fastest_p50_ms:.1f} ms</div>
      <div class="stat-sub">{HW_DISPLAY.get(report.best_hardware, report.best_hardware)}</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">SLA Compliance</div>
      <div class="stat-value" style="color:{'#4caf50' if sla_count == len(profiles) else '#C74634'}">{sla_count}/{len(profiles)}</div>
      <div class="stat-sub">hardware configs pass {SLA_MS:.0f}ms SLA</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">A100 Bottleneck</div>
      <div class="stat-value" style="color:#f5c242;font-size:18px">{bottleneck_comp.replace("_"," ")}</div>
      <div class="stat-sub">{bottleneck_ms:.1f} ms p50 ({next((c.pct_of_total for c in a100.components if c.name == bottleneck_comp), 0):.0f}% of total)</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Jetson / A100 Ratio</div>
      <div class="stat-value" style="color:#e07b2e">{ratio:.2f}x</div>
      <div class="stat-sub">slower on edge ({jetson.total_p50:.0f}ms vs {a100.total_p50:.0f}ms)</div>
    </div>
  </div>

  <!-- Stacked bar chart -->
  <div class="section">
    <div class="section-title">Component Latency — Stacked Bar (p50 ms)</div>
    {stacked_bar}
  </div>

  <!-- Donut + table -->
  <div class="section">
    <div class="section-title">OCI A100 Breakdown &amp; Hardware Comparison</div>
    <div class="charts">
      {donut}
      <div style="flex:1;min-width:340px">
        <table>
          <thead>
            <tr>
              <th>Hardware</th>
              <th>p50</th>
              <th>p95</th>
              <th>p99</th>
              <th>SLA</th>
              <th>Bottleneck</th>
            </tr>
          </thead>
          <tbody>{table_rows}</tbody>
        </table>
      </div>
    </div>
  </div>

  <!-- Optimization recommendations -->
  <div class="section">
    <div class="section-title">Optimization Recommendations</div>
    <div class="opt-grid">{opt_cards}</div>
  </div>

  <div class="footer">
    Generated by latency_breakdown_profiler.py &nbsp;|&nbsp;
    OCI Robot Cloud &nbsp;|&nbsp;
    {len(comp_names)} components profiled over {N_SAMPLES} simulated runs per hardware target
  </div>
</body>
</html>"""
    return html


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="GR00T end-to-end latency breakdown profiler"
    )
    parser.add_argument("--mock", action="store_true", default=True,
                        help="Use simulated latency data (always on for now)")
    parser.add_argument("--output", default="/tmp/latency_breakdown_profiler.html",
                        help="Path for the HTML report")
    parser.add_argument("--seed", type=int, default=42,
                        help="RNG seed for reproducible simulation")
    args = parser.parse_args()

    rng = random.Random(args.seed)

    print("Simulating latency profiles...")
    profiles = []
    for hw in HARDWARE_CONFIGS:
        profile = simulate_hardware(hw, rng)
        profiles.append(profile)
        sla_str = "PASS" if profile.meets_200ms_sla else "FAIL"
        print(f"  {HW_DISPLAY.get(hw, hw):<14} p50={profile.total_p50:.1f}ms  "
              f"p99={profile.total_p99:.1f}ms  SLA:{sla_str}")

    report = build_report(profiles)
    print_component_table(report)

    html = generate_html(report)
    with open(args.output, "w", encoding="utf-8") as fh:
        fh.write(html)
    print(f"HTML report written to: {args.output}")


if __name__ == "__main__":
    main()
