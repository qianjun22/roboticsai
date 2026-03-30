# GR00T V3 Eval Suite — port 8956
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
<title>GR00T V3 Eval Suite</title>
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
  .green { background: #14532d; color: #4ade80; }
  .blue  { background: #0c2a4a; color: #38bdf8; }
  .red   { background: #3b0f0a; color: #f87171; }
  .stat-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; }
  .stat { background: #0f172a; border-radius: 8px; padding: 14px; text-align: center; }
  .stat .val { font-size: 1.8rem; font-weight: 700; color: #38bdf8; }
  .stat .lbl { font-size: 0.78rem; color: #64748b; margin-top: 4px; }
</style>
</head>
<body>
<h1>GR00T V3 Eval Suite</h1>
<p class="meta">Port 8956 &nbsp;|&nbsp; 25 tasks &times; 20 episodes &times; 3 envs &nbsp;|&nbsp; 1500 total episodes &nbsp;|&nbsp; ~4 hr wall time &nbsp;|&nbsp; 3-node parallel</p>

<div class="card">
  <h2>Protocol Summary</h2>
  <div class="stat-grid">
    <div class="stat"><div class="val">25</div><div class="lbl">Tasks</div></div>
    <div class="stat"><div class="val">20</div><div class="lbl">Episodes / Task / Env</div></div>
    <div class="stat"><div class="val">3</div><div class="lbl">Environments</div></div>
    <div class="stat"><div class="val">1500</div><div class="lbl">Total Episodes</div></div>
  </div>
</div>

<div class="card">
  <h2>Eval Protocol Breakdown</h2>
  <svg width="100%" height="260" viewBox="0 0 800 260">
    <!-- bars: episodes per task category -->
    <!-- 5 categories: Pick&Place, Pour, Fold, Assemble, Navigate -->
    <!-- episodes: 300 300 300 300 300 (equal, 5 task groups x5 tasks x20 eps x3 env) -->
    <defs>
      <linearGradient id="gbar" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="#38bdf8"/>
        <stop offset="100%" stop-color="#0369a1"/>
      </linearGradient>
    </defs>
    <!-- axes -->
    <line x1="80" y1="20" x2="80" y2="210" stroke="#334155" stroke-width="1"/>
    <line x1="80" y1="210" x2="780" y2="210" stroke="#334155" stroke-width="1"/>
    <!-- y labels -->
    <text x="70" y="214" fill="#64748b" font-size="11" text-anchor="end">0</text>
    <text x="70" y="164" fill="#64748b" font-size="11" text-anchor="end">150</text>
    <text x="70" y="114" fill="#64748b" font-size="11" text-anchor="end">300</text>
    <line x1="80" y1="160" x2="780" y2="160" stroke="#1e293b" stroke-width="1" stroke-dasharray="4,4"/>
    <line x1="80" y1="110" x2="780" y2="110" stroke="#1e293b" stroke-width="1" stroke-dasharray="4,4"/>
    <!-- bars -->
    <rect x="100" y="110" width="100" height="100" fill="url(#gbar)" rx="4"/>
    <rect x="240" y="110" width="100" height="100" fill="url(#gbar)" rx="4"/>
    <rect x="380" y="110" width="100" height="100" fill="url(#gbar)" rx="4"/>
    <rect x="520" y="110" width="100" height="100" fill="url(#gbar)" rx="4"/>
    <rect x="660" y="110" width="100" height="100" fill="url(#gbar)" rx="4"/>
    <!-- labels -->
    <text x="150" y="230" fill="#94a3b8" font-size="11" text-anchor="middle">Pick &amp; Place</text>
    <text x="290" y="230" fill="#94a3b8" font-size="11" text-anchor="middle">Pour</text>
    <text x="430" y="230" fill="#94a3b8" font-size="11" text-anchor="middle">Fold</text>
    <text x="570" y="230" fill="#94a3b8" font-size="11" text-anchor="middle">Assemble</text>
    <text x="710" y="230" fill="#94a3b8" font-size="11" text-anchor="middle">Navigate</text>
    <!-- value labels -->
    <text x="150" y="105" fill="#38bdf8" font-size="12" text-anchor="middle" font-weight="600">300</text>
    <text x="290" y="105" fill="#38bdf8" font-size="12" text-anchor="middle" font-weight="600">300</text>
    <text x="430" y="105" fill="#38bdf8" font-size="12" text-anchor="middle" font-weight="600">300</text>
    <text x="570" y="105" fill="#38bdf8" font-size="12" text-anchor="middle" font-weight="600">300</text>
    <text x="710" y="105" fill="#38bdf8" font-size="12" text-anchor="middle" font-weight="600">300</text>
    <text x="430" y="18" fill="#e2e8f0" font-size="13" text-anchor="middle" font-weight="600">Episodes per Task Category (5 tasks × 20 eps × 3 envs)</text>
  </svg>
</div>

<div class="card">
  <h2>Projected V2 vs V3 Success Rate Comparison</h2>
  <svg width="100%" height="320" viewBox="0 0 820 320">
    <defs>
      <linearGradient id="v2g" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="#475569"/>
        <stop offset="100%" stop-color="#1e293b"/>
      </linearGradient>
      <linearGradient id="v3g" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="#C74634"/>
        <stop offset="100%" stop-color="#7f1d1d"/>
      </linearGradient>
    </defs>
    <!-- axes -->
    <line x1="90" y1="20" x2="90" y2="260" stroke="#334155" stroke-width="1"/>
    <line x1="90" y1="260" x2="800" y2="260" stroke="#334155" stroke-width="1"/>
    <!-- y grid -->
    <text x="80" y="264" fill="#64748b" font-size="10" text-anchor="end">0%</text>
    <text x="80" y="214" fill="#64748b" font-size="10" text-anchor="end">25%</text>
    <text x="80" y="164" fill="#64748b" font-size="10" text-anchor="end">50%</text>
    <text x="80" y="114" fill="#64748b" font-size="10" text-anchor="end">75%</text>
    <text x="80" y="64"  fill="#64748b" font-size="10" text-anchor="end">100%</text>
    <line x1="90" y1="260" x2="800" y2="260" stroke="#1e293b" stroke-dasharray="3,3"/>
    <line x1="90" y1="210" x2="800" y2="210" stroke="#1e293b" stroke-dasharray="3,3"/>
    <line x1="90" y1="160" x2="800" y2="160" stroke="#1e293b" stroke-dasharray="3,3"/>
    <line x1="90" y1="110" x2="800" y2="110" stroke="#1e293b" stroke-dasharray="3,3"/>
    <line x1="90" y1="60"  x2="800" y2="60"  stroke="#1e293b" stroke-dasharray="3,3"/>
    <!-- scale: 200px = 100% => 1% = 2px; bars start y=260 -->
    <!-- Pick&Place: v2=72%, v3=77% -->
    <rect x="110" y="116" width="45" height="144" fill="url(#v2g)" rx="3"/>
    <rect x="160" y="106" width="45" height="154" fill="url(#v3g)" rx="3"/>
    <!-- Pour: v2=60%, v3=69% -->
    <rect x="240" y="140" width="45" height="120" fill="url(#v2g)" rx="3"/>
    <rect x="290" y="122" width="45" height="138" fill="url(#v3g)" rx="3"/>
    <!-- Fold: v2=55%, v3=62% -->
    <rect x="370" y="150" width="45" height="110" fill="url(#v2g)" rx="3"/>
    <rect x="420" y="136" width="45" height="124" fill="url(#v3g)" rx="3"/>
    <!-- Assemble: v2=48%, v3=53% -->
    <rect x="500" y="164" width="45" height="96"  fill="url(#v2g)" rx="3"/>
    <rect x="550" y="154" width="45" height="106" fill="url(#v3g)" rx="3"/>
    <!-- Navigate: v2=80%, v3=85% -->
    <rect x="630" y="100" width="45" height="160" fill="url(#v2g)" rx="3"/>
    <rect x="680" y="90"  width="45" height="170" fill="url(#v3g)" rx="3"/>
    <!-- x labels -->
    <text x="147" y="278" fill="#94a3b8" font-size="10" text-anchor="middle">Pick&amp;Place</text>
    <text x="277" y="278" fill="#94a3b8" font-size="10" text-anchor="middle">Pour</text>
    <text x="407" y="278" fill="#94a3b8" font-size="10" text-anchor="middle">Fold</text>
    <text x="537" y="278" fill="#94a3b8" font-size="10" text-anchor="middle">Assemble</text>
    <text x="667" y="278" fill="#94a3b8" font-size="10" text-anchor="middle">Navigate</text>
    <!-- value labels -->
    <text x="132" y="112" fill="#94a3b8" font-size="10" text-anchor="middle">72%</text>
    <text x="182" y="102" fill="#f87171" font-size="10" text-anchor="middle">77%</text>
    <text x="262" y="136" fill="#94a3b8" font-size="10" text-anchor="middle">60%</text>
    <text x="312" y="118" fill="#f87171" font-size="10" text-anchor="middle">69%</text>
    <text x="392" y="146" fill="#94a3b8" font-size="10" text-anchor="middle">55%</text>
    <text x="442" y="132" fill="#f87171" font-size="10" text-anchor="middle">62%</text>
    <text x="522" y="160" fill="#94a3b8" font-size="10" text-anchor="middle">48%</text>
    <text x="572" y="150" fill="#f87171" font-size="10" text-anchor="middle">53%</text>
    <text x="652" y="96"  fill="#94a3b8" font-size="10" text-anchor="middle">80%</text>
    <text x="702" y="86"  fill="#f87171" font-size="10" text-anchor="middle">85%</text>
    <!-- legend -->
    <rect x="300" y="295" width="14" height="14" fill="url(#v2g)" rx="2"/>
    <text x="318" y="307" fill="#94a3b8" font-size="11">V2 (baseline)</text>
    <rect x="430" y="295" width="14" height="14" fill="url(#v3g)" rx="2"/>
    <text x="448" y="307" fill="#f87171" font-size="11">V3 (projected)</text>
    <text x="430" y="18" fill="#e2e8f0" font-size="13" text-anchor="middle" font-weight="600">V2 vs V3 Projected Success Rate (%)</text>
  </svg>
  <p style="color:#64748b;font-size:0.82rem;margin-top:8px;">Avg: +5pp &nbsp;|&nbsp; Pour: +9pp &nbsp;|&nbsp; Fold: +7pp &nbsp;|&nbsp; 3-node parallel eval across Isaac Sim / ManiSkill2 / RLBench</p>
</div>

<div class="card">
  <h2>Task Registry</h2>
  <table>
    <tr><th>Task</th><th>Category</th><th>Episodes</th><th>Env</th><th>V2 SR</th><th>V3 Proj</th><th>Delta</th></tr>
    <tr><td>PickCube</td><td>Pick &amp; Place</td><td>60</td><td>ManiSkill2</td><td>74%</td><td>79%</td><td><span class="badge green">+5pp</span></td></tr>
    <tr><td>StackBlocks</td><td>Pick &amp; Place</td><td>60</td><td>Isaac Sim</td><td>70%</td><td>75%</td><td><span class="badge green">+5pp</span></td></tr>
    <tr><td>PourWater</td><td>Pour</td><td>60</td><td>RLBench</td><td>58%</td><td>67%</td><td><span class="badge green">+9pp</span></td></tr>
    <tr><td>FoldCloth</td><td>Fold</td><td>60</td><td>Isaac Sim</td><td>53%</td><td>60%</td><td><span class="badge green">+7pp</span></td></tr>
    <tr><td>AssemblePeg</td><td>Assemble</td><td>60</td><td>ManiSkill2</td><td>46%</td><td>51%</td><td><span class="badge green">+5pp</span></td></tr>
    <tr><td>NavigateMaze</td><td>Navigate</td><td>60</td><td>Isaac Sim</td><td>81%</td><td>86%</td><td><span class="badge green">+5pp</span></td></tr>
  </table>
</div>

<p style="color:#334155;font-size:0.75rem;margin-top:24px;">GR00T V3 Eval Suite &mdash; OCI Robot Cloud &mdash; Port 8956</p>
</body>
</html>
"""

if USE_FASTAPI:
    app = FastAPI(title="GR00T V3 Eval Suite")

    @app.get("/", response_class=HTMLResponse)
    async def root():
        return HTML

    @app.get("/health")
    async def health():
        tasks = 25
        episodes_per_task_env = 20
        envs = 3
        total = tasks * episodes_per_task_env * envs
        wall_time_hr = round(total / 375, 2)  # ~375 eps/hr across 3 nodes
        return {
            "status": "ok",
            "service": "groot_v3_eval_suite",
            "port": 8956,
            "tasks": tasks,
            "episodes_per_task_per_env": episodes_per_task_env,
            "envs": envs,
            "total_episodes": total,
            "estimated_wall_time_hr": wall_time_hr,
            "nodes": 3,
            "v2_avg_sr": 0.63,
            "v3_proj_avg_sr": 0.68,
            "avg_delta_pp": 5,
        }

    @app.get("/tasks")
    async def list_tasks():
        tasks = [
            {"name": "PickCube",    "category": "Pick & Place", "v2_sr": 0.74, "v3_proj": 0.79, "env": "ManiSkill2"},
            {"name": "StackBlocks", "category": "Pick & Place", "v2_sr": 0.70, "v3_proj": 0.75, "env": "Isaac Sim"},
            {"name": "PourWater",   "category": "Pour",         "v2_sr": 0.58, "v3_proj": 0.67, "env": "RLBench"},
            {"name": "FoldCloth",   "category": "Fold",         "v2_sr": 0.53, "v3_proj": 0.60, "env": "Isaac Sim"},
            {"name": "AssemblePeg", "category": "Assemble",     "v2_sr": 0.46, "v3_proj": 0.51, "env": "ManiSkill2"},
            {"name": "NavigateMaze","category": "Navigate",     "v2_sr": 0.81, "v3_proj": 0.86, "env": "Isaac Sim"},
        ]
        return {"tasks": tasks, "count": len(tasks)}

else:
    import json
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/health":
                body = json.dumps({"status": "ok", "port": 8956}).encode()
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
        uvicorn.run(app, host="0.0.0.0", port=8956)
    else:
        print("Serving on http://0.0.0.0:8956 (fallback HTTPServer)")
        HTTPServer(("0.0.0.0", 8956), Handler).serve_forever()
