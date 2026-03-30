"""Annual Revenue Model — FastAPI port 8859"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8859

# 3-year ARR model anchors (monthly, in $k)
# Scenarios: base, upside (GTC+NVIDIA), stretch (marketplace)
MONTHLY_ARR = {
    # (year, month_1_based): (base, upside, stretch)
    (2026, 1):  (2,    3,    4),
    (2026, 3):  (5,    8,   10),
    (2026, 6):  (12,  18,   22),
    (2026, 9):  (28,  42,   55),   # AI World Sep inflection
    (2026, 12): (47,  75,  100),
    (2027, 3):  (120, 200,  280),
    (2027, 6):  (280, 450,  620),
    (2027, 9):  (520, 680,  900),
    (2027, 12): (840, 1100, 1500), # GTC + NVIDIA
    (2028, 3):  (1200,1600, 2200),
    (2028, 6):  (1900,2500, 3400),
    (2028, 9):  (2800,3600, 4900),
    (2028, 12): (4200,5500, 7500), # Marketplace
}

# Sorted timeline for SVG
TIMELINE = sorted(MONTHLY_ARR.keys())


def _s_curve_svg() -> str:
    """SVG S-curve of 3-year ARR across three scenarios."""
    svg_w, svg_h = 540, 260
    pad_l, pad_b, pad_t = 60, 40, 20
    plot_w = svg_w - pad_l - 20
    plot_h = svg_h - pad_b - pad_t

    max_arr = 8000  # $k ceiling for y-axis
    n = len(TIMELINE)

    def px(i):
        return pad_l + int(i / (n - 1) * plot_w)

    def py(val):
        return pad_t + plot_h - int(val / max_arr * plot_h)

    def polyline(scenario_idx, color, dash=""):
        pts = " ".join(
            f"{px(i)},{py(MONTHLY_ARR[k][scenario_idx])}"
            for i, k in enumerate(TIMELINE)
        )
        stroke_dash = f'stroke-dasharray="{dash}"' if dash else ""
        return f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2.5" {stroke_dash}/>'

    # AI World Sep 2026 = index 3 in timeline
    aiw_x = px(3)

    x_labels = ""
    for i, (yr, mo) in enumerate(TIMELINE):
        if mo in (1, 6, 12):
            lbl = f"{yr}-{mo:02d}"
            x_labels += (
                f'<text x="{px(i)}" y="{svg_h - 6}" font-size="9" fill="#64748b" '
                f'text-anchor="middle">{lbl}</text>'
            )

    # Y-axis ticks
    y_ticks = ""
    for v in [0, 1000, 2000, 4000, 6000, 8000]:
        yy = py(v)
        lbl = f"${v//1000}M" if v >= 1000 else "$0"
        y_ticks += (
            f'<line x1="{pad_l - 4}" y1="{yy}" x2="{svg_w - 20}" y2="{yy}" '
            f'stroke="#1e293b" stroke-width="1"/>'
            f'<text x="{pad_l - 6}" y="{yy + 4}" font-size="9" fill="#64748b" text-anchor="end">{lbl}</text>'
        )

    return (
        f'<svg viewBox="0 0 {svg_w} {svg_h}" xmlns="http://www.w3.org/2000/svg">'
        f'{y_ticks}'
        # AI World inflection marker
        f'<line x1="{aiw_x}" y1="{pad_t}" x2="{aiw_x}" y2="{svg_h - pad_b}" '
        f'stroke="#facc15" stroke-width="1.5" stroke-dasharray="4 3"/>'
        f'<text x="{aiw_x + 4}" y="{pad_t + 12}" font-size="9" fill="#facc15">AI World Sep</text>'
        # Three scenario curves
        + polyline(2, "#64748b", "6 3")   # stretch (top)
        + polyline(1, "#38bdf8", "")       # upside (GTC+NVIDIA)
        + polyline(0, "#C74634", "")       # base
        # Legend
        f'<rect x="{pad_l}" y="{pad_t}" width="10" height="4" fill="#C74634"/>'
        f'<text x="{pad_l + 14}" y="{pad_t + 5}" font-size="9" fill="#e2e8f0">Base</text>'
        f'<rect x="{pad_l + 55}" y="{pad_t}" width="10" height="4" fill="#38bdf8"/>'
        f'<text x="{pad_l + 69}" y="{pad_t + 5}" font-size="9" fill="#e2e8f0">GTC+NVIDIA</text>'
        f'<rect x="{pad_l + 145}" y="{pad_t}" width="10" height="4" fill="#64748b"/>'
        f'<text x="{pad_l + 159}" y="{pad_t + 5}" font-size="9" fill="#e2e8f0">Marketplace</text>'
        + x_labels
        + f'</svg>'
    )


def build_html() -> str:
    scurve = _s_curve_svg()
    return f"""<!DOCTYPE html><html><head><title>Annual Revenue Model</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui;padding:24px}}
h1{{color:#C74634;margin-bottom:4px}}h2{{color:#38bdf8;margin-top:0}}
.card{{background:#1e293b;padding:20px;margin:10px 0;border-radius:8px}}
.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:16px}}
.metric{{background:#0f172a;border-radius:8px;padding:16px;text-align:center}}
.metric .val{{font-size:1.8rem;font-weight:bold;color:#38bdf8}}
.metric .sub{{font-size:0.9rem;color:#C74634;margin-top:2px}}
.metric .lbl{{font-size:0.75rem;color:#64748b;margin-top:4px}}
.badge{{display:inline-block;padding:2px 10px;border-radius:12px;font-size:0.8rem;
        background:#C74634;color:#fff;margin-left:8px}}
table{{width:100%;border-collapse:collapse;font-size:0.85rem}}
th{{color:#64748b;text-align:left;padding:6px 8px;border-bottom:1px solid #334155}}
td{{padding:6px 8px;border-bottom:1px solid #1e293b}}
tr:hover td{{background:#0f172a}}
.up{{color:#4ade80}}.hi{{color:#38bdf8}}.lo{{color:#C74634}}
</style></head>
<body>
<h1>Annual Revenue Model <span class="badge">port {PORT}</span></h1>
<p style="color:#64748b">3-year ARR projection (2026-2028) across Base, GTC+NVIDIA Upside,
   and Marketplace Stretch scenarios.</p>

<div class="grid">
  <div class="metric">
    <div class="val">$47k</div>
    <div class="sub">Dec 2026 Base ARR</div>
    <div class="lbl">Post AI World ramp</div>
  </div>
  <div class="metric">
    <div class="val">$840k</div>
    <div class="sub">Dec 2027 Base ARR</div>
    <div class="lbl">GTC + NVIDIA partnership</div>
  </div>
  <div class="metric">
    <div class="val">$4.2M</div>
    <div class="sub">Dec 2028 Base ARR</div>
    <div class="lbl">Marketplace &amp; platform</div>
  </div>
</div>

<div class="card">
  <h2>ARR S-Curve (2026-2028)</h2>
  {scurve}
  <p style="font-size:0.8rem;color:#64748b;margin-top:8px">
    AI World Sep 2026 is the primary inflection point — fleet trials convert to
    paid contracts, driving 8× MoM acceleration in Q4 2026.
  </p>
</div>

<div class="card">
  <h2>Scenario Milestones</h2>
  <table>
    <tr><th>Date</th><th>Base ($k ARR)</th><th>GTC+NVIDIA ($k)</th><th>Marketplace ($k)</th></tr>
    {''.join(
        f"<tr><td>{yr}-{mo:02d}</td>"
        f"<td class='lo'>${MONTHLY_ARR[(yr,mo)][0]}k</td>"
        f"<td class='hi'>${MONTHLY_ARR[(yr,mo)][1]}k</td>"
        f"<td class='up'>${MONTHLY_ARR[(yr,mo)][2]}k</td></tr>"
        for yr, mo in TIMELINE
    )}
  </table>
</div>

<div class="card">
  <h2>Series A Gate Criteria</h2>
  <ul style="color:#94a3b8;font-size:0.9rem">
    <li>ARR threshold: <strong style="color:#38bdf8">$500k</strong> (expected Q3 2027 base / Q2 2027 upside)</li>
    <li>NVIDIA partnership: signed LOI or co-sell agreement</li>
    <li>Design partners: ≥ 5 paying fleet customers</li>
    <li>Gross margin target: ≥ 65% (compute cost optimisation via Autoscaler V3)</li>
  </ul>
</div>
</body></html>"""


if USE_FASTAPI:
    app = FastAPI(title="Annual Revenue Model")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return build_html()

    @app.get("/health")
    def health():
        return {"status": "ok", "port": PORT}

    @app.get("/projections")
    def projections():
        return {
            "model": "3-year ARR",
            "scenarios": ["base", "gtc_nvidia", "marketplace"],
            "milestones": [
                {"date": f"{yr}-{mo:02d}",
                 "base_k": v[0], "gtc_nvidia_k": v[1], "marketplace_k": v[2]}
                for (yr, mo), v in sorted(MONTHLY_ARR.items())
            ],
            "series_a_target_arr_k": 500,
            "ai_world_inflection": "2026-09",
        }


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(build_html().encode())

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
