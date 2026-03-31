"""NVIDIA Partnership Tracker — GTM partnership development service.

Port 10179
Tracks NVIDIA partnership milestones: Isaac Sim + Cosmos + GR00T + preferred cloud.
Milestone path: intro -> co-engineering LOI -> preferred cloud agreement -> GTC 2027 joint talk.
"""

import json
from datetime import datetime

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    _FASTAPI_AVAILABLE = True
except ImportError:
    _FASTAPI_AVAILABLE = False

PORT = 10179
SERVICE_NAME = "nvidia_partnership_tracker"

HTML_DASHBOARD = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>NVIDIA Partnership Tracker</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; padding: 2rem; }
    h1 { color: #C74634; font-size: 1.8rem; margin-bottom: 0.4rem; }
    .subtitle { color: #38bdf8; font-size: 0.95rem; margin-bottom: 2rem; }
    .grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 1.2rem; margin-bottom: 2rem; }
    .card { background: #1e293b; border-radius: 10px; padding: 1.2rem; border: 1px solid #334155; }
    .card h2 { color: #38bdf8; font-size: 0.85rem; margin-bottom: 0.6rem; text-transform: uppercase; letter-spacing: 0.05em; }
    .metric { font-size: 1.6rem; font-weight: 700; color: #C74634; }
    .metric-label { font-size: 0.78rem; color: #94a3b8; margin-top: 0.2rem; }
    .chart-container { background: #1e293b; border-radius: 10px; padding: 1.4rem; border: 1px solid #334155; margin-bottom: 1.5rem; }
    .chart-container h2 { color: #38bdf8; font-size: 1rem; margin-bottom: 1rem; text-transform: uppercase; letter-spacing: 0.05em; }
    .milestones { background: #1e293b; border-radius: 10px; padding: 1.4rem; border: 1px solid #334155; margin-bottom: 1.5rem; }
    .milestones h2 { color: #38bdf8; font-size: 1rem; margin-bottom: 1rem; text-transform: uppercase; letter-spacing: 0.05em; }
    .milestone-row { display: flex; align-items: center; gap: 1rem; margin-bottom: 0.8rem; }
    .m-dot { width: 12px; height: 12px; border-radius: 50%; flex-shrink: 0; }
    .m-done { background: #34d399; }
    .m-active { background: #C74634; }
    .m-future { background: #475569; }
    .m-label { font-size: 0.88rem; color: #cbd5e1; }
    .m-status { font-size: 0.75rem; margin-left: auto; padding: 0.15rem 0.5rem; border-radius: 9999px; }
    .s-done { background: #0f3b2d; color: #34d399; border: 1px solid #34d399; }
    .s-active { background: #3b1010; color: #f87171; border: 1px solid #f87171; }
    .s-future { background: #1e293b; color: #64748b; border: 1px solid #475569; }
    .endpoints { background: #1e293b; border-radius: 10px; padding: 1.4rem; border: 1px solid #334155; }
    .endpoints h2 { color: #38bdf8; font-size: 1rem; margin-bottom: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em; }
    .ep { font-family: monospace; font-size: 0.85rem; color: #fbbf24; margin-bottom: 0.4rem; }
  </style>
</head>
<body>
  <h1>NVIDIA Partnership Tracker</h1>
  <div class="subtitle">Isaac Sim + Cosmos + GR00T + Preferred Cloud &mdash; Port 10179 &mdash; OCI Robot Cloud GTM</div>

  <div class="grid">
    <div class="card">
      <h2>Preferred Cloud ARR</h2>
      <div class="metric">$2.8M</div>
      <div class="metric-label">estimated annual recurring revenue</div>
    </div>
    <div class="card">
      <h2>Co-Engineering</h2>
      <div class="metric">2 FTE</div>
      <div class="metric-label">equivalent NVIDIA eng bandwidth</div>
    </div>
    <div class="card">
      <h2>GTC 2027 Leads</h2>
      <div class="metric">800</div>
      <div class="metric-label">projected pipeline from joint talk</div>
    </div>
  </div>

  <div class="chart-container">
    <h2>NVIDIA Deal Value Breakdown</h2>
    <svg viewBox="0 0 520 190" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:520px;display:block;">
      <!-- axes -->
      <line x1="70" y1="20" x2="70" y2="150" stroke="#334155" stroke-width="1"/>
      <line x1="70" y1="150" x2="490" y2="150" stroke="#334155" stroke-width="1"/>
      <!-- Preferred Cloud $2.8M ARR — tallest bar (index 100% = 130px height) -->
      <rect x="90" y="20" width="100" height="130" fill="#C74634" rx="3"/>
      <text x="140" y="15" text-anchor="middle" fill="#e2e8f0" font-size="11" font-weight="bold">$2.8M ARR</text>
      <text x="140" y="168" text-anchor="middle" fill="#94a3b8" font-size="10">Preferred</text>
      <text x="140" y="180" text-anchor="middle" fill="#94a3b8" font-size="10">Cloud</text>
      <!-- Co-engineering 2 FTE — proportional bar (scale: 2/2.8 ≈ 71% → ~92px) -->
      <rect x="230" y="58" width="100" height="92" fill="#38bdf8" rx="3"/>
      <text x="280" y="53" text-anchor="middle" fill="#e2e8f0" font-size="11" font-weight="bold">2 FTE</text>
      <text x="280" y="168" text-anchor="middle" fill="#94a3b8" font-size="10">Co-Engineering</text>
      <text x="280" y="180" text-anchor="middle" fill="#94a3b8" font-size="10">LOI</text>
      <!-- GTC 800 leads — smaller bar (scale: 800 leads → ~45px) -->
      <rect x="370" y="105" width="100" height="45" fill="#a78bfa" rx="3"/>
      <text x="420" y="100" text-anchor="middle" fill="#e2e8f0" font-size="11" font-weight="bold">800 leads</text>
      <text x="420" y="168" text-anchor="middle" fill="#94a3b8" font-size="10">GTC 2027</text>
      <text x="420" y="180" text-anchor="middle" fill="#94a3b8" font-size="10">Joint Talk</text>
      <!-- y-axis labels -->
      <text x="65" y="155" text-anchor="end" fill="#64748b" font-size="9">0</text>
      <text x="65" y="85" text-anchor="end" fill="#64748b" font-size="9">mid</text>
      <text x="65" y="24" text-anchor="end" fill="#64748b" font-size="9">max</text>
      <line x1="70" y1="85" x2="490" y2="85" stroke="#1e293b" stroke-width="1" stroke-dasharray="4,4"/>
    </svg>
  </div>

  <div class="milestones">
    <h2>Milestone Path</h2>
    <div class="milestone-row">
      <div class="m-dot m-done"></div>
      <div class="m-label">1. Intro &amp; Technical Alignment (Isaac Sim + GR00T eval on OCI)</div>
      <span class="m-status s-done">done</span>
    </div>
    <div class="milestone-row">
      <div class="m-dot m-active"></div>
      <div class="m-label">2. Co-Engineering LOI — 2 FTE NVIDIA eng working on OCI integrations</div>
      <span class="m-status s-active">in progress</span>
    </div>
    <div class="milestone-row">
      <div class="m-dot m-future"></div>
      <div class="m-label">3. Preferred Cloud Agreement — OCI as preferred cloud for NVIDIA robotics ($2.8M ARR)</div>
      <span class="m-status s-future">Q3 2026</span>
    </div>
    <div class="milestone-row">
      <div class="m-dot m-future"></div>
      <div class="m-label">4. Cosmos World Model deep integration &amp; joint reference architecture</div>
      <span class="m-status s-future">Q4 2026</span>
    </div>
    <div class="milestone-row">
      <div class="m-dot m-future"></div>
      <div class="m-label">5. GTC 2027 Joint Talk — 800 projected leads from joint keynote session</div>
      <span class="m-status s-future">GTC 2027</span>
    </div>
  </div>

  <div class="endpoints">
    <h2>API Endpoints</h2>
    <div class="ep">GET /health &mdash; service health</div>
    <div class="ep">GET / &mdash; this dashboard</div>
    <div class="ep">GET /partnerships/nvidia/status &mdash; current milestone status</div>
    <div class="ep">GET /partnerships/nvidia/deal_value &mdash; deal value breakdown</div>
  </div>
</body>
</html>
"""

if _FASTAPI_AVAILABLE:
    app = FastAPI(title=SERVICE_NAME, version="1.0.0")

    @app.get("/health")
    def health():
        return JSONResponse({
            "status": "ok",
            "port": PORT,
            "service": SERVICE_NAME,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        })

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return HTMLResponse(content=HTML_DASHBOARD)

    @app.get("/partnerships/nvidia/status")
    def nvidia_status():
        return JSONResponse({
            "partner": "NVIDIA",
            "integrations": ["Isaac Sim", "Cosmos World Model", "GR00T N1.6", "Preferred Cloud"],
            "current_milestone": "co_engineering_loi",
            "milestones": [
                {"id": "intro", "name": "Intro & Technical Alignment", "status": "done", "completed": "2026-01-15"},
                {"id": "co_engineering_loi", "name": "Co-Engineering LOI", "status": "in_progress", "target": "2026-06-30"},
                {"id": "preferred_cloud", "name": "Preferred Cloud Agreement", "status": "planned", "target": "2026-09-30"},
                {"id": "cosmos_integration", "name": "Cosmos Deep Integration", "status": "planned", "target": "2026-12-31"},
                {"id": "gtc_2027", "name": "GTC 2027 Joint Talk", "status": "planned", "target": "2027-03-01"},
            ],
            "last_updated": datetime.utcnow().isoformat() + "Z",
        })

    @app.get("/partnerships/nvidia/deal_value")
    def nvidia_deal_value():
        return JSONResponse({
            "partner": "NVIDIA",
            "total_estimated_arr_usd": 2800000,
            "breakdown": [
                {
                    "category": "preferred_cloud",
                    "label": "Preferred Cloud Agreement",
                    "value_usd_arr": 2800000,
                    "description": "OCI as preferred cloud for NVIDIA robotics workloads",
                },
                {
                    "category": "co_engineering",
                    "label": "Co-Engineering LOI",
                    "value_fte_equiv": 2,
                    "description": "2 FTE NVIDIA eng bandwidth for OCI integrations",
                },
                {
                    "category": "gtc_2027",
                    "label": "GTC 2027 Joint Talk",
                    "projected_leads": 800,
                    "description": "Pipeline from joint keynote session at GTC 2027",
                },
            ],
            "currency": "USD",
            "as_of": "2026-03-30",
        })

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

    def _run_fallback():
        server = http.server.HTTPServer(("0.0.0.0", PORT), _Handler)
        print(f"[{SERVICE_NAME}] fallback http.server listening on port {PORT}")
        server.serve_forever()

if __name__ == "__main__":
    if _FASTAPI_AVAILABLE:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        _run_fallback()
