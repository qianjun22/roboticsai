#!/usr/bin/env python3
"""
Model governance and responsible AI report for GR00T enterprise deployments.
Covers data provenance, bias, safety, and compliance.

Usage:
    python model_governance_report.py --mock --output /tmp/model_governance_report.html
"""

import argparse
import math
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import List


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class GovernanceDimension:
    name: str
    score: float
    max_score: float
    status: str  # compliant / partial / non_compliant
    findings: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)

    @property
    def pct(self) -> float:
        return (self.score / self.max_score * 100) if self.max_score > 0 else 0.0


@dataclass
class PartnerGovernance:
    partner_name: str
    tier: str
    overall_score: float
    compliant_dims: int
    total_dims: int
    certification_level: str
    next_review_date: str


@dataclass
class GovernanceReport:
    overall_score: float
    certification_level: str
    dims: List[GovernanceDimension]
    partner_results: List[PartnerGovernance]

    @property
    def compliant_count(self) -> int:
        return sum(1 for d in self.dims if d.status == "compliant")

    @property
    def lowest_dim(self) -> GovernanceDimension:
        return min(self.dims, key=lambda d: d.pct)


# ---------------------------------------------------------------------------
# Dimension definitions (mock data)
# ---------------------------------------------------------------------------

DIMENSION_META = {
    "data_provenance": {
        "label": "Data Provenance",
        "description": "Training data origin, licensing, and consent",
    },
    "bias_testing": {
        "label": "Bias Testing",
        "description": "Demographic, task, and environmental bias evaluation",
    },
    "safety_constraints": {
        "label": "Safety Constraints",
        "description": "Velocity/force/workspace limits and kill-switch",
    },
    "transparency": {
        "label": "Transparency",
        "description": "Model card, documentation, and decision explainability",
    },
    "privacy": {
        "label": "Privacy",
        "description": "Data handling, partner isolation, and GDPR compliance",
    },
    "reliability": {
        "label": "Reliability",
        "description": "Uptime SLAs, failure modes, and degradation testing",
    },
    "compliance": {
        "label": "Regulatory Compliance",
        "description": "SOC2, OSHA robot safety standards, FedRAMP readiness",
    },
}

DIMENSION_ORDER = [
    "data_provenance",
    "bias_testing",
    "safety_constraints",
    "transparency",
    "privacy",
    "reliability",
    "compliance",
]


def _status_from_score(pct: float) -> str:
    if pct >= 85:
        return "compliant"
    if pct >= 70:
        return "partial"
    return "non_compliant"


def _cert_level(score: float) -> str:
    if score >= 85:
        return "Gold"
    if score >= 70:
        return "Silver"
    return "Bronze"


def build_mock_report() -> GovernanceReport:
    today = date.today()
    review_date = (today + timedelta(days=180)).isoformat()

    dims = [
        GovernanceDimension(
            name="data_provenance",
            score=88,
            max_score=100,
            status=_status_from_score(88),
            findings=[
                "Training corpus sourced from Open-X Embodiment (CC BY 4.0) and Genesis simulator.",
                "OCI-generated synthetic demonstrations fully documented in data card.",
                "Third-party RoboSet subset (MIT license) — 4.2% of total training volume.",
            ],
            recommendations=[
                "Publish full dataset lineage graph to model card page.",
                "Automate license compatibility checks in CI pipeline.",
            ],
        ),
        GovernanceDimension(
            name="bias_testing",
            score=64,
            max_score=100,
            status=_status_from_score(64),
            findings=[
                "Success rate variance of 18 pp across lighting conditions (bright vs dim).",
                "Object color bias detected: dark-colored objects show 12% lower grasp success.",
                "Limited evaluation on non-standard table heights and surface textures.",
                "No systematic demographic bias testing for human-robot interaction scenarios.",
            ],
            recommendations=[
                "Expand domain randomization in Genesis SDG to cover 20+ lighting presets.",
                "Add dark-object oversampling in next fine-tune dataset collection cycle.",
                "Implement automated bias regression suite in evaluation harness.",
                "Define demographic bias test protocol for HRI scenarios by Q2 2026.",
            ],
        ),
        GovernanceDimension(
            name="safety_constraints",
            score=91,
            max_score=100,
            status=_status_from_score(91),
            findings=[
                "Joint velocity hard limits enforced at controller level (≤1.5 m/s EE).",
                "Force/torque threshold kill-switch triggers at 50 N — validated in bench tests.",
                "Workspace boundary enforcement implemented via real-time bounding-box check.",
                "Emergency stop latency measured at 12 ms (target: <20 ms).",
            ],
            recommendations=[
                "Add redundant software kill-switch path independent of primary inference loop.",
                "Publish safety test certificate to customer-facing documentation portal.",
            ],
        ),
        GovernanceDimension(
            name="transparency",
            score=87,
            max_score=100,
            status=_status_from_score(87),
            findings=[
                "Model card v1.2 published covering architecture, training data, and known limitations.",
                "GR00T N1.6 inference API returns confidence scores per action chunk.",
                "Changelog maintained for all fine-tuned checkpoint versions in model registry.",
                "Decision explainability limited to token-level attention maps (no task-level rationale).",
            ],
            recommendations=[
                "Develop task-level rationale module to accompany action outputs.",
                "Translate model card to customer-preferred formats (PDF, SharePoint).",
            ],
        ),
        GovernanceDimension(
            name="privacy",
            score=92,
            max_score=100,
            status=_status_from_score(92),
            findings=[
                "Partner fine-tune data stored in isolated OCI Object Storage namespaces.",
                "No cross-tenant data leakage detected in isolation penetration test (2025-12).",
                "GDPR Article 30 processing records maintained for EU partner deployments.",
                "Telemetry pipeline anonymizes robot serial numbers before logging.",
            ],
            recommendations=[
                "Implement automated GDPR right-to-erasure workflow for partner data deletion.",
                "Conduct annual privacy impact assessment for new telemetry data types.",
            ],
        ),
        GovernanceDimension(
            name="reliability",
            score=83,
            max_score=100,
            status=_status_from_score(83),
            findings=[
                "Inference API p99 latency: 231 ms (SLA: <500 ms) — compliant.",
                "Measured 99.7% uptime over trailing 90 days (SLA: 99.5%) — compliant.",
                "Graceful degradation to rule-based fallback confirmed in 3/5 failure scenarios.",
                "Cold-start latency spike (8–12 s) on first request after GPU idle period.",
            ],
            recommendations=[
                "Implement warm-pool inference workers to eliminate cold-start spike.",
                "Complete remaining 2 failure-mode degradation test cases.",
                "Add SLA breach alerting with 15-minute PagerDuty escalation path.",
            ],
        ),
        GovernanceDimension(
            name="compliance",
            score=78,
            max_score=100,
            status=_status_from_score(78),
            findings=[
                "SOC 2 Type II audit in progress — expected completion Q2 2026.",
                "OSHA 1910.217 machine guarding review completed for pilot deployments.",
                "FedRAMP Moderate baseline gap assessment identifies 14 open controls.",
                "ISO/IEC 42001 AI management system readiness: 62% of controls addressed.",
            ],
            recommendations=[
                "Prioritize closure of 14 FedRAMP open controls to unblock federal pipeline.",
                "Engage third-party auditor for ISO 42001 gap remediation road map.",
                "Schedule OSHA compliance review for new customer deployment sites.",
            ],
        ),
    ]

    # Overall score = weighted average (bias gets 0.8 weight due to maturity gap)
    weights = {
        "data_provenance": 1.0,
        "bias_testing": 0.8,
        "safety_constraints": 1.2,
        "transparency": 1.0,
        "privacy": 1.0,
        "reliability": 1.0,
        "compliance": 1.0,
    }
    total_w = sum(weights.values())
    dim_map = {d.name: d for d in dims}
    weighted_sum = sum(dim_map[k].pct * w for k, w in weights.items())
    overall = round(weighted_sum / total_w, 1)

    # Partner results
    partners = [
        PartnerGovernance(
            partner_name="Kawasaki Robotics",
            tier="Tier 1",
            overall_score=84.2,
            compliant_dims=5,
            total_dims=7,
            certification_level=_cert_level(84.2),
            next_review_date=(today + timedelta(days=90)).isoformat(),
        ),
        PartnerGovernance(
            partner_name="Teradyne / Universal Robots",
            tier="Tier 1",
            overall_score=79.6,
            compliant_dims=4,
            total_dims=7,
            certification_level=_cert_level(79.6),
            next_review_date=(today + timedelta(days=120)).isoformat(),
        ),
        PartnerGovernance(
            partner_name="Seegrid Fleet AI",
            tier="Tier 2",
            overall_score=71.3,
            compliant_dims=4,
            total_dims=7,
            certification_level=_cert_level(71.3),
            next_review_date=review_date,
        ),
    ]

    return GovernanceReport(
        overall_score=overall,
        certification_level=_cert_level(overall),
        dims=dims,
        partner_results=partners,
    )


# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------

def _radar_svg(dims: List[GovernanceDimension], width: int = 420, height: int = 420) -> str:
    cx, cy, r = width / 2, height / 2, min(width, height) / 2 - 60
    n = len(dims)
    labels = [DIMENSION_META[d.name]["label"] for d in dims]
    scores = [d.pct / 100.0 for d in dims]

    def pt(i: int, frac: float):
        angle = math.pi / 2 - 2 * math.pi * i / n
        return cx + frac * r * math.cos(angle), cy - frac * r * math.sin(angle)

    # Grid rings
    rings = ""
    for level in [0.25, 0.5, 0.75, 1.0]:
        pts = " ".join(f"{pt(i, level)[0]:.1f},{pt(i, level)[1]:.1f}" for i in range(n))
        rings += f'<polygon points="{pts}" fill="none" stroke="#334155" stroke-width="1"/>\n'

    # Axis lines
    axes = ""
    for i in range(n):
        x2, y2 = pt(i, 1.0)
        axes += f'<line x1="{cx:.1f}" y1="{cy:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#334155" stroke-width="1"/>\n'

    # Score polygon
    poly_pts = " ".join(f"{pt(i, scores[i])[0]:.1f},{pt(i, scores[i])[1]:.1f}" for i in range(n))
    poly = (
        f'<polygon points="{poly_pts}" fill="#C74634" fill-opacity="0.25" '
        f'stroke="#C74634" stroke-width="2"/>\n'
    )

    # Dots
    dots = ""
    for i, s in enumerate(scores):
        x, y = pt(i, s)
        dots += f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="#C74634"/>\n'

    # Labels
    label_els = ""
    for i, lbl in enumerate(labels):
        lx, ly = pt(i, 1.18)
        anchor = "middle"
        if lx < cx - 10:
            anchor = "end"
        elif lx > cx + 10:
            anchor = "start"
        score_pct = f"{dims[i].pct:.0f}%"
        label_els += (
            f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="{anchor}" '
            f'font-size="11" fill="#94a3b8">{lbl}</text>\n'
            f'<text x="{lx:.1f}" y="{ly + 14:.1f}" text-anchor="{anchor}" '
            f'font-size="10" fill="#C74634" font-weight="bold">{score_pct}</text>\n'
        )

    return (
        f'<svg viewBox="0 0 {width} {height}" width="{width}" height="{height}" '
        f'xmlns="http://www.w3.org/2000/svg">\n'
        f'{rings}{axes}{poly}{dots}{label_els}'
        f'</svg>'
    )


def _partner_bar_svg(partners: List[PartnerGovernance], width: int = 560, height: int = 220) -> str:
    margin_left, margin_right = 170, 30
    margin_top, margin_bottom = 20, 40
    bar_area_w = width - margin_left - margin_right
    bar_area_h = height - margin_top - margin_bottom
    n = len(partners)
    bar_h = min(36, (bar_area_h - (n - 1) * 12) // n)
    gap = (bar_area_h - n * bar_h) // (n + 1)

    cert_colors = {"Gold": "#f59e0b", "Silver": "#94a3b8", "Bronze": "#b45309"}

    bars = ""
    for i, p in enumerate(partners):
        y = margin_top + gap * (i + 1) + bar_h * i
        bar_w = bar_area_w * p.overall_score / 100
        color = cert_colors.get(p.certification_level, "#C74634")

        bars += (
            f'<text x="{margin_left - 8}" y="{y + bar_h / 2 + 4:.1f}" '
            f'text-anchor="end" font-size="12" fill="#94a3b8">{p.partner_name}</text>\n'
            f'<rect x="{margin_left}" y="{y}" width="{bar_w:.1f}" height="{bar_h}" '
            f'rx="3" fill="{color}" fill-opacity="0.85"/>\n'
            f'<text x="{margin_left + bar_w + 6:.1f}" y="{y + bar_h / 2 + 4:.1f}" '
            f'font-size="12" fill="#e2e8f0" font-weight="bold">{p.overall_score:.1f}%</text>\n'
            f'<text x="{margin_left + bar_w + 52:.1f}" y="{y + bar_h / 2 + 4:.1f}" '
            f'font-size="11" fill="{color}">{p.certification_level}</text>\n'
        )

    # x-axis ticks
    ticks = ""
    for v in [0, 25, 50, 70, 85, 100]:
        x = margin_left + bar_area_w * v / 100
        ticks += (
            f'<line x1="{x:.1f}" y1="{margin_top}" x2="{x:.1f}" '
            f'y2="{height - margin_bottom}" stroke="#334155" stroke-width="1" stroke-dasharray="3,3"/>\n'
            f'<text x="{x:.1f}" y="{height - margin_bottom + 14}" text-anchor="middle" '
            f'font-size="10" fill="#64748b">{v}%</text>\n'
        )

    return (
        f'<svg viewBox="0 0 {width} {height}" width="{width}" height="{height}" '
        f'xmlns="http://www.w3.org/2000/svg">\n'
        f'{ticks}{bars}'
        f'</svg>'
    )


# ---------------------------------------------------------------------------
# HTML report
# ---------------------------------------------------------------------------

STATUS_BADGE = {
    "compliant": ('<span style="background:#16a34a;color:#fff;padding:2px 10px;'
                  'border-radius:12px;font-size:12px;font-weight:600">Compliant</span>'),
    "partial": ('<span style="background:#d97706;color:#fff;padding:2px 10px;'
                'border-radius:12px;font-size:12px;font-weight:600">Partial</span>'),
    "non_compliant": ('<span style="background:#dc2626;color:#fff;padding:2px 10px;'
                      'border-radius:12px;font-size:12px;font-weight:600">Non-Compliant</span>'),
}

CERT_COLORS = {"Gold": "#f59e0b", "Silver": "#94a3b8", "Bronze": "#b45309"}


def _cert_badge(level: str) -> str:
    color = CERT_COLORS.get(level, "#64748b")
    medal = {"Gold": "★", "Silver": "✦", "Bronze": "●"}.get(level, "")
    return (
        f'<span style="background:{color};color:#1e293b;padding:4px 16px;'
        f'border-radius:20px;font-size:14px;font-weight:700">{medal} {level}</span>'
    )


def generate_html(report: GovernanceReport) -> str:
    today_str = date.today().isoformat()

    # Stat cards
    lowest = report.lowest_dim
    cards_html = ""
    card_data = [
        ("Overall Score", f"{report.overall_score:.1f}%", "#C74634"),
        ("Certification", _cert_badge(report.certification_level), CERT_COLORS.get(report.certification_level, "#64748b")),
        ("Compliant Dims", f"{report.compliant_count} / {len(report.dims)}", "#16a34a"),
        ("Lowest Dim", f"{DIMENSION_META[lowest.name]['label']} ({lowest.pct:.0f}%)", "#d97706"),
    ]
    for title, value, color in card_data:
        cards_html += f"""
        <div style="background:#0f172a;border:1px solid #1e3a5f;border-left:4px solid {color};
                    border-radius:8px;padding:20px 24px;min-width:180px;flex:1">
          <div style="color:#64748b;font-size:12px;text-transform:uppercase;letter-spacing:1px;margin-bottom:8px">{title}</div>
          <div style="font-size:22px;font-weight:700;color:#e2e8f0">{value}</div>
        </div>"""

    # Dimension table rows
    table_rows = ""
    for d in report.dims:
        meta = DIMENSION_META[d.name]
        badge = STATUS_BADGE.get(d.status, "")
        finding = d.findings[0] if d.findings else "—"
        rec = d.recommendations[0] if d.recommendations else "—"
        bar_w = int(d.pct)
        bar_color = "#16a34a" if d.pct >= 85 else ("#d97706" if d.pct >= 70 else "#dc2626")
        table_rows += f"""
        <tr style="border-bottom:1px solid #1e293b">
          <td style="padding:14px 12px">
            <div style="font-weight:600;color:#e2e8f0">{meta['label']}</div>
            <div style="font-size:11px;color:#64748b;margin-top:2px">{meta['description']}</div>
          </td>
          <td style="padding:14px 12px;white-space:nowrap">
            <div style="display:flex;align-items:center;gap:8px">
              <div style="background:#1e293b;border-radius:4px;width:80px;height:8px;overflow:hidden">
                <div style="background:{bar_color};width:{bar_w}%;height:100%"></div>
              </div>
              <span style="color:#e2e8f0;font-weight:600">{d.pct:.0f}%</span>
            </div>
          </td>
          <td style="padding:14px 12px">{badge}</td>
          <td style="padding:14px 12px;font-size:13px;color:#94a3b8;max-width:260px">{finding}</td>
          <td style="padding:14px 12px;font-size:13px;color:#7dd3fc;max-width:240px">{rec}</td>
        </tr>"""

    # Gap analysis for Gold
    gap_dims = [d for d in report.dims if d.pct < 85]
    gap_html = ""
    if gap_dims:
        gap_html = """
        <div style="background:#0f172a;border:1px solid #1e3a5f;border-radius:12px;padding:24px;margin-bottom:32px">
          <h2 style="color:#C74634;margin:0 0 16px 0;font-size:18px">Gap Analysis — Path to Gold Certification</h2>
          <p style="color:#94a3b8;font-size:14px;margin:0 0 16px 0">
            Gold certification requires all dimensions to score &ge;85%. The following dimensions need improvement:
          </p>
          <table style="width:100%;border-collapse:collapse">
            <thead>
              <tr style="border-bottom:2px solid #1e3a5f">
                <th style="text-align:left;padding:8px 12px;color:#64748b;font-size:12px;text-transform:uppercase">Dimension</th>
                <th style="text-align:left;padding:8px 12px;color:#64748b;font-size:12px;text-transform:uppercase">Current</th>
                <th style="text-align:left;padding:8px 12px;color:#64748b;font-size:12px;text-transform:uppercase">Gap to Gold</th>
                <th style="text-align:left;padding:8px 12px;color:#64748b;font-size:12px;text-transform:uppercase">Priority Actions</th>
              </tr>
            </thead>
            <tbody>"""
        for d in sorted(gap_dims, key=lambda x: x.pct):
            gap = 85 - d.pct
            recs = "; ".join(d.recommendations[:2])
            gap_html += f"""
              <tr style="border-bottom:1px solid #1e293b">
                <td style="padding:10px 12px;color:#e2e8f0;font-weight:600">{DIMENSION_META[d.name]['label']}</td>
                <td style="padding:10px 12px;color:#d97706">{d.pct:.0f}%</td>
                <td style="padding:10px 12px;color:#dc2626">+{gap:.0f} pp needed</td>
                <td style="padding:10px 12px;color:#94a3b8;font-size:13px">{recs}</td>
              </tr>"""
        gap_html += """
            </tbody>
          </table>
        </div>"""

    # Partner findings detail
    partner_detail = ""
    cert_colors_css = CERT_COLORS
    for p in report.partner_results:
        c = cert_colors_css.get(p.certification_level, "#64748b")
        partner_detail += f"""
        <tr style="border-bottom:1px solid #1e293b">
          <td style="padding:12px 14px;color:#e2e8f0;font-weight:600">{p.partner_name}</td>
          <td style="padding:12px 14px;color:#94a3b8">{p.tier}</td>
          <td style="padding:12px 14px;color:#e2e8f0;font-weight:700">{p.overall_score:.1f}%</td>
          <td style="padding:12px 14px">{_cert_badge(p.certification_level)}</td>
          <td style="padding:12px 14px;color:#94a3b8">{p.compliant_dims} / {p.total_dims}</td>
          <td style="padding:12px 14px;color:#64748b;font-size:13px">{p.next_review_date}</td>
        </tr>"""

    radar_svg = _radar_svg(report.dims)
    bar_svg = _partner_bar_svg(report.partner_results)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Model Governance Report — OCI Robot Cloud</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #1e293b; color: #e2e8f0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; padding: 40px 24px; }}
    h1 {{ font-size: 26px; font-weight: 700; }}
    h2 {{ font-size: 18px; font-weight: 600; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th {{ font-size: 12px; text-transform: uppercase; color: #64748b; padding: 10px 12px; text-align: left; border-bottom: 2px solid #1e3a5f; }}
    a {{ color: #7dd3fc; text-decoration: none; }}
  </style>
</head>
<body>
  <div style="max-width:1100px;margin:0 auto">

    <!-- Header -->
    <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:32px">
      <div>
        <div style="color:#C74634;font-size:13px;text-transform:uppercase;letter-spacing:2px;margin-bottom:6px">
          Oracle Cloud Infrastructure — Robot Cloud
        </div>
        <h1 style="color:#e2e8f0;margin-bottom:6px">Model Governance &amp; Responsible AI Report</h1>
        <div style="color:#64748b;font-size:14px">GR00T N1.6 Enterprise Deployment &nbsp;|&nbsp; Generated: {today_str}</div>
      </div>
      <div style="text-align:right">
        {_cert_badge(report.certification_level)}
        <div style="color:#64748b;font-size:12px;margin-top:6px">Current Certification Level</div>
      </div>
    </div>

    <!-- Stat Cards -->
    <div style="display:flex;gap:16px;flex-wrap:wrap;margin-bottom:32px">
      {cards_html}
    </div>

    <!-- Charts row -->
    <div style="display:flex;gap:24px;flex-wrap:wrap;margin-bottom:32px">
      <div style="background:#0f172a;border:1px solid #1e3a5f;border-radius:12px;padding:24px;flex:0 0 auto">
        <h2 style="color:#e2e8f0;margin-bottom:16px">Governance Radar — Overall System</h2>
        {radar_svg}
      </div>
      <div style="background:#0f172a;border:1px solid #1e3a5f;border-radius:12px;padding:24px;flex:1;min-width:300px">
        <h2 style="color:#e2e8f0;margin-bottom:16px">Partner Governance Scores</h2>
        {bar_svg}
        <div style="margin-top:12px;display:flex;gap:16px;flex-wrap:wrap">
          <span style="font-size:12px;color:#f59e0b">★ Gold (&gt;85%)</span>
          <span style="font-size:12px;color:#94a3b8">✦ Silver (70–85%)</span>
          <span style="font-size:12px;color:#b45309">● Bronze (&lt;70%)</span>
        </div>
      </div>
    </div>

    <!-- Gap Analysis -->
    {gap_html}

    <!-- Dimension Detail Table -->
    <div style="background:#0f172a;border:1px solid #1e3a5f;border-radius:12px;padding:24px;margin-bottom:32px">
      <h2 style="color:#e2e8f0;margin-bottom:16px">Governance Dimension Detail</h2>
      <table>
        <thead>
          <tr>
            <th>Dimension</th>
            <th>Score</th>
            <th>Status</th>
            <th>Key Finding</th>
            <th>Top Recommendation</th>
          </tr>
        </thead>
        <tbody>{table_rows}</tbody>
      </table>
    </div>

    <!-- Partner Governance Table -->
    <div style="background:#0f172a;border:1px solid #1e3a5f;border-radius:12px;padding:24px;margin-bottom:32px">
      <h2 style="color:#e2e8f0;margin-bottom:16px">Enterprise Partner Governance Summary</h2>
      <table>
        <thead>
          <tr>
            <th>Partner</th>
            <th>Tier</th>
            <th>Overall Score</th>
            <th>Certification</th>
            <th>Compliant Dims</th>
            <th>Next Review</th>
          </tr>
        </thead>
        <tbody>{partner_detail}</tbody>
      </table>
    </div>

    <!-- Footer -->
    <div style="border-top:1px solid #1e3a5f;padding-top:20px;color:#475569;font-size:12px;text-align:center">
      OCI Robot Cloud — Model Governance Report &nbsp;|&nbsp; Generated {today_str}
      &nbsp;|&nbsp; Oracle Confidential
    </div>

  </div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------

def print_summary(report: GovernanceReport) -> None:
    sep = "-" * 60
    print(sep)
    print("  OCI Robot Cloud — Model Governance Report")
    print(sep)
    print(f"  Overall Score     : {report.overall_score:.1f}%")
    print(f"  Certification     : {report.certification_level}")
    print(f"  Compliant Dims    : {report.compliant_count} / {len(report.dims)}")
    print(sep)
    print(f"  {'Dimension':<28} {'Score':>6}  {'Status'}")
    print(f"  {'-'*28} {'-'*6}  {'-'*14}")
    for d in report.dims:
        label = DIMENSION_META[d.name]["label"]
        print(f"  {label:<28} {d.pct:>5.0f}%  {d.status}")
    print(sep)
    print("  Partner Governance:")
    for p in report.partner_results:
        print(f"    {p.partner_name:<35} {p.overall_score:.1f}%  [{p.certification_level}]")
    print(sep)
    gap_dims = [d for d in report.dims if d.pct < 85]
    if gap_dims:
        print("  Gap to Gold Certification:")
        for d in sorted(gap_dims, key=lambda x: x.pct):
            label = DIMENSION_META[d.name]["label"]
            print(f"    {label:<28} needs +{85 - d.pct:.0f} pp")
    else:
        print("  All dimensions meet Gold threshold (>=85%).")
    print(sep)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate GR00T model governance and responsible AI report."
    )
    parser.add_argument("--mock", action="store_true", help="Use mock/demo data")
    parser.add_argument(
        "--output",
        default="/tmp/model_governance_report.html",
        help="Output HTML file path (default: /tmp/model_governance_report.html)",
    )
    args = parser.parse_args()

    if args.mock:
        report = build_mock_report()
    else:
        print("Note: Only --mock mode is currently supported. Using mock data.")
        report = build_mock_report()

    print_summary(report)

    html = generate_html(report)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\n  Report written to: {args.output}")


if __name__ == "__main__":
    main()
