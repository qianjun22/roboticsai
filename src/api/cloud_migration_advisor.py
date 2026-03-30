"""Cloud Migration Advisor — port 8234
Advises robotics startups on migrating from AWS/Azure to OCI Robot Cloud.
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

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

ARCHETYPES = [
    {
        "name": "Startup",
        "color": "#38bdf8",
        "data_portability": 88,
        "api_compatibility": 91,
        "cost_delta": 79,
        "nvidia_stack_lockin": 100,
        "team_expertise": 72,
        "migration_complexity": 2.1,
        "payback_months": 8,
        "risk": "Low",
        "readiness_pct": 82,
    },
    {
        "name": "Scaleup",
        "color": "#a78bfa",
        "data_portability": 74,
        "api_compatibility": 83,
        "cost_delta": 68,
        "nvidia_stack_lockin": 100,
        "team_expertise": 85,
        "migration_complexity": 3.4,
        "payback_months": 14,
        "risk": "Medium",
        "readiness_pct": 71,
    },
    {
        "name": "Enterprise",
        "color": "#C74634",
        "data_portability": 58,
        "api_compatibility": 67,
        "cost_delta": 55,
        "nvidia_stack_lockin": 100,
        "team_expertise": 91,
        "migration_complexity": 5.8,
        "payback_months": 22,
        "risk": "High",
        "readiness_pct": 59,
    },
]

WATERFALL_ITEMS = [
    {"label": "Migration Effort",          "value": -42000, "type": "cost"},
    {"label": "Training Cost Savings",      "value":  85000, "type": "save"},
    {"label": "Inference Savings",          "value":  67000, "type": "save"},
    {"label": "Support Savings",            "value":  31000, "type": "save"},
    {"label": "NVIDIA Partnership Value",   "value":  46000, "type": "save"},
]
NPV_3YR = 187000

# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------

def _radar_svg() -> str:
    """5-axis radar chart for 3 customer archetypes."""
    cx, cy, r = 220, 200, 140
    axes = ["Data Portability", "API Compat", "Cost Delta", "NVIDIA Stack", "Team Expertise"]
    keys = ["data_portability", "api_compatibility", "cost_delta", "nvidia_stack_lockin", "team_expertise"]
    n = len(axes)

    def pt(angle_idx, pct, radius=r):
        angle = math.pi / 2 + 2 * math.pi * angle_idx / n
        x = cx + radius * pct / 100 * math.cos(angle)
        y = cy - radius * pct / 100 * math.sin(angle)
        return x, y

    # grid rings
    rings = ""
    for lvl in [20, 40, 60, 80, 100]:
        pts = " ".join(f"{pt(i, lvl)[0]:.1f},{pt(i, lvl)[1]:.1f}" for i in range(n))
        rings += f'<polygon points="{pts}" fill="none" stroke="#334155" stroke-width="0.8"/>\n'
        label_x, label_y = pt(0, lvl)
        rings += f'<text x="{label_x+4:.1f}" y="{label_y:.1f}" fill="#64748b" font-size="9">{lvl}</text>\n'

    # axis lines + labels
    axes_svg = ""
    for i, label in enumerate(axes):
        ox, oy = pt(i, 100)
        axes_svg += f'<line x1="{cx}" y1="{cy}" x2="{ox:.1f}" y2="{oy:.1f}" stroke="#475569" stroke-width="1"/>\n'
        lx, ly = pt(i, 115)
        axes_svg += f'<text x="{lx:.1f}" y="{ly:.1f}" fill="#94a3b8" font-size="10" text-anchor="middle">{label}</text>\n'

    # polygons per archetype
    polys = ""
    for arch in ARCHETYPES:
        pts = " ".join(f"{pt(i, arch[keys[i]])[0]:.1f},{pt(i, arch[keys[i]])[1]:.1f}" for i in range(n))
        polys += (f'<polygon points="{pts}" fill="{arch["color"]}" fill-opacity="0.15" '
                  f'stroke="{arch["color"]}" stroke-width="2"/>\n')

    # legend
    legend = ""
    for i, arch in enumerate(ARCHETYPES):
        lx, ly = 370, 140 + i * 22
        legend += f'<rect x="{lx}" y="{ly-10}" width="14" height="14" fill="{arch["color"]}" rx="2"/>'
        legend += f'<text x="{lx+18}" y="{ly+2}" fill="#cbd5e1" font-size="11">{arch["name"]}</text>'

    return (f'<svg viewBox="0 0 480 400" xmlns="http://www.w3.org/2000/svg" '
            f'style="width:100%;max-width:480px">'
            f'<rect width="480" height="400" fill="#1e293b" rx="8"/>'
            f'<text x="240" y="24" fill="#f1f5f9" font-size="14" font-weight="bold" text-anchor="middle">'
            f'Migration Readiness Radar</text>'
            f'{rings}{axes_svg}{polys}{legend}</svg>')


def _waterfall_svg() -> str:
    """Waterfall chart: migration cost vs savings → 3-year NPV."""
    W, H = 580, 320
    pad_l, pad_r, pad_t, pad_b = 50, 20, 40, 60
    chart_w = W - pad_l - pad_r
    chart_h = H - pad_t - pad_b

    # compute running base
    items = WATERFALL_ITEMS
    total_range = 260000
    zero_y = pad_t + chart_h * 0.55  # zero line y
    scale = chart_h * 0.85 / total_range

    bar_w = chart_w / (len(items) + 2) * 0.6
    bars = ""
    running = 0
    for idx, item in enumerate(items):
        x = pad_l + (idx + 0.7) * (chart_w / (len(items) + 1))
        v = item["value"]
        color = "#C74634" if v < 0 else "#38bdf8"
        bar_top = zero_y - (running + (v if v > 0 else 0)) * scale
        bar_h = abs(v) * scale
        bars += f'<rect x="{x:.1f}" y="{bar_top:.1f}" width="{bar_w:.1f}" height="{bar_h:.1f}" fill="{color}" rx="2"/>'
        sign = "+" if v > 0 else ""
        bars += (f'<text x="{x + bar_w/2:.1f}" y="{bar_top - 4:.1f}" '
                 f'fill="#f1f5f9" font-size="9" text-anchor="middle">{sign}${abs(v)//1000}k</text>')
        # label below
        short = item["label"].replace(" ", "\n")
        lines = item["label"].split(" ")
        for li, word in enumerate(lines[:2]):
            bars += (f'<text x="{x + bar_w/2:.1f}" y="{zero_y + 14 + li*11:.1f}" '
                     f'fill="#94a3b8" font-size="8" text-anchor="middle">{word}</text>')
        running += v

    # NPV bar
    npv_x = pad_l + (len(items) + 0.7) * (chart_w / (len(items) + 1))
    npv_top = zero_y - running * scale
    npv_h = running * scale
    bars += (f'<rect x="{npv_x:.1f}" y="{npv_top:.1f}" width="{bar_w:.1f}" height="{npv_h:.1f}" '
             f'fill="#22c55e" rx="2"/>')
    bars += (f'<text x="{npv_x + bar_w/2:.1f}" y="{npv_top - 4:.1f}" '
             f'fill="#22c55e" font-size="10" font-weight="bold" text-anchor="middle">${NPV_3YR//1000}k NPV</text>')
    bars += (f'<text x="{npv_x + bar_w/2:.1f}" y="{zero_y + 14:.1f}" '
             f'fill="#94a3b8" font-size="8" text-anchor="middle">3-Yr NPV</text>')

    # zero line
    zero_line = f'<line x1="{pad_l}" y1="{zero_y:.1f}" x2="{W-pad_r}" y2="{zero_y:.1f}" stroke="#475569" stroke-width="1" stroke-dasharray="4,3"/>'

    return (f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:{W}px">'
            f'<rect width="{W}" height="{H}" fill="#1e293b" rx="8"/>'
            f'<text x="{W//2}" y="22" fill="#f1f5f9" font-size="14" font-weight="bold" text-anchor="middle">'
            f'3-Year Migration Cost vs Savings (Startup Archetype)</text>'
            f'{zero_line}{bars}</svg>')


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def _build_html() -> str:
    arch_cards = ""
    for arch in ARCHETYPES:
        risk_color = {"Low": "#22c55e", "Medium": "#f59e0b", "High": "#C74634"}[arch["risk"]]
        arch_cards += f"""
        <div class="card">
          <div class="card-title" style="color:{arch['color']}">{arch['name']}</div>
          <div class="metric">Readiness: <span style="color:{arch['color']}">{arch['readiness_pct']}%</span></div>
          <div class="metric">Complexity: <span>{arch['migration_complexity']}/10</span></div>
          <div class="metric">Payback: <span>{arch['payback_months']} months</span></div>
          <div class="metric">Risk: <span style="color:{risk_color}">{arch['risk']}</span></div>
          <div class="metric">NVIDIA Stack: <span style="color:#22c55e">100% compatible</span></div>
        </div>"""

    radar_svg = _radar_svg()
    waterfall_svg = _waterfall_svg()

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>OCI Robot Cloud — Cloud Migration Advisor</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; }}
  header {{ background: #1e293b; border-bottom: 2px solid #C74634; padding: 16px 32px; display:flex; align-items:center; gap:16px; }}
  header h1 {{ font-size: 1.4rem; color: #f1f5f9; }}
  header .badge {{ background: #C74634; color: #fff; padding: 3px 10px; border-radius: 12px; font-size: 0.75rem; font-weight: 600; }}
  .container {{ max-width: 1100px; margin: 0 auto; padding: 32px 24px; }}
  .section-title {{ font-size: 1.1rem; color: #38bdf8; font-weight: 600; margin: 28px 0 14px; border-left: 3px solid #C74634; padding-left: 10px; }}
  .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px,1fr)); gap: 16px; margin-bottom: 28px; }}
  .card {{ background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 18px; }}
  .card-title {{ font-size: 1rem; font-weight: 700; margin-bottom: 10px; }}
  .metric {{ display: flex; justify-content: space-between; font-size: 0.85rem; color: #94a3b8; padding: 4px 0; border-bottom: 1px solid #1e3a5a22; }}
  .metric span {{ color: #f1f5f9; font-weight: 500; }}
  .charts {{ display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }}
  @media(max-width:700px) {{ .charts {{ grid-template-columns:1fr; }} }}
  .chart-box {{ background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 16px; }}
  .kpi-row {{ display:flex; gap:16px; flex-wrap:wrap; margin-bottom:24px; }}
  .kpi {{ background:#1e293b; border:1px solid #334155; border-radius:8px; padding:14px 20px; flex:1; min-width:160px; }}
  .kpi .val {{ font-size:1.6rem; font-weight:700; color:#38bdf8; }}
  .kpi .lbl {{ font-size:0.75rem; color:#64748b; margin-top:4px; }}
  footer {{ text-align:center; color:#334155; font-size:0.75rem; padding:32px; }}
</style>
</head>
<body>
<header>
  <div><div style="font-size:0.7rem;color:#64748b;letter-spacing:2px">OCI ROBOT CLOUD</div>
       <h1>Cloud Migration Advisor</h1></div>
  <div class="badge">PORT 8234</div>
</header>
<div class="container">
  <div class="section-title">Platform KPIs</div>
  <div class="kpi-row">
    <div class="kpi"><div class="val">$187k</div><div class="lbl">3-Year NPV (Startup)</div></div>
    <div class="kpi"><div class="val">8 mo</div><div class="lbl">Startup Payback Period</div></div>
    <div class="kpi"><div class="val">82%</div><div class="lbl">Startup Readiness Score</div></div>
    <div class="kpi"><div class="val" style="color:#22c55e">100%</div><div class="lbl">NVIDIA Stack Compatible</div></div>
    <div class="kpi"><div class="val">3</div><div class="lbl">Archetypes Analyzed</div></div>
  </div>

  <div class="section-title">Archetype Analysis</div>
  <div class="cards">{arch_cards}</div>

  <div class="section-title">Visualizations</div>
  <div class="charts">
    <div class="chart-box">{radar_svg}</div>
    <div class="chart-box">{waterfall_svg}</div>
  </div>
</div>
<footer>OCI Robot Cloud &mdash; Cloud Migration Advisor &mdash; port 8234 &mdash; Oracle Confidential</footer>
</body>
</html>"""


# ---------------------------------------------------------------------------
# App wiring
# ---------------------------------------------------------------------------

if USE_FASTAPI:
    app = FastAPI(title="Cloud Migration Advisor", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return HTMLResponse(content=_build_html())

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "cloud_migration_advisor", "port": 8234}

    @app.get("/api/archetypes")
    async def archetypes():
        return {"archetypes": ARCHETYPES}

    @app.get("/api/npv")
    async def npv():
        return {"npv_3yr_usd": NPV_3YR, "waterfall": WATERFALL_ITEMS}

else:
    # Fallback stdlib server
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
        uvicorn.run(app, host="0.0.0.0", port=8234)
    else:
        print("fastapi not found — serving on http://0.0.0.0:8234 via stdlib")
        HTTPServer(("0.0.0.0", 8234), _Handler).serve_forever()
