"""
Motion Planning Benchmarker — port 8666
OCI Robot Cloud | cycle-152A
"""

PLANNERS = ["RRT", "RRT*", "OMPL", "GR00T_learned", "hybrid"]
SUCCESS = [97, 98, 96, 94, 99.2]
PLAN_TIME_MS = [280, 340, 220, 8.3, 12]
PATH_LENGTH = [1.42, 1.38, 1.45, 1.51, 1.36]
SMOOTHNESS = [0.82, 0.79, 0.85, 0.88, 0.76]
CLEARANCE = [0.24, 0.26, 0.22, 0.19, 0.28]

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Motion Planning Benchmarker | OCI Robot Cloud</title>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',system-ui,sans-serif;min-height:100vh;padding:2rem}
  h1{color:#C74634;font-size:1.7rem;margin-bottom:.3rem}
  .sub{color:#38bdf8;font-size:.9rem;margin-bottom:2rem}
  .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(480px,1fr));gap:1.5rem}
  .card{background:#1e293b;border:1px solid #334155;border-radius:12px;padding:1.25rem}
  .card h2{color:#38bdf8;font-size:1rem;margin-bottom:1rem;text-transform:uppercase;letter-spacing:.05em}
  svg{width:100%;overflow:visible}
  .metric-row{display:flex;flex-wrap:wrap;gap:1rem;margin-top:1.5rem}
  .metric{background:#0f172a;border:1px solid #334155;border-radius:8px;padding:.75rem 1.25rem;flex:1;min-width:180px}
  .metric .val{color:#C74634;font-size:1.4rem;font-weight:700}
  .metric .lbl{color:#94a3b8;font-size:.78rem;margin-top:.2rem}
  .badge{display:inline-block;background:#C74634;color:#fff;border-radius:4px;padding:1px 7px;font-size:.72rem;margin-left:.4rem;vertical-align:middle}
</style>
</head>
<body>
<h1>Motion Planning Benchmarker</h1>
<p class="sub">OCI Robot Cloud &mdash; Port 8666 &mdash; 5 Planners Evaluated</p>
<div class="grid">

<!-- SVG 1: Success Rate + Planning Time dual-axis bar -->
<div class="card">
<h2>Planning Success Rate &amp; Time (Dual-Axis)</h2>
<svg viewBox="0 0 480 300" xmlns="http://www.w3.org/2000/svg">
  <!-- axes -->
  <line x1="60" y1="20" x2="60" y2="250" stroke="#475569" stroke-width="1.2"/>
  <line x1="60" y1="250" x2="460" y2="250" stroke="#475569" stroke-width="1.2"/>
  <line x1="460" y1="20" x2="460" y2="250" stroke="#38bdf8" stroke-width="1.2" stroke-dasharray="4,3"/>

  <!-- left y-axis labels (success %) -->
  <text x="54" y="25" fill="#94a3b8" font-size="9" text-anchor="end">100%</text>
  <text x="54" y="71" fill="#94a3b8" font-size="9" text-anchor="end">98%</text>
  <text x="54" y="117" fill="#94a3b8" font-size="9" text-anchor="end">96%</text>
  <text x="54" y="163" fill="#94a3b8" font-size="9" text-anchor="end">94%</text>
  <text x="54" y="209" fill="#94a3b8" font-size="9" text-anchor="end">92%</text>
  <text x="28" y="140" fill="#e2e8f0" font-size="9" transform="rotate(-90,28,140)" text-anchor="middle">Success Rate</text>

  <!-- right y-axis labels (time ms) -->
  <text x="466" y="25" fill="#38bdf8" font-size="9" text-anchor="start">350ms</text>
  <text x="466" y="90" fill="#38bdf8" font-size="9" text-anchor="start">262ms</text>
  <text x="466" y="155" fill="#38bdf8" font-size="9" text-anchor="start">175ms</text>
  <text x="466" y="220" fill="#38bdf8" font-size="9" text-anchor="start">87ms</text>
  <text x="466" y="250" fill="#38bdf8" font-size="9" text-anchor="start">0ms</text>
  <text x="480" y="140" fill="#38bdf8" font-size="9" transform="rotate(90,480,140)" text-anchor="middle">Plan Time (ms)</text>

  <!-- grid lines -->
  <line x1="60" y1="71" x2="460" y2="71" stroke="#1e293b" stroke-width="0.7"/>
  <line x1="60" y1="117" x2="460" y2="117" stroke="#1e293b" stroke-width="0.7"/>
  <line x1="60" y1="163" x2="460" y2="163" stroke="#1e293b" stroke-width="0.7"/>
  <line x1="60" y1="209" x2="460" y2="209" stroke="#1e293b" stroke-width="0.7"/>

  <!-- bars: success rate (left axis: 92-100% maps to y=209..25, range=8% -> 184px, 1%=23px) -->
  <!-- RRT 97% -> (97-92)*23=115px height, top = 250-115=135 -->
  <rect x="72" y="135" width="28" height="115" fill="#C74634" rx="2"/>
  <!-- RRT* 98% -> 138px, top=112 -->
  <rect x="148" y="112" width="28" height="138" fill="#C74634" rx="2"/>
  <!-- OMPL 96% -> 92px, top=158 -->
  <rect x="224" y="158" width="28" height="92" fill="#C74634" rx="2"/>
  <!-- GR00T 94% -> 46px, top=204 -->
  <rect x="300" y="204" width="28" height="46" fill="#C74634" rx="2"/>
  <!-- hybrid 99.2% -> ~165px, top=85; highlight -->
  <rect x="376" y="85" width="28" height="165" fill="#22c55e" rx="2"/>

  <!-- time dots (right axis: 0-350ms maps to y=250..25, 350->225px range, 1ms=0.643px) -->
  <!-- RRT 280ms -> 250 - 280*0.643 = 250-180=70 -->
  <circle cx="86" cy="70" r="5" fill="#38bdf8"/>
  <!-- RRT* 340ms -> 250-218.6=31 -->
  <circle cx="162" cy="31" r="5" fill="#38bdf8"/>
  <!-- OMPL 220ms -> 250-141.4=109 -->
  <circle cx="238" cy="109" r="5" fill="#38bdf8"/>
  <!-- GR00T 8.3ms -> 250-5.3=245 -->
  <circle cx="314" cy="245" r="5" fill="#fbbf24"/>
  <!-- hybrid 12ms -> 250-7.7=242 -->
  <circle cx="390" cy="242" r="5" fill="#fbbf24"/>

  <!-- connect time dots -->
  <polyline points="86,70 162,31 238,109 314,245 390,242" fill="none" stroke="#38bdf8" stroke-width="1.5" stroke-dasharray="5,3"/>

  <!-- x labels -->
  <text x="86" y="268" fill="#94a3b8" font-size="9" text-anchor="middle">RRT</text>
  <text x="162" y="268" fill="#94a3b8" font-size="9" text-anchor="middle">RRT*</text>
  <text x="238" y="268" fill="#94a3b8" font-size="9" text-anchor="middle">OMPL</text>
  <text x="314" y="268" fill="#94a3b8" font-size="9" text-anchor="middle">GR00T</text>
  <text x="390" y="268" fill="#22c55e" font-size="9" text-anchor="middle" font-weight="bold">hybrid&#9733;</text>

  <!-- legend -->
  <rect x="100" y="280" width="10" height="10" fill="#C74634" rx="1"/>
  <text x="115" y="289" fill="#94a3b8" font-size="8">Success Rate</text>
  <rect x="190" y="280" width="10" height="10" fill="#22c55e" rx="1"/>
  <text x="205" y="289" fill="#94a3b8" font-size="8">Hybrid (recommended)</text>
  <circle cx="305" cy="285" r="4" fill="#38bdf8"/>
  <text x="314" y="289" fill="#94a3b8" font-size="8">Plan Time</text>

  <!-- success % labels on bars -->
  <text x="86" y="130" fill="#e2e8f0" font-size="8" text-anchor="middle">97%</text>
  <text x="162" y="107" fill="#e2e8f0" font-size="8" text-anchor="middle">98%</text>
  <text x="238" y="153" fill="#e2e8f0" font-size="8" text-anchor="middle">96%</text>
  <text x="314" y="199" fill="#e2e8f0" font-size="8" text-anchor="middle">94%</text>
  <text x="390" y="80" fill="#e2e8f0" font-size="8" text-anchor="middle">99.2%</text>
</svg>
</div>

<!-- SVG 2: Path Quality Grouped Bars -->
<div class="card">
<h2>Path Quality Metrics (Lower = Better for Length)</h2>
<svg viewBox="0 0 480 300" xmlns="http://www.w3.org/2000/svg">
  <line x1="60" y1="20" x2="60" y2="250" stroke="#475569" stroke-width="1.2"/>
  <line x1="60" y1="250" x2="460" y2="250" stroke="#475569" stroke-width="1.2"/>

  <!-- y-axis labels 0..1.6 -> 230px, step 0.4 -> 57.5px -->
  <text x="54" y="254" fill="#94a3b8" font-size="9" text-anchor="end">0</text>
  <text x="54" y="197" fill="#94a3b8" font-size="9" text-anchor="end">0.4</text>
  <text x="54" y="139" fill="#94a3b8" font-size="9" text-anchor="end">0.8</text>
  <text x="54" y="82" fill="#94a3b8" font-size="9" text-anchor="end">1.2</text>
  <text x="54" y="24" fill="#94a3b8" font-size="9" text-anchor="end">1.6</text>
  <line x1="60" y1="197" x2="460" y2="197" stroke="#1e293b" stroke-width="0.7"/>
  <line x1="60" y1="139" x2="460" y2="139" stroke="#1e293b" stroke-width="0.7"/>
  <line x1="60" y1="82" x2="460" y2="82" stroke="#1e293b" stroke-width="0.7"/>

  <!-- scale: val * (230/1.6) = val * 143.75; bar top = 250 - height -->
  <!-- Group spacing: 5 planners, 3 bars each, group width ~78px, bar=18px, gap=3px -->
  <!-- planner x-starts: 65, 143, 221, 299, 377 -->

  <!-- RRT: path_length=1.42 h=204, smooth=0.82 h=118, clear=0.24 h=34 -->
  <rect x="65" y="46" width="16" height="204" fill="#C74634" rx="1"/>
  <rect x="84" y="132" width="16" height="118" fill="#38bdf8" rx="1"/>
  <rect x="103" y="216" width="16" height="34" fill="#a78bfa" rx="1"/>
  <text x="93" y="268" fill="#94a3b8" font-size="8" text-anchor="middle">RRT</text>

  <!-- RRT*: 1.38/0.79/0.26 -> 198/114/37 -->
  <rect x="143" y="52" width="16" height="198" fill="#C74634" rx="1"/>
  <rect x="162" y="136" width="16" height="114" fill="#38bdf8" rx="1"/>
  <rect x="181" y="213" width="16" height="37" fill="#a78bfa" rx="1"/>
  <text x="171" y="268" fill="#94a3b8" font-size="8" text-anchor="middle">RRT*</text>

  <!-- OMPL: 1.45/0.85/0.22 -> 209/122/32 -->
  <rect x="221" y="41" width="16" height="209" fill="#C74634" rx="1"/>
  <rect x="240" y="128" width="16" height="122" fill="#38bdf8" rx="1"/>
  <rect x="259" y="218" width="16" height="32" fill="#a78bfa" rx="1"/>
  <text x="249" y="268" fill="#94a3b8" font-size="8" text-anchor="middle">OMPL</text>

  <!-- GR00T: 1.51/0.88/0.19 -> 217/127/27 -->
  <rect x="299" y="33" width="16" height="217" fill="#C74634" rx="1"/>
  <rect x="318" y="123" width="16" height="127" fill="#38bdf8" rx="1"/>
  <rect x="337" y="223" width="16" height="27" fill="#a78bfa" rx="1"/>
  <text x="327" y="268" fill="#94a3b8" font-size="8" text-anchor="middle">GR00T</text>

  <!-- hybrid: 1.36/0.76/0.28 -> 195/109/40 -->
  <rect x="377" y="55" width="16" height="195" fill="#22c55e" rx="1"/>
  <rect x="396" y="141" width="16" height="109" fill="#38bdf8" rx="1"/>
  <rect x="415" y="210" width="16" height="40" fill="#a78bfa" rx="1"/>
  <text x="405" y="268" fill="#22c55e" font-size="8" text-anchor="middle" font-weight="bold">hybrid</text>

  <!-- legend -->
  <rect x="65" y="280" width="10" height="8" fill="#C74634" rx="1"/>
  <text x="80" y="288" fill="#94a3b8" font-size="8">Path Length</text>
  <rect x="155" y="280" width="10" height="8" fill="#38bdf8" rx="1"/>
  <text x="170" y="288" fill="#94a3b8" font-size="8">Smoothness</text>
  <rect x="250" y="280" width="10" height="8" fill="#a78bfa" rx="1"/>
  <text x="265" y="288" fill="#94a3b8" font-size="8">Clearance</text>
</svg>
</div>

<!-- SVG 3: Planning Time CDF -->
<div class="card" style="grid-column:1/-1">
<h2>Planning Time CDF — % Requests Below Latency Threshold</h2>
<svg viewBox="0 0 700 300" xmlns="http://www.w3.org/2000/svg">
  <line x1="70" y1="20" x2="70" y2="250" stroke="#475569" stroke-width="1.2"/>
  <line x1="70" y1="250" x2="660" y2="250" stroke="#475569" stroke-width="1.2"/>

  <!-- y-axis 0-100% -->
  <text x="64" y="254" fill="#94a3b8" font-size="9" text-anchor="end">0%</text>
  <text x="64" y="196" fill="#94a3b8" font-size="9" text-anchor="end">25%</text>
  <text x="64" y="138" fill="#94a3b8" font-size="9" text-anchor="end">50%</text>
  <text x="64" y="80" fill="#94a3b8" font-size="9" text-anchor="end">75%</text>
  <text x="64" y="24" fill="#94a3b8" font-size="9" text-anchor="end">100%</text>
  <line x1="70" y1="196" x2="660" y2="196" stroke="#1e293b" stroke-width="0.7"/>
  <line x1="70" y1="138" x2="660" y2="138" stroke="#1e293b" stroke-width="0.7"/>
  <line x1="70" y1="80" x2="660" y2="80" stroke="#1e293b" stroke-width="0.7"/>

  <!-- x-axis 0-500ms: 590px / 500 = 1.18px per ms -->
  <text x="70" y="268" fill="#94a3b8" font-size="9" text-anchor="middle">0</text>
  <text x="188" y="268" fill="#94a3b8" font-size="9" text-anchor="middle">100ms</text>
  <text x="306" y="268" fill="#94a3b8" font-size="9" text-anchor="middle">200ms</text>
  <text x="424" y="268" fill="#94a3b8" font-size="9" text-anchor="middle">300ms</text>
  <text x="542" y="268" fill="#94a3b8" font-size="9" text-anchor="middle">400ms</text>
  <text x="660" y="268" fill="#94a3b8" font-size="9" text-anchor="middle">500ms</text>
  <line x1="188" y1="245" x2="188" y2="255" stroke="#475569"/>
  <line x1="306" y1="245" x2="306" y2="255" stroke="#475569"/>
  <line x1="424" y1="245" x2="424" y2="255" stroke="#475569"/>
  <line x1="542" y1="245" x2="542" y2="255" stroke="#475569"/>

  <!-- y scale: 0%=250, 100%=20; 230px range. x scale: 0ms=70, 500ms=660; 590px. -->
  <!-- GR00T_learned: p50=8.3ms — very fast, almost all done by 30ms -->
  <!-- points (ms, %): (0,0)(5,30)(8.3,50)(15,80)(25,95)(50,99)(100,100) -->
  <polyline
    points="70,250 76,181 80,135 88,64 100,27 129,22 188,22"
    fill="none" stroke="#fbbf24" stroke-width="2.5"/>
  <text x="175" y="18" fill="#fbbf24" font-size="9">GR00T</text>

  <!-- hybrid: p50≈12ms, 99%<40ms -->
  <!-- (0,0)(8,30)(12,50)(20,80)(35,95)(60,99)(110,100) -->
  <polyline
    points="70,250 79,181 84,135 94,64 111,27 141,22 200,22"
    fill="none" stroke="#22c55e" stroke-width="2.5"/>
  <text x="195" y="30" fill="#22c55e" font-size="9">hybrid</text>

  <!-- OMPL: mean≈220ms, p50≈200ms -->
  <!-- (0,0)(100,20)(150,40)(200,55)(250,70)(300,85)(350,95)(400,99)(500,100) -->
  <polyline
    points="70,250 188,204 247,196 306,186 365,174 424,157 483,138 542,127 660,22"
    fill="none" stroke="#a78bfa" stroke-width="2"/>
  <text x="490" y="130" fill="#a78bfa" font-size="9">OMPL</text>

  <!-- RRT: mean≈280ms -->
  <!-- (0,0)(80,10)(150,25)(220,45)(280,60)(350,78)(420,90)(480,98)(500,100) -->
  <polyline
    points="70,250 164,227 247,212 329,197 400,185 483,170 565,157 636,148 660,22"
    fill="none" stroke="#C74634" stroke-width="2"/>
  <text x="545" y="148" fill="#C74634" font-size="9">RRT</text>

  <!-- RRT*: mean≈340ms, rightmost -->
  <!-- (0,0)(100,8)(200,20)(280,35)(340,55)(400,72)(450,85)(490,96)(500,100) -->
  <polyline
    points="70,250 188,231 306,227 400,220 471,214 542,207 600,200 648,195 660,22"
    fill="none" stroke="#38bdf8" stroke-width="2"/>
  <text x="630" y="202" fill="#38bdf8" font-size="9">RRT*</text>

  <!-- 50% horizontal reference -->
  <line x1="70" y1="138" x2="660" y2="138" stroke="#475569" stroke-width="0.8" stroke-dasharray="6,4"/>
  <text x="665" y="141" fill="#475569" font-size="8">p50</text>

  <text x="365" y="290" fill="#94a3b8" font-size="9" text-anchor="middle">Latency (ms)</text>
  <text x="20" y="135" fill="#94a3b8" font-size="9" transform="rotate(-90,20,135)" text-anchor="middle">CDF (%)</text>
</svg>
</div>

</div>

<!-- Key Metrics -->
<div class="metric-row">
  <div class="metric">
    <div class="val">8.3ms</div>
    <div class="lbl">GR00T p50 latency</div>
  </div>
  <div class="metric">
    <div class="val">99.2%</div>
    <div class="lbl">Hybrid success rate</div>
  </div>
  <div class="metric">
    <div class="val">12ms</div>
    <div class="lbl">Hybrid plan time</div>
  </div>
  <div class="metric">
    <div class="val">340ms</div>
    <div class="lbl">RRT* plan time (slowest)</div>
  </div>
  <div class="metric">
    <div class="val">hybrid<span class="badge">PROD</span></div>
    <div class="lbl">Recommended planner</div>
  </div>
</div>
</body>
</html>"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn

    app = FastAPI(title="Motion Planning Benchmarker", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return HTML

    @app.get("/health")
    async def health():
        return JSONResponse({"status": "ok", "service": "motion_planning_benchmarker", "port": 8666})

    @app.get("/metrics")
    async def metrics():
        return JSONResponse({
            "planners": PLANNERS,
            "success_rate_pct": SUCCESS,
            "plan_time_ms": PLAN_TIME_MS,
            "path_length": PATH_LENGTH,
            "smoothness": SMOOTHNESS,
            "clearance": CLEARANCE,
            "recommended": "hybrid",
            "groot_p50_ms": 8.3,
            "hybrid_success_pct": 99.2,
            "hybrid_plan_time_ms": 12,
        })

    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=8666)

except ImportError:
    from http.server import HTTPServer, BaseHTTPRequestHandler
    import json

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass
        def do_GET(self):
            if self.path == "/health":
                body = json.dumps({"status": "ok", "service": "motion_planning_benchmarker", "port": 8666}).encode()
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
        server = HTTPServer(("0.0.0.0", 8666), Handler)
        print("Motion Planning Benchmarker running on port 8666")
        server.serve_forever()
