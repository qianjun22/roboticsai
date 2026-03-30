# Board Metrics Dashboard — port 8915
# 16 board KPIs with traffic-light RAG status, sparklines, and summary grid

import math
import random

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

TITLE = "Board Metrics Dashboard"
PORT = 8915

# Seed for reproducible sparkline noise
random.seed(42)

# --- KPI definitions ---
# status: G=green, A=amber, R=red
KPIS = [
    # name,        value,    unit,   status, trend_dir, description
    ("ARR",        "$4.2M",  "",     "G",    +1,  "Annual Recurring Revenue"),
    ("MRR",        "$350K",  "",     "G",    +1,  "Monthly Recurring Revenue"),
    ("NRR",        "118%",   "",     "G",    +1,  "Net Revenue Retention"),
    ("Gross Margin","71%",  "",     "G",    +1,  "Revenue minus COGS"),
    ("Burn Rate",  "$280K",  "/mo",  "A",    -1,  "Monthly cash burn"),
    ("Runway",     "18 mo",  "",     "G",    0,   "Months of cash remaining"),
    ("CAC",        "$14.2K", "",     "A",    -1,  "Customer Acquisition Cost"),
    ("LTV",        "$88K",   "",     "G",    +1,  "Customer Lifetime Value"),
    ("LTV/CAC",    "6.2×",   "",     "G",    +1,  "LTV to CAC ratio"),
    ("Customers",  "47",     "",     "G",    +1,  "Paying design partners"),
    ("Churn",      "3.8%",   "",     "A",    -1,  "Annual logo churn rate"),
    ("Pipeline",   "$18.6M", "",     "G",    +1,  "Qualified sales pipeline"),
    ("NPS",        "62",     "",     "G",    +1,  "Net Promoter Score"),
    ("SR",         "77%",    "",     "G",    +1,  "Task Success Rate (robot)"),
    ("Latency",    "227ms",  "",     "R",    -1,  "Inference latency p50"),
    ("Cost/Run",   "$0.0043","",     "R",    0,   "Cost per 10K inference steps"),
]

STATUS_COLOR = {"G": "#22c55e", "A": "#f59e0b", "R": "#ef4444"}
STATUS_LABEL = {"G": "On Track", "A": "Monitor", "R": "Action Needed"}

# Summary counts
GREEN_COUNT = sum(1 for k in KPIS if k[3] == "G")
AMBER_COUNT = sum(1 for k in KPIS if k[3] == "A")
RED_COUNT   = sum(1 for k in KPIS if k[3] == "R")


def _sparkline_svg(status, trend_dir, w=80, h=32):
    """Generate a small inline sparkline SVG with subtle noise."""
    n = 12
    base = [0.35 + (i / (n - 1)) * 0.45 * trend_dir for i in range(n)]  # gentle trend
    vals = [max(0.05, min(0.95, base[i] + random.uniform(-0.07, 0.07))) for i in range(n)]
    mn, mx = min(vals), max(vals)
    rng = mx - mn if mx != mn else 0.1
    pts = []
    for i, v in enumerate(vals):
        px = 2 + (i / (n - 1)) * (w - 4)
        py = 2 + (h - 4) - ((v - mn) / rng) * (h - 4)
        pts.append(f"{px:.1f},{py:.1f}")
    color = STATUS_COLOR[status]
    poly = f'<polyline points="{" ".join(pts)}" fill="none" stroke="{color}" stroke-width="1.5" stroke-linejoin="round" stroke-linecap="round"/>'
    # area fill
    area_pts = pts + [f"{2 + (w - 4):.1f},{h - 2}", f"2,{h - 2}"]
    area = f'<polygon points="{" ".join(area_pts)}" fill="{color}" fill-opacity="0.12"/>'
    return f'<svg width="{w}" height="{h}" xmlns="http://www.w3.org/2000/svg">{area}{poly}</svg>'


def _rag_badge(status):
    color = STATUS_COLOR[status]
    label = STATUS_LABEL[status]
    return f'<span style="background:{color}22;color:{color};border:1px solid {color}55;border-radius:12px;padding:2px 10px;font-size:0.72rem;font-weight:600">{label}</span>'


def _trend_arrow(trend_dir):
    if trend_dir > 0:
        return '<span style="color:#22c55e;font-size:1rem">&#8599;</span>'
    elif trend_dir < 0:
        return '<span style="color:#ef4444;font-size:1rem">&#8600;</span>'
    return '<span style="color:#64748b;font-size:1rem">&#8594;</span>'


def build_html() -> str:
    # ---- Summary bar chart SVG ----
    bar_data = [("Green", GREEN_COUNT, "#22c55e"), ("Amber", AMBER_COUNT, "#f59e0b"), ("Red", RED_COUNT, "#ef4444")]
    bw, bh = 320, 80
    bar_svg_parts = []
    bar_x = 10
    bar_total = len(KPIS)
    for label, count, color in bar_data:
        bwidth = int((count / bar_total) * (bw - 20))
        bar_svg_parts.append(
            f'<rect x="{bar_x}" y="20" width="{bwidth}" height="30" rx="4" fill="{color}" fill-opacity="0.85"/>'
            f'<text x="{bar_x + bwidth // 2}" y="40" fill="#0f172a" font-size="12" font-weight="700" text-anchor="middle">{count}</text>'
            f'<text x="{bar_x + bwidth // 2}" y="65" fill="{color}" font-size="10" text-anchor="middle">{label}</text>'
        )
        bar_x += bwidth + 4
    bar_svg = f'<svg width="{bw}" height="{bh}" xmlns="http://www.w3.org/2000/svg" style="background:#1e293b;border-radius:8px">{" ".join(bar_svg_parts)}</svg>'

    # ---- KPI cards grid ----
    cards = ""
    for name, value, unit, status, trend_dir, desc in KPIS:
        color = STATUS_COLOR[status]
        spark = _sparkline_svg(status, trend_dir)
        badge = _rag_badge(status)
        arrow = _trend_arrow(trend_dir)
        cards += f"""<div style="background:#1e293b;border-radius:10px;padding:16px 18px;border-left:3px solid {color};">
      <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:6px">
        <div>
          <div style="font-size:0.78rem;color:#64748b;margin-bottom:2px">{name}</div>
          <div style="font-size:1.45rem;font-weight:700;color:{color}">{value}<span style="font-size:0.8rem;color:#64748b">{unit}</span> {arrow}</div>
        </div>
        {spark}
      </div>
      <div style="display:flex;align-items:center;justify-content:space-between">
        <div style="font-size:0.73rem;color:#475569">{desc}</div>
        {badge}
      </div>
    </div>"""

    # ---- Radar-style summary SVG (hexadecagon) ----
    radar_w, radar_h = 420, 340
    cx, cy, r_max = radar_w // 2, radar_h // 2, 130
    n_kpi = len(KPIS)
    # Normalize each KPI to 0-1 score (G=1.0, A=0.6, R=0.3)
    score_map = {"G": 1.0, "A": 0.6, "R": 0.3}
    # Axis endpoints
    axes = []
    for i in range(n_kpi):
        angle = math.pi / 2 - (2 * math.pi * i / n_kpi)
        axes.append((cx + r_max * math.cos(angle), cy - r_max * math.sin(angle)))
    # Grid circles
    grid_circles = ""
    for level in [0.25, 0.5, 0.75, 1.0]:
        pts = []
        for i in range(n_kpi):
            angle = math.pi / 2 - (2 * math.pi * i / n_kpi)
            px = cx + r_max * level * math.cos(angle)
            py = cy - r_max * level * math.sin(angle)
            pts.append(f"{px:.1f},{py:.1f}")
        grid_circles += f'<polygon points="{" ".join(pts)}" fill="none" stroke="#1e293b" stroke-width="1"/>'
    # Data polygon
    data_pts = []
    for i, (_, _, _, status, _, _) in enumerate(KPIS):
        score = score_map[status]
        angle = math.pi / 2 - (2 * math.pi * i / n_kpi)
        px = cx + r_max * score * math.cos(angle)
        py = cy - r_max * score * math.sin(angle)
        data_pts.append(f"{px:.1f},{py:.1f}")
    data_poly = f'<polygon points="{" ".join(data_pts)}" fill="#38bdf822" stroke="#38bdf8" stroke-width="1.5"/>'
    # Axis lines + labels
    axis_lines = ""
    for i, (ax, ay) in enumerate(axes):
        axis_lines += f'<line x1="{cx}" y1="{cy}" x2="{ax:.1f}" y2="{ay:.1f}" stroke="#1e293b" stroke-width="1"/>'
        lx = cx + (r_max + 14) * math.cos(math.pi / 2 - (2 * math.pi * i / n_kpi))
        ly = cy - (r_max + 14) * math.sin(math.pi / 2 - (2 * math.pi * i / n_kpi))
        k = KPIS[i]
        axis_lines += f'<text x="{lx:.1f}" y="{ly:.1f}" fill="{STATUS_COLOR[k[3]]}" font-size="8" text-anchor="middle" dominant-baseline="middle">{k[0]}</text>'

    radar_svg = f"""<svg width="{radar_w}" height="{radar_h}" xmlns="http://www.w3.org/2000/svg" style="background:#0f172a;border-radius:10px">
  {grid_circles}
  {axis_lines}
  {data_poly}
  <circle cx="{cx}" cy="{cy}" r="3" fill="#38bdf8"/>
  <text x="{cx}" y="{radar_h - 10}" fill="#334155" font-size="9" text-anchor="middle">Board KPI Radar — {GREEN_COUNT}G / {AMBER_COUNT}A / {RED_COUNT}R</text>
</svg>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>{TITLE}</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; padding: 28px; }}
    h1 {{ color: #C74634; font-size: 1.7rem; margin-bottom: 4px; }}
    h2 {{ color: #38bdf8; font-size: 1.1rem; margin: 28px 0 12px; }}
    .subtitle {{ color: #64748b; font-size: 0.9rem; margin-bottom: 24px; }}
    .summary-row {{ display: flex; gap: 20px; align-items: center; flex-wrap: wrap; margin-bottom: 24px; }}
    .sum-stat {{ background: #1e293b; border-radius: 8px; padding: 14px 22px; text-align: center; min-width: 110px; }}
    .sum-val {{ font-size: 2rem; font-weight: 700; }}
    .sum-lbl {{ font-size: 0.75rem; color: #64748b; margin-top: 2px; }}
    .kpi-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 14px; }}
    .port-badge {{ float: right; background: #1e293b; color: #38bdf8; font-size: 0.75rem; padding: 4px 10px; border-radius: 20px; }}
  </style>
</head>
<body>
  <h1>{TITLE} <span class="port-badge">:{PORT}</span></h1>
  <p class="subtitle">16 Board KPIs · Traffic-light RAG status · Sparkline trends · Q1 2027</p>

  <div class="summary-row">
    <div class="sum-stat"><div class="sum-val" style="color:#22c55e">{GREEN_COUNT}</div><div class="sum-lbl">Green — On Track</div></div>
    <div class="sum-stat"><div class="sum-val" style="color:#f59e0b">{AMBER_COUNT}</div><div class="sum-lbl">Amber — Monitor</div></div>
    <div class="sum-stat"><div class="sum-val" style="color:#ef4444">{RED_COUNT}</div><div class="sum-lbl">Red — Action Needed</div></div>
    <div>{bar_svg}</div>
  </div>

  <h2>KPI Grid with Sparklines</h2>
  <div class="kpi-grid">{cards}</div>

  <h2>KPI Radar Overview</h2>
  <div style="margin-top:8px">{radar_svg}</div>

  <p style="color:#334155;font-size:0.78rem;margin-top:20px">OCI Robot Cloud · Board Metrics Dashboard · port {PORT}</p>
</body>
</html>"""
    return html


if USE_FASTAPI:
    app = FastAPI(title=TITLE)

    @app.get("/", response_class=HTMLResponse)
    async def index():
        return build_html()

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": TITLE, "port": PORT}

    @app.get("/api/kpis")
    async def api_kpis():
        return {
            "kpis": [
                {"name": k[0], "value": k[1], "unit": k[2], "status": k[3], "description": k[5]}
                for k in KPIS
            ],
            "summary": {"green": GREEN_COUNT, "amber": AMBER_COUNT, "red": RED_COUNT},
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
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        print(f"[{TITLE}] FastAPI unavailable — serving on http://0.0.0.0:{PORT}")
        HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
