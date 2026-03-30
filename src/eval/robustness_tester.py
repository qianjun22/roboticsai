"""Policy Robustness Stress Tester — OCI Robot Cloud  (port 8143)"""

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
except ImportError:
    FastAPI = None

from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Static data
# ---------------------------------------------------------------------------

CATEGORIES = [
    {
        "id": "lighting_variation",
        "name": "Lighting Variation",
        "sr_clean": 0.78,
        "sr_stressed": 0.61,
        "drop_pp": -17,
        "grade": "C",
        "episodes": 20,
        "perturbation": "Random ambient 0-500 lux + 3 point lights",
    },
    {
        "id": "object_pose_noise",
        "name": "Object Pose Noise",
        "sr_clean": 0.78,
        "sr_stressed": 0.72,
        "drop_pp": -6,
        "grade": "A",
        "episodes": 20,
        "perturbation": "\u00b15cm position, \u00b115\u00b0 rotation",
    },
    {
        "id": "latency_injection",
        "name": "Latency Injection",
        "sr_clean": 0.78,
        "sr_stressed": 0.69,
        "drop_pp": -9,
        "grade": "B",
        "episodes": 20,
        "perturbation": "50-150ms random action delay",
    },
    {
        "id": "gripper_noise",
        "name": "Gripper Noise",
        "sr_clean": 0.78,
        "sr_stressed": 0.71,
        "drop_pp": -7,
        "grade": "A",
        "episodes": 20,
        "perturbation": "\u00b15% grasp force, \u00b12mm width noise",
    },
    {
        "id": "background_clutter",
        "name": "Background Clutter",
        "sr_clean": 0.78,
        "sr_stressed": 0.55,
        "drop_pp": -23,
        "grade": "D",
        "episodes": 20,
        "perturbation": "5-8 random distractor objects",
    },
    {
        "id": "combined_attack",
        "name": "Combined Attack",
        "sr_clean": 0.78,
        "sr_stressed": 0.41,
        "drop_pp": -37,
        "grade": "F",
        "episodes": 20,
        "perturbation": "All perturbations simultaneously",
    },
]

GRADE_SCORE = {"A": 95, "B": 80, "C": 65, "D": 50, "F": 20}
GRADE_COLOR = {"A": "#4ade80", "B": "#38bdf8", "C": "#f59e0b", "D": "#fb923c", "F": "#C74634"}

AVG_ROBUSTNESS_SCORE = sum(GRADE_SCORE[c["grade"]] for c in CATEGORIES) // len(CATEGORIES)  # 67

HARDENING_PLAN = [
    {
        "priority": 1,
        "action": "Domain Randomization for Lighting",
        "target": "lighting_variation",
        "expected_improvement": "+10pp",
        "effort": "Medium",
        "description": "Add 200-800 lux variation + random shadow masks during SDG. Retrain 2k extra demos.",
    },
    {
        "priority": 2,
        "action": "Distractor Object Training",
        "target": "background_clutter",
        "expected_improvement": "+15pp",
        "effort": "High",
        "description": "Inject 4-10 YCB distractor objects in simulation. Train for 500 additional fine-tune steps.",
    },
    {
        "priority": 3,
        "action": "Combined-Attack Curriculum",
        "target": "combined_attack",
        "expected_improvement": "+20pp",
        "effort": "High",
        "description": "Progressive curriculum: single perturbation → pairwise → full combined. 3-stage training schedule.",
    },
]

# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------

def _bar_chart_svg() -> str:
    W, H = 680, 200
    pad_l, pad_r, pad_t, pad_b = 50, 20, 20, 50
    n = len(CATEGORIES)
    chart_w = W - pad_l - pad_r
    chart_h = H - pad_t - pad_b
    group_w = chart_w / n
    bar_w = group_w * 0.35
    gap = group_w * 0.07

    lines = [
        f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg" style="background:#1e293b;border-radius:8px">',
    ]

    # y-grid
    for v in [0, 0.2, 0.4, 0.6, 0.8, 1.0]:
        y = pad_t + chart_h - v * chart_h
        lines.append(f'<line x1="{pad_l}" y1="{y:.1f}" x2="{W-pad_r}" y2="{y:.1f}" stroke="#334155" stroke-width="1" stroke-dasharray="3,3"/>')
        lines.append(f'<text x="{pad_l-4}" y="{y+4:.1f}" fill="#94a3b8" font-size="10" text-anchor="end">{int(v*100)}%</text>')

    for i, cat in enumerate(CATEGORIES):
        cx = pad_l + i * group_w + group_w / 2
        # clean bar
        bx_clean = cx - bar_w - gap / 2
        bh_clean = cat["sr_clean"] * chart_h
        by_clean = pad_t + chart_h - bh_clean
        lines.append(f'<rect x="{bx_clean:.1f}" y="{by_clean:.1f}" width="{bar_w:.1f}" height="{bh_clean:.1f}" rx="3" fill="#38bdf8" opacity="0.85"/>')

        # stressed bar (color by grade)
        grade_col = GRADE_COLOR[cat["grade"]]
        bx_str = cx + gap / 2
        bh_str = cat["sr_stressed"] * chart_h
        by_str = pad_t + chart_h - bh_str
        lines.append(f'<rect x="{bx_str:.1f}" y="{by_str:.1f}" width="{bar_w:.1f}" height="{bh_str:.1f}" rx="3" fill="{grade_col}" opacity="0.85"/>')

        # x label
        short = cat["id"].replace("_", " ")
        lines.append(f'<text x="{cx:.1f}" y="{H-pad_b+14}" fill="#94a3b8" font-size="9" text-anchor="middle">{short}</text>')

    # legend
    lines.append(f'<rect x="{pad_l}" y="6" width="10" height="10" fill="#38bdf8" rx="2"/>')
    lines.append(f'<text x="{pad_l+13}" y="15" fill="#94a3b8" font-size="10">Clean SR</text>')
    lines.append(f'<rect x="{pad_l+90}" y="6" width="10" height="10" fill="#94a3b8" rx="2"/>')
    lines.append(f'<text x="{pad_l+103}" y="15" fill="#94a3b8" font-size="10">Stressed SR (color=grade)</text>')

    lines.append('</svg>')
    return "\n".join(lines)


def _grade_heatmap_svg() -> str:
    W, H = 680, 100
    n = len(CATEGORIES)
    cell_w = W / n
    cell_h = H

    lines = [
        f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg" style="border-radius:8px;overflow:hidden">',
    ]
    for i, cat in enumerate(CATEGORIES):
        col = GRADE_COLOR[cat["grade"]]
        x = i * cell_w
        lines.append(f'<rect x="{x:.1f}" y="0" width="{cell_w:.1f}" height="{cell_h}" fill="{col}" opacity="0.25"/>')
        lines.append(f'<rect x="{x:.1f}" y="0" width="{cell_w:.1f}" height="4" fill="{col}"/>')
        cx = x + cell_w / 2
        lines.append(f'<text x="{cx:.1f}" y="32" fill="{col}" font-size="28" font-weight="700" text-anchor="middle">{cat["grade"]}</text>')
        lines.append(f'<text x="{cx:.1f}" y="55" fill="#e2e8f0" font-size="14" font-weight="600" text-anchor="middle">{cat["drop_pp"]}pp</text>')
        short = cat["name"].replace(" ", "\n")
        lines.append(f'<text x="{cx:.1f}" y="73" fill="#94a3b8" font-size="10" text-anchor="middle">{cat["name"].split()[0]}</text>')
        lines.append(f'<text x="{cx:.1f}" y="86" fill="#64748b" font-size="9" text-anchor="middle">{" ".join(cat["name"].split()[1:])}</text>')
    lines.append('</svg>')
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def _build_html() -> str:
    bar_chart = _bar_chart_svg()
    heatmap = _grade_heatmap_svg()

    score_color = "#4ade80" if AVG_ROBUSTNESS_SCORE >= 80 else ("#f59e0b" if AVG_ROBUSTNESS_SCORE >= 60 else "#C74634")

    cat_rows = "".join(
        f'<tr style="border-bottom:1px solid #1e293b">'
        f'<td style="padding:10px 12px;color:#e2e8f0">{c["name"]}</td>'
        f'<td style="padding:10px 12px;color:#38bdf8;text-align:center">{int(c["sr_clean"]*100)}%</td>'
        f'<td style="padding:10px 12px;text-align:center"><span style="color:{GRADE_COLOR[c["grade"]]}">{int(c["sr_stressed"]*100)}%</span></td>'
        f'<td style="padding:10px 12px;color:{GRADE_COLOR[c["grade"]]};font-weight:700;text-align:center">{c["drop_pp"]}pp</td>'
        f'<td style="padding:10px 12px;text-align:center"><span style="background:{GRADE_COLOR[c["grade"]]}22;color:{GRADE_COLOR[c["grade"]]};padding:2px 10px;border-radius:9999px;font-weight:700">{c["grade"]}</span></td>'
        f'<td style="padding:10px 12px;color:#64748b;font-size:11px">{c["perturbation"]}</td>'
        f'</tr>'
        for c in CATEGORIES
    )

    plan_cards = "".join(
        f'<div style="background:#1e293b;border-radius:8px;padding:16px;border-left:3px solid #C74634">'
        f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">'
        f'<span style="color:#C74634;font-weight:700;font-size:13px">#{p["priority"]} {p["action"]}</span>'
        f'<span style="background:#4ade8022;color:#4ade80;padding:2px 8px;border-radius:9999px;font-size:11px">{p["expected_improvement"]}</span>'
        f'</div>'
        f'<div style="color:#94a3b8;font-size:12px;margin-bottom:4px">{p["description"]}</div>'
        f'<div style="color:#64748b;font-size:11px">Target: <span style="color:#38bdf8">{p["target"]}</span> &nbsp;|&nbsp; Effort: {p["effort"]}</div>'
        f'</div>'
        for p in HARDENING_PLAN
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Robustness Tester — OCI Robot Cloud</title>
<style>
  * {{ box-sizing:border-box; margin:0; padding:0 }}
  body {{ background:#0f172a; color:#e2e8f0; font-family:'Segoe UI',system-ui,sans-serif; padding:24px }}
  h1 {{ color:#38bdf8; font-size:22px; margin-bottom:4px }}
  h2 {{ color:#cbd5e1; font-size:15px; margin:24px 0 10px }}
  .sub {{ color:#64748b; font-size:13px }}
  table {{ width:100%; border-collapse:collapse; background:#0f172a; border-radius:8px; overflow:hidden }}
  th {{ background:#1e293b; color:#64748b; font-size:11px; text-transform:uppercase; padding:8px 12px; text-align:left }}
  tr:hover {{ background:#1e293b40 }}
  .badge-port {{ background:#38bdf822; color:#38bdf8; padding:2px 8px; border-radius:9999px; font-size:11px }}
  .plan-grid {{ display:grid; grid-template-columns:1fr; gap:12px; margin-top:8px }}
</style>
</head>
<body>
<div style="display:flex;align-items:center;justify-content:space-between">
  <div>
    <h1>Policy Robustness Stress Tester</h1>
    <p class="sub">OCI Robot Cloud &nbsp;|&nbsp; <span class="badge-port">:8143</span> &nbsp;|&nbsp; {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}</p>
  </div>
  <div style="text-align:right">
    <div style="font-size:42px;font-weight:800;color:{score_color}">{AVG_ROBUSTNESS_SCORE}</div>
    <div style="font-size:12px;color:#64748b">Avg Robustness Score / 100</div>
  </div>
</div>

<h2>Success Rate: Clean vs Stressed</h2>
{bar_chart}

<h2>Grade Heatmap</h2>
{heatmap}

<h2>Category Results</h2>
<table>
  <thead><tr><th>Category</th><th style="text-align:center">SR Clean</th><th style="text-align:center">SR Stressed</th><th style="text-align:center">Drop</th><th style="text-align:center">Grade</th><th>Perturbation</th></tr></thead>
  <tbody>{cat_rows}</tbody>
</table>

<h2>Priority Hardening Plan</h2>
<div class="plan-grid">{plan_cards}</div>

<p style="margin-top:32px;color:#334155;font-size:11px">OCI Robot Cloud · Robustness Stress Tester · port 8143</p>
</body></html>"""


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

if FastAPI is not None:
    app = FastAPI(title="Policy Robustness Stress Tester", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return _build_html()

    @app.get("/categories")
    def list_categories():
        return {"categories": CATEGORIES, "total": len(CATEGORIES)}

    @app.get("/categories/{category_id}")
    def get_category(category_id: str):
        for c in CATEGORIES:
            if c["id"] == category_id:
                return c
        raise HTTPException(status_code=404, detail=f"Category {category_id} not found")

    @app.get("/summary")
    def get_summary():
        grade_dist = {}
        for c in CATEGORIES:
            grade_dist[c["grade"]] = grade_dist.get(c["grade"], 0) + 1
        worst = min(CATEGORIES, key=lambda c: c["sr_stressed"])
        best  = max(CATEGORIES, key=lambda c: c["sr_stressed"])
        return {
            "avg_robustness_score": AVG_ROBUSTNESS_SCORE,
            "categories_tested": len(CATEGORIES),
            "episodes_per_category": 20,
            "grade_distribution": grade_dist,
            "worst_category": worst["id"],
            "best_category": best["id"],
            "baseline_sr": 0.78,
            "mean_stressed_sr": round(sum(c["sr_stressed"] for c in CATEGORIES) / len(CATEGORIES), 3),
        }

    @app.get("/plan")
    def get_hardening_plan():
        return {
            "hardening_plan": HARDENING_PLAN,
            "total_actions": len(HARDENING_PLAN),
            "projected_score_after_hardening": min(AVG_ROBUSTNESS_SCORE + 15, 100),
        }

if __name__ == "__main__":
    if FastAPI is None:
        raise SystemExit("FastAPI not installed. Run: pip install fastapi uvicorn")
    uvicorn.run("robustness_tester:app", host="0.0.0.0", port=8143, reload=True)
