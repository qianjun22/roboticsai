#!/usr/bin/env python3
"""
customer_churn_predictor.py — Churn risk prediction for OCI Robot Cloud design partners.

Analyzes usage patterns, SR trends, billing, NPS, and support tickets to compute
churn probability for each design partner. Surfaces intervention recommendations.

Usage:
    python src/api/customer_churn_predictor.py --mock --output /tmp/customer_churn_predictor.html
"""

import argparse
import json
import math
import random
import time
from dataclasses import dataclass, field
from pathlib import Path


PARTNERS = [
    # (name, tier, months_active, base_churn_risk)
    ("partner_alpha",   "enterprise", 6, 0.08),   # happy, long-term
    ("partner_beta",    "growth",     4, 0.22),   # moderate risk
    ("partner_gamma",   "pilot",      2, 0.41),   # new, unstable
    ("partner_delta",   "enterprise", 5, 0.15),
    ("partner_epsilon", "growth",     3, 0.31),
]

CHURN_FACTORS = [
    "sr_declining",
    "low_api_usage",
    "billing_issues",
    "support_tickets_open",
    "no_dagger_upgrade",
    "low_nps",
    "competitor_evaluating",
]


@dataclass
class ChurnSignal:
    factor: str
    present: bool
    weight: float
    contribution: float


@dataclass
class PartnerChurnProfile:
    partner_name: str
    tier: str
    months_active: int
    churn_probability: float
    risk_level: str         # LOW/MEDIUM/HIGH/CRITICAL
    monthly_arr: float
    arr_at_risk: float
    current_sr: float
    sr_trend: str           # improving/stable/declining
    api_calls_30d: int
    nps_score: int
    open_tickets: int
    signals: list[ChurnSignal]
    recommended_action: str
    urgency_days: int       # days before next renewal/checkpoint


@dataclass
class ChurnReport:
    total_arr: float
    arr_at_risk: float
    pct_at_risk: float
    high_risk_partners: int
    critical_partners: list[str]
    results: list[PartnerChurnProfile] = field(default_factory=list)


def simulate_churn(seed: int = 42) -> ChurnReport:
    rng = random.Random(seed)
    results: list[PartnerChurnProfile] = []

    tier_arr = {"pilot": 800, "growth": 2400, "enterprise": 6500}

    for name, tier, months, base_risk in PARTNERS:
        # Simulate signals
        signals: list[ChurnSignal] = []
        final_risk = base_risk

        for factor in CHURN_FACTORS:
            weight = {"sr_declining": 0.25, "low_api_usage": 0.15,
                      "billing_issues": 0.20, "support_tickets_open": 0.10,
                      "no_dagger_upgrade": 0.10, "low_nps": 0.15,
                      "competitor_evaluating": 0.05}.get(factor, 0.1)
            present = rng.random() < (base_risk * 1.5)
            contribution = weight * (0.8 + rng.gauss(0, 0.1)) if present else 0.0
            final_risk += contribution * 0.3
            signals.append(ChurnSignal(factor=factor, present=present,
                                       weight=weight, contribution=round(contribution, 3)))

        final_risk = max(0.02, min(0.95, final_risk + rng.gauss(0, 0.03)))

        risk_level = ("CRITICAL" if final_risk > 0.65
                      else "HIGH" if final_risk > 0.40
                      else "MEDIUM" if final_risk > 0.20
                      else "LOW")

        arr = tier_arr[tier] * (1 + rng.gauss(0, 0.1))
        arr_risk = arr * final_risk

        sr = 0.55 + rng.gauss(0, 0.08) + months * 0.01
        sr = max(0.3, min(0.92, sr))
        sr_trend_v = rng.gauss(0, 0.02)
        sr_trend = "improving" if sr_trend_v > 0.01 else "declining" if sr_trend_v < -0.01 else "stable"

        api_calls = int(max(10, (1 - base_risk) * 2000 + rng.gauss(0, 200)))
        nps = max(-10, min(10, int(10 - final_risk * 15 + rng.gauss(0, 1.5))))
        tickets = max(0, int(final_risk * 6 + rng.gauss(0, 1)))

        # Recommendation based on top signal
        top_signal = max(signals, key=lambda s: s.contribution)
        action_map = {
            "sr_declining": "Schedule DAgger run with CSM — boost SR to maintain renewal",
            "low_api_usage": "Executive sponsor call — confirm champion still active",
            "billing_issues": "Finance team engagement + invoice reconciliation",
            "support_tickets_open": "Escalate to P1 SLA — resolve blockers this week",
            "no_dagger_upgrade": "Demo DAgger ROI — show 15%+ SR improvement with data",
            "low_nps": "NPS recovery playbook — QBR with roadmap alignment",
            "competitor_evaluating": "Competitive defense briefing + exclusive feature preview",
        }
        action = action_map.get(top_signal.factor, "Proactive health check call")

        urgency = max(7, int(30 * (1 - final_risk) + rng.gauss(0, 3)))

        results.append(PartnerChurnProfile(
            partner_name=name, tier=tier, months_active=months,
            churn_probability=round(final_risk, 3),
            risk_level=risk_level,
            monthly_arr=round(arr / 12, 0),
            arr_at_risk=round(arr_risk, 0),
            current_sr=round(sr, 3),
            sr_trend=sr_trend,
            api_calls_30d=api_calls,
            nps_score=nps,
            open_tickets=tickets,
            signals=signals,
            recommended_action=action,
            urgency_days=urgency,
        ))

    total_arr = sum(r.monthly_arr * 12 for r in results)
    arr_at_risk = sum(r.arr_at_risk for r in results)
    high_risk = sum(1 for r in results if r.risk_level in ("HIGH", "CRITICAL"))
    critical = [r.partner_name for r in results if r.risk_level == "CRITICAL"]

    return ChurnReport(
        total_arr=round(total_arr, 0),
        arr_at_risk=round(arr_at_risk, 0),
        pct_at_risk=round(arr_at_risk / total_arr * 100, 1),
        high_risk_partners=high_risk,
        critical_partners=critical,
        results=results,
    )


def render_html(report: ChurnReport) -> str:
    RISK_COLORS = {"LOW": "#22c55e", "MEDIUM": "#f59e0b", "HIGH": "#ef4444", "CRITICAL": "#dc2626"}
    TIER_COLORS = {"pilot": "#f59e0b", "growth": "#3b82f6", "enterprise": "#22c55e"}
    TREND_ICONS = {"improving": "↑", "stable": "→", "declining": "↓"}
    TREND_COLORS = {"improving": "#22c55e", "stable": "#94a3b8", "declining": "#ef4444"}

    # SVG: churn probability bar chart (sorted by risk)
    sorted_r = sorted(report.results, key=lambda r: r.churn_probability, reverse=True)
    w, h, ml, mb = 460, 160, 120, 30
    inner_w = w - ml - 20
    bar_h = 18
    gap = 8

    svg_bar = f'<svg width="{w}" height="{h}" style="background:#0f172a;border-radius:8px">'
    svg_bar += f'<line x1="{ml}" y1="15" x2="{ml}" y2="{h - mb}" stroke="#475569"/>'
    svg_bar += f'<line x1="{ml}" y1="{h-mb}" x2="{w-20}" y2="{h-mb}" stroke="#475569"/>'

    for i, r in enumerate(sorted_r):
        y = 20 + i * (bar_h + gap)
        bar_w = r.churn_probability * inner_w
        col = RISK_COLORS[r.risk_level]
        svg_bar += (f'<rect x="{ml}" y="{y}" width="{bar_w:.1f}" '
                    f'height="{bar_h}" fill="{col}" opacity="0.75" rx="2"/>')
        svg_bar += (f'<text x="{ml-4}" y="{y+bar_h-4}" fill="#94a3b8" '
                    f'font-size="9" text-anchor="end">{r.partner_name[:14]}</text>')
        svg_bar += (f'<text x="{ml+bar_w+4:.1f}" y="{y+bar_h-4}" fill="{col}" '
                    f'font-size="8.5">{r.churn_probability:.0%}</text>')

    for v in [0.25, 0.50, 0.75, 1.0]:
        x = ml + v * inner_w
        svg_bar += (f'<line x1="{x:.1f}" y1="15" x2="{x:.1f}" y2="{h-mb}" '
                    f'stroke="#1e293b" stroke-width="1"/>')
        svg_bar += (f'<text x="{x:.1f}" y="{h-mb+12}" fill="#64748b" '
                    f'font-size="7.5" text-anchor="middle">{v:.0%}</text>')

    svg_bar += '</svg>'

    # SVG: ARR at risk vs monthly ARR per partner (bubble chart)
    bw, bh, bm = 360, 200, 45
    max_arr = max(r.monthly_arr * 12 for r in report.results)

    svg_bub = f'<svg width="{bw}" height="{bh}" style="background:#0f172a;border-radius:8px">'
    svg_bub += f'<line x1="{bm}" y1="{bm}" x2="{bm}" y2="{bh-bm}" stroke="#475569"/>'
    svg_bub += f'<line x1="{bm}" y1="{bh-bm}" x2="{bw-bm}" y2="{bh-bm}" stroke="#475569"/>'

    for r in report.results:
        col = RISK_COLORS[r.risk_level]
        cx = bm + (r.churn_probability) * (bw - 2 * bm)
        cy = bh - bm - (r.monthly_arr * 12 / max_arr) * (bh - 2 * bm)
        size = 5 + (r.monthly_arr * 12 / max_arr) * 10
        svg_bub += (f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{size:.1f}" '
                    f'fill="{col}" opacity="0.7"/>')
        svg_bub += (f'<text x="{cx:.1f}" y="{cy-size-3:.1f}" fill="{col}" '
                    f'font-size="7.5" text-anchor="middle">{r.partner_name[:8]}</text>')

    # 0.5 churn threshold
    x50 = bm + 0.5 * (bw - 2 * bm)
    svg_bub += (f'<line x1="{x50:.1f}" y1="{bm}" x2="{x50:.1f}" y2="{bh-bm}" '
                f'stroke="#ef4444" stroke-width="1" stroke-dasharray="4,3" opacity="0.5"/>')
    svg_bub += (f'<text x="{bw-bm}" y="{bh-bm+12}" fill="#64748b" '
                f'font-size="7.5" text-anchor="end">Churn Risk →</text>')
    svg_bub += (f'<text x="{bm-10}" y="{bh//2}" fill="#64748b" font-size="7.5" '
                f'text-anchor="middle" transform="rotate(-90,{bm-10},{bh//2})">ARR ↑</text>')
    svg_bub += '</svg>'

    # Partner rows
    rows = ""
    for r in sorted_r:
        risk_col  = RISK_COLORS[r.risk_level]
        tier_col  = TIER_COLORS.get(r.tier, "#64748b")
        trend_col = TREND_COLORS[r.sr_trend]
        top_sig   = max(r.signals, key=lambda s: s.contribution)
        rows += (f'<tr>'
                 f'<td style="color:#e2e8f0;font-weight:bold">{r.partner_name}</td>'
                 f'<td style="color:{tier_col}">{r.tier}</td>'
                 f'<td style="color:{risk_col};font-weight:bold">{r.churn_probability:.0%} — {r.risk_level}</td>'
                 f'<td style="color:#22c55e">${r.monthly_arr:,.0f}/mo</td>'
                 f'<td style="color:#ef4444">${r.arr_at_risk:,.0f}</td>'
                 f'<td style="color:{trend_col}">{r.current_sr:.0%} {TREND_ICONS[r.sr_trend]}</td>'
                 f'<td style="color:#64748b">{r.nps_score:+d}</td>'
                 f'<td style="color:#94a3b8;font-size:9px">{r.recommended_action[:50]}...</td>'
                 f'</tr>')

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Customer Churn Predictor</title>
<style>
body{{background:#1e293b;color:#e2e8f0;font-family:monospace;margin:0;padding:24px}}
h1{{color:#C74634;margin:0 0 4px}}
.meta{{color:#94a3b8;font-size:12px;margin-bottom:20px}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:20px}}
.card{{background:#0f172a;border-radius:8px;padding:14px}}
.card h3{{color:#94a3b8;font-size:11px;text-transform:uppercase;margin:0 0 4px}}
.big{{font-size:22px;font-weight:bold}}
.layout{{display:grid;grid-template-columns:3fr 2fr;gap:12px;margin-bottom:20px}}
table{{width:100%;border-collapse:collapse;font-size:11px}}
th{{color:#94a3b8;text-align:left;padding:5px 8px;border-bottom:1px solid #334155}}
td{{padding:3px 8px;border-bottom:1px solid #1e293b}}
h3.sec{{color:#94a3b8;font-size:11px;text-transform:uppercase;margin-bottom:8px}}
</style></head>
<body>
<h1>Customer Churn Predictor</h1>
<div class="meta">
  {len(PARTNERS)} design partners · 7 churn signals · OCI Robot Cloud retention analysis
</div>

<div class="grid">
  <div class="card"><h3>Total ARR</h3>
    <div class="big" style="color:#22c55e">${report.total_arr:,.0f}</div>
  </div>
  <div class="card"><h3>ARR at Risk</h3>
    <div class="big" style="color:#ef4444">${report.arr_at_risk:,.0f}</div>
    <div style="color:#64748b;font-size:10px">{report.pct_at_risk:.1f}% of ARR</div>
  </div>
  <div class="card"><h3>High Risk Partners</h3>
    <div class="big" style="color:#f59e0b">{report.high_risk_partners}</div>
    <div style="color:#64748b;font-size:10px">need immediate action</div>
  </div>
  <div class="card"><h3>Critical</h3>
    <div class="big" style="color:#dc2626">{len(report.critical_partners)}</div>
    <div style="color:#64748b;font-size:10px">
      {", ".join(report.critical_partners) if report.critical_partners else "None"}
    </div>
  </div>
</div>

<div class="layout">
  <div>
    <h3 class="sec">Churn Probability by Partner</h3>
    {svg_bar}
  </div>
  <div>
    <h3 class="sec">ARR vs Churn Risk (size=ARR)</h3>
    {svg_bub}
    <div style="color:#64748b;font-size:10px;margin-top:4px">
      Right of dashed line (>50%) = high churn risk
    </div>
  </div>
</div>

<h3 class="sec">Partner Risk Detail</h3>
<table>
  <tr><th>Partner</th><th>Tier</th><th>Churn Risk</th><th>ARR/mo</th>
      <th>ARR at Risk</th><th>SR</th><th>NPS</th><th>Recommended Action</th></tr>
  {rows}
</table>

<div style="background:#0f172a;border-radius:8px;padding:12px;margin-top:14px;font-size:10px">
  <div style="color:#C74634;font-weight:bold;margin-bottom:4px">RETENTION PLAYBOOK</div>
  <div style="color:#22c55e">LOW (&lt;20%): monthly health check email; auto-share SR reports</div>
  <div style="color:#f59e0b">MEDIUM (20–40%): bi-weekly CSM call; DAgger upgrade offer; NPS survey</div>
  <div style="color:#ef4444">HIGH (40–65%): executive sponsor engagement; quarterly roadmap review; discount offer</div>
  <div style="color:#dc2626">CRITICAL (&gt;65%): CEO/CTO call within 48h; custom SLA; joint pilot success criteria</div>
</div>
</body></html>"""


def main():
    parser = argparse.ArgumentParser(description="Customer churn predictor for OCI Robot Cloud")
    parser.add_argument("--mock",   action="store_true", default=True)
    parser.add_argument("--output", default="/tmp/customer_churn_predictor.html")
    parser.add_argument("--seed",   type=int, default=42)
    args = parser.parse_args()

    print(f"[churn] {len(PARTNERS)} partners · {len(CHURN_FACTORS)} signals")
    t0 = time.time()

    report = simulate_churn(args.seed)

    print(f"\n  {'Partner':<18} {'Risk':>8} {'Level':>10} {'ARR/mo':>8} {'SR':>6}  Action")
    print(f"  {'─'*18} {'─'*8} {'─'*10} {'─'*8} {'─'*6}  {'─'*30}")
    for r in sorted(report.results, key=lambda x: x.churn_probability, reverse=True):
        print(f"  {r.partner_name:<18} {r.churn_probability:>7.0%} {r.risk_level:>10} "
              f"${r.monthly_arr:>6,.0f} {r.current_sr:>5.0%}  "
              f"{r.recommended_action[:35]}...")

    print(f"\n  Total ARR: ${report.total_arr:,.0f} | At risk: ${report.arr_at_risk:,.0f} "
          f"({report.pct_at_risk:.1f}%)")
    print(f"  [{time.time()-t0:.1f}s]\n")

    html = render_html(report)
    Path(args.output).write_text(html)
    print(f"  HTML → {args.output}")

    json_out = Path(args.output).with_suffix(".json")
    json_out.write_text(json.dumps({
        "total_arr": report.total_arr,
        "arr_at_risk": report.arr_at_risk,
        "pct_at_risk": report.pct_at_risk,
        "high_risk_partners": report.high_risk_partners,
        "results": [{"name": r.partner_name, "churn_probability": r.churn_probability,
                     "risk_level": r.risk_level, "arr_at_risk": r.arr_at_risk} for r in report.results],
    }, indent=2))
    print(f"  JSON → {json_out}")


if __name__ == "__main__":
    main()
