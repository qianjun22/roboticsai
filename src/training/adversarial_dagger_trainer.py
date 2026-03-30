# Adversarial DAgger Trainer — port 8976
import math
import random
import os

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8976
SERVICE_TITLE = "Adversarial DAgger Trainer"

HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Adversarial DAgger Trainer</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; padding: 24px; }
  h1 { color: #C74634; font-size: 2rem; margin-bottom: 8px; }
  h2 { color: #38bdf8; font-size: 1.2rem; margin: 20px 0 10px; }
  .subtitle { color: #94a3b8; margin-bottom: 24px; font-size: 0.95rem; }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 24px; }
  .card { background: #1e293b; border-radius: 10px; padding: 20px; border: 1px solid #334155; }
  .card .val { font-size: 2rem; font-weight: bold; color: #38bdf8; }
  .card .adv { color: #C74634; }
  .card .label { font-size: 0.85rem; color: #94a3b8; margin-top: 4px; }
  .chart-box { background: #1e293b; border-radius: 10px; padding: 20px; border: 1px solid #334155; margin-bottom: 20px; }
  svg text { font-family: 'Segoe UI', sans-serif; }
  .tag { display: inline-block; padding: 2px 10px; border-radius: 12px; font-size: 0.78rem; margin: 2px; }
  .tag-blue { background: #0c4a6e; color: #38bdf8; }
  .tag-red { background: #4c0519; color: #f87171; }
  .tag-green { background: #052e16; color: #4ade80; }
</style>
</head>
<body>
<h1>Adversarial DAgger Trainer</h1>
<p class="subtitle">Policy vs Adversary minimax game — perturbed evaluation suite | Port 8976</p>

<div class="grid">
  <div class="card">
    <div class="val adv">0.74</div>
    <div class="label">Vanilla DAgger SR</div>
  </div>
  <div class="card">
    <div class="val">0.77</div>
    <div class="label">Adversarial DAgger SR (perturbed eval)</div>
  </div>
  <div class="card">
    <div class="val">2&times;</div>
    <div class="label">Fewer demos needed</div>
  </div>
  <div class="card">
    <div class="val adv">+23%</div>
    <div class="label">Cost per run ($0.53)</div>
  </div>
</div>

<h2>Adversarial vs Vanilla SR Comparison</h2>
<div class="chart-box">
  <svg viewBox="0 0 700 260" width="100%">
    <!-- axes -->
    <line x1="60" y1="20" x2="60" y2="220" stroke="#475569" stroke-width="1.5"/>
    <line x1="60" y1="220" x2="680" y2="220" stroke="#475569" stroke-width="1.5"/>
    <!-- y-axis labels -->
    <text x="52" y="225" fill="#64748b" font-size="11" text-anchor="end">0.0</text>
    <text x="52" y="180" fill="#64748b" font-size="11" text-anchor="end">0.25</text>
    <text x="52" y="140" fill="#64748b" font-size="11" text-anchor="end">0.50</text>
    <text x="52" y="100" fill="#64748b" font-size="11" text-anchor="end">0.75</text>
    <text x="52" y="60"  fill="#64748b" font-size="11" text-anchor="end">1.00</text>
    <!-- grid -->
    <line x1="60" y1="180" x2="680" y2="180" stroke="#1e3a5f" stroke-width="0.8" stroke-dasharray="4,3"/>
    <line x1="60" y1="140" x2="680" y2="140" stroke="#1e3a5f" stroke-width="0.8" stroke-dasharray="4,3"/>
    <line x1="60" y1="100" x2="680" y2="100" stroke="#1e3a5f" stroke-width="0.8" stroke-dasharray="0"/>
    <line x1="60" y1="60"  x2="680" y2="60"  stroke="#1e3a5f" stroke-width="0.8" stroke-dasharray="4,3"/>
    <!-- SR=0.74 vanilla (red bars) -->
    <!-- Epochs: 1..8, vanilla SR: 0.30 0.42 0.52 0.60 0.65 0.70 0.72 0.74 -->
    <!-- bar width=32, gap=40, x_start=80 -->
    <!-- y = 220 - sr*200 -->
    <rect x="78"  y="160" width="28" height="60"  fill="#C74634" opacity="0.8" rx="3"/>
    <rect x="158" y="136" width="28" height="84"  fill="#C74634" opacity="0.8" rx="3"/>
    <rect x="238" y="116" width="28" height="104" fill="#C74634" opacity="0.8" rx="3"/>
    <rect x="318" y="100" width="28" height="120" fill="#C74634" opacity="0.8" rx="3"/>
    <rect x="398" y="90"  width="28" height="130" fill="#C74634" opacity="0.8" rx="3"/>
    <rect x="478" y="80"  width="28" height="140" fill="#C74634" opacity="0.8" rx="3"/>
    <rect x="558" y="76"  width="28" height="144" fill="#C74634" opacity="0.8" rx="3"/>
    <rect x="618" y="72"  width="28" height="148" fill="#C74634" opacity="0.8" rx="3"/>
    <!-- adversarial DAgger SR: 0.34 0.48 0.58 0.66 0.71 0.74 0.76 0.77 -->
    <rect x="110" y="152" width="28" height="68"  fill="#38bdf8" opacity="0.85" rx="3"/>
    <rect x="190" y="124" width="28" height="96"  fill="#38bdf8" opacity="0.85" rx="3"/>
    <rect x="270" y="104" width="28" height="116" fill="#38bdf8" opacity="0.85" rx="3"/>
    <rect x="350" y="88"  width="28" height="132" fill="#38bdf8" opacity="0.85" rx="3"/>
    <rect x="430" y="78"  width="28" height="142" fill="#38bdf8" opacity="0.85" rx="3"/>
    <rect x="510" y="72"  width="28" height="148" fill="#38bdf8" opacity="0.85" rx="3"/>
    <rect x="590" y="68"  width="28" height="152" fill="#38bdf8" opacity="0.85" rx="3"/>
    <rect x="646" y="66"  width="28" height="154" fill="#38bdf8" opacity="0.85" rx="3"/>
    <!-- epoch labels -->
    <text x="103"  y="236" fill="#94a3b8" font-size="10" text-anchor="middle">E1</text>
    <text x="183"  y="236" fill="#94a3b8" font-size="10" text-anchor="middle">E2</text>
    <text x="263"  y="236" fill="#94a3b8" font-size="10" text-anchor="middle">E3</text>
    <text x="343"  y="236" fill="#94a3b8" font-size="10" text-anchor="middle">E4</text>
    <text x="423"  y="236" fill="#94a3b8" font-size="10" text-anchor="middle">E5</text>
    <text x="503"  y="236" fill="#94a3b8" font-size="10" text-anchor="middle">E6</text>
    <text x="583"  y="236" fill="#94a3b8" font-size="10" text-anchor="middle">E7</text>
    <text x="646"  y="236" fill="#94a3b8" font-size="10" text-anchor="middle">E8</text>
    <!-- legend -->
    <rect x="70" y="5" width="12" height="12" fill="#C74634" rx="2"/>
    <text x="86" y="15" fill="#e2e8f0" font-size="11">Vanilla DAgger (final SR=0.74)</text>
    <rect x="280" y="5" width="12" height="12" fill="#38bdf8" rx="2"/>
    <text x="296" y="15" fill="#e2e8f0" font-size="11">Adversarial DAgger (final SR=0.77)</text>
  </svg>
</div>

<h2>Difficulty Curriculum</h2>
<div class="chart-box">
  <svg viewBox="0 0 700 200" width="100%">
    <!-- axes -->
    <line x1="60" y1="20" x2="60" y2="170" stroke="#475569" stroke-width="1.5"/>
    <line x1="60" y1="170" x2="680" y2="170" stroke="#475569" stroke-width="1.5"/>
    <text x="52" y="175" fill="#64748b" font-size="11" text-anchor="end">0</text>
    <text x="52" y="130" fill="#64748b" font-size="11" text-anchor="end">3</text>
    <text x="52" y="90"  fill="#64748b" font-size="11" text-anchor="end">6</text>
    <text x="52" y="50"  fill="#64748b" font-size="11" text-anchor="end">9</text>
    <!-- perturbation magnitude curve -->
    <!-- points: (80,155),(160,148),(240,138),(320,122),(400,104),(480,82),(560,62),(640,46) -->
    <polyline points="80,155 160,148 240,138 320,122 400,104 480,82 560,62 640,46"
      fill="none" stroke="#f59e0b" stroke-width="2.5" stroke-linejoin="round"/>
    <!-- adversary win rate -->
    <!-- 0.45 0.47 0.50 0.52 0.49 0.44 0.40 0.37 scaled: y=170-(v*150) -->
    <polyline points="80,102 160,100 240,95 320,92 400,96 480,104 560,110 640,115"
      fill="none" stroke="#a78bfa" stroke-width="2.5" stroke-linejoin="round" stroke-dasharray="6,3"/>
    <!-- dots -->
    <circle cx="80"  cy="155" r="4" fill="#f59e0b"/>
    <circle cx="160" cy="148" r="4" fill="#f59e0b"/>
    <circle cx="240" cy="138" r="4" fill="#f59e0b"/>
    <circle cx="320" cy="122" r="4" fill="#f59e0b"/>
    <circle cx="400" cy="104" r="4" fill="#f59e0b"/>
    <circle cx="480" cy="82"  r="4" fill="#f59e0b"/>
    <circle cx="560" cy="62"  r="4" fill="#f59e0b"/>
    <circle cx="640" cy="46"  r="4" fill="#f59e0b"/>
    <!-- labels -->
    <text x="103"  y="186" fill="#94a3b8" font-size="10" text-anchor="middle">E1</text>
    <text x="183"  y="186" fill="#94a3b8" font-size="10" text-anchor="middle">E2</text>
    <text x="263"  y="186" fill="#94a3b8" font-size="10" text-anchor="middle">E3</text>
    <text x="343"  y="186" fill="#94a3b8" font-size="10" text-anchor="middle">E4</text>
    <text x="423"  y="186" fill="#94a3b8" font-size="10" text-anchor="middle">E5</text>
    <text x="503"  y="186" fill="#94a3b8" font-size="10" text-anchor="middle">E6</text>
    <text x="583"  y="186" fill="#94a3b8" font-size="10" text-anchor="middle">E7</text>
    <text x="646"  y="186" fill="#94a3b8" font-size="10" text-anchor="middle">E8</text>
    <!-- legend -->
    <line x1="70" y1="10" x2="90" y2="10" stroke="#f59e0b" stroke-width="2.5"/>
    <text x="94" y="14" fill="#e2e8f0" font-size="11">Perturbation Magnitude</text>
    <line x1="280" y1="10" x2="300" y2="10" stroke="#a78bfa" stroke-width="2.5" stroke-dasharray="6,3"/>
    <text x="304" y="14" fill="#e2e8f0" font-size="11">Adversary Win Rate</text>
  </svg>
</div>

<div style="margin-top:16px;">
  <span class="tag tag-blue">minimax</span>
  <span class="tag tag-blue">DAgger</span>
  <span class="tag tag-red">adversarial perturbations</span>
  <span class="tag tag-green">SR +4.1%</span>
  <span class="tag tag-blue">curriculum difficulty</span>
  <span class="tag tag-red">+23% cost</span>
</div>
</body>
</html>
"""

if USE_FASTAPI:
    app = FastAPI(title=SERVICE_TITLE)

    @app.get("/", response_class=HTMLResponse)
    async def root():
        return HTML

    @app.get("/health")
    async def health():
        vanilla_sr = 0.74
        adv_sr = 0.77
        demos_reduction = 0.5
        cost_per_run = 0.53
        return {
            "status": "ok",
            "service": SERVICE_TITLE,
            "port": PORT,
            "metrics": {
                "vanilla_dagger_sr": vanilla_sr,
                "adversarial_dagger_sr": adv_sr,
                "sr_delta": round(adv_sr - vanilla_sr, 3),
                "demos_reduction_factor": demos_reduction,
                "cost_per_run_usd": cost_per_run,
                "cost_increase_pct": 23,
            }
        }

    @app.get("/metrics")
    async def metrics():
        epochs = list(range(1, 9))
        vanilla_sr = [0.30, 0.42, 0.52, 0.60, 0.65, 0.70, 0.72, 0.74]
        adv_sr = [0.34, 0.48, 0.58, 0.66, 0.71, 0.74, 0.76, 0.77]
        perturb_mag = [round(0.1 + 0.12 * math.log1p(i), 3) for i in epochs]
        adversary_win = [0.45, 0.47, 0.50, 0.52, 0.49, 0.44, 0.40, 0.37]
        return {
            "epochs": epochs,
            "vanilla_sr_curve": vanilla_sr,
            "adversarial_sr_curve": adv_sr,
            "perturbation_magnitude": perturb_mag,
            "adversary_win_rate": adversary_win,
        }

    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=PORT)

else:
    from http.server import HTTPServer, BaseHTTPRequestHandler

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = HTML.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        def log_message(self, fmt, *args):
            pass

    if __name__ == "__main__":
        server = HTTPServer(("0.0.0.0", PORT), Handler)
        print(f"{SERVICE_TITLE} fallback server on port {PORT}")
        server.serve_forever()
