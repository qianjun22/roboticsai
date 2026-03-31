"""growth_hacking_engine.py — FastAPI service port 10185
Systematic growth experiments: channel testing, conversion optimization, viral loops.
Cycle-532A | OCI Robot Cloud
"""

import json
import time
from typing import Any, Dict, List, Optional

PORT = 10185
SERVICE_NAME = "growth_hacking_engine"

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    _FASTAPI_AVAILABLE = True
except ImportError:
    _FASTAPI_AVAILABLE = False

# ---------------------------------------------------------------------------
# In-memory experiment store (mock)
# ---------------------------------------------------------------------------
_EXPERIMENTS: List[Dict[str, Any]] = [
    {"id": "exp_001", "name": "NVIDIA referral incentive", "channel": "nvidia_referral", "status": "active", "roi": 87500},
    {"id": "exp_002", "name": "GitHub star → trial flow", "channel": "github", "status": "active", "roi": 42000},
    {"id": "exp_003", "name": "AI World viral demo booth", "channel": "conference", "status": "complete", "roi": 57500},
    {"id": "exp_004", "name": "Inbound SEO / docs", "channel": "inbound", "status": "active", "roi": 105000},
]

if _FASTAPI_AVAILABLE:
    app = FastAPI(title=SERVICE_NAME, version="1.0.0")

    @app.get("/health")
    def health() -> JSONResponse:
        return JSONResponse({
            "status": "ok",
            "port": PORT,
            "service": SERVICE_NAME,
            "timestamp": time.time()
        })

    @app.get("/", response_class=HTMLResponse)
    def dashboard() -> str:
        return _render_dashboard()

    @app.get("/growth/experiments")
    def list_experiments() -> JSONResponse:
        """Return all growth experiments with current ROI estimates."""
        return JSONResponse({
            "experiments": _EXPERIMENTS,
            "total_experiments": len(_EXPERIMENTS),
            "active": sum(1 for e in _EXPERIMENTS if e["status"] == "active"),
            "mock": True
        })

    @app.post("/growth/launch_experiment")
    def launch_experiment(payload: Optional[Dict[str, Any]] = None) -> JSONResponse:
        """Stub: register and launch a new growth experiment."""
        exp_id = f"exp_{int(time.time())}"
        name = (payload or {}).get("name", "unnamed experiment")
        channel = (payload or {}).get("channel", "unknown")
        new_exp = {
            "id": exp_id,
            "name": name,
            "channel": channel,
            "status": "launched",
            "roi": 0,
            "mock": True
        }
        _EXPERIMENTS.append(new_exp)
        return JSONResponse({"status": "launched", "experiment": new_exp})


def _render_dashboard() -> str:
    return """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Growth Hacking Engine — Port 10185</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; padding: 2rem; }
    h1 { color: #C74634; font-size: 1.8rem; margin-bottom: 0.4rem; }
    .subtitle { color: #38bdf8; font-size: 1rem; margin-bottom: 2rem; }
    .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; }
    .card { background: #1e293b; border-radius: 12px; padding: 1.5rem; }
    .card h2 { color: #38bdf8; font-size: 1rem; margin-bottom: 1rem; text-transform: uppercase; letter-spacing: 0.05em; }
    .metric { display: flex; justify-content: space-between; padding: 0.4rem 0; border-bottom: 1px solid #334155; }
    .metric:last-child { border-bottom: none; }
    .metric .label { color: #94a3b8; }
    .metric .value { color: #f1f5f9; font-weight: 600; }
    .badge { display: inline-block; background: #C74634; color: #fff; border-radius: 6px; padding: 0.2rem 0.6rem; font-size: 0.8rem; font-weight: 700; margin-left: 0.4rem; }
    svg text { font-family: 'Segoe UI', sans-serif; }
  </style>
</head>
<body>
  <h1>Growth Hacking Engine <span class="badge">:10185</span></h1>
  <p class="subtitle">Channel testing, conversion optimization, viral loops — OCI Robot Cloud GTM</p>

  <div class="grid">
    <div class="card">
      <h2>ROI by Channel</h2>
      <svg width="100%" viewBox="0 0 320 200" xmlns="http://www.w3.org/2000/svg">
        <!-- Y-axis labels (in $K) -->
        <text x="28" y="20" fill="#94a3b8" font-size="10">$120K</text>
        <text x="28" y="55" fill="#94a3b8" font-size="10">$90K</text>
        <text x="28" y="90" fill="#94a3b8" font-size="10">$60K</text>
        <text x="28" y="125" fill="#94a3b8" font-size="10">$30K</text>
        <!-- Grid lines -->
        <line x1="55" y1="15" x2="310" y2="15" stroke="#334155" stroke-width="1"/>
        <line x1="55" y1="50" x2="310" y2="50" stroke="#334155" stroke-width="1"/>
        <line x1="55" y1="85" x2="310" y2="85" stroke="#334155" stroke-width="1"/>
        <line x1="55" y1="120" x2="310" y2="120" stroke="#334155" stroke-width="1"/>
        <!-- Bar: Inbound $105K (105/120 = 87.5% of 120px height = 105px) -->
        <rect x="60" y="20" width="55" height="105" fill="#C74634" rx="4"/>
        <text x="87" y="15" fill="#f1f5f9" font-size="10" text-anchor="middle" font-weight="700">$105K</text>
        <text x="87" y="145" fill="#94a3b8" font-size="9" text-anchor="middle">Inbound</text>
        <!-- Bar: NVIDIA referral $87.5K (87.5/120 = 87.5px) -->
        <rect x="130" y="37" width="55" height="88" fill="#38bdf8" rx="4"/>
        <text x="157" y="32" fill="#f1f5f9" font-size="10" text-anchor="middle" font-weight="700">$87.5K</text>
        <text x="157" y="145" fill="#94a3b8" font-size="9" text-anchor="middle">NVIDIA Ref.</text>
        <!-- Bar: Conference $57.5K (57.5/120 = 57.5px) -->
        <rect x="200" y="67" width="55" height="58" fill="#7c3aed" rx="4"/>
        <text x="227" y="62" fill="#f1f5f9" font-size="10" text-anchor="middle" font-weight="700">$57.5K</text>
        <text x="227" y="145" fill="#94a3b8" font-size="9" text-anchor="middle">Conference</text>
        <!-- Caption -->
        <text x="160" y="170" fill="#38bdf8" font-size="10" text-anchor="middle">Pipeline ROI — Q1 2026 estimates</text>
      </svg>
    </div>

    <div class="card">
      <h2>Growth Loops</h2>
      <div class="metric"><span class="label">NVIDIA referral</span><span class="value">$87.5K pipeline</span></div>
      <div class="metric"><span class="label">GitHub star → trial</span><span class="value">$42K pipeline</span></div>
      <div class="metric"><span class="label">AI World viral demo</span><span class="value">$57.5K pipeline</span></div>
      <div class="metric"><span class="label">Conference → inbound</span><span class="value">Compounding</span></div>
      <div class="metric"><span class="label">Total pipeline</span><span class="value">$292K+</span></div>
    </div>

    <div class="card">
      <h2>Endpoints</h2>
      <div class="metric"><span class="label">GET /health</span><span class="value">Service health</span></div>
      <div class="metric"><span class="label">GET /</span><span class="value">This dashboard</span></div>
      <div class="metric"><span class="label">GET /growth/experiments</span><span class="value">List experiments</span></div>
      <div class="metric"><span class="label">POST /growth/launch_experiment</span><span class="value">Launch new exp.</span></div>
    </div>

    <div class="card">
      <h2>Service Info</h2>
      <div class="metric"><span class="label">Service</span><span class="value">growth_hacking_engine</span></div>
      <div class="metric"><span class="label">Port</span><span class="value">10185</span></div>
      <div class="metric"><span class="label">Cycle</span><span class="value">532A</span></div>
      <div class="metric"><span class="label">Project</span><span class="value">OCI Robot Cloud GTM</span></div>
    </div>
  </div>
</body>
</html>
"""


if not _FASTAPI_AVAILABLE:
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
                body = _render_dashboard().encode()
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
        with socketserver.TCPServer(("", PORT), _Handler) as httpd:
            print(f"[{SERVICE_NAME}] Fallback HTTP server running on port {PORT}")
            httpd.serve_forever()
