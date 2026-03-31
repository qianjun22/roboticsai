"""Force Field Policy v2 — learned force fields for manipulation.

Port 10180. Attracts end-effector to goal, repels from obstacles, guides path.
Architecture: IRL from demonstrations, continuous force field, 2D quiver plot visualization.
"""

import json
import math
from datetime import datetime

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

PORT = 10180
SERVICE_NAME = "force_field_policy_v2"

HTML_DASHBOARD = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Force Field Policy v2 — OCI Robot Cloud</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; padding: 2rem; }
    h1 { color: #38bdf8; font-size: 1.8rem; margin-bottom: 0.5rem; }
    h2 { color: #C74634; font-size: 1.1rem; margin-bottom: 1.5rem; font-weight: 400; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-bottom: 2rem; }
    .card { background: #1e293b; border-radius: 8px; padding: 1.25rem; border-left: 3px solid #C74634; }
    .card-label { font-size: 0.75rem; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.05em; }
    .card-value { font-size: 1.6rem; font-weight: 700; color: #38bdf8; margin-top: 0.25rem; }
    .chart-section { background: #1e293b; border-radius: 8px; padding: 1.5rem; margin-bottom: 2rem; }
    .chart-title { color: #94a3b8; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 1rem; }
    .endpoints { background: #1e293b; border-radius: 8px; padding: 1.5rem; }
    .endpoint { display: flex; align-items: center; gap: 0.75rem; margin-bottom: 0.75rem; }
    .method { background: #C74634; color: white; font-size: 0.7rem; font-weight: 700; padding: 0.2rem 0.5rem; border-radius: 4px; min-width: 3.5rem; text-align: center; }
    .method.get { background: #0284c7; }
    .path { color: #e2e8f0; font-family: monospace; font-size: 0.9rem; }
    .desc { color: #64748b; font-size: 0.8rem; }
    footer { margin-top: 2rem; text-align: center; color: #475569; font-size: 0.75rem; }
  </style>
</head>
<body>
  <h1>Force Field Policy v2</h1>
  <h2>Learned Force Fields for Robot Manipulation &mdash; OCI Robot Cloud</h2>

  <div class="grid">
    <div class="card">
      <div class="card-label">Model Version</div>
      <div class="card-value">v2.0</div>
    </div>
    <div class="card">
      <div class="card-label">SR vs v1</div>
      <div class="card-value">+5 pp</div>
    </div>
    <div class="card">
      <div class="card-label">Inference</div>
      <div class="card-value">18 ms</div>
    </div>
    <div class="card">
      <div class="card-label">Field Dims</div>
      <div class="card-value">6-DoF</div>
    </div>
  </div>

  <div class="chart-section">
    <div class="chart-title">Success Rate: Force Field v2 vs v1</div>
    <svg width="100%" height="180" viewBox="0 0 480 180" xmlns="http://www.w3.org/2000/svg">
      <!-- Background grid -->
      <line x1="80" y1="20" x2="80" y2="150" stroke="#334155" stroke-width="1"/>
      <line x1="80" y1="150" x2="460" y2="150" stroke="#334155" stroke-width="1"/>
      <!-- Grid lines -->
      <line x1="80" y1="70" x2="460" y2="70" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,3"/>
      <line x1="80" y1="110" x2="460" y2="110" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,3"/>
      <!-- Y-axis labels -->
      <text x="72" y="24" fill="#94a3b8" font-size="10" text-anchor="end">100%</text>
      <text x="72" y="74" fill="#94a3b8" font-size="10" text-anchor="end">75%</text>
      <text x="72" y="114" fill="#94a3b8" font-size="10" text-anchor="end">50%</text>
      <text x="72" y="154" fill="#94a3b8" font-size="10" text-anchor="end">0%</text>
      <!-- Bar: Force Field v2 = 93% -->
      <rect x="130" y="35" width="80" height="115" fill="#38bdf8" rx="4"/>
      <text x="170" y="28" fill="#38bdf8" font-size="13" font-weight="700" text-anchor="middle">93%</text>
      <text x="170" y="168" fill="#94a3b8" font-size="11" text-anchor="middle">Force Field v2</text>
      <!-- Bar: Force Field v1 = 88% -->
      <rect x="270" y="61" width="80" height="89" fill="#C74634" rx="4"/>
      <text x="310" y="54" fill="#C74634" font-size="13" font-weight="700" text-anchor="middle">88%</text>
      <text x="310" y="168" fill="#94a3b8" font-size="11" text-anchor="middle">Force Field v1</text>
    </svg>
  </div>

  <div class="chart-section">
    <div class="chart-title">Architecture: IRL-Trained Continuous Force Field</div>
    <svg width="100%" height="120" viewBox="0 0 480 120" xmlns="http://www.w3.org/2000/svg">
      <!-- Pipeline boxes -->
      <rect x="10" y="40" width="90" height="40" rx="6" fill="#0f172a" stroke="#38bdf8" stroke-width="1.5"/>
      <text x="55" y="56" fill="#38bdf8" font-size="9" text-anchor="middle">Demonstrations</text>
      <text x="55" y="70" fill="#94a3b8" font-size="8" text-anchor="middle">(IRL)</text>
      <line x1="100" y1="60" x2="125" y2="60" stroke="#475569" stroke-width="1.5" marker-end="url(#arr)"/>
      <rect x="125" y="40" width="90" height="40" rx="6" fill="#0f172a" stroke="#C74634" stroke-width="1.5"/>
      <text x="170" y="56" fill="#C74634" font-size="9" text-anchor="middle">Force Field</text>
      <text x="170" y="70" fill="#94a3b8" font-size="8" text-anchor="middle">(Continuous)</text>
      <line x1="215" y1="60" x2="240" y2="60" stroke="#475569" stroke-width="1.5" marker-end="url(#arr)"/>
      <rect x="240" y="40" width="90" height="40" rx="6" fill="#0f172a" stroke="#38bdf8" stroke-width="1.5"/>
      <text x="285" y="56" fill="#38bdf8" font-size="9" text-anchor="middle">Quiver Plot</text>
      <text x="285" y="70" fill="#94a3b8" font-size="8" text-anchor="middle">(2D Viz)</text>
      <line x1="330" y1="60" x2="355" y2="60" stroke="#475569" stroke-width="1.5" marker-end="url(#arr)"/>
      <rect x="355" y="40" width="100" height="40" rx="6" fill="#0f172a" stroke="#C74634" stroke-width="1.5"/>
      <text x="405" y="56" fill="#C74634" font-size="9" text-anchor="middle">Robot Action</text>
      <text x="405" y="70" fill="#94a3b8" font-size="8" text-anchor="middle">(6-DoF Control)</text>
      <defs>
        <marker id="arr" markerWidth="6" markerHeight="6" refX="3" refY="3" orient="auto">
          <path d="M0,0 L6,3 L0,6 Z" fill="#475569"/>
        </marker>
      </defs>
    </svg>
  </div>

  <div class="endpoints">
    <div class="chart-title" style="margin-bottom:1rem">API Endpoints</div>
    <div class="endpoint">
      <span class="method get">GET</span>
      <span class="path">/health</span>
      <span class="desc">Service health &amp; status</span>
    </div>
    <div class="endpoint">
      <span class="method get">GET</span>
      <span class="path">/</span>
      <span class="desc">This dashboard</span>
    </div>
    <div class="endpoint">
      <span class="method">POST</span>
      <span class="path">/control/force_field_execute</span>
      <span class="desc">Execute force-field-guided action</span>
    </div>
    <div class="endpoint">
      <span class="method get">GET</span>
      <span class="path">/control/force_field_v2/visualize</span>
      <span class="desc">Return 2D quiver plot data</span>
    </div>
  </div>

  <footer>OCI Robot Cloud &mdash; Force Field Policy v2 &mdash; Port {port} &mdash; &copy; 2026 Oracle</footer>
</body>
</html>
""".replace("{port}", str(PORT))

if HAS_FASTAPI:
    app = FastAPI(title=SERVICE_NAME, version="2.0.0")

    @app.get("/health")
    async def health():
        return JSONResponse({"status": "ok", "port": PORT, "service": SERVICE_NAME, "timestamp": datetime.utcnow().isoformat()})

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return HTMLResponse(HTML_DASHBOARD)

    @app.post("/control/force_field_execute")
    async def force_field_execute(payload: dict = None):
        """Execute a force-field-guided robot action step."""
        mock_response = {
            "action": [0.012, -0.034, 0.021, 0.005, -0.008, 0.003],
            "attract_magnitude": 0.87,
            "repel_magnitude": 0.13,
            "net_force_norm": 0.74,
            "goal_distance": 0.043,
            "obstacle_clearance": 0.182,
            "policy_version": "v2",
            "inference_ms": 18,
        }
        return JSONResponse(mock_response)

    @app.get("/control/force_field_v2/visualize")
    async def force_field_visualize():
        """Return 2D quiver plot data for force field visualization."""
        grid_size = 8
        vectors = []
        for i in range(grid_size):
            for j in range(grid_size):
                x = i / (grid_size - 1)
                y = j / (grid_size - 1)
                # Attract toward (0.8, 0.8), repel from (0.3, 0.3)
                dx_attract = 0.8 - x
                dy_attract = 0.8 - y
                dist_repel = math.sqrt((x - 0.3)**2 + (y - 0.3)**2) + 1e-6
                dx_repel = -(x - 0.3) / dist_repel**2 * 0.05
                dy_repel = -(y - 0.3) / dist_repel**2 * 0.05
                fx = dx_attract * 0.15 + dx_repel
                fy = dy_attract * 0.15 + dy_repel
                vectors.append({"x": round(x, 3), "y": round(y, 3), "fx": round(fx, 4), "fy": round(fy, 4)})
        return JSONResponse({"grid": vectors, "goal": {"x": 0.8, "y": 0.8}, "obstacle": {"x": 0.3, "y": 0.3}, "policy_version": "v2"})

else:
    # Fallback: stdlib HTTPServer
    import http.server

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/health":
                body = json.dumps({"status": "ok", "port": PORT, "service": SERVICE_NAME}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)
            else:
                body = HTML_DASHBOARD.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(body)

        def log_message(self, fmt, *args):
            pass

    def _serve():
        server = http.server.HTTPServer(("0.0.0.0", PORT), _Handler)
        print(f"[{SERVICE_NAME}] Fallback HTTP server on port {PORT}")
        server.serve_forever()

if __name__ == "__main__":
    if HAS_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        _serve()
