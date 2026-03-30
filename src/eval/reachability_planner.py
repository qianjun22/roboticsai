"""OCI Robot Cloud — Reachability Planner  (port 8670)
Workspace reachability analysis and task coverage planning.
"""
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

import math
import random

PORT = 8670

# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------

def build_workspace_svg() -> str:
    """10×10 grid top-down workspace reachability map (1 m × 1 m)."""
    cell = 40          # px per cell
    n    = 10
    size = cell * n    # 400
    cx   = size // 2  # robot base centre
    cy   = size // 2
    reach_px = int(0.85 * size)   # 850 mm reach ≈ 85 % of 1 m

    random.seed(42)
    rows = []
    for r in range(n):
        for c in range(n):
            # distance from centre in normalised units
            dx = (c + 0.5) * cell - cx
            dy = (r + 0.5) * cell - cy
            dist = math.sqrt(dx*dx + dy*dy)
            ratio = dist / (reach_px / 2)
            if ratio < 0.75:
                fill = "#22c55e"   # green  — fully reachable
            elif ratio < 1.0:
                fill = "#eab308"   # yellow — partial
            else:
                fill = "#ef4444"   # red    — unreachable
            x, y = c * cell, r * cell
            rows.append(
                f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" '
                f'fill="{fill}" stroke="#1e293b" stroke-width="1" opacity="0.85"/>'
            )

    # reach circle
    circle = (
        f'<circle cx="{cx}" cy="{cy}" r="{reach_px//2}" '
        f'fill="none" stroke="#38bdf8" stroke-width="2" stroke-dasharray="6 3"/>'
    )
    # robot base marker
    base = (
        f'<circle cx="{cx}" cy="{cy}" r="8" fill="#C74634"/>'
        f'<text x="{cx}" y="{cy-14}" text-anchor="middle" '
        f'fill="#f1f5f9" font-size="11" font-family="monospace">base</text>'
    )
    # legend
    legend_items = [
        ("#22c55e", "Reachable"),
        ("#eab308", "Partial"),
        ("#ef4444", "Unreachable"),
    ]
    legend = ""
    for i, (col, label) in enumerate(legend_items):
        lx, ly = size + 16, 20 + i * 22
        legend += (
            f'<rect x="{lx}" y="{ly}" width="14" height="14" fill="{col}" rx="2"/>'
            f'<text x="{lx+20}" y="{ly+11}" fill="#94a3b8" font-size="11" '
            f'font-family="monospace">{label}</text>'
        )

    total_w = size + 120
    return (
        f'<svg viewBox="0 0 {total_w} {size}" xmlns="http://www.w3.org/2000/svg" '
        f'style="background:#1e293b;border-radius:8px">'
        + "".join(rows) + circle + base + legend +
        "</svg>"
    )


def build_task_coverage_svg() -> str:
    """Horizontal bar chart — task coverage %."""
    tasks = [
        ("cube_lift",  94),
        ("pick_place", 89),
        ("stack",      82),
        ("pour",       76),
        ("insert",     71),
        ("high_shelf", 41),   # bottleneck — highlighted
        ("tool_use",   68),
    ]
    bar_h   = 28
    gap     = 14
    label_w = 110
    bar_max = 300
    threshold = 50
    pad_top = 30
    total_h = pad_top + len(tasks) * (bar_h + gap) + 30
    total_w = label_w + bar_max + 80

    parts = [
        f'<text x="{total_w//2}" y="20" text-anchor="middle" fill="#C74634" '
        f'font-size="13" font-weight="bold" font-family="monospace">Task Coverage (%)</text>',
        # threshold line
        f'<line x1="{label_w + int(threshold/100*bar_max)}" y1="{pad_top}" '
        f'x1="{label_w + int(threshold/100*bar_max)}" '
        f'x2="{label_w + int(threshold/100*bar_max)}" y2="{total_h-20}" '
        f'stroke="#f59e0b" stroke-width="1" stroke-dasharray="4 3"/>',
    ]
    # fix: proper line element
    tx = label_w + int(threshold/100*bar_max)
    parts[-1] = (
        f'<line x1="{tx}" y1="{pad_top}" x2="{tx}" y2="{total_h-20}" '
        f'stroke="#f59e0b" stroke-width="1" stroke-dasharray="4 3"/>'
        f'<text x="{tx+3}" y="{pad_top+10}" fill="#f59e0b" font-size="9" '
        f'font-family="monospace">threshold</text>'
    )

    for i, (name, pct) in enumerate(tasks):
        y   = pad_top + i * (bar_h + gap)
        bw  = int(pct / 100 * bar_max)
        highlight = name == "high_shelf"
        bar_col  = "#C74634" if highlight else "#38bdf8"
        label_col = "#fca5a5" if highlight else "#e2e8f0"
        parts.append(
            f'<text x="{label_w-6}" y="{y+bar_h//2+4}" text-anchor="end" '
            f'fill="{label_col}" font-size="11" font-family="monospace">{name}</text>'
            f'<rect x="{label_w}" y="{y}" width="{bw}" height="{bar_h}" '
            f'fill="{bar_col}" rx="3" opacity="0.9"/>'
            f'<text x="{label_w+bw+5}" y="{y+bar_h//2+4}" fill="{label_col}" '
            f'font-size="11" font-family="monospace">{pct}%</text>'
        )

    return (
        f'<svg viewBox="0 0 {total_w} {total_h}" xmlns="http://www.w3.org/2000/svg" '
        f'style="background:#1e293b;border-radius:8px">'
        + "".join(parts) + "</svg>"
    )


def build_scatter_svg() -> str:
    """Reachability % vs SR scatter — 10 pts per task, trend line r=0.88."""
    random.seed(7)
    task_meta = [
        ("cube_lift",  94, 0.78, "#22c55e"),
        ("pick_place", 89, 0.71, "#38bdf8"),
        ("stack",      82, 0.64, "#a78bfa"),
        ("pour",       76, 0.57, "#fb923c"),
        ("insert",     71, 0.51, "#f472b6"),
        ("high_shelf", 41, 0.22, "#ef4444"),
        ("tool_use",   68, 0.49, "#eab308"),
    ]
    W, H = 460, 320
    pad = {"l": 55, "r": 20, "t": 30, "b": 45}
    pw = W - pad["l"] - pad["r"]
    ph = H - pad["t"]  - pad["b"]

    def tx(v): return pad["l"] + v * pw          # v in [0,1]
    def ty(v): return pad["t"] + (1 - v) * ph    # v in [0,1]

    parts = [
        # axes
        f'<line x1="{pad["l"]}" y1="{pad["t"]}" x2="{pad["l"]}" y2="{pad["t"]+ph}" stroke="#475569" stroke-width="1"/>',
        f'<line x1="{pad["l"]}" y1="{pad["t"]+ph}" x2="{pad["l"]+pw}" y2="{pad["t"]+ph}" stroke="#475569" stroke-width="1"/>',
        # axis labels
        f'<text x="{W//2}" y="{H-5}" text-anchor="middle" fill="#94a3b8" font-size="11" font-family="monospace">Reachability (%)</text>',
        f'<text x="12" y="{H//2}" text-anchor="middle" fill="#94a3b8" font-size="11" font-family="monospace" transform="rotate(-90,12,{H//2})">Success Rate</text>',
        f'<text x="{W//2}" y="20" text-anchor="middle" fill="#C74634" font-size="13" font-weight="bold" font-family="monospace">Reachability vs SR  (r=0.88)</text>',
    ]
    # grid lines
    for v in [0.25, 0.5, 0.75, 1.0]:
        gx = tx(v)
        gy = ty(v)
        parts.append(
            f'<line x1="{gx}" y1="{pad["t"]}" x2="{gx}" y2="{pad["t"]+ph}" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="3 3"/>'
            f'<line x1="{pad["l"]}" y1="{gy}" x2="{pad["l"]+pw}" y2="{gy}" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="3 3"/>'
            f'<text x="{gx}" y="{pad["t"]+ph+14}" text-anchor="middle" fill="#64748b" font-size="9" font-family="monospace">{int(v*100)}</text>'
            f'<text x="{pad["l"]-6}" y="{gy+4}" text-anchor="end" fill="#64748b" font-size="9" font-family="monospace">{v:.2f}</text>'
        )

    # trend line (r=0.88 ⟹ slope≈0.82, intercept≈0.0)
    x0, x1 = 0.3, 1.0
    y0 = 0.82 * x0 - 0.07
    y1 = 0.82 * x1 - 0.07
    parts.append(
        f'<line x1="{tx(x0):.1f}" y1="{ty(y0):.1f}" x2="{tx(x1):.1f}" y2="{ty(y1):.1f}" '
        f'stroke="#f59e0b" stroke-width="1.5" stroke-dasharray="6 3" opacity="0.7"/>'
    )

    # scatter points
    for task, base_r, base_sr, col in task_meta:
        for _ in range(10):
            rx  = base_r/100 + random.gauss(0, 0.03)
            sry = base_sr    + random.gauss(0, 0.04)
            rx  = max(0.1, min(1.0, rx))
            sry = max(0.0, min(1.0, sry))
            parts.append(
                f'<circle cx="{tx(rx):.1f}" cy="{ty(sry):.1f}" r="4" '
                f'fill="{col}" opacity="0.8"/>'
            )

    # legend
    for i, (task, *_, col) in enumerate(task_meta):
        lx = pad["l"] + (i % 4) * 110
        ly = H - 8 if i < 4 else H + 10  # single row is fine
        ly = pad["t"] + 14 + i * 16
        lx = W - 140
        if i < 7:
            parts.append(
                f'<circle cx="{lx}" cy="{ly}" r="4" fill="{col}"/>'
                f'<text x="{lx+10}" y="{ly+4}" fill="#94a3b8" font-size="9" font-family="monospace">{task}</text>'
            )

    return (
        f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" '
        f'style="background:#1e293b;border-radius:8px">'
        + "".join(parts) + "</svg>"
    )


# ---------------------------------------------------------------------------
# HTML page
# ---------------------------------------------------------------------------

HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Reachability Planner — OCI Robot Cloud</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{background:#0f172a;color:#e2e8f0;font-family:monospace;padding:24px}}
  h1{{color:#C74634;font-size:1.5rem;margin-bottom:4px}}
  .sub{{color:#64748b;font-size:.8rem;margin-bottom:24px}}
  .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(420px,1fr));gap:24px}}
  .card{{background:#1e293b;border-radius:10px;padding:20px;border:1px solid #334155}}
  .card h2{{color:#C74634;font-size:1rem;margin-bottom:14px}}
  .card svg{{width:100%;height:auto}}
  .metrics{{display:flex;flex-wrap:wrap;gap:12px;margin-top:20px}}
  .metric{{background:#0f172a;border:1px solid #334155;border-radius:8px;padding:12px 18px;min-width:160px}}
  .metric .val{{color:#38bdf8;font-size:1.4rem;font-weight:bold}}
  .metric .lbl{{color:#64748b;font-size:.75rem;margin-top:2px}}
  .warn .val{{color:#C74634}}
  .footer{{color:#475569;font-size:.7rem;margin-top:28px;text-align:center}}
</style>
</head>
<body>
<h1>Reachability Planner</h1>
<p class="sub">OCI Robot Cloud · Port {port} · Workspace reachability analysis &amp; task coverage</p>

<div class="grid">
  <div class="card">
    <h2>Workspace Reachability (Top-Down, 1m × 1m)</h2>
    {ws_svg}
  </div>
  <div class="card">
    <h2>Task Coverage</h2>
    {tc_svg}
  </div>
  <div class="card">
    <h2>Reachability vs Success Rate</h2>
    {sc_svg}
  </div>
</div>

<div class="metrics">
  <div class="metric warn">
    <div class="val">41%</div>
    <div class="lbl">high_shelf reachability (bottleneck)</div>
  </div>
  <div class="metric">
    <div class="val">67%</div>
    <div class="lbl">high_shelf w/ stretch posture</div>
  </div>
  <div class="metric">
    <div class="val">+0.11 pp</div>
    <div class="lbl">SR gain from base pose opt.</div>
  </div>
  <div class="metric">
    <div class="val">850 mm</div>
    <div class="lbl">arm reach radius</div>
  </div>
  <div class="metric">
    <div class="val">r = 0.88</div>
    <div class="lbl">reachability–SR correlation</div>
  </div>
</div>

<p class="footer">OCI Robot Cloud — Reachability Planner · port {port}</p>
</body>
</html>
"""


def make_html() -> str:
    return HTML.format(
        port=PORT,
        ws_svg=build_workspace_svg(),
        tc_svg=build_task_coverage_svg(),
        sc_svg=build_scatter_svg(),
    )


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

if USE_FASTAPI:
    app = FastAPI(title="Reachability Planner", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return HTMLResponse(content=make_html())

    @app.get("/health")
    def health():
        return JSONResponse({"status": "ok", "port": PORT})

    @app.get("/metrics")
    def metrics():
        return JSONResponse({
            "high_shelf_reachability_pct": 41,
            "high_shelf_stretch_pct": 67,
            "base_pose_sr_gain_pp": 0.11,
            "reach_radius_mm": 850,
            "reachability_sr_correlation": 0.88,
            "tasks": {
                "cube_lift":  {"reachability": 94, "sr": 0.78},
                "pick_place": {"reachability": 89, "sr": 0.71},
                "stack":      {"reachability": 82, "sr": 0.64},
                "pour":       {"reachability": 76, "sr": 0.57},
                "insert":     {"reachability": 71, "sr": 0.51},
                "high_shelf": {"reachability": 41, "sr": 0.22},
                "tool_use":   {"reachability": 68, "sr": 0.49},
            },
        })

else:
    # stdlib fallback
    from http.server import BaseHTTPRequestHandler, HTTPServer
    import json

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a): pass

        def do_GET(self):
            if self.path == "/health":
                body = json.dumps({"status": "ok", "port": PORT}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)
            else:
                body = make_html().encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(body)


if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        print(f"FastAPI not found — starting stdlib HTTPServer on port {PORT}")
        HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
