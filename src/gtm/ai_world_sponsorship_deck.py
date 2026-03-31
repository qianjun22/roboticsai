"""AI World Sponsorship Deck — FastAPI service (port 10237)

OCI Robot Cloud as headline platinum sponsor for AI World 2026.
Sponsorship tiers: Platinum $80K (keynote + 20x20 booth + joint press),
Gold $40K.  Pipeline impact: $840K.
"""

import json
from datetime import datetime

PORT = 10237
SERVICE_NAME = "ai_world_sponsorship_deck"

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    _FASTAPI_AVAILABLE = True
except ImportError:
    _FASTAPI_AVAILABLE = False

# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>AI World 2026 Sponsorship — OCI Robot Cloud</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; padding: 2rem; }
    h1 { color: #C74634; font-size: 1.75rem; margin-bottom: 0.25rem; }
    .subtitle { color: #38bdf8; font-size: 0.9rem; margin-bottom: 2rem; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1.25rem; margin-bottom: 2rem; }
    .card { background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 1.25rem; }
    .card .label { font-size: 0.75rem; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.4rem; }
    .card .value { font-size: 1.5rem; font-weight: 700; color: #38bdf8; }
    .card .unit { font-size: 0.8rem; color: #64748b; }
    .chart-section { background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 1.5rem; margin-bottom: 2rem; }
    .chart-title { color: #C74634; font-size: 1rem; font-weight: 600; margin-bottom: 1rem; }
    .tiers { background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 1.5rem; margin-bottom: 2rem; }
    .tier-row { display: flex; align-items: center; gap: 1rem; padding: 0.75rem 0; border-bottom: 1px solid #0f172a; }
    .tier-row:last-child { border-bottom: none; }
    .tier-badge { border-radius: 6px; padding: 0.25rem 0.75rem; font-size: 0.75rem; font-weight: 700; min-width: 72px; text-align: center; }
    .platinum { background: #38bdf8; color: #0f172a; }
    .gold { background: #C74634; color: #fff; }
    .tier-price { font-size: 1.1rem; font-weight: 700; color: #e2e8f0; min-width: 70px; }
    .tier-desc { color: #94a3b8; font-size: 0.82rem; }
    .endpoints { background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 1.5rem; }
    .endpoint { display: flex; align-items: center; gap: 0.75rem; padding: 0.5rem 0; border-bottom: 1px solid #0f172a; }
    .endpoint:last-child { border-bottom: none; }
    .method { background: #0369a1; color: #fff; border-radius: 4px; padding: 0.15rem 0.5rem; font-size: 0.7rem; font-weight: 700; min-width: 44px; text-align: center; }
    .path { font-family: monospace; color: #38bdf8; font-size: 0.85rem; }
    .desc { color: #94a3b8; font-size: 0.8rem; margin-left: auto; }
    footer { margin-top: 2rem; color: #475569; font-size: 0.75rem; text-align: center; }
  </style>
</head>
<body>
  <h1>AI World 2026 Sponsorship</h1>
  <p class="subtitle">OCI Robot Cloud &mdash; Headline Platinum Sponsor &mdash; Port {PORT}</p>

  <div class="grid">
    <div class="card"><div class="label">Platinum Investment</div><div class="value">$80K</div><div class="unit">Keynote + 20×20 booth + press</div></div>
    <div class="card"><div class="label">Projected Pipeline</div><div class="value">$840K</div><div class="unit">Total deal impact</div></div>
    <div class="card"><div class="label">Keynote Reach</div><div class="value">2,000</div><div class="unit">Attendees</div></div>
    <div class="card"><div class="label">Media Outlets</div><div class="value">5</div><div class="unit">Press placements</div></div>
  </div>

  <div class="chart-section">
    <div class="chart-title">Sponsorship ROI Breakdown — AI World 2026</div>
    <svg viewBox="0 0 560 220" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:560px;">
      <!-- Axes -->
      <line x1="70" y1="20" x2="70" y2="170" stroke="#475569" stroke-width="1.5"/>
      <line x1="70" y1="170" x2="520" y2="170" stroke="#475569" stroke-width="1.5"/>
      <!-- Y-axis label -->
      <text x="10" y="100" fill="#94a3b8" font-size="10" transform="rotate(-90,10,100)">Count / Units</text>
      <!-- Gridlines -->
      <line x1="70" y1="120" x2="520" y2="120" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,3"/>
      <line x1="70" y1="70" x2="520" y2="70" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,3"/>
      <!-- Bar 1: Keynote Attendees 2000 (normalize to 140px = 2000) -->
      <rect x="100" y="30" width="80" height="140" fill="#38bdf8" rx="4"/>
      <text x="140" y="23" fill="#38bdf8" font-size="12" font-weight="700" text-anchor="middle">2,000</text>
      <text x="140" y="188" fill="#e2e8f0" font-size="10" text-anchor="middle">Keynote</text>
      <text x="140" y="200" fill="#94a3b8" font-size="9" text-anchor="middle">Attendees</text>
      <!-- Bar 2: Booth Badge Scans 500 (500/2000 * 140 = 35px) -->
      <rect x="240" y="135" width="80" height="35" fill="#C74634" rx="4"/>
      <text x="280" y="128" fill="#C74634" font-size="12" font-weight="700" text-anchor="middle">500</text>
      <text x="280" y="188" fill="#e2e8f0" font-size="10" text-anchor="middle">Booth Badge</text>
      <text x="280" y="200" fill="#94a3b8" font-size="9" text-anchor="middle">Scans</text>
      <!-- Bar 3: Press Outlets 5 (5/2000 * 140 ≈ 0.35 → floor to 10px min for visibility) -->
      <rect x="380" y="155" width="80" height="15" fill="#7c3aed" rx="4"/>
      <text x="420" y="148" fill="#a78bfa" font-size="12" font-weight="700" text-anchor="middle">5</text>
      <text x="420" y="188" fill="#e2e8f0" font-size="10" text-anchor="middle">Press</text>
      <text x="420" y="200" fill="#94a3b8" font-size="9" text-anchor="middle">Outlets</text>
      <!-- Pipeline annotation -->
      <text x="520" y="60" fill="#38bdf8" font-size="11" text-anchor="end">Pipeline: $840K</text>
    </svg>
  </div>

  <div class="tiers">
    <div class="chart-title" style="margin-bottom:0.75rem;">Sponsorship Tiers</div>
    <div class="tier-row">
      <span class="tier-badge platinum">PLATINUM</span>
      <span class="tier-price">$80,000</span>
      <span class="tier-desc">Headline keynote slot &middot; 20×20 booth &middot; Joint press release &middot; Logo on all materials &middot; 10 VIP passes</span>
    </div>
    <div class="tier-row">
      <span class="tier-badge gold">GOLD</span>
      <span class="tier-price">$40,000</span>
      <span class="tier-desc">15-min breakout session &middot; 10×10 booth &middot; Logo on select materials &middot; 5 conference passes</span>
    </div>
  </div>

  <div class="endpoints">
    <div class="chart-title" style="margin-bottom:0.75rem;">API Endpoints</div>
    <div class="endpoint"><span class="method">GET</span><span class="path">/events/ai_world/sponsorship</span><span class="desc">Sponsorship proposal details</span></div>
    <div class="endpoint"><span class="method">GET</span><span class="path">/events/ai_world/sponsorship_status</span><span class="desc">Current approval status</span></div>
    <div class="endpoint"><span class="method">GET</span><span class="path">/health</span><span class="desc">Service health check</span></div>
    <div class="endpoint"><span class="method">GET</span><span class="path">/</span><span class="desc">This dashboard</span></div>
  </div>

  <footer>OCI Robot Cloud &mdash; AI World 2026 Sponsorship Deck &mdash; Port {PORT}</footer>
</body>
</html>
""".replace("{PORT}", str(PORT))


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

if _FASTAPI_AVAILABLE:
    app = FastAPI(
        title=SERVICE_NAME,
        description="AI World 2026 sponsorship proposal — OCI Robot Cloud headline platinum sponsor",
        version="1.0.0",
    )

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
        return DASHBOARD_HTML

    @app.get("/events/ai_world/sponsorship")
    def get_sponsorship():
        """Stub: returns AI World 2026 sponsorship proposal details."""
        return JSONResponse({
            "event": "AI World 2026",
            "sponsor": "OCI Robot Cloud",
            "tier": "Platinum",
            "investment_usd": 80000,
            "projected_pipeline_usd": 840000,
            "deliverables": [
                "Headline keynote slot",
                "20x20 booth",
                "Joint press release",
                "Logo on all event materials",
                "10 VIP passes",
            ],
            "reach": {
                "keynote_attendees": 2000,
                "booth_badge_scans": 500,
                "press_outlets": 5,
            },
            "tiers": [
                {"name": "Platinum", "price_usd": 80000, "includes": "keynote + 20x20 booth + joint press"},
                {"name": "Gold", "price_usd": 40000, "includes": "breakout session + 10x10 booth"},
            ],
            "timestamp": datetime.utcnow().isoformat() + "Z",
        })

    @app.get("/events/ai_world/sponsorship_status")
    def get_sponsorship_status():
        """Stub: returns current sponsorship approval status."""
        return JSONResponse({
            "event": "AI World 2026",
            "status": "pending_approval",
            "submitted_date": "2026-03-28",
            "decision_date": "2026-04-15",
            "approver": "VP Marketing",
            "pipeline_confirmed_usd": 0,
            "pipeline_projected_usd": 840000,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        })


# ---------------------------------------------------------------------------
# Fallback: stdlib HTTPServer
# ---------------------------------------------------------------------------

else:
    import http.server
    import socketserver

    class _Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass

        def do_GET(self):
            if self.path == "/health":
                body = json.dumps({"status": "ok", "port": PORT, "service": SERVICE_NAME}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)
            elif self.path == "/events/ai_world/sponsorship":
                body = json.dumps({"event": "AI World 2026", "tier": "Platinum", "investment_usd": 80000, "projected_pipeline_usd": 840000}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)
            elif self.path == "/events/ai_world/sponsorship_status":
                body = json.dumps({"status": "pending_approval", "pipeline_projected_usd": 840000}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)
            else:
                body = DASHBOARD_HTML.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(body)

    def _serve():
        with socketserver.TCPServer(("", PORT), _Handler) as httpd:
            print(f"[{SERVICE_NAME}] stdlib fallback listening on port {PORT}")
            httpd.serve_forever()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if _FASTAPI_AVAILABLE:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        _serve()
