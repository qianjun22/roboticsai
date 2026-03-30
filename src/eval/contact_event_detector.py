"""contact_event_detector.py — FastAPI service on port 8254

Detects and classifies contact events during robot manipulation
from force-torque sensor data. Provides real-time classification
of none/touch/grasp/slip events with latency metrics.
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

import math
import random
import json
from typing import List, Dict, Any

random.seed(42)

# ---------------------------------------------------------------------------
# Mock data generation
# ---------------------------------------------------------------------------

DETECTION_LATENCY_MS = 12.0
OVERALL_ACCURACY = 0.94
GRASP_PRECISION = 0.89
SLIP_RECALL = 0.74
FALSE_POSITIVE_RATE = 0.031

CONTACT_CLASSES = ["none", "touch", "grasp", "slip"]

# Confusion matrix: rows=actual, cols=predicted
CONFUSION_MATRIX = [
    [112,  3,  1,  2],   # actual: none
    [  4, 87,  6,  3],   # actual: touch
    [  2,  5, 91,  3],   # actual: grasp
    [  3,  6,  8, 50],   # actual: slip  (hardest)
]

# Contact events placed on the 300-step timeseries
CONTACT_EVENTS = [
    {"step": 42,  "type": "first_touch",       "color": "#38bdf8"},
    {"step": 88,  "type": "grasp_established",  "color": "#22c55e"},
    {"step": 174, "type": "slip",               "color": "#f59e0b"},
    {"step": 251, "type": "release",            "color": "#C74634"},
]


def _make_ft_series(timesteps: int = 300) -> Dict[str, List[float]]:
    """Generate 6-channel F/T mock data with realistic contact transitions."""
    rng = random.Random(7)
    series: Dict[str, List[float]] = {k: [] for k in ["Fx", "Fy", "Fz", "Tx", "Ty", "Tz"]}
    state = "none"  # none | touch | grasp | slip
    event_map = {e["step"]: e["type"] for e in CONTACT_EVENTS}

    for t in range(timesteps):
        if t in event_map:
            state = event_map[t]

        if state == "none":
            base_f, base_t = 0.0, 0.0
        elif state == "first_touch":
            base_f, base_t = 3.5, 0.05
        elif state == "grasp_established":
            base_f, base_t = 8.2, 0.18
        elif state == "slip":
            base_f, base_t = 5.1, 0.35
        else:  # release
            base_f, base_t = 0.8, 0.02

        noise_f = rng.gauss(0, 0.4)
        noise_t = rng.gauss(0, 0.008)

        series["Fx"].append(round(base_f * 0.80 + noise_f, 3))
        series["Fy"].append(round(base_f * 0.55 + noise_f * 0.7, 3))
        series["Fz"].append(round(base_f * 1.00 + noise_f * 1.1, 3))
        series["Tx"].append(round(base_t * 0.90 + noise_t, 4))
        series["Ty"].append(round(base_t * 1.10 + noise_t * 0.8, 4))
        series["Tz"].append(round(base_t * 0.75 + noise_t * 1.2, 4))

    return series


FT_DATA = _make_ft_series(300)


# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------

def _scale(values: List[float], x0: int, y0: int, w: int, h: int,
           vmin: float, vmax: float) -> List[str]:
    """Map a list of values to SVG polyline point strings."""
    pts = []
    n = len(values)
    vrange = vmax - vmin if vmax != vmin else 1.0
    for i, v in enumerate(values):
        x = x0 + (i / (n - 1)) * w
        y = y0 + h - ((v - vmin) / vrange) * h
        pts.append(f"{x:.1f},{y:.1f}")
    return pts


def _svg_timeseries() -> str:
    """SVG 1: 6-channel F/T timeseries over 300 steps (2 panels)."""
    W, H = 860, 380
    PX, PY, PW, PH = 60, 30, 760, 130
    GAP = 50

    force_channels = ["Fx", "Fy", "Fz"]
    torque_channels = ["Tx", "Ty", "Tz"]
    colors_f = ["#38bdf8", "#818cf8", "#C74634"]
    colors_t = ["#22c55e", "#f59e0b", "#e879f9"]

    def panel(channels, colors, label, y_off, vmin, vmax):
        lines = []
        # background
        lines.append(f'<rect x="{PX}" y="{y_off}" width="{PW}" height="{PH}" fill="#1e293b" rx="4"/>')
        # grid
        for gi in range(5):
            gy = y_off + gi * PH // 4
            lines.append(f'<line x1="{PX}" y1="{gy}" x2="{PX+PW}" y2="{gy}" stroke="#334155" stroke-width="0.5"/>')
        # contact event vertical lines
        n = 300
        for ev in CONTACT_EVENTS:
            ex = PX + (ev["step"] / (n - 1)) * PW
            lines.append(f'<line x1="{ex:.1f}" y1="{y_off}" x2="{ex:.1f}" y2="{y_off+PH}" stroke="{ev["color"]}" stroke-width="1.2" stroke-dasharray="4,3" opacity="0.8"/>')
            if y_off == PY:  # label only on top panel
                lbl = ev["type"].replace("_", " ")
                lines.append(f'<text x="{ex+3:.1f}" y="{y_off+12}" fill="{ev["color"]}" font-size="9" font-family="monospace">{lbl}</text>')
        # data lines
        for ch, col in zip(channels, colors):
            pts = " ".join(_scale(FT_DATA[ch], PX, y_off, PW, PH, vmin, vmax))
            lines.append(f'<polyline points="{pts}" fill="none" stroke="{col}" stroke-width="1.4" opacity="0.9"/>')
        # axis label
        lines.append(f'<text x="{PX-8}" y="{y_off + PH//2}" fill="#94a3b8" font-size="10" font-family="monospace" text-anchor="middle" transform="rotate(-90,{PX-8},{y_off + PH//2})">{label}</text>')
        # legend
        for i, (ch, col) in enumerate(zip(channels, colors)):
            lx = PX + 8 + i * 60
            lines.append(f'<line x1="{lx}" y1="{y_off+PH-8}" x2="{lx+16}" y2="{y_off+PH-8}" stroke="{col}" stroke-width="2"/>')
            lines.append(f'<text x="{lx+20}" y="{y_off+PH-5}" fill="{col}" font-size="9" font-family="monospace">{ch}</text>')
        return "\n".join(lines)

    f_y = PY
    t_y = PY + PH + GAP
    total_h = t_y + PH + 30

    svg_parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{total_h}" style="background:#0f172a;border-radius:8px">',
        f'<text x="{W//2}" y="20" fill="#f1f5f9" font-size="13" font-family="monospace" text-anchor="middle" font-weight="bold">Force-Torque Timeseries — Contact Event Detection (300 steps)</text>',
        panel(force_channels, colors_f, "Force (N)", f_y, -2.0, 12.0),
        panel(torque_channels, colors_t, "Torque (Nm)", t_y, -0.05, 0.55),
        # x-axis ticks
        *[f'<text x="{PX + (i/5)*PW:.0f}" y="{total_h-6}" fill="#64748b" font-size="9" font-family="monospace" text-anchor="middle">{i*60}</text>' for i in range(6)],
        f'<text x="{PX+PW//2}" y="{total_h}" fill="#64748b" font-size="10" font-family="monospace" text-anchor="middle">Timestep</text>',
        '</svg>'
    ]
    return "\n".join(svg_parts)


def _svg_confusion_matrix() -> str:
    """SVG 2: 4×4 confusion matrix heatmap with per-class metrics."""
    CELL = 72
    LABEL_W = 56
    TOP = 60
    LEFT = 80
    W = LEFT + 4 * CELL + 160
    H = TOP + 4 * CELL + 80

    # Compute per-class precision and recall
    cm = CONFUSION_MATRIX
    n_cls = 4
    row_sums = [sum(cm[r]) for r in range(n_cls)]
    col_sums = [sum(cm[r][c] for r in range(n_cls)) for c in range(n_cls)]
    total = sum(row_sums)
    correct = sum(cm[i][i] for i in range(n_cls))

    def precision(c):
        return cm[c][c] / col_sums[c] if col_sums[c] else 0

    def recall(c):
        return cm[c][c] / row_sums[c] if row_sums[c] else 0

    # max non-diagonal value for color scale
    max_val = max(cm[r][c] for r in range(n_cls) for c in range(n_cls) if r != c)
    diag_max = max(cm[i][i] for i in range(n_cls))

    def cell_color(r, c, val):
        if r == c:
            intensity = val / diag_max
            # green channel for correct
            g = int(50 + intensity * 150)
            return f"rgb(20,{g},60)"
        else:
            intensity = val / (max_val + 1)
            r_ch = int(80 + intensity * 130)
            return f"rgb({r_ch},30,30)"

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#0f172a;border-radius:8px">',
        f'<text x="{LEFT + 4*CELL//2}" y="22" fill="#f1f5f9" font-size="13" font-family="monospace" text-anchor="middle" font-weight="bold">Confusion Matrix — Contact Event Classification</text>',
        f'<text x="{LEFT + 4*CELL//2}" y="40" fill="#94a3b8" font-size="10" font-family="monospace" text-anchor="middle">Rows = Actual Class, Cols = Predicted Class</text>',
    ]

    # column headers
    for c, cls in enumerate(CONTACT_CLASSES):
        cx = LEFT + c * CELL + CELL // 2
        parts.append(f'<text x="{cx}" y="{TOP - 8}" fill="#38bdf8" font-size="10" font-family="monospace" text-anchor="middle">{cls}</text>')
    parts.append(f'<text x="{LEFT + 4*CELL//2}" y="{TOP - 22}" fill="#64748b" font-size="9" font-family="monospace" text-anchor="middle">Predicted →</text>')

    # row headers
    for r, cls in enumerate(CONTACT_CLASSES):
        ry = TOP + r * CELL + CELL // 2 + 4
        parts.append(f'<text x="{LEFT - 8}" y="{ry}" fill="#38bdf8" font-size="10" font-family="monospace" text-anchor="end">{cls}</text>')
    parts.append(f'<text x="{LEFT - 36}" y="{TOP + 2*CELL}" fill="#64748b" font-size="9" font-family="monospace" text-anchor="middle" transform="rotate(-90,{LEFT-36},{TOP + 2*CELL})">Actual →</text>')

    # cells
    for r in range(n_cls):
        for c in range(n_cls):
            val = cm[r][c]
            x = LEFT + c * CELL
            y = TOP + r * CELL
            color = cell_color(r, c, val)
            parts.append(f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" fill="{color}" stroke="#1e293b" stroke-width="2"/>')
            parts.append(f'<text x="{x + CELL//2}" y="{y + CELL//2 + 5}" fill="#f1f5f9" font-size="14" font-family="monospace" text-anchor="middle" font-weight="bold">{val}</text>')

    # per-class metrics sidebar
    mx = LEFT + 4 * CELL + 20
    parts.append(f'<text x="{mx}" y="{TOP - 8}" fill="#f1f5f9" font-size="10" font-family="monospace" font-weight="bold">Prec / Recall</text>')
    for c in range(n_cls):
        my = TOP + c * CELL + CELL // 2 + 4
        p = precision(c)
        rc = recall(c)
        p_color = "#22c55e" if p >= 0.85 else "#f59e0b" if p >= 0.70 else "#C74634"
        r_color = "#22c55e" if rc >= 0.85 else "#f59e0b" if rc >= 0.70 else "#C74634"
        parts.append(f'<text x="{mx}" y="{my}" fill="{p_color}" font-size="11" font-family="monospace">{p:.2f}  /  <tspan fill="{r_color}">{rc:.2f}</tspan></text>')

    # summary row
    sy = TOP + 4 * CELL + 30
    acc = correct / total
    parts.append(f'<text x="{LEFT}" y="{sy}" fill="#94a3b8" font-size="11" font-family="monospace">Overall accuracy: <tspan fill="#22c55e" font-weight="bold">{acc:.1%}</tspan>   Total samples: {total}   Slip recall: <tspan fill="#f59e0b">{recall(3):.2f}</tspan> (hardest class)</text>')

    parts.append('</svg>')
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def _html_dashboard() -> str:
    svg1 = _svg_timeseries()
    svg2 = _svg_confusion_matrix()

    metrics = [
        ("Contact Detection Accuracy", f"{OVERALL_ACCURACY:.1%}", "#22c55e"),
        ("Grasp Precision",            f"{GRASP_PRECISION:.2f}",  "#38bdf8"),
        ("Slip Recall",                f"{SLIP_RECALL:.2f}",      "#f59e0b"),
        ("False Positive Rate",        f"{FALSE_POSITIVE_RATE:.1%}", "#94a3b8"),
        ("Avg Detection Latency",      f"{DETECTION_LATENCY_MS} ms", "#38bdf8"),
        ("Contact Classes",            "4",                       "#818cf8"),
    ]

    cards = "".join(
        f'<div style="background:#1e293b;border-radius:8px;padding:16px 20px;min-width:150px">'
        f'<div style="color:#64748b;font-size:11px;margin-bottom:4px">{label}</div>'
        f'<div style="color:{color};font-size:22px;font-weight:bold;font-family:monospace">{value}</div>'
        f'</div>'
        for label, value, color in metrics
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Contact Event Detector — Port 8254</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #f1f5f9; font-family: 'Segoe UI', sans-serif; padding: 24px; }}
    h1 {{ color: #C74634; font-size: 22px; margin-bottom: 4px; }}
    .subtitle {{ color: #64748b; font-size: 13px; margin-bottom: 20px; }}
    .cards {{ display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 28px; }}
    .section {{ margin-bottom: 32px; }}
    .section h2 {{ color: #38bdf8; font-size: 15px; margin-bottom: 10px; }}
    .svg-wrap {{ overflow-x: auto; }}
    .event-legend {{ display: flex; gap: 20px; margin-top: 10px; flex-wrap: wrap; }}
    .ev-item {{ display: flex; align-items: center; gap: 6px; font-size: 12px; color: #94a3b8; }}
    .ev-dot {{ width: 12px; height: 3px; border-radius: 2px; }}
  </style>
</head>
<body>
  <h1>Contact Event Detector</h1>
  <div class="subtitle">Force-torque based contact classification · Port 8254 · OCI Robot Cloud</div>

  <div class="cards">{cards}</div>

  <div class="section">
    <h2>Force-Torque Timeseries with Detected Events</h2>
    <div class="svg-wrap">{svg1}</div>
    <div class="event-legend">
      {''.join(f'<div class="ev-item"><div class="ev-dot" style="background:{e["color"]}"></div>{e["type"].replace("_"," ")} @ step {e["step"]}</div>' for e in CONTACT_EVENTS)}
    </div>
  </div>

  <div class="section">
    <h2>Confusion Matrix — Predicted vs Actual Contact Event Type</h2>
    <div class="svg-wrap">{svg2}</div>
  </div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# FastAPI app (or stdlib fallback)
# ---------------------------------------------------------------------------

if HAS_FASTAPI:
    app = FastAPI(
        title="Contact Event Detector",
        description="Detects and classifies contact events from force-torque data",
        version="1.0.0",
    )

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return _html_dashboard()

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "contact_event_detector", "port": 8254}

    @app.get("/metrics")
    def metrics_endpoint():
        return {
            "contact_detection_accuracy": OVERALL_ACCURACY,
            "grasp_precision": GRASP_PRECISION,
            "slip_recall": SLIP_RECALL,
            "false_positive_rate": FALSE_POSITIVE_RATE,
            "avg_detection_latency_ms": DETECTION_LATENCY_MS,
            "contact_classes": CONTACT_CLASSES,
        }

    @app.get("/events")
    def contact_events():
        return {"events": CONTACT_EVENTS, "total_timesteps": 300}

    @app.get("/confusion_matrix")
    def confusion_matrix_endpoint():
        return {
            "matrix": CONFUSION_MATRIX,
            "classes": CONTACT_CLASSES,
            "overall_accuracy": OVERALL_ACCURACY,
        }

else:
    # Stdlib fallback
    from http.server import HTTPServer, BaseHTTPRequestHandler

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/health":
                body = json.dumps({"status": "ok", "service": "contact_event_detector", "port": 8254}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
            else:
                body = _html_dashboard().encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            pass  # suppress access logs


if __name__ == "__main__":
    if HAS_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8254)
    else:
        print("fastapi not installed — falling back to stdlib http.server on port 8254")
        HTTPServer(("0.0.0.0", 8254), _Handler).serve_forever()
