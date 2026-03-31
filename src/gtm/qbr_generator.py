"""QBR Generator — auto-generate customer quarterly business review decks.

Port: 10219
Cycle: 540B
"""

import json
import sys
from datetime import datetime

PORT = 10219
SERVICE_NAME = "qbr_generator"

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    from pydantic import BaseModel
    import uvicorn
    _FASTAPI_AVAILABLE = True
except ImportError:
    _FASTAPI_AVAILABLE = False

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>QBR Generator</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; padding: 2rem; }
    h1 { color: #C74634; font-size: 1.8rem; margin-bottom: 0.4rem; }
    .subtitle { color: #38bdf8; font-size: 0.95rem; margin-bottom: 2rem; }
    .card { background: #1e293b; border-radius: 10px; padding: 1.5rem; margin-bottom: 1.5rem; }
    .card h2 { color: #38bdf8; margin-bottom: 1rem; font-size: 1.1rem; }
    .stat-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 1rem; }
    .stat { background: #0f172a; border-radius: 8px; padding: 1rem; text-align: center; border: 1px solid #334155; }
    .stat .val { font-size: 1.8rem; font-weight: 700; color: #C74634; }
    .stat .lbl { font-size: 0.8rem; color: #94a3b8; margin-top: 0.3rem; }
    .badge { display: inline-block; background: #0f172a; border: 1px solid #38bdf8; color: #38bdf8;
             border-radius: 4px; padding: 0.2rem 0.6rem; font-size: 0.8rem; margin: 0.2rem; }
    .slide-list { list-style: none; }
    .slide-list li { padding: 0.5rem 0; border-bottom: 1px solid #1e293b; font-size: 0.9rem; }
    .slide-list li:last-child { border-bottom: none; }
    .slide-num { color: #C74634; font-weight: 700; margin-right: 0.6rem; }
    .endpoints { font-size: 0.85rem; color: #94a3b8; }
    .endpoints span { color: #38bdf8; }
    svg text { font-family: 'Segoe UI', sans-serif; }
  </style>
</head>
<body>
  <h1>QBR Generator</h1>
  <p class="subtitle">Auto-generate customer quarterly business review decks from live APIs &nbsp;&bull;&nbsp; Port {PORT}</p>

  <div class="card">
    <h2>Expansion Conversion: With vs Without Ask (% converting to upsell)</h2>
    <svg width="480" height="200" viewBox="0 0 480 200" xmlns="http://www.w3.org/2000/svg">
      <!-- Y-axis label -->
      <text x="18" y="14" font-size="11" fill="#94a3b8">Conv %</text>
      <!-- Grid lines -->
      <line x1="60" y1="20" x2="460" y2="20" stroke="#334155" stroke-width="1" stroke-dasharray="4,3"/>
      <line x1="60" y1="57.5" x2="460" y2="57.5" stroke="#334155" stroke-width="1" stroke-dasharray="4,3"/>
      <line x1="60" y1="95" x2="460" y2="95" stroke="#334155" stroke-width="1" stroke-dasharray="4,3"/>
      <line x1="60" y1="132.5" x2="460" y2="132.5" stroke="#334155" stroke-width="1" stroke-dasharray="4,3"/>
      <!-- Y-axis ticks -->
      <text x="50" y="24" font-size="10" fill="#64748b" text-anchor="end">40</text>
      <text x="50" y="61" font-size="10" fill="#64748b" text-anchor="end">30</text>
      <text x="50" y="99" font-size="10" fill="#64748b" text-anchor="end">20</text>
      <text x="50" y="136" font-size="10" fill="#64748b" text-anchor="end">10</text>
      <!-- Bar: With Expansion Ask 31% -->
      <rect x="100" y="52.5" width="120" height="127.5" rx="4" fill="#C74634"/>
      <text x="160" y="48" font-size="13" fill="#f1f5f9" text-anchor="middle" font-weight="bold">31%</text>
      <text x="160" y="185" font-size="11" fill="#94a3b8" text-anchor="middle">With Expansion Ask</text>
      <!-- Bar: Without Ask 8% -->
      <rect x="260" y="147" width="120" height="33" rx="4" fill="#38bdf8"/>
      <text x="320" y="143" font-size="13" fill="#f1f5f9" text-anchor="middle" font-weight="bold">8%</text>
      <text x="320" y="185" font-size="11" fill="#94a3b8" text-anchor="middle">Without Ask</text>
      <!-- X-axis -->
      <line x1="60" y1="180" x2="460" y2="180" stroke="#475569" stroke-width="1"/>
    </svg>
  </div>

  <div class="card">
    <h2>QBR Deck — 5-Slide Template</h2>
    <ul class="slide-list">
      <li><span class="slide-num">1</span>Executive Summary &mdash; key wins, risks, net health score</li>
      <li><span class="slide-num">2</span>SR Progress &mdash; success rate trend, benchmark vs peers</li>
      <li><span class="slide-num">3</span>Usage Analytics &mdash; inference calls, latency p50/p95, data flywheel growth</li>
      <li><span class="slide-num">4</span>Roadmap &mdash; upcoming features, scheduled fine-tune cycles</li>
      <li><span class="slide-num">5</span>Expansion Ask &mdash; additional robots, new task domains, Premier support</li>
    </ul>
  </div>

  <div class="card">
    <h2>Key Metrics</h2>
    <div class="stat-grid">
      <div class="stat"><div class="val">31%</div><div class="lbl">Conversion w/ Ask</div></div>
      <div class="stat"><div class="val">8%</div><div class="lbl">Conversion w/o Ask</div></div>
      <div class="stat"><div class="val">3.9&times;</div><div class="lbl">Ask Lift</div></div>
      <div class="stat"><div class="val">5</div><div class="lbl">Slides per Deck</div></div>
      <div class="stat"><div class="val">&lt;2 min</div><div class="lbl">Auto-gen Time</div></div>
      <div class="stat"><div class="val">Quarterly</div><div class="lbl">Cadence</div></div>
    </div>
  </div>

  <div class="card">
    <h2>Data Sources Auto-Pulled</h2>
    <span class="badge">Inference API (port 8001)</span>
    <span class="badge">Eval Service (port 8021)</span>
    <span class="badge">Billing API (port 8022)</span>
    <span class="badge">Data Flywheel (port 8023)</span>
    <span class="badge">CRM (port 8076)</span>
  </div>

  <div class="card endpoints">
    <h2>Endpoints</h2>
    <p><span>GET</span> /health &mdash; service health</p>
    <p><span>GET</span> / &mdash; this dashboard</p>
    <p><span>POST</span> /customers/qbr/generate &mdash; generate QBR deck for a customer</p>
    <p><span>GET</span> /customers/qbr/history &mdash; list previously generated QBR decks</p>
  </div>
</body>
</html>
""".replace("{PORT}", str(PORT))


if _FASTAPI_AVAILABLE:
    app = FastAPI(title=SERVICE_NAME, version="1.0.0")

    class QBRRequest(BaseModel):
        customer_id: str
        quarter: str = "Q1-2026"
        include_expansion_ask: bool = True

    @app.get("/health")
    async def health():
        return JSONResponse({"status": "ok", "port": PORT, "service": SERVICE_NAME,
                             "timestamp": datetime.utcnow().isoformat() + "Z"})

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return HTMLResponse(content=DASHBOARD_HTML)

    @app.post("/customers/qbr/generate")
    async def generate_qbr(req: QBRRequest):
        return JSONResponse({
            "job_id": f"qbr-{req.customer_id}-{req.quarter}-001",
            "customer_id": req.customer_id,
            "quarter": req.quarter,
            "include_expansion_ask": req.include_expansion_ask,
            "slides": [
                {"slide": 1, "title": "Executive Summary"},
                {"slide": 2, "title": "SR Progress"},
                {"slide": 3, "title": "Usage Analytics"},
                {"slide": 4, "title": "Roadmap"},
                {"slide": 5, "title": "Expansion Ask"},
            ],
            "estimated_conversion_rate": 0.31 if req.include_expansion_ask else 0.08,
            "status": "queued",
            "created_at": datetime.utcnow().isoformat() + "Z"
        })

    @app.get("/customers/qbr/history")
    async def qbr_history(customer_id: str = None, limit: int = 20):
        mock_history = [
            {"job_id": "qbr-acme-Q4-2025-001", "customer_id": "acme", "quarter": "Q4-2025",
             "status": "delivered", "conversion": True, "created_at": "2025-12-15T10:00:00Z"},
            {"job_id": "qbr-globex-Q4-2025-001", "customer_id": "globex", "quarter": "Q4-2025",
             "status": "delivered", "conversion": False, "created_at": "2025-12-16T14:30:00Z"},
        ]
        if customer_id:
            mock_history = [r for r in mock_history if r["customer_id"] == customer_id]
        return JSONResponse({"history": mock_history[:limit], "total": len(mock_history)})

else:
    # Fallback http.server
    from http.server import HTTPServer, BaseHTTPRequestHandler

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/health":
                body = json.dumps({"status": "ok", "port": PORT, "service": SERVICE_NAME}).encode()
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

        def log_message(self, fmt, *args):  # suppress default logging
            pass

    def _run_fallback():
        server = HTTPServer(("0.0.0.0", PORT), _Handler)
        print(f"[{SERVICE_NAME}] Fallback http.server running on port {PORT}")
        server.serve_forever()


if __name__ == "__main__":
    if _FASTAPI_AVAILABLE:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        _run_fallback()
