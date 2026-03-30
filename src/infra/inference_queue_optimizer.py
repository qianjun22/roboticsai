"""Inference Queue Optimizer — FastAPI port 8706"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8706

def build_html():
    # Generate queue depth over time (24 slots)
    slots = 24
    queue_depths = [max(0, int(18 + 12 * math.sin(i * math.pi / 6) + random.uniform(-3, 3))) for i in range(slots)]
    latencies = [round(20 + 15 * math.cos(i * math.pi / 8) + random.uniform(-2, 4), 1) for i in range(slots)]
    throughputs = [round(120 + 40 * math.sin(i * math.pi / 5 + 1) + random.uniform(-5, 5), 1) for i in range(slots)]

    max_depth = max(queue_depths) or 1
    max_lat = max(latencies) or 1
    max_thr = max(throughputs) or 1

    bar_w = 14
    chart_h = 120
    chart_w = slots * (bar_w + 2) + 20

    # Queue depth bars
    depth_bars = ""
    for i, d in enumerate(queue_depths):
        h = int(d / max_depth * chart_h)
        x = 10 + i * (bar_w + 2)
        y = chart_h - h
        color = "#C74634" if d > 25 else "#38bdf8"
        depth_bars += f'<rect x="{x}" y="{y}" width="{bar_w}" height="{h}" fill="{color}" rx="2"/>'

    # Latency line
    lat_points = " ".join(
        f"{10 + i * (bar_w + 2) + bar_w // 2},{chart_h - int(l / max_lat * chart_h)}"
        for i, l in enumerate(latencies)
    )
    lat_polyline = f'<polyline points="{lat_points}" fill="none" stroke="#a78bfa" stroke-width="2"/>'

    # Throughput line
    thr_points = " ".join(
        f"{10 + i * (bar_w + 2) + bar_w // 2},{chart_h - int(t / max_thr * chart_h)}"
        for i, t in enumerate(throughputs)
    )
    thr_polyline = f'<polyline points="{thr_points}" fill="none" stroke="#34d399" stroke-width="2"/>'

    # Priority bucket stats
    priorities = ["CRITICAL", "HIGH", "NORMAL", "LOW", "BATCH"]
    bucket_counts = [random.randint(2, 8), random.randint(10, 30), random.randint(40, 80),
                     random.randint(20, 50), random.randint(5, 15)]
    bucket_colors = ["#ef4444", "#f97316", "#38bdf8", "#94a3b8", "#64748b"]
    bucket_rows = ""
    for p, c, col in zip(priorities, bucket_counts, bucket_colors):
        bucket_rows += f"""
        <tr>
          <td style="color:{col};font-weight:bold;padding:6px 12px">{p}</td>
          <td style="padding:6px 12px;text-align:right">{c}</td>
          <td style="padding:6px 12px">
            <div style="background:#334155;border-radius:4px;height:10px;width:160px">
              <div style="background:{col};height:10px;border-radius:4px;width:{min(int(c/80*160),160)}px"></div>
            </div>
          </td>
        </tr>"""

    total_queued = sum(bucket_counts)
    avg_latency = round(sum(latencies) / len(latencies), 1)
    peak_throughput = max(throughputs)
    gpu_util = round(65 + 20 * math.sin(random.uniform(0, math.pi)), 1)
    cache_hit = round(random.uniform(72, 94), 1)

    return f"""<!DOCTYPE html><html><head><title>Inference Queue Optimizer</title>
<meta http-equiv="refresh" content="10">
<style>
  body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui;padding:20px}}
  h1{{color:#C74634;margin:0 0 4px 0;font-size:1.6rem}}
  h2{{color:#38bdf8;font-size:1rem;margin:0 0 12px 0}}
  .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin-bottom:20px}}
  .card{{background:#1e293b;padding:20px;border-radius:8px;border:1px solid #334155}}
  .metric{{font-size:2rem;font-weight:bold;color:#f8fafc}}
  .label{{font-size:0.75rem;color:#94a3b8;margin-top:4px}}
  .alert{{color:#ef4444}}.good{{color:#34d399}}
  table{{width:100%;border-collapse:collapse}}
  tr:nth-child(even){{background:#162032}}
</style></head>
<body>
<h1>Inference Queue Optimizer</h1>
<p style="color:#64748b;margin:0 0 20px 0">Port {PORT} | OCI Robot Cloud | Adaptive priority scheduling</p>

<div class="grid">
  <div class="card"><div class="metric {'alert' if total_queued > 100 else 'good'}">{total_queued}</div><div class="label">Total Queued Requests</div></div>
  <div class="card"><div class="metric">{avg_latency}<span style="font-size:1rem">ms</span></div><div class="label">Avg Queue Latency</div></div>
  <div class="card"><div class="metric">{peak_throughput}<span style="font-size:1rem">/s</span></div><div class="label">Peak Throughput</div></div>
  <div class="card"><div class="metric {'alert' if gpu_util > 90 else 'good'}">{gpu_util}<span style="font-size:1rem">%</span></div><div class="label">GPU Utilization</div></div>
  <div class="card"><div class="metric good">{cache_hit}<span style="font-size:1rem">%</span></div><div class="label">KV-Cache Hit Rate</div></div>
</div>

<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
  <div class="card">
    <h2>Queue Depth (24h) + Latency Overlay</h2>
    <svg width="{chart_w}" height="{chart_h + 10}" style="display:block">
      {depth_bars}
      {lat_polyline}
    </svg>
    <div style="font-size:0.7rem;color:#64748b;margin-top:6px">
      <span style="color:#38bdf8">&#9646;</span> Queue Depth &nbsp;
      <span style="color:#a78bfa">&#9644;</span> Latency (normalized)
    </div>
  </div>
  <div class="card">
    <h2>Throughput Over Time</h2>
    <svg width="{chart_w}" height="{chart_h + 10}" style="display:block">
      {thr_polyline}
      <line x1="10" y1="0" x2="10" y2="{chart_h}" stroke="#334155" stroke-width="1"/>
      <line x1="10" y1="{chart_h}" x2="{chart_w - 10}" y2="{chart_h}" stroke="#334155" stroke-width="1"/>
    </svg>
    <div style="font-size:0.7rem;color:#64748b;margin-top:6px">
      <span style="color:#34d399">&#9644;</span> Requests/sec
    </div>
  </div>
</div>

<div class="card" style="margin-top:12px">
  <h2>Priority Bucket Distribution</h2>
  <table>
    <thead><tr style="color:#64748b;font-size:0.75rem">
      <th style="text-align:left;padding:6px 12px">PRIORITY</th>
      <th style="text-align:right;padding:6px 12px">QUEUED</th>
      <th style="padding:6px 12px">FILL</th>
    </tr></thead>
    <tbody>{bucket_rows}</tbody>
  </table>
</div>

<div class="card" style="margin-top:12px">
  <h2>Optimization Parameters</h2>
  <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:16px;font-size:0.85rem">
    <div><span style="color:#64748b">Batch Window:</span> <span style="color:#38bdf8">{random.randint(10,50)}ms</span></div>
    <div><span style="color:#64748b">Max Batch Size:</span> <span style="color:#38bdf8">{random.choice([8,16,32,64])}</span></div>
    <div><span style="color:#64748b">Preemption Policy:</span> <span style="color:#34d399">WORK_CONSERVING</span></div>
    <div><span style="color:#64748b">Scheduler:</span> <span style="color:#38bdf8">MLFQ v2.1</span></div>
    <div><span style="color:#64748b">Overflow Action:</span> <span style="color:#f97316">BACKPRESSURE</span></div>
    <div><span style="color:#64748b">Health:</span> <span style="color:#34d399">HEALTHY</span></div>
  </div>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Inference Queue Optimizer")
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
