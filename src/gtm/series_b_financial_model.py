"""series_b_financial_model.py — Series B $20M raise financial model.

Targeting Q4 2027 close. Models base / bull / bear scenarios.
Port: 10055
"""

from __future__ import annotations

import json
from typing import Any, Dict

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    from pydantic import BaseModel
    import uvicorn
    _FASTAPI = True
except ImportError:
    _FASTAPI = False
    from http.server import BaseHTTPRequestHandler, HTTPServer
    from urllib.parse import urlparse, parse_qs

PORT = 10055

# ---------------------------------------------------------------------------
# Financial model constants
# ---------------------------------------------------------------------------

SCENARIOS: Dict[str, Dict[str, Any]] = {
    "base": {
        "arr_at_raise": 2_100_000.0,
        "valuation": 80_000_000.0,
        "runway_months": 24,
        "use_of_funds": {
            "engineering_8_hires": 5_600_000,
            "infrastructure_oci": 4_000_000,
            "gtm_sales_marketing": 6_000_000,
            "g_and_a": 2_400_000,
            "reserve": 2_000_000,
        },
    },
    "bull": {
        "arr_at_raise": 3_500_000.0,
        "valuation": 120_000_000.0,
        "runway_months": 30,
        "use_of_funds": {
            "engineering_8_hires": 5_600_000,
            "infrastructure_oci": 5_000_000,
            "gtm_sales_marketing": 7_000_000,
            "g_and_a": 2_400_000,
            "reserve": 0,
        },
    },
    "bear": {
        "arr_at_raise": 1_200_000.0,
        "valuation": 56_000_000.0,
        "runway_months": 18,
        "use_of_funds": {
            "engineering_8_hires": 5_600_000,
            "infrastructure_oci": 3_000_000,
            "gtm_sales_marketing": 4_500_000,
            "g_and_a": 2_400_000,
            "reserve": 4_500_000,
        },
    },
}

MILESTONES = [
    {
        "event": "AI World Demo (Boston)",
        "target_date": "Q1 2027",
        "metric": "Live demo to 500+ robotics practitioners",
        "arr_target": 0,
        "status": "planned",
    },
    {
        "event": "10 Design-Partner Customers",
        "target_date": "Q2 2027",
        "metric": "10 paying design partners @ avg $15k ARR",
        "arr_target": 150_000,
        "status": "planned",
    },
    {
        "event": "Series A Close",
        "target_date": "Q3 2027",
        "metric": "$5M Series A, $20M post-money",
        "arr_target": 800_000,
        "status": "planned",
    },
    {
        "event": "Series B Close",
        "target_date": "Q4 2027",
        "metric": "$20M Series B, $80M post-money",
        "arr_target": 2_100_000,
        "status": "target",
    },
]

# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

DASHBOARD_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Series B Financial Model — OCI Robot Cloud</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: #0f172a;
      color: #e2e8f0;
      font-family: 'Segoe UI', system-ui, sans-serif;
      min-height: 100vh;
      padding: 2rem;
    }
    h1 { color: #C74634; font-size: 1.8rem; margin-bottom: 0.25rem; }
    .subtitle { color: #38bdf8; font-size: 1rem; margin-bottom: 2rem; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1.25rem; margin-bottom: 2rem; }
    .card {
      background: #1e293b;
      border: 1px solid #334155;
      border-radius: 10px;
      padding: 1.25rem 1.5rem;
    }
    .card .label { font-size: 0.75rem; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.4rem; }
    .card .value { font-size: 2rem; font-weight: 700; }
    .val-red   { color: #C74634; }
    .val-blue  { color: #38bdf8; }
    .val-green { color: #4ade80; }
    .val-amber { color: #fbbf24; }
    .section-title { color: #38bdf8; font-size: 1.1rem; margin: 1.5rem 0 0.75rem; }
    .ms-table { width: 100%; border-collapse: collapse; margin-bottom: 1.5rem; }
    .ms-table th, .ms-table td {
      border: 1px solid #334155;
      padding: 0.55rem 0.9rem;
      font-size: 0.88rem;
      text-align: left;
    }
    .ms-table th { background: #1e293b; color: #38bdf8; font-weight: 600; }
    .ms-table td { background: #0f172a; }
    .badge {
      display: inline-block; padding: 0.15rem 0.55rem;
      border-radius: 4px; font-size: 0.75rem; font-weight: 700;
    }
    .badge-planned { background: #1e40af; color: #bfdbfe; }
    .badge-target  { background: #C74634; color: #fff; }
    .chart-wrap { background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 1.25rem 1.5rem; margin-bottom: 2rem; }
    .footer { color: #475569; font-size: 0.8rem; margin-top: 2rem; }
  </style>
</head>
<body>
  <h1>Series B Financial Model — OCI Robot Cloud</h1>
  <p class="subtitle">$20M raise &nbsp;|&nbsp; Q4 2027 target close &nbsp;|&nbsp; Port 10055</p>

  <div class="grid">
    <div class="card">
      <div class="label">Raise Amount</div>
      <div class="value val-red">$20M</div>
    </div>
    <div class="card">
      <div class="label">Post-Money Valuation</div>
      <div class="value val-blue">$80M</div>
    </div>
    <div class="card">
      <div class="label">ARR at Raise (Base)</div>
      <div class="value val-green">$2.1M</div>
    </div>
    <div class="card">
      <div class="label">Runway</div>
      <div class="value val-amber">24 mo</div>
    </div>
    <div class="card">
      <div class="label">Target Close</div>
      <div class="value val-red">Q4 2027</div>
    </div>
  </div>

  <!-- Use of Funds bar chart -->
  <div class="chart-wrap">
    <p class="section-title" style="margin-top:0">Use of Funds — Base Scenario ($20M)</p>
    <svg viewBox="0 0 560 220" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:560px;display:block;margin:0 auto">
      <!-- axes -->
      <line x1="150" y1="10" x2="150" y2="180" stroke="#475569" stroke-width="1"/>
      <line x1="150" y1="180" x2="550" y2="180" stroke="#475569" stroke-width="1"/>
      <!-- x labels -->
      <text x="150" y="195" fill="#94a3b8" font-size="9" text-anchor="middle">$0</text>
      <text x="250" y="195" fill="#94a3b8" font-size="9" text-anchor="middle">$2.5M</text>
      <text x="350" y="195" fill="#94a3b8" font-size="9" text-anchor="middle">$5M</text>
      <text x="450" y="195" fill="#94a3b8" font-size="9" text-anchor="middle">$7.5M</text>
      <text x="550" y="195" fill="#94a3b8" font-size="9" text-anchor="middle">$10M</text>
      <!-- Engineering: $5.6M = 224px -->
      <rect x="150" y="20"  width="224" height="26" fill="#C74634" rx="3"/>
      <text x="145" y="38"  fill="#94a3b8" font-size="10" text-anchor="end">Engineering (8 hires)</text>
      <text x="382" y="38"  fill="#fff" font-size="10" dx="4">$5.6M</text>
      <!-- Infrastructure: $4M = 160px -->
      <rect x="150" y="54"  width="160" height="26" fill="#38bdf8" rx="3"/>
      <text x="145" y="72"  fill="#94a3b8" font-size="10" text-anchor="end">Infrastructure (OCI)</text>
      <text x="318" y="72"  fill="#0f172a" font-size="10" dx="4">$4.0M</text>
      <!-- GTM: $6M = 240px -->
      <rect x="150" y="88"  width="240" height="26" fill="#4ade80" rx="3"/>
      <text x="145" y="106" fill="#94a3b8" font-size="10" text-anchor="end">GTM (Sales &amp; Mktg)</text>
      <text x="398" y="106" fill="#0f172a" font-size="10" dx="4">$6.0M</text>
      <!-- G&A: $2.4M = 96px -->
      <rect x="150" y="122" width="96"  height="26" fill="#fbbf24" rx="3"/>
      <text x="145" y="140" fill="#94a3b8" font-size="10" text-anchor="end">G&amp;A</text>
      <text x="254" y="140" fill="#0f172a" font-size="10" dx="4">$2.4M</text>
      <!-- Reserve: $2M = 80px -->
      <rect x="150" y="156" width="80"  height="26" fill="#818cf8" rx="3"/>
      <text x="145" y="174" fill="#94a3b8" font-size="10" text-anchor="end">Reserve</text>
      <text x="238" y="174" fill="#fff" font-size="10" dx="4">$2.0M</text>
    </svg>
  </div>

  <p class="section-title">Milestone Ladder</p>
  <table class="ms-table">
    <thead>
      <tr><th>Event</th><th>Target Date</th><th>Metric</th><th>ARR Target</th><th>Status</th></tr>
    </thead>
    <tbody>
      <tr>
        <td>AI World Demo (Boston)</td>
        <td>Q1 2027</td>
        <td>Live demo to 500+ practitioners</td>
        <td>—</td>
        <td><span class="badge badge-planned">planned</span></td>
      </tr>
      <tr>
        <td>10 Design-Partner Customers</td>
        <td>Q2 2027</td>
        <td>10 paying @ avg $15k ARR</td>
        <td>$150K</td>
        <td><span class="badge badge-planned">planned</span></td>
      </tr>
      <tr>
        <td>Series A Close</td>
        <td>Q3 2027</td>
        <td>$5M raise, $20M post-money</td>
        <td>$800K</td>
        <td><span class="badge badge-planned">planned</span></td>
      </tr>
      <tr>
        <td>Series B Close</td>
        <td>Q4 2027</td>
        <td>$20M raise, $80M post-money</td>
        <td>$2.1M</td>
        <td><span class="badge badge-target">TARGET</span></td>
      </tr>
    </tbody>
  </table>

  <p class="section-title">Scenario Comparison</p>
  <table class="ms-table">
    <thead>
      <tr><th>Scenario</th><th>ARR at Raise</th><th>Post-Money Val</th><th>Runway</th></tr>
    </thead>
    <tbody>
      <tr><td>Base</td><td>$2.1M</td><td>$80M</td><td>24 mo</td></tr>
      <tr><td>Bull</td><td>$3.5M</td><td>$120M</td><td>30 mo</td></tr>
      <tr><td>Bear</td><td>$1.2M</td><td>$56M</td><td>18 mo</td></tr>
    </tbody>
  </table>

  <p class="footer">OCI Robot Cloud &mdash; Series B Financial Model &mdash; Port 10055</p>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

if _FASTAPI:
    app = FastAPI(
        title="Series B Financial Model",
        description="OCI Robot Cloud Series B $20M raise model — Q4 2027 target close.",
        version="1.0.0",
    )

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return DASHBOARD_HTML

    @app.get("/health")
    async def health():
        return JSONResponse({"status": "ok", "service": "series_b_financial_model", "port": PORT})

    @app.get("/finance/series_b_model")
    async def series_b_model(scenario: str = "base"):
        if scenario not in SCENARIOS:
            from fastapi import HTTPException
            raise HTTPException(status_code=422, detail=f"scenario must be one of: {list(SCENARIOS.keys())}")
        return JSONResponse(SCENARIOS[scenario])

    @app.get("/finance/series_b_milestones")
    async def series_b_milestones():
        return JSONResponse({"milestones": MILESTONES})

# ---------------------------------------------------------------------------
# stdlib HTTPServer fallback
# ---------------------------------------------------------------------------

else:
    class _Handler(BaseHTTPRequestHandler):
        def _send(self, code: int, ctype: str, body: str):
            data = body.encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            parsed = urlparse(self.path)
            qs = parse_qs(parsed.query)
            if parsed.path == "/":
                self._send(200, "text/html", DASHBOARD_HTML)
            elif parsed.path == "/health":
                self._send(200, "application/json",
                           json.dumps({"status": "ok", "service": "series_b_financial_model", "port": PORT}))
            elif parsed.path == "/finance/series_b_model":
                scenario = (qs.get("scenario") or ["base"])[0]
                if scenario not in SCENARIOS:
                    self._send(422, "application/json",
                               json.dumps({"detail": f"scenario must be one of: {list(SCENARIOS.keys())}"}))
                else:
                    self._send(200, "application/json", json.dumps(SCENARIOS[scenario]))
            elif parsed.path == "/finance/series_b_milestones":
                self._send(200, "application/json", json.dumps({"milestones": MILESTONES}))
            else:
                self._send(404, "application/json", json.dumps({"detail": "not found"}))

        def log_message(self, fmt, *args):
            pass


if __name__ == "__main__":
    if _FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        print(f"FastAPI not found — starting stdlib HTTPServer on port {PORT}")
        server = HTTPServer(("0.0.0.0", PORT), _Handler)
        server.serve_forever()
