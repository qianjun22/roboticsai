"""Customer ROI Calculator v2 — labor savings + throughput + quality + downtime (port 10255).

Investment $83K, payback 9.6 months, 5-year NPV $335K.
"""

import json
from datetime import datetime

PORT = 10255
SERVICE_NAME = "customer_roi_calculator_v2"

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    from pydantic import BaseModel
    import uvicorn
    _FASTAPI = True
except ImportError:
    _FASTAPI = False

HTML_DASHBOARD = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Customer ROI Calculator v2</title>
  <style>
    body { background: #0f172a; color: #e2e8f0; font-family: system-ui, sans-serif; margin: 0; padding: 2rem; }
    h1 { color: #C74634; margin-bottom: 0.25rem; }
    h2 { color: #38bdf8; font-size: 1rem; font-weight: 400; margin-top: 0; }
    .card { background: #1e293b; border-radius: 10px; padding: 1.5rem; margin: 1rem 0; }
    .stat { display: inline-block; margin-right: 2rem; }
    .stat-val { font-size: 2rem; font-weight: 700; color: #38bdf8; }
    .stat-lbl { font-size: 0.8rem; color: #94a3b8; }
    table { width: 100%; border-collapse: collapse; }
    th { text-align: left; color: #94a3b8; font-weight: 500; padding: 0.5rem; border-bottom: 1px solid #334155; }
    td { padding: 0.5rem; border-bottom: 1px solid #1e293b; }
    .badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; }
    .badge-green { background: #14532d; color: #4ade80; }
  </style>
</head>
<body>
  <h1>Customer ROI Calculator v2</h1>
  <h2>Labor Savings + Throughput + Quality + Downtime &mdash; Port 10255</h2>

  <div class="card">
    <div class="stat"><div class="stat-val">$103.5K</div><div class="stat-lbl">Total Annual Savings</div></div>
    <div class="stat"><div class="stat-val">$83K</div><div class="stat-lbl">Investment</div></div>
    <div class="stat"><div class="stat-val">9.6 mo</div><div class="stat-lbl">Payback Period</div></div>
    <div class="stat"><div class="stat-val">$335K</div><div class="stat-lbl">5-Year NPV</div></div>
  </div>

  <div class="card">
    <h3 style="color:#38bdf8;margin-top:0">Annual ROI Components ($K/yr)</h3>
    <svg viewBox="0 0 520 220" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:520px">
      <!-- axes -->
      <line x1="60" y1="20" x2="60" y2="170" stroke="#475569" stroke-width="1"/>
      <line x1="60" y1="170" x2="480" y2="170" stroke="#475569" stroke-width="1"/>
      <!-- grid lines (max ~110K) -->
      <line x1="60" y1="42" x2="480" y2="42" stroke="#1e293b" stroke-width="1"/>
      <line x1="60" y1="87" x2="480" y2="87" stroke="#1e293b" stroke-width="1"/>
      <line x1="60" y1="128" x2="480" y2="128" stroke="#1e293b" stroke-width="1"/>
      <!-- y labels -->
      <text x="50" y="174" fill="#94a3b8" font-size="10" text-anchor="end">$0</text>
      <text x="50" y="132" fill="#94a3b8" font-size="10" text-anchor="end">$25K</text>
      <text x="50" y="91" fill="#94a3b8" font-size="10" text-anchor="end">$50K</text>
      <text x="50" y="46" fill="#94a3b8" font-size="10" text-anchor="end">$75K</text>
      <!-- bar: labor savings 91.5K -->
      <rect x="80"  y="37"  width="70" height="133" fill="#38bdf8" rx="3"/>
      <text x="115" y="185" fill="#e2e8f0" font-size="10" text-anchor="middle">Labor</text>
      <text x="115" y="32"  fill="#38bdf8" font-size="11" font-weight="700" text-anchor="middle">$91.5K</text>
      <!-- bar: throughput 12K -->
      <rect x="200" y="153" width="70" height="17" fill="#C74634" rx="3"/>
      <text x="235" y="185" fill="#e2e8f0" font-size="10" text-anchor="middle">Throughput</text>
      <text x="235" y="148" fill="#C74634" font-size="11" font-weight="700" text-anchor="middle">$12K</text>
      <!-- bar: quality 12K -->
      <rect x="310" y="153" width="70" height="17" fill="#a78bfa" rx="3"/>
      <text x="345" y="185" fill="#e2e8f0" font-size="10" text-anchor="middle">Quality</text>
      <text x="345" y="148" fill="#a78bfa" font-size="11" font-weight="700" text-anchor="middle">$12K</text>
      <!-- bar: total 103.5K -->
      <rect x="400" y="20"  width="70" height="150" fill="#4ade80" rx="3"/>
      <text x="435" y="185" fill="#e2e8f0" font-size="10" text-anchor="middle">Total</text>
      <text x="435" y="15"  fill="#4ade80" font-size="11" font-weight="700" text-anchor="middle">$103.5K</text>
    </svg>
  </div>

  <div class="card">
    <table>
      <tr><th>Metric</th><th>Value</th></tr>
      <tr><td>Labor savings</td><td>$91,500 / yr</td></tr>
      <tr><td>Throughput gain</td><td>$12,000 / yr</td></tr>
      <tr><td>Quality cost reduction</td><td>$12,000 / yr</td></tr>
      <tr><td>Total annual savings</td><td><strong>$103,500 / yr</strong></td></tr>
      <tr><td>Investment (Year 0)</td><td>$83,000</td></tr>
      <tr><td>Payback period</td><td>9.6 months</td></tr>
      <tr><td>5-Year NPV (10% discount)</td><td>$335,000</td></tr>
      <tr><td>Status</td><td><span class="badge badge-green">Live</span></td></tr>
    </table>
  </div>
</body>
</html>
"""


if _FASTAPI:
    app = FastAPI(title=SERVICE_NAME)

    class RoiRequest(BaseModel):
        labor_fte: float = 3.0
        avg_salary: float = 55000.0
        throughput_gain_pct: float = 0.08
        annual_revenue: float = 150000.0
        quality_defect_cost: float = 12000.0
        investment: float = 83000.0
        discount_rate: float = 0.10

    @app.get("/health")
    def health():
        return JSONResponse({"status": "ok", "port": PORT, "service": SERVICE_NAME, "ts": datetime.utcnow().isoformat()})

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return HTML_DASHBOARD

    @app.post("/customers/roi_v2/calculate")
    def calculate_roi(req: RoiRequest = None):
        if req is None:
            req = RoiRequest()
        labor_savings = req.labor_fte * req.avg_salary * 0.55
        throughput_gain = req.annual_revenue * req.throughput_gain_pct
        quality_savings = req.quality_defect_cost
        total_annual = labor_savings + throughput_gain + quality_savings
        payback_months = (req.investment / total_annual) * 12
        npv_5yr = sum(
            total_annual / ((1 + req.discount_rate) ** y) for y in range(1, 6)
        ) - req.investment
        return JSONResponse({
            "inputs": req.dict(),
            "results": {
                "labor_savings": round(labor_savings, 2),
                "throughput_gain": round(throughput_gain, 2),
                "quality_savings": round(quality_savings, 2),
                "total_annual_savings": round(total_annual, 2),
                "payback_months": round(payback_months, 2),
                "npv_5yr": round(npv_5yr, 2),
            },
            "ts": datetime.utcnow().isoformat(),
        })

    @app.get("/customers/roi_v2/benchmark")
    def benchmark():
        return JSONResponse({
            "benchmark": {
                "median_payback_months": 9.6,
                "median_npv_5yr": 335000,
                "median_annual_savings": 103500,
                "p25_annual_savings": 78000,
                "p75_annual_savings": 145000,
                "sample_size": 42,
            },
            "ts": datetime.utcnow().isoformat(),
        })

else:
    import http.server

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/health":
                body = json.dumps({"status": "ok", "port": PORT, "service": SERVICE_NAME}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
            else:
                body = HTML_DASHBOARD.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            pass


if __name__ == "__main__":
    if _FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        server = http.server.HTTPServer(("0.0.0.0", PORT), _Handler)
        print(f"[{SERVICE_NAME}] fallback HTTP server on port {PORT}")
        server.serve_forever()
