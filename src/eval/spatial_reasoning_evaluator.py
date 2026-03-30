"""Spatial Reasoning Evaluator — FastAPI service on port 8317.

Evaluates GR00T spatial reasoning capabilities for 3D manipulation understanding.
Compares GR00T_v2 vs BC_1000 baseline across 8 spatial challenges.
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    _FASTAPI = True
except ImportError:
    _FASTAPI = False

import math
import random
from datetime import datetime

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

random.seed(42)

SPATIAL_TASKS = [
    {"name": "place_left_of",       "groot_v2": 0.82, "bc_1000": 0.58, "n_episodes": 200},
    {"name": "place_right_of",      "groot_v2": 0.80, "bc_1000": 0.55, "n_episodes": 200},
    {"name": "stack_on_top",        "groot_v2": 0.91, "bc_1000": 0.62, "n_episodes": 200},
    {"name": "insert_behind",       "groot_v2": 0.74, "bc_1000": 0.47, "n_episodes": 200},
    {"name": "align_with_edge",     "groot_v2": 0.76, "bc_1000": 0.51, "n_episodes": 200},
    {"name": "spatial_sequence_3step", "groot_v2": 0.68, "bc_1000": 0.44, "n_episodes": 150},
    {"name": "mirror_placement",    "groot_v2": 0.70, "bc_1000": 0.48, "n_episodes": 150},
    {"name": "depth_ordering",      "groot_v2": 0.52, "bc_1000": 0.33, "n_episodes": 150},
]

SPATIAL_COMPOSITE_GROOT = round(sum(t["groot_v2"] for t in SPATIAL_TASKS) / len(SPATIAL_TASKS), 3)
SPATIAL_COMPOSITE_BC    = round(sum(t["bc_1000"]  for t in SPATIAL_TASKS) / len(SPATIAL_TASKS), 3)
Y_BIAS_MM = -8.0  # systematic bias: always short on y-axis (camera calibration)

# Generate placement error scatter (200 episodes, top-down view: x, y)
def _gen_placements():
    """Generate final object positions vs target — with systematic y-axis bias."""
    random.seed(7)
    points = []
    for _ in range(200):
        ex = random.gauss(0.0, 12.0)   # x error in mm
        ey = random.gauss(Y_BIAS_MM, 9.0)  # y error: biased -8mm
        ez = random.gauss(0.0, 5.0)   # z error
        points.append({"ex": round(ex, 2), "ey": round(ey, 2), "ez": round(ez, 2)})
    return points

PLACEMENT_ERRORS = _gen_placements()

KEY_METRICS = {
    "spatial_composite_groot_v2": SPATIAL_COMPOSITE_GROOT,
    "spatial_composite_bc_1000": SPATIAL_COMPOSITE_BC,
    "improvement_over_bc": round(SPATIAL_COMPOSITE_GROOT - SPATIAL_COMPOSITE_BC, 3),
    "improvement_pct": round((SPATIAL_COMPOSITE_GROOT - SPATIAL_COMPOSITE_BC) / SPATIAL_COMPOSITE_BC * 100, 1),
    "hardest_task": "depth_ordering",
    "easiest_task": "stack_on_top",
    "systematic_y_bias_mm": Y_BIAS_MM,
    "bias_cause": "camera calibration offset",
    "total_episodes_evaluated": sum(t["n_episodes"] for t in SPATIAL_TASKS),
}

# ---------------------------------------------------------------------------
# SVG generators
# ---------------------------------------------------------------------------

def svg_task_success_bars() -> str:
    """Bar chart comparing GR00T_v2 vs BC_1000 across 8 spatial challenges."""
    n = len(SPATIAL_TASKS)
    W, H = 780, 340
    margin = {"l": 170, "r": 30, "t": 40, "b": 50}
    inner_w = W - margin["l"] - margin["r"]
    inner_h = H - margin["t"] - margin["b"]

    bar_group_h = inner_h / n
    bar_h = bar_group_h * 0.32
    gap = bar_group_h * 0.08

    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" style="background:#1e293b;border-radius:8px">')

    # Y-axis gridlines at 0, 0.25, 0.5, 0.75, 1.0
    for tick in [0.0, 0.25, 0.50, 0.75, 1.0]:
        x = margin["l"] + int(tick * inner_w)
        lines.append(f'<line x1="{x}" y1="{margin["t"]}" x2="{x}" y2="{margin["t"]+inner_h}" stroke="#334155" stroke-width="1" stroke-dasharray="4,3"/>')
        lines.append(f'<text x="{x}" y="{margin["t"]+inner_h+14}" text-anchor="middle" fill="#64748b" font-size="10" font-family="sans-serif">{int(tick*100)}%</text>')

    # Bars
    for i, task in enumerate(SPATIAL_TASKS):
        base_y = margin["t"] + i * bar_group_h

        # BC bar (bottom of pair)
        bc_w = int(task["bc_1000"] * inner_w)
        y_bc = base_y + bar_group_h * 0.5 + gap
        lines.append(f'<rect x="{margin["l"]}" y="{y_bc:.1f}" width="{bc_w}" height="{bar_h:.1f}" fill="#64748b" rx="2"/>')
        lines.append(f'<text x="{margin["l"]+bc_w+4}" y="{y_bc+bar_h*0.75:.1f}" fill="#94a3b8" font-size="10" font-family="sans-serif">{task["bc_1000"]:.2f}</text>')

        # GR00T bar (top of pair)
        gr_w = int(task["groot_v2"] * inner_w)
        y_gr = base_y + bar_group_h * 0.5 - bar_h - gap
        bar_color = "#C74634" if task["groot_v2"] < 0.60 else "#ef4444" if task["groot_v2"] < 0.70 else "#C74634"
        lines.append(f'<rect x="{margin["l"]}" y="{y_gr:.1f}" width="{gr_w}" height="{bar_h:.1f}" fill="{bar_color}" rx="2"/>')
        lines.append(f'<text x="{margin["l"]+gr_w+4}" y="{y_gr+bar_h*0.75:.1f}" fill="#fca5a5" font-size="10" font-family="sans-serif">{task["groot_v2"]:.2f}</text>')

        # Task name label
        label = task["name"].replace("_", " ")
        label_y = base_y + bar_group_h * 0.5
        lines.append(f'<text x="{margin["l"]-8}" y="{label_y:.1f}" text-anchor="end" fill="#cbd5e1" font-size="11" font-family="monospace" dominant-baseline="middle">{label}</text>')

    # Axis line
    lines.append(f'<line x1="{margin["l"]}" y1="{margin["t"]}" x2="{margin["l"]}" y2="{margin["t"]+inner_h}" stroke="#475569" stroke-width="2"/>')

    # Legend
    lines.append(f'<rect x="{W-170}" y="{margin["t"]}" width="12" height="10" fill="#C74634" rx="2"/>')
    lines.append(f'<text x="{W-155}" y="{margin["t"]+9}" fill="#e2e8f0" font-size="11" font-family="sans-serif">GR00T_v2</text>')
    lines.append(f'<rect x="{W-170}" y="{margin["t"]+16}" width="12" height="10" fill="#64748b" rx="2"/>')
    lines.append(f'<text x="{W-155}" y="{margin["t"]+25}" fill="#e2e8f0" font-size="11" font-family="sans-serif">BC_1000</text>')

    lines.append(f'<text x="{W//2}" y="18" text-anchor="middle" fill="#e2e8f0" font-size="13" font-weight="bold" font-family="sans-serif">Spatial Task Success Rate — GR00T_v2 vs BC_1000</text>')
    lines.append('</svg>')
    return '\n'.join(lines)


def svg_3d_error_map() -> str:
    """Scatter of final placement errors: top-down (XY) and side-view (XZ)."""
    W, H = 780, 340
    panel_w = (W - 80) // 2
    panel_h = H - 60
    margin_top = 40
    scale = panel_w / 80  # ±40mm range

    def to_px_xy(ex, ey, ox, oy):
        px = ox + panel_w // 2 + ex * scale
        py = oy + panel_h // 2 - ey * scale
        return px, py

    def to_px_xz(ex, ez, ox, oy):
        px = ox + panel_w // 2 + ex * scale
        pz = oy + panel_h // 2 - ez * scale * 2
        return px, pz

    ox1, oy1 = 30, margin_top
    ox2, oy2 = ox1 + panel_w + 20, margin_top

    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" style="background:#1e293b;border-radius:8px">')

    for ox, oy, label in [(ox1, oy1, 'Top-Down View (XY)'), (ox2, oy2, 'Side View (XZ)')]:
        # Panel border
        lines.append(f'<rect x="{ox}" y="{oy}" width="{panel_w}" height="{panel_h}" fill="#0f172a" rx="4" stroke="#334155" stroke-width="1"/>')
        # Crosshairs (target)
        cx_p = ox + panel_w // 2
        cy_p = oy + panel_h // 2
        lines.append(f'<line x1="{cx_p}" y1="{oy+8}" x2="{cx_p}" y2="{oy+panel_h-8}" stroke="#334155" stroke-width="1" stroke-dasharray="3,3"/>')
        lines.append(f'<line x1="{ox+8}" y1="{cy_p}" x2="{ox+panel_w-8}" y2="{cy_p}" stroke="#334155" stroke-width="1" stroke-dasharray="3,3"/>')
        # Target bullseye
        for r in [8, 16, 24]:
            lines.append(f'<circle cx="{cx_p}" cy="{cy_p}" r="{r}" fill="none" stroke="#22c55e" stroke-width="1" opacity="0.4"/>')
        lines.append(f'<circle cx="{cx_p}" cy="{cy_p}" r="4" fill="#22c55e" opacity="0.9"/>')

        # Panel label
        lines.append(f'<text x="{ox+panel_w//2}" y="{oy-6}" text-anchor="middle" fill="#94a3b8" font-size="11" font-family="sans-serif">{label}</text>')

        # Axis labels
        lines.append(f'<text x="{ox+panel_w-4}" y="{cy_p+4}" text-anchor="end" fill="#475569" font-size="9" font-family="sans-serif">+X</text>')
        y_axis_label = '+Y' if 'XY' in label else '+Z'
        lines.append(f'<text x="{cx_p+4}" y="{oy+12}" fill="#475569" font-size="9" font-family="sans-serif">{y_axis_label}</text>')

    # Scatter points — XY top-down
    for p in PLACEMENT_ERRORS:
        px, py = to_px_xy(p["ex"], p["ey"], ox1, oy1)
        # Clamp
        if ox1 < px < ox1 + panel_w and oy1 < py < oy1 + panel_h:
            lines.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="2" fill="#38bdf8" opacity="0.35"/>')

    # Scatter points — XZ side view
    for p in PLACEMENT_ERRORS:
        px, pz = to_px_xz(p["ex"], p["ez"], ox2, oy2)
        if ox2 < px < ox2 + panel_w and oy2 < pz < oy2 + panel_h:
            lines.append(f'<circle cx="{px:.1f}" cy="{pz:.1f}" r="2" fill="#38bdf8" opacity="0.35"/>')

    # Systematic bias arrow (XY panel)
    bias_px = ox1 + panel_w // 2
    bias_center_y = oy1 + panel_h // 2 - Y_BIAS_MM * scale  # shifted up by -8mm = shifted down visually
    centroid_y = oy1 + panel_h // 2 - Y_BIAS_MM * scale
    # Arrow from target to centroid
    ty = oy1 + panel_h // 2
    lines.append(f'<line x1="{bias_px}" y1="{ty}" x2="{bias_px:.1f}" y2="{centroid_y:.1f}" stroke="#f59e0b" stroke-width="2" marker-end="url(#arrow)"/>')

    # Arrow marker def
    lines.insert(1, '<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L0,6 L8,3 z" fill="#f59e0b"/></marker></defs>')

    # Bias annotation
    lines.append(f'<text x="{bias_px+6}" y="{(ty+centroid_y)/2:.1f}" fill="#f59e0b" font-size="10" font-family="sans-serif">−8mm Y bias</text>')

    # Error ellipse (approximate) in XY
    ell_cx = ox1 + panel_w // 2
    ell_cy_center = oy1 + panel_h // 2 - Y_BIAS_MM * scale
    lines.append(f'<ellipse cx="{ell_cx:.1f}" cy="{ell_cy_center:.1f}" rx="{12*scale:.1f}" ry="{9*scale:.1f}" fill="none" stroke="#C74634" stroke-width="1.5" stroke-dasharray="5,3" opacity="0.7"/>')

    # Error ellipse in XZ
    ell_cx2 = ox2 + panel_w // 2
    lines.append(f'<ellipse cx="{ell_cx2:.1f}" cy="{oy2+panel_h//2:.1f}" rx="{12*scale:.1f}" ry="{5*scale:.1f}" fill="none" stroke="#C74634" stroke-width="1.5" stroke-dasharray="5,3" opacity="0.7"/>')

    # Legend
    lines.append(f'<circle cx="{W-180}" cy="{H-18}" r="4" fill="#38bdf8" opacity="0.8"/>')
    lines.append(f'<text x="{W-172}" y="{H-14}" fill="#94a3b8" font-size="10" font-family="sans-serif">placements (200 eps)</text>')
    lines.append(f'<circle cx="{W-180}" cy="{H-6}" r="4" fill="#22c55e"/>')
    lines.append(f'<text x="{W-172}" y="{H-2}" fill="#94a3b8" font-size="10" font-family="sans-serif">target</text>')

    lines.append(f'<text x="{W//2}" y="16" text-anchor="middle" fill="#e2e8f0" font-size="13" font-weight="bold" font-family="sans-serif">3D Placement Error Map (200 Episodes)</text>')
    lines.append('</svg>')
    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def build_html() -> str:
    bar_svg = svg_task_success_bars()
    error_svg = svg_3d_error_map()
    m = KEY_METRICS
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    def metric_card(title, value, sub="", color="#38bdf8"):
        return f"""
        <div style="background:#1e293b;border-radius:8px;padding:16px 20px;border-left:3px solid {color};">
          <div style="color:#94a3b8;font-size:12px;margin-bottom:4px;">{title}</div>
          <div style="color:{color};font-size:24px;font-weight:700;">{value}</div>
          {f'<div style="color:#64748b;font-size:11px;margin-top:4px;">{sub}</div>' if sub else ''}
        </div>"""

    cards = [
        metric_card("Spatial Composite (GR00T_v2)", f"{m['spatial_composite_groot_v2']:.2f}", "avg over 8 tasks", "#C74634"),
        metric_card("Spatial Composite (BC_1000)", f"{m['spatial_composite_bc_1000']:.2f}", "baseline", "#64748b"),
        metric_card("Improvement vs BC", f"+{m['improvement_pct']}%", f"+{m['improvement_over_bc']} absolute", "#22c55e"),
        metric_card("Hardest Task", m["hardest_task"], "depth_ordering (0.52)", "#f59e0b"),
        metric_card("Easiest Task", m["easiest_task"], "stack_on_top (0.91)", "#38bdf8"),
        metric_card("Y-Axis Bias", f"{m['systematic_y_bias_mm']}mm", m["bias_cause"], "#a78bfa"),
    ]

    task_rows = ""
    for t in SPATIAL_TASKS:
        delta = round(t["groot_v2"] - t["bc_1000"], 2)
        delta_color = "#22c55e" if delta > 0.25 else "#f59e0b" if delta > 0.15 else "#94a3b8"
        hardest = " *" if t["name"] == m["hardest_task"] else ""
        task_rows += f"""
        <tr>
          <td style="color:#cbd5e1;font-family:monospace;font-size:12px;">{t['name']}{hardest}</td>
          <td style="color:#C74634;font-weight:700;">{t['groot_v2']:.2f}</td>
          <td style="color:#64748b;">{t['bc_1000']:.2f}</td>
          <td style="color:{delta_color};font-weight:600;">+{delta:.2f}</td>
          <td style="color:#475569;">{t['n_episodes']}</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Spatial Reasoning Evaluator — OCI Robot Cloud</title>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',system-ui,sans-serif;padding:24px;}}
    h1{{color:#C74634;font-size:22px;font-weight:700;margin-bottom:4px;}}
    h2{{color:#38bdf8;font-size:15px;font-weight:600;margin:28px 0 12px;}}
    .subtitle{{color:#64748b;font-size:13px;margin-bottom:24px;}}
    .grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:12px;margin-bottom:28px;}}
    .svg-row{{display:flex;flex-wrap:wrap;gap:24px;margin-bottom:28px;align-items:flex-start;}}
    table{{width:100%;border-collapse:collapse;}}
    th{{color:#64748b;font-size:12px;text-align:left;padding:8px 12px;border-bottom:1px solid #1e293b;}}
    td{{padding:10px 12px;border-bottom:1px solid #1e293b22;font-size:13px;}}
    tr:hover td{{background:#1e293b44;}}
    .footer{{color:#334155;font-size:11px;margin-top:32px;text-align:center;}}
  </style>
</head>
<body>
  <h1>Spatial Reasoning Evaluator</h1>
  <div class="subtitle">OCI Robot Cloud — GR00T 3D Spatial Understanding &nbsp;·&nbsp; port 8317 &nbsp;·&nbsp; {now}</div>

  <div class="grid">{''.join(cards)}</div>

  <h2>Task Performance &amp; Placement Error Analysis</h2>
  <div class="svg-row">
    <div>{bar_svg}</div>
    <div>{error_svg}</div>
  </div>

  <h2>Per-Task Results</h2>
  <table>
    <thead><tr><th>Task</th><th>GR00T_v2</th><th>BC_1000</th><th>Delta</th><th>Episodes</th></tr></thead>
    <tbody>{task_rows}</tbody>
  </table>
  <div style="color:#64748b;font-size:11px;margin-top:8px;">* hardest task &nbsp;|&nbsp; systematic Y-axis bias: {m['systematic_y_bias_mm']}mm ({m['bias_cause']})</div>

  <div class="footer">OCI Robot Cloud &mdash; Spatial Reasoning Evaluator &mdash; cycle-64A</div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# App wiring
# ---------------------------------------------------------------------------

if _FASTAPI:
    app = FastAPI(
        title="Spatial Reasoning Evaluator",
        description="Evaluates GR00T spatial reasoning capabilities for 3D manipulation.",
        version="1.0.0",
    )

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return HTMLResponse(content=build_html())

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "spatial_reasoning_evaluator", "port": 8317}

    @app.get("/metrics")
    async def metrics():
        return KEY_METRICS

    @app.get("/tasks")
    async def tasks():
        return {"tasks": SPATIAL_TASKS}

    @app.get("/errors")
    async def errors():
        return {"placement_errors": PLACEMENT_ERRORS[:50], "total": len(PLACEMENT_ERRORS), "y_bias_mm": Y_BIAS_MM}

else:
    import http.server
    import socketserver

    class Handler(http.server.BaseHTTPRequestHandler):
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
    if _FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8317)
    else:
        print("FastAPI not available — using stdlib http.server on port 8317")
        with socketserver.TCPServer(("", 8317), Handler) as httpd:
            httpd.serve_forever()
