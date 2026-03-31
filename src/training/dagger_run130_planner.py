"""dagger_run130_planner.py — Milestone DAgger run130 planner service.

All five systems combined (synthesis, uncertainty-guided, fleet, preference,
continual), targeting 97% success rate.

Port: 10058
"""

from __future__ import annotations

import json
from typing import Any

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import HTMLResponse, JSONResponse
    from pydantic import BaseModel
    import uvicorn
    _FASTAPI = True
except ImportError:
    _FASTAPI = False
    from http.server import BaseHTTPRequestHandler, HTTPServer
    import urllib.parse as _urlparse

PORT = 10058
RUN_ID = "run130"
MILESTONE_SR = 97.0
PRIOR_BEST_SR = 96.0
COST_PER_ITER = 12.9
TOTAL_ITERS = 10
TOTAL_COST = COST_PER_ITER * TOTAL_ITERS
ALL_SYSTEMS = ["synthesis", "uncertainty_guided", "fleet", "preference", "continual"]

JOURNEY = [
    ("BC baseline", 5),
    ("DAgger run1", 18),
    ("run10", 34),
    ("run30", 52),
    ("run60", 71),
    ("run90", 84),
    ("run110", 91),
    ("run120", 94),
    ("run125", 96),
    ("run130", 97),
]

HTML_DASHBOARD = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>DAgger Run130 Planner — OCI Robot Cloud</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; min-height: 100vh; }
    header { background: #1e293b; border-bottom: 3px solid #C74634; padding: 1.25rem 2rem; display: flex; align-items: center; gap: 1rem; }
    header h1 { font-size: 1.5rem; color: #f8fafc; letter-spacing: .02em; }
    header .badge { background: #C74634; color: #fff; font-size: .75rem; font-weight: 700; padding: .2rem .65rem; border-radius: 9999px; text-transform: uppercase; }
    main { max-width: 1100px; margin: 2rem auto; padding: 0 1.5rem; }
    .kpi-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1.25rem; margin-bottom: 2rem; }
    .kpi { background: #1e293b; border: 1px solid #334155; border-radius: .75rem; padding: 1.25rem 1.5rem; }
    .kpi .label { font-size: .75rem; text-transform: uppercase; letter-spacing: .08em; color: #94a3b8; margin-bottom: .4rem; }
    .kpi .value { font-size: 2.25rem; font-weight: 800; color: #38bdf8; }
    .kpi .sub { font-size: .8rem; color: #64748b; margin-top: .25rem; }
    .kpi.highlight .value { color: #C74634; }
    .section-title { font-size: 1.1rem; font-weight: 700; color: #38bdf8; margin-bottom: 1rem; letter-spacing: .03em; text-transform: uppercase; }
    .card { background: #1e293b; border: 1px solid #334155; border-radius: .75rem; padding: 1.5rem; margin-bottom: 1.75rem; }
    .chart-wrap { overflow-x: auto; }
    svg text { font-family: 'Segoe UI', system-ui, sans-serif; }
    .systems { display: flex; flex-wrap: wrap; gap: .75rem; }
    .sys-pill { background: #0f172a; border: 1.5px solid #38bdf8; color: #38bdf8; border-radius: 9999px; padding: .35rem 1rem; font-size: .85rem; font-weight: 600; }
    .endpoint-list { list-style: none; }
    .endpoint-list li { padding: .45rem 0; border-bottom: 1px solid #1e293b; font-size: .9rem; color: #94a3b8; }
    .endpoint-list li span { color: #38bdf8; font-weight: 600; margin-right: .6rem; }
    footer { text-align: center; padding: 2rem; color: #334155; font-size: .8rem; }
  </style>
</head>
<body>
<header>
  <h1>DAgger Run130 Planner</h1>
  <span class="badge">Milestone</span>
  <span style="margin-left:auto;color:#94a3b8;font-size:.85rem;">OCI Robot Cloud — Port {port}</span>
</header>
<main>
  <div class="kpi-row">
    <div class="kpi highlight">
      <div class="label">Projected SR (iter 10)</div>
      <div class="value">97%</div>
      <div class="sub">Prior best: 96%</div>
    </div>
    <div class="kpi">
      <div class="label">Total Cost</div>
      <div class="value">$129</div>
      <div class="sub">$12.90 / iteration × 10</div>
    </div>
    <div class="kpi">
      <div class="label">Systems Combined</div>
      <div class="value">5</div>
      <div class="sub">All systems active</div>
    </div>
    <div class="kpi">
      <div class="label">SR Improvement</div>
      <div class="value">+1pp</div>
      <div class="sub">over run125 (96%)</div>
    </div>
  </div>

  <div class="card">
    <div class="section-title">DAgger Journey: 5% → 97%</div>
    <div class="chart-wrap">
      <svg viewBox="0 0 860 260" width="100%" xmlns="http://www.w3.org/2000/svg">
        <!-- axes -->
        <line x1="70" y1="20" x2="70" y2="210" stroke="#334155" stroke-width="1.5"/>
        <line x1="70" y1="210" x2="840" y2="210" stroke="#334155" stroke-width="1.5"/>
        <!-- y-axis labels -->
        <text x="60" y="214" fill="#64748b" font-size="11" text-anchor="end">0%</text>
        <text x="60" y="165" fill="#64748b" font-size="11" text-anchor="end">25%</text>
        <text x="60" y="116" fill="#64748b" font-size="11" text-anchor="end">50%</text>
        <text x="60" y="67"  fill="#64748b" font-size="11" text-anchor="end">75%</text>
        <text x="60" y="24"  fill="#64748b" font-size="11" text-anchor="end">100%</text>
        <!-- grid lines -->
        <line x1="70" y1="165" x2="840" y2="165" stroke="#1e293b" stroke-width="1" stroke-dasharray="4,4"/>
        <line x1="70" y1="116" x2="840" y2="116" stroke="#1e293b" stroke-width="1" stroke-dasharray="4,4"/>
        <line x1="70" y1="67"  x2="840" y2="67"  stroke="#1e293b" stroke-width="1" stroke-dasharray="4,4"/>
        <!-- bars: 10 entries, width=62, gap=14, start=78 -->
        <!-- BC baseline 5% => h=9.5, y=200.5 -->
        <rect x="78"  y="200" width="55" height="10" fill="#334155" rx="3"/>
        <text x="105" y="225" fill="#64748b" font-size="9" text-anchor="middle">BC</text>
        <text x="105" y="196" fill="#94a3b8" font-size="10" text-anchor="middle">5%</text>
        <!-- run1 18% => h=34.2 -->
        <rect x="154" y="176" width="55" height="34" fill="#38bdf8" rx="3" opacity="0.55"/>
        <text x="181" y="225" fill="#64748b" font-size="9" text-anchor="middle">run1</text>
        <text x="181" y="172" fill="#38bdf8" font-size="10" text-anchor="middle">18%</text>
        <!-- run10 34% => h=64.6 -->
        <rect x="230" y="145" width="55" height="65" fill="#38bdf8" rx="3" opacity="0.60"/>
        <text x="257" y="225" fill="#64748b" font-size="9" text-anchor="middle">run10</text>
        <text x="257" y="141" fill="#38bdf8" font-size="10" text-anchor="middle">34%</text>
        <!-- run30 52% => h=98.8 -->
        <rect x="306" y="111" width="55" height="99" fill="#38bdf8" rx="3" opacity="0.65"/>
        <text x="333" y="225" fill="#64748b" font-size="9" text-anchor="middle">run30</text>
        <text x="333" y="107" fill="#38bdf8" font-size="10" text-anchor="middle">52%</text>
        <!-- run60 71% => h=134.9 -->
        <rect x="382" y="75" width="55" height="135" fill="#38bdf8" rx="3" opacity="0.70"/>
        <text x="409" y="225" fill="#64748b" font-size="9" text-anchor="middle">run60</text>
        <text x="409" y="71" fill="#38bdf8" font-size="10" text-anchor="middle">71%</text>
        <!-- run90 84% => h=159.6 -->
        <rect x="458" y="50" width="55" height="160" fill="#38bdf8" rx="3" opacity="0.75"/>
        <text x="485" y="225" fill="#64748b" font-size="9" text-anchor="middle">run90</text>
        <text x="485" y="46" fill="#38bdf8" font-size="10" text-anchor="middle">84%</text>
        <!-- run110 91% => h=172.9 -->
        <rect x="534" y="37" width="55" height="173" fill="#38bdf8" rx="3" opacity="0.80"/>
        <text x="561" y="225" fill="#64748b" font-size="9" text-anchor="middle">run110</text>
        <text x="561" y="33" fill="#38bdf8" font-size="10" text-anchor="middle">91%</text>
        <!-- run120 94% => h=178.6 -->
        <rect x="610" y="31" width="55" height="179" fill="#38bdf8" rx="3" opacity="0.85"/>
        <text x="637" y="225" fill="#64748b" font-size="9" text-anchor="middle">run120</text>
        <text x="637" y="27" fill="#38bdf8" font-size="10" text-anchor="middle">94%</text>
        <!-- run125 96% => h=182.4 -->
        <rect x="686" y="28" width="55" height="182" fill="#38bdf8" rx="3" opacity="0.90"/>
        <text x="713" y="225" fill="#64748b" font-size="9" text-anchor="middle">run125</text>
        <text x="713" y="24" fill="#38bdf8" font-size="10" text-anchor="middle">96%</text>
        <!-- run130 97% MILESTONE => h=184.3 -->
        <rect x="762" y="26" width="55" height="184" fill="#C74634" rx="3"/>
        <text x="789" y="225" fill="#C74634" font-size="9" font-weight="700" text-anchor="middle">run130</text>
        <text x="789" y="22" fill="#C74634" font-size="11" font-weight="800" text-anchor="middle">97% ★</text>
      </svg>
    </div>
  </div>

  <div class="card">
    <div class="section-title">All 5 Systems Active</div>
    <div class="systems">
      <span class="sys-pill">synthesis</span>
      <span class="sys-pill">uncertainty_guided</span>
      <span class="sys-pill">fleet</span>
      <span class="sys-pill">preference</span>
      <span class="sys-pill">continual</span>
    </div>
  </div>

  <div class="card">
    <div class="section-title">API Endpoints</div>
    <ul class="endpoint-list">
      <li><span>GET</span>/  — this dashboard</li>
      <li><span>GET</span>/health  — JSON health check</li>
      <li><span>GET</span>/dagger/run130/status  — milestone status JSON</li>
      <li><span>POST</span>/dagger/run130/plan  — plan with custom config</li>
    </ul>
  </div>
</main>
<footer>OCI Robot Cloud &copy; 2026 Oracle — DAgger Run130 Milestone Planner</footer>
</body>
</html>
""".replace("{port}", str(PORT))


if _FASTAPI:
    app = FastAPI(
        title="DAgger Run130 Planner",
        description="Milestone DAgger run130 — all systems combined, targeting 97% SR",
        version="1.0.0",
    )

    class PlanConfig(BaseModel):
        config: dict[str, bool] = {
            "synthesis": True,
            "uncertainty": True,
            "fleet": True,
            "preference": True,
            "continual": True,
        }

    @app.get("/", response_class=HTMLResponse)
    async def dashboard() -> HTMLResponse:
        return HTMLResponse(content=HTML_DASHBOARD)

    @app.get("/health")
    async def health() -> JSONResponse:
        return JSONResponse({
            "status": "ok",
            "service": "dagger_run130_planner",
            "port": PORT,
            "run_id": RUN_ID,
            "milestone": True,
        })

    @app.get("/dagger/run130/status")
    async def run130_status() -> JSONResponse:
        return JSONResponse({
            "run_id": RUN_ID,
            "milestone": True,
            "projected_sr_iter10": MILESTONE_SR,
            "prior_best": PRIOR_BEST_SR,
            "cost_per_iter_usd": COST_PER_ITER,
            "total_cost_usd": TOTAL_COST,
            "all_systems": ALL_SYSTEMS,
        })

    @app.post("/dagger/run130/plan")
    async def plan(body: PlanConfig) -> JSONResponse:
        cfg = body.config
        active = sum(1 for v in cfg.values() if v)
        boost = active * 0.2
        projected_sr = min(MILESTONE_SR, PRIOR_BEST_SR + boost)
        iters = max(1, round((projected_sr - PRIOR_BEST_SR) / 0.1))
        cost = round(iters * COST_PER_ITER, 2)
        return JSONResponse({
            "projected_sr": projected_sr,
            "iterations_to_target": iters,
            "cost_usd": cost,
            "prior_best_sr": PRIOR_BEST_SR,
        })

    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=PORT)

else:
    # stdlib fallback
    class _Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:  # type: ignore[override]
            pass

        def _send(self, code: int, ctype: str, body: str | bytes) -> None:
            if isinstance(body, str):
                body = body.encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            path = self.path.split("?")[0]
            if path == "/":
                self._send(200, "text/html", HTML_DASHBOARD)
            elif path == "/health":
                self._send(200, "application/json", json.dumps({
                    "status": "ok", "service": "dagger_run130_planner", "port": PORT
                }))
            elif path == "/dagger/run130/status":
                self._send(200, "application/json", json.dumps({
                    "run_id": RUN_ID, "milestone": True,
                    "projected_sr_iter10": MILESTONE_SR, "prior_best": PRIOR_BEST_SR,
                    "cost_per_iter_usd": COST_PER_ITER, "total_cost_usd": TOTAL_COST,
                    "all_systems": ALL_SYSTEMS,
                }))
            else:
                self._send(404, "application/json", json.dumps({"error": "not found"}))

        def do_POST(self) -> None:
            path = self.path.split("?")[0]
            if path == "/dagger/run130/plan":
                length = int(self.headers.get("Content-Length", 0))
                raw = self.rfile.read(length)
                try:
                    body = json.loads(raw)
                    cfg = body.get("config", {})
                except Exception:
                    cfg = {}
                active = sum(1 for v in cfg.values() if v)
                boost = active * 0.2
                projected_sr = min(MILESTONE_SR, PRIOR_BEST_SR + boost)
                iters = max(1, round((projected_sr - PRIOR_BEST_SR) / 0.1))
                cost = round(iters * COST_PER_ITER, 2)
                self._send(200, "application/json", json.dumps({
                    "projected_sr": projected_sr, "iterations_to_target": iters,
                    "cost_usd": cost, "prior_best_sr": PRIOR_BEST_SR,
                }))
            else:
                self._send(404, "application/json", json.dumps({"error": "not found"}))

    if __name__ == "__main__":
        server = HTTPServer(("0.0.0.0", PORT), _Handler)
        print(f"Serving on http://0.0.0.0:{PORT} (stdlib HTTPServer)")
        server.serve_forever()
