"""Eval Pipeline Orchestrator — FastAPI service on port 8262.

Orchestrates multi-stage evaluation pipelines with dependency management
and parallelism tracking for GR00T-based robot policies.
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

import random
import math
import json
from datetime import datetime, timedelta

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

STAGES = [
    {"id": "data_load",        "label": "data_load",        "deps": [],                                  "est_min": 8,  "act_min": 9,  "status": "done",    "parallel_group": 0},
    {"id": "preprocess",       "label": "preprocess",       "deps": ["data_load"],                       "est_min": 12, "act_min": 11, "status": "done",    "parallel_group": 1},
    {"id": "offline_metrics",  "label": "offline_metrics",  "deps": ["preprocess"],                     "est_min": 18, "act_min": 20, "status": "done",    "parallel_group": 2},
    {"id": "safety_checks",    "label": "safety_checks",    "deps": ["preprocess"],                     "est_min": 15, "act_min": 16, "status": "done",    "parallel_group": 2},
    {"id": "latency_test",     "label": "latency_test",     "deps": ["preprocess"],                     "est_min": 10, "act_min": 12, "status": "done",    "parallel_group": 2},
    {"id": "sim_rollout",      "label": "sim_rollout",      "deps": ["offline_metrics", "safety_checks"],"est_min": 25, "act_min": 27, "status": "running","parallel_group": 3},
    {"id": "real_robot_eval",  "label": "real_robot_eval",  "deps": ["sim_rollout"],                    "est_min": 35, "act_min": 35, "status": "pending", "parallel_group": 4},
    {"id": "report_generation","label": "report_generation","deps": ["real_robot_eval", "latency_test"], "est_min": 5,  "act_min": 5,  "status": "pending", "parallel_group": 5},
]

METRICS = {
    "model": "groot_v2",
    "pipeline_id": "eval-2026-03-30-001",
    "parallel_speedup": 1.67,
    "sequential_total_min": 112,
    "parallel_wall_clock_min": 67,
    "critical_path": ["data_load", "preprocess", "offline_metrics", "sim_rollout", "real_robot_eval", "report_generation"],
    "bottleneck_stage": "real_robot_eval",
    "failure_recovery_min": 4.2,
    "stages_complete": 5,
    "stages_total": 8,
    "parallel_savings_min": 45,
}

# ---------------------------------------------------------------------------
# SVG generators
# ---------------------------------------------------------------------------

def _stage_color(status: str) -> str:
    return {"done": "#22c55e", "running": "#38bdf8", "pending": "#475569", "failed": "#ef4444"}.get(status, "#475569")


def build_dag_svg() -> str:
    """Pipeline DAG SVG with nodes laid out left-to-right by parallel group."""
    W, H = 860, 320
    # Assign x positions per group
    group_x = {0: 60, 1: 170, 2: 310, 3: 530, 4: 650, 5: 780}
    # Within group assign y
    group_members: dict = {}
    for s in STAGES:
        g = s["parallel_group"]
        group_members.setdefault(g, []).append(s["id"])
    node_pos: dict = {}
    for g, members in group_members.items():
        count = len(members)
        for i, sid in enumerate(members):
            y = H // 2 + (i - (count - 1) / 2) * 80
            node_pos[sid] = (group_x[g], int(y))

    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#1e293b;border-radius:8px">')
    lines.append('<defs><marker id="arr" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">'
                 '<polygon points="0 0,8 3,0 6" fill="#64748b"/></marker></defs>')
    # Title
    lines.append(f'<text x="{W//2}" y="22" text-anchor="middle" fill="#94a3b8" font-size="13" font-family="monospace">'
                 'Eval Pipeline DAG — groot_v2</text>')
    # Edges
    id_map = {s["id"]: s for s in STAGES}
    for s in STAGES:
        x2, y2 = node_pos[s["id"]]
        for dep in s["deps"]:
            x1, y1 = node_pos[dep]
            lines.append(f'<line x1="{x1+46}" y1="{y1}" x2="{x2-46}" y2="{y2}" '
                         'stroke="#64748b" stroke-width="1.5" marker-end="url(#arr)"/>')
    # Nodes
    for s in STAGES:
        x, y = node_pos[s["id"]]
        col = _stage_color(s["status"])
        is_critical = s["id"] in METRICS["critical_path"]
        stroke = "#f59e0b" if is_critical else col
        lines.append(f'<rect x="{x-46}" y="{y-18}" width="92" height="36" rx="6" '
                     f'fill="{col}22" stroke="{stroke}" stroke-width="{2 if is_critical else 1}"/>')
        lines.append(f'<text x="{x}" y="{y-4}" text-anchor="middle" fill="{col}" '
                     f'font-size="10" font-family="monospace">{s["label"]}</text>')
        lines.append(f'<text x="{x}" y="{y+10}" text-anchor="middle" fill="#94a3b8" '
                     f'font-size="9" font-family="monospace">{s["act_min"]}min / {s["status"]}</text>')
    # Legend
    legend = [("done", "#22c55e", 10), ("running", "#38bdf8", 90), ("pending", "#475569", 170), ("critical", "#f59e0b", 250)]
    for lbl, col, lx in legend:
        lines.append(f'<rect x="{lx}" y="{H-22}" width="12" height="12" rx="2" fill="{col}44" stroke="{col}"/>')
        lines.append(f'<text x="{lx+16}" y="{H-12}" fill="#94a3b8" font-size="10" font-family="monospace">{lbl}</text>')
    lines.append('</svg>')
    return "\n".join(lines)


def build_gantt_svg() -> str:
    """Gantt chart showing parallel vs sequential execution."""
    W, H = 860, 360
    LEFT = 140  # label column width
    CHART_W = W - LEFT - 20
    SEQ_TOTAL = METRICS["sequential_total_min"]
    PAR_TOTAL = METRICS["parallel_wall_clock_min"]
    # Compute sequential start times (linear)
    seq_starts = {}
    t = 0
    for s in STAGES:
        seq_starts[s["id"]] = t
        t += s["act_min"]
    # Compute parallel start times based on group
    group_start = {0: 0, 1: 9, 2: 20, 3: 40, 4: 67, 5: 102}  # wall-clock minutes
    # Actually compute based on max dep end
    par_starts: dict = {}
    par_ends: dict = {}
    for s in STAGES:
        if not s["deps"]:
            par_starts[s["id"]] = 0
        else:
            par_starts[s["id"]] = max(par_ends.get(d, 0) for d in s["deps"])
        par_ends[s["id"]] = par_starts[s["id"]] + s["act_min"]

    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#1e293b;border-radius:8px">')
    # Title
    lines.append(f'<text x="{W//2}" y="22" text-anchor="middle" fill="#94a3b8" font-size="13" font-family="monospace">'
                 'Gantt: Parallel (top) vs Sequential (bottom) Execution</text>')
    # Grid lines
    for tick in range(0, SEQ_TOTAL + 1, 20):
        gx = LEFT + int(tick / SEQ_TOTAL * CHART_W)
        lines.append(f'<line x1="{gx}" y1="30" x2="{gx}" y2="{H-50}" stroke="#334155" stroke-width="1"/>')
        lines.append(f'<text x="{gx}" y="{H-35}" text-anchor="middle" fill="#64748b" font-size="9" font-family="monospace">{tick}m</text>')

    ROW_H = 24
    ROW_PAD = 4
    colors = ["#38bdf8", "#22c55e", "#a78bfa", "#f59e0b", "#C74634", "#34d399", "#fb923c", "#e879f9"]
    # Parallel rows
    for i, s in enumerate(STAGES):
        y = 38 + i * (ROW_H + ROW_PAD)
        ps = par_starts[s["id"]]
        pe = par_ends[s["id"]]
        bx = LEFT + int(ps / SEQ_TOTAL * CHART_W)
        bw = max(4, int((pe - ps) / SEQ_TOTAL * CHART_W))
        col = colors[i % len(colors)]
        # label
        lines.append(f'<text x="{LEFT-4}" y="{y+15}" text-anchor="end" fill="#94a3b8" font-size="10" font-family="monospace">{s["label"]}</text>')
        lines.append(f'<rect x="{bx}" y="{y+2}" width="{bw}" height="{ROW_H-4}" rx="3" fill="{col}55" stroke="{col}"/>')
        lines.append(f'<text x="{bx + bw//2}" y="{y+15}" text-anchor="middle" fill="{col}" font-size="9" font-family="monospace">{s["act_min"]}m</text>')

    # Summary bar
    par_bar_x = LEFT
    par_bar_w = int(PAR_TOTAL / SEQ_TOTAL * CHART_W)
    seq_bar_x = LEFT
    seq_bar_w = CHART_W
    bar_y = H - 28
    lines.append(f'<rect x="{par_bar_x}" y="{bar_y}" width="{par_bar_w}" height="12" rx="3" fill="#38bdf822" stroke="#38bdf8"/>')
    lines.append(f'<text x="{par_bar_x + par_bar_w + 4}" y="{bar_y+10}" fill="#38bdf8" font-size="10" font-family="monospace">Parallel: {PAR_TOTAL}min</text>')
    lines.append(f'<rect x="{seq_bar_x}" y="{bar_y-16}" width="{seq_bar_w}" height="12" rx="3" fill="#ef444422" stroke="#ef4444"/>')
    lines.append(f'<text x="{seq_bar_x + seq_bar_w + 4}" y="{bar_y-6}" fill="#ef4444" font-size="10" font-family="monospace">Sequential: {SEQ_TOTAL}min</text>')
    lines.append('</svg>')
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def build_html() -> str:
    dag = build_dag_svg()
    gantt = build_gantt_svg()
    stages_json = json.dumps(STAGES, indent=2)
    m = METRICS
    pct_done = int(m["stages_complete"] / m["stages_total"] * 100)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Eval Pipeline Orchestrator — Port 8262</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',monospace,sans-serif;padding:20px}}
  h1{{color:#C74634;font-size:1.6rem;margin-bottom:4px}}
  .sub{{color:#64748b;font-size:.85rem;margin-bottom:20px}}
  .cards{{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:12px;margin-bottom:24px}}
  .card{{background:#1e293b;border:1px solid #334155;border-radius:8px;padding:14px}}
  .card .val{{font-size:1.6rem;font-weight:700;color:#38bdf8}}
  .card .lbl{{font-size:.75rem;color:#64748b;margin-top:2px}}
  .card .val.green{{color:#22c55e}}
  .card .val.red{{color:#C74634}}
  .card .val.amber{{color:#f59e0b}}
  .section{{margin-bottom:28px}}
  .section h2{{font-size:1rem;color:#94a3b8;margin-bottom:10px;text-transform:uppercase;letter-spacing:.05em}}
  svg{{max-width:100%;height:auto}}
  .progress-bar{{background:#334155;border-radius:4px;height:12px;margin:8px 0}}
  .progress-fill{{background:linear-gradient(90deg,#38bdf8,#22c55e);height:12px;border-radius:4px;transition:width .3s}}
  table{{width:100%;border-collapse:collapse;font-size:.8rem}}
  th{{background:#1e293b;color:#64748b;padding:8px 10px;text-align:left;border-bottom:1px solid #334155}}
  td{{padding:7px 10px;border-bottom:1px solid #1e293b}}
  tr:hover td{{background:#1e293b}}
  .badge{{display:inline-block;padding:2px 8px;border-radius:9999px;font-size:.7rem;font-weight:600}}
  .done{{background:#22c55e22;color:#22c55e;border:1px solid #22c55e}}
  .running{{background:#38bdf822;color:#38bdf8;border:1px solid #38bdf8}}
  .pending{{background:#47556922;color:#94a3b8;border:1px solid #475569}}
  footer{{color:#334155;font-size:.75rem;margin-top:30px;text-align:center}}
</style>
</head>
<body>
<h1>Eval Pipeline Orchestrator</h1>
<p class="sub">Port 8262 &nbsp;|&nbsp; Model: {m['model']} &nbsp;|&nbsp; Pipeline: {m['pipeline_id']}</p>

<div class="cards">
  <div class="card"><div class="val green">{m['parallel_speedup']}x</div><div class="lbl">Parallelism Speedup</div></div>
  <div class="card"><div class="val">{m['parallel_wall_clock_min']}m</div><div class="lbl">Wall Clock (Parallel)</div></div>
  <div class="card"><div class="val red">{m['sequential_total_min']}m</div><div class="lbl">Sequential Estimate</div></div>
  <div class="card"><div class="val amber">{m['parallel_savings_min']}m</div><div class="lbl">Time Saved</div></div>
  <div class="card"><div class="val">{m['stages_complete']}/{m['stages_total']}</div><div class="lbl">Stages Complete</div></div>
  <div class="card"><div class="val">{m['failure_recovery_min']}m</div><div class="lbl">Failure Recovery</div></div>
</div>

<div class="section">
  <h2>Pipeline Progress</h2>
  <div class="progress-bar"><div class="progress-fill" style="width:{pct_done}%"></div></div>
  <p style="color:#64748b;font-size:.8rem">{pct_done}% complete — critical path: {' → '.join(m['critical_path'][:4])} → ...</p>
</div>

<div class="section">
  <h2>Pipeline DAG</h2>
  {dag}
</div>

<div class="section">
  <h2>Execution Gantt Chart</h2>
  {gantt}
</div>

<div class="section">
  <h2>Stage Details</h2>
  <table>
    <tr><th>Stage</th><th>Status</th><th>Dependencies</th><th>Est (min)</th><th>Actual (min)</th><th>Delta</th></tr>
    {''.join(f"<tr><td style='color:#e2e8f0'>{s['label']}</td><td><span class='badge {s['status']}'>{s['status']}</span></td><td style='color:#64748b'>{', '.join(s['deps']) if s['deps'] else '—'}</td><td>{s['est_min']}</td><td>{s['act_min']}</td><td style='color:{\"#ef4444\" if s[\"act_min\"]>s[\"est_min\"] else \"#22c55e\"}'>{s['act_min']-s['est_min']:+d}</td></tr>" for s in STAGES)}
  </table>
</div>

<footer>OCI Robot Cloud &mdash; Eval Pipeline Orchestrator v2 &mdash; {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC</footer>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

if HAS_FASTAPI:
    app = FastAPI(title="Eval Pipeline Orchestrator", version="2.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return build_html()

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "eval_pipeline_orchestrator", "port": 8262}

    @app.get("/metrics")
    async def metrics():
        return METRICS

    @app.get("/stages")
    async def stages():
        return STAGES

    @app.get("/dag")
    async def dag_svg():
        from fastapi.responses import Response
        return Response(content=build_dag_svg(), media_type="image/svg+xml")

    @app.get("/gantt")
    async def gantt_svg():
        from fastapi.responses import Response
        return Response(content=build_gantt_svg(), media_type="image/svg+xml")

else:
    # Fallback: stdlib http.server
    import http.server
    import socketserver

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            body = build_html().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            pass


if __name__ == "__main__":
    if HAS_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8262)
    else:
        PORT = 8262
        with socketserver.TCPServer(("", PORT), Handler) as httpd:
            print(f"Serving on http://0.0.0.0:{PORT} (stdlib fallback)")
            httpd.serve_forever()
