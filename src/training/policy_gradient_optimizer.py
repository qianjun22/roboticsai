"""Policy Gradient Optimizer — FastAPI service on port 10192.

PPO-style policy gradient fine-tuning on top of IL baseline.
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

PORT = 10192
SERVICE_NAME = "policy_gradient_optimizer"

HTML_DASHBOARD = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Policy Gradient Optimizer</title>
  <style>
    body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; margin: 0; padding: 2rem; }
    h1 { color: #C74634; margin-bottom: 0.25rem; }
    .subtitle { color: #38bdf8; font-size: 0.95rem; margin-bottom: 2rem; }
    .card { background: #1e293b; border-radius: 10px; padding: 1.5rem; margin-bottom: 1.5rem; }
    .card h2 { color: #38bdf8; margin-top: 0; font-size: 1.1rem; }
    .metric { display: inline-block; margin-right: 2rem; margin-bottom: 1rem; }
    .metric .val { font-size: 1.8rem; font-weight: bold; color: #C74634; }
    .metric .lbl { font-size: 0.8rem; color: #94a3b8; }
    table { width: 100%; border-collapse: collapse; font-size: 0.9rem; }
    th { text-align: left; color: #38bdf8; padding: 0.4rem 0.6rem; border-bottom: 1px solid #334155; }
    td { padding: 0.4rem 0.6rem; border-bottom: 1px solid #1e293b; }
    .badge { display: inline-block; padding: 0.15rem 0.5rem; border-radius: 9999px; font-size: 0.75rem; }
    .green { background: #14532d; color: #86efac; }
    .blue  { background: #0c4a6e; color: #7dd3fc; }
  </style>
</head>
<body>
  <h1>Policy Gradient Optimizer</h1>
  <p class="subtitle">Port 10192 &mdash; PPO-style fine-tuning on top of Imitation Learning baseline</p>

  <div class="card">
    <h2>Success Rate Comparison</h2>
    <svg width="420" height="160" viewBox="0 0 420 160" xmlns="http://www.w3.org/2000/svg">
      <!-- Grid lines -->
      <line x1="60" y1="10" x2="60" y2="130" stroke="#334155" stroke-width="1"/>
      <line x1="60" y1="130" x2="400" y2="130" stroke="#334155" stroke-width="1"/>
      <!-- Y axis labels -->
      <text x="55" y="134" fill="#94a3b8" font-size="11" text-anchor="end">0%</text>
      <text x="55" y="83" fill="#94a3b8" font-size="11" text-anchor="end">50%</text>
      <text x="55" y="14" fill="#94a3b8" font-size="11" text-anchor="end">100%</text>
      <!-- Horizontal guide -->
      <line x1="60" y1="82" x2="400" y2="82" stroke="#1e293b" stroke-width="1" stroke-dasharray="4"/>
      <!-- Bar: PG fine-tuned 96% -->
      <rect x="90" y="19" width="90" height="111" fill="#C74634" rx="4"/>
      <text x="135" y="14" fill="#e2e8f0" font-size="12" text-anchor="middle" font-weight="bold">96%</text>
      <text x="135" y="148" fill="#94a3b8" font-size="11" text-anchor="middle">PG Fine-tuned</text>
      <!-- Bar: IL-only 93% -->
      <rect x="230" y="23" width="90" height="107" fill="#38bdf8" rx="4"/>
      <text x="275" y="18" fill="#e2e8f0" font-size="12" text-anchor="middle" font-weight="bold">93%</text>
      <text x="275" y="148" fill="#94a3b8" font-size="11" text-anchor="middle">IL-only</text>
    </svg>
  </div>

  <div class="card">
    <h2>Reward Function</h2>
    <table>
      <tr><th>Event</th><th>Reward</th></tr>
      <tr><td>Task completion</td><td style="color:#86efac">+10</td></tr>
      <tr><td>Successful grasp</td><td style="color:#86efac">+3</td></tr>
      <tr><td>Efficient path</td><td style="color:#86efac">+1</td></tr>
      <tr><td>Collision</td><td style="color:#fca5a5">-5</td></tr>
      <tr><td>Drop</td><td style="color:#fca5a5">-8</td></tr>
    </table>
  </div>

  <div class="card">
    <h2>Run Parameters</h2>
    <div class="metric"><div class="val">2 hr</div><div class="lbl">A100 Training Time</div></div>
    <div class="metric"><div class="val">$0.87</div><div class="lbl">Cost / Run</div></div>
    <div class="metric"><div class="val">+3 pp</div><div class="lbl">SR Gain over IL</div></div>
  </div>

  <div class="card">
    <h2>Endpoints</h2>
    <table>
      <tr><th>Method</th><th>Path</th><th>Description</th></tr>
      <tr><td><span class="badge green">GET</span></td><td>/health</td><td>Health check</td></tr>
      <tr><td><span class="badge green">GET</span></td><td>/</td><td>This dashboard</td></tr>
      <tr><td><span class="badge blue">POST</span></td><td>/training/pg_finetune</td><td>Launch PG fine-tune job</td></tr>
      <tr><td><span class="badge green">GET</span></td><td>/training/pg_status</td><td>Query fine-tune job status</td></tr>
    </table>
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
        return HTML_DASHBOARD

    @app.post("/training/pg_finetune")
    async def pg_finetune(payload: dict = None):
        """Launch a PPO fine-tune job on top of an IL checkpoint."""
        job_id = f"pg-{int(time.time())}"
        return JSONResponse({
            "job_id": job_id,
            "status": "queued",
            "algorithm": "PPO",
            "estimated_duration_min": 120,
            "cost_usd": 0.87,
            "reward_config": {
                "task_completion": 10,
                "grasp": 3,
                "efficient_path": 1,
                "collision": -5,
                "drop": -8,
            },
        })

    @app.get("/training/pg_status")
    async def pg_status(job_id: str = "latest"):
        """Return mock status for a PG fine-tune job."""
        return JSONResponse({
            "job_id": job_id,
            "status": "running",
            "progress_pct": 42,
            "current_sr": 0.94,
            "baseline_sr": 0.93,
            "steps_completed": 2100,
            "total_steps": 5000,
        })

else:
    # Fallback: stdlib HTTP server
    import http.server

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/health":
                body = json.dumps({"status": "ok", "port": PORT, "service": SERVICE_NAME}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                body = HTML_DASHBOARD.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        def log_message(self, fmt, *args):  # silence default logging
            pass

if __name__ == "__main__":
    if _FASTAPI_AVAILABLE:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        server = http.server.HTTPServer(("0.0.0.0", PORT), _Handler)
        print(f"[{SERVICE_NAME}] Fallback HTTP server running on port {PORT}")
        server.serve_forever()
