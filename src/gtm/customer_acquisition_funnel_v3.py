"""Customer Acquisition Funnel v3 — multi-channel with AI World boost modeling.

Port 10187 | cycle-532B
Channels: NVIDIA referral, inbound content, conference, outbound SDR, partner.
"""

import json
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = 10187
SERVICE_NAME = "customer_acquisition_funnel_v3"

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    _FASTAPI = True
except ImportError:
    _FASTAPI = False

_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Customer Acquisition Funnel v3</title>
  <style>
    body { margin: 0; background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; }
    header { background: #C74634; padding: 20px 32px; }
    header h1 { margin: 0; font-size: 1.6rem; letter-spacing: .5px; }
    header p  { margin: 4px 0 0; font-size: .9rem; opacity: .85; }
    main { padding: 32px; max-width: 900px; }
    .card { background: #1e293b; border-radius: 10px; padding: 24px; margin-bottom: 24px; }
    .card h2 { margin-top: 0; color: #38bdf8; font-size: 1.1rem; }
    .kv { display: flex; gap: 32px; flex-wrap: wrap; }
    .kv div { min-width: 130px; }
    .kv .label { font-size: .75rem; color: #94a3b8; text-transform: uppercase; letter-spacing: .5px; }
    .kv .value { font-size: 1.5rem; font-weight: 700; color: #f8fafc; }
    table { width: 100%; border-collapse: collapse; font-size: .88rem; }
    th { text-align: left; padding: 8px 12px; color: #94a3b8; border-bottom: 1px solid #334155; }
    td { padding: 8px 12px; border-bottom: 1px solid #1e293b; }
    tr:hover td { background: #0f172a; }
    .endpoints li { margin: 6px 0; font-size: .9rem; color: #cbd5e1; }
    .endpoints code { background: #0f172a; border-radius: 4px; padding: 2px 6px; color: #38bdf8; }
  </style>
</head>
<body>
  <header>
    <h1>Customer Acquisition Funnel v3</h1>
    <p>Multi-Channel &nbsp;|&nbsp; AI World Boost Modeling &nbsp;|&nbsp; Port {port}</p>
  </header>
  <main>
    <div class="card">
      <h2>Funnel Volume (per month)</h2>
      <svg width="520" height="190" viewBox="0 0 520 190" xmlns="http://www.w3.org/2000/svg">
        <!-- MQLs 24 → bar width scaled: 24/24 * 400 = 400 -->
        <rect x="70" y="10"  width="400" height="36" rx="4" fill="#C74634"/>
        <text x="478" y="34" fill="#f8fafc" font-size="12" font-weight="bold">24 MQLs</text>
        <!-- SQLs 14 → 14/24 * 400 ≈ 233 -->
        <rect x="70" y="55"  width="233" height="36" rx="4" fill="#38bdf8"/>
        <text x="311" y="79" fill="#f8fafc" font-size="12" font-weight="bold">14 SQLs</text>
        <!-- Trials 6 → 6/24 * 400 = 100 -->
        <rect x="70" y="100" width="100" height="36" rx="4" fill="#6366f1"/>
        <text x="178" y="124" fill="#f8fafc" font-size="12" font-weight="bold">6 Trials</text>
        <!-- Closed 1.2 → 1.2/24 * 400 = 20 -->
        <rect x="70" y="145" width="20"  height="36" rx="4" fill="#22c55e"/>
        <text x="98"  y="169" fill="#f8fafc" font-size="12" font-weight="bold">1.2 Closed</text>
        <!-- y-axis -->
        <line x1="70" y1="0" x2="70" y2="185" stroke="#334155" stroke-width="1"/>
      </svg>
    </div>
    <div class="card">
      <h2>Monthly Funnel KPIs</h2>
      <div class="kv">
        <div><div class="label">MQLs</div><div class="value">24</div></div>
        <div><div class="label">SQLs</div><div class="value">14</div></div>
        <div><div class="label">Trials</div><div class="value">6</div></div>
        <div><div class="label">Closed</div><div class="value">1.2</div></div>
      </div>
    </div>
    <div class="card">
      <h2>Channel Mix</h2>
      <table>
        <thead><tr><th>Channel</th><th>MQL Contribution</th></tr></thead>
        <tbody>
          <tr><td>NVIDIA Referral</td><td>35%</td></tr>
          <tr><td>Inbound Content</td><td>25%</td></tr>
          <tr><td>Conference</td><td>20%</td></tr>
          <tr><td>Outbound SDR</td><td>12%</td></tr>
          <tr><td>Partner</td><td>8%</td></tr>
        </tbody>
      </table>
    </div>
    <div class="card">
      <h2>API Endpoints</h2>
      <ul class="endpoints">
        <li><code>GET /health</code> &mdash; liveness check</li>
        <li><code>GET /funnel/v3/metrics</code> &mdash; current funnel metrics</li>
        <li><code>GET /funnel/v3/forecast</code> &mdash; AI World boost forecast</li>
      </ul>
    </div>
  </main>
</body>
</html>
""".replace("{port}", str(PORT))

if _FASTAPI:
    app = FastAPI(title=SERVICE_NAME)

    @app.get("/health")
    def health():
        return JSONResponse({"status": "ok", "port": PORT, "service": SERVICE_NAME})

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return HTMLResponse(content=_HTML)

    @app.get("/funnel/v3/metrics")
    def metrics():
        return JSONResponse({
            "version": 3,
            "period": "monthly",
            "mqls": 24,
            "sqls": 14,
            "trials": 6,
            "closed": 1.2,
            "channels": [
                {"name": "nvidia_referral",  "mql_share": 0.35},
                {"name": "inbound_content",  "mql_share": 0.25},
                {"name": "conference",       "mql_share": 0.20},
                {"name": "outbound_sdr",     "mql_share": 0.12},
                {"name": "partner",          "mql_share": 0.08},
            ],
        })

    @app.get("/funnel/v3/forecast")
    def forecast():
        return JSONResponse({
            "model": "ai_world_boost_v3",
            "forecast_period": "next_quarter",
            "projected_mqls": 38,
            "projected_sqls": 22,
            "projected_trials": 9,
            "projected_closed": 2.1,
            "ai_world_boost_multiplier": 1.58,
            "top_channel_forecast": "nvidia_referral",
        })

else:
    class _Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            if self.path == "/health":
                body = json.dumps({"status": "ok", "port": PORT, "service": SERVICE_NAME}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)
            else:
                body = _HTML.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(body)

    def _serve():
        server = HTTPServer(("0.0.0.0", PORT), _Handler)
        print(f"[{SERVICE_NAME}] fallback HTTP server on port {PORT}")
        server.serve_forever()

if __name__ == "__main__":
    if _FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        _serve()
