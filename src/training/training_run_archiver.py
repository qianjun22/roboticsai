# Training Run Archiver — port 8922
# Checkpoint archival pipeline with hot/warm/cold tiering

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
<title>Training Run Archiver</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; padding: 24px; }
  h1 { color: #C74634; font-size: 2rem; margin-bottom: 4px; }
  .subtitle { color: #94a3b8; font-size: 0.95rem; margin-bottom: 28px; }
  h2 { color: #38bdf8; font-size: 1.15rem; margin-bottom: 14px; }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; margin-bottom: 28px; }
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
  .badge-hot { background: #7f1d1d; color: #fca5a5; }
  .badge-warm { background: #78350f; color: #fde68a; }
  .badge-cold { background: #1e3a5f; color: #93c5fd; }
  .badge-glacier { background: #1e293b; color: #94a3b8; border: 1px solid #475569; }
  .policy-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 14px; margin-bottom: 28px; }
  .policy-card { background: #1e293b; border-radius: 10px; padding: 16px; border-left: 4px solid #38bdf8; }
  .policy-card .ptype { font-size: 0.8rem; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.07em; }
  .policy-card .pname { font-size: 1.05rem; font-weight: 700; color: #f1f5f9; margin: 4px 0; }
  .policy-card .pdetail { font-size: 0.82rem; color: #cbd5e1; }
  footer { color: #475569; font-size: 0.78rem; margin-top: 32px; text-align: center; }
</style>
</head>
<body>
<h1>Training Run Archiver</h1>
<p class="subtitle">Checkpoint archival pipeline &mdash; hot/warm/cold/glacier tiering &mdash; port 8922</p>

<div class="grid">
  <div class="card"><div class="label">Total Runs Archived</div><div class="value">47</div><div class="delta" style="color:#94a3b8">12 GB avg per run</div></div>
  <div class="card"><div class="label">Raw Storage</div><div class="value">564 GB</div><div class="delta red">&uarr; untiered baseline</div></div>
  <div class="card"><div class="label">Tiered Storage</div><div class="value">98 GB</div><div class="delta green">&darr; 82.6% reduction</div></div>
  <div class="card"><div class="label">Monthly Cost</div><div class="value">$2.26</div><div class="delta green">vs $12.97 untiered (&minus;82.6%)</div></div>
  <div class="card"><div class="label">Hot Tier</div><div class="value">8 runs</div><div class="delta" style="color:#94a3b8">96 GB &mdash; &lt;1s retrieval</div></div>
  <div class="card"><div class="label">Warm Tier</div><div class="value">14 runs</div><div class="delta" style="color:#94a3b8">Compressed &mdash; &lt;30s retrieval</div></div>
  <div class="card"><div class="label">Cold Tier</div><div class="value">18 runs</div><div class="delta" style="color:#94a3b8">Object store &mdash; &lt;5 min</div></div>
  <div class="card"><div class="label">Glacier Tier</div><div class="value">7 runs</div><div class="delta" style="color:#94a3b8">Deep archive &mdash; &lt;4 hr</div></div>
</div>

<div class="chart-wrap">
  <h2>Storage Tier Breakdown (GB)</h2>
  <svg viewBox="0 0 760 220" xmlns="http://www.w3.org/2000/svg">
    <!-- axes -->
    <line x1="60" y1="20" x2="60" y2="180" stroke="#334155" stroke-width="1.5"/>
    <line x1="60" y1="180" x2="740" y2="180" stroke="#334155" stroke-width="1.5"/>
    <!-- grid lines at 25%, 50%, 75%, 100% of max 120 GB -->
    <line x1="60" y1="150" x2="740" y2="150" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,4"/>
    <line x1="60" y1="120" x2="740" y2="120" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,4"/>
    <line x1="60" y1="90" x2="740" y2="90" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,4"/>
    <line x1="60" y1="60" x2="740" y2="60" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,4"/>
    <!-- y labels -->
    <text x="52" y="183" fill="#94a3b8" font-size="11" text-anchor="end">0</text>
    <text x="52" y="153" fill="#94a3b8" font-size="11" text-anchor="end">30</text>
    <text x="52" y="123" fill="#94a3b8" font-size="11" text-anchor="end">60</text>
    <text x="52" y="93" fill="#94a3b8" font-size="11" text-anchor="end">90</text>
    <text x="52" y="63" fill="#94a3b8" font-size="11" text-anchor="end">120</text>
    <!-- bars: hot=96GB, warm=18GB, cold=8GB, glacier=2GB (compressed). scale: 120GB=120px, 1px=1GB -->
    <!-- hot bar: 96GB -> height=96, y=180-96=84 -->
    <rect x="100" y="84" width="100" height="96" fill="#ef4444" rx="4"/>
    <text x="150" y="79" fill="#fca5a5" font-size="12" text-anchor="middle">96 GB</text>
    <!-- warm bar: 18GB -> height=18, y=162 -->
    <rect x="270" y="162" width="100" height="18" fill="#f59e0b" rx="4"/>
    <text x="320" y="157" fill="#fde68a" font-size="12" text-anchor="middle">18 GB</text>
    <!-- cold bar: 8GB -> height=8, y=172 -->
    <rect x="440" y="172" width="100" height="8" fill="#38bdf8" rx="4"/>
    <text x="490" y="167" fill="#93c5fd" font-size="12" text-anchor="middle">8 GB</text>
    <!-- glacier bar: 2GB -> height=2 -->
    <rect x="610" y="178" width="100" height="2" fill="#64748b" rx="2"/>
    <text x="660" y="173" fill="#94a3b8" font-size="12" text-anchor="middle">2 GB</text>
    <!-- x labels -->
    <text x="150" y="198" fill="#e2e8f0" font-size="12" text-anchor="middle">Hot</text>
    <text x="320" y="198" fill="#e2e8f0" font-size="12" text-anchor="middle">Warm</text>
    <text x="490" y="198" fill="#e2e8f0" font-size="12" text-anchor="middle">Cold</text>
    <text x="660" y="198" fill="#e2e8f0" font-size="12" text-anchor="middle">Glacier</text>
    <text x="150" y="212" fill="#94a3b8" font-size="10" text-anchor="middle">&lt;1s</text>
    <text x="320" y="212" fill="#94a3b8" font-size="10" text-anchor="middle">&lt;30s</text>
    <text x="490" y="212" fill="#94a3b8" font-size="10" text-anchor="middle">&lt;5 min</text>
    <text x="660" y="212" fill="#94a3b8" font-size="10" text-anchor="middle">&lt;4 hr</text>
  </svg>
</div>

<div class="chart-wrap">
  <h2>Retrieval Time vs. Cost Trade-off (log scale)</h2>
  <svg viewBox="0 0 760 200" xmlns="http://www.w3.org/2000/svg">
    <!-- axes -->
    <line x1="60" y1="20" x2="60" y2="165" stroke="#334155" stroke-width="1.5"/>
    <line x1="60" y1="165" x2="740" y2="165" stroke="#334155" stroke-width="1.5"/>
    <!-- x axis: tiers equally spaced -->
    <!-- cost bars (scaled): hot $1.48/mo, warm $0.54, cold $0.19, glacier $0.05 -->
    <!-- max cost $1.48 -> scale to 120px -->
    <rect x="90" y="45" width="100" height="120" fill="#ef444466" rx="4"/>
    <rect x="260" y="101" width="100" height="64" fill="#f59e0b66" rx="4"/>
    <rect x="430" y="142" width="100" height="23" fill="#38bdf866" rx="4"/>
    <rect x="600" y="159" width="100" height="6" fill="#64748b66" rx="4"/>
    <!-- cost labels -->
    <text x="140" y="40" fill="#fca5a5" font-size="12" text-anchor="middle">$1.48/mo</text>
    <text x="310" y="96" fill="#fde68a" font-size="12" text-anchor="middle">$0.54/mo</text>
    <text x="480" y="137" fill="#93c5fd" font-size="12" text-anchor="middle">$0.19/mo</text>
    <text x="650" y="154" fill="#94a3b8" font-size="12" text-anchor="middle">$0.05/mo</text>
    <!-- x labels -->
    <text x="140" y="180" fill="#e2e8f0" font-size="12" text-anchor="middle">Hot</text>
    <text x="310" y="180" fill="#e2e8f0" font-size="12" text-anchor="middle">Warm</text>
    <text x="480" y="180" fill="#e2e8f0" font-size="12" text-anchor="middle">Cold</text>
    <text x="650" y="180" fill="#e2e8f0" font-size="12" text-anchor="middle">Glacier</text>
    <text x="140" y="194" fill="#94a3b8" font-size="10" text-anchor="middle">&lt;1s latency</text>
    <text x="310" y="194" fill="#94a3b8" font-size="10" text-anchor="middle">&lt;30s latency</text>
    <text x="480" y="194" fill="#94a3b8" font-size="10" text-anchor="middle">&lt;5 min</text>
    <text x="650" y="194" fill="#94a3b8" font-size="10" text-anchor="middle">&lt;4 hr</text>
  </svg>
</div>

<div class="chart-wrap">
  <h2>Retention Policy</h2>
  <div class="policy-grid">
    <div class="policy-card" style="border-color:#ef4444">
      <div class="ptype">Production</div>
      <div class="pname">2-Year Retention</div>
      <div class="pdetail">Hot &rarr; Warm (30d) &rarr; Cold (90d) &rarr; Glacier (1yr)</div>
    </div>
    <div class="policy-card" style="border-color:#f59e0b">
      <div class="ptype">Research</div>
      <div class="pname">90-Day Retention</div>
      <div class="pdetail">Hot (14d) &rarr; Warm (30d) &rarr; Cold (90d) &rarr; Purge</div>
    </div>
    <div class="policy-card" style="border-color:#a855f7">
      <div class="ptype">DAgger</div>
      <div class="pname">1-Year Retention</div>
      <div class="pdetail">Hot (7d) &rarr; Warm (30d) &rarr; Cold (1yr) &rarr; Glacier</div>
    </div>
    <div class="policy-card" style="border-color:#38bdf8">
      <div class="ptype">Fine-Tune</div>
      <div class="pname">180-Day Retention</div>
      <div class="pdetail">Hot (7d) &rarr; Warm (45d) &rarr; Cold (180d) &rarr; Review</div>
    </div>
  </div>
</div>

<div class="chart-wrap">
  <h2>Recent Archive Operations</h2>
  <table>
    <thead>
      <tr><th>Run ID</th><th>Model</th><th>Size</th><th>Tier</th><th>Retention Policy</th><th>Age</th><th>Retrieval</th></tr>
    </thead>
    <tbody>
      <tr><td>run-047</td><td>GR00T-N1.6</td><td>12.3 GB</td><td><span class="badge badge-hot">Hot</span></td><td>Production</td><td>2d</td><td>&lt; 1s</td></tr>
      <tr><td>run-046</td><td>GR00T-N1.6</td><td>11.8 GB</td><td><span class="badge badge-hot">Hot</span></td><td>Production</td><td>5d</td><td>&lt; 1s</td></tr>
      <tr><td>run-039</td><td>DAgger-r5</td><td>9.4 GB</td><td><span class="badge badge-warm">Warm</span></td><td>DAgger</td><td>31d</td><td>&lt; 30s</td></tr>
      <tr><td>run-033</td><td>BC-baseline</td><td>8.1 GB</td><td><span class="badge badge-cold">Cold</span></td><td>Research</td><td>67d</td><td>&lt; 5 min</td></tr>
      <tr><td>run-021</td><td>GR00T-N1.0</td><td>14.2 GB</td><td><span class="badge badge-cold">Cold</span></td><td>Production</td><td>112d</td><td>&lt; 5 min</td></tr>
      <tr><td>run-008</td><td>OpenVLA-v1</td><td>7.6 GB</td><td><span class="badge badge-glacier">Glacier</span></td><td>Research</td><td>289d</td><td>&lt; 4 hr</td></tr>
      <tr><td>run-001</td><td>OpenVLA-v0</td><td>6.9 GB</td><td><span class="badge badge-glacier">Glacier</span></td><td>Research</td><td>341d</td><td>&lt; 4 hr</td></tr>
    </tbody>
  </table>
</div>

<footer>Training Run Archiver &mdash; OCI Robot Cloud &mdash; port 8922 &mdash; 47 runs &times; 12 GB = 564 GB managed</footer>
</body></html>
"""

if USE_FASTAPI:
    app = FastAPI(title="Training Run Archiver", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return HTML

    @app.get("/health")
    async def health():
        hot_gb = 96
        warm_gb = 18
        cold_gb = 8
        glacier_gb = 2
        total_raw = 564
        total_tiered = hot_gb + warm_gb + cold_gb + glacier_gb
        reduction = round((1 - total_tiered / total_raw) * 100, 1)
        monthly_cost = round(hot_gb * 0.0154 + warm_gb * 0.03 + cold_gb * 0.024 + glacier_gb * 0.025, 2)
        return {
            "status": "ok",
            "service": "training_run_archiver",
            "port": 8922,
            "runs_archived": 47,
            "total_raw_gb": total_raw,
            "total_tiered_gb": total_tiered,
            "reduction_pct": reduction,
            "monthly_cost_usd": monthly_cost,
            "tiers": {
                "hot": {"runs": 8, "gb": hot_gb, "retrieval": "<1s"},
                "warm": {"runs": 14, "gb": warm_gb, "retrieval": "<30s"},
                "cold": {"runs": 18, "gb": cold_gb, "retrieval": "<5min"},
                "glacier": {"runs": 7, "gb": glacier_gb, "retrieval": "<4hr"},
            },
        }

    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=8922)

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
        print("FastAPI unavailable — using stdlib HTTPServer on port 8922")
        HTTPServer(("0.0.0.0", 8922), Handler).serve_forever()
