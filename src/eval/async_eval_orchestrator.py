"""Async Eval Orchestrator — FastAPI port 8735"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8735

def build_html():
    random.seed()

    # Simulate async eval jobs across tasks
    tasks = ["PickCube", "StackBlocks", "OpenDrawer", "PourLiquid", "AssembleGear", "SortObjects"]
    n_tasks = len(tasks)

    # Per-task success rates over 20 eval rounds (sigmoid-shaped improvement)
    rounds = 20
    def success_series(base, gain):
        return [round(min(0.98, base + gain * (1 / (1 + math.exp(-(r - 10) * 0.4))) + random.uniform(-0.03, 0.03)), 3)
                for r in range(rounds)]

    task_series = {
        "PickCube":     success_series(0.30, 0.55),
        "StackBlocks":  success_series(0.20, 0.45),
        "OpenDrawer":   success_series(0.25, 0.50),
        "PourLiquid":   success_series(0.15, 0.40),
        "AssembleGear": success_series(0.10, 0.35),
        "SortObjects":  success_series(0.22, 0.48),
    }
    colors = ["#38bdf8", "#a78bfa", "#34d399", "#f97316", "#fb7185", "#facc15"]

    # SVG multi-line chart
    w_svg, h_svg = 620, 180
    def to_pts(series):
        pts = []
        for i, v in enumerate(series):
            x = 44 + i * (w_svg - 64) / (rounds - 1)
            y = h_svg - 22 - v * (h_svg - 44)
            pts.append(f"{x:.1f},{y:.1f}")
        return " ".join(pts)

    lines_svg = ""
    for (task, series), color in zip(task_series.items(), colors):
        lines_svg += f'<polyline points="{to_pts(series)}" fill="none" stroke="{color}" stroke-width="1.8" opacity="0.9"/>\n'

    grid_svg = "".join(
        f'<line x1="44" y1="{h_svg-22 - k*(h_svg-44)//4}" x2="{w_svg-20}" y2="{h_svg-22 - k*(h_svg-44)//4}" stroke="#1e293b" stroke-width="1"/>'
        for k in range(1, 5)
    )

    legend_svg = ""
    for i, (task, color) in enumerate(zip(tasks, colors)):
        lx = 44 + i * 92
        legend_svg += f'<rect x="{lx}" y="{h_svg+2}" width="10" height="10" fill="{color}" rx="2"/>'
        legend_svg += f'<text x="{lx+14}" y="{h_svg+11}" fill="{color}" font-size="10">{task}</text>'

    # Gantt-style async job timeline (12 concurrent workers)
    n_workers = 12
    n_jobs = 40
    timeline_w, timeline_h = 620, 200
    job_h = (timeline_h - 30) / n_workers
    gantt_svg = ""
    random.seed(7)
    for j in range(n_jobs):
        worker = j % n_workers
        start = random.uniform(0, 85)
        dur   = random.uniform(3, 14)
        task_idx = j % n_tasks
        color = colors[task_idx]
        x = 10 + start * (timeline_w - 20) / 100
        y = 10 + worker * job_h
        bw = dur * (timeline_w - 20) / 100
        alpha = 0.75
        gantt_svg += (
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{job_h*0.75:.1f}" '
            f'fill="{color}" rx="2" opacity="{alpha}"/>'
        )
    for w in range(n_workers):
        y = 10 + w * job_h + job_h * 0.375
        gantt_svg += f'<text x="4" y="{y:.1f}" fill="#475569" font-size="8" text-anchor="end">W{w:02d}</text>'

    # Throughput sparkline (jobs/min)
    n_ticks = 60
    throughput = [round(18 + 14 * math.sin(t * 0.18) + random.uniform(-3, 3), 1) for t in range(n_ticks)]
    spark_w, spark_h = 620, 70
    spark_pts = " ".join(
        f"{10 + i * (spark_w - 20) / (n_ticks - 1):.1f},{spark_h - 8 - (v - 0) / 40 * (spark_h - 16):.1f}"
        for i, v in enumerate(throughput)
    )
    area_pts = (
        f"10,{spark_h-8} " + spark_pts + f" {10 + (n_ticks-1)*(spark_w-20)/(n_ticks-1):.1f},{spark_h-8}"
    )

    # Summary stats
    latest_sr = {task: series[-1] for task, series in task_series.items()}
    avg_sr = round(sum(latest_sr.values()) / n_tasks, 3)
    best_task = max(latest_sr, key=latest_sr.get)
    total_jobs = random.randint(12400, 13800)
    queue_depth = random.randint(0, 8)
    avg_throughput = round(sum(throughput) / n_ticks, 1)

    return f"""<!DOCTYPE html><html><head><title>Async Eval Orchestrator</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui;padding:20px}}
h1{{color:#C74634;margin-bottom:4px}}h2{{color:#38bdf8;font-size:14px;margin:0 0 12px}}
.card{{background:#1e293b;padding:18px 20px;margin:8px 0;border-radius:8px}}
.stat{{display:inline-block;background:#0f172a;border-radius:6px;padding:10px 18px;margin:5px;text-align:center}}
.stat .val{{font-size:26px;font-weight:700;color:#38bdf8}}.stat .lbl{{font-size:11px;color:#94a3b8}}
.badge{{display:inline-block;background:#0369a1;color:#bae6fd;border-radius:4px;padding:2px 8px;font-size:11px;margin-left:8px}}
.tbl{{width:100%;border-collapse:collapse;font-size:12px}}
.tbl th{{color:#94a3b8;text-align:left;padding:4px 8px;border-bottom:1px solid #334155}}
.tbl td{{padding:4px 8px;border-bottom:1px solid #1e293b}}
.bar-bg{{background:#0f172a;border-radius:3px;height:8px;width:100px;display:inline-block;vertical-align:middle}}
.bar-fg{{background:#38bdf8;border-radius:3px;height:8px;display:inline-block}}
svg text{{font-family:system-ui}}
</style></head>
<body>
<h1>Async Eval Orchestrator <span class="badge">RUNNING</span></h1>
<p style="color:#94a3b8;margin-top:4px">{n_workers}-worker parallel evaluation pipeline for GR00T policy checkpoints &mdash; port {PORT}</p>

<div class="card">
  <h2>Cluster Summary</h2>
  <div class="stat"><div class="val">{n_workers}</div><div class="lbl">Active Workers</div></div>
  <div class="stat"><div class="val">{total_jobs:,}</div><div class="lbl">Jobs Completed</div></div>
  <div class="stat"><div class="val">{avg_sr:.3f}</div><div class="lbl">Avg Success Rate</div></div>
  <div class="stat"><div class="val">{avg_throughput}</div><div class="lbl">Jobs / Min</div></div>
  <div class="stat"><div class="val">{queue_depth}</div><div class="lbl">Queue Depth</div></div>
  <div class="stat"><div class="val">{best_task}</div><div class="lbl">Best Task</div></div>
</div>

<div class="card">
  <h2>Success Rate per Task — 20 Eval Rounds</h2>
  <svg width="{w_svg}" height="{h_svg + 22}" style="background:#0f172a;border-radius:6px">
    {grid_svg}
    {lines_svg}
    {legend_svg}
    <text x="8" y="{h_svg//2}" fill="#64748b" font-size="10" text-anchor="middle" transform="rotate(-90,8,{h_svg//2})">success</text>
    <text x="{w_svg//2}" y="{h_svg+20}" text-anchor="middle" fill="#64748b" font-size="10">eval round</text>
  </svg>
</div>

<div class="card">
  <h2>Worker Timeline (Gantt) — Last 100 Eval Slots</h2>
  <svg width="{timeline_w}" height="{timeline_h}" style="background:#0f172a;border-radius:6px">
    {gantt_svg}
    <text x="{timeline_w//2}" y="{timeline_h-4}" text-anchor="middle" fill="#64748b" font-size="10">time &#8594;</text>
  </svg>
</div>

<div class="card">
  <h2>Throughput Sparkline — Jobs/Min (last 60 ticks)</h2>
  <svg width="{spark_w}" height="{spark_h}" style="background:#0f172a;border-radius:6px">
    <polygon points="{area_pts}" fill="#0ea5e9" opacity="0.18"/>
    <polyline points="{spark_pts}" fill="none" stroke="#0ea5e9" stroke-width="2"/>
    <text x="14" y="14" fill="#38bdf8" font-size="11">peak: {max(throughput)} j/m</text>
    <text x="14" y="{spark_h-6}" fill="#64748b" font-size="10">tick 0</text>
    <text x="{spark_w-14}" y="{spark_h-6}" text-anchor="end" fill="#64748b" font-size="10">tick {n_ticks}</text>
  </svg>
</div>

<div class="card">
  <h2>Per-Task Final Success Rates</h2>
  <table class="tbl">
    <tr><th>Task</th><th>Success Rate</th><th>Bar</th><th>Status</th></tr>
    {''.join(f"<tr><td style='color:{colors[i]}'>{task}</td><td>{sr:.3f}</td><td><span class='bar-bg'><span class='bar-fg' style='width:{int(sr*100)}px;background:{colors[i]}'></span></span></td><td style='color:{'#34d399' if sr>=0.6 else '#f97316'}'>{('PASS' if sr>=0.6 else 'TRAIN')}</td></tr>" for i,(task,sr) in enumerate(latest_sr.items()))}
  </table>
</div>

<div class="card" style="font-size:12px;color:#64748b">
  <b style="color:#94a3b8">Architecture:</b> asyncio task pool with {n_workers} concurrent LIBERO simulation workers; priority queue with checkpoint versioning.<br>
  <b style="color:#94a3b8">Endpoints:</b>
  <code style="background:#0f172a;padding:2px 6px;border-radius:3px">POST /submit</code>
  <code style="background:#0f172a;padding:2px 6px;border-radius:3px">GET /status/{{job_id}}</code>
  <code style="background:#0f172a;padding:2px 6px;border-radius:3px">GET /results</code>
  <code style="background:#0f172a;padding:2px 6px;border-radius:3px">GET /workers</code>
  <code style="background:#0f172a;padding:2px 6px;border-radius:3px">DELETE /cancel/{{job_id}}</code>
  <code style="background:#0f172a;padding:2px 6px;border-radius:3px">GET /health</code>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Async Eval Orchestrator")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return build_html()

    @app.get("/health")
    def health():
        return {"status": "ok", "port": PORT, "service": "async_eval_orchestrator"}

    @app.post("/submit")
    def submit(checkpoint: str = "gr00t-v1", task: str = "PickCube", episodes: int = 20):
        job_id = f"job-{random.randint(10000, 99999)}"
        return {"job_id": job_id, "checkpoint": checkpoint, "task": task, "episodes": episodes, "status": "queued"}

    @app.get("/status/{job_id}")
    def status(job_id: str):
        states = ["queued", "running", "running", "running", "done"]
        return {"job_id": job_id, "status": random.choice(states), "progress": random.randint(0, 100)}

    @app.get("/results")
    def results():
        tasks = ["PickCube", "StackBlocks", "OpenDrawer", "PourLiquid", "AssembleGear", "SortObjects"]
        return {task: round(random.uniform(0.4, 0.95), 3) for task in tasks}

    @app.get("/workers")
    def workers():
        return {"active": random.randint(8, 12), "idle": random.randint(0, 4), "total": 12}

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(build_html().encode())
    def log_message(self, *a): pass

if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
