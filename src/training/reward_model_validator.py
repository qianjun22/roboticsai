"""
Reward Model Validator — port 8676
OCI Robot Cloud | cycle-154B
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

import json
from datetime import datetime

# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------

def svg_accuracy_curves() -> str:
    W, H = 700, 380
    pad = {"l": 70, "r": 160, "t": 50, "b": 60}
    cw = W - pad["l"] - pad["r"]
    ch = H - pad["t"] - pad["b"]

    # steps 0-5000, accuracy 0.5-1.0
    def sx(step): return pad["l"] + (step / 5000) * cw
    def sy(acc): return pad["t"] + ch - ((acc - 0.5) / 0.5) * ch

    # v1 train: ramp fast, plateau ~0.84
    # v1 val:   ramp, plateau ~0.784
    # v2 train: ramp faster, plateau ~0.88
    # v2 val:   ramp faster, plateau ~0.821

    def curve_pts(pts):
        return " ".join(f"{sx(s):.1f},{sy(a):.1f}" for s, a in pts)

    v1_train = [(0,.50),(300,.62),(700,.71),(1200,.77),(2000,.81),(3000,.83),(4000,.84),(5000,.840)]
    v1_val   = [(0,.50),(300,.59),(700,.67),(1200,.72),(2000,.76),(3000,.77),(4000,.784),(5000,.784)]
    v2_train = [(0,.50),(300,.65),(700,.75),(1200,.81),(2000,.85),(3000,.87),(4000,.88),(5000,.880)]
    v2_val   = [(0,.50),(300,.62),(700,.72),(1200,.77),(2000,.80),(3000,.815),(4000,.821),(5000,.821)]

    # grid lines
    grid = ""
    for a in [0.5, 0.6, 0.7, 0.8, 0.9, 1.0]:
        y = sy(a)
        grid += f'<line x1="{pad["l"]}" y1="{y:.1f}" x2="{pad["l"]+cw}" y2="{y:.1f}" stroke="#1e293b" stroke-width="1"/>'
        grid += f'<text x="{pad["l"]-8}" y="{y+4:.1f}" fill="#94a3b8" font-size="11" text-anchor="end">{a:.1f}</text>'
    for s in [0, 1000, 2000, 3000, 4000, 5000]:
        x = sx(s)
        grid += f'<line x1="{x:.1f}" y1="{pad["t"]}" x2="{x:.1f}" y2="{pad["t"]+ch}" stroke="#1e293b" stroke-width="1"/>'
        grid += f'<text x="{x:.1f}" y="{pad["t"]+ch+18}" fill="#94a3b8" font-size="11" text-anchor="middle">{s}</text>'

    # annotation: plateau 82.1% val v2
    ann_x = sx(4200)
    ann_y = sy(0.821)

    # legend
    legend_x = pad["l"] + cw + 12
    legend = (
        f'<rect x="{legend_x}" y="55" width="12" height="3" fill="#38bdf8"/>'
        f'<text x="{legend_x+16}" y="62" fill="#94a3b8" font-size="10">v2 train</text>'
        f'<rect x="{legend_x}" y="75" width="12" height="3" fill="#38bdf8" stroke-dasharray="4,3" stroke="#38bdf8" fill-opacity="0.4"/>'
        f'<line x1="{legend_x}" y1="84" x2="{legend_x+12}" y2="84" stroke="#38bdf8" stroke-width="2" stroke-dasharray="4,3"/>'
        f'<text x="{legend_x+16}" y="88" fill="#94a3b8" font-size="10">v2 val</text>'
        f'<rect x="{legend_x}" y="100" width="12" height="3" fill="#C74634"/>'
        f'<text x="{legend_x+16}" y="108" fill="#94a3b8" font-size="10">v1 train</text>'
        f'<line x1="{legend_x}" y1="122" x2="{legend_x+12}" y2="122" stroke="#C74634" stroke-width="2" stroke-dasharray="4,3"/>'
        f'<text x="{legend_x+16}" y="126" fill="#94a3b8" font-size="10">v1 val</text>'
    )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#0f172a;border-radius:8px">
  <text x="{W//2}" y="28" fill="#e2e8f0" font-size="14" font-weight="bold" text-anchor="middle">Train / Val Accuracy — v1 vs v2</text>
  <text x="{W//2}" y="46" fill="#64748b" font-size="11" text-anchor="middle">Steps 0–5000</text>
  {grid}
  <!-- axes labels -->
  <text x="{pad['l']+cw//2}" y="{H-8}" fill="#94a3b8" font-size="11" text-anchor="middle">Training Steps</text>
  <text x="14" y="{pad['t']+ch//2}" fill="#94a3b8" font-size="11" text-anchor="middle" transform="rotate(-90,14,{pad['t']+ch//2})">Accuracy</text>
  <!-- v1 train -->
  <polyline points="{curve_pts(v1_train)}" fill="none" stroke="#C74634" stroke-width="2"/>
  <!-- v1 val -->
  <polyline points="{curve_pts(v1_val)}" fill="none" stroke="#C74634" stroke-width="2" stroke-dasharray="5,4"/>
  <!-- v2 train -->
  <polyline points="{curve_pts(v2_train)}" fill="none" stroke="#38bdf8" stroke-width="2.5"/>
  <!-- v2 val -->
  <polyline points="{curve_pts(v2_val)}" fill="none" stroke="#38bdf8" stroke-width="2.5" stroke-dasharray="5,4"/>
  <!-- annotation plateau 82.1% -->
  <circle cx="{ann_x:.1f}" cy="{ann_y:.1f}" r="5" fill="none" stroke="#fbbf24" stroke-width="1.5"/>
  <line x1="{ann_x+6:.1f}" y1="{ann_y-6:.1f}" x2="{ann_x+30:.1f}" y2="{ann_y-28:.1f}" stroke="#fbbf24" stroke-width="1"/>
  <text x="{ann_x+32:.1f}" y="{ann_y-30:.1f}" fill="#fbbf24" font-size="10">82.1% val (v2)</text>
  <!-- axes -->
  <line x1="{pad['l']}" y1="{pad['t']}" x2="{pad['l']}" y2="{pad['t']+ch}" stroke="#334155" stroke-width="1.5"/>
  <line x1="{pad['l']}" y1="{pad['t']+ch}" x2="{pad['l']+cw}" y2="{pad['t']+ch}" stroke="#334155" stroke-width="1.5"/>
  {legend}
</svg>"""


def svg_labeler_heatmap() -> str:
    tasks = ["pick_place", "pour", "stack", "sweep", "insert", "handover"]
    pairs = ["L1-L2", "L1-L3", "L2-L3"]
    # kappa values (tasks x pairs)
    kappa = [
        [0.94, 0.92, 0.90],
        [0.71, 0.73, 0.72],
        [0.88, 0.86, 0.87],
        [0.83, 0.81, 0.82],
        [0.85, 0.84, 0.86],
        [0.89, 0.87, 0.88],
    ]
    cell_w, cell_h = 80, 45
    lpad = 100
    tpad = 80
    W = lpad + cell_w * len(pairs) + 60
    H = tpad + cell_h * len(tasks) + 50

    def kappa_color(k):
        # low=red, high=green; map 0.65-1.0
        t = (k - 0.65) / 0.35
        t = max(0, min(1, t))
        r = int(199 * (1 - t) + 34 * t)
        g = int(70 * (1 - t) + 197 * t)
        b = int(52 * (1 - t) + 94 * t)
        return f"rgb({r},{g},{b})"

    cells = ""
    for ri, task in enumerate(tasks):
        for ci, pair in enumerate(pairs):
            k = kappa[ri][ci]
            x = lpad + ci * cell_w
            y = tpad + ri * cell_h
            cells += f'<rect x="{x}" y="{y}" width="{cell_w-2}" height="{cell_h-2}" fill="{kappa_color(k)}" rx="3"/>'
            cells += f'<text x="{x+cell_w//2-1}" y="{y+cell_h//2+5}" fill="#0f172a" font-size="12" font-weight="bold" text-anchor="middle">{k:.2f}</text>'
            # annotate pour lowest
            if task == "pour":
                cells += f'<rect x="{x-1}" y="{y-1}" width="{cell_w}" height="{cell_h}" fill="none" stroke="#fbbf24" stroke-width="2" rx="3"/>'

    # row labels
    row_labels = ""
    for ri, task in enumerate(tasks):
        y = tpad + ri * cell_h + cell_h // 2 + 5
        row_labels += f'<text x="{lpad-8}" y="{y}" fill="#94a3b8" font-size="11" text-anchor="end">{task}</text>'

    # col labels
    col_labels = ""
    for ci, pair in enumerate(pairs):
        x = lpad + ci * cell_w + cell_w // 2 - 1
        col_labels += f'<text x="{x}" y="{tpad-10}" fill="#94a3b8" font-size="11" text-anchor="middle">{pair}</text>'

    # colorbar
    cb_x = lpad + cell_w * len(pairs) + 10
    cb_items = [(0.71, "#c74622"), (0.80, "#8ab04a"), (0.94, "#22c55e")]
    cb_html = f'<text x="{cb_x+2}" y="{tpad-10}" fill="#64748b" font-size="9">k</text>'
    for i, (k, col) in enumerate(cb_items):
        yy = tpad + i * 28
        cb_html += f'<rect x="{cb_x}" y="{yy}" width="14" height="14" fill="{col}" rx="2"/>'
        cb_html += f'<text x="{cb_x+18}" y="{yy+11}" fill="#94a3b8" font-size="9">{k}</text>'

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#0f172a;border-radius:8px">
  <text x="{W//2}" y="28" fill="#e2e8f0" font-size="14" font-weight="bold" text-anchor="middle">Labeler Agreement Heatmap (Cohen's kappa)</text>
  <text x="{W//2}" y="46" fill="#64748b" font-size="11" text-anchor="middle">6 task types x 3 labeler pairs - amber border = lowest kappa (pour, 0.71)</text>
  {cells}
  {row_labels}
  {col_labels}
  {cb_html}
</svg>"""


def svg_reward_scatter() -> str:
    import math
    W, H = 560, 420
    pad = {"l": 70, "r": 40, "t": 50, "b": 60}
    cw = W - pad["l"] - pad["r"]
    ch = H - pad["t"] - pad["b"]

    # 20 episodes: (reward_model_score, actual_SR)
    episodes = [
        (0.42, 0.15), (0.48, 0.20), (0.53, 0.25), (0.58, 0.30), (0.61, 0.38),
        (0.65, 0.42), (0.68, 0.50), (0.71, 0.52), (0.74, 0.58), (0.76, 0.62),
        (0.79, 0.66), (0.81, 0.70), (0.83, 0.73), (0.85, 0.76), (0.87, 0.80),
        (0.89, 0.83), (0.91, 0.87), (0.93, 0.89), (0.95, 0.92), (0.97, 0.95),
    ]

    def sx(v): return pad["l"] + ((v - 0.35) / 0.70) * cw
    def sy(v): return pad["t"] + ch - (v / 1.0) * ch

    xs = [e[0] for e in episodes]
    ys = [e[1] for e in episodes]
    n = len(xs)
    mx = sum(xs) / n
    my = sum(ys) / n
    m = sum((xi - mx) * (yi - my) for xi, yi in zip(xs, ys)) / sum((xi - mx) ** 2 for xi in xs)
    b = my - m * mx

    x0, x1 = 0.38, 0.99
    y0_t, y1_t = m * x0 + b, m * x1 + b

    # confidence band +-0.08
    def band_poly(x0, x1, m, b, delta=0.08):
        pts_top = [(x0, m * x0 + b + delta), (x1, m * x1 + b + delta)]
        pts_bot = [(x1, m * x1 + b - delta), (x0, m * x0 + b - delta)]
        all_pts = pts_top + pts_bot
        return " ".join(f"{sx(p[0]):.1f},{sy(max(0,min(1,p[1]))):.1f}" for p in all_pts)

    grid = ""
    for v in [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]:
        y = sy(v)
        grid += f'<line x1="{pad["l"]}" y1="{y:.1f}" x2="{pad["l"]+cw}" y2="{y:.1f}" stroke="#1e293b" stroke-width="1"/>'
        grid += f'<text x="{pad["l"]-8}" y="{y+4:.1f}" fill="#94a3b8" font-size="10" text-anchor="end">{v:.1f}</text>'
    for v in [0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]:
        x = sx(v)
        grid += f'<line x1="{x:.1f}" y1="{pad["t"]}" x2="{x:.1f}" y2="{pad["t"]+ch}" stroke="#1e293b" stroke-width="1"/>'
        grid += f'<text x="{x:.1f}" y="{pad["t"]+ch+16}" fill="#94a3b8" font-size="10" text-anchor="middle">{v:.1f}</text>'

    dots = "".join(
        f'<circle cx="{sx(e[0]):.1f}" cy="{sy(e[1]):.1f}" r="5" fill="#38bdf8" fill-opacity="0.85" stroke="#0f172a" stroke-width="1"/>'
        for e in episodes
    )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#0f172a;border-radius:8px">
  <text x="{W//2}" y="28" fill="#e2e8f0" font-size="14" font-weight="bold" text-anchor="middle">Reward Score vs Actual Success Rate</text>
  <text x="{W//2}" y="46" fill="#64748b" font-size="11" text-anchor="middle">20 episodes - Pearson r = 0.87</text>
  {grid}
  <!-- confidence band -->
  <polygon points="{band_poly(x0,x1,m,b)}" fill="#38bdf8" fill-opacity="0.10"/>
  <!-- trend line -->
  <line x1="{sx(x0):.1f}" y1="{sy(y0_t):.1f}" x2="{sx(x1):.1f}" y2="{sy(y1_t):.1f}" stroke="#38bdf8" stroke-width="1.5" stroke-dasharray="6,4"/>
  {dots}
  <!-- r annotation -->
  <text x="{pad['l']+cw-4}" y="{pad['t']+20}" fill="#fbbf24" font-size="11" text-anchor="end">r = 0.87</text>
  <!-- axes -->
  <line x1="{pad['l']}" y1="{pad['t']}" x2="{pad['l']}" y2="{pad['t']+ch}" stroke="#334155" stroke-width="1.5"/>
  <line x1="{pad['l']}" y1="{pad['t']+ch}" x2="{pad['l']+cw}" y2="{pad['t']+ch}" stroke="#334155" stroke-width="1.5"/>
  <text x="{pad['l']+cw//2}" y="{H-8}" fill="#94a3b8" font-size="11" text-anchor="middle">Reward Model Score</text>
  <text x="14" y="{pad['t']+ch//2}" fill="#94a3b8" font-size="11" text-anchor="middle" transform="rotate(-90,14,{pad['t']+ch//2})">Actual Success Rate</text>
</svg>"""


# ---------------------------------------------------------------------------
# HTML page
# ---------------------------------------------------------------------------

def build_html() -> str:
    acc_svg   = svg_accuracy_curves()
    heat_svg  = svg_labeler_heatmap()
    scat_svg  = svg_reward_scatter()

    metrics = [
        ("Validation Accuracy", "82.1%", "up from 78.4% (v1)", "#22c55e"),
        ("Cohen's kappa (avg)", "0.81", "labeler agreement", "#38bdf8"),
        ("Pour Task kappa", "0.71", "needs calibration", "#fbbf24"),
        ("ECE (after temp scaling)", "0.038", "well-calibrated", "#22c55e"),
        ("Pearson r (reward vs SR)", "0.87", "strong correlation", "#38bdf8"),
        ("Service Port", "8676", "reward_model_validator", "#C74634"),
    ]

    cards = "".join(f"""
      <div style="background:#1e293b;border-radius:8px;padding:16px 20px;border-left:3px solid {c}">
        <div style="color:#64748b;font-size:11px;text-transform:uppercase;letter-spacing:.05em">{label}</div>
        <div style="color:{c};font-size:26px;font-weight:700;margin:4px 0">{val}</div>
        <div style="color:#94a3b8;font-size:12px">{sub}</div>
      </div>""" for label, val, sub, c in metrics)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Reward Model Validator - OCI Robot Cloud</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',system-ui,sans-serif;min-height:100vh}}
  header{{background:#0f172a;border-bottom:1px solid #1e293b;padding:18px 32px;display:flex;align-items:center;gap:16px}}
  header h1{{font-size:20px;font-weight:700;color:#e2e8f0}}
  header .badge{{background:#C74634;color:#fff;font-size:11px;padding:3px 10px;border-radius:12px;font-weight:600}}
  header .port{{background:#1e293b;color:#38bdf8;font-size:11px;padding:3px 10px;border-radius:12px}}
  .main{{padding:24px 32px;max-width:1200px;margin:0 auto}}
  .section-title{{color:#94a3b8;font-size:12px;text-transform:uppercase;letter-spacing:.08em;margin-bottom:12px;margin-top:28px}}
  .metrics{{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:12px;margin-bottom:8px}}
  .charts{{display:flex;flex-direction:column;gap:24px}}
  .chart-card{{background:#1e293b;border-radius:10px;padding:20px;overflow-x:auto}}
  .chart-card h3{{color:#94a3b8;font-size:12px;text-transform:uppercase;letter-spacing:.06em;margin-bottom:14px}}
  svg{{display:block;max-width:100%}}
  footer{{text-align:center;padding:20px;color:#334155;font-size:11px}}
</style>
</head>
<body>
<header>
  <h1>Reward Model Validator</h1>
  <span class="badge">OCI Robot Cloud</span>
  <span class="port">:8676</span>
  <span style="margin-left:auto;color:#64748b;font-size:12px">cycle-154B</span>
</header>
<div class="main">
  <div class="section-title">Key Metrics</div>
  <div class="metrics">{cards}</div>

  <div class="section-title">Charts</div>
  <div class="charts">
    <div class="chart-card">
      <h3>Train / Val Accuracy Curves - v1 vs v2</h3>
      {acc_svg}
    </div>
    <div class="chart-card">
      <h3>Labeler Agreement Heatmap (Cohen's kappa)</h3>
      {heat_svg}
    </div>
    <div class="chart-card">
      <h3>Reward Score vs Actual Success Rate</h3>
      {scat_svg}
    </div>
  </div>
</div>
<footer>OCI Robot Cloud - Reward Model Validator | Port 8676 | {datetime.utcnow().strftime('%Y-%m-%d')}</footer>
</body>
</html>"""


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

if USE_FASTAPI:
    app = FastAPI(title="Reward Model Validator", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return build_html()

    @app.get("/health")
    async def health():
        return JSONResponse({"status": "ok", "service": "reward_model_validator", "port": 8676})

    @app.get("/metrics")
    async def metrics():
        return JSONResponse({
            "val_accuracy": 0.821,
            "v1_val_accuracy": 0.784,
            "avg_kappa": 0.81,
            "pour_kappa": 0.71,
            "pick_place_kappa": 0.94,
            "ece": 0.038,
            "pearson_r": 0.87,
            "episodes_evaluated": 20,
        })

    if __name__ == "__main__":
        import uvicorn
        uvicorn.run(app, host="0.0.0.0", port=8676)

else:
    # stdlib fallback
    from http.server import HTTPServer, BaseHTTPRequestHandler

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a): pass
        def do_GET(self):
            if self.path == "/health":
                body = json.dumps({"status": "ok", "service": "reward_model_validator", "port": 8676}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
            else:
                body = build_html().encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    if __name__ == "__main__":
        srv = HTTPServer(("0.0.0.0", 8676), Handler)
        print("reward_model_validator listening on :8676")
        srv.serve_forever()
