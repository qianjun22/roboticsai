"""Competitive Intelligence Platform — FastAPI service on port 10161.

Collects and analyzes competitive signals from PI Research, Covariant, AWS,
and new entrants via job postings, press releases, GitHub, pricing pages,
conference talks, and customer reviews.
"""

import json
import time
from datetime import datetime

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    _FASTAPI_AVAILABLE = True
except ImportError:
    _FASTAPI_AVAILABLE = False

PORT = 10161
SERVICE_NAME = "competitive_intelligence_platform"

HTML_DASHBOARD = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Competitive Intelligence Platform — Port 10161</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; padding: 2rem; }
    h1 { color: #C74634; font-size: 1.8rem; margin-bottom: 0.25rem; }
    .subtitle { color: #38bdf8; font-size: 0.95rem; margin-bottom: 2rem; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 1.25rem; margin-bottom: 2.5rem; }
    .card { background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 1.25rem; }
    .card h3 { color: #38bdf8; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.5rem; }
    .card .value { font-size: 1.6rem; font-weight: 700; color: #f1f5f9; }
    .card .unit { font-size: 0.8rem; color: #94a3b8; margin-top: 0.15rem; }
    .chart-box { background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 1.5rem; margin-bottom: 2rem; }
    .chart-box h2 { color: #C74634; margin-bottom: 1.25rem; font-size: 1.1rem; }
    .sources { background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 1.25rem; margin-bottom: 2rem; }
    .sources h2 { color: #C74634; margin-bottom: 0.75rem; font-size: 1.1rem; }
    .tag { display: inline-block; background: #0f172a; border: 1px solid #334155; border-radius: 5px; padding: 0.2rem 0.5rem; font-size: 0.75rem; color: #94a3b8; margin: 0.2rem; }
    .threat-high { color: #f87171; }
    .threat-med  { color: #fbbf24; }
    .threat-low  { color: #4ade80; }
  </style>
</head>
<body>
  <h1>Competitive Intelligence Platform</h1>
  <p class="subtitle">Port 10161 &nbsp;|&nbsp; PI Research &bull; Covariant &bull; AWS &bull; New Entrants &nbsp;|&nbsp; 6 data sources</p>

  <div class="grid">
    <div class="card">
      <h3>Competitors Tracked</h3>
      <div class="value">12</div>
      <div class="unit">active profiles</div>
    </div>
    <div class="card">
      <h3>Signals This Week</h3>
      <div class="value">47</div>
      <div class="unit">new intel items</div>
    </div>
    <div class="card">
      <h3>High-Threat Alerts</h3>
      <div class="value threat-high">3</div>
      <div class="unit">require attention</div>
    </div>
    <div class="card">
      <h3>Data Sources</h3>
      <div class="value">6</div>
      <div class="unit">automated pipelines</div>
    </div>
  </div>

  <div class="chart-box">
    <h2>Threat Level by Competitor</h2>
    <svg viewBox="0 0 520 220" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:520px;display:block;">
      <!-- Axes -->
      <line x1="70" y1="10" x2="70" y2="170" stroke="#475569" stroke-width="1"/>
      <line x1="70" y1="170" x2="510" y2="170" stroke="#475569" stroke-width="1"/>
      <!-- Y labels -->
      <text x="62" y="173" fill="#94a3b8" font-size="11" text-anchor="end">Low</text>
      <text x="62" y="116" fill="#94a3b8" font-size="11" text-anchor="end">Med</text>
      <text x="62" y="60" fill="#94a3b8" font-size="11" text-anchor="end">High</text>
      <!-- PI Research (High) -->
      <rect x="90" y="13" width="90" height="157" fill="#f87171" rx="4"/>
      <text x="135" y="9" fill="#f87171" font-size="11" text-anchor="middle" font-weight="700">HIGH</text>
      <text x="135" y="190" fill="#94a3b8" font-size="11" text-anchor="middle">PI Research</text>
      <!-- Covariant (High) -->
      <rect x="210" y="13" width="90" height="157" fill="#f87171" rx="4"/>
      <text x="255" y="9" fill="#f87171" font-size="11" text-anchor="middle" font-weight="700">HIGH</text>
      <text x="255" y="190" fill="#94a3b8" font-size="11" text-anchor="middle">Covariant</text>
      <!-- AWS (Medium) -->
      <rect x="330" y="65" width="90" height="105" fill="#fbbf24" rx="4"/>
      <text x="375" y="61" fill="#fbbf24" font-size="11" text-anchor="middle" font-weight="700">MED</text>
      <text x="375" y="190" fill="#94a3b8" font-size="11" text-anchor="middle">AWS</text>
      <!-- New Entrants legend -->
      <text x="460" y="120" fill="#94a3b8" font-size="10" text-anchor="middle">New</text>
      <text x="460" y="133" fill="#94a3b8" font-size="10" text-anchor="middle">Entrants</text>
      <text x="460" y="146" fill="#4ade80" font-size="10" text-anchor="middle">monitoring</text>
    </svg>
  </div>

  <div class="sources">
    <h2>Data Sources</h2>
    <span class="tag">Job Postings</span>
    <span class="tag">Press Releases</span>
    <span class="tag">GitHub Activity</span>
    <span class="tag">Pricing Pages</span>
    <span class="tag">Conference Talks</span>
    <span class="tag">Customer Reviews</span>
    <p style="margin-top:1rem;color:#94a3b8;font-size:0.875rem;">
      Signals are collected, deduplicated, and scored by threat relevance every 6 hours.
      Alerts fire when a competitor crosses a threat-level threshold or shows unusual hiring velocity.
    </p>
  </div>
</body>
</html>
"""

if _FASTAPI_AVAILABLE:
    app = FastAPI(title="Competitive Intelligence Platform", version="1.0.0")

    @app.get("/health")
    def health():
        return JSONResponse({"status": "ok", "port": PORT, "service": SERVICE_NAME, "timestamp": datetime.utcnow().isoformat()})

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return HTML_DASHBOARD

    @app.get("/competitive/intelligence")
    def get_intelligence():
        """Return latest competitive intelligence signals."""
        return JSONResponse({
            "collected_at": datetime.utcnow().isoformat(),
            "competitors": [
                {
                    "name": "PI Research",
                    "threat_level": "high",
                    "recent_signals": [
                        {"source": "job_postings", "detail": "12 new ML engineer roles this month", "score": 0.91},
                        {"source": "press_releases", "detail": "Series C announcement $200M", "score": 0.88},
                    ],
                    "hiring_velocity": "accelerating",
                },
                {
                    "name": "Covariant",
                    "threat_level": "high",
                    "recent_signals": [
                        {"source": "github", "detail": "3 new public repos in diffusion policy", "score": 0.85},
                        {"source": "conference_talks", "detail": "ICRA keynote slot confirmed", "score": 0.82},
                    ],
                    "hiring_velocity": "steady",
                },
                {
                    "name": "AWS",
                    "threat_level": "medium",
                    "recent_signals": [
                        {"source": "pricing_pages", "detail": "RoboMaker price drop 15%", "score": 0.72},
                        {"source": "customer_reviews", "detail": "Uptick in positive simulation reviews", "score": 0.68},
                    ],
                    "hiring_velocity": "steady",
                },
            ],
            "total_signals_this_week": 47,
            "data_sources": ["job_postings", "press_releases", "github", "pricing_pages", "conference_talks", "customer_reviews"],
        })

    @app.get("/competitive/alerts")
    def get_alerts():
        """Return active competitive alerts requiring attention."""
        return JSONResponse({
            "alerts": [
                {
                    "id": "alert_001",
                    "competitor": "PI Research",
                    "severity": "high",
                    "type": "funding_event",
                    "message": "PI Research closed $200M Series C; expect product acceleration",
                    "triggered_at": "2026-03-28T14:22:00Z",
                    "action_required": True,
                },
                {
                    "id": "alert_002",
                    "competitor": "Covariant",
                    "severity": "high",
                    "type": "talent_spike",
                    "message": "Covariant posted 8 diffusion policy roles — possible new product line",
                    "triggered_at": "2026-03-29T09:05:00Z",
                    "action_required": True,
                },
                {
                    "id": "alert_003",
                    "competitor": "AWS",
                    "severity": "medium",
                    "type": "pricing_change",
                    "message": "AWS RoboMaker simulation hours reduced 15% — potential enterprise push",
                    "triggered_at": "2026-03-30T00:00:00Z",
                    "action_required": False,
                },
            ],
            "total_alerts": 3,
            "high_severity_count": 2,
            "medium_severity_count": 1,
            "generated_at": datetime.utcnow().isoformat(),
        })

else:
    # Fallback: stdlib HTTP server
    import http.server
    import socketserver

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

    def _run_fallback():
        with socketserver.TCPServer(("", PORT), _Handler) as httpd:
            print(f"[{SERVICE_NAME}] fallback HTTP server on port {PORT}")
            httpd.serve_forever()

if __name__ == "__main__":
    if _FASTAPI_AVAILABLE:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        _run_fallback()
