"""capacity_planner_v2.py — OCI Robot Cloud GPU Fleet Capacity Planner v2
FastAPI service on port 8326
Long-range capacity planning through AI World 2026 and beyond.
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
from datetime import datetime, timedelta

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

MONTHS = [
    "Jan 26", "Feb 26", "Mar 26", "Apr 26", "May 26",
    "Jun 26", "Jul 26", "Aug 26", "Sep 26", "Oct 26",
    "Nov 26", "Dec 26", "Jan 27", "Feb 27", "Mar 27",
]

# GPU-hours demand per month (growing curve with milestone bumps)
DEMAND = [
    4200, 4800, 5300, 5900, 6400,
    8200, 9100, 11500, 13800, 14200,
    14800, 15300, 17200, 18500, 21000,
]

# GPU-hours supply per month (step-function at node additions)
# Nodes: 4 through May, 5th added Jun, 6th added Aug, 7th considered Jan27
SUPPLY = [
    7200, 7200, 7200, 7200, 7200,   # Jan-May: 4 nodes
    9000, 9000, 10800, 10800, 10800, # Jun: +1 node; Aug: +1 node
    10800, 10800, 14400, 14400, 14400, # Jan27: +1 node
]

MILESTONES = {
    5: "Machina\nPilot",
    8: "AI World",
    14: "GTC Mar",
}

# Node expansion timeline
NODE_EVENTS = [
    {"month_idx": 0,  "nodes": 4, "cost_mo": 12800, "mrr": 6200,  "label": "Baseline"},
    {"month_idx": 5,  "nodes": 5, "cost_mo": 16000, "mrr": 11400, "label": "Machina Pilot"},
    {"month_idx": 7,  "nodes": 6, "cost_mo": 19200, "mrr": 19000, "label": "AI World Prep"},
    {"month_idx": 12, "nodes": 7, "cost_mo": 22400, "mrr": 28500, "label": "GTC Ramp"},
]

NODE_COST_PER = 3200  # $/node/month

METRICS = {
    "current_nodes": 4,
    "headroom_months": 2,
    "next_trigger": "Jun 2026 (Machina pilot)",
    "cost_per_node": "$3,200/mo",
    "sep_mrr": "$19,000",
    "sep_node_cost": "$3,200",
    "roi_day1": "positive",
    "expansion_roi_6th_node": "493%",
}


# ---------------------------------------------------------------------------
# SVG generators
# ---------------------------------------------------------------------------

def svg_demand_supply() -> str:
    W, H = 820, 320
    PAD_L, PAD_R, PAD_T, PAD_B = 60, 30, 30, 50
    plot_w = W - PAD_L - PAD_R
    plot_h = H - PAD_T - PAD_B
    n = len(MONTHS)
    max_val = max(max(DEMAND), max(SUPPLY)) * 1.05

    def px(i):
        return PAD_L + i * plot_w / (n - 1)

    def py(v):
        return PAD_T + plot_h - (v / max_val) * plot_h

    # Surplus/deficit shading between supply and demand
    surplus_poly = []
    deficit_poly = []
    for i in range(n):
        surplus_poly.append((px(i), py(max(SUPPLY[i], DEMAND[i]))))
    for i in range(n - 1, -1, -1):
        surplus_poly.append((px(i), py(min(SUPPLY[i], DEMAND[i]))))

    def pts(lst):
        return " ".join(f"{x:.1f},{y:.1f}" for x, y in lst)

    # Build supply and demand polylines
    supply_pts = " ".join(f"{px(i):.1f},{py(SUPPLY[i]):.1f}" for i in range(n))
    demand_pts = " ".join(f"{px(i):.1f},{py(DEMAND[i]):.1f}" for i in range(n))

    # Surplus regions (supply > demand = green)
    # Deficit regions (demand > supply = red)
    shading = ""
    for i in range(n - 1):
        x0, x1 = px(i), px(i + 1)
        s0, s1 = SUPPLY[i], SUPPLY[i + 1]
        d0, d1 = DEMAND[i], DEMAND[i + 1]
        if s0 >= d0 and s1 >= d1:
            poly = [(x0, py(s0)), (x1, py(s1)), (x1, py(d1)), (x0, py(d0))]
            shading += f'<polygon points="{pts(poly)}" fill="#22c55e" fill-opacity="0.18"/>'
        elif s0 < d0 and s1 < d1:
            poly = [(x0, py(d0)), (x1, py(d1)), (x1, py(s1)), (x0, py(s0))]
            shading += f'<polygon points="{pts(poly)}" fill="#ef4444" fill-opacity="0.22"/>'

    # Milestone annotations
    milestone_svg = ""
    for idx, label in MILESTONES.items():
        xm = px(idx)
        milestone_svg += f'''
        <line x1="{xm:.1f}" y1="{PAD_T}" x2="{xm:.1f}" y2="{PAD_T+plot_h}" stroke="#f59e0b" stroke-width="1.5" stroke-dasharray="4,3"/>
        <text x="{xm:.1f}" y="{PAD_T - 8}" fill="#f59e0b" font-size="10" text-anchor="middle">{label.replace(chr(10), " ")}</text>
        '''

    # Y-axis labels
    y_labels = ""
    for tick in range(0, int(max_val) + 1, 3000):
        yp = py(tick)
        if PAD_T <= yp <= PAD_T + plot_h:
            y_labels += f'<text x="{PAD_L - 6}" y="{yp + 4:.1f}" fill="#94a3b8" font-size="10" text-anchor="end">{tick // 1000}k</text>'
            y_labels += f'<line x1="{PAD_L}" y1="{yp:.1f}" x2="{PAD_L + plot_w}" y2="{yp:.1f}" stroke="#1e293b" stroke-width="1"/>'

    # X-axis labels
    x_labels = ""
    for i, m in enumerate(MONTHS):
        xp = px(i)
        x_labels += f'<text x="{xp:.1f}" y="{PAD_T + plot_h + 18}" fill="#64748b" font-size="9" text-anchor="middle">{m}</text>'

    return f'''
    <svg width="{W}" height="{H}" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" style="background:#0f172a;border-radius:8px">
      <text x="{W//2}" y="18" fill="#e2e8f0" font-size="13" font-weight="bold" text-anchor="middle">GPU-Hrs Demand vs Supply Forecast — Jan 2026 → Mar 2027</text>
      {y_labels}
      {x_labels}
      {shading}
      <polyline points="{supply_pts}" fill="none" stroke="#38bdf8" stroke-width="2.5"/>
      <polyline points="{demand_pts}" fill="none" stroke="#C74634" stroke-width="2.5"/>
      {milestone_svg}
      <!-- Legend -->
      <rect x="{PAD_L}" y="{H-18}" width="12" height="8" fill="#38bdf8"/>
      <text x="{PAD_L+16}" y="{H-11}" fill="#94a3b8" font-size="10">Supply</text>
      <rect x="{PAD_L+70}" y="{H-18}" width="12" height="8" fill="#C74634"/>
      <text x="{PAD_L+86}" y="{H-11}" fill="#94a3b8" font-size="10">Demand</text>
      <rect x="{PAD_L+160}" y="{H-18}" width="12" height="8" fill="#22c55e" fill-opacity="0.5"/>
      <text x="{PAD_L+176}" y="{H-11}" fill="#94a3b8" font-size="10">Surplus</text>
      <rect x="{PAD_L+240}" y="{H-18}" width="12" height="8" fill="#ef4444" fill-opacity="0.5"/>
      <text x="{PAD_L+256}" y="{H-11}" fill="#94a3b8" font-size="10">Deficit</text>
    </svg>
    '''


def svg_node_expansion() -> str:
    W, H = 820, 300
    PAD_L, PAD_R, PAD_T, PAD_B = 70, 30, 40, 60
    plot_w = W - PAD_L - PAD_R
    plot_h = H - PAD_T - PAD_B
    n = len(NODE_EVENTS)

    max_mrr = max(e["mrr"] for e in NODE_EVENTS) * 1.2
    max_cost = max(e["cost_mo"] for e in NODE_EVENTS) * 1.2
    scale = max(max_mrr, max_cost)

    bar_w = 60
    group_gap = plot_w / n

    bars = ""
    labels = ""
    roi_labels = ""

    for i, ev in enumerate(NODE_EVENTS):
        cx = PAD_L + i * group_gap + group_gap / 2
        # Cost bar (blue)
        cost_h = (ev["cost_mo"] / scale) * plot_h
        cy_cost = PAD_T + plot_h - cost_h
        bars += f'<rect x="{cx - bar_w/2 - 2:.1f}" y="{cy_cost:.1f}" width="{bar_w/2 - 2:.1f}" height="{cost_h:.1f}" fill="#38bdf8" rx="2"/>'
        # MRR bar (red/green)
        mrr_h = (ev["mrr"] / scale) * plot_h
        cy_mrr = PAD_T + plot_h - mrr_h
        mrr_color = "#22c55e" if ev["mrr"] > ev["cost_mo"] else "#C74634"
        bars += f'<rect x="{cx + 2:.1f}" y="{cy_mrr:.1f}" width="{bar_w/2 - 2:.1f}" height="{mrr_h:.1f}" fill="{mrr_color}" rx="2"/>'

        # ROI label
        roi = (ev["mrr"] - ev["cost_mo"]) / ev["cost_mo"] * 100
        roi_str = f"+{roi:.0f}%" if roi >= 0 else f"{roi:.0f}%"
        roi_color = "#22c55e" if roi >= 0 else "#ef4444"
        roi_labels += f'<text x="{cx:.1f}" y="{PAD_T - 10}" fill="{roi_color}" font-size="11" font-weight="bold" text-anchor="middle">ROI {roi_str}</text>'

        # Node count
        labels += f'<text x="{cx:.1f}" y="{PAD_T + plot_h + 16}" fill="#e2e8f0" font-size="11" text-anchor="middle">{ev["nodes"]} nodes</text>'
        labels += f'<text x="{cx:.1f}" y="{PAD_T + plot_h + 30}" fill="#64748b" font-size="10" text-anchor="middle">{ev["label"]}</text>'
        # Cost/MRR values
        bars += f'<text x="{cx - bar_w/4 - 2:.1f}" y="{cy_cost - 4:.1f}" fill="#38bdf8" font-size="9" text-anchor="middle">${ev["cost_mo"]//1000}k</text>'
        bars += f'<text x="{cx + bar_w/4 + 2:.1f}" y="{cy_mrr - 4:.1f}" fill="{mrr_color}" font-size="9" text-anchor="middle">${ev["mrr"]//1000}k</text>'

    # Y-axis
    y_axis = ""
    for tick in range(0, int(scale) + 1, 5000):
        yp = PAD_T + plot_h - (tick / scale) * plot_h
        if PAD_T <= yp <= PAD_T + plot_h:
            y_axis += f'<text x="{PAD_L - 6}" y="{yp + 4:.1f}" fill="#94a3b8" font-size="10" text-anchor="end">${tick//1000}k</text>'
            y_axis += f'<line x1="{PAD_L}" y1="{yp:.1f}" x2="{PAD_L+plot_w}" y2="{yp:.1f}" stroke="#1e293b" stroke-width="1"/>'

    return f'''
    <svg width="{W}" height="{H}" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" style="background:#0f172a;border-radius:8px">
      <text x="{W//2}" y="20" fill="#e2e8f0" font-size="13" font-weight="bold" text-anchor="middle">Node Expansion Decision Timeline — Cost vs Revenue per Expansion</text>
      {y_axis}
      {bars}
      {labels}
      {roi_labels}
      <!-- baseline axis -->
      <line x1="{PAD_L}" y1="{PAD_T+plot_h}" x2="{PAD_L+plot_w}" y2="{PAD_T+plot_h}" stroke="#334155" stroke-width="1.5"/>
      <!-- Legend -->
      <rect x="{PAD_L}" y="{H-14}" width="12" height="8" fill="#38bdf8"/>
      <text x="{PAD_L+16}" y="{H-7}" fill="#94a3b8" font-size="10">Monthly Cost</text>
      <rect x="{PAD_L+110}" y="{H-14}" width="12" height="8" fill="#22c55e"/>
      <text x="{PAD_L+126}" y="{H-7}" fill="#94a3b8" font-size="10">MRR (profitable)</text>
      <rect x="{PAD_L+250}" y="{H-14}" width="12" height="8" fill="#C74634"/>
      <text x="{PAD_L+266}" y="{H-7}" fill="#94a3b8" font-size="10">MRR (loss)</text>
    </svg>
    '''


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def build_html() -> str:
    svg1 = svg_demand_supply()
    svg2 = svg_node_expansion()
    m = METRICS

    metric_cards = ""
    for k, v in m.items():
        label = k.replace("_", " ").title()
        metric_cards += f'''
        <div style="background:#1e293b;border:1px solid #334155;border-radius:8px;padding:16px;min-width:160px;flex:1">
          <div style="color:#64748b;font-size:11px;margin-bottom:6px;text-transform:uppercase;letter-spacing:.05em">{label}</div>
          <div style="color:#e2e8f0;font-size:17px;font-weight:700">{v}</div>
        </div>
        '''

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Capacity Planner v2 — OCI Robot Cloud</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; padding: 24px; }}
    h1 {{ font-size: 22px; font-weight: 700; margin-bottom: 4px; }}
    .subtitle {{ color: #64748b; font-size: 13px; margin-bottom: 24px; }}
    .badge {{ display:inline-block; background:#C74634; color:#fff; font-size:11px; padding:2px 10px; border-radius:999px; margin-left:10px; vertical-align:middle; }}
    .section {{ margin-bottom: 32px; }}
    .section-title {{ font-size: 14px; font-weight: 600; color: #94a3b8; margin-bottom: 12px; text-transform: uppercase; letter-spacing: .05em; }}
    .metrics {{ display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 24px; }}
    .chart-wrap {{ border-radius: 8px; overflow: hidden; margin-bottom: 20px; }}
    footer {{ color: #334155; font-size: 11px; text-align: center; margin-top: 32px; }}
  </style>
</head>
<body>
  <h1>OCI Robot Cloud — Capacity Planner v2 <span class="badge">port 8326</span></h1>
  <div class="subtitle">Long-range GPU fleet planning through AI World 2026 and GTC 2027</div>

  <div class="section">
    <div class="section-title">Fleet Metrics</div>
    <div class="metrics">
      {metric_cards}
    </div>
  </div>

  <div class="section">
    <div class="section-title">GPU-Hrs: Demand vs Supply (Jan 2026 – Mar 2027)</div>
    <div class="chart-wrap">{svg1}</div>
  </div>

  <div class="section">
    <div class="section-title">Node Expansion Decision Timeline</div>
    <div class="chart-wrap">{svg2}</div>
  </div>

  <footer>OCI Robot Cloud &mdash; Capacity Planner v2 &mdash; Generated {datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")}</footer>
</body>
</html>'''


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

if USE_FASTAPI:
    app = FastAPI(
        title="Capacity Planner v2",
        description="Long-range GPU fleet capacity planning for OCI Robot Cloud",
        version="2.0.0",
    )

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return HTMLResponse(content=build_html())

    @app.get("/api/metrics")
    async def api_metrics():
        return {
            "metrics": METRICS,
            "demand": DEMAND,
            "supply": SUPPLY,
            "months": MONTHS,
            "node_events": NODE_EVENTS,
        }

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "capacity_planner_v2", "port": 8326}

else:
    # Fallback: stdlib http.server
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = build_html().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            pass  # suppress default logging


if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8326)
    else:
        print("FastAPI not available — starting stdlib HTTP server on port 8326")
        HTTPServer(("0.0.0.0", 8326), Handler).serve_forever()
