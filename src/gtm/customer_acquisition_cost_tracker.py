"""customer_acquisition_cost_tracker.py — Cycle 502A (port 10065)
Full-funnel CAC tracking by channel with LTV:CAC ratio.
"""
from __future__ import annotations

from typing import Optional

try:
    from fastapi import FastAPI, Query
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    _HAVE_FASTAPI = True
except ImportError:
    _HAVE_FASTAPI = False

# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

CAC_DATA: dict[str, dict] = {
    "nvidia_referral": {
        "channel": "nvidia_referral",
        "cac": 6000.0,
        "ltv_cac_ratio": 69.2,
        "cac_breakdown": {
            "marketing": 1200,
            "sales": 2800,
            "events": 800,
            "enablement": 1200,
        },
        "trend": "decreasing",
        "notes": "NVIDIA co-sell pipeline — lowest CAC channel",
    },
    "direct_outbound": {
        "channel": "direct_outbound",
        "cac": 14000.0,
        "ltv_cac_ratio": 29.6,
        "cac_breakdown": {
            "marketing": 3000,
            "sales": 7000,
            "events": 2000,
            "enablement": 2000,
        },
        "trend": "stable",
        "notes": "Cold outbound + SDR sequences",
    },
    "conference": {
        "channel": "conference",
        "cac": 18000.0,
        "ltv_cac_ratio": 23.1,
        "cac_breakdown": {
            "marketing": 5000,
            "sales": 6000,
            "events": 5000,
            "enablement": 2000,
        },
        "trend": "increasing",
        "notes": "GTC, AI World, trade shows",
    },
    "inbound_web": {
        "channel": "inbound_web",
        "cac": 9500.0,
        "ltv_cac_ratio": 43.7,
        "cac_breakdown": {
            "marketing": 4500,
            "sales": 3000,
            "events": 0,
            "enablement": 2000,
        },
        "trend": "decreasing",
        "notes": "Demo requests + OCI marketplace",
    },
    "blended": {
        "channel": "blended",
        "cac": 12000.0,
        "ltv_cac_ratio": 34.6,
        "cac_breakdown": {
            "marketing": 3425,
            "sales": 4700,
            "events": 1950,
            "enablement": 1925,
        },
        "trend": "decreasing",
        "notes": "Weighted average across all channels",
    },
}

UNIT_ECONOMICS = {
    "arr": 250000,
    "cac": 12000,
    "ltv": 415000,
    "payback_months": 5.4,
    "ltv_cac_ratio": 34.6,
    "gross_margin_pct": 72,
    "churn_annual_pct": 8,
    "expansion_arr_pct": 15,
}

CAC_TREND = [
    {"quarter": "Q1 2025", "cac": 15000},
    {"quarter": "Q2 2025", "cac": 14200},
    {"quarter": "Q3 2025", "cac": 13500},
    {"quarter": "Q4 2025", "cac": 12800},
    {"quarter": "Q1 2026", "cac": 12000},
    {"quarter": "Target (AI World)", "cac": 8000},
]

# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>CAC Tracker — OCI Robot Cloud GTM</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; padding: 2rem; }
    h1 { color: #C74634; font-size: 1.8rem; margin-bottom: 0.25rem; }
    .subtitle { color: #94a3b8; font-size: 0.9rem; margin-bottom: 2rem; }
    .kpi-row { display: flex; gap: 1.25rem; flex-wrap: wrap; margin-bottom: 2rem; }
    .kpi { background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 1.2rem 1.6rem; flex: 1 1 160px; }
    .kpi .label { color: #94a3b8; font-size: 0.78rem; text-transform: uppercase; letter-spacing: .06em; }
    .kpi .value { color: #38bdf8; font-size: 2rem; font-weight: 700; margin-top: 0.3rem; }
    .kpi .sub { color: #64748b; font-size: 0.8rem; margin-top: 0.2rem; }
    .card { background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 1.5rem; margin-bottom: 1.5rem; }
    .card h2 { color: #38bdf8; font-size: 1.1rem; margin-bottom: 1rem; }
    table { width: 100%; border-collapse: collapse; font-size: 0.88rem; }
    th { color: #94a3b8; text-align: left; padding: 0.5rem 0.75rem; border-bottom: 1px solid #334155; font-weight: 600; }
    td { padding: 0.55rem 0.75rem; border-bottom: 1px solid #1e293b; }
    tr:last-child td { border-bottom: none; }
    .badge { display: inline-block; padding: 0.15rem 0.55rem; border-radius: 999px; font-size: 0.75rem; font-weight: 600; }
    .badge-green  { background: #14532d; color: #4ade80; }
    .badge-yellow { background: #422006; color: #fbbf24; }
    .badge-red    { background: #450a0a; color: #f87171; }
    .badge-blue   { background: #0c4a6e; color: #38bdf8; }
    footer { color: #475569; font-size: 0.78rem; margin-top: 2rem; text-align: center; }
  </style>
</head>
<body>
  <h1>Customer Acquisition Cost Tracker</h1>
  <p class="subtitle">OCI Robot Cloud GTM — Cycle 502A &nbsp;|&nbsp; Port 10065 &nbsp;|&nbsp; Full-Funnel CAC by Channel</p>

  <div class="kpi-row">
    <div class="kpi"><div class="label">Blended CAC</div><div class="value">$12K</div><div class="sub">Q1 2026</div></div>
    <div class="kpi"><div class="label">LTV : CAC</div><div class="value">34.6&#215;</div><div class="sub">target &gt; 3&#215;</div></div>
    <div class="kpi"><div class="label">Payback Period</div><div class="value">5.4 mo</div><div class="sub">best-in-class</div></div>
    <div class="kpi"><div class="label">Target CAC</div><div class="value">$8K</div><div class="sub">by AI World 2026</div></div>
  </div>

  <div class="card">
    <h2>CAC by Channel</h2>
    <!-- Bar chart: horizontal CAC bars, max = $18K -->
    <svg viewBox="0 0 720 230" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:720px;display:block;margin:0 auto 1.25rem">
      <!-- x-axis -->
      <line x1="170" y1="10" x2="170" y2="200" stroke="#334155" stroke-width="1"/>
      <line x1="170" y1="200" x2="715" y2="200" stroke="#334155" stroke-width="1"/>
      <!-- x-axis labels ($0 $6K $12K $18K) -->
      <text x="170" y="215" fill="#64748b" font-size="10" text-anchor="middle">$0</text>
      <text x="354" y="215" fill="#64748b" font-size="10" text-anchor="middle">$6K</text>
      <text x="538" y="215" fill="#64748b" font-size="10" text-anchor="middle">$12K</text>
      <text x="715" y="215" fill="#64748b" font-size="10" text-anchor="middle">$18K</text>
      <!-- guide lines -->
      <line x1="354" y1="10" x2="354" y2="200" stroke="#1e293b" stroke-width="1" stroke-dasharray="4,3"/>
      <line x1="538" y1="10" x2="538" y2="200" stroke="#1e293b" stroke-width="1" stroke-dasharray="4,3"/>
      <!-- NVIDIA $6K — width=(6000/18000)*545=181.7 -->
      <text x="165" y="43"  fill="#94a3b8" font-size="11" text-anchor="end">NVIDIA ref</text>
      <rect x="170" y="28"  width="182" height="26" fill="#38bdf8" rx="3"/>
      <text x="358" y="46" fill="#e2e8f0" font-size="11" font-weight="600">$6K</text>
      <!-- Direct $14K — width=(14000/18000)*545=424 -->
      <text x="165" y="91"  fill="#94a3b8" font-size="11" text-anchor="end">Direct</text>
      <rect x="170" y="76"  width="424" height="26" fill="#C74634" rx="3"/>
      <text x="600" y="94" fill="#e2e8f0" font-size="11" font-weight="600">$14K</text>
      <!-- Conference $18K — width=545 -->
      <text x="165" y="139" fill="#94a3b8" font-size="11" text-anchor="end">Conference</text>
      <rect x="170" y="124" width="545" height="26" fill="#C74634" rx="3" opacity="0.85"/>
      <text x="721" y="142" fill="#e2e8f0" font-size="11" font-weight="600">$18K</text>
      <!-- Inbound $9.5K — width=(9500/18000)*545=287.6 -->
      <text x="165" y="187" fill="#94a3b8" font-size="11" text-anchor="end">Inbound web</text>
      <rect x="170" y="172" width="288" height="26" fill="#38bdf8" rx="3" opacity="0.8"/>
      <text x="464" y="190" fill="#e2e8f0" font-size="11" font-weight="600">$9.5K</text>
    </svg>

    <table>
      <thead><tr><th>Channel</th><th>CAC</th><th>LTV:CAC</th><th>Trend</th><th>Notes</th></tr></thead>
      <tbody>
        <tr><td>NVIDIA Referral</td><td>$6,000</td><td><span class="badge badge-green">69.2&#215;</span></td><td><span class="badge badge-green">&#x2193; Decreasing</span></td><td>Co-sell pipeline — lowest CAC</td></tr>
        <tr><td>Inbound Web</td>    <td>$9,500</td><td><span class="badge badge-green">43.7&#215;</span></td><td><span class="badge badge-green">&#x2193; Decreasing</span></td><td>Demo requests + OCI marketplace</td></tr>
        <tr><td>Blended</td>        <td>$12,000</td><td><span class="badge badge-blue">34.6&#215;</span></td><td><span class="badge badge-green">&#x2193; Decreasing</span></td><td>Weighted average all channels</td></tr>
        <tr><td>Direct Outbound</td><td>$14,000</td><td><span class="badge badge-yellow">29.6&#215;</span></td><td><span class="badge badge-yellow">&#x2192; Stable</span></td><td>Cold outbound + SDR sequences</td></tr>
        <tr><td>Conference</td>     <td>$18,000</td><td><span class="badge badge-red">23.1&#215;</span></td><td><span class="badge badge-red">&#x2191; Increasing</span></td><td>GTC, AI World, trade shows</td></tr>
      </tbody>
    </table>
  </div>

  <div class="card">
    <h2>CAC Trend &amp; Target</h2>
    <svg viewBox="0 0 720 180" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:720px;display:block;margin:0 auto 1rem">
      <!-- axes -->
      <line x1="50" y1="10" x2="50"  y2="150" stroke="#334155" stroke-width="1"/>
      <line x1="50" y1="150" x2="710" y2="150" stroke="#334155" stroke-width="1"/>
      <!-- y labels: $8K=130, $10K=110, $12K=90, $14K=70, $16K=50 -->
      <text x="45" y="133" fill="#64748b" font-size="10" text-anchor="end">$8K</text>
      <text x="45" y="113" fill="#64748b" font-size="10" text-anchor="end">$10K</text>
      <text x="45" y="93"  fill="#64748b" font-size="10" text-anchor="end">$12K</text>
      <text x="45" y="73"  fill="#64748b" font-size="10" text-anchor="end">$14K</text>
      <text x="45" y="53"  fill="#64748b" font-size="10" text-anchor="end">$16K</text>
      <!-- guideline $8K target -->
      <line x1="50" y1="130" x2="710" y2="130" stroke="#4ade80" stroke-width="1" stroke-dasharray="5,3" opacity="0.5"/>
      <!-- data points (x spacing ~120px for 6 points from x=80): Q1=80,Q2=200,Q3=320,Q4=440,Q1-26=560,Target=680 -->
      <!-- y = 150 - (cac-8000)/8000 * 140  (range 8K-16K mapped to 0-140px) -->
      <!-- Q1 2025: 15000 → y=150-122.5=27.5 -->
      <!-- Q2 2025: 14200 → y=150-108.5=41.5 -->
      <!-- Q3 2025: 13500 → y=150-96.25=53.75 -->
      <!-- Q4 2025: 12800 → y=150-84=66 -->
      <!-- Q1 2026: 12000 → y=150-70=80 -->
      <!-- Target:   8000 → y=150-0=150 → pin to 130 (at $8K line) -->
      <polyline points="80,27.5 200,41.5 320,53.75 440,66 560,80 680,130"
                fill="none" stroke="#38bdf8" stroke-width="2.5" stroke-linejoin="round"/>
      <circle cx="80"  cy="27.5"  r="5" fill="#38bdf8"/>
      <circle cx="200" cy="41.5"  r="5" fill="#38bdf8"/>
      <circle cx="320" cy="53.75" r="5" fill="#38bdf8"/>
      <circle cx="440" cy="66"    r="5" fill="#38bdf8"/>
      <circle cx="560" cy="80"    r="5" fill="#38bdf8"/>
      <circle cx="680" cy="130"   r="6" fill="#4ade80" stroke="#0f172a" stroke-width="2"/>
      <!-- x labels -->
      <text x="80"  y="165" fill="#94a3b8" font-size="9" text-anchor="middle">Q1 '25</text>
      <text x="200" y="165" fill="#94a3b8" font-size="9" text-anchor="middle">Q2 '25</text>
      <text x="320" y="165" fill="#94a3b8" font-size="9" text-anchor="middle">Q3 '25</text>
      <text x="440" y="165" fill="#94a3b8" font-size="9" text-anchor="middle">Q4 '25</text>
      <text x="560" y="165" fill="#94a3b8" font-size="9" text-anchor="middle">Q1 '26</text>
      <text x="680" y="165" fill="#4ade80" font-size="9" text-anchor="middle" font-weight="600">AI World</text>
      <text x="680" y="124" fill="#4ade80" font-size="9" text-anchor="middle">$8K target</text>
    </svg>
  </div>

  <div class="card">
    <h2>Unit Economics</h2>
    <table>
      <thead><tr><th>Metric</th><th>Value</th><th>Notes</th></tr></thead>
      <tbody>
        <tr><td>ARR per customer</td>       <td>$250,000</td><td>avg contract value</td></tr>
        <tr><td>Blended CAC</td>            <td>$12,000</td> <td>Q1 2026 actuals</td></tr>
        <tr><td>Customer LTV</td>           <td>$415,000</td><td>based on 8% churn, 15% expansion</td></tr>
        <tr><td>LTV : CAC</td>              <td><span class="badge badge-green">34.6&#215;</span></td><td>well above 3&#215; benchmark</td></tr>
        <tr><td>Payback period</td>         <td>5.4 months</td><td>gross margin 72%</td></tr>
        <tr><td>Gross margin</td>           <td>72%</td>      <td>infra + support included</td></tr>
      </tbody>
    </table>
  </div>

  <footer>OCI Robot Cloud &mdash; CAC Tracker &mdash; Port 10065 &mdash; Cycle 502A</footer>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

if _HAVE_FASTAPI:
    app = FastAPI(
        title="Customer Acquisition Cost Tracker",
        description="Full-funnel CAC tracking by channel with LTV:CAC ratio",
        version="1.0.0",
    )

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return HTMLResponse(content=DASHBOARD_HTML)

    @app.get("/health")
    async def health():
        return JSONResponse({"status": "ok", "service": "customer_acquisition_cost_tracker", "port": 10065, "cycle": "502A"})

    @app.get("/gtm/cac")
    async def get_cac(channel: Optional[str] = Query(default=None, description="Channel name (e.g. nvidia_referral, blended)")):
        if channel is None:
            return JSONResponse({"channels": list(CAC_DATA.keys()), "data": CAC_DATA})
        ch = CAC_DATA.get(channel)
        if ch is None:
            return JSONResponse({"error": f"Unknown channel '{channel}'. Available: {list(CAC_DATA.keys())}"}, status_code=404)
        return JSONResponse(ch)

    @app.get("/gtm/unit_economics")
    async def get_unit_economics():
        return JSONResponse(UNIT_ECONOMICS)

else:
    import json as _json
    from http.server import BaseHTTPRequestHandler, HTTPServer
    from urllib.parse import urlparse, parse_qs

    class Handler(BaseHTTPRequestHandler):
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
            qs = parse_qs(parsed.query)
            if parsed.path == "/":
                self._send(200, "text/html", DASHBOARD_HTML)
            elif parsed.path == "/health":
                self._send(200, "application/json", _json.dumps({"status": "ok", "service": "customer_acquisition_cost_tracker", "port": 10065}))
            elif parsed.path == "/gtm/cac":
                channel = qs.get("channel", [None])[0]
                if channel is None:
                    self._send(200, "application/json", _json.dumps({"channels": list(CAC_DATA.keys())}))
                else:
                    ch = CAC_DATA.get(channel)
                    if ch:
                        self._send(200, "application/json", _json.dumps(ch))
                    else:
                        self._send(404, "application/json", _json.dumps({"error": f"Unknown channel '{channel}'"}))
            elif parsed.path == "/gtm/unit_economics":
                self._send(200, "application/json", _json.dumps(UNIT_ECONOMICS))
            else:
                self._send(404, "application/json", _json.dumps({"error": "not found"}))


if __name__ == "__main__":
    if _HAVE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=10065)
    else:
        server = HTTPServer(("0.0.0.0", 10065), Handler)
        print("CAC Tracker (stdlib) running on port 10065")
        server.serve_forever()
