"""Revenue Forecast Model v2 — bottoms-up + scenario-based ARR forecast with Monte Carlo simulation.

Port: 10003
Cycle: 486B
"""

import json
import math
import random
from datetime import datetime

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    _USE_FASTAPI = True
except ImportError:
    _USE_FASTAPI = False
    from http.server import BaseHTTPRequestHandler, HTTPServer
    from urllib.parse import urlparse, parse_qs

PORT = 10003

# --- Financial constants ---
CURRENT_ARR = 250_000
MRR = round(CURRENT_ARR / 12)
NRR = 118          # net revenue retention %
BURN = 45_000
RUNWAY_MONTHS = 18

_SCENARIOS = {
    "base": {
        "arr_projection": 430_000,
        "ci": [380_000, 480_000],
        "assumptions": {
            "new_logos_per_month": 3,
            "avg_contract_value": 18_000,
            "churn_rate_pct": 8,
            "expansion_rate_pct": 22,
            "cac_payback_months": 14,
        },
    },
    "bull": {
        "arr_projection": 590_000,
        "ci": [530_000, 660_000],
        "assumptions": {
            "new_logos_per_month": 5,
            "avg_contract_value": 22_000,
            "churn_rate_pct": 5,
            "expansion_rate_pct": 35,
            "cac_payback_months": 11,
        },
    },
    "bear": {
        "arr_projection": 310_000,
        "ci": [270_000, 350_000],
        "assumptions": {
            "new_logos_per_month": 1,
            "avg_contract_value": 14_000,
            "churn_rate_pct": 14,
            "expansion_rate_pct": 12,
            "cac_payback_months": 20,
        },
    },
}


def _monte_carlo_ci(base_arr: float, horizon: int, n_sims: int = 1000, seed: int = 42):
    """Simple Monte Carlo: compound monthly with stochastic growth."""
    rng = random.Random(seed)
    results = []
    monthly_growth = (base_arr / CURRENT_ARR) ** (1 / max(horizon, 1)) - 1
    for _ in range(n_sims):
        arr = float(CURRENT_ARR)
        for _ in range(horizon):
            shock = rng.gauss(0, 0.02)
            arr *= 1 + monthly_growth + shock
        results.append(arr)
    results.sort()
    p10 = results[int(0.10 * n_sims)]
    p90 = results[int(0.90 * n_sims)]
    median = results[n_sims // 2]
    return round(median), [round(p10), round(p90)]


HTML_DASHBOARD = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Revenue Forecast Model v2 — OCI Robot Cloud</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; min-height: 100vh; }
    header { background: #1e293b; border-bottom: 2px solid #C74634; padding: 18px 32px; display: flex; align-items: center; gap: 16px; }
    header h1 { font-size: 1.4rem; color: #f8fafc; font-weight: 700; }
    header .badge { background: #C74634; color: #fff; font-size: 0.75rem; padding: 3px 10px; border-radius: 12px; font-weight: 600; }
    .container { max-width: 1100px; margin: 0 auto; padding: 32px 24px; }
    .kpi-row { display: grid; grid-template-columns: repeat(5, 1fr); gap: 16px; margin-bottom: 32px; }
    .kpi { background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 18px; }
    .kpi .label { font-size: 0.74rem; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 8px; }
    .kpi .value { font-size: 1.7rem; font-weight: 700; color: #38bdf8; }
    .kpi .sub { font-size: 0.74rem; color: #64748b; margin-top: 4px; }
    .card { background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 24px; margin-bottom: 24px; }
    .card h2 { font-size: 1rem; color: #38bdf8; font-weight: 600; margin-bottom: 20px; text-transform: uppercase; letter-spacing: 0.06em; }
    svg text { font-family: 'Segoe UI', system-ui, sans-serif; }
    .scenarios { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; margin-bottom: 24px; }
    .scenario-card { background: #0f172a; border: 1px solid #334155; border-radius: 8px; padding: 20px; text-align: center; }
    .scenario-card .name { font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 10px; }
    .scenario-card .arr { font-size: 2rem; font-weight: 700; margin-bottom: 6px; }
    .scenario-card .ci { font-size: 0.76rem; color: #64748b; }
    .bull .name, .bull .arr { color: #4ade80; }
    .base .name, .base .arr { color: #38bdf8; }
    .bear .name, .bear .arr { color: #C74634; }
    .footer { text-align: center; color: #334155; font-size: 0.75rem; padding: 24px 0; }
  </style>
</head>
<body>
  <header>
    <h1>Revenue Forecast Model v2</h1>
    <span class="badge">Cycle 486B</span>
    <span class="badge" style="background:#0ea5e9">Port 10003</span>
    <span class="badge" style="background:#6366f1">Monte Carlo</span>
  </header>
  <div class="container">
    <div class="kpi-row">
      <div class="kpi">
        <div class="label">Current ARR</div>
        <div class="value">$250K</div>
        <div class="sub">as of Q1 2026</div>
      </div>
      <div class="kpi">
        <div class="label">MRR</div>
        <div class="value">$20.8K</div>
        <div class="sub">monthly recurring</div>
      </div>
      <div class="kpi">
        <div class="label">NRR</div>
        <div class="value">118%</div>
        <div class="sub">net revenue retention</div>
      </div>
      <div class="kpi">
        <div class="label">Burn Rate</div>
        <div class="value" style="color:#C74634">$45K</div>
        <div class="sub">per month</div>
      </div>
      <div class="kpi">
        <div class="label">Runway</div>
        <div class="value">18 mo</div>
        <div class="sub">at current burn</div>
      </div>
    </div>

    <div class="scenarios">
      <div class="scenario-card bull">
        <div class="name">Bull Case</div>
        <div class="arr">$590K</div>
        <div class="ci">CI: $530K – $660K</div>
      </div>
      <div class="scenario-card base">
        <div class="name">Base Case</div>
        <div class="arr">$430K</div>
        <div class="ci">CI: $380K – $480K</div>
      </div>
      <div class="scenario-card bear">
        <div class="name">Bear Case</div>
        <div class="arr">$310K</div>
        <div class="ci">CI: $270K – $350K</div>
      </div>
    </div>

    <div class="card">
      <h2>ARR by Q4 2026 — Scenario Comparison</h2>
      <svg width="100%" viewBox="0 0 680 280" xmlns="http://www.w3.org/2000/svg">
        <!-- Axes -->
        <line x1="70" y1="20" x2="70" y2="220" stroke="#334155" stroke-width="1"/>
        <line x1="70" y1="220" x2="630" y2="220" stroke="#334155" stroke-width="1"/>
        <!-- Y gridlines: 0, 150K, 300K, 450K, 600K -->
        <!-- max=600K, height=200, scale=200/600000 -->
        <!-- 600K → y=20; 450K → y=70; 300K → y=120; 150K → y=170; 0 → y=220 -->
        <line x1="70" y1="20"  x2="630" y2="20"  stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,4"/>
        <line x1="70" y1="70"  x2="630" y2="70"  stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,4"/>
        <line x1="70" y1="120" x2="630" y2="120" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,4"/>
        <line x1="70" y1="170" x2="630" y2="170" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,4"/>
        <text x="60" y="24"  text-anchor="end" fill="#64748b" font-size="11">$600K</text>
        <text x="60" y="74"  text-anchor="end" fill="#64748b" font-size="11">$450K</text>
        <text x="60" y="124" text-anchor="end" fill="#64748b" font-size="11">$300K</text>
        <text x="60" y="174" text-anchor="end" fill="#64748b" font-size="11">$150K</text>
        <text x="60" y="224" text-anchor="end" fill="#64748b" font-size="11">$0</text>
        <!-- Bull: $590K => y=220-(590/600)*200=220-196.7=23.3 height=196.7 -->
        <rect x="130" y="23" width="120" height="197" fill="#4ade80" rx="4" opacity="0.85"/>
        <text x="190" y="17" text-anchor="middle" fill="#4ade80" font-size="13" font-weight="700">$590K</text>
        <text x="190" y="242" text-anchor="middle" fill="#94a3b8" font-size="12">Bull Case</text>
        <!-- CI bar: 530K-660K (cap at 600K) => y_top=20+(600-590)/600*200=23, y_bot=220-(530/600)*200=43.3 -->
        <line x1="190" y1="20" x2="190" y2="44" stroke="#4ade80" stroke-width="2" stroke-dasharray="3,2"/>
        <!-- Base: $430K => y=220-(430/600)*200=220-143.3=76.7 height=143.3 -->
        <rect x="290" y="77" width="120" height="143" fill="#38bdf8" rx="4" opacity="0.85"/>
        <text x="350" y="71" text-anchor="middle" fill="#38bdf8" font-size="13" font-weight="700">$430K</text>
        <text x="350" y="242" text-anchor="middle" fill="#94a3b8" font-size="12">Base Case</text>
        <!-- CI: 380-480 => y_top=220-(480/600)*200=60; y_bot=220-(380/600)*200=93.3 -->
        <line x1="350" y1="60" x2="350" y2="93" stroke="#38bdf8" stroke-width="2" stroke-dasharray="3,2"/>
        <!-- Bear: $310K => y=220-(310/600)*200=220-103.3=116.7 height=103.3 -->
        <rect x="450" y="117" width="120" height="103" fill="#C74634" rx="4" opacity="0.85"/>
        <text x="510" y="111" text-anchor="middle" fill="#C74634" font-size="13" font-weight="700">$310K</text>
        <text x="510" y="242" text-anchor="middle" fill="#94a3b8" font-size="12">Bear Case</text>
        <!-- CI: 270-350 => y_top=220-(350/600)*200=103.3; y_bot=220-(270/600)*200=130 -->
        <line x1="510" y1="103" x2="510" y2="130" stroke="#C74634" stroke-width="2" stroke-dasharray="3,2"/>
        <!-- Current ARR marker: $250K => y=220-(250/600)*200=136.7 -->
        <line x1="70" y1="137" x2="630" y2="137" stroke="#fbbf24" stroke-width="1.5" stroke-dasharray="6,3"/>
        <text x="635" y="141" fill="#fbbf24" font-size="10">Current $250K</text>
        <!-- Legend -->
        <text x="350" y="270" text-anchor="middle" fill="#64748b" font-size="11">Q4 2026 ARR Projection (Monte Carlo 80% CI)</text>
      </svg>
    </div>

    <div class="card">
      <h2>Monthly ARR Growth Trajectory (Base Case)</h2>
      <svg width="100%" viewBox="0 0 680 200" xmlns="http://www.w3.org/2000/svg">
        <line x1="50" y1="10" x2="50" y2="165" stroke="#334155" stroke-width="1"/>
        <line x1="50" y1="165" x2="650" y2="165" stroke="#334155" stroke-width="1"/>
        <!-- 9 months Q2-Q4 2026; ARR grows from 250K to 430K linearly with noise -->
        <!-- x: 50 + i*(600/8) for i=0..8; y: 165 - arr/430*155 -->
        <!-- arr months: 250,272,295,318,342,366,390,410,430 -->
        <!-- y vals: 165-250/430*155=165-90.1=74.9; ...165-155=10 -->
        <polyline points="
          50,75
          125,65
          200,56
          275,47
          350,38
          425,30
          500,21
          575,15
          650,10
        " fill="none" stroke="#38bdf8" stroke-width="2.5" stroke-linejoin="round"/>
        <!-- Bull envelope -->
        <polyline points="
          50,75
          125,61
          200,48
          275,36
          350,25
          425,15
          500,8
          575,5
          650,3
        " fill="none" stroke="#4ade80" stroke-width="1.5" stroke-dasharray="5,3"/>
        <!-- Bear envelope -->
        <polyline points="
          50,75
          125,70
          200,65
          275,60
          350,54
          425,48
          500,43
          575,38
          650,34
        " fill="none" stroke="#C74634" stroke-width="1.5" stroke-dasharray="5,3"/>
        <!-- Dots on base line -->
        <circle cx="50"  cy="75" r="3" fill="#38bdf8"/>
        <circle cx="650" cy="10" r="4" fill="#38bdf8"/>
        <!-- X labels -->
        <text x="50"  y="180" text-anchor="middle" fill="#64748b" font-size="10">Apr</text>
        <text x="200" y="180" text-anchor="middle" fill="#64748b" font-size="10">Jun</text>
        <text x="350" y="180" text-anchor="middle" fill="#64748b" font-size="10">Aug</text>
        <text x="500" y="180" text-anchor="middle" fill="#64748b" font-size="10">Oct</text>
        <text x="650" y="180" text-anchor="middle" fill="#64748b" font-size="10">Dec</text>
        <!-- Legend -->
        <rect x="420" y="130" width="12" height="4" fill="#38bdf8" rx="1"/>
        <text x="436" y="136" fill="#94a3b8" font-size="10">Base</text>
        <rect x="470" y="130" width="12" height="4" fill="#4ade80" rx="1"/>
        <text x="486" y="136" fill="#94a3b8" font-size="10">Bull</text>
        <rect x="520" y="130" width="12" height="4" fill="#C74634" rx="1"/>
        <text x="536" y="136" fill="#94a3b8" font-size="10">Bear</text>
      </svg>
    </div>
  </div>
  <div class="footer">OCI Robot Cloud &mdash; Revenue Forecast Model v2 &mdash; Port 10003</div>
</body>
</html>
"""


if _USE_FASTAPI:
    app = FastAPI(
        title="Revenue Forecast Model v2",
        description="Bottoms-up + scenario-based ARR forecast with Monte Carlo simulation",
        version="2.0.0",
    )

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return HTML_DASHBOARD

    @app.get("/health")
    def health():
        return {
            "status": "ok",
            "service": "revenue_forecast_model_v2",
            "port": PORT,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

    @app.get("/finance/forecast")
    def forecast(scenario: str = "base", horizon_months: int = 9):
        if scenario not in _SCENARIOS:
            from fastapi import HTTPException
            raise HTTPException(status_code=422, detail=f"scenario must be one of: {list(_SCENARIOS)}")
        sc = _SCENARIOS[scenario]
        median, ci = _monte_carlo_ci(sc["arr_projection"], max(horizon_months, 1))
        return {
            "scenario": scenario,
            "horizon_months": horizon_months,
            "arr_projection": sc["arr_projection"],
            "monte_carlo_median": median,
            "confidence_interval": ci,
            "key_assumptions": sc["assumptions"],
        }

    @app.get("/finance/current")
    def current_financials():
        return {
            "current_arr": CURRENT_ARR,
            "mrr": MRR,
            "nrr": NRR,
            "burn": BURN,
            "runway_months": RUNWAY_MONTHS,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

else:
    class _Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass

        def _send(self, code, content_type, body):
            encoded = body.encode() if isinstance(body, str) else body
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def do_GET(self):
            parsed = urlparse(self.path)
            path = parsed.path
            qs = parse_qs(parsed.query)
            if path == "/":
                self._send(200, "text/html", HTML_DASHBOARD)
            elif path == "/health":
                self._send(200, "application/json", json.dumps({"status": "ok", "port": PORT}))
            elif path == "/finance/current":
                self._send(200, "application/json", json.dumps({
                    "current_arr": CURRENT_ARR, "mrr": MRR, "nrr": NRR,
                    "burn": BURN, "runway_months": RUNWAY_MONTHS,
                }))
            elif path == "/finance/forecast":
                scenario = qs.get("scenario", ["base"])[0]
                horizon = int(qs.get("horizon_months", ["9"])[0])
                if scenario not in _SCENARIOS:
                    self._send(422, "application/json", json.dumps({"detail": "invalid scenario"}))
                    return
                sc = _SCENARIOS[scenario]
                median, ci = _monte_carlo_ci(sc["arr_projection"], max(horizon, 1))
                result = {
                    "scenario": scenario,
                    "horizon_months": horizon,
                    "arr_projection": sc["arr_projection"],
                    "monte_carlo_median": median,
                    "confidence_interval": ci,
                    "key_assumptions": sc["assumptions"],
                }
                self._send(200, "application/json", json.dumps(result))
            else:
                self._send(404, "application/json", json.dumps({"detail": "not found"}))


if __name__ == "__main__":
    if _USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        print(f"FastAPI not available — starting stdlib HTTPServer on port {PORT}")
        server = HTTPServer(("0.0.0.0", PORT), _Handler)
        server.serve_forever()
