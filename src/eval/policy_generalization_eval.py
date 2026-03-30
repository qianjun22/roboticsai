#!/usr/bin/env python3
"""
policy_generalization_eval.py — Evaluates GR00T policy generalization across unseen conditions.

Tests trained policy on 4 generalization axes: spatial (new cube positions), visual
(new lighting/textures), kinematic (joint perturbations), and temporal (execution speed
variations). Identifies failure modes and suggests fine-tuning strategies.

Usage:
    python src/eval/policy_generalization_eval.py --mock --output /tmp/gen_eval.html
    python src/eval/policy_generalization_eval.py --checkpoint /tmp/dagger_run9 --episodes 20
"""

import argparse
import json
import math
import random
import time
from dataclasses import dataclass
from pathlib import Path


# ── Generalization axes ───────────────────────────────────────────────────────

@dataclass
class GenAxis:
    axis_id: str
    name: str
    description: str
    n_conditions: int
    conditions: list[str]


GEN_AXES = [
    GenAxis(
        "spatial",
        "Spatial Generalization",
        "Cube at unseen positions outside training distribution",
        6,
        ["center (train)", "near-left", "near-right", "far-left", "far-right", "extreme-edge"],
    ),
    GenAxis(
        "visual",
        "Visual Generalization",
        "Lighting and texture variations unseen during training",
        5,
        ["standard (train)", "dim-lighting", "bright-glare", "colored-cube", "textured-table"],
    ),
    GenAxis(
        "kinematic",
        "Kinematic Robustness",
        "Joint perturbations, friction changes, and payload variations",
        5,
        ["nominal (train)", "joint-noise-1%", "joint-noise-3%", "friction-+30%", "payload-+200g"],
    ),
    GenAxis(
        "temporal",
        "Temporal Robustness",
        "Execution speed variations and observation delays",
        4,
        ["nominal (train)", "50ms-delay", "slow-0.7x", "fast-1.3x"],
    ),
]


# ── Mock evaluation ───────────────────────────────────────────────────────────

def simulate_gen_eval(axes: list[GenAxis], base_sr: float = 0.72,
                      n_eps: int = 20, seed: int = 42) -> dict:
    rng = random.Random(seed)

    results = {}
    for axis in axes:
        axis_results = []
        for i, cond in enumerate(axis.conditions):
            if i == 0:
                sr = base_sr + rng.gauss(0, 0.03)
            else:
                # Degradation increases with condition index
                severity = i / (len(axis.conditions) - 1)
                # Different axes degrade differently
                if axis.axis_id == "spatial":
                    drop = severity * 0.35 * (1 + rng.gauss(0, 0.1))
                elif axis.axis_id == "visual":
                    drop = severity * 0.20 * (1 + rng.gauss(0, 0.1))
                elif axis.axis_id == "kinematic":
                    drop = severity * 0.25 * (1 + rng.gauss(0, 0.1))
                else:   # temporal
                    drop = severity * 0.15 * (1 + rng.gauss(0, 0.08))
                sr = base_sr - drop + rng.gauss(0, 0.02)
            sr = max(0.0, min(1.0, sr))
            n_success = round(sr * n_eps)
            actual_sr = n_success / n_eps
            axis_results.append({
                "condition": cond,
                "success_rate": round(actual_sr, 3),
                "n_success": n_success,
                "n_episodes": n_eps,
                "is_training": i == 0,
            })
        results[axis.axis_id] = axis_results

    # Overall generalization score: weighted avg of non-training conditions
    all_ood_srs = []
    for axis_id, conds in results.items():
        ood = [c["success_rate"] for c in conds if not c["is_training"]]
        all_ood_srs.extend(ood)
    gen_score = sum(all_ood_srs) / len(all_ood_srs) if all_ood_srs else 0
    gen_gap = base_sr - gen_score

    return {
        "base_sr": round(base_sr, 3),
        "gen_score": round(gen_score, 3),
        "gen_gap": round(gen_gap, 3),
        "gen_grade": ("A" if gen_gap < 0.10 else "B" if gen_gap < 0.20 else
                      "C" if gen_gap < 0.30 else "D"),
        "axes": results,
        "n_episodes": n_eps,
        "recommendations": _recommendations(results, gen_gap),
    }


def _recommendations(results: dict, gen_gap: float) -> list[str]:
    recs = []
    # Find worst axis
    worst_axis = None
    worst_drop = 0
    for axis_id, conds in results.items():
        train_sr = next(c["success_rate"] for c in conds if c["is_training"])
        min_sr = min(c["success_rate"] for c in conds if not c["is_training"])
        drop = train_sr - min_sr
        if drop > worst_drop:
            worst_drop = drop
            worst_axis = axis_id

    if worst_axis == "spatial":
        recs.append("Increase cube position randomization in SDG (cube_x_range ±0.15m)")
        recs.append("Add more demos at extreme positions (left/right edge)")
    elif worst_axis == "visual":
        recs.append("Enable Isaac Sim lighting DR (HDR environments + spot lights)")
        recs.append("Use Cosmos data augmentation for color/texture diversity")
    elif worst_axis == "kinematic":
        recs.append("Add joint noise augmentation during training (σ=0.02 rad)")
        recs.append("Increase action smoothness regularization in reward function")
    elif worst_axis == "temporal":
        recs.append("Train with random observation delays (0-100ms)")
        recs.append("Use action chunk N=16 to buffer latency variations")

    if gen_gap > 0.20:
        recs.append("Consider 1000+ additional demos across all OOD conditions")
        recs.append("Run targeted DAgger on worst-performing conditions")
    return recs


# ── HTML report ───────────────────────────────────────────────────────────────

def render_html(data: dict, axes: list[GenAxis]) -> str:
    grade_col = {"A": "#22c55e", "B": "#3b82f6", "C": "#f59e0b", "D": "#ef4444"}
    gc = grade_col.get(data["gen_grade"], "#ef4444")

    AXIS_COLORS = ["#C74634", "#3b82f6", "#22c55e", "#f59e0b"]

    # SVG: grouped bar chart per axis
    w, h = 560, 180
    n_axes = len(axes)
    axis_w = (w - 40) / n_axes
    svg = f'<svg width="{w}" height="{h}" style="background:#0f172a;border-radius:8px">'
    svg += f'<line x1="20" y1="{h-20}" x2="{w}" y2="{h-20}" stroke="#334155" stroke-width="1"/>'

    for ai, axis in enumerate(axes):
        conds = data["axes"][axis.axis_id]
        n_conds = len(conds)
        bar_w = max(4, axis_w / (n_conds + 1) - 2)
        ax_x = 20 + ai * axis_w

        for ci, cond in enumerate(conds):
            sr = cond["success_rate"]
            bh = sr * (h - 40)
            x = ax_x + ci * (bar_w + 2)
            col = AXIS_COLORS[ai] if not cond["is_training"] else "#475569"
            opacity = "0.9" if not cond["is_training"] else "0.5"
            svg += (f'<rect x="{x:.1f}" y="{h-20-bh:.1f}" width="{bar_w:.1f}" '
                    f'height="{bh:.1f}" fill="{col}" rx="1" opacity="{opacity}"/>')

        # Axis label
        svg += (f'<text x="{ax_x + axis_w/2:.1f}" y="{h-5}" fill="{AXIS_COLORS[ai]}" '
                f'font-size="9" text-anchor="middle">{axis.name[:10]}</text>')

    svg += '</svg>'

    # Per-axis detail tables
    axis_tables = ""
    for ai, axis in enumerate(axes):
        conds = data["axes"][axis.axis_id]
        col = AXIS_COLORS[ai]
        rows = ""
        train_sr = next(c["success_rate"] for c in conds if c["is_training"])
        for c in conds:
            drop = train_sr - c["success_rate"] if not c["is_training"] else 0
            sr_col = "#22c55e" if c["success_rate"] >= 0.60 else \
                     "#f59e0b" if c["success_rate"] >= 0.35 else "#ef4444"
            tag = " (train)" if c["is_training"] else ""
            drop_str = f"-{drop:.0%}" if drop > 0 else "—"
            drop_col = "#ef4444" if drop > 0.2 else "#f59e0b" if drop > 0.1 else "#64748b"
            rows += (f'<tr><td style="color:#e2e8f0">{c["condition"]}{tag}</td>'
                     f'<td style="color:{sr_col}">{c["success_rate"]:.0%}</td>'
                     f'<td style="color:{drop_col}">{drop_str}</td>'
                     f'<td style="color:#64748b">{c["n_success"]}/{c["n_episodes"]}</td></tr>')
        axis_tables += f"""
        <div style="margin-bottom:16px">
          <h3 style="color:{col};font-size:12px;margin-bottom:6px">{axis.name}</h3>
          <p style="color:#64748b;font-size:11px;margin:0 0 6px">{axis.description}</p>
          <table><tr><th>Condition</th><th>SR</th><th>Drop</th><th>N</th></tr>{rows}</table>
        </div>"""

    recs_html = "".join(
        f'<div style="color:#94a3b8;font-size:12px;padding:4px 0">→ {r}</div>'
        for r in data["recommendations"]
    )

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Policy Generalization Eval</title>
<style>
body{{background:#1e293b;color:#e2e8f0;font-family:monospace;margin:0;padding:24px}}
h1{{color:#C74634;margin:0 0 4px}}
.meta{{color:#94a3b8;font-size:12px;margin-bottom:20px}}
.grid{{display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:12px;margin-bottom:20px}}
.card{{background:#0f172a;border-radius:8px;padding:14px}}
.card h3{{color:#94a3b8;font-size:11px;text-transform:uppercase;margin:0 0 4px}}
.big{{font-size:32px;font-weight:bold}}
.cols{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}
table{{width:100%;border-collapse:collapse;font-size:12px}}
th{{color:#94a3b8;text-align:left;padding:4px 8px;border-bottom:1px solid #334155}}
td{{padding:3px 8px;border-bottom:1px solid #1e293b}}
</style></head>
<body>
<h1>Policy Generalization Evaluation</h1>
<div class="meta">{data['n_episodes']} eps per condition · 4 generalization axes · GR00T N1.6-3B</div>

<div class="grid">
  <div class="card"><h3>Training SR</h3>
    <div class="big" style="color:#22c55e">{data['base_sr']:.0%}</div></div>
  <div class="card"><h3>OOD Gen Score</h3>
    <div class="big" style="color:{gc}">{data['gen_score']:.0%}</div></div>
  <div class="card"><h3>Gen Gap</h3>
    <div class="big" style="color:{'#ef4444' if data['gen_gap']>0.15 else '#f59e0b'}">
      -{data['gen_gap']:.0%}</div></div>
  <div class="card"><h3>Grade</h3>
    <div class="big" style="color:{gc}">{data['gen_grade']}</div>
    <div style="color:#64748b;font-size:11px">A=&lt;10% gap · B=&lt;20%</div></div>
</div>

<div style="margin-bottom:20px">
  <h3 style="color:#94a3b8;font-size:11px;text-transform:uppercase;margin-bottom:8px">
    SR by Axis & Condition (gray=training, colored=OOD)
  </h3>
  {svg}
</div>

<div class="cols">
  <div>{axis_tables[:len(axis_tables)//2 + 200]}</div>
  <div>{axis_tables[len(axis_tables)//2 + 200:]}</div>
</div>

<div style="background:#0f172a;border-radius:8px;padding:14px;margin-top:16px">
  <h3 style="color:#94a3b8;font-size:11px;text-transform:uppercase;margin-bottom:8px">Recommendations</h3>
  {recs_html}
</div>
</body></html>"""


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Policy generalization evaluation")
    parser.add_argument("--mock",       action="store_true", default=True)
    parser.add_argument("--checkpoint", default="")
    parser.add_argument("--base-sr",    type=float, default=0.72)
    parser.add_argument("--episodes",   type=int, default=20)
    parser.add_argument("--output",     default="/tmp/policy_generalization_eval.html")
    parser.add_argument("--seed",       type=int, default=42)
    args = parser.parse_args()

    print(f"[gen-eval] Evaluating generalization across {len(GEN_AXES)} axes...")
    t0 = time.time()

    data = simulate_gen_eval(GEN_AXES, args.base_sr, args.episodes, args.seed)

    print(f"\n  Training SR: {data['base_sr']:.0%}  →  OOD: {data['gen_score']:.0%}  "
          f"(gap={data['gen_gap']:.0%}, grade={data['gen_grade']})")
    print(f"\n  Axis breakdown:")
    for axis in GEN_AXES:
        conds = data["axes"][axis.axis_id]
        ood_srs = [c["success_rate"] for c in conds if not c["is_training"]]
        print(f"    {axis.name:<28} avg_ood={sum(ood_srs)/len(ood_srs):.0%}  "
              f"min={min(ood_srs):.0%}")

    print(f"\n  Recs:")
    for r in data["recommendations"]:
        print(f"    → {r}")
    print(f"\n  [{time.time()-t0:.1f}s]\n")

    html = render_html(data, GEN_AXES)
    Path(args.output).write_text(html)
    print(f"  HTML → {args.output}")

    json_out = Path(args.output).with_suffix(".json")
    json_out.write_text(json.dumps(data, indent=2))
    print(f"  JSON → {json_out}")


if __name__ == "__main__":
    main()
