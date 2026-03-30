"""ROI Attribution Dashboard — OCI Robot Cloud (port 8597)"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

from http.server import HTTPServer, BaseHTTPRequestHandler


def build_html() -> str:
    return """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ROI Attribution Dashboard — OCI Robot Cloud</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background: #0f172a;
    color: #e2e8f0;
    font-family: 'Segoe UI', system-ui, sans-serif;
    padding: 24px;
  }
  h1 { color: #C74634; font-size: 1.8rem; margin-bottom: 4px; }
  .subtitle { color: #94a3b8; font-size: 0.9rem; margin-bottom: 28px; }
  .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }
  .card {
    background: #1e293b;
    border: 1px solid #334155;
    border-radius: 12px;
    padding: 20px;
  }
  .card.full { grid-column: 1 / -1; }
  .card h2 { color: #C74634; font-size: 1rem; margin-bottom: 16px; }
  .metrics-grid { display: grid; grid-template-columns: repeat(4,1fr); gap: 12px; margin-top: 24px; }
  .metric {
    background: #0f172a;
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 14px;
    text-align: center;
  }
  .metric .val { color: #38bdf8; font-size: 1.5rem; font-weight: 700; }
  .metric .lbl { color: #94a3b8; font-size: 0.75rem; margin-top: 4px; }
  svg text { font-family: 'Segoe UI', system-ui, sans-serif; }
  .footer { color: #475569; font-size: 0.75rem; margin-top: 24px; text-align: center; }
</style>
</head>
<body>

<h1>ROI Attribution Dashboard</h1>
<p class="subtitle">Per-Partner Investment vs Revenue, Shapley Attribution &amp; Portfolio Quadrant Analysis</p>

<div class="grid">

  <!-- Chart 1: Waterfall ROI per Partner -->
  <div class="card">
    <h2>Per-Partner ROI Waterfall (Investment vs Revenue)</h2>
    <svg viewBox="0 0 420 240" width="100%">
      <!-- axes -->
      <line x1="60" y1="10" x2="60" y2="190" stroke="#334155" stroke-width="1"/>
      <line x1="60" y1="190" x2="410" y2="190" stroke="#334155" stroke-width="1"/>

      <!-- y-axis labels (0 to 400k) -->
      <text x="52" y="193" fill="#94a3b8" font-size="9" text-anchor="end">$0</text>
      <text x="52" y="144" fill="#94a3b8" font-size="9" text-anchor="end">$100k</text>
      <text x="52" y="95"  fill="#94a3b8" font-size="9" text-anchor="end">$200k</text>
      <text x="52" y="46"  fill="#94a3b8" font-size="9" text-anchor="end">$300k</text>
      <line x1="60" y1="144" x2="410" y2="144" stroke="#1e3a5f" stroke-width="0.5" stroke-dasharray="4,3"/>
      <line x1="60" y1="95"  x2="410" y2="95"  stroke="#1e3a5f" stroke-width="0.5" stroke-dasharray="4,3"/>
      <line x1="60" y1="46"  x2="410" y2="46"  stroke="#1e3a5f" stroke-width="0.5" stroke-dasharray="4,3"/>

      <!-- scale: 0→190, 300k→46; per 100k=(190-46)/3=48px -->

      <!-- PI: invest=$80k→39px bar from 190, revenue=$256k→PI 3.2x=123px bar -->
      <!-- invest: height=80/100*48=38.4, y=190-38=152 -->
      <!-- revenue: height=256/100*48=122.9, y=190-123=67 -->
      <rect x="75"  y="152" width="30" height="38" fill="#C74634" rx="2"/>
      <rect x="107" y="67"  width="30" height="123" fill="#22c55e" rx="2"/>
      <text x="90"  y="148" fill="#C74634" font-size="9" text-anchor="middle">$80k</text>
      <text x="122" y="63"  fill="#22c55e" font-size="9" text-anchor="middle">$256k</text>
      <text x="98"  y="215" fill="#38bdf8" font-size="10" text-anchor="middle" font-weight="600">PI</text>
      <text x="98"  y="227" fill="#22c55e" font-size="9" text-anchor="middle">3.2x ROI</text>

      <!-- BotWorks: invest=$90k, revenue=$99k (1.1x) -->
      <rect x="175" y="147" width="30" height="43" fill="#C74634" rx="2"/>
      <rect x="207" y="143" width="30" height="47" fill="#f59e0b" rx="2"/>
      <text x="190" y="143" fill="#C74634" font-size="9" text-anchor="middle">$90k</text>
      <text x="222" y="139" fill="#f59e0b" font-size="9" text-anchor="middle">$99k</text>
      <text x="198" y="215" fill="#38bdf8" font-size="10" text-anchor="middle" font-weight="600">BotWorks</text>
      <text x="198" y="227" fill="#f59e0b" font-size="9" text-anchor="middle">1.1x ROI</text>

      <!-- 1X: invest=$75k, revenue=$60k (0.8x) -->
      <rect x="275" y="154" width="30" height="36" fill="#C74634" rx="2"/>
      <rect x="307" y="161" width="30" height="29" fill="#ef4444" rx="2"/>
      <text x="290" y="150" fill="#C74634" font-size="9" text-anchor="middle">$75k</text>
      <text x="322" y="157" fill="#ef4444" font-size="9" text-anchor="middle">$60k</text>
      <text x="298" y="215" fill="#38bdf8" font-size="10" text-anchor="middle" font-weight="600">1X</text>
      <text x="298" y="227" fill="#ef4444" font-size="9" text-anchor="middle">0.8x ROI</text>

      <!-- legend -->
      <rect x="68" y="200" width="10" height="8" fill="#C74634" rx="1"/>
      <text x="82" y="207" fill="#94a3b8" font-size="8">Investment (Compute+Support+Onboarding)</text>
      <rect x="290" y="200" width="10" height="8" fill="#22c55e" rx="1"/>
      <text x="304" y="207" fill="#94a3b8" font-size="8">Revenue</text>
    </svg>
  </div>

  <!-- Chart 2: Shapley Value Attribution -->
  <div class="card">
    <h2>Shapley Value Attribution to Revenue</h2>
    <svg viewBox="0 0 420 240" width="100%">
      <!-- horizontal bar chart -->
      <!-- axes -->
      <line x1="110" y1="10" x2="110" y2="185" stroke="#334155" stroke-width="1"/>
      <line x1="110" y1="185" x2="400" y2="185" stroke="#334155" stroke-width="1"/>

      <!-- x-axis labels (0 to 40%) -->
      <text x="110" y="198" fill="#94a3b8" font-size="9" text-anchor="middle">0%</text>
      <text x="182" y="198" fill="#94a3b8" font-size="9" text-anchor="middle">10%</text>
      <text x="254" y="198" fill="#94a3b8" font-size="9" text-anchor="middle">20%</text>
      <text x="326" y="198" fill="#94a3b8" font-size="9" text-anchor="middle">30%</text>
      <text x="398" y="198" fill="#94a3b8" font-size="9" text-anchor="middle">40%</text>
      <line x1="182" y1="10" x2="182" y2="185" stroke="#1e3a5f" stroke-width="0.5" stroke-dasharray="4,3"/>
      <line x1="254" y1="10" x2="254" y2="185" stroke="#1e3a5f" stroke-width="0.5" stroke-dasharray="4,3"/>
      <line x1="326" y1="10" x2="326" y2="185" stroke="#1e3a5f" stroke-width="0.5" stroke-dasharray="4,3"/>

      <!-- scale: 0→110, 40%→398; per%=(398-110)/40=7.2px -->

      <!-- compute_hrs: 35% → width=35*7.2=252 -->
      <rect x="110" y="20" width="252" height="26" fill="#38bdf8" rx="3"/>
      <text x="105" y="37" fill="#94a3b8" font-size="9" text-anchor="end">Compute hrs</text>
      <text x="366" y="37" fill="#38bdf8" font-size="9">35%</text>

      <!-- SR: 28% → width=28*7.2=201.6 -->
      <rect x="110" y="60" width="202" height="26" fill="#22d3ee" rx="3"/>
      <text x="105" y="77" fill="#94a3b8" font-size="9" text-anchor="end">Success Rate</text>
      <text x="316" y="77" fill="#22d3ee" font-size="9">28%</text>

      <!-- demos: 22% → width=22*7.2=158.4 -->
      <rect x="110" y="100" width="158" height="26" fill="#0ea5e9" rx="3"/>
      <text x="105" y="117" fill="#94a3b8" font-size="9" text-anchor="end">Demos</text>
      <text x="272" y="117" fill="#0ea5e9" font-size="9">22%</text>

      <!-- API_calls: 15% → width=15*7.2=108 -->
      <rect x="110" y="140" width="108" height="26" fill="#7dd3fc" rx="3"/>
      <text x="105" y="157" fill="#94a3b8" font-size="9" text-anchor="end">API Calls</text>
      <text x="222" y="157" fill="#7dd3fc" font-size="9">15%</text>

      <!-- total annotation -->
      <text x="230" y="215" fill="#94a3b8" font-size="9" text-anchor="middle">Shapley attribution sums to 100% across all features</text>
    </svg>
  </div>

  <!-- Chart 3: ROI Scatter with Quadrants -->
  <div class="card full">
    <h2>Partner ROI Scatter — Quadrant Analysis (Bubble = ARR)</h2>
    <svg viewBox="0 0 760 280" width="100%">
      <!-- axes -->
      <line x1="80" y1="20" x2="80" y2="220" stroke="#334155" stroke-width="1"/>
      <line x1="80" y1="220" x2="720" y2="220" stroke="#334155" stroke-width="1"/>

      <!-- x-axis: Investment ($0 to $200k) -->
      <text x="400" y="248" fill="#94a3b8" font-size="11" text-anchor="middle">Investment ($k)</text>
      <text x="80"  y="234" fill="#94a3b8" font-size="9" text-anchor="middle">0</text>
      <text x="240" y="234" fill="#94a3b8" font-size="9" text-anchor="middle">50</text>
      <text x="400" y="234" fill="#94a3b8" font-size="9" text-anchor="middle">100</text>
      <text x="560" y="234" fill="#94a3b8" font-size="9" text-anchor="middle">150</text>
      <text x="720" y="234" fill="#94a3b8" font-size="9" text-anchor="middle">200</text>

      <!-- y-axis: Revenue ($0 to $400k) -->
      <text x="30" y="120" fill="#94a3b8" font-size="11" text-anchor="middle" transform="rotate(-90,30,120)">Revenue ($k)</text>
      <text x="72" y="223" fill="#94a3b8" font-size="9" text-anchor="end">0</text>
      <text x="72" y="173" fill="#94a3b8" font-size="9" text-anchor="end">100</text>
      <text x="72" y="123" fill="#94a3b8" font-size="9" text-anchor="end">200</text>
      <text x="72" y="73"  fill="#94a3b8" font-size="9" text-anchor="end">300</text>
      <text x="72" y="23"  fill="#94a3b8" font-size="9" text-anchor="end">400</text>

      <!-- scale x: 0→80, 200k→720; per k=(720-80)/200=3.2px -->
      <!-- scale y: 0→220, 400k→20; per k=(220-20)/400=0.5px -->

      <!-- Quadrant dividers (at investment=100k → x=80+100*3.2=400; revenue=200k → y=220-200*0.5=120) -->
      <line x1="400" y1="20"  x2="400" y2="220" stroke="#38bdf8" stroke-width="1" stroke-dasharray="6,4" opacity="0.4"/>
      <line x1="80"  y1="120" x2="720" y2="120" stroke="#38bdf8" stroke-width="1" stroke-dasharray="6,4" opacity="0.4"/>

      <!-- Quadrant labels -->
      <text x="230" y="40"  fill="#22c55e" font-size="10" opacity="0.6">INVEST</text>
      <text x="510" y="40"  fill="#38bdf8" font-size="10" opacity="0.6">GROW</text>
      <text x="230" y="210" fill="#f59e0b" font-size="10" opacity="0.6">EXIT</text>
      <text x="510" y="210" fill="#94a3b8" font-size="10" opacity="0.6">MAINTAIN</text>

      <!-- Partner 1: PI — invest=$80k, revenue=$256k, ARR=$320k (large bubble) -->
      <!-- x=80+80*3.2=336, y=220-256*0.5=92, r=320/15=21 -->
      <circle cx="336" cy="92" r="22" fill="#22c55e" opacity="0.75"/>
      <text x="336" cy="92" y="96" fill="#0f172a" font-size="9" text-anchor="middle" font-weight="700">PI</text>
      <text x="336" y="72" fill="#22c55e" font-size="9" text-anchor="middle">3.2x</text>

      <!-- Partner 2: BotWorks — invest=$90k, revenue=$99k, ARR=$120k -->
      <!-- x=80+90*3.2=368, y=220-99*0.5=170.5, r=120/15=8 -->
      <circle cx="368" cy="170" r="10" fill="#94a3b8" opacity="0.75"/>
      <text x="368" y="174" fill="#0f172a" font-size="8" text-anchor="middle" font-weight="700">BW</text>
      <text x="368" y="158" fill="#94a3b8" font-size="9" text-anchor="middle">1.1x</text>

      <!-- Partner 3: 1X — invest=$75k, revenue=$60k, ARR=$70k -->
      <!-- x=80+75*3.2=320, y=220-60*0.5=190, r=70/15=4.7 -->
      <circle cx="320" cy="190" r="8" fill="#ef4444" opacity="0.75"/>
      <text x="320" y="194" fill="#fff" font-size="7" text-anchor="middle" font-weight="700">1X</text>
      <text x="320" y="178" fill="#ef4444" font-size="9" text-anchor="middle">0.8x</text>

      <!-- Partner 4: Apptronik — invest=$120k, revenue=$240k, ARR=$280k -->
      <!-- x=80+120*3.2=464, y=220-240*0.5=100, r=280/15=18.7 -->
      <circle cx="464" cy="100" r="19" fill="#0ea5e9" opacity="0.75"/>
      <text x="464" y="104" fill="#0f172a" font-size="8" text-anchor="middle" font-weight="700">APT</text>
      <text x="464" y="80" fill="#0ea5e9" font-size="9" text-anchor="middle">2.0x</text>

      <!-- Partner 5: Agility — invest=$140k, revenue=$196k, ARR=$220k -->
      <!-- x=80+140*3.2=528, y=220-196*0.5=122, r=220/15=14.7 -->
      <circle cx="528" cy="122" r="15" fill="#a78bfa" opacity="0.75"/>
      <text x="528" y="126" fill="#0f172a" font-size="8" text-anchor="middle" font-weight="700">AGI</text>
      <text x="528" y="104" fill="#a78bfa" font-size="9" text-anchor="middle">1.4x</text>

      <!-- legend -->
      <text x="85" y="265" fill="#94a3b8" font-size="8">Bubble size = ARR</text>
      <circle cx="220" cy="261" r="6"  fill="#22c55e" opacity="0.75"/><text x="230" y="265" fill="#22c55e" font-size="8">PI (GROW)</text>
      <circle cx="290" cy="261" r="5"  fill="#94a3b8" opacity="0.75"/><text x="299" y="265" fill="#94a3b8" font-size="8">BotWorks (MAINTAIN)</text>
      <circle cx="400" cy="261" r="4"  fill="#ef4444" opacity="0.75"/><text x="408" y="265" fill="#ef4444" font-size="8">1X (WATCH)</text>
      <circle cx="470" cy="261" r="5"  fill="#0ea5e9" opacity="0.75"/><text x="479" y="265" fill="#0ea5e9" font-size="8">Apptronik</text>
      <circle cx="550" cy="261" r="5"  fill="#a78bfa" opacity="0.75"/><text x="559" y="265" fill="#a78bfa" font-size="8">Agility</text>
    </svg>
  </div>

</div>

<!-- Metrics -->
<div class="metrics-grid">
  <div class="metric">
    <div class="val">3.2x</div>
    <div class="lbl">PI ROI — GROW quadrant</div>
  </div>
  <div class="metric">
    <div class="val">MAINTAIN</div>
    <div class="lbl">BotWorks (1.1x ROI)</div>
  </div>
  <div class="metric">
    <div class="val">WATCH</div>
    <div class="lbl">1X (0.8x ROI — below threshold)</div>
  </div>
  <div class="metric">
    <div class="val">2.4x</div>
    <div class="lbl">Platform blended ROI</div>
  </div>
</div>

<p class="footer">OCI Robot Cloud — ROI Attribution Dashboard | Port 8597 | Cycle 134B</p>
</body>
</html>
"""


if USE_FASTAPI:
    app = FastAPI(
        title="ROI Attribution Dashboard",
        description="Per-partner ROI waterfall, Shapley attribution, and quadrant scatter analysis",
        version="1.0.0",
    )

    @app.get("/", response_class=HTMLResponse)
    async def root():
        return HTMLResponse(content=build_html())

    @app.get("/health")
    async def health():
        return {
            "status": "ok",
            "service": "roi_attribution_dashboard",
            "port": 8597,
            "version": "1.0.0",
            "metrics": {
                "pi_roi": 3.2,
                "botworks_roi": 1.1,
                "onex_roi": 0.8,
                "platform_blended_roi": 2.4,
                "top_shapley_feature": "compute_hrs",
                "top_shapley_pct": 35.0,
            },
        }

    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=8597)

else:
    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/health":
                body = b'{"status":"ok","service":"roi_attribution_dashboard","port":8597}'
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
            else:
                body = build_html().encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            pass

    if __name__ == "__main__":
        print("FastAPI not available — using stdlib HTTPServer on port 8597")
        server = HTTPServer(("0.0.0.0", 8597), _Handler)
        server.serve_forever()
