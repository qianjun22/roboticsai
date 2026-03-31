"""Pricing Experiment Framework — A/B testing for pricing strategies (port 10227)."""

import json
import sys
from datetime import datetime

PORT = 10227
SERVICE_NAME = "pricing_experiment_framework"

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    from pydantic import BaseModel
    import uvicorn
    _FASTAPI_AVAILABLE = True
except ImportError:
    _FASTAPI_AVAILABLE = False

HTML_DASHBOARD = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Pricing Experiment Framework</title>
  <style>
    body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; margin: 0; padding: 24px; }
    h1 { color: #C74634; font-size: 1.8rem; margin-bottom: 4px; }
    h2 { color: #38bdf8; font-size: 1.1rem; font-weight: 400; margin-top: 0; }
    .card { background: #1e293b; border-radius: 10px; padding: 20px; margin: 16px 0; }
    .metric { display: inline-block; margin: 8px 16px 8px 0; }
    .metric .val { font-size: 2rem; font-weight: 700; color: #38bdf8; }
    .metric .lbl { font-size: 0.8rem; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.05em; }
    table { width: 100%; border-collapse: collapse; margin-top: 8px; }
    th { text-align: left; color: #94a3b8; font-size: 0.75rem; text-transform: uppercase; padding: 6px 8px; border-bottom: 1px solid #334155; }
    td { padding: 8px; border-bottom: 1px solid #1e293b; font-size: 0.9rem; }
    tr:hover td { background: #0f172a; }
    .badge { display: inline-block; padding: 2px 10px; border-radius: 999px; font-size: 0.75rem; font-weight: 600; }
    .badge-green  { background: #14532d; color: #4ade80; }
    .badge-blue   { background: #0c4a6e; color: #38bdf8; }
    .badge-orange { background: #431407; color: #fb923c; }
    .badge-post   { background: #3b0764; color: #c084fc; }
    .endpoint { color: #38bdf8; font-family: monospace; font-size: 0.85rem; }
    .pos { color: #4ade80; } .neg { color: #f87171; }
  </style>
</head>
<body>
  <h1>Pricing Experiment Framework</h1>
  <h2>A/B testing pricing strategies — conversion + ACV impact measurement</h2>

  <div class="card">
    <div class="metric"><div class="val">4</div><div class="lbl">Live Experiments</div></div>
    <div class="metric"><div class="val">2wk</div><div class="lbl">Min Duration / Arm</div></div>
    <div class="metric"><div class="val">10</div><div class="lbl">Deals / Arm</div></div>
    <div class="metric"><div class="val">Monthly</div><div class="lbl">Review Cadence</div></div>
  </div>

  <div class="card">
    <h3 style="color:#C74634;margin-top:0">Experiment Results (Conversion / ACV Delta)</h3>
    <svg viewBox="0 0 500 180" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:560px">
      <!-- axes -->
      <line x1="70" y1="10" x2="70" y2="140" stroke="#334155" stroke-width="1"/>
      <line x1="70" y1="140" x2="480" y2="140" stroke="#334155" stroke-width="1"/>
      <!-- grid -->
      <line x1="70" y1="35"  x2="480" y2="35"  stroke="#1e293b" stroke-width="1" stroke-dasharray="4"/>
      <line x1="70" y1="87"  x2="480" y2="87"  stroke="#1e293b" stroke-width="1" stroke-dasharray="4"/>
      <line x1="70" y1="140" x2="480" y2="140" stroke="#334155" stroke-width="1"/>
      <!-- y labels -->
      <text x="62" y="144" fill="#94a3b8" font-size="10" text-anchor="end">0%</text>
      <text x="62" y="91"  fill="#94a3b8" font-size="10" text-anchor="end">5%</text>
      <text x="62" y="39"  fill="#94a3b8" font-size="10" text-anchor="end">10%</text>
      <!-- bar: Annual billing +12% ACV -->
      <rect x="90"  y="14"  width="80" height="126" fill="#38bdf8" rx="3"/>
      <text x="130" y="10"  fill="#e2e8f0" font-size="11" text-anchor="middle">+12% ACV</text>
      <text x="130" y="158" fill="#94a3b8" font-size="9"  text-anchor="middle">Annual Billing</text>
      <!-- bar: 15% discount +8% conversion -->
      <rect x="210" y="56"  width="80" height="84"  fill="#4ade80" rx="3"/>
      <text x="250" y="52"  fill="#e2e8f0" font-size="11" text-anchor="middle">+8% Conv.</text>
      <text x="250" y="158" fill="#94a3b8" font-size="9"  text-anchor="middle">15% Discount</text>
      <!-- bar: per-robot -5% conversion (negative — draw upward from baseline, color red) -->
      <rect x="330" y="140" width="80" height="52"  fill="#f87171" rx="3"/>
      <text x="370" y="138" fill="#e2e8f0" font-size="11" text-anchor="middle">-5% Conv.</text>
      <text x="370" y="158" fill="#94a3b8" font-size="9"  text-anchor="middle">Per-Robot</text>
    </svg>
    <p style="font-size:0.75rem;color:#64748b;margin:4px 0 0">* Negative bar (Per-Robot) extends below baseline.</p>
  </div>

  <div class="card">
    <h3 style="color:#C74634;margin-top:0">Live Experiments</h3>
    <table>
      <tr><th>Experiment</th><th>Hypothesis</th><th>Status</th><th>Signal</th></tr>
      <tr>
        <td>Annual Billing</td>
        <td>Annual commit → +12% ACV</td>
        <td><span class="badge badge-green">live</span></td>
        <td class="pos">+12% ACV</td>
      </tr>
      <tr>
        <td>15% Discount</td>
        <td>Discount at proposal → +8% conversion</td>
        <td><span class="badge badge-green">live</span></td>
        <td class="pos">+8% Conv.</td>
      </tr>
      <tr>
        <td>Per-Robot Pricing</td>
        <td>Per-unit pricing vs flat — clarity tradeoff</td>
        <td><span class="badge badge-green">live</span></td>
        <td class="neg">-5% Conv.</td>
      </tr>
      <tr>
        <td>Freemium Tier</td>
        <td>Free 1-robot tier drives enterprise pipeline</td>
        <td><span class="badge badge-orange">pending</span></td>
        <td>—</td>
      </tr>
    </table>
  </div>

  <div class="card">
    <h3 style="color:#C74634;margin-top:0">API Endpoints</h3>
    <p><span class="badge badge-blue">GET</span>  <span class="endpoint">/health</span> — service health</p>
    <p><span class="badge badge-blue">GET</span>  <span class="endpoint">/pricing/experiments</span> — list all experiments</p>
    <p><span class="badge badge-post">POST</span> <span class="endpoint">/pricing/experiments/launch</span> — launch new experiment</p>
  </div>
</body>
</html>
"""

if _FASTAPI_AVAILABLE:
    app = FastAPI(title=SERVICE_NAME, version="1.0.0")

    class ExperimentLaunchRequest(BaseModel):
        name: str
        hypothesis: str
        min_duration_weeks: int = 2
        deals_per_arm: int = 10

    @app.get("/health")
    def health():
        return JSONResponse({"status": "ok", "port": PORT, "service": SERVICE_NAME, "ts": datetime.utcnow().isoformat()})

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return HTML_DASHBOARD

    @app.get("/pricing/experiments")
    def list_experiments():
        return JSONResponse({
            "total": 4,
            "min_duration_weeks": 2,
            "deals_per_arm": 10,
            "review_cadence": "monthly",
            "experiments": [
                {"id": "exp-001", "name": "Annual Billing",   "status": "live",    "signal_acv_delta": 0.12,  "signal_conv_delta": None},
                {"id": "exp-002", "name": "15% Discount",    "status": "live",    "signal_acv_delta": None,  "signal_conv_delta": 0.08},
                {"id": "exp-003", "name": "Per-Robot Pricing", "status": "live",  "signal_acv_delta": None,  "signal_conv_delta": -0.05},
                {"id": "exp-004", "name": "Freemium Tier",   "status": "pending", "signal_acv_delta": None,  "signal_conv_delta": None}
            ]
        })

    @app.post("/pricing/experiments/launch")
    def launch_experiment(req: ExperimentLaunchRequest):
        import uuid
        exp_id = "exp-" + str(uuid.uuid4())[:8]
        return JSONResponse({
            "id": exp_id,
            "name": req.name,
            "hypothesis": req.hypothesis,
            "min_duration_weeks": req.min_duration_weeks,
            "deals_per_arm": req.deals_per_arm,
            "status": "launched",
            "created_at": datetime.utcnow().isoformat()
        }, status_code=201)

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
                body = HTML_DASHBOARD.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(body)

        def log_message(self, fmt, *args):
            pass

    def _serve():
        server = http.server.HTTPServer(("0.0.0.0", PORT), _Handler)
        print(f"[{SERVICE_NAME}] Fallback HTTP server on port {PORT}")
        server.serve_forever()

if __name__ == "__main__":
    if _FASTAPI_AVAILABLE:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        _serve()
