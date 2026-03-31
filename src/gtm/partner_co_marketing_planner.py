"""Partner Co-Marketing Planner — NVIDIA + Oracle joint content, events, and PR service.

Port: 10247
Service: NVIDIA + Oracle co-marketing plan planner (joint content, events, PR)
"""

import json
import sys
from datetime import datetime

PORT = 10247
SERVICE_NAME = "partner_co_marketing_planner"

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    _FASTAPI_AVAILABLE = True
except ImportError:
    _FASTAPI_AVAILABLE = False

if _FASTAPI_AVAILABLE:
    app = FastAPI(title="Partner Co-Marketing Planner", version="1.0.0")

    @app.get("/health")
    async def health():
        return JSONResponse({
            "status": "ok",
            "port": PORT,
            "service": SERVICE_NAME,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        })

    @app.get("/marketing/co_marketing/plan")
    async def co_marketing_plan():
        return JSONResponse({
            "partners": ["NVIDIA", "Oracle"],
            "total_estimated_reach": 17000,
            "channels": [
                {"name": "NVIDIA Blog", "expected_views": 12000, "date": "2026-06"},
                {"name": "GTC Session", "expected_attendees": 800, "date": "2026-06"},
                {"name": "Oracle Blog", "expected_views": 4000, "date": "2026-07"},
                {"name": "Oracle Cloud World", "type": "event", "date": "2026-07"},
                {"name": "AI World Joint Announcement", "type": "press", "date": "2026-09"},
                {"name": "GTC Proposal", "type": "proposal", "date": "2026-10"}
            ],
            "timeline": [
                {"month": "June 2026", "action": "NVIDIA blog post — OCI Robot Cloud feature"},
                {"month": "July 2026", "action": "Oracle Cloud World joint demo session"},
                {"month": "September 2026", "action": "AI World joint announcement + press release"},
                {"month": "October 2026", "action": "GTC 2027 session proposal submission"}
            ],
            "status": "planned"
        })

    @app.get("/marketing/co_marketing/status")
    async def co_marketing_status():
        return JSONResponse({
            "service": SERVICE_NAME,
            "active_campaigns": 0,
            "upcoming_milestones": [
                {"milestone": "NVIDIA blog draft due", "date": "2026-05-15"},
                {"milestone": "Cloud World session abstract", "date": "2026-06-01"}
            ],
            "state": "planning",
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
  <title>Partner Co-Marketing Planner</title>
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
    .timeline { list-style: none; padding: 0; margin: 0; }
    .timeline li { display: flex; gap: 16px; padding: 12px 0; border-bottom: 1px solid #0f172a; }
    .timeline li:last-child { border-bottom: none; }
    .tl-month { color: #38bdf8; font-weight: 700; min-width: 130px; font-size: 0.9rem; }
    .tl-action { color: #cbd5e1; font-size: 0.9rem; }
  </style>
</head>
<body>
  <header>
    <h1>NVIDIA + Oracle Co-Marketing Planner</h1>
    <span class="badge">PORT 10247</span>
  </header>
  <main>
    <div class="card">
      <h2>Estimated Reach by Channel</h2>
      <p class="meta">Joint content + events + PR — total 17K reach across NVIDIA and Oracle audiences</p>
      <svg width="680" height="220" viewBox="0 0 680 220">
        <!-- Y axis -->
        <line x1="60" y1="10" x2="60" y2="170" stroke="#334155" stroke-width="1"/>
        <!-- X axis -->
        <line x1="60" y1="170" x2="640" y2="170" stroke="#334155" stroke-width="1"/>
        <!-- Y grid & labels -->
        <line x1="60" y1="170" x2="640" y2="170" stroke="#1e293b" stroke-width="1" stroke-dasharray="4,3"/>
        <line x1="60" y1="116" x2="640" y2="116" stroke="#1e293b" stroke-width="1" stroke-dasharray="4,3"/>
        <line x1="60" y1="62" x2="640" y2="62" stroke="#1e293b" stroke-width="1" stroke-dasharray="4,3"/>
        <text x="54" y="174" fill="#64748b" font-size="11" text-anchor="end">0</text>
        <text x="54" y="120" fill="#64748b" font-size="11" text-anchor="end">5K</text>
        <text x="54" y="66" fill="#64748b" font-size="11" text-anchor="end">10K</text>
        <!-- NVIDIA Blog 12K -->
        <rect x="85" y="16" width="100" height="154" fill="#38bdf8" rx="4"/>
        <text x="135" y="12" fill="#38bdf8" font-size="12" text-anchor="middle" font-weight="700">12K</text>
        <!-- GTC Session 800 -->
        <rect x="215" y="163" width="100" height="7" fill="#38bdf8" rx="2" opacity="0.7"/>
        <text x="265" y="158" fill="#38bdf8" font-size="12" text-anchor="middle" font-weight="700">800</text>
        <!-- Oracle Blog 4K -->
        <rect x="345" y="116" width="100" height="54" fill="#C74634" rx="4"/>
        <text x="395" y="112" fill="#C74634" font-size="12" text-anchor="middle" font-weight="700">4K</text>
        <!-- Total 17K (capped) -->
        <rect x="475" y="30" width="100" height="140" fill="#C74634" rx="4" opacity="0.7"/>
        <text x="525" y="26" fill="#C74634" font-size="12" text-anchor="middle" font-weight="700">17K</text>
        <!-- X labels -->
        <text x="135" y="190" fill="#94a3b8" font-size="11" text-anchor="middle">NVIDIA Blog</text>
        <text x="265" y="190" fill="#94a3b8" font-size="11" text-anchor="middle">GTC Session</text>
        <text x="395" y="190" fill="#94a3b8" font-size="11" text-anchor="middle">Oracle Blog</text>
        <text x="525" y="190" fill="#94a3b8" font-size="11" text-anchor="middle">Total</text>
        <!-- Legend -->
        <rect x="85" y="205" width="12" height="12" fill="#38bdf8" rx="2"/>
        <text x="103" y="216" fill="#94a3b8" font-size="11">NVIDIA channels</text>
        <rect x="240" y="205" width="12" height="12" fill="#C74634" rx="2"/>
        <text x="258" y="216" fill="#94a3b8" font-size="11">Oracle / Combined</text>
      </svg>
      <div class="stat-row">
        <div class="stat"><div class="label">NVIDIA Blog Views</div><div class="value">12K</div></div>
        <div class="stat"><div class="label">GTC Attendees</div><div class="value">800</div></div>
        <div class="stat"><div class="label">Oracle Blog Views</div><div class="value">4K</div></div>
        <div class="stat"><div class="label">Total Reach</div><div class="value">17K</div></div>
      </div>
    </div>
    <div class="card">
      <h2>Campaign Timeline</h2>
      <ul class="timeline">
        <li><span class="tl-month">June 2026</span><span class="tl-action">NVIDIA blog post — OCI Robot Cloud feature</span></li>
        <li><span class="tl-month">July 2026</span><span class="tl-action">Oracle Cloud World joint demo session</span></li>
        <li><span class="tl-month">September 2026</span><span class="tl-action">AI World joint announcement + press release</span></li>
        <li><span class="tl-month">October 2026</span><span class="tl-action">GTC 2027 session proposal submission</span></li>
      </ul>
    </div>
    <div class="card">
      <h2>Service Endpoints</h2>
      <ul style="color:#94a3b8; line-height:2">
        <li><code style="color:#38bdf8">GET /health</code> — liveness check</li>
        <li><code style="color:#38bdf8">GET /marketing/co_marketing/plan</code> — full co-marketing plan</li>
        <li><code style="color:#38bdf8">GET /marketing/co_marketing/status</code> — campaign status</li>
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
