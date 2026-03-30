"""
Robot arm workspace reachability and collision-free region mapping.
Helps select optimal arm for task geometry.
"""

from __future__ import annotations

import argparse
import math
import random
import sys
from dataclasses import dataclass, field
from typing import List


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class WorkspaceCell:
    x: float
    y: float
    z: float
    reachable: bool
    collision_free: bool
    ik_success_rate: float
    avg_manipulability: float


@dataclass
class ArmProfile:
    arm_name: str
    n_joints: int
    reach_radius_m: float
    reachable_volume_m3: float
    collision_free_pct: float
    avg_ik_success_rate: float
    avg_manipulability: float
    dead_zones: int


@dataclass
class WorkspaceReport:
    best_arm: str
    most_collision_free: str
    results: List[ArmProfile] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Arm definitions
# ---------------------------------------------------------------------------

ARM_SPECS = {
    "franka_panda": {
        "n_joints": 7,
        "reach_radius_m": 0.85,
        # biases (all relative to unit sphere)
        "front_bias": 1.05,     # slight preference for front quadrant
        "collision_base_rate": 0.14,  # % of reachable cells that have collisions
        "ik_range": (0.80, 0.95),
        "manip_range": (0.55, 0.90),  # best manipulability up close
        "close_range_manip_boost": True,
    },
    "ur5e": {
        "n_joints": 6,
        "reach_radius_m": 0.85,
        "front_bias": 1.00,
        "collision_base_rate": 0.18,
        "ik_range": (0.75, 0.92),
        "manip_range": (0.45, 0.85),
        "close_range_manip_boost": False,
    },
    "kinova_gen3": {
        "n_joints": 7,
        "reach_radius_m": 0.90,
        "front_bias": 1.02,
        "collision_base_rate": 0.08,   # most collision-free (~82% CF = ~18% not)
        "ik_range": (0.78, 0.93),
        "manip_range": (0.48, 0.87),
        "close_range_manip_boost": False,
    },
    "xarm7": {
        "n_joints": 7,
        "reach_radius_m": 0.70,
        "front_bias": 1.03,
        "collision_base_rate": 0.22,
        "ik_range": (0.70, 0.88),
        "manip_range": (0.40, 0.82),
        "close_range_manip_boost": False,
    },
}

# Grid definition: 10×10×5 = 500 cells
GRID_X = [round(-0.5 + i * 0.5 / 4.5, 6) for i in range(10)]   # -0.50 … 0.50 (10 pts)
GRID_Y = [round(-0.5 + i * 0.5 / 4.5, 6) for i in range(10)]
GRID_Z = [round(0.0  + i * 0.8 / 4.0, 6) for i in range(5)]    #  0.00 … 0.80 (5 pts)

CELL_VOLUME = (GRID_X[1] - GRID_X[0]) * (GRID_Y[1] - GRID_Y[0]) * (GRID_Z[1] - GRID_Z[0])


# ---------------------------------------------------------------------------
# Simulation helpers
# ---------------------------------------------------------------------------

def _rand_range(rng: random.Random, lo: float, hi: float) -> float:
    return lo + rng.random() * (hi - lo)


def simulate_arm(arm_name: str, specs: dict, rng: random.Random) -> tuple[List[WorkspaceCell], ArmProfile]:
    """Generate workspace cells and compute aggregate profile for one arm."""
    cells: List[WorkspaceCell] = []
    reach = specs["reach_radius_m"]
    reach_sq = reach ** 2

    reachable_cells: List[WorkspaceCell] = []

    for z in GRID_Z:
        for y in GRID_Y:
            for x in GRID_X:
                dist_sq = x * x + y * y + z * z
                dist = math.sqrt(dist_sq)

                # --- Reachability ---
                # Sphere check with arm-specific front bias (y>0 is "front")
                bias = specs["front_bias"] if y >= 0 else 1.0
                effective_reach_sq = (reach * bias) ** 2

                # Exclude zone very close to base (< 0.08m) — singularity dead zone
                too_close = dist < 0.08

                # Exclude above-head zone for UR5e (elbow-up limit)
                elbow_limit = (arm_name == "ur5e" and z > 0.7 and abs(x) < 0.15 and abs(y) < 0.15)

                reachable = (not too_close) and (not elbow_limit) and (dist_sq <= effective_reach_sq)

                # Small probabilistic jitter for realism
                if reachable and rng.random() < 0.03:
                    reachable = False
                if (not reachable) and dist_sq <= effective_reach_sq * 0.85 and not too_close and rng.random() < 0.04:
                    reachable = True

                # --- Collision free ---
                collision_free = False
                ik_success = 0.0
                manip = 0.0

                if reachable:
                    # Collision probability increases at extremes of workspace
                    norm_dist = dist / reach  # 0 .. ~1.1
                    edge_factor = max(0.0, norm_dist - 0.65) / 0.35  # ramps up after 65% reach
                    p_collision = specs["collision_base_rate"] + 0.18 * edge_factor * edge_factor
                    collision_free = rng.random() > p_collision

                    # IK success: higher near centre, lower at extremes
                    ik_lo, ik_hi = specs["ik_range"]
                    ik_base = _rand_range(rng, ik_lo, ik_hi)
                    ik_edge_penalty = 0.12 * edge_factor
                    ik_success = max(0.40, min(0.99, ik_base - ik_edge_penalty))

                    # Manipulability: franka best close-range
                    m_lo, m_hi = specs["manip_range"]
                    if specs["close_range_manip_boost"] and norm_dist < 0.5:
                        m_hi = min(1.0, m_hi + 0.08)
                    manip = _rand_range(rng, m_lo, m_hi) * max(0.5, 1.0 - 0.5 * edge_factor)

                cell = WorkspaceCell(
                    x=x, y=y, z=z,
                    reachable=reachable,
                    collision_free=(reachable and collision_free),
                    ik_success_rate=ik_success,
                    avg_manipulability=manip,
                )
                cells.append(cell)
                if reachable:
                    reachable_cells.append(cell)

    # --- Aggregate metrics ---
    n_total = len(cells)
    n_reachable = sum(1 for c in cells if c.reachable)
    n_cf = sum(1 for c in cells if c.reachable and c.collision_free)

    reachable_volume = n_reachable * CELL_VOLUME
    cf_pct = (n_cf / n_reachable * 100.0) if n_reachable > 0 else 0.0

    avg_ik = (sum(c.ik_success_rate for c in reachable_cells) / len(reachable_cells)
              if reachable_cells else 0.0)
    avg_manip = (sum(c.avg_manipulability for c in reachable_cells) / len(reachable_cells)
                 if reachable_cells else 0.0)

    # Dead zones: cells that are geometrically inside reach sphere but unreachable
    dead_zones = sum(
        1 for c in cells
        if (not c.reachable) and (c.x**2 + c.y**2 + c.z**2 <= (reach * 0.85)**2)
    )

    profile = ArmProfile(
        arm_name=arm_name,
        n_joints=specs["n_joints"],
        reach_radius_m=reach,
        reachable_volume_m3=round(reachable_volume, 4),
        collision_free_pct=round(cf_pct, 2),
        avg_ik_success_rate=round(avg_ik, 4),
        avg_manipulability=round(avg_manip, 4),
        dead_zones=dead_zones,
    )

    return cells, profile


def run_simulation(seed: int = 42) -> tuple[dict[str, List[WorkspaceCell]], WorkspaceReport]:
    """Run simulation for all arms and produce a WorkspaceReport."""
    rng = random.Random(seed)
    all_cells: dict[str, List[WorkspaceCell]] = {}
    profiles: List[ArmProfile] = []

    for arm_name, specs in ARM_SPECS.items():
        cells, profile = simulate_arm(arm_name, specs, rng)
        all_cells[arm_name] = cells
        profiles.append(profile)

    # Rank: best overall = highest score combining volume + CF + IK
    def overall_score(p: ArmProfile) -> float:
        return p.reachable_volume_m3 * 0.4 + p.collision_free_pct * 0.01 * 0.35 + p.avg_ik_success_rate * 0.25

    best = max(profiles, key=overall_score)
    most_cf = max(profiles, key=lambda p: p.collision_free_pct)

    report = WorkspaceReport(
        best_arm=best.arm_name,
        most_collision_free=most_cf.arm_name,
        results=profiles,
    )
    return all_cells, report


# ---------------------------------------------------------------------------
# CLI table printer
# ---------------------------------------------------------------------------

def print_table(report: WorkspaceReport) -> None:
    cols = ["Arm", "Joints", "Reach(m)", "Volume(m³)", "CF%", "IK Succ", "Manip", "DeadZones"]
    widths = [16, 7, 9, 11, 8, 9, 8, 10]

    header = "  ".join(f"{c:<{w}}" for c, w in zip(cols, widths))
    sep = "  ".join("-" * w for w in widths)

    print("\n" + "=" * len(header))
    print("  Robot Arm Workspace Comparison")
    print("=" * len(header))
    print(header)
    print(sep)

    for p in report.results:
        marker = " *" if p.arm_name == report.best_arm else "  "
        row = [
            p.arm_name + marker,
            str(p.n_joints),
            f"{p.reach_radius_m:.2f}",
            f"{p.reachable_volume_m3:.4f}",
            f"{p.collision_free_pct:.1f}",
            f"{p.avg_ik_success_rate:.3f}",
            f"{p.avg_manipulability:.3f}",
            str(p.dead_zones),
        ]
        print("  ".join(f"{v:<{w}}" for v, w in zip(row, widths)))

    print(sep)
    print(f"  * Best overall arm: {report.best_arm}")
    print(f"  Most collision-free: {report.most_collision_free}")
    print()


# ---------------------------------------------------------------------------
# HTML report
# ---------------------------------------------------------------------------

# Cell size and layout for SVG workspace maps
SVG_CELL_PX = 32
SVG_PADDING = 36
N_X = len(GRID_X)   # 10
N_Y = len(GRID_Y)   # 10

SVG_W = N_X * SVG_CELL_PX + SVG_PADDING * 2
SVG_H = N_Y * SVG_CELL_PX + SVG_PADDING * 2 + 18  # +18 for title


def _cell_color(reachable: bool, collision_free: bool) -> str:
    if not reachable:
        return "#334155"          # gray — unreachable
    if reachable and collision_free:
        return "#22c55e"          # green — reachable + CF
    return "#f59e0b"              # yellow — reachable but collision risk


def _build_workspace_svg(arm_name: str, cells: List[WorkspaceCell]) -> str:
    """2D top-view (x-y plane) at z ≈ 0.5m (index 3 out of 0-4)."""
    z_slice = GRID_Z[3]  # z=0.6m approx
    slice_cells = {(round(c.x, 6), round(c.y, 6)): c
                   for c in cells if abs(c.z - z_slice) < 1e-4}

    rects = []
    for iy, y in enumerate(GRID_Y):
        for ix, x in enumerate(GRID_X):
            c = slice_cells.get((round(x, 6), round(y, 6)))
            if c is None:
                color = "#1e293b"
            else:
                color = _cell_color(c.reachable, c.collision_free)
            px = SVG_PADDING + ix * SVG_CELL_PX
            py = SVG_PADDING + (N_Y - 1 - iy) * SVG_CELL_PX + 18  # flip Y; offset for title
            rects.append(
                f'<rect x="{px}" y="{py}" width="{SVG_CELL_PX-1}" height="{SVG_CELL_PX-1}" '
                f'fill="{color}" rx="2"/>'
            )

    # Axis labels
    x_labels = []
    for ix, x in enumerate(GRID_X):
        if ix % 3 == 0:
            px = SVG_PADDING + ix * SVG_CELL_PX + SVG_CELL_PX // 2
            x_labels.append(
                f'<text x="{px}" y="{SVG_H - 4}" fill="#94a3b8" font-size="9" text-anchor="middle">{x:.1f}</text>'
            )

    y_labels = []
    for iy, y in enumerate(GRID_Y):
        if iy % 3 == 0:
            py = SVG_PADDING + (N_Y - 1 - iy) * SVG_CELL_PX + SVG_CELL_PX // 2 + 4 + 18
            y_labels.append(
                f'<text x="{SVG_PADDING - 4}" y="{py}" fill="#94a3b8" font-size="9" text-anchor="end">{y:.1f}</text>'
            )

    title = (f'<text x="{SVG_W//2}" y="13" fill="#e2e8f0" font-size="11" '
             f'font-weight="bold" text-anchor="middle">{arm_name}</text>')

    svg = (
        f'<svg width="{SVG_W}" height="{SVG_H}" xmlns="http://www.w3.org/2000/svg" '
        f'style="background:#0f172a;border-radius:6px;">'
        + title
        + "".join(rects)
        + "".join(x_labels)
        + "".join(y_labels)
        + "</svg>"
    )
    return svg


def _build_bar_chart(profiles: List[ArmProfile]) -> str:
    """Three grouped bars per arm: volume (normalised), CF%, IK success."""
    arm_names = [p.arm_name for p in profiles]
    n_arms = len(arm_names)

    chart_w = 580
    chart_h = 220
    pad_l, pad_r, pad_t, pad_b = 48, 20, 20, 50
    plot_w = chart_w - pad_l - pad_r
    plot_h = chart_h - pad_t - pad_b

    max_val = 100.0  # percentages
    bar_group_w = plot_w / n_arms
    bar_w = bar_group_w / 5  # 3 bars + 2 gaps

    colors = ["#3b82f6", "#22c55e", "#f59e0b"]
    series = ["Volume%", "CF%", "IK%"]

    max_volume = max(p.reachable_volume_m3 for p in profiles)

    def pct(p: ArmProfile, idx: int) -> float:
        if idx == 0:
            return (p.reachable_volume_m3 / max_volume) * 100.0
        if idx == 1:
            return p.collision_free_pct
        return p.avg_ik_success_rate * 100.0

    rects = []
    labels = []
    for ai, p in enumerate(profiles):
        gx = pad_l + ai * bar_group_w
        for si in range(3):
            v = pct(p, si)
            bh = v / max_val * plot_h
            bx = gx + (si + 0.75) * bar_w
            by = pad_t + plot_h - bh
            rects.append(
                f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bar_w:.1f}" height="{bh:.1f}" '
                f'fill="{colors[si]}" rx="2" opacity="0.88"/>'
            )
        # arm label
        lx = gx + bar_group_w / 2
        labels.append(
            f'<text x="{lx:.1f}" y="{chart_h - pad_b + 14}" fill="#94a3b8" font-size="9" '
            f'text-anchor="middle">{p.arm_name.replace("_", " ")}</text>'
        )

    # Y axis ticks
    ticks = []
    for t in [0, 25, 50, 75, 100]:
        ty = pad_t + plot_h - t / max_val * plot_h
        ticks.append(
            f'<line x1="{pad_l}" y1="{ty:.1f}" x2="{pad_l + plot_w}" y2="{ty:.1f}" '
            f'stroke="#334155" stroke-width="1"/>'
        )
        ticks.append(
            f'<text x="{pad_l - 4}" y="{ty + 4:.1f}" fill="#64748b" font-size="8" text-anchor="end">{t}%</text>'
        )

    # Legend
    legend = []
    for i, (s, c) in enumerate(zip(series, colors)):
        lx = pad_l + i * 100
        legend.append(f'<rect x="{lx}" y="{chart_h - 12}" width="10" height="10" fill="{c}" rx="2"/>')
        legend.append(
            f'<text x="{lx + 13}" y="{chart_h - 3}" fill="#94a3b8" font-size="9">{s}</text>'
        )

    svg = (
        f'<svg width="{chart_w}" height="{chart_h}" xmlns="http://www.w3.org/2000/svg" '
        f'style="background:#0f172a;border-radius:6px;">'
        + "".join(ticks)
        + "".join(rects)
        + "".join(labels)
        + "".join(legend)
        + "</svg>"
    )
    return svg


def _legend_svg() -> str:
    items = [
        ("#22c55e", "Reachable + Collision-free"),
        ("#f59e0b", "Reachable (collision risk)"),
        ("#334155", "Unreachable"),
    ]
    parts = []
    x = 0
    for color, label in items:
        parts.append(f'<rect x="{x}" y="4" width="12" height="12" fill="{color}" rx="2"/>')
        parts.append(f'<text x="{x+16}" y="14" fill="#94a3b8" font-size="10">{label}</text>')
        x += len(label) * 6 + 32
    return f'<svg width="{x}" height="20" xmlns="http://www.w3.org/2000/svg">{"".join(parts)}</svg>'


def generate_html(
    all_cells: dict[str, List[WorkspaceCell]],
    report: WorkspaceReport,
) -> str:
    profiles = report.results
    best = next(p for p in profiles if p.arm_name == report.best_arm)

    # --- Stat cards ---
    def card(title: str, value: str, sub: str, highlight: bool = False) -> str:
        border = "border-left:3px solid #C74634;" if highlight else "border-left:3px solid #3b82f6;"
        return (
            f'<div style="background:#0f172a;{border}padding:16px 20px;border-radius:8px;">'
            f'<div style="color:#64748b;font-size:11px;text-transform:uppercase;letter-spacing:.06em">{title}</div>'
            f'<div style="color:#f1f5f9;font-size:28px;font-weight:700;margin:4px 0">{value}</div>'
            f'<div style="color:#94a3b8;font-size:11px">{sub}</div>'
            f"</div>"
        )

    cards_html = "".join([
        card("Best Arm (Overall)", best.arm_name.replace("_", " "), "highest composite score", highlight=True),
        card("Reachable Volume", f"{best.reachable_volume_m3:.4f} m³", f"({best.arm_name})"),
        card("Collision-Free %",
             f"{max(p.collision_free_pct for p in profiles):.1f}%",
             f"({report.most_collision_free})"),
        card("Avg IK Success",
             f"{max(p.avg_ik_success_rate for p in profiles)*100:.1f}%",
             f"({max(profiles, key=lambda p: p.avg_ik_success_rate).arm_name})"),
    ])

    # --- Workspace maps 2×2 grid ---
    arm_names = list(ARM_SPECS.keys())
    maps_html = '<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">'
    for arm_name in arm_names:
        maps_html += _build_workspace_svg(arm_name, all_cells[arm_name])
    maps_html += "</div>"

    # --- Bar chart ---
    bar_chart_html = _build_bar_chart(profiles)

    # --- Table ---
    def td(v: str, bold: bool = False) -> str:
        style = "padding:8px 12px;border-bottom:1px solid #1e293b;"
        if bold:
            style += "font-weight:700;color:#f1f5f9;"
        return f'<td style="{style}">{v}</td>'

    rows = ""
    for p in profiles:
        highlight = p.arm_name == report.best_arm
        tr_style = 'style="background:#0f172a;"' if highlight else 'style="background:#111827;"'
        rows += (
            f"<tr {tr_style}>"
            + td(p.arm_name, bold=highlight)
            + td(str(p.n_joints))
            + td(f"{p.reach_radius_m:.2f}")
            + td(f"{p.reachable_volume_m3:.4f}")
            + td(f"{p.collision_free_pct:.1f}%")
            + td(f"{p.avg_ik_success_rate:.3f}")
            + td(f"{p.avg_manipulability:.3f}")
            + td(str(p.dead_zones))
            + "</tr>"
        )

    th_style = "padding:10px 12px;text-align:left;color:#94a3b8;font-size:11px;text-transform:uppercase;letter-spacing:.05em;border-bottom:2px solid #C74634;"
    table_html = (
        '<table style="width:100%;border-collapse:collapse;background:#0f172a;border-radius:8px;overflow:hidden;">'
        "<thead><tr>"
        + "".join(f'<th style="{th_style}">{h}</th>' for h in
                  ["Arm", "Joints", "Reach (m)", "Volume (m³)", "CF%", "IK Success", "Manip", "Dead Zones"])
        + "</tr></thead><tbody>"
        + rows
        + "</tbody></table>"
    )

    # --- Insight ---
    insight_html = """
    <div style="background:#0f172a;border:1px solid #334155;border-radius:8px;padding:20px 24px;">
      <h3 style="color:#C74634;margin:0 0 12px;font-size:14px;text-transform:uppercase;letter-spacing:.05em">
        Analysis &amp; Recommendations
      </h3>
      <ul style="color:#94a3b8;font-size:13px;line-height:1.7;margin:0;padding-left:18px;">
        <li><strong style="color:#e2e8f0">kinova_gen3</strong> is recommended for task diversity —
            it combines the largest reach radius (0.90 m), the highest collision-free percentage,
            and consistent IK success across the workspace. Ideal for pick-and-place tasks spanning
            wide table areas or multi-position assembly.</li>
        <li><strong style="color:#e2e8f0">franka_panda</strong> delivers the best manipulability
            in close-range tasks (within 0.5 m of base). The 7-DOF kinematic redundancy and
            well-tuned joint limits make it the preferred choice for precision insertion, screwdriving,
            and dexterous manipulation where Jacobian conditioning matters.</li>
        <li><strong style="color:#e2e8f0">ur5e</strong> is a solid generalist but shows a higher
            collision rate at workspace extremes and an elbow-up singularity zone above z=0.70 m.</li>
        <li><strong style="color:#e2e8f0">xarm7</strong> has the smallest reach radius (0.70 m) and
            highest collision base rate — best suited for constrained benchtop tasks where footprint
            matters more than reach.</li>
      </ul>
    </div>
    """

    legend_html = _legend_svg()

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Workspace Collision Mapper — OCI Robot Cloud</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #1e293b; color: #cbd5e1; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
  .container {{ max-width: 1100px; margin: 0 auto; padding: 32px 24px; }}
  h1 {{ color: #f1f5f9; font-size: 22px; font-weight: 700; margin-bottom: 4px; }}
  .subtitle {{ color: #64748b; font-size: 13px; margin-bottom: 28px; }}
  .section {{ margin-bottom: 32px; }}
  .section-title {{ color: #e2e8f0; font-size: 14px; font-weight: 600; text-transform: uppercase;
                    letter-spacing: .06em; margin-bottom: 14px; padding-bottom: 6px;
                    border-bottom: 1px solid #334155; }}
  .stat-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }}
  @media (max-width: 800px) {{ .stat-grid {{ grid-template-columns: repeat(2, 1fr); }} }}
  .oracle-red {{ color: #C74634; }}
</style>
</head>
<body>
<div class="container">
  <h1>Robot Arm Workspace &amp; Collision Map</h1>
  <p class="subtitle">OCI Robot Cloud — reachability and collision-free region analysis (500-cell grid, 4 arms)</p>

  <div class="section">
    <div class="section-title">Summary</div>
    <div class="stat-grid">{cards_html}</div>
  </div>

  <div class="section">
    <div class="section-title">Top-View Workspace Map (z ≈ 0.60 m slice)</div>
    <div style="margin-bottom:10px;">{legend_html}</div>
    {maps_html}
  </div>

  <div class="section">
    <div class="section-title">Performance Comparison</div>
    {bar_chart_html}
    <p style="color:#475569;font-size:10px;margin-top:6px;">
      Volume% normalised to best arm. CF% = collision-free percentage. IK% = avg IK success × 100.
    </p>
  </div>

  <div class="section">
    <div class="section-title">Arm Specifications</div>
    {table_html}
  </div>

  <div class="section">
    {insight_html}
  </div>

  <div style="color:#334155;font-size:10px;text-align:center;margin-top:24px;">
    Generated by workspace_collision_mapper.py · OCI Robot Cloud · Oracle Confidential
  </div>
</div>
</body>
</html>"""
    return html


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Robot arm workspace reachability and collision-free region mapping."
    )
    parser.add_argument("--mock", action="store_true", default=True,
                        help="Use mock/simulated data (default: True; no real robot required)")
    parser.add_argument("--output", default="/tmp/workspace_collision_mapper.html",
                        help="Path for the HTML report (default: /tmp/workspace_collision_mapper.html)")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed for reproducible simulation (default: 42)")
    args = parser.parse_args()

    print("Running workspace simulation (seed={}, grid={}×{}×{}={} cells, arms={}) ...".format(
        args.seed, len(GRID_X), len(GRID_Y), len(GRID_Z),
        len(GRID_X) * len(GRID_Y) * len(GRID_Z),
        ", ".join(ARM_SPECS.keys()),
    ))

    all_cells, report = run_simulation(seed=args.seed)

    print_table(report)

    html = generate_html(all_cells, report)
    with open(args.output, "w", encoding="utf-8") as fh:
        fh.write(html)

    print(f"HTML report saved to: {args.output}")
    print(f"Best arm: {report.best_arm}  |  Most collision-free: {report.most_collision_free}")


if __name__ == "__main__":
    main()
