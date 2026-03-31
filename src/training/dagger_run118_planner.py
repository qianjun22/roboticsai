"""DAgger Run118 Planner — curriculum DAgger with progressive difficulty.

Port: 10010
Cycle: 488B
"""

from __future__ import annotations

import json
import math
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import HTMLResponse, JSONResponse
    from pydantic import BaseModel
    import uvicorn
    _FASTAPI = True
except ImportError:
    _FASTAPI = False

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
PORT = 10010
RUN_ID = "run118"

PHASE_CONFIG = [
    {"phase": 1, "difficulty": "easy",   "expert_requirement": "50% expert queries",  "sr": 88, "threshold": 0.80},
    {"phase": 2, "difficulty": "medium",  "expert_requirement": "30% expert queries",  "sr": 91, "threshold": 0.88},
    {"phase": 3, "difficulty": "hard",    "expert_requirement": "15% expert queries",  "sr": 94, "threshold": 0.91},
]
RANDOM_BASELINE_SR = 91

# ---------------------------------------------------------------------------
# Business logic
# ---------------------------------------------------------------------------

def plan_next_phase(current_phase: int, current_sr: float) -> dict:
    idx = current_phase - 1
    if idx < 0 or idx >= len(PHASE_CONFIG):
        raise ValueError(f"current_phase must be 1-{len(PHASE_CONFIG)}")
    cfg = PHASE_CONFIG[idx]
    # Advance if SR meets threshold and not already at last phase
    if current_sr >= cfg["threshold"] and current_phase < len(PHASE_CONFIG):
        next_idx = idx + 1
    else:
        next_idx = idx
    next_cfg = PHASE_CONFIG[next_idx]
    projected_sr = next_cfg["sr"] + round((current_sr - cfg["sr"]) * 0.4, 2)
    return {
        "next_phase": next_cfg["phase"],
        "task_difficulty": next_cfg["difficulty"],
        "expert_requirement": next_cfg["expert_requirement"],
        "projected_sr": round(min(projected_sr, 99.0), 2),
    }


def get_run_status() -> dict:
    return {
        "run_id": RUN_ID,
        "phases": len(PHASE_CONFIG),
        "phase1_sr": PHASE_CONFIG[0]["sr"],
        "phase2_sr": PHASE_CONFIG[1]["sr"],
        "phase3_sr": PHASE_CONFIG[2]["sr"],
        "random_baseline_sr": RANDOM_BASELINE_SR,
    }


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------
DASHBOARD_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>DAgger Run118 Planner — OCI Robot Cloud</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: #0f172a; color: #e2e8f0; font-family: 'Inter', 'Segoe UI', sans-serif; min-height: 100vh; padding: 2rem; }
    h1 { color: #C74634; font-size: 1.75rem; font-weight: 700; margin-bottom: 0.25rem; }
    .subtitle { color: #38bdf8; font-size: 0.95rem; margin-bottom: 2rem; }
    .cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-bottom: 2.5rem; }
    .card { background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 1.25rem; }
    .card-label { font-size: 0.75rem; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.5rem; }
    .card-value { font-size: 2rem; font-weight: 700; color: #38bdf8; }
    .card-sub { font-size: 0.8rem; color: #64748b; margin-top: 0.25rem; }
    .card-value.red { color: #C74634; }
    .section-title { color: #38bdf8; font-size: 1.1rem; font-weight: 600; margin-bottom: 1rem; }
    .chart-wrap { background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 1.5rem; margin-bottom: 2rem; }
    svg text { font-family: inherit; }
    .phase-table { width: 100%; border-collapse: collapse; }
    .phase-table th, .phase-table td { border: 1px solid #334155; padding: 0.6rem 1rem; text-align: left; font-size: 0.875rem; }
    .phase-table th { background: #0f172a; color: #94a3b8; text-transform: uppercase; font-size: 0.75rem; }
    .phase-table tr:nth-child(even) td { background: #162032; }
    .badge-easy   { color: #4ade80; font-weight: 600; }
    .badge-medium { color: #facc15; font-weight: 600; }
    .badge-hard   { color: #f87171; font-weight: 600; }
    footer { margin-top: 3rem; color: #475569; font-size: 0.75rem; text-align: center; }
  </style>
</head>
<body>
  <h1>DAgger Run118 Planner</h1>
  <p class="subtitle">Curriculum DAgger — Progressive Difficulty: Easy &rarr; Medium &rarr; Hard &nbsp;|&nbsp; Port 10010</p>

  <div class="cards">
    <div class="card">
      <div class="card-label">Phase 1 SR (Easy)</div>
      <div class="card-value">88%</div>
      <div class="card-sub">Threshold &ge; 80%</div>
    </div>
    <div class="card">
      <div class="card-label">Phase 2 SR (Medium)</div>
      <div class="card-value">91%</div>
      <div class="card-sub">Threshold &ge; 88%</div>
    </div>
    <div class="card">
      <div class="card-label">Phase 3 SR (Hard)</div>
      <div class="card-value">94%</div>
      <div class="card-sub">Threshold &ge; 91%</div>
    </div>
    <div class="card">
      <div class="card-label">Random Baseline SR</div>
      <div class="card-value red">91%</div>
      <div class="card-sub">Phase 3 beats baseline by +3pp</div>
    </div>
  </div>

  <div class="chart-wrap">
    <div class="section-title">Curriculum Progression vs Random Baseline</div>
    <svg width="100%" viewBox="0 0 640 260" xmlns="http://www.w3.org/2000/svg">
      <!-- axes -->
      <line x1="60" y1="20" x2="60" y2="210" stroke="#475569" stroke-width="1.5"/>
      <line x1="60" y1="210" x2="620" y2="210" stroke="#475569" stroke-width="1.5"/>
      <!-- y-axis labels -->
      <text x="52" y="214" fill="#64748b" font-size="11" text-anchor="end">80</text>
      <text x="52" y="167" fill="#64748b" font-size="11" text-anchor="end">85</text>
      <text x="52" y="120" fill="#64748b" font-size="11" text-anchor="end">90</text>
      <text x="52" y="73"  fill="#64748b" font-size="11" text-anchor="end">95</text>
      <text x="52" y="26"  fill="#64748b" font-size="11" text-anchor="end">100</text>
      <!-- grid lines -->
      <line x1="60" y1="167" x2="620" y2="167" stroke="#1e293b" stroke-width="1" stroke-dasharray="4 3"/>
      <line x1="60" y1="120" x2="620" y2="120" stroke="#1e293b" stroke-width="1" stroke-dasharray="4 3"/>
      <line x1="60" y1="73"  x2="620" y2="73"  stroke="#1e293b" stroke-width="1" stroke-dasharray="4 3"/>
      <!-- baseline line (91% = y=120 - (91-90)*9.4 = 120-9.4=110.6 ... scale: 100%-80% = 190px => 1%=9.5px, 80%=y210) -->
      <!-- y = 210 - (sr - 80) * 9.5 -->
      <!-- Phase1=88% => y=210-76=134; Phase2=91%=>y=210-104.5=105.5; Phase3=94%=>y=210-133=77 -->
      <!-- Random=91% => y=105.5 -->
      <line x1="60" y1="105" x2="620" y2="105" stroke="#C74634" stroke-width="1.5" stroke-dasharray="6 4"/>
      <text x="625" y="109" fill="#C74634" font-size="10" text-anchor="start">Rand 91%</text>
      <!-- bars: 3 phases, spread across x=80-580 -->
      <!-- Phase1: x=100, w=120 -->
      <rect x="100" y="134" width="120" height="76" fill="#38bdf8" rx="4"/>
      <text x="160" y="128" fill="#38bdf8" font-size="12" font-weight="700" text-anchor="middle">88%</text>
      <text x="160" y="228" fill="#94a3b8" font-size="11" text-anchor="middle">Phase 1 — Easy</text>
      <!-- Phase2: x=260, w=120 -->
      <rect x="260" y="105" width="120" height="105" fill="#38bdf8" rx="4" opacity="0.85"/>
      <text x="320" y="99"  fill="#38bdf8" font-size="12" font-weight="700" text-anchor="middle">91%</text>
      <text x="320" y="228" fill="#94a3b8" font-size="11" text-anchor="middle">Phase 2 — Medium</text>
      <!-- Phase3: x=420, w=120 -->
      <rect x="420" y="77" width="120" height="133" fill="#38bdf8" rx="4" opacity="0.7"/>
      <text x="480" y="71"  fill="#38bdf8" font-size="12" font-weight="700" text-anchor="middle">94%</text>
      <text x="480" y="228" fill="#94a3b8" font-size="11" text-anchor="middle">Phase 3 — Hard</text>
      <!-- y-axis title -->
      <text transform="rotate(-90)" x="-115" y="18" fill="#64748b" font-size="11" text-anchor="middle">Success Rate (%)</text>
    </svg>
  </div>

  <div class="chart-wrap">
    <div class="section-title">Phase Details</div>
    <table class="phase-table">
      <thead><tr><th>Phase</th><th>Difficulty</th><th>Expert Queries</th><th>Advance Threshold</th><th>Achieved SR</th></tr></thead>
      <tbody>
        <tr><td>1</td><td><span class="badge-easy">Easy</span></td><td>50%</td><td>&ge; 80%</td><td>88%</td></tr>
        <tr><td>2</td><td><span class="badge-medium">Medium</span></td><td>30%</td><td>&ge; 88%</td><td>91%</td></tr>
        <tr><td>3</td><td><span class="badge-hard">Hard</span></td><td>15%</td><td>&mdash;</td><td>94%</td></tr>
      </tbody>
    </table>
  </div>

  <footer>OCI Robot Cloud &mdash; DAgger Run118 Planner &mdash; Cycle 488B</footer>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
if _FASTAPI:
    app = FastAPI(
        title="DAgger Run118 Planner",
        description="Curriculum DAgger with progressive difficulty (easy→medium→hard)",
        version="1.0.0",
    )

    class PlanRequest(BaseModel):
        current_phase: int
        current_sr: float

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return DASHBOARD_HTML

    @app.get("/health")
    def health():
        return JSONResponse({"status": "ok", "service": "dagger_run118_planner", "port": PORT})

    @app.post("/dagger/run118/plan")
    def plan(req: PlanRequest):
        try:
            result = plan_next_phase(req.current_phase, req.current_sr)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return JSONResponse(result)

    @app.get("/dagger/run118/status")
    def status():
        return JSONResponse(get_run_status())


# ---------------------------------------------------------------------------
# Stdlib fallback HTTPServer
# ---------------------------------------------------------------------------
class _FallbackHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # silence default logging
        pass

    def _send(self, code: int, content_type: str, body: str | bytes):
        encoded = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self):
        if self.path == "/":
            self._send(200, "text/html; charset=utf-8", DASHBOARD_HTML)
        elif self.path == "/health":
            body = json.dumps({"status": "ok", "service": "dagger_run118_planner", "port": PORT})
            self._send(200, "application/json", body)
        elif self.path == "/dagger/run118/status":
            self._send(200, "application/json", json.dumps(get_run_status()))
        else:
            self._send(404, "application/json", json.dumps({"error": "not found"}))

    def do_POST(self):
        if self.path == "/dagger/run118/plan":
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length)
            try:
                data = json.loads(raw)
                result = plan_next_phase(int(data["current_phase"]), float(data["current_sr"]))
                self._send(200, "application/json", json.dumps(result))
            except (KeyError, ValueError) as exc:
                self._send(422, "application/json", json.dumps({"error": str(exc)}))
        else:
            self._send(404, "application/json", json.dumps({"error": "not found"}))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    if _FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        print(f"[fallback] Serving on http://0.0.0.0:{PORT}  (fastapi not available)")
        HTTPServer(("0.0.0.0", PORT), _FallbackHandler).serve_forever()
