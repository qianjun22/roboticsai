"""
Revenue Cohort Analyzer — port 8667
OCI Robot Cloud | cycle-152A
"""

COHORT_LABELS = ["Cohort-1 (Q1 2025)", "Cohort-2 (Q3 2025)"]
COHORT1_RETENTION = [100, 100, 100, 97, 97, 97]
COHORT1_ARPU = [840, 960, 1080, 1180, 1310, 1420]
COHORT2_ARPU_PROJ = [600, 780, 980, 1170, 1420, 1680]
PAYBACK_MO = [4, 3]

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Revenue Cohort Analyzer | OCI Robot Cloud</title>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',system-ui,sans-serif;min-height:100vh;padding:2rem}
  h1{color:#C74634;font-size:1.7rem;margin-bottom:.3rem}
  .sub{color:#38bdf8;font-size:.9rem;margin-bottom:2rem}
  .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(460px,1fr));gap:1.5rem}
  .card{background:#1e293b;border:1px solid #334155;border-radius:12px;padding:1.25rem}
  .card h2{color:#38bdf8;font-size:1rem;margin-bottom:1rem;text-transform:uppercase;letter-spacing:.05em}
  svg{width:100%;overflow:visible}
  .metric-row{display:flex;flex-wrap:wrap;gap:1rem;margin-top:1.5rem}
  .metric{background:#0f172a;border:1px solid #334155;border-radius:8px;padding:.75rem 1.25rem;flex:1;min-width:180px}
  .metric .val{color:#C74634;font-size:1.4rem;font-weight:700}
  .metric .lbl{color:#94a3b8;font-size:.78rem;margin-top:.2rem}
  .badge{display:inline-block;background:#22c55e;color:#fff;border-radius:4px;padding:1px 7px;font-size:.72rem;margin-left:.4rem;vertical-align:middle}
</style>
</head>
<body>
<h1>Revenue Cohort Analyzer</h1>
<p class="sub">OCI Robot Cloud &mdash; Port 8667 &mdash; Cohort Retention &amp; ARPU Analysis</p>
<div class="grid">

<!-- SVG 1: Cohort Retention Heatmap -->
<div class="card">
<h2>Cohort Retention Heatmap (% ARR Retained)</h2>
<svg viewBox="0 0 480 220" xmlns="http://www.w3.org/2000/svg">
  <!-- Column headers: Month 1-6 -->
  <text x="110" y="16" fill="#94a3b8" font-size="9" text-anchor="middle">Mo 1</text>
  <text x="170" y="16" fill="#94a3b8" font-size="9" text-anchor="middle">Mo 2</text>
  <text x="230" y="16" fill="#94a3b8" font-size="9" text-anchor="middle">Mo 3</text>
  <text x="290" y="16" fill="#94a3b8" font-size="9" text-anchor="middle">Mo 4</text>
  <text x="350" y="16" fill="#94a3b8" font-size="9" text-anchor="middle">Mo 5</text>
  <text x="410" y="16" fill="#94a3b8" font-size="9" text-anchor="middle">Mo 6</text>

  <!-- Row: Cohort-1 -->
  <text x="95" y="57" fill="#e2e8f0" font-size="8.5" text-anchor="end">Cohort-1</text>
  <!-- 100% cells — deep green -->
  <rect x="80" y="26" width="55" height="42" rx="3" fill="#16a34a"/>
  <rect x="140" y="26" width="55" height="42" rx="3" fill="#16a34a"/>
  <rect x="200" y="26" width="55" height="42" rx="3" fill="#16a34a"/>
  <!-- 97% cells — slightly lighter green -->
  <rect x="260" y="26" width="55" height="42" rx="3" fill="#22c55e"/>
  <rect x="320" y="26" width="55" height="42" rx="3" fill="#22c55e"/>
  <rect x="380" y="26" width="55" height="42" rx="3" fill="#22c55e"/>
  <!-- cell labels -->
  <text x="107" y="51" fill="#fff" font-size="10" text-anchor="middle" font-weight="bold">100%</text>
  <text x="167" y="51" fill="#fff" font-size="10" text-anchor="middle" font-weight="bold">100%</text>
  <text x="227" y="51" fill="#fff" font-size="10" text-anchor="middle" font-weight="bold">100%</text>
  <text x="287" y="51" fill="#fff" font-size="10" text-anchor="middle" font-weight="bold">97%</text>
  <text x="347" y="51" fill="#fff" font-size="10" text-anchor="middle" font-weight="bold">97%</text>
  <text x="407" y="51" fill="#fff" font-size="10" text-anchor="middle" font-weight="bold">97%</text>

  <!-- Row: Cohort-2 (projected, lighter tones) -->
  <text x="95" y="122" fill="#e2e8f0" font-size="8.5" text-anchor="end">Cohort-2</text>
  <!-- projected 100/100/100/98/98/96 -->
  <rect x="80" y="91" width="55" height="42" rx="3" fill="#15803d" opacity="0.75"/>
  <rect x="140" y="91" width="55" height="42" rx="3" fill="#15803d" opacity="0.75"/>
  <rect x="200" y="91" width="55" height="42" rx="3" fill="#15803d" opacity="0.75"/>
  <rect x="260" y="91" width="55" height="42" rx="3" fill="#16a34a" opacity="0.75"/>
  <rect x="320" y="91" width="55" height="42" rx="3" fill="#16a34a" opacity="0.75"/>
  <rect x="380" y="91" width="55" height="42" rx="3" fill="#22c55e" opacity="0.75"/>
  <text x="107" y="116" fill="#fff" font-size="10" text-anchor="middle" font-weight="bold">100%</text>
  <text x="167" y="116" fill="#fff" font-size="10" text-anchor="middle" font-weight="bold">100%</text>
  <text x="227" y="116" fill="#fff" font-size="10" text-anchor="middle" font-weight="bold">100%</text>
  <text x="287" y="116" fill="#fff" font-size="10" text-anchor="middle" font-weight="bold">98%</text>
  <text x="347" y="116" fill="#fff" font-size="10" text-anchor="middle" font-weight="bold">98%</text>
  <text x="407" y="116" fill="#fff" font-size="10" text-anchor="middle" font-weight="bold">96%</text>

  <!-- color scale legend -->
  <text x="80" y="158" fill="#94a3b8" font-size="8">Color scale:</text>
  <rect x="145" y="148" width="22" height="12" rx="2" fill="#15803d"/>
  <text x="170" y="158" fill="#94a3b8" font-size="8">95-99%</text>
  <rect x="225" y="148" width="22" height="12" rx="2" fill="#16a34a"/>
  <text x="250" y="158" fill="#94a3b8" font-size="8">99-100%</text>
  <rect x="315" y="148" width="22" height="12" rx="2" fill="#22c55e"/>
  <text x="340" y="158" fill="#94a3b8" font-size="8">100% (3m)</text>

  <text x="80" y="180" fill="#64748b" font-size="8">* Cohort-2 values are projected</text>
  <text x="80" y="193" fill="#64748b" font-size="8">Cohort-1: confirmed data &bull; Perfect retention first 3 months</text>
</svg>
</div>

<!-- SVG 2: ARPU Growth Curves -->
<div class="card">
<h2>ARPU Growth Curves (0–18 Months)</h2>
<svg viewBox="0 0 480 280" xmlns="http://www.w3.org/2000/svg">
  <line x1="60" y1="20" x2="60" y2="240" stroke="#475569" stroke-width="1.2"/>
  <line x1="60" y1="240" x2="460" y2="240" stroke="#475569" stroke-width="1.2"/>

  <!-- y-axis $0-$1800: 220px, 1px=$0.1222 -->
  <text x="54" y="244" fill="#94a3b8" font-size="9" text-anchor="end">$0</text>
  <text x="54" y="189" fill="#94a3b8" font-size="9" text-anchor="end">$500</text>
  <text x="54" y="134" fill="#94a3b8" font-size="9" text-anchor="end">$1,000</text>
  <text x="54" y="79" fill="#94a3b8" font-size="9" text-anchor="end">$1,500</text>
  <text x="54" y="24" fill="#94a3b8" font-size="9" text-anchor="end">$1,800</text>
  <line x1="60" y1="189" x2="460" y2="189" stroke="#1e293b" stroke-width="0.7"/>
  <line x1="60" y1="134" x2="460" y2="134" stroke="#1e293b" stroke-width="0.7"/>
  <line x1="60" y1="79" x2="460" y2="79" stroke="#1e293b" stroke-width="0.7"/>

  <!-- x-axis months 0-18: 400px / 18 = 22.2px per month -->
  <text x="60" y="258" fill="#94a3b8" font-size="9" text-anchor="middle">0</text>
  <text x="171" y="258" fill="#94a3b8" font-size="9" text-anchor="middle">5mo</text>
  <text x="282" y="258" fill="#94a3b8" font-size="9" text-anchor="middle">10mo</text>
  <text x="393" y="258" fill="#94a3b8" font-size="9" text-anchor="middle">15mo</text>
  <text x="460" y="258" fill="#94a3b8" font-size="9" text-anchor="middle">18mo</text>

  <!-- scale helper: y = 240 - (val/1800)*220 -->
  <!-- Cohort-1: mo 0..5 = 840/960/1080/1180/1310/1420 mapped to x=0..5*22.2=111 pts -->
  <!-- mo6-18: extrapolate gently to ~1600 at mo18 -->
  <!-- x = 60 + mo*22.2 -->
  <!-- Cohort-1 actuals + gentle projection -->
  <polyline
    points="60,137 82,122 104,108 127,96 149,80 171,67 193,59 215,52 237,46 260,41 282,37 304,34 326,31 349,29 371,27 393,25 415,24 438,23 460,22"
    fill="none" stroke="#C74634" stroke-width="2.5"/>
  <!-- dots at actual data points (mo 0-5 actuals) -->
  <circle cx="60" cy="137" r="4" fill="#C74634"/>
  <circle cx="82" cy="122" r="4" fill="#C74634"/>
  <circle cx="104" cy="108" r="4" fill="#C74634"/>
  <circle cx="127" cy="96" r="4" fill="#C74634"/>
  <circle cx="149" cy="80" r="4" fill="#C74634"/>
  <circle cx="171" cy="67" r="4" fill="#C74634"/>
  <text x="175" y="62" fill="#C74634" font-size="9">$1,420</text>
  <!-- projected dashes -->
  <line x1="171" y1="67" x2="460" y2="22" stroke="#C74634" stroke-width="1.5" stroke-dasharray="6,4" opacity="0.6"/>

  <!-- Cohort-2 (steeper ramp, projected) mo 0-5 = 600/780/980/1170/1420/1680 -->
  <!-- y vals: 240-(600/1800)*220=167; 240-(780/1800)*220=145; 240-(980/1800)*220=120; -->
  <!-- 240-(1170/1800)*220=97; 240-(1420/1800)*220=67; 240-(1680/1800)*220=35 -->
  <polyline
    points="60,167 82,145 104,120 127,97 149,67 171,35"
    fill="none" stroke="#38bdf8" stroke-width="2.5" stroke-dasharray="7,3"/>
  <circle cx="60" cy="167" r="4" fill="#38bdf8"/>
  <circle cx="82" cy="145" r="4" fill="#38bdf8"/>
  <circle cx="104" cy="120" r="4" fill="#38bdf8"/>
  <circle cx="127" cy="97" r="4" fill="#38bdf8"/>
  <circle cx="149" cy="67" r="4" fill="#38bdf8"/>
  <circle cx="171" cy="35" r="4" fill="#38bdf8"/>
  <text x="175" y="34" fill="#38bdf8" font-size="9">$1,680 (proj.)</text>
  <!-- project cohort-2 forward steeply -->
  <line x1="171" y1="35" x2="460" y2="15" stroke="#38bdf8" stroke-width="1.5" stroke-dasharray="5,4" opacity="0.5"/>

  <!-- legend -->
  <line x1="65" y1="272" x2="95" y2="272" stroke="#C74634" stroke-width="2.5"/>
  <circle cx="80" cy="272" r="3" fill="#C74634"/>
  <text x="100" y="276" fill="#94a3b8" font-size="8">Cohort-1 (actual + proj.)</text>
  <line x1="235" y1="272" x2="265" y2="272" stroke="#38bdf8" stroke-width="2.5" stroke-dasharray="5,3"/>
  <circle cx="250" cy="272" r="3" fill="#38bdf8"/>
  <text x="270" y="276" fill="#94a3b8" font-size="8">Cohort-2 (projected)</text>

  <text x="260" y="290" fill="#94a3b8" font-size="8" text-anchor="middle">Month</text>
  <text x="18" y="135" fill="#94a3b8" font-size="8" transform="rotate(-90,18,135)" text-anchor="middle">ARPU (USD/mo)</text>
</svg>
</div>

<!-- SVG 3: Cohort Payback Period Bar -->
<div class="card" style="grid-column:1/-1">
<h2>Cohort Payback Period (Target: &lt;6 Months)</h2>
<svg viewBox="0 0 600 200" xmlns="http://www.w3.org/2000/svg">
  <line x1="80" y1="20" x2="80" y2="150" stroke="#475569" stroke-width="1.2"/>
  <line x1="80" y1="150" x2="560" y2="150" stroke="#475569" stroke-width="1.2"/>

  <!-- y-axis 0-8 months: 130px range, 1mo=16.25px -->
  <text x="74" y="154" fill="#94a3b8" font-size="9" text-anchor="end">0</text>
  <text x="74" y="106" fill="#94a3b8" font-size="9" text-anchor="end">3mo</text>
  <text x="74" y="57" fill="#94a3b8" font-size="9" text-anchor="end">6mo</text>
  <text x="74" y="24" fill="#94a3b8" font-size="9" text-anchor="end">8mo</text>
  <line x1="80" y1="106" x2="560" y2="106" stroke="#1e293b" stroke-width="0.7"/>
  <line x1="80" y1="57" x2="560" y2="57" stroke="#1e293b" stroke-width="0.7"/>

  <!-- Target <6mo line (at y=57) -->
  <line x1="80" y1="57" x2="560" y2="57" stroke="#fbbf24" stroke-width="1.5" stroke-dasharray="8,4"/>
  <text x="565" y="60" fill="#fbbf24" font-size="9">Target &lt;6mo</text>

  <!-- Cohort-1: 4 months -> h = 4*16.25=65, top=150-65=85 -->
  <rect x="160" y="85" width="100" height="65" fill="#C74634" rx="3"/>
  <text x="210" y="80" fill="#e2e8f0" font-size="11" text-anchor="middle" font-weight="bold">4 months</text>
  <text x="210" y="170" fill="#94a3b8" font-size="9" text-anchor="middle">Cohort-1</text>
  <text x="210" y="181" fill="#64748b" font-size="8" text-anchor="middle">(confirmed)</text>

  <!-- Cohort-2: 3 months projected -> h=48.75, top=101 -->
  <rect x="340" y="101" width="100" height="49" fill="#22c55e" rx="3"/>
  <text x="390" y="96" fill="#e2e8f0" font-size="11" text-anchor="middle" font-weight="bold">3 months</text>
  <text x="390" y="170" fill="#94a3b8" font-size="9" text-anchor="middle">Cohort-2</text>
  <text x="390" y="181" fill="#64748b" font-size="8" text-anchor="middle">(projected)</text>

  <!-- improvement arrow -->
  <line x1="262" y1="110" x2="338" y2="110" stroke="#38bdf8" stroke-width="1.5" marker-end="url(#arr)"/>
  <defs>
    <marker id="arr" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto">
      <path d="M0,0 L6,3 L0,6 Z" fill="#38bdf8"/>
    </marker>
  </defs>
  <text x="300" y="106" fill="#38bdf8" font-size="8" text-anchor="middle">&#8722;25%</text>

  <text x="320" y="195" fill="#94a3b8" font-size="8" text-anchor="middle">Both cohorts beat the &lt;6 month target</text>
</svg>
</div>

</div>

<!-- Key Metrics -->
<div class="metric-row">
  <div class="metric">
    <div class="val">100%</div>
    <div class="lbl">Cohort-1 retention (first 3mo)</div>
  </div>
  <div class="metric">
    <div class="val">$1,420</div>
    <div class="lbl">Cohort-1 ARPU at 6mo</div>
  </div>
  <div class="metric">
    <div class="val">$1,680</div>
    <div class="lbl">Cohort-2 ARPU at 6mo (proj.)</div>
  </div>
  <div class="metric">
    <div class="val">$28k</div>
    <div class="lbl">Cohort-2 projected CLV<span class="badge">+17%</span></div>
  </div>
  <div class="metric">
    <div class="val">3mo</div>
    <div class="lbl">Cohort-2 payback period (proj.)</div>
  </div>
</div>
</body>
</html>"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn

    app = FastAPI(title="Revenue Cohort Analyzer", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return HTML

    @app.get("/health")
    async def health():
        return JSONResponse({"status": "ok", "service": "revenue_cohort_analyzer", "port": 8667})

    @app.get("/metrics")
    async def metrics():
        return JSONResponse({
            "cohorts": COHORT_LABELS,
            "cohort1_retention_pct": COHORT1_RETENTION,
            "cohort1_arpu_usd": COHORT1_ARPU,
            "cohort2_arpu_projected_usd": COHORT2_ARPU_PROJ,
            "payback_months": PAYBACK_MO,
            "cohort1_clv_usd": 24000,
            "cohort2_clv_projected_usd": 28000,
            "cohort1_3mo_retention_pct": 100,
            "target_payback_months": 6,
        })

    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=8667)

except ImportError:
    from http.server import HTTPServer, BaseHTTPRequestHandler
    import json

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass
        def do_GET(self):
            if self.path == "/health":
                body = json.dumps({"status": "ok", "service": "revenue_cohort_analyzer", "port": 8667}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
            else:
                body = HTML.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    if __name__ == "__main__":
        server = HTTPServer(("0.0.0.0", 8667), Handler)
        print("Revenue Cohort Analyzer running on port 8667")
        server.serve_forever()
