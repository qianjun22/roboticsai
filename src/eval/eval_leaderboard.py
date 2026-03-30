"""Eval Leaderboard — port 8235
Public-facing leaderboard of GR00T policy performance across OCI Robot Cloud customers.
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

import math
import random

# ---------------------------------------------------------------------------
# Mock leaderboard data
# ---------------------------------------------------------------------------

random.seed(42)

EMBODIMENT_COLORS = {
    "Franka": "#38bdf8",
    "UR5":    "#a78bfa",
    "xArm":  "#fb923c",
    "Stretch": "#4ade80",
}

LEADERBOARD = [
    {"rank": 1,  "model": "PI_custom_v3",     "customer": "Customer-A", "sr": 0.83, "demos": 2400, "embodiment": "Franka", "cost_usd": 210,  "production": False},
    {"rank": 2,  "model": "OCI_prod",          "customer": "OCI-Platform", "sr": 0.78, "demos": 1000, "embodiment": "Franka", "cost_usd": 87,   "production": True},
    {"rank": 3,  "model": "UR5_scaleup_v2",    "customer": "Customer-B", "sr": 0.76, "demos": 1800, "embodiment": "UR5",    "cost_usd": 155,  "production": False},
    {"rank": 4,  "model": "xArm_enterprise",   "customer": "Customer-C", "sr": 0.74, "demos": 3200, "embodiment": "xArm",  "cost_usd": 290,  "production": False},
    {"rank": 5,  "model": "Covariant_pilot",   "customer": "Customer-D", "sr": 0.72, "demos": 950,  "embodiment": "Stretch","cost_usd": 80,   "production": False},
    {"rank": 6,  "model": "Franka_v1_baseline","customer": "Customer-E", "sr": 0.69, "demos": 600,  "embodiment": "Franka", "cost_usd": 55,   "production": False},
    {"rank": 7,  "model": "UR5_startup_r3",    "customer": "Customer-F", "sr": 0.65, "demos": 400,  "embodiment": "UR5",    "cost_usd": 38,   "production": False},
    {"rank": 8,  "model": "xArm_draft",        "customer": "Customer-G", "sr": 0.61, "demos": 280,  "embodiment": "xArm",  "cost_usd": 27,   "production": False},
    {"rank": 9,  "model": "Stretch_v0.9",      "customer": "Customer-H", "sr": 0.57, "demos": 180,  "embodiment": "Stretch","cost_usd": 19,   "production": False},
    {"rank": 10, "model": "GR00T_default",     "customer": "OCI-Platform", "sr": 0.52, "demos": 100,  "embodiment": "Franka", "cost_usd": 9,    "production": False},
]

# Additional scatter-only models (not in top-10 bar chart)
SCATTER_EXTRA = [
    {"model": "UR5_exp1",   "sr": 0.48, "demos": 70,   "embodiment": "UR5",    "cost_usd": 7},
    {"model": "xArm_test",  "sr": 0.44, "demos": 50,   "embodiment": "xArm",  "cost_usd": 5},
    {"model": "Stretch_v1", "sr": 0.68, "demos": 1200, "embodiment": "Stretch","cost_usd": 98},
    {"model": "UR5_v3",     "sr": 0.71, "demos": 1500, "embodiment": "UR5",    "cost_usd": 130},
    {"model": "xArm_v4",   "sr": 0.77, "demos": 2800, "embodiment": "xArm",  "cost_usd": 250},
]

AVG_SR = round(sum(m["sr"] for m in LEADERBOARD) / len(LEADERBOARD), 3)
SOTA_SR = 0.83

# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------

def _bar_chart_svg() -> str:
    """Horizontal bar chart of top-10 models by SR."""
    W, H = 580, 360
    pad_l, pad_r, pad_t, pad_b = 160, 80, 40, 20
    chart_w = W - pad_l - pad_r
    chart_h = H - pad_t - pad_b
    bar_h = chart_h / len(LEADERBOARD) * 0.65
    row_h = chart_h / len(LEADERBOARD)

    bars = ""
    for i, m in enumerate(LEADERBOARD):
        y = pad_t + i * row_h + (row_h - bar_h) / 2
        bw = m["sr"] * chart_w / 1.0   # max sr ~0.83, scale to chart_w
        color = "#C74634" if m["production"] else EMBODIMENT_COLORS.get(m["embodiment"], "#38bdf8")
        bars += f'<rect x="{pad_l}" y="{y:.1f}" width="{bw:.1f}" height="{bar_h:.1f}" fill="{color}" rx="2"/>'
        # SR label
        bars += (f'<text x="{pad_l + bw + 5:.1f}" y="{y + bar_h*0.7:.1f}" '
                 f'fill="#f1f5f9" font-size="10" font-weight="600">{m["sr"]:.2f}</text>')
        # demos
        bars += (f'<text x="{W - pad_r + 2:.1f}" y="{y + bar_h*0.7:.1f}" '
                 f'fill="#64748b" font-size="8">{m["demos"]}d</text>')
        # model name
        prod_star = " ★" if m["production"] else ""
        bars += (f'<text x="{pad_l - 4:.1f}" y="{y + bar_h*0.7:.1f}" '
                 f'fill="{color}" font-size="9" text-anchor="end">{m["model"]}{prod_star}</text>')

    # x-axis ticks
    ticks = ""
    for v in [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]:
        tx = pad_l + v * chart_w
        ticks += f'<line x1="{tx:.1f}" y1="{pad_t}" x2="{tx:.1f}" y2="{pad_t+chart_h}" stroke="#334155" stroke-width="0.5"/>'
        ticks += f'<text x="{tx:.1f}" y="{pad_t+chart_h+12:.1f}" fill="#64748b" font-size="8" text-anchor="middle">{v:.1f}</text>'

    return (f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:{W}px">'
            f'<rect width="{W}" height="{H}" fill="#1e293b" rx="8"/>'
            f'<text x="{W//2}" y="22" fill="#f1f5f9" font-size="13" font-weight="bold" text-anchor="middle">'
            f'Top-10 Models by Success Rate</text>'
            f'<text x="{W//2}" y="36" fill="#64748b" font-size="9" text-anchor="middle">'
            f'&#9733; = PRODUCTION model (Oracle Red)</text>'
            f'{ticks}{bars}</svg>')


def _scatter_svg() -> str:
    """Scatter plot: SR vs fine-tuning cost, Pareto frontier, colored by embodiment."""
    W, H = 520, 340
    pad_l, pad_r, pad_t, pad_b = 50, 30, 40, 50
    chart_w = W - pad_l - pad_r
    chart_h = H - pad_t - pad_b

    all_models = LEADERBOARD + [{**e, "production": False, "rank": 99, "customer": ""} for e in SCATTER_EXTRA]

    max_cost = max(m["cost_usd"] for m in all_models)
    max_demos = max(m["demos"] for m in all_models)

    def px(cost):
        return pad_l + cost / max_cost * chart_w

    def py(sr):
        return pad_t + chart_h - (sr - 0.3) / 0.6 * chart_h

    # grid
    grid = ""
    for sr_tick in [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]:
        gy = py(sr_tick)
        grid += f'<line x1="{pad_l}" y1="{gy:.1f}" x2="{W-pad_r}" y2="{gy:.1f}" stroke="#1e3a5f" stroke-width="0.8"/>'
        grid += f'<text x="{pad_l-4:.1f}" y="{gy+3:.1f}" fill="#64748b" font-size="8" text-anchor="end">{sr_tick:.1f}</text>'
    for c_tick in [0, 50, 100, 150, 200, 250, 300]:
        gx = px(c_tick)
        grid += f'<line x1="{gx:.1f}" y1="{pad_t}" x2="{gx:.1f}" y2="{pad_t+chart_h}" stroke="#1e3a5f" stroke-width="0.8"/>'
        grid += f'<text x="{gx:.1f}" y="{pad_t+chart_h+12:.1f}" fill="#64748b" font-size="7" text-anchor="middle">${c_tick}</text>'

    # Pareto frontier (dominant models: highest SR for given cost)
    sorted_by_cost = sorted(all_models, key=lambda m: m["cost_usd"])
    pareto = []
    best_sr = 0.0
    for m in sorted_by_cost:
        if m["sr"] > best_sr:
            best_sr = m["sr"]
            pareto.append(m)
    pareto_pts = " ".join(f"{px(m['cost_usd']):.1f},{py(m['sr']):.1f}" for m in pareto)
    pareto_line = f'<polyline points="{pareto_pts}" fill="none" stroke="#22c55e" stroke-width="1.5" stroke-dasharray="5,3"/>'
    pareto_lbl = (f'<text x="{px(pareto[-1]["cost_usd"])+4:.1f}" y="{py(pareto[-1]["sr"])-5:.1f}" '
                  f'fill="#22c55e" font-size="8">Pareto</text>')

    # dots
    dots = ""
    for m in all_models:
        cx = px(m["cost_usd"])
        cy = py(m["sr"])
        r = 4 + m["demos"] / max_demos * 9
        color = "#C74634" if m.get("production") else EMBODIMENT_COLORS.get(m["embodiment"], "#38bdf8")
        dots += (f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" '
                 f'fill="{color}" fill-opacity="0.75" stroke="{color}" stroke-width="1"/>'
                 f'<title>{m["model"]} SR={m["sr"]} cost=${m["cost_usd"]}</title>')

    # legend embodiments
    legend = ""
    for i, (emb, col) in enumerate(EMBODIMENT_COLORS.items()):
        lx, ly = W - pad_r - 68, pad_t + 8 + i * 18
        legend += f'<circle cx="{lx+6}" cy="{ly}" r="5" fill="{col}" fill-opacity="0.8"/>'
        legend += f'<text x="{lx+14}" y="{ly+4}" fill="#cbd5e1" font-size="9">{emb}</text>'

    # axes labels
    ax_lbl = (f'<text x="{pad_l + chart_w/2:.1f}" y="{H-4}" fill="#94a3b8" font-size="9" text-anchor="middle">'
              f'Fine-tuning Cost (USD)</text>'
              f'<text x="12" y="{pad_t + chart_h/2:.1f}" fill="#94a3b8" font-size="9" '
              f'transform="rotate(-90,12,{pad_t + chart_h/2:.1f})" text-anchor="middle">Success Rate</text>')

    return (f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:{W}px">'
            f'<rect width="{W}" height="{H}" fill="#1e293b" rx="8"/>'
            f'<text x="{W//2}" y="22" fill="#f1f5f9" font-size="13" font-weight="bold" text-anchor="middle">'
            f'SR vs Fine-Tuning Cost — All Submitted Models</text>'
            f'<text x="{W//2}" y="35" fill="#64748b" font-size="8" text-anchor="middle">'
            f'Dot size ∝ demos count &nbsp;|&nbsp; Green dashed = Pareto frontier</text>'
            f'{grid}{pareto_line}{pareto_lbl}{dots}{legend}{ax_lbl}</svg>')


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def _build_html() -> str:
    # embodiment breakdown
    emb_counts: dict = {}
    emb_sr_sum: dict = {}
    for m in LEADERBOARD:
        e = m["embodiment"]
        emb_counts[e] = emb_counts.get(e, 0) + 1
        emb_sr_sum[e] = emb_sr_sum.get(e, 0.0) + m["sr"]
    emb_rows = ""
    for e, cnt in sorted(emb_counts.items()):
        avg = emb_sr_sum[e] / cnt
        col = EMBODIMENT_COLORS.get(e, "#f1f5f9")
        emb_rows += (f'<tr><td style="color:{col}">{e}</td><td>{cnt}</td>'
                     f'<td style="color:{col}">{avg:.2f}</td></tr>')

    bar_svg = _bar_chart_svg()
    scatter_svg = _scatter_svg()

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>OCI Robot Cloud — Eval Leaderboard</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; }}
  header {{ background: #1e293b; border-bottom: 2px solid #C74634; padding: 16px 32px; display:flex; align-items:center; gap:16px; }}
  header h1 {{ font-size: 1.4rem; color: #f1f5f9; }}
  .badge {{ background: #C74634; color: #fff; padding: 3px 10px; border-radius: 12px; font-size: 0.75rem; font-weight: 600; }}
  .container {{ max-width: 1200px; margin: 0 auto; padding: 32px 24px; }}
  .section-title {{ font-size: 1.1rem; color: #38bdf8; font-weight: 600; margin: 28px 0 14px; border-left: 3px solid #C74634; padding-left: 10px; }}
  .kpi-row {{ display:flex; gap:16px; flex-wrap:wrap; margin-bottom:28px; }}
  .kpi {{ background:#1e293b; border:1px solid #334155; border-radius:8px; padding:14px 20px; flex:1; min-width:160px; }}
  .kpi .val {{ font-size:1.6rem; font-weight:700; color:#38bdf8; }}
  .kpi .lbl {{ font-size:0.75rem; color:#64748b; margin-top:4px; }}
  .charts {{ display:grid; grid-template-columns:1fr 1fr; gap:24px; }}
  @media(max-width:700px) {{ .charts {{ grid-template-columns:1fr; }} }}
  .chart-box {{ background:#1e293b; border:1px solid #334155; border-radius:10px; padding:16px; }}
  table {{ width:100%; border-collapse:collapse; background:#1e293b; border-radius:8px; overflow:hidden; }}
  th {{ background:#0f2744; color:#94a3b8; font-size:0.75rem; text-transform:uppercase; padding:8px 12px; text-align:left; }}
  td {{ padding:8px 12px; font-size:0.85rem; border-bottom:1px solid #1e3a5f; }}
  tr:last-child td {{ border-bottom:none; }}
  footer {{ text-align:center; color:#334155; font-size:0.75rem; padding:32px; }}
</style>
</head>
<body>
<header>
  <div><div style="font-size:0.7rem;color:#64748b;letter-spacing:2px">OCI ROBOT CLOUD</div>
       <h1>GR00T Policy Eval Leaderboard</h1></div>
  <div class="badge">PORT 8235</div>
</header>
<div class="container">
  <div class="section-title">Platform KPIs</div>
  <div class="kpi-row">
    <div class="kpi"><div class="val">{SOTA_SR}</div><div class="lbl">SOTA SR (LIBERO)</div></div>
    <div class="kpi"><div class="val">{AVG_SR}</div><div class="lbl">Avg Platform SR</div></div>
    <div class="kpi"><div class="val">{len(LEADERBOARD) + len(SCATTER_EXTRA)}</div><div class="lbl">Total Submitted Models</div></div>
    <div class="kpi"><div class="val">PI_custom_v3</div><div class="lbl">#1 Model (Pareto Best)</div></div>
    <div class="kpi"><div class="val">4</div><div class="lbl">Embodiment Types</div></div>
  </div>

  <div class="section-title">Visualizations</div>
  <div class="charts">
    <div class="chart-box">{bar_svg}</div>
    <div class="chart-box">{scatter_svg}</div>
  </div>

  <div class="section-title">Embodiment Leaderboard Breakdown</div>
  <table>
    <thead><tr><th>Embodiment</th><th>Models</th><th>Avg SR</th></tr></thead>
    <tbody>{emb_rows}</tbody>
  </table>
</div>
<footer>OCI Robot Cloud &mdash; Eval Leaderboard &mdash; port 8235 &mdash; Oracle Confidential</footer>
</body>
</html>"""


# ---------------------------------------------------------------------------
# App wiring
# ---------------------------------------------------------------------------

if USE_FASTAPI:
    app = FastAPI(title="Eval Leaderboard", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return HTMLResponse(content=_build_html())

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "eval_leaderboard", "port": 8235}

    @app.get("/api/leaderboard")
    async def leaderboard():
        return {"leaderboard": LEADERBOARD, "avg_sr": AVG_SR, "sota_sr": SOTA_SR}

    @app.get("/api/scatter")
    async def scatter():
        return {"models": LEADERBOARD + SCATTER_EXTRA}

else:
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            html = _build_html().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html)))
            self.end_headers()
            self.wfile.write(html)

        def log_message(self, fmt, *args):
            pass


if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8235)
    else:
        print("fastapi not found — serving on http://0.0.0.0:8235 via stdlib")
        HTTPServer(("0.0.0.0", 8235), _Handler).serve_forever()
