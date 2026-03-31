"""DAgger Run158 Planner — intervention minimization service (port 10170).

Strategy: run autonomously until uncertainty > 0.4, request intervention only
then. Target <10% intervention rate, ultimately <5%.
"""

import json
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = 10170
SERVICE_NAME = "dagger_run158_planner"

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    _FASTAPI = True
except ImportError:
    _FASTAPI = False

# ---------------------------------------------------------------------------
# Dashboard HTML
# ---------------------------------------------------------------------------

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>DAgger Run158 Planner</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: #0f172a;
      color: #e2e8f0;
      font-family: 'Segoe UI', system-ui, sans-serif;
      padding: 2rem;
    }
    h1 { color: #38bdf8; font-size: 1.8rem; margin-bottom: 0.25rem; }
    .subtitle { color: #94a3b8; margin-bottom: 2rem; font-size: 0.95rem; }
    .badge {
      display: inline-block;
      background: #C74634;
      color: #fff;
      border-radius: 4px;
      padding: 0.2rem 0.7rem;
      font-size: 0.8rem;
      font-weight: 600;
      margin-left: 0.75rem;
      vertical-align: middle;
    }
    .card {
      background: #1e293b;
      border: 1px solid #334155;
      border-radius: 10px;
      padding: 1.5rem;
      margin-bottom: 1.5rem;
    }
    .card h2 { color: #38bdf8; font-size: 1.1rem; margin-bottom: 1rem; }
    .metric-row { display: flex; gap: 1.5rem; flex-wrap: wrap; margin-bottom: 1rem; }
    .metric {
      background: #0f172a;
      border: 1px solid #334155;
      border-radius: 8px;
      padding: 0.9rem 1.2rem;
      min-width: 130px;
    }
    .metric .label { color: #94a3b8; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; }
    .metric .value { color: #38bdf8; font-size: 1.5rem; font-weight: 700; margin-top: 0.2rem; }
    .endpoint { color: #a5f3fc; font-family: monospace; font-size: 0.85rem; margin: 0.3rem 0; }
    svg text { font-family: 'Segoe UI', system-ui, sans-serif; }
  </style>
</head>
<body>
  <h1>DAgger Run158 Planner <span class="badge">PORT 10170</span></h1>
  <p class="subtitle">Intervention minimization — maximize autonomy while maintaining success rate</p>

  <div class="card">
    <h2>Autonomy Trend — Intervention Rate Over Time</h2>
    <svg width="520" height="200" viewBox="0 0 520 200">
      <!-- axes -->
      <line x1="60" y1="10" x2="60" y2="160" stroke="#334155" stroke-width="1.5"/>
      <line x1="60" y1="160" x2="500" y2="160" stroke="#334155" stroke-width="1.5"/>

      <!-- y-axis labels -->
      <text x="50" y="14" fill="#94a3b8" font-size="11" text-anchor="end">30%</text>
      <text x="50" y="52" fill="#94a3b8" font-size="11" text-anchor="end">20%</text>
      <text x="50" y="90" fill="#94a3b8" font-size="11" text-anchor="end">10%</text>
      <text x="50" y="128" fill="#94a3b8" font-size="11" text-anchor="end">5%</text>
      <text x="50" y="160" fill="#94a3b8" font-size="11" text-anchor="end">0%</text>

      <!-- gridlines -->
      <line x1="60" y1="14" x2="500" y2="14" stroke="#1e293b" stroke-width="1"/>
      <line x1="60" y1="52" x2="500" y2="52" stroke="#1e293b" stroke-width="1"/>
      <line x1="60" y1="90" x2="500" y2="90" stroke="#1e293b" stroke-width="1"/>
      <line x1="60" y1="128" x2="500" y2="128" stroke="#334155" stroke-dasharray="4 3" stroke-width="1"/>

      <!-- target line label -->
      <text x="502" y="131" fill="#C74634" font-size="10">target &lt;5%</text>

      <!-- bars: month1=23% → height=(23/30)*146≈112, month2=14%→68, month3=8%→39 -->
      <!-- month 1 -->
      <rect x="100" y="48" width="80" height="112" fill="#C74634" rx="4"/>
      <text x="140" y="42" fill="#e2e8f0" font-size="12" text-anchor="middle">23%</text>
      <text x="140" y="175" fill="#94a3b8" font-size="11" text-anchor="middle">Month 1</text>

      <!-- month 2 -->
      <rect x="220" y="92" width="80" height="68" fill="#38bdf8" rx="4"/>
      <text x="260" y="86" fill="#e2e8f0" font-size="12" text-anchor="middle">14%</text>
      <text x="260" y="175" fill="#94a3b8" font-size="11" text-anchor="middle">Month 2</text>

      <!-- month 3 -->
      <rect x="340" y="121" width="80" height="39" fill="#38bdf8" rx="4"/>
      <text x="380" y="115" fill="#e2e8f0" font-size="12" text-anchor="middle">8%</text>
      <text x="380" y="175" fill="#94a3b8" font-size="11" text-anchor="middle">Month 3</text>
    </svg>
  </div>

  <div class="card">
    <h2>Strategy</h2>
    <div class="metric-row">
      <div class="metric"><div class="label">Uncertainty Threshold</div><div class="value">&gt;0.4</div></div>
      <div class="metric"><div class="label">Intervention Target</div><div class="value">&lt;10%</div></div>
      <div class="metric"><div class="label">Stretch Target</div><div class="value">&lt;5%</div></div>
      <div class="metric"><div class="label">Current SR</div><div class="value">85%</div></div>
    </div>
    <p style="color:#94a3b8;font-size:0.9rem;">
      Run autonomously until ensemble uncertainty exceeds 0.4; request human
      intervention only then. DAgger loop aggregates expert corrections into
      the replay buffer and retrains every 500 steps.
    </p>
  </div>

  <div class="card">
    <h2>Endpoints</h2>
    <div class="endpoint">GET  /health</div>
    <div class="endpoint">GET  /</div>
    <div class="endpoint">GET  /dagger/run158/plan</div>
    <div class="endpoint">GET  /dagger/run158/status</div>
  </div>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# Mock data helpers
# ---------------------------------------------------------------------------

def _run158_plan():
    return {
        "run_id": "run158",
        "strategy": "uncertainty_gated_intervention",
        "uncertainty_threshold": 0.4,
        "intervention_target_pct": 10,
        "stretch_target_pct": 5,
        "replay_buffer_size": 5000,
        "retrain_every_steps": 500,
        "current_autonomy_pct": 92,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def _run158_status():
    return {
        "run_id": "run158",
        "status": "active",
        "episodes_completed": 1580,
        "intervention_rate_pct": 8.2,
        "current_sr_pct": 85,
        "last_retrain_step": 1500,
        "uncertainty_triggers_last_100": 7,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

if _FASTAPI:
    app = FastAPI(title=SERVICE_NAME, version="1.0.0")

    @app.get("/health")
    def health():
        return JSONResponse({"status": "ok", "port": PORT, "service": SERVICE_NAME})

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return HTMLResponse(content=DASHBOARD_HTML)

    @app.get("/dagger/run158/plan")
    def dagger_plan():
        return JSONResponse(_run158_plan())

    @app.get("/dagger/run158/status")
    def dagger_status():
        return JSONResponse(_run158_status())


# ---------------------------------------------------------------------------
# Fallback stdlib HTTP server
# ---------------------------------------------------------------------------

class _FallbackHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # silence default access log
        pass

    def _send(self, code, ctype, body):
        encoded = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self):
        if self.path == "/health":
            self._send(200, "application/json",
                       json.dumps({"status": "ok", "port": PORT, "service": SERVICE_NAME}))
        elif self.path in ("/", ""):
            self._send(200, "text/html", DASHBOARD_HTML)
        elif self.path == "/dagger/run158/plan":
            self._send(200, "application/json", json.dumps(_run158_plan()))
        elif self.path == "/dagger/run158/status":
            self._send(200, "application/json", json.dumps(_run158_status()))
        else:
            self._send(404, "application/json", json.dumps({"error": "not found"}))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if _FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        print(f"fastapi not available — falling back to stdlib HTTPServer on port {PORT}")
        server = HTTPServer(("0.0.0.0", PORT), _FallbackHandler)
        print(f"{SERVICE_NAME} listening on http://0.0.0.0:{PORT}")
        server.serve_forever()
