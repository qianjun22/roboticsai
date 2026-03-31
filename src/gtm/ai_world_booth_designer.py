"""AI World Booth Designer — Booth Design Spec & Traffic Planning Service.

Port 10199 | Cycle 535B
10x10ft booth design spec, layout planning, and attendee traffic projections
for the AI World conference.
"""

import json
import time
from typing import Any, Dict

PORT = 10199
SERVICE_NAME = "ai_world_booth_designer"

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

# ---------------------------------------------------------------------------
# Stub data
# ---------------------------------------------------------------------------

BOOTH_DESIGN = {
    "event": "AI World",
    "booth_size_ft": "10x10",
    "layout": [
        {"zone": "front_center", "item": "Robot Demo Station", "size_ft": "4x4",
         "description": "Live GR00T N1.6 pick-and-place demo; primary attendee magnet"},
        {"zone": "left_wall",    "item": '65" TV Display',     "size_ft": "3x2",
         "description": "Loop: OCI Robot Cloud product video + metrics"},
        {"zone": "right_wall",   "item": "Interactive Kiosk",  "size_ft": "2x2",
         "description": "Touchscreen: architecture explorer + pricing calculator"},
        {"zone": "back_wall",    "item": "Backdrop Banner",    "size_ft": "10x8",
         "description": "Oracle Cloud + OCI Robot Cloud branding; QR code to docs"},
    ],
    "traffic_targets": {
        "badge_scans": 500,
        "demo_viewers": 360,
        "live_demos_per_hr": 3,
        "attendees_per_demo": 15,
    },
    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
}

BOOTH_CHECKLIST = {
    "event": "AI World",
    "checklist": [
        {"id": "C01", "category": "Hardware",   "item": "UR5e robot arm + gripper",          "status": "confirmed"},
        {"id": "C02", "category": "Hardware",   "item": '65" 4K TV on stand',               "status": "confirmed"},
        {"id": "C03", "category": "Hardware",   "item": "Touch-screen kiosk (24\")",          "status": "pending"},
        {"id": "C04", "category": "Hardware",   "item": "OCI A10 GPU laptop for inference",  "status": "confirmed"},
        {"id": "C05", "category": "Branding",   "item": "10x8ft backdrop banner (print)",    "status": "in_progress"},
        {"id": "C06", "category": "Branding",   "item": "Table throw + Oracle logo",         "status": "confirmed"},
        {"id": "C07", "category": "Software",   "item": "GR00T N1.6 inference server live",  "status": "confirmed"},
        {"id": "C08", "category": "Software",   "item": "Demo loop video (60-sec)",          "status": "confirmed"},
        {"id": "C09", "category": "Software",   "item": "Kiosk web app deployed",            "status": "pending"},
        {"id": "C10", "category": "Logistics",  "item": "Badge scanner app configured",     "status": "pending"},
        {"id": "C11", "category": "Logistics",  "item": "Lead capture CRM integration",     "status": "in_progress"},
        {"id": "C12", "category": "Logistics",  "item": "Staff briefing doc distributed",   "status": "pending"},
    ],
    "summary": {
        "total": 12,
        "confirmed": 6,
        "in_progress": 2,
        "pending": 4,
    },
    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
}

# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AI World Booth Designer — Port 10199</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; padding: 2rem; }}
    h1 {{ color: #C74634; font-size: 1.6rem; margin-bottom: 0.25rem; }}
    h2 {{ color: #38bdf8; font-size: 1rem; margin: 1.5rem 0 0.5rem; }}
    .badge {{ display: inline-block; background: #1e293b; border: 1px solid #334155;
              border-radius: 4px; padding: 0.15rem 0.6rem; font-size: 0.78rem;
              color: #94a3b8; margin-left: 0.5rem; }}
    .card {{ background: #1e293b; border: 1px solid #334155; border-radius: 8px;
             padding: 1.2rem 1.5rem; margin-bottom: 1rem; }}
    .metric {{ display: flex; gap: 2rem; flex-wrap: wrap; margin-top: 0.5rem; }}
    .metric-item {{ text-align: center; }}
    .metric-value {{ font-size: 1.8rem; font-weight: 700; color: #38bdf8; }}
    .metric-label {{ font-size: 0.75rem; color: #64748b; margin-top: 0.2rem; }}
    .layout-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 0.6rem; margin-top: 0.5rem; }}
    .zone {{ background: #0f172a; border: 1px solid #334155; border-radius: 6px;
             padding: 0.6rem 0.8rem; }}
    .zone-name {{ color: #38bdf8; font-size: 0.8rem; font-weight: 600; }}
    .zone-item {{ color: #e2e8f0; font-size: 0.85rem; margin: 0.2rem 0; }}
    .zone-desc {{ color: #64748b; font-size: 0.75rem; }}
    .endpoint {{ background: #0f172a; border-left: 3px solid #C74634;
                 padding: 0.4rem 0.8rem; margin: 0.3rem 0; border-radius: 0 4px 4px 0;
                 font-family: monospace; font-size: 0.85rem; color: #94a3b8; }}
    svg text {{ font-family: 'Segoe UI', sans-serif; }}
  </style>
</head>
<body>
  <h1>AI World Booth Designer <span class="badge">port 10199</span></h1>
  <p style="color:#64748b;font-size:0.85rem;">10x10ft booth design spec, layout planning &amp; attendee traffic projections</p>

  <h2>Traffic Plan (AI World, 10x10ft Booth)</h2>
  <div class="card">
    <svg width="480" height="210" viewBox="0 0 480 210" xmlns="http://www.w3.org/2000/svg">
      <!-- axes -->
      <line x1="70" y1="10" x2="70" y2="160" stroke="#334155" stroke-width="1.5"/>
      <line x1="70" y1="160" x2="460" y2="160" stroke="#334155" stroke-width="1.5"/>

      <!-- y gridlines & labels (max ~500) -->
      <line x1="70" y1="10"  x2="460" y2="10"  stroke="#1e293b" stroke-width="1"/>
      <line x1="70" y1="55"  x2="460" y2="55"  stroke="#1e293b" stroke-width="1"/>
      <line x1="70" y1="100" x2="460" y2="100" stroke="#1e293b" stroke-width="1"/>
      <line x1="70" y1="130" x2="460" y2="130" stroke="#1e293b" stroke-width="1"/>
      <text x="65" y="14"  text-anchor="end" fill="#64748b" font-size="11">500</text>
      <text x="65" y="59"  text-anchor="end" fill="#64748b" font-size="11">375</text>
      <text x="65" y="104" text-anchor="end" fill="#64748b" font-size="11">250</text>
      <text x="65" y="134" text-anchor="end" fill="#64748b" font-size="11">150</text>
      <text x="65" y="163" text-anchor="end" fill="#64748b" font-size="11">0</text>

      <!-- Badge Scans: 500 → height 150, y=10 -->
      <rect x="90"  y="10" width="80" height="150" fill="#38bdf8" rx="3"/>
      <text x="130" y="6"  text-anchor="middle" fill="#38bdf8" font-size="12" font-weight="700">500</text>
      <text x="130" y="178" text-anchor="middle" fill="#94a3b8" font-size="11">Badge</text>
      <text x="130" y="191" text-anchor="middle" fill="#64748b" font-size="10">Scans (target)</text>

      <!-- Demo Viewers: 360 → height 108, y=52 -->
      <rect x="210" y="52" width="80" height="108" fill="#C74634" rx="3"/>
      <text x="250" y="47"  text-anchor="middle" fill="#C74634" font-size="12" font-weight="700">360</text>
      <text x="250" y="178" text-anchor="middle" fill="#94a3b8" font-size="11">Demo</text>
      <text x="250" y="191" text-anchor="middle" fill="#64748b" font-size="10">Viewers</text>

      <!-- Live Demos capacity: 3/hr x 15 = 45/hr → show 45 -->
      <!-- height = 45/500 * 150 = 13.5, y = 146.5 -->
      <rect x="330" y="147" width="80" height="13" fill="#a3e635" rx="3"/>
      <text x="370" y="143" text-anchor="middle" fill="#a3e635" font-size="12" font-weight="700">45/hr</text>
      <text x="370" y="178" text-anchor="middle" fill="#94a3b8" font-size="11">Live Demo</text>
      <text x="370" y="191" text-anchor="middle" fill="#64748b" font-size="10">Capacity</text>
    </svg>
    <p style="font-size:0.75rem;color:#64748b;margin-top:0.4rem;">Live demos: 3/hr × 15 attendees = 45 attendees/hr demo capacity</p>
  </div>

  <h2>Booth Layout (10x10ft)</h2>
  <div class="card">
    <div class="layout-grid">
      <div class="zone">
        <div class="zone-name">Front Center</div>
        <div class="zone-item">Robot Demo Station (4x4ft)</div>
        <div class="zone-desc">GR00T N1.6 pick-and-place live demo</div>
      </div>
      <div class="zone">
        <div class="zone-name">Left Wall</div>
        <div class="zone-item">65" TV Display (3x2ft)</div>
        <div class="zone-desc">Product video loop + key metrics</div>
      </div>
      <div class="zone">
        <div class="zone-name">Right Wall</div>
        <div class="zone-item">Interactive Kiosk (2x2ft)</div>
        <div class="zone-desc">Architecture explorer + pricing calc</div>
      </div>
      <div class="zone">
        <div class="zone-name">Back Wall</div>
        <div class="zone-item">Backdrop Banner (10x8ft)</div>
        <div class="zone-desc">Oracle / OCI Robot Cloud branding + QR</div>
      </div>
    </div>
  </div>

  <h2>Endpoints</h2>
  <div class="card">
    <div class="endpoint">GET /health</div>
    <div class="endpoint">GET /</div>
    <div class="endpoint">GET /events/ai_world/booth_design</div>
    <div class="endpoint">GET /events/ai_world/booth_checklist</div>
  </div>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

if HAS_FASTAPI:
    app = FastAPI(
        title="AI World Booth Designer",
        description="AI World 10x10ft booth design spec, layout planning, and attendee traffic projections.",
        version="1.0.0",
    )

    @app.get("/health")
    def health() -> Dict[str, Any]:
        return {"status": "ok", "port": PORT, "service": SERVICE_NAME}

    @app.get("/", response_class=HTMLResponse)
    def dashboard() -> str:
        return DASHBOARD_HTML

    @app.get("/events/ai_world/booth_design")
    def get_booth_design() -> Dict[str, Any]:
        return BOOTH_DESIGN

    @app.get("/events/ai_world/booth_checklist")
    def get_booth_checklist() -> Dict[str, Any]:
        return BOOTH_CHECKLIST

# ---------------------------------------------------------------------------
# Fallback HTTP server
# ---------------------------------------------------------------------------

else:
    import http.server
    import socketserver

    class _Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):  # silence default logging
            pass

        def do_GET(self):
            if self.path == "/health":
                body = json.dumps({"status": "ok", "port": PORT, "service": SERVICE_NAME}).encode()
                ctype = "application/json"
            elif self.path == "/events/ai_world/booth_design":
                body = json.dumps(BOOTH_DESIGN).encode()
                ctype = "application/json"
            elif self.path == "/events/ai_world/booth_checklist":
                body = json.dumps(BOOTH_CHECKLIST).encode()
                ctype = "application/json"
            else:
                body = DASHBOARD_HTML.encode()
                ctype = "text/html"
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    def _serve():
        with socketserver.TCPServer(("", PORT), _Handler) as httpd:
            print(f"{SERVICE_NAME} fallback server running on port {PORT}")
            httpd.serve_forever()

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if HAS_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        _serve()
