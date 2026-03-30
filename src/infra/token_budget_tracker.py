"""Token Budget Tracker — OCI Robot Cloud compute credit dashboard (port 8154)."""

import math
from datetime import datetime

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
except ImportError as e:
    raise SystemExit(f"Missing dependency: {e}. Run: pip install fastapi uvicorn") from e

app = FastAPI(title="Token Budget Tracker", version="1.0.0")

# ---------------------------------------------------------------------------
# Static data
# ---------------------------------------------------------------------------

PERIODS = [
    {"month": "Jan 2026", "allocated": 5000, "used": 3912, "remaining": 1088, "status": "CLOSED"},
    {"month": "Feb 2026", "allocated": 6000, "used": 5847, "remaining": 153,  "status": "CLOSED"},
    {"month": "Mar 2026", "allocated": 8000, "used": 6241, "remaining": 1759, "status": "ACTIVE"},
    {"month": "Apr 2026", "allocated": 10000, "used": 0,   "remaining": 10000, "status": "PENDING",
     "forecast": 8800},
]

MARCH_BREAKDOWN = [
    {"category": "A100_80GB_compute", "credits": 4120, "usd": 3978.48},
    {"category": "A100_40GB_compute", "credits": 1240, "usd": 1198.56},
    {"category": "object_storage",    "credits": 180,  "usd": 173.88},
    {"category": "network_egress",    "credits": 701,  "usd": 677.17},
]

KPIS = {
    "daily_burn_rate_usd": 99.40,
    "days_until_apr_budget_exhausted": 100.6,
    "efficiency_score_pct": 78,
    "alert": "Mar budget 78% consumed with 1 day remaining — Apr allocation looks sufficient",
}

# ---------------------------------------------------------------------------
# SVG generators
# ---------------------------------------------------------------------------

def _burn_rate_svg() -> str:
    """Area chart 680x200: Jan-Mar actual (sky fill), Apr forecast (dashed amber)."""
    w, h = 680, 200
    pad_l, pad_r, pad_t, pad_b = 60, 20, 20, 40
    chart_w = w - pad_l - pad_r
    chart_h = h - pad_t - pad_b

    months = ["Jan", "Feb", "Mar", "Apr"]
    used   = [3912,  5847,  6241,  8800]   # Apr = forecast
    allocs = [5000,  6000,  8000, 10000]
    max_val = 11000

    def cx(i):  return pad_l + i * (chart_w / (len(months) - 1))
    def cy(v):  return pad_t + chart_h - (v / max_val) * chart_h

    # Actual area (Jan-Mar, indices 0-2)
    actual_pts = " ".join(f"{cx(i):.1f},{cy(used[i]):.1f}" for i in range(3))
    area_pts   = f"{cx(0):.1f},{cy(0):.1f} {actual_pts} {cx(2):.1f},{cy(0):.1f}"

    # Forecast line (Mar→Apr, indices 2-3)
    forecast_line = f"M {cx(2):.1f},{cy(used[2]):.1f} L {cx(3):.1f},{cy(used[3]):.1f}"

    # Allocation markers (horizontal ticks)
    alloc_marks = ""
    for i, a in enumerate(allocs):
        x = cx(i)
        y = cy(a)
        alloc_marks += f'<line x1="{x-8:.1f}" y1="{y:.1f}" x2="{x+8:.1f}" y2="{y:.1f}" stroke="#94a3b8" stroke-width="1.5" stroke-dasharray="4,2"/>'

    # Gridlines
    grids = ""
    for v in [2000, 4000, 6000, 8000, 10000]:
        y = cy(v)
        grids += f'<line x1="{pad_l}" y1="{y:.1f}" x2="{w-pad_r}" y2="{y:.1f}" stroke="#1e293b" stroke-width="1"/>'
        grids += f'<text x="{pad_l-6}" y="{y+4:.1f}" fill="#64748b" font-size="9" text-anchor="end">{v//1000}k</text>'

    # Month labels
    labels = "".join(
        f'<text x="{cx(i):.1f}" y="{h-8}" fill="#94a3b8" font-size="10" text-anchor="middle">{m}</text>'
        for i, m in enumerate(months)
    )

    # Dots for actuals
    dots = "".join(
        f'<circle cx="{cx(i):.1f}" cy="{cy(used[i]):.1f}" r="4" fill="#38bdf8"/>'
        for i in range(3)
    )
    # Apr forecast dot (amber)
    dots += f'<circle cx="{cx(3):.1f}" cy="{cy(used[3]):.1f}" r="4" fill="#f59e0b" stroke="#0f172a" stroke-width="1.5"/>'

    return f'''<svg width="{w}" height="{h}" xmlns="http://www.w3.org/2000/svg">
  <rect width="{w}" height="{h}" fill="#0f172a" rx="8"/>
  {grids}
  <defs>
    <linearGradient id="skyGrad" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#38bdf8" stop-opacity="0.45"/>
      <stop offset="100%" stop-color="#38bdf8" stop-opacity="0.04"/>
    </linearGradient>
  </defs>
  <polygon points="{area_pts}" fill="url(#skyGrad)"/>
  <polyline points="{actual_pts}" fill="none" stroke="#38bdf8" stroke-width="2.5" stroke-linejoin="round"/>
  <path d="{forecast_line}" fill="none" stroke="#f59e0b" stroke-width="2" stroke-dasharray="7,4"/>
  {alloc_marks}
  {dots}
  {labels}
  <text x="{pad_l+4}" y="{pad_t+14}" fill="#94a3b8" font-size="10">Credits Used vs Allocated</text>
  <rect x="{w-120}" y="{pad_t}" width="10" height="6" fill="#38bdf8" fill-opacity="0.5" rx="1"/>
  <text x="{w-106}" y="{pad_t+7}" fill="#94a3b8" font-size="9">Actual</text>
  <line x1="{w-80}" y1="{pad_t+3}" x2="{w-70}" y2="{pad_t+3}" stroke="#f59e0b" stroke-width="2" stroke-dasharray="4,2"/>
  <text x="{w-66}" y="{pad_t+7}" fill="#94a3b8" font-size="9">Forecast</text>
</svg>'''


def _donut_svg() -> str:
    """Donut chart 420x260: March spend by category."""
    w, h = 420, 260
    cx, cy_c, r_outer, r_inner = 140, 130, 100, 58

    items = MARCH_BREAKDOWN
    total = sum(x["credits"] for x in items)
    colors = ["#C74634", "#ef6c4a", "#38bdf8", "#818cf8"]

    def polar(angle, radius):
        rad = math.radians(angle - 90)
        return cx + radius * math.cos(rad), cy_c + radius * math.sin(rad)

    slices = ""
    start_angle = 0.0
    for i, item in enumerate(items):
        sweep = (item["credits"] / total) * 360
        end_angle = start_angle + sweep
        large = 1 if sweep > 180 else 0
        ox, oy = polar(start_angle, r_outer)
        ex, ey = polar(end_angle, r_outer)
        ix_e, iy_e = polar(end_angle, r_inner)
        ix_s, iy_s = polar(start_angle, r_inner)
        path = (f"M {ox:.2f},{oy:.2f} "
                f"A {r_outer},{r_outer} 0 {large},1 {ex:.2f},{ey:.2f} "
                f"L {ix_e:.2f},{iy_e:.2f} "
                f"A {r_inner},{r_inner} 0 {large},0 {ix_s:.2f},{iy_s:.2f} Z")
        slices += f'<path d="{path}" fill="{colors[i]}" stroke="#0f172a" stroke-width="2"/>'
        start_angle = end_angle

    # Legend
    legend = ""
    for i, item in enumerate(items):
        ly = 60 + i * 42
        pct = item["credits"] / total * 100
        short = item["category"].replace("_", " ")
        legend += (
            f'<rect x="290" y="{ly}" width="12" height="12" fill="{colors[i]}" rx="2"/>'
            f'<text x="308" y="{ly+10}" fill="#e2e8f0" font-size="11" font-weight="600">{short}</text>'
            f'<text x="308" y="{ly+23}" fill="#64748b" font-size="10">{item["credits"]} cr · {pct:.1f}%</text>'
        )

    center_label = (
        f'<text x="{cx}" y="{cy_c-6}" fill="#e2e8f0" font-size="13" font-weight="700" text-anchor="middle">6,241</text>'
        f'<text x="{cx}" y="{cy_c+10}" fill="#64748b" font-size="9" text-anchor="middle">Mar credits</text>'
    )

    return f'''<svg width="{w}" height="{h}" xmlns="http://www.w3.org/2000/svg">
  <rect width="{w}" height="{h}" fill="#0f172a" rx="8"/>
  {slices}
  <circle cx="{cx}" cy="{cy_c}" r="{r_inner-2}" fill="#0f172a"/>
  {center_label}
  {legend}
  <text x="{cx}" y="{h-12}" fill="#64748b" font-size="10" text-anchor="middle">March 2026 Spend by Category</text>
</svg>'''


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    burn_svg  = _burn_rate_svg()
    donut_svg = _donut_svg()

    period_rows = ""
    for p in PERIODS:
        pct = round(p["used"] / p["allocated"] * 100, 1) if p["allocated"] else 0
        bar_color = "#38bdf8" if p["status"] == "ACTIVE" else ("#f59e0b" if p["status"] == "PENDING" else "#475569")
        status_color = {"ACTIVE": "#22c55e", "CLOSED": "#64748b", "PENDING": "#f59e0b"}.get(p["status"], "#94a3b8")
        forecast_cell = f"{p.get('forecast', '')} cr (forecast)" if p["status"] == "PENDING" else ""
        period_rows += f"""
        <tr>
          <td style='padding:10px 14px;color:#e2e8f0;font-weight:600'>{p['month']}</td>
          <td style='padding:10px 14px;color:#94a3b8'>{p['allocated']:,}</td>
          <td style='padding:10px 14px;color:#e2e8f0'>{p['used']:,}</td>
          <td style='padding:10px 14px'>
            <div style='background:#1e293b;border-radius:4px;height:8px;width:120px'>
              <div style='background:{bar_color};width:{min(pct,100)}%;height:8px;border-radius:4px'></div>
            </div>
            <span style='color:#94a3b8;font-size:11px'>{pct}%</span>
          </td>
          <td style='padding:10px 14px;color:#94a3b8'>{p['remaining']:,} {forecast_cell}</td>
          <td style='padding:10px 14px'><span style='background:{status_color}22;color:{status_color};padding:2px 10px;border-radius:12px;font-size:11px;font-weight:700'>{p['status']}</span></td>
        </tr>"""

    breakdown_rows = ""
    for item in MARCH_BREAKDOWN:
        breakdown_rows += f"""
        <tr>
          <td style='padding:8px 14px;color:#e2e8f0'>{item['category']}</td>
          <td style='padding:8px 14px;color:#38bdf8;font-weight:600'>{item['credits']:,}</td>
          <td style='padding:8px 14px;color:#94a3b8'>${item['usd']:,.2f}</td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Token Budget Tracker — OCI Robot Cloud</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; }}
    .header {{ background: linear-gradient(135deg,#1e293b,#0f172a); border-bottom: 1px solid #1e293b;
               padding: 18px 32px; display: flex; align-items: center; gap: 16px; }}
    .header .logo {{ width: 28px; height: 28px; background: #C74634; border-radius: 6px;
                    display: flex; align-items: center; justify-content: center; font-weight: 900;
                    color: #fff; font-size: 14px; }}
    .header h1 {{ font-size: 20px; font-weight: 700; }}
    .header .sub {{ color: #64748b; font-size: 13px; margin-top: 2px; }}
    .badge {{ background: #22c55e22; color: #22c55e; padding: 2px 10px; border-radius: 12px;
              font-size: 11px; font-weight: 700; margin-left: 12px; }}
    .content {{ padding: 28px 32px; }}
    .kpi-row {{ display: flex; gap: 16px; margin-bottom: 28px; flex-wrap: wrap; }}
    .kpi {{ background: #1e293b; border: 1px solid #334155; border-radius: 10px;
            padding: 18px 24px; flex: 1; min-width: 180px; }}
    .kpi .val {{ font-size: 26px; font-weight: 800; color: #38bdf8; }}
    .kpi .lbl {{ color: #64748b; font-size: 12px; margin-top: 4px; }}
    .alert-box {{ background: #f59e0b18; border: 1px solid #f59e0b44; border-radius: 8px;
                 padding: 12px 18px; margin-bottom: 28px; color: #fcd34d; font-size: 13px; }}
    .section-title {{ font-size: 15px; font-weight: 700; color: #94a3b8; margin-bottom: 14px;
                      text-transform: uppercase; letter-spacing: .06em; }}
    .card {{ background: #1e293b; border: 1px solid #334155; border-radius: 10px;
             padding: 20px; margin-bottom: 24px; }}
    table {{ width: 100%; border-collapse: collapse; }}
    tr:nth-child(even) {{ background: #ffffff06; }}
    th {{ padding: 10px 14px; text-align: left; color: #64748b; font-size: 11px;
          text-transform: uppercase; letter-spacing: .06em; border-bottom: 1px solid #334155; }}
    .charts-row {{ display: flex; gap: 20px; flex-wrap: wrap; margin-bottom: 24px; }}
    .chart-card {{ background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 16px; }}
  </style>
</head>
<body>
<div class="header">
  <div class="logo">T</div>
  <div>
    <h1>Token Budget Tracker <span class="badge">ACTIVE</span></h1>
    <div class="sub">OCI Robot Cloud · Compute Credit Dashboard · Port 8154</div>
  </div>
</div>
<div class="content">
  <div class="kpi-row">
    <div class="kpi"><div class="val">$99.40</div><div class="lbl">Daily Burn Rate</div></div>
    <div class="kpi"><div class="val">100.6d</div><div class="lbl">Days Until Apr Budget Exhausted</div></div>
    <div class="kpi"><div class="val" style="color:#22c55e">78%</div><div class="lbl">Efficiency Score (productive vs overhead)</div></div>
    <div class="kpi"><div class="val" style="color:#f59e0b">1,759</div><div class="lbl">Mar Credits Remaining</div></div>
  </div>

  <div class="alert-box">&#9888; {KPIS['alert']}</div>

  <div class="charts-row">
    <div class="chart-card">
      <div class="section-title" style="margin-bottom:10px">Burn Rate — 4-Month Trend</div>
      {burn_svg}
    </div>
    <div class="chart-card">
      <div class="section-title" style="margin-bottom:10px">March Spend by Category</div>
      {donut_svg}
    </div>
  </div>

  <div class="card">
    <div class="section-title">Budget Periods</div>
    <table>
      <thead><tr>
        <th>Period</th><th>Allocated</th><th>Used</th><th>Burn %</th><th>Remaining</th><th>Status</th>
      </tr></thead>
      <tbody>{period_rows}</tbody>
    </table>
  </div>

  <div class="card">
    <div class="section-title">March 2026 — Credit Breakdown</div>
    <table>
      <thead><tr><th>Category</th><th>Credits</th><th>USD Equiv.</th></tr></thead>
      <tbody>{breakdown_rows}</tbody>
    </table>
  </div>
</div>
</body>
</html>"""
    return HTMLResponse(content=html)


@app.get("/periods")
async def get_periods():
    return JSONResponse(content={"periods": PERIODS})


@app.get("/current")
async def get_current():
    current = next((p for p in PERIODS if p["status"] == "ACTIVE"), None)
    return JSONResponse(content={"current_period": current, "breakdown": MARCH_BREAKDOWN, "kpis": KPIS})


@app.get("/forecast")
async def get_forecast():
    pending = [p for p in PERIODS if p["status"] == "PENDING"]
    return JSONResponse(content={
        "forecast_periods": pending,
        "methodology": "linear trend from Jan-Mar actuals",
        "confidence": "medium",
        "daily_burn_rate_usd": KPIS["daily_burn_rate_usd"],
    })


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8154)
