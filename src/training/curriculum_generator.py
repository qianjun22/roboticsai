"""OCI Robot Cloud — Automated Curriculum Learning Stage Generator (port 8141)."""
from __future__ import annotations

from typing import Optional

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
except ImportError:  # pragma: no cover
    FastAPI = None  # type: ignore
    HTTPException = None  # type: ignore
    HTMLResponse = None  # type: ignore
    JSONResponse = None  # type: ignore
    uvicorn = None  # type: ignore

# ---------------------------------------------------------------------------
# Static data
# ---------------------------------------------------------------------------

TASK_INFO: dict = {
    "name": "cube_lift",
    "robot": "Franka Panda",
    "total_stages": 5,
}

STAGES: list[dict] = [
    {
        "id": "stage_1_reach",
        "index": 1,
        "difficulty": 0.15,
        "target_sr": 0.85,
        "reward_weights": {"reach": 0.8, "grasp": 0.1, "lift": 0.1, "place": 0.0},
        "episodes": 200,
        "status": "COMPLETED",
        "achieved_sr": 0.91,
        "current_episode": 200,
    },
    {
        "id": "stage_2_grasp",
        "index": 2,
        "difficulty": 0.35,
        "target_sr": 0.75,
        "reward_weights": {"reach": 0.2, "grasp": 0.6, "lift": 0.2, "place": 0.0},
        "episodes": 400,
        "status": "COMPLETED",
        "achieved_sr": 0.78,
        "current_episode": 400,
    },
    {
        "id": "stage_3_lift_low",
        "index": 3,
        "difficulty": 0.55,
        "target_sr": 0.65,
        "reward_weights": {"reach": 0.1, "grasp": 0.3, "lift": 0.6, "place": 0.0},
        "episodes": 600,
        "status": "ACTIVE",
        "achieved_sr": 0.71,
        "current_episode": 847,
    },
    {
        "id": "stage_4_lift_target",
        "index": 4,
        "difficulty": 0.75,
        "target_sr": 0.80,
        "reward_weights": {"reach": 0.05, "grasp": 0.15, "lift": 0.55, "place": 0.25},
        "episodes": 800,
        "status": "PENDING",
        "achieved_sr": None,
        "current_episode": 0,
    },
    {
        "id": "stage_5_precision",
        "index": 5,
        "difficulty": 0.92,
        "target_sr": 0.85,
        "reward_weights": {"reach": 0.05, "grasp": 0.1, "lift": 0.3, "place": 0.55},
        "episodes": 1000,
        "status": "PENDING",
        "achieved_sr": None,
        "current_episode": 0,
    },
]

ADVANCEMENT_LOGIC: dict = {
    "threshold_multiplier": 0.95,
    "consecutive_eval_windows": 3,
    "description": "Auto-advance when achieved_sr > target_sr × 0.95 for 3 consecutive eval windows",
}

RECOMMENDATION: str = "Advance to stage_4 when stage_3 SR reaches 76% (current: 71%, gap: 5pp)"

COMPONENT_COLORS: dict[str, str] = {
    "reach": "#38bdf8",
    "grasp": "#C74634",
    "lift": "#22c55e",
    "place": "#a78bfa",
}

STATUS_COLORS: dict[str, str] = {
    "COMPLETED": "#22c55e",
    "ACTIVE": "#38bdf8",
    "PENDING": "#475569",
}

# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------

def _difficulty_svg() -> str:
    """680x200 staircase chart — difficulty progression with target_sr circles."""
    W, H = 680, 200
    pad_left, pad_right, pad_top, pad_bot = 50, 20, 20, 35
    chart_w = W - pad_left - pad_right
    chart_h = H - pad_top - pad_bot

    # x positions: evenly spaced per stage
    n = len(STAGES)
    xs = [pad_left + int(chart_w * (i + 0.5) / n) for i in range(n)]

    def y_for(val: float) -> int:
        return pad_top + chart_h - int(chart_h * val)

    lines = [
        f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg">',
        f'<rect width="{W}" height="{H}" fill="#1e293b" rx="8"/>',
    ]

    # y-axis grid + labels
    for val in [0.0, 0.25, 0.5, 0.75, 1.0]:
        y = y_for(val)
        lines.append(f'<line x1="{pad_left}" y1="{y}" x2="{pad_left + chart_w}" y2="{y}" stroke="#334155" stroke-width="1" stroke-dasharray="4,4"/>')
        lines.append(f'<text x="{pad_left - 6}" y="{y + 4}" text-anchor="end" fill="#64748b" font-size="10" font-family="monospace">{val:.2f}</text>')

    # staircase segments
    for i, stage in enumerate(STAGES):
        col = STATUS_COLORS[stage["status"]]
        x_start = pad_left if i == 0 else xs[i - 1]
        x_end = xs[i]
        prev_diff = STAGES[i - 1]["difficulty"] if i > 0 else stage["difficulty"]
        y_prev = y_for(prev_diff)
        y_curr = y_for(stage["difficulty"])
        if i > 0:
            # vertical step
            lines.append(f'<line x1="{xs[i-1]}" y1="{y_prev}" x2="{xs[i-1]}" y2="{y_curr}" stroke="{col}" stroke-width="2.5"/>')
        # horizontal plateau
        lines.append(f'<line x1="{x_start if i == 0 else xs[i-1]}" y1="{y_curr}" x2="{x_end}" y2="{y_curr}" stroke="{col}" stroke-width="2.5"/>')

    # difficulty dots + labels
    for i, stage in enumerate(STAGES):
        col = STATUS_COLORS[stage["status"]]
        x = xs[i]
        y = y_for(stage["difficulty"])
        lines.append(f'<circle cx="{x}" cy="{y}" r="5" fill="{col}"/>')
        lines.append(f'<text x="{x}" y="{y - 10}" text-anchor="middle" fill="{col}" font-size="10" font-family="monospace">{stage["difficulty"]}</text>')

    # target_sr circles (hollow)
    for i, stage in enumerate(STAGES):
        x = xs[i]
        y = y_for(stage["target_sr"])
        lines.append(f'<circle cx="{x}" cy="{y}" r="4" fill="none" stroke="#f59e0b" stroke-width="1.5"/>')

    # x-axis labels
    for i, stage in enumerate(STAGES):
        lines.append(f'<text x="{xs[i]}" y="{H - 6}" text-anchor="middle" fill="#94a3b8" font-size="10" font-family="monospace">{stage["id"].replace("_", " ")[:12]}</text>')

    # legend
    for i, (label, col) in enumerate([("Completed", "#22c55e"), ("Active", "#38bdf8"), ("Pending", "#475569"), ("Target SR", "#f59e0b")]):
        lx = pad_left + 20 + i * 150
        if label == "Target SR":
            lines.append(f'<circle cx="{lx}" cy="{pad_top + 8}" r="4" fill="none" stroke="#f59e0b" stroke-width="1.5"/>')
        else:
            lines.append(f'<circle cx="{lx}" cy="{pad_top + 8}" r="5" fill="{col}"/>')
        lines.append(f'<text x="{lx + 10}" y="{pad_top + 12}" fill="{col}" font-size="10" font-family="monospace">{label}</text>')

    lines.append("</svg>")
    return "\n".join(lines)


def _reward_weight_svg() -> str:
    """680x200 stacked bar chart — reward weights per stage."""
    W, H = 680, 200
    pad_left, pad_right, pad_top, pad_bot = 50, 20, 20, 35
    chart_w = W - pad_left - pad_right
    chart_h = H - pad_top - pad_bot
    n = len(STAGES)
    bar_w = int(chart_w / n) - 10
    components = ["reach", "grasp", "lift", "place"]

    lines = [
        f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg">',
        f'<rect width="{W}" height="{H}" fill="#1e293b" rx="8"/>',
    ]

    # y-axis grid
    for val in [0.0, 0.25, 0.5, 0.75, 1.0]:
        y = pad_top + chart_h - int(chart_h * val)
        lines.append(f'<line x1="{pad_left}" y1="{y}" x2="{pad_left + chart_w}" y2="{y}" stroke="#334155" stroke-width="1" stroke-dasharray="4,4"/>')
        lines.append(f'<text x="{pad_left - 6}" y="{y + 4}" text-anchor="end" fill="#64748b" font-size="10" font-family="monospace">{val:.2f}</text>')

    for i, stage in enumerate(STAGES):
        x = pad_left + int(chart_w * i / n) + 5
        cumulative = 0.0
        for comp in components:
            w = stage["reward_weights"].get(comp, 0.0)
            if w <= 0:
                cumulative += w
                continue
            seg_h = int(chart_h * w)
            y = pad_top + chart_h - int(chart_h * (cumulative + w))
            col = COMPONENT_COLORS[comp]
            lines.append(f'<rect x="{x}" y="{y}" width="{bar_w}" height="{seg_h}" fill="{col}" opacity="0.85"/>')
            if seg_h > 14:
                lines.append(f'<text x="{x + bar_w // 2}" y="{y + seg_h // 2 + 4}" text-anchor="middle" fill="#0f172a" font-size="9" font-weight="bold" font-family="monospace">{w:.2f}</text>')
            cumulative += w
        # x label
        cx = x + bar_w // 2
        lines.append(f'<text x="{cx}" y="{H - 6}" text-anchor="middle" fill="#94a3b8" font-size="10" font-family="monospace">S{stage["index"]}</text>')

    # legend
    for i, comp in enumerate(components):
        lx = pad_left + 20 + i * 150
        lines.append(f'<rect x="{lx}" y="{pad_top}" width="12" height="12" fill="{COMPONENT_COLORS[comp]}" rx="2"/>')
        lines.append(f'<text x="{lx + 16}" y="{pad_top + 10}" fill="{COMPONENT_COLORS[comp]}" font-size="10" font-family="monospace">{comp}</text>')

    lines.append("</svg>")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def _dashboard_html() -> str:
    diff_svg = _difficulty_svg()
    reward_svg = _reward_weight_svg()

    stage_rows = ""
    for s in STAGES:
        col = STATUS_COLORS[s["status"]]
        ach = f"{s['achieved_sr'] * 100:.0f}%" if s["achieved_sr"] is not None else "—"
        prog = f"{s['current_episode']} / {s['episodes']}" if s["status"] != "PENDING" else f"0 / {s['episodes']}"
        rw = " | ".join(f"{k}:{v:.2f}" for k, v in s["reward_weights"].items() if v > 0)
        stage_rows += f"""
        <tr>
          <td style="color:#e2e8f0;font-family:monospace">{s['id']}</td>
          <td style="color:{col};font-weight:600">{s['status']}</td>
          <td style="color:#38bdf8;font-family:monospace">{s['difficulty']}</td>
          <td style="color:#f59e0b;font-family:monospace">{s['target_sr']:.0%}</td>
          <td style="color:#22c55e;font-family:monospace">{ach}</td>
          <td style="color:#94a3b8;font-size:12px">{prog}</td>
          <td style="color:#64748b;font-size:12px;font-family:monospace">{rw}</td>
        </tr>"""

    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>OCI Robot Cloud — Curriculum Generator</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; padding: 24px; }}
    h1 {{ color: #C74634; font-size: 22px; margin-bottom: 4px; }}
    .sub {{ color: #64748b; font-size: 13px; margin-bottom: 24px; }}
    .card {{ background: #1e293b; border-radius: 10px; padding: 20px; margin-bottom: 20px; }}
    h2 {{ color: #38bdf8; font-size: 15px; margin-bottom: 14px; text-transform: uppercase; letter-spacing: 1px; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th {{ color: #64748b; font-size: 11px; text-transform: uppercase; letter-spacing: 1px; padding: 6px 10px; text-align: left; border-bottom: 1px solid #334155; }}
    td {{ padding: 8px 10px; border-bottom: 1px solid #1e293b; font-size: 13px; }}
    .grid2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
    .reco-box {{ background: #0f172a; border-left: 3px solid #38bdf8; padding: 14px 18px; border-radius: 4px; }}
    .adv-box {{ background: #0f172a; border-left: 3px solid #22c55e; padding: 14px 18px; border-radius: 4px; font-size: 13px; line-height: 2; }}
    .label {{ color: #94a3b8; }} .val {{ color: #38bdf8; font-family: monospace; }}
  </style>
</head>
<body>
  <h1>OCI Robot Cloud — Curriculum Stage Generator</h1>
  <div class="sub">Port 8141 · Task: cube_lift · Robot: Franka Panda · 5 auto-generated stages</div>

  <div class="card" style="background:#1e293b;border-left:4px solid #38bdf8;">
    <div class="reco-box">
      <span style="color:#38bdf8;font-size:14px;font-weight:600">Next Recommendation: </span>
      <span style="color:#e2e8f0;font-size:14px">{RECOMMENDATION}</span>
    </div>
  </div>

  <div class="grid2">
    <div class="card">
      <h2>Difficulty Progression</h2>
      {diff_svg}
    </div>
    <div class="card">
      <h2>Reward Weight Breakdown</h2>
      {reward_svg}
    </div>
  </div>

  <div class="card">
    <h2>Stage Summary</h2>
    <table>
      <thead><tr><th>Stage</th><th>Status</th><th>Difficulty</th><th>Target SR</th><th>Achieved SR</th><th>Episodes</th><th>Reward Weights</th></tr></thead>
      <tbody>{stage_rows}</tbody>
    </table>
  </div>

  <div class="card">
    <h2>Advancement Logic</h2>
    <div class="adv-box">
      <span class="label">Rule: </span><span class="val">{ADVANCEMENT_LOGIC['description']}</span><br>
      <span class="label">Threshold multiplier: </span><span class="val">{ADVANCEMENT_LOGIC['threshold_multiplier']}</span> &nbsp;|
      <span class="label"> Consecutive windows required: </span><span class="val">{ADVANCEMENT_LOGIC['consecutive_eval_windows']}</span>
    </div>
  </div>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

if FastAPI is not None:
    app = FastAPI(
        title="OCI Robot Cloud — Curriculum Generator",
        description="Automated curriculum learning stage generator for robot manipulation tasks.",
        version="1.0.0",
    )

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return _dashboard_html()

    @app.get("/stages")
    async def list_stages():
        return {"task": TASK_INFO, "stages": STAGES, "total": len(STAGES)}

    @app.get("/stages/{stage_id}")
    async def get_stage(stage_id: str):
        stage = next((s for s in STAGES if s["id"] == stage_id), None)
        if stage is None:
            raise HTTPException(status_code=404, detail=f"Stage '{stage_id}' not found")
        return stage

    @app.get("/recommendation")
    async def get_recommendation():
        active = next((s for s in STAGES if s["status"] == "ACTIVE"), None)
        return {
            "recommendation": RECOMMENDATION,
            "advancement_logic": ADVANCEMENT_LOGIC,
            "active_stage": active,
        }

    @app.post("/advance")
    async def advance_stage():
        active = next((s for s in STAGES if s["status"] == "ACTIVE"), None)
        if active is None:
            return {"status": "no_active_stage", "message": "No stage is currently ACTIVE."}
        threshold = active["target_sr"] * ADVANCEMENT_LOGIC["threshold_multiplier"]
        achieved = active["achieved_sr"] or 0.0
        if achieved < threshold:
            return {
                "status": "not_ready",
                "stage": active["id"],
                "achieved_sr": achieved,
                "required_sr": round(threshold, 3),
                "gap_pp": round((threshold - achieved) * 100, 1),
                "message": f"Stage not ready for advancement. Gap: {round((threshold - achieved) * 100, 1)}pp",
            }
        return {
            "status": "ready",
            "stage": active["id"],
            "achieved_sr": achieved,
            "required_sr": round(threshold, 3),
            "message": "Stage meets advancement criteria. Advance manually or via orchestrator.",
            "next_stage": next((s["id"] for s in STAGES if s["status"] == "PENDING"), None),
        }


if __name__ == "__main__":
    if uvicorn is None:
        raise RuntimeError("uvicorn not installed")
    uvicorn.run("curriculum_generator:app", host="0.0.0.0", port=8141, reload=False)
