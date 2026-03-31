"""MRR Dashboard — Monthly Recurring Revenue detailed tracking service.

Port: 10267
Tracks new + expansion + contraction + churn MRR components.
Customers: Machina $15.6K/mo, Verdant $4.2K/mo, Helix $2.8K/mo — total $22.6K/mo.
MoM growth 8.6%; ARR run rate $271K; MRR target June $35.8K; 100% cohort retention.
"""

PORT = 10267
SERVICE_NAME = "mrr_dashboard"

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    _FASTAPI_AVAILABLE = True
except ImportError:
    _FASTAPI_AVAILABLE = False

if _FASTAPI_AVAILABLE:
    app = FastAPI(title=SERVICE_NAME, version="1.0.0")

    @app.get("/health")
    def health():
        return JSONResponse({"status": "ok", "port": PORT, "service": SERVICE_NAME})

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return HTMLResponse(content=_html_dashboard())

    @app.get("/finance/mrr/dashboard")
    def mrr_dashboard():
        return JSONResponse({
            "period": "2026-03",
            "mrr_total_usd": 22600,
            "customers": [
                {"name": "Machina", "mrr": 15600, "status": "active"},
                {"name": "Verdant", "mrr": 4200, "status": "active"},
                {"name": "Helix",   "mrr": 2800, "status": "active"}
            ],
            "components": {
                "new_mrr": 2800,
                "expansion_mrr": 1400,
                "contraction_mrr": -200,
                "churn_mrr": 0
            },
            "mom_growth_pct": 8.6,
            "arr_run_rate_usd": 271200,
            "cohort_retention_pct": 100.0
        })

    @app.get("/finance/mrr/forecast")
    def mrr_forecast():
        return JSONResponse({
            "forecast_month": "2026-06",
            "mrr_target_usd": 35800,
            "mrr_current_usd": 22600,
            "gap_usd": 13200,
            "months_remaining": 3,
            "required_mom_growth_pct": 16.5,
            "scenarios": [
                {"label": "conservative", "mrr_june": 29400, "mom_growth": 9.0},
                {"label": "base",         "mrr_june": 33800, "mom_growth": 14.2},
                {"label": "optimistic",   "mrr_june": 38200, "mom_growth": 19.1}
            ]
        })

def _html_dashboard() -> str:
    return """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>MRR Dashboard — Port 10267</title>
  <style>
    body { margin: 0; background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; }
    header { background: #C74634; padding: 18px 32px; display: flex; align-items: center; gap: 16px; }
    header h1 { margin: 0; font-size: 1.4rem; font-weight: 700; letter-spacing: 0.02em; }
    header span { font-size: 0.85rem; opacity: 0.85; }
    .container { max-width: 900px; margin: 36px auto; padding: 0 24px; }
    .card { background: #1e293b; border-radius: 10px; padding: 24px 28px; margin-bottom: 24px; border: 1px solid #334155; }
    .card h2 { margin: 0 0 16px; font-size: 1.05rem; color: #38bdf8; text-transform: uppercase; letter-spacing: 0.06em; }
    .kpi-row { display: flex; gap: 20px; flex-wrap: wrap; margin-bottom: 24px; }
    .kpi { background: #1e293b; border-radius: 8px; padding: 14px 20px; flex: 1; min-width: 140px; border: 1px solid #334155; }
    .kpi .val { font-size: 1.7rem; font-weight: 700; color: #38bdf8; }
    .kpi .lbl { font-size: 0.78rem; color: #94a3b8; margin-top: 4px; }
    .badge { display: inline-block; background: #4ade80; color: #0f172a; border-radius: 5px; padding: 2px 10px; font-size: 0.78rem; font-weight: 700; }
    table { width: 100%; border-collapse: collapse; font-size: 0.9rem; }
    th { color: #94a3b8; text-align: left; padding: 8px 10px; border-bottom: 1px solid #334155; }
    td { padding: 8px 10px; border-bottom: 1px solid #1e293b; }
    tr:last-child td { border-bottom: none; }
    .good { color: #4ade80; } .warn { color: #facc15; } .red { color: #f87171; }
  </style>
</head>
<body>
  <header>
    <div>
      <h1>MRR Dashboard — Monthly Recurring Revenue</h1>
      <span>Port 10267 &nbsp;|&nbsp; OCI Robot Cloud &nbsp;|&nbsp; Cycle 552B</span>
    </div>
  </header>
  <div class="container">
    <div class="kpi-row">
      <div class="kpi"><div class="val">$22.6K</div><div class="lbl">Total MRR (Mar 2026)</div></div>
      <div class="kpi"><div class="val good">+8.6%</div><div class="lbl">MoM Growth</div></div>
      <div class="kpi"><div class="val">$271K</div><div class="lbl">ARR Run Rate</div></div>
      <div class="kpi"><div class="val">$35.8K</div><div class="lbl">MRR Target (June)</div></div>
      <div class="kpi"><div class="val good">100%</div><div class="lbl">Cohort Retention</div></div>
    </div>
    <div class="card">
      <h2>MRR by Customer</h2>
      <svg viewBox="0 0 560 210" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:560px;display:block;">
        <!-- axes -->
        <line x1="60" y1="10" x2="60" y2="165" stroke="#475569" stroke-width="1"/>
        <line x1="60" y1="165" x2="530" y2="165" stroke="#475569" stroke-width="1"/>
        <!-- Machina $15.6K — tallest bar -->
        <rect x="80"  y="62"  width="110" height="103" rx="4" fill="#38bdf8"/>
        <text x="135" y="56"  fill="#38bdf8" font-size="12" font-weight="700" text-anchor="middle">$15.6K</text>
        <text x="135" y="183" fill="#94a3b8" font-size="12" text-anchor="middle">Machina</text>
        <!-- Verdant $4.2K -->
        <rect x="220" y="137" width="110" height="28"  rx="4" fill="#C74634"/>
        <text x="275" y="130" fill="#C74634" font-size="12" font-weight="700" text-anchor="middle">$4.2K</text>
        <text x="275" y="183" fill="#94a3b8" font-size="12" text-anchor="middle">Verdant</text>
        <!-- Helix $2.8K -->
        <rect x="360" y="146" width="110" height="19"  rx="4" fill="#818cf8"/>
        <text x="415" y="140" fill="#818cf8" font-size="12" font-weight="700" text-anchor="middle">$2.8K</text>
        <text x="415" y="183" fill="#94a3b8" font-size="12" text-anchor="middle">Helix</text>
        <!-- y-axis -->
        <text x="52" y="168" fill="#64748b" font-size="10" text-anchor="end">$0</text>
        <text x="52" y="100" fill="#64748b" font-size="10" text-anchor="end">$8K</text>
        <text x="52" y="15"  fill="#64748b" font-size="10" text-anchor="end">$16K</text>
        <!-- total label -->
        <text x="510" y="80"  fill="#4ade80" font-size="13" font-weight="700" text-anchor="middle">$22.6K</text>
        <text x="510" y="95"  fill="#94a3b8" font-size="11" text-anchor="middle">total</text>
      </svg>
    </div>
    <div class="card">
      <h2>MRR Components (Mar 2026)</h2>
      <table>
        <tr><th>Component</th><th>Amount</th><th>Notes</th></tr>
        <tr><td>New MRR</td><td class="good">+$2,800</td><td>Helix onboarded</td></tr>
        <tr><td>Expansion MRR</td><td class="good">+$1,400</td><td>Machina seat expansion</td></tr>
        <tr><td>Contraction MRR</td><td class="warn">-$200</td><td>Verdant plan downgrade</td></tr>
        <tr><td>Churn MRR</td><td class="good">$0</td><td>0% churn this month</td></tr>
        <tr><td><strong>Net New MRR</strong></td><td><strong class="good">+$4,000</strong></td><td><span class="badge">+8.6% MoM</span></td></tr>
      </table>
    </div>
    <div class="card">
      <h2>June Forecast</h2>
      <table>
        <tr><th>Scenario</th><th>MRR June</th><th>Req. MoM Growth</th></tr>
        <tr><td>Conservative</td><td>$29,400</td><td class="warn">9.0%</td></tr>
        <tr><td>Base</td><td>$33,800</td><td class="warn">14.2%</td></tr>
        <tr><td>Optimistic</td><td class="good">$38,200</td><td class="good">19.1%</td></tr>
        <tr><td><strong>Target</strong></td><td><strong>$35,800</strong></td><td>16.5%</td></tr>
      </table>
    </div>
    <div class="card" style="font-size:0.82rem;color:#64748b;padding:14px 20px;">
      Endpoints: <code>GET /health</code> &nbsp;|&nbsp; <code>GET /finance/mrr/dashboard</code> &nbsp;|&nbsp; <code>GET /finance/mrr/forecast</code>
    </div>
  </div>
</body>
</html>
"""


if not _FASTAPI_AVAILABLE:
    import http.server
    import json

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/health":
                body = json.dumps({"status": "ok", "port": PORT, "service": SERVICE_NAME}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)
            else:
                body = _html_dashboard().encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(body)

        def log_message(self, fmt, *args):  # suppress default logging
            pass


if __name__ == "__main__":
    if _FASTAPI_AVAILABLE:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        server = http.server.HTTPServer(("0.0.0.0", PORT), _Handler)
        print(f"Fallback HTTP server running on port {PORT}")
        server.serve_forever()
