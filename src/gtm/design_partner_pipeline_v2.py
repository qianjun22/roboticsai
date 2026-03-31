"""Design Partner Pipeline v2 — 5→8 target design partners, NVIDIA-referred (port 10157)."""

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

PORT = 10157
SERVICE_NAME = "design_partner_pipeline_v2"

HTML_DASHBOARD = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Design Partner Pipeline v2</title>
  <style>
    body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; margin: 0; padding: 2rem; }
    h1 { color: #C74634; font-size: 1.8rem; margin-bottom: 0.25rem; }
    .subtitle { color: #38bdf8; font-size: 1rem; margin-bottom: 2rem; }
    .card { background: #1e293b; border-radius: 10px; padding: 1.5rem; margin-bottom: 1.5rem; }
    .card h2 { color: #38bdf8; margin-top: 0; font-size: 1.1rem; }
    .metric-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 1rem; margin-bottom: 1.5rem; }
    .metric { background: #1e293b; border-radius: 8px; padding: 1rem; text-align: center; border: 1px solid #334155; }
    .metric .value { font-size: 2rem; font-weight: bold; color: #C74634; }
    .metric .label { font-size: 0.8rem; color: #94a3b8; margin-top: 0.25rem; }
    .partner-table { width: 100%; border-collapse: collapse; }
    .partner-table th { background: #0f172a; color: #38bdf8; padding: 0.75rem; text-align: left; }
    .partner-table td { padding: 0.75rem; border-bottom: 1px solid #334155; }
    .badge { display: inline-block; padding: 0.2rem 0.6rem; border-radius: 4px; font-size: 0.75rem; }
    .badge-qualified { background: #1e3a5f; color: #93c5fd; }
    .badge-proposal { background: #3b1f5e; color: #d8b4fe; }
    .badge-negotiation { background: #78350f; color: #fde68a; }
    .badge-signed { background: #14532d; color: #86efac; }
    footer { margin-top: 2rem; color: #475569; font-size: 0.75rem; text-align: center; }
  </style>
</head>
<body>
  <h1>Design Partner Pipeline v2</h1>
  <p class="subtitle">5 → 8 target design partners | NVIDIA-referred | $41.5K ARR each | Port {port}</p>

  <div class="metric-grid">
    <div class="metric"><div class="value">5</div><div class="label">Qualified</div></div>
    <div class="metric"><div class="value">3</div><div class="label">Proposal Sent</div></div>
    <div class="metric"><div class="value">2</div><div class="label">In Negotiation</div></div>
    <div class="metric"><div class="value">3</div><div class="label">Signed</div></div>
  </div>

  <div class="card">
    <h2>Pipeline Stage Distribution</h2>
    <svg width="100%" height="220" viewBox="0 0 560 220" xmlns="http://www.w3.org/2000/svg">
      <!-- Axes -->
      <line x1="60" y1="10" x2="60" y2="170" stroke="#475569" stroke-width="1.5"/>
      <line x1="60" y1="170" x2="540" y2="170" stroke="#475569" stroke-width="1.5"/>
      <!-- Grid lines (max 5) -->
      <line x1="60" y1="42" x2="540" y2="42" stroke="#334155" stroke-width="1" stroke-dasharray="4"/>
      <line x1="60" y1="74" x2="540" y2="74" stroke="#334155" stroke-width="1" stroke-dasharray="4"/>
      <line x1="60" y1="106" x2="540" y2="106" stroke="#334155" stroke-width="1" stroke-dasharray="4"/>
      <line x1="60" y1="138" x2="540" y2="138" stroke="#334155" stroke-width="1" stroke-dasharray="4"/>
      <!-- Y labels -->
      <text x="50" y="46" fill="#94a3b8" font-size="11" text-anchor="end">5</text>
      <text x="50" y="78" fill="#94a3b8" font-size="11" text-anchor="end">4</text>
      <text x="50" y="110" fill="#94a3b8" font-size="11" text-anchor="end">3</text>
      <text x="50" y="142" fill="#94a3b8" font-size="11" text-anchor="end">2</text>
      <text x="50" y="174" fill="#94a3b8" font-size="11" text-anchor="end">0</text>
      <!-- Bar: Qualified 5 -->
      <rect x="80" y="42" width="70" height="128" fill="#38bdf8" rx="4"/>
      <text x="115" y="36" fill="#e2e8f0" font-size="12" text-anchor="middle" font-weight="bold">5</text>
      <text x="115" y="190" fill="#94a3b8" font-size="11" text-anchor="middle">Qualified</text>
      <!-- Bar: Proposal Sent 3 -->
      <rect x="190" y="106" width="70" height="64" fill="#a78bfa" rx="4"/>
      <text x="225" y="100" fill="#e2e8f0" font-size="12" text-anchor="middle" font-weight="bold">3</text>
      <text x="225" y="190" fill="#94a3b8" font-size="11" text-anchor="middle">Proposal</text>
      <text x="225" y="203" fill="#94a3b8" font-size="11" text-anchor="middle">Sent</text>
      <!-- Bar: In Negotiation 2 -->
      <rect x="300" y="138" width="70" height="32" fill="#fbbf24" rx="4"/>
      <text x="335" y="132" fill="#e2e8f0" font-size="12" text-anchor="middle" font-weight="bold">2</text>
      <text x="335" y="190" fill="#94a3b8" font-size="11" text-anchor="middle">Negotiation</text>
      <!-- Bar: Signed 3 -->
      <rect x="410" y="106" width="70" height="64" fill="#C74634" rx="4"/>
      <text x="445" y="100" fill="#e2e8f0" font-size="12" text-anchor="middle" font-weight="bold">3</text>
      <text x="445" y="190" fill="#94a3b8" font-size="11" text-anchor="middle">Signed</text>
    </svg>
  </div>

  <div class="card">
    <h2>Pipeline Summary</h2>
    <table class="partner-table">
      <thead>
        <tr><th>Stage</th><th>Count</th><th>ARR Potential</th><th>Source</th></tr>
      </thead>
      <tbody>
        <tr><td><span class="badge badge-qualified">Qualified</span></td><td>5</td><td>$207.5K</td><td>NVIDIA referral + inbound</td></tr>
        <tr><td><span class="badge badge-proposal">Proposal Sent</span></td><td>3</td><td>$124.5K</td><td>NVIDIA-referred</td></tr>
        <tr><td><span class="badge badge-negotiation">In Negotiation</span></td><td>2</td><td>$83K</td><td>NVIDIA-referred</td></tr>
        <tr><td><span class="badge badge-signed">Signed</span></td><td>3</td><td>$124.5K</td><td>AI World pipeline</td></tr>
      </tbody>
    </table>
    <p style="color:#94a3b8; font-size:0.85rem; margin-top:1rem;">Target: 8 signed by AI World &mdash; Each DP ~$41.5K ARR &mdash; v2 expands from 5 original targets</p>
  </div>

  <footer>OCI Robot Cloud &mdash; Design Partner Pipeline v2 &mdash; Port {port} &mdash; Oracle Confidential</footer>
</body>
</html>
""".replace("{port}", str(PORT))

if HAS_FASTAPI:
    app = FastAPI(title=SERVICE_NAME, version="2.0.0")

    @app.get("/health")
    def health():
        return JSONResponse({"status": "ok", "port": PORT, "service": SERVICE_NAME, "timestamp": datetime.utcnow().isoformat()})

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return HTML_DASHBOARD

    @app.get("/partners/design_partners/v2")
    def get_design_partners_v2():
        return JSONResponse({
            "version": "v2",
            "total_targets": 8,
            "arr_per_partner": 41500,
            "partners": [
                {"id": f"dp-{i:03d}", "stage": stage, "arr": 41500, "source": "NVIDIA-referred"}
                for i, stage in enumerate(
                    ["signed", "signed", "signed", "negotiation", "negotiation",
                     "proposal_sent", "proposal_sent", "proposal_sent"], 1
                )
            ],
            "timestamp": datetime.utcnow().isoformat(),
        })

    @app.get("/partners/design_partners/v2/pipeline")
    def get_pipeline_v2():
        return JSONResponse({
            "version": "v2",
            "pipeline": {
                "qualified": 5,
                "proposal_sent": 3,
                "in_negotiation": 2,
                "signed": 3,
            },
            "target_signed": 8,
            "arr_per_partner": 41500,
            "total_arr_potential": 8 * 41500,
            "milestone": "AI World",
            "timestamp": datetime.utcnow().isoformat(),
        })

else:
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
