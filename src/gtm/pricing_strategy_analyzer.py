"""Pricing Strategy Analyzer — value-based pricing with competitive benchmarking.

Port: 10009
Endpoints:
  GET  /                   → HTML dashboard
  GET  /health             → JSON health check
  GET  /pricing/analysis   → pricing scenario analysis (query param: scenario)
  GET  /pricing/competitive → competitive benchmark table
"""

import json
import math
from datetime import datetime

try:
    from fastapi import FastAPI, Query
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    _FASTAPI = True
except ImportError:
    _FASTAPI = False

# ---------------------------------------------------------------------------
# Domain logic
# ---------------------------------------------------------------------------

OCI_PRICE        = 0.43   # $/run  (current)
PI_PRICE         = 2.10   # $/run  (Physical Intelligence Research)
AWS_P4D_PRICE    = 4.13   # $/run  (AWS p4d equivalent)
PROPOSED_V2      = 0.65   # $/run  (+51% margin proposal)

# Scenario definitions: name -> (proposed_price, revenue_impact_pct, position, recommendation)
SCENARIOS = {
    "conservative": (
        0.52,
        20.9,
        "Still 4.0x cheaper than PI Research",
        "Safe entry — captures margin without alienating early adopters.",
    ),
    "standard": (
        PROPOSED_V2,
        51.2,
        "3.2x cheaper than PI Research; 6.4x cheaper than AWS p4d",
        "Recommended: strong value story with meaningful margin improvement.",
    ),
    "premium": (
        0.89,
        107.0,
        "2.4x cheaper than PI Research; 4.6x cheaper than AWS p4d",
        "Aggressive — justified only after proven enterprise ROI case studies.",
    ),
}


def _analyze(scenario: str):
    key = scenario.lower() if scenario.lower() in SCENARIOS else "standard"
    proposed, impact, position, rec = SCENARIOS[key]
    return {
        "scenario": key,
        "current_price": OCI_PRICE,
        "proposed_price": proposed,
        "revenue_impact_pct": impact,
        "competitive_position": position,
        "recommendation": rec,
    }


def _competitive():
    advantage_multiple = round(PI_PRICE / OCI_PRICE, 1)
    return {
        "oci_per_run": OCI_PRICE,
        "pi_research_per_run": PI_PRICE,
        "aws_p4d_equivalent": AWS_P4D_PRICE,
        "oci_advantage": f"{advantage_multiple}x cheaper",
        "oci_vs_aws": f"{round(AWS_P4D_PRICE / OCI_PRICE, 1)}x cheaper",
        "v2_proposed": PROPOSED_V2,
        "v2_margin_increase_pct": round((PROPOSED_V2 - OCI_PRICE) / OCI_PRICE * 100, 1),
    }


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

# Bar chart values (scale: 0-5 -> 0-180px height, y-baseline=210)
def _bar(price, scale=180 / 5.0):
    h = round(price * scale)
    y = 210 - h
    return y, h, y - 6

_oci_y,  _oci_h,  _oci_ty  = _bar(OCI_PRICE)
_v2_y,   _v2_h,   _v2_ty   = _bar(PROPOSED_V2)
_pi_y,   _pi_h,   _pi_ty   = _bar(PI_PRICE)
_aws_y,  _aws_h,  _aws_ty  = _bar(AWS_P4D_PRICE)

DASHBOARD_HTML = f"""\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Pricing Strategy Analyzer | OCI Robot Cloud</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; min-height: 100vh; padding: 2rem; }}
    h1 {{ color: #C74634; font-size: 1.8rem; font-weight: 700; margin-bottom: 0.25rem; }}
    .subtitle {{ color: #94a3b8; font-size: 0.9rem; margin-bottom: 2rem; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1.25rem; margin-bottom: 2rem; }}
    .card {{ background: #1e293b; border: 1px solid #334155; border-radius: 0.75rem; padding: 1.25rem; }}
    .card-label {{ color: #94a3b8; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.5rem; }}
    .card-value {{ font-size: 2rem; font-weight: 700; color: #38bdf8; }}
    .card-sub {{ color: #64748b; font-size: 0.8rem; margin-top: 0.25rem; }}
    .highlight {{ color: #C74634 !important; }}
    .chart-section {{ background: #1e293b; border: 1px solid #334155; border-radius: 0.75rem; padding: 1.5rem; margin-bottom: 2rem; }}
    .chart-title {{ color: #C74634; font-size: 1rem; font-weight: 600; margin-bottom: 1rem; }}
    .endpoints {{ background: #1e293b; border: 1px solid #334155; border-radius: 0.75rem; padding: 1.25rem; }}
    .endpoint {{ display: flex; align-items: center; gap: 0.75rem; padding: 0.5rem 0; border-bottom: 1px solid #0f172a; }}
    .endpoint:last-child {{ border-bottom: none; }}
    .method {{ background: #0369a1; color: #fff; font-size: 0.7rem; font-weight: 700; padding: 0.2rem 0.5rem; border-radius: 0.25rem; min-width: 3.5rem; text-align: center; }}
    .path {{ color: #38bdf8; font-family: monospace; font-size: 0.85rem; }}
    .desc {{ color: #94a3b8; font-size: 0.8rem; margin-left: auto; }}
    footer {{ color: #475569; font-size: 0.75rem; text-align: center; margin-top: 2rem; }}
  </style>
</head>
<body>
  <h1>Pricing Strategy Analyzer</h1>
  <p class="subtitle">Value-based pricing with competitive benchmarking &mdash; OCI Robot Cloud &bull; Port 10009</p>

  <div class="grid">
    <div class="card">
      <div class="card-label">OCI Current Price</div>
      <div class="card-value">$0.43<span style="font-size:1rem">/run</span></div>
      <div class="card-sub">9.6x cheaper than PI Research</div>
    </div>
    <div class="card">
      <div class="card-label">v2 Proposed Price</div>
      <div class="card-value" style="color:#38bdf8">$0.65<span style="font-size:1rem">/run</span></div>
      <div class="card-sub">+51% margin increase</div>
    </div>
    <div class="card">
      <div class="card-label">PI Research Price</div>
      <div class="card-value highlight">$2.10<span style="font-size:1rem">/run</span></div>
      <div class="card-sub">4.9x vs OCI current</div>
    </div>
    <div class="card">
      <div class="card-label">AWS p4d Equivalent</div>
      <div class="card-value highlight">$4.13<span style="font-size:1rem">/run</span></div>
      <div class="card-sub">9.6x vs OCI current</div>
    </div>
    <div class="card">
      <div class="card-label">OCI Advantage</div>
      <div class="card-value">9.6x</div>
      <div class="card-sub">cheaper than PI Research</div>
    </div>
    <div class="card">
      <div class="card-label">Service Port</div>
      <div class="card-value">10009</div>
      <div class="card-sub">FastAPI / uvicorn</div>
    </div>
  </div>

  <div class="chart-section">
    <div class="chart-title">Price per Inference Run — Competitive Landscape</div>
    <svg viewBox="0 0 560 260" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:560px;display:block">
      <!-- axes -->
      <line x1="60" y1="20" x2="60" y2="210" stroke="#334155" stroke-width="1.5"/>
      <line x1="60" y1="210" x2="520" y2="210" stroke="#334155" stroke-width="1.5"/>
      <!-- y-axis labels -->
      <text x="50" y="215" fill="#64748b" font-size="11" text-anchor="end">$0</text>
      <text x="50" y="179" fill="#64748b" font-size="11" text-anchor="end">$1</text>
      <text x="50" y="143" fill="#64748b" font-size="11" text-anchor="end">$2</text>
      <text x="50" y="107" fill="#64748b" font-size="11" text-anchor="end">$3</text>
      <text x="50" y="71"  fill="#64748b" font-size="11" text-anchor="end">$4</text>
      <!-- gridlines -->
      <line x1="60" y1="174" x2="520" y2="174" stroke="#1e293b" stroke-width="1"/>
      <line x1="60" y1="138" x2="520" y2="138" stroke="#1e293b" stroke-width="1"/>
      <line x1="60" y1="102" x2="520" y2="102" stroke="#1e293b" stroke-width="1"/>
      <line x1="60" y1="66"  x2="520" y2="66"  stroke="#1e293b" stroke-width="1"/>
      <!-- OCI current: $0.43 -->
      <rect x="80"  y="{oci_y}"  width="70" height="{oci_h}"  rx="4" fill="#38bdf8"/>
      <text x="115" y="{oci_ty}" fill="#38bdf8" font-size="12" text-anchor="middle" font-weight="700">$0.43</text>
      <!-- OCI v2 proposal: $0.65 -->
      <rect x="170" y="{v2_y}"   width="70" height="{v2_h}"   rx="4" fill="#0ea5e9"/>
      <text x="205" y="{v2_ty}"  fill="#0ea5e9" font-size="12" text-anchor="middle" font-weight="700">$0.65</text>
      <!-- PI Research: $2.10 -->
      <rect x="310" y="{pi_y}"   width="70" height="{pi_h}"   rx="4" fill="#C74634"/>
      <text x="345" y="{pi_ty}"  fill="#C74634" font-size="12" text-anchor="middle" font-weight="700">$2.10</text>
      <!-- AWS p4d: $4.13 -->
      <rect x="400" y="{aws_y}"  width="70" height="{aws_h}"  rx="4" fill="#dc2626"/>
      <text x="435" y="{aws_ty}" fill="#dc2626" font-size="12" text-anchor="middle" font-weight="700">$4.13</text>
      <!-- x-axis labels -->
      <text x="115" y="228" fill="#94a3b8" font-size="10" text-anchor="middle">OCI Current</text>
      <text x="205" y="228" fill="#94a3b8" font-size="10" text-anchor="middle">OCI v2 Proposal</text>
      <text x="345" y="228" fill="#94a3b8" font-size="10" text-anchor="middle">PI Research</text>
      <text x="435" y="228" fill="#94a3b8" font-size="10" text-anchor="middle">AWS p4d</text>
    </svg>
  </div>

  <div class="endpoints">
    <div style="color:#C74634;font-size:1rem;font-weight:600;margin-bottom:0.75rem;">API Endpoints</div>
    <div class="endpoint"><span class="method">GET</span><span class="path">/</span><span class="desc">HTML dashboard</span></div>
    <div class="endpoint"><span class="method">GET</span><span class="path">/health</span><span class="desc">JSON health check</span></div>
    <div class="endpoint"><span class="method">GET</span><span class="path">/pricing/analysis?scenario=standard</span><span class="desc">Pricing scenario analysis</span></div>
    <div class="endpoint"><span class="method">GET</span><span class="path">/pricing/competitive</span><span class="desc">Competitive benchmark table</span></div>
  </div>

  <footer>OCI Robot Cloud &bull; Pricing Strategy Analyzer &bull; Port 10009 &bull; &copy; 2026 Oracle</footer>
</body>
</html>
""".replace("{oci_y}", str(_oci_y)).replace("{oci_h}", str(_oci_h)).replace("{oci_ty}", str(_oci_ty)) \
   .replace("{v2_y}",  str(_v2_y)).replace("{v2_h}",  str(_v2_h)).replace("{v2_ty}",  str(_v2_ty)) \
   .replace("{pi_y}",  str(_pi_y)).replace("{pi_h}",  str(_pi_h)).replace("{pi_ty}",  str(_pi_ty)) \
   .replace("{aws_y}", str(_aws_y)).replace("{aws_h}", str(_aws_h)).replace("{aws_ty}", str(_aws_ty))


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

if _FASTAPI:
    app = FastAPI(
        title="Pricing Strategy Analyzer",
        description="Value-based pricing analysis with competitive benchmarking",
        version="1.0.0",
    )

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    def dashboard():
        return DASHBOARD_HTML

    @app.get("/health")
    def health():
        return JSONResponse({
            "status": "ok",
            "service": "pricing_strategy_analyzer",
            "port": 10009,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        })

    @app.get("/pricing/analysis")
    def pricing_analysis(scenario: str = Query(default="standard", description="conservative | standard | premium")):
        return JSONResponse(_analyze(scenario))

    @app.get("/pricing/competitive")
    def pricing_competitive():
        return JSONResponse(_competitive())


# ---------------------------------------------------------------------------
# stdlib HTTPServer fallback
# ---------------------------------------------------------------------------

else:
    from http.server import BaseHTTPRequestHandler, HTTPServer
    from urllib.parse import urlparse, parse_qs

    class _Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass

        def _send(self, code, content_type, body):
            encoded = body.encode() if isinstance(body, str) else body
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def do_GET(self):
            parsed = urlparse(self.path)
            path = parsed.path
            qs = parse_qs(parsed.query)

            if path in ("/", ""):
                self._send(200, "text/html; charset=utf-8", DASHBOARD_HTML)
            elif path == "/health":
                self._send(200, "application/json",
                           json.dumps({"status": "ok", "service": "pricing_strategy_analyzer", "port": 10009}))
            elif path == "/pricing/analysis":
                scenario = qs.get("scenario", ["standard"])[0]
                self._send(200, "application/json", json.dumps(_analyze(scenario)))
            elif path == "/pricing/competitive":
                self._send(200, "application/json", json.dumps(_competitive()))
            else:
                self._send(404, "application/json", json.dumps({"error": "not found"}))


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if _FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=10009)
    else:
        print("[pricing_strategy_analyzer] fastapi not found — starting stdlib HTTPServer on port 10009")
        server = HTTPServer(("0.0.0.0", 10009), _Handler)
        server.serve_forever()
