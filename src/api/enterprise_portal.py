"""Enterprise self-service portal for OCI Robot Cloud management (port 8338)."""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

import random
import math
import json
from datetime import datetime, timedelta

# --- Mock Data ---
MOCK_ACTIVE_JOBS = 4
MOCK_MONTHLY_COST = 224.0
MOCK_SR_TREND = [0.65, 0.67, 0.70, 0.71, 0.73, 0.75, 0.76, 0.78]
MOCK_PARTNER_COUNT = 5
MOCK_API_CALLS = 847000
MOCK_OPEN_TICKETS = 2

MOCK_QUOTAS = [
    {"name": "GPU_hours",      "used": 67, "reserved": 15, "available": 18},
    {"name": "API_calls",      "used": 43, "reserved": 22, "available": 35},
    {"name": "fine_tune_runs", "used": 40, "reserved": 10, "available": 50},
    {"name": "eval_runs",      "used": 55, "reserved": 5,  "available": 40},
    {"name": "storage",        "used": 28, "reserved": 12, "available": 60},
]


def _sparkline_path(values, x0, y0, w, h):
    """Generate SVG polyline points for a sparkline."""
    mn, mx = min(values), max(values)
    rng = mx - mn if mx != mn else 1
    pts = []
    for i, v in enumerate(values):
        px = x0 + i * w / (len(values) - 1)
        py = y0 + h - (v - mn) / rng * h
        pts.append(f"{px:.1f},{py:.1f}")
    return " ".join(pts)


def _donut_arc(cx, cy, r, pct, color, stroke_w=10):
    """SVG arc for a donut segment (pct in 0-100)."""
    circ = 2 * math.pi * r
    dash = circ * pct / 100
    return (
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" '
        f'stroke="{color}" stroke-width="{stroke_w}" '
        f'stroke-dasharray="{dash:.2f} {circ:.2f}" '
        f'stroke-dashoffset="0" transform="rotate(-90 {cx} {cy})"/>'
    )


def build_dashboard_svg():
    """SVG 1: 6-widget dashboard grid (2 rows x 3 cols)."""
    widgets = [
        {"label": "Active Jobs",    "value": str(MOCK_ACTIVE_JOBS),    "sub": "running",         "spark": [2,3,4,3,5,4,4,4]},
        {"label": "Monthly Cost",   "value": f"${MOCK_MONTHLY_COST:.0f}", "sub": "this month",   "spark": [180,190,200,195,210,215,220,224]},
        {"label": "SR Trend",       "value": "0.78",                   "sub": "latest",          "spark": MOCK_SR_TREND},
        {"label": "Partners",       "value": str(MOCK_PARTNER_COUNT),  "sub": "active",          "spark": [3,3,4,4,4,5,5,5]},
        {"label": "API Calls",      "value": "847k",                   "sub": "this month",      "spark": [600,650,700,720,760,800,830,847]},
        {"label": "Open Tickets",   "value": str(MOCK_OPEN_TICKETS),   "sub": "support",         "spark": [5,4,4,3,3,2,3,2]},
    ]
    COLS, ROWS = 3, 2
    W, H = 600, 340
    cell_w, cell_h = W // COLS, H // ROWS
    svg_parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'style="background:#1e293b;border-radius:12px;">'
    ]
    colors = ["#C74634", "#38bdf8", "#34d399", "#a78bfa", "#fbbf24", "#fb7185"]
    for i, w in enumerate(widgets):
        col, row = i % COLS, i // COLS
        x0, y0 = col * cell_w, row * cell_h
        c = colors[i]
        # cell background
        svg_parts.append(
            f'<rect x="{x0+6}" y="{y0+6}" width="{cell_w-12}" height="{cell_h-12}" '
            f'rx="8" fill="#0f172a" stroke="{c}" stroke-width="1.5" opacity="0.8"/>'
        )
        # label
        svg_parts.append(
            f'<text x="{x0+16}" y="{y0+30}" font-size="11" fill="#94a3b8" font-family="monospace">{w["label"]}</text>'
        )
        # value
        svg_parts.append(
            f'<text x="{x0+16}" y="{y0+60}" font-size="22" font-weight="bold" fill="{c}" font-family="monospace">{w["value"]}</text>'
        )
        # sub
        svg_parts.append(
            f'<text x="{x0+16}" y="{y0+76}" font-size="10" fill="#64748b" font-family="monospace">{w["sub"]}</text>'
        )
        # sparkline
        spark_x, spark_y = x0 + 16, y0 + cell_h - 40
        spark_w, spark_h = cell_w - 32, 28
        pts = _sparkline_path(w["spark"], spark_x, spark_y, spark_w, spark_h)
        svg_parts.append(
            f'<polyline points="{pts}" fill="none" stroke="{c}" stroke-width="2" opacity="0.9"/>'
        )
        svg_parts.append(
            f'<polyline points="{pts}" fill="{c}" fill-opacity="0.08" stroke="none"/>'
        )
    svg_parts.append('</svg>')
    return "".join(svg_parts)


def build_quota_svg():
    """SVG 2: Usage quota donuts for 5 quota types."""
    N = len(MOCK_QUOTAS)
    W, H = 620, 180
    cx_step = W // N
    COLORS_USED = "#C74634"
    COLORS_RES  = "#38bdf8"
    COLORS_AVAIL = "#1e3a5f"
    R = 42
    svg_parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'style="background:#1e293b;border-radius:12px;">'
    ]
    for i, q in enumerate(MOCK_QUOTAS):
        cx = cx_step * i + cx_step // 2
        cy = H // 2
        # Available (background full circle)
        circ = 2 * math.pi * R
        svg_parts.append(
            f'<circle cx="{cx}" cy="{cy}" r="{R}" fill="none" '
            f'stroke="{COLORS_AVAIL}" stroke-width="10"/>'
        )
        # Reserved arc (offset by used)
        used_dash = circ * q["used"] / 100
        res_dash  = circ * q["reserved"] / 100
        svg_parts.append(
            f'<circle cx="{cx}" cy="{cy}" r="{R}" fill="none" '
            f'stroke="{COLORS_RES}" stroke-width="10" '
            f'stroke-dasharray="{res_dash:.2f} {circ:.2f}" '
            f'stroke-dashoffset="{-used_dash:.2f}" '
            f'transform="rotate(-90 {cx} {cy})"/>'
        )
        # Used arc
        svg_parts.append(_donut_arc(cx, cy, R, q["used"], COLORS_USED, 10))
        # Center label
        svg_parts.append(
            f'<text x="{cx}" y="{cy+5}" text-anchor="middle" font-size="13" '
            f'font-weight="bold" fill="#f1f5f9" font-family="monospace">{q["used"]}%</text>'
        )
        # Name below
        name_disp = q["name"].replace("_", " ")
        svg_parts.append(
            f'<text x="{cx}" y="{cy + R + 18}" text-anchor="middle" font-size="9" '
            f'fill="#94a3b8" font-family="monospace">{name_disp}</text>'
        )
    # Legend
    lx, ly = 10, 14
    for color, label in [(COLORS_USED, "used"), (COLORS_RES, "reserved"), (COLORS_AVAIL, "available")]:
        svg_parts.append(f'<rect x="{lx}" y="{ly-8}" width="10" height="10" fill="{color}"/>')
        svg_parts.append(f'<text x="{lx+14}" y="{ly+1}" font-size="9" fill="#94a3b8" font-family="monospace">{label}</text>')
        lx += 70
    svg_parts.append('</svg>')
    return "".join(svg_parts)


HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>OCI Robot Cloud — Enterprise Portal</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #0f172a; color: #e2e8f0; font-family: 'Courier New', monospace; }}
  header {{ background: #1e293b; border-bottom: 2px solid #C74634; padding: 18px 32px;
            display: flex; align-items: center; gap: 16px; }}
  header h1 {{ font-size: 1.4rem; color: #f1f5f9; }}
  header span.badge {{ background: #C74634; color: #fff; padding: 2px 10px;
                       border-radius: 12px; font-size: 0.75rem; }}
  main {{ padding: 28px 32px; }}
  h2 {{ font-size: 1rem; color: #38bdf8; margin-bottom: 14px; letter-spacing: 0.05em; }}
  .section {{ margin-bottom: 36px; }}
  .svg-wrap {{ overflow-x: auto; }}
  .metrics-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; margin-bottom: 28px; }}
  .metric-card {{ background: #1e293b; border: 1px solid #334155; border-radius: 8px;
                  padding: 16px 18px; }}
  .metric-card .label {{ font-size: 0.75rem; color: #64748b; margin-bottom: 4px; }}
  .metric-card .val {{ font-size: 1.5rem; font-weight: bold; color: #38bdf8; }}
  .metric-card .desc {{ font-size: 0.7rem; color: #475569; margin-top: 4px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.82rem; }}
  th {{ text-align: left; color: #38bdf8; border-bottom: 1px solid #334155; padding: 8px 10px; }}
  td {{ padding: 8px 10px; border-bottom: 1px solid #1e293b; color: #cbd5e1; }}
  tr:hover td {{ background: #1e293b; }}
  footer {{ text-align: center; padding: 20px; font-size: 0.7rem; color: #334155; }}
</style>
</head>
<body>
<header>
  <div style="width:32px;height:32px;background:#C74634;border-radius:6px;
              display:flex;align-items:center;justify-content:center;font-weight:bold;">R</div>
  <h1>OCI Robot Cloud — Enterprise Portal</h1>
  <span class="badge">PORT 8338</span>
  <span style="margin-left:auto;font-size:0.75rem;color:#64748b;">Updated: {timestamp}</span>
</header>
<main>
  <div class="metrics-grid">
    <div class="metric-card">
      <div class="label">Active Jobs</div>
      <div class="val" style="color:#C74634;">{active_jobs}</div>
      <div class="desc">running fine-tune / eval tasks</div>
    </div>
    <div class="metric-card">
      <div class="label">Monthly Cost</div>
      <div class="val">${monthly_cost:.0f}</div>
      <div class="desc">current billing cycle</div>
    </div>
    <div class="metric-card">
      <div class="label">Latest SR</div>
      <div class="val" style="color:#34d399;">0.78</div>
      <div class="desc">success rate (trend +0.13)</div>
    </div>
    <div class="metric-card">
      <div class="label">Active Partners</div>
      <div class="val" style="color:#a78bfa;">{partners}</div>
      <div class="desc">enterprise integrations</div>
    </div>
    <div class="metric-card">
      <div class="label">API Calls</div>
      <div class="val" style="color:#fbbf24;">847k</div>
      <div class="desc">this billing period</div>
    </div>
    <div class="metric-card">
      <div class="label">Open Tickets</div>
      <div class="val" style="color:#fb7185;">{tickets}</div>
      <div class="desc">support backlog</div>
    </div>
  </div>

  <div class="section">
    <h2>DASHBOARD OVERVIEW</h2>
    <div class="svg-wrap">{dashboard_svg}</div>
  </div>

  <div class="section">
    <h2>QUOTA UTILIZATION</h2>
    <div class="svg-wrap">{quota_svg}</div>
  </div>

  <div class="section">
    <h2>ACTIVE JOBS</h2>
    <table>
      <thead><tr><th>Job ID</th><th>Type</th><th>Status</th><th>Progress</th><th>ETA</th></tr></thead>
      <tbody>
        <tr><td>job-9a1f</td><td>fine_tune</td><td style="color:#34d399;">running</td><td>68%</td><td>~14 min</td></tr>
        <tr><td>job-3c7d</td><td>eval</td><td style="color:#34d399;">running</td><td>42%</td><td>~6 min</td></tr>
        <tr><td>job-b2e8</td><td>sdg</td><td style="color:#fbbf24;">queued</td><td>0%</td><td>~31 min</td></tr>
        <tr><td>job-f1a0</td><td>inference</td><td style="color:#34d399;">running</td><td>91%</td><td>~2 min</td></tr>
      </tbody>
    </table>
  </div>

  <div class="section">
    <h2>OPEN SUPPORT TICKETS</h2>
    <table>
      <thead><tr><th>Ticket</th><th>Subject</th><th>Priority</th><th>Opened</th></tr></thead>
      <tbody>
        <tr><td>#T-0041</td><td>GPU allocation timeout on A100 pool</td><td style="color:#C74634;">HIGH</td><td>2 days ago</td></tr>
        <tr><td>#T-0039</td><td>Checkpoint export format question</td><td style="color:#fbbf24;">MEDIUM</td><td>5 days ago</td></tr>
      </tbody>
    </table>
  </div>
</main>
<footer>OCI Robot Cloud Enterprise Portal &mdash; port 8338 &mdash; Oracle Confidential</footer>
</body>
</html>
"""


def render_page():
    return HTML_TEMPLATE.format(
        timestamp=datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        active_jobs=MOCK_ACTIVE_JOBS,
        monthly_cost=MOCK_MONTHLY_COST,
        partners=MOCK_PARTNER_COUNT,
        tickets=MOCK_OPEN_TICKETS,
        dashboard_svg=build_dashboard_svg(),
        quota_svg=build_quota_svg(),
    )


if HAS_FASTAPI:
    app = FastAPI(title="Enterprise Portal", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def index():
        return render_page()

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "enterprise_portal", "port": 8338}

    @app.get("/api/summary")
    async def summary():
        return {
            "active_jobs": MOCK_ACTIVE_JOBS,
            "monthly_cost_usd": MOCK_MONTHLY_COST,
            "sr_trend": MOCK_SR_TREND,
            "partner_count": MOCK_PARTNER_COUNT,
            "api_calls": MOCK_API_CALLS,
            "open_tickets": MOCK_OPEN_TICKETS,
            "quotas": MOCK_QUOTAS,
        }

else:
    # Fallback: stdlib http.server
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = render_page().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass


if __name__ == "__main__":
    if HAS_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8338)
    else:
        print("FastAPI not found — starting stdlib server on port 8338")
        HTTPServer(("0.0.0.0", 8338), _Handler).serve_forever()
