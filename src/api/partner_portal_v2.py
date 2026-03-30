# Partner Portal V2 — port 8983
# Self-service portal: DAgger launch, checkpoint browser, eval request,
# billing, support, SDK download, roadmap voting

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
<title>Partner Portal V2</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; padding: 2rem; }
  h1 { color: #C74634; font-size: 2rem; margin-bottom: 0.5rem; }
  h2 { color: #38bdf8; font-size: 1.2rem; margin: 1.5rem 0 0.75rem; }
  .subtitle { color: #94a3b8; margin-bottom: 2rem; font-size: 0.95rem; }
  .cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 1rem; margin-bottom: 2rem; }
  .card { background: #1e293b; border-radius: 8px; padding: 1.25rem; border-left: 3px solid #38bdf8; }
  .card .value { font-size: 1.8rem; font-weight: 700; color: #f1f5f9; }
  .card .label { color: #94a3b8; font-size: 0.85rem; margin-top: 0.25rem; }
  .card .delta { font-size: 0.8rem; margin-top: 0.4rem; }
  .pos { color: #4ade80; } .neg { color: #f87171; } .neu { color: #facc15; }
  .chart-box { background: #1e293b; border-radius: 8px; padding: 1.5rem; margin-bottom: 1.5rem; }
  svg text { font-family: 'Segoe UI', sans-serif; }
  table { width: 100%; border-collapse: collapse; background: #1e293b; border-radius: 8px; overflow: hidden; }
  th { background: #0f172a; color: #38bdf8; padding: 0.75rem 1rem; text-align: left; font-size: 0.85rem; }
  td { padding: 0.7rem 1rem; border-top: 1px solid #334155; font-size: 0.9rem; color: #cbd5e1; }
  tr:hover td { background: #263248; }
  .badge { display: inline-block; padding: 0.2rem 0.6rem; border-radius: 9999px; font-size: 0.75rem; font-weight: 600; }
  .badge-green { background: #14532d; color: #4ade80; }
  .badge-blue { background: #0c4a6e; color: #38bdf8; }
  .badge-yellow { background: #422006; color: #facc15; }
</style>
</head>
<body>
<h1>Partner Portal V2</h1>
<p class="subtitle">Self-service portal for design partners &mdash; port 8983</p>

<div class="cards">
  <div class="card">
    <div class="value">4/5</div>
    <div class="label">MAU (partners active weekly)</div>
    <div class="delta pos">80% weekly engagement</div>
  </div>
  <div class="card">
    <div class="value">18 min</div>
    <div class="label">Avg Session Duration</div>
    <div class="delta pos">+4min vs V1 (14min)</div>
  </div>
  <div class="card">
    <div class="value">NPS 78</div>
    <div class="label">Portal Net Promoter Score</div>
    <div class="delta pos">World-class (&gt;70)</div>
  </div>
  <div class="card">
    <div class="value">7</div>
    <div class="label">Self-Service Features</div>
    <div class="delta neu">DAgger, ckpt, eval, billing...</div>
  </div>
</div>

<h2>Feature Engagement Breakdown</h2>
<div class="chart-box">
  <svg width="100%" viewBox="0 0 760 260" xmlns="http://www.w3.org/2000/svg">
    <!-- axes -->
    <line x1="180" y1="20" x2="180" y2="220" stroke="#475569" stroke-width="1"/>
    <line x1="180" y1="220" x2="730" y2="220" stroke="#475569" stroke-width="1"/>
    <text x="455" y="250" fill="#94a3b8" font-size="11" text-anchor="middle">Avg Weekly Sessions per Partner</text>
    <!-- x grid and labels -->
    <line x1="294" y1="20" x2="294" y2="220" stroke="#1e293b" stroke-width="1" stroke-dasharray="4"/>
    <line x1="408" y1="20" x2="408" y2="220" stroke="#1e293b" stroke-width="1" stroke-dasharray="4"/>
    <line x1="522" y1="20" x2="522" y2="220" stroke="#1e293b" stroke-width="1" stroke-dasharray="4"/>
    <line x1="636" y1="20" x2="636" y2="220" stroke="#1e293b" stroke-width="1" stroke-dasharray="4"/>
    <text x="180" y="235" fill="#94a3b8" font-size="9" text-anchor="middle">0</text>
    <text x="294" y="235" fill="#94a3b8" font-size="9" text-anchor="middle">1</text>
    <text x="408" y="235" fill="#94a3b8" font-size="9" text-anchor="middle">2</text>
    <text x="522" y="235" fill="#94a3b8" font-size="9" text-anchor="middle">3</text>
    <text x="636" y="235" fill="#94a3b8" font-size="9" text-anchor="middle">4</text>
    <!-- Feature bars (horizontal): 7 features, values proportional to 114px=1 session -->
    <!-- DAgger Launch: 3.8 sessions -->
    <rect x="180" y="32" width="433" height="22" fill="#C74634" opacity="0.85" rx="3"/>
    <text x="174" y="48" fill="#94a3b8" font-size="10" text-anchor="end">DAgger Launch</text>
    <text x="618" y="48" fill="#f1f5f9" font-size="10">3.8</text>
    <!-- Checkpoint Browser: 3.2 -->
    <rect x="180" y="62" width="365" height="22" fill="#38bdf8" opacity="0.8" rx="3"/>
    <text x="174" y="78" fill="#94a3b8" font-size="10" text-anchor="end">Checkpoint Browser</text>
    <text x="550" y="78" fill="#f1f5f9" font-size="10">3.2</text>
    <!-- Eval Request: 2.9 -->
    <rect x="180" y="92" width="331" height="22" fill="#38bdf8" opacity="0.7" rx="3"/>
    <text x="174" y="108" fill="#94a3b8" font-size="10" text-anchor="end">Eval Request</text>
    <text x="516" y="108" fill="#f1f5f9" font-size="10">2.9</text>
    <!-- Billing Dashboard: 2.1 -->
    <rect x="180" y="122" width="239" height="22" fill="#4ade80" opacity="0.75" rx="3"/>
    <text x="174" y="138" fill="#94a3b8" font-size="10" text-anchor="end">Billing Dashboard</text>
    <text x="424" y="138" fill="#0f172a" font-size="10" font-weight="600">2.1</text>
    <!-- Support Tickets: 1.4 -->
    <rect x="180" y="152" width="160" height="22" fill="#facc15" opacity="0.75" rx="3"/>
    <text x="174" y="168" fill="#94a3b8" font-size="10" text-anchor="end">Support Tickets</text>
    <text x="345" y="168" fill="#0f172a" font-size="10" font-weight="600">1.4</text>
    <!-- SDK Download: 1.1 -->
    <rect x="180" y="182" width="125" height="22" fill="#a78bfa" opacity="0.8" rx="3"/>
    <text x="174" y="198" fill="#94a3b8" font-size="10" text-anchor="end">SDK Download</text>
    <text x="310" y="198" fill="#f1f5f9" font-size="10">1.1</text>
    <!-- Roadmap Voting: 0.7 -->
    <rect x="180" y="212" width="80" height=""height="0"/>
    <!-- Use separate row for roadmap -->
  </svg>
  <!-- Extra bar for roadmap voting rendered below to avoid viewBox clipping -->
  <svg width="100%" viewBox="0 0 760 50" xmlns="http://www.w3.org/2000/svg">
    <rect x="180" y="10" width="80" height="22" fill="#f472b6" opacity="0.8" rx="3"/>
    <text x="174" y="26" fill="#94a3b8" font-size="10" text-anchor="end">Roadmap Voting</text>
    <text x="265" y="26" fill="#f1f5f9" font-size="10">0.7</text>
  </svg>
</div>

<h2>Portal Usage Metrics (Weekly Trend)</h2>
<div class="chart-box">
  <svg width="100%" viewBox="0 0 760 200" xmlns="http://www.w3.org/2000/svg">
    <!-- axes -->
    <line x1="60" y1="10" x2="60" y2="160" stroke="#475569" stroke-width="1"/>
    <line x1="60" y1="160" x2="730" y2="160" stroke="#475569" stroke-width="1"/>
    <text x="395" y="185" fill="#94a3b8" font-size="11" text-anchor="middle">Week (last 8 weeks)</text>
    <text x="15" y="90" fill="#94a3b8" font-size="11" transform="rotate(-90,15,90)">Total Sessions</text>
    <!-- grid -->
    <line x1="60" y1="50" x2="730" y2="50" stroke="#1e293b" stroke-width="1" stroke-dasharray="4"/>
    <line x1="60" y1="100" x2="730" y2="100" stroke="#1e293b" stroke-width="1" stroke-dasharray="4"/>
    <line x1="60" y1="130" x2="730" y2="130" stroke="#1e293b" stroke-width="1" stroke-dasharray="4"/>
    <text x="55" y="54" fill="#94a3b8" font-size="9" text-anchor="end">60</text>
    <text x="55" y="104" fill="#94a3b8" font-size="9" text-anchor="end">30</text>
    <text x="55" y="134" fill="#94a3b8" font-size="9" text-anchor="end">15</text>
    <!-- Line chart: 8 weekly data points sessions=[22,27,31,35,38,42,47,52] -->
    <!-- x positions: 60+i*95 for i=0..7, y: 160-(val/60)*150 -->
    <!-- W1 22 -> y=105 W2 27->y=92 W3 31->y=82 W4 35->y=72 W5 38->y=65 W6 42->y=55 W7 47->y=42 W8 52->y=30 -->
    <polyline points="60,105 155,92 250,82 345,72 440,65 535,55 630,42 725,30"
      fill="none" stroke="#C74634" stroke-width="2.5" stroke-linejoin="round"/>
    <!-- dots -->
    <circle cx="60" cy="105" r="4" fill="#C74634"/>
    <circle cx="155" cy="92" r="4" fill="#C74634"/>
    <circle cx="250" cy="82" r="4" fill="#C74634"/>
    <circle cx="345" cy="72" r="4" fill="#C74634"/>
    <circle cx="440" cy="65" r="4" fill="#C74634"/>
    <circle cx="535" cy="55" r="4" fill="#C74634"/>
    <circle cx="630" cy="42" r="4" fill="#C74634"/>
    <circle cx="725" cy="30" r="5" fill="#4ade80"/>
    <!-- x week labels -->
    <text x="60" y="175" fill="#94a3b8" font-size="9" text-anchor="middle">W-8</text>
    <text x="155" y="175" fill="#94a3b8" font-size="9" text-anchor="middle">W-7</text>
    <text x="250" y="175" fill="#94a3b8" font-size="9" text-anchor="middle">W-6</text>
    <text x="345" y="175" fill="#94a3b8" font-size="9" text-anchor="middle">W-5</text>
    <text x="440" y="175" fill="#94a3b8" font-size="9" text-anchor="middle">W-4</text>
    <text x="535" y="175" fill="#94a3b8" font-size="9" text-anchor="middle">W-3</text>
    <text x="630" y="175" fill="#94a3b8" font-size="9" text-anchor="middle">W-2</text>
    <text x="725" y="175" fill="#4ade80" font-size="9" text-anchor="middle">Now</text>
    <!-- session labels at endpoints -->
    <text x="60" y="100" fill="#94a3b8" font-size="9" text-anchor="middle">22</text>
    <text x="725" y="25" fill="#4ade80" font-size="9" text-anchor="middle">52</text>
  </svg>
</div>

<h2>Feature Inventory</h2>
<table>
  <thead><tr><th>Feature</th><th>Description</th><th>Avg Uses/Week</th><th>Status</th></tr></thead>
  <tbody>
    <tr><td>DAgger Launch</td><td>One-click DAgger training run with config form</td><td>3.8</td><td><span class="badge badge-green">GA</span></td></tr>
    <tr><td>Checkpoint Browser</td><td>Browse, compare, and download model checkpoints</td><td>3.2</td><td><span class="badge badge-green">GA</span></td></tr>
    <tr><td>Eval Request</td><td>Submit closed-loop eval jobs + view results dashboard</td><td>2.9</td><td><span class="badge badge-green">GA</span></td></tr>
    <tr><td>Billing Dashboard</td><td>Real-time cost breakdown by service/run</td><td>2.1</td><td><span class="badge badge-green">GA</span></td></tr>
    <tr><td>Support Tickets</td><td>Create and track support requests in-portal</td><td>1.4</td><td><span class="badge badge-green">GA</span></td></tr>
    <tr><td>SDK Download</td><td>Versioned SDK downloads with changelog</td><td>1.1</td><td><span class="badge badge-green">GA</span></td></tr>
    <tr><td>Roadmap Voting</td><td>Upvote and comment on upcoming features</td><td>0.7</td><td><span class="badge badge-blue">Beta</span></td></tr>
  </tbody>
</table>

</body>
</html>
"""

if USE_FASTAPI:
    app = FastAPI(title="Partner Portal V2")

    @app.get("/", response_class=HTMLResponse)
    async def root():
        return HTML

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "partner_portal_v2", "port": 8983}

    @app.get("/metrics")
    async def metrics():
        return {
            "mau_partners": 4,
            "total_partners": 5,
            "weekly_engagement_pct": 80,
            "avg_session_min": 18,
            "portal_nps": 78,
            "features_ga": 6,
            "features_beta": 1,
            "top_feature": "dagger_launch",
            "top_feature_weekly_sessions": 3.8,
        }

    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=8983)
else:
    from http.server import HTTPServer, BaseHTTPRequestHandler

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(HTML.encode())
        def log_message(self, *args):
            pass

    if __name__ == "__main__":
        print("FastAPI not available, using stdlib HTTPServer on port 8983")
        HTTPServer(("0.0.0.0", 8983), Handler).serve_forever()
