#!/usr/bin/env python3
"""
Partner Expansion Planner — FastAPI service on port 8303
Plans partner tier upgrades and expansion opportunities for revenue growth.
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
import json
from datetime import datetime

# ── Mock data ──────────────────────────────────────────────────────────────────
PARTNERS = [
    {
        "name": "PI",
        "usage_growth": 0.82,
        "sr_improvement": 0.78,
        "tier": "growth",
        "mrr": 680,
        "quota_pct": 0.80,
        "expansion_action": "Upgrade to Enterprise",
        "expansion_value": 800,
        "upgrade_readiness": 0.91,
        "quadrant": "expand",
        "notes": "At 80% quota, enterprise tier unlocks multi-arm + priority GPU",
    },
    {
        "name": "Apt",
        "usage_growth": 0.75,
        "sr_improvement": 0.70,
        "tier": "growth",
        "mrr": 580,
        "quota_pct": 0.73,
        "expansion_action": "Add 2nd Robot Arm",
        "expansion_value": 600,
        "upgrade_readiness": 0.84,
        "quadrant": "expand",
        "notes": "Expanding to 2nd arm doubles GPU allocation and MRR",
    },
    {
        "name": "1X",
        "usage_growth": 0.40,
        "sr_improvement": 0.35,
        "tier": "starter",
        "mrr": 320,
        "quota_pct": 0.45,
        "expansion_action": "SR Improvement Required",
        "expansion_value": 400,
        "upgrade_readiness": 0.42,
        "quadrant": "nurture",
        "notes": "Needs SR >60% to justify expansion; currently at 45%",
    },
    {
        "name": "NewCo-A",
        "usage_growth": 0.55,
        "sr_improvement": 0.60,
        "tier": "pipeline",
        "mrr": 0,
        "quota_pct": 0.0,
        "expansion_action": "Close Starter Deal",
        "expansion_value": 1200,
        "upgrade_readiness": 0.72,
        "quadrant": "pipeline",
        "notes": "New partner in pipeline — logistics automation, 3 robots",
    },
    {
        "name": "NewCo-B",
        "usage_growth": 0.48,
        "sr_improvement": 0.50,
        "tier": "pipeline",
        "mrr": 0,
        "quota_pct": 0.0,
        "expansion_action": "Close Starter Deal",
        "expansion_value": 800,
        "upgrade_readiness": 0.65,
        "quadrant": "pipeline",
        "notes": "New partner in pipeline — warehouse picking, 2 robots",
    },
]

CURRENT_MRR = 2927
PROJECTED_MRR = 6727

WATERFALL = [
    {"label": "Baseline MRR",     "value": 2927, "type": "base"},
    {"label": "PI Enterprise",    "value": 800,  "type": "add"},
    {"label": "Apt 2nd Arm",      "value": 600,  "type": "add"},
    {"label": "1X Recovery",      "value": 400,  "type": "add"},
    {"label": "NewCo-A",          "value": 1200, "type": "add"},
    {"label": "NewCo-B",          "value": 800,  "type": "add"},
    {"label": "Projected MRR",    "value": 6727, "type": "total"},
]


def build_svg_opportunity_matrix() -> str:
    """SVG 1: 2x2 opportunity matrix — usage growth vs SR improvement."""
    w, h = 820, 420
    cx, cy = 80, 40
    cw, ch = 660, 300
    mid_x = cx + cw / 2
    mid_y = cy + ch / 2

    COLORS = {
        "expand":   "#38bdf8",
        "nurture":  "#f59e0b",
        "pipeline": "#a78bfa",
        "at_risk":  "#C74634",
    }
    QUAD_LABELS = [
        {"label": "EXPAND",    "x": mid_x + cw/4, "y": mid_y - ch/4, "color": "#38bdf8"},
        {"label": "NURTURE",   "x": mid_x - cw/4, "y": mid_y - ch/4, "color": "#f59e0b"},
        {"label": "AT RISK",   "x": mid_x - cw/4, "y": mid_y + ch/4, "color": "#C74634"},
        {"label": "WATCH",     "x": mid_x + cw/4, "y": mid_y + ch/4, "color": "#94a3b8"},
    ]

    def px(v): return cx + v * cw
    def py(v): return cy + ch - v * ch

    # Quadrant backgrounds
    quads = (
        f'<rect x="{mid_x}" y="{cy}" width="{cw/2}" height="{ch/2}" fill="#38bdf8" opacity="0.06" rx="0"/>'
        f'<rect x="{cx}" y="{cy}" width="{cw/2}" height="{ch/2}" fill="#f59e0b" opacity="0.05" rx="0"/>'
        f'<rect x="{cx}" y="{mid_y}" width="{cw/2}" height="{ch/2}" fill="#C74634" opacity="0.06" rx="0"/>'
        f'<rect x="{mid_x}" y="{mid_y}" width="{cw/2}" height="{ch/2}" fill="#475569" opacity="0.05" rx="0"/>'
    )

    qlabels = "".join(
        f'<text x="{q["x"]:.1f}" y="{q["y"]:.1f}" fill="{q["color"]}" font-size="13" '
        f'font-weight="bold" text-anchor="middle" opacity="0.5">{q["label"]}</text>'
        for q in QUAD_LABELS
    )

    dots = ""
    for p in PARTNERS:
        dx = px(p["usage_growth"])
        dy = py(p["sr_improvement"])
        color = COLORS.get(p["quadrant"], "#94a3b8")
        r = 22 if p["quadrant"] == "expand" else 16
        dots += f'<circle cx="{dx:.1f}" cy="{dy:.1f}" r="{r}" fill="{color}" opacity="0.85"/>'
        dots += f'<text x="{dx:.1f}" y="{dy+4:.1f}" fill="#0f172a" font-size="11" font-weight="bold" text-anchor="middle">{p["name"]}</text>'
        dots += f'<text x="{dx+r+4:.1f}" y="{dy-8:.1f}" fill="{color}" font-size="10">${p["expansion_value"]}/mo</text>'
        dots += f'<text x="{dx+r+4:.1f}" y="{dy+4:.1f}" fill="#94a3b8" font-size="9">rdns {p["upgrade_readiness"]*100:.0f}%</text>'

    # Grid ticks
    grid = ""
    for v in [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]:
        gx = px(v)
        gy = py(v)
        grid += f'<line x1="{gx:.1f}" y1="{cy}" x2="{gx:.1f}" y2="{cy+ch}" stroke="#1e293b" stroke-width="1"/>'
        grid += f'<line x1="{cx}" y1="{gy:.1f}" x2="{cx+cw}" y2="{gy:.1f}" stroke="#1e293b" stroke-width="1"/>'
        grid += f'<text x="{gx:.1f}" y="{cy+ch+16}" fill="#475569" font-size="10" text-anchor="middle">{int(v*100)}%</text>'
        grid += f'<text x="{cx-8}" y="{gy+4:.1f}" fill="#475569" font-size="10" text-anchor="end">{int(v*100)}%</text>'

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" style="background:#0f172a;border-radius:12px;font-family:monospace">
  <text x="{w//2}" y="24" fill="#f1f5f9" font-size="16" font-weight="bold" text-anchor="middle">Partner Expansion Opportunity Matrix</text>

  {grid}
  {quads}

  <!-- Axes -->
  <line x1="{cx}" y1="{cy}" x2="{cx}" y2="{cy+ch}" stroke="#475569" stroke-width="1.5"/>
  <line x1="{cx}" y1="{cy+ch}" x2="{cx+cw}" y2="{cy+ch}" stroke="#475569" stroke-width="1.5"/>
  <!-- Dividers -->
  <line x1="{mid_x:.1f}" y1="{cy}" x2="{mid_x:.1f}" y2="{cy+ch}" stroke="#334155" stroke-width="1.5" stroke-dasharray="5,3"/>
  <line x1="{cx}" y1="{mid_y:.1f}" x2="{cx+cw}" y2="{mid_y:.1f}" stroke="#334155" stroke-width="1.5" stroke-dasharray="5,3"/>

  {qlabels}
  {dots}

  <text x="{cx+cw//2}" y="{cy+ch+32}" fill="#64748b" font-size="11" text-anchor="middle">Usage Growth →</text>
  <text x="{cx-48}" y="{cy+ch//2}" fill="#64748b" font-size="11" text-anchor="middle" transform="rotate(-90,{cx-48},{cy+ch//2})">SR Improvement →</text>

  <!-- Legend -->
  <circle cx="{cx}" cy="{cy+ch+50}" r="6" fill="#38bdf8"/>
  <text x="{cx+12}" y="{cy+ch+54}" fill="#94a3b8" font-size="11">Expand (PI, Apt)</text>
  <circle cx="{cx+140}" cy="{cy+ch+50}" r="6" fill="#f59e0b"/>
  <text x="{cx+152}" y="{cy+ch+54}" fill="#94a3b8" font-size="11">Nurture (1X)</text>
  <circle cx="{cx+260}" cy="{cy+ch+50}" r="6" fill="#a78bfa"/>
  <text x="{cx+272}" y="{cy+ch+54}" fill="#94a3b8" font-size="11">Pipeline (NewCo-A, B)</text>
</svg>'''
    return svg


def build_svg_waterfall() -> str:
    """SVG 2: Revenue expansion waterfall."""
    w, h = 820, 380
    cx, cy = 60, 40
    cw_total = 700
    bar_w = 80
    gap = (cw_total - len(WATERFALL) * bar_w) / (len(WATERFALL) - 1)
    chart_h = 260
    max_val = 7200

    COLORS_W = {"base": "#C74634", "add": "#38bdf8", "total": "#6ee7b7"}

    running = 0
    bars = ""
    labels = ""
    connectors = ""
    prev_top_y = None
    prev_bar_right = None

    for i, item in enumerate(WATERFALL):
        bx = cx + i * (bar_w + gap)
        color = COLORS_W[item["type"]]

        if item["type"] == "base":
            bot_y = cy + chart_h
            top_y = cy + chart_h - (item["value"] / max_val) * chart_h
            bh = (item["value"] / max_val) * chart_h
        elif item["type"] == "add":
            bot_y = cy + chart_h - (running / max_val) * chart_h
            bh = (item["value"] / max_val) * chart_h
            top_y = bot_y - bh
        else:  # total
            bot_y = cy + chart_h
            bh = (item["value"] / max_val) * chart_h
            top_y = cy + chart_h - bh

        bars += f'<rect x="{bx:.1f}" y="{top_y:.1f}" width="{bar_w}" height="{bh:.1f}" fill="{color}" opacity="0.85" rx="4"/>'
        bars += f'<text x="{bx + bar_w/2:.1f}" y="{top_y - 6:.1f}" fill="{color}" font-size="11" font-weight="bold" text-anchor="middle">${item["value"]:,}</text>'
        labels += f'<text x="{bx + bar_w/2:.1f}" y="{cy + chart_h + 18}" fill="#94a3b8" font-size="10" text-anchor="middle">{item["label"]}</text>'

        # Connector line from previous bar top to this bar bottom
        if prev_top_y is not None and item["type"] == "add":
            connectors += f'<line x1="{prev_bar_right:.1f}" y1="{prev_top_y:.1f}" x2="{bx:.1f}" y2="{bot_y:.1f}" stroke="#334155" stroke-width="1" stroke-dasharray="3,2"/>'

        if item["type"] != "total":
            running += item["value"]
            prev_top_y = top_y
            prev_bar_right = bx + bar_w

    # Grid
    grid = ""
    for v in [0, 1000, 2000, 3000, 4000, 5000, 6000, 7000]:
        gy = cy + chart_h - (v / max_val) * chart_h
        grid += f'<line x1="{cx}" y1="{gy:.1f}" x2="{cx+cw_total}" y2="{gy:.1f}" stroke="#1e293b" stroke-width="1"/>'
        grid += f'<text x="{cx-8}" y="{gy+4:.1f}" fill="#475569" font-size="10" text-anchor="end">${v//1000}k</text>'

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" style="background:#0f172a;border-radius:12px;font-family:monospace">
  <text x="{w//2}" y="24" fill="#f1f5f9" font-size="16" font-weight="bold" text-anchor="middle">Revenue Expansion Waterfall — Jun MRR</text>

  {grid}
  <line x1="{cx}" y1="{cy}" x2="{cx}" y2="{cy+chart_h}" stroke="#475569" stroke-width="1.5"/>
  <line x1="{cx}" y1="{cy+chart_h}" x2="{cx+cw_total}" y2="{cy+chart_h}" stroke="#475569" stroke-width="1.5"/>

  {connectors}
  {bars}
  {labels}

  <!-- Delta annotation -->
  <text x="{cx+cw_total//2}" y="{cy+chart_h+36}" fill="#6ee7b7" font-size="12" text-anchor="middle" font-weight="bold">+${PROJECTED_MRR - CURRENT_MRR:,} expansion · {((PROJECTED_MRR/CURRENT_MRR - 1)*100):.0f}% NRR growth</text>

  <!-- Legend -->
  <rect x="{cx}" y="{cy+chart_h+52}" width="14" height="10" fill="#C74634" rx="2"/>
  <text x="{cx+18}" y="{cy+chart_h+62}" fill="#94a3b8" font-size="11">Baseline</text>
  <rect x="{cx+100}" y="{cy+chart_h+52}" width="14" height="10" fill="#38bdf8" rx="2"/>
  <text x="{cx+118}" y="{cy+chart_h+62}" fill="#94a3b8" font-size="11">Expansion</text>
  <rect x="{cx+220}" y="{cy+chart_h+52}" width="14" height="10" fill="#6ee7b7" rx="2"/>
  <text x="{cx+238}" y="{cy+chart_h+62}" fill="#94a3b8" font-size="11">Projected Total</text>
</svg>'''
    return svg


def build_html() -> str:
    svg1 = build_svg_opportunity_matrix()
    svg2 = build_svg_waterfall()

    expand_qualified = [p for p in PARTNERS if p["quadrant"] == "expand"]
    pipeline_partners = [p for p in PARTNERS if p["quadrant"] == "pipeline"]
    avg_readiness = sum(p["upgrade_readiness"] for p in expand_qualified) / len(expand_qualified) if expand_qualified else 0
    total_expansion = sum(p["expansion_value"] for p in PARTNERS)
    nrr_pct = round((PROJECTED_MRR / CURRENT_MRR - 1) * 100, 1)

    partner_rows = "".join(
        f"""<tr>
          <td>{p['name']}</td>
          <td><span style='background:#1e293b;padding:2px 8px;border-radius:4px;'>{p['tier']}</span></td>
          <td>${p['mrr']:,}</td>
          <td style='color:#38bdf8'>{p['upgrade_readiness']*100:.0f}%</td>
          <td>{p['expansion_action']}</td>
          <td style='color:#6ee7b7'>+${p['expansion_value']:,}</td>
          <td style='color:#94a3b8;font-size:0.8rem'>{p['notes']}</td>
        </tr>"""
        for p in PARTNERS
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Partner Expansion Planner — Port 8303</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #f1f5f9; font-family: 'Courier New', monospace; padding: 24px; }}
    h1 {{ color: #C74634; font-size: 1.6rem; margin-bottom: 4px; }}
    .subtitle {{ color: #64748b; font-size: 0.85rem; margin-bottom: 24px; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 16px; margin-bottom: 28px; }}
    .card {{ background: #1e293b; border-radius: 10px; padding: 16px; border-left: 3px solid #C74634; }}
    .card.blue {{ border-left-color: #38bdf8; }}
    .card.green {{ border-left-color: #6ee7b7; }}
    .card.purple {{ border-left-color: #a78bfa; }}
    .card-label {{ color: #64748b; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; }}
    .card-value {{ color: #f1f5f9; font-size: 1.5rem; font-weight: bold; margin-top: 6px; }}
    .card-sub {{ color: #94a3b8; font-size: 0.75rem; margin-top: 4px; }}
    .svg-wrap {{ background: #0f172a; border-radius: 12px; margin-bottom: 24px; overflow-x: auto; }}
    .section-title {{ color: #94a3b8; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.1em; margin-bottom: 10px; }}
    table {{ width: 100%; border-collapse: collapse; margin-bottom: 24px; font-size: 0.85rem; }}
    th {{ background: #1e293b; color: #64748b; font-weight: normal; text-align: left; padding: 8px 12px; text-transform: uppercase; font-size: 0.75rem; letter-spacing: 0.05em; }}
    td {{ padding: 8px 12px; border-bottom: 1px solid #1e293b; }}
    tr:hover td {{ background: #1e293b44; }}
  </style>
</head>
<body>
  <h1>Partner Expansion Planner</h1>
  <div class="subtitle">Port 8303 · Jun MRR: ${CURRENT_MRR:,} → ${PROJECTED_MRR:,} projected · NRR +{nrr_pct}%</div>

  <div class="grid">
    <div class="card blue">
      <div class="card-label">Expansion Qualified</div>
      <div class="card-value">{len(expand_qualified)}</div>
      <div class="card-sub">partners ready to expand</div>
    </div>
    <div class="card">
      <div class="card-label">Avg Readiness Score</div>
      <div class="card-value">{avg_readiness*100:.0f}%</div>
      <div class="card-sub">expand-qualified partners</div>
    </div>
    <div class="card green">
      <div class="card-label">Jun MRR Projected</div>
      <div class="card-value">${PROJECTED_MRR:,}</div>
      <div class="card-sub">from ${CURRENT_MRR:,} baseline</div>
    </div>
    <div class="card purple">
      <div class="card-label">Pipeline Partners</div>
      <div class="card-value">{len(pipeline_partners)}</div>
      <div class="card-sub">new partners to close</div>
    </div>
    <div class="card">
      <div class="card-label">Total Expansion ARR</div>
      <div class="card-value">${total_expansion*12:,}</div>
      <div class="card-sub">${total_expansion:,}/mo potential</div>
    </div>
    <div class="card green">
      <div class="card-label">NRR Contribution</div>
      <div class="card-value">+{nrr_pct}%</div>
      <div class="card-sub">from expansion activity</div>
    </div>
  </div>

  <div class="section-title">Expansion Opportunity Matrix</div>
  <div class="svg-wrap">{svg1}</div>

  <div class="section-title">Revenue Expansion Waterfall</div>
  <div class="svg-wrap">{svg2}</div>

  <div class="section-title">Partner Details</div>
  <table>
    <thead>
      <tr>
        <th>Partner</th>
        <th>Tier</th>
        <th>Current MRR</th>
        <th>Readiness</th>
        <th>Action</th>
        <th>Expansion Value</th>
        <th>Notes</th>
      </tr>
    </thead>
    <tbody>{partner_rows}</tbody>
  </table>

  <div style="color:#475569;font-size:0.75rem;margin-top:16px;">Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} · OCI Robot Cloud · Partner Expansion Planner</div>
</body>
</html>"""


if USE_FASTAPI:
    app = FastAPI(title="Partner Expansion Planner", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return HTMLResponse(content=build_html())

    @app.get("/api/partners")
    async def partners():
        return {
            "partners": PARTNERS,
            "current_mrr": CURRENT_MRR,
            "projected_mrr": PROJECTED_MRR,
            "nrr_pct": round((PROJECTED_MRR / CURRENT_MRR - 1) * 100, 1),
            "expand_qualified": [p["name"] for p in PARTNERS if p["quadrant"] == "expand"],
            "pipeline": [p["name"] for p in PARTNERS if p["quadrant"] == "pipeline"],
        }

    @app.get("/api/waterfall")
    async def waterfall():
        return {"waterfall": WATERFALL, "baseline": CURRENT_MRR, "projected": PROJECTED_MRR}

else:
    import http.server
    import socketserver

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(build_html().encode())

        def log_message(self, format, *args):
            pass


if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8303)
    else:
        print("FastAPI not found — using stdlib HTTP server on port 8303")
        with socketserver.TCPServer(("", 8303), Handler) as httpd:
            httpd.serve_forever()
