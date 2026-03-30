"""Robot Config Manager — FastAPI service on port 8329.

Manages robot hardware configurations, calibration params, and deployment
profiles. Detects config drift and surfaces critical misconfigurations.
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    _USE_FASTAPI = True
except ImportError:
    _USE_FASTAPI = False

import math
import random
import json
from datetime import datetime, timedelta

random.seed(7)

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

ROBOTS = [
    {"id": "PI_SF",           "site": "San Francisco",  "status": "active"},
    {"id": "Apt_Austin",      "site": "Austin TX",      "status": "active"},
    {"id": "OCI_bench",       "site": "OCI Lab Ashburn","status": "active"},
]

# Config parameters with expected vs actual values per robot
CONFIG_PARAMS = [
    {"param": "chunk_size",       "expected": 16,   "units": "steps"},
    {"param": "camera_fps",       "expected": 30,   "units": "Hz"},
    {"param": "servo_gain",       "expected": 1.00, "units": ""},
    {"param": "gripper_thresh",   "expected": 0.50, "units": "N"},
    {"param": "camera_offset_x",  "expected": 0.00, "units": "mm"},
    {"param": "camera_offset_z",  "expected": 0.00, "units": "mm"},
    {"param": "latency_budget",   "expected": 250,  "units": "ms"},
    {"param": "joint_limit_scale","expected": 1.00, "units": ""},
]

# Actual values per robot — OCI_bench has CRITICAL chunk_size drift; PI had camera_offset issue (now fixed)
ACTUAL_VALUES = {
    "PI_SF": {
        "chunk_size": 16,   "camera_fps": 30,  "servo_gain": 1.01,
        "gripper_thresh": 0.51, "camera_offset_x": 0.00, "camera_offset_z": 0.00,
        "latency_budget": 248, "joint_limit_scale": 1.00,
    },
    "Apt_Austin": {
        "chunk_size": 16,   "camera_fps": 29,  "servo_gain": 0.98,
        "gripper_thresh": 0.50, "camera_offset_x": 0.80, "camera_offset_z": -0.40,
        "latency_budget": 255, "joint_limit_scale": 0.99,
    },
    "OCI_bench": {
        "chunk_size": 8,    "camera_fps": 30,  "servo_gain": 1.00,
        "gripper_thresh": 0.50, "camera_offset_x": 0.00, "camera_offset_z": 0.00,
        "latency_budget": 232, "joint_limit_scale": 1.00,
    },
}

# Config version history — 6 months, 3 robots
HISTORY_EVENTS = [
    {"robot": "PI_SF",      "month": 0, "event": "Initial deploy",         "severity": "ok"},
    {"robot": "PI_SF",      "month": 1, "event": "camera_fps → 30",        "severity": "ok"},
    {"robot": "PI_SF",      "month": 2, "event": "camera_offset drift",    "severity": "warn"},
    {"robot": "PI_SF",      "month": 3, "event": "camera_offset fixed",    "severity": "ok"},
    {"robot": "PI_SF",      "month": 4, "event": "servo_gain tuned",       "severity": "ok"},
    {"robot": "PI_SF",      "month": 5, "event": "Calibration current",    "severity": "ok"},
    {"robot": "Apt_Austin", "month": 0, "event": "Initial deploy",         "severity": "ok"},
    {"robot": "Apt_Austin", "month": 1, "event": "gripper_thresh +2%",     "severity": "ok"},
    {"robot": "Apt_Austin", "month": 2, "event": "Calibration",            "severity": "ok"},
    {"robot": "Apt_Austin", "month": 3, "event": "Stable",                 "severity": "ok"},
    {"robot": "Apt_Austin", "month": 4, "event": "latency bump +5ms",      "severity": "warn"},
    {"robot": "Apt_Austin", "month": 5, "event": "Calibration current",    "severity": "ok"},
    {"robot": "OCI_bench",  "month": 0, "event": "Initial deploy",         "severity": "ok"},
    {"robot": "OCI_bench",  "month": 1, "event": "chunk_size → 8 (bug)",   "severity": "critical"},
    {"robot": "OCI_bench",  "month": 2, "event": "Undetected drift",       "severity": "warn"},
    {"robot": "OCI_bench",  "month": 3, "event": "DRIFT DETECTED",         "severity": "critical"},
    {"robot": "OCI_bench",  "month": 4, "event": "Pending fix",            "severity": "warn"},
    {"robot": "OCI_bench",  "month": 5, "event": "Still unresolved",       "severity": "critical"},
]

MONTH_LABELS = ["Oct", "Nov", "Dec", "Jan", "Feb", "Mar"]


def _drift_pct(param: dict, robot_id: str) -> float:
    actual = ACTUAL_VALUES[robot_id][param["param"]]
    expected = param["expected"]
    if expected == 0:
        return 0.0
    return abs(actual - expected) / abs(expected) * 100


def _drift_severity(pct: float) -> str:
    if pct > 40:
        return "critical"
    if pct > 5:
        return "minor"
    return "ok"


# ---------------------------------------------------------------------------
# SVG 1: Config version history timeline
# ---------------------------------------------------------------------------

def _build_history_svg() -> str:
    W, H = 640, 260
    margin = {"top": 40, "right": 20, "bottom": 40, "left": 90}
    chart_w = W - margin["left"] - margin["right"]
    chart_h = H - margin["top"] - margin["bottom"]
    n_months = 6
    n_robots = len(ROBOTS)
    row_h = chart_h / n_robots
    col_w = chart_w / (n_months - 1)

    SEV_COLOR = {"ok": "#22c55e", "warn": "#f59e0b", "critical": "#C74634"}

    elems = ""
    # Grid lines
    for mi in range(n_months):
        x = margin["left"] + mi * col_w
        elems += (
            f'<line x1="{x:.1f}" y1="{margin["top"]}" x2="{x:.1f}" '
            f'y2="{H - margin["bottom"]}" stroke="#1e293b" stroke-width="1"/>\n'
        )
        elems += (
            f'<text x="{x:.1f}" y="{H - margin["bottom"] + 14}" fill="#64748b" '
            f'font-size="11" text-anchor="middle">{MONTH_LABELS[mi]}</text>\n'
        )

    # Robot rows
    for ri, robot in enumerate(ROBOTS):
        ry = margin["top"] + ri * row_h + row_h / 2
        # horizontal baseline
        elems += (
            f'<line x1="{margin["left"]}" y1="{ry:.1f}" '
            f'x2="{W - margin["right"]}" y2="{ry:.1f}" '
            f'stroke="#334155" stroke-width="1.5"/>\n'
        )
        elems += (
            f'<text x="{margin["left"] - 6}" y="{ry + 4:.1f}" fill="#94a3b8" '
            f'font-size="11" text-anchor="end">{robot["id"]}</text>\n'
        )
        # events
        robot_events = [e for e in HISTORY_EVENTS if e["robot"] == robot["id"]]
        for ev in robot_events:
            ex = margin["left"] + ev["month"] * col_w
            color = SEV_COLOR[ev["severity"]]
            r = 7 if ev["severity"] == "critical" else 5
            elems += (
                f'<circle cx="{ex:.1f}" cy="{ry:.1f}" r="{r}" '
                f'fill="{color}" stroke="#0f172a" stroke-width="1.5"/>\n'
            )
            if ev["severity"] in ("critical", "warn"):
                # short label above
                label = ev["event"][:18]
                elems += (
                    f'<text x="{ex:.1f}" y="{ry - r - 3:.1f}" fill="{color}" '
                    f'font-size="8" text-anchor="middle">{label}</text>\n'
                )

    # Legend
    lx = margin["left"]
    for sev, color in SEV_COLOR.items():
        elems += (
            f'<circle cx="{lx + 5}" cy="{H - 6}" r="5" fill="{color}"/>'
            f'<text x="{lx + 13}" y="{H - 2}" fill="#94a3b8" font-size="9">{sev}</text>'
        )
        lx += 70

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'style="background:#0f172a;border-radius:8px">\n'
        f'<text x="{W//2}" y="22" fill="#f1f5f9" font-size="13" font-weight="bold" '
        f'text-anchor="middle">Config Version History — 6-Month Timeline</text>\n'
        + elems +
        f'</svg>'
    )


# ---------------------------------------------------------------------------
# SVG 2: Config drift bar chart
# ---------------------------------------------------------------------------

def _build_drift_svg() -> str:
    W, H = 640, 300
    margin = {"top": 40, "right": 20, "bottom": 60, "left": 110}
    chart_w = W - margin["left"] - margin["right"]
    chart_h = H - margin["top"] - margin["bottom"]
    n_params = len(CONFIG_PARAMS)
    group_w = chart_w / n_params
    bar_w = group_w / (len(ROBOTS) + 1)  # +1 for gap
    max_drift = 55  # % to show

    ROBOT_COLORS = ["#38bdf8", "#a3e635", "#C74634"]

    elems = ""
    # y-axis ticks
    for v in [0, 10, 20, 30, 40, 50]:
        ty = margin["top"] + chart_h - (v / max_drift) * chart_h
        elems += (
            f'<line x1="{margin["left"]}" y1="{ty:.1f}" x2="{W - margin["right"]}" y2="{ty:.1f}" '
            f'stroke="#1e293b" stroke-width="1"/>\n'
        )
        elems += (
            f'<text x="{margin["left"] - 5}" y="{ty + 3:.1f}" fill="#64748b" '
            f'font-size="9" text-anchor="end">{v}%</text>\n'
        )

    # Threshold line at 5%
    thresh_y = margin["top"] + chart_h - (5 / max_drift) * chart_h
    elems += (
        f'<line x1="{margin["left"]}" y1="{thresh_y:.1f}" x2="{W - margin["right"]}" '
        f'y2="{thresh_y:.1f}" stroke="#f59e0b" stroke-width="1" stroke-dasharray="4,3"/>\n'
        f'<text x="{W - margin["right"] + 2}" y="{thresh_y + 3:.1f}" '
        f'fill="#f59e0b" font-size="8">5% threshold</text>\n'
    )

    for pi, param in enumerate(CONFIG_PARAMS):
        gx = margin["left"] + pi * group_w
        for ri, robot in enumerate(ROBOTS):
            drift = _drift_pct(param, robot["id"])
            bh = max(2, (drift / max_drift) * chart_h)
            bx = gx + ri * bar_w + bar_w * 0.1
            by = margin["top"] + chart_h - bh
            color = "#C74634" if drift > 40 else ("#f59e0b" if drift > 5 else ROBOT_COLORS[ri])
            elems += (
                f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bar_w * 0.8:.1f}" '
                f'height="{bh:.1f}" fill="{color}" rx="2"/>\n'
            )
            if drift > 5:
                elems += (
                    f'<text x="{bx + bar_w * 0.4:.1f}" y="{by - 3:.1f}" '
                    f'fill="{color}" font-size="7" text-anchor="middle">{drift:.0f}%</text>\n'
                )
        # param label
        elems += (
            f'<text x="{gx + group_w/2:.1f}" y="{H - margin["bottom"] + 14}" '
            f'fill="#94a3b8" font-size="9" text-anchor="middle" '
            f'transform="rotate(-30 {gx + group_w/2:.1f} {H - margin["bottom"] + 14})">{param["param"]}</text>\n'
        )

    # Legend
    lx = margin["left"]
    for ri, robot in enumerate(ROBOTS):
        elems += (
            f'<rect x="{lx}" y="{H - 16}" width="10" height="10" fill="{ROBOT_COLORS[ri]}" rx="2"/>'
            f'<text x="{lx + 13}" y="{H - 7}" fill="#94a3b8" font-size="10">{robot["id"]}</text>'
        )
        lx += 90

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'style="background:#0f172a;border-radius:8px">\n'
        f'<text x="{W//2}" y="22" fill="#f1f5f9" font-size="13" font-weight="bold" '
        f'text-anchor="middle">Config Drift Detection — Expected vs Actual (%)</text>\n'
        + elems +
        f'</svg>'
    )


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def _drift_summary():
    critical, minor = [], []
    for robot in ROBOTS:
        for param in CONFIG_PARAMS:
            d = _drift_pct(param, robot["id"])
            sev = _drift_severity(d)
            if sev == "critical":
                critical.append({"robot": robot["id"], "param": param["param"], "drift": round(d, 1)})
            elif sev == "minor":
                minor.append({"robot": robot["id"], "param": param["param"], "drift": round(d, 1)})
    return critical, minor


def _dashboard_html() -> str:
    hist_svg = _build_history_svg()
    drift_svg = _build_drift_svg()
    critical, minor = _drift_summary()
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    critical_rows = ""
    for c in critical:
        critical_rows += (
            f'<tr><td style="color:#C74634;font-weight:700">{c["robot"]}</td>'
            f'<td>{c["param"]}</td>'
            f'<td style="color:#C74634">{c["drift"]}%</td>'
            f'<td style="color:#C74634">CRITICAL</td></tr>'
        )
    for m in minor:
        critical_rows += (
            f'<tr><td>{m["robot"]}</td>'
            f'<td>{m["param"]}</td>'
            f'<td style="color:#f59e0b">{m["drift"]}%</td>'
            f'<td style="color:#f59e0b">MINOR</td></tr>'
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Robot Config Manager — Port 8329</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #0f172a; color: #f1f5f9; font-family: 'Segoe UI', system-ui, sans-serif; }}
  header {{ background: #1e293b; border-bottom: 2px solid #C74634; padding: 14px 28px;
            display: flex; align-items: center; justify-content: space-between; }}
  header h1 {{ font-size: 1.2rem; color: #f1f5f9; }}
  header span {{ font-size: 0.8rem; color: #64748b; }}
  .metrics {{ display: grid; grid-template-columns: repeat(4,1fr); gap: 12px;
              padding: 20px 28px; }}
  .metric {{ background: #1e293b; border-radius: 8px; padding: 14px 18px;
             border-left: 3px solid #38bdf8; }}
  .metric .val {{ font-size: 1.5rem; font-weight: 700; color: #38bdf8; }}
  .metric .lbl {{ font-size: 0.75rem; color: #94a3b8; margin-top: 4px; }}
  .metric.critical .val {{ color: #C74634; }}
  .metric.critical {{ border-left-color: #C74634; }}
  .metric.warn .val {{ color: #f59e0b; }}
  .metric.warn {{ border-left-color: #f59e0b; }}
  .charts {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px;
             padding: 0 28px 16px; }}
  .chart-card {{ background: #1e293b; border-radius: 8px; padding: 16px; }}
  .chart-card h2 {{ font-size: 0.85rem; color: #94a3b8; margin-bottom: 12px;
                   text-transform: uppercase; letter-spacing: 0.05em; }}
  .chart-card svg {{ display: block; max-width: 100%; }}
  .drift-table {{ margin: 0 28px 28px; background: #1e293b; border-radius: 8px;
                  padding: 16px; }}
  .drift-table h2 {{ font-size: 0.85rem; color: #94a3b8; margin-bottom: 10px;
                    text-transform: uppercase; letter-spacing: 0.05em; }}
  table {{ border-collapse: collapse; width: 100%; font-size: 0.82rem; }}
  th {{ color: #64748b; text-align: left; padding: 6px 10px;
        border-bottom: 1px solid #334155; }}
  td {{ padding: 6px 10px; border-bottom: 1px solid #1e293b; }}
  footer {{ padding: 10px 28px; font-size: 0.72rem; color: #475569; text-align: right; }}
</style>
</head>
<body>
<header>
  <h1>Robot Config Manager <span style="color:#C74634">Hardware + Calibration Profiles</span></h1>
  <span>Port 8329 &nbsp;|&nbsp; {now}</span>
</header>
<div class="metrics">
  <div class="metric critical">
    <div class="val">{len(critical)}</div>
    <div class="lbl">Critical Drifts</div>
  </div>
  <div class="metric warn">
    <div class="val">{len(minor)}</div>
    <div class="lbl">Minor Drifts</div>
  </div>
  <div class="metric">
    <div class="val">{len(ROBOTS)}</div>
    <div class="lbl">Deployed Robots</div>
  </div>
  <div class="metric">
    <div class="val">Mar 8</div>
    <div class="lbl">Last Calibration (PI_SF)</div>
  </div>
</div>
<div class="charts">
  <div class="chart-card">
    <h2>Config Version History (6 Months)</h2>
    {hist_svg}
  </div>
  <div class="chart-card">
    <h2>Config Drift Detection per Parameter</h2>
    {drift_svg}
  </div>
</div>
<div class="drift-table">
  <h2>Drift Alert Table</h2>
  <table>
    <tr><th>Robot</th><th>Parameter</th><th>Drift %</th><th>Severity</th></tr>
    {critical_rows}
  </table>
</div>
<footer>OCI Robot Cloud &nbsp;|&nbsp; Robot Config Manager v1.0 &nbsp;|&nbsp; cycle-67A</footer>
</body>
</html>"""


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

if _USE_FASTAPI:
    app = FastAPI(
        title="Robot Config Manager",
        description="Manages robot hardware configs, calibration params, and deployment profiles.",
        version="1.0.0",
    )

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return _dashboard_html()

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "robot_config_manager", "port": 8329}

    @app.get("/api/robots")
    async def get_robots():
        return {"robots": ROBOTS}

    @app.get("/api/configs/{robot_id}")
    async def get_config(robot_id: str):
        if robot_id not in ACTUAL_VALUES:
            return {"error": "Robot not found", "available": list(ACTUAL_VALUES.keys())}
        return {"robot_id": robot_id, "config": ACTUAL_VALUES[robot_id]}

    @app.get("/api/drift")
    async def get_drift():
        critical, minor = _drift_summary()
        return {
            "critical": critical,
            "minor": minor,
            "summary": {
                "critical_count": len(critical),
                "minor_count": len(minor),
                "robots_checked": len(ROBOTS),
                "params_checked": len(CONFIG_PARAMS),
            },
        }

    @app.get("/api/history")
    async def get_history():
        return {
            "events": HISTORY_EVENTS,
            "month_labels": MONTH_LABELS,
            "robots": [r["id"] for r in ROBOTS],
        }

else:
    import http.server
    import socketserver

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            body = _dashboard_html().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            pass


if __name__ == "__main__":
    if _USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8329)
    else:
        print("FastAPI not available — falling back to stdlib http.server on port 8329")
        with socketserver.TCPServer(("", 8329), _Handler) as httpd:
            httpd.serve_forever()
