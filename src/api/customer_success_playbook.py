# Customer Success Playbook Service — port 8675
# OCI Robot Cloud | cycle-154A

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Customer Success Playbook</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; padding: 24px; }
    h1 { color: #38bdf8; font-size: 1.6rem; margin-bottom: 4px; }
    .subtitle { color: #94a3b8; font-size: 0.85rem; margin-bottom: 28px; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(380px, 1fr)); gap: 24px; }
    .card { background: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 20px; }
    .card h2 { color: #C74634; font-size: 1rem; margin-bottom: 16px; letter-spacing: 0.03em; }
    svg { display: block; width: 100%; }
    .metrics { display: flex; flex-wrap: wrap; gap: 12px; margin-top: 24px; }
    .metric { background: #0f172a; border: 1px solid #334155; border-radius: 8px; padding: 12px 18px; flex: 1; min-width: 160px; }
    .metric .val { color: #38bdf8; font-size: 1.4rem; font-weight: 700; }
    .metric .lbl { color: #94a3b8; font-size: 0.75rem; margin-top: 2px; }
  </style>
</head>
<body>
  <h1>Customer Success Playbook</h1>
  <p class="subtitle">Port 8675 &nbsp;|&nbsp; OCI Robot Cloud &nbsp;|&nbsp; 12 Triggers &nbsp;|&nbsp; Proactive Retention Engine</p>

  <div class="grid">

    <!-- Card 1: Decision Tree -->
    <div class="card">
      <h2>Playbook Decision Tree</h2>
      <svg viewBox="0 0 420 420" xmlns="http://www.w3.org/2000/svg">
        <!-- Root: health_score -->
        <rect x="135" y="10" width="150" height="38" rx="8" fill="#1e3a5f" stroke="#38bdf8" stroke-width="1.5"/>
        <text x="210" y="33" text-anchor="middle" fill="#38bdf8" font-size="12" font-weight="bold">health_score</text>

        <!-- Branch lines from root -->
        <line x1="210" y1="48" x2="210" y2="75" stroke="#475569" stroke-width="1.5"/>
        <!-- Trigger node -->
        <rect x="135" y="75" width="150" height="38" rx="8" fill="#1e293b" stroke="#64748b" stroke-width="1.5"/>
        <text x="210" y="98" text-anchor="middle" fill="#94a3b8" font-size="11">trigger_type?</text>

        <!-- 5 branch lines -->
        <!-- branch 1: x=50 -->
        <line x1="210" y1="113" x2="210" y2="130" stroke="#475569" stroke-width="1"/>
        <line x1="210" y1="130" x2="50"  y2="130" stroke="#475569" stroke-width="1"/>
        <line x1="50"  y1="130" x2="50"  y2="155" stroke="#475569" stroke-width="1"/>
        <!-- branch 2: x=130 -->
        <line x1="210" y1="130" x2="130" y2="130" stroke="#475569" stroke-width="1"/>
        <line x1="130" y1="130" x2="130" y2="155" stroke="#475569" stroke-width="1"/>
        <!-- branch 3: x=210 -->
        <line x1="210" y1="113" x2="210" y2="155" stroke="#475569" stroke-width="1"/>
        <!-- branch 4: x=290 -->
        <line x1="210" y1="130" x2="290" y2="130" stroke="#475569" stroke-width="1"/>
        <line x1="290" y1="130" x2="290" y2="155" stroke="#475569" stroke-width="1"/>
        <!-- branch 5: x=370 -->
        <line x1="210" y1="130" x2="370" y2="130" stroke="#475569" stroke-width="1"/>
        <line x1="370" y1="130" x2="370" y2="155" stroke="#475569" stroke-width="1"/>

        <!-- Trigger boxes -->
        <!-- 1: churn_risk (red) -->
        <rect x="10"  y="155" width="80" height="34" rx="6" fill="#7f1d1d" stroke="#ef4444" stroke-width="1.5"/>
        <text x="50"  y="170" text-anchor="middle" fill="#fca5a5" font-size="8" font-weight="bold">churn</text>
        <text x="50"  y="182" text-anchor="middle" fill="#fca5a5" font-size="8">_risk</text>
        <!-- 2: low_adoption (orange) -->
        <rect x="90"  y="155" width="80" height="34" rx="6" fill="#7c2d12" stroke="#f97316" stroke-width="1.5"/>
        <text x="130" y="170" text-anchor="middle" fill="#fdba74" font-size="8" font-weight="bold">low</text>
        <text x="130" y="182" text-anchor="middle" fill="#fdba74" font-size="8">_adoption</text>
        <!-- 3: milestone (green) -->
        <rect x="170" y="155" width="80" height="34" rx="6" fill="#14532d" stroke="#22c55e" stroke-width="1.5"/>
        <text x="210" y="170" text-anchor="middle" fill="#86efac" font-size="8" font-weight="bold">milestone</text>
        <text x="210" y="182" text-anchor="middle" fill="#86efac" font-size="8">_achieved</text>
        <!-- 4: support_spike (yellow) -->
        <rect x="250" y="155" width="80" height="34" rx="6" fill="#713f12" stroke="#eab308" stroke-width="1.5"/>
        <text x="290" y="170" text-anchor="middle" fill="#fde68a" font-size="8" font-weight="bold">support</text>
        <text x="290" y="182" text-anchor="middle" fill="#fde68a" font-size="8">_spike</text>
        <!-- 5: renewal (blue) -->
        <rect x="330" y="155" width="80" height="34" rx="6" fill="#1e3a5f" stroke="#38bdf8" stroke-width="1.5"/>
        <text x="370" y="170" text-anchor="middle" fill="#7dd3fc" font-size="8" font-weight="bold">renewal</text>
        <text x="370" y="182" text-anchor="middle" fill="#7dd3fc" font-size="8">_90d</text>

        <!-- Action lines -->
        <line x1="50"  y1="189" x2="50"  y2="240" stroke="#475569" stroke-width="1"/>
        <line x1="130" y1="189" x2="130" y2="240" stroke="#475569" stroke-width="1"/>
        <line x1="210" y1="189" x2="210" y2="240" stroke="#475569" stroke-width="1"/>
        <line x1="290" y1="189" x2="290" y2="240" stroke="#475569" stroke-width="1"/>
        <line x1="370" y1="189" x2="370" y2="240" stroke="#475569" stroke-width="1"/>

        <!-- Action boxes -->
        <!-- 1: exec call (red/critical) -->
        <rect x="10"  y="240" width="80" height="40" rx="6" fill="#450a0a" stroke="#C74634" stroke-width="2"/>
        <text x="50"  y="257" text-anchor="middle" fill="#fca5a5" font-size="8">Executive</text>
        <text x="50"  y="269" text-anchor="middle" fill="#fca5a5" font-size="8">Call (78%)</text>
        <!-- 2: feature demo -->
        <rect x="90"  y="240" width="80" height="40" rx="6" fill="#431407" stroke="#f97316" stroke-width="1.5"/>
        <text x="130" y="257" text-anchor="middle" fill="#fdba74" font-size="8">Feature</text>
        <text x="130" y="269" text-anchor="middle" fill="#fdba74" font-size="8">Demo (34%)</text>
        <!-- 3: QBR -->
        <rect x="170" y="240" width="80" height="40" rx="6" fill="#052e16" stroke="#22c55e" stroke-width="1.5"/>
        <text x="210" y="257" text-anchor="middle" fill="#86efac" font-size="8">QBR +</text>
        <text x="210" y="269" text-anchor="middle" fill="#86efac" font-size="8">Upsell</text>
        <!-- 4: training -->
        <rect x="250" y="240" width="80" height="40" rx="6" fill="#422006" stroke="#eab308" stroke-width="1.5"/>
        <text x="290" y="257" text-anchor="middle" fill="#fde68a" font-size="8">Training</text>
        <text x="290" y="269" text-anchor="middle" fill="#fde68a" font-size="8">(+21% SR)</text>
        <!-- 5: dedicated CSM -->
        <rect x="330" y="240" width="80" height="40" rx="6" fill="#082f49" stroke="#38bdf8" stroke-width="2"/>
        <text x="370" y="257" text-anchor="middle" fill="#7dd3fc" font-size="8">Dedicated</text>
        <text x="370" y="269" text-anchor="middle" fill="#7dd3fc" font-size="8">CSM (91%)</text>

        <!-- Outcome lines + boxes -->
        <line x1="50"  y1="280" x2="50"  y2="330" stroke="#475569" stroke-width="1"/>
        <line x1="130" y1="280" x2="130" y2="330" stroke="#475569" stroke-width="1"/>
        <line x1="210" y1="280" x2="210" y2="330" stroke="#475569" stroke-width="1"/>
        <line x1="290" y1="280" x2="290" y2="330" stroke="#475569" stroke-width="1"/>
        <line x1="370" y1="280" x2="370" y2="330" stroke="#475569" stroke-width="1"/>

        <!-- Outcomes -->
        <rect x="10"  y="330" width="80" height="30" rx="5" fill="#1e293b" stroke="#334155"/>
        <text x="50"  y="349" text-anchor="middle" fill="#94a3b8" font-size="8">Retained</text>
        <rect x="90"  y="330" width="80" height="30" rx="5" fill="#1e293b" stroke="#334155"/>
        <text x="130" y="349" text-anchor="middle" fill="#94a3b8" font-size="8">Expanded</text>
        <rect x="170" y="330" width="80" height="30" rx="5" fill="#1e293b" stroke="#334155"/>
        <text x="210" y="349" text-anchor="middle" fill="#94a3b8" font-size="8">Upsold</text>
        <rect x="250" y="330" width="80" height="30" rx="5" fill="#1e293b" stroke="#334155"/>
        <text x="290" y="349" text-anchor="middle" fill="#94a3b8" font-size="8">Resolved</text>
        <rect x="330" y="330" width="80" height="30" rx="5" fill="#1e293b" stroke="#334155"/>
        <text x="370" y="349" text-anchor="middle" fill="#94a3b8" font-size="8">Renewed</text>

        <!-- Title -->
        <text x="210" y="410" text-anchor="middle" fill="#475569" font-size="9">12 trigger types — 5 primary branches shown</text>
      </svg>
    </div>

    <!-- Card 2: Intervention Effectiveness -->
    <div class="card">
      <h2>Intervention Effectiveness (Retention Improvement %)</h2>
      <svg viewBox="0 0 400 260" xmlns="http://www.w3.org/2000/svg">
        <!-- Axes -->
        <line x1="140" y1="20" x2="140" y2="220" stroke="#475569" stroke-width="1.5"/>
        <line x1="140" y1="220" x2="385" y2="220" stroke="#475569" stroke-width="1.5"/>
        <!-- X grid -->
        <line x1="140" y1="220" x2="385" y2="220" stroke="#1e293b" stroke-width="1"/>
        <line x1="216" y1="20"  x2="216" y2="220" stroke="#1e293b" stroke-width="1" opacity="0.5"/>
        <line x1="292" y1="20"  x2="292" y2="220" stroke="#1e293b" stroke-width="1" opacity="0.5"/>
        <line x1="368" y1="20"  x2="368" y2="220" stroke="#1e293b" stroke-width="1" opacity="0.5"/>
        <!-- X labels -->
        <text x="140" y="234" text-anchor="middle" fill="#64748b" font-size="9">0%</text>
        <text x="216" y="234" text-anchor="middle" fill="#64748b" font-size="9">25%</text>
        <text x="292" y="234" text-anchor="middle" fill="#64748b" font-size="9">50%</text>
        <text x="368" y="234" text-anchor="middle" fill="#64748b" font-size="9">75%</text>
        <!-- Bars: 5 rows, each bar width = pct/100 * 245 -->
        <!-- dedicated_CSM: 91% → 223px -->
        <rect x="141" y="28"  width="223" height="28" rx="4" fill="#38bdf8"/>
        <text x="10"  y="47"  fill="#94a3b8" font-size="9" text-anchor="start">dedicated_CSM</text>
        <text x="368" y="47"  fill="#38bdf8" font-size="10" font-weight="bold">91%</text>
        <!-- executive_call: 78% → 191px -->
        <rect x="141" y="66"  width="191" height="28" rx="4" fill="#C74634"/>
        <text x="10"  y="85"  fill="#94a3b8" font-size="9" text-anchor="start">executive_call</text>
        <text x="336" y="85"  fill="#fca5a5" font-size="10" font-weight="bold">78%</text>
        <!-- feature_demo: 34% → 83px -->
        <rect x="141" y="104" width="83"  height="28" rx="4" fill="#f97316"/>
        <text x="10"  y="123" fill="#94a3b8" font-size="9" text-anchor="start">feature_demo</text>
        <text x="228" y="123" fill="#fdba74" font-size="10" font-weight="bold">34%</text>
        <!-- training: 21% → 51px -->
        <rect x="141" y="142" width="51"  height="28" rx="4" fill="#eab308"/>
        <text x="10"  y="161" fill="#94a3b8" font-size="9" text-anchor="start">training</text>
        <text x="196" y="161" fill="#fde68a" font-size="10" font-weight="bold">21%</text>
        <!-- discount: 12% → 29px -->
        <rect x="141" y="180" width="29"  height="28" rx="4" fill="#64748b"/>
        <text x="10"  y="199" fill="#94a3b8" font-size="9" text-anchor="start">discount</text>
        <text x="174" y="199" fill="#cbd5e1" font-size="10" font-weight="bold">12%</text>
      </svg>
    </div>

    <!-- Card 3: Active Playbooks Heatmap -->
    <div class="card">
      <h2>Active Playbooks Heatmap (Partners x Playbook Types)</h2>
      <svg viewBox="0 0 420 240" xmlns="http://www.w3.org/2000/svg">
        <!-- Col headers: playbook types -->
        <text x="110" y="18" text-anchor="middle" fill="#94a3b8" font-size="8.5">churn</text>
        <text x="170" y="18" text-anchor="middle" fill="#94a3b8" font-size="8.5">onboard</text>
        <text x="230" y="18" text-anchor="middle" fill="#94a3b8" font-size="8.5">upsell</text>
        <text x="290" y="18" text-anchor="middle" fill="#94a3b8" font-size="8.5">renewal</text>
        <text x="350" y="18" text-anchor="middle" fill="#94a3b8" font-size="8.5">support</text>

        <!-- Row labels: partners -->
        <text x="70" y="50"  text-anchor="end" fill="#94a3b8" font-size="9">PI (ABB)</text>
        <text x="70" y="95"  text-anchor="end" fill="#94a3b8" font-size="9">Siemens</text>
        <text x="70" y="140" text-anchor="end" fill="#94a3b8" font-size="9">FANUC</text>
        <text x="70" y="185" text-anchor="end" fill="#94a3b8" font-size="9">Yaskawa</text>
        <text x="70" y="225" text-anchor="end" fill="#94a3b8" font-size="9">1X (NEO)</text>

        <!-- PI row: all green (active) -->
        <rect x="80"  y="28" width="58" height="32" rx="4" fill="#14532d" stroke="#22c55e" stroke-width="1.5"/>
        <text x="109" y="50" text-anchor="middle" fill="#86efac" font-size="10" font-weight="bold">✓</text>
        <rect x="140" y="28" width="58" height="32" rx="4" fill="#14532d" stroke="#22c55e" stroke-width="1.5"/>
        <text x="169" y="50" text-anchor="middle" fill="#86efac" font-size="10" font-weight="bold">✓</text>
        <rect x="200" y="28" width="58" height="32" rx="4" fill="#14532d" stroke="#22c55e" stroke-width="1.5"/>
        <text x="229" y="50" text-anchor="middle" fill="#86efac" font-size="10" font-weight="bold">✓</text>
        <rect x="260" y="28" width="58" height="32" rx="4" fill="#14532d" stroke="#22c55e" stroke-width="1.5"/>
        <text x="289" y="50" text-anchor="middle" fill="#86efac" font-size="10" font-weight="bold">✓</text>
        <rect x="320" y="28" width="58" height="32" rx="4" fill="#14532d" stroke="#22c55e" stroke-width="1.5"/>
        <text x="349" y="50" text-anchor="middle" fill="#86efac" font-size="10" font-weight="bold">✓</text>

        <!-- Siemens row: onboard + renewal active -->
        <rect x="80"  y="72" width="58" height="32" rx="4" fill="#1e293b" stroke="#334155"/>
        <text x="109" y="94" text-anchor="middle" fill="#475569" font-size="10">–</text>
        <rect x="140" y="72" width="58" height="32" rx="4" fill="#14532d" stroke="#22c55e" stroke-width="1.5"/>
        <text x="169" y="94" text-anchor="middle" fill="#86efac" font-size="10" font-weight="bold">✓</text>
        <rect x="200" y="72" width="58" height="32" rx="4" fill="#1e293b" stroke="#334155"/>
        <text x="229" y="94" text-anchor="middle" fill="#475569" font-size="10">–</text>
        <rect x="260" y="72" width="58" height="32" rx="4" fill="#14532d" stroke="#22c55e" stroke-width="1.5"/>
        <text x="289" y="94" text-anchor="middle" fill="#86efac" font-size="10" font-weight="bold">✓</text>
        <rect x="320" y="72" width="58" height="32" rx="4" fill="#1e293b" stroke="#334155"/>
        <text x="349" y="94" text-anchor="middle" fill="#475569" font-size="10">–</text>

        <!-- FANUC row: upsell + support active -->
        <rect x="80"  y="117" width="58" height="32" rx="4" fill="#1e293b" stroke="#334155"/>
        <text x="109" y="139" text-anchor="middle" fill="#475569" font-size="10">–</text>
        <rect x="140" y="117" width="58" height="32" rx="4" fill="#1e293b" stroke="#334155"/>
        <text x="169" y="139" text-anchor="middle" fill="#475569" font-size="10">–</text>
        <rect x="200" y="117" width="58" height="32" rx="4" fill="#14532d" stroke="#22c55e" stroke-width="1.5"/>
        <text x="229" y="139" text-anchor="middle" fill="#86efac" font-size="10" font-weight="bold">✓</text>
        <rect x="260" y="117" width="58" height="32" rx="4" fill="#1e293b" stroke="#334155"/>
        <text x="289" y="139" text-anchor="middle" fill="#475569" font-size="10">–</text>
        <rect x="320" y="117" width="58" height="32" rx="4" fill="#14532d" stroke="#22c55e" stroke-width="1.5"/>
        <text x="349" y="139" text-anchor="middle" fill="#86efac" font-size="10" font-weight="bold">✓</text>

        <!-- Yaskawa row: renewal active -->
        <rect x="80"  y="162" width="58" height="32" rx="4" fill="#1e293b" stroke="#334155"/>
        <text x="109" y="184" text-anchor="middle" fill="#475569" font-size="10">–</text>
        <rect x="140" y="162" width="58" height="32" rx="4" fill="#1e293b" stroke="#334155"/>
        <text x="169" y="184" text-anchor="middle" fill="#475569" font-size="10">–</text>
        <rect x="200" y="162" width="58" height="32" rx="4" fill="#1e293b" stroke="#334155"/>
        <text x="229" y="184" text-anchor="middle" fill="#475569" font-size="10">–</text>
        <rect x="260" y="162" width="58" height="32" rx="4" fill="#14532d" stroke="#22c55e" stroke-width="1.5"/>
        <text x="289" y="184" text-anchor="middle" fill="#86efac" font-size="10" font-weight="bold">✓</text>
        <rect x="320" y="162" width="58" height="32" rx="4" fill="#1e293b" stroke="#334155"/>
        <text x="349" y="184" text-anchor="middle" fill="#475569" font-size="10">–</text>

        <!-- 1X row: churn_risk RED (active critical) -->
        <rect x="80"  y="202" width="58" height="32" rx="4" fill="#7f1d1d" stroke="#ef4444" stroke-width="2"/>
        <text x="109" y="224" text-anchor="middle" fill="#fca5a5" font-size="10" font-weight="bold">RISK</text>
        <rect x="140" y="202" width="58" height="32" rx="4" fill="#1e293b" stroke="#334155"/>
        <text x="169" y="224" text-anchor="middle" fill="#475569" font-size="10">–</text>
        <rect x="200" y="202" width="58" height="32" rx="4" fill="#1e293b" stroke="#334155"/>
        <text x="229" y="224" text-anchor="middle" fill="#475569" font-size="10">–</text>
        <rect x="260" y="202" width="58" height="32" rx="4" fill="#1e293b" stroke="#334155"/>
        <text x="289" y="224" text-anchor="middle" fill="#475569" font-size="10">–</text>
        <rect x="320" y="202" width="58" height="32" rx="4" fill="#1e293b" stroke="#334155"/>
        <text x="349" y="224" text-anchor="middle" fill="#475569" font-size="10">–</text>
      </svg>
      <p style="color:#ef4444;font-size:0.72rem;margin-top:8px;">1X (NEO) churn_risk playbook ACTIVE — executive call triggered</p>
    </div>

  </div>

  <div class="metrics">
    <div class="metric"><div class="val">12</div><div class="lbl">Trigger types monitored</div></div>
    <div class="metric"><div class="val">91%</div><div class="lbl">Dedicated CSM retention rate</div></div>
    <div class="metric"><div class="val">78%</div><div class="lbl">Executive call retention rate</div></div>
    <div class="metric"><div class="val">+21%</div><div class="lbl">Training SR improvement</div></div>
    <div class="metric"><div class="val">12%</div><div class="lbl">Discount used (last resort)</div></div>
    <div class="metric"><div class="val">1X</div><div class="lbl">Active churn risk (NEO)</div></div>
  </div>
</body>
</html>
"""

if USE_FASTAPI:
    app = FastAPI(title="Customer Success Playbook", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def root():
        return HTML

    @app.get("/health")
    async def health():
        return JSONResponse({"status": "ok", "service": "customer_success_playbook", "port": 8675})

    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=8675)

else:
    from http.server import HTTPServer, BaseHTTPRequestHandler
    import json

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass
        def do_GET(self):
            if self.path == "/health":
                body = json.dumps({"status": "ok", "service": "customer_success_playbook", "port": 8675}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(HTML.encode())

    if __name__ == "__main__":
        server = HTTPServer(("0.0.0.0", 8675), Handler)
        print("Serving on port 8675")
        server.serve_forever()
