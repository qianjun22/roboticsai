"""Policy Rollout Recorder — FastAPI port 8686"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8686

def build_html():
    random.seed(42)
    # Generate episode rollout data
    episodes = 40
    ep_labels = list(range(1, episodes + 1))
    # Success rate per episode window (rolling 5)
    success_flags = [1 if random.random() < (0.3 + 0.5 * (i / episodes)) else 0 for i in range(episodes)]
    rolling_success = []
    for i in range(episodes):
        window = success_flags[max(0, i-4):i+1]
        rolling_success.append(sum(window) / len(window) * 100)
    # Action prediction error (MAE) per episode — decreasing with noise
    mae_vals = [0.35 * math.exp(-0.04 * i) + 0.015 * math.sin(i * 0.7) + random.uniform(0, 0.02) for i in range(episodes)]
    # Episode lengths in steps
    ep_lengths = [int(80 + 40 * math.sin(i * 0.3) + random.uniform(-10, 10)) for i in range(episodes)]

    # SVG: rolling success rate line chart
    w, h = 560, 160
    pad = 40
    x_scale = (w - pad * 2) / (episodes - 1)
    y_scale = (h - pad * 2) / 100
    success_pts = " ".join(f"{pad + i * x_scale:.1f},{h - pad - v * y_scale:.1f}" for i, v in enumerate(rolling_success))

    # SVG: MAE line chart
    mae_max = max(mae_vals) * 1.1
    mae_pts = " ".join(f"{pad + i * x_scale:.1f},{h - pad - (v / mae_max) * (h - pad * 2):.1f}" for i, v in enumerate(mae_vals))

    # SVG: episode length bar chart
    bar_w = max(2, (w - pad * 2) / episodes - 1)
    bar_max = max(ep_lengths)
    bars_svg = ""
    colors = ["#22c55e" if success_flags[i] else "#ef4444" for i in range(episodes)]
    for i, (ln, c) in enumerate(zip(ep_lengths, colors)):
        bh = (ln / bar_max) * (h - pad * 2)
        bx = pad + i * ((w - pad * 2) / episodes)
        by = h - pad - bh
        bars_svg += f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bar_w:.1f}" height="{bh:.1f}" fill="{c}" opacity="0.8"/>'

    total_eps = episodes
    success_count = sum(success_flags)
    avg_mae = sum(mae_vals) / len(mae_vals)
    avg_len = sum(ep_lengths) / len(ep_lengths)
    latest_sr = rolling_success[-1]

    return f"""<!DOCTYPE html><html><head><title>Policy Rollout Recorder</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui,sans-serif}}
h1{{color:#C74634;padding:20px 20px 0;margin:0;font-size:1.6rem}}
.subtitle{{color:#94a3b8;padding:4px 20px 16px;font-size:0.9rem}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;padding:0 20px 20px}}
.card{{background:#1e293b;padding:20px;border-radius:8px}}
.card.wide{{grid-column:span 2}}
.card.full{{grid-column:span 4}}
h2{{color:#38bdf8;margin:0 0 12px;font-size:1rem}}
.stat{{font-size:2rem;font-weight:700;color:#f1f5f9}}
.label{{color:#64748b;font-size:0.8rem;margin-top:4px}}
.good{{color:#22c55e}}.bad{{color:#ef4444}}.warn{{color:#f59e0b}}
svg text{{fill:#94a3b8;font-size:10px}}
</style></head>
<body>
<h1>Policy Rollout Recorder</h1>
<div class="subtitle">Port {PORT} — Real-time episode evaluation and policy performance tracking</div>
<div class="grid">
  <div class="card">
    <h2>Total Episodes</h2>
    <div class="stat">{total_eps}</div>
    <div class="label">recorded this session</div>
  </div>
  <div class="card">
    <h2>Success Rate</h2>
    <div class="stat {'good' if latest_sr >= 60 else 'warn' if latest_sr >= 40 else 'bad'}">{latest_sr:.1f}%</div>
    <div class="label">rolling 5-episode window</div>
  </div>
  <div class="card">
    <h2>Avg MAE</h2>
    <div class="stat warn">{avg_mae:.4f}</div>
    <div class="label">action prediction error</div>
  </div>
  <div class="card">
    <h2>Avg Steps</h2>
    <div class="stat">{avg_len:.0f}</div>
    <div class="label">per episode</div>
  </div>

  <div class="card wide">
    <h2>Rolling Success Rate (%)</h2>
    <svg width="{w}" height="{h}">
      <line x1="{pad}" y1="{h-pad}" x2="{w-pad}" y2="{h-pad}" stroke="#334155" stroke-width="1"/>
      <line x1="{pad}" y1="{pad}" x2="{pad}" y2="{h-pad}" stroke="#334155" stroke-width="1"/>
      <text x="{pad-4}" y="{pad+4}" text-anchor="end">100</text>
      <text x="{pad-4}" y="{h-pad+4}" text-anchor="end">0</text>
      <polyline points="{success_pts}" fill="none" stroke="#22c55e" stroke-width="2"/>
      <text x="{w//2}" y="{h-4}" text-anchor="middle">Episode</text>
    </svg>
  </div>

  <div class="card wide">
    <h2>Action Prediction MAE</h2>
    <svg width="{w}" height="{h}">
      <line x1="{pad}" y1="{h-pad}" x2="{w-pad}" y2="{h-pad}" stroke="#334155" stroke-width="1"/>
      <line x1="{pad}" y1="{pad}" x2="{pad}" y2="{h-pad}" stroke="#334155" stroke-width="1"/>
      <text x="{pad-4}" y="{pad+4}" text-anchor="end">{mae_max:.3f}</text>
      <text x="{pad-4}" y="{h-pad+4}" text-anchor="end">0</text>
      <polyline points="{mae_pts}" fill="none" stroke="#f59e0b" stroke-width="2"/>
      <text x="{w//2}" y="{h-4}" text-anchor="middle">Episode</text>
    </svg>
  </div>

  <div class="card full">
    <h2>Episode Lengths (green=success, red=failure)</h2>
    <svg width="{w}" height="{h}">
      <line x1="{pad}" y1="{h-pad}" x2="{w-pad}" y2="{h-pad}" stroke="#334155" stroke-width="1"/>
      <line x1="{pad}" y1="{pad}" x2="{pad}" y2="{h-pad}" stroke="#334155" stroke-width="1"/>
      <text x="{pad-4}" y="{pad+4}" text-anchor="end">{bar_max}</text>
      <text x="{pad-4}" y="{h-pad+4}" text-anchor="end">0</text>
      {bars_svg}
      <text x="{w//2}" y="{h-4}" text-anchor="middle">Episode Index</text>
    </svg>
  </div>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Policy Rollout Recorder")
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
