"""customer_lifecycle_manager.py — Full-lifecycle customer management service (port 10075).

Cycle-504B: Tracks prospects through trial → active → expand → renew → advocate with
stage-based playbooks and CLV analytics.
"""

from __future__ import annotations

import json
import random
from datetime import datetime, timezone
from typing import Any

try:
    from fastapi import FastAPI, HTTPException, Query
    from fastapi.responses import HTMLResponse, JSONResponse
    from pydantic import BaseModel
    import uvicorn
    _FASTAPI = True
except ImportError:  # pragma: no cover
    _FASTAPI = False
    from http.server import BaseHTTPRequestHandler, HTTPServer  # type: ignore

PORT = 10075
SERVICE_NAME = "customer_lifecycle_manager"
VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# Domain data
# ---------------------------------------------------------------------------
LIFECYCLE_STAGES = ["prospect", "trial", "active", "expand", "renew", "advocate"]

STAGE_CRITERIA: dict[str, list[str]] = {
    "prospect":  ["Demo completed", "Use-case qualified", "Budget confirmed"],
    "trial":     ["Pilot signed", "First workload running", "Champion identified"],
    "active":    ["Full deployment", "3+ robots trained", "Success metric baseline set"],
    "expand":    ["2nd fleet site", "Multi-task policies live", "QBR completed"],
    "renew":     ["Contract renewal signed", "NPS ≥ 8", "Renewal upsell discussed"],
    "advocate":  ["Case study published", "Reference call given", "Community contribution"],
}

PLAYBOOKS: dict[str, str] = {
    "prospect":  "pb_prospect_discovery_v3",
    "trial":     "pb_trial_onboarding_v5",
    "active":    "pb_active_expansion_v4",
    "expand":    "pb_expand_multisite_v2",
    "renew":     "pb_renewal_qbr_v3",
    "advocate":  "pb_advocate_community_v1",
}

# Seeded customer DB
_CUSTOMERS: dict[str, dict[str, Any]] = {
    "machina-001": {
        "name": "Machina Labs",
        "current_stage": "expand",
        "stage_duration_days": 18,
        "health_score": 91.5,
        "clv": 415_000,
        "robots": 6,
        "segment": "enterprise",
    },
    "apptronik-002": {
        "name": "Apptronik",
        "current_stage": "active",
        "stage_duration_days": 45,
        "health_score": 84.0,
        "clv": 280_000,
        "robots": 4,
        "segment": "enterprise",
    },
    "agility-003": {
        "name": "Agility Robotics",
        "current_stage": "trial",
        "stage_duration_days": 22,
        "health_score": 76.5,
        "clv": 195_000,
        "robots": 3,
        "segment": "mid-market",
    },
    "sanctuary-004": {
        "name": "Sanctuary AI",
        "current_stage": "renew",
        "stage_duration_days": 8,
        "health_score": 88.0,
        "clv": 320_000,
        "robots": 5,
        "segment": "enterprise",
    },
    "skild-005": {
        "name": "Skild AI",
        "current_stage": "prospect",
        "stage_duration_days": 5,
        "health_score": 68.0,
        "clv": 120_000,
        "robots": 0,
        "segment": "startup",
    },
    "figure-006": {
        "name": "Figure AI",
        "current_stage": "advocate",
        "stage_duration_days": 90,
        "health_score": 97.0,
        "clv": 580_000,
        "robots": 12,
        "segment": "enterprise",
    },
}

# Stage velocity (median days to exit each stage)
_STAGE_VELOCITY: dict[str, int] = {
    "prospect": 14,
    "trial": 30,
    "active": 60,
    "expand": 45,
    "renew": 21,
    "advocate": 180,
}

# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------
DASHBOARD_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>Customer Lifecycle Manager</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; padding: 24px; }
  h1 { color: #C74634; font-size: 1.6rem; margin-bottom: 4px; }
  .subtitle { color: #94a3b8; font-size: 0.875rem; margin-bottom: 24px; }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 32px; }
  .card { background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 20px; }
  .card h3 { color: #38bdf8; font-size: 0.75rem; text-transform: uppercase; letter-spacing: .08em; margin-bottom: 8px; }
  .card .value { font-size: 2rem; font-weight: 700; color: #f1f5f9; }
  .card .unit { font-size: 0.8rem; color: #64748b; margin-top: 2px; }
  .section-title { color: #38bdf8; font-size: 1rem; font-weight: 600; margin-bottom: 12px; }
  .chart-wrap { background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 20px; margin-bottom: 32px; }
  .badge { display: inline-block; background: #C74634; color: #fff; border-radius: 6px; padding: 2px 10px; font-size: 0.75rem; font-weight: 600; margin-left: 8px; vertical-align: middle; }
  .stage-row { display: flex; align-items: center; gap: 0; margin-bottom: 16px; flex-wrap: wrap; }
  .stage-box { flex: 1; min-width: 90px; padding: 10px 6px; text-align: center; background: #0f172a; border: 1px solid #334155; font-size: 0.75rem; color: #94a3b8; position: relative; }
  .stage-box.active-stage { background: #C74634; color: #fff; font-weight: 700; border-color: #C74634; }
  .stage-box .stage-count { font-size: 1.25rem; font-weight: 700; color: #38bdf8; display: block; }
  .stage-box.active-stage .stage-count { color: #fff; }
  .arrow { color: #334155; font-size: 1.2rem; padding: 0 2px; align-self: center; }
  table { width: 100%; border-collapse: collapse; font-size: 0.875rem; }
  th { color: #38bdf8; text-align: left; padding: 8px 12px; border-bottom: 1px solid #334155; }
  td { padding: 8px 12px; border-bottom: 1px solid #1e293b; color: #cbd5e1; }
  tr:hover td { background: #1e293b; }
  .hs-high { color: #4ade80; } .hs-mid { color: #facc15; } .hs-low { color: #f87171; }
  .stage-pill { display: inline-block; border-radius: 12px; padding: 2px 10px; font-size: 0.7rem; font-weight: 600; }
  .sp-prospect { background:#1e3a5f; color:#93c5fd; } .sp-trial { background:#1e4040; color:#5eead4; }
  .sp-active { background:#1a3a1a; color:#4ade80; } .sp-expand { background:#3d2b00; color:#fbbf24; }
  .sp-renew { background:#3d1a1a; color:#f87171; } .sp-advocate { background:#2d1a4d; color:#c084fc; }
  footer { margin-top: 32px; color: #475569; font-size: 0.75rem; text-align: center; }
  .highlight { color: #C74634; font-weight: 700; }
</style>
</head>
<body>
<h1>Customer Lifecycle Manager <span class="badge">LIVE</span></h1>
<p class="subtitle">Full lifecycle: prospect → trial → active → expand → renew → advocate &nbsp;|&nbsp; OCI Robot Cloud cycle-504B &nbsp;|&nbsp; port 10075</p>

<div class="grid">
  <div class="card"><h3>Total Customers</h3><div class="value">6</div><div class="unit">across all stages</div></div>
  <div class="card"><h3>Total CLV Pipeline</h3><div class="value" style="color:#C74634">$1.91M</div><div class="unit">combined lifetime value</div></div>
  <div class="card"><h3>Spotlight</h3><div class="value" style="font-size:1.2rem">Machina Labs</div><div class="unit highlight">Approaching expand → renew ↑</div></div>
  <div class="card"><h3>Avg Health Score</h3><div class="value">84.2</div><div class="unit">/ 100 across active customers</div></div>
  <div class="card"><h3>Advocates</h3><div class="value">1</div><div class="unit">Figure AI — CLV $580K</div></div>
  <div class="card"><h3>At-Risk (health &lt;75)</h3><div class="value" style="color:#facc15">1</div><div class="unit">Skild AI — prospect stage</div></div>
</div>

<div class="chart-wrap">
  <div class="section-title">Lifecycle Stage Distribution</div>
  <div class="stage-row">
    <div class="stage-box"><span class="stage-count">1</span>Prospect<br/><small>~14d median</small></div>
    <div class="arrow">›</div>
    <div class="stage-box"><span class="stage-count">1</span>Trial<br/><small>~30d median</small></div>
    <div class="arrow">›</div>
    <div class="stage-box"><span class="stage-count">1</span>Active<br/><small>~60d median</small></div>
    <div class="arrow">›</div>
    <div class="stage-box active-stage"><span class="stage-count">1</span>Expand<br/><small>~45d median</small></div>
    <div class="arrow">›</div>
    <div class="stage-box"><span class="stage-count">1</span>Renew<br/><small>~21d median</small></div>
    <div class="arrow">›</div>
    <div class="stage-box"><span class="stage-count">1</span>Advocate<br/><small>~180d median</small></div>
  </div>
  <p style="color:#64748b; font-size:0.8rem; margin-top:8px;">Active stage highlighted in Oracle red — Machina Labs in Expand stage (day 18 of ~45)</p>
</div>

<div class="chart-wrap">
  <div class="section-title">CLV by Stage — Bar Chart</div>
  <svg viewBox="0 0 580 230" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:620px;display:block;margin:auto">
    <!-- axes -->
    <line x1="70" y1="10" x2="70" y2="185" stroke="#334155" stroke-width="1"/>
    <line x1="70" y1="185" x2="560" y2="185" stroke="#334155" stroke-width="1"/>
    <!-- y labels ($K) -->
    <text x="62" y="189" fill="#64748b" font-size="10" text-anchor="end">0</text>
    <text x="62" y="152" fill="#64748b" font-size="10" text-anchor="end">100K</text>
    <text x="62" y="115" fill="#64748b" font-size="10" text-anchor="end">200K</text>
    <text x="62" y="78" fill="#64748b" font-size="10" text-anchor="end">300K</text>
    <text x="62" y="41" fill="#64748b" font-size="10" text-anchor="end">400K</text>
    <text x="62" y="14" fill="#64748b" font-size="10" text-anchor="end">500K</text>
    <!-- grid lines -->
    <line x1="70" y1="152" x2="560" y2="152" stroke="#1e293b" stroke-dasharray="4" stroke-width="1"/>
    <line x1="70" y1="115" x2="560" y2="115" stroke="#1e293b" stroke-dasharray="4" stroke-width="1"/>
    <line x1="70" y1="78" x2="560" y2="78" stroke="#1e293b" stroke-dasharray="4" stroke-width="1"/>
    <line x1="70" y1="41" x2="560" y2="41" stroke="#1e293b" stroke-dasharray="4" stroke-width="1"/>
    <!-- bars: scale 500K→175px -->
    <!-- Skild 120K → 42px, y=185-42=143 -->
    <rect x="80" y="143" width="58" height="42" fill="#93c5fd" rx="3"/>
    <text x="109" y="137" fill="#93c5fd" font-size="9" text-anchor="middle">$120K</text>
    <text x="109" y="208" fill="#94a3b8" font-size="10" text-anchor="middle">Skild</text>
    <text x="109" y="218" fill="#64748b" font-size="9" text-anchor="middle">(prospect)</text>
    <!-- Agility 195K → 68px, y=185-68=117 -->
    <rect x="158" y="117" width="58" height="68" fill="#5eead4" rx="3"/>
    <text x="187" y="111" fill="#5eead4" font-size="9" text-anchor="middle">$195K</text>
    <text x="187" y="208" fill="#94a3b8" font-size="10" text-anchor="middle">Agility</text>
    <text x="187" y="218" fill="#64748b" font-size="9" text-anchor="middle">(trial)</text>
    <!-- Apptronik 280K → 98px, y=185-98=87 -->
    <rect x="236" y="87" width="58" height="98" fill="#4ade80" rx="3"/>
    <text x="265" y="81" fill="#4ade80" font-size="9" text-anchor="middle">$280K</text>
    <text x="265" y="208" fill="#94a3b8" font-size="10" text-anchor="middle">Apptronik</text>
    <text x="265" y="218" fill="#64748b" font-size="9" text-anchor="middle">(active)</text>
    <!-- Machina 415K → 145px, y=185-145=40 -->
    <rect x="314" y="40" width="58" height="145" fill="#C74634" rx="3"/>
    <text x="343" y="34" fill="#C74634" font-size="9" text-anchor="middle" font-weight="bold">$415K</text>
    <text x="343" y="208" fill="#94a3b8" font-size="10" text-anchor="middle">Machina</text>
    <text x="343" y="218" fill="#64748b" font-size="9" text-anchor="middle">(expand)</text>
    <!-- Sanctuary 320K → 112px, y=185-112=73 -->
    <rect x="392" y="73" width="58" height="112" fill="#f87171" rx="3"/>
    <text x="421" y="67" fill="#f87171" font-size="9" text-anchor="middle">$320K</text>
    <text x="421" y="208" fill="#94a3b8" font-size="10" text-anchor="middle">Sanctuary</text>
    <text x="421" y="218" fill="#64748b" font-size="9" text-anchor="middle">(renew)</text>
    <!-- Figure 580K → 175px → capped at 175, y=185-175=10 -->
    <rect x="470" y="10" width="58" height="175" fill="#c084fc" rx="3"/>
    <text x="499" y="8" fill="#c084fc" font-size="9" text-anchor="middle">$580K</text>
    <text x="499" y="208" fill="#94a3b8" font-size="10" text-anchor="middle">Figure AI</text>
    <text x="499" y="218" fill="#64748b" font-size="9" text-anchor="middle">(advocate)</text>
  </svg>
</div>

<div class="chart-wrap">
  <div class="section-title">Customer Roster &amp; Stage Velocity</div>
  <table>
    <thead><tr><th>Customer</th><th>Stage</th><th>Days in Stage</th><th>Median Exit</th><th>Health Score</th><th>CLV</th></tr></thead>
    <tbody>
      <tr>
        <td><strong>Machina Labs</strong></td>
        <td><span class="stage-pill sp-expand">expand</span></td>
        <td>18</td><td>~45d</td>
        <td class="hs-high">91.5</td><td class="hs-high">$415K</td>
      </tr>
      <tr>
        <td>Apptronik</td>
        <td><span class="stage-pill sp-active">active</span></td>
        <td>45</td><td>~60d</td>
        <td class="hs-high">84.0</td><td>$280K</td>
      </tr>
      <tr>
        <td>Agility Robotics</td>
        <td><span class="stage-pill sp-trial">trial</span></td>
        <td>22</td><td>~30d</td>
        <td class="hs-mid">76.5</td><td>$195K</td>
      </tr>
      <tr>
        <td>Sanctuary AI</td>
        <td><span class="stage-pill sp-renew">renew</span></td>
        <td>8</td><td>~21d</td>
        <td class="hs-high">88.0</td><td>$320K</td>
      </tr>
      <tr>
        <td>Skild AI</td>
        <td><span class="stage-pill sp-prospect">prospect</span></td>
        <td>5</td><td>~14d</td>
        <td class="hs-low">68.0</td><td>$120K</td>
      </tr>
      <tr>
        <td>Figure AI</td>
        <td><span class="stage-pill sp-advocate">advocate</span></td>
        <td>90</td><td>~180d</td>
        <td class="hs-high">97.0</td><td class="hs-high">$580K</td>
      </tr>
    </tbody>
  </table>
</div>

<footer>OCI Robot Cloud &mdash; Customer Lifecycle Manager &mdash; cycle-504B &mdash; port 10075</footer>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------
if _FASTAPI:
    class StageTransitionRequest(BaseModel):  # type: ignore[misc]
        customer_id: str
        new_stage: str


# ---------------------------------------------------------------------------
# Business logic
# ---------------------------------------------------------------------------

def _get_lifecycle(customer_id: str) -> dict[str, Any] | None:
    cust = _CUSTOMERS.get(customer_id)
    if not cust:
        return None
    stage = cust["current_stage"]
    return {
        "customer_id": customer_id,
        "customer_name": cust["name"],
        "current_stage": stage,
        "stage_duration_days": cust["stage_duration_days"],
        "next_stage_criteria": STAGE_CRITERIA.get(stage, []),
        "health_score": cust["health_score"],
        "clv": cust["clv"],
        "median_exit_days": _STAGE_VELOCITY.get(stage, 30),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _transition_stage(customer_id: str, new_stage: str) -> dict[str, Any] | None:
    if new_stage not in LIFECYCLE_STAGES:
        return None
    cust = _CUSTOMERS.get(customer_id)
    if not cust:
        return None
    old_stage = cust["current_stage"]
    cust["current_stage"] = new_stage
    cust["stage_duration_days"] = 0
    # Simulate health-score nudge on stage advance
    old_idx = LIFECYCLE_STAGES.index(old_stage) if old_stage in LIFECYCLE_STAGES else 0
    new_idx = LIFECYCLE_STAGES.index(new_stage)
    if new_idx > old_idx:
        cust["health_score"] = round(min(100.0, cust["health_score"] + random.uniform(1, 4)), 1)
    return {
        "customer_id": customer_id,
        "customer_name": cust["name"],
        "previous_stage": old_stage,
        "updated_lifecycle": _get_lifecycle(customer_id),
        "triggered_playbook": PLAYBOOKS[new_stage],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _health() -> dict[str, Any]:
    return {
        "service": SERVICE_NAME,
        "version": VERSION,
        "port": PORT,
        "status": "healthy",
        "customers_tracked": len(_CUSTOMERS),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
if _FASTAPI:
    app = FastAPI(
        title="Customer Lifecycle Manager",
        description="Full customer lifecycle from prospect through advocate with stage-based playbooks",
        version=VERSION,
    )

    @app.get("/", response_class=HTMLResponse)
    async def dashboard() -> HTMLResponse:
        return HTMLResponse(content=DASHBOARD_HTML)

    @app.get("/health")
    async def health() -> JSONResponse:
        return JSONResponse(_health())

    @app.get("/customers/lifecycle")
    async def get_lifecycle(customer_id: str = Query(..., description="Customer identifier")) -> JSONResponse:
        data = _get_lifecycle(customer_id)
        if data is None:
            raise HTTPException(status_code=404, detail=f"Customer '{customer_id}' not found")
        return JSONResponse(data)

    @app.post("/customers/stage_transition")
    async def stage_transition(req: StageTransitionRequest) -> JSONResponse:  # type: ignore[name-defined]
        if req.new_stage not in LIFECYCLE_STAGES:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid stage '{req.new_stage}'. Valid: {LIFECYCLE_STAGES}",
            )
        result = _transition_stage(req.customer_id, req.new_stage)
        if result is None:
            raise HTTPException(status_code=404, detail=f"Customer '{req.customer_id}' not found")
        return JSONResponse(result)


# ---------------------------------------------------------------------------
# stdlib fallback
# ---------------------------------------------------------------------------
else:  # pragma: no cover
    class _Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:  # noqa: D401
            pass

        def _send(self, code: int, ctype: str, body: str | bytes) -> None:
            data = body.encode() if isinstance(body, str) else body
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self) -> None:
            if self.path in ("/", ""):
                self._send(200, "text/html", DASHBOARD_HTML)
            elif self.path == "/health":
                self._send(200, "application/json", json.dumps(_health()))
            elif self.path.startswith("/customers/lifecycle"):
                from urllib.parse import urlparse, parse_qs
                qs = parse_qs(urlparse(self.path).query)
                cid = qs.get("customer_id", [None])[0]
                if not cid:
                    self._send(422, "application/json", json.dumps({"detail": "customer_id required"}))
                    return
                data = _get_lifecycle(cid)
                if data is None:
                    self._send(404, "application/json", json.dumps({"detail": "not found"}))
                else:
                    self._send(200, "application/json", json.dumps(data))
            else:
                self._send(404, "application/json", json.dumps({"detail": "not found"}))

        def do_POST(self) -> None:
            if self.path == "/customers/stage_transition":
                length = int(self.headers.get("Content-Length", 0))
                raw = self.rfile.read(length)
                try:
                    payload = json.loads(raw)
                except json.JSONDecodeError:
                    payload = {}
                cid = payload.get("customer_id", "")
                ns = payload.get("new_stage", "")
                if ns not in LIFECYCLE_STAGES:
                    self._send(422, "application/json", json.dumps({"detail": f"invalid stage {ns}"}))
                    return
                result = _transition_stage(cid, ns)
                if result is None:
                    self._send(404, "application/json", json.dumps({"detail": "not found"}))
                else:
                    self._send(200, "application/json", json.dumps(result))
            else:
                self._send(404, "application/json", json.dumps({"detail": "not found"}))

    def _run_stdlib() -> None:
        server = HTTPServer(("0.0.0.0", PORT), _Handler)
        print(f"[{SERVICE_NAME}] stdlib HTTPServer running on port {PORT}")
        server.serve_forever()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    if _FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:  # pragma: no cover
        _run_stdlib()
