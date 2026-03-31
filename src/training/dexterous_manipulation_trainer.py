"""Dexterous Manipulation Trainer — port 10044

Multi-finger dexterous manipulation service: regrasping, rotation,
fingertip force control, and fragile object handling.
"""

import json
import math
import random
import time
from datetime import datetime

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import HTMLResponse, JSONResponse
    from pydantic import BaseModel
    import uvicorn
    _FASTAPI = True
except ImportError:
    _FASTAPI = False
    from http.server import BaseHTTPRequestHandler, HTTPServer
    from urllib.parse import urlparse

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
PORT = 10044
SERVICE_NAME = "dexterous_manipulation_trainer"
VERSION = "1.0.0"

SUPPORTED_TASKS = ["screw_insert", "tool_handoff", "card_dealing", "fragile_handling"]
SR_BY_TASK = {
    "screw_insert": 79,
    "tool_handoff": 83,
    "card_dealing": 71,
    "fragile_handling": 85,
}
VS_STANDARD_GRASP = 91  # standard grasp SR % (simpler tasks)

# ---------------------------------------------------------------------------
# HTML Dashboard
# ---------------------------------------------------------------------------
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Dexterous Manipulation Trainer — OCI Robot Cloud</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; min-height: 100vh; }
    header { background: #1e293b; border-bottom: 2px solid #C74634; padding: 1.2rem 2rem;
             display: flex; align-items: center; gap: 1rem; }
    header h1 { font-size: 1.4rem; font-weight: 700; color: #f8fafc; }
    header span.badge { background: #C74634; color: #fff; font-size: 0.72rem;
                        padding: 0.2rem 0.6rem; border-radius: 999px; font-weight: 600; }
    .subtitle { color: #94a3b8; font-size: 0.82rem; margin-top: 0.2rem; }
    main { max-width: 1100px; margin: 2rem auto; padding: 0 1.5rem; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 1.2rem; margin-bottom: 2rem; }
    .card { background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 1.4rem; }
    .card .label { font-size: 0.75rem; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 0.5rem; }
    .card .value { font-size: 2rem; font-weight: 700; color: #38bdf8; }
    .card .value.red { color: #C74634; }
    .card .value.green { color: #4ade80; }
    .card .sub { font-size: 0.8rem; color: #64748b; margin-top: 0.3rem; }
    section.chart-section { background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 1.6rem; margin-bottom: 2rem; }
    section.chart-section h2 { font-size: 1rem; font-weight: 600; color: #f1f5f9; margin-bottom: 1.2rem; }
    .bar-label { font-size: 0.78rem; fill: #94a3b8; }
    .bar-value { font-size: 0.82rem; fill: #e2e8f0; font-weight: 600; }
    .axis-line { stroke: #334155; stroke-width: 1; }
    table { width: 100%; border-collapse: collapse; }
    thead th { background: #0f172a; color: #94a3b8; font-size: 0.75rem; text-transform: uppercase;
               letter-spacing: 0.05em; padding: 0.7rem 1rem; text-align: left; }
    tbody tr { border-top: 1px solid #334155; }
    tbody td { padding: 0.8rem 1rem; font-size: 0.88rem; }
    tbody tr:hover td { background: #0f172a44; }
    .pill { display: inline-block; padding: 0.15rem 0.55rem; border-radius: 999px; font-size: 0.72rem; font-weight: 600; }
    .pill.blue { background: #0c4a6e; color: #38bdf8; }
    .pill.red { background: #450a0a; color: #f87171; }
    footer { text-align: center; color: #475569; font-size: 0.75rem; padding: 2rem; }
  </style>
</head>
<body>
<header>
  <div>
    <h1>Dexterous Manipulation Trainer <span class="badge">port 10044</span></h1>
    <div class="subtitle">Multi-finger regrasping · rotation · fingertip force control</div>
  </div>
</header>
<main>
  <div class="grid">
    <div class="card">
      <div class="label">Dexterous SR (avg)</div>
      <div class="value">79%</div>
      <div class="sub">across 4 hard tasks</div>
    </div>
    <div class="card">
      <div class="label">Standard Grasp SR</div>
      <div class="value red">91%</div>
      <div class="sub">simpler pick-and-place only</div>
    </div>
    <div class="card">
      <div class="label">Dexterous Task Types</div>
      <div class="value green">4</div>
      <div class="sub">screw · handoff · cards · fragile</div>
    </div>
    <div class="card">
      <div class="label">Best Use Case</div>
      <div class="value" style="font-size:1.1rem; color:#38bdf8; margin-top:0.4rem;">Fragile Object<br>Handling</div>
      <div class="sub">85% SR — glassware, sensors</div>
    </div>
  </div>

  <section class="chart-section">
    <h2>Success Rate by Dexterous Task Type</h2>
    <svg viewBox="0 0 700 240" xmlns="http://www.w3.org/2000/svg" width="100%">
      <!-- axes -->
      <line x1="90" y1="20" x2="90" y2="190" class="axis-line" />
      <line x1="90" y1="190" x2="680" y2="190" class="axis-line" />
      <!-- y-axis labels -->
      <text x="82" y="194" text-anchor="end" class="bar-label">0%</text>
      <text x="82" y="147" text-anchor="end" class="bar-label">25%</text>
      <text x="82" y="100" text-anchor="end" class="bar-label">50%</text>
      <text x="82" y="53" text-anchor="end" class="bar-label">75%</text>
      <text x="82" y="24" text-anchor="end" class="bar-label">100%</text>
      <!-- gridlines -->
      <line x1="90" y1="147" x2="680" y2="147" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,3" />
      <line x1="90" y1="100" x2="680" y2="100" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,3" />
      <line x1="90" y1="53" x2="680" y2="53" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,3" />

      <!-- screw_insert 79% → height=134 → y=56 -->
      <rect x="115" y="56" width="80" height="134" rx="4" fill="#38bdf8" opacity="0.85" />
      <text x="155" y="50" text-anchor="middle" class="bar-value">79%</text>
      <text x="155" y="210" text-anchor="middle" class="bar-label">Screw Insert</text>

      <!-- tool_handoff 83% → height=141 → y=49 -->
      <rect x="255" y="49" width="80" height="141" rx="4" fill="#38bdf8" opacity="0.85" />
      <text x="295" y="43" text-anchor="middle" class="bar-value">83%</text>
      <text x="295" y="210" text-anchor="middle" class="bar-label">Tool Handoff</text>

      <!-- card_dealing 71% → height=120 → y=70 -->
      <rect x="395" y="70" width="80" height="120" rx="4" fill="#C74634" opacity="0.85" />
      <text x="435" y="64" text-anchor="middle" class="bar-value">71%</text>
      <text x="435" y="210" text-anchor="middle" class="bar-label">Card Dealing</text>

      <!-- fragile_handling 85% → height=144 → y=46 -->
      <rect x="535" y="46" width="80" height="144" rx="4" fill="#4ade80" opacity="0.85" />
      <text x="575" y="40" text-anchor="middle" class="bar-value">85%</text>
      <text x="575" y="210" text-anchor="middle" class="bar-label">Fragile Handling</text>
    </svg>
  </section>

  <section class="chart-section">
    <h2>Task Capability Reference</h2>
    <table>
      <thead>
        <tr>
          <th>Task</th><th>Success Rate</th><th>Key Challenge</th><th>Approach</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td>Screw Insert</td>
          <td><span class="pill blue">79%</span></td>
          <td>Sub-mm alignment under compliance</td>
          <td>Fingertip force feedback + spiral search</td>
        </tr>
        <tr>
          <td>Tool Handoff</td>
          <td><span class="pill blue">83%</span></td>
          <td>Coordinated dual-arm regrasp</td>
          <td>Contact-aware regrasp planner</td>
        </tr>
        <tr>
          <td>Card Dealing</td>
          <td><span class="pill red">71%</span></td>
          <td>High-speed precision release</td>
          <td>Predictive fingertip velocity control</td>
        </tr>
        <tr>
          <td>Fragile Handling</td>
          <td><span class="pill blue">85%</span></td>
          <td>Force limit compliance (glassware, sensors)</td>
          <td>Admittance control + force cap 2N</td>
        </tr>
      </tbody>
    </table>
  </section>
</main>
<footer>OCI Robot Cloud &mdash; Dexterous Manipulation Trainer v1.0.0 &mdash; port 10044</footer>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# Health payload
# ---------------------------------------------------------------------------
def _health_payload():
    return {
        "service": SERVICE_NAME,
        "version": VERSION,
        "port": PORT,
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "supported_tasks": SUPPORTED_TASKS,
    }

# ---------------------------------------------------------------------------
# Inference helper (deterministic-ish for demo)
# ---------------------------------------------------------------------------
def _predict_dexterous(image_b64: str, target_object: str, task: str):
    """Generate finger positions and force targets for a dexterous manipulation task."""
    rng = random.Random(len(image_b64) + len(target_object) + len(task))
    n_fingers = 5  # full dexterous hand
    finger_positions = [
        [round(rng.uniform(-0.04, 0.04), 4),
         round(rng.uniform(0.01, 0.06), 4),
         round(rng.uniform(-0.02, 0.02), 4)]
        for _ in range(n_fingers)
    ]
    base_force = {"screw_insert": 3.2, "tool_handoff": 5.8, "card_dealing": 1.1, "fragile_handling": 1.8}
    f_base = base_force.get(task, 4.0)
    force_targets = [round(f_base + rng.gauss(0, 0.3), 3) for _ in range(n_fingers)]
    regrasp_plans = {
        "screw_insert": "pinch→compliant-wrap→insert-spiral",
        "tool_handoff": "power-grasp→reorient-90°→handoff-release",
        "card_dealing": "lateral-pinch→slide-release",
        "fragile_handling": "envelope-grasp→force-cap-2N→lift",
    }
    confidence = round(SR_BY_TASK.get(task, 75) / 100.0 + rng.gauss(0, 0.04), 3)
    confidence = max(0.0, min(1.0, confidence))
    return {
        "finger_positions": finger_positions,
        "force_targets": force_targets,
        "regrasp_plan": regrasp_plans.get(task, "standard-wrap"),
        "confidence": confidence,
    }


# ===========================================================================
# FastAPI branch
# ===========================================================================
if _FASTAPI:
    app = FastAPI(
        title="Dexterous Manipulation Trainer",
        description="Multi-finger dexterous manipulation: regrasping, rotation, fingertip force control.",
        version=VERSION,
    )

    class DexterousRequest(BaseModel):
        image_b64: str
        target_object: str
        task: str

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return HTMLResponse(content=DASHBOARD_HTML)

    @app.get("/health")
    def health():
        return JSONResponse(content=_health_payload())

    @app.post("/dexterous/predict")
    def dexterous_predict(req: DexterousRequest):
        if req.task not in SUPPORTED_TASKS:
            raise HTTPException(
                status_code=422,
                detail=f"Unknown task '{req.task}'. Supported: {SUPPORTED_TASKS}",
            )
        result = _predict_dexterous(req.image_b64, req.target_object, req.task)
        return JSONResponse(content=result)

    @app.get("/dexterous/capabilities")
    def dexterous_capabilities():
        return JSONResponse(content={
            "supported_tasks": SUPPORTED_TASKS,
            "sr_by_task": SR_BY_TASK,
            "vs_standard_grasp": VS_STANDARD_GRASP,
        })

# ===========================================================================
# HTTPServer fallback
# ===========================================================================
else:
    import json as _json
    from urllib.parse import urlparse as _urlparse

    class _Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):  # silence default logging
            pass

        def _send(self, code, content_type, body):
            if isinstance(body, str):
                body = body.encode()
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            path = _urlparse(self.path).path
            if path == "/":
                self._send(200, "text/html", DASHBOARD_HTML)
            elif path == "/health":
                self._send(200, "application/json", _json.dumps(_health_payload()))
            elif path == "/dexterous/capabilities":
                self._send(200, "application/json", _json.dumps({
                    "supported_tasks": SUPPORTED_TASKS,
                    "sr_by_task": SR_BY_TASK,
                    "vs_standard_grasp": VS_STANDARD_GRASP,
                }))
            else:
                self._send(404, "application/json", _json.dumps({"error": "not found"}))

        def do_POST(self):
            path = _urlparse(self.path).path
            if path == "/dexterous/predict":
                length = int(self.headers.get("Content-Length", 0))
                body = _json.loads(self.rfile.read(length))
                task = body.get("task", "")
                if task not in SUPPORTED_TASKS:
                    self._send(422, "application/json",
                               _json.dumps({"error": f"Unknown task '{task}'"}))
                    return
                result = _predict_dexterous(
                    body.get("image_b64", ""),
                    body.get("target_object", ""),
                    task,
                )
                self._send(200, "application/json", _json.dumps(result))
            else:
                self._send(404, "application/json", _json.dumps({"error": "not found"}))


# ===========================================================================
# Entry point
# ===========================================================================
if __name__ == "__main__":
    if _FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        print(f"[{SERVICE_NAME}] FastAPI not available — starting stdlib HTTPServer on port {PORT}")
        server = HTTPServer(("0.0.0.0", PORT), _Handler)
        print(f"[{SERVICE_NAME}] Listening on http://0.0.0.0:{PORT}")
        server.serve_forever()
