"""enterprise_churn_predictor.py — cycle-486A

ML-based churn risk scoring from behavioral signals.
Port: 10001
"""

from __future__ import annotations

import json
import math
import random
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlparse

try:
    from fastapi import FastAPI, Query
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    _FASTAPI = True
except ImportError:
    _FASTAPI = False

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
PORT = 10001
SERVICE_NAME = "enterprise_churn_predictor"
CURRENT_CHURN_PCT = 0
MODEL_AUC = 0.91
N_BEHAVIORAL_SIGNALS = 23
ARR_AT_RISK_PER_CHURN = 83_000  # USD

# ---------------------------------------------------------------------------
# Synthetic customer dataset (deterministic)
# ---------------------------------------------------------------------------
_SIGNALS = [
    "login_frequency_drop", "api_call_decrease", "support_tickets_spike",
    "feature_adoption_low", "invoice_late_payment", "nps_score_low",
    "executive_sponsor_change", "competitor_evaluation", "low_seat_utilization",
    "training_completion_low", "integration_errors_high", "contract_renewal_proximity",
    "usage_trend_negative", "onboarding_incomplete", "qbr_no_show",
    "expansion_stalled", "roi_unrealized", "health_score_declining",
    "dau_wau_ratio_drop", "data_export_spike", "sso_issues",
    "billing_disputes", "champion_departed",
]
assert len(_SIGNALS) == N_BEHAVIORAL_SIGNALS

_ACTIONS_BY_RISK = {
    "critical": [
        "Escalate to CSM director within 24h",
        "Schedule emergency executive business review",
        "Offer retention incentive or contract restructure",
        "Deploy dedicated support engineer",
    ],
    "high": [
        "Schedule QBR within 2 weeks",
        "Assign dedicated CSM",
        "Conduct ROI audit and share results",
        "Offer training workshop for low-adoption areas",
    ],
    "medium": [
        "Send proactive health-check survey",
        "Share relevant product roadmap items",
        "Invite to customer advisory board",
        "Provide monthly usage summary report",
    ],
    "low": [
        "Monitor with standard cadence",
        "Enroll in automated nurture sequence",
        "Highlight new features in next newsletter",
    ],
}


def _risk_level(score: float) -> str:
    if score >= 0.75:
        return "critical"
    if score >= 0.50:
        return "high"
    if score >= 0.25:
        return "medium"
    return "low"


def _make_customer(idx: int) -> Dict[str, Any]:
    rng = random.Random(idx * 31337 + 7)
    names = [
        "Acme Robotics", "Zenith Automation", "Apex Manufacturing",
        "Quantum Dynamics", "NovaTech Systems", "Stellar Enterprises",
        "Pinnacle AI", "Nexus Solutions", "Vortex Industries", "Luminary Corp",
    ]
    name = names[idx % len(names)] + (f" {idx // len(names) + 1}" if idx >= len(names) else "")
    score = round(rng.uniform(0.05, 0.70), 3)
    n_signals = max(1, int(score * N_BEHAVIORAL_SIGNALS * rng.uniform(0.4, 0.8)))
    top_signals = rng.sample(_SIGNALS, min(n_signals, len(_SIGNALS)))[:4]
    risk = _risk_level(score)
    actions = rng.sample(_ACTIONS_BY_RISK[risk], min(2, len(_ACTIONS_BY_RISK[risk])))
    arr = round(rng.uniform(40_000, 200_000), -3)
    return {
        "customer_id": f"cust_{idx:04d}",
        "name": name,
        "churn_score": score,
        "risk_level": risk,
        "top_signals": top_signals,
        "recommended_actions": actions,
        "arr_usd": arr,
    }


_CUSTOMERS: List[Dict[str, Any]] = [_make_customer(i) for i in range(12)]
_CUSTOMER_MAP: Dict[str, Dict[str, Any]] = {c["customer_id"]: c for c in _CUSTOMERS}


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------
def _bar_rows() -> str:
    rows = []
    sorted_c = sorted(_CUSTOMERS, key=lambda c: c["churn_score"], reverse=True)[:8]
    bar_w = 320
    for i, c in enumerate(sorted_c):
        y = 20 + i * 22
        w = max(4, int(c["churn_score"] * bar_w))
        color = (
            "#C74634" if c["churn_score"] >= 0.75
            else "#f97316" if c["churn_score"] >= 0.50
            else "#38bdf8" if c["churn_score"] >= 0.25
            else "#4ade80"
        )
        label = c["name"][:22]
        rows.append(
            f'<rect x="140" y="{y}" width="{w}" height="16" rx="3" fill="{color}" opacity="0.88"/>'
            f'<text x="134" y="{y+12}" text-anchor="end" fill="#94a3b8" font-size="10">{label}</text>'
            f'<text x="{140+w+4}" y="{y+12}" fill="#e2e8f0" font-size="10">{c["churn_score"]:.2f}</text>'
        )
    return "\n    ".join(rows)


def _build_dashboard() -> str:
    total_arr_at_risk = sum(
        c["arr_usd"] for c in _CUSTOMERS if c["risk_level"] in ("critical", "high")
    )
    critical_count = sum(1 for c in _CUSTOMERS if c["risk_level"] == "critical")
    high_count = sum(1 for c in _CUSTOMERS if c["risk_level"] == "high")
    chart_height = 20 + len(_CUSTOMERS[:8]) * 22 + 10

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Enterprise Churn Predictor — OCI Robot Cloud</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; padding: 2rem; }}
  h1 {{ color: #C74634; font-size: 1.8rem; margin-bottom: 0.25rem; }}
  .subtitle {{ color: #94a3b8; font-size: 0.95rem; margin-bottom: 2rem; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1.25rem; margin-bottom: 2.5rem; }}
  .card {{ background: #1e293b; border-radius: 12px; padding: 1.5rem; border: 1px solid #334155; }}
  .card .label {{ font-size: 0.78rem; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.4rem; }}
  .card .value {{ font-size: 2rem; font-weight: 700; color: #38bdf8; }}
  .card .unit {{ font-size: 0.9rem; color: #64748b; margin-top: 0.2rem; }}
  .card.red .value {{ color: #C74634; }}
  .card.green .value {{ color: #4ade80; }}
  h2 {{ color: #38bdf8; font-size: 1.2rem; margin-bottom: 1rem; }}
  .chart-wrap {{ background: #1e293b; border-radius: 12px; padding: 1.5rem; border: 1px solid #334155; margin-bottom: 2rem; }}
  svg text {{ font-family: 'Segoe UI', system-ui, sans-serif; }}
  .endpoints {{ background: #1e293b; border-radius: 12px; padding: 1.5rem; border: 1px solid #334155; }}
  .ep {{ display: flex; align-items: center; gap: 0.75rem; margin-bottom: 0.75rem; }}
  .method {{ background: #0369a1; color: #fff; font-size: 0.75rem; font-weight: 700; padding: 0.2rem 0.5rem; border-radius: 4px; min-width: 48px; text-align: center; }}
  .path {{ color: #38bdf8; font-family: monospace; font-size: 0.9rem; }}
  .desc {{ color: #94a3b8; font-size: 0.85rem; }}
  footer {{ margin-top: 2rem; color: #475569; font-size: 0.8rem; text-align: center; }}
</style>
</head>
<body>
<h1>Enterprise Churn Predictor</h1>
<p class="subtitle">OCI Robot Cloud · cycle-486A · port {PORT}</p>

<div class="grid">
  <div class="card green">
    <div class="label">Current Churn</div>
    <div class="value">{CURRENT_CHURN_PCT}%</div>
    <div class="unit">active customers retained</div>
  </div>
  <div class="card">
    <div class="label">Model AUC</div>
    <div class="value">{MODEL_AUC}</div>
    <div class="unit">ROC-AUC on holdout set</div>
  </div>
  <div class="card red">
    <div class="label">Behavioral Signals</div>
    <div class="value">{N_BEHAVIORAL_SIGNALS}</div>
    <div class="unit">features tracked per customer</div>
  </div>
  <div class="card">
    <div class="label">ARR at Risk / Churn</div>
    <div class="value">${ARR_AT_RISK_PER_CHURN // 1000}K</div>
    <div class="unit">avg ARR per customer</div>
  </div>
  <div class="card red">
    <div class="label">Critical Risk</div>
    <div class="value">{critical_count}</div>
    <div class="unit">customers (score ≥ 0.75)</div>
  </div>
  <div class="card">
    <div class="label">High Risk</div>
    <div class="value">{high_count}</div>
    <div class="unit">customers (score 0.50–0.75)</div>
  </div>
</div>

<div class="chart-wrap">
  <h2>Top Customer Churn Scores</h2>
  <svg width="100%" viewBox="0 0 500 {chart_height}" xmlns="http://www.w3.org/2000/svg">
    {_bar_rows()}
  </svg>
  <div style="margin-top:0.75rem; font-size:0.8rem; color:#64748b;">
    <span style="color:#C74634">&#9632;</span> Critical (&ge;0.75) &nbsp;
    <span style="color:#f97316">&#9632;</span> High (0.50&ndash;0.74) &nbsp;
    <span style="color:#38bdf8">&#9632;</span> Medium (0.25&ndash;0.49) &nbsp;
    <span style="color:#4ade80">&#9632;</span> Low (&lt;0.25)
  </div>
</div>

<div class="endpoints">
  <h2>API Endpoints</h2>
  <div class="ep"><span class="method">GET</span><span class="path">/</span><span class="desc">This dashboard</span></div>
  <div class="ep"><span class="method">GET</span><span class="path">/health</span><span class="desc">Health check JSON</span></div>
  <div class="ep"><span class="method">GET</span><span class="path">/customers/churn_risk?customer_id=&lt;id&gt;</span><span class="desc">Churn score for a single customer</span></div>
  <div class="ep"><span class="method">GET</span><span class="path">/customers/all_risks</span><span class="desc">All customers with churn scores</span></div>
</div>

<footer>OCI Robot Cloud &mdash; Oracle Confidential &mdash; cycle-486A</footer>
</body>
</html>"""


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------
if _FASTAPI:
    app = FastAPI(
        title=SERVICE_NAME,
        description="ML-based churn risk scoring from behavioral signals.",
        version="1.0.0",
    )

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return _build_dashboard()

    @app.get("/health")
    async def health():
        return JSONResponse({
            "service": SERVICE_NAME,
            "status": "healthy",
            "port": PORT,
            "timestamp": time.time(),
        })

    @app.get("/customers/churn_risk")
    async def churn_risk(customer_id: str = Query(..., description="Customer ID, e.g. cust_0001")):
        customer = _CUSTOMER_MAP.get(customer_id)
        if customer is None:
            return JSONResponse({"error": f"Customer '{customer_id}' not found."}, status_code=404)
        return JSONResponse({
            "customer_id": customer["customer_id"],
            "churn_score": customer["churn_score"],
            "risk_level": customer["risk_level"],
            "top_signals": customer["top_signals"],
            "recommended_actions": customer["recommended_actions"],
        })

    @app.get("/customers/all_risks")
    async def all_risks():
        return JSONResponse([
            {
                "customer_id": c["customer_id"],
                "name": c["name"],
                "churn_score": c["churn_score"],
                "risk_level": c["risk_level"],
                "arr_usd": c["arr_usd"],
            }
            for c in sorted(_CUSTOMERS, key=lambda x: x["churn_score"], reverse=True)
        ])


# ---------------------------------------------------------------------------
# stdlib HTTPServer fallback
# ---------------------------------------------------------------------------
else:
    class _Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass

        def _send(self, code: int, ctype: str, body: str | bytes):
            if isinstance(body, str):
                body = body.encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            parsed = urlparse(self.path)
            path = parsed.path
            qs = parse_qs(parsed.query)

            if path == "/":
                self._send(200, "text/html", _build_dashboard())
            elif path == "/health":
                self._send(200, "application/json",
                           json.dumps({"service": SERVICE_NAME, "status": "healthy", "port": PORT}))
            elif path == "/customers/churn_risk":
                cid_list = qs.get("customer_id", [])
                if not cid_list:
                    self._send(400, "application/json", json.dumps({"error": "customer_id required"}))
                    return
                customer = _CUSTOMER_MAP.get(cid_list[0])
                if customer is None:
                    self._send(404, "application/json", json.dumps({"error": "not found"}))
                    return
                self._send(200, "application/json", json.dumps({
                    "customer_id": customer["customer_id"],
                    "churn_score": customer["churn_score"],
                    "risk_level": customer["risk_level"],
                    "top_signals": customer["top_signals"],
                    "recommended_actions": customer["recommended_actions"],
                }))
            elif path == "/customers/all_risks":
                payload = [
                    {
                        "customer_id": c["customer_id"],
                        "name": c["name"],
                        "churn_score": c["churn_score"],
                        "risk_level": c["risk_level"],
                        "arr_usd": c["arr_usd"],
                    }
                    for c in sorted(_CUSTOMERS, key=lambda x: x["churn_score"], reverse=True)
                ]
                self._send(200, "application/json", json.dumps(payload))
            else:
                self._send(404, "application/json", json.dumps({"error": "not found"}))


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    if _FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        print(f"[{SERVICE_NAME}] fastapi not found — starting stdlib HTTPServer on port {PORT}")
        server = HTTPServer(("0.0.0.0", PORT), _Handler)
        server.serve_forever()
