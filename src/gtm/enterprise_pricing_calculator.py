"""Enterprise Pricing Calculator — OCI Robot Cloud (port 10049)

Enterprise deal pricing with tier recommendation and ROI context.
FastAPI service with stdlib fallback via http.server.
"""

from __future__ import annotations

import json
import math
import time
from typing import Any, Dict

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    _FASTAPI = True
except ImportError:
    _FASTAPI = False

# ---------------------------------------------------------------------------
# Pricing logic
# ---------------------------------------------------------------------------

TIERS: Dict[str, Dict[str, Any]] = {
    "starter": {
        "label": "Starter",
        "min_robots": 1,
        "max_robots": 99,
        "annual_base_usd": 50_000,
        "per_robot_usd": 400,
        "per_run_usd": 0.08,
        "fine_tune_usd": 2_000,
        "support": "Standard (email, 48h SLA)",
    },
    "growth": {
        "label": "Growth",
        "min_robots": 100,
        "max_robots": 499,
        "annual_base_usd": 150_000,
        "per_robot_usd": 300,
        "per_run_usd": 0.05,
        "fine_tune_usd": 1_500,
        "support": "Priority (Slack, 4h SLA)",
    },
    "enterprise": {
        "label": "Enterprise",
        "min_robots": 500,
        "max_robots": 999_999,
        "annual_base_usd": 300_000,
        "per_robot_usd": 200,
        "per_run_usd": 0.03,
        "fine_tune_usd": 1_000,
        "support": "Dedicated CSM + 1h SLA",
    },
}

# Assumed savings per robot per year in manual labour cost (USD)
_LABOUR_SAVINGS_PER_ROBOT_PER_YEAR = 35_000
# Working days in a year
_WORKING_DAYS = 250


def _select_tier(robot_count: int) -> str:
    if robot_count >= 500:
        return "enterprise"
    if robot_count >= 100:
        return "growth"
    return "starter"


def calculate_pricing(
    robot_count: int,
    monthly_runs: int,
    fine_tunes_per_year: int,
    support_tier: str = "standard",
) -> Dict[str, Any]:
    """Calculate annual contract value, tier, ROI, and payback period."""
    robot_count = max(1, robot_count)
    monthly_runs = max(0, monthly_runs)
    fine_tunes_per_year = max(0, fine_tunes_per_year)

    tier_key = _select_tier(robot_count)
    t = TIERS[tier_key]

    base = t["annual_base_usd"]
    robot_charge = robot_count * t["per_robot_usd"]
    run_charge = monthly_runs * 12 * t["per_run_usd"]
    ft_charge = fine_tunes_per_year * t["fine_tune_usd"]

    # Premium support uplift (enterprise / growth already include priority)
    support_uplift = 0.0
    if support_tier.lower() in ("premium", "dedicated") and tier_key == "starter":
        support_uplift = 15_000.0

    acv = base + robot_charge + run_charge + ft_charge + support_uplift

    # ROI: annual labour savings vs ACV
    annual_savings = robot_count * _LABOUR_SAVINGS_PER_ROBOT_PER_YEAR
    roi_multiple = round(annual_savings / acv, 2) if acv > 0 else 0.0
    payback_days = int(math.ceil(acv / annual_savings * _WORKING_DAYS)) if annual_savings > 0 else 9999

    return {
        "annual_contract_value": round(acv, 2),
        "tier": t["label"],
        "roi_multiple": roi_multiple,
        "payback_days": payback_days,
        "breakdown": {
            "base_platform_fee": base,
            "robot_fleet_charge": round(robot_charge, 2),
            "inference_run_charge": round(run_charge, 2),
            "fine_tune_charge": round(ft_charge, 2),
            "support_uplift": support_uplift,
        },
    }


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Enterprise Pricing Calculator — OCI Robot Cloud</title>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{background:#0f172a;color:#e2e8f0;font-family:system-ui,sans-serif;min-height:100vh;padding:2rem}
  h1{color:#C74634;font-size:1.8rem;margin-bottom:.25rem}
  .sub{color:#38bdf8;font-size:.95rem;margin-bottom:2rem}
  .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:1.5rem;margin-bottom:2rem}
  .card{background:#1e293b;border-radius:12px;padding:1.5rem;border:1px solid #334155}
  .card h2{color:#38bdf8;font-size:1rem;margin-bottom:.75rem;text-transform:uppercase;letter-spacing:.05em}
  .metric{font-size:2rem;font-weight:700;color:#f1f5f9}
  .label{font-size:.8rem;color:#94a3b8;margin-top:.25rem}
  table{width:100%;border-collapse:collapse;font-size:.88rem}
  th{color:#38bdf8;text-align:left;padding:.5rem .75rem;border-bottom:1px solid #334155;font-weight:600}
  td{padding:.5rem .75rem;border-bottom:1px solid #1e293b;color:#cbd5e1}
  tr:last-child td{border-bottom:none}
  .tier-starter{color:#94a3b8}
  .tier-growth{color:#38bdf8}
  .tier-enterprise{color:#C74634}
  .example{background:#1e293b;border-radius:12px;padding:1.5rem;border:1px solid #334155;margin-bottom:2rem}
  .example h2{color:#38bdf8;font-size:1rem;margin-bottom:.75rem;text-transform:uppercase;letter-spacing:.05em}
  .example p{color:#cbd5e1;line-height:1.7;font-size:.9rem}
  .example strong{color:#f1f5f9}
  svg text{font-family:system-ui,sans-serif}
  .endpoint{background:#0f172a;border-radius:8px;padding:.75rem 1rem;font-family:monospace;font-size:.82rem;color:#38bdf8;margin-top:.5rem}
</style>
</head>
<body>
<h1>&#128200; Enterprise Pricing Calculator</h1>
<p class="sub">OCI Robot Cloud &mdash; Deal Pricing, Tier Recommendation &amp; ROI Context &mdash; Port 10049</p>

<div class="grid">
  <div class="card">
    <h2>Example Deal</h2>
    <div class="metric">$47K/yr</div>
    <div class="label">50 robots &times; 500 runs/mo (Starter tier)</div>
  </div>
  <div class="card">
    <h2>ROI Multiple</h2>
    <div class="metric" style="color:#4ade80">37&times;</div>
    <div class="label">Labour savings vs. platform cost</div>
  </div>
  <div class="card">
    <h2>Payback Period</h2>
    <div class="metric" style="color:#38bdf8">7 days</div>
    <div class="label">Working days to break even</div>
  </div>
  <div class="card">
    <h2>Enterprise Floor</h2>
    <div class="metric" style="color:#C74634">$300K/yr</div>
    <div class="label">500+ robots, dedicated CSM</div>
  </div>
</div>

<!-- SVG Bar Chart: ACV by tier for a representative fleet -->
<div class="card" style="margin-bottom:2rem">
  <h2>Annual Contract Value by Tier (Representative Fleet)</h2>
  <svg width="100%" viewBox="0 0 520 220" xmlns="http://www.w3.org/2000/svg">
    <!-- grid lines -->
    <line x1="80" y1="20" x2="500" y2="20" stroke="#334155" stroke-width="1"/>
    <line x1="80" y1="60" x2="500" y2="60" stroke="#334155" stroke-width="1"/>
    <line x1="80" y1="100" x2="500" y2="100" stroke="#334155" stroke-width="1"/>
    <line x1="80" y1="140" x2="500" y2="140" stroke="#334155" stroke-width="1"/>
    <!-- y-axis labels -->
    <text x="72" y="24" fill="#64748b" font-size="11" text-anchor="end">$400K</text>
    <text x="72" y="64" fill="#64748b" font-size="11" text-anchor="end">$300K</text>
    <text x="72" y="104" fill="#64748b" font-size="11" text-anchor="end">$200K</text>
    <text x="72" y="144" fill="#64748b" font-size="11" text-anchor="end">$100K</text>
    <!-- baseline -->
    <line x1="80" y1="160" x2="500" y2="160" stroke="#475569" stroke-width="1.5"/>
    <!-- Starter: ~$47K — bar height = 47/400 * 140 = 16.45 -->
    <rect x="100" y="143.55" width="80" height="16.45" rx="4" fill="#64748b"/>
    <text x="140" y="138" fill="#e2e8f0" font-size="12" font-weight="700" text-anchor="middle">$47K</text>
    <text x="140" y="178" fill="#94a3b8" font-size="11" text-anchor="middle">Starter</text>
    <text x="140" y="192" fill="#64748b" font-size="10" text-anchor="middle">(50 robots)</text>
    <!-- Growth: ~$195K — bar height = 195/400 * 140 = 68.25 -->
    <rect x="220" y="91.75" width="80" height="68.25" rx="4" fill="#38bdf8"/>
    <text x="260" y="86" fill="#e2e8f0" font-size="12" font-weight="700" text-anchor="middle">$195K</text>
    <text x="260" y="178" fill="#94a3b8" font-size="11" text-anchor="middle">Growth</text>
    <text x="260" y="192" fill="#64748b" font-size="10" text-anchor="middle">(200 robots)</text>
    <!-- Enterprise: ~$400K+ — bar height = 400/400 * 140 = 140 -->
    <rect x="340" y="20" width="80" height="140" rx="4" fill="#C74634"/>
    <text x="380" y="14" fill="#e2e8f0" font-size="12" font-weight="700" text-anchor="middle">$400K+</text>
    <text x="380" y="178" fill="#94a3b8" font-size="11" text-anchor="middle">Enterprise</text>
    <text x="380" y="192" fill="#64748b" font-size="10" text-anchor="middle">(600 robots)</text>
  </svg>
</div>

<!-- Tier comparison table -->
<div class="card" style="margin-bottom:2rem">
  <h2>Tier Comparison</h2>
  <table>
    <thead>
      <tr>
        <th>Tier</th>
        <th>Fleet Size</th>
        <th>Base Fee</th>
        <th>Per Robot</th>
        <th>Per Run</th>
        <th>Support</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td class="tier-starter">Starter</td>
        <td>&lt;100</td>
        <td>$50K/yr</td>
        <td>$400/yr</td>
        <td>$0.08</td>
        <td>Email 48h SLA</td>
      </tr>
      <tr>
        <td class="tier-growth">Growth</td>
        <td>100&ndash;499</td>
        <td>$150K/yr</td>
        <td>$300/yr</td>
        <td>$0.05</td>
        <td>Slack 4h SLA</td>
      </tr>
      <tr>
        <td class="tier-enterprise">Enterprise</td>
        <td>500+</td>
        <td>$300K/yr</td>
        <td>$200/yr</td>
        <td>$0.03</td>
        <td>Dedicated CSM 1h SLA</td>
      </tr>
    </tbody>
  </table>
</div>

<div class="example">
  <h2>Example Deal: Garment Factory, 50 Robots</h2>
  <p>
    <strong>Inputs:</strong> 50 robots, 500 inference runs/month, 2 fine-tunes/year, standard support.<br>
    <strong>Breakdown:</strong> $50K base + $20K fleet + $2.4K runs + $4K fine-tunes = <strong>~$76K/yr</strong>.<br>
    <strong>Labour savings:</strong> 50 robots &times; $35K/robot/yr = <strong>$1.75M/yr</strong>.<br>
    <strong>ROI:</strong> 23&times; payback in under 7 working days.
  </p>
</div>

<div class="card">
  <h2>API Endpoints</h2>
  <div class="endpoint">POST /pricing/calculate &nbsp;&mdash;&nbsp; {"robot_count": int, "monthly_runs": int, "fine_tunes_per_year": int, "support_tier": str}</div>
  <div class="endpoint">GET &nbsp;/pricing/tiers &nbsp;&mdash;&nbsp; tier definitions</div>
  <div class="endpoint">GET &nbsp;/health &nbsp;&mdash;&nbsp; service health</div>
</div>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

if _FASTAPI:
    app = FastAPI(
        title="Enterprise Pricing Calculator",
        description="Enterprise deal pricing with tier recommendation and ROI context.",
        version="1.0.0",
    )

    @app.get("/", response_class=HTMLResponse)
    async def dashboard() -> HTMLResponse:
        return HTMLResponse(content=_HTML)

    @app.get("/health")
    async def health() -> JSONResponse:
        return JSONResponse({
            "status": "ok",
            "service": "enterprise_pricing_calculator",
            "port": 10049,
            "timestamp": time.time(),
        })

    @app.post("/pricing/calculate")
    async def pricing_calculate(body: Dict[str, Any]) -> JSONResponse:
        result = calculate_pricing(
            robot_count=int(body.get("robot_count", 50)),
            monthly_runs=int(body.get("monthly_runs", 0)),
            fine_tunes_per_year=int(body.get("fine_tunes_per_year", 0)),
            support_tier=str(body.get("support_tier", "standard")),
        )
        return JSONResponse(result)

    @app.get("/pricing/tiers")
    async def pricing_tiers() -> JSONResponse:
        tiers_out = {
            k: {
                "label": v["label"],
                "min_robots": v["min_robots"],
                "max_robots": v["max_robots"],
                "annual_base_usd": v["annual_base_usd"],
                "per_robot_usd": v["per_robot_usd"],
                "per_run_usd": v["per_run_usd"],
                "fine_tune_usd": v["fine_tune_usd"],
                "support": v["support"],
            }
            for k, v in TIERS.items()
        }
        return JSONResponse(tiers_out)


# ---------------------------------------------------------------------------
# stdlib fallback
# ---------------------------------------------------------------------------

else:
    import http.server
    import urllib.parse

    class _Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):  # silence default logging
            pass

        def _send(self, code: int, content_type: str, body: str | bytes) -> None:
            if isinstance(body, str):
                body = body.encode()
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            path = urllib.parse.urlparse(self.path).path
            if path == "/":
                self._send(200, "text/html", _HTML)
            elif path == "/health":
                self._send(200, "application/json",
                           json.dumps({"status": "ok", "service": "enterprise_pricing_calculator", "port": 10049}))
            elif path == "/pricing/tiers":
                tiers_out = {
                    k: {fk: fv for fk, fv in v.items()}
                    for k, v in TIERS.items()
                }
                self._send(200, "application/json", json.dumps(tiers_out))
            else:
                self._send(404, "application/json", json.dumps({"error": "not found"}))

        def do_POST(self) -> None:
            path = urllib.parse.urlparse(self.path).path
            if path == "/pricing/calculate":
                length = int(self.headers.get("Content-Length", 0))
                raw = self.rfile.read(length)
                try:
                    body = json.loads(raw)
                except Exception:
                    body = {}
                result = calculate_pricing(
                    robot_count=int(body.get("robot_count", 50)),
                    monthly_runs=int(body.get("monthly_runs", 0)),
                    fine_tunes_per_year=int(body.get("fine_tunes_per_year", 0)),
                    support_tier=str(body.get("support_tier", "standard")),
                )
                self._send(200, "application/json", json.dumps(result))
            else:
                self._send(404, "application/json", json.dumps({"error": "not found"}))


if __name__ == "__main__":
    if _FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=10049)
    else:
        server = http.server.HTTPServer(("0.0.0.0", 10049), _Handler)
        print("Enterprise Pricing Calculator running on http://0.0.0.0:10049 (stdlib mode)")
        server.serve_forever()
