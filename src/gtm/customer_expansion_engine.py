"""Customer Expansion Engine — identify and execute upsell/cross-sell opportunities.

Port: 10023
Cycle: 491B
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

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
# Constants
# ---------------------------------------------------------------------------
PORT = 10023

_OPPORTUNITIES = [
    {
        "customer_id": "machina-robotics",
        "customer_name": "Machina Robotics",
        "opportunity_type": "multi-gpu-training",
        "estimated_acv": 41000.0,
        "current_acv": 96000.0,
        "expansion_signal": "GPU utilization >90% for 30 consecutive days",
        "playbook_step": "Schedule capacity review → propose A100 × 8 cluster upgrade",
        "confidence": 0.87,
    },
    {
        "customer_id": "verdant-ag",
        "customer_name": "Verdant Ag",
        "opportunity_type": "sdg-dataset-gen",
        "estimated_acv": 28000.0,
        "current_acv": 54000.0,
        "expansion_signal": "Requested Isaac Sim quote twice in 60 days",
        "playbook_step": "Demo SDG pipeline → land 500-demo/month package",
        "confidence": 0.79,
    },
    {
        "customer_id": "helix-dynamics",
        "customer_name": "Helix Dynamics",
        "opportunity_type": "policy-distillation",
        "estimated_acv": 15000.0,
        "current_acv": 38000.0,
        "expansion_signal": "Opened policy distillation docs 14 times last month",
        "playbook_step": "Send distillation case study → offer 30-day POC",
        "confidence": 0.72,
    },
]

_CUSTOMER_MAP = {o["customer_id"]: o for o in _OPPORTUNITIES}

_PROPOSAL_TEMPLATES = {
    "multi-gpu-training": (
        "Based on your sustained GPU utilization, we recommend upgrading to an A100 × 8 cluster. "
        "This will reduce your training wall-clock time by ~3× and unlock DDP fine-tuning at scale. "
        "Estimated onboarding: 5 business days."
    ),
    "sdg-dataset-gen": (
        "We propose adding the OCI Robot Cloud SDG package powered by Isaac Sim RTX. "
        "You'll generate photorealistic demonstrations with domain randomization at 500 demos/month, "
        "eliminating the need for physical robot time. Estimated onboarding: 3 business days."
    ),
    "policy-distillation": (
        "Our policy distillation service compresses your GR00T N1.6 model to a 4× smaller student "
        "network with <2% SR degradation — ideal for edge/Jetson deployment. "
        "We recommend a 30-day POC at no additional cost to validate against your task suite."
    ),
}

_DEFAULT_PROPOSAL = (
    "Thank you for your continued partnership. Based on your current usage patterns, "
    "our team has identified an expansion opportunity aligned with your roadmap. "
    "A dedicated solution architect will reach out within 2 business days."
)


def _get_opportunities(threshold_acv: float) -> list[dict]:
    return [
        {
            "customer_id": o["customer_id"],
            "customer_name": o["customer_name"],
            "opportunity_type": o["opportunity_type"],
            "estimated_acv": o["estimated_acv"],
            "expansion_signal": o["expansion_signal"],
            "playbook_step": o["playbook_step"],
            "confidence": o["confidence"],
        }
        for o in _OPPORTUNITIES
        if o["estimated_acv"] >= threshold_acv
    ]


def _build_proposal(customer_id: str, opportunity_type: str) -> dict:
    opp = _CUSTOMER_MAP.get(customer_id)
    if opp is None:
        return {
            "proposal_draft": _DEFAULT_PROPOSAL,
            "estimated_acv": 0.0,
            "timeline_days": 14,
            "customer_id": customer_id,
            "opportunity_type": opportunity_type,
        }
    template = _PROPOSAL_TEMPLATES.get(opportunity_type, _DEFAULT_PROPOSAL)
    return {
        "proposal_draft": template,
        "estimated_acv": opp["estimated_acv"],
        "timeline_days": 5 if opportunity_type == "multi-gpu-training" else 10,
        "customer_id": customer_id,
        "opportunity_type": opportunity_type,
        "confidence": opp["confidence"],
    }


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------
DAR_BG = "#0f172a"
ORACLE_RED = "#C74634"
SKY_BLUE = "#38bdf8"

HTML_DASHBOARD = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Customer Expansion Engine — OCI Robot Cloud</title>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{background:{bg};color:#e2e8f0;font-family:'Segoe UI',system-ui,sans-serif;padding:2rem}}
    h1{{color:{red};font-size:1.6rem;margin-bottom:0.25rem}}
    .sub{{color:{sky};font-size:0.9rem;margin-bottom:2rem}}
    .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:1.25rem;margin-bottom:2rem}}
    .card{{background:#1e293b;border:1px solid #334155;border-radius:10px;padding:1.25rem}}
    .card .label{{font-size:0.75rem;color:#94a3b8;text-transform:uppercase;letter-spacing:.06em;margin-bottom:.4rem}}
    .card .value{{font-size:2rem;font-weight:700;color:{sky}}}
    .card .unit{{font-size:0.8rem;color:#64748b;margin-top:.15rem}}
    .badge{{display:inline-block;background:{red};color:#fff;border-radius:6px;padding:.15rem .6rem;font-size:0.75rem;margin-left:.5rem}}
    .chart-wrap{{background:#1e293b;border:1px solid #334155;border-radius:10px;padding:1.5rem;margin-bottom:2rem}}
    .chart-title{{color:{sky};font-size:1rem;font-weight:600;margin-bottom:1rem}}
    .signals{{list-style:none;padding:0}}
    .signals li{{padding:.45rem 0;border-bottom:1px solid #1e293b;font-size:.875rem;color:#cbd5e1}}
    .signals li::before{{content:"▸ ";color:{red}}}
    table{{width:100%;border-collapse:collapse;font-size:.875rem}}
    th{{text-align:left;color:#94a3b8;border-bottom:1px solid #334155;padding:.5rem 0}}
    td{{padding:.5rem 0;border-bottom:1px solid #1e293b}}
    td.num{{text-align:right;color:{sky};font-weight:600}}
    footer{{margin-top:2rem;font-size:.75rem;color:#475569;text-align:center}}
  </style>
</head>
<body>
  <h1>Customer Expansion Engine <span class="badge">GTM</span></h1>
  <div class="sub">Port 10023 &mdash; Cycle 491B &mdash; Upsell / Cross-sell Pipeline</div>

  <div class="grid">
    <div class="card"><div class="label">Total Expansion Pipeline</div><div class="value">$84K</div><div class="unit">across 3 accounts</div></div>
    <div class="card"><div class="label">Net Revenue Retention</div><div class="value">118%</div><div class="unit">NRR driven by expansions</div></div>
    <div class="card"><div class="label">Top Opportunity</div><div class="value">$41K</div><div class="unit">Machina — multi-GPU upgrade</div></div>
    <div class="card"><div class="label">Avg Confidence</div><div class="value">79%</div><div class="unit">weighted by ACV</div></div>
  </div>

  <div class="chart-wrap">
    <div class="chart-title">Expansion ACV by Account ($K)</div>
    <svg viewBox="0 0 520 160" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:560px;display:block;margin:0 auto">
      <!-- y-axis -->
      <line x1="50" y1="10" x2="50" y2="130" stroke="#334155" stroke-width="1"/>
      <text x="45" y="135" fill="#94a3b8" font-size="11" text-anchor="end">0</text>
      <text x="45" y="80"  fill="#94a3b8" font-size="11" text-anchor="end">20</text>
      <text x="45" y="30"  fill="#94a3b8" font-size="11" text-anchor="end">40</text>
      <!-- Machina $41K bar height = 41/50*100 = 82 -->
      <rect x="70"  y="48" width="90" height="82" rx="4" fill="{red}" opacity="0.85"/>
      <text x="115" y="43" fill="{red}"  font-size="12" font-weight="bold" text-anchor="middle">$41K</text>
      <text x="115" y="148" fill="#94a3b8" font-size="11" text-anchor="middle">Machina</text>
      <!-- Verdant $28K bar height = 28/50*100 = 56 -->
      <rect x="215" y="74" width="90" height="56" rx="4" fill="{sky}" opacity="0.85"/>
      <text x="260" y="69" fill="{sky}"  font-size="12" font-weight="bold" text-anchor="middle">$28K</text>
      <text x="260" y="148" fill="#94a3b8" font-size="11" text-anchor="middle">Verdant</text>
      <!-- Helix $15K bar height = 15/50*100 = 30 -->
      <rect x="360" y="100" width="90" height="30" rx="4" fill="{red}" opacity="0.55"/>
      <text x="405" y="95"  fill="#e2e8f0" font-size="12" font-weight="bold" text-anchor="middle">$15K</text>
      <text x="405" y="148" fill="#94a3b8" font-size="11" text-anchor="middle">Helix</text>
    </svg>
  </div>

  <div class="chart-wrap">
    <div class="chart-title">Expansion Signals</div>
    <ul class="signals">
      <li>Machina — GPU utilization &gt;90% for 30 consecutive days</li>
      <li>Verdant — Requested Isaac Sim quote twice in 60 days</li>
      <li>Helix — Opened policy distillation docs 14 times last month</li>
      <li>NRR at 118% — expansion motions outpacing churn by 2.3×</li>
      <li>Avg time-to-close for expansion deals: 8 business days</li>
    </ul>
  </div>

  <div class="chart-wrap">
    <div class="chart-title">Opportunity Table</div>
    <table>
      <thead><tr><th>Account</th><th>Type</th><th>Est. ACV</th><th>Confidence</th></tr></thead>
      <tbody>
        <tr><td>Machina Robotics</td><td>Multi-GPU Training</td><td class="num">$41,000</td><td class="num">87%</td></tr>
        <tr><td>Verdant Ag</td><td>SDG Dataset Gen</td><td class="num">$28,000</td><td class="num">79%</td></tr>
        <tr><td>Helix Dynamics</td><td>Policy Distillation</td><td class="num">$15,000</td><td class="num">72%</td></tr>
      </tbody>
    </table>
  </div>

  <footer>OCI Robot Cloud &mdash; Customer Expansion Engine &mdash; {ts}</footer>
</body>
</html>
""".format(bg=DAR_BG, red=ORACLE_RED, sky=SKY_BLUE, ts=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
if _FASTAPI:
    app = FastAPI(title="Customer Expansion Engine", version="1.0.0")

    class ProposalRequest(BaseModel):
        customer_id: str
        opportunity_type: str

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return HTMLResponse(content=HTML_DASHBOARD)

    @app.get("/health")
    async def health():
        return JSONResponse({"status": "ok", "service": "customer_expansion_engine", "port": PORT,
                             "timestamp": datetime.now(timezone.utc).isoformat()})

    @app.get("/customers/expansion_opportunities")
    async def expansion_opportunities(threshold_acv: float = Query(default=0.0, ge=0.0)):
        opps = _get_opportunities(threshold_acv)
        return JSONResponse({
            "opportunities": opps,
            "total_pipeline_acv": sum(o["estimated_acv"] for o in opps),
            "count": len(opps),
            "threshold_acv": threshold_acv,
        })

    @app.post("/customers/expansion_proposal")
    async def expansion_proposal(req: ProposalRequest):
        return JSONResponse(_build_proposal(req.customer_id, req.opportunity_type))

# ---------------------------------------------------------------------------
# Stdlib fallback
# ---------------------------------------------------------------------------
else:
    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urlparse(self.path)
            path = parsed.path
            params = parse_qs(parsed.query)
            if path == "/":
                body = HTML_DASHBOARD.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
            elif path == "/health":
                body = json.dumps({"status": "ok", "service": "customer_expansion_engine", "port": PORT}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
            elif path == "/customers/expansion_opportunities":
                threshold = float(params.get("threshold_acv", ["0"])[0])
                opps = _get_opportunities(threshold)
                body = json.dumps({
                    "opportunities": opps,
                    "total_pipeline_acv": sum(o["estimated_acv"] for o in opps),
                    "count": len(opps),
                    "threshold_acv": threshold,
                }).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
            else:
                body = b"{\"error\": \"not found\"}"
                self.send_response(404)
                self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            path = urlparse(self.path).path
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length)
            try:
                data = json.loads(raw)
            except Exception:
                data = {}
            if path == "/customers/expansion_proposal":
                body = json.dumps(_build_proposal(
                    data.get("customer_id", ""),
                    data.get("opportunity_type", ""),
                )).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
            else:
                body = b"{\"error\": \"not found\"}"
                self.send_response(404)
                self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            pass

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    if _FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        print(f"FastAPI not available — starting stdlib HTTPServer on port {PORT}")
        server = HTTPServer(("0.0.0.0", PORT), _Handler)
        server.serve_forever()
