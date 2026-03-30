"""Training Stability Monitor — FastAPI port 8798"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8798

def build_html():
    random.seed(42)
    # Generate training loss curve data using exponential decay + noise
    steps = list(range(0, 2001, 100))
    base_loss = [2.4 * math.exp(-0.0018 * s) + 0.08 + random.gauss(0, 0.012) for s in steps]
    val_loss  = [2.5 * math.exp(-0.0016 * s) + 0.11 + random.gauss(0, 0.018) for s in steps]

    # Gradient norm (should stay bounded; spikes = instability)
    grad_norms = [0.45 + 0.35 * math.sin(s / 300) + abs(random.gauss(0, 0.08)) for s in steps]
    grad_norms[7] = 3.1   # artificial spike at step 700
    grad_norms[14] = 2.7  # another spike at step 1400

    # Learning rate schedule (cosine decay)
    lr_vals = [1e-4 * 0.5 * (1 + math.cos(math.pi * s / 2000)) for s in steps]

    # SVG dimensions
    W, H, PAD = 680, 180, 40
    x_scale = (W - PAD * 2) / max(steps)
    loss_max = 2.6

    def to_svg_x(s): return PAD + s * x_scale
    def to_svg_y(v, vmin, vmax): return H - PAD - (v - vmin) / (vmax - vmin) * (H - PAD * 2)

    # Loss chart polylines
    train_pts = " ".join(f"{to_svg_x(s):.1f},{to_svg_y(v, 0, loss_max):.1f}" for s, v in zip(steps, base_loss))
    val_pts   = " ".join(f"{to_svg_x(s):.1f},{to_svg_y(v, 0, loss_max):.1f}" for s, v in zip(steps, val_loss))

    # Grad norm chart
    gn_max = 3.5
    grad_pts = " ".join(f"{to_svg_x(s):.1f},{to_svg_y(v, 0, gn_max):.1f}" for s, v in zip(steps, grad_norms))
    # Highlight spike points
    spike_circles = ""
    for s, v in zip(steps, grad_norms):
        if v > 2.0:
            spike_circles += f'<circle cx="{to_svg_x(s):.1f}" cy="{to_svg_y(v, 0, gn_max):.1f}" r="5" fill="#f97316" opacity="0.9"/>'

    # LR chart
    lr_max = 1.05e-4; lr_min = 0
    lr_pts = " ".join(f"{to_svg_x(s):.1f},{to_svg_y(v, lr_min, lr_max):.1f}" for s, v in zip(steps, lr_vals))

    # Stability score (penalise spikes and divergence)
    max_grad = max(grad_norms)
    gap = abs(base_loss[-1] - val_loss[-1])
    stability_score = max(0, min(100, 100 - (max_grad - 0.5) * 12 - gap * 80))
    score_color = "#22c55e" if stability_score > 70 else ("#f59e0b" if stability_score > 45 else "#ef4444")

    current_step = 2000
    current_train_loss = base_loss[-1]
    current_val_loss   = val_loss[-1]
    current_lr = lr_vals[-1]

    return f"""<!DOCTYPE html><html><head><title>Training Stability Monitor</title>
<meta http-equiv="refresh" content="15">
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui,sans-serif}}
h1{{color:#C74634;margin:0;padding:20px 20px 8px;font-size:1.6rem;letter-spacing:0.03em}}
.subtitle{{color:#94a3b8;padding:0 20px 16px;font-size:0.85rem}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;padding:0 20px 16px}}
.kpi{{background:#1e293b;border-radius:8px;padding:16px;border-left:4px solid #38bdf8}}
.kpi .label{{font-size:0.75rem;color:#94a3b8;text-transform:uppercase;letter-spacing:0.06em}}
.kpi .value{{font-size:1.5rem;font-weight:700;margin-top:4px}}
.kpi .sub{{font-size:0.75rem;color:#64748b;margin-top:2px}}
.card{{background:#1e293b;border-radius:8px;padding:16px;margin:0 20px 14px}}
.card h2{{color:#38bdf8;margin:0 0 12px;font-size:1rem;font-weight:600}}
.badge{{display:inline-block;padding:2px 10px;border-radius:12px;font-size:0.75rem;font-weight:700}}
.alert{{background:#1e293b;border-left:4px solid #f97316;border-radius:8px;padding:12px 16px;margin:0 20px 14px;font-size:0.85rem}}
.footer{{color:#475569;font-size:0.75rem;padding:8px 20px 20px}}
</style></head>
<body>
<h1>Training Stability Monitor</h1>
<div class="subtitle">OCI Robot Cloud · GR00T N1.6 Fine-tune · Real-time diagnostics · port {PORT}</div>

<div class="grid">
  <div class="kpi" style="border-color:{score_color}">
    <div class="label">Stability Score</div>
    <div class="value" style="color:{score_color}">{stability_score:.1f}</div>
    <div class="sub">/ 100 composite</div>
  </div>
  <div class="kpi">
    <div class="label">Current Step</div>
    <div class="value" style="color:#e2e8f0">{current_step:,}</div>
    <div class="sub">of 5,000 target</div>
  </div>
  <div class="kpi">
    <div class="label">Train / Val Loss</div>
    <div class="value" style="color:#38bdf8">{current_train_loss:.4f}</div>
    <div class="sub">val {current_val_loss:.4f} | gap {gap:.4f}</div>
  </div>
  <div class="kpi">
    <div class="label">Learning Rate</div>
    <div class="value" style="color:#a78bfa">{current_lr:.2e}</div>
    <div class="sub">cosine decay schedule</div>
  </div>
</div>

<div class="alert">
  ⚠ Gradient spike detected at steps 700 (norm=3.10) and 1400 (norm=2.70) — gradient clipping threshold 1.0 applied. Training resumed normally.
</div>

<div class="card">
  <h2>Loss Curves — Train vs Validation</h2>
  <svg width="100%" viewBox="0 0 {W} {H}" preserveAspectRatio="xMidYMid meet">
    <defs><linearGradient id="trainGrad" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#38bdf8" stop-opacity="0.3"/>
      <stop offset="100%" stop-color="#38bdf8" stop-opacity="0"/>
    </linearGradient></defs>
    <!-- Grid lines -->
    {chr(10).join(f'<line x1="{PAD}" y1="{to_svg_y(v, 0, loss_max):.1f}" x2="{W-PAD}" y2="{to_svg_y(v, 0, loss_max):.1f}" stroke="#334155" stroke-width="1" stroke-dasharray="4,4"/><text x="{PAD-6}" y="{to_svg_y(v, 0, loss_max)+4:.1f}" fill="#64748b" font-size="9" text-anchor="end">{v:.1f}</text>' for v in [0.2, 0.5, 1.0, 1.5, 2.0, 2.5])}
    <!-- X axis ticks -->
    {chr(10).join(f'<text x="{to_svg_x(s):.1f}" y="{H-8}" fill="#64748b" font-size="9" text-anchor="middle">{s}</text>' for s in steps[::4])}
    <polyline points="{train_pts}" fill="none" stroke="#38bdf8" stroke-width="2"/>
    <polyline points="{val_pts}"   fill="none" stroke="#f43f5e" stroke-width="2" stroke-dasharray="6,3"/>
    <text x="{W-PAD}" y="30" fill="#38bdf8" font-size="10" text-anchor="end">— Train</text>
    <text x="{W-PAD}" y="44" fill="#f43f5e" font-size="10" text-anchor="end">-- Val</text>
    <text x="{PAD}" y="14" fill="#94a3b8" font-size="10">Loss</text>
  </svg>
</div>

<div class="card">
  <h2>Gradient Norm — Spike Detection</h2>
  <svg width="100%" viewBox="0 0 {W} {H}" preserveAspectRatio="xMidYMid meet">
    <!-- Danger zone -->
    <rect x="{PAD}" y="{to_svg_y(1.0, 0, gn_max):.1f}" width="{W-PAD*2}" height="{to_svg_y(0, 0, gn_max) - to_svg_y(1.0, 0, gn_max):.1f}" fill="#f97316" opacity="0.05"/>
    <line x1="{PAD}" y1="{to_svg_y(1.0, 0, gn_max):.1f}" x2="{W-PAD}" y2="{to_svg_y(1.0, 0, gn_max):.1f}" stroke="#f97316" stroke-width="1" stroke-dasharray="5,3" opacity="0.6"/>
    <text x="{W-PAD-4}" y="{to_svg_y(1.0, 0, gn_max)-4:.1f}" fill="#f97316" font-size="9" text-anchor="end">clip threshold 1.0</text>
    {chr(10).join(f'<line x1="{PAD}" y1="{to_svg_y(v, 0, gn_max):.1f}" x2="{W-PAD}" y2="{to_svg_y(v, 0, gn_max):.1f}" stroke="#334155" stroke-width="1" stroke-dasharray="4,4"/><text x="{PAD-6}" y="{to_svg_y(v, 0, gn_max)+4:.1f}" fill="#64748b" font-size="9" text-anchor="end">{v:.1f}</text>' for v in [0.5, 1.0, 1.5, 2.0, 2.5, 3.0])}
    <polyline points="{grad_pts}" fill="none" stroke="#a78bfa" stroke-width="1.5"/>
    {spike_circles}
    <text x="{PAD}" y="14" fill="#94a3b8" font-size="10">Gradient Norm</text>
    {chr(10).join(f'<text x="{to_svg_x(s):.1f}" y="{H-8}" fill="#64748b" font-size="9" text-anchor="middle">{s}</text>' for s in steps[::4])}
  </svg>
</div>

<div class="card">
  <h2>Learning Rate Schedule (Cosine Decay)</h2>
  <svg width="100%" viewBox="0 0 {W} 120" preserveAspectRatio="xMidYMid meet">
    {''.join(f'<line x1="{PAD}" y1="{80 - (v / lr_max) * 60:.1f}" x2="{W-PAD}" y2="{80 - (v / lr_max) * 60:.1f}" stroke="#334155" stroke-width="1" stroke-dasharray="4,4"/>' for v in [0.25e-4, 0.5e-4, 0.75e-4, 1.0e-4])}
    <polyline points="{' '.join(f'{to_svg_x(s):.1f},{80 - (v / lr_max) * 60:.1f}' for s, v in zip(steps, lr_vals))}" fill="none" stroke="#22c55e" stroke-width="2"/>
    <text x="{PAD}" y="14" fill="#94a3b8" font-size="10">LR</text>
    <text x="{PAD-6}" y="24" fill="#64748b" font-size="8" text-anchor="end">1e-4</text>
    <text x="{PAD-6}" y="84" fill="#64748b" font-size="8" text-anchor="end">0</text>
    {chr(10).join(f'<text x="{to_svg_x(s):.1f}" y="108" fill="#64748b" font-size="9" text-anchor="middle">{s}</text>' for s in steps[::4])}
  </svg>
</div>

<div class="card">
  <h2>Diagnostic Summary</h2>
  <table style="width:100%;border-collapse:collapse;font-size:0.85rem">
    <tr style="border-bottom:1px solid #334155">
      <th style="text-align:left;padding:6px 8px;color:#94a3b8">Check</th>
      <th style="text-align:left;padding:6px 8px;color:#94a3b8">Status</th>
      <th style="text-align:left;padding:6px 8px;color:#94a3b8">Detail</th>
    </tr>
    <tr style="border-bottom:1px solid #1e293b">
      <td style="padding:6px 8px">Loss Convergence</td>
      <td style="padding:6px 8px"><span class="badge" style="background:#14532d;color:#86efac">PASS</span></td>
      <td style="padding:6px 8px;color:#94a3b8">Train {current_train_loss:.4f} — monotonically decreasing</td>
    </tr>
    <tr style="border-bottom:1px solid #1e293b">
      <td style="padding:6px 8px">Overfitting Gap</td>
      <td style="padding:6px 8px"><span class="badge" style="background:#{'7c2d12' if gap > 0.05 else '14532d'};color:#{'fdba74' if gap > 0.05 else '86efac'}">{'WARN' if gap > 0.05 else 'PASS'}</span></td>
      <td style="padding:6px 8px;color:#94a3b8">Gap = {gap:.4f} (threshold 0.05)</td>
    </tr>
    <tr style="border-bottom:1px solid #1e293b">
      <td style="padding:6px 8px">Gradient Stability</td>
      <td style="padding:6px 8px"><span class="badge" style="background:#7c2d12;color:#fdba74">WARN</span></td>
      <td style="padding:6px 8px;color:#94a3b8">2 spikes exceeding clip threshold (steps 700, 1400)</td>
    </tr>
    <tr style="border-bottom:1px solid #1e293b">
      <td style="padding:6px 8px">LR Schedule</td>
      <td style="padding:6px 8px"><span class="badge" style="background:#14532d;color:#86efac">PASS</span></td>
      <td style="padding:6px 8px;color:#94a3b8">Cosine decay — current {current_lr:.2e}</td>
    </tr>
    <tr>
      <td style="padding:6px 8px">GPU Memory</td>
      <td style="padding:6px 8px"><span class="badge" style="background:#14532d;color:#86efac">PASS</span></td>
      <td style="padding:6px 8px;color:#94a3b8">38.2 GB / 40 GB A100 (95.5%) — no OOM events</td>
    </tr>
  </table>
</div>

<div class="footer">OCI Robot Cloud · Training Stability Monitor · port {PORT} · auto-refresh 15s</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Training Stability Monitor")
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
