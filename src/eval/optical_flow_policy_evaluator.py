"""Optical Flow Policy Evaluator — FastAPI port 8788"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8788

def build_html():
    random.seed(42)
    # Generate optical flow magnitude data over 40 timesteps
    timesteps = 40
    flow_magnitudes = [2.5 + 1.8 * math.sin(i * 0.3) + random.uniform(-0.4, 0.4) for i in range(timesteps)]
    policy_scores  = [0.55 + 0.3 * math.cos(i * 0.25 + 0.5) * math.exp(-i * 0.02) + random.uniform(-0.05, 0.05) for i in range(timesteps)]
    correlation    = [flow_magnitudes[i] * policy_scores[i] / 5.0 + random.uniform(-0.1, 0.1) for i in range(timesteps)]

    # SVG line chart for flow magnitudes (w=560, h=140)
    W, H = 560, 140
    pad = 20
    def to_svg_x(i): return pad + i * (W - 2 * pad) / (timesteps - 1)
    def to_svg_y(val, lo, hi): return H - pad - (val - lo) / (hi - lo) * (H - 2 * pad)

    fm_lo, fm_hi = min(flow_magnitudes) - 0.2, max(flow_magnitudes) + 0.2
    flow_pts = " ".join(f"{to_svg_x(i):.1f},{to_svg_y(v, fm_lo, fm_hi):.1f}" for i, v in enumerate(flow_magnitudes))

    ps_lo, ps_hi = 0.0, 1.0
    policy_pts = " ".join(f"{to_svg_x(i):.1f},{to_svg_y(v, ps_lo, ps_hi):.1f}" for i, v in enumerate(policy_scores))

    # Heatmap cells for correlation matrix (10x10 sampled)
    heatmap_cells = ""
    for row in range(10):
        for col in range(10):
            val = 0.5 + 0.5 * math.sin(row * 0.7) * math.cos(col * 0.7) + random.uniform(-0.1, 0.1)
            val = max(0.0, min(1.0, val))
            r = int(val * 200)
            g = int((1 - val) * 180 + 20)
            b = int(180 - val * 130)
            heatmap_cells += f'<rect x="{col*28}" y="{row*28}" width="26" height="26" fill="rgb({r},{g},{b})" rx="3"/>'
            heatmap_cells += f'<text x="{col*28+13}" y="{row*28+16}" text-anchor="middle" font-size="8" fill="#fff">{val:.1f}</text>'

    avg_flow = sum(flow_magnitudes) / len(flow_magnitudes)
    avg_score = sum(policy_scores) / len(policy_scores)
    avg_corr  = sum(correlation) / len(correlation)
    peak_flow = max(flow_magnitudes)
    min_score = min(policy_scores)

    return f"""<!DOCTYPE html><html><head><title>Optical Flow Policy Evaluator</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui,sans-serif}}
h1{{color:#C74634;padding:24px 32px 0;margin:0;font-size:1.6rem;letter-spacing:0.03em}}
h2{{color:#38bdf8;font-size:1.1rem;margin:0 0 12px}}
.subtitle{{color:#94a3b8;padding:4px 32px 20px;font-size:0.92rem}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;padding:0 32px 16px}}
.card{{background:#1e293b;padding:20px;border-radius:10px;border:1px solid #334155}}
.full{{grid-column:1/-1}}
.stat-row{{display:flex;gap:12px;flex-wrap:wrap;padding:0 32px 16px}}
.stat{{background:#1e293b;border-radius:8px;padding:14px 22px;border:1px solid #334155;min-width:120px}}
.stat .val{{font-size:1.5rem;font-weight:700;color:#C74634}}
.stat .lbl{{font-size:0.78rem;color:#94a3b8;margin-top:2px}}
svg text{{font-family:system-ui}}
.tag{{display:inline-block;background:#0f4c6b;color:#7dd3fc;border-radius:4px;padding:2px 8px;font-size:0.78rem;margin:2px}}
</style></head>
<body>
<h1>Optical Flow Policy Evaluator</h1>
<div class="subtitle">Real-time optical flow analysis correlated with robot policy action confidence — port {PORT}</div>

<div class="stat-row">
  <div class="stat"><div class="val">{avg_flow:.2f}</div><div class="lbl">Avg Flow Magnitude</div></div>
  <div class="stat"><div class="val">{avg_score:.3f}</div><div class="lbl">Avg Policy Score</div></div>
  <div class="stat"><div class="val">{avg_corr:.3f}</div><div class="lbl">Avg Correlation</div></div>
  <div class="stat"><div class="val">{peak_flow:.2f}</div><div class="lbl">Peak Flow</div></div>
  <div class="stat"><div class="val">{min_score:.3f}</div><div class="lbl">Min Policy Confidence</div></div>
  <div class="stat"><div class="val">{timesteps}</div><div class="lbl">Timesteps Evaluated</div></div>
</div>

<div class="grid">
  <div class="card">
    <h2>Optical Flow Magnitude Over Time</h2>
    <svg width="{W}" height="{H}" style="background:#0f172a;border-radius:6px">
      <polyline points="{flow_pts}" fill="none" stroke="#38bdf8" stroke-width="2" stroke-linejoin="round"/>
      <!-- x-axis label -->
      <text x="{pad}" y="{H-2}" font-size="9" fill="#64748b">t=0</text>
      <text x="{W-pad-20}" y="{H-2}" font-size="9" fill="#64748b">t={timesteps-1}</text>
      <text x="8" y="{pad+5}" font-size="9" fill="#64748b">{fm_hi:.1f}</text>
      <text x="8" y="{H-pad}" font-size="9" fill="#64748b">{fm_lo:.1f}</text>
    </svg>
  </div>

  <div class="card">
    <h2>Policy Confidence Score Over Time</h2>
    <svg width="{W}" height="{H}" style="background:#0f172a;border-radius:6px">
      <polyline points="{policy_pts}" fill="none" stroke="#f59e0b" stroke-width="2" stroke-linejoin="round"/>
      <line x1="{pad}" y1="{to_svg_y(0.5, ps_lo, ps_hi):.1f}" x2="{W-pad}" y2="{to_svg_y(0.5, ps_lo, ps_hi):.1f}"
            stroke="#475569" stroke-width="1" stroke-dasharray="4,4"/>
      <text x="{W-pad-24}" y="{to_svg_y(0.5, ps_lo, ps_hi):.1f}" font-size="9" fill="#64748b">0.5</text>
      <text x="{pad}" y="{H-2}" font-size="9" fill="#64748b">t=0</text>
      <text x="{W-pad-20}" y="{H-2}" font-size="9" fill="#64748b">t={timesteps-1}</text>
    </svg>
  </div>

  <div class="card full">
    <h2>Flow-Policy Correlation Heatmap (10×10 Action Dimensions)</h2>
    <svg width="280" height="280" style="background:#0f172a;border-radius:6px">
      {heatmap_cells}
    </svg>
    <div style="margin-top:10px">
      <span class="tag">low correlation</span>
      <span class="tag" style="background:#1a4730;color:#6ee7b7">high correlation</span>
      <span class="tag" style="background:#3b1d1d;color:#fca5a5">negative correlation</span>
    </div>
  </div>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Optical Flow Policy Evaluator")
    @app.get("/", response_class=HTMLResponse)
    def index(): return build_html()
    @app.get("/health")
    def health(): return {"status": "ok", "port": PORT}
    @app.get("/metrics")
    def metrics():
        random.seed(42)
        flow_magnitudes = [2.5 + 1.8 * math.sin(i * 0.3) + random.uniform(-0.4, 0.4) for i in range(40)]
        policy_scores   = [0.55 + 0.3 * math.cos(i * 0.25 + 0.5) * math.exp(-i * 0.02) + random.uniform(-0.05, 0.05) for i in range(40)]
        return {
            "avg_flow_magnitude": sum(flow_magnitudes) / 40,
            "avg_policy_score": sum(policy_scores) / 40,
            "timesteps": 40,
            "port": PORT
        }

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
