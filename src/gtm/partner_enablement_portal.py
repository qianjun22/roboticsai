"""Partner Enablement Portal — self-serve partner onboarding and management.

Port: 9999
"""

import hashlib
import json
import random
import secrets
import string
import time
from typing import Any, Dict

try:
    from fastapi import FastAPI, Query
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    _FASTAPI_AVAILABLE = True
except ImportError:
    _FASTAPI_AVAILABLE = False

# ---------------------------------------------------------------------------
# In-process partner registry (demo)
# ---------------------------------------------------------------------------

_PARTNERS: Dict[str, Dict[str, Any]] = {}

_TIERS = {
    "starter": {"rpm": 60,  "price_usd": 0},
    "growth":  {"rpm": 600, "price_usd": 499},
    "enterprise": {"rpm": 6000, "price_usd": 2499},
}


def _make_api_key(company: str) -> str:
    rand = secrets.token_hex(12)
    prefix = company[:4].upper().replace(" ", "X")
    return f"oci-rb-{prefix}-{rand}"


def _sandbox_endpoint(tier: str) -> str:
    return f"https://sandbox.roboticsai.oci.oracle.com/v1/{tier}/infer"


# ---------------------------------------------------------------------------
# HTML Dashboard
# ---------------------------------------------------------------------------

_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Partner Enablement Portal</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; padding: 2rem; }
    h1 { color: #C74634; font-size: 1.8rem; margin-bottom: 0.4rem; }
    h2 { color: #38bdf8; font-size: 1.1rem; margin: 1.5rem 0 0.6rem; }
    .subtitle { color: #94a3b8; font-size: 0.95rem; margin-bottom: 1.8rem; }
    .cards { display: flex; gap: 1rem; flex-wrap: wrap; margin-bottom: 2rem; }
    .card { background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 1.2rem 1.6rem; min-width: 150px; }
    .card-label { color: #94a3b8; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em; }
    .card-value { font-size: 2rem; font-weight: 700; margin-top: 0.3rem; }
    .red   { color: #C74634; }
    .blue  { color: #38bdf8; }
    .green { color: #4ade80; }
    .amber { color: #fbbf24; }
    .purple { color: #a78bfa; }
    .chart-wrap { background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 1.4rem; display: inline-block; }
    table { border-collapse: collapse; width: 100%; }
    th { background: #0f172a; color: #38bdf8; text-align: left; padding: 0.6rem 1rem; font-size: 0.85rem; }
    td { padding: 0.55rem 1rem; border-top: 1px solid #1e293b; font-size: 0.9rem; color: #cbd5e1; }
    tr:hover td { background: #1e293b; }
    .badge { display: inline-block; border-radius: 999px; padding: 0.15rem 0.65rem; font-size: 0.75rem; font-weight: 600; }
    .b-blue   { background: #0c4a6e; color: #38bdf8; }
    .b-green  { background: #14532d; color: #4ade80; }
    .b-amber  { background: #78350f; color: #fbbf24; }
    .b-purple { background: #2e1065; color: #a78bfa; }
    footer { color: #475569; font-size: 0.75rem; margin-top: 2.5rem; }
  </style>
</head>
<body>
  <h1>Partner Enablement Portal</h1>
  <p class="subtitle">Self-serve onboarding &amp; management for OCI Robot Cloud partners &nbsp;|&nbsp; Port 9999</p>

  <div class="cards">
    <div class="card">
      <div class="card-label">Partner NPS</div>
      <div class="card-value green">74</div>
    </div>
    <div class="card">
      <div class="card-label">Time-to-First-API</div>
      <div class="card-value blue">12 min</div>
    </div>
    <div class="card">
      <div class="card-label">Churn Rate</div>
      <div class="card-value green">0%</div>
    </div>
    <div class="card">
      <div class="card-label">Tier Levels</div>
      <div class="card-value red">3</div>
    </div>
    <div class="card">
      <div class="card-label">Active Partners</div>
      <div class="card-value amber">47</div>
    </div>
  </div>

  <h2>Partner Growth by Tier</h2>
  <div class="chart-wrap">
    <svg width="480" height="220" viewBox="0 0 480 220" xmlns="http://www.w3.org/2000/svg">
      <!-- axes -->
      <line x1="60" y1="10" x2="60" y2="180" stroke="#334155" stroke-width="1.5"/>
      <line x1="60" y1="180" x2="460" y2="180" stroke="#334155" stroke-width="1.5"/>
      <!-- y labels (max 25 partners) -->
      <text x="52" y="185" fill="#64748b" font-size="11" text-anchor="end">0</text>
      <text x="52" y="146" fill="#64748b" font-size="11" text-anchor="end">5</text>
      <text x="52" y="112" fill="#64748b" font-size="11" text-anchor="end">10</text>
      <text x="52" y="78"  fill="#64748b" font-size="11" text-anchor="end">15</text>
      <text x="52" y="44"  fill="#64748b" font-size="11" text-anchor="end">20</text>
      <text x="52" y="15"  fill="#64748b" font-size="11" text-anchor="end">25</text>
      <!-- grid lines (34px per 5 units) -->
      <line x1="60" y1="146" x2="460" y2="146" stroke="#1e293b" stroke-width="1"/>
      <line x1="60" y1="112" x2="460" y2="112" stroke="#1e293b" stroke-width="1"/>
      <line x1="60" y1="78"  x2="460" y2="78"  stroke="#1e293b" stroke-width="1"/>
      <line x1="60" y1="44"  x2="460" y2="44"  stroke="#1e293b" stroke-width="1"/>
      <!-- Starter: 22 partners → 22*6.8=149.6; bar height 149.6, y=180-149.6=30.4 -->
      <rect x="80"  y="30.4" width="90" height="149.6" fill="#38bdf8" rx="4"/>
      <text x="125" y="24"  fill="#38bdf8" font-size="12" text-anchor="middle">22</text>
      <!-- Growth: 17 partners → 17*6.8=115.6 -->
      <rect x="210" y="64.4" width="90" height="115.6" fill="#a78bfa" rx="4"/>
      <text x="255" y="58"  fill="#a78bfa" font-size="12" text-anchor="middle">17</text>
      <!-- Enterprise: 8 partners → 8*6.8=54.4 -->
      <rect x="340" y="125.6" width="90" height="54.4" fill="#C74634" rx="4"/>
      <text x="385" y="120" fill="#C74634" font-size="12" text-anchor="middle">8</text>
      <!-- x labels -->
      <text x="125" y="198" fill="#94a3b8" font-size="11" text-anchor="middle">Starter (Free)</text>
      <text x="255" y="198" fill="#94a3b8" font-size="11" text-anchor="middle">Growth ($499/mo)</text>
      <text x="385" y="198" fill="#94a3b8" font-size="11" text-anchor="middle">Enterprise ($2499/mo)</text>
    </svg>
  </div>

  <h2>Tier Comparison</h2>
  <table>
    <thead><tr><th>Tier</th><th>Price/mo</th><th>Rate Limit</th><th>SLA</th><th>Support</th></tr></thead>
    <tbody>
      <tr>
        <td><span class="badge b-blue">Starter</span></td>
        <td>Free</td><td>60 RPM</td><td>—</td><td>Community</td>
      </tr>
      <tr>
        <td><span class="badge b-purple">Growth</span></td>
        <td>$499</td><td>600 RPM</td><td>99.5%</td><td>Email 24h</td>
      </tr>
      <tr>
        <td><span class="badge b-amber">Enterprise</span></td>
        <td>$2,499</td><td>6,000 RPM</td><td>99.9%</td><td>Slack + TAM</td>
      </tr>
    </tbody>
  </table>

  <h2>API Endpoints</h2>
  <table>
    <thead><tr><th>Method</th><th>Path</th><th>Description</th></tr></thead>
    <tbody>
      <tr><td><span class="badge b-blue">GET</span></td><td>/</td><td>This dashboard</td></tr>
      <tr><td><span class="badge b-green">GET</span></td><td>/health</td><td>Health check</td></tr>
      <tr><td><span class="badge b-amber">POST</span></td><td>/partner/onboard</td><td>Onboard a new partner (returns API key)</td></tr>
      <tr><td><span class="badge b-blue">GET</span></td><td>/partner/dashboard</td><td>Partner usage metrics (requires api_key)</td></tr>
    </tbody>
  </table>

  <footer>OCI Robot Cloud &mdash; Partner Enablement Portal &mdash; Port 9999</footer>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

if _FASTAPI_AVAILABLE:
    app = FastAPI(
        title="Partner Enablement Portal",
        description="Self-serve partner onboarding and management for OCI Robot Cloud",
        version="1.0.0",
    )

    @app.get("/", response_class=HTMLResponse)
    async def dashboard() -> HTMLResponse:
        return HTMLResponse(content=_HTML)

    @app.get("/health")
    async def health() -> Dict[str, Any]:
        return {"status": "ok", "service": "partner_enablement_portal", "port": 9999}

    @app.post("/partner/onboard")
    async def onboard_partner(body: Dict[str, Any]) -> Dict[str, Any]:
        company: str = str(body.get("company", "Unknown"))
        email: str = str(body.get("email", ""))
        tier: str = str(body.get("tier", "starter")).lower()
        if tier not in _TIERS:
            tier = "starter"

        api_key = _make_api_key(company)
        sandbox_endpoint = _sandbox_endpoint(tier)

        _PARTNERS[api_key] = {
            "company": company,
            "email": email,
            "tier": tier,
            "usage_runs": 0,
            "sr_achieved": 0.0,
            "cost_usd": _TIERS[tier]["price_usd"],
            "health_score": 100.0,
            "created_at": time.time(),
        }

        return {
            "api_key": api_key,
            "sandbox_endpoint": sandbox_endpoint,
            "tier": tier,
        }

    @app.get("/partner/dashboard")
    async def partner_dashboard(api_key: str = Query(...)) -> Dict[str, Any]:
        if api_key not in _PARTNERS:
            # Return demo data for unknown keys
            return {
                "usage_runs": random.randint(120, 850),
                "sr_achieved": round(random.uniform(88.0, 94.5), 1),
                "cost_usd": 499.0,
                "health_score": round(random.uniform(92.0, 99.5), 1),
            }
        p = _PARTNERS[api_key]
        # Simulate some usage accumulation
        p["usage_runs"] += random.randint(1, 5)
        p["sr_achieved"] = round(min(94.0, p["sr_achieved"] + random.uniform(0.1, 0.5)), 1)
        return {
            "usage_runs": p["usage_runs"],
            "sr_achieved": p["sr_achieved"],
            "cost_usd": p["cost_usd"],
            "health_score": p["health_score"],
        }

# ---------------------------------------------------------------------------
# Fallback: stdlib HTTP server
# ---------------------------------------------------------------------------

if not _FASTAPI_AVAILABLE:
    import http.server
    import urllib.parse

    class _Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *args: Any) -> None:
            pass

        def _send(self, code: int, ctype: str, body: bytes) -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path
            params = dict(urllib.parse.parse_qsl(parsed.query))
            if path == "/":
                self._send(200, "text/html", _HTML.encode())
            elif path == "/health":
                data = json.dumps({"status": "ok", "service": "partner_enablement_portal", "port": 9999}).encode()
                self._send(200, "application/json", data)
            elif path == "/partner/dashboard":
                data = json.dumps({"usage_runs": random.randint(120, 850), "sr_achieved": 91.5, "cost_usd": 499.0, "health_score": 96.3}).encode()
                self._send(200, "application/json", data)
            else:
                self._send(404, "application/json", b'{"error":"not found"}')

        def do_POST(self) -> None:
            path = urllib.parse.urlparse(self.path).path
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length) or b"{}")
            if path == "/partner/onboard":
                company = str(body.get("company", "Unknown"))
                tier = str(body.get("tier", "starter")).lower()
                if tier not in _TIERS:
                    tier = "starter"
                api_key = _make_api_key(company)
                data = json.dumps({"api_key": api_key, "sandbox_endpoint": _sandbox_endpoint(tier), "tier": tier}).encode()
                self._send(200, "application/json", data)
            else:
                self._send(404, "application/json", b'{"error":"not found"}')

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if _FASTAPI_AVAILABLE:
        import uvicorn  # type: ignore
        uvicorn.run(app, host="0.0.0.0", port=9999)
    else:
        import http.server
        server = http.server.HTTPServer(("0.0.0.0", 9999), _Handler)
        print("[partner_enablement_portal] Serving on http://0.0.0.0:9999 (stdlib fallback)")
        server.serve_forever()
