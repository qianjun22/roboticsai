"""saas_billing_engine.py — Usage-based + seat SaaS billing with dunning management.

Port: 10037
Cycle: 495A
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict

try:
    from fastapi import FastAPI, Query
    from fastapi.responses import HTMLResponse, JSONResponse
    from pydantic import BaseModel
    import uvicorn
    _FASTAPI = True
except ImportError:
    _FASTAPI = False
    from http.server import BaseHTTPRequestHandler, HTTPServer
    from urllib.parse import urlparse, parse_qs

# ---------------------------------------------------------------------------
# In-memory billing store
# ---------------------------------------------------------------------------

_BILLING: Dict[str, Dict[str, Any]] = {
    "cust_acme": {
        "tier": "growth",
        "seat_count": 12,
        "seat_price": 299.0,
        "usage_runs": 4200,
        "usage_price_per_run": 0.012,
        "payment_status": "current",
        "dunning_day": 0,
    },
    "cust_beta": {
        "tier": "starter",
        "seat_count": 3,
        "seat_price": 99.0,
        "usage_runs": 820,
        "usage_price_per_run": 0.008,
        "payment_status": "overdue_d3",
        "dunning_day": 3,
    },
    "cust_gamma": {
        "tier": "enterprise",
        "seat_count": 40,
        "seat_price": 499.0,
        "usage_runs": 15600,
        "usage_price_per_run": 0.006,
        "payment_status": "current",
        "dunning_day": 0,
    },
}

_START_TIME = time.time()
_DAYS_IN_MONTH = 30
_CURRENT_DAY = 15  # simulate mid-month


def _compute_invoice(customer: Dict[str, Any]) -> float:
    seat_rev = customer["seat_count"] * customer["seat_price"]
    usage_rev = customer["usage_runs"] * customer["usage_price_per_run"]
    return round(seat_rev + usage_rev, 2)


def _projected_monthly(customer: Dict[str, Any]) -> float:
    daily_runs = customer["usage_runs"] / max(1, _CURRENT_DAY)
    projected_runs = daily_runs * _DAYS_IN_MONTH
    seat_rev = customer["seat_count"] * customer["seat_price"]
    usage_rev = projected_runs * customer["usage_price_per_run"]
    return round(seat_rev + usage_rev, 2)


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>SaaS Billing Engine — OCI Robot Cloud</title>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',system-ui,sans-serif;min-height:100vh;padding:2rem}
  h1{color:#38bdf8;font-size:1.8rem;margin-bottom:.25rem}
  .subtitle{color:#94a3b8;font-size:.9rem;margin-bottom:2rem}
  .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:1rem;margin-bottom:2rem}
  .card{background:#1e293b;border-radius:.75rem;padding:1.25rem;border:1px solid #334155}
  .card-title{color:#94a3b8;font-size:.75rem;text-transform:uppercase;letter-spacing:.08em;margin-bottom:.5rem}
  .card-value{font-size:1.8rem;font-weight:700;color:#38bdf8}
  .card-sub{font-size:.8rem;color:#64748b;margin-top:.25rem}
  .section{background:#1e293b;border-radius:.75rem;padding:1.5rem;border:1px solid #334155;margin-bottom:1.5rem}
  .section h2{color:#C74634;font-size:1rem;margin-bottom:1rem;text-transform:uppercase;letter-spacing:.06em}
  table{width:100%;border-collapse:collapse;font-size:.85rem}
  th{color:#94a3b8;text-align:left;padding:.5rem .75rem;border-bottom:1px solid #334155}
  td{padding:.5rem .75rem;border-bottom:1px solid #1e293b;color:#cbd5e1}
  tr:last-child td{border-bottom:none}
  .badge{display:inline-block;padding:.2rem .6rem;border-radius:9999px;font-size:.75rem;font-weight:600}
  .badge-green{background:#14532d;color:#4ade80}
  .badge-red{background:#450a0a;color:#f87171}
  .badge-yellow{background:#422006;color:#fbbf24}
  .badge-blue{background:#0c4a6e;color:#38bdf8}
  .dunning-flow{display:flex;gap:.75rem;align-items:center;flex-wrap:wrap;margin-top:.5rem}
  .dnode{background:#0f172a;border:1px solid #334155;border-radius:.5rem;padding:.5rem 1rem;font-size:.8rem;text-align:center}
  .dnode-label{color:#94a3b8;font-size:.7rem}
  .dnode-day{color:#C74634;font-weight:700;font-size:1rem}
  .arrow{color:#334155;font-size:1.2rem}
  svg text{font-family:'Segoe UI',system-ui,sans-serif}
</style>
</head>
<body>
<h1>SaaS Billing Engine</h1>
<p class="subtitle">OCI Robot Cloud · Port 10037 · Usage-based + seat billing with dunning management</p>

<div class="grid">
  <div class="card">
    <div class="card-title">MRR</div>
    <div class="card-value">$20.8K</div>
    <div class="card-sub">Monthly recurring revenue</div>
  </div>
  <div class="card">
    <div class="card-title">ARR</div>
    <div class="card-value">$250K</div>
    <div class="card-sub">Annual run rate</div>
  </div>
  <div class="card">
    <div class="card-title">Usage Revenue</div>
    <div class="card-value">$43K</div>
    <div class="card-sub">17% of ARR</div>
  </div>
  <div class="card">
    <div class="card-title">Seat Revenue</div>
    <div class="card-value">$207K</div>
    <div class="card-sub">83% of ARR</div>
  </div>
  <div class="card">
    <div class="card-title">Active Customers</div>
    <div class="card-value">3</div>
    <div class="card-sub">1 in dunning (D3)</div>
  </div>
</div>

<div class="section">
  <h2>Revenue Breakdown — Usage vs Seat</h2>
  <svg viewBox="0 0 480 200" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:480px;display:block;margin:0 auto">
    <!-- axes -->
    <line x1="60" y1="10" x2="60" y2="165" stroke="#334155" stroke-width="1"/>
    <line x1="60" y1="165" x2="460" y2="165" stroke="#334155" stroke-width="1"/>
    <!-- y labels (max $250K) -->
    <text x="55" y="15" fill="#64748b" font-size="10" text-anchor="end">$250K</text>
    <text x="55" y="72" fill="#64748b" font-size="10" text-anchor="end">$125K</text>
    <text x="55" y="165" fill="#64748b" font-size="10" text-anchor="end">$0</text>
    <!-- grid -->
    <line x1="60" y1="72" x2="460" y2="72" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4 3"/>
    <!-- ARR total: $250K → height 155 -->
    <rect x="80" y="10" width="80" height="155" fill="#38bdf8" rx="3"/>
    <text x="120" y="6" fill="#38bdf8" font-size="11" text-anchor="middle" font-weight="bold">$250K ARR</text>
    <!-- Seat $207K → height=207/250*155=128 -->
    <rect x="200" y="37" width="80" height="128" fill="#C74634" rx="3"/>
    <text x="240" y="33" fill="#C74634" font-size="11" text-anchor="middle" font-weight="bold">$207K Seat</text>
    <!-- Usage $43K → height=43/250*155=27 -->
    <rect x="320" y="138" width="80" height="27" fill="#7c3aed" rx="3"/>
    <text x="360" y="134" fill="#a78bfa" font-size="11" text-anchor="middle" font-weight="bold">$43K Usage</text>
    <!-- x labels -->
    <text x="120" y="182" fill="#94a3b8" font-size="11" text-anchor="middle">Total ARR</text>
    <text x="240" y="182" fill="#94a3b8" font-size="11" text-anchor="middle">Seat</text>
    <text x="360" y="182" fill="#94a3b8" font-size="11" text-anchor="middle">Usage</text>
    <!-- legend -->
    <rect x="65" y="192" width="10" height="7" fill="#38bdf8" rx="1"/>
    <text x="79" y="199" fill="#94a3b8" font-size="9">ARR</text>
    <rect x="110" y="192" width="10" height="7" fill="#C74634" rx="1"/>
    <text x="124" y="199" fill="#94a3b8" font-size="9">Seat</text>
    <rect x="155" y="192" width="10" height="7" fill="#7c3aed" rx="1"/>
    <text x="169" y="199" fill="#94a3b8" font-size="9">Usage</text>
  </svg>
</div>

<div class="section">
  <h2>Dunning Flow</h2>
  <div class="dunning-flow">
    <div class="dnode"><div class="dnode-label">Invoice</div><div class="dnode-day">D0</div></div>
    <div class="arrow">→</div>
    <div class="dnode"><div class="dnode-label">Reminder</div><div class="dnode-day">D1</div></div>
    <div class="arrow">→</div>
    <div class="dnode"><div class="dnode-label">Follow-up</div><div class="dnode-day">D3</div></div>
    <div class="arrow">→</div>
    <div class="dnode"><div class="dnode-label">Escalate</div><div class="dnode-day">D7</div></div>
    <div class="arrow">→</div>
    <div class="dnode"><div class="dnode-label">Suspend</div><div class="dnode-day">D14</div></div>
    <div class="arrow">→</div>
    <div class="dnode"><div class="dnode-label">Terminate</div><div class="dnode-day">D21</div></div>
  </div>
</div>

<div class="section">
  <h2>Customer Billing Summary</h2>
  <table>
    <thead><tr><th>Customer</th><th>Tier</th><th>Seats</th><th>Usage Runs</th><th>Invoice</th><th>Payment Status</th></tr></thead>
    <tbody>
      <tr>
        <td>cust_acme</td>
        <td><span class="badge badge-blue">growth</span></td>
        <td>12</td><td>4,200</td><td>$3,638.40</td>
        <td><span class="badge badge-green">current</span></td>
      </tr>
      <tr>
        <td>cust_beta</td>
        <td><span class="badge badge-yellow">starter</span></td>
        <td>3</td><td>820</td><td>$303.56</td>
        <td><span class="badge badge-red">overdue D3</span></td>
      </tr>
      <tr>
        <td>cust_gamma</td>
        <td><span class="badge badge-blue">enterprise</span></td>
        <td>40</td><td>15,600</td><td>$20,093.60</td>
        <td><span class="badge badge-green">current</span></td>
      </tr>
    </tbody>
  </table>
</div>

<div class="section">
  <h2>API Endpoints</h2>
  <table>
    <thead><tr><th>Method</th><th>Path</th><th>Description</th></tr></thead>
    <tbody>
      <tr><td>GET</td><td>/</td><td>HTML dashboard</td></tr>
      <tr><td>GET</td><td>/health</td><td>JSON health check</td></tr>
      <tr><td>POST</td><td>/billing/record_usage</td><td>Record runs and get invoice amount</td></tr>
      <tr><td>GET</td><td>/billing/summary?customer_id=...</td><td>Customer billing summary</td></tr>
    </tbody>
  </table>
</div>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

if _FASTAPI:
    app = FastAPI(
        title="SaaS Billing Engine",
        description="Usage-based + seat SaaS billing with dunning management.",
        version="1.0.0",
    )

    class UsageRequest(BaseModel):
        customer_id: str
        run_count: int

    @app.get("/", response_class=HTMLResponse)
    async def dashboard() -> HTMLResponse:
        return HTMLResponse(content=HTML)

    @app.get("/health")
    async def health() -> JSONResponse:
        return JSONResponse({
            "status": "ok",
            "service": "saas_billing_engine",
            "port": 10037,
            "uptime_seconds": round(time.time() - _START_TIME, 1),
            "customers": len(_BILLING),
        })

    @app.post("/billing/record_usage")
    async def record_usage(req: UsageRequest) -> JSONResponse:
        if req.customer_id not in _BILLING:
            # auto-create starter customer
            _BILLING[req.customer_id] = {
                "tier": "starter",
                "seat_count": 1,
                "seat_price": 99.0,
                "usage_runs": 0,
                "usage_price_per_run": 0.008,
                "payment_status": "current",
                "dunning_day": 0,
            }
        customer = _BILLING[req.customer_id]
        customer["usage_runs"] += req.run_count
        invoice_amount = _compute_invoice(customer)
        projected = _projected_monthly(customer)
        return JSONResponse({
            "invoice_amount": invoice_amount,
            "current_period_usage": customer["usage_runs"],
            "projected_monthly": projected,
        })

    @app.get("/billing/summary")
    async def billing_summary(customer_id: str = Query(..., description="Customer ID")) -> JSONResponse:
        if customer_id not in _BILLING:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail=f"Customer '{customer_id}' not found")
        customer = _BILLING[customer_id]
        return JSONResponse({
            "current_month_usage": customer["usage_runs"],
            "projected_invoice": _projected_monthly(customer),
            "payment_status": customer["payment_status"],
            "tier": customer["tier"],
        })


# ---------------------------------------------------------------------------
# Stdlib HTTPServer fallback
# ---------------------------------------------------------------------------

else:
    class _Handler(BaseHTTPRequestHandler):
        def log_message(self, *args: Any) -> None:
            pass

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            path = parsed.path
            if path in ("/", ""):
                body = HTML.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif path == "/health":
                payload = json.dumps({
                    "status": "ok",
                    "service": "saas_billing_engine",
                    "port": 10037,
                    "uptime_seconds": round(time.time() - _START_TIME, 1),
                    "customers": len(_BILLING),
                }).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
            elif path == "/billing/summary":
                qs = parse_qs(parsed.query)
                cid = qs.get("customer_id", [None])[0]
                if cid and cid in _BILLING:
                    c = _BILLING[cid]
                    payload = json.dumps({
                        "current_month_usage": c["usage_runs"],
                        "projected_invoice": _projected_monthly(c),
                        "payment_status": c["payment_status"],
                        "tier": c["tier"],
                    }).encode()
                    self.send_response(200)
                else:
                    payload = json.dumps({"error": "customer not found"}).encode()
                    self.send_response(404)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
            else:
                self.send_error(404)

        def do_POST(self) -> None:
            if self.path == "/billing/record_usage":
                length = int(self.headers.get("Content-Length", 0))
                data = json.loads(self.rfile.read(length))
                cid = data.get("customer_id", "")
                run_count = int(data.get("run_count", 0))
                if cid not in _BILLING:
                    _BILLING[cid] = {
                        "tier": "starter",
                        "seat_count": 1,
                        "seat_price": 99.0,
                        "usage_runs": 0,
                        "usage_price_per_run": 0.008,
                        "payment_status": "current",
                        "dunning_day": 0,
                    }
                _BILLING[cid]["usage_runs"] += run_count
                payload = json.dumps({
                    "invoice_amount": _compute_invoice(_BILLING[cid]),
                    "current_period_usage": _BILLING[cid]["usage_runs"],
                    "projected_monthly": _projected_monthly(_BILLING[cid]),
                }).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
            else:
                self.send_error(404)


if __name__ == "__main__":
    if _FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=10037)
    else:
        print("FastAPI not available — starting stdlib HTTPServer on port 10037")
        server = HTTPServer(("0.0.0.0", 10037), _Handler)
        server.serve_forever()
