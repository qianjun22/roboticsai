"""Deformable Object Policy Service — port 10208

Policy training and inference for deformable object manipulation:
cloth folding, rope coiling, soft pouch grasping.
Uses FEM cloth simulation in Genesis.
Customer verticals: food packaging, textile, cable harnessing.
"""

import json
import time
from datetime import datetime

PORT = 10208
SERVICE_NAME = "deformable_object_policy"

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    _FASTAPI_AVAILABLE = True
except ImportError:
    _FASTAPI_AVAILABLE = False

HTML_DASHBOARD = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Deformable Object Policy — OCI Robot Cloud</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; padding: 2rem; }
    h1 { color: #C74634; font-size: 1.8rem; margin-bottom: 0.25rem; }
    .subtitle { color: #38bdf8; font-size: 0.95rem; margin-bottom: 2rem; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-bottom: 2rem; }
    .card { background: #1e293b; border-radius: 8px; padding: 1.25rem; border-left: 3px solid #C74634; }
    .card h3 { color: #38bdf8; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.5rem; }
    .card .value { font-size: 1.6rem; font-weight: bold; color: #f1f5f9; }
    .card .unit { font-size: 0.75rem; color: #94a3b8; margin-top: 0.2rem; }
    .chart-section { background: #1e293b; border-radius: 8px; padding: 1.5rem; margin-bottom: 2rem; }
    .chart-section h2 { color: #C74634; margin-bottom: 1rem; font-size: 1.1rem; }
    .endpoints { background: #1e293b; border-radius: 8px; padding: 1.5rem; }
    .endpoints h2 { color: #C74634; margin-bottom: 1rem; font-size: 1.1rem; }
    .endpoint { display: flex; align-items: center; gap: 0.75rem; padding: 0.5rem 0; border-bottom: 1px solid #334155; }
    .endpoint:last-child { border-bottom: none; }
    .method { background: #C74634; color: white; padding: 0.2rem 0.5rem; border-radius: 4px; font-size: 0.75rem; font-weight: bold; min-width: 45px; text-align: center; }
    .method.get { background: #0369a1; }
    .path { color: #38bdf8; font-family: monospace; font-size: 0.9rem; }
    .desc { color: #94a3b8; font-size: 0.85rem; margin-left: auto; }
  </style>
</head>
<body>
  <h1>Deformable Object Policy</h1>
  <p class="subtitle">OCI Robot Cloud — Port 10208 &nbsp;|&nbsp; FEM-based deformable manipulation training</p>

  <div class="grid">
    <div class="card">
      <h3>Avg Success Rate</h3>
      <div class="value">74%</div>
      <div class="unit">across object types</div>
    </div>
    <div class="card">
      <h3>Best Object Type</h3>
      <div class="value">Pouch</div>
      <div class="unit">81% SR grasp</div>
    </div>
    <div class="card">
      <h3>FEM Sim Steps</h3>
      <div class="value">2 k</div>
      <div class="unit">per training episode</div>
    </div>
    <div class="card">
      <h3>Customer Verticals</h3>
      <div class="value">3</div>
      <div class="unit">food pkg / textile / cable</div>
    </div>
  </div>

  <div class="chart-section">
    <h2>Success Rate by Object Type</h2>
    <svg viewBox="0 0 520 220" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:600px;">
      <!-- Y-axis labels -->
      <text x="38" y="20" fill="#94a3b8" font-size="10" text-anchor="end">100%</text>
      <text x="38" y="55" fill="#94a3b8" font-size="10" text-anchor="end">75%</text>
      <text x="38" y="90" fill="#94a3b8" font-size="10" text-anchor="end">50%</text>
      <text x="38" y="125" fill="#94a3b8" font-size="10" text-anchor="end">25%</text>
      <!-- Grid lines -->
      <line x1="42" y1="16" x2="510" y2="16" stroke="#334155" stroke-width="1" />
      <line x1="42" y1="51" x2="510" y2="51" stroke="#334155" stroke-width="1" />
      <line x1="42" y1="86" x2="510" y2="86" stroke="#334155" stroke-width="1" />
      <line x1="42" y1="121" x2="510" y2="121" stroke="#334155" stroke-width="1" />
      <line x1="42" y1="156" x2="510" y2="156" stroke="#334155" stroke-width="1" />
      <!-- Bars: bottom=156, height scale: 156px = 100% -->
      <!-- Cloth Fold 72% => height=110 -->
      <rect x="65" y="46" width="80" height="110" fill="#C74634" rx="3" />
      <text x="105" y="40" fill="#f1f5f9" font-size="11" text-anchor="middle" font-weight="bold">72%</text>
      <text x="105" y="172" fill="#94a3b8" font-size="10" text-anchor="middle">Cloth Fold</text>
      <!-- Rope Coil 68% => height=104 -->
      <rect x="185" y="52" width="80" height="104" fill="#0369a1" rx="3" />
      <text x="225" y="46" fill="#f1f5f9" font-size="11" text-anchor="middle" font-weight="bold">68%</text>
      <text x="225" y="172" fill="#94a3b8" font-size="10" text-anchor="middle">Rope Coil</text>
      <!-- Pouch Grasp 81% => height=124 -->
      <rect x="305" y="32" width="80" height="124" fill="#38bdf8" rx="3" />
      <text x="345" y="26" fill="#f1f5f9" font-size="11" text-anchor="middle" font-weight="bold">81%</text>
      <text x="345" y="172" fill="#94a3b8" font-size="10" text-anchor="middle">Pouch Grasp</text>
      <!-- Avg 74% => height=113 -->
      <rect x="425" y="43" width="80" height="113" fill="#7c3aed" rx="3" />
      <text x="465" y="37" fill="#f1f5f9" font-size="11" text-anchor="middle" font-weight="bold">74%</text>
      <text x="465" y="172" fill="#94a3b8" font-size="10" text-anchor="middle">Avg</text>
      <!-- X axis -->
      <line x1="42" y1="156" x2="510" y2="156" stroke="#475569" stroke-width="1.5" />
    </svg>
  </div>

  <div class="endpoints">
    <h2>API Endpoints</h2>
    <div class="endpoint">
      <span class="method get">GET</span>
      <span class="path">/health</span>
      <span class="desc">Service health + status</span>
    </div>
    <div class="endpoint">
      <span class="method get">GET</span>
      <span class="path">/</span>
      <span class="desc">This dashboard</span>
    </div>
    <div class="endpoint">
      <span class="method">POST</span>
      <span class="path">/training/deformable_train</span>
      <span class="desc">Launch deformable object training run</span>
    </div>
    <div class="endpoint">
      <span class="method">POST</span>
      <span class="path">/inference/deformable_execute</span>
      <span class="desc">Execute deformable manipulation policy</span>
    </div>
  </div>
</body>
</html>
"""

if _FASTAPI_AVAILABLE:
    app = FastAPI(
        title=SERVICE_NAME,
        description="Deformable object manipulation policy training and inference",
        version="1.0.0",
    )

    @app.get("/health")
    def health():
        return JSONResponse({
            "status": "ok",
            "port": PORT,
            "service": SERVICE_NAME,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        })

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return HTML_DASHBOARD

    @app.post("/training/deformable_train")
    def deformable_train(object_type: str = "cloth", episodes: int = 500):
        """Launch a deformable object policy training run (stub)."""
        return JSONResponse({
            "status": "queued",
            "object_type": object_type,
            "episodes": episodes,
            "estimated_duration_min": round(episodes * 0.045, 1),
            "sim_backend": "genesis_fem",
            "run_id": f"def-train-{int(time.time())}",
            "timestamp": datetime.utcnow().isoformat() + "Z",
        })

    @app.post("/inference/deformable_execute")
    def deformable_execute(object_type: str = "pouch", checkpoint: str = "latest"):
        """Execute deformable manipulation policy (stub)."""
        sr_map = {"cloth": 0.72, "rope": 0.68, "pouch": 0.81}
        return JSONResponse({
            "status": "success",
            "object_type": object_type,
            "checkpoint": checkpoint,
            "predicted_success_rate": sr_map.get(object_type, 0.74),
            "latency_ms": 241,
            "action_chunks": 16,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        })

else:
    # Fallback: stdlib HTTP server
    import http.server
    import socketserver

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
                body = HTML_DASHBOARD.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

    def _serve():
        with socketserver.TCPServer(("", PORT), _Handler) as httpd:
            print(f"[{SERVICE_NAME}] stdlib fallback listening on port {PORT}")
            httpd.serve_forever()

if __name__ == "__main__":
    if _FASTAPI_AVAILABLE:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        _serve()
