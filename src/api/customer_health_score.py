#!/usr/bin/env python3
"""
Customer Health Score Dashboard
Port 8307 — composite health scoring for proactive churn prevention & expansion signals
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

import math
import random
from datetime import datetime

# ── Mock customer data ───────────────────────────────────────────────────────

# 6 health dimensions (scale 1-5)
DIMENSIONS = ["Usage Trend", "SR Improvement", "Support Tickets", "API Adoption", "Engagement", "Renewal Signal"]

# Partners and their dimension scores
PARTNERS = [
    {
        "name": "PI",
        "color": "#4ade80",
        "scores": [4.8, 4.6, 4.5, 4.2, 4.5, 4.0],
        "composite": 4.4,
        "status": "EXPANDING",
        "status_color": "#4ade80",
        "note": "Strong API adoption, increasing fleet size",
    },
    {
        "name": "Apt",
        "color": "#38bdf8",
        "scores": [3.9, 3.8, 4.0, 3.7, 3.9, 3.5],
        "composite": 3.8,
        "status": "STABLE",
        "status_color": "#38bdf8",
        "note": "Consistent usage, no major support issues",
    },
    {
        "name": "Covariant",
        "color": "#fbbf24",
        "scores": [3.3, 3.5, 2.2, 3.0, 3.4, 3.0],
        "composite": 3.2,
        "status": "AT RISK",
        "status_color": "#fbbf24",
        "note": "Support ticket spike in Feb — needs attention",
    },
    {
        "name": "1X",
        "color": "#f87171",
        "scores": [2.5, 2.4, 3.0, 2.8, 2.6, 2.2],
        "composite": 2.7,
        "status": "CHURN RISK",
        "status_color": "#f87171",
        "note": "Flat usage + SR not improving — urgent action needed",
    },
    {
        "name": "Robust AI",
        "color": "#a78bfa",
        "scores": [4.2, 4.0, 4.3, 4.1, 3.9, 4.0],
        "composite": 4.1,
        "status": "HEALTHY",
        "status_color": "#a78bfa",
        "note": "High satisfaction, exploring premium tier",
    },
]

# 3-month health trend (Jan, Feb, Mar)
random.seed(17)
MONTH_LABELS = ["Jan", "Feb", "Mar"]

# Trend data — composite score per partner per month
TREND_DATA = {
    "PI":        [3.9, 4.2, 4.4],
    "Apt":       [3.7, 3.8, 3.8],
    "Covariant": [3.8, 3.2, 3.2],
    "1X":        [3.1, 2.9, 2.7],
    "Robust AI": [3.9, 4.0, 4.1],
}

# ── Computed stats ───────────────────────────────────────────────────────────

AVG_HEALTH   = round(sum(p["composite"] for p in PARTNERS) / len(PARTNERS), 2)
CHURN_RISK   = [p["name"] for p in PARTNERS if p["composite"] < 3.0]
EXPANSION    = [p["name"] for p in PARTNERS if p["composite"] >= 4.3]
HEALTH_NPS_CORR = 0.87   # mock correlation

# ── SVG 1: Health Scorecard (heatmap grid) ───────────────────────────────────

def _dim_color(score: float) -> str:
    if score >= 4.0:
        return "#166534"  # dark green
    if score >= 3.0:
        return "#854d0e"  # amber
    return "#7f1d1d"      # red

def _dim_text_color(score: float) -> str:
    if score >= 4.0:
        return "#4ade80"
    if score >= 3.0:
        return "#fbbf24"
    return "#f87171"


def svg_scorecard() -> str:
    N_P = len(PARTNERS)
    N_D = len(DIMENSIONS)
    CELL_W, CELL_H = 80, 44
    LEFT_PAD = 90
    TOP_PAD  = 70
    W = LEFT_PAD + N_D * CELL_W + 90   # +90 for composite col
    H = TOP_PAD + N_P * CELL_H + 30

    out = f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg" style="background:#0f172a;border-radius:10px">'
    out += f'<text x="{W//2}" y="22" fill="#f1f5f9" font-size="14" font-weight="bold" text-anchor="middle">Customer Health Scorecard — {datetime.utcnow().strftime("%B %Y")}</text>'

    # Dimension headers
    for di, dim in enumerate(DIMENSIONS):
        x = LEFT_PAD + di * CELL_W + CELL_W // 2
        # wrap long label
        parts = dim.split(" ")
        for line_i, part in enumerate(parts):
            out += f'<text x="{x}" y="{44 + line_i*14}" fill="#94a3b8" font-size="10" text-anchor="middle">{part}</text>'

    out += f'<text x="{LEFT_PAD + N_D * CELL_W + 45}" y="44" fill="#38bdf8" font-size="11" font-weight="bold" text-anchor="middle">Score</text>'

    # Partner rows
    for pi, partner in enumerate(PARTNERS):
        row_y = TOP_PAD + pi * CELL_H
        # Partner name
        out += f'<text x="{LEFT_PAD-8}" y="{row_y + CELL_H//2 + 5}" fill="{partner["color"]}" font-size="12" font-weight="bold" text-anchor="end">{partner["name"]}</text>'

        for di, score in enumerate(partner["scores"]):
            cx = LEFT_PAD + di * CELL_W
            out += f'<rect x="{cx+2}" y="{row_y+3}" width="{CELL_W-4}" height="{CELL_H-6}" fill="{_dim_color(score)}" rx="5"/>'
            out += f'<text x="{cx + CELL_W//2}" y="{row_y + CELL_H//2 + 5}" fill="{_dim_text_color(score)}" font-size="13" font-weight="bold" text-anchor="middle">{score}</text>'

        # Composite
        comp = partner["composite"]
        cx = LEFT_PAD + N_D * CELL_W
        out += f'<rect x="{cx+2}" y="{row_y+3}" width="84" height="{CELL_H-6}" fill="{_dim_color(comp)}" rx="5"/>'
        out += f'<text x="{cx+44}" y="{row_y + CELL_H//2 + 5}" fill="{_dim_text_color(comp)}" font-size="14" font-weight="700" text-anchor="middle">{comp}/5</text>'

    out += '</svg>'
    return out


# ── SVG 2: Health Score Trend Lines ──────────────────────────────────────────

def svg_trend() -> str:
    W, H = 700, 340
    PAD_L, PAD_R, PAD_T, PAD_B = 60, 30, 40, 55
    plot_w = W - PAD_L - PAD_R
    plot_h = H - PAD_T - PAD_B
    N_MONTHS = len(MONTH_LABELS)
    SCORE_MIN, SCORE_MAX = 1.0, 5.0

    def xp(idx):
        return PAD_L + idx * (plot_w / (N_MONTHS - 1))

    def yp(score):
        frac = (score - SCORE_MIN) / (SCORE_MAX - SCORE_MIN)
        return PAD_T + plot_h - frac * plot_h

    # Grid
    grid = ""
    for tick in [2.0, 2.5, 3.0, 3.5, 4.0, 4.5]:
        y = yp(tick)
        grid += f'<line x1="{PAD_L}" y1="{y:.1f}" x2="{W-PAD_R}" y2="{y:.1f}" stroke="#1e3a5f" stroke-width="1"/>'
        grid += f'<text x="{PAD_L-8}" y="{y+4:.1f}" fill="#94a3b8" font-size="10" text-anchor="end">{tick:.1f}</text>'

    for i, lbl in enumerate(MONTH_LABELS):
        x = xp(i)
        grid += f'<line x1="{x:.1f}" y1="{PAD_T}" x2="{x:.1f}" y2="{PAD_T+plot_h}" stroke="#1e3a5f" stroke-width="1"/>'
        grid += f'<text x="{x:.1f}" y="{PAD_T+plot_h+18}" fill="#94a3b8" font-size="12" text-anchor="middle">{lbl}</text>'

    lines = ""
    for partner in PARTNERS:
        name   = partner["name"]
        color  = partner["color"]
        scores = TREND_DATA[name]
        pts    = " ".join(f"{xp(i):.1f},{yp(s):.1f}" for i, s in enumerate(scores))
        lines += f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2.5"/>'
        # dots
        for i, s in enumerate(scores):
            lines += f'<circle cx="{xp(i):.1f}" cy="{yp(s):.1f}" r="5" fill="{color}" stroke="#0f172a" stroke-width="2"/>'
        # end label
        last_x = xp(N_MONTHS-1) + 6
        last_y = yp(scores[-1]) + 4
        lines += f'<text x="{last_x:.1f}" y="{last_y:.1f}" fill="{color}" font-size="11">{name}</text>'

    # Churn threshold line
    thresh_y = yp(3.0)
    lines += f'<line x1="{PAD_L}" y1="{thresh_y:.1f}" x2="{W-PAD_R}" y2="{thresh_y:.1f}" stroke="#f87171" stroke-width="1.5" stroke-dasharray="8,4"/>'
    lines += f'<text x="{PAD_L+4}" y="{thresh_y-5:.1f}" fill="#f87171" font-size="10">churn risk threshold</text>'

    svg = f"""
<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg" style="background:#0f172a;border-radius:10px">
  <text x="{W//2}" y="22" fill="#f1f5f9" font-size="14" font-weight="bold" text-anchor="middle">Health Score Trend — Jan to Mar 2026</text>
  {grid}
  {lines}
  <text x="14" y="{PAD_T + plot_h//2}" fill="#94a3b8" font-size="11" text-anchor="middle" transform="rotate(-90,14,{PAD_T + plot_h//2})">Health Score (1-5)</text>
</svg>"""
    return svg


# ── HTML page ────────────────────────────────────────────────────────────────

def build_html() -> str:
    churn_str     = ", ".join(CHURN_RISK) if CHURN_RISK else "None"
    expansion_str = ", ".join(EXPANSION)  if EXPANSION  else "None"

    rows = ""
    for p in PARTNERS:
        rows += f"""
        <tr>
          <td style="font-weight:700;color:{p['color']}">{p['name']}</td>
          <td style="color:{p['status_color']};font-weight:600">{p['status']}</td>
          <td style="color:#38bdf8;font-weight:700">{p['composite']}/5</td>
          <td style="color:#94a3b8;font-size:0.85rem">{p['note']}</td>
        </tr>"""

    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <title>Customer Health Score Dashboard</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #f1f5f9; font-family: 'Segoe UI', sans-serif; padding: 24px; }}
    h1 {{ color: #C74634; font-size: 1.8rem; margin-bottom: 4px; }}
    .subtitle {{ color: #94a3b8; font-size: 0.95rem; margin-bottom: 24px; }}
    .kpi-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 28px; }}
    .kpi {{ background: #1e293b; border-radius: 10px; padding: 18px; border-left: 4px solid #C74634; }}
    .kpi .val {{ font-size: 2rem; font-weight: 700; color: #38bdf8; }}
    .kpi .lbl {{ font-size: 0.8rem; color: #94a3b8; margin-top: 4px; }}
    .section {{ background: #1e293b; border-radius: 10px; padding: 20px; margin-bottom: 24px; }}
    .section h2 {{ color: #38bdf8; font-size: 1.1rem; margin-bottom: 14px; }}
    svg {{ max-width: 100%; display: block; margin: 0 auto; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 8px; }}
    th {{ text-align: left; color: #94a3b8; font-size: 0.8rem; padding: 6px 10px;
          border-bottom: 1px solid #334155; }}
    td {{ padding: 10px 10px; border-bottom: 1px solid #1e293b; font-size: 0.9rem; }}
    .alert {{ background: #450a0a; border: 1px solid #f87171; border-radius: 8px;
              padding: 12px 16px; margin-bottom: 16px; color: #fca5a5; font-size: 0.9rem; }}
    .footer {{ text-align: center; color: #475569; font-size: 0.8rem; margin-top: 24px; }}
  </style>
</head>
<body>
  <h1>Customer Health Score Dashboard</h1>
  <p class="subtitle">Composite health scoring across 5 design partners &bull; 6 dimensions &bull; Proactive churn prevention &amp; expansion signals</p>

  {'<div class="alert">&#9888; CHURN RISK: ' + churn_str + ' — flat usage, SR not improving. Schedule urgent review.</div>' if CHURN_RISK else ''}

  <div class="kpi-grid">
    <div class="kpi"><div class="val">{AVG_HEALTH}/5</div><div class="lbl">Avg Fleet Health Score</div></div>
    <div class="kpi"><div class="val" style="color:#f87171">{len(CHURN_RISK)}</div><div class="lbl">Churn Risk Partners</div></div>
    <div class="kpi"><div class="val" style="color:#4ade80">{len(EXPANSION)}</div><div class="lbl">Expansion Opportunity</div></div>
    <div class="kpi"><div class="val">{HEALTH_NPS_CORR}</div><div class="lbl">Health–NPS Correlation</div></div>
  </div>

  <div class="section">
    <h2>Health Scorecard — 5 Partners × 6 Dimensions</h2>
    {svg_scorecard()}
  </div>

  <div class="section">
    <h2>Health Score Trend (Jan–Mar 2026)</h2>
    {svg_trend()}
  </div>

  <div class="section">
    <h2>Partner Summary</h2>
    <table>
      <thead><tr><th>Partner</th><th>Status</th><th>Score</th><th>Notes</th></tr></thead>
      <tbody>{rows}</tbody>
    </table>
  </div>

  <div class="footer">OCI Robot Cloud &bull; Customer Health Score &bull; Port 8307 &bull; {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC</div>
</body>
</html>
"""


# ── App ──────────────────────────────────────────────────────────────────────

if HAS_FASTAPI:
    app = FastAPI(title="Customer Health Score Dashboard", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return HTMLResponse(content=build_html())

    @app.get("/api/health")
    async def health_summary():
        return {
            "avg_health_score": AVG_HEALTH,
            "churn_risk_partners": CHURN_RISK,
            "expansion_opportunity": EXPANSION,
            "health_nps_correlation": HEALTH_NPS_CORR,
            "partners": [
                {
                    "name": p["name"],
                    "composite": p["composite"],
                    "status": p["status"],
                    "dimension_scores": dict(zip(DIMENSIONS, p["scores"])),
                    "note": p["note"],
                }
                for p in PARTNERS
            ],
        }

    @app.get("/api/trend")
    async def trend():
        return {
            "months": MONTH_LABELS,
            "trends": TREND_DATA,
        }

else:
    from http.server import HTTPServer, BaseHTTPRequestHandler

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = build_html().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            pass


if __name__ == "__main__":
    if HAS_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8307)
    else:
        print("FastAPI not found — starting stdlib fallback on port 8307")
        HTTPServer(("0.0.0.0", 8307), Handler).serve_forever()
