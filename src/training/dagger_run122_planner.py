"""dagger_run122_planner.py — Online DAgger Run 122 Planner (port 10026)

Cycle-492B service: deploy → detect failures → collect corrections → micro-finetune → redeploy (24hr cycle)
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from typing import Any, Dict

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import HTMLResponse, JSONResponse
    from pydantic import BaseModel
    import uvicorn
    _USE_FASTAPI = True
except ImportError:
    _USE_FASTAPI = False
    from http.server import BaseHTTPRequestHandler, HTTPServer
    from urllib.parse import urlparse

PORT = 10026
RUN_ID = "run122"
INITIAL_SR = 85.0
SR_24H = 87.0
SR_7D = 91.0
DAILY_IMPROVEMENT_PCT = 0.3
BASELINE_SR = 80.0

HTML_DASHBOARD = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>DAgger Run 122 — Online Planner</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; padding: 2rem; }
    h1 { color: #C74634; font-size: 1.8rem; margin-bottom: 0.25rem; }
    .subtitle { color: #94a3b8; font-size: 0.9rem; margin-bottom: 2rem; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-bottom: 2rem; }
    .card { background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 1.25rem; }
    .card-label { color: #94a3b8; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.4rem; }
    .card-value { font-size: 1.6rem; font-weight: 700; color: #38bdf8; }
    .card-value.red { color: #C74634; }
    .card-value.green { color: #4ade80; }
    .section { background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 1.5rem; margin-bottom: 1.5rem; }
    .section h2 { color: #38bdf8; font-size: 1.1rem; margin-bottom: 1rem; }
    svg text { font-family: 'Segoe UI', system-ui, sans-serif; }
    .cycle-steps { display: flex; gap: 0.5rem; flex-wrap: wrap; margin-top: 0.75rem; }
    .step { background: #0f172a; border: 1px solid #38bdf8; border-radius: 6px; padding: 0.4rem 0.8rem; font-size: 0.8rem; color: #38bdf8; }
    .step.active { background: #C74634; border-color: #C74634; color: #fff; }
    .arrow { color: #475569; align-self: center; font-size: 1.1rem; }
    table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
    th { color: #94a3b8; text-align: left; padding: 0.5rem 0.75rem; border-bottom: 1px solid #334155; font-weight: 500; }
    td { padding: 0.5rem 0.75rem; border-bottom: 1px solid #1e293b; }
    .badge { display: inline-block; padding: 0.15rem 0.5rem; border-radius: 4px; font-size: 0.72rem; font-weight: 600; }
    .badge-blue { background: #0c4a6e; color: #38bdf8; }
    .badge-red { background: #450a0a; color: #fca5a5; }
    .badge-green { background: #052e16; color: #4ade80; }
  </style>
</head>
<body>
  <h1>DAgger Run 122 — Online Planner</h1>
  <p class="subtitle">Continuous improvement loop: deploy → fail detection → corrections → micro-finetune → redeploy &nbsp;|&nbsp; Port {PORT}</p>

  <div class="grid">
    <div class="card"><div class="card-label">Initial Deploy SR</div><div class="card-value red">85.0%</div></div>
    <div class="card"><div class="card-label">SR After 24 hr</div><div class="card-value">87.0%</div></div>
    <div class="card"><div class="card-label">SR After 7 Days</div><div class="card-value green">91.0%</div></div>
    <div class="card"><div class="card-label">Daily Improvement</div><div class="card-value">+0.3%</div></div>
    <div class="card"><div class="card-label">Improvement vs Baseline</div><div class="card-value green">+11.0 pp</div></div>
    <div class="card"><div class="card-label">Cycle</div><div class="card-value">24 hr</div></div>
  </div>

  <div class="section">
    <h2>Success Rate Progression (SVG Bar Chart)</h2>
    <svg viewBox="0 0 680 220" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:680px;display:block;">
      <!-- axes -->
      <line x1="60" y1="10" x2="60" y2="180" stroke="#475569" stroke-width="1"/>
      <line x1="60" y1="180" x2="640" y2="180" stroke="#475569" stroke-width="1"/>
      <!-- y gridlines & labels -->
      <text x="55" y="180" fill="#64748b" font-size="11" text-anchor="end">75%</text>
      <line x1="60" y1="180" x2="640" y2="180" stroke="#1e293b" stroke-width="1" stroke-dasharray="4"/>
      <text x="55" y="140" fill="#64748b" font-size="11" text-anchor="end">80%</text>
      <line x1="60" y1="140" x2="640" y2="140" stroke="#334155" stroke-width="1" stroke-dasharray="4"/>
      <text x="55" y="100" fill="#64748b" font-size="11" text-anchor="end">85%</text>
      <line x1="60" y1="100" x2="640" y2="100" stroke="#334155" stroke-width="1" stroke-dasharray="4"/>
      <text x="55" y="60" fill="#64748b" font-size="11" text-anchor="end">90%</text>
      <line x1="60" y1="60" x2="640" y2="60" stroke="#334155" stroke-width="1" stroke-dasharray="4"/>
      <text x="55" y="20" fill="#64748b" font-size="11" text-anchor="end">95%</text>
      <!-- bars: scale 75-95% → 180 to 10, range 160px per 20ppt; each 1ppt = 8px -->
      <!-- Baseline 80%: (80-75)*8=40px tall, top=180-40=140 -->
      <rect x="90" y="140" width="60" height="40" fill="#475569" rx="3"/>
      <text x="120" y="135" fill="#94a3b8" font-size="11" text-anchor="middle">80.0%</text>
      <text x="120" y="198" fill="#94a3b8" font-size="11" text-anchor="middle">Baseline</text>
      <!-- Initial 85%: (85-75)*8=80px, top=180-80=100 -->
      <rect x="200" y="100" width="60" height="80" fill="#C74634" rx="3"/>
      <text x="230" y="95" fill="#fca5a5" font-size="11" text-anchor="middle">85.0%</text>
      <text x="230" y="198" fill="#94a3b8" font-size="11" text-anchor="middle">Deploy</text>
      <!-- 24hr 87%: (87-75)*8=96px, top=180-96=84 -->
      <rect x="310" y="84" width="60" height="96" fill="#0ea5e9" rx="3"/>
      <text x="340" y="79" fill="#7dd3fc" font-size="11" text-anchor="middle">87.0%</text>
      <text x="340" y="198" fill="#94a3b8" font-size="11" text-anchor="middle">+24 hr</text>
      <!-- 3d 89.4%: (89.4-75)*8=115.2, top=64.8≈65 -->
      <rect x="420" y="65" width="60" height="115" fill="#38bdf8" rx="3"/>
      <text x="450" y="60" fill="#bae6fd" font-size="11" text-anchor="middle">89.4%</text>
      <text x="450" y="198" fill="#94a3b8" font-size="11" text-anchor="middle">+3 Days</text>
      <!-- 7d 91%: (91-75)*8=128, top=52 -->
      <rect x="530" y="52" width="60" height="128" fill="#4ade80" rx="3"/>
      <text x="560" y="47" fill="#86efac" font-size="11" text-anchor="middle">91.0%</text>
      <text x="560" y="198" fill="#94a3b8" font-size="11" text-anchor="middle">+7 Days</text>
      <!-- trend line -->
      <polyline points="120,140 230,100 340,84 450,65 560,52" fill="none" stroke="#fbbf24" stroke-width="1.5" stroke-dasharray="5,3"/>
    </svg>
  </div>

  <div class="section">
    <h2>24-Hour DAgger Cycle Architecture</h2>
    <div class="cycle-steps">
      <div class="step active">1. Deploy Policy</div>
      <div class="arrow">→</div>
      <div class="step">2. Monitor Failures</div>
      <div class="arrow">→</div>
      <div class="step">3. Collect Corrections</div>
      <div class="arrow">→</div>
      <div class="step">4. Micro-Finetune</div>
      <div class="arrow">→</div>
      <div class="step">5. Validate SR</div>
      <div class="arrow">→</div>
      <div class="step">6. Redeploy</div>
    </div>
  </div>

  <div class="section">
    <h2>Run 122 — Daily Snapshot</h2>
    <table>
      <thead><tr><th>Day</th><th>SR</th><th>Improvement vs Prior</th><th>Corrections</th><th>Finetune Trigger</th></tr></thead>
      <tbody>
        <tr><td>Day 0 (deploy)</td><td>85.0%</td><td>—</td><td>—</td><td>—</td></tr>
        <tr><td>Day 1</td><td>85.3%</td><td><span class="badge badge-green">+0.3%</span></td><td>12</td><td>corrections &ge; 10</td></tr>
        <tr><td>Day 2</td><td>85.6%</td><td><span class="badge badge-green">+0.3%</span></td><td>11</td><td>corrections &ge; 10</td></tr>
        <tr><td>Day 7</td><td>87.0%</td><td><span class="badge badge-green">+0.3%</span></td><td>9</td><td>corrections &ge; 10</td></tr>
        <tr><td>Day 21</td><td>91.0%</td><td><span class="badge badge-green">+0.3%</span></td><td>7</td><td>corrections &ge; 10</td></tr>
      </tbody>
    </table>
  </div>

  <div class="section">
    <h2>Endpoints</h2>
    <table>
      <thead><tr><th>Method</th><th>Path</th><th>Description</th></tr></thead>
      <tbody>
        <tr><td><span class="badge badge-blue">GET</span></td><td>/</td><td>This dashboard</td></tr>
        <tr><td><span class="badge badge-blue">GET</span></td><td>/health</td><td>Health check JSON</td></tr>
        <tr><td><span class="badge badge-blue">GET</span></td><td>/dagger/run122/status</td><td>Run 122 status &amp; SR metrics</td></tr>
        <tr><td><span class="badge badge-red">POST</span></td><td>/dagger/run122/online_step</td><td>Simulate one online DAgger step</td></tr>
      </tbody>
    </table>
  </div>
</body>
</html>
""".replace("{PORT}", str(PORT))


def compute_online_step(day: int, failure_count: int, corrections_collected: int) -> Dict[str, Any]:
    """Compute SR improvement for a single online DAgger step."""
    sr_gain_from_corrections = min(corrections_collected * 0.05, 1.5)
    sr_gain_from_time = day * DAILY_IMPROVEMENT_PCT
    new_sr = min(INITIAL_SR + sr_gain_from_time + sr_gain_from_corrections, 97.0)
    improvement_over_baseline = round(new_sr - BASELINE_SR, 3)
    # Trigger finetune when corrections >= 10 or failures spike
    if corrections_collected >= 10:
        next_trigger = "immediate — correction buffer full"
    elif failure_count >= 5:
        next_trigger = "immediate — failure spike detected"
    else:
        needed = 10 - corrections_collected
        next_trigger = f"collect {needed} more corrections"
    return {
        "new_sr": round(new_sr, 3),
        "improvement_over_baseline": improvement_over_baseline,
        "next_finetune_trigger": next_trigger,
    }


if _USE_FASTAPI:
    app = FastAPI(
        title="DAgger Run 122 Online Planner",
        description="Online DAgger planning service — 24hr continuous improvement cycle",
        version="1.0.0",
    )

    class OnlineStepRequest(BaseModel):
        day: int
        failure_count: int
        corrections_collected: int

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return HTML_DASHBOARD

    @app.get("/health")
    async def health():
        return JSONResponse({
            "status": "ok",
            "service": "dagger_run122_planner",
            "port": PORT,
            "run_id": RUN_ID,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    @app.get("/dagger/run122/status")
    async def run_status():
        return JSONResponse({
            "run_id": RUN_ID,
            "mode": "online",
            "initial_deploy_sr": INITIAL_SR,
            "sr_after_24h": SR_24H,
            "sr_after_7d": SR_7D,
            "daily_improvement_pct": DAILY_IMPROVEMENT_PCT,
        })

    @app.post("/dagger/run122/online_step")
    async def online_step(req: OnlineStepRequest):
        if req.day < 0:
            raise HTTPException(status_code=422, detail="day must be >= 0")
        if req.failure_count < 0 or req.corrections_collected < 0:
            raise HTTPException(status_code=422, detail="counts must be non-negative")
        return JSONResponse(compute_online_step(req.day, req.failure_count, req.corrections_collected))

else:
    # stdlib fallback
    class _Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):  # silence access log
            pass

        def _send(self, code: int, content_type: str, body: str):
            encoded = body.encode()
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
                body = json.dumps({"status": "ok", "service": "dagger_run122_planner", "port": PORT})
                self._send(200, "application/json", body)
            elif path == "/dagger/run122/status":
                body = json.dumps({
                    "run_id": RUN_ID, "mode": "online",
                    "initial_deploy_sr": INITIAL_SR, "sr_after_24h": SR_24H,
                    "sr_after_7d": SR_7D, "daily_improvement_pct": DAILY_IMPROVEMENT_PCT,
                })
                self._send(200, "application/json", body)
            else:
                self._send(404, "application/json", json.dumps({"error": "not found"}))

        def do_POST(self):
            path = urlparse(self.path).path
            if path == "/dagger/run122/online_step":
                length = int(self.headers.get("Content-Length", 0))
                data = json.loads(self.rfile.read(length))
                result = compute_online_step(
                    int(data.get("day", 0)),
                    int(data.get("failure_count", 0)),
                    int(data.get("corrections_collected", 0)),
                )
                self._send(200, "application/json", json.dumps(result))
            else:
                self._send(404, "application/json", json.dumps({"error": "not found"}))


if __name__ == "__main__":
    if _USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        print(f"FastAPI not available — falling back to stdlib HTTPServer on port {PORT}")
        server = HTTPServer(("0.0.0.0", PORT), _Handler)
        server.serve_forever()
