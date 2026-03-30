"""Multi-Arm Coordination Tracker — FastAPI port 8700"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8700

def build_html():
    random.seed(42)
    # Generate joint angle trajectories for 4 arms over 60 time steps
    steps = 60
    arms = ["Arm-A", "Arm-B", "Arm-C", "Arm-D"]
    colors = ["#C74634", "#38bdf8", "#a3e635", "#f59e0b"]

    # Sync score: how closely all arms follow a reference sinusoid
    sync_scores = [round(85 + 10 * math.sin(i * 0.3) + random.uniform(-3, 3), 2) for i in range(20)]
    avg_sync = round(sum(sync_scores) / len(sync_scores), 2)

    # Build SVG polyline for each arm's joint angle (shoulder pitch)
    svg_w, svg_h = 560, 160
    polylines = ""
    for idx, (arm, color) in enumerate(zip(arms, colors)):
        phase = idx * math.pi / 4
        pts = []
        for t in range(steps):
            x = 10 + t * (svg_w - 20) / (steps - 1)
            angle = math.sin(t * 0.2 + phase) * 60 + random.uniform(-5, 5)
            y = svg_h / 2 - angle * (svg_h / 2 - 10) / 65
            pts.append(f"{x:.1f},{y:.1f}")
        polylines += f'<polyline points="{",".join(pts)}" fill="none" stroke="{color}" stroke-width="2" opacity="0.9"/>\n'

    # Collision proximity heatmap row (arm pairs)
    pairs = [("A-B", 0.12), ("A-C", 0.34), ("A-D", 0.08), ("B-C", 0.21), ("B-D", 0.45), ("C-D", 0.17)]
    heat_cells = ""
    for i, (pair, risk) in enumerate(pairs):
        r = int(200 * risk)
        g = int(200 * (1 - risk))
        heat_cells += (
            f'<rect x="{10 + i*90}" y="10" width="80" height="50" rx="6" '
            f'fill="rgb({r},{g},60)" opacity="0.85"/>'
            f'<text x="{50 + i*90}" y="32" text-anchor="middle" fill="#fff" font-size="12">{pair}</text>'
            f'<text x="{50 + i*90}" y="50" text-anchor="middle" fill="#fff" font-size="11">{risk:.0%}</text>'
        )

    # Sync score sparkline
    spark_pts = []
    for i, s in enumerate(sync_scores):
        x = 10 + i * (540 / (len(sync_scores) - 1))
        y = 60 - (s - 75) * (50 / 20)
        spark_pts.append(f"{x:.1f},{y:.1f}")
    spark_svg = f'<polyline points="{",".join(spark_pts)}" fill="none" stroke="#38bdf8" stroke-width="2.5"/>'

    # Task completion rates per arm
    completions = {arm: round(random.uniform(88, 99), 1) for arm in arms}
    bars = ""
    for i, (arm, pct) in enumerate(completions.items()):
        bw = pct * 4.8
        bars += (
            f'<rect x="80" y="{10 + i*32}" width="{bw:.1f}" height="22" rx="4" fill="{colors[i]}" opacity="0.85"/>'
            f'<text x="72" y="{26 + i*32}" text-anchor="end" fill="#94a3b8" font-size="12">{arm}</text>'
            f'<text x="{86 + bw:.1f}" y="{26 + i*32}" fill="#e2e8f0" font-size="12">{pct}%</text>'
        )

    return f"""<!DOCTYPE html><html><head><title>Multi-Arm Coordination Tracker</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui;padding:20px}}
h1{{color:#C74634;margin-bottom:4px}}h2{{color:#38bdf8;margin:0 0 12px}}
.card{{background:#1e293b;padding:20px;margin:10px 0;border-radius:8px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:10px}}
.badge{{display:inline-block;background:#C74634;color:#fff;border-radius:4px;padding:2px 10px;font-size:13px;margin-right:8px}}
.stat{{font-size:2rem;font-weight:700;color:#38bdf8}}
.sub{{font-size:0.85rem;color:#64748b}}
</style></head>
<body>
<h1>Multi-Arm Coordination Tracker</h1>
<p class="sub">Port {PORT} &nbsp;|&nbsp; 4-arm robotic cell &nbsp;|&nbsp; Real-time sync monitoring</p>

<div class="grid">
  <div class="card">
    <h2>Fleet Sync Score</h2>
    <div class="stat">{avg_sync}%</div>
    <p class="sub">Rolling 20-cycle average — target &ge;90%</p>
    <svg width="560" height="70" viewBox="0 0 560 70">
      <line x1="10" y1="10" x2="10" y2="65" stroke="#334155" stroke-width="1"/>
      <line x1="10" y1="65" x2="550" y2="65" stroke="#334155" stroke-width="1"/>
      {spark_svg}
    </svg>
  </div>
  <div class="card">
    <h2>Task Completion Rate</h2>
    <svg width="560" height="140">
      {bars}
    </svg>
  </div>
</div>

<div class="card">
  <h2>Joint Angle Trajectories (Shoulder Pitch, deg)</h2>
  {''.join(f'<span class="badge" style="background:{c}">{a}</span>' for a, c in zip(arms, colors))}
  <svg width="560" height="{svg_h}" viewBox="0 0 {svg_w} {svg_h}" style="margin-top:10px">
    <line x1="10" y1="{svg_h//2}" x2="{svg_w-10}" y2="{svg_h//2}" stroke="#334155" stroke-width="1" stroke-dasharray="4"/>
    {polylines}
  </svg>
</div>

<div class="card">
  <h2>Collision Proximity Risk (Arm Pairs)</h2>
  <svg width="560" height="70">
    {heat_cells}
  </svg>
  <p class="sub">Color: red = high risk, green = low risk. Threshold alert at &gt;40%.</p>
</div>

</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Multi-Arm Coordination Tracker")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return build_html()

    @app.get("/health")
    def health():
        return {"status": "ok", "port": PORT}

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
