"""DAgger Run157 Planner — continual evaluation DAgger with early stopping.

Port: 10166
Protocol: 50 corrections → 20-episode eval → SR check, stop at SR=95%
"""

PORT = 10166
SERVICE_NAME = "dagger_run157_planner"

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    _has_fastapi = True
except ImportError:
    _has_fastapi = False

if _has_fastapi:
    app = FastAPI(title=SERVICE_NAME, version="1.0.0")

    @app.get("/health")
    def health():
        return JSONResponse({"status": "ok", "port": PORT, "service": SERVICE_NAME})

    @app.get("/dagger/run157/plan")
    def dagger_run157_plan():
        return JSONResponse({
            "run": "run157",
            "type": "continual_evaluation_dagger",
            "protocol": {
                "corrections_per_round": 50,
                "eval_episodes_per_round": 20,
                "sr_target": 0.95,
                "max_rounds": 10,
                "early_stopping": True
            },
            "efficiency": {
                "corrections_with_early_stop": 280,
                "corrections_without_early_stop": 350,
                "savings_pct": 20
            },
            "status": "planned"
        })

    @app.get("/dagger/run157/status")
    def dagger_run157_status():
        return JSONResponse({
            "run": "run157",
            "current_round": 0,
            "corrections_so_far": 0,
            "latest_sr": None,
            "early_stop_triggered": False,
            "state": "not_started"
        })

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        html = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>DAgger Run157 Planner</title>
  <style>
    body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; margin: 0; padding: 2rem; }
    h1 { color: #C74634; font-size: 1.8rem; margin-bottom: 0.25rem; }
    .subtitle { color: #38bdf8; font-size: 0.95rem; margin-bottom: 2rem; }
    .card { background: #1e293b; border-radius: 10px; padding: 1.5rem; margin-bottom: 1.5rem; }
    .card h2 { color: #38bdf8; font-size: 1.1rem; margin-top: 0; }
    .badge { display: inline-block; background: #C74634; color: #fff; border-radius: 4px; padding: 2px 10px; font-size: 0.8rem; margin-left: 0.5rem; }
    .label { fill: #94a3b8; font-size: 12px; }
    .bar-label { fill: #e2e8f0; font-size: 11px; font-weight: bold; }
    .axis { stroke: #334155; }
    table { width: 100%; border-collapse: collapse; }
    th { color: #38bdf8; text-align: left; padding: 0.4rem 0.6rem; border-bottom: 1px solid #334155; }
    td { padding: 0.4rem 0.6rem; border-bottom: 1px solid #1e293b; color: #cbd5e1; }
  </style>
</head>
<body>
  <h1>DAgger Run157 Planner <span class="badge">port 10166</span></h1>
  <p class="subtitle">Continual Evaluation DAgger — Early Stopping at SR=95%</p>

  <div class="card">
    <h2>Early Stopping Efficiency</h2>
    <svg width="480" height="180" viewBox="0 0 480 180" xmlns="http://www.w3.org/2000/svg">
      <!-- Y axis -->
      <line x1="60" y1="20" x2="60" y2="140" class="axis" stroke="#334155" stroke-width="1"/>
      <!-- X axis -->
      <line x1="60" y1="140" x2="440" y2="140" class="axis" stroke="#334155" stroke-width="1"/>

      <!-- Bar: with early stopping (280 corrections) -->
      <!-- max = 350, bar width area = 360px -->
      <!-- 280/350 * 360 = 288px -->
      <rect x="60" y="50" width="288" height="36" fill="#38bdf8" rx="4"/>
      <text x="356" y="73" class="bar-label">280 corrections (early stop)</text>

      <!-- Bar: without early stopping (350 corrections) -->
      <!-- 350/350 * 360 = 360px -->
      <rect x="60" y="97" width="360" height="36" fill="#C74634" rx="4"/>
      <text x="428" y="120" class="bar-label">350</text>

      <!-- Y labels -->
      <text x="52" y="73" text-anchor="end" class="label">w/ stop</text>
      <text x="52" y="120" text-anchor="end" class="label">w/o stop</text>

      <!-- Title -->
      <text x="240" y="165" text-anchor="middle" class="label">Corrections to Reach SR=95% | 20% savings</text>
    </svg>
  </div>

  <div class="card">
    <h2>Protocol</h2>
    <table>
      <tr><th>Step</th><th>Action</th><th>Detail</th></tr>
      <tr><td>1</td><td>Collect corrections</td><td>50 human / scripted corrections</td></tr>
      <tr><td>2</td><td>Fine-tune policy</td><td>DAgger gradient update</td></tr>
      <tr><td>3</td><td>Evaluate</td><td>20-episode rollout, measure SR</td></tr>
      <tr><td>4</td><td>Check SR target</td><td>Stop if SR &ge; 95%, else repeat</td></tr>
      <tr><td>—</td><td>Max rounds</td><td>10 rounds (500 corrections max)</td></tr>
    </table>
  </div>

  <div class="card">
    <h2>Endpoints</h2>
    <table>
      <tr><th>Method</th><th>Path</th><th>Description</th></tr>
      <tr><td>GET</td><td>/health</td><td>Health check</td></tr>
      <tr><td>GET</td><td>/dagger/run157/plan</td><td>Full run157 plan + efficiency data</td></tr>
      <tr><td>GET</td><td>/dagger/run157/status</td><td>Live run state and SR</td></tr>
      <tr><td>GET</td><td>/</td><td>This dashboard</td></tr>
    </table>
  </div>
</body>
</html>
"""
        return HTMLResponse(content=html)

else:
    # Fallback: stdlib HTTP server
    import http.server
    import json

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/health":
                body = json.dumps({"status": "ok", "port": PORT, "service": SERVICE_NAME}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(b"DAgger Run157 Planner — install fastapi for full UI")

        def log_message(self, fmt, *args):
            pass

    def _serve():
        server = http.server.HTTPServer(("0.0.0.0", PORT), _Handler)
        server.serve_forever()

if __name__ == "__main__":
    if _has_fastapi:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        _serve()
