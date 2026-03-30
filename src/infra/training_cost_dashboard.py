#!/usr/bin/env python3
"""
Training Cost Dashboard — OCI Robot Cloud
Port 8330 | cycle-67B

Real-time training cost dashboard with budget alerts and cost-per-SR tracking.
"""

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
from datetime import datetime

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

TRAINING_RUNS = [
    {"id": "BC_500",        "type": "BC",       "cost": 2.40,  "sr": 0.28, "steps": 500,  "date": "2026-01-08"},
    {"id": "BC_1000",       "type": "BC",       "cost": 4.80,  "sr": 0.41, "steps": 1000, "date": "2026-01-15"},
    {"id": "BC_2000",       "type": "BC",       "cost": 9.60,  "sr": 0.51, "steps": 2000, "date": "2026-01-22"},
    {"id": "DAgger_r5",     "type": "DAgger",   "cost": 6.10,  "sr": 0.45, "steps": 1200, "date": "2026-02-01"},
    {"id": "DAgger_r6",     "type": "DAgger",   "cost": 7.30,  "sr": 0.54, "steps": 1500, "date": "2026-02-08"},
    {"id": "DAgger_r7",     "type": "DAgger",   "cost": 5.90,  "sr": 0.58, "steps": 1200, "date": "2026-02-14"},
    {"id": "DAgger_r8",     "type": "DAgger",   "cost": 6.80,  "sr": 0.63, "steps": 1400, "date": "2026-02-21"},
    {"id": "DAgger_r9_v2.2","type": "DAgger",   "cost": 4.73,  "sr": 0.71, "steps": 980,  "date": "2026-03-01", "best": True},
    {"id": "groot_v1",      "type": "GR00T_ft", "cost": 38.00, "sr": 0.62, "steps": 5000, "date": "2026-02-05"},
    {"id": "groot_v2",      "type": "GR00T_ft", "cost": 67.00, "sr": 0.79, "steps": 8000, "date": "2026-02-25"},
    {"id": "groot_v2.1",    "type": "GR00T_ft", "cost": 54.00, "sr": 0.76, "steps": 7000, "date": "2026-03-10"},
    {"id": "groot_v3",      "type": "GR00T_ft", "cost": 142.00,"sr": None,  "steps": 18000,"date": "2026-03-28", "ongoing": True},
]

MONTHLY_SPEND = {
    "Jan": {"training": 16.80, "eval": 4.20, "sdg": 3.10},
    "Feb": {"training": 69.10, "eval": 9.80, "sdg": 7.40},
    "Mar": {"training": 98.00, "eval": 8.60, "sdg": 7.00},
}

BUDGET = 500.0
YTD_TOTAL = 224.0
COST_PER_SR_AVG = 6.71
BEST_RUN = "DAgger_r9_v2.2"
BEST_RUN_COST = 4.73
BEST_RUN_SR = 0.71
PROJECTED_80SR_COST = 287.0


# ---------------------------------------------------------------------------
# SVG builders
# ---------------------------------------------------------------------------

def build_scatter_svg() -> str:
    """Cost vs SR scatter plot with efficiency frontier."""
    W, H = 600, 380
    PAD_L, PAD_R, PAD_T, PAD_B = 70, 30, 30, 55

    max_cost = 160
    min_cost = 0
    min_sr = 0.20
    max_sr = 0.85

    def cx(cost):
        return PAD_L + (cost - min_cost) / (max_cost - min_cost) * (W - PAD_L - PAD_R)

    def cy(sr):
        return PAD_T + (1 - (sr - min_sr) / (max_sr - min_sr)) * (H - PAD_T - PAD_B)

    colors = {"BC": "#38bdf8", "DAgger": "#C74634", "GR00T_ft": "#a78bfa"}
    labels = {"BC": "BC", "DAgger": "DAgger", "GR00T_ft": "GR00T fine-tune"}

    # Efficiency frontier points (sorted by cost)
    completed = [r for r in TRAINING_RUNS if r["sr"] is not None]
    frontier = []
    best_sr = -1
    for r in sorted(completed, key=lambda x: x["cost"]):
        if r["sr"] > best_sr:
            best_sr = r["sr"]
            frontier.append(r)

    frontier_pts = " ".join(f"{cx(r['cost']):.1f},{cy(r['sr']):.1f}" for r in frontier)

    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#1e293b;border-radius:8px">')

    # Grid
    for cost_tick in [0, 20, 40, 60, 80, 100, 120, 140, 160]:
        x = cx(cost_tick)
        lines.append(f'<line x1="{x:.1f}" y1="{PAD_T}" x2="{x:.1f}" y2="{H-PAD_B}" stroke="#334155" stroke-width="1"/>')
        lines.append(f'<text x="{x:.1f}" y="{H-PAD_B+16}" text-anchor="middle" fill="#94a3b8" font-size="10">${cost_tick}</text>')

    for sr_tick in [0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]:
        y = cy(sr_tick)
        lines.append(f'<line x1="{PAD_L}" y1="{y:.1f}" x2="{W-PAD_R}" y2="{y:.1f}" stroke="#334155" stroke-width="1"/>')
        lines.append(f'<text x="{PAD_L-8}" y="{y+4:.1f}" text-anchor="end" fill="#94a3b8" font-size="10">{sr_tick:.0%}</text>')

    # Axes
    lines.append(f'<line x1="{PAD_L}" y1="{PAD_T}" x2="{PAD_L}" y2="{H-PAD_B}" stroke="#475569" stroke-width="1"/>')
    lines.append(f'<line x1="{PAD_L}" y1="{H-PAD_B}" x2="{W-PAD_R}" y2="{H-PAD_B}" stroke="#475569" stroke-width="1"/>')

    # Axis labels
    lines.append(f'<text x="{(PAD_L+W-PAD_R)//2}" y="{H-5}" text-anchor="middle" fill="#94a3b8" font-size="11">Training Cost ($)</text>')
    lines.append(f'<text x="14" y="{(PAD_T+H-PAD_B)//2}" text-anchor="middle" fill="#94a3b8" font-size="11" transform="rotate(-90,14,{(PAD_T+H-PAD_B)//2})">Success Rate</text>')

    # Frontier line
    if len(frontier) > 1:
        lines.append(f'<polyline points="{frontier_pts}" fill="none" stroke="#fbbf24" stroke-width="1.5" stroke-dasharray="5,3" opacity="0.7"/>')
        lines.append(f'<text x="{cx(frontier[len(frontier)//2]["cost"])+6:.1f}" y="{cy(frontier[len(frontier)//2]["sr"])-6:.1f}" fill="#fbbf24" font-size="9">Efficiency Frontier</text>')

    # Plot points
    for r in completed:
        col = colors.get(r["type"], "#94a3b8")
        x, y = cx(r["cost"]), cy(r["sr"])
        radius = 7 if r.get("best") else 5
        stroke = "#fbbf24" if r.get("best") else "none"
        sw = 2 if r.get("best") else 0
        lines.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{radius}" fill="{col}" stroke="{stroke}" stroke-width="{sw}"/>')
        if r.get("best"):
            lines.append(f'<text x="{x+10:.1f}" y="{y-8:.1f}" fill="#fbbf24" font-size="9" font-weight="bold">DAgger_r9 ★ best efficiency</text>')
            lines.append(f'<text x="{x+10:.1f}" y="{y+4:.1f}" fill="#fbbf24" font-size="9">${r["cost"]} / SR {r["sr"]:.0%}</text>')

    # Legend
    lx = PAD_L + 10
    ly = PAD_T + 10
    for i, (k, col) in enumerate(colors.items()):
        lines.append(f'<circle cx="{lx+8}" cy="{ly+i*18}" r="5" fill="{col}"/>')
        lines.append(f'<text x="{lx+18}" y="{ly+i*18+4}" fill="#cbd5e1" font-size="10">{labels[k]}</text>')

    # Title
    lines.append(f'<text x="{W//2}" y="{PAD_T-10}" text-anchor="middle" fill="#f1f5f9" font-size="13" font-weight="bold">Training Cost vs Success Rate</text>')

    lines.append('</svg>')
    return "\n".join(lines)


def build_timeline_svg() -> str:
    """Cumulative cost timeline as step chart (Jan–Mar 2026)."""
    W, H = 600, 320
    PAD_L, PAD_R, PAD_T, PAD_B = 65, 20, 30, 55

    # Build day-level cumulative data for each category
    categories = ["training", "eval", "sdg"]
    colors_cat = {"training": "#C74634", "eval": "#38bdf8", "sdg": "#a78bfa"}

    # Simplified monthly step-chart data points (day-of-year index 0-89)
    # Jan=days 0-30, Feb=31-58, Mar=59-89
    months = ["Jan", "Feb", "Mar"]
    month_end_days = [31, 59, 90]
    budget_milestones = [(50, "$50"), (100, "$100"), (150, "$150"), (200, "$200"), (224, "YTD")]

    # Cumulative totals at each month end
    cum = {c: [] for c in categories}
    running = {c: 0.0 for c in categories}
    day_points = {c: [(0, 0.0)] for c in categories}
    for i, m in enumerate(months):
        for c in categories:
            running[c] += MONTHLY_SPEND[m][c]
            day_points[c].append((month_end_days[i], running[c]))

    max_cum = max(sum(MONTHLY_SPEND[m][c] for c in categories for m in ["Jan", "Feb", "Mar"]) for _ in [1])
    total_cum = {c: day_points[c][-1][1] for c in categories}
    max_y = 130  # max display value

    def px(day):
        return PAD_L + day / 90 * (W - PAD_L - PAD_R)

    def py(val):
        return PAD_T + (1 - val / max_y) * (H - PAD_T - PAD_B)

    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#1e293b;border-radius:8px">')

    # Grid
    for yv in [0, 25, 50, 75, 100, 125]:
        y = py(yv)
        lines.append(f'<line x1="{PAD_L}" y1="{y:.1f}" x2="{W-PAD_R}" y2="{y:.1f}" stroke="#334155" stroke-width="1"/>')
        lines.append(f'<text x="{PAD_L-6}" y="{y+4:.1f}" text-anchor="end" fill="#94a3b8" font-size="10">${yv}</text>')

    # Month dividers
    for d, m in zip(month_end_days, months):
        x = px(d)
        lines.append(f'<line x1="{x:.1f}" y1="{PAD_T}" x2="{x:.1f}" y2="{H-PAD_B}" stroke="#475569" stroke-width="1" stroke-dasharray="4,2"/>')
    for i, m in enumerate(months):
        start_day = 0 if i == 0 else month_end_days[i-1]
        mid = (start_day + month_end_days[i]) / 2
        lines.append(f'<text x="{px(mid):.1f}" y="{H-PAD_B+16}" text-anchor="middle" fill="#94a3b8" font-size="11">{m} 2026</text>')

    # Budget milestones
    for bval, blabel in budget_milestones:
        # Add cumulative tracking line — total spend
        pass  # handled below

    # Draw step lines for each category
    for c in categories:
        pts = day_points[c]
        col = colors_cat[c]
        # Build step-chart path
        path_d = f"M {px(pts[0][0]):.1f},{py(pts[0][1]):.1f}"
        for j in range(1, len(pts)):
            prev_day, prev_val = pts[j-1]
            cur_day, cur_val = pts[j]
            path_d += f" L {px(cur_day):.1f},{py(prev_val):.1f} L {px(cur_day):.1f},{py(cur_val):.1f}"
        lines.append(f'<path d="{path_d}" fill="none" stroke="{col}" stroke-width="2"/>')

    # Total cumulative line
    total_pts = [(0, 0.0)]
    for i, m in enumerate(months):
        total_pts.append((month_end_days[i], sum(day_points[c][i+1][1] for c in categories)))
    total_path = f"M {px(total_pts[0][0]):.1f},{py(total_pts[0][1]):.1f}"
    for j in range(1, len(total_pts)):
        pd_, pv = total_pts[j-1]
        cd_, cv = total_pts[j]
        total_path += f" L {px(cd_):.1f},{py(pv):.1f} L {px(cd_):.1f},{py(cv):.1f}"
    lines.append(f'<path d="{total_path}" fill="none" stroke="#fbbf24" stroke-width="2.5" stroke-dasharray="6,3"/>')

    # YTD marker
    ytd_x = px(90)
    ytd_y = py(YTD_TOTAL)
    lines.append(f'<circle cx="{ytd_x:.1f}" cy="{ytd_y:.1f}" r="6" fill="#fbbf24"/>')
    lines.append(f'<text x="{ytd_x-8:.1f}" y="{ytd_y-10:.1f}" text-anchor="end" fill="#fbbf24" font-size="10" font-weight="bold">YTD $224 / $500 budget</text>')

    # Budget line
    lines.append(f'<line x1="{PAD_L}" y1="{py(max_y):.1f}" x2="{W-PAD_R}" y2="{py(max_y):.1f}" stroke="#ef4444" stroke-width="1" stroke-dasharray="3,3" opacity="0.5"/>')

    # Legend
    legend_items = list(colors_cat.items()) + [("total", "#fbbf24")]
    legend_labels = {"training": "Training", "eval": "Eval", "sdg": "SDG", "total": "Total"}
    for i, (k, col) in enumerate(legend_items):
        lx = PAD_L + i * 110
        lines.append(f'<line x1="{lx}" y1="{H-12}" x2="{lx+20}" y2="{H-12}" stroke="{col}" stroke-width="2"/>')
        lines.append(f'<text x="{lx+24}" y="{H-8}" fill="#cbd5e1" font-size="10">{legend_labels[k]}</text>')

    # Axes
    lines.append(f'<line x1="{PAD_L}" y1="{PAD_T}" x2="{PAD_L}" y2="{H-PAD_B}" stroke="#475569" stroke-width="1"/>')
    lines.append(f'<line x1="{PAD_L}" y1="{H-PAD_B}" x2="{W-PAD_R}" y2="{H-PAD_B}" stroke="#475569" stroke-width="1"/>')
    lines.append(f'<text x="12" y="{(PAD_T+H-PAD_B)//2}" text-anchor="middle" fill="#94a3b8" font-size="11" transform="rotate(-90,12,{(PAD_T+H-PAD_B)//2})">Cumulative Cost ($)</text>')

    lines.append(f'<text x="{W//2}" y="{PAD_T-10}" text-anchor="middle" fill="#f1f5f9" font-size="13" font-weight="bold">Cumulative Training Spend — Jan–Mar 2026</text>')
    lines.append('</svg>')
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------

def build_html() -> str:
    scatter_svg = build_scatter_svg()
    timeline_svg = build_timeline_svg()

    completed_runs = [r for r in TRAINING_RUNS if r["sr"] is not None]
    efficiency_rows = sorted(completed_runs, key=lambda r: r["cost"] / r["sr"])

    budget_pct = YTD_TOTAL / BUDGET * 100
    budget_bar_color = "#C74634" if budget_pct > 70 else "#38bdf8"

    rows_html = ""
    for r in efficiency_rows:
        eff = r["cost"] / r["sr"]
        badge = ""
        if r.get("best"):
            badge = '<span style="background:#fbbf24;color:#0f172a;border-radius:4px;padding:1px 6px;font-size:10px;font-weight:700;margin-left:6px">★ BEST</span>'
        sr_pct = f"{r['sr']:.0%}"
        type_colors = {"BC": "#38bdf8", "DAgger": "#C74634", "GR00T_ft": "#a78bfa"}
        tc = type_colors.get(r["type"], "#94a3b8")
        rows_html += f"""
        <tr style="border-bottom:1px solid #1e3a5f">
          <td style="padding:6px 10px">{r['id']}{badge}</td>
          <td style="padding:6px 10px;color:{tc}">{r['type']}</td>
          <td style="padding:6px 10px;text-align:right">${r['cost']:.2f}</td>
          <td style="padding:6px 10px;text-align:right">{sr_pct}</td>
          <td style="padding:6px 10px;text-align:right">${eff:.2f}</td>
          <td style="padding:6px 10px;color:#64748b">{r['date']}</td>
        </tr>"""

    ongoing_html = ""
    for r in TRAINING_RUNS:
        if r.get("ongoing"):
            ongoing_html += f"""
            <div style="background:#1e293b;border:1px solid #C74634;border-radius:8px;padding:12px 16px;margin-bottom:10px">
              <div style="color:#C74634;font-weight:700;font-size:13px">⚡ ONGOING: {r['id']}</div>
              <div style="color:#94a3b8;font-size:12px;margin-top:4px">
                Accrued: ${r['cost']:.0f} | Steps: {r['steps']:,} | Est. completion: Apr 2 2026
              </div>
            </div>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Training Cost Dashboard — OCI Robot Cloud</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',system-ui,sans-serif;padding:24px}}
  h1{{color:#f1f5f9;font-size:22px;font-weight:700;margin-bottom:4px}}
  .subtitle{{color:#64748b;font-size:13px;margin-bottom:24px}}
  .kpi-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:28px}}
  .kpi{{background:#1e293b;border-radius:10px;padding:18px 20px;border-left:3px solid #C74634}}
  .kpi .label{{color:#94a3b8;font-size:11px;text-transform:uppercase;letter-spacing:.05em;margin-bottom:6px}}
  .kpi .value{{color:#f1f5f9;font-size:26px;font-weight:700}}
  .kpi .sub{{color:#64748b;font-size:11px;margin-top:4px}}
  .kpi.blue{{border-left-color:#38bdf8}}
  .kpi.green{{border-left-color:#4ade80}}
  .kpi.yellow{{border-left-color:#fbbf24}}
  .chart-row{{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-bottom:28px}}
  .chart-box{{background:#1e293b;border-radius:10px;padding:16px}}
  .section-title{{color:#cbd5e1;font-size:13px;font-weight:600;margin-bottom:14px;letter-spacing:.04em;text-transform:uppercase}}
  table{{width:100%;border-collapse:collapse;font-size:12px}}
  th{{text-align:left;padding:8px 10px;color:#64748b;font-weight:600;border-bottom:2px solid #334155;font-size:11px;text-transform:uppercase}}
  th:not(:first-child){{text-align:right}}
  tr:hover{{background:rgba(56,189,248,.04)}}
  .budget-bar{{background:#1e3a5f;border-radius:6px;height:10px;overflow:hidden;margin-top:8px}}
  .budget-fill{{height:100%;border-radius:6px;background:{budget_bar_color};transition:width .3s}}
  .alert{{background:#2d1a1a;border:1px solid #C74634;border-radius:8px;padding:12px 16px;margin-bottom:20px;color:#fca5a5;font-size:13px}}
  .ongoing-section{{margin-bottom:28px}}
  svg{{max-width:100%;height:auto}}
</style>
</head>
<body>
<h1>Training Cost Dashboard</h1>
<div class="subtitle">OCI Robot Cloud · Port 8330 · Updated {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}</div>

<div class="kpi-grid">
  <div class="kpi">
    <div class="label">YTD Spend</div>
    <div class="value">${YTD_TOTAL:.0f}</div>
    <div class="sub">{budget_pct:.0f}% of ${BUDGET:.0f} budget</div>
    <div class="budget-bar"><div class="budget-fill" style="width:{budget_pct:.0f}%"></div></div>
  </div>
  <div class="kpi blue">
    <div class="label">Avg Cost / SR Point</div>
    <div class="value">${COST_PER_SR_AVG:.2f}</div>
    <div class="sub">across {len(completed_runs)} completed runs</div>
  </div>
  <div class="kpi green">
    <div class="label">Best Efficiency Run</div>
    <div class="value">{BEST_RUN}</div>
    <div class="sub">${BEST_RUN_COST} → SR {BEST_RUN_SR:.0%}</div>
  </div>
  <div class="kpi yellow">
    <div class="label">Proj. Cost to SR 80%</div>
    <div class="value">${PROJECTED_80SR_COST}</div>
    <div class="sub">${PROJECTED_80SR_COST - YTD_TOTAL:.0f} remaining</div>
  </div>
</div>

<div class="ongoing-section">
  <div class="section-title">Active Training Runs</div>
  {ongoing_html}
</div>

<div class="chart-row">
  <div class="chart-box">
    {scatter_svg}
  </div>
  <div class="chart-box">
    {timeline_svg}
  </div>
</div>

<div style="background:#1e293b;border-radius:10px;padding:20px">
  <div class="section-title">All Training Runs — Efficiency Ranking (cost / SR)</div>
  <table>
    <thead><tr>
      <th>Run ID</th><th>Type</th><th style="text-align:right">Cost ($)</th>
      <th style="text-align:right">Final SR</th><th style="text-align:right">$/SR-pt</th><th>Date</th>
    </tr></thead>
    <tbody>{rows_html}</tbody>
  </table>
</div>

<div style="margin-top:20px;color:#334155;font-size:11px;text-align:center">
  OCI Robot Cloud · Training Cost Dashboard v1.0 · Port 8330 · cycle-67B
</div>
</body>
</html>"""
    return html


# ---------------------------------------------------------------------------
# App / server
# ---------------------------------------------------------------------------

if HAS_FASTAPI:
    app = FastAPI(title="Training Cost Dashboard", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return HTMLResponse(content=build_html())

    @app.get("/api/runs")
    async def api_runs():
        return {"runs": TRAINING_RUNS, "ytd_total": YTD_TOTAL, "budget": BUDGET}

    @app.get("/api/metrics")
    async def api_metrics():
        completed = [r for r in TRAINING_RUNS if r["sr"] is not None]
        return {
            "ytd_total": YTD_TOTAL,
            "budget": BUDGET,
            "budget_pct": round(YTD_TOTAL / BUDGET * 100, 1),
            "cost_per_sr_avg": COST_PER_SR_AVG,
            "best_run": BEST_RUN,
            "best_run_cost": BEST_RUN_COST,
            "best_run_sr": BEST_RUN_SR,
            "projected_80sr_cost": PROJECTED_80SR_COST,
            "completed_runs": len(completed),
            "monthly_spend": MONTHLY_SPEND,
        }

    @app.get("/health")
    async def health():
        return {"status": "ok", "port": 8330, "service": "training_cost_dashboard"}

else:
    # Fallback: stdlib http.server
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(build_html().encode())

        def log_message(self, fmt, *args):
            pass


if __name__ == "__main__":
    if HAS_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8330)
    else:
        print("FastAPI not found — falling back to stdlib http.server on port 8330")
        server = HTTPServer(("0.0.0.0", 8330), Handler)
        server.serve_forever()
