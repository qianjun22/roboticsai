"""
Analyzes simulation scene complexity to predict SDG data quality and sim-to-real gap.
Helps choose the right scene config before 1000-demo collection runs by comparing
fps trade-offs, Pareto-optimal configs, and policy success-rate predictions.
"""

import argparse
import math
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List, Optional, Tuple


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

class ComplexityLevel(Enum):
    MINIMAL = "minimal"
    BASIC = "basic"
    STANDARD = "standard"
    RICH = "rich"
    ULTRA = "ultra"


@dataclass
class SceneMetrics:
    scene_id: str
    n_objects: int
    n_lights: int
    texture_variety: float          # 0-1
    physics_complexity: str         # low / med / high
    camera_count: int
    estimated_fps: float
    estimated_sim_to_real_gap: float  # 0-10 (lower = better)
    predicted_policy_sr: float      # 0-1
    simulator: str = "genesis"
    domain_randomization: bool = False
    notes: str = ""

    # Derived at construction time
    cost_per_episode_sec: float = field(init=False)

    def __post_init__(self):
        # seconds per episode assuming each demo = 10 sim-seconds at given fps
        frames_per_episode = 10.0 * self.estimated_fps
        # overhead factor grows with complexity
        overhead = 1.0 + 0.05 * self.n_objects
        self.cost_per_episode_sec = (frames_per_episode / max(self.estimated_fps, 0.1)) * overhead

    def cost_per_1k_demos_hr(self) -> float:
        return (self.cost_per_episode_sec * 1000) / 3600.0


# ---------------------------------------------------------------------------
# Scene catalog
# ---------------------------------------------------------------------------

SCENES: List[SceneMetrics] = [
    SceneMetrics(
        scene_id="minimal",
        n_objects=1, n_lights=1,
        texture_variety=0.1, physics_complexity="low",
        camera_count=1, estimated_fps=38.5,
        estimated_sim_to_real_gap=8.2,
        predicted_policy_sr=0.28,
        simulator="genesis",
        notes="Single-object, single-light Genesis baseline — fast but large sim-to-real gap",
    ),
    SceneMetrics(
        scene_id="basic",
        n_objects=2, n_lights=2,
        texture_variety=0.25, physics_complexity="low",
        camera_count=1, estimated_fps=25.0,
        estimated_sim_to_real_gap=6.8,
        predicted_policy_sr=0.38,
        simulator="genesis",
        notes="Two objects, two lights; slight texture variety added",
    ),
    SceneMetrics(
        scene_id="standard",
        n_objects=3, n_lights=3,
        texture_variety=0.45, physics_complexity="med",
        camera_count=1, estimated_fps=18.0,
        estimated_sim_to_real_gap=5.1,
        predicted_policy_sr=0.52,
        simulator="isaac",
        notes="Isaac Sim standard: 3 objects, medium physics, balanced trade-off",
    ),
    SceneMetrics(
        scene_id="rich_dr",
        n_objects=5, n_lights=4,
        texture_variety=0.65, physics_complexity="med",
        camera_count=1, estimated_fps=12.0,
        estimated_sim_to_real_gap=3.8,
        predicted_policy_sr=0.67,
        simulator="isaac",
        domain_randomization=True,
        notes="Isaac RTX with domain randomization sweep; good gap/cost balance",
    ),
    SceneMetrics(
        scene_id="multi_cam",
        n_objects=3, n_lights=3,
        texture_variety=0.45, physics_complexity="med",
        camera_count=3, estimated_fps=14.0,
        estimated_sim_to_real_gap=4.2,
        predicted_policy_sr=0.61,
        simulator="isaac",
        notes="Standard scene + 3 cameras for richer visual observations",
    ),
    SceneMetrics(
        scene_id="photorealistic",
        n_objects=3, n_lights=5,
        texture_variety=0.85, physics_complexity="high",
        camera_count=2, estimated_fps=8.0,
        estimated_sim_to_real_gap=2.9,
        predicted_policy_sr=0.73,
        simulator="isaac",
        notes="Full RTX path-traced rendering with PBR textures; smallest single-config gap",
    ),
    SceneMetrics(
        scene_id="adversarial",
        n_objects=5, n_lights=3,
        texture_variety=0.55, physics_complexity="high",
        camera_count=1, estimated_fps=6.0,
        estimated_sim_to_real_gap=4.5,
        predicted_policy_sr=0.56,
        simulator="isaac",
        domain_randomization=True,
        notes="Distractors + clutter; hardens policy robustness but raises gap due to unrealistic clutter",
    ),
    SceneMetrics(
        scene_id="combined_best",
        n_objects=5, n_lights=5,
        texture_variety=0.92, physics_complexity="high",
        camera_count=3, estimated_fps=5.0,
        estimated_sim_to_real_gap=2.1,
        predicted_policy_sr=0.81,
        simulator="isaac",
        domain_randomization=True,
        notes="rich_dr + multi_cam + photorealistic combined; best predicted SR but most expensive",
    ),
]


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

def pareto_optimal(scenes: List[SceneMetrics]) -> List[SceneMetrics]:
    """Return Pareto-optimal scenes: maximize fps AND minimize sim-to-real gap."""
    pareto = []
    for candidate in scenes:
        dominated = False
        for other in scenes:
            if other.scene_id == candidate.scene_id:
                continue
            if (other.estimated_fps >= candidate.estimated_fps and
                    other.estimated_sim_to_real_gap <= candidate.estimated_sim_to_real_gap and
                    (other.estimated_fps > candidate.estimated_fps or
                     other.estimated_sim_to_real_gap < candidate.estimated_sim_to_real_gap)):
                dominated = True
                break
        if not dominated:
            pareto.append(candidate)
    return pareto


def analyze_tradeoffs(scenes: List[SceneMetrics]) -> dict:
    pareto = pareto_optimal(scenes)
    pareto_ids = {s.scene_id for s in pareto}
    best_sr = max(scenes, key=lambda s: s.predicted_policy_sr)
    best_cost = min(scenes, key=lambda s: s.cost_per_1k_demos_hr())
    return {
        "pareto_optimal": pareto,
        "pareto_ids": pareto_ids,
        "best_sr_scene": best_sr,
        "cheapest_scene": best_cost,
        "avg_gap": sum(s.estimated_sim_to_real_gap for s in scenes) / len(scenes),
        "avg_fps": sum(s.estimated_fps for s in scenes) / len(scenes),
    }


def recommend(n_demos: int = 1000, compute_budget_hr: float = 5.0) -> Tuple[SceneMetrics, str]:
    """Return best scene for given demo count and compute budget."""
    feasible = [s for s in SCENES if s.cost_per_1k_demos_hr() * (n_demos / 1000.0) <= compute_budget_hr]
    if not feasible:
        # Fallback: cheapest option even if over budget
        best = min(SCENES, key=lambda s: s.cost_per_1k_demos_hr())
        reason = (f"No scene fits within {compute_budget_hr}h budget for {n_demos} demos. "
                  f"Cheapest option '{best.scene_id}' costs "
                  f"{best.cost_per_1k_demos_hr() * n_demos / 1000:.1f}h.")
    else:
        # Among feasible, pick highest predicted SR; tie-break on lowest gap
        best = max(feasible, key=lambda s: (s.predicted_policy_sr, -s.estimated_sim_to_real_gap))
        cost = best.cost_per_1k_demos_hr() * n_demos / 1000.0
        reason = (f"'{best.scene_id}' predicts {best.predicted_policy_sr:.0%} policy SR with "
                  f"sim-to-real gap {best.estimated_sim_to_real_gap} — fits in "
                  f"{cost:.1f}h of {compute_budget_hr}h budget.")
    return best, reason


# ---------------------------------------------------------------------------
# HTML renderer
# ---------------------------------------------------------------------------

def _gap_color(gap: float) -> str:
    if gap < 4.0:
        return "#22c55e"   # green
    if gap < 6.0:
        return "#f59e0b"   # amber
    return "#ef4444"       # red


def render_html(scenes: List[SceneMetrics], analysis: dict,
                rec: SceneMetrics, rec_reason: str,
                n_demos: int, budget_hr: float) -> str:
    pareto_ids = analysis["pareto_ids"]

    # --- SVG scatter: x=fps, y=gap ---
    W, H, PAD = 560, 340, 50
    fps_vals = [s.estimated_fps for s in scenes]
    gap_vals = [s.estimated_sim_to_real_gap for s in scenes]
    fps_min, fps_max = min(fps_vals) - 2, max(fps_vals) + 4
    gap_min, gap_max = 1.5, 9.5

    def sx(fps):
        return PAD + (fps - fps_min) / (fps_max - fps_min) * (W - 2 * PAD)

    def sy(gap):
        return H - PAD - (gap_max - gap) / (gap_max - gap_min) * (H - 2 * PAD)

    scatter_points = []
    for s in scenes:
        cx, cy = sx(s.estimated_fps), sy(s.estimated_sim_to_real_gap)
        color = "#818cf8" if s.scene_id in pareto_ids else "#94a3b8"
        star = " ★" if s.scene_id == rec.scene_id else ""
        scatter_points.append(
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="8" fill="{color}" stroke="#1e293b" stroke-width="1.5"/>'
            f'<text x="{cx + 10:.1f}" y="{cy + 4:.1f}" fill="#e2e8f0" font-size="11">{s.scene_id}{star}</text>'
        )

    # Pareto frontier line (sorted by fps)
    pareto_sorted = sorted(analysis["pareto_optimal"], key=lambda s: s.estimated_fps)
    if len(pareto_sorted) > 1:
        pts = " ".join(f"{sx(s.estimated_fps):.1f},{sy(s.estimated_sim_to_real_gap):.1f}"
                       for s in pareto_sorted)
        pareto_line = f'<polyline points="{pts}" fill="none" stroke="#818cf8" stroke-width="1.5" stroke-dasharray="4 3"/>'
    else:
        pareto_line = ""

    svg_scatter = f"""
<svg width="{W}" height="{H}" style="background:#1e293b;border-radius:8px">
  <text x="{W//2}" y="20" text-anchor="middle" fill="#94a3b8" font-size="13">FPS vs Sim-to-Real Gap</text>
  <line x1="{PAD}" y1="{H-PAD}" x2="{W-PAD}" y2="{H-PAD}" stroke="#475569" stroke-width="1"/>
  <line x1="{PAD}" y1="{PAD}" x2="{PAD}" y2="{H-PAD}" stroke="#475569" stroke-width="1"/>
  <text x="{W//2}" y="{H-8}" text-anchor="middle" fill="#94a3b8" font-size="11">FPS (higher = cheaper)</text>
  <text x="12" y="{H//2}" text-anchor="middle" fill="#94a3b8" font-size="11" transform="rotate(-90,12,{H//2})">Sim-to-Real Gap (lower = better)</text>
  {pareto_line}
  {''.join(scatter_points)}
  <text x="{W-PAD+5}" y="{PAD+15}" fill="#818cf8" font-size="10">● Pareto</text>
  <text x="{W-PAD+5}" y="{PAD+28}" fill="#94a3b8" font-size="10">● Other</text>
</svg>"""

    # --- Bar chart: predicted policy SR ---
    BW, BH, BPAD = 560, 260, 50
    bar_w = (BW - 2 * BPAD) / len(scenes) - 6

    bars = []
    for i, s in enumerate(scenes):
        bx = BPAD + i * ((BW - 2 * BPAD) / len(scenes))
        bar_h = s.predicted_policy_sr * (BH - 2 * BPAD - 20)
        by = BH - BPAD - bar_h
        color = _gap_color(s.estimated_sim_to_real_gap)
        bars.append(
            f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bar_w:.1f}" height="{bar_h:.1f}" '
            f'fill="{color}" rx="3"/>'
            f'<text x="{bx + bar_w/2:.1f}" y="{by - 4:.1f}" text-anchor="middle" '
            f'fill="#e2e8f0" font-size="10">{s.predicted_policy_sr:.0%}</text>'
            f'<text x="{bx + bar_w/2:.1f}" y="{BH - BPAD + 14:.1f}" text-anchor="middle" '
            f'fill="#94a3b8" font-size="9" transform="rotate(-35,{bx + bar_w/2:.1f},{BH - BPAD + 14:.1f})">'
            f'{s.scene_id}</text>'
        )

    svg_bar = f"""
<svg width="{BW}" height="{BH}" style="background:#1e293b;border-radius:8px">
  <text x="{BW//2}" y="20" text-anchor="middle" fill="#94a3b8" font-size="13">Predicted Policy Success Rate</text>
  <line x1="{BPAD}" y1="{BH-BPAD}" x2="{BW-BPAD}" y2="{BH-BPAD}" stroke="#475569" stroke-width="1"/>
  {''.join(bars)}
  <text x="{BW - 20}" y="42" fill="#22c55e" font-size="10">■ gap&lt;4</text>
  <text x="{BW - 20}" y="56" fill="#f59e0b" font-size="10">■ gap&lt;6</text>
  <text x="{BW - 20}" y="70" fill="#ef4444" font-size="10">■ gap≥6</text>
</svg>"""

    # --- Metrics table ---
    header_cols = ["Scene", "Objects", "Lights", "Tex Variety", "Physics",
                   "Cameras", "FPS", "Gap", "Pred SR", "Cost/1k demos (hr)", "DR", "Simulator"]

    def td(val, bold=False, color=None):
        style = ""
        if bold:
            style += "font-weight:600;"
        if color:
            style += f"color:{color};"
        return f'<td style="padding:6px 10px;border-bottom:1px solid #334155;{style}">{val}</td>'

    rows = []
    for s in scenes:
        highlight = ' style="background:#1e3a5f;"' if s.scene_id == rec.scene_id else ""
        pareto_marker = " ★" if s.scene_id in pareto_ids else ""
        row = (
            f'<tr{highlight}>'
            + td(s.scene_id + pareto_marker, bold=(s.scene_id == rec.scene_id))
            + td(s.n_objects)
            + td(s.n_lights)
            + td(f"{s.texture_variety:.2f}")
            + td(s.physics_complexity)
            + td(s.camera_count)
            + td(f"{s.estimated_fps:.1f}")
            + td(f"{s.estimated_sim_to_real_gap:.1f}", color=_gap_color(s.estimated_sim_to_real_gap))
            + td(f"{s.predicted_policy_sr:.0%}", color=_gap_color(s.estimated_sim_to_real_gap))
            + td(f"{s.cost_per_1k_demos_hr():.2f}")
            + td("Yes" if s.domain_randomization else "No")
            + td(s.simulator)
            + "</tr>"
        )
        rows.append(row)

    table_html = f"""
<table style="width:100%;border-collapse:collapse;color:#e2e8f0;font-size:13px;background:#1e293b;border-radius:8px;overflow:hidden">
  <thead>
    <tr style="background:#0f172a">
      {''.join(f'<th style="padding:8px 10px;text-align:left;color:#94a3b8;font-weight:500">{c}</th>' for c in header_cols)}
    </tr>
  </thead>
  <tbody>
    {''.join(rows)}
  </tbody>
</table>
<p style="color:#64748b;font-size:11px;margin-top:4px">★ = Pareto-optimal (fps vs gap)  |  highlighted row = recommended config</p>"""

    rec_box = f"""
<div style="background:#0f2744;border:1px solid #3b82f6;border-radius:8px;padding:16px 20px;color:#e2e8f0">
  <div style="font-size:15px;font-weight:600;color:#60a5fa;margin-bottom:6px">
    Recommendation for {n_demos} demos / {budget_hr}h budget
  </div>
  <div style="font-size:22px;font-weight:700;color:#f8fafc;margin-bottom:4px">{rec.scene_id}</div>
  <div style="color:#94a3b8;font-size:13px">{rec_reason}</div>
  <div style="margin-top:10px;display:flex;gap:24px;font-size:13px">
    <span>FPS: <b style="color:#f8fafc">{rec.estimated_fps}</b></span>
    <span>Gap: <b style="color:{_gap_color(rec.estimated_sim_to_real_gap)}">{rec.estimated_sim_to_real_gap}</b></span>
    <span>SR: <b style="color:#f8fafc">{rec.predicted_policy_sr:.0%}</b></span>
    <span>Cost: <b style="color:#f8fafc">{rec.cost_per_1k_demos_hr() * n_demos / 1000:.1f}h</b></span>
  </div>
</div>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<title>Scene Complexity Analyzer</title>
<style>
  body {{background:#0f172a;color:#e2e8f0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
         margin:0;padding:24px;}}
  h1 {{color:#f8fafc;font-size:22px;margin-bottom:4px}}
  h2 {{color:#94a3b8;font-size:14px;font-weight:400;margin:0 0 24px}}
  .grid {{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-bottom:24px}}
  .section {{margin-bottom:24px}}
  .section-title {{color:#64748b;font-size:12px;text-transform:uppercase;letter-spacing:.08em;margin-bottom:8px}}
</style>
</head>
<body>
<h1>Scene Complexity Analyzer</h1>
<h2>Sim-to-real gap &amp; SDG quality prediction before data collection runs</h2>

<div class="section">{rec_box}</div>

<div class="grid">
  <div>
    <div class="section-title">FPS vs Sim-to-Real Gap (Pareto frontier in purple)</div>
    {svg_scatter}
  </div>
  <div>
    <div class="section-title">Predicted Policy Success Rate by Scene</div>
    {svg_bar}
  </div>
</div>

<div class="section">
  <div class="section-title">All Scene Metrics</div>
  {table_html}
</div>

<div style="color:#475569;font-size:11px;margin-top:16px">
  Generated by scene_complexity_analyzer.py — OCI Robot Cloud SDG Pipeline
</div>
</body>
</html>"""
    return html


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Analyze simulation scene complexity to predict SDG quality and sim-to-real gap."
    )
    parser.add_argument("--n-demos", type=int, default=1000,
                        help="Number of demos to collect (default: 1000)")
    parser.add_argument("--budget-hr", type=float, default=5.0,
                        help="Compute budget in hours (default: 5.0)")
    parser.add_argument("--output", type=str, default="/tmp/scene_complexity.html",
                        help="Output HTML path (default: /tmp/scene_complexity.html)")
    args = parser.parse_args()

    analysis = analyze_tradeoffs(SCENES)
    rec, rec_reason = recommend(args.n_demos, args.budget_hr)

    print(f"Analyzing {len(SCENES)} scene configurations...")
    print(f"  Pareto-optimal configs: {', '.join(s.scene_id for s in analysis['pareto_optimal'])}")
    print(f"  Best predicted SR: {analysis['best_sr_scene'].scene_id} "
          f"({analysis['best_sr_scene'].predicted_policy_sr:.0%})")
    print(f"  Cheapest: {analysis['cheapest_scene'].scene_id} "
          f"({analysis['cheapest_scene'].cost_per_1k_demos_hr():.2f}h/1k demos)")
    print(f"\nRecommendation ({args.n_demos} demos, {args.budget_hr}h budget): {rec.scene_id}")
    print(f"  {rec_reason}")

    html = render_html(SCENES, analysis, rec, rec_reason, args.n_demos, args.budget_hr)
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    print(f"\nDashboard written to: {out_path}")


if __name__ == "__main__":
    main()
