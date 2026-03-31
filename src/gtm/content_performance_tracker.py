"""Content Performance Tracker — marketing content metrics across blog, video, GitHub, talks & social.

Port: 10223
Cycle: 541B
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    _FASTAPI_AVAILABLE = True
except ImportError:
    _FASTAPI_AVAILABLE = False

PORT = 10223
SERVICE_NAME = "content_performance_tracker"

# ---------------------------------------------------------------------------
# Content metrics data
# ---------------------------------------------------------------------------

CONTENT_METRICS: Dict[str, Any] = {
    "channels": [
        {"name": "Blog",      "metric": "Views/mo",     "value": 2300,  "unit": "2.3K"},
        {"name": "GitHub",    "metric": "Stars",        "value": 847,   "unit": "847"},
        {"name": "YouTube",   "metric": "Views",        "value": 1200,  "unit": "1.2K"},
        {"name": "LinkedIn",  "metric": "Impressions",  "value": 4800,  "unit": "4.8K"},
    ],
    "pipeline_attribution": {
        "attributed_pct": 31,
        "attributed_value_usd": 260000,
    },
    "roi": {
        "ratio": "325:1",
        "monthly_investment_hours": 8,
    },
}

RECOMMENDATIONS: List[Dict[str, str]] = [
    {"priority": "high",   "channel": "LinkedIn",  "action": "Double posting cadence — highest impression volume."},
    {"priority": "high",   "channel": "Blog",      "action": "Add OCI Robot Cloud tutorial series to drive SEO."},
    {"priority": "medium", "channel": "YouTube",   "action": "Publish demo video clips from Isaac Sim sessions."},
    {"priority": "medium", "channel": "GitHub",    "action": "Pin top 3 repos and add README badges for star growth."},
    {"priority": "low",    "channel": "Talks",     "action": "Submit GTC 2027 talk abstract by Q3 2026 deadline."},
]

DASHBOARD_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Content Performance Tracker</title>
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
    .endpoints { background: #1e293b; border: 1px solid #334155; border-radius: 0.75rem; padding: 1.25rem 1.75rem; margin-bottom: 2rem; }
    .ep { display: flex; align-items: center; gap: 0.75rem; padding: 0.45rem 0; border-bottom: 1px solid #0f172a; }
    .ep:last-child { border-bottom: none; }
    .method { background: #0c4a6e; color: #38bdf8; font-size: 0.72rem; font-weight: 700; padding: 0.2rem 0.5rem; border-radius: 0.3rem; }
    .path { color: #e2e8f0; font-family: monospace; font-size: 0.88rem; }
    .desc { color: #64748b; font-size: 0.8rem; margin-left: auto; }
    footer { margin-top: 2.5rem; color: #475569; font-size: 0.75rem; text-align: center; }
  </style>
</head>
<body>
  <h1>Content Performance Tracker</h1>
  <p class="subtitle">Blog &bull; GitHub &bull; YouTube &bull; LinkedIn &bull; Talks &mdash; port {port}</p>

  <div class="cards">
    <div class="card">
      <div class="card-label">Pipeline Attribution</div>
      <div class="card-value">31%</div>
      <div class="card-sub">$260K attributed</div>
    </div>
    <div class="card">
      <div class="card-label">Content ROI</div>
      <div class="card-value">325:1</div>
      <div class="card-sub">8 hr/mo investment</div>
    </div>
    <div class="card">
      <div class="card-label">LinkedIn</div>
      <div class="card-value">4.8K</div>
      <div class="card-sub">impressions/mo</div>
    </div>
    <div class="card">
      <div class="card-label">Blog</div>
      <div class="card-value">2.3K</div>
      <div class="card-sub">views/mo</div>
    </div>
    <div class="card">
      <div class="card-label">GitHub Stars</div>
      <div class="card-value">847</div>
      <div class="card-sub">total</div>
    </div>
    <div class="card">
      <div class="card-label">YouTube</div>
      <div class="card-value">1.2K</div>
      <div class="card-sub">views</div>
    </div>
  </div>

  <div class="chart-wrap">
    <div class="section-title">Content Channel Metrics (normalized to max 4800)</div>
    <svg width="540" height="210" viewBox="0 0 540 210" xmlns="http://www.w3.org/2000/svg">
      <!-- Axes -->
      <line x1="70" y1="10" x2="70" y2="160" stroke="#334155" stroke-width="1.5"/>
      <line x1="70" y1="160" x2="520" y2="160" stroke="#334155" stroke-width="1.5"/>

      <!-- Y-axis labels -->
      <text x="62" y="164" fill="#64748b" font-size="10" text-anchor="end">0</text>
      <text x="62" y="122" fill="#64748b" font-size="10" text-anchor="end">1.2K</text>
      <text x="62" y="84" fill="#64748b" font-size="10" text-anchor="end">2.4K</text>
      <text x="62" y="46" fill="#64748b" font-size="10" text-anchor="end">3.6K</text>
      <text x="62" y="12" fill="#64748b" font-size="10" text-anchor="end">4.8K</text>

      <!-- Grid lines -->
      <line x1="70" y1="120" x2="520" y2="120" stroke="#1e293b" stroke-width="1" stroke-dasharray="4,3"/>
      <line x1="70" y1="82" x2="520" y2="82" stroke="#1e293b" stroke-width="1" stroke-dasharray="4,3"/>
      <line x1="70" y1="44" x2="520" y2="44" stroke="#1e293b" stroke-width="1" stroke-dasharray="4,3"/>

      <!-- Blog: 2300/4800 * 150 = 71.9 -->
      <rect x="85" y="88" width="60" height="72" fill="#38bdf8" rx="4"/>
      <text x="115" y="82" fill="#38bdf8" font-size="11" font-weight="700" text-anchor="middle">2.3K</text>
      <text x="115" y="178" fill="#94a3b8" font-size="11" text-anchor="middle">Blog</text>
      <text x="115" y="191" fill="#64748b" font-size="9" text-anchor="middle">views/mo</text>

      <!-- GitHub: 847/4800 * 150 = 26.5 -->
      <rect x="195" y="133" width="60" height="27" fill="#C74634" rx="4"/>
      <text x="225" y="127" fill="#C74634" font-size="11" font-weight="700" text-anchor="middle">847</text>
      <text x="225" y="178" fill="#94a3b8" font-size="11" text-anchor="middle">GitHub</text>
      <text x="225" y="191" fill="#64748b" font-size="9" text-anchor="middle">stars</text>

      <!-- YouTube: 1200/4800 * 150 = 37.5 -->
      <rect x="305" y="122" width="60" height="38" fill="#a78bfa" rx="4"/>
      <text x="335" y="116" fill="#a78bfa" font-size="11" font-weight="700" text-anchor="middle">1.2K</text>
      <text x="335" y="178" fill="#94a3b8" font-size="11" text-anchor="middle">YouTube</text>
      <text x="335" y="191" fill="#64748b" font-size="9" text-anchor="middle">views</text>

      <!-- LinkedIn: 4800/4800 * 150 = 150 -->
      <rect x="415" y="10" width="60" height="150" fill="#34d399" rx="4"/>
      <text x="445" y="8" fill="#34d399" font-size="11" font-weight="700" text-anchor="middle">4.8K</text>
      <text x="445" y="178" fill="#94a3b8" font-size="11" text-anchor="middle">LinkedIn</text>
      <text x="445" y="191" fill="#64748b" font-size="9" text-anchor="middle">impressions</text>
    </svg>
  </div>

  <div class="endpoints">
    <div class="section-title">API Endpoints</div>
    <div class="ep"><span class="method">GET</span><span class="path">/health</span><span class="desc">Service health</span></div>
    <div class="ep"><span class="method">GET</span><span class="path">/</span><span class="desc">This dashboard</span></div>
    <div class="ep"><span class="method">GET</span><span class="path">/content/performance</span><span class="desc">All channel metrics + ROI</span></div>
    <div class="ep"><span class="method">GET</span><span class="path">/content/recommendations</span><span class="desc">Prioritized action items</span></div>
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

    @app.get("/content/performance")
    async def content_performance() -> JSONResponse:
        return JSONResponse(CONTENT_METRICS)

    @app.get("/content/recommendations")
    async def content_recommendations() -> JSONResponse:
        return JSONResponse({"recommendations": RECOMMENDATIONS})

else:
    import http.server

    class _Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
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


if __name__ == "__main__":
    if _FASTAPI_AVAILABLE:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        import http.server
        server = http.server.HTTPServer(("0.0.0.0", PORT), _Handler)
        print(f"Fallback http.server running on port {PORT}")
        server.serve_forever()
