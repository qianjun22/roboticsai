"""Data Flywheel v2 Service — port 8265

Enhanced data flywheel tracking real→sim→fine-tune→deploy→collect loop efficiency.
Uses mock data; no heavy ML imports at module level.
"""

import json
import math
import random
from datetime import datetime

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

FLYWHEEL_CYCLES = [
    {"cycle": 0, "label": "Baseline",     "demos": 500,  "sr": 0.42, "cycle_time_w": None, "method": "BC",     "projected": False},
    {"cycle": 1, "label": "DAgger-1",     "demos": 1000, "sr": 0.71, "cycle_time_w": 4.0,  "method": "DAgger", "projected": False},
    {"cycle": 2, "label": "DAgger-2",     "demos": 1600, "sr": 0.78, "cycle_time_w": 2.0,  "method": "DAgger", "projected": False},
    {"cycle": 3, "label": "DAgger-3 (proj)", "demos": 2100, "sr": 0.83, "cycle_time_w": 1.5,  "method": "DAgger", "projected": True},
]

FLYWHEEL_STAGES = [
    {"id": "real_demos",    "label": "Real Demos",     "color": "#38bdf8"},
    {"id": "offline_eval",  "label": "Offline Eval",   "color": "#a78bfa"},
    {"id": "fine_tune",     "label": "Fine-Tune",      "color": "#C74634"},
    {"id": "deploy",        "label": "Deploy",         "color": "#fb923c"},
    {"id": "dagger_collect","label": "DAgger Collect", "color": "#34d399"},
]

CYCLE_STAGE_TIMES = {
    1: {"real_demos": "2w", "offline_eval": "3d", "fine_tune": "2d", "deploy": "1d", "dagger_collect": "2w"},
    2: {"real_demos": "1w", "offline_eval": "2d", "fine_tune": "1.5d", "deploy": "1d", "dagger_collect": "1w"},
    3: {"real_demos": "3d", "offline_eval": "1d", "fine_tune": "1d",  "deploy": "6h", "dagger_collect": "5d"},
}


def get_summary():
    completed = [c for c in FLYWHEEL_CYCLES if not c["projected"]]
    latest    = completed[-1]
    first     = completed[0]
    sr_gain   = round(latest["sr"] - first["sr"], 3)
    accel     = None
    times     = [c["cycle_time_w"] for c in completed if c["cycle_time_w"]]
    if len(times) >= 2:
        accel = round(times[0] / times[-1], 2)
    return {
        "total_cycles": len(completed) - 1,
        "current_sr": latest["sr"],
        "baseline_sr": first["sr"],
        "sr_gain": sr_gain,
        "current_demos": latest["demos"],
        "cycle_acceleration": accel,
        "optimal_trigger_threshold": 0.05,
        "marginal_sr_c1_c2": round(FLYWHEEL_CYCLES[2]["sr"] - FLYWHEEL_CYCLES[1]["sr"], 3),
        "marginal_sr_c0_c1": round(FLYWHEEL_CYCLES[1]["sr"] - FLYWHEEL_CYCLES[0]["sr"], 3),
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


# ---------------------------------------------------------------------------
# SVG: Flywheel cycle diagram (circular flow)
# ---------------------------------------------------------------------------

def _svg_flywheel_diagram() -> str:
    W, H = 620, 380
    cx, cy = W // 2, H // 2
    R = 130  # radius of stage circle

    n = len(FLYWHEEL_STAGES)
    # angles: start from top, go clockwise
    angles = [math.pi * (-0.5 + 2 * i / n) for i in range(n)]

    def pt(angle, r=R):
        return cx + r * math.cos(angle), cy + r * math.sin(angle)

    # draw arcs between stages
    arcs = ""
    cycle_labels = ["4w→2w→1.5w", "+500 demos", "fine-tune 2d", "deploy 1d", "+600 demos"]
    for i in range(n):
        a0 = angles[i]
        a1 = angles[(i + 1) % n]
        # midpoint of arc
        a_mid = (a0 + a1) / 2
        # arc path (approximate with cubic bezier along the ring)
        sx, sy = pt(a0, R + 20)
        ex, ey = pt(a1, R + 20)
        # control points — push outward
        cmx, cmy = pt(a_mid, R + 52)
        arcs += (
            f'<path d="M{sx:.1f},{sy:.1f} Q{cmx:.1f},{cmy:.1f} {ex:.1f},{ey:.1f}" '
            f'fill="none" stroke="#38bdf8" stroke-width="2" stroke-dasharray="5,3" opacity="0.6"/>'
        )
        # arrowhead
        arcs += (
            f'<circle cx="{ex:.1f}" cy="{ey:.1f}" r="3.5" fill="#38bdf8" opacity="0.8"/>'
        )
        # label midpoint
        lx, ly = pt(a_mid, R + 72)
        arcs += (
            f'<text x="{lx:.1f}" y="{ly:.1f}" fill="#94a3b8" font-size="9" text-anchor="middle">{cycle_labels[i]}</text>'
        )

    # stage nodes
    nodes = ""
    for i, stage in enumerate(FLYWHEEL_STAGES):
        sx, sy = pt(angles[i])
        color = stage["color"]
        nodes += (
            f'<circle cx="{sx:.1f}" cy="{sy:.1f}" r="34" fill="#1e293b" stroke="{color}" stroke-width="2.5"/>'
            f'<text x="{sx:.1f}" y="{sy-4:.1f}" fill="{color}" font-size="9.5" font-weight="600" text-anchor="middle">{stage["label"].split()[0]}</text>'
        )
        if " " in stage["label"]:
            second = stage["label"].split(" ", 1)[1]
            nodes += f'<text x="{sx:.1f}" y="{sy+9:.1f}" fill="{color}" font-size="9.5" font-weight="600" text-anchor="middle">{second}</text>'

    # center annotation
    center = (
        f'<circle cx="{cx}" cy="{cy}" r="38" fill="#0f172a" stroke="#334155" stroke-width="1.5"/>'
        f'<text x="{cx}" y="{cy-8}" fill="#C74634" font-size="11" font-weight="700" text-anchor="middle">Flywheel</text>'
        f'<text x="{cx}" y="{cy+6}" fill="#94a3b8" font-size="9" text-anchor="middle">v2  ·  5 cycles</text>'
        f'<text x="{cx}" y="{cy+20}" fill="#34d399" font-size="9" text-anchor="middle">2.7× faster</text>'
    )

    # title
    title = f'<text x="{W//2}" y="22" fill="#e2e8f0" font-size="13" font-weight="600" text-anchor="middle">Data Flywheel Cycle Diagram</text>'

    return f'''
<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg"
     style="background:#0f172a;border-radius:8px;">
  {title}
  {arcs}
  {nodes}
  {center}
</svg>'''


# ---------------------------------------------------------------------------
# SVG: Line chart — data volume and SR per cycle
# ---------------------------------------------------------------------------

def _svg_cycle_chart() -> str:
    W, H = 620, 320
    pad_l, pad_r, pad_t, pad_b = 65, 70, 30, 50
    inner_w = W - pad_l - pad_r
    inner_h = H - pad_t - pad_b

    cycles   = [c["cycle"] for c in FLYWHEEL_CYCLES]
    srs      = [c["sr"]    for c in FLYWHEEL_CYCLES]
    demos    = [c["demos"] for c in FLYWHEEL_CYCLES]
    proj_idx = [i for i, c in enumerate(FLYWHEEL_CYCLES) if c["projected"]]

    x_min, x_max = 0, 3
    sr_min, sr_max = 0.35, 0.90
    d_min, d_max  = 0, 2500

    def xp(v):
        return pad_l + (v - x_min) / (x_max - x_min) * inner_w

    def ysr(v):
        return pad_t + inner_h - (v - sr_min) / (sr_max - sr_min) * inner_h

    def yd(v):
        return pad_t + inner_h - (v - d_min) / (d_max - d_min) * inner_h

    # gridlines
    grid = ""
    for v in [0.40, 0.50, 0.60, 0.70, 0.80]:
        yy = ysr(v)
        grid += f'<line x1="{pad_l}" y1="{yy:.1f}" x2="{W-pad_r}" y2="{yy:.1f}" stroke="#1e293b" stroke-width="1"/>'
        grid += f'<text x="{pad_l-6}" y="{yy+4:.1f}" fill="#94a3b8" font-size="10" text-anchor="end">{v:.2f}</text>'
    for v in [500, 1000, 1500, 2000, 2500]:
        yy = yd(v)
        grid += f'<text x="{W-pad_r+8}" y="{yy+4:.1f}" fill="#34d399" font-size="10">{v}</text>'

    # x axis labels
    x_labels = ""
    for c in FLYWHEEL_CYCLES:
        xx = xp(c["cycle"])
        lbl = f"C{c['cycle']}{' (proj)' if c['projected'] else ''}"
        x_labels += f'<text x="{xx:.1f}" y="{pad_t+inner_h+18}" fill="#94a3b8" font-size="10" text-anchor="middle">{lbl}</text>'

    # SR polyline — solid for real, dashed for projected
    real_sr_pts = " ".join(
        f"{xp(c['cycle']):.1f},{ysr(c['sr']):.1f}"
        for c in FLYWHEEL_CYCLES if not c["projected"]
    )
    # projected continuation
    last_real = next(c for c in reversed(FLYWHEEL_CYCLES) if not c["projected"])
    proj_sr_pts = " ".join(
        f"{xp(c['cycle']):.1f},{ysr(c['sr']):.1f}"
        for c in [last_real] + [c for c in FLYWHEEL_CYCLES if c["projected"]]
    )

    # Demos polyline
    real_d_pts = " ".join(
        f"{xp(c['cycle']):.1f},{yd(c['demos']):.1f}"
        for c in FLYWHEEL_CYCLES if not c["projected"]
    )
    proj_d_pts = " ".join(
        f"{xp(c['cycle']):.1f},{yd(c['demos']):.1f}"
        for c in [last_real] + [c for c in FLYWHEEL_CYCLES if c["projected"]]
    )

    # dots
    dots = ""
    for c in FLYWHEEL_CYCLES:
        xx = xp(c["cycle"])
        yy_sr = ysr(c["sr"])
        yy_d  = yd(c["demos"])
        fill_sr = "#38bdf8" if not c["projected"] else "none"
        stroke_sr = "#38bdf8"
        dots += f'<circle cx="{xx:.1f}" cy="{yy_sr:.1f}" r="5" fill="{fill_sr}" stroke="{stroke_sr}" stroke-width="2"/>'
        fill_d = "#34d399" if not c["projected"] else "none"
        dots += f'<circle cx="{xx:.1f}" cy="{yy_d:.1f}" r="5" fill="{fill_d}" stroke="#34d399" stroke-width="2"/>'
        # value labels
        dots += f'<text x="{xx:.1f}" y="{yy_sr-9:.1f}" fill="#38bdf8" font-size="9" text-anchor="middle">{c["sr"]}</text>'
        dots += f'<text x="{xx:.1f}" y="{yy_d+18:.1f}" fill="#34d399" font-size="9" text-anchor="middle">{c["demos"]}</text>'

    svg = f'''
<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg"
     style="background:#0f172a;border-radius:8px;">
  {grid}
  <line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t+inner_h}" stroke="#334155" stroke-width="1.5"/>
  <line x1="{pad_l}" y1="{pad_t+inner_h}" x2="{W-pad_r}" y2="{pad_t+inner_h}" stroke="#334155" stroke-width="1.5"/>
  <line x1="{W-pad_r}" y1="{pad_t}" x2="{W-pad_r}" y2="{pad_t+inner_h}" stroke="#334155" stroke-width="1.5"/>
  <!-- SR lines -->
  <polyline points="{real_sr_pts}" fill="none" stroke="#38bdf8" stroke-width="2.5"/>
  <polyline points="{proj_sr_pts}" fill="none" stroke="#38bdf8" stroke-width="2" stroke-dasharray="6,4"/>
  <!-- Demo lines -->
  <polyline points="{real_d_pts}" fill="none" stroke="#34d399" stroke-width="2.5"/>
  <polyline points="{proj_d_pts}" fill="none" stroke="#34d399" stroke-width="2" stroke-dasharray="6,4"/>
  {dots}
  {x_labels}
  <!-- axis labels -->
  <text x="{pad_l-50}" y="{pad_t+inner_h//2}" fill="#38bdf8" font-size="11"
        transform="rotate(-90,{pad_l-50},{pad_t+inner_h//2})">Success Rate</text>
  <text x="{W-pad_r+55}" y="{pad_t+inner_h//2}" fill="#34d399" font-size="11"
        transform="rotate(90,{W-pad_r+55},{pad_t+inner_h//2})">Demos</text>
  <text x="{W//2}" y="{H-4}" fill="#94a3b8" font-size="11" text-anchor="middle">Flywheel Cycle</text>
  <!-- legend -->
  <rect x="{pad_l+10}" y="{pad_t+8}" width="12" height="3" fill="#38bdf8"/>
  <text x="{pad_l+26}" y="{pad_t+14}" fill="#38bdf8" font-size="10">Success Rate</text>
  <rect x="{pad_l+115}" y="{pad_t+8}" width="12" height="3" fill="#34d399"/>
  <text x="{pad_l+131}" y="{pad_t+14}" fill="#34d399" font-size="10">Demo Count</text>
  <text x="{pad_l+210}" y="{pad_t+14}" fill="#94a3b8" font-size="9">-- projected</text>
</svg>'''
    return svg


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def _build_html() -> str:
    summary = get_summary()
    chart1  = _svg_flywheel_diagram()
    chart2  = _svg_cycle_chart()

    rows = "".join(
        f"<tr>"
        f"<td>C{c['cycle']}</td>"
        f"<td>{c['label']}</td>"
        f"<td>{c['demos']:,}</td>"
        f"<td>{c['sr']:.2f}</td>"
        f"<td>{c['cycle_time_w']}w</td>"
        f"<td>{c['method']}</td>"
        f"{'<td style=color:#94a3b8;font-style:italic>Projected</td>' if c['projected'] else '<td style=color:#34d399>Completed</td>'}"
        f"</tr>"
        for c in FLYWHEEL_CYCLES
    )

    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Data Flywheel v2 — OCI Robot Cloud</title>
  <style>
    *{{margin:0;padding:0;box-sizing:border-box}}
    body{{background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',system-ui,sans-serif;padding:24px}}
    h1{{color:#C74634;font-size:1.6rem;margin-bottom:4px}}
    .sub{{color:#94a3b8;font-size:.85rem;margin-bottom:24px}}
    .kpi-row{{display:flex;gap:16px;flex-wrap:wrap;margin-bottom:28px}}
    .kpi{{background:#1e293b;border:1px solid #334155;border-radius:8px;padding:16px 20px;min-width:150px}}
    .kpi .val{{font-size:1.7rem;font-weight:700;color:#38bdf8}}
    .kpi .lbl{{font-size:.75rem;color:#94a3b8;margin-top:2px}}
    .kpi.accent .val{{color:#C74634}}
    .kpi.green .val{{color:#34d399}}
    .charts{{display:flex;flex-direction:column;gap:24px;margin-bottom:28px}}
    .chart-box{{background:#1e293b;border:1px solid #334155;border-radius:10px;padding:16px}}
    .chart-box h2{{color:#38bdf8;font-size:.95rem;margin-bottom:12px}}
    table{{width:100%;border-collapse:collapse;background:#1e293b;border-radius:8px;overflow:hidden}}
    th{{background:#0f172a;color:#94a3b8;font-size:.8rem;padding:10px 14px;text-align:left;border-bottom:1px solid #334155}}
    td{{padding:9px 14px;font-size:.85rem;border-bottom:1px solid #1a2540}}
    tr:hover td{{background:#0f172a}}
    footer{{margin-top:28px;color:#475569;font-size:.75rem;text-align:center}}
  </style>
</head>
<body>
  <h1>Data Flywheel v2</h1>
  <div class="sub">Real → Sim → Fine-Tune → Deploy → Collect loop tracker &mdash; port 8265 &mdash; {summary['timestamp']}</div>

  <div class="kpi-row">
    <div class="kpi accent"><div class="val">{summary['total_cycles']}</div><div class="lbl">Completed Cycles</div></div>
    <div class="kpi"><div class="val">{summary['current_sr']}</div><div class="lbl">Current SR</div></div>
    <div class="kpi"><div class="val">+{summary['sr_gain']}</div><div class="lbl">Total SR Gain</div></div>
    <div class="kpi green"><div class="val">{summary['cycle_acceleration']}×</div><div class="lbl">Cycle Acceleration</div></div>
    <div class="kpi"><div class="val">{summary['current_demos']:,}</div><div class="lbl">Total Demos</div></div>
    <div class="kpi"><div class="val">{summary['optimal_trigger_threshold']}</div><div class="lbl">Retrigger Threshold (SR drop)</div></div>
  </div>

  <div class="charts">
    <div class="chart-box">
      <h2>Flywheel Cycle Diagram — Real→Eval→FineTune→Deploy→Collect</h2>
      {chart1}
    </div>
    <div class="chart-box">
      <h2>Data Volume &amp; Success Rate per Flywheel Cycle</h2>
      {chart2}
    </div>
  </div>

  <table>
    <thead>
      <tr>
        <th>Cycle</th><th>Label</th><th>Demos</th>
        <th>SR</th><th>Cycle Time</th><th>Method</th><th>Status</th>
      </tr>
    </thead>
    <tbody>{rows}</tbody>
  </table>

  <footer>OCI Robot Cloud &mdash; Data Flywheel v2 Service &mdash; port 8265</footer>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

if USE_FASTAPI:
    app = FastAPI(
        title="Data Flywheel v2",
        description="Enhanced data flywheel tracking real→sim→fine-tune→deploy→collect loop efficiency",
        version="2.0.0",
    )

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return HTMLResponse(_build_html())

    @app.get("/api/summary")
    async def api_summary():
        return JSONResponse(get_summary())

    @app.get("/api/cycles")
    async def api_cycles():
        return JSONResponse(FLYWHEEL_CYCLES)

    @app.get("/api/stages")
    async def api_stages():
        return JSONResponse(FLYWHEEL_STAGES)

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "data_flywheel_v2", "port": 8265}

else:
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/api/summary":
                body = json.dumps(get_summary()).encode()
                ct = "application/json"
            elif self.path == "/api/cycles":
                body = json.dumps(FLYWHEEL_CYCLES).encode()
                ct = "application/json"
            elif self.path == "/health":
                body = json.dumps({"status": "ok", "port": 8265}).encode()
                ct = "application/json"
            else:
                body = _build_html().encode()
                ct = "text/html"
            self.send_response(200)
            self.send_header("Content-Type", ct)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            pass


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8265)
    else:
        print("[data_flywheel_v2] fastapi not found — using stdlib http.server on port 8265")
        server = HTTPServer(("0.0.0.0", 8265), _Handler)
        print("[data_flywheel_v2] Listening on http://0.0.0.0:8265")
        server.serve_forever()
