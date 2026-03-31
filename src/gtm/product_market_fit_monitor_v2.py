"""Product Market Fit Monitor v2 — PMF monitoring service (port 10231).

Tracks Sean Ellis score, NPS, usage, and retention across segments.
Overall PMF 76/100; Sean Ellis 47% "very disappointed" (threshold 40%);
NRR 118%, churn 0%.
"""

import json
import time
from typing import Any, Dict

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    _FASTAPI_AVAILABLE = True
except ImportError:
    _FASTAPI_AVAILABLE = False

PORT = 10231
SERVICE_NAME = "product_market_fit_monitor_v2"

_HTML_DASHBOARD = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>PMF Monitor v2</title>
  <style>
    body { margin: 0; background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; }
    .header { background: #C74634; padding: 1.5rem 2rem; }
    .header h1 { margin: 0; font-size: 1.6rem; color: #fff; }
    .header p  { margin: 0.25rem 0 0; color: #fecaca; font-size: 0.9rem; }
    .container { padding: 2rem; max-width: 960px; margin: 0 auto; }
    .cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(175px, 1fr)); gap: 1rem; margin-bottom: 2rem; }
    .card { background: #1e293b; border-radius: 8px; padding: 1.25rem; border-left: 4px solid #38bdf8; }
    .card.warn { border-left-color: #C74634; }
    .card .label { font-size: 0.75rem; color: #94a3b8; text-transform: uppercase; letter-spacing: .05em; }
    .card .value { font-size: 1.8rem; font-weight: 700; color: #38bdf8; margin-top: 0.25rem; }
    .card.warn .value { color: #fca5a5; }
    .card .sub   { font-size: 0.8rem; color: #64748b; margin-top: 0.2rem; }
    .chart-section { background: #1e293b; border-radius: 8px; padding: 1.5rem; margin-bottom: 1.5rem; }
    .chart-section h2 { margin: 0 0 1rem; font-size: 1.1rem; color: #38bdf8; }
    .footer { text-align: center; margin-top: 2rem; color: #475569; font-size: 0.8rem; }
  </style>
</head>
<body>
  <div class="header">
    <h1>Product Market Fit Monitor v2</h1>
    <p>Port {port} &mdash; Sean Ellis + NPS + Usage + Retention</p>
  </div>
  <div class="container">
    <div class="cards">
      <div class="card">
        <div class="label">Overall PMF</div>
        <div class="value">76/100</div>
        <div class="sub">above 70 threshold</div>
      </div>
      <div class="card">
        <div class="label">Sean Ellis</div>
        <div class="value">47%</div>
        <div class="sub">&ldquo;very disappointed&rdquo; &gt;40%</div>
      </div>
      <div class="card">
        <div class="label">NRR</div>
        <div class="value">118%</div>
        <div class="sub">net revenue retention</div>
      </div>
      <div class="card warn">
        <div class="label">Churn</div>
        <div class="value">0%</div>
        <div class="sub">no churn this period</div>
      </div>
    </div>
    <div class="chart-section">
      <h2>PMF Score by Segment (threshold: 70)</h2>
      <svg viewBox="0 0 600 260" xmlns="http://www.w3.org/2000/svg" style="width:100%;">
        <!-- axes -->
        <line x1="70" y1="20" x2="70" y2="210" stroke="#334155" stroke-width="1.5"/>
        <line x1="70" y1="210" x2="570" y2="210" stroke="#334155" stroke-width="1.5"/>
        <!-- y-axis labels -->
        <text x="60" y="215" fill="#64748b" font-size="11" text-anchor="end">0</text>
        <text x="60" y="172" fill="#64748b" font-size="11" text-anchor="end">25</text>
        <text x="60" y="130" fill="#64748b" font-size="11" text-anchor="end">50</text>
        <text x="60" y="87"  fill="#64748b" font-size="11" text-anchor="end">75</text>
        <text x="60" y="44"  fill="#64748b" font-size="11" text-anchor="end">100</text>
        <!-- gridlines -->
        <line x1="70" y1="172" x2="570" y2="172" stroke="#1e293b" stroke-width="1" stroke-dasharray="4,4"/>
        <line x1="70" y1="130" x2="570" y2="130" stroke="#1e293b" stroke-width="1" stroke-dasharray="4,4"/>
        <line x1="70" y1="87"  x2="570" y2="87"  stroke="#1e293b" stroke-width="1" stroke-dasharray="4,4"/>
        <line x1="70" y1="44"  x2="570" y2="44"  stroke="#1e293b" stroke-width="1" stroke-dasharray="4,4"/>
        <!-- threshold line at 70 (y = 210 - 70*1.9 = 210-133 = 77) -->
        <line x1="70" y1="77" x2="570" y2="77" stroke="#f59e0b" stroke-width="1.5" stroke-dasharray="6,3"/>
        <text x="574" y="81" fill="#f59e0b" font-size="10">70</text>
        <!-- bar: Manufacturing 82 (height = 82*1.9 = 155.8 -> y=54) -->
        <rect x="110" y="54" width="90" height="156" rx="4" fill="#38bdf8" opacity="0.9"/>
        <text x="155" y="48"  fill="#e2e8f0" font-size="12" text-anchor="middle" font-weight="bold">82</text>
        <text x="155" y="228" fill="#94a3b8" font-size="11" text-anchor="middle">Manufacturing</text>
        <!-- bar: Logistics 74 (height = 74*1.9 = 140.6 -> y=69) -->
        <rect x="255" y="69" width="90" height="141" rx="4" fill="#38bdf8" opacity="0.75"/>
        <text x="300" y="63"  fill="#e2e8f0" font-size="12" text-anchor="middle" font-weight="bold">74</text>
        <text x="300" y="228" fill="#94a3b8" font-size="11" text-anchor="middle">Logistics</text>
        <!-- bar: Food 71 (height = 71*1.9 = 134.9 -> y=75) -->
        <rect x="400" y="75" width="90" height="135" rx="4" fill="#38bdf8" opacity="0.6"/>
        <text x="445" y="69"  fill="#e2e8f0" font-size="12" text-anchor="middle" font-weight="bold">71</text>
        <text x="445" y="228" fill="#94a3b8" font-size="11" text-anchor="middle">Food &amp; Bev</text>
        <!-- note -->
        <text x="310" y="252" fill="#64748b" font-size="10" text-anchor="middle">All segments above PMF threshold of 70</text>
      </svg>
    </div>
  </div>
  <div class="footer">OCI Robot Cloud &mdash; PMF Monitor v2 &mdash; Port {port}</div>
</body>
</html>
""".replace("{port}", str(PORT))


def _health_payload() -> Dict[str, Any]:
    return {
        "status": "ok",
        "port": PORT,
        "service": SERVICE_NAME,
        "timestamp": time.time(),
    }


def _pmf_v2_payload() -> Dict[str, Any]:
    return {
        "overall_pmf_score": 76,
        "threshold": 70,
        "above_threshold": True,
        "sean_ellis_score": 0.47,
        "sean_ellis_threshold": 0.40,
        "sean_ellis_pass": True,
        "nrr": 1.18,
        "churn_rate": 0.0,
        "segments": {
            "manufacturing": {"pmf_score": 82, "above_threshold": True},
            "logistics": {"pmf_score": 74, "above_threshold": True},
            "food_and_bev": {"pmf_score": 71, "above_threshold": True},
        },
        "version": "v2",
    }


def _pmf_v2_trend_payload() -> Dict[str, Any]:
    return {
        "metric": "overall_pmf_score",
        "version": "v2",
        "trend": [
            {"period": "2025-Q4", "score": 61},
            {"period": "2026-Q1", "score": 68},
            {"period": "2026-Q2", "score": 72},
            {"period": "2026-Q3", "score": 76},
        ],
        "direction": "up",
        "delta_qoq": "+4",
        "forecast_next_quarter": 79,
    }


if _FASTAPI_AVAILABLE:
    app = FastAPI(title=SERVICE_NAME, version="2.0.0")

    @app.get("/health")
    async def health():
        return JSONResponse(_health_payload())

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return HTMLResponse(_HTML_DASHBOARD)

    @app.get("/product/pmf_v2")
    async def pmf_v2():
        return JSONResponse(_pmf_v2_payload())

    @app.get("/product/pmf_v2/trend")
    async def pmf_v2_trend():
        return JSONResponse(_pmf_v2_trend_payload())

else:
    import http.server

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/health":
                body = json.dumps(_health_payload()).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)
            elif self.path == "/product/pmf_v2":
                body = json.dumps(_pmf_v2_payload()).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)
            elif self.path == "/product/pmf_v2/trend":
                body = json.dumps(_pmf_v2_trend_payload()).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)
            else:
                body = _HTML_DASHBOARD.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(body)

        def log_message(self, fmt, *args):
            pass


if __name__ == "__main__":
    if _FASTAPI_AVAILABLE:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        server = http.server.HTTPServer(("0.0.0.0", PORT), _Handler)
        print(f"Fallback HTTPServer running on port {PORT}")
        server.serve_forever()
