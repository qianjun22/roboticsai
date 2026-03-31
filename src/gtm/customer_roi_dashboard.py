"""Customer ROI Dashboard — port 10045

Per-customer ROI visualization with payback period and savings breakdown.
Portfolio: Machina 3.8× ($312K, 97d), Verdant 2.1× ($174K, 173d), Helix 1.7× ($143K, 215d).
"""

import json
import random
from datetime import datetime
from urllib.parse import urlparse, parse_qs

try:
    from fastapi import FastAPI, Query
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    _FASTAPI = True
except ImportError:
    _FASTAPI = False
    from http.server import BaseHTTPRequestHandler, HTTPServer

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
PORT = 10045
SERVICE_NAME = "customer_roi_dashboard"
VERSION = "1.0.0"

CUSTOMER_DATA = {
    "machina": {
        "name": "Machina Robotics",
        "roi_multiple": 3.8,
        "annual_savings_usd": 312000,
        "payback_days": 97,
        "sr_before": 54.0,
        "sr_after": 88.0,
    },
    "verdant": {
        "name": "Verdant Automation",
        "roi_multiple": 2.1,
        "annual_savings_usd": 174000,
        "payback_days": 173,
        "sr_before": 61.0,
        "sr_after": 84.0,
    },
    "helix": {
        "name": "Helix Systems",
        "roi_multiple": 1.7,
        "annual_savings_usd": 143000,
        "payback_days": 215,
        "sr_before": 67.0,
        "sr_after": 82.0,
    },
}

PORTFOLIO_SUMMARY = {
    "avg_roi_multiple": 2.5,
    "avg_payback_days": 162,
    "avg_annual_savings_usd": 210000,
    "customer_count": len(CUSTOMER_DATA),
    "customers": list(CUSTOMER_DATA.keys()),
}

# ---------------------------------------------------------------------------
# HTML Dashboard
# ---------------------------------------------------------------------------
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Customer ROI Dashboard — OCI Robot Cloud</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; min-height: 100vh; }
    header { background: #1e293b; border-bottom: 2px solid #C74634; padding: 1.2rem 2rem;
             display: flex; align-items: center; gap: 1rem; }
    header h1 { font-size: 1.4rem; font-weight: 700; color: #f8fafc; }
    header span.badge { background: #C74634; color: #fff; font-size: 0.72rem;
                        padding: 0.2rem 0.6rem; border-radius: 999px; font-weight: 600; }
    .subtitle { color: #94a3b8; font-size: 0.82rem; margin-top: 0.2rem; }
    main { max-width: 1100px; margin: 2rem auto; padding: 0 1.5rem; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 1.2rem; margin-bottom: 2rem; }
    .card { background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 1.4rem; }
    .card .label { font-size: 0.75rem; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 0.5rem; }
    .card .value { font-size: 2rem; font-weight: 700; color: #38bdf8; }
    .card .value.orange { color: #fb923c; }
    .card .value.green { color: #4ade80; }
    .card .sub { font-size: 0.8rem; color: #64748b; margin-top: 0.3rem; }
    section.chart-section { background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 1.6rem; margin-bottom: 2rem; }
    section.chart-section h2 { font-size: 1rem; font-weight: 600; color: #f1f5f9; margin-bottom: 1.2rem; }
    .bar-label { font-size: 0.78rem; fill: #94a3b8; }
    .bar-value { font-size: 0.82rem; fill: #e2e8f0; font-weight: 600; }
    .axis-line { stroke: #334155; stroke-width: 1; }
    table { width: 100%; border-collapse: collapse; }
    thead th { background: #0f172a; color: #94a3b8; font-size: 0.75rem; text-transform: uppercase;
               letter-spacing: 0.05em; padding: 0.7rem 1rem; text-align: left; }
    tbody tr { border-top: 1px solid #334155; }
    tbody td { padding: 0.8rem 1rem; font-size: 0.88rem; }
    tbody tr:hover td { background: #0f172a44; }
    .pill { display: inline-block; padding: 0.15rem 0.55rem; border-radius: 999px; font-size: 0.72rem; font-weight: 600; }
    .pill.blue { background: #0c4a6e; color: #38bdf8; }
    .pill.green { background: #052e16; color: #4ade80; }
    .pill.orange { background: #431407; color: #fb923c; }
    .sr-bar-bg { display: inline-block; background: #334155; border-radius: 4px; width: 120px; height: 8px; vertical-align: middle; margin-left: 6px; }
    .sr-bar-fill { display: inline-block; background: #38bdf8; border-radius: 4px; height: 8px; }
    footer { text-align: center; color: #475569; font-size: 0.75rem; padding: 2rem; }
  </style>
</head>
<body>
<header>
  <div>
    <h1>Customer ROI Dashboard <span class="badge">port 10045</span></h1>
    <div class="subtitle">Per-customer ROI · payback period · savings breakdown</div>
  </div>
</header>
<main>
  <!-- Portfolio KPIs -->
  <div class="grid">
    <div class="card">
      <div class="label">Portfolio Avg ROI</div>
      <div class="value green">2.5×</div>
      <div class="sub">across 3 design partners</div>
    </div>
    <div class="card">
      <div class="label">Avg Payback Period</div>
      <div class="value">162 days</div>
      <div class="sub">~5.4 months to breakeven</div>
    </div>
    <div class="card">
      <div class="label">Avg Annual Savings</div>
      <div class="value orange">$210K</div>
      <div class="sub">per customer / year</div>
    </div>
    <div class="card">
      <div class="label">Best ROI</div>
      <div class="value green">3.8×</div>
      <div class="sub">Machina — 97 day payback</div>
    </div>
  </div>

  <!-- ROI bar chart -->
  <section class="chart-section">
    <h2>ROI Multiple by Customer</h2>
    <svg viewBox="0 0 700 240" xmlns="http://www.w3.org/2000/svg" width="100%">
      <!-- axes -->
      <line x1="90" y1="20" x2="90" y2="190" class="axis-line" />
      <line x1="90" y1="190" x2="680" y2="190" class="axis-line" />
      <!-- y-axis labels (0–4×) -->
      <text x="82" y="194" text-anchor="end" class="bar-label">0×</text>
      <text x="82" y="147" text-anchor="end" class="bar-label">1×</text>
      <text x="82" y="100" text-anchor="end" class="bar-label">2×</text>
      <text x="82" y="53" text-anchor="end" class="bar-label">3×</text>
      <text x="82" y="24" text-anchor="end" class="bar-label">4×</text>
      <!-- gridlines -->
      <line x1="90" y1="147" x2="680" y2="147" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,3" />
      <line x1="90" y1="100" x2="680" y2="100" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,3" />
      <line x1="90" y1="53" x2="680" y2="53" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,3" />

      <!-- Machina 3.8× → bar height = 3.8/4*170=161.5 → y=28.5 -->
      <rect x="115" y="29" width="100" height="161" rx="4" fill="#4ade80" opacity="0.85" />
      <text x="165" y="23" text-anchor="middle" class="bar-value">3.8×</text>
      <text x="165" y="210" text-anchor="middle" class="bar-label">Machina</text>

      <!-- Verdant 2.1× → height = 2.1/4*170=89.25 → y=100.75 -->
      <rect x="285" y="101" width="100" height="89" rx="4" fill="#38bdf8" opacity="0.85" />
      <text x="335" y="95" text-anchor="middle" class="bar-value">2.1×</text>
      <text x="335" y="210" text-anchor="middle" class="bar-label">Verdant</text>

      <!-- Helix 1.7× → height = 1.7/4*170=72.25 → y=117.75 -->
      <rect x="455" y="118" width="100" height="72" rx="4" fill="#C74634" opacity="0.85" />
      <text x="505" y="112" text-anchor="middle" class="bar-value">1.7×</text>
      <text x="505" y="210" text-anchor="middle" class="bar-label">Helix</text>
    </svg>
  </section>

  <!-- Customer table -->
  <section class="chart-section">
    <h2>Customer ROI Breakdown</h2>
    <table>
      <thead>
        <tr>
          <th>Customer</th><th>ROI Multiple</th><th>Annual Savings</th>
          <th>Payback Period</th><th>SR Lift</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td><strong>Machina Robotics</strong></td>
          <td><span class="pill green">3.8×</span></td>
          <td>$312K / yr</td>
          <td>97 days</td>
          <td>
            54% → 88%
            <span class="sr-bar-bg"><span class="sr-bar-fill" style="width:88%"></span></span>
          </td>
        </tr>
        <tr>
          <td><strong>Verdant Automation</strong></td>
          <td><span class="pill blue">2.1×</span></td>
          <td>$174K / yr</td>
          <td>173 days</td>
          <td>
            61% → 84%
            <span class="sr-bar-bg"><span class="sr-bar-fill" style="width:84%"></span></span>
          </td>
        </tr>
        <tr>
          <td><strong>Helix Systems</strong></td>
          <td><span class="pill orange">1.7×</span></td>
          <td>$143K / yr</td>
          <td>215 days</td>
          <td>
            67% → 82%
            <span class="sr-bar-bg"><span class="sr-bar-fill" style="width:82%"></span></span>
          </td>
        </tr>
      </tbody>
    </table>
  </section>
</main>
<footer>OCI Robot Cloud &mdash; Customer ROI Dashboard v1.0.0 &mdash; port 10045</footer>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# Health payload
# ---------------------------------------------------------------------------
def _health_payload():
    return {
        "service": SERVICE_NAME,
        "version": VERSION,
        "port": PORT,
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "customer_count": len(CUSTOMER_DATA),
    }

# ---------------------------------------------------------------------------
# ROI lookup helper
# ---------------------------------------------------------------------------
def _get_roi(customer_id: str):
    key = customer_id.lower().strip()
    # partial match
    for k, v in CUSTOMER_DATA.items():
        if k.startswith(key) or key in k:
            return v
    return None


# ===========================================================================
# FastAPI branch
# ===========================================================================
if _FASTAPI:
    app = FastAPI(
        title="Customer ROI Dashboard",
        description="Per-customer ROI visualization with payback period and savings breakdown.",
        version=VERSION,
    )

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return HTMLResponse(content=DASHBOARD_HTML)

    @app.get("/health")
    def health():
        return JSONResponse(content=_health_payload())

    @app.get("/customers/roi_dashboard")
    def roi_dashboard(customer_id: str = Query(..., description="Customer identifier (e.g. machina, verdant, helix)")):
        record = _get_roi(customer_id)
        if record is None:
            return JSONResponse(
                status_code=404,
                content={"error": f"Customer '{customer_id}' not found.", "available": list(CUSTOMER_DATA.keys())},
            )
        return JSONResponse(content={
            "customer_id": customer_id,
            "roi_multiple": record["roi_multiple"],
            "annual_savings_usd": record["annual_savings_usd"],
            "payback_days": record["payback_days"],
            "sr_before": record["sr_before"],
            "sr_after": record["sr_after"],
        })

    @app.get("/customers/portfolio_roi")
    def portfolio_roi():
        return JSONResponse(content=PORTFOLIO_SUMMARY)

# ===========================================================================
# HTTPServer fallback
# ===========================================================================
else:
    import json as _json
    from urllib.parse import urlparse as _urlparse, parse_qs as _parse_qs

    class _Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass

        def _send(self, code, content_type, body):
            if isinstance(body, str):
                body = body.encode()
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            parsed = _urlparse(self.path)
            path = parsed.path
            qs = _parse_qs(parsed.query)

            if path == "/":
                self._send(200, "text/html", DASHBOARD_HTML)
            elif path == "/health":
                self._send(200, "application/json", _json.dumps(_health_payload()))
            elif path == "/customers/roi_dashboard":
                cid = qs.get("customer_id", [None])[0]
                if not cid:
                    self._send(422, "application/json",
                               _json.dumps({"error": "customer_id query param required"}))
                    return
                record = _get_roi(cid)
                if record is None:
                    self._send(404, "application/json",
                               _json.dumps({"error": f"Customer '{cid}' not found.",
                                            "available": list(CUSTOMER_DATA.keys())}))
                    return
                self._send(200, "application/json", _json.dumps({
                    "customer_id": cid,
                    "roi_multiple": record["roi_multiple"],
                    "annual_savings_usd": record["annual_savings_usd"],
                    "payback_days": record["payback_days"],
                    "sr_before": record["sr_before"],
                    "sr_after": record["sr_after"],
                }))
            elif path == "/customers/portfolio_roi":
                self._send(200, "application/json", _json.dumps(PORTFOLIO_SUMMARY))
            else:
                self._send(404, "application/json", _json.dumps({"error": "not found"}))


# ===========================================================================
# Entry point
# ===========================================================================
if __name__ == "__main__":
    if _FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        print(f"[{SERVICE_NAME}] FastAPI not available — starting stdlib HTTPServer on port {PORT}")
        server = HTTPServer(("0.0.0.0", PORT), _Handler)
        print(f"[{SERVICE_NAME}] Listening on http://0.0.0.0:{PORT}")
        server.serve_forever()
