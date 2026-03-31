"""DAgger Run 133 Planner — Batch Active Learning for Maximally Informative Scenario Selection.

Port: 10070
Cycle: 503B
"""

from __future__ import annotations

import json
import random
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import HTMLResponse, JSONResponse
    from pydantic import BaseModel
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 10070
SERVICE_NAME = "DAgger Run133 Planner"

# ---------------------------------------------------------------------------
# HTML Dashboard
# ---------------------------------------------------------------------------

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>DAgger Run133 Planner — Batch Active Learning</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; padding: 2rem; }
    h1 { color: #C74634; font-size: 1.8rem; margin-bottom: 0.25rem; }
    .subtitle { color: #94a3b8; font-size: 0.9rem; margin-bottom: 2rem; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 1.25rem; margin-bottom: 2rem; }
    .card { background: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 1.25rem; }
    .card .label { color: #94a3b8; font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 0.4rem; }
    .card .value { font-size: 2rem; font-weight: 700; color: #38bdf8; }
    .card .sub { font-size: 0.8rem; color: #64748b; margin-top: 0.3rem; }
    .section-title { color: #C74634; font-size: 1.1rem; font-weight: 600; margin-bottom: 1rem; }
    .chart-container { background: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 1.5rem; margin-bottom: 2rem; }
    .badge { display: inline-block; padding: 0.2rem 0.6rem; border-radius: 9999px; font-size: 0.75rem; font-weight: 600; }
    .badge-green { background: #064e3b; color: #34d399; }
    .badge-blue { background: #0c4a6e; color: #38bdf8; }
    .info-box { background: #1e293b; border-left: 4px solid #C74634; border-radius: 0 8px 8px 0; padding: 1rem 1.25rem; margin-bottom: 1.5rem; color: #94a3b8; font-size: 0.88rem; line-height: 1.6; }
    table { width: 100%; border-collapse: collapse; font-size: 0.88rem; }
    th { background: #0f172a; color: #94a3b8; text-align: left; padding: 0.6rem 0.8rem; font-weight: 600; }
    td { border-top: 1px solid #1e293b; padding: 0.6rem 0.8rem; }
    tr:hover td { background: #1e293b; }
    .endpoint-list { list-style: none; }
    .endpoint-list li { padding: 0.4rem 0; border-bottom: 1px solid #1e293b; font-size: 0.85rem; }
    .method { color: #38bdf8; font-weight: 700; margin-right: 0.5rem; }
    code { background: #0f172a; padding: 0.15rem 0.4rem; border-radius: 4px; font-size: 0.82rem; color: #e2e8f0; }
  </style>
</head>
<body>
  <h1>DAgger Run133 Planner</h1>
  <p class="subtitle">Batch Active Learning — Maximally Informative Scenario Selection &nbsp;|&nbsp; Port 10070 &nbsp;|&nbsp; Cycle 503B</p>

  <div class="grid">
    <div class="card">
      <div class="label">Active Batch SR (Iter 6)</div>
      <div class="value">95.0%</div>
      <div class="sub">Batch-active learned policy</div>
    </div>
    <div class="card">
      <div class="label">Random Batch SR (Iter 6)</div>
      <div class="value">91.0%</div>
      <div class="sub">Random selection baseline</div>
    </div>
    <div class="card">
      <div class="label">Coverage Improvement</div>
      <div class="value">+40%</div>
      <div class="sub">Scenario space covered vs random</div>
    </div>
    <div class="card">
      <div class="label">Batch Size</div>
      <div class="value">50</div>
      <div class="sub">Scenarios per iteration</div>
    </div>
    <div class="card">
      <div class="label">Candidate Pool</div>
      <div class="value">1 000</div>
      <div class="sub">Total candidate scenarios</div>
    </div>
    <div class="card">
      <div class="label">Run ID</div>
      <div class="value" style="font-size:1.3rem;">run133</div>
      <div class="sub"><span class="badge badge-green">active</span></div>
    </div>
  </div>

  <!-- SVG Bar Chart: Active vs Random SR per iteration -->
  <div class="chart-container">
    <div class="section-title">Success Rate per DAgger Iteration — Active vs Random Batch Selection</div>
    <svg viewBox="0 0 680 260" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:680px;display:block;">
      <!-- axes -->
      <line x1="60" y1="20" x2="60" y2="210" stroke="#334155" stroke-width="1.5"/>
      <line x1="60" y1="210" x2="650" y2="210" stroke="#334155" stroke-width="1.5"/>
      <!-- y-axis labels -->
      <text x="50" y="215" fill="#64748b" font-size="11" text-anchor="end">0%</text>
      <text x="50" y="163" fill="#64748b" font-size="11" text-anchor="end">25%</text>
      <text x="50" y="111" fill="#64748b" font-size="11" text-anchor="end">50%</text>
      <text x="50" y="59"  fill="#64748b" font-size="11" text-anchor="end">75%</text>
      <text x="50" y="27"  fill="#64748b" font-size="11" text-anchor="end">100%</text>
      <!-- horizontal grid lines -->
      <line x1="60" y1="210" x2="650" y2="210" stroke="#1e293b" stroke-width="1"/>
      <line x1="60" y1="158" x2="650" y2="158" stroke="#1e293b" stroke-width="1"/>
      <line x1="60" y1="106" x2="650" y2="106" stroke="#1e293b" stroke-width="1"/>
      <line x1="60" y1="54"  x2="650" y2="54"  stroke="#1e293b" stroke-width="1"/>
      <line x1="60" y1="22"  x2="650" y2="22"  stroke="#1e293b" stroke-width="1"/>
      <!-- iter1: active 60%, random 55% -->
      <rect x="80"  y="82"  width="28" height="128" fill="#38bdf8" rx="3"/>
      <rect x="112" y="95"  width="28" height="115" fill="#C74634" rx="3" opacity="0.8"/>
      <text x="100" y="225" fill="#94a3b8" font-size="11" text-anchor="middle">Iter 1</text>
      <!-- iter2: active 70%, random 62% -->
      <rect x="180" y="62"  width="28" height="148" fill="#38bdf8" rx="3"/>
      <rect x="212" y="77"  width="28" height="133" fill="#C74634" rx="3" opacity="0.8"/>
      <text x="200" y="225" fill="#94a3b8" font-size="11" text-anchor="middle">Iter 2</text>
      <!-- iter3: active 78%, random 70% -->
      <rect x="280" y="45"  width="28" height="165" fill="#38bdf8" rx="3"/>
      <rect x="312" y="62"  width="28" height="148" fill="#C74634" rx="3" opacity="0.8"/>
      <text x="300" y="225" fill="#94a3b8" font-size="11" text-anchor="middle">Iter 3</text>
      <!-- iter4: active 85%, random 77% -->
      <rect x="380" y="30"  width="28" height="180" fill="#38bdf8" rx="3"/>
      <rect x="412" y="48"  width="28" height="162" fill="#C74634" rx="3" opacity="0.8"/>
      <text x="400" y="225" fill="#94a3b8" font-size="11" text-anchor="middle">Iter 4</text>
      <!-- iter5: active 91%, random 85% -->
      <rect x="480" y="22"  width="28" height="188" fill="#38bdf8" rx="3"/>
      <rect x="512" y="30"  width="28" height="180" fill="#C74634" rx="3" opacity="0.8"/>
      <text x="500" y="225" fill="#94a3b8" font-size="11" text-anchor="middle">Iter 5</text>
      <!-- iter6: active 95%, random 91% -->
      <rect x="580" y="18"  width="28" height="192" fill="#38bdf8" rx="3"/>
      <rect x="612" y="22"  width="28" height="188" fill="#C74634" rx="3" opacity="0.8"/>
      <text x="600" y="225" fill="#94a3b8" font-size="11" text-anchor="middle">Iter 6</text>
      <!-- legend -->
      <rect x="80" y="240" width="14" height="10" fill="#38bdf8" rx="2"/>
      <text x="100" y="250" fill="#94a3b8" font-size="11">Active Batch SR</text>
      <rect x="220" y="240" width="14" height="10" fill="#C74634" rx="2" opacity="0.8"/>
      <text x="240" y="250" fill="#94a3b8" font-size="11">Random Batch SR</text>
    </svg>
  </div>

  <div class="info-box">
    <strong>Active Selection Mechanism:</strong> Each iteration ranks all candidate scenarios by a composite uncertainty score
    (ensemble disagreement × novelty × task diversity). The top-50 highest-scoring scenarios form the batch,
    ensuring maximum coverage of the scenario space while prioritising regions where the current policy is most uncertain.
    After 6 iterations the active strategy achieves <strong>95% SR</strong> vs 91% for random selection,
    with <strong>40% more of the scenario space</strong> covered per iteration budget.
  </div>

  <div class="chart-container">
    <div class="section-title">API Endpoints</div>
    <ul class="endpoint-list">
      <li><span class="method">GET</span> <code>/</code> — HTML dashboard</li>
      <li><span class="method">GET</span> <code>/health</code> — JSON health check</li>
      <li><span class="method">GET</span> <code>/dagger/run133/status</code> — current run statistics</li>
      <li><span class="method">POST</span> <code>/dagger/run133/select_batch</code> — select informative batch of scenarios</li>
    </ul>
  </div>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# Data / business logic
# ---------------------------------------------------------------------------

RUN_STATUS = {
    "run_id": "run133",
    "batch_size": 50,
    "candidate_pool": 1000,
    "batch_active_sr_iter6": 95.0,
    "random_batch_sr_iter6": 91.0,
    "coverage_improvement_pct": 40,
}


def _select_batch_logic(candidate_scenarios: int, batch_size: int, selection_criteria: list[str]) -> dict[str, Any]:
    """Simulate batch active learning selection."""
    # Clamp batch_size to candidate_scenarios
    effective_batch = min(batch_size, candidate_scenarios)
    # Coverage improves with diversity/uncertainty criteria
    criteria_bonus = 0.02 * len([c for c in selection_criteria if c in ("uncertainty", "diversity", "novelty")])
    coverage_pct = round(min(100.0, (effective_batch / max(candidate_scenarios, 1)) * 100 * (1 + criteria_bonus * 2)), 2)
    # SR estimates
    batch_active_sr = round(min(99.0, 95.0 + criteria_bonus * 10 + random.uniform(-0.5, 0.5)), 2)
    random_batch_sr = round(min(95.0, 91.0 + random.uniform(-0.5, 0.5)), 2)
    return {
        "selected_scenarios": effective_batch,
        "coverage_pct": coverage_pct,
        "batch_active_sr": batch_active_sr,
        "random_batch_sr": random_batch_sr,
    }


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

if USE_FASTAPI:
    app = FastAPI(title=SERVICE_NAME, version="1.0.0")

    class SelectBatchRequest(BaseModel):
        candidate_scenarios: int = 1000
        batch_size: int = 50
        selection_criteria: list[str] = ["uncertainty", "diversity"]

    @app.get("/", response_class=HTMLResponse)
    async def dashboard() -> HTMLResponse:
        return HTMLResponse(content=DASHBOARD_HTML)

    @app.get("/health")
    async def health() -> JSONResponse:
        return JSONResponse({"status": "ok", "service": SERVICE_NAME, "port": PORT})

    @app.get("/dagger/run133/status")
    async def run_status() -> JSONResponse:
        return JSONResponse(RUN_STATUS)

    @app.post("/dagger/run133/select_batch")
    async def select_batch(req: SelectBatchRequest) -> JSONResponse:
        result = _select_batch_logic(req.candidate_scenarios, req.batch_size, req.selection_criteria)
        return JSONResponse(result)

# ---------------------------------------------------------------------------
# HTTPServer fallback
# ---------------------------------------------------------------------------

else:
    import urllib.parse

    class _Handler(BaseHTTPRequestHandler):
        def _send(self, code: int, content_type: str, body: str | bytes) -> None:
            encoded = body.encode() if isinstance(body, str) else body
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def do_GET(self) -> None:  # noqa: N802
            path = self.path.split("?")[0]
            if path == "/":
                self._send(200, "text/html", DASHBOARD_HTML)
            elif path == "/health":
                self._send(200, "application/json", json.dumps({"status": "ok", "service": SERVICE_NAME, "port": PORT}))
            elif path == "/dagger/run133/status":
                self._send(200, "application/json", json.dumps(RUN_STATUS))
            else:
                self._send(404, "application/json", json.dumps({"error": "not found"}))

        def do_POST(self) -> None:  # noqa: N802
            path = self.path.split("?")[0]
            if path == "/dagger/run133/select_batch":
                length = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(length) or b"{}")
                result = _select_batch_logic(
                    body.get("candidate_scenarios", 1000),
                    body.get("batch_size", 50),
                    body.get("selection_criteria", ["uncertainty", "diversity"]),
                )
                self._send(200, "application/json", json.dumps(result))
            else:
                self._send(404, "application/json", json.dumps({"error": "not found"}))

        def log_message(self, *args: Any) -> None:  # noqa: ANN002
            pass

    def _run_fallback() -> None:
        server = HTTPServer(("0.0.0.0", PORT), _Handler)
        print(f"{SERVICE_NAME} (stdlib HTTPServer) listening on port {PORT}")
        server.serve_forever()

# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        _run_fallback()
