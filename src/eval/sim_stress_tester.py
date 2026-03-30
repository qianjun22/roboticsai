"""sim_stress_tester.py — OCI Robot Cloud Simulation Stress Tester Service (port 8310)

Stress tests simulation environments under extreme conditions to find failure modes.
FastAPI service with dark-theme HTML dashboard, SVG charts, and mock data.
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

import random
import math
import json
from datetime import datetime

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

STRESS_DIMS = [
    {"name": "high_frequency_contacts", "score": 0.91, "status": "PASS",   "note": "1kHz contact events stable"},
    {"name": "many_objects_20",          "score": 0.88, "status": "PASS",   "note": "20-object scenes OK at 30fps"},
    {"name": "long_horizon_2000steps",   "score": 0.85, "status": "PASS",   "note": "Drift <0.3mm at 2000 steps"},
    {"name": "concurrent_tasks_4",       "score": 0.83, "status": "PASS",   "note": "4-task parallel OK"},
    {"name": "physics_instability",      "score": 0.79, "status": "PASS",   "note": "Auto-recovery in 3 frames"},
    {"name": "memory_pressure",          "score": 0.61, "status": "MARGINAL","note": "76.2 GB / 80 GB — tight"},
    {"name": "high_DR",                  "score": 0.87, "status": "PASS",   "note": "DR range ×10 handles fine"},
    {"name": "mixed_embodiment",         "score": 0.80, "status": "PASS",   "note": "Arm + mobile base co-sim"},
]

# Concurrent sim performance data
# (concurrent_count, a100_80gb_fps, a100_40gb_fps)
CONCURRENT_PERF = [
    (1,  62, 58),
    (2,  52, 47),
    (4,  40, 34),
    (8,  24, 17),
    (12, 12,  6),
    (16,  5,  2),
]

SUMMARY = {
    "pass_rate": 7 / 8,
    "memory_pressure_margin_gb": 80 - 76.2,
    "max_concurrent_sims": 8,
    "breakdown_at": 12,
    "a100_80gb_8sim_fps": 24,
    "test_run_ts": "2026-03-30T04:00:00Z",
    "total_test_cases": 320,
    "failed_test_cases": 7,
}

# ---------------------------------------------------------------------------
# SVG generators
# ---------------------------------------------------------------------------

def radar_svg() -> str:
    """Radar chart of 8 stress dimensions with pass/fail coloring."""
    cx, cy, r = 220, 210, 140
    n = len(STRESS_DIMS)
    angles = [math.pi / 2 + 2 * math.pi * i / n for i in range(n)]

    def pt(angle: float, frac: float):
        return (cx + frac * r * math.cos(angle),
                cy - frac * r * math.sin(angle))

    # Grid rings
    rings = ""
    for level in [0.25, 0.5, 0.75, 1.0]:
        pts = " ".join(f"{pt(a, level)[0]:.1f},{pt(a, level)[1]:.1f}" for a in angles)
        rings += f'<polygon points="{pts}" fill="none" stroke="#334155" stroke-width="1"/>\n'

    # Axis lines
    axes = ""
    for a in angles:
        x, y = pt(a, 1.0)
        axes += f'<line x1="{cx}" y1="{cy}" x2="{x:.1f}" y2="{y:.1f}" stroke="#475569" stroke-width="1"/>\n'

    # Data polygon
    data_pts = " ".join(f"{pt(a, d['score'])[0]:.1f},{pt(a, d['score'])[1]:.1f}"
                        for a, d in zip(angles, STRESS_DIMS))
    poly = (f'<polygon points="{data_pts}" fill="#38bdf840" stroke="#38bdf8" stroke-width="2"/>\n')

    # Dots + labels
    dots = ""
    labels = ""
    for i, (a, d) in enumerate(zip(angles, STRESS_DIMS)):
        x, y = pt(a, d["score"])
        color = "#ef4444" if d["status"] == "MARGINAL" else "#22c55e"
        dots += f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="{color}"/>\n'

        lx, ly = pt(a, 1.18)
        anchor = "middle"
        if lx < cx - 10: anchor = "end"
        elif lx > cx + 10: anchor = "start"
        short = d["name"].replace("_", " ")
        score_label = f"{d['score']:.2f}"
        status_color = "#ef4444" if d["status"] == "MARGINAL" else "#a3e635"
        labels += (f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="{anchor}" '
                   f'font-size="9" fill="#cbd5e1">{short}</text>\n'
                   f'<text x="{lx:.1f}" y="{ly+11:.1f}" text-anchor="{anchor}" '
                   f'font-size="8" fill="{status_color}">{score_label} {d["status"]}</text>\n')

    title = '<text x="220" y="22" text-anchor="middle" font-size="13" font-weight="bold" fill="#f1f5f9">Stress Test Radar — 8 Dimensions</text>'
    return (f'<svg width="440" height="380" xmlns="http://www.w3.org/2000/svg" '
            f'style="background:#1e293b;border-radius:8px">\n'
            f'{title}\n{rings}{axes}{poly}{dots}{labels}</svg>')


def perf_curve_svg() -> str:
    """Performance degradation curve: FPS vs concurrent sim count, two GPU lines."""
    W, H = 520, 300
    PAD_L, PAD_R, PAD_T, PAD_B = 55, 20, 30, 50
    chart_w = W - PAD_L - PAD_R
    chart_h = H - PAD_T - PAD_B

    x_vals = [c[0] for c in CONCURRENT_PERF]
    x_max = 16
    y_max = 70
    fps_threshold = 20  # minimum acceptable FPS

    def sx(v): return PAD_L + (v / x_max) * chart_w
    def sy(v): return PAD_T + chart_h - (v / y_max) * chart_h

    # Threshold line
    thresh_y = sy(fps_threshold)
    threshold = (f'<line x1="{sx(0):.1f}" y1="{thresh_y:.1f}" '
                 f'x2="{sx(x_max):.1f}" y2="{thresh_y:.1f}" '
                 f'stroke="#f59e0b" stroke-width="1" stroke-dasharray="4,3"/>\n'
                 f'<text x="{sx(x_max)-4:.1f}" y="{thresh_y-4:.1f}" text-anchor="end" '
                 f'font-size="9" fill="#f59e0b">20fps min</text>\n')

    def polyline(key_idx: int, color: str) -> str:
        pts = " ".join(f"{sx(c[0]):.1f},{sy(c[key_idx]):.1f}" for c in CONCURRENT_PERF)
        return f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2.5"/>\n'

    line_80 = polyline(1, "#38bdf8")
    line_40 = polyline(2, "#C74634")

    # Dots + breakdown marker
    dots = ""
    for c in CONCURRENT_PERF:
        for key_idx, color in [(1, "#38bdf8"), (2, "#C74634")]:
            fps = c[key_idx]
            x_, y_ = sx(c[0]), sy(fps)
            dot_color = "#ef4444" if fps < fps_threshold else color
            dots += f'<circle cx="{x_:.1f}" cy="{y_:.1f}" r="4" fill="{dot_color}"/>\n'

    # Breakdown annotation at concurrent=12
    bd_x = sx(12)
    breakdown = (f'<line x1="{bd_x:.1f}" y1="{PAD_T}" x2="{bd_x:.1f}" y2="{PAD_T+chart_h}" '
                 f'stroke="#ef4444" stroke-width="1" stroke-dasharray="3,3"/>\n'
                 f'<text x="{bd_x+3:.1f}" y="{PAD_T+14:.1f}" font-size="9" fill="#ef4444">breakdown</text>\n')

    # Grid
    grid = ""
    for yv in range(0, 71, 10):
        gy = sy(yv)
        grid += (f'<line x1="{PAD_L}" y1="{gy:.1f}" x2="{W-PAD_R}" y2="{gy:.1f}" '
                 f'stroke="#1e3a5f" stroke-width="1"/>\n'
                 f'<text x="{PAD_L-5}" y="{gy+4:.1f}" text-anchor="end" font-size="9" fill="#94a3b8">{yv}</text>\n')
    for xv in x_vals:
        gx = sx(xv)
        grid += (f'<line x1="{gx:.1f}" y1="{PAD_T}" x2="{gx:.1f}" y2="{PAD_T+chart_h}" '
                 f'stroke="#1e3a5f" stroke-width="1"/>\n'
                 f'<text x="{gx:.1f}" y="{PAD_T+chart_h+14:.1f}" text-anchor="middle" font-size="9" fill="#94a3b8">{xv}</text>\n')

    # Axes
    axes = (f'<line x1="{PAD_L}" y1="{PAD_T}" x2="{PAD_L}" y2="{PAD_T+chart_h}" stroke="#475569" stroke-width="1.5"/>\n'
            f'<line x1="{PAD_L}" y1="{PAD_T+chart_h}" x2="{W-PAD_R}" y2="{PAD_T+chart_h}" stroke="#475569" stroke-width="1.5"/>\n')

    # Labels
    title = f'<text x="{W//2}" y="18" text-anchor="middle" font-size="13" font-weight="bold" fill="#f1f5f9">FPS vs Concurrent Simulations</text>'
    xlabel = f'<text x="{W//2}" y="{H-4}" text-anchor="middle" font-size="10" fill="#94a3b8">Concurrent Simulations</text>'
    ylabel = (f'<text x="12" y="{PAD_T+chart_h//2}" text-anchor="middle" font-size="10" fill="#94a3b8" '
              f'transform="rotate(-90,12,{PAD_T+chart_h//2})">FPS</text>')
    legend = (f'<rect x="{W-140}" y="{PAD_T+5}" width="10" height="10" fill="#38bdf8"/>'
              f'<text x="{W-126}" y="{PAD_T+14}" font-size="9" fill="#cbd5e1">A100 80GB</text>'
              f'<rect x="{W-140}" y="{PAD_T+22}" width="10" height="10" fill="#C74634"/>'
              f'<text x="{W-126}" y="{PAD_T+31}" font-size="9" fill="#cbd5e1">A100 40GB</text>')

    return (f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg" '
            f'style="background:#1e293b;border-radius:8px">\n'
            f'{title}{xlabel}{ylabel}\n{grid}{axes}{threshold}{line_80}{line_40}{dots}{breakdown}{legend}</svg>')


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def make_html() -> str:
    radar = radar_svg()
    perf = perf_curve_svg()

    rows = ""
    for d in STRESS_DIMS:
        bar_w = int(d["score"] * 160)
        status_color = "#ef4444" if d["status"] == "MARGINAL" else "#22c55e"
        rows += f"""
        <tr>
          <td style="padding:6px 10px;color:#e2e8f0">{d['name']}</td>
          <td style="padding:6px 10px">
            <div style="background:#0f172a;border-radius:4px;width:160px;height:12px">
              <div style="background:#38bdf8;width:{bar_w}px;height:12px;border-radius:4px"></div>
            </div>
          </td>
          <td style="padding:6px 10px;color:#94a3b8">{d['score']:.2f}</td>
          <td style="padding:6px 10px;color:{status_color};font-weight:bold">{d['status']}</td>
          <td style="padding:6px 10px;color:#64748b;font-size:12px">{d['note']}</td>
        </tr>"""

    pass_rate_pct = SUMMARY["pass_rate"] * 100
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Sim Stress Tester — Port 8310</title>
  <style>
    body {{ margin:0; background:#0f172a; color:#e2e8f0; font-family:'Segoe UI',sans-serif; }}
    .header {{ background:#1e293b; padding:20px 32px; border-bottom:3px solid #C74634; display:flex; align-items:center; gap:16px; }}
    .header h1 {{ margin:0; font-size:22px; color:#f1f5f9; }}
    .header .sub {{ font-size:13px; color:#94a3b8; margin-top:4px; }}
    .badge {{ background:#C74634; color:#fff; padding:4px 12px; border-radius:20px; font-size:12px; font-weight:bold; }}
    .kpi-row {{ display:flex; gap:16px; padding:24px 32px 0; flex-wrap:wrap; }}
    .kpi {{ background:#1e293b; border-radius:10px; padding:18px 24px; min-width:160px; border-left:4px solid #38bdf8; }}
    .kpi.warn {{ border-left-color:#f59e0b; }}
    .kpi.bad {{ border-left-color:#ef4444; }}
    .kpi .val {{ font-size:28px; font-weight:bold; color:#38bdf8; }}
    .kpi.warn .val {{ color:#f59e0b; }}
    .kpi.bad .val {{ color:#ef4444; }}
    .kpi .lbl {{ font-size:12px; color:#94a3b8; margin-top:4px; }}
    .section {{ padding:24px 32px; }}
    .section h2 {{ font-size:16px; color:#94a3b8; text-transform:uppercase; letter-spacing:.08em; margin-bottom:16px; }}
    table {{ border-collapse:collapse; width:100%; background:#1e293b; border-radius:10px; overflow:hidden; }}
    th {{ background:#0f172a; padding:8px 10px; text-align:left; font-size:12px; color:#64748b; text-transform:uppercase; }}
    tr:nth-child(even) {{ background:#162032; }}
    .charts {{ display:flex; gap:24px; flex-wrap:wrap; padding:0 32px 24px; }}
    .footer {{ padding:16px 32px; font-size:11px; color:#334155; border-top:1px solid #1e293b; }}
  </style>
</head>
<body>
  <div class="header">
    <div>
      <h1>Simulation Stress Tester</h1>
      <div class="sub">OCI Robot Cloud · Extreme condition failure-mode discovery · Port 8310</div>
    </div>
    <div style="margin-left:auto"><span class="badge">LIVE</span></div>
  </div>

  <div class="kpi-row">
    <div class="kpi">
      <div class="val">{pass_rate_pct:.0f}%</div>
      <div class="lbl">Stress Test Pass Rate</div>
    </div>
    <div class="kpi warn">
      <div class="val">{SUMMARY['memory_pressure_margin_gb']:.1f} GB</div>
      <div class="lbl">Memory Pressure Margin</div>
    </div>
    <div class="kpi">
      <div class="val">{SUMMARY['max_concurrent_sims']}</div>
      <div class="lbl">Max Concurrent Sims (&gt;20fps)</div>
    </div>
    <div class="kpi bad">
      <div class="val">{SUMMARY['breakdown_at']}</div>
      <div class="lbl">Breakdown Concurrent Count</div>
    </div>
    <div class="kpi">
      <div class="val">{SUMMARY['a100_80gb_8sim_fps']} fps</div>
      <div class="lbl">A100 80GB @ 8 Concurrent</div>
    </div>
    <div class="kpi">
      <div class="val">{SUMMARY['total_test_cases'] - SUMMARY['failed_test_cases']}/{SUMMARY['total_test_cases']}</div>
      <div class="lbl">Test Cases Passed</div>
    </div>
  </div>

  <div class="section">
    <h2>Stress Dimension Results</h2>
    <table>
      <thead><tr>
        <th>Dimension</th><th>Score Bar</th><th>Score</th><th>Status</th><th>Note</th>
      </tr></thead>
      <tbody>{rows}</tbody>
    </table>
  </div>

  <div class="charts">
    <div>
      <div style="font-size:13px;color:#94a3b8;margin-bottom:8px">Stress Test Radar — 8 Dimensions</div>
      {radar}
    </div>
    <div>
      <div style="font-size:13px;color:#94a3b8;margin-bottom:8px">Performance Degradation Curve</div>
      {perf}
    </div>
  </div>

  <div class="footer">
    Last run: {SUMMARY['test_run_ts']} · OCI Robot Cloud Eval Infrastructure · sim_stress_tester v1.0
  </div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

if USE_FASTAPI:
    app = FastAPI(
        title="Sim Stress Tester",
        description="Stress tests simulation environments under extreme conditions",
        version="1.0.0",
    )

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return make_html()

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "sim_stress_tester", "port": 8310}

    @app.get("/api/summary")
    def api_summary():
        return SUMMARY

    @app.get("/api/stress-dims")
    def api_stress_dims():
        return STRESS_DIMS

    @app.get("/api/concurrent-perf")
    def api_concurrent_perf():
        return [
            {"concurrent": c[0], "a100_80gb_fps": c[1], "a100_40gb_fps": c[2]}
            for c in CONCURRENT_PERF
        ]

else:
    # Stdlib fallback
    import http.server
    import socketserver

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/health":
                body = b'{"status": "ok", "service": "sim_stress_tester", "port": 8310}'
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
            else:
                body = make_html().encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            pass


if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8310)
    else:
        with socketserver.TCPServer(("", 8310), Handler) as httpd:
            print("Sim Stress Tester (stdlib) running on port 8310")
            httpd.serve_forever()
