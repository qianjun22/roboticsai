"""DAgger Run 165 Planner — Compositional Task DAgger Service.

Port 10198 | Cycle 535B
Learns subtasks independently and composes them at test time.
40% data savings vs monolithic policy on 6-step tasks.
"""

import json
import time
from typing import Any, Dict

PORT = 10198
SERVICE_NAME = "dagger_run165_planner"

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

# ---------------------------------------------------------------------------
# Stub data
# ---------------------------------------------------------------------------

RUN165_STATUS = {
    "run_id": "dagger_run165",
    "strategy": "compositional",
    "status": "complete",
    "subtasks": {
        "pick": {"phases": ["reach", "grasp", "lift"], "sr": 0.97},
        "place": {"phases": ["carry", "lower", "release"], "sr": 0.94},
    },
    "metrics": {
        "compositional_sr": 0.94,
        "monolithic_sr": 0.87,
        "data_savings_pct": 40,
        "task_steps": 6,
        "avg_latency_ms": 231,
    },
    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
}

RUN165_PLAN = {
    "run_id": "dagger_run165",
    "plan_type": "compositional",
    "decomposition": [
        {"step": 1, "subtask": "pick", "phase": "reach",   "target": "cube_xyz"},
        {"step": 2, "subtask": "pick", "phase": "grasp",   "target": "cube_xyz"},
        {"step": 3, "subtask": "pick", "phase": "lift",    "target": "cube_xyz"},
        {"step": 4, "subtask": "place", "phase": "carry",  "target": "goal_xyz"},
        {"step": 5, "subtask": "place", "phase": "lower",  "target": "goal_xyz"},
        {"step": 6, "subtask": "place", "phase": "release", "target": "goal_xyz"},
    ],
    "data_savings_pct": 40,
    "notes": "Subtasks trained independently; composed sequentially at test time.",
}

# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>DAgger Run 165 Planner — Port 10198</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; padding: 2rem; }}
    h1 {{ color: #C74634; font-size: 1.6rem; margin-bottom: 0.25rem; }}
    h2 {{ color: #38bdf8; font-size: 1rem; margin: 1.5rem 0 0.5rem; }}
    .badge {{ display: inline-block; background: #1e293b; border: 1px solid #334155;
              border-radius: 4px; padding: 0.15rem 0.6rem; font-size: 0.78rem;
              color: #94a3b8; margin-left: 0.5rem; }}
    .card {{ background: #1e293b; border: 1px solid #334155; border-radius: 8px;
             padding: 1.2rem 1.5rem; margin-bottom: 1rem; }}
    .metric {{ display: flex; gap: 2rem; flex-wrap: wrap; margin-top: 0.5rem; }}
    .metric-item {{ text-align: center; }}
    .metric-value {{ font-size: 1.8rem; font-weight: 700; color: #38bdf8; }}
    .metric-label {{ font-size: 0.75rem; color: #64748b; margin-top: 0.2rem; }}
    .endpoint {{ background: #0f172a; border-left: 3px solid #C74634;
                 padding: 0.4rem 0.8rem; margin: 0.3rem 0; border-radius: 0 4px 4px 0;
                 font-family: monospace; font-size: 0.85rem; color: #94a3b8; }}
    svg text {{ font-family: 'Segoe UI', sans-serif; }}
  </style>
</head>
<body>
  <h1>DAgger Run 165 Planner <span class="badge">port 10198</span></h1>
  <p style="color:#64748b;font-size:0.85rem;">Compositional Task DAgger — subtasks learned independently, composed at test time</p>

  <h2>Success Rate: Compositional vs Monolithic (6-Step Tasks)</h2>
  <div class="card">
    <svg width="480" height="200" viewBox="0 0 480 200" xmlns="http://www.w3.org/2000/svg">
      <!-- axes -->
      <line x1="60" y1="10" x2="60" y2="160" stroke="#334155" stroke-width="1.5"/>
      <line x1="60" y1="160" x2="460" y2="160" stroke="#334155" stroke-width="1.5"/>

      <!-- y gridlines & labels -->
      <line x1="60" y1="10"  x2="460" y2="10"  stroke="#1e293b" stroke-width="1"/>
      <line x1="60" y1="43"  x2="460" y2="43"  stroke="#1e293b" stroke-width="1"/>
      <line x1="60" y1="77"  x2="460" y2="77"  stroke="#1e293b" stroke-width="1"/>
      <line x1="60" y1="110" x2="460" y2="110" stroke="#1e293b" stroke-width="1"/>
      <text x="55" y="14"  text-anchor="end" fill="#64748b" font-size="11">100%</text>
      <text x="55" y="47"  text-anchor="end" fill="#64748b" font-size="11">75%</text>
      <text x="55" y="81"  text-anchor="end" fill="#64748b" font-size="11">50%</text>
      <text x="55" y="114" text-anchor="end" fill="#64748b" font-size="11">25%</text>
      <text x="55" y="163" text-anchor="end" fill="#64748b" font-size="11">0%</text>

      <!-- Compositional 94% -->
      <!-- bar height = 94% * 150px = 141px; y = 160 - 141 = 19 -->
      <rect x="110" y="19" width="80" height="141" fill="#38bdf8" rx="3"/>
      <text x="150" y="14" text-anchor="middle" fill="#38bdf8" font-size="13" font-weight="700">94%</text>
      <text x="150" y="178" text-anchor="middle" fill="#94a3b8" font-size="11">Compositional</text>
      <text x="150" y="191" text-anchor="middle" fill="#64748b" font-size="10">(Run 165)</text>

      <!-- Monolithic 87% -->
      <!-- bar height = 87% * 150px = 130.5px; y = 160 - 130.5 = 29.5 -->
      <rect x="270" y="30" width="80" height="130" fill="#C74634" rx="3"/>
      <text x="310" y="25" text-anchor="middle" fill="#C74634" font-size="13" font-weight="700">87%</text>
      <text x="310" y="178" text-anchor="middle" fill="#94a3b8" font-size="11">Monolithic</text>
      <text x="310" y="191" text-anchor="middle" fill="#64748b" font-size="10">(Baseline)</text>

      <!-- delta annotation -->
      <text x="400" y="70" fill="#a3e635" font-size="12" font-weight="600">+7pp SR</text>
      <text x="400" y="86" fill="#a3e635" font-size="11">40% fewer</text>
      <text x="400" y="100" fill="#a3e635" font-size="11">demos</text>
    </svg>
  </div>

  <h2>Task Decomposition</h2>
  <div class="card">
    <div class="metric">
      <div class="metric-item"><div class="metric-value" style="color:#38bdf8">Pick</div>
        <div class="metric-label">reach → grasp → lift</div></div>
      <div class="metric-item"><div class="metric-value" style="color:#C74634">Place</div>
        <div class="metric-label">carry → lower → release</div></div>
      <div class="metric-item"><div class="metric-value">40%</div>
        <div class="metric-label">data savings vs monolithic</div></div>
      <div class="metric-item"><div class="metric-value">6</div>
        <div class="metric-label">task steps</div></div>
    </div>
  </div>

  <h2>Endpoints</h2>
  <div class="card">
    <div class="endpoint">GET /health</div>
    <div class="endpoint">GET /</div>
    <div class="endpoint">GET /dagger/run165/plan</div>
    <div class="endpoint">GET /dagger/run165/status</div>
  </div>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

if HAS_FASTAPI:
    app = FastAPI(
        title="DAgger Run 165 Planner",
        description="Compositional Task DAgger: learn subtasks independently, compose at test time.",
        version="1.0.0",
    )

    @app.get("/health")
    def health() -> Dict[str, Any]:
        return {"status": "ok", "port": PORT, "service": SERVICE_NAME}

    @app.get("/", response_class=HTMLResponse)
    def dashboard() -> str:
        return DASHBOARD_HTML

    @app.get("/dagger/run165/plan")
    def get_plan() -> Dict[str, Any]:
        return RUN165_PLAN

    @app.get("/dagger/run165/status")
    def get_status() -> Dict[str, Any]:
        return RUN165_STATUS

# ---------------------------------------------------------------------------
# Fallback HTTP server
# ---------------------------------------------------------------------------

else:
    import http.server
    import socketserver

    class _Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):  # silence default logging
            pass

        def do_GET(self):
            if self.path == "/health":
                body = json.dumps({"status": "ok", "port": PORT, "service": SERVICE_NAME}).encode()
                ctype = "application/json"
            elif self.path == "/dagger/run165/plan":
                body = json.dumps(RUN165_PLAN).encode()
                ctype = "application/json"
            elif self.path == "/dagger/run165/status":
                body = json.dumps(RUN165_STATUS).encode()
                ctype = "application/json"
            else:
                body = DASHBOARD_HTML.encode()
                ctype = "text/html"
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    def _serve():
        with socketserver.TCPServer(("", PORT), _Handler) as httpd:
            print(f"{SERVICE_NAME} fallback server running on port {PORT}")
            httpd.serve_forever()

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if HAS_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        _serve()
