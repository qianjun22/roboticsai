"""Enterprise Deal Desk Service — port 10261

Enterprise deal approval and structuring: custom terms, discount approval workflows,
and contract review. Avg cycle 3 days, 94% approval rate, avg 8% discount.
"""

import json
import time
from datetime import datetime

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    _FASTAPI_AVAILABLE = True
except ImportError:
    _FASTAPI_AVAILABLE = False

PORT = 10261
SERVICE_NAME = "enterprise_deal_desk"

_DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Enterprise Deal Desk — OCI Robot Cloud</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; padding: 2rem; }
    h1 { color: #C74634; font-size: 1.8rem; margin-bottom: 0.4rem; }
    .subtitle { color: #38bdf8; font-size: 0.95rem; margin-bottom: 2rem; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-bottom: 2rem; }
    .card { background: #1e293b; border-radius: 10px; padding: 1.2rem; border: 1px solid #334155; }
    .card .label { font-size: 0.75rem; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.05em; }
    .card .value { font-size: 1.6rem; font-weight: 700; color: #38bdf8; margin-top: 0.3rem; }
    .card .note { font-size: 0.8rem; color: #64748b; margin-top: 0.2rem; }
    .chart-box { background: #1e293b; border-radius: 10px; padding: 1.5rem; border: 1px solid #334155; margin-bottom: 2rem; }
    .chart-box h2 { color: #C74634; font-size: 1rem; margin-bottom: 1rem; }
    .endpoints { background: #1e293b; border-radius: 10px; padding: 1.5rem; border: 1px solid #334155; }
    .endpoints h2 { color: #C74634; font-size: 1rem; margin-bottom: 1rem; }
    .ep { display: flex; align-items: center; gap: 0.75rem; padding: 0.5rem 0; border-bottom: 1px solid #0f172a; }
    .ep:last-child { border-bottom: none; }
    .method { font-size: 0.7rem; font-weight: 700; padding: 0.2rem 0.5rem; border-radius: 4px; }
    .get { background: #0369a1; color: #e0f2fe; }
    .post { background: #065f46; color: #d1fae5; }
    .path { font-family: monospace; font-size: 0.85rem; color: #cbd5e1; }
    .tier-table { width: 100%; border-collapse: collapse; margin-top: 0.75rem; font-size: 0.85rem; }
    .tier-table th { color: #94a3b8; text-align: left; padding: 0.4rem 0.5rem; border-bottom: 1px solid #334155; }
    .tier-table td { padding: 0.4rem 0.5rem; border-bottom: 1px solid #1e293b; }
  </style>
</head>
<body>
  <h1>Enterprise Deal Desk</h1>
  <p class="subtitle">Custom terms &middot; discount approval &middot; contract review &mdash; port {PORT}</p>

  <div class="grid">
    <div class="card"><div class="label">Approval Rate</div><div class="value">94%</div><div class="note">last 90 days</div></div>
    <div class="card"><div class="label">Avg Cycle Time</div><div class="value">3 days</div><div class="note">submission to approval</div></div>
    <div class="card"><div class="label">Avg Discount</div><div class="value">8%</div><div class="note">across approved deals</div></div>
    <div class="card"><div class="label">Renegotiations</div><div class="value">0</div><div class="note">post-signature</div></div>
  </div>

  <div class="chart-box">
    <h2>Discount Approval Tiers</h2>
    <svg viewBox="0 0 520 180" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:520px;display:block;">
      <!-- Axes -->
      <line x1="100" y1="10" x2="100" y2="150" stroke="#334155" stroke-width="1"/>
      <line x1="100" y1="150" x2="500" y2="150" stroke="#334155" stroke-width="1"/>

      <!-- AE-only tier: <5% discount, fastest (width ~160) -->
      <rect x="100" y="30" width="160" height="28" fill="#38bdf8" rx="3"/>
      <text x="270" y="49" fill="#e2e8f0" font-size="12">&lt;5% — AE only</text>
      <text x="90" y="49" fill="#94a3b8" font-size="10" text-anchor="end">AE</text>

      <!-- VP tier: 5-15%, medium (width ~280) -->
      <rect x="100" y="72" width="280" height="28" fill="#C74634" rx="3"/>
      <text x="390" y="91" fill="#e2e8f0" font-size="12">5-15% — VP approval</text>
      <text x="90" y="91" fill="#94a3b8" font-size="10" text-anchor="end">VP</text>

      <!-- CEO tier: >15%, full bar (width ~390) -->
      <rect x="100" y="114" width="390" height="28" fill="#475569" rx="3"/>
      <text x="498" y="133" fill="#e2e8f0" font-size="12" text-anchor="end">&gt;15% — CEO approval</text>
      <text x="90" y="133" fill="#94a3b8" font-size="10" text-anchor="end">CEO</text>
    </svg>
  </div>

  <div class="endpoints">
    <h2>Endpoints</h2>
    <div class="ep"><span class="method get">GET</span><span class="path">/health</span></div>
    <div class="ep"><span class="method get">GET</span><span class="path">/</span></div>
    <div class="ep"><span class="method post">POST</span><span class="path">/deals/desk/submit</span></div>
    <div class="ep"><span class="method get">GET</span><span class="path">/deals/desk/status</span></div>
  </div>
</body>
</html>
""".replace("{PORT}", str(PORT))


if _FASTAPI_AVAILABLE:
    app = FastAPI(title=SERVICE_NAME, version="1.0.0")

    @app.get("/health")
    async def health():
        return JSONResponse({
            "status": "ok",
            "port": PORT,
            "service": SERVICE_NAME,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        })

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return HTMLResponse(content=_DASHBOARD_HTML)

    @app.post("/deals/desk/submit")
    async def submit_deal(
        account_name: str = "Acme Corp",
        arr_usd: float = 500000.0,
        discount_pct: float = 8.0,
        custom_terms: bool = False,
    ):
        """Stub: submit a deal for desk review and approval routing."""
        deal_id = f"DEAL-{int(time.time())}"
        if discount_pct < 5.0:
            approver = "AE"
            estimated_days = 0
        elif discount_pct <= 15.0:
            approver = "VP Sales"
            estimated_days = 2
        else:
            approver = "CEO"
            estimated_days = 5

        return JSONResponse({
            "deal_id": deal_id,
            "account_name": account_name,
            "arr_usd": arr_usd,
            "discount_pct": discount_pct,
            "custom_terms": custom_terms,
            "status": "submitted",
            "approval_tier": approver,
            "estimated_cycle_days": estimated_days,
            "message": f"Deal submitted. Routed to {approver} for approval.",
            "submitted_at": datetime.utcnow().isoformat() + "Z",
        })

    @app.get("/deals/desk/status")
    async def deal_status(deal_id: str = "DEAL-latest"):
        """Stub: return deal approval status."""
        return JSONResponse({
            "deal_id": deal_id,
            "status": "approved",
            "approval_tier": "VP Sales",
            "discount_pct": 8.0,
            "approved_by": "VP Sales",
            "cycle_days": 3,
            "metrics_summary": {
                "approval_rate_pct": 94,
                "avg_cycle_days": 3,
                "avg_discount_pct": 8,
                "post_signature_renegotiations": 0,
            },
            "approved_at": datetime.utcnow().isoformat() + "Z",
        })

else:
    # Fallback: stdlib HTTP server
    import http.server

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/health":
                body = json.dumps({"status": "ok", "port": PORT, "service": SERVICE_NAME}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)
            else:
                body = _DASHBOARD_HTML.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(body)

        def log_message(self, fmt, *args):
            pass

    def _serve():
        server = http.server.HTTPServer(("0.0.0.0", PORT), _Handler)
        print(f"[{SERVICE_NAME}] fallback HTTP server on port {PORT}")
        server.serve_forever()


if __name__ == "__main__":
    if _FASTAPI_AVAILABLE:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        _serve()
