"""Training Run Scheduler — FastAPI service on port 8231.

Priority-based scheduler for GR00T training runs across OCI GPU fleet.
Dashboard: http://localhost:8231
"""

import math
import random
from datetime import date, datetime, timedelta

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    _FASTAPI = True
except ImportError:  # pragma: no cover
    _FASTAPI = False

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

random.seed(42)
TODAY = date(2026, 3, 30)
NOW   = datetime(2026, 3, 30, 14, 22, 0)

JOB_COLORS = {
    "fine_tune": "#C74634",
    "dagger":    "#38bdf8",
    "eval":      "#22c55e",
    "sdg":       "#f59e0b",
}

JOBS = [
    {"id": "groot_finetune_v3", "type": "fine_tune", "gpu": "A100-node-1",
     "start_offset_h": -6,  "duration_h": 18, "priority": 1,
     "status": "running",  "steps": 8200, "total_steps": 20000},
    {"id": "dagger_run10",      "type": "dagger",    "gpu": "A100-node-2",
     "start_offset_h": -2,  "duration_h": 10, "priority": 1,
     "status": "running",  "steps": 1800, "total_steps": 5000},
    {"id": "eval_batch_v3",    "type": "eval",      "gpu": "A100-node-1",
     "start_offset_h": 12,  "duration_h": 4,  "priority": 2,
     "status": "queued",   "steps": 0,    "total_steps": 400},
    {"id": "sdg_v4",            "type": "sdg",       "gpu": "A100-node-2",
     "start_offset_h": 8,   "duration_h": 14, "priority": 2,
     "status": "queued",   "steps": 0,    "total_steps": 10000},
    {"id": "groot_finetune_v4", "type": "fine_tune", "gpu": "A100-node-1",
     "start_offset_h": 36,  "duration_h": 20, "priority": 3,
     "status": "queued",   "steps": 0,    "total_steps": 25000},
    {"id": "eval_curriculum",  "type": "eval",      "gpu": "A100-node-2",
     "start_offset_h": 22,  "duration_h": 3,  "priority": 3,
     "status": "queued",   "steps": 0,    "total_steps": 300},
]

GPU_NODES = [
    {"id": "A100-node-1", "gpus": 8, "util": 87, "memory_gb": 640,
     "mem_used_gb": 512, "cost_hr": 19.2},
    {"id": "A100-node-2", "gpus": 8, "util": 91, "memory_gb": 640,
     "mem_used_gb": 578, "cost_hr": 19.2},
]


# ---------------------------------------------------------------------------
# SVG builders
# ---------------------------------------------------------------------------

def _svg_gantt() -> str:
    """Gantt chart — 7-day lookahead, jobs as colored bars."""
    W, H = 720, 260
    left, right, top, bottom = 130, 20, 40, 50
    plot_w = W - left - right
    plot_h = H - top - bottom
    hours = 7 * 24  # 168h window

    NODES = ["A100-node-1", "A100-node-2"]
    row_h = (plot_h - 10) // len(NODES)

    def x_pos(offset_h):
        return left + (offset_h / hours) * plot_w

    def y_pos(node_idx):
        return top + node_idx * row_h

    lines = []
    # background grid
    for d in range(8):
        xp = x_pos(d * 24)
        dt = (TODAY + timedelta(days=d)).strftime("%b %d")
        lines.append(
            f'<line x1="{xp:.1f}" y1="{top}" x2="{xp:.1f}" y2="{top + plot_h}" '
            f'stroke="#1e293b" stroke-width="1"/>'
            f'<text x="{xp:.1f}" y="{top + plot_h + 14}" text-anchor="middle" '
            f'font-size="9" fill="#64748b">{dt}</text>'
        )

    # night/weekend shading (Fri 18h — Mon 6h approx)
    # Fri Mar 27 18h offset relative to NOW=Mon Mar 30 14:22
    for d in range(8):
        day_of_week = (TODAY + timedelta(days=d)).weekday()  # 0=Mon
        if day_of_week in (5, 6):  # Sat/Sun
            x0 = x_pos(d * 24)
            x1 = x_pos((d + 1) * 24)
            lines.append(
                f'<rect x="{x0:.1f}" y="{top}" width="{x1 - x0:.1f}" height="{plot_h}" '
                f'fill="#38bdf8" opacity="0.04"/>'
            )

    # node labels
    for ni, node in enumerate(NODES):
        yp = y_pos(ni)
        mid = yp + row_h // 2
        lines.append(
            f'<text x="{left - 6}" y="{mid + 4}" text-anchor="end" '
            f'font-size="11" fill="#94a3b8">{node}</text>'
            f'<line x1="{left}" y1="{yp}" x2="{left + plot_w}" y2="{yp}" '
            f'stroke="#334155" stroke-width="0.5"/>'
        )

    # job bars
    for job in JOBS:
        ni    = NODES.index(job["gpu"])
        col   = JOB_COLORS[job["type"]]
        x0    = x_pos(max(0, job["start_offset_h"]))
        bw    = (job["duration_h"] / hours) * plot_w
        yp    = y_pos(ni) + 4
        bh    = row_h - 10
        opa   = "1" if job["status"] == "running" else "0.65"
        label = job["id"]
        lines.append(
            f'<rect x="{x0:.1f}" y="{yp}" width="{bw:.1f}" height="{bh}" '
            f'rx="3" fill="{col}" opacity="{opa}"/>'
            f'<text x="{x0 + 4:.1f}" y="{yp + bh - 5}" font-size="9" fill="#0f172a" '
            f'clip-path="url(#clip)">{label}</text>'
        )

    # "now" cursor
    xnow = x_pos(0)
    lines.append(
        f'<line x1="{xnow:.1f}" y1="{top}" x2="{xnow:.1f}" y2="{top + plot_h}" '
        f'stroke="#f1f5f9" stroke-width="2" stroke-dasharray="4,2"/>'
        f'<text x="{xnow + 2:.1f}" y="{top + 10}" font-size="9" fill="#f1f5f9">NOW</text>'
    )

    # legend
    legend_y = H - 14
    for li, (jt, col) in enumerate(JOB_COLORS.items()):
        lx = left + li * 140
        lines.append(
            f'<rect x="{lx}" y="{legend_y - 10}" width="12" height="10" fill="{col}"/>'
            f'<text x="{lx + 16}" y="{legend_y}" font-size="10" fill="#94a3b8">{jt}</text>'
        )

    svg_body = "\n".join(lines)
    return (
        f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" '
        f'style="width:100%;background:#0f172a;border-radius:8px;padding:10px">'
        f'<defs><clipPath id="clip"><rect x="{left}" y="{top}" width="{plot_w}" height="{plot_h}"/></clipPath></defs>'
        f'<text x="{W//2}" y="16" text-anchor="middle" font-size="13" font-weight="bold" fill="#f1f5f9">'
        f'GR00T Training Job Gantt — 7-Day Lookahead</text>'
        f'{svg_body}'
        f'</svg>'
    )


def _svg_gpu_forecast() -> str:
    """Bar chart — predicted GPU utilization per node per day for 7 days."""
    W, H = 720, 260
    left, right, top, bottom = 60, 20, 40, 50
    plot_w = W - left - right
    plot_h = H - top - bottom
    days   = 7
    nodes  = [n["id"] for n in GPU_NODES]
    n_days = days
    n_nodes = len(nodes)
    group_w = plot_w / n_days
    bar_w   = (group_w - 10) / n_nodes
    node_colors = ["#C74634", "#38bdf8"]

    def y_pos(util):
        return top + plot_h - (min(util, 105) / 105) * plot_h

    lines = []
    # axes
    lines.append(
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_h}" stroke="#334155"/>'
        f'<line x1="{left}" y1="{top + plot_h}" x2="{left + plot_w}" y2="{top + plot_h}" stroke="#334155"/>'
    )
    for pct in [0, 25, 50, 75, 90, 100]:
        yp = y_pos(pct)
        lines.append(
            f'<line x1="{left}" y1="{yp:.1f}" x2="{left + plot_w}" y2="{yp:.1f}" '
            f'stroke="{"#ef4444" if pct == 90 else "#1e293b"}" stroke-width="1" '
            f'stroke-dasharray="{"" if pct == 90 else "2,3"}"/>'
            f'<text x="{left - 4}" y="{yp + 4:.1f}" text-anchor="end" font-size="9" fill="#64748b">{pct}%</text>'
        )

    for d in range(days):
        dt   = TODAY + timedelta(days=d)
        dow  = dt.weekday()  # 0=Mon
        xg   = left + d * group_w
        label = dt.strftime("%a %m/%d")
        lines.append(
            f'<text x="{xg + group_w/2:.1f}" y="{top + plot_h + 14}" '
            f'text-anchor="middle" font-size="9" fill="{"#38bdf8" if dow >= 5 else "#64748b"}">{label}</text>'
        )
        if dow >= 5:
            lines.append(
                f'<rect x="{xg:.1f}" y="{top}" width="{group_w:.1f}" height="{plot_h}" '
                f'fill="#38bdf8" opacity="0.05"/>'
                f'<text x="{xg + group_w/2:.1f}" y="{top + plot_h/2:.1f}" text-anchor="middle" '
                f'font-size="9" fill="#38bdf8" opacity="0.4">OPP</text>'
            )

        for ni, (node, col) in enumerate(zip(nodes, node_colors)):
            base = GPU_NODES[ni]["util"]
            # simulate weekday/night variation
            is_weekend = dow >= 5
            util = base * (0.55 if is_weekend else random.uniform(0.82, 1.05))
            util = min(util, 100)
            xb   = xg + 5 + ni * bar_w
            bh   = (util / 105) * plot_h
            yb   = top + plot_h - bh
            bc   = "#ef4444" if util >= 90 else ("#f59e0b" if util >= 70 else col)
            lines.append(
                f'<rect x="{xb:.1f}" y="{yb:.1f}" width="{bar_w - 2:.1f}" height="{bh:.1f}" '
                f'rx="2" fill="{bc}" opacity="0.85"/>'
                f'<text x="{xb + bar_w/2 - 1:.1f}" y="{yb - 3:.1f}" text-anchor="middle" '
                f'font-size="8" fill="#94a3b8">{util:.0f}%</text>'
            )

    # legend
    legend_y = H - 14
    for li, (node, col) in enumerate(zip(nodes, node_colors)):
        lx = left + li * 200
        lines.append(
            f'<rect x="{lx}" y="{legend_y - 10}" width="12" height="10" fill="{col}"/>'
            f'<text x="{lx + 16}" y="{legend_y}" font-size="10" fill="#94a3b8">{node}</text>'
        )
    lines.append(
        f'<text x="{left + 420}" y="{legend_y}" font-size="10" fill="#38bdf8" opacity="0.7">'
        f'OPP = Weekend optimization opportunity</text>'
    )

    svg_body = "\n".join(lines)
    return (
        f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" '
        f'style="width:100%;background:#0f172a;border-radius:8px;padding:10px">'
        f'<text x="{W//2}" y="16" text-anchor="middle" font-size="13" font-weight="bold" fill="#f1f5f9">'
        f'GPU Node Utilization Forecast — 7 Days (Night/Weekend Opportunities Highlighted)</text>'
        f'{svg_body}'
        f'</svg>'
    )


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def _build_dashboard() -> str:
    running = [j for j in JOBS if j["status"] == "running"]
    queued  = [j for j in JOBS if j["status"] == "queued"]
    total_cost_hr = sum(n["cost_hr"] * n["util"] / 100 for n in GPU_NODES)
    week_cost = total_cost_hr * 24 * 7

    jobs_html = ""
    for j in JOBS:
        col    = JOB_COLORS[j["type"]]
        est_h  = j["start_offset_h"]
        wait   = f"starts in {est_h}h" if est_h > 0 else ("running" if j["status"] == "running" else "now")
        pct    = int(j["steps"] / j["total_steps"] * 100) if j["status"] == "running" else 0
        bar    = (
            f'<div style="background:#334155;border-radius:4px;height:6px;width:100%;margin-top:4px">'
            f'<div style="background:{col};width:{pct}%;height:6px;border-radius:4px"></div></div>'
        ) if j["status"] == "running" else ""
        jobs_html += f"""
        <tr>
          <td style="padding:8px 12px">
            <span style="color:{col};font-weight:bold">{j['id']}</span>
            {bar}
          </td>
          <td style="padding:8px 12px">
            <span style="background:{col}22;border:1px solid {col};border-radius:4px;
                         padding:2px 6px;font-size:11px;color:{col}">{j['type']}</span>
          </td>
          <td style="padding:8px 12px;color:#94a3b8">{j['gpu']}</td>
          <td style="padding:8px 12px;color:#e2e8f0">{j['status']}</td>
          <td style="padding:8px 12px;color:#64748b">{j['duration_h']}h</td>
          <td style="padding:8px 12px;color:#f59e0b">P{j['priority']}</td>
          <td style="padding:8px 12px;color:#64748b">{wait}</td>
        </tr>"""

    svg1 = _svg_gantt()
    svg2 = _svg_gpu_forecast()

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Training Run Scheduler — Port 8231</title>
  <style>
    * {{ margin:0; padding:0; box-sizing:border-box }}
    body {{ background:#0f172a; color:#e2e8f0; font-family:'Segoe UI',system-ui,sans-serif; padding:24px }}
    h1   {{ color:#C74634; font-size:22px; margin-bottom:4px }}
    h2   {{ color:#38bdf8; font-size:15px; margin:24px 0 10px }}
    .sub {{ color:#64748b; font-size:13px; margin-bottom:20px }}
    .kpi-row {{ display:flex; gap:16px; flex-wrap:wrap; margin-bottom:24px }}
    .kpi {{ background:#1e293b; border:1px solid #334155; border-radius:8px;
             padding:14px 20px; min-width:160px }}
    .kpi .val  {{ font-size:26px; font-weight:700; color:#38bdf8 }}
    .kpi .lbl  {{ font-size:12px; color:#64748b; margin-top:2px }}
    .kpi.warn .val {{ color:#f59e0b }}
    .kpi.crit .val {{ color:#ef4444 }}
    table {{ width:100%; border-collapse:collapse; background:#1e293b;
             border-radius:8px; overflow:hidden }}
    thead th {{ background:#0f172a; padding:8px 12px; text-align:left;
                font-size:12px; color:#64748b; border-bottom:1px solid #334155 }}
    tbody tr:nth-child(even) {{ background:#162032 }}
    .chart-grid {{ display:grid; grid-template-columns:1fr; gap:20px; margin-bottom:24px }}
    .badge-oracle {{ display:inline-block; background:#C7463422; border:1px solid #C74634;
                     border-radius:4px; padding:2px 8px; font-size:11px; color:#C74634;
                     margin-left:12px }}
  </style>
</head>
<body>
  <h1>Training Run Scheduler <span class="badge-oracle">PORT 8231</span></h1>
  <p class="sub">GR00T Priority-Based Scheduler — OCI GPU Fleet | {TODAY} {NOW.strftime('%H:%M')}</p>

  <div class="kpi-row">
    <div class="kpi crit">
      <div class="val">{len(queued)}</div>
      <div class="lbl">Jobs Queued</div>
    </div>
    <div class="kpi">
      <div class="val" style="color:#22c55e">{len(running)}</div>
      <div class="lbl">Jobs Running</div>
    </div>
    <div class="kpi warn">
      <div class="val">{GPU_NODES[0]['util']}% / {GPU_NODES[1]['util']}%</div>
      <div class="lbl">GPU Node Utilization</div>
    </div>
    <div class="kpi">
      <div class="val">~8h</div>
      <div class="lbl">Est. Queue Wait Time</div>
    </div>
    <div class="kpi warn">
      <div class="val">${week_cost:.0f}</div>
      <div class="lbl">Projected Week GPU Cost</div>
    </div>
    <div class="kpi">
      <div class="val" style="color:#22c55e">78%</div>
      <div class="lbl">Schedule Optimization Score</div>
    </div>
  </div>

  <h2>7-Day Job Gantt Chart</h2>
  <div class="chart-grid">{svg1}</div>

  <h2>GPU Node Utilization Forecast</h2>
  <div class="chart-grid" style="margin-bottom:24px">{svg2}</div>

  <h2>Job Queue Detail</h2>
  <table>
    <thead>
      <tr>
        <th>Job ID</th><th>Type</th><th>GPU Node</th>
        <th>Status</th><th>Duration</th><th>Priority</th><th>Wait / ETA</th>
      </tr>
    </thead>
    <tbody>{jobs_html}</tbody>
  </table>

  <p style="margin-top:20px;font-size:12px;color:#334155">
    OCI Robot Cloud — Training Run Scheduler v1.0 | Refreshed {NOW.strftime('%Y-%m-%d %H:%M')}
  </p>
</body>
</html>"""


# ---------------------------------------------------------------------------
# FastAPI / stdlib server
# ---------------------------------------------------------------------------

if _FASTAPI:
    app = FastAPI(title="Training Run Scheduler", version="1.0")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return _build_dashboard()

    @app.get("/api/jobs")
    async def api_jobs():
        return {"timestamp": str(NOW), "jobs": JOBS, "nodes": GPU_NODES}

    @app.get("/api/queue")
    async def api_queue():
        return {
            "queued": len([j for j in JOBS if j["status"] == "queued"]),
            "running": len([j for j in JOBS if j["status"] == "running"]),
            "week_cost_usd": round(
                sum(n["cost_hr"] * n["util"] / 100 for n in GPU_NODES) * 24 * 7, 2
            ),
        }

    @app.get("/health")
    async def health():
        return {"status": "ok", "port": 8231}

else:  # pragma: no cover — stdlib fallback
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = _build_dashboard().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            pass


if __name__ == "__main__":
    if _FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8231)
    else:  # pragma: no cover
        print("[training_run_scheduler] fastapi not found — starting stdlib server on :8231")
        HTTPServer(("0.0.0.0", 8231), _Handler).serve_forever()
