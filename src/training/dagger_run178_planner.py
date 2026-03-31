"""DAgger Run178 Planner — Hindsight Experience Replay DAgger (port 10250)"""

PORT = 10250
SERVICE_NAME = "dagger_run178_planner"

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    _FASTAPI_AVAILABLE = True
except ImportError:
    _FASTAPI_AVAILABLE = False

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>DAgger Run178 Planner</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; padding: 2rem; }
    h1 { color: #C74634; font-size: 1.75rem; margin-bottom: 0.5rem; }
    .subtitle { color: #38bdf8; font-size: 1rem; margin-bottom: 2rem; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 1.25rem; margin-bottom: 2.5rem; }
    .card { background: #1e293b; border: 1px solid #334155; border-radius: 0.75rem; padding: 1.25rem; }
    .card h3 { color: #38bdf8; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.5rem; }
    .card .value { font-size: 2rem; font-weight: 700; color: #f1f5f9; }
    .card .label { font-size: 0.75rem; color: #94a3b8; margin-top: 0.25rem; }
    .chart-section { background: #1e293b; border: 1px solid #334155; border-radius: 0.75rem; padding: 1.5rem; margin-bottom: 2rem; }
    .chart-section h2 { color: #C74634; margin-bottom: 1rem; font-size: 1.1rem; }
    .endpoints { background: #1e293b; border: 1px solid #334155; border-radius: 0.75rem; padding: 1.5rem; }
    .endpoints h2 { color: #C74634; margin-bottom: 1rem; font-size: 1.1rem; }
    .ep { display: flex; align-items: center; gap: 0.75rem; padding: 0.5rem 0; border-bottom: 1px solid #334155; }
    .ep:last-child { border-bottom: none; }
    .method { background: #0c4a6e; color: #38bdf8; font-size: 0.75rem; font-weight: 700; padding: 0.2rem 0.5rem; border-radius: 0.25rem; min-width: 44px; text-align: center; }
    .path { color: #e2e8f0; font-family: monospace; font-size: 0.9rem; }
    .desc { color: #94a3b8; font-size: 0.8rem; margin-left: auto; }
  </style>
</head>
<body>
  <h1>DAgger Run178 Planner</h1>
  <p class="subtitle">Hindsight Experience Replay DAgger &mdash; Port 10250 &mdash; OCI Robot Cloud</p>

  <div class="grid">
    <div class="card">
      <h3>HER DAgger SR</h3>
      <div class="value">94%</div>
      <div class="label">Success rate</div>
    </div>
    <div class="card">
      <h3>Standard DAgger SR</h3>
      <div class="value">90%</div>
      <div class="label">Baseline success rate</div>
    </div>
    <div class="card">
      <h3>Data Efficiency</h3>
      <div class="value">1.8x</div>
      <div class="label">vs standard DAgger</div>
    </div>
    <div class="card">
      <h3>Reward Type</h3>
      <div class="value" style="font-size:1.1rem; padding-top:0.4rem;">Sparse</div>
      <div class="label">Failures relabeled as intermediate goals</div>
    </div>
  </div>

  <div class="chart-section">
    <h2>Success Rate: HER DAgger vs Standard DAgger</h2>
    <svg viewBox="0 0 500 200" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:500px;display:block;">
      <!-- Y-axis -->
      <line x1="60" y1="10" x2="60" y2="160" stroke="#334155" stroke-width="1"/>
      <!-- X-axis -->
      <line x1="60" y1="160" x2="460" y2="160" stroke="#334155" stroke-width="1"/>
      <!-- Y labels -->
      <text x="50" y="165" fill="#94a3b8" font-size="11" text-anchor="end">0%</text>
      <text x="50" y="115" fill="#94a3b8" font-size="11" text-anchor="end">50%</text>
      <text x="50" y="65" fill="#94a3b8" font-size="11" text-anchor="end">100%</text>
      <!-- Grid -->
      <line x1="60" y1="110" x2="460" y2="110" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,4"/>
      <line x1="60" y1="60" x2="460" y2="60" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,4"/>
      <!-- HER DAgger bar: 94% => height = 94/100 * 150 = 141 -->
      <rect x="110" y="19" width="100" height="141" fill="#C74634" rx="4"/>
      <text x="160" y="14" fill="#f1f5f9" font-size="13" font-weight="bold" text-anchor="middle">94%</text>
      <text x="160" y="180" fill="#94a3b8" font-size="11" text-anchor="middle">HER DAgger</text>
      <!-- Standard bar: 90% => height = 135 -->
      <rect x="280" y="25" width="100" height="135" fill="#38bdf8" rx="4"/>
      <text x="330" y="20" fill="#f1f5f9" font-size="13" font-weight="bold" text-anchor="middle">90%</text>
      <text x="330" y="180" fill="#94a3b8" font-size="11" text-anchor="middle">Standard DAgger</text>
    </svg>
  </div>

  <div class="endpoints">
    <h2>API Endpoints</h2>
    <div class="ep"><span class="method">GET</span><span class="path">/health</span><span class="desc">Service health check</span></div>
    <div class="ep"><span class="method">GET</span><span class="path">/</span><span class="desc">This dashboard</span></div>
    <div class="ep"><span class="method">GET</span><span class="path">/dagger/run178/plan</span><span class="desc">HER DAgger plan for run178</span></div>
    <div class="ep"><span class="method">GET</span><span class="path">/dagger/run178/status</span><span class="desc">Run178 training status</span></div>
  </div>
</body>
</html>
"""

if _FASTAPI_AVAILABLE:
    app = FastAPI(title=SERVICE_NAME, version="1.0.0")

    @app.get("/health")
    async def health():
        return JSONResponse({"status": "ok", "port": PORT, "service": SERVICE_NAME})

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return HTMLResponse(content=DASHBOARD_HTML)

    @app.get("/dagger/run178/plan")
    async def dagger_plan():
        return JSONResponse({
            "run": 178,
            "algorithm": "HER-DAgger",
            "strategy": "Hindsight Experience Replay",
            "relabel_failures_as_intermediate_goals": True,
            "data_efficiency_multiplier": 1.8,
            "reward_type": "sparse",
            "her_dagger_sr": 0.94,
            "standard_dagger_sr": 0.90,
            "plan_steps": [
                "collect_rollout",
                "relabel_failed_episodes",
                "compute_her_targets",
                "update_policy",
                "evaluate"
            ]
        })

    @app.get("/dagger/run178/status")
    async def dagger_status():
        return JSONResponse({
            "run": 178,
            "status": "complete",
            "episodes_collected": 5000,
            "episodes_relabeled": 1820,
            "current_sr": 0.94,
            "baseline_sr": 0.90,
            "data_efficiency": "1.8x",
            "convergence_step": 4200
        })

else:
    import http.server
    import json
    import urllib.parse

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            path = urllib.parse.urlparse(self.path).path
            if path == "/health":
                body = json.dumps({"status": "ok", "port": PORT, "service": SERVICE_NAME}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
            elif path == "/dagger/run178/plan":
                body = json.dumps({"run": 178, "algorithm": "HER-DAgger", "her_dagger_sr": 0.94}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
            elif path == "/dagger/run178/status":
                body = json.dumps({"run": 178, "status": "complete", "current_sr": 0.94}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
            else:
                body = DASHBOARD_HTML.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            pass

if __name__ == "__main__":
    if _FASTAPI_AVAILABLE:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        server = http.server.HTTPServer(("0.0.0.0", PORT), _Handler)
        print(f"[{SERVICE_NAME}] Fallback HTTP server on port {PORT}")
        server.serve_forever()
