# sim_randomization_scheduler.py — port 8613
# Adaptive domain-randomization schedule for sim-to-real transfer.

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

from http.server import HTTPServer, BaseHTTPRequestHandler
import math

# ---------------------------------------------------------------------------
# HTML builder
# ---------------------------------------------------------------------------

def build_html() -> str:
    dims  = ["lighting", "texture", "friction", "mass", "pose_noise",
             "background", "camera", "object_scale"]
    stages = ["S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8"]

    # DR schedule: 8 dims × 8 stages (randomization range 0–1)
    # Ramps up, then adaptive gating after S5
    schedule = [
        # S1    S2    S3    S4    S5    S6    S7    S8
        [0.15, 0.30, 0.45, 0.60, 0.72, 0.80, 0.85, 0.88],  # lighting
        [0.10, 0.22, 0.35, 0.50, 0.62, 0.70, 0.76, 0.80],  # texture
        [0.08, 0.18, 0.28, 0.40, 0.52, 0.58, 0.63, 0.67],  # friction
        [0.06, 0.14, 0.24, 0.35, 0.46, 0.52, 0.56, 0.60],  # mass
        [0.12, 0.24, 0.36, 0.48, 0.58, 0.64, 0.69, 0.72],  # pose_noise
        [0.05, 0.12, 0.20, 0.30, 0.40, 0.46, 0.50, 0.54],  # background
        [0.08, 0.16, 0.26, 0.38, 0.48, 0.54, 0.58, 0.62],  # camera
        [0.06, 0.14, 0.22, 0.33, 0.43, 0.49, 0.53, 0.57],  # object_scale
    ]

    # ---- SVG 1: heatmap ----
    cell_w, cell_h = 50, 36
    hm_pad_l, hm_pad_t = 92, 30
    hm_w = hm_pad_l + len(stages) * cell_w + 20
    hm_h = hm_pad_t + len(dims) * cell_h + 30

    def heat_color(v):
        # 0 → dark blue #0f2942, 1 → Oracle red #C74634
        r = int(0x0f + v * (0xC7 - 0x0f))
        g = int(0x29 + v * (0x46 - 0x29))
        b = int(0x42 + v * (0x34 - 0x42))
        return f"#{r:02x}{g:02x}{b:02x}"

    cells_svg = ""
    for ri, row in enumerate(schedule):
        for ci, val in enumerate(row):
            x = hm_pad_l + ci * cell_w
            y = hm_pad_t + ri * cell_h
            cells_svg += (
                f'<rect x="{x}" y="{y}" width="{cell_w-1}" height="{cell_h-1}"'
                f' fill="{heat_color(val)}" rx="2"/>\n'
            )
            cells_svg += (
                f'<text x="{x + cell_w//2}" y="{y + cell_h//2 + 4}"'
                f' text-anchor="middle" fill="#e2e8f0" font-size="10">{val:.2f}</text>\n'
            )
        # row label
        cells_svg += (
            f'<text x="{hm_pad_l - 6}" y="{hm_pad_t + ri*cell_h + cell_h//2 + 4}"'
            f' text-anchor="end" fill="#94a3b8" font-size="11">{dims[ri]}</text>\n'
        )
    # column labels
    for ci, s in enumerate(stages):
        x = hm_pad_l + ci * cell_w + cell_w // 2
        cells_svg += f'<text x="{x}" y="{hm_pad_t - 8}" text-anchor="middle" fill="#94a3b8" font-size="11">{s}</text>\n'

    # color-scale legend bar
    legend_x0, legend_y0 = hm_pad_l, hm_h - 18
    legend_w = len(stages) * cell_w
    gradient_stops = "".join(
        f'<stop offset="{int(i*100/10)}%" stop-color="{heat_color(i/10)}"/>'
        for i in range(11)
    )
    cells_svg += f"""
      <defs><linearGradient id="hg" x1="0" x2="1" y1="0" y2="0">{gradient_stops}</linearGradient></defs>
      <rect x="{legend_x0}" y="{legend_y0}" width="{legend_w}" height="10" fill="url(#hg)" rx="3"/>
      <text x="{legend_x0}" y="{legend_y0+22}" fill="#64748b" font-size="10">0.0 (no rand)</text>
      <text x="{legend_x0+legend_w}" y="{legend_y0+22}" text-anchor="end" fill="#64748b" font-size="10">1.0 (max)</text>
    """

    svg1 = f"""
    <svg width="{hm_w}" height="{hm_h}" xmlns="http://www.w3.org/2000/svg">
      <rect width="100%" height="100%" fill="#0f172a" rx="8"/>
      {cells_svg}
    </svg>"""

    # ---- SVG 2: SR impact bar chart (sorted) ----
    # SR delta when each dim is at max vs baseline
    sr_impact = [
        ("lighting",     0.060),
        ("texture",      0.040),
        ("pose_noise",   0.032),
        ("camera",       0.027),
        ("friction",     0.021),
        ("mass",         0.016),
        ("object_scale", 0.012),
        ("background",   0.009),
    ]
    sr_impact_sorted = sorted(sr_impact, key=lambda x: x[1], reverse=True)

    bar2_w, bar2_h = 520, 220
    b2_pad_l, b2_pad_b = 110, 35
    b2_inner_w = bar2_w - b2_pad_l - 20
    b2_inner_h = bar2_h - b2_pad_b - 20
    b2_bar_h = int(b2_inner_h / len(sr_impact_sorted)) - 4
    b2_max = 0.07

    bars2_svg = ""
    for i, (name, val) in enumerate(sr_impact_sorted):
        bw = int(val / b2_max * b2_inner_w)
        y = 20 + i * (b2_bar_h + 4)
        intensity = val / b2_max
        r = int(0x38 + intensity * (0xC7 - 0x38))
        g = int(0xbd + intensity * (0x46 - 0xbd))
        bv = int(0xf8 + intensity * (0x34 - 0xf8))
        color = f"#{r:02x}{g:02x}{max(0,bv):02x}"
        bars2_svg += f'<rect x="{b2_pad_l}" y="{y}" width="{bw}" height="{b2_bar_h}" fill="{color}" rx="3" opacity="0.9"/>\n'
        bars2_svg += f'<text x="{b2_pad_l - 6}" y="{y + b2_bar_h//2 + 4}" text-anchor="end" fill="#94a3b8" font-size="11">{name}</text>\n'
        bars2_svg += f'<text x="{b2_pad_l + bw + 5}" y="{y + b2_bar_h//2 + 4}" fill="#e2e8f0" font-size="10">+{val:.3f}</text>\n'

    # x-axis
    bars2_svg += f'<line x1="{b2_pad_l}" y1="{bar2_h - b2_pad_b}" x2="{bar2_w-20}" y2="{bar2_h - b2_pad_b}" stroke="#334155" stroke-width="1"/>\n'
    bars2_svg += f'<text x="{b2_pad_l + b2_inner_w//2}" y="{bar2_h - 6}" text-anchor="middle" fill="#64748b" font-size="11">SR delta (pp) when dimension at max</text>\n'

    svg2 = f"""
    <svg width="{bar2_w}" height="{bar2_h}" xmlns="http://www.w3.org/2000/svg">
      <rect width="100%" height="100%" fill="#0f172a" rx="8"/>
      {bars2_svg}
    </svg>"""

    # ---- SVG 3: diversity score progression ----
    # diversity = accumulated variety over training; SR gates at 0.6 and 0.8
    steps_k = list(range(0, 81, 5))   # 0 .. 80 k steps
    n = len(steps_k)

    def diversity(s):
        """Saturating growth with slight S-shape."""
        return 1.0 - math.exp(-s / 25.0) * (1 + 0.3 * math.exp(-s / 8.0))

    div_vals = [diversity(s) for s in steps_k]
    sr_gate_vals = [0.6, 0.8]   # diversity thresholds that gate SR measurement
    sr_gate_colors = ["#f59e0b", "#34d399"]
    sr_gate_labels = ["SR gate 1 (SR>0.6)", "SR gate 2 (SR>0.8)"]

    dv_w, dv_h = 520, 220
    dv_pad_l, dv_pad_b = 50, 40
    dv_inner_w = dv_w - dv_pad_l - 20
    dv_inner_h = dv_h - dv_pad_b - 20

    def dv_px(i):
        return dv_pad_l + int(i / (n - 1) * dv_inner_w)

    def dv_py(v):
        return dv_h - dv_pad_b - int(v * dv_inner_h)

    line_pts = " ".join(f"{dv_px(i)},{dv_py(v)}" for i, v in enumerate(div_vals))
    area_pts = f"{dv_px(0)},{dv_py(0)} " + line_pts + f" {dv_px(n-1)},{dv_py(0)}"

    div_svg = f"""
      <polygon points="{area_pts}" fill="#38bdf8" opacity="0.12"/>
      <polyline points="{line_pts}" fill="none" stroke="#38bdf8" stroke-width="2"/>
    """

    # gate lines
    for gv, gc, gl in zip(sr_gate_vals, sr_gate_colors, sr_gate_labels):
        gy = dv_py(gv)
        div_svg += f'<line x1="{dv_pad_l}" y1="{gy}" x2="{dv_w-20}" y2="{gy}" stroke="{gc}" stroke-width="1.5" stroke-dasharray="6,3"/>\n'
        div_svg += f'<text x="{dv_w-22}" y="{gy-4}" text-anchor="end" fill="{gc}" font-size="10">{gl}</text>\n'

    # y-axis ticks
    for tick in [0.0, 0.25, 0.5, 0.75, 1.0]:
        ty = dv_py(tick)
        div_svg += f'<line x1="{dv_pad_l}" y1="{ty}" x2="{dv_w-20}" y2="{ty}" stroke="#1e293b" stroke-width="1"/>\n'
        div_svg += f'<text x="{dv_pad_l-6}" y="{ty+4}" text-anchor="end" fill="#64748b" font-size="10">{tick:.2f}</text>\n'

    # x-axis labels
    for tick_k in [0, 20, 40, 60, 80]:
        i = tick_k // 5
        tx = dv_px(i)
        div_svg += f'<text x="{tx}" y="{dv_h - dv_pad_b + 14}" text-anchor="middle" fill="#64748b" font-size="10">{tick_k}k</text>\n'

    div_svg += f'<text x="{dv_w//2}" y="{dv_h - 4}" text-anchor="middle" fill="#64748b" font-size="11">Training Steps — Diversity Score Progression</text>\n'

    svg3 = f"""
    <svg width="{dv_w}" height="{dv_h}" xmlns="http://www.w3.org/2000/svg">
      <rect width="100%" height="100%" fill="#0f172a" rx="8"/>
      {div_svg}
    </svg>"""

    html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Sim Randomization Scheduler — Port 8613</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; padding: 32px; }}
    h1 {{ color: #C74634; font-size: 1.6rem; margin-bottom: 6px; }}
    h2 {{ color: #38bdf8; font-size: 1.1rem; margin: 28px 0 10px; }}
    p.sub {{ color: #64748b; font-size: 0.85rem; margin-bottom: 24px; }}
    .card {{ background: #1e293b; border-radius: 10px; padding: 20px; display: inline-block; }}
    .metrics {{ display: flex; flex-wrap: wrap; gap: 16px; margin-top: 28px; }}
    .metric {{ background: #1e293b; border-left: 4px solid #38bdf8; border-radius: 6px;
               padding: 14px 20px; min-width: 210px; }}
    .metric .val {{ font-size: 1.8rem; font-weight: 700; color: #38bdf8; }}
    .metric .lbl {{ font-size: 0.8rem; color: #64748b; margin-top: 4px; }}
    .metric.warn .val {{ color: #f59e0b; }}
    .metric.warn {{ border-color: #f59e0b; }}
    .metric.red .val {{ color: #f87171; }}
    .metric.red {{ border-color: #f87171; }}
    .metric.good .val {{ color: #34d399; }}
    .metric.good {{ border-color: #34d399; }}
  </style>
</head>
<body>
  <h1>Sim Randomization Scheduler</h1>
  <p class="sub">Adaptive domain randomization schedule for sim-to-real transfer — OCI Robot Cloud</p>

  <h2>DR Parameter Schedule Heatmap (8 dims x 8 stages)</h2>
  <div class="card">{svg1}</div>

  <h2>Randomization Dimension vs SR Impact</h2>
  <div class="card">{svg2}</div>

  <h2>Diversity Score Progression with SR Gating Thresholds</h2>
  <div class="card">{svg3}</div>

  <h2>Key Metrics</h2>
  <div class="metrics">
    <div class="metric good">
      <div class="val">SR &gt; 0.7</div>
      <div class="lbl">Threshold for adaptive DR engagement</div>
    </div>
    <div class="metric warn">
      <div class="val">+0.06pp</div>
      <div class="lbl">Lighting — highest SR impact dimension</div>
    </div>
    <div class="metric red">
      <div class="val">-0.03pp</div>
      <div class="lbl">Over-randomization penalty (&gt;5 dims at max)</div>
    </div>
    <div class="metric">
      <div class="val">&le; 5 dims</div>
      <div class="lbl">Recommended max active DR dimensions simultaneously</div>
    </div>
  </div>
</body>
</html>"""
    return html


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

if USE_FASTAPI:
    app = FastAPI(title="Sim Randomization Scheduler", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return HTMLResponse(content=build_html())

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "sim_randomization_scheduler", "port": 8613}

    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=8613)

else:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/health":
                body = b'{"status": "ok", "service": "sim_randomization_scheduler", "port": 8613}'
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
            else:
                body = build_html().encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    if __name__ == "__main__":
        print("Serving sim_randomization_scheduler on port 8613 (stdlib fallback)")
        HTTPServer(("0.0.0.0", 8613), Handler).serve_forever()
