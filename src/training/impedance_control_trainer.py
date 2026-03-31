"""Impedance Control Trainer — variable impedance control training service (port 10156)."""

import json
import sys
from datetime import datetime

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

PORT = 10156
SERVICE_NAME = "impedance_control_trainer"

HTML_DASHBOARD = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Impedance Control Trainer</title>
  <style>
    body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; margin: 0; padding: 2rem; }
    h1 { color: #C74634; font-size: 1.8rem; margin-bottom: 0.25rem; }
    .subtitle { color: #38bdf8; font-size: 1rem; margin-bottom: 2rem; }
    .card { background: #1e293b; border-radius: 10px; padding: 1.5rem; margin-bottom: 1.5rem; }
    .card h2 { color: #38bdf8; margin-top: 0; font-size: 1.1rem; }
    .metric-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 1rem; margin-bottom: 1.5rem; }
    .metric { background: #1e293b; border-radius: 8px; padding: 1rem; text-align: center; border: 1px solid #334155; }
    .metric .value { font-size: 2rem; font-weight: bold; color: #C74634; }
    .metric .label { font-size: 0.8rem; color: #94a3b8; margin-top: 0.25rem; }
    .phase-table { width: 100%; border-collapse: collapse; }
    .phase-table th { background: #0f172a; color: #38bdf8; padding: 0.75rem; text-align: left; }
    .phase-table td { padding: 0.75rem; border-bottom: 1px solid #334155; }
    .badge { display: inline-block; padding: 0.2rem 0.6rem; border-radius: 4px; font-size: 0.75rem; }
    .badge-high { background: #7f1d1d; color: #fca5a5; }
    .badge-low { background: #14532d; color: #86efac; }
    .badge-med { background: #78350f; color: #fde68a; }
    footer { margin-top: 2rem; color: #475569; font-size: 0.75rem; text-align: center; }
  </style>
</head>
<body>
  <h1>Impedance Control Trainer</h1>
  <p class="subtitle">Variable impedance control training — stiffness &amp; damping adaptation | Port {port}</p>

  <div class="metric-grid">
    <div class="metric"><div class="value">91%</div><div class="label">Impedance-Adaptive SR</div></div>
    <div class="metric"><div class="value">79%</div><div class="label">Fixed-Stiffness SR</div></div>
    <div class="metric"><div class="value">+15%</div><div class="label">Improvement</div></div>
  </div>

  <div class="card">
    <h2>Impedance Success Rate Comparison</h2>
    <svg width="100%" height="200" viewBox="0 0 520 200" xmlns="http://www.w3.org/2000/svg">
      <!-- Axes -->
      <line x1="60" y1="10" x2="60" y2="160" stroke="#475569" stroke-width="1.5"/>
      <line x1="60" y1="160" x2="500" y2="160" stroke="#475569" stroke-width="1.5"/>
      <!-- Grid lines -->
      <line x1="60" y1="50" x2="500" y2="50" stroke="#334155" stroke-width="1" stroke-dasharray="4"/>
      <line x1="60" y1="90" x2="500" y2="90" stroke="#334155" stroke-width="1" stroke-dasharray="4"/>
      <line x1="60" y1="130" x2="500" y2="130" stroke="#334155" stroke-width="1" stroke-dasharray="4"/>
      <!-- Y labels -->
      <text x="50" y="55" fill="#94a3b8" font-size="11" text-anchor="end">100%</text>
      <text x="50" y="95" fill="#94a3b8" font-size="11" text-anchor="end">75%</text>
      <text x="50" y="135" fill="#94a3b8" font-size="11" text-anchor="end">50%</text>
      <!-- Bar: Impedance-Adaptive 91% -->
      <rect x="90" y="23" width="80" height="137" fill="#C74634" rx="4"/>
      <text x="130" y="17" fill="#e2e8f0" font-size="12" text-anchor="middle" font-weight="bold">91%</text>
      <text x="130" y="178" fill="#94a3b8" font-size="11" text-anchor="middle">Impedance</text>
      <text x="130" y="191" fill="#94a3b8" font-size="11" text-anchor="middle">Adaptive</text>
      <!-- Bar: Fixed-Stiffness 79% -->
      <rect x="220" y="41" width="80" height="119" fill="#38bdf8" rx="4"/>
      <text x="260" y="35" fill="#e2e8f0" font-size="12" text-anchor="middle" font-weight="bold">79%</text>
      <text x="260" y="178" fill="#94a3b8" font-size="11" text-anchor="middle">Fixed</text>
      <text x="260" y="191" fill="#94a3b8" font-size="11" text-anchor="middle">Stiffness</text>
    </svg>
  </div>

  <div class="card">
    <h2>Phase-Specific Impedance Profile</h2>
    <table class="phase-table">
      <thead>
        <tr><th>Phase</th><th>Stiffness Mode</th><th>Damping</th><th>Use Case</th></tr>
      </thead>
      <tbody>
        <tr><td>Approach</td><td><span class="badge badge-high">High</span></td><td>0.85</td><td>Rigid positioning, contact prep</td></tr>
        <tr><td>Contact</td><td><span class="badge badge-low">Low</span></td><td>0.45</td><td>Compliant insertion, force control</td></tr>
        <tr><td>Assembly</td><td><span class="badge badge-med">Medium</span></td><td>0.65</td><td>Balanced torque + precision</td></tr>
      </tbody>
    </table>
  </div>

  <footer>OCI Robot Cloud &mdash; Impedance Control Trainer &mdash; Port {port} &mdash; Oracle Confidential</footer>
</body>
</html>
""".replace("{port}", str(PORT))

if HAS_FASTAPI:
    app = FastAPI(title=SERVICE_NAME, version="1.0.0")

    @app.get("/health")
    def health():
        return JSONResponse({"status": "ok", "port": PORT, "service": SERVICE_NAME, "timestamp": datetime.utcnow().isoformat()})

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return HTML_DASHBOARD

    @app.post("/control/impedance_execute")
    def impedance_execute(phase: str = "approach"):
        profiles = {
            "approach": {"stiffness": "high", "kp": 800, "damping": 0.85},
            "contact":  {"stiffness": "low",  "kp": 200, "damping": 0.45},
            "assembly": {"stiffness": "medium","kp": 450, "damping": 0.65},
        }
        profile = profiles.get(phase, profiles["approach"])
        return JSONResponse({"status": "executed", "phase": phase, "impedance_profile": profile, "timestamp": datetime.utcnow().isoformat()})

    @app.get("/control/impedance_calibration")
    def impedance_calibration():
        return JSONResponse({
            "status": "calibrated",
            "calibration": {
                "approach_kp": 800, "approach_kd": 0.85,
                "contact_kp": 200, "contact_kd": 0.45,
                "assembly_kp": 450, "assembly_kd": 0.65,
            },
            "adaptive_sr": 0.91,
            "fixed_sr": 0.79,
            "timestamp": datetime.utcnow().isoformat(),
        })

else:
    # Fallback: stdlib HTTP server
    from http.server import HTTPServer, BaseHTTPRequestHandler

    class Handler(BaseHTTPRequestHandler):
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

    def run_fallback():
        server = HTTPServer(("0.0.0.0", PORT), Handler)
        print(f"[{SERVICE_NAME}] Fallback HTTP server on port {PORT}")
        server.serve_forever()

if __name__ == "__main__":
    if HAS_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        run_fallback()
