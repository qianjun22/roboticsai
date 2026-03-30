"""Real Robot Deployment Checklist Service — OCI Robot Cloud (port 8626).

Dark-theme FastAPI service providing SVG visualizations for robot deployment
checklist phases, deployment timeline Gantt, and risk matrix.
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8626

# ---------------------------------------------------------------------------
# SVG generators
# ---------------------------------------------------------------------------

def svg_checklist_phases() -> str:
    """8-phase horizontal bar checklist with PASS/PENDING/HUMAN-REQUIRED badges."""
    phases = [
        ("Safety Pre-Check",    "HUMAN-REQUIRED", "#f97316"),
        ("Calibration",         "HUMAN-REQUIRED", "#f97316"),
        ("Connectivity Test",   "PASS",            "#22c55e"),
        ("Model Load",          "PASS",            "#22c55e"),
        ("Warm-Up Routine",     "PASS",            "#22c55e"),
        ("Evaluation Run",      "PASS",            "#22c55e"),
        ("Go Live",             "PASS",            "#22c55e"),
        ("Live Monitor",        "PENDING",         "#fbbf24"),
    ]
    W, ROW_H, PAD_TOP = 760, 44, 40
    H = PAD_TOP + len(phases) * ROW_H + 20
    rows = []
    for i, (name, badge, color) in enumerate(phases):
        y = PAD_TOP + i * ROW_H
        bar_w = 520
        rows.append(
            f'<rect x="20" y="{y+6}" width="{bar_w}" height="28" rx="5" fill="#1e293b"/>'
            f'<rect x="20" y="{y+6}" width="{bar_w}" height="28" rx="5" fill="{color}" opacity="0.15"/>'
            f'<text x="32" y="{y+25}" font-family="monospace" font-size="13" fill="#e2e8f0">{name}</text>'
            f'<rect x="558" y="{y+6}" width="170" height="28" rx="5" fill="{color}" opacity="0.25"/>'
            f'<text x="643" y="{y+25}" font-family="monospace" font-size="11" fill="{color}" '
            f'text-anchor="middle" font-weight="bold">{badge}</text>'
        )
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#0f172a;">'
        f'<text x="{W//2}" y="24" font-family="monospace" font-size="15" fill="#C74634" '
        f'text-anchor="middle" font-weight="bold">Deployment Phase Checklist</text>'
        + "".join(rows)
        + "</svg>"
    )
    return svg


def svg_deployment_gantt() -> str:
    """Gantt chart for last 3 deployments (phases as bars, total time ~47 min)."""
    # Each deployment has 8 phases with approximate durations in minutes
    deployments = [
        {"label": "Deploy-3 (latest)", "start": 0,   "color": "#38bdf8"},
        {"label": "Deploy-2",          "start": 55,  "color": "#818cf8"},
        {"label": "Deploy-1",          "start": 110, "color": "#a78bfa"},
    ]
    phase_durations = [4, 8, 3, 5, 6, 10, 5, 6]  # 47 min total
    phase_names = ["Safety", "Calib", "Connect", "Load", "WarmUp", "Eval", "GoLive", "Monitor"]
    W, H = 760, 200
    SCALE = 9.5  # pixels per minute
    LEFT = 140
    ROW_H = 30
    PAD_TOP = 40

    bars = []
    # x-axis ticks
    for t in range(0, 50, 10):
        tx = LEFT + t * SCALE
        bars.append(
            f'<line x1="{tx}" y1="{PAD_TOP-5}" x2="{tx}" y2="{H-20}" stroke="#334155" stroke-width="1"/>'
            f'<text x="{tx}" y="{H-8}" font-size="10" fill="#64748b" text-anchor="middle">{t}m</text>'
        )

    for di, dep in enumerate(deployments):
        row_y = PAD_TOP + di * ROW_H
        bars.append(
            f'<text x="{LEFT-6}" y="{row_y+18}" font-family="monospace" font-size="11" '
            f'fill="#94a3b8" text-anchor="end">{dep["label"]}</text>'
        )
        cursor = 0
        for pi, dur in enumerate(phase_durations):
            x = LEFT + cursor * SCALE
            bw = dur * SCALE - 1
            bars.append(
                f'<rect x="{x:.1f}" y="{row_y}" width="{bw:.1f}" height="22" rx="3" '
                f'fill="{dep["color"]}" opacity="0.7"/>'
                f'<text x="{x+bw/2:.1f}" y="{row_y+14}" font-size="9" fill="#0f172a" '
                f'text-anchor="middle">{phase_names[pi]}</text>'
            )
            cursor += dur
        total_x = LEFT + cursor * SCALE + 4
        bars.append(
            f'<text x="{total_x:.1f}" y="{row_y+15}" font-size="10" fill="#22c55e">47m ✓</text>'
        )

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#0f172a;">'
        f'<text x="{W//2}" y="24" font-family="monospace" font-size="15" fill="#C74634" '
        f'text-anchor="middle" font-weight="bold">Deployment Timeline — Last 3 Runs</text>'
        + "".join(bars)
        + "</svg>"
    )
    return svg


def svg_risk_matrix() -> str:
    """Risk matrix: 8 phases x 4 risk types, color = mitigation status."""
    phases = ["Safety", "Calib", "Connect", "Load", "WarmUp", "Eval", "GoLive", "Monitor"]
    risk_types = ["Data Loss", "Performance", "Safety", "Downtime"]
    # 0=mitigated(green), 1=partial(amber), 2=open(red), 3=N/A(gray)
    matrix = [
        [2, 1, 2, 0],  # Safety
        [1, 2, 2, 1],  # Calib
        [0, 1, 0, 1],  # Connect
        [1, 1, 0, 0],  # Load
        [0, 1, 1, 0],  # WarmUp
        [0, 2, 1, 0],  # Eval
        [1, 1, 1, 1],  # GoLive
        [0, 0, 0, 1],  # Monitor
    ]
    colors = ["#22c55e", "#fbbf24", "#ef4444", "#475569"]
    labels = ["Mitigated", "Partial", "Open", "N/A"]
    CELL = 60
    LEFT = 90
    TOP = 60
    W = LEFT + len(risk_types) * CELL + 120
    H = TOP + len(phases) * CELL + 60

    cells = []
    # Column headers
    for ci, rt in enumerate(risk_types):
        cx = LEFT + ci * CELL + CELL // 2
        cells.append(
            f'<text x="{cx}" y="{TOP-10}" font-size="11" fill="#94a3b8" '
            f'text-anchor="middle" font-family="monospace">{rt}</text>'
        )
    # Row headers + cells
    for ri, phase in enumerate(phases):
        ry = TOP + ri * CELL
        cells.append(
            f'<text x="{LEFT-6}" y="{ry+CELL//2+4}" font-size="11" fill="#94a3b8" '
            f'text-anchor="end" font-family="monospace">{phase}</text>'
        )
        for ci, val in enumerate(matrix[ri]):
            cx = LEFT + ci * CELL
            cells.append(
                f'<rect x="{cx+3}" y="{ry+3}" width="{CELL-6}" height="{CELL-6}" rx="4" '
                f'fill="{colors[val]}" opacity="0.7"/>'
                f'<text x="{cx+CELL//2}" y="{ry+CELL//2+4}" font-size="9" fill="#0f172a" '
                f'text-anchor="middle" font-weight="bold">{labels[val]}</text>'
            )
    # Legend
    lx = LEFT + len(risk_types) * CELL + 10
    for i, (c, lbl) in enumerate(zip(colors, labels)):
        ly = TOP + i * 26
        cells.append(
            f'<rect x="{lx}" y="{ly}" width="14" height="14" rx="2" fill="{c}" opacity="0.8"/>'
            f'<text x="{lx+18}" y="{ly+11}" font-size="10" fill="#94a3b8" font-family="monospace">{lbl}</text>'
        )

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#0f172a;">'
        f'<text x="{(W)//2}" y="30" font-family="monospace" font-size="15" fill="#C74634" '
        f'text-anchor="middle" font-weight="bold">Risk Matrix — Phase × Risk Type</text>'
        + "".join(cells)
        + "</svg>"
    )
    return svg


# ---------------------------------------------------------------------------
# HTML page
# ---------------------------------------------------------------------------

def build_html() -> str:
    checklist_svg = svg_checklist_phases()
    gantt_svg = svg_deployment_gantt()
    risk_svg = svg_risk_matrix()
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Real Robot Deployment Checklist — OCI Robot Cloud</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #e2e8f0; font-family: monospace; padding: 24px; }}
    h1 {{ color: #C74634; font-size: 22px; margin-bottom: 6px; }}
    h2 {{ color: #38bdf8; font-size: 15px; margin: 20px 0 8px; }}
    .subtitle {{ color: #64748b; font-size: 13px; margin-bottom: 20px; }}
    .metrics {{ display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 24px; }}
    .metric {{ background: #1e293b; border: 1px solid #334155; border-radius: 8px;
               padding: 14px 20px; min-width: 160px; }}
    .metric .val {{ font-size: 26px; font-weight: bold; color: #38bdf8; }}
    .metric .lbl {{ font-size: 11px; color: #94a3b8; margin-top: 4px; }}
    .metric.warn .val {{ color: #f97316; }}
    .metric.ok   .val {{ color: #22c55e; }}
    .chart {{ margin-bottom: 28px; overflow-x: auto; }}
    svg {{ display: block; border-radius: 8px; border: 1px solid #1e293b; }}
  </style>
</head>
<body>
  <h1>Real Robot Deployment Checklist</h1>
  <p class="subtitle">OCI Robot Cloud · Port {PORT} · Automated gate review for physical robot deployments</p>

  <div class="metrics">
    <div class="metric ok"><div class="val">6 / 8</div><div class="lbl">Phases Automated</div></div>
    <div class="metric warn"><div class="val">2</div><div class="lbl">Human Sign-off Required<br>(Safety + Calibration)</div></div>
    <div class="metric ok"><div class="val">100%</div><div class="lbl">Success — Last 3 Deploys</div></div>
    <div class="metric"><div class="val">47 min</div><div class="lbl">Avg Deployment Time</div></div>
  </div>

  <h2>Phase Checklist</h2>
  <div class="chart">{checklist_svg}</div>

  <h2>Deployment Timeline (Last 3 Runs)</h2>
  <div class="chart">{gantt_svg}</div>

  <h2>Risk Matrix</h2>
  <div class="chart">{risk_svg}</div>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

if USE_FASTAPI:
    app = FastAPI(
        title="Real Robot Deployment Checklist",
        description="Deployment phase checklist, Gantt timeline, and risk matrix for physical robot deployments.",
        version="1.0.0",
    )

    @app.get("/", response_class=HTMLResponse)
    async def index():
        return HTMLResponse(content=build_html())

    @app.get("/health")
    async def health():
        return JSONResponse({"status": "ok", "service": "real_robot_deployment_checklist", "port": PORT})

    @app.get("/api/checklist")
    async def api_checklist():
        return JSONResponse({
            "phases_automated": 6,
            "phases_total": 8,
            "human_required": ["safety_pre_check", "calibration"],
            "success_rate_last_3": 1.0,
            "avg_deployment_minutes": 47,
        })

    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=PORT)

else:
    # Fallback: stdlib HTTP server
    from http.server import BaseHTTPRequestHandler, HTTPServer
    import json

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):  # silence access log
            pass

        def do_GET(self):
            if self.path == "/health":
                body = json.dumps({"status": "ok", "port": PORT}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                body = build_html().encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

    if __name__ == "__main__":
        print(f"Serving on http://0.0.0.0:{PORT} (stdlib fallback)")
        HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
