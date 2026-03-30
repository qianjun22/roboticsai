"""Multi-Camera Fusion Evaluator — FastAPI port 8812"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8812

def build_html():
    random.seed(42)
    num_cameras = 6
    camera_names = ["Front-RGB", "Left-RGB", "Right-RGB", "Wrist-RGB", "Overhead-RGBD", "Back-RGB"]
    # Simulate latency (ms), overlap scores, and fusion confidence per camera
    latencies = [random.uniform(8, 35) for _ in range(num_cameras)]
    overlaps = [random.uniform(0.55, 0.98) for _ in range(num_cameras)]
    confidences = [random.uniform(0.70, 0.99) for _ in range(num_cameras)]

    # Radar chart data (hexagon): map each camera to an angle
    cx, cy, r = 180, 160, 110
    radar_points = []
    for i, conf in enumerate(confidences):
        angle = math.radians(i * 60 - 90)
        rx = cx + conf * r * math.cos(angle)
        ry = cy + conf * r * math.sin(angle)
        radar_points.append((rx, ry))
    radar_poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in radar_points)

    # Hexagon grid lines (25%, 50%, 75%, 100%)
    hex_grids = []
    for scale in [0.25, 0.5, 0.75, 1.0]:
        pts = []
        for i in range(6):
            angle = math.radians(i * 60 - 90)
            pts.append((cx + scale * r * math.cos(angle), cy + scale * r * math.sin(angle)))
        pts.append(pts[0])
        hex_grids.append(" ".join(f"{x:.1f},{y:.1f}" for x, y in pts))

    radar_spokes = ""
    for i in range(6):
        angle = math.radians(i * 60 - 90)
        ex = cx + r * math.cos(angle)
        ey = cy + r * math.sin(angle)
        radar_spokes += f'<line x1="{cx}" y1="{cy}" x2="{ex:.1f}" y2="{ey:.1f}" stroke="#334155" stroke-width="1"/>'
        lx = cx + (r + 18) * math.cos(angle)
        ly = cy + (r + 18) * math.sin(angle)
        radar_spokes += f'<text x="{lx:.1f}" y="{ly:.1f}" fill="#94a3b8" font-size="9" text-anchor="middle" dominant-baseline="middle">{camera_names[i]}</text>'

    hex_grid_svg = ""
    for pts_str in hex_grids:
        hex_grid_svg += f'<polyline points="{pts_str}" fill="none" stroke="#1e3a5f" stroke-width="1"/>'

    # Latency bar chart (horizontal)
    bar_svg = ""
    max_lat = max(latencies)
    bar_w = 200
    for i, (name, lat) in enumerate(zip(camera_names, latencies)):
        bw = int(lat / max_lat * bar_w)
        color = "#C74634" if lat > 25 else "#38bdf8"
        bar_svg += f'<rect x="100" y="{i*30+5}" width="{bw}" height="18" rx="3" fill="{color}" opacity="0.85"/>'
        bar_svg += f'<text x="95" y="{i*30+17}" fill="#94a3b8" font-size="10" text-anchor="end">{name}</text>'
        bar_svg += f'<text x="{100+bw+4}" y="{i*30+17}" fill="#e2e8f0" font-size="10">{lat:.1f}ms</text>'

    # Time-series fusion score (last 40 frames)
    random.seed(99)
    fusion_scores = [0.82 + 0.12 * math.sin(t * 0.4) + random.uniform(-0.04, 0.04) for t in range(40)]
    ts_w, ts_h = 360, 80
    ts_pts = []
    for i, v in enumerate(fusion_scores):
        x = i * (ts_w / 39)
        y = ts_h - (v - 0.7) / 0.3 * ts_h
        ts_pts.append((x, max(2, min(ts_h - 2, y))))
    ts_poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in ts_pts)
    # Fill area under curve
    ts_fill = f"{ts_poly} {ts_w:.1f},{ts_h} 0,{ts_h}"

    avg_fusion = sum(fusion_scores) / len(fusion_scores)
    avg_latency = sum(latencies) / len(latencies)
    avg_overlap = sum(overlaps) / len(overlaps)

    return f"""<!DOCTYPE html><html><head><title>Multi-Camera Fusion Evaluator</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui,sans-serif}}
h1{{color:#C74634;padding:20px 20px 4px;margin:0;font-size:1.5rem}}
.subtitle{{color:#64748b;padding:0 20px 16px;font-size:0.85rem}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:0}}
.card{{background:#1e293b;padding:20px;margin:10px;border-radius:8px;border:1px solid #334155}}
h2{{color:#38bdf8;margin:0 0 12px;font-size:1rem}}
.kpi-row{{display:flex;gap:12px;margin-bottom:8px}}
.kpi{{background:#0f172a;border-radius:6px;padding:12px 16px;flex:1;text-align:center}}
.kpi .val{{font-size:1.6rem;font-weight:700;color:#38bdf8}}
.kpi .lbl{{font-size:0.72rem;color:#64748b;margin-top:2px}}
.tag{{display:inline-block;padding:2px 8px;border-radius:4px;font-size:0.75rem;font-weight:600}}
.ok{{background:#14532d;color:#4ade80}}.warn{{background:#7c2d12;color:#fb923c}}
</style></head>
<body>
<h1>Multi-Camera Fusion Evaluator</h1>
<div class="subtitle">Port {PORT} &nbsp;|&nbsp; {num_cameras}-camera robot perception stack &nbsp;|&nbsp; Real-time fusion quality monitoring</div>

<div class="kpi-row" style="padding:0 10px">
  <div class="kpi"><div class="val">{avg_fusion:.3f}</div><div class="lbl">Avg Fusion Score</div></div>
  <div class="kpi"><div class="val">{avg_latency:.1f}ms</div><div class="lbl">Avg Camera Latency</div></div>
  <div class="kpi"><div class="val">{avg_overlap:.2f}</div><div class="lbl">Avg FOV Overlap</div></div>
  <div class="kpi"><div class="val">{num_cameras}</div><div class="lbl">Active Cameras</div></div>
</div>

<div class="grid">
  <div class="card">
    <h2>Confidence Radar (per camera)</h2>
    <svg width="360" height="320" viewBox="0 0 360 320">
      {hex_grid_svg}
      {radar_spokes}
      <polygon points="{radar_poly}" fill="#38bdf8" fill-opacity="0.18" stroke="#38bdf8" stroke-width="2"/>
      {''.join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="#38bdf8"/>' for x, y in radar_points)}
      <text x="{cx}" y="290" fill="#475569" font-size="10" text-anchor="middle">Confidence score 0→1 per axis</text>
    </svg>
  </div>

  <div class="card">
    <h2>Camera Latency (ms)</h2>
    <svg width="360" height="210" viewBox="0 0 360 210">
      {bar_svg}
      <line x1="100" y1="0" x2="100" y2="195" stroke="#334155" stroke-width="1"/>
      <text x="200" y="200" fill="#475569" font-size="9" text-anchor="middle">Latency in ms — red &gt; 25ms threshold</text>
    </svg>
  </div>

  <div class="card" style="grid-column:1/-1">
    <h2>Fusion Score — Last 40 Frames</h2>
    <svg width="100%" height="110" viewBox="0 0 360 90" preserveAspectRatio="none">
      <defs><linearGradient id="tsg" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="#38bdf8" stop-opacity="0.35"/>
        <stop offset="100%" stop-color="#38bdf8" stop-opacity="0.02"/>
      </linearGradient></defs>
      <polygon points="{ts_fill}" fill="url(#tsg)"/>
      <polyline points="{ts_poly}" fill="none" stroke="#38bdf8" stroke-width="2"/>
      <line x1="0" y1="{ts_h - (0.82 - 0.7)/0.3*ts_h:.1f}" x2="{ts_w}" y2="{ts_h - (0.82 - 0.7)/0.3*ts_h:.1f}" stroke="#C74634" stroke-width="1" stroke-dasharray="4,3"/>
      <text x="{ts_w-2}" y="{ts_h - (0.82-0.7)/0.3*ts_h - 3:.1f}" fill="#C74634" font-size="8" text-anchor="end">target 0.82</text>
    </svg>
  </div>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Multi-Camera Fusion Evaluator")
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
