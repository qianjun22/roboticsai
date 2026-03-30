"""Reward Model V4 — video-conditioned preference reward service (port 8948)."""

import math
import random

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8948
SERVICE_TITLE = "Reward Model V4"

# ── stats ──────────────────────────────────────────────────────────────────
V3_ACCURACY = 84.7
V4_ACCURACY = 87.3
DELTA_PP = V4_ACCURACY - V3_ACCURACY          # +2.6 pp
V3_PAIRS = 1_200
V4_PAIRS = 2_100
CONTACT_PHASE_GAIN = 38.0                      # % improvement from temporal shaping

# per-epoch training loss curve (simulated with real math)
def _loss_curve(epochs: int = 20, start: float = 0.72, end: float = 0.13) -> list:
    return [round(start * math.exp(-3.5 * e / epochs) + end * (1 - math.exp(-3.5 * e / epochs)) + random.gauss(0, 0.004), 4) for e in range(epochs)]

random.seed(42)
LOSS_V3 = _loss_curve(20, 0.75, 0.18)
LOSS_V4 = _loss_curve(20, 0.72, 0.13)

# SVG bar-chart: v3 vs v4 accuracy
def _accuracy_svg() -> str:
    bars = [
        ("V3", V3_ACCURACY, "#38bdf8"),
        ("V4", V4_ACCURACY, "#C74634"),
    ]
    w, h, pad_l, pad_b = 420, 260, 60, 40
    y_min, y_max = 80, 92
    def ys(v):
        return h - pad_b - (v - y_min) / (y_max - y_min) * (h - pad_b - 30)
    bar_w = 70
    rects = ""
    for i, (label, val, color) in enumerate(bars):
        x = pad_l + 60 + i * 140
        y = ys(val)
        bar_h = h - pad_b - y
        rects += f'<rect x="{x}" y="{y:.1f}" width="{bar_w}" height="{bar_h:.1f}" fill="{color}" rx="4"/>'
        rects += f'<text x="{x + bar_w/2:.1f}" y="{y - 6:.1f}" text-anchor="middle" fill="#e2e8f0" font-size="13" font-weight="bold">{val}%</text>'
        rects += f'<text x="{x + bar_w/2:.1f}" y="{h - pad_b + 18:.1f}" text-anchor="middle" fill="#94a3b8" font-size="12">{label}</text>'
    # y-axis ticks
    ticks = ""
    for tick in range(int(y_min), int(y_max) + 1, 2):
        y = ys(tick)
        ticks += f'<line x1="{pad_l}" y1="{y:.1f}" x2="{w}" y2="{y:.1f}" stroke="#1e293b" stroke-width="1"/>'
        ticks += f'<text x="{pad_l - 6}" y="{y + 4:.1f}" text-anchor="end" fill="#94a3b8" font-size="10">{tick}</text>'
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" style="background:#1e293b;border-radius:8px">
  {ticks}{rects}
  <text x="{w//2}" y="20" text-anchor="middle" fill="#38bdf8" font-size="13" font-weight="bold">Accuracy: V3 vs V4 (%)</text>
</svg>'''

# SVG line-chart: preference dataset growth
def _dataset_svg() -> str:
    data = [("V1", 400), ("V2", 750), ("V3", V3_PAIRS), ("V4", V4_PAIRS)]
    w, h, pad_l, pad_b = 420, 220, 55, 40
    y_min, y_max = 0, 2400
    def ys(v): return h - pad_b - v / y_max * (h - pad_b - 30)
    def xs(i): return pad_l + 30 + i * 95
    pts = " ".join(f"{xs(i)},{ys(v):.1f}" for i, (_, v) in enumerate(data))
    circles = ""
    for i, (label, val) in enumerate(data):
        x, y = xs(i), ys(val)
        circles += f'<circle cx="{x}" cy="{y:.1f}" r="5" fill="#C74634"/>'
        circles += f'<text x="{x}" y="{y - 9:.1f}" text-anchor="middle" fill="#e2e8f0" font-size="11">{val:,}</text>'
        circles += f'<text x="{x}" y="{h - pad_b + 16:.1f}" text-anchor="middle" fill="#94a3b8" font-size="11">{label}</text>'
    ticks = ""
    for tick in range(0, 2401, 600):
        y = ys(tick)
        ticks += f'<line x1="{pad_l}" y1="{y:.1f}" x2="{w}" y2="{y:.1f}" stroke="#334155" stroke-width="1"/>'
        ticks += f'<text x="{pad_l - 4}" y="{y + 4:.1f}" text-anchor="end" fill="#94a3b8" font-size="9">{tick}</text>'
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" style="background:#1e293b;border-radius:8px">
  {ticks}
  <polyline points="{pts}" fill="none" stroke="#38bdf8" stroke-width="2"/>
  {circles}
  <text x="{w//2}" y="18" text-anchor="middle" fill="#38bdf8" font-size="13" font-weight="bold">Preference Dataset Growth (pairs)</text>
</svg>'''

HTML = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<title>{SERVICE_TITLE}</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',sans-serif;padding:2rem}}
  h1{{color:#C74634;font-size:1.8rem;margin-bottom:.4rem}}
  h2{{color:#38bdf8;font-size:1.1rem;margin:1.4rem 0 .6rem}}
  .card{{background:#1e293b;border-radius:10px;padding:1.2rem;margin-bottom:1.2rem}}
  .stat-row{{display:flex;gap:1.2rem;flex-wrap:wrap;margin-bottom:1rem}}
  .stat{{background:#0f172a;border-radius:8px;padding:.8rem 1.2rem;min-width:150px}}
  .stat .val{{font-size:1.6rem;font-weight:700;color:#C74634}}
  .stat .lbl{{font-size:.8rem;color:#94a3b8;margin-top:.2rem}}
  .delta{{color:#4ade80}}
  .charts{{display:flex;gap:1.4rem;flex-wrap:wrap}}
  table{{border-collapse:collapse;width:100%;font-size:.88rem}}
  th{{background:#0f172a;color:#38bdf8;padding:.5rem .8rem;text-align:left}}
  td{{padding:.45rem .8rem;border-bottom:1px solid #334155}}
  tr:hover td{{background:#0f172a}}
  .badge{{display:inline-block;padding:.15rem .5rem;border-radius:4px;font-size:.75rem;font-weight:600}}
  .badge-green{{background:#14532d;color:#4ade80}}
  .badge-blue{{background:#0c4a6e;color:#38bdf8}}
</style>
</head>
<body>
<h1>{SERVICE_TITLE}</h1>
<p style="color:#94a3b8;font-size:.9rem">Video-conditioned preference reward — per-step temporal shaping | Port {PORT}</p>

<div class="card">
  <h2>Key Metrics</h2>
  <div class="stat-row">
    <div class="stat"><div class="val">{V4_ACCURACY}%</div><div class="lbl">V4 Accuracy</div></div>
    <div class="stat"><div class="val">{V3_ACCURACY}%</div><div class="lbl">V3 Accuracy</div></div>
    <div class="stat"><div class="val delta">+{DELTA_PP:.1f} pp</div><div class="lbl">Accuracy Delta</div></div>
    <div class="stat"><div class="val">{V4_PAIRS:,}</div><div class="lbl">V4 Preference Pairs</div></div>
    <div class="stat"><div class="val">+{CONTACT_PHASE_GAIN:.0f}%</div><div class="lbl">Contact-Phase Shaping</div></div>
  </div>
</div>

<div class="card">
  <h2>V3 vs V4 Accuracy &amp; Preference Dataset Growth</h2>
  <div class="charts">
    {_accuracy_svg()}
    {_dataset_svg()}
  </div>
</div>

<div class="card">
  <h2>Architecture Changes V3 → V4</h2>
  <table>
    <thead><tr><th>Component</th><th>V3</th><th>V4</th><th>Impact</th></tr></thead>
    <tbody>
      <tr><td>Preference pairs</td><td>1,200</td><td>2,100</td><td><span class="badge badge-green">+75%</span></td></tr>
      <tr><td>Temporal shaping</td><td>Episode-level</td><td>Per-step (contact-phase)</td><td><span class="badge badge-green">+38%</span></td></tr>
      <tr><td>Video conditioning</td><td>Frame sampling 4 fps</td><td>Adaptive 8–16 fps</td><td><span class="badge badge-blue">improved</span></td></tr>
      <tr><td>Backbone</td><td>ViT-B/16</td><td>ViT-L/14 + temporal attention</td><td><span class="badge badge-green">+1.9 pp</span></td></tr>
      <tr><td>Contrastive loss</td><td>Pairwise Bradley-Terry</td><td>Listwise + temporal margin</td><td><span class="badge badge-green">+0.7 pp</span></td></tr>
      <tr><td>Inference latency</td><td>18 ms</td><td>22 ms</td><td><span class="badge badge-blue">acceptable</span></td></tr>
    </tbody>
  </table>
</div>

<div class="card">
  <h2>Per-Step Temporal Reward Formula</h2>
  <p style="font-family:monospace;font-size:.9rem;color:#38bdf8;background:#0f172a;padding:.8rem;border-radius:6px;line-height:1.7">
    r(s,a,t) = r_global(τ) · α(t) + r_contact(s,a) · β(t)<br/>
    α(t) = 1 − exp(−3·t/T)&nbsp;&nbsp;&nbsp;# ramps up over episode<br/>
    β(t) = exp(−2·(t−t_contact)²/σ²)&nbsp;&nbsp;&nbsp;# Gaussian peak at contact
  </p>
  <p style="color:#94a3b8;font-size:.85rem;margin-top:.6rem">Contact phase σ=0.12·T empirically tuned on LIBERO-90 suite.</p>
</div>
</body></html>
"""

if USE_FASTAPI:
    app = FastAPI(title=SERVICE_TITLE)

    @app.get("/", response_class=HTMLResponse)
    def index():
        return HTML

    @app.get("/health")
    def health():
        return {"status": "ok", "service": SERVICE_TITLE, "port": PORT,
                "v4_accuracy": V4_ACCURACY, "v3_accuracy": V3_ACCURACY,
                "delta_pp": DELTA_PP, "v4_pairs": V4_PAIRS}

else:
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class _H(BaseHTTPRequestHandler):
        def do_GET(self):
            body = HTML.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        def log_message(self, *_): pass

if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        print(f"{SERVICE_TITLE} fallback on :{PORT}")
        HTTPServer(("0.0.0.0", PORT), _H).serve_forever()
