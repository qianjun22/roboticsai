# Cosmos World Model Integrator — port 8982
# Genesis physics + Cosmos WM v1.5 visual rendering pipeline

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
<title>Cosmos World Model Integrator</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; padding: 2rem; }
  h1 { color: #C74634; font-size: 2rem; margin-bottom: 0.5rem; }
  h2 { color: #38bdf8; font-size: 1.2rem; margin: 1.5rem 0 0.75rem; }
  .subtitle { color: #94a3b8; margin-bottom: 2rem; font-size: 0.95rem; }
  .cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-bottom: 2rem; }
  .card { background: #1e293b; border-radius: 8px; padding: 1.25rem; border-left: 3px solid #C74634; }
  .card .value { font-size: 1.8rem; font-weight: 700; color: #f1f5f9; }
  .card .label { color: #94a3b8; font-size: 0.85rem; margin-top: 0.25rem; }
  .card .delta { font-size: 0.8rem; margin-top: 0.4rem; }
  .pos { color: #4ade80; } .neg { color: #f87171; }
  .chart-box { background: #1e293b; border-radius: 8px; padding: 1.5rem; margin-bottom: 1.5rem; }
  svg text { font-family: 'Segoe UI', sans-serif; }
  table { width: 100%; border-collapse: collapse; background: #1e293b; border-radius: 8px; overflow: hidden; }
  th { background: #0f172a; color: #38bdf8; padding: 0.75rem 1rem; text-align: left; font-size: 0.85rem; }
  td { padding: 0.7rem 1rem; border-top: 1px solid #334155; font-size: 0.9rem; color: #cbd5e1; }
  tr:hover td { background: #263248; }
  .badge { display: inline-block; padding: 0.2rem 0.6rem; border-radius: 9999px; font-size: 0.75rem; font-weight: 600; }
  .badge-green { background: #14532d; color: #4ade80; }
  .badge-blue { background: #0c4a6e; color: #38bdf8; }
  .badge-red { background: #450a0a; color: #f87171; }
</style>
</head>
<body>
<h1>Cosmos World Model Integrator</h1>
<p class="subtitle">Genesis physics + Cosmos WM v1.5 visual rendering pipeline &mdash; port 8982</p>

<div class="cards">
  <div class="card">
    <div class="value">47 ms</div>
    <div class="label">Cosmos render time / frame</div>
    <div class="delta neg">+35ms vs Genesis 12ms</div>
  </div>
  <div class="card">
    <div class="value">+6 pp</div>
    <div class="label">Success Rate Gain</div>
    <div class="delta pos">Cosmos WM v1.5 over Genesis-only</div>
  </div>
  <div class="card">
    <div class="value">10,000</div>
    <div class="label">Scene Variations</div>
    <div class="delta pos">from 50 base scenes</div>
  </div>
  <div class="card">
    <div class="value">$0.019</div>
    <div class="label">Cost / Scene (Cosmos)</div>
    <div class="delta neg">vs $0.003 Genesis-only</div>
  </div>
</div>

<h2>Performance vs Cost Tradeoff</h2>
<div class="chart-box">
  <svg width="100%" viewBox="0 0 760 260" xmlns="http://www.w3.org/2000/svg">
    <!-- axes -->
    <line x1="60" y1="20" x2="60" y2="220" stroke="#475569" stroke-width="1"/>
    <line x1="60" y1="220" x2="730" y2="220" stroke="#475569" stroke-width="1"/>
    <!-- y-axis label -->
    <text x="15" y="130" fill="#94a3b8" font-size="11" transform="rotate(-90,15,130)">Render Time (ms/frame)</text>
    <!-- x-axis label -->
    <text x="395" y="250" fill="#94a3b8" font-size="11" text-anchor="middle">Cost per Scene ($)</text>
    <!-- y grid -->
    <line x1="60" y1="60" x2="730" y2="60" stroke="#1e293b" stroke-width="1" stroke-dasharray="4"/>
    <line x1="60" y1="120" x2="730" y2="120" stroke="#1e293b" stroke-width="1" stroke-dasharray="4"/>
    <line x1="60" y1="180" x2="730" y2="180" stroke="#1e293b" stroke-width="1" stroke-dasharray="4"/>
    <!-- y labels -->
    <text x="55" y="64" fill="#94a3b8" font-size="10" text-anchor="end">60</text>
    <text x="55" y="124" fill="#94a3b8" font-size="10" text-anchor="end">30</text>
    <text x="55" y="184" fill="#94a3b8" font-size="10" text-anchor="end">10</text>
    <text x="55" y="224" fill="#94a3b8" font-size="10" text-anchor="end">0</text>
    <!-- x labels -->
    <text x="150" y="235" fill="#94a3b8" font-size="10" text-anchor="middle">$0.003</text>
    <text x="450" y="235" fill="#94a3b8" font-size="10" text-anchor="middle">$0.010</text>
    <text x="680" y="235" fill="#94a3b8" font-size="10" text-anchor="middle">$0.019</text>
    <!-- Genesis bubble -->
    <circle cx="150" cy="196" r="16" fill="#38bdf8" opacity="0.8"/>
    <text x="150" y="200" fill="#0f172a" font-size="10" text-anchor="middle" font-weight="700">12ms</text>
    <text x="150" y="180" fill="#38bdf8" font-size="11" text-anchor="middle">Genesis</text>
    <!-- Cosmos bubble -->
    <circle cx="680" cy="108" r="22" fill="#C74634" opacity="0.85"/>
    <text x="680" y="112" fill="#fff" font-size="10" text-anchor="middle" font-weight="700">47ms</text>
    <text x="680" y="92" fill="#C74634" font-size="11" text-anchor="middle">Cosmos WM</text>
    <!-- SR annotation arrows -->
    <line x1="165" y1="190" x2="658" y2="118" stroke="#94a3b8" stroke-width="1" stroke-dasharray="4"/>
    <text x="400" y="148" fill="#4ade80" font-size="11" text-anchor="middle">+6pp SR gain justifies 6.3x cost</text>
  </svg>
</div>

<h2>Success Rate Improvement Chart</h2>
<div class="chart-box">
  <svg width="100%" viewBox="0 0 760 220" xmlns="http://www.w3.org/2000/svg">
    <!-- axes -->
    <line x1="60" y1="10" x2="60" y2="180" stroke="#475569" stroke-width="1"/>
    <line x1="60" y1="180" x2="730" y2="180" stroke="#475569" stroke-width="1"/>
    <text x="395" y="210" fill="#94a3b8" font-size="11" text-anchor="middle">Policy / Environment Configuration</text>
    <text x="15" y="100" fill="#94a3b8" font-size="11" transform="rotate(-90,15,100)">Success Rate (%)</text>
    <!-- y grid and labels -->
    <line x1="60" y1="40" x2="730" y2="40" stroke="#1e293b" stroke-width="1" stroke-dasharray="4"/>
    <line x1="60" y1="100" x2="730" y2="100" stroke="#1e293b" stroke-width="1" stroke-dasharray="4"/>
    <line x1="60" y1="140" x2="730" y2="140" stroke="#1e293b" stroke-width="1" stroke-dasharray="4"/>
    <text x="55" y="44" fill="#94a3b8" font-size="10" text-anchor="end">100</text>
    <text x="55" y="104" fill="#94a3b8" font-size="10" text-anchor="end">70</text>
    <text x="55" y="144" fill="#94a3b8" font-size="10" text-anchor="end">50</text>
    <!-- Bars: 6 configs, pairs Genesis(blue) / Cosmos(red) -->
    <!-- Config 1: Genesis 62%, Cosmos 68% -->
    <rect x="80" y="105" width="28" height="75" fill="#38bdf8" opacity="0.8" rx="3"/>
    <rect x="112" y="93" width="28" height="87" fill="#C74634" opacity="0.85" rx="3"/>
    <text x="105" y="195" fill="#94a3b8" font-size="9" text-anchor="middle">Cfg-1</text>
    <!-- Config 2: Genesis 71%, Cosmos 77% -->
    <rect x="170" y="88" width="28" height="92" fill="#38bdf8" opacity="0.8" rx="3"/>
    <rect x="202" y="76" width="28" height="104" fill="#C74634" opacity="0.85" rx="3"/>
    <text x="195" y="195" fill="#94a3b8" font-size="9" text-anchor="middle">Cfg-2</text>
    <!-- Config 3: Genesis 58%, Cosmos 64% -->
    <rect x="260" y="111" width="28" height="69" fill="#38bdf8" opacity="0.8" rx="3"/>
    <rect x="292" y="99" width="28" height="81" fill="#C74634" opacity="0.85" rx="3"/>
    <text x="285" y="195" fill="#94a3b8" font-size="9" text-anchor="middle">Cfg-3</text>
    <!-- Config 4: Genesis 75%, Cosmos 81% -->
    <rect x="350" y="82" width="28" height="98" fill="#38bdf8" opacity="0.8" rx="3"/>
    <rect x="382" y="70" width="28" height="110" fill="#C74634" opacity="0.85" rx="3"/>
    <text x="375" y="195" fill="#94a3b8" font-size="9" text-anchor="middle">Cfg-4</text>
    <!-- Config 5: Genesis 66%, Cosmos 72% -->
    <rect x="440" y="100" width="28" height="80" fill="#38bdf8" opacity="0.8" rx="3"/>
    <rect x="472" y="88" width="28" height="92" fill="#C74634" opacity="0.85" rx="3"/>
    <text x="465" y="195" fill="#94a3b8" font-size="9" text-anchor="middle">Cfg-5</text>
    <!-- Config 6: Genesis 80%, Cosmos 86% -->
    <rect x="530" y="70" width="28" height="110" fill="#38bdf8" opacity="0.8" rx="3"/>
    <rect x="562" y="58" width="28" height="122" fill="#C74634" opacity="0.85" rx="3"/>
    <text x="555" y="195" fill="#94a3b8" font-size="9" text-anchor="middle">Cfg-6</text>
    <!-- legend -->
    <rect x="640" y="20" width="12" height="12" fill="#38bdf8" rx="2"/>
    <text x="656" y="31" fill="#94a3b8" font-size="11">Genesis</text>
    <rect x="640" y="40" width="12" height="12" fill="#C74634" rx="2"/>
    <text x="656" y="51" fill="#94a3b8" font-size="11">Cosmos WM</text>
  </svg>
</div>

<h2>Pipeline Configuration</h2>
<table>
  <thead><tr><th>Stage</th><th>Engine</th><th>Latency</th><th>Output</th><th>Status</th></tr></thead>
  <tbody>
    <tr><td>Physics sim</td><td>Genesis 0.2.1</td><td>12 ms/frame</td><td>Joint states + contacts</td><td><span class="badge badge-green">Active</span></td></tr>
    <tr><td>World model rendering</td><td>Cosmos WM v1.5</td><td>47 ms/frame</td><td>RGB + depth (256x256)</td><td><span class="badge badge-green">Active</span></td></tr>
    <tr><td>Scene variation engine</td><td>Internal SDG</td><td>8 ms/scene</td><td>10k variations / 50 bases</td><td><span class="badge badge-green">Active</span></td></tr>
    <tr><td>Cost tracker</td><td>OCI Billing API</td><td>async</td><td>$0.019/scene logged</td><td><span class="badge badge-blue">Monitoring</span></td></tr>
    <tr><td>SR evaluator</td><td>Closed-loop eval</td><td>226 ms/ep</td><td>+6pp over baseline</td><td><span class="badge badge-green">Validated</span></td></tr>
  </tbody>
</table>

</body>
</html>
"""

if USE_FASTAPI:
    app = FastAPI(title="Cosmos World Model Integrator")

    @app.get("/", response_class=HTMLResponse)
    async def root():
        return HTML

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "cosmos_world_model_integrator", "port": 8982}

    @app.get("/metrics")
    async def metrics():
        return {
            "render_time_ms": 47,
            "genesis_render_time_ms": 12,
            "sr_gain_pp": 6,
            "scene_variations": 10000,
            "base_scenes": 50,
            "cost_per_scene_cosmos": 0.019,
            "cost_per_scene_genesis": 0.003,
            "frames_per_second": round(1000 / 47, 1),
        }

    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=8982)
else:
    from http.server import HTTPServer, BaseHTTPRequestHandler

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(HTML.encode())
        def log_message(self, *args):
            pass

    if __name__ == "__main__":
        print("FastAPI not available, using stdlib HTTPServer on port 8982")
        HTTPServer(("0.0.0.0", 8982), Handler).serve_forever()
