"""DAgger Run116 Planner — environment diversity training across 10 scene variants → generalize to 50.

Port: 10002
Cycle: 486B
"""

import json
import random
import math
from datetime import datetime

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import HTMLResponse, JSONResponse
    from pydantic import BaseModel
    import uvicorn
    _USE_FASTAPI = True
except ImportError:
    _USE_FASTAPI = False
    from http.server import BaseHTTPRequestHandler, HTTPServer
    from urllib.parse import urlparse, parse_qs

PORT = 10002
RUN_ID = "run116"
TRAIN_SCENES = 10
TEST_SCENES = 50
PROJECTED_SR = 89.0
SINGLE_SCENE_BASELINE = 71.0
GENERALIZATION_GAIN = round(PROJECTED_SR - SINGLE_SCENE_BASELINE, 1)

HTML_DASHBOARD = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>DAgger Run116 Planner — OCI Robot Cloud</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; min-height: 100vh; }
    header { background: #1e293b; border-bottom: 2px solid #C74634; padding: 18px 32px; display: flex; align-items: center; gap: 16px; }
    header h1 { font-size: 1.4rem; color: #f8fafc; font-weight: 700; }
    header .badge { background: #C74634; color: #fff; font-size: 0.75rem; padding: 3px 10px; border-radius: 12px; font-weight: 600; }
    .container { max-width: 1100px; margin: 0 auto; padding: 32px 24px; }
    .kpi-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; margin-bottom: 32px; }
    .kpi { background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 20px; }
    .kpi .label { font-size: 0.78rem; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 8px; }
    .kpi .value { font-size: 2rem; font-weight: 700; color: #38bdf8; }
    .kpi .value.red { color: #C74634; }
    .kpi .value.green { color: #4ade80; }
    .kpi .sub { font-size: 0.78rem; color: #64748b; margin-top: 4px; }
    .card { background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 24px; margin-bottom: 24px; }
    .card h2 { font-size: 1rem; color: #38bdf8; font-weight: 600; margin-bottom: 20px; text-transform: uppercase; letter-spacing: 0.06em; }
    svg text { font-family: 'Segoe UI', system-ui, sans-serif; }
    .footer { text-align: center; color: #334155; font-size: 0.75rem; padding: 24px 0; }
  </style>
</head>
<body>
  <header>
    <h1>DAgger Run116 Planner</h1>
    <span class="badge">Cycle 486B</span>
    <span class="badge" style="background:#0ea5e9">Port 10002</span>
  </header>
  <div class="container">
    <div class="kpi-row">
      <div class="kpi">
        <div class="label">Diverse Training SR</div>
        <div class="value green">89%</div>
        <div class="sub">10 scene variants</div>
      </div>
      <div class="kpi">
        <div class="label">Single-Scene Baseline</div>
        <div class="value red">71%</div>
        <div class="sub">1 scene variant</div>
      </div>
      <div class="kpi">
        <div class="label">Generalization Gain</div>
        <div class="value">+18%</div>
        <div class="sub">across 50 test scenes</div>
      </div>
      <div class="kpi">
        <div class="label">Test Scenes</div>
        <div class="value">50</div>
        <div class="sub">from 10 train variants</div>
      </div>
    </div>

    <div class="card">
      <h2>Success Rate: Diverse vs Single-Scene Training</h2>
      <svg width="100%" viewBox="0 0 640 260" xmlns="http://www.w3.org/2000/svg">
        <!-- Y axis -->
        <line x1="60" y1="20" x2="60" y2="210" stroke="#334155" stroke-width="1"/>
        <!-- X axis -->
        <line x1="60" y1="210" x2="600" y2="210" stroke="#334155" stroke-width="1"/>
        <!-- Y gridlines & labels -->
        <line x1="60" y1="20" x2="600" y2="20" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,4"/>
        <text x="50" y="24" text-anchor="end" fill="#64748b" font-size="11">100%</text>
        <line x1="60" y1="58" x2="600" y2="58" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,4"/>
        <text x="50" y="62" text-anchor="end" fill="#64748b" font-size="11">80%</text>
        <line x1="60" y1="96" x2="600" y2="96" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,4"/>
        <text x="50" y="100" text-anchor="end" fill="#64748b" font-size="11">60%</text>
        <line x1="60" y1="134" x2="600" y2="134" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,4"/>
        <text x="50" y="138" text-anchor="end" fill="#64748b" font-size="11">40%</text>
        <line x1="60" y1="172" x2="600" y2="172" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,4"/>
        <text x="50" y="176" text-anchor="end" fill="#64748b" font-size="11">20%</text>
        <!-- Bar: Diverse Training 89% => height = 89/100*190 = 169.1 => y=210-169=41 -->
        <rect x="140" y="41" width="140" height="169" fill="#38bdf8" rx="4"/>
        <text x="210" y="35" text-anchor="middle" fill="#38bdf8" font-size="13" font-weight="700">89%</text>
        <text x="210" y="230" text-anchor="middle" fill="#94a3b8" font-size="12">Diverse (10 scenes)</text>
        <!-- Bar: Single-Scene 71% => height=71/100*190=134.9 => y=210-135=75 -->
        <rect x="360" y="75" width="140" height="135" fill="#C74634" rx="4"/>
        <text x="430" y="69" text-anchor="middle" fill="#C74634" font-size="13" font-weight="700">71%</text>
        <text x="430" y="230" text-anchor="middle" fill="#94a3b8" font-size="12">Single-Scene</text>
        <!-- Gain annotation arrow -->
        <line x1="280" y1="55" x2="360" y2="88" stroke="#4ade80" stroke-width="1.5" stroke-dasharray="4,3"/>
        <text x="320" y="65" text-anchor="middle" fill="#4ade80" font-size="11" font-weight="600">+18% gain</text>
      </svg>
    </div>

    <div class="card">
      <h2>Scene Diversity Training Progress (Iterations 1–10)</h2>
      <svg width="100%" viewBox="0 0 640 220" xmlns="http://www.w3.org/2000/svg">
        <line x1="50" y1="10" x2="50" y2="180" stroke="#334155" stroke-width="1"/>
        <line x1="50" y1="180" x2="620" y2="180" stroke="#334155" stroke-width="1"/>
        <!-- SR line: 10 iterations, SR starts at 71 and climbs to 89 -->
        <!-- x positions: 50 + i*(570/9) for i=0..9; y: 180 - sr/100*170 -->
        <!-- sr values: 71,73,75,77,79,81,83,85,87,89 -->
        <polyline points="
          50,59
          113,55
          176,51
          239,47
          302,43
          365,39
          428,35
          491,31
          554,27
          617,24
        " fill="none" stroke="#38bdf8" stroke-width="2.5" stroke-linejoin="round"/>
        <!-- Dots -->
        <circle cx="50" cy="59" r="4" fill="#38bdf8"/>
        <circle cx="617" cy="24" r="5" fill="#4ade80"/>
        <!-- baseline -->
        <line x1="50" y1="59" x2="620" y2="59" stroke="#C74634" stroke-width="1.5" stroke-dasharray="5,3"/>
        <text x="625" y="63" fill="#C74634" font-size="10">71%</text>
        <text x="625" y="28" fill="#4ade80" font-size="10">89%</text>
        <!-- X labels -->
        <text x="50" y="196" text-anchor="middle" fill="#64748b" font-size="10">1</text>
        <text x="617" y="196" text-anchor="middle" fill="#64748b" font-size="10">10</text>
        <text x="335" y="210" text-anchor="middle" fill="#64748b" font-size="11">DAgger Iteration</text>
        <text x="10" y="100" fill="#64748b" font-size="11" transform="rotate(-90,10,100)">Success Rate</text>
      </svg>
    </div>
  </div>
  <div class="footer">OCI Robot Cloud &mdash; DAgger Run116 Planner &mdash; Port 10002</div>
</body>
</html>
"""


def _compute_plan(iteration: int, n_scenes: int) -> dict:
    """Simulate diverse-training SR vs single-scene SR given iteration + scene count."""
    random.seed(iteration * 31 + n_scenes * 7)
    scene_bonus = min((n_scenes - 1) * 2.0, 36.0)  # cap at 36 pp gain
    diverse_sr = round(min(SINGLE_SCENE_BASELINE + scene_bonus + random.uniform(-0.5, 0.5), 99.0), 2)
    single_sr = round(SINGLE_SCENE_BASELINE + random.uniform(-1.0, 1.0), 2)
    gain = round(diverse_sr - single_sr, 2)
    return {
        "scene_variants": n_scenes,
        "diverse_sr": diverse_sr,
        "single_scene_sr": single_sr,
        "generalization_gain_pct": gain,
    }


if _USE_FASTAPI:
    app = FastAPI(
        title="DAgger Run116 Planner",
        description="Environment diversity training across 10 scene variants — generalize to 50",
        version="1.0.0",
    )

    class PlanRequest(BaseModel):
        iteration: int = 1
        n_scenes: int = 10

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return HTML_DASHBOARD

    @app.get("/health")
    def health():
        return {
            "status": "ok",
            "service": "dagger_run116_planner",
            "port": PORT,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

    @app.post("/dagger/run116/plan")
    def plan(req: PlanRequest):
        if req.iteration < 1 or req.n_scenes < 1:
            raise HTTPException(status_code=422, detail="iteration and n_scenes must be >= 1")
        return _compute_plan(req.iteration, req.n_scenes)

    @app.get("/dagger/run116/status")
    def status():
        return {
            "run_id": RUN_ID,
            "train_scenes": TRAIN_SCENES,
            "test_scenes": TEST_SCENES,
            "projected_sr": PROJECTED_SR,
            "single_scene_baseline": SINGLE_SCENE_BASELINE,
            "generalization_gain_pct": GENERALIZATION_GAIN,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

else:
    # stdlib HTTPServer fallback
    class _Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):  # suppress default logging
            pass

        def _send(self, code, content_type, body):
            encoded = body.encode() if isinstance(body, str) else body
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def do_GET(self):
            path = urlparse(self.path).path
            if path == "/":
                self._send(200, "text/html", HTML_DASHBOARD)
            elif path == "/health":
                body = json.dumps({"status": "ok", "service": "dagger_run116_planner", "port": PORT})
                self._send(200, "application/json", body)
            elif path == "/dagger/run116/status":
                body = json.dumps({
                    "run_id": RUN_ID,
                    "train_scenes": TRAIN_SCENES,
                    "test_scenes": TEST_SCENES,
                    "projected_sr": PROJECTED_SR,
                    "single_scene_baseline": SINGLE_SCENE_BASELINE,
                    "generalization_gain_pct": GENERALIZATION_GAIN,
                })
                self._send(200, "application/json", body)
            else:
                self._send(404, "application/json", json.dumps({"detail": "not found"}))

        def do_POST(self):
            path = urlparse(self.path).path
            if path == "/dagger/run116/plan":
                length = int(self.headers.get("Content-Length", 0))
                raw = self.rfile.read(length)
                try:
                    data = json.loads(raw)
                    result = _compute_plan(int(data.get("iteration", 1)), int(data.get("n_scenes", 10)))
                    self._send(200, "application/json", json.dumps(result))
                except Exception as exc:
                    self._send(422, "application/json", json.dumps({"detail": str(exc)}))
            else:
                self._send(404, "application/json", json.dumps({"detail": "not found"}))


if __name__ == "__main__":
    if _USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        print(f"FastAPI not available — starting stdlib HTTPServer on port {PORT}")
        server = HTTPServer(("0.0.0.0", PORT), _Handler)
        server.serve_forever()
