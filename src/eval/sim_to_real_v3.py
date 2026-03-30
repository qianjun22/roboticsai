"""sim_to_real_v3.py — Sim-to-Real Transfer v3 Dashboard (port 8320)

Progressive domain adaptation with gap closing metrics, SVG charts, dark theme.
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
from datetime import datetime, timedelta

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

MONTHLY_GAP_DATA = [
    # (week_label, sim_sr, real_sr, annotation)
    ("Jan W1",  78.0, 51.0, None),
    ("Jan W2",  78.2, 51.8, None),
    ("Jan W3",  78.5, 52.5, "domain_rand_v2"),
    ("Jan W4",  79.0, 54.0, None),
    ("Feb W1",  79.2, 55.3, None),
    ("Feb W2",  79.5, 56.8, None),
    ("Feb W3",  79.8, 57.4, "real_demos_added"),
    ("Feb W4",  80.0, 59.6, None),
    ("Mar W1",  80.3, 60.9, None),
    ("Mar W2",  80.5, 62.2, None),
    ("Mar W3",  80.7, 63.8, "Cosmos_WM"),
    ("Mar W4",  81.0, 65.5, None),
    ("Apr W1",  81.1, 66.8, None),
    ("Apr W2",  81.2, 68.1, "dagger_online"),
    ("Apr W3",  81.3, 69.4, None),
    ("Apr W4",  81.0, 71.0, None),
    ("May W1",  81.2, 72.1, None),
    ("May W2",  81.4, 73.3, None),
    ("May W3",  81.5, 74.2, None),
    ("May W4",  81.6, 75.1, None),
    ("Jun W1",  81.7, 76.0, None),
    ("Jun W2",  81.8, 76.9, None),
    ("Jun W3",  82.0, 77.5, None),
    ("Jun W4",  82.1, 78.2, None),
]

TECHNIQUE_CONTRIBUTIONS = [
    ("domain_rand_v2",  6),
    ("real_demos_added", 8),
    ("Cosmos_WM",       5),
    ("dagger_online",   4),
    ("baseline_gap",    4),  # remaining
]

RADAR_DIMS = [
    ("visual_gap",       {"v1": 72, "v2": 55, "v3": 28}, 0),
    ("physics_gap",      {"v1": 65, "v2": 45, "v3": 22}, 0),
    ("sensor_gap",       {"v1": 80, "v2": 62, "v3": 38}, 0),
    ("task_variation",   {"v1": 58, "v2": 40, "v3": 18}, 0),
    ("lighting_gap",     {"v1": 70, "v2": 48, "v3": 20}, 0),
    ("texture_gap",      {"v1": 85, "v2": 68, "v3": 44}, 0),
]

KEY_METRICS = {
    "gap_jan":             27,
    "gap_current":         10,
    "gap_target":           5,
    "gap_closure_rate":    "~2.8 pp/month",
    "largest_remaining":   "texture_gap (44%)",
    "eta_to_target":       "Sep 2026",
    "best_technique":      "real_demos_added (-8 pp)",
    "sim_sr_current":      81.0,
    "real_sr_current":     71.0,
}


# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------

def build_gap_trajectory_svg() -> str:
    W, H = 820, 320
    pad_l, pad_r, pad_t, pad_b = 55, 30, 30, 60

    n = len(MONTHLY_GAP_DATA)
    x_step = (W - pad_l - pad_r) / max(n - 1, 1)

    sim_vals  = [d[1] for d in MONTHLY_GAP_DATA]
    real_vals = [d[2] for d in MONTHLY_GAP_DATA]
    gap_vals  = [s - r for s, r in zip(sim_vals, real_vals)]

    y_min, y_max = 0, 32

    def yx(i, v):
        x = pad_l + i * x_step
        y = pad_t + (y_max - v) / (y_max - y_min) * (H - pad_t - pad_b)
        return x, y

    # Build polyline points for gap
    gap_pts  = " ".join(f"{yx(i, g)[0]:.1f},{yx(i, g)[1]:.1f}" for i, g in enumerate(gap_vals))
    sim_pts  = " ".join(f"{yx(i, s)[0]:.1f},{pad_t + (y_max - s) / (y_max - y_min) * (H - pad_t - pad_b):.1f}" for i, s in enumerate(sim_vals))

    # X-axis labels: show month labels
    month_labels = []
    for i, (label, _, _, _) in enumerate(MONTHLY_GAP_DATA):
        if "W1" in label:
            x = pad_l + i * x_step
            month_labels.append(f'<text x="{x:.1f}" y="{H - pad_b + 18}" fill="#94a3b8" font-size="10" text-anchor="middle">{label[:3]}</text>')

    # Annotation markers
    annotations = []
    for i, (label, sim_v, real_v, ann) in enumerate(MONTHLY_GAP_DATA):
        if ann:
            g = sim_v - real_v
            cx, cy = yx(i, g)
            annotations.append(
                f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="6" fill="#f97316" stroke="#0f172a" stroke-width="1.5"/>'
                f'<text x="{cx:.1f}" y="{cy - 12:.1f}" fill="#f97316" font-size="9" text-anchor="middle">{ann}</text>'
            )

    # Y grid lines
    y_grid = ""
    for v in range(0, 33, 5):
        _, gy = yx(0, v)
        y_grid += f'<line x1="{pad_l}" y1="{gy:.1f}" x2="{W - pad_r}" y2="{gy:.1f}" stroke="#1e293b" stroke-width="1"/>'
        y_grid += f'<text x="{pad_l - 6}" y="{gy + 4:.1f}" fill="#94a3b8" font-size="10" text-anchor="end">{v}</text>'

    svg = f"""
<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg" style="background:#0f172a;border-radius:8px">
  <defs>
    <linearGradient id="gapGrad" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#C74634" stop-opacity="0.5"/>
      <stop offset="100%" stop-color="#C74634" stop-opacity="0.05"/>
    </linearGradient>
  </defs>
  <!-- Grid -->
  {y_grid}
  <!-- Axis -->
  <line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{H - pad_b}" stroke="#334155" stroke-width="1"/>
  <line x1="{pad_l}" y1="{H - pad_b}" x2="{W - pad_r}" y2="{H - pad_b}" stroke="#334155" stroke-width="1"/>
  <!-- Gap area fill -->
  <polyline points="{gap_pts} {pad_l + (n-1)*x_step:.1f},{H - pad_b} {pad_l},{H - pad_b}" fill="url(#gapGrad)" stroke="none"/>
  <!-- Gap line -->
  <polyline points="{gap_pts}" fill="none" stroke="#C74634" stroke-width="2.5"/>
  <!-- Annotations -->
  {chr(10).join(annotations)}
  <!-- Month labels -->
  {chr(10).join(month_labels)}
  <!-- Target line -->
  <line x1="{pad_l}" y1="{yx(0, 5)[1]:.1f}" x2="{W - pad_r}" y2="{yx(0, 5)[1]:.1f}" stroke="#22c55e" stroke-width="1" stroke-dasharray="6,4"/>
  <text x="{W - pad_r - 2}" y="{yx(0, 5)[1] - 5:.1f}" fill="#22c55e" font-size="10" text-anchor="end">Target &lt;5pp</text>
  <!-- Title -->
  <text x="{W // 2}" y="18" fill="#e2e8f0" font-size="13" text-anchor="middle" font-weight="bold">Sim-to-Real Gap Trajectory (Jan–Jun 2026)</text>
  <!-- Y label -->
  <text x="12" y="{(H) // 2}" fill="#94a3b8" font-size="11" text-anchor="middle" transform="rotate(-90 12 {(H) // 2})">Gap (pp)</text>
  <!-- Legend -->
  <rect x="{pad_l}" y="{H - pad_b + 28}" width="14" height="3" fill="#C74634"/>
  <text x="{pad_l + 18}" y="{H - pad_b + 33}" fill="#94a3b8" font-size="10">Sim-Real Gap</text>
  <rect x="{pad_l + 120}" y="{H - pad_b + 28}" width="14" height="3" fill="#f97316"/>
  <text x="{pad_l + 134}" y="{H - pad_b + 33}" fill="#94a3b8" font-size="10">Technique Applied</text>
  <rect x="{pad_l + 270}" y="{H - pad_b + 28}" width="14" height="3" fill="#22c55e" stroke-dasharray="4,3"/>
  <text x="{pad_l + 284}" y="{H - pad_b + 33}" fill="#94a3b8" font-size="10">Target &lt;5pp</text>
</svg>"""
    return svg


def build_radar_svg() -> str:
    W, H = 520, 340
    cx, cy = 260, 175
    R = 130
    dims = RADAR_DIMS
    n = len(dims)

    colors = {"v1": "#64748b", "v2": "#38bdf8", "v3": "#C74634"}
    labels = [d[0].replace("_", " ") for d in dims]

    def polar(i, frac):
        angle = math.pi / 2 - 2 * math.pi * i / n
        r = frac * R
        return cx + r * math.cos(angle), cy - r * math.sin(angle)

    # Grid rings
    rings = ""
    for frac in [0.25, 0.5, 0.75, 1.0]:
        pts = " ".join(f"{polar(i, frac)[0]:.1f},{polar(i, frac)[1]:.1f}" for i in range(n))
        pts += f" {polar(0, frac)[0]:.1f},{polar(0, frac)[1]:.1f}"
        rings += f'<polyline points="{pts}" fill="none" stroke="#1e293b" stroke-width="1"/>'
        label_v = int(frac * 100)
        lx, ly = polar(1, frac)
        rings += f'<text x="{lx + 4:.1f}" y="{ly:.1f}" fill="#475569" font-size="9">{label_v}</text>'

    # Spokes
    spokes = ""
    for i in range(n):
        ex, ey = polar(i, 1.0)
        spokes += f'<line x1="{cx}" y1="{cy}" x2="{ex:.1f}" y2="{ey:.1f}" stroke="#1e293b" stroke-width="1"/>'
        lx, ly = polar(i, 1.18)
        spokes += f'<text x="{lx:.1f}" y="{ly:.1f}" fill="#94a3b8" font-size="10" text-anchor="middle">{labels[i]}</text>'

    # Version polygons
    polys = ""
    for ver, color in colors.items():
        pts = " ".join(f"{polar(i, dims[i][1][ver] / 100)[0]:.1f},{polar(i, dims[i][1][ver] / 100)[1]:.1f}" for i in range(n))
        p0x, p0y = polar(0, dims[0][1][ver] / 100)
        pts += f" {p0x:.1f},{p0y:.1f}"
        polys += f'<polyline points="{pts}" fill="{color}" fill-opacity="0.12" stroke="{color}" stroke-width="2"/>'

    # Legend
    legend = ""
    lx0 = 30
    for i, (ver, color) in enumerate(colors.items()):
        legend += f'<rect x="{lx0 + i * 100}" y="{H - 22}" width="12" height="12" fill="{color}"/>'
        legend += f'<text x="{lx0 + i * 100 + 16}" y="{H - 11}" fill="#94a3b8" font-size="11">{ver.upper()}</text>'

    svg = f"""
<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg" style="background:#0f172a;border-radius:8px">
  <text x="{W // 2}" y="20" fill="#e2e8f0" font-size="13" text-anchor="middle" font-weight="bold">Domain Adaptation Radar — v1 vs v2 vs v3</text>
  {rings}
  {spokes}
  {polys}
  {legend}
</svg>"""
    return svg


# ---------------------------------------------------------------------------
# HTML page
# ---------------------------------------------------------------------------

def build_html() -> str:
    gap_svg    = build_gap_trajectory_svg()
    radar_svg  = build_radar_svg()
    m = KEY_METRICS
    rows = "".join(
        f'<tr><td style="color:#94a3b8;padding:6px 12px">{k}</td><td style="color:#e2e8f0;padding:6px 12px">{v}</td></tr>'
        for k, v in m.items()
    )
    technique_rows = "".join(
        f'<tr><td style="color:#94a3b8;padding:4px 10px">{t}</td>'
        f'<td><div style="width:{pp*8}px;height:14px;background:#C74634;border-radius:3px;display:inline-block"></div></td>'
        f'<td style="color:#f97316;padding:4px 8px">-{pp} pp</td></tr>'
        for t, pp in TECHNIQUE_CONTRIBUTIONS
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Sim-to-Real v3 | Port 8320</title>
<style>
  body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',sans-serif}}
  h1{{color:#C74634;text-align:center;margin:24px 0 4px}}
  .subtitle{{text-align:center;color:#38bdf8;font-size:13px;margin-bottom:24px}}
  .grid{{display:grid;grid-template-columns:1fr 1fr;gap:20px;padding:0 24px 24px}}
  .card{{background:#1e293b;border-radius:10px;padding:18px}}
  .card h2{{color:#38bdf8;font-size:14px;margin:0 0 12px}}
  table{{width:100%;border-collapse:collapse}}
  tr:hover td{{background:#263447}}
  .badge{{display:inline-block;background:#C74634;color:#fff;border-radius:4px;padding:2px 8px;font-size:11px}}
  .full{{grid-column:1/-1}}
</style>
</head>
<body>
<h1>Sim-to-Real Transfer v3</h1>
<p class="subtitle">Progressive Domain Adaptation Dashboard &mdash; Port 8320</p>
<div class="grid">
  <div class="card full">
    <h2>Gap Closing Trajectory (Jan&ndash;Jun 2026)</h2>
    {gap_svg}
  </div>
  <div class="card full">
    <h2>Domain Adaptation Radar</h2>
    {radar_svg}
  </div>
  <div class="card">
    <h2>Key Metrics</h2>
    <table>{rows}</table>
  </div>
  <div class="card">
    <h2>Technique Contributions to Gap Closure</h2>
    <table>{technique_rows}</table>
  </div>
</div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

if USE_FASTAPI:
    app = FastAPI(title="Sim-to-Real v3", version="3.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return HTMLResponse(content=build_html())

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "sim_to_real_v3", "port": 8320}

    @app.get("/metrics")
    async def metrics():
        return KEY_METRICS

    @app.get("/gap_data")
    async def gap_data():
        return [
            {"week": w, "sim_sr": s, "real_sr": r, "gap": round(s - r, 1), "annotation": a}
            for w, s, r, a in MONTHLY_GAP_DATA
        ]

else:
    # Fallback: stdlib http.server
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = build_html().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        def log_message(self, *_): pass


if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8320)
    else:
        server = HTTPServer(("0.0.0.0", 8320), Handler)
        print("Serving sim_to_real_v3 on http://0.0.0.0:8320 (stdlib fallback)")
        server.serve_forever()
