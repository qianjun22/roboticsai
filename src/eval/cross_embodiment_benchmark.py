#!/usr/bin/env python3
"""
cross_embodiment_benchmark.py

Benchmarks the same GR00T policy across multiple robot embodiments,
measuring zero-shot and few-shot transfer performance.
Key for OCI multi-embodiment value proposition.

Usage:
    python cross_embodiment_benchmark.py --mock --output /tmp/cross_embodiment_benchmark.html --seed 42
"""

import argparse
import math
import random
from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class EmbodimentResult:
    robot: str
    manufacturer: str
    dof: int
    zero_shot_sr: float
    fewshot_10demo_sr: float
    fewshot_50demo_sr: float
    fewshot_100demo_sr: float
    similarity_to_franka: float
    fine_tune_cost_usd: float
    inference_latency_ms: float
    recommended: bool = False


# ---------------------------------------------------------------------------
# Robot definitions
# ---------------------------------------------------------------------------

ROBOTS = [
    # (robot, manufacturer, dof, similarity_to_franka, base_latency_ms)
    ("Franka Research 3",  "Franka Robotics",  7, 1.00, 155),
    ("UR5e",               "Universal Robots",  6, 0.82, 170),
    ("xArm7",              "UFACTORY",          7, 0.88, 160),
    ("Kinova Gen3",        "Kinova",            7, 0.85, 175),
    ("Sawyer",             "Rethink Robotics",  7, 0.79, 195),
    ("KUKA iiwa",          "KUKA",              7, 0.76, 210),
    ("Spot Arm",           "Boston Dynamics",   6, 0.55, 290),
    ("Unitree Z1",         "Unitree Robotics",  6, 0.62, 265),
    ("AgileX Piper",       "AgileX Robotics",   6, 0.68, 240),
    ("Flexiv Rizon4",      "Flexiv",            7, 0.83, 185),
]

# Source (Franka) policy success rate baseline
SOURCE_SR = 0.72


# ---------------------------------------------------------------------------
# Simulation helpers
# ---------------------------------------------------------------------------

def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def simulate_transfer(
    robot_name: str,
    manufacturer: str,
    dof: int,
    similarity: float,
    base_latency_ms: float,
    seed: int = 42,
) -> EmbodimentResult:
    """Compute SR for each condition using deterministic noise seeded by robot name."""
    rng = random.Random(seed + hash(robot_name) % 10_000)

    def noise(scale: float = 0.04) -> float:
        return rng.gauss(0, scale)

    # zero-shot: limited — DAgger policy has little cross-embodiment generalisation
    zero_shot = _clamp(similarity * 0.52 + noise(0.05))

    # few-shot 10 demos: modest boost via sigmoid
    fewshot_10 = _clamp(zero_shot * 1.35 + _sigmoid((similarity - 0.7) * 6) * 0.08 + noise(0.04))

    # few-shot 50 demos
    fewshot_50 = _clamp(SOURCE_SR * similarity * 0.78 + noise(0.04))

    # few-shot 100 demos (best)
    fewshot_100 = _clamp(SOURCE_SR * similarity * 0.85 + noise(0.03))

    # fine-tune cost: fewer demos + lower similarity → cheaper (less useful signal)
    base_cost = 0.40
    cost = _clamp(base_cost * (0.5 + similarity) * (dof / 7.0) + rng.uniform(-0.03, 0.05),
                  lo=0.10, hi=1.50)

    # Inference latency: base + jitter
    latency = base_latency_ms + rng.gauss(0, 12)

    return EmbodimentResult(
        robot=robot_name,
        manufacturer=manufacturer,
        dof=dof,
        zero_shot_sr=round(zero_shot, 4),
        fewshot_10demo_sr=round(fewshot_10, 4),
        fewshot_50demo_sr=round(fewshot_50, 4),
        fewshot_100demo_sr=round(fewshot_100, 4),
        similarity_to_franka=similarity,
        fine_tune_cost_usd=round(cost, 4),
        inference_latency_ms=round(latency, 1),
    )


def run_benchmark(seed: int = 42) -> List[EmbodimentResult]:
    results = []
    for robot_name, mfr, dof, sim, latency in ROBOTS:
        r = simulate_transfer(robot_name, mfr, dof, sim, latency, seed=seed)
        results.append(r)
    # Mark Pareto-optimal robots
    pareto = find_pareto_frontier(results)
    pareto_names = {r.robot for r in pareto}
    for r in results:
        r.recommended = r.robot in pareto_names
    return results


# ---------------------------------------------------------------------------
# Pareto frontier
# ---------------------------------------------------------------------------

def find_pareto_frontier(results: List[EmbodimentResult]) -> List[EmbodimentResult]:
    """
    Find robots where no other robot dominates on BOTH:
      - higher fewshot_100demo_sr
      - lower fine_tune_cost_usd
    """
    pareto = []
    for candidate in results:
        dominated = False
        for other in results:
            if other is candidate:
                continue
            if (other.fewshot_100demo_sr >= candidate.fewshot_100demo_sr and
                    other.fine_tune_cost_usd <= candidate.fine_tune_cost_usd and
                    (other.fewshot_100demo_sr > candidate.fewshot_100demo_sr or
                     other.fine_tune_cost_usd < candidate.fine_tune_cost_usd)):
                dominated = True
                break
        if not dominated:
            pareto.append(candidate)
    return pareto


# ---------------------------------------------------------------------------
# HTML report
# ---------------------------------------------------------------------------

# Manufacturer color palette (kept consistent across scatter plot)
MFR_COLORS = {
    "Franka Robotics":    "#C74634",
    "Universal Robots":   "#3b82f6",
    "UFACTORY":           "#22c55e",
    "Kinova":             "#f59e0b",
    "Rethink Robotics":   "#a855f7",
    "KUKA":               "#ec4899",
    "Boston Dynamics":    "#14b8a6",
    "Unitree Robotics":   "#f97316",
    "AgileX Robotics":    "#6366f1",
    "Flexiv":             "#84cc16",
}


def _pct(v: float) -> str:
    return f"{v * 100:.1f}%"


def _build_grouped_bar_svg(results: List[EmbodimentResult]) -> str:
    """Grouped bar chart — 4 bars per robot, sorted by fewshot_100demo_sr."""
    sorted_r = sorted(results, key=lambda r: r.fewshot_100demo_sr)

    W, H = 860, 340
    pad_left, pad_bottom, pad_top, pad_right = 52, 80, 20, 20
    chart_w = W - pad_left - pad_right
    chart_h = H - pad_bottom - pad_top

    n_robots = len(sorted_r)
    group_w = chart_w / n_robots
    bar_gap = 2
    bar_w = (group_w - bar_gap * 5) / 4

    colors = ["#94a3b8", "#3b82f6", "#22c55e", "#C74634"]
    labels = ["Zero-shot", "10-demo", "50-demo", "100-demo"]

    def y_pos(sr: float) -> float:
        return pad_top + chart_h * (1 - sr)

    lines = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
             f'style="background:#1e293b;border-radius:8px">']

    # Y-axis gridlines
    for pct in [0.2, 0.4, 0.6, 0.8, 1.0]:
        yy = y_pos(pct)
        lines.append(f'<line x1="{pad_left}" y1="{yy:.1f}" x2="{W - pad_right}" y2="{yy:.1f}" '
                     f'stroke="#334155" stroke-width="1"/>')
        lines.append(f'<text x="{pad_left - 4}" y="{yy + 4:.1f}" fill="#94a3b8" font-size="10" '
                     f'text-anchor="end">{int(pct * 100)}%</text>')

    # Bars
    for i, r in enumerate(sorted_r):
        srs = [r.zero_shot_sr, r.fewshot_10demo_sr, r.fewshot_50demo_sr, r.fewshot_100demo_sr]
        group_x = pad_left + i * group_w + bar_gap
        for j, (sr, color) in enumerate(zip(srs, colors)):
            bx = group_x + j * (bar_w + bar_gap)
            bh = chart_h * sr
            by = pad_top + chart_h - bh
            lines.append(f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bar_w:.1f}" height="{bh:.1f}" '
                         f'fill="{color}" rx="2"/>')
            if sr >= 0.08:
                lines.append(f'<text x="{bx + bar_w / 2:.1f}" y="{by - 2:.1f}" fill="#f1f5f9" '
                             f'font-size="8" text-anchor="middle">{int(sr * 100)}</text>')

        # Robot label (rotated)
        lx = group_x + group_w / 2 - bar_gap
        ly = H - pad_bottom + 10
        name = r.robot.replace("Research ", "R").replace("Rizon", "Rz")
        lines.append(f'<text x="{lx:.1f}" y="{ly}" fill="#94a3b8" font-size="9" '
                     f'text-anchor="end" transform="rotate(-35 {lx:.1f} {ly})">{name}</text>')

    # Legend
    legend_x = pad_left + 10
    legend_y = pad_top + 8
    for j, (color, label) in enumerate(zip(colors, labels)):
        lx = legend_x + j * 120
        lines.append(f'<rect x="{lx}" y="{legend_y}" width="12" height="12" fill="{color}" rx="2"/>')
        lines.append(f'<text x="{lx + 15}" y="{legend_y + 10}" fill="#cbd5e1" font-size="11">{label}</text>')

    lines.append('</svg>')
    return "\n".join(lines)


def _build_scatter_svg(results: List[EmbodimentResult]) -> str:
    """Scatter plot: cost (x) vs fewshot_100demo_sr (y) with Pareto frontier."""
    W, H = 560, 340
    pad_left, pad_bottom, pad_top, pad_right = 55, 50, 20, 120

    chart_w = W - pad_left - pad_right
    chart_h = H - pad_bottom - pad_top

    costs = [r.fine_tune_cost_usd for r in results]
    min_cost, max_cost = min(costs) * 0.9, max(costs) * 1.1

    def sx(cost: float) -> float:
        return pad_left + (cost - min_cost) / (max_cost - min_cost) * chart_w

    def sy(sr: float) -> float:
        return pad_top + chart_h * (1 - sr)

    lines = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
             f'style="background:#1e293b;border-radius:8px">']

    # Gridlines
    for pct in [0.2, 0.4, 0.6, 0.8, 1.0]:
        yy = sy(pct)
        lines.append(f'<line x1="{pad_left}" y1="{yy:.1f}" x2="{W - pad_right}" y2="{yy:.1f}" '
                     f'stroke="#334155" stroke-width="1"/>')
        lines.append(f'<text x="{pad_left - 4}" y="{yy + 4:.1f}" fill="#94a3b8" font-size="10" '
                     f'text-anchor="end">{int(pct * 100)}%</text>')

    # X-axis labels
    for cost_tick in [0.2, 0.4, 0.6, 0.8, 1.0, 1.2]:
        if min_cost <= cost_tick <= max_cost:
            xx = sx(cost_tick)
            lines.append(f'<text x="{xx:.1f}" y="{H - pad_bottom + 14}" fill="#94a3b8" '
                         f'font-size="10" text-anchor="middle">${cost_tick:.1f}</text>')

    # Axis labels
    lines.append(f'<text x="{pad_left + chart_w / 2}" y="{H - 4}" fill="#94a3b8" font-size="11" '
                 f'text-anchor="middle">Fine-tune Cost (USD / 100 demos)</text>')
    lines.append(f'<text x="12" y="{pad_top + chart_h / 2}" fill="#94a3b8" font-size="11" '
                 f'text-anchor="middle" transform="rotate(-90 12 {pad_top + chart_h / 2:.0f})">'
                 f'100-Demo SR</text>')

    # Pareto frontier (sorted by cost)
    pareto = [r for r in results if r.recommended]
    pareto_sorted = sorted(pareto, key=lambda r: r.fine_tune_cost_usd)
    if len(pareto_sorted) > 1:
        pts = " ".join(f"{sx(r.fine_tune_cost_usd):.1f},{sy(r.fewshot_100demo_sr):.1f}"
                       for r in pareto_sorted)
        lines.append(f'<polyline points="{pts}" fill="none" stroke="#C74634" '
                     f'stroke-width="2" stroke-dasharray="6 3"/>')

    # Points
    for r in results:
        cx = sx(r.fine_tune_cost_usd)
        cy = sy(r.fewshot_100demo_sr)
        color = MFR_COLORS.get(r.manufacturer, "#94a3b8")
        stroke = "#ffffff" if r.recommended else "none"
        sw = 2 if r.recommended else 0
        lines.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="7" fill="{color}" '
                     f'stroke="{stroke}" stroke-width="{sw}"/>')
        lines.append(f'<title>{r.robot}: SR={_pct(r.fewshot_100demo_sr)}, '
                     f'cost=${r.fine_tune_cost_usd:.3f}</title>')

    # Legend (manufacturer)
    legend_y = pad_top
    seen = {}
    for r in results:
        if r.manufacturer not in seen:
            seen[r.manufacturer] = MFR_COLORS.get(r.manufacturer, "#94a3b8")
    for idx, (mfr, color) in enumerate(seen.items()):
        lx = W - pad_right + 8
        ly = legend_y + idx * 18
        lines.append(f'<circle cx="{lx + 6}" cy="{ly + 6}" r="5" fill="{color}"/>')
        short = mfr.replace(" Robotics", "").replace(" Robots", "")
        lines.append(f'<text x="{lx + 14}" y="{ly + 10}" fill="#cbd5e1" font-size="9">{short}</text>')

    lines.append('</svg>')
    return "\n".join(lines)


def generate_html_report(results: List[EmbodimentResult], seed: int) -> str:
    total = len(results)
    avg_zero = sum(r.zero_shot_sr for r in results) / total
    best_fewshot = max(r.fewshot_100demo_sr for r in results)
    n_pareto = sum(1 for r in results if r.recommended)

    bar_svg = _build_grouped_bar_svg(results)
    scatter_svg = _build_scatter_svg(results)

    # Table rows sorted by fewshot_100demo_sr desc
    sorted_results = sorted(results, key=lambda r: r.fewshot_100demo_sr, reverse=True)
    table_rows = []
    for r in sorted_results:
        star = "★" if r.recommended else ""
        row_bg = "#1e3a4a" if r.recommended else ""
        style = f' style="background:{row_bg}"' if row_bg else ""
        table_rows.append(
            f"<tr{style}>"
            f"<td>{star} {r.robot}</td>"
            f"<td>{r.manufacturer}</td>"
            f"<td>{r.dof}</td>"
            f"<td>{_pct(r.zero_shot_sr)}</td>"
            f"<td>{_pct(r.fewshot_10demo_sr)}</td>"
            f"<td>{_pct(r.fewshot_50demo_sr)}</td>"
            f"<td><strong>{_pct(r.fewshot_100demo_sr)}</strong></td>"
            f"<td>{r.similarity_to_franka:.2f}</td>"
            f"<td>${r.fine_tune_cost_usd:.3f}</td>"
            f"<td>{r.inference_latency_ms:.0f} ms</td>"
            f"</tr>"
        )
    table_html = "\n".join(table_rows)

    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<title>OCI Robot Cloud — Cross-Embodiment Benchmark</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #0f172a; color: #e2e8f0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; padding: 24px; }}
  h1 {{ color: #C74634; font-size: 1.6rem; margin-bottom: 4px; }}
  .subtitle {{ color: #94a3b8; font-size: 0.9rem; margin-bottom: 24px; }}
  .kpi-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 32px; }}
  .kpi {{ background: #1e293b; border-radius: 10px; padding: 20px; border-left: 4px solid #C74634; }}
  .kpi-label {{ color: #94a3b8; font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 6px; }}
  .kpi-value {{ color: #f1f5f9; font-size: 2rem; font-weight: 700; }}
  .kpi-sub {{ color: #64748b; font-size: 0.78rem; margin-top: 4px; }}
  .section {{ margin-bottom: 36px; }}
  h2 {{ color: #C74634; font-size: 1.1rem; margin-bottom: 12px; border-bottom: 1px solid #334155; padding-bottom: 6px; }}
  .charts {{ display: grid; grid-template-columns: 1fr auto; gap: 24px; align-items: start; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.82rem; }}
  th {{ background: #1e293b; color: #94a3b8; text-transform: uppercase; font-size: 0.72rem; letter-spacing: 0.04em; padding: 10px 8px; text-align: left; border-bottom: 2px solid #334155; }}
  td {{ padding: 9px 8px; border-bottom: 1px solid #1e293b; }}
  tr:hover td {{ background: #1e293b; }}
  .badge {{ display: inline-block; background: #C74634; color: white; border-radius: 4px; padding: 1px 6px; font-size: 0.7rem; margin-left: 4px; }}
  footer {{ color: #475569; font-size: 0.75rem; margin-top: 32px; text-align: center; }}
</style>
</head>
<body>
<h1>OCI Robot Cloud — Cross-Embodiment Benchmark</h1>
<p class="subtitle">GR00T N1.6 policy transfer: zero-shot vs. few-shot across {total} robot embodiments &nbsp;|&nbsp; Source: Franka Research 3 &nbsp;|&nbsp; Seed: {seed} &nbsp;|&nbsp; Generated: {now}</p>

<div class="kpi-grid">
  <div class="kpi">
    <div class="kpi-label">Total Embodiments</div>
    <div class="kpi-value">{total}</div>
    <div class="kpi-sub">7 arm manufacturers</div>
  </div>
  <div class="kpi">
    <div class="kpi-label">Avg Zero-Shot SR</div>
    <div class="kpi-value">{_pct(avg_zero)}</div>
    <div class="kpi-sub">No adaptation required</div>
  </div>
  <div class="kpi">
    <div class="kpi-label">Best 100-Demo SR</div>
    <div class="kpi-value">{_pct(best_fewshot)}</div>
    <div class="kpi-sub">Top performer (few-shot)</div>
  </div>
  <div class="kpi">
    <div class="kpi-label">Pareto Optimal</div>
    <div class="kpi-value">{n_pareto}</div>
    <div class="kpi-sub">Recommended for deployment</div>
  </div>
</div>

<div class="section">
  <h2>Transfer Performance by Embodiment</h2>
  <p style="color:#64748b;font-size:0.78rem;margin-bottom:10px">Grouped bars show success rate per shot condition, sorted by 100-demo SR. Numbers inside bars = integer SR%.</p>
  {bar_svg}
</div>

<div class="section">
  <h2>Cost vs. Performance (100-Demo Fine-Tuning)</h2>
  <p style="color:#64748b;font-size:0.78rem;margin-bottom:10px">Each point = one robot embodiment. White ring = Pareto-optimal (recommended). Dashed line = Pareto frontier.</p>
  <div class="charts">
    {scatter_svg}
    <div style="background:#1e293b;border-radius:8px;padding:16px;min-width:200px">
      <div style="color:#C74634;font-weight:700;margin-bottom:12px">Pareto-Optimal Robots</div>
      {"".join(f'<div style="margin-bottom:8px;padding:8px;background:#0f172a;border-radius:6px"><span style="color:#f1f5f9;font-size:0.85rem">{r.robot}</span><br/><span style="color:#64748b;font-size:0.75rem">{_pct(r.fewshot_100demo_sr)} SR &bull; ${r.fine_tune_cost_usd:.3f}</span></div>' for r in sorted(find_pareto_frontier(results), key=lambda x: x.fewshot_100demo_sr, reverse=True))}
    </div>
  </div>
</div>

<div class="section">
  <h2>Full Results Table</h2>
  <table>
    <thead>
      <tr>
        <th>Robot</th><th>Manufacturer</th><th>DoF</th>
        <th>Zero-Shot SR</th><th>10-Demo SR</th><th>50-Demo SR</th><th>100-Demo SR</th>
        <th>Similarity</th><th>Cost (USD)</th><th>Latency</th>
      </tr>
    </thead>
    <tbody>
      {table_html}
    </tbody>
  </table>
  <p style="color:#475569;font-size:0.75rem;margin-top:8px">★ = Pareto-optimal (no other robot dominates on both SR and cost). Highlighted rows recommended for production deployment.</p>
</div>

<footer>OCI Robot Cloud &nbsp;|&nbsp; Cross-Embodiment Benchmark v1.0 &nbsp;|&nbsp; Oracle Confidential</footer>
</body>
</html>"""


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Cross-embodiment benchmark for GR00T policy transfer"
    )
    parser.add_argument("--mock", action="store_true",
                        help="Use simulated (mock) data — no live inference required")
    parser.add_argument("--output", default="/tmp/cross_embodiment_benchmark.html",
                        help="Output HTML file path (default: /tmp/cross_embodiment_benchmark.html)")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed for reproducible noise (default: 42)")
    args = parser.parse_args()

    if not args.mock:
        print("[INFO] --mock not specified; only simulated data is available in this release.")
        print("       Proceeding with simulation (seed={}).".format(args.seed))

    print(f"[INFO] Running cross-embodiment benchmark (seed={args.seed}) ...")
    results = run_benchmark(seed=args.seed)

    print(f"\n{'Robot':<22} {'Zero-Shot':>10} {'10-Demo':>8} {'50-Demo':>8} {'100-Demo':>9} "
          f"{'Cost':>8} {'Latency':>9} {'Pareto':>7}")
    print("-" * 90)
    for r in sorted(results, key=lambda x: x.fewshot_100demo_sr, reverse=True):
        star = "★" if r.recommended else " "
        print(f"{r.robot:<22} {_pct(r.zero_shot_sr):>10} {_pct(r.fewshot_10demo_sr):>8} "
              f"{_pct(r.fewshot_50demo_sr):>8} {_pct(r.fewshot_100demo_sr):>9} "
              f"${r.fine_tune_cost_usd:>6.3f} {r.inference_latency_ms:>7.0f}ms  {star}")

    pareto = find_pareto_frontier(results)
    print(f"\n[INFO] Pareto-optimal ({len(pareto)}): {', '.join(r.robot for r in pareto)}")

    html = generate_html_report(results, seed=args.seed)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[INFO] Report saved → {args.output}")


if __name__ == "__main__":
    main()
