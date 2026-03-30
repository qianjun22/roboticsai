#!/usr/bin/env python3
"""
partner_health_scorecard.py — Generates weekly health scorecards per design partner (port 8061).

Composite score across training cadence, success rate trend, DAgger engagement,
support tickets, and renewal risk. Renders a dark-themed HTML dashboard with
per-partner dimension bars, grade badges, and renewal risk summary.

Usage:
    python src/api/partner_health_scorecard.py --port 8061 --mock
    python src/api/partner_health_scorecard.py --output /tmp/partner_scorecards.html
    # → http://localhost:8061
"""

import argparse
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import List
from urllib.parse import urlparse

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class HealthDimension:
    name: str
    score: float          # 0-10
    weight: float
    description: str
    trend: str            # "up" | "down" | "flat"


@dataclass
class PartnerScorecard:
    partner_id: str
    company: str
    week_of: str          # YYYY-WW
    dimensions: List[HealthDimension]
    composite_score: float
    grade: str            # A / B / C / D / F
    renewal_risk: str     # low / medium / high
    recommendations: List[str]


# ---------------------------------------------------------------------------
# Mock data factory
# ---------------------------------------------------------------------------

def _week_of(dt: datetime = None) -> str:
    dt = dt or datetime.now()
    return f"{dt.year}-{dt.strftime('%W')}"


def generate_scorecard(partner_id: str) -> PartnerScorecard:
    """Return a PartnerScorecard for the given partner_id (mock data)."""
    week = _week_of()

    catalogue = {
        "AcmeRobotics": PartnerScorecard(
            partner_id="AcmeRobotics",
            company="Acme Robotics Inc.",
            week_of=week,
            dimensions=[
                HealthDimension("training_cadence",     9.0, 0.25,
                                "5 fine-tune jobs run this week — above average",          "up"),
                HealthDimension("success_rate_trend",   8.5, 0.30,
                                "SR at 72%, up +4 pp vs last week",                        "up"),
                HealthDimension("dagger_engagement",    9.0, 0.20,
                                "3 DAgger iterations completed",                           "up"),
                HealthDimension("data_freshness",       7.5, 0.15,
                                "120 new demos uploaded in the last 7 days",               "up"),
                HealthDimension("support_health",       9.5, 0.10,
                                "No open tickets; last resolved 2 days ago",               "flat"),
            ],
            composite_score=8.4,
            grade="A",
            renewal_risk="low",
            recommendations=[
                "Consider enabling multi-task curriculum to push SR above 80%.",
                "Share success playbook with other design partners.",
                "Evaluate Cosmos world model integration for broader task coverage.",
            ],
        ),

        "BotCo": PartnerScorecard(
            partner_id="BotCo",
            company="BotCo Systems LLC",
            week_of=week,
            dimensions=[
                HealthDimension("training_cadence",     7.0, 0.25,
                                "2 fine-tune jobs this week — acceptable but slowing",     "flat"),
                HealthDimension("success_rate_trend",   6.5, 0.30,
                                "SR at 58%, flat for 2 weeks",                             "flat"),
                HealthDimension("dagger_engagement",    3.5, 0.20,
                                "No DAgger runs in 10 days",                               "down"),
                HealthDimension("data_freshness",       4.0, 0.15,
                                "Last demo upload was 12 days ago",                        "down"),
                HealthDimension("support_health",       8.0, 0.10,
                                "1 open non-blocking ticket (P3)",                         "flat"),
            ],
            composite_score=6.1,
            grade="B",
            renewal_risk="medium",
            recommendations=[
                "Resume DAgger iterations — stale policy likely causing SR plateau.",
                "Upload at least 50 new demos to refresh training distribution.",
                "Schedule a CSM check-in call to unblock data collection pipeline.",
            ],
        ),

        "NexaArm": PartnerScorecard(
            partner_id="NexaArm",
            company="NexaArm Technologies",
            week_of=week,
            dimensions=[
                HealthDimension("training_cadence",     4.5, 0.25,
                                "1 fine-tune job this week; 2 failed mid-run",             "down"),
                HealthDimension("success_rate_trend",   3.5, 0.30,
                                "SR at 31%, down -8 pp over 3 weeks",                      "down"),
                HealthDimension("dagger_engagement",    4.0, 0.20,
                                "1 DAgger run started but aborted",                        "down"),
                HealthDimension("data_freshness",       2.5, 0.15,
                                "No new demo data in 3 weeks",                             "down"),
                HealthDimension("support_health",       7.0, 0.10,
                                "No open tickets but no support activity either",          "flat"),
            ],
            composite_score=4.2,
            grade="C",
            renewal_risk="high",
            recommendations=[
                "URGENT: SR declining — review failure modes with engineering team.",
                "Upload fresh demos immediately; data staleness is degrading policy.",
                "Assign a dedicated CSM to conduct weekly check-ins.",
                "Consider rollback to last stable checkpoint while debugging.",
            ],
        ),

        "ViperRob": PartnerScorecard(
            partner_id="ViperRob",
            company="ViperRob Automation",
            week_of=week,
            dimensions=[
                HealthDimension("training_cadence",     1.5, 0.25,
                                "No fine-tune jobs in 2 weeks",                            "down"),
                HealthDimension("success_rate_trend",   2.0, 0.30,
                                "SR at 14%, down -15 pp; effectively inactive",            "down"),
                HealthDimension("dagger_engagement",    2.5, 0.20,
                                "No DAgger activity this month",                           "down"),
                HealthDimension("data_freshness",       3.0, 0.15,
                                "Last demo upload was 28 days ago",                        "down"),
                HealthDimension("support_health",       2.0, 0.10,
                                "2 open blocking tickets (P1) unacknowledged for 5 days",  "down"),
            ],
            composite_score=2.8,
            grade="D",
            renewal_risk="high",
            recommendations=[
                "CRITICAL: 2 unresolved P1 blockers — escalate to engineering immediately.",
                "Executive outreach needed; partner may be considering churn.",
                "Offer complimentary onboarding session to restart usage.",
                "Create 30-day recovery plan with milestone checkpoints.",
            ],
        ),
    }

    if partner_id not in catalogue:
        raise KeyError(f"Unknown partner_id: {partner_id!r}")
    return catalogue[partner_id]


def all_scorecards() -> List[PartnerScorecard]:
    """Return scorecards for all 4 mock design partners."""
    return [generate_scorecard(pid) for pid in
            ("AcmeRobotics", "BotCo", "NexaArm", "ViperRob")]


# ---------------------------------------------------------------------------
# HTML rendering helpers
# ---------------------------------------------------------------------------

_GRADE_COLOR = {"A": "#22c55e", "B": "#3b82f6", "C": "#f59e0b", "D": "#ef4444", "F": "#ef4444"}
_RISK_COLOR  = {"low": "#22c55e", "medium": "#f59e0b", "high": "#ef4444"}
_TREND_ARROW = {"up": "▲", "down": "▼", "flat": "►"}
_TREND_COLOR = {"up": "#22c55e", "down": "#ef4444", "flat": "#94a3b8"}

_DIM_LABEL = {
    "training_cadence":   "Training Cadence",
    "success_rate_trend": "Success Rate Trend",
    "dagger_engagement":  "DAgger Engagement",
    "data_freshness":     "Data Freshness",
    "support_health":     "Support Health",
}

_BASE_STYLE = """
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif;
         padding: 2rem; }
  h1   { font-size: 1.6rem; font-weight: 700; color: #f8fafc; margin-bottom: 0.25rem; }
  h2   { font-size: 1.1rem; font-weight: 600; color: #cbd5e1; margin-bottom: 1rem; }
  .subtitle { color: #64748b; font-size: 0.85rem; margin-bottom: 2rem; }
  .risk-banner { background: #1e293b; border: 1px solid #334155; border-radius: 8px;
                 padding: 1rem 1.5rem; margin-bottom: 2rem; }
  .risk-banner h2 { margin-bottom: 0.5rem; font-size: 1rem; }
  .risk-list { display: flex; gap: 0.75rem; flex-wrap: wrap; }
  .risk-badge { padding: 0.3rem 0.8rem; border-radius: 999px; font-size: 0.8rem;
                font-weight: 600; }
  .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; }
  .card { background: #1e293b; border: 1px solid #334155; border-radius: 12px;
          padding: 1.5rem; }
  .card-header { display: flex; justify-content: space-between; align-items: flex-start;
                 margin-bottom: 1rem; }
  .card-title { font-size: 1.05rem; font-weight: 700; color: #f1f5f9; }
  .card-company { font-size: 0.78rem; color: #64748b; margin-top: 0.2rem; }
  .grade-badge { font-size: 1.6rem; font-weight: 900; width: 48px; height: 48px;
                 border-radius: 8px; display: flex; align-items: center;
                 justify-content: center; flex-shrink: 0; }
  .composite { font-size: 2rem; font-weight: 800; margin: 0.5rem 0; }
  .composite span { font-size: 1rem; font-weight: 400; color: #64748b; }
  .risk-label { font-size: 0.75rem; font-weight: 600; padding: 0.2rem 0.6rem;
                border-radius: 999px; display: inline-block; margin-bottom: 1rem; }
  .dim-row { margin-bottom: 0.6rem; }
  .dim-meta { display: flex; justify-content: space-between; align-items: center;
              font-size: 0.78rem; margin-bottom: 0.2rem; }
  .dim-name { color: #94a3b8; }
  .dim-score { font-weight: 700; }
  .dim-trend { font-size: 0.7rem; margin-left: 0.3rem; }
  .bar-bg { background: #0f172a; border-radius: 999px; height: 6px; }
  .bar-fill { height: 6px; border-radius: 999px; }
  .recs { margin-top: 1rem; border-top: 1px solid #334155; padding-top: 0.9rem; }
  .recs-title { font-size: 0.75rem; color: #64748b; text-transform: uppercase;
                letter-spacing: 0.05em; margin-bottom: 0.5rem; }
  .rec-item { font-size: 0.78rem; color: #cbd5e1; padding: 0.2rem 0;
              padding-left: 1rem; position: relative; }
  .rec-item::before { content: "•"; position: absolute; left: 0; color: #475569; }
  .week-label { font-size: 0.75rem; color: #475569; margin-top: 0.5rem; }
  @media (max-width: 800px) { .grid { grid-template-columns: 1fr; } }
</style>
"""


def _dim_bar(dim: HealthDimension) -> str:
    pct = dim.score / 10 * 100
    if dim.score >= 7:
        color = "#22c55e"
    elif dim.score >= 4:
        color = "#f59e0b"
    else:
        color = "#ef4444"
    arrow = _TREND_ARROW[dim.trend]
    arrow_color = _TREND_COLOR[dim.trend]
    label = _DIM_LABEL.get(dim.name, dim.name.replace("_", " ").title())
    return f"""
    <div class="dim-row" title="{dim.description}">
      <div class="dim-meta">
        <span class="dim-name">{label}</span>
        <span class="dim-score" style="color:{color}">
          {dim.score:.1f}
          <span class="dim-trend" style="color:{arrow_color}">{arrow}</span>
        </span>
      </div>
      <div class="bar-bg">
        <div class="bar-fill" style="width:{pct:.1f}%;background:{color};"></div>
      </div>
    </div>"""


def _partner_card(card: PartnerScorecard, link: bool = True) -> str:
    grade_color = _GRADE_COLOR.get(card.grade, "#ef4444")
    risk_color  = _RISK_COLOR.get(card.renewal_risk, "#94a3b8")
    dims_html   = "".join(_dim_bar(d) for d in card.dimensions)
    recs_html   = "".join(f'<div class="rec-item">{r}</div>' for r in card.recommendations)
    title_html  = (f'<a href="/scorecards/{card.partner_id}" '
                   f'style="color:inherit;text-decoration:none;">{card.company}</a>'
                   if link else card.company)
    return f"""
    <div class="card">
      <div class="card-header">
        <div>
          <div class="card-title">{title_html}</div>
          <div class="card-company">{card.partner_id}</div>
        </div>
        <div class="grade-badge" style="background:{grade_color}22;color:{grade_color};">
          {card.grade}
        </div>
      </div>
      <div class="composite" style="color:{grade_color};">
        {card.composite_score:.1f}<span> / 10</span>
      </div>
      <span class="risk-label" style="background:{risk_color}22;color:{risk_color};">
        {card.renewal_risk.upper()} RENEWAL RISK
      </span>
      {dims_html}
      <div class="recs">
        <div class="recs-title">Recommendations</div>
        {recs_html}
      </div>
      <div class="week-label">Week {card.week_of}</div>
    </div>"""


def render_dashboard(scorecards: List[PartnerScorecard]) -> str:
    """Render dark-themed HTML dashboard with 2x2 partner card grid."""
    high_risk = [c for c in scorecards if c.renewal_risk == "high"]
    risk_badges = "".join(
        f'<span class="risk-badge" style="background:#ef444422;color:#ef4444;">'
        f'{c.company}</span>'
        for c in high_risk
    )
    if not high_risk:
        risk_badges = '<span style="color:#22c55e;font-size:0.85rem;">No high-risk partners this week.</span>'

    cards_html = "".join(_partner_card(c) for c in scorecards)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>OCI Robot Cloud — Partner Health Scorecards</title>
  {_BASE_STYLE}
</head>
<body>
  <h1>OCI Robot Cloud — Partner Health Scorecards</h1>
  <div class="subtitle">Generated {now_str} &nbsp;·&nbsp; 4 design partners</div>

  <div class="risk-banner">
    <h2>Renewal Risk Alert</h2>
    <div class="risk-list">{risk_badges}</div>
  </div>

  <div class="grid">{cards_html}</div>
</body>
</html>"""


def render_scorecard(card: PartnerScorecard) -> str:
    """Render detailed single-partner scorecard page."""
    grade_color = _GRADE_COLOR.get(card.grade, "#ef4444")
    risk_color  = _RISK_COLOR.get(card.renewal_risk, "#94a3b8")
    dims_rows   = "".join(_dim_bar(d) for d in card.dimensions)
    recs_html   = "".join(f'<div class="rec-item">{r}</div>' for r in card.recommendations)
    now_str     = datetime.now().strftime("%Y-%m-%d %H:%M")

    dim_table_rows = "".join(
        f"<tr><td style='padding:0.4rem 0.6rem;color:#94a3b8;'>"
        f"{_DIM_LABEL.get(d.name, d.name)}</td>"
        f"<td style='padding:0.4rem 0.6rem;font-weight:700;'>{d.score:.1f}</td>"
        f"<td style='padding:0.4rem 0.6rem;color:#64748b;'>{d.weight:.0%}</td>"
        f"<td style='padding:0.4rem 0.6rem;font-size:0.85rem;color:#94a3b8;'>{d.description}</td>"
        f"<td style='padding:0.4rem 0.6rem;color:{_TREND_COLOR[d.trend]};'>"
        f"{_TREND_ARROW[d.trend]} {d.trend}</td></tr>"
        for d in card.dimensions
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{card.company} — Health Scorecard</title>
  {_BASE_STYLE}
  <style>
    table {{ width: 100%; border-collapse: collapse; margin-top: 1rem; }}
    th {{ padding: 0.4rem 0.6rem; text-align: left; color: #475569;
          font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em;
          border-bottom: 1px solid #334155; }}
    td {{ border-bottom: 1px solid #1e293b; }}
    .back-link {{ color: #60a5fa; text-decoration: none; font-size: 0.85rem;
                  display: inline-block; margin-bottom: 1.5rem; }}
    .detail-card {{ background: #1e293b; border: 1px solid #334155;
                    border-radius: 12px; padding: 2rem; max-width: 780px; }}
  </style>
</head>
<body>
  <a class="back-link" href="/scorecards">← All Partners</a>
  <div class="detail-card">
    <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:1.5rem;">
      <div>
        <h1>{card.company}</h1>
        <div class="subtitle" style="margin-bottom:0;">{card.partner_id} &nbsp;·&nbsp; Week {card.week_of} &nbsp;·&nbsp; {now_str}</div>
      </div>
      <div class="grade-badge" style="background:{grade_color}22;color:{grade_color};font-size:2rem;width:64px;height:64px;">
        {card.grade}
      </div>
    </div>

    <div style="margin-bottom:1.5rem;">
      <div class="composite" style="color:{grade_color};">{card.composite_score:.1f}<span> / 10</span></div>
      <span class="risk-label" style="background:{risk_color}22;color:{risk_color};">
        {card.renewal_risk.upper()} RENEWAL RISK
      </span>
    </div>

    <h2>Dimension Scores</h2>
    {dims_rows}

    <table>
      <thead>
        <tr>
          <th>Dimension</th><th>Score</th><th>Weight</th>
          <th>Description</th><th>Trend</th>
        </tr>
      </thead>
      <tbody>{dim_table_rows}</tbody>
    </table>

    <div class="recs" style="margin-top:1.5rem;">
      <div class="recs-title">Recommendations</div>
      {recs_html}
    </div>
  </div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# HTTP server
# ---------------------------------------------------------------------------

def _scorecard_to_dict(card: PartnerScorecard) -> dict:
    return {
        "partner_id":     card.partner_id,
        "company":        card.company,
        "week_of":        card.week_of,
        "composite_score": card.composite_score,
        "grade":          card.grade,
        "renewal_risk":   card.renewal_risk,
        "recommendations": card.recommendations,
        "dimensions": [
            {
                "name":        d.name,
                "score":       d.score,
                "weight":      d.weight,
                "description": d.description,
                "trend":       d.trend,
            }
            for d in card.dimensions
        ],
    }


class ScorecardHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # suppress access log noise
        pass

    def _send(self, code: int, content_type: str, body: str | bytes):
        data = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        parsed = urlparse(self.path)
        path   = parsed.path.rstrip("/") or "/"

        if path == "/scorecards":
            cards = all_scorecards()
            self._send(200, "text/html; charset=utf-8", render_dashboard(cards))

        elif path.startswith("/scorecards/"):
            pid = path[len("/scorecards/"):]
            try:
                card = generate_scorecard(pid)
                self._send(200, "text/html; charset=utf-8", render_scorecard(card))
            except KeyError:
                self._send(404, "text/plain", f"Partner not found: {pid}")

        elif path == "/api/scorecards":
            cards = all_scorecards()
            payload = json.dumps([_scorecard_to_dict(c) for c in cards], indent=2)
            self._send(200, "application/json", payload)

        elif path in ("/", ""):
            self._send(302, "text/plain", "")
            self.send_header("Location", "/scorecards")

        else:
            self._send(404, "text/plain", "Not found")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="OCI Robot Cloud — Partner Health Scorecard Service"
    )
    parser.add_argument("--mock",   action="store_true", default=True,
                        help="Use mock partner data (default: True)")
    parser.add_argument("--port",   type=int, default=8061,
                        help="HTTP port (default: 8061)")
    parser.add_argument("--output", type=str, default=None,
                        help="Write dashboard HTML to file and exit (e.g. /tmp/partner_scorecards.html)")
    args = parser.parse_args()

    cards = all_scorecards()

    if args.output:
        html = render_dashboard(cards)
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(html)
        print(f"[scorecard] Dashboard written to {args.output}")
        return

    print(f"[scorecard] Starting on http://localhost:{args.port}")
    print(f"[scorecard] Routes:")
    print(f"            GET /scorecards            → HTML dashboard")
    print(f"            GET /scorecards/<partner>  → single partner detail")
    print(f"            GET /api/scorecards        → JSON all scorecards")
    server = HTTPServer(("", args.port), ScorecardHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[scorecard] Stopped.")


if __name__ == "__main__":
    main()
