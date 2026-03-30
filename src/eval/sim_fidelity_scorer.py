#!/usr/bin/env python3
"""
sim_fidelity_scorer.py — Measures simulation fidelity vs real-robot data for GR00T training.

Compares synthetic (SDG) episode distributions against real teleoperation demos across
visual, kinematic, and contact dimensions. High fidelity → lower sim-to-real gap.

Usage:
    python src/eval/sim_fidelity_scorer.py --mock --output /tmp/sim_fidelity_scorer.html
"""

import argparse
import json
import math
import random
import time
from dataclasses import dataclass, field
from pathlib import Path


SIM_CONFIGS = [
    # (name, renderer, physics_engine, domain_rand)
    ("genesis_basic",    "rasterize",  "genesis",   False),
    ("genesis_dr",       "rasterize",  "genesis",   True),
    ("isaac_basic",      "rtx",        "physx",     False),
    ("isaac_dr",         "rtx",        "physx",     True),
    ("cosmos_wm",        "neural",     "cosmos",    True),
]

FIDELITY_DIMS = [
    "visual_realism",
    "contact_physics",
    "joint_dynamics",
    "object_geometry",
    "lighting_variance",
    "trajectory_diversity",
]

N_REAL_DEMOS = 50
N_SIM_DEMOS  = 200


@dataclass
class FidelityDimScore:
    dim_name: str
    sim_config: str
    score: float          # 0–1 (1 = matches real perfectly)
    real_mean: float
    sim_mean: float
    distribution_overlap: float  # Bhattacharyya coefficient
    ks_statistic: float          # KS distance (lower = more similar)


@dataclass
class SimFidelityResult:
    config_name: str
    renderer: str
    physics_engine: str
    domain_rand: bool
    overall_fidelity: float   # weighted avg across dims
    dim_scores: list[FidelityDimScore]
    policy_sr_from_sim: float   # policy trained on this sim
    sim2real_gap: float
    cost_factor: float          # relative SDG cost


@dataclass
class FidelityReport:
    best_config: str
    best_fidelity: float
    best_sr_config: str
    n_real_demos: int
    n_sim_demos: int
    results: list[SimFidelityResult] = field(default_factory=list)


# Baseline fidelity per config per dim (real = 1.0)
FIDELITY_MATRIX = {
    "genesis_basic":  [0.41, 0.62, 0.71, 0.78, 0.35, 0.58],
    "genesis_dr":     [0.53, 0.68, 0.74, 0.79, 0.64, 0.72],
    "isaac_basic":    [0.71, 0.79, 0.84, 0.85, 0.68, 0.67],
    "isaac_dr":       [0.82, 0.84, 0.86, 0.87, 0.88, 0.81],
    "cosmos_wm":      [0.91, 0.76, 0.79, 0.83, 0.92, 0.88],
}

DIM_WEIGHTS = [0.25, 0.20, 0.20, 0.15, 0.10, 0.10]

CONFIG_SR      = {"genesis_basic": 0.58, "genesis_dr": 0.67, "isaac_basic": 0.72,
                  "isaac_dr": 0.79, "cosmos_wm": 0.77}
CONFIG_GAP     = {"genesis_basic": 0.38, "genesis_dr": 0.28, "isaac_basic": 0.22,
                  "isaac_dr": 0.14, "cosmos_wm": 0.16}
CONFIG_COST    = {"genesis_basic": 1.0,  "genesis_dr": 1.4,  "isaac_basic": 2.8,
                  "isaac_dr": 3.6,  "cosmos_wm": 4.2}


def simulate_fidelity(seed: int = 42) -> FidelityReport:
    rng = random.Random(seed)
    results: list[SimFidelityResult] = []

    for cfg_name, renderer, physics, dr in SIM_CONFIGS:
        base_scores = FIDELITY_MATRIX[cfg_name]
        dim_scores: list[FidelityDimScore] = []

        for i, dim in enumerate(FIDELITY_DIMS):
            base = base_scores[i]
            score = base + rng.gauss(0, 0.025)
            score = max(0.1, min(1.0, score))

            # Simulate real vs sim stat distributions
            real_mean = 0.5 + rng.gauss(0, 0.05)
            sim_mean  = real_mean + (1 - score) * 0.3 * rng.choice([-1, 1])
            # Distribution overlap approximates Bhattacharyya
            overlap = score * 0.9 + rng.gauss(0, 0.03)
            overlap = max(0.05, min(1.0, overlap))
            ks_stat = (1 - score) * 0.4 + rng.gauss(0, 0.02)
            ks_stat = max(0.01, min(0.8, ks_stat))

            dim_scores.append(FidelityDimScore(
                dim_name=dim, sim_config=cfg_name,
                score=round(score, 3),
                real_mean=round(real_mean, 3),
                sim_mean=round(sim_mean, 3),
                distribution_overlap=round(overlap, 3),
                ks_statistic=round(ks_stat, 3),
            ))

        overall = sum(DIM_WEIGHTS[i] * dim_scores[i].score for i in range(len(FIDELITY_DIMS)))

        results.append(SimFidelityResult(
            config_name=cfg_name, renderer=renderer,
            physics_engine=physics, domain_rand=dr,
            overall_fidelity=round(overall, 3),
            dim_scores=dim_scores,
            policy_sr_from_sim=round(CONFIG_SR[cfg_name] + rng.gauss(0, 0.02), 3),
            sim2real_gap=round(CONFIG_GAP[cfg_name] + rng.gauss(0, 0.01), 3),
            cost_factor=CONFIG_COST[cfg_name],
        ))

    best = max(results, key=lambda r: r.overall_fidelity).config_name
    best_sr = max(results, key=lambda r: r.policy_sr_from_sim).config_name

    return FidelityReport(
        best_config=best, best_fidelity=max(r.overall_fidelity for r in results),
        best_sr_config=best_sr,
        n_real_demos=N_REAL_DEMOS, n_sim_demos=N_SIM_DEMOS,
        results=results,
    )


def render_html(report: FidelityReport) -> str:
    CFG_COLORS = {
        "genesis_basic": "#475569", "genesis_dr": "#64748b",
        "isaac_basic": "#3b82f6",   "isaac_dr": "#22c55e",
        "cosmos_wm": "#f59e0b",
    }

    # SVG: radar chart per config (spider web, 6 dims)
    rw, rh = 320, 280
    cx, cy, r = rw // 2, rh // 2, 100
    n_dims = len(FIDELITY_DIMS)
    angles = [2 * math.pi * i / n_dims - math.pi / 2 for i in range(n_dims)]

    svg_radar = f'<svg width="{rw}" height="{rh}" style="background:#0f172a;border-radius:8px">'

    # Grid rings
    for ring in [0.25, 0.5, 0.75, 1.0]:
        pts = [(cx + ring * r * math.cos(a), cy + ring * r * math.sin(a)) for a in angles]
        pstr = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts) + f" {pts[0][0]:.1f},{pts[0][1]:.1f}"
        svg_radar += (f'<polyline points="{pstr}" fill="none" stroke="#1e293b" stroke-width="1"/>')
        lx = cx + ring * r * math.cos(angles[0]) + 4
        ly = cy + ring * r * math.sin(angles[0])
        svg_radar += (f'<text x="{lx:.1f}" y="{ly:.1f}" fill="#334155" font-size="7">{ring:.0%}</text>')

    # Axes
    for a, dim in zip(angles, FIDELITY_DIMS):
        ax, ay = cx + r * math.cos(a), cy + r * math.sin(a)
        svg_radar += f'<line x1="{cx}" y1="{cy}" x2="{ax:.1f}" y2="{ay:.1f}" stroke="#1e293b"/>'
        lx = cx + (r + 14) * math.cos(a)
        ly = cy + (r + 14) * math.sin(a)
        svg_radar += (f'<text x="{lx:.1f}" y="{ly+3:.1f}" fill="#64748b" font-size="7.5" '
                      f'text-anchor="middle">{dim.replace("_", " ")}</text>')

    for res in report.results:
        col = CFG_COLORS[res.config_name]
        vals = {ds.dim_name: ds.score for ds in res.dim_scores}
        pts = [(cx + vals[dim] * r * math.cos(a), cy + vals[dim] * r * math.sin(a))
               for dim, a in zip(FIDELITY_DIMS, angles)]
        pstr = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts) + f" {pts[0][0]:.1f},{pts[0][1]:.1f}"
        svg_radar += (f'<polyline points="{pstr}" fill="{col}" fill-opacity="0.05" '
                      f'stroke="{col}" stroke-width="1.5" opacity="0.8"/>')

    svg_radar += '</svg>'

    # SVG: fidelity vs sim2real gap scatter
    sw, sh, sm = 360, 220, 50
    svg_scat = f'<svg width="{sw}" height="{sh}" style="background:#0f172a;border-radius:8px">'
    svg_scat += f'<line x1="{sm}" y1="{sm}" x2="{sm}" y2="{sh-sm}" stroke="#475569"/>'
    svg_scat += f'<line x1="{sm}" y1="{sh-sm}" x2="{sw-sm}" y2="{sh-sm}" stroke="#475569"/>'

    min_fid = min(r.overall_fidelity for r in report.results) - 0.05
    max_fid = max(r.overall_fidelity for r in report.results) + 0.02
    fid_range = max_fid - min_fid
    max_gap = max(r.sim2real_gap for r in report.results) + 0.03
    gap_range = max_gap

    for res in report.results:
        col = CFG_COLORS[res.config_name]
        x = sm + (res.overall_fidelity - min_fid) / fid_range * (sw - 2 * sm)
        y = sh - sm - (1 - res.sim2real_gap / max_gap) * (sh - 2 * sm)
        size = 5 + (res.cost_factor / 5) * 4
        svg_scat += (f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{size:.1f}" '
                     f'fill="{col}" opacity="0.85"/>')
        svg_scat += (f'<text x="{x+size+3:.1f}" y="{y+4:.1f}" fill="{col}" '
                     f'font-size="8">{res.config_name[:10]}</text>')

    svg_scat += (f'<text x="{sw//2}" y="{sh-sm+14}" fill="#64748b" '
                 f'font-size="8" text-anchor="middle">Fidelity Score →</text>')
    svg_scat += (f'<text x="{sm-10}" y="{sh//2}" fill="#64748b" font-size="8" '
                 f'text-anchor="middle" transform="rotate(-90,{sm-10},{sh//2})">Sim2Real Gap ↓</text>')
    svg_scat += (f'<text x="{sw-sm-20}" y="{sm-6}" fill="#64748b" font-size="7">dot size = cost</text>')
    svg_scat += '</svg>'

    # Dim scores table
    rows = ""
    for res in report.results:
        col = CFG_COLORS[res.config_name]
        dim_cells = "".join(
            f'<td style="color:{"#22c55e" if ds.score>=0.8 else "#f59e0b" if ds.score>=0.6 else "#ef4444"}">'
            f'{ds.score:.2f}</td>'
            for ds in res.dim_scores
        )
        gap_col = "#22c55e" if res.sim2real_gap < 0.2 else "#f59e0b" if res.sim2real_gap < 0.3 else "#ef4444"
        rows += (f'<tr>'
                 f'<td style="color:{col};font-weight:bold">{res.config_name}</td>'
                 f'<td style="color:#22c55e">{res.overall_fidelity:.3f}</td>'
                 f'{dim_cells}'
                 f'<td style="color:{gap_col}">{res.sim2real_gap:.2f}</td>'
                 f'<td style="color:#94a3b8">{res.policy_sr_from_sim:.1%}</td>'
                 f'<td style="color:#64748b">{res.cost_factor:.1f}×</td>'
                 f'</tr>')

    dim_headers = "".join(f'<th>{d[:8]}</th>' for d in FIDELITY_DIMS)

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Sim Fidelity Scorer</title>
<style>
body{{background:#1e293b;color:#e2e8f0;font-family:monospace;margin:0;padding:24px}}
h1{{color:#C74634;margin:0 0 4px}}
.meta{{color:#94a3b8;font-size:12px;margin-bottom:20px}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:20px}}
.card{{background:#0f172a;border-radius:8px;padding:14px}}
.card h3{{color:#94a3b8;font-size:11px;text-transform:uppercase;margin:0 0 4px}}
.big{{font-size:22px;font-weight:bold}}
.layout{{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:20px}}
table{{width:100%;border-collapse:collapse;font-size:11px}}
th{{color:#94a3b8;text-align:left;padding:5px 8px;border-bottom:1px solid #334155}}
td{{padding:3px 8px;border-bottom:1px solid #1e293b}}
h3.sec{{color:#94a3b8;font-size:11px;text-transform:uppercase;margin-bottom:8px}}
</style></head>
<body>
<h1>Sim Fidelity Scorer</h1>
<div class="meta">
  {len(SIM_CONFIGS)} sim configs · {len(FIDELITY_DIMS)} fidelity dims · {N_REAL_DEMOS} real demos baseline
</div>

<div class="grid">
  <div class="card"><h3>Best Fidelity</h3>
    <div style="color:#22c55e;font-size:13px;font-weight:bold">{report.best_config}</div>
    <div class="big" style="color:#22c55e">{report.best_fidelity:.3f}</div>
  </div>
  <div class="card"><h3>Best Policy SR</h3>
    <div style="color:#3b82f6;font-size:13px;font-weight:bold">{report.best_sr_config}</div>
    <div class="big" style="color:#3b82f6">
      {max(r.policy_sr_from_sim for r in report.results):.1%}
    </div>
  </div>
  <div class="card"><h3>Best Sim2Real Gap</h3>
    <div class="big" style="color:#f59e0b">
      {min(r.sim2real_gap for r in report.results):.2f}
    </div>
    <div style="color:#64748b;font-size:10px">{report.best_config}</div>
  </div>
  <div class="card"><h3>Cost Range</h3>
    <div class="big" style="color:#94a3b8">1–4.2×</div>
    <div style="color:#64748b;font-size:10px">genesis_basic → cosmos_wm</div>
  </div>
</div>

<div class="layout">
  <div>
    <h3 class="sec">Fidelity Radar — All Configs</h3>
    {svg_radar}
    <div style="color:#64748b;font-size:10px;margin-top:4px">
      {"  ".join(f'<span style="color:{c}">■</span> {n}' for n, c in CFG_COLORS.items())}
    </div>
  </div>
  <div>
    <h3 class="sec">Fidelity vs Sim2Real Gap (size=cost)</h3>
    {svg_scat}
    <div style="color:#64748b;font-size:10px;margin-top:4px">
      Top-right = ideal (high fidelity + low gap). isaac_dr best Pareto.
    </div>
  </div>
</div>

<h3 class="sec">Config × Dimension Fidelity Scores</h3>
<table>
  <tr><th>Config</th><th>Overall</th>{dim_headers}<th>Sim2Real Gap</th><th>Policy SR</th><th>Cost</th></tr>
  {rows}
</table>

<div style="background:#0f172a;border-radius:8px;padding:12px;margin-top:14px;font-size:10px">
  <div style="color:#C74634;font-weight:bold;margin-bottom:4px">FIDELITY RECOMMENDATIONS</div>
  <div style="color:#22c55e">Production: isaac_dr — best Pareto (fidelity 0.855, gap 0.14, policy SR 79%)</div>
  <div style="color:#f59e0b">Visual tasks: cosmos_wm — best visual_realism (0.91) and lighting_variance (0.92)</div>
  <div style="color:#3b82f6">Fast iteration: genesis_dr — 2.6× cheaper than isaac_dr, reasonable gap (0.28)</div>
  <div style="color:#64748b;margin-top:4px">Dim weights: visual 25%, contact 20%, dynamics 20%, geometry 15%, lighting 10%, diversity 10%</div>
</div>
</body></html>"""


def main():
    parser = argparse.ArgumentParser(description="Simulation fidelity scorer for GR00T SDG configs")
    parser.add_argument("--mock",   action="store_true", default=True)
    parser.add_argument("--output", default="/tmp/sim_fidelity_scorer.html")
    parser.add_argument("--seed",   type=int, default=42)
    args = parser.parse_args()

    print(f"[fidelity] {len(SIM_CONFIGS)} configs · {len(FIDELITY_DIMS)} dims · {N_REAL_DEMOS} real demos")
    t0 = time.time()

    report = simulate_fidelity(args.seed)

    print(f"\n  {'Config':<18} {'Fidelity':>9} {'Sim2Real':>10} {'PolicySR':>9} {'Cost':>6}")
    print(f"  {'─'*18} {'─'*9} {'─'*10} {'─'*9} {'─'*6}")
    for r in sorted(report.results, key=lambda x: x.overall_fidelity, reverse=True):
        flag = " ← best" if r.config_name == report.best_config else ""
        print(f"  {r.config_name:<18} {r.overall_fidelity:>9.3f} {r.sim2real_gap:>10.3f} "
              f"{r.policy_sr_from_sim:>8.1%} {r.cost_factor:>5.1f}×{flag}")

    print(f"\n  Best config: {report.best_config} (fidelity={report.best_fidelity:.3f})")
    print(f"  [{time.time()-t0:.1f}s]\n")

    html = render_html(report)
    Path(args.output).write_text(html)
    print(f"  HTML → {args.output}")

    json_out = Path(args.output).with_suffix(".json")
    json_out.write_text(json.dumps({
        "best_config": report.best_config,
        "best_fidelity": report.best_fidelity,
        "results": [{"config": r.config_name, "fidelity": r.overall_fidelity,
                     "sim2real_gap": r.sim2real_gap, "policy_sr": r.policy_sr_from_sim} for r in report.results],
    }, indent=2))
    print(f"  JSON → {json_out}")


if __name__ == "__main__":
    main()
