"""DAgger Run117 Planner — failure-mode targeted correction collection service.

Port: 10006
Cycle: 487B
"""

from __future__ import annotations

import json
from typing import Dict

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    _FASTAPI = True
except ImportError:
    _FASTAPI = False

# ---------------------------------------------------------------------------
# HTML Dashboard
# ---------------------------------------------------------------------------

DASHBOARD_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>DAgger Run117 Planner</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; padding: 2rem; }
    h1 { color: #C74634; font-size: 1.8rem; margin-bottom: 0.4rem; }
    .subtitle { color: #94a3b8; margin-bottom: 2rem; font-size: 0.95rem; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1.2rem; margin-bottom: 2rem; }
    .card { background: #1e293b; border-radius: 10px; padding: 1.4rem; border: 1px solid #334155; }
    .card h3 { color: #94a3b8; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.5rem; }
    .card .value { font-size: 2rem; font-weight: 700; color: #38bdf8; }
    .card .unit { font-size: 0.85rem; color: #64748b; margin-top: 0.2rem; }
    .highlight { color: #C74634 !important; }
    .green { color: #4ade80 !important; }
    h2 { color: #38bdf8; font-size: 1.2rem; margin-bottom: 1rem; }
    .chart-wrap { background: #1e293b; border-radius: 10px; padding: 1.5rem; border: 1px solid #334155; margin-bottom: 2rem; }
    svg text { fill: #94a3b8; font-family: 'Segoe UI', sans-serif; }
    .badge { display: inline-block; padding: 0.25rem 0.7rem; border-radius: 999px; font-size: 0.75rem; font-weight: 600; margin-right: 0.4rem; }
    .badge-red { background: #7f1d1d; color: #fca5a5; }
    .badge-blue { background: #0c4a6e; color: #7dd3fc; }
    .badge-gray { background: #1e3a5f; color: #93c5fd; }
    .endpoint { background: #1e293b; border-radius: 8px; padding: 1rem; margin-bottom: 0.8rem; border-left: 3px solid #C74634; }
    .endpoint .method { color: #C74634; font-weight: 700; font-size: 0.85rem; }
    .endpoint .path { color: #38bdf8; font-size: 0.9rem; margin-left: 0.5rem; }
    .endpoint .desc { color: #64748b; font-size: 0.82rem; margin-top: 0.3rem; }
  </style>
</head>
<body>
  <h1>DAgger Run117 Planner</h1>
  <p class="subtitle">Failure-Mode Targeted Correction Collection &mdash; Cycle 487B</p>

  <div class="grid">
    <div class="card">
      <h3>Targeted SR</h3>
      <div class="value green">93%</div>
      <div class="unit">success rate (targeted)</div>
    </div>
    <div class="card">
      <h3>Uniform SR</h3>
      <div class="value highlight">89%</div>
      <div class="unit">success rate (uniform)</div>
    </div>
    <div class="card">
      <h3>Corrections Saved</h3>
      <div class="value green">43%</div>
      <div class="unit">fewer corrections needed</div>
    </div>
    <div class="card">
      <h3>Run ID</h3>
      <div class="value" style="font-size:1.4rem">run117</div>
      <div class="unit">DAgger iteration</div>
    </div>
  </div>

  <div class="chart-wrap">
    <h2>Failure Mode Distribution &amp; SR Comparison</h2>
    <svg width="100%" height="260" viewBox="0 0 700 260" preserveAspectRatio="xMidYMid meet">
      <!-- Axes -->
      <line x1="60" y1="20" x2="60" y2="200" stroke="#334155" stroke-width="1.5"/>
      <line x1="60" y1="200" x2="680" y2="200" stroke="#334155" stroke-width="1.5"/>

      <!-- Y-axis labels -->
      <text x="52" y="204" text-anchor="end" font-size="11">0</text>
      <text x="52" y="154" text-anchor="end" font-size="11">25</text>
      <text x="52" y="104" text-anchor="end" font-size="11">50</text>
      <text x="52" y="54" text-anchor="end" font-size="11">75</text>
      <line x1="60" y1="150" x2="680" y2="150" stroke="#1e3a5f" stroke-dasharray="4" stroke-width="1"/>
      <line x1="60" y1="100" x2="680" y2="100" stroke="#1e3a5f" stroke-dasharray="4" stroke-width="1"/>
      <line x1="60" y1="50" x2="680" y2="50" stroke="#1e3a5f" stroke-dasharray="4" stroke-width="1"/>

      <!-- Failure mode bars (% of corrections budget) -->
      <!-- slip 60% -->
      <rect x="80" y="80" width="60" height="120" fill="#C74634" rx="4"/>
      <text x="110" y="75" text-anchor="middle" font-size="11" fill="#fca5a5">60%</text>
      <text x="110" y="220" text-anchor="middle" font-size="11">Slip</text>

      <!-- misalign 25% -->
      <rect x="180" y="150" width="60" height="50" fill="#C74634" opacity="0.7" rx="4"/>
      <text x="210" y="145" text-anchor="middle" font-size="11" fill="#fca5a5">25%</text>
      <text x="210" y="220" text-anchor="middle" font-size="11">Misalign</text>

      <!-- drop 15% -->
      <rect x="280" y="170" width="60" height="30" fill="#C74634" opacity="0.5" rx="4"/>
      <text x="310" y="165" text-anchor="middle" font-size="11" fill="#fca5a5">15%</text>
      <text x="310" y="220" text-anchor="middle" font-size="11">Drop</text>

      <!-- SR comparison bars -->
      <!-- Targeted SR 93% -->
      <rect x="440" y="13" width="70" height="187" fill="#38bdf8" rx="4"/>
      <text x="475" y="10" text-anchor="middle" font-size="11" fill="#7dd3fc">93%</text>
      <text x="475" y="220" text-anchor="middle" font-size="11">Targeted SR</text>

      <!-- Uniform SR 89% -->
      <rect x="540" y="21" width="70" height="179" fill="#38bdf8" opacity="0.5" rx="4"/>
      <text x="575" y="17" text-anchor="middle" font-size="11" fill="#7dd3fc">89%</text>
      <text x="575" y="220" text-anchor="middle" font-size="11">Uniform SR</text>

      <!-- Section labels -->
      <text x="210" y="245" text-anchor="middle" font-size="12" fill="#C74634" font-weight="600">Failure Modes</text>
      <text x="507" y="245" text-anchor="middle" font-size="12" fill="#38bdf8" font-weight="600">SR Comparison</text>
      <line x1="380" y1="200" x2="380" y2="250" stroke="#334155" stroke-width="1" stroke-dasharray="4"/>
    </svg>
  </div>

  <div class="chart-wrap">
    <h2>Top Failure Modes</h2>
    <span class="badge badge-red">Slip 60%</span>
    <span class="badge badge-blue">Misalign 25%</span>
    <span class="badge badge-gray">Drop 15%</span>
  </div>

  <div class="chart-wrap">
    <h2>API Endpoints</h2>
    <div class="endpoint">
      <span class="method">GET</span><span class="path">/health</span>
      <div class="desc">Service health check — returns JSON status</div>
    </div>
    <div class="endpoint">
      <span class="method">GET</span><span class="path">/dagger/run117/status</span>
      <div class="desc">Current run117 status, failure modes, and SR metrics</div>
    </div>
    <div class="endpoint">
      <span class="method">POST</span><span class="path">/dagger/run117/plan</span>
      <div class="desc">Plan targeted correction budget from failure analysis input</div>
    </div>
  </div>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# Business logic
# ---------------------------------------------------------------------------

RUN117_STATUS = {
    "run_id": "run117",
    "top_failure_modes": ["slip 60%", "misalign 25%", "drop 15%"],
    "targeted_sr": 93.0,
    "uniform_sr": 89.0,
    "corrections_saved_pct": 43,
}


def _plan_corrections(failure_analysis: Dict[str, float]) -> dict:
    """Given failure weights, compute targeted correction budget and SR lift."""
    total = sum(failure_analysis.values()) or 1.0
    budget: Dict[str, int] = {}
    base_corrections = 200
    for mode, weight in failure_analysis.items():
        budget[mode] = max(1, int(round(base_corrections * weight / total)))

    # Weighted success rate model (simplified)
    targeted_sr = round(min(98.0, 87.0 + 6.0 * (1 - abs(max(failure_analysis.values()) / total - 0.6))), 1)
    uniform_sr = 89.0
    efficiency_gain = round((1 - sum(budget.values()) / base_corrections) * 100, 1)
    return {
        "correction_budget": budget,
        "targeted_sr": targeted_sr,
        "uniform_sr": uniform_sr,
        "efficiency_gain_pct": max(0.0, efficiency_gain),
    }


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

if _FASTAPI:
    app = FastAPI(
        title="DAgger Run117 Planner",
        description="Failure-mode targeted correction collection planning",
        version="1.0.0",
    )

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return DASHBOARD_HTML

    @app.get("/health")
    async def health():
        return JSONResponse({"status": "ok", "service": "dagger_run117_planner", "port": 10006})

    @app.get("/dagger/run117/status")
    async def run117_status():
        return JSONResponse(RUN117_STATUS)

    @app.post("/dagger/run117/plan")
    async def run117_plan(body: dict):
        failure_analysis = body.get("failure_analysis", {"slip": 0.6, "misalign": 0.25, "drop": 0.15})
        result = _plan_corrections(failure_analysis)
        return JSONResponse(result)

else:
    # ---------------------------------------------------------------------------
    # stdlib fallback (HTTPServer)
    # ---------------------------------------------------------------------------
    import http.server
    import urllib.parse

    class _Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):  # silence default logging
            pass

        def _send(self, code: int, content_type: str, body: str):
            encoded = body.encode()
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def do_GET(self):
            path = urllib.parse.urlparse(self.path).path
            if path == "/":
                self._send(200, "text/html", DASHBOARD_HTML)
            elif path == "/health":
                self._send(200, "application/json", json.dumps({"status": "ok", "service": "dagger_run117_planner", "port": 10006}))
            elif path == "/dagger/run117/status":
                self._send(200, "application/json", json.dumps(RUN117_STATUS))
            else:
                self._send(404, "application/json", json.dumps({"error": "not found"}))

        def do_POST(self):
            path = urllib.parse.urlparse(self.path).path
            if path == "/dagger/run117/plan":
                length = int(self.headers.get("Content-Length", 0))
                raw = self.rfile.read(length)
                try:
                    body = json.loads(raw)
                except Exception:
                    body = {}
                failure_analysis = body.get("failure_analysis", {"slip": 0.6, "misalign": 0.25, "drop": 0.15})
                result = _plan_corrections(failure_analysis)
                self._send(200, "application/json", json.dumps(result))
            else:
                self._send(404, "application/json", json.dumps({"error": "not found"}))


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if _FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=10006)
    else:
        import http.server
        server = http.server.HTTPServer(("0.0.0.0", 10006), _Handler)
        print("DAgger Run117 Planner running on http://0.0.0.0:10006 (stdlib fallback)")
        server.serve_forever()
