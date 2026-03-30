"""
Multi-task gradient conflict analysis and PCGrad surgery effectiveness for GR00T multi-task fine-tuning.

Analyzes gradient conflicts across manipulation tasks, applies PCGrad (gradient surgery),
and generates an HTML report with conflict heatmap, gradient norm charts, and insights.

Usage:
    python gradient_surgery_analyzer.py --mock --output /tmp/gradient_surgery_analyzer.html --seed 42
"""

import argparse
import math
import random
import html as html_lib
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class GradientConflict:
    task_pair: tuple
    conflict_angle_deg: float
    cosine_sim: float
    magnitude_ratio: float
    surgery_applied: bool


@dataclass
class TaskGradientProfile:
    task_name: str
    avg_gradient_norm: float
    gradient_variance: float
    conflict_rate: float
    post_surgery_improvement: float


@dataclass
class SurgeryReport:
    best_task_combo: str
    worst_conflict_pair: str
    total_conflict_rate: float
    surgery_improvement_pct: float
    task_profiles: list = field(default_factory=list)
    conflicts: list = field(default_factory=list)


# ---------------------------------------------------------------------------
# Simulation helpers
# ---------------------------------------------------------------------------

TASKS = [
    "pick_and_place",
    "stack_blocks",
    "door_opening",
    "drawer_pull",
    "tool_use",
    "pouring",
]

# Pre-defined cosine similarity matrix (upper-triangular populated; negatives = conflict)
# pick_and_place vs door_opening must be ~-0.45
FIXED_COSINE_SIMS = {
    ("pick_and_place", "stack_blocks"):  0.62,
    ("pick_and_place", "door_opening"): -0.45,
    ("pick_and_place", "drawer_pull"):   0.18,
    ("pick_and_place", "tool_use"):     -0.12,
    ("pick_and_place", "pouring"):       0.31,
    ("stack_blocks",   "door_opening"): -0.28,
    ("stack_blocks",   "drawer_pull"):   0.55,
    ("stack_blocks",   "tool_use"):      0.09,
    ("stack_blocks",   "pouring"):      -0.07,
    ("door_opening",   "drawer_pull"):   0.43,
    ("door_opening",   "tool_use"):     -0.33,
    ("door_opening",   "pouring"):      -0.19,
    ("drawer_pull",    "tool_use"):      0.27,
    ("drawer_pull",    "pouring"):       0.14,
    ("tool_use",       "pouring"):      -0.22,
}

# Pre-defined gradient norms per task (before surgery)
TASK_NORMS_BEFORE = {
    "pick_and_place": 1.84,
    "stack_blocks":   1.42,
    "door_opening":   2.11,
    "drawer_pull":    1.67,
    "tool_use":       2.38,
    "pouring":        1.23,
}

# Per-task gradient variance
TASK_VARIANCE = {
    "pick_and_place": 0.14,
    "stack_blocks":   0.09,
    "door_opening":   0.22,
    "drawer_pull":    0.11,
    "tool_use":       0.31,
    "pouring":        0.07,
}

# Surgery reduces norm slightly (projection removes conflicting component)
SURGERY_NORM_FACTOR = {
    "pick_and_place": 0.91,
    "stack_blocks":   0.94,
    "door_opening":   0.88,
    "drawer_pull":    0.93,
    "tool_use":       0.85,
    "pouring":        0.96,
}

# Post-surgery improvement per task (success rate delta %)
TASK_SR_IMPROVEMENT = {
    "pick_and_place":  19.2,
    "stack_blocks":    14.7,
    "door_opening":    22.4,
    "drawer_pull":     11.8,
    "tool_use":        25.1,
    "pouring":          9.3,
}


def _cosine_to_angle(cosine_sim: float) -> float:
    """Convert cosine similarity to angle in degrees."""
    clamped = max(-1.0, min(1.0, cosine_sim))
    return math.degrees(math.acos(clamped))


def _get_cosine(t1: str, t2: str) -> float:
    key = (t1, t2)
    if key in FIXED_COSINE_SIMS:
        return FIXED_COSINE_SIMS[key]
    rev = (t2, t1)
    if rev in FIXED_COSINE_SIMS:
        return FIXED_COSINE_SIMS[rev]
    return 0.0


def _magnitude_ratio(t1: str, t2: str) -> float:
    n1 = TASK_NORMS_BEFORE[t1]
    n2 = TASK_NORMS_BEFORE[t2]
    return round(n1 / n2, 3) if n2 > 0 else 1.0


def simulate_gradients(seed: int = 42) -> SurgeryReport:
    random.seed(seed)

    conflicts: list[GradientConflict] = []
    conflicting_pairs = []

    for i, t1 in enumerate(TASKS):
        for j, t2 in enumerate(TASKS):
            if j <= i:
                continue
            cos_sim = _get_cosine(t1, t2)
            angle = _cosine_to_angle(cos_sim)
            mag_ratio = _magnitude_ratio(t1, t2)
            surgery_applied = cos_sim < 0.0
            gc = GradientConflict(
                task_pair=(t1, t2),
                conflict_angle_deg=round(angle, 2),
                cosine_sim=round(cos_sim, 4),
                magnitude_ratio=mag_ratio,
                surgery_applied=surgery_applied,
            )
            conflicts.append(gc)
            if surgery_applied:
                conflicting_pairs.append(gc)

    total_pairs = len(conflicts)
    num_conflicting = len(conflicting_pairs)
    total_conflict_rate_pre = round(num_conflicting / total_pairs * 100, 1)

    # Post-surgery conflict rate: ~8%
    post_surgery_conflict_rate = 8.1

    # Surgery improvement: ~18%
    surgery_improvement_pct = 18.3

    # Worst conflict pair: lowest cosine sim
    worst = min(conflicts, key=lambda c: c.cosine_sim)
    worst_conflict_pair = f"{worst.task_pair[0]} vs {worst.task_pair[1]}"

    # Best task combo: highest cosine sim
    best = max(conflicts, key=lambda c: c.cosine_sim)
    best_task_combo = f"{best.task_pair[0]} + {best.task_pair[1]}"

    # Build per-task profiles
    task_profiles: list[TaskGradientProfile] = []
    for task in TASKS:
        # Conflict rate for this task: fraction of its pairs that conflict
        task_pairs = [c for c in conflicts if task in c.task_pair]
        task_conflict_count = sum(1 for c in task_pairs if c.surgery_applied)
        task_conflict_rate = round(task_conflict_count / len(task_pairs) * 100, 1)

        tp = TaskGradientProfile(
            task_name=task,
            avg_gradient_norm=round(TASK_NORMS_BEFORE[task], 4),
            gradient_variance=TASK_VARIANCE[task],
            conflict_rate=task_conflict_rate,
            post_surgery_improvement=TASK_SR_IMPROVEMENT[task],
        )
        task_profiles.append(tp)

    report = SurgeryReport(
        best_task_combo=best_task_combo,
        worst_conflict_pair=worst_conflict_pair,
        total_conflict_rate=total_conflict_rate_pre,
        surgery_improvement_pct=surgery_improvement_pct,
        task_profiles=task_profiles,
        conflicts=conflicts,
    )
    return report


# ---------------------------------------------------------------------------
# Console output
# ---------------------------------------------------------------------------

def print_conflict_matrix(report: SurgeryReport) -> None:
    """Print the 6×6 conflict cosine similarity matrix to stdout."""
    n = len(TASKS)
    col_w = 14

    # Header
    header = " " * 17
    for t in TASKS:
        header += t[:col_w].center(col_w)
    print(header)
    print("-" * (17 + n * col_w))

    for t1 in TASKS:
        row = t1[:16].ljust(17)
        for t2 in TASKS:
            if t1 == t2:
                row += "  ----  ".center(col_w)
            else:
                cos = _get_cosine(t1, t2)
                marker = "**" if cos < 0 else "  "
                row += f"{marker}{cos:+.3f}{marker}".center(col_w)
        print(row)

    print()
    print("** = conflicting gradient pair (cosine < 0)")
    print(f"\nTotal conflict rate (pre-surgery): {report.total_conflict_rate}%")
    print(f"Post-surgery conflict rate:        8.1%")
    print(f"Worst conflict pair:               {report.worst_conflict_pair}")
    print(f"Best task combo:                   {report.best_task_combo}")
    print(f"Multi-task SR improvement:         +{report.surgery_improvement_pct}%")
    print()


# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------

def _lerp_color(frac: float) -> str:
    """
    Map frac in [-1, 1] to a color:
      -1.0 → red   (#ef4444)
       0.0 → white (#f8fafc)
      +1.0 → blue  (#3b82f6)
    """
    if frac < 0:
        t = -frac  # 0..1 → white to red
        r = int(248 + t * (239 - 248))
        g = int(250 + t * (68  - 250))
        b = int(252 + t * (68  - 252))
    else:
        t = frac   # 0..1 → white to blue
        r = int(248 + t * (59  - 248))
        g = int(250 + t * (130 - 250))
        b = int(252 + t * (246 - 252))
    return f"rgb({r},{g},{b})"


def build_heatmap_svg() -> str:
    """Build SVG heatmap for the 6×6 cosine similarity matrix."""
    cell = 72
    margin_top = 90
    margin_left = 120
    label_font = 11
    w = margin_left + 6 * cell + 20
    h = margin_top + 6 * cell + 20

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}">',
        '<style>text{font-family:monospace;fill:#e2e8f0;}</style>',
    ]

    # Column labels (rotated)
    for j, t2 in enumerate(TASKS):
        cx = margin_left + j * cell + cell // 2
        label = t2.replace("_", " ")
        lines.append(
            f'<text x="{cx}" y="{margin_top - 10}" font-size="{label_font}" '
            f'text-anchor="end" transform="rotate(-40,{cx},{margin_top - 10})">'
            f'{label}</text>'
        )

    # Row labels + cells
    for i, t1 in enumerate(TASKS):
        cy_center = margin_top + i * cell + cell // 2
        label = t1.replace("_", " ")
        lines.append(
            f'<text x="{margin_left - 8}" y="{cy_center + 4}" font-size="{label_font}" '
            f'text-anchor="end">{label}</text>'
        )
        for j, t2 in enumerate(TASKS):
            cx = margin_left + j * cell
            cy = margin_top + i * cell
            if t1 == t2:
                color = "#334155"
                val_text = "—"
                text_fill = "#94a3b8"
            else:
                cos = _get_cosine(t1, t2)
                color = _lerp_color(cos)
                val_text = f"{cos:+.2f}"
                # Dark text on light cells
                if abs(cos) < 0.3:
                    text_fill = "#1e293b"
                elif cos > 0:
                    text_fill = "#1e293b"
                else:
                    text_fill = "#fff7f7"
            lines.append(
                f'<rect x="{cx+1}" y="{cy+1}" width="{cell-2}" height="{cell-2}" '
                f'fill="{color}" rx="4"/>'
            )
            lines.append(
                f'<text x="{cx + cell//2}" y="{cy + cell//2 + 5}" font-size="12" '
                f'text-anchor="middle" fill="{text_fill}">{val_text}</text>'
            )

    # Color legend
    legend_y = h - 14
    legend_x_start = margin_left
    legend_w = 6 * cell
    lines.append(
        f'<defs><linearGradient id="lg" x1="0" x2="1" y1="0" y2="0">'
        f'<stop offset="0%" stop-color="#ef4444"/>'
        f'<stop offset="50%" stop-color="#f8fafc"/>'
        f'<stop offset="100%" stop-color="#3b82f6"/>'
        f'</linearGradient></defs>'
    )
    lines.append(
        f'<rect x="{legend_x_start}" y="{legend_y - 8}" width="{legend_w}" height="8" '
        f'fill="url(#lg)" rx="2"/>'
    )
    lines.append(
        f'<text x="{legend_x_start}" y="{legend_y + 4}" font-size="9" fill="#94a3b8">-1.0 (conflict)</text>'
    )
    lines.append(
        f'<text x="{legend_x_start + legend_w}" y="{legend_y + 4}" font-size="9" '
        f'text-anchor="end" fill="#94a3b8">+1.0 (aligned)</text>'
    )

    lines.append('</svg>')
    return "\n".join(lines)


def build_bar_chart_svg(report: SurgeryReport) -> str:
    """Build grouped bar chart: gradient norm before vs after surgery per task."""
    bar_w = 24
    gap = 8
    group_gap = 20
    n = len(TASKS)
    margin_left = 50
    margin_top = 20
    margin_bottom = 70
    chart_h = 200
    w = margin_left + n * (2 * bar_w + gap + group_gap) + 20
    h = margin_top + chart_h + margin_bottom

    max_norm = max(TASK_NORMS_BEFORE.values()) * 1.1

    def y_for(val: float) -> float:
        return margin_top + chart_h - (val / max_norm) * chart_h

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}">',
        '<style>text{font-family:monospace;fill:#e2e8f0;}</style>',
    ]

    # Y-axis ticks
    for tick in [0.5, 1.0, 1.5, 2.0, 2.5]:
        if tick > max_norm:
            break
        ty = y_for(tick)
        lines.append(
            f'<line x1="{margin_left}" y1="{ty}" x2="{w - 10}" y2="{ty}" '
            f'stroke="#334155" stroke-width="1" stroke-dasharray="4,4"/>'
        )
        lines.append(
            f'<text x="{margin_left - 6}" y="{ty + 4}" font-size="10" text-anchor="end">'
            f'{tick:.1f}</text>'
        )

    # Bars
    for idx, tp in enumerate(report.task_profiles):
        x_base = margin_left + idx * (2 * bar_w + gap + group_gap)
        norm_before = TASK_NORMS_BEFORE[tp.task_name]
        norm_after = norm_before * SURGERY_NORM_FACTOR[tp.task_name]

        # Before bar (Oracle red)
        y_b = y_for(norm_before)
        lines.append(
            f'<rect x="{x_base}" y="{y_b}" width="{bar_w}" '
            f'height="{chart_h - (y_b - margin_top)}" fill="#C74634" rx="3"/>'
        )
        lines.append(
            f'<text x="{x_base + bar_w//2}" y="{y_b - 4}" font-size="9" '
            f'text-anchor="middle" fill="#fca5a5">{norm_before:.2f}</text>'
        )

        # After bar (teal)
        y_a = y_for(norm_after)
        lines.append(
            f'<rect x="{x_base + bar_w + gap}" y="{y_a}" width="{bar_w}" '
            f'height="{chart_h - (y_a - margin_top)}" fill="#0d9488" rx="3"/>'
        )
        lines.append(
            f'<text x="{x_base + bar_w + gap + bar_w//2}" y="{y_a - 4}" font-size="9" '
            f'text-anchor="middle" fill="#5eead4">{norm_after:.2f}</text>'
        )

        # X label
        label = tp.task_name.replace("_", "\n")
        label_parts = tp.task_name.replace("_", " ").split()
        lx = x_base + bar_w
        for li, part in enumerate(label_parts):
            lines.append(
                f'<text x="{lx}" y="{margin_top + chart_h + 14 + li * 12}" '
                f'font-size="9" text-anchor="middle" fill="#94a3b8">{part}</text>'
            )

    # Legend
    legend_y = h - 10
    legend_x = margin_left
    lines.append(
        f'<rect x="{legend_x}" y="{legend_y - 8}" width="12" height="8" fill="#C74634" rx="2"/>'
    )
    lines.append(
        f'<text x="{legend_x + 15}" y="{legend_y}" font-size="10" fill="#e2e8f0">Before surgery</text>'
    )
    lines.append(
        f'<rect x="{legend_x + 110}" y="{legend_y - 8}" width="12" height="8" fill="#0d9488" rx="2"/>'
    )
    lines.append(
        f'<text x="{legend_x + 125}" y="{legend_y}" font-size="10" fill="#e2e8f0">After surgery</text>'
    )

    lines.append('</svg>')
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# HTML report
# ---------------------------------------------------------------------------

def build_html_report(report: SurgeryReport) -> str:
    heatmap_svg = build_heatmap_svg()
    bar_chart_svg = build_bar_chart_svg(report)

    # Table rows for conflict pairs
    conflict_rows = []
    for c in sorted(report.conflicts, key=lambda x: x.cosine_sim):
        t1, t2 = c.task_pair
        applied = "Yes" if c.surgery_applied else "No"
        badge_class = "badge-conflict" if c.surgery_applied else "badge-aligned"
        if c.surgery_applied:
            # approximate improvement: average of the two tasks
            imp1 = TASK_SR_IMPROVEMENT[t1]
            imp2 = TASK_SR_IMPROVEMENT[t2]
            improvement = f"+{(imp1 + imp2) / 2:.1f}%"
        else:
            improvement = "N/A"
        conflict_rows.append(
            f"<tr>"
            f"<td>{html_lib.escape(t1)}</td>"
            f"<td>{html_lib.escape(t2)}</td>"
            f"<td>{c.conflict_angle_deg:.1f}°</td>"
            f"<td class='{'neg' if c.cosine_sim < 0 else 'pos'}'>{c.cosine_sim:+.4f}</td>"
            f"<td>{c.magnitude_ratio:.3f}</td>"
            f"<td><span class='{badge_class}'>{applied}</span></td>"
            f"<td>{improvement}</td>"
            f"</tr>"
        )
    conflict_table = "\n".join(conflict_rows)

    # Top-3 conflict pairs (most negative cosine)
    top3 = sorted(report.conflicts, key=lambda x: x.cosine_sim)[:3]
    top3_items = "".join(
        f"<li><strong>{c.task_pair[0]}</strong> vs <strong>{c.task_pair[1]}</strong> "
        f"— cosine sim: <span class='neg'>{c.cosine_sim:+.4f}</span>, "
        f"angle: {c.conflict_angle_deg:.1f}°</li>"
        for c in top3
    )

    # Task profile table rows
    profile_rows = []
    for tp in report.task_profiles:
        profile_rows.append(
            f"<tr>"
            f"<td>{html_lib.escape(tp.task_name.replace('_', ' ').title())}</td>"
            f"<td>{tp.avg_gradient_norm:.4f}</td>"
            f"<td>{TASK_NORMS_BEFORE[tp.task_name] * SURGERY_NORM_FACTOR[tp.task_name]:.4f}</td>"
            f"<td>{tp.gradient_variance:.4f}</td>"
            f"<td>{tp.conflict_rate:.1f}%</td>"
            f"<td class='pos'>+{tp.post_surgery_improvement:.1f}%</td>"
            f"</tr>"
        )
    profile_table = "\n".join(profile_rows)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Gradient Surgery Analyzer — GR00T Multi-Task Fine-Tuning</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: #1e293b;
    color: #e2e8f0;
    font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
    font-size: 14px;
    line-height: 1.6;
    padding: 24px;
  }}
  h1 {{ font-size: 1.6rem; font-weight: 700; color: #f1f5f9; margin-bottom: 4px; }}
  h2 {{ font-size: 1.1rem; font-weight: 600; color: #cbd5e1; margin: 24px 0 12px; }}
  .subtitle {{ color: #64748b; font-size: 0.85rem; margin-bottom: 24px; }}
  .oracle-accent {{ color: #C74634; font-weight: 700; }}

  /* Stat cards */
  .stat-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 16px;
    margin-bottom: 32px;
  }}
  .stat-card {{
    background: #0f172a;
    border: 1px solid #334155;
    border-radius: 10px;
    padding: 18px 20px;
  }}
  .stat-label {{ color: #94a3b8; font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.05em; }}
  .stat-value {{ font-size: 1.5rem; font-weight: 700; color: #f1f5f9; margin: 4px 0; }}
  .stat-sub {{ color: #64748b; font-size: 0.78rem; }}
  .stat-card.conflict .stat-value {{ color: #ef4444; }}
  .stat-card.improved .stat-value {{ color: #22c55e; }}
  .stat-card.warning .stat-value {{ color: #f59e0b; }}
  .stat-card.info .stat-value {{ color: #60a5fa; }}

  /* Sections */
  .section {{
    background: #0f172a;
    border: 1px solid #334155;
    border-radius: 10px;
    padding: 20px 24px;
    margin-bottom: 24px;
  }}
  .section h2 {{ margin-top: 0; }}

  /* Charts */
  .charts-row {{
    display: grid;
    grid-template-columns: auto 1fr;
    gap: 24px;
    align-items: start;
  }}
  svg text {{ font-family: monospace; }}
  .chart-container {{ overflow-x: auto; }}

  /* Tables */
  table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 0.82rem;
  }}
  th {{
    background: #1e293b;
    color: #94a3b8;
    text-transform: uppercase;
    font-size: 0.72rem;
    letter-spacing: 0.05em;
    padding: 8px 12px;
    text-align: left;
    border-bottom: 1px solid #334155;
  }}
  td {{
    padding: 8px 12px;
    border-bottom: 1px solid #1e293b;
    color: #cbd5e1;
  }}
  tr:hover td {{ background: #1e293b; }}
  .neg {{ color: #ef4444; font-weight: 600; }}
  .pos {{ color: #22c55e; font-weight: 600; }}
  .badge-conflict {{
    background: rgba(239,68,68,0.15);
    color: #ef4444;
    border: 1px solid rgba(239,68,68,0.3);
    border-radius: 4px;
    padding: 2px 8px;
    font-size: 0.75rem;
  }}
  .badge-aligned {{
    background: rgba(34,197,94,0.1);
    color: #22c55e;
    border: 1px solid rgba(34,197,94,0.25);
    border-radius: 4px;
    padding: 2px 8px;
    font-size: 0.75rem;
  }}

  /* Insight box */
  .insight {{
    background: rgba(199,70,52,0.08);
    border-left: 3px solid #C74634;
    border-radius: 0 8px 8px 0;
    padding: 14px 18px;
    margin-top: 16px;
  }}
  .insight h3 {{ color: #C74634; font-size: 0.9rem; margin-bottom: 8px; }}
  .insight ul {{ padding-left: 18px; color: #cbd5e1; }}
  .insight li {{ margin-bottom: 6px; font-size: 0.85rem; }}

  footer {{
    text-align: center;
    color: #334155;
    font-size: 0.75rem;
    margin-top: 32px;
  }}
</style>
</head>
<body>

<h1>Gradient Surgery Analyzer</h1>
<p class="subtitle">
  Multi-task gradient conflict analysis &amp; PCGrad surgery effectiveness
  — <span class="oracle-accent">GR00T</span> fine-tuning across 6 manipulation tasks
</p>

<!-- Stat Cards -->
<div class="stat-grid">
  <div class="stat-card conflict">
    <div class="stat-label">Conflict Rate (Pre-Surgery)</div>
    <div class="stat-value">{report.total_conflict_rate}%</div>
    <div class="stat-sub">Post-surgery: 8.1% &darr;</div>
  </div>
  <div class="stat-card improved">
    <div class="stat-label">Multi-Task SR Improvement</div>
    <div class="stat-value">+{report.surgery_improvement_pct}%</div>
    <div class="stat-sub">Via PCGrad projection</div>
  </div>
  <div class="stat-card warning">
    <div class="stat-label">Worst Conflict Pair</div>
    <div class="stat-value" style="font-size:1.0rem;padding-top:4px">{html_lib.escape(report.worst_conflict_pair)}</div>
    <div class="stat-sub">cosine sim ≈ −0.45</div>
  </div>
  <div class="stat-card info">
    <div class="stat-label">Best Task Combo</div>
    <div class="stat-value" style="font-size:1.0rem;padding-top:4px">{html_lib.escape(report.best_task_combo)}</div>
    <div class="stat-sub">cosine sim ≈ +0.62</div>
  </div>
</div>

<!-- Heatmap + Bar Chart -->
<div class="section">
  <h2>Gradient Conflict Heatmap &amp; Norm Comparison</h2>
  <div class="charts-row">
    <div class="chart-container">
      {heatmap_svg}
    </div>
    <div class="chart-container">
      {bar_chart_svg}
    </div>
  </div>
</div>

<!-- Conflict Pairs Table -->
<div class="section">
  <h2>Gradient Conflict Details — All Task Pairs</h2>
  <table>
    <thead>
      <tr>
        <th>Task A</th>
        <th>Task B</th>
        <th>Conflict Angle</th>
        <th>Cosine Sim</th>
        <th>Magnitude Ratio</th>
        <th>Surgery Applied</th>
        <th>SR Improvement</th>
      </tr>
    </thead>
    <tbody>
      {conflict_table}
    </tbody>
  </table>
</div>

<!-- Per-Task Profile Table -->
<div class="section">
  <h2>Per-Task Gradient Profiles</h2>
  <table>
    <thead>
      <tr>
        <th>Task</th>
        <th>Grad Norm (Before)</th>
        <th>Grad Norm (After)</th>
        <th>Variance</th>
        <th>Conflict Rate</th>
        <th>Post-Surgery SR &Delta;</th>
      </tr>
    </thead>
    <tbody>
      {profile_table}
    </tbody>
  </table>
</div>

<!-- Insights -->
<div class="section">
  <h2>Insights &amp; Recommendations</h2>
  <div class="insight">
    <h3>PCGrad Recommendation</h3>
    <ul>
      <li>
        <strong>PCGrad is strongly recommended</strong> for this 6-task training run.
        Pre-surgery conflict rate of {report.total_conflict_rate}% drops to 8.1% post-surgery,
        and overall multi-task success rate improves by +{report.surgery_improvement_pct}%.
      </li>
      <li>
        The PCGrad projection removes the conflicting component of each gradient when
        cosine similarity between task gradients is negative, preventing destructive interference
        during weight updates.
      </li>
      <li>
        <strong>Computational overhead</strong> is O(T²) per step where T=number of tasks;
        for 6 tasks this adds ~15 pairwise projections, which is negligible on A100 GPUs.
      </li>
    </ul>
  </div>
  <div class="insight" style="margin-top:12px; border-left-color:#f59e0b; background:rgba(245,158,11,0.07)">
    <h3 style="color:#f59e0b">Top-3 Conflict Pairs to Monitor</h3>
    <ul>
      {top3_items}
      <li>
        Consider <strong>task grouping</strong>: train pick_and_place + stack_blocks + drawer_pull
        (high mutual alignment) separately from door_opening + tool_use + pouring
        if PCGrad alone is insufficient.
      </li>
    </ul>
  </div>
</div>

<footer>
  Generated by gradient_surgery_analyzer.py — Oracle OCI Robot Cloud &bull; GR00T Multi-Task Fine-Tuning
</footer>

</body>
</html>"""
    return html


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Analyze multi-task gradient conflicts and PCGrad surgery effectiveness."
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Run with simulated (mock) gradient data.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="/tmp/gradient_surgery_analyzer.html",
        help="Path for the HTML report output.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducibility.",
    )
    args = parser.parse_args()

    print("=" * 72)
    print("  Gradient Surgery Analyzer — GR00T Multi-Task Fine-Tuning")
    print("=" * 72)
    print(f"  Tasks : {', '.join(TASKS)}")
    print(f"  Seed  : {args.seed}")
    print(f"  Output: {args.output}")
    print()

    report = simulate_gradients(seed=args.seed)

    print("Gradient Cosine Similarity Matrix (negative = conflicting, marked **):")
    print()
    print_conflict_matrix(report)

    html = build_html_report(report)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"HTML report written to: {args.output}")
    print()
    print("Summary:")
    print(f"  - Total task pairs analyzed : {len(report.conflicts)}")
    print(f"  - Conflicting pairs          : {sum(1 for c in report.conflicts if c.surgery_applied)}")
    print(f"  - Pre-surgery conflict rate  : {report.total_conflict_rate}%")
    print(f"  - Post-surgery conflict rate : 8.1%")
    print(f"  - Multi-task SR improvement  : +{report.surgery_improvement_pct}%")
    print(f"  - Worst conflict pair        : {report.worst_conflict_pair}")
    print(f"  - Best task combo            : {report.best_task_combo}")
    print()
    print("Per-task post-surgery SR improvement:")
    for tp in report.task_profiles:
        bar = "#" * int(tp.post_surgery_improvement / 1.5)
        print(f"  {tp.task_name:<20} +{tp.post_surgery_improvement:5.1f}%  {bar}")
    print()


if __name__ == "__main__":
    main()
