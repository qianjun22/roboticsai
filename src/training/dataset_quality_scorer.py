#!/usr/bin/env python3
"""
Dataset Quality Scorer — FastAPI service on port 8228
Scores training dataset quality across multiple dimensions for GR00T fine-tuning.
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
import json
from datetime import datetime

# ---------------------------------------------------------------------------
# Mock data — realistic GR00T dataset quality metrics
# ---------------------------------------------------------------------------

DATASET_VERSIONS = ["ds_v1", "ds_v2", "ds_v3", "ds_v4"]

# Quality dimensions: completeness, consistency, diversity, balance, noise_level (inverted for score)
QUALITY_DATA = {
    "ds_v1": {"completeness": 0.58, "consistency": 0.62, "diversity": 0.55, "balance": 0.60, "noise_level": 0.71, "overall": 0.61, "sr": 0.42, "n_demos": 210},
    "ds_v2": {"completeness": 0.70, "consistency": 0.74, "diversity": 0.65, "balance": 0.68, "noise_level": 0.78, "overall": 0.71, "sr": 0.55, "n_demos": 450},
    "ds_v3": {"completeness": 0.81, "consistency": 0.83, "diversity": 0.76, "balance": 0.79, "noise_level": 0.86, "overall": 0.81, "sr": 0.67, "n_demos": 780},
    "ds_v4": {"completeness": 0.91, "consistency": 0.88, "diversity": 0.85, "balance": 0.90, "noise_level": 0.92, "overall": 0.89, "sr": 0.78, "n_demos": 1200},
}

DIMENSIONS = ["completeness", "consistency": "consistency", "diversity": "diversity", "balance": "balance", "noise_level": "noise_level"]
DIM_LIST = ["completeness", "consistency", "diversity", "balance", "noise_level"]
DIM_COLORS = ["#38bdf8", "#818cf8", "#34d399", "#fbbf24", "#f472b6"]

PREPROCESS_STEPS = {
    "ds_v1": ["Filter short episodes (<10 frames)", "Re-label gripper states", "Augment with mirroring", "Normalize joint velocities"],
    "ds_v2": ["Balance task distribution", "Remove outlier trajectories (z>3)", "Add wrist-camera views"],
    "ds_v3": ["Minor noise filtering", "Re-index episode IDs"],
    "ds_v4": ["Production-ready — no steps required"],
}

PEARSON_R = 0.96


def _dim_label(d: str) -> str:
    return d.replace("_", " ").title()


def build_stacked_bar_svg() -> str:
    """SVG 1: Horizontal stacked bar chart of quality dimensions per dataset version."""
    W, H = 680, 320
    pad_left, pad_right, pad_top, pad_bottom = 80, 160, 40, 50
    chart_w = W - pad_left - pad_right
    chart_h = H - pad_top - pad_bottom
    bar_h = 38
    gap = 18
    n = len(DATASET_VERSIONS)

    bars_svg = ""
    for i, ds in enumerate(DATASET_VERSIONS):
        y = pad_top + i * (bar_h + gap)
        x_cursor = pad_left
        data = QUALITY_DATA[ds]
        total = sum(data[d] for d in DIM_LIST)
        for j, dim in enumerate(DIM_LIST):
            seg_w = (data[dim] / total) * chart_w
            bars_svg += f'<rect x="{x_cursor:.1f}" y="{y}" width="{seg_w:.1f}" height="{bar_h}" fill="{DIM_COLORS[j]}" opacity="0.88"/>\n'
            if seg_w > 28:
                bars_svg += f'<text x="{x_cursor + seg_w/2:.1f}" y="{y + bar_h/2 + 4:.1f}" text-anchor="middle" font-size="10" fill="#0f172a" font-weight="600">{data[dim]:.2f}</text>\n'
            x_cursor += seg_w
        # overall score label
        bars_svg += f'<text x="{pad_left + chart_w + 8}" y="{y + bar_h/2 + 4:.1f}" font-size="11" fill="#e2e8f0">Q={data["overall"]:.2f} SR={data["sr"]:.2f}</text>\n'
        # ds label
        bars_svg += f'<text x="{pad_left - 8}" y="{y + bar_h/2 + 4:.1f}" text-anchor="end" font-size="12" fill="#94a3b8" font-weight="600">{ds}</text>\n'

    # Legend
    legend_y = H - 22
    lx = pad_left
    for j, dim in enumerate(DIM_LIST):
        bars_svg += f'<rect x="{lx}" y="{legend_y - 10}" width="14" height="10" fill="{DIM_COLORS[j]}" opacity="0.88"/>\n'
        bars_svg += f'<text x="{lx + 17}" y="{legend_y}" font-size="10" fill="#94a3b8">{_dim_label(dim)}</text>\n'
        lx += 110

    title = '<text x="340" y="22" text-anchor="middle" font-size="14" font-weight="700" fill="#f8fafc">Dataset Quality Dimensions (Stacked) — ds_v1 → ds_v4</text>'
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#1e293b;border-radius:10px">
{title}
{bars_svg}
</svg>'''


def build_trend_line_svg() -> str:
    """SVG 2: Line chart of overall quality score trend with SR correlation overlay."""
    W, H = 620, 300
    pad_l, pad_r, pad_t, pad_b = 60, 80, 40, 50
    chart_w = W - pad_l - pad_r
    chart_h = H - pad_t - pad_b

    versions = DATASET_VERSIONS
    quality_scores = [QUALITY_DATA[d]["overall"] for d in versions]
    sr_scores = [QUALITY_DATA[d]["sr"] for d in versions]

    def x_pos(i): return pad_l + (i / (len(versions) - 1)) * chart_w
    def y_q(v): return pad_t + chart_h - ((v - 0.3) / 0.7) * chart_h
    def y_sr(v): return pad_t + chart_h - ((v - 0.2) / 0.7) * chart_h

    # Grid lines
    grid = ""
    for tick in [0.4, 0.5, 0.6, 0.7, 0.8, 0.9]:
        gy = y_q(tick)
        grid += f'<line x1="{pad_l}" y1="{gy:.1f}" x2="{pad_l+chart_w}" y2="{gy:.1f}" stroke="#334155" stroke-width="1"/>\n'
        grid += f'<text x="{pad_l-8}" y="{gy+4:.1f}" text-anchor="end" font-size="10" fill="#64748b">{tick:.1f}</text>\n'

    # X axis labels
    x_labels = ""
    for i, ds in enumerate(versions):
        x_labels += f'<text x="{x_pos(i):.1f}" y="{pad_t+chart_h+18}" text-anchor="middle" font-size="11" fill="#94a3b8">{ds}</text>\n'

    # Quality line
    q_pts = " ".join(f"{x_pos(i):.1f},{y_q(v):.1f}" for i, v in enumerate(quality_scores))
    q_line = f'<polyline points="{q_pts}" fill="none" stroke="#38bdf8" stroke-width="2.5"/>\n'
    q_dots = "".join(f'<circle cx="{x_pos(i):.1f}" cy="{y_q(v):.1f}" r="5" fill="#38bdf8"/>\n<text x="{x_pos(i):.1f}" y="{y_q(v)-10:.1f}" text-anchor="middle" font-size="10" fill="#38bdf8">{v:.2f}</text>\n' for i, v in enumerate(quality_scores))

    # SR line
    sr_pts = " ".join(f"{x_pos(i):.1f},{y_sr(v):.1f}" for i, v in enumerate(sr_scores))
    sr_line = f'<polyline points="{sr_pts}" fill="none" stroke="#C74634" stroke-width="2.5" stroke-dasharray="6,3"/>\n'
    sr_dots = "".join(f'<circle cx="{x_pos(i):.1f}" cy="{y_sr(v):.1f}" r="5" fill="#C74634"/>\n<text x="{x_pos(i):.1f}" y="{y_sr(v)+18:.1f}" text-anchor="middle" font-size="10" fill="#C74634">{v:.2f}</text>\n' for i, v in enumerate(sr_scores))

    # Right axis label for SR
    sr_axis = f'<text x="{pad_l+chart_w+55}" y="{pad_t+chart_h//2}" text-anchor="middle" font-size="10" fill="#C74634" transform="rotate(90 {pad_l+chart_w+55} {pad_t+chart_h//2})">SR</text>\n'
    pearson = f'<text x="{W//2}" y="{H-8}" text-anchor="middle" font-size="11" fill="#fbbf24">Pearson r = {PEARSON_R} — Quality Score is strong predictor of final SR</text>\n'

    legend = f'''<rect x="{pad_l}" y="{pad_t-20}" width="12" height="4" fill="#38bdf8"/>
<text x="{pad_l+15}" y="{pad_t-15}" font-size="10" fill="#38bdf8">Quality Score</text>
<rect x="{pad_l+110}" y="{pad_t-20}" width="12" height="4" fill="#C74634"/>
<text x="{pad_l+125}" y="{pad_t-15}" font-size="10" fill="#C74634">Success Rate (SR)</text>'''

    title = f'<text x="{W//2}" y="18" text-anchor="middle" font-size="14" font-weight="700" fill="#f8fafc">Quality Score vs SR Correlation Trend</text>'

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#1e293b;border-radius:10px">
{title}
{grid}{x_labels}{q_line}{q_dots}{sr_line}{sr_dots}{sr_axis}{pearson}{legend}
</svg>'''


def build_html() -> str:
    svg1 = build_stacked_bar_svg()
    svg2 = build_trend_line_svg()

    # Summary cards
    cards_html = ""
    for ds in DATASET_VERSIONS:
        d = QUALITY_DATA[ds]
        weakest = min(DIM_LIST, key=lambda x: d[x])
        steps = PREPROCESS_STEPS.get(ds, [])
        steps_html = "".join(f"<li style='color:#94a3b8;font-size:13px'>{s}</li>" for s in steps)
        cards_html += f"""
        <div style='background:#1e293b;border-radius:12px;padding:18px;border:1px solid #334155'>
            <div style='font-size:16px;font-weight:700;color:#38bdf8;margin-bottom:8px'>{ds}</div>
            <div style='color:#f8fafc;font-size:24px;font-weight:800;margin-bottom:4px'>{d['overall']:.2f} <span style='font-size:13px;color:#94a3b8'>quality</span></div>
            <div style='color:#C74634;font-size:18px;font-weight:700;margin-bottom:4px'>SR: {d['sr']:.2f}</div>
            <div style='color:#fbbf24;font-size:12px;margin-bottom:6px'>Demos: {d['n_demos']} &nbsp;|&nbsp; Weakest: {_dim_label(weakest)} ({d[weakest]:.2f})</div>
            <ul style='padding-left:16px;margin:0'>{steps_html}</ul>
        </div>"""

    return f"""<!DOCTYPE html>
<html lang='en'>
<head>
  <meta charset='UTF-8'/>
  <meta name='viewport' content='width=device-width, initial-scale=1.0'/>
  <title>Dataset Quality Scorer — Port 8228</title>
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
    footer {{color:#334155;font-size:12px;margin-top:32px;text-align:center;}}
  </style>
</head>
<body>
  <span class='badge'>OCI Robot Cloud</span>
  <span class='badge badge-blue'>Port 8228</span>
  <h1>Dataset Quality Scorer</h1>
  <div class='subtitle'>GR00T fine-tuning dataset quality analysis — Pearson r = {PEARSON_R} between quality score and SR</div>

  <div class='stat-row'>
    <div class='stat'><div class='stat-val'>{PEARSON_R}</div><div class='stat-lbl'>Quality–SR Pearson r</div></div>
    <div class='stat'><div class='stat-val' style='color:#34d399'>0.89</div><div class='stat-lbl'>ds_v4 Quality Score</div></div>
    <div class='stat'><div class='stat-val' style='color:#C74634'>0.78</div><div class='stat-lbl'>ds_v4 Success Rate</div></div>
    <div class='stat'><div class='stat-val'>1,200</div><div class='stat-lbl'>ds_v4 Demo Count</div></div>
    <div class='stat'><div class='stat-val'>+0.28</div><div class='stat-lbl'>SR Gain v1 → v4</div></div>
  </div>

  <div class='section-title'>Quality Dimensions Breakdown</div>
  <div class='chart-row'>
    {svg1}
  </div>

  <div class='section-title'>Quality Score vs SR Correlation</div>
  <div class='chart-row'>
    {svg2}
  </div>

  <div class='section-title'>Dataset Version Cards</div>
  <div class='grid-cards'>
    {cards_html}
  </div>

  <footer>Dataset Quality Scorer &mdash; OCI Robot Cloud &mdash; {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</footer>
</body>
</html>"""


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

if HAS_FASTAPI:
    app = FastAPI(title="Dataset Quality Scorer", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return HTMLResponse(content=build_html())

    @app.get("/api/quality")
    async def api_quality():
        return {
            "datasets": QUALITY_DATA,
            "pearson_r": PEARSON_R,
            "best_version": "ds_v4",
            "weakest_dim_per_version": {
                ds: min(DIM_LIST, key=lambda x: QUALITY_DATA[ds][x])
                for ds in DATASET_VERSIONS
            },
            "preprocess_steps": PREPROCESS_STEPS,
            "timestamp": datetime.utcnow().isoformat(),
        }

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "dataset_quality_scorer", "port": 8228}

else:
    # Fallback: stdlib http.server
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
        uvicorn.run(app, host="0.0.0.0", port=8228)
    else:
        print("[dataset_quality_scorer] fastapi not found — falling back to stdlib http.server on port 8228")
        server = HTTPServer(("0.0.0.0", 8228), _Handler)
        print("[dataset_quality_scorer] Serving on http://0.0.0.0:8228")
        server.serve_forever()
