"""Policy Loss Landscape V2 — FastAPI port 8814"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8814

def build_html():
    random.seed(42)

    # Generate loss landscape surface data (2D grid, 20x20)
    grid_size = 20
    landscape_points = []
    for i in range(grid_size):
        for j in range(grid_size):
            x = (i - grid_size / 2) * 0.5
            y = (j - grid_size / 2) * 0.5
            # Rosenbrock-like loss with noise
            z = (1 - x)**2 + 100 * (y - x**2)**2
            z = math.log(1 + z) * 0.3 + random.gauss(0, 0.05)
            landscape_points.append((i, j, max(0, z)))

    # Training loss curves over epochs
    epochs = 80
    train_losses = []
    val_losses = []
    base = 2.5
    for ep in range(epochs):
        t = ep / epochs
        train_l = base * math.exp(-3.2 * t) + 0.08 + random.gauss(0, 0.012)
        val_l = base * math.exp(-2.8 * t) + 0.12 + 0.05 * math.sin(t * math.pi * 4) + random.gauss(0, 0.015)
        train_losses.append(max(0.05, train_l))
        val_losses.append(max(0.07, val_l))

    # Gradient norm over steps
    steps = 60
    grad_norms = []
    for s in range(steps):
        t = s / steps
        gn = 1.8 * math.exp(-2.0 * t) + 0.1 + 0.3 * abs(math.sin(t * math.pi * 6)) + random.gauss(0, 0.04)
        grad_norms.append(max(0.02, gn))

    # Hessian eigenvalue spectrum
    n_eigs = 40
    eigenvalues = sorted([abs(random.gauss(0, 1)) * math.exp(-random.random() * 2) for _ in range(n_eigs)], reverse=True)

    # SVG: Loss curves chart (600x200)
    chart_w, chart_h = 600, 200
    pad = 40
    max_loss = max(max(train_losses), max(val_losses))
    min_loss = min(min(train_losses), min(val_losses))
    loss_range = max_loss - min_loss or 1

    def lx(i): return pad + (i / (epochs - 1)) * (chart_w - 2 * pad)
    def ly(v): return chart_h - pad - ((v - min_loss) / loss_range) * (chart_h - 2 * pad)

    train_path = " ".join(f"{lx(i):.1f},{ly(v):.1f}" for i, v in enumerate(train_losses))
    val_path = " ".join(f"{lx(i):.1f},{ly(v):.1f}" for i, v in enumerate(val_losses))

    # SVG: Gradient norm chart (600x150)
    gn_w, gn_h = 600, 150
    max_gn = max(grad_norms)
    def gnx(i): return pad + (i / (steps - 1)) * (gn_w - 2 * pad)
    def gny(v): return gn_h - pad - (v / max_gn) * (gn_h - 2 * pad)
    gn_path = " ".join(f"{gnx(i):.1f},{gny(v):.1f}" for i, v in enumerate(grad_norms))

    # SVG: Eigenvalue bar chart (600x150)
    eig_w, eig_h = 600, 150
    bar_w = (eig_w - 2 * pad) / n_eigs
    max_eig = max(eigenvalues)
    eig_bars = ""
    for k, ev in enumerate(eigenvalues):
        bh = (ev / max_eig) * (eig_h - 2 * pad)
        bx = pad + k * bar_w
        by = eig_h - pad - bh
        hue = int(200 + 60 * (1 - ev / max_eig))
        eig_bars += f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bar_w * 0.8:.1f}" height="{bh:.1f}" fill="hsl({hue},70%,55%)" opacity="0.9"/>'

    # Loss landscape heatmap (SVG, 300x300)
    cell = 14
    hm_svg = ""
    max_z = max(z for _, _, z in landscape_points)
    for i, j, z in landscape_points:
        norm = z / max_z if max_z > 0 else 0
        r = int(15 + norm * 180)
        g = int(50 + (1 - norm) * 120)
        b = int(200 - norm * 100)
        hm_svg += f'<rect x="{j * cell}" y="{i * cell}" width="{cell}" height="{cell}" fill="rgb({r},{g},{b})"/>'

    # Stats
    final_train = train_losses[-1]
    final_val = val_losses[-1]
    best_val = min(val_losses)
    best_ep = val_losses.index(best_val)
    avg_gn = sum(grad_norms) / len(grad_norms)
    sharpness = sum(1 for ev in eigenvalues if ev > 0.5 * max_eig)

    return f"""<!DOCTYPE html><html><head><title>Policy Loss Landscape V2</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui,sans-serif}}
h1{{color:#C74634;padding:20px 20px 5px;margin:0;font-size:1.6rem;letter-spacing:0.5px}}
h2{{color:#38bdf8;margin:0 0 12px;font-size:1.1rem}}
.subtitle{{color:#94a3b8;padding:0 20px 16px;font-size:0.9rem}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:0}}
.card{{background:#1e293b;padding:20px;margin:10px;border-radius:8px;border:1px solid #334155}}
.card-full{{background:#1e293b;padding:20px;margin:10px;border-radius:8px;border:1px solid #334155}}
.stat-row{{display:flex;gap:12px;margin-bottom:16px;flex-wrap:wrap}}
.stat{{background:#0f172a;border-radius:6px;padding:12px 18px;border-left:3px solid #C74634}}
.stat-val{{font-size:1.5rem;font-weight:700;color:#f1f5f9}}
.stat-lbl{{font-size:0.75rem;color:#94a3b8;margin-top:2px}}
.legend{{display:flex;gap:16px;margin-bottom:8px;font-size:0.78rem}}
.leg-dot{{width:12px;height:12px;border-radius:50%;display:inline-block;margin-right:4px;vertical-align:middle}}
svg text{{font-family:system-ui,sans-serif}}
</style></head>
<body>
<h1>Policy Loss Landscape V2</h1>
<div class="subtitle">GR00T N1.5 — Training dynamics, gradient flow, and loss geometry analysis — Port {PORT}</div>

<div class="card-full">
  <div class="stat-row">
    <div class="stat"><div class="stat-val">{final_train:.4f}</div><div class="stat-lbl">Final Train Loss</div></div>
    <div class="stat"><div class="stat-val">{final_val:.4f}</div><div class="stat-lbl">Final Val Loss</div></div>
    <div class="stat"><div class="stat-val">{best_val:.4f}</div><div class="stat-lbl">Best Val Loss (ep {best_ep})</div></div>
    <div class="stat"><div class="stat-val">{avg_gn:.3f}</div><div class="stat-lbl">Avg Gradient Norm</div></div>
    <div class="stat"><div class="stat-val">{sharpness}</div><div class="stat-lbl">Sharp Hessian Dims</div></div>
  </div>
</div>

<div class="grid">
  <div class="card">
    <h2>Training &amp; Validation Loss</h2>
    <div class="legend">
      <span><span class="leg-dot" style="background:#38bdf8"></span>Train</span>
      <span><span class="leg-dot" style="background:#f59e0b"></span>Validation</span>
    </div>
    <svg width="{chart_w}" height="{chart_h}" style="overflow:visible">
      <!-- Grid lines -->
      {''.join(f'<line x1="{pad}" y1="{ly(min_loss + (loss_range * k / 4)):.1f}" x2="{chart_w - pad}" y2="{ly(min_loss + (loss_range * k / 4)):.1f}" stroke="#334155" stroke-width="1"/>' for k in range(5))}
      <!-- Axes -->
      <line x1="{pad}" y1="{pad}" x2="{pad}" y2="{chart_h - pad}" stroke="#475569" stroke-width="1.5"/>
      <line x1="{pad}" y1="{chart_h - pad}" x2="{chart_w - pad}" y2="{chart_h - pad}" stroke="#475569" stroke-width="1.5"/>
      <!-- Val loss -->
      <polyline points="{val_path}" fill="none" stroke="#f59e0b" stroke-width="2" opacity="0.85"/>
      <!-- Train loss -->
      <polyline points="{train_path}" fill="none" stroke="#38bdf8" stroke-width="2"/>
      <!-- Best val marker -->
      <circle cx="{lx(best_ep):.1f}" cy="{ly(best_val):.1f}" r="5" fill="#22c55e" stroke="#0f172a" stroke-width="1.5"/>
      <!-- Axis labels -->
      <text x="{pad}" y="{pad - 6}" fill="#94a3b8" font-size="10">Loss</text>
      <text x="{chart_w - pad}" y="{chart_h - pad + 18}" fill="#94a3b8" font-size="10" text-anchor="end">Epoch {epochs}</text>
      <text x="{pad}" y="{chart_h - pad + 18}" fill="#94a3b8" font-size="10">0</text>
    </svg>
  </div>

  <div class="card">
    <h2>Loss Landscape Heatmap (Parameter Space)</h2>
    <svg width="{grid_size * cell}" height="{grid_size * cell}" style="border-radius:4px;display:block">
      {hm_svg}
      <!-- Minimum marker -->
      <circle cx="{grid_size * cell // 2}" cy="{grid_size * cell // 2}" r="6" fill="none" stroke="#22c55e" stroke-width="2"/>
      <circle cx="{grid_size * cell // 2}" cy="{grid_size * cell // 2}" r="2" fill="#22c55e"/>
    </svg>
    <div style="font-size:0.75rem;color:#94a3b8;margin-top:8px">Blue=flat, Red=sharp. Green circle = current optimum.</div>
  </div>

  <div class="card">
    <h2>Gradient Norm vs Steps</h2>
    <svg width="{gn_w}" height="{gn_h}">
      {''.join(f'<line x1="{pad}" y1="{gny(max_gn * k / 4):.1f}" x2="{gn_w - pad}" y2="{gny(max_gn * k / 4):.1f}" stroke="#334155" stroke-width="1"/>' for k in range(5))}
      <line x1="{pad}" y1="{pad}" x2="{pad}" y2="{gn_h - pad}" stroke="#475569" stroke-width="1.5"/>
      <line x1="{pad}" y1="{gn_h - pad}" x2="{gn_w - pad}" y2="{gn_h - pad}" stroke="#475569" stroke-width="1.5"/>
      <!-- Fill area -->
      <polygon points="{pad},{gn_h - pad} {' '.join(f'{gnx(i):.1f},{gny(v):.1f}' for i, v in enumerate(grad_norms))} {gnx(steps - 1):.1f},{gn_h - pad}" fill="#C74634" opacity="0.18"/>
      <polyline points="{gn_path}" fill="none" stroke="#C74634" stroke-width="2"/>
      <!-- Clipping threshold line -->
      <line x1="{pad}" y1="{gny(max_gn * 0.4):.1f}" x2="{gn_w - pad}" y2="{gny(max_gn * 0.4):.1f}" stroke="#f59e0b" stroke-width="1" stroke-dasharray="4,3"/>
      <text x="{gn_w - pad + 3}" y="{gny(max_gn * 0.4) + 4:.1f}" fill="#f59e0b" font-size="9">clip</text>
      <text x="{pad}" y="{pad - 6}" fill="#94a3b8" font-size="10">||∇||</text>
    </svg>
  </div>

  <div class="card">
    <h2>Hessian Eigenvalue Spectrum</h2>
    <svg width="{eig_w}" height="{eig_h}">
      {eig_bars}
      <line x1="{pad}" y1="{pad}" x2="{pad}" y2="{eig_h - pad}" stroke="#475569" stroke-width="1.5"/>
      <line x1="{pad}" y1="{eig_h - pad}" x2="{eig_w - pad}" y2="{eig_h - pad}" stroke="#475569" stroke-width="1.5"/>
      <text x="{pad}" y="{pad - 6}" fill="#94a3b8" font-size="10">λ magnitude</text>
      <text x="{eig_w // 2}" y="{eig_h - 4}" fill="#94a3b8" font-size="10" text-anchor="middle">Eigenvalue rank (sharpness → flatness)</text>
    </svg>
    <div style="font-size:0.75rem;color:#94a3b8;margin-top:4px">Large eigenvalues indicate sharp loss directions. Flat minima generalize better.</div>
  </div>
</div>

<div class="card-full" style="margin:10px">
  <h2>Landscape Analysis Summary</h2>
  <p style="color:#cbd5e1;line-height:1.6;margin:0">
    Policy training converged from <strong style="color:#f1f5f9">{train_losses[0]:.3f}</strong> → <strong style="color:#38bdf8">{final_train:.4f}</strong> over {epochs} epochs.
    Validation gap: <strong style="color:#f59e0b">{final_val - final_train:.4f}</strong> (generalization margin).
    Hessian analysis reveals <strong style="color:#C74634">{sharpness} sharp directions</strong> vs {n_eigs - sharpness} flat — policy sits in a moderately sharp basin.
    Gradient clipping engaged ~{sum(1 for g in grad_norms if g > max_gn * 0.4)} of {steps} steps. Recommend SAM optimizer for flatter minima.
  </p>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Policy Loss Landscape V2")
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
