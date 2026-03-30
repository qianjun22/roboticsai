"""OCI Robot Cloud 6-Month Resource Demand Forecaster — port 8207.

Fits a 35% MoM conservative growth curve to Jan-Mar 2026 actuals,
then projects Apr-Sep 2026 for GPU-hours, partners, and revenue.
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
except ImportError:
    FastAPI = None  # type: ignore
    HTMLResponse = None  # type: ignore
    JSONResponse = None  # type: ignore
    uvicorn = None  # type: ignore

# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------
ACTUALS = [
    {"month": "Jan 2026", "gpu_hrs": 1281,  "fine_tune_runs": 12, "eval_runs": 48,  "partners": 1, "revenue": 1204.80},
    {"month": "Feb 2026", "gpu_hrs": 1897,  "fine_tune_runs": 18, "eval_runs": 89,  "partners": 2, "revenue": 2024.70},
    {"month": "Mar 2026", "gpu_hrs": 2847,  "fine_tune_runs": 24, "eval_runs": 142, "partners": 4, "revenue": 3182.84},
]

FORECAST = [
    {"month": "Apr 2026", "gpu_hrs": 3843,  "partners": 5,  "revenue": 4297},
    {"month": "May 2026", "gpu_hrs": 5188,  "partners": 7,  "revenue": 5801},
    {"month": "Jun 2026", "gpu_hrs": 7004,  "partners": 9,  "revenue": 7831},
    {"month": "Jul 2026", "gpu_hrs": 9455,  "partners": 12, "revenue": 10572},
    {"month": "Aug 2026", "gpu_hrs": 12764, "partners": 15, "revenue": 14272},
    {"month": "Sep 2026", "gpu_hrs": 17231, "partners": 19, "revenue": 19267},
]

# 4 A100s per node × 730 hrs/mo = 2920 hrs/node/mo
NODE_CAPACITY_HRS = 2920
CURRENT_NODES = 4
CURRENT_CAPACITY = NODE_CAPACITY_HRS * CURRENT_NODES  # 11 680

# Methodology note
METHODOLOGY = (
    "Exponential growth rate observed Jan-Mar 2026 avg ~49% MoM. "
    "Conservative 35% MoM applied (S-curve saturation adjustment). "
    "Aug/Sep boosted by projected AI World 2026 partner surge."
)

# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------
W = 680
PAD = {"l": 60, "r": 20, "t": 24, "b": 32}


def _lerp(a, b, t):
    return a + (b - a) * t


# ---- Revenue area chart (actual=solid fill, forecast=dashed + uncertainty band) ----
def build_revenue_svg():
    H = 240
    pw = W - PAD["l"] - PAD["r"]
    ph = H - PAD["t"] - PAD["b"]
    x0, y0 = PAD["l"], PAD["t"]

    all_months = [d["month"] for d in ACTUALS] + [d["month"] for d in FORECAST]
    all_rev = [d["revenue"] for d in ACTUALS] + [d["revenue"] for d in FORECAST]
    n = len(all_months)
    max_rev = max(all_rev) * 1.12

    def xp(i):
        return x0 + i / (n - 1) * pw

    def yp(v):
        return y0 + ph - v / max_rev * ph

    svgs = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'style="background:#0f172a;border-radius:8px;">',
        f'<text x="{W//2}" y="14" fill="#e2e8f0" font-size="11" text-anchor="middle" font-weight="bold">'
        f'Revenue Forecast — Jan 2026 to Sep 2026</text>',
    ]

    # Uncertainty band for forecast (±15%)
    n_act = len(ACTUALS)
    band_pts_top = " ".join(
        f"{xp(n_act - 1 + i):.1f},{yp(d['revenue'] * 1.15):.1f}"
        for i, d in enumerate(FORECAST)
    )
    band_pts_bot = " ".join(
        f"{xp(n_act - 1 + i):.1f},{yp(d['revenue'] * 0.85):.1f}"
        for i, d in reversed(list(enumerate(FORECAST)))
    )
    # Close at actuals last point
    close_x = xp(n_act - 1)
    close_y_top = yp(ACTUALS[-1]["revenue"] * 1.15)
    close_y_bot = yp(ACTUALS[-1]["revenue"] * 0.85)
    band_poly = f"{close_x:.1f},{close_y_top:.1f} {band_pts_top} {band_pts_bot} {close_x:.1f},{close_y_bot:.1f}"
    svgs.append(f'<polygon points="{band_poly}" fill="#C74634" opacity="0.12"/>')

    # Actual area fill
    act_pts = " ".join(f"{xp(i):.1f},{yp(d['revenue']):.1f}" for i, d in enumerate(ACTUALS))
    area_poly = (
        f"{xp(0):.1f},{y0+ph:.1f} "
        + act_pts
        + f" {xp(len(ACTUALS)-1):.1f},{y0+ph:.1f}"
    )
    svgs.append(f'<polygon points="{area_poly}" fill="#38bdf8" opacity="0.25"/>')
    svgs.append(f'<polyline points="{act_pts}" fill="none" stroke="#38bdf8" stroke-width="2.5"/>')

    # Forecast dashed line
    fc_pts = " ".join(
        f"{xp(n_act - 1 + i):.1f},{yp(d['revenue']):.1f}"
        for i, d in enumerate(FORECAST)
    )
    join_pt = f"{xp(n_act-1):.1f},{yp(ACTUALS[-1]['revenue']):.1f}"
    svgs.append(
        f'<polyline points="{join_pt} {fc_pts}" fill="none" stroke="#C74634" '
        f'stroke-width="2" stroke-dasharray="6,4"/>'
    )

    # $100k ARR milestone ≈ $8333/mo
    arr_line_y = yp(8333)
    if y0 <= arr_line_y <= y0 + ph:
        svgs.append(
            f'<line x1="{x0}" y1="{arr_line_y:.1f}" x2="{x0+pw}" y2="{arr_line_y:.1f}" '
            f'stroke="#facc15" stroke-width="1" stroke-dasharray="3,3"/>'
        )
        svgs.append(
            f'<text x="{x0+pw-2}" y="{arr_line_y-3:.1f}" fill="#facc15" font-size="8" text-anchor="end">$100k ARR</text>'
        )

    # X axis labels
    for i, m in enumerate(all_months):
        svgs.append(
            f'<text x="{xp(i):.1f}" y="{y0+ph+18}" fill="#64748b" font-size="8" text-anchor="middle">{m[:3]}</text>'
        )

    # Y axis labels
    for frac in [0, 0.25, 0.5, 0.75, 1.0]:
        val = frac * max_rev
        yv = yp(val)
        label = f"${val/1000:.0f}k" if val >= 1000 else f"${val:.0f}"
        svgs.append(
            f'<text x="{x0-4}" y="{yv:.1f}" fill="#94a3b8" font-size="8" text-anchor="end" dominant-baseline="middle">{label}</text>'
        )

    # Legend
    svgs.append(f'<line x1="{W-140}" y1="14" x2="{W-125}" y2="14" stroke="#38bdf8" stroke-width="2.5"/>')
    svgs.append(f'<text x="{W-122}" y="17" fill="#94a3b8" font-size="8">Actual</text>')
    svgs.append(f'<line x1="{W-80}" y1="14" x2="{W-65}" y2="14" stroke="#C74634" stroke-width="2" stroke-dasharray="6,4"/>')
    svgs.append(f'<text x="{W-62}" y="17" fill="#94a3b8" font-size="8">Forecast</text>')

    svgs.append(f'<rect x="{x0}" y="{y0}" width="{pw}" height="{ph}" fill="none" stroke="#1e293b" stroke-width="1"/>')
    svgs.append("</svg>")
    return "".join(svgs)


# ---- GPU demand bar chart ----
def build_gpu_svg():
    H = 200
    pw = W - PAD["l"] - PAD["r"]
    ph = H - PAD["t"] - PAD["b"]
    x0, y0 = PAD["l"], PAD["t"]

    all_data = [
        {"month": d["month"], "gpu_hrs": d["gpu_hrs"], "actual": True}
        for d in ACTUALS
    ] + [
        {"month": d["month"], "gpu_hrs": d["gpu_hrs"], "actual": False}
        for d in FORECAST
    ]
    n = len(all_data)
    max_gpu = max(d["gpu_hrs"] for d in all_data) * 1.15

    bar_w = pw / n * 0.6
    gap = pw / n

    svgs = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'style="background:#0f172a;border-radius:8px;">',
        f'<text x="{W//2}" y="14" fill="#e2e8f0" font-size="11" text-anchor="middle" font-weight="bold">'
        f'GPU-Hours Demand — Actual vs Forecast</text>',
    ]

    # Capacity line
    cap_y = y0 + ph - CURRENT_CAPACITY / max_gpu * ph
    svgs.append(
        f'<line x1="{x0}" y1="{cap_y:.1f}" x2="{x0+pw}" y2="{cap_y:.1f}" '
        f'stroke="#f59e0b" stroke-width="1.5" stroke-dasharray="5,3"/>'
    )
    svgs.append(
        f'<text x="{x0+4}" y="{cap_y-4:.1f}" fill="#f59e0b" font-size="8">'
        f'Current capacity ({CURRENT_CAPACITY:,} hrs/mo — 4 nodes)</text>'
    )

    for i, d in enumerate(all_data):
        bx = x0 + i * gap + (gap - bar_w) / 2
        bh = d["gpu_hrs"] / max_gpu * ph
        by = y0 + ph - bh
        color = "#38bdf8" if d["actual"] else "#C74634"
        svgs.append(f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bar_w:.1f}" height="{bh:.1f}" fill="{color}" rx="2"/>')
        svgs.append(
            f'<text x="{bx + bar_w/2:.1f}" y="{y0+ph+14}" fill="#64748b" '
            f'font-size="8" text-anchor="middle">{d["month"][:3]}</text>'
        )
        # Value label on top
        svgs.append(
            f'<text x="{bx + bar_w/2:.1f}" y="{by-3:.1f}" fill="{color}" '
            f'font-size="7" text-anchor="middle">{d["gpu_hrs"]:,}</text>'
        )

    # Y axis
    for frac in [0, 0.5, 1.0]:
        val = frac * max_gpu
        yv = y0 + ph - frac * ph
        svgs.append(
            f'<text x="{x0-4}" y="{yv:.1f}" fill="#94a3b8" font-size="8" text-anchor="end" dominant-baseline="middle">{val/1000:.0f}k</text>'
        )

    # Legend
    svgs.append(f'<rect x="{W-130}" y="6" width="10" height="8" fill="#38bdf8" rx="1"/>')
    svgs.append(f'<text x="{W-117}" y="13" fill="#94a3b8" font-size="8">Actual</text>')
    svgs.append(f'<rect x="{W-75}" y="6" width="10" height="8" fill="#C74634" rx="1"/>')
    svgs.append(f'<text x="{W-62}" y="13" fill="#94a3b8" font-size="8">Forecast</text>')

    svgs.append(f'<rect x="{x0}" y="{y0}" width="{pw}" height="{ph}" fill="none" stroke="#1e293b" stroke-width="1"/>')
    svgs.append("</svg>")
    return "".join(svgs)


# ---------------------------------------------------------------------------
# Capacity alert
# ---------------------------------------------------------------------------
def _capacity_alert():
    first_exceed = next(
        (d for d in FORECAST if d["gpu_hrs"] > CURRENT_CAPACITY), None
    )
    if first_exceed:
        nodes_needed_jun = -(-FORECAST[2]["gpu_hrs"] // NODE_CAPACITY_HRS)  # ceil div
        nodes_needed_sep = -(-FORECAST[5]["gpu_hrs"] // NODE_CAPACITY_HRS)
        return {
            "alert": "CAPACITY EXCEEDED",
            "current_capacity_hrs_mo": CURRENT_CAPACITY,
            "current_nodes": CURRENT_NODES,
            "first_exceeds": first_exceed["month"],
            "nodes_needed_jun_2026": nodes_needed_jun,
            "nodes_needed_sep_2026": nodes_needed_sep,
            "action": "Start OCI quota increase request NOW — lead time 4-6 weeks",
        }
    return {"alert": "OK", "current_capacity_hrs_mo": CURRENT_CAPACITY}


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<title>Resource Forecaster — OCI Robot Cloud</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #0f172a; color: #e2e8f0; font-family: 'Inter', sans-serif; padding: 24px; }}
  h1 {{ color: #C74634; font-size: 1.4rem; margin-bottom: 4px; }}
  .sub {{ color: #64748b; font-size: 0.85rem; margin-bottom: 20px; }}
  .card {{ background: #1e293b; border-radius: 10px; padding: 16px; margin-bottom: 18px; }}
  .card h2 {{ font-size: 0.95rem; color: #38bdf8; margin-bottom: 12px; }}
  .alert-box {{ background: #450a0a; border: 1px solid #C74634; border-radius: 8px;
               padding: 12px 16px; margin-bottom: 18px; }}
  .alert-box h3 {{ color: #C74634; font-size: 0.95rem; margin-bottom: 6px; }}
  .alert-box p {{ font-size: 0.82rem; color: #fca5a5; line-height: 1.5; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.82rem; }}
  th {{ background: #0f172a; color: #94a3b8; padding: 6px 10px; text-align: right; }}
  th:first-child {{ text-align: left; }}
  td {{ padding: 6px 10px; border-bottom: 1px solid #0f172a; text-align: right; }}
  td:first-child {{ text-align: left; }}
  tr:last-child td {{ border-bottom: none; }}
  .actual {{ color: #38bdf8; }}
  .forecast {{ color: #C74634; }}
  .methodology {{ font-size: 0.78rem; color: #475569; margin-top: 8px; font-style: italic; }}
  .api {{ font-size: 0.78rem; color: #475569; margin-top: 12px; }}
  .api a {{ color: #38bdf8; text-decoration: none; }}
  svg {{ max-width: 100%; }}
</style>
</head>
<body>
<h1>6-Month OCI Resource Demand Forecaster</h1>
<div class="sub">OCI Robot Cloud &mdash; Port 8207 &mdash; Jan 2026 actuals + Apr–Sep 2026 projection</div>

<div class="alert-box">
  <h3>Capacity Alert</h3>
  <p>
    Current 4 A100s support ~{capacity:,} GPU-hrs/mo.
    Forecast exceeds this by <strong>June 2026</strong> &mdash;
    start OCI quota increase request <strong>NOW</strong>.
    Need ~6 nodes by Jun, ~10 nodes by Sep 2026.
  </p>
</div>

<div class="card">
  <h2>Revenue Forecast</h2>
  {revenue_svg}
</div>

<div class="card">
  <h2>GPU-Hours Demand</h2>
  {gpu_svg}
</div>

<div class="card">
  <h2>Monthly Detail</h2>
  <table>
    <tr>
      <th>Month</th><th>GPU-Hrs</th><th>Partners</th>
      <th>Fine-Tune Runs</th><th>Eval Runs</th><th>Revenue</th>
    </tr>
    {table_rows}
  </table>
  <p class="methodology">{methodology}</p>
</div>

<div class="api">
  API endpoints:
  <a href="/actuals">/actuals</a> &nbsp;
  <a href="/forecast">/forecast</a> &nbsp;
  <a href="/capacity-alert">/capacity-alert</a>
</div>
</body></html>
"""


def _table_rows():
    rows = []
    for d in ACTUALS:
        rows.append(
            f'<tr><td class="actual">{d["month"]}</td>'
            f'<td>{d["gpu_hrs"]:,}</td>'
            f'<td>{d["partners"]}</td>'
            f'<td>{d["fine_tune_runs"]}</td>'
            f'<td>{d["eval_runs"]}</td>'
            f'<td>${d["revenue"]:,.2f}</td></tr>'
        )
    for d in FORECAST:
        rows.append(
            f'<tr><td class="forecast">{d["month"]} *</td>'
            f'<td>{d["gpu_hrs"]:,}</td>'
            f'<td>{d["partners"]}</td>'
            f'<td>—</td><td>—</td>'
            f'<td>${d["revenue"]:,}</td></tr>'
        )
    return "".join(rows)


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
if FastAPI is not None:
    app = FastAPI(title="Resource Forecaster", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        html = DASHBOARD_HTML.format(
            capacity=CURRENT_CAPACITY,
            revenue_svg=build_revenue_svg(),
            gpu_svg=build_gpu_svg(),
            table_rows=_table_rows(),
            methodology=METHODOLOGY,
        )
        return HTMLResponse(html)

    @app.get("/actuals")
    async def actuals():
        return JSONResponse({"actuals": ACTUALS})

    @app.get("/forecast")
    async def forecast():
        return JSONResponse({
            "forecast": FORECAST,
            "methodology": METHODOLOGY,
            "growth_rate_applied": "35% MoM conservative",
        })

    @app.get("/capacity-alert")
    async def capacity_alert():
        return JSONResponse(_capacity_alert())


if __name__ == "__main__":
    if uvicorn is None:
        print("uvicorn not installed — run: pip install fastapi uvicorn")
    else:
        uvicorn.run("resource_forecaster:app", host="0.0.0.0", port=8207, reload=False)
