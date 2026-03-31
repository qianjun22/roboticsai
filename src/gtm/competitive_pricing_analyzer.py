"""Competitive Pricing Analyzer — OCI Robot Cloud (port 10221)

Analyzes competitor pricing vs OCI Robot Cloud (9.6x TCO advantage).
Pricing elasticity: +10% price = -2% conversion.
Segment pricing: startup $60K, growth $83K, enterprise $150K+.
"""

import json
import time
from datetime import datetime

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    _FASTAPI_AVAILABLE = True
except ImportError:
    _FASTAPI_AVAILABLE = False

PORT = 10221
SERVICE_NAME = "competitive-pricing-analyzer"

_HTML_DASHBOARD = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Competitive Pricing Analyzer — OCI Robot Cloud</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; padding: 2rem; }
    h1 { color: #C74634; font-size: 1.8rem; margin-bottom: 0.25rem; }
    .subtitle { color: #38bdf8; font-size: 0.95rem; margin-bottom: 2rem; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-bottom: 2rem; }
    .card { background: #1e293b; border-radius: 8px; padding: 1.25rem; border-left: 3px solid #C74634; }
    .card-label { font-size: 0.75rem; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.05em; }
    .card-value { font-size: 1.5rem; font-weight: 700; color: #38bdf8; margin-top: 0.25rem; }
    .chart-container { background: #1e293b; border-radius: 8px; padding: 1.5rem; }
    .chart-title { color: #C74634; font-size: 1rem; font-weight: 600; margin-bottom: 1rem; }
    .endpoints { margin-top: 2rem; background: #1e293b; border-radius: 8px; padding: 1.5rem; }
    .endpoints h2 { color: #38bdf8; font-size: 1rem; margin-bottom: 0.75rem; }
    .ep { padding: 0.4rem 0; border-bottom: 1px solid #334155; font-size: 0.875rem; }
    .ep:last-child { border-bottom: none; }
    .method { color: #C74634; font-weight: 700; margin-right: 0.5rem; }
    .path { color: #e2e8f0; }
  </style>
</head>
<body>
  <h1>Competitive Pricing Analyzer</h1>
  <div class="subtitle">OCI Robot Cloud &mdash; Port 10221 &mdash; 9.6&times; TCO advantage</div>

  <div class="grid">
    <div class="card">
      <div class="card-label">TCO Advantage</div>
      <div class="card-value">9.6&times;</div>
    </div>
    <div class="card">
      <div class="card-label">OCI Annual TCO</div>
      <div class="card-value">$83K</div>
    </div>
    <div class="card">
      <div class="card-label">AWS Equivalent</div>
      <div class="card-value">$797K</div>
    </div>
    <div class="card">
      <div class="card-label">Price Elasticity</div>
      <div class="card-value" style="font-size:1rem;padding-top:0.3rem;">-2% conv / +10%</div>
    </div>
  </div>

  <div class="chart-container">
    <div class="chart-title">Annual TCO Comparison: OCI Robot Cloud vs AWS Equivalent ($K)</div>
    <svg viewBox="0 0 460 210" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:560px;display:block;">
      <!-- axes -->
      <line x1="70" y1="10" x2="70" y2="165" stroke="#475569" stroke-width="1"/>
      <line x1="70" y1="165" x2="430" y2="165" stroke="#475569" stroke-width="1"/>
      <!-- y-axis labels (0, 200, 400, 600, 800) -->
      <text x="60" y="168" text-anchor="end" fill="#94a3b8" font-size="10">$0K</text>
      <text x="60" y="127" text-anchor="end" fill="#94a3b8" font-size="10">$200K</text>
      <text x="60" y="86" text-anchor="end" fill="#94a3b8" font-size="10">$400K</text>
      <text x="60" y="45" text-anchor="end" fill="#94a3b8" font-size="10">$600K</text>
      <text x="60" y="14" text-anchor="end" fill="#94a3b8" font-size="10">$800K</text>
      <!-- gridlines -->
      <line x1="70" y1="123" x2="430" y2="123" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,3"/>
      <line x1="70" y1="82" x2="430" y2="82" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,3"/>
      <line x1="70" y1="41" x2="430" y2="41" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,3"/>
      <line x1="70" y1="10" x2="430" y2="10" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,3"/>
      <!-- OCI $83K: 83/800 * 155 = 16.1px tall, top = 165 - 16 = 149 -->
      <rect x="100" y="149" width="80" height="16" fill="#38bdf8" rx="3"/>
      <text x="140" y="142" text-anchor="middle" fill="#38bdf8" font-size="11" font-weight="bold">$83K</text>
      <text x="140" y="183" text-anchor="middle" fill="#94a3b8" font-size="11">OCI Robot Cloud</text>
      <!-- AWS $797K: 797/800 * 155 = 154.5px tall, top = 165 - 154.5 = 10.5 -->
      <rect x="220" y="11" width="80" height="154" fill="#C74634" rx="3"/>
      <text x="260" y="7" text-anchor="middle" fill="#C74634" font-size="11" font-weight="bold">$797K</text>
      <text x="260" y="183" text-anchor="middle" fill="#94a3b8" font-size="11">AWS Equivalent</text>
      <!-- Savings annotation -->
      <text x="340" y="80" fill="#38bdf8" font-size="11" font-weight="bold">9.6&times; savings</text>
      <text x="340" y="95" fill="#94a3b8" font-size="10">vs AWS equivalent</text>
    </svg>
  </div>

  <div class="endpoints">
    <h2>Endpoints</h2>
    <div class="ep"><span class="method">GET</span><span class="path">/health</span> &mdash; Health check</div>
    <div class="ep"><span class="method">GET</span><span class="path">/</span> &mdash; This dashboard</div>
    <div class="ep"><span class="method">GET</span><span class="path">/pricing/competitive_analysis</span> &mdash; Full competitive pricing breakdown</div>
    <div class="ep"><span class="method">GET</span><span class="path">/pricing/recommendation</span> &mdash; Segment-based pricing recommendation</div>
  </div>
</body>
</html>
"""

if _FASTAPI_AVAILABLE:
    app = FastAPI(title=SERVICE_NAME, version="1.0.0")

    @app.get("/health")
    async def health():
        return JSONResponse({"status": "ok", "port": PORT, "service": SERVICE_NAME, "timestamp": datetime.utcnow().isoformat()})

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return HTMLResponse(_HTML_DASHBOARD)

    @app.get("/pricing/competitive_analysis")
    async def competitive_analysis():
        """Stub: returns competitive pricing comparison data."""
        return JSONResponse({
            "tco_advantage_vs_aws": 9.6,
            "oci_annual_tco_usd": 83_000,
            "competitors": [
                {"name": "AWS RoboMaker", "annual_tco_usd": 797_000, "advantage_ratio": 9.6},
                {"name": "Azure Robot Service", "annual_tco_usd": 650_000, "advantage_ratio": 7.8},
                {"name": "GCP Cloud Robotics", "annual_tco_usd": 720_000, "advantage_ratio": 8.7}
            ],
            "price_elasticity": {"conversion_change_pct_per_10pct_price_increase": -2.0},
            "segment_pricing_usd": {
                "startup": 60_000,
                "growth": 83_000,
                "enterprise": "150000+"
            },
            "timestamp": datetime.utcnow().isoformat()
        })

    @app.get("/pricing/recommendation")
    async def pricing_recommendation():
        """Stub: returns segment-based pricing recommendation."""
        return JSONResponse({
            "recommended_segment": "growth",
            "recommended_price_usd": 83_000,
            "rationale": "Maximizes conversion rate while maintaining 9.6x TCO advantage narrative",
            "conversion_rate_estimate_pct": 34.2,
            "confidence": 0.88,
            "alternatives": [
                {"segment": "startup", "price_usd": 60_000, "conversion_rate_pct": 41.0},
                {"segment": "enterprise", "price_usd": 150_000, "conversion_rate_pct": 22.5}
            ],
            "timestamp": datetime.utcnow().isoformat()
        })

else:
    # Fallback: stdlib HTTP server
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class _Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):  # silence default logging
            pass

        def do_GET(self):
            if self.path == "/health":
                body = json.dumps({"status": "ok", "port": PORT, "service": SERVICE_NAME}).encode()
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

    def _run_fallback():
        server = HTTPServer(("0.0.0.0", PORT), _Handler)
        print(f"[{SERVICE_NAME}] stdlib fallback listening on port {PORT}")
        server.serve_forever()

if __name__ == "__main__":
    if _FASTAPI_AVAILABLE:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        _run_fallback()
