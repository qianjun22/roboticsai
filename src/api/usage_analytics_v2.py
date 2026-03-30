# Usage Analytics V2 — port 8979
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
<title>Usage Analytics V2</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; padding: 2rem; }
  h1 { color: #C74634; font-size: 2rem; margin-bottom: 0.5rem; }
  h2 { color: #38bdf8; font-size: 1.2rem; margin: 1.5rem 0 0.75rem; }
  .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; margin-top: 1.5rem; }
  .card { background: #1e293b; border-radius: 12px; padding: 1.5rem; }
  .subtitle { color: #94a3b8; font-size: 0.95rem; margin-bottom: 1rem; }
  .stat-row { display: flex; justify-content: space-between; align-items: center;
              padding: 0.5rem 0; border-bottom: 1px solid #334155; }
  .stat-row:last-child { border-bottom: none; }
  .stat-label { color: #cbd5e1; font-size: 0.9rem; }
  .stat-value { color: #38bdf8; font-weight: 600; font-size: 0.95rem; }
  .stat-value.red { color: #C74634; }
  .stat-value.green { color: #4ade80; }
  .tag { display: inline-block; padding: 2px 8px; border-radius: 4px;
         font-size: 0.75rem; margin-left: 6px; }
  .tag-up { background: rgba(74,222,128,0.15); color: #4ade80; }
  .tag-down { background: rgba(199,70,52,0.15); color: #C74634; }
  svg text { font-family: 'Segoe UI', sans-serif; }
</style>
</head>
<body>
<h1>Usage Analytics V2</h1>
<p class="subtitle">Cohort Retention &amp; Feature Engagement &mdash; Port 8979</p>

<div class="grid">
  <div class="card">
    <h2>Q1 Cohort Retention (Week-over-Week)</h2>
    <svg width="100%" viewBox="0 0 320 200" xmlns="http://www.w3.org/2000/svg">
      <!-- Q1 cohort: wk1=100, wk2=98, wk3=97, wk4=96, wk5=96, wk6=95, wk7=95, wk8=94 -->
      <!-- chart area: x 40..300, y 20..170, range 85..100 scaled -->
      <!-- y scale: 100 → y=20, 85 → y=170; (val-85)/(15) * 150 inverted -->
      <!-- y = 170 - (val-85)/15*150 -->
      <!-- wk1 x=40: y=170-(15/15)*150=20 -->
      <!-- wk2 x=77: y=170-(13/15)*150=40 -->
      <!-- wk3 x=114: y=170-(12/15)*150=50 -->
      <!-- wk4 x=151: y=170-(11/15)*150=60 -->
      <!-- wk5 x=188: y=170-(11/15)*150=60 -->
      <!-- wk6 x=225: y=170-(10/15)*150=70 -->
      <!-- wk7 x=262: y=170-(10/15)*150=70 -->
      <!-- wk8 x=299: y=170-(9/15)*150=80 -->
      <line x1="40" y1="20" x2="40" y2="170" stroke="#475569" stroke-width="1"/>
      <line x1="40" y1="170" x2="310" y2="170" stroke="#475569" stroke-width="1"/>
      <!-- grid -->
      <line x1="40" y1="70" x2="310" y2="70" stroke="#334155" stroke-width="1" stroke-dasharray="4,3"/>
      <line x1="40" y1="120" x2="310" y2="120" stroke="#334155" stroke-width="1" stroke-dasharray="4,3"/>
      <text x="34" y="173" text-anchor="end" fill="#94a3b8" font-size="9">85%</text>
      <text x="34" y="123" text-anchor="end" fill="#94a3b8" font-size="9">90%</text>
      <text x="34" y="73" text-anchor="end" fill="#94a3b8" font-size="9">95%</text>
      <text x="34" y="23" text-anchor="end" fill="#94a3b8" font-size="9">100%</text>
      <!-- area fill -->
      <polygon
        points="40,20 77,40 114,50 151,60 188,60 225,70 262,70 299,80 299,170 40,170"
        fill="rgba(56,189,248,0.12)"/>
      <!-- line -->
      <polyline
        points="40,20 77,40 114,50 151,60 188,60 225,70 262,70 299,80"
        fill="none" stroke="#38bdf8" stroke-width="2.5" stroke-linejoin="round"/>
      <!-- dots -->
      <circle cx="40" cy="20" r="3.5" fill="#38bdf8"/>
      <circle cx="77" cy="40" r="3.5" fill="#38bdf8"/>
      <circle cx="114" cy="50" r="3.5" fill="#38bdf8"/>
      <circle cx="151" cy="60" r="3.5" fill="#38bdf8"/>
      <circle cx="188" cy="60" r="3.5" fill="#38bdf8"/>
      <circle cx="225" cy="70" r="3.5" fill="#38bdf8"/>
      <circle cx="262" cy="70" r="3.5" fill="#38bdf8"/>
      <circle cx="299" cy="80" r="3.5" fill="#C74634"/>
      <!-- wk8 annotation -->
      <text x="299" y="73" text-anchor="middle" fill="#C74634" font-size="10" font-weight="bold">94%</text>
      <!-- x labels -->
      <text x="40" y="183" text-anchor="middle" fill="#94a3b8" font-size="9">Wk1</text>
      <text x="77" y="183" text-anchor="middle" fill="#94a3b8" font-size="9">Wk2</text>
      <text x="114" y="183" text-anchor="middle" fill="#94a3b8" font-size="9">Wk3</text>
      <text x="151" y="183" text-anchor="middle" fill="#94a3b8" font-size="9">Wk4</text>
      <text x="188" y="183" text-anchor="middle" fill="#94a3b8" font-size="9">Wk5</text>
      <text x="225" y="183" text-anchor="middle" fill="#94a3b8" font-size="9">Wk6</text>
      <text x="262" y="183" text-anchor="middle" fill="#94a3b8" font-size="9">Wk7</text>
      <text x="299" y="183" text-anchor="middle" fill="#94a3b8" font-size="9">Wk8</text>
    </svg>
  </div>

  <div class="card">
    <h2>Feature Engagement Funnel</h2>
    <svg width="100%" viewBox="0 0 320 200" xmlns="http://www.w3.org/2000/svg">
      <!-- Inference 100%, Eval 91%, DAgger 78%, Streaming 47% -->
      <!-- Horizontal bars, max width=220 -->
      <!-- Inference: 220 -->
      <text x="8" y="32" fill="#cbd5e1" font-size="10">Inference</text>
      <rect x="90" y="20" width="220" height="18" fill="#38bdf8" rx="3"/>
      <text x="316" y="33" fill="#38bdf8" font-size="10" text-anchor="end">100%</text>
      <!-- Eval: 200.2 -->
      <text x="8" y="70" fill="#cbd5e1" font-size="10">Eval</text>
      <rect x="90" y="58" width="200" height="18" fill="#38bdf8" rx="3"/>
      <text x="296" y="71" fill="#38bdf8" font-size="10" text-anchor="end">91%</text>
      <!-- DAgger: 171.6 -->
      <text x="8" y="108" fill="#cbd5e1" font-size="10">DAgger</text>
      <rect x="90" y="96" width="172" height="18" fill="#0ea5e9" rx="3"/>
      <text x="270" y="109" fill="#0ea5e9" font-size="10" text-anchor="end">78%</text>
      <!-- Streaming: 103.4  fastest growing tag -->
      <text x="8" y="146" fill="#cbd5e1" font-size="10">Streaming</text>
      <rect x="90" y="134" width="103" height="18" fill="#C74634" rx="3"/>
      <text x="200" y="147" fill="#C74634" font-size="10" text-anchor="end">47%</text>
      <text x="205" y="147" fill="#4ade80" font-size="9">&#9650; fastest growing</text>
      <!-- axis -->
      <line x1="90" y1="165" x2="310" y2="165" stroke="#475569" stroke-width="1"/>
      <text x="90" y="178" text-anchor="middle" fill="#94a3b8" font-size="9">0%</text>
      <text x="200" y="178" text-anchor="middle" fill="#94a3b8" font-size="9">50%</text>
      <text x="310" y="178" text-anchor="middle" fill="#94a3b8" font-size="9">100%</text>
    </svg>
  </div>
</div>

<div class="card" style="margin-top:1.5rem;">
  <h2>Usage Highlights</h2>
  <div class="stat-row">
    <span class="stat-label">Top User (API calls/day)</span>
    <span class="stat-value">PI &mdash; 847 calls/day <span class="tag tag-up">&#9650; active</span></span>
  </div>
  <div class="stat-row">
    <span class="stat-label">Declining User Segment</span>
    <span class="stat-value red">1X cohort <span class="tag tag-down">&#9660; declining</span></span>
  </div>
  <div class="stat-row">
    <span class="stat-label">Q1 Cohort Week-8 Retention</span>
    <span class="stat-value green">94%</span>
  </div>
  <div class="stat-row">
    <span class="stat-label">Fastest-Growing Feature</span>
    <span class="stat-value green">Streaming (+47%, up from 0) <span class="tag tag-up">&#9650;</span></span>
  </div>
  <div class="stat-row">
    <span class="stat-label">Core Feature Adoption (Inference)</span>
    <span class="stat-value">100% of active users</span>
  </div>
  <div class="stat-row">
    <span class="stat-label">Advanced Feature Adoption (DAgger)</span>
    <span class="stat-value">78% of active users</span>
  </div>
</div>

</body>
</html>
"""

if USE_FASTAPI:
    app = FastAPI(title="Usage Analytics V2")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return HTML

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "usage_analytics_v2", "port": 8979}

    @app.get("/metrics")
    def metrics():
        return {
            "cohort_retention": {
                "q1_week8": 0.94,
                "weekly": [1.00, 0.98, 0.97, 0.96, 0.96, 0.95, 0.95, 0.94],
            },
            "feature_engagement": {
                "inference": 1.00,
                "eval": 0.91,
                "dagger": 0.78,
                "streaming": 0.47,
            },
            "top_user": {"segment": "PI", "calls_per_day": 847},
            "declining_segment": "1X",
        }

else:
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(HTML.encode())

        def log_message(self, fmt, *args):
            pass

if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8979)
    else:
        server = HTTPServer(("0.0.0.0", 8979), Handler)
        print("Serving on http://0.0.0.0:8979 (fallback HTTPServer)")
        server.serve_forever()
