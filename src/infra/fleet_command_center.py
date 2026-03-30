"""Fleet Command Center — port 8931
Real-time node status grid, job queue Gantt, 7-day fleet ops timeline.
"""
import math
import random

HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Fleet Command Center</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; padding: 24px; }
  h1 { color: #C74634; font-size: 2rem; margin-bottom: 8px; }
  h2 { color: #38bdf8; font-size: 1.2rem; margin: 24px 0 12px; }
  .card { background: #1e293b; border-radius: 10px; padding: 20px; margin-bottom: 20px; }
  .grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
  table { width: 100%; border-collapse: collapse; font-size: 0.9rem; }
  th { background: #0f172a; color: #38bdf8; padding: 8px 12px; text-align: left; }
  td { padding: 7px 12px; border-bottom: 1px solid #334155; }
  .badge { border-radius: 4px; padding: 2px 9px; font-size: 0.78rem; font-weight: 600; display: inline-block; }
  .b-train  { background: #C74634; color: #fff; }
  .b-eval   { background: #38bdf8; color: #0f172a; }
  .b-serve  { background: #22c55e; color: #0f172a; }
  .b-idle   { background: #334155; color: #94a3b8; }
  .b-reserv { background: #7c3aed; color: #fff; }
  .meta { color: #64748b; font-size: 0.82rem; margin-top: 6px; }
  .node-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 14px; margin-top: 8px; }
  .node-card { background: #0f172a; border-radius: 8px; padding: 14px 10px; text-align: center; border: 2px solid #334155; }
  .node-card.training  { border-color: #C74634; }
  .node-card.eval      { border-color: #38bdf8; }
  .node-card.serving   { border-color: #22c55e; }
  .node-card.idle      { border-color: #334155; }
  .node-card.reserved  { border-color: #7c3aed; }
  .node-name { font-weight: 700; font-size: 1rem; margin-bottom: 6px; }
  .node-status { font-size: 0.78rem; margin-top: 4px; }
  .node-util { font-size: 0.82rem; color: #94a3b8; margin-top: 4px; }
  svg text { font-family: 'Segoe UI', sans-serif; }
</style>
</head>
<body>
<h1>Fleet Command Center</h1>
<p class="meta">Real-time GPU node status &bull; Job queue &bull; 7-day fleet ops timeline &bull; Port 8931</p>

<h2>GPU Node Status Grid</h2>
<div class="card">
  <div class="node-grid">
    <div class="node-card training">
      <div class="node-name" style="color:#C74634">GPU4</div>
      <span class="badge b-train">TRAINING</span>
      <div class="node-util">Util: 94%</div>
      <div class="node-util">VRAM: 76GB / 80GB</div>
      <div class="node-util">Job: run11_finetune</div>
    </div>
    <div class="node-card eval">
      <div class="node-name" style="color:#38bdf8">GPU5</div>
      <span class="badge b-eval">EVAL</span>
      <div class="node-util">Util: 61%</div>
      <div class="node-util">VRAM: 42GB / 80GB</div>
      <div class="node-util">Job: closed_loop_eval</div>
    </div>
    <div class="node-card serving">
      <div class="node-name" style="color:#22c55e">GPU6</div>
      <span class="badge b-serve">SERVING</span>
      <div class="node-util">Util: 38%</div>
      <div class="node-util">VRAM: 28GB / 80GB</div>
      <div class="node-util">Job: inference_api</div>
    </div>
    <div class="node-card idle">
      <div class="node-name" style="color:#94a3b8">GPU7</div>
      <span class="badge b-idle">IDLE</span>
      <div class="node-util">Util: 0%</div>
      <div class="node-util">VRAM: 0GB / 80GB</div>
      <div class="node-util">Standby</div>
    </div>
    <div class="node-card reserved">
      <div class="node-name" style="color:#a78bfa">GPU8</div>
      <span class="badge b-reserv">RESERVED_N2</span>
      <div class="node-util">Util: 0%</div>
      <div class="node-util">VRAM: 0GB / 80GB</div>
      <div class="node-util">Node: N2 cluster</div>
    </div>
  </div>
</div>

<h2>Job Priority Queue — Gantt (12 Pending Jobs)</h2>
<div class="card">
  <svg width="100%" viewBox="0 0 760 320" xmlns="http://www.w3.org/2000/svg">
    <!-- axis -->
    <line x1="160" y1="20" x2="740" y2="20" stroke="#334155" stroke-width="1"/>
    <line x1="160" y1="20" x2="160" y2="300" stroke="#334155" stroke-width="1"/>
    <!-- time labels: T+0h .. T+24h -->
    <text x="160" y="15" fill="#64748b" font-size="10" text-anchor="middle">T+0h</text>
    <text x="305" y="15" fill="#64748b" font-size="10" text-anchor="middle">T+6h</text>
    <text x="450" y="15" fill="#64748b" font-size="10" text-anchor="middle">T+12h</text>
    <text x="595" y="15" fill="#64748b" font-size="10" text-anchor="middle">T+18h</text>
    <text x="740" y="15" fill="#64748b" font-size="10" text-anchor="middle">T+24h</text>
    <!-- grid lines -->
    <line x1="305" y1="20" x2="305" y2="300" stroke="#1e293b" stroke-width="1"/>
    <line x1="450" y1="20" x2="450" y2="300" stroke="#1e293b" stroke-width="1"/>
    <line x1="595" y1="20" x2="595" y2="300" stroke="#1e293b" stroke-width="1"/>

    <!-- jobs: label, start_h, dur_h, color, priority -->
    <!-- scale: 1h = (740-160)/24 = 24.17px -->
    <!-- J1: dagger_run7 P1 start=0 dur=6 -->
    <text x="5" y="38" fill="#e2e8f0" font-size="10">J1 dagger_run7</text>
    <rect x="160" y="26" width="145" height="18" rx="3" fill="#C74634" opacity="0.9"/>
    <text x="232" y="39" text-anchor="middle" fill="#fff" font-size="9">P1 · 6h</text>

    <!-- J2: hpo_sweep_v3 P1 start=0 dur=8 -->
    <text x="5" y="60" fill="#e2e8f0" font-size="10">J2 hpo_sweep_v3</text>
    <rect x="160" y="48" width="193" height="18" rx="3" fill="#C74634" opacity="0.75"/>
    <text x="256" y="61" text-anchor="middle" fill="#fff" font-size="9">P1 · 8h</text>

    <!-- J3: multi_task_eval P2 start=2 dur=3 -->
    <text x="5" y="82" fill="#e2e8f0" font-size="10">J3 multi_task_eval</text>
    <rect x="208" y="70" width="72" height="18" rx="3" fill="#38bdf8" opacity="0.85"/>
    <text x="244" y="83" text-anchor="middle" fill="#0f172a" font-size="9">P2 · 3h</text>

    <!-- J4: inference_bench P2 start=6 dur=2 -->
    <text x="5" y="104" fill="#e2e8f0" font-size="10">J4 inference_bench</text>
    <rect x="305" y="92" width="48" height="18" rx="3" fill="#38bdf8" opacity="0.7"/>
    <text x="329" y="105" text-anchor="middle" fill="#0f172a" font-size="9">P2 · 2h</text>

    <!-- J5: sdg_collect P2 start=1 dur=10 -->
    <text x="5" y="126" fill="#e2e8f0" font-size="10">J5 sdg_collect</text>
    <rect x="184" y="114" width="241" height="18" rx="3" fill="#7c3aed" opacity="0.7"/>
    <text x="304" y="127" text-anchor="middle" fill="#fff" font-size="9">P2 · 10h</text>

    <!-- J6: dataset_version P3 start=8 dur=1 -->
    <text x="5" y="148" fill="#e2e8f0" font-size="10">J6 dataset_version</text>
    <rect x="353" y="136" width="24" height="18" rx="3" fill="#22c55e" opacity="0.8"/>
    <text x="365" y="149" text-anchor="middle" fill="#0f172a" font-size="9">P3</text>

    <!-- J7: model_export P3 start=9 dur=2 -->
    <text x="5" y="170" fill="#e2e8f0" font-size="10">J7 model_export</text>
    <rect x="377" y="158" width="48" height="18" rx="3" fill="#22c55e" opacity="0.7"/>
    <text x="401" y="171" text-anchor="middle" fill="#0f172a" font-size="9">P3 · 2h</text>

    <!-- J8: safety_monitor P3 start=12 dur=12 -->
    <text x="5" y="192" fill="#e2e8f0" font-size="10">J8 safety_monitor</text>
    <rect x="450" y="180" width="290" height="18" rx="3" fill="#f59e0b" opacity="0.6"/>
    <text x="595" y="193" text-anchor="middle" fill="#0f172a" font-size="9">P3 · 12h (continuous)</text>

    <!-- J9: curriculum_sdg P3 start=11 dur=4 -->
    <text x="5" y="214" fill="#e2e8f0" font-size="10">J9 curriculum_sdg</text>
    <rect x="426" y="202" width="97" height="18" rx="3" fill="#7c3aed" opacity="0.6"/>
    <text x="474" y="215" text-anchor="middle" fill="#fff" font-size="9">P3 · 4h</text>

    <!-- J10: checkpoint_gc P4 start=16 dur=1 -->
    <text x="5" y="236" fill="#e2e8f0" font-size="10">J10 checkpoint_gc</text>
    <rect x="547" y="224" width="24" height="18" rx="3" fill="#334155" opacity="0.9"/>
    <text x="559" y="237" text-anchor="middle" fill="#94a3b8" font-size="9">P4</text>

    <!-- J11: drift_detect P4 start=18 dur=2 -->
    <text x="5" y="258" fill="#e2e8f0" font-size="10">J11 drift_detect</text>
    <rect x="595" y="246" width="48" height="18" rx="3" fill="#334155" opacity="0.9"/>
    <text x="619" y="259" text-anchor="middle" fill="#94a3b8" font-size="9">P4 · 2h</text>

    <!-- J12: telemetry_dump P4 start=22 dur=2 -->
    <text x="5" y="280" fill="#e2e8f0" font-size="10">J12 telemetry_dump</text>
    <rect x="691" y="268" width="48" height="18" rx="3" fill="#334155" opacity="0.8"/>
    <text x="715" y="281" text-anchor="middle" fill="#94a3b8" font-size="9">P4 · 2h</text>

    <!-- legend -->
    <rect x="160" y="303" width="12" height="10" rx="2" fill="#C74634"/>
    <text x="175" y="312" fill="#94a3b8" font-size="10">P1 Critical</text>
    <rect x="260" y="303" width="12" height="10" rx="2" fill="#38bdf8"/>
    <text x="275" y="312" fill="#94a3b8" font-size="10">P2 High</text>
    <rect x="340" y="303" width="12" height="10" rx="2" fill="#22c55e"/>
    <text x="355" y="312" fill="#94a3b8" font-size="10">P3 Med</text>
    <rect x="410" y="303" width="12" height="10" rx="2" fill="#334155"/>
    <text x="425" y="312" fill="#94a3b8" font-size="10">P4 Low</text>
  </svg>
</div>

<h2>7-Day Fleet Operations Timeline</h2>
<div class="card">
  <svg width="100%" viewBox="0 0 760 200" xmlns="http://www.w3.org/2000/svg">
    <!-- bars per day: stacked GPU-hours -->
    <!-- days: Mon Tue Wed Thu Fri Sat Sun -->
    <!-- categories: training, eval, serving, idle -->
    <defs>
      <linearGradient id="gtrain" x1="0" x2="0" y1="0" y2="1">
        <stop offset="0%" stop-color="#C74634"/>
        <stop offset="100%" stop-color="#9b2c1c"/>
      </linearGradient>
      <linearGradient id="geval" x1="0" x2="0" y1="0" y2="1">
        <stop offset="0%" stop-color="#38bdf8"/>
        <stop offset="100%" stop-color="#0ea5e9"/>
      </linearGradient>
    </defs>
    <!-- axis -->
    <line x1="50" y1="160" x2="750" y2="160" stroke="#334155" stroke-width="1"/>
    <line x1="50" y1="20" x2="50" y2="160" stroke="#334155" stroke-width="1"/>
    <!-- y labels (GPU-hours) -->
    <text x="45" y="162" fill="#64748b" font-size="10" text-anchor="end">0</text>
    <text x="45" y="122" fill="#64748b" font-size="10" text-anchor="end">40</text>
    <text x="45" y="82" fill="#64748b" font-size="10" text-anchor="end">80</text>
    <text x="45" y="42" fill="#64748b" font-size="10" text-anchor="end">120</text>
    <line x1="50" y1="122" x2="750" y2="122" stroke="#1e293b" stroke-width="1"/>
    <line x1="50" y1="82" x2="750" y2="82" stroke="#1e293b" stroke-width="1"/>
    <line x1="50" y1="42" x2="750" y2="42" stroke="#1e293b" stroke-width="1"/>

    <!-- Each day: x offset, train_h, eval_h, serve_h, idle_h (sum=120 = 5 GPUs * 24h) -->
    <!-- Mon: train=72 eval=18 serve=18 idle=12 -->
    <rect x="65"  y="40"  width="70" height="72" fill="url(#gtrain)"/>
    <rect x="65"  y="112" width="70" height="18" fill="url(#geval)"/>
    <rect x="65"  y="130" width="70" height="18" fill="#22c55e" opacity="0.8"/>
    <rect x="65"  y="148" width="70" height="12" fill="#334155"/>
    <text x="100" y="175" fill="#94a3b8" font-size="11" text-anchor="middle">Mon</text>

    <!-- Tue: train=60 eval=24 serve=18 idle=18 -->
    <rect x="165" y="60"  width="70" height="60" fill="url(#gtrain)"/>
    <rect x="165" y="120" width="70" height="24" fill="url(#geval)"/>
    <rect x="165" y="144" width="70" height="18" fill="#22c55e" opacity="0.8"/>
    <rect x="165" y="162" width="70" height="0"  fill="#334155"/>
    <text x="200" y="175" fill="#94a3b8" font-size="11" text-anchor="middle">Tue</text>

    <!-- Wed: train=80 eval=16 serve=12 idle=12 -->
    <rect x="265" y="27"  width="70" height="80" fill="url(#gtrain)"/>
    <rect x="265" y="107" width="70" height="16" fill="url(#geval)"/>
    <rect x="265" y="123" width="70" height="12" fill="#22c55e" opacity="0.8"/>
    <rect x="265" y="135" width="70" height="12" fill="#334155" opacity="0.7"/>
    <text x="300" y="175" fill="#94a3b8" font-size="11" text-anchor="middle">Wed</text>

    <!-- Thu: train=68 eval=20 serve=20 idle=12 -->
    <rect x="365" y="42"  width="70" height="68" fill="url(#gtrain)"/>
    <rect x="365" y="110" width="70" height="20" fill="url(#geval)"/>
    <rect x="365" y="130" width="70" height="20" fill="#22c55e" opacity="0.8"/>
    <rect x="365" y="150" width="70" height="12" fill="#334155"/>
    <text x="400" y="175" fill="#94a3b8" font-size="11" text-anchor="middle">Thu</text>

    <!-- Fri: train=56 eval=28 serve=24 idle=12 -->
    <rect x="465" y="64"  width="70" height="56" fill="url(#gtrain)"/>
    <rect x="465" y="120" width="70" height="28" fill="url(#geval)"/>
    <rect x="465" y="148" width="70" height="24" fill="#22c55e" opacity="0.8"/>
    <rect x="465" y="172" width="70" height="0"  fill="#334155"/>
    <text x="500" y="175" fill="#94a3b8" font-size="11" text-anchor="middle">Fri</text>

    <!-- Sat: train=40 eval=16 serve=24 idle=40 -->
    <rect x="565" y="80"  width="70" height="40" fill="url(#gtrain)"/>
    <rect x="565" y="120" width="70" height="16" fill="url(#geval)"/>
    <rect x="565" y="136" width="70" height="24" fill="#22c55e" opacity="0.8"/>
    <rect x="565" y="160" width="70" height="0"  fill="#334155"/>
    <text x="600" y="175" fill="#94a3b8" font-size="11" text-anchor="middle">Sat</text>

    <!-- Sun: train=24 eval=8 serve=24 idle=64 -->
    <rect x="665" y="136" width="70" height="24" fill="url(#gtrain)"/>
    <rect x="665" y="144" width="70" height="8"  fill="url(#geval)"/>
    <rect x="665" y="152" width="70" height="24" fill="#22c55e" opacity="0.8"/>
    <rect x="665" y="176" width="70" height="0"  fill="#334155"/>
    <text x="700" y="175" fill="#94a3b8" font-size="11" text-anchor="middle">Sun</text>

    <!-- legend -->
    <rect x="55" y="185" width="12" height="10" rx="2" fill="#C74634"/>
    <text x="70" y="194" fill="#94a3b8" font-size="10">Training</text>
    <rect x="135" y="185" width="12" height="10" rx="2" fill="#38bdf8"/>
    <text x="150" y="194" fill="#94a3b8" font-size="10">Eval</text>
    <rect x="195" y="185" width="12" height="10" rx="2" fill="#22c55e"/>
    <text x="210" y="194" fill="#94a3b8" font-size="10">Serving</text>
    <rect x="270" y="185" width="12" height="10" rx="2" fill="#334155"/>
    <text x="285" y="194" fill="#94a3b8" font-size="10">Idle</text>
    <text x="500" y="194" fill="#64748b" font-size="10">Y-axis: GPU-hours/day (5 nodes × 24h = 120 max)</text>
  </svg>
</div>

<h2>Node Summary</h2>
<div class="card">
  <table>
    <thead><tr><th>Node</th><th>Status</th><th>GPU Util</th><th>VRAM Used</th><th>Active Job</th><th>Uptime</th></tr></thead>
    <tbody>
      <tr><td>GPU4</td><td><span class="badge b-train">TRAINING</span></td><td>94%</td><td>76 / 80 GB</td><td>run11_finetune</td><td>18h 42m</td></tr>
      <tr><td>GPU5</td><td><span class="badge b-eval">EVAL</span></td><td>61%</td><td>42 / 80 GB</td><td>closed_loop_eval</td><td>3h 11m</td></tr>
      <tr><td>GPU6</td><td><span class="badge b-serve">SERVING</span></td><td>38%</td><td>28 / 80 GB</td><td>inference_api</td><td>6d 7h</td></tr>
      <tr><td>GPU7</td><td><span class="badge b-idle">IDLE</span></td><td>0%</td><td>0 / 80 GB</td><td>—</td><td>2h 05m</td></tr>
      <tr><td>GPU8</td><td><span class="badge b-reserv">RESERVED_N2</span></td><td>0%</td><td>0 / 80 GB</td><td>—</td><td>Reserved</td></tr>
    </tbody>
  </table>
</div>
</body>
</html>
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn

    app = FastAPI(title="Fleet Command Center")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return HTML

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "fleet_command_center", "port": 8931}

    @app.get("/api/nodes")
    def nodes():
        return {
            "nodes": [
                {"id": "GPU4", "status": "TRAINING",    "util_pct": 94, "vram_gb": 76, "vram_total_gb": 80, "job": "run11_finetune"},
                {"id": "GPU5", "status": "EVAL",        "util_pct": 61, "vram_gb": 42, "vram_total_gb": 80, "job": "closed_loop_eval"},
                {"id": "GPU6", "status": "SERVING",     "util_pct": 38, "vram_gb": 28, "vram_total_gb": 80, "job": "inference_api"},
                {"id": "GPU7", "status": "IDLE",        "util_pct":  0, "vram_gb":  0, "vram_total_gb": 80, "job": None},
                {"id": "GPU8", "status": "RESERVED_N2", "util_pct":  0, "vram_gb":  0, "vram_total_gb": 80, "job": None},
            ]
        }

    @app.get("/api/queue")
    def queue():
        jobs = [
            {"id": "J1",  "name": "dagger_run7",     "priority": 1, "start_h": 0,  "dur_h": 6},
            {"id": "J2",  "name": "hpo_sweep_v3",    "priority": 1, "start_h": 0,  "dur_h": 8},
            {"id": "J3",  "name": "multi_task_eval", "priority": 2, "start_h": 2,  "dur_h": 3},
            {"id": "J4",  "name": "inference_bench",  "priority": 2, "start_h": 6,  "dur_h": 2},
            {"id": "J5",  "name": "sdg_collect",      "priority": 2, "start_h": 1,  "dur_h": 10},
            {"id": "J6",  "name": "dataset_version",  "priority": 3, "start_h": 8,  "dur_h": 1},
            {"id": "J7",  "name": "model_export",     "priority": 3, "start_h": 9,  "dur_h": 2},
            {"id": "J8",  "name": "safety_monitor",   "priority": 3, "start_h": 12, "dur_h": 12},
            {"id": "J9",  "name": "curriculum_sdg",   "priority": 3, "start_h": 11, "dur_h": 4},
            {"id": "J10", "name": "checkpoint_gc",    "priority": 4, "start_h": 16, "dur_h": 1},
            {"id": "J11", "name": "drift_detect",     "priority": 4, "start_h": 18, "dur_h": 2},
            {"id": "J12", "name": "telemetry_dump",   "priority": 4, "start_h": 22, "dur_h": 2},
        ]
        return {"pending_jobs": len(jobs), "jobs": jobs}

    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=8931)

except ImportError:
    from http.server import HTTPServer, BaseHTTPRequestHandler

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(HTML.encode())
        def log_message(self, *a): pass

    if __name__ == "__main__":
        print("Serving on http://0.0.0.0:8931")
        HTTPServer(("0.0.0.0", 8931), Handler).serve_forever()
