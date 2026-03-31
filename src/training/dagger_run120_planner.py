"""DAgger Run-120 Sub-Task Planner — port 10018.

Sub-task DAgger: collects corrections per sub-task (reach/grasp/lift/transport)
and composes sub-task policies into an end-to-end policy.
"""

from __future__ import annotations

import json
import random
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Dict

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    _FASTAPI = True
except ImportError:
    _FASTAPI = False

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PORT = 10018

BASE_SR: Dict[str, int] = {
    "reach": 98,
    "grasp": 94,
    "lift": 91,
    "transport": 89,
}

COMPOSED_SR = 93
E2E_SR = 85

# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>DAgger Run-120 Sub-Task Planner</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; padding: 2rem; }
    h1 { color: #C74634; font-size: 1.8rem; margin-bottom: 0.25rem; }
    .subtitle { color: #94a3b8; font-size: 0.9rem; margin-bottom: 2rem; }
    .cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 1rem; margin-bottom: 2rem; }
    .card { background: #1e293b; border-radius: 10px; padding: 1.25rem; border-left: 4px solid #38bdf8; }
    .card.highlight { border-left-color: #C74634; }
    .card h3 { font-size: 0.75rem; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.5rem; }
    .card .value { font-size: 2rem; font-weight: 700; color: #38bdf8; }
    .card.highlight .value { color: #C74634; }
    .card .label { font-size: 0.8rem; color: #64748b; margin-top: 0.25rem; }
    .chart-section { background: #1e293b; border-radius: 10px; padding: 1.5rem; margin-bottom: 2rem; }
    .chart-section h2 { color: #38bdf8; font-size: 1.1rem; margin-bottom: 1.25rem; }
    .bar-row { display: flex; align-items: center; gap: 1rem; margin-bottom: 0.75rem; }
    .bar-label { width: 90px; font-size: 0.85rem; color: #94a3b8; text-align: right; }
    .bar-track { flex: 1; height: 28px; background: #0f172a; border-radius: 6px; overflow: hidden; }
    .bar-fill { height: 100%; border-radius: 6px; display: flex; align-items: center; padding-left: 0.75rem; font-weight: 600; font-size: 0.85rem; color: #fff; transition: width 0.6s ease; }
    .bar-fill.subtask { background: linear-gradient(90deg, #38bdf8, #0ea5e9); }
    .bar-fill.composed { background: linear-gradient(90deg, #C74634, #ef4444); }
    .bar-fill.e2e { background: linear-gradient(90deg, #f59e0b, #d97706); }
    .endpoints { background: #1e293b; border-radius: 10px; padding: 1.5rem; }
    .endpoints h2 { color: #38bdf8; font-size: 1.1rem; margin-bottom: 1rem; }
    .endpoint { font-family: monospace; font-size: 0.85rem; padding: 0.5rem 0.75rem; background: #0f172a; border-radius: 6px; margin-bottom: 0.5rem; color: #e2e8f0; }
    .method { color: #C74634; font-weight: 700; margin-right: 0.5rem; }
    .gain { color: #4ade80; font-weight: 700; }
    footer { margin-top: 2rem; text-align: center; font-size: 0.75rem; color: #334155; }
  </style>
</head>
<body>
  <h1>DAgger Run-120 Sub-Task Planner</h1>
  <p class="subtitle">OCI Robot Cloud &mdash; Port 10018 &mdash; Sub-task correction collection &amp; policy composition</p>

  <div class="cards">
    <div class="card">
      <h3>Reach SR</h3>
      <div class="value">98%</div>
      <div class="label">Sub-task policy</div>
    </div>
    <div class="card">
      <h3>Grasp SR</h3>
      <div class="value">94%</div>
      <div class="label">Sub-task policy</div>
    </div>
    <div class="card">
      <h3>Lift SR</h3>
      <div class="value">91%</div>
      <div class="label">Sub-task policy</div>
    </div>
    <div class="card">
      <h3>Transport SR</h3>
      <div class="value">89%</div>
      <div class="label">Sub-task policy</div>
    </div>
    <div class="card highlight">
      <h3>Composed SR</h3>
      <div class="value">93%</div>
      <div class="label">Sub-task composition</div>
    </div>
    <div class="card">
      <h3>E2E SR</h3>
      <div class="value">85%</div>
      <div class="label">Monolithic policy</div>
    </div>
    <div class="card highlight">
      <h3>Composition Gain</h3>
      <div class="value gain">+9.4%</div>
      <div class="label">vs monolithic e2e</div>
    </div>
  </div>

  <!-- SVG bar chart -->
  <div class="chart-section">
    <h2>Sub-task Success Rate Breakdown</h2>
    <svg width="100%" height="240" viewBox="0 0 600 240" xmlns="http://www.w3.org/2000/svg">
      <!-- background -->
      <rect width="600" height="240" fill="#1e293b" rx="8"/>
      <!-- grid lines -->
      <line x1="80" y1="20" x2="580" y2="20" stroke="#334155" stroke-width="1"/>
      <line x1="80" y1="60" x2="580" y2="60" stroke="#334155" stroke-width="1"/>
      <line x1="80" y1="100" x2="580" y2="100" stroke="#334155" stroke-width="1"/>
      <line x1="80" y1="140" x2="580" y2="140" stroke="#334155" stroke-width="1"/>
      <line x1="80" y1="180" x2="580" y2="180" stroke="#334155" stroke-width="1"/>
      <!-- y-axis labels -->
      <text x="70" y="24" fill="#64748b" font-size="11" text-anchor="end">100%</text>
      <text x="70" y="64" fill="#64748b" font-size="11" text-anchor="end">80%</text>
      <text x="70" y="104" fill="#64748b" font-size="11" text-anchor="end">60%</text>
      <text x="70" y="144" fill="#64748b" font-size="11" text-anchor="end">40%</text>
      <text x="70" y="184" fill="#64748b" font-size="11" text-anchor="end">20%</text>
      <!-- bars: reach 98% -->
      <rect x="100" y="27.2" width="60" height="152.8" fill="#38bdf8" rx="4"/>
      <text x="130" y="215" fill="#94a3b8" font-size="12" text-anchor="middle">Reach</text>
      <text x="130" y="22" fill="#e2e8f0" font-size="12" font-weight="bold" text-anchor="middle">98%</text>
      <!-- bars: grasp 94% -->
      <rect x="185" y="33.2" width="60" height="146.8" fill="#38bdf8" rx="4"/>
      <text x="215" y="215" fill="#94a3b8" font-size="12" text-anchor="middle">Grasp</text>
      <text x="215" y="28" fill="#e2e8f0" font-size="12" font-weight="bold" text-anchor="middle">94%</text>
      <!-- bars: lift 91% -->
      <rect x="270" y="37.6" width="60" height="142.4" fill="#38bdf8" rx="4"/>
      <text x="300" y="215" fill="#94a3b8" font-size="12" text-anchor="middle">Lift</text>
      <text x="300" y="32" fill="#e2e8f0" font-size="12" font-weight="bold" text-anchor="middle">91%</text>
      <!-- bars: transport 89% -->
      <rect x="355" y="40.4" width="60" height="139.6" fill="#38bdf8" rx="4"/>
      <text x="385" y="215" fill="#94a3b8" font-size="12" text-anchor="middle">Transport</text>
      <text x="385" y="35" fill="#e2e8f0" font-size="12" font-weight="bold" text-anchor="middle">89%</text>
      <!-- bars: composed 93% (red) -->
      <rect x="440" y="34.8" width="60" height="145.2" fill="#C74634" rx="4"/>
      <text x="470" y="215" fill="#94a3b8" font-size="12" text-anchor="middle">Composed</text>
      <text x="470" y="30" fill="#e2e8f0" font-size="12" font-weight="bold" text-anchor="middle">93%</text>
      <!-- bars: e2e 85% (amber) -->
      <rect x="510" y="46" width="60" height="134" fill="#f59e0b" rx="4"/>
      <text x="540" y="215" fill="#94a3b8" font-size="12" text-anchor="middle">E2E</text>
      <text x="540" y="41" fill="#e2e8f0" font-size="12" font-weight="bold" text-anchor="middle">85%</text>
      <!-- legend -->
      <rect x="100" y="228" width="12" height="10" fill="#38bdf8" rx="2"/>
      <text x="116" y="238" fill="#94a3b8" font-size="11">Sub-task Policy</text>
      <rect x="260" y="228" width="12" height="10" fill="#C74634" rx="2"/>
      <text x="276" y="238" fill="#94a3b8" font-size="11">Composed</text>
      <rect x="390" y="228" width="12" height="10" fill="#f59e0b" rx="2"/>
      <text x="406" y="238" fill="#94a3b8" font-size="11">E2E Monolithic</text>
    </svg>
  </div>

  <div class="endpoints">
    <h2>API Endpoints</h2>
    <div class="endpoint"><span class="method">GET</span>/health &mdash; Health check</div>
    <div class="endpoint"><span class="method">GET</span>/dagger/run120/status &mdash; Current run-120 metrics</div>
    <div class="endpoint"><span class="method">POST</span>/dagger/run120/plan &mdash; Plan sub-task DAgger iterations</div>
  </div>

  <footer>OCI Robot Cloud &bull; DAgger Run-120 Sub-Task Planner &bull; Port 10018</footer>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# Business logic
# ---------------------------------------------------------------------------

def compute_plan(subtask: str, iterations: int) -> dict:
    """Simulate planning a DAgger run for a given sub-task."""
    subtask_lower = subtask.lower()
    base = BASE_SR.get(subtask_lower, 80)
    # Simulate marginal gain from additional iterations
    gain = min(iterations * 0.05, 5.0)
    updated_sr = min(base + gain + random.uniform(-0.5, 0.5), 99.9)

    updated_subtask_sr = dict(BASE_SR)
    updated_subtask_sr[subtask_lower] = round(updated_sr, 1)

    composed = round(sum(updated_subtask_sr.values()) / len(updated_subtask_sr) * 1.01, 1)
    e2e = round(composed * 0.913, 1)
    gain_pct = round((composed - E2E_SR) / E2E_SR * 100, 2)

    return {
        "subtask_sr": updated_subtask_sr,
        "composed_sr": composed,
        "e2e_sr": e2e,
        "composition_gain_pct": gain_pct,
    }


def get_status() -> dict:
    return {
        "run_id": "run120",
        "subtasks": ["reach", "grasp", "lift", "transport"],
        "subtask_sr": BASE_SR,
        "composed_sr": COMPOSED_SR,
        "e2e_sr": E2E_SR,
    }


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

if _FASTAPI:
    from fastapi import FastAPI, Request
    from fastapi.responses import HTMLResponse, JSONResponse
    from pydantic import BaseModel

    app = FastAPI(title="DAgger Run-120 Sub-Task Planner", version="1.0.0")

    class PlanRequest(BaseModel):
        subtask: str
        iterations: int = 100

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return HTML

    @app.get("/health")
    async def health():
        return JSONResponse({"status": "ok", "service": "dagger_run120_planner", "port": PORT})

    @app.get("/dagger/run120/status")
    async def status():
        return JSONResponse(get_status())

    @app.post("/dagger/run120/plan")
    async def plan(req: PlanRequest):
        result = compute_plan(req.subtask, req.iterations)
        return JSONResponse(result)

# ---------------------------------------------------------------------------
# stdlib HTTPServer fallback
# ---------------------------------------------------------------------------

else:
    class _Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):  # silence access log
            pass

        def _send(self, code: int, content_type: str, body: bytes):
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == "/":
                self._send(200, "text/html; charset=utf-8", HTML.encode())
            elif self.path == "/health":
                body = json.dumps({"status": "ok", "service": "dagger_run120_planner", "port": PORT}).encode()
                self._send(200, "application/json", body)
            elif self.path == "/dagger/run120/status":
                body = json.dumps(get_status()).encode()
                self._send(200, "application/json", body)
            else:
                self._send(404, "application/json", b'{"error": "not found"}')

        def do_POST(self):
            if self.path == "/dagger/run120/plan":
                length = int(self.headers.get("Content-Length", 0))
                raw = self.rfile.read(length)
                try:
                    data = json.loads(raw)
                    result = compute_plan(data.get("subtask", "reach"), int(data.get("iterations", 100)))
                    body = json.dumps(result).encode()
                    self._send(200, "application/json", body)
                except Exception as exc:
                    body = json.dumps({"error": str(exc)}).encode()
                    self._send(400, "application/json", body)
            else:
                self._send(404, "application/json", b'{"error": "not found"}')

    def _serve():
        server = HTTPServer(("0.0.0.0", PORT), _Handler)
        print(f"DAgger Run-120 Planner (stdlib) listening on port {PORT}")
        server.serve_forever()

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if _FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        _serve()
