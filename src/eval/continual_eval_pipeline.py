"""
Continual Eval Pipeline — port 8650
OCI Robot Cloud | cycle-148A
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

# ── SVG helpers ────────────────────────────────────────────────────────────────

def svg_gantt() -> str:
    """Eval schedule Gantt — 3 tiers × 4 weeks, resource allocation %."""
    W, H = 760, 320
    weeks = ["Week 1", "Week 2", "Week 3", "Week 4"]
    tiers = [
        {"name": "Quick (daily)",    "color": "#38bdf8", "alloc": 15, "bars": [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28]},
        {"name": "Standard (weekly)","color": "#C74634", "alloc": 35, "bars": [7,14,21,28]},
        {"name": "Extended (monthly)","color": "#a78bfa","alloc": 50, "bars": [28]},
    ]
    margin_left = 180
    margin_top  = 50
    row_h       = 70
    day_w       = (W - margin_left - 30) / 28

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'style="background:#0f172a;font-family:monospace">',
        # title
        f'<text x="{W//2}" y="28" fill="#f8fafc" font-size="15" font-weight="bold" text-anchor="middle">'
        'Eval Schedule Gantt — 4-Week View</text>',
    ]

    # week grid
    for wi, wlabel in enumerate(weeks):
        x = margin_left + wi * 7 * day_w
        lines.append(f'<line x1="{x:.1f}" y1="{margin_top-10}" x2="{x:.1f}" y2="{H-40}" '
                      f'stroke="#334155" stroke-width="1"/>')
        lines.append(f'<text x="{x + 3.5*day_w:.1f}" y="{margin_top-14}" fill="#94a3b8" '
                      f'font-size="11" text-anchor="middle">{wlabel}</text>')

    for ti, tier in enumerate(tiers):
        y = margin_top + ti * row_h
        # row label
        lines.append(f'<text x="{margin_left-8}" y="{y+20}" fill="{tier["color"]}" '
                      f'font-size="12" text-anchor="end">{tier["name"]}</text>')
        lines.append(f'<text x="{margin_left-8}" y="{y+36}" fill="#64748b" '
                      f'font-size="10" text-anchor="end">Alloc {tier["alloc"]}%</text>')
        # bars
        for day in tier["bars"]:
            bx = margin_left + (day - 1) * day_w
            bw = day_w * 0.7
            bh = 22
            lines.append(f'<rect x="{bx:.1f}" y="{y+8}" width="{bw:.1f}" height="{bh}" '
                          f'rx="3" fill="{tier["color"]}" opacity="0.85"/>')

    # resource allocation bar at bottom
    by = H - 35
    lines.append(f'<text x="{margin_left}" y="{by-6}" fill="#94a3b8" font-size="10">Resource allocation</text>')
    colors = ["#38bdf8","#C74634","#a78bfa"]
    allocs = [15, 35, 50]
    bx = margin_left
    bw_total = W - margin_left - 30
    for ci, (c, a) in enumerate(zip(colors, allocs)):
        bw = bw_total * a / 100
        lines.append(f'<rect x="{bx:.1f}" y="{by}" width="{bw:.1f}" height="12" fill="{c}" opacity="0.8"/>')
        lines.append(f'<text x="{bx + bw/2:.1f}" y="{by+10}" fill="#0f172a" font-size="9" '
                      f'text-anchor="middle" font-weight="bold">{a}%</text>')
        bx += bw

    lines.append('</svg>')
    return "\n".join(lines)


def svg_sr_trend() -> str:
    """SR trend with CI bands — rolling 30-day, 3 eval tiers."""
    W, H = 760, 300
    ml, mr, mt, mb = 55, 20, 30, 45

    # synthetic SR data (days 1-30)
    import math
    days = list(range(1, 31))

    def sr_series(base, noise_amp, trend):
        vals = []
        for i, d in enumerate(days):
            v = base + trend * i / 30 + noise_amp * math.sin(d * 0.7 + base)
            vals.append(max(0.0, min(1.0, v)))
        return vals

    quick    = sr_series(0.78, 0.04, 0.05)
    standard = sr_series(0.71, 0.03, 0.07)
    extended = sr_series(0.64, 0.025, 0.09)
    sigma    = 0.03

    iw = W - ml - mr
    ih = H - mt - mb
    sr_min, sr_max = 0.55, 1.0

    def px(d_idx): return ml + d_idx / (len(days)-1) * iw
    def py(v):     return mt + ih - (v - sr_min) / (sr_max - sr_min) * ih

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'style="background:#0f172a;font-family:monospace">',
        f'<text x="{W//2}" y="20" fill="#f8fafc" font-size="14" font-weight="bold" '
        f'text-anchor="middle">30-Day SR Trend with ±1σ CI Bands</text>',
    ]

    # grid
    for sr_tick in [0.6, 0.7, 0.8, 0.9, 1.0]:
        y = py(sr_tick)
        lines.append(f'<line x1="{ml}" y1="{y:.1f}" x2="{W-mr}" y2="{y:.1f}" stroke="#1e293b" stroke-width="1"/>')
        lines.append(f'<text x="{ml-5}" y="{y+4:.1f}" fill="#64748b" font-size="10" text-anchor="end">{sr_tick:.0%}</text>')

    # day axis
    for di in [0, 9, 19, 29]:
        x = px(di)
        lines.append(f'<text x="{x:.1f}" y="{H-10}" fill="#64748b" font-size="10" text-anchor="middle">Day {days[di]}</text>')

    series = [
        (quick,    "#38bdf8", "Quick"),
        (standard, "#C74634", "Standard"),
        (extended, "#a78bfa", "Extended"),
    ]

    for vals, color, label in series:
        # CI band (polygon)
        upper = [min(1.0, v + sigma) for v in vals]
        lower = [max(0.0, v - sigma) for v in vals]
        pts_upper = " ".join(f"{px(i):.1f},{py(u):.1f}" for i, u in enumerate(upper))
        pts_lower = " ".join(f"{px(i):.1f},{py(l):.1f}" for i, l in enumerate(reversed(lower)))
        lines.append(f'<polygon points="{pts_upper} {pts_lower}" fill="{color}" opacity="0.15"/>')
        # line
        pts = " ".join(f"{px(i):.1f},{py(v):.1f}" for i, v in enumerate(vals))
        lines.append(f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2"/>')

    # legend
    lx = ml
    for vals, color, label in series:
        last_v = vals[-1]
        lines.append(f'<rect x="{lx}" y="{H-32}" width="10" height="10" fill="{color}"/>')
        lines.append(f'<text x="{lx+13}" y="{H-24}" fill="{color}" font-size="10">{label} ({last_v:.0%})</text>')
        lx += 150

    lines.append('</svg>')
    return "\n".join(lines)


def svg_regression_gate() -> str:
    """Regression gate status table SVG."""
    W, H = 760, 260
    rows = [
        ("Quick eval",    "+2.1%", "+1.4%", "+5.3%", "PASS"),
        ("Standard eval", "+0.8%", "-0.3%", "+2.1%", "WARN"),
        ("Extended eval", "+1.5%", "+0.9%", "+3.8%", "PASS"),
    ]
    badge_color = {"PASS": "#22c55e", "WARN": "#f59e0b", "BLOCK": "#ef4444"}
    col_labels = ["Eval Tier", "vs Last Week ΔSR", "vs Last Month ΔSR", "vs Baseline ΔSR", "Gate Status"]
    col_x = [20, 180, 340, 490, 630]
    row_h = 44

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'style="background:#0f172a;font-family:monospace">',
        f'<text x="{W//2}" y="24" fill="#f8fafc" font-size="14" font-weight="bold" '
        f'text-anchor="middle">Regression Gate Status</text>',
    ]

    # header bg
    lines.append(f'<rect x="10" y="34" width="{W-20}" height="28" rx="4" fill="#1e293b"/>')
    for ci, (cx, cl) in enumerate(zip(col_x, col_labels)):
        lines.append(f'<text x="{cx}" y="52" fill="#94a3b8" font-size="11" font-weight="bold">{cl}</text>')

    for ri, (tier, dw, dm, db, status) in enumerate(rows):
        ry = 34 + 28 + ri * row_h + 6
        bg = "#0f1f38" if ri % 2 == 0 else "#0f172a"
        lines.append(f'<rect x="10" y="{ry}" width="{W-20}" height="{row_h-4}" rx="3" fill="{bg}"/>')
        vals = [tier, dw, dm, db]
        for ci, (cx, v) in enumerate(zip(col_x, vals)):
            color = "#38bdf8" if ci == 0 else ("#22c55e" if v.startswith("+") else "#ef4444")
            lines.append(f'<text x="{cx}" y="{ry+22}" fill="{color}" font-size="12">{v}</text>')
        # badge
        bc = badge_color.get(status, "#64748b")
        lines.append(f'<rect x="{col_x[4]}" y="{ry+6}" width="72" height="22" rx="11" fill="{bc}" opacity="0.2"/>')
        lines.append(f'<rect x="{col_x[4]}" y="{ry+6}" width="72" height="22" rx="11" '
                      f'fill="none" stroke="{bc}" stroke-width="1.5"/>')
        lines.append(f'<text x="{col_x[4]+36}" y="{ry+21}" fill="{bc}" font-size="11" '
                      f'font-weight="bold" text-anchor="middle">{status}</text>')

    lines.append('</svg>')
    return "\n".join(lines)


# ── HTML page ──────────────────────────────────────────────────────────────────

def build_html() -> str:
    gantt   = svg_gantt()
    trend   = svg_sr_trend()
    reg     = svg_regression_gate()

    metrics = [
        ("Evals / Week",       "20.6",   "across all tiers"),
        ("Quick eval cost",    "$2.00",   "per run"),
        ("Standard eval cost", "$8.00",   "per run"),
        ("Extended eval cost", "$19.00",  "per run"),
        ("Extended monthly",   "$114",    "budget"),
        ("Quick catch rate",   "78%",     "of regressions"),
        ("Regressions",        "0",       "in 14 deployments"),
    ]

    cards = "".join(
        f'<div style="background:#1e293b;border:1px solid #334155;border-radius:8px;padding:16px 20px;min-width:150px">'
        f'<div style="color:#94a3b8;font-size:11px;margin-bottom:4px">{m[0]}</div>'
        f'<div style="color:#38bdf8;font-size:24px;font-weight:bold">{m[1]}</div>'
        f'<div style="color:#64748b;font-size:10px;margin-top:2px">{m[2]}</div>'
        f'</div>'
        for m in metrics
    )

    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Continual Eval Pipeline | OCI Robot Cloud</title>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{background:#0f172a;color:#f8fafc;font-family:'JetBrains Mono',monospace,sans-serif;padding:24px}}
    h1{{font-size:22px;color:#38bdf8;margin-bottom:4px}}
    .sub{{color:#64748b;font-size:13px;margin-bottom:24px}}
    .metrics{{display:flex;flex-wrap:wrap;gap:12px;margin-bottom:28px}}
    .section{{margin-bottom:32px}}
    .section h2{{font-size:14px;color:#94a3b8;text-transform:uppercase;letter-spacing:.05em;margin-bottom:12px;
                 border-bottom:1px solid #1e293b;padding-bottom:6px}}
    svg{{border-radius:8px;display:block}}
  </style>
</head>
<body>
  <h1>Continual Eval Pipeline</h1>
  <div class="sub">OCI Robot Cloud &mdash; port 8650 &mdash; {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC</div>

  <div class="metrics">{cards}</div>

  <div class="section">
    <h2>Eval Schedule Gantt</h2>
    {gantt}
  </div>
  <div class="section">
    <h2>Success Rate Trend (±1σ CI)</h2>
    {trend}
  </div>
  <div class="section">
    <h2>Regression Gate Status</h2>
    {reg}
  </div>
</body>
</html>"""


# ── App ────────────────────────────────────────────────────────────────────────

if USE_FASTAPI:
    app = FastAPI(title="Continual Eval Pipeline", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def root():
        return HTMLResponse(content=build_html())

    @app.get("/health")
    async def health():
        return JSONResponse({"status": "ok", "service": "continual_eval_pipeline", "port": 8650})

    @app.get("/metrics")
    async def metrics():
        return JSONResponse({
            "evals_per_week": 20.6,
            "cost_quick_usd": 2.0,
            "cost_standard_usd": 8.0,
            "cost_extended_usd": 19.0,
            "extended_monthly_usd": 114.0,
            "quick_catch_rate": 0.78,
            "regressions_in_14_deployments": 0,
        })

    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=8650)

else:
    # stdlib fallback
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a): pass
        def do_GET(self):
            if self.path == "/health":
                body = json.dumps({"status": "ok", "service": "continual_eval_pipeline", "port": 8650}).encode()
                ct = "application/json"
            else:
                body = build_html().encode()
                ct = "text/html"
            self.send_response(200)
            self.send_header("Content-Type", ct)
            self.end_headers()
            self.wfile.write(body)

    if __name__ == "__main__":
        print("FastAPI unavailable — running stdlib HTTPServer on :8650")
        HTTPServer(("0.0.0.0", 8650), Handler).serve_forever()
