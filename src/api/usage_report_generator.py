#!/usr/bin/env python3
"""
usage_report_generator.py — Generates monthly usage reports for OCI Robot Cloud partners.

Produces per-partner PDF-ready HTML reports covering GPU consumption, training runs,
eval results, cost breakdown, and ROI metrics. Sent automatically on the 1st of each month.

Usage:
    python src/api/usage_report_generator.py --mock --month 2026-03
    python src/api/usage_report_generator.py --partner acme --output /tmp/acme_mar2026.html
"""

import argparse
import json
import math
import random
from dataclasses import dataclass, field
from datetime import datetime, date
from pathlib import Path


# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class TrainingRunRecord:
    run_id: str
    date: str
    algo: str           # BC / DAgger / LoRA / HPO
    n_steps: int
    n_demos: int
    gpu_type: str
    gpu_hours: float
    cost_usd: float
    final_sr: float     # 0–1
    final_loss: float


@dataclass
class PartnerUsageReport:
    partner_id: str
    company: str
    tier: str
    month: str
    runs: list[TrainingRunRecord]
    # Aggregated
    total_gpu_hours: float
    total_cost_usd: float
    included_hours: float   # tier entitlement
    overage_usd: float
    best_sr: float
    sr_improvement: float   # vs prior month
    total_demos: int
    eval_episodes: int
    # ROI
    estimated_manual_cost_usd: float   # hiring ML engineer to do same
    roi_multiple: float


# ── Mock data generator ───────────────────────────────────────────────────────

def mock_partner(partner_id: str, company: str, tier: str,
                 month: str, seed: int = 42) -> PartnerUsageReport:
    rng = random.Random(seed)
    tier_hours = {"Pilot": 24, "Growth": 120, "Enterprise": 500}
    tier_price = {"Pilot": 500, "Growth": 2000, "Enterprise": 8000}
    included_h = tier_hours[tier]

    n_runs = {"Pilot": rng.randint(4, 8), "Growth": rng.randint(10, 20),
              "Enterprise": rng.randint(20, 40)}[tier]

    runs = []
    gpu_h_used = 0.0
    sr_start = rng.uniform(0.05, 0.25)

    for i in range(n_runs):
        algo = rng.choices(["BC", "DAgger", "LoRA", "HPO"], weights=[0.2, 0.4, 0.3, 0.1])[0]
        n_steps = rng.choice([1000, 2000, 3000, 5000])
        gpu_type = rng.choices(["A100_80GB", "A10_24GB"], weights=[0.4, 0.6])[0]
        it_s = 2.35 if "A100" in gpu_type else 1.05
        gpu_h = n_steps / (it_s * 3600)
        rate = 4.20 if "A100" in gpu_type else 1.50
        cost = gpu_h * rate

        # SR improves over runs
        sr = min(0.92, sr_start + i * rng.uniform(0.01, 0.04) + rng.gauss(0, 0.02))
        loss_final = max(0.05, 0.68 - sr * 0.7 + rng.gauss(0, 0.01))

        run_date = f"{month}-{str(rng.randint(1, 28)).zfill(2)}"
        runs.append(TrainingRunRecord(
            run_id=f"{partner_id}-{month}-r{i+1:02d}",
            date=run_date,
            algo=algo,
            n_steps=n_steps,
            n_demos=rng.choice([200, 500, 1000, 2000]),
            gpu_type=gpu_type,
            gpu_hours=round(gpu_h, 3),
            cost_usd=round(cost, 4),
            final_sr=round(sr, 3),
            final_loss=round(loss_final, 4),
        ))
        gpu_h_used += gpu_h
        sr_start = sr

    total_cost = sum(r.cost_usd for r in runs)
    overage_h = max(0, gpu_h_used - included_h)
    overage_usd = overage_h * 4.20 * 0.8   # 20% discount on overage

    best_sr = max(r.final_sr for r in runs)
    sr_improvement = best_sr - runs[0].final_sr

    # ROI: ML engineer costs $250/hr; same work would take ~8× more hours
    manual_hr = gpu_h_used * 8
    manual_cost = manual_hr * 250
    roi = manual_cost / (tier_price[tier] + total_cost) if total_cost > 0 else 1.0

    return PartnerUsageReport(
        partner_id=partner_id,
        company=company,
        tier=tier,
        month=month,
        runs=runs,
        total_gpu_hours=round(gpu_h_used, 2),
        total_cost_usd=round(total_cost, 2),
        included_hours=included_h,
        overage_usd=round(overage_usd, 2),
        best_sr=round(best_sr, 3),
        sr_improvement=round(sr_improvement, 3),
        total_demos=sum(r.n_demos for r in runs),
        eval_episodes=len(runs) * 10,
        estimated_manual_cost_usd=round(manual_cost, 0),
        roi_multiple=round(roi, 1),
    )


MOCK_PARTNERS = [
    ("acme",   "Acme Robotics",  "Enterprise", 1),
    ("botco",  "BotCo",          "Growth",     2),
    ("nexa",   "NexaArm",        "Pilot",      3),
    ("viper",  "ViperRob",       "Growth",     4),
]


# ── HTML report renderer ──────────────────────────────────────────────────────

def render_partner_report(report: PartnerUsageReport) -> str:
    # SVG: SR progression over runs (sorted by date)
    sorted_runs = sorted(report.runs, key=lambda r: r.date)
    w, h = 520, 130
    n = len(sorted_runs)
    x_scale = (w - 50) / max(n - 1, 1)
    y_scale = (h - 30) / 1.0

    sr_pts = " ".join(
        f"{25+i*x_scale:.1f},{h-10-r.final_sr*y_scale:.1f}"
        for i, r in enumerate(sorted_runs)
    )
    target_y = h - 10 - 0.65 * y_scale
    loss_pts = " ".join(
        f"{25+i*x_scale:.1f},{h-10-r.final_loss*y_scale:.1f}"
        for i, r in enumerate(sorted_runs)
    )

    svg = (
        f'<svg width="{w}" height="{h}" style="background:#0f172a;border-radius:8px">'
        f'<line x1="25" y1="{target_y:.1f}" x2="{w}" y2="{target_y:.1f}" '
        f'stroke="#f59e0b" stroke-width="1" stroke-dasharray="4,3"/>'
        f'<text x="27" y="{target_y-3:.1f}" fill="#f59e0b" font-size="9">target 65%</text>'
        f'<polyline points="{sr_pts}" fill="none" stroke="#22c55e" stroke-width="2"/>'
        f'<polyline points="{loss_pts}" fill="none" stroke="#C74634" stroke-width="1.5" '
        f'stroke-dasharray="3,2" opacity="0.7"/>'
        f'<text x="27" y="{h-2}" fill="#22c55e" font-size="9">— success rate</text>'
        f'<text x="130" y="{h-2}" fill="#C74634" font-size="9">-- loss</text>'
    )
    for i, r in enumerate(sorted_runs):
        col = "#22c55e" if r.final_sr >= 0.65 else "#f59e0b"
        svg += (f'<circle cx="{25+i*x_scale:.1f}" cy="{h-10-r.final_sr*y_scale:.1f}" '
                f'r="3" fill="{col}"/>')
    svg += '</svg>'

    # Run rows
    algo_colors = {"BC": "#64748b", "DAgger": "#22c55e", "LoRA": "#3b82f6", "HPO": "#f59e0b"}
    run_rows = ""
    for r in sorted_runs:
        ac = algo_colors.get(r.algo, "#94a3b8")
        sr_c = "#22c55e" if r.final_sr >= 0.65 else "#f59e0b" if r.final_sr >= 0.35 else "#ef4444"
        run_rows += (f'<tr><td style="color:#64748b">{r.date}</td>'
                     f'<td style="color:{ac}">{r.algo}</td>'
                     f'<td>{r.n_steps:,}</td>'
                     f'<td>{r.n_demos}</td>'
                     f'<td>{r.gpu_type.replace("_","·")}</td>'
                     f'<td>{r.gpu_hours:.2f}h</td>'
                     f'<td>${r.cost_usd:.4f}</td>'
                     f'<td style="color:{sr_c}">{r.final_sr:.0%}</td></tr>')

    util_pct = min(100, report.total_gpu_hours / report.included_hours * 100)
    util_col = "#22c55e" if util_pct >= 60 else "#f59e0b" if util_pct >= 30 else "#ef4444"
    overage_row = (f'<div style="color:#f59e0b;font-size:11px;margin-top:4px">'
                   f'Overage: +${report.overage_usd:.2f}</div>'
                   if report.overage_usd > 0 else "")

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<title>{report.company} — Usage Report {report.month}</title>
<style>
body{{background:#1e293b;color:#e2e8f0;font-family:'Segoe UI',sans-serif;margin:0;padding:28px;max-width:900px}}
h1{{color:#C74634;margin:0 0 4px;font-size:22px}}
h2{{color:#C74634;font-size:14px;margin:20px 0 10px;border-bottom:1px solid #334155;padding-bottom:4px}}
.meta{{color:#94a3b8;font-size:12px;margin-bottom:20px}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:20px}}
.card{{background:#0f172a;border-radius:8px;padding:14px}}
.card h3{{color:#94a3b8;font-size:10px;text-transform:uppercase;margin:0 0 4px}}
.big{{font-size:26px;font-weight:bold}}
table{{width:100%;border-collapse:collapse;font-size:12px}}
th{{color:#64748b;text-align:left;padding:4px 8px;border-bottom:1px solid #334155}}
td{{padding:3px 8px;border-bottom:1px solid #1e293b}}
.util-bar{{background:#334155;border-radius:3px;height:8px;margin-top:4px}}
.util-fill{{height:8px;border-radius:3px;background:{util_col};width:{util_pct:.0f}%}}
footer{{color:#475569;font-size:10px;margin-top:24px;border-top:1px solid #334155;padding-top:10px}}
</style></head>
<body>
<h1>{report.company} — Monthly Usage Report</h1>
<div class="meta">{report.month} · {report.tier} tier · {report.partner_id}@oci-robot-cloud</div>

<div class="grid">
  <div class="card"><h3>Best SR This Month</h3>
    <div class="big" style="color:#22c55e">{report.best_sr:.0%}</div>
    <div style="color:#64748b;font-size:11px">+{report.sr_improvement:.0%} vs start</div></div>
  <div class="card"><h3>GPU Hours Used</h3>
    <div class="big" style="color:{util_col}">{report.total_gpu_hours:.1f}h</div>
    <div class="util-bar"><div class="util-fill"></div></div>
    <div style="color:#64748b;font-size:10px">{util_pct:.0f}% of {report.included_hours}h included</div>
    {overage_row}</div>
  <div class="card"><h3>Training Cost</h3>
    <div class="big">${report.total_cost_usd:.2f}</div>
    <div style="color:#64748b;font-size:11px">incl. in {report.tier} plan</div></div>
  <div class="card"><h3>ROI vs Manual</h3>
    <div class="big" style="color:#22c55e">{report.roi_multiple:.1f}×</div>
    <div style="color:#64748b;font-size:11px">${report.estimated_manual_cost_usd:,.0f} saved</div></div>
</div>

<h2>Success Rate & Loss Progression</h2>
{svg}

<h2>Training Runs ({len(report.runs)} total)</h2>
<table>
  <tr><th>Date</th><th>Algorithm</th><th>Steps</th><th>Demos</th>
      <th>GPU</th><th>GPU-hrs</th><th>Cost</th><th>SR</th></tr>
  {run_rows}
</table>

<footer>
  OCI Robot Cloud · {report.company} · {report.month} ·
  {report.total_demos:,} total demo frames processed · {report.eval_episodes} eval episodes ·
  Contact: oci-robot-cloud@oracle.com
</footer>
</body></html>"""


def render_index(reports: list[PartnerUsageReport], month: str) -> str:
    rows = ""
    for r in sorted(reports, key=lambda x: -x.best_sr):
        sr_c = "#22c55e" if r.best_sr >= 0.65 else "#f59e0b" if r.best_sr >= 0.35 else "#ef4444"
        rows += (f'<tr><td style="color:#e2e8f0">{r.company}</td>'
                 f'<td style="color:#64748b">{r.tier}</td>'
                 f'<td style="color:{sr_c}">{r.best_sr:.0%}</td>'
                 f'<td>+{r.sr_improvement:.0%}</td>'
                 f'<td>{r.total_gpu_hours:.1f}h</td>'
                 f'<td>${r.total_cost_usd:.2f}</td>'
                 f'<td style="color:#22c55e">{r.roi_multiple:.1f}×</td>'
                 f'<td>{len(r.runs)}</td></tr>')
    total_cost = sum(r.total_cost_usd for r in reports)
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Usage Reports {month}</title>
<style>
body{{background:#1e293b;color:#e2e8f0;font-family:monospace;margin:0;padding:24px}}
h1{{color:#C74634;margin:0 0 20px}}
table{{width:100%;border-collapse:collapse;font-size:13px}}
th{{color:#94a3b8;text-align:left;padding:6px 10px;border-bottom:1px solid #334155}}
td{{padding:5px 10px;border-bottom:1px solid #1e293b}}
</style></head>
<body>
<h1>Usage Reports — {month} · {len(reports)} partners · ${total_cost:.2f} total</h1>
<table>
  <tr><th>Company</th><th>Tier</th><th>Best SR</th><th>SR Gain</th>
      <th>GPU-hrs</th><th>Cost</th><th>ROI</th><th>Runs</th></tr>
  {rows}
</table>
</body></html>"""


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Monthly usage report generator")
    parser.add_argument("--mock",    action="store_true", default=True)
    parser.add_argument("--month",   default=datetime.now().strftime("%Y-%m"))
    parser.add_argument("--partner", default="",
                        help="Partner ID to generate single report (default=all)")
    parser.add_argument("--output",  default="/tmp/usage_reports")
    args = parser.parse_args()

    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)

    partners = [(p, c, t, s) for p, c, t, s in MOCK_PARTNERS
                if not args.partner or p == args.partner]

    reports = []
    for pid, company, tier, seed in partners:
        print(f"  [gen] {company} ({tier})...")
        rpt = mock_partner(pid, company, tier, args.month, seed)
        reports.append(rpt)
        html = render_partner_report(rpt)
        path = out / f"{pid}_{args.month}.html"
        path.write_text(html)
        print(f"         → {path}  SR={rpt.best_sr:.0%}  cost=${rpt.total_cost_usd:.2f}  "
              f"ROI={rpt.roi_multiple:.1f}×")

    if len(reports) > 1:
        idx = render_index(reports, args.month)
        idx_path = out / f"index_{args.month}.html"
        idx_path.write_text(idx)
        print(f"\n  Index → {idx_path}")

    json_path = out / f"summary_{args.month}.json"
    json_path.write_text(json.dumps(
        [{"partner": r.partner_id, "company": r.company, "best_sr": r.best_sr,
          "cost_usd": r.total_cost_usd, "roi": r.roi_multiple, "runs": len(r.runs)}
         for r in reports], indent=2))
    print(f"  JSON → {json_path}")


if __name__ == "__main__":
    main()
