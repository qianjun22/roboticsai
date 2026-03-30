# Competitive Moat Tracker — port 8969
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
<title>Competitive Moat Tracker</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; padding: 2rem; }
  h1 { color: #C74634; font-size: 2rem; margin-bottom: 0.5rem; }
  h2 { color: #38bdf8; font-size: 1.2rem; margin: 1.5rem 0 0.75rem; }
  .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; margin-top: 1.5rem; }
  .card { background: #1e293b; border-radius: 12px; padding: 1.5rem; }
  .card h3 { color: #38bdf8; margin-bottom: 1rem; font-size: 1rem; }
  .metric { display: flex; justify-content: space-between; padding: 0.4rem 0; border-bottom: 1px solid #334155; }
  .metric:last-child { border-bottom: none; }
  .metric .label { color: #94a3b8; }
  .metric .value { color: #f1f5f9; font-weight: 600; }
  .tag { display: inline-block; padding: 0.2rem 0.6rem; border-radius: 4px; font-size: 0.75rem; font-weight: 600; margin-left: 0.5rem; }
  .tag-green { background: #064e3b; color: #6ee7b7; }
  .tag-blue { background: #0c4a6e; color: #7dd3fc; }
  .tag-red { background: #7f1d1d; color: #fca5a5; }
  .tag-yellow { background: #78350f; color: #fcd34d; }
  svg text { font-family: 'Segoe UI', sans-serif; }
  .subtitle { color: #64748b; font-size: 0.9rem; margin-bottom: 1rem; }
</style>
</head>
<body>
<h1>Competitive Moat Tracker</h1>
<p class="subtitle">Port 8969 &mdash; 6-Moat Analysis &amp; Durability Assessment</p>

<div class="grid">
  <!-- Moat Depth Radar -->
  <div class="card">
    <h3>Moat Depth Radar (0-10 scale)</h3>
    <svg viewBox="0 0 300 280" width="100%">
      <!-- Radar chart: 6 axes, center 150,145, radius 90 -->
      <!-- Axes at 0,60,120,180,240,300 degrees -->
      <!-- Moat scores: NVIDIA_preferred=9, cost_9.6x=8, US_origin=7, OCI_access=9, IP=8, data_flywheel=9 -->

      <defs>
        <polygon id="hex" points="150,55 228,100 228,190 150,235 72,190 72,100" fill="none" stroke="#334155" stroke-width="0.8"/>
      </defs>

      <!-- Background rings at 25%, 50%, 75%, 100% -->
      <polygon points="150,122 169.5,132 169.5,152 150,162 130.5,152 130.5,132" fill="none" stroke="#1e3a5f" stroke-width="0.5"/>
      <polygon points="150,100 189,122 189,168 150,190 111,168 111,122" fill="none" stroke="#1e3a5f" stroke-width="0.5"/>
      <polygon points="150,77 208.5,112 208.5,178 150,212 91.5,178 91.5,112" fill="none" stroke="#1e3a5f" stroke-width="0.5"/>
      <polygon points="150,55 228,100 228,190 150,235 72,190 72,100" fill="none" stroke="#334155" stroke-width="1"/>

      <!-- Axis lines -->
      <line x1="150" y1="145" x2="150" y2="55" stroke="#334155" stroke-width="0.8"/>
      <line x1="150" y1="145" x2="228" y2="100" stroke="#334155" stroke-width="0.8"/>
      <line x1="150" y1="145" x2="228" y2="190" stroke="#334155" stroke-width="0.8"/>
      <line x1="150" y1="145" x2="150" y2="235" stroke="#334155" stroke-width="0.8"/>
      <line x1="150" y1="145" x2="72" y2="190" stroke="#334155" stroke-width="0.8"/>
      <line x1="150" y1="145" x2="72" y2="100" stroke="#334155" stroke-width="0.8"/>

      <!-- Scores: NVIDIA_preferred=9/10, cost=8/10, US_origin=7/10, OCI_access=9/10, IP=8/10, flywheel=9/10 -->
      <!-- Each axis: 0deg=top(150,55 to 150,145), 60deg=upper-right, 120=lower-right, 180=bottom, 240=lower-left, 300=upper-left -->
      <!-- point = center + (score/10)*direction -->
      <!-- NVIDIA(9): up: 150, 145-81=64 -> (150,64) -->
      <!-- cost(8): upper-right: center+(72,45)*0.8 -> (207.6,109) -->
      <!-- US_origin(7): lower-right: center+(72,-45)*0.7... -->
      <!-- Let me compute properly: radius=90 -->
      <!-- 0deg (top): (150,145-90)=(150,55) -> at score 9: (150,145-81)=(150,64) -->
      <!-- 60deg (upper-right): (150+78,145-45)=(228,100) -> at 8: (150+62.4,145-36)=(212.4,109) -->
      <!-- 120deg (lower-right): (150+78,145+45)=(228,190) -> at 7: (150+54.6,145+31.5)=(204.6,176.5) -->
      <!-- 180deg (bottom): (150,145+90)=(150,235) -> at 9: (150,145+81)=(150,226) -->
      <!-- 240deg (lower-left): (150-78,145+45)=(72,190) -> at 8: (150-62.4,145+36)=(87.6,181) -->
      <!-- 300deg (upper-left): (150-78,145-45)=(72,100) -> at 9: (150-81*sin60,145-81*cos60)=(150-70.1,145-40.5)=(79.9,104.5) -->
      <polygon
        points="150,64 212.4,109 204.6,176.5 150,226 87.6,181 79.9,104.5"
        fill="#C74634" fill-opacity="0.25" stroke="#C74634" stroke-width="2"/>

      <!-- Data points -->
      <circle cx="150" cy="64" r="4" fill="#C74634"/>
      <circle cx="212" cy="109" r="4" fill="#C74634"/>
      <circle cx="205" cy="177" r="4" fill="#C74634"/>
      <circle cx="150" cy="226" r="4" fill="#C74634"/>
      <circle cx="88" cy="181" r="4" fill="#C74634"/>
      <circle cx="80" cy="105" r="4" fill="#C74634"/>

      <!-- Axis labels -->
      <text x="150" y="48" text-anchor="middle" fill="#38bdf8" font-size="9">NVIDIA</text>
      <text x="150" y="41" text-anchor="middle" fill="#64748b" font-size="8">preferred</text>
      <text x="244" y="103" text-anchor="start" fill="#38bdf8" font-size="9">Cost</text>
      <text x="244" y="113" text-anchor="start" fill="#64748b" font-size="8">9.6x</text>
      <text x="244" y="188" text-anchor="start" fill="#38bdf8" font-size="9">US</text>
      <text x="244" y="198" text-anchor="start" fill="#64748b" font-size="8">origin</text>
      <text x="150" y="250" text-anchor="middle" fill="#38bdf8" font-size="9">OCI</text>
      <text x="150" y="260" text-anchor="middle" fill="#64748b" font-size="8">access</text>
      <text x="54" y="188" text-anchor="end" fill="#38bdf8" font-size="9">IP</text>
      <text x="54" y="198" text-anchor="end" fill="#64748b" font-size="8">moat</text>
      <text x="54" y="103" text-anchor="end" fill="#38bdf8" font-size="9">Data</text>
      <text x="54" y="113" text-anchor="end" fill="#64748b" font-size="8">flywheel</text>
    </svg>
  </div>

  <!-- Durability Comparison -->
  <div class="card">
    <h3>Moat Durability (years to replicate)</h3>
    <svg viewBox="0 0 300 220" width="100%">
      <!-- Horizontal bar chart -->
      <!-- Moats: IP=10yr, flywheel=7yr, OCI_access=6yr, NVIDIA_pref=5yr, cost=4yr, US_origin=3yr -->
      <!-- max=10, bar width = (val/10)*210 -->

      <!-- Y labels + bars -->
      <!-- IP -->
      <text x="80" y="32" text-anchor="end" fill="#94a3b8" font-size="10">IP Moat</text>
      <rect x="85" y="20" width="210" height="14" rx="3" fill="#1e3a5f"/>
      <rect x="85" y="20" width="210" height="14" rx="3" fill="#C74634" opacity="0.85"/>
      <text x="299" y="32" text-anchor="end" fill="#f1f5f9" font-size="10" font-weight="bold">10 yr</text>

      <!-- flywheel -->
      <text x="80" y="62" text-anchor="end" fill="#94a3b8" font-size="10">Data Flywheel</text>
      <rect x="85" y="50" width="147" height="14" rx="3" fill="#38bdf8" opacity="0.85"/>
      <text x="236" y="62" text-anchor="end" fill="#f1f5f9" font-size="10" font-weight="bold">7 yr</text>

      <!-- OCI access -->
      <text x="80" y="92" text-anchor="end" fill="#94a3b8" font-size="10">OCI Access</text>
      <rect x="85" y="80" width="126" height="14" rx="3" fill="#a78bfa" opacity="0.85"/>
      <text x="215" y="92" text-anchor="end" fill="#f1f5f9" font-size="10" font-weight="bold">6 yr</text>

      <!-- NVIDIA pref -->
      <text x="80" y="122" text-anchor="end" fill="#94a3b8" font-size="10">NVIDIA Pref</text>
      <rect x="85" y="110" width="105" height="14" rx="3" fill="#34d399" opacity="0.85"/>
      <text x="194" y="122" text-anchor="end" fill="#f1f5f9" font-size="10" font-weight="bold">5 yr</text>

      <!-- cost -->
      <text x="80" y="152" text-anchor="end" fill="#94a3b8" font-size="10">Cost 9.6x</text>
      <rect x="85" y="140" width="84" height="14" rx="3" fill="#fbbf24" opacity="0.85"/>
      <text x="173" y="152" text-anchor="end" fill="#f1f5f9" font-size="10" font-weight="bold">4 yr</text>

      <!-- US origin -->
      <text x="80" y="182" text-anchor="end" fill="#94a3b8" font-size="10">US Origin</text>
      <rect x="85" y="170" width="63" height="14" rx="3" fill="#64748b" opacity="0.85"/>
      <text x="152" y="182" text-anchor="end" fill="#f1f5f9" font-size="10" font-weight="bold">3 yr</text>

      <!-- X axis -->
      <line x1="85" y1="195" x2="295" y2="195" stroke="#334155" stroke-width="1"/>
      <text x="85" y="208" fill="#64748b" font-size="9">0</text>
      <text x="148" y="208" fill="#64748b" font-size="9">3</text>
      <text x="190" y="208" fill="#64748b" font-size="9">5</text>
      <text x="232" y="208" fill="#64748b" font-size="9">7</text>
      <text x="253" y="208" fill="#64748b" font-size="9">8</text>
      <text x="289" y="208" fill="#64748b" font-size="9">10</text>
    </svg>
  </div>
</div>

<h2>6-Moat Analysis Summary</h2>
<div class="grid">
  <div class="card">
    <h3>Moat Depth Scores</h3>
    <div class="metric"><span class="label">NVIDIA Preferred Partner</span><span class="value">9/10 <span class="tag tag-green">strong</span></span></div>
    <div class="metric"><span class="label">Cost Advantage (9.6x)</span><span class="value">8/10</span></div>
    <div class="metric"><span class="label">US Origin Compliance</span><span class="value">7/10</span></div>
    <div class="metric"><span class="label">OCI Infrastructure Access</span><span class="value">9/10 <span class="tag tag-green">strong</span></span></div>
    <div class="metric"><span class="label">IP Portfolio</span><span class="value">8/10</span></div>
    <div class="metric"><span class="label">Data Flywheel</span><span class="value">9/10 <span class="tag tag-green">strong</span></span></div>
  </div>
  <div class="card">
    <h3>Competitor Replication Timeline</h3>
    <div class="metric"><span class="label">IP Moat</span><span class="value">10 yr <span class="tag tag-red">hardest</span></span></div>
    <div class="metric"><span class="label">Data Flywheel</span><span class="value">7 yr <span class="tag tag-red">hard</span></span></div>
    <div class="metric"><span class="label">OCI Access</span><span class="value">6 yr</span></div>
    <div class="metric"><span class="label">NVIDIA Preferred</span><span class="value">5 yr</span></div>
    <div class="metric"><span class="label">Cost 9.6x</span><span class="value">4 yr</span></div>
    <div class="metric"><span class="label">US Origin</span><span class="value">3 yr <span class="tag tag-blue">easiest</span></span></div>
  </div>
</div>

</body>
</html>
"""

if USE_FASTAPI:
    app = FastAPI(title="Competitive Moat Tracker")

    @app.get("/", response_class=HTMLResponse)
    async def index():
        return HTML

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "competitive_moat_tracker", "port": 8969}

    @app.get("/api/moats")
    async def moats():
        return {
            "moats": [
                {"name": "NVIDIA_preferred", "depth": 9, "durability_yr": 5},
                {"name": "cost_9.6x", "depth": 8, "durability_yr": 4},
                {"name": "US_origin", "depth": 7, "durability_yr": 3},
                {"name": "OCI_access", "depth": 9, "durability_yr": 6},
                {"name": "IP", "depth": 8, "durability_yr": 10},
                {"name": "data_flywheel", "depth": 9, "durability_yr": 7}
            ],
            "most_durable": "IP",
            "second_most_durable": "data_flywheel"
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
        uvicorn.run(app, host="0.0.0.0", port=8969)
    else:
        server = HTTPServer(("0.0.0.0", 8969), Handler)
        print("Serving on http://0.0.0.0:8969")
        server.serve_forever()
