"""Enterprise Onboarding Accelerator — FastAPI service (port 10233)

Accelerates enterprise customer onboarding from 18 days to 7 days by removing
friction across auth, SDK setup, and first evaluation run.
"""

import json
import time
import uuid
from typing import Any, Dict

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

PORT = 10233
SERVICE_NAME = "enterprise_onboarding_accelerator"

HTML_DASHBOARD = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Enterprise Onboarding Accelerator — OCI Robot Cloud</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; padding: 2rem; }
    h1 { color: #C74634; font-size: 1.8rem; margin-bottom: 0.25rem; }
    .subtitle { color: #38bdf8; font-size: 0.95rem; margin-bottom: 2rem; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-bottom: 2rem; }
    .card { background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 1.25rem; }
    .card-label { color: #94a3b8; font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.05em; }
    .card-value { color: #38bdf8; font-size: 1.6rem; font-weight: 700; margin-top: 0.25rem; }
    .card-unit { color: #64748b; font-size: 0.8rem; }
    .section { background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 1.5rem; margin-bottom: 1.5rem; }
    .section h2 { color: #C74634; font-size: 1.1rem; margin-bottom: 1rem; }
    .plan-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 0.75rem; }
    .plan-day { background: #0f172a; border: 1px solid #334155; border-radius: 6px; padding: 0.75rem; font-size: 0.85rem; }
    .plan-day-label { color: #C74634; font-weight: 700; font-size: 0.8rem; margin-bottom: 0.25rem; }
    .endpoints { list-style: none; }
    .endpoints li { padding: 0.4rem 0; border-bottom: 1px solid #334155; font-size: 0.9rem; }
    .endpoints li:last-child { border-bottom: none; }
    .method { display: inline-block; padding: 0.15rem 0.5rem; border-radius: 4px; font-size: 0.75rem; font-weight: 700; margin-right: 0.5rem; }
    .get { background: #166534; color: #4ade80; }
    .post { background: #1e40af; color: #93c5fd; }
    .path { color: #e2e8f0; font-family: monospace; }
    svg text { font-family: 'Segoe UI', system-ui, sans-serif; }
  </style>
</head>
<body>
  <h1>Enterprise Onboarding Accelerator</h1>
  <p class="subtitle">18 days → 7 days · Friction removed across auth, SDK, and first eval · Port 10233</p>

  <div class="grid">
    <div class="card">
      <div class="card-label">Before</div>
      <div class="card-value">18<span class="card-unit"> days</span></div>
      <div class="card-unit">legacy onboarding</div>
    </div>
    <div class="card">
      <div class="card-label">After</div>
      <div class="card-value">7<span class="card-unit"> days</span></div>
      <div class="card-unit">accelerated onboarding</div>
    </div>
    <div class="card">
      <div class="card-label">Time Saved</div>
      <div class="card-value">61<span class="card-unit">%</span></div>
      <div class="card-unit">reduction</div>
    </div>
    <div class="card">
      <div class="card-label">Auth Friction</div>
      <div class="card-value">4→0<span class="card-unit"> days</span></div>
      <div class="card-unit">eliminated</div>
    </div>
  </div>

  <div class="section">
    <h2>Friction Removal by Category (days saved)</h2>
    <!-- SVG bar chart: before (red) vs after (blue) -->
    <svg width="100%" viewBox="0 0 560 240" xmlns="http://www.w3.org/2000/svg">
      <text x="10" y="20" fill="#94a3b8" font-size="11">Days</text>

      <!-- Grid lines at 0,2,4,6 days (max=7 → scale to 180px) -->
      <!-- y_base=200, scale=180/7≈25.7px per day -->
      <line x1="70" y1="200" x2="530" y2="200" stroke="#475569" stroke-width="1.5"/>
      <line x1="70" y1="200" x2="70" y2="30" stroke="#475569" stroke-width="1.5"/>
      <line x1="70" y1="149" x2="530" y2="149" stroke="#334155" stroke-width="1"/>
      <line x1="70" y1="97"  x2="530" y2="97"  stroke="#334155" stroke-width="1"/>
      <line x1="70" y1="46"  x2="530" y2="46"  stroke="#334155" stroke-width="1"/>

      <text x="58" y="204" fill="#64748b" font-size="10" text-anchor="end">0</text>
      <text x="58" y="153" fill="#64748b" font-size="10" text-anchor="end">2</text>
      <text x="58" y="101" fill="#64748b" font-size="10" text-anchor="end">4</text>
      <text x="58" y="50"  fill="#64748b" font-size="10" text-anchor="end">6</text>

      <!-- Auth issues: before=4 days, after=0 -->
      <!-- before bar: height=4*25.7=102.8; y=200-102.8=97.2 -->
      <rect x="90"  y="97.2" width="55" height="102.8" fill="#C74634" rx="4" opacity="0.85"/>
      <text x="117" y="90"  fill="#e2e8f0" font-size="11" text-anchor="middle" font-weight="bold">4d</text>
      <!-- after bar: 0 days → tiny sliver for visibility -->
      <rect x="150" y="197" width="55" height="3"     fill="#38bdf8" rx="2" opacity="0.85"/>
      <text x="177" y="193" fill="#38bdf8" font-size="11" text-anchor="middle" font-weight="bold">0d</text>
      <text x="147" y="222" fill="#94a3b8" font-size="10" text-anchor="middle">Auth Issues</text>

      <!-- SDK setup: before=3 days, after=0 -->
      <!-- before: height=3*25.7=77.1; y=200-77.1=122.9 -->
      <rect x="230" y="122.9" width="55" height="77.1" fill="#C74634" rx="4" opacity="0.85"/>
      <text x="257" y="116"  fill="#e2e8f0" font-size="11" text-anchor="middle" font-weight="bold">3d</text>
      <rect x="290" y="197" width="55" height="3"     fill="#38bdf8" rx="2" opacity="0.85"/>
      <text x="317" y="193" fill="#38bdf8" font-size="11" text-anchor="middle" font-weight="bold">0d</text>
      <text x="287" y="222" fill="#94a3b8" font-size="10" text-anchor="middle">SDK Setup</text>

      <!-- First eval: before=6 days, after=2 -->
      <!-- before: height=6*25.7=154.2; y=200-154.2=45.8 -->
      <rect x="370" y="45.8" width="55" height="154.2" fill="#C74634" rx="4" opacity="0.85"/>
      <text x="397" y="39"  fill="#e2e8f0" font-size="11" text-anchor="middle" font-weight="bold">6d</text>
      <!-- after: height=2*25.7=51.4; y=200-51.4=148.6 -->
      <rect x="430" y="148.6" width="55" height="51.4" fill="#38bdf8" rx="4" opacity="0.85"/>
      <text x="457" y="142"  fill="#e2e8f0" font-size="11" text-anchor="middle" font-weight="bold">2d</text>
      <text x="427" y="222" fill="#94a3b8" font-size="10" text-anchor="middle">First Eval</text>

      <!-- Legend -->
      <rect x="80" y="230" width="12" height="8" fill="#C74634" rx="2"/>
      <text x="96" y="238" fill="#94a3b8" font-size="10">Before</text>
      <rect x="145" y="230" width="12" height="8" fill="#38bdf8" rx="2"/>
      <text x="161" y="238" fill="#94a3b8" font-size="10">After</text>
    </svg>
  </div>

  <div class="section">
    <h2>7-Day Onboarding Plan</h2>
    <div class="plan-grid">
      <div class="plan-day">
        <div class="plan-day-label">Day 1</div>
        Credentials provisioned, IAM roles configured, OCI tenancy access validated
      </div>
      <div class="plan-day">
        <div class="plan-day-label">Day 2–3</div>
        SDK installed, first fine-tune job launched on sample grasp dataset
      </div>
      <div class="plan-day">
        <div class="plan-day-label">Day 4–5</div>
        Eval run completed, results reviewed, policy iterated with customer data
      </div>
      <div class="plan-day">
        <div class="plan-day-label">Day 6–7</div>
        Production endpoint deployed, monitoring enabled, customer team trained
      </div>
    </div>
  </div>

  <div class="section">
    <h2>API Endpoints</h2>
    <ul class="endpoints">
      <li><span class="method get">GET</span><span class="path">/health</span> — Service health &amp; status</li>
      <li><span class="method get">GET</span><span class="path">/</span> — This dashboard</li>
      <li><span class="method post">POST</span><span class="path">/onboarding/start</span> — Initiate onboarding for a new enterprise customer</li>
      <li><span class="method get">GET</span><span class="path">/onboarding/status</span> — Get onboarding progress and current day</li>
    </ul>
  </div>
</body>
</html>
"""


if HAS_FASTAPI:
    app = FastAPI(title=SERVICE_NAME, version="1.0.0")

    @app.get("/health")
    async def health() -> JSONResponse:
        return JSONResponse({
            "status": "ok",
            "port": PORT,
            "service": SERVICE_NAME,
            "onboarding_target_days": 7,
            "baseline_days": 18,
        })

    @app.get("/", response_class=HTMLResponse)
    async def dashboard() -> HTMLResponse:
        return HTMLResponse(content=HTML_DASHBOARD)

    @app.post("/onboarding/start")
    async def start_onboarding(body: Dict[str, Any] = None) -> JSONResponse:
        """Initiate onboarding for a new enterprise customer (stub)."""
        customer_id = (body or {}).get("customer_id", f"cust-{uuid.uuid4().hex[:8]}")
        return JSONResponse({
            "status": "onboarding_started",
            "customer_id": customer_id,
            "onboarding_id": f"onb-{uuid.uuid4().hex[:12]}",
            "target_completion_days": 7,
            "current_day": 1,
            "next_milestone": "credentials_provisioned",
            "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        })

    @app.get("/onboarding/status")
    async def onboarding_status(onboarding_id: str = "") -> JSONResponse:
        """Get onboarding progress (stub)."""
        return JSONResponse({
            "onboarding_id": onboarding_id or f"onb-{uuid.uuid4().hex[:12]}",
            "current_day": 3,
            "total_days": 7,
            "percent_complete": 42,
            "milestones_completed": ["credentials_provisioned", "sdk_installed", "first_finetune_launched"],
            "milestones_pending": ["eval_run", "policy_iteration", "production_deploy", "team_training"],
            "status": "in_progress",
        })

else:
    # Fallback: stdlib http.server
    import http.server
    import socketserver

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
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

        def log_message(self, fmt, *args):  # silence default logging
            pass

    def _serve():
        with socketserver.TCPServer(("", PORT), _Handler) as httpd:
            print(f"[{SERVICE_NAME}] fallback http.server on port {PORT}")
            httpd.serve_forever()


if __name__ == "__main__":
    if HAS_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        _serve()
