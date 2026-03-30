"""Customer ROI Calculator V2 — port 8913
Per-customer ROI model: labor savings, payback period, 3-yr NPV.
Baseline scenario (PI): 12 robots × $4,320/day labor savings → 4.2-month payback, 3-yr NPV $1.2M.
"""

import math
import random

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8913
TITLE = "Customer ROI Calculator V2"

# ── ROI scenario data ─────────────────────────────────────────────────────────
SCENARIOS = [
    {
        "name": "PI (Baseline)",
        "robots": 12,
        "daily_labor_savings": 4320,
        "oci_monthly_cost": 3200,
        "upfront_cost": 54000,
        "payback_months": 4.2,
        "npv_3yr": 1_200_000,
        "highlight": True,
    },
    {
        "name": "Small (5 robots)",
        "robots": 5,
        "daily_labor_savings": 1800,
        "oci_monthly_cost": 1400,
        "upfront_cost": 22500,
        "payback_months": 6.8,
        "npv_3yr": 480_000,
        "highlight": False,
    },
    {
        "name": "Enterprise (40 robots)",
        "robots": 40,
        "daily_labor_savings": 14400,
        "oci_monthly_cost": 9800,
        "upfront_cost": 180_000,
        "payback_months": 3.1,
        "npv_3yr": 4_100_000,
        "highlight": False,
    },
    {
        "name": "Mid-Market (20 robots)",
        "robots": 20,
        "daily_labor_savings": 7200,
        "oci_monthly_cost": 5600,
        "upfront_cost": 90_000,
        "payback_months": 3.8,
        "npv_3yr": 2_250_000,
        "highlight": False,
    },
]

MAX_NPV = max(s["npv_3yr"] for s in SCENARIOS)
BAR_W = 320


def _npv_bar(value: float, max_val: float, highlight: bool) -> str:
    w = math.floor((value / max_val) * BAR_W)
    color = "#C74634" if highlight else "#38bdf8"
    label = f"${value/1e6:.2f}M"
    return (
        f'<rect x="0" y="4" width="{w}" height="18" rx="3" fill="{color}"/>'
        f'<text x="{w + 6}" y="18" fill="#94a3b8" font-size="12">{label}</text>'
    )


def build_html() -> str:
    # Table rows
    table_rows = ""
    for s in SCENARIOS:
        hl = ' style="background:#1e3a5f"' if s["highlight"] else ""
        badge = ' <span style="background:#7f1d1d;color:#fca5a5;padding:1px 6px;border-radius:10px;font-size:.75rem">baseline</span>' if s["highlight"] else ""
        table_rows += (
            f"<tr{hl}>"
            f"<td>{s['name']}{badge}</td>"
            f"<td>{s['robots']}</td>"
            f"<td>${s['daily_labor_savings']:,}</td>"
            f"<td>${s['oci_monthly_cost']:,}</td>"
            f"<td>{s['payback_months']} mo</td>"
            f"<td>${s['npv_3yr']:,.0f}</td>"
            f"</tr>"
        )

    # SVG bars — payback period (lower = better, invert scale)
    max_payback = max(s["payback_months"] for s in SCENARIOS)
    payback_rows = ""
    for i, s in enumerate(SCENARIOS):
        y_off = i * 34
        inv_val = max_payback - s["payback_months"] + 1  # invert so shorter = longer bar
        w = math.floor((inv_val / (max_payback + 1)) * BAR_W)
        color = "#C74634" if s["highlight"] else "#38bdf8"
        payback_rows += (
            f'<g transform="translate(0,{y_off})">'
            f'<text x="0" y="16" fill="#e2e8f0" font-size="12">{s["name"][:14]}</text>'
            f'<g transform="translate(120,0)">'
            f'<rect x="0" y="4" width="{w}" height="18" rx="3" fill="{color}"/>'
            f'<text x="{w + 6}" y="18" fill="#94a3b8" font-size="12">{s["payback_months"]} mo</text>'
            f'</g></g>'
        )

    # SVG bars — 3yr NPV
    npv_rows = ""
    for i, s in enumerate(SCENARIOS):
        y_off = i * 34
        npv_rows += (
            f'<g transform="translate(0,{y_off})">'
            f'<text x="0" y="16" fill="#e2e8f0" font-size="12">{s["name"][:14]}</text>'
            f'<g transform="translate(120,0)">{_npv_bar(s["npv_3yr"], MAX_NPV, s["highlight"])}</g>'
            f'</g>'
        )

    svg_h = len(SCENARIOS) * 34 + 10

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{TITLE}</title>
<style>
  body{{margin:0;font-family:'Segoe UI',sans-serif;background:#0f172a;color:#e2e8f0;}}
  header{{background:#1e293b;padding:20px 32px;border-bottom:2px solid #C74634;}}
  header h1{{margin:0;font-size:1.7rem;color:#C74634;}}
  header p{{margin:4px 0 0;color:#94a3b8;font-size:.9rem;}}
  main{{padding:28px 32px;display:grid;grid-template-columns:1fr 1fr;gap:24px;}}
  .card{{background:#1e293b;border-radius:10px;padding:20px;box-shadow:0 2px 8px #0004;}}
  .card h2{{margin:0 0 14px;font-size:1.1rem;color:#38bdf8;}}
  table{{width:100%;border-collapse:collapse;font-size:.85rem;}}
  th{{background:#0f172a;color:#38bdf8;padding:8px 10px;text-align:left;border-bottom:1px solid #334155;}}
  td{{padding:8px 10px;border-bottom:1px solid #1e293b;color:#cbd5e1;}}
  tr:last-child td{{border-bottom:none;}}
  .kpi-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-top:4px;}}
  .kpi{{background:#0f172a;border-radius:8px;padding:14px;text-align:center;}}
  .kpi .val{{font-size:1.6rem;font-weight:700;color:#C74634;}}
  .kpi .lbl{{font-size:.78rem;color:#64748b;margin-top:4px;}}
  footer{{text-align:center;padding:16px;color:#475569;font-size:.8rem;}}
</style>
</head>
<body>
<header>
  <h1>{TITLE}</h1>
  <p>Per-customer ROI model — labor savings, payback period, 3-yr NPV &mdash; port {PORT}</p>
</header>
<main>
  <!-- KPI strip for baseline PI scenario -->
  <div class="card" style="grid-column:1/-1">
    <h2>PI Baseline Scenario — 12 Robots</h2>
    <div class="kpi-grid">
      <div class="kpi"><div class="val">$4,320</div><div class="lbl">Daily Labor Savings</div></div>
      <div class="kpi"><div class="val">4.2 mo</div><div class="lbl">Payback Period</div></div>
      <div class="kpi"><div class="val">$1.2M</div><div class="lbl">3-Year NPV</div></div>
    </div>
  </div>
  <!-- Full scenario table -->
  <div class="card" style="grid-column:1/-1">
    <h2>ROI Scenario Table</h2>
    <table>
      <tr>
        <th>Scenario</th>
        <th>Robots</th>
        <th>Daily Labor Savings</th>
        <th>OCI Monthly Cost</th>
        <th>Payback Period</th>
        <th>3-Yr NPV</th>
      </tr>
      {table_rows}
    </table>
  </div>
  <!-- Payback period chart -->
  <div class="card">
    <h2>Payback Period Comparison (shorter = better)</h2>
    <svg width="{BAR_W + 140}" height="{svg_h}" xmlns="http://www.w3.org/2000/svg">
      {payback_rows}
    </svg>
  </div>
  <!-- 3yr NPV chart -->
  <div class="card">
    <h2>3-Year NPV Comparison</h2>
    <svg width="{BAR_W + 140}" height="{svg_h}" xmlns="http://www.w3.org/2000/svg">
      {npv_rows}
    </svg>
  </div>
</main>
<footer>OCI Robot Cloud &mdash; Customer ROI Calculator V2 &mdash; port {PORT}</footer>
</body>
</html>"""


if USE_FASTAPI:
    app = FastAPI(title=TITLE)

    @app.get("/", response_class=HTMLResponse)
    async def root():
        return build_html()

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": TITLE, "port": PORT}

    @app.get("/api/scenarios")
    async def scenarios():
        return {"scenarios": SCENARIOS}

else:
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class _H(BaseHTTPRequestHandler):
        def do_GET(self):
            body = build_html().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_): pass


if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        print(f"[fallback] Serving {TITLE} on http://0.0.0.0:{PORT}")
        HTTPServer(("0.0.0.0", PORT), _H).serve_forever()
