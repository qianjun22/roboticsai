"""OCI Spot Scheduler — FastAPI port 8451"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8451

def build_html():
    random.seed(13)
    hours = list(range(24))
    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

    # 7-day × 24-hour spot availability heatmap
    avail = []
    for d in range(7):
        row = []
        for h in range(24):
            # business hours = lower availability, weekends = higher
            base = 0.88 if d >= 5 else 0.72
            if 9 <= h <= 17 and d < 5:
                base -= 0.18
            v = max(0.2, min(1.0, base + random.gauss(0, 0.08)))
            row.append(v)
        avail.append(row)

    cell_w, cell_h = 22, 26
    hmap = ""
    for d, row in enumerate(avail):
        for h, v in enumerate(row):
            x = 45 + h * cell_w
            y = 10 + d * cell_h
            if v >= 0.80:
                color = "#22c55e"
            elif v >= 0.60:
                color = "#f59e0b"
            else:
                color = "#C74634"
            hmap += f'<rect x="{x}" y="{y}" width="{cell_w-1}" height="{cell_h-2}" fill="{color}" opacity="{0.3+v*0.65:.2f}" rx="2"/>'
        hmap += f'<text x="40" y="{10 + d*cell_h + 17}" fill="#94a3b8" font-size="10" text-anchor="end">{days[d]}</text>'
    for h in [0, 6, 12, 18, 23]:
        hmap += f'<text x="{45+h*cell_w+cell_w//2}" y="{10+7*cell_h+12}" fill="#64748b" font-size="9" text-anchor="middle">{h:02d}h</text>'

    # recovery time bars
    scenarios = ["ckpt_restart", "graceful_pause", "spot_failover", "preempt+retry", "DR_fallback"]
    times = [2.3, 1.1, 4.7, 6.2, 15.0]
    rec_bars = ""
    for i, (s, t) in enumerate(zip(scenarios, times)):
        y = 20 + i * 32
        w = int(t / 16.0 * 300)
        color = "#22c55e" if t < 3 else "#f59e0b" if t < 8 else "#C74634"
        rec_bars += f'<rect x="130" y="{y}" width="{w}" height="22" fill="{color}" rx="3" opacity="0.85"/>'
        rec_bars += f'<text x="126" y="{y+15}" fill="#94a3b8" font-size="10" text-anchor="end">{s}</text>'
        rec_bars += f'<text x="{130+w+5}" y="{y+15}" fill="#e2e8f0" font-size="10">{t}min</text>'

    return f"""<!DOCTYPE html>
<html>
<head><title>OCI Spot Scheduler</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',sans-serif}}
.hdr{{background:#1e293b;padding:16px 24px;border-bottom:2px solid #C74634;display:flex;align-items:center;gap:12px}}
.hdr h1{{margin:0;font-size:20px;color:#f1f5f9}}
.badge{{background:#C74634;color:#fff;padding:3px 10px;border-radius:12px;font-size:11px;font-weight:700}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;padding:20px}}
.card{{background:#1e293b;border-radius:10px;padding:18px;border:1px solid #334155}}
.card h3{{margin:0 0 12px;font-size:14px;color:#94a3b8;text-transform:uppercase;letter-spacing:.05em}}
.metrics{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;padding:16px 20px}}
.m{{background:#1e293b;border-radius:8px;padding:12px 16px;border:1px solid #334155}}
.mv{{font-size:24px;font-weight:700;color:#38bdf8}}
.ml{{font-size:11px;color:#64748b;margin-top:2px}}
.delta{{font-size:12px;color:#22c55e;margin-top:4px}}
</style>
</head>
<body>
<div class="hdr">
  <span class="badge">PORT {PORT}</span>
  <h1>OCI Spot Scheduler — Cost Optimization</h1>
</div>
<div class="metrics">
  <div class="m"><div class="mv">65%</div><div class="ml">Cost Savings</div><div class="delta">$147→$51/day</div></div>
  <div class="m"><div class="mv">0</div><div class="ml">Failed Jobs (30d)</div><div class="delta">100% recovery</div></div>
  <div class="m"><div class="mv">2.3min</div><div class="ml">Avg Recovery Time</div></div>
  <div class="m"><div class="mv">Ashburn</div><div class="ml">Best Availability</div><div class="delta">90% avg avail</div></div>
</div>
<div class="grid">
  <div class="card">
    <h3>Spot Availability Heatmap (7d × 24h)</h3>
    <svg viewBox="0 0 580 200" width="100%">
      {hmap}
    </svg>
    <p style="font-size:11px;color:#94a3b8;margin:6px 0 0">Green=High avail, Amber=Medium, Red=Low. Business hours Mon-Fri have reduced availability.</p>
  </div>
  <div class="card">
    <h3>Preemption Recovery Time by Scenario</h3>
    <svg viewBox="0 0 470 180" width="100%">
      <line x1="128" y1="10" x2="128" y2="178" stroke="#334155" stroke-width="1"/>
      <line x1="258" y1="10" x2="258" y2="178" stroke="#334155" stroke-width="1" stroke-dasharray="3,3" opacity="0.5"/>
      <text x="258" y="8" fill="#f59e0b" font-size="9" text-anchor="middle">5min SLA</text>
      {rec_bars}
    </svg>
  </div>
</div>
</body>
</html>"""

if USE_FASTAPI:
    app = FastAPI(title="OCI Spot Scheduler")
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
