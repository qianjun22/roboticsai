"""Bimanual Policy Trainer — FastAPI port 8716"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8716

def build_html():
    random.seed(42)

    # Generate loss curve (exponential decay with noise)
    steps = list(range(0, 2001, 100))
    loss_vals = [round(2.4 * math.exp(-0.0018 * s) + 0.08 + random.gauss(0, 0.015), 4) for s in steps]

    # Arm synchrony metric (sinusoidal, improving over time)
    sync_vals = [round(0.55 + 0.38 * (1 - math.exp(-s / 800)) + 0.04 * math.sin(s / 120) + random.gauss(0, 0.01), 3) for s in steps]

    # SVG loss curve (600x180)
    svg_w, svg_h = 600, 180
    pad = 40
    plot_w = svg_w - 2 * pad
    plot_h = svg_h - 2 * pad
    loss_min, loss_max = 0.05, 2.5

    def lx(i):
        return pad + i * plot_w / (len(steps) - 1)

    def ly(v):
        return pad + plot_h - (v - loss_min) / (loss_max - loss_min) * plot_h

    loss_pts = " ".join(f"{lx(i):.1f},{ly(v):.1f}" for i, v in enumerate(loss_vals))
    sync_pts = " ".join(f"{lx(i):.1f},{pad + plot_h - (v - 0.5) / 0.5 * plot_h:.1f}" for i, v in enumerate(sync_vals))

    # Current metrics
    current_loss = loss_vals[-1]
    current_sync = sync_vals[-1]
    left_arm_mae  = round(0.021 + random.gauss(0, 0.003), 4)
    right_arm_mae = round(0.019 + random.gauss(0, 0.003), 4)
    coord_score   = round(current_sync * 100, 1)
    grad_norm     = round(0.18 + random.gauss(0, 0.02), 4)
    lr_current    = round(1e-4 * math.exp(-2001 / 5000), 6)
    epoch         = 14
    batch_size    = 64
    gpu_util      = random.randint(87, 96)

    # Task breakdown (bar chart)
    tasks = ["Pick-Place", "Handover", "Peg-Insert", "Fold-Cloth", "Wipe-Table"]
    task_sr = [round(0.82 + random.gauss(0, 0.05), 2) for _ in tasks]
    task_sr = [max(0.0, min(1.0, v)) for v in task_sr]

    bar_svg_w, bar_svg_h = 600, 160
    bar_pad = 40
    bar_w = (bar_svg_w - 2 * bar_pad) / len(tasks) - 8

    bars_html = ""
    colors = ["#38bdf8", "#818cf8", "#34d399", "#fb923c", "#f472b6"]
    for i, (t, sr) in enumerate(zip(tasks, task_sr)):
        bx = bar_pad + i * ((bar_svg_w - 2 * bar_pad) / len(tasks))
        bh = sr * (bar_svg_h - 2 * bar_pad)
        by = bar_pad + (bar_svg_h - 2 * bar_pad) - bh
        bars_html += f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bar_w:.1f}" height="{bh:.1f}" fill="{colors[i]}" rx="3"/>'
        bars_html += f'<text x="{bx + bar_w/2:.1f}" y="{by - 4:.1f}" fill="#e2e8f0" font-size="11" text-anchor="middle">{sr:.0%}</text>'
        bars_html += f'<text x="{bx + bar_w/2:.1f}" y="{bar_svg_h - 6:.1f}" fill="#94a3b8" font-size="10" text-anchor="middle">{t}</text>'

    return f"""<!DOCTYPE html><html><head><title>Bimanual Policy Trainer</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui,sans-serif}}
h1{{color:#C74634;margin:0;padding:20px 24px 4px;font-size:1.6rem}}
.subtitle{{color:#94a3b8;padding:0 24px 16px;font-size:0.9rem}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;padding:0 16px 16px}}
.card{{background:#1e293b;padding:18px 20px;border-radius:10px;border:1px solid #334155}}
.card h2{{color:#38bdf8;margin:0 0 10px;font-size:0.95rem;text-transform:uppercase;letter-spacing:.05em}}
.kpi{{font-size:2rem;font-weight:700;color:#f1f5f9}}
.kpi-sub{{font-size:0.78rem;color:#64748b;margin-top:2px}}
.wide{{grid-column:span 2}}
.full{{grid-column:span 4}}
svg text{{font-family:system-ui,sans-serif}}
.tag{{display:inline-block;background:#0f3460;color:#38bdf8;border-radius:4px;padding:2px 8px;font-size:0.78rem;margin-right:6px}}
</style></head>
<body>
<h1>Bimanual Policy Trainer</h1>
<p class="subtitle">GR00T N1.6 — Dual-arm coordination fine-tuning pipeline &nbsp;|&nbsp; Port {PORT}</p>

<div class="grid">
  <div class="card">
    <h2>Train Loss</h2>
    <div class="kpi">{current_loss:.4f}</div>
    <div class="kpi-sub">step 2000 / 2000 &nbsp; epoch {epoch}</div>
  </div>
  <div class="card">
    <h2>Arm Sync Score</h2>
    <div class="kpi">{coord_score:.1f}%</div>
    <div class="kpi-sub">left/right temporal alignment</div>
  </div>
  <div class="card">
    <h2>Left Arm MAE</h2>
    <div class="kpi">{left_arm_mae:.4f}</div>
    <div class="kpi-sub">joint-space rad error</div>
  </div>
  <div class="card">
    <h2>Right Arm MAE</h2>
    <div class="kpi">{right_arm_mae:.4f}</div>
    <div class="kpi-sub">joint-space rad error</div>
  </div>

  <div class="card wide">
    <h2>Training Loss Curve</h2>
    <svg width="{svg_w}" height="{svg_h}" viewBox="0 0 {svg_w} {svg_h}">
      <line x1="{pad}" y1="{pad}" x2="{pad}" y2="{pad+plot_h}" stroke="#334155" stroke-width="1"/>
      <line x1="{pad}" y1="{pad+plot_h}" x2="{pad+plot_w}" y2="{pad+plot_h}" stroke="#334155" stroke-width="1"/>
      <text x="{pad-6}" y="{pad+4}" fill="#64748b" font-size="10" text-anchor="end">{loss_max:.1f}</text>
      <text x="{pad-6}" y="{pad+plot_h}" fill="#64748b" font-size="10" text-anchor="end">{loss_min:.2f}</text>
      <text x="{pad}" y="{pad+plot_h+14}" fill="#64748b" font-size="10">0</text>
      <text x="{pad+plot_w}" y="{pad+plot_h+14}" fill="#64748b" font-size="10" text-anchor="end">2000</text>
      <polyline points="{loss_pts}" fill="none" stroke="#C74634" stroke-width="2.2" stroke-linejoin="round"/>
      <circle cx="{lx(len(steps)-1):.1f}" cy="{ly(loss_vals[-1]):.1f}" r="4" fill="#C74634"/>
    </svg>
  </div>

  <div class="card wide">
    <h2>Arm Synchrony Over Training</h2>
    <svg width="{svg_w}" height="{svg_h}" viewBox="0 0 {svg_w} {svg_h}">
      <line x1="{pad}" y1="{pad}" x2="{pad}" y2="{pad+plot_h}" stroke="#334155" stroke-width="1"/>
      <line x1="{pad}" y1="{pad+plot_h}" x2="{pad+plot_w}" y2="{pad+plot_h}" stroke="#334155" stroke-width="1"/>
      <text x="{pad-6}" y="{pad+4}" fill="#64748b" font-size="10" text-anchor="end">100%</text>
      <text x="{pad-6}" y="{pad+plot_h}" fill="#64748b" font-size="10" text-anchor="end">50%</text>
      <polyline points="{sync_pts}" fill="none" stroke="#34d399" stroke-width="2.2" stroke-linejoin="round"/>
    </svg>
  </div>

  <div class="card full">
    <h2>Per-Task Success Rate</h2>
    <svg width="{bar_svg_w}" height="{bar_svg_h}" viewBox="0 0 {bar_svg_w} {bar_svg_h}">
      {bars_html}
    </svg>
  </div>

  <div class="card">
    <h2>Gradient Norm</h2>
    <div class="kpi">{grad_norm:.4f}</div>
    <div class="kpi-sub">clipped at 1.0</div>
  </div>
  <div class="card">
    <h2>Learning Rate</h2>
    <div class="kpi" style="font-size:1.4rem">{lr_current:.2e}</div>
    <div class="kpi-sub">cosine decay</div>
  </div>
  <div class="card">
    <h2>Batch Size</h2>
    <div class="kpi">{batch_size}</div>
    <div class="kpi-sub">per GPU &nbsp;×&nbsp; 4 GPUs</div>
  </div>
  <div class="card">
    <h2>GPU Utilization</h2>
    <div class="kpi">{gpu_util}%</div>
    <div class="kpi-sub">A100 80GB SXM</div>
  </div>

  <div class="card full">
    <h2>Config</h2>
    <span class="tag">model: GR00T-N1.6</span>
    <span class="tag">arms: 2 × 7-DoF</span>
    <span class="tag">chunk_size: 16</span>
    <span class="tag">obs_horizon: 2</span>
    <span class="tag">action_dim: 14</span>
    <span class="tag">dataset: bimanual_1k_demos</span>
    <span class="tag">DDP: 4×A100</span>
    <span class="tag">amp: bf16</span>
  </div>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Bimanual Policy Trainer")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return build_html()

    @app.get("/health")
    def health():
        return {"status": "ok", "port": PORT}

    @app.get("/metrics")
    def metrics():
        random.seed()
        return {
            "port": PORT,
            "step": 2000,
            "train_loss": round(random.uniform(0.09, 0.12), 4),
            "left_arm_mae": round(random.uniform(0.018, 0.025), 4),
            "right_arm_mae": round(random.uniform(0.018, 0.025), 4),
            "sync_score": round(random.uniform(0.88, 0.94), 3),
            "gpu_util_pct": random.randint(87, 96),
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
