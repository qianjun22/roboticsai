"""
Training Run Comparator — OCI Robot Cloud
Port 8655 | cycle-149A
Dark theme FastAPI dashboard for comparing training runs.
stdlib only (math, random).
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

PORT = 8655

# ── Data ─────────────────────────────────────────────────────────────────────

AXES = ["SR", "Loss", "Latency", "Cost", "Smoothness", "Stability"]
N_AXES = len(AXES)

# Values 0–1 (higher = better for all axes after normalization)
RUNS = {
    "BC":            [0.30, 0.45, 0.60, 0.70, 0.50, 0.55],
    "dagger_r9":     [0.55, 0.62, 0.65, 0.58, 0.68, 0.72],
    "groot_v2":      [0.82, 0.80, 0.74, 0.65, 0.85, 0.83],
    "run10_partial": [0.61, 0.68, 0.71, 0.62, 0.73, 0.70],
}

RUN_COLORS = {
    "BC":            "#64748b",
    "dagger_r9":     "#38bdf8",
    "groot_v2":      "#C74634",
    "run10_partial": "#a78bfa",
}

# Parallel coordinates — 6 runs × 5 normalized dimensions
PARA_DIMS = ["SR", "Loss inv", "Latency inv", "Cost inv", "Smoothness"]
PARA_RUNS = {
    "BC":            [0.30, 0.45, 0.60, 0.70, 0.50],
    "dagger_r9":     [0.55, 0.62, 0.65, 0.58, 0.68],
    "groot_v2":      [0.82, 0.80, 0.74, 0.65, 0.85],
    "run10_partial": [0.61, 0.68, 0.71, 0.62, 0.73],
    "run7_ablate":   [0.42, 0.50, 0.55, 0.75, 0.45],
    "run3_early":    [0.25, 0.38, 0.52, 0.80, 0.38],
}
PARA_COLORS = {
    "BC":            "#64748b",
    "dagger_r9":     "#38bdf8",
    "groot_v2":      "#C74634",
    "run10_partial": "#a78bfa",
    "run7_ablate":   "#34d399",
    "run3_early":    "#fb923c",
}

# Pairwise p-value table (6 runs)
PVAL_RUNS = ["BC", "dagger_r9", "groot_v2", "run10", "run7", "run3"]
# lower triangle values (i > j): None = diagonal, "NS" = not significant, float = p
PVAL_MATRIX = [
    [None, None,  None,  None,  None,  None],
    [0.001, None, None,  None,  None,  None],
    [0.001, 0.033, None, None,  None,  None],
    [0.021, 0.142, 0.087, None, None,  None],
    [0.003, 0.071, 0.044, 0.312, None, None],
    [0.001, 0.008, 0.002, 0.195, 0.241, None],
]

# ── SVG generators ────────────────────────────────────────────────────────────

def svg_radar() -> str:
    W, H = 500, 380
    cx, cy, r = W // 2, H // 2 + 10, 130

    def axis_pt(i, frac):
        angle = math.pi / 2 + 2 * math.pi * i / N_AXES
        x = cx + frac * r * math.cos(angle)
        y = cy - frac * r * math.sin(angle)
        return x, y

    elems = []

    # Gridlines at 0.25, 0.5, 0.75, 1.0
    for frac in [0.25, 0.5, 0.75, 1.0]:
        pts = [f"{ax_x:.1f},{ay:.1f}" for i in range(N_AXES) for ax_x, ay in [axis_pt(i, frac)]]
        poly_pts = " ".join(pts)
        # Build full polygon
        corners = [axis_pt(i, frac) for i in range(N_AXES)]
        poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in corners)
        elems.append(f'<polygon points="{poly}" fill="none" stroke="#1e293b" stroke-width="1"/>')

    # Spoke lines
    for i in range(N_AXES):
        ox, oy = axis_pt(i, 0)
        ex, ey = axis_pt(i, 1)
        elems.append(f'<line x1="{ox:.1f}" y1="{oy:.1f}" x2="{ex:.1f}" y2="{ey:.1f}" stroke="#334155" stroke-width="1"/>')

    # Axis labels
    for i, ax_name in enumerate(AXES):
        lx, ly = axis_pt(i, 1.18)
        elems.append(f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="middle" dominant-baseline="middle" fill="#94a3b8" font-size="11">{ax_name}</text>')

    # Run polygons
    for run_name, vals in RUNS.items():
        color = RUN_COLORS[run_name]
        corners = [axis_pt(i, vals[i]) for i in range(N_AXES)]
        poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in corners)
        opacity = "0.55" if run_name == "groot_v2" else "0.30"
        sw = "2.5" if run_name == "groot_v2" else "1.5"
        elems.append(f'<polygon points="{poly}" fill="{color}" fill-opacity="{opacity}" stroke="{color}" stroke-width="{sw}"/>')

    # Legend
    leg_x, leg_y = 12, 12
    for run_name, color in RUN_COLORS.items():
        elems.append(f'<rect x="{leg_x}" y="{leg_y}" width="12" height="10" fill="{color}" rx="2"/>')
        elems.append(f'<text x="{leg_x + 16}" y="{leg_y + 9}" fill="#e2e8f0" font-size="10">{run_name}</text>')
        leg_y += 18

    inner = "\n".join(elems)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#0f172a;border-radius:8px">
{inner}
</svg>'''


def svg_parallel() -> str:
    W, H = 620, 300
    pad_l, pad_r, pad_t, pad_b = 60, 20, 40, 40
    n_dims = len(PARA_DIMS)
    dim_x = [pad_l + i * (W - pad_l - pad_r) / (n_dims - 1) for i in range(n_dims)]

    def dim_y(val):
        return H - pad_b - val * (H - pad_t - pad_b)

    elems = []

    # Dimension axes
    for i, dim_name in enumerate(PARA_DIMS):
        x = dim_x[i]
        elems.append(f'<line x1="{x:.1f}" y1="{pad_t}" x2="{x:.1f}" y2="{H - pad_b}" stroke="#334155" stroke-width="1.5"/>')
        elems.append(f'<text x="{x:.1f}" y="{pad_t - 8}" text-anchor="middle" fill="#38bdf8" font-size="10">{dim_name}</text>')
        for tick in [0, 0.5, 1.0]:
            ty = dim_y(tick)
            elems.append(f'<text x="{x - 4:.1f}" y="{ty + 4:.1f}" text-anchor="end" fill="#475569" font-size="8">{tick:.1f}</text>')

    # Lines per run (groot_v2 last / on top)
    run_order = [k for k in PARA_RUNS if k != "groot_v2"] + ["groot_v2"]
    for run_name in run_order:
        vals = PARA_RUNS[run_name]
        color = PARA_COLORS[run_name]
        sw = "2.5" if run_name == "groot_v2" else "1.2"
        pts = " ".join(f"{dim_x[i]:.1f},{dim_y(vals[i]):.1f}" for i in range(n_dims))
        elems.append(f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="{sw}" opacity="0.85"/>')

    # Legend
    leg_x, leg_y = pad_l, H - 6
    for run_name, color in PARA_COLORS.items():
        elems.append(f'<rect x="{leg_x}" y="{leg_y - 8}" width="10" height="8" fill="{color}" rx="1"/>')
        elems.append(f'<text x="{leg_x + 13}" y="{leg_y}" fill="#94a3b8" font-size="9">{run_name}</text>')
        leg_x += 88

    inner = "\n".join(elems)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#0f172a;border-radius:8px">
{inner}
</svg>'''


def svg_pvalue_table() -> str:
    N = len(PVAL_RUNS)
    cell = 68
    off_x = 90
    off_y = 28
    W = off_x + N * cell + 10
    H = off_y + N * cell + 10

    def p_color(v):
        if v is None:
            return "#0f172a"
        if isinstance(v, str):
            return "#1e293b"
        if v < 0.05:
            return "#14532d"
        return "#1e3a5f"

    def p_label(v):
        if v is None:
            return "—"
        if isinstance(v, float):
            star = " ★" if v < 0.05 else " NS"
            return f"{v:.3f}{star}"
        return str(v)

    elems = []
    # Column headers
    for j, rname in enumerate(PVAL_RUNS):
        elems.append(f'<text x="{off_x + j * cell + cell // 2}" y="18" text-anchor="middle" fill="#38bdf8" font-size="10" font-weight="bold">{rname}</text>')
    # Row headers + cells
    for i, rname in enumerate(PVAL_RUNS):
        elems.append(f'<text x="{off_x - 6}" y="{off_y + i * cell + cell // 2 + 4}" text-anchor="end" fill="#94a3b8" font-size="10">{rname}</text>')
        for j in range(N):
            if j > i:
                continue
            v = PVAL_MATRIX[i][j]
            cx = off_x + j * cell
            cy = off_y + i * cell
            bg = p_color(v)
            lbl = p_label(v)
            elems.append(f'<rect x="{cx + 1}" y="{cy + 1}" width="{cell - 2}" height="{cell - 2}" fill="{bg}" rx="3"/>')
            txt_col = "#C74634" if isinstance(v, float) and v < 0.05 else "#94a3b8"
            elems.append(f'<text x="{cx + cell // 2}" y="{cy + cell // 2 + 4}" text-anchor="middle" fill="{txt_col}" font-size="9">{lbl}</text>')

    inner = "\n".join(elems)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#0f172a;border-radius:8px">
{inner}
</svg>'''


# ── HTML page ─────────────────────────────────────────────────────────────────

def build_html() -> str:
    radar_svg  = svg_radar()
    para_svg   = svg_parallel()
    pval_svg   = svg_pvalue_table()

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Training Run Comparator — OCI Robot Cloud</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; padding: 2rem; }}
  h1 {{ color: #C74634; font-size: 1.7rem; margin-bottom: .25rem; }}
  .subtitle {{ color: #64748b; font-size: .85rem; margin-bottom: 1.5rem; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 1.5rem; }}
  .card {{ background: #1e293b; border-radius: 10px; padding: 1.25rem; border: 1px solid #334155; }}
  .card-title {{ color: #38bdf8; font-size: .9rem; font-weight: 600; margin-bottom: .75rem; }}
  .kpi-row {{ display: flex; gap: 1rem; flex-wrap: wrap; margin-bottom: 1.5rem; }}
  .kpi {{ background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: .75rem 1.25rem; min-width: 160px; }}
  .kpi-val {{ font-size: 1.6rem; font-weight: 700; color: #38bdf8; }}
  .kpi-lbl {{ font-size: .75rem; color: #64748b; margin-top: 2px; }}
  .kpi.red .kpi-val {{ color: #C74634; }}
  .kpi.green .kpi-val {{ color: #22c55e; }}
  svg {{ max-width: 100%; height: auto; display: block; }}
  .note {{ color: #64748b; font-size: .8rem; margin-top: .5rem; }}
</style>
</head>
<body>
<h1>Training Run Comparator</h1>
<p class="subtitle">OCI Robot Cloud · port {PORT} · 23 runs tracked · cycle-149A</p>

<div class="kpi-row">
  <div class="kpi"><div class="kpi-val">23</div><div class="kpi-lbl">Runs tracked</div></div>
  <div class="kpi green"><div class="kpi-val">groot_v2</div><div class="kpi-lbl">Pareto dominant</div></div>
  <div class="kpi red"><div class="kpi-val">p=0.033</div><div class="kpi-lbl">groot_v2 vs dagger_r9 ★</div></div>
  <div class="kpi"><div class="kpi-val">NS</div><div class="kpi-lbl">run10 vs r9 (in progress)</div></div>
</div>

<div class="grid">
  <div class="card">
    <div class="card-title">Radar Comparison — 6 Axes (BC / dagger_r9 / groot_v2 / run10_partial)</div>
    {radar_svg}
    <p class="note">Oracle red = groot_v2 (outermost on SR &amp; Smoothness)</p>
  </div>
  <div class="card">
    <div class="card-title">Parallel Coordinates — 5 Normalized Dimensions (6 runs)</div>
    {para_svg}
    <p class="note">Oracle red line = groot_v2</p>
  </div>
  <div class="card">
    <div class="card-title">Pairwise p-value Table (lower triangle, ★ = p&lt;0.05)</div>
    {pval_svg}
    <p class="note">Green = significant &nbsp;|&nbsp; NS = not significant</p>
  </div>
</div>
</body>
</html>"""


# ── App ───────────────────────────────────────────────────────────────────────

if USE_FASTAPI:
    app = FastAPI(title="Training Run Comparator", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def index():
        return HTMLResponse(build_html())

    @app.get("/health")
    async def health():
        return JSONResponse({"status": "ok", "port": PORT})

    @app.get("/runs")
    async def runs():
        return JSONResponse({
            "total_runs": 23,
            "pareto_dominant": "groot_v2",
            "significant_pairs": [
                {"run_a": "groot_v2", "run_b": "dagger_r9", "p": 0.033, "significant": True}
            ],
            "in_progress": ["run10_partial"],
        })

    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=PORT)

else:
    from http.server import BaseHTTPRequestHandler, HTTPServer
    import json as _json

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass

        def do_GET(self):
            if self.path == "/health":
                body = _json.dumps({"status": "ok", "port": PORT}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                body = build_html().encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

    if __name__ == "__main__":
        server = HTTPServer(("0.0.0.0", PORT), Handler)
        print(f"Serving on http://0.0.0.0:{PORT}")
        server.serve_forever()
