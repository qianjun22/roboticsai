"""Investor Pitch Tracker — tracks the full pitch funnel from research to close (port 10263).

AI World 200 investor attendees; NVIDIA 3 warm intros; deck v6 ready; data room 87% complete.
Funnel: research → intro → first meeting → deep dive → partner meeting → term sheet → close.
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

PORT = 10263
SERVICE_NAME = "investor_pitch_tracker"

STARTED_AT = datetime.utcnow().isoformat() + "Z"

HTML_DASHBOARD = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Investor Pitch Tracker</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; padding: 2rem; }
    h1 { color: #C74634; font-size: 1.8rem; margin-bottom: 0.4rem; }
    .subtitle { color: #38bdf8; font-size: 0.95rem; margin-bottom: 2rem; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-bottom: 2rem; }
    .card { background: #1e293b; border-radius: 10px; padding: 1.2rem; border-left: 4px solid #C74634; }
    .card .label { font-size: 0.75rem; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.05em; }
    .card .value { font-size: 1.6rem; font-weight: 700; color: #38bdf8; margin-top: 0.3rem; }
    .section { background: #1e293b; border-radius: 10px; padding: 1.5rem; margin-bottom: 1.5rem; }
    .section h2 { color: #38bdf8; font-size: 1.1rem; margin-bottom: 1rem; }
    .funnel-label { font-size: 0.82rem; color: #94a3b8; }
    .footer { color: #475569; font-size: 0.8rem; margin-top: 2rem; }
  </style>
</head>
<body>
  <h1>Investor Pitch Tracker</h1>
  <p class="subtitle">Full Funnel: Research &rarr; Intro &rarr; First Meeting &rarr; Deep Dive &rarr; Partner Meeting &rarr; Term Sheet &rarr; Close &mdash; Port {port}</p>

  <div class="grid">
    <div class="card"><div class="label">AI World Attendees</div><div class="value">200</div></div>
    <div class="card"><div class="label">NVIDIA Warm Intros</div><div class="value">3</div></div>
    <div class="card"><div class="label">Deck Version</div><div class="value">v6</div></div>
    <div class="card"><div class="label">Data Room</div><div class="value">87%</div></div>
  </div>

  <!-- SVG Funnel Bar Chart -->
  <div class="section">
    <h2>7-Stage Investor Pitch Funnel</h2>
    <svg viewBox="0 0 520 260" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:520px;display:block;">
      <!-- Axes -->
      <line x1="130" y1="10" x2="130" y2="190" stroke="#475569" stroke-width="1"/>
      <line x1="130" y1="190" x2="510" y2="190" stroke="#475569" stroke-width="1"/>
      <!-- Y-axis stage labels -->
      <text x="125" y="38" fill="#94a3b8" font-size="10" text-anchor="end">Research</text>
      <text x="125" y="63" fill="#94a3b8" font-size="10" text-anchor="end">Intro</text>
      <text x="125" y="88" fill="#94a3b8" font-size="10" text-anchor="end">First Meeting</text>
      <text x="125" y="113" fill="#94a3b8" font-size="10" text-anchor="end">Deep Dive</text>
      <text x="125" y="138" fill="#94a3b8" font-size="10" text-anchor="end">Partner Mtg</text>
      <text x="125" y="163" fill="#94a3b8" font-size="10" text-anchor="end">Term Sheet</text>
      <text x="125" y="188" fill="#94a3b8" font-size="10" text-anchor="end">Close</text>
      <!-- Bars (horizontal funnel): counts 200, 48, 22, 12, 6, 3, 1 scaled to max 360px = 200 -->
      <!-- Research: 200 → 360px -->
      <rect x="133" y="24" width="360" height="18" fill="#38bdf8" rx="3"/>
      <text x="498" y="37" fill="#38bdf8" font-size="10" font-weight="bold">200</text>
      <!-- Intro: 48 → 86px -->
      <rect x="133" y="49" width="86" height="18" fill="#38bdf8" rx="3" opacity="0.9"/>
      <text x="224" y="62" fill="#38bdf8" font-size="10" font-weight="bold">48</text>
      <!-- First Meeting: 22 → 40px -->
      <rect x="133" y="74" width="40" height="18" fill="#C74634" rx="3" opacity="0.95"/>
      <text x="178" y="87" fill="#C74634" font-size="10" font-weight="bold">22</text>
      <!-- Deep Dive: 12 → 22px -->
      <rect x="133" y="99" width="22" height="18" fill="#C74634" rx="3" opacity="0.85"/>
      <text x="160" y="112" fill="#C74634" font-size="10" font-weight="bold">12</text>
      <!-- Partner Meeting: 6 → 11px -->
      <rect x="133" y="124" width="11" height="18" fill="#C74634" rx="3" opacity="0.75"/>
      <text x="149" y="137" fill="#C74634" font-size="10" font-weight="bold">6</text>
      <!-- Term Sheet: 3 → 5px -->
      <rect x="133" y="149" width="5" height="18" fill="#C74634" rx="3" opacity="0.65"/>
      <text x="143" y="162" fill="#C74634" font-size="10" font-weight="bold">3</text>
      <!-- Close: 1 → 2px -->
      <rect x="133" y="174" width="2" height="18" fill="#C74634" rx="3" opacity="0.55"/>
      <text x="140" y="187" fill="#C74634" font-size="10" font-weight="bold">1</text>
      <!-- X-axis label -->
      <text x="320" y="215" fill="#475569" font-size="10" text-anchor="middle">Number of Investors</text>
    </svg>
    <p class="funnel-label" style="margin-top:0.5rem;">Funnel conversion driven by AI World event (200 attendees) and NVIDIA warm intro program (3 active intros). Deck v6 and data room 87% complete accelerate deep-dive to term sheet conversion.</p>
  </div>

  <p class="footer">Service: {service_name} &nbsp;|&nbsp; Port: {port} &nbsp;|&nbsp; Started: {started_at}</p>
</body>
</html>
""".format(port=PORT, service_name=SERVICE_NAME, started_at=STARTED_AT)


if _FASTAPI_AVAILABLE:
    app = FastAPI(title=SERVICE_NAME, version="1.0.0")

    @app.get("/health")
    def health():
        return JSONResponse({"status": "ok", "port": PORT, "service": SERVICE_NAME, "timestamp": datetime.utcnow().isoformat() + "Z"})

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return HTMLResponse(content=HTML_DASHBOARD)

    @app.get("/investors/pitch_tracker")
    def pitch_tracker():
        return JSONResponse({
            "deck_version": "v6",
            "data_room_pct": 87,
            "ai_world_attendees": 200,
            "nvidia_warm_intros": 3,
            "active_conversations": 22,
            "term_sheets_received": 3,
            "closes": 1,
            "updated_at": datetime.utcnow().isoformat() + "Z",
        })

    @app.get("/investors/pitch_tracker/funnel")
    def pitch_funnel():
        return JSONResponse({
            "funnel": [
                {"stage": "research",         "count": 200},
                {"stage": "intro",             "count": 48},
                {"stage": "first_meeting",     "count": 22},
                {"stage": "deep_dive",         "count": 12},
                {"stage": "partner_meeting",   "count": 6},
                {"stage": "term_sheet",        "count": 3},
                {"stage": "close",             "count": 1},
            ],
            "generated_at": datetime.utcnow().isoformat() + "Z",
        })

else:
    # Fallback: stdlib HTTP server
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
                body = HTML_DASHBOARD.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(body)

        def log_message(self, fmt, *args):  # silence default logging
            pass


if __name__ == "__main__":
    if _FASTAPI_AVAILABLE:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        server = http.server.HTTPServer(("0.0.0.0", PORT), _Handler)
        print(f"[{SERVICE_NAME}] fallback HTTP server on port {PORT}")
        server.serve_forever()
