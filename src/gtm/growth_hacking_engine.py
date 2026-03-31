"""Growth Hacking Engine — ICE-scored growth experiment management (Impact × Confidence × Ease).

Port: 10071
Cycle: 503B
"""

from __future__ import annotations

import json
import random
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

try:
    from fastapi import FastAPI, Query
    from fastapi.responses import HTMLResponse, JSONResponse
    from pydantic import BaseModel
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 10071
SERVICE_NAME = "Growth Hacking Engine"

# ---------------------------------------------------------------------------
# HTML Dashboard
# ---------------------------------------------------------------------------

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Growth Hacking Engine — ICE Experiment Manager</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; padding: 2rem; }
    h1 { color: #C74634; font-size: 1.8rem; margin-bottom: 0.25rem; }
    .subtitle { color: #94a3b8; font-size: 0.9rem; margin-bottom: 2rem; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1.25rem; margin-bottom: 2rem; }
    .card { background: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 1.25rem; }
    .card .label { color: #94a3b8; font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 0.4rem; }
    .card .value { font-size: 2rem; font-weight: 700; color: #38bdf8; }
    .card .sub { font-size: 0.8rem; color: #64748b; margin-top: 0.3rem; }
    .section-title { color: #C74634; font-size: 1.1rem; font-weight: 600; margin-bottom: 1rem; }
    .chart-container { background: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 1.5rem; margin-bottom: 2rem; }
    .badge { display: inline-block; padding: 0.2rem 0.6rem; border-radius: 9999px; font-size: 0.75rem; font-weight: 600; }
    .badge-green { background: #064e3b; color: #34d399; }
    .badge-yellow { background: #451a03; color: #fbbf24; }
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
    .ice-bar-bg { background: #0f172a; border-radius: 9999px; height: 8px; width: 100%; margin-top: 4px; }
    .ice-bar { height: 8px; border-radius: 9999px; background: linear-gradient(90deg, #C74634, #38bdf8); }
  </style>
</head>
<body>
  <h1>Growth Hacking Engine</h1>
  <p class="subtitle">ICE-Scored Experiment Management (Impact &times; Confidence &times; Ease) &nbsp;|&nbsp; Port 10071 &nbsp;|&nbsp; Cycle 503B</p>

  <div class="grid">
    <div class="card">
      <div class="label">Experiments Queued</div>
      <div class="value">23</div>
      <div class="sub">Pending prioritisation</div>
    </div>
    <div class="card">
      <div class="label">Win Rate</div>
      <div class="value">37%</div>
      <div class="sub">Across all completed experiments</div>
    </div>
    <div class="card">
      <div class="label">Pipeline Lift per Win</div>
      <div class="value">+12%</div>
      <div class="sub">Average pipeline uplift</div>
    </div>
    <div class="card">
      <div class="label">Top ICE Score</div>
      <div class="value">8.4</div>
      <div class="sub">NVIDIA partner listing</div>
    </div>
  </div>

  <!-- SVG Bar Chart: Top experiments by ICE score -->
  <div class="chart-container">
    <div class="section-title">Top Experiments by ICE Score</div>
    <svg viewBox="0 0 660 220" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:660px;display:block;">
      <!-- axes -->
      <line x1="200" y1="20" x2="200" y2="180" stroke="#334155" stroke-width="1.5"/>
      <line x1="200" y1="180" x2="640" y2="180" stroke="#334155" stroke-width="1.5"/>
      <!-- x-axis ticks -->
      <text x="200" y="196" fill="#64748b" font-size="10" text-anchor="middle">0</text>
      <text x="288" y="196" fill="#64748b" font-size="10" text-anchor="middle">2</text>
      <text x="376" y="196" fill="#64748b" font-size="10" text-anchor="middle">4</text>
      <text x="464" y="196" fill="#64748b" font-size="10" text-anchor="middle">6</text>
      <text x="552" y="196" fill="#64748b" font-size="10" text-anchor="middle">8</text>
      <text x="618" y="196" fill="#64748b" font-size="10" text-anchor="middle">10</text>
      <!-- vertical grid lines -->
      <line x1="288" y1="20" x2="288" y2="180" stroke="#1e293b" stroke-width="1"/>
      <line x1="376" y1="20" x2="376" y2="180" stroke="#1e293b" stroke-width="1"/>
      <line x1="464" y1="20" x2="464" y2="180" stroke="#1e293b" stroke-width="1"/>
      <line x1="552" y1="20" x2="552" y2="180" stroke="#1e293b" stroke-width="1"/>
      <!-- Bar 1: NVIDIA partner listing 8.4 (score/10 * 440 = 369.6) -->
      <rect x="201" y="30" width="370" height="30" fill="#38bdf8" rx="4"/>
      <text x="10" y="50" fill="#e2e8f0" font-size="11">NVIDIA partner listing</text>
      <text x="580" y="50" fill="#38bdf8" font-size="12" font-weight="700">8.4</text>
      <!-- Bar 2: GTC talk 7.9 (7.9/10 * 440 = 347.6) -->
      <rect x="201" y="80" width="348" height="30" fill="#C74634" rx="4" opacity="0.9"/>
      <text x="10" y="100" fill="#e2e8f0" font-size="11">GTC talk submission</text>
      <text x="558" y="100" fill="#C74634" font-size="12" font-weight="700">7.9</text>
      <!-- Bar 3: Case study SEO 7.2 (7.2/10 * 440 = 316.8) -->
      <rect x="201" y="130" width="317" height="30" fill="#7c3aed" rx="4" opacity="0.85"/>
      <text x="10" y="150" fill="#e2e8f0" font-size="11">Case study SEO</text>
      <text x="527" y="150" fill="#a78bfa" font-size="12" font-weight="700">7.2</text>
      <!-- x-axis label -->
      <text x="420" y="212" fill="#64748b" font-size="11" text-anchor="middle">ICE Score (0–10)</text>
    </svg>
  </div>

  <div class="info-box">
    <strong>ICE Framework:</strong> Each experiment is scored on <strong>Impact</strong> (expected pipeline uplift, 1–10),
    <strong>Confidence</strong> (probability of winning based on prior data, 1–10), and
    <strong>Ease</strong> (effort / time-to-run, 1–10). The composite ICE score = I &times; C &times; E / 100.
    Experiments are executed in descending ICE order. A win is recorded when the primary metric improves
    by &ge;5% over the control. Each win historically adds <strong>+12% pipeline</strong>.
  </div>

  <div class="chart-container">
    <div class="section-title">Experiment Backlog Sample</div>
    <table>
      <thead>
        <tr>
          <th>ID</th><th>Experiment</th><th>Impact</th><th>Confidence</th><th>Ease</th><th>ICE</th><th>Status</th>
        </tr>
      </thead>
      <tbody>
        <tr><td>EXP-001</td><td>NVIDIA partner listing</td><td>9</td><td>8</td><td>9</td><td>8.4*</td><td><span class="badge badge-blue">queued</span></td></tr>
        <tr><td>EXP-002</td><td>GTC talk submission</td><td>9</td><td>8</td><td>8</td><td>7.9*</td><td><span class="badge badge-blue">queued</span></td></tr>
        <tr><td>EXP-003</td><td>Case study SEO</td><td>8</td><td>8</td><td>8</td><td>7.2*</td><td><span class="badge badge-blue">queued</span></td></tr>
        <tr><td>EXP-004</td><td>Outbound sequence A/B</td><td>7</td><td>7</td><td>8</td><td>5.6</td><td><span class="badge badge-yellow">running</span></td></tr>
        <tr><td>EXP-005</td><td>LinkedIn thought leadership</td><td>6</td><td>6</td><td>9</td><td>4.9</td><td><span class="badge badge-green">won</span></td></tr>
      </tbody>
    </table>
    <p style="color:#64748b;font-size:0.78rem;margin-top:0.6rem;">* Normalised composite score displayed; raw = I&times;C&times;E/100 rounded.</p>
  </div>

  <div class="chart-container">
    <div class="section-title">API Endpoints</div>
    <ul class="endpoint-list">
      <li><span class="method">GET</span> <code>/</code> — HTML dashboard</li>
      <li><span class="method">GET</span> <code>/health</code> — JSON health check</li>
      <li><span class="method">GET</span> <code>/growth/experiments?status=&lt;queued|running|won|lost&gt;</code> — list experiments with ICE scores</li>
      <li><span class="method">POST</span> <code>/growth/log_result</code> — log experiment result and get next recommendation</li>
    </ul>
  </div>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

EXPERIMENTS: list[dict[str, Any]] = [
    {"id": "EXP-001", "name": "NVIDIA partner listing",       "impact": 9, "confidence": 8, "ease": 9, "ice_score": 8.4, "status": "queued",  "projected_pipeline_lift_pct": 15},
    {"id": "EXP-002", "name": "GTC talk submission",           "impact": 9, "confidence": 8, "ease": 8, "ice_score": 7.9, "status": "queued",  "projected_pipeline_lift_pct": 14},
    {"id": "EXP-003", "name": "Case study SEO",               "impact": 8, "confidence": 8, "ease": 8, "ice_score": 7.2, "status": "queued",  "projected_pipeline_lift_pct": 12},
    {"id": "EXP-004", "name": "Outbound sequence A/B",        "impact": 7, "confidence": 7, "ease": 8, "ice_score": 5.6, "status": "running", "projected_pipeline_lift_pct": 10},
    {"id": "EXP-005", "name": "LinkedIn thought leadership",  "impact": 6, "confidence": 6, "ease": 9, "ice_score": 4.9, "status": "won",     "projected_pipeline_lift_pct": 9},
    {"id": "EXP-006", "name": "Webinar co-host with partner", "impact": 7, "confidence": 6, "ease": 7, "ice_score": 4.6, "status": "queued",  "projected_pipeline_lift_pct": 11},
    {"id": "EXP-007", "name": "Cold email personalisation",   "impact": 6, "confidence": 7, "ease": 8, "ice_score": 4.5, "status": "queued",  "projected_pipeline_lift_pct": 8},
    {"id": "EXP-008", "name": "Referral programme launch",    "impact": 8, "confidence": 5, "ease": 6, "ice_score": 4.2, "status": "lost",    "projected_pipeline_lift_pct": 13},
]

WIN_RATE: float = 37.0

NEXT_EXPERIMENT_ID: str = "EXP-001"  # highest ICE in queue


def _get_experiments(status: str | None) -> list[dict[str, Any]]:
    if status:
        return [e for e in EXPERIMENTS if e["status"] == status]
    return EXPERIMENTS


def _log_result_logic(experiment_id: str, metric: str, result: float) -> dict[str, Any]:
    """Simulate logging an experiment result."""
    # Find next highest-ICE queued experiment
    queued = sorted([e for e in EXPERIMENTS if e["status"] == "queued"], key=lambda x: -x["ice_score"])
    next_exp = queued[0]["name"] if queued else "No further experiments queued"
    # Simulate win-rate update (slight random walk)
    new_wr = round(max(0.0, min(100.0, WIN_RATE + random.uniform(-2.0, 4.0))), 1)
    learnings = (
        f"Experiment {experiment_id} recorded {metric}={result:.3f}. "
        f"Result {'exceeds' if result >= 0.05 else 'does not meet'} the ≥5% win threshold. "
        "Updating ICE confidence priors for similar experiments."
    )
    return {
        "updated_win_rate": new_wr,
        "learnings": learnings,
        "next_experiment": next_exp,
    }


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

if USE_FASTAPI:
    app = FastAPI(title=SERVICE_NAME, version="1.0.0")

    class LogResultRequest(BaseModel):
        experiment_id: str
        metric: str
        result: float

    @app.get("/", response_class=HTMLResponse)
    async def dashboard() -> HTMLResponse:
        return HTMLResponse(content=DASHBOARD_HTML)

    @app.get("/health")
    async def health() -> JSONResponse:
        return JSONResponse({"status": "ok", "service": SERVICE_NAME, "port": PORT})

    @app.get("/growth/experiments")
    async def get_experiments(status: str | None = Query(default=None)) -> JSONResponse:
        return JSONResponse({"experiments": _get_experiments(status), "total": len(EXPERIMENTS), "queued": 23, "win_rate_pct": WIN_RATE})

    @app.post("/growth/log_result")
    async def log_result(req: LogResultRequest) -> JSONResponse:
        result = _log_result_logic(req.experiment_id, req.metric, req.result)
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
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path
            params = urllib.parse.parse_qs(parsed.query)
            if path == "/":
                self._send(200, "text/html", DASHBOARD_HTML)
            elif path == "/health":
                self._send(200, "application/json", json.dumps({"status": "ok", "service": SERVICE_NAME, "port": PORT}))
            elif path == "/growth/experiments":
                status = params.get("status", [None])[0]
                exps = _get_experiments(status)
                self._send(200, "application/json", json.dumps({"experiments": exps, "total": len(EXPERIMENTS), "queued": 23, "win_rate_pct": WIN_RATE}))
            else:
                self._send(404, "application/json", json.dumps({"error": "not found"}))

        def do_POST(self) -> None:  # noqa: N802
            path = self.path.split("?")[0]
            if path == "/growth/log_result":
                length = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(length) or b"{}")
                result = _log_result_logic(
                    body.get("experiment_id", "EXP-000"),
                    body.get("metric", "conversion_rate"),
                    float(body.get("result", 0.0)),
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
