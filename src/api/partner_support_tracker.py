"""Partner Support Tracker — OCI Robot Cloud (port 8242)

Tracks partner support tickets, resolution times, and satisfaction scores.
Provides SLA compliance monitoring and partner churn risk signals.
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
from datetime import datetime, timedelta

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

random.seed(42)

CATEGORIES = [
    {"name": "integration",     "count": 16, "avg_days": 3.1, "color": "#38bdf8"},
    {"name": "performance",     "count": 10, "avg_days": 2.4, "color": "#818cf8"},
    {"name": "billing",         "count": 6,  "avg_days": 0.8, "color": "#34d399"},
    {"name": "data",            "count": 6,  "avg_days": 2.9, "color": "#fbbf24"},
    {"name": "hardware",        "count": 5,  "avg_days": 4.2, "color": "#f87171"},
    {"name": "feature_request", "count": 4,  "avg_days": 1.5, "color": "#c084fc"},
]

MONTHLY = [
    {"month": "Oct", "tickets": 5,  "csat": 3.8, "avg_response_hrs": 8.2},
    {"month": "Nov", "tickets": 7,  "csat": 3.9, "avg_response_hrs": 7.5},
    {"month": "Dec", "tickets": 6,  "csat": 4.0, "avg_response_hrs": 6.8},
    {"month": "Jan", "tickets": 9,  "csat": 4.1, "avg_response_hrs": 5.9},
    {"month": "Feb", "tickets": 11, "csat": 4.1, "avg_response_hrs": 5.3},
    {"month": "Mar", "tickets": 9,  "csat": 4.2, "avg_response_hrs": 4.8},
]

PARTNERS = [
    {"name": "Acme Robotics",    "tier": "Enterprise", "open": 2, "csat": 4.5, "sla_hit": 98, "churn_risk": "Low"},
    {"name": "FutureFab Inc",    "tier": "Enterprise", "open": 1, "csat": 4.3, "sla_hit": 96, "churn_risk": "Low"},
    {"name": "RoboLogix",        "tier": "Standard",   "open": 3, "csat": 3.6, "sla_hit": 81, "churn_risk": "Medium"},
    {"name": "NexGen Automation","tier": "Standard",   "open": 1, "csat": 4.0, "sla_hit": 89, "churn_risk": "Low"},
    {"name": "Synapse Systems",  "tier": "Startup",    "open": 4, "csat": 3.2, "sla_hit": 74, "churn_risk": "High"},
]

TOTAL_TICKETS = 47
OVERALL_CSAT  = 4.2
SLA_COMPLIANCE = 91.5
AVG_RESOLUTION = 2.3
REPEAT_RATE    = 14.0

# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------

def build_donut_svg() -> str:
    """Donut chart of ticket categories."""
    cx, cy, r_outer, r_inner = 200, 200, 150, 80
    total = sum(c["count"] for c in CATEGORIES)
    segments = []
    labels   = []
    angle    = -math.pi / 2   # start at top

    for cat in CATEGORIES:
        sweep = 2 * math.pi * cat["count"] / total
        x1 = cx + r_outer * math.cos(angle)
        y1 = cy + r_outer * math.sin(angle)
        x2 = cx + r_outer * math.cos(angle + sweep)
        y2 = cy + r_outer * math.sin(angle + sweep)
        xi1 = cx + r_inner * math.cos(angle + sweep)
        yi1 = cy + r_inner * math.sin(angle + sweep)
        xi2 = cx + r_inner * math.cos(angle)
        yi2 = cy + r_inner * math.sin(angle)
        large = 1 if sweep > math.pi else 0
        d = (f"M {x1:.1f} {y1:.1f} "
             f"A {r_outer} {r_outer} 0 {large} 1 {x2:.1f} {y2:.1f} "
             f"L {xi1:.1f} {yi1:.1f} "
             f"A {r_inner} {r_inner} 0 {large} 0 {xi2:.1f} {yi2:.1f} Z")
        segments.append(f'<path d="{d}" fill="{cat["color"]}" opacity="0.9"/>')

        # label at midpoint of arc
        mid = angle + sweep / 2
        lx = cx + (r_outer + 22) * math.cos(mid)
        ly = cy + (r_outer + 22) * math.sin(mid)
        pct = round(cat["count"] / total * 100)
        labels.append(
            f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="middle" '
            f'fill="#94a3b8" font-size="11" font-family="monospace">{pct}%</text>'
        )
        angle += sweep

    # legend — right side
    legend_items = []
    for i, cat in enumerate(CATEGORIES):
        lx = 400
        ly = 90 + i * 38
        legend_items.append(
            f'<rect x="{lx}" y="{ly}" width="14" height="14" fill="{cat["color"]}" rx="3"/>'
            f'<text x="{lx+20}" y="{ly+11}" fill="#e2e8f0" font-size="12" font-family="monospace">{cat["name"]}</text>'
            f'<text x="{lx+170}" y="{ly+11}" fill="#94a3b8" font-size="11" font-family="monospace" text-anchor="end">{cat["count"]} tickets / {cat["avg_days"]}d</text>'
        )

    center_label = (
        f'<text x="{cx}" y="{cy-8}" text-anchor="middle" fill="#f8fafc" font-size="28" font-weight="bold" font-family="monospace">{total}</text>'
        f'<text x="{cx}" y="{cy+14}" text-anchor="middle" fill="#94a3b8" font-size="12" font-family="monospace">tickets</text>'
    )

    return (
        '<svg viewBox="0 0 600 400" xmlns="http://www.w3.org/2000/svg" '
        'style="background:#1e293b;border-radius:12px;width:100%;max-width:600px;">'
        + "".join(segments) + center_label + "".join(labels) + "".join(legend_items)
        + "</svg>"
    )


def build_line_chart_svg() -> str:
    """Dual-axis line chart: monthly ticket volume + CSAT."""
    W, H    = 620, 320
    PAD_L   = 60
    PAD_R   = 70
    PAD_T   = 30
    PAD_B   = 50
    cw      = W - PAD_L - PAD_R
    ch      = H - PAD_T - PAD_B
    months  = MONTHLY
    n       = len(months)
    xs      = [PAD_L + i * cw / (n - 1) for i in range(n)]

    # ticket axis: 0 – 14
    max_t = 14
    def ty(v): return PAD_T + ch - (v / max_t) * ch

    # csat axis: 3.5 – 5.0
    csat_min, csat_max = 3.5, 5.0
    def cy_fn(v): return PAD_T + ch - ((v - csat_min) / (csat_max - csat_min)) * ch

    # grid lines
    grids = ""
    for g in [2, 4, 6, 8, 10, 12, 14]:
        gy = ty(g)
        grids += f'<line x1="{PAD_L}" y1="{gy:.1f}" x2="{W - PAD_R}" y2="{gy:.1f}" stroke="#334155" stroke-width="1"/>'
        grids += f'<text x="{PAD_L - 8}" y="{gy + 4:.1f}" text-anchor="end" fill="#64748b" font-size="10" font-family="monospace">{g}</text>'

    for g in [3.5, 4.0, 4.5, 5.0]:
        gy = cy_fn(g)
        grids += f'<text x="{W - PAD_R + 8}" y="{gy + 4:.1f}" fill="#64748b" font-size="10" font-family="monospace">{g}</text>'

    # ticket polyline
    tpts = " ".join(f"{xs[i]:.1f},{ty(m['tickets']):.1f}" for i, m in enumerate(months))
    ticket_line = (
        f'<polyline points="{tpts}" fill="none" stroke="#38bdf8" stroke-width="2.5" stroke-linejoin="round"/>'
    )
    ticket_dots = "".join(
        f'<circle cx="{xs[i]:.1f}" cy="{ty(m["tickets"]):.1f}" r="4" fill="#38bdf8"/>'
        f'<text x="{xs[i]:.1f}" y="{ty(m["tickets"]) - 10:.1f}" text-anchor="middle" fill="#38bdf8" font-size="10" font-family="monospace">{m["tickets"]}</text>'
        for i, m in enumerate(months)
    )

    # csat polyline
    cpts = " ".join(f"{xs[i]:.1f},{cy_fn(m['csat']):.1f}" for i, m in enumerate(months))
    csat_line = (
        f'<polyline points="{cpts}" fill="none" stroke="#34d399" stroke-width="2.5" stroke-linejoin="round" stroke-dasharray="6 3"/>'
    )
    csat_dots = "".join(
        f'<circle cx="{xs[i]:.1f}" cy="{cy_fn(m["csat"]):.1f}" r="4" fill="#34d399"/>'
        f'<text x="{xs[i]:.1f}" y="{cy_fn(m["csat"]) - 10:.1f}" text-anchor="middle" fill="#34d399" font-size="10" font-family="monospace">{m["csat"]}</text>'
        for i, m in enumerate(months)
    )

    # x-axis labels
    xlabels = "".join(
        f'<text x="{xs[i]:.1f}" y="{H - PAD_B + 18}" text-anchor="middle" fill="#94a3b8" font-size="12" font-family="monospace">{m["month"]}</text>'
        for i, m in enumerate(months)
    )

    # axis titles
    axis_titles = (
        f'<text x="{PAD_L - 50}" y="{PAD_T + ch // 2}" text-anchor="middle" fill="#38bdf8" font-size="11" font-family="monospace" transform="rotate(-90 {PAD_L - 50} {PAD_T + ch // 2})">Ticket Volume</text>'
        f'<text x="{W - PAD_R + 55}" y="{PAD_T + ch // 2}" text-anchor="middle" fill="#34d399" font-size="11" font-family="monospace" transform="rotate(90 {W - PAD_R + 55} {PAD_T + ch // 2})">CSAT (0–5)</text>'
    )

    legend = (
        f'<rect x="{PAD_L}" y="8" width="12" height="4" fill="#38bdf8" rx="2"/>'
        f'<text x="{PAD_L + 18}" y="14" fill="#e2e8f0" font-size="11" font-family="monospace">Ticket Volume</text>'
        f'<rect x="{PAD_L + 130}" y="8" width="12" height="4" fill="#34d399" rx="2"/>'
        f'<text x="{PAD_L + 148}" y="14" fill="#e2e8f0" font-size="11" font-family="monospace">CSAT Score</text>'
    )

    return (
        f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" '
        f'style="background:#1e293b;border-radius:12px;width:100%;max-width:{W}px;">'
        + grids + ticket_line + ticket_dots + csat_line + csat_dots + xlabels + axis_titles + legend
        + "</svg>"
    )


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def build_html() -> str:
    donut_svg = build_donut_svg()
    line_svg  = build_line_chart_svg()

    churn_rows = ""
    for p in PARTNERS:
        risk_color = {"Low": "#34d399", "Medium": "#fbbf24", "High": "#f87171"}[p["churn_risk"]]
        churn_rows += (
            f'<tr>'
            f'<td>{p["name"]}</td>'
            f'<td><span style="background:#1e293b;padding:2px 8px;border-radius:9999px;font-size:11px">{p["tier"]}</span></td>'
            f'<td>{p["open"]}</td>'
            f'<td>{p["csat"]}</td>'
            f'<td>{p["sla_hit"]}%</td>'
            f'<td><span style="color:{risk_color};font-weight:600">{p["churn_risk"]}</span></td>'
            f'</tr>'
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Partner Support Tracker — OCI Robot Cloud</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; padding: 24px; }}
  h1   {{ font-size: 1.6rem; color: #f8fafc; margin-bottom: 4px; }}
  h2   {{ font-size: 1.1rem; color: #94a3b8; margin: 28px 0 12px; }}
  .subtitle {{ color: #64748b; font-size: 0.85rem; margin-bottom: 24px; }}
  .kpi-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px; margin-bottom: 32px; }}
  .kpi {{ background: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 20px; }}
  .kpi .val {{ font-size: 2rem; font-weight: 700; color: #38bdf8; line-height: 1.1; }}
  .kpi .lbl {{ font-size: 0.78rem; color: #64748b; margin-top: 4px; }}
  .kpi .sub {{ font-size: 0.72rem; color: #475569; margin-top: 2px; }}
  .oracle-red {{ color: #C74634; }}
  .chart-card {{ background: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 20px; margin-bottom: 28px; }}
  .chart-title {{ font-size: 0.95rem; font-weight: 600; color: #cbd5e1; margin-bottom: 14px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.85rem; }}
  th {{ text-align: left; color: #64748b; font-weight: 500; padding: 8px 12px; border-bottom: 1px solid #334155; }}
  td {{ padding: 10px 12px; border-bottom: 1px solid #1e293b; color: #cbd5e1; }}
  tr:hover td {{ background: #0f172a; }}
  .footer {{ margin-top: 40px; font-size: 0.75rem; color: #334155; text-align: center; }}
</style>
</head>
<body>
<h1>Partner Support Tracker <span class="oracle-red">&#9679;</span> OCI Robot Cloud</h1>
<p class="subtitle">Ticket analytics, SLA compliance, and churn risk signals &mdash; port 8242</p>

<div class="kpi-grid">
  <div class="kpi"><div class="val">{TOTAL_TICKETS}</div><div class="lbl">Total Tickets</div><div class="sub">last 6 months</div></div>
  <div class="kpi"><div class="val">{OVERALL_CSAT}/5</div><div class="lbl">Overall CSAT</div><div class="sub">partner satisfaction</div></div>
  <div class="kpi"><div class="val">{SLA_COMPLIANCE}%</div><div class="lbl">SLA Compliance</div><div class="sub">enterprise 4h SLA</div></div>
  <div class="kpi"><div class="val">{AVG_RESOLUTION}d</div><div class="lbl">Avg Resolution</div><div class="sub">all categories</div></div>
  <div class="kpi"><div class="val">{REPEAT_RATE}%</div><div class="lbl">Repeat Ticket Rate</div><div class="sub">same partner same issue</div></div>
</div>

<div class="chart-card">
  <div class="chart-title">Ticket Categories — Distribution &amp; Avg Resolution Time</div>
  {donut_svg}
</div>

<div class="chart-card">
  <div class="chart-title">Monthly Ticket Volume &amp; CSAT Trend (Oct&ndash;Mar)</div>
  {line_svg}
</div>

<h2>Partner Churn Risk Dashboard</h2>
<div class="chart-card">
  <table>
    <thead><tr><th>Partner</th><th>Tier</th><th>Open Tickets</th><th>CSAT</th><th>SLA Hit</th><th>Churn Risk</th></tr></thead>
    <tbody>{churn_rows}</tbody>
  </table>
</div>

<div class="footer">OCI Robot Cloud &bull; Partner Support Tracker &bull; port 8242 &bull; {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

if USE_FASTAPI:
    app = FastAPI(title="Partner Support Tracker", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return build_html()

    @app.get("/api/summary")
    async def summary():
        return {
            "total_tickets":   TOTAL_TICKETS,
            "overall_csat":    OVERALL_CSAT,
            "sla_compliance":  SLA_COMPLIANCE,
            "avg_resolution_days": AVG_RESOLUTION,
            "repeat_ticket_rate":  REPEAT_RATE,
            "categories":      CATEGORIES,
            "monthly":         MONTHLY,
            "partners":        PARTNERS,
        }

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "partner-support-tracker", "port": 8242}

else:
    # stdlib fallback
    import http.server
    import socketserver

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            body = build_html().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        def log_message(self, *a): pass


if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8242)
    else:
        with socketserver.TCPServer(("", 8242), Handler) as srv:
            print("Serving on http://0.0.0.0:8242  (stdlib fallback)")
            srv.serve_forever()
