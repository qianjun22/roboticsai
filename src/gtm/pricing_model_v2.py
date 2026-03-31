"""Pricing Model V2 — value-based 3-tier + usage-based redesign.

Port: 10159
"""

import json
import sys
from datetime import datetime

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    _FASTAPI_AVAILABLE = True
except ImportError:
    _FASTAPI_AVAILABLE = False

PORT = 10159
SERVICE_NAME = "pricing_model_v2"

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Pricing Model V2</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; padding: 2rem; }
    h1 { color: #C74634; font-size: 1.8rem; margin-bottom: 0.4rem; }
    .subtitle { color: #38bdf8; font-size: 0.95rem; margin-bottom: 2rem; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-bottom: 2rem; }
    .card { background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 1.2rem; }
    .card .label { color: #94a3b8; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em; }
    .card .value { color: #38bdf8; font-size: 1.5rem; font-weight: 700; margin-top: 0.3rem; }
    .chart-section { background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 1.5rem; margin-bottom: 2rem; }
    .chart-section h2 { color: #C74634; font-size: 1.1rem; margin-bottom: 1rem; }
    .tiers { background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 1.5rem; }
    .tiers h2 { color: #C74634; font-size: 1.1rem; margin-bottom: 1rem; }
    .tier-row { display: flex; align-items: center; gap: 1rem; padding: 0.6rem 0; border-bottom: 1px solid #334155; }
    .tier-row:last-child { border-bottom: none; }
    .tier-name { color: #38bdf8; width: 100px; font-weight: 600; }
    .tier-price { color: #C74634; width: 120px; font-weight: 700; }
    .tier-gm { color: #4ade80; margin-left: auto; font-weight: 600; }
    .tier-desc { color: #94a3b8; font-size: 0.9rem; }
    footer { margin-top: 2rem; color: #475569; font-size: 0.8rem; }
  </style>
</head>
<body>
  <h1>Pricing Model V2</h1>
  <p class="subtitle">Value-Based 3-Tier + Usage-Based Redesign &mdash; Port {PORT}</p>

  <div class="grid">
    <div class="card"><div class="label">Model Version</div><div class="value">V2</div></div>
    <div class="card"><div class="label">Tiers</div><div class="value">3</div></div>
    <div class="card"><div class="label">Avg GM</div><div class="value">90%</div></div>
    <div class="card"><div class="label">ACV Range</div><div class="value">$60K–$150K</div></div>
  </div>

  <div class="chart-section">
    <h2>Gross Margin by Tier</h2>
    <svg viewBox="0 0 520 200" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:520px;display:block;">
      <!-- Axes -->
      <line x1="60" y1="10" x2="60" y2="160" stroke="#475569" stroke-width="1"/>
      <line x1="60" y1="160" x2="500" y2="160" stroke="#475569" stroke-width="1"/>
      <!-- Y labels -->
      <text x="50" y="164" fill="#94a3b8" font-size="11" text-anchor="end">0%</text>
      <text x="50" y="122" fill="#94a3b8" font-size="11" text-anchor="end">25%</text>
      <text x="50" y="80" fill="#94a3b8" font-size="11" text-anchor="end">50%</text>
      <text x="50" y="38" fill="#94a3b8" font-size="11" text-anchor="end">75%</text>
      <!-- Starter 87% -->
      <rect x="80" y="21" width="80" height="139" fill="#38bdf8" rx="3"/>
      <text x="120" y="17" fill="#e2e8f0" font-size="11" text-anchor="middle">87%</text>
      <text x="120" y="178" fill="#94a3b8" font-size="10" text-anchor="middle">Starter</text>
      <text x="120" y="190" fill="#94a3b8" font-size="10" text-anchor="middle">$60K/yr</text>
      <!-- Growth 89% -->
      <rect x="220" y="17" width="80" height="143" fill="#C74634" rx="3"/>
      <text x="260" y="13" fill="#e2e8f0" font-size="11" text-anchor="middle">89%</text>
      <text x="260" y="178" fill="#94a3b8" font-size="10" text-anchor="middle">Growth</text>
      <text x="260" y="190" fill="#94a3b8" font-size="10" text-anchor="middle">$83K/yr</text>
      <!-- Enterprise 93% -->
      <rect x="360" y="10" width="80" height="150" fill="#7c3aed" rx="3"/>
      <text x="400" y="6" fill="#e2e8f0" font-size="11" text-anchor="middle">93%</text>
      <text x="400" y="178" fill="#94a3b8" font-size="10" text-anchor="middle">Enterprise</text>
      <text x="400" y="190" fill="#94a3b8" font-size="10" text-anchor="middle">$150K/yr</text>
    </svg>
  </div>

  <div class="tiers">
    <h2>Tier Details</h2>
    <div class="tier-row">
      <span class="tier-name">Starter</span>
      <span class="tier-price">$60K / yr</span>
      <span class="tier-desc">1 robot, 1 skill, community support, 10K inferences/mo</span>
      <span class="tier-gm">GM 87%</span>
    </div>
    <div class="tier-row">
      <span class="tier-name">Growth</span>
      <span class="tier-price">$83K / yr</span>
      <span class="tier-desc">Up to 5 robots, 5 skills, SLA 99.5%, 100K inferences/mo</span>
      <span class="tier-gm">GM 89%</span>
    </div>
    <div class="tier-row">
      <span class="tier-name">Enterprise</span>
      <span class="tier-price">$150K / yr</span>
      <span class="tier-desc">Unlimited robots, custom skills, SLA 99.9%, dedicated GPU, 1M inferences/mo</span>
      <span class="tier-gm">GM 93%</span>
    </div>
  </div>

  <footer>OCI Robot Cloud &mdash; {SERVICE_NAME} &mdash; port {PORT} &mdash; {ts}</footer>
</body>
</html>
""".replace("{PORT}", str(PORT)).replace("{SERVICE_NAME}", SERVICE_NAME)


if _FASTAPI_AVAILABLE:
    app = FastAPI(title=SERVICE_NAME, version="2.0.0")

    @app.get("/health")
    def health():
        return JSONResponse({"status": "ok", "port": PORT, "service": SERVICE_NAME, "ts": datetime.utcnow().isoformat()})

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        html = DASHBOARD_HTML.replace("{ts}", datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"))
        return HTMLResponse(content=html)

    @app.get("/pricing/v2/quote")
    def pricing_quote(tier: str = "growth", robots: int = 1, inferences_per_month: int = 50000):
        tiers = {
            "starter": {"base_acv": 60000, "gm": 0.87, "max_robots": 1, "max_inferences": 10000},
            "growth":  {"base_acv": 83000, "gm": 0.89, "max_robots": 5,  "max_inferences": 100000},
            "enterprise": {"base_acv": 150000, "gm": 0.93, "max_robots": None, "max_inferences": 1000000},
        }
        t = tiers.get(tier.lower(), tiers["growth"])
        overage_inferences = max(0, inferences_per_month - t["max_inferences"]) if t["max_inferences"] else 0
        overage_charge = overage_inferences * 0.002  # $0.002 per extra inference
        total_acv = t["base_acv"] + overage_charge * 12
        return JSONResponse({
            "tier": tier,
            "robots": robots,
            "inferences_per_month": inferences_per_month,
            "base_acv_usd": t["base_acv"],
            "overage_annual_usd": round(overage_charge * 12, 2),
            "total_acv_usd": round(total_acv, 2),
            "gross_margin": t["gm"],
            "currency": "USD",
        })

    @app.get("/pricing/v2/calculator")
    def pricing_calculator():
        return JSONResponse({
            "model_version": "v2",
            "tiers": [
                {"name": "starter",    "acv_usd": 60000,  "gm": 0.87, "max_robots": 1,    "inferences_mo": 10000},
                {"name": "growth",     "acv_usd": 83000,  "gm": 0.89, "max_robots": 5,    "inferences_mo": 100000},
                {"name": "enterprise", "acv_usd": 150000, "gm": 0.93, "max_robots": None, "inferences_mo": 1000000},
            ],
            "overage_rate_per_inference_usd": 0.002,
            "usage_based_add_on": True,
        })

else:
    # Fallback: stdlib HTTPServer
    from http.server import HTTPServer, BaseHTTPRequestHandler

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/health":
                body = json.dumps({"status": "ok", "port": PORT, "service": SERVICE_NAME}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)
            else:
                html = DASHBOARD_HTML.replace("{ts}", datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")).encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(html)

        def log_message(self, fmt, *args):
            pass


if __name__ == "__main__":
    if _FASTAPI_AVAILABLE:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        print(f"FastAPI not available — starting stdlib fallback on port {PORT}")
        server = HTTPServer(("0.0.0.0", PORT), Handler)
        server.serve_forever()
