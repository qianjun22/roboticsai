# industry_vertical_tracker.py — Port 8973
# 5 verticals: warehouse / manufacturing / foodservice / healthcare / construction

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
<title>Industry Vertical Tracker</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; padding: 2rem; }
  h1 { color: #C74634; font-size: 2rem; margin-bottom: 0.5rem; }
  h2 { color: #38bdf8; font-size: 1.25rem; margin: 1.5rem 0 0.75rem; }
  .subtitle { color: #94a3b8; margin-bottom: 2rem; font-size: 0.95rem; }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-bottom: 2rem; }
  .card { background: #1e293b; border-radius: 10px; padding: 1.25rem; border: 1px solid #334155; }
  .metric { font-size: 2rem; font-weight: 700; color: #38bdf8; }
  .metric.red { color: #C74634; }
  .label { color: #94a3b8; font-size: 0.8rem; margin-top: 0.25rem; }
  .badge { display: inline-block; padding: 0.2rem 0.6rem; border-radius: 999px; font-size: 0.75rem; font-weight: 600; }
  .badge-blue { background: #1e40af; color: #93c5fd; }
  .badge-green { background: #14532d; color: #86efac; }
  .badge-orange { background: #7c2d12; color: #fdba74; }
  .badge-purple { background: #4c1d95; color: #c4b5fd; }
  .badge-gray { background: #1e293b; color: #94a3b8; border: 1px solid #334155; }
  table { width: 100%; border-collapse: collapse; font-size: 0.9rem; }
  th { color: #38bdf8; text-align: left; padding: 0.5rem 0.75rem; border-bottom: 1px solid #334155; }
  td { padding: 0.5rem 0.75rem; border-bottom: 1px solid #1e293b; color: #cbd5e1; }
  tr:hover td { background: #1e293b; }
  svg text { font-family: 'Segoe UI', system-ui, sans-serif; }
</style>
</head>
<body>
<h1>Industry Vertical Tracker</h1>
<p class="subtitle">OCI Robot Cloud fit scores across 5 verticals &nbsp;|&nbsp; Port 8973</p>

<div class="grid">
  <div class="card">
    <div class="metric">5</div>
    <div class="label">Target Verticals</div>
  </div>
  <div class="card">
    <div class="metric">91%</div>
    <div class="label">Warehouse — Highest OCI Fit</div>
  </div>
  <div class="card">
    <div class="metric red">$4.2T</div>
    <div class="label">Addressable Market (5 verticals)</div>
  </div>
  <div class="card">
    <div class="metric">6</div>
    <div class="label">Design Partners Mapped</div>
  </div>
</div>

<h2>Vertical Fit Heatmap</h2>
<div class="card">
  <svg width="100%" height="300" viewBox="0 0 720 300">
    <!-- Column headers -->
    <text x="180" y="22" text-anchor="middle" fill="#38bdf8" font-size="12">OCI Fit</text>
    <text x="300" y="22" text-anchor="middle" fill="#38bdf8" font-size="12">Maturity</text>
    <text x="420" y="22" text-anchor="middle" fill="#38bdf8" font-size="12">TAM ($B)</text>
    <text x="560" y="22" text-anchor="middle" fill="#38bdf8" font-size="12">Pipeline</text>

    <!-- Row data -->
    <!-- Warehouse: fit=91, color=22c55e -->
    <text x="70" y="58" fill="#e2e8f0" font-size="13" font-weight="600">Warehouse</text>
    <rect x="130" y="38" width="100" height="28" rx="5" fill="#14532d"/>
    <text x="180" y="57" text-anchor="middle" fill="#22c55e" font-size="13" font-weight="700">91%</text>
    <rect x="250" y="38" width="100" height="28" rx="5" fill="#14532d"/>
    <text x="300" y="57" text-anchor="middle" fill="#22c55e" font-size="12">High</text>
    <rect x="370" y="38" width="100" height="28" rx="5" fill="#1e293b"/>
    <text x="420" y="57" text-anchor="middle" fill="#e2e8f0" font-size="12">$890B</text>
    <rect x="490" y="38" width="160" height="28" rx="5" fill="#1e293b"/>
    <text x="570" y="57" text-anchor="middle" fill="#86efac" font-size="11">PI, Covariant</text>

    <!-- Manufacturing: fit=84 -->
    <text x="70" y="108" fill="#e2e8f0" font-size="13" font-weight="600">Manufacturing</text>
    <rect x="130" y="88" width="100" height="28" rx="5" fill="#1c3b2e"/>
    <text x="180" y="107" text-anchor="middle" fill="#4ade80" font-size="13" font-weight="700">84%</text>
    <rect x="250" y="88" width="100" height="28" rx="5" fill="#1c3b2e"/>
    <text x="300" y="107" text-anchor="middle" fill="#4ade80" font-size="12">High</text>
    <rect x="370" y="88" width="100" height="28" rx="5" fill="#1e293b"/>
    <text x="420" y="107" text-anchor="middle" fill="#e2e8f0" font-size="12">$1,200B</text>
    <rect x="490" y="88" width="160" height="28" rx="5" fill="#1e293b"/>
    <text x="570" y="107" text-anchor="middle" fill="#86efac" font-size="11">Machina Labs</text>

    <!-- Foodservice: fit=72 -->
    <text x="70" y="158" fill="#e2e8f0" font-size="13" font-weight="600">Foodservice</text>
    <rect x="130" y="138" width="100" height="28" rx="5" fill="#422006"/>
    <text x="180" y="157" text-anchor="middle" fill="#fb923c" font-size="13" font-weight="700">72%</text>
    <rect x="250" y="138" width="100" height="28" rx="5" fill="#422006"/>
    <text x="300" y="157" text-anchor="middle" fill="#fb923c" font-size="12">Medium</text>
    <rect x="370" y="138" width="100" height="28" rx="5" fill="#1e293b"/>
    <text x="420" y="157" text-anchor="middle" fill="#e2e8f0" font-size="12">$310B</text>
    <rect x="490" y="138" width="160" height="28" rx="5" fill="#1e293b"/>
    <text x="570" y="157" text-anchor="middle" fill="#94a3b8" font-size="11">Recruiting</text>

    <!-- Healthcare: fit=68 -->
    <text x="70" y="208" fill="#e2e8f0" font-size="13" font-weight="600">Healthcare</text>
    <rect x="130" y="188" width="100" height="28" rx="5" fill="#422006"/>
    <text x="180" y="207" text-anchor="middle" fill="#fbbf24" font-size="13" font-weight="700">68%</text>
    <rect x="250" y="188" width="100" height="28" rx="5" fill="#422006"/>
    <text x="300" y="207" text-anchor="middle" fill="#fbbf24" font-size="12">Medium</text>
    <rect x="370" y="188" width="100" height="28" rx="5" fill="#1e293b"/>
    <text x="420" y="207" text-anchor="middle" fill="#e2e8f0" font-size="12">$520B</text>
    <rect x="490" y="188" width="160" height="28" rx="5" fill="#1e293b"/>
    <text x="570" y="207" text-anchor="middle" fill="#94a3b8" font-size="11">Evaluating</text>

    <!-- Construction: fit=61 -->
    <text x="70" y="258" fill="#e2e8f0" font-size="13" font-weight="600">Construction</text>
    <rect x="130" y="238" width="100" height="28" rx="5" fill="#7f1d1d"/>
    <text x="180" y="257" text-anchor="middle" fill="#f87171" font-size="13" font-weight="700">61%</text>
    <rect x="250" y="238" width="100" height="28" rx="5" fill="#7f1d1d"/>
    <text x="300" y="257" text-anchor="middle" fill="#f87171" font-size="12">Low</text>
    <rect x="370" y="238" width="100" height="28" rx="5" fill="#1e293b"/>
    <text x="420" y="257" text-anchor="middle" fill="#e2e8f0" font-size="12">$1,280B</text>
    <rect x="490" y="238" width="160" height="28" rx="5" fill="#1e293b"/>
    <text x="570" y="257" text-anchor="middle" fill="#94a3b8" font-size="11">Watchlist</text>
  </svg>
</div>

<h2>Market Size Comparison</h2>
<div class="card">
  <svg width="100%" height="220" viewBox="0 0 700 220">
    <text x="350" y="18" text-anchor="middle" fill="#94a3b8" font-size="13">TAM per Vertical ($B) — bar width proportional to market size</text>

    <!-- Max TAM = 1280 (Construction), scale to 400px -->
    <!-- Warehouse: 890/1280*400=278 -->
    <rect x="130" y="35" width="278" height="26" fill="#22c55e" rx="4"/>
    <text x="70" y="53" text-anchor="end" fill="#e2e8f0" font-size="12">Warehouse</text>
    <text x="415" y="53" fill="#22c55e" font-size="12" font-weight="700">$890B</text>

    <!-- Manufacturing: 1200/1280*400=375 -->
    <rect x="130" y="72" width="375" height="26" fill="#38bdf8" rx="4"/>
    <text x="70" y="90" text-anchor="end" fill="#e2e8f0" font-size="12">Manufacturing</text>
    <text x="512" y="90" fill="#38bdf8" font-size="12" font-weight="700">$1,200B</text>

    <!-- Foodservice: 310/1280*400=97 -->
    <rect x="130" y="109" width="97" height="26" fill="#fb923c" rx="4"/>
    <text x="70" y="127" text-anchor="end" fill="#e2e8f0" font-size="12">Foodservice</text>
    <text x="234" y="127" fill="#fb923c" font-size="12" font-weight="700">$310B</text>

    <!-- Healthcare: 520/1280*400=163 -->
    <rect x="130" y="146" width="163" height="26" fill="#a78bfa" rx="4"/>
    <text x="70" y="164" text-anchor="end" fill="#e2e8f0" font-size="12">Healthcare</text>
    <text x="300" y="164" fill="#a78bfa" font-size="12" font-weight="700">$520B</text>

    <!-- Construction: 1280/1280*400=400 -->
    <rect x="130" y="183" width="400" height="26" fill="#C74634" rx="4"/>
    <text x="70" y="201" text-anchor="end" fill="#e2e8f0" font-size="12">Construction</text>
    <text x="537" y="201" fill="#C74634" font-size="12" font-weight="700">$1,280B</text>
  </svg>
</div>

<h2>Design Partner Mapping</h2>
<div class="card">
  <table>
    <thead>
      <tr><th>Partner</th><th>Vertical</th><th>Stage</th><th>OCI Fit</th></tr>
    </thead>
    <tbody>
      <tr><td>Physical Intelligence (PI)</td><td>Warehouse</td><td><span class="badge badge-green">Active</span></td><td>91%</td></tr>
      <tr><td>Covariant</td><td>Warehouse</td><td><span class="badge badge-green">Active</span></td><td>91%</td></tr>
      <tr><td>Machina Labs</td><td>Manufacturing</td><td><span class="badge badge-blue">Pilot</span></td><td>84%</td></tr>
      <tr><td>1X Technologies</td><td>Logistics</td><td><span class="badge badge-orange">Evaluating</span></td><td>79%</td></tr>
      <tr><td>Apptronik</td><td>Manufacturing</td><td><span class="badge badge-orange">Evaluating</span></td><td>82%</td></tr>
      <tr><td>Figure AI</td><td>Warehouse / Mfg</td><td><span class="badge badge-gray">Watchlist</span></td><td>88%</td></tr>
    </tbody>
  </table>
</div>

<p style="color:#475569; font-size:0.78rem; margin-top:2rem;">OCI Robot Cloud &mdash; Industry Vertical Tracker &mdash; Port 8973</p>
</body>
</html>
"""

if USE_FASTAPI:
    app = FastAPI(title="Industry Vertical Tracker", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def root():
        return HTML

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "industry_vertical_tracker", "port": 8973}

    @app.get("/metrics")
    async def metrics():
        return {
            "verticals": [
                {"name": "warehouse", "fit_pct": 91, "tam_b": 890, "partners": ["PI", "Covariant"]},
                {"name": "manufacturing", "fit_pct": 84, "tam_b": 1200, "partners": ["Machina Labs"]},
                {"name": "foodservice", "fit_pct": 72, "tam_b": 310, "partners": []},
                {"name": "healthcare", "fit_pct": 68, "tam_b": 520, "partners": []},
                {"name": "construction", "fit_pct": 61, "tam_b": 1280, "partners": []},
            ],
            "top_vertical": "warehouse",
            "design_partners": 6,
            "total_tam_b": 4200,
        }

    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=8973)

else:
    import http.server

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(HTML.encode())
        def log_message(self, fmt, *args):
            pass

    if __name__ == "__main__":
        server = http.server.HTTPServer(("0.0.0.0", 8973), Handler)
        print("Industry Vertical Tracker running on port 8973")
        server.serve_forever()
