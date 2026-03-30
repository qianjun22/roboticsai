"""Model Sharding Optimizer — FastAPI port 8592"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8592

def build_html():
    return """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Model Sharding Optimizer — OCI Robot Cloud</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; min-height: 100vh; }
  .header { background: #1e293b; border-bottom: 2px solid #C74634; padding: 20px 32px; display: flex; align-items: center; gap: 16px; }
  .header h1 { color: #C74634; font-size: 1.6rem; font-weight: 700; letter-spacing: -0.02em; }
  .header .sub { color: #94a3b8; font-size: 0.9rem; }
  .badge { background: #C74634; color: #fff; font-size: 0.75rem; font-weight: 600; padding: 3px 10px; border-radius: 20px; }
  .container { max-width: 1400px; margin: 0 auto; padding: 32px; }
  .metrics-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 32px; }
  .metric-card { background: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 20px; text-align: center; }
  .metric-card .val { font-size: 2rem; font-weight: 700; color: #38bdf8; }
  .metric-card .label { color: #94a3b8; font-size: 0.8rem; margin-top: 6px; }
  .metric-card .sub-val { color: #64748b; font-size: 0.85rem; margin-top: 4px; }
  .charts-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; margin-bottom: 24px; }
  .chart-full { grid-column: 1 / -1; }
  .chart-card { background: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 24px; }
  .chart-card h2 { color: #C74634; font-size: 1rem; font-weight: 600; margin-bottom: 20px; display: flex; align-items: center; gap: 8px; }
  .chart-card h2::before { content: ''; display: inline-block; width: 4px; height: 16px; background: #C74634; border-radius: 2px; }
  svg text { font-family: 'Segoe UI', system-ui, sans-serif; }
  .insight { background: #0f172a; border: 1px solid #38bdf8; border-radius: 8px; padding: 12px 16px; margin-top: 16px; color: #38bdf8; font-size: 0.85rem; }
  .footer { text-align: center; color: #475569; font-size: 0.8rem; padding: 24px; border-top: 1px solid #1e293b; }
</style>
</head>
<body>

<div class="header">
  <div>
    <h1>Model Sharding Optimizer</h1>
    <div class="sub">GR00T 3B tensor &amp; pipeline parallelism analysis — OCI Robot Cloud</div>
  </div>
  <span class="badge">PORT 8592</span>
</div>

<div class="container">

  <!-- Metrics Row -->
  <div class="metrics-row">
    <div class="metric-card">
      <div class="val">3.2x</div>
      <div class="label">4-GPU TP Throughput</div>
      <div class="sub-val">vs single GPU baseline</div>
    </div>
    <div class="metric-card">
      <div class="val">82%</div>
      <div class="label">4-GPU TP Efficiency</div>
      <div class="sub-val">scaling efficiency</div>
    </div>
    <div class="metric-card">
      <div class="val">5.1x</div>
      <div class="label">Hybrid TP+PP Throughput</div>
      <div class="sub-val">8-GPU combined sharding</div>
    </div>
    <div class="metric-card">
      <div class="val">78%</div>
      <div class="label">Hybrid TP+PP Efficiency</div>
      <div class="sub-val">at 8-GPU scale</div>
    </div>
  </div>

  <!-- Charts Grid -->
  <div class="charts-grid">

    <!-- Tensor Parallelism Efficiency -->
    <div class="chart-card">
      <h2>Tensor Parallelism: Throughput &amp; Efficiency</h2>
      <svg viewBox="0 0 520 300" width="100%">
        <!-- Background grid -->
        <line x1="60" y1="20" x2="60" y2="240" stroke="#334155" stroke-width="1"/>
        <line x1="60" y1="240" x2="500" y2="240" stroke="#334155" stroke-width="1"/>
        <!-- Horizontal grid lines -->
        <line x1="60" y1="180" x2="500" y2="180" stroke="#1e3a4a" stroke-width="1" stroke-dasharray="4,4"/>
        <line x1="60" y1="120" x2="500" y2="120" stroke="#1e3a4a" stroke-width="1" stroke-dasharray="4,4"/>
        <line x1="60" y1="60" x2="500" y2="60" stroke="#1e3a4a" stroke-width="1" stroke-dasharray="4,4"/>
        <!-- Y axis labels -->
        <text x="50" y="244" text-anchor="end" fill="#64748b" font-size="11">0</text>
        <text x="50" y="184" text-anchor="end" fill="#64748b" font-size="11">2</text>
        <text x="50" y="124" text-anchor="end" fill="#64748b" font-size="11">4</text>
        <text x="50" y="64" text-anchor="end" fill="#64748b" font-size="11">6</text>
        <!-- Y axis title -->
        <text x="14" y="140" text-anchor="middle" fill="#94a3b8" font-size="11" transform="rotate(-90 14 140)">Throughput (relative)</text>
        <!-- Bars: 1,2,4,8 GPU -- throughput 1.0, 1.9, 3.2, 5.1 (max ~6) -->
        <!-- GPU 1: throughput bar (blue) -->
        <rect x="80" y="200" width="40" height="40" fill="#38bdf8" rx="3" opacity="0.9"/>
        <text x="100" y="196" text-anchor="middle" fill="#38bdf8" font-size="11" font-weight="600">1.0x</text>
        <!-- GPU 2 -->
        <rect x="180" y="164" width="40" height="76" fill="#38bdf8" rx="3" opacity="0.9"/>
        <text x="200" y="160" text-anchor="middle" fill="#38bdf8" font-size="11" font-weight="600">1.9x</text>
        <!-- GPU 4 -->
        <rect x="280" y="112" width="40" height="128" fill="#38bdf8" rx="3" opacity="0.9"/>
        <text x="300" y="108" text-anchor="middle" fill="#38bdf8" font-size="11" font-weight="600">3.2x</text>
        <!-- GPU 8 -->
        <rect x="380" y="36" width="40" height="204" fill="#38bdf8" rx="3" opacity="0.9"/>
        <text x="400" y="32" text-anchor="middle" fill="#38bdf8" font-size="11" font-weight="600">5.1x</text>
        <!-- Efficiency line: 100%, 95%, 82%, 65% (scale: 240 - pct*1.8) -->
        <polyline points="100,60 200,69 300,92.4 400,123" fill="none" stroke="#C74634" stroke-width="2.5" stroke-linejoin="round"/>
        <circle cx="100" cy="60" r="5" fill="#C74634"/>
        <circle cx="200" cy="69" r="5" fill="#C74634"/>
        <circle cx="300" cy="92.4" r="5" fill="#C74634"/>
        <circle cx="400" cy="123" r="5" fill="#C74634"/>
        <!-- Efficiency labels -->
        <text x="100" y="52" text-anchor="middle" fill="#C74634" font-size="10">100%</text>
        <text x="200" y="61" text-anchor="middle" fill="#C74634" font-size="10">95%</text>
        <text x="300" y="85" text-anchor="middle" fill="#C74634" font-size="10">82%</text>
        <text x="400" y="116" text-anchor="middle" fill="#C74634" font-size="10">65%</text>
        <!-- X axis labels -->
        <text x="100" y="258" text-anchor="middle" fill="#94a3b8" font-size="11">1 GPU</text>
        <text x="200" y="258" text-anchor="middle" fill="#94a3b8" font-size="11">2 GPU</text>
        <text x="300" y="258" text-anchor="middle" fill="#94a3b8" font-size="11">4 GPU</text>
        <text x="400" y="258" text-anchor="middle" fill="#94a3b8" font-size="11">8 GPU</text>
        <!-- Legend -->
        <rect x="62" y="272" width="12" height="12" fill="#38bdf8" rx="2"/>
        <text x="79" y="282" fill="#94a3b8" font-size="10">Throughput</text>
        <circle cx="160" cy="278" r="5" fill="#C74634"/>
        <text x="170" y="282" fill="#94a3b8" font-size="10">Efficiency</text>
      </svg>
      <div class="insight">Optimal sweet spot: 4-GPU TP delivers 3.2x throughput at 82% efficiency — best throughput/efficiency tradeoff for GR00T 3B inference.</div>
    </div>

    <!-- Pipeline Parallelism Bubble Ratio -->
    <div class="chart-card">
      <h2>Pipeline Parallelism: Bubble Ratio vs Micro-Batch</h2>
      <svg viewBox="0 0 520 300" width="100%">
        <!-- Grid -->
        <line x1="60" y1="20" x2="60" y2="240" stroke="#334155" stroke-width="1"/>
        <line x1="60" y1="240" x2="500" y2="240" stroke="#334155" stroke-width="1"/>
        <line x1="60" y1="190" x2="500" y2="190" stroke="#1e3a4a" stroke-width="1" stroke-dasharray="4,4"/>
        <line x1="60" y1="140" x2="500" y2="140" stroke="#1e3a4a" stroke-width="1" stroke-dasharray="4,4"/>
        <line x1="60" y1="90" x2="500" y2="90" stroke="#1e3a4a" stroke-width="1" stroke-dasharray="4,4"/>
        <!-- Y labels -->
        <text x="50" y="244" text-anchor="end" fill="#64748b" font-size="11">0%</text>
        <text x="50" y="194" text-anchor="end" fill="#64748b" font-size="11">20%</text>
        <text x="50" y="144" text-anchor="end" fill="#64748b" font-size="11">40%</text>
        <text x="50" y="94" text-anchor="end" fill="#64748b" font-size="11">60%</text>
        <text x="14" y="140" text-anchor="middle" fill="#94a3b8" font-size="11" transform="rotate(-90 14 140)">Bubble Ratio (%)</text>
        <!-- Data points: mb=1:50%, mb=2:28%, mb=4:15%, mb=8:8%, mb=16:5% -->
        <!-- y = 240 - pct*3.8 (50%->50, so 240-190=50 ✓; 28%->240-106=134... use scale 240-pct*3.8) -->
        <!-- x positions: 80, 155, 230, 340, 450 -->
        <polyline
          points="80,50 155,133.6 230,183 340,209.6 450,221"
          fill="none" stroke="#38bdf8" stroke-width="2.5" stroke-linejoin="round"/>
        <!-- Fill area under curve -->
        <polygon
          points="80,50 155,133.6 230,183 340,209.6 450,221 450,240 80,240"
          fill="#38bdf8" opacity="0.08"/>
        <!-- Data point circles -->
        <circle cx="80" cy="50" r="6" fill="#C74634" stroke="#0f172a" stroke-width="2"/>
        <circle cx="155" cy="133.6" r="6" fill="#C74634" stroke="#0f172a" stroke-width="2"/>
        <circle cx="230" cy="183" r="6" fill="#C74634" stroke="#0f172a" stroke-width="2"/>
        <circle cx="340" cy="209.6" r="6" fill="#C74634" stroke="#0f172a" stroke-width="2"/>
        <circle cx="450" cy="221" r="6" fill="#C74634" stroke="#0f172a" stroke-width="2"/>
        <!-- Labels -->
        <text x="80" y="42" text-anchor="middle" fill="#e2e8f0" font-size="10" font-weight="600">50%</text>
        <text x="155" y="126" text-anchor="middle" fill="#e2e8f0" font-size="10" font-weight="600">28%</text>
        <text x="230" y="175" text-anchor="middle" fill="#e2e8f0" font-size="10" font-weight="600">15%</text>
        <text x="340" y="202" text-anchor="middle" fill="#e2e8f0" font-size="10" font-weight="600">8%</text>
        <text x="450" y="213" text-anchor="middle" fill="#e2e8f0" font-size="10" font-weight="600">5%</text>
        <!-- X labels -->
        <text x="80" y="258" text-anchor="middle" fill="#94a3b8" font-size="11">mb=1</text>
        <text x="155" y="258" text-anchor="middle" fill="#94a3b8" font-size="11">mb=2</text>
        <text x="230" y="258" text-anchor="middle" fill="#94a3b8" font-size="11">mb=4</text>
        <text x="340" y="258" text-anchor="middle" fill="#94a3b8" font-size="11">mb=8</text>
        <text x="450" y="258" text-anchor="middle" fill="#94a3b8" font-size="11">mb=16</text>
        <text x="280" y="275" text-anchor="middle" fill="#64748b" font-size="10">Micro-Batch Count</text>
      </svg>
      <div class="insight">Increasing micro-batches from 1→16 reduces pipeline bubble from 50%→5%. Use mb=8 for balanced latency/efficiency in production inference.</div>
    </div>

    <!-- Memory Per Shard (full width) -->
    <div class="chart-card chart-full">
      <h2>GR00T 3B — Memory Per Shard by GPU Count</h2>
      <svg viewBox="0 0 1100 260" width="100%">
        <!-- Axes -->
        <line x1="80" y1="20" x2="80" y2="210" stroke="#334155" stroke-width="1"/>
        <line x1="80" y1="210" x2="1060" y2="210" stroke="#334155" stroke-width="1"/>
        <!-- Grid lines -->
        <line x1="80" y1="160" x2="1060" y2="160" stroke="#1e3a4a" stroke-width="1" stroke-dasharray="4,4"/>
        <line x1="80" y1="110" x2="1060" y2="110" stroke="#1e3a4a" stroke-width="1" stroke-dasharray="4,4"/>
        <line x1="80" y1="60" x2="1060" y2="60" stroke="#1e3a4a" stroke-width="1" stroke-dasharray="4,4"/>
        <!-- Y labels (0,2,4,6,8 GB) -->
        <text x="70" y="214" text-anchor="end" fill="#64748b" font-size="11">0 GB</text>
        <text x="70" y="164" text-anchor="end" fill="#64748b" font-size="11">2 GB</text>
        <text x="70" y="114" text-anchor="end" fill="#64748b" font-size="11">4 GB</text>
        <text x="70" y="64" text-anchor="end" fill="#64748b" font-size="11">6 GB</text>
        <text x="20" y="120" text-anchor="middle" fill="#94a3b8" font-size="11" transform="rotate(-90 20 120)">Memory/Shard (GB)</text>
        <!-- Bars: 1GPU=6.7GB, 2GPU=3.5GB, 4GPU=1.8GB, 8GPU=0.95GB -->
        <!-- scale: 210 - gb*(210-20)/7 = 210 - gb*27.14 -->
        <!-- 1GPU: y=210-6.7*27.14=28, h=182 -->
        <rect x="150" y="28" width="120" height="182" fill="#C74634" rx="4" opacity="0.85"/>
        <text x="210" y="22" text-anchor="middle" fill="#C74634" font-size="13" font-weight="700">6.7 GB</text>
        <!-- 2GPU: y=210-3.5*27.14=115, h=95 -->
        <rect x="380" y="115" width="120" height="95" fill="#38bdf8" rx="4" opacity="0.85"/>
        <text x="440" y="109" text-anchor="middle" fill="#38bdf8" font-size="13" font-weight="700">3.5 GB</text>
        <!-- 4GPU: y=210-1.8*27.14=161, h=49 -->
        <rect x="610" y="161" width="120" height="49" fill="#38bdf8" rx="4" opacity="0.85"/>
        <text x="670" y="155" text-anchor="middle" fill="#38bdf8" font-size="13" font-weight="700">1.8 GB</text>
        <!-- 8GPU: y=210-0.95*27.14=184, h=26 -->
        <rect x="840" y="184" width="120" height="26" fill="#10b981" rx="4" opacity="0.85"/>
        <text x="900" y="178" text-anchor="middle" fill="#10b981" font-size="13" font-weight="700">0.95 GB</text>
        <!-- Reduction badges -->
        <text x="440" y="138" text-anchor="middle" fill="#64748b" font-size="10">▼ 48%</text>
        <text x="670" y="175" text-anchor="middle" fill="#64748b" font-size="10">▼ 73%</text>
        <text x="900" y="196" text-anchor="middle" fill="#64748b" font-size="10">▼ 86%</text>
        <!-- X labels -->
        <text x="210" y="228" text-anchor="middle" fill="#94a3b8" font-size="12">1 GPU (baseline)</text>
        <text x="440" y="228" text-anchor="middle" fill="#94a3b8" font-size="12">2 GPU shards</text>
        <text x="670" y="228" text-anchor="middle" fill="#94a3b8" font-size="12">4 GPU shards</text>
        <text x="900" y="228" text-anchor="middle" fill="#94a3b8" font-size="12">8 GPU shards</text>
        <!-- Legend -->
        <rect x="82" y="242" width="12" height="10" fill="#C74634" rx="2" opacity="0.85"/>
        <text x="99" y="251" fill="#94a3b8" font-size="10">Single GPU (full model)</text>
        <rect x="230" y="242" width="12" height="10" fill="#38bdf8" rx="2" opacity="0.85"/>
        <text x="247" y="251" fill="#94a3b8" font-size="10">Tensor parallel shards</text>
        <rect x="390" y="242" width="12" height="10" fill="#10b981" rx="2" opacity="0.85"/>
        <text x="407" y="251" fill="#94a3b8" font-size="10">8-GPU optimal</text>
      </svg>
      <div class="insight">8-GPU sharding reduces per-device memory 86% (6.7 GB → 0.95 GB), enabling GR00T 3B on lower-memory OCI instances. Tradeoff: 65% scaling efficiency vs 100% single-GPU utilization.</div>
    </div>

  </div>

</div>

<div class="footer">OCI Robot Cloud — Model Sharding Optimizer | Port 8592 | GR00T 3B Parallelism Analysis</div>

</body>
</html>
"""

if USE_FASTAPI:
    app = FastAPI(title="Model Sharding Optimizer")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return build_html()

    @app.get("/health")
    def health():
        return {"status": "ok", "port": PORT}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(build_html().encode())

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
