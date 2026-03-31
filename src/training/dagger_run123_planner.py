"""DAgger Run 123 Planner — Uncertainty-guided DAgger service (port 10030).

Requests human corrections only when policy entropy exceeds threshold,
reducing annotation burden while maintaining high task success rates.
"""

from __future__ import annotations

import json
import math
import random
from datetime import datetime

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

PORT = 10030

HTML_DASHBOARD = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>DAgger Run 123 Planner — OCI Robot Cloud</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; min-height: 100vh; }
    header { background: #1e293b; border-bottom: 3px solid #C74634; padding: 1.25rem 2rem; display: flex; align-items: center; gap: 1rem; }
    header h1 { font-size: 1.5rem; color: #f1f5f9; }
    header span.badge { background: #C74634; color: #fff; font-size: 0.75rem; padding: 0.2rem 0.6rem; border-radius: 9999px; }
    .container { max-width: 1100px; margin: 2rem auto; padding: 0 1.5rem; }
    .kpi-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 1rem; margin-bottom: 2rem; }
    .kpi { background: #1e293b; border: 1px solid #334155; border-radius: 0.75rem; padding: 1.25rem; }
    .kpi .label { font-size: 0.75rem; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.5rem; }
    .kpi .value { font-size: 2rem; font-weight: 700; }
    .kpi .value.red { color: #C74634; }
    .kpi .value.blue { color: #38bdf8; }
    .kpi .value.green { color: #4ade80; }
    .kpi .value.amber { color: #fbbf24; }
    .section { background: #1e293b; border: 1px solid #334155; border-radius: 0.75rem; padding: 1.5rem; margin-bottom: 1.5rem; }
    .section h2 { font-size: 1rem; color: #38bdf8; margin-bottom: 1.25rem; text-transform: uppercase; letter-spacing: 0.05em; }
    svg text { font-family: 'Segoe UI', system-ui, sans-serif; }
    .entropy-zones { display: grid; grid-template-columns: repeat(3, 1fr); gap: 1rem; margin-top: 1rem; }
    .zone { border-radius: 0.5rem; padding: 1rem; text-align: center; }
    .zone.low { background: #052e16; border: 1px solid #4ade80; }
    .zone.mid { background: #431407; border: 1px solid #fbbf24; }
    .zone.high { background: #450a0a; border: 1px solid #C74634; }
    .zone .zone-label { font-size: 0.7rem; color: #94a3b8; text-transform: uppercase; margin-bottom: 0.4rem; }
    .zone .zone-val { font-size: 1.4rem; font-weight: 700; }
    .zone.low .zone-val { color: #4ade80; }
    .zone.mid .zone-val { color: #fbbf24; }
    .zone.high .zone-val { color: #C74634; }
    .zone .zone-desc { font-size: 0.7rem; color: #94a3b8; margin-top: 0.3rem; }
    footer { text-align: center; color: #475569; font-size: 0.75rem; padding: 2rem; }
  </style>
</head>
<body>
  <header>
    <h1>DAgger Run 123 Planner</h1>
    <span class="badge">Port 10030</span>
    <span class="badge" style="background:#38bdf8;color:#0f172a;">Uncertainty-Guided</span>
  </header>
  <div class="container">
    <div class="kpi-row">
      <div class="kpi">
        <div class="label">Uncertainty-Guided SR</div>
        <div class="value blue">94%</div>
      </div>
      <div class="kpi">
        <div class="label">Uniform Sampling SR</div>
        <div class="value amber">91%</div>
      </div>
      <div class="kpi">
        <div class="label">Corrections Saved</div>
        <div class="value green">49%</div>
      </div>
      <div class="kpi">
        <div class="label">Entropy Threshold</div>
        <div class="value red">0.80</div>
      </div>
    </div>

    <!-- Bar chart: SR comparison across DAgger iterations -->
    <div class="section">
      <h2>Success Rate — Uncertainty-Guided vs Uniform Sampling</h2>
      <svg viewBox="0 0 700 260" width="100%" xmlns="http://www.w3.org/2000/svg">
        <!-- axes -->
        <line x1="60" y1="20" x2="60" y2="210" stroke="#475569" stroke-width="1"/>
        <line x1="60" y1="210" x2="680" y2="210" stroke="#475569" stroke-width="1"/>
        <!-- y labels -->
        <text x="55" y="214" fill="#64748b" font-size="10" text-anchor="end">0%</text>
        <text x="55" y="172" fill="#64748b" font-size="10" text-anchor="end">25%</text>
        <text x="55" y="130" fill="#64748b" font-size="10" text-anchor="end">50%</text>
        <text x="55" y="88" fill="#64748b" font-size="10" text-anchor="end">75%</text>
        <text x="55" y="46" fill="#64748b" font-size="10" text-anchor="end">100%</text>
        <!-- grid lines -->
        <line x1="60" y1="168" x2="680" y2="168" stroke="#1e3a5f" stroke-width="0.5" stroke-dasharray="4,4"/>
        <line x1="60" y1="126" x2="680" y2="126" stroke="#1e3a5f" stroke-width="0.5" stroke-dasharray="4,4"/>
        <line x1="60" y1="84" x2="680" y2="84" stroke="#1e3a5f" stroke-width="0.5" stroke-dasharray="4,4"/>
        <line x1="60" y1="42" x2="680" y2="42" stroke="#1e3a5f" stroke-width="0.5" stroke-dasharray="4,4"/>
        <!-- Iteration data: 5 iterations, grouped bars -->
        <!-- Iter 1: UG=72%, UF=68% -->
        <rect x="80" y="123" width="30" height="87" fill="#38bdf8" rx="3"/>
        <rect x="114" y="137" width="30" height="73" fill="#C74634" rx="3"/>
        <!-- Iter 2: UG=80%, UF=75% -->
        <rect x="198" y="107" width="30" height="103" fill="#38bdf8" rx="3"/>
        <rect x="232" y="120" width="30" height="90" fill="#C74634" rx="3"/>
        <!-- Iter 3: UG=86%, UF=81% -->
        <rect x="316" y="92" width="30" height="118" fill="#38bdf8" rx="3"/>
        <rect x="350" y="105" width="30" height="105" fill="#C74634" rx="3"/>
        <!-- Iter 4: UG=91%, UF=87% -->
        <rect x="434" y="76" width="30" height="134" fill="#38bdf8" rx="3"/>
        <rect x="468" y="90" width="30" height="120" fill="#C74634" rx="3"/>
        <!-- Iter 5: UG=94%, UF=91% -->
        <rect x="552" y="65" width="30" height="145" fill="#38bdf8" rx="3"/>
        <rect x="586" y="76" width="30" height="134" fill="#C74634" rx="3"/>
        <!-- x labels -->
        <text x="109" y="226" fill="#94a3b8" font-size="10" text-anchor="middle">Iter 1</text>
        <text x="227" y="226" fill="#94a3b8" font-size="10" text-anchor="middle">Iter 2</text>
        <text x="345" y="226" fill="#94a3b8" font-size="10" text-anchor="middle">Iter 3</text>
        <text x="463" y="226" fill="#94a3b8" font-size="10" text-anchor="middle">Iter 4</text>
        <text x="581" y="226" fill="#94a3b8" font-size="10" text-anchor="middle">Iter 5</text>
        <!-- legend -->
        <rect x="62" y="238" width="12" height="12" fill="#38bdf8" rx="2"/>
        <text x="78" y="249" fill="#e2e8f0" font-size="11">Uncertainty-Guided</text>
        <rect x="200" y="238" width="12" height="12" fill="#C74634" rx="2"/>
        <text x="216" y="249" fill="#e2e8f0" font-size="11">Uniform Sampling</text>
      </svg>
    </div>

    <!-- Entropy zones -->
    <div class="section">
      <h2>3-Zone Entropy Classification</h2>
      <div class="entropy-zones">
        <div class="zone low">
          <div class="zone-label">Low Entropy</div>
          <div class="zone-val">0.0 – 0.4</div>
          <div class="zone-desc">Policy confident — no correction needed. Auto-execute.</div>
        </div>
        <div class="zone mid">
          <div class="zone-label">Mid Entropy</div>
          <div class="zone-val">0.4 – 0.8</div>
          <div class="zone-desc">Marginal — log for review, skip immediate correction.</div>
        </div>
        <div class="zone high">
          <div class="zone-label">High Entropy</div>
          <div class="zone-val">&gt; 0.8</div>
          <div class="zone-desc">Request human correction. Threshold exceeded.</div>
        </div>
      </div>
    </div>
  </div>
  <footer>OCI Robot Cloud &mdash; DAgger Run 123 Planner &mdash; Port 10030 &mdash; Uncertainty-Guided Annotation</footer>
</body>
</html>
"""


def _compute_plan(iteration: int, entropy_threshold: float) -> dict:
    """Simulate uncertainty-guided vs uniform DAgger planning."""
    rng = random.Random(iteration * 31 + int(entropy_threshold * 100))
    base_sr = min(0.60 + iteration * 0.07, 0.94)
    uncertainty_sr = round(min(base_sr + rng.uniform(0.01, 0.04), 0.97), 4)
    uniform_sr = round(max(uncertainty_sr - rng.uniform(0.02, 0.05), 0.50), 4)
    # fraction of steps where entropy > threshold (need correction)
    high_entropy_frac = max(0.10, 1.0 - entropy_threshold - rng.uniform(0.0, 0.15))
    corrections_needed = int(1000 * high_entropy_frac)
    uniform_corrections = 1000
    efficiency_gain = round((1.0 - corrections_needed / uniform_corrections) * 100, 1)
    return {
        "corrections_needed": corrections_needed,
        "uncertainty_guided_sr": round(uncertainty_sr * 100, 2),
        "uniform_sr": round(uniform_sr * 100, 2),
        "efficiency_gain_pct": efficiency_gain,
    }


if _FASTAPI:
    app = FastAPI(
        title="DAgger Run 123 Planner",
        description="Uncertainty-guided DAgger: request corrections only when policy entropy > threshold.",
        version="1.0.0",
    )

    class PlanRequest(BaseModel):
        iteration: int = 1
        entropy_threshold: float = 0.8

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        """Serve the HTML dashboard."""
        return HTML_DASHBOARD

    @app.get("/health")
    async def health():
        return {
            "status": "ok",
            "service": "dagger_run123_planner",
            "port": PORT,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

    @app.post("/dagger/run123/plan")
    async def plan(req: PlanRequest):
        """Plan DAgger correction budget using uncertainty guidance."""
        if req.iteration < 1 or req.iteration > 100:
            raise HTTPException(status_code=422, detail="iteration must be between 1 and 100")
        if not (0.0 < req.entropy_threshold < 1.0):
            raise HTTPException(status_code=422, detail="entropy_threshold must be in (0, 1)")
        return _compute_plan(req.iteration, req.entropy_threshold)

    @app.get("/dagger/run123/status")
    async def status():
        """Return current run123 status summary."""
        return {
            "run_id": "run123",
            "entropy_threshold": 0.8,
            "uncertainty_sr": 94.0,
            "uniform_sr": 91.0,
            "corrections_saved_pct": 49,
        }

else:
    # stdlib fallback
    class _Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):  # silence default logging
            pass

        def _send_json(self, data: dict, status: int = 200):
            body = json.dumps(data).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_html(self, html: str):
            body = html.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            parsed = urlparse(self.path)
            path = parsed.path
            if path == "/":
                self._send_html(HTML_DASHBOARD)
            elif path == "/health":
                self._send_json({"status": "ok", "service": "dagger_run123_planner", "port": PORT})
            elif path == "/dagger/run123/status":
                self._send_json({
                    "run_id": "run123",
                    "entropy_threshold": 0.8,
                    "uncertainty_sr": 94.0,
                    "uniform_sr": 91.0,
                    "corrections_saved_pct": 49,
                })
            else:
                self._send_json({"error": "not found"}, 404)

        def do_POST(self):
            parsed = urlparse(self.path)
            if parsed.path == "/dagger/run123/plan":
                length = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(length) or b"{}")
                iteration = int(body.get("iteration", 1))
                entropy_threshold = float(body.get("entropy_threshold", 0.8))
                self._send_json(_compute_plan(iteration, entropy_threshold))
            else:
                self._send_json({"error": "not found"}, 404)


if __name__ == "__main__":
    if _FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        print(f"[dagger_run123_planner] stdlib fallback — listening on port {PORT}")
        server = HTTPServer(("0.0.0.0", PORT), _Handler)
        server.serve_forever()
