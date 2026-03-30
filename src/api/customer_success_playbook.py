#!/usr/bin/env python3
"""
OCI Robot Cloud — Customer Success Playbook Generator
Port 8070 | Generates automated, tailored action plans for CSMs per partner.
"""

import argparse
import json
import math
import random
from dataclasses import dataclass, field
from datetime import date, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import List, Optional


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class PlaybookAction:
    action_id: str
    priority: str          # P0 / P1 / P2 / P3
    category: str          # training / eval / support / expansion / retention
    title: str
    description: str
    owner: str             # CSM / partner / engineering
    due_in_days: int
    blockers: List[str]
    success_metric: str


@dataclass
class PartnerProfile:
    partner: str
    tier: str              # strategic / growth / standard
    days_since_signup: int
    current_sr: float      # success rate 0–100
    sr_trend: str          # improving / plateau / declining / too_early
    last_dagger_run: Optional[int]   # days ago, None = never
    demo_count: int
    support_tickets_open: int
    nps_score: Optional[int]         # 0–10, None = not yet measured
    renewal_in_days: int
    risk_level: str        # low / medium / high / critical


# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

def generate_partner_profiles(seed: int = 42) -> List[PartnerProfile]:
    random.seed(seed)
    return [
        PartnerProfile(
            partner="agility_robotics",
            tier="strategic",
            days_since_signup=45,
            current_sr=68.0,
            sr_trend="improving",
            last_dagger_run=7,
            demo_count=12,
            support_tickets_open=2,
            nps_score=8,
            renewal_in_days=200,
            risk_level="low",
        ),
        PartnerProfile(
            partner="figure_ai",
            tier="growth",
            days_since_signup=20,
            current_sr=35.0,
            sr_trend="plateau",
            last_dagger_run=None,
            demo_count=4,
            support_tickets_open=0,
            nps_score=6,
            renewal_in_days=160,
            risk_level="medium",
        ),
        PartnerProfile(
            partner="boston_dynamics",
            tier="strategic",
            days_since_signup=90,
            current_sr=52.0,
            sr_trend="declining",
            last_dagger_run=30,
            demo_count=20,
            support_tickets_open=5,
            nps_score=4,
            renewal_in_days=45,
            risk_level="high",
        ),
        PartnerProfile(
            partner="pilot_customer",
            tier="standard",
            days_since_signup=10,
            current_sr=12.0,
            sr_trend="too_early",
            last_dagger_run=None,
            demo_count=1,
            support_tickets_open=1,
            nps_score=None,
            renewal_in_days=350,
            risk_level="critical",
        ),
        PartnerProfile(
            partner="new_customer",
            tier="standard",
            days_since_signup=5,
            current_sr=0.0,
            sr_trend="too_early",
            last_dagger_run=None,
            demo_count=0,
            support_tickets_open=0,
            nps_score=None,
            renewal_in_days=360,
            risk_level="critical",
        ),
    ]


# ---------------------------------------------------------------------------
# Playbook generation
# ---------------------------------------------------------------------------

def generate_playbook(profile: PartnerProfile) -> List[PlaybookAction]:
    actions: List[PlaybookAction] = []
    aid = 0

    def next_id(prefix: str) -> str:
        nonlocal aid
        aid += 1
        return f"{prefix}-{aid:02d}"

    # P0: emergency onboarding if SR < 20%
    if profile.current_sr < 20 and profile.days_since_signup > 7:
        actions.append(PlaybookAction(
            action_id=next_id(profile.partner[:4].upper()),
            priority="P0",
            category="training",
            title="Emergency Onboarding Session",
            description=(
                f"SR is critically low at {profile.current_sr:.0f}%. Schedule a live "
                "2-hour onboarding session with an OCI Robot Cloud solutions engineer "
                "to walk through dataset preparation, task setup, and baseline training."
            ),
            owner="CSM",
            due_in_days=3,
            blockers=["Partner availability", "Demo environment access"],
            success_metric="SR reaches 30%+ within 14 days of session",
        ))

    # P0: declining SR → engineering review
    if profile.sr_trend == "declining":
        actions.append(PlaybookAction(
            action_id=next_id(profile.partner[:4].upper()),
            priority="P0",
            category="support",
            title="Schedule Engineering Root-Cause Review",
            description=(
                "SR trend is declining. Engage an OCI Robot Cloud engineer to review "
                "recent training runs, eval logs, and dataset quality. Identify root cause "
                "within 5 business days."
            ),
            owner="engineering",
            due_in_days=5,
            blockers=["Engineering capacity", "Access to partner training logs"],
            success_metric="Root cause identified and remediation plan delivered",
        ))

    # P1: support escalation if > 3 open tickets
    if profile.support_tickets_open > 3:
        actions.append(PlaybookAction(
            action_id=next_id(profile.partner[:4].upper()),
            priority="P1",
            category="support",
            title="Support Escalation — Ticket Backlog",
            description=(
                f"{profile.support_tickets_open} open support tickets detected. "
                "CSM to triage with support lead, set SLA targets per ticket, and "
                "send a consolidated status update to partner within 24h."
            ),
            owner="CSM",
            due_in_days=2,
            blockers=["Support team bandwidth"],
            success_metric="All tickets acknowledged with SLA; backlog < 2 within 10 days",
        ))

    # P1: plateau → recommend DAgger run
    if profile.sr_trend == "plateau":
        actions.append(PlaybookAction(
            action_id=next_id(profile.partner[:4].upper()),
            priority="P1",
            category="training",
            title="DAgger Run Kickoff — Break SR Plateau",
            description=(
                "SR has plateaued. Recommend a DAgger (Dataset Aggregation) run to "
                "collect corrective demonstrations for failure cases. Provide runbook "
                "and schedule a 30-min call to kick off."
            ),
            owner="CSM",
            due_in_days=7,
            blockers=["Partner data collection setup"],
            success_metric="DAgger run initiated; SR improves > 5pp within 21 days",
        ))

    # P1: no DAgger runs at all and SR not 0 (new customers handled by onboarding)
    if profile.last_dagger_run is None and profile.current_sr >= 20:
        actions.append(PlaybookAction(
            action_id=next_id(profile.partner[:4].upper()),
            priority="P1",
            category="training",
            title="First DAgger Run Kickoff Call",
            description=(
                "Partner has never run DAgger. Schedule a kickoff call to explain "
                "the DAgger workflow, set up teleoperation data collection, and "
                "target SR improvement beyond BC baseline."
            ),
            owner="CSM",
            due_in_days=10,
            blockers=["Teleoperation hardware availability"],
            success_metric="First DAgger run completed",
        ))

    # P1: renewal < 60 days → QBR
    if profile.renewal_in_days < 60:
        actions.append(PlaybookAction(
            action_id=next_id(profile.partner[:4].upper()),
            priority="P1",
            category="retention",
            title="Schedule Quarterly Business Review (QBR)",
            description=(
                f"Renewal is {profile.renewal_in_days} days away. Schedule QBR to "
                "review ROI, SR improvements, roadmap alignment, and contract terms. "
                "Prepare deck with SR trajectory and cost savings."
            ),
            owner="CSM",
            due_in_days=14,
            blockers=["Executive availability on partner side"],
            success_metric="QBR completed; renewal intent confirmed in writing",
        ))

    # P2: new customer — full onboarding path
    if profile.days_since_signup <= 7:
        actions.append(PlaybookAction(
            action_id=next_id(profile.partner[:4].upper()),
            priority="P0",
            category="training",
            title="Day-1 Onboarding — Environment Setup",
            description=(
                "Partner just signed. Complete environment provisioning checklist: "
                "OCI tenancy access, API key generation, SDK install, first training "
                "run on the quickstart task. Target first SR reading within 5 days."
            ),
            owner="CSM",
            due_in_days=2,
            blockers=["OCI tenancy provisioning"],
            success_metric="First training run submitted; SR reading > 0%",
        ))
        actions.append(PlaybookAction(
            action_id=next_id(profile.partner[:4].upper()),
            priority="P1",
            category="training",
            title="Week-1 Check-in — Dataset Validation",
            description=(
                "Schedule 30-min check-in to review initial dataset quality, "
                "correct common setup errors, and set 30-day SR target."
            ),
            owner="CSM",
            due_in_days=7,
            blockers=[],
            success_metric="Dataset validated; 30-day SR target agreed",
        ))

    # P2: low NPS
    if profile.nps_score is not None and profile.nps_score < 6:
        actions.append(PlaybookAction(
            action_id=next_id(profile.partner[:4].upper()),
            priority="P1",
            category="retention",
            title="NPS Recovery — Partner Sentiment Call",
            description=(
                f"NPS score is {profile.nps_score}/10, indicating dissatisfaction. "
                "Schedule a 1:1 call with partner lead to uncover pain points and "
                "draft a remediation plan within 5 business days."
            ),
            owner="CSM",
            due_in_days=5,
            blockers=["Partner availability"],
            success_metric="Root cause documented; NPS follow-up survey shows >= 7 in 30 days",
        ))

    # P2: eval coverage gap
    if profile.demo_count < 5 and profile.days_since_signup > 14:
        actions.append(PlaybookAction(
            action_id=next_id(profile.partner[:4].upper()),
            priority="P2",
            category="eval",
            title="Increase Eval Coverage — Run Closed-Loop Benchmarks",
            description=(
                f"Only {profile.demo_count} demos recorded. Encourage partner to run "
                "closed-loop eval with at least 20 episodes per task to get statistically "
                "meaningful SR estimates. Share eval runbook."
            ),
            owner="partner",
            due_in_days=14,
            blockers=["Simulation environment availability"],
            success_metric="20+ eval episodes completed per task; SR confidence interval < 5pp",
        ))

    # P2: strategic tier — expansion opportunity if SR > 60%
    if profile.tier == "strategic" and profile.current_sr >= 60:
        actions.append(PlaybookAction(
            action_id=next_id(profile.partner[:4].upper()),
            priority="P2",
            category="expansion",
            title="Expansion Discovery — Multi-Task Upsell",
            description=(
                f"SR at {profile.current_sr:.0f}% on primary task. Initiate expansion "
                "conversation around multi-task training, additional robot embodiments, "
                "or fleet-scale deployment. Prepare ROI model."
            ),
            owner="CSM",
            due_in_days=21,
            blockers=["Budget cycle timing"],
            success_metric="Expansion discovery call completed; upsell opportunity logged in CRM",
        ))

    # P3: documentation / self-service nudge
    actions.append(PlaybookAction(
        action_id=next_id(profile.partner[:4].upper()),
        priority="P3",
        category="training",
        title="Share Latest Best-Practice Runbook",
        description=(
            "Send partner the latest OCI Robot Cloud training best-practices guide "
            "covering dataset curation, hyperparameter tuning, and DAgger scheduling. "
            "Track open rate via email."
        ),
        owner="CSM",
        due_in_days=30,
        blockers=[],
        success_metric="Partner confirms receipt; at least one recommendation implemented",
    ))

    # Sort: P0 first, then P1, P2, P3
    priority_order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    actions.sort(key=lambda a: priority_order.get(a.priority, 9))

    return actions[:12]  # cap at 12 per partner


# ---------------------------------------------------------------------------
# HTML report
# ---------------------------------------------------------------------------

RISK_BADGE = {
    "critical": '<span class="badge critical">🔴 CRITICAL</span>',
    "high":     '<span class="badge high">🟡 HIGH</span>',
    "medium":   '<span class="badge medium">🟠 MEDIUM</span>',
    "low":      '<span class="badge low">🟢 LOW</span>',
}

PRIORITY_COLOR = {"P0": "#ef4444", "P1": "#f97316", "P2": "#eab308", "P3": "#6b7280"}
CATEGORY_ICON  = {
    "training":  "🏋",
    "eval":      "📊",
    "support":   "🛠",
    "expansion": "📈",
    "retention": "🔒",
}


def _sr_bar_color(risk: str) -> str:
    return {"critical": "#ef4444", "high": "#f97316", "medium": "#eab308", "low": "#22c55e"}.get(risk, "#94a3b8")


def _build_svg_health(profiles: List[PartnerProfile]) -> str:
    bar_h = 32
    gap   = 12
    label_w = 160
    chart_w = 500
    total_h = len(profiles) * (bar_h + gap) + 40
    svg_w   = label_w + chart_w + 80

    bars = ""
    for i, p in enumerate(profiles):
        y      = 20 + i * (bar_h + gap)
        fill_w = int(p.current_sr / 100 * chart_w)
        color  = _sr_bar_color(p.risk_level)
        name   = p.partner.replace("_", " ").title()
        bars += (
            f'<text x="{label_w - 8}" y="{y + bar_h // 2 + 5}" '
            f'text-anchor="end" fill="#cbd5e1" font-size="13" font-family="monospace">{name}</text>'
            f'<rect x="{label_w}" y="{y}" width="{chart_w}" height="{bar_h}" fill="#334155" rx="4"/>'
            f'<rect x="{label_w}" y="{y}" width="{fill_w}" height="{bar_h}" fill="{color}" rx="4"/>'
            f'<text x="{label_w + fill_w + 6}" y="{y + bar_h // 2 + 5}" '
            f'fill="#f1f5f9" font-size="12" font-family="monospace">{p.current_sr:.0f}%</text>'
        )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{svg_w}" height="{total_h}" '
        f'style="background:#0f172a;border-radius:8px;padding:8px">'
        f'{bars}'
        f'</svg>'
    )


def _action_card(action: PlaybookAction) -> str:
    color   = PRIORITY_COLOR.get(action.priority, "#6b7280")
    icon    = CATEGORY_ICON.get(action.category, "•")
    blocker_html = (
        "".join(f'<li>{b}</li>' for b in action.blockers)
        if action.blockers else "<li><em>None</em></li>"
    )
    due_date = (date.today() + timedelta(days=action.due_in_days)).strftime("%b %d, %Y")
    return f"""
    <div class="action-card" style="border-left:4px solid {color}">
      <div class="action-header">
        <span class="priority-badge" style="background:{color}">{action.priority}</span>
        <span class="category-icon">{icon}</span>
        <strong>{action.title}</strong>
        <span class="owner-tag">{action.owner}</span>
      </div>
      <p class="action-desc">{action.description}</p>
      <div class="action-meta">
        <span>Due: <strong>{due_date}</strong> (+{action.due_in_days}d)</span>
        <span>Metric: <em>{action.success_metric}</em></span>
      </div>
      <div class="blockers"><strong>Blockers:</strong><ul>{blocker_html}</ul></div>
    </div>"""


def _partner_section(profile: PartnerProfile, actions: List[PlaybookAction]) -> str:
    badge   = RISK_BADGE.get(profile.risk_level, profile.risk_level)
    trend_icon = {"improving": "↑", "plateau": "→", "declining": "↓", "too_early": "?"}.get(profile.sr_trend, "?")
    cards   = "".join(_action_card(a) for a in actions)
    dagger  = f"{profile.last_dagger_run}d ago" if profile.last_dagger_run is not None else "never"
    nps     = str(profile.nps_score) if profile.nps_score is not None else "N/A"
    return f"""
  <section class="partner-section">
    <div class="partner-header">
      <h2>{profile.partner.replace('_', ' ').title()}</h2>
      {badge}
      <span class="tier-tag">{profile.tier.upper()}</span>
    </div>
    <div class="partner-stats">
      <div class="stat"><label>SR</label><value>{profile.current_sr:.0f}%&nbsp;{trend_icon}</value></div>
      <div class="stat"><label>Days Active</label><value>{profile.days_since_signup}</value></div>
      <div class="stat"><label>DAgger</label><value>{dagger}</value></div>
      <div class="stat"><label>Open Tickets</label><value>{profile.support_tickets_open}</value></div>
      <div class="stat"><label>NPS</label><value>{nps}</value></div>
      <div class="stat"><label>Renewal In</label><value>{profile.renewal_in_days}d</value></div>
      <div class="stat"><label>Actions</label><value>{len(actions)}</value></div>
    </div>
    <div class="actions-grid">{cards}</div>
  </section>"""


def _summary_table(profiles: List[PartnerProfile], playbooks: dict) -> str:
    rows = ""
    for p in profiles:
        acts  = playbooks[p.partner]
        p0cnt = sum(1 for a in acts if a.priority == "P0")
        color = _sr_bar_color(p.risk_level)
        trend_icon = {"improving": "↑ improving", "plateau": "→ plateau",
                      "declining": "↓ declining", "too_early": "? early"}.get(p.sr_trend, p.sr_trend)
        rows += f"""
      <tr>
        <td><strong>{p.partner.replace('_', ' ').title()}</strong></td>
        <td>{p.tier}</td>
        <td style="color:{color};font-weight:bold">{p.current_sr:.0f}%</td>
        <td>{trend_icon}</td>
        <td>{p.support_tickets_open}</td>
        <td>{p.renewal_in_days}d</td>
        <td>{RISK_BADGE.get(p.risk_level, p.risk_level)}</td>
        <td style="color:#ef4444;font-weight:bold">{p0cnt} P0</td>
        <td>{len(acts)} total</td>
      </tr>"""
    return f"""
  <section class="summary-section">
    <h2>Partner Summary</h2>
    <table>
      <thead>
        <tr>
          <th>Partner</th><th>Tier</th><th>SR</th><th>Trend</th>
          <th>Tickets</th><th>Renewal</th><th>Risk</th>
          <th>P0 Actions</th><th>Total Actions</th>
        </tr>
      </thead>
      <tbody>{rows}</tbody>
    </table>
  </section>"""


def build_html_report(profiles: List[PartnerProfile]) -> str:
    playbooks = {p.partner: generate_playbook(p) for p in profiles}
    svg       = _build_svg_health(profiles)
    sections  = "".join(_partner_section(p, playbooks[p.partner]) for p in profiles)
    summary   = _summary_table(profiles, playbooks)
    ts        = date.today().strftime("%Y-%m-%d")
    total_actions = sum(len(v) for v in playbooks.values())
    p0_total  = sum(1 for v in playbooks.values() for a in v if a.priority == "P0")

    css = """
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: #1e293b; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; padding: 24px; }
    h1 { color: #C74634; font-size: 2rem; margin-bottom: 4px; }
    h2 { color: #C74634; font-size: 1.3rem; margin-bottom: 16px; }
    .subtitle { color: #94a3b8; margin-bottom: 32px; font-size: 0.95rem; }
    .kpi-row { display: flex; gap: 16px; margin-bottom: 32px; flex-wrap: wrap; }
    .kpi { background: #0f172a; border: 1px solid #334155; border-radius: 8px; padding: 16px 24px; min-width: 140px; }
    .kpi label { display: block; color: #94a3b8; font-size: 0.8rem; text-transform: uppercase; margin-bottom: 4px; }
    .kpi value { font-size: 1.8rem; font-weight: bold; color: #f1f5f9; }
    .svg-section { margin-bottom: 32px; }
    .svg-section h2 { margin-bottom: 12px; }
    .partner-section { background: #0f172a; border: 1px solid #334155; border-radius: 10px;
                        padding: 24px; margin-bottom: 28px; }
    .partner-header { display: flex; align-items: center; gap: 12px; margin-bottom: 16px; flex-wrap: wrap; }
    .partner-header h2 { margin: 0; }
    .badge { padding: 3px 10px; border-radius: 12px; font-size: 0.82rem; font-weight: bold; }
    .badge.critical { background: #450a0a; color: #fca5a5; }
    .badge.high     { background: #431407; color: #fdba74; }
    .badge.medium   { background: #422006; color: #fde68a; }
    .badge.low      { background: #052e16; color: #86efac; }
    .tier-tag { background: #1e3a5f; color: #93c5fd; padding: 3px 10px; border-radius: 12px;
                font-size: 0.78rem; font-weight: bold; }
    .partner-stats { display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 20px; }
    .stat { background: #1e293b; border: 1px solid #334155; border-radius: 6px;
            padding: 8px 14px; min-width: 90px; text-align: center; }
    .stat label { display: block; color: #94a3b8; font-size: 0.72rem; text-transform: uppercase; }
    .stat value { display: block; font-size: 1.1rem; font-weight: bold; color: #f1f5f9; }
    .actions-grid { display: flex; flex-direction: column; gap: 12px; }
    .action-card { background: #1e293b; border-radius: 8px; padding: 14px 16px; }
    .action-header { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; flex-wrap: wrap; }
    .priority-badge { color: #fff; padding: 2px 8px; border-radius: 4px;
                      font-size: 0.78rem; font-weight: bold; flex-shrink: 0; }
    .category-icon { font-size: 1rem; }
    .owner-tag { margin-left: auto; background: #1e3a5f; color: #93c5fd;
                 padding: 2px 8px; border-radius: 10px; font-size: 0.75rem; }
    .action-desc { color: #cbd5e1; font-size: 0.88rem; margin-bottom: 8px; line-height: 1.5; }
    .action-meta { display: flex; gap: 24px; font-size: 0.82rem; color: #94a3b8; margin-bottom: 6px; flex-wrap: wrap; }
    .blockers { font-size: 0.8rem; color: #94a3b8; }
    .blockers ul { padding-left: 18px; margin-top: 3px; }
    .summary-section { margin-top: 32px; }
    table { width: 100%; border-collapse: collapse; font-size: 0.88rem; }
    th { background: #0f172a; color: #94a3b8; text-align: left; padding: 10px 12px;
         border-bottom: 2px solid #334155; }
    td { padding: 10px 12px; border-bottom: 1px solid #1e293b; }
    tr:hover td { background: #1e293b; }
    """

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>OCI Robot Cloud — Customer Success Playbooks</title>
  <style>{css}</style>
</head>
<body>
  <h1>OCI Robot Cloud — Customer Success Playbooks</h1>
  <p class="subtitle">Generated {ts} &nbsp;·&nbsp; {len(profiles)} partners &nbsp;·&nbsp;
     {total_actions} actions &nbsp;·&nbsp;
     <span style="color:#ef4444;font-weight:bold">{p0_total} P0 items require immediate attention</span></p>

  <div class="kpi-row">
    <div class="kpi"><label>Partners</label><value>{len(profiles)}</value></div>
    <div class="kpi"><label>P0 Actions</label><value style="color:#ef4444">{p0_total}</value></div>
    <div class="kpi"><label>Total Actions</label><value>{total_actions}</value></div>
    <div class="kpi"><label>Avg SR</label><value>{sum(p.current_sr for p in profiles)/len(profiles):.0f}%</value></div>
    <div class="kpi"><label>Critical/High</label><value style="color:#f97316">{sum(1 for p in profiles if p.risk_level in ('critical','high'))}</value></div>
  </div>

  <div class="svg-section">
    <h2>Partner Health Overview — Success Rate</h2>
    {svg}
  </div>

  {summary}

  {sections}
</body>
</html>"""


# ---------------------------------------------------------------------------
# HTTP server
# ---------------------------------------------------------------------------

def make_handler(profiles: List[PartnerProfile]):
    html_cache = build_html_report(profiles)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            print(f"[{self.address_string()}] {fmt % args}")

        def do_GET(self):
            if self.path in ("/", "/index.html", "/playbook"):
                body = html_cache.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif self.path == "/api/playbooks":
                data = []
                for p in profiles:
                    acts = generate_playbook(p)
                    data.append({
                        "partner": p.partner,
                        "risk_level": p.risk_level,
                        "current_sr": p.current_sr,
                        "actions": [
                            {"id": a.action_id, "priority": a.priority,
                             "title": a.title, "owner": a.owner,
                             "due_in_days": a.due_in_days}
                            for a in acts
                        ],
                    })
                body = json.dumps(data, indent=2).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif self.path == "/health":
                body = b'{"status":"ok"}'
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b"Not found")

    return Handler


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="OCI Robot Cloud — Customer Success Playbook Generator")
    parser.add_argument("--mock",   action="store_true", default=True,
                        help="Use mock partner data (default: True)")
    parser.add_argument("--port",   type=int, default=8070,
                        help="HTTP server port (default: 8070)")
    parser.add_argument("--output", type=str, default=None,
                        help="Save HTML to file and exit (e.g. /tmp/customer_success_playbook.html)")
    args = parser.parse_args()

    profiles = generate_partner_profiles()

    if args.output:
        html = build_html_report(profiles)
        with open(args.output, "w") as f:
            f.write(html)
        print(f"Report saved to {args.output}")
        return

    print(f"OCI Robot Cloud — Customer Success Playbook Generator")
    print(f"Serving on http://localhost:{args.port}/")
    print(f"  GET /           — HTML playbook report")
    print(f"  GET /api/playbooks — JSON summary")
    print(f"  GET /health     — health check")

    handler = make_handler(profiles)
    server  = HTTPServer(("0.0.0.0", args.port), handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.server_close()


if __name__ == "__main__":
    main()
