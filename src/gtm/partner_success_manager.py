"""Partner Success Manager — Proactive partner success with QBR cadence and milestone tracking.

Port: 10039
Cycle: 495B
"""

from __future__ import annotations

import json
import random
from datetime import datetime, timedelta
from typing import Any

try:
    from fastapi import FastAPI, Query
    from fastapi.responses import HTMLResponse, JSONResponse
    from pydantic import BaseModel
    import uvicorn
    _FASTAPI = True
except ImportError:
    _FASTAPI = False
    from http.server import BaseHTTPRequestHandler, HTTPServer
    import urllib.parse as _up

PORT = 10039
SERVICE_NAME = "partner_success_manager"
VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# Mock partner data
# ---------------------------------------------------------------------------
PARTNERS: dict[str, dict] = {
    "acme_robotics": {
        "name": "ACME Robotics",
        "tier": "Premier",
        "health_score": 91.0,
        "milestones": {"onboarding": True, "first_deployment": True, "case_study": True, "renewal": True},
        "milestone_days": {"onboarding": 14, "first_deployment": 32, "case_study": 61, "renewal": 90},
        "qbr_date": "2026-04-15",
        "next_action": "Schedule Q2 QBR and explore GR00T N2 upgrade path",
        "nps": 78,
    },
    "deepmind_mfg": {
        "name": "DeepMind Manufacturing",
        "tier": "Strategic",
        "health_score": 88.5,
        "milestones": {"onboarding": True, "first_deployment": True, "case_study": False, "renewal": True},
        "milestone_days": {"onboarding": 10, "first_deployment": 28, "case_study": None, "renewal": 85},
        "qbr_date": "2026-04-22",
        "next_action": "Drive case study co-authorship; share ACME Robotics template",
        "nps": 72,
    },
    "boston_dynamics_oci": {
        "name": "Boston Dynamics OCI",
        "tier": "Premier",
        "health_score": 94.2,
        "milestones": {"onboarding": True, "first_deployment": True, "case_study": True, "renewal": True},
        "milestone_days": {"onboarding": 7, "first_deployment": 21, "case_study": 55, "renewal": 78},
        "qbr_date": "2026-04-08",
        "next_action": "Upsell multi-GPU DDP tier; present ROI analysis",
        "nps": 82,
    },
}

DEFAULT_PARTNER = "acme_robotics"

QBR_AGENDA_TEMPLATE = [
    "Welcome & relationship health review",
    "Q1 usage metrics and ROI highlights",
    "Fine-tuning pipeline performance walkthrough (MAE, throughput)",
    "Roadmap preview: GR00T N2, multi-GPU DDP, Isaac Sim SDG",
    "Partner feedback and open issues",
    "Co-marketing & case study opportunities",
    "Q2 success plan and milestone targets",
    "Next steps and action items",
]

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Partner Success Manager | OCI Robot Cloud</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; min-height: 100vh; }
    header {
      background: linear-gradient(135deg, #C74634 0%, #a03828 100%);
      padding: 1.5rem 2rem;
      display: flex; align-items: center; justify-content: space-between;
    }
    header h1 { font-size: 1.4rem; font-weight: 700; letter-spacing: 0.02em; }
    header span { font-size: 0.8rem; background: rgba(255,255,255,0.15); padding: 0.25rem 0.75rem; border-radius: 9999px; }
    .container { max-width: 1100px; margin: 0 auto; padding: 2rem; }
    .kpi-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-bottom: 2rem; }
    .kpi {
      background: #1e293b; border: 1px solid #334155; border-radius: 0.75rem;
      padding: 1.25rem; text-align: center;
    }
    .kpi .label { font-size: 0.75rem; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 0.4rem; }
    .kpi .value { font-size: 2rem; font-weight: 700; color: #38bdf8; }
    .kpi .sub { font-size: 0.75rem; color: #64748b; margin-top: 0.2rem; }
    .card {
      background: #1e293b; border: 1px solid #334155; border-radius: 0.75rem;
      padding: 1.5rem; margin-bottom: 1.5rem;
    }
    .card h2 { font-size: 1rem; font-weight: 600; color: #38bdf8; margin-bottom: 1.25rem; text-transform: uppercase; letter-spacing: 0.06em; }
    .badge {
      display: inline-block; font-size: 0.7rem; font-weight: 600;
      padding: 0.2rem 0.55rem; border-radius: 9999px; margin-left: 0.5rem;
    }
    .badge-green  { background: #14532d; color: #4ade80; }
    .badge-blue   { background: 0c4a6e; color: #38bdf8; }
    .badge-orange { background: #431407; color: #fb923c; }
    .partner-row {
      display: flex; align-items: center; justify-content: space-between;
      padding: 0.75rem 0; border-bottom: 1px solid #334155;
      font-size: 0.85rem;
    }
    .partner-row:last-child { border-bottom: none; }
    .health-pill {
      display: inline-block; padding: 0.2rem 0.65rem; border-radius: 9999px; font-weight: 700; font-size: 0.8rem;
    }
    .health-high  { background: #14532d; color: #4ade80; }
    .health-med   { background: #1c3d5a; color: #38bdf8; }
    footer { text-align: center; padding: 2rem; font-size: 0.75rem; color: #475569; }
  </style>
</head>
<body>
<header>
  <h1>Partner Success Manager</h1>
  <span>Port 10039 &nbsp;|&nbsp; Cycle 495B</span>
</header>
<div class="container">

  <div class="kpi-grid">
    <div class="kpi">
      <div class="label">QBR Coverage</div>
      <div class="value">100%</div>
      <div class="sub">all partners scheduled</div>
    </div>
    <div class="kpi">
      <div class="label">Avg Milestone</div>
      <div class="value">47d</div>
      <div class="sub">time-to-first-deployment</div>
    </div>
    <div class="kpi">
      <div class="label">Case Study Conv.</div>
      <div class="value">67%</div>
      <div class="sub">2 of 3 partners</div>
    </div>
    <div class="kpi">
      <div class="label">Renewal Rate</div>
      <div class="value">100%</div>
      <div class="sub">Q1 2026</div>
    </div>
    <div class="kpi">
      <div class="label">Avg NPS</div>
      <div class="value">74</div>
      <div class="sub">across premier partners</div>
    </div>
  </div>

  <div class="card">
    <h2>Partner Health Overview</h2>
    <!-- SVG bar chart: health scores -->
    <svg viewBox="0 0 700 200" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:auto;display:block;margin-bottom:1rem;">
      <!-- grid lines (60-100 range, each 10pp = 35px) -->
      <line x1="100" y1="20" x2="680" y2="20" stroke="#334155" stroke-width="1"/>
      <line x1="100" y1="55" x2="680" y2="55" stroke="#334155" stroke-width="1"/>
      <line x1="100" y1="90" x2="680" y2="90" stroke="#334155" stroke-width="1"/>
      <line x1="100" y1="125" x2="680" y2="125" stroke="#334155" stroke-width="1"/>
      <line x1="100" y1="160" x2="680" y2="160" stroke="#334155" stroke-width="1"/>
      <!-- y-axis -->
      <text x="90" y="23"  fill="#64748b" font-size="11" text-anchor="end">100</text>
      <text x="90" y="58"  fill="#64748b" font-size="11" text-anchor="end">90</text>
      <text x="90" y="93"  fill="#64748b" font-size="11" text-anchor="end">80</text>
      <text x="90" y="128" fill="#64748b" font-size="11" text-anchor="end">70</text>
      <text x="90" y="163" fill="#64748b" font-size="11" text-anchor="end">60</text>
      <!-- ACME 91 => height=(91-60)*3.5=108.5 top=160-108.5=51.5 -->
      <rect x="130" y="51"  width="120" height="109" rx="4" fill="#38bdf8" opacity="0.9"/>
      <text x="190" y="45"  fill="#38bdf8" font-size="13" font-weight="bold" text-anchor="middle">91.0</text>
      <text x="190" y="180" fill="#94a3b8" font-size="11" text-anchor="middle">ACME Robotics</text>
      <!-- DeepMind 88.5 => height=98.75 top=61.25 -->
      <rect x="290" y="61"  width="120" height="99"  rx="4" fill="#38bdf8" opacity="0.75"/>
      <text x="350" y="55"  fill="#38bdf8" font-size="13" font-weight="bold" text-anchor="middle">88.5</text>
      <text x="350" y="180" fill="#94a3b8" font-size="11" text-anchor="middle">DeepMind Mfg</text>
      <!-- Boston 94.2 => height=120.7 top=39.3 -->
      <rect x="450" y="39"  width="120" height="121" rx="4" fill="#C74634" opacity="0.85"/>
      <text x="510" y="33"  fill="#f87171" font-size="13" font-weight="bold" text-anchor="middle">94.2</text>
      <text x="510" y="180" fill="#94a3b8" font-size="11" text-anchor="middle">Boston Dynamics</text>
      <!-- target line at 85 => y=160-(85-60)*3.5=160-87.5=72.5 -->
      <line x1="100" y1="72" x2="680" y2="72" stroke="#f59e0b" stroke-width="1.5" stroke-dasharray="6,4"/>
      <text x="682" y="75" fill="#f59e0b" font-size="10">target 85</text>
    </svg>

    <div class="partner-row">
      <div><strong>ACME Robotics</strong> &mdash; Premier &nbsp;&bull;&nbsp; QBR: Apr 15</div>
      <span class="health-pill health-high">91.0</span>
    </div>
    <div class="partner-row">
      <div><strong>DeepMind Manufacturing</strong> &mdash; Strategic &nbsp;&bull;&nbsp; QBR: Apr 22</div>
      <span class="health-pill health-med">88.5</span>
    </div>
    <div class="partner-row">
      <div><strong>Boston Dynamics OCI</strong> &mdash; Premier &nbsp;&bull;&nbsp; QBR: Apr 8</div>
      <span class="health-pill health-high">94.2</span>
    </div>
  </div>

  <div class="card">
    <h2>Endpoints</h2>
    <table style="width:100%;border-collapse:collapse;font-size:0.85rem;">
      <thead>
        <tr style="border-bottom:1px solid #334155;">
          <th style="text-align:left;padding:0.5rem 0;color:#64748b;">Method</th>
          <th style="text-align:left;padding:0.5rem 0;color:#64748b;">Path</th>
          <th style="text-align:left;padding:0.5rem 0;color:#64748b;">Description</th>
        </tr>
      </thead>
      <tbody>
        <tr style="border-bottom:1px solid #1e293b;">
          <td style="padding:0.5rem 0;"><span class="badge badge-green">GET</span></td>
          <td style="padding:0.5rem 0;color:#38bdf8;">/</td>
          <td style="padding:0.5rem 0;">This dashboard</td>
        </tr>
        <tr style="border-bottom:1px solid #1e293b;">
          <td style="padding:0.5rem 0;"><span class="badge badge-green">GET</span></td>
          <td style="padding:0.5rem 0;color:#38bdf8;">/health</td>
          <td style="padding:0.5rem 0;">JSON health check</td>
        </tr>
        <tr style="border-bottom:1px solid #1e293b;">
          <td style="padding:0.5rem 0;"><span class="badge badge-green">GET</span></td>
          <td style="padding:0.5rem 0;color:#38bdf8;">/partners/success_status?partner_id=acme_robotics</td>
          <td style="padding:0.5rem 0;">Partner milestone + health snapshot</td>
        </tr>
        <tr>
          <td style="padding:0.5rem 0;"><span class="badge badge-orange">POST</span></td>
          <td style="padding:0.5rem 0;color:#38bdf8;">/partners/qbr</td>
          <td style="padding:0.5rem 0;">Generate QBR agenda and action items</td>
        </tr>
      </tbody>
    </table>
  </div>

</div>
<footer>OCI Robot Cloud &mdash; Partner Success Manager &mdash; Port 10039 &mdash; Cycle 495B</footer>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
if _FASTAPI:
    app = FastAPI(
        title="Partner Success Manager",
        description="Proactive partner success management with QBR cadence and milestone tracking",
        version=VERSION,
    )

    class QBRRequest(BaseModel):
        partner_id: str
        quarter: str = "Q2-2026"

    @app.get("/", response_class=HTMLResponse)
    async def dashboard() -> HTMLResponse:
        return HTMLResponse(content=DASHBOARD_HTML)

    @app.get("/health")
    async def health() -> JSONResponse:
        return JSONResponse({
            "service": SERVICE_NAME,
            "status": "healthy",
            "version": VERSION,
            "port": PORT,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        })

    @app.get("/partners/success_status")
    async def success_status(partner_id: str = Query(default=DEFAULT_PARTNER)) -> JSONResponse:
        p = PARTNERS.get(partner_id)
        if p is None:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail=f"Partner '{partner_id}' not found")
        return JSONResponse({
            "partner_id": partner_id,
            "name": p["name"],
            "tier": p["tier"],
            "milestone_completion": p["milestones"],
            "milestone_days": p["milestone_days"],
            "qbr_date": p["qbr_date"],
            "health_score": p["health_score"],
            "nps": p["nps"],
            "next_action": p["next_action"],
        })

    @app.post("/partners/qbr")
    async def qbr(req: QBRRequest) -> JSONResponse:
        p = PARTNERS.get(req.partner_id)
        if p is None:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail=f"Partner '{req.partner_id}' not found")
        action_items = [
            f"Share {req.quarter} roadmap preview deck with {p['name']}",
            "Confirm renewal terms and expansion SKUs",
            "Identify co-marketing case study timeline",
            "Review open support tickets and SLA compliance",
            "Schedule next QBR date + assign CSM follow-ups",
        ]
        return JSONResponse({
            "partner_id": req.partner_id,
            "partner_name": p["name"],
            "quarter": req.quarter,
            "qbr_agenda": QBR_AGENDA_TEMPLATE,
            "action_items": action_items,
            "health_score": p["health_score"],
            "nps": p["nps"],
        })

# ---------------------------------------------------------------------------
# stdlib fallback
# ---------------------------------------------------------------------------
else:
    class _Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:
            pass

        def _send(self, code: int, body: str, ct: str = "application/json") -> None:
            enc = body.encode()
            self.send_response(code)
            self.send_header("Content-Type", ct)
            self.send_header("Content-Length", str(len(enc)))
            self.end_headers()
            self.wfile.write(enc)

        def do_GET(self) -> None:
            parsed = _up.urlparse(self.path)
            path = parsed.path
            params = dict(_up.parse_qsl(parsed.query))
            if path == "/":
                self._send(200, DASHBOARD_HTML, "text/html; charset=utf-8")
            elif path == "/health":
                self._send(200, json.dumps({"service": SERVICE_NAME, "status": "healthy", "version": VERSION, "port": PORT}))
            elif path == "/partners/success_status":
                pid = params.get("partner_id", DEFAULT_PARTNER)
                p = PARTNERS.get(pid)
                if p is None:
                    self._send(404, json.dumps({"detail": f"Partner '{pid}' not found"}))
                else:
                    self._send(200, json.dumps({"partner_id": pid, "name": p["name"], "milestone_completion": p["milestones"], "qbr_date": p["qbr_date"], "health_score": p["health_score"], "next_action": p["next_action"]}))
            else:
                self._send(404, json.dumps({"detail": "not found"}))

        def do_POST(self) -> None:
            path = self.path.split("?")[0]
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length)) if length else {}
            if path == "/partners/qbr":
                pid = body.get("partner_id", DEFAULT_PARTNER)
                quarter = body.get("quarter", "Q2-2026")
                p = PARTNERS.get(pid)
                if p is None:
                    self._send(404, json.dumps({"detail": f"Partner '{pid}' not found"}))
                else:
                    action_items = [f"Share {quarter} roadmap preview with {p['name']}", "Confirm renewal terms", "Identify case study timeline"]
                    self._send(200, json.dumps({"qbr_agenda": QBR_AGENDA_TEMPLATE, "action_items": action_items, "health_score": p["health_score"]}))
            else:
                self._send(404, json.dumps({"detail": "not found"}))


if __name__ == "__main__":
    if _FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        server = HTTPServer(("0.0.0.0", PORT), _Handler)
        print(f"[{SERVICE_NAME}] stdlib HTTPServer on port {PORT}")
        server.serve_forever()
