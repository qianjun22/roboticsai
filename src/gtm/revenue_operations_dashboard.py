"""Revenue Operations Dashboard — unified RevOps view.

Pipeline + forecast + retention + expansion metrics in one service.

KPIs:
  ARR $250K | NRR 118% | Win Rate 73% | Pipeline $840K
  CAC $10.2K | LTV $415K | Payback 5.4mo | Churn 0%

Port: 10163
"""

import json
import time
from typing import Any, Dict, List

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    _FASTAPI = True
except ImportError:
    _FASTAPI = False

PORT = 10163
SERVICE_NAME = "revenue_operations_dashboard"

_START_TIME = time.time()

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------
_DASHBOARD_DATA: Dict[str, Any] = {
    "arr_usd": 250_000,
    "nrr_pct": 118,
    "win_rate_pct": 73,
    "pipeline_usd": 840_000,
    "cac_usd": 10_200,
    "ltv_usd": 415_000,
    "payback_months": 5.4,
    "churn_pct": 0.0,
    "updated_at": "2026-03-30T00:00:00Z",
}

_ALERTS: List[Dict[str, Any]] = [
    {"severity": "info",    "message": "NRR exceeded 115% target — expansion momentum strong."},
    {"severity": "info",    "message": "Pipeline coverage 3.4× ARR — healthy for Q2 close."},
    {"severity": "warning", "message": "2 design-partner trials expire in 14 days — follow up."},
]


def _html_dashboard() -> str:
    return """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Revenue Operations Dashboard — Port 10163</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; padding: 2rem; }
    h1 { color: #C74634; font-size: 1.6rem; margin-bottom: 0.25rem; }
    .subtitle { color: #38bdf8; font-size: 0.9rem; margin-bottom: 2rem; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 1rem; margin-bottom: 2rem; }
    .card { background: #1e293b; border-radius: 8px; padding: 1.25rem; border: 1px solid #334155; }
    .card .label { font-size: 0.72rem; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.4rem; }
    .card .value { font-size: 1.45rem; font-weight: 700; color: #f1f5f9; }
    .chart-section { background: #1e293b; border-radius: 8px; padding: 1.5rem; border: 1px solid #334155; margin-bottom: 2rem; }
    .chart-section h2 { color: #38bdf8; font-size: 1rem; margin-bottom: 1.25rem; }
    .alerts { background: #1e293b; border-radius: 8px; padding: 1.5rem; border: 1px solid #334155; }
    .alerts h2 { color: #38bdf8; font-size: 1rem; margin-bottom: 1rem; }
    .alert-item { display: flex; align-items: flex-start; gap: 0.75rem; margin-bottom: 0.75rem; }
    .badge { border-radius: 4px; padding: 0.15rem 0.5rem; font-size: 0.7rem; font-weight: 700; text-transform: uppercase; white-space: nowrap; }
    .info    { background: #0c4a6e; color: #38bdf8; }
    .warning { background: #78350f; color: #fcd34d; }
    footer { margin-top: 2rem; font-size: 0.75rem; color: #475569; }
  </style>
</head>
<body>
  <h1>Revenue Operations Dashboard</h1>
  <p class="subtitle">Unified Pipeline &middot; Forecast &middot; Retention &middot; Expansion &mdash; Port 10163</p>

  <div class="grid">
    <div class="card"><div class="label">ARR</div><div class="value" style="color:#38bdf8">$250K</div></div>
    <div class="card"><div class="label">NRR</div><div class="value" style="color:#86efac">118%</div></div>
    <div class="card"><div class="label">Win Rate</div><div class="value">73%</div></div>
    <div class="card"><div class="label">Pipeline</div><div class="value" style="color:#38bdf8">$840K</div></div>
    <div class="card"><div class="label">CAC</div><div class="value">$10.2K</div></div>
    <div class="card"><div class="label">LTV</div><div class="value" style="color:#86efac">$415K</div></div>
    <div class="card"><div class="label">Payback</div><div class="value">5.4 mo</div></div>
    <div class="card"><div class="label">Churn</div><div class="value" style="color:#86efac">0%</div></div>
  </div>

  <div class="chart-section">
    <h2>Key Revenue KPIs</h2>
    <!-- Normalised bar chart: values scaled to fit 120px height -->
    <!-- ARR $250K → 250, NRR 118% → 118, Win Rate 73% → 73, Pipeline $840K → 840 -->
    <!-- Scale: 840 → 110px → factor = 110/840 ≈ 0.1310 -->
    <svg viewBox="0 0 440 175" xmlns="http://www.w3.org/2000/svg" width="100%" style="max-width:520px">
      <!-- axes -->
      <line x1="55" y1="10" x2="55" y2="130" stroke="#475569" stroke-width="1"/>
      <line x1="55" y1="130" x2="430" y2="130" stroke="#475569" stroke-width="1"/>
      <!-- grid -->
      <line x1="55" y1="40" x2="430" y2="40" stroke="#334155" stroke-width="0.5" stroke-dasharray="4,3"/>
      <line x1="55" y1="70" x2="430" y2="70" stroke="#334155" stroke-width="0.5" stroke-dasharray="4,3"/>
      <line x1="55" y1="100" x2="430" y2="100" stroke="#334155" stroke-width="0.5" stroke-dasharray="4,3"/>
      <!-- y-axis labels (raw units labelled on chart) -->
      <!-- ARR $250K: height=250*0.131=32.75; y=130-32=98 -->
      <rect x="70"  y="98"  width="55" height="32" fill="#38bdf8" rx="3"/>
      <text x="97"  y="93"  fill="#38bdf8"  font-size="9" font-weight="bold" text-anchor="middle">$250K</text>
      <text x="97"  y="145" fill="#cbd5e1" font-size="8" text-anchor="middle">ARR</text>
      <!-- NRR 118%: height=118*0.131=15.5; y=130-15=115 -->
      <rect x="155" y="115" width="55" height="15" fill="#86efac" rx="3"/>
      <text x="182" y="110" fill="#86efac"  font-size="9" font-weight="bold" text-anchor="middle">118%</text>
      <text x="182" y="145" fill="#cbd5e1" font-size="8" text-anchor="middle">NRR</text>
      <!-- Win Rate 73%: height=73*0.131=9.6; y=130-10=120 -->
      <rect x="240" y="120" width="55" height="10" fill="#C74634" rx="3"/>
      <text x="267" y="115" fill="#C74634"  font-size="9" font-weight="bold" text-anchor="middle">73%</text>
      <text x="267" y="145" fill="#cbd5e1" font-size="8" text-anchor="middle">Win Rate</text>
      <!-- Pipeline $840K: height=840*0.131=110; y=130-110=20 -->
      <rect x="325" y="20"  width="55" height="110" fill="#7c3aed" rx="3"/>
      <text x="352" y="15"  fill="#a78bfa"  font-size="9" font-weight="bold" text-anchor="middle">$840K</text>
      <text x="352" y="145" fill="#cbd5e1" font-size="8" text-anchor="middle">Pipeline</text>
    </svg>
  </div>

  <div class="alerts">
    <h2>Active Alerts</h2>
    <div class="alert-item"><span class="badge info">info</span><span>NRR exceeded 115% target — expansion momentum strong.</span></div>
    <div class="alert-item"><span class="badge info">info</span><span>Pipeline coverage 3.4&times; ARR — healthy for Q2 close.</span></div>
    <div class="alert-item"><span class="badge warning">warn</span><span>2 design-partner trials expire in 14 days — follow up.</span></div>
  </div>

  <footer>OCI Robot Cloud &mdash; Revenue Operations Dashboard &mdash; Port 10163</footer>
</body>
</html>
"""


if _FASTAPI:
    app = FastAPI(title=SERVICE_NAME, version="1.0.0")

    @app.get("/health")
    def health():
        return JSONResponse({
            "status": "ok",
            "port": PORT,
            "service": SERVICE_NAME,
            "uptime_seconds": round(time.time() - _START_TIME, 1),
        })

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return HTMLResponse(_html_dashboard())

    @app.get("/revops/dashboard")
    def get_dashboard():
        return JSONResponse(_DASHBOARD_DATA)

    @app.get("/revops/alerts")
    def get_alerts():
        return JSONResponse({"alerts": _ALERTS, "count": len(_ALERTS)})

else:
    import http.server
    import urllib.parse

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            path = urllib.parse.urlparse(self.path).path
            if path == "/health":
                body = json.dumps({"status": "ok", "port": PORT, "service": SERVICE_NAME}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
            elif path == "/revops/dashboard":
                body = json.dumps(_DASHBOARD_DATA).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
            elif path == "/revops/alerts":
                body = json.dumps({"alerts": _ALERTS, "count": len(_ALERTS)}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
            else:
                body = _html_dashboard().encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    def _serve():
        server = http.server.HTTPServer(("0.0.0.0", PORT), _Handler)
        print(f"[{SERVICE_NAME}] fallback HTTP server on port {PORT}")
        server.serve_forever()


if __name__ == "__main__":
    if _FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        _serve()
