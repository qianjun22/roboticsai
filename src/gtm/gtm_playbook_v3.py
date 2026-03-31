"""GTM Playbook V3 — AI World + NVIDIA + Series A Integrated GTM (port 10251)"""

PORT = 10251
SERVICE_NAME = "gtm_playbook_v3"

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    _FASTAPI_AVAILABLE = True
except ImportError:
    _FASTAPI_AVAILABLE = False

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>GTM Playbook V3</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; padding: 2rem; }
    h1 { color: #C74634; font-size: 1.75rem; margin-bottom: 0.5rem; }
    .subtitle { color: #38bdf8; font-size: 1rem; margin-bottom: 2rem; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 1.25rem; margin-bottom: 2.5rem; }
    .card { background: #1e293b; border: 1px solid #334155; border-radius: 0.75rem; padding: 1.25rem; }
    .card h3 { color: #38bdf8; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.5rem; }
    .card .value { font-size: 2rem; font-weight: 700; color: #f1f5f9; }
    .card .label { font-size: 0.75rem; color: #94a3b8; margin-top: 0.25rem; }
    .chart-section { background: #1e293b; border: 1px solid #334155; border-radius: 0.75rem; padding: 1.5rem; margin-bottom: 2rem; }
    .chart-section h2 { color: #C74634; margin-bottom: 1rem; font-size: 1.1rem; }
    .phases { background: #1e293b; border: 1px solid #334155; border-radius: 0.75rem; padding: 1.5rem; margin-bottom: 2rem; }
    .phases h2 { color: #C74634; margin-bottom: 1rem; font-size: 1.1rem; }
    .phase { display: flex; gap: 1rem; padding: 0.75rem 0; border-bottom: 1px solid #334155; align-items: flex-start; }
    .phase:last-child { border-bottom: none; }
    .phase-badge { background: #C74634; color: #fff; font-size: 0.7rem; font-weight: 700; padding: 0.25rem 0.6rem; border-radius: 0.25rem; min-width: 60px; text-align: center; margin-top: 0.1rem; }
    .phase-info h4 { color: #f1f5f9; font-size: 0.95rem; margin-bottom: 0.2rem; }
    .phase-info p { color: #94a3b8; font-size: 0.82rem; }
    .endpoints { background: #1e293b; border: 1px solid #334155; border-radius: 0.75rem; padding: 1.5rem; }
    .endpoints h2 { color: #C74634; margin-bottom: 1rem; font-size: 1.1rem; }
    .ep { display: flex; align-items: center; gap: 0.75rem; padding: 0.5rem 0; border-bottom: 1px solid #334155; }
    .ep:last-child { border-bottom: none; }
    .method { background: #0c4a6e; color: #38bdf8; font-size: 0.75rem; font-weight: 700; padding: 0.2rem 0.5rem; border-radius: 0.25rem; min-width: 44px; text-align: center; }
    .path { color: #e2e8f0; font-family: monospace; font-size: 0.9rem; }
    .desc { color: #94a3b8; font-size: 0.8rem; margin-left: auto; }
  </style>
</head>
<body>
  <h1>GTM Playbook V3</h1>
  <p class="subtitle">AI World + NVIDIA + Series A Integrated GTM &mdash; Port 10251 &mdash; OCI Robot Cloud</p>

  <div class="grid">
    <div class="card">
      <h3>Inbound / Content</h3>
      <div class="value">42%</div>
      <div class="label">Channel mix share</div>
    </div>
    <div class="card">
      <h3>NVIDIA Referral</h3>
      <div class="value">35%</div>
      <div class="label">Channel mix share</div>
    </div>
    <div class="card">
      <h3>Conference</h3>
      <div class="value">23%</div>
      <div class="label">Channel mix share</div>
    </div>
    <div class="card">
      <h3>GTM Phases</h3>
      <div class="value">3</div>
      <div class="label">Land &rarr; Expand &rarr; Scale</div>
    </div>
  </div>

  <div class="chart-section">
    <h2>Channel Mix: GTM Pipeline Contribution</h2>
    <svg viewBox="0 0 520 200" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:520px;display:block;">
      <!-- Y-axis -->
      <line x1="70" y1="10" x2="70" y2="160" stroke="#334155" stroke-width="1"/>
      <!-- X-axis -->
      <line x1="70" y1="160" x2="490" y2="160" stroke="#334155" stroke-width="1"/>
      <!-- Y labels -->
      <text x="60" y="165" fill="#94a3b8" font-size="11" text-anchor="end">0%</text>
      <text x="60" y="115" fill="#94a3b8" font-size="11" text-anchor="end">25%</text>
      <text x="60" y="65" fill="#94a3b8" font-size="11" text-anchor="end">50%</text>
      <!-- Grid -->
      <line x1="70" y1="110" x2="490" y2="110" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,4"/>
      <line x1="70" y1="60" x2="490" y2="60" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,4"/>
      <!-- Inbound/Content 42% => height = 42/50*150 = 126 -->
      <rect x="95" y="34" width="90" height="126" fill="#C74634" rx="4"/>
      <text x="140" y="29" fill="#f1f5f9" font-size="13" font-weight="bold" text-anchor="middle">42%</text>
      <text x="140" y="180" fill="#94a3b8" font-size="10" text-anchor="middle">Inbound/Content</text>
      <!-- NVIDIA Referral 35% => height = 35/50*150 = 105 -->
      <rect x="215" y="55" width="90" height="105" fill="#38bdf8" rx="4"/>
      <text x="260" y="50" fill="#f1f5f9" font-size="13" font-weight="bold" text-anchor="middle">35%</text>
      <text x="260" y="180" fill="#94a3b8" font-size="10" text-anchor="middle">NVIDIA Referral</text>
      <!-- Conference 23% => height = 23/50*150 = 69 -->
      <rect x="335" y="91" width="90" height="69" fill="#7c3aed" rx="4"/>
      <text x="380" y="86" fill="#f1f5f9" font-size="13" font-weight="bold" text-anchor="middle">23%</text>
      <text x="380" y="180" fill="#94a3b8" font-size="10" text-anchor="middle">Conference</text>
    </svg>
  </div>

  <div class="phases">
    <h2>GTM Phases</h2>
    <div class="phase">
      <div class="phase-badge">LAND</div>
      <div class="phase-info">
        <h4>Phase 1: Design Partner Pilots</h4>
        <p>Onboard 5 design partners; co-develop robot + use case; produce case studies and reference architectures.</p>
      </div>
    </div>
    <div class="phase">
      <div class="phase-badge">EXPAND</div>
      <div class="phase-info">
        <h4>Phase 2: Robot + Use Case Expansion</h4>
        <p>Expand from pilot cohort to broader ICP; leverage NVIDIA referral channel; multi-robot deployment packages.</p>
      </div>
    </div>
    <div class="phase">
      <div class="phase-badge">SCALE</div>
      <div class="phase-info">
        <h4>Phase 3: AI World + NVIDIA + Series A</h4>
        <p>AI World launch event; NVIDIA ecosystem go-to-market; Series A fundraise fuels sales team and OCI capacity.</p>
      </div>
    </div>
  </div>

  <div class="endpoints">
    <h2>API Endpoints</h2>
    <div class="ep"><span class="method">GET</span><span class="path">/health</span><span class="desc">Service health check</span></div>
    <div class="ep"><span class="method">GET</span><span class="path">/</span><span class="desc">This dashboard</span></div>
    <div class="ep"><span class="method">GET</span><span class="path">/gtm/v3/playbook</span><span class="desc">Full GTM v3 playbook</span></div>
    <div class="ep"><span class="method">GET</span><span class="path">/gtm/v3/status</span><span class="desc">GTM execution status</span></div>
  </div>
</body>
</html>
"""

if _FASTAPI_AVAILABLE:
    app = FastAPI(title=SERVICE_NAME, version="1.0.0")

    @app.get("/health")
    async def health():
        return JSONResponse({"status": "ok", "port": PORT, "service": SERVICE_NAME})

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return HTMLResponse(content=DASHBOARD_HTML)

    @app.get("/gtm/v3/playbook")
    async def gtm_playbook():
        return JSONResponse({
            "version": 3,
            "title": "AI World + NVIDIA + Series A Integrated GTM",
            "channel_mix": {
                "inbound_content": 0.42,
                "nvidia_referral": 0.35,
                "conference": 0.23
            },
            "phases": [
                {
                    "phase": "land",
                    "label": "Design Partner Pilots",
                    "target_partners": 5,
                    "deliverables": ["case_studies", "reference_architectures", "pilot_reports"]
                },
                {
                    "phase": "expand",
                    "label": "Robot + Use Case Expansion",
                    "channels": ["nvidia_referral", "icp_outbound", "multi_robot_packages"]
                },
                {
                    "phase": "scale",
                    "label": "AI World + NVIDIA + Series A",
                    "milestones": ["ai_world_launch", "nvidia_ecosystem_gtm", "series_a_close"]
                }
            ]
        })

    @app.get("/gtm/v3/status")
    async def gtm_status():
        return JSONResponse({
            "version": 3,
            "status": "active",
            "current_phase": "expand",
            "design_partners_onboarded": 4,
            "design_partners_target": 5,
            "nvidia_referrals_active": 12,
            "series_a_status": "in_progress"
        })

else:
    import http.server
    import json
    import urllib.parse

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            path = urllib.parse.urlparse(self.path).path
            if path == "/health":
                body = json.dumps({"status": "ok", "port": PORT, "service": SERVICE_NAME}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
            elif path == "/gtm/v3/playbook":
                body = json.dumps({"version": 3, "title": "AI World + NVIDIA + Series A Integrated GTM"}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
            elif path == "/gtm/v3/status":
                body = json.dumps({"version": 3, "status": "active", "current_phase": "expand"}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
            else:
                body = DASHBOARD_HTML.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            pass

if __name__ == "__main__":
    if _FASTAPI_AVAILABLE:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        server = http.server.HTTPServer(("0.0.0.0", PORT), _Handler)
        print(f"[{SERVICE_NAME}] Fallback HTTP server on port {PORT}")
        server.serve_forever()
