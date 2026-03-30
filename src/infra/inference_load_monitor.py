"""Inference Load Monitor — FastAPI port 8463"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8463

def build_html():
    random.seed(41)
    hours = list(range(24))
    # req/s simulation: business hours peak
    req_s = []
    for h in hours:
        if 9 <= h <= 17:
            base = 8.5 + 3.0 * math.sin((h - 9) * math.pi / 8)
        elif 6 <= h < 9 or 17 < h <= 20:
            base = 3.0 + 1.5 * math.sin((h - 6) * math.pi / 14)
        else:
            base = 0.8
        req_s.append(max(0.2, base + random.gauss(0, 0.5)))

    capacity = 12.0  # req/s GPU capacity
    load_pts = " ".join(f"{35+i*22:.1f},{170-req_s[i]/capacity*140:.1f}" for i in range(24))
    cap_y = 170 - 140
    fill_pts = f"35,170 " + " ".join(f"{35+i*22:.1f},{170-req_s[i]/capacity*140:.1f}" for i in range(24)) + f" {35+23*22:.1f},170"
    load_svg = f'<polygon points="{fill_pts}" fill="#38bdf8" opacity="0.15"/>'
    load_svg += f'<polyline points="{load_pts}" fill="none" stroke="#38bdf8" stroke-width="2.5"/>'
    load_svg += f'<line x1="35" y1="{cap_y}" x2="{35+23*22}" y2="{cap_y}" stroke="#C74634" stroke-width="1.5" stroke-dasharray="5,3"/>'
    load_svg += f'<text x="{35+23*22+5}" y="{cap_y+4}" fill="#C74634" font-size="9">Capacity {capacity} req/s</text>'
    for h in [0, 4, 8, 12, 16, 20, 23]:
        load_svg += f'<text x="{35+h*22}" y="183" fill="#64748b" font-size="9" text-anchor="middle">{h:02d}h</text>'

    # 7-day forecast
    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    day_peak = [9.2, 9.8, 10.1, 9.5, 8.7, 3.2, 2.1]
    day_proj = [9.4, 10.0, 10.3, 9.7, 8.9, 3.5, 2.3]
    forecast_svg = ""
    for i, (day, peak, proj) in enumerate(zip(day_names, day_peak, day_proj)):
        x = 30 + i * 68
        h_peak = int(peak / 12 * 130)
        h_proj = int(proj / 12 * 130)
        forecast_svg += f'<rect x="{x}" y="{145-h_peak}" width="36" height="{h_peak}" fill="#38bdf8" opacity="0.7" rx="3"/>'
        forecast_svg += f'<rect x="{x+38}" y="{145-h_proj}" width="20" height="{h_proj}" fill="#f59e0b" opacity="0.6" rx="3"/>'
        forecast_svg += f'<text x="{x+27}" y="160" fill="#64748b" font-size="10" text-anchor="middle">{day}</text>'

    # AI World spike annotation
    forecast_svg += f'<text x="350" y="25" fill="#C74634" font-size="10">AI World Sep: 10× spike</text>'
    forecast_svg += f'<text x="350" y="38" fill="#94a3b8" font-size="9">pre-provision 8 A100 nodes</text>'

    return f"""<!DOCTYPE html>
<html>
<head><title>Inference Load Monitor</title>
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
.warn{{font-size:12px;color:#f59e0b;margin-top:4px}}
</style>
</head>
<body>
<div class="hdr">
  <span class="badge">PORT {PORT}</span>
  <h1>Inference Load Monitor — Real-Time &amp; Forecast</h1>
</div>
<div class="metrics">
  <div class="m"><div class="mv">10.1</div><div class="ml">Peak req/s (Wed)</div></div>
  <div class="m"><div class="mv">12.0</div><div class="ml">GPU Capacity req/s</div></div>
  <div class="m"><div class="mv">84%</div><div class="ml">Peak Utilization</div><div class="warn">⚠ Sep spike needs 8× capacity</div></div>
  <div class="m"><div class="mv">99.9%</div><div class="ml">SLA at Peak Load</div></div>
</div>
<div class="grid">
  <div class="card">
    <h3>24h Load vs Capacity</h3>
    <svg viewBox="0 0 570 200" width="100%">
      <line x1="32" y1="10" x2="32" y2="173" stroke="#334155" stroke-width="1"/>
      <line x1="32" y1="173" x2="560" y2="173" stroke="#334155" stroke-width="1"/>
      {load_svg}
    </svg>
  </div>
  <div class="card">
    <h3>7-Day Load Forecast (actual + projected)</h3>
    <svg viewBox="0 0 510 175" width="100%">
      <line x1="22" y1="10" x2="22" y2="148" stroke="#334155" stroke-width="1"/>
      <line x1="22" y1="148" x2="500" y2="148" stroke="#334155" stroke-width="1"/>
      {forecast_svg}
      <rect x="22" y="10" width="10" height="10" fill="#38bdf8" opacity="0.7"/>
      <text x="36" y="20" fill="#94a3b8" font-size="9">Actual</text>
      <rect x="22" y="24" width="10" height="10" fill="#f59e0b" opacity="0.6"/>
      <text x="36" y="34" fill="#94a3b8" font-size="9">Forecast</text>
    </svg>
  </div>
</div>
</body>
</html>"""

if USE_FASTAPI:
    app = FastAPI(title="Inference Load Monitor")
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
