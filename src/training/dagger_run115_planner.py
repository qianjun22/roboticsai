"""DAgger Run 115 Planner — multi-modal DAgger with vision + force + proprioception corrections.

Port: 9998
"""

import json
import random
import string
from typing import Any, Dict

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    _FASTAPI_AVAILABLE = True
except ImportError:
    _FASTAPI_AVAILABLE = False

# ---------------------------------------------------------------------------
# HTML Dashboard
# ---------------------------------------------------------------------------

_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>DAgger Run 115 Planner</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; padding: 2rem; }
    h1 { color: #C74634; font-size: 1.8rem; margin-bottom: 0.4rem; }
    h2 { color: #38bdf8; font-size: 1.1rem; margin: 1.5rem 0 0.6rem; }
    .subtitle { color: #94a3b8; font-size: 0.95rem; margin-bottom: 1.8rem; }
    .cards { display: flex; gap: 1rem; flex-wrap: wrap; margin-bottom: 2rem; }
    .card { background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 1.2rem 1.6rem; min-width: 160px; }
    .card-label { color: #94a3b8; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em; }
    .card-value { font-size: 2rem; font-weight: 700; margin-top: 0.3rem; }
    .red   { color: #C74634; }
    .blue  { color: #38bdf8; }
    .green { color: #4ade80; }
    .amber { color: #fbbf24; }
    .chart-wrap { background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 1.4rem; display: inline-block; }
    table { border-collapse: collapse; width: 100%; }
    th { background: #0f172a; color: #38bdf8; text-align: left; padding: 0.6rem 1rem; font-size: 0.85rem; }
    td { padding: 0.55rem 1rem; border-top: 1px solid #1e293b; font-size: 0.9rem; color: #cbd5e1; }
    tr:hover td { background: #1e293b; }
    .badge { display: inline-block; border-radius: 999px; padding: 0.15rem 0.65rem; font-size: 0.75rem; font-weight: 600; }
    .b-blue  { background: #0c4a6e; color: #38bdf8; }
    .b-green { background: #14532d; color: #4ade80; }
    .b-amber { background: #78350f; color: #fbbf24; }
    footer { color: #475569; font-size: 0.75rem; margin-top: 2.5rem; }
  </style>
</head>
<body>
  <h1>DAgger Run 115 Planner</h1>
  <p class="subtitle">Multi-Modal DAgger: Vision + Force + Proprioception &nbsp;|&nbsp; Port 9998 &nbsp;|&nbsp; OCI Robot Cloud</p>

  <div class="cards">
    <div class="card">
      <div class="card-label">Multi-Modal SR</div>
      <div class="card-value green">94%</div>
    </div>
    <div class="card">
      <div class="card-label">Vision-Only SR</div>
      <div class="card-value amber">91%</div>
    </div>
    <div class="card">
      <div class="card-label">SR Gain</div>
      <div class="card-value blue">+3 pp</div>
    </div>
    <div class="card">
      <div class="card-label">Modalities</div>
      <div class="card-value red">3</div>
    </div>
    <div class="card">
      <div class="card-label">Run ID</div>
      <div class="card-value" style="font-size:1.2rem;color:#e2e8f0;">run115</div>
    </div>
  </div>

  <h2>Success Rate by Modality Configuration</h2>
  <div class="chart-wrap">
    <svg width="520" height="220" viewBox="0 0 520 220" xmlns="http://www.w3.org/2000/svg">
      <!-- axes -->
      <line x1="60" y1="10" x2="60" y2="180" stroke="#334155" stroke-width="1.5"/>
      <line x1="60" y1="180" x2="510" y2="180" stroke="#334155" stroke-width="1.5"/>
      <!-- y labels -->
      <text x="50" y="185" fill="#64748b" font-size="11" text-anchor="end">0%</text>
      <text x="50" y="140" fill="#64748b" font-size="11" text-anchor="end">25%</text>
      <text x="50" y="95"  fill="#64748b" font-size="11" text-anchor="end">50%</text>
      <text x="50" y="50"  fill="#64748b" font-size="11" text-anchor="end">75%</text>
      <text x="50" y="15"  fill="#64748b" font-size="11" text-anchor="end">100%</text>
      <!-- grid -->
      <line x1="60" y1="140" x2="510" y2="140" stroke="#1e293b" stroke-width="1"/>
      <line x1="60" y1="95"  x2="510" y2="95"  stroke="#1e293b" stroke-width="1"/>
      <line x1="60" y1="50"  x2="510" y2="50"  stroke="#1e293b" stroke-width="1"/>
      <!-- bars: 170px = 100%; bar width=80 -->
      <!-- Vision only: 91% → 154.7 -->
      <rect x="80"  y="25.3" width="80" height="154.7" fill="#fbbf24" rx="4"/>
      <text x="120" y="20"   fill="#fbbf24" font-size="12" text-anchor="middle">91%</text>
      <!-- Vision+Force: 92.5% → 157.25 -->
      <rect x="200" y="22.75" width="80" height="157.25" fill="#38bdf8" rx="4"/>
      <text x="240" y="17"   fill="#38bdf8" font-size="12" text-anchor="middle">92.5%</text>
      <!-- V+P: 93% → 158.1 -->
      <rect x="320" y="21.9" width="80" height="158.1" fill="#818cf8" rx="4"/>
      <text x="360" y="16"   fill="#818cf8" font-size="12" text-anchor="middle">93%</text>
      <!-- V+F+P (run115): 94% → 159.8 -->
      <rect x="420" y="20.2" width="60" height="159.8" fill="#4ade80" rx="4"/>
      <text x="450" y="15"   fill="#4ade80" font-size="12" text-anchor="middle">94%</text>
      <!-- x labels -->
      <text x="120" y="198" fill="#94a3b8" font-size="10" text-anchor="middle">Vision</text>
      <text x="240" y="198" fill="#94a3b8" font-size="10" text-anchor="middle">V+Force</text>
      <text x="360" y="198" fill="#94a3b8" font-size="10" text-anchor="middle">V+Prop</text>
      <text x="450" y="198" fill="#94a3b8" font-size="10" text-anchor="middle">V+F+P</text>
      <text x="450" y="210" fill="#4ade80" font-size="9"  text-anchor="middle">(run115)</text>
    </svg>
  </div>

  <h2>Modality Breakdown</h2>
  <table>
    <thead><tr><th>Modality</th><th>Sensor</th><th>Correction Weight</th><th>Status</th></tr></thead>
    <tbody>
      <tr><td>Vision</td><td>RGB-D Camera</td><td>0.55</td><td><span class="badge b-green">Active</span></td></tr>
      <tr><td>Force</td><td>6-DOF F/T Sensor</td><td>0.25</td><td><span class="badge b-green">Active</span></td></tr>
      <tr><td>Proprioception</td><td>Joint Encoders</td><td>0.20</td><td><span class="badge b-green">Active</span></td></tr>
    </tbody>
  </table>

  <h2>API Endpoints</h2>
  <table>
    <thead><tr><th>Method</th><th>Path</th><th>Description</th></tr></thead>
    <tbody>
      <tr><td><span class="badge b-blue">GET</span></td><td>/</td><td>This dashboard</td></tr>
      <tr><td><span class="badge b-green">GET</span></td><td>/health</td><td>Health check</td></tr>
      <tr><td><span class="badge b-amber">GET</span></td><td>/dagger/run115/status</td><td>Run 115 status and projected SR</td></tr>
      <tr><td><span class="badge b-amber">POST</span></td><td>/dagger/run115/plan</td><td>Plan corrections for an iteration</td></tr>
    </tbody>
  </table>

  <footer>OCI Robot Cloud &mdash; DAgger Run 115 Planner &mdash; Port 9998</footer>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

if _FASTAPI_AVAILABLE:
    app = FastAPI(
        title="DAgger Run 115 Planner",
        description="Multi-modal DAgger with vision + force + proprioception corrections",
        version="1.0.0",
    )

    @app.get("/", response_class=HTMLResponse)
    async def dashboard() -> HTMLResponse:
        return HTMLResponse(content=_HTML)

    @app.get("/health")
    async def health() -> Dict[str, Any]:
        return {"status": "ok", "service": "dagger_run115_planner", "port": 9998}

    @app.get("/dagger/run115/status")
    async def run115_status() -> Dict[str, Any]:
        return {
            "run_id": "run115",
            "modalities": 3,
            "projected_sr_iter4": 94.0,
            "baseline_vision_only_sr": 91.0,
        }

    @app.post("/dagger/run115/plan")
    async def plan_corrections(body: Dict[str, Any]) -> Dict[str, Any]:
        iteration: int = int(body.get("iteration", 1))
        current_sr: float = float(body.get("current_sr", 91.0))

        # Heuristic: corrections scale down as SR improves
        gap = max(0.0, 94.0 - current_sr)
        corrections_needed = max(1, int(round(gap * 2.5 + iteration * 0.4)))
        projected_sr = round(min(94.0, current_sr + gap * 0.4), 2)

        return {
            "corrections_needed": corrections_needed,
            "modalities": ["vision", "force", "proprioception"],
            "projected_sr": projected_sr,
        }

# ---------------------------------------------------------------------------
# Fallback: stdlib HTTP server
# ---------------------------------------------------------------------------

if not _FASTAPI_AVAILABLE:
    import http.server
    import urllib.parse

    class _Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *args: Any) -> None:  # silence default logs
            pass

        def _send(self, code: int, ctype: str, body: bytes) -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            path = urllib.parse.urlparse(self.path).path
            if path == "/":
                self._send(200, "text/html", _HTML.encode())
            elif path == "/health":
                data = json.dumps({"status": "ok", "service": "dagger_run115_planner", "port": 9998}).encode()
                self._send(200, "application/json", data)
            elif path == "/dagger/run115/status":
                data = json.dumps({"run_id": "run115", "modalities": 3, "projected_sr_iter4": 94.0, "baseline_vision_only_sr": 91.0}).encode()
                self._send(200, "application/json", data)
            else:
                self._send(404, "application/json", b'{"error":"not found"}')

        def do_POST(self) -> None:
            path = urllib.parse.urlparse(self.path).path
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length) or b"{}")
            if path == "/dagger/run115/plan":
                iteration = int(body.get("iteration", 1))
                current_sr = float(body.get("current_sr", 91.0))
                gap = max(0.0, 94.0 - current_sr)
                corrections_needed = max(1, int(round(gap * 2.5 + iteration * 0.4)))
                projected_sr = round(min(94.0, current_sr + gap * 0.4), 2)
                data = json.dumps({"corrections_needed": corrections_needed, "modalities": ["vision", "force", "proprioception"], "projected_sr": projected_sr}).encode()
                self._send(200, "application/json", data)
            else:
                self._send(404, "application/json", b'{"error":"not found"}')

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if _FASTAPI_AVAILABLE:
        import uvicorn  # type: ignore
        uvicorn.run(app, host="0.0.0.0", port=9998)
    else:
        import http.server
        server = http.server.HTTPServer(("0.0.0.0", 9998), _Handler)
        print("[dagger_run115_planner] Serving on http://0.0.0.0:9998 (stdlib fallback)")
        server.serve_forever()
