# GPU Memory Profiler V2 — port 8950
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
<title>GPU Memory Profiler V2</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; padding: 2rem; }
  h1 { color: #C74634; font-size: 2rem; margin-bottom: 0.5rem; }
  h2 { color: #38bdf8; font-size: 1.25rem; margin: 1.5rem 0 0.75rem; }
  h3 { color: #38bdf8; font-size: 1rem; margin-bottom: 0.5rem; }
  .subtitle { color: #94a3b8; margin-bottom: 2rem; }
  .cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-bottom: 1.5rem; }
  .card { background: #1e293b; border-radius: 10px; padding: 1.25rem; border-left: 4px solid #C74634; }
  .card.blue { border-left-color: #38bdf8; }
  .card.green { border-left-color: #4ade80; }
  .card-val { font-size: 1.8rem; font-weight: 700; color: #f8fafc; }
  .card-label { color: #94a3b8; font-size: 0.85rem; margin-top: 0.3rem; }
  table { width: 100%; border-collapse: collapse; }
  th { background: #1e293b; color: #38bdf8; padding: 0.75rem 1rem; text-align: left; }
  td { padding: 0.7rem 1rem; border-bottom: 1px solid #1e293b; }
  tr:hover td { background: #1e293b55; }
  .tag { display: inline-block; padding: 0.2rem 0.6rem; border-radius: 4px; font-size: 0.78rem; font-weight: 600; }
  .safe { background: #166534; color: #4ade80; }
  .warn { background: #78350f; color: #fbbf24; }
  .chart-wrap { background: #1e293b; border-radius: 10px; padding: 1.25rem; margin-bottom: 1.5rem; }
  svg text { font-family: 'Segoe UI', sans-serif; }
  .footer { color: #475569; font-size: 0.8rem; margin-top: 2rem; text-align: center; }
</style>
</head>
<body>
<h1>GPU Memory Profiler V2</h1>
<p class="subtitle">Peak memory breakdown, gradient checkpointing analysis, and multi-GPU pipeline planning — Port 8950</p>

<div class="cards">
  <div class="card">
    <div class="card-val">10.6 GB</div>
    <div class="card-label">Total Peak (1 GPU)</div>
  </div>
  <div class="card blue">
    <div class="card-val">80 GB</div>
    <div class="card-label">A100 VRAM Capacity</div>
  </div>
  <div class="card green">
    <div class="card-val">6.4 GB</div>
    <div class="card-label">Peak w/ Grad Checkpointing</div>
  </div>
  <div class="card">
    <div class="card-val">2-GPU</div>
    <div class="card-label">N2 Pipeline Parallel Min.</div>
  </div>
</div>

<h2>Memory Breakdown</h2>
<div class="chart-wrap">
  <svg width="100%" height="220" viewBox="0 0 700 220">
    <!-- Background grid -->
    <line x1="60" y1="20" x2="60" y2="180" stroke="#334155" stroke-width="1"/>
    <line x1="60" y1="180" x2="680" y2="180" stroke="#334155" stroke-width="1"/>
    <!-- Y axis labels -->
    <text x="55" y="25" text-anchor="end" fill="#64748b" font-size="11">12 GB</text>
    <text x="55" y="70" text-anchor="end" fill="#64748b" font-size="11">9 GB</text>
    <text x="55" y="115" text-anchor="end" fill="#64748b" font-size="11">6 GB</text>
    <text x="55" y="160" text-anchor="end" fill="#64748b" font-size="11">3 GB</text>
    <text x="55" y="183" text-anchor="end" fill="#64748b" font-size="11">0</text>
    <!-- Grid lines -->
    <line x1="60" y1="25" x2="680" y2="25" stroke="#1e293b" stroke-width="1"/>
    <line x1="60" y1="70" x2="680" y2="70" stroke="#1e293b" stroke-width="1"/>
    <line x1="60" y1="115" x2="680" y2="115" stroke="#1e293b" stroke-width="1"/>
    <line x1="60" y1="160" x2="680" y2="160" stroke="#1e293b" stroke-width="1"/>
    <!-- Bars: scale 0-12GB = 0-160px -->
    <!-- Model weights 6.7GB => 89px -->
    <rect x="100" y="91" width="120" height="89" fill="#C74634" rx="4"/>
    <text x="160" y="86" text-anchor="middle" fill="#f8fafc" font-size="12" font-weight="600">6.7 GB</text>
    <text x="160" y="200" text-anchor="middle" fill="#94a3b8" font-size="11">Model Weights</text>
    <!-- Activations 2.1GB => 28px -->
    <rect x="280" y="152" width="120" height="28" fill="#38bdf8" rx="4"/>
    <text x="340" y="148" text-anchor="middle" fill="#f8fafc" font-size="12" font-weight="600">2.1 GB</text>
    <text x="340" y="200" text-anchor="middle" fill="#94a3b8" font-size="11">Activations</text>
    <!-- Optimizer 1.8GB => 24px -->
    <rect x="460" y="156" width="120" height="24" fill="#a78bfa" rx="4"/>
    <text x="520" y="152" text-anchor="middle" fill="#f8fafc" font-size="12" font-weight="600">1.8 GB</text>
    <text x="520" y="200" text-anchor="middle" fill="#94a3b8" font-size="11">Optimizer State</text>
    <!-- Total line -->
    <line x1="65" y1="38" x2="675" y2="38" stroke="#fbbf24" stroke-width="1.5" stroke-dasharray="6,3"/>
    <text x="670" y="35" text-anchor="end" fill="#fbbf24" font-size="11">Total 10.6 GB</text>
  </svg>
</div>

<h2>Optimization Comparison</h2>
<div class="chart-wrap">
  <table>
    <thead>
      <tr>
        <th>Configuration</th>
        <th>Peak Memory</th>
        <th>Reduction</th>
        <th>A100 80GB Status</th>
        <th>N2 (40GB/GPU)</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td>Baseline (BF16, full grads)</td>
        <td>10.6 GB</td>
        <td>—</td>
        <td><span class="tag safe">SAFE (13.3%)</span></td>
        <td><span class="tag safe">1 GPU</span></td>
      </tr>
      <tr>
        <td>Gradient Checkpointing</td>
        <td>6.4 GB</td>
        <td>-40%</td>
        <td><span class="tag safe">SAFE (8.0%)</span></td>
        <td><span class="tag safe">1 GPU</span></td>
      </tr>
      <tr>
        <td>FP8 Quantized Inference</td>
        <td>5.2 GB</td>
        <td>-51%</td>
        <td><span class="tag safe">SAFE (6.5%)</span></td>
        <td><span class="tag safe">1 GPU</span></td>
      </tr>
      <tr>
        <td>Full Fine-Tune (AdamW, BF16)</td>
        <td>42.4 GB</td>
        <td>+300%</td>
        <td><span class="tag safe">SAFE (53%)</span></td>
        <td><span class="tag warn">2-GPU PP</span></td>
      </tr>
      <tr>
        <td>Full Fine-Tune + Grad Ckpt</td>
        <td>26.8 GB</td>
        <td>+153%</td>
        <td><span class="tag safe">SAFE (33.5%)</span></td>
        <td><span class="tag warn">2-GPU PP</span></td>
      </tr>
    </tbody>
  </table>
</div>

<h2>Memory Timeline (Training Step)</h2>
<div class="chart-wrap">
  <svg width="100%" height="200" viewBox="0 0 700 200">
    <defs>
      <linearGradient id="memGrad" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="#38bdf8" stop-opacity="0.4"/>
        <stop offset="100%" stop-color="#38bdf8" stop-opacity="0"/>
      </linearGradient>
      <linearGradient id="ckptGrad" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="#4ade80" stop-opacity="0.4"/>
        <stop offset="100%" stop-color="#4ade80" stop-opacity="0"/>
      </linearGradient>
    </defs>
    <!-- Axes -->
    <line x1="60" y1="10" x2="60" y2="160" stroke="#334155" stroke-width="1"/>
    <line x1="60" y1="160" x2="680" y2="160" stroke="#334155" stroke-width="1"/>
    <text x="55" y="15" text-anchor="end" fill="#64748b" font-size="10">45 GB</text>
    <text x="55" y="55" text-anchor="end" fill="#64748b" font-size="10">30 GB</text>
    <text x="55" y="100" text-anchor="end" fill="#64748b" font-size="10">15 GB</text>
    <text x="55" y="163" text-anchor="end" fill="#64748b" font-size="10">0</text>
    <!-- Baseline curve points (scale: 45GB=150px height) -->
    <!-- forward: 10.6->42.4, backward: 42.4->10.6, optimizer: 10.6->12.4->10.6 -->
    <polyline points="65,142 160,89 240,16 340,89 420,131 480,126 540,131 620,131"
      fill="none" stroke="#38bdf8" stroke-width="2"/>
    <polygon points="65,142 160,89 240,16 340,89 420,131 480,126 540,131 620,131 620,160 65,160"
      fill="url(#memGrad)"/>
    <!-- Grad checkpointing curve -->
    <polyline points="65,142 160,116 240,89 340,116 420,149 480,145 540,149 620,149"
      fill="none" stroke="#4ade80" stroke-width="2" stroke-dasharray="6,3"/>
    <polygon points="65,142 160,116 240,89 340,116 420,149 480,145 540,149 620,149 620,160 65,160"
      fill="url(#ckptGrad)"/>
    <!-- Labels -->
    <text x="120" y="175" text-anchor="middle" fill="#94a3b8" font-size="10">Load</text>
    <text x="240" y="175" text-anchor="middle" fill="#94a3b8" font-size="10">Forward</text>
    <text x="370" y="175" text-anchor="middle" fill="#94a3b8" font-size="10">Backward</text>
    <text x="490" y="175" text-anchor="middle" fill="#94a3b8" font-size="10">Optim Step</text>
    <text x="620" y="175" text-anchor="middle" fill="#94a3b8" font-size="10">Idle</text>
    <!-- Legend -->
    <rect x="65" y="185" width="14" height="4" fill="#38bdf8" rx="2"/>
    <text x="84" y="192" fill="#94a3b8" font-size="10">Baseline (42.4 GB peak)</text>
    <rect x="270" y="185" width="14" height="4" fill="#4ade80" rx="2"/>
    <text x="289" y="192" fill="#94a3b8" font-size="10">Grad Checkpointing (26.8 GB peak)</text>
  </svg>
</div>

<h2>N2 Pipeline Parallel Config (2-GPU)</h2>
<div class="cards">
  <div class="card blue">
    <div class="card-val">GPU 0</div>
    <div class="card-label">Layers 0-18 (encoder + early decoder)</div>
  </div>
  <div class="card blue">
    <div class="card-val">GPU 1</div>
    <div class="card-label">Layers 19-36 (late decoder + heads)</div>
  </div>
  <div class="card green">
    <div class="card-val">~21 GB</div>
    <div class="card-label">Per-GPU peak (full fine-tune)</div>
  </div>
  <div class="card">
    <div class="card-val">PCIe</div>
    <div class="card-label">Inter-GPU activation transfer</div>
  </div>
</div>

<p class="footer">OCI Robot Cloud — GPU Memory Profiler V2 | Port 8950 | A100 80GB Safe Headroom: 86.7%</p>
</body>
</html>
"""

if USE_FASTAPI:
    app = FastAPI(title="GPU Memory Profiler V2")

    @app.get("/", response_class=HTMLResponse)
    async def index():
        return HTML

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "gpu_memory_profiler_v2", "port": 8950}

    @app.get("/api/memory")
    async def memory_breakdown():
        return {
            "model_weights_gb": 6.7,
            "activations_gb": 2.1,
            "optimizer_state_gb": 1.8,
            "total_peak_gb": 10.6,
            "a100_capacity_gb": 80,
            "utilization_pct": round(10.6 / 80 * 100, 1),
            "grad_checkpointing_peak_gb": 6.4,
            "grad_checkpointing_reduction_pct": 40,
            "n2_min_gpus": 2,
        }

else:
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(HTML.encode())

        def log_message(self, *args):
            pass

if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8950)
    else:
        server = HTTPServer(("0.0.0.0", 8950), Handler)
        print("Serving on http://0.0.0.0:8950")
        server.serve_forever()
