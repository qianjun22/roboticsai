"""AI World Demo Rehearsal Service — 12-week countdown, weekly milestones.

Port: 10167
Success criteria: 5 consecutive runs SR>85%, latency<250ms, graceful failure recovery
"""

PORT = 10167
SERVICE_NAME = "ai_world_demo_rehearsal"

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    from pydantic import BaseModel
    import uvicorn
    _has_fastapi = True
except ImportError:
    _has_fastapi = False

if _has_fastapi:
    app = FastAPI(title=SERVICE_NAME, version="1.0.0")

    class RehearsalLog(BaseModel):
        week: int
        run_number: int
        sr: float
        latency_ms: float
        failure_recovery: bool
        notes: str = ""

    @app.get("/health")
    def health():
        return JSONResponse({"status": "ok", "port": PORT, "service": SERVICE_NAME})

    @app.get("/events/ai_world/rehearsal")
    def get_rehearsal_plan():
        return JSONResponse({
            "event": "AI World",
            "total_weeks": 12,
            "phases": [
                {"weeks": "12-8", "focus": "Script & Calibrate", "milestone": "Script locked, hardware calibrated"},
                {"weeks": "8-4",  "focus": "Full Run-Throughs", "milestone": "End-to-end demo stable, SR>70%"},
                {"weeks": "4-2",  "focus": "Dress Rehearsal",   "milestone": "SR>85%, latency<250ms"},
                {"weeks": "2-0",  "focus": "Final Prep",        "milestone": "5 consecutive SR>85%, failure recovery confirmed"}
            ],
            "success_criteria": {
                "consecutive_passing_runs": 5,
                "sr_threshold": 0.85,
                "latency_ms_max": 250,
                "graceful_failure_recovery": True
            },
            "status": "scheduled"
        })

    @app.post("/events/ai_world/log_rehearsal")
    def log_rehearsal(entry: RehearsalLog):
        passed = entry.sr > 0.85 and entry.latency_ms < 250 and entry.failure_recovery
        return JSONResponse({
            "logged": True,
            "week": entry.week,
            "run_number": entry.run_number,
            "sr": entry.sr,
            "latency_ms": entry.latency_ms,
            "passed": passed,
            "message": "Run passed success criteria" if passed else "Run did not meet success criteria"
        })

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        html = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>AI World Demo Rehearsal</title>
  <style>
    body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; margin: 0; padding: 2rem; }
    h1 { color: #C74634; font-size: 1.8rem; margin-bottom: 0.25rem; }
    .subtitle { color: #38bdf8; font-size: 0.95rem; margin-bottom: 2rem; }
    .card { background: #1e293b; border-radius: 10px; padding: 1.5rem; margin-bottom: 1.5rem; }
    .card h2 { color: #38bdf8; font-size: 1.1rem; margin-top: 0; }
    .badge { display: inline-block; background: #C74634; color: #fff; border-radius: 4px; padding: 2px 10px; font-size: 0.8rem; margin-left: 0.5rem; }
    .label { fill: #94a3b8; font-size: 11px; }
    .bar-label { fill: #0f172a; font-size: 11px; font-weight: bold; }
    .axis { stroke: #334155; }
    .phase-label { fill: #e2e8f0; font-size: 11px; }
    table { width: 100%; border-collapse: collapse; }
    th { color: #38bdf8; text-align: left; padding: 0.4rem 0.6rem; border-bottom: 1px solid #334155; }
    td { padding: 0.4rem 0.6rem; border-bottom: 1px solid #1e293b; color: #cbd5e1; }
    .chip { display: inline-block; border-radius: 4px; padding: 1px 8px; font-size: 0.78rem; }
    .green { background: #166534; color: #86efac; }
    .yellow { background: #713f12; color: #fde68a; }
    .red { background: #7f1d1d; color: #fca5a5; }
  </style>
</head>
<body>
  <h1>AI World Demo Rehearsal <span class="badge">port 10167</span></h1>
  <p class="subtitle">12-Week Countdown to AI World | SR&gt;85% &bull; Latency&lt;250ms &bull; Graceful Recovery</p>

  <div class="card">
    <h2>Rehearsal Schedule (Weeks to Event)</h2>
    <!-- 4 phases, bar = weeks allocated, chart width 400px, 12 weeks total -->
    <svg width="520" height="210" viewBox="0 0 520 210" xmlns="http://www.w3.org/2000/svg">
      <!-- Y axis -->
      <line x1="70" y1="15" x2="70" y2="155" stroke="#334155" stroke-width="1"/>
      <!-- X axis -->
      <line x1="70" y1="155" x2="470" y2="155" stroke="#334155" stroke-width="1"/>

      <!-- Phase bars: scale = 400px / 12 weeks = 33.3px/week -->

      <!-- Weeks 12-8: 4 weeks = 133px -->
      <rect x="70" y="22" width="133" height="28" fill="#38bdf8" rx="3"/>
      <text x="76" y="41" class="bar-label">Script &amp; Calibrate (wk 12-8)</text>

      <!-- Weeks 8-4: 4 weeks = 133px -->
      <rect x="70" y="61" width="133" height="28" fill="#7c3aed" rx="3"/>
      <text x="76" y="80" class="bar-label" fill="#e2e8f0">Full Run-Throughs (wk 8-4)</text>

      <!-- Weeks 4-2: 2 weeks = 67px -->
      <rect x="70" y="100" width="67" height="28" fill="#C74634" rx="3"/>
      <text x="144" y="119" class="phase-label">Dress Rehearsal (wk 4-2)</text>

      <!-- Weeks 2-0: 2 weeks = 67px -->
      <rect x="70" y="139" width="67" height="28" fill="#16a34a" rx="3"/>
      <!-- this bar overlaps axis slightly, shift label -->
      <text x="144" y="158" class="phase-label">Final Prep (wk 2-0)</text>

      <!-- X axis ticks -->
      <text x="70"  y="172" text-anchor="middle" class="label">wk 12</text>
      <text x="203" y="172" text-anchor="middle" class="label">wk 8</text>
      <text x="336" y="172" text-anchor="middle" class="label">wk 4</text>
      <text x="403" y="172" text-anchor="middle" class="label">wk 2</text>
      <text x="470" y="172" text-anchor="middle" class="label">wk 0</text>

      <text x="270" y="195" text-anchor="middle" class="label">Timeline (12 weeks to AI World)</text>
    </svg>
  </div>

  <div class="card">
    <h2>Success Criteria</h2>
    <table>
      <tr><th>Criterion</th><th>Target</th><th>State</th></tr>
      <tr><td>Consecutive passing runs</td><td>5 runs</td><td><span class="chip yellow">pending</span></td></tr>
      <tr><td>Success Rate (SR)</td><td>&gt; 85%</td><td><span class="chip yellow">pending</span></td></tr>
      <tr><td>Inference latency</td><td>&lt; 250 ms</td><td><span class="chip green">235ms baseline</span></td></tr>
      <tr><td>Graceful failure recovery</td><td>Required</td><td><span class="chip yellow">pending</span></td></tr>
    </table>
  </div>

  <div class="card">
    <h2>Endpoints</h2>
    <table>
      <tr><th>Method</th><th>Path</th><th>Description</th></tr>
      <tr><td>GET</td><td>/health</td><td>Health check</td></tr>
      <tr><td>GET</td><td>/events/ai_world/rehearsal</td><td>Full rehearsal plan + phases</td></tr>
      <tr><td>POST</td><td>/events/ai_world/log_rehearsal</td><td>Log a rehearsal run result</td></tr>
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
                self.wfile.write(b"AI World Demo Rehearsal — install fastapi for full UI")

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
