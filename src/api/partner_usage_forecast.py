"""Partner Usage Forecast Service — port 8258

Forecasts partner GPU usage and revenue for capacity planning and sales pipeline.
Oracle OCI Robot Cloud — cycle-49B
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

import random
import math
import json
from datetime import datetime

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

PARTNERS = [
    {"name": "PI (Physical Intelligence)", "short": "PI",    "color": "#38bdf8"},
    {"name": "1X Technologies",            "short": "1X",    "color": "#C74634"},
    {"name": "Agility Robotics",           "short": "Agility", "color": "#a78bfa"},
    {"name": "Boston Dynamics",            "short": "BD",    "color": "#34d399"},
    {"name": "Sanctuary AI",               "short": "Sanct", "color": "#fbbf24"},
]

# Monthly MRR per partner (Jan–Mar actuals, Apr–Sep forecast)
# Total Mar ARR = $2,927  →  MRR ≈ $244 base; target Sep $19k/12 ≈ $1,583 MRR
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep"]
ACTUAL_MONTHS = 3   # Jan–Mar are actuals

# MRR per partner per month (USD)
MRR_DATA = {
    "PI":     [210, 310, 490, 680, 920, 1180, 1450, 1800, 2400],  # fastest growth
    "1X":     [140, 145, 148, 150, 151, 150,  149,  148,  148],   # flat / churn risk
    "Agility":[80,  120, 180, 260, 350, 470,  600,  750,  950],
    "BD":     [50,  70,  110, 160, 220, 310,  420,  560,  710],
    "Sanct":  [30,  50,  70,  100, 140, 190,  250,  320,  420],
}

# Bubble chart data: current MRR, projected 6-month MRR, demos/month
BUBBLE_DATA = [
    {"short": "PI",     "cur_mrr": 490,  "proj_mrr": 2400, "demos": 38, "color": "#38bdf8",  "risk": False},
    {"short": "1X",     "cur_mrr": 148,  "proj_mrr": 148,  "demos": 8,  "color": "#C74634",  "risk": True},
    {"short": "Agility","cur_mrr": 180,  "proj_mrr": 950,  "demos": 22, "color": "#a78bfa",  "risk": False},
    {"short": "BD",     "cur_mrr": 110,  "proj_mrr": 710,  "demos": 15, "color": "#34d399",  "risk": False},
    {"short": "Sanct",  "cur_mrr": 70,   "proj_mrr": 420,  "demos": 9,  "color": "#fbbf24",  "risk": False},
]

# Key metrics
METRICS = {
    "mar_arr":            2927,
    "sep_mrr_target":     19000,
    "nrr_pct":            127,
    "partner_expansion":  4,    # out of 5 expanding
    "churn_risk_count":   1,    # 1X
    "new_partners_needed":3,
    "gpu_capacity_sep_h100": 64,  # H100s needed at Sep revenue target
}

# ---------------------------------------------------------------------------
# SVG generators
# ---------------------------------------------------------------------------

def make_area_chart() -> str:
    """Stacked area chart: MRR by partner over Jan-Sep."""
    W, H = 700, 280
    PAD_L, PAD_R, PAD_T, PAD_B = 60, 20, 30, 50
    chart_w = W - PAD_L - PAD_R
    chart_h = H - PAD_T - PAD_B

    n = len(MONTHS)
    # stacked totals
    totals = [sum(MRR_DATA[p["short"]][i] for p in PARTNERS) for i in range(n)]
    max_val = max(totals) * 1.1

    def px(i):  # x pixel for month index
        return PAD_L + i * chart_w / (n - 1)

    def py(v):  # y pixel for value
        return PAD_T + chart_h - (v / max_val) * chart_h

    # Build cumulative stacks
    order = ["Sanct", "BD", "Agility", "1X", "PI"]
    partner_colors = {p["short"]: p["color"] for p in PARTNERS}

    paths_svg = ""
    prev_bottoms = [0.0] * n
    for short in order:
        tops = [prev_bottoms[i] + MRR_DATA[short][i] for i in range(n)]
        # forward path
        pts_top = " ".join(f"{px(i):.1f},{py(tops[i]):.1f}" for i in range(n))
        # reverse bottom
        pts_bot = " ".join(f"{px(i):.1f},{py(prev_bottoms[i]):.1f}" for i in range(n - 1, -1, -1))
        d = f"M {pts_top.split()[0]} L {pts_top} L {pts_bot} Z"
        paths_svg += f'<path d="{d}" fill="{partner_colors[short]}" fill-opacity="0.75"/>\n'
        prev_bottoms = tops

    # Divider: actual vs forecast
    div_x = px(ACTUAL_MONTHS - 1) + (px(ACTUAL_MONTHS) - px(ACTUAL_MONTHS - 1)) / 2
    divider = (f'<line x1="{div_x:.1f}" y1="{PAD_T}" x2="{div_x:.1f}" y2="{PAD_T + chart_h}" '
               f'stroke="#94a3b8" stroke-width="1.5" stroke-dasharray="5,4"/>\n'
               f'<text x="{div_x - 4:.1f}" y="{PAD_T + 12}" fill="#94a3b8" font-size="9" text-anchor="end">Actuals</text>\n'
               f'<text x="{div_x + 4:.1f}" y="{PAD_T + 12}" fill="#94a3b8" font-size="9">Forecast</text>\n')

    # AI World annotation at Sep
    ann_x = px(8)
    ann_y = py(totals[8]) - 8
    annotation = (f'<line x1="{ann_x:.1f}" y1="{ann_y + 4:.1f}" x2="{ann_x:.1f}" y2="{py(totals[8]):.1f}" '
                  f'stroke="#C74634" stroke-width="1.5"/>\n'
                  f'<text x="{ann_x:.1f}" y="{ann_y:.1f}" fill="#C74634" font-size="9" text-anchor="middle">AI World Sep</text>\n')

    # X axis labels
    x_labels = "".join(
        f'<text x="{px(i):.1f}" y="{PAD_T + chart_h + 16}" fill="#94a3b8" font-size="10" text-anchor="middle">{MONTHS[i]}</text>\n'
        for i in range(n)
    )

    # Y axis labels
    y_ticks = [0, 2000, 4000, 6000]
    y_labels = "".join(
        f'<text x="{PAD_L - 6}" y="{py(v) + 4:.1f}" fill="#94a3b8" font-size="9" text-anchor="end">${v//1000}k</text>\n'
        f'<line x1="{PAD_L}" y1="{py(v):.1f}" x2="{PAD_L + chart_w}" y2="{py(v):.1f}" stroke="#1e293b" stroke-width="0.8"/>\n'
        for v in y_ticks
    )

    # Legend
    legend = ""
    for idx, p in enumerate(PARTNERS):
        lx = PAD_L + idx * 120
        ly = H - 10
        legend += (f'<rect x="{lx}" y="{ly - 7}" width="10" height="8" fill="{p["color"]}" fill-opacity="0.8"/>\n'
                   f'<text x="{lx + 13}" y="{ly}" fill="#cbd5e1" font-size="9">{p["short"]}</text>\n')

    # Target line at $19k MRR
    target_y = py(19000)
    target_line = (f'<line x1="{PAD_L}" y1="{target_y:.1f}" x2="{PAD_L + chart_w}" y2="{target_y:.1f}" '
                   f'stroke="#C74634" stroke-width="1" stroke-dasharray="6,3" opacity="0.6"/>\n'
                   f'<text x="{PAD_L + chart_w - 2}" y="{target_y - 3:.1f}" fill="#C74634" font-size="8" text-anchor="end">$19k target</text>\n')

    svg = (f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" '
           f'style="width:100%;max-width:{W}px;background:#0f172a;border-radius:8px;">\n'
           f'{y_labels}{target_line}{paths_svg}{divider}{annotation}{x_labels}{legend}'
           f'<text x="{W//2}" y="{PAD_T - 10}" fill="#e2e8f0" font-size="11" font-weight="bold" text-anchor="middle">Partner MRR Forecast — Jan–Sep 2026 (Stacked)</text>\n'
           f'</svg>')
    return svg


def make_bubble_chart() -> str:
    """Bubble scatter: current MRR vs projected 6-month MRR; bubble = demos/month."""
    W, H = 700, 300
    PAD_L, PAD_R, PAD_T, PAD_B = 70, 30, 30, 55
    chart_w = W - PAD_L - PAD_R
    chart_h = H - PAD_T - PAD_B

    max_cur = 550
    max_proj = 2600
    max_demos = 40

    def px(v):  return PAD_L + (v / max_cur) * chart_w
    def py(v):  return PAD_T + chart_h - (v / max_proj) * chart_h
    def pr(d):  return 6 + (d / max_demos) * 22  # bubble radius

    bubbles = ""
    labels = ""
    for b in BUBBLE_DATA:
        cx = px(b["cur_mrr"])
        cy = py(b["proj_mrr"])
        r  = pr(b["demos"])
        stroke = "#C74634" if b["risk"] else b["color"]
        stroke_w = 2.5 if b["risk"] else 1
        bubbles += (f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" '
                    f'fill="{b["color"]}" fill-opacity="0.35" '
                    f'stroke="{stroke}" stroke-width="{stroke_w}"/>\n')
        label_y = cy - r - 4 if cy - r - 4 > PAD_T + 10 else cy + r + 12
        churn_tag = " ⚠" if b["risk"] else ""
        labels += (f'<text x="{cx:.1f}" y="{label_y:.1f}" fill="#e2e8f0" font-size="10" '
                   f'text-anchor="middle" font-weight="bold">{b["short"]}{churn_tag}</text>\n')

    # diagonal guide line: equal growth (45°)
    # map proj=cur line
    diag_pts = []
    for v in [0, 550]:
        dx = px(v)
        dy = py(min(v, max_proj))
        diag_pts.append(f"{dx:.1f},{dy:.1f}")
    diag = (f'<polyline points="{" ".join(diag_pts)}" fill="none" stroke="#475569" '
            f'stroke-width="1" stroke-dasharray="4,4"/>\n'
            f'<text x="{px(200):.1f}" y="{py(230):.1f}" fill="#475569" font-size="8" '
            f'transform="rotate(-35,{px(200):.1f},{py(230):.1f})">No Growth</text>\n')

    # Axes
    x_ticks = [0, 100, 200, 300, 400, 500]
    x_labels = "".join(
        f'<text x="{px(v):.1f}" y="{PAD_T + chart_h + 16}" fill="#94a3b8" font-size="9" text-anchor="middle">${v}</text>\n'
        for v in x_ticks
    )
    x_axis_title = (f'<text x="{PAD_L + chart_w/2:.1f}" y="{H - 8}" fill="#94a3b8" '
                    f'font-size="10" text-anchor="middle">Current MRR (Mar 2026)</text>\n')

    y_ticks = [0, 500, 1000, 1500, 2000, 2500]
    y_labels = "".join(
        f'<text x="{PAD_L - 6}" y="{py(v) + 4:.1f}" fill="#94a3b8" font-size="9" text-anchor="end">${v}</text>\n'
        f'<line x1="{PAD_L}" y1="{py(v):.1f}" x2="{PAD_L + chart_w}" y2="{py(v):.1f}" stroke="#1e293b" stroke-width="0.8"/>\n'
        for v in y_ticks
    )
    y_axis_title = (f'<text x="14" y="{PAD_T + chart_h/2:.1f}" fill="#94a3b8" font-size="10" '
                    f'text-anchor="middle" transform="rotate(-90,14,{PAD_T + chart_h/2:.1f})">Projected MRR (Sep 2026)</text>\n')

    # Churn risk annotation
    churn_note = (f'<rect x="{PAD_L + chart_w - 130}" y="{PAD_T + 4}" width="120" height="22" '
                  f'rx="4" fill="#C74634" fill-opacity="0.15" stroke="#C74634" stroke-width="0.8"/>\n'
                  f'<text x="{PAD_L + chart_w - 70}" y="{PAD_T + 19}" fill="#C74634" '
                  f'font-size="9" text-anchor="middle">⚠ Churn risk: 1X flat</text>\n')

    title = (f'<text x="{W//2}" y="{PAD_T - 10}" fill="#e2e8f0" font-size="11" '
             f'font-weight="bold" text-anchor="middle">Partner Growth Trajectory — Bubble = demos/mo</text>\n')

    svg = (f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" '
           f'style="width:100%;max-width:{W}px;background:#0f172a;border-radius:8px;">\n'
           f'{y_labels}{y_axis_title}{diag}{bubbles}{labels}{x_labels}{x_axis_title}{churn_note}{title}'
           f'</svg>')
    return svg


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def build_html() -> str:
    area_svg   = make_area_chart()
    bubble_svg = make_bubble_chart()
    m = METRICS
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    metric_cards = [
        ("Mar ARR",              f"${m['mar_arr']:,}",             "#38bdf8"),
        ("Sep MRR Target",       f"${m['sep_mrr_target']:,}",       "#C74634"),
        ("Net Revenue Retention",f"{m['nrr_pct']}%",               "#34d399"),
        ("Partners Expanding",   f"{m['partner_expansion']}/5",    "#a78bfa"),
        ("Churn Risks",          f"{m['churn_risk_count']} (1X)",  "#fbbf24"),
        ("New Partners Needed",  f"{m['new_partners_needed']}",    "#f87171"),
        ("H100s @ Sep Target",   f"{m['gpu_capacity_sep_h100']}", "#38bdf8"),
    ]

    cards_html = "".join(
        f'<div style="background:#1e293b;border-radius:8px;padding:14px 18px;border-left:3px solid {c};">'
        f'<div style="color:#94a3b8;font-size:11px;margin-bottom:4px;">{label}</div>'
        f'<div style="color:{c};font-size:22px;font-weight:700;">{val}</div></div>\n'
        for label, val, c in metric_cards
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Partner Usage Forecast — OCI Robot Cloud</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #e2e8f0; font-family: system-ui, sans-serif; padding: 24px; }}
    h1   {{ color: #C74634; font-size: 20px; margin-bottom: 4px; }}
    .sub {{ color: #64748b; font-size: 12px; margin-bottom: 20px; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fill,minmax(160px,1fr)); gap: 12px; margin-bottom: 28px; }}
    .chart-wrap {{ margin-bottom: 28px; }}
    .chart-title {{ color: #94a3b8; font-size: 12px; margin-bottom: 8px; text-transform: uppercase; letter-spacing: .05em; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 12px; background: #1e293b; border-radius: 8px; overflow: hidden; margin-bottom: 20px; }}
    th {{ background: #0f172a; color: #94a3b8; padding: 8px 12px; text-align: left; font-weight: 600; }}
    td {{ padding: 7px 12px; border-bottom: 1px solid #0f172a; }}
    tr:last-child td {{ border-bottom: none; }}
    .risk  {{ color: #fbbf24; }}
    .grow  {{ color: #34d399; }}
    footer {{ color: #334155; font-size: 11px; margin-top: 24px; }}
  </style>
</head>
<body>
  <h1>Partner Usage Forecast</h1>
  <div class="sub">OCI Robot Cloud · Capacity &amp; Sales Pipeline · Generated {ts}</div>

  <div class="grid">
    {cards_html}
  </div>

  <div class="chart-wrap">
    <div class="chart-title">6-Month Stacked MRR Forecast by Partner</div>
    {area_svg}
  </div>

  <div class="chart-wrap">
    <div class="chart-title">Partner Growth Trajectory (Current vs Projected MRR)</div>
    {bubble_svg}
  </div>

  <table>
    <thead><tr><th>Partner</th><th>Mar MRR</th><th>Sep Proj</th><th>Demos/mo</th><th>NRR</th><th>Status</th></tr></thead>
    <tbody>
      <tr><td>PI (Physical Intelligence)</td><td>$490</td><td>$2,400</td><td>38</td><td class="grow">156%</td><td class="grow">Expanding fast</td></tr>
      <tr><td>1X Technologies</td><td>$148</td><td>$148</td><td>8</td><td class="risk">100%</td><td class="risk">⚠ Churn risk — flat usage</td></tr>
      <tr><td>Agility Robotics</td><td>$180</td><td>$950</td><td>22</td><td class="grow">144%</td><td class="grow">Expanding</td></tr>
      <tr><td>Boston Dynamics</td><td>$110</td><td>$710</td><td>15</td><td class="grow">138%</td><td class="grow">Expanding</td></tr>
      <tr><td>Sanctuary AI</td><td>$70</td><td>$420</td><td>9</td><td class="grow">132%</td><td class="grow">Expanding</td></tr>
    </tbody>
  </table>

  <footer>OCI Robot Cloud · Partner Usage Forecast Service · Port 8258 · Oracle Confidential</footer>
</body>
</html>"""


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

if USE_FASTAPI:
    app = FastAPI(
        title="Partner Usage Forecast",
        description="Forecasts partner GPU usage and revenue for capacity planning and sales pipeline.",
        version="1.0.0",
    )

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return HTMLResponse(content=build_html())

    @app.get("/metrics")
    def metrics():
        return METRICS

    @app.get("/partners")
    def partners():
        return BUBBLE_DATA

    @app.get("/forecast")
    def forecast():
        return {"months": MONTHS, "mrr": MRR_DATA}

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "partner_usage_forecast", "port": 8258}

else:
    # stdlib fallback
    from http.server import HTTPServer, BaseHTTPRequestHandler

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            html = build_html().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html)))
            self.end_headers()
            self.wfile.write(html)
        def log_message(self, *_): pass


if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8258)
    else:
        print("FastAPI not available — serving via stdlib HTTP on port 8258")
        HTTPServer(("0.0.0.0", 8258), Handler).serve_forever()
