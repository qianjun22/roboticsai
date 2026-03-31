"""Enterprise Pilot Playbook — structured 30-day enterprise pilot service.

Port: 10225
Features: 4-week pilot plan, success criteria, conversion tracking, exec review gate
"""

import json
import time
from datetime import datetime

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    from fastapi import Body
    import uvicorn
    _FASTAPI_AVAILABLE = True
except ImportError:
    _FASTAPI_AVAILABLE = False

PORT = 10225
SERVICE_NAME = "enterprise_pilot_playbook"

HTML_DASHBOARD = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Enterprise Pilot Playbook</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; padding: 2rem; }
    h1 { color: #C74634; font-size: 1.8rem; margin-bottom: 0.5rem; }
    h2 { color: #38bdf8; font-size: 1.2rem; margin: 1.5rem 0 0.75rem; }
    .badge { display: inline-block; background: #1e293b; border: 1px solid #334155; border-radius: 6px;
             padding: 0.25rem 0.75rem; font-size: 0.8rem; color: #94a3b8; margin-right: 0.5rem; }
    .badge.red { border-color: #C74634; color: #C74634; }
    .badge.blue { border-color: #38bdf8; color: #38bdf8; }
    .badge.green { border-color: #4ade80; color: #4ade80; }
    .card { background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 1.25rem;
            margin-bottom: 1rem; }
    .metric-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 1rem; margin: 1rem 0; }
    .metric { background: #0f172a; border-radius: 8px; padding: 1rem; text-align: center; }
    .metric .val { font-size: 2rem; font-weight: 700; color: #38bdf8; }
    .metric .val.green { color: #4ade80; }
    .metric .lbl { font-size: 0.75rem; color: #64748b; margin-top: 0.25rem; }
    table { width: 100%; border-collapse: collapse; font-size: 0.88rem; }
    th { background: #0f172a; color: #38bdf8; padding: 0.6rem 0.8rem; text-align: left; }
    td { padding: 0.55rem 0.8rem; border-bottom: 1px solid #1e293b; color: #cbd5e1; }
    tr:hover td { background: #1e293b55; }
    .week { display: flex; gap: 1rem; flex-wrap: wrap; margin-top: 0.5rem; }
    .week-card { flex: 1; min-width: 120px; background: #0f172a; border-radius: 8px; padding: 0.9rem;
                 border-left: 3px solid #38bdf8; }
    .week-card.gate { border-left-color: #C74634; }
    .week-card h3 { font-size: 0.8rem; color: #38bdf8; margin-bottom: 0.4rem; }
    .week-card.gate h3 { color: #C74634; }
    .week-card p { font-size: 0.78rem; color: #94a3b8; line-height: 1.4; }
    footer { margin-top: 2rem; font-size: 0.75rem; color: #475569; }
  </style>
</head>
<body>
  <h1>Enterprise Pilot Playbook</h1>
  <div style="margin:0.5rem 0 1.25rem">
    <span class="badge blue">port 10225</span>
    <span class="badge green">30-day pilot</span>
    <span class="badge">73% conversion</span>
    <span class="badge">NPS 71</span>
  </div>

  <div class="card">
    <h2>Pilot Conversion Metrics</h2>
    <svg viewBox="0 0 560 220" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:560px;display:block;margin:1rem 0">
      <!-- grid lines -->
      <line x1="60" y1="20" x2="60" y2="170" stroke="#334155" stroke-width="1"/>
      <line x1="60" y1="170" x2="540" y2="170" stroke="#334155" stroke-width="1"/>
      <line x1="60" y1="130" x2="540" y2="130" stroke="#1e293b" stroke-width="1" stroke-dasharray="4,3"/>
      <line x1="60" y1="90" x2="540" y2="90" stroke="#1e293b" stroke-width="1" stroke-dasharray="4,3"/>
      <line x1="60" y1="50" x2="540" y2="50" stroke="#1e293b" stroke-width="1" stroke-dasharray="4,3"/>
      <!-- y-axis labels: 0,25,50,75,100 -->
      <text x="52" y="174" fill="#64748b" font-size="11" text-anchor="end">0</text>
      <text x="52" y="134" fill="#64748b" font-size="11" text-anchor="end">25</text>
      <text x="52" y="94" fill="#64748b" font-size="11" text-anchor="end">50</text>
      <text x="52" y="54" fill="#64748b" font-size="11" text-anchor="end">75</text>
      <!-- pilot-to-paid 73% → 73/100*150=109.5px bar -->
      <rect x="100" y="60" width="65" height="110" fill="#38bdf8" rx="4"/>
      <text x="132" y="55" fill="#38bdf8" font-size="12" text-anchor="middle" font-weight="bold">73%</text>
      <text x="132" y="190" fill="#94a3b8" font-size="11" text-anchor="middle">Pilot-to-Paid</text>
      <!-- avg pilot score 4.2/5 → 4.2/5*150=126px bar -->
      <rect x="230" y="44" width="65" height="126" fill="#C74634" rx="4"/>
      <text x="262" y="39" fill="#C74634" font-size="12" text-anchor="middle" font-weight="bold">4.2/5</text>
      <text x="262" y="190" fill="#94a3b8" font-size="11" text-anchor="middle">Avg Pilot Score</text>
      <!-- NPS 71 → 71/100*150=106.5px bar -->
      <rect x="360" y="63" width="65" height="107" fill="#4ade80" rx="4"/>
      <text x="392" y="58" fill="#4ade80" font-size="12" text-anchor="middle" font-weight="bold">71</text>
      <text x="392" y="190" fill="#94a3b8" font-size="11" text-anchor="middle">Pilot NPS</text>
      <!-- legend -->
      <rect x="80" y="205" width="12" height="10" fill="#38bdf8" rx="2"/>
      <text x="96" y="214" fill="#94a3b8" font-size="11">Conversion %</text>
      <rect x="210" y="205" width="12" height="10" fill="#C74634" rx="2"/>
      <text x="226" y="214" fill="#94a3b8" font-size="11">Score (out of 5)</text>
      <rect x="360" y="205" width="12" height="10" fill="#4ade80" rx="2"/>
      <text x="376" y="214" fill="#94a3b8" font-size="11">NPS (0-100)</text>
    </svg>
  </div>

  <div class="metric-grid">
    <div class="metric"><div class="val green">73%</div><div class="lbl">Pilot-to-paid conversion</div></div>
    <div class="metric"><div class="val">4.2/5</div><div class="lbl">Avg pilot score</div></div>
    <div class="metric"><div class="val green">71</div><div class="lbl">Pilot NPS</div></div>
    <div class="metric"><div class="val">30 days</div><div class="lbl">Pilot duration</div></div>
    <div class="metric"><div class="val">SR&gt;65%</div><div class="lbl">W3 gate threshold</div></div>
  </div>

  <div class="card">
    <h2>4-Week Pilot Plan</h2>
    <div class="week">
      <div class="week-card">
        <h3>W1 — Setup</h3>
        <p>Env provisioning, OCI account, GR00T endpoint live. KPIs agreed. Baseline eval run.</p>
      </div>
      <div class="week-card">
        <h3>W2 — Fine-Tune</h3>
        <p>Customer demo data collected. 1 fine-tune cycle. SR benchmark vs baseline. Weekly check-in.</p>
      </div>
      <div class="week-card gate">
        <h3>W3 — Production Test &amp; Gate</h3>
        <p>Full prod sim. SR &gt; 65% = proceed to commercial. Failure = extend or halt. Gate decision recorded.</p>
      </div>
      <div class="week-card">
        <h3>W4 — Exec Review</h3>
        <p>ROI report. Exec presentation. Contract negotiation kickoff. NPS survey sent.</p>
      </div>
    </div>
  </div>

  <div class="card">
    <h2>Success Criteria</h2>
    <table>
      <tr><th>Week</th><th>Criterion</th><th>Threshold</th><th>Action if missed</th></tr>
      <tr><td>W1</td><td>Env live &amp; baseline eval complete</td><td>100% setup</td><td>Escalate to CSE</td></tr>
      <tr><td>W2</td><td>Fine-tune MAE improvement</td><td>&lt;0.10 MAE</td><td>Add training data</td></tr>
      <tr><td>W3</td><td>Production SR gate</td><td>SR &gt; 65%</td><td>Convert or 2-week ext</td></tr>
      <tr><td>W4</td><td>Exec approval + NPS</td><td>NPS &ge; 50</td><td>Executive sponsor call</td></tr>
    </table>
  </div>

  <div class="card">
    <h2>API Endpoints</h2>
    <table>
      <tr><th>Method</th><th>Path</th><th>Description</th></tr>
      <tr><td>GET</td><td>/health</td><td>Service health check</td></tr>
      <tr><td>GET</td><td>/</td><td>This dashboard</td></tr>
      <tr><td>GET</td><td>/pilots/playbook</td><td>Return full pilot playbook config</td></tr>
      <tr><td>POST</td><td>/pilots/log_result</td><td>Log a pilot week result</td></tr>
    </table>
  </div>

  <footer>OCI Robot Cloud &bull; Enterprise Pilot Playbook &bull; port 10225 &bull; cycle-542A</footer>
</body>
</html>
"""

_PLAYBOOK = {
    "duration_days": 30,
    "weeks": [
        {"week": 1, "name": "Setup",
         "activities": ["Env provisioning", "OCI account", "GR00T endpoint live", "KPIs agreed", "Baseline eval"],
         "success_criterion": "100% setup complete"},
        {"week": 2, "name": "Fine-Tune",
         "activities": ["Demo data collection", "1 fine-tune cycle", "SR benchmark", "Weekly check-in"],
         "success_criterion": "MAE < 0.10"},
        {"week": 3, "name": "Production Test", "gate": True,
         "activities": ["Full prod simulation", "SR gate evaluation", "Go/no-go decision"],
         "success_criterion": "SR > 65%", "action_if_missed": "extend or halt"},
        {"week": 4, "name": "Exec Review",
         "activities": ["ROI report", "Exec presentation", "Contract negotiation kickoff", "NPS survey"],
         "success_criterion": "NPS >= 50"}
    ],
    "conversion_metrics": {
        "pilot_to_paid_pct": 73,
        "avg_pilot_score": 4.2,
        "pilot_nps": 71
    },
    "w3_gate_threshold_sr_pct": 65
}

if _FASTAPI_AVAILABLE:
    app = FastAPI(title=SERVICE_NAME, version="1.0.0")

    @app.get("/health")
    def health():
        return JSONResponse({"status": "ok", "port": PORT, "service": SERVICE_NAME,
                             "timestamp": datetime.utcnow().isoformat() + "Z"})

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return HTML_DASHBOARD

    @app.get("/pilots/playbook")
    def get_playbook():
        return JSONResponse(_PLAYBOOK)

    @app.post("/pilots/log_result")
    def log_result(body: dict = Body(default={})):
        # Stub: accept and echo pilot week result
        return JSONResponse({
            "logged": True,
            "received": body,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "message": "Pilot result recorded (stub)"
        })

else:
    import http.server
    import urllib.parse

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            path = urllib.parse.urlparse(self.path).path
            if path == "/health":
                body = json.dumps({"status": "ok", "port": PORT, "service": SERVICE_NAME}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)
            elif path == "/pilots/playbook":
                body = json.dumps(_PLAYBOOK).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(HTML_DASHBOARD.encode())

        def do_POST(self):
            path = urllib.parse.urlparse(self.path).path
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length) if length else b"{}"
            if path == "/pilots/log_result":
                body = json.dumps({"logged": True, "message": "Pilot result recorded (stub)"}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)

        def log_message(self, fmt, *args):
            pass

    def _run_fallback():
        server = http.server.HTTPServer(("0.0.0.0", PORT), _Handler)
        print(f"[{SERVICE_NAME}] stdlib fallback on port {PORT}")
        server.serve_forever()

if __name__ == "__main__":
    if _FASTAPI_AVAILABLE:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        _run_fallback()
