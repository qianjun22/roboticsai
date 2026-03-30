"""Policy Regularization V2 — FastAPI port 8690"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8690

def build_html():
    # Generate regularization loss curves with math/random
    steps = list(range(0, 500, 10))
    l2_losses = [2.4 * math.exp(-i/120) + random.uniform(-0.03, 0.03) for i in range(50)]
    kl_losses = [1.8 * math.exp(-i/90) + random.uniform(-0.02, 0.02) for i in range(50)]
    entropy_losses = [0.9 * (1 - math.exp(-i/60)) + random.uniform(-0.01, 0.01) for i in range(50)]

    # SVG polyline for L2, KL, Entropy
    def to_svg_points(values, x_scale=10, y_offset=140, y_scale=60):
        pts = []
        for i, v in enumerate(values):
            x = 30 + i * x_scale
            y = y_offset - v * y_scale
            pts.append(f"{x:.1f},{y:.1f}")
        return " ".join(pts)

    l2_pts = to_svg_points(l2_losses)
    kl_pts = to_svg_points(kl_losses, y_scale=50)
    ent_pts = to_svg_points(entropy_losses, y_scale=80)

    # Weight norm distribution (histogram-style bars)
    weight_bins = [random.gauss(0, 1) for _ in range(20)]
    weight_bars = ""
    for i, v in enumerate(weight_bins):
        h = max(4, int(abs(v) * 40))
        color = "#38bdf8" if v > 0 else "#f472b6"
        weight_bars += f'<rect x="{20+i*18}" y="{120-h}" width="14" height="{h}" fill="{color}" rx="2"/>'

    # Regularization coefficients table
    lambdas = {
        "L2 Weight Decay": round(random.uniform(1e-4, 5e-4), 6),
        "KL Divergence": round(random.uniform(0.001, 0.01), 5),
        "Entropy Bonus": round(random.uniform(0.005, 0.02), 4),
        "Spectral Norm": round(random.uniform(0.8, 1.2), 3),
        "Dropout Rate": round(random.uniform(0.05, 0.2), 3),
        "Grad Clip Norm": round(random.uniform(0.5, 2.0), 3),
    }
    table_rows = "".join(
        f"<tr><td style='padding:6px 12px;color:#94a3b8'>{k}</td>"
        f"<td style='padding:6px 12px;color:#34d399;font-weight:bold'>{v}</td></tr>"
        for k, v in lambdas.items()
    )

    # Policy gradient variance (sin-based noise)
    var_pts = []
    for i in range(50):
        x = 30 + i * 10
        y = 200 - (30 * math.exp(-i/40) * abs(math.sin(i * 0.4)) + random.uniform(0, 5))
        var_pts.append(f"{x:.1f},{y:.1f}")
    var_pts_str = " ".join(var_pts)

    return f"""<!DOCTYPE html><html><head><title>Policy Regularization V2</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui}}
h1{{color:#C74634;padding:20px 20px 0;margin:0}}
h2{{color:#38bdf8;margin:0 0 12px}}
.card{{background:#1e293b;padding:20px;margin:10px;border-radius:8px;display:inline-block;vertical-align:top;min-width:340px}}
.grid{{display:flex;flex-wrap:wrap}}
table{{border-collapse:collapse;width:100%}}
tr:nth-child(even){{background:#0f172a30}}
.badge{{display:inline-block;padding:2px 10px;border-radius:12px;font-size:0.78em;margin-left:6px}}
.ok{{background:#064e3b;color:#34d399}}
.warn{{background:#451a03;color:#fb923c}}
.subtitle{{color:#64748b;font-size:0.88em;padding:0 20px 16px}}
</style></head>
<body>
<h1>Policy Regularization V2 <span class="badge ok">ACTIVE</span></h1>
<div class="subtitle">Port {PORT} — Adaptive regularization scheduler for GR00T N1.6 fine-tuning</div>
<div class="grid">

<div class="card">
<h2>Loss Curves</h2>
<svg width="530" height="160" style="display:block">
  <!-- Grid lines -->
  <line x1="30" y1="20" x2="30" y2="150" stroke="#334155" stroke-width="1"/>
  <line x1="30" y1="150" x2="520" y2="150" stroke="#334155" stroke-width="1"/>
  {''.join(f'<line x1="30" y1="{y}" x2="520" y2="{y}" stroke="#1e293b" stroke-width="1"/>' for y in range(30,151,30))}
  <!-- L2 loss -->
  <polyline points="{l2_pts}" fill="none" stroke="#38bdf8" stroke-width="2"/>
  <!-- KL loss -->
  <polyline points="{kl_pts}" fill="none" stroke="#f472b6" stroke-width="2"/>
  <!-- Entropy -->
  <polyline points="{ent_pts}" fill="none" stroke="#34d399" stroke-width="2"/>
  <!-- Legend -->
  <rect x="350" y="15" width="12" height="4" fill="#38bdf8" rx="2"/><text x="366" y="21" font-size="10" fill="#94a3b8">L2</text>
  <rect x="390" y="15" width="12" height="4" fill="#f472b6" rx="2"/><text x="406" y="21" font-size="10" fill="#94a3b8">KL</text>
  <rect x="428" y="15" width="12" height="4" fill="#34d399" rx="2"/><text x="444" y="21" font-size="10" fill="#94a3b8">Entropy</text>
  <!-- Axis labels -->
  <text x="12" y="25" font-size="9" fill="#475569">2.4</text>
  <text x="12" y="85" font-size="9" fill="#475569">1.2</text>
  <text x="12" y="153" font-size="9" fill="#475569">0.0</text>
  <text x="270" y="160" font-size="9" fill="#475569">Training Steps</text>
</svg>
</div>

<div class="card">
<h2>Regularization Coefficients</h2>
<table>{table_rows}</table>
</div>

<div class="card">
<h2>Weight Norm Distribution</h2>
<svg width="390" height="130" style="display:block">
  <line x1="15" y1="120" x2="380" y2="120" stroke="#334155" stroke-width="1"/>
  {weight_bars}
  <text x="5" y="125" font-size="9" fill="#475569">Layer Weights</text>
</svg>
<div style="font-size:0.8em;color:#64748b;margin-top:4px">Blue = positive norms &nbsp; Pink = negative norms</div>
</div>

<div class="card">
<h2>Policy Gradient Variance</h2>
<svg width="530" height="220" style="display:block">
  <line x1="30" y1="20" x2="30" y2="210" stroke="#334155" stroke-width="1"/>
  <line x1="30" y1="210" x2="520" y2="210" stroke="#334155" stroke-width="1"/>
  {''.join(f'<line x1="30" y1="{y}" x2="520" y2="{y}" stroke="#1e293b" stroke-width="1"/>' for y in range(50,211,40))}
  <polyline points="{var_pts_str}" fill="none" stroke="#fb923c" stroke-width="2"/>
  <text x="200" y="218" font-size="9" fill="#475569">Steps (x10)</text>
  <text x="32" y="30" font-size="9" fill="#475569">High Variance</text>
  <text x="32" y="205" font-size="9" fill="#475569">Low Variance</text>
</svg>
</div>

</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Policy Regularization V2")
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
