"""Robot Sensor Calibration Monitor — OCI Robot Cloud — port 8159"""

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
except ImportError:
    FastAPI = None

import math
import random

# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

SENSORS = [
    {
        "id": "wrist_camera_rgb",
        "label": "Wrist Camera (RGB)",
        "last_calibrated": "2026-03-28",
        "drift": 1.2,
        "threshold": 5.0,
        "unit": "px",
        "status": "OK",
        "calibration_type": "intrinsic+extrinsic",
    },
    {
        "id": "wrist_camera_depth",
        "label": "Wrist Camera (Depth)",
        "last_calibrated": "2026-03-28",
        "drift": 3.4,
        "threshold": 8.0,
        "unit": "mm",
        "status": "OK",
        "calibration_type": "depth_scale",
    },
    {
        "id": "joint_encoders",
        "label": "Joint Encoders",
        "last_calibrated": "2026-03-30",
        "drift": 0.12,
        "threshold": 0.5,
        "unit": "deg",
        "status": "OK",
        "calibration_type": "zero_offset",
    },
    {
        "id": "force_torque_sensor",
        "label": "Force/Torque Sensor",
        "last_calibrated": "2026-03-25",
        "drift": 0.8,
        "threshold": 2.0,
        "unit": "N",
        "status": "WARNING",
        "calibration_type": "bias_reset",
        "note": "Approaching threshold — schedule recalibration in 3 days",
    },
    {
        "id": "gripper_position",
        "label": "Gripper Position",
        "last_calibrated": "2026-03-29",
        "drift": 0.4,
        "threshold": 1.0,
        "unit": "mm",
        "status": "OK",
        "calibration_type": "open_close_range",
    },
]

SENSORS_BY_ID = {s["id"]: s for s in SENSORS}

# Calibration type → color
CAL_TYPE_COLOR = {
    "intrinsic+extrinsic": "#38bdf8",
    "depth_scale":          "#818cf8",
    "zero_offset":          "#4ade80",
    "bias_reset":           "#fbbf24",
    "open_close_range":     "#f472b6",
}

# Deterministic pseudo-history: 5 calibration events per sensor in Feb-Mar 2026
# Represented as day-of-year offsets from Feb 1 (day 32)
_SEED_OFFSETS = [
    [0, 8, 18, 30, 42],   # wrist_camera_rgb
    [1, 10, 20, 32, 42],  # wrist_camera_depth
    [2, 11, 21, 34, 58],  # joint_encoders  (last = Mar 30)
    [4, 13, 23, 36, 53],  # force_torque_sensor (last = Mar 25)
    [3, 12, 22, 35, 57],  # gripper_position (last = Mar 29)
]
_LABELS = ["Feb 1", "Feb 9", "Feb 19", "Mar 3", "Mar 14"]


def drift_pct(sensor: dict) -> float:
    return sensor["drift"] / sensor["threshold"] * 100.0


def bar_color(pct: float) -> str:
    if pct >= 80:
        return "#f87171"  # red
    if pct >= 50:
        return "#fbbf24"  # amber
    return "#4ade80"       # green

# ---------------------------------------------------------------------------
# SVG: Drift bar chart
# ---------------------------------------------------------------------------

def drift_bar_svg() -> str:
    W, H = 680, 200
    pad_l, pad_r, pad_t, pad_b = 170, 30, 20, 40
    chart_w = W - pad_l - pad_r
    chart_h = H - pad_t - pad_b
    bar_gap = 8
    n = len(SENSORS)
    bar_h = (chart_h - bar_gap * (n + 1)) / n

    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#0f172a;font-family:sans-serif">')

    # grid lines at 0, 50, 80, 100%
    for pct_mark in [0, 50, 80, 100]:
        x = pad_l + chart_w * pct_mark / 100
        clr = "#C74634" if pct_mark == 100 else "#1e293b"
        lines.append(f'<line x1="{x:.1f}" y1="{pad_t}" x2="{x:.1f}" y2="{H-pad_b}" stroke="{clr}" stroke-width="{1 if pct_mark<100 else 2}" stroke-dasharray="{"4,3" if pct_mark not in (0,100) else "none"}"/>')
        lines.append(f'<text x="{x:.1f}" y="{H-pad_b+14}" fill="#64748b" font-size="10" text-anchor="middle">{pct_mark}%</text>')

    for i, sensor in enumerate(SENSORS):
        y = pad_t + bar_gap * (i + 1) + bar_h * i
        pct = drift_pct(sensor)
        bar_w = chart_w * min(pct, 100) / 100
        clr = bar_color(pct)
        # label
        lines.append(f'<text x="{pad_l-8}" y="{y + bar_h/2 + 4:.1f}" fill="#94a3b8" font-size="11" text-anchor="end">{sensor["label"]}</text>')
        # bar bg
        lines.append(f'<rect x="{pad_l}" y="{y:.1f}" width="{chart_w}" height="{bar_h:.1f}" rx="3" fill="#1e293b"/>')
        # bar fill
        lines.append(f'<rect x="{pad_l}" y="{y:.1f}" width="{bar_w:.1f}" height="{bar_h:.1f}" rx="3" fill="{clr}"/>')
        # value label
        lines.append(f'<text x="{pad_l + bar_w + 6:.1f}" y="{y + bar_h/2 + 4:.1f}" fill="{clr}" font-size="10">{pct:.0f}% ({sensor["drift"]}{sensor["unit"]})</text>')

    lines.append(f'<text x="{pad_l + chart_w//2}" y="{H-2}" fill="#475569" font-size="10" text-anchor="middle">Drift as % of threshold — threshold line at 100%</text>')
    lines.append('</svg>')
    return "\n".join(lines)

# ---------------------------------------------------------------------------
# SVG: Calibration history timeline
# ---------------------------------------------------------------------------

def history_svg() -> str:
    W, H = 680, 160
    pad_l, pad_r, pad_t, pad_b = 170, 30, 20, 30
    chart_w = W - pad_l - pad_r
    row_h = (H - pad_t - pad_b) / len(SENSORS)
    n_events = 5
    # x positions for 5 events spread evenly
    xs = [pad_l + chart_w * i / (n_events - 1) for i in range(n_events)]
    # x-axis date labels
    x_labels = ["Feb 1", "Feb 9", "Feb 19", "Mar 3", "Mar 30"]

    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#0f172a;font-family:sans-serif">')

    # x-axis labels
    for xi, lbl in zip(xs, x_labels):
        lines.append(f'<text x="{xi:.1f}" y="{H-pad_b+14}" fill="#64748b" font-size="10" text-anchor="middle">{lbl}</text>')
        lines.append(f'<line x1="{xi:.1f}" y1="{pad_t}" x2="{xi:.1f}" y2="{H-pad_b}" stroke="#1e293b" stroke-width="1"/>')

    for i, sensor in enumerate(SENSORS):
        cy = pad_t + row_h * i + row_h / 2
        clr = CAL_TYPE_COLOR.get(sensor["calibration_type"], "#94a3b8")
        # row label
        lines.append(f'<text x="{pad_l-8}" y="{cy+4:.1f}" fill="#94a3b8" font-size="11" text-anchor="end">{sensor["label"]}</text>')
        # baseline
        lines.append(f'<line x1="{pad_l}" y1="{cy:.1f}" x2="{pad_l+chart_w}" y2="{cy:.1f}" stroke="#1e293b" stroke-width="1"/>')
        # dots
        for xi in xs:
            lines.append(f'<circle cx="{xi:.1f}" cy="{cy:.1f}" r="5" fill="{clr}" stroke="#0f172a" stroke-width="1.5"/>')

    # legend
    lx = pad_l
    lines.append(f'<text x="{lx}" y="{H-2}" fill="#475569" font-size="10">Color by calibration type: </text>')
    offset = lx + 160
    for cal_type, clr in CAL_TYPE_COLOR.items():
        lines.append(f'<circle cx="{offset}" cy="{H-6}" r="4" fill="{clr}"/>')
        lines.append(f'<text x="{offset+7}" y="{H-2}" fill="{clr}" font-size="9">{cal_type}</text>')
        offset += len(cal_type) * 7 + 20

    lines.append('</svg>')
    return "\n".join(lines)

# ---------------------------------------------------------------------------
# SVG: 30-day calibration forecast (bar chart by week)
# ---------------------------------------------------------------------------

def forecast_svg() -> str:
    """Predicted recalibration events by week for next 4 weeks."""
    # Simple deterministic forecast: sensors close to threshold recal sooner
    # weeks labelled W1..W4 from 2026-03-30
    week_labels = ["Apr 1-7", "Apr 8-14", "Apr 15-21", "Apr 22-28"]
    week_counts = [2, 1, 2, 1]  # predicted recal events per week

    W, H = 680, 140
    pad_l, pad_r, pad_t, pad_b = 60, 30, 20, 40
    chart_w = W - pad_l - pad_r
    chart_h = H - pad_t - pad_b
    n = len(week_labels)
    group_w = chart_w / n
    bar_w = group_w * 0.5
    max_count = max(week_counts) + 1

    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#0f172a;font-family:sans-serif">')
    # y grid
    for cnt in range(0, max_count + 1):
        y = pad_t + chart_h - chart_h * cnt / max_count
        lines.append(f'<line x1="{pad_l}" y1="{y:.1f}" x2="{W-pad_r}" y2="{y:.1f}" stroke="#1e293b" stroke-width="1"/>')
        lines.append(f'<text x="{pad_l-6}" y="{y+4:.1f}" fill="#64748b" font-size="10" text-anchor="end">{cnt}</text>')

    for i, (lbl, cnt) in enumerate(zip(week_labels, week_counts)):
        cx = pad_l + group_w * i + group_w / 2
        bx = cx - bar_w / 2
        bh = chart_h * cnt / max_count
        by = pad_t + chart_h - bh
        clr = "#C74634" if cnt >= 2 else "#38bdf8"
        lines.append(f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bar_w:.1f}" height="{bh:.1f}" rx="3" fill="{clr}"/>')
        lines.append(f'<text x="{cx:.1f}" y="{by-5:.1f}" fill="{clr}" font-size="11" text-anchor="middle">{cnt}</text>')
        lines.append(f'<text x="{cx:.1f}" y="{H-pad_b+14}" fill="#94a3b8" font-size="10" text-anchor="middle">{lbl}</text>')

    lines.append(f'<text x="{pad_l}" y="{H-1}" fill="#475569" font-size="10">Predicted recalibration events (30-day forecast from 2026-03-30)</text>')
    lines.append('</svg>')
    return "\n".join(lines)

# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def build_html() -> str:
    dsvg = drift_bar_svg()
    hsvg = history_svg()
    fsvg = forecast_svg()

    sensor_cards = ""
    for s in SENSORS:
        pct = drift_pct(s)
        clr = bar_color(pct)
        status_bg = "#78350f" if s["status"] == "WARNING" else "#14532d"
        status_fg = "#fbbf24" if s["status"] == "WARNING" else "#4ade80"
        note_html = f'<p style="color:#fbbf24;font-size:11px;margin:4px 0 0">{s.get("note","")}</p>' if s.get("note") else ""
        sensor_cards += f"""
        <div style="background:#1e293b;border-radius:8px;padding:12px;min-width:180px;flex:1">
          <div style="font-size:12px;color:#64748b">{s['label']}</div>
          <div style="font-size:22px;font-weight:bold;color:{clr}">{pct:.0f}%</div>
          <div style="font-size:11px;color:#94a3b8">drift: {s['drift']}{s['unit']} / {s['threshold']}{s['unit']}</div>
          <div style="font-size:11px;color:#64748b">last cal: {s['last_calibrated']}</div>
          <span style="background:{status_bg};color:{status_fg};font-size:10px;padding:1px 8px;border-radius:10px">{s['status']}</span>
          {note_html}
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Sensor Calibration Monitor — OCI Robot Cloud</title>
<style>
  body {{ margin:0; background:#0f172a; color:#e2e8f0; font-family:sans-serif; padding:24px; }}
  h1 {{ color:#C74634; font-size:22px; margin-bottom:4px; }}
  .subtitle {{ color:#64748b; font-size:13px; margin-bottom:20px; }}
  .card {{ background:#1e293b; border-radius:10px; padding:18px; margin-bottom:20px; }}
  .card h2 {{ font-size:15px;color:#38bdf8;margin-top:0; }}
  .sensor-grid {{ display:flex; flex-wrap:wrap; gap:12px; margin-bottom:0; }}
</style>
</head>
<body>
<h1>Sensor Calibration Monitor</h1>
<p class="subtitle">OCI Robot Cloud · Franka Panda · port 8159 — auto-recalibrate when drift &gt; 80% of threshold</p>

<div class="card">
  <h2>Sensor Status Overview</h2>
  <div class="sensor-grid">{sensor_cards}</div>
</div>

<div class="card">
  <h2>Drift as % of Threshold</h2>
  {dsvg}
</div>

<div class="card">
  <h2>Calibration History (last 5 events per sensor)</h2>
  {hsvg}
</div>

<div class="card">
  <h2>30-Day Recalibration Forecast</h2>
  {fsvg}
</div>
</body>
</html>"""

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

if FastAPI is not None:
    app = FastAPI(title="Sensor Calibration Monitor", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return build_html()

    @app.get("/sensors")
    def list_sensors():
        return SENSORS

    @app.get("/sensors/{sensor_id}")
    def get_sensor(sensor_id: str):
        if sensor_id not in SENSORS_BY_ID:
            raise HTTPException(status_code=404, detail="Sensor not found")
        s = SENSORS_BY_ID[sensor_id]
        return {**s, "drift_pct": drift_pct(s)}

    @app.get("/schedule")
    def get_schedule():
        """Return sensors that need recalibration (drift > 80% of threshold)."""
        to_recal = []
        for s in SENSORS:
            pct = drift_pct(s)
            if pct >= 80:
                urgency = "immediate" if pct >= 100 else "soon"
                to_recal.append({
                    "sensor_id": s["id"],
                    "label": s["label"],
                    "drift_pct": round(pct, 1),
                    "status": s["status"],
                    "urgency": urgency,
                    "note": s.get("note", ""),
                })
        return {"recalibration_needed": to_recal, "total": len(to_recal)}

if __name__ == "__main__":
    uvicorn.run("sensor_calibration:app", host="0.0.0.0", port=8159, reload=True)
