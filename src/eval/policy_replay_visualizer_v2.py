"""Policy Replay Visualizer V2 — FastAPI port 8834"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8834

# Deterministic trajectory data for SVG overlay
random.seed(42)
EPISODES = 1847
SUCCESS_RATE = 0.78
SPEEDUP = 12

def _build_trajectory_svg():
    """Generate SVG with color-coded trajectory overlays and success/failure heatmap."""
    w, h = 480, 320
    cells_x, cells_y = 12, 8
    cell_w = w / cells_x
    cell_h = h / cells_y

    # Heatmap cells
    rects = []
    random.seed(7)
    for gy in range(cells_y):
        for gx in range(cells_x):
            rate = max(0.0, min(1.0, random.gauss(SUCCESS_RATE, 0.18)))
            r = int(200 * (1 - rate))
            g = int(200 * rate)
            b = 40
            opacity = 0.55
            rects.append(
                f'<rect x="{gx*cell_w:.1f}" y="{gy*cell_h:.1f}" '
                f'width="{cell_w:.1f}" height="{cell_h:.1f}" '
                f'fill="rgb({r},{g},{b})" opacity="{opacity}"/>'
            )

    # Trajectory polylines (5 sample episodes)
    polylines = []
    colors = ["#38bdf8", "#4ade80", "#f59e0b", "#f87171", "#a78bfa"]
    random.seed(13)
    for i, color in enumerate(colors):
        pts = []
        x, y = random.uniform(20, 80), random.uniform(20, 80)
        for _ in range(18):
            x = max(5, min(w-5, x + random.gauss(0, 18)))
            y = max(5, min(h-5, y + random.gauss(0, 14)))
            pts.append(f"{x:.1f},{y:.1f}")
        success = random.random() < SUCCESS_RATE
        stroke_dash = "" if success else 'stroke-dasharray="6,3"'
        polylines.append(
            f'<polyline points="{" ".join(pts)}" fill="none" stroke="{color}" '
            f'stroke-width="1.8" opacity="0.85" {stroke_dash}/>'
        )
        # Start/end markers
        sx, sy = [float(v) for v in pts[0].split(",")]
        ex, ey = [float(v) for v in pts[-1].split(",")]
        polylines.append(f'<circle cx="{sx:.1f}" cy="{sy:.1f}" r="4" fill="{color}"/>')
        marker = "#4ade80" if success else "#f87171"
        polylines.append(f'<circle cx="{ex:.1f}" cy="{ey:.1f}" r="5" fill="{marker}" stroke="white" stroke-width="1"/>')

    svg_body = "\n".join(rects + polylines)
    return (
        f'<svg viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
        f'xmlns="http://www.w3.org/2000/svg" style="border-radius:6px;background:#0f172a;">'
        f'{svg_body}'
        f'<rect x="0" y="0" width="{w}" height="{h}" fill="none" stroke="#334155" stroke-width="1"/>'
        f'</svg>'
    )

def _build_timeline_svg():
    """Per-episode action sequence timeline (last 20 episodes)."""
    w, h = 480, 120
    eps = 20
    bar_h = 5
    gap = 1
    step_w = w / 60  # 60 time steps
    random.seed(99)
    bars = []
    action_colors = ["#38bdf8", "#f59e0b", "#a78bfa", "#4ade80", "#f87171"]
    for ep in range(eps):
        y_off = ep * (bar_h + gap)
        t = 0
        while t < 60:
            duration = random.randint(2, 8)
            color = random.choice(action_colors)
            bars.append(
                f'<rect x="{t*step_w:.1f}" y="{y_off:.1f}" '
                f'width="{min(duration, 60-t)*step_w:.1f}" height="{bar_h}" '
                f'fill="{color}" opacity="0.8"/>'
            )
            t += duration
    return (
        f'<svg viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
        f'xmlns="http://www.w3.org/2000/svg" style="border-radius:6px;background:#0f172a;">'
        + "\n".join(bars) +
        f'<rect x="0" y="0" width="{w}" height="{h}" fill="none" stroke="#334155" stroke-width="1"/>'
        f'</svg>'
    )

def build_html():
    traj_svg = _build_trajectory_svg()
    timeline_svg = _build_timeline_svg()
    success_pct = int(SUCCESS_RATE * 100)
    return f"""<!DOCTYPE html><html><head><title>Policy Replay Visualizer V2</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui;padding:20px}}
h1{{color:#C74634;margin-bottom:4px}}h2{{color:#38bdf8;margin:12px 0 8px}}
.card{{background:#1e293b;padding:20px;margin:10px 0;border-radius:8px}}
.metrics{{display:flex;gap:20px;flex-wrap:wrap;margin-bottom:16px}}
.metric{{background:#0f172a;padding:12px 18px;border-radius:6px;text-align:center;min-width:120px}}
.metric .val{{font-size:2rem;font-weight:700;color:#38bdf8}}
.metric .lbl{{font-size:0.78rem;color:#94a3b8;margin-top:4px}}
.legend{{display:flex;gap:14px;flex-wrap:wrap;margin-top:10px;font-size:0.8rem}}
.dot{{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:4px}}
</style></head>
<body>
<h1>Policy Replay Visualizer V2</h1>
<p style="color:#94a3b8;margin-top:0">Port {PORT} &nbsp;|&nbsp; Enhanced replay system with trajectory overlays, heatmaps &amp; action timelines</p>

<div class="card">
  <h2>Key Metrics</h2>
  <div class="metrics">
    <div class="metric"><div class="val">{EPISODES:,}</div><div class="lbl">Episodes Replayed</div></div>
    <div class="metric"><div class="val">{success_pct}%</div><div class="lbl">Success Zones Highlighted</div></div>
    <div class="metric"><div class="val">{SPEEDUP}×</div><div class="lbl">Speedup vs V1</div></div>
    <div class="metric"><div class="val">5</div><div class="lbl">Trajectory Overlays</div></div>
  </div>
</div>

<div class="card">
  <h2>Trajectory Overlay &amp; Success/Failure Heatmap</h2>
  <p style="color:#94a3b8;font-size:0.82rem">Color heatmap = local success rate (green=high, red=low). Lines = sampled episode paths. Solid end = success, dashed = failure.</p>
  {traj_svg}
  <div class="legend">
    <span><span class="dot" style="background:#38bdf8"></span>Episode 1</span>
    <span><span class="dot" style="background:#4ade80"></span>Episode 2</span>
    <span><span class="dot" style="background:#f59e0b"></span>Episode 3</span>
    <span><span class="dot" style="background:#f87171"></span>Episode 4</span>
    <span><span class="dot" style="background:#a78bfa"></span>Episode 5</span>
    <span><span class="dot" style="background:#4ade80"></span>Success end</span>
    <span><span class="dot" style="background:#f87171"></span>Failure end</span>
  </div>
</div>

<div class="card">
  <h2>Per-Episode Action Sequence Timeline (last 20 episodes)</h2>
  <p style="color:#94a3b8;font-size:0.82rem">Each row = one episode. Color segments = action primitives over 60 time steps.</p>
  {timeline_svg}
  <div class="legend">
    <span><span class="dot" style="background:#38bdf8"></span>Reach</span>
    <span><span class="dot" style="background:#f59e0b"></span>Grasp</span>
    <span><span class="dot" style="background:#a78bfa"></span>Lift</span>
    <span><span class="dot" style="background:#4ade80"></span>Place</span>
    <span><span class="dot" style="background:#f87171"></span>Recover</span>
  </div>
</div>

</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Policy Replay Visualizer V2")
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
