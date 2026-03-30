"""OCI Robot Cloud — API Version Tracker (port 8238)

Tracks API version adoption and deprecation across OCI Robot Cloud SDK users.
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
from datetime import datetime, timedelta

PORT = 8238

# ---------------------------------------------------------------------------
# Mock data generation
# ---------------------------------------------------------------------------

random.seed(42)

VERSIONS = ["v0.1", "v0.2", "v0.3.0"]
ENDPOINTS = ["/predict", "/train", "/eval", "/health", "/metrics", "/dataset"]

def _generate_weekly_adoption():
    """12 weeks of version distribution (%) — migration from v0.1 → v0.3.0."""
    weeks = []
    for w in range(12):
        # v0.1 declines: 42% → 8%
        v01 = max(8, 42 - w * 3 + random.randint(-1, 1))
        # v0.2 peaks mid-migration then declines: 38% → 24%
        v02 = max(24, 38 + int(4 * math.sin(math.pi * w / 6)) - w + random.randint(-2, 2))
        v02 = min(v02, 100 - v01 - 2)
        # v0.3.0 grows: 20% → 68%
        v03 = max(0, 100 - v01 - v02)
        weeks.append({"week": w + 1, "v0.1": v01, "v0.2": v02, "v0.3.0": v03})
    return weeks

def _generate_endpoint_calls():
    """Call volume per endpoint per version — total ~26,670."""
    base = {"/predict": 8200, "/train": 4800, "/eval": 4100,
            "/health": 3900, "/metrics": 3200, "/dataset": 2470}
    rows = []
    for ep, total in base.items():
        v01 = int(total * 0.08 + random.randint(-50, 50))
        v02 = int(total * 0.24 + random.randint(-80, 80))
        v03 = total - v01 - v02
        rows.append({"endpoint": ep, "v0.1": v01, "v0.2": v02, "v0.3.0": v03,
                     "total": total})
    return rows

WEEKLY = _generate_weekly_adoption()
ENDPOINT_CALLS = _generate_endpoint_calls()
TOTAL_CALLS = sum(r["total"] for r in ENDPOINT_CALLS)

# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------

def _svg_stacked_area() -> str:
    W, H = 620, 260
    PAD_L, PAD_R, PAD_T, PAD_B = 52, 20, 20, 40
    cw = W - PAD_L - PAD_R
    ch = H - PAD_T - PAD_B
    n = len(WEEKLY)

    colors = {"v0.3.0": "#38bdf8", "v0.2": "#7dd3fc", "v0.1": "#C74634"}
    # Build stacked polygons bottom-up: v0.1 at bottom, v0.3.0 at top
    stack_order = ["v0.1", "v0.2", "v0.3.0"]

    def x(i): return PAD_L + i * cw / (n - 1)
    def y(pct): return PAD_T + ch * (1 - pct / 100)

    # Compute cumulative tops
    tops = {v: [] for v in stack_order}
    bottoms = {v: [] for v in stack_order}
    for w in WEEKLY:
        cum = 0
        for v in stack_order:
            bottoms[v].append(cum)
            cum += w[v]
            tops[v].append(cum)

    paths = []
    for v in reversed(stack_order):
        pts_top = " ".join(f"{x(i):.1f},{y(tops[v][i]):.1f}" for i in range(n))
        pts_bot = " ".join(f"{x(i):.1f},{y(bottoms[v][i]):.1f}" for i in reversed(range(n)))
        pts = pts_top + " " + pts_bot
        paths.append(f'<polygon points="{pts}" fill="{colors[v]}" opacity="0.85"/>')

    # Grid lines
    grids = ""
    for pct in [0, 25, 50, 75, 100]:
        yy = y(pct)
        grids += f'<line x1="{PAD_L}" y1="{yy:.1f}" x2="{W - PAD_R}" y2="{yy:.1f}" stroke="#334155" stroke-width="1"/>'
        grids += f'<text x="{PAD_L - 6}" y="{yy + 4:.1f}" fill="#94a3b8" font-size="10" text-anchor="end">{pct}%</text>'

    # X axis labels (every 2 weeks)
    xlabels = ""
    for i, w in enumerate(WEEKLY):
        if i % 2 == 0:
            xlabels += f'<text x="{x(i):.1f}" y="{H - 6}" fill="#94a3b8" font-size="10" text-anchor="middle">W{w["week"]}</text>'

    # Sunset annotation at week 16 (off chart — show arrow at right edge)
    sunset = f'<text x="{W - PAD_R - 2}" y="{PAD_T + 12}" fill="#C74634" font-size="10" text-anchor="end">v0.1 sunset →W16</text>'

    legend = ""
    lx = PAD_L
    for v, c in colors.items():
        legend += f'<rect x="{lx}" y="{H - 18}" width="10" height="10" fill="{c}" rx="2"/>'
        legend += f'<text x="{lx + 13}" y="{H - 8}" fill="#cbd5e1" font-size="10">{v}</text>'
        lx += 70

    return f"""<svg xmlns='http://www.w3.org/2000/svg' width='{W}' height='{H}' style='background:#1e293b;border-radius:8px'>
  {grids}
  {''.join(paths)}
  {xlabels}
  {sunset}
  {legend}
  <text x="{W//2}" y="{PAD_T - 6}" fill="#f1f5f9" font-size="12" text-anchor="middle" font-weight="bold">API Version Adoption — 12-Week Migration</text>
</svg>"""


def _svg_endpoint_bars() -> str:
    W, H = 620, 280
    PAD_L, PAD_R, PAD_T, PAD_B = 80, 20, 30, 40
    cw = W - PAD_L - PAD_R
    ch = H - PAD_T - PAD_B

    eps = ENDPOINT_CALLS
    n = len(eps)
    max_total = max(r["total"] for r in eps)

    group_w = cw / n
    bar_w = group_w * 0.22
    gap = group_w * 0.04
    colors = {"v0.1": "#C74634", "v0.2": "#7dd3fc", "v0.3.0": "#38bdf8"}

    bars = ""
    xlabels = ""
    for i, row in enumerate(eps):
        gx = PAD_L + i * group_w + group_w * 0.08
        for j, v in enumerate(["v0.1", "v0.2", "v0.3.0"]):
            bx = gx + j * (bar_w + gap)
            bh = ch * row[v] / max_total
            by = PAD_T + ch - bh
            bars += f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bar_w:.1f}" height="{bh:.1f}" fill="{colors[v]}" rx="2" opacity="0.9"/>'
            if row[v] > 200:
                bars += f'<text x="{bx + bar_w/2:.1f}" y="{by - 3:.1f}" fill="#94a3b8" font-size="8" text-anchor="middle">{row[v]}</text>'
        cx = PAD_L + i * group_w + group_w / 2
        xlabels += f'<text x="{cx:.1f}" y="{H - 6}" fill="#94a3b8" font-size="10" text-anchor="middle">{row["endpoint"]}</text>'

    # Grid
    grids = ""
    for tick in [0, 2000, 4000, 6000, 8000]:
        if tick > max_total:
            break
        yy = PAD_T + ch * (1 - tick / max_total)
        grids += f'<line x1="{PAD_L}" y1="{yy:.1f}" x2="{W - PAD_R}" y2="{yy:.1f}" stroke="#334155" stroke-width="1"/>'
        grids += f'<text x="{PAD_L - 4}" y="{yy + 4:.1f}" fill="#94a3b8" font-size="9" text-anchor="end">{tick}</text>'

    legend = ""
    lx = PAD_L
    for v, c in colors.items():
        legend += f'<rect x="{lx}" y="{H - 18}" width="10" height="10" fill="{c}" rx="2"/>'
        legend += f'<text x="{lx + 13}" y="{H - 8}" fill="#cbd5e1" font-size="10">{v}</text>'
        lx += 70

    return f"""<svg xmlns='http://www.w3.org/2000/svg' width='{W}' height='{H}' style='background:#1e293b;border-radius:8px'>
  {grids}
  {bars}
  {xlabels}
  {legend}
  <text x="{W//2}" y="{PAD_T - 8}" fill="#f1f5f9" font-size="12" text-anchor="middle" font-weight="bold">API Call Volume by Endpoint × Version (total {TOTAL_CALLS:,})</text>
</svg>"""


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def _build_html() -> str:
    current = WEEKLY[-1]
    sunset_users = current["v0.1"]
    migration_vel = round((WEEKLY[-1]["v0.3.0"] - WEEKLY[0]["v0.3.0"]) / 11, 1)

    svg1 = _svg_stacked_area()
    svg2 = _svg_endpoint_bars()

    metrics = [
        ("v0.3.0 Adoption", f"{current['v0.3.0']}%", "#38bdf8"),
        ("Sunset Risk (v0.1)", f"{sunset_users}%", "#C74634"),
        ("Migration Velocity", f"+{migration_vel}%/wk", "#4ade80"),
        ("Total API Calls", f"{TOTAL_CALLS:,}", "#f1f5f9"),
        ("v0.1 Sunset Week", "W16", "#fbbf24"),
        ("Auto-Upgrade Available", "Yes", "#4ade80"),
    ]

    cards = "".join(
        f'<div style="background:#1e293b;border:1px solid #334155;border-radius:8px;padding:16px;text-align:center">'
        f'<div style="color:#94a3b8;font-size:12px;margin-bottom:6px">{label}</div>'
        f'<div style="color:{color};font-size:22px;font-weight:700">{value}</div>'
        f'</div>'
        for label, value, color in metrics
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>API Version Tracker — OCI Robot Cloud</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #f1f5f9; font-family: 'Segoe UI', system-ui, sans-serif; padding: 24px; }}
    h1 {{ color: #C74634; font-size: 22px; margin-bottom: 4px; }}
    .subtitle {{ color: #64748b; font-size: 13px; margin-bottom: 20px; }}
    .grid-6 {{ display: grid; grid-template-columns: repeat(6, 1fr); gap: 12px; margin-bottom: 24px; }}
    .chart-row {{ display: flex; gap: 20px; flex-wrap: wrap; margin-bottom: 20px; }}
    .chart-box {{ background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 16px; }}
    .tag {{ display: inline-block; background: #C74634; color: #fff; font-size: 11px; padding: 2px 8px; border-radius: 4px; margin-left: 10px; }}
    footer {{ color: #475569; font-size: 11px; margin-top: 16px; }}
  </style>
</head>
<body>
  <h1>API Version Tracker <span class="tag">PORT 8238</span></h1>
  <p class="subtitle">OCI Robot Cloud SDK — version adoption, deprecation sunset risk, migration velocity</p>

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
    app = FastAPI(title="API Version Tracker", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return _build_html()

    @app.get("/api/adoption")
    async def adoption():
        return {"weeks": WEEKLY, "current": WEEKLY[-1]}

    @app.get("/api/endpoints")
    async def endpoints():
        return {"endpoints": ENDPOINT_CALLS, "total_calls": TOTAL_CALLS}

    @app.get("/api/summary")
    async def summary():
        cur = WEEKLY[-1]
        return {
            "v0.3.0_adoption_pct": cur["v0.3.0"],
            "sunset_risk_pct": cur["v0.1"],
            "total_calls": TOTAL_CALLS,
            "auto_upgrade": True,
            "sunset_week": 16,
        }

    @app.get("/health")
    async def health():
        return {"status": "ok", "port": PORT, "service": "api_version_tracker"}

else:
    # Fallback: stdlib HTTP server
    from http.server import HTTPServer, BaseHTTPRequestHandler

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = _build_html().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):  # silence default logging
            pass


if __name__ == "__main__":
    if HAS_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        print(f"FastAPI not found — starting stdlib server on port {PORT}")
        HTTPServer(("0.0.0.0", PORT), _Handler).serve_forever()
