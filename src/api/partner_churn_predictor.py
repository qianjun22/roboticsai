# Partner Churn Predictor — port 8957
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
<html>
<head>
<meta charset="UTF-8">
<title>Partner Churn Predictor</title>
<style>
  body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; margin: 0; padding: 24px; }
  h1 { color: #C74634; font-size: 2rem; margin-bottom: 4px; }
  h2 { color: #38bdf8; font-size: 1.25rem; margin: 24px 0 12px; }
  .card { background: #1e293b; border-radius: 10px; padding: 20px; margin-bottom: 20px; }
  .meta { color: #94a3b8; font-size: 0.9rem; margin-bottom: 16px; }
  table { width: 100%; border-collapse: collapse; font-size: 0.9rem; }
  th { color: #38bdf8; text-align: left; padding: 8px 12px; border-bottom: 1px solid #334155; }
  td { padding: 8px 12px; border-bottom: 1px solid #1e293b; }
  tr:hover td { background: #273449; }
  .badge { display: inline-block; padding: 2px 10px; border-radius: 12px; font-size: 0.8rem; font-weight: 600; }
  .low    { background: #14532d; color: #4ade80; }
  .medium { background: #422006; color: #fb923c; }
  .high   { background: #3b0f0a; color: #f87171; }
  .stat-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; }
  .stat { background: #0f172a; border-radius: 8px; padding: 14px; text-align: center; }
  .stat .val { font-size: 1.8rem; font-weight: 700; color: #38bdf8; }
  .stat .lbl { font-size: 0.78rem; color: #64748b; margin-top: 4px; }
</style>
</head>
<body>
<h1>Partner Churn Predictor</h1>
<p class="meta">Port 8957 &nbsp;|&nbsp; 8-signal ML model &nbsp;|&nbsp; 5 active design partners &nbsp;|&nbsp; Real-time risk scoring</p>

<div class="card">
  <h2>Fleet Summary</h2>
  <div class="stat-grid">
    <div class="stat"><div class="val">5</div><div class="lbl">Partners Tracked</div></div>
    <div class="stat"><div class="val">8</div><div class="lbl">Churn Signals</div></div>
    <div class="stat"><div class="val">13.6%</div><div class="lbl">Portfolio Avg Churn Risk</div></div>
    <div class="stat"><div class="val">$18.4K</div><div class="lbl">Max Intervention ROI (1X)</div></div>
  </div>
</div>

<div class="card">
  <h2>Churn Probability by Partner</h2>
  <svg width="100%" height="280" viewBox="0 0 820 280">
    <defs>
      <linearGradient id="lowg" x1="0" y1="0" x2="1" y2="0">
        <stop offset="0%" stop-color="#166534"/>
        <stop offset="100%" stop-color="#4ade80"/>
      </linearGradient>
      <linearGradient id="medg" x1="0" y1="0" x2="1" y2="0">
        <stop offset="0%" stop-color="#7c2d12"/>
        <stop offset="100%" stop-color="#fb923c"/>
      </linearGradient>
      <linearGradient id="highg" x1="0" y1="0" x2="1" y2="0">
        <stop offset="0%" stop-color="#7f1d1d"/>
        <stop offset="100%" stop-color="#f87171"/>
      </linearGradient>
    </defs>
    <!-- y axis labels -->
    <text x="30" y="40"  fill="#94a3b8" font-size="11" text-anchor="middle">PI</text>
    <text x="30" y="90"  fill="#94a3b8" font-size="11" text-anchor="middle">Covariant</text>
    <text x="30" y="140" fill="#94a3b8" font-size="11" text-anchor="middle">Machina</text>
    <text x="30" y="190" fill="#94a3b8" font-size="11" text-anchor="middle">1X</text>
    <text x="30" y="240" fill="#94a3b8" font-size="11" text-anchor="middle">Apptronik</text>
    <!-- x axis -->
    <line x1="80" y1="20" x2="80" y2="255" stroke="#334155" stroke-width="1"/>
    <line x1="80" y1="255" x2="810" y2="255" stroke="#334155" stroke-width="1"/>
    <!-- x grid: 0 10 20 30 40% => 0 73 146 219 292px (scale: 730px=40%) -->
    <text x="80"  y="268" fill="#64748b" font-size="10" text-anchor="middle">0%</text>
    <text x="262" y="268" fill="#64748b" font-size="10" text-anchor="middle">10%</text>
    <text x="445" y="268" fill="#64748b" font-size="10" text-anchor="middle">20%</text>
    <text x="627" y="268" fill="#64748b" font-size="10" text-anchor="middle">30%</text>
    <line x1="262" y1="20" x2="262" y2="255" stroke="#1e293b" stroke-dasharray="3,3"/>
    <line x1="445" y1="20" x2="445" y2="255" stroke="#1e293b" stroke-dasharray="3,3"/>
    <line x1="627" y1="20" x2="627" y2="255" stroke="#1e293b" stroke-dasharray="3,3"/>
    <!-- PI 2%: 2/40*730=36.5 -->
    <rect x="80" y="22" width="36" height="30" fill="url(#lowg)" rx="4"/>
    <text x="122" y="42" fill="#4ade80" font-size="12" font-weight="600">2%</text>
    <!-- Covariant 5%: 5/40*730=91.25 -->
    <rect x="80" y="72" width="91" height="30" fill="url(#lowg)" rx="4"/>
    <text x="177" y="92" fill="#4ade80" font-size="12" font-weight="600">5%</text>
    <!-- Machina 18%: 18/40*730=328.5 -->
    <rect x="80" y="122" width="328" height="30" fill="url(#medg)" rx="4"/>
    <text x="414" y="142" fill="#fb923c" font-size="12" font-weight="600">18%</text>
    <!-- 1X 31%: 31/40*730=565.75 -->
    <rect x="80" y="172" width="565" height="30" fill="url(#highg)" rx="4"/>
    <text x="651" y="192" fill="#f87171" font-size="12" font-weight="600">31%</text>
    <!-- Apptronik 12%: 12/40*730=219 -->
    <rect x="80" y="222" width="219" height="30" fill="url(#medg)" rx="4"/>
    <text x="305" y="242" fill="#fb923c" font-size="12" font-weight="600">12%</text>
    <text x="430" y="14" fill="#e2e8f0" font-size="13" text-anchor="middle" font-weight="600">30-Day Churn Probability (%)</text>
  </svg>
</div>

<div class="card">
  <h2>Intervention Value Chart</h2>
  <svg width="100%" height="240" viewBox="0 0 820 240">
    <defs>
      <linearGradient id="roig" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="#C74634"/>
        <stop offset="100%" stop-color="#7f1d1d"/>
      </linearGradient>
    </defs>
    <line x1="80" y1="20" x2="80" y2="195" stroke="#334155" stroke-width="1"/>
    <line x1="80" y1="195" x2="800" y2="195" stroke="#334155" stroke-width="1"/>
    <!-- y grid: 0 5000 10000 15000 20000 -->
    <text x="70" y="199" fill="#64748b" font-size="10" text-anchor="end">$0</text>
    <text x="70" y="151" fill="#64748b" font-size="10" text-anchor="end">$5K</text>
    <text x="70" y="103" fill="#64748b" font-size="10" text-anchor="end">$10K</text>
    <text x="70" y="55"  fill="#64748b" font-size="10" text-anchor="end">$15K</text>
    <line x1="80" y1="147" x2="800" y2="147" stroke="#1e293b" stroke-dasharray="3,3"/>
    <line x1="80" y1="99"  x2="800" y2="99"  stroke="#1e293b" stroke-dasharray="3,3"/>
    <line x1="80" y1="51"  x2="800" y2="51"  stroke="#1e293b" stroke-dasharray="3,3"/>
    <!-- scale: 175px = $20K => $1K = 8.75px; bars at 195 - val*8.75/1000 -->
    <!-- PI: 0.02*$12K ACV = $240 => bar tiny -->
    <!-- Covariant: 0.05*$18K = $900 -->
    <!-- Machina: 0.18*$22K = $3960 -->
    <!-- 1X: 0.31*$24K * reduce_cost_factor = $18400 (given) => height=161 -->
    <!-- Apptronik: 0.12*$19K = $2280 -->
    <!-- ROI = churn_prob * ACV - intervention_cost -->
    <rect x="100" y="193" width="80" height="2"   fill="url(#roig)" rx="3"/>
    <rect x="240" y="187" width="80" height="8"   fill="url(#roig)" rx="3"/>
    <rect x="380" y="160" width="80" height="35"  fill="url(#roig)" rx="3"/>
    <rect x="520" y="34"  width="80" height="161" fill="url(#roig)" rx="3"/>
    <rect x="660" y="175" width="80" height="20"  fill="url(#roig)" rx="3"/>
    <!-- labels -->
    <text x="140" y="213" fill="#94a3b8" font-size="10" text-anchor="middle">PI</text>
    <text x="280" y="213" fill="#94a3b8" font-size="10" text-anchor="middle">Covariant</text>
    <text x="420" y="213" fill="#94a3b8" font-size="10" text-anchor="middle">Machina</text>
    <text x="560" y="213" fill="#94a3b8" font-size="10" text-anchor="middle">1X</text>
    <text x="700" y="213" fill="#94a3b8" font-size="10" text-anchor="middle">Apptronik</text>
    <!-- value labels -->
    <text x="140" y="190" fill="#94a3b8"  font-size="10" text-anchor="middle">$240</text>
    <text x="280" y="184" fill="#fb923c"  font-size="10" text-anchor="middle">$900</text>
    <text x="420" y="157" fill="#fb923c"  font-size="10" text-anchor="middle">$3,960</text>
    <text x="560" y="30"  fill="#f87171"  font-size="11" text-anchor="middle" font-weight="700">$18,400</text>
    <text x="700" y="172" fill="#fb923c"  font-size="10" text-anchor="middle">$2,280</text>
    <text x="430" y="14" fill="#e2e8f0" font-size="13" text-anchor="middle" font-weight="600">Intervention ROI by Partner ($)</text>
  </svg>
</div>

<div class="card">
  <h2>8-Signal Model Features</h2>
  <table>
    <tr><th>#</th><th>Signal</th><th>Weight</th><th>Description</th></tr>
    <tr><td>1</td><td>API call frequency delta</td><td>0.22</td><td>30-day drop in API calls vs prior 30 days</td></tr>
    <tr><td>2</td><td>Support ticket volume</td><td>0.18</td><td>Open/unresolved tickets in last 14 days</td></tr>
    <tr><td>3</td><td>NPS / CSAT score</td><td>0.16</td><td>Latest survey score (0–10 scale)</td></tr>
    <tr><td>4</td><td>Executive engagement</td><td>0.14</td><td>Days since last exec-level touchpoint</td></tr>
    <tr><td>5</td><td>Contract renewal proximity</td><td>0.12</td><td>Days to contract expiry</td></tr>
    <tr><td>6</td><td>Integration breadth</td><td>0.09</td><td>Number of OCI services actively used</td></tr>
    <tr><td>7</td><td>Competitive signal</td><td>0.06</td><td>Keyword mentions of competitors in support/Slack</td></tr>
    <tr><td>8</td><td>ROI realization</td><td>0.03</td><td>Customer-reported automation ROI vs target</td></tr>
  </table>
</div>

<div class="card">
  <h2>Risk Detail</h2>
  <table>
    <tr><th>Partner</th><th>Churn Prob</th><th>Risk Level</th><th>Top Signal</th><th>Intervention ROI</th><th>Recommended Action</th></tr>
    <tr>
      <td>PI</td><td>2%</td>
      <td><span class="badge low">Low</span></td>
      <td>Contract renewal proximity</td><td>$240</td><td>Quarterly check-in</td>
    </tr>
    <tr>
      <td>Covariant</td><td>5%</td>
      <td><span class="badge low">Low</span></td>
      <td>Support ticket volume</td><td>$900</td><td>Technical office hours</td>
    </tr>
    <tr>
      <td>Machina</td><td>18%</td>
      <td><span class="badge medium">Medium</span></td>
      <td>API call frequency delta</td><td>$3,960</td><td>Executive touchpoint + roadmap share</td>
    </tr>
    <tr>
      <td>1X</td><td>31%</td>
      <td><span class="badge high">High</span></td>
      <td>NPS score + competitive signal</td><td>$18,400</td><td>Urgent EBC + custom success plan</td>
    </tr>
    <tr>
      <td>Apptronik</td><td>12%</td>
      <td><span class="badge medium">Medium</span></td>
      <td>Executive engagement lapse</td><td>$2,280</td><td>Schedule exec sync within 7 days</td>
    </tr>
  </table>
</div>

<p style="color:#334155;font-size:0.75rem;margin-top:24px;">Partner Churn Predictor &mdash; OCI Robot Cloud &mdash; Port 8957</p>
</body>
</html>
"""

if USE_FASTAPI:
    app = FastAPI(title="Partner Churn Predictor")

    @app.get("/", response_class=HTMLResponse)
    async def root():
        return HTML

    @app.get("/health")
    async def health():
        return {
            "status": "ok",
            "service": "partner_churn_predictor",
            "port": 8957,
            "partners": 5,
            "signals": 8,
            "portfolio_avg_churn_risk": 0.136,
            "high_risk_partners": ["1X"],
        }

    @app.get("/predictions")
    async def predictions():
        data = [
            {"partner": "PI",         "churn_prob": 0.02, "risk": "low",    "intervention_roi": 240},
            {"partner": "Covariant",   "churn_prob": 0.05, "risk": "low",    "intervention_roi": 900},
            {"partner": "Machina",     "churn_prob": 0.18, "risk": "medium", "intervention_roi": 3960},
            {"partner": "1X",          "churn_prob": 0.31, "risk": "high",   "intervention_roi": 18400},
            {"partner": "Apptronik",   "churn_prob": 0.12, "risk": "medium", "intervention_roi": 2280},
        ]
        return {"predictions": data, "model_signals": 8}

else:
    import json
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/health":
                body = json.dumps({"status": "ok", "port": 8957}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)
            else:
                body = HTML.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(body)
        def log_message(self, *a): pass

if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8957)
    else:
        print("Serving on http://0.0.0.0:8957 (fallback HTTPServer)")
        HTTPServer(("0.0.0.0", 8957), Handler).serve_forever()
