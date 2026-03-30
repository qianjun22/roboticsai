"""Tactile Feedback Analyzer — FastAPI port 8456"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8456

def build_html():
    random.seed(23)
    # 6-sensor tactile array heatmap (2x3 grid)
    sensor_labels = ["T_left_prox", "T_right_prox", "T_left_dist", "T_right_dist", "Palm_left", "Palm_right"]
    # pressure during grasp phase
    pressures = [0.82, 0.79, 0.91, 0.88, 0.54, 0.51]
    heat_svg = ""
    for i, (label, p) in enumerate(zip(sensor_labels, pressures)):
        row = i // 3
        col = i % 3
        x = 30 + col * 110
        y = 20 + row * 80
        if p >= 0.75:
            color = "#22c55e"
        elif p >= 0.50:
            color = "#f59e0b"
        else:
            color = "#C74634"
        heat_svg += f'<rect x="{x}" y="{y}" width="96" height="68" fill="{color}" opacity="{0.3+p*0.65:.2f}" rx="6"/>'
        heat_svg += f'<text x="{x+48}" y="{y+30}" fill="#e2e8f0" font-size="18" font-weight="bold" text-anchor="middle">{int(p*100)}</text>'
        heat_svg += f'<text x="{x+48}" y="{y+48}" fill="#94a3b8" font-size="9" text-anchor="middle">{label}</text>'

    # force timeline SVG (847 steps, slip events)
    steps = list(range(0, 848, 8))
    forces = []
    slip_events = []
    for i, s in enumerate(steps):
        if s < 200:  # reach
            f = 0.5 + random.gauss(0, 0.3)
        elif s < 280:  # contact/grasp
            f = 8.0 + random.gauss(0, 1.5)
        elif s < 600:  # lift and hold
            f = 14.3 + random.gauss(0, 0.8)
        else:  # place
            f = 6.0 + random.gauss(0, 1.2)
        f = max(0, f)
        forces.append(f)
        if 280 <= s <= 350 and random.random() < 0.08:
            slip_events.append(i)

    f_pts = " ".join(f"{35+i*2.6:.1f},{160-forces[i]/18*120:.1f}" for i in range(len(steps)))
    force_svg = f'<polyline points="{f_pts}" fill="none" stroke="#38bdf8" stroke-width="1.5"/>'
    for idx in slip_events:
        fx = 35 + idx * 2.6
        fy = 160 - forces[idx] / 18 * 120
        force_svg += f'<circle cx="{fx:.1f}" cy="{fy:.1f}" r="4" fill="#C74634"/>'
    # phase bands
    force_svg += f'<rect x="35" y="10" width="68" height="150" fill="#334155" opacity="0.2" rx="2"/>'
    force_svg += f'<text x="70" y="8" fill="#64748b" font-size="8" text-anchor="middle">reach</text>'
    force_svg += f'<rect x="103" y="10" width="27" height="150" fill="#C74634" opacity="0.1" rx="2"/>'
    force_svg += f'<text x="117" y="8" fill="#C74634" font-size="8" text-anchor="middle">contact</text>'
    force_svg += f'<rect x="130" y="10" width="104" height="150" fill="#22c55e" opacity="0.07" rx="2"/>'
    force_svg += f'<text x="182" y="8" fill="#22c55e" font-size="8" text-anchor="middle">lift+hold (14.3N avg)</text>'

    return f"""<!DOCTYPE html>
<html>
<head><title>Tactile Feedback Analyzer</title>
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
  <h1>Tactile Feedback Analyzer — Grasp Force Profile</h1>
</div>
<div class="metrics">
  <div class="m"><div class="mv">14.3N</div><div class="ml">Avg Grasp Force</div></div>
  <div class="m"><div class="mv">94%</div><div class="ml">Slip Detection Acc</div><div class="delta">8ms latency</div></div>
  <div class="m"><div class="mv">+4pp</div><div class="ml">SR with Tactile</div><div class="delta">fragile objects</div></div>
  <div class="m"><div class="mv">0.71</div><div class="ml">Sim Tactile Fidelity</div></div>
</div>
<div class="grid">
  <div class="card">
    <h3>Fingertip Pressure Array (grasp phase)</h3>
    <svg viewBox="0 0 380 190" width="100%">
      {heat_svg}
    </svg>
    <p style="font-size:11px;color:#94a3b8;margin:6px 0 0">Distal sensors highest pressure (0.91/0.88); palm sensors moderate (0.54/0.51). Asymmetry normal for cube grasp.</p>
  </div>
  <div class="card">
    <h3>Force Timeline (847 steps, &#9679; = slip event)</h3>
    <svg viewBox="0 0 360 175" width="100%">
      <line x1="32" y1="10" x2="32" y2="163" stroke="#334155" stroke-width="1"/>
      <line x1="32" y1="163" x2="355" y2="163" stroke="#334155" stroke-width="1"/>
      {force_svg}
      <text x="18" y="163" fill="#64748b" font-size="8">0N</text>
      <text x="18" y="43" fill="#64748b" font-size="8">18N</text>
    </svg>
  </div>
</div>
</body>
</html>"""

if USE_FASTAPI:
    app = FastAPI(title="Tactile Feedback Analyzer")
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
