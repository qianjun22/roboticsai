"""OCI Robot Cloud — Partner Invoice Dashboard  (port 8671)
Invoice aging, monthly trends, and payment velocity analytics.
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

PORT = 8671

# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

PARTNERS = ["PI", "1X", "Apptronik", "Agility", "Sanctuary"]

# Invoice aging buckets per partner: [current, 30d, 60d, 90d+]  ($ thousands)
AGING = {
    "PI":         [12.4, 2.1, 0.3, 0.0],
    "1X":         [ 8.9, 4.2, 1.8, 0.6],
    "Apptronik": [10.1, 1.4, 0.0, 0.0],
    "Agility":   [ 7.3, 2.8, 0.9, 0.2],
    "Sanctuary": [ 5.6, 1.1, 0.5, 1.3],
}

# Monthly totals Apr-Jun 2026 ($ thousands)
MONTHLY = {
    "PI":         [11.2, 13.8, 14.8],
    "1X":         [ 9.4, 10.1, 15.5],
    "Apptronik": [ 8.7,  9.2,  9.8],
    "Agility":   [ 7.0,  7.6,  8.2],
    "Sanctuary": [ 5.8,  6.0,  6.5],
}
MONTHS = ["Apr", "May", "Jun"]

# ---------------------------------------------------------------------------
# SVG builders
# ---------------------------------------------------------------------------

def build_aging_svg() -> str:
    """Stacked bar — invoice aging per partner."""
    W, H = 520, 300
    pad  = {"l": 80, "r": 20, "t": 40, "b": 50}
    pw   = W - pad["l"] - pad["r"]
    ph   = H - pad["t"]  - pad["b"]
    n    = len(PARTNERS)
    bar_w = pw / n * 0.6
    gap   = pw / n
    colors = ["#22c55e", "#eab308", "#f97316", "#ef4444"]
    labels = ["Current", "30d", "60d", "90d+"]

    max_val = max(sum(v) for v in AGING.values())

    parts = [
        f'<text x="{W//2}" y="22" text-anchor="middle" fill="#C74634" '
        f'font-size="13" font-weight="bold" font-family="monospace">Invoice Aging by Partner ($k)</text>',
    ]

    # y-axis grid
    for i in range(5):
        v  = i / 4 * max_val
        gy = pad["t"] + ph - (v / max_val * ph)
        parts.append(
            f'<line x1="{pad["l"]}" y1="{gy:.1f}" x2="{pad["l"]+pw}" y2="{gy:.1f}" '
            f'stroke="#1e3a5f" stroke-width="1" stroke-dasharray="3 3"/>'
            f'<text x="{pad["l"]-6}" y="{gy+4:.1f}" text-anchor="end" fill="#64748b" '
            f'font-size="9" font-family="monospace">{v:.0f}k</text>'
        )

    for pi, partner in enumerate(PARTNERS):
        buckets = AGING[partner]
        bx = pad["l"] + pi * gap + (gap - bar_w) / 2
        base = 0.0
        for bi, (amt, col) in enumerate(zip(buckets, colors)):
            bh = (amt / max_val) * ph
            by = pad["t"] + ph - (base + amt) / max_val * ph
            if amt > 0:
                parts.append(
                    f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bar_w:.1f}" height="{bh:.1f}" '
                    f'fill="{col}" opacity="0.88" rx="1"/>'
                )
            base += amt
        # x-axis label
        parts.append(
            f'<text x="{bx + bar_w/2:.1f}" y="{pad["t"]+ph+16}" text-anchor="middle" '
            f'fill="#cbd5e1" font-size="11" font-family="monospace">{partner}</text>'
        )

    # legend
    for i, (col, lbl) in enumerate(zip(colors, labels)):
        lx = pad["l"] + i * 110
        ly = H - 12
        parts.append(
            f'<rect x="{lx}" y="{ly-10}" width="10" height="10" fill="{col}" rx="1"/>'
            f'<text x="{lx+14}" y="{ly}" fill="#94a3b8" font-size="9" font-family="monospace">{lbl}</text>'
        )

    return (
        f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" '
        f'style="background:#1e293b;border-radius:8px">'
        + "".join(parts) + "</svg>"
    )


def build_trend_svg() -> str:
    """Monthly invoice trend (line chart) Apr-Jun 2026."""
    W, H = 460, 280
    pad  = {"l": 55, "r": 20, "t": 40, "b": 45}
    pw   = W - pad["l"] - pad["r"]
    ph   = H - pad["t"]  - pad["b"]
    cols = ["#38bdf8", "#ef4444", "#22c55e", "#a78bfa", "#fb923c"]

    all_vals = [v for vals in MONTHLY.values() for v in vals]
    max_v = max(all_vals) * 1.1

    def tx(i): return pad["l"] + i / (len(MONTHS)-1) * pw
    def ty(v): return pad["t"] + (1 - v / max_v) * ph

    parts = [
        f'<text x="{W//2}" y="22" text-anchor="middle" fill="#C74634" '
        f'font-size="13" font-weight="bold" font-family="monospace">Monthly Invoice Trend ($k)</text>',
    ]
    # grid
    for i, m in enumerate(MONTHS):
        gx = tx(i)
        parts.append(
            f'<line x1="{gx:.1f}" y1="{pad["t"]}" x2="{gx:.1f}" y2="{pad["t"]+ph}" '
            f'stroke="#1e3a5f" stroke-width="1" stroke-dasharray="3 3"/>'
            f'<text x="{gx:.1f}" y="{pad["t"]+ph+14}" text-anchor="middle" '
            f'fill="#64748b" font-size="10" font-family="monospace">{m}</text>'
        )
    for k in range(4):
        v  = k / 3 * max_v
        gy = ty(v)
        parts.append(
            f'<line x1="{pad["l"]}" y1="{gy:.1f}" x2="{pad["l"]+pw}" y2="{gy:.1f}" '
            f'stroke="#1e3a5f" stroke-width="1" stroke-dasharray="3 3"/>'
            f'<text x="{pad["l"]-6}" y="{gy+4:.1f}" text-anchor="end" fill="#64748b" '
            f'font-size="9" font-family="monospace">{v:.0f}</text>'
        )

    # lines
    for pi, (partner, col) in enumerate(zip(PARTNERS, cols)):
        vals = MONTHLY[partner]
        pts  = " ".join(f"{tx(i):.1f},{ty(v):.1f}" for i, v in enumerate(vals))
        parts.append(
            f'<polyline points="{pts}" fill="none" stroke="{col}" stroke-width="2" '
            f'stroke-linejoin="round" stroke-linecap="round"/>'
        )
        for i, v in enumerate(vals):
            parts.append(f'<circle cx="{tx(i):.1f}" cy="{ty(v):.1f}" r="3" fill="{col}"/>')
        # legend right side
        ly = pad["t"] + 14 + pi * 20
        lx = W - 80
        parts.append(
            f'<circle cx="{lx}" cy="{ly}" r="4" fill="{col}"/>'
            f'<text x="{lx+10}" y="{ly+4}" fill="#94a3b8" font-size="9" font-family="monospace">{partner}</text>'
        )

    return (
        f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" '
        f'style="background:#1e293b;border-radius:8px">'
        + "".join(parts) + "</svg>"
    )


def build_velocity_svg() -> str:
    """Payment velocity scatter — x=invoice_amount, y=days_to_pay."""
    random.seed(13)
    # (partner, avg_amount_k, avg_days, colour)
    partner_profile = [
        ("PI",         1.2,  8, "#38bdf8"),
        ("1X",         4.8, 28, "#ef4444"),
        ("Apptronik", 2.1, 14, "#22c55e"),
        ("Agility",   1.8, 16, "#a78bfa"),
        ("Sanctuary", 3.2, 21, "#fb923c"),
    ]
    n_pts = 3  # 3 pts × 5 partners = 15

    W, H = 460, 300
    pad  = {"l": 55, "r": 20, "t": 40, "b": 45}
    pw   = W - pad["l"] - pad["r"]
    ph   = H - pad["t"]  - pad["b"]

    max_amt  = 8.0
    max_days = 35

    def tx(v): return pad["l"] + (v / max_amt)  * pw
    def ty(v): return pad["t"] + (1 - v / max_days) * ph

    parts = [
        f'<text x="{W//2}" y="22" text-anchor="middle" fill="#C74634" '
        f'font-size="13" font-weight="bold" font-family="monospace">Payment Velocity</text>',
        f'<text x="{W//2}" y="{H-5}" text-anchor="middle" fill="#94a3b8" font-size="10" font-family="monospace">Invoice Amount ($k)</text>',
        f'<text x="12" y="{H//2}" text-anchor="middle" fill="#94a3b8" font-size="10" font-family="monospace" transform="rotate(-90,12,{H//2})">Days to Pay</text>',
        # axes
        f'<line x1="{pad["l"]}" y1="{pad["t"]}" x2="{pad["l"]}" y2="{pad["t"]+ph}" stroke="#475569" stroke-width="1"/>',
        f'<line x1="{pad["l"]}" y1="{pad["t"]+ph}" x2="{pad["l"]+pw}" y2="{pad["t"]+ph}" stroke="#475569" stroke-width="1"/>',
    ]
    # grid
    for k in range(1, 5):
        v  = k * 2
        gx = tx(v)
        parts.append(
            f'<line x1="{gx:.1f}" y1="{pad["t"]}" x2="{gx:.1f}" y2="{pad["t"]+ph}" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="3 3"/>'
            f'<text x="{gx:.1f}" y="{pad["t"]+ph+14}" text-anchor="middle" fill="#64748b" font-size="9" font-family="monospace">{v}</text>'
        )
    for k in [0, 7, 14, 21, 28, 35]:
        gy = ty(k)
        parts.append(
            f'<line x1="{pad["l"]}" y1="{gy:.1f}" x2="{pad["l"]+pw}" y2="{gy:.1f}" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="3 3"/>'
            f'<text x="{pad["l"]-6}" y="{gy+4:.1f}" text-anchor="end" fill="#64748b" font-size="9" font-family="monospace">{k}</text>'
        )

    for partner, avg_amt, avg_days, col in partner_profile:
        for _ in range(n_pts):
            amt  = avg_amt  + random.gauss(0, 0.4)
            days = avg_days + random.gauss(0, 2.0)
            amt  = max(0.3, min(max_amt - 0.3, amt))
            days = max(1,   min(max_days - 1,  int(days)))
            parts.append(
                f'<circle cx="{tx(amt):.1f}" cy="{ty(days):.1f}" r="6" '
                f'fill="{col}" opacity="0.85"/>'
            )
        # legend
        li = partner_profile.index((partner, avg_amt, avg_days, col))
        lx = pad["l"] + li * 82
        ly = H - 8
        parts.append(
            f'<circle cx="{lx+4}" cy="{ly-4}" r="5" fill="{col}" opacity="0.85"/>'
            f'<text x="{lx+14}" y="{ly}" fill="#94a3b8" font-size="9" font-family="monospace">{partner}</text>'
        )

    # quadrant labels
    parts.append(
        f'<text x="{pad["l"]+8}" y="{pad["t"]+16}" fill="#22c55e" font-size="9" font-family="monospace" opacity="0.7">fast + small</text>'
        f'<text x="{pad["l"]+pw-70}" y="{pad["t"]+ph-8}" fill="#ef4444" font-size="9" font-family="monospace" opacity="0.7">slow + large</text>'
    )

    return (
        f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" '
        f'style="background:#1e293b;border-radius:8px">'
        + "".join(parts) + "</svg>"
    )


# ---------------------------------------------------------------------------
# HTML page
# ---------------------------------------------------------------------------

HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Partner Invoice Dashboard — OCI Robot Cloud</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{background:#0f172a;color:#e2e8f0;font-family:monospace;padding:24px}}
  h1{{color:#C74634;font-size:1.5rem;margin-bottom:4px}}
  .sub{{color:#64748b;font-size:.8rem;margin-bottom:24px}}
  .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(440px,1fr));gap:24px}}
  .card{{background:#1e293b;border-radius:10px;padding:20px;border:1px solid #334155}}
  .card h2{{color:#C74634;font-size:1rem;margin-bottom:14px}}
  .card svg{{width:100%;height:auto}}
  .metrics{{display:flex;flex-wrap:wrap;gap:12px;margin-top:20px}}
  .metric{{background:#0f172a;border:1px solid #334155;border-radius:8px;padding:12px 18px;min-width:150px}}
  .metric .val{{color:#38bdf8;font-size:1.4rem;font-weight:bold}}
  .metric .lbl{{color:#64748b;font-size:.75rem;margin-top:2px}}
  .good .val{{color:#22c55e}}
  .footer{{color:#475569;font-size:.7rem;margin-top:28px;text-align:center}}
</style>
</head>
<body>
<h1>Partner Invoice Dashboard</h1>
<p class="sub">OCI Robot Cloud · Port {port} · Apr–Jun 2026</p>

<div class="grid">
  <div class="card">
    <h2>Invoice Aging (Stacked)</h2>
    {aging_svg}
  </div>
  <div class="card">
    <h2>Monthly Invoice Trend</h2>
    {trend_svg}
  </div>
  <div class="card">
    <h2>Payment Velocity</h2>
    {vel_svg}
  </div>
</div>

<div class="metrics">
  <div class="metric">
    <div class="val">$2,847</div>
    <div class="lbl">avg invoice amount</div>
  </div>
  <div class="metric good">
    <div class="val">94%</div>
    <div class="lbl">on-time payment rate</div>
  </div>
  <div class="metric good">
    <div class="val">0</div>
    <div class="lbl">open disputes</div>
  </div>
  <div class="metric good">
    <div class="val">8d</div>
    <div class="lbl">PI avg days to pay</div>
  </div>
  <div class="metric">
    <div class="val">28d</div>
    <div class="lbl">1X avg days to pay</div>
  </div>
  <div class="metric">
    <div class="val">Day 15</div>
    <div class="lbl">auto-reminder trigger</div>
  </div>
</div>

<p class="footer">OCI Robot Cloud — Partner Invoice Dashboard · port {port}</p>
</body>
</html>
"""


def make_html() -> str:
    return HTML.format(
        port=PORT,
        aging_svg=build_aging_svg(),
        trend_svg=build_trend_svg(),
        vel_svg=build_velocity_svg(),
    )


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

if USE_FASTAPI:
    app = FastAPI(title="Partner Invoice Dashboard", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return HTMLResponse(content=make_html())

    @app.get("/health")
    def health():
        return JSONResponse({"status": "ok", "port": PORT})

    @app.get("/metrics")
    def metrics():
        return JSONResponse({
            "avg_invoice_usd": 2847,
            "on_time_pct": 94,
            "open_disputes": 0,
            "auto_reminder_day": 15,
            "partner_days_to_pay": {
                "PI": 8, "1X": 28, "Apptronik": 14,
                "Agility": 16, "Sanctuary": 21,
            },
            "aging_buckets_k": AGING,
            "monthly_totals_k": MONTHLY,
        })

else:
    from http.server import BaseHTTPRequestHandler, HTTPServer
    import json

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a): pass

        def do_GET(self):
            if self.path == "/health":
                body = json.dumps({"status": "ok", "port": PORT}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)
            else:
                body = make_html().encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(body)


if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        print(f"FastAPI not found — starting stdlib HTTPServer on port {PORT}")
        HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
