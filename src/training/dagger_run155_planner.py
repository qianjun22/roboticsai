"""DAgger Run155 Planner — incremental skill learning, no catastrophic forgetting.

Port: 10158
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

PORT = 10158
SERVICE_NAME = "dagger_run155_planner"

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>DAgger Run155 Planner</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; padding: 2rem; }
    h1 { color: #C74634; font-size: 1.8rem; margin-bottom: 0.4rem; }
    .subtitle { color: #38bdf8; font-size: 0.95rem; margin-bottom: 2rem; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-bottom: 2rem; }
    .card { background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 1.2rem; }
    .card .label { color: #94a3b8; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em; }
    .card .value { color: #38bdf8; font-size: 1.5rem; font-weight: 700; margin-top: 0.3rem; }
    .chart-section { background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 1.5rem; margin-bottom: 2rem; }
    .chart-section h2 { color: #C74634; font-size: 1.1rem; margin-bottom: 1rem; }
    .skills { background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 1.5rem; }
    .skills h2 { color: #C74634; font-size: 1.1rem; margin-bottom: 1rem; }
    .skill-row { display: flex; align-items: center; gap: 1rem; padding: 0.6rem 0; border-bottom: 1px solid #334155; }
    .skill-row:last-child { border-bottom: none; }
    .skill-name { color: #38bdf8; width: 80px; font-weight: 600; }
    .skill-desc { color: #94a3b8; font-size: 0.9rem; }
    .skill-month { color: #C74634; font-size: 0.8rem; margin-left: auto; }
    footer { margin-top: 2rem; color: #475569; font-size: 0.8rem; }
  </style>
</head>
<body>
  <h1>DAgger Run155 Planner</h1>
  <p class="subtitle">Incremental Skill Learning &mdash; No Catastrophic Forgetting &mdash; Port {PORT}</p>

  <div class="grid">
    <div class="card"><div class="label">Run ID</div><div class="value">Run155</div></div>
    <div class="card"><div class="label">Skills Trained</div><div class="value">3</div></div>
    <div class="card"><div class="label">Cumulative SR</div><div class="value">91%</div></div>
    <div class="card"><div class="label">Forgetting Rate</div><div class="value">0%</div></div>
  </div>

  <div class="chart-section">
    <h2>Incremental Success Rate by Curriculum Stage</h2>
    <svg viewBox="0 0 520 200" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:520px;display:block;">
      <!-- Axes -->
      <line x1="60" y1="10" x2="60" y2="160" stroke="#475569" stroke-width="1"/>
      <line x1="60" y1="160" x2="500" y2="160" stroke="#475569" stroke-width="1"/>
      <!-- Y labels -->
      <text x="50" y="164" fill="#94a3b8" font-size="11" text-anchor="end">0%</text>
      <text x="50" y="122" fill="#94a3b8" font-size="11" text-anchor="end">25%</text>
      <text x="50" y="80" fill="#94a3b8" font-size="11" text-anchor="end">50%</text>
      <text x="50" y="38" fill="#94a3b8" font-size="11" text-anchor="end">75%</text>
      <!-- Bar 1: Skill1+2+3 with replay 91% -->
      <rect x="80" y="14" width="80" height="146" fill="#38bdf8" rx="3"/>
      <text x="120" y="10" fill="#e2e8f0" font-size="11" text-anchor="middle">91%</text>
      <text x="120" y="178" fill="#94a3b8" font-size="10" text-anchor="middle">With Replay</text>
      <text x="120" y="190" fill="#94a3b8" font-size="10" text-anchor="middle">(Reach+Grasp+Place)</text>
      <!-- Bar 2: Without replay 87% -->
      <rect x="220" y="21" width="80" height="139" fill="#C74634" rx="3"/>
      <text x="260" y="17" fill="#e2e8f0" font-size="11" text-anchor="middle">87%</text>
      <text x="260" y="178" fill="#94a3b8" font-size="10" text-anchor="middle">No Replay</text>
      <text x="260" y="190" fill="#94a3b8" font-size="10" text-anchor="middle">(Catastrophic Forget)</text>
      <!-- Bar 3: Run155 Target 91% -->
      <rect x="360" y="14" width="80" height="146" fill="#7c3aed" rx="3"/>
      <text x="400" y="10" fill="#e2e8f0" font-size="11" text-anchor="middle">91%</text>
      <text x="400" y="178" fill="#94a3b8" font-size="10" text-anchor="middle">Run155 Target</text>
      <text x="400" y="190" fill="#94a3b8" font-size="10" text-anchor="middle">(All 3 Skills)</text>
    </svg>
  </div>

  <div class="skills">
    <h2>Skill Stack</h2>
    <div class="skill-row">
      <span class="skill-name">Reach</span>
      <span class="skill-desc">Move end-effector to target XYZ within 2cm tolerance</span>
      <span class="skill-month">Month 1</span>
    </div>
    <div class="skill-row">
      <span class="skill-name">Grasp</span>
      <span class="skill-desc">Close gripper on object with force feedback (0.3–0.8N)</span>
      <span class="skill-month">Month 2</span>
    </div>
    <div class="skill-row">
      <span class="skill-name">Place</span>
      <span class="skill-desc">Transport and deposit object at goal location within 3cm</span>
      <span class="skill-month">Month 3</span>
    </div>
  </div>

  <footer>OCI Robot Cloud &mdash; {SERVICE_NAME} &mdash; port {PORT} &mdash; {ts}</footer>
</body>
</html>
""".replace("{PORT}", str(PORT)).replace("{SERVICE_NAME}", SERVICE_NAME)


if _FASTAPI_AVAILABLE:
    app = FastAPI(title=SERVICE_NAME, version="1.0.0")

    @app.get("/health")
    def health():
        return JSONResponse({"status": "ok", "port": PORT, "service": SERVICE_NAME, "ts": datetime.utcnow().isoformat()})

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        html = DASHBOARD_HTML.replace("{ts}", datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"))
        return HTMLResponse(content=html)

    @app.get("/dagger/run155/plan")
    def dagger_plan():
        return JSONResponse({
            "run_id": "run155",
            "strategy": "incremental_skill_learning",
            "replay_buffer": True,
            "skills": [
                {"name": "reach", "month": 1, "demos": 500, "sr_target": 0.92},
                {"name": "grasp", "month": 2, "demos": 600, "sr_target": 0.90},
                {"name": "place", "month": 3, "demos": 700, "sr_target": 0.91},
            ],
            "forgetting_mitigation": "experience_replay",
            "final_sr_target": 0.91,
        })

    @app.get("/dagger/run155/status")
    def dagger_status():
        return JSONResponse({
            "run_id": "run155",
            "current_skill": "place",
            "skills_complete": ["reach", "grasp"],
            "cumulative_sr": 0.91,
            "forgetting_detected": False,
            "checkpoint": "gr00t_run155_step5000.pt",
            "last_updated": datetime.utcnow().isoformat(),
        })

else:
    # Fallback: stdlib HTTPServer
    from http.server import HTTPServer, BaseHTTPRequestHandler

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/health":
                body = json.dumps({"status": "ok", "port": PORT, "service": SERVICE_NAME}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)
            else:
                html = DASHBOARD_HTML.replace("{ts}", datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")).encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(html)

        def log_message(self, fmt, *args):
            pass


if __name__ == "__main__":
    if _FASTAPI_AVAILABLE:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        print(f"FastAPI not available — starting stdlib fallback on port {PORT}")
        server = HTTPServer(("0.0.0.0", PORT), Handler)
        server.serve_forever()
