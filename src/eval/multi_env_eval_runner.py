#!/usr/bin/env python3
"""
Multi-Environment Eval Runner — FastAPI service on port 8229
Evaluates GR00T policy across multiple simulation environments simultaneously.
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

import math
import json
from datetime import datetime

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

ENVIRONMENTS = ["Genesis", "Isaac Sim", "LIBERO", "PyBullet"]
POLICIES = ["dagger_r9", "groot_v2", "groot_v3_progress"]

# SR per (env, policy)
SR_DATA = {
    "Genesis":    {"dagger_r9": 0.62, "groot_v2": 0.74, "groot_v3_progress": 0.77},
    "Isaac Sim":  {"dagger_r9": 0.59, "groot_v2": 0.72, "groot_v3_progress": 0.75},
    "LIBERO":     {"dagger_r9": 0.71, "groot_v2": 0.84, "groot_v3_progress": 0.83},
    "PyBullet":   {"dagger_r9": 0.48, "groot_v2": 0.71, "groot_v3_progress": 0.69},
}

# Difficulty tiers
DIFFICULTY = {
    "LIBERO": ("Easiest", "#34d399"),
    "Genesis": ("Moderate", "#fbbf24"),
    "Isaac Sim": ("Challenging", "#f97316"),
    "PyBullet": ("Hardest", "#f87171"),
}

# Radar metrics per environment (0.0 – 1.0)
# sr, latency, stability, generalization, cost_efficiency
RADAR_DATA = {
    "Genesis":    {"sr": 0.71, "latency": 0.82, "stability": 0.75, "generalization": 0.68, "cost_efficiency": 0.88},
    "Isaac Sim":  {"sr": 0.69, "latency": 0.55, "stability": 0.78, "generalization": 0.88, "cost_efficiency": 0.52},
    "LIBERO":     {"sr": 0.84, "latency": 0.91, "stability": 0.86, "generalization": 0.65, "cost_efficiency": 0.95},
    "PyBullet":   {"sr": 0.63, "latency": 0.94, "stability": 0.60, "generalization": 0.58, "cost_efficiency": 0.97},
}
RADAR_METRICS = ["sr", "latency", "stability", "generalization", "cost_efficiency"]
RADAR_COLORS = {"Genesis": "#38bdf8", "Isaac Sim": "#f97316", "LIBERO": "#34d399", "PyBullet": "#f87171"}

ENSEMBLE_SCORE = 0.752
RECOMMENDED_ENV = "Isaac Sim"

# Correlation matrix (symmetric, 4x4)
CORR_MATRIX = [
    [1.00, 0.87, 0.72, 0.65],
    [0.87, 1.00, 0.69, 0.61],
    [0.72, 0.69, 1.00, 0.54],
    [0.65, 0.61, 0.54, 1.00],
]


def _metric_label(m: str) -> str:
    return m.replace("_", " ").title()


def build_grouped_bar_svg() -> str:
    """SVG 1: Grouped bar chart of SR across 4 environments for 3 policy checkpoints."""
    W, H = 700, 340
    pad_l, pad_r, pad_t, pad_b = 70, 20, 50, 80
    chart_w = W - pad_l - pad_r
    chart_h = H - pad_t - pad_b

    n_envs = len(ENVIRONMENTS)
    n_pols = len(POLICIES)
    group_w = chart_w / n_envs
    bar_w = group_w * 0.22
    gap_bar = group_w * 0.04
    pol_colors = ["#38bdf8", "#C74634", "#34d399"]

    def y_bar(v): return pad_t + chart_h - (v * chart_h)
    def bar_h_px(v): return v * chart_h

    bars = ""
    # Y-axis grid
    for tick in [0.2, 0.4, 0.6, 0.8, 1.0]:
        gy = y_bar(tick)
        bars += f'<line x1="{pad_l}" y1="{gy:.1f}" x2="{pad_l+chart_w}" y2="{gy:.1f}" stroke="#334155" stroke-width="1"/>\n'
        bars += f'<text x="{pad_l-8}" y="{gy+4:.1f}" text-anchor="end" font-size="10" fill="#64748b">{tick:.1f}</text>\n'

    for gi, env in enumerate(ENVIRONMENTS):
        gx = pad_l + gi * group_w
        center_x = gx + group_w / 2
        diff_label, diff_color = DIFFICULTY[env]
        # Difficulty badge
        bars += f'<rect x="{center_x-32:.1f}" y="{pad_t+chart_h+18}" width="64" height="16" rx="4" fill="{diff_color}" opacity="0.25"/>\n'
        bars += f'<text x="{center_x:.1f}" y="{pad_t+chart_h+29}" text-anchor="middle" font-size="10" fill="{diff_color}">{diff_label}</text>\n'
        # Env name
        bars += f'<text x="{center_x:.1f}" y="{pad_t+chart_h+50}" text-anchor="middle" font-size="12" font-weight="600" fill="#94a3b8">{env}</text>\n'

        for pi, pol in enumerate(POLICIES):
            bx = gx + pi * (bar_w + gap_bar) + gap_bar
            val = SR_DATA[env][pol]
            bh = bar_h_px(val)
            by = y_bar(val)
            bars += f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bar_w:.1f}" height="{bh:.1f}" fill="{pol_colors[pi]}" rx="2" opacity="0.9"/>\n'
            bars += f'<text x="{bx+bar_w/2:.1f}" y="{by-4:.1f}" text-anchor="middle" font-size="9" fill="{pol_colors[pi]}">{val:.2f}</text>\n'

    # Legend
    lx = pad_l
    for pi, pol in enumerate(POLICIES):
        bars += f'<rect x="{lx}" y="8" width="14" height="10" fill="{pol_colors[pi]}" rx="2"/>\n'
        bars += f'<text x="{lx+17}" y="17" font-size="10" fill="#94a3b8">{pol}</text>\n'
        lx += 145

    title = f'<text x="{W//2}" y="38" text-anchor="middle" font-size="14" font-weight="700" fill="#f8fafc">SR per Environment &amp; Policy Checkpoint</text>'
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#1e293b;border-radius:10px">
{title}
{bars}
</svg>'''


def build_radar_svg() -> str:
    """SVG 2: Radar chart of 5 evaluation metrics per environment."""
    W, H = 520, 420
    cx, cy, r = W // 2, H // 2 + 10, 140
    n = len(RADAR_METRICS)
    angles = [math.pi / 2 + 2 * math.pi * i / n for i in range(n)]

    def polar(val, angle, radius=r):
        return cx + val * radius * math.cos(angle), cy - val * radius * math.sin(angle)

    grid_svg = ""
    # Grid rings
    for ring in [0.25, 0.5, 0.75, 1.0]:
        pts = " ".join(f"{polar(ring, a)[0]:.1f},{polar(ring, a)[1]:.1f}" for a in angles)
        grid_svg += f'<polygon points="{pts}" fill="none" stroke="#334155" stroke-width="1"/>\n'
        grid_svg += f'<text x="{cx+ring*r+4:.1f}" y="{cy+4}" font-size="9" fill="#475569">{ring:.0%}</text>\n'
    # Spokes
    for a in angles:
        ex, ey = polar(1.0, a)
        grid_svg += f'<line x1="{cx}" y1="{cy}" x2="{ex:.1f}" y2="{ey:.1f}" stroke="#334155" stroke-width="1"/>\n'
    # Metric labels
    for i, (m, a) in enumerate(zip(RADAR_METRICS, angles)):
        lx, ly = polar(1.18, a)
        grid_svg += f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="middle" dominant-baseline="middle" font-size="11" fill="#94a3b8" font-weight="600">{_metric_label(m)}</text>\n'

    # Env polygons
    polys = ""
    for env in ENVIRONMENTS:
        vals = [RADAR_DATA[env][m] for m in RADAR_METRICS]
        pts = " ".join(f"{polar(v, a)[0]:.1f},{polar(v, a)[1]:.1f}" for v, a in zip(vals, angles))
        col = RADAR_COLORS[env]
        polys += f'<polygon points="{pts}" fill="{col}" fill-opacity="0.12" stroke="{col}" stroke-width="2"/>\n'
        for v, a in zip(vals, angles):
            px, py = polar(v, a)
            polys += f'<circle cx="{px:.1f}" cy="{py:.1f}" r="4" fill="{col}"/>\n'

    # Legend
    legend_y = H - 30
    lx = 20
    for env in ENVIRONMENTS:
        col = RADAR_COLORS[env]
        diff_label, _ = DIFFICULTY[env]
        polys += f'<rect x="{lx}" y="{legend_y-10}" width="12" height="12" fill="{col}" rx="2"/>\n'
        polys += f'<text x="{lx+15}" y="{legend_y}" font-size="10" fill="{col}">{env}</text>\n'
        lx += 120

    title = f'<text x="{W//2}" y="22" text-anchor="middle" font-size="14" font-weight="700" fill="#f8fafc">Eval Metrics Radar — Per Environment</text>'
    rec = f'<text x="{W//2}" y="{H-10}" text-anchor="middle" font-size="11" fill="#fbbf24">Recommended primary eval env: {RECOMMENDED_ENV} (best real-world transfer)</text>'
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#1e293b;border-radius:10px">
{title}{grid_svg}{polys}{rec}
</svg>'''


def build_corr_table() -> str:
    """HTML table for environment correlation matrix."""
    header = "<tr><th></th>" + "".join(f"<th>{e}</th>" for e in ENVIRONMENTS) + "</tr>"
    rows = ""
    for i, env_r in enumerate(ENVIRONMENTS):
        cells = f"<td style='font-weight:700;color:#94a3b8'>{env_r}</td>"
        for j, env_c in enumerate(ENVIRONMENTS):
            v = CORR_MATRIX[i][j]
            intensity = int(v * 120)
            bg = f"rgb({40+intensity},{60+intensity//2},{80+intensity//3})" if i != j else "#1e3a5f"
            cells += f"<td style='background:{bg};color:#f8fafc;font-size:13px;font-weight:600'>{v:.2f}</td>"
        rows += f"<tr>{cells}</tr>"
    return f"""<table style='border-collapse:collapse;width:100%'>
<thead style='color:#64748b;font-size:12px'>{header}</thead>
<tbody>{rows}</tbody>
</table>"""


def build_html() -> str:
    svg1 = build_grouped_bar_svg()
    svg2 = build_radar_svg()
    corr_tbl = build_corr_table()

    # Per-env summary cards
    cards_html = ""
    for env in ENVIRONMENTS:
        diff_label, diff_color = DIFFICULTY[env]
        best_pol = max(POLICIES, key=lambda p: SR_DATA[env][p])
        best_sr = SR_DATA[env][best_pol]
        radar = RADAR_DATA[env]
        cards_html += f"""
        <div style='background:#1e293b;border-radius:12px;padding:18px;border:1px solid #334155'>
            <div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:8px'>
                <span style='font-size:16px;font-weight:700;color:#38bdf8'>{env}</span>
                <span style='background:{diff_color};color:#0f172a;border-radius:6px;padding:2px 8px;font-size:11px;font-weight:700'>{diff_label}</span>
            </div>
            <div style='color:#f8fafc;font-size:22px;font-weight:800;margin-bottom:4px'>SR {best_sr:.2f} <span style='font-size:12px;color:#94a3b8'>({best_pol})</span></div>
            <div style='font-size:12px;color:#64748b;margin-top:4px'>
                Stability: {radar['stability']:.2f} &nbsp;|&nbsp; Generalization: {radar['generalization']:.2f}<br/>
                Latency: {radar['latency']:.2f} &nbsp;|&nbsp; Cost Eff: {radar['cost_efficiency']:.2f}
            </div>
        </div>"""

    return f"""<!DOCTYPE html>
<html lang='en'>
<head>
  <meta charset='UTF-8'/>
  <meta name='viewport' content='width=device-width, initial-scale=1.0'/>
  <title>Multi-Env Eval Runner — Port 8229</title>
  <style>
    * {{box-sizing:border-box;margin:0;padding:0;}}
    body {{background:#0f172a;color:#f8fafc;font-family:'Inter',system-ui,sans-serif;padding:24px;}}
    h1 {{font-size:26px;font-weight:800;color:#38bdf8;margin-bottom:4px;}}
    .subtitle {{color:#64748b;font-size:14px;margin-bottom:24px;}}
    .badge {{display:inline-block;background:#C74634;color:#fff;border-radius:6px;padding:2px 10px;font-size:12px;font-weight:700;margin-right:8px;}}
    .badge-blue {{background:#0ea5e9;}}
    .section-title {{font-size:17px;font-weight:700;color:#e2e8f0;margin:28px 0 12px;}}
    .grid-cards {{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:16px;margin-bottom:32px;}}
    .stat-row {{display:flex;gap:24px;flex-wrap:wrap;margin-bottom:28px;}}
    .stat {{background:#1e293b;border:1px solid #334155;border-radius:10px;padding:16px 24px;min-width:160px;}}
    .stat-val {{font-size:28px;font-weight:800;color:#38bdf8;}}
    .stat-lbl {{font-size:12px;color:#64748b;margin-top:2px;}}
    .chart-row {{display:flex;gap:20px;flex-wrap:wrap;margin-bottom:28px;}}
    .corr-box {{background:#1e293b;border:1px solid #334155;border-radius:12px;padding:20px;margin-bottom:28px;overflow-x:auto;}}
    footer {{color:#334155;font-size:12px;margin-top:32px;text-align:center;}}
    table th,table td {{padding:8px 14px;text-align:center;border:1px solid #1e293b;}}
    table thead th {{background:#0f172a;color:#64748b;}}
  </style>
</head>
<body>
  <span class='badge'>OCI Robot Cloud</span>
  <span class='badge badge-blue'>Port 8229</span>
  <h1>Multi-Environment Eval Runner</h1>
  <div class='subtitle'>GR00T policy evaluated across Genesis / Isaac Sim / LIBERO / PyBullet simultaneously &mdash; Recommended: {RECOMMENDED_ENV}</div>

  <div class='stat-row'>
    <div class='stat'><div class='stat-val'>{ENSEMBLE_SCORE}</div><div class='stat-lbl'>Ensemble Eval Score</div></div>
    <div class='stat'><div class='stat-val' style='color:#34d399'>0.84</div><div class='stat-lbl'>Best SR (LIBERO)</div></div>
    <div class='stat'><div class='stat-val' style='color:#f87171'>0.71</div><div class='stat-lbl'>Hardest SR (PyBullet)</div></div>
    <div class='stat'><div class='stat-val'>{RECOMMENDED_ENV}</div><div class='stat-lbl'>Primary Eval Env</div></div>
    <div class='stat'><div class='stat-val'>groot_v2</div><div class='stat-lbl'>Most Consistent Policy</div></div>
  </div>

  <div class='section-title'>Success Rate by Environment &amp; Policy</div>
  <div class='chart-row'>
    {svg1}
  </div>

  <div class='section-title'>Evaluation Metrics Radar</div>
  <div class='chart-row'>
    {svg2}
  </div>

  <div class='section-title'>Environment Correlation Matrix</div>
  <div class='corr-box'>
    {corr_tbl}
  </div>

  <div class='section-title'>Environment Summary Cards</div>
  <div class='grid-cards'>
    {cards_html}
  </div>

  <footer>Multi-Env Eval Runner &mdash; OCI Robot Cloud &mdash; {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</footer>
</body>
</html>"""


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

if HAS_FASTAPI:
    app = FastAPI(title="Multi-Env Eval Runner", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return HTMLResponse(content=build_html())

    @app.get("/api/results")
    async def api_results():
        return {
            "sr_data": SR_DATA,
            "radar_data": RADAR_DATA,
            "ensemble_score": ENSEMBLE_SCORE,
            "recommended_env": RECOMMENDED_ENV,
            "difficulty": {k: v[0] for k, v in DIFFICULTY.items()},
            "correlation_matrix": {
                ENVIRONMENTS[i]: {ENVIRONMENTS[j]: CORR_MATRIX[i][j] for j in range(len(ENVIRONMENTS))}
                for i in range(len(ENVIRONMENTS))
            },
            "timestamp": datetime.utcnow().isoformat(),
        }

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "multi_env_eval_runner", "port": 8229}

else:
    from http.server import HTTPServer, BaseHTTPRequestHandler

    class _Handler(BaseHTTPRequestHandler):
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
    if HAS_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8229)
    else:
        print("[multi_env_eval_runner] fastapi not found — falling back to stdlib http.server on port 8229")
        server = HTTPServer(("0.0.0.0", 8229), _Handler)
        print("[multi_env_eval_runner] Serving on http://0.0.0.0:8229")
        server.serve_forever()
