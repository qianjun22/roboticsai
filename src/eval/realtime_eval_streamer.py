"""Realtime Eval Streamer — FastAPI port 8698"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8698

def build_html():
    # Generate realistic eval episode data
    episodes = 40
    success_rates = [max(0.0, min(1.0, 0.35 + 0.45 * (1 - math.exp(-i / 12)) + random.uniform(-0.06, 0.06))) for i in range(episodes)]
    rewards = [max(0.0, 0.4 + 0.5 * (1 - math.exp(-i / 10)) + random.uniform(-0.08, 0.08)) for i in range(episodes)]
    latencies_ms = [220 + 40 * math.sin(i * 0.4) + random.uniform(-15, 15) for i in range(episodes)]

    # SVG success rate line chart (600x160)
    sr_w, sr_h = 560, 140
    sr_pts = " ".join(
        f"{10 + i * (sr_w - 20) / (episodes - 1):.1f},{sr_h - 10 - (sr_h - 20) * v:.1f}"
        for i, v in enumerate(success_rates)
    )
    # SVG reward area chart
    rw_pts = " ".join(
        f"{10 + i * (sr_w - 20) / (episodes - 1):.1f},{sr_h - 10 - (sr_h - 20) * v:.1f}"
        for i, v in enumerate(rewards)
    )
    rw_area = rw_pts + f" {10 + (episodes-1)*(sr_w-20)/(episodes-1):.1f},{sr_h-10} 10,{sr_h-10}"

    # SVG latency bar chart
    bar_w = (sr_w - 20) / episodes
    lat_bars = "".join(
        f'<rect x="{10 + i * bar_w:.1f}" y="{sr_h - 10 - (sr_h - 20) * (v / 320):.1f}" '
        f'width="{bar_w * 0.75:.1f}" height="{(sr_h - 20) * (v / 320):.1f}" fill="#f59e0b" opacity="0.8"/>'
        for i, v in enumerate(latencies_ms)
    )

    cur_sr = success_rates[-1]
    cur_rw = rewards[-1]
    cur_lat = latencies_ms[-1]
    avg_sr = sum(success_rates) / episodes
    total_steps = episodes * random.randint(180, 240)

    # Scatter plot: reward vs success for each episode
    scatter_pts = "".join(
        f'<circle cx="{20 + (sr_w - 40) * success_rates[i]:.1f}" cy="{sr_h - 20 - (sr_h - 40) * rewards[i]:.1f}" r="4" '
        f'fill="#38bdf8" opacity="0.7"/>'
        for i in range(episodes)
    )

    return f"""<!DOCTYPE html><html><head><title>Realtime Eval Streamer</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui}}
h1{{color:#C74634;padding:20px 20px 0;margin:0}}
h2{{color:#38bdf8;margin:0 0 10px}}
.card{{background:#1e293b;padding:20px;margin:10px;border-radius:8px}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:10px}}
.stat{{background:#1e293b;padding:16px;border-radius:8px;text-align:center}}
.stat-val{{font-size:2em;font-weight:bold;color:#38bdf8}}
.stat-lbl{{color:#94a3b8;font-size:0.85em;margin-top:4px}}
.row{{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin:10px}}
svg{{width:100%;height:auto;overflow:visible}}
.badge{{display:inline-block;padding:2px 8px;border-radius:4px;font-size:0.75em;margin-left:6px}}
.live{{background:#16a34a;color:#fff}}
</style></head>
<body>
<h1>Realtime Eval Streamer <span class="badge live">LIVE</span></h1>
<p style="color:#94a3b8;padding:0 20px;margin:4px 0">Port {PORT} — Streaming closed-loop evaluation metrics in real-time</p>

<div class="grid">
  <div class="stat"><div class="stat-val">{cur_sr*100:.1f}%</div><div class="stat-lbl">Current Success Rate</div></div>
  <div class="stat"><div class="stat-val">{avg_sr*100:.1f}%</div><div class="stat-lbl">Avg Success Rate</div></div>
  <div class="stat"><div class="stat-val">{cur_lat:.0f}ms</div><div class="stat-lbl">Inference Latency</div></div>
  <div class="stat"><div class="stat-val">{total_steps:,}</div><div class="stat-lbl">Total Steps Evaluated</div></div>
</div>

<div class="row">
  <div class="card">
    <h2>Success Rate per Episode</h2>
    <svg viewBox="0 0 {sr_w} {sr_h}" style="height:160px">
      <line x1="10" y1="{sr_h-10}" x2="{sr_w-10}" y2="{sr_h-10}" stroke="#334155" stroke-width="1"/>
      <line x1="10" y1="10" x2="10" y2="{sr_h-10}" stroke="#334155" stroke-width="1"/>
      <polyline points="{sr_pts}" fill="none" stroke="#22c55e" stroke-width="2.5" stroke-linejoin="round"/>
      {''.join(f'<circle cx="{10 + i*(sr_w-20)/(episodes-1):.1f}" cy="{sr_h-10-(sr_h-20)*v:.1f}" r="3" fill="#22c55e"/>' for i,v in enumerate(success_rates))}
      <text x="12" y="22" fill="#64748b" font-size="10">1.0</text>
      <text x="12" y="{sr_h//2}" fill="#64748b" font-size="10">0.5</text>
      <text x="12" y="{sr_h-12}" fill="#64748b" font-size="10">0.0</text>
    </svg>
  </div>
  <div class="card">
    <h2>Inference Latency (ms)</h2>
    <svg viewBox="0 0 {sr_w} {sr_h}" style="height:160px">
      <line x1="10" y1="{sr_h-10}" x2="{sr_w-10}" y2="{sr_h-10}" stroke="#334155" stroke-width="1"/>
      <line x1="10" y1="10" x2="10" y2="{sr_h-10}" stroke="#334155" stroke-width="1"/>
      {lat_bars}
      <text x="12" y="22" fill="#64748b" font-size="10">320ms</text>
      <text x="12" y="{sr_h-12}" fill="#64748b" font-size="10">0ms</text>
    </svg>
  </div>
</div>

<div class="row">
  <div class="card">
    <h2>Cumulative Reward per Episode</h2>
    <svg viewBox="0 0 {sr_w} {sr_h}" style="height:160px">
      <line x1="10" y1="{sr_h-10}" x2="{sr_w-10}" y2="{sr_h-10}" stroke="#334155" stroke-width="1"/>
      <polygon points="{rw_area}" fill="#38bdf8" opacity="0.18"/>
      <polyline points="{rw_pts}" fill="none" stroke="#38bdf8" stroke-width="2.5" stroke-linejoin="round"/>
      <text x="12" y="22" fill="#64748b" font-size="10">1.0</text>
      <text x="12" y="{sr_h-12}" fill="#64748b" font-size="10">0.0</text>
    </svg>
  </div>
  <div class="card">
    <h2>Reward vs Success Scatter</h2>
    <svg viewBox="0 0 {sr_w} {sr_h}" style="height:160px">
      <line x1="20" y1="{sr_h-20}" x2="{sr_w-20}" y2="{sr_h-20}" stroke="#334155" stroke-width="1"/>
      <line x1="20" y1="20" x2="20" y2="{sr_h-20}" stroke="#334155" stroke-width="1"/>
      {scatter_pts}
      <text x="{sr_w//2-20}" y="{sr_h-4}" fill="#64748b" font-size="10">Success Rate</text>
      <text x="2" y="{sr_h//2}" fill="#64748b" font-size="10" writing-mode="vertical-rl">Reward</text>
    </svg>
  </div>
</div>

<div class="card" style="margin:10px">
  <h2>Recent Episodes</h2>
  <table style="width:100%;border-collapse:collapse;font-size:0.9em">
    <tr style="color:#94a3b8;border-bottom:1px solid #334155">
      <th style="text-align:left;padding:6px">Episode</th>
      <th style="text-align:left;padding:6px">Success</th>
      <th style="text-align:left;padding:6px">Reward</th>
      <th style="text-align:left;padding:6px">Latency</th>
      <th style="text-align:left;padding:6px">Steps</th>
    </tr>
    {''.join(f"<tr style='border-bottom:1px solid #1e293b'><td style='padding:5px 6px'>Ep {episodes-5+j+1}</td><td style='padding:5px 6px;color:{('#22c55e' if success_rates[episodes-5+j]>0.5 else '#ef4444')}'>{success_rates[episodes-5+j]*100:.1f}%</td><td style='padding:5px 6px'>{rewards[episodes-5+j]:.3f}</td><td style='padding:5px 6px'>{latencies_ms[episodes-5+j]:.0f}ms</td><td style='padding:5px 6px'>{random.randint(180,240)}</td></tr>" for j in range(5))}
  </table>
</div>

</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Realtime Eval Streamer")
    @app.get("/", response_class=HTMLResponse)
    def index(): return build_html()
    @app.get("/health")
    def health(): return {"status": "ok", "port": PORT}
    @app.get("/metrics")
    def metrics():
        eps = 40
        sr = [max(0.0, min(1.0, 0.35 + 0.45*(1-math.exp(-i/12)) + random.uniform(-0.06, 0.06))) for i in range(eps)]
        return {"success_rate": sum(sr)/eps, "episodes": eps, "port": PORT}

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
