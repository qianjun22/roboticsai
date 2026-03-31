"""enterprise_legal_tracker.py — Enterprise contract pipeline & compliance tracking (port 10069).

Cycle-503A | OCI Robot Cloud
Tracks MSA/LOI status, outstanding legal items, renewal dates, and compliance framework readiness.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

try:
    from fastapi import FastAPI, Query
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    _FASTAPI = True
except ImportError:
    _FASTAPI = False
    from http.server import BaseHTTPRequestHandler, HTTPServer
    from urllib.parse import urlparse, parse_qs

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
PORT = 10069
SERVICE = "enterprise_legal_tracker"
VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------
CONTRACTS: dict[str, dict[str, Any]] = {
    "machina": {
        "customer": "Machina Labs",
        "status": "MSA Signed",
        "contract_type": "MSA",
        "outstanding_items": [],
        "renewal_date": "2027-03-15",
        "arr": 180000,
        "cycle_days": 18,
    },
    "verdant": {
        "customer": "Verdant Robotics",
        "status": "MSA Signed",
        "contract_type": "MSA",
        "outstanding_items": ["Addendum A: data residency clause under review"],
        "renewal_date": "2027-06-01",
        "arr": 240000,
        "cycle_days": 22,
    },
    "helix": {
        "customer": "Helix Systems",
        "status": "MSA Signed",
        "contract_type": "MSA",
        "outstanding_items": [],
        "renewal_date": "2027-09-30",
        "arr": 120000,
        "cycle_days": 29,
    },
    "viam": {
        "customer": "Viam Inc.",
        "status": "LOI Signed",
        "contract_type": "LOI",
        "outstanding_items": ["MSA negotiation in progress", "Procurement review pending"],
        "renewal_date": "N/A",
        "arr": 0,
        "cycle_days": 23,
    },
}

COMPLIANCE: dict[str, dict[str, Any]] = {
    "soc2": {
        "framework": "SOC 2 Type II",
        "status": "In Preparation",
        "evidence": [
            "Access control policies documented",
            "Encryption at rest enabled (AES-256)",
            "Audit logging active across all services",
        ],
        "gaps": [
            "Vendor risk management questionnaires incomplete",
            "Business continuity plan draft pending final review",
        ],
        "target_date": "2026-09-30",
    },
    "gdpr": {
        "framework": "GDPR",
        "status": "Compliant",
        "evidence": [
            "Data processing agreements (DPAs) in place for all EU customers",
            "Right-to-erasure workflow implemented",
            "Privacy notice updated 2026-01-10",
        ],
        "gaps": [],
        "target_date": "N/A",
    },
    "export_controls": {
        "framework": "Export Controls (EAR/ITAR)",
        "status": "Review In Progress",
        "evidence": [
            "ECCNs classified for all software components",
            "End-use screening enabled in CRM",
        ],
        "gaps": [
            "Technology control plan (TCP) pending Oracle Legal sign-off",
        ],
        "target_date": "2026-06-30",
    },
    "nvidia_license": {
        "framework": "NVIDIA License Compliance",
        "status": "Compliant",
        "evidence": [
            "GR00T N1.6 NVIDIA Research License — non-commercial terms honored",
            "Production use restricted to OCI internal fine-tuning; no redistribution",
            "License review completed 2026-02-15",
        ],
        "gaps": [
            "Commercial license negotiation required before GA customer deployment",
        ],
        "target_date": "2026-12-31",
    },
}

# ---------------------------------------------------------------------------
# HTML Dashboard
# ---------------------------------------------------------------------------
HTML_DASHBOARD = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Enterprise Legal Tracker | OCI Robot Cloud</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; min-height: 100vh; }
    header { background: #1e293b; border-bottom: 2px solid #C74634; padding: 18px 32px; display: flex; align-items: center; gap: 16px; }
    header h1 { font-size: 1.4rem; font-weight: 700; color: #f8fafc; }
    header .badge { background: #C74634; color: #fff; border-radius: 4px; padding: 2px 10px; font-size: 0.75rem; font-weight: 600; }
    .container { max-width: 1100px; margin: 0 auto; padding: 32px 24px; }
    .kpi-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 28px; }
    .kpi { background: #1e293b; border-radius: 10px; padding: 20px; border-left: 4px solid #38bdf8; }
    .kpi.green { border-left-color: #22c55e; }
    .kpi.yellow { border-left-color: #fbbf24; }
    .kpi.red { border-left-color: #C74634; }
    .kpi label { font-size: 0.72rem; color: #94a3b8; text-transform: uppercase; letter-spacing: .05em; }
    .kpi .val { font-size: 2rem; font-weight: 700; color: #f8fafc; margin-top: 4px; }
    .kpi .sub { font-size: 0.8rem; color: #64748b; margin-top: 2px; }
    .grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }
    .card { background: #1e293b; border-radius: 10px; padding: 24px; margin-bottom: 0; }
    .card h2 { font-size: 1rem; font-weight: 600; color: #38bdf8; margin-bottom: 16px; }
    table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
    th { color: #64748b; font-weight: 600; text-transform: uppercase; font-size: 0.72rem; letter-spacing: .05em; padding: 0 0 10px 0; text-align: left; }
    td { padding: 10px 0; border-top: 1px solid #334155; color: #cbd5e1; }
    .chip { display: inline-block; border-radius: 12px; padding: 2px 10px; font-size: 0.75rem; font-weight: 600; }
    .chip.signed { background: #14532d; color: #86efac; }
    .chip.loi { background: #1e3a5f; color: #7dd3fc; }
    .chip.prep { background: #451a03; color: #fdba74; }
    .chip.ok { background: #14532d; color: #86efac; }
    .chip.review { background: #451a03; color: #fdba74; }
    footer { text-align: center; color: #475569; font-size: 0.75rem; padding: 24px; }
  </style>
</head>
<body>
<header>
  <h1>Enterprise Legal Tracker</h1>
  <span class="badge">PORT 10069</span>
  <span style="margin-left:auto;color:#64748b;font-size:0.8rem;">OCI Robot Cloud · Cycle-503A</span>
</header>
<div class="container">
  <div class="kpi-row">
    <div class="kpi green">
      <label>MSA Signed</label>
      <div class="val">3</div>
      <div class="sub">Machina · Verdant · Helix</div>
    </div>
    <div class="kpi">
      <label>LOI Signed</label>
      <div class="val">1</div>
      <div class="sub">Viam — MSA in progress</div>
    </div>
    <div class="kpi yellow">
      <label>Avg Contract Cycle</label>
      <div class="val">23 days</div>
      <div class="sub">Target: 15 days</div>
    </div>
    <div class="kpi red">
      <label>SOC 2 Type II</label>
      <div class="val">Q3 2026</div>
      <div class="sub">In preparation</div>
    </div>
  </div>

  <div class="grid2">
    <div class="card">
      <h2>Contract Pipeline</h2>
      <table>
        <thead>
          <tr><th>Customer</th><th>Status</th><th>Renewal</th><th>Cycle</th></tr>
        </thead>
        <tbody>
          <tr>
            <td>Machina Labs</td>
            <td><span class="chip signed">MSA Signed</span></td>
            <td>2027-03-15</td>
            <td>18d</td>
          </tr>
          <tr>
            <td>Verdant Robotics</td>
            <td><span class="chip signed">MSA Signed</span></td>
            <td>2027-06-01</td>
            <td>22d</td>
          </tr>
          <tr>
            <td>Helix Systems</td>
            <td><span class="chip signed">MSA Signed</span></td>
            <td>2027-09-30</td>
            <td>29d</td>
          </tr>
          <tr>
            <td>Viam Inc.</td>
            <td><span class="chip loi">LOI Signed</span></td>
            <td>N/A</td>
            <td>23d</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="card">
      <h2>Contract Cycle Days (vs 15-day target)</h2>
      <svg viewBox="0 0 320 180" width="100%" height="180">
        <rect width="320" height="180" fill="#1e293b" rx="8"/>
        <!-- Target line at x = 60 + (15/35)*220 = 60+94 = 154 -->
        <line x1="154" y1="16" x2="154" y2="164" stroke="#22c55e" stroke-width="1.5" stroke-dasharray="5,3"/>
        <text x="156" y="14" fill="#22c55e" font-size="10">Target 15d</text>
        <!-- Machina: 18d → 60 + (18/35)*220 = 60+113 = 173 -->
        <rect x="60" y="24" width="113" height="28" rx="4" fill="#38bdf8" opacity="0.85"/>
        <text x="178" y="44" fill="#f8fafc" font-size="12" font-weight="600">18d</text>
        <text x="4" y="44" fill="#94a3b8" font-size="10">Machina</text>
        <!-- Verdant: 22d → 60 + (22/35)*220 = 60+138 = 198 -->
        <rect x="60" y="68" width="138" height="28" rx="4" fill="#38bdf8" opacity="0.85"/>
        <text x="202" y="88" fill="#f8fafc" font-size="12" font-weight="600">22d</text>
        <text x="4" y="88" fill="#94a3b8" font-size="10">Verdant</text>
        <!-- Helix: 29d → 60 + (29/35)*220 = 60+182 = 242 -->
        <rect x="60" y="112" width="182" height="28" rx="4" fill="#C74634" opacity="0.85"/>
        <text x="246" y="132" fill="#f8fafc" font-size="12" font-weight="600">29d</text>
        <text x="4" y="132" fill="#94a3b8" font-size="10">Helix</text>
        <!-- Viam: 23d → 60 + (23/35)*220 = 60+145 = 205 -->
        <rect x="60" y="156" width="145" height="16" rx="4" fill="#64748b" opacity="0.7"/>
        <text x="209" y="169" fill="#f8fafc" font-size="11" font-weight="600">23d</text>
        <text x="4" y="169" fill="#94a3b8" font-size="10">Viam</text>
      </svg>
    </div>
  </div>

  <div class="card" style="margin-top:24px;">
    <h2>Compliance Framework Status</h2>
    <table>
      <thead>
        <tr><th>Framework</th><th>Status</th><th>Target Date</th><th>Open Gaps</th></tr>
      </thead>
      <tbody>
        <tr>
          <td>SOC 2 Type II</td>
          <td><span class="chip prep">In Preparation</span></td>
          <td>2026-09-30</td>
          <td>2 items</td>
        </tr>
        <tr>
          <td>GDPR</td>
          <td><span class="chip ok">Compliant</span></td>
          <td>N/A</td>
          <td>0 items</td>
        </tr>
        <tr>
          <td>Export Controls (EAR/ITAR)</td>
          <td><span class="chip review">Review In Progress</span></td>
          <td>2026-06-30</td>
          <td>1 item</td>
        </tr>
        <tr>
          <td>NVIDIA License Compliance</td>
          <td><span class="chip ok">Compliant</span></td>
          <td>2026-12-31</td>
          <td>1 item (commercial)</td>
        </tr>
      </tbody>
    </table>
  </div>
</div>
<footer>OCI Robot Cloud — Enterprise Legal Tracker | Cycle-503A | Port 10069</footer>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# FastAPI Application
# ---------------------------------------------------------------------------
if _FASTAPI:
    app = FastAPI(
        title="Enterprise Legal Tracker",
        description="Contract pipeline and compliance status tracking for OCI Robot Cloud.",
        version=VERSION,
    )

    @app.get("/", response_class=HTMLResponse)
    async def dashboard() -> HTMLResponse:
        return HTMLResponse(content=HTML_DASHBOARD)

    @app.get("/health")
    async def health() -> JSONResponse:
        return JSONResponse({
            "service": SERVICE,
            "version": VERSION,
            "status": "ok",
            "port": PORT,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    @app.get("/legal/contracts")
    async def get_contracts(
        customer_id: str = Query(default="", description="Customer key: machina, verdant, helix, viam")
    ) -> JSONResponse:
        if customer_id:
            key = customer_id.lower()
            if key not in CONTRACTS:
                return JSONResponse(
                    {"error": f"Unknown customer_id '{customer_id}'. Valid: {list(CONTRACTS.keys())}"},
                    status_code=404,
                )
            return JSONResponse(CONTRACTS[key])
        return JSONResponse({"contracts": CONTRACTS})

    @app.get("/legal/compliance")
    async def get_compliance(
        framework: str = Query(default="", description="Framework key: soc2, gdpr, export_controls, nvidia_license")
    ) -> JSONResponse:
        if framework:
            key = framework.lower()
            if key not in COMPLIANCE:
                return JSONResponse(
                    {"error": f"Unknown framework '{framework}'. Valid: {list(COMPLIANCE.keys())}"},
                    status_code=404,
                )
            return JSONResponse(COMPLIANCE[key])
        return JSONResponse({"compliance": COMPLIANCE})

else:
    # ---------------------------------------------------------------------------
    # stdlib HTTPServer fallback
    # ---------------------------------------------------------------------------
    class _Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:
            pass

        def _send(self, code: int, body: str, content_type: str = "application/json") -> None:
            encoded = body.encode()
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            qs = parse_qs(parsed.query)

            if parsed.path == "/":
                self._send(200, HTML_DASHBOARD, "text/html; charset=utf-8")
            elif parsed.path == "/health":
                self._send(200, json.dumps({
                    "service": SERVICE, "version": VERSION,
                    "status": "ok", "port": PORT,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }))
            elif parsed.path == "/legal/contracts":
                cid = qs.get("customer_id", [""])[0].lower()
                if cid:
                    if cid in CONTRACTS:
                        self._send(200, json.dumps(CONTRACTS[cid]))
                    else:
                        self._send(404, json.dumps({"error": f"Unknown customer_id '{cid}'"}))
                else:
                    self._send(200, json.dumps({"contracts": CONTRACTS}))
            elif parsed.path == "/legal/compliance":
                fw = qs.get("framework", [""])[0].lower()
                if fw:
                    if fw in COMPLIANCE:
                        self._send(200, json.dumps(COMPLIANCE[fw]))
                    else:
                        self._send(404, json.dumps({"error": f"Unknown framework '{fw}'"}))
                else:
                    self._send(200, json.dumps({"compliance": COMPLIANCE}))
            else:
                self._send(404, json.dumps({"error": "not found"}))


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    if _FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        server = HTTPServer(("0.0.0.0", PORT), _Handler)
        print(f"[{SERVICE}] stdlib fallback server on port {PORT}")
        server.serve_forever()
