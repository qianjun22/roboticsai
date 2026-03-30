"""Grasp Force Controller — FastAPI port 8762"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8762

def build_html():
    # Simulate grasp force readings over 60 time steps
    steps = 60
    t = [i for i in range(steps)]
    # Normal force: rising grip with damped oscillation
    normal_force = [round(8.0 * (1 - math.exp(-i / 12.0)) + 0.4 * math.sin(i * 0.7) * math.exp(-i / 20.0) + random.uniform(-0.15, 0.15), 3) for i in t]
    # Tangential (shear) force: smaller, noisy
    shear_force = [round(1.2 * math.sin(i * 0.3 + 0.5) + random.uniform(-0.1, 0.1), 3) for i in t]
    # Slip ratio: ratio of shear to normal (should stay below friction cone limit ~0.35)
    slip_ratio = [round(abs(shear_force[i]) / max(normal_force[i], 0.01), 4) for i in t]

    # SVG polyline for normal force (scale: 0-12N → 0-120px, x: 0-600px)
    svg_w, svg_h = 600, 140
    def to_pts(values, vmin, vmax):
        pts = []
        for idx, v in enumerate(values):
            x = int(idx * svg_w / (steps - 1))
            y = svg_h - int((v - vmin) / (vmax - vmin + 1e-9) * svg_h)
            pts.append(f"{x},{y}")
        return " ".join(pts)

    nf_pts = to_pts(normal_force, 0, 12)
    sf_pts = to_pts(shear_force, -2, 2)
    sr_pts = to_pts(slip_ratio, 0, 0.6)

    # Latest values
    latest_nf = normal_force[-1]
    latest_sf = shear_force[-1]
    latest_sr = slip_ratio[-1]
    slip_status = "SAFE" if latest_sr < 0.35 else "SLIP RISK"
    slip_color = "#22c55e" if latest_sr < 0.35 else "#ef4444"

    # Finger positions (3 fingers, angles in degrees)
    finger_angles = [round(30 + 60 * (1 - math.exp(-steps / 12.0)) + random.uniform(-1, 1), 1) for _ in range(3)]
    finger_labels = ["Finger A", "Finger B", "Finger C"]

    finger_rows = "".join(
        f"<tr><td>{finger_labels[i]}</td><td>{finger_angles[i]}°</td>"
        f"<td>{round(normal_force[-1] * (0.32 + random.uniform(-0.02, 0.02)), 2)} N</td></tr>"
        for i in range(3)
    )

    return f"""<!DOCTYPE html><html><head><title>Grasp Force Controller</title>
<meta charset='utf-8'>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui,sans-serif}}
h1{{color:#C74634;padding:20px 20px 0;margin:0}}h2{{color:#38bdf8;margin-top:0}}
.card{{background:#1e293b;padding:20px;margin:10px;border-radius:8px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:0}}
.badge{{display:inline-block;padding:4px 12px;border-radius:4px;font-weight:bold;font-size:0.95em}}
table{{width:100%;border-collapse:collapse}}th,td{{padding:6px 10px;border-bottom:1px solid #334155;text-align:left}}
th{{color:#94a3b8;font-size:0.85em}}
.metric{{font-size:2em;font-weight:bold;color:#f0f9ff}}
.label{{color:#94a3b8;font-size:0.8em;margin-bottom:4px}}
</style></head>
<body>
<h1>Grasp Force Controller</h1>
<p style='color:#94a3b8;padding:0 20px;margin:4px 0 0'>Port {PORT} &mdash; Real-time tactile feedback &amp; slip detection</p>

<div class='grid'>
<div class='card'>
  <h2>Live Metrics</h2>
  <div style='display:flex;gap:24px;flex-wrap:wrap'>
    <div><div class='label'>Normal Force</div><div class='metric'>{latest_nf:.2f} N</div></div>
    <div><div class='label'>Shear Force</div><div class='metric'>{latest_sf:.2f} N</div></div>
    <div><div class='label'>Slip Ratio</div><div class='metric'>{latest_sr:.3f}</div></div>
    <div><div class='label'>Slip Status</div><div class='badge' style='background:{slip_color};color:#fff;margin-top:8px'>{slip_status}</div></div>
  </div>
</div>
<div class='card'>
  <h2>Finger Joint Positions</h2>
  <table><thead><tr><th>Finger</th><th>Angle</th><th>Contact Force</th></tr></thead>
  <tbody>{finger_rows}</tbody></table>
</div>
</div>

<div class='card'>
  <h2>Normal Force Over Time (0–12 N)</h2>
  <svg width='{svg_w}' height='{svg_h}' style='display:block;background:#0f172a;border-radius:4px'>
    <polyline points='{nf_pts}' fill='none' stroke='#38bdf8' stroke-width='2'/>
    <line x1='0' y1='{int(svg_h - 10/12*svg_h)}' x2='{svg_w}' y2='{int(svg_h - 10/12*svg_h)}' stroke='#C74634' stroke-dasharray='4,4' stroke-width='1'/>
    <text x='4' y='{int(svg_h - 10/12*svg_h) - 4}' fill='#C74634' font-size='11'>Max grip 10N</text>
  </svg>
</div>

<div class='card'>
  <h2>Shear Force (±2 N)</h2>
  <svg width='{svg_w}' height='{svg_h}' style='display:block;background:#0f172a;border-radius:4px'>
    <line x1='0' y1='{svg_h//2}' x2='{svg_w}' y2='{svg_h//2}' stroke='#475569' stroke-width='1'/>
    <polyline points='{sf_pts}' fill='none' stroke='#a78bfa' stroke-width='2'/>
  </svg>
</div>

<div class='card'>
  <h2>Slip Ratio (friction cone limit = 0.35)</h2>
  <svg width='{svg_w}' height='{svg_h}' style='display:block;background:#0f172a;border-radius:4px'>
    <line x1='0' y1='{int(svg_h - 0.35/0.6*svg_h)}' x2='{svg_w}' y2='{int(svg_h - 0.35/0.6*svg_h)}' stroke='#f59e0b' stroke-dasharray='6,3' stroke-width='1.5'/>
    <text x='4' y='{int(svg_h - 0.35/0.6*svg_h) - 4}' fill='#f59e0b' font-size='11'>Slip limit 0.35</text>
    <polyline points='{sr_pts}' fill='none' stroke='#22c55e' stroke-width='2'/>
  </svg>
</div>

</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Grasp Force Controller")
    @app.get("/", response_class=HTMLResponse)
    def index(): return build_html()
    @app.get("/health")
    def health(): return {"status": "ok", "port": PORT}
    @app.get("/force")
    def force():
        nf = round(8.0 * (1 - math.exp(-30 / 12.0)) + random.uniform(-0.2, 0.2), 3)
        sf = round(1.2 * math.sin(30 * 0.3) + random.uniform(-0.1, 0.1), 3)
        return {"normal_force_N": nf, "shear_force_N": sf, "slip_ratio": round(abs(sf) / max(nf, 0.01), 4)}

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
