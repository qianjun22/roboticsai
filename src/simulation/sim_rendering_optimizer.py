"""OCI Robot Cloud — Sim Rendering Optimizer (port 8239)

Optimizes Isaac Sim rendering settings for synthetic data generation throughput.
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

import random
import math
from datetime import datetime

PORT = 8239

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

random.seed(7)

RENDER_MODES = ["headless", "low", "medium", "high", "RTX"]
GPU_TYPES = ["A100_80GB", "A100_40GB", "V100"]

# FPS table: render_mode × gpu_type
_FPS = {
    "headless": {"A100_80GB": 94,  "A100_40GB": 82,  "V100": 61},
    "low":      {"A100_80GB": 78,  "A100_40GB": 67,  "V100": 48},
    "medium":   {"A100_80GB": 67,  "A100_40GB": 55,  "V100": 39},
    "high":     {"A100_80GB": 43,  "A100_40GB": 35,  "V100": 22},
    "RTX":      {"A100_80GB": 28,  "A100_40GB": 21,  "V100": 12},
}

# Cost per 1000 demo frames (USD)
_COST = {
    "headless": {"A100_80GB": 0.12, "A100_40GB": 0.14, "V100": 0.18},
    "low":      {"A100_80GB": 0.14, "A100_40GB": 0.17, "V100": 0.22},
    "medium":   {"A100_80GB": 0.17, "A100_40GB": 0.21, "V100": 0.29},
    "high":     {"A100_80GB": 0.26, "A100_40GB": 0.33, "V100": 0.47},
    "RTX":      {"A100_80GB": 0.41, "A100_40GB": 0.55, "V100": 0.82},
}

# Perceptual quality score [0, 1] per render mode
_QUALITY = {
    "headless": 0.51,
    "low":      0.68,
    "medium":   0.82,
    "high":     0.91,
    "RTX":      0.97,
}

# Recommended config
RECOMMENDED = {"mode": "medium", "gpu": "A100_80GB",
               "fps": 67, "cost": 0.17, "quality": 0.82}

# GPU utilization % per render mode
_GPU_UTIL = {"headless": 58, "low": 68, "medium": 79, "high": 89, "RTX": 96}

# ---------------------------------------------------------------------------
# SVG 1: FPS vs rendering quality — 15 lines (5 modes × 3 GPUs)
# ---------------------------------------------------------------------------

def _svg_fps_lines() -> str:
    W, H = 640, 280
    PAD_L, PAD_R, PAD_T, PAD_B = 52, 130, 24, 40
    cw = W - PAD_L - PAD_R
    ch = H - PAD_T - PAD_B

    qualities = [_QUALITY[m] for m in RENDER_MODES]
    min_q, max_q = 0.45, 1.0
    max_fps = 100

    gpu_colors = {"A100_80GB": "#38bdf8", "A100_40GB": "#7dd3fc", "V100": "#fbbf24"}
    mode_dash  = {"headless": "none", "low": "4,2", "medium": "none",
                  "high": "6,3", "RTX": "2,2"}

    def qx(q): return PAD_L + cw * (q - min_q) / (max_q - min_q)
    def fy(f): return PAD_T + ch * (1 - f / max_fps)

    # Grid
    grids = ""
    for q_tick in [0.5, 0.6, 0.7, 0.8, 0.9, 1.0]:
        xx = qx(q_tick)
        grids += f'<line x1="{xx:.1f}" y1="{PAD_T}" x2="{xx:.1f}" y2="{PAD_T+ch}" stroke="#334155" stroke-width="1"/>'
        grids += f'<text x="{xx:.1f}" y="{H-4}" fill="#94a3b8" font-size="9" text-anchor="middle">{q_tick:.1f}</text>'
    for f_tick in [0, 20, 40, 60, 80, 100]:
        yy = fy(f_tick)
        grids += f'<line x1="{PAD_L}" y1="{yy:.1f}" x2="{PAD_L+cw}" y2="{yy:.1f}" stroke="#334155" stroke-width="1"/>'
        grids += f'<text x="{PAD_L-4}" y="{yy+4:.1f}" fill="#94a3b8" font-size="9" text-anchor="end">{f_tick}</text>'

    # Lines: one per GPU per render mode series
    lines_svg = ""
    for gpu in GPU_TYPES:
        pts = " ".join(f"{qx(_QUALITY[m]):.1f},{fy(_FPS[m][gpu]):.1f}" for m in RENDER_MODES)
        lines_svg += f'<polyline points="{pts}" fill="none" stroke="{gpu_colors[gpu]}" stroke-width="2.2" stroke-dasharray="{mode_dash["medium"]}"/>'
        # Dots + mode labels on A100_80GB only
        for m in RENDER_MODES:
            cx_ = qx(_QUALITY[m])
            cy_ = fy(_FPS[m][gpu])
            lines_svg += f'<circle cx="{cx_:.1f}" cy="{cy_:.1f}" r="4" fill="{gpu_colors[gpu]}" opacity="0.9"/>'
            if gpu == "A100_80GB":
                lines_svg += f'<text x="{cx_:.1f}" y="{cy_ - 7:.1f}" fill="#e2e8f0" font-size="9" text-anchor="middle">{m}</text>'

    # Optimal zone: quality >= 0.8 AND cost <= $0.50 (medium/high for A100)
    opt_x = qx(0.80)
    lines_svg += f'<rect x="{opt_x:.1f}" y="{PAD_T}" width="{PAD_L+cw-opt_x:.1f}" height="{ch}" fill="#4ade80" opacity="0.07"/>'
    lines_svg += f'<text x="{opt_x+4:.1f}" y="{PAD_T+14}" fill="#4ade80" font-size="9">SDG optimal zone</text>'

    # Recommended star
    rx = qx(RECOMMENDED["quality"])
    ry = fy(RECOMMENDED["fps"])
    lines_svg += f'<polygon points="{rx},{ry-8} {rx+5},{ry+5} {rx-7},{ry-3} {rx+7},{ry-3} {rx-5},{ry+5}" fill="#f97316" opacity="0.95"/>'
    lines_svg += f'<text x="{rx+9:.1f}" y="{ry+4:.1f}" fill="#f97316" font-size="9">recommended</text>'

    # Legend
    legend = ""
    ly = PAD_T + 4
    for gpu, c in gpu_colors.items():
        legend += f'<line x1="{W-PAD_R+8}" y1="{ly+5}" x2="{W-PAD_R+22}" y2="{ly+5}" stroke="{c}" stroke-width="2.5"/>'
        legend += f'<text x="{W-PAD_R+25}" y="{ly+9}" fill="#cbd5e1" font-size="10">{gpu}</text>'
        ly += 18

    title = f'<text x="{PAD_L + cw//2}" y="14" fill="#f1f5f9" font-size="12" text-anchor="middle" font-weight="bold">FPS vs Rendering Quality (15 config lines)</text>'
    x_lbl = f'<text x="{PAD_L + cw//2}" y="{H-1}" fill="#94a3b8" font-size="10" text-anchor="middle">Perceptual Quality Score</text>'
    y_lbl = f'<text x="10" y="{PAD_T + ch//2}" fill="#94a3b8" font-size="10" text-anchor="middle" transform="rotate(-90 10 {PAD_T + ch//2})">FPS</text>'

    return f"""<svg xmlns='http://www.w3.org/2000/svg' width='{W}' height='{H}' style='background:#1e293b;border-radius:8px'>
  {grids}{lines_svg}{legend}{title}{x_lbl}{y_lbl}
</svg>"""


# ---------------------------------------------------------------------------
# SVG 2: Cost per 1000 demo frames — bar chart with optimal point annotation
# ---------------------------------------------------------------------------

def _svg_cost_bars() -> str:
    W, H = 640, 280
    PAD_L, PAD_R, PAD_T, PAD_B = 52, 20, 30, 50
    cw = W - PAD_L - PAD_R
    ch = H - PAD_T - PAD_B

    gpu_colors = {"A100_80GB": "#38bdf8", "A100_40GB": "#7dd3fc", "V100": "#fbbf24"}
    n_modes = len(RENDER_MODES)
    n_gpus  = len(GPU_TYPES)
    max_cost = 0.90

    group_w = cw / n_modes
    bar_w = group_w * 0.23
    gap = group_w * 0.03

    bars = ""
    xlabels = ""
    opt_threshold_cost = 0.50
    opt_threshold_quality = 0.80

    for i, mode in enumerate(RENDER_MODES):
        gx = PAD_L + i * group_w + group_w * 0.08
        for j, gpu in enumerate(GPU_TYPES):
            cost = _COST[mode][gpu]
            bx = gx + j * (bar_w + gap)
            bh = ch * cost / max_cost
            by = PAD_T + ch - bh
            c = gpu_colors[gpu]
            opacity = "0.9"
            # highlight optimal
            is_optimal = (_QUALITY[mode] >= opt_threshold_quality and
                          cost <= opt_threshold_cost)
            stroke = ' stroke="#f97316" stroke-width="2"' if is_optimal else ""
            bars += f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bar_w:.1f}" height="{bh:.1f}" fill="{c}" rx="2" opacity="{opacity}"{stroke}/>'
            # cost label
            bars += f'<text x="{bx + bar_w/2:.1f}" y="{by - 3:.1f}" fill="#94a3b8" font-size="8" text-anchor="middle">${cost:.2f}</text>'

        cx = PAD_L + i * group_w + group_w / 2
        xlabels += f'<text x="{cx:.1f}" y="{H - 16}" fill="#94a3b8" font-size="10" text-anchor="middle">{mode}</text>'
        # quality score below mode name
        xlabels += f'<text x="{cx:.1f}" y="{H - 4}" fill="#64748b" font-size="8" text-anchor="middle">q={_QUALITY[mode]:.2f}</text>'

    # Cost threshold line $0.50
    thresh_y = PAD_T + ch * (1 - opt_threshold_cost / max_cost)
    bars += f'<line x1="{PAD_L}" y1="{thresh_y:.1f}" x2="{W-PAD_R}" y2="{thresh_y:.1f}" stroke="#f97316" stroke-width="1.5" stroke-dasharray="5,3"/>'
    bars += f'<text x="{W-PAD_R-2}" y="{thresh_y-4:.1f}" fill="#f97316" font-size="9" text-anchor="end">$0.50 cost ceiling</text>'

    # Grid
    grids = ""
    for c_tick in [0.0, 0.20, 0.40, 0.60, 0.80]:
        yy = PAD_T + ch * (1 - c_tick / max_cost)
        grids += f'<line x1="{PAD_L}" y1="{yy:.1f}" x2="{W-PAD_R}" y2="{yy:.1f}" stroke="#334155" stroke-width="1"/>'
        grids += f'<text x="{PAD_L-4}" y="{yy+4:.1f}" fill="#94a3b8" font-size="9" text-anchor="end">${c_tick:.2f}</text>'

    # Optimal annotation arrow
    opt_mode_i = RENDER_MODES.index("medium")
    opt_gpu_j  = GPU_TYPES.index("A100_80GB")
    opt_bx = PAD_L + opt_mode_i * group_w + group_w * 0.08 + opt_gpu_j * (bar_w + gap) + bar_w / 2
    opt_cost = _COST["medium"]["A100_80GB"]
    opt_by = PAD_T + ch - ch * opt_cost / max_cost - 18
    grids += f'<text x="{opt_bx:.1f}" y="{opt_by - 4:.1f}" fill="#f97316" font-size="9" text-anchor="middle">OPTIMAL</text>'
    grids += f'<line x1="{opt_bx:.1f}" y1="{opt_by:.1f}" x2="{opt_bx:.1f}" y2="{opt_by + 12:.1f}" stroke="#f97316" stroke-width="1.5" marker-end="url(#arr)"/>'

    legend = ""
    lx = PAD_L
    for gpu, c in gpu_colors.items():
        legend += f'<rect x="{lx}" y="{H - 30}" width="10" height="10" fill="{c}" rx="2"/>'
        legend += f'<text x="{lx + 13}" y="{H - 20}" fill="#cbd5e1" font-size="10">{gpu}</text>'
        lx += 110

    title = f'<text x="{PAD_L + cw//2}" y="18" fill="#f1f5f9" font-size="12" text-anchor="middle" font-weight="bold">Cost per 1,000 Demo Frames — Rendering Mode × GPU (orange border = Pareto-optimal)</text>'
    y_lbl = f'<text x="10" y="{PAD_T + ch//2}" fill="#94a3b8" font-size="10" text-anchor="middle" transform="rotate(-90 10 {PAD_T + ch//2})">$/1k frames</text>'

    defs = '<defs><marker id="arr" markerWidth="6" markerHeight="6" refX="3" refY="6" orient="auto"><path d="M0,0 L3,6 L6,0" fill="#f97316"/></marker></defs>'

    return f"""<svg xmlns='http://www.w3.org/2000/svg' width='{W}' height='{H}' style='background:#1e293b;border-radius:8px'>
  {defs}{grids}{bars}{xlabels}{legend}{title}{y_lbl}
</svg>"""


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def _build_html() -> str:
    svg1 = _svg_fps_lines()
    svg2 = _svg_cost_bars()

    metrics = [
        ("Headless A100_80GB",  "94 fps / $0.12", "#38bdf8"),
        ("RTX A100_80GB",       "28 fps / $0.41", "#7dd3fc"),
        ("Recommended (medium)","67 fps / $0.17", "#4ade80"),
        ("Quality Threshold",   "≥ 0.80",          "#f97316"),
        ("Cost Ceiling",        "$0.50 / 1k",      "#f97316"),
        ("V100 RTX (worst)",    "12 fps / $0.82",  "#C74634"),
    ]

    cards = "".join(
        f'<div style="background:#1e293b;border:1px solid #334155;border-radius:8px;padding:14px;text-align:center">'
        f'<div style="color:#94a3b8;font-size:11px;margin-bottom:6px">{label}</div>'
        f'<div style="color:{color};font-size:17px;font-weight:700">{value}</div>'
        f'</div>'
        for label, value, color in metrics
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Sim Rendering Optimizer — OCI Robot Cloud</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #f1f5f9; font-family: 'Segoe UI', system-ui, sans-serif; padding: 24px; }}
    h1 {{ color: #C74634; font-size: 22px; margin-bottom: 4px; }}
    .subtitle {{ color: #64748b; font-size: 13px; margin-bottom: 20px; }}
    .grid-6 {{ display: grid; grid-template-columns: repeat(6, 1fr); gap: 12px; margin-bottom: 24px; }}
    .chart-row {{ display: flex; gap: 20px; flex-wrap: wrap; margin-bottom: 20px; }}
    .chart-box {{ background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 16px; }}
    .tag {{ display: inline-block; background: #C74634; color: #fff; font-size: 11px; padding: 2px 8px; border-radius: 4px; margin-left: 10px; }}
    .badge {{ display: inline-block; background: #4ade8022; color: #4ade80; border: 1px solid #4ade8055;
              font-size: 11px; padding: 2px 10px; border-radius: 12px; margin-left: 8px; }}
    footer {{ color: #475569; font-size: 11px; margin-top: 16px; }}
  </style>
</head>
<body>
  <h1>Sim Rendering Optimizer <span class="tag">PORT 8239</span>
      <span class="badge">Pareto-Optimal: medium + A100_80GB</span></h1>
  <p class="subtitle">Isaac Sim SDG throughput optimizer — FPS, cost, and quality Pareto frontier across 5 render modes × 3 GPU types</p>

  <div class="grid-6">{cards}</div>

  <div class="chart-row">
    <div class="chart-box">{svg1}</div>
  </div>
  <div class="chart-row">
    <div class="chart-box">{svg2}</div>
  </div>

  <footer>Updated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')} &nbsp;|&nbsp; OCI Robot Cloud Platform</footer>
</body>
</html>"""


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

if HAS_FASTAPI:
    app = FastAPI(title="Sim Rendering Optimizer", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return _build_html()

    @app.get("/api/fps")
    async def fps_table():
        return {"modes": RENDER_MODES, "gpus": GPU_TYPES, "fps": _FPS}

    @app.get("/api/cost")
    async def cost_table():
        return {"modes": RENDER_MODES, "gpus": GPU_TYPES, "cost_per_1k": _COST}

    @app.get("/api/pareto")
    async def pareto():
        """Return all configs meeting quality>=0.8 and cost<=0.50."""
        results = []
        for mode in RENDER_MODES:
            if _QUALITY[mode] < 0.80:
                continue
            for gpu in GPU_TYPES:
                cost = _COST[mode][gpu]
                if cost <= 0.50:
                    results.append({
                        "mode": mode, "gpu": gpu,
                        "fps": _FPS[mode][gpu],
                        "cost_per_1k": cost,
                        "quality": _QUALITY[mode],
                        "gpu_util_pct": _GPU_UTIL[mode],
                    })
        results.sort(key=lambda r: r["cost_per_1k"])
        return {"pareto_configs": results, "recommended": RECOMMENDED}

    @app.get("/api/recommend")
    async def recommend():
        return RECOMMENDED

    @app.get("/health")
    async def health():
        return {"status": "ok", "port": PORT, "service": "sim_rendering_optimizer"}

else:
    from http.server import HTTPServer, BaseHTTPRequestHandler

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = _build_html().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            pass


if __name__ == "__main__":
    if HAS_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        print(f"FastAPI not found — starting stdlib server on port {PORT}")
        HTTPServer(("0.0.0.0", PORT), _Handler).serve_forever()
