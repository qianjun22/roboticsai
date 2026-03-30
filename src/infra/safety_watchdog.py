"""Safety Watchdog Service — OCI Robot Cloud (port 8163)
Real-time safety monitor and watchdog for robot inference.
"""

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
except ImportError:
    FastAPI = None
    HTTPException = None
    HTMLResponse = None
    JSONResponse = None
    uvicorn = None

import math
from datetime import datetime, timezone
from typing import Optional

# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

SAFETY_CHECKS = [
    {
        "name": "joint_velocity_limit",
        "label": "Joint Velocity",
        "unit": "rad/s",
        "threshold": 2.5,
        "current_max": 1.84,
        "status": "OK",
        "violations_24h": 0,
        "detail": "",
    },
    {
        "name": "joint_torque_limit",
        "label": "Joint Torque",
        "unit": "Nm",
        "threshold": 87.0,
        "current_max": 62.1,
        "status": "OK",
        "violations_24h": 0,
        "detail": "",
    },
    {
        "name": "workspace_boundary",
        "label": "Workspace Boundary",
        "unit": "m radius",
        "threshold": 0.95,
        "current_max": 0.71,
        "status": "OK",
        "violations_24h": 1,
        "detail": "",
    },
    {
        "name": "gripper_force_limit",
        "label": "Gripper Force",
        "unit": "N",
        "threshold": 70.0,
        "current_max": 48.3,
        "status": "OK",
        "violations_24h": 0,
        "detail": "",
    },
    {
        "name": "collision_proximity",
        "label": "Collision Proximity",
        "unit": "mm",
        "threshold": 50.0,
        "current_max": 78.0,
        "status": "OK",
        "violations_24h": 0,
        "detail": "current_min=78mm (higher=safer)",
    },
    {
        "name": "inference_timeout",
        "label": "Inference Timeout",
        "unit": "ms",
        "threshold": 500.0,
        "current_max": 312.0,
        "status": "WARNING",
        "violations_24h": 3,
        "detail": "Spike at step 847",
    },
]

ESTOP_HISTORY = [
    {
        "ts": "2026-03-25T11:14Z",
        "cause": "workspace_boundary_exceeded",
        "recovery_time_s": 12,
    },
    {
        "ts": "2026-03-28T16:33Z",
        "cause": "workspace_boundary_exceeded",
        "recovery_time_s": 8,
    },
]

SAFETY_SCORE = 96

# ---------------------------------------------------------------------------
# SVG generators
# ---------------------------------------------------------------------------

def _arc_path(cx: float, cy: float, r: float, start_deg: float, end_deg: float) -> str:
    """Return SVG arc path string for a filled arc stroke (start/end in degrees, 0=top)."""
    def polar(deg: float):
        rad = math.radians(deg - 90)  # 0 deg = top
        return cx + r * math.cos(rad), cy + r * math.sin(rad)

    x1, y1 = polar(start_deg)
    x2, y2 = polar(end_deg)
    large = 1 if (end_deg - start_deg) > 180 else 0
    return f"M {x1:.2f} {y1:.2f} A {r} {r} 0 {large} 1 {x2:.2f} {y2:.2f}"


def _gauge_color(pct: float) -> str:
    """Return color based on percentage of threshold (for most checks higher=worse)."""
    if pct >= 0.80:
        return "#ef4444"  # red
    elif pct >= 0.60:
        return "#f59e0b"  # amber
    else:
        return "#22c55e"  # green


def _svg_gauges() -> str:
    """2x3 grid of arc gauges for the 6 safety checks."""
    W, H = 680, 200
    COLS, ROWS = 3, 2
    CELL_W = W // COLS
    CELL_H = H // ROWS
    R = 36

    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#0f172a;font-family:monospace">')

    for i, chk in enumerate(SAFETY_CHECKS):
        col = i % COLS
        row = i // COLS
        cx = CELL_W * col + CELL_W // 2
        cy = CELL_H * row + CELL_H // 2 - 5

        # collision_proximity: lower current = worse (invert ratio)
        if chk["name"] == "collision_proximity":
            pct = 1.0 - min(chk["current_max"] / (chk["threshold"] * 2), 1.0)
        else:
            pct = min(chk["current_max"] / chk["threshold"], 1.0)

        color = _gauge_color(pct)
        status_color = "#22c55e" if chk["status"] == "OK" else "#f59e0b"

        # Background arc (grey track) -135 to +135 degrees
        lines.append(f'<path d="{_arc_path(cx, cy, R, -135, 135)}" fill="none" stroke="#1e293b" stroke-width="8" stroke-linecap="round"/>')

        # Value arc
        end_angle = -135 + pct * 270
        if end_angle > -135:  # avoid zero-length path
            lines.append(f'<path d="{_arc_path(cx, cy, R, -135, end_angle)}" fill="none" stroke="{color}" stroke-width="8" stroke-linecap="round"/>')

        # Center text: pct
        pct_label = f"{pct*100:.0f}%"
        lines.append(f'<text x="{cx}" y="{cy+5}" fill="{color}" font-size="14" font-weight="bold" text-anchor="middle">{pct_label}</text>')

        # Label below gauge
        lines.append(f'<text x="{cx}" y="{cy+R+18}" fill="#94a3b8" font-size="10" text-anchor="middle">{chk["label"]}</text>')

        # Status dot top-right of cell
        dot_x = CELL_W * col + CELL_W - 14
        dot_y = CELL_H * row + 14
        lines.append(f'<circle cx="{dot_x}" cy="{dot_y}" r="5" fill="{status_color}"/>')
        lines.append(f'<text x="{dot_x - 8}" y="{dot_y + 4}" fill="{status_color}" font-size="9" text-anchor="end">{chk["status"]}</text>')

    lines.append('</svg>')
    return "\n".join(lines)


def _svg_estop_timeline() -> str:
    """7-day timeline with e-stop markers."""
    W, H = 680, 120
    PAD_L, PAD_R = 60, 30
    AXIS_Y = 70
    TOTAL_DAYS = 7

    # Day 0 = 2026-03-23, Day 7 = 2026-03-30
    ORIGIN_DATE = "2026-03-23"

    def ts_to_x(ts: str) -> float:
        # ts format: "2026-03-25T11:14Z"
        date_part = ts.split("T")[0]
        from datetime import date
        parts = date_part.split("-")
        d = date(int(parts[0]), int(parts[1]), int(parts[2]))
        oparts = ORIGIN_DATE.split("-")
        origin = date(int(oparts[0]), int(oparts[1]), int(oparts[2]))
        days = (d - origin).days
        return PAD_L + (days / TOTAL_DAYS) * (W - PAD_L - PAD_R)

    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#0f172a;font-family:monospace">')

    # Title
    lines.append(f'<text x="{PAD_L}" y="18" fill="#64748b" font-size="11">Emergency Stop Events — Last 7 Days</text>')

    # Day ticks
    day_labels = ["Mar 23", "Mar 24", "Mar 25", "Mar 26", "Mar 27", "Mar 28", "Mar 29", "Mar 30"]
    for i, label in enumerate(day_labels):
        x = PAD_L + (i / TOTAL_DAYS) * (W - PAD_L - PAD_R)
        lines.append(f'<line x1="{x:.1f}" y1="{AXIS_Y}" x2="{x:.1f}" y2="{AXIS_Y+6}" stroke="#334155" stroke-width="1"/>')
        lines.append(f'<text x="{x:.1f}" y="{AXIS_Y+18}" fill="#475569" font-size="9" text-anchor="middle">{label}</text>')

    # Axis
    lines.append(f'<line x1="{PAD_L}" y1="{AXIS_Y}" x2="{W-PAD_R}" y2="{AXIS_Y}" stroke="#334155" stroke-width="2"/>')

    # E-stop markers
    for estop in ESTOP_HISTORY:
        x = ts_to_x(estop["ts"])
        # Red vertical spike
        lines.append(f'<line x1="{x:.1f}" y1="{AXIS_Y-30}" x2="{x:.1f}" y2="{AXIS_Y}" stroke="#C74634" stroke-width="3"/>')
        lines.append(f'<circle cx="{x:.1f}" cy="{AXIS_Y-30}" r="5" fill="#C74634"/>')
        # Recovery time label
        lines.append(f'<text x="{x:.1f}" y="{AXIS_Y-35}" fill="#fbbf24" font-size="9" text-anchor="middle">+{estop["recovery_time_s"]}s</text>')
        # Date label
        date_label = estop["ts"].split("T")[0]
        lines.append(f'<text x="{x:.1f}" y="{AXIS_Y-44}" fill="#94a3b8" font-size="8" text-anchor="middle">{date_label}</text>')

    lines.append('</svg>')
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def _html_dashboard() -> str:
    svg_gauges = _svg_gauges()
    svg_estop = _svg_estop_timeline()

    # Build checks table rows
    rows = []
    for chk in SAFETY_CHECKS:
        pct = min(chk["current_max"] / chk["threshold"] * 100, 100)
        bar_color = "#22c55e" if pct < 60 else ("#f59e0b" if pct < 80 else "#ef4444")
        status_style = "color:#22c55e" if chk["status"] == "OK" else "color:#f59e0b;font-weight:bold"
        v24 = chk["violations_24h"]
        v_style = "color:#ef4444;font-weight:bold" if v24 > 0 else "color:#64748b"
        detail = chk["detail"] or "—"
        rows.append(f'''
        <tr style="border-bottom:1px solid #1e293b">
          <td style="color:#e2e8f0">{chk["label"]}</td>
          <td style="color:#94a3b8">{chk["threshold"]} {chk["unit"]}</td>
          <td style="color:#38bdf8">{chk["current_max"]} {chk["unit"]}</td>
          <td>
            <div style="background:#1e293b;border-radius:4px;height:8px;width:100px">
              <div style="background:{bar_color};height:8px;border-radius:4px;width:{min(pct,100):.0f}px"></div>
            </div>
            <span style="color:#64748b;font-size:10px">{pct:.0f}%</span>
          </td>
          <td style="{status_style}">{chk["status"]}</td>
          <td style="{v_style}">{v24}</td>
          <td style="color:#64748b;font-size:12px">{detail}</td>
        </tr>''')

    rows_html = "".join(rows)

    # E-stop table
    estop_rows = "".join(
        f'<tr style="border-bottom:1px solid #1e293b"><td style="color:#f87171">{e["ts"]}</td><td style="color:#fbbf24">{e["cause"]}</td><td style="color:#38bdf8">{e["recovery_time_s"]}s</td></tr>'
        for e in ESTOP_HISTORY
    )

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Safety Watchdog — OCI Robot Cloud</title>
  <style>
    body {{ background:#0f172a; color:#e2e8f0; font-family:monospace; margin:0; padding:24px }}
    h1 {{ color:#C74634; margin-bottom:4px }}
    .subtitle {{ color:#64748b; font-size:13px; margin-bottom:24px }}
    .card {{ background:#0f172a; border:1px solid #1e293b; border-radius:8px; padding:20px; margin-bottom:20px }}
    h2 {{ color:#38bdf8; font-size:15px; margin:0 0 14px }}
    table {{ width:100%; border-collapse:collapse }}
    th {{ color:#64748b; font-size:12px; text-align:left; padding:6px 10px; border-bottom:1px solid #1e293b }}
    td {{ padding:8px 10px; font-size:13px; vertical-align:middle }}
    tr:hover {{ background:#1e293b30 }}
    .score {{ font-size:48px; font-weight:bold; color:#22c55e }}
    .score-label {{ color:#64748b; font-size:13px }}
  </style>
</head>
<body>
  <h1>Safety Watchdog Service</h1>
  <div class="subtitle">Real-Time Robot Safety Monitor &mdash; OCI Robot Cloud &mdash; port 8163</div>

  <div class="card" style="display:flex;align-items:center;gap:40px">
    <div>
      <div class="score">{SAFETY_SCORE}<span style="font-size:20px;color:#64748b">/100</span></div>
      <div class="score-label">Safety Score</div>
    </div>
    <div style="flex:1">
      <div style="color:#f59e0b;font-size:13px">&#9888; 1 WARNING: inference_timeout — spike at step 847 (3 violations/24h)</div>
      <div style="color:#64748b;font-size:12px;margin-top:4px">All other checks: OK &nbsp;|&nbsp; E-stops this week: {len(ESTOP_HISTORY)} (workspace boundary)</div>
    </div>
  </div>

  <div class="card">
    <h2>Safety Check Gauges (% of threshold)</h2>
    {svg_gauges}
  </div>

  <div class="card">
    <h2>Safety Checks Detail</h2>
    <table>
      <thead>
        <tr><th>Check</th><th>Threshold</th><th>Current</th><th>Load</th><th>Status</th><th>Violations/24h</th><th>Detail</th></tr>
      </thead>
      <tbody>{rows_html}</tbody>
    </table>
  </div>

  <div class="card">
    <h2>Emergency Stop Timeline</h2>
    {svg_estop}
    <table style="margin-top:12px">
      <thead><tr><th>Timestamp</th><th>Cause</th><th>Recovery Time</th></tr></thead>
      <tbody>{estop_rows}</tbody>
    </table>
  </div>

  <div style="color:#334155;font-size:11px;margin-top:8px">API: GET /checks &nbsp;|&nbsp; GET /violations &nbsp;|&nbsp; GET /estops &nbsp;|&nbsp; POST /emergency-stop</div>
</body>
</html>'''


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

if FastAPI is not None:
    app = FastAPI(title="Safety Watchdog Service", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return _html_dashboard()

    @app.get("/checks")
    def list_checks():
        return SAFETY_CHECKS

    @app.get("/violations")
    def get_violations(severity: Optional[str] = None):
        """Return checks with violations. Filter by severity: warning, error."""
        results = [c for c in SAFETY_CHECKS if c["violations_24h"] > 0 or c["status"] != "OK"]
        if severity == "warning":
            results = [c for c in results if c["status"] == "WARNING"]
        elif severity == "error":
            results = [c for c in results if c["status"] == "ERROR"]
        return results

    @app.get("/estops")
    def get_estops():
        return ESTOP_HISTORY

    @app.post("/emergency-stop")
    def trigger_estop(cause: str = "manual_trigger"):
        """Trigger an emergency stop."""
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
        record = {"ts": ts, "cause": cause, "recovery_time_s": None, "status": "active"}
        ESTOP_HISTORY.append(record)
        return {"status": "emergency_stop_triggered", "ts": ts, "cause": cause}

else:
    class app:  # type: ignore
        pass


if __name__ == "__main__":
    if uvicorn is not None:
        uvicorn.run("safety_watchdog:app", host="0.0.0.0", port=8163, reload=False)
    else:
        print("uvicorn not installed — cannot start server")
