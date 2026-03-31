"""customer_advocacy_engine.py — Turn happy customers into advocates (port 10265).

Reference + case study + referral + champion tracking.
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

PORT = 10265
SERVICE_NAME = "customer_advocacy_engine"

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Customer Advocacy Engine</title>
<style>
  body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; margin: 0; padding: 24px; }
  h1 { color: #C74634; margin-bottom: 4px; font-size: 1.7rem; }
  .subtitle { color: #38bdf8; font-size: 0.95rem; margin-bottom: 28px; }
  .cards { display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 32px; }
  .card { background: #1e293b; border-radius: 10px; padding: 18px 24px; min-width: 180px; }
  .card .label { font-size: 0.8rem; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.05em; }
  .card .value { font-size: 1.6rem; font-weight: 700; color: #38bdf8; margin-top: 4px; }
  .card .sub { font-size: 0.78rem; color: #64748b; margin-top: 2px; }
  .section { background: #1e293b; border-radius: 10px; padding: 20px 24px; margin-bottom: 20px; }
  .section h2 { color: #C74634; font-size: 1.05rem; margin-top: 0; margin-bottom: 16px; }
  svg text { font-family: 'Segoe UI', sans-serif; }
  .badge { display: inline-block; padding: 2px 10px; border-radius: 12px; font-size: 0.78rem; font-weight: 600; }
  .badge-green { background: #14532d; color: #4ade80; }
  .badge-yellow { background: #422006; color: #fbbf24; }
  .badge-blue { background: #0c4a6e; color: #38bdf8; }
  table { width: 100%; border-collapse: collapse; font-size: 0.88rem; }
  th { color: #94a3b8; text-align: left; padding: 6px 10px; border-bottom: 1px solid #334155; }
  td { padding: 8px 10px; border-bottom: 1px solid #1e293b; }
</style>
</head>
<body>
<h1>Customer Advocacy Engine</h1>
<div class="subtitle">Reference &bull; Case Study &bull; Referral &bull; Champion Tracking &nbsp;|&nbsp; Port {port}</div>

<div class="cards">
  <div class="card">
    <div class="label">Active Advocates</div>
    <div class="value">3</div>
    <div class="sub">Machina / Verdant / Helix</div>
  </div>
  <div class="card">
    <div class="label">Referral Pipeline ARR</div>
    <div class="value">$87.5K</div>
    <div class="sub">from referrals</div>
  </div>
  <div class="card">
    <div class="label">Influenced Deals</div>
    <div class="value">3</div>
    <div class="sub">via case study</div>
  </div>
  <div class="card">
    <div class="label">Win Rate Lift</div>
    <div class="value">+18%</div>
    <div class="sub">with reference call</div>
  </div>
</div>

<div class="section">
  <h2>Advocacy Value by Activity</h2>
  <!-- Bar chart: max scale = $87.5K ARR. Use relative heights. -->
  <!-- reference call: +18% win rate (index value ~54K equiv); case study: 3 deals (~45K); referral: $87.5K -->
  <!-- Normalise to 87.5K = 120px bar height -->
  <svg width="480" height="170" viewBox="0 0 480 170">
    <!-- Grid -->
    <line x1="60" y1="10" x2="440" y2="10" stroke="#334155" stroke-width="1"/>
    <line x1="60" y1="50" x2="440" y2="50" stroke="#334155" stroke-width="1"/>
    <line x1="60" y1="90" x2="440" y2="90" stroke="#334155" stroke-width="1"/>
    <line x1="60" y1="130" x2="440" y2="130" stroke="#334155" stroke-width="1"/>
    <!-- Y labels -->
    <text x="48" y="14" fill="#64748b" font-size="10" text-anchor="end">high</text>
    <text x="48" y="94" fill="#64748b" font-size="10" text-anchor="end">mid</text>
    <text x="48" y="134" fill="#64748b" font-size="10" text-anchor="end">0</text>
    <!-- Reference Call: win rate +18% → height ~74 -->
    <rect x="90" y="56" width="80" height="74" fill="#C74634" rx="3"/>
    <text x="130" y="52" fill="#e2e8f0" font-size="11" text-anchor="middle">+18% win rate</text>
    <text x="130" y="148" fill="#94a3b8" font-size="11" text-anchor="middle">Reference</text>
    <text x="130" y="162" fill="#64748b" font-size="10" text-anchor="middle">Call</text>
    <!-- Case Study: 3 influenced deals → height ~55 -->
    <rect x="210" y="75" width="80" height="55" fill="#38bdf8" rx="3"/>
    <text x="250" y="71" fill="#e2e8f0" font-size="11" text-anchor="middle">3 deals</text>
    <text x="250" y="148" fill="#94a3b8" font-size="11" text-anchor="middle">Case</text>
    <text x="250" y="162" fill="#64748b" font-size="10" text-anchor="middle">Study</text>
    <!-- Referral: $87.5K ARR → height ~120 -->
    <rect x="330" y="10" width="80" height="120" fill="#4ade80" rx="3"/>
    <text x="370" y="7" fill="#e2e8f0" font-size="11" text-anchor="middle">$87.5K ARR</text>
    <text x="370" y="148" fill="#94a3b8" font-size="11" text-anchor="middle">Referral</text>
    <text x="370" y="162" fill="#64748b" font-size="10" text-anchor="middle">Pipeline</text>
  </svg>
</div>

<div class="section">
  <h2>Customer Advocacy Tracks</h2>
  <table>
    <tr><th>Customer</th><th>NPS</th><th>Track</th><th>Next Action</th><th>Status</th></tr>
    <tr>
      <td>Machina</td><td>74</td><td>Champion</td>
      <td>Schedule exec reference call (Q2)</td>
      <td><span class="badge badge-green">CHAMPION</span></td>
    </tr>
    <tr>
      <td>Verdant</td><td>65</td><td>Nurture</td>
      <td>Share ROI case study template</td>
      <td><span class="badge badge-yellow">NURTURE</span></td>
    </tr>
    <tr>
      <td>Helix</td><td>66</td><td>Nurture</td>
      <td>Invite to advisory board</td>
      <td><span class="badge badge-yellow">NURTURE</span></td>
    </tr>
  </table>
</div>

<div class="section">
  <h2>Advocacy Program Metrics</h2>
  <table>
    <tr><th>Program</th><th>Participants</th><th>Impact</th><th>Conversion</th></tr>
    <tr><td>Reference Call</td><td>1 (Machina)</td><td>+18% win rate on tagged opps</td><td>High</td></tr>
    <tr><td>Case Study</td><td>2 (Machina, Verdant draft)</td><td>3 influenced deals pipeline</td><td>Medium</td></tr>
    <tr><td>Referral</td><td>1 (Machina)</td><td>$87.5K ARR in referral pipe</td><td>High</td></tr>
    <tr><td>Advisory Board</td><td>0 (recruiting)</td><td>Product roadmap input</td><td>TBD</td></tr>
  </table>
</div>

</body>
</html>
""".replace("{port}", str(PORT))


if _FASTAPI_AVAILABLE:
    app = FastAPI(title=SERVICE_NAME, version="1.0.0")

    @app.get("/health")
    def health():
        return JSONResponse({"status": "ok", "port": PORT, "service": SERVICE_NAME, "ts": datetime.utcnow().isoformat()})

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return HTMLResponse(content=DASHBOARD_HTML)

    @app.get("/customers/advocacy/score")
    def advocacy_scores():
        """Stub: return NPS-based advocacy scores for all customers."""
        return JSONResponse({
            "ts": datetime.utcnow().isoformat(),
            "scores": [
                {"customer": "Machina", "nps": 74, "track": "champion", "eligible_programs": ["reference", "case_study", "referral"]},
                {"customer": "Verdant", "nps": 65, "track": "nurture",  "eligible_programs": ["case_study"]},
                {"customer": "Helix",   "nps": 66, "track": "nurture",  "eligible_programs": ["advisory_board"]}
            ]
        })

    @app.post("/customers/advocacy/request")
    def request_advocacy(payload: dict = None):
        """Stub: submit an advocacy activity request (reference call, case study, referral)."""
        payload = payload or {}
        return JSONResponse({
            "ts": datetime.utcnow().isoformat(),
            "request_id": f"adv-{int(time.time())}",
            "customer": payload.get("customer", "unknown"),
            "program": payload.get("program", "reference"),
            "status": "submitted",
            "next_step": "CSM notified; expect response within 2 business days"
        })

else:
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
                body = DASHBOARD_HTML.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(body)

        def log_message(self, fmt, *args):
            pass


if __name__ == "__main__":
    if _FASTAPI_AVAILABLE:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        with socketserver.TCPServer(("", PORT), _Handler) as httpd:
            print(f"{SERVICE_NAME} fallback server on port {PORT}")
            httpd.serve_forever()
