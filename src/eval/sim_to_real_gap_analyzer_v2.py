# Sim-to-Real Gap Analyzer V2 — port 8968
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
<title>Sim-to-Real Gap Analyzer V2</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; padding: 2rem; }
  h1 { color: #C74634; font-size: 2rem; margin-bottom: 0.5rem; }
  h2 { color: #38bdf8; font-size: 1.2rem; margin: 1.5rem 0 0.75rem; }
  .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; margin-top: 1.5rem; }
  .card { background: #1e293b; border-radius: 12px; padding: 1.5rem; }
  .card h3 { color: #38bdf8; margin-bottom: 1rem; font-size: 1rem; }
  .metric { display: flex; justify-content: space-between; padding: 0.4rem 0; border-bottom: 1px solid #334155; }
  .metric:last-child { border-bottom: none; }
  .metric .label { color: #94a3b8; }
  .metric .value { color: #f1f5f9; font-weight: 600; }
  .tag { display: inline-block; padding: 0.2rem 0.6rem; border-radius: 4px; font-size: 0.75rem; font-weight: 600; margin-left: 0.5rem; }
  .tag-green { background: #064e3b; color: #6ee7b7; }
  .tag-blue { background: #0c4a6e; color: #7dd3fc; }
  .tag-red { background: #7f1d1d; color: #fca5a5; }
  svg text { font-family: 'Segoe UI', sans-serif; }
  .subtitle { color: #64748b; font-size: 0.9rem; margin-bottom: 1rem; }
</style>
</head>
<body>
<h1>Sim-to-Real Gap Analyzer V2</h1>
<p class="subtitle">Port 8968 &mdash; Decomposition &amp; Closure Trajectory Analysis</p>

<div class="grid">
  <!-- Gap Decomposition Pie -->
  <div class="card">
    <h3>Gap Decomposition by Source</h3>
    <svg viewBox="0 0 300 260" width="100%">
      <!-- Pie chart center: 150,130, radius 100 -->
      <!-- Visual 38%: 0 to 136.8 deg -->
      <!-- Physics 31%: 136.8 to 248.4 deg -->
      <!-- Sensor 18%: 248.4 to 313.2 deg -->
      <!-- Kinematics 13%: 313.2 to 360 deg -->

      <!-- Visual 38% slice: #C74634 -->
      <path d="M150,130 L150,30 A100,100 0 0,1 233.1,180.0 Z" fill="#C74634" opacity="0.85"/>
      <!-- Physics 31% slice: #38bdf8 -->
      <path d="M150,130 L233.1,180.0 A100,100 0 0,1 82.6,218.2 Z" fill="#38bdf8" opacity="0.85"/>
      <!-- Sensor 18% slice: #a78bfa -->
      <path d="M150,130 L82.6,218.2 A100,100 0 0,1 69.0,69.9 Z" fill="#a78bfa" opacity="0.85"/>
      <!-- Kinematics 13% slice: #34d399 -->
      <path d="M150,130 L69.0,69.9 A100,100 0 0,1 150,30 Z" fill="#34d399" opacity="0.85"/>

      <!-- Center label -->
      <circle cx="150" cy="130" r="38" fill="#1e293b"/>
      <text x="150" y="126" text-anchor="middle" fill="#e2e8f0" font-size="11">Total</text>
      <text x="150" y="142" text-anchor="middle" fill="#e2e8f0" font-size="13" font-weight="bold">100%</text>

      <!-- Legend -->
      <rect x="20" y="240" width="12" height="12" fill="#C74634" rx="2"/>
      <text x="36" y="251" fill="#e2e8f0" font-size="11">Visual 38%</text>
      <rect x="110" y="240" width="12" height="12" fill="#38bdf8" rx="2"/>
      <text x="126" y="251" fill="#e2e8f0" font-size="11">Physics 31%</text>
      <rect x="20" y="258" width="12" height="12" fill="#a78bfa" rx="2"/>
      <text x="36" y="269" fill="#e2e8f0" font-size="11">Sensor 18%</text>
      <rect x="110" y="258" width="12" height="12" fill="#34d399" rx="2"/>
      <text x="126" y="269" fill="#e2e8f0" font-size="11">Kinematics 13%</text>
    </svg>
  </div>

  <!-- Gap Closure Trajectory -->
  <div class="card">
    <h3>Gap Closure Trajectory (percentage points)</h3>
    <svg viewBox="0 0 300 220" width="100%">
      <!-- Axes -->
      <line x1="50" y1="20" x2="50" y2="170" stroke="#334155" stroke-width="1.5"/>
      <line x1="50" y1="170" x2="280" y2="170" stroke="#334155" stroke-width="1.5"/>

      <!-- Y axis labels (gap pp: 20 at bottom, 4 at top) -->
      <text x="44" y="174" text-anchor="end" fill="#64748b" font-size="9">0</text>
      <text x="44" y="148" text-anchor="end" fill="#64748b" font-size="9">4</text>
      <text x="44" y="124" text-anchor="end" fill="#64748b" font-size="9">8</text>
      <text x="44" y="99" text-anchor="end" fill="#64748b" font-size="9">12</text>
      <text x="44" y="74" text-anchor="end" fill="#64748b" font-size="9">16</text>
      <text x="44" y="49" text-anchor="end" fill="#64748b" font-size="9">20</text>

      <!-- grid lines -->
      <line x1="50" y1="148" x2="280" y2="148" stroke="#1e3a5f" stroke-width="0.5" stroke-dasharray="3,3"/>
      <line x1="50" y1="124" x2="280" y2="124" stroke="#1e3a5f" stroke-width="0.5" stroke-dasharray="3,3"/>
      <line x1="50" y1="99" x2="280" y2="99" stroke="#1e3a5f" stroke-width="0.5" stroke-dasharray="3,3"/>
      <line x1="50" y1="74" x2="280" y2="74" stroke="#1e3a5f" stroke-width="0.5" stroke-dasharray="3,3"/>
      <line x1="50" y1="49" x2="280" y2="49" stroke="#1e3a5f" stroke-width="0.5" stroke-dasharray="3,3"/>

      <!-- Data points: v1=18pp, v2=14pp, v3_target=8pp -->
      <!-- y = 170 - (val/20)*150 -->
      <!-- v1: y=170-(18/20)*150=170-135=35 -- wait, scale: 20pp maps to y=49 (top), 0 maps to y=170 -->
      <!-- y = 170 - (val/20)*(170-49) = 170 - val*6.05 -->
      <!-- v1(18): y=170-108.9=61.1 x=90 -->
      <!-- v2(14): y=170-84.7=85.3 x=165 -->
      <!-- v3(8):  y=170-48.4=121.6 x=240 -->

      <!-- Bars -->
      <rect x="75" y="61" width="35" height="109" fill="#C74634" opacity="0.8" rx="3"/>
      <rect x="150" y="85" width="35" height="85" fill="#38bdf8" opacity="0.8" rx="3"/>
      <rect x="225" y="122" width="35" height="48" fill="#34d399" opacity="0.8" rx="3" stroke-dasharray="4,2" stroke="#34d399" fill-opacity="0.4"/>

      <!-- Value labels -->
      <text x="92" y="56" text-anchor="middle" fill="#C74634" font-size="11" font-weight="bold">18pp</text>
      <text x="167" y="80" text-anchor="middle" fill="#38bdf8" font-size="11" font-weight="bold">14pp</text>
      <text x="242" y="117" text-anchor="middle" fill="#34d399" font-size="11" font-weight="bold">8pp*</text>

      <!-- X labels -->
      <text x="92" y="186" text-anchor="middle" fill="#94a3b8" font-size="10">v1</text>
      <text x="167" y="186" text-anchor="middle" fill="#94a3b8" font-size="10">v2</text>
      <text x="242" y="186" text-anchor="middle" fill="#94a3b8" font-size="10">v3 target</text>

      <!-- Trend arrow -->
      <line x1="92" y1="65" x2="240" y2="118" stroke="#f59e0b" stroke-width="1.5" stroke-dasharray="5,3" marker-end="url(#arrow)"/>
      <defs>
        <marker id="arrow" markerWidth="6" markerHeight="6" refX="3" refY="3" orient="auto">
          <path d="M0,0 L0,6 L6,3 Z" fill="#f59e0b"/>
        </marker>
      </defs>

      <text x="155" y="210" text-anchor="middle" fill="#64748b" font-size="9">* v3 target | Cosmos WM: -31% visual gap</text>
    </svg>
  </div>
</div>

<h2>Gap Breakdown Metrics</h2>
<div class="grid">
  <div class="card">
    <h3>Decomposition Detail</h3>
    <div class="metric"><span class="label">Visual Domain Gap</span><span class="value">38% <span class="tag tag-red">largest</span></span></div>
    <div class="metric"><span class="label">Physics Fidelity Gap</span><span class="value">31%</span></div>
    <div class="metric"><span class="label">Sensor Noise Gap</span><span class="value">18%</span></div>
    <div class="metric"><span class="label">Kinematics Gap</span><span class="value">13%</span></div>
    <div class="metric"><span class="label">Cosmos WM Visual Reduction</span><span class="value">-31% <span class="tag tag-green">improved</span></span></div>
  </div>
  <div class="card">
    <h3>Version Progression</h3>
    <div class="metric"><span class="label">v1 Total Gap</span><span class="value">18 pp</span></div>
    <div class="metric"><span class="label">v2 Total Gap</span><span class="value">14 pp <span class="tag tag-blue">&minus;4pp</span></span></div>
    <div class="metric"><span class="label">v3 Target Gap</span><span class="value">8 pp <span class="tag tag-green">&minus;6pp</span></span></div>
    <div class="metric"><span class="label">Overall Reduction</span><span class="value">55.6%</span></div>
    <div class="metric"><span class="label">Primary Driver</span><span class="value">Cosmos World Model</span></div>
  </div>
</div>

</body>
</html>
"""

if USE_FASTAPI:
    app = FastAPI(title="Sim-to-Real Gap Analyzer V2")

    @app.get("/", response_class=HTMLResponse)
    async def index():
        return HTML

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "sim_to_real_gap_analyzer_v2", "port": 8968}

    @app.get("/api/decomposition")
    async def decomposition():
        return {
            "visual": 38,
            "physics": 31,
            "sensor": 18,
            "kinematics": 13,
            "cosmos_wm_visual_reduction_pct": -31
        }

    @app.get("/api/trajectory")
    async def trajectory():
        return {
            "versions": [
                {"version": "v1", "gap_pp": 18},
                {"version": "v2", "gap_pp": 14},
                {"version": "v3_target", "gap_pp": 8}
            ],
            "overall_reduction_pct": round((1 - 8/18) * 100, 1)
        }

else:
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(HTML.encode())
        def log_message(self, fmt, *args):
            pass


if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8968)
    else:
        server = HTTPServer(("0.0.0.0", 8968), Handler)
        print("Serving on http://0.0.0.0:8968")
        server.serve_forever()
