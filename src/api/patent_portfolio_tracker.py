"""Patent Portfolio Tracker — port 8961

3 patents in draft: universal_robot_transfer / video_reward_model / adaptive_dagger
$2.4M IP value estimate. Filing timeline: Apr provisional -> Jul utility -> Mar 2027 PCT.
2+ patents needed for Series A.
"""

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
<title>Patent Portfolio Tracker</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; padding: 2rem; }
  h1 { color: #C74634; font-size: 2rem; margin-bottom: 0.5rem; }
  h2 { color: #38bdf8; font-size: 1.2rem; margin: 1.5rem 0 0.75rem; }
  .subtitle { color: #94a3b8; font-size: 0.95rem; margin-bottom: 2rem; }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-bottom: 2rem; }
  .card { background: #1e293b; border-radius: 10px; padding: 1.25rem; border: 1px solid #334155; }
  .card .label { color: #94a3b8; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em; }
  .card .value { color: #f1f5f9; font-size: 1.8rem; font-weight: 700; margin-top: 0.25rem; }
  .card .sub { color: #64748b; font-size: 0.75rem; margin-top: 0.2rem; }
  .chart-box { background: #1e293b; border-radius: 10px; padding: 1.5rem; border: 1px solid #334155; margin-bottom: 1.5rem; }
  .patent { background: #1e293b; border-radius: 8px; padding: 1rem 1.25rem; border-left: 4px solid #C74634; margin-bottom: 0.75rem; }
  .patent .name { color: #C74634; font-weight: 700; font-size: 0.95rem; }
  .patent .desc { color: #94a3b8; font-size: 0.82rem; margin-top: 0.2rem; }
  .patent .value { color: #22c55e; font-size: 0.85rem; font-weight: 600; margin-top: 0.4rem; }
  .badge { display: inline-block; background: #0f172a; border-radius: 4px; padding: 0.1rem 0.5rem; font-size: 0.72rem; margin-left: 0.5rem; }
  .badge.draft { color: #f59e0b; border: 1px solid #f59e0b; }
  .badge.provisional { color: #38bdf8; border: 1px solid #38bdf8; }
  .badge.filed { color: #22c55e; border: 1px solid #22c55e; }
  .milestone { display: flex; align-items: flex-start; gap: 1rem; padding: 0.75rem 0; border-bottom: 1px solid #1e293b; }
  .milestone:last-child { border-bottom: none; }
  .milestone .dot { width: 12px; height: 12px; border-radius: 50%; margin-top: 3px; flex-shrink: 0; }
  .milestone .dot.done { background: #22c55e; }
  .milestone .dot.next { background: #38bdf8; }
  .milestone .dot.future { background: #475569; }
  .milestone .date { color: #38bdf8; font-weight: 600; font-size: 0.85rem; min-width: 90px; }
  .milestone .text { color: #e2e8f0; font-size: 0.85rem; }
  .milestone .sub { color: #64748b; font-size: 0.78rem; }
</style>
</head>
<body>
<h1>Patent Portfolio Tracker</h1>
<p class="subtitle">Port 8961 &mdash; IP pipeline management &mdash; 3 patents in draft &mdash; $2.4M estimated portfolio value</p>

<div class="grid">
  <div class="card"><div class="label">Patents in Draft</div><div class="value">3</div><div class="sub">all active</div></div>
  <div class="card"><div class="label">IP Value Estimate</div><div class="value">$2.4M</div><div class="sub">total portfolio</div></div>
  <div class="card"><div class="label">Series A Requirement</div><div class="value">2+</div><div class="sub">patents needed</div></div>
  <div class="card"><div class="label">PCT Deadline</div><div class="value">Mar 2027</div><div class="sub">12-month window</div></div>
</div>

<h2>Patent Pipeline</h2>

<div class="patent">
  <div class="name">universal_robot_transfer <span class="badge draft">DRAFT</span></div>
  <div class="desc">Cross-embodiment policy transfer via latent space alignment — enables one trained policy to generalize to new robot hardware without retraining.</div>
  <div class="value">Estimated value: $900K &bull; Priority: HIGH &bull; Claim coverage: 12 claims</div>
</div>

<div class="patent">
  <div class="name">video_reward_model <span class="badge draft">DRAFT</span></div>
  <div class="desc">Vision-language reward model trained on robot demonstration videos — eliminates manual reward engineering for new manipulation tasks.</div>
  <div class="value">Estimated value: $850K &bull; Priority: HIGH &bull; Claim coverage: 9 claims</div>
</div>

<div class="patent">
  <div class="name">adaptive_dagger <span class="badge draft">DRAFT</span></div>
  <div class="desc">Online DAgger variant with automatic intervention threshold tuning — reduces human correction burden by 63% in production deployments.</div>
  <div class="value">Estimated value: $650K &bull; Priority: MEDIUM &bull; Claim coverage: 7 claims</div>
</div>

<h2>Filing Timeline</h2>
<div class="chart-box">
  <div class="milestone">
    <div class="dot next"></div>
    <div>
      <div class="date">Apr 2026</div>
      <div class="text">Provisional Filing — all 3 patents</div>
      <div class="sub">Establishes priority date &bull; 12-month protection window opens</div>
    </div>
  </div>
  <div class="milestone">
    <div class="dot future"></div>
    <div>
      <div class="date">Jul 2026</div>
      <div class="text">Utility Application — universal_robot_transfer + video_reward_model</div>
      <div class="sub">Full claim set filed &bull; Satisfies Series A 2-patent requirement</div>
    </div>
  </div>
  <div class="milestone">
    <div class="dot future"></div>
    <div>
      <div class="date">Sep 2026</div>
      <div class="text">Utility Application — adaptive_dagger</div>
      <div class="sub">Completes portfolio &bull; 3 utility patents in prosecution</div>
    </div>
  </div>
  <div class="milestone">
    <div class="dot future"></div>
    <div>
      <div class="date">Mar 2027</div>
      <div class="text">PCT International Filing</div>
      <div class="sub">Extends protection to 150+ countries &bull; Required for enterprise licensing</div>
    </div>
  </div>
</div>

<h2>IP Value Breakdown</h2>
<div class="chart-box">
  <svg width="100%" viewBox="0 0 580 220" xmlns="http://www.w3.org/2000/svg">
    <!-- Pie chart math: total=2400, slices: 900, 850, 650 -->
    <!-- Angles: 900/2400=37.5%, 850/2400=35.4%, 650/2400=27.1% -->
    <!-- 0.375*360=135deg, 0.354*360=127.4deg, 0.271*360=97.6deg -->
    <!-- SVG arc path for pie -->
    <!-- Slice 1: 0 -> 135deg (universal_robot_transfer, #C74634) -->
    <path d="M 110 110 L 110 30 A 80 80 0 0 1 166.6 166.6 Z" fill="#C74634"/>
    <!-- Slice 2: 135 -> 262.4deg (video_reward_model, #38bdf8) -->
    <path d="M 110 110 L 166.6 166.6 A 80 80 0 0 1 39.0 156.5 Z" fill="#38bdf8"/>
    <!-- Slice 3: 262.4 -> 360deg (adaptive_dagger, #f59e0b) -->
    <path d="M 110 110 L 39.0 156.5 A 80 80 0 0 1 110 30 Z" fill="#f59e0b"/>
    <!-- Center hole -->
    <circle cx="110" cy="110" r="38" fill="#1e293b"/>
    <text x="110" y="105" fill="#e2e8f0" font-size="13" text-anchor="middle" font-weight="700">$2.4M</text>
    <text x="110" y="122" fill="#94a3b8" font-size="9" text-anchor="middle">total IP value</text>
    <!-- Legend -->
    <rect x="220" y="60" width="12" height="12" fill="#C74634" rx="2"/>
    <text x="238" y="71" fill="#e2e8f0" font-size="12">universal_robot_transfer</text>
    <text x="238" y="85" fill="#22c55e" font-size="11">$900K (37.5%)</text>
    <rect x="220" y="105" width="12" height="12" fill="#38bdf8" rx="2"/>
    <text x="238" y="116" fill="#e2e8f0" font-size="12">video_reward_model</text>
    <text x="238" y="130" fill="#22c55e" font-size="11">$850K (35.4%)</text>
    <rect x="220" y="150" width="12" height="12" fill="#f59e0b" rx="2"/>
    <text x="238" y="161" fill="#e2e8f0" font-size="12">adaptive_dagger</text>
    <text x="238" y="175" fill="#22c55e" font-size="11">$650K (27.1%)</text>
    <!-- Series A threshold line annotation -->
    <text x="380" y="205" fill="#64748b" font-size="10" text-anchor="middle">2+ patents required for Series A fundraise</text>
  </svg>
</div>

</body>
</html>
"""

if USE_FASTAPI:
    app = FastAPI(title="Patent Portfolio Tracker", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def root():
        return HTML

    @app.get("/health")
    async def health():
        return {"status": "ok", "port": 8961, "service": "patent_portfolio_tracker"}

    @app.get("/portfolio")
    async def portfolio():
        return {
            "patents": [
                {"name": "universal_robot_transfer", "status": "draft", "value_usd": 900000, "claims": 12},
                {"name": "video_reward_model", "status": "draft", "value_usd": 850000, "claims": 9},
                {"name": "adaptive_dagger", "status": "draft", "value_usd": 650000, "claims": 7},
            ],
            "total_value_usd": 2400000,
            "series_a_requirement": 2,
            "timeline": [
                {"date": "2026-04", "event": "provisional_filing", "patents": 3},
                {"date": "2026-07", "event": "utility_application", "patents": ["universal_robot_transfer", "video_reward_model"]},
                {"date": "2026-09", "event": "utility_application", "patents": ["adaptive_dagger"]},
                {"date": "2027-03", "event": "pct_international_filing", "patents": 3},
            ],
        }

else:
    from http.server import HTTPServer, BaseHTTPRequestHandler

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(HTML.encode())
        def log_message(self, *a):
            pass

if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8961)
    else:
        print("Serving on http://0.0.0.0:8961 (fallback HTTPServer)")
        HTTPServer(("0.0.0.0", 8961), Handler).serve_forever()
