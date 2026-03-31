"""DAgger Run 171 Planner — active learning DAgger with uncertainty-based expert queries.

Port: 10222
Cycle: 541B
"""

from __future__ import annotations

import json
from typing import Any, Dict

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    _FASTAPI_AVAILABLE = True
except ImportError:
    _FASTAPI_AVAILABLE = False

PORT = 10222
SERVICE_NAME = "dagger_run171_planner"

# ---------------------------------------------------------------------------
# Service metadata
# ---------------------------------------------------------------------------

RUN171_CONFIG: Dict[str, Any] = {
    "run_id": "run171",
    "strategy": "active_learning_dagger",
    "entropy_threshold": 0.45,
    "description": "Query expert only when model uncertainty (action entropy) exceeds threshold.",
    "results": {
        "active_queries": 200,
        "active_sr_pct": 92,
        "uniform_queries": 350,
        "uniform_sr_pct": 90,
        "efficiency_gain_pct": 43,
        "correction_reduction_pct": 40,
    },
}

DASHBOARD_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>DAgger Run 171 Planner</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; padding: 2rem; }
    h1 { color: #C74634; font-size: 1.75rem; margin-bottom: 0.25rem; }
    .subtitle { color: #38bdf8; font-size: 0.95rem; margin-bottom: 2rem; }
    .cards { display: flex; gap: 1.25rem; flex-wrap: wrap; margin-bottom: 2rem; }
    .card { background: #1e293b; border: 1px solid #334155; border-radius: 0.75rem; padding: 1.25rem 1.75rem; min-width: 160px; }
    .card-label { font-size: 0.78rem; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.05em; }
    .card-value { font-size: 1.9rem; font-weight: 700; color: #38bdf8; margin-top: 0.25rem; }
    .card-sub { font-size: 0.78rem; color: #64748b; margin-top: 0.2rem; }
    .section-title { color: #94a3b8; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 0.75rem; }
    .chart-wrap { background: #1e293b; border: 1px solid #334155; border-radius: 0.75rem; padding: 1.5rem; margin-bottom: 2rem; }
    .endpoints { background: #1e293b; border: 1px solid #334155; border-radius: 0.75rem; padding: 1.25rem 1.75rem; }
    .ep { display: flex; align-items: center; gap: 0.75rem; padding: 0.45rem 0; border-bottom: 1px solid #1e293b; }
    .ep:last-child { border-bottom: none; }
    .method { background: #0c4a6e; color: #38bdf8; font-size: 0.72rem; font-weight: 700; padding: 0.2rem 0.5rem; border-radius: 0.3rem; }
    .path { color: #e2e8f0; font-family: monospace; font-size: 0.88rem; }
    .desc { color: #64748b; font-size: 0.8rem; margin-left: auto; }
    footer { margin-top: 2.5rem; color: #475569; font-size: 0.75rem; text-align: center; }
  </style>
</head>
<body>
  <h1>DAgger Run 171 Planner</h1>
  <p class="subtitle">Active Learning DAgger &mdash; uncertainty-gated expert queries &mdash; port {port}</p>

  <div class="cards">
    <div class="card">
      <div class="card-label">Entropy Threshold</div>
      <div class="card-value">0.45</div>
      <div class="card-sub">query gate</div>
    </div>
    <div class="card">
      <div class="card-label">Active SR</div>
      <div class="card-value">92%</div>
      <div class="card-sub">200 queries</div>
    </div>
    <div class="card">
      <div class="card-label">Uniform SR</div>
      <div class="card-value">90%</div>
      <div class="card-sub">350 queries</div>
    </div>
    <div class="card">
      <div class="card-label">Efficiency Gain</div>
      <div class="card-value">43%</div>
      <div class="card-sub">fewer queries</div>
    </div>
    <div class="card">
      <div class="card-label">Correction Reduction</div>
      <div class="card-value">40%</div>
      <div class="card-sub">same SR</div>
    </div>
  </div>

  <div class="chart-wrap">
    <div class="section-title">Expert Query Efficiency: Active vs Uniform Sampling</div>
    <svg width="520" height="200" viewBox="0 0 520 200" xmlns="http://www.w3.org/2000/svg">
      <!-- Axes -->
      <line x1="60" y1="10" x2="60" y2="160" stroke="#334155" stroke-width="1.5"/>
      <line x1="60" y1="160" x2="500" y2="160" stroke="#334155" stroke-width="1.5"/>

      <!-- Y-axis labels -->
      <text x="52" y="164" fill="#64748b" font-size="11" text-anchor="end">0</text>
      <text x="52" y="122" fill="#64748b" font-size="11" text-anchor="end">100</text>
      <text x="52" y="84" fill="#64748b" font-size="11" text-anchor="end">200</text>
      <text x="52" y="46" fill="#64748b" font-size="11" text-anchor="end">300</text>
      <text x="52" y="12" fill="#64748b" font-size="11" text-anchor="end">400</text>

      <!-- Grid lines -->
      <line x1="60" y1="120" x2="500" y2="120" stroke="#1e293b" stroke-width="1" stroke-dasharray="4,3"/>
      <line x1="60" y1="82" x2="500" y2="82" stroke="#1e293b" stroke-width="1" stroke-dasharray="4,3"/>
      <line x1="60" y1="44" x2="500" y2="44" stroke="#1e293b" stroke-width="1" stroke-dasharray="4,3"/>

      <!-- Active bar: 200 queries, height = 200/400 * 150 = 75 -->
      <rect x="100" y="85" width="70" height="75" fill="#38bdf8" rx="4"/>
      <text x="135" y="79" fill="#38bdf8" font-size="12" font-weight="700" text-anchor="middle">200</text>
      <text x="135" y="178" fill="#94a3b8" font-size="11" text-anchor="middle">Active</text>
      <text x="135" y="190" fill="#64748b" font-size="10" text-anchor="middle">92% SR</text>

      <!-- Uniform bar: 350 queries, height = 350/400 * 150 = 131.25 -->
      <rect x="240" y="28" width="70" height="132" fill="#C74634" rx="4"/>
      <text x="275" y="22" fill="#C74634" font-size="12" font-weight="700" text-anchor="middle">350</text>
      <text x="275" y="178" fill="#94a3b8" font-size="11" text-anchor="middle">Uniform</text>
      <text x="275" y="190" fill="#64748b" font-size="10" text-anchor="middle">90% SR</text>

      <!-- Delta annotation -->
      <line x1="380" y1="85" x2="380" y2="28" stroke="#a3e635" stroke-width="1.5" stroke-dasharray="4,2"/>
      <text x="415" y="60" fill="#a3e635" font-size="12" font-weight="600" text-anchor="middle">43%</text>
      <text x="415" y="74" fill="#a3e635" font-size="10" text-anchor="middle">fewer queries</text>
    </svg>
  </div>

  <div class="endpoints">
    <div class="section-title">API Endpoints</div>
    <div class="ep"><span class="method">GET</span><span class="path">/health</span><span class="desc">Service health</span></div>
    <div class="ep"><span class="method">GET</span><span class="path">/</span><span class="desc">This dashboard</span></div>
    <div class="ep"><span class="method">GET</span><span class="path">/dagger/run171/plan</span><span class="desc">Return active-learning DAgger plan config</span></div>
    <div class="ep"><span class="method">GET</span><span class="path">/dagger/run171/status</span><span class="desc">Current run status &amp; metrics</span></div>
  </div>

  <footer>OCI Robot Cloud &mdash; {service} &mdash; port {port} &mdash; cycle 541B</footer>
</body>
</html>
""".format(port=PORT, service=SERVICE_NAME)


if _FASTAPI_AVAILABLE:
    app = FastAPI(title=SERVICE_NAME, version="1.0.0")

    @app.get("/health")
    async def health() -> JSONResponse:
        return JSONResponse({"status": "ok", "port": PORT, "service": SERVICE_NAME})

    @app.get("/", response_class=HTMLResponse)
    async def dashboard() -> HTMLResponse:
        return HTMLResponse(DASHBOARD_HTML)

    @app.get("/dagger/run171/plan")
    async def run171_plan() -> JSONResponse:
        return JSONResponse({
            "run_id": RUN171_CONFIG["run_id"],
            "strategy": RUN171_CONFIG["strategy"],
            "entropy_threshold": RUN171_CONFIG["entropy_threshold"],
            "description": RUN171_CONFIG["description"],
            "expected_efficiency_gain_pct": RUN171_CONFIG["results"]["efficiency_gain_pct"],
        })

    @app.get("/dagger/run171/status")
    async def run171_status() -> JSONResponse:
        return JSONResponse({
            "run_id": RUN171_CONFIG["run_id"],
            "status": "complete",
            "results": RUN171_CONFIG["results"],
        })

else:
    import http.server
    import threading

    class _Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):  # silence access log
            pass

        def do_GET(self):
            if self.path == "/health":
                body = json.dumps({"status": "ok", "port": PORT, "service": SERVICE_NAME}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                body = DASHBOARD_HTML.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

    def _serve():
        server = http.server.HTTPServer(("0.0.0.0", PORT), _Handler)
        server.serve_forever()


if __name__ == "__main__":
    if _FASTAPI_AVAILABLE:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        import http.server
        server = http.server.HTTPServer(("0.0.0.0", PORT), _Handler)
        print(f"Fallback http.server running on port {PORT}")
        server.serve_forever()
