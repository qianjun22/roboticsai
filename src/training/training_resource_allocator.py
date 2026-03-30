"""Training Resource Allocator — FastAPI port 8707"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8707

def build_html():
    random.seed(42 + int(math.floor(random.random() * 1000)))

    # Active training jobs
    job_names = [
        "GR00T-N1.6-finetune-v3", "DAgger-run7-policy", "BC-baseline-v2",
        "Curriculum-Stage2", "Distill-Teacher2Student", "MultiTask-Adapter",
    ]
    statuses = ["RUNNING", "RUNNING", "QUEUED", "RUNNING", "PENDING", "RUNNING"]
    gpu_allocs = [8, 4, 0, 2, 0, 4]
    cpu_allocs = [32, 16, 0, 8, 0, 16]
    mem_allocs = [320, 160, 0, 64, 0, 128]
    progress = [round(random.uniform(0.1, 0.95), 2) for _ in job_names]
    eta_mins = [random.randint(5, 480) for _ in job_names]
    priorities = ["HIGH", "HIGH", "NORMAL", "NORMAL", "LOW", "HIGH"]
    status_colors = {"RUNNING": "#34d399", "QUEUED": "#f97316", "PENDING": "#94a3b8"}

    job_rows = ""
    for name, st, gp, cp, mp, prog, eta, pri in zip(
        job_names, statuses, gpu_allocs, cpu_allocs, mem_allocs, progress, eta_mins, priorities
    ):
        sc = status_colors.get(st, "#94a3b8")
        bar_fill = int(prog * 140)
        job_rows += f"""
        <tr>
          <td style="padding:8px 10px;font-size:0.82rem">{name}</td>
          <td style="padding:8px 10px"><span style="color:{sc};font-weight:bold">{st}</span></td>
          <td style="padding:8px 10px;text-align:center">{gp}</td>
          <td style="padding:8px 10px;text-align:center">{cp}</td>
          <td style="padding:8px 10px;text-align:center">{mp}GB</td>
          <td style="padding:8px 10px">
            <div style="background:#334155;border-radius:4px;height:8px;width:140px">
              <div style="background:#38bdf8;height:8px;border-radius:4px;width:{bar_fill}px"></div>
            </div>
            <span style="font-size:0.7rem;color:#64748b">{int(prog*100)}% | ETA {eta}m</span>
          </td>
          <td style="padding:8px 10px;color:#a78bfa;font-size:0.8rem">{pri}</td>
        </tr>"""

    # Resource utilization over 30 steps
    steps = 30
    gpu_util_series = [round(55 + 30 * math.sin(i * math.pi / 8) + random.uniform(-5, 5), 1) for i in range(steps)]
    cpu_util_series = [round(40 + 20 * math.cos(i * math.pi / 6) + random.uniform(-3, 3), 1) for i in range(steps)]
    mem_util_series = [round(60 + 15 * math.sin(i * math.pi / 10 + 1) + random.uniform(-2, 2), 1) for i in range(steps)]

    chart_h = 100
    chart_w = steps * 14 + 20

    def make_line(series, color):
        pts = " ".join(
            f"{10 + i * 14},{chart_h - int(v / 100 * chart_h)}"
            for i, v in enumerate(series)
        )
        return f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2"/>'

    gpu_line = make_line(gpu_util_series, "#C74634")
    cpu_line = make_line(cpu_util_series, "#38bdf8")
    mem_line = make_line(mem_util_series, "#a78bfa")

    # Cluster capacity
    total_gpus = 16
    used_gpus = sum(gpu_allocs)
    total_cpus = 128
    used_cpus = sum(cpu_allocs)
    total_mem = 1024
    used_mem = sum(mem_allocs)

    gpu_pct = round(used_gpus / total_gpus * 100)
    cpu_pct = round(used_cpus / total_cpus * 100)
    mem_pct = round(used_mem / total_mem * 100)

    current_gpu = round(gpu_util_series[-1], 1)
    current_cpu = round(cpu_util_series[-1], 1)
    current_mem = round(mem_util_series[-1], 1)

    def gauge_bar(pct, color):
        return f"""
        <div style="background:#334155;border-radius:4px;height:14px;width:100%;margin-top:6px">
          <div style="background:{color};height:14px;border-radius:4px;width:{pct}%;transition:width 0.3s"></div>
        </div>
        <div style="font-size:0.7rem;color:#64748b;margin-top:2px">{pct}% allocated</div>"""

    # Cost estimate
    gpu_cost_hr = round(used_gpus * 3.06, 2)  # A100 ~$3.06/hr OCI
    running_jobs = sum(1 for s in statuses if s == "RUNNING")

    return f"""<!DOCTYPE html><html><head><title>Training Resource Allocator</title>
<meta http-equiv="refresh" content="15">
<style>
  body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui;padding:20px}}
  h1{{color:#C74634;margin:0 0 4px 0;font-size:1.6rem}}
  h2{{color:#38bdf8;font-size:1rem;margin:0 0 12px 0}}
  .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin-bottom:20px}}
  .card{{background:#1e293b;padding:20px;border-radius:8px;border:1px solid #334155}}
  .metric{{font-size:2rem;font-weight:bold;color:#f8fafc}}
  .label{{font-size:0.75rem;color:#94a3b8;margin-top:4px}}
  .good{{color:#34d399}}.warn{{color:#f97316}}.alert{{color:#ef4444}}
  table{{width:100%;border-collapse:collapse;font-size:0.82rem}}
  th{{color:#64748b;font-size:0.72rem;text-align:left;padding:8px 10px;border-bottom:1px solid #334155}}
  tr:nth-child(even){{background:#162032}}
</style></head>
<body>
<h1>Training Resource Allocator</h1>
<p style="color:#64748b;margin:0 0 20px 0">Port {PORT} | OCI Robot Cloud | Multi-job GPU/CPU/MEM scheduler</p>

<div class="grid">
  <div class="card"><div class="metric good">{running_jobs}</div><div class="label">Active Training Jobs</div></div>
  <div class="card"><div class="metric {'alert' if gpu_pct > 90 else 'warn' if gpu_pct > 70 else 'good'}">{used_gpus}<span style="font-size:1rem">/{total_gpus}</span></div><div class="label">GPUs Allocated</div></div>
  <div class="card"><div class="metric">{cpu_pct}<span style="font-size:1rem">%</span></div><div class="label">CPU Utilization</div></div>
  <div class="card"><div class="metric">{mem_pct}<span style="font-size:1rem">%</span></div><div class="label">Memory Utilization</div></div>
  <div class="card"><div class="metric warn">${gpu_cost_hr}</div><div class="label">Est. GPU Cost/hr</div></div>
</div>

<div style="display:grid;grid-template-columns:2fr 1fr;gap:12px;margin-bottom:12px">
  <div class="card">
    <h2>Resource Utilization (30 checkpoints)</h2>
    <svg width="{chart_w}" height="{chart_h + 10}" style="display:block">
      <line x1="10" y1="0" x2="10" y2="{chart_h}" stroke="#1e293b" stroke-width="1"/>
      <line x1="10" y1="{chart_h}" x2="{chart_w}" y2="{chart_h}" stroke="#334155" stroke-width="1"/>
      {gpu_line}
      {cpu_line}
      {mem_line}
    </svg>
    <div style="font-size:0.7rem;color:#64748b;margin-top:6px">
      <span style="color:#C74634">&#9644;</span> GPU &nbsp;
      <span style="color:#38bdf8">&#9644;</span> CPU &nbsp;
      <span style="color:#a78bfa">&#9644;</span> Memory
    </div>
  </div>
  <div class="card">
    <h2>Cluster Capacity</h2>
    <div style="margin-bottom:16px">
      <div style="display:flex;justify-content:space-between"><span style="color:#64748b;font-size:0.8rem">GPU</span><span style="color:#C74634">{used_gpus}/{total_gpus}</span></div>
      {gauge_bar(gpu_pct, '#C74634')}
    </div>
    <div style="margin-bottom:16px">
      <div style="display:flex;justify-content:space-between"><span style="color:#64748b;font-size:0.8rem">CPU cores</span><span style="color:#38bdf8">{used_cpus}/{total_cpus}</span></div>
      {gauge_bar(cpu_pct, '#38bdf8')}
    </div>
    <div>
      <div style="display:flex;justify-content:space-between"><span style="color:#64748b;font-size:0.8rem">Memory</span><span style="color:#a78bfa">{used_mem}/{total_mem}GB</span></div>
      {gauge_bar(mem_pct, '#a78bfa')}
    </div>
  </div>
</div>

<div class="card">
  <h2>Active Job Roster</h2>
  <table>
    <thead><tr>
      <th>JOB NAME</th><th>STATUS</th><th>GPUS</th><th>CPUs</th><th>MEM</th><th>PROGRESS</th><th>PRIORITY</th>
    </tr></thead>
    <tbody>{job_rows}</tbody>
  </table>
</div>

<div class="card" style="margin-top:12px">
  <h2>Scheduler Configuration</h2>
  <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:16px;font-size:0.85rem">
    <div><span style="color:#64748b">Strategy:</span> <span style="color:#38bdf8">FAIR_SHARE</span></div>
    <div><span style="color:#64748b">Preemption:</span> <span style="color:#34d399">ENABLED</span></div>
    <div><span style="color:#64748b">Gang Scheduling:</span> <span style="color:#34d399">ON</span></div>
    <div><span style="color:#64748b">Backfill:</span> <span style="color:#38bdf8">CONSERVATIVE</span></div>
    <div><span style="color:#64748b">Checkpoint Freq:</span> <span style="color:#38bdf8">500 steps</span></div>
    <div><span style="color:#64748b">Health:</span> <span style="color:#34d399">HEALTHY</span></div>
  </div>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Training Resource Allocator")
    @app.get("/", response_class=HTMLResponse)
    def index(): return build_html()
    @app.get("/health")
    def health(): return {"status": "ok", "port": PORT}

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
