"""account_based_marketing_engine.py — Account-Based Marketing Engine (port 10217)

Personalized outreach at 140 target accounts across 3 tiers.
Drives 1.8x SQL conversion lift vs non-ABM baseline.
"""

import json
import random
from datetime import datetime

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    _FASTAPI = True
except ImportError:
    _FASTAPI = False

PORT = 10217
SERVICE_NAME = "account_based_marketing_engine"

# ---------------------------------------------------------------------------
# App / fallback
# ---------------------------------------------------------------------------

if _FASTAPI:
    app = FastAPI(title=SERVICE_NAME, version="1.0.0")

# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Account-Based Marketing Engine</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; padding: 2rem; }
    h1 { color: #C74634; font-size: 1.8rem; margin-bottom: 0.25rem; }
    .subtitle { color: #38bdf8; font-size: 0.95rem; margin-bottom: 2rem; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 1.2rem; margin-bottom: 2rem; }
    .card { background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 1.2rem; }
    .card h3 { color: #38bdf8; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 0.5rem; }
    .card .val { font-size: 2rem; font-weight: 700; color: #f1f5f9; }
    .card .sub { font-size: 0.8rem; color: #94a3b8; margin-top: 0.25rem; }
    .section { background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 1.5rem; margin-bottom: 1.5rem; }
    .section h2 { color: #C74634; font-size: 1.1rem; margin-bottom: 1rem; }
    table { width: 100%; border-collapse: collapse; font-size: 0.88rem; }
    th { text-align: left; color: #38bdf8; padding: 0.5rem 0.75rem; border-bottom: 1px solid #334155; }
    td { padding: 0.5rem 0.75rem; border-bottom: 1px solid #1e293b; color: #cbd5e1; }
    tr:hover td { background: #0f172a; }
    .badge { display: inline-block; padding: 0.15rem 0.55rem; border-radius: 9999px; font-size: 0.75rem; font-weight: 600; }
    .badge-gold { background: #713f12; color: #fde68a; }
    .badge-silver { background: #1e3a5f; color: #93c5fd; }
    .badge-bronze { background: #292524; color: #d6d3d1; }
    .badge-green { background: #14532d; color: #86efac; }
    svg text { font-family: 'Segoe UI', sans-serif; }
  </style>
</head>
<body>
  <h1>Account-Based Marketing Engine</h1>
  <p class="subtitle">Personalized outreach &mdash; 140 target accounts &mdash; 1.8&times; SQL conversion lift &mdash; port 10217</p>

  <div class="grid">
    <div class="card"><h3>Target Accounts</h3><div class="val">140</div><div class="sub">Across 3 tiers</div></div>
    <div class="card"><h3>ABM Tier 1 SQL Rate</h3><div class="val">40%</div><div class="sub">vs 22% non-ABM (1.8&times;)</div></div>
    <div class="card"><h3>Personalization Steps</h3><div class="val">4</div><div class="sub">Signal → Content → Outreach → Nurture</div></div>
    <div class="card"><h3>Named Accounts</h3><div class="val">10</div><div class="sub">Tier 1 (white-glove)</div></div>
  </div>

  <div class="section">
    <h2>ABM Conversion Lift vs Non-ABM (SVG Bar Chart)</h2>
    <svg width="520" height="220" viewBox="0 0 520 220">
      <!-- Y axis labels -->
      <text x="28" y="20" fill="#94a3b8" font-size="11">50%</text>
      <text x="28" y="65" fill="#94a3b8" font-size="11">40%</text>
      <text x="28" y="110" fill="#94a3b8" font-size="11">30%</text>
      <text x="28" y="155" fill="#94a3b8" font-size="11">20%</text>
      <text x="28" y="175" fill="#94a3b8" font-size="11">10%</text>
      <!-- Grid lines -->
      <line x1="60" y1="15" x2="510" y2="15" stroke="#334155" stroke-width="1"/>
      <line x1="60" y1="60" x2="510" y2="60" stroke="#334155" stroke-width="1"/>
      <line x1="60" y1="105" x2="510" y2="105" stroke="#334155" stroke-width="1"/>
      <line x1="60" y1="150" x2="510" y2="150" stroke="#334155" stroke-width="1"/>
      <line x1="60" y1="170" x2="510" y2="170" stroke="#334155" stroke-width="1"/>
      <!-- ABM Tier 1: 40% -> tall bar (160px from bottom=175) -> y=15, h=160 -->
      <rect x="80" y="15" width="40" height="160" fill="#C74634" rx="3"/>
      <text x="100" y="11" fill="#C74634" font-size="11" text-anchor="middle" font-weight="bold">40%</text>
      <!-- Non-ABM: 22% -> bar height=88px -> y=87, h=88 -->
      <rect x="230" y="87" width="40" height="88" fill="#334155" rx="3"/>
      <text x="250" y="83" fill="#94a3b8" font-size="11" text-anchor="middle">22%</text>
      <!-- Lift label -->
      <text x="390" y="90" fill="#38bdf8" font-size="13" font-weight="bold" text-anchor="middle">1.8&times; lift</text>
      <text x="390" y="108" fill="#94a3b8" font-size="10" text-anchor="middle">ABM vs Non-ABM</text>
      <!-- X labels -->
      <text x="100" y="192" fill="#e2e8f0" font-size="10" text-anchor="middle">ABM Tier 1</text>
      <text x="100" y="204" fill="#94a3b8" font-size="9" text-anchor="middle">(10 named accts)</text>
      <text x="250" y="192" fill="#e2e8f0" font-size="10" text-anchor="middle">Non-ABM</text>
      <text x="250" y="204" fill="#94a3b8" font-size="9" text-anchor="middle">(general outreach)</text>
    </svg>
  </div>

  <div class="section">
    <h2>Tier Structure</h2>
    <table>
      <thead><tr><th>Tier</th><th>Accounts</th><th>Strategy</th><th>SQL Rate</th><th>Status</th></tr></thead>
      <tbody>
        <tr><td><span class="badge badge-gold">Tier 1</span></td><td>10 named accounts</td><td>White-glove: exec briefing, custom demo, dedicated AE</td><td>40%</td><td><span class="badge badge-green">Active</span></td></tr>
        <tr><td><span class="badge badge-silver">Tier 2</span></td><td>30 accounts</td><td>Semi-personalised: industry content, SDR sequence, webinar invite</td><td>31%</td><td><span class="badge badge-green">Active</span></td></tr>
        <tr><td><span class="badge badge-bronze">Tier 3</span></td><td>100 accounts</td><td>Programmatic: intent-triggered nurture, paid retargeting</td><td>25%</td><td><span class="badge badge-green">Active</span></td></tr>
      </tbody>
    </table>
  </div>

  <div class="section">
    <h2>4-Step Personalization Flow</h2>
    <table>
      <thead><tr><th>Step</th><th>Action</th><th>Signal / Input</th><th>Output</th></tr></thead>
      <tbody>
        <tr><td>1</td><td>Intent Signal Capture</td><td>G2, Bombora, web visits, LinkedIn engagement</td><td>Account intent score (0–100)</td></tr>
        <tr><td>2</td><td>Content Personalization</td><td>Industry, persona, pain point, stage</td><td>Tailored asset pack (deck, ROI calc, case study)</td></tr>
        <tr><td>3</td><td>Multi-channel Outreach</td><td>Email sequence + LinkedIn + direct mail (T1)</td><td>Meeting booked / demo request</td></tr>
        <tr><td>4</td><td>Nurture &amp; Handoff</td><td>Engagement score, ICP fit, buying signals</td><td>SQL handoff to AE with context brief</td></tr>
      </tbody>
    </table>
  </div>

  <div class="section">
    <h2>Endpoints</h2>
    <table>
      <thead><tr><th>Method</th><th>Path</th><th>Description</th></tr></thead>
      <tbody>
        <tr><td>GET</td><td>/health</td><td>Service health check</td></tr>
        <tr><td>GET</td><td>/</td><td>This dashboard</td></tr>
        <tr><td>GET</td><td>/marketing/abm/accounts</td><td>List target accounts with tier &amp; intent score</td></tr>
        <tr><td>POST</td><td>/marketing/abm/personalize</td><td>Generate personalized outreach plan for an account</td></tr>
      </tbody>
    </table>
  </div>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

if _FASTAPI:
    @app.get("/health")
    def health():
        return JSONResponse({"status": "ok", "port": PORT, "service": SERVICE_NAME, "timestamp": datetime.utcnow().isoformat()})

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return HTMLResponse(content=DASHBOARD_HTML)

    @app.get("/marketing/abm/accounts")
    def list_accounts():
        """List target accounts with tier and intent score (stub — returns mock data)."""
        mock_accounts = [
            {"account_id": f"acct_{i:03d}", "name": f"Enterprise Co {i}",
             "tier": 1 if i <= 10 else (2 if i <= 40 else 3),
             "industry": random.choice(["Manufacturing", "Logistics", "Healthcare", "Retail", "Automotive"]),
             "intent_score": random.randint(55, 99),
             "stage": random.choice(["awareness", "consideration", "decision"]),
             "sql_converted": random.random() < (0.40 if i <= 10 else 0.31 if i <= 40 else 0.25)}
            for i in range(1, 141)
        ]
        return JSONResponse({
            "total_accounts": 140,
            "tiers": {"tier1": 10, "tier2": 30, "tier3": 100},
            "accounts": mock_accounts[:20],  # paginated preview
            "note": "Showing first 20 of 140 accounts. Use ?tier=1|2|3 filter in production.",
        })

    @app.post("/marketing/abm/personalize")
    def personalize(payload: dict = None):
        """Generate personalized outreach plan for an account (stub — returns mock data)."""
        account_name = (payload or {}).get("account_name", "Acme Corp")
        tier = (payload or {}).get("tier", 1)
        intent_score = (payload or {}).get("intent_score", random.randint(60, 95))
        return JSONResponse({
            "account": account_name,
            "tier": tier,
            "intent_score": intent_score,
            "personalization_plan": [
                {"step": 1, "action": "Intent Signal Capture", "signal": f"G2 intent score {intent_score}", "next": "Trigger Tier-{tier} sequence"},
                {"step": 2, "action": "Content Personalization", "assets": ["Custom ROI calculator", "Industry case study", "Executive briefing deck"]},
                {"step": 3, "action": "Multi-channel Outreach", "channels": ["Email sequence (5-touch)", "LinkedIn InMail", "Direct mail (T1 only)"] if tier == 1 else ["Email sequence (3-touch)", "LinkedIn InMail"]},
                {"step": 4, "action": "Nurture & Handoff", "sql_threshold": 70, "handoff_trigger": "Meeting booked OR intent_score >= 80"},
            ],
            "estimated_sql_probability": 0.40 if tier == 1 else (0.31 if tier == 2 else 0.25),
            "generated_at": datetime.utcnow().isoformat(),
        })

# ---------------------------------------------------------------------------
# Fallback HTTP server
# ---------------------------------------------------------------------------

if not _FASTAPI:
    from http.server import HTTPServer, BaseHTTPRequestHandler

    class _Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):  # silence default logging
            pass

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

    def _run_fallback():
        server = HTTPServer(("0.0.0.0", PORT), _Handler)
        print(f"[{SERVICE_NAME}] fallback http.server running on port {PORT}")
        server.serve_forever()

# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if _FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        _run_fallback()
