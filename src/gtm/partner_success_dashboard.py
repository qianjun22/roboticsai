"""Partner Success Dashboard — partner health + success tracking (NVIDIA + SI + VAR channels).

FastAPI service on port 10189.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    _FASTAPI_AVAILABLE = True
except ImportError:
    _FASTAPI_AVAILABLE = False

PORT = 10189
SERVICE_NAME = "partner_success_dashboard"

_DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Partner Success Dashboard</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; padding: 2rem; }
    h1 { color: #38bdf8; font-size: 1.8rem; margin-bottom: 0.25rem; }
    .subtitle { color: #94a3b8; font-size: 0.95rem; margin-bottom: 2rem; }
    .cards { display: flex; gap: 1.5rem; flex-wrap: wrap; margin-bottom: 2.5rem; }
    .card { background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 1.25rem 1.75rem; min-width: 160px; }
    .card-label { color: #94a3b8; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em; }
    .card-value { color: #38bdf8; font-size: 2rem; font-weight: 700; margin-top: 0.2rem; }
    .card-unit { color: #64748b; font-size: 0.85rem; }
    .section-title { color: #C74634; font-size: 1.1rem; font-weight: 600; margin-bottom: 1rem; }
    .chart-wrap { background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 1.5rem; max-width: 660px; }
    .badge { display: inline-block; background: #C74634; color: #fff; font-size: 0.75rem; border-radius: 4px; padding: 0.15rem 0.5rem; margin-left: 0.5rem; vertical-align: middle; }
    table { width: 100%; border-collapse: collapse; margin-top: 1.5rem; }
    th { background: #1e293b; color: #38bdf8; text-align: left; padding: 0.6rem 1rem; font-size: 0.8rem; text-transform: uppercase; }
    td { padding: 0.6rem 1rem; border-bottom: 1px solid #1e293b; font-size: 0.9rem; color: #cbd5e1; }
    tr:hover td { background: #1e293b; }
  </style>
</head>
<body>
  <h1>Partner Success Dashboard <span class="badge">port 10189</span></h1>
  <p class="subtitle">NVIDIA &middot; SI &middot; VAR channel health, NPS 72, enablement score 78%</p>

  <div class="cards">
    <div class="card">
      <div class="card-label">Partner NPS</div>
      <div class="card-value">72</div>
    </div>
    <div class="card">
      <div class="card-label">Enablement score</div>
      <div class="card-value">78<span class="card-unit">%</span></div>
    </div>
    <div class="card">
      <div class="card-label">NVIDIA-referred pipeline</div>
      <div class="card-value">$420<span class="card-unit">K</span></div>
    </div>
    <div class="card">
      <div class="card-label">Direct pipeline</div>
      <div class="card-value">$420<span class="card-unit">K</span></div>
    </div>
  </div>

  <div class="chart-wrap">
    <div class="section-title">Partner Pipeline by Channel ($K)</div>
    <svg width="580" height="210" viewBox="0 0 580 210" xmlns="http://www.w3.org/2000/svg">
      <!-- Axes -->
      <line x1="80" y1="10" x2="80" y2="165" stroke="#334155" stroke-width="1"/>
      <line x1="80" y1="165" x2="560" y2="165" stroke="#334155" stroke-width="1"/>
      <!-- Grid lines -->
      <line x1="80" y1="40" x2="560" y2="40" stroke="#1e293b" stroke-width="1" stroke-dasharray="4,4"/>
      <line x1="80" y1="82" x2="560" y2="82" stroke="#1e293b" stroke-width="1" stroke-dasharray="4,4"/>
      <line x1="80" y1="124" x2="560" y2="124" stroke="#1e293b" stroke-width="1" stroke-dasharray="4,4"/>
      <!-- Y labels -->
      <text x="72" y="169" fill="#64748b" font-size="11" text-anchor="end">$0K</text>
      <text x="72" y="128" fill="#64748b" font-size="11" text-anchor="end">$140K</text>
      <text x="72" y="86" fill="#64748b" font-size="11" text-anchor="end">$280K</text>
      <text x="72" y="44" fill="#64748b" font-size="11" text-anchor="end">$420K</text>
      <!-- Bar: NVIDIA-referred $420K -->
      <rect x="110" y="10" width="90" height="155" fill="#38bdf8" rx="3"/>
      <text x="155" y="6" fill="#38bdf8" font-size="12" text-anchor="middle" font-weight="bold">$420K</text>
      <text x="155" y="185" fill="#94a3b8" font-size="11" text-anchor="middle">NVIDIA-referred</text>
      <!-- Bar: direct $420K -->
      <rect x="230" y="10" width="90" height="155" fill="#C74634" rx="3"/>
      <text x="275" y="6" fill="#C74634" font-size="12" text-anchor="middle" font-weight="bold">$420K</text>
      <text x="275" y="185" fill="#94a3b8" font-size="11" text-anchor="middle">Direct</text>
      <!-- Bar: SI $0 -->
      <rect x="350" y="163" width="90" height="2" fill="#7c3aed" rx="1"/>
      <text x="395" y="158" fill="#a78bfa" font-size="12" text-anchor="middle" font-weight="bold">$0</text>
      <text x="395" y="185" fill="#94a3b8" font-size="11" text-anchor="middle">SI</text>
      <!-- Bar: VAR $0 -->
      <rect x="460" y="163" width="90" height="2" fill="#059669" rx="1"/>
      <text x="505" y="158" fill="#34d399" font-size="12" text-anchor="middle" font-weight="bold">$0</text>
      <text x="505" y="185" fill="#94a3b8" font-size="11" text-anchor="middle">VAR</text>
    </svg>
  </div>

  <table style="margin-top:2rem; max-width:660px;">
    <thead><tr><th>Endpoint</th><th>Method</th><th>Description</th></tr></thead>
    <tbody>
      <tr><td>/health</td><td>GET</td><td>Service health &amp; metadata</td></tr>
      <tr><td>/partners/success/dashboard</td><td>GET</td><td>Partner health scores &amp; pipeline by channel</td></tr>
      <tr><td>/partners/success/alerts</td><td>GET</td><td>Active partner health alerts &amp; action items</td></tr>
    </tbody>
  </table>
</body>
</html>
"""

if _FASTAPI_AVAILABLE:
    app = FastAPI(title=SERVICE_NAME, version="1.0.0")

    @app.get("/health")
    async def health() -> JSONResponse:
        return JSONResponse({
            "status": "ok",
            "port": PORT,
            "service": SERVICE_NAME,
            "version": "1.0.0",
            "description": "Partner health + success tracking (NVIDIA, SI, VAR channels)",
        })

    @app.get("/", response_class=HTMLResponse)
    async def dashboard() -> HTMLResponse:
        return HTMLResponse(content=_DASHBOARD_HTML)

    @app.get("/partners/success/dashboard")
    async def partner_dashboard() -> JSONResponse:
        """Stub: return partner health scores and pipeline data by channel."""
        return JSONResponse({
            "partner_nps": 72,
            "enablement_score_pct": 78,
            "channels": [
                {
                    "name": "NVIDIA-referred",
                    "pipeline_usd": 420000,
                    "active_deals": 3,
                    "health": "green",
                    "cadence": "weekly",
                },
                {
                    "name": "Direct",
                    "pipeline_usd": 420000,
                    "active_deals": 4,
                    "health": "green",
                    "cadence": "bi-weekly",
                },
                {
                    "name": "SI",
                    "pipeline_usd": 0,
                    "active_deals": 0,
                    "health": "red",
                    "cadence": "monthly",
                },
                {
                    "name": "VAR",
                    "pipeline_usd": 0,
                    "active_deals": 0,
                    "health": "red",
                    "cadence": "monthly",
                },
            ],
        })

    @app.get("/partners/success/alerts")
    async def partner_alerts() -> JSONResponse:
        """Stub: return active partner health alerts and action items."""
        return JSONResponse({
            "alerts": [
                {
                    "severity": "high",
                    "channel": "SI",
                    "message": "No active pipeline — SI partner enablement overdue",
                    "action": "Schedule SI enablement workshop within 2 weeks",
                },
                {
                    "severity": "high",
                    "channel": "VAR",
                    "message": "No active pipeline — VAR recruitment not started",
                    "action": "Identify and onboard 2 VAR partners by end of quarter",
                },
                {
                    "severity": "low",
                    "channel": "NVIDIA-referred",
                    "message": "NPS below target (72 vs 80 target)",
                    "action": "Conduct partner satisfaction survey and address top feedback",
                },
            ],
            "total_alerts": 3,
            "critical": 0,
            "high": 2,
            "low": 1,
        })

else:
    # Fallback: stdlib HTTP server
    import http.server

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/health":
                body = json.dumps({"status": "ok", "port": PORT, "service": SERVICE_NAME}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)
            else:
                body = _DASHBOARD_HTML.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(body)

        def log_message(self, fmt, *args):  # suppress default logging
            pass

    def _serve():
        server = http.server.HTTPServer(("0.0.0.0", PORT), _Handler)
        print(f"[{SERVICE_NAME}] fallback HTTP server on port {PORT}")
        server.serve_forever()

if __name__ == "__main__":
    if _FASTAPI_AVAILABLE:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        _serve()
