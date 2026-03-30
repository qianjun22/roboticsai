"""Reward Signal Debugger — FastAPI port 8790"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8790

def build_html():
    random.seed(42)
    # Generate reward curves over 200 training steps
    steps = list(range(0, 200, 2))
    # Sparse reward signal with noise
    sparse_rewards = [max(0.0, math.tanh((s - 60) / 30) + random.gauss(0, 0.15)) for s in steps]
    # Dense shaped reward
    dense_rewards = [0.3 * math.sin(s / 15) * math.exp(-s / 300) + 0.5 * math.tanh((s - 40) / 25) + random.gauss(0, 0.05) for s in steps]
    # Potential-based shaping term
    shaping = [0.2 * math.cos(s / 10) * math.exp(-s / 200) + random.gauss(0, 0.03) for s in steps]

    # SVG polyline points (scaled to 560x120 viewport)
    def to_svg_points(vals, y_min, y_max, width=560, height=120):
        pts = []
        for i, v in enumerate(vals):
            x = i * width / (len(vals) - 1)
            y = height - (v - y_min) / max(y_max - y_min, 1e-9) * height
            pts.append(f"{x:.1f},{y:.1f}")
        return " ".join(pts)

    sparse_pts = to_svg_points(sparse_rewards, -0.3, 1.2)
    dense_pts  = to_svg_points(dense_rewards,  -0.3, 1.2)
    shaping_pts = to_svg_points(shaping,        -0.3, 1.2)

    # Component breakdown bar chart (last 20 steps avg)
    tail = -20
    comp_names = ["Task", "Safety", "Efficiency", "Smooth", "Contact"]
    comp_vals  = [
        max(0, sum(sparse_rewards[tail:]) / 20),
        max(0, 0.18 + random.gauss(0, 0.02)),
        max(0, 0.12 + random.gauss(0, 0.015)),
        max(0, 0.09 + random.gauss(0, 0.01)),
        max(0, 0.06 + random.gauss(0, 0.008)),
    ]
    total_reward = sum(comp_vals)

    bar_svg_parts = []
    colors = ["#C74634", "#38bdf8", "#34d399", "#fbbf24", "#a78bfa"]
    bar_width = 70
    for idx, (name, val) in enumerate(zip(comp_names, comp_vals)):
        bar_h = int(val / max(total_reward, 1e-9) * 100)
        x = 20 + idx * 100
        y = 120 - bar_h
        bar_svg_parts.append(
            f'<rect x="{x}" y="{y}" width="{bar_width}" height="{bar_h}" fill="{colors[idx]}" opacity="0.85"/>'
            f'<text x="{x + bar_width//2}" y="{y - 5}" fill="#e2e8f0" font-size="10" text-anchor="middle">{val:.3f}</text>'
            f'<text x="{x + bar_width//2}" y="138" fill="#94a3b8" font-size="10" text-anchor="middle">{name}</text>'
        )
    bar_svg = "\n".join(bar_svg_parts)

    # Reward variance heatmap (10x10 grid: episode x component)
    heatmap_cells = []
    for row in range(10):
        for col in range(10):
            intensity = 0.4 + 0.5 * math.sin(row * 0.8 + col * 0.5) + random.gauss(0, 0.1)
            intensity = max(0.0, min(1.0, intensity))
            r = int(30 + intensity * 180)
            g = int(30 + intensity * 80)
            b = int(80 + intensity * 120)
            heatmap_cells.append(
                f'<rect x="{col*28}" y="{row*22}" width="26" height="20" fill="rgb({r},{g},{b})" rx="2"/>'
            )
    heatmap_svg = "\n".join(heatmap_cells)

    # Stats
    avg_sparse = sum(sparse_rewards[-20:]) / 20
    avg_dense  = sum(dense_rewards[-20:]) / 20
    variance   = sum((v - avg_sparse)**2 for v in sparse_rewards[-20:]) / 20

    return f"""<!DOCTYPE html><html><head><title>Reward Signal Debugger</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui,sans-serif}}
h1{{color:#C74634;padding:20px 20px 0;margin:0;font-size:1.6rem}}
.subtitle{{color:#64748b;padding:4px 20px 16px;font-size:0.85rem}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;padding:0 16px}}
.grid3{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px;padding:0 16px 16px}}
.card{{background:#1e293b;padding:20px;border-radius:8px;border:1px solid #334155}}
.card h2{{color:#38bdf8;margin:0 0 12px;font-size:1rem}}
.stat-val{{font-size:2rem;font-weight:700;color:#C74634}}
.stat-label{{color:#64748b;font-size:0.8rem;margin-top:4px}}
.badge{{display:inline-block;padding:3px 10px;border-radius:99px;font-size:0.75rem;background:#1e3a5f;color:#38bdf8;margin:2px}}
svg text{{font-family:system-ui}}
</style></head>
<body>
<h1>Reward Signal Debugger</h1>
<div class="subtitle">OCI Robot Cloud · Training Step Analysis · Port {PORT}</div>

<div class="grid3">
  <div class="card">
    <h2>Sparse Reward (recent)</h2>
    <div class="stat-val">{avg_sparse:.4f}</div>
    <div class="stat-label">avg last 20 steps</div>
    <div style="margin-top:8px"><span class="badge">var={variance:.4f}</span> <span class="badge">steps=200</span></div>
  </div>
  <div class="card">
    <h2>Dense Reward (recent)</h2>
    <div class="stat-val">{avg_dense:.4f}</div>
    <div class="stat-label">avg last 20 steps</div>
    <div style="margin-top:8px"><span class="badge">shaped</span> <span class="badge">potential-based</span></div>
  </div>
  <div class="card">
    <h2>Total Composite</h2>
    <div class="stat-val">{total_reward:.4f}</div>
    <div class="stat-label">sum of components</div>
    <div style="margin-top:8px"><span class="badge">5 components</span> <span class="badge">weighted</span></div>
  </div>
</div>

<div class="grid" style="margin-top:0">
  <div class="card">
    <h2>Reward Curves Over Training</h2>
    <svg width="100%" viewBox="0 0 560 130" preserveAspectRatio="xMidYMid meet">
      <!-- Grid lines -->
      <line x1="0" y1="0"   x2="560" y2="0"   stroke="#334155" stroke-width="0.5"/>
      <line x1="0" y1="32"  x2="560" y2="32"  stroke="#334155" stroke-width="0.5"/>
      <line x1="0" y1="65"  x2="560" y2="65"  stroke="#334155" stroke-width="0.5"/>
      <line x1="0" y1="97"  x2="560" y2="97"  stroke="#334155" stroke-width="0.5"/>
      <line x1="0" y1="120" x2="560" y2="120" stroke="#334155" stroke-width="0.5"/>
      <!-- Curves -->
      <polyline points="{shaping_pts}" fill="none" stroke="#a78bfa" stroke-width="1.5" opacity="0.7"/>
      <polyline points="{dense_pts}"   fill="none" stroke="#34d399" stroke-width="2" opacity="0.85"/>
      <polyline points="{sparse_pts}"  fill="none" stroke="#C74634" stroke-width="2.5"/>
      <!-- Legend -->
      <rect x="10" y="4" width="12" height="4" fill="#C74634"/><text x="26" y="11" fill="#e2e8f0" font-size="10">Sparse</text>
      <rect x="80" y="4" width="12" height="4" fill="#34d399"/><text x="96" y="11" fill="#e2e8f0" font-size="10">Dense</text>
      <rect x="150" y="4" width="12" height="4" fill="#a78bfa"/><text x="166" y="11" fill="#e2e8f0" font-size="10">Shaping</text>
    </svg>
  </div>

  <div class="card">
    <h2>Component Breakdown (last 20 steps)</h2>
    <svg width="100%" viewBox="0 0 580 150" preserveAspectRatio="xMidYMid meet">
      <!-- Axis -->
      <line x1="10" y1="0" x2="10" y2="120" stroke="#334155" stroke-width="1"/>
      <line x1="10" y1="120" x2="570" y2="120" stroke="#334155" stroke-width="1"/>
      {bar_svg}
    </svg>
  </div>
</div>

<div class="grid" style="margin-top:0">
  <div class="card">
    <h2>Reward Variance Heatmap (Episodes × Components)</h2>
    <svg width="100%" viewBox="0 0 280 220" preserveAspectRatio="xMidYMid meet">
      {heatmap_svg}
      <text x="0"   y="215" fill="#64748b" font-size="9">Ep 1</text>
      <text x="240" y="215" fill="#64748b" font-size="9">Ep 10</text>
    </svg>
  </div>

  <div class="card">
    <h2>Reward Shaping Diagnostics</h2>
    <table style="width:100%;border-collapse:collapse;font-size:0.85rem">
      <tr style="color:#64748b"><td>Signal Type</td><td style="text-align:right">Value</td><td style="text-align:right">Status</td></tr>
      <tr style="border-top:1px solid #334155"><td>Sparse reward coverage</td><td style="text-align:right">{avg_sparse:.4f}</td><td style="text-align:right;color:#34d399">OK</td></tr>
      <tr style="border-top:1px solid #334155"><td>Potential-based shaping</td><td style="text-align:right">{sum(shaping[-20:])/20:.4f}</td><td style="text-align:right;color:#34d399">OK</td></tr>
      <tr style="border-top:1px solid #334155"><td>Reward variance</td><td style="text-align:right">{variance:.5f}</td><td style="text-align:right;color:#{'fbbf24' if variance > 0.05 else '34d399'}">{'HIGH' if variance > 0.05 else 'STABLE'}</td></tr>
      <tr style="border-top:1px solid #334155"><td>Dense/sparse ratio</td><td style="text-align:right">{avg_dense/max(avg_sparse,1e-9):.2f}x</td><td style="text-align:right;color:#38bdf8">INFO</td></tr>
      <tr style="border-top:1px solid #334155"><td>Shaping leak</td><td style="text-align:right">{abs(sum(shaping[-5:])/5):.5f}</td><td style="text-align:right;color:#34d399">OK</td></tr>
      <tr style="border-top:1px solid #334155"><td>Composite score</td><td style="text-align:right">{total_reward:.4f}</td><td style="text-align:right;color:#C74634">LIVE</td></tr>
    </table>
  </div>
</div>

</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Reward Signal Debugger")
    @app.get("/", response_class=HTMLResponse)
    def index(): return build_html()
    @app.get("/health")
    def health(): return {"status": "ok", "port": PORT, "service": "reward_signal_debugger"}

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
