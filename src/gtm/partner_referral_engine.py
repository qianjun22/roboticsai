"""Partner Referral Engine — automated NVIDIA, SI, and customer referral tracking."""

import json
import datetime

PORT = 10235
SERVICE_NAME = "partner_referral_engine"

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    from fastapi import Body
    import uvicorn
    _has_fastapi = True
except ImportError:
    _has_fastapi = False

HTML_DASHBOARD = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Partner Referral Engine</title>
  <style>
    body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; margin: 0; padding: 2rem; }
    h1 { color: #C74634; margin-bottom: 0.25rem; }
    h2 { color: #38bdf8; margin-top: 2rem; }
    .badge { display: inline-block; background: #1e293b; border: 1px solid #38bdf8; color: #38bdf8;
             border-radius: 4px; padding: 0.2rem 0.6rem; font-size: 0.8rem; margin-left: 0.5rem; }
    .card { background: #1e293b; border-radius: 8px; padding: 1.25rem 1.5rem; margin: 1rem 0; }
    .metric { font-size: 2rem; font-weight: 700; color: #38bdf8; }
    .label { font-size: 0.85rem; color: #94a3b8; margin-top: 0.25rem; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 1rem; }
    .endpoint { background: #0f172a; border-left: 3px solid #C74634; padding: 0.5rem 1rem;
                font-family: monospace; font-size: 0.9rem; margin: 0.4rem 0; border-radius: 0 4px 4px 0; }
    .legend-dot { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 6px; }
  </style>
</head>
<body>
  <h1>Partner Referral Engine <span class="badge">port 10235</span></h1>
  <p style="color:#94a3b8;">Automated tracking for NVIDIA, SI, and customer referral quality across the pipeline.</p>

  <h2>Referral Quality by Source</h2>
  <div class="card">
    <svg width="520" height="240" viewBox="0 0 520 240" xmlns="http://www.w3.org/2000/svg">
      <!-- Axes -->
      <line x1="70" y1="10" x2="70" y2="190" stroke="#334155" stroke-width="1"/>
      <line x1="70" y1="190" x2="500" y2="190" stroke="#334155" stroke-width="1"/>
      <!-- Y labels -->
      <text x="65" y="190" text-anchor="end" fill="#94a3b8" font-size="11">0</text>
      <text x="65" y="143" text-anchor="end" fill="#94a3b8" font-size="11">10</text>
      <text x="65" y="95" text-anchor="end" fill="#94a3b8" font-size="11">20</text>
      <text x="65" y="48" text-anchor="end" fill="#94a3b8" font-size="11">30</text>
      <!-- Gridlines -->
      <line x1="70" y1="143" x2="500" y2="143" stroke="#1e293b" stroke-width="1"/>
      <line x1="70" y1="95" x2="500" y2="95" stroke="#1e293b" stroke-width="1"/>
      <line x1="70" y1="48" x2="500" y2="48" stroke="#1e293b" stroke-width="1"/>

      <!-- NVIDIA: total 3 (blue), qualified 2 (sky) -->
      <rect x="90" y="170" width="38" height="20" fill="#1e40af" rx="2"/>
      <text x="109" y="166" text-anchor="middle" fill="#94a3b8" font-size="10">3</text>
      <rect x="132" y="177" width="38" height="13" fill="#38bdf8" rx="2"/>
      <text x="151" y="173" text-anchor="middle" fill="#38bdf8" font-size="10">2</text>
      <text x="130" y="210" text-anchor="middle" fill="#94a3b8" font-size="11">NVIDIA</text>

      <!-- Customer: total 1, qualified 1 -->
      <rect x="220" y="183" width="38" height="7" fill="#1e40af" rx="2"/>
      <text x="239" y="179" text-anchor="middle" fill="#94a3b8" font-size="10">1</text>
      <rect x="262" y="183" width="38" height="7" fill="#38bdf8" rx="2"/>
      <text x="281" y="179" text-anchor="middle" fill="#38bdf8" font-size="10">1</text>
      <text x="260" y="210" text-anchor="middle" fill="#94a3b8" font-size="11">Customer</text>

      <!-- Conference: total 28, qualified 6 -->
      <rect x="350" y="10" width="38" height="180" fill="#1e40af" rx="2"/>
      <text x="369" y="8" text-anchor="middle" fill="#94a3b8" font-size="10">28</text>
      <rect x="392" y="150" width="38" height="40" fill="#38bdf8" rx="2"/>
      <text x="411" y="147" text-anchor="middle" fill="#38bdf8" font-size="10">6</text>
      <text x="390" y="210" text-anchor="middle" fill="#94a3b8" font-size="11">Conference</text>

      <!-- Legend -->
      <rect x="75" y="225" width="10" height="10" fill="#1e40af" rx="1"/>
      <text x="90" y="234" fill="#94a3b8" font-size="11">Total referrals</text>
      <rect x="200" y="225" width="10" height="10" fill="#38bdf8" rx="1"/>
      <text x="215" y="234" fill="#94a3b8" font-size="11">Qualified</text>
    </svg>
  </div>

  <h2>Pipeline Metrics</h2>
  <div class="grid">
    <div class="card">
      <div class="metric">$480K</div>
      <div class="label">Referral-sourced pipeline</div>
    </div>
    <div class="card">
      <div class="metric">$87.5K</div>
      <div class="label">Referral ARR</div>
    </div>
    <div class="card">
      <div class="metric">73%</div>
      <div class="label">Referral close rate</div>
    </div>
    <div class="card">
      <div class="metric">3</div>
      <div class="label">Partner channels tracked</div>
    </div>
  </div>

  <h2>API Endpoints</h2>
  <div class="card">
    <div class="endpoint">GET  /health</div>
    <div class="endpoint">GET  /referrals/engine</div>
    <div class="endpoint">POST /referrals/register</div>
  </div>
</body>
</html>
"""


if _has_fastapi:
    app = FastAPI(title=SERVICE_NAME, version="1.0.0")

    @app.get("/health")
    async def health():
        return JSONResponse({
            "status": "ok",
            "port": PORT,
            "service": SERVICE_NAME,
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        })

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return HTMLResponse(content=HTML_DASHBOARD)

    @app.get("/referrals/engine")
    async def get_engine():
        return JSONResponse({
            "service": SERVICE_NAME,
            "pipeline_usd": 480000,
            "referral_arr_usd": 87500,
            "close_rate_pct": 73,
            "sources": {
                "nvidia": {"total": 3, "qualified": 2},
                "customer": {"total": 1, "qualified": 1},
                "conference": {"total": 28, "qualified": 6},
            },
            "last_updated": "2026-03-30T00:00:00Z",
        })

    @app.post("/referrals/register")
    async def register_referral(payload: dict = Body(default={})):
        return JSONResponse({
            "status": "registered",
            "referral_id": "ref-" + datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S"),
            "source": payload.get("source", "unknown"),
            "contact": payload.get("contact", ""),
            "estimated_arr_usd": payload.get("estimated_arr_usd", 0),
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        })

else:
    import http.server
    import socketserver

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/health":
                body = json.dumps({"status": "ok", "port": PORT, "service": SERVICE_NAME}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
            else:
                body = HTML_DASHBOARD.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            pass

    def _serve():
        with socketserver.TCPServer(("", PORT), _Handler) as httpd:
            print(f"{SERVICE_NAME} fallback server on port {PORT}")
            httpd.serve_forever()


if __name__ == "__main__":
    if _has_fastapi:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        _serve()
