"""Safety Incident Dashboard — FastAPI port 8458"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8458

def build_html():
    random.seed(37)
    # 90-day incident timeline
    days = list(range(90))
    # simulated incidents: e-stops, soft-limits, near-miss, contact-force
    e_stops = [5, 28, 41, 68]
    soft_limits = [7, 14, 19, 31, 43, 52, 61, 72, 84]
    near_miss = [3, 12, 22, 35, 47, 58, 69, 78, 87]
    contact_force = [1, 4, 8, 11, 16, 21, 26, 33, 38, 45, 51, 57, 63, 70, 76, 82, 88]

    timeline_svg = ""
    # background bands
    for d in range(90):
        if d % 7 < 5:
            pass  # weekday
    timeline_svg += f'<line x1="30" y1="10" x2="30" y2="200" stroke="#334155" stroke-width="1"/>'
    timeline_svg += f'<line x1="30" y1="200" x2="550" y2="200" stroke="#334155" stroke-width="1"/>'

    def day_x(d): return 30 + d * 5.7

    for d in e_stops:
        timeline_svg += f'<circle cx="{day_x(d):.1f}" cy="40" r="7" fill="#C74634"/>'
    for d in soft_limits:
        timeline_svg += f'<circle cx="{day_x(d):.1f}" cy="90" r="5" fill="#f59e0b"/>'
    for d in near_miss:
        timeline_svg += f'<circle cx="{day_x(d):.1f}" cy="135" r="4" fill="#38bdf8"/>'
    for d in contact_force:
        timeline_svg += f'<circle cx="{day_x(d):.1f}" cy="175" r="3" fill="#8b5cf6"/>'

    # labels
    for label, y, color in [("E-Stop", 40, "#C74634"), ("Soft Limit", 90, "#f59e0b"), ("Near Miss", 135, "#38bdf8"), ("Contact Force", 175, "#8b5cf6")]:
        timeline_svg += f'<text x="26" y="{y+4}" fill="{color}" font-size="9" text-anchor="end">{label}</text>'
    for d in [0, 15, 30, 45, 60, 75, 89]:
        timeline_svg += f'<text x="{day_x(d):.1f}" y="212" fill="#64748b" font-size="9" text-anchor="middle">d{d}</text>'

    # incident rate trend (per 1k episodes)
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun"]
    rates = [4.2, 3.8, 3.1, 2.7, 2.1, 1.8]
    trend_pts = " ".join(f"{40+i*76:.1f},{130-rates[i]/5*110:.1f}" for i in range(len(months)))
    trend_svg = f'<polyline points="{trend_pts}" fill="none" stroke="#22c55e" stroke-width="2.5"/>'
    for i, (m, r) in enumerate(zip(months, rates)):
        x = 40 + i*76
        y = 130 - r/5*110
        trend_svg += f'<circle cx="{x}" cy="{y:.1f}" r="4" fill="#22c55e"/>'
        trend_svg += f'<text x="{x}" y="144" fill="#64748b" font-size="10" text-anchor="middle">{m}</text>'
        trend_svg += f'<text x="{x}" y="{y-6:.1f}" fill="#22c55e" font-size="9" text-anchor="middle">{r}</text>'

    return f"""<!DOCTYPE html>
<html>
<head><title>Safety Incident Dashboard</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',sans-serif}}
.hdr{{background:#1e293b;padding:16px 24px;border-bottom:2px solid #C74634;display:flex;align-items:center;gap:12px}}
.hdr h1{{margin:0;font-size:20px;color:#f1f5f9}}
.badge{{background:#C74634;color:#fff;padding:3px 10px;border-radius:12px;font-size:11px;font-weight:700}}
.grid{{display:grid;grid-template-columns:3fr 2fr;gap:16px;padding:20px}}
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
  <h1>Safety Incident Dashboard — 90-Day Overview</h1>
</div>
<div class="metrics">
  <div class="m"><div class="mv">0</div><div class="ml">Hard Collisions (30d)</div><div class="delta">✓ zero hard events</div></div>
  <div class="m"><div class="mv">4</div><div class="ml">E-Stops (90d)</div><div class="delta">all resolved</div></div>
  <div class="m"><div class="mv">99.2%</div><div class="ml">Safety Compliance</div></div>
  <div class="m"><div class="mv">1.8</div><div class="ml">Incident Rate/1k eps</div><div class="delta">↓ from 4.2 in Jan</div></div>
</div>
<div class="grid">
  <div class="card">
    <h3>Incident Timeline (90 days, by severity)</h3>
    <svg viewBox="0 0 560 220" width="100%">
      {timeline_svg}
    </svg>
  </div>
  <div class="card">
    <h3>Incident Rate Trend (per 1k episodes)</h3>
    <svg viewBox="0 0 500 160" width="100%">
      <line x1="30" y1="10" x2="30" y2="138" stroke="#334155" stroke-width="1"/>
      <line x1="30" y1="138" x2="490" y2="138" stroke="#334155" stroke-width="1"/>
      <line x1="30" y1="{130-2.0/5*110:.1f}" x2="490" y2="{130-2.0/5*110:.1f}" stroke="#f59e0b" stroke-width="1" stroke-dasharray="4,3"/>
      <text x="492" y="{130-2.0/5*110+4:.1f}" fill="#f59e0b" font-size="9">target 2.0</text>
      {trend_svg}
    </svg>
  </div>
</div>
</body>
</html>"""

if USE_FASTAPI:
    app = FastAPI(title="Safety Incident Dashboard")
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
