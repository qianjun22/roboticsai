"""Churn Prevention Engine — ML-driven predict + intervene service (port 10183)."""

import json
import random
from datetime import datetime

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    from fastapi import Body
    import uvicorn
    _FASTAPI_AVAILABLE = True
except ImportError:
    _FASTAPI_AVAILABLE = False

PORT = 10183
SERVICE_NAME = "churn_prevention_engine"

_MOCK_AT_RISK = [
    {"account_id": "ACC-1042", "account_name": "Acme Robotics", "churn_prob": 0.83, "days_to_renewal": 28, "arr": 240000, "recommended_action": "emergency_retention"},
    {"account_id": "ACC-2187", "account_name": "Vertex AI Labs", "churn_prob": 0.71, "days_to_renewal": 47, "arr": 185000, "recommended_action": "exec_alignment"},
    {"account_id": "ACC-3305", "account_name": "Synapse Dynamics", "churn_prob": 0.58, "days_to_renewal": 74, "arr": 310000, "recommended_action": "exec_alignment"},
    {"account_id": "ACC-4490", "account_name": "OmniRobot Inc", "churn_prob": 0.44, "days_to_renewal": 95, "arr": 420000, "recommended_action": "success_call"},
]

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Churn Prevention Engine</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; padding: 2rem; }
  h1 { color: #C74634; font-size: 1.8rem; margin-bottom: 0.5rem; }
  .subtitle { color: #94a3b8; margin-bottom: 2rem; font-size: 0.95rem; }
  .badge { display: inline-block; background: #1e293b; border: 1px solid #334155; border-radius: 9999px; padding: 0.2rem 0.75rem; font-size: 0.75rem; color: #38bdf8; margin-right: 0.5rem; }
  .card { background: #1e293b; border: 1px solid #334155; border-radius: 0.75rem; padding: 1.5rem; margin-bottom: 1.5rem; }
  .card h2 { color: #38bdf8; font-size: 1.1rem; margin-bottom: 1rem; }
  .metrics { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 1rem; margin-bottom: 1.5rem; }
  .metric { background: #0f172a; border: 1px solid #334155; border-radius: 0.5rem; padding: 1rem; text-align: center; }
  .metric .value { font-size: 2rem; font-weight: 700; color: #C74634; }
  .metric .label { font-size: 0.75rem; color: #64748b; margin-top: 0.25rem; }
  .chart-wrap { overflow-x: auto; }
  .endpoints { list-style: none; }
  .endpoints li { padding: 0.5rem 0; border-bottom: 1px solid #334155; color: #cbd5e1; font-family: monospace; font-size: 0.85rem; }
  .endpoints li:last-child { border-bottom: none; }
  .method { display: inline-block; padding: 0.1rem 0.5rem; border-radius: 0.25rem; font-size: 0.7rem; font-weight: 700; margin-right: 0.5rem; }
  .get { background: #166534; color: #86efac; }
  .post { background: #1e3a5f; color: #93c5fd; }
  table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
  th { color: #64748b; text-align: left; padding: 0.5rem; border-bottom: 1px solid #334155; }
  td { padding: 0.5rem; border-bottom: 1px solid #1e293b; }
  .risk-high { color: #f87171; font-weight: 600; }
  .risk-med { color: #fb923c; font-weight: 600; }
  .risk-low { color: #4ade80; font-weight: 600; }
</style>
</head>
<body>
<h1>Churn Prevention Engine</h1>
<p class="subtitle">
  <span class="badge">port 10183</span>
  <span class="badge">ML-driven</span>
  <span class="badge">predict + intervene</span>
  Predict churn risk before customer decision and trigger optimal intervention playbooks.
</p>

<div class="metrics">
  <div class="metric"><div class="value">0.91</div><div class="label">AUC-ROC</div></div>
  <div class="metric"><div class="value">87%</div><div class="label">Recall</div></div>
  <div class="metric"><div class="value">82%</div><div class="label">Precision</div></div>
  <div class="metric"><div class="value">35:1</div><div class="label">Prevention ROI</div></div>
  <div class="metric"><div class="value">$83K</div><div class="label">Saved / Prevented Churn</div></div>
</div>

<div class="card">
  <h2>Intervention Timing — Success Rate by Days Before Renewal</h2>
  <div class="chart-wrap">
    <svg viewBox="0 0 480 200" xmlns="http://www.w3.org/2000/svg" width="480" height="210">
      <!-- Y-axis labels -->
      <text x="32" y="20"  fill="#64748b" font-size="11" text-anchor="end">100%</text>
      <text x="32" y="58"  fill="#64748b" font-size="11" text-anchor="end">75%</text>
      <text x="32" y="96"  fill="#64748b" font-size="11" text-anchor="end">50%</text>
      <text x="32" y="134" fill="#64748b" font-size="11" text-anchor="end">25%</text>
      <text x="32" y="170" fill="#64748b" font-size="11" text-anchor="end">0%</text>
      <!-- Gridlines -->
      <line x1="36" y1="15"  x2="475" y2="15"  stroke="#1e293b" stroke-width="1"/>
      <line x1="36" y1="53"  x2="475" y2="53"  stroke="#1e293b" stroke-width="1"/>
      <line x1="36" y1="91"  x2="475" y2="91"  stroke="#1e293b" stroke-width="1"/>
      <line x1="36" y1="129" x2="475" y2="129" stroke="#1e293b" stroke-width="1"/>
      <line x1="36" y1="165" x2="475" y2="165" stroke="#334155" stroke-width="1"/>
      <!-- Bars: 90d=78%, 60d=64%, 30d=41%, 15d=19% -->
      <!-- 90 days out — success call — 78% height=(78/100)*150=117 y=165-117=48 -->
      <rect x="65"  y="48"  width="70" height="117" fill="#38bdf8" rx="3"/>
      <!-- 60 days — exec alignment — 64% height=96 y=69 -->
      <rect x="185" y="69"  width="70" height="96"  fill="#38bdf8" rx="3"/>
      <!-- 30 days — emergency retention — 41% height=62 y=103 -->
      <rect x="305" y="103" width="70" height="62"  fill="#C74634" rx="3"/>
      <!-- 15 days — win-back — 19% height=29 y=136 -->
      <rect x="395" y="136" width="70" height="29"  fill="#C74634" rx="3"/>
      <!-- Value labels -->
      <text x="100"  y="44"  fill="#38bdf8" font-size="11" text-anchor="middle">78%</text>
      <text x="220"  y="65"  fill="#38bdf8" font-size="11" text-anchor="middle">64%</text>
      <text x="340"  y="99"  fill="#f87171" font-size="11" text-anchor="middle">41%</text>
      <text x="430"  y="132" fill="#f87171" font-size="11" text-anchor="middle">19%</text>
      <!-- X-axis labels -->
      <text x="100"  y="182" fill="#94a3b8" font-size="9" text-anchor="middle">90 days out</text>
      <text x="100"  y="193" fill="#64748b" font-size="8" text-anchor="middle">Success Call</text>
      <text x="220"  y="182" fill="#94a3b8" font-size="9" text-anchor="middle">60 days out</text>
      <text x="220"  y="193" fill="#64748b" font-size="8" text-anchor="middle">Exec Alignment</text>
      <text x="340"  y="182" fill="#94a3b8" font-size="9" text-anchor="middle">30 days out</text>
      <text x="340"  y="193" fill="#64748b" font-size="8" text-anchor="middle">Emergency Retention</text>
      <text x="430"  y="182" fill="#94a3b8" font-size="9" text-anchor="middle">15 days out</text>
      <text x="430"  y="193" fill="#64748b" font-size="8" text-anchor="middle">Win-back</text>
      <!-- Legend -->
      <rect x="65" y="200" width="10" height="8" fill="#38bdf8" rx="1"/>
      <text x="78" y="208" fill="#94a3b8" font-size="8">High success window</text>
      <rect x="200" y="200" width="10" height="8" fill="#C74634" rx="1"/>
      <text x="213" y="208" fill="#94a3b8" font-size="8">Late / low success</text>
    </svg>
  </div>
</div>

<div class="card">
  <h2>At-Risk Accounts (Mock)</h2>
  <table>
    <thead>
      <tr><th>Account</th><th>Churn Prob</th><th>Days to Renewal</th><th>ARR</th><th>Recommended Action</th></tr>
    </thead>
    <tbody>
      <tr><td>Acme Robotics</td><td><span class="risk-high">83%</span></td><td>28</td><td>$240K</td><td>Emergency Retention</td></tr>
      <tr><td>Vertex AI Labs</td><td><span class="risk-high">71%</span></td><td>47</td><td>$185K</td><td>Exec Alignment</td></tr>
      <tr><td>Synapse Dynamics</td><td><span class="risk-med">58%</span></td><td>74</td><td>$310K</td><td>Exec Alignment</td></tr>
      <tr><td>OmniRobot Inc</td><td><span class="risk-low">44%</span></td><td>95</td><td>$420K</td><td>Success Call</td></tr>
    </tbody>
  </table>
</div>

<div class="card">
  <h2>API Endpoints</h2>
  <ul class="endpoints">
    <li><span class="method get">GET</span>/health — service health check</li>
    <li><span class="method get">GET</span>/ — this dashboard</li>
    <li><span class="method get">GET</span>/churn/predictions — at-risk account list with scores</li>
    <li><span class="method post">POST</span>/churn/launch_intervention — trigger intervention for an account</li>
  </ul>
</div>
</body>
</html>
"""

if _FASTAPI_AVAILABLE:
    app = FastAPI(title=SERVICE_NAME, version="1.0.0")

    @app.get("/health")
    async def health():
        return JSONResponse({"status": "ok", "port": PORT, "service": SERVICE_NAME, "timestamp": datetime.utcnow().isoformat() + "Z"})

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return HTMLResponse(content=DASHBOARD_HTML)

    @app.get("/churn/predictions")
    async def get_predictions():
        return JSONResponse({
            "model_version": "v3.1",
            "auc_roc": 0.91,
            "recall": 0.87,
            "precision": 0.82,
            "roi": "35:1",
            "savings_per_prevented_churn_usd": 83000,
            "at_risk_accounts": _MOCK_AT_RISK,
            "generated_at": datetime.utcnow().isoformat() + "Z",
        })

    @app.post("/churn/launch_intervention")
    async def launch_intervention(payload: dict = Body(default={})):
        account_id = payload.get("account_id", "ACC-UNKNOWN")
        action = payload.get("action", "success_call")
        return JSONResponse({
            "status": "intervention_launched",
            "account_id": account_id,
            "action": action,
            "intervention_id": f"INT-{random.randint(10000, 99999)}",
            "estimated_success_rate": {"success_call": 0.78, "exec_alignment": 0.64, "emergency_retention": 0.41, "win_back": 0.19}.get(action, 0.50),
            "launched_at": datetime.utcnow().isoformat() + "Z",
        })

else:
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
                body = DASHBOARD_HTML.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(body)

        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            _ = self.rfile.read(length)
            body = json.dumps({"status": "intervention_launched", "note": "fastapi not available"}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            pass

if __name__ == "__main__":
    if _FASTAPI_AVAILABLE:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        server = http.server.HTTPServer(("0.0.0.0", PORT), _Handler)
        print(f"Fallback HTTP server on port {PORT}")
        server.serve_forever()
