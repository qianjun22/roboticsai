"""Automated Evaluation Scheduler — port 8153."""

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
except ImportError:
    FastAPI = None

# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

JOBS = [
    {
        "id": "eval_001",
        "model": "groot_finetune_v2",
        "task": "cube_lift",
        "episodes": 20,
        "status": "COMPLETED",
        "sr": 0.78,
        "scheduled": "2026-03-30T08:00Z",
        "started": "08:01",
        "duration_min": 12,
    },
    {
        "id": "eval_002",
        "model": "dagger_run10",
        "task": "cube_lift",
        "episodes": 20,
        "status": "RUNNING",
        "sr": None,
        "scheduled": "2026-03-30T14:00Z",
        "started": "14:02",
        "duration_min": None,
    },
    {
        "id": "eval_003",
        "model": "groot_finetune_v3",
        "task": "cube_lift",
        "episodes": 20,
        "status": "QUEUED",
        "sr": None,
        "scheduled": "2026-03-30T18:00Z",
        "eta": "18:00",
        "duration_min": None,
    },
    {
        "id": "eval_004",
        "model": "adapter_r16_v2",
        "task": "cube_lift",
        "episodes": 20,
        "status": "QUEUED",
        "sr": None,
        "scheduled": "2026-03-31T08:00Z",
        "duration_min": None,
    },
    {
        "id": "eval_005",
        "model": "groot_finetune_v2",
        "task": "cube_place",
        "episodes": 20,
        "status": "QUEUED",
        "sr": None,
        "scheduled": "2026-03-31T10:00Z",
        "duration_min": None,
    },
    {
        "id": "eval_006",
        "model": "groot_finetune_v2",
        "task": "push_to_goal",
        "episodes": 20,
        "status": "QUEUED",
        "sr": None,
        "scheduled": "2026-03-31T12:00Z",
        "duration_min": None,
    },
    {
        "id": "eval_007",
        "model": "dagger_run9_v2",
        "task": "cube_lift",
        "episodes": 50,
        "status": "COMPLETED",
        "sr": 0.71,
        "scheduled": "2026-03-29T14:00Z",
        "started": "14:00",
        "duration_min": 28,
    },
    {
        "id": "eval_008",
        "model": "bc_baseline",
        "task": "cube_lift",
        "episodes": 20,
        "status": "COMPLETED",
        "sr": 0.05,
        "scheduled": "2026-03-28T10:00Z",
        "started": "10:01",
        "duration_min": 10,
    },
]

JOBS_BY_ID = {j["id"]: j for j in JOBS}

TRIGGER_RULES = [
    "Auto-schedule eval after every fine-tune completion",
    "Auto-schedule eval after DAgger run milestone (1000 steps)",
    "Weekly regression eval on production model (every Monday 08:00Z)",
]

# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------

# Day range: Mar 28 – Apr 2  (6 days)
DAY_LABELS = ["Mar 28", "Mar 29", "Mar 30", "Mar 31", "Apr 1", "Apr 2"]
# Map scheduled date to day index 0-5
DATE_DAY = {
    "2026-03-28": 0,
    "2026-03-29": 1,
    "2026-03-30": 2,
    "2026-03-31": 3,
    "2026-04-01": 4,
    "2026-04-02": 5,
}

MODEL_ROW = {
    "groot_finetune_v2": 0,
    "groot_finetune_v3": 1,
    "dagger_run10": 2,
    "dagger_run9_v2": 2,
    "adapter_r16_v2": 1,
    "bc_baseline": 0,
}

MODEL_ROWS_DISPLAY = ["groot_finetune_v2 / bc_baseline", "groot_finetune_v3 / adapter_r16_v2", "dagger_run9_v2 / dagger_run10"]

STATUS_COLOR_MAP = {
    "COMPLETED": "#22c55e",
    "RUNNING": "#38bdf8",
    "QUEUED": "#475569",
    "FAILED": "#ef4444",
}


def _svg_eval_calendar() -> str:
    """Eval calendar: x=days Mar28-Apr2, y=3 model rows (680x160)."""
    W, H = 680, 160
    PL, PR, PT, PB = 140, 10, 30, 24
    plot_w = W - PL - PR
    plot_h = H - PT - PB
    n_days = 6
    n_rows = 3
    day_w = plot_w / n_days
    row_h = plot_h / n_rows

    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#1e293b;border-radius:8px">')
    lines.append(f'<text x="{W//2}" y="18" fill="#e2e8f0" font-size="12" text-anchor="middle" font-weight="bold">Eval Calendar — Mar 28 to Apr 2</text>')

    # Grid
    for d in range(n_days + 1):
        x = PL + d * day_w
        lines.append(f'<line x1="{x:.1f}" y1="{PT}" x2="{x:.1f}" y2="{PT+plot_h}" stroke="#334155" stroke-width="1"/>')
    for r in range(n_rows + 1):
        y = PT + r * row_h
        lines.append(f'<line x1="{PL}" y1="{y:.1f}" x2="{PL+plot_w}" y2="{y:.1f}" stroke="#334155" stroke-width="1"/>')

    # Day labels
    for d, label in enumerate(DAY_LABELS):
        x = PL + (d + 0.5) * day_w
        lines.append(f'<text x="{x:.1f}" y="{PT+plot_h+16}" fill="#94a3b8" font-size="9" text-anchor="middle">{label}</text>')

    # Row labels
    for r, label in enumerate(MODEL_ROWS_DISPLAY):
        y = PT + (r + 0.5) * row_h + 4
        lines.append(f'<text x="{PL-4}" y="{y:.1f}" fill="#94a3b8" font-size="9" text-anchor="end">{label}</text>')

    # Job rectangles
    for job in JOBS:
        date_str = job["scheduled"][:10]
        day_idx = DATE_DAY.get(date_str)
        if day_idx is None:
            continue
        row = MODEL_ROW.get(job["model"], 0)
        color = STATUS_COLOR_MAP.get(job["status"], "#6b7280")
        x = PL + day_idx * day_w + 2
        y = PT + row * row_h + 2
        bw = day_w - 4
        bh = row_h - 4
        extra = ""
        if job["status"] == "RUNNING":
            extra = f' style="animation:pulse 1.5s infinite"'
        lines.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{bh:.1f}" fill="{color}" fill-opacity="0.25" stroke="{color}" stroke-width="1.5" rx="3"{extra}/>')
        if job["sr"] is not None:
            lines.append(f'<text x="{x+bw/2:.1f}" y="{y+bh/2+4:.1f}" fill="{color}" font-size="10" text-anchor="middle" font-weight="bold">SR={job["sr"]:.2f}</text>')
        else:
            lines.append(f'<text x="{x+bw/2:.1f}" y="{y+bh/2+4:.1f}" fill="{color}" font-size="9" text-anchor="middle">{job["status"]}</text>')

    lines.append('<style>@keyframes pulse{0%,100%{opacity:1}50%{opacity:0.5}}</style>')
    lines.append('</svg>')
    return '\n'.join(lines)


def _svg_sr_tracking() -> str:
    """SR over time for completed evals (680x180)."""
    W, H = 680, 180
    PL, PR, PT, PB = 60, 30, 24, 40
    plot_w = W - PL - PR
    plot_h = H - PT - PB

    completed = [j for j in JOBS if j["status"] == "COMPLETED"]
    # Sort by date
    order = ["eval_008", "eval_007", "eval_001"]
    pts_ordered = []
    for eid in order:
        for j in completed:
            if j["id"] == eid:
                pts_ordered.append(j)

    x_labels = [j["scheduled"][:10].replace("2026-", "") for j in pts_ordered]
    srs = [j["sr"] for j in pts_ordered]

    x_min, x_max = 0, len(pts_ordered) - 1
    y_min, y_max = 0.0, 1.0

    def px(i):
        if x_max == 0:
            return PL + plot_w // 2
        return PL + (i / x_max) * plot_w

    def py(sr):
        return PT + plot_h - (sr - y_min) / (y_max - y_min) * plot_h

    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#1e293b;border-radius:8px">')
    lines.append(f'<text x="{W//2}" y="16" fill="#e2e8f0" font-size="12" text-anchor="middle" font-weight="bold">SR Progression — Completed Evals</text>')

    # Axes
    lines.append(f'<line x1="{PL}" y1="{PT}" x2="{PL}" y2="{PT+plot_h}" stroke="#475569" stroke-width="1"/>')
    lines.append(f'<line x1="{PL}" y1="{PT+plot_h}" x2="{PL+plot_w}" y2="{PT+plot_h}" stroke="#475569" stroke-width="1"/>')

    # Y ticks
    for sr_tick in [0.0, 0.25, 0.50, 0.75, 1.0]:
        ty = py(sr_tick)
        lines.append(f'<line x1="{PL-4}" y1="{ty:.1f}" x2="{PL}" y2="{ty:.1f}" stroke="#475569"/>')
        lines.append(f'<text x="{PL-6}" y="{ty+4:.1f}" fill="#94a3b8" font-size="10" text-anchor="end">{sr_tick:.2f}</text>')

    # Line
    if len(pts_ordered) >= 2:
        pts_str = ' '.join(f"{px(i):.1f},{py(s):.1f}" for i, s in enumerate(srs))
        lines.append(f'<polyline points="{pts_str}" fill="none" stroke="#38bdf8" stroke-width="2"/>')

    # Dots and labels
    for i, (j, sr) in enumerate(zip(pts_ordered, srs)):
        cx = px(i)
        cy = py(sr)
        lines.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="6" fill="#38bdf8" stroke="#0f172a" stroke-width="2"/>')
        lines.append(f'<text x="{cx:.1f}" y="{cy-10:.1f}" fill="#38bdf8" font-size="10" text-anchor="middle">{sr:.2f}</text>')
        lbl = x_labels[i] if i < len(x_labels) else ""
        lines.append(f'<text x="{cx:.1f}" y="{PT+plot_h+14}" fill="#94a3b8" font-size="9" text-anchor="middle">{lbl}</text>')
        lines.append(f'<text x="{cx:.1f}" y="{PT+plot_h+24}" fill="#64748b" font-size="8" text-anchor="middle">{j["model"]}</text>')

    # Axis labels
    lines.append(f'<text x="14" y="{PT+plot_h//2}" fill="#94a3b8" font-size="11" text-anchor="middle" transform="rotate(-90,14,{PT+plot_h//2})">SR</text>')

    lines.append('</svg>')
    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# Dashboard HTML
# ---------------------------------------------------------------------------

def _dashboard_html() -> str:
    svg1 = _svg_eval_calendar()
    svg2 = _svg_sr_tracking()

    status_icon = {"COMPLETED": "&#10003;", "RUNNING": "&#9654;", "QUEUED": "&#9679;", "FAILED": "&#10007;"}

    rows = []
    for j in JOBS:
        color = STATUS_COLOR_MAP.get(j["status"], "#6b7280")
        sr_cell = f"{j['sr']:.2f}" if j["sr"] is not None else "—"
        dur_cell = f"{j['duration_min']} min" if j["duration_min"] else "—"
        icon = status_icon.get(j["status"], "")
        rows.append(
            f'<tr>'
            f'<td style="padding:8px 12px;font-family:monospace;color:#e2e8f0">{j["id"]}</td>'
            f'<td style="padding:8px 12px;color:#94a3b8;font-size:13px">{j["model"]}</td>'
            f'<td style="padding:8px 12px;color:#94a3b8">{j["task"]}</td>'
            f'<td style="padding:8px 12px;text-align:center;color:#94a3b8">{j["episodes"]}</td>'
            f'<td style="padding:8px 12px;text-align:center">'
            f'<span style="background:{color}22;color:{color};border:1px solid {color};border-radius:4px;padding:2px 8px;font-size:12px">{icon} {j["status"]}</span>'
            f'</td>'
            f'<td style="padding:8px 12px;text-align:center;color:#38bdf8;font-weight:bold">{sr_cell}</td>'
            f'<td style="padding:8px 12px;text-align:center;color:#94a3b8">{j["scheduled"]}</td>'
            f'<td style="padding:8px 12px;text-align:center;color:#94a3b8">{dur_cell}</td>'
            f'</tr>'
        )

    rule_items = ''.join(f'<li style="margin-bottom:6px;color:#86efac">{r}</li>' for r in TRIGGER_RULES)
    table_rows = ''.join(rows)

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Eval Scheduler — port 8153</title>
<style>
  body {{ margin:0; padding:0; background:#0f172a; color:#e2e8f0; font-family:system-ui,sans-serif; }}
  .header {{ background:#1e293b; border-bottom:2px solid #C74634; padding:16px 24px; display:flex; align-items:center; gap:12px; }}
  .header h1 {{ margin:0; font-size:20px; color:#ffffff; }}
  .badge {{ background:#C74634; color:#fff; border-radius:4px; padding:3px 10px; font-size:12px; font-weight:bold; }}
  .port {{ background:#1e3a5f; color:#38bdf8; border-radius:4px; padding:3px 10px; font-size:12px; }}
  .section {{ padding:20px 24px; }}
  .section h2 {{ margin:0 0 14px 0; font-size:15px; color:#94a3b8; text-transform:uppercase; letter-spacing:.05em; }}
  .charts {{ display:grid; grid-template-columns:1fr 1fr; gap:16px; padding:0 24px 20px; }}
  .card {{ background:#1e293b; border-radius:8px; padding:16px; border:1px solid #334155; }}
  .rules {{ background:#0f1f2e; border:1px solid #38bdf8; border-radius:8px; padding:14px 18px; margin:0 24px 20px; }}
  .rules-title {{ color:#38bdf8; font-size:13px; font-weight:bold; margin-bottom:8px; }}
  .rules ul {{ margin:0; padding-left:18px; }}
  table {{ width:100%; border-collapse:collapse; }}
  th {{ background:#0f172a; color:#64748b; font-size:12px; text-transform:uppercase; padding:8px 12px; text-align:left; border-bottom:1px solid #334155; }}
  tr:hover {{ background:#1e293b44; }}
  tr:not(:last-child) td {{ border-bottom:1px solid #1e293b; }}
  .stat-bar {{ display:flex; gap:16px; padding:0 24px 16px; }}
  .stat {{ background:#1e293b; border-radius:8px; padding:14px 18px; border:1px solid #334155; min-width:120px; }}
  .stat-val {{ font-size:28px; font-weight:bold; color:#38bdf8; }}
  .stat-lbl {{ font-size:11px; color:#64748b; margin-top:2px; }}
</style>
</head>
<body>
<div class="header">
  <span class="badge">OCI Robot Cloud</span>
  <h1>Eval Scheduler</h1>
  <span class="port">port 8153</span>
</div>

<div class="stat-bar">
  <div class="stat"><div class="stat-val">8</div><div class="stat-lbl">Total Jobs</div></div>
  <div class="stat"><div class="stat-val" style="color:#22c55e">3</div><div class="stat-lbl">Completed</div></div>
  <div class="stat"><div class="stat-val" style="color:#38bdf8">1</div><div class="stat-lbl">Running</div></div>
  <div class="stat"><div class="stat-val" style="color:#94a3b8">4</div><div class="stat-lbl">Queued</div></div>
  <div class="stat"><div class="stat-val" style="color:#f59e0b">0.78</div><div class="stat-lbl">Latest SR</div></div>
</div>

<div class="section">
  <h2>Schedule &amp; Progress</h2>
</div>
<div class="charts">
  <div class="card">{svg1}</div>
  <div class="card">{svg2}</div>
</div>

<div class="rules">
  <div class="rules-title">Trigger Rules</div>
  <ul class="rules">{rule_items}</ul>
</div>

<div class="section">
  <h2>All Jobs</h2>
  <table>
    <thead>
      <tr>
        <th>ID</th><th>Model</th><th>Task</th><th>Episodes</th>
        <th>Status</th><th>SR</th><th>Scheduled</th><th>Duration</th>
      </tr>
    </thead>
    <tbody>{table_rows}</tbody>
  </table>
</div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(title="Eval Scheduler", version="1.0.0")


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    return HTMLResponse(content=_dashboard_html())


@app.get("/jobs")
async def list_jobs():
    return JSONResponse(content=JOBS)


@app.get("/jobs/{job_id}")
async def get_job(job_id: str):
    if job_id not in JOBS_BY_ID:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    return JSONResponse(content=JOBS_BY_ID[job_id])


@app.get("/next")
async def next_scheduled():
    queued = [j for j in JOBS if j["status"] == "QUEUED"]
    if not queued:
        return JSONResponse(content={"message": "No queued jobs"})
    # Sort by scheduled timestamp
    queued.sort(key=lambda j: j["scheduled"])
    return JSONResponse(content=queued[0])


@app.get("/history")
async def history():
    completed = [j for j in JOBS if j["status"] == "COMPLETED"]
    completed.sort(key=lambda j: j["scheduled"])
    return JSONResponse(content=completed)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8153)
