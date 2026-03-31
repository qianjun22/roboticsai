"""DAgger Run121 Planner — synthesis run combining diversity + force + curriculum + reward.

Port: 10022
Cycle: 491B
"""

from __future__ import annotations

import json
import random
from datetime import datetime, timezone

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import HTMLResponse, JSONResponse
    from pydantic import BaseModel
    import uvicorn
    _FASTAPI = True
except ImportError:
    _FASTAPI = False
    from http.server import BaseHTTPRequestHandler, HTTPServer
    from urllib.parse import urlparse

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
PORT = 10022
RUN_ID = "run121"
COMPONENT_NAMES = ["diversity", "force", "curriculum", "reward"]
PRIOR_BEST_SR = 95.0
PROJECTED_SR_ITER8 = 96.0
COMPONENT_CONTRIBUTIONS = {
    "diversity": 28,
    "force": 24,
    "curriculum": 27,
    "reward": 21,
}

# ---------------------------------------------------------------------------
# Business logic
# ---------------------------------------------------------------------------

def _plan_run121(components: list[str]) -> dict:
    valid = [c for c in components if c in COMPONENT_CONTRIBUTIONS]
    if not valid:
        valid = COMPONENT_NAMES[:]
    total_weight = sum(COMPONENT_CONTRIBUTIONS[c] for c in valid)
    base_sr = PRIOR_BEST_SR
    synthesis_gain = round(len(valid) * 0.25 + random.uniform(0.1, 0.4), 2)
    projected_sr = round(min(base_sr + synthesis_gain, 99.9), 2)
    synthesis_gain_pct = round((projected_sr - base_sr) / base_sr * 100, 3)
    iters = max(4, 10 - len(valid))
    return {
        "projected_sr": projected_sr,
        "iterations_to_target": iters,
        "prior_best_sr": base_sr,
        "synthesis_gain_pct": synthesis_gain_pct,
        "components_used": valid,
        "total_contribution_weight": total_weight,
    }


def _run_status() -> dict:
    return {
        "run_id": RUN_ID,
        "components": len(COMPONENT_NAMES),
        "projected_sr_iter8": PROJECTED_SR_ITER8,
        "prior_best_run119": PRIOR_BEST_SR,
        "synthesis_approach": "+".join(COMPONENT_NAMES),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------
DAR_BG = "#0f172a"
ORACLE_RED = "#C74634"
SKY_BLUE = "#38bdf8"

HTML_DASHBOARD = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>DAgger Run121 Planner — OCI Robot Cloud</title>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{background:{bg};color:#e2e8f0;font-family:'Segoe UI',system-ui,sans-serif;padding:2rem}}
    h1{{color:{red};font-size:1.6rem;margin-bottom:0.25rem}}
    .sub{{color:{sky};font-size:0.9rem;margin-bottom:2rem}}
    .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:1.25rem;margin-bottom:2rem}}
    .card{{background:#1e293b;border:1px solid #334155;border-radius:10px;padding:1.25rem}}
    .card .label{{font-size:0.75rem;color:#94a3b8;text-transform:uppercase;letter-spacing:.06em;margin-bottom:.4rem}}
    .card .value{{font-size:2rem;font-weight:700;color:{sky}}}
    .card .unit{{font-size:0.8rem;color:#64748b;margin-top:.15rem}}
    .badge{{display:inline-block;background:{red};color:#fff;border-radius:6px;padding:.15rem .6rem;font-size:0.75rem;margin-left:.5rem}}
    .chart-wrap{{background:#1e293b;border:1px solid #334155;border-radius:10px;padding:1.5rem;margin-bottom:2rem}}
    .chart-title{{color:{sky};font-size:1rem;font-weight:600;margin-bottom:1rem}}
    table{{width:100%;border-collapse:collapse;font-size:.875rem}}
    th{{text-align:left;color:#94a3b8;border-bottom:1px solid #334155;padding:.5rem 0}}
    td{{padding:.5rem 0;border-bottom:1px solid #1e293b}}
    td.num{{text-align:right;color:{sky};font-weight:600}}
    footer{{margin-top:2rem;font-size:.75rem;color:#475569;text-align:center}}
  </style>
</head>
<body>
  <h1>DAgger Run121 Planner <span class="badge">Synthesis</span></h1>
  <div class="sub">Port 10022 &mdash; Cycle 491B &mdash; Combining diversity + force + curriculum + reward</div>

  <div class="grid">
    <div class="card"><div class="label">Projected SR (iter 8)</div><div class="value">96.0%</div><div class="unit">vs prior best 95.0%</div></div>
    <div class="card"><div class="label">Prior Best (run119)</div><div class="value">95.0%</div><div class="unit">single-component champion</div></div>
    <div class="card"><div class="label">Synthesis Gain</div><div class="value">+1.0%</div><div class="unit">absolute SR improvement</div></div>
    <div class="card"><div class="label">Components Combined</div><div class="value">4</div><div class="unit">diversity · force · curriculum · reward</div></div>
  </div>

  <div class="chart-wrap">
    <div class="chart-title">Component Contribution Breakdown</div>
    <svg viewBox="0 0 520 180" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:560px;display:block;margin:0 auto">
      <!-- diversity -->
      <rect x="30"  y="20"  width="145" height="34" rx="4" fill="{red}" opacity="0.85"/>
      <text x="182" y="43" fill="#e2e8f0" font-size="13">diversity — 28%</text>
      <!-- force -->
      <rect x="30"  y="66"  width="124" height="34" rx="4" fill="{sky}" opacity="0.85"/>
      <text x="161" y="89" fill="#e2e8f0" font-size="13">force — 24%</text>
      <!-- curriculum -->
      <rect x="30"  y="112" width="140" height="34" rx="4" fill="{red}" opacity="0.65"/>
      <text x="177" y="135" fill="#e2e8f0" font-size="13">curriculum — 27%</text>
      <!-- reward -->
      <rect x="30"  y="158" width="109" height="18" rx="4" fill="{sky}" opacity="0.65"/>
      <text x="146" y="172" fill="#e2e8f0" font-size="13">reward — 21%</text>
    </svg>
  </div>

  <div class="chart-wrap">
    <div class="chart-title">SR Comparison: Run119 vs Run121 (projected)</div>
    <svg viewBox="0 0 520 120" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:560px;display:block;margin:0 auto">
      <!-- x-axis labels -->
      <text x="80"  y="112" fill="#94a3b8" font-size="12" text-anchor="middle">Run119 (best prior)</text>
      <text x="300" y="112" fill="#94a3b8" font-size="12" text-anchor="middle">Run121 (projected)</text>
      <!-- bars -->
      <rect x="30"  y="12" width="100" height="88" rx="4" fill="{red}" opacity="0.75"/>
      <text x="80"  y="8"  fill="{red}"  font-size="13" font-weight="bold" text-anchor="middle">95.0%</text>
      <rect x="250" y="3"  width="100" height="97" rx="4" fill="{sky}" opacity="0.85"/>
      <text x="300" y="0"  fill="{sky}"  font-size="13" font-weight="bold" text-anchor="middle" dy="13">96.0%</text>
    </svg>
  </div>

  <footer>OCI Robot Cloud &mdash; DAgger Run121 Planner &mdash; {ts}</footer>
</body>
</html>
""".format(bg=DAR_BG, red=ORACLE_RED, sky=SKY_BLUE, ts=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
if _FASTAPI:
    app = FastAPI(title="DAgger Run121 Planner", version="1.0.0")

    class PlanRequest(BaseModel):
        components: list[str] = COMPONENT_NAMES[:]

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return HTMLResponse(content=HTML_DASHBOARD)

    @app.get("/health")
    async def health():
        return JSONResponse({"status": "ok", "service": "dagger_run121_planner", "port": PORT,
                             "timestamp": datetime.now(timezone.utc).isoformat()})

    @app.post("/dagger/run121/plan")
    async def plan(req: PlanRequest):
        return JSONResponse(_plan_run121(req.components))

    @app.get("/dagger/run121/status")
    async def status():
        return JSONResponse(_run_status())

# ---------------------------------------------------------------------------
# Stdlib fallback
# ---------------------------------------------------------------------------
else:
    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            path = urlparse(self.path).path
            if path == "/":
                body = HTML_DASHBOARD.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
            elif path == "/health":
                body = json.dumps({"status": "ok", "service": "dagger_run121_planner", "port": PORT}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
            elif path == "/dagger/run121/status":
                body = json.dumps(_run_status()).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
            else:
                body = b"{\"error\": \"not found\"}"
                self.send_response(404)
                self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            path = urlparse(self.path).path
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length)
            try:
                data = json.loads(raw)
            except Exception:
                data = {}
            if path == "/dagger/run121/plan":
                components = data.get("components", COMPONENT_NAMES)
                body = json.dumps(_plan_run121(components)).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
            else:
                body = b"{\"error\": \"not found\"}"
                self.send_response(404)
                self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):  # silence default logs
            pass

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    if _FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        print(f"FastAPI not available — starting stdlib HTTPServer on port {PORT}")
        server = HTTPServer(("0.0.0.0", PORT), _Handler)
        server.serve_forever()
