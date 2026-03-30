"""HPC Job Monitor — FastAPI service on port 8276.

Monitors HPC-style batch jobs across OCI GPU fleet for training pipeline.
Fallback to stdlib http.server if FastAPI/uvicorn are not installed.
"""

import math
import random
import json
from datetime import datetime, timedelta

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

random.seed(42)

JOBS = [
    {"id": "job-001", "name": "DAgger_r10",   "status": "RUNNING",   "node": "gpu-node-1", "type": "dagger",    "elapsed_h": 2.1, "est_total_h": 4.0,  "gpu_alloc": 4, "gpu_used": 3.8, "batch": 32},
    {"id": "job-002", "name": "groot_v3",     "status": "RUNNING",   "node": "gpu-node-2", "type": "finetune",  "elapsed_h": 1.3, "est_total_h": 8.0,  "gpu_alloc": 8, "gpu_used": 4.1, "batch": 64},
    {"id": "job-003", "name": "bc_eval_r5",   "status": "RUNNING",   "node": "gpu-node-3", "type": "eval",     "elapsed_h": 0.4, "est_total_h": 1.0,  "gpu_alloc": 2, "gpu_used": 1.9, "batch": 16},
    {"id": "job-004", "name": "sdg_gen_v2",   "status": "QUEUED",    "node": None,         "type": "sdg",      "elapsed_h": 0.0, "est_total_h": 3.0,  "gpu_alloc": 4, "gpu_used": 0.0, "batch": 32},
    {"id": "job-005", "name": "hpo_sweep_8",  "status": "QUEUED",    "node": None,         "type": "hpo",      "elapsed_h": 0.0, "est_total_h": 6.0,  "gpu_alloc": 8, "gpu_used": 0.0, "batch": 128},
    {"id": "job-006", "name": "distill_v1",   "status": "QUEUED",    "node": None,         "type": "finetune",  "elapsed_h": 0.0, "est_total_h": 5.0,  "gpu_alloc": 4, "gpu_used": 0.0, "batch": 64},
    {"id": "job-007", "name": "cosmos_prep",  "status": "QUEUED",    "node": None,         "type": "sdg",      "elapsed_h": 0.0, "est_total_h": 2.0,  "gpu_alloc": 2, "gpu_used": 0.0, "batch": 16},
    {"id": "job-008", "name": "bc_1000demo",  "status": "COMPLETED", "node": "gpu-node-4", "type": "finetune",  "elapsed_h": 35.4, "est_total_h": 35.4, "gpu_alloc": 4, "gpu_used": 3.9, "batch": 32},
    {"id": "job-009", "name": "eval_ckpt_42", "status": "COMPLETED", "node": "gpu-node-1", "type": "eval",     "elapsed_h": 0.8, "est_total_h": 0.8,  "gpu_alloc": 1, "gpu_used": 0.9, "batch": 8},
    {"id": "job-010", "name": "dagger_r9_oom","status": "FAILED",    "node": "gpu-node-2", "type": "dagger",    "elapsed_h": 0.2, "est_total_h": 4.0,  "gpu_alloc": 4, "gpu_used": 4.0, "batch": 32, "error": "OOM at batch=32"},
]

NODES = [
    {"id": "gpu-node-1", "gpus": 8, "used": 5, "mem_gb": 640, "mem_used_gb": 390},
    {"id": "gpu-node-2", "gpus": 8, "used": 12, "mem_gb": 640, "mem_used_gb": 510},
    {"id": "gpu-node-3", "gpus": 4, "used": 2,  "mem_gb": 320, "mem_used_gb": 190},
    {"id": "gpu-node-4", "gpus": 8, "used": 4,  "mem_gb": 640, "mem_used_gb": 320},
]

TYPE_COLORS = {
    "dagger":   "#38bdf8",
    "finetune": "#a78bfa",
    "eval":     "#34d399",
    "sdg":      "#fbbf24",
    "hpo":      "#f472b6",
}

STATUS_COLORS = {
    "RUNNING":   "#38bdf8",
    "QUEUED":    "#94a3b8",
    "COMPLETED": "#34d399",
    "FAILED":    "#f87171",
}


def compute_metrics():
    running = [j for j in JOBS if j["status"] == "RUNNING"]
    queued  = [j for j in JOBS if j["status"] == "QUEUED"]
    failed  = [j for j in JOBS if j["status"] == "FAILED"]

    # Resource waste: jobs where gpu_used/gpu_alloc < 0.6
    waste_jobs = [j for j in running if j["gpu_used"] / j["gpu_alloc"] < 0.6]
    waste_pct  = (len(waste_jobs) / max(len(running), 1)) * 100

    # Avg queued wait estimate (2.1h average)
    avg_wait = 2.1

    oom_rate  = len(failed) / len(JOBS) * 100
    reclaim   = 18.0  # $/day

    return {
        "queue_depth":    len(queued),
        "avg_wait_h":     avg_wait,
        "resource_waste": round(waste_pct, 1),
        "oom_rate":       round(oom_rate, 1),
        "reclaim_day":    reclaim,
        "running":        len(running),
        "completed":      len([j for j in JOBS if j["status"] == "COMPLETED"]),
        "failed":         len(failed),
    }


# ---------------------------------------------------------------------------
# SVG builders
# ---------------------------------------------------------------------------

def svg_gantt() -> str:
    """Horizontal Gantt chart: 10 jobs across 4 GPU nodes."""
    W, H = 760, 320
    row_h  = 28
    left   = 130
    top    = 40
    tl_w   = W - left - 20
    max_h  = 10.0  # hours axis

    def px(hours):
        return left + (hours / max_h) * tl_w

    lines = []
    lines.append(f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg" style="font-family:monospace;font-size:11px;">')
    lines.append(f'<rect width="{W}" height="{H}" fill="#0f172a" rx="8"/>')

    # Title
    lines.append(f'<text x="{W//2}" y="22" fill="#e2e8f0" font-size="13" font-weight="bold" text-anchor="middle">Job Queue — Gantt View (10 Jobs / 4 Nodes)</text>')

    # X-axis grid + labels
    for h in range(0, 11, 2):
        x = px(h)
        lines.append(f'<line x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{top + 10*row_h}" stroke="#1e293b" stroke-width="1"/>')
        lines.append(f'<text x="{x:.1f}" y="{top + 10*row_h + 14}" fill="#64748b" text-anchor="middle">{h}h</text>')

    # Sort jobs by node then id for layout
    job_rows = sorted(JOBS, key=lambda j: (j["node"] or "zzz", j["id"]))

    for i, job in enumerate(job_rows):
        y = top + i * row_h
        status  = job["status"]
        elapsed = job["elapsed_h"]
        est     = job["est_total_h"]
        color   = TYPE_COLORS.get(job["type"], "#94a3b8")
        s_color = STATUS_COLORS.get(status, "#94a3b8")

        # Row label
        label = f"{job['name'][:14]}"
        lines.append(f'<text x="{left-6}" y="{y+17}" fill="{s_color}" text-anchor="end">{label}</text>')

        if status in ("RUNNING", "COMPLETED", "FAILED"):
            # Completed portion
            bar_w = max(2, (elapsed / max_h) * tl_w)
            lines.append(f'<rect x="{left:.1f}" y="{y+5}" width="{bar_w:.1f}" height="18" fill="{color}" rx="3" opacity="0.9"/>')
            # Remaining (estimated)
            if status == "RUNNING" and est > elapsed:
                rem_w = ((est - elapsed) / max_h) * tl_w
                lines.append(f'<rect x="{left+bar_w:.1f}" y="{y+5}" width="{rem_w:.1f}" height="18" fill="{color}" rx="3" opacity="0.3"/>')
            # Status badge
            bx = left + bar_w + 4
            lines.append(f'<text x="{bx:.1f}" y="{y+17}" fill="{s_color}" font-size="10">{status}</text>')
        else:
            # QUEUED — show estimated bar starting from "now" (2h mark)
            now_px  = px(2.0)
            wait_offset = 2.1  # avg wait
            bar_start = px(2.0 + wait_offset)
            bar_w = (est / max_h) * tl_w
            lines.append(f'<rect x="{bar_start:.1f}" y="{y+5}" width="{bar_w:.1f}" height="18" fill="{color}" rx="3" opacity="0.25" stroke-dasharray="4 2" stroke="{color}" stroke-width="1"/>')
            lines.append(f'<text x="{bar_start+4:.1f}" y="{y+17}" fill="#64748b" font-size="10">~{wait_offset}h wait</text>')

    # "Now" marker
    now_x = px(2.0)
    lines.append(f'<line x1="{now_x:.1f}" y1="{top}" x2="{now_x:.1f}" y2="{top+10*row_h}" stroke="#C74634" stroke-width="2" stroke-dasharray="5 3"/>')
    lines.append(f'<text x="{now_x+3:.1f}" y="{top-6}" fill="#C74634" font-size="11" font-weight="bold">NOW</text>')

    lines.append('</svg>')
    return '\n'.join(lines)


def svg_resource_efficiency() -> str:
    """Bar chart: allocated vs used GPUs per running/completed job."""
    W, H = 760, 280
    left, right_margin = 60, 30
    top, bottom = 40, 50
    chart_h = H - top - bottom
    chart_w = W - left - right_margin

    relevant = [j for j in JOBS if j["status"] in ("RUNNING", "COMPLETED")]
    n        = len(relevant)
    bar_group_w = chart_w / max(n, 1)
    bar_w    = bar_group_w * 0.35
    max_gpus = 10

    def py(gpus):
        return top + chart_h - (gpus / max_gpus) * chart_h

    lines = []
    lines.append(f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg" style="font-family:monospace;font-size:11px;">')
    lines.append(f'<rect width="{W}" height="{H}" fill="#0f172a" rx="8"/>')
    lines.append(f'<text x="{W//2}" y="22" fill="#e2e8f0" font-size="13" font-weight="bold" text-anchor="middle">GPU Efficiency — Allocated vs Actual Usage (reclaim opp: $18/day)</text>')

    # Y-axis grid
    for g in range(0, 11, 2):
        y = py(g)
        lines.append(f'<line x1="{left}" y1="{y:.1f}" x2="{W-right_margin}" y2="{y:.1f}" stroke="#1e293b" stroke-width="1"/>')
        lines.append(f'<text x="{left-6}" y="{y+4:.1f}" fill="#64748b" text-anchor="end">{g}</text>')

    # 60% threshold line
    threshold_y = py(0)  # relative — draw at 60% of each bar, handled per-bar

    for i, job in enumerate(relevant):
        cx      = left + i * bar_group_w + bar_group_w / 2
        alloc   = job["gpu_alloc"]
        used    = job["gpu_used"]
        waste   = used / alloc < 0.6
        alloc_y = py(alloc)
        used_y  = py(used)
        alloc_h = top + chart_h - alloc_y
        used_h  = top + chart_h - used_y

        # Allocated bar (faded)
        lines.append(f'<rect x="{cx - bar_w:.1f}" y="{alloc_y:.1f}" width="{bar_w:.1f}" height="{alloc_h:.1f}" fill="#334155" rx="2"/>')
        lines.append(f'<text x="{cx - bar_w/2:.1f}" y="{alloc_y-4:.1f}" fill="#64748b" text-anchor="middle" font-size="9">{alloc}A</text>')

        # Used bar
        used_color = "#f87171" if waste else "#38bdf8"
        lines.append(f'<rect x="{cx:.1f}" y="{used_y:.1f}" width="{bar_w:.1f}" height="{used_h:.1f}" fill="{used_color}" rx="2" opacity="0.85"/>')
        pct = int(used / alloc * 100)
        lines.append(f'<text x="{cx + bar_w/2:.1f}" y="{used_y-4:.1f}" fill="{used_color}" text-anchor="middle" font-size="9">{pct}%</text>')

        # Waste annotation
        if waste:
            lines.append(f'<text x="{cx + bar_w/2:.1f}" y="{used_y+14:.1f}" fill="#f87171" text-anchor="middle" font-size="9">WASTE</text>')

        # X label
        label = job["name"][:10]
        lines.append(f'<text x="{cx:.1f}" y="{H-8}" fill="#94a3b8" text-anchor="middle" font-size="9">{label}</text>')

    # Legend
    lx = W - right_margin - 160
    lines.append(f'<rect x="{lx}" y="{top}" width="12" height="12" fill="#334155" rx="2"/>')
    lines.append(f'<text x="{lx+16}" y="{top+10}" fill="#94a3b8" font-size="10">Allocated</text>')
    lines.append(f'<rect x="{lx}" y="{top+18}" width="12" height="12" fill="#38bdf8" rx="2"/>')
    lines.append(f'<text x="{lx+16}" y="{top+28}" fill="#94a3b8" font-size="10">Used (efficient)</text>')
    lines.append(f'<rect x="{lx}" y="{top+36}" width="12" height="12" fill="#f87171" rx="2"/>')
    lines.append(f'<text x="{lx+16}" y="{top+46}" fill="#94a3b8" font-size="10">Used (&lt;60% — waste)</text>')

    lines.append('</svg>')
    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def build_html() -> str:
    m     = compute_metrics()
    gantt = svg_gantt()
    reff  = svg_resource_efficiency()
    now   = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    status_rows = ""
    for job in JOBS:
        sc = STATUS_COLORS.get(job["status"], "#94a3b8")
        tc = TYPE_COLORS.get(job["type"], "#94a3b8")
        err = job.get("error", "—")
        node = job["node"] or "—"
        pct  = f"{job['gpu_used']/job['gpu_alloc']*100:.0f}%" if job["gpu_alloc"] else "—"
        status_rows += f"""
        <tr>
          <td style="color:#e2e8f0">{job['id']}</td>
          <td style="color:#e2e8f0;font-weight:600">{job['name']}</td>
          <td><span style="color:{sc};border:1px solid {sc};padding:1px 6px;border-radius:4px;font-size:11px">{job['status']}</span></td>
          <td style="color:{tc}">{job['type']}</td>
          <td style="color:#94a3b8">{node}</td>
          <td style="color:#94a3b8">{job['elapsed_h']}h / {job['est_total_h']}h</td>
          <td style="color:#94a3b8">{pct}</td>
          <td style="color:#f87171;font-size:11px">{err}</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>HPC Job Monitor — Port 8276</title>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',system-ui,sans-serif;padding:24px}}
    h1{{font-size:22px;font-weight:700;color:#f1f5f9;margin-bottom:4px}}
    .sub{{color:#64748b;font-size:13px;margin-bottom:24px}}
    .accent{{color:#C74634}}
    .kpi-row{{display:flex;gap:16px;flex-wrap:wrap;margin-bottom:28px}}
    .kpi{{background:#1e293b;border:1px solid #334155;border-radius:10px;padding:16px 20px;min-width:140px;flex:1}}
    .kpi .label{{font-size:11px;color:#64748b;text-transform:uppercase;letter-spacing:.05em}}
    .kpi .value{{font-size:26px;font-weight:700;color:#38bdf8;margin-top:4px}}
    .kpi .value.warn{{color:#f87171}}
    .kpi .value.ok{{color:#34d399}}
    .kpi .value.neutral{{color:#fbbf24}}
    .card{{background:#1e293b;border:1px solid #334155;border-radius:10px;padding:20px;margin-bottom:20px}}
    .card h2{{font-size:14px;font-weight:600;color:#94a3b8;margin-bottom:16px;text-transform:uppercase;letter-spacing:.05em}}
    table{{width:100%;border-collapse:collapse;font-size:12px}}
    th{{color:#64748b;font-weight:500;text-align:left;padding:6px 10px;border-bottom:1px solid #334155}}
    td{{padding:6px 10px;border-bottom:1px solid #1e293b}}
    tr:hover td{{background:#0f172a}}
    footer{{color:#334155;font-size:11px;margin-top:24px;text-align:center}}
  </style>
</head>
<body>
  <h1>HPC Job Monitor <span class="accent">// OCI GPU Fleet</span></h1>
  <div class="sub">Training pipeline batch job tracker &mdash; {now}</div>

  <div class="kpi-row">
    <div class="kpi"><div class="label">Queue Depth</div><div class="value neutral">{m['queue_depth']}</div></div>
    <div class="kpi"><div class="label">Avg Wait Time</div><div class="value neutral">{m['avg_wait_h']}h</div></div>
    <div class="kpi"><div class="label">Resource Waste</div><div class="value warn">{m['resource_waste']}%</div></div>
    <div class="kpi"><div class="label">OOM Failure Rate</div><div class="value warn">{m['oom_rate']}%</div></div>
    <div class="kpi"><div class="label">Reclaim Opp.</div><div class="value warn">${m['reclaim_day']}/day</div></div>
    <div class="kpi"><div class="label">Running / Done</div><div class="value ok">{m['running']} / {m['completed']}</div></div>
  </div>

  <div class="card">
    <h2>Job Gantt — Queue Timeline</h2>
    {gantt}
  </div>

  <div class="card">
    <h2>GPU Efficiency — Allocated vs Used</h2>
    {reff}
  </div>

  <div class="card">
    <h2>All Jobs</h2>
    <table>
      <thead><tr><th>ID</th><th>Name</th><th>Status</th><th>Type</th><th>Node</th><th>Elapsed / Est</th><th>GPU%</th><th>Error</th></tr></thead>
      <tbody>{status_rows}</tbody>
    </table>
  </div>

  <footer>OCI Robot Cloud &mdash; HPC Job Monitor &mdash; port 8276</footer>
</body>
</html>"""


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

if USE_FASTAPI:
    app = FastAPI(title="HPC Job Monitor", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return HTMLResponse(content=build_html())

    @app.get("/api/jobs")
    async def api_jobs():
        return {"jobs": JOBS, "metrics": compute_metrics()}

    @app.get("/api/nodes")
    async def api_nodes():
        return {"nodes": NODES}

    @app.get("/health")
    async def health():
        return {"status": "ok", "port": 8276, "service": "hpc_job_monitor"}


# ---------------------------------------------------------------------------
# Stdlib fallback
# ---------------------------------------------------------------------------

class _StdlibHandler:
    def __init__(self, *a, **kw):
        pass

if not USE_FASTAPI:
    from http.server import BaseHTTPRequestHandler, HTTPServer
    import urllib.parse

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            path = urllib.parse.urlparse(self.path).path
            if path == "/api/jobs":
                body = json.dumps({"jobs": JOBS, "metrics": compute_metrics()}).encode()
                ct   = "application/json"
            elif path == "/health":
                body = json.dumps({"status": "ok", "port": 8276}).encode()
                ct   = "application/json"
            else:
                body = build_html().encode()
                ct   = "text/html"
            self.send_response(200)
            self.send_header("Content-Type", ct)
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass


if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8276)
    else:
        print("FastAPI not found — starting stdlib server on port 8276")
        server = HTTPServer(("0.0.0.0", 8276), _Handler)
        server.serve_forever()
