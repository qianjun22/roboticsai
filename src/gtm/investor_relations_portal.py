"""
Investor relations portal — monthly update generation, live KPI dashboard
(ARR $250K, NRR 118%, SR 85%, burn $45K, runway 18mo), per-investor comms log,
update cadence management.
FastAPI service — OCI Robot Cloud
Port: 10109
"""
from __future__ import annotations
import json, math, random, time
from datetime import datetime, timedelta
from typing import Dict, List, Optional

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import HTMLResponse, JSONResponse
    from pydantic import BaseModel
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False
    from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = 10109

# --- Static KPI snapshot (refreshed monthly in production) -------------------

KPIS = {
    "arr_usd": 250_000,
    "arr_growth_mom_pct": 12.4,
    "nrr_pct": 118.0,
    "success_rate_pct": 85.0,
    "burn_usd_per_mo": 45_000,
    "runway_months": 18,
    "design_partners": 7,
    "inference_latency_ms": 231,
    "models_deployed": 3,
    "ft_accuracy_n": 0.21,
    "as_of": "2026-03-01",
}

MILESTONES = [
    {"date": "2025-10", "event": "GR00T N1.6 inference server live on OCI (227ms P50)"},
    {"date": "2025-11", "event": "First design partner signed — automotive OEM"},
    {"date": "2025-12", "event": "Fine-tuning pipeline: MAE 0.013 (8.7× vs baseline)"},
    {"date": "2026-01", "event": "Multi-GPU DDP: 3.07× throughput; 7-slide product deck"},
    {"date": "2026-02", "event": "Closed-loop eval 85% SR (17/20 tasks, 231ms)"},
    {"date": "2026-03", "event": "pip-installable SDK; CoRL paper draft submitted"},
]

INVESTORS = [
    {
        "id": "inv_001",
        "name": "Sequoia Capital",
        "stage": "seed_lead",
        "check_size_usd": 3_000_000,
        "last_contact": "2026-03-15",
        "next_update_due": "2026-04-01",
        "sentiment": "bullish",
        "primary_contact": "partner@sequoia.com",
    },
    {
        "id": "inv_002",
        "name": "Andreessen Horowitz",
        "stage": "series_a_prospect",
        "check_size_usd": 10_000_000,
        "last_contact": "2026-03-10",
        "next_update_due": "2026-04-10",
        "sentiment": "interested",
        "primary_contact": "partner@a16z.com",
    },
    {
        "id": "inv_003",
        "name": "Oracle Strategic Investments",
        "stage": "strategic_partner",
        "check_size_usd": 1_500_000,
        "last_contact": "2026-03-20",
        "next_update_due": "2026-04-20",
        "sentiment": "committed",
        "primary_contact": "corp.dev@oracle.com",
    },
    {
        "id": "inv_004",
        "name": "Toyota Ventures",
        "stage": "seed_participant",
        "check_size_usd": 500_000,
        "last_contact": "2026-02-28",
        "next_update_due": "2026-03-31",
        "sentiment": "neutral",
        "primary_contact": "ventures@toyota.com",
    },
]

# Comms log (in-memory; production would use a DB)
COMMS_LOG: List[dict] = [
    {
        "investor_id": "inv_001",
        "date": "2026-03-15",
        "type": "monthly_update",
        "summary": "Shared Q1 KPI pack; SR 85% highlight; runway 18mo confirmed.",
        "response": "Positive — requesting demo of closed-loop eval.",
    },
    {
        "investor_id": "inv_002",
        "date": "2026-03-10",
        "type": "intro_call",
        "summary": "First call post-CoRL paper; discussed Series A sizing.",
        "response": "Wants technical deep-dive with robotics GP next month.",
    },
    {
        "investor_id": "inv_003",
        "date": "2026-03-20",
        "type": "board_update",
        "summary": "OCI compute credits extended 6 months; strategic alignment confirmed.",
        "response": "Approved additional $250K credit line.",
    },
]


# --- Pydantic models ---------------------------------------------------------

if USE_FASTAPI:
    class UpdateRequest(BaseModel):
        period: str  # e.g. "2026-03" or "Q1 2026"
        investor_ids: Optional[List[str]] = None  # None = all investors
        include_financials: bool = True
        include_technical: bool = True
        personalize: bool = True

    class UpdateResponse(BaseModel):
        period: str
        update_draft: str
        recipients: List[dict]
        scheduled_send: str
        kpi_snapshot: dict


def _generate_update_draft(period: str, include_financials: bool,
                            include_technical: bool) -> str:
    """Generate a markdown investor update for the given period."""
    now_str = datetime.utcnow().strftime("%B %Y")
    lines = [
        f"# OCI Robot Cloud — Investor Update: {period}",
        f"_Generated {now_str} | Confidential — not for distribution_",
        "",
        "## Executive Summary",
        "We continue to execute on our technical roadmap with strong momentum:",
        f"- **85% closed-loop task success rate** (17/20 LIBERO tasks, 231ms latency)",
        f"- **7 design partners** signed across automotive, logistics, and semiconductor",
        f"- CoRL 2026 paper submitted; GTC demo scheduled for April",
        "",
    ]
    if include_financials:
        lines += [
            "## Financial KPIs",
            f"| Metric | Value | MoM |",
            f"|--------|-------|-----|",
            f"| ARR | $250K | +12.4% |",
            f"| NRR | 118% | +3pp |",
            f"| Burn | $45K/mo | -5% |",
            f"| Runway | 18 months | stable |",
            f"| Design Partners | 7 | +2 |",
            "",
        ]
    if include_technical:
        lines += [
            "## Technical Milestones",
            "- GR00T N1.6 inference: 231ms P50 on OCI A100 (6.7GB VRAM)",
            "- Fine-tuning: MAE 0.013 (8.7× improvement over baseline)",
            "- Multi-GPU DDP: 3.07× throughput; F/T calibration v2: ±0.2N accuracy",
            "- pip-installable SDK: `pip install oci-robot-cloud`",
            "",
        ]
    lines += [
        "## Next 30 Days",
        "1. Series A process kick-off (target: $8M, Q3 2026 close)",
        "2. GTC live demo — closed-loop pick-and-place with 85% SR",
        "3. Onboard 2 additional design partners (semiconductor + pharma verticals)",
        "4. CoRL paper decision expected mid-April",
        "",
        "## Ask",
        "- Warm intros to robotics GPs at Khosla, Lightspeed, and GV",
        "- Reference calls with portfolio companies using manipulation robots",
        "",
        "---",
        "_OCI Robot Cloud · contact@oci-robot.cloud · Confidential_",
    ]
    return "\n".join(lines)


if USE_FASTAPI:
    app = FastAPI(
        title="Investor Relations Portal",
        version="1.0.0",
        description="Monthly update generation, live KPI dashboard, and per-investor comms log",
    )

    @app.get("/ir/dashboard")
    def ir_dashboard():
        """
        Live IR dashboard — KPIs, milestones, investor log, and next update dates.
        """
        # Compute days until next update for each investor
        today = datetime.utcnow().date()
        investor_summary = []
        for inv in INVESTORS:
            due = datetime.strptime(inv["next_update_due"], "%Y-%m-%d").date()
            days_until = (due - today).days
            investor_summary.append({
                **inv,
                "days_until_next_update": days_until,
                "update_status": "overdue" if days_until < 0 else (
                    "due_soon" if days_until <= 7 else "on_track"
                ),
            })

        # Aggregate comms log per investor
        comms_by_investor = {}
        for log in COMMS_LOG:
            iid = log["investor_id"]
            comms_by_investor.setdefault(iid, []).append(log)

        return {
            "kpis": KPIS,
            "milestones": MILESTONES,
            "investor_log": investor_summary,
            "comms_log": comms_by_investor,
            "next_update_date": min(
                inv["next_update_due"] for inv in INVESTORS
            ),
            "total_committed_usd": sum(inv["check_size_usd"] for inv in INVESTORS),
            "total_investors": len(INVESTORS),
            "generated_at": datetime.utcnow().isoformat() + "Z",
        }

    @app.post("/ir/send_update", response_model=UpdateResponse)
    def send_update(req: UpdateRequest):
        """
        Generate and schedule a monthly investor update.

        - Drafts a personalized markdown update for the given period.
        - Targets all investors (or the specified subset).
        - Returns the draft + recipient list + scheduled send time.
        """
        # Filter investors
        targets = [
            inv for inv in INVESTORS
            if req.investor_ids is None or inv["id"] in req.investor_ids
        ]
        if not targets:
            raise HTTPException(status_code=404, detail="No matching investors found")

        draft = _generate_update_draft(
            req.period, req.include_financials, req.include_technical
        )

        # Schedule send for next business-hour window (09:00 UTC next day)
        tomorrow = datetime.utcnow().replace(hour=9, minute=0, second=0, microsecond=0)
        tomorrow += timedelta(days=1)

        recipients = [
            {
                "investor_id": inv["id"],
                "name": inv["name"],
                "email": inv["primary_contact"],
                "personalized": req.personalize,
            }
            for inv in targets
        ]

        # Log this send event
        for inv in targets:
            COMMS_LOG.append({
                "investor_id": inv["id"],
                "date": datetime.utcnow().strftime("%Y-%m-%d"),
                "type": "monthly_update",
                "summary": f"Auto-generated update for period {req.period}.",
                "response": "pending",
            })

        return UpdateResponse(
            period=req.period,
            update_draft=draft,
            recipients=recipients,
            scheduled_send=tomorrow.isoformat() + "Z",
            kpi_snapshot=KPIS,
        )

    @app.get("/health")
    def health():
        return {"status": "ok", "port": PORT, "ts": datetime.utcnow().isoformat()}

    @app.get("/", response_class=HTMLResponse)
    def index():
        return HTMLResponse("""<!DOCTYPE html><html><head><title>Investor Relations Portal</title>
<style>body{background:#0f172a;color:#f1f5f9;font-family:sans-serif;padding:2rem}
h1{color:#C74634}a{color:#38bdf8}.stat{display:inline-block;background:#1e293b;padding:1rem;border-radius:8px;margin:.5rem}
.kpi{font-size:1.4rem;font-weight:bold;color:#38bdf8}</style></head><body>
<h1>Investor Relations Portal</h1>
<p>OCI Robot Cloud · Port 10109</p>
<div>
  <span class="stat">ARR<br><span class="kpi">$250K</span></span>
  <span class="stat">NRR<br><span class="kpi">118%</span></span>
  <span class="stat">Success Rate<br><span class="kpi">85%</span></span>
  <span class="stat">Burn<br><span class="kpi">$45K/mo</span></span>
  <span class="stat">Runway<br><span class="kpi">18 mo</span></span>
  <span class="stat">Design Partners<br><span class="kpi">7</span></span>
</div>
<p><a href="/docs">API Docs</a> | <a href="/health">Health</a> | <a href="/ir/dashboard">IR Dashboard</a></p>
</body></html>""")

    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=PORT)

else:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok", "port": PORT}).encode())
        def do_POST(self):
            self.do_GET()
        def log_message(self, *a):
            pass
    if __name__ == "__main__":
        HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
