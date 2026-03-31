"""Pricing Dashboard — FastAPI service (port 10249).

Real-time pricing metrics: deal pricing, discount tracking, and margin analysis.
"""

import json
import time
from typing import Any, Dict, List, Optional

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    _FASTAPI_AVAILABLE = True
except ImportError:
    _FASTAPI_AVAILABLE = False

PORT = 10249
SERVICE_NAME = "pricing_dashboard"

_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Pricing Dashboard</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; padding: 2rem; }
    h1 { color: #C74634; font-size: 1.8rem; margin-bottom: 0.4rem; }
    .subtitle { color: #38bdf8; font-size: 0.95rem; margin-bottom: 2rem; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1.2rem; margin-bottom: 2rem; }
    .card { background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 1.2rem; }
    .card h3 { color: #38bdf8; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.5rem; }
    .card .val { color: #f1f5f9; font-size: 1.6rem; font-weight: 700; }
    .card .sub { color: #94a3b8; font-size: 0.78rem; margin-top: 0.25rem; }
    .chart-wrap { background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 1.5rem; margin-bottom: 2rem; }
    .chart-wrap h2 { color: #C74634; font-size: 1rem; margin-bottom: 1rem; }
    .waterfall { background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 1.5rem; margin-bottom: 2rem; }
    .waterfall h2 { color: #C74634; font-size: 1rem; margin-bottom: 1rem; }
    .wf-row { display: flex; align-items: center; margin-bottom: 0.5rem; gap: 0.8rem; }
    .wf-label { color: #94a3b8; font-size: 0.82rem; width: 160px; flex-shrink: 0; }
    .wf-bar-bg { flex: 1; background: #0f172a; border-radius: 4px; height: 20px; position: relative; overflow: hidden; }
    .wf-bar { height: 100%; border-radius: 4px; display: flex; align-items: center; padding-left: 6px; font-size: 0.78rem; font-weight: 600; color: #f1f5f9; }
    .wf-val { color: #f1f5f9; font-size: 0.82rem; width: 56px; text-align: right; flex-shrink: 0; }
    .endpoint { background: #1e293b; border-left: 3px solid #C74634; border-radius: 6px; padding: 0.8rem 1rem; margin-bottom: 0.6rem; }
    .endpoint code { color: #38bdf8; font-size: 0.85rem; }
    .endpoint p { color: #94a3b8; font-size: 0.78rem; margin-top: 0.3rem; }
    footer { color: #475569; font-size: 0.75rem; margin-top: 2rem; }
  </style>
</head>
<body>
  <h1>Pricing Dashboard</h1>
  <p class="subtitle">Real-time deal pricing, discount tracking &amp; margin &mdash; port 10249</p>

  <div class="grid">
    <div class="card"><h3>Q3 ACV Target</h3><div class="val">$95K</div><div class="sub">Q1: $71K &rarr; Q2: $83K trend</div></div>
    <div class="card"><h3>Blended GM</h3><div class="val">91%</div><div class="sub">Gross margin</div></div>
    <div class="card"><h3>Avg Discount</h3><div class="val">8%</div><div class="sub">Highest: 15%</div></div>
    <div class="card"><h3>Port</h3><div class="val">10249</div><div class="sub">FastAPI / uvicorn</div></div>
  </div>

  <div class="chart-wrap">
    <h2>ACV Trend (K USD)</h2>
    <svg viewBox="0 0 480 200" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:480px;display:block;">
      <!-- axes -->
      <line x1="60" y1="10" x2="60" y2="160" stroke="#475569" stroke-width="1"/>
      <line x1="60" y1="160" x2="460" y2="160" stroke="#475569" stroke-width="1"/>
      <!-- grid lines -->
      <line x1="60" y1="40" x2="460" y2="40" stroke="#334155" stroke-width="0.5" stroke-dasharray="4"/>
      <line x1="60" y1="80" x2="460" y2="80" stroke="#334155" stroke-width="0.5" stroke-dasharray="4"/>
      <line x1="60" y1="120" x2="460" y2="120" stroke="#334155" stroke-width="0.5" stroke-dasharray="4"/>
      <!-- y labels (0, 33, 66, 100 mapped to $0, ~33K, ~66K, ~100K) -->
      <text x="52" y="163" fill="#94a3b8" font-size="11" text-anchor="end">$0</text>
      <text x="52" y="123" fill="#94a3b8" font-size="11" text-anchor="end">$33K</text>
      <text x="52" y="83" fill="#94a3b8" font-size="11" text-anchor="end">$66K</text>
      <text x="52" y="43" fill="#94a3b8" font-size="11" text-anchor="end">$100K</text>
      <!-- bar Q1 $71K => 71/100*150=106.5, y=160-106.5=53.5 -->
      <rect x="90" y="54" width="70" height="106" fill="#C74634" rx="4"/>
      <text x="125" y="48" fill="#f1f5f9" font-size="12" text-anchor="middle" font-weight="bold">$71K</text>
      <text x="125" y="178" fill="#94a3b8" font-size="11" text-anchor="middle">Q1</text>
      <!-- bar Q2 $83K => 83/100*150=124.5, y=160-124.5=35.5 -->
      <rect x="205" y="36" width="70" height="124" fill="#38bdf8" rx="4"/>
      <text x="240" y="30" fill="#f1f5f9" font-size="12" text-anchor="middle" font-weight="bold">$83K</text>
      <text x="240" y="178" fill="#94a3b8" font-size="11" text-anchor="middle">Q2</text>
      <!-- bar Q3 target $95K => 95/100*150=142.5, y=160-142.5=17.5 -->
      <rect x="320" y="18" width="70" height="142" fill="#64748b" rx="4" stroke="#38bdf8" stroke-width="1.5" stroke-dasharray="4"/>
      <text x="355" y="12" fill="#f1f5f9" font-size="12" text-anchor="middle" font-weight="bold">$95K*</text>
      <text x="355" y="178" fill="#94a3b8" font-size="11" text-anchor="middle">Q3 Target</text>
    </svg>
  </div>

  <div class="waterfall">
    <h2>Discount Waterfall — Representative Deal</h2>
    <div class="wf-row">
      <span class="wf-label">List Price</span>
      <div class="wf-bar-bg"><div class="wf-bar" style="width:100%;background:#C74634;">List</div></div>
      <span class="wf-val">$83K</span>
    </div>
    <div class="wf-row">
      <span class="wf-label">Volume Discount (-4%)</span>
      <div class="wf-bar-bg"><div class="wf-bar" style="width:96%;background:#7f1d1d;"></div></div>
      <span class="wf-val" style="color:#fca5a5;">-$3.3K</span>
    </div>
    <div class="wf-row">
      <span class="wf-label">Competitive Discount (-3%)</span>
      <div class="wf-bar-bg"><div class="wf-bar" style="width:90%;background:#7f1d1d;"></div></div>
      <span class="wf-val" style="color:#fca5a5;">-$2.5K</span>
    </div>
    <div class="wf-row">
      <span class="wf-label">Net Price</span>
      <div class="wf-bar-bg"><div class="wf-bar" style="width:90%;background:#15803d;">Net</div></div>
      <span class="wf-val" style="color:#86efac;">$75K</span>
    </div>
  </div>

  <div class="chart-wrap">
    <h2>API Endpoints</h2>
    <div class="endpoint"><code>GET /health</code><p>Service health check — status, port, service name</p></div>
    <div class="endpoint"><code>GET /</code><p>This HTML dashboard</p></div>
    <div class="endpoint"><code>GET /pricing/dashboard</code><p>Current pricing metrics, ACV trend, discount summary</p></div>
    <div class="endpoint"><code>GET /pricing/deals</code><p>List of recent deals with pricing and discount breakdown</p></div>
  </div>

  <footer>OCI Robot Cloud &mdash; Pricing Dashboard &mdash; port 10249</footer>
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
            "timestamp": time.time(),
        })

    @app.get("/", response_class=HTMLResponse)
    async def dashboard() -> HTMLResponse:
        return HTMLResponse(content=_HTML)

    @app.get("/pricing/dashboard")
    async def pricing_dashboard() -> JSONResponse:
        """Stub: return current pricing metrics and ACV trend."""
        return JSONResponse({
            "service": SERVICE_NAME,
            "acv_trend": {
                "Q1": 71000,
                "Q2": 83000,
                "Q3_target": 95000,
            },
            "blended_gm_pct": 91,
            "discount": {
                "avg_pct": 8,
                "max_pct": 15,
                "waterfall_example": {
                    "list_price": 83000,
                    "volume_discount_pct": 4,
                    "competitive_discount_pct": 3,
                    "net_price": 75000,
                },
            },
            "as_of": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        })

    @app.get("/pricing/deals")
    async def pricing_deals() -> JSONResponse:
        """Stub: return list of recent deals with pricing and discount breakdown."""
        return JSONResponse({
            "service": SERVICE_NAME,
            "deals": [
                {
                    "deal_id": "deal-001",
                    "customer": "Acme Robotics",
                    "list_price": 83000,
                    "discount_pct": 9.6,
                    "net_price": 75000,
                    "gm_pct": 91,
                    "quarter": "Q2",
                    "status": "closed_won",
                },
                {
                    "deal_id": "deal-002",
                    "customer": "Beta Automation",
                    "list_price": 95000,
                    "discount_pct": 15,
                    "net_price": 80750,
                    "gm_pct": 89,
                    "quarter": "Q3",
                    "status": "pipeline",
                },
                {
                    "deal_id": "deal-003",
                    "customer": "Gamma Labs",
                    "list_price": 71000,
                    "discount_pct": 4,
                    "net_price": 68160,
                    "gm_pct": 92,
                    "quarter": "Q1",
                    "status": "closed_won",
                },
            ],
            "total_deals": 3,
        })

else:
    # Fallback: stdlib http.server
    import http.server
    import socketserver

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/health":
                body = json.dumps({"status": "ok", "port": PORT, "service": SERVICE_NAME}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)
            else:
                body = _HTML.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(body)

        def log_message(self, fmt, *args):  # silence default logging
            pass

    def _serve():
        with socketserver.TCPServer(("", PORT), _Handler) as httpd:
            print(f"{SERVICE_NAME} fallback server on port {PORT}")
            httpd.serve_forever()


if __name__ == "__main__":
    if _FASTAPI_AVAILABLE:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        _serve()
