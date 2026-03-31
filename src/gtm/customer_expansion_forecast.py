"""Customer Expansion Forecast — FastAPI service (port 10245).

Predicts per-customer expansion ARR with a 12-month lookahead.
Top accounts: Machina ($41K/4mo), Helix ($28K/7mo), Verdant ($15K/9mo) = $84K total.
"""

import json
import time
from typing import Any, Dict, List

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    _FASTAPI_AVAILABLE = True
except ImportError:
    _FASTAPI_AVAILABLE = False

PORT = 10245
SERVICE_NAME = "customer_expansion_forecast"

# ---------------------------------------------------------------------------
# Static forecast data
# ---------------------------------------------------------------------------

_PORTFOLIO: List[Dict[str, Any]] = [
    {
        "customer": "Machina",
        "expansion_probability": 0.78,
        "expansion_arr_usd": 41000,
        "expected_months_to_close": 4,
        "top_signals": ["high API usage growth", "new robotics division", "exec sponsor engaged"],
        "recommended_action": "Schedule executive business review; propose multi-arm bundle.",
    },
    {
        "customer": "Helix",
        "expansion_probability": 0.62,
        "expansion_arr_usd": 28000,
        "expected_months_to_close": 7,
        "top_signals": ["pilot success", "budget cycle Q3", "3 new use-cases identified"],
        "recommended_action": "Present ROI case study; introduce SDG add-on package.",
    },
    {
        "customer": "Verdant",
        "expansion_probability": 0.45,
        "expansion_arr_usd": 15000,
        "expected_months_to_close": 9,
        "top_signals": ["moderate usage", "interest in fine-tuning", "price sensitivity noted"],
        "recommended_action": "Offer starter fine-tuning tier; nurture with monthly check-ins.",
    },
]

_PORTFOLIO_SUMMARY = {
    "total_expansion_arr_usd": 84000,
    "num_accounts": len(_PORTFOLIO),
    "forecast_horizon_months": 12,
    "weighted_pipeline_usd": int(
        sum(c["expansion_arr_usd"] * c["expansion_probability"] for c in _PORTFOLIO)
    ),
    "generated_at": "2026-03-30T00:00:00Z",
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
  <title>Customer Expansion Forecast — Port {port}</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background: #0f172a;
      color: #e2e8f0;
      font-family: 'Segoe UI', system-ui, sans-serif;
      min-height: 100vh;
      padding: 2rem;
    }}
    h1 {{ color: #38bdf8; font-size: 1.75rem; margin-bottom: 0.25rem; }}
    .subtitle {{ color: #94a3b8; font-size: 0.95rem; margin-bottom: 2rem; }}
    .badge {{
      display: inline-block;
      background: #C74634;
      color: #fff;
      border-radius: 4px;
      padding: 2px 10px;
      font-size: 0.8rem;
      font-weight: 600;
      margin-bottom: 2rem;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 1.25rem;
      margin-bottom: 2rem;
    }}
    .card {{
      background: #1e293b;
      border: 1px solid #334155;
      border-radius: 10px;
      padding: 1.25rem;
    }}
    .card-title {{ color: #94a3b8; font-size: 0.78rem; text-transform: uppercase; letter-spacing: .05em; margin-bottom: 0.4rem; }}
    .card-value {{ color: #38bdf8; font-size: 1.6rem; font-weight: 700; }}
    .card-sub {{ color: #64748b; font-size: 0.78rem; margin-top: 0.2rem; }}
    .chart-section {{
      background: #1e293b;
      border: 1px solid #334155;
      border-radius: 10px;
      padding: 1.5rem;
      margin-bottom: 2rem;
    }}
    .chart-title {{ color: #38bdf8; font-size: 1rem; font-weight: 600; margin-bottom: 1rem; }}
    .endpoint {{
      background: #1e293b;
      border: 1px solid #334155;
      border-radius: 8px;
      padding: 0.75rem 1rem;
      margin-bottom: 0.6rem;
      font-family: monospace;
      font-size: 0.87rem;
      color: #a5f3fc;
    }}
    .method {{ color: #C74634; font-weight: 700; margin-right: 0.75rem; }}
  </style>
</head>
<body>
  <h1>Customer Expansion Forecast</h1>
  <div class="subtitle">12-month per-customer expansion ARR prediction — powered by OCI Robot Cloud signals</div>
  <span class="badge">OCI Robot Cloud · Port {port}</span>

  <div class="grid">
    <div class="card">
      <div class="card-title">Total Pipeline</div>
      <div class="card-value">$84K</div>
      <div class="card-sub">3 accounts · 12-mo horizon</div>
    </div>
    <div class="card">
      <div class="card-title">Weighted Pipeline</div>
      <div class="card-value">$52K</div>
      <div class="card-sub">Prob-adjusted ARR</div>
    </div>
    <div class="card">
      <div class="card-title">Top Account</div>
      <div class="card-value" style="color:#4ade80">Machina</div>
      <div class="card-sub">$41K · 78% · 4 months</div>
    </div>
    <div class="card">
      <div class="card-title">Forecast Horizon</div>
      <div class="card-value">12 mo</div>
      <div class="card-sub">Lookahead window</div>
    </div>
  </div>

  <div class="chart-section">
    <div class="chart-title">Expansion Probability by Account</div>
    <svg width="100%" height="170" viewBox="0 0 480 170" xmlns="http://www.w3.org/2000/svg">
      <!-- axes -->
      <line x1="70" y1="10" x2="70" y2="130" stroke="#334155" stroke-width="1"/>
      <line x1="70" y1="130" x2="460" y2="130" stroke="#334155" stroke-width="1"/>
      <!-- grid lines 25/50/75/100 -->
      <line x1="70" y1="100" x2="460" y2="100" stroke="#1e3a5f" stroke-width="0.5" stroke-dasharray="3,3"/>
      <line x1="70" y1="70"  x2="460" y2="70"  stroke="#1e3a5f" stroke-width="0.5" stroke-dasharray="3,3"/>
      <line x1="70" y1="40"  x2="460" y2="40"  stroke="#1e3a5f" stroke-width="0.5" stroke-dasharray="3,3"/>
      <line x1="70" y1="10"  x2="460" y2="10"  stroke="#1e3a5f" stroke-width="0.5" stroke-dasharray="3,3"/>
      <!-- y-axis labels -->
      <text x="62" y="134" fill="#64748b" font-size="10" text-anchor="end">0%</text>
      <text x="62" y="104" fill="#64748b" font-size="10" text-anchor="end">25%</text>
      <text x="62" y="74"  fill="#64748b" font-size="10" text-anchor="end">50%</text>
      <text x="62" y="44"  fill="#64748b" font-size="10" text-anchor="end">75%</text>
      <text x="62" y="14"  fill="#64748b" font-size="10" text-anchor="end">100%</text>
      <!-- bars: scale 100%=120px, baseline y=130 -->
      <!-- Machina 78% → h=93.6, y=36.4 -->
      <rect x="90"  y="36"  width="80" height="94" fill="#38bdf8" rx="4"/>
      <text x="130" y="29"  fill="#e2e8f0" font-size="11" text-anchor="middle">78%</text>
      <text x="130" y="150" fill="#94a3b8" font-size="11" text-anchor="middle">Machina</text>
      <!-- Helix 62% → h=74.4, y=55.6 -->
      <rect x="220" y="56"  width="80" height="74" fill="#C74634" rx="4"/>
      <text x="260" y="49"  fill="#e2e8f0" font-size="11" text-anchor="middle">62%</text>
      <text x="260" y="150" fill="#94a3b8" font-size="11" text-anchor="middle">Helix</text>
      <!-- Verdant 45% → h=54, y=76 -->
      <rect x="350" y="76"  width="80" height="54" fill="#a78bfa" rx="4"/>
      <text x="390" y="69"  fill="#e2e8f0" font-size="11" text-anchor="middle">45%</text>
      <text x="390" y="150" fill="#94a3b8" font-size="11" text-anchor="middle">Verdant</text>
    </svg>
  </div>

  <div class="chart-section">
    <div class="chart-title">API Endpoints</div>
    <div class="endpoint"><span class="method">GET</span>/health — liveness probe</div>
    <div class="endpoint"><span class="method">GET</span>/ — this dashboard</div>
    <div class="endpoint"><span class="method">GET</span>/customers/expansion_forecast — per-account forecasts</div>
    <div class="endpoint"><span class="method">GET</span>/customers/expansion_forecast/portfolio — portfolio summary</div>
  </div>
</body>
</html>
""".format(port=PORT)


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

if _FASTAPI_AVAILABLE:
    app = FastAPI(
        title="Customer Expansion Forecast",
        description="Predicts per-customer expansion ARR with 12-month lookahead",
        version="1.0.0",
    )

    @app.get("/health")
    def health() -> JSONResponse:
        return JSONResponse({
            "status": "ok",
            "port": PORT,
            "service": SERVICE_NAME,
            "version": "1.0.0",
            "timestamp": time.time(),
        })

    @app.get("/", response_class=HTMLResponse)
    def dashboard() -> HTMLResponse:
        return HTMLResponse(content=DASHBOARD_HTML)

    @app.get("/customers/expansion_forecast")
    def expansion_forecast() -> JSONResponse:
        """Return per-account expansion forecasts."""
        return JSONResponse({
            "forecasts": _PORTFOLIO,
            "count": len(_PORTFOLIO),
            "generated_at": _PORTFOLIO_SUMMARY["generated_at"],
        })

    @app.get("/customers/expansion_forecast/portfolio")
    def portfolio_summary() -> JSONResponse:
        """Return aggregate portfolio expansion summary."""
        return JSONResponse(_PORTFOLIO_SUMMARY)


# ---------------------------------------------------------------------------
# Fallback: stdlib HTTPServer
# ---------------------------------------------------------------------------

else:
    import http.server
    import urllib.parse

    class _Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass

        def do_GET(self):
            path = urllib.parse.urlparse(self.path).path
            if path == "/health":
                body = json.dumps({
                    "status": "ok",
                    "port": PORT,
                    "service": SERVICE_NAME,
                    "note": "fastapi not installed — stdlib fallback",
                }).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)
            elif path == "/customers/expansion_forecast":
                body = json.dumps({"forecasts": _PORTFOLIO, "count": len(_PORTFOLIO)}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)
            elif path == "/customers/expansion_forecast/portfolio":
                body = json.dumps(_PORTFOLIO_SUMMARY).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)
            else:
                body = DASHBOARD_HTML.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(body)

    def _serve():
        server = http.server.HTTPServer(("0.0.0.0", PORT), _Handler)
        print(f"[{SERVICE_NAME}] stdlib fallback listening on port {PORT}")
        server.serve_forever()


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if _FASTAPI_AVAILABLE:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        _serve()
