"""Adaptive Inference Scheduler — FastAPI port 8844"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8844

def build_html():
    # Generate queue depth data points for 24h SVG chart
    hours = list(range(24))
    # Simulate realistic queue depths per tier over 24h
    enterprise_depths = [round(max(0, 8 + 6*math.sin((h-9)*math.pi/8) + random.uniform(-1,1)), 1) for h in hours]
    standard_depths   = [round(max(0, 20 + 15*math.sin((h-10)*math.pi/7) + random.uniform(-2,2)), 1) for h in hours]
    batch_depths      = [round(max(0, 35 + 25*math.sin((h-14)*math.pi/9) + random.uniform(-3,3)), 1) for h in hours]

    def to_svg_points(depths, y_scale=2.0, y_offset=10):
        pts = []
        for i, d in enumerate(depths):
            x = 30 + i * (520/23)
            y = 130 - d * y_scale + y_offset
            pts.append(f"{x:.1f},{y:.1f}")
        return " ".join(pts)

    ent_pts = to_svg_points(enterprise_depths, y_scale=2.5)
    std_pts = to_svg_points(standard_depths,   y_scale=1.5)
    bat_pts = to_svg_points(batch_depths,       y_scale=1.0)

    # Build x-axis hour labels (every 4h)
    x_labels = ""
    for i, h in enumerate(hours):
        if h % 4 == 0:
            x = 30 + i * (520/23)
            x_labels += f'<text x="{x:.1f}" y="155" fill="#94a3b8" font-size="10" text-anchor="middle">{h:02d}:00</text>\n'

    return f"""<!DOCTYPE html><html><head><title>Adaptive Inference Scheduler</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui}}
h1{{color:#C74634;padding:20px 20px 0}}h2{{color:#38bdf8}}
.card{{background:#1e293b;padding:20px;margin:10px;border-radius:8px}}
.metrics{{display:flex;gap:20px;flex-wrap:wrap}}
.metric{{background:#0f172a;padding:14px 20px;border-radius:6px;border-left:4px solid #C74634}}
.metric .val{{font-size:2em;font-weight:bold;color:#f8fafc}}
.metric .lbl{{font-size:0.8em;color:#94a3b8;margin-top:4px}}
.legend{{display:flex;gap:18px;margin-bottom:8px;font-size:0.85em}}
.dot{{width:12px;height:12px;border-radius:50%;display:inline-block;margin-right:5px;vertical-align:middle}}
</style></head>
<body>
<h1>Adaptive Inference Scheduler</h1>
<p style="padding:0 20px;color:#94a3b8">Dynamic request routing across GPU nodes with priority tiers · Port {PORT}</p>

<div class="card">
  <h2>Queue Depth per Tier — 24h</h2>
  <div class="legend">
    <span><span class="dot" style="background:#f59e0b"></span>Enterprise SLA</span>
    <span><span class="dot" style="background:#38bdf8"></span>Standard</span>
    <span><span class="dot" style="background:#6366f1"></span>Batch</span>
  </div>
  <svg width="580" height="170" style="display:block">
    <!-- Grid lines -->
    <line x1="30" y1="10"  x2="30" y2="140" stroke="#334155" stroke-width="1"/>
    <line x1="30" y1="10"  x2="555" y2="10"  stroke="#334155" stroke-width="0.5" stroke-dasharray="4,3"/>
    <line x1="30" y1="47"  x2="555" y2="47"  stroke="#334155" stroke-width="0.5" stroke-dasharray="4,3"/>
    <line x1="30" y1="84"  x2="555" y2="84"  stroke="#334155" stroke-width="0.5" stroke-dasharray="4,3"/>
    <line x1="30" y1="140" x2="555" y2="140" stroke="#334155" stroke-width="1"/>
    <!-- Y-axis labels -->
    <text x="25" y="13"  fill="#94a3b8" font-size="9" text-anchor="end">60</text>
    <text x="25" y="50"  fill="#94a3b8" font-size="9" text-anchor="end">40</text>
    <text x="25" y="87"  fill="#94a3b8" font-size="9" text-anchor="end">20</text>
    <text x="25" y="143" fill="#94a3b8" font-size="9" text-anchor="end">0</text>
    <!-- Tier polylines -->
    <polyline points="{bat_pts}" fill="none" stroke="#6366f1" stroke-width="1.8" stroke-linejoin="round"/>
    <polyline points="{std_pts}" fill="none" stroke="#38bdf8" stroke-width="1.8" stroke-linejoin="round"/>
    <polyline points="{ent_pts}" fill="none" stroke="#f59e0b" stroke-width="2.2" stroke-linejoin="round"/>
    <!-- X-axis labels -->
    {x_labels}
  </svg>
</div>

<div class="card">
  <h2>Metrics</h2>
  <div class="metrics">
    <div class="metric"><div class="val">847</div><div class="lbl">Peak Req/hr</div></div>
    <div class="metric"><div class="val">−23%</div><div class="lbl">Tail Latency Reduction</div></div>
    <div class="metric"><div class="val">267ms</div><div class="lbl">p99 Latency</div></div>
    <div class="metric"><div class="val">3</div><div class="lbl">Priority Tiers</div></div>
  </div>
</div>

<div class="card">
  <h2>Tier Configuration</h2>
  <table style="width:100%;border-collapse:collapse;font-size:0.9em">
    <thead><tr style="border-bottom:1px solid #334155;color:#94a3b8">
      <th style="text-align:left;padding:8px">Tier</th>
      <th style="text-align:left;padding:8px">SLA Target</th>
      <th style="text-align:left;padding:8px">GPU Allocation</th>
      <th style="text-align:left;padding:8px">Queue Cap</th>
    </tr></thead>
    <tbody>
      <tr style="border-bottom:1px solid #1e293b">
        <td style="padding:8px;color:#f59e0b">Enterprise SLA</td>
        <td style="padding:8px">p99 &lt; 200ms</td>
        <td style="padding:8px">40%</td>
        <td style="padding:8px">16</td>
      </tr>
      <tr style="border-bottom:1px solid #1e293b">
        <td style="padding:8px;color:#38bdf8">Standard</td>
        <td style="padding:8px">p99 &lt; 400ms</td>
        <td style="padding:8px">40%</td>
        <td style="padding:8px">64</td>
      </tr>
      <tr>
        <td style="padding:8px;color:#6366f1">Batch</td>
        <td style="padding:8px">Best-effort</td>
        <td style="padding:8px">20%</td>
        <td style="padding:8px">256</td>
      </tr>
    </tbody>
  </table>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Adaptive Inference Scheduler")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return build_html()

    @app.get("/health")
    def health():
        return {"status": "ok", "port": PORT}

    @app.get("/metrics")
    def metrics():
        return {
            "peak_req_per_hr": 847,
            "tail_latency_reduction_pct": 23,
            "p99_latency_ms": 267,
            "tiers": ["enterprise_sla", "standard", "batch"],
        }

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
