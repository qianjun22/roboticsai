"""Joint Torque Analyzer — OCI Robot Cloud  (port 8202)

Analyzes Franka 7-DOF torque profiles for the cube_lift task (847-step episode).
Detects safety violations and generates SVG charts.
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
except ImportError as e:
    raise SystemExit(f"Missing dependency: {e}  —  pip install fastapi uvicorn") from e

import math
import random

app = FastAPI(
    title="Joint Torque Analyzer",
    description="Franka 7-DOF torque safety analysis — OCI Robot Cloud",
    version="1.0.0",
)

# ── Static joint data ──────────────────────────────────────────────────────────
JOINTS = [
    {"id": "joint_1", "max_torque": 18.4, "limit": 87.0,  "avg_torque": 12.1, "peak_utilization": 0.21, "smoothness": 0.94},
    {"id": "joint_2", "max_torque": 47.2, "limit": 87.0,  "avg_torque": 31.8, "peak_utilization": 0.54, "smoothness": 0.89},
    {"id": "joint_3", "max_torque": 29.1, "limit": 87.0,  "avg_torque": 19.4, "peak_utilization": 0.33, "smoothness": 0.91},
    {"id": "joint_4", "max_torque": 71.3, "limit": 87.0,  "avg_torque": 52.7, "peak_utilization": 0.82, "smoothness": 0.87},
    {"id": "joint_5", "max_torque": 12.8, "limit": 12.0,  "avg_torque":  8.4, "peak_utilization": 1.07, "smoothness": 0.76},
    {"id": "joint_6", "max_torque":  8.7, "limit": 12.0,  "avg_torque":  5.9, "peak_utilization": 0.73, "smoothness": 0.93},
    {"id": "joint_7", "max_torque":  4.2, "limit": 12.0,  "avg_torque":  2.8, "peak_utilization": 0.35, "smoothness": 0.91},
]

EPISODE_STEPS = 847
GRASP_STEP   = 620
SAFETY_NOTE  = (
    "joint_5 torque exceeded by 6.7% — reduce action magnitude during grasp phase; "
    "consider joint_5 torque penalty in reward shaping v3.1"
)

# ── Chart helpers ──────────────────────────────────────────────────────────────

def _bar_chart_svg() -> str:
    """Torque utilization bar chart — 680×220 px."""
    W, H     = 680, 220
    pad_l    = 52
    pad_r    = 20
    pad_t    = 24
    pad_b    = 40
    n        = len(JOINTS)
    chart_w  = W - pad_l - pad_r
    chart_h  = H - pad_t - pad_b
    bar_w    = (chart_w / n) * 0.55
    bar_gap  = chart_w / n
    max_val  = 1.20   # y-axis top

    def y_of(v: float) -> float:
        return pad_t + chart_h * (1.0 - v / max_val)

    bars = []
    for i, j in enumerate(JOINTS):
        cx   = pad_l + bar_gap * i + bar_gap / 2
        bx   = cx - bar_w / 2
        util = j["peak_utilization"]
        by   = y_of(util)
        bh   = y_of(0) - by
        if util > 1.0:
            color = "#ef4444"          # red — exceeds limit
        elif util >= 0.80:
            color = "#f59e0b"          # amber — watch
        else:
            color = "#38bdf8"          # sky blue — normal

        label = j["id"].replace("joint_", "J")
        val_y = by - 5
        bars.append(
            f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bar_w:.1f}" height="{bh:.1f}" fill="{color}" rx="3"/>'
            f'<text x="{cx:.1f}" y="{val_y:.1f}" text-anchor="middle" fill="{color}" font-size="11" font-family="monospace">{util:.2f}</text>'
            f'<text x="{cx:.1f}" y="{H - pad_b + 14:.1f}" text-anchor="middle" fill="#94a3b8" font-size="11" font-family="monospace">{label}</text>'
        )

    # 100% red limit line
    y100 = y_of(1.0)
    limit_line = (
        f'<line x1="{pad_l}" y1="{y100:.1f}" x2="{W - pad_r}" y2="{y100:.1f}" '
        f'stroke="#ef4444" stroke-width="1.5" stroke-dasharray="6 3"/>'
        f'<text x="{W - pad_r - 2}" y="{y100 - 4:.1f}" text-anchor="end" fill="#ef4444" font-size="10" font-family="monospace">100% limit</text>'
    )

    # y-axis ticks
    ticks = ""
    for v in [0.25, 0.50, 0.75, 1.00]:
        ty = y_of(v)
        ticks += (
            f'<line x1="{pad_l - 4}" y1="{ty:.1f}" x2="{pad_l}" y2="{ty:.1f}" stroke="#475569" stroke-width="1"/>'
            f'<text x="{pad_l - 7}" y="{ty + 4:.1f}" text-anchor="end" fill="#64748b" font-size="10" font-family="monospace">{int(v*100)}%</text>'
        )

    # Safety annotation for joint_5
    j5_cx = pad_l + bar_gap * 4 + bar_gap / 2
    j5_by = y_of(JOINTS[4]["peak_utilization"])
    annotation = (
        f'<text x="{j5_cx:.1f}" y="{j5_by - 16:.1f}" text-anchor="middle" fill="#ef4444" font-size="10" font-family="monospace">⚠ EXCEED</text>'
    )

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'style="background:#1e293b;border-radius:8px;">'
        f'<text x="{W//2}" y="15" text-anchor="middle" fill="#e2e8f0" font-size="12" font-family="monospace" font-weight="bold">'
        f'Peak Torque Utilization — cube_lift (847 steps)</text>'
        + ticks + limit_line + "".join(bars) + annotation +
        f'<line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t + chart_h}" stroke="#475569" stroke-width="1"/>'
        f'<line x1="{pad_l}" y1="{pad_t + chart_h}" x2="{W - pad_r}" y2="{pad_t + chart_h}" stroke="#475569" stroke-width="1"/>'
        f'</svg>'
    )
    return svg


def _timeseries_svg() -> str:
    """7-joint torque time series — 680×240 px."""
    W, H   = 680, 240
    pad_l  = 52
    pad_r  = 80
    pad_t  = 24
    pad_b  = 36
    chart_w = W - pad_l - pad_r
    chart_h = H - pad_t - pad_b
    steps   = EPISODE_STEPS
    max_nm  = 90.0
    samples = 120   # downsample for compact SVG

    colors = ["#38bdf8","#818cf8","#34d399","#f59e0b","#ef4444","#fb923c","#a78bfa"]

    def sx(step: int) -> float:
        return pad_l + chart_w * step / steps

    def sy(nm: float) -> float:
        return pad_t + chart_h * (1.0 - nm / max_nm)

    lines_svg = ""
    legend_svg = ""
    rng = random.Random(42)

    for ji, j in enumerate(JOINTS):
        avg     = j["avg_torque"]
        max_t   = j["max_torque"]
        lim     = j["limit"]
        smooth  = j["smoothness"]
        pts     = []
        val     = avg
        for s in range(samples):
            step = int(s * steps / samples)
            # Grasp spike around step 620
            spike = 0.0
            if abs(step - GRASP_STEP) < (steps / samples) * 3:
                spike = (max_t - avg) * 0.85
            noise  = rng.gauss(0, avg * (1 - smooth) * 0.4)
            target = avg + spike + noise
            val    = val * 0.75 + target * 0.25
            val    = max(0.0, min(val, max_t * 1.05))
            pts.append((sx(step), sy(val)))

        polyline = " ".join(f"{px:.1f},{py:.1f}" for px, py in pts)
        c = colors[ji]
        lines_svg += f'<polyline points="{polyline}" fill="none" stroke="{c}" stroke-width="1.5" opacity="0.9"/>'

        # Legend
        lx = W - pad_r + 8
        ly = pad_t + 14 + ji * 18
        legend_svg += (
            f'<rect x="{lx}" y="{ly - 8}" width="12" height="8" fill="{c}" rx="1"/>'
            f'<text x="{lx + 15}" y="{ly}" fill="{c}" font-size="10" font-family="monospace">{j["id"].replace("joint_","J")}</text>'
        )

    # 12Nm dashed limit for joint_5
    y12 = sy(12.0)
    limit_line = (
        f'<line x1="{pad_l}" y1="{y12:.1f}" x2="{W - pad_r}" y2="{y12:.1f}" '
        f'stroke="#ef4444" stroke-width="1" stroke-dasharray="5 3" opacity="0.6"/>'
        f'<text x="{pad_l + 4}" y="{y12 - 4:.1f}" fill="#ef4444" font-size="9" font-family="monospace">12 Nm limit (J5/J6/J7)</text>'
    )

    # Grasp event marker
    gx = sx(GRASP_STEP)
    grasp = (
        f'<line x1="{gx:.1f}" y1="{pad_t}" x2="{gx:.1f}" y2="{pad_t + chart_h}" '
        f'stroke="#fbbf24" stroke-width="1" stroke-dasharray="4 2" opacity="0.7"/>'
        f'<text x="{gx + 3:.1f}" y="{pad_t + 10:.1f}" fill="#fbbf24" font-size="9" font-family="monospace">grasp</text>'
    )

    # y-axis
    ticks = ""
    for nm in [0, 20, 40, 60, 80]:
        ty = sy(nm)
        ticks += (
            f'<line x1="{pad_l - 4}" y1="{ty:.1f}" x2="{pad_l}" y2="{ty:.1f}" stroke="#475569"/>'
            f'<text x="{pad_l - 7}" y="{ty + 4:.1f}" text-anchor="end" fill="#64748b" font-size="10" font-family="monospace">{nm}</text>'
        )

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'style="background:#1e293b;border-radius:8px;">'
        f'<text x="{(pad_l + W - pad_r)//2}" y="15" text-anchor="middle" fill="#e2e8f0" font-size="12" font-family="monospace" font-weight="bold">'
        f'Torque Time Series [Nm] — 847-step Episode</text>'
        + ticks
        + f'<line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t + chart_h}" stroke="#475569"/>'
        + f'<line x1="{pad_l}" y1="{pad_t + chart_h}" x2="{W - pad_r}" y2="{pad_t + chart_h}" stroke="#475569"/>'
        + limit_line + grasp + lines_svg + legend_svg
        + f'<text x="{pad_l}" y="{H - 5}" fill="#64748b" font-size="9" font-family="monospace">step</text>'
        + f'<text x="{pad_l + chart_w}" y="{H - 5}" text-anchor="end" fill="#64748b" font-size="9" font-family="monospace">{steps}</text>'
        + f'</svg>'
    )
    return svg


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.get("/joints")
def get_joints():
    """Return all joint torque data as JSON."""
    return JSONResponse({
        "episode": "cube_lift",
        "steps": EPISODE_STEPS,
        "joints": JOINTS,
    })


@app.get("/violations")
def get_violations():
    """Return joints that exceed or approach torque limits."""
    violations = []
    warnings   = []
    for j in JOINTS:
        util = j["peak_utilization"]
        if util > 1.0:
            violations.append({
                **j,
                "severity": "CRITICAL",
                "overage_pct": round((util - 1.0) * 100, 1),
                "recommendation": SAFETY_NOTE,
            })
        elif util >= 0.80:
            warnings.append({
                **j,
                "severity": "WARNING",
                "overage_pct": 0.0,
                "recommendation": "Monitor closely; near torque limit.",
            })
    return JSONResponse({
        "violations": violations,
        "warnings": warnings,
        "safe_count": len(JOINTS) - len(violations) - len(warnings),
    })


@app.get("/timeseries")
def get_timeseries():
    """Return sampled torque time series for each joint."""
    rng     = random.Random(42)
    samples = 120
    result  = {}
    for j in JOINTS:
        avg    = j["avg_torque"]
        max_t  = j["max_torque"]
        smooth = j["smoothness"]
        series = []
        val    = avg
        for s in range(samples):
            step  = int(s * EPISODE_STEPS / samples)
            spike = 0.0
            if abs(step - GRASP_STEP) < (EPISODE_STEPS / samples) * 3:
                spike = (max_t - avg) * 0.85
            noise  = rng.gauss(0, avg * (1 - smooth) * 0.4)
            target = avg + spike + noise
            val    = val * 0.75 + target * 0.25
            val    = max(0.0, min(val, max_t * 1.05))
            series.append({"step": step, "torque_nm": round(val, 3)})
        result[j["id"]] = series
    return JSONResponse({"episode": "cube_lift", "grasp_step": GRASP_STEP, "series": result})


@app.get("/", response_class=HTMLResponse)
def dashboard():
    bar_svg = _bar_chart_svg()
    ts_svg  = _timeseries_svg()

    violation_rows = ""
    for j in JOINTS:
        util   = j["peak_utilization"]
        status = "OK"
        color  = "#38bdf8"
        if util > 1.0:
            status = "EXCEED"
            color  = "#ef4444"
        elif util >= 0.80:
            status = "WATCH"
            color  = "#f59e0b"
        violation_rows += (
            f'<tr>'
            f'<td style="padding:6px 12px;font-family:monospace;color:#e2e8f0">{j["id"]}</td>'
            f'<td style="padding:6px 12px;text-align:right;color:#94a3b8">{j["max_torque"]}</td>'
            f'<td style="padding:6px 12px;text-align:right;color:#94a3b8">{j["limit"]}</td>'
            f'<td style="padding:6px 12px;text-align:right;color:#94a3b8">{j["avg_torque"]}</td>'
            f'<td style="padding:6px 12px;text-align:right;color:{color};font-weight:bold">{util:.2f}</td>'
            f'<td style="padding:6px 12px;text-align:right;color:#94a3b8">{j["smoothness"]}</td>'
            f'<td style="padding:6px 12px"><span style="background:{color}22;color:{color};padding:2px 8px;border-radius:4px;font-size:11px;font-family:monospace">{status}</span></td>'
            f'</tr>'
        )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Joint Torque Analyzer — OCI Robot Cloud</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #e2e8f0; font-family: system-ui, sans-serif; }}
    .header {{ background: #1e293b; border-bottom: 2px solid #C74634; padding: 16px 32px; display: flex; align-items: center; gap: 16px; }}
    .logo {{ color: #C74634; font-size: 22px; font-weight: 800; letter-spacing: -0.5px; }}
    .subtitle {{ color: #64748b; font-size: 13px; }}
    .badge {{ background: #ef444422; color: #ef4444; border: 1px solid #ef4444; padding: 3px 10px; border-radius: 4px; font-size: 11px; font-family: monospace; }}
    .container {{ max-width: 900px; margin: 0 auto; padding: 28px 24px; }}
    .alert {{ background: #ef444415; border: 1px solid #ef4444; border-radius: 8px; padding: 14px 18px; margin-bottom: 24px; font-size: 13px; color: #fca5a5; }}
    .alert strong {{ color: #ef4444; }}
    .card {{ background: #1e293b; border-radius: 10px; padding: 20px; margin-bottom: 24px; border: 1px solid #334155; }}
    .card-title {{ color: #38bdf8; font-size: 13px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 16px; }}
    table {{ width: 100%; border-collapse: collapse; }}
    thead th {{ color: #64748b; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; padding: 6px 12px; text-align: right; border-bottom: 1px solid #334155; }}
    thead th:first-child {{ text-align: left; }}
    tbody tr:hover {{ background: #ffffff08; }}
    .note {{ background: #0ea5e915; border-left: 3px solid #38bdf8; padding: 12px 16px; border-radius: 0 6px 6px 0; font-size: 13px; color: #7dd3fc; margin-top: 8px; }}
    .port {{ color: #64748b; font-size: 12px; font-family: monospace; }}
  </style>
</head>
<body>
  <div class="header">
    <div>
      <div class="logo">OCI Robot Cloud</div>
      <div class="subtitle">Joint Torque Analyzer &nbsp;&#183;&nbsp; Franka 7-DOF &nbsp;&#183;&nbsp; <span class="port">:8202</span></div>
    </div>
    <div style="margin-left:auto"><span class="badge">&#9888; 1 VIOLATION</span></div>
  </div>
  <div class="container">
    <div class="alert">
      <strong>&#9888; Safety Alert:</strong> {SAFETY_NOTE}
    </div>

    <div class="card">
      <div class="card-title">Peak Torque Utilization</div>
      {bar_svg}
    </div>

    <div class="card">
      <div class="card-title">Torque Time Series</div>
      {ts_svg}
    </div>

    <div class="card">
      <div class="card-title">Joint Summary Table</div>
      <table>
        <thead><tr>
          <th style="text-align:left">Joint</th>
          <th>Max Torque (Nm)</th>
          <th>Limit (Nm)</th>
          <th>Avg Torque (Nm)</th>
          <th>Peak Util</th>
          <th>Smoothness</th>
          <th>Status</th>
        </tr></thead>
        <tbody>{violation_rows}</tbody>
      </table>
      <div class="note">&#128161; Recommendation: {SAFETY_NOTE}</div>
    </div>

    <div style="color:#475569;font-size:11px;text-align:center;margin-top:8px">
      Episode: cube_lift &nbsp;|&nbsp; Steps: {EPISODE_STEPS} &nbsp;|&nbsp; Grasp event @ step {GRASP_STEP}
      &nbsp;|&nbsp; API: <code>/joints</code> &nbsp;<code>/violations</code> &nbsp;<code>/timeseries</code>
    </div>
  </div>
</body>
</html>"""
    return HTMLResponse(html)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8202)
