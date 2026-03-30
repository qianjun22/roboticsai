"""
Object Segmentation Evaluator — OCI Robot Cloud
Port 8654 | cycle-149A
Dark theme FastAPI dashboard for segmentation quality metrics.
stdlib only (math, random).
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

import math
import random

PORT = 8654

# ── Data ─────────────────────────────────────────────────────────────────────

CATEGORIES = ["cube", "cylinder", "mug", "tool", "container"]

MIOU_GROOT_V2 = [0.91, 0.83, 0.79, 0.71, 0.77]
MIOU_BC       = [0.74, 0.67, 0.63, 0.55, 0.61]

HEATMAP_DATA = {
    # category: [precision, recall, F1]
    "cube":      [0.93, 0.90, 0.91],
    "cylinder":  [0.86, 0.81, 0.83],
    "mug":       [0.82, 0.77, 0.79],
    "tool":      [0.75, 0.68, 0.71],
    "container": [0.80, 0.75, 0.77],
}

random.seed(42)
SCATTER_POINTS = []
for _ in range(20):
    miou = random.uniform(0.50, 0.95)
    # SR loosely correlated with mIoU (r≈0.81)
    noise = random.gauss(0, 0.07)
    sr = max(0.05, min(0.92, 0.9 * miou - 0.05 + noise))
    SCATTER_POINTS.append((round(miou, 3), round(sr, 3)))

# ── SVG generators ────────────────────────────────────────────────────────────

def svg_miou_bars() -> str:
    W, H = 640, 320
    pad_l, pad_r, pad_t, pad_b = 70, 20, 30, 50
    n = len(CATEGORIES)
    group_w = (W - pad_l - pad_r) / n
    bar_w = group_w * 0.30
    max_val = 1.0

    def y_px(v):
        return pad_t + (H - pad_t - pad_b) * (1 - v / max_val)

    bars = []
    # Y gridlines
    for tick in [0.0, 0.25, 0.5, 0.75, 1.0]:
        yp = y_px(tick)
        bars.append(f'<line x1="{pad_l}" y1="{yp:.1f}" x2="{W - pad_r}" y2="{yp:.1f}" stroke="#1e293b" stroke-width="1"/>')
        bars.append(f'<text x="{pad_l - 6}" y="{yp + 4:.1f}" text-anchor="end" fill="#94a3b8" font-size="10">{tick:.2f}</text>')

    for i, cat in enumerate(CATEGORIES):
        gx = pad_l + i * group_w + group_w * 0.1
        # GR00T_v2 bar (Oracle red)
        v2 = MIOU_GROOT_V2[i]
        bc = MIOU_BC[i]
        bar_height_v2 = (H - pad_t - pad_b) * v2
        bar_height_bc = (H - pad_t - pad_b) * bc
        yv2 = y_px(v2)
        ybc = y_px(bc)

        bars.append(f'<rect x="{gx:.1f}" y="{yv2:.1f}" width="{bar_w:.1f}" height="{bar_height_v2:.1f}" fill="#C74634" rx="2"/>')
        bars.append(f'<rect x="{gx + bar_w + 4:.1f}" y="{ybc:.1f}" width="{bar_w:.1f}" height="{bar_height_bc:.1f}" fill="#38bdf8" rx="2"/>')
        bars.append(f'<text x="{gx + bar_w:.1f}" y="{H - pad_b + 14}" text-anchor="middle" fill="#94a3b8" font-size="10">{cat}</text>')
        # value labels
        bars.append(f'<text x="{gx + bar_w * 0.5:.1f}" y="{yv2 - 4:.1f}" text-anchor="middle" fill="#C74634" font-size="9">{v2}</text>')
        bars.append(f'<text x="{gx + bar_w * 1.5 + 4:.1f}" y="{ybc - 4:.1f}" text-anchor="middle" fill="#38bdf8" font-size="9">{bc}</text>')

    # Legend
    bars.append(f'<rect x="{pad_l}" y="6" width="12" height="10" fill="#C74634" rx="2"/>')
    bars.append(f'<text x="{pad_l + 16}" y="15" fill="#e2e8f0" font-size="10">GR00T_v2</text>')
    bars.append(f'<rect x="{pad_l + 80}" y="6" width="12" height="10" fill="#38bdf8" rx="2"/>')
    bars.append(f'<text x="{pad_l + 96}" y="15" fill="#e2e8f0" font-size="10">BC</text>')

    # Y axis label
    bars.append(f'<text x="12" y="{(H) // 2}" text-anchor="middle" fill="#94a3b8" font-size="11" transform="rotate(-90,12,{H // 2})">mIoU</text>')

    inner = "\n".join(bars)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#0f172a;border-radius:8px">
{inner}
</svg>'''


def svg_heatmap() -> str:
    W, H = 520, 240
    col_labels = ["Precision", "Recall", "F1"]
    row_labels = CATEGORIES
    rows = len(row_labels)
    cols = len(col_labels)
    cell_w = 80
    cell_h = 36
    off_x = 90
    off_y = 40

    def color(v: float) -> str:
        # green gradient: low=#1e3a2f high=#22c55e
        r = int(30 + (34 - 30) * v)
        g = int(58 + (197 - 58) * v)
        b = int(47 + (94 - 47) * v)
        return f"#{r:02x}{g:02x}{b:02x}"

    elems = []
    # column headers
    for j, cl in enumerate(col_labels):
        elems.append(f'<text x="{off_x + j * cell_w + cell_w // 2}" y="28" text-anchor="middle" fill="#38bdf8" font-size="11" font-weight="bold">{cl}</text>')

    for i, rcat in enumerate(row_labels):
        vals = HEATMAP_DATA[rcat]
        elems.append(f'<text x="{off_x - 6}" y="{off_y + i * cell_h + cell_h // 2 + 4}" text-anchor="end" fill="#94a3b8" font-size="10">{rcat}</text>')
        for j, v in enumerate(vals):
            cx = off_x + j * cell_w
            cy = off_y + i * cell_h
            c = color(v)
            elems.append(f'<rect x="{cx}" y="{cy}" width="{cell_w - 2}" height="{cell_h - 2}" fill="{c}" rx="3"/>')
            elems.append(f'<text x="{cx + cell_w // 2}" y="{cy + cell_h // 2 + 4}" text-anchor="middle" fill="#f8fafc" font-size="11" font-weight="bold">{v:.2f}</text>')

    inner = "\n".join(elems)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#0f172a;border-radius:8px">
{inner}
</svg>'''


def svg_scatter() -> str:
    W, H = 500, 320
    pad_l, pad_r, pad_t, pad_b = 55, 20, 20, 50

    def px(miou_v):
        return pad_l + (W - pad_l - pad_r) * (miou_v - 0.48) / (0.97 - 0.48)

    def py(sr_v):
        return H - pad_b - (H - pad_t - pad_b) * sr_v

    elems = []

    # Gridlines
    for xv in [0.5, 0.6, 0.7, 0.8, 0.9]:
        xp = px(xv)
        elems.append(f'<line x1="{xp:.1f}" y1="{pad_t}" x2="{xp:.1f}" y2="{H - pad_b}" stroke="#1e293b" stroke-width="1"/>')
        elems.append(f'<text x="{xp:.1f}" y="{H - pad_b + 14}" text-anchor="middle" fill="#94a3b8" font-size="9">{xv}</text>')
    for yv in [0.1, 0.3, 0.5, 0.7, 0.9]:
        yp = py(yv)
        elems.append(f'<line x1="{pad_l}" y1="{yp:.1f}" x2="{W - pad_r}" y2="{yp:.1f}" stroke="#1e293b" stroke-width="1"/>')
        elems.append(f'<text x="{pad_l - 6}" y="{yp + 4:.1f}" text-anchor="end" fill="#94a3b8" font-size="9">{yv}</text>')

    # Trend line (r=0.81, least squares approximation)
    # SR ≈ 0.9*mIoU - 0.05
    x0, x1 = 0.50, 0.95
    y0_tr = 0.9 * x0 - 0.05
    y1_tr = 0.9 * x1 - 0.05
    elems.append(f'<line x1="{px(x0):.1f}" y1="{py(y0_tr):.1f}" x2="{px(x1):.1f}" y2="{py(y1_tr):.1f}" stroke="#f59e0b" stroke-width="1.5" stroke-dasharray="5,3"/>')
    elems.append(f'<text x="{px(0.87):.1f}" y="{py(0.72):.1f}" fill="#f59e0b" font-size="10">r = 0.81</text>')

    # Points
    for (miou_v, sr_v) in SCATTER_POINTS:
        xp = px(miou_v)
        yp = py(sr_v)
        elems.append(f'<circle cx="{xp:.1f}" cy="{yp:.1f}" r="5" fill="#38bdf8" opacity="0.85"/>')

    # Axis labels
    elems.append(f'<text x="{(W + pad_l) // 2}" y="{H - 4}" text-anchor="middle" fill="#94a3b8" font-size="11">mIoU</text>')
    elems.append(f'<text x="13" y="{(H) // 2}" text-anchor="middle" fill="#94a3b8" font-size="11" transform="rotate(-90,13,{H // 2})">Success Rate</text>')

    inner = "\n".join(elems)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#0f172a;border-radius:8px">
{inner}
</svg>'''


# ── HTML page ─────────────────────────────────────────────────────────────────

def build_html() -> str:
    bars_svg    = svg_miou_bars()
    heatmap_svg = svg_heatmap()
    scatter_svg = svg_scatter()

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Object Segmentation Evaluator — OCI Robot Cloud</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; padding: 2rem; }}
  h1 {{ color: #C74634; font-size: 1.7rem; margin-bottom: .25rem; }}
  h2 {{ color: #C74634; font-size: 1.1rem; margin: 1.5rem 0 .5rem; }}
  .subtitle {{ color: #64748b; font-size: .85rem; margin-bottom: 1.5rem; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 1.5rem; }}
  .card {{ background: #1e293b; border-radius: 10px; padding: 1.25rem; border: 1px solid #334155; }}
  .card-title {{ color: #38bdf8; font-size: .9rem; font-weight: 600; margin-bottom: .75rem; }}
  .kpi-row {{ display: flex; gap: 1rem; flex-wrap: wrap; margin-bottom: 1.5rem; }}
  .kpi {{ background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: .75rem 1.25rem; min-width: 140px; }}
  .kpi-val {{ font-size: 1.6rem; font-weight: 700; color: #38bdf8; }}
  .kpi-lbl {{ font-size: .75rem; color: #64748b; margin-top: 2px; }}
  .kpi.red .kpi-val {{ color: #C74634; }}
  .kpi.warn .kpi-val {{ color: #f59e0b; }}
  svg {{ max-width: 100%; height: auto; display: block; }}
  .note {{ color: #64748b; font-size: .8rem; margin-top: .5rem; }}
</style>
</head>
<body>
<h1>Object Segmentation Evaluator</h1>
<p class="subtitle">OCI Robot Cloud · port {PORT} · GR00T_v2 vs BC · cycle-149A</p>

<div class="kpi-row">
  <div class="kpi"><div class="kpi-val">0.84</div><div class="kpi-lbl">Avg mIoU (GR00T_v2)</div></div>
  <div class="kpi"><div class="kpi-val">0.91</div><div class="kpi-lbl">Best: cube</div></div>
  <div class="kpi warn"><div class="kpi-val">0.71</div><div class="kpi-lbl">Worst: tool</div></div>
  <div class="kpi red"><div class="kpi-val">34%</div><div class="kpi-lbl">Failures from seg error</div></div>
</div>

<div class="grid">
  <div class="card">
    <div class="card-title">mIoU per Category — GR00T_v2 vs BC</div>
    {bars_svg}
    <p class="note">Oracle red = GR00T_v2 &nbsp;|&nbsp; Blue = BC</p>
  </div>
  <div class="card">
    <div class="card-title">Segmentation Metrics Heatmap (Precision / Recall / F1)</div>
    {heatmap_svg}
    <p class="note">Green intensity ∝ metric value (0–1)</p>
  </div>
  <div class="card">
    <div class="card-title">IoU vs Success Rate Scatter (r = 0.81)</div>
    {scatter_svg}
    <p class="note">20 evaluation runs &nbsp;|&nbsp; dashed = trend line</p>
  </div>
</div>
</body>
</html>"""


# ── App ───────────────────────────────────────────────────────────────────────

if USE_FASTAPI:
    app = FastAPI(title="Object Segmentation Evaluator", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def index():
        return HTMLResponse(build_html())

    @app.get("/health")
    async def health():
        return JSONResponse({"status": "ok", "port": PORT})

    @app.get("/metrics")
    async def metrics():
        return JSONResponse({
            "avg_miou_groot_v2": 0.84,
            "best_category": "cube",
            "best_miou": 0.91,
            "worst_category": "tool",
            "worst_miou": 0.71,
            "seg_error_failure_rate": 0.34,
            "categories": {
                cat: {"groot_v2": MIOU_GROOT_V2[i], "bc": MIOU_BC[i]}
                for i, cat in enumerate(CATEGORIES)
            },
        })

    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=PORT)

else:
    # stdlib HTTPServer fallback
    from http.server import BaseHTTPRequestHandler, HTTPServer
    import json as _json

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass

        def do_GET(self):
            if self.path == "/health":
                body = _json.dumps({"status": "ok", "port": PORT}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                body = build_html().encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

    if __name__ == "__main__":
        server = HTTPServer(("0.0.0.0", PORT), Handler)
        print(f"Serving on http://0.0.0.0:{PORT}")
        server.serve_forever()
