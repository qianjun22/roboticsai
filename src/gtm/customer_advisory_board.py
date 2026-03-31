"""Customer Advisory Board (CAB) — FastAPI service on port 10165.

Formal customer advisory board with 5 members and quarterly meetings.
Tracks roadmap changes, case studies, expansion deals, and ARR from CAB outputs.
"""

import json
import sys
from datetime import datetime

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

PORT = 10165
SERVICE_NAME = "customer_advisory_board"

CAB_MEMBERS = [
    {"id": 1, "name": "Dr. Sarah Chen", "title": "CTO", "company": "Machina Labs",
     "status": "active", "joined": "2025-Q4"},
    {"id": 2, "name": "Marcus Webb", "title": "VP Engineering", "company": "Verdant Robotics",
     "status": "active", "joined": "2025-Q4"},
    {"id": 3, "name": "Priya Nair", "title": "CEO", "company": "Helix Robotics",
     "status": "active", "joined": "2026-Q1"},
    {"id": 4, "name": "TBD", "title": "Head of Automation", "company": "Prospective Member A",
     "status": "prospective", "joined": None},
    {"id": 5, "name": "TBD", "title": "CTO", "company": "Prospective Member B",
     "status": "prospective", "joined": None},
]

CAB_OUTPUTS = [
    {"metric": "Roadmap Changes", "value": 4, "unit": "items", "color": "#C74634"},
    {"metric": "Case Studies Committed", "value": 2, "unit": "studies", "color": "#38bdf8"},
    {"metric": "Expansion Deals", "value": 1, "unit": "deal", "color": "#34d399"},
    {"metric": "ARR from CAB", "value": 28, "unit": "K USD", "color": "#fbbf24"},
]

MOCK_FEEDBACK = [
    {"member_id": 1, "quarter": "2026-Q1", "theme": "Sim-to-real gap",
     "priority": "high", "roadmap_impact": True},
    {"member_id": 2, "quarter": "2026-Q1", "theme": "Multi-robot coordination APIs",
     "priority": "medium", "roadmap_impact": True},
    {"member_id": 3, "quarter": "2026-Q1", "theme": "Edge inference latency <200ms",
     "priority": "high", "roadmap_impact": True},
]

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Customer Advisory Board — Port {port}</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; padding: 2rem; }}
    h1 {{ color: #C74634; font-size: 1.6rem; margin-bottom: 0.25rem; }}
    .subtitle {{ color: #94a3b8; font-size: 0.9rem; margin-bottom: 2rem; }}
    .badge {{ display: inline-block; background: #1e293b; border: 1px solid #334155; border-radius: 9999px;
              padding: 0.2rem 0.75rem; font-size: 0.78rem; color: #38bdf8; margin-right: 0.5rem; }}
    .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 1rem; margin: 1.5rem 0; }}
    .card {{ background: #1e293b; border: 1px solid #334155; border-radius: 0.75rem; padding: 1.25rem; }}
    .card .val {{ font-size: 1.8rem; font-weight: 700; color: #38bdf8; }}
    .card .lbl {{ font-size: 0.78rem; color: #94a3b8; margin-top: 0.25rem; }}
    .chart-wrap {{ background: #1e293b; border: 1px solid #334155; border-radius: 0.75rem; padding: 1.5rem; margin-top: 1.5rem; }}
    .chart-title {{ color: #cbd5e1; font-size: 0.95rem; margin-bottom: 1rem; }}
    .members {{ margin-top: 1.5rem; background: #1e293b; border: 1px solid #334155; border-radius: 0.75rem; padding: 1.25rem; }}
    .members-title {{ color: #cbd5e1; font-size: 0.95rem; margin-bottom: 1rem; }}
    .member {{ display: flex; align-items: center; padding: 0.5rem 0; border-bottom: 1px solid #1e3a52; }}
    .member:last-child {{ border-bottom: none; }}
    .member-dot {{ width: 10px; height: 10px; border-radius: 50%; margin-right: 0.75rem; flex-shrink: 0; }}
    .member-info {{ flex: 1; font-size: 0.85rem; }}
    .member-info .name {{ color: #e2e8f0; font-weight: 600; }}
    .member-info .role {{ color: #94a3b8; font-size: 0.78rem; }}
    .member-status {{ font-size: 0.72rem; padding: 0.15rem 0.5rem; border-radius: 9999px; }}
    .status-active {{ background: #064e3b; color: #34d399; }}
    .status-prospective {{ background: #1e3a52; color: #38bdf8; }}
    .endpoints {{ margin-top: 1.5rem; }}
    .ep {{ background: #1e293b; border-left: 3px solid #C74634; padding: 0.6rem 1rem; margin-bottom: 0.5rem;
           border-radius: 0 0.5rem 0.5rem 0; font-size: 0.85rem; color: #cbd5e1; }}
    .ep span {{ color: #38bdf8; font-weight: 600; margin-right: 0.5rem; }}
  </style>
</head>
<body>
  <h1>Customer Advisory Board</h1>
  <p class="subtitle">Formal CAB — 5 members, quarterly meetings — Port {port}</p>
  <div>
    <span class="badge">CAB v1.0</span>
    <span class="badge">Port {port}</span>
    <span class="badge">5 Members</span>
    <span class="badge">Quarterly Cadence</span>
    <span class="badge">OCI Robot Cloud</span>
  </div>

  <div class="cards">
    <div class="card"><div class="val">5</div><div class="lbl">Total Members</div></div>
    <div class="card"><div class="val">4</div><div class="lbl">Roadmap Changes</div></div>
    <div class="card"><div class="val">2</div><div class="lbl">Case Studies Committed</div></div>
    <div class="card"><div class="val">$28K</div><div class="lbl">ARR from CAB</div></div>
  </div>

  <div class="chart-wrap">
    <div class="chart-title">CAB Outputs (Q1 2026)</div>
    <svg viewBox="0 0 520 160" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:520px;">
      <!-- Roadmap Changes: 4 (scale: *30) -->
      <rect x="40" y="14" width="120" height="28" rx="4" fill="#C74634"/>
      <text x="170" y="33" fill="#e2e8f0" font-size="13">Roadmap Changes — 4 items</text>
      <!-- Case Studies: 2 (*30=60) -->
      <rect x="40" y="52" width="60" height="28" rx="4" fill="#38bdf8"/>
      <text x="110" y="71" fill="#e2e8f0" font-size="13">Case Studies Committed — 2</text>
      <!-- Expansion Deals: 1 (*30=30) -->
      <rect x="40" y="90" width="30" height="28" rx="4" fill="#34d399"/>
      <text x="80" y="109" fill="#e2e8f0" font-size="13">Expansion Deals — 1</text>
      <!-- ARR $28K (bar width=84 for visual) -->
      <rect x="40" y="128" width="84" height="28" rx="4" fill="#fbbf24"/>
      <text x="134" y="147" fill="#e2e8f0" font-size="13">ARR from CAB — $28K</text>
    </svg>
  </div>

  <div class="members">
    <div class="members-title">Advisory Board Members</div>
    <div class="member">
      <div class="member-dot" style="background:#C74634;"></div>
      <div class="member-info"><div class="name">Dr. Sarah Chen</div><div class="role">CTO — Machina Labs</div></div>
      <span class="member-status status-active">active</span>
    </div>
    <div class="member">
      <div class="member-dot" style="background:#38bdf8;"></div>
      <div class="member-info"><div class="name">Marcus Webb</div><div class="role">VP Engineering — Verdant Robotics</div></div>
      <span class="member-status status-active">active</span>
    </div>
    <div class="member">
      <div class="member-dot" style="background:#a78bfa;"></div>
      <div class="member-info"><div class="name">Priya Nair</div><div class="role">CEO — Helix Robotics</div></div>
      <span class="member-status status-active">active</span>
    </div>
    <div class="member">
      <div class="member-dot" style="background:#475569;"></div>
      <div class="member-info"><div class="name">TBD</div><div class="role">Head of Automation — Prospective Member A</div></div>
      <span class="member-status status-prospective">prospective</span>
    </div>
    <div class="member">
      <div class="member-dot" style="background:#475569;"></div>
      <div class="member-info"><div class="name">TBD</div><div class="role">CTO — Prospective Member B</div></div>
      <span class="member-status status-prospective">prospective</span>
    </div>
  </div>

  <div class="endpoints">
    <div style="color:#94a3b8;font-size:0.8rem;margin-bottom:0.5rem;">ENDPOINTS</div>
    <div class="ep"><span>GET</span>/health — service health</div>
    <div class="ep"><span>GET</span>/cab/members — list all CAB members</div>
    <div class="ep"><span>GET</span>/cab/feedback — Q1 2026 feedback themes</div>
  </div>
</body>
</html>
""".format(port=PORT)

if HAS_FASTAPI:
    app = FastAPI(title=SERVICE_NAME, version="1.0.0")

    @app.get("/health")
    def health():
        return JSONResponse({"status": "ok", "port": PORT, "service": SERVICE_NAME,
                             "timestamp": datetime.utcnow().isoformat() + "Z"})

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return HTMLResponse(content=DASHBOARD_HTML)

    @app.get("/cab/members")
    def get_members():
        return JSONResponse({"members": CAB_MEMBERS, "total": len(CAB_MEMBERS),
                             "active": sum(1 for m in CAB_MEMBERS if m["status"] == "active")})

    @app.get("/cab/feedback")
    def get_feedback():
        return JSONResponse({"feedback": MOCK_FEEDBACK, "quarter": "2026-Q1",
                             "outputs": CAB_OUTPUTS})

else:
    # Fallback: stdlib HTTP server
    from http.server import HTTPServer, BaseHTTPRequestHandler

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):  # silence default logging
            pass

        def do_GET(self):
            if self.path == "/health":
                body = json.dumps({"status": "ok", "port": PORT, "service": SERVICE_NAME}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)
            elif self.path == "/cab/members":
                body = json.dumps({"members": CAB_MEMBERS}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)
            elif self.path == "/cab/feedback":
                body = json.dumps({"feedback": MOCK_FEEDBACK, "outputs": CAB_OUTPUTS}).encode()
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

    def run_fallback():
        server = HTTPServer(("0.0.0.0", PORT), Handler)
        print(f"[{SERVICE_NAME}] fallback http.server running on port {PORT}")
        server.serve_forever()

if __name__ == "__main__":
    if HAS_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        run_fallback()
