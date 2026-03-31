"""Enterprise Onboarding Playbook — cycle-494A (port 10033).

Structured T+0 through T+90 enterprise onboarding with milestone tracking.
"""

import json
import time
from datetime import datetime

try:
    from fastapi import FastAPI, Query
    from fastapi.responses import HTMLResponse, JSONResponse
    from pydantic import BaseModel
    import uvicorn
    _FASTAPI = True
except ImportError:
    _FASTAPI = False
    from http.server import BaseHTTPRequestHandler, HTTPServer

# ---------------------------------------------------------------------------
# Domain data
# ---------------------------------------------------------------------------

PHASES = [
    {"id": "kickoff",     "label": "T+0  Kickoff",          "days": (0, 7)},
    {"id": "integration", "label": "T+7  API Integration",  "days": (7, 18)},
    {"id": "validation",  "label": "T+18 Validation",       "days": (18, 35)},
    {"id": "pilot",       "label": "T+35 Pilot",            "days": (35, 60)},
    {"id": "production",  "label": "T+60 Production",       "days": (60, 90)},
]

MILESTONE_ORDER = [
    "kickoff_call",
    "env_provisioned",
    "api_keys_issued",
    "sdk_installed",
    "first_api_call",
    "integration_complete",
    "security_review",
    "uat_passed",
    "pilot_launched",
    "sla_signed",
    "production_go_live",
]

NEXT_STEPS_MAP = {
    "kickoff_call":        ["Provision OCI tenancy", "Issue API keys", "Share SDK docs"],
    "env_provisioned":    ["Install Python SDK", "Configure auth tokens", "Run smoke test"],
    "api_keys_issued":    ["Install SDK", "Test /health endpoint", "Schedule integration call"],
    "sdk_installed":      ["Make first API call", "Review response schema", "Set up error handling"],
    "first_api_call":     ["Complete full integration", "Submit to security review", "Schedule UAT"],
    "integration_complete": ["Run security review checklist", "Schedule UAT session", "Draft SLA"],
    "security_review":    ["Execute UAT test plan", "Resolve any findings", "Get UAT sign-off"],
    "uat_passed":         ["Launch pilot with 1 robot", "Monitor KPIs daily", "Draft SLA terms"],
    "pilot_launched":     ["Collect pilot metrics", "Executive review", "Finalize SLA"],
    "sla_signed":         ["Schedule go-live date", "Brief support team", "Enable production tier"],
    "production_go_live": ["Quarterly business review scheduled", "Expansion discussion", "NPS survey sent"],
}

# In-memory customer state (demo data pre-seeded)
_CUSTOMER_DB: dict = {
    "machina": {
        "name": "Machina Labs",
        "completed_milestones": list(MILESTONE_ORDER),  # T+90 complete
        "days_elapsed": 90,
    },
    "verdant": {
        "name": "Verdant Robotics",
        "completed_milestones": list(MILESTONE_ORDER),  # T+90 complete
        "days_elapsed": 90,
    },
    "helix": {
        "name": "Helix Automation",
        "completed_milestones": list(MILESTONE_ORDER),  # T+90 complete
        "days_elapsed": 90,
    },
}


def _phase_for_milestones(completed: list) -> str:
    n = len(completed)
    if n == 0:
        return "T+0 Kickoff"
    if n <= 3:
        return "T+7 API Integration"
    if n <= 5:
        return "T+18 Validation"
    if n <= 8:
        return "T+35 Pilot"
    if n <= 10:
        return "T+60 Production"
    return "T+90 Complete"


def _days_to_production(completed: list) -> int:
    remaining = len(MILESTONE_ORDER) - len(completed)
    return max(0, remaining * 5)  # ~5 days per milestone


def _milestone_completion_dict(completed: list) -> dict:
    return {m: (m in completed) for m in MILESTONE_ORDER}


def _blockers(completed: list) -> list:
    remaining = [m for m in MILESTONE_ORDER if m not in completed]
    if not remaining:
        return []
    next_m = remaining[0]
    blockers_map = {
        "api_keys_issued":     ["Awaiting OCI tenancy approval"],
        "integration_complete": ["API integration avg 11 days — schedule dedicated eng time"],
        "security_review":    ["Security team queue: 3-5 day wait"],
        "uat_passed":         ["UAT environment setup pending"],
        "production_go_live": ["SLA legal review in progress"],
    }
    return blockers_map.get(next_m, [f"Pending: {next_m.replace('_', ' ')}"])


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Enterprise Onboarding Playbook | OCI Robot Cloud</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; min-height: 100vh; }
    header { background: #C74634; padding: 1.25rem 2rem; display: flex; align-items: center; gap: 1rem; }
    header h1 { font-size: 1.4rem; font-weight: 700; letter-spacing: .02em; }
    header span.badge { background: #38bdf8; color: #0f172a; border-radius: 9999px; padding: 0.2rem 0.75rem; font-size: 0.75rem; font-weight: 700; }
    main { max-width: 1100px; margin: 0 auto; padding: 2rem 1.5rem; }
    h2 { color: #38bdf8; font-size: 1.1rem; margin-bottom: 1rem; text-transform: uppercase; letter-spacing: .06em; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 1.25rem; margin-bottom: 2rem; }
    .card { background: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 1.25rem 1.5rem; }
    .card .label { font-size: 0.78rem; color: #94a3b8; margin-bottom: 0.4rem; text-transform: uppercase; letter-spacing: .05em; }
    .card .value { font-size: 2rem; font-weight: 800; }
    .card .sub { font-size: 0.82rem; color: #64748b; margin-top: 0.25rem; }
    .red { color: #C74634; }
    .blue { color: #38bdf8; }
    .green { color: #4ade80; }
    .yellow { color: #fbbf24; }
    .chart-wrap { background: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 1.5rem; margin-bottom: 2rem; }
    .customer-table { width: 100%; border-collapse: collapse; font-size: 0.88rem; }
    .customer-table th, .customer-table td { padding: 0.65rem 1rem; border-bottom: 1px solid #334155; text-align: left; }
    .customer-table th { color: #94a3b8; font-weight: 600; text-transform: uppercase; font-size: 0.75rem; }
    .pill { display: inline-block; border-radius: 9999px; padding: 0.15rem 0.6rem; font-size: 0.75rem; font-weight: 700; }
    .pill-green { background: #14532d; color: #4ade80; }
    .pill-blue  { background: #0c4a6e; color: #38bdf8; }
    footer { text-align: center; color: #475569; font-size: 0.78rem; padding: 2rem; }
  </style>
</head>
<body>
<header>
  <h1>Enterprise Onboarding Playbook</h1>
  <span class="badge">T+0 &rarr; T+90</span>
  <span class="badge" style="background:#1e293b;color:#38bdf8;">Port 10033</span>
</header>
<main>
  <section class="grid">
    <div class="card">
      <div class="label">Avg Days to Production</div>
      <div class="value red">67</div>
      <div class="sub">Target: 45 days &nbsp;(&minus;22 d gap)</div>
    </div>
    <div class="card">
      <div class="label">Bottleneck</div>
      <div class="value yellow">11 d</div>
      <div class="sub">API Integration phase</div>
    </div>
    <div class="card">
      <div class="label">Customers T+90 Complete</div>
      <div class="value green">3 / 3</div>
      <div class="sub">Machina, Verdant, Helix</div>
    </div>
    <div class="card">
      <div class="label">Milestones per Customer</div>
      <div class="value blue">11</div>
      <div class="sub">Across 5 phases</div>
    </div>
  </section>

  <section class="chart-wrap">
    <h2>Days per Phase (Avg Across Customers)</h2>
    <svg viewBox="0 0 620 230" width="100%" aria-label="Bar chart of days per onboarding phase">
      <!-- axes -->
      <line x1="90" y1="15" x2="90" y2="180" stroke="#334155" stroke-width="1"/>
      <line x1="90" y1="180" x2="590" y2="180" stroke="#334155" stroke-width="1"/>
      <!-- Y labels (max=15 days) -->
      <text x="82" y="183" fill="#64748b" font-size="10" text-anchor="end">0</text>
      <text x="82" y="143" fill="#64748b" font-size="10" text-anchor="end">5</text>
      <text x="82" y="103" fill="#64748b" font-size="10" text-anchor="end">10</text>
      <text x="82" y="63" fill="#64748b" font-size="10" text-anchor="end">15</text>
      <!-- grid -->
      <line x1="90" y1="140" x2="590" y2="140" stroke="#1e293b" stroke-dasharray="4 4" stroke-width="1"/>
      <line x1="90" y1="100" x2="590" y2="100" stroke="#1e293b" stroke-dasharray="4 4" stroke-width="1"/>
      <line x1="90" y1="60"  x2="590" y2="60"  stroke="#1e293b" stroke-dasharray="4 4" stroke-width="1"/>
      <!-- Bars: scale = 165px / 15 days = 11px per day -->
      <!-- Kickoff 7d → 77px, y=180-77=103 -->
      <rect x="100" y="103" width="60" height="77" fill="#38bdf8" rx="3"/>
      <text x="130" y="96" fill="#38bdf8" font-size="11" font-weight="700" text-anchor="middle">7 d</text>
      <text x="130" y="200" fill="#94a3b8" font-size="10" text-anchor="middle">Kickoff</text>
      <!-- API Integration 11d → 121px, y=180-121=59 -->
      <rect x="195" y="59" width="60" height="121" fill="#C74634" rx="3"/>
      <text x="225" y="52" fill="#C74634" font-size="11" font-weight="700" text-anchor="middle">11 d</text>
      <text x="225" y="200" fill="#94a3b8" font-size="10" text-anchor="middle">API Integ.</text>
      <!-- Validation 8d → 88px, y=180-88=92 -->
      <rect x="290" y="92" width="60" height="88" fill="#38bdf8" rx="3"/>
      <text x="320" y="85" fill="#38bdf8" font-size="11" font-weight="700" text-anchor="middle">8 d</text>
      <text x="320" y="200" fill="#94a3b8" font-size="10" text-anchor="middle">Validation</text>
      <!-- Pilot 13d → 143px, y=180-143=37 -->
      <rect x="385" y="37" width="60" height="143" fill="#a855f7" rx="3"/>
      <text x="415" y="30" fill="#a855f7" font-size="11" font-weight="700" text-anchor="middle">13 d</text>
      <text x="415" y="200" fill="#94a3b8" font-size="10" text-anchor="middle">Pilot</text>
      <!-- Production 28d capped at 165px, y=15 -->
      <rect x="480" y="55" width="60" height="125" fill="#4ade80" rx="3"/>
      <text x="510" y="48" fill="#4ade80" font-size="11" font-weight="700" text-anchor="middle">28 d</text>
      <text x="510" y="200" fill="#94a3b8" font-size="10" text-anchor="middle">Production</text>
      <!-- Target line at 45d total → just an annotation -->
      <text x="590" y="183" fill="#fbbf24" font-size="10" text-anchor="end">Target: 45 d total</text>
    </svg>
  </section>

  <section class="chart-wrap">
    <h2>Customer Status</h2>
    <table class="customer-table">
      <thead><tr><th>Customer</th><th>Phase</th><th>Days Elapsed</th><th>Milestones</th><th>Status</th></tr></thead>
      <tbody>
        <tr>
          <td>Machina Labs</td>
          <td>T+90 Complete</td>
          <td>90</td>
          <td>11 / 11</td>
          <td><span class="pill pill-green">Complete</span></td>
        </tr>
        <tr>
          <td>Verdant Robotics</td>
          <td>T+90 Complete</td>
          <td>90</td>
          <td>11 / 11</td>
          <td><span class="pill pill-green">Complete</span></td>
        </tr>
        <tr>
          <td>Helix Automation</td>
          <td>T+90 Complete</td>
          <td>90</td>
          <td>11 / 11</td>
          <td><span class="pill pill-green">Complete</span></td>
        </tr>
      </tbody>
    </table>
  </section>
</main>
<footer>OCI Robot Cloud &mdash; Enterprise Onboarding Playbook &mdash; cycle-494A</footer>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

if _FASTAPI:
    app = FastAPI(
        title="Enterprise Onboarding Playbook",
        description="T+0 through T+90 enterprise onboarding with milestone tracking",
        version="1.0.0",
    )

    class MilestoneRequest(BaseModel):
        customer_id: str
        milestone: str

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return HTMLResponse(content=DASHBOARD_HTML)

    @app.get("/health")
    async def health():
        return JSONResponse({
            "status": "healthy",
            "service": "enterprise_onboarding_playbook",
            "port": 10033,
            "total_milestones": len(MILESTONE_ORDER),
            "phases": len(PHASES),
            "timestamp": datetime.utcnow().isoformat() + "Z",
        })

    @app.get("/onboarding/status")
    async def onboarding_status(customer_id: str = Query(..., description="Customer identifier")):
        cid = customer_id.lower()
        if cid not in _CUSTOMER_DB:
            # Auto-create new customer
            _CUSTOMER_DB[cid] = {"name": customer_id, "completed_milestones": [], "days_elapsed": 0}
        c = _CUSTOMER_DB[cid]
        completed = c["completed_milestones"]
        return {
            "customer_id": cid,
            "customer_name": c["name"],
            "phase": _phase_for_milestones(completed),
            "milestone_completion": _milestone_completion_dict(completed),
            "milestones_done": len(completed),
            "milestones_total": len(MILESTONE_ORDER),
            "days_elapsed": c["days_elapsed"],
            "days_to_production": _days_to_production(completed),
            "blockers": _blockers(completed),
        }

    @app.post("/onboarding/milestone")
    async def complete_milestone(req: MilestoneRequest):
        cid = req.customer_id.lower()
        if cid not in _CUSTOMER_DB:
            _CUSTOMER_DB[cid] = {"name": req.customer_id, "completed_milestones": [], "days_elapsed": 0}
        c = _CUSTOMER_DB[cid]
        if req.milestone not in MILESTONE_ORDER:
            from fastapi import HTTPException
            raise HTTPException(status_code=422, detail=f"Unknown milestone '{req.milestone}'. Valid: {MILESTONE_ORDER}")
        if req.milestone not in c["completed_milestones"]:
            c["completed_milestones"].append(req.milestone)
            c["days_elapsed"] += 5  # ~5 days per milestone
        completed = c["completed_milestones"]
        phase = _phase_for_milestones(completed)
        next_steps = NEXT_STEPS_MAP.get(req.milestone, ["Review dashboard for next milestone"])
        return {
            "customer_id": cid,
            "milestone_completed": req.milestone,
            "updated_status": f"{len(completed)}/{len(MILESTONE_ORDER)} milestones complete",
            "next_steps": next_steps,
            "phase": phase,
            "days_to_production": _days_to_production(completed),
        }

# ---------------------------------------------------------------------------
# HTTPServer fallback
# ---------------------------------------------------------------------------

else:
    class _Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass

        def _send_json(self, data, status=200):
            body = json.dumps(data).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            from urllib.parse import urlparse, parse_qs
            parsed = urlparse(self.path)
            if parsed.path == "/health":
                self._send_json({"status": "healthy", "service": "enterprise_onboarding_playbook", "port": 10033})
            elif parsed.path == "/onboarding/status":
                params = parse_qs(parsed.query)
                cid = params.get("customer_id", ["unknown"])[0].lower()
                if cid not in _CUSTOMER_DB:
                    _CUSTOMER_DB[cid] = {"name": cid, "completed_milestones": [], "days_elapsed": 0}
                c = _CUSTOMER_DB[cid]
                completed = c["completed_milestones"]
                self._send_json({
                    "customer_id": cid,
                    "phase": _phase_for_milestones(completed),
                    "milestone_completion": _milestone_completion_dict(completed),
                    "days_to_production": _days_to_production(completed),
                    "blockers": _blockers(completed),
                })
            else:
                body = DASHBOARD_HTML.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(body)

        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length)
            try:
                data = json.loads(raw)
            except Exception:
                data = {}
            cid = data.get("customer_id", "unknown").lower()
            milestone = data.get("milestone", "")
            if cid not in _CUSTOMER_DB:
                _CUSTOMER_DB[cid] = {"name": cid, "completed_milestones": [], "days_elapsed": 0}
            c = _CUSTOMER_DB[cid]
            if milestone and milestone not in c["completed_milestones"]:
                c["completed_milestones"].append(milestone)
            completed = c["completed_milestones"]
            self._send_json({
                "updated_status": f"{len(completed)}/{len(MILESTONE_ORDER)} milestones complete",
                "next_steps": NEXT_STEPS_MAP.get(milestone, []),
                "phase": _phase_for_milestones(completed),
            })

# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if _FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=10033)
    else:
        print("FastAPI not available — starting stdlib HTTPServer on port 10033")
        server = HTTPServer(("0.0.0.0", 10033), _Handler)
        server.serve_forever()
