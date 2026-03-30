"""
training_throughput_v4.py — OCI Robot Cloud
Port 8672 | Step-time breakdown, GPU scaling, optimization opportunities
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
<title>Training Throughput v4 — OCI Robot Cloud</title>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',system-ui,sans-serif;min-height:100vh;padding:32px}
  h1{color:#C74634;font-size:1.7rem;font-weight:700;margin-bottom:4px}
  .subtitle{color:#94a3b8;font-size:.9rem;margin-bottom:32px}
  .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(480px,1fr));gap:24px}
  .card{background:#1e293b;border:1px solid #334155;border-radius:12px;padding:24px}
  .card h2{color:#38bdf8;font-size:1rem;font-weight:600;margin-bottom:16px;text-transform:uppercase;letter-spacing:.06em}
  .metrics{display:flex;flex-wrap:wrap;gap:16px;margin-bottom:32px}
  .metric{background:#1e293b;border:1px solid #334155;border-radius:10px;padding:16px 24px;min-width:160px}
  .metric .val{color:#C74634;font-size:1.6rem;font-weight:700}
  .metric .lbl{color:#94a3b8;font-size:.78rem;margin-top:2px}
  svg{width:100%;height:auto;display:block}
  .legend{display:flex;flex-wrap:wrap;gap:10px;margin-top:12px}
  .leg-item{display:flex;align-items:center;gap:5px;font-size:.75rem;color:#94a3b8}
  .leg-dot{width:10px;height:10px;border-radius:2px;flex-shrink:0}
  footer{margin-top:40px;color:#475569;font-size:.75rem;text-align:center}
</style>
</head>
<body>

<h1>Training Throughput v4</h1>
<p class="subtitle">OCI Robot Cloud — GR00T N1.6 Fine-Tuning Performance Analysis</p>

<div class="metrics">
  <div class="metric"><div class="val">8.9 it/s</div><div class="lbl">4-GPU FP16 throughput</div></div>
  <div class="metric"><div class="val">13.2 it/s</div><div class="lbl">FP8 target (+48%)</div></div>
  <div class="metric"><div class="val">+0.8 it/s</div><div class="lbl">Async prefetch gain</div></div>
  <div class="metric"><div class="val">$0.043</div><div class="lbl">Per sim-episode cost</div></div>
</div>

<div class="grid">

  <!-- Card 1: Step time breakdown stacked bar -->
  <div class="card">
    <h2>Step Time Breakdown by GPU Config</h2>
    <svg viewBox="0 0 460 300" xmlns="http://www.w3.org/2000/svg">
      <text x="12" y="160" fill="#64748b" font-size="10" transform="rotate(-90,12,160)" text-anchor="middle">Step Time (ms)</text>
      <line x1="55" y1="30" x2="55" y2="250" stroke="#1e3a5f" stroke-width="1"/>
      <text x="50" y="254" fill="#64748b" font-size="9" text-anchor="end">0</text>
      <line x1="55" y1="250" x2="435" y2="250" stroke="#334155" stroke-width="1"/>
      <text x="50" y="207" fill="#64748b" font-size="9" text-anchor="end">100</text>
      <line x1="55" y1="206" x2="435" y2="206" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="3,3"/>
      <text x="50" y="163" fill="#64748b" font-size="9" text-anchor="end">200</text>
      <line x1="55" y1="162" x2="435" y2="162" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="3,3"/>
      <text x="50" y="119" fill="#64748b" font-size="9" text-anchor="end">300</text>
      <line x1="55" y1="118" x2="435" y2="118" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="3,3"/>
      <text x="50" y="75" fill="#64748b" font-size="9" text-anchor="end">400</text>
      <line x1="55" y1="74" x2="435" y2="74" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="3,3"/>

      <!-- 1-GPU bar (426ms) -->
      <rect x="95" y="223.6" width="70" height="26.4" fill="#38bdf8" opacity="0.9"/>
      <rect x="95" y="214.8" width="70" height="8.8" fill="#818cf8" opacity="0.9"/>
      <rect x="95" y="135.6" width="70" height="79.2" fill="#C74634" opacity="0.9"/>
      <rect x="95" y="96" width="70" height="39.6" fill="#f59e0b" opacity="0.9"/>
      <rect x="95" y="60.8" width="70" height="35.2" fill="#34d399" opacity="0.9"/>
      <rect x="95" y="38.8" width="70" height="22" fill="#fb7185" opacity="0.9"/>
      <rect x="95" y="30" width="70" height="8.8" fill="#a78bfa" opacity="0.9"/>
      <text x="130" y="265" fill="#94a3b8" font-size="10" text-anchor="middle">1-GPU</text>
      <text x="130" y="276" fill="#64748b" font-size="9" text-anchor="middle">426 ms</text>

      <!-- 2-GPU bar (224ms) -->
      <rect x="195" y="236.1" width="70" height="13.9" fill="#38bdf8" opacity="0.9"/>
      <rect x="195" y="231.5" width="70" height="4.6" fill="#818cf8" opacity="0.9"/>
      <rect x="195" y="189.9" width="70" height="41.6" fill="#C74634" opacity="0.9"/>
      <rect x="195" y="169.1" width="70" height="20.8" fill="#f59e0b" opacity="0.9"/>
      <rect x="195" y="150.6" width="70" height="18.5" fill="#34d399" opacity="0.9"/>
      <rect x="195" y="139" width="70" height="11.6" fill="#fb7185" opacity="0.9"/>
      <rect x="195" y="134.4" width="70" height="4.6" fill="#a78bfa" opacity="0.9"/>
      <text x="230" y="265" fill="#94a3b8" font-size="10" text-anchor="middle">2-GPU</text>
      <text x="230" y="276" fill="#64748b" font-size="9" text-anchor="middle">224 ms</text>

      <!-- 4-GPU bar (112ms) -->
      <rect x="295" y="243.1" width="70" height="6.9" fill="#38bdf8" opacity="0.9"/>
      <rect x="295" y="240.8" width="70" height="2.3" fill="#818cf8" opacity="0.9"/>
      <rect x="295" y="220" width="70" height="20.8" fill="#C74634" opacity="0.9"/>
      <rect x="295" y="209.6" width="70" height="10.4" fill="#f59e0b" opacity="0.9"/>
      <rect x="295" y="200.4" width="70" height="9.2" fill="#34d399" opacity="0.9"/>
      <rect x="295" y="194.6" width="70" height="5.8" fill="#fb7185" opacity="0.9"/>
      <rect x="295" y="192.1" width="70" height="2.3" fill="#a78bfa" opacity="0.9"/>
      <text x="330" y="265" fill="#94a3b8" font-size="10" text-anchor="middle">4-GPU</text>
      <text x="330" y="276" fill="#64748b" font-size="9" text-anchor="middle">112 ms</text>
    </svg>
    <div class="legend">
      <div class="leg-item"><div class="leg-dot" style="background:#38bdf8"></div>data_load 12%</div>
      <div class="leg-item"><div class="leg-dot" style="background:#818cf8"></div>tokenize 4%</div>
      <div class="leg-item"><div class="leg-dot" style="background:#C74634"></div>vision_enc 36%</div>
      <div class="leg-item"><div class="leg-dot" style="background:#f59e0b"></div>cross_attn 18%</div>
      <div class="leg-item"><div class="leg-dot" style="background:#34d399"></div>action_dec 16%</div>
      <div class="leg-item"><div class="leg-dot" style="background:#fb7185"></div>backward 10%</div>
      <div class="leg-item"><div class="leg-dot" style="background:#a78bfa"></div>optimizer 4%</div>
    </div>
  </div>

  <!-- Card 2: GPU scaling efficiency -->
  <div class="card">
    <h2>GPU Scaling Efficiency</h2>
    <svg viewBox="0 0 460 280" xmlns="http://www.w3.org/2000/svg">
      <line x1="60" y1="20" x2="60" y2="230" stroke="#334155" stroke-width="1.5"/>
      <line x1="60" y1="230" x2="430" y2="230" stroke="#334155" stroke-width="1.5"/>
      <text x="14" y="130" fill="#64748b" font-size="10" transform="rotate(-90,14,130)" text-anchor="middle">Throughput (it/s)</text>
      <text x="245" y="268" fill="#64748b" font-size="10" text-anchor="middle">GPU Count</text>
      <text x="55" y="233" fill="#64748b" font-size="9" text-anchor="end">0</text>
      <text x="55" y="191" fill="#64748b" font-size="9" text-anchor="end">2</text>
      <line x1="60" y1="188" x2="430" y2="188" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="3,3"/>
      <text x="55" y="149" fill="#64748b" font-size="9" text-anchor="end">4</text>
      <line x1="60" y1="146" x2="430" y2="146" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="3,3"/>
      <text x="55" y="107" fill="#64748b" font-size="9" text-anchor="end">6</text>
      <line x1="60" y1="104" x2="430" y2="104" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="3,3"/>
      <text x="55" y="65" fill="#64748b" font-size="9" text-anchor="end">8</text>
      <line x1="60" y1="62" x2="430" y2="62" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="3,3"/>
      <text x="55" y="23" fill="#64748b" font-size="9" text-anchor="end">10</text>
      <line x1="60" y1="20" x2="430" y2="20" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="3,3"/>
      <text x="120" y="245" fill="#94a3b8" font-size="10" text-anchor="middle">1</text>
      <text x="245" y="245" fill="#94a3b8" font-size="10" text-anchor="middle">2</text>
      <text x="370" y="245" fill="#94a3b8" font-size="10" text-anchor="middle">4</text>
      <!-- Ideal line -->
      <polyline points="120,180.65 245,131.3 370,32.6" fill="none" stroke="#38bdf8" stroke-width="1.5" stroke-dasharray="6,3" opacity="0.6"/>
      <text x="380" y="30" fill="#38bdf8" font-size="9" opacity="0.7">ideal</text>
      <!-- 1-GPU bar: 2.35 it/s -->
      <rect x="95" y="180.65" width="50" height="49.35" fill="#C74634" opacity="0.85" rx="3"/>
      <text x="120" y="176" fill="#e2e8f0" font-size="10" text-anchor="middle">2.35</text>
      <!-- 2-GPU bar: 4.47 it/s -->
      <rect x="220" y="136.13" width="50" height="93.87" fill="#C74634" opacity="0.85" rx="3"/>
      <text x="245" y="131" fill="#e2e8f0" font-size="10" text-anchor="middle">4.47</text>
      <text x="245" y="119" fill="#34d399" font-size="9" text-anchor="middle">95.1% eff</text>
      <!-- 4-GPU bar: 8.90 it/s -->
      <rect x="345" y="43.1" width="50" height="186.9" fill="#C74634" opacity="0.85" rx="3"/>
      <text x="370" y="38" fill="#e2e8f0" font-size="10" text-anchor="middle">8.90</text>
      <text x="370" y="26" fill="#34d399" font-size="9" text-anchor="middle">94.7% eff</text>
      <!-- Ideal dots -->
      <circle cx="120" cy="180.65" r="4" fill="#38bdf8" opacity="0.8"/>
      <circle cx="245" cy="131.3" r="4" fill="#38bdf8" opacity="0.8"/>
      <circle cx="370" cy="32.6" r="4" fill="#38bdf8" opacity="0.8"/>
    </svg>
    <div class="legend">
      <div class="leg-item"><div class="leg-dot" style="background:#C74634"></div>Measured throughput</div>
      <div class="leg-item"><div class="leg-dot" style="background:#38bdf8;opacity:0.6"></div>Ideal linear scaling</div>
    </div>
  </div>

  <!-- Card 3: Optimization opportunities -->
  <div class="card" style="grid-column:1/-1">
    <h2>Optimization Opportunities — Expected Speedup</h2>
    <svg viewBox="0 0 860 220" xmlns="http://www.w3.org/2000/svg">
      <line x1="180" y1="20" x2="180" y2="170" stroke="#334155" stroke-width="1.5"/>
      <line x1="180" y1="170" x2="840" y2="170" stroke="#334155" stroke-width="1.5"/>
      <text x="510" y="210" fill="#64748b" font-size="10" text-anchor="middle">Expected Throughput Gain (%)</text>
      <text x="180" y="185" fill="#64748b" font-size="9" text-anchor="middle">0</text>
      <text x="290" y="185" fill="#64748b" font-size="9" text-anchor="middle">10</text>
      <line x1="290" y1="20" x2="290" y2="170" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="3,3"/>
      <text x="400" y="185" fill="#64748b" font-size="9" text-anchor="middle">20</text>
      <line x1="400" y1="20" x2="400" y2="170" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="3,3"/>
      <text x="510" y="185" fill="#64748b" font-size="9" text-anchor="middle">30</text>
      <line x1="510" y1="20" x2="510" y2="170" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="3,3"/>
      <text x="620" y="185" fill="#64748b" font-size="9" text-anchor="middle">40</text>
      <line x1="620" y1="20" x2="620" y2="170" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="3,3"/>
      <text x="730" y="185" fill="#64748b" font-size="9" text-anchor="middle">50</text>
      <line x1="730" y1="20" x2="730" y2="170" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="3,3"/>
      <!-- Async Prefetch +8.5% -->
      <text x="172" y="50" fill="#94a3b8" font-size="11" text-anchor="end">Async Prefetch</text>
      <rect x="180" y="30" width="93.5" height="28" fill="#38bdf8" opacity="0.85" rx="3"/>
      <text x="279" y="49" fill="#38bdf8" font-size="10">+8.5%</text>
      <!-- FP8 +48.3% -->
      <text x="172" y="88" fill="#94a3b8" font-size="11" text-anchor="end">FP8 Precision</text>
      <rect x="180" y="68" width="531.3" height="28" fill="#C74634" opacity="0.85" rx="3"/>
      <text x="717" y="87" fill="#C74634" font-size="10">+48.3%</text>
      <!-- TensorRT +22% -->
      <text x="172" y="126" fill="#94a3b8" font-size="11" text-anchor="end">TensorRT Enc.</text>
      <rect x="180" y="106" width="242" height="28" fill="#f59e0b" opacity="0.85" rx="3"/>
      <text x="428" y="125" fill="#f59e0b" font-size="10">+22.0%</text>
      <!-- Grad Accum +5% -->
      <text x="172" y="164" fill="#94a3b8" font-size="11" text-anchor="end">Grad. Accumulation</text>
      <rect x="180" y="144" width="55" height="28" fill="#a78bfa" opacity="0.85" rx="3"/>
      <text x="241" y="163" fill="#a78bfa" font-size="10">+5.0%</text>
    </svg>
  </div>

</div>

<footer>OCI Robot Cloud · Training Throughput v4 · Port 8672 · © 2026 Oracle Corporation</footer>
</body>
</html>"""

if USE_FASTAPI:
    app = FastAPI(title="Training Throughput v4", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def index():
        return HTML

    @app.get("/health")
    async def health():
        return {
            "status": "ok",
            "service": "training_throughput_v4",
            "port": 8672,
            "metrics": {
                "throughput_4gpu_fp16_its": 8.9,
                "throughput_fp8_target_its": 13.2,
                "async_prefetch_gain_its": 0.8,
                "cost_per_sim_episode_usd": 0.043,
            },
        }

    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=8672)

else:
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            if self.path == "/health":
                body = b'{"status":"ok","service":"training_throughput_v4","port":8672}'
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
            else:
                body = HTML.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    if __name__ == "__main__":
        print("Serving on http://0.0.0.0:8672 (stdlib fallback)")
        HTTPServer(("0.0.0.0", 8672), Handler).serve_forever()
