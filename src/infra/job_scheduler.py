"""GPU Job Scheduler — OCI Robot Cloud  (port 8142)"""

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
except ImportError:
    FastAPI = None

import math
from datetime import datetime, timezone
from typing import Optional

# ---------------------------------------------------------------------------
# Static data
# ---------------------------------------------------------------------------

NODES = [
    {"id": "ashburn-prod-1",    "gpus": "2×A100_80GB", "util": 87, "reserved_until": "2026-03-30T20:00Z"},
    {"id": "ashburn-canary-1",  "gpus": "2×A100_80GB", "util": 72, "reserved_until": None},
    {"id": "phoenix-eval-1",    "gpus": "1×A100_40GB", "util": 45, "reserved_until": None},
    {"id": "frankfurt-staging-1","gpus": "1×A100_40GB", "util": 31, "reserved_until": None},
]

JOBS = [
    {"id":"j001","type":"fine_tune", "priority":"P1","gpu_req":"A100_80GB×2","est_hours":6.2, "status":"RUNNING",  "node":"ashburn-prod-1",    "submitted":"03-30 08:14","eta":None,         "partner":"physical_intelligence"},
    {"id":"j002","type":"hpo_search","priority":"P2","gpu_req":"A100_80GB×1","est_hours":2.1, "status":"RUNNING",  "node":"ashburn-canary-1",  "submitted":"03-30 10:42","eta":None,         "partner":"apptronik"},
    {"id":"j003","type":"eval",      "priority":"P3","gpu_req":"A100_40GB×1","est_hours":0.8, "status":"RUNNING",  "node":"phoenix-eval-1",   "submitted":"03-30 13:15","eta":None,         "partner":"1x_technologies"},
    {"id":"j004","type":"sdg",       "priority":"P2","gpu_req":"A100_40GB×1","est_hours":2.4, "status":"QUEUED",   "node":None,               "submitted":"03-30 12:00","eta":"03-30 17:30","partner":"agility_robotics"},
    {"id":"j005","type":"fine_tune", "priority":"P1","gpu_req":"A100_80GB×2","est_hours":5.8, "status":"QUEUED",   "node":None,               "submitted":"03-30 11:30","eta":"03-30 21:00","partner":"physical_intelligence"},
    {"id":"j006","type":"eval",      "priority":"P3","gpu_req":"A100_40GB×1","est_hours":1.2, "status":"QUEUED",   "node":None,               "submitted":"03-30 13:00","eta":"03-30 18:30","partner":"apptronik"},
    {"id":"j007","type":"hpo_search","priority":"P2","gpu_req":"A100_80GB×1","est_hours":3.5, "status":"QUEUED",   "node":None,               "submitted":"03-30 14:00","eta":"03-30 19:00","partner":"agility_robotics"},
    {"id":"j008","type":"sdg",       "priority":"P2","gpu_req":"A100_40GB×1","est_hours":1.8, "status":"COMPLETED","node":"frankfurt-staging-1","submitted":"03-30 06:00","eta":None,         "partner":"1x_technologies"},
    {"id":"j009","type":"eval",      "priority":"P3","gpu_req":"A100_40GB×1","est_hours":0.9, "status":"COMPLETED","node":"phoenix-eval-1",   "submitted":"03-30 07:00","eta":None,         "partner":"physical_intelligence"},
    {"id":"j010","type":"fine_tune", "priority":"P1","gpu_req":"A100_80GB×2","est_hours":4.1, "status":"COMPLETED","node":"ashburn-prod-1",   "submitted":"03-30 02:00","eta":None,         "partner":"apptronik"},
]

STATS = {
    "running":3, "queued":4, "completed_today":12,
    "gpu_hours_today":28.4, "cost_today":86.90
}

# queue depth per hour over past 24h (hour 0 = midnight)
QUEUE_DEPTH_24H = [2,2,3,3,2,1,2,3,4,5,6,7,6,5,4,5,6,5,4,3,3,2,2,2]

# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------

TYPE_COLOR = {"fine_tune":"#C74634","hpo_search":"#f59e0b","eval":"#38bdf8","sdg":"#4ade80"}

def _gantt_svg() -> str:
    W, H = 680, 220
    lane_h = 44
    pad_l, pad_r, pad_t, pad_b = 160, 20, 30, 30
    chart_w = W - pad_l - pad_r
    chart_h = H - pad_t - pad_b
    now_h = 14  # current hour (14:00)
    window = 12  # hours shown

    def x_of(h_offset: float) -> float:
        return pad_l + (h_offset / window) * chart_w

    node_ids = [n["id"] for n in NODES]

    lines = [
        f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg" style="background:#1e293b;border-radius:8px">',
        # grid lines
    ]
    for i in range(window + 1):
        xg = x_of(i)
        hour_label = (now_h + i) % 24
        lines.append(f'<line x1="{xg:.1f}" y1="{pad_t}" x2="{xg:.1f}" y2="{H-pad_b}" stroke="#334155" stroke-width="1"/>')
        lines.append(f'<text x="{xg:.1f}" y="{H-pad_b+14}" fill="#94a3b8" font-size="10" text-anchor="middle">{hour_label:02d}:00</text>')

    # lane backgrounds + labels
    for li, nid in enumerate(node_ids):
        y0 = pad_t + li * lane_h
        bg = "#0f172a" if li % 2 == 0 else "#1e293b"
        lines.append(f'<rect x="{pad_l}" y="{y0}" width="{chart_w}" height="{lane_h}" fill="{bg}"/>')
        short = nid.replace("-","\n")
        lines.append(f'<text x="{pad_l-6}" y="{y0+lane_h//2+4}" fill="#cbd5e1" font-size="10" text-anchor="end">{nid}</text>')

    # jobs
    job_start_offset = {
        "j001": -5.77,  # started 08:14, now=14:00 → running for 5.77h
        "j002": -3.3,
        "j003": -0.75,
        "j004":  3.5,   # eta 17:30 → starts at +3.5h
        "j005":  7.0,
        "j006":  4.5,
        "j007":  5.0,
        "j008": -8.0,   # completed
        "j009": -7.0,
        "j010": -12.0,
    }
    node_to_lane = {n["id"]: i for i, n in enumerate(NODES)}

    for job in JOBS:
        color = TYPE_COLOR.get(job["type"], "#94a3b8")
        dur = job["est_hours"]
        start_off = job_start_offset[job["id"]]
        bar_x = x_of(max(start_off, 0))
        end_off = start_off + dur
        bar_end = x_of(min(end_off, window))
        bar_w = max(bar_end - bar_x, 2)

        if job["status"] == "COMPLETED":
            if end_off < 0:
                continue  # outside window
            opacity = 0.35
            dash = ""
        elif job["status"] == "RUNNING":
            opacity = 0.9
            dash = ""
        else:  # QUEUED
            opacity = 0.7
            dash = 'stroke-dasharray="6,3" stroke="#94a3b8" stroke-width="1"'

        lane = node_to_lane.get(job["node"] or "phoenix-eval-1", 2)
        y0 = pad_t + lane * lane_h + 8
        bh = lane_h - 16
        lines.append(f'<rect x="{bar_x:.1f}" y="{y0}" width="{bar_w:.1f}" height="{bh}" rx="3" fill="{color}" opacity="{opacity}" {dash}/>')
        if bar_w > 30:
            lines.append(f'<text x="{bar_x+4:.1f}" y="{y0+bh//2+4}" fill="#fff" font-size="9" opacity="{min(opacity+0.1,1)}">{job["id"]}</text>')

    # "now" line
    lines.append(f'<line x1="{x_of(0):.1f}" y1="{pad_t}" x2="{x_of(0):.1f}" y2="{H-pad_b}" stroke="#f97316" stroke-width="2" stroke-dasharray="4,2"/>')
    lines.append(f'<text x="{x_of(0)+4:.1f}" y="{pad_t+10}" fill="#f97316" font-size="10">NOW</text>')

    # legend
    lx = pad_l
    for jtype, col in TYPE_COLOR.items():
        lines.append(f'<rect x="{lx}" y="6" width="10" height="10" fill="{col}" rx="2"/>')
        lines.append(f'<text x="{lx+13}" y="15" fill="#94a3b8" font-size="10">{jtype}</text>')
        lx += 110

    lines.append('</svg>')
    return "\n".join(lines)


def _queue_depth_svg() -> str:
    W, H = 680, 160
    pad_l, pad_r, pad_t, pad_b = 40, 20, 20, 30
    data = QUEUE_DEPTH_24H
    n = len(data)
    max_d = max(data) or 1
    chart_w = W - pad_l - pad_r
    chart_h = H - pad_t - pad_b

    def px(i): return pad_l + (i / (n - 1)) * chart_w
    def py(v): return pad_t + chart_h - (v / max_d) * chart_h

    lines = [
        f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg" style="background:#1e293b;border-radius:8px">',
    ]
    # area
    pts = " ".join(f"{px(i):.1f},{py(d):.1f}" for i, d in enumerate(data))
    bot_l = f"{px(0):.1f},{py(0):.1f}"
    bot_r = f"{px(n-1):.1f},{py(0):.1f}"
    lines.append(f'<polyline points="{bot_l} {pts} {bot_r}" fill="#38bdf820" stroke="none"/>')
    lines.append(f'<polyline points="{pts}" fill="none" stroke="#38bdf8" stroke-width="2"/>')

    # dots
    for i, d in enumerate(data):
        lines.append(f'<circle cx="{px(i):.1f}" cy="{py(d):.1f}" r="3" fill="#38bdf8"/>')

    # x-axis labels every 6h
    for i in range(0, n, 6):
        lines.append(f'<text x="{px(i):.1f}" y="{H-pad_b+14}" fill="#94a3b8" font-size="10" text-anchor="middle">{i:02d}:00</text>')
        lines.append(f'<line x1="{px(i):.1f}" y1="{pad_t}" x2="{px(i):.1f}" y2="{H-pad_b}" stroke="#334155" stroke-width="1"/>')

    # y-axis labels
    for v in range(0, max_d + 1, 2):
        lines.append(f'<text x="{pad_l-4}" y="{py(v)+4:.1f}" fill="#94a3b8" font-size="10" text-anchor="end">{v}</text>')
        lines.append(f'<line x1="{pad_l}" y1="{py(v):.1f}" x2="{W-pad_r}" y2="{py(v):.1f}" stroke="#334155" stroke-width="1" stroke-dasharray="3,3"/>')

    lines.append('</svg>')
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def _build_html() -> str:
    gantt = _gantt_svg()
    queue_chart = _queue_depth_svg()

    running = [j for j in JOBS if j["status"] == "RUNNING"]
    queued  = [j for j in JOBS if j["status"] == "QUEUED"]

    def status_badge(s):
        c = {"RUNNING":"#38bdf8","QUEUED":"#f59e0b","COMPLETED":"#4ade80"}.get(s,"#94a3b8")
        return f'<span style="background:{c}22;color:{c};padding:2px 8px;border-radius:9999px;font-size:11px">{s}</span>'

    def prio_badge(p):
        c = {"P1":"#C74634","P2":"#f59e0b","P3":"#94a3b8"}.get(p,"#94a3b8")
        return f'<span style="color:{c};font-weight:700">{p}</span>'

    rows = "".join(
        f'<tr style="border-bottom:1px solid #1e293b">'
        f'<td style="padding:8px 12px;color:#38bdf8;font-family:monospace">{j["id"]}</td>'
        f'<td style="padding:8px 12px">{prio_badge(j["priority"])}</td>'
        f'<td style="padding:8px 12px;color:#cbd5e1">{j["type"]}</td>'
        f'<td style="padding:8px 12px;color:#94a3b8">{j["gpu_req"]}</td>'
        f'<td style="padding:8px 12px;color:#94a3b8">{j["est_hours"]}h</td>'
        f'<td style="padding:8px 12px">{status_badge(j["status"])}</td>'
        f'<td style="padding:8px 12px;color:#94a3b8;font-size:11px">{j["node"] or "—"}</td>'
        f'<td style="padding:8px 12px;color:#94a3b8;font-size:11px">{j["partner"]}</td>'
        f'</tr>'
        for j in JOBS
    )

    node_rows = "".join(
        f'<tr style="border-bottom:1px solid #1e293b">'
        f'<td style="padding:8px 12px;color:#38bdf8;font-family:monospace">{n["id"]}</td>'
        f'<td style="padding:8px 12px;color:#cbd5e1">{n["gpus"]}</td>'
        f'<td style="padding:8px 12px">'
        f'<div style="background:#334155;border-radius:4px;height:8px;width:100px;display:inline-block">'
        f'<div style="background:{"#C74634" if n["util"]>80 else "#38bdf8"};width:{n["util"]}px;height:8px;border-radius:4px"></div>'
        f'</div> <span style="color:#94a3b8;font-size:11px">{n["util"]}%</span></td>'
        f'<td style="padding:8px 12px;color:#94a3b8;font-size:11px">{n["reserved_until"] or "—"}</td>'
        f'</tr>'
        for n in NODES
    )

    stats_html = "".join(
        f'<div style="background:#1e293b;border-radius:8px;padding:16px 24px;text-align:center">'
        f'<div style="font-size:28px;font-weight:700;color:{vc}">{vv}</div>'
        f'<div style="font-size:12px;color:#94a3b8;margin-top:4px">{lbl}</div>'
        f'</div>'
        for lbl, vv, vc in [
            ("Running Jobs",    STATS["running"],          "#38bdf8"),
            ("Queued Jobs",     STATS["queued"],           "#f59e0b"),
            ("Completed Today", STATS["completed_today"],  "#4ade80"),
            ("GPU-Hours Today", f"{STATS['gpu_hours_today']:.1f}", "#e2e8f0"),
            ("Cost Today",      f"${STATS['cost_today']:.2f}",    "#C74634"),
        ]
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>GPU Job Scheduler — OCI Robot Cloud</title>
<style>
  * {{ box-sizing:border-box; margin:0; padding:0 }}
  body {{ background:#0f172a; color:#e2e8f0; font-family:'Segoe UI',system-ui,sans-serif; padding:24px }}
  h1 {{ color:#38bdf8; font-size:22px; margin-bottom:4px }}
  h2 {{ color:#cbd5e1; font-size:15px; margin:24px 0 10px }}
  .sub {{ color:#64748b; font-size:13px }}
  .cards {{ display:grid; grid-template-columns:repeat(5,1fr); gap:12px; margin:20px 0 }}
  table {{ width:100%; border-collapse:collapse; background:#0f172a; border-radius:8px; overflow:hidden }}
  th {{ background:#1e293b; color:#64748b; font-size:11px; text-transform:uppercase; padding:8px 12px; text-align:left }}
  tr:hover {{ background:#1e293b40 }}
  .badge-port {{ background:#38bdf822; color:#38bdf8; padding:2px 8px; border-radius:9999px; font-size:11px }}
</style>
</head>
<body>
<div style="display:flex;align-items:center;justify-content:space-between">
  <div>
    <h1>GPU Job Scheduler</h1>
    <p class="sub">OCI Robot Cloud &nbsp;|&nbsp; <span class="badge-port">:8142</span> &nbsp;|&nbsp; {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}</p>
  </div>
  <div style="color:#4ade80;font-size:13px">● LIVE</div>
</div>

<div class="cards">{stats_html}</div>

<h2>Job Gantt — 12-Hour Window</h2>
{gantt}

<h2>Queue Depth — Past 24 Hours</h2>
{queue_chart}

<h2>GPU Nodes</h2>
<table>
  <thead><tr><th>Node</th><th>GPUs</th><th>Utilization</th><th>Reserved Until</th></tr></thead>
  <tbody>{node_rows}</tbody>
</table>

<h2>All Jobs</h2>
<table>
  <thead><tr><th>Job ID</th><th>Priority</th><th>Type</th><th>GPU Req</th><th>Est Hours</th><th>Status</th><th>Node</th><th>Partner</th></tr></thead>
  <tbody>{rows}</tbody>
</table>

<p style="margin-top:32px;color:#334155;font-size:11px">OCI Robot Cloud · GPU Job Scheduler · port 8142</p>
</body></html>"""


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

if FastAPI is not None:
    app = FastAPI(title="GPU Job Scheduler", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return _build_html()

    @app.get("/jobs")
    def list_jobs():
        return {"jobs": JOBS, "total": len(JOBS)}

    @app.get("/jobs/{job_id}")
    def get_job(job_id: str):
        for j in JOBS:
            if j["id"] == job_id:
                return j
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    @app.get("/queue")
    def get_queue():
        priority_order = {"P1": 0, "P2": 1, "P3": 2}
        queued = [j for j in JOBS if j["status"] == "QUEUED"]
        queued_sorted = sorted(queued, key=lambda j: (priority_order.get(j["priority"], 9), j["submitted"]))
        return {"queue": queued_sorted, "depth": len(queued_sorted)}

    @app.post("/schedule")
    def schedule_job(job: dict):
        required = {"type", "priority", "gpu_req", "est_hours", "partner"}
        missing = required - set(job.keys())
        if missing:
            raise HTTPException(status_code=422, detail=f"Missing fields: {missing}")
        new_id = f"j{len(JOBS)+1:03d}"
        entry = {
            "id": new_id,
            "status": "QUEUED",
            "node": None,
            "submitted": datetime.now(timezone.utc).strftime("%m-%d %H:%M"),
            "eta": None,
            **{k: job[k] for k in required},
        }
        JOBS.append(entry)
        return {"accepted": True, "job_id": new_id, "job": entry}

if __name__ == "__main__":
    if FastAPI is None:
        raise SystemExit("FastAPI not installed. Run: pip install fastapi uvicorn")
    uvicorn.run("job_scheduler:app", host="0.0.0.0", port=8142, reload=True)
