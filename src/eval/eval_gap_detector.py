"""eval_gap_detector.py — Sim-to-Real Gap Detector (port 8219)

FastAPI service that detects capability gaps between simulation evaluation
and real-world robot performance across tasks and time.
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False

import math
import random
from datetime import datetime

# ── Mock data ────────────────────────────────────────────────────────────────

TASKS = [
    {"name": "pick_place",  "sim": 91, "real": 82},
    {"name": "stack",       "sim": 85, "real": 71},
    {"name": "pour",        "sim": 78, "real": 51},   # worst: 27pp gap
    {"name": "wipe",        "sim": 74, "real": 58},
    {"name": "drawer",      "sim": 88, "real": 76},
    {"name": "button",      "sim": 93, "real": 86},
    {"name": "handover",    "sim": 80, "real": 63},
    {"name": "sort",        "sim": 86, "real": 74},
]

# Gap threshold for red highlight (percentage points)
GAP_THRESHOLD = 15

# Monthly gap trend Jan–Jun 2026 (average pp gap across all tasks)
MONTHLY_TREND = [
    {"month": "Jan", "gap": 18.2},
    {"month": "Feb", "gap": 16.8},
    {"month": "Mar", "gap": 15.1},
    {"month": "Apr", "gap": 13.7},
    {"month": "May", "gap": 12.3},
    {"month": "Jun", "gap": 11.0},  # projected
]

KEY_METRICS = {
    "worst_gap_task": "pour",
    "worst_gap_pp": 27,
    "avg_gap_pp": 18,
    "gap_closure_rate": 1.4,   # pp per month
    "real_demos_to_close": 420,
    "tasks_above_threshold": sum(1 for t in TASKS if (t["sim"] - t["real"]) > GAP_THRESHOLD),
}


# ── SVG generators ────────────────────────────────────────────────────────────

def _svg_grouped_bar() -> str:
    """Grouped bar chart: sim vs real success rate per task, gaps >15pp in red."""
    W, H = 760, 330
    PAD_L, PAD_R, PAD_T, PAD_B = 60, 20, 40, 70

    n = len(TASKS)
    group_w = (W - PAD_L - PAD_R) / n
    bar_w = group_w * 0.32

    def sx(i, slot):  # slot 0=sim, 1=real
        return PAD_L + i * group_w + group_w * 0.15 + slot * (bar_w + 4)

    def sy(pct):
        return PAD_T + (1 - pct / 100) * (H - PAD_T - PAD_B)

    def bar_h(pct):
        return pct / 100 * (H - PAD_T - PAD_B)

    # grid lines
    grid = ""
    for pct in [25, 50, 75, 100]:
        yy = sy(pct)
        grid += f'<line x1="{PAD_L}" y1="{yy:.1f}" x2="{W-PAD_R}" y2="{yy:.1f}" stroke="#1e3a5f" stroke-width="0.8"/>'
        grid += f'<text x="{PAD_L-6}" y="{yy+4:.1f}" text-anchor="end" font-size="11" fill="#94a3b8">{pct}%</text>'

    rects = ""
    xlabels = ""
    for i, task in enumerate(TASKS):
        gap = task["sim"] - task["real"]
        gap_color = "#C74634" if gap > GAP_THRESHOLD else "#38bdf8"

        # sim bar (always sky blue)
        bx_sim = sx(i, 0)
        by_sim = sy(task["sim"])
        bh_sim = bar_h(task["sim"])
        rects += f'<rect x="{bx_sim:.1f}" y="{by_sim:.1f}" width="{bar_w:.1f}" height="{bh_sim:.1f}" fill="#38bdf8" rx="2" opacity="0.85"/>'
        rects += f'<text x="{bx_sim + bar_w/2:.1f}" y="{by_sim-4:.1f}" text-anchor="middle" font-size="9" fill="#38bdf8">{task["sim"]}%</text>'

        # real bar (gap-sensitive color)
        bx_real = sx(i, 1)
        by_real = sy(task["real"])
        bh_real = bar_h(task["real"])
        rects += f'<rect x="{bx_real:.1f}" y="{by_real:.1f}" width="{bar_w:.1f}" height="{bh_real:.1f}" fill="{gap_color}" rx="2" opacity="0.85"/>'
        rects += f'<text x="{bx_real + bar_w/2:.1f}" y="{by_real-4:.1f}" text-anchor="middle" font-size="9" fill="{gap_color}">{task["real"]}%</text>'

        # gap annotation
        if gap > GAP_THRESHOLD:
            mid_x = (bx_sim + bx_real + bar_w) / 2
            rects += f'<text x="{mid_x:.1f}" y="{by_real + bh_real + 14:.1f}" text-anchor="middle" font-size="9" fill="#f87171">-{gap}pp</text>'

        # x-axis label
        cx = PAD_L + i * group_w + group_w / 2
        xlabels += f'<text x="{cx:.1f}" y="{H-PAD_B+16}" text-anchor="middle" font-size="10" fill="#94a3b8">{task["name"]}</text>'

    # legend
    legend = (
        f'<rect x="{PAD_L}" y="{H-14}" width="10" height="8" fill="#38bdf8"/>'
        f'<text x="{PAD_L+14}" y="{H-7}" font-size="11" fill="#cbd5e1">Sim</text>'
        f'<rect x="{PAD_L+55}" y="{H-14}" width="10" height="8" fill="#38bdf8" opacity="0.5"/>'
        f'<text x="{PAD_L+69}" y="{H-7}" font-size="11" fill="#cbd5e1">Real (gap ≤15pp)</text>'
        f'<rect x="{PAD_L+210}" y="{H-14}" width="10" height="8" fill="#C74634"/>'
        f'<text x="{PAD_L+224}" y="{H-7}" font-size="11" fill="#cbd5e1">Real (gap &gt;15pp)</text>'
    )

    svg = f"""<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:auto;">
  <rect width="{W}" height="{H}" fill="#0f172a" rx="8"/>
  <text x="{W//2}" y="22" text-anchor="middle" font-size="13" font-weight="bold" fill="#f1f5f9">Task Success Rate: Sim vs Real (8 Tasks)</text>
  {grid}
  {rects}
  {xlabels}
  {legend}
</svg>"""
    return svg


def _svg_gap_trend() -> str:
    """Line chart of average sim-real gap trend over Jan–Jun 2026."""
    W, H = 760, 290
    PAD_L, PAD_R, PAD_T, PAD_B = 65, 30, 40, 55

    months = MONTHLY_TREND
    n = len(months)
    max_gap = 22
    min_gap = 0

    def sx(i):
        return PAD_L + (i / (n - 1)) * (W - PAD_L - PAD_R)

    def sy(v):
        return PAD_T + (1 - (v - min_gap) / (max_gap - min_gap)) * (H - PAD_T - PAD_B)

    # grid
    grid = ""
    for tick in [0, 5, 10, 15, 20]:
        yy = sy(tick)
        grid += f'<line x1="{PAD_L}" y1="{yy:.1f}" x2="{W-PAD_R}" y2="{yy:.1f}" stroke="#1e3a5f" stroke-width="0.8"/>'
        grid += f'<text x="{PAD_L-8}" y="{yy+4:.1f}" text-anchor="end" font-size="11" fill="#94a3b8">{tick}pp</text>'

    # threshold line at 15pp
    thresh_y = sy(GAP_THRESHOLD)
    grid += f'<line x1="{PAD_L}" y1="{thresh_y:.1f}" x2="{W-PAD_R}" y2="{thresh_y:.1f}" stroke="#f59e0b" stroke-width="1.2" stroke-dasharray="5,4"/>'
    grid += f'<text x="{W-PAD_R-2}" y="{thresh_y-5:.1f}" text-anchor="end" font-size="10" fill="#f59e0b">15pp threshold</text>'

    # area fill
    pts_top = " ".join(f"{sx(i):.1f},{sy(m['gap']):.1f}" for i, m in enumerate(months))
    base_y = sy(0)
    pts_area = pts_top + f" {sx(n-1):.1f},{base_y:.1f} {sx(0):.1f},{base_y:.1f}"
    area = f'<polygon points="{pts_area}" fill="#38bdf8" opacity="0.08"/>'

    # line
    line_pts = " ".join(f"{sx(i):.1f},{sy(m['gap']):.1f}" for i, m in enumerate(months))
    main_line = f'<polyline points="{line_pts}" fill="none" stroke="#38bdf8" stroke-width="2.5"/>'

    # dots and labels
    dots = ""
    for i, m in enumerate(months):
        cx, cy = sx(i), sy(m["gap"])
        is_proj = m["month"] == "Jun"
        dot_color = "#94a3b8" if is_proj else "#38bdf8"
        dots += f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="5" fill="{dot_color}" stroke="#0f172a" stroke-width="2"/>'
        dots += f'<text x="{cx:.1f}" y="{cy-10:.1f}" text-anchor="middle" font-size="10" fill="{dot_color}">{m["gap"]}pp</text>'
        dots += f'<text x="{cx:.1f}" y="{H-PAD_B+16}" text-anchor="middle" font-size="11" fill="#94a3b8">{m["month"]}</text>'

    # DAgger annotation arrow area
    annot_x = sx(2)
    annot = (
        f'<text x="{annot_x:.1f}" y="{PAD_T+16}" text-anchor="middle" font-size="10" fill="#22c55e">DAgger + real demos applied</text>'
        f'<line x1="{annot_x:.1f}" y1="{PAD_T+20}" x2="{annot_x:.1f}" y2="{sy(15.1)-6:.1f}" stroke="#22c55e" stroke-width="1" stroke-dasharray="3,3"/>'
    )

    # Jun projected label
    jun_x = sx(n - 1)
    proj_label = f'<text x="{jun_x:.1f}" y="{H-PAD_B+30}" text-anchor="middle" font-size="9" fill="#64748b">projected</text>'

    svg = f"""<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:auto;">
  <rect width="{W}" height="{H}" fill="#0f172a" rx="8"/>
  <text x="{W//2}" y="22" text-anchor="middle" font-size="13" font-weight="bold" fill="#f1f5f9">Sim-to-Real Gap Trend — Jan to Jun 2026 (avg across tasks)</text>
  {grid}
  {area}
  {main_line}
  {dots}
  {annot}
  {proj_label}
</svg>"""
    return svg


# ── HTML dashboard ────────────────────────────────────────────────────────────

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Sim-to-Real Gap Detector</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; padding: 24px; }}
  h1 {{ color: #38bdf8; font-size: 1.6rem; margin-bottom: 6px; }}
  .subtitle {{ color: #64748b; font-size: 0.9rem; margin-bottom: 24px; }}
  .kpi-row {{ display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 28px; }}
  .kpi {{ background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 16px 22px; min-width: 170px; }}
  .kpi-label {{ color: #64748b; font-size: 0.78rem; text-transform: uppercase; letter-spacing: .06em; }}
  .kpi-value {{ color: #38bdf8; font-size: 1.9rem; font-weight: 700; margin-top: 4px; }}
  .kpi-value.red {{ color: #C74634; }}
  .kpi-value.green {{ color: #22c55e; }}
  .kpi-value.amber {{ color: #f59e0b; }}
  .card {{ background: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 20px; margin-bottom: 24px; }}
  .card h2 {{ font-size: 1rem; color: #94a3b8; margin-bottom: 16px; text-transform: uppercase; letter-spacing: .05em; }}
  .footer {{ color: #475569; font-size: 0.75rem; margin-top: 20px; }}
  .oracle-bar {{ height: 4px; background: linear-gradient(90deg, #C74634, #38bdf8); border-radius: 2px; margin-bottom: 22px; }}
  .badge {{ display: inline-block; background: #C74634; color: #fff; font-size: 0.72rem; padding: 2px 8px; border-radius: 12px; margin-left: 8px; vertical-align: middle; }}
</style>
</head>
<body>
<div class="oracle-bar"></div>
<h1>Sim-to-Real Gap Detector <span class="badge">{tasks_above} tasks above threshold</span></h1>
<p class="subtitle">Capability gap analysis between simulation evaluation and real-world robot performance · Port 8219</p>

<div class="kpi-row">
  <div class="kpi">
    <div class="kpi-label">Worst Gap Task</div>
    <div class="kpi-value red">{worst_task}</div>
  </div>
  <div class="kpi">
    <div class="kpi-label">Worst Gap</div>
    <div class="kpi-value red">{worst_gap}pp</div>
  </div>
  <div class="kpi">
    <div class="kpi-label">Avg Gap (Jan)</div>
    <div class="kpi-value amber">18pp</div>
  </div>
  <div class="kpi">
    <div class="kpi-label">Projected Gap (Jun)</div>
    <div class="kpi-value green">11pp</div>
  </div>
  <div class="kpi">
    <div class="kpi-label">Gap Closure Rate</div>
    <div class="kpi-value">1.4pp/mo</div>
  </div>
  <div class="kpi">
    <div class="kpi-label">Real Demos to Close</div>
    <div class="kpi-value">{real_demos}</div>
  </div>
</div>

<div class="card">
  <h2>Task Success Rate: Sim vs Real — Red = Gap &gt;15pp</h2>
  {chart_bars}
</div>

<div class="card">
  <h2>Sim-to-Real Gap Trend (Jan–Jun 2026)</h2>
  {chart_trend}
</div>

<div class="footer">OCI Robot Cloud · Sim-to-Real Gap Detector · {ts} · Powered by DAgger + GR00T N1.6 fine-tuning</div>
</body>
</html>
"""


def build_html() -> str:
    m = KEY_METRICS
    return DASHBOARD_HTML.format(
        tasks_above=m["tasks_above_threshold"],
        worst_task=m["worst_gap_task"],
        worst_gap=m["worst_gap_pp"],
        real_demos=m["real_demos_to_close"],
        chart_bars=_svg_grouped_bar(),
        chart_trend=_svg_gap_trend(),
        ts=datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
    )


# ── FastAPI app (with stdlib fallback) ───────────────────────────────────────

if FASTAPI_AVAILABLE:
    app = FastAPI(
        title="Eval Gap Detector",
        description="Sim-to-real capability gap detection service — port 8219",
        version="1.0.0",
    )

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return HTMLResponse(content=build_html())

    @app.get("/api/gaps")
    async def gap_data():
        return {
            "tasks": TASKS,
            "gap_threshold_pp": GAP_THRESHOLD,
            "monthly_trend": MONTHLY_TREND,
            "key_metrics": KEY_METRICS,
        }

    @app.get("/api/gaps/{task_name}")
    async def task_gap(task_name: str):
        for t in TASKS:
            if t["name"] == task_name:
                gap = t["sim"] - t["real"]
                return {**t, "gap_pp": gap, "above_threshold": gap > GAP_THRESHOLD}
        return {"error": f"Task '{task_name}' not found"}

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "eval_gap_detector", "port": 8219}

else:
    import http.server
    import socketserver

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            body = build_html().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            pass


if __name__ == "__main__":
    if FASTAPI_AVAILABLE:
        uvicorn.run(app, host="0.0.0.0", port=8219)
    else:
        with socketserver.TCPServer(("", 8219), _Handler) as httpd:
            print("Serving on http://0.0.0.0:8219 (stdlib fallback)")
            httpd.serve_forever()
