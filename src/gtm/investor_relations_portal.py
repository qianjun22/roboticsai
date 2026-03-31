"""Investor relations portal — monthly update generation, live KPI dashboard
(ARR $250K, NRR 118%, SR 85%, burn $45K, runway 18mo), per-investor comms log,
update cadence management.
FastAPI service — OCI Robot Cloud
Port: 10109"""
from __future__ import annotations
import json, math, random, time
from datetime import datetime, timedelta
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    from pydantic import BaseModel
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False
    from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = 10109

# --- Live KPIs ---
_KPIS = {
    "arr_usd": 250_000,
    "nrr_pct": 118,
    "success_rate_pct": 85,
    "monthly_burn_usd": 45_000,
    "runway_months": 18,
    "design_partners": 4,
    "pilots_active": 2,
    "models_deployed": 7,
    "inference_latency_ms": 235,
}

_MILESTONES = [
    {"date": "2026-01-15", "title": "GR00T N1.6 integration", "status": "complete"},
    {"date": "2026-02-10", "title": "Multi-GPU DDP 3.07× throughput", "status": "complete"},
    {"date": "2026-03-01", "title": "85% closed-loop success rate (17/20)", "status": "complete"},
    {"date": "2026-04-30", "title": "First paying customer ($250K ARR)", "status": "complete"},
    {"date": "2026-06-30", "title": "Isaac Sim domain randomization SDG", "status": "in_progress"},
    {"date": "2026-09-30", "title": "Series A close ($8M target)", "status": "planned"},
]

_INVESTOR_LOG = [
    {
        "investor": "Oracle Ventures",
        "type": "strategic",
        "last_update": "2026-03-15",
        "cadence_days": 30,
        "sentiment": "positive",
        "notes": "Interested in OCI integration story",
    },
    {
        "investor": "NVIDIA Deep Learning VC",
        "type": "strategic",
        "last_update": "2026-03-01",
        "cadence_days": 45,
        "sentiment": "very_positive",
        "notes": "GR00T partnership potential discussed",
    },
    {
        "investor": "Robotics Fund I",
        "type": "financial",
        "last_update": "2026-02-28",
        "cadence_days": 30,
        "sentiment": "neutral",
        "notes": "Wants to see 3 more design partners before leading",
    },
    {
        "investor": "Industrial AI Partners",
        "type": "financial",
        "last_update": "2026-03-20",
        "cadence_days": 60,
        "sentiment": "positive",
        "notes": "Impressed with 85% SR benchmark",
    },
]

def _days_until_next_update(last_update_str: str, cadence_days: int) -> int:
    last = datetime.strptime(last_update_str, "%Y-%m-%d")
    next_due = last + timedelta(days=cadence_days)
    return max(0, (next_due - datetime.utcnow()).days)

def _generate_update_draft(period: str) -> str:
    return f"""**OCI Robot Cloud — Investor Update ({period})**

Dear Investors,

Here is our monthly update for {period}.

**Key Metrics:**
- ARR: ${_KPIS['arr_usd']:,} | NRR: {_KPIS['nrr_pct']}%
- Closed-loop Success Rate: {_KPIS['success_rate_pct']}% (17/20 tasks)
- Monthly Burn: ${_KPIS['monthly_burn_usd']:,} | Runway: {_KPIS['runway_months']} months
- Active Pilots: {_KPIS['pilots_active']} | Design Partners: {_KPIS['design_partners']}

**Milestones This Period:**
- GR00T N1.6 running on OCI at 235ms latency
- Multi-GPU DDP achieved 3.07× training throughput
- 85% closed-loop eval success rate confirmed
- Fine-tuning pipeline: MAE 0.013 (8.7× vs baseline)

**Next 30 Days:**
- Isaac Sim RTX domain randomization SDG launch
- 2 additional design partner onboardings
- Series A preparation: deck + data room

**Ask:** Introductions to manufacturing/logistics robotics operators welcome.

Best,
Jun Qian, CEO — OCI Robot Cloud
"""

if USE_FASTAPI:
    app = FastAPI(title="Investor Relations Portal", version="1.0.0")

    class UpdateRequest(BaseModel):
        period: str  # e.g. "March 2026"
        recipients: list = []  # investor names to include; empty = all

    @app.get("/health")
    def health():
        return {"status": "ok", "port": PORT, "ts": datetime.utcnow().isoformat()}

    @app.get("/", response_class=HTMLResponse)
    def index():
        return HTMLResponse(f"""<!DOCTYPE html><html><head><title>Investor Relations Portal</title>
<style>body{{background:#0f172a;color:#f1f5f9;font-family:sans-serif;padding:2rem}}h1{{color:#C74634}}a{{color:#38bdf8}}</style></head><body>
<h1>Investor Relations Portal</h1><p>OCI Robot Cloud · Port {PORT}</p><p><a href="/docs">API Docs</a> | <a href="/health">Health</a> | <a href="/ir/dashboard">Dashboard</a></p>
<p>ARR $250K · NRR 118% · SR 85% · Burn $45K/mo · Runway 18mo</p></body></html>""")

    @app.get("/ir/dashboard")
    def ir_dashboard():
        """Live KPI dashboard with investor log and next update schedule."""
        enriched_log = []
        for inv in _INVESTOR_LOG:
            days_left = _days_until_next_update(inv["last_update"], inv["cadence_days"])
            enriched_log.append({
                **inv,
                "days_until_next_update": days_left,
                "update_due": days_left == 0,
            })
        # Sort by most overdue first
        enriched_log.sort(key=lambda x: x["days_until_next_update"])
        overdue = [i for i in enriched_log if i["days_until_next_update"] == 0]
        next_update_date = (
            min(
                [
                    datetime.strptime(i["last_update"], "%Y-%m-%d")
                    + timedelta(days=i["cadence_days"])
                    for i in _INVESTOR_LOG
                ]
            ).strftime("%Y-%m-%d")
        )
        return {
            "kpis": _KPIS,
            "milestones": _MILESTONES,
            "investor_log": enriched_log,
            "summary": {
                "total_investors": len(_INVESTOR_LOG),
                "updates_due_now": len(overdue),
                "overdue_investors": [i["investor"] for i in overdue],
            },
            "next_update_date": next_update_date,
            "ts": datetime.utcnow().isoformat(),
        }

    @app.post("/ir/send_update")
    def send_update(req: UpdateRequest):
        """Generate monthly investor update draft and schedule send."""
        target_investors = [
            inv for inv in _INVESTOR_LOG
            if not req.recipients or inv["investor"] in req.recipients
        ]
        update_draft = _generate_update_draft(req.period)
        recipient_list = [inv["investor"] for inv in target_investors]
        # Simulate scheduled send 2 hours from now
        scheduled_send = (datetime.utcnow() + timedelta(hours=2)).isoformat()
        return {
            "period": req.period,
            "update_draft": update_draft,
            "recipients": recipient_list,
            "recipient_count": len(recipient_list),
            "scheduled_send": scheduled_send,
            "status": "draft_ready",
            "word_count": len(update_draft.split()),
            "ts": datetime.utcnow().isoformat(),
        }

    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=PORT)
else:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok", "port": PORT}).encode())
        def log_message(self, *a): pass
    if __name__ == "__main__":
        HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
