"""Board Deck Q3 Generator — Series A readiness + AI World preview + NVIDIA progress (port 10171).

Narrative arc: Q1 foundation → Q2 traction → Q3 launch → Q4 raise.
"""

import json
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = 10171
SERVICE_NAME = "board_deck_q3_generator"

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    from fastapi import Body
    import uvicorn
    _FASTAPI = True
except ImportError:
    _FASTAPI = False

# ---------------------------------------------------------------------------
# Dashboard HTML
# ---------------------------------------------------------------------------

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Board Deck Q3 Generator</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: #0f172a;
      color: #e2e8f0;
      font-family: 'Segoe UI', system-ui, sans-serif;
      padding: 2rem;
    }
    h1 { color: #38bdf8; font-size: 1.8rem; margin-bottom: 0.25rem; }
    .subtitle { color: #94a3b8; margin-bottom: 2rem; font-size: 0.95rem; }
    .badge {
      display: inline-block;
      background: #C74634;
      color: #fff;
      border-radius: 4px;
      padding: 0.2rem 0.7rem;
      font-size: 0.8rem;
      font-weight: 600;
      margin-left: 0.75rem;
      vertical-align: middle;
    }
    .card {
      background: #1e293b;
      border: 1px solid #334155;
      border-radius: 10px;
      padding: 1.5rem;
      margin-bottom: 1.5rem;
    }
    .card h2 { color: #38bdf8; font-size: 1.1rem; margin-bottom: 1rem; }
    .metric-row { display: flex; gap: 1.5rem; flex-wrap: wrap; margin-bottom: 1rem; }
    .metric {
      background: #0f172a;
      border: 1px solid #334155;
      border-radius: 8px;
      padding: 0.9rem 1.2rem;
      min-width: 130px;
    }
    .metric .label { color: #94a3b8; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; }
    .metric .value { color: #38bdf8; font-size: 1.5rem; font-weight: 700; margin-top: 0.2rem; }
    .arc-row { display: flex; gap: 0; margin-top: 0.5rem; }
    .arc-step {
      flex: 1;
      text-align: center;
      padding: 0.6rem 0.4rem;
      font-size: 0.8rem;
      border-right: 1px solid #334155;
    }
    .arc-step:last-child { border-right: none; }
    .arc-step .qlabel { color: #38bdf8; font-weight: 700; font-size: 0.9rem; }
    .arc-step .qdesc  { color: #94a3b8; font-size: 0.75rem; margin-top: 0.2rem; }
    .arc-step.active  { background: #1e3a5f; border-radius: 6px; }
    .endpoint { color: #a5f3fc; font-family: monospace; font-size: 0.85rem; margin: 0.3rem 0; }
    svg text { font-family: 'Segoe UI', system-ui, sans-serif; }
  </style>
</head>
<body>
  <h1>Board Deck Q3 Generator <span class="badge">PORT 10171</span></h1>
  <p class="subtitle">Series A readiness &bull; AI World preview &bull; NVIDIA partnership progress</p>

  <div class="card">
    <h2>Q3 2026 Targets</h2>
    <svg width="540" height="210" viewBox="0 0 540 210">
      <!-- axes -->
      <line x1="60" y1="10" x2="60" y2="165" stroke="#334155" stroke-width="1.5"/>
      <line x1="60" y1="165" x2="520" y2="165" stroke="#334155" stroke-width="1.5"/>

      <!-- y-axis (0-100 normalized) labels -->
      <text x="50" y="14"  fill="#94a3b8" font-size="11" text-anchor="end">100</text>
      <text x="50" y="57"  fill="#94a3b8" font-size="11" text-anchor="end">75</text>
      <text x="50" y="100" fill="#94a3b8" font-size="11" text-anchor="end">50</text>
      <text x="50" y="143" fill="#94a3b8" font-size="11" text-anchor="end">25</text>
      <text x="50" y="165" fill="#94a3b8" font-size="11" text-anchor="end">0</text>

      <!-- gridlines -->
      <line x1="60" y1="14"  x2="520" y2="14"  stroke="#1e293b" stroke-width="1"/>
      <line x1="60" y1="57"  x2="520" y2="57"  stroke="#1e293b" stroke-width="1"/>
      <line x1="60" y1="100" x2="520" y2="100" stroke="#1e293b" stroke-width="1"/>
      <line x1="60" y1="143" x2="520" y2="143" stroke="#1e293b" stroke-width="1"/>

      <!-- ARR $430K → normalized ~86/100 → height=129 -->
      <rect x="80"  y="36"  width="80" height="129" fill="#C74634" rx="4"/>
      <text x="120" y="30"  fill="#e2e8f0" font-size="11" text-anchor="middle">$430K</text>
      <text x="120" y="181" fill="#94a3b8" font-size="11" text-anchor="middle">ARR</text>

      <!-- NRR 130% → normalized 100 → height=151 -->
      <rect x="200" y="14"  width="80" height="151" fill="#38bdf8" rx="4"/>
      <text x="240" y="8"   fill="#e2e8f0" font-size="11" text-anchor="middle">130%</text>
      <text x="240" y="181" fill="#94a3b8" font-size="11" text-anchor="middle">NRR</text>

      <!-- SR 95% → normalized 95 → height=143 -->
      <rect x="320" y="22"  width="80" height="143" fill="#38bdf8" rx="4"/>
      <text x="360" y="16"  fill="#e2e8f0" font-size="11" text-anchor="middle">95%</text>
      <text x="360" y="181" fill="#94a3b8" font-size="11" text-anchor="middle">SR</text>

      <!-- Customers 6 → normalized 60 → height=90 -->
      <rect x="440" y="75"  width="80" height="90"  fill="#C74634" rx="4"/>
      <text x="480" y="69"  fill="#e2e8f0" font-size="11" text-anchor="middle">6</text>
      <text x="480" y="181" fill="#94a3b8" font-size="11" text-anchor="middle">Customers</text>
    </svg>
  </div>

  <div class="card">
    <h2>Narrative Arc</h2>
    <div class="arc-row">
      <div class="arc-step">
        <div class="qlabel">Q1</div>
        <div class="qdesc">Foundation<br/>GR00T + OCI infra</div>
      </div>
      <div class="arc-step">
        <div class="qlabel">Q2</div>
        <div class="qdesc">Traction<br/>design partners + DAgger</div>
      </div>
      <div class="arc-step active">
        <div class="qlabel">Q3 &#9654;</div>
        <div class="qdesc">Launch<br/>AI World + NVIDIA GTM</div>
      </div>
      <div class="arc-step">
        <div class="qlabel">Q4</div>
        <div class="qdesc">Series A raise<br/>$8M target</div>
      </div>
    </div>
  </div>

  <div class="card">
    <h2>Metrics</h2>
    <div class="metric-row">
      <div class="metric"><div class="label">ARR Target</div><div class="value">$430K</div></div>
      <div class="metric"><div class="label">NRR Target</div><div class="value">130%</div></div>
      <div class="metric"><div class="label">SR Target</div><div class="value">95%</div></div>
      <div class="metric"><div class="label">Customers</div><div class="value">6</div></div>
    </div>
  </div>

  <div class="card">
    <h2>Endpoints</h2>
    <div class="endpoint">GET  /health</div>
    <div class="endpoint">GET  /</div>
    <div class="endpoint">GET  /board/q3_deck</div>
    <div class="endpoint">POST /board/generate_q3</div>
  </div>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# Mock data helpers
# ---------------------------------------------------------------------------

def _q3_deck_meta():
    return {
        "deck": "OCI Robot Cloud — Q3 2026 Board Deck",
        "quarter": "Q3 2026",
        "narrative_arc": [
            {"quarter": "Q1", "theme": "Foundation", "highlights": ["GR00T N1.6 on OCI", "fine-tune pipeline", "first design partner"]},
            {"quarter": "Q2", "theme": "Traction",   "highlights": ["DAgger run158", "85% SR", "3 paying customers"]},
            {"quarter": "Q3", "theme": "Launch",     "highlights": ["AI World demo", "NVIDIA GTM", "ARR $430K"]},
            {"quarter": "Q4", "theme": "Series A",   "highlights": ["$8M raise", "6 enterprise customers", "multi-region"]},
        ],
        "targets": {"arr_usd": 430000, "nrr_pct": 130, "sr_pct": 95, "customers": 6},
        "status": "draft",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def _generate_q3(params=None):
    deck = _q3_deck_meta()
    deck["status"] = "generated"
    deck["slides"] = [
        {"slide": 1, "title": "OCI Robot Cloud — Q3 2026", "type": "cover"},
        {"slide": 2, "title": "Narrative Arc", "type": "arc"},
        {"slide": 3, "title": "Q3 KPIs", "type": "metrics"},
        {"slide": 4, "title": "AI World Preview", "type": "demo"},
        {"slide": 5, "title": "NVIDIA Partnership Progress", "type": "gtm"},
        {"slide": 6, "title": "Series A Readiness", "type": "fundraise"},
        {"slide": 7, "title": "Appendix — Technical Deep Dive", "type": "appendix"},
    ]
    if params:
        deck["params"] = params
    return deck


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

if _FASTAPI:
    app = FastAPI(title=SERVICE_NAME, version="1.0.0")

    @app.get("/health")
    def health():
        return JSONResponse({"status": "ok", "port": PORT, "service": SERVICE_NAME})

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return HTMLResponse(content=DASHBOARD_HTML)

    @app.get("/board/q3_deck")
    def q3_deck():
        return JSONResponse(_q3_deck_meta())

    @app.post("/board/generate_q3")
    def generate_q3(params: dict = Body(default={})):
        return JSONResponse(_generate_q3(params))


# ---------------------------------------------------------------------------
# Fallback stdlib HTTP server
# ---------------------------------------------------------------------------

class _FallbackHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _send(self, code, ctype, body):
        encoded = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self):
        if self.path == "/health":
            self._send(200, "application/json",
                       json.dumps({"status": "ok", "port": PORT, "service": SERVICE_NAME}))
        elif self.path in ("/", ""):
            self._send(200, "text/html", DASHBOARD_HTML)
        elif self.path == "/board/q3_deck":
            self._send(200, "application/json", json.dumps(_q3_deck_meta()))
        else:
            self._send(404, "application/json", json.dumps({"error": "not found"}))

    def do_POST(self):
        if self.path == "/board/generate_q3":
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length) if length else b"{}"
            try:
                params = json.loads(raw)
            except Exception:
                params = {}
            self._send(200, "application/json", json.dumps(_generate_q3(params)))
        else:
            self._send(404, "application/json", json.dumps({"error": "not found"}))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if _FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        print(f"fastapi not available — falling back to stdlib HTTPServer on port {PORT}")
        server = HTTPServer(("0.0.0.0", PORT), _FallbackHandler)
        print(f"{SERVICE_NAME} listening on http://0.0.0.0:{PORT}")
        server.serve_forever()
