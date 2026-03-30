"""
sdk_documentation_dashboard.py — port 8665
OCI Robot Cloud | SDK documentation coverage analytics dashboard.
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

import json
from datetime import datetime

# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------

# Coverage data
MODULES = ["predict", "train", "eval", "finetune", "embed", "dagger", "pipeline", "utils"]
DOC_TYPES = ["docstring", "example", "tutorial", "reference"]

COVERAGE = {
    #              docstring  example  tutorial  reference
    "predict":    [98,        92,      88,        96],
    "train":      [85,        78,      72,        80],
    "eval":       [90,        82,      75,        88],
    "finetune":   [80,        70,      65,        74],
    "embed":      [88,        76,      68,        82],
    "dagger":     [72,        55,      42,        74],   # /train/dagger gap
    "pipeline":   [82,        68,      60,        78],
    "utils":      [76,        64,      55,        70],
}

def _cov_color(pct: int) -> str:
    if pct < 50:  return "#C74634"   # red
    if pct < 80:  return "#f59e0b"   # amber
    return "#22c55e"                  # green


def svg_coverage_heatmap() -> str:
    """8 modules x 4 doc types heatmap."""
    cell_w, cell_h = 82, 36
    pad_l, pad_t = 90, 60
    W = pad_l + len(DOC_TYPES) * cell_w + 10
    H = pad_t + len(MODULES) * cell_h + 20

    cells = ""
    # Column headers
    for j, dtype in enumerate(DOC_TYPES):
        x = pad_l + j * cell_w + cell_w // 2
        cells += (
            f'<text x="{x}" y="{pad_t - 10}" fill="#94a3b8" font-size="12" '
            f'text-anchor="middle">{dtype}</text>\n'
        )
    # Row labels + cells
    for i, mod in enumerate(MODULES):
        y = pad_t + i * cell_h
        cells += (
            f'<text x="{pad_l - 8}" y="{y + cell_h//2 + 5}" fill="#e2e8f0" '
            f'font-size="12" text-anchor="end">/{mod}</text>\n'
        )
        for j, pct in enumerate(COVERAGE[mod]):
            x = pad_l + j * cell_w
            color = _cov_color(pct)
            cells += (
                f'<rect x="{x+2}" y="{y+2}" width="{cell_w-4}" height="{cell_h-4}" '
                f'fill="{color}" rx="4" opacity="0.85"/>\n'
                f'<text x="{x+cell_w//2}" y="{y+cell_h//2+5}" fill="#0f172a" '
                f'font-size="12" font-weight="700" text-anchor="middle">{pct}%</text>\n'
            )

    # Legend
    legend = ""
    for idx, (label, color) in enumerate([("<50% gap", "#C74634"), ("50-80% partial", "#f59e0b"), ("80%+ good", "#22c55e")]):
        lx = pad_l + idx * 155
        ly = H - 14
        legend += (
            f'<rect x="{lx}" y="{ly}" width="14" height="14" fill="{color}" rx="2"/>\n'
            f'<text x="{lx+18}" y="{ly+11}" fill="#94a3b8" font-size="11">{label}</text>\n'
        )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H+10}" '
        f'style="background:#1e293b;border-radius:8px;">\n'
        f'<text x="{W//2}" y="22" fill="#e2e8f0" font-size="14" font-weight="bold" '
        f'text-anchor="middle">Documentation Coverage Heatmap</text>\n'
        f'{cells}{legend}'
        f'</svg>'
    )


def svg_coverage_trend() -> str:
    """30-day coverage trend line: 68% to 78%."""
    W, H = 520, 260
    pad_l, pad_b, pad_r, pad_t = 50, 45, 20, 35

    cw = W - pad_l - pad_r
    ch = H - pad_t - pad_b

    import math as _math
    days = list(range(30))
    vals = []
    for d in days:
        t = d / 29
        v = 68 + 10 * (3 * t * t - 2 * t * t * t)
        v += 0.6 * _math.sin(d * 1.3)
        vals.append(v)

    min_v, max_v = 65, 82

    def px(d): return pad_l + (d / 29) * cw
    def py(v): return pad_t + (1 - (v - min_v) / (max_v - min_v)) * ch

    # Grid
    grid = ""
    for v in [68, 72, 76, 80]:
        gy = py(v)
        grid += (
            f'<line x1="{pad_l}" y1="{gy:.1f}" x2="{pad_l+cw}" y2="{gy:.1f}" '
            f'stroke="#1e293b" stroke-width="1"/>\n'
            f'<text x="{pad_l-6}" y="{gy+4:.1f}" fill="#94a3b8" font-size="11" '
            f'text-anchor="end">{v}%</text>\n'
        )

    # Area fill
    area_pts = f"{px(0):.1f},{py(min_v):.1f} "
    area_pts += " ".join(f"{px(d):.1f},{py(v):.1f}" for d, v in zip(days, vals))
    area_pts += f" {px(29):.1f},{py(min_v):.1f}"
    area = f'<polygon points="{area_pts}" fill="#38bdf8" opacity="0.12"/>\n'

    # Line
    line_pts = " ".join(f"{px(d):.1f},{py(v):.1f}" for d, v in zip(days, vals))
    trend_line = f'<polyline points="{line_pts}" fill="none" stroke="#38bdf8" stroke-width="2.5"/>\n'

    # Markers
    markers = (
        f'<circle cx="{px(0):.1f}" cy="{py(vals[0]):.1f}" r="5" fill="#38bdf8"/>\n'
        f'<text x="{px(0):.1f}" y="{py(vals[0])-10:.1f}" fill="#38bdf8" font-size="12" '
        f'text-anchor="middle">68%</text>\n'
        f'<circle cx="{px(29):.1f}" cy="{py(vals[-1]):.1f}" r="5" fill="#4ade80"/>\n'
        f'<text x="{px(29):.1f}" y="{py(vals[-1])-10:.1f}" fill="#4ade80" font-size="12" '
        f'text-anchor="middle">78%</text>\n'
    )

    x_labels = ""
    for d in [0, 7, 14, 21, 29]:
        x_labels += (
            f'<text x="{px(d):.1f}" y="{pad_t+ch+16}" fill="#94a3b8" font-size="11" '
            f'text-anchor="middle">Day {d+1}</text>\n'
        )

    axis_label = (
        f'<text x="{W//2}" y="{H-2}" fill="#94a3b8" font-size="12" '
        f'text-anchor="middle">Last 30 Days</text>\n'
        f'<text x="13" y="{pad_t+ch//2:.1f}" fill="#94a3b8" font-size="12" '
        f'text-anchor="middle" transform="rotate(-90,13,{pad_t+ch//2:.1f})">Coverage %</text>\n'
    )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'style="background:#1e293b;border-radius:8px;">\n'
        f'<text x="{W//2}" y="20" fill="#e2e8f0" font-size="14" font-weight="bold" '
        f'text-anchor="middle">Coverage Trend (30 Days)</text>\n'
        f'{grid}{area}{trend_line}{markers}{x_labels}{axis_label}'
        f'</svg>'
    )


def svg_endpoint_access() -> str:
    """Most accessed endpoints — horizontal bar chart with avg time-on-page."""
    endpoints = [
        ("/predict",       4820, 3.1),
        ("/train",         3210, 4.8),
        ("/eval",          2870, 3.9),
        ("/finetune",      2100, 5.2),
        ("/embed",         1760, 2.7),
        ("/train/dagger",  1540, 6.1),
        ("/pipeline",       980, 4.4),
        ("/utils",          640, 2.1),
    ]
    max_views = 4820
    W, H = 540, 310
    pad_l, pad_t = 140, 40
    bar_h, bar_gap = 22, 8
    bar_w = W - pad_l - 100

    bars = ""
    for i, (ep, views, avg_time) in enumerate(endpoints):
        y = pad_t + i * (bar_h + bar_gap)
        w = (views / max_views) * bar_w
        color = "#38bdf8" if ep != "/train/dagger" else "#f59e0b"
        bars += (
            f'<rect x="{pad_l}" y="{y}" width="{w:.1f}" height="{bar_h}" '
            f'fill="{color}" rx="3" opacity="0.9"/>\n'
            f'<text x="{pad_l - 8}" y="{y + bar_h//2 + 4}" fill="#e2e8f0" '
            f'font-size="12" text-anchor="end">{ep}</text>\n'
            f'<text x="{pad_l + w + 6:.1f}" y="{y + bar_h//2 + 4}" fill="#94a3b8" '
            f'font-size="11">{views:,} views · {avg_time}min</text>\n'
        )

    grid = ""
    for v in [1000, 2000, 3000, 4000]:
        x = pad_l + (v / max_views) * bar_w
        total_h = pad_t + len(endpoints) * (bar_h + bar_gap)
        grid += (
            f'<line x1="{x:.1f}" y1="{pad_t}" x2="{x:.1f}" y2="{total_h:.1f}" '
            f'stroke="#334155" stroke-width="1"/>\n'
            f'<text x="{x:.1f}" y="{total_h + 14:.1f}" fill="#94a3b8" font-size="10" '
            f'text-anchor="middle">{v//1000}k</text>\n'
        )

    total_h = pad_t + len(endpoints) * (bar_h + bar_gap)
    axis = (
        f'<text x="{pad_l + bar_w//2}" y="{total_h + 28}" fill="#94a3b8" font-size="12" '
        f'text-anchor="middle">Weekly Views</text>\n'
    )
    note = (
        f'<text x="{W-8}" y="{pad_t + 5 * (bar_h+bar_gap) + bar_h//2 + 4}" '
        f'fill="#f59e0b" font-size="11" text-anchor="end">doc gap</text>\n'
    )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'style="background:#1e293b;border-radius:8px;">\n'
        f'<text x="{W//2}" y="22" fill="#e2e8f0" font-size="14" font-weight="bold" '
        f'text-anchor="middle">Most Accessed Endpoints (Weekly)</text>\n'
        f'{grid}{bars}{axis}{note}'
        f'</svg>'
    )


# ---------------------------------------------------------------------------
# HTML page
# ---------------------------------------------------------------------------

def build_html() -> str:
    heatmap = svg_coverage_heatmap()
    trend   = svg_coverage_trend()
    access  = svg_endpoint_access()

    metrics = [
        ("Overall Coverage",    "78 %"),
        ("/predict Coverage",   "94 %"),
        ("/train/dagger Gap",   "61 %"),
        ("New Tutorials",       "3"),
        ("Doc NPS",             "4.1 / 5"),
        ("Top Request",         "DAgger examples"),
    ]
    metric_cards = "".join(
        f'<div style="background:#1e293b;border:1px solid #334155;border-radius:8px;'
        f'padding:16px 20px;min-width:150px;">'
        f'<div style="color:#94a3b8;font-size:12px;margin-bottom:4px;">{k}</div>'
        f'<div style="color:#38bdf8;font-size:20px;font-weight:700;">{v}</div>'
        f'</div>'
        for k, v in metrics
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>SDK Documentation Dashboard — OCI Robot Cloud</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',system-ui,sans-serif;padding:32px}}
  h1{{font-size:24px;font-weight:700;color:#38bdf8;margin-bottom:4px}}
  .subtitle{{color:#94a3b8;font-size:14px;margin-bottom:28px}}
  .badge{{display:inline-block;background:#C74634;color:#fff;font-size:11px;
          border-radius:4px;padding:2px 8px;margin-left:10px;vertical-align:middle}}
  .metrics{{display:flex;flex-wrap:wrap;gap:14px;margin-bottom:32px}}
  .charts{{display:grid;grid-template-columns:repeat(auto-fit,minmax(500px,1fr));gap:24px;margin-bottom:32px}}
  .chart-box{{background:#1e293b;border:1px solid #334155;border-radius:10px;padding:20px}}
  .chart-title{{color:#e2e8f0;font-size:14px;font-weight:600;margin-bottom:14px}}
  .gap-callout{{background:#1e293b;border-left:3px solid #f59e0b;border-radius:6px;
                padding:12px 16px;margin-bottom:28px;font-size:13px;color:#fbbf24}}
  .footer{{color:#475569;font-size:12px;border-top:1px solid #1e293b;padding-top:16px}}
</style>
</head>
<body>
<h1>SDK Documentation Dashboard <span class="badge">port 8665</span></h1>
<p class="subtitle">OCI Robot Cloud SDK documentation coverage &amp; analytics | {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC</p>

<div class="gap-callout">
  Action needed: <strong>/train/dagger</strong> documentation coverage is 61% — top user request is DAgger examples.
  3 new tutorials added this cycle; overall coverage improved from 68% to 78%.
</div>

<div class="metrics">{metric_cards}</div>

<div class="charts">
  <div class="chart-box" style="grid-column:1/-1">
    <div class="chart-title">Documentation Coverage Heatmap (8 modules x 4 doc types)</div>
    {heatmap}
  </div>
  <div class="chart-box">
    <div class="chart-title">Coverage Trend — Last 30 Days</div>
    {trend}
  </div>
  <div class="chart-box">
    <div class="chart-title">Most Accessed Endpoints (Weekly Views + Avg Time-on-Page)</div>
    {access}
  </div>
</div>

<div class="footer">OCI Robot Cloud &mdash; SDK Documentation Dashboard v1.0 &mdash; cycle-151B</div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

if USE_FASTAPI:
    app = FastAPI(
        title="SDK Documentation Dashboard",
        description="OCI Robot Cloud SDK documentation coverage analytics",
        version="1.0.0",
    )

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return build_html()

    @app.get("/health")
    async def health():
        return JSONResponse({"status": "ok", "service": "sdk_documentation_dashboard", "port": 8665})

    @app.get("/metrics")
    async def metrics():
        return JSONResponse({
            "overall_coverage_pct": 78,
            "predict_coverage_pct": 94,
            "dagger_coverage_pct": 61,
            "new_tutorials": 3,
            "doc_nps": 4.1,
            "top_request": "DAgger examples",
        })

else:
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a): pass

        def do_GET(self):
            if self.path == "/health":
                body = json.dumps({"status": "ok", "service": "sdk_documentation_dashboard", "port": 8665}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                body = build_html().encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)


if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8665)
    else:
        print("FastAPI not available — starting stdlib HTTPServer on port 8665")
        HTTPServer(("0.0.0.0", 8665), Handler).serve_forever()
