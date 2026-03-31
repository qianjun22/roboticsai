"""Customer Journey Optimizer — optimizing customer journey from trial to expansion.

Port: 10213
Service: customer-journey-optimizer
"""

import json
import random
from datetime import datetime

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    _FASTAPI_AVAILABLE = True
except ImportError:
    _FASTAPI_AVAILABLE = False

PORT = 10213
SERVICE_NAME = "customer-journey-optimizer"

HTML_DASHBOARD = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Customer Journey Optimizer</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; padding: 2rem; }
    h1 { color: #C74634; font-size: 1.8rem; margin-bottom: 0.5rem; }
    .subtitle { color: #38bdf8; font-size: 0.95rem; margin-bottom: 2rem; }
    .card { background: #1e293b; border-radius: 12px; padding: 1.5rem; margin-bottom: 1.5rem; }
    .card h2 { color: #38bdf8; font-size: 1.1rem; margin-bottom: 1rem; }
    .metric-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-bottom: 1.5rem; }
    .metric { background: #0f172a; border-radius: 8px; padding: 1rem; text-align: center; }
    .metric .value { font-size: 2rem; font-weight: bold; color: #C74634; }
    .metric .target { font-size: 1rem; color: #38bdf8; font-weight: 600; }
    .metric .label { font-size: 0.8rem; color: #94a3b8; margin-top: 0.25rem; }
    .tag { display: inline-block; background: #334155; color: #38bdf8; border-radius: 4px;
           padding: 0.2rem 0.6rem; font-size: 0.75rem; margin: 0.2rem; }
    .status-ok { color: #4ade80; font-weight: bold; }
    svg text { font-family: 'Segoe UI', sans-serif; }
  </style>
</head>
<body>
  <h1>Customer Journey Optimizer</h1>
  <p class="subtitle">Friction reduction &amp; personalization from trial to expansion &mdash; Port {PORT}</p>

  <div class="metric-grid">
    <div class="metric">
      <div class="value">18 d</div>
      <div class="target">Target: 10 d</div>
      <div class="label">Trial &rarr; Production</div>
    </div>
    <div class="metric">
      <div class="value">42 d</div>
      <div class="target">Target: 30 d</div>
      <div class="label">First SR Milestone</div>
    </div>
    <div class="metric">
      <div class="value">12 d</div>
      <div class="target">Target: 5 d</div>
      <div class="label">QBR Setup</div>
    </div>
    <div class="metric">
      <div class="value">74</div>
      <div class="target">vs 51 (friction-heavy)</div>
      <div class="label">NPS: Frictionless</div>
    </div>
  </div>

  <div class="card">
    <h2>Journey Friction: Current vs Target (days)</h2>
    <svg width="480" height="210" viewBox="0 0 480 210" xmlns="http://www.w3.org/2000/svg">
      <!-- axes -->
      <line x1="140" y1="20" x2="140" y2="170" stroke="#475569" stroke-width="1.5"/>
      <line x1="140" y1="170" x2="460" y2="170" stroke="#475569" stroke-width="1.5"/>
      <!-- y axis labels -->
      <text x="132" y="174" fill="#94a3b8" font-size="10" text-anchor="end">0</text>
      <text x="132" y="134" fill="#94a3b8" font-size="10" text-anchor="end">15</text>
      <text x="132" y="94" fill="#94a3b8" font-size="10" text-anchor="end">30</text>
      <text x="132" y="54" fill="#94a3b8" font-size="10" text-anchor="end">45</text>
      <!-- grid -->
      <line x1="140" y1="130" x2="460" y2="130" stroke="#1e293b" stroke-width="1"/>
      <line x1="140" y1="90" x2="460" y2="90" stroke="#1e293b" stroke-width="1"/>
      <line x1="140" y1="50" x2="460" y2="50" stroke="#1e293b" stroke-width="1"/>
      <!-- group 1: Trial->Production current=18, target=10 -->
      <rect x="155" y="122" width="28" height="48" rx="3" fill="#C74634" opacity="0.9"/>
      <text x="169" y="118" fill="#e2e8f0" font-size="10" text-anchor="middle">18d</text>
      <rect x="187" y="143" width="28" height="27" rx="3" fill="#38bdf8" opacity="0.8"/>
      <text x="201" y="139" fill="#38bdf8" font-size="10" text-anchor="middle">10d</text>
      <text x="183" y="192" fill="#94a3b8" font-size="9" text-anchor="middle">Trial&rarr;Prod</text>
      <!-- group 2: First SR current=42, target=30 -->
      <rect x="255" y="58" width="28" height="112" rx="3" fill="#C74634" opacity="0.9"/>
      <text x="269" y="54" fill="#e2e8f0" font-size="10" text-anchor="middle">42d</text>
      <rect x="287" y="90" width="28" height="80" rx="3" fill="#38bdf8" opacity="0.8"/>
      <text x="301" y="86" fill="#38bdf8" font-size="10" text-anchor="middle">30d</text>
      <text x="283" y="192" fill="#94a3b8" font-size="9" text-anchor="middle">First SR</text>
      <!-- group 3: QBR Setup current=12, target=5 -->
      <rect x="355" y="138" width="28" height="32" rx="3" fill="#C74634" opacity="0.9"/>
      <text x="369" y="134" fill="#e2e8f0" font-size="10" text-anchor="middle">12d</text>
      <rect x="387" y="157" width="28" height="13" rx="3" fill="#38bdf8" opacity="0.8"/>
      <text x="401" y="153" fill="#38bdf8" font-size="10" text-anchor="middle">5d</text>
      <text x="383" y="192" fill="#94a3b8" font-size="9" text-anchor="middle">QBR Setup</text>
      <!-- legend -->
      <rect x="155" y="200" width="10" height="8" fill="#C74634"/>
      <text x="169" y="208" fill="#94a3b8" font-size="9">Current</text>
      <rect x="210" y="200" width="10" height="8" fill="#38bdf8"/>
      <text x="224" y="208" fill="#94a3b8" font-size="9">Target</text>
    </svg>
  </div>

  <div class="card">
    <h2>Personalization &amp; NPS</h2>
    <p style="color:#94a3b8; font-size:0.9rem; line-height:1.7;">
      NPS frictionless journey: <span class="tag">74</span>
      NPS friction-heavy: <span class="tag">51</span><br/>
      Personalized by: <span class="tag">use case</span> <span class="tag">team type</span><br/>
      Status: <span class="status-ok">ONLINE</span>
    </p>
  </div>

  <div class="card">
    <h2>API Endpoints</h2>
    <p style="color:#94a3b8; font-size:0.9rem; line-height:1.8;">
      <span class="tag">GET</span> /health &nbsp; Service health check<br/>
      <span class="tag">GET</span> /customers/journey &nbsp; Retrieve active customer journey stages<br/>
      <span class="tag">GET</span> /customers/journey/analytics &nbsp; Journey funnel analytics &amp; friction metrics
    </p>
  </div>
</body>
</html>
""".replace("{PORT}", str(PORT))


if _FASTAPI_AVAILABLE:
    app = FastAPI(title=SERVICE_NAME, version="1.0.0")

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

    @app.get("/customers/journey")
    def get_journey():
        """Retrieve active customer journey stages with friction metrics."""
        return JSONResponse({
            "stages": [
                {"stage": "trial", "avg_days": 18, "target_days": 10, "status": "above_target"},
                {"stage": "first_sr_milestone", "avg_days": 42, "target_days": 30, "status": "above_target"},
                {"stage": "qbr_setup", "avg_days": 12, "target_days": 5, "status": "above_target"},
                {"stage": "expansion", "avg_days": 90, "target_days": 60, "status": "above_target"},
            ],
            "personalization": ["use_case", "team_type"],
            "nps": {"frictionless": 74, "friction_heavy": 51},
            "retrieved_at": datetime.utcnow().isoformat() + "Z",
        })

    @app.get("/customers/journey/analytics")
    def get_journey_analytics():
        """Journey funnel analytics and friction metrics."""
        return JSONResponse({
            "funnel": {
                "trial_starts": random.randint(180, 220),
                "reached_production": random.randint(120, 150),
                "first_sr_milestone": random.randint(90, 120),
                "qbr_completed": random.randint(60, 90),
                "expanded": random.randint(40, 70),
            },
            "friction_reduction_opportunity_days": {
                "trial_to_production": 8,
                "first_sr_milestone": 12,
                "qbr_setup": 7,
            },
            "nps_delta": 23,
            "generated_at": datetime.utcnow().isoformat() + "Z",
        })

else:
    import http.server
    import urllib.parse

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            path = urllib.parse.urlparse(self.path).path
            if path == "/health":
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

        def log_message(self, fmt, *args):
            pass


if __name__ == "__main__":
    if _FASTAPI_AVAILABLE:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        print(f"FastAPI not available — falling back to http.server on port {PORT}")
        server = http.server.HTTPServer(("0.0.0.0", PORT), _Handler)
        server.serve_forever()
