# Policy Gradient Visualizer V2 — port 8908
# Per-layer gradient norms, gradient health trend, LoRA gradient isolation

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
<title>Policy Gradient Visualizer V2</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; padding: 2rem; }
  h1 { color: #C74634; font-size: 2rem; margin-bottom: 0.5rem; }
  h2 { color: #38bdf8; font-size: 1.25rem; margin: 1.5rem 0 0.75rem; }
  .subtitle { color: #94a3b8; margin-bottom: 2rem; }
  .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; }
  .card { background: #1e293b; border-radius: 12px; padding: 1.5rem; }
  .card.full { grid-column: 1 / -1; }
  svg text { font-family: 'Segoe UI', sans-serif; }
  .tag { display: inline-block; background: #0f172a; color: #38bdf8; border: 1px solid #38bdf8;
         border-radius: 4px; padding: 2px 8px; font-size: 0.75rem; margin: 2px; }
  .tag.red { color: #C74634; border-color: #C74634; }
  .tag.green { color: #4ade80; border-color: #4ade80; }
  .stat { font-size: 2rem; font-weight: 700; color: #38bdf8; }
  .stat-label { font-size: 0.8rem; color: #94a3b8; margin-top: 4px; }
  .stats-row { display: flex; gap: 2rem; margin-top: 1rem; }
</style>
</head>
<body>
<h1>Policy Gradient Visualizer V2</h1>
<p class="subtitle">Per-layer gradient norms &bull; LoRA isolation &bull; Training stability — Port 8908</p>

<div class="grid">
  <!-- Gradient Norm Bars -->
  <div class="card">
    <h2>Per-Layer Gradient Norms</h2>
    <svg width="100%" viewBox="0 0 420 240" xmlns="http://www.w3.org/2000/svg">
      <!-- Y axis -->
      <line x1="60" y1="10" x2="60" y2="200" stroke="#334155" stroke-width="1"/>
      <!-- X axis -->
      <line x1="60" y1="200" x2="410" y2="200" stroke="#334155" stroke-width="1"/>
      <!-- Y labels -->
      <text x="55" y="200" text-anchor="end" fill="#94a3b8" font-size="10">0</text>
      <text x="55" y="155" text-anchor="end" fill="#94a3b8" font-size="10">0.05</text>
      <text x="55" y="110" text-anchor="end" fill="#94a3b8" font-size="10">0.10</text>
      <text x="55" y="65" text-anchor="end" fill="#94a3b8" font-size="10">0.15</text>
      <text x="55" y="20" text-anchor="end" fill="#94a3b8" font-size="10">0.20</text>
      <!-- grid lines -->
      <line x1="60" y1="155" x2="410" y2="155" stroke="#1e293b" stroke-width="1" stroke-dasharray="3,3"/>
      <line x1="60" y1="110" x2="410" y2="110" stroke="#1e293b" stroke-width="1" stroke-dasharray="3,3"/>
      <line x1="60" y1="65" x2="410" y2="65" stroke="#1e293b" stroke-width="1" stroke-dasharray="3,3"/>
      <!-- encoder bar: norm 0.182 -> height=182/200*190=172.9 -->
      <rect x="75" y="27" width="50" height="173" fill="#38bdf8" rx="3"/>
      <text x="100" y="218" text-anchor="middle" fill="#94a3b8" font-size="10">encoder</text>
      <text x="100" y="22" text-anchor="middle" fill="#e2e8f0" font-size="10">0.182</text>
      <!-- cross_attn: 0.134 -> 127 -->
      <rect x="145" y="73" width="50" height="127" fill="#C74634" rx="3"/>
      <text x="170" y="218" text-anchor="middle" fill="#94a3b8" font-size="10">cross_attn</text>
      <text x="170" y="68" text-anchor="middle" fill="#e2e8f0" font-size="10">0.134</text>
      <!-- decoder: 0.097 -> 92 -->
      <rect x="215" y="108" width="50" height="92" fill="#38bdf8" rx="3"/>
      <text x="240" y="218" text-anchor="middle" fill="#94a3b8" font-size="10">decoder</text>
      <text x="240" y="103" text-anchor="middle" fill="#e2e8f0" font-size="10">0.097</text>
      <!-- lora_A: 0.041 -> 39 -->
      <rect x="285" y="161" width="50" height="39" fill="#4ade80" rx="3"/>
      <text x="310" y="218" text-anchor="middle" fill="#94a3b8" font-size="10">lora_A</text>
      <text x="310" y="156" text-anchor="middle" fill="#e2e8f0" font-size="10">0.041</text>
      <!-- lora_B: 0.028 -> 27 -->
      <rect x="355" y="173" width="50" height="27" fill="#4ade80" rx="3"/>
      <text x="380" y="218" text-anchor="middle" fill="#94a3b8" font-size="10">lora_B</text>
      <text x="380" y="168" text-anchor="middle" fill="#e2e8f0" font-size="10">0.028</text>
    </svg>
    <div style="margin-top:0.5rem">
      <span class="tag">base model frozen</span>
      <span class="tag green">lora_A healthy</span>
      <span class="tag green">lora_B healthy</span>
    </div>
  </div>

  <!-- LoRA Gradient Isolation -->
  <div class="card">
    <h2>LoRA Gradient Isolation</h2>
    <svg width="100%" viewBox="0 0 420 240" xmlns="http://www.w3.org/2000/svg">
      <!-- background bands -->
      <rect x="60" y="10" width="350" height="190" fill="#0f172a" rx="4"/>
      <!-- frozen zone label -->
      <rect x="60" y="10" width="350" height="110" fill="#1a2744" rx="4"/>
      <text x="235" y="30" text-anchor="middle" fill="#475569" font-size="11">BASE MODEL (FROZEN — grad=0)</text>
      <!-- trainable zone -->
      <rect x="60" y="130" width="350" height="70" fill="#14291a" rx="4"/>
      <text x="235" y="148" text-anchor="middle" fill="#4ade80" font-size="11">LoRA ADAPTERS (TRAINABLE)</text>
      <!-- encoder grad line (flat at 0 in frozen zone) -->
      <polyline points="70,80 150,80 230,80 310,80 400,80" fill="none" stroke="#475569" stroke-width="2" stroke-dasharray="4,3"/>
      <text x="402" y="83" fill="#475569" font-size="9">encoder</text>
      <!-- cross_attn grad line -->
      <polyline points="70,95 150,95 230,95 310,95 400,95" fill="none" stroke="#475569" stroke-width="2" stroke-dasharray="4,3"/>
      <text x="402" y="98" fill="#475569" font-size="9">cross_attn</text>
      <!-- decoder grad line -->
      <polyline points="70,110 150,110 230,110 310,110 400,110" fill="none" stroke="#475569" stroke-width="2" stroke-dasharray="4,3"/>
      <text x="402" y="113" fill="#475569" font-size="9">decoder</text>
      <!-- lora_A active grad -->
      <polyline points="70,185 110,182 150,178 190,175 230,172 270,170 310,168 350,166 400,163" fill="none" stroke="#4ade80" stroke-width="2"/>
      <text x="402" y="166" fill="#4ade80" font-size="9">lora_A</text>
      <!-- lora_B active grad -->
      <polyline points="70,192 110,190 150,187 190,184 230,182 270,180 310,178 350,176 400,174" fill="none" stroke="#38bdf8" stroke-width="2"/>
      <text x="402" y="177" fill="#38bdf8" font-size="9">lora_B</text>
      <!-- x axis -->
      <line x1="60" y1="205" x2="410" y2="205" stroke="#334155" stroke-width="1"/>
      <text x="60" y="218" fill="#94a3b8" font-size="9">step 0</text>
      <text x="370" y="218" fill="#94a3b8" font-size="9">step 5000</text>
    </svg>
    <div style="margin-top:0.5rem">
      <span class="tag red">3 frozen layers</span>
      <span class="tag green">2 LoRA layers active</span>
    </div>
  </div>

  <!-- Gradient Health Trend -->
  <div class="card full">
    <h2>Gradient Health Trend — 5000 Steps</h2>
    <svg width="100%" viewBox="0 0 860 200" xmlns="http://www.w3.org/2000/svg">
      <line x1="50" y1="10" x2="50" y2="170" stroke="#334155" stroke-width="1"/>
      <line x1="50" y1="170" x2="850" y2="170" stroke="#334155" stroke-width="1"/>
      <!-- y labels -->
      <text x="45" y="170" text-anchor="end" fill="#94a3b8" font-size="9">0</text>
      <text x="45" y="130" text-anchor="end" fill="#94a3b8" font-size="9">0.05</text>
      <text x="45" y="90" text-anchor="end" fill="#94a3b8" font-size="9">0.10</text>
      <text x="45" y="50" text-anchor="end" fill="#94a3b8" font-size="9">0.15</text>
      <text x="45" y="15" text-anchor="end" fill="#94a3b8" font-size="9">0.20</text>
      <line x1="50" y1="130" x2="850" y2="130" stroke="#1e293b" stroke-width="1" stroke-dasharray="3,3"/>
      <line x1="50" y1="90" x2="850" y2="90" stroke="#1e293b" stroke-width="1" stroke-dasharray="3,3"/>
      <line x1="50" y1="50" x2="850" y2="50" stroke="#1e293b" stroke-width="1" stroke-dasharray="3,3"/>
      <!-- encoder trend (decaying from 0.182) -->
      <polyline points="55,27 140,35 225,44 310,55 395,65 480,76 565,83 650,88 735,91 820,93"
        fill="none" stroke="#38bdf8" stroke-width="2"/>
      <!-- cross_attn trend -->
      <polyline points="55,54 140,63 225,72 310,82 395,91 480,98 565,104 650,108 735,111 820,113"
        fill="none" stroke="#C74634" stroke-width="2"/>
      <!-- decoder trend -->
      <polyline points="55,78 140,87 225,95 310,103 395,110 480,116 565,120 650,124 735,127 820,129"
        fill="none" stroke="#f59e0b" stroke-width="2"/>
      <!-- lora_A trend (stable low) -->
      <polyline points="55,141 140,143 225,144 310,145 395,146 480,146 565,147 650,147 735,148 820,148"
        fill="none" stroke="#4ade80" stroke-width="2"/>
      <!-- lora_B trend -->
      <polyline points="55,152 140,154 225,155 310,156 395,157 480,157 565,158 650,158 735,158 820,159"
        fill="none" stroke="#a78bfa" stroke-width="2"/>
      <!-- x labels -->
      <text x="55" y="185" fill="#94a3b8" font-size="9">0</text>
      <text x="215" y="185" fill="#94a3b8" font-size="9">1000</text>
      <text x="390" y="185" fill="#94a3b8" font-size="9">2500</text>
      <text x="795" y="185" fill="#94a3b8" font-size="9">5000</text>
      <!-- legend -->
      <rect x="55" y="190" width="10" height="3" fill="#38bdf8"/>
      <text x="70" y="197" fill="#94a3b8" font-size="9">encoder</text>
      <rect x="130" y="190" width="10" height="3" fill="#C74634"/>
      <text x="145" y="197" fill="#94a3b8" font-size="9">cross_attn</text>
      <rect x="220" y="190" width="10" height="3" fill="#f59e0b"/>
      <text x="235" y="197" fill="#94a3b8" font-size="9">decoder</text>
      <rect x="295" y="190" width="10" height="3" fill="#4ade80"/>
      <text x="310" y="197" fill="#94a3b8" font-size="9">lora_A</text>
      <rect x="355" y="190" width="10" height="3" fill="#a78bfa"/>
      <text x="370" y="197" fill="#94a3b8" font-size="9">lora_B</text>
    </svg>
    <div class="stats-row">
      <div><div class="stat">0.028</div><div class="stat-label">lora_B final norm</div></div>
      <div><div class="stat">0.041</div><div class="stat-label">lora_A final norm</div></div>
      <div><div class="stat">-84%</div><div class="stat-label">encoder norm decay</div></div>
      <div><div class="stat">healthy</div><div class="stat-label">gradient flow status</div></div>
    </div>
  </div>
</div>
</body>
</html>
"""

if USE_FASTAPI:
    app = FastAPI(title="Policy Gradient Visualizer V2")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return HTML

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "policy_gradient_visualizer_v2", "port": 8908}

    @app.get("/api/gradient-norms")
    def gradient_norms():
        layers = ["encoder", "cross_attn", "decoder", "lora_A", "lora_B"]
        frozen = [True, True, True, False, False]
        base_norms = [0.182, 0.134, 0.097, 0.041, 0.028]
        return {
            "layers": [
                {"name": l, "frozen": f, "norm": n}
                for l, f, n in zip(layers, frozen, base_norms)
            ]
        }

    @app.get("/api/health-trend")
    def health_trend():
        steps = list(range(0, 5001, 500))
        layers = {
            "encoder": [round(0.182 * math.exp(-0.0004 * s), 4) for s in steps],
            "cross_attn": [round(0.134 * math.exp(-0.0003 * s), 4) for s in steps],
            "decoder": [round(0.097 * math.exp(-0.0002 * s), 4) for s in steps],
            "lora_A": [round(0.041 + 0.001 * math.sin(s / 400), 4) for s in steps],
            "lora_B": [round(0.028 + 0.0007 * math.sin(s / 500), 4) for s in steps],
        }
        return {"steps": steps, "norms": layers}

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
        uvicorn.run(app, host="0.0.0.0", port=8908)
    else:
        print("[policy_gradient_visualizer_v2] FastAPI unavailable — serving on port 8908 via HTTPServer")
        HTTPServer(("0.0.0.0", 8908), Handler).serve_forever()
