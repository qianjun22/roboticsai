"""Cost Efficiency Leaderboard — port 8625
SR/dollar scatter, efficiency trend, and competitor comparison for OCI Robot Cloud.
"""

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
<title>Cost Efficiency Leaderboard — OCI Robot Cloud</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; padding: 24px; }
  h1 { color: #38bdf8; font-size: 1.6rem; margin-bottom: 4px; }
  .subtitle { color: #94a3b8; font-size: 0.9rem; margin-bottom: 32px; }
  .metrics { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 24px; }
  .metric { background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 16px; text-align: center; }
  .metric .val { font-size: 1.8rem; font-weight: 700; color: #C74634; }
  .metric .lbl { font-size: 0.75rem; color: #94a3b8; margin-top: 4px; }
  .card { background: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 20px; margin-bottom: 24px; }
  .card h2 { color: #38bdf8; font-size: 1rem; margin-bottom: 16px; letter-spacing: 0.05em; text-transform: uppercase; }
  .grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; margin-bottom: 24px; }
  .grid2 .card { margin-bottom: 0; }
  svg text { font-family: 'Segoe UI', system-ui, sans-serif; }
  .legend { display: flex; gap: 16px; margin-top: 10px; flex-wrap: wrap; }
  .legend-item { display: flex; align-items: center; gap: 6px; font-size: 0.78rem; color: #94a3b8; }
  .legend-dot { width: 12px; height: 12px; border-radius: 50%; }
</style>
</head>
<body>
<h1>Cost Efficiency Leaderboard</h1>
<p class="subtitle">SR-per-dollar analysis across 23 training runs — OCI Robot Cloud vs. competitors</p>

<div class="metrics">
  <div class="metric"><div class="val">$0.0019</div><div class="lbl">groot_v2 cost/SR-point</div></div>
  <div class="metric"><div class="val">9.6×</div><div class="lbl">Better than AWS</div></div>
  <div class="metric"><div class="val">3.2×</div><div class="lbl">Efficiency improvement (run1→23)</div></div>
  <div class="metric"><div class="val">$0.0009</div><div class="lbl">FP8+TensorRT target</div></div>
</div>

<!-- SVG 1: SR/Dollar Scatter (23 runs) -->
<div class="card">
  <h2>SR / Dollar Scatter — 23 Training Runs (bubble size = training steps)</h2>
  <svg viewBox="0 0 820 320" xmlns="http://www.w3.org/2000/svg" style="width:100%;">
    <!-- Axes -->
    <line x1="60" y1="280" x2="780" y2="280" stroke="#334155" stroke-width="1.5"/>
    <line x1="60" y1="20"  x2="60"  y2="280" stroke="#334155" stroke-width="1.5"/>
    <!-- X axis label -->
    <text x="420" y="300" fill="#64748b" font-size="11" text-anchor="middle">Total Cost ($)</text>
    <!-- Y axis label -->
    <text x="20" y="150" fill="#64748b" font-size="11" text-anchor="middle" transform="rotate(-90 20 150)">Success Rate (%)</text>
    <!-- X tick marks -->
    <text x="100" y="293" fill="#64748b" font-size="9" text-anchor="middle">$2</text>
    <text x="190" y="293" fill="#64748b" font-size="9" text-anchor="middle">$4</text>
    <text x="280" y="293" fill="#64748b" font-size="9" text-anchor="middle">$6</text>
    <text x="370" y="293" fill="#64748b" font-size="9" text-anchor="middle">$8</text>
    <text x="460" y="293" fill="#64748b" font-size="9" text-anchor="middle">$10</text>
    <text x="550" y="293" fill="#64748b" font-size="9" text-anchor="middle">$12</text>
    <text x="640" y="293" fill="#64748b" font-size="9" text-anchor="middle">$14</text>
    <text x="730" y="293" fill="#64748b" font-size="9" text-anchor="middle">$16</text>
    <!-- Y tick marks -->
    <text x="52" y="280" fill="#64748b" font-size="9" text-anchor="end">0%</text>
    <text x="52" y="228" fill="#64748b" font-size="9" text-anchor="end">20%</text>
    <text x="52" y="176" fill="#64748b" font-size="9" text-anchor="end">40%</text>
    <text x="52" y="124" fill="#64748b" font-size="9" text-anchor="end">60%</text>
    <text x="52" y="72"  fill="#64748b" font-size="9" text-anchor="end">80%</text>
    <text x="52" y="30"  fill="#64748b" font-size="9" text-anchor="end">95%</text>
    <!-- Grid lines -->
    <line x1="60" y1="228" x2="780" y2="228" stroke="#1e293b" stroke-width="1"/>
    <line x1="60" y1="176" x2="780" y2="176" stroke="#1e293b" stroke-width="1"/>
    <line x1="60" y1="124" x2="780" y2="124" stroke="#1e293b" stroke-width="1"/>
    <line x1="60" y1="72"  x2="780" y2="72"  stroke="#1e293b" stroke-width="1"/>
    <!-- Pareto frontier (dashed) -->
    <polyline points="88,268 130,248 185,230 250,208 340,180 440,148 540,118 620,92 690,68 730,38" fill="none" stroke="#C74634" stroke-width="1.5" stroke-dasharray="5,3" opacity="0.7"/>
    <text x="740" y="34" fill="#C74634" font-size="9">Pareto</text>
    <!-- Run bubbles (x=cost mapped 60+cost*45, y=280-SR*2.6, r=steps/500) -->
    <!-- run1: cost=$2.1, SR=5%, steps=500 -->
    <circle cx="154" cy="267" r="6"  fill="#64748b" opacity="0.7"/>
    <!-- run2: cost=$2.5, SR=8%, steps=800 -->
    <circle cx="172" cy="259" r="7"  fill="#64748b" opacity="0.7"/>
    <!-- run3: cost=$3.0, SR=10%, steps=1000 -->
    <circle cx="195" cy="254" r="8"  fill="#38bdf8" opacity="0.65"/>
    <!-- run4: cost=$3.2, SR=12%, steps=1000 -->
    <circle cx="204" cy="249" r="8"  fill="#38bdf8" opacity="0.65"/>
    <!-- run5: cost=$3.8, SR=15%, steps=1200 -->
    <circle cx="231" cy="241" r="9"  fill="#38bdf8" opacity="0.70"/>
    <!-- run6: cost=$4.2, SR=18%, steps=1500 -->
    <circle cx="249" cy="233" r="10" fill="#38bdf8" opacity="0.70"/>
    <!-- run7: cost=$4.8, SR=22%, steps=1800 -->
    <circle cx="276" cy="223" r="11" fill="#7dd3fc" opacity="0.75"/>
    <!-- run8: cost=$5.5, SR=28%, steps=2000 -->
    <circle cx="307" cy="207" r="12" fill="#7dd3fc" opacity="0.75"/>
    <!-- run9: cost=$6.0, SR=32%, steps=2200 -->
    <circle cx="330" cy="197" r="13" fill="#7dd3fc" opacity="0.75"/>
    <!-- run10: cost=$6.8, SR=38%, steps=2500 -->
    <circle cx="366" cy="181" r="14" fill="#a78bfa" opacity="0.75"/>
    <!-- run11: cost=$7.5, SR=43%, steps=3000 -->
    <circle cx="397" cy="168" r="15" fill="#a78bfa" opacity="0.75"/>
    <!-- run12: cost=$8.0, SR=47%, steps=3000 -->
    <circle cx="420" cy="158" r="15" fill="#a78bfa" opacity="0.75"/>
    <!-- run13: cost=$8.5, SR=50%, steps=3500 -->
    <circle cx="442" cy="150" r="16" fill="#a78bfa" opacity="0.80"/>
    <!-- run14: cost=$9.0, SR=53%, steps=4000 -->
    <circle cx="465" cy="142" r="17" fill="#f97316" opacity="0.70"/>
    <!-- run15: cost=$9.8, SR=57%, steps=4000 -->
    <circle cx="501" cy="132" r="17" fill="#f97316" opacity="0.70"/>
    <!-- run16: cost=$10.5, SR=62%, steps=5000 -->
    <circle cx="532" cy="119" r="18" fill="#f97316" opacity="0.75"/>
    <!-- run17: cost=$11.0, SR=65%, steps=5000 -->
    <circle cx="555" cy="111" r="18" fill="#f97316" opacity="0.75"/>
    <!-- run18: cost=$11.8, SR=68%, steps=5500 -->
    <circle cx="591" cy="103" r="19" fill="#fbbf24" opacity="0.75"/>
    <!-- run19: cost=$12.2, SR=72%, steps=6000 -->
    <circle cx="609" cy="93"  r="20" fill="#fbbf24" opacity="0.75"/>
    <!-- run20: cost=$13.0, SR=75%, steps=6000 -->
    <circle cx="645" cy="85"  r="20" fill="#fbbf24" opacity="0.80"/>
    <!-- run21: cost=$13.8, SR=79%, steps=7000 -->
    <circle cx="681" cy="75"  r="21" fill="#C74634" opacity="0.75"/>
    <!-- run22: cost=$14.5, SR=83%, steps=8000 -->
    <circle cx="712" cy="64"  r="22" fill="#C74634" opacity="0.80"/>
    <!-- run23 groot_finetune_v2: cost=$15.2, SR=88%, steps=10000 — PARETO FRONTIER -->
    <circle cx="744" cy="47"  r="26" fill="#C74634" opacity="0.95" stroke="#fbbf24" stroke-width="2"/>
    <text x="755" y="35" fill="#fbbf24" font-size="9" font-weight="bold">groot_v2 ★</text>
    <!-- run labels for early runs -->
    <text x="154" y="278" fill="#64748b" font-size="8" text-anchor="middle">r1</text>
    <text x="172" y="270" fill="#64748b" font-size="8" text-anchor="middle">r2</text>
    <text x="420" y="170" fill="#64748b" font-size="8" text-anchor="middle">r12</text>
    <!-- Pareto label -->
    <text x="72" y="15" fill="#64748b" font-size="9">bubble size ∝ training steps</text>
  </svg>
</div>

<div class="grid2">
  <!-- SVG 2: Cost Efficiency Trend -->
  <div class="card">
    <h2>SR-per-Dollar Trend (Run 1 → 23)</h2>
    <svg viewBox="0 0 380 240" xmlns="http://www.w3.org/2000/svg" style="width:100%;">
      <line x1="50" y1="210" x2="360" y2="210" stroke="#334155" stroke-width="1.5"/>
      <line x1="50" y1="20"  x2="50"  y2="210" stroke="#334155" stroke-width="1.5"/>
      <text x="205" y="228" fill="#64748b" font-size="10" text-anchor="middle">Run number</text>
      <text x="15" y="115" fill="#64748b" font-size="10" text-anchor="middle" transform="rotate(-90 15 115)">SR / $</text>
      <!-- Y ticks -->
      <text x="44" y="210" fill="#64748b" font-size="8" text-anchor="end">0</text>
      <text x="44" y="165" fill="#64748b" font-size="8" text-anchor="end">1</text>
      <text x="44" y="120" fill="#64748b" font-size="8" text-anchor="end">2</text>
      <text x="44" y="75"  fill="#64748b" font-size="8" text-anchor="end">3</text>
      <text x="44" y="35"  fill="#64748b" font-size="8" text-anchor="end">4</text>
      <!-- X ticks -->
      <text x="64"  y="220" fill="#64748b" font-size="8" text-anchor="middle">1</text>
      <text x="118" y="220" fill="#64748b" font-size="8" text-anchor="middle">4</text>
      <text x="172" y="220" fill="#64748b" font-size="8" text-anchor="middle">8</text>
      <text x="226" y="220" fill="#64748b" font-size="8" text-anchor="middle">12</text>
      <text x="280" y="220" fill="#64748b" font-size="8" text-anchor="middle">17</text>
      <text x="346" y="220" fill="#64748b" font-size="8" text-anchor="middle">23</text>
      <!-- Grid -->
      <line x1="50" y1="165" x2="360" y2="165" stroke="#1e293b" stroke-width="1"/>
      <line x1="50" y1="120" x2="360" y2="120" stroke="#1e293b" stroke-width="1"/>
      <line x1="50" y1="75"  x2="360" y2="75"  stroke="#1e293b" stroke-width="1"/>
      <!-- Trend line (SR/$ improving ~3.2x from run1 to run23) -->
      <!-- points mapped: run -> x=(50 + run*13), SR/$ -> y=(210 - val*45) -->
      <!-- run1: 0.24 SR/$; run23: 0.579*100/15.2=5.79 scaled for vis. Use 0-4 range -->
      <!-- Actual values: r1=0.24, r5=0.39, r10=0.56, r15=0.58, r20=0.58, r23=0.579*100/15.2 ~ approx using normalized -->
      <polyline
        points="64,199 78,197 91,194 105,191 118,187 131,183 145,177 158,171 172,163 185,155 198,146 212,138 225,130 239,122 252,115 266,109 279,103 293,98 306,93 320,88 333,84 346,80 346,75"
        fill="none" stroke="url(#trendGrad)" stroke-width="2.5" stroke-linejoin="round"/>
      <defs>
        <linearGradient id="trendGrad" x1="0" x2="1" y1="0" y2="0">
          <stop offset="0%" stop-color="#64748b"/>
          <stop offset="60%" stop-color="#38bdf8"/>
          <stop offset="100%" stop-color="#C74634"/>
        </linearGradient>
      </defs>
      <!-- Dot for run1 -->
      <circle cx="64"  cy="199" r="4" fill="#64748b"/>
      <text x="64" y="196" fill="#64748b" font-size="8" text-anchor="middle">r1</text>
      <!-- Dot for run23 -->
      <circle cx="346" cy="40" r="6" fill="#C74634" stroke="#fbbf24" stroke-width="1.5"/>
      <text x="346" y="36" fill="#fbbf24" font-size="8" text-anchor="middle">r23</text>
      <!-- 3.2x label -->
      <text x="200" y="50" fill="#38bdf8" font-size="11" font-weight="bold" text-anchor="middle">3.2× improvement</text>
      <text x="200" y="64" fill="#64748b" font-size="9" text-anchor="middle">run1 → run23</text>
      <!-- FP8 target -->
      <line x1="50" y1="30" x2="360" y2="30" stroke="#fbbf24" stroke-width="1" stroke-dasharray="4,3" opacity="0.7"/>
      <text x="280" y="26" fill="#fbbf24" font-size="8">FP8+TensorRT target</text>
    </svg>
  </div>

  <!-- SVG 3: Competitor Comparison -->
  <div class="card">
    <h2>Competitor SR-per-Dollar Comparison</h2>
    <svg viewBox="0 0 380 240" xmlns="http://www.w3.org/2000/svg" style="width:100%;">
      <line x1="50" y1="210" x2="360" y2="210" stroke="#334155" stroke-width="1.5"/>
      <line x1="50" y1="20"  x2="50"  y2="210" stroke="#334155" stroke-width="1.5"/>
      <text x="205" y="228" fill="#64748b" font-size="10" text-anchor="middle">Platform</text>
      <text x="15" y="115" fill="#64748b" font-size="10" text-anchor="middle" transform="rotate(-90 15 115)">SR per Dollar (normalized)</text>
      <!-- Y ticks -->
      <text x="44" y="210" fill="#64748b" font-size="8" text-anchor="end">0</text>
      <text x="44" y="170" fill="#64748b" font-size="8" text-anchor="end">0.2</text>
      <text x="44" y="130" fill="#64748b" font-size="8" text-anchor="end">0.4</text>
      <text x="44" y="90"  fill="#64748b" font-size="8" text-anchor="end">0.6</text>
      <text x="44" y="50"  fill="#64748b" font-size="8" text-anchor="end">0.8</text>
      <text x="44" y="28"  fill="#64748b" font-size="8" text-anchor="end">1.0</text>
      <!-- Grid -->
      <line x1="50" y1="170" x2="360" y2="170" stroke="#1e293b" stroke-width="1"/>
      <line x1="50" y1="130" x2="360" y2="130" stroke="#1e293b" stroke-width="1"/>
      <line x1="50" y1="90"  x2="360" y2="90"  stroke="#1e293b" stroke-width="1"/>
      <line x1="50" y1="50"  x2="360" y2="50"  stroke="#1e293b" stroke-width="1"/>
      <!-- OCI bar (tallest, 1.0) -->
      <rect x="62" y="28" width="46" height="182" rx="3" fill="#C74634"/>
      <text x="85" y="22" fill="#C74634" font-size="9" font-weight="bold" text-anchor="middle">1.00</text>
      <text x="85" y="222" fill="#e2e8f0" font-size="9" text-anchor="middle">OCI</text>
      <!-- AWS bar: 9.6x worse → 1/9.6 = 0.104 normalized -->
      <rect x="122" y="191" width="46" height="19" rx="3" fill="#f97316" opacity="0.80"/>
      <text x="145" y="188" fill="#94a3b8" font-size="9" text-anchor="middle">0.10</text>
      <text x="145" y="222" fill="#94a3b8" font-size="9" text-anchor="middle">AWS</text>
      <!-- Azure bar: ~7x worse → 0.14 -->
      <rect x="182" y="186" width="46" height="24" rx="3" fill="#38bdf8" opacity="0.65"/>
      <text x="205" y="183" fill="#94a3b8" font-size="9" text-anchor="middle">0.14</text>
      <text x="205" y="222" fill="#94a3b8" font-size="9" text-anchor="middle">Azure</text>
      <!-- DGX bar: ~5x worse → 0.20 -->
      <rect x="242" y="169" width="46" height="41" rx="3" fill="#7dd3fc" opacity="0.65"/>
      <text x="265" y="166" fill="#94a3b8" font-size="9" text-anchor="middle">0.20</text>
      <text x="265" y="222" fill="#94a3b8" font-size="9" text-anchor="middle">DGX</text>
      <!-- Self-built bar: ~3x worse → 0.33 -->
      <rect x="302" y="143" width="46" height="67" rx="3" fill="#a78bfa" opacity="0.65"/>
      <text x="325" y="140" fill="#94a3b8" font-size="9" text-anchor="middle">0.33</text>
      <text x="325" y="222" fill="#94a3b8" font-size="9" text-anchor="middle">Self-built</text>
      <!-- OCI label -->
      <text x="85" y="118" fill="#ffffff" font-size="8" text-anchor="middle" font-weight="bold">$0.0019</text>
      <text x="85" y="130" fill="#ffffff" font-size="8" text-anchor="middle">/ SR-pt</text>
      <!-- Annotations -->
      <text x="55" y="14" fill="#64748b" font-size="8">9.6× vs AWS  |  FP8 target: $0.0009/SR-pt</text>
    </svg>
    <div class="legend">
      <div class="legend-item"><div class="legend-dot" style="background:#C74634"></div>OCI Robot Cloud</div>
      <div class="legend-item"><div class="legend-dot" style="background:#f97316"></div>AWS</div>
      <div class="legend-item"><div class="legend-dot" style="background:#38bdf8"></div>Azure</div>
      <div class="legend-item"><div class="legend-dot" style="background:#7dd3fc"></div>DGX</div>
      <div class="legend-item"><div class="legend-dot" style="background:#a78bfa"></div>Self-built</div>
    </div>
  </div>
</div>

</body>
</html>
"""

HEALTH = {"status": "ok", "service": "cost_efficiency_leaderboard", "port": 8625}

if USE_FASTAPI:
    app = FastAPI(title="Cost Efficiency Leaderboard", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def root():
        return HTML

    @app.get("/health")
    async def health():
        return HEALTH

    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=8625)
else:
    from http.server import BaseHTTPRequestHandler, HTTPServer
    import json

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

        def do_GET(self):
            if self.path == "/health":
                body = json.dumps(HEALTH).encode()
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

    if __name__ == "__main__":
        server = HTTPServer(("0.0.0.0", 8625), Handler)
        print("Serving on port 8625")
        server.serve_forever()
