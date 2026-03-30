# Revenue Operations Dashboard — port 8923
# RevOps end-to-end: MRR, AR, DSO, collections, upsell pipeline

import math
import random

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Revenue Operations Dashboard</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; padding: 24px; }
  h1 { color: #C74634; font-size: 2rem; margin-bottom: 4px; }
  .subtitle { color: #94a3b8; font-size: 0.95rem; margin-bottom: 28px; }
  h2 { color: #38bdf8; font-size: 1.15rem; margin-bottom: 14px; }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 28px; }
  .card { background: #1e293b; border-radius: 10px; padding: 20px; }
  .card .label { font-size: 0.78rem; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 6px; }
  .card .value { font-size: 1.65rem; font-weight: 700; color: #f1f5f9; }
  .card .delta { font-size: 0.82rem; margin-top: 4px; }
  .green { color: #4ade80; }
  .red { color: #f87171; }
  .amber { color: #fbbf24; }
  .chart-wrap { background: #1e293b; border-radius: 10px; padding: 20px; margin-bottom: 28px; }
  svg { width: 100%; }
  table { width: 100%; border-collapse: collapse; font-size: 0.88rem; }
  th { text-align: left; padding: 10px 12px; background: #0f172a; color: #94a3b8; font-weight: 600; text-transform: uppercase; font-size: 0.75rem; letter-spacing: 0.06em; }
  td { padding: 10px 12px; border-bottom: 1px solid #334155; }
  tr:last-child td { border-bottom: none; }
  .badge { display: inline-block; padding: 2px 10px; border-radius: 20px; font-size: 0.75rem; font-weight: 600; }
  .badge-paid { background: #14532d; color: #86efac; }
  .badge-overdue { background: #7f1d1d; color: #fca5a5; }
  .badge-pending { background: #78350f; color: #fde68a; }
  .badge-upsell { background: #1e3a5f; color: #93c5fd; }
  footer { color: #475569; font-size: 0.78rem; margin-top: 32px; text-align: center; }
</style>
</head>
<body>
<h1>Revenue Operations Dashboard</h1>
<p class="subtitle">RevOps end-to-end &mdash; MRR, AR, DSO, collections efficiency &mdash; port 8923</p>

<div class="grid">
  <div class="card"><div class="label">MRR Recognized</div><div class="value">$35,240</div><div class="delta green">&uarr; +8.4% MoM</div></div>
  <div class="card"><div class="label">Accounts Receivable</div><div class="value">$12,400</div><div class="delta amber">3 open invoices</div></div>
  <div class="card"><div class="label">DSO</div><div class="value">23 days</div><div class="delta green">Target &le; 30d &check;</div></div>
  <div class="card"><div class="label">Overdue AR</div><div class="value">$4,200</div><div class="delta red">Machina &mdash; 7d overdue</div></div>
  <div class="card"><div class="label">Upsell Pipeline</div><div class="value">$47,000</div><div class="delta" style="color:#93c5fd">3 active opportunities</div></div>
  <div class="card"><div class="label">Collections Rate</div><div class="value">94.2%</div><div class="delta green">+1.1pp vs prior mo</div></div>
  <div class="card"><div class="label">Churn Risk</div><div class="value">1 acct</div><div class="delta red">Machina &mdash; escalate</div></div>
  <div class="card"><div class="label">NRR</div><div class="value">112%</div><div class="delta green">Expansion &gt; churn</div></div>
</div>

<div class="chart-wrap">
  <h2>Cash Flow Waterfall (Current Month, $k)</h2>
  <svg viewBox="0 0 760 240" xmlns="http://www.w3.org/2000/svg">
    <!-- axes -->
    <line x1="60" y1="20" x2="60" y2="195" stroke="#334155" stroke-width="1.5"/>
    <line x1="60" y1="195" x2="740" y2="195" stroke="#334155" stroke-width="1.5"/>
    <!-- zero line at y=195, scale: $5k = 20px -->
    <!-- Contracted MRR $35.24k -> 141px green from bottom: y=195-141=54 -->
    <rect x="80" y="54" width="85" height="141" fill="#22c55e" rx="4"/>
    <text x="122" y="48" fill="#86efac" font-size="11" text-anchor="middle">$35.24k</text>
    <!-- Deferred: -$3.2k (portion deferred, shown as negative step) y=195-141+12.8=66.8 -> drop from 54 by 12.8 -->
    <rect x="185" y="54" width="85" height="12.8" fill="#ef4444" rx="4"/>
    <text x="227" y="48" fill="#fca5a5" font-size="11" text-anchor="middle">-$3.2k</text>
    <!-- Recognized: $32.04k base, floating bar from 66.8 up by 128.2 -->
    <rect x="290" y="66.8" width="85" height="128.2" fill="#22c55e" rx="4"/>
    <text x="332" y="61" fill="#86efac" font-size="11" text-anchor="middle">$32.0k</text>
    <!-- Collections +$28.4k -->
    <!-- AR opening $12.4k, collected $28.4k, floating -->
    <rect x="395" y="81.4" width="85" height="113.6" fill="#38bdf8" rx="4"/>
    <text x="437" y="76" fill="#93c5fd" font-size="11" text-anchor="middle">+$28.4k</text>
    <!-- Overdue AR -$4.2k: drop -->
    <rect x="500" y="81.4" width="85" height="16.8" fill="#f59e0b" rx="4"/>
    <text x="542" y="76" fill="#fde68a" font-size="11" text-anchor="middle">-$4.2k</text>
    <!-- Net cash ending $56.2k -> 224.8px but capped to chart: show relative to 100px max = scale $0.25k/px -->
    <!-- For visual clarity, just show proportional end bar at 140px (=$35k) -->
    <rect x="605" y="55" width="85" height="140" fill="#a855f7" rx="4"/>
    <text x="647" y="49" fill="#d8b4fe" font-size="11" text-anchor="middle">$56.2k</text>
    <!-- x labels -->
    <text x="122" y="210" fill="#e2e8f0" font-size="11" text-anchor="middle">Contracted</text>
    <text x="122" y="222" fill="#94a3b8" font-size="10" text-anchor="middle">MRR</text>
    <text x="227" y="210" fill="#e2e8f0" font-size="11" text-anchor="middle">Deferred</text>
    <text x="332" y="210" fill="#e2e8f0" font-size="11" text-anchor="middle">Recognized</text>
    <text x="437" y="210" fill="#e2e8f0" font-size="11" text-anchor="middle">Collections</text>
    <text x="542" y="210" fill="#e2e8f0" font-size="11" text-anchor="middle">Overdue AR</text>
    <text x="647" y="210" fill="#e2e8f0" font-size="11" text-anchor="middle">Net Cash</text>
    <text x="647" y="222" fill="#94a3b8" font-size="10" text-anchor="middle">Position</text>
  </svg>
</div>

<div class="chart-wrap">
  <h2>Collections Efficiency Trend (past 8 months, %)</h2>
  <svg viewBox="0 0 760 200" xmlns="http://www.w3.org/2000/svg">
    <!-- axes -->
    <line x1="60" y1="20" x2="60" y2="165" stroke="#334155" stroke-width="1.5"/>
    <line x1="60" y1="165" x2="740" y2="165" stroke="#334155" stroke-width="1.5"/>
    <!-- grid at 70%, 80%, 90%, 100% -->
    <!-- scale: 70%=165, 100%=20 → 1%=1.633px -->
    <line x1="60" y1="165" x2="740" y2="165" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,4"/>
    <line x1="60" y1="116.3" x2="740" y2="116.3" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,4"/>
    <line x1="60" y1="83.3" x2="740" y2="83.3" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,4"/>
    <line x1="60" y1="20" x2="740" y2="20" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,4"/>
    <text x="52" y="168" fill="#94a3b8" font-size="10" text-anchor="end">70%</text>
    <text x="52" y="119" fill="#94a3b8" font-size="10" text-anchor="end">80%</text>
    <text x="52" y="86" fill="#94a3b8" font-size="10" text-anchor="end">85%</text>
    <text x="52" y="23" fill="#94a3b8" font-size="10" text-anchor="end">100%</text>
    <!-- data points: months Aug-Mar, values 83,85,87,88,91,90,93.1,94.2 -->
    <!-- y = 165 - (val-70)*1.633 -->
    <!-- Aug: 83 -> 165-21.2=143.8; Sep: 85->132.2; Oct:87->120.6; Nov:88->114.8; Dec:91->98.6; Jan:90->100.2; Feb:93.1->75.4; Mar:94.2->73.5 -->
    <polyline
      points="90,143.8 195,132.2 300,120.6 380,114.8 460,98.6 540,100.2 640,75.4 720,73.5"
      fill="none" stroke="#38bdf8" stroke-width="2.5" stroke-linejoin="round"/>
    <!-- area fill -->
    <polygon
      points="90,143.8 195,132.2 300,120.6 380,114.8 460,98.6 540,100.2 640,75.4 720,73.5 720,165 90,165"
      fill="#38bdf820"/>
    <!-- dots -->
    <circle cx="90" cy="143.8" r="4" fill="#38bdf8"/>
    <circle cx="195" cy="132.2" r="4" fill="#38bdf8"/>
    <circle cx="300" cy="120.6" r="4" fill="#38bdf8"/>
    <circle cx="380" cy="114.8" r="4" fill="#38bdf8"/>
    <circle cx="460" cy="98.6" r="4" fill="#38bdf8"/>
    <circle cx="540" cy="100.2" r="4" fill="#38bdf8"/>
    <circle cx="640" cy="75.4" r="4" fill="#38bdf8"/>
    <circle cx="720" cy="73.5" r="5" fill="#4ade80" stroke="#0f172a" stroke-width="2"/>
    <!-- value labels -->
    <text x="720" y="67" fill="#4ade80" font-size="11" text-anchor="middle">94.2%</text>
    <!-- x axis labels -->
    <text x="90" y="180" fill="#94a3b8" font-size="10" text-anchor="middle">Aug</text>
    <text x="195" y="180" fill="#94a3b8" font-size="10" text-anchor="middle">Sep</text>
    <text x="300" y="180" fill="#94a3b8" font-size="10" text-anchor="middle">Oct</text>
    <text x="380" y="180" fill="#94a3b8" font-size="10" text-anchor="middle">Nov</text>
    <text x="460" y="180" fill="#94a3b8" font-size="10" text-anchor="middle">Dec</text>
    <text x="540" y="180" fill="#94a3b8" font-size="10" text-anchor="middle">Jan</text>
    <text x="640" y="180" fill="#94a3b8" font-size="10" text-anchor="middle">Feb</text>
    <text x="720" y="180" fill="#e2e8f0" font-size="10" text-anchor="middle" font-weight="600">Mar</text>
  </svg>
</div>

<div class="chart-wrap">
  <h2>Accounts Receivable &amp; Upsell Pipeline</h2>
  <table>
    <thead>
      <tr><th>Account</th><th>Type</th><th>Amount</th><th>Due / Close Date</th><th>Days</th><th>Status</th><th>Owner</th></tr>
    </thead>
    <tbody>
      <tr><td>AgroBot Inc.</td><td>Invoice</td><td>$4,800</td><td>2026-04-05</td><td>+6d</td><td><span class="badge badge-pending">Pending</span></td><td>AR Team</td></tr>
      <tr><td>Machina Robotics</td><td>Invoice</td><td>$4,200</td><td>2026-03-23</td><td>-7d</td><td><span class="badge badge-overdue">Overdue</span></td><td>Escalate</td></tr>
      <tr><td>SynthArm Labs</td><td>Invoice</td><td>$3,400</td><td>2026-04-12</td><td>+13d</td><td><span class="badge badge-pending">Pending</span></td><td>AR Team</td></tr>
      <tr><td>AgroBot Inc.</td><td>Upsell</td><td>$22,000</td><td>2026-05-15</td><td>Opp</td><td><span class="badge badge-upsell">Pipeline</span></td><td>Sales</td></tr>
      <tr><td>Helix Dynamics</td><td>Upsell</td><td>$15,000</td><td>2026-04-30</td><td>Opp</td><td><span class="badge badge-upsell">Pipeline</span></td><td>Sales</td></tr>
      <tr><td>TerraForge</td><td>Upsell</td><td>$10,000</td><td>2026-06-01</td><td>Opp</td><td><span class="badge badge-upsell">Pipeline</span></td><td>Sales</td></tr>
      <tr><td>SynthArm Labs</td><td>Invoice</td><td>$2,800</td><td>2026-03-18</td><td>-12d</td><td><span class="badge badge-paid">Paid</span></td><td>&mdash;</td></tr>
      <tr><td>Helix Dynamics</td><td>Invoice</td><td>$6,100</td><td>2026-03-20</td><td>-10d</td><td><span class="badge badge-paid">Paid</span></td><td>&mdash;</td></tr>
    </tbody>
  </table>
</div>

<footer>Revenue Operations Dashboard &mdash; OCI Robot Cloud &mdash; port 8923 &mdash; MRR $35,240 &bull; AR $12,400 &bull; DSO 23d &bull; NRR 112%</footer>
</body></html>
"""

if USE_FASTAPI:
    app = FastAPI(title="Revenue Operations Dashboard", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return HTML

    @app.get("/health")
    async def health():
        mrr = 35240
        ar_total = 12400
        ar_overdue = 4200
        dso = 23
        upsell_pipeline = 47000
        collections_rate = 94.2
        nrr = 112
        return {
            "status": "ok",
            "service": "revenue_operations_dashboard",
            "port": 8923,
            "mrr_usd": mrr,
            "ar_total_usd": ar_total,
            "ar_overdue_usd": ar_overdue,
            "dso_days": dso,
            "upsell_pipeline_usd": upsell_pipeline,
            "collections_rate_pct": collections_rate,
            "nrr_pct": nrr,
            "alerts": [
                {"account": "Machina Robotics", "issue": "invoice overdue 7 days", "amount": ar_overdue}
            ],
        }

    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=8923)

else:
    from http.server import HTTPServer, BaseHTTPRequestHandler

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = HTML.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    if __name__ == "__main__":
        print("FastAPI unavailable — using stdlib HTTPServer on port 8923")
        HTTPServer(("0.0.0.0", 8923), Handler).serve_forever()
