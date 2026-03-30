"""Sim World Generator — OCI Robot Cloud (port 8668)

Generates diverse simulation worlds for robot training.
Dark theme dashboard with SVG visualizations.
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

from http.server import HTTPServer, BaseHTTPRequestHandler
import json

# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------

def svg_scene_composition_matrix() -> str:
    """8 object-type columns × 6 arrangement rows; cells are colored rectangles."""
    cols = 8
    rows = 6
    cell_w, cell_h = 52, 36
    pad_x, pad_y = 60, 50
    total_w = pad_x + cols * cell_w + 20
    total_h = pad_y + rows * cell_h + 30

    col_labels = ["Cube", "Sphere", "Cylinder", "Tool", "Container", "Organic", "Flat", "Stack"]
    row_labels = ["Sparse", "Grid", "Cluster", "Random", "Layered", "Mixed"]

    # Color palette per object type (Oracle red variants + blues + greens)
    col_colors = [
        ["#C74634", "#e05a46", "#a33829", "#d4614d", "#f07060", "#b84030"],
        ["#38bdf8", "#0ea5e9", "#7dd3fc", "#0284c7", "#bae6fd", "#38bdf8"],
        ["#34d399", "#10b981", "#6ee7b7", "#059669", "#a7f3d0", "#34d399"],
        ["#f59e0b", "#d97706", "#fcd34d", "#b45309", "#fde68a", "#f59e0b"],
        ["#a78bfa", "#8b5cf6", "#c4b5fd", "#7c3aed", "#ddd6fe", "#a78bfa"],
        ["#fb7185", "#f43f5e", "#fda4af", "#e11d48", "#ffe4e6", "#fb7185"],
        ["#67e8f9", "#22d3ee", "#a5f3fc", "#0891b2", "#cffafe", "#67e8f9"],
        ["#86efac", "#4ade80", "#bbf7d0", "#16a34a", "#dcfce7", "#86efac"],
    ]

    svg_parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{total_w}" height="{total_h}">',
        f'<rect width="{total_w}" height="{total_h}" fill="#1e293b" rx="8"/>',
        # title
        f'<text x="{total_w//2}" y="22" fill="#94a3b8" font-size="11" font-family="monospace" text-anchor="middle">Scene Composition Matrix</text>',
    ]

    # Column labels
    for ci, label in enumerate(col_labels):
        x = pad_x + ci * cell_w + cell_w // 2
        svg_parts.append(
            f'<text x="{x}" y="42" fill="#64748b" font-size="8" font-family="monospace" text-anchor="middle">{label}</text>'
        )

    # Row labels + cells
    for ri, row_label in enumerate(row_labels):
        y = pad_y + ri * cell_h
        svg_parts.append(
            f'<text x="{pad_x - 4}" y="{y + cell_h//2 + 4}" fill="#64748b" font-size="8" font-family="monospace" text-anchor="end">{row_label}</text>'
        )
        for ci in range(cols):
            x = pad_x + ci * cell_w
            color = col_colors[ci][ri]
            opacity = 0.5 + 0.5 * ((ri * cols + ci) % 7) / 6
            svg_parts.append(
                f'<rect x="{x + 2}" y="{y + 2}" width="{cell_w - 4}" height="{cell_h - 4}" '
                f'fill="{color}" opacity="{opacity:.2f}" rx="3"/>'
            )

    svg_parts.append('</svg>')
    return ''.join(svg_parts)


def svg_diversity_histogram() -> str:
    """Diversity score histogram (x=0-1, 10 bins, mean=0.84 line, slight left skew)."""
    # Bin counts for a left-skewed distribution peaking near 0.8-0.9
    bins = [2, 4, 8, 15, 28, 52, 98, 145, 120, 68]
    bin_max = max(bins)
    w, h = 420, 200
    pad_l, pad_r, pad_t, pad_b = 45, 20, 30, 40
    chart_w = w - pad_l - pad_r
    chart_h = h - pad_t - pad_b
    bar_w = chart_w / len(bins)
    mean_x = pad_l + int(0.84 * chart_w)

    svg_parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}">',
        f'<rect width="{w}" height="{h}" fill="#1e293b" rx="8"/>',
        f'<text x="{w//2}" y="20" fill="#94a3b8" font-size="11" font-family="monospace" text-anchor="middle">World Diversity Score Distribution</text>',
    ]

    # Bars
    for i, count in enumerate(bins):
        bar_h = int(count / bin_max * chart_h)
        x = pad_l + i * bar_w
        y = pad_t + chart_h - bar_h
        svg_parts.append(
            f'<rect x="{x + 1:.1f}" y="{y}" width="{bar_w - 2:.1f}" height="{bar_h}" fill="#38bdf8" opacity="0.75" rx="2"/>'
        )

    # Mean line
    svg_parts.append(
        f'<line x1="{mean_x}" y1="{pad_t}" x2="{mean_x}" y2="{pad_t + chart_h}" stroke="#C74634" stroke-width="2" stroke-dasharray="4,3"/>'
    )
    svg_parts.append(
        f'<text x="{mean_x + 4}" y="{pad_t + 14}" fill="#C74634" font-size="9" font-family="monospace">mean=0.84</text>'
    )

    # X-axis labels
    for i in range(11):
        x = pad_l + i * (chart_w / 10)
        label = f"{i/10:.1f}"
        svg_parts.append(
            f'<text x="{x:.1f}" y="{pad_t + chart_h + 14}" fill="#64748b" font-size="8" font-family="monospace" text-anchor="middle">{label}</text>'
        )

    # Y-axis
    for tick in [0, 50, 100, 145]:
        y = pad_t + chart_h - int(tick / bin_max * chart_h)
        svg_parts.append(
            f'<text x="{pad_l - 4}" y="{y + 3}" fill="#64748b" font-size="8" font-family="monospace" text-anchor="end">{tick}</text>'
        )
        svg_parts.append(
            f'<line x1="{pad_l}" y1="{y}" x2="{pad_l + chart_w}" y2="{y}" stroke="#334155" stroke-width="0.5"/>'
        )

    # Axis labels
    svg_parts.append(f'<text x="{w//2}" y="{h - 4}" fill="#64748b" font-size="9" font-family="monospace" text-anchor="middle">Diversity Score</text>')
    svg_parts.append('</svg>')
    return ''.join(svg_parts)


def svg_throughput_gauge() -> str:
    """Arc gauge: current 847/hr (85%), target 1000/hr (100%), needle at 85%."""
    import math
    w, h = 300, 200
    cx, cy, r = 150, 155, 110
    start_angle = 210  # degrees (clockwise from 3 o'clock)
    sweep = 240  # total arc degrees

    def polar(angle_deg, radius):
        a = math.radians(angle_deg)
        return cx + radius * math.cos(a), cy - radius * math.sin(a)

    def arc_path(pct, stroke_color, stroke_w, r_arc):
        angle = start_angle - pct * sweep
        x1, y1 = polar(start_angle, r_arc)
        x2, y2 = polar(angle, r_arc)
        large = 1 if pct * sweep > 180 else 0
        return (
            f'<path d="M {x1:.2f} {y1:.2f} A {r_arc} {r_arc} 0 {large} 0 {x2:.2f} {y2:.2f}" '
            f'fill="none" stroke="{stroke_color}" stroke-width="{stroke_w}" stroke-linecap="round"/>'
        )

    svg_parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}">',
        f'<rect width="{w}" height="{h}" fill="#1e293b" rx="8"/>',
        f'<text x="{w//2}" y="22" fill="#94a3b8" font-size="11" font-family="monospace" text-anchor="middle">Generation Throughput</text>',
        # background arc
        arc_path(1.0, '#334155', 18, r),
        # filled arc to 85%
        arc_path(0.85, '#38bdf8', 18, r),
        # target marker at 100%
    ]

    # Needle at 85%
    needle_angle = start_angle - 0.85 * sweep
    nx, ny = polar(needle_angle, r - 20)
    svg_parts.append(
        f'<line x1="{cx}" y1="{cy}" x2="{nx:.2f}" y2="{ny:.2f}" stroke="#C74634" stroke-width="3" stroke-linecap="round"/>'
    )
    svg_parts.append(f'<circle cx="{cx}" cy="{cy}" r="6" fill="#C74634"/>')

    # Labels
    svg_parts.append(f'<text x="{cx}" y="{cy - 25}" fill="#38bdf8" font-size="22" font-family="monospace" text-anchor="middle" font-weight="bold">847</text>')
    svg_parts.append(f'<text x="{cx}" y="{cy - 8}" fill="#64748b" font-size="10" font-family="monospace" text-anchor="middle">worlds / hr</text>')
    svg_parts.append(f'<text x="{cx}" y="{cy + 10}" fill="#94a3b8" font-size="9" font-family="monospace" text-anchor="middle">Target: 1000/hr</text>')

    # Min / max labels
    x0, y0 = polar(start_angle, r + 16)
    x1, y1 = polar(start_angle - sweep, r + 16)
    svg_parts.append(f'<text x="{x0:.1f}" y="{y0:.1f}" fill="#64748b" font-size="8" font-family="monospace" text-anchor="middle">0</text>')
    svg_parts.append(f'<text x="{x1:.1f}" y="{y1:.1f}" fill="#64748b" font-size="8" font-family="monospace" text-anchor="middle">1000</text>')

    svg_parts.append('</svg>')
    return ''.join(svg_parts)


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def build_html() -> str:
    matrix_svg = svg_scene_composition_matrix()
    hist_svg = svg_diversity_histogram()
    gauge_svg = svg_throughput_gauge()

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Sim World Generator — OCI Robot Cloud</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #0f172a; color: #e2e8f0; font-family: 'Courier New', monospace; }}
  header {{ background: #1e293b; border-bottom: 2px solid #C74634; padding: 16px 32px; display: flex; align-items: center; gap: 16px; }}
  header h1 {{ font-size: 1.3rem; color: #f8fafc; }}
  header .badge {{ background: #C74634; color: #fff; font-size: 0.7rem; padding: 3px 10px; border-radius: 12px; }}
  header .port {{ color: #38bdf8; font-size: 0.85rem; }}
  .metrics {{ display: flex; flex-wrap: wrap; gap: 12px; padding: 20px 32px; }}
  .metric-card {{ background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 14px 20px; min-width: 150px; }}
  .metric-card .val {{ font-size: 1.6rem; font-weight: bold; color: #38bdf8; }}
  .metric-card .lbl {{ font-size: 0.72rem; color: #64748b; margin-top: 4px; }}
  .metric-card .val.red {{ color: #C74634; }}
  .metric-card .val.green {{ color: #34d399; }}
  .charts {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(360px, 1fr)); gap: 20px; padding: 0 32px 32px; }}
  .chart-box {{ background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 12px; }}
  .chart-box h2 {{ font-size: 0.85rem; color: #94a3b8; margin-bottom: 10px; }}
  .chart-box svg {{ width: 100%; height: auto; display: block; }}
  .edge-cases {{ display: flex; gap: 8px; padding: 4px 0; }}
  .edge-tag {{ padding: 3px 10px; border-radius: 10px; font-size: 0.75rem; }}
  footer {{ text-align: center; padding: 12px; color: #334155; font-size: 0.7rem; border-top: 1px solid #1e293b; }}
</style>
</head>
<body>
<header>
  <div>
    <h1>Sim World Generator</h1>
    <span class="port">:8668 — Simulation Service</span>
  </div>
  <span class="badge">OCI Robot Cloud</span>
</header>

<div class="metrics">
  <div class="metric-card"><div class="val">8.4</div><div class="lbl">Avg Objects / Scene</div></div>
  <div class="metric-card"><div class="val">24</div><div class="lbl">Unique Materials</div></div>
  <div class="metric-card"><div class="val red">847</div><div class="lbl">Worlds / Hour</div></div>
  <div class="metric-card"><div class="val green">0.84</div><div class="lbl">Diversity Score</div></div>
  <div class="metric-card"><div class="val">-0.62</div><div class="lbl">Diversity ↔ Sim2Real Gap (r)</div></div>
  <div class="metric-card">
    <div class="lbl" style="margin-bottom:6px">Edge Cases</div>
    <div class="edge-cases">
      <span class="edge-tag" style="background:#1e3a5f;color:#38bdf8">2% Empty</span>
      <span class="edge-tag" style="background:#3b1f2b;color:#f87171">8% Cluttered</span>
    </div>
  </div>
</div>

<div class="charts">
  <div class="chart-box">
    <h2>Scene Composition Matrix (Object Types × Arrangements)</h2>
    {matrix_svg}
  </div>
  <div class="chart-box">
    <h2>World Diversity Score Histogram</h2>
    {hist_svg}
  </div>
  <div class="chart-box">
    <h2>Generation Throughput Gauge</h2>
    {gauge_svg}
  </div>
</div>

<footer>OCI Robot Cloud · Sim World Generator · Port 8668</footer>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

if USE_FASTAPI:
    app = FastAPI(
        title="Sim World Generator",
        description="Generates diverse simulation worlds for robot training.",
        version="1.0.0",
    )

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return HTMLResponse(content=build_html())

    @app.get("/health")
    def health():
        return JSONResponse({"status": "ok", "service": "sim_world_generator", "port": 8668})

    @app.get("/metrics")
    def metrics():
        return JSONResponse({
            "avg_objects_per_scene": 8.4,
            "unique_materials": 24,
            "worlds_per_hour": 847,
            "diversity_score": 0.84,
            "edge_cases": {"empty_pct": 2, "cluttered_pct": 8},
            "diversity_sim2real_correlation": -0.62,
        })

else:
    # Stdlib fallback
    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/health":
                body = json.dumps({"status": "ok", "service": "sim_world_generator", "port": 8668}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
            else:
                body = build_html().encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):  # suppress default logging
            pass


if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8668)
    else:
        print("FastAPI not found — starting stdlib HTTP server on port 8668")
        HTTPServer(("0.0.0.0", 8668), _Handler).serve_forever()
