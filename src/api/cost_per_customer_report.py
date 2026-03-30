"""cost_per_customer_report.py — Per-customer profitability reports with cost attribution and margin analysis.
Port: 8314
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
from datetime import datetime

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------
PARTNERS = [
    {"name": "PI",  "revenue": 850, "compute_cost": 120, "infra_overhead": 50, "support_cost": 30, "platform_share": 47},
    {"name": "Apt", "revenue": 720, "compute_cost": 140, "infra_overhead": 55, "support_cost": 40, "platform_share": 31},
    {"name": "1X",  "revenue": 410, "compute_cost": 130, "infra_overhead": 55, "support_cost": 35, "platform_share": 0},
    {"name": "Agbt","revenue": 530, "compute_cost": 95,  "infra_overhead": 40, "support_cost": 25, "platform_share": 21},
    {"name": "Phy", "revenue": 417, "compute_cost": 88,  "infra_overhead": 38, "support_cost": 22, "platform_share": 17},
]

# Monthly gross margin % per partner over 3 months (Jan, Feb, Mar)
MARGIN_TREND = {
    "PI":   [68, 70, 71],
    "Apt":  [59, 61, 63],
    "1X":   [50, 51, 51],
    "Agbt": [60, 62, 64],
    "Phy":  [61, 63, 65],
}

PRICING_EVENTS = [
    {"partner": "PI",  "month_idx": 1, "label": "Tier upgrade"},
    {"partner": "Apt", "month_idx": 2, "label": "Rate adj."},
]

PLATFORM_AVG_MARGIN = 68
MARCH_REVENUE = 2927
MARCH_COGS = 936
MARCH_GROSS_MARGIN = round((MARCH_REVENUE - MARCH_COGS) / MARCH_REVENUE * 100, 1)
TARGET_MARGIN = 75
TARGET_MONTH = "Sep 2026"

# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------

def build_waterfall_svg() -> str:
    """SVG 1: Customer P&L waterfall for each of 5 partners."""
    W, H = 900, 320
    pad_left, pad_top, pad_bottom = 60, 30, 50
    chart_w = W - pad_left - 20
    chart_h = H - pad_top - pad_bottom

    partner_gap = chart_w // len(PARTNERS)
    bar_w = partner_gap - 20

    cost_keys = ["compute_cost", "infra_overhead", "support_cost", "platform_share"]
    cost_labels = ["Compute", "Infra OH", "Support", "Platform"]
    cost_colors = ["#f87171", "#fb923c", "#facc15", "#a78bfa"]

    max_val = max(p["revenue"] for p in PARTNERS) * 1.1
    y_scale = chart_h / max_val

    svg_parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#1e293b;border-radius:8px">',
        f'<text x="{W//2}" y="18" text-anchor="middle" fill="#e2e8f0" font-size="13" font-family="monospace" font-weight="bold">Customer P&amp;L Waterfall — March 2026</text>',
    ]

    # Y-axis gridlines
    for pct in [0, 25, 50, 75, 100]:
        val = max_val * pct / 100
        y = pad_top + chart_h - val * y_scale
        svg_parts.append(f'<line x1="{pad_left}" y1="{y:.1f}" x2="{W-20}" y2="{y:.1f}" stroke="#334155" stroke-width="1"/>')
        svg_parts.append(f'<text x="{pad_left-4}" y="{y+4:.1f}" text-anchor="end" fill="#94a3b8" font-size="9" font-family="monospace">${val:.0f}</text>')

    for i, p in enumerate(PARTNERS):
        x0 = pad_left + i * partner_gap + 10
        rev = p["revenue"]
        cogs = sum(p[k] for k in cost_keys)
        profit = rev - cogs

        # Revenue bar (full height, semi-transparent)
        rev_h = rev * y_scale
        rev_y = pad_top + chart_h - rev_h
        svg_parts.append(f'<rect x="{x0}" y="{rev_y:.1f}" width="{bar_w}" height="{rev_h:.1f}" fill="#38bdf8" opacity="0.25" rx="2"/>')
        svg_parts.append(f'<text x="{x0 + bar_w//2}" y="{rev_y - 4:.1f}" text-anchor="middle" fill="#38bdf8" font-size="9" font-family="monospace">${rev}</text>')

        # Stacked cost bars from top of revenue bar downward
        cursor_y = rev_y
        for ki, key in enumerate(cost_keys):
            val = p[key]
            if val == 0:
                continue
            seg_h = val * y_scale
            svg_parts.append(f'<rect x="{x0}" y="{cursor_y:.1f}" width="{bar_w}" height="{seg_h:.1f}" fill="{cost_colors[ki]}" rx="1" opacity="0.85"/>')
            if seg_h > 10:
                svg_parts.append(f'<text x="{x0 + bar_w//2}" y="{cursor_y + seg_h/2 + 3:.1f}" text-anchor="middle" fill="#0f172a" font-size="8" font-family="monospace">{cost_labels[ki]}</text>')
            cursor_y += seg_h

        # Profit bar (green/red)
        profit_color = "#4ade80" if profit >= 0 else "#f87171"
        profit_h = abs(profit) * y_scale
        profit_y = cursor_y
        svg_parts.append(f'<rect x="{x0}" y="{profit_y:.1f}" width="{bar_w}" height="{profit_h:.1f}" fill="{profit_color}" rx="2"/>')
        margin_pct = round(profit / rev * 100, 1)
        svg_parts.append(f'<text x="{x0 + bar_w//2}" y="{profit_y + profit_h + 10:.1f}" text-anchor="middle" fill="{profit_color}" font-size="9" font-family="monospace">{margin_pct}%</text>')

        # Partner label
        label_y = pad_top + chart_h + 25
        svg_parts.append(f'<text x="{x0 + bar_w//2}" y="{label_y}" text-anchor="middle" fill="#e2e8f0" font-size="11" font-family="monospace" font-weight="bold">{p["name"]}</text>')

    # Legend
    legend_x = pad_left
    legend_y = H - 10
    for ki, lbl in enumerate(cost_labels):
        svg_parts.append(f'<rect x="{legend_x}" y="{legend_y - 10}" width="10" height="10" fill="{cost_colors[ki]}"/>')
        svg_parts.append(f'<text x="{legend_x + 13}" y="{legend_y}" fill="#94a3b8" font-size="9" font-family="monospace">{lbl}</text>')
        legend_x += 80
    svg_parts.append(f'<rect x="{legend_x}" y="{legend_y - 10}" width="10" height="10" fill="#4ade80"/>')
    svg_parts.append(f'<text x="{legend_x + 13}" y="{legend_y}" fill="#94a3b8" font-size="9" font-family="monospace">Gross Profit</text>')

    svg_parts.append('</svg>')
    return '\n'.join(svg_parts)


def build_margin_trend_svg() -> str:
    """SVG 2: Gross margin trend line per partner over 3 months."""
    W, H = 900, 280
    pad_left, pad_top, pad_bottom = 70, 40, 50
    chart_w = W - pad_left - 30
    chart_h = H - pad_top - pad_bottom

    months = ["Jan", "Feb", "Mar"]
    y_min, y_max = 45, 80
    x_step = chart_w / (len(months) - 1)
    y_scale = chart_h / (y_max - y_min)

    partner_colors = {
        "PI":   "#38bdf8",
        "Apt":  "#a78bfa",
        "1X":   "#f87171",
        "Agbt": "#4ade80",
        "Phy":  "#fb923c",
    }

    svg_parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#1e293b;border-radius:8px">',
        f'<text x="{W//2}" y="20" text-anchor="middle" fill="#e2e8f0" font-size="13" font-family="monospace" font-weight="bold">Gross Margin Trend — Q1 2026 (target 75% by {TARGET_MONTH})</text>',
    ]

    # Target line
    target_y = pad_top + chart_h - (TARGET_MARGIN - y_min) * y_scale
    svg_parts.append(f'<line x1="{pad_left}" y1="{target_y:.1f}" x2="{pad_left + chart_w}" y2="{target_y:.1f}" stroke="#C74634" stroke-width="1.5" stroke-dasharray="6,3"/>')
    svg_parts.append(f'<text x="{pad_left + chart_w + 4}" y="{target_y + 4:.1f}" fill="#C74634" font-size="9" font-family="monospace">75% target</text>')

    # Y-axis gridlines
    for pct in range(y_min, y_max + 1, 5):
        y = pad_top + chart_h - (pct - y_min) * y_scale
        svg_parts.append(f'<line x1="{pad_left}" y1="{y:.1f}" x2="{pad_left + chart_w}" y2="{y:.1f}" stroke="#334155" stroke-width="1"/>')
        svg_parts.append(f'<text x="{pad_left - 5}" y="{y + 4:.1f}" text-anchor="end" fill="#94a3b8" font-size="9" font-family="monospace">{pct}%</text>')

    # X-axis month labels
    for mi, m in enumerate(months):
        x = pad_left + mi * x_step
        svg_parts.append(f'<text x="{x:.1f}" y="{pad_top + chart_h + 18}" text-anchor="middle" fill="#94a3b8" font-size="10" font-family="monospace">{m}</text>')

    # Lines and points per partner
    for pname, color in partner_colors.items():
        vals = MARGIN_TREND[pname]
        points = []
        for mi, v in enumerate(vals):
            px = pad_left + mi * x_step
            py = pad_top + chart_h - (v - y_min) * y_scale
            points.append((px, py))

        # Polyline
        pts_str = ' '.join(f'{px:.1f},{py:.1f}' for px, py in points)
        svg_parts.append(f'<polyline points="{pts_str}" fill="none" stroke="{color}" stroke-width="2"/>')

        # Points
        for px, py in points:
            svg_parts.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="4" fill="{color}"/>')

        # Label at last point
        lx, ly = points[-1]
        svg_parts.append(f'<text x="{lx + 6:.1f}" y="{ly + 4:.1f}" fill="{color}" font-size="10" font-family="monospace">{pname} {vals[-1]}%</text>')

    # Pricing event annotations
    for ev in PRICING_EVENTS:
        pname = ev["partner"]
        mi = ev["month_idx"]
        vals = MARGIN_TREND[pname]
        px = pad_left + mi * x_step
        py = pad_top + chart_h - (vals[mi] - y_min) * y_scale
        color = partner_colors[pname]
        svg_parts.append(f'<line x1="{px:.1f}" y1="{py - 6:.1f}" x2="{px:.1f}" y2="{py - 20:.1f}" stroke="{color}" stroke-width="1"/>')
        svg_parts.append(f'<text x="{px:.1f}" y="{py - 23:.1f}" text-anchor="middle" fill="{color}" font-size="8" font-family="monospace">{ev["label"]}</text>')

    svg_parts.append('</svg>')
    return '\n'.join(svg_parts)


# ---------------------------------------------------------------------------
# HTML page
# ---------------------------------------------------------------------------

def build_html() -> str:
    waterfall_svg = build_waterfall_svg()
    trend_svg = build_margin_trend_svg()

    rows = []
    for p in PARTNERS:
        cogs = sum(p[k] for k in ["compute_cost", "infra_overhead", "support_cost", "platform_share"])
        gp = p["revenue"] - cogs
        gm = round(gp / p["revenue"] * 100, 1)
        color = "#4ade80" if gm >= 65 else ("#facc15" if gm >= 55 else "#f87171")
        rows.append(f"""
          <tr>
            <td style='padding:8px 12px;font-weight:bold;color:#e2e8f0'>{p['name']}</td>
            <td style='padding:8px 12px;color:#38bdf8'>${p['revenue']}</td>
            <td style='padding:8px 12px;color:#f87171'>${p['compute_cost']}</td>
            <td style='padding:8px 12px;color:#fb923c'>${p['infra_overhead']}</td>
            <td style='padding:8px 12px;color:#facc15'>${p['support_cost']}</td>
            <td style='padding:8px 12px;color:#a78bfa'>${p['platform_share']}</td>
            <td style='padding:8px 12px;color:#4ade80'>${gp}</td>
            <td style='padding:8px 12px;font-weight:bold;color:{color}'>{gm}%</td>
          </tr>""")

    table_rows = '\n'.join(rows)

    return f"""<!DOCTYPE html>
<html lang='en'>
<head>
  <meta charset='UTF-8'/>
  <title>Cost Per Customer Report | OCI Robot Cloud</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #e2e8f0; font-family: 'Courier New', monospace; }}
    header {{ background: #1e293b; border-bottom: 2px solid #C74634; padding: 16px 32px; display: flex; align-items: center; gap: 16px; }}
    header h1 {{ font-size: 18px; color: #f8fafc; }}
    .badge {{ background: #C74634; color: #fff; padding: 2px 10px; border-radius: 12px; font-size: 12px; }}
    .port-badge {{ background: #334155; color: #94a3b8; padding: 2px 10px; border-radius: 12px; font-size: 12px; }}
    main {{ padding: 24px 32px; }}
    .kpi-row {{ display: flex; gap: 16px; margin-bottom: 24px; flex-wrap: wrap; }}
    .kpi {{ background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 16px 24px; min-width: 170px; }}
    .kpi .label {{ font-size: 11px; color: #94a3b8; margin-bottom: 6px; }}
    .kpi .val {{ font-size: 24px; font-weight: bold; }}
    .kpi .sub {{ font-size: 11px; color: #64748b; margin-top: 4px; }}
    .chart-section {{ background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 20px; margin-bottom: 24px; }}
    .chart-section h2 {{ font-size: 14px; color: #94a3b8; margin-bottom: 14px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
    thead tr {{ background: #334155; }}
    th {{ padding: 10px 12px; color: #94a3b8; text-align: left; font-weight: normal; }}
    tbody tr:hover {{ background: #1e293b; }}
    tbody tr {{ border-bottom: 1px solid #1e293b; }}
    footer {{ text-align: center; padding: 16px; color: #475569; font-size: 11px; }}
  </style>
</head>
<body>
  <header>
    <div>
      <h1>Cost Per Customer Report</h1>
      <div style='font-size:12px;color:#94a3b8;margin-top:4px'>OCI Robot Cloud — Profitability &amp; Margin Analysis</div>
    </div>
    <div style='margin-left:auto;display:flex;gap:8px;align-items:center'>
      <span class='badge'>Port 8314</span>
      <span class='port-badge'>March 2026</span>
    </div>
  </header>
  <main>
    <div class='kpi-row'>
      <div class='kpi'><div class='label'>March Revenue</div><div class='val' style='color:#38bdf8'>${MARCH_REVENUE:,}</div><div class='sub'>5 partners</div></div>
      <div class='kpi'><div class='label'>March COGS</div><div class='val' style='color:#f87171'>${MARCH_COGS:,}</div><div class='sub'>compute + infra + support</div></div>
      <div class='kpi'><div class='label'>Gross Margin</div><div class='val' style='color:#4ade80'>{MARCH_GROSS_MARGIN}%</div><div class='sub'>platform avg</div></div>
      <div class='kpi'><div class='label'>Best Partner</div><div class='val' style='color:#38bdf8'>PI 71%</div><div class='sub'>tier upgrade Q1</div></div>
      <div class='kpi'><div class='label'>Worst Partner</div><div class='val' style='color:#f87171'>1X 51%</div><div class='sub'>flat usage → fixed OH</div></div>
      <div class='kpi'><div class='label'>Target ({TARGET_MONTH})</div><div class='val' style='color:#C74634'>{TARGET_MARGIN}%</div><div class='sub'>+7pp from current</div></div>
    </div>

    <div class='chart-section'>
      <h2>SVG 1 — Customer P&amp;L Waterfall (Revenue decomposition)</h2>
      {waterfall_svg}
    </div>

    <div class='chart-section'>
      <h2>SVG 2 — Gross Margin Trend by Partner (Q1 2026, with pricing events)</h2>
      {trend_svg}
    </div>

    <div class='chart-section'>
      <h2>COGS Breakdown Table</h2>
      <table>
        <thead><tr>
          <th>Partner</th><th>Revenue ($K)</th><th>Compute</th><th>Infra OH</th><th>Support</th><th>Platform Share</th><th>Gross Profit</th><th>GM%</th>
        </tr></thead>
        <tbody>{table_rows}</tbody>
      </table>
    </div>
  </main>
  <footer>OCI Robot Cloud · Cost Per Customer Report · Port 8314 · Generated {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC</footer>
</body>
</html>"""


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

if USE_FASTAPI:
    app = FastAPI(title="Cost Per Customer Report", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return HTMLResponse(content=build_html())

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "cost_per_customer_report", "port": 8314}

    @app.get("/api/partners")
    async def api_partners():
        result = []
        for p in PARTNERS:
            cogs = sum(p[k] for k in ["compute_cost", "infra_overhead", "support_cost", "platform_share"])
            gp = p["revenue"] - cogs
            result.append({**p, "gross_profit": gp, "gross_margin_pct": round(gp / p["revenue"] * 100, 1)})
        return {"partners": result, "platform_avg_margin": PLATFORM_AVG_MARGIN, "target_margin": TARGET_MARGIN, "target_month": TARGET_MONTH}

else:
    # Fallback: stdlib http.server
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            content = build_html().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

        def log_message(self, fmt, *args):
            pass


if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8314)
    else:
        print("[cost_per_customer_report] FastAPI not found — falling back to stdlib HTTP server on port 8314")
        HTTPServer(("0.0.0.0", 8314), Handler).serve_forever()
