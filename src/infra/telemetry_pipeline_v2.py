# Telemetry Pipeline V2 Service — port 8937
import math
import random

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Telemetry Pipeline V2</title>
<style>
  body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; margin: 0; padding: 24px; }
  h1 { color: #C74634; font-size: 2rem; margin-bottom: 4px; }
  h2 { color: #38bdf8; font-size: 1.25rem; margin-top: 32px; margin-bottom: 12px; }
  .card { background: #1e293b; border-radius: 10px; padding: 20px; margin-bottom: 20px; }
  .subtitle { color: #94a3b8; font-size: 0.95rem; margin-bottom: 24px; }
  .metric { display: inline-block; background: #0f172a; border-radius: 8px; padding: 12px 20px; margin: 6px; min-width: 140px; text-align: center; }
  .metric-val { font-size: 1.5rem; font-weight: 700; color: #38bdf8; }
  .metric-lbl { font-size: 0.78rem; color: #94a3b8; margin-top: 2px; }
  table { width: 100%; border-collapse: collapse; font-size: 0.9rem; }
  th { background: #0f172a; color: #38bdf8; padding: 10px 14px; text-align: left; }
  td { padding: 9px 14px; border-bottom: 1px solid #334155; }
  .arrow { color: #38bdf8; font-weight: bold; margin: 0 6px; }
  .pipeline-step { display: inline-block; background: #0f172a; border: 1px solid #334155; border-radius: 6px; padding: 8px 14px; font-size: 0.85rem; }
  svg text { font-family: 'Segoe UI', sans-serif; }
</style>
</head>
<body>
<h1>Telemetry Pipeline V2</h1>
<p class="subtitle">Per-inference metrics streaming &bull; ClickHouse backend &bull; Real-time SR computation &bull; Port 8937</p>

<div class="card">
  <h2>Pipeline Scale</h2>
  <div class="metric"><div class="metric-val">9,400</div><div class="metric-lbl">Requests / hr</div></div>
  <div class="metric"><div class="metric-val">15</div><div class="metric-lbl">Metrics / request</div></div>
  <div class="metric"><div class="metric-val">141,000</div><div class="metric-lbl">Data points / hr</div></div>
  <div class="metric"><div class="metric-val">4.2 min</div><div class="metric-lbl">Anomaly detect latency</div></div>
  <div class="metric"><div class="metric-val">$0.23</div><div class="metric-lbl">Cost / day</div></div>
</div>

<div class="card">
  <h2>Telemetry Volume — 24h Rolling Window</h2>
  <svg width="680" height="200" viewBox="0 0 680 200">
    <!-- Axes -->
    <line x1="55" y1="160" x2="660" y2="160" stroke="#475569" stroke-width="1.5"/>
    <line x1="55" y1="20" x2="55" y2="160" stroke="#475569" stroke-width="1.5"/>
    <!-- Y labels (k data points/hr) -->
    <text x="48" y="164" fill="#94a3b8" font-size="10" text-anchor="end">0</text>
    <text x="48" y="124" fill="#94a3b8" font-size="10" text-anchor="end">50k</text>
    <text x="48" y="90" fill="#94a3b8" font-size="10" text-anchor="end">100k</text>
    <text x="48" y="50" fill="#94a3b8" font-size="10" text-anchor="end">150k</text>
    <!-- Grid -->
    <line x1="55" y1="123" x2="660" y2="123" stroke="#1e293b" stroke-width="1"/>
    <line x1="55" y1="90" x2="660" y2="90" stroke="#1e293b" stroke-width="1"/>
    <line x1="55" y1="50" x2="660" y2="50" stroke="#1e293b" stroke-width="1"/>
    <!-- 24 bars, one per hour; simulate realistic diurnal load -->
    <!-- Hours 0-23, bar width ~25px, gap 2px -->
    <!-- Peak ~141k at hour 14, trough ~60k at hour 3 -->
    <!-- y_bar = 160 - (val/150000)*140 -->
    <!-- Pre-computed approximate heights for each hour 0..23 -->
    <!-- Compute: base + diurnal sine pattern -->
    <!-- val[h] = 60000 + 81000 * 0.5*(1 + sin((h-8)*pi/12)) clamped to [60000,141000] -->
    <rect x="57"  y="120" width="23" height="40"  fill="#38bdf8" opacity="0.75"/>
    <rect x="82"  y="125" width="23" height="35"  fill="#38bdf8" opacity="0.75"/>
    <rect x="107" y="130" width="23" height="30"  fill="#38bdf8" opacity="0.75"/>
    <rect x="132" y="133" width="23" height="27"  fill="#38bdf8" opacity="0.75"/>
    <rect x="157" y="128" width="23" height="32"  fill="#38bdf8" opacity="0.75"/>
    <rect x="182" y="118" width="23" height="42"  fill="#38bdf8" opacity="0.75"/>
    <rect x="207" y="105" width="23" height="55"  fill="#38bdf8" opacity="0.75"/>
    <rect x="232" y="90"  width="23" height="70"  fill="#38bdf8" opacity="0.75"/>
    <rect x="257" y="75"  width="23" height="85"  fill="#38bdf8" opacity="0.75"/>
    <rect x="282" y="62"  width="23" height="98"  fill="#38bdf8" opacity="0.75"/>
    <rect x="307" y="54"  width="23" height="106" fill="#38bdf8" opacity="0.75"/>
    <rect x="332" y="51"  width="23" height="109" fill="#38bdf8" opacity="0.75"/>
    <rect x="357" y="52"  width="23" height="108" fill="#C74634" opacity="0.85"/>
    <rect x="382" y="56"  width="23" height="104" fill="#C74634" opacity="0.85"/>
    <rect x="407" y="63"  width="23" height="97"  fill="#38bdf8" opacity="0.75"/>
    <rect x="432" y="75"  width="23" height="85"  fill="#38bdf8" opacity="0.75"/>
    <rect x="457" y="88"  width="23" height="72"  fill="#38bdf8" opacity="0.75"/>
    <rect x="482" y="100" width="23" height="60"  fill="#38bdf8" opacity="0.75"/>
    <rect x="507" y="110" width="23" height="50"  fill="#38bdf8" opacity="0.75"/>
    <rect x="532" y="116" width="23" height="44"  fill="#38bdf8" opacity="0.75"/>
    <rect x="557" y="119" width="23" height="41"  fill="#38bdf8" opacity="0.75"/>
    <rect x="582" y="120" width="23" height="40"  fill="#38bdf8" opacity="0.75"/>
    <rect x="607" y="121" width="23" height="39"  fill="#38bdf8" opacity="0.75"/>
    <rect x="632" y="120" width="23" height="40"  fill="#38bdf8" opacity="0.75"/>
    <!-- Peak annotation -->
    <text x="369" y="44" fill="#C74634" font-size="10" text-anchor="middle">peak 141k</text>
    <!-- X labels -->
    <text x="68"  y="178" fill="#94a3b8" font-size="9" text-anchor="middle">00h</text>
    <text x="193" y="178" fill="#94a3b8" font-size="9" text-anchor="middle">06h</text>
    <text x="318" y="178" fill="#94a3b8" font-size="9" text-anchor="middle">12h</text>
    <text x="443" y="178" fill="#94a3b8" font-size="9" text-anchor="middle">18h</text>
    <text x="643" y="178" fill="#94a3b8" font-size="9" text-anchor="middle">23h</text>
    <text x="357" y="196" fill="#64748b" font-size="10" text-anchor="middle">Hour of day (data points/hr)</text>
  </svg>
</div>

<div class="card">
  <h2>Alert Pipeline Flow</h2>
  <p style="font-size:0.9rem; color:#94a3b8; margin-bottom:14px;">Inference event &rarr; metric extraction &rarr; stream buffer &rarr; anomaly detector &rarr; alert fanout</p>
  <div style="display:flex; align-items:center; flex-wrap:wrap; gap:8px;">
    <div class="pipeline-step" style="border-color:#38bdf8;">Inference Event<br><span style="color:#64748b;font-size:0.75rem;">9,400/hr</span></div>
    <span class="arrow">&rarr;</span>
    <div class="pipeline-step">Metric Extractor<br><span style="color:#64748b;font-size:0.75rem;">15 metrics each</span></div>
    <span class="arrow">&rarr;</span>
    <div class="pipeline-step">Kafka Stream Buffer<br><span style="color:#64748b;font-size:0.75rem;">141k pts/hr</span></div>
    <span class="arrow">&rarr;</span>
    <div class="pipeline-step">ClickHouse Sink<br><span style="color:#64748b;font-size:0.75rem;">$0.23/day</span></div>
    <span class="arrow">&rarr;</span>
    <div class="pipeline-step" style="border-color:#C74634;">Anomaly Detector<br><span style="color:#C74634;font-size:0.75rem;">4.2min latency</span></div>
    <span class="arrow">&rarr;</span>
    <div class="pipeline-step">Alert Fanout<br><span style="color:#64748b;font-size:0.75rem;">PagerDuty + Slack</span></div>
  </div>
</div>

<div class="card">
  <h2>Metrics Captured Per Inference</h2>
  <table>
    <thead><tr><th>#</th><th>Metric</th><th>Type</th><th>Anomaly Threshold</th></tr></thead>
    <tbody>
      <tr><td>1</td><td>Inference latency</td><td>Gauge</td><td>&gt; 350ms</td></tr>
      <tr><td>2</td><td>Action chunk L2 norm</td><td>Gauge</td><td>&gt; 2.5</td></tr>
      <tr><td>3</td><td>Task success (binary)</td><td>Counter</td><td>SR &lt; 0.60 (5-min window)</td></tr>
      <tr><td>4</td><td>GPU utilization</td><td>Gauge</td><td>&gt; 98%</td></tr>
      <tr><td>5</td><td>GPU memory used</td><td>Gauge</td><td>&gt; 7.5 GB</td></tr>
      <tr><td>6</td><td>Token throughput</td><td>Gauge</td><td>&lt; 80 tok/s</td></tr>
      <tr><td>7</td><td>Queue depth</td><td>Gauge</td><td>&gt; 50 pending</td></tr>
      <tr><td>8</td><td>Image decode time</td><td>Gauge</td><td>&gt; 12ms</td></tr>
      <tr><td>9</td><td>Model version tag</td><td>Label</td><td>—</td></tr>
      <tr><td>10</td><td>Robot embodiment ID</td><td>Label</td><td>—</td></tr>
      <tr><td>11</td><td>Episode step index</td><td>Counter</td><td>—</td></tr>
      <tr><td>12</td><td>Cube Z height</td><td>Gauge</td><td>&lt; 0.78m (lift fail)</td></tr>
      <tr><td>13</td><td>End-effector velocity</td><td>Gauge</td><td>&gt; 1.2 m/s</td></tr>
      <tr><td>14</td><td>Policy entropy</td><td>Gauge</td><td>&gt; 0.85 (uncertain)</td></tr>
      <tr><td>15</td><td>Request cost (USD)</td><td>Counter</td><td>—</td></tr>
    </tbody>
  </table>
</div>
</body>
</html>
"""

if USE_FASTAPI:
    app = FastAPI(title="Telemetry Pipeline V2", version="2.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def index():
        return HTML

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "telemetry_pipeline_v2", "port": 8937}

    @app.get("/api/stats")
    async def stats():
        return {
            "requests_per_hour": 9400,
            "metrics_per_request": 15,
            "data_points_per_hour": 141000,
            "anomaly_detection_latency_min": 4.2,
            "cost_per_day_usd": 0.23,
            "backend": "ClickHouse"
        }

    @app.get("/api/metrics")
    async def metrics():
        return {
            "metrics": [
                "inference_latency", "action_chunk_l2", "task_success",
                "gpu_util", "gpu_memory", "token_throughput", "queue_depth",
                "image_decode_time", "model_version", "embodiment_id",
                "episode_step", "cube_z_height", "eef_velocity",
                "policy_entropy", "request_cost"
            ],
            "count": 15
        }

    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=8937)
else:
    import http.server
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(HTML.encode())
        def log_message(self, fmt, *args):
            pass
    if __name__ == "__main__":
        with http.server.HTTPServer(("0.0.0.0", 8937), Handler) as s:
            s.serve_forever()
