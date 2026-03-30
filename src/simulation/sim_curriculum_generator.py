"""
sim_curriculum_generator.py — port 8628
Curriculum learning generator for robot simulation tasks.
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>Sim Curriculum Generator — OCI Robot Cloud</title>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',system-ui,sans-serif;min-height:100vh;padding:32px}
  h1{color:#C74634;font-size:2rem;font-weight:700;margin-bottom:6px;letter-spacing:-0.5px}
  h2{color:#C74634;font-size:1.15rem;font-weight:600;margin:28px 0 12px}
  .subtitle{color:#94a3b8;font-size:0.95rem;margin-bottom:32px}
  .grid{display:grid;grid-template-columns:1fr 1fr;gap:24px;margin-bottom:24px}
  .card{background:#1e293b;border:1px solid #334155;border-radius:12px;padding:24px}
  .card-full{background:#1e293b;border:1px solid #334155;border-radius:12px;padding:24px;margin-bottom:24px}
  .metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:24px}
  .metric{background:#1e293b;border:1px solid #334155;border-radius:10px;padding:18px;text-align:center}
  .metric-val{color:#38bdf8;font-size:1.8rem;font-weight:700;line-height:1}
  .metric-lbl{color:#64748b;font-size:0.78rem;margin-top:6px;text-transform:uppercase;letter-spacing:.05em}
  svg text{font-family:'Segoe UI',system-ui,sans-serif}
  .tag{display:inline-block;background:#0f3460;color:#38bdf8;border-radius:4px;padding:2px 8px;font-size:0.75rem;margin-right:6px}
</style>
</head>
<body>
<h1>Sim Curriculum Generator</h1>
<p class="subtitle">Port 8628 &nbsp;|&nbsp; Adaptive difficulty progression for robot manipulation training</p>

<div class="metrics">
  <div class="metric"><div class="metric-val">40%</div><div class="metric-lbl">Fewer Steps (vs Random)</div></div>
  <div class="metric"><div class="metric-val">12</div><div class="metric-lbl">Curriculum Stages</div></div>
  <div class="metric"><div class="metric-val">200</div><div class="metric-lbl">Episodes per Stage</div></div>
  <div class="metric"><div class="metric-val">1840</div><div class="metric-lbl">Steps to SR=0.70 (CB)</div></div>
</div>

<!-- Chart 1: Task Difficulty Progression -->
<div class="card-full">
  <h2>Task Difficulty Progression — Steps to SR = 0.70</h2>
  <svg viewBox="0 0 860 300" width="100%" xmlns="http://www.w3.org/2000/svg">
    <!-- axes -->
    <line x1="70" y1="260" x2="820" y2="260" stroke="#334155" stroke-width="1.5"/>
    <line x1="70" y1="20"  x2="70"  y2="260" stroke="#334155" stroke-width="1.5"/>
    <!-- y-axis labels -->
    <text x="60" y="264" fill="#64748b" font-size="11" text-anchor="end">0</text>
    <text x="60" y="214" fill="#64748b" font-size="11" text-anchor="end">500</text>
    <text x="60" y="164" fill="#64748b" font-size="11" text-anchor="end">1000</text>
    <text x="60" y="114" fill="#64748b" font-size="11" text-anchor="end">1500</text>
    <text x="60" y="64"  fill="#64748b" font-size="11" text-anchor="end">2000</text>
    <!-- gridlines -->
    <line x1="70" y1="214" x2="820" y2="214" stroke="#1e293b" stroke-width="1" stroke-dasharray="4 4"/>
    <line x1="70" y1="164" x2="820" y2="164" stroke="#1e293b" stroke-width="1" stroke-dasharray="4 4"/>
    <line x1="70" y1="114" x2="820" y2="114" stroke="#1e293b" stroke-width="1" stroke-dasharray="4 4"/>
    <line x1="70" y1="64"  x2="820" y2="64"  stroke="#1e293b" stroke-width="1" stroke-dasharray="4 4"/>
    <!-- bars: tasks=[reach,pick,place,stack,pour,insert,assemble,bimanual], steps=[180,320,460,680,820,1050,1380,1900] -->
    <!-- bar width=68, gap=24, start x=95 -->
    <!-- reach: 180 steps -> height=18 -> y=242 -->
    <rect x="95"  y="242" width="68" height="18"  fill="#38bdf8" rx="3"/>
    <text x="129" y="258" fill="#0f172a" font-size="9" text-anchor="middle" font-weight="600">180</text>
    <text x="129" y="278" fill="#94a3b8" font-size="10" text-anchor="middle">Reach</text>
    <!-- pick: 320 -> height=32 -> y=228 -->
    <rect x="187" y="228" width="68" height="32"  fill="#38bdf8" rx="3"/>
    <text x="221" y="246" fill="#0f172a" font-size="9" text-anchor="middle" font-weight="600">320</text>
    <text x="221" y="278" fill="#94a3b8" font-size="10" text-anchor="middle">Pick</text>
    <!-- place: 460 -> height=46 -> y=214 -->
    <rect x="279" y="214" width="68" height="46"  fill="#38bdf8" rx="3"/>
    <text x="313" y="241" fill="#0f172a" font-size="9" text-anchor="middle" font-weight="600">460</text>
    <text x="313" y="278" fill="#94a3b8" font-size="10" text-anchor="middle">Place</text>
    <!-- stack: 680 -> height=68 -> y=192 -->
    <rect x="371" y="192" width="68" height="68"  fill="#C74634" rx="3"/>
    <text x="405" y="230" fill="#fff" font-size="9" text-anchor="middle" font-weight="600">680</text>
    <text x="405" y="278" fill="#94a3b8" font-size="10" text-anchor="middle">Stack</text>
    <!-- pour: 820 -> height=82 -> y=178 -->
    <rect x="463" y="178" width="68" height="82"  fill="#C74634" rx="3"/>
    <text x="497" y="223" fill="#fff" font-size="9" text-anchor="middle" font-weight="600">820</text>
    <text x="497" y="278" fill="#94a3b8" font-size="10" text-anchor="middle">Pour</text>
    <!-- insert: 1050 -> height=105 -> y=155 -->
    <rect x="555" y="155" width="68" height="105" fill="#C74634" rx="3"/>
    <text x="589" y="212" fill="#fff" font-size="9" text-anchor="middle" font-weight="600">1050</text>
    <text x="589" y="278" fill="#94a3b8" font-size="10" text-anchor="middle">Insert</text>
    <!-- assemble: 1380 -> height=138 -> y=122 -->
    <rect x="647" y="122" width="68" height="138" fill="#ef4444" rx="3"/>
    <text x="681" y="195" fill="#fff" font-size="9" text-anchor="middle" font-weight="600">1380</text>
    <text x="681" y="278" fill="#94a3b8" font-size="10" text-anchor="middle">Assemble</text>
    <!-- bimanual: 1900 -> height=190 -> y=70 -->
    <rect x="739" y="70"  width="68" height="190" fill="#ef4444" rx="3"/>
    <text x="773" y="170" fill="#fff" font-size="9" text-anchor="middle" font-weight="600">1900</text>
    <text x="773" y="278" fill="#94a3b8" font-size="10" text-anchor="middle">Bimanual</text>
    <!-- y-axis title -->
    <text x="18" y="150" fill="#64748b" font-size="11" text-anchor="middle" transform="rotate(-90,18,150)">Steps to SR = 0.70</text>
  </svg>
</div>

<div class="grid">
<!-- Chart 2: Scene Complexity Ramping -->
<div class="card">
  <h2>Scene Complexity Ramping (12 Stages)</h2>
  <svg viewBox="0 0 400 260" width="100%" xmlns="http://www.w3.org/2000/svg">
    <line x1="50" y1="220" x2="380" y2="220" stroke="#334155" stroke-width="1.5"/>
    <line x1="50" y1="20"  x2="50"  y2="220" stroke="#334155" stroke-width="1.5"/>
    <!-- y labels -->
    <text x="42" y="224" fill="#64748b" font-size="10" text-anchor="end">0.0</text>
    <text x="42" y="174" fill="#64748b" font-size="10" text-anchor="end">0.25</text>
    <text x="42" y="124" fill="#64748b" font-size="10" text-anchor="end">0.50</text>
    <text x="42" y="74"  fill="#64748b" font-size="10" text-anchor="end">0.75</text>
    <text x="42" y="28"  fill="#64748b" font-size="10" text-anchor="end">1.00</text>
    <!-- gridlines -->
    <line x1="50" y1="174" x2="380" y2="174" stroke="#334155" stroke-width="0.5" stroke-dasharray="3 3"/>
    <line x1="50" y1="124" x2="380" y2="124" stroke="#334155" stroke-width="0.5" stroke-dasharray="3 3"/>
    <line x1="50" y1="74"  x2="380" y2="74"  stroke="#334155" stroke-width="0.5" stroke-dasharray="3 3"/>
    <line x1="50" y1="28"  x2="380" y2="28"  stroke="#334155" stroke-width="0.5" stroke-dasharray="3 3"/>
    <!-- 12 x-ticks: spacing = 330/11 = 30px each, starting x=50 -->
    <!-- stages 1-12: x = 50 + (i)*30 -->
    <text x="50"  y="234" fill="#64748b" font-size="8" text-anchor="middle">1</text>
    <text x="80"  y="234" fill="#64748b" font-size="8" text-anchor="middle">2</text>
    <text x="110" y="234" fill="#64748b" font-size="8" text-anchor="middle">3</text>
    <text x="140" y="234" fill="#64748b" font-size="8" text-anchor="middle">4</text>
    <text x="170" y="234" fill="#64748b" font-size="8" text-anchor="middle">5</text>
    <text x="200" y="234" fill="#64748b" font-size="8" text-anchor="middle">6</text>
    <text x="230" y="234" fill="#64748b" font-size="8" text-anchor="middle">7</text>
    <text x="260" y="234" fill="#64748b" font-size="8" text-anchor="middle">8</text>
    <text x="290" y="234" fill="#64748b" font-size="8" text-anchor="middle">9</text>
    <text x="320" y="234" fill="#64748b" font-size="8" text-anchor="middle">10</text>
    <text x="350" y="234" fill="#64748b" font-size="8" text-anchor="middle">11</text>
    <text x="380" y="234" fill="#64748b" font-size="8" text-anchor="middle">12</text>
    <!-- object_count line (blue #38bdf8): normalized ramp -->
    <!-- values: 0.05,0.12,0.20,0.28,0.36,0.45,0.55,0.62,0.70,0.79,0.88,1.00 -->
    <!-- y = 220 - val*192 -->
    <polyline points="50,211 80,197 110,182 140,166 170,151 200,134 230,114 260,101 290,86 320,69 350,51 380,28"
      fill="none" stroke="#38bdf8" stroke-width="2" stroke-linejoin="round"/>
    <!-- clutter line (orange): 0.02,0.05,0.09,0.14,0.20,0.28,0.37,0.46,0.56,0.67,0.80,1.00 -->
    <polyline points="50,216 80,210 110,203 140,193 170,182 200,166 230,149 260,132 290,112 320,91 350,67 380,28"
      fill="none" stroke="#f59e0b" stroke-width="2" stroke-linejoin="round"/>
    <!-- lighting_range line (green): 0.10,0.18,0.27,0.35,0.43,0.51,0.59,0.67,0.75,0.83,0.91,1.00 -->
    <polyline points="50,201 80,185 110,168 140,153 170,137 200,122 230,107 260,91 290,76 320,60 350,44 380,28"
      fill="none" stroke="#4ade80" stroke-width="2" stroke-linejoin="round"/>
    <!-- legend -->
    <rect x="55" y="30" width="10" height="3" fill="#38bdf8" rx="1"/>
    <text x="70" y="34" fill="#94a3b8" font-size="9">Object Count</text>
    <rect x="55" y="44" width="10" height="3" fill="#f59e0b" rx="1"/>
    <text x="70" y="48" fill="#94a3b8" font-size="9">Clutter</text>
    <rect x="55" y="58" width="10" height="3" fill="#4ade80" rx="1"/>
    <text x="70" y="62" fill="#94a3b8" font-size="9">Lighting Range</text>
    <text x="215" y="248" fill="#64748b" font-size="9" text-anchor="middle">Curriculum Stage</text>
  </svg>
</div>

<!-- Chart 3: Curriculum Efficiency Comparison -->
<div class="card">
  <h2>Curriculum Efficiency — Convergence to SR = 0.70</h2>
  <svg viewBox="0 0 400 260" width="100%" xmlns="http://www.w3.org/2000/svg">
    <line x1="50" y1="220" x2="380" y2="220" stroke="#334155" stroke-width="1.5"/>
    <line x1="50" y1="20"  x2="50"  y2="220" stroke="#334155" stroke-width="1.5"/>
    <!-- y labels SR -->
    <text x="42" y="224" fill="#64748b" font-size="10" text-anchor="end">0.0</text>
    <text x="42" y="174" fill="#64748b" font-size="10" text-anchor="end">0.2</text>
    <text x="42" y="124" fill="#64748b" font-size="10" text-anchor="end">0.4</text>
    <text x="42" y="74"  fill="#64748b" font-size="10" text-anchor="end">0.6</text>
    <text x="42" y="28"  fill="#64748b" font-size="10" text-anchor="end">0.8</text>
    <!-- gridlines -->
    <line x1="50" y1="174" x2="380" y2="174" stroke="#334155" stroke-width="0.5" stroke-dasharray="3 3"/>
    <line x1="50" y1="124" x2="380" y2="124" stroke="#334155" stroke-width="0.5" stroke-dasharray="3 3"/>
    <line x1="50" y1="74"  x2="380" y2="74"  stroke="#334155" stroke-width="0.5" stroke-dasharray="3 3"/>
    <!-- SR=0.70 target line -->
    <line x1="50" y1="45" x2="380" y2="45" stroke="#C74634" stroke-width="1" stroke-dasharray="5 3"/>
    <text x="383" y="48" fill="#C74634" font-size="9">SR=0.70</text>
    <!-- x labels: steps 0->3200, range=330px -->
    <text x="50"  y="234" fill="#64748b" font-size="8" text-anchor="middle">0</text>
    <text x="133" y="234" fill="#64748b" font-size="8" text-anchor="middle">800</text>
    <text x="215" y="234" fill="#64748b" font-size="8" text-anchor="middle">1600</text>
    <text x="298" y="234" fill="#64748b" font-size="8" text-anchor="middle">2400</text>
    <text x="380" y="234" fill="#64748b" font-size="8" text-anchor="middle">3200</text>
    <!-- px per step = 330/3200 = 0.103 -->
    <!-- Random (gray): 0->3100 at SR=0.70; slow sigmoid -->
    <!-- pts at steps: 0->0.03, 400->0.08, 800->0.15, 1200->0.24, 1600->0.35, 2000->0.47, 2400->0.57, 2800->0.65, 3100->0.70 -->
    <!-- y = 220 - SR*200 -->
    <polyline points="50,214 91,204 133,190 174,172 215,150 227,126 268,106 289,87 370,80"
      fill="none" stroke="#64748b" stroke-width="2"/>
    <!-- Fixed (yellow): reaches 0.70 at ~2600 -->
    <polyline points="50,214 91,202 133,185 174,162 215,137 257,110 289,83 310,45 380,42"
      fill="none" stroke="#f59e0b" stroke-width="2"/>
    <!-- Adaptive (blue): reaches 0.70 at ~2100 -->
    <polyline points="50,214 91,200 133,180 174,154 215,122 247,90 268,60 289,46 380,40"
      fill="none" stroke="#38bdf8" stroke-width="2"/>
    <!-- Competence-based (green): fastest, ~1840 steps -->
    <polyline points="50,214 91,196 133,170 174,136 215,96 236,65 247,47 268,45 380,38"
      fill="none" stroke="#4ade80" stroke-width="2.5"/>
    <!-- convergence markers -->
    <circle cx="370" cy="80"  r="4" fill="#64748b"/>
    <circle cx="310" cy="45"  r="4" fill="#f59e0b"/>
    <circle cx="289" cy="46"  r="4" fill="#38bdf8"/>
    <circle cx="247" cy="47"  r="4" fill="#4ade80"/>
    <!-- legend -->
    <line x1="55" y1="33" x2="72" y2="33" stroke="#64748b" stroke-width="2"/>
    <text x="75" y="36" fill="#94a3b8" font-size="9">Random (3100)</text>
    <line x1="145" y1="33" x2="162" y2="33" stroke="#f59e0b" stroke-width="2"/>
    <text x="165" y="36" fill="#94a3b8" font-size="9">Fixed (2580)</text>
    <line x1="55" y1="47" x2="72" y2="47" stroke="#38bdf8" stroke-width="2"/>
    <text x="75" y="50" fill="#94a3b8" font-size="9">Adaptive (2100)</text>
    <line x1="145" y1="47" x2="162" y2="47" stroke="#4ade80" stroke-width="2.5"/>
    <text x="165" y="50" fill="#94a3b8" font-size="9">Competence (1840)</text>
    <text x="215" y="248" fill="#64748b" font-size="9" text-anchor="middle">Training Steps</text>
  </svg>
</div>
</div>

<div class="card">
  <h2>Curriculum Configuration</h2>
  <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-top:8px">
    <div>
      <div style="color:#38bdf8;font-size:0.85rem;font-weight:600;margin-bottom:8px">Strategy</div>
      <div style="color:#94a3b8;font-size:0.83rem;line-height:1.8">
        <span class="tag">competence-based</span><br/>
        Difficulty plateau detection<br/>
        Auto-advance on SR plateau &gt; 5 episodes<br/>
        Rollback on SR drop &gt; 15%
      </div>
    </div>
    <div>
      <div style="color:#38bdf8;font-size:0.85rem;font-weight:600;margin-bottom:8px">Stage Config</div>
      <div style="color:#94a3b8;font-size:0.83rem;line-height:1.8">
        12 stages x 200 episodes<br/>
        Min SR to advance: 0.60<br/>
        Max stage episodes: 400<br/>
        Warmup stages: 2 (no advance)
      </div>
    </div>
    <div>
      <div style="color:#38bdf8;font-size:0.85rem;font-weight:600;margin-bottom:8px">Performance</div>
      <div style="color:#94a3b8;font-size:0.83rem;line-height:1.8">
        40% fewer steps vs random<br/>
        1840 steps to SR = 0.70<br/>
        Plateau detection: +-0.02 window<br/>
        Efficiency gain: 1.69x over random
      </div>
    </div>
  </div>
</div>

</body>
</html>"""

if USE_FASTAPI:
    app = FastAPI(title="Sim Curriculum Generator", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def index():
        return HTML

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "sim_curriculum_generator", "port": 8628}

    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=8628)

else:
    from http.server import HTTPServer, BaseHTTPRequestHandler

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/health":
                body = b'{"status":"ok","service":"sim_curriculum_generator","port":8628}'
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
            else:
                body = HTML.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            pass

    if __name__ == "__main__":
        print("FastAPI not available, using HTTPServer on port 8628")
        HTTPServer(("0.0.0.0", 8628), Handler).serve_forever()
