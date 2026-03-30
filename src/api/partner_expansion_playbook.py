# Partner Expansion Playbook — port 8951
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
<title>Partner Expansion Playbook</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; padding: 2rem; }
  h1 { color: #C74634; font-size: 2rem; margin-bottom: 0.5rem; }
  h2 { color: #38bdf8; font-size: 1.25rem; margin: 1.5rem 0 0.75rem; }
  .subtitle { color: #94a3b8; margin-bottom: 2rem; }
  .cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 1rem; margin-bottom: 1.5rem; }
  .card { background: #1e293b; border-radius: 10px; padding: 1.25rem; border-left: 4px solid #C74634; }
  .card.blue { border-left-color: #38bdf8; }
  .card.green { border-left-color: #4ade80; }
  .card.purple { border-left-color: #a78bfa; }
  .card-val { font-size: 1.7rem; font-weight: 700; color: #f8fafc; }
  .card-label { color: #94a3b8; font-size: 0.85rem; margin-top: 0.3rem; }
  table { width: 100%; border-collapse: collapse; }
  th { background: #1e293b; color: #38bdf8; padding: 0.75rem 1rem; text-align: left; font-size: 0.9rem; }
  td { padding: 0.7rem 1rem; border-bottom: 1px solid #1e293b; font-size: 0.9rem; }
  tr:hover td { background: #1e293b55; }
  .tag { display: inline-block; padding: 0.2rem 0.6rem; border-radius: 4px; font-size: 0.78rem; font-weight: 600; }
  .high { background: #14532d; color: #4ade80; }
  .med { background: #713f12; color: #fbbf24; }
  .low { background: #1e1b4b; color: #a78bfa; }
  .chart-wrap { background: #1e293b; border-radius: 10px; padding: 1.25rem; margin-bottom: 1.5rem; }
  .lever-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 1rem; margin-bottom: 1.5rem; }
  .lever { background: #1e293b; border-radius: 10px; padding: 1.25rem; border-top: 3px solid #38bdf8; }
  .lever h3 { color: #38bdf8; font-size: 0.95rem; margin-bottom: 0.5rem; }
  .lever p { color: #94a3b8; font-size: 0.85rem; line-height: 1.5; }
  .lever .num { color: #C74634; font-weight: 700; font-size: 1.1rem; }
  .progress-bar { background: #334155; border-radius: 4px; height: 8px; margin-top: 0.4rem; }
  .progress-fill { height: 8px; border-radius: 4px; background: linear-gradient(90deg, #C74634, #38bdf8); }
  svg text { font-family: 'Segoe UI', sans-serif; }
  .footer { color: #475569; font-size: 0.8rem; margin-top: 2rem; text-align: center; }
</style>
</head>
<body>
<h1>Partner Expansion Playbook</h1>
<p class="subtitle">5 expansion levers, usage-triggered conversations, Q2 2026 upsell pipeline — Port 8951</p>

<div class="cards">
  <div class="card">
    <div class="card-val">$24,300</div>
    <div class="card-label">Q2 Expansion Target</div>
  </div>
  <div class="card blue">
    <div class="card-val">5</div>
    <div class="card-label">Active Design Partners</div>
  </div>
  <div class="card green">
    <div class="card-val">5</div>
    <div class="card-label">Expansion Levers</div>
  </div>
  <div class="card purple">
    <div class="card-val">3.2×</div>
    <div class="card-label">Avg Usage Growth (QoQ)</div>
  </div>
</div>

<h2>5 Expansion Levers</h2>
<div class="lever-grid">
  <div class="lever">
    <h3>1. Seat Expansion</h3>
    <p>When team usage exceeds <span class="num">80%</span> of contracted seats for 2+ weeks, trigger a capacity review. Average uplift: +40% ACV.</p>
  </div>
  <div class="lever">
    <h3>2. Task Breadth</h3>
    <p>Partners initially deploy 1-2 robot tasks. At <span class="num">90-day</span> mark, introduce multi-task fine-tuning bundle (pick-place + inspection + handover).</p>
  </div>
  <div class="lever">
    <h3>3. Data Volume Tier</h3>
    <p>Usage-triggered: when monthly demo uploads exceed <span class="num">500</span>, upsell to Enterprise Data tier (unlimited SDG + longer retention).</p>
  </div>
  <div class="lever">
    <h3>4. Inference Scale</h3>
    <p>When latency SLA is repeatedly near threshold (<span class="num">&lt;250ms</span>), introduce dedicated inference cluster add-on. +$800-$2,400/mo.</p>
  </div>
  <div class="lever">
    <h3>5. Real-World Deploy Pack</h3>
    <p>At <span class="num">10+</span> successful sim evals, offer Jetson deploy pack + OTA update service. One-time $1,200 + $300/mo recurring.</p>
  </div>
</div>

<h2>Q2 2026 Expansion Plan by Partner</h2>
<div class="chart-wrap">
  <table>
    <thead>
      <tr>
        <th>Partner</th>
        <th>Current MRR</th>
        <th>Q2 Target</th>
        <th>Expansion $</th>
        <th>Primary Lever</th>
        <th>Trigger Condition</th>
        <th>Priority</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td><strong>Physical Intelligence (PI)</strong></td>
        <td>$4,200</td>
        <td>$12,600</td>
        <td style="color:#4ade80">+$8,400</td>
        <td>Task Breadth + Data Tier</td>
        <td>500+ demos/mo, 3 task types active</td>
        <td><span class="tag high">HIGH</span></td>
      </tr>
      <tr>
        <td><strong>Covariant</strong></td>
        <td>$3,600</td>
        <td>$7,800</td>
        <td style="color:#4ade80">+$4,200</td>
        <td>Inference Scale</td>
        <td>Latency P95 &gt; 240ms for 10 days</td>
        <td><span class="tag high">HIGH</span></td>
      </tr>
      <tr>
        <td><strong>Machina Labs</strong></td>
        <td>$2,800</td>
        <td>$8,800</td>
        <td style="color:#4ade80">+$6,000</td>
        <td>Seat Expansion + Deploy Pack</td>
        <td>18/20 seats active, 12 sim evals passed</td>
        <td><span class="tag high">HIGH</span></td>
      </tr>
      <tr>
        <td><strong>1X Technologies</strong></td>
        <td>$1,800</td>
        <td>$3,900</td>
        <td style="color:#fbbf24">+$2,100</td>
        <td>Task Breadth</td>
        <td>90-day mark reached, 1 task deployed</td>
        <td><span class="tag med">MED</span></td>
      </tr>
      <tr>
        <td><strong>Apptronik</strong></td>
        <td>$2,100</td>
        <td>$5,700</td>
        <td style="color:#fbbf24">+$3,600</td>
        <td>Data Volume + Deploy Pack</td>
        <td>480 demos/mo (near threshold)</td>
        <td><span class="tag med">MED</span></td>
      </tr>
    </tbody>
  </table>
</div>

<h2>Q2 Upsell Pipeline (SVG)</h2>
<div class="chart-wrap">
  <svg width="100%" height="240" viewBox="0 0 720 240">
    <!-- X axis -->
    <line x1="60" y1="190" x2="700" y2="190" stroke="#334155" stroke-width="1"/>
    <!-- Y axis -->
    <line x1="60" y1="10" x2="60" y2="190" stroke="#334155" stroke-width="1"/>
    <!-- Y labels: scale 0-10k -> 0-180px -->
    <text x="55" y="15" text-anchor="end" fill="#64748b" font-size="10">$10k</text>
    <text x="55" y="55" text-anchor="end" fill="#64748b" font-size="10">$7k</text>
    <text x="55" y="100" text-anchor="end" fill="#64748b" font-size="10">$4k</text>
    <text x="55" y="145" text-anchor="end" fill="#64748b" font-size="10">$2k</text>
    <text x="55" y="193" text-anchor="end" fill="#64748b" font-size="10">0</text>
    <!-- Grid lines -->
    <line x1="60" y1="15" x2="700" y2="15" stroke="#1e293b" stroke-width="1"/>
    <line x1="60" y1="55" x2="700" y2="55" stroke="#1e293b" stroke-width="1"/>
    <line x1="60" y1="100" x2="700" y2="100" stroke="#1e293b" stroke-width="1"/>
    <line x1="60" y1="145" x2="700" y2="145" stroke="#1e293b" stroke-width="1"/>
    <!-- PI bar: $8400 => 151px -->
    <rect x="80" y="39" width="90" height="151" fill="#C74634" rx="4" opacity="0.85"/>
    <text x="125" y="34" text-anchor="middle" fill="#f8fafc" font-size="11" font-weight="600">$8,400</text>
    <text x="125" y="210" text-anchor="middle" fill="#94a3b8" font-size="10">PI</text>
    <!-- Covariant: $4200 => 76px -->
    <rect x="210" y="114" width="90" height="76" fill="#38bdf8" rx="4" opacity="0.85"/>
    <text x="255" y="109" text-anchor="middle" fill="#f8fafc" font-size="11" font-weight="600">$4,200</text>
    <text x="255" y="210" text-anchor="middle" fill="#94a3b8" font-size="10">Covariant</text>
    <!-- Machina: $6000 => 108px -->
    <rect x="340" y="82" width="90" height="108" fill="#a78bfa" rx="4" opacity="0.85"/>
    <text x="385" y="77" text-anchor="middle" fill="#f8fafc" font-size="11" font-weight="600">$6,000</text>
    <text x="385" y="210" text-anchor="middle" fill="#94a3b8" font-size="10">Machina</text>
    <!-- 1X: $2100 => 38px -->
    <rect x="470" y="152" width="90" height="38" fill="#fbbf24" rx="4" opacity="0.85"/>
    <text x="515" y="147" text-anchor="middle" fill="#f8fafc" font-size="11" font-weight="600">$2,100</text>
    <text x="515" y="210" text-anchor="middle" fill="#94a3b8" font-size="10">1X</text>
    <!-- Apptronik: $3600 => 65px -->
    <rect x="600" y="125" width="90" height="65" fill="#4ade80" rx="4" opacity="0.85"/>
    <text x="645" y="120" text-anchor="middle" fill="#f8fafc" font-size="11" font-weight="600">$3,600</text>
    <text x="645" y="210" text-anchor="middle" fill="#94a3b8" font-size="10">Apptronik</text>
    <!-- Total label -->
    <text x="380" y="228" text-anchor="middle" fill="#38bdf8" font-size="12" font-weight="600">Total Q2 Expansion: $24,300</text>
  </svg>
</div>

<h2>Usage-Triggered Conversation Guide</h2>
<div class="chart-wrap">
  <table>
    <thead>
      <tr>
        <th>Signal</th>
        <th>Threshold</th>
        <th>Action</th>
        <th>Talk Track</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td>Seat utilization</td>
        <td>&ge;80% for 14 days</td>
        <td>Schedule capacity review</td>
        <td>"Your team is getting great value — want to unblock the next 5 engineers?"</td>
      </tr>
      <tr>
        <td>Demo upload volume</td>
        <td>&ge;500/mo</td>
        <td>Introduce Enterprise Data tier</td>
        <td>"You're generating serious data — let's unlock unlimited SDG + 12-mo retention."</td>
      </tr>
      <tr>
        <td>Latency P95</td>
        <td>&gt;240ms for 10 days</td>
        <td>Propose dedicated cluster</td>
        <td>"We can guarantee &lt;200ms with a dedicated inference node — worth a look?"</td>
      </tr>
      <tr>
        <td>Sim eval pass count</td>
        <td>&ge;10 passed evals</td>
        <td>Offer Deploy Pack</td>
        <td>"You've validated the model — ready to ship to hardware? Jetson pack takes 30 min."</td>
      </tr>
      <tr>
        <td>Time since onboarding</td>
        <td>90 days</td>
        <td>Multi-task bundle pitch</td>
        <td>"You've mastered pick-place — let's add inspection + handover in one fine-tune run."</td>
      </tr>
    </tbody>
  </table>
</div>

<p class="footer">OCI Robot Cloud — Partner Expansion Playbook | Port 8951 | Q2 2026 Target: $24,300 MRR Expansion</p>
</body>
</html>
"""

if USE_FASTAPI:
    app = FastAPI(title="Partner Expansion Playbook")

    @app.get("/", response_class=HTMLResponse)
    async def index():
        return HTML

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "partner_expansion_playbook", "port": 8951}

    @app.get("/api/pipeline")
    async def pipeline():
        return {
            "q2_target_usd": 24300,
            "partners": [
                {"name": "Physical Intelligence", "expansion": 8400, "lever": "Task Breadth + Data Tier", "priority": "HIGH"},
                {"name": "Covariant", "expansion": 4200, "lever": "Inference Scale", "priority": "HIGH"},
                {"name": "Machina Labs", "expansion": 6000, "lever": "Seat Expansion + Deploy Pack", "priority": "HIGH"},
                {"name": "1X Technologies", "expansion": 2100, "lever": "Task Breadth", "priority": "MED"},
                {"name": "Apptronik", "expansion": 3600, "lever": "Data Volume + Deploy Pack", "priority": "MED"},
            ],
            "expansion_levers": 5,
        }

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
        uvicorn.run(app, host="0.0.0.0", port=8951)
    else:
        server = HTTPServer(("0.0.0.0", 8951), Handler)
        print("Serving on http://0.0.0.0:8951")
        server.serve_forever()
