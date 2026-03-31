"""Board Governance Tracker — board meeting management, materials & KPI tracking.

Port: 10011
Cycle: 488B
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

try:
    from fastapi import FastAPI, Query
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    _FASTAPI = True
except ImportError:
    _FASTAPI = False

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
PORT = 10011

BOARD_DATES = {
    "Q1 2026": "2026-03-15",
    "Q2 2026": "2026-06-14",
    "Q3 2026": "2026-09-13",
    "Q4 2026": "2026-12-13",
}

KPIS: dict = {
    "arr": 250_000,
    "burn": 45_000,
    "runway_months": 18,
    "nrr": 118,
    "sr_pct": 85,
    "nvidia_milestone": "intro scheduled",
    "ai_world_readiness_pct": 72,
}

QUARTER_DATA: dict[str, dict] = {
    "Q1 2026": {
        "kpis": {**KPIs, "sr_pct": 85, "ai_world_readiness_pct": 72},
        "action_items": [
            "Finalise NVIDIA partnership MoU draft",
            "Complete AI World 2026 demo rehearsal",
            "Close Series A term sheet",
            "Hire VP of Engineering",
        ],
        "decisions_log": [
            "Approved $120k infra spend for A100 cluster expansion",
            "Ratified OCI Robot Cloud public beta launch",
        ],
        "materials_status": "deck submitted, financials pending CFO sign-off",
    },
    "Q2 2026": {
        "kpis": {**KPIs, "sr_pct": 88, "ai_world_readiness_pct": 90},
        "action_items": [
            "Present AI World post-mortem",
            "Review Series A close & cap table",
            "Approve FY2026 revised budget",
        ],
        "decisions_log": [
            "Approved AI World sponsorship ($45k)",
            "Authorised NVIDIA co-sell agreement",
        ],
        "materials_status": "draft in progress",
    },
    "Q3 2026": {
        "kpis": {**KPIs, "sr_pct": 91, "arr": 380_000},
        "action_items": [
            "Mid-year strategy review",
            "Evaluate international expansion (EU)",
            "Approve stock option refresh pool",
        ],
        "decisions_log": [],
        "materials_status": "not started",
    },
    "Q4 2026": {
        "kpis": {**KPIs, "sr_pct": 94, "arr": 500_000},
        "action_items": [
            "2027 budget approval",
            "Board composition review",
            "Annual CEO performance review",
        ],
        "decisions_log": [],
        "materials_status": "not started",
    },
}

# Fix forward-reference in QUARTER_DATA (KPIs was referenced before assignment)
for _q, _d in QUARTER_DATA.items():
    _d["kpis"] = {k: v for k, v in _d["kpis"].items()}


def get_board_deck(quarter: str) -> dict:
    q = quarter.strip() if quarter else "Q1 2026"
    data = QUARTER_DATA.get(q)
    if data is None:
        # Default to Q1
        q = "Q1 2026"
        data = QUARTER_DATA[q]
    return {"quarter": q, **data}


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------
DASHBOARD_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Board Governance Tracker — OCI Robot Cloud</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: #0f172a; color: #e2e8f0; font-family: 'Inter', 'Segoe UI', sans-serif; min-height: 100vh; padding: 2rem; }
    h1 { color: #C74634; font-size: 1.75rem; font-weight: 700; margin-bottom: 0.25rem; }
    .subtitle { color: #38bdf8; font-size: 0.95rem; margin-bottom: 2rem; }
    .cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-bottom: 2.5rem; }
    .card { background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 1.25rem; }
    .card-label { font-size: 0.75rem; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.5rem; }
    .card-value { font-size: 1.8rem; font-weight: 700; color: #38bdf8; }
    .card-value.green { color: #4ade80; }
    .card-value.red   { color: #C74634; }
    .card-value.yellow{ color: #facc15; }
    .card-sub { font-size: 0.8rem; color: #64748b; margin-top: 0.25rem; }
    .section-title { color: #38bdf8; font-size: 1.1rem; font-weight: 600; margin-bottom: 1rem; }
    .chart-wrap  { background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 1.5rem; margin-bottom: 2rem; }
    .dates-grid  { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 1rem; margin-bottom: 2rem; }
    .date-card   { background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 1rem; text-align: center; }
    .date-q      { font-size: 1rem; font-weight: 700; color: #C74634; margin-bottom: 0.25rem; }
    .date-val    { font-size: 0.875rem; color: #94a3b8; }
    .consent-table { width: 100%; border-collapse: collapse; }
    .consent-table th, .consent-table td { border: 1px solid #334155; padding: 0.6rem 1rem; font-size: 0.875rem; }
    .consent-table th { background: #0f172a; color: #94a3b8; text-transform: uppercase; font-size: 0.75rem; }
    .consent-table tr:nth-child(even) td { background: #162032; }
    .status-done   { color: #4ade80; font-weight: 600; }
    .status-ip     { color: #facc15; font-weight: 600; }
    .status-pending{ color: #f87171; font-weight: 600; }
    svg text { font-family: inherit; }
    footer { margin-top: 3rem; color: #475569; font-size: 0.75rem; text-align: center; }
  </style>
</head>
<body>
  <h1>Board Governance Tracker</h1>
  <p class="subtitle">OCI Robot Cloud — Board Meeting Management, KPI Tracking &amp; Materials Readiness &nbsp;|&nbsp; Port 10011</p>

  <!-- Board dates -->
  <div class="section-title">2026 Board Meeting Dates</div>
  <div class="dates-grid">
    <div class="date-card"><div class="date-q">Q1 2026</div><div class="date-val">15 Mar 2026</div></div>
    <div class="date-card"><div class="date-q">Q2 2026</div><div class="date-val">14 Jun 2026</div></div>
    <div class="date-card"><div class="date-q">Q3 2026</div><div class="date-val">13 Sep 2026</div></div>
    <div class="date-card"><div class="date-q">Q4 2026</div><div class="date-val">13 Dec 2026</div></div>
  </div>

  <!-- KPI dashboard -->
  <div class="section-title">Key Performance Indicators (Q1 2026)</div>
  <div class="cards">
    <div class="card">
      <div class="card-label">ARR</div>
      <div class="card-value green">$250K</div>
      <div class="card-sub">Annual Recurring Revenue</div>
    </div>
    <div class="card">
      <div class="card-label">Monthly Burn</div>
      <div class="card-value red">$45K</div>
      <div class="card-sub">Cash outflow / month</div>
    </div>
    <div class="card">
      <div class="card-label">Runway</div>
      <div class="card-value">18 mo</div>
      <div class="card-sub">Cash runway</div>
    </div>
    <div class="card">
      <div class="card-label">NRR</div>
      <div class="card-value green">118%</div>
      <div class="card-sub">Net Revenue Retention</div>
    </div>
    <div class="card">
      <div class="card-label">Task Success Rate</div>
      <div class="card-value">85%</div>
      <div class="card-sub">Robot policy SR</div>
    </div>
    <div class="card">
      <div class="card-label">NVIDIA Milestone</div>
      <div class="card-value yellow" style="font-size:1rem;padding-top:0.3rem;">Intro Scheduled</div>
      <div class="card-sub">Partnership status</div>
    </div>
    <div class="card">
      <div class="card-label">AI World Readiness</div>
      <div class="card-value yellow">72%</div>
      <div class="card-sub">Demo readiness</div>
    </div>
  </div>

  <!-- SR bar chart across quarters -->
  <div class="chart-wrap">
    <div class="section-title">Task Success Rate Trajectory — 2026</div>
    <svg width="100%" viewBox="0 0 640 260" xmlns="http://www.w3.org/2000/svg">
      <!-- axes -->
      <line x1="60" y1="20" x2="60" y2="210" stroke="#475569" stroke-width="1.5"/>
      <line x1="60" y1="210" x2="620" y2="210" stroke="#475569" stroke-width="1.5"/>
      <!-- y labels (70-100%) => 140px range => 1%=4.67px, 70%=210 -->
      <text x="52" y="214" fill="#64748b" font-size="11" text-anchor="end">70</text>
      <text x="52" y="167" fill="#64748b" font-size="11" text-anchor="end">80</text>
      <text x="52" y="120" fill="#64748b" font-size="11" text-anchor="end">90</text>
      <text x="52" y="73"  fill="#64748b" font-size="11" text-anchor="end">100</text>
      <!-- grid lines -->
      <line x1="60" y1="167" x2="620" y2="167" stroke="#1e293b" stroke-width="1" stroke-dasharray="4 3"/>
      <line x1="60" y1="120" x2="620" y2="120" stroke="#1e293b" stroke-width="1" stroke-dasharray="4 3"/>
      <line x1="60" y1="73"  x2="620" y2="73"  stroke="#1e293b" stroke-width="1" stroke-dasharray="4 3"/>
      <!-- bars: y = 210 - (sr-70)*4.67 -->
      <!-- Q1 85% => y=210-(15*4.67)=210-70=140; h=70 -->
      <rect x="90"  y="140" width="100" height="70"  fill="#38bdf8" rx="4"/>
      <text x="140" y="134" fill="#38bdf8" font-size="12" font-weight="700" text-anchor="middle">85%</text>
      <text x="140" y="228" fill="#94a3b8" font-size="11" text-anchor="middle">Q1 2026</text>
      <!-- Q2 88% => y=210-84=126; h=84 -->
      <rect x="230" y="126" width="100" height="84"  fill="#38bdf8" rx="4" opacity="0.88"/>
      <text x="280" y="120" fill="#38bdf8" font-size="12" font-weight="700" text-anchor="middle">88%</text>
      <text x="280" y="228" fill="#94a3b8" font-size="11" text-anchor="middle">Q2 2026</text>
      <!-- Q3 91% => y=210-98=112; h=98 -->
      <rect x="370" y="112" width="100" height="98"  fill="#38bdf8" rx="4" opacity="0.78"/>
      <text x="420" y="106" fill="#38bdf8" font-size="12" font-weight="700" text-anchor="middle">91%</text>
      <text x="420" y="228" fill="#94a3b8" font-size="11" text-anchor="middle">Q3 2026</text>
      <!-- Q4 94% => y=210-112=98; h=112 -->
      <rect x="510" y="98" width="100" height="112" fill="#38bdf8" rx="4" opacity="0.68"/>
      <text x="560" y="92" fill="#38bdf8" font-size="12" font-weight="700" text-anchor="middle">94%</text>
      <text x="560" y="228" fill="#94a3b8" font-size="11" text-anchor="middle">Q4 2026</text>
      <text transform="rotate(-90)" x="-115" y="18" fill="#64748b" font-size="11" text-anchor="middle">Success Rate (%)</text>
    </svg>
  </div>

  <!-- Consent thresholds -->
  <div class="chart-wrap">
    <div class="section-title">Consent &amp; Approval Thresholds</div>
    <table class="consent-table">
      <thead><tr><th>Decision Type</th><th>Required Approval</th><th>Threshold</th></tr></thead>
      <tbody>
        <tr><td>Budget &gt;$50k</td><td>Board majority</td><td>&ge; 3/5 directors</td></tr>
        <tr><td>Equity issuance</td><td>Board + investor consent</td><td>Unanimous</td></tr>
        <tr><td>Executive hire (VP+)</td><td>CEO + Board chair</td><td>2 approvals</td></tr>
        <tr><td>Partnership MoU</td><td>CEO approval</td><td>Solo CEO</td></tr>
        <tr><td>Strategic pivot</td><td>Board majority</td><td>&ge; 3/5 directors</td></tr>
      </tbody>
    </table>
  </div>

  <!-- Materials readiness -->
  <div class="chart-wrap">
    <div class="section-title">Materials Readiness by Quarter</div>
    <table class="consent-table">
      <thead><tr><th>Quarter</th><th>Board Date</th><th>Materials Status</th></tr></thead>
      <tbody>
        <tr><td>Q1 2026</td><td>15 Mar 2026</td><td><span class="status-ip">Deck submitted, financials pending</span></td></tr>
        <tr><td>Q2 2026</td><td>14 Jun 2026</td><td><span class="status-ip">Draft in progress</span></td></tr>
        <tr><td>Q3 2026</td><td>13 Sep 2026</td><td><span class="status-pending">Not started</span></td></tr>
        <tr><td>Q4 2026</td><td>13 Dec 2026</td><td><span class="status-pending">Not started</span></td></tr>
      </tbody>
    </table>
  </div>

  <footer>OCI Robot Cloud &mdash; Board Governance Tracker &mdash; Cycle 488B</footer>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
if _FASTAPI:
    app = FastAPI(
        title="Board Governance Tracker",
        description="Board meeting management with materials compilation and KPI tracking",
        version="1.0.0",
    )

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return DASHBOARD_HTML

    @app.get("/health")
    def health():
        return JSONResponse({"status": "ok", "service": "board_governance_tracker", "port": PORT})

    @app.get("/governance/board_deck")
    def board_deck(quarter: str = Query(default="Q1 2026", description="Quarter, e.g. Q1 2026")):
        return JSONResponse(get_board_deck(quarter))

    @app.get("/governance/kpis")
    def kpis():
        return JSONResponse(KPIs)


# ---------------------------------------------------------------------------
# Stdlib fallback HTTPServer
# ---------------------------------------------------------------------------
class _FallbackHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _send(self, code: int, content_type: str, body: str | bytes):
        encoded = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)
        if path == "/":
            self._send(200, "text/html; charset=utf-8", DASHBOARD_HTML)
        elif path == "/health":
            self._send(200, "application/json",
                       json.dumps({"status": "ok", "service": "board_governance_tracker", "port": PORT}))
        elif path == "/governance/kpis":
            self._send(200, "application/json", json.dumps(KPIs))
        elif path == "/governance/board_deck":
            quarter = qs.get("quarter", ["Q1 2026"])[0]
            self._send(200, "application/json", json.dumps(get_board_deck(quarter)))
        else:
            self._send(404, "application/json", json.dumps({"error": "not found"}))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    if _FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        print(f"[fallback] Serving on http://0.0.0.0:{PORT}  (fastapi not available)")
        HTTPServer(("0.0.0.0", PORT), _FallbackHandler).serve_forever()
