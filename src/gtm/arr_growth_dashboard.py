"""arr_growth_dashboard.py — port 10061
Comprehensive ARR growth tracking: waterfall, cohort, forecast, and NRR.
"""

import json
from datetime import datetime

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    _FASTAPI = True
except ImportError:
    _FASTAPI = False
    from http.server import BaseHTTPRequestHandler, HTTPServer
    from urllib.parse import urlparse, parse_qs

# ---------------------------------------------------------------------------
# ARR data model
# ---------------------------------------------------------------------------

_ARR_DATA = {
    "arr_by_source": {
        "new_logos": 83000,
        "expansion": 78000,
        "reactivations": 12000,
        "churn": -18000,
        "contraction": -5000,
    },
    "waterfall": {
        "opening_arr": 100000,
        "new_logos": 83000,
        "expansion": 78000,
        "reactivations": 12000,
        "churn": -18000,
        "contraction": -5000,
        "closing_arr": 250000,
    },
    "cohorts": {
        "Q1_2026": {"initial_arr": 83000, "current_arr": 97940, "nrr_pct": 118},
        "Q2_2026": {"initial_arr": 167000, "current_arr": 167000, "nrr_pct": 100},
    },
    "cohort_expansion": 1.18,
    "growth_rate_pct": 12.0,
    "forecast": {
        "Q3_2026": 330000,
        "Q4_2026": 430000,
        "method": "linear_regression_mom_12pct",
    },
    "nrr_pct": 118,
    "mom_growth_pct": 12,
}


def _arr_dashboard_for_period(period: str) -> dict:
    """Return ARR dashboard data, optionally filtered by period."""
    data = dict(_ARR_DATA)
    data["period"] = period or "YTD"
    data["generated_at"] = datetime.utcnow().isoformat() + "Z"
    return data


def _arr_drivers() -> dict:
    w = _ARR_DATA["waterfall"]
    new_logos = w["new_logos"]
    expansion = w["expansion"]
    reactivations = w["reactivations"]
    churn = w["churn"]
    contraction = w["contraction"]
    net_new_arr = new_logos + expansion + reactivations + churn + contraction
    return {
        "expansion": expansion,
        "new_logos": new_logos,
        "reactivations": reactivations,
        "churn": churn,
        "contraction": contraction,
        "net_new_arr": net_new_arr,
        "opening_arr": w["opening_arr"],
        "closing_arr": w["closing_arr"],
        "nrr_pct": _ARR_DATA["nrr_pct"],
        "mom_growth_pct": _ARR_DATA["mom_growth_pct"],
    }


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>ARR Growth Dashboard — OCI Robot Cloud</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; padding: 2rem; }
    h1 { color: #C74634; font-size: 1.8rem; margin-bottom: .25rem; }
    .subtitle { color: #94a3b8; font-size: .9rem; margin-bottom: 2rem; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 1.25rem; margin-bottom: 2rem; }
    .card { background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 1.25rem; }
    .card h3 { color: #94a3b8; font-size: .75rem; text-transform: uppercase; letter-spacing: .08em; margin-bottom: .5rem; }
    .card .val { font-size: 1.9rem; font-weight: 700; color: #38bdf8; }
    .card .unit { font-size: .8rem; color: #64748b; margin-top: .2rem; }
    .red { color: #C74634 !important; }
    .green { color: #34d399 !important; }
    .section { background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 1.5rem; margin-bottom: 1.5rem; }
    .section h2 { color: #38bdf8; font-size: 1.1rem; margin-bottom: 1rem; }
    .badge { display: inline-block; padding: .2rem .7rem; border-radius: 999px; font-size: .75rem; font-weight: 600; }
    .badge-green { background: #064e3b; color: #34d399; }
    .badge-blue { background: #0c4a6e; color: #38bdf8; }
    .badge-red { background: #450a0a; color: #fca5a5; }
    table { width: 100%; border-collapse: collapse; font-size: .875rem; }
    th { color: #94a3b8; text-align: left; padding: .5rem .75rem; border-bottom: 1px solid #334155; }
    td { padding: .6rem .75rem; border-bottom: 1px solid #1e293b; }
    tr:hover td { background: #0f172a; }
    footer { color: #475569; font-size: .75rem; text-align: center; margin-top: 2rem; }
    .two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; }
    @media(max-width:700px){ .two-col { grid-template-columns: 1fr; } }
  </style>
</head>
<body>
  <h1>ARR Growth Dashboard</h1>
  <div class="subtitle">Port 10061 &nbsp;|&nbsp; OCI Robot Cloud &nbsp;|&nbsp; YTD 2026 &nbsp;|&nbsp; Target $430K Q4 2026</div>

  <div class="grid">
    <div class="card">
      <h3>Closing ARR</h3>
      <div class="val green">$250K</div>
      <div class="unit">from $100K opening</div>
    </div>
    <div class="card">
      <h3>Net New ARR</h3>
      <div class="val">$150K</div>
      <div class="unit">this period</div>
    </div>
    <div class="card">
      <h3>NRR</h3>
      <div class="val green">118%</div>
      <div class="unit">net revenue retention</div>
    </div>
    <div class="card">
      <h3>MoM Growth</h3>
      <div class="val">12%</div>
      <div class="unit">month-over-month</div>
    </div>
    <div class="card">
      <h3>Q4 2026 Forecast</h3>
      <div class="val">$430K</div>
      <div class="unit">linear extrapolation</div>
    </div>
    <div class="card">
      <h3>Churn</h3>
      <div class="val red">-$18K</div>
      <div class="unit">gross churn this period</div>
    </div>
  </div>

  <!-- ARR Waterfall SVG -->
  <div class="section">
    <h2>ARR Waterfall — Opening to $250K Closing</h2>
    <!--
      Scale: max displayed bar segment $250K → height 160px → 1px = $1,562.5
      Bars (all relative to baseline y=175):
        Opening $100K  → h=64   , y=111   , color #38bdf8  (start)
        New Logos +$83K→ h=53.1 , y=57.9  , color #34d399  (addition)
        Expansion +$78K→ h=49.9 , y=8     , color #34d399  (addition)
        Reactiv +$12K → h=7.7  , y=0.3   (capped), color #34d399
        Churn   -$18K → h=11.5 , color #C74634 (reduction)
        Contract -$5K → h=3.2  , color #C74634
        Closing $250K → h=160  , y=15    , color #38bdf8  (result)
      Simplified waterfall: show each as a standalone bar for clarity.
    -->
    <svg viewBox="0 0 640 240" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:640px;display:block;">
      <!-- Axes -->
      <line x1="50" y1="10" x2="50" y2="185" stroke="#334155" stroke-width="1.5"/>
      <line x1="50" y1="185" x2="620" y2="185" stroke="#334155" stroke-width="1.5"/>
      <!-- Y gridlines & labels (0, 50K, 100K, 150K, 200K, 250K) -->
      <!-- 250K = y10, 0 = y185, scale = 175/250000 = 0.0007 px per $ -->
      <line x1="50" y1="185" x2="620" y2="185" stroke="#334155" stroke-dasharray="4,3"/>
      <text x="44" y="188" fill="#64748b" font-size="10" text-anchor="end">$0</text>
      <line x1="50" y1="150" x2="620" y2="150" stroke="#1e3a5f" stroke-dasharray="4,3"/>
      <text x="44" y="153" fill="#64748b" font-size="10" text-anchor="end">$50K</text>
      <line x1="50" y1="115" x2="620" y2="115" stroke="#1e3a5f" stroke-dasharray="4,3"/>
      <text x="44" y="118" fill="#64748b" font-size="10" text-anchor="end">$100K</text>
      <line x1="50" y1="80" x2="620" y2="80" stroke="#1e3a5f" stroke-dasharray="4,3"/>
      <text x="44" y="83" fill="#64748b" font-size="10" text-anchor="end">$150K</text>
      <line x1="50" y1="45" x2="620" y2="45" stroke="#1e3a5f" stroke-dasharray="4,3"/>
      <text x="44" y="48" fill="#64748b" font-size="10" text-anchor="end">$200K</text>
      <line x1="50" y1="10" x2="620" y2="10" stroke="#1e3a5f" stroke-dasharray="4,3"/>
      <text x="44" y="13" fill="#64748b" font-size="10" text-anchor="end">$250K</text>

      <!-- Opening $100K  y=115, h=70 -->
      <rect x="65" y="115" width="62" height="70" rx="3" fill="#38bdf8" opacity=".85"/>
      <text x="96" y="112" fill="#38bdf8" font-size="11" font-weight="bold" text-anchor="middle">$100K</text>
      <text x="96" y="200" fill="#94a3b8" font-size="10" text-anchor="middle">Opening</text>

      <!-- New Logos +$83K  y=56.9, h=58.1 -->
      <rect x="150" y="56.9" width="62" height="58.1" rx="3" fill="#34d399" opacity=".85"/>
      <text x="181" y="53" fill="#34d399" font-size="11" font-weight="bold" text-anchor="middle">+$83K</text>
      <text x="181" y="200" fill="#94a3b8" font-size="10" text-anchor="middle">New Logos</text>

      <!-- Expansion +$78K  y=2.3, h=54.6 (cap to 10) -->
      <rect x="235" y="10" width="62" height="46.9" rx="3" fill="#34d399" opacity=".85"/>
      <text x="266" y="7" fill="#34d399" font-size="11" font-weight="bold" text-anchor="middle">+$78K</text>
      <text x="266" y="200" fill="#94a3b8" font-size="10" text-anchor="middle">Expansion</text>

      <!-- Reactivations +$12K  y=115+8.4=h=8.4 -->
      <rect x="320" y="114.6" width="62" height="8.4" rx="2" fill="#34d399" opacity=".85"/>
      <text x="351" y="110" fill="#34d399" font-size="11" font-weight="bold" text-anchor="middle">+$12K</text>
      <text x="351" y="200" fill="#94a3b8" font-size="10" text-anchor="middle">Reactiv.</text>

      <!-- Churn -$18K  y=185, h=12.6 (downward, draw from 185 up) -->
      <rect x="405" y="172.4" width="62" height="12.6" rx="2" fill="#C74634" opacity=".85"/>
      <text x="436" y="168" fill="#C74634" font-size="11" font-weight="bold" text-anchor="middle">-$18K</text>
      <text x="436" y="200" fill="#94a3b8" font-size="10" text-anchor="middle">Churn</text>

      <!-- Contraction -$5K -->
      <rect x="490" y="181.5" width="62" height="3.5" rx="2" fill="#C74634" opacity=".85"/>
      <text x="521" y="177" fill="#C74634" font-size="11" font-weight="bold" text-anchor="middle">-$5K</text>
      <text x="521" y="200" fill="#94a3b8" font-size="10" text-anchor="middle">Contraction</text>

      <!-- Closing $250K  y=10, h=175 -->
      <rect x="555" y="10" width="55" height="175" rx="3" fill="#38bdf8" opacity=".9"/>
      <text x="582" y="7" fill="#38bdf8" font-size="12" font-weight="bold" text-anchor="middle">$250K</text>
      <text x="582" y="200" fill="#94a3b8" font-size="10" text-anchor="middle">Closing</text>
    </svg>
  </div>

  <div class="two-col">
    <!-- Cohort table -->
    <div class="section">
      <h2>Cohort Expansion &nbsp;<span class="badge badge-green">NRR 118%</span></h2>
      <table>
        <thead><tr><th>Cohort</th><th>Initial ARR</th><th>Current ARR</th><th>NRR</th></tr></thead>
        <tbody>
          <tr><td>Q1 2026</td><td>$83K</td><td>$97.9K</td><td class="green">118%</td></tr>
          <tr><td>Q2 2026</td><td>$167K</td><td>$167K</td><td>100%</td></tr>
        </tbody>
      </table>
    </div>

    <!-- Forecast table -->
    <div class="section">
      <h2>ARR Forecast &nbsp;<span class="badge badge-blue">12% MoM</span></h2>
      <table>
        <thead><tr><th>Quarter</th><th>Forecast ARR</th><th>vs Current</th></tr></thead>
        <tbody>
          <tr><td>Current</td><td>$250K</td><td>—</td></tr>
          <tr><td>Q3 2026</td><td>$330K</td><td class="green">+32%</td></tr>
          <tr><td>Q4 2026</td><td class="green">$430K</td><td class="green">+72%</td></tr>
        </tbody>
      </table>
    </div>
  </div>

  <!-- ARR Drivers -->
  <div class="section">
    <h2>ARR Driver Breakdown — Net New $150K</h2>
    <table>
      <thead><tr><th>Driver</th><th>Amount</th><th>% of Net New</th><th>Type</th></tr></thead>
      <tbody>
        <tr><td>New Logos</td><td class="green">+$83K</td><td>55%</td><td><span class="badge badge-green">ADD</span></td></tr>
        <tr><td>Expansion</td><td class="green">+$78K</td><td>52%</td><td><span class="badge badge-green">ADD</span></td></tr>
        <tr><td>Reactivations</td><td class="green">+$12K</td><td>8%</td><td><span class="badge badge-green">ADD</span></td></tr>
        <tr><td>Churn</td><td class="red">-$18K</td><td>-12%</td><td><span class="badge badge-red">LOSS</span></td></tr>
        <tr><td>Contraction</td><td class="red">-$5K</td><td>-3%</td><td><span class="badge badge-red">LOSS</span></td></tr>
        <tr style="font-weight:700"><td>Net New ARR</td><td class="green">+$150K</td><td>100%</td><td><span class="badge badge-blue">NET</span></td></tr>
      </tbody>
    </table>
  </div>

  <footer>OCI Robot Cloud &mdash; ARR Growth Dashboard &mdash; Port 10061 &mdash; &copy; 2026 Oracle</footer>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

if _FASTAPI:
    app = FastAPI(
        title="ARR Growth Dashboard",
        description="Comprehensive ARR growth tracking: waterfall, cohort, forecast, and NRR",
        version="1.0.0",
    )

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return DASHBOARD_HTML

    @app.get("/health")
    def health():
        return {
            "status": "ok",
            "service": "arr_growth_dashboard",
            "port": 10061,
            "closing_arr": 250000,
            "nrr_pct": 118,
        }

    @app.get("/finance/arr_dashboard")
    def arr_dashboard(period: str = "YTD"):
        return _arr_dashboard_for_period(period)

    @app.get("/finance/arr_drivers")
    def arr_drivers():
        return _arr_drivers()

# ---------------------------------------------------------------------------
# stdlib HTTPServer fallback
# ---------------------------------------------------------------------------

else:
    from urllib.parse import urlparse, parse_qs

    class _Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass

        def _send(self, code, ctype, body):
            enc = body.encode() if isinstance(body, str) else body
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", len(enc))
            self.end_headers()
            self.wfile.write(enc)

        def do_GET(self):
            parsed = urlparse(self.path)
            path = parsed.path
            qs = parse_qs(parsed.query)
            if path in ("/", ""):
                self._send(200, "text/html", DASHBOARD_HTML)
            elif path == "/health":
                self._send(200, "application/json", json.dumps({
                    "status": "ok", "service": "arr_growth_dashboard", "port": 10061
                }))
            elif path == "/finance/arr_dashboard":
                period = qs.get("period", ["YTD"])[0]
                self._send(200, "application/json", json.dumps(_arr_dashboard_for_period(period)))
            elif path == "/finance/arr_drivers":
                self._send(200, "application/json", json.dumps(_arr_drivers()))
            else:
                self._send(404, "application/json", json.dumps({"error": "not found"}))

# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if _FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=10061)
    else:
        print("[arr_growth_dashboard] fastapi not found — using stdlib HTTPServer on port 10061")
        server = HTTPServer(("0.0.0.0", 10061), _Handler)
        server.serve_forever()
