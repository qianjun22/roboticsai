"""Reward Shaping Studio — port 8958"""
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
<title>Reward Shaping Studio</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; padding: 24px; }
  h1 { color: #C74634; font-size: 2rem; margin-bottom: 4px; }
  h2 { color: #38bdf8; font-size: 1.1rem; margin: 20px 0 10px; }
  .subtitle { color: #94a3b8; font-size: 0.9rem; margin-bottom: 24px; }
  .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
  .card { background: #1e293b; border-radius: 10px; padding: 20px; }
  .card.full { grid-column: 1 / -1; }
  .stat { font-size: 2rem; font-weight: 700; color: #38bdf8; }
  .label { font-size: 0.8rem; color: #94a3b8; margin-top: 2px; }
  .badge { display: inline-block; background: #C74634; color: #fff; border-radius: 4px; padding: 2px 8px; font-size: 0.75rem; margin-left: 8px; }
  .bar-row { display: flex; align-items: center; margin: 8px 0; gap: 10px; }
  .bar-label { width: 130px; font-size: 0.85rem; color: #cbd5e1; }
  .bar-bg { flex: 1; background: #0f172a; border-radius: 4px; height: 18px; overflow: hidden; }
  .bar-fill { height: 100%; border-radius: 4px; display: flex; align-items: center; padding-left: 6px; font-size: 0.75rem; font-weight: 600; color: #fff; }
  svg text { font-family: 'Segoe UI', sans-serif; }
</style>
</head>
<body>
<h1>Reward Shaping Studio</h1>
<p class="subtitle">Partner-configurable reward component builder &nbsp;|&nbsp; Port 8958 &nbsp;<span class="badge">Gold Tier</span></p>

<div class="grid">
  <!-- KPI cards -->
  <div class="card">
    <div class="stat">5</div>
    <div class="label">Reward Components</div>
  </div>
  <div class="card">
    <div class="stat">+18%</div>
    <div class="label">SR Lift vs Flat Reward</div>
  </div>

  <!-- Component contribution bars -->
  <div class="card full">
    <h2>Component Contribution to Success Rate</h2>
    <div class="bar-row">
      <div class="bar-label">task_success</div>
      <div class="bar-bg"><div class="bar-fill" style="width:52%;background:#C74634;">52%</div></div>
    </div>
    <div class="bar-row">
      <div class="bar-label">grasp_stability</div>
      <div class="bar-bg"><div class="bar-fill" style="width:21%;background:#38bdf8;">21%</div></div>
    </div>
    <div class="bar-row">
      <div class="bar-label">efficiency</div>
      <div class="bar-bg"><div class="bar-fill" style="width:14%;background:#818cf8;">14%</div></div>
    </div>
    <div class="bar-row">
      <div class="bar-label">safety</div>
      <div class="bar-bg"><div class="bar-fill" style="width:8%;background:#f59e0b;">8%</div></div>
    </div>
    <div class="bar-row">
      <div class="bar-label">smoothness</div>
      <div class="bar-bg"><div class="bar-fill" style="width:5%;background:#34d399;">5%</div></div>
    </div>
  </div>

  <!-- Reward vs SR heatmap (SVG) -->
  <div class="card full">
    <h2>Reward Weight vs Success Rate Heatmap</h2>
    <svg width="100%" viewBox="0 0 620 260" xmlns="http://www.w3.org/2000/svg">
      <!-- axes -->
      <line x1="60" y1="20" x2="60" y2="220" stroke="#334155" stroke-width="1"/>
      <line x1="60" y1="220" x2="600" y2="220" stroke="#334155" stroke-width="1"/>
      <!-- y-axis labels -->
      <text x="50" y="225" fill="#64748b" font-size="11" text-anchor="end">0%</text>
      <text x="50" y="175" fill="#64748b" font-size="11" text-anchor="end">25%</text>
      <text x="50" y="125" fill="#64748b" font-size="11" text-anchor="end">50%</text>
      <text x="50" y="75" fill="#64748b" font-size="11" text-anchor="end">75%</text>
      <text x="50" y="30" fill="#64748b" font-size="11" text-anchor="end">100%</text>
      <!-- x-axis labels -->
      <text x="62" y="236" fill="#64748b" font-size="11">0.0</text>
      <text x="172" y="236" fill="#64748b" font-size="11">0.25</text>
      <text x="282" y="236" fill="#64748b" font-size="11">0.50</text>
      <text x="392" y="236" fill="#64748b" font-size="11">0.75</text>
      <text x="502" y="236" fill="#64748b" font-size="11">1.0</text>
      <!-- axis titles -->
      <text x="330" y="255" fill="#94a3b8" font-size="12" text-anchor="middle">task_success weight</text>
      <text x="14" y="125" fill="#94a3b8" font-size="12" text-anchor="middle" transform="rotate(-90,14,125)">SR (%)</text>
      <!-- heatmap cells: 5 columns x 4 rows, color by SR value -->
      <!-- row 1: safety_weight=low -->
      <rect x="62" y="22" width="106" height="48" fill="#1e3a5f" opacity="0.85" rx="3"/>
      <text x="115" y="50" fill="#7dd3fc" font-size="13" text-anchor="middle" font-weight="600">31%</text>
      <rect x="172" y="22" width="106" height="48" fill="#1e4d8c" opacity="0.85" rx="3"/>
      <text x="225" y="50" fill="#93c5fd" font-size="13" text-anchor="middle" font-weight="600">44%</text>
      <rect x="282" y="22" width="106" height="48" fill="#1d4ed8" opacity="0.9" rx="3"/>
      <text x="335" y="50" fill="#bfdbfe" font-size="13" text-anchor="middle" font-weight="600">63%</text>
      <rect x="392" y="22" width="106" height="48" fill="#2563eb" opacity="0.9" rx="3"/>
      <text x="445" y="50" fill="#dbeafe" font-size="13" text-anchor="middle" font-weight="600">75%</text>
      <rect x="502" y="22" width="96" height="48" fill="#38bdf8" opacity="0.7" rx="3"/>
      <text x="550" y="50" fill="#fff" font-size="13" text-anchor="middle" font-weight="600">68%</text>
      <!-- row 2 -->
      <rect x="62" y="74" width="106" height="48" fill="#1e3a5f" opacity="0.7" rx="3"/>
      <text x="115" y="102" fill="#7dd3fc" font-size="13" text-anchor="middle" font-weight="600">28%</text>
      <rect x="172" y="74" width="106" height="48" fill="#1e4d8c" opacity="0.75" rx="3"/>
      <text x="225" y="102" fill="#93c5fd" font-size="13" text-anchor="middle" font-weight="600">41%</text>
      <rect x="282" y="74" width="106" height="48" fill="#1d4ed8" opacity="0.8" rx="3"/>
      <text x="335" y="102" fill="#bfdbfe" font-size="13" text-anchor="middle" font-weight="600">58%</text>
      <rect x="392" y="74" width="106" height="48" fill="#C74634" opacity="0.85" rx="3"/>
      <text x="445" y="102" fill="#fff" font-size="13" text-anchor="middle" font-weight="600">71%</text>
      <rect x="502" y="74" width="96" height="48" fill="#9f1239" opacity="0.7" rx="3"/>
      <text x="550" y="102" fill="#fecdd3" font-size="13" text-anchor="middle" font-weight="600">60%</text>
      <!-- row 3 -->
      <rect x="62" y="126" width="106" height="48" fill="#1e293b" opacity="0.9" rx="3"/>
      <text x="115" y="154" fill="#64748b" font-size="13" text-anchor="middle" font-weight="600">18%</text>
      <rect x="172" y="126" width="106" height="48" fill="#1e3a5f" opacity="0.8" rx="3"/>
      <text x="225" y="154" fill="#7dd3fc" font-size="13" text-anchor="middle" font-weight="600">33%</text>
      <rect x="282" y="126" width="106" height="48" fill="#1e4d8c" opacity="0.8" rx="3"/>
      <text x="335" y="154" fill="#93c5fd" font-size="13" text-anchor="middle" font-weight="600">49%</text>
      <rect x="392" y="126" width="106" height="48" fill="#1d4ed8" opacity="0.8" rx="3"/>
      <text x="445" y="154" fill="#bfdbfe" font-size="13" text-anchor="middle" font-weight="600">62%</text>
      <rect x="502" y="126" width="96" height="48" fill="#2563eb" opacity="0.7" rx="3"/>
      <text x="550" y="154" fill="#dbeafe" font-size="13" text-anchor="middle" font-weight="600">54%</text>
      <!-- row 4 -->
      <rect x="62" y="172" width="106" height="46" fill="#1e293b" opacity="0.7" rx="3"/>
      <text x="115" y="199" fill="#475569" font-size="13" text-anchor="middle" font-weight="600">9%</text>
      <rect x="172" y="172" width="106" height="46" fill="#1e293b" opacity="0.8" rx="3"/>
      <text x="225" y="199" fill="#64748b" font-size="13" text-anchor="middle" font-weight="600">22%</text>
      <rect x="282" y="172" width="106" height="46" fill="#1e3a5f" opacity="0.8" rx="3"/>
      <text x="335" y="199" fill="#7dd3fc" font-size="13" text-anchor="middle" font-weight="600">37%</text>
      <rect x="392" y="172" width="106" height="46" fill="#1e4d8c" opacity="0.8" rx="3"/>
      <text x="445" y="199" fill="#93c5fd" font-size="13" text-anchor="middle" font-weight="600">51%</text>
      <rect x="502" y="172" width="96" height="46" fill="#1d4ed8" opacity="0.7" rx="3"/>
      <text x="550" y="199" fill="#bfdbfe" font-size="13" text-anchor="middle" font-weight="600">46%</text>
      <!-- legend -->
      <text x="62" y="250" fill="#94a3b8" font-size="11">Color intensity = SR magnitude &nbsp;|&nbsp; Rows: safety_weight low→high &nbsp;|&nbsp; Optimal: task_success=0.75, safety=mid</text>
    </svg>
  </div>

  <!-- Gold tier config -->
  <div class="card full">
    <h2>Gold Tier — Partner-Configurable Weights</h2>
    <div style="display:flex;gap:16px;flex-wrap:wrap;margin-top:8px;">
      <div style="background:#0f172a;border-radius:8px;padding:12px 20px;">
        <div style="color:#C74634;font-weight:700;">task_success</div>
        <div style="color:#e2e8f0;font-size:1.3rem;font-weight:700;">0.52</div>
        <div style="color:#64748b;font-size:0.75rem;">range [0.3, 0.8]</div>
      </div>
      <div style="background:#0f172a;border-radius:8px;padding:12px 20px;">
        <div style="color:#38bdf8;font-weight:700;">grasp_stability</div>
        <div style="color:#e2e8f0;font-size:1.3rem;font-weight:700;">0.21</div>
        <div style="color:#64748b;font-size:0.75rem;">range [0.1, 0.4]</div>
      </div>
      <div style="background:#0f172a;border-radius:8px;padding:12px 20px;">
        <div style="color:#818cf8;font-weight:700;">efficiency</div>
        <div style="color:#e2e8f0;font-size:1.3rem;font-weight:700;">0.14</div>
        <div style="color:#64748b;font-size:0.75rem;">range [0.05, 0.3]</div>
      </div>
      <div style="background:#0f172a;border-radius:8px;padding:12px 20px;">
        <div style="color:#f59e0b;font-weight:700;">safety</div>
        <div style="color:#e2e8f0;font-size:1.3rem;font-weight:700;">0.08</div>
        <div style="color:#64748b;font-size:0.75rem;">range [0.05, 0.2]</div>
      </div>
      <div style="background:#0f172a;border-radius:8px;padding:12px 20px;">
        <div style="color:#34d399;font-weight:700;">smoothness</div>
        <div style="color:#e2e8f0;font-size:1.3rem;font-weight:700;">0.05</div>
        <div style="color:#64748b;font-size:0.75rem;">range [0.0, 0.15]</div>
      </div>
    </div>
  </div>
</div>
</body>
</html>
"""

if USE_FASTAPI:
    app = FastAPI(title="Reward Shaping Studio")

    @app.get("/", response_class=HTMLResponse)
    async def index():
        return HTML

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "reward_shaping_studio", "port": 8958}

    @app.get("/api/components")
    async def components():
        return {
            "components": [
                {"name": "task_success",   "weight": 0.52, "sr_contribution": 0.52},
                {"name": "grasp_stability","weight": 0.21, "sr_contribution": 0.21},
                {"name": "efficiency",     "weight": 0.14, "sr_contribution": 0.14},
                {"name": "safety",         "weight": 0.08, "sr_contribution": 0.08},
                {"name": "smoothness",     "weight": 0.05, "sr_contribution": 0.05},
            ],
            "sr_lift_vs_flat": 0.18,
            "tier": "Gold",
        }

else:
    from http.server import HTTPServer, BaseHTTPRequestHandler

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(HTML.encode())
        def log_message(self, *_):
            pass

if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8958)
    else:
        print("FastAPI unavailable — serving fallback on :8958")
        HTTPServer(("0.0.0.0", 8958), Handler).serve_forever()
