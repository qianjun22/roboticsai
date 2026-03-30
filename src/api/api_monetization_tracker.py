"""API Monetization Tracker — port 8959"""
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
<title>API Monetization Tracker</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; padding: 24px; }
  h1 { color: #C74634; font-size: 2rem; margin-bottom: 4px; }
  h2 { color: #38bdf8; font-size: 1.1rem; margin: 20px 0 10px; }
  .subtitle { color: #94a3b8; font-size: 0.9rem; margin-bottom: 24px; }
  .grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; }
  .card { background: #1e293b; border-radius: 10px; padding: 20px; }
  .card.half { grid-column: span 1; }
  .card.full { grid-column: 1 / -1; }
  .card.two { grid-column: span 2; }
  .stat { font-size: 2rem; font-weight: 700; color: #38bdf8; }
  .stat.red { color: #C74634; }
  .stat.green { color: #34d399; }
  .label { font-size: 0.8rem; color: #94a3b8; margin-top: 2px; }
  .badge { display: inline-block; background: #C74634; color: #fff; border-radius: 4px; padding: 2px 8px; font-size: 0.75rem; margin-left: 8px; }
  .tier-row { display: flex; justify-content: space-between; align-items: center; padding: 10px 0; border-bottom: 1px solid #0f172a; }
  .tier-row:last-child { border-bottom: none; }
  .tier-name { font-weight: 600; font-size: 0.95rem; }
  .tier-price { color: #38bdf8; font-weight: 700; }
  .tier-margin { font-size: 0.85rem; }
  svg text { font-family: 'Segoe UI', sans-serif; }
</style>
</head>
<body>
<h1>API Monetization Tracker</h1>
<p class="subtitle">Per-tier API pricing &amp; revenue analytics &nbsp;|&nbsp; Port 8959 &nbsp;<span class="badge">+34%/mo growth</span></p>

<div class="grid">
  <!-- KPI cards -->
  <div class="card half">
    <div class="stat">$0.012</div>
    <div class="label">Starter — per API call</div>
  </div>
  <div class="card half">
    <div class="stat">$0.009</div>
    <div class="label">Growth — per API call</div>
  </div>
  <div class="card half">
    <div class="stat">$0.006</div>
    <div class="label">Scale — per API call</div>
  </div>

  <!-- Usage growth chart -->
  <div class="card two">
    <h2>Monthly API Call Volume — +34%/mo Growth</h2>
    <svg width="100%" viewBox="0 0 500 200" xmlns="http://www.w3.org/2000/svg">
      <!-- axes -->
      <line x1="50" y1="10" x2="50" y2="160" stroke="#334155" stroke-width="1"/>
      <line x1="50" y1="160" x2="490" y2="160" stroke="#334155" stroke-width="1"/>
      <!-- gridlines -->
      <line x1="50" y1="40" x2="490" y2="40" stroke="#1e293b" stroke-width="1" stroke-dasharray="4,4"/>
      <line x1="50" y1="80" x2="490" y2="80" stroke="#1e293b" stroke-width="1" stroke-dasharray="4,4"/>
      <line x1="50" y1="120" x2="490" y2="120" stroke="#1e293b" stroke-width="1" stroke-dasharray="4,4"/>
      <!-- y-axis labels -->
      <text x="44" y="165" fill="#64748b" font-size="10" text-anchor="end">0</text>
      <text x="44" y="125" fill="#64748b" font-size="10" text-anchor="end">500K</text>
      <text x="44" y="85" fill="#64748b" font-size="10" text-anchor="end">1M</text>
      <text x="44" y="45" fill="#64748b" font-size="10" text-anchor="end">1.5M</text>
      <text x="44" y="15" fill="#64748b" font-size="10" text-anchor="end">2M</text>
      <!-- bars: 6 months, volumes roughly following 1.34^n growth -->
      <!-- month labels -->
      <text x="80"  y="175" fill="#64748b" font-size="10" text-anchor="middle">Oct</text>
      <text x="148" y="175" fill="#64748b" font-size="10" text-anchor="middle">Nov</text>
      <text x="216" y="175" fill="#64748b" font-size="10" text-anchor="middle">Dec</text>
      <text x="284" y="175" fill="#64748b" font-size="10" text-anchor="middle">Jan</text>
      <text x="352" y="175" fill="#64748b" font-size="10" text-anchor="middle">Feb</text>
      <text x="420" y="175" fill="#64748b" font-size="10" text-anchor="middle">Mar</text>
      <!-- bar heights: scale 0-2M → 0-150px. volumes: 280K,376K,504K,675K,904K,1212K -->
      <rect x="60"  y="139" width="40" height="21"  fill="#38bdf8" opacity="0.6" rx="3"/>
      <rect x="128" y="132" width="40" height="28"  fill="#38bdf8" opacity="0.65" rx="3"/>
      <rect x="196" y="122" width="40" height="38"  fill="#38bdf8" opacity="0.7" rx="3"/>
      <rect x="264" y="110" width="40" height="50"  fill="#38bdf8" opacity="0.8" rx="3"/>
      <rect x="332" y="92"  width="40" height="68"  fill="#C74634" opacity="0.85" rx="3"/>
      <rect x="400" y="69"  width="40" height="91"  fill="#C74634" opacity="0.9" rx="3"/>
      <!-- value labels -->
      <text x="80"  y="136" fill="#7dd3fc" font-size="9" text-anchor="middle">280K</text>
      <text x="148" y="129" fill="#7dd3fc" font-size="9" text-anchor="middle">376K</text>
      <text x="216" y="119" fill="#7dd3fc" font-size="9" text-anchor="middle">504K</text>
      <text x="284" y="107" fill="#7dd3fc" font-size="9" text-anchor="middle">675K</text>
      <text x="352" y="89"  fill="#fca5a5" font-size="9" text-anchor="middle">904K</text>
      <text x="420" y="66"  fill="#fca5a5" font-size="9" text-anchor="middle">1.21M</text>
    </svg>
  </div>

  <!-- Gross margin card -->
  <div class="card half">
    <h2>Gross Margin by Tier</h2>
    <div class="tier-row">
      <span class="tier-name" style="color:#38bdf8;">Starter</span>
      <span class="tier-price">$0.012/call</span>
      <span class="tier-margin" style="color:#34d399;">52% GM</span>
    </div>
    <div class="tier-row">
      <span class="tier-name" style="color:#818cf8;">Growth</span>
      <span class="tier-price">$0.009/call</span>
      <span class="tier-margin" style="color:#34d399;">71% GM</span>
    </div>
    <div class="tier-row">
      <span class="tier-name" style="color:#C74634;">Scale</span>
      <span class="tier-price">$0.006/call</span>
      <span class="tier-margin" style="color:#34d399;">83% GM</span>
    </div>
  </div>

  <!-- Revenue breakdown chart -->
  <div class="card full">
    <h2>Revenue Breakdown — March 2026</h2>
    <svg width="100%" viewBox="0 0 620 180" xmlns="http://www.w3.org/2000/svg">
      <!-- stacked horizontal bar -->
      <!-- Total monthly revenue estimate: 1.21M calls split ~40% Starter, 35% Growth, 25% Scale -->
      <!-- Starter: 484K * $0.012 = $5,808  Growth: 423.5K * $0.009 = $3,812  Scale: 302.5K * $0.006 = $1,815 -->
      <!-- Total ~$11,435. Overage (Machina): $340 -->
      <!-- bar width 540px total -->
      <rect x="60" y="40" width="274" height="50" fill="#38bdf8" rx="3"/>
      <text x="197" y="70" fill="#0f172a" font-size="13" text-anchor="middle" font-weight="700">Starter $5,808</text>
      <rect x="334" y="40" width="180" height="50" fill="#818cf8" rx="3"/>
      <text x="424" y="70" fill="#fff" font-size="13" text-anchor="middle" font-weight="700">Growth $3,812</text>
      <rect x="514" y="40" width="86" height="50" fill="#C74634" rx="3"/>
      <text x="557" y="70" fill="#fff" font-size="11" text-anchor="middle" font-weight="700">Scale $1,815</text>
      <!-- overage bar below -->
      <rect x="60" y="105" width="16" height="30" fill="#f59e0b" rx="3"/>
      <text x="82" y="125" fill="#fbbf24" font-size="12" font-weight="600">Machina overage: $340</text>
      <!-- total -->
      <text x="60" y="160" fill="#94a3b8" font-size="12">Total MRR (API): $11,775 &nbsp;|&nbsp; Overage partner: Machina ($340) &nbsp;|&nbsp; Blended GM: 70.6%</text>
    </svg>
  </div>
</div>
</body>
</html>
"""

if USE_FASTAPI:
    app = FastAPI(title="API Monetization Tracker")

    @app.get("/", response_class=HTMLResponse)
    async def index():
        return HTML

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "api_monetization_tracker", "port": 8959}

    @app.get("/api/pricing")
    async def pricing():
        return {
            "tiers": [
                {"name": "Starter", "price_per_call": 0.012, "gross_margin": 0.52},
                {"name": "Growth",  "price_per_call": 0.009, "gross_margin": 0.71},
                {"name": "Scale",   "price_per_call": 0.006, "gross_margin": 0.83},
            ],
            "monthly_growth_rate": 0.34,
            "machina_overage_usd": 340,
            "march_mrr_usd": 11775,
            "blended_gm": 0.706,
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
        uvicorn.run(app, host="0.0.0.0", port=8959)
    else:
        print("FastAPI unavailable — serving fallback on :8959")
        HTTPServer(("0.0.0.0", 8959), Handler).serve_forever()
