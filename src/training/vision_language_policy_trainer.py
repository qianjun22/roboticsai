"""Vision-Language Policy Trainer — FastAPI port 8768"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8768

def build_html():
    random.seed(42)

    # Simulate training loss curve over 200 steps (exponential decay + noise)
    steps = list(range(0, 201, 5))
    losses = [0.95 * math.exp(-i / 80) + 0.05 + random.gauss(0, 0.008) for i in steps]
    val_losses = [l + random.uniform(0.01, 0.04) for l in losses]

    # Normalize to SVG coordinates: x in [60, 780], y in [40, 240]
    def to_svg_x(step): return 60 + (step / 200) * 720
    def to_svg_y(val, lo=0.02, hi=0.98): return 240 - ((val - lo) / (hi - lo)) * 200

    train_pts = " ".join(f"{to_svg_x(s):.1f},{to_svg_y(l):.1f}" for s, l in zip(steps, losses))
    val_pts   = " ".join(f"{to_svg_x(s):.1f},{to_svg_y(v):.1f}" for s, v in zip(steps, val_losses))

    # Action accuracy over time (sigmoid ramp)
    acc_pts = " ".join(
        f"{to_svg_x(s):.1f},{240 - (1/(1+math.exp(-(s-80)/20)))*200 + random.gauss(0,3):.1f}"
        for s in steps
    )

    # Language grounding attention heatmap (8x8 grid, cosine-based weights)
    heatmap_cells = ""
    for row in range(8):
        for col in range(8):
            val = 0.5 + 0.5 * math.cos(math.pi * row / 7) * math.cos(math.pi * col / 7)
            val += random.gauss(0, 0.06)
            val = max(0.0, min(1.0, val))
            r = int(55 + val * 180)
            g = int(30 + val * 40)
            b = int(200 - val * 140)
            x = 60 + col * 40
            y = 40 + row * 40
            heatmap_cells += f'<rect x="{x}" y="{y}" width="38" height="38" fill="rgb({r},{g},{b})" rx="3"/>'
            label = f"{val:.2f}"
            heatmap_cells += f'<text x="{x+19}" y="{y+24}" fill="white" font-size="9" text-anchor="middle">{label}</text>'

    # Modality contribution bars
    modalities = [("RGB Vision", 0.42), ("Depth Map", 0.23), ("Language Instr.", 0.21), ("Proprioception", 0.14)]
    bar_html = ""
    colors = ["#C74634", "#38bdf8", "#4ade80", "#facc15"]
    for i, (name, w) in enumerate(modalities):
        bar_html += f"""
        <div style="margin:8px 0">
          <div style="display:flex;justify-content:space-between;margin-bottom:3px">
            <span style="font-size:13px">{name}</span>
            <span style="color:#94a3b8;font-size:13px">{w*100:.0f}%</span>
          </div>
          <div style="background:#334155;border-radius:4px;height:10px">
            <div style="background:{colors[i]};width:{w*100:.0f}%;height:10px;border-radius:4px"></div>
          </div>
        </div>"""

    # Policy head stats
    current_loss = losses[-1]
    current_acc = 1 / (1 + math.exp(-(200 - 80) / 20))
    grad_norm = 0.012 + random.uniform(0, 0.008)
    lr = 3e-5 * math.exp(-200 / 300)

    return f"""<!DOCTYPE html><html><head><title>Vision-Language Policy Trainer</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui,sans-serif}}
h1{{color:#C74634;margin:20px 24px 4px;font-size:1.5rem}}
.subtitle{{color:#94a3b8;margin:0 24px 20px;font-size:0.85rem}}
h2{{color:#38bdf8;margin:0 0 12px;font-size:1rem}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;padding:0 20px 20px}}
.card{{background:#1e293b;padding:20px;border-radius:8px;border:1px solid #334155}}
.card.wide{{grid-column:span 2}}
.stat-row{{display:flex;gap:16px;padding:0 20px 16px}}
.stat{{background:#1e293b;border-radius:8px;padding:16px 24px;flex:1;border:1px solid #334155}}
.stat .val{{font-size:1.8rem;font-weight:700;color:#C74634}}
.stat .lbl{{font-size:0.75rem;color:#94a3b8;margin-top:4px}}
.badge{{display:inline-block;background:#0f3460;color:#38bdf8;border-radius:4px;padding:2px 8px;font-size:0.75rem;margin:2px}}
</style></head>
<body>
<h1>Vision-Language Policy Trainer</h1>
<div class="subtitle">GR00T N1.6 fine-tuning — OCI A100 cluster — port {PORT}</div>

<div class="stat-row">
  <div class="stat"><div class="val">{current_loss:.4f}</div><div class="lbl">Train Loss (step 200)</div></div>
  <div class="stat"><div class="val">{current_acc*100:.1f}%</div><div class="lbl">Action Accuracy</div></div>
  <div class="stat"><div class="val">{grad_norm:.4f}</div><div class="lbl">Gradient Norm</div></div>
  <div class="stat"><div class="val">{lr:.2e}</div><div class="lbl">Learning Rate</div></div>
</div>

<div class="grid">
  <div class="card">
    <h2>Training &amp; Validation Loss</h2>
    <svg width="100%" viewBox="0 0 840 280" style="overflow:visible">
      <!-- Grid lines -->
      {''.join(f'<line x1="60" y1="{40+i*50}" x2="780" y2="{40+i*50}" stroke="#334155" stroke-width="0.5"/>' for i in range(5))}
      {''.join(f'<line x1="{60+i*144}" y1="40" x2="{60+i*144}" y2="240" stroke="#334155" stroke-width="0.5"/>' for i in range(6))}
      <!-- Axes -->
      <line x1="60" y1="40" x2="60" y2="240" stroke="#475569" stroke-width="1"/>
      <line x1="60" y1="240" x2="780" y2="240" stroke="#475569" stroke-width="1"/>
      <!-- Train loss -->
      <polyline points="{train_pts}" fill="none" stroke="#C74634" stroke-width="2"/>
      <!-- Val loss -->
      <polyline points="{val_pts}" fill="none" stroke="#38bdf8" stroke-width="1.5" stroke-dasharray="6,3"/>
      <!-- Labels -->
      <text x="65" y="265" fill="#94a3b8" font-size="10">0</text>
      <text x="420" y="265" fill="#94a3b8" font-size="10">100</text>
      <text x="770" y="265" fill="#94a3b8" font-size="10">200</text>
      <text x="785" y="245" fill="#94a3b8" font-size="10">Steps</text>
      <!-- Legend -->
      <line x1="620" y1="30" x2="645" y2="30" stroke="#C74634" stroke-width="2"/>
      <text x="650" y="34" fill="#e2e8f0" font-size="11">Train</text>
      <line x1="700" y1="30" x2="725" y2="30" stroke="#38bdf8" stroke-width="1.5" stroke-dasharray="4,2"/>
      <text x="730" y="34" fill="#e2e8f0" font-size="11">Val</text>
    </svg>
  </div>

  <div class="card">
    <h2>Action Prediction Accuracy</h2>
    <svg width="100%" viewBox="0 0 840 280" style="overflow:visible">
      {''.join(f'<line x1="60" y1="{40+i*50}" x2="780" y2="{40+i*50}" stroke="#334155" stroke-width="0.5"/>' for i in range(5))}
      <line x1="60" y1="40" x2="60" y2="240" stroke="#475569" stroke-width="1"/>
      <line x1="60" y1="240" x2="780" y2="240" stroke="#475569" stroke-width="1"/>
      <polyline points="{acc_pts}" fill="none" stroke="#4ade80" stroke-width="2"/>
      <text x="65" y="265" fill="#94a3b8" font-size="10">0</text>
      <text x="420" y="265" fill="#94a3b8" font-size="10">100</text>
      <text x="770" y="265" fill="#94a3b8" font-size="10">200 steps</text>
      <text x="40" y="245" fill="#94a3b8" font-size="9">0%</text>
      <text x="40" y="145" fill="#94a3b8" font-size="9">50%</text>
      <text x="40" y="44" fill="#94a3b8" font-size="9">100%</text>
    </svg>
  </div>

  <div class="card">
    <h2>Language-Vision Attention Heatmap (8×8 tokens)</h2>
    <svg width="100%" viewBox="0 0 380 380">
      {heatmap_cells}
      <text x="190" y="375" fill="#94a3b8" font-size="11" text-anchor="middle">Vision token columns →</text>
    </svg>
  </div>

  <div class="card">
    <h2>Modality Contribution Weights</h2>
    {bar_html}
    <div style="margin-top:20px">
      <div style="color:#94a3b8;font-size:12px;margin-bottom:8px">Active model components:</div>
      <span class="badge">ViT-L/14 vision encoder</span>
      <span class="badge">LLaMA-3 8B language backbone</span>
      <span class="badge">Diffusion action head</span>
      <span class="badge">Cross-attn fusion</span>
      <span class="badge">Proprio MLP</span>
    </div>
    <div style="margin-top:16px;color:#94a3b8;font-size:12px">
      Dataset: <strong style="color:#e2e8f0">LIBERO-90 + custom SDG</strong> &nbsp;|&nbsp;
      Demos: <strong style="color:#e2e8f0">1,000</strong> &nbsp;|&nbsp;
      Context len: <strong style="color:#e2e8f0">2 frames</strong>
    </div>
  </div>
</div>
</body></html>"""


if USE_FASTAPI:
    app = FastAPI(title="Vision-Language Policy Trainer")

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
            "step": 200,
            "train_loss": round(0.95 * math.exp(-200 / 80) + 0.05 + random.gauss(0, 0.008), 6),
            "val_loss": round(0.95 * math.exp(-200 / 80) + 0.07 + random.gauss(0, 0.008), 6),
            "action_accuracy": round(1 / (1 + math.exp(-(200 - 80) / 20)), 4),
            "grad_norm": round(0.012 + random.uniform(0, 0.008), 6),
            "learning_rate": round(3e-5 * math.exp(-200 / 300), 8),
        }


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(build_html().encode())

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
