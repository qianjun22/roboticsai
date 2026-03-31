"""DAgger Run175 Planner — online policy evaluation with real-time learning curve.

FastAPI service on port 10238.
Tracks SR after every 25 corrections; raises stagnation alert if no >10%
improvement over any 50-correction window.
"""

PORT = 10238
SERVICE_NAME = "dagger_run175_planner"

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    _FASTAPI = True
except ImportError:
    _FASTAPI = False

# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------
_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>DAgger Run175 Planner</title>
  <style>
    body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; margin: 0; padding: 2rem; }
    h1   { color: #C74634; margin-bottom: 0.25rem; }
    h2   { color: #38bdf8; font-size: 1rem; font-weight: 400; margin-top: 0; }
    .card { background: #1e293b; border-radius: 0.75rem; padding: 1.5rem; margin: 1rem 0; }
    .badge { display: inline-block; background: #C74634; color: #fff;
             border-radius: 0.4rem; padding: 0.15rem 0.6rem; font-size: 0.8rem; }
    table  { width: 100%; border-collapse: collapse; margin-top: 0.5rem; }
    th, td { text-align: left; padding: 0.4rem 0.6rem; border-bottom: 1px solid #334155; font-size: 0.9rem; }
    th     { color: #38bdf8; }
    .bar-label { font-size: 0.75rem; fill: #94a3b8; }
    .bar-val   { font-size: 0.78rem; fill: #e2e8f0; font-weight: bold; }
  </style>
</head>
<body>
  <h1>DAgger Run175 Planner</h1>
  <h2>Online policy evaluation &mdash; port 10238 &nbsp;<span class="badge">LIVE</span></h2>

  <div class="card">
    <h3 style="color:#38bdf8;margin-top:0">Success Rate vs Corrections (mini-eval N=10, &plusmn;6%)</h3>
    <svg viewBox="0 0 480 220" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:480px">
      <!-- grid lines -->
      <line x1="60" y1="20" x2="60" y2="180" stroke="#334155" stroke-width="1"/>
      <line x1="60" y1="180" x2="460" y2="180" stroke="#334155" stroke-width="1"/>
      <!-- y-axis ticks -->
      <text x="52" y="184" text-anchor="end" class="bar-label">0%</text>
      <text x="52" y="137" text-anchor="end" class="bar-label">50%</text>
      <text x="52" y="90"  text-anchor="end" class="bar-label">75%</text>
      <text x="52" y="43"  text-anchor="end" class="bar-label">100%</text>
      <line x1="60" y1="136" x2="460" y2="136" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,3"/>
      <line x1="60" y1="88"  x2="460" y2="88"  stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,3"/>
      <!-- bars: SR 67% 74% 81% 87% across 4 correction buckets -->
      <!-- bar 1: 0-25 corrections, SR=67%, height = 67/100 * 160 = 107.2 -->
      <rect x="80"  y="72.8" width="60" height="107.2" rx="4" fill="#C74634" opacity="0.85"/>
      <text x="110" y="67"   text-anchor="middle" class="bar-val">67%</text>
      <text x="110" y="197"  text-anchor="middle" class="bar-label">0-25</text>
      <!-- bar 2: 25-50, SR=74%, height = 118.4 -->
      <rect x="175" y="61.6" width="60" height="118.4" rx="4" fill="#C74634" opacity="0.90"/>
      <text x="205" y="56"   text-anchor="middle" class="bar-val">74%</text>
      <text x="205" y="197"  text-anchor="middle" class="bar-label">25-50</text>
      <!-- bar 3: 50-75, SR=81%, height = 129.6 -->
      <rect x="270" y="50.4" width="60" height="129.6" rx="4" fill="#38bdf8" opacity="0.90"/>
      <text x="300" y="44"   text-anchor="middle" class="bar-val">81%</text>
      <text x="300" y="197"  text-anchor="middle" class="bar-label">50-75</text>
      <!-- bar 4: 75-100, SR=87%, height = 139.2 -->
      <rect x="365" y="40.8" width="60" height="139.2" rx="4" fill="#38bdf8"/>
      <text x="395" y="35"   text-anchor="middle" class="bar-val">87%</text>
      <text x="395" y="197"  text-anchor="middle" class="bar-label">75-100</text>
      <!-- x-axis label -->
      <text x="260" y="215" text-anchor="middle" class="bar-label">Corrections (cumulative)</text>
    </svg>
  </div>

  <div class="card">
    <h3 style="color:#38bdf8;margin-top:0">Run175 Config</h3>
    <table>
      <tr><th>Parameter</th><th>Value</th></tr>
      <tr><td>Eval frequency</td><td>Every 25 corrections</td></tr>
      <tr><td>Mini-eval episodes (N)</td><td>10</td></tr>
      <tr><td>SR accuracy</td><td>&plusmn;6%</td></tr>
      <tr><td>Stagnation alert threshold</td><td>&lt;10% improvement over 50 corrections</td></tr>
      <tr><td>Target SR</td><td>&ge;85%</td></tr>
      <tr><td>Checkpoint cadence</td><td>Every 50 corrections</td></tr>
    </table>
  </div>

  <div class="card" style="font-size:0.85rem;color:#64748b">
    Endpoints: <code>GET /health</code> &nbsp; <code>GET /dagger/run175/plan</code> &nbsp; <code>GET /dagger/run175/status</code>
  </div>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# Mock data helpers
# ---------------------------------------------------------------------------

def _mock_plan():
    return {
        "run": "run175",
        "strategy": "online_dagger",
        "eval_every_corrections": 25,
        "mini_eval_n": 10,
        "sr_accuracy_pct": 6,
        "stagnation_window": 50,
        "stagnation_threshold_pct": 10,
        "target_sr": 0.85,
        "checkpoint_cadence": 50,
        "sr_curve": [
            {"correction_range": "0-25",   "sr": 0.67},
            {"correction_range": "25-50",  "sr": 0.74},
            {"correction_range": "50-75",  "sr": 0.81},
            {"correction_range": "75-100", "sr": 0.87},
        ],
    }


def _mock_status():
    return {
        "run": "run175",
        "status": "running",
        "corrections_so_far": 87,
        "current_sr": 0.84,
        "stagnation_alert": False,
        "last_checkpoint": "ckpt_run175_c050.pt",
        "eta_to_target": "~13 more corrections",
    }


# ---------------------------------------------------------------------------
# FastAPI app (or stdlib fallback)
# ---------------------------------------------------------------------------

if _FASTAPI:
    app = FastAPI(title=SERVICE_NAME, version="1.0.0")

    @app.get("/health")
    def health():
        return JSONResponse({"status": "ok", "port": PORT, "service": SERVICE_NAME})

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return _HTML

    @app.get("/dagger/run175/plan")
    def dagger_plan():
        return JSONResponse(_mock_plan())

    @app.get("/dagger/run175/status")
    def dagger_status():
        return JSONResponse(_mock_status())

else:
    # ---------------------------------------------------------------------------
    # Stdlib fallback
    # ---------------------------------------------------------------------------
    import json
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class _Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):  # silence default logging
            pass

        def _send(self, code, body, content_type="application/json"):
            data = body.encode() if isinstance(body, str) else body
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.path == "/health":
                self._send(200, json.dumps({"status": "ok", "port": PORT, "service": SERVICE_NAME}))
            elif self.path == "/":
                self._send(200, _HTML, "text/html; charset=utf-8")
            elif self.path == "/dagger/run175/plan":
                self._send(200, json.dumps(_mock_plan()))
            elif self.path == "/dagger/run175/status":
                self._send(200, json.dumps(_mock_status()))
            else:
                self._send(404, json.dumps({"error": "not found"}))


if __name__ == "__main__":
    if _FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        print(f"[{SERVICE_NAME}] fastapi not found — starting stdlib HTTPServer on port {PORT}")
        server = HTTPServer(("0.0.0.0", PORT), _Handler)
        server.serve_forever()
