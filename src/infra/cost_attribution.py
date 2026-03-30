"""GPU Cost Attribution Dashboard — port 8151"""

from __future__ import annotations

import math
from typing import Any

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
except ImportError:  # pragma: no cover
    FastAPI = None  # type: ignore
    HTMLResponse = None  # type: ignore
    JSONResponse = None  # type: ignore
    uvicorn = None  # type: ignore

# ---------------------------------------------------------------------------
# Static data
# ---------------------------------------------------------------------------

MARCH_TOTAL = 3182.84

BY_PARTNER: dict[str, dict[str, Any]] = {
    "physical_intelligence": {"cost": 1847.20, "pct": 58.1},
    "apptronik":             {"cost": 876.50,  "pct": 27.5},
    "1x_technologies":       {"cost": 298.86,  "pct": 9.4},
    "agility_robotics":      {"cost": 160.28,  "pct": 5.0},
}

BY_TASK: dict[str, dict[str, Any]] = {
    "fine_tune": {"cost": 2121.23, "pct": 66.7},
    "sdg":       {"cost": 477.43,  "pct": 15.0},
    "eval":      {"cost": 350.11,  "pct": 11.0},
    "hpo":       {"cost": 234.07,  "pct": 7.4},
}

BY_REGION: dict[str, dict[str, Any]] = {
    "ashburn":   {"cost": 2866.32, "pct": 90.1},
    "phoenix":   {"cost": 190.97,  "pct": 6.0},
    "frankfurt": {"cost": 125.55,  "pct": 3.9},
}

BY_GPU: dict[str, dict[str, Any]] = {
    "A100_80GB": {"cost": 2547.93, "pct": 80.1},
    "A100_40GB": {"cost": 634.91,  "pct": 19.9},
}

# 90-day trend: Jan / Feb / Mar
TREND_MONTHS = ["Jan", "Feb", "Mar"]
TREND: dict[str, list[float]] = {
    "physical_intelligence": [1204.80, 1612.40, 1847.20],
    "apptronik":             [0.0,     412.30,  876.50],
    "1x_technologies":       [0.0,     0.0,     298.86],
    "agility_robotics":      [0.0,     0.0,     160.28],
}

SR_IMPROVEMENT = 0.73  # from 0.05 to 0.78
COST_PER_SR_POINT = MARCH_TOTAL / SR_IMPROVEMENT  # $4,360/pp

PARTNER_COLORS = {
    "physical_intelligence": "#C74634",
    "apptronik":             "#38bdf8",
    "1x_technologies":       "#f59e0b",
    "agility_robotics":      "#22c55e",
}

# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------

def _partner_donut_svg() -> str:
    """420x280 donut: by-partner March breakdown."""
    W, H, R, r = 420, 280, 100, 50
    cx, cy = 155, 145

    slices = list(BY_PARTNER.items())
    total = MARCH_TOTAL

    def arc_path(start_deg: float, end_deg: float, radius: float, inner_r: float) -> str:
        def pt(deg: float, rad: float):
            a = math.radians(deg - 90)
            return cx + rad * math.cos(a), cy + rad * math.sin(a)
        large = 1 if (end_deg - start_deg) > 180 else 0
        ox, oy = pt(start_deg, radius)
        ax, ay = pt(end_deg, radius)
        ix, iy = pt(end_deg, inner_r)
        bx, by = pt(start_deg, inner_r)
        return f"M{ox:.2f},{oy:.2f} A{radius},{radius} 0 {large},1 {ax:.2f},{ay:.2f} L{ix:.2f},{iy:.2f} A{inner_r},{inner_r} 0 {large},0 {bx:.2f},{by:.2f} Z"

    paths = []
    start = 0.0
    for name, data in slices:
        deg = (data["cost"] / total) * 360
        end = start + deg
        color = PARTNER_COLORS[name]
        d = arc_path(start, end, R, r)
        paths.append(f'<path d="{d}" fill="{color}" opacity="0.9" stroke="#0f172a" stroke-width="1.5"/>')
        # label
        mid_deg = start + deg / 2
        a = math.radians(mid_deg - 90)
        lx = cx + (R + 18) * math.cos(a)
        ly = cy + (R + 18) * math.sin(a)
        anchor = "start" if lx > cx else "end"
        paths.append(f'<text x="{lx:.1f}" y="{ly:.1f}" fill="#cbd5e1" font-size="9" text-anchor="{anchor}">{data["pct"]}%</text>')
        start = end

    # center label
    paths.append(f'<text x="{cx}" y="{cy - 6}" fill="#94a3b8" font-size="10" text-anchor="middle">March</text>')
    paths.append(f'<text x="{cx}" y="{cy + 10}" fill="#f8fafc" font-size="13" font-weight="bold" text-anchor="middle">${total:,.0f}</text>')

    # legend
    legend = []
    lx0, ly0 = 280, 60
    for i, (name, data) in enumerate(slices):
        color = PARTNER_COLORS[name]
        lyi = ly0 + i * 24
        legend.append(f'<rect x="{lx0}" y="{lyi}" width="12" height="12" rx="2" fill="{color}"/>')
        legend.append(f'<text x="{lx0 + 16}" y="{lyi + 10}" fill="#cbd5e1" font-size="10">{name.replace("_", " ")} ${data["cost"]:,.0f}</text>')

    body = "\n".join(paths + legend)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'style="background:#1e293b;border-radius:8px">'
        f'<text x="{W//2}" y="16" fill="#94a3b8" font-size="11" text-anchor="middle">Cost by Partner — March 2026</text>'
        f'{body}</svg>'
    )


def _stacked_bar_svg() -> str:
    """680x200 stacked bar: 3 months, 4 partners stacked."""
    W, H, PAD = 680, 200, 40
    chart_w = W - 2 * PAD
    chart_h = H - 2 * PAD

    month_totals = [sum(TREND[p][m] for p in TREND) for m in range(3)]
    max_total = max(month_totals)

    bar_total_w = chart_w / 3
    bar_w = bar_total_w * 0.6
    bar_gap = bar_total_w * 0.2

    partners = list(TREND.keys())

    rects = []
    xlabels = []
    for m, month in enumerate(TREND_MONTHS):
        x = PAD + m * bar_total_w + bar_gap
        cumulative = 0.0
        for partner in partners:
            val = TREND[partner][m]
            if val == 0:
                continue
            bar_h = (val / max_total) * chart_h
            y = PAD + chart_h - cumulative * chart_h / max_total - bar_h
            color = PARTNER_COLORS[partner]
            rects.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{bar_h:.1f}" fill="{color}" opacity="0.85"/>')
            cumulative += val
        # month label
        mx = x + bar_w / 2
        xlabels.append(f'<text x="{mx:.1f}" y="{H - 8}" fill="#94a3b8" font-size="11" text-anchor="middle">{month} 2026</text>')
        # total label
        total_h = (month_totals[m] / max_total) * chart_h
        ty = PAD + chart_h - total_h - 4
        xlabels.append(f'<text x="{mx:.1f}" y="{ty:.1f}" fill="#f8fafc" font-size="10" text-anchor="middle">${month_totals[m]:,.0f}</text>')

    # legend
    legend = []
    lx0 = PAD
    for i, p in enumerate(partners):
        lx = lx0 + i * 150
        legend.append(f'<rect x="{lx}" y="8" width="10" height="10" rx="2" fill="{PARTNER_COLORS[p]}"/>')
        legend.append(f'<text x="{lx + 14}" y="18" fill="#94a3b8" font-size="9">{p.replace("_", " ")}</text>')

    body = "\n".join(rects + xlabels + legend)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'style="background:#1e293b;border-radius:8px">'
        f'<line x1="{PAD}" y1="{PAD + chart_h}" x2="{W - PAD}" y2="{PAD + chart_h}" stroke="#334155" stroke-width="1"/>'
        f'{body}</svg>'
    )


def _task_bar_svg() -> str:
    """680x160 horizontal bar chart by task type."""
    W, H, PAD_L, PAD_R, PAD_V = 680, 160, 110, 20, 20
    chart_w = W - PAD_L - PAD_R
    chart_h = H - 2 * PAD_V

    tasks = list(BY_TASK.items())
    n = len(tasks)
    bar_h = chart_h / n * 0.6
    bar_gap = chart_h / n * 0.4
    max_cost = max(d["cost"] for _, d in tasks)

    task_colors = ["#38bdf8", "#f59e0b", "#a78bfa", "#22c55e"]

    bars = []
    for i, (name, data) in enumerate(tasks):
        bw = (data["cost"] / max_cost) * chart_w
        y = PAD_V + i * (bar_h + bar_gap)
        color = task_colors[i % len(task_colors)]
        bars.append(f'<rect x="{PAD_L}" y="{y:.1f}" width="{bw:.1f}" height="{bar_h:.1f}" rx="3" fill="{color}" opacity="0.85"/>')
        bars.append(f'<text x="{PAD_L - 6}" y="{y + bar_h/2 + 4:.1f}" fill="#94a3b8" font-size="10" text-anchor="end">{name.replace("_", " ")} {data["pct"]}%</text>')
        bars.append(f'<text x="{PAD_L + bw + 4:.1f}" y="{y + bar_h/2 + 4:.1f}" fill="#f8fafc" font-size="10">${data["cost"]:,.0f}</text>')

    body = "\n".join(bars)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'style="background:#1e293b;border-radius:8px">'
        f'<text x="{W//2}" y="14" fill="#94a3b8" font-size="11" text-anchor="middle">Cost by Task Type — March 2026</text>'
        f'{body}</svg>'
    )


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def _dashboard_html() -> str:
    donut_svg = _partner_donut_svg()
    stacked_svg = _stacked_bar_svg()
    task_svg = _task_bar_svg()

    partner_rows = ""
    for name, data in BY_PARTNER.items():
        color = PARTNER_COLORS[name]
        partner_rows += (
            f'<tr><td><span style="display:inline-block;width:10px;height:10px;border-radius:2px;background:{color};margin-right:6px"></span>'
            f'{name.replace("_", " ")}</td><td>${data["cost"]:,.2f}</td><td>{data["pct"]}%</td></tr>'
        )

    task_rows = ""
    for name, data in BY_TASK.items():
        task_rows += f'<tr><td>{name.replace("_", " ")}</td><td>${data["cost"]:,.2f}</td><td>{data["pct"]}%</td></tr>'

    region_rows = ""
    for name, data in BY_REGION.items():
        region_rows += f'<tr><td>{name}</td><td>${data["cost"]:,.2f}</td><td>{data["pct"]}%</td></tr>'

    gpu_rows = ""
    for name, data in BY_GPU.items():
        gpu_rows += f'<tr><td>{name}</td><td>${data["cost"]:,.2f}</td><td>{data["pct"]}%</td></tr>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Cost Attribution | OCI Robot Cloud</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',system-ui,sans-serif;padding:24px}}
h1{{color:#C74634;font-size:1.6rem;margin-bottom:4px}}
.sub{{color:#64748b;font-size:0.85rem;margin-bottom:24px}}
.grid2{{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-bottom:20px}}
.grid3{{display:grid;grid-template-columns:repeat(3,1fr);gap:20px;margin-bottom:20px}}
.card{{background:#1e293b;border-radius:10px;padding:20px}}
.card h2{{font-size:1rem;color:#94a3b8;margin-bottom:14px;text-transform:uppercase;letter-spacing:.05em}}
table{{width:100%;border-collapse:collapse;font-size:0.88rem}}
th{{color:#64748b;font-weight:600;padding:6px 10px;text-align:left;border-bottom:1px solid #334155}}
td{{padding:6px 10px;border-bottom:1px solid #1e293b}}
.stat{{font-size:2rem;font-weight:700;color:#38bdf8}}
.stat-label{{font-size:0.75rem;color:#64748b;margin-top:4px}}
.stats-row{{display:flex;gap:20px;margin-bottom:20px}}
.stat-card{{background:#1e293b;border-radius:10px;padding:16px 24px;flex:1;text-align:center}}
svg{{max-width:100%;height:auto}}
</style>
</head>
<body>
<h1>Cost Attribution Dashboard</h1>
<p class="sub">OCI Robot Cloud · GPU Spend Analysis · Port 8151</p>

<div class="stats-row">
  <div class="stat-card"><div class="stat" style="color:#C74634">${MARCH_TOTAL:,.2f}</div><div class="stat-label">March 2026 Total</div></div>
  <div class="stat-card"><div class="stat">$4,360</div><div class="stat-label">Cost per SR point</div></div>
  <div class="stat-card"><div class="stat">4</div><div class="stat-label">Active Partners</div></div>
  <div class="stat-card"><div class="stat" style="color:#22c55e">+73pp</div><div class="stat-label">SR Improvement</div></div>
  <div class="stat-card"><div class="stat">3</div><div class="stat-label">Regions</div></div>
</div>

<div class="grid2">
  <div class="card">
    <h2>Partner Breakdown</h2>
    {donut_svg}
  </div>
  <div class="card">
    <h2>Partner Detail</h2>
    <table>
      <thead><tr><th>Partner</th><th>Cost</th><th>Share</th></tr></thead>
      <tbody>{partner_rows}</tbody>
    </table>
    <div style="margin-top:20px">
      <h2 style="font-size:0.9rem;color:#94a3b8;margin-bottom:10px">BY TASK TYPE</h2>
      <table>
        <thead><tr><th>Task</th><th>Cost</th><th>Share</th></tr></thead>
        <tbody>{task_rows}</tbody>
      </table>
    </div>
  </div>
</div>

<div class="card" style="margin-bottom:20px">
  <h2>90-Day Trend — Stacked by Partner</h2>
  {stacked_svg}
</div>

<div class="card" style="margin-bottom:20px">
  <h2>Task Type Breakdown</h2>
  {task_svg}
</div>

<div class="grid2">
  <div class="card">
    <h2>By Region</h2>
    <table>
      <thead><tr><th>Region</th><th>Cost</th><th>Share</th></tr></thead>
      <tbody>{region_rows}</tbody>
    </table>
  </div>
  <div class="card">
    <h2>By GPU Type</h2>
    <table>
      <thead><tr><th>GPU</th><th>Cost</th><th>Share</th></tr></thead>
      <tbody>{gpu_rows}</tbody>
    </table>
    <div style="margin-top:16px;padding:12px;background:#0f172a;border-radius:6px">
      <p style="font-size:0.82rem;color:#64748b">Cost Efficiency</p>
      <p style="color:#38bdf8;font-size:1.1rem;font-weight:700">$4,360 / SR point</p>
      <p style="font-size:0.78rem;color:#475569;margin-top:4px">$3,182.84 total ÷ 0.73 SR improvement (0.05→0.78)</p>
    </div>
  </div>
</div>

<p style="color:#334155;font-size:0.75rem;margin-top:20px;text-align:center">
  API: GET /summary · /by-partner · /by-task-type · /trend | Oracle Confidential
</p>
</body></html>"""


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

if FastAPI is not None:
    app = FastAPI(title="Cost Attribution", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    def dashboard() -> HTMLResponse:
        return HTMLResponse(_dashboard_html())

    @app.get("/summary")
    def summary() -> JSONResponse:
        return JSONResponse({
            "period": "2026-03",
            "total_usd": MARCH_TOTAL,
            "sr_improvement": SR_IMPROVEMENT,
            "cost_per_sr_point": round(COST_PER_SR_POINT, 2),
            "partners": len(BY_PARTNER),
            "regions": len(BY_REGION),
        })

    @app.get("/by-partner")
    def by_partner() -> JSONResponse:
        return JSONResponse({
            "period": "2026-03",
            "breakdown": [
                {"partner": k, **v} for k, v in BY_PARTNER.items()
            ],
        })

    @app.get("/by-task-type")
    def by_task_type() -> JSONResponse:
        return JSONResponse({
            "period": "2026-03",
            "breakdown": [
                {"task_type": k, **v} for k, v in BY_TASK.items()
            ],
        })

    @app.get("/trend")
    def trend() -> JSONResponse:
        rows = []
        for m_idx, month in enumerate(TREND_MONTHS):
            row: dict[str, Any] = {"month": month}
            for partner, vals in TREND.items():
                row[partner] = vals[m_idx]
            row["total"] = sum(TREND[p][m_idx] for p in TREND)
            rows.append(row)
        return JSONResponse({"months": TREND_MONTHS, "data": rows})


if __name__ == "__main__":
    if uvicorn is None:
        raise RuntimeError("uvicorn not installed — run: pip install fastapi uvicorn")
    uvicorn.run("cost_attribution:app", host="0.0.0.0", port=8151, reload=True)
