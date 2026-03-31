"""DAgger Run156 Planner — curriculum-aware DAgger service.

Adapts correction difficulty to current success rate:
  SR < 60%   → easy (teacher always corrects)
  SR 60-80%  → medium (teacher corrects on deviation)
  SR > 80%   → hard / adversarial (sparse correction)

Port: 10162
"""

import json
import time
from typing import Any, Dict

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    _FASTAPI = True
except ImportError:
    _FASTAPI = False

PORT = 10162
SERVICE_NAME = "dagger_run156_planner"

_START_TIME = time.time()

# ---------------------------------------------------------------------------
# Mock state
# ---------------------------------------------------------------------------
_RUN156_STATE: Dict[str, Any] = {
    "run_id": "run156",
    "current_sr": 0.87,
    "difficulty": "hard",
    "episodes_collected": 4820,
    "corrections_applied": 1103,
    "curriculum_stage": 3,
    "status": "running",
}


def _difficulty_from_sr(sr: float) -> str:
    if sr < 0.60:
        return "easy"
    elif sr <= 0.80:
        return "medium"
    else:
        return "hard (adversarial)"


def _html_dashboard() -> str:
    return """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>DAgger Run156 Planner — Port 10162</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; padding: 2rem; }
    h1 { color: #C74634; font-size: 1.6rem; margin-bottom: 0.25rem; }
    .subtitle { color: #38bdf8; font-size: 0.9rem; margin-bottom: 2rem; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 1rem; margin-bottom: 2rem; }
    .card { background: #1e293b; border-radius: 8px; padding: 1.25rem; border: 1px solid #334155; }
    .card .label { font-size: 0.75rem; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.4rem; }
    .card .value { font-size: 1.5rem; font-weight: 700; color: #f1f5f9; }
    .chart-section { background: #1e293b; border-radius: 8px; padding: 1.5rem; border: 1px solid #334155; margin-bottom: 2rem; }
    .chart-section h2 { color: #38bdf8; font-size: 1rem; margin-bottom: 1.25rem; }
    .ladder { background: #1e293b; border-radius: 8px; padding: 1.5rem; border: 1px solid #334155; }
    .ladder h2 { color: #38bdf8; font-size: 1rem; margin-bottom: 1rem; }
    .ladder-item { display: flex; align-items: center; gap: 1rem; margin-bottom: 0.75rem; }
    .ladder-badge { border-radius: 4px; padding: 0.2rem 0.6rem; font-size: 0.75rem; font-weight: 600; min-width: 60px; text-align: center; }
    .easy { background: #14532d; color: #86efac; }
    .medium { background: #78350f; color: #fcd34d; }
    .hard { background: #7f1d1d; color: #fca5a5; }
    footer { margin-top: 2rem; font-size: 0.75rem; color: #475569; }
  </style>
</head>
<body>
  <h1>DAgger Run156 Planner</h1>
  <p class="subtitle">Curriculum-aware DAgger &mdash; Port 10162</p>

  <div class="grid">
    <div class="card"><div class="label">Current SR</div><div class="value" style="color:#38bdf8">87%</div></div>
    <div class="card"><div class="label">Difficulty</div><div class="value" style="color:#fca5a5">Hard</div></div>
    <div class="card"><div class="label">Episodes</div><div class="value">4,820</div></div>
    <div class="card"><div class="label">Corrections</div><div class="value">1,103</div></div>
    <div class="card"><div class="label">Stage</div><div class="value">3 / 3</div></div>
    <div class="card"><div class="label">Status</div><div class="value" style="color:#86efac">Running</div></div>
  </div>

  <div class="chart-section">
    <h2>Success Rate: Curriculum DAgger vs Flat Difficulty</h2>
    <svg viewBox="0 0 400 160" xmlns="http://www.w3.org/2000/svg" width="100%" style="max-width:480px">
      <!-- axes -->
      <line x1="60" y1="10" x2="60" y2="130" stroke="#475569" stroke-width="1"/>
      <line x1="60" y1="130" x2="390" y2="130" stroke="#475569" stroke-width="1"/>
      <!-- grid lines -->
      <line x1="60" y1="34" x2="390" y2="34" stroke="#334155" stroke-width="0.5" stroke-dasharray="4,3"/>
      <line x1="60" y1="58" x2="390" y2="58" stroke="#334155" stroke-width="0.5" stroke-dasharray="4,3"/>
      <line x1="60" y1="82" x2="390" y2="82" stroke="#334155" stroke-width="0.5" stroke-dasharray="4,3"/>
      <line x1="60" y1="106" x2="390" y2="106" stroke="#334155" stroke-width="0.5" stroke-dasharray="4,3"/>
      <!-- y labels -->
      <text x="52" y="37" fill="#94a3b8" font-size="9" text-anchor="end">100%</text>
      <text x="52" y="61" fill="#94a3b8" font-size="9" text-anchor="end">75%</text>
      <text x="52" y="85" fill="#94a3b8" font-size="9" text-anchor="end">50%</text>
      <text x="52" y="109" fill="#94a3b8" font-size="9" text-anchor="end">25%</text>
      <!-- bars: curriculum DAgger 95% -->
      <!-- bar height: 95/100 * 96 = 91.2; y = 130-91.2 = 38.8 -->
      <rect x="100" y="38" width="70" height="92" fill="#38bdf8" rx="3"/>
      <text x="135" y="33" fill="#38bdf8" font-size="11" font-weight="bold" text-anchor="middle">95%</text>
      <text x="135" y="146" fill="#cbd5e1" font-size="9" text-anchor="middle">Curriculum</text>
      <text x="135" y="156" fill="#cbd5e1" font-size="9" text-anchor="middle">DAgger</text>
      <!-- bars: flat difficulty 91% -->
      <!-- bar height: 91/100 * 96 = 87.36; y = 130-87.36 = 42.64 -->
      <rect x="220" y="43" width="70" height="87" fill="#C74634" rx="3"/>
      <text x="255" y="38" fill="#C74634" font-size="11" font-weight="bold" text-anchor="middle">91%</text>
      <text x="255" y="146" fill="#cbd5e1" font-size="9" text-anchor="middle">Flat</text>
      <text x="255" y="156" fill="#cbd5e1" font-size="9" text-anchor="middle">Difficulty</text>
    </svg>
  </div>

  <div class="ladder">
    <h2>Difficulty Ladder</h2>
    <div class="ladder-item">
      <span class="ladder-badge easy">Easy</span>
      <span>SR &lt; 60% — teacher always corrects every deviation</span>
    </div>
    <div class="ladder-item">
      <span class="ladder-badge medium">Medium</span>
      <span>SR 60–80% — teacher corrects on significant deviation (&gt;15°)</span>
    </div>
    <div class="ladder-item">
      <span class="ladder-badge hard">Hard</span>
      <span>SR &gt; 80% — adversarial / sparse correction, policy challenged</span>
    </div>
  </div>

  <footer>OCI Robot Cloud &mdash; DAgger Run156 Planner &mdash; Port 10162</footer>
</body>
</html>
"""


if _FASTAPI:
    app = FastAPI(title=SERVICE_NAME, version="1.0.0")

    @app.get("/health")
    def health():
        return JSONResponse({
            "status": "ok",
            "port": PORT,
            "service": SERVICE_NAME,
            "uptime_seconds": round(time.time() - _START_TIME, 1),
        })

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return HTMLResponse(_html_dashboard())

    @app.get("/dagger/run156/plan")
    def get_plan():
        sr = _RUN156_STATE["current_sr"]
        difficulty = _difficulty_from_sr(sr)
        return JSONResponse({
            "run_id": "run156",
            "current_sr": sr,
            "recommended_difficulty": difficulty,
            "plan": {
                "easy": {"correction_threshold_deg": 5, "teacher_rate": 1.0},
                "medium": {"correction_threshold_deg": 15, "teacher_rate": 0.6},
                "hard (adversarial)": {"correction_threshold_deg": 30, "teacher_rate": 0.2},
            }.get(difficulty, {}),
            "next_checkpoint_at_episodes": _RUN156_STATE["episodes_collected"] + 200,
        })

    @app.get("/dagger/run156/status")
    def get_status():
        return JSONResponse(_RUN156_STATE)

else:
    # Fallback: stdlib HTTP server
    import http.server
    import urllib.parse

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            path = urllib.parse.urlparse(self.path).path
            if path == "/health":
                body = json.dumps({"status": "ok", "port": PORT, "service": SERVICE_NAME}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
            elif path == "/dagger/run156/status":
                body = json.dumps(_RUN156_STATE).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
            else:
                body = _html_dashboard().encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    def _serve():
        server = http.server.HTTPServer(("0.0.0.0", PORT), _Handler)
        print(f"[{SERVICE_NAME}] fallback HTTP server on port {PORT}")
        server.serve_forever()


if __name__ == "__main__":
    if _FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        _serve()
