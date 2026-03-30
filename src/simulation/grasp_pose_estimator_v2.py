"""Grasp Pose Estimator V2 — FastAPI port 8816"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8816

def build_html():
    # Generate grasp quality scores and pose confidence over time
    random.seed(42)
    n = 40
    timestamps = list(range(n))
    grasp_quality = [0.55 + 0.3 * math.sin(i * 0.4) + random.uniform(-0.05, 0.05) for i in range(n)]
    pose_conf = [0.7 + 0.2 * math.cos(i * 0.3 + 0.5) + random.uniform(-0.04, 0.04) for i in range(n)]

    # SVG line chart — dual series
    w, h = 520, 160
    pad = 30
    chart_w = w - 2 * pad
    chart_h = h - 2 * pad

    def to_svg_pts(series, mn=0.0, mx=1.0):
        pts = []
        for i, v in enumerate(series):
            x = pad + i * chart_w / (len(series) - 1)
            y = pad + chart_h - (v - mn) / (mx - mn) * chart_h
            pts.append(f"{x:.1f},{y:.1f}")
        return " ".join(pts)

    gq_pts = to_svg_pts(grasp_quality)
    pc_pts = to_svg_pts(pose_conf)

    # Orientation heatmap: 6x6 grid of grasp approach angles
    heatmap_cells = ""
    for row in range(6):
        for col in range(6):
            angle = (row * 6 + col) * (180 / 35)
            intensity = 0.4 + 0.6 * abs(math.sin(math.radians(angle)))
            r = int(30 + 170 * (1 - intensity))
            g = int(80 + 100 * intensity)
            b = int(200 * intensity)
            cx = 20 + col * 38
            cy = 20 + row * 28
            heatmap_cells += f'<rect x="{cx}" y="{cy}" width="34" height="24" rx="3" fill="rgb({r},{g},{b})" opacity="0.85"/>'
            heatmap_cells += f'<text x="{cx+17}" y="{cy+16}" text-anchor="middle" font-size="9" fill="#e2e8f0">{angle:.0f}°</text>'

    # Recent grasp attempts table data
    attempts = []
    for i in range(8):
        q = round(random.uniform(0.62, 0.97), 3)
        roll = round(random.uniform(-15, 15), 1)
        pitch = round(random.uniform(-10, 10), 1)
        yaw = round(random.uniform(0, 360), 1)
        status = "SUCCESS" if q > 0.75 else "RETRY"
        color = "#4ade80" if status == "SUCCESS" else "#fb923c"
        attempts.append(f'<tr><td>#{1000+i}</td><td>{q}</td><td>{roll}°</td><td>{pitch}°</td><td>{yaw}°</td><td style="color:{color}">{status}</td></tr>')
    table_rows = "".join(attempts)

    avg_q = round(sum(grasp_quality) / len(grasp_quality), 4)
    avg_c = round(sum(pose_conf) / len(pose_conf), 4)
    peak_q = round(max(grasp_quality), 4)

    return f"""<!DOCTYPE html><html><head><title>Grasp Pose Estimator V2</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui;padding:20px}}
h1{{color:#C74634;margin:0 0 4px 0}}h2{{color:#38bdf8;font-size:1rem;margin:12px 0 8px 0}}
.card{{background:#1e293b;padding:20px;margin:12px 0;border-radius:8px;border:1px solid #334155}}
.grid{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px}}
.stat{{background:#0f172a;padding:14px;border-radius:6px;text-align:center}}
.stat .val{{font-size:1.8rem;font-weight:bold;color:#38bdf8}}
.stat .lbl{{font-size:0.75rem;color:#94a3b8;margin-top:4px}}
table{{width:100%;border-collapse:collapse;font-size:0.82rem}}
th{{background:#0f172a;padding:8px;text-align:left;color:#94a3b8;border-bottom:1px solid #334155}}
td{{padding:7px 8px;border-bottom:1px solid #1e293b}}
.badge{{background:#1e3a5f;color:#38bdf8;padding:2px 8px;border-radius:12px;font-size:0.75rem}}
.legend{{display:flex;gap:16px;font-size:0.75rem;margin-bottom:6px}}
.dot{{width:10px;height:10px;border-radius:50%;display:inline-block;margin-right:4px}}
</style></head>
<body>
<h1>Grasp Pose Estimator V2</h1>
<p style="color:#94a3b8;font-size:0.85rem;margin:0 0 16px 0">Real-time 6-DOF grasp pose estimation with deep feature fusion &nbsp;<span class="badge">Port {PORT}</span></p>

<div class="grid">
  <div class="stat"><div class="val">{avg_q}</div><div class="lbl">Avg Grasp Quality</div></div>
  <div class="stat"><div class="val">{avg_c}</div><div class="lbl">Avg Pose Confidence</div></div>
  <div class="stat"><div class="val">{peak_q}</div><div class="lbl">Peak Quality Score</div></div>
</div>

<div class="card">
  <h2>Grasp Quality &amp; Pose Confidence (last {n} frames)</h2>
  <div class="legend">
    <span><span class="dot" style="background:#38bdf8"></span>Grasp Quality</span>
    <span><span class="dot" style="background:#f472b6"></span>Pose Confidence</span>
  </div>
  <svg width="{w}" height="{h}" style="background:#0f172a;border-radius:6px;display:block">
    <polyline points="{gq_pts}" fill="none" stroke="#38bdf8" stroke-width="2"/>
    <polyline points="{pc_pts}" fill="none" stroke="#f472b6" stroke-width="2" stroke-dasharray="4,2"/>
    <line x1="{pad}" y1="{pad}" x2="{pad}" y2="{pad+chart_h}" stroke="#334155" stroke-width="1"/>
    <line x1="{pad}" y1="{pad+chart_h}" x2="{pad+chart_w}" y2="{pad+chart_h}" stroke="#334155" stroke-width="1"/>
    <text x="{pad-5}" y="{pad+5}" text-anchor="end" font-size="9" fill="#64748b">1.0</text>
    <text x="{pad-5}" y="{pad+chart_h//2+4}" text-anchor="end" font-size="9" fill="#64748b">0.5</text>
    <text x="{pad-5}" y="{pad+chart_h}" text-anchor="end" font-size="9" fill="#64748b">0.0</text>
  </svg>
</div>

<div class="card">
  <h2>Approach Angle Heatmap (36 orientations)</h2>
  <svg width="248" height="188" style="background:#0f172a;border-radius:6px;display:block">
    {heatmap_cells}
  </svg>
  <p style="color:#64748b;font-size:0.75rem;margin:6px 0 0 0">Color intensity = grasp success likelihood |sin(θ)| per approach angle</p>
</div>

<div class="card">
  <h2>Recent Grasp Attempts</h2>
  <table>
    <tr><th>ID</th><th>Quality</th><th>Roll</th><th>Pitch</th><th>Yaw</th><th>Status</th></tr>
    {table_rows}
  </table>
</div>

</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Grasp Pose Estimator V2")
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
