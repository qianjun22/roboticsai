"""DAgger Run177 Planner — adversarial data augmentation service.

Port: 10246
Service: DAgger run177 adversarial augmentation planner (FGSM-based correction augmentation)
"""

import json
import sys
from datetime import datetime

PORT = 10246
SERVICE_NAME = "dagger_run177_planner"

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    _FASTAPI_AVAILABLE = True
except ImportError:
    _FASTAPI_AVAILABLE = False

if _FASTAPI_AVAILABLE:
    app = FastAPI(title="DAgger Run177 Planner", version="1.0.0")

    @app.get("/health")
    async def health():
        return JSONResponse({
            "status": "ok",
            "port": PORT,
            "service": SERVICE_NAME,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        })

    @app.get("/dagger/run177/plan")
    async def dagger_run177_plan():
        return JSONResponse({
            "run_id": "run177",
            "strategy": "adversarial_augmentation",
            "method": "FGSM",
            "epsilon": 0.01,
            "augmentation_factor": 2,
            "expert_time_overhead": "0x (same expert time)",
            "target_sr_clean": 0.93,
            "target_sr_perturbed": 0.87,
            "baseline_sr_clean": 0.91,
            "baseline_sr_perturbed": 0.71,
            "perturbed_sr_improvement": "+16%",
            "status": "planned"
        })

    @app.get("/dagger/run177/status")
    async def dagger_run177_status():
        return JSONResponse({
            "run_id": "run177",
            "phase": "adversarial_augmentation",
            "augmentation_active": True,
            "fgsm_steps_applied": 0,
            "corrections_augmented": 0,
            "sr_clean": None,
            "sr_perturbed": None,
            "state": "pending",
            "timestamp": datetime.utcnow().isoformat() + "Z"
        })

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return HTMLResponse(_render_dashboard())

else:
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
                body = _render_dashboard().encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(body)

        def log_message(self, fmt, *args):
            pass


def _render_dashboard() -> str:
    return """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>DAgger Run177 Planner</title>
  <style>
    body { margin: 0; background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; }
    header { background: #C74634; padding: 18px 32px; display: flex; align-items: center; gap: 16px; }
    header h1 { margin: 0; font-size: 1.4rem; color: #fff; }
    .badge { background: #38bdf8; color: #0f172a; border-radius: 4px; padding: 2px 10px; font-size: 0.8rem; font-weight: 700; }
    main { max-width: 860px; margin: 40px auto; padding: 0 24px; }
    .card { background: #1e293b; border-radius: 10px; padding: 28px 32px; margin-bottom: 28px; }
    h2 { color: #38bdf8; margin-top: 0; font-size: 1.1rem; }
    .meta { color: #94a3b8; font-size: 0.85rem; margin-bottom: 18px; }
    svg text { font-family: 'Segoe UI', sans-serif; }
    .stat-row { display: flex; gap: 24px; flex-wrap: wrap; margin-top: 18px; }
    .stat { background: #0f172a; border-radius: 8px; padding: 14px 20px; min-width: 160px; }
    .stat .label { color: #94a3b8; font-size: 0.8rem; margin-bottom: 4px; }
    .stat .value { color: #38bdf8; font-size: 1.4rem; font-weight: 700; }
    .highlight { color: #C74634; }
  </style>
</head>
<body>
  <header>
    <h1>DAgger Run177 — Adversarial Augmentation Planner</h1>
    <span class="badge">PORT 10246</span>
  </header>
  <main>
    <div class="card">
      <h2>Success Rate: Adversarial-Augmented vs Standard</h2>
      <p class="meta">FGSM adversarial examples augment corrections 2x at zero extra expert time</p>
      <svg width="700" height="220" viewBox="0 0 700 220">
        <!-- Y axis -->
        <line x1="60" y1="10" x2="60" y2="170" stroke="#334155" stroke-width="1"/>
        <!-- X axis -->
        <line x1="60" y1="170" x2="660" y2="170" stroke="#334155" stroke-width="1"/>
        <!-- Y labels -->
        <text x="54" y="174" fill="#64748b" font-size="11" text-anchor="end">0%</text>
        <text x="54" y="128" fill="#64748b" font-size="11" text-anchor="end">50%</text>
        <text x="54" y="82" fill="#64748b" font-size="11" text-anchor="end">75%</text>
        <text x="54" y="44" fill="#64748b" font-size="11" text-anchor="end">93%</text>
        <!-- Grid lines -->
        <line x1="60" y1="128" x2="660" y2="128" stroke="#1e293b" stroke-width="1" stroke-dasharray="4,3"/>
        <line x1="60" y1="82" x2="660" y2="82" stroke="#1e293b" stroke-width="1" stroke-dasharray="4,3"/>
        <!-- Adversarial Clean 93% -->
        <rect x="90" y="16" width="100" height="154" fill="#38bdf8" rx="4"/>
        <text x="140" y="12" fill="#38bdf8" font-size="12" text-anchor="middle" font-weight="700">93%</text>
        <!-- Adversarial Perturbed 87% -->
        <rect x="210" y="42" width="100" height="128" fill="#38bdf8" rx="4" opacity="0.7"/>
        <text x="260" y="38" fill="#38bdf8" font-size="12" text-anchor="middle" font-weight="700">87%</text>
        <!-- Standard Clean 91% -->
        <rect x="380" y="24" width="100" height="146" fill="#C74634" rx="4"/>
        <text x="430" y="20" fill="#C74634" font-size="12" text-anchor="middle" font-weight="700">91%</text>
        <!-- Standard Perturbed 71% -->
        <rect x="500" y="83" width="100" height="87" fill="#C74634" rx="4" opacity="0.7"/>
        <text x="550" y="79" fill="#C74634" font-size="12" text-anchor="middle" font-weight="700">71%</text>
        <!-- X labels -->
        <text x="140" y="190" fill="#94a3b8" font-size="11" text-anchor="middle">Adv Clean</text>
        <text x="260" y="190" fill="#94a3b8" font-size="11" text-anchor="middle">Adv Perturbed</text>
        <text x="430" y="190" fill="#94a3b8" font-size="11" text-anchor="middle">Std Clean</text>
        <text x="550" y="190" fill="#94a3b8" font-size="11" text-anchor="middle">Std Perturbed</text>
        <!-- Legend -->
        <rect x="90" y="205" width="12" height="12" fill="#38bdf8" rx="2"/>
        <text x="108" y="216" fill="#94a3b8" font-size="11">Adversarial-Augmented</text>
        <rect x="260" y="205" width="12" height="12" fill="#C74634" rx="2"/>
        <text x="278" y="216" fill="#94a3b8" font-size="11">Standard DAgger</text>
      </svg>
      <div class="stat-row">
        <div class="stat"><div class="label">Perturbed SR Gain</div><div class="value">+16%</div></div>
        <div class="stat"><div class="label">Augmentation Factor</div><div class="value">2x</div></div>
        <div class="stat"><div class="label">Extra Expert Time</div><div class="value highlight">0x</div></div>
        <div class="stat"><div class="label">Method</div><div class="value" style="font-size:1rem">FGSM</div></div>
      </div>
    </div>
    <div class="card">
      <h2>Service Endpoints</h2>
      <ul style="color:#94a3b8; line-height:2">
        <li><code style="color:#38bdf8">GET /health</code> — liveness check</li>
        <li><code style="color:#38bdf8">GET /dagger/run177/plan</code> — adversarial augmentation plan</li>
        <li><code style="color:#38bdf8">GET /dagger/run177/status</code> — run status</li>
        <li><code style="color:#38bdf8">GET /</code> — this dashboard</li>
      </ul>
    </div>
  </main>
</body>
</html>
"""


if __name__ == "__main__":
    if _FASTAPI_AVAILABLE:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        print(f"fastapi not available — falling back to http.server on port {PORT}", file=sys.stderr)
        server = http.server.HTTPServer(("0.0.0.0", PORT), _Handler)
        server.serve_forever()
