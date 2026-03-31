"""Enterprise Expansion Playbook Service — port 10169

Manages enterprise account expansion playbook with four expansion motions:
robot expansion, use case expansion, volume expansion, and tier upgrade.
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

PORT = 10169
SERVICE_NAME = "enterprise_expansion_playbook"

EXPANSION_PLAYS = [
    {
        "id": "tier_upgrade",
        "name": "Tier Upgrade",
        "avg_arr_usd": 67000,
        "triggers": [">80% GPU utilization for 30d", "inference queue depth >50", "SLA misses"],
        "close_timeline_days": 21,
        "description": "Upgrade customer from Standard to Enterprise tier; unlocks priority inference, SLA guarantees, and dedicated support.",
    },
    {
        "id": "robot_expansion",
        "name": "Robot Expansion",
        "avg_arr_usd": 41000,
        "triggers": ["pilot fleet >90% success rate", "customer requesting >3 new robots", "new facility opening"],
        "close_timeline_days": 30,
        "description": "Expand licensed robot count from pilot fleet to full production deployment.",
    },
    {
        "id": "use_case_expansion",
        "name": "Use Case Expansion",
        "avg_arr_usd": 28000,
        "triggers": ["second task type requested", "cross-team interest", "QBR with positive NPS"],
        "close_timeline_days": 45,
        "description": "Land a second robot task type (e.g., add bin-picking to existing pick-and-place customer).",
    },
    {
        "id": "volume_expansion",
        "name": "Volume Expansion",
        "avg_arr_usd": 15000,
        "triggers": ["data collection >500 demos/mo", "fine-tune frequency >2x/mo", "storage near quota"],
        "close_timeline_days": 14,
        "description": "Increase fine-tuning compute, data storage, and inference call quota for high-throughput accounts.",
    },
]

HTML_DASHBOARD = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Enterprise Expansion Playbook — OCI Robot Cloud</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; padding: 2rem; }
    h1 { color: #C74634; font-size: 1.8rem; margin-bottom: 0.25rem; }
    .subtitle { color: #38bdf8; font-size: 0.95rem; margin-bottom: 2rem; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-bottom: 2rem; }
    .card { background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 1.25rem; }
    .card h3 { color: #38bdf8; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.5rem; }
    .card .val { font-size: 1.6rem; font-weight: 700; color: #f1f5f9; }
    .card .unit { font-size: 0.75rem; color: #94a3b8; margin-top: 0.2rem; }
    .chart-section { background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 1.5rem; margin-bottom: 2rem; }
    .chart-section h2 { color: #f1f5f9; font-size: 1.1rem; margin-bottom: 1.25rem; }
    .plays { display: grid; gap: 1rem; }
    .play { background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 1.25rem; }
    .play h3 { color: #38bdf8; font-size: 1rem; margin-bottom: 0.5rem; }
    .play .arr { color: #C74634; font-weight: 700; font-size: 1.1rem; }
    .play p { color: #94a3b8; font-size: 0.875rem; margin: 0.4rem 0; }
    .play .triggers { margin-top: 0.5rem; }
    .play .triggers span { display: inline-block; background: #0f172a; border: 1px solid #334155; border-radius: 4px; padding: 0.2rem 0.5rem; font-size: 0.75rem; color: #cbd5e1; margin: 0.15rem 0.15rem 0 0; }
    footer { margin-top: 2rem; color: #475569; font-size: 0.8rem; text-align: center; }
  </style>
</head>
<body>
  <h1>Enterprise Expansion Playbook</h1>
  <p class="subtitle">OCI Robot Cloud · Port 10169 · 4 expansion motions · Avg close 21–45 days</p>

  <div class="grid">
    <div class="card">
      <h3>Expansion Plays</h3>
      <div class="val">4</div>
      <div class="unit">motions</div>
    </div>
    <div class="card">
      <h3>Top Play ARR</h3>
      <div class="val">$67K</div>
      <div class="unit">tier upgrade</div>
    </div>
    <div class="card">
      <h3>Fastest Close</h3>
      <div class="val">14d</div>
      <div class="unit">volume expansion</div>
    </div>
    <div class="card">
      <h3>Total Pipeline</h3>
      <div class="val">$151K</div>
      <div class="unit">avg ARR per account</div>
    </div>
  </div>

  <div class="chart-section">
    <h2>Expansion Plays by Average ARR (USD)</h2>
    <svg viewBox="0 0 560 220" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:560px;display:block;">
      <!-- Y-axis labels -->
      <text x="40" y="20" fill="#94a3b8" font-size="10" text-anchor="end">$70K</text>
      <text x="40" y="58" fill="#94a3b8" font-size="10" text-anchor="end">$52K</text>
      <text x="40" y="98" fill="#94a3b8" font-size="10" text-anchor="end">$35K</text>
      <text x="40" y="138" fill="#94a3b8" font-size="10" text-anchor="end">$17K</text>
      <!-- gridlines -->
      <line x1="45" y1="18" x2="550" y2="18" stroke="#334155" stroke-width="0.5"/>
      <line x1="45" y1="58" x2="550" y2="58" stroke="#334155" stroke-width="0.5"/>
      <line x1="45" y1="98" x2="550" y2="98" stroke="#334155" stroke-width="0.5"/>
      <line x1="45" y1="138" x2="550" y2="138" stroke="#334155" stroke-width="0.5"/>
      <line x1="45" y1="158" x2="550" y2="158" stroke="#334155" stroke-width="0.5"/>

      <!-- Bar 1: Tier Upgrade $67K -->
      <rect x="60" y="21" width="80" height="137" fill="#C74634" rx="3"/>
      <text x="100" y="16" fill="#f1f5f9" font-size="11" text-anchor="middle">$67K</text>
      <text x="100" y="175" fill="#94a3b8" font-size="9" text-anchor="middle">Tier</text>
      <text x="100" y="187" fill="#94a3b8" font-size="9" text-anchor="middle">Upgrade</text>

      <!-- Bar 2: Robot Expansion $41K -->
      <rect x="185" y="74" width="80" height="84" fill="#38bdf8" rx="3"/>
      <text x="225" y="69" fill="#f1f5f9" font-size="11" text-anchor="middle">$41K</text>
      <text x="225" y="175" fill="#94a3b8" font-size="9" text-anchor="middle">Robot</text>
      <text x="225" y="187" fill="#94a3b8" font-size="9" text-anchor="middle">Expansion</text>

      <!-- Bar 3: Use Case $28K -->
      <rect x="310" y="99" width="80" height="59" fill="#C74634" rx="3"/>
      <text x="350" y="94" fill="#f1f5f9" font-size="11" text-anchor="middle">$28K</text>
      <text x="350" y="175" fill="#94a3b8" font-size="9" text-anchor="middle">Use Case</text>
      <text x="350" y="187" fill="#94a3b8" font-size="9" text-anchor="middle">Expansion</text>

      <!-- Bar 4: Volume $15K -->
      <rect x="435" y="124" width="80" height="34" fill="#38bdf8" rx="3"/>
      <text x="475" y="119" fill="#f1f5f9" font-size="11" text-anchor="middle">$15K</text>
      <text x="475" y="175" fill="#94a3b8" font-size="9" text-anchor="middle">Volume</text>
      <text x="475" y="187" fill="#94a3b8" font-size="9" text-anchor="middle">Expansion</text>
    </svg>
  </div>

  <div class="plays">
    <div class="play">
      <h3>Tier Upgrade</h3>
      <div class="arr">$67K avg ARR &nbsp;·&nbsp; Close in ~21 days</div>
      <p>Upgrade customer from Standard to Enterprise tier; unlocks priority inference, SLA guarantees, and dedicated support.</p>
      <div class="triggers">
        <span>&gt;80% GPU utilization for 30d</span>
        <span>inference queue depth &gt;50</span>
        <span>SLA misses</span>
      </div>
    </div>
    <div class="play">
      <h3>Robot Expansion</h3>
      <div class="arr">$41K avg ARR &nbsp;·&nbsp; Close in ~30 days</div>
      <p>Expand licensed robot count from pilot fleet to full production deployment.</p>
      <div class="triggers">
        <span>pilot fleet &gt;90% success rate</span>
        <span>customer requesting &gt;3 new robots</span>
        <span>new facility opening</span>
      </div>
    </div>
    <div class="play">
      <h3>Use Case Expansion</h3>
      <div class="arr">$28K avg ARR &nbsp;·&nbsp; Close in ~45 days</div>
      <p>Land a second robot task type (e.g., add bin-picking to existing pick-and-place customer).</p>
      <div class="triggers">
        <span>second task type requested</span>
        <span>cross-team interest</span>
        <span>QBR with positive NPS</span>
      </div>
    </div>
    <div class="play">
      <h3>Volume Expansion</h3>
      <div class="arr">$15K avg ARR &nbsp;·&nbsp; Close in ~14 days</div>
      <p>Increase fine-tuning compute, data storage, and inference call quota for high-throughput accounts.</p>
      <div class="triggers">
        <span>data collection &gt;500 demos/mo</span>
        <span>fine-tune frequency &gt;2x/mo</span>
        <span>storage near quota</span>
      </div>
    </div>
  </div>

  <footer>OCI Robot Cloud · Enterprise Expansion Playbook · Port 10169</footer>
</body>
</html>
"""

if _FASTAPI_AVAILABLE:
    app = FastAPI(title=SERVICE_NAME, version="1.0.0")

    @app.get("/health")
    def health():
        return JSONResponse({"status": "ok", "port": PORT, "service": SERVICE_NAME, "ts": datetime.utcnow().isoformat()})

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return HTML_DASHBOARD

    @app.get("/expansion/playbook")
    def get_playbook():
        """Return all expansion plays with triggers and timelines (stub)."""
        return {
            "status": "ok",
            "plays": EXPANSION_PLAYS,
            "total_plays": len(EXPANSION_PLAYS),
            "total_potential_arr_usd": sum(p["avg_arr_usd"] for p in EXPANSION_PLAYS),
        }

    @app.post("/expansion/launch_play")
    def launch_play(payload: dict = None):
        """Launch an expansion play for a given account (stub)."""
        play_id = (payload or {}).get("play_id", "tier_upgrade")
        account_id = (payload or {}).get("account_id", "acct_demo_001")
        play = next((p for p in EXPANSION_PLAYS if p["id"] == play_id), EXPANSION_PLAYS[0])
        return {
            "status": "launched",
            "play_id": play_id,
            "account_id": account_id,
            "play_name": play["name"],
            "expected_arr_usd": play["avg_arr_usd"],
            "close_timeline_days": play["close_timeline_days"],
            "next_steps": [
                "Schedule discovery call with account champion",
                "Pull usage metrics from billing service (port 8079)",
                "Prepare ROI analysis with robotics_roi_calc (port 8069)",
                "Submit to Salesforce opportunity pipeline",
            ],
            "launched_at": datetime.utcnow().isoformat(),
        }

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

        def log_message(self, fmt, *args):  # silence default logging
            pass


if __name__ == "__main__":
    if _FASTAPI_AVAILABLE:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        with socketserver.TCPServer(("", PORT), _Handler) as httpd:
            print(f"{SERVICE_NAME} fallback server running on port {PORT}")
            httpd.serve_forever()
