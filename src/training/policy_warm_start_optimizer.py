"""Policy Warm-Start Optimizer — FastAPI port 8810"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8810

def build_html():
    random.seed(42)
    # Simulate warm-start vs cold-start convergence curves
    steps = list(range(0, 500, 25))
    warm_loss = [0.85 * math.exp(-0.012 * s) + 0.04 + random.gauss(0, 0.005) for s in steps]
    cold_loss = [1.45 * math.exp(-0.007 * s) + 0.08 + random.gauss(0, 0.008) for s in steps]

    # SVG polyline data
    svg_w, svg_h = 560, 220
    def to_svg_pts(vals, min_v=0.0, max_v=1.5):
        pts = []
        for i, v in enumerate(vals):
            x = 40 + i * (svg_w - 60) / (len(vals) - 1)
            y = svg_h - 30 - (v - min_v) / (max_v - min_v) * (svg_h - 50)
            pts.append(f"{x:.1f},{y:.1f}")
        return " ".join(pts)

    warm_pts = to_svg_pts(warm_loss)
    cold_pts = to_svg_pts(cold_loss)

    # Gradient fill polygon for warm start area
    warm_area = warm_pts + f" {40 + (len(steps)-1)*(svg_w-60)/(len(steps)-1):.1f},{svg_h-30} 40,{svg_h-30}"

    # Per-task warm-start speedup bars
    tasks = ["PickPlace", "StackCube", "PourLiquid", "OpenDoor", "AssemblePeg"]
    speedups = [random.uniform(1.8, 3.4) for _ in tasks]
    bar_w = 72
    bar_spacing = 90

    bars_svg = ""
    for i, (task, sp) in enumerate(zip(tasks, speedups)):
        bx = 40 + i * bar_spacing
        bh = sp / 4.0 * 140
        by = 170 - bh
        hue = int(200 + i * 25)
        bars_svg += f'<rect x="{bx}" y="{by:.1f}" width="{bar_w}" height="{bh:.1f}" rx="4" fill="hsl({hue},70%,50%)" opacity="0.85"/>'
        bars_svg += f'<text x="{bx+bar_w/2:.1f}" y="{by-6:.1f}" text-anchor="middle" fill="#e2e8f0" font-size="12">{sp:.2f}x</text>'
        bars_svg += f'<text x="{bx+bar_w/2:.1f}" y="185" text-anchor="middle" fill="#94a3b8" font-size="10">{task}</text>'

    # Checkpoint reuse heatmap (5 source checkpoints x 5 target tasks)
    heat_data = [[random.uniform(0.3, 1.0) for _ in range(5)] for _ in range(5)]
    heat_svg = ""
    cell = 44
    for r in range(5):
        for c in range(5):
            v = heat_data[r][c]
            g = int(v * 180)
            b = int(v * 240)
            heat_svg += f'<rect x="{30+c*cell}" y="{20+r*cell}" width="{cell-2}" height="{cell-2}" rx="3" fill="rgb(0,{g},{b})" opacity="0.9"/>'
            heat_svg += f'<text x="{30+c*cell+cell//2-1}" y="{20+r*cell+cell//2+4}" text-anchor="middle" fill="white" font-size="10">{v:.2f}</text>'

    final_warm = warm_loss[-1]
    final_cold = cold_loss[-1]
    speedup_avg = sum(speedups) / len(speedups)

    return f"""<!DOCTYPE html><html><head><title>Policy Warm-Start Optimizer</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui,sans-serif}}
h1{{color:#C74634;padding:20px 24px 0;margin:0;font-size:1.6rem}}
.subtitle{{color:#64748b;padding:2px 24px 16px;font-size:0.9rem}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;padding:0 16px 16px}}
.card{{background:#1e293b;padding:20px;border-radius:10px;border:1px solid #334155}}
.card h2{{color:#38bdf8;margin:0 0 12px;font-size:1rem;text-transform:uppercase;letter-spacing:.05em}}
.stat-row{{display:flex;gap:24px;padding:0 16px 16px}}
.stat{{background:#1e293b;border-radius:8px;padding:14px 20px;flex:1;border:1px solid #334155}}
.stat .val{{font-size:2rem;font-weight:700;color:#22d3ee}}
.stat .lbl{{font-size:0.78rem;color:#64748b;margin-top:2px}}
.full{{grid-column:1/-1}}
</style></head>
<body>
<h1>Policy Warm-Start Optimizer</h1>
<div class="subtitle">Accelerate robot policy training via checkpoint transfer and curriculum initialization</div>

<div class="stat-row">
  <div class="stat"><div class="val">{speedup_avg:.2f}x</div><div class="lbl">Avg convergence speedup</div></div>
  <div class="stat"><div class="val">{final_warm:.4f}</div><div class="lbl">Warm-start final loss</div></div>
  <div class="stat"><div class="val">{final_cold:.4f}</div><div class="lbl">Cold-start final loss</div></div>
  <div class="stat"><div class="val">{len(tasks)}</div><div class="lbl">Tasks evaluated</div></div>
</div>

<div class="grid">
  <div class="card full">
    <h2>Convergence Curves — Warm vs Cold Start (Training Loss)</h2>
    <svg width="100%" viewBox="0 0 {svg_w} {svg_h}" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <linearGradient id="wg" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="#22d3ee" stop-opacity="0.3"/>
          <stop offset="100%" stop-color="#22d3ee" stop-opacity="0.02"/>
        </linearGradient>
      </defs>
      <polygon points="{warm_area}" fill="url(#wg)"/>
      <polyline points="{cold_pts}" fill="none" stroke="#f87171" stroke-width="2.5" stroke-dasharray="6,3"/>
      <polyline points="{warm_pts}" fill="none" stroke="#22d3ee" stroke-width="2.5"/>
      <!-- Axes -->
      <line x1="40" y1="10" x2="40" y2="{svg_h-30}" stroke="#475569" stroke-width="1"/>
      <line x1="40" y1="{svg_h-30}" x2="{svg_w-10}" y2="{svg_h-30}" stroke="#475569" stroke-width="1"/>
      <text x="{svg_w//2}" y="{svg_h-4}" text-anchor="middle" fill="#94a3b8" font-size="11">Training Steps</text>
      <text x="10" y="{svg_h//2}" transform="rotate(-90,10,{svg_h//2})" text-anchor="middle" fill="#94a3b8" font-size="11">Loss</text>
      <!-- Legend -->
      <line x1="60" y1="18" x2="90" y2="18" stroke="#22d3ee" stroke-width="2.5"/>
      <text x="95" y="22" fill="#e2e8f0" font-size="11">Warm Start</text>
      <line x1="180" y1="18" x2="210" y2="18" stroke="#f87171" stroke-width="2.5" stroke-dasharray="6,3"/>
      <text x="215" y="22" fill="#e2e8f0" font-size="11">Cold Start</text>
    </svg>
  </div>

  <div class="card">
    <h2>Per-Task Convergence Speedup</h2>
    <svg width="100%" viewBox="0 480 200 480" xmlns="http://www.w3.org/2000/svg">
      {bars_svg}
      <line x1="30" y1="170" x2="510" y2="170" stroke="#475569" stroke-width="1"/>
    </svg>
  </div>

  <div class="card">
    <h2>Checkpoint Reuse Compatibility (Transfer Score)</h2>
    <p style="color:#64748b;font-size:0.8rem;margin:0 0 8px">Rows=source checkpoints, Cols=target tasks</p>
    <svg width="100%" viewBox="0 0 250 250" xmlns="http://www.w3.org/2000/svg">
      {heat_svg}
      <text x="125" y="245" text-anchor="middle" fill="#475569" font-size="10">Target Tasks →</text>
    </svg>
  </div>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Policy Warm-Start Optimizer")
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
