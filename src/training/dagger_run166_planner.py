"""DAgger Run166 Planner — long-horizon DAgger with 10-step correction sequences.

Port 10202
"""

import json
from datetime import datetime

PORT = 10202
SERVICE_NAME = "dagger_run166_planner"

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    _FASTAPI_AVAILABLE = True
except ImportError:
    _FASTAPI_AVAILABLE = False

_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>DAgger Run166 Planner</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; padding: 2rem; }
    h1 { color: #C74634; font-size: 1.8rem; margin-bottom: 0.4rem; }
    .subtitle { color: #38bdf8; font-size: 1rem; margin-bottom: 2rem; }
    .card { background: #1e293b; border-radius: 10px; padding: 1.5rem; margin-bottom: 1.5rem; }
    .card h2 { color: #38bdf8; margin-bottom: 1rem; font-size: 1.1rem; }
    .metric { display: inline-block; margin-right: 2rem; margin-bottom: 0.5rem; }
    .metric .val { font-size: 2rem; font-weight: bold; color: #C74634; }
    .metric .lbl { font-size: 0.8rem; color: #94a3b8; }
    .tag { display: inline-block; background: #0f172a; border: 1px solid #38bdf8;
           color: #38bdf8; border-radius: 4px; padding: 0.2rem 0.6rem;
           font-size: 0.75rem; margin: 0.2rem; }
    .endpoints { font-size: 0.85rem; }
    .endpoints a { color: #38bdf8; text-decoration: none; display: block; margin: 0.3rem 0; }
    .endpoints a:hover { color: #C74634; }
    svg text { font-family: 'Segoe UI', sans-serif; }
  </style>
</head>
<body>
  <h1>DAgger Run166 Planner</h1>
  <p class="subtitle">Long-horizon DAgger — 10-step correction sequences for complex multi-step tasks</p>

  <div class="card">
    <h2>Success Rate: Long-Horizon vs Standard (15-step tasks)</h2>
    <svg width="480" height="200" viewBox="0 0 480 200">
      <!-- background -->
      <rect width="480" height="200" fill="#0f172a" rx="8"/>
      <!-- axes -->
      <line x1="60" y1="160" x2="440" y2="160" stroke="#334155" stroke-width="1"/>
      <line x1="60" y1="20" x2="60" y2="160" stroke="#334155" stroke-width="1"/>
      <!-- gridlines -->
      <line x1="60" y1="120" x2="440" y2="120" stroke="#1e293b" stroke-width="1" stroke-dasharray="4,3"/>
      <line x1="60" y1="80" x2="440" y2="80" stroke="#1e293b" stroke-width="1" stroke-dasharray="4,3"/>
      <line x1="60" y1="40" x2="440" y2="40" stroke="#1e293b" stroke-width="1" stroke-dasharray="4,3"/>
      <!-- y-axis labels -->
      <text x="52" y="164" fill="#64748b" font-size="10" text-anchor="end">0%</text>
      <text x="52" y="124" fill="#64748b" font-size="10" text-anchor="end">25%</text>
      <text x="52" y="84" fill="#64748b" font-size="10" text-anchor="end">50%</text>
      <text x="52" y="44" fill="#64748b" font-size="10" text-anchor="end">75%</text>
      <!-- bar: long-horizon DAgger 94% -->
      <rect x="120" y="23" width="80" height="137" fill="#C74634" rx="4"/>
      <text x="160" y="17" fill="#e2e8f0" font-size="12" text-anchor="middle" font-weight="bold">94%</text>
      <text x="160" y="178" fill="#94a3b8" font-size="11" text-anchor="middle">Long-Horizon</text>
      <text x="160" y="191" fill="#94a3b8" font-size="10" text-anchor="middle">(Run166)</text>
      <!-- bar: standard single-step 88% -->
      <rect x="280" y="35" width="80" height="125" fill="#38bdf8" rx="4"/>
      <text x="320" y="29" fill="#e2e8f0" font-size="12" text-anchor="middle" font-weight="bold">88%</text>
      <text x="320" y="178" fill="#94a3b8" font-size="11" text-anchor="middle">Standard</text>
      <text x="320" y="191" fill="#94a3b8" font-size="10" text-anchor="middle">(Single-step)</text>
    </svg>
  </div>

  <div class="card">
    <h2>Run166 Key Facts</h2>
    <div class="metric"><div class="val">10</div><div class="lbl">Correction Steps / Demo</div></div>
    <div class="metric"><div class="val">10s</div><div class="lbl">Expert Video per Demo</div></div>
    <div class="metric"><div class="val">10202</div><div class="lbl">Service Port</div></div>
    <div class="metric"><div class="val">94%</div><div class="lbl">SR Long-Horizon</div></div>
    <p style="margin-top:1rem; color:#94a3b8; font-size:0.85rem;">
      Expert labels full 10-step recovery plan from 10s video — 10 corrections from 1 demo.
      Essential for assembly tasks requiring coordinated multi-step recovery.
    </p>
  </div>

  <div class="card">
    <h2>Tags</h2>
    <span class="tag">dagger</span>
    <span class="tag">long-horizon</span>
    <span class="tag">10-step-sequence</span>
    <span class="tag">assembly</span>
    <span class="tag">run166</span>
    <span class="tag">multi-step-recovery</span>
    <span class="tag">imitation-learning</span>
  </div>

  <div class="card endpoints">
    <h2>Endpoints</h2>
    <a href="/health">/health — service health check</a>
    <a href="/dagger/run166/plan">/dagger/run166/plan — get 10-step correction plan</a>
    <a href="/dagger/run166/status">/dagger/run166/status — run166 training status</a>
  </div>
</body>
</html>
"""


if _FASTAPI_AVAILABLE:
    app = FastAPI(title=SERVICE_NAME, version="1.0.0")

    @app.get("/health")
    async def health():
        return JSONResponse({"status": "ok", "port": PORT, "service": SERVICE_NAME,
                             "timestamp": datetime.utcnow().isoformat()})

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return HTMLResponse(content=_HTML)

    @app.get("/dagger/run166/plan")
    async def dagger_run166_plan():
        """Return a mock 10-step long-horizon correction plan."""
        return JSONResponse({
            "run_id": "run166",
            "plan_type": "long_horizon_10step",
            "num_corrections": 10,
            "corrections": [
                {"step": i + 1,
                 "action": f"correction_step_{i + 1}",
                 "description": f"Expert correction {i + 1}: adjust trajectory waypoint for sub-task {i + 1}"}
                for i in range(10)
            ],
            "source_video_duration_s": 10,
            "use_case": "assembly",
            "sr_long_horizon": 0.94,
            "sr_standard": 0.88,
            "generated_at": datetime.utcnow().isoformat()
        })

    @app.get("/dagger/run166/status")
    async def dagger_run166_status():
        """Return mock run166 training status."""
        return JSONResponse({
            "run_id": "run166",
            "status": "complete",
            "policy": "gr00t_n1.6_dagger_run166",
            "steps_trained": 5000,
            "success_rate_15step": 0.94,
            "baseline_sr": 0.88,
            "improvement_pct": 6.8,
            "port": PORT,
            "checked_at": datetime.utcnow().isoformat()
        })

else:
    # Fallback: stdlib http.server
    import http.server

    class _Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):  # silence access log
            pass

        def _send(self, code, ctype, body):
            enc = body.encode() if isinstance(body, str) else body
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(enc)))
            self.end_headers()
            self.wfile.write(enc)

        def do_GET(self):
            if self.path == "/health":
                self._send(200, "application/json",
                           json.dumps({"status": "ok", "port": PORT, "service": SERVICE_NAME}))
            elif self.path in ("/", ""):
                self._send(200, "text/html", _HTML)
            elif self.path == "/dagger/run166/plan":
                self._send(200, "application/json",
                           json.dumps({"run_id": "run166", "plan_type": "long_horizon_10step",
                                       "num_corrections": 10}))
            elif self.path == "/dagger/run166/status":
                self._send(200, "application/json",
                           json.dumps({"run_id": "run166", "status": "complete",
                                       "success_rate_15step": 0.94}))
            else:
                self._send(404, "application/json", json.dumps({"error": "not found"}))


if __name__ == "__main__":
    if _FASTAPI_AVAILABLE:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        server = http.server.HTTPServer(("0.0.0.0", PORT), _Handler)
        print(f"[{SERVICE_NAME}] fallback http.server listening on port {PORT}")
        server.serve_forever()
