"""Training Pipeline Debugger — FastAPI port 8758"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8758

def build_html():
    random.seed(42)
    # Generate training loss curve (exponential decay + noise)
    n_steps = 40
    loss_points = []
    grad_points = []
    lr_points = []
    for i in range(n_steps):
        loss = 0.8 * math.exp(-i * 0.08) + 0.05 + random.gauss(0, 0.015)
        loss = max(0.04, loss)
        grad_norm = 2.5 * math.exp(-i * 0.05) + 0.3 + random.gauss(0, 0.1)
        lr = 1e-4 * (0.95 ** (i // 5))
        loss_points.append(loss)
        grad_points.append(max(0.1, grad_norm))
        lr_points.append(lr)

    # SVG loss curve
    svg_w, svg_h = 560, 160
    pad = 30
    max_loss = max(loss_points)
    min_loss = min(loss_points)
    def lx(i): return pad + i * (svg_w - 2*pad) / (n_steps - 1)
    def ly(v): return pad + (1 - (v - min_loss) / (max_loss - min_loss + 1e-9)) * (svg_h - 2*pad)
    loss_path = " ".join(f"{lx(i):.1f},{ly(v):.1f}" for i, v in enumerate(loss_points))

    # SVG gradient norm bars
    bar_w = (svg_w - 2*pad) / n_steps - 1
    max_grad = max(grad_points)
    grad_bars = ""
    for i, g in enumerate(grad_points):
        bh = (g / max_grad) * (svg_h - 2*pad)
        bx = pad + i * (svg_w - 2*pad) / n_steps
        by = svg_h - pad - bh
        color = "#ef4444" if g > 2.0 else "#38bdf8"
        grad_bars += f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bar_w:.1f}" height="{bh:.1f}" fill="{color}" opacity="0.8"/>'

    # Stage pipeline status
    stages = [
        ("Data Loader", "ok", f"{random.randint(980,1024)} samples/s"),
        ("Augmentation", "ok", f"{random.randint(94,99)}% CPU util"),
        ("Forward Pass", "ok", f"{random.uniform(18,22):.1f}ms/batch"),
        ("Backward Pass", "warn", f"grad norm {grad_points[-1]:.3f}"),
        ("Optimizer Step", "ok", f"lr={lr_points[-1]:.2e}"),
        ("Checkpoint", "ok", "step 2000 saved"),
    ]
    stage_rows = ""
    for name, status, detail in stages:
        dot_color = "#22c55e" if status == "ok" else "#f59e0b"
        stage_rows += f"""
        <tr>
          <td style="padding:8px 12px">
            <span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:{dot_color};margin-right:8px"></span>
            {name}
          </td>
          <td style="padding:8px 12px;color:#94a3b8">{detail}</td>
        </tr>"""

    # Memory timeline (cyclic sine pattern simulating memory growth per epoch)
    mem_points = []
    for i in range(n_steps):
        mem = 14.2 + 2.1 * math.sin(i * 0.4) + i * 0.05 + random.gauss(0, 0.2)
        mem_points.append(min(24.0, max(10.0, mem)))
    max_mem = 24.0
    mem_path = " ".join(f"{lx(i):.1f},{pad + (1 - v/max_mem)*(svg_h-2*pad):.1f}" for i, v in enumerate(mem_points))

    final_loss = loss_points[-1]
    total_steps = 2000 + random.randint(0, 50)
    throughput = random.uniform(2.1, 2.4)

    return f"""<!DOCTYPE html>
<html><head><title>Training Pipeline Debugger</title>
<style>
  body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui,sans-serif}}
  h1{{color:#C74634;margin:0;padding:20px 24px 0;font-size:1.5rem;letter-spacing:.02em}}
  h2{{color:#38bdf8;font-size:1rem;margin:0 0 12px}}
  .grid{{display:grid;grid-template-columns:1fr 1fr;gap:12px;padding:16px}}
  .card{{background:#1e293b;padding:20px;border-radius:8px;border:1px solid #334155}}
  .card.wide{{grid-column:span 2}}
  .stat{{display:inline-block;margin-right:24px;margin-bottom:8px}}
  .stat .val{{font-size:1.6rem;font-weight:700;color:#f1f5f9}}
  .stat .lbl{{font-size:.75rem;color:#64748b;text-transform:uppercase;letter-spacing:.05em}}
  table{{width:100%;border-collapse:collapse}}
  tr:nth-child(even){{background:#0f172a}}
  .badge-ok{{background:#15803d;color:#bbf7d0;padding:2px 8px;border-radius:4px;font-size:.75rem}}
  .badge-warn{{background:#92400e;color:#fde68a;padding:2px 8px;border-radius:4px;font-size:.75rem}}
  svg text{{font-size:10px;fill:#64748b}}
</style></head>
<body>
<h1>Training Pipeline Debugger</h1>
<p style="color:#64748b;margin:4px 24px 0;font-size:.85rem">OCI Robot Cloud — GR00T N1.6 Fine-tune Monitor — Port {PORT}</p>

<div class="grid">
  <div class="card wide">
    <h2>Key Metrics</h2>
    <div class="stat"><div class="val">{final_loss:.4f}</div><div class="lbl">Current Loss</div></div>
    <div class="stat"><div class="val">{total_steps:,}</div><div class="lbl">Total Steps</div></div>
    <div class="stat"><div class="val">{throughput:.2f} it/s</div><div class="lbl">Throughput</div></div>
    <div class="stat"><div class="val">{lr_points[-1]:.2e}</div><div class="lbl">Learning Rate</div></div>
    <div class="stat"><div class="val">{grad_points[-1]:.3f}</div><div class="lbl">Grad Norm</div></div>
    <div class="stat"><div class="val">{mem_points[-1]:.1f} GB</div><div class="lbl">GPU Memory</div></div>
  </div>

  <div class="card">
    <h2>Training Loss Curve</h2>
    <svg width="{svg_w}" height="{svg_h}" style="display:block">
      <defs><linearGradient id="lg" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="#38bdf8" stop-opacity="0.3"/>
        <stop offset="100%" stop-color="#38bdf8" stop-opacity="0"/>
      </linearGradient></defs>
      <polyline points="{loss_path}" fill="none" stroke="#38bdf8" stroke-width="2"/>
      <polygon points="{loss_path} {lx(n_steps-1):.1f},{svg_h-pad} {lx(0):.1f},{svg_h-pad}" fill="url(#lg)"/>
      <line x1="{pad}" y1="{svg_h-pad}" x2="{svg_w-pad}" y2="{svg_h-pad}" stroke="#334155" stroke-width="1"/>
      <line x1="{pad}" y1="{pad}" x2="{pad}" y2="{svg_h-pad}" stroke="#334155" stroke-width="1"/>
      <text x="{pad}" y="{pad-4}">{max_loss:.3f}</text>
      <text x="{pad}" y="{svg_h-pad+12}">{min_loss:.3f}</text>
      <text x="{svg_w//2}" y="{svg_h-2}" text-anchor="middle">Steps (x50)</text>
    </svg>
  </div>

  <div class="card">
    <h2>Gradient Norm History</h2>
    <svg width="{svg_w}" height="{svg_h}" style="display:block">
      {grad_bars}
      <line x1="{pad}" y1="{svg_h-pad}" x2="{svg_w-pad}" y2="{svg_h-pad}" stroke="#334155" stroke-width="1"/>
      <line x1="{pad}" y1="{pad}" x2="{pad}" y2="{svg_h-pad}" stroke="#334155" stroke-width="1"/>
      <text x="{pad}" y="{pad-4}">{max_grad:.2f}</text>
      <text x="{svg_w//2}" y="{svg_h-2}" text-anchor="middle">Steps (x50) — red = grad explosion risk</text>
    </svg>
  </div>

  <div class="card">
    <h2>GPU Memory Usage (GB)</h2>
    <svg width="{svg_w}" height="{svg_h}" style="display:block">
      <defs><linearGradient id="lg2" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="#a78bfa" stop-opacity="0.4"/>
        <stop offset="100%" stop-color="#a78bfa" stop-opacity="0"/>
      </linearGradient></defs>
      <polyline points="{mem_path}" fill="none" stroke="#a78bfa" stroke-width="2"/>
      <polygon points="{mem_path} {lx(n_steps-1):.1f},{svg_h-pad} {lx(0):.1f},{svg_h-pad}" fill="url(#lg2)"/>
      <line x1="{pad}" y1="{svg_h-pad}" x2="{svg_w-pad}" y2="{svg_h-pad}" stroke="#334155" stroke-width="1"/>
      <line x1="{pad}" y1="{pad}" x2="{pad}" y2="{svg_h-pad}" stroke="#334155" stroke-width="1"/>
      <text x="{pad}" y="{pad-4}">24.0 GB</text>
      <text x="{pad}" y="{svg_h-pad+12}">0 GB</text>
      <text x="{svg_w//2}" y="{svg_h-2}" text-anchor="middle">Steps (x50)</text>
    </svg>
  </div>

  <div class="card">
    <h2>Pipeline Stage Health</h2>
    <table>
      <thead><tr>
        <th style="text-align:left;padding:8px 12px;color:#64748b;font-weight:500">Stage</th>
        <th style="text-align:left;padding:8px 12px;color:#64748b;font-weight:500">Detail</th>
      </tr></thead>
      <tbody>{stage_rows}</tbody>
    </table>
  </div>

</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Training Pipeline Debugger")
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
