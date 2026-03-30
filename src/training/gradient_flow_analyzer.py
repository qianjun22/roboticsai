"""Gradient Flow Analyzer — FastAPI port 8718"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8718

LAYER_NAMES = [
    "embed", "attn_0", "ffn_0", "attn_1", "ffn_1",
    "attn_2", "ffn_2", "attn_3", "ffn_3", "head"
]

def build_html():
    random.seed(42)
    # Simulate gradient norms per layer (exponential decay + noise)
    norms = []
    for i, name in enumerate(LAYER_NAMES):
        base = math.exp(-i * 0.18) * 2.4 + 0.05
        noise = random.gauss(0, 0.08)
        norms.append(max(0.01, base + noise))

    # Gradient variance (higher in early layers)
    variances = [max(0.001, n * random.uniform(0.3, 0.7)) for n in norms]

    # SVG bar chart — gradient norms
    bar_w = 44
    bar_gap = 8
    chart_h = 160
    max_norm = max(norms)
    bars_svg = ""
    labels_svg = ""
    for i, (name, norm) in enumerate(zip(LAYER_NAMES, norms)):
        x = 40 + i * (bar_w + bar_gap)
        bar_h = int((norm / max_norm) * (chart_h - 20))
        y = chart_h - bar_h
        # Color: green→yellow→red by gradient magnitude
        ratio = norm / max_norm
        r = int(min(255, ratio * 510))
        g = int(min(255, (1 - ratio) * 510))
        bars_svg += f'<rect x="{x}" y="{y}" width="{bar_w}" height="{bar_h}" fill="rgb({r},{g},60)" rx="3"/>'
        bars_svg += f'<text x="{x + bar_w//2}" y="{y - 4}" fill="#e2e8f0" font-size="9" text-anchor="middle">{norm:.3f}</text>'
        labels_svg += f'<text x="{x + bar_w//2}" y="{chart_h + 14}" fill="#94a3b8" font-size="8" text-anchor="middle">{name}</text>'

    # SVG line chart — gradient flow over training steps
    steps = 60
    step_w = 8
    line_h = 120
    points = []
    val = 1.0
    for s in range(steps):
        val = val * random.uniform(0.97, 1.03) - 0.002
        val = max(0.01, min(2.0, val))
        px = 40 + s * step_w
        py = line_h - int((val / 2.0) * (line_h - 10)) + 10
        points.append(f"{px},{py}")
    polyline = " ".join(points)

    # Vanishing/exploding gradient detection
    vanishing = [name for name, n in zip(LAYER_NAMES, norms) if n < 0.05]
    exploding = [name for name, n in zip(LAYER_NAMES, norms) if n > 1.5]
    health_color = "#22c55e" if not vanishing and not exploding else "#ef4444"
    health_label = "Healthy" if not vanishing and not exploding else "Issues Detected"

    total_params = 1_247_832
    mean_norm = sum(norms) / len(norms)
    grad_ratio = max(norms) / (min(norms) + 1e-9)

    chart_svg_width = 40 + len(LAYER_NAMES) * (bar_w + bar_gap) + 20
    line_svg_width = 40 + steps * step_w + 20

    return f"""<!DOCTYPE html><html><head><title>Gradient Flow Analyzer</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui;padding:20px}}
h1{{color:#C74634;margin:0 0 4px 0;font-size:1.6rem}}
h2{{color:#38bdf8;font-size:1rem;margin:0 0 12px 0}}
h3{{color:#94a3b8;font-size:0.85rem;margin:0 0 8px 0;text-transform:uppercase;letter-spacing:.05em}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:12px}}
.card{{background:#1e293b;padding:20px;border-radius:8px}}
.card.wide{{grid-column:1/-1}}
.stat{{display:inline-block;margin:8px 16px 8px 0}}
.stat .val{{font-size:1.5rem;font-weight:700;color:#f8fafc}}
.stat .lbl{{font-size:0.72rem;color:#64748b;text-transform:uppercase}}
.badge{{display:inline-block;padding:3px 10px;border-radius:99px;font-size:0.8rem;font-weight:600}}
.warn{{background:#451a03;color:#fb923c}}
svg{{overflow:visible}}
</style></head>
<body>
<h1>Gradient Flow Analyzer</h1>
<h2>OCI Robot Cloud — Training Health Dashboard &nbsp; <span class="badge" style="background:#052e16;color:{health_color}">{health_label}</span></h2>

<div class="grid">
  <div class="card">
    <h3>Summary Statistics</h3>
    <span class="stat"><div class="val">{mean_norm:.4f}</div><div class="lbl">Mean Grad Norm</div></span>
    <span class="stat"><div class="val">{grad_ratio:.1f}×</div><div class="lbl">Max/Min Ratio</div></span>
    <span class="stat"><div class="val">{total_params:,}</div><div class="lbl">Total Params</div></span>
    <span class="stat"><div class="val">{len(vanishing)}</div><div class="lbl">Vanishing Layers</div></span>
    <span class="stat"><div class="val">{len(exploding)}</div><div class="lbl">Exploding Layers</div></span>
  </div>
  <div class="card">
    <h3>Layer Health</h3>
    {''.join(f'<div style="display:flex;align-items:center;margin:4px 0"><span style="width:80px;font-size:0.8rem;color:#94a3b8">{n}</span><div style="flex:1;background:#0f172a;border-radius:4px;height:10px"><div style="width:{int(v/max_norm*100)}%;height:10px;border-radius:4px;background:hsl({int((1-v/max_norm)*120)},70%,45%)"></div></div><span style="width:50px;text-align:right;font-size:0.75rem;color:#cbd5e1">{v:.4f}</span></div>' for n, v in zip(LAYER_NAMES, norms))}
  </div>

  <div class="card wide">
    <h3>Gradient Norms per Layer</h3>
    <svg width="{chart_svg_width}" height="{chart_h + 30}">
      <line x1="30" y1="{chart_h}" x2="{chart_svg_width}" y2="{chart_h}" stroke="#334155" stroke-width="1"/>
      {bars_svg}
      {labels_svg}
    </svg>
  </div>

  <div class="card wide">
    <h3>Global Gradient Norm — Training Steps (last 60)</h3>
    <svg width="{line_svg_width}" height="{line_h + 30}">
      <line x1="30" y1="{line_h + 10}" x2="{line_svg_width}" y2="{line_h + 10}" stroke="#334155" stroke-width="1"/>
      <polyline points="{polyline}" fill="none" stroke="#38bdf8" stroke-width="2"/>
      <line x1="40" y1="{int(line_h - (0.05/2.0)*(line_h-10)) + 10}" x2="{line_svg_width - 10}" y2="{int(line_h - (0.05/2.0)*(line_h-10)) + 10}" stroke="#ef4444" stroke-width="1" stroke-dasharray="4,3"/>
      <text x="{line_svg_width - 8}" y="{int(line_h - (0.05/2.0)*(line_h-10)) + 14}" fill="#ef4444" font-size="8">vanish</text>
    </svg>
  </div>
</div>

<div style="font-size:0.72rem;color:#475569;margin-top:8px">Port {PORT} — Updated every 30s — Model: GR00T-N1.6 fine-tune</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Gradient Flow Analyzer")

    @app.get("/", response_class=HTMLResponse)
    def index(): return build_html()

    @app.get("/health")
    def health(): return {"status": "ok", "port": PORT}

    @app.get("/metrics")
    def metrics():
        random.seed(None)
        norms = {name: round(max(0.01, math.exp(-i * 0.18) * 2.4 + random.gauss(0, 0.08)), 4)
                 for i, name in enumerate(LAYER_NAMES)}
        return {"port": PORT, "layer_norms": norms, "mean": round(sum(norms.values()) / len(norms), 4)}

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
