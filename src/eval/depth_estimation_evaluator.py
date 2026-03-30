# Depth Estimation Evaluator Service — port 8674
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
  <title>Depth Estimation Evaluator</title>
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
  <h1>Depth Estimation Evaluator</h1>
  <p class="subtitle">Port 8674 &nbsp;|&nbsp; OCI Robot Cloud &nbsp;|&nbsp; Stereo + Mono Depth Analysis</p>

  <div class="grid">

    <!-- Card 1: Depth Error Heatmap -->
    <div class="card">
      <h2>Depth Error Heatmap (8x6 Region Grid)</h2>
      <svg viewBox="0 0 400 300" xmlns="http://www.w3.org/2000/svg">
        <!-- 8 cols x 6 rows = 48 cells; edges/corners warm, center cool -->
        <!-- Row 0 (top) -->
        <rect x="0"   y="0"   width="50" height="50" fill="#dc2626"/>
        <rect x="50"  y="0"   width="50" height="50" fill="#ef4444"/>
        <rect x="100" y="0"   width="50" height="50" fill="#f97316"/>
        <rect x="150" y="0"   width="50" height="50" fill="#fb923c"/>
        <rect x="200" y="0"   width="50" height="50" fill="#fb923c"/>
        <rect x="250" y="0"   width="50" height="50" fill="#f97316"/>
        <rect x="300" y="0"   width="50" height="50" fill="#ef4444"/>
        <rect x="350" y="0"   width="50" height="50" fill="#dc2626"/>
        <!-- Row 1 -->
        <rect x="0"   y="50"  width="50" height="50" fill="#ef4444"/>
        <rect x="50"  y="50"  width="50" height="50" fill="#f59e0b"/>
        <rect x="100" y="50"  width="50" height="50" fill="#fbbf24"/>
        <rect x="150" y="50"  width="50" height="50" fill="#a3e635"/>
        <rect x="200" y="50"  width="50" height="50" fill="#a3e635"/>
        <rect x="250" y="50"  width="50" height="50" fill="#fbbf24"/>
        <rect x="300" y="50"  width="50" height="50" fill="#f59e0b"/>
        <rect x="350" y="50"  width="50" height="50" fill="#ef4444"/>
        <!-- Row 2 -->
        <rect x="0"   y="100" width="50" height="50" fill="#f97316"/>
        <rect x="50"  y="100" width="50" height="50" fill="#fbbf24"/>
        <rect x="100" y="100" width="50" height="50" fill="#4ade80"/>
        <rect x="150" y="100" width="50" height="50" fill="#22d3ee"/>
        <rect x="200" y="100" width="50" height="50" fill="#22d3ee"/>
        <rect x="250" y="100" width="50" height="50" fill="#4ade80"/>
        <rect x="300" y="100" width="50" height="50" fill="#fbbf24"/>
        <rect x="350" y="100" width="50" height="50" fill="#f97316"/>
        <!-- Row 3 -->
        <rect x="0"   y="150" width="50" height="50" fill="#f97316"/>
        <rect x="50"  y="150" width="50" height="50" fill="#fbbf24"/>
        <rect x="100" y="150" width="50" height="50" fill="#4ade80"/>
        <rect x="150" y="150" width="50" height="50" fill="#38bdf8"/>
        <rect x="200" y="150" width="50" height="50" fill="#38bdf8"/>
        <rect x="250" y="150" width="50" height="50" fill="#4ade80"/>
        <rect x="300" y="150" width="50" height="50" fill="#fbbf24"/>
        <rect x="350" y="150" width="50" height="50" fill="#f97316"/>
        <!-- Row 4 -->
        <rect x="0"   y="200" width="50" height="50" fill="#ef4444"/>
        <rect x="50"  y="200" width="50" height="50" fill="#f59e0b"/>
        <rect x="100" y="200" width="50" height="50" fill="#fbbf24"/>
        <rect x="150" y="200" width="50" height="50" fill="#a3e635"/>
        <rect x="200" y="200" width="50" height="50" fill="#a3e635"/>
        <rect x="250" y="200" width="50" height="50" fill="#fbbf24"/>
        <rect x="300" y="200" width="50" height="50" fill="#f59e0b"/>
        <rect x="350" y="200" width="50" height="50" fill="#ef4444"/>
        <!-- Row 5 (bottom) -->
        <rect x="0"   y="250" width="50" height="50" fill="#dc2626"/>
        <rect x="50"  y="250" width="50" height="50" fill="#ef4444"/>
        <rect x="100" y="250" width="50" height="50" fill="#f97316"/>
        <rect x="150" y="250" width="50" height="50" fill="#fb923c"/>
        <rect x="200" y="250" width="50" height="50" fill="#fb923c"/>
        <rect x="250" y="250" width="50" height="50" fill="#f97316"/>
        <rect x="300" y="250" width="50" height="50" fill="#ef4444"/>
        <rect x="350" y="250" width="50" height="50" fill="#dc2626"/>
        <!-- Grid lines -->
        <g stroke="#0f172a" stroke-width="1" opacity="0.6">
          <line x1="50"  y1="0" x2="50"  y2="300"/>
          <line x1="100" y1="0" x2="100" y2="300"/>
          <line x1="150" y1="0" x2="150" y2="300"/>
          <line x1="200" y1="0" x2="200" y2="300"/>
          <line x1="250" y1="0" x2="250" y2="300"/>
          <line x1="300" y1="0" x2="300" y2="300"/>
          <line x1="350" y1="0" x2="350" y2="300"/>
          <line x1="0" y1="50"  x2="400" y2="50"/>
          <line x1="0" y1="100" x2="400" y2="100"/>
          <line x1="0" y1="150" x2="400" y2="150"/>
          <line x1="0" y1="200" x2="400" y2="200"/>
          <line x1="0" y1="250" x2="400" y2="250"/>
        </g>
        <!-- Labels -->
        <text x="200" y="130" text-anchor="middle" fill="#0f172a" font-size="11" font-weight="bold">LOW ERROR</text>
        <text x="25"  y="25"  text-anchor="middle" fill="white"   font-size="9">HIGH</text>
        <text x="375" y="25"  text-anchor="middle" fill="white"   font-size="9">HIGH</text>
        <text x="25"  y="275" text-anchor="middle" fill="white"   font-size="9">HIGH</text>
        <text x="375" y="275" text-anchor="middle" fill="white"   font-size="9">HIGH</text>
      </svg>
      <p style="color:#64748b;font-size:0.72rem;margin-top:8px;">Warm = high depth error &nbsp;|&nbsp; Cool = low depth error &nbsp;|&nbsp; Edges/corners worst</p>
    </div>

    <!-- Card 2: Abs Error vs Distance -->
    <div class="card">
      <h2>Absolute Error vs Distance</h2>
      <svg viewBox="0 0 400 260" xmlns="http://www.w3.org/2000/svg">
        <!-- Axes -->
        <line x1="50" y1="220" x2="380" y2="220" stroke="#475569" stroke-width="1.5"/>
        <line x1="50" y1="20"  x2="50"  y2="220" stroke="#475569" stroke-width="1.5"/>
        <!-- Y grid lines -->
        <line x1="50" y1="170" x2="380" y2="170" stroke="#1e293b" stroke-width="1"/>
        <line x1="50" y1="120" x2="380" y2="120" stroke="#1e293b" stroke-width="1"/>
        <line x1="50" y1="70"  x2="380" y2="70"  stroke="#1e293b" stroke-width="1"/>
        <!-- Y labels -->
        <text x="44" y="224" text-anchor="end" fill="#64748b" font-size="10">0</text>
        <text x="44" y="174" text-anchor="end" fill="#64748b" font-size="10">10</text>
        <text x="44" y="124" text-anchor="end" fill="#64748b" font-size="10">25</text>
        <text x="44" y="74"  text-anchor="end" fill="#64748b" font-size="10">40</text>
        <!-- X labels: 0.1 to 2.0m mapped to x=50..380 -->
        <!-- x(d) = 50 + (d-0.1)/(2.0-0.1) * 330 -->
        <!-- y(e) = 220 - e/42 * 200 -->
        <text x="50"  y="234" text-anchor="middle" fill="#64748b" font-size="10">0.1</text>
        <text x="137" y="234" text-anchor="middle" fill="#64748b" font-size="10">0.6</text>
        <text x="224" y="234" text-anchor="middle" fill="#64748b" font-size="10">1.1</text>
        <text x="311" y="234" text-anchor="middle" fill="#64748b" font-size="10">1.6</text>
        <text x="380" y="234" text-anchor="middle" fill="#64748b" font-size="10">2.0</text>
        <!-- Axis labels -->
        <text x="215" y="252" text-anchor="middle" fill="#94a3b8" font-size="11">Distance (m)</text>
        <text x="14" y="130" text-anchor="middle" fill="#94a3b8" font-size="11" transform="rotate(-90,14,130)">Error (mm)</text>
        <!-- Stereo line: 2.1mm @ 0.1m → 18mm @ 2.0m -->
        <!-- y(2.1) = 220 - 2.1/42*200 = 210; y(18) = 220 - 18/42*200 = 134.3 -->
        <polyline
          points="50,210 137,195 224,175 311,155 380,134"
          fill="none" stroke="#38bdf8" stroke-width="2.5" stroke-linejoin="round"/>
        <!-- Mono line: 8.4mm @ 0.1m → 42mm @ 2.0m -->
        <!-- y(8.4) = 220 - 8.4/42*200 = 180; y(42) = 220 - 42/42*200 = 20 -->
        <polyline
          points="50,180 137,158 224,126 311,78 380,20"
          fill="none" stroke="#C74634" stroke-width="2.5" stroke-linejoin="round" stroke-dasharray="6,3"/>
        <!-- Legend -->
        <line x1="200" y1="40" x2="230" y2="40" stroke="#38bdf8" stroke-width="2.5"/>
        <text x="234" y="44" fill="#38bdf8" font-size="11">Stereo</text>
        <line x1="200" y1="58" x2="230" y2="58" stroke="#C74634" stroke-width="2.5" stroke-dasharray="6,3"/>
        <text x="234" y="62" fill="#C74634" font-size="11">Mono</text>
      </svg>
    </div>

    <!-- Card 3: Confidence Distribution -->
    <div class="card">
      <h2>Confidence Distribution Histogram</h2>
      <svg viewBox="0 0 400 260" xmlns="http://www.w3.org/2000/svg">
        <!-- Low-confidence region highlight -->
        <rect x="50" y="20" width="66" height="200" fill="#7f1d1d" opacity="0.35" rx="2"/>
        <text x="83" y="230" text-anchor="middle" fill="#ef4444" font-size="9">Low conf</text>
        <!-- Axes -->
        <line x1="50" y1="220" x2="380" y2="220" stroke="#475569" stroke-width="1.5"/>
        <line x1="50" y1="20"  x2="50"  y2="220" stroke="#475569" stroke-width="1.5"/>
        <!-- Bars: 10 bins, width=33 each, x starts 50 -->
        <!-- bins: 0-0.1, 0.1-0.2, ..., 0.9-1.0 -->
        <!-- heights (% of pixels): 2,3,4,5,7,12,18,25,30,35 → scale to 200px max(35)→174px -->
        <!-- bar heights scaled: h = val/35*174 -->
        <!-- Low conf (<0.4) = bins 0-3 = red; rest = teal -->
        <rect x="50"  y="210" width="32" height="10"  fill="#ef4444" rx="2"/> <!-- 0.0-0.1: 2% -->
        <rect x="83"  y="205" width="32" height="15"  fill="#ef4444" rx="2"/> <!-- 0.1-0.2: 3% -->
        <rect x="116" y="200" width="32" height="20"  fill="#ef4444" rx="2"/> <!-- 0.2-0.3: 4% -->
        <rect x="149" y="195" width="32" height="25"  fill="#ef4444" rx="2"/> <!-- 0.3-0.4: 5% -->
        <rect x="182" y="185" width="32" height="35"  fill="#38bdf8" opacity="0.8" rx="2"/> <!-- 0.4-0.5: 7% -->
        <rect x="215" y="161" width="32" height="59"  fill="#38bdf8" opacity="0.85" rx="2"/> <!-- 0.5-0.6: 12% -->
        <rect x="248" y="132" width="32" height="88"  fill="#38bdf8" opacity="0.9" rx="2"/> <!-- 0.6-0.7: 18% -->
        <rect x="281" y="98"  width="32" height="122" fill="#38bdf8" opacity="0.95" rx="2"/> <!-- 0.7-0.8: 25% -->
        <rect x="314" y="72"  width="16" height="148" fill="#38bdf8" rx="2"/>              <!-- 0.8-0.9: 30% -->
        <rect x="331" y="49"  width="16" height="171" fill="#22d3ee" rx="2"/>              <!-- 0.9-1.0: 35% -->
        <!-- X labels -->
        <text x="66"  y="240" text-anchor="middle" fill="#64748b" font-size="9">0.1</text>
        <text x="132" y="240" text-anchor="middle" fill="#64748b" font-size="9">0.3</text>
        <text x="198" y="240" text-anchor="middle" fill="#64748b" font-size="9">0.5</text>
        <text x="264" y="240" text-anchor="middle" fill="#64748b" font-size="9">0.7</text>
        <text x="331" y="240" text-anchor="middle" fill="#64748b" font-size="9">0.9</text>
        <!-- Axis labels -->
        <text x="215" y="255" text-anchor="middle" fill="#94a3b8" font-size="11">Confidence Score</text>
        <!-- Legend -->
        <rect x="200" y="25" width="12" height="12" fill="#ef4444" rx="2"/>
        <text x="216" y="36" fill="#ef4444" font-size="10">Low (&lt;0.4)</text>
        <rect x="270" y="25" width="12" height="12" fill="#38bdf8" rx="2"/>
        <text x="286" y="36" fill="#38bdf8" font-size="10">High</text>
      </svg>
    </div>

  </div>

  <div class="metrics">
    <div class="metric"><div class="val">2.1 mm</div><div class="lbl">Stereo RMS @ 0.5m</div></div>
    <div class="metric"><div class="val">8.4 mm</div><div class="lbl">Mono RMS @ 0.5m</div></div>
    <div class="metric"><div class="val">&lt;0.4</div><div class="lbl">Textureless failure threshold</div></div>
    <div class="metric"><div class="val">+0.07pp</div><div class="lbl">SR gain (distant grasps)</div></div>
    <div class="metric"><div class="val">18 mm</div><div class="lbl">Stereo error @ 2.0m</div></div>
    <div class="metric"><div class="val">42 mm</div><div class="lbl">Mono error @ 2.0m</div></div>
  </div>
</body>
</html>
"""

if USE_FASTAPI:
    app = FastAPI(title="Depth Estimation Evaluator", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def root():
        return HTML

    @app.get("/health")
    async def health():
        return JSONResponse({"status": "ok", "service": "depth_estimation_evaluator", "port": 8674})

    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=8674)

else:
    from http.server import HTTPServer, BaseHTTPRequestHandler
    import json

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass
        def do_GET(self):
            if self.path == "/health":
                body = json.dumps({"status": "ok", "service": "depth_estimation_evaluator", "port": 8674}).encode()
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
        server = HTTPServer(("0.0.0.0", 8674), Handler)
        print("Serving on port 8674")
        server.serve_forever()
