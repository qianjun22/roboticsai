#!/usr/bin/env python3
"""
partner_qbr_generator.py — Quarterly Business Review (QBR) report generator
for OCI Robot Cloud design partners.

Usage:
    python partner_qbr_generator.py [--mock] [--quarter Q1-2026]
                                    [--output /tmp/partner_qbr.html]
                                    [--seed 42]
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import List, Optional


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class MonthlyMetrics:
    month: str                      # e.g. "Jan 2026"
    api_calls: int
    compute_hours: float
    jobs_completed: int
    job_success_rate: float         # 0.0 – 1.0
    mae_improvement: float          # fractional improvement vs baseline (0.0 = none)
    data_demos_uploaded: int
    model_versions_finetuned: int
    billing_usd: float
    overage_instances: int
    support_tickets: int


@dataclass
class PartnerMetrics:
    name: str
    tier: str                       # pilot / growth / enterprise
    months: List[MonthlyMetrics] = field(default_factory=list)
    nps_score: float = 0.0          # 0 – 10
    health_status: str = "green"    # green / yellow / red
    most_used_feature: str = ""
    recommendation: str = ""
    recommendation_priority: str = "medium"  # low / medium / high

    # Computed fields (populated after simulation)
    mom_growth_api: float = 0.0     # MoM growth in API calls (last two months)
    mom_growth_compute: float = 0.0


@dataclass
class QuarterSummary:
    quarter: str
    total_compute_hours: float
    total_revenue_usd: float
    avg_nps: float
    partner_health: dict            # {"green": n, "yellow": n, "red": n}
    partner_count: int


# ---------------------------------------------------------------------------
# Simulation helpers
# ---------------------------------------------------------------------------

PARTNER_PROFILES = [
    {
        "name": "Apptronik",
        "tier": "enterprise",
        "base_api": 12_000,
        "base_compute": 480,
        "base_jobs": 900,
        "success_rate": 0.82,
        "mae_improvement": 0.31,
        "nps_base": 8.5,
        "feature": "Multi-task Curriculum SDG",
    },
    {
        "name": "Figure AI",
        "tier": "enterprise",
        "base_api": 18_500,
        "base_compute": 720,
        "base_jobs": 1_400,
        "success_rate": 0.79,
        "mae_improvement": 0.27,
        "nps_base": 7.8,
        "feature": "GR00T N1.6 Fine-tuning",
    },
    {
        "name": "Physical Intelligence",
        "tier": "growth",
        "base_api": 7_200,
        "base_compute": 280,
        "base_jobs": 540,
        "success_rate": 0.88,
        "mae_improvement": 0.41,
        "nps_base": 9.1,
        "feature": "Isaac Sim Domain Randomization",
    },
    {
        "name": "Agility Robotics",
        "tier": "growth",
        "base_api": 5_800,
        "base_compute": 210,
        "base_jobs": 420,
        "success_rate": 0.74,
        "mae_improvement": 0.19,
        "nps_base": 6.4,
        "feature": "DAgger Policy Refinement",
    },
    {
        "name": "Skild AI",
        "tier": "pilot",
        "base_api": 2_400,
        "base_compute": 95,
        "base_jobs": 180,
        "success_rate": 0.68,
        "mae_improvement": 0.12,
        "nps_base": 5.8,
        "feature": "Closed-Loop Evaluation",
    },
]

MONTH_LABELS = ["Jan 2026", "Feb 2026", "Mar 2026"]

BILLING_RATE_PER_COMPUTE_HOUR = 2.85   # USD


def _noisy(rng: random.Random, base: float, noise: float = 0.08) -> float:
    """Return base +/- noise fraction."""
    return base * (1.0 + rng.uniform(-noise, noise))


def simulate_partner(profile: dict, rng: random.Random, quarter: str) -> PartnerMetrics:
    """Generate three months of metrics for one partner."""
    months: List[MonthlyMetrics] = []
    growth_factor = 1.0

    for label in MONTH_LABELS:
        api_calls = int(_noisy(rng, profile["base_api"] * growth_factor, 0.10))
        compute_hours = round(_noisy(rng, profile["base_compute"] * growth_factor, 0.09), 1)
        jobs_completed = int(_noisy(rng, profile["base_jobs"] * growth_factor, 0.10))
        success_rate = min(0.99, max(0.40, _noisy(rng, profile["success_rate"], 0.05)))
        mae_improvement = max(0.0, _noisy(rng, profile["mae_improvement"], 0.12))
        data_demos = int(_noisy(rng, compute_hours * 2.1, 0.15))
        model_versions = rng.randint(1, 4)
        billing = round(compute_hours * BILLING_RATE_PER_COMPUTE_HOUR
                        + rng.uniform(0, compute_hours * 0.15), 2)
        overage = rng.randint(0, 3) if profile["tier"] != "enterprise" else rng.randint(0, 1)
        tickets = rng.randint(0, 5)

        months.append(MonthlyMetrics(
            month=label,
            api_calls=api_calls,
            compute_hours=compute_hours,
            jobs_completed=jobs_completed,
            job_success_rate=round(success_rate, 4),
            mae_improvement=round(mae_improvement, 4),
            data_demos_uploaded=data_demos,
            model_versions_finetuned=model_versions,
            billing_usd=billing,
            overage_instances=overage,
            support_tickets=tickets,
        ))
        growth_factor *= rng.uniform(1.03, 1.12)

    nps = round(min(10.0, max(0.0, _noisy(rng, profile["nps_base"], 0.06))), 2)
    health = "green" if nps >= 8.0 else ("yellow" if nps >= 6.0 else "red")

    # MoM growth rates
    mom_api = (months[-1].api_calls - months[-2].api_calls) / max(months[-2].api_calls, 1)
    mom_compute = (months[-1].compute_hours - months[-2].compute_hours) / max(months[-2].compute_hours, 0.01)

    partner = PartnerMetrics(
        name=profile["name"],
        tier=profile["tier"],
        months=months,
        nps_score=nps,
        health_status=health,
        most_used_feature=profile["feature"],
        mom_growth_api=round(mom_api, 4),
        mom_growth_compute=round(mom_compute, 4),
    )
    partner.recommendation, partner.recommendation_priority = _generate_recommendation(partner)
    return partner


def simulate_all_partners(seed: int, quarter: str) -> List[PartnerMetrics]:
    rng = random.Random(seed)
    return [simulate_partner(p, rng, quarter) for p in PARTNER_PROFILES]


def compute_quarter_summary(partners: List[PartnerMetrics], quarter: str) -> QuarterSummary:
    total_compute = sum(m.compute_hours for p in partners for m in p.months)
    total_revenue = sum(m.billing_usd for p in partners for m in p.months)
    avg_nps = sum(p.nps_score for p in partners) / len(partners)
    health_dist: dict = {"green": 0, "yellow": 0, "red": 0}
    for p in partners:
        health_dist[p.health_status] += 1
    return QuarterSummary(
        quarter=quarter,
        total_compute_hours=round(total_compute, 1),
        total_revenue_usd=round(total_revenue, 2),
        avg_nps=round(avg_nps, 2),
        partner_health=health_dist,
        partner_count=len(partners),
    )


# ---------------------------------------------------------------------------
# Recommendation engine
# ---------------------------------------------------------------------------

def _generate_recommendation(partner: PartnerMetrics) -> tuple[str, str]:
    last = partner.months[-1]

    if partner.health_status == "red":
        return ("NPS critically low — schedule executive check-in and offer dedicated CSM support.", "high")
    if last.support_tickets >= 4:
        return ("Elevated support volume — audit recurring issues and offer proactive office hours.", "high")
    if last.overage_instances >= 3:
        return ("Frequent overages detected — consider GPU reservation plan for predictable workloads.", "medium")
    if last.job_success_rate >= 0.87:
        return ("High success rate — strong candidate for public case study or co-marketing.", "medium")
    if last.mae_improvement >= 0.35:
        return ("Exceptional MAE improvement — highlight in GTC/AI World technical talks.", "medium")
    if partner.mom_growth_api > 0.10:
        return ("Rapid API growth — proactively discuss tier upgrade and dedicated infra.", "medium")
    if partner.tier == "pilot" and last.jobs_completed > 150:
        return ("Pilot engagement exceeds targets — initiate growth tier conversion conversation.", "high")
    if last.data_demos_uploaded < 100:
        return ("Low data upload volume — run demo data onboarding workshop to accelerate fine-tuning.", "low")
    return ("Usage trending positively — maintain quarterly cadence and share roadmap preview.", "low")


# ---------------------------------------------------------------------------
# Console output
# ---------------------------------------------------------------------------

def print_summary_table(partners: List[PartnerMetrics], summary: QuarterSummary) -> None:
    BOLD = "\033[1m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    RED = "\033[31m"
    RESET = "\033[0m"

    colour = {"green": GREEN, "yellow": YELLOW, "red": RED}

    print(f"\n{BOLD}{'=' * 80}{RESET}")
    print(f"{BOLD}  OCI Robot Cloud — {summary.quarter} Quarterly Business Review{RESET}")
    print(f"{'=' * 80}")
    print(f"  Partners: {summary.partner_count}  |  "
          f"Total Compute: {summary.total_compute_hours:,.1f} hrs  |  "
          f"Revenue: ${summary.total_revenue_usd:,.2f}  |  "
          f"Avg NPS: {summary.avg_nps:.1f}/10")
    print(f"  Health: "
          f"{GREEN}Green {summary.partner_health['green']}{RESET}  "
          f"{YELLOW}Yellow {summary.partner_health['yellow']}{RESET}  "
          f"{RED}Red {summary.partner_health['red']}{RESET}")
    print(f"{'=' * 80}\n")

    header = f"{'Partner':<26} {'Tier':<12} {'NPS':>5} {'Health':>7} "
    header += f"{'Compute(hrs)':>13} {'Revenue':>10} {'Success%':>9} {'MoM API':>8}"
    print(BOLD + header + RESET)
    print("-" * 90)

    for p in partners:
        last = p.months[-1]
        total_compute = sum(m.compute_hours for m in p.months)
        total_billing = sum(m.billing_usd for m in p.months)
        c = colour.get(p.health_status, RESET)
        arrow = "▲" if p.mom_growth_api >= 0 else "▼"
        row = (f"{p.name:<26} {p.tier:<12} {p.nps_score:>5.1f} "
               f"{c}{p.health_status.upper():>7}{RESET} "
               f"{total_compute:>13,.1f} ${total_billing:>9,.2f} "
               f"{last.job_success_rate * 100:>8.1f}% "
               f"{arrow}{abs(p.mom_growth_api) * 100:>6.1f}%")
        print(row)

    print(f"\n{'=' * 80}\n")

    print(f"{BOLD}Recommendations:{RESET}")
    print(f"{'Partner':<26} {'Priority':>8}  Recommendation")
    print("-" * 90)
    for p in partners:
        pri_colour = RED if p.recommendation_priority == "high" else (
            YELLOW if p.recommendation_priority == "medium" else GREEN)
        print(f"{p.name:<26} {pri_colour}{p.recommendation_priority.upper():>8}{RESET}  {p.recommendation}")
    print()


# ---------------------------------------------------------------------------
# SVG chart helpers
# ---------------------------------------------------------------------------

def _svg_bar_chart(partners: List[PartnerMetrics], width: int = 700, height: int = 240) -> str:
    """SVG bar chart: total compute hours per partner."""
    values = [sum(m.compute_hours for m in p.months) for p in partners]
    max_val = max(values) if values else 1
    bar_colours = ["#C74634", "#3b82f6", "#10b981", "#f59e0b", "#8b5cf6"]
    n = len(partners)
    padding = {"left": 60, "right": 20, "top": 20, "bottom": 60}
    chart_w = width - padding["left"] - padding["right"]
    chart_h = height - padding["top"] - padding["bottom"]
    bar_w = int(chart_w / (n * 1.8))
    gap = int(chart_w / n)

    paths: List[str] = []

    # Y-axis grid lines and labels
    for i in range(5):
        y_val = max_val * (i / 4)
        y_px = padding["top"] + chart_h - int(chart_h * i / 4)
        paths.append(
            f'<line x1="{padding["left"]}" y1="{y_px}" '
            f'x2="{width - padding["right"]}" y2="{y_px}" '
            f'stroke="#334155" stroke-width="1"/>'
        )
        paths.append(
            f'<text x="{padding["left"] - 6}" y="{y_px + 4}" '
            f'text-anchor="end" font-size="10" fill="#94a3b8">{int(y_val)}</text>'
        )

    for idx, (partner, val, colour) in enumerate(zip(partners, values, bar_colours)):
        x = padding["left"] + idx * gap + (gap - bar_w) // 2
        bar_h = int(chart_h * val / max_val)
        y = padding["top"] + chart_h - bar_h
        paths.append(
            f'<rect x="{x}" y="{y}" width="{bar_w}" height="{bar_h}" '
            f'fill="{colour}" rx="3"/>'
        )
        paths.append(
            f'<text x="{x + bar_w // 2}" y="{y - 5}" text-anchor="middle" '
            f'font-size="10" fill="#e2e8f0">{val:,.0f}</text>'
        )
        label = partner.name.split()[0]
        paths.append(
            f'<text x="{x + bar_w // 2}" y="{height - padding["bottom"] + 18}" '
            f'text-anchor="middle" font-size="10" fill="#94a3b8">{label}</text>'
        )

    # Axes
    paths.append(
        f'<line x1="{padding["left"]}" y1="{padding["top"]}" '
        f'x2="{padding["left"]}" y2="{padding["top"] + chart_h}" '
        f'stroke="#475569" stroke-width="1.5"/>'
    )
    paths.append(
        f'<line x1="{padding["left"]}" y1="{padding["top"] + chart_h}" '
        f'x2="{width - padding["right"]}" y2="{padding["top"] + chart_h}" '
        f'stroke="#475569" stroke-width="1.5"/>'
    )
    paths.append(
        f'<text x="{width // 2}" y="{height - 4}" text-anchor="middle" '
        f'font-size="11" fill="#94a3b8">Compute Hours (Q total)</text>'
    )

    inner = "\n    ".join(paths)
    return (
        f'<svg width="{width}" height="{height}" '
        f'xmlns="http://www.w3.org/2000/svg" '
        f'style="background:#0f172a;border-radius:8px;">\n    {inner}\n</svg>'
    )


def _svg_line_chart(partners: List[PartnerMetrics], width: int = 700, height: int = 240) -> str:
    """SVG line chart: success rate over 3 months per partner."""
    line_colours = ["#C74634", "#3b82f6", "#10b981", "#f59e0b", "#8b5cf6"]
    padding = {"left": 55, "right": 130, "top": 20, "bottom": 55}
    chart_w = width - padding["left"] - padding["right"]
    chart_h = height - padding["top"] - padding["bottom"]
    month_count = len(MONTH_LABELS)
    x_step = chart_w / (month_count - 1) if month_count > 1 else chart_w

    y_min, y_max = 0.50, 1.00

    def to_px(val: float, idx: int):
        x = padding["left"] + idx * x_step
        y = padding["top"] + chart_h - (val - y_min) / (y_max - y_min) * chart_h
        return x, y

    paths: List[str] = []

    # Grid lines
    for i in range(6):
        val = y_min + (y_max - y_min) * i / 5
        _, y_px = to_px(val, 0)
        paths.append(
            f'<line x1="{padding["left"]}" y1="{y_px:.1f}" '
            f'x2="{width - padding["right"]}" y2="{y_px:.1f}" '
            f'stroke="#334155" stroke-width="1"/>'
        )
        paths.append(
            f'<text x="{padding["left"] - 6}" y="{y_px + 4:.1f}" '
            f'text-anchor="end" font-size="10" fill="#94a3b8">{int(val * 100)}%</text>'
        )

    # X-axis labels
    for idx, label in enumerate(MONTH_LABELS):
        x_px, _ = to_px(y_min, idx)
        paths.append(
            f'<text x="{x_px:.1f}" y="{padding["top"] + chart_h + 18}" '
            f'text-anchor="middle" font-size="10" fill="#94a3b8">{label}</text>'
        )

    # Lines + dots
    for partner, colour in zip(partners, line_colours):
        rates = [m.job_success_rate for m in partner.months]
        points = [to_px(r, i) for i, r in enumerate(rates)]
        polyline = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
        paths.append(
            f'<polyline points="{polyline}" fill="none" stroke="{colour}" '
            f'stroke-width="2.5" stroke-linejoin="round"/>'
        )
        for x_px, y_px in points:
            paths.append(
                f'<circle cx="{x_px:.1f}" cy="{y_px:.1f}" r="4" '
                f'fill="{colour}" stroke="#1e293b" stroke-width="1.5"/>'
            )
        # Legend on right
        leg_y = padding["top"] + 20 + list(zip(partners, line_colours)).index((partner, colour)) * 20
        leg_x = width - padding["right"] + 10
        paths.append(
            f'<rect x="{leg_x}" y="{leg_y - 8}" width="12" height="12" '
            f'fill="{colour}" rx="2"/>'
        )
        short = partner.name.split()[0]
        paths.append(
            f'<text x="{leg_x + 16}" y="{leg_y + 2}" font-size="10" fill="#e2e8f0">{short}</text>'
        )

    # Axes
    paths.append(
        f'<line x1="{padding["left"]}" y1="{padding["top"]}" '
        f'x2="{padding["left"]}" y2="{padding["top"] + chart_h}" '
        f'stroke="#475569" stroke-width="1.5"/>'
    )
    paths.append(
        f'<line x1="{padding["left"]}" y1="{padding["top"] + chart_h}" '
        f'x2="{width - padding["right"]}" y2="{padding["top"] + chart_h}" '
        f'stroke="#475569" stroke-width="1.5"/>'
    )
    paths.append(
        f'<text x="{padding["left"] + chart_w // 2}" y="{height - 4}" '
        f'text-anchor="middle" font-size="11" fill="#94a3b8">Job Success Rate Trend</text>'
    )

    inner = "\n    ".join(paths)
    return (
        f'<svg width="{width}" height="{height}" '
        f'xmlns="http://www.w3.org/2000/svg" '
        f'style="background:#0f172a;border-radius:8px;">\n    {inner}\n</svg>'
    )


# ---------------------------------------------------------------------------
# HTML renderer
# ---------------------------------------------------------------------------

_HEALTH_COLOUR = {
    "green": "#22c55e",
    "yellow": "#f59e0b",
    "red": "#ef4444",
}

_TIER_BADGE = {
    "pilot":      "background:#1e3a5f;color:#60a5fa;",
    "growth":     "background:#14352b;color:#34d399;",
    "enterprise": "background:#3b1a1a;color:#C74634;",
}


def _partner_card(partner: PartnerMetrics) -> str:
    last = partner.months[-1]
    prev = partner.months[-2]
    total_compute = sum(m.compute_hours for m in partner.months)
    total_billing = sum(m.billing_usd for m in partner.months)
    hc = _HEALTH_COLOUR[partner.health_status]
    tier_style = _TIER_BADGE.get(partner.tier, "")

    def arrow(new: float, old: float) -> str:
        if new > old:
            return '<span style="color:#22c55e">&#9650;</span>'
        if new < old:
            return '<span style="color:#ef4444">&#9660;</span>'
        return '<span style="color:#94a3b8">&#9644;</span>'

    api_arrow = arrow(last.api_calls, prev.api_calls)
    compute_arrow = arrow(last.compute_hours, prev.compute_hours)
    success_arrow = arrow(last.job_success_rate, prev.job_success_rate)

    mom_api_pct = f"{'+' if partner.mom_growth_api >= 0 else ''}{partner.mom_growth_api * 100:.1f}%"
    mom_compute_pct = f"{'+' if partner.mom_growth_compute >= 0 else ''}{partner.mom_growth_compute * 100:.1f}%"

    return f"""
<div style="background:#0f172a;border-radius:12px;padding:20px;
            border-left:4px solid {hc};min-width:260px;flex:1 1 260px;">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
    <div>
      <div style="font-size:16px;font-weight:700;color:#f1f5f9;">{partner.name}</div>
      <span style="font-size:11px;padding:2px 8px;border-radius:4px;{tier_style}">{partner.tier.upper()}</span>
    </div>
    <div style="text-align:right;">
      <div style="font-size:22px;font-weight:800;color:{hc};">{partner.nps_score:.1f}</div>
      <div style="font-size:10px;color:#64748b;">NPS / 10</div>
    </div>
  </div>

  <table style="width:100%;font-size:12px;border-collapse:collapse;">
    <tr>
      <td style="color:#94a3b8;padding:3px 0;">API Calls (last mo.)</td>
      <td style="color:#e2e8f0;text-align:right;">{last.api_calls:,} {api_arrow}</td>
    </tr>
    <tr>
      <td style="color:#94a3b8;padding:3px 0;">Compute Hours (Q)</td>
      <td style="color:#e2e8f0;text-align:right;">{total_compute:,.1f} {compute_arrow}</td>
    </tr>
    <tr>
      <td style="color:#94a3b8;padding:3px 0;">Jobs Completed (last mo.)</td>
      <td style="color:#e2e8f0;text-align:right;">{last.jobs_completed:,}</td>
    </tr>
    <tr>
      <td style="color:#94a3b8;padding:3px 0;">Success Rate</td>
      <td style="color:#e2e8f0;text-align:right;">{last.job_success_rate * 100:.1f}% {success_arrow}</td>
    </tr>
    <tr>
      <td style="color:#94a3b8;padding:3px 0;">MAE Improvement</td>
      <td style="color:#e2e8f0;text-align:right;">+{last.mae_improvement * 100:.1f}%</td>
    </tr>
    <tr>
      <td style="color:#94a3b8;padding:3px 0;">Model Versions (last mo.)</td>
      <td style="color:#e2e8f0;text-align:right;">{last.model_versions_finetuned}</td>
    </tr>
    <tr>
      <td style="color:#94a3b8;padding:3px 0;">Q Revenue</td>
      <td style="color:#e2e8f0;text-align:right;">${total_billing:,.2f}</td>
    </tr>
    <tr>
      <td style="color:#94a3b8;padding:3px 0;">Support Tickets</td>
      <td style="color:#e2e8f0;text-align:right;">{last.support_tickets}</td>
    </tr>
  </table>

  <div style="margin-top:12px;padding:8px;background:#1e293b;border-radius:6px;">
    <div style="font-size:10px;color:#64748b;margin-bottom:4px;">TOP FEATURE</div>
    <div style="font-size:11px;color:#93c5fd;">{partner.most_used_feature}</div>
  </div>

  <div style="margin-top:8px;font-size:11px;color:#64748b;">
    MoM API {mom_api_pct} &nbsp;|&nbsp; MoM Compute {mom_compute_pct}
  </div>
</div>
"""


def _priority_badge(priority: str) -> str:
    colours = {
        "high":   ("background:#3b1a1a;color:#C74634;", "HIGH"),
        "medium": ("background:#2d2a14;color:#f59e0b;", "MEDIUM"),
        "low":    ("background:#14352b;color:#34d399;", "LOW"),
    }
    style, label = colours.get(priority, ("", priority.upper()))
    return f'<span style="font-size:11px;padding:2px 8px;border-radius:4px;{style}">{label}</span>'


def render_html(partners: List[PartnerMetrics], summary: QuarterSummary, quarter: str) -> str:
    bar_svg = _svg_bar_chart(partners)
    line_svg = _svg_line_chart(partners)

    cards_html = "\n".join(_partner_card(p) for p in partners)

    rec_rows = ""
    for p in partners:
        hc = _HEALTH_COLOUR[p.health_status]
        rec_rows += f"""
      <tr style="border-bottom:1px solid #1e293b;">
        <td style="padding:10px 12px;color:#e2e8f0;font-weight:600;">
          <span style="display:inline-block;width:8px;height:8px;border-radius:50%;
                       background:{hc};margin-right:8px;"></span>{p.name}
        </td>
        <td style="padding:10px 12px;color:#94a3b8;">{p.recommendation}</td>
        <td style="padding:10px 12px;text-align:center;">{_priority_badge(p.recommendation_priority)}</td>
      </tr>"""

    health_items = "".join(
        f'<span style="color:{_HEALTH_COLOUR[k]};font-weight:700;">{v} {k.capitalize()}</span>  '
        for k, v in summary.partner_health.items()
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>OCI Robot Cloud — {quarter} Partner QBR</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: #1e293b;
      color: #e2e8f0;
      min-height: 100vh;
    }}
    h1, h2, h3 {{ color: #C74634; }}
    a {{ color: #60a5fa; }}
    .container {{ max-width: 1100px; margin: 0 auto; padding: 32px 24px; }}
    .banner {{
      background: #0f172a;
      border-radius: 12px;
      padding: 28px 32px;
      margin-bottom: 32px;
      border: 1px solid #334155;
    }}
    .banner h1 {{ font-size: 26px; margin-bottom: 12px; }}
    .kpi-row {{
      display: flex;
      gap: 24px;
      flex-wrap: wrap;
      margin-top: 16px;
    }}
    .kpi {{
      flex: 1 1 140px;
      background: #1e293b;
      border-radius: 8px;
      padding: 14px 18px;
      text-align: center;
    }}
    .kpi-value {{ font-size: 28px; font-weight: 800; color: #f1f5f9; }}
    .kpi-label {{ font-size: 11px; color: #64748b; margin-top: 4px; text-transform: uppercase; }}
    .section-title {{
      font-size: 18px;
      margin: 32px 0 16px;
      padding-bottom: 8px;
      border-bottom: 1px solid #334155;
    }}
    .partner-grid {{
      display: flex;
      flex-wrap: wrap;
      gap: 16px;
    }}
    .charts-row {{
      display: flex;
      gap: 24px;
      flex-wrap: wrap;
      margin-top: 8px;
    }}
    .chart-box {{
      flex: 1 1 340px;
      background: #0f172a;
      border-radius: 12px;
      padding: 16px;
      border: 1px solid #1e293b;
    }}
    .chart-box h3 {{ font-size: 13px; margin-bottom: 12px; color: #94a3b8; }}
    table.rec-table {{
      width: 100%;
      border-collapse: collapse;
      background: #0f172a;
      border-radius: 10px;
      overflow: hidden;
    }}
    table.rec-table thead th {{
      background: #1e293b;
      color: #94a3b8;
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      padding: 10px 12px;
      text-align: left;
    }}
    .footer {{
      text-align: center;
      color: #334155;
      font-size: 11px;
      margin-top: 48px;
      padding-top: 16px;
      border-top: 1px solid #1e293b;
    }}
  </style>
</head>
<body>
<div class="container">

  <!-- Banner -->
  <div class="banner">
    <h1>OCI Robot Cloud &mdash; {summary.quarter} Partner QBR</h1>
    <p style="color:#94a3b8;font-size:13px;">Design Partner Performance Report &bull; Generated automatically</p>
    <div class="kpi-row">
      <div class="kpi">
        <div class="kpi-value">{summary.partner_count}</div>
        <div class="kpi-label">Active Partners</div>
      </div>
      <div class="kpi">
        <div class="kpi-value">{summary.total_compute_hours:,.0f}</div>
        <div class="kpi-label">Compute Hours</div>
      </div>
      <div class="kpi">
        <div class="kpi-value">${summary.total_revenue_usd:,.0f}</div>
        <div class="kpi-label">Total Revenue</div>
      </div>
      <div class="kpi">
        <div class="kpi-value">{summary.avg_nps:.1f}<span style="font-size:16px;color:#64748b;">/10</span></div>
        <div class="kpi-label">Avg NPS</div>
      </div>
      <div class="kpi" style="text-align:left;">
        <div style="font-size:13px;line-height:2;">{health_items}</div>
        <div class="kpi-label">Partner Health</div>
      </div>
    </div>
  </div>

  <!-- Partner Cards -->
  <h2 class="section-title">Partner Scorecards</h2>
  <div class="partner-grid">
    {cards_html}
  </div>

  <!-- Charts -->
  <h2 class="section-title">Analytics</h2>
  <div class="charts-row">
    <div class="chart-box">
      <h3>Compute Hours by Partner (Q Total)</h3>
      {bar_svg}
    </div>
    <div class="chart-box">
      <h3>Job Success Rate Trend</h3>
      {line_svg}
    </div>
  </div>

  <!-- Recommendations -->
  <h2 class="section-title">Recommendations</h2>
  <table class="rec-table">
    <thead>
      <tr>
        <th style="width:18%;">Partner</th>
        <th>Recommendation</th>
        <th style="width:10%;text-align:center;">Priority</th>
      </tr>
    </thead>
    <tbody>
      {rec_rows}
    </tbody>
  </table>

  <div class="footer">
    OCI Robot Cloud &bull; Oracle &bull; Confidential &bull; {summary.quarter}
  </div>
</div>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# JSON serialization helper
# ---------------------------------------------------------------------------

def build_json_output(partners: List[PartnerMetrics], summary: QuarterSummary) -> dict:
    return {
        "quarter_summary": asdict(summary),
        "partners": [asdict(p) for p in partners],
    }


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------

def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate OCI Robot Cloud Partner QBR report."
    )
    parser.add_argument("--mock", action="store_true", default=True,
                        help="Use simulated data (default: True)")
    parser.add_argument("--quarter", default="Q1-2026",
                        help="Quarter label, e.g. Q1-2026 (default: Q1-2026)")
    parser.add_argument("--output", default="/tmp/partner_qbr.html",
                        help="Output path for the HTML report (default: /tmp/partner_qbr.html)")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed for simulation reproducibility (default: 42)")
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> None:
    args = parse_args(argv)

    print(f"[QBR] Generating {args.quarter} report (seed={args.seed}) …")

    partners = simulate_all_partners(seed=args.seed, quarter=args.quarter)
    summary = compute_quarter_summary(partners, args.quarter)

    print_summary_table(partners, summary)

    # HTML
    html = render_html(partners, summary, args.quarter)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    print(f"[QBR] HTML report written to: {output_path}")

    # JSON
    json_path = output_path.with_suffix(".json")
    json_path.write_text(
        json.dumps(build_json_output(partners, summary), indent=2),
        encoding="utf-8",
    )
    print(f"[QBR] JSON data written to:   {json_path}")


if __name__ == "__main__":
    main()
