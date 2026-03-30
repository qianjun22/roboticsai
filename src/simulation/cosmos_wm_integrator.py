"""Cosmos World Model Integrator — FastAPI port 8736"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8736

def build_html():
    random.seed(42)
    # Generate world-model latent trajectory data
    steps = 32
    latent_loss = [round(2.8 * math.exp(-i / 10) + 0.12 + random.uniform(-0.03, 0.03), 4) for i in range(steps)]
    recon_loss  = [round(1.5 * math.exp(-i / 12) + 0.08 + random.uniform(-0.02, 0.02), 4) for i in range(steps)]
    pred_horizon = [round(0.95 - 0.45 * math.exp(-i / 8) + random.uniform(-0.01, 0.01), 4) for i in range(steps)]

    # SVG line chart: latent_loss & recon_loss over training steps
    W, H = 560, 180
    pad = 36
    chart_w = W - 2 * pad
    chart_h = H - 2 * pad
    max_loss = 3.0

    def to_svg_pts(series, lo=0.0, hi=3.0):
        pts = []
        for i, v in enumerate(series):
            x = pad + i * chart_w / (len(series) - 1)
            y = H - pad - (v - lo) / (hi - lo) * chart_h
            pts.append(f"{x:.1f},{y:.1f}")
        return " ".join(pts)

    latent_pts = to_svg_pts(latent_loss)
    recon_pts  = to_svg_pts(recon_loss)

    # Horizon bar chart
    bar_w = chart_w / steps
    bars_svg = ""
    for i, v in enumerate(pred_horizon):
        bh = v * chart_h
        bx = pad + i * bar_w
        by = H - pad - bh
        g = int(59 + v * 130)
        bars_svg += f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bar_w - 1:.1f}" height="{bh:.1f}" fill="#{0:02x}{g:02x}{0xaf:02x}" opacity="0.8"/>'

    # Simulation metrics
    wm_fps      = round(28.4 + random.uniform(-1.2, 1.2), 1)
    token_rate  = round(1247 + random.uniform(-50, 50))
    latent_dim  = 2048
    horizon_len = 16
    rollout_acc = round(0.874 + random.uniform(-0.01, 0.01), 3)
    gpu_mem_gb  = round(18.3 + random.uniform(-0.5, 0.5), 1)

    # Sine-based prediction error surface (heatmap approximation via rects)
    heat_n = 20
    heat_size = chart_w / heat_n
    heat_svg = ""
    for row in range(heat_n):
        for col in range(heat_n):
            v = 0.5 + 0.45 * math.sin(row * 0.4) * math.cos(col * 0.4)
            r = int(15 + v * 200)
            b = int(200 - v * 160)
            heat_svg += (f'<rect x="{pad + col * heat_size:.1f}" y="{pad + row * heat_size:.1f}" '
                         f'width="{heat_size:.1f}" height="{heat_size:.1f}" '
                         f'fill="rgb({r},56,{b})" opacity="0.85"/>')

    return f"""<!DOCTYPE html><html><head><title>Cosmos WM Integrator</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui;padding:20px}}
h1{{color:#C74634;margin:0 0 4px 0}}h2{{color:#38bdf8;font-size:14px;margin:8px 0 4px 0}}
.card{{background:#1e293b;padding:18px;margin:10px 0;border-radius:8px;border:1px solid #334155}}
.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:10px}}
.metric{{background:#0f172a;border-radius:6px;padding:14px;text-align:center}}
.metric .val{{font-size:28px;font-weight:700;color:#a78bfa}}
.metric .lbl{{font-size:11px;color:#94a3b8;margin-top:4px}}
.tag{{display:inline-block;background:#1e3a5f;color:#7dd3fc;padding:2px 8px;border-radius:4px;font-size:11px;margin:2px}}
svg text{{font:11px system-ui;fill:#94a3b8}}
</style></head>
<body>
<h1>Cosmos World Model Integrator</h1>
<p style="color:#64748b;font-size:13px;margin:0 0 12px 0">OCI A100 cluster · latent dim {latent_dim} · horizon {horizon_len} steps · port {PORT}</p>

<div class="grid">
  <div class="metric"><div class="val">{wm_fps}</div><div class="lbl">Sim FPS</div></div>
  <div class="metric"><div class="val">{int(token_rate):,}</div><div class="lbl">Tokens/sec</div></div>
  <div class="metric"><div class="val">{rollout_acc:.1%}</div><div class="lbl">Rollout Accuracy</div></div>
  <div class="metric"><div class="val">{gpu_mem_gb} GB</div><div class="lbl">GPU Memory</div></div>
  <div class="metric"><div class="val">{latent_dim:,}</div><div class="lbl">Latent Dim</div></div>
  <div class="metric"><div class="val">{horizon_len}</div><div class="lbl">Pred Horizon</div></div>
</div>

<div class="card">
  <h2>Training Loss Curves — {steps} steps</h2>
  <svg width="{W}" height="{H}" style="display:block">
    <line x1="{pad}" y1="{pad}" x2="{pad}" y2="{H-pad}" stroke="#334155"/>
    <line x1="{pad}" y1="{H-pad}" x2="{W-pad}" y2="{H-pad}" stroke="#334155"/>
    <polyline points="{latent_pts}" fill="none" stroke="#a78bfa" stroke-width="2"/>
    <polyline points="{recon_pts}"  fill="none" stroke="#38bdf8" stroke-width="2"/>
    <text x="{pad+4}" y="{pad+14}">■ Latent Loss</text>
    <text x="{pad+110}" y="{pad+14}" fill="#38bdf8">■ Recon Loss</text>
    <text x="{pad}" y="{H-pad+14}">0</text>
    <text x="{W-pad-12}" y="{H-pad+14}">{steps}</text>
  </svg>
</div>

<div class="card">
  <h2>Prediction Horizon Accuracy per Step</h2>
  <svg width="{W}" height="{H}" style="display:block">
    <line x1="{pad}" y1="{pad}" x2="{pad}" y2="{H-pad}" stroke="#334155"/>
    <line x1="{pad}" y1="{H-pad}" x2="{W-pad}" y2="{H-pad}" stroke="#334155"/>
    {bars_svg}
    <text x="{pad}" y="{H-pad+14}">step 0</text>
    <text x="{W-pad-30}" y="{H-pad+14}">step {steps-1}</text>
  </svg>
</div>

<div class="card">
  <h2>Latent Space Prediction Error Heatmap (20×20 grid)</h2>
  <svg width="{W}" height="{W}" style="display:block">
    {heat_svg}
    <text x="4" y="{W//2}" transform="rotate(-90 4 {W//2})">latent dim B</text>
    <text x="{W//2 - 40}" y="{W - 4}">latent dim A</text>
  </svg>
</div>

<div class="card">
  <h2>Integration Stack</h2>
  <span class="tag">NVIDIA Cosmos 1.0</span><span class="tag">Diffusion Transformer</span>
  <span class="tag">GR00T N1.6 backbone</span><span class="tag">OCI A100 40GB</span>
  <span class="tag">PyTorch 2.3</span><span class="tag">Flash-Attn v2</span>
  <span class="tag">latent dim 2048</span><span class="tag">horizon 16</span>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Cosmos World Model Integrator")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return build_html()

    @app.get("/health")
    def health():
        return {"status": "ok", "port": PORT, "service": "cosmos_wm_integrator"}

    @app.get("/metrics")
    def metrics():
        random.seed()
        return {
            "sim_fps": round(28.4 + random.uniform(-1.2, 1.2), 1),
            "token_rate": round(1247 + random.uniform(-50, 50)),
            "rollout_accuracy": round(0.874 + random.uniform(-0.01, 0.01), 3),
            "gpu_memory_gb": round(18.3 + random.uniform(-0.5, 0.5), 1),
            "latent_dim": 2048,
            "pred_horizon": 16,
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
