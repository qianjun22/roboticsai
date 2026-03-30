#!/usr/bin/env python3
"""
OCI Robot Cloud — Design Partner CRM Dashboard
FastAPI service on port 8077
"""

from __future__ import annotations

import uuid
from datetime import datetime, date
from typing import List, Optional, Dict, Any

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

class Partner(BaseModel):
    id: str
    name: str
    stage: str  # prospect / pilot / active / churned
    contact_name: str
    contact_email: str
    robot_type: str
    use_case: str
    monthly_gpu_hours_target: int
    onboarding_step: int  # 1-7
    health_score: int  # 0-100
    last_activity: str
    notes: str
    blockers: Optional[str] = None


class Milestone(BaseModel):
    partner_id: str
    name: str
    target_date: str
    status: str  # pending / done / at_risk
    notes: str


class Activity(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    partner_id: str
    type: str  # email / call / demo / training_run
    description: str
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


# ---------------------------------------------------------------------------
# In-memory data store
# ---------------------------------------------------------------------------

PARTNERS: Dict[str, Partner] = {}
MILESTONES: List[Milestone] = []
ACTIVITIES: List[Activity] = []

GPU_PRICE_PER_HOUR = 4.10


def _seed_data() -> None:
    partners_raw = [
        Partner(
            id="apptronik",
            name="Apptronik",
            stage="pilot",
            contact_name="Jeff Cardenas",
            contact_email="jeff@apptronik.com",
            robot_type="Apollo humanoid",
            use_case="warehouse_automation",
            monthly_gpu_hours_target=200,
            onboarding_step=5,
            health_score=70,
            last_activity="2026-03-27",
            notes="Apollo humanoid pilot in Austin warehouse. Strong engineering team, responsive. Needs Isaac Sim license resolved to proceed to full fine-tune.",
            blockers="Waiting on Isaac Sim license",
        ),
        Partner(
            id="skild-ai",
            name="Skild AI",
            stage="pilot",
            contact_name="Deepak Pathak",
            contact_email="deepak@skild.ai",
            robot_type="custom_arm",
            use_case="assembly_line",
            monthly_gpu_hours_target=150,
            onboarding_step=6,
            health_score=40,
            last_activity="2026-03-25",
            notes="Custom 6-DOF arm for PCB assembly. At risk — accuracy stuck at 52% on pick-and-place task. Scheduled joint debug session with ML team.",
            blockers="Model accuracy below 60% threshold",
        ),
        Partner(
            id="physical-intelligence",
            name="Physical Intelligence",
            stage="prospect",
            contact_name="Karol Hausman",
            contact_email="karol@physicalintelligence.company",
            robot_type="mobile_manipulator",
            use_case="home_assistant",
            monthly_gpu_hours_target=300,
            onboarding_step=3,
            health_score=20,
            last_activity="2026-03-20",
            notes="High-value prospect with large-scale home robotics ambitions. Legal review blocking data-sharing NDA. Executive champion identified.",
            blockers="Legal review of data sharing agreement",
        ),
        Partner(
            id="covariant",
            name="Covariant",
            stage="active",
            contact_name="Peter Chen",
            contact_email="peter@covariant.ai",
            robot_type="RDT_arm",
            use_case="logistics_picking",
            monthly_gpu_hours_target=500,
            onboarding_step=7,
            health_score=95,
            last_activity="2026-03-29",
            notes="Flagship active customer. RDT arm achieving 98% pick accuracy in 3PL warehouse. Expanding to second site in Q2. Excellent reference account.",
            blockers=None,
        ),
        Partner(
            id="1x-technologies",
            name="1X Technologies",
            stage="pilot",
            contact_name="Bernt Bornich",
            contact_email="bernt@1x.tech",
            robot_type="NEO_humanoid",
            use_case="general_manipulation",
            monthly_gpu_hours_target=400,
            onboarding_step=4,
            health_score=80,
            last_activity="2026-03-28",
            notes="NEO humanoid pilot targeting general household tasks. Good trajectory — DAgger dataset collection underway, currently at 280 demos. Target 500 to unlock next fine-tune cycle.",
            blockers="Need DAgger dataset > 500 demos",
        ),
    ]
    for p in partners_raw:
        PARTNERS[p.id] = p

    MILESTONES.extend([
        Milestone(partner_id="apptronik", name="Isaac Sim license activated", target_date="2026-04-07", status="at_risk", notes="Procurement in legal review"),
        Milestone(partner_id="apptronik", name="First 200-hr fine-tune complete", target_date="2026-04-21", status="pending", notes="Blocked on license"),
        Milestone(partner_id="apptronik", name="Warehouse pilot Go/No-Go review", target_date="2026-05-05", status="pending", notes=""),
        Milestone(partner_id="skild-ai", name="Accuracy > 60% on pick-and-place", target_date="2026-04-10", status="at_risk", notes="Joint debug scheduled"),
        Milestone(partner_id="skild-ai", name="100-demo DAgger dataset submitted", target_date="2026-04-17", status="pending", notes=""),
        Milestone(partner_id="skild-ai", name="Customer sign-off on assembly pilot", target_date="2026-05-01", status="pending", notes=""),
        Milestone(partner_id="physical-intelligence", name="NDA / data-sharing agreement signed", target_date="2026-04-15", status="at_risk", notes="Legal review ongoing"),
        Milestone(partner_id="physical-intelligence", name="Onboarding kickoff call", target_date="2026-04-22", status="pending", notes="Pending NDA"),
        Milestone(partner_id="physical-intelligence", name="First training run on OCI", target_date="2026-05-15", status="pending", notes=""),
        Milestone(partner_id="covariant", name="Second warehouse site deployment", target_date="2026-04-30", status="pending", notes="Contract signed"),
        Milestone(partner_id="covariant", name="Q2 expansion — 750 GPU-hr tier", target_date="2026-06-01", status="pending", notes="Upsell conversation initiated"),
        Milestone(partner_id="1x-technologies", name="500-demo DAgger dataset complete", target_date="2026-04-12", status="pending", notes="At 280 demos today"),
        Milestone(partner_id="1x-technologies", name="NEO full fine-tune (400 GPU-hr)", target_date="2026-04-26", status="pending", notes=""),
        Milestone(partner_id="1x-technologies", name="General manipulation benchmark > 70%", target_date="2026-05-10", status="pending", notes=""),
    ])

    ACTIVITIES.extend([
        Activity(partner_id="apptronik", type="call", description="Quarterly business review — roadmap alignment and Isaac Sim license escalation", timestamp="2026-03-27T14:00:00"),
        Activity(partner_id="apptronik", type="email", description="Sent Isaac Sim license procurement checklist to IT contact", timestamp="2026-03-24T10:30:00"),
        Activity(partner_id="skild-ai", type="demo", description="Live debug session on pick-and-place accuracy — identified data imbalance issue", timestamp="2026-03-25T16:00:00"),
        Activity(partner_id="skild-ai", type="training_run", description="Retrain with balanced dataset — accuracy reached 52%, up from 45%", timestamp="2026-03-22T09:00:00"),
        Activity(partner_id="physical-intelligence", type="call", description="Intro call with Karol — confirmed OCI interest, sent NDA for legal review", timestamp="2026-03-20T11:00:00"),
        Activity(partner_id="covariant", type="training_run", description="500-hr monthly training run completed — 98.2% pick accuracy", timestamp="2026-03-29T08:00:00"),
        Activity(partner_id="covariant", type="call", description="Upsell discussion — Q2 expansion to 750 GPU-hr tier", timestamp="2026-03-26T15:00:00"),
        Activity(partner_id="1x-technologies", type="training_run", description="DAgger iteration 3 — collected 80 new demos, dataset now at 280", timestamp="2026-03-28T13:00:00"),
        Activity(partner_id="1x-technologies", type="email", description="Shared best-practice guide for teleoperation demo collection", timestamp="2026-03-25T09:00:00"),
    ])


_seed_data()

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="OCI Robot Cloud — Design Partner Dashboard",
    description="CRM dashboard for GR00T N1.6 fine-tuning design partners",
    version="1.0.0",
)

# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------

@app.get("/api/partners", response_model=List[Partner])
def list_partners() -> List[Partner]:
    return list(PARTNERS.values())


@app.get("/api/partners/{partner_id}", response_model=Partner)
def get_partner(partner_id: str) -> Partner:
    partner = PARTNERS.get(partner_id)
    if not partner:
        raise HTTPException(status_code=404, detail=f"Partner '{partner_id}' not found")
    return partner


@app.get("/api/partners/{partner_id}/milestones", response_model=List[Milestone])
def get_partner_milestones(partner_id: str) -> List[Milestone]:
    if partner_id not in PARTNERS:
        raise HTTPException(status_code=404, detail=f"Partner '{partner_id}' not found")
    return [m for m in MILESTONES if m.partner_id == partner_id]


@app.get("/api/health-summary")
def health_summary() -> Dict[str, Any]:
    partners = list(PARTNERS.values())
    total = len(partners)
    avg_health = round(sum(p.health_score for p in partners) / total, 1) if total else 0
    at_risk = sum(1 for p in partners if p.health_score < 50)
    active_count = sum(1 for p in partners if p.stage == "active")
    return {
        "total_partners": total,
        "avg_health_score": avg_health,
        "at_risk_count": at_risk,
        "active_count": active_count,
        "pilot_count": sum(1 for p in partners if p.stage == "pilot"),
        "prospect_count": sum(1 for p in partners if p.stage == "prospect"),
    }


@app.get("/api/pipeline")
def pipeline_view() -> Dict[str, Any]:
    stages = ["prospect", "pilot", "active", "churned"]
    result: Dict[str, Any] = {}
    for stage in stages:
        partners_in_stage = [p for p in PARTNERS.values() if p.stage == stage]
        monthly_gpu = sum(p.monthly_gpu_hours_target for p in partners_in_stage)
        result[stage] = {
            "count": len(partners_in_stage),
            "partners": [p.name for p in partners_in_stage],
            "total_monthly_gpu_hours": monthly_gpu,
            "monthly_revenue_potential_usd": round(monthly_gpu * GPU_PRICE_PER_HOUR, 2),
            "annual_revenue_potential_usd": round(monthly_gpu * GPU_PRICE_PER_HOUR * 12, 2),
        }
    all_partners = list(PARTNERS.values())
    total_gpu = sum(p.monthly_gpu_hours_target for p in all_partners)
    result["total"] = {
        "total_monthly_gpu_hours": total_gpu,
        "monthly_revenue_potential_usd": round(total_gpu * GPU_PRICE_PER_HOUR, 2),
        "annual_revenue_potential_usd": round(total_gpu * GPU_PRICE_PER_HOUR * 12, 2),
    }
    return result


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def _health_color(score: int) -> str:
    if score >= 70:
        return "#22c55e"
    elif score >= 40:
        return "#f59e0b"
    else:
        return "#ef4444"


def _stage_badge(stage: str) -> str:
    colors = {
        "prospect": "#6366f1",
        "pilot":    "#f59e0b",
        "active":   "#22c55e",
        "churned":  "#6b7280",
    }
    color = colors.get(stage, "#6b7280")
    return f'<span style="background:{color};color:#fff;padding:2px 10px;border-radius:12px;font-size:11px;font-weight:600;text-transform:uppercase;">{stage}</span>'


def _render_dashboard() -> str:
    partners = list(PARTNERS.values())
    summary = health_summary()
    pipeline = pipeline_view()

    pipeline_html = ""
    stage_order = ["prospect", "pilot", "active"]
    stage_colors = {"prospect": "#6366f1", "pilot": "#f59e0b", "active": "#22c55e"}
    for stage in stage_order:
        info = pipeline.get(stage, {})
        color = stage_colors[stage]
        pipeline_html += f"""
        <div style="flex:1;background:#1e293b;border-radius:10px;padding:16px;text-align:center;border:1px solid #334155;">
          <div style="color:{color};font-size:28px;font-weight:700;">{info.get('count', 0)}</div>
          <div style="color:#94a3b8;font-size:12px;text-transform:uppercase;letter-spacing:1px;margin-bottom:8px;">{stage}</div>
          <div style="color:#e2e8f0;font-size:13px;">{info.get('total_monthly_gpu_hours',0)} GPU-hrs/mo</div>
          <div style="color:#64748b;font-size:12px;">${info.get('monthly_revenue_potential_usd',0):,.0f}/mo</div>
        </div>"""

    cards_html = ""
    for p in partners:
        hcolor = _health_color(p.health_score)
        badge = _stage_badge(p.stage)
        blocker_html = ""
        if p.blockers:
            blocker_html = f'<div style="background:#450a0a;border:1px solid #7f1d1d;border-radius:6px;padding:8px 12px;margin-top:10px;color:#fca5a5;font-size:12px;">\u26a0 {p.blockers}</div>'

        step_pct = round((p.onboarding_step / 7) * 100)
        step_color = hcolor

        milestones_for_card = [m for m in MILESTONES if m.partner_id == p.id]
        milestone_rows = ""
        for m in milestones_for_card[:3]:
            ms_color = {"done": "#22c55e", "at_risk": "#ef4444", "pending": "#94a3b8"}.get(m.status, "#94a3b8")
            ms_icon = {"done": "\u2713", "at_risk": "!", "pending": "\u25cb"}.get(m.status, "\u25cb")
            milestone_rows += f'<div style="display:flex;align-items:center;gap:8px;padding:4px 0;border-bottom:1px solid #1e293b;"><span style="color:{ms_color};font-weight:700;width:14px;">{ms_icon}</span><span style="color:#cbd5e1;font-size:12px;flex:1;">{m.name}</span><span style="color:#64748b;font-size:11px;">{m.target_date}</span></div>'

        revenue_mo = round(p.monthly_gpu_hours_target * GPU_PRICE_PER_HOUR, 0)
        cards_html += f"""
        <div style="background:#1e293b;border:1px solid #334155;border-radius:12px;padding:20px;display:flex;flex-direction:column;gap:10px;">
          <div style="display:flex;justify-content:space-between;align-items:flex-start;">
            <div>
              <div style="color:#f1f5f9;font-size:18px;font-weight:700;">{p.name}</div>
              <div style="color:#94a3b8;font-size:13px;">{p.contact_name} \u00b7 {p.contact_email}</div>
            </div>
            <div style="display:flex;flex-direction:column;align-items:flex-end;gap:6px;">
              {badge}
              <div style="color:{hcolor};font-size:22px;font-weight:700;">{p.health_score}<span style="font-size:12px;color:#64748b;">/100</span></div>
            </div>
          </div>

          <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;font-size:12px;">
            <div><span style="color:#64748b;">Robot:</span> <span style="color:#cbd5e1;">{p.robot_type}</span></div>
            <div><span style="color:#64748b;">Use case:</span> <span style="color:#cbd5e1;">{p.use_case.replace('_',' ')}</span></div>
            <div><span style="color:#64748b;">GPU target:</span> <span style="color:#cbd5e1;">{p.monthly_gpu_hours_target} hrs/mo</span></div>
            <div><span style="color:#64748b;">Revenue:</span> <span style="color:#22c55e;">${revenue_mo:,.0f}/mo</span></div>
          </div>

          <div>
            <div style="display:flex;justify-content:space-between;margin-bottom:4px;">
              <span style="color:#64748b;font-size:11px;">Onboarding step {p.onboarding_step}/7</span>
              <span style="color:{step_color};font-size:11px;">{step_pct}%</span>
            </div>
            <div style="background:#0f172a;border-radius:4px;height:6px;">
              <div style="background:{step_color};width:{step_pct}%;height:6px;border-radius:4px;"></div>
            </div>
          </div>

          {blocker_html}

          <div style="margin-top:4px;">
            <div style="color:#64748b;font-size:11px;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px;">Milestones</div>
            {milestone_rows}
          </div>

          <div style="color:#475569;font-size:11px;border-top:1px solid #334155;padding-top:8px;">Last activity: {p.last_activity}</div>
        </div>"""

    revenue_rows = ""
    total_gpu_all = 0
    for p in sorted(partners, key=lambda x: x.monthly_gpu_hours_target, reverse=True):
        mo = round(p.monthly_gpu_hours_target * GPU_PRICE_PER_HOUR, 0)
        ann = mo * 12
        total_gpu_all += p.monthly_gpu_hours_target
        hcolor = _health_color(p.health_score)
        revenue_rows += f"""
        <tr>
          <td style="padding:10px 14px;color:#e2e8f0;">{p.name}</td>
          <td style="padding:10px 14px;color:#94a3b8;">{p.stage}</td>
          <td style="padding:10px 14px;color:#94a3b8;text-align:right;">{p.monthly_gpu_hours_target}</td>
          <td style="padding:10px 14px;color:#22c55e;text-align:right;">${mo:,.0f}</td>
          <td style="padding:10px 14px;color:#22c55e;text-align:right;">${ann:,.0f}</td>
          <td style="padding:10px 14px;text-align:center;"><span style="color:{hcolor};font-weight:700;">{p.health_score}</span></td>
        </tr>"""
    total_mo = round(total_gpu_all * GPU_PRICE_PER_HOUR, 0)
    total_ann = total_mo * 12
    revenue_rows += f"""
    <tr style="border-top:2px solid #334155;background:#1e293b;">
      <td style="padding:10px 14px;color:#f1f5f9;font-weight:700;" colspan="2">TOTAL</td>
      <td style="padding:10px 14px;color:#f1f5f9;font-weight:700;text-align:right;">{total_gpu_all}</td>
      <td style="padding:10px 14px;color:#4ade80;font-weight:700;text-align:right;">${total_mo:,.0f}</td>
      <td style="padding:10px 14px;color:#4ade80;font-weight:700;text-align:right;">${total_ann:,.0f}</td>
      <td style="padding:10px 14px;"></td>
    </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>OCI Robot Cloud \u2014 Design Partner Dashboard</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #e2e8f0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; min-height: 100vh; }}
    table {{ border-collapse: collapse; width: 100%; }}
    tr:hover td {{ background: rgba(255,255,255,0.03); }}
  </style>
</head>
<body>
  <div style="max-width:1400px;margin:0 auto;padding:32px 24px;">

    <!-- Header -->
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:32px;">
      <div>
        <div style="color:#94a3b8;font-size:12px;text-transform:uppercase;letter-spacing:2px;margin-bottom:6px;">OCI Robot Cloud</div>
        <h1 style="font-size:28px;font-weight:700;color:#f1f5f9;">Design Partner Dashboard</h1>
        <div style="color:#64748b;font-size:13px;margin-top:4px;">NVIDIA GR00T N1.6 Fine-Tuning Program \u00b7 {len(partners)} partners \u00b7 ${GPU_PRICE_PER_HOUR}/GPU-hr</div>
      </div>
      <div style="text-align:right;color:#64748b;font-size:12px;">
        <div>Port 8077</div>
        <div>API: <a href="/api/partners" style="color:#6366f1;">/api/partners</a></div>
      </div>
    </div>

    <!-- KPI row -->
    <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:28px;">
      <div style="background:#1e293b;border-radius:10px;padding:16px;border:1px solid #334155;">
        <div style="color:#64748b;font-size:11px;text-transform:uppercase;letter-spacing:1px;">Total Partners</div>
        <div style="color:#f1f5f9;font-size:32px;font-weight:700;">{summary['total_partners']}</div>
      </div>
      <div style="background:#1e293b;border-radius:10px;padding:16px;border:1px solid #334155;">
        <div style="color:#64748b;font-size:11px;text-transform:uppercase;letter-spacing:1px;">Avg Health Score</div>
        <div style="color:{_health_color(int(summary['avg_health_score']))};font-size:32px;font-weight:700;">{summary['avg_health_score']}</div>
      </div>
      <div style="background:#1e293b;border-radius:10px;padding:16px;border:1px solid #334155;">
        <div style="color:#64748b;font-size:11px;text-transform:uppercase;letter-spacing:1px;">At Risk (&lt;50)</div>
        <div style="color:#ef4444;font-size:32px;font-weight:700;">{summary['at_risk_count']}</div>
      </div>
      <div style="background:#1e293b;border-radius:10px;padding:16px;border:1px solid #334155;">
        <div style="color:#64748b;font-size:11px;text-transform:uppercase;letter-spacing:1px;">Monthly ARR Potential</div>
        <div style="color:#22c55e;font-size:28px;font-weight:700;">${total_mo:,.0f}</div>
      </div>
    </div>

    <!-- Pipeline summary -->
    <div style="margin-bottom:28px;">
      <div style="color:#94a3b8;font-size:12px;text-transform:uppercase;letter-spacing:1px;margin-bottom:12px;">Pipeline by Stage</div>
      <div style="display:flex;gap:12px;">
        {pipeline_html}
      </div>
    </div>

    <!-- Partner cards -->
    <div style="margin-bottom:32px;">
      <div style="color:#94a3b8;font-size:12px;text-transform:uppercase;letter-spacing:1px;margin-bottom:16px;">Partner Details</div>
      <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(380px,1fr));gap:20px;">
        {cards_html}
      </div>
    </div>

    <!-- Revenue table -->
    <div>
      <div style="color:#94a3b8;font-size:12px;text-transform:uppercase;letter-spacing:1px;margin-bottom:12px;">GPU Revenue Potential</div>
      <div style="background:#1e293b;border-radius:12px;border:1px solid #334155;overflow:hidden;">
        <table>
          <thead>
            <tr style="background:#0f172a;">
              <th style="padding:12px 14px;text-align:left;color:#64748b;font-size:11px;text-transform:uppercase;letter-spacing:1px;">Partner</th>
              <th style="padding:12px 14px;text-align:left;color:#64748b;font-size:11px;text-transform:uppercase;letter-spacing:1px;">Stage</th>
              <th style="padding:12px 14px;text-align:right;color:#64748b;font-size:11px;text-transform:uppercase;letter-spacing:1px;">GPU Hrs/Mo</th>
              <th style="padding:12px 14px;text-align:right;color:#64748b;font-size:11px;text-transform:uppercase;letter-spacing:1px;">Monthly ($)</th>
              <th style="padding:12px 14px;text-align:right;color:#64748b;font-size:11px;text-transform:uppercase;letter-spacing:1px;">Annual ($)</th>
              <th style="padding:12px 14px;text-align:center;color:#64748b;font-size:11px;text-transform:uppercase;letter-spacing:1px;">Health</th>
            </tr>
          </thead>
          <tbody>
            {revenue_rows}
          </tbody>
        </table>
      </div>
    </div>

    <div style="text-align:center;margin-top:40px;color:#334155;font-size:12px;">
      OCI Robot Cloud \u00b7 Design Partner CRM \u00b7 <a href="/docs" style="color:#6366f1;">API Docs</a>
    </div>
  </div>
</body>
</html>"""
    return html


@app.get("/", response_class=HTMLResponse)
def dashboard() -> HTMLResponse:
    return HTMLResponse(content=_render_dashboard())


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8077)
