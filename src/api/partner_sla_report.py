# Partner SLA Report — port 8909
# Monthly SLA compliance: latency_p95<250ms, uptime>99.5%, eval_turnaround<4h
# Q1 2026 100% compliance, heat calendar

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
<title>Partner SLA Report</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; padding: 2rem; }
  h1 { color: #C74634; font-size: 2rem; margin-bottom: 0.5rem; }
  h2 { color: #38bdf8; font-size: 1.25rem; margin: 1.5rem 0 0.75rem; }
  .subtitle { color: #94a3b8; margin-bottom: 2rem; }
  .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; }
  .card { background: #1e293b; border-radius: 12px; padding: 1.5rem; }
  .card.full { grid-column: 1 / -1; }
  table { width: 100%; border-collapse: collapse; font-size: 0.875rem; }
  th { color: #38bdf8; text-align: left; padding: 8px 12px; border-bottom: 1px solid #334155; }
  td { padding: 8px 12px; border-bottom: 1px solid #1e293b; }
  tr:hover td { background: #0f172a; }
  .badge { display: inline-block; border-radius: 4px; padding: 2px 8px; font-size: 0.75rem; font-weight: 600; }
  .pass { background: #14532d; color: #4ade80; }
  .warn { background: #422006; color: #fb923c; }
  .fail { background: #450a0a; color: #f87171; }
  .stat { font-size: 2rem; font-weight: 700; color: #4ade80; }
  .stat-label { font-size: 0.8rem; color: #94a3b8; margin-top: 4px; }
  .stats-row { display: flex; gap: 2rem; margin-top: 1rem; flex-wrap: wrap; }
  svg text { font-family: 'Segoe UI', sans-serif; }
</style>
</head>
<body>
<h1>Partner SLA Report</h1>
<p class="subtitle">Monthly SLA compliance &bull; latency_p95 &lt;250ms &bull; uptime &gt;99.5% &bull; eval_turnaround &lt;4h &bull; Port 8909</p>

<div class="grid">

  <!-- Per-Partner SLA Status Grid -->
  <div class="card full">
    <h2>Per-Partner SLA Status — Q1 2026</h2>
    <table>
      <thead>
        <tr>
          <th>Partner</th>
          <th>Latency P95 (ms)</th>
          <th>Uptime (%)</th>
          <th>Eval Turnaround (h)</th>
          <th>Jan</th>
          <th>Feb</th>
          <th>Mar</th>
          <th>Overall</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td><strong>Boston Dynamics</strong></td>
          <td>187</td>
          <td>99.91</td>
          <td>1.8</td>
          <td><span class="badge pass">PASS</span></td>
          <td><span class="badge pass">PASS</span></td>
          <td><span class="badge pass">PASS</span></td>
          <td><span class="badge pass">100%</span></td>
        </tr>
        <tr>
          <td><strong>Figure AI</strong></td>
          <td>212</td>
          <td>99.73</td>
          <td>2.4</td>
          <td><span class="badge pass">PASS</span></td>
          <td><span class="badge pass">PASS</span></td>
          <td><span class="badge pass">PASS</span></td>
          <td><span class="badge pass">100%</span></td>
        </tr>
        <tr>
          <td><strong>Agility Robotics</strong></td>
          <td>198</td>
          <td>99.84</td>
          <td>1.5</td>
          <td><span class="badge pass">PASS</span></td>
          <td><span class="badge pass">PASS</span></td>
          <td><span class="badge pass">PASS</span></td>
          <td><span class="badge pass">100%</span></td>
        </tr>
        <tr>
          <td><strong>Sanctuary AI</strong></td>
          <td>231</td>
          <td>99.61</td>
          <td>3.2</td>
          <td><span class="badge pass">PASS</span></td>
          <td><span class="badge pass">PASS</span></td>
          <td><span class="badge pass">PASS</span></td>
          <td><span class="badge pass">100%</span></td>
        </tr>
        <tr>
          <td><strong>1X Technologies</strong></td>
          <td>204</td>
          <td>99.78</td>
          <td>2.1</td>
          <td><span class="badge pass">PASS</span></td>
          <td><span class="badge pass">PASS</span></td>
          <td><span class="badge pass">PASS</span></td>
          <td><span class="badge pass">100%</span></td>
        </tr>
      </tbody>
    </table>
    <div class="stats-row" style="margin-top:1.25rem">
      <div><div class="stat">100%</div><div class="stat-label">Q1 compliance rate</div></div>
      <div><div class="stat">5/5</div><div class="stat-label">partners all-green</div></div>
      <div><div class="stat">206ms</div><div class="stat-label">avg latency P95</div></div>
      <div><div class="stat">99.77%</div><div class="stat-label">avg uptime</div></div>
    </div>
  </div>

  <!-- SLA Heat Calendar -->
  <div class="card">
    <h2>SLA Heat Calendar — Q1 2026</h2>
    <svg width="100%" viewBox="0 0 400 220" xmlns="http://www.w3.org/2000/svg">
      <!-- month labels -->
      <text x="70" y="18" fill="#38bdf8" font-size="11" font-weight="600">January</text>
      <text x="180" y="18" fill="#38bdf8" font-size="11" font-weight="600">February</text>
      <text x="300" y="18" fill="#38bdf8" font-size="11" font-weight="600">March</text>
      <!-- day-of-week labels -->
      <text x="22" y="38" fill="#94a3b8" font-size="8">Mon</text>
      <text x="22" y="52" fill="#94a3b8" font-size="8">Tue</text>
      <text x="22" y="66" fill="#94a3b8" font-size="8">Wed</text>
      <text x="22" y="80" fill="#94a3b8" font-size="8">Thu</text>
      <text x="22" y="94" fill="#94a3b8" font-size="8">Fri</text>
      <!-- January weeks (5 columns x 5 rows) -->
      <!-- All green = #14532d -->
      <!-- week 1 col x=55 -->
      <rect x="55" y="27" width="13" height="13" fill="#14532d" rx="2"/>
      <rect x="55" y="42" width="13" height="13" fill="#14532d" rx="2"/>
      <rect x="55" y="57" width="13" height="13" fill="#14532d" rx="2"/>
      <rect x="55" y="72" width="13" height="13" fill="#14532d" rx="2"/>
      <rect x="55" y="87" width="13" height="13" fill="#14532d" rx="2"/>
      <!-- week 2 -->
      <rect x="70" y="27" width="13" height="13" fill="#14532d" rx="2"/>
      <rect x="70" y="42" width="13" height="13" fill="#14532d" rx="2"/>
      <rect x="70" y="57" width="13" height="13" fill="#14532d" rx="2"/>
      <rect x="70" y="72" width="13" height="13" fill="#14532d" rx="2"/>
      <rect x="70" y="87" width="13" height="13" fill="#14532d" rx="2"/>
      <!-- week 3 -->
      <rect x="85" y="27" width="13" height="13" fill="#14532d" rx="2"/>
      <rect x="85" y="42" width="13" height="13" fill="#14532d" rx="2"/>
      <rect x="85" y="57" width="13" height="13" fill="#14532d" rx="2"/>
      <rect x="85" y="72" width="13" height="13" fill="#14532d" rx="2"/>
      <rect x="85" y="87" width="13" height="13" fill="#14532d" rx="2"/>
      <!-- week 4 -->
      <rect x="100" y="27" width="13" height="13" fill="#14532d" rx="2"/>
      <rect x="100" y="42" width="13" height="13" fill="#14532d" rx="2"/>
      <rect x="100" y="57" width="13" height="13" fill="#14532d" rx="2"/>
      <rect x="100" y="72" width="13" height="13" fill="#14532d" rx="2"/>
      <rect x="100" y="87" width="13" height="13" fill="#14532d" rx="2"/>
      <!-- February -->
      <rect x="170" y="27" width="13" height="13" fill="#14532d" rx="2"/>
      <rect x="170" y="42" width="13" height="13" fill="#14532d" rx="2"/>
      <rect x="170" y="57" width="13" height="13" fill="#14532d" rx="2"/>
      <rect x="170" y="72" width="13" height="13" fill="#14532d" rx="2"/>
      <rect x="170" y="87" width="13" height="13" fill="#14532d" rx="2"/>
      <rect x="185" y="27" width="13" height="13" fill="#14532d" rx="2"/>
      <rect x="185" y="42" width="13" height="13" fill="#14532d" rx="2"/>
      <rect x="185" y="57" width="13" height="13" fill="#14532d" rx="2"/>
      <rect x="185" y="72" width="13" height="13" fill="#14532d" rx="2"/>
      <rect x="185" y="87" width="13" height="13" fill="#14532d" rx="2"/>
      <rect x="200" y="27" width="13" height="13" fill="#14532d" rx="2"/>
      <rect x="200" y="42" width="13" height="13" fill="#14532d" rx="2"/>
      <rect x="200" y="57" width="13" height="13" fill="#14532d" rx="2"/>
      <rect x="200" y="72" width="13" height="13" fill="#14532d" rx="2"/>
      <rect x="200" y="87" width="13" height="13" fill="#14532d" rx="2"/>
      <rect x="215" y="27" width="13" height="13" fill="#14532d" rx="2"/>
      <rect x="215" y="42" width="13" height="13" fill="#14532d" rx="2"/>
      <rect x="215" y="57" width="13" height="13" fill="#14532d" rx="2"/>
      <rect x="215" y="72" width="13" height="13" fill="#14532d" rx="2"/>
      <rect x="215" y="87" width="13" height="13" fill="#14532d" rx="2"/>
      <!-- March -->
      <rect x="285" y="27" width="13" height="13" fill="#14532d" rx="2"/>
      <rect x="285" y="42" width="13" height="13" fill="#14532d" rx="2"/>
      <rect x="285" y="57" width="13" height="13" fill="#14532d" rx="2"/>
      <rect x="285" y="72" width="13" height="13" fill="#14532d" rx="2"/>
      <rect x="285" y="87" width="13" height="13" fill="#14532d" rx="2"/>
      <rect x="300" y="27" width="13" height="13" fill="#14532d" rx="2"/>
      <rect x="300" y="42" width="13" height="13" fill="#14532d" rx="2"/>
      <rect x="300" y="57" width="13" height="13" fill="#14532d" rx="2"/>
      <rect x="300" y="72" width="13" height="13" fill="#14532d" rx="2"/>
      <rect x="300" y="87" width="13" height="13" fill="#14532d" rx="2"/>
      <rect x="315" y="27" width="13" height="13" fill="#14532d" rx="2"/>
      <rect x="315" y="42" width="13" height="13" fill="#14532d" rx="2"/>
      <rect x="315" y="57" width="13" height="13" fill="#14532d" rx="2"/>
      <rect x="315" y="72" width="13" height="13" fill="#14532d" rx="2"/>
      <rect x="315" y="87" width="13" height="13" fill="#14532d" rx="2"/>
      <rect x="330" y="27" width="13" height="13" fill="#14532d" rx="2"/>
      <rect x="330" y="42" width="13" height="13" fill="#14532d" rx="2"/>
      <rect x="330" y="57" width="13" height="13" fill="#14532d" rx="2"/>
      <rect x="330" y="72" width="13" height="13" fill="#14532d" rx="2"/>
      <rect x="330" y="87" width="13" height="13" fill="#14532d" rx="2"/>
      <!-- legend -->
      <rect x="55" y="115" width="12" height="12" fill="#14532d" rx="2"/>
      <text x="72" y="124" fill="#94a3b8" font-size="10">All SLAs met</text>
      <rect x="150" y="115" width="12" height="12" fill="#422006" rx="2"/>
      <text x="167" y="124" fill="#94a3b8" font-size="10">1 SLA breach</text>
      <rect x="250" y="115" width="12" height="12" fill="#450a0a" rx="2"/>
      <text x="267" y="124" fill="#94a3b8" font-size="10">2+ SLA breaches</text>
      <!-- annotation -->
      <text x="200" y="150" text-anchor="middle" fill="#4ade80" font-size="12" font-weight="600">Zero SLA breaches across all Q1 2026 working days</text>
    </svg>
  </div>

  <!-- Compliance Trend -->
  <div class="card">
    <h2>Compliance Trend — Q1 2026</h2>
    <svg width="100%" viewBox="0 0 380 220" xmlns="http://www.w3.org/2000/svg">
      <line x1="50" y1="10" x2="50" y2="180" stroke="#334155" stroke-width="1"/>
      <line x1="50" y1="180" x2="370" y2="180" stroke="#334155" stroke-width="1"/>
      <!-- Y labels (95-100%) -->
      <text x="45" y="180" text-anchor="end" fill="#94a3b8" font-size="9">95%</text>
      <text x="45" y="145" text-anchor="end" fill="#94a3b8" font-size="9">96%</text>
      <text x="45" y="110" text-anchor="end" fill="#94a3b8" font-size="9">97%</text>
      <text x="45" y="75" text-anchor="end" fill="#94a3b8" font-size="9">98%</text>
      <text x="45" y="40" text-anchor="end" fill="#94a3b8" font-size="9">99%</text>
      <text x="45" y="15" text-anchor="end" fill="#94a3b8" font-size="9">100%</text>
      <line x1="50" y1="15" x2="370" y2="15" stroke="#4ade80" stroke-width="1" stroke-dasharray="3,3" opacity="0.4"/>
      <!-- grid -->
      <line x1="50" y1="75" x2="370" y2="75" stroke="#1e293b" stroke-width="1" stroke-dasharray="2,3"/>
      <line x1="50" y1="110" x2="370" y2="110" stroke="#1e293b" stroke-width="1" stroke-dasharray="2,3"/>
      <line x1="50" y1="145" x2="370" y2="145" stroke="#1e293b" stroke-width="1" stroke-dasharray="2,3"/>
      <!-- latency compliance (100% flat) -->
      <polyline points="60,15 150,15 240,15 350,15" fill="none" stroke="#38bdf8" stroke-width="2"/>
      <!-- uptime compliance -->
      <polyline points="60,15 150,15 240,15 350,15" fill="none" stroke="#4ade80" stroke-width="2" stroke-dasharray="6,3"/>
      <!-- eval turnaround -->
      <polyline points="60,15 150,15 240,15 350,15" fill="none" stroke="#C74634" stroke-width="2" stroke-dasharray="2,4"/>
      <!-- x labels -->
      <text x="60" y="195" fill="#94a3b8" font-size="9">Jan</text>
      <text x="150" y="195" fill="#94a3b8" font-size="9">Feb</text>
      <text x="240" y="195" fill="#94a3b8" font-size="9">Mar</text>
      <!-- legend -->
      <rect x="60" y="205" width="20" height="2" fill="#38bdf8"/>
      <text x="85" y="210" fill="#94a3b8" font-size="9">latency_p95</text>
      <rect x="155" y="205" width="20" height="2" fill="#4ade80"/>
      <text x="180" y="210" fill="#94a3b8" font-size="9">uptime</text>
      <rect x="240" y="205" width="20" height="2" fill="#C74634"/>
      <text x="265" y="210" fill="#94a3b8" font-size="9">eval_turnaround</text>
    </svg>
  </div>

</div>
</body>
</html>
"""

if USE_FASTAPI:
    app = FastAPI(title="Partner SLA Report")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return HTML

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "partner_sla_report", "port": 8909}

    @app.get("/api/sla-data")
    def sla_data():
        partners = [
            {"name": "Boston Dynamics", "latency_p95_ms": 187, "uptime_pct": 99.91, "eval_turnaround_h": 1.8, "q1_compliance": 100},
            {"name": "Figure AI", "latency_p95_ms": 212, "uptime_pct": 99.73, "eval_turnaround_h": 2.4, "q1_compliance": 100},
            {"name": "Agility Robotics", "latency_p95_ms": 198, "uptime_pct": 99.84, "eval_turnaround_h": 1.5, "q1_compliance": 100},
            {"name": "Sanctuary AI", "latency_p95_ms": 231, "uptime_pct": 99.61, "eval_turnaround_h": 3.2, "q1_compliance": 100},
            {"name": "1X Technologies", "latency_p95_ms": 204, "uptime_pct": 99.78, "eval_turnaround_h": 2.1, "q1_compliance": 100},
        ]
        thresholds = {"latency_p95_ms": 250, "uptime_pct": 99.5, "eval_turnaround_h": 4}
        return {"partners": partners, "thresholds": thresholds, "overall_q1_compliance": 100}

    @app.get("/api/monthly-trend")
    def monthly_trend():
        months = ["Jan 2026", "Feb 2026", "Mar 2026"]
        metrics = {
            "latency_p95_compliance": [100, 100, 100],
            "uptime_compliance": [100, 100, 100],
            "eval_turnaround_compliance": [100, 100, 100],
        }
        return {"months": months, "compliance": metrics}

else:
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(HTML.encode())

        def log_message(self, *args):
            pass

if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8909)
    else:
        print("[partner_sla_report] FastAPI unavailable — serving on port 8909 via HTTPServer")
        HTTPServer(("0.0.0.0", 8909), Handler).serve_forever()
