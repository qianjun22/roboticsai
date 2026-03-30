"""
OCI Robot Cloud — Task Success Rate Forecaster
Port 8684 | Probabilistic SR forecast through Sep 2026 with contributing factor decomposition
"""

import math
import datetime
import json

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

# ---------------------------------------------------------------------------
# Forecast Data
# ---------------------------------------------------------------------------

MONTHS = ["Apr", "May", "Jun", "Jul", "Aug", "Sep"]
MONTH_IDX = list(range(len(MONTHS)))  # 0-5

# Probabilistic SR forecast (p10 / p50 / p90)
FORECAST = {
    "p10": [0.78, 0.79, 0.80, 0.81, 0.82, 0.83],
    "p50": [0.78, 0.80, 0.82, 0.84, 0.86, 0.88],
    "p90": [0.78, 0.81, 0.84, 0.87, 0.89, 0.91],
}

# Historical SR (Jan-Mar 2026)
HISTORICAL = [
    {"month": "Jan", "sr": 0.62, "historical": True},
    {"month": "Feb", "sr": 0.68, "historical": True},
    {"month": "Mar", "sr": 0.74, "historical": True},
    {"month": "Apr", "sr": 0.78, "historical": True},  # current
]

# Milestones (DAgger run index in month array)
MILESTONES = [
    {"month_idx": 1, "label": "DAgger run10"},
    {"month_idx": 3, "label": "DAgger run11"},
]

# Contributing factors per month (stacked, must sum to ~forecast p50 delta each month)
# Absolute contribution to SR above 0.78 baseline
FACTORS = {
    "DAgger":        [0.000, 0.006, 0.012, 0.018, 0.024, 0.030],
    "Real Demos":    [0.000, 0.004, 0.006, 0.008, 0.010, 0.012],
    "Cosmos":        [0.000, 0.002, 0.004, 0.006, 0.008, 0.010],
    "Distillation":  [0.000, 0.002, 0.003, 0.005, 0.006, 0.008],
    "Data Flywheel": [0.000, 0.000, 0.002, 0.003, 0.004, 0.006],
}

FACTOR_COLORS = [
    "#38bdf8",  # DAgger
    "#22c55e",  # Real Demos
    "#f59e0b",  # Cosmos
    "#a78bfa",  # Distillation
    "#f472b6",  # Data Flywheel
]

KEY_METRICS = {
    "base_case_sep": 0.88,
    "best_sep": 0.91,
    "worst_sep": 0.83,
    "run11_lift_pp": 0.06,
    "real_demos_per_100_pp": 0.02,
    "cosmos_lift_pp": 0.05,
    "current_sr": 0.78,
}

# ---------------------------------------------------------------------------
# SVG Helpers
# ---------------------------------------------------------------------------

SVG_W = 680
SVG_H = 300
PAD_L, PAD_R, PAD_T, PAD_B = 60, 30, 30, 50
CHART_W = SVG_W - PAD_L - PAD_R
CHART_H = SVG_H - PAD_T - PAD_B
Y_MIN, Y_MAX = 0.60, 1.00


def x_pos(idx: int) -> float:
    """Map month index (0-5) to SVG x coordinate."""
    return PAD_L + idx * CHART_W / (len(MONTHS) - 1)


def y_pos(sr: float) -> float:
    """Map SR value to SVG y coordinate."""
    frac = (sr - Y_MIN) / (Y_MAX - Y_MIN)
    return PAD_T + CHART_H * (1.0 - frac)


def _axis_lines() -> str:
    lines = []
    # Y gridlines
    for sr in [0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95, 1.00]:
        y = y_pos(sr)
        lines.append(
            f'<line x1="{PAD_L}" y1="{y:.1f}" x2="{PAD_L + CHART_W}" y2="{y:.1f}" '
            f'stroke="#1e293b" stroke-width="1"/>'
        )
        lines.append(
            f'<text x="{PAD_L - 6}" y="{y + 4:.1f}" text-anchor="end" '
            f'font-size="9" fill="#64748b" font-family="monospace">{sr:.2f}</text>'
        )
    # X axis labels
    for i, m in enumerate(MONTHS):
        x = x_pos(i)
        lines.append(
            f'<text x="{x:.1f}" y="{PAD_T + CHART_H + 18}" text-anchor="middle" '
            f'font-size="10" fill="#94a3b8" font-family="monospace">{m}</text>'
        )
    # Axis border
    lines.append(
        f'<rect x="{PAD_L}" y="{PAD_T}" width="{CHART_W}" height="{CHART_H}" '
        f'fill="none" stroke="#334155" stroke-width="1"/>'
    )
    return "\n".join(lines)


def build_svg_fan_chart() -> str:
    """SR forecast fan chart: shaded p10/p50/p90 bands."""
    lines = []
    lines.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{SVG_W}" height="{SVG_H}" '
        f'style="background:#0f172a;border-radius:8px;">'
    )
    lines.append(f'<rect width="{SVG_W}" height="{SVG_H}" fill="#0f172a" rx="8"/>')
    lines.append(_axis_lines())

    # Shaded band: p10-p90
    pts_top = " ".join(f"{x_pos(i):.1f},{y_pos(v):.1f}" for i, v in enumerate(FORECAST["p90"]))
    pts_bot = " ".join(f"{x_pos(i):.1f},{y_pos(v):.1f}" for i, v in enumerate(FORECAST["p10"]))
    # Build polygon: top (p90 left→right), bottom (p10 right→left)
    poly_pts = pts_top + " " + " ".join(
        f"{x_pos(i):.1f},{y_pos(v):.1f}" for i, v in reversed(list(enumerate(FORECAST["p10"])))
    )
    lines.append(f'<polygon points="{poly_pts}" fill="#38bdf8" opacity="0.12"/>')

    # p10 / p90 dashed boundary
    for key, color, dash in [("p10", "#38bdf8", "4,3"), ("p90", "#38bdf8", "4,3")]:
        pts = " ".join(f"{x_pos(i):.1f},{y_pos(v):.1f}" for i, v in enumerate(FORECAST[key]))
        lines.append(
            f'<polyline points="{pts}" fill="none" stroke="{color}" '
            f'stroke-width="1" stroke-dasharray="{dash}" opacity="0.5"/>'
        )

    # p50 solid line
    pts_p50 = " ".join(f"{x_pos(i):.1f},{y_pos(v):.1f}" for i, v in enumerate(FORECAST["p50"]))
    lines.append(
        f'<polyline points="{pts_p50}" fill="none" stroke="#38bdf8" stroke-width="2.5"/>'
    )

    # Milestone annotations
    for ms in MILESTONES:
        mx = x_pos(ms["month_idx"])
        lines.append(
            f'<line x1="{mx:.1f}" y1="{PAD_T}" x2="{mx:.1f}" y2="{PAD_T + CHART_H}" '
            f'stroke="#C74634" stroke-width="1.5" stroke-dasharray="5,3" opacity="0.8"/>'
        )
        lines.append(
            f'<text x="{mx + 4:.1f}" y="{PAD_T + 14}" font-size="9" fill="#C74634" '
            f'font-family="monospace">{ms["label"]}</text>'
        )

    # Current SR dot
    cx0, cy0 = x_pos(0), y_pos(FORECAST["p50"][0])
    lines.append(f'<circle cx="{cx0:.1f}" cy="{cy0:.1f}" r="5" fill="#C74634"/>')
    lines.append(
        f'<text x="{cx0 + 8:.1f}" y="{cy0 - 6:.1f}" font-size="9" fill="#C74634" '
        f'font-family="monospace">SR=0.78</text>'
    )

    # Legend
    leg_y = SVG_H - 12
    for label, color, dash in [
        ("p50 (base)", "#38bdf8", ""),
        ("p10/p90 band", "#38bdf8", "4,3"),
        ("Milestones", "#C74634", "5,3"),
    ]:
        pass  # inline legend below chart

    lines.append("</svg>")
    return "\n".join(lines)


def build_svg_stacked_area() -> str:
    """Contributing factor decomposition stacked area chart."""
    factor_names = list(FACTORS.keys())
    # Compute cumulative stacks
    stacks = []  # stacks[factor_idx][month_idx] = cumulative SR from baseline
    cum = [0.78] * len(MONTHS)
    for fi, name in enumerate(factor_names):
        vals = FACTORS[name]
        top = [cum[i] + vals[i] for i in range(len(MONTHS))]
        stacks.append((name, list(cum), top))
        cum = top

    W, H = 680, 280
    pl, pr, pt, pb = 60, 30, 30, 50
    cw = W - pl - pr
    ch = H - pt - pb
    y0, y1 = 0.76, 0.92

    def xp(i): return pl + i * cw / (len(MONTHS) - 1)
    def yp(v): return pt + ch * (1.0 - (v - y0) / (y1 - y0))

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'style="background:#0f172a;border-radius:8px;">',
        f'<rect width="{W}" height="{H}" fill="#0f172a" rx="8"/>',
    ]

    # Gridlines
    for sr in [0.78, 0.80, 0.82, 0.84, 0.86, 0.88, 0.90]:
        y = yp(sr)
        lines.append(
            f'<line x1="{pl}" y1="{y:.1f}" x2="{pl + cw}" y2="{y:.1f}" '
            f'stroke="#1e293b" stroke-width="1"/>'
        )
        lines.append(
            f'<text x="{pl - 6}" y="{y + 4:.1f}" text-anchor="end" font-size="9" '
            f'fill="#64748b" font-family="monospace">{sr:.2f}</text>'
        )
    for i, m in enumerate(MONTHS):
        x = xp(i)
        lines.append(
            f'<text x="{x:.1f}" y="{pt + ch + 18}" text-anchor="middle" '
            f'font-size="10" fill="#94a3b8" font-family="monospace">{m}</text>'
        )

    # Stacked areas (bottom to top)
    for fi, (name, bot, top) in enumerate(stacks):
        color = FACTOR_COLORS[fi]
        # Polygon: top left→right, then bottom right→left
        poly = " ".join(f"{xp(i):.1f},{yp(top[i]):.1f}" for i in range(len(MONTHS)))
        poly += " " + " ".join(
            f"{xp(i):.1f},{yp(bot[i]):.1f}" for i in reversed(range(len(MONTHS)))
        )
        lines.append(
            f'<polygon points="{poly}" fill="{color}" opacity="0.55"/>'
        )
        # Top border line
        tline = " ".join(f"{xp(i):.1f},{yp(top[i]):.1f}" for i in range(len(MONTHS)))
        lines.append(
            f'<polyline points="{tline}" fill="none" stroke="{color}" stroke-width="1.5"/>'
        )

    # Legend
    lx = pl + 10
    for fi, name in enumerate(factor_names):
        rx = lx + fi * 120
        lines.append(
            f'<rect x="{rx}" y="{pt + 6}" width="10" height="10" '
            f'fill="{FACTOR_COLORS[fi]}" opacity="0.8" rx="2"/>'
        )
        lines.append(
            f'<text x="{rx + 14}" y="{pt + 15}" font-size="9" fill="#94a3b8" '
            f'font-family="monospace">{name}</text>'
        )

    lines.append("</svg>")
    return "\n".join(lines)


def build_svg_scatter() -> str:
    """Historical + forecast scatter with widening CI."""
    W, H = 680, 260
    pl, pr, pt, pb = 60, 30, 30, 50
    cw = W - pl - pr
    ch = H - pt - pb
    y0, y1 = 0.55, 1.00

    # Map historical months onto x axis (Jan=0 through Sep=8)
    all_months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep"]
    total = len(all_months) - 1

    def xp(m_idx): return pl + m_idx * cw / total
    def yp(v): return pt + ch * (1.0 - (v - y0) / (y1 - y0))

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'style="background:#0f172a;border-radius:8px;">',
        f'<rect width="{W}" height="{H}" fill="#0f172a" rx="8"/>',
    ]

    # Gridlines
    for sr in [0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95]:
        y = yp(sr)
        lines.append(
            f'<line x1="{pl}" y1="{y:.1f}" x2="{pl + cw}" y2="{y:.1f}" '
            f'stroke="#1e293b" stroke-width="1"/>'
        )
        lines.append(
            f'<text x="{pl - 6}" y="{y + 4:.1f}" text-anchor="end" font-size="9" '
            f'fill="#64748b" font-family="monospace">{sr:.2f}</text>'
        )
    for i, m in enumerate(all_months):
        x = xp(i)
        lines.append(
            f'<text x="{x:.1f}" y="{pt + ch + 18}" text-anchor="middle" '
            f'font-size="10" fill="#94a3b8" font-family="monospace">{m}</text>'
        )

    # Historical dots (Jan-Mar) + current (Apr)
    hist_data = [(0, 0.62), (1, 0.68), (2, 0.74), (3, 0.78)]
    for mi, sr in hist_data:
        lines.append(
            f'<circle cx="{xp(mi):.1f}" cy="{yp(sr):.1f}" r="5" '
            f'fill="#22c55e" opacity="0.9"/>'
        )

    # Forecast dots + CI bars (Apr-Sep, wider CI each month)
    forecast_months = list(range(3, 9))  # Apr=3 through Sep=8
    ci_half_base = 0.005
    for i, mi in enumerate(forecast_months):
        sr_p50 = FORECAST["p50"][i]
        sr_p10 = FORECAST["p10"][i]
        sr_p90 = FORECAST["p90"][i]
        x = xp(mi)
        y_med = yp(sr_p50)
        y_lo = yp(sr_p90)  # higher SR = lower y
        y_hi = yp(sr_p10)
        # CI whisker
        lines.append(
            f'<line x1="{x:.1f}" y1="{y_lo:.1f}" x2="{x:.1f}" y2="{y_hi:.1f}" '
            f'stroke="#38bdf8" stroke-width="{1.0 + i * 0.3:.1f}" opacity="0.5"/>'
        )
        lines.append(
            f'<line x1="{x - 5:.1f}" y1="{y_lo:.1f}" x2="{x + 5:.1f}" y2="{y_lo:.1f}" '
            f'stroke="#38bdf8" stroke-width="1" opacity="0.5"/>'
        )
        lines.append(
            f'<line x1="{x - 5:.1f}" y1="{y_hi:.1f}" x2="{x + 5:.1f}" y2="{y_hi:.1f}" '
            f'stroke="#38bdf8" stroke-width="1" opacity="0.5"/>'
        )
        # Forecast dot
        lines.append(
            f'<circle cx="{x:.1f}" cy="{y_med:.1f}" r="4" '
            f'fill="#38bdf8" opacity="0.85"/>'
        )

    # Legend
    lines.append(
        f'<circle cx="{pl + 10}" cy="{pt + 10}" r="5" fill="#22c55e" opacity="0.9"/>'
    )
    lines.append(
        f'<text x="{pl + 20}" y="{pt + 14}" font-size="9" fill="#94a3b8" '
        f'font-family="monospace">Historical</text>'
    )
    lines.append(
        f'<circle cx="{pl + 100}" cy="{pt + 10}" r="4" fill="#38bdf8" opacity="0.85"/>'
    )
    lines.append(
        f'<text x="{pl + 112}" y="{pt + 14}" font-size="9" fill="#94a3b8" '
        f'font-family="monospace">Forecast (p50) + CI</text>'
    )

    lines.append("</svg>")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# HTML Page
# ---------------------------------------------------------------------------

def build_html() -> str:
    fan = build_svg_fan_chart()
    stacked = build_svg_stacked_area()
    scatter = build_svg_scatter()

    def metric_card(label: str, value: str, color: str = "#38bdf8") -> str:
        return f"""
        <div style="background:#1e293b;border-radius:8px;padding:14px 18px;flex:1;min-width:130px;">
          <div style="color:#64748b;font-size:11px;text-transform:uppercase;
                      letter-spacing:1px;margin-bottom:6px;">{label}</div>
          <div style="color:{color};font-size:26px;font-weight:800;">{value}</div>
        </div>"""

    cards = (
        metric_card("Base Sep SR", f"{KEY_METRICS['base_case_sep']:.0%}", "#38bdf8") +
        metric_card("Best Case", f"{KEY_METRICS['best_sep']:.0%}", "#22c55e") +
        metric_card("Worst Case", f"{KEY_METRICS['worst_sep']:.0%}", "#f59e0b") +
        metric_card("run11 Lift", f"+{KEY_METRICS['run11_lift_pp']:.0%}pp", "#C74634") +
        metric_card("Cosmos Lift", f"+{KEY_METRICS['cosmos_lift_pp']:.0%}pp", "#a78bfa") +
        metric_card("Current SR", f"{KEY_METRICS['current_sr']:.0%}", "#f472b6")
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>OCI Robot Cloud — Task SR Forecaster</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #f1f5f9; font-family: -apple-system, BlinkMacSystemFont,
            'Segoe UI', sans-serif; min-height: 100vh; }}
    h1 {{ color: #C74634; font-size: 22px; font-weight: 800; letter-spacing: 0.5px; }}
    .section {{ background: #1e293b; border-radius: 10px; padding: 20px 22px; margin-bottom: 22px; }}
    .section-title {{ color: #C74634; font-size: 12px; font-weight: 700; letter-spacing: 1px;
                      text-transform: uppercase; margin-bottom: 14px; }}
  </style>
</head>
<body>
  <div style="max-width:780px;margin:0 auto;padding:28px 20px;">
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:24px;">
      <div>
        <h1>OCI Robot Cloud</h1>
        <div style="color:#94a3b8;font-size:13px;margin-top:4px;">
          Task Success Rate Forecaster &mdash; Apr&ndash;Sep 2026
        </div>
      </div>
      <div style="background:#1e293b;border-radius:8px;padding:8px 16px;
                  color:#38bdf8;font-size:12px;font-family:monospace;">PORT 8684</div>
    </div>

    <div style="display:flex;gap:12px;flex-wrap:wrap;margin-bottom:22px;">
      {cards}
    </div>

    <div class="section">
      <div class="section-title">SR Forecast Fan Chart (p10 / p50 / p90)</div>
      {fan}
      <div style="display:flex;gap:20px;margin-top:10px;flex-wrap:wrap;">
        <span style="color:#38bdf8;font-size:11px;">&#9644; p50 forecast</span>
        <span style="color:#38bdf8;font-size:11px;opacity:.5;">&#9644; p10/p90 band</span>
        <span style="color:#C74634;font-size:11px;">&#9474; DAgger milestones</span>
        <span style="color:#C74634;font-size:11px;">&#9679; Current SR=0.78</span>
      </div>
    </div>

    <div class="section">
      <div class="section-title">Contributing Factor Decomposition</div>
      {stacked}
      <div style="color:#64748b;font-size:11px;margin-top:8px;">
        Stacked contributions above 0.78 baseline: DAgger iterations, real demo ingestion,
        Cosmos augmentation, policy distillation, and data flywheel compounding.
      </div>
    </div>

    <div class="section">
      <div class="section-title">Historical + Forecast Scatter (CI widens with horizon)</div>
      {scatter}
    </div>

    <div style="text-align:center;color:#334155;font-size:11px;margin-top:28px;
                padding-top:16px;border-top:1px solid #1e293b;">
      Oracle Confidential | OCI Robot Cloud SR Forecaster | Port 8684
    </div>
  </div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# FastAPI Application
# ---------------------------------------------------------------------------

if HAS_FASTAPI:
    app = FastAPI(
        title="OCI Robot Cloud — Task SR Forecaster",
        description="Probabilistic success rate forecast with contributing factor decomposition",
        version="1.0.0",
    )

    @app.get("/", response_class=HTMLResponse)
    def root():
        return HTMLResponse(content=build_html())

    @app.get("/health")
    def health():
        return JSONResponse({"status": "ok", "service": "task_success_rate_forecaster", "port": 8684})

    @app.get("/forecast")
    def forecast():
        return JSONResponse({
            "months": MONTHS,
            "p10": FORECAST["p10"],
            "p50": FORECAST["p50"],
            "p90": FORECAST["p90"],
            "milestones": MILESTONES,
            "key_metrics": KEY_METRICS,
        })

    @app.get("/factors")
    def factors():
        return JSONResponse({"months": MONTHS, "factors": FACTORS})


# ---------------------------------------------------------------------------
# CLI fallback
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if HAS_FASTAPI:
        uvicorn.run("task_success_rate_forecaster:app", host="0.0.0.0", port=8684, reload=False)
    else:
        out_path = "/tmp/task_success_rate_forecaster.html"
        with open(out_path, "w") as f:
            f.write(build_html())
        print(f"[task_success_rate_forecaster] Saved static HTML to {out_path}")
        print(f"[task_success_rate_forecaster] Key metrics: {json.dumps(KEY_METRICS, indent=2)}")
