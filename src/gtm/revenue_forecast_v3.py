"""Revenue Forecast v3 Service — OCI Robot Cloud (port 10201).

ML revenue forecasting blending bottoms-up, top-down, and AI World
scenario models. v3 target MAPE 12% vs v2 18%.
"""

import json
import sys
from datetime import datetime

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    _FASTAPI_AVAILABLE = True
except ImportError:
    _FASTAPI_AVAILABLE = False

PORT = 10201
SERVICE_NAME = "revenue-forecast-v3"

HTML_DASHBOARD = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Revenue Forecast v3 | OCI Robot Cloud</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; padding: 2rem; }
    h1 { color: #38bdf8; font-size: 1.6rem; margin-bottom: 0.4rem; }
    .subtitle { color: #94a3b8; font-size: 0.9rem; margin-bottom: 2rem; }
    .badge { display: inline-block; background: #C74634; color: #fff; font-size: 0.75rem;
             padding: 0.2rem 0.6rem; border-radius: 9999px; margin-left: 0.5rem; vertical-align: middle; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 1.2rem; margin-bottom: 2rem; }
    .card { background: #1e293b; border: 1px solid #334155; border-radius: 0.75rem; padding: 1.2rem; }
    .card-title { font-size: 0.75rem; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.5rem; }
    .card-value { font-size: 1.8rem; font-weight: 700; color: #38bdf8; }
    .card-sub { font-size: 0.8rem; color: #64748b; margin-top: 0.25rem; }
    .section-title { color: #38bdf8; font-size: 1rem; font-weight: 600; margin-bottom: 1rem; }
    .chart-wrap { background: #1e293b; border: 1px solid #334155; border-radius: 0.75rem; padding: 1.5rem; margin-bottom: 2rem; }
    .endpoints { background: #1e293b; border: 1px solid #334155; border-radius: 0.75rem; padding: 1.2rem; }
    .ep { display: flex; align-items: center; gap: 0.75rem; padding: 0.5rem 0; border-bottom: 1px solid #334155; }
    .ep:last-child { border-bottom: none; }
    .method { font-size: 0.7rem; font-weight: 700; padding: 0.15rem 0.5rem; border-radius: 4px; }
    .get  { background: #0ea5e9; color: #fff; }
    .ep-path { font-family: monospace; font-size: 0.85rem; color: #e2e8f0; }
    .ep-desc { font-size: 0.78rem; color: #94a3b8; margin-left: auto; }
    .footer { margin-top: 2rem; font-size: 0.75rem; color: #475569; }
    .highlight { color: #C74634; font-weight: 600; }
  </style>
</head>
<body>
  <h1>Revenue Forecast v3 <span class="badge">port 10201</span></h1>
  <p class="subtitle">Bottoms-up + Top-down + AI World scenario blend &mdash; target MAPE 12% &mdash; OCI Robot Cloud</p>

  <div class="grid">
    <div class="card">
      <div class="card-title">Bull ARR (Q3)</div>
      <div class="card-value">$580K</div>
      <div class="card-sub">Optimistic scenario</div>
    </div>
    <div class="card">
      <div class="card-title">Base ARR (Q3)</div>
      <div class="card-value">$430K</div>
      <div class="card-sub">Most likely scenario</div>
    </div>
    <div class="card">
      <div class="card-title">Bear ARR (Q3)</div>
      <div class="card-value">$320K</div>
      <div class="card-sub">Conservative scenario</div>
    </div>
    <div class="card">
      <div class="card-title">AI World Boost</div>
      <div class="card-value" style="color:#C74634;">+$120K</div>
      <div class="card-sub">Explicit event model</div>
    </div>
    <div class="card">
      <div class="card-title">v3 MAPE Target</div>
      <div class="card-value">12%</div>
      <div class="card-sub">vs v2 18% (&minus;6pp)</div>
    </div>
    <div class="card">
      <div class="card-title">Blend Methods</div>
      <div class="card-value">3</div>
      <div class="card-sub">Bottoms-up, Top-down, AI World</div>
    </div>
  </div>

  <div class="chart-wrap">
    <div class="section-title">ARR by Scenario — Q3 Forecast ($K)</div>
    <svg viewBox="0 0 560 210" xmlns="http://www.w3.org/2000/svg" style="width:100%; max-width:560px; display:block; margin:0 auto;">
      <!-- axes -->
      <line x1="70" y1="10" x2="70" y2="160" stroke="#334155" stroke-width="1"/>
      <line x1="70" y1="160" x2="530" y2="160" stroke="#334155" stroke-width="1"/>
      <!-- y labels (max 600K) -->
      <text x="62" y="164" fill="#64748b" font-size="10" text-anchor="end">$0</text>
      <text x="62" y="136" fill="#64748b" font-size="10" text-anchor="end">$100K</text>
      <text x="62" y="110" fill="#64748b" font-size="10" text-anchor="end">$200K</text>
      <text x="62" y="83"  fill="#64748b" font-size="10" text-anchor="end">$300K</text>
      <text x="62" y="56"  fill="#64748b" font-size="10" text-anchor="end">$400K</text>
      <text x="62" y="30"  fill="#64748b" font-size="10" text-anchor="end">$500K</text>
      <!-- gridlines -->
      <line x1="70" y1="30"  x2="530" y2="30"  stroke="#1e3a52" stroke-width="1" stroke-dasharray="4,4"/>
      <line x1="70" y1="56"  x2="530" y2="56"  stroke="#1e3a52" stroke-width="1" stroke-dasharray="4,4"/>
      <line x1="70" y1="83"  x2="530" y2="83"  stroke="#1e3a52" stroke-width="1" stroke-dasharray="4,4"/>
      <line x1="70" y1="110" x2="530" y2="110" stroke="#1e3a52" stroke-width="1" stroke-dasharray="4,4"/>
      <line x1="70" y1="136" x2="530" y2="136" stroke="#1e3a52" stroke-width="1" stroke-dasharray="4,4"/>
      <!-- Bull $580K → 580/600*150=145, y=160-145=15 -->
      <rect x="90"  y="15"  width="100" height="145" fill="#38bdf8" rx="4"/>
      <text x="140" y="10"  fill="#38bdf8" font-size="12" font-weight="bold" text-anchor="middle">$580K</text>
      <text x="140" y="178" fill="#94a3b8" font-size="11" text-anchor="middle">Bull</text>
      <!-- Base $430K → 430/600*150=107.5, y=160-107.5=52.5 -->
      <rect x="230" y="53"  width="100" height="107" fill="#7dd3fc" rx="4"/>
      <text x="280" y="47"  fill="#7dd3fc" font-size="12" font-weight="bold" text-anchor="middle">$430K</text>
      <text x="280" y="178" fill="#94a3b8" font-size="11" text-anchor="middle">Base</text>
      <!-- Bear $320K → 320/600*150=80, y=160-80=80 -->
      <rect x="370" y="80"  width="100" height="80"  fill="#C74634" rx="4"/>
      <text x="420" y="74"  fill="#C74634" font-size="12" font-weight="bold" text-anchor="middle">$320K</text>
      <text x="420" y="178" fill="#94a3b8" font-size="11" text-anchor="middle">Bear</text>
    </svg>
  </div>

  <div class="endpoints">
    <div class="section-title">Endpoints</div>
    <div class="ep"><span class="method get">GET</span> <span class="ep-path">/health</span>                  <span class="ep-desc">Service health check</span></div>
    <div class="ep"><span class="method get">GET</span> <span class="ep-path">/</span>                         <span class="ep-desc">This dashboard</span></div>
    <div class="ep"><span class="method get">GET</span> <span class="ep-path">/forecast/v3/revenue</span>     <span class="ep-desc">Latest blended revenue forecast</span></div>
    <div class="ep"><span class="method get">GET</span> <span class="ep-path">/forecast/v3/scenarios</span>   <span class="ep-desc">Bull / base / bear scenario breakdown</span></div>
  </div>

  <div class="footer">OCI Robot Cloud &mdash; cycle-536A &mdash; port 10201</div>
</body>
</html>
"""

if _FASTAPI_AVAILABLE:
    app = FastAPI(title=SERVICE_NAME, version="3.0.0")

    @app.get("/health")
    def health():
        return JSONResponse({"status": "ok", "port": PORT, "service": SERVICE_NAME,
                             "version": "3.0.0",
                             "timestamp": datetime.utcnow().isoformat() + "Z"})

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return HTMLResponse(content=HTML_DASHBOARD)

    @app.get("/forecast/v3/revenue")
    def forecast_revenue():
        """Return the latest blended revenue forecast (stub)."""
        return JSONResponse({
            "version": "v3",
            "blend_methods": ["bottoms_up", "top_down", "ai_world_event"],
            "ai_world_boost_usd": 120_000,
            "mape_target": 0.12,
            "mape_v2": 0.18,
            "blended_arr_q3_usd": 430_000,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        })

    @app.get("/forecast/v3/scenarios")
    def forecast_scenarios():
        """Return bull / base / bear scenario breakdown (stub)."""
        return JSONResponse({
            "version": "v3",
            "quarter": "Q3",
            "scenarios": {
                "bull": {"arr_usd": 580_000, "description": "Optimistic — full AI World pipeline converts"},
                "base": {"arr_usd": 430_000, "description": "Most likely — blended model consensus"},
                "bear": {"arr_usd": 320_000, "description": "Conservative — macro headwinds persist"},
            },
            "ai_world_explicit_event_boost_usd": 120_000,
            "blend_methods": ["bottoms_up", "top_down", "ai_world_event"],
            "mape_target": 0.12,
            "mape_v2": 0.18,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        })

else:
    # Fallback: stdlib HTTP server
    import http.server

    _MOCK_REVENUE = json.dumps({
        "version": "v3",
        "blend_methods": ["bottoms_up", "top_down", "ai_world_event"],
        "ai_world_boost_usd": 120_000,
        "mape_target": 0.12,
        "mape_v2": 0.18,
        "blended_arr_q3_usd": 430_000,
    })
    _MOCK_SCENARIOS = json.dumps({
        "version": "v3",
        "quarter": "Q3",
        "scenarios": {
            "bull": {"arr_usd": 580_000},
            "base": {"arr_usd": 430_000},
            "bear": {"arr_usd": 320_000},
        },
    })

    class _Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass

        def _respond(self, code, ctype, body_bytes):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body_bytes)))
            self.end_headers()
            self.wfile.write(body_bytes)

        def do_GET(self):
            if self.path == "/health":
                self._respond(200, "application/json",
                              json.dumps({"status": "ok", "port": PORT, "service": SERVICE_NAME}).encode())
            elif self.path == "/forecast/v3/revenue":
                self._respond(200, "application/json", _MOCK_REVENUE.encode())
            elif self.path == "/forecast/v3/scenarios":
                self._respond(200, "application/json", _MOCK_SCENARIOS.encode())
            else:
                self._respond(200, "text/html", HTML_DASHBOARD.encode())


if __name__ == "__main__":
    if _FASTAPI_AVAILABLE:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        print(f"[{SERVICE_NAME}] fastapi not found — using stdlib HTTP server on port {PORT}",
              file=sys.stderr)
        server = http.server.HTTPServer(("0.0.0.0", PORT), _Handler)
        server.serve_forever()
