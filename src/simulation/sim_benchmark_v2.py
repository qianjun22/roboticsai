"""Sim Benchmark v2 Service — port 8349

Comprehensive simulation environment benchmark v2 with NVIDIA-certified test
protocols. Compares Genesis / Isaac_Sim / PyBullet / MuJoCo / RoboSuite across
physics accuracy, rendering quality, speed, API compatibility, cost, and
NVIDIA support dimensions.
"""

import math
import random
import json
from datetime import datetime

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    _USE_FASTAPI = True
except ImportError:
    _USE_FASTAPI = False

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

ENGINES = [
    {
        "name":              "Isaac_Sim",
        "physics_accuracy":  0.91,
        "rendering_quality": 0.95,
        "speed":             0.42,  # normalised 0-1 (40 fps / 240 fps max)
        "api_compatibility": 0.88,
        "cost":              0.35,  # inverted: lower cost → higher bar
        "nvidia_support":    1.00,
        "fps":               40,
        "cost_per_1k":       0.17,
        "quality_score":     0.91,
        "certified":         True,
        "use_case":          "Qualitative eval, sim-to-real transfer",
        "color":             "#38bdf8",
    },
    {
        "name":              "Genesis",
        "physics_accuracy":  0.79,
        "rendering_quality": 0.73,
        "speed":             0.98,  # 94fps -> near max
        "api_compatibility": 0.82,
        "cost":              0.88,  # cheap
        "nvidia_support":    0.70,
        "fps":               94,
        "cost_per_1k":       0.12,
        "quality_score":     0.79,
        "certified":         False,
        "use_case":          "SDG volume generation (recommended)",
        "color":             "#34d399",
    },
    {
        "name":              "PyBullet",
        "physics_accuracy":  0.61,
        "rendering_quality": 0.45,
        "speed":             1.00,  # 180fps max in set
        "api_compatibility": 0.70,
        "cost":              1.00,  # free
        "nvidia_support":    0.30,
        "fps":               180,
        "cost_per_1k":       0.08,
        "quality_score":     0.61,
        "certified":         False,
        "use_case":          "Rapid prototyping, CI tests",
        "color":             "#facc15",
    },
    {
        "name":              "MuJoCo",
        "physics_accuracy":  0.85,
        "rendering_quality": 0.68,
        "speed":             0.82,  # ~78fps
        "api_compatibility": 0.75,
        "cost":              0.80,
        "nvidia_support":    0.50,
        "fps":               78,
        "cost_per_1k":       0.09,
        "quality_score":     0.85,
        "certified":         False,
        "use_case":          "Physics research, contact-rich tasks",
        "color":             "#c084fc",
    },
    {
        "name":              "RoboSuite",
        "physics_accuracy":  0.80,
        "rendering_quality": 0.72,
        "speed":             0.60,  # ~57fps
        "api_compatibility": 0.92,
        "cost":              0.75,
        "nvidia_support":    0.55,
        "fps":               57,
        "cost_per_1k":       0.11,
        "quality_score":     0.80,
        "certified":         False,
        "use_case":          "Manipulation benchmarks, Gym compat",
        "color":             "#f97316",
    },
]

DIMENSIONS = ["physics_accuracy", "rendering_quality", "speed", "api_compatibility", "cost", "nvidia_support"]
DIM_LABELS  = ["Physics", "Rendering", "Speed", "API Compat", "Cost", "NVIDIA"]

METRICS = {
    "engines_evaluated":         5,
    "dimensions":                6,
    "nvidia_certified":          "Isaac_Sim",
    "recommended_sdg_volume":    "Genesis (0.79 quality, $0.12/1k, 94fps)",
    "recommended_qual_eval":     "Isaac_Sim (0.91 quality, NVIDIA-certified)",
    "fastest_engine":            "PyBullet (180fps, $0.08/1k)",
    "best_quality_cost_ratio":   "Genesis (6.58)",
    "protocol_version":          "v2.1-NVIDIA",
    "benchmark_date":            datetime.utcnow().strftime("%Y-%m-%d"),
}

# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------

def _radar_svg() -> str:
    cx, cy, r = 300, 200, 130
    n = len(DIMENSIONS)
    # axis endpoints
    axes = []
    for i in range(n):
        angle = math.radians(-90 + i * 360 / n)
        axes.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))

    def _poly(engine):
        pts = []
        for i, dim in enumerate(DIMENSIONS):
            val = engine[dim]
            angle = math.radians(-90 + i * 360 / n)
            px = cx + r * val * math.cos(angle)
            py = cy + r * val * math.sin(angle)
            pts.append(f"{px:.1f},{py:.1f}")
        return " ".join(pts)

    # grid circles
    grid = ""
    for level in [0.25, 0.5, 0.75, 1.0]:
        pts = []
        for i in range(n):
            angle = math.radians(-90 + i * 360 / n)
            pts.append(f"{cx + r*level*math.cos(angle):.1f},{cy + r*level*math.sin(angle):.1f}")
        grid += f'<polygon points="{" ".join(pts)}" fill="none" stroke="#334155" stroke-width="1"/>'

    # axis lines + labels
    axis_lines = ""
    for i, (ax, ay) in enumerate(axes):
        axis_lines += f'<line x1="{cx}" y1="{cy}" x2="{ax:.1f}" y2="{ay:.1f}" stroke="#475569" stroke-width="1"/>'
        lx = cx + (r + 20) * math.cos(math.radians(-90 + i * 360 / n))
        ly = cy + (r + 20) * math.sin(math.radians(-90 + i * 360 / n))
        axis_lines += f'<text x="{lx:.1f}" y="{ly:.1f}" fill="#94a3b8" font-size="9" text-anchor="middle" font-family="monospace">{DIM_LABELS[i]}</text>'

    # engine polygons
    polys = ""
    for eng in ENGINES:
        polys += f'<polygon points="{_poly(eng)}" fill="{eng["color"]}" fill-opacity="0.15" stroke="{eng["color"]}" stroke-width="1.5"/>'

    # legend
    legend = ""
    for i, eng in enumerate(ENGINES):
        lx = 20 + (i % 3) * 185
        ly = 360 + (i // 3) * 18
        legend += (
            f'<rect x="{lx}" y="{ly - 9}" width="12" height="12" fill="{eng["color"]}" rx="2"/>'
            f'<text x="{lx + 16}" y="{ly}" fill="#cbd5e1" font-size="9" font-family="monospace">{eng["name"]}</text>'
        )

    return f"""
<svg viewBox="0 0 600 400" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:600px">
  <rect width="600" height="400" fill="#0f172a" rx="8"/>
  <text x="300" y="22" fill="#e2e8f0" font-size="13" text-anchor="middle" font-family="monospace" font-weight="bold">Sim Engine Comparison Radar</text>
  <text x="300" y="37" fill="#94a3b8" font-size="9" text-anchor="middle" font-family="monospace">5 Engines × 6 Dimensions · NVIDIA-Certified Protocol v2.1</text>
  {grid}
  {axis_lines}
  {polys}
  {legend}
</svg>"""


def _frontier_svg() -> str:
    # x-axis: cost_per_1k (0.05 → 0.20), y-axis: quality_score (0.5 → 1.0)
    W, H = 560, 320
    PAD_L, PAD_R, PAD_T, PAD_B = 70, 30, 40, 50
    plot_w = W - PAD_L - PAD_R
    plot_h = H - PAD_T - PAD_B
    x_min, x_max = 0.06, 0.20
    y_min, y_max = 0.55, 1.00

    def _px(cost):
        return PAD_L + (cost - x_min) / (x_max - x_min) * plot_w

    def _py(qual):
        return PAD_T + (1 - (qual - y_min) / (y_max - y_min)) * plot_h

    # sort by cost for pareto frontier (lower cost better)
    sorted_eng = sorted(ENGINES, key=lambda e: e["cost_per_1k"])
    # Pareto: max quality seen so far sweeping from lowest cost
    pareto_pts = []
    best_q = 0.0
    for e in sorted_eng:
        if e["quality_score"] >= best_q:
            best_q = e["quality_score"]
            pareto_pts.append((e["cost_per_1k"], e["quality_score"]))
    pareto_path = " ".join(
        f"{'M' if i == 0 else 'L'}{_px(p[0]):.1f},{_py(p[1]):.1f}"
        for i, p in enumerate(pareto_pts)
    )

    dots = ""
    for eng in ENGINES:
        px = _px(eng["cost_per_1k"])
        py = _py(eng["quality_score"])
        dots += f'<circle cx="{px:.1f}" cy="{py:.1f}" r="8" fill="{eng["color"]}" stroke="#0f172a" stroke-width="2"/>'
        label_dy = -14 if eng["name"] not in ("PyBullet",) else 18
        dots += f'<text x="{px:.1f}" y="{py + label_dy:.1f}" fill="{eng["color"]}" font-size="9" text-anchor="middle" font-family="monospace">{eng["name"]}</text>'

    # Recommended annotations
    isaac = next(e for e in ENGINES if e["name"] == "Isaac_Sim")
    genesis = next(e for e in ENGINES if e["name"] == "Genesis")
    annots = (
        f'<rect x="{_px(isaac["cost_per_1k"]) + 10:.1f}" y="{_py(isaac["quality_score"]) - 16:.1f}" '
        f'width="110" height="14" fill="#1e293b" rx="3"/>'
        f'<text x="{_px(isaac["cost_per_1k"]) + 15:.1f}" y="{_py(isaac["quality_score"]) - 5:.1f}" '
        f'fill="#38bdf8" font-size="8" font-family="monospace">Recommended: qual eval</text>'
        f'<rect x="{_px(genesis["cost_per_1k"]) + 10:.1f}" y="{_py(genesis["quality_score"]) - 16:.1f}" '
        f'width="110" height="14" fill="#1e293b" rx="3"/>'
        f'<text x="{_px(genesis["cost_per_1k"]) + 15:.1f}" y="{_py(genesis["quality_score"]) - 5:.1f}" '
        f'fill="#34d399" font-size="8" font-family="monospace">Recommended: SDG volume</text>'
    )

    # axes
    axes_svg = (
        f'<line x1="{PAD_L}" y1="{PAD_T}" x2="{PAD_L}" y2="{PAD_T + plot_h}" stroke="#475569" stroke-width="1"/>'
        f'<line x1="{PAD_L}" y1="{PAD_T + plot_h}" x2="{PAD_L + plot_w}" y2="{PAD_T + plot_h}" stroke="#475569" stroke-width="1"/>'
        f'<text x="{PAD_L + plot_w//2}" y="{H - 8}" fill="#94a3b8" font-size="9" text-anchor="middle" font-family="monospace">Cost per 1k demos ($)</text>'
        f'<text x="14" y="{PAD_T + plot_h//2}" fill="#94a3b8" font-size="9" text-anchor="middle" font-family="monospace" transform="rotate(-90 14 {PAD_T + plot_h//2})">Quality Score</text>'
    )
    # tick labels
    ticks = ""
    for v in [0.08, 0.10, 0.12, 0.14, 0.17]:
        ticks += f'<text x="{_px(v):.1f}" y="{PAD_T + plot_h + 14}" fill="#475569" font-size="8" text-anchor="middle" font-family="monospace">{v:.2f}</text>'
    for v in [0.6, 0.7, 0.8, 0.9, 1.0]:
        ticks += f'<text x="{PAD_L - 6}" y="{_py(v) + 4:.1f}" fill="#475569" font-size="8" text-anchor="end" font-family="monospace">{v:.1f}</text>'

    return f"""
<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:{W}px">
  <rect width="{W}" height="{H}" fill="#0f172a" rx="8"/>
  <text x="{W//2}" y="22" fill="#e2e8f0" font-size="13" text-anchor="middle" font-family="monospace" font-weight="bold">Performance vs Cost Frontier</text>
  <text x="{W//2}" y="37" fill="#94a3b8" font-size="9" text-anchor="middle" font-family="monospace">Pareto Frontier — lower cost · higher quality = better</text>
  {axes_svg}
  {ticks}
  <path d="{pareto_path}" fill="none" stroke="#facc15" stroke-width="1.5" stroke-dasharray="6,3"/>
  {dots}
  {annots}
</svg>"""


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def _dashboard_html() -> str:
    ts = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    metrics_rows = "".join(
        f'<tr><td style="color:#94a3b8;padding:4px 12px">{k}</td>'
        f'<td style="color:#e2e8f0;padding:4px 12px">{v}</td></tr>'
        for k, v in METRICS.items()
    )
    engine_rows = "".join(
        f'<tr>'
        f'<td style="color:{e["color"]};padding:4px 10px">{e["name"]}</td>'
        f'<td style="color:#e2e8f0;padding:4px 10px">{e["fps"]} fps</td>'
        f'<td style="color:#e2e8f0;padding:4px 10px">${e["cost_per_1k"]:.2f}/1k</td>'
        f'<td style="color:#e2e8f0;padding:4px 10px">{e["quality_score"]:.2f}</td>'
        f'<td style="color:{"#34d399" if e["certified"] else "#475569"};padding:4px 10px">{"Yes" if e["certified"] else "No"}</td>'
        f'<td style="color:#94a3b8;padding:4px 10px;font-size:0.75rem">{e["use_case"]}</td>'
        f'</tr>'
        for e in ENGINES
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Sim Benchmark v2 — Port 8349</title>
  <style>
    body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:'Courier New',monospace;padding:24px}}
    h1{{color:#C74634;font-size:1.4rem;margin-bottom:4px}}
    h2{{color:#38bdf8;font-size:1rem;margin:24px 0 8px}}
    .badge{{display:inline-block;background:#1e293b;border:1px solid #334155;border-radius:6px;
            padding:2px 10px;font-size:0.75rem;color:#94a3b8;margin-right:6px}}
    .card{{background:#1e293b;border:1px solid #334155;border-radius:10px;padding:20px;margin-bottom:24px}}
    table{{border-collapse:collapse;width:100%}}
    tr:nth-child(even){{background:#0f172a}}
    th{{color:#38bdf8;padding:4px 10px;text-align:left;font-size:0.8rem;border-bottom:1px solid #334155}}
  </style>
</head>
<body>
  <h1>Sim Benchmark v2 Dashboard</h1>
  <span class="badge">NVIDIA-Certified Protocol v2.1</span>
  <span class="badge">Port 8349</span>
  <span class="badge">{ts}</span>

  <h2>SVG 1 — Sim Engine Comparison Radar</h2>
  <div class="card">{_radar_svg()}</div>

  <h2>SVG 2 — Performance vs Cost Frontier</h2>
  <div class="card">{_frontier_svg()}</div>

  <h2>Engine Summary Table</h2>
  <div class="card">
    <table>
      <thead><tr>
        <th>Engine</th><th>Speed</th><th>Cost/1k</th><th>Quality</th><th>NVIDIA Cert</th><th>Use Case</th>
      </tr></thead>
      <tbody>{engine_rows}</tbody>
    </table>
  </div>

  <h2>Key Metrics</h2>
  <div class="card">
    <table>{metrics_rows}</table>
  </div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

if _USE_FASTAPI:
    app = FastAPI(
        title="Sim Benchmark v2",
        description="NVIDIA-certified simulation environment benchmark",
        version="2.0.0",
    )

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return HTMLResponse(content=_dashboard_html())

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "sim_benchmark_v2", "port": 8349}

    @app.get("/engines")
    async def engines():
        return {"engines": ENGINES}

    @app.get("/metrics")
    async def metrics():
        return METRICS

    @app.get("/recommendation")
    async def recommendation():
        return {
            "sdg_volume":   {"engine": "Genesis",   "reason": "best cost/speed — $0.12/1k, 94fps, quality 0.79"},
            "qual_eval":    {"engine": "Isaac_Sim",  "reason": "best quality + NVIDIA-certified — 0.91, $0.17/1k"},
            "ci_tests":     {"engine": "PyBullet",   "reason": "fastest + free — 180fps, $0.08/1k"},
            "physics_research": {"engine": "MuJoCo", "reason": "best physics accuracy for contact-rich tasks"},
        }

else:
    import http.server
    import socketserver

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            body = _dashboard_html().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        def log_message(self, fmt, *args):
            pass


if __name__ == "__main__":
    if _USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8349)
    else:
        with socketserver.TCPServer(("", 8349), _Handler) as httpd:
            print("Serving on http://0.0.0.0:8349 (stdlib fallback)")
            httpd.serve_forever()
