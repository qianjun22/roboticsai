"""Investor Pipeline CRM v2 — tier-based outreach for 24→40 targets.

Port 10175 | cycle-529B
Tiers: tier-1 lead (5), tier-2 strategic (15), tier-3 financial (20).
Pipeline stages: research → outreach → first meeting → deep dive → term sheet.
"""

import json
import os
import sys
from datetime import datetime

PORT = 10175
SERVICE_NAME = "investor_pipeline_crm_v2"

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    _FASTAPI = True
except ImportError:
    _FASTAPI = False

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

if _FASTAPI:
    app = FastAPI(title=SERVICE_NAME, version="2.0.0")

    @app.get("/health")
    async def health():
        return JSONResponse({"status": "ok", "port": PORT, "service": SERVICE_NAME})

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return HTMLResponse(content=_html_dashboard())

    @app.get("/investors/pipeline/v2")
    async def get_pipeline():
        """Return full investor pipeline v2 with tier breakdown."""
        return JSONResponse({
            "version": "v2",
            "total_targets": 40,
            "previous_targets": 24,
            "tiers": [
                {"tier": 1, "label": "Lead", "count": 5,
                 "description": "Top-priority, actively leading robotics / AI infra funds"},
                {"tier": 2, "label": "Strategic", "count": 15,
                 "description": "Strategic corporates + CVCs with robotics portfolio"},
                {"tier": 3, "label": "Financial", "count": 20,
                 "description": "Growth / late-stage financial VCs"},
            ],
            "pipeline_stages": [
                {"stage": "research", "count": 20},
                {"stage": "outreach", "count": 12},
                {"stage": "first_meeting", "count": 6},
                {"stage": "deep_dive", "count": 3},
                {"stage": "term_sheet", "count": 0},
            ],
            "generated_at": datetime.utcnow().isoformat() + "Z",
        })

    @app.get("/investors/pipeline/v2/summary")
    async def get_summary():
        """Return KPI summary for the investor pipeline v2."""
        return JSONResponse({
            "version": "v2",
            "total_targets": 40,
            "active_conversations": 9,
            "term_sheets": 0,
            "conversion_rate_outreach_to_meeting": "50%",
            "avg_days_to_first_meeting": 14,
            "next_actions": [
                "Send deck to 3 tier-1 targets by EOM",
                "Schedule deep-dive with 2 strategic CVCs",
                "Expand research list to fill tier-3 slots",
            ],
            "generated_at": datetime.utcnow().isoformat() + "Z",
        })

# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def _html_dashboard() -> str:
    return """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Investor Pipeline CRM v2</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; padding: 32px; }
  h1 { color: #C74634; font-size: 1.8rem; margin-bottom: 4px; }
  .subtitle { color: #94a3b8; font-size: 0.95rem; margin-bottom: 32px; }
  .grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 24px; }
  .card { background: #1e293b; border-radius: 12px; padding: 24px; }
  .card h2 { color: #38bdf8; font-size: 1rem; text-transform: uppercase;
             letter-spacing: 0.08em; margin-bottom: 16px; }
  .stat { font-size: 2.4rem; font-weight: 700; color: #f1f5f9; }
  .stat-label { color: #64748b; font-size: 0.85rem; margin-top: 4px; }
  .badge { display: inline-block; background: #C74634; color: #fff;
           padding: 2px 10px; border-radius: 20px; font-size: 0.8rem;
           font-weight: 600; margin-left: 8px; vertical-align: middle; }
  .chart-wrap { grid-column: span 3; }
  .endpoint { font-family: monospace; font-size: 0.85rem; color: #38bdf8;
              background: #0f172a; border-radius: 6px; padding: 10px 14px;
              margin-bottom: 8px; }
  .endpoint span { color: #94a3b8; }
  .tier-list { list-style: none; }
  .tier-list li { padding: 6px 0; border-bottom: 1px solid #0f172a; font-size: 0.9rem; }
  .tier-list li:last-child { border-bottom: none; }
  .t1 { color: #C74634; font-weight: 700; }
  .t2 { color: #38bdf8; font-weight: 700; }
  .t3 { color: #94a3b8; font-weight: 700; }
</style>
</head>
<body>
<h1>Investor Pipeline CRM v2 <span class="badge">port 10175</span></h1>
<p class="subtitle">Tier-based outreach — 24 → 40 targets; tier-1 lead, tier-2 strategic, tier-3 financial</p>
<div class="grid">
  <div class="card">
    <h2>Total Targets</h2>
    <div class="stat">40</div>
    <div class="stat-label">Up from 24 in v1 (+67%)</div>
  </div>
  <div class="card">
    <h2>Active Conversations</h2>
    <div class="stat">9</div>
    <div class="stat-label">Outreach + meetings in progress</div>
  </div>
  <div class="card">
    <h2>Tiers</h2>
    <ul class="tier-list">
      <li><span class="t1">Tier 1 Lead</span> — 5 investors</li>
      <li><span class="t2">Tier 2 Strategic</span> — 15 investors</li>
      <li><span class="t3">Tier 3 Financial</span> — 20 investors</li>
    </ul>
  </div>
  <div class="card chart-wrap">
    <h2>Pipeline Stages</h2>
    <svg viewBox="0 0 620 200" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:620px;display:block;margin-top:8px">
      <!-- axes -->
      <line x1="80" y1="10" x2="80" y2="160" stroke="#334155" stroke-width="1"/>
      <line x1="80" y1="160" x2="600" y2="160" stroke="#334155" stroke-width="1"/>
      <!-- y labels -->
      <text x="72" y="165" fill="#64748b" font-size="11" text-anchor="end">0</text>
      <text x="72" y="112" fill="#64748b" font-size="11" text-anchor="end">10</text>
      <text x="72" y="60" fill="#64748b" font-size="11" text-anchor="end">20</text>
      <!-- gridlines -->
      <line x1="80" y1="111" x2="600" y2="111" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,3"/>
      <line x1="80" y1="60" x2="600" y2="60" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,3"/>
      <!-- bars: max=20 → scale 150/20=7.5px per unit -->
      <!-- research 20 → h=150, y=10 -->
      <rect x="95" y="10" width="70" height="150" rx="4" fill="#C74634" opacity="0.9"/>
      <text x="130" y="6" fill="#e2e8f0" font-size="12" font-weight="700" text-anchor="middle">20</text>
      <text x="130" y="176" fill="#94a3b8" font-size="11" text-anchor="middle">Research</text>
      <!-- outreach 12 → h=90, y=70 -->
      <rect x="195" y="70" width="70" height="90" rx="4" fill="#38bdf8" opacity="0.85"/>
      <text x="230" y="66" fill="#e2e8f0" font-size="12" font-weight="700" text-anchor="middle">12</text>
      <text x="230" y="176" fill="#94a3b8" font-size="11" text-anchor="middle">Outreach</text>
      <!-- first meeting 6 → h=45, y=115 -->
      <rect x="295" y="115" width="70" height="45" rx="4" fill="#7c3aed" opacity="0.85"/>
      <text x="330" y="111" fill="#e2e8f0" font-size="12" font-weight="700" text-anchor="middle">6</text>
      <text x="330" y="176" fill="#94a3b8" font-size="11" text-anchor="middle">1st Meeting</text>
      <!-- deep dive 3 → h=22.5≈23, y=137 -->
      <rect x="395" y="137" width="70" height="23" rx="4" fill="#0ea5e9" opacity="0.85"/>
      <text x="430" y="133" fill="#e2e8f0" font-size="12" font-weight="700" text-anchor="middle">3</text>
      <text x="430" y="176" fill="#94a3b8" font-size="11" text-anchor="middle">Deep Dive</text>
      <!-- term sheet 0 → h=2 (floor), y=158 -->
      <rect x="495" y="157" width="70" height="3" rx="2" fill="#64748b" opacity="0.7"/>
      <text x="530" y="153" fill="#64748b" font-size="12" font-weight="700" text-anchor="middle">0</text>
      <text x="530" y="176" fill="#94a3b8" font-size="11" text-anchor="middle">Term Sheet</text>
    </svg>
  </div>
  <div class="card" style="grid-column:span 3">
    <h2>Endpoints</h2>
    <div class="endpoint">GET /health <span>— liveness probe</span></div>
    <div class="endpoint">GET /investors/pipeline/v2 <span>— full pipeline with tier breakdown</span></div>
    <div class="endpoint">GET /investors/pipeline/v2/summary <span>— KPI summary + next actions</span></div>
  </div>
</div>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# Fallback HTTP server
# ---------------------------------------------------------------------------

if not _FASTAPI:
    import http.server
    import socketserver

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/health":
                body = json.dumps({"status": "ok", "port": PORT,
                                   "service": SERVICE_NAME}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)
            else:
                body = _html_dashboard().encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(body)

        def log_message(self, fmt, *args):  # suppress default logging
            pass

    def _run_fallback():
        with socketserver.TCPServer(("", PORT), _Handler) as httpd:
            print(f"{SERVICE_NAME} fallback server on port {PORT}")
            httpd.serve_forever()

# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if _FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        _run_fallback()
