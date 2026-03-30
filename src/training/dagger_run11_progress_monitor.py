"""DAgger Run11 Progress Monitor — port 8954"""
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
<title>DAgger Run11 Progress Monitor</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; padding: 24px; }
  h1 { color: #C74634; font-size: 2rem; margin-bottom: 8px; }
  h2 { color: #38bdf8; font-size: 1.2rem; margin: 24px 0 12px; }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 24px; }
  .card { background: #1e293b; border-radius: 10px; padding: 18px; }
  .card .label { color: #94a3b8; font-size: 0.85rem; margin-bottom: 6px; }
  .card .value { font-size: 1.6rem; font-weight: 700; color: #f1f5f9; }
  .card .sub { font-size: 0.8rem; color: #64748b; margin-top: 4px; }
  .chart-box { background: #1e293b; border-radius: 10px; padding: 18px; margin-bottom: 24px; }
  .milestones { display: flex; flex-direction: column; gap: 10px; }
  .milestone { background: #1e293b; border-radius: 8px; padding: 12px 18px; display: flex; justify-content: space-between; align-items: center; }
  .milestone .ms-label { color: #e2e8f0; }
  .milestone .ms-date { color: #38bdf8; font-weight: 600; }
  .milestone.done .ms-label { color: #4ade80; }
  .badge { display: inline-block; padding: 2px 10px; border-radius: 12px; font-size: 0.78rem; font-weight: 600; }
  .badge.running { background: #1d4ed8; color: #bfdbfe; }
  .badge.done { background: #166534; color: #bbf7d0; }
  .badge.pending { background: #374151; color: #9ca3af; }
  footer { margin-top: 32px; color: #475569; font-size: 0.8rem; text-align: center; }
</style>
</head>
<body>
<h1>DAgger Run11 Progress Monitor</h1>
<p style="color:#64748b;margin-bottom:20px;">Live dashboard — step counter / loss / success rate / GPU utilization / ETA</p>

<div class="grid">
  <div class="card">
    <div class="label">Current Step</div>
    <div class="value" id="step">1,247</div>
    <div class="sub">Target: 5,000</div>
  </div>
  <div class="card">
    <div class="label">Training Loss</div>
    <div class="value" id="loss" style="color:#38bdf8">0.0821</div>
    <div class="sub">Run10 at this step: 0.1134</div>
  </div>
  <div class="card">
    <div class="label">Success Rate</div>
    <div class="value" id="sr" style="color:#4ade80">28.5%</div>
    <div class="sub">Projected at 5k steps: 67%</div>
  </div>
  <div class="card">
    <div class="label">GPU Utilization</div>
    <div class="value" id="gpu">91%</div>
    <div class="sub">A100 80GB · 4× DDP</div>
  </div>
  <div class="card">
    <div class="label">ETA to 5000 Steps</div>
    <div class="value" id="eta">Apr 28</div>
    <div class="sub">~374 hrs remaining</div>
  </div>
  <div class="card">
    <div class="label">Throughput</div>
    <div class="value">3.07 it/s</div>
    <div class="sub">Multi-GPU DDP</div>
  </div>
</div>

<h2>Loss Curve Comparison: Run11 vs Run10</h2>
<div class="chart-box">
  <svg id="loss-chart" viewBox="0 0 700 220" width="100%" style="display:block;">
    <!-- axes -->
    <line x1="60" y1="10" x2="60" y2="190" stroke="#334155" stroke-width="1.5"/>
    <line x1="60" y1="190" x2="680" y2="190" stroke="#334155" stroke-width="1.5"/>
    <!-- y labels -->
    <text x="50" y="14" fill="#64748b" font-size="11" text-anchor="end">0.30</text>
    <text x="50" y="57" fill="#64748b" font-size="11" text-anchor="end">0.22</text>
    <text x="50" y="100" fill="#64748b" font-size="11" text-anchor="end">0.15</text>
    <text x="50" y="143" fill="#64748b" font-size="11" text-anchor="end">0.07</text>
    <text x="50" y="190" fill="#64748b" font-size="11" text-anchor="end">0.00</text>
    <!-- x labels -->
    <text x="60" y="205" fill="#64748b" font-size="11" text-anchor="middle">0</text>
    <text x="185" y="205" fill="#64748b" font-size="11" text-anchor="middle">1000</text>
    <text x="310" y="205" fill="#64748b" font-size="11" text-anchor="middle">2000</text>
    <text x="435" y="205" fill="#64748b" font-size="11" text-anchor="middle">3000</text>
    <text x="560" y="205" fill="#64748b" font-size="11" text-anchor="middle">4000</text>
    <text x="680" y="205" fill="#64748b" font-size="11" text-anchor="middle">5000</text>
    <!-- Run10 loss (higher) -->
    <polyline points="60,20 185,62 310,90 435,112 560,130 680,143"
      fill="none" stroke="#f97316" stroke-width="2" stroke-dasharray="6,3"/>
    <!-- Run11 loss (lower/better) solid up to step 1247 then projected dashed -->
    <polyline points="60,20 130,45 185,55 250,63"
      fill="none" stroke="#38bdf8" stroke-width="2.5"/>
    <polyline points="250,63 310,73 435,90 560,103 680,112"
      fill="none" stroke="#38bdf8" stroke-width="2" stroke-dasharray="5,4" opacity="0.6"/>
    <!-- legend -->
    <line x1="490" y1="30" x2="520" y2="30" stroke="#f97316" stroke-width="2" stroke-dasharray="6,3"/>
    <text x="525" y="34" fill="#f97316" font-size="12">Run10</text>
    <line x1="490" y1="50" x2="520" y2="50" stroke="#38bdf8" stroke-width="2.5"/>
    <text x="525" y="54" fill="#38bdf8" font-size="12">Run11</text>
    <!-- current step marker -->
    <line x1="250" y1="10" x2="250" y2="190" stroke="#4ade80" stroke-width="1" stroke-dasharray="3,3"/>
    <text x="255" y="25" fill="#4ade80" font-size="10">step 1247</text>
    <text x="30" y="115" fill="#94a3b8" font-size="11" transform="rotate(-90,30,115)">Loss</text>
    <text x="370" y="218" fill="#94a3b8" font-size="11" text-anchor="middle">Training Steps</text>
  </svg>
</div>

<h2>Projected Success Rate Trajectory (Polynomial Fit)</h2>
<div class="chart-box">
  <svg id="sr-chart" viewBox="0 0 700 200" width="100%" style="display:block;">
    <line x1="60" y1="10" x2="60" y2="175" stroke="#334155" stroke-width="1.5"/>
    <line x1="60" y1="175" x2="680" y2="175" stroke="#334155" stroke-width="1.5"/>
    <text x="50" y="14" fill="#64748b" font-size="11" text-anchor="end">80%</text>
    <text x="50" y="55" fill="#64748b" font-size="11" text-anchor="end">60%</text>
    <text x="50" y="96" fill="#64748b" font-size="11" text-anchor="end">40%</text>
    <text x="50" y="137" fill="#64748b" font-size="11" text-anchor="end">20%</text>
    <text x="50" y="175" fill="#64748b" font-size="11" text-anchor="end">0%</text>
    <text x="60" y="190" fill="#64748b" font-size="11" text-anchor="middle">0</text>
    <text x="185" y="190" fill="#64748b" font-size="11" text-anchor="middle">1000</text>
    <text x="310" y="190" fill="#64748b" font-size="11" text-anchor="middle">2000</text>
    <text x="435" y="190" fill="#64748b" font-size="11" text-anchor="middle">3000</text>
    <text x="560" y="190" fill="#64748b" font-size="11" text-anchor="middle">4000</text>
    <text x="680" y="190" fill="#64748b" font-size="11" text-anchor="middle">5000</text>
    <!-- polynomial SR trajectory: f(x)=80*(1-exp(-x/2200)) approx -->
    <!-- sampled: 0->5%, 1000->28.5%, 2000->47%, 3000->58%, 4000->65%, 5000->68% -->
    <!-- actual solid up to 1247 -->
    <polyline points="60,165 185,124 255,120"
      fill="none" stroke="#4ade80" stroke-width="2.5"/>
    <!-- projected dashed -->
    <polyline points="255,120 310,96 435,77 560,65 680,59"
      fill="none" stroke="#4ade80" stroke-width="2" stroke-dasharray="5,4" opacity="0.6"/>
    <line x1="255" y1="10" x2="255" y2="175" stroke="#4ade80" stroke-width="1" stroke-dasharray="3,3"/>
    <text x="260" y="25" fill="#4ade80" font-size="10">now</text>
    <text x="30" y="95" fill="#94a3b8" font-size="11" transform="rotate(-90,30,95)">Success Rate</text>
    <text x="370" y="200" fill="#94a3b8" font-size="11" text-anchor="middle">Training Steps</text>
  </svg>
</div>

<h2>Milestones</h2>
<div class="milestones">
  <div class="milestone">
    <span class="ms-label">Step 1000 — Early convergence checkpoint</span>
    <span class="ms-date">Apr 18 &nbsp;<span class="badge done">DONE</span></span>
  </div>
  <div class="milestone">
    <span class="ms-label">Step 2500 — Mid-run evaluation</span>
    <span class="ms-date">Apr 28 &nbsp;<span class="badge running">IN PROGRESS</span></span>
  </div>
  <div class="milestone">
    <span class="ms-label">Step 5000 — Final checkpoint &amp; full eval</span>
    <span class="ms-date">May 8 &nbsp;<span class="badge pending">PENDING</span></span>
  </div>
</div>

<footer>OCI Robot Cloud · DAgger Run11 Progress Monitor · port 8954</footer>

<script>
// Simulate live counter updates
let step = 1247;
function tick() {
  step += Math.floor(Math.random() * 3);
  document.getElementById('step').textContent = step.toLocaleString();
  const loss = Math.max(0.055, 0.0821 * Math.exp(-0.00003 * (step - 1247)));
  document.getElementById('loss').textContent = loss.toFixed(4);
  const sr = 80 * (1 - Math.exp(-step / 2200));
  document.getElementById('sr').textContent = sr.toFixed(1) + '%';
  const gpu = 88 + Math.floor(Math.random() * 6);
  document.getElementById('gpu').textContent = gpu + '%';
  setTimeout(tick, 2000);
}
tick();
</script>
</body>
</html>
"""

if USE_FASTAPI:
    app = FastAPI(title="DAgger Run11 Progress Monitor")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return HTML

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "dagger_run11_progress_monitor", "port": 8954}

    @app.get("/metrics")
    def metrics():
        step = random.randint(1240, 1260)
        loss = round(0.0821 - random.uniform(0, 0.002), 4)
        sr = round(80 * (1 - math.exp(-step / 2200)), 2)
        return {
            "step": step,
            "loss": loss,
            "success_rate_pct": sr,
            "gpu_util_pct": random.randint(88, 94),
            "run10_loss_at_step": round(0.1134 - random.uniform(0, 0.001), 4),
            "projected_sr_at_5k": 67.0,
            "eta_step_5000": "2026-05-08",
        }

else:
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(HTML.encode())
        def log_message(self, *a):
            pass

if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8954)
    else:
        print("Fallback: serving on port 8954")
        HTTPServer(("0.0.0.0", 8954), Handler).serve_forever()
