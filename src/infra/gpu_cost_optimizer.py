#!/usr/bin/env python3
"""
gpu_cost_optimizer.py — GPU cost optimization recommendations for OCI Robot Cloud.

Analyzes training job patterns and recommends cost-saving strategies:
spot vs on-demand, batch coalescing, off-peak scheduling, multi-GPU efficiency.
Targets 30%+ cost reduction vs naive scheduling.

Usage:
    python src/infra/gpu_cost_optimizer.py --mock --output /tmp/gpu_cost_optimizer.html
    python src/infra/gpu_cost_optimizer.py --jobs 50 --seed 42
"""

import argparse
import json
import math
import random
import time
from dataclasses import dataclass
from pathlib import Path


# ── Types ─────────────────────────────────────────────────────────────────────

@dataclass
class TrainingJob:
    job_id: str
    partner: str
    task: str
    n_steps: int
    batch_size: int
    gpu_type: str       # A100_80GB / A10_24GB
    submitted_at_hr: float   # hour of day (0-23)
    is_urgent: bool
    estimated_hr: float


@dataclass
class OptimizationStrategy:
    name: str
    description: str
    savings_pct: float
    applicable_jobs: int
    risk: str   # low/medium/high


# ── Rates ─────────────────────────────────────────────────────────────────────

RATES = {
    "A100_80GB": {"on_demand": 4.20, "spot": 1.47, "preempt_rate": 0.08},
    "A10_24GB":  {"on_demand": 1.50, "spot": 0.52, "preempt_rate": 0.05},
}

OFF_PEAK_DISCOUNT = 0.15   # 15% cheaper 10pm-6am


# ── Mock job generator ────────────────────────────────────────────────────────

def generate_jobs(n: int = 30, seed: int = 42) -> list[TrainingJob]:
    rng = random.Random(seed)
    partners = ["AcmeRobotics", "BotCo", "NexaArm", "internal", "ViperRob"]
    tasks = ["pick_and_lift", "bin_picking", "cable_routing", "door_open"]
    jobs = []
    for i in range(n):
        steps = rng.choice([1000, 2000, 3000, 5000, 10000])
        gpu = rng.choices(["A100_80GB", "A10_24GB"], weights=[0.3, 0.7])[0]
        hr_per_kstep = {"A100_80GB": 1/8.46, "A10_24GB": 1/2.35}[gpu]
        jobs.append(TrainingJob(
            job_id=f"job-{i+1:03d}",
            partner=rng.choice(partners),
            task=rng.choice(tasks),
            n_steps=steps,
            batch_size=rng.choice([16, 32, 64]),
            gpu_type=gpu,
            submitted_at_hr=rng.uniform(0, 24),
            is_urgent=rng.random() < 0.15,
            estimated_hr=steps / 1000 * hr_per_kstep,
        ))
    return jobs


# ── Optimization analysis ─────────────────────────────────────────────────────

def analyze(jobs: list[TrainingJob]) -> dict:
    # Baseline cost (all on-demand, submitted time)
    baseline_cost = sum(
        j.estimated_hr * RATES[j.gpu_type]["on_demand"]
        for j in jobs
    )

    # Strategy 1: Spot instances for non-urgent jobs
    spot_eligible = [j for j in jobs if not j.is_urgent]
    spot_savings = sum(
        j.estimated_hr * (RATES[j.gpu_type]["on_demand"] - RATES[j.gpu_type]["spot"])
        * (1 - RATES[j.gpu_type]["preempt_rate"] * 1.5)   # account for retries
        for j in spot_eligible
    )

    # Strategy 2: Off-peak scheduling (defer peak-hour jobs)
    peak_jobs = [j for j in jobs if 8 <= j.submitted_at_hr <= 22 and not j.is_urgent]
    offpeak_savings = sum(
        j.estimated_hr * RATES[j.gpu_type]["on_demand"] * OFF_PEAK_DISCOUNT
        for j in peak_jobs
    )

    # Strategy 3: Use A10 instead of A100 for small jobs (<=2000 steps)
    downgrade_eligible = [j for j in jobs if j.n_steps <= 2000 and j.gpu_type == "A100_80GB"]
    downgrade_savings = sum(
        j.estimated_hr * (RATES["A100_80GB"]["on_demand"] - RATES["A10_24GB"]["on_demand"])
        for j in downgrade_eligible
    )

    # Strategy 4: Batch coalescing (merge small jobs same task/partner)
    from itertools import groupby
    small_jobs = sorted([j for j in jobs if j.n_steps <= 1000],
                        key=lambda j: (j.partner, j.task))
    coalesce_groups = []
    for _, grp in groupby(small_jobs, key=lambda j: (j.partner, j.task)):
        grp = list(grp)
        if len(grp) >= 2:
            coalesce_groups.append(grp)
    # Save ~20% overhead per coalesced batch
    coalesce_savings = sum(
        sum(j.estimated_hr for j in grp) * RATES[grp[0].gpu_type]["on_demand"] * 0.20
        for grp in coalesce_groups
    )

    # Combined (non-additive — overlap)
    combined_savings = spot_savings + offpeak_savings * 0.4 + downgrade_savings + coalesce_savings
    combined_savings = min(combined_savings, baseline_cost * 0.45)   # cap at 45%

    strategies: list[OptimizationStrategy] = [
        OptimizationStrategy(
            "spot_instances",
            f"Use OCI spot/preemptible for {len(spot_eligible)} non-urgent jobs",
            round(spot_savings / baseline_cost * 100, 1),
            len(spot_eligible),
            "medium",
        ),
        OptimizationStrategy(
            "off_peak_scheduling",
            f"Defer {len(peak_jobs)} peak-hour jobs to 10pm–6am window",
            round(offpeak_savings / baseline_cost * 100, 1),
            len(peak_jobs),
            "low",
        ),
        OptimizationStrategy(
            "gpu_downgrade",
            f"Run {len(downgrade_eligible)} small jobs (≤2k steps) on A10 instead of A100",
            round(downgrade_savings / baseline_cost * 100, 1),
            len(downgrade_eligible),
            "low",
        ),
        OptimizationStrategy(
            "batch_coalescing",
            f"Merge {sum(len(g) for g in coalesce_groups)} small same-task jobs into batches",
            round(coalesce_savings / baseline_cost * 100, 1),
            sum(len(g) for g in coalesce_groups),
            "low",
        ),
    ]

    optimized_cost = baseline_cost - combined_savings
    total_savings_pct = combined_savings / baseline_cost * 100

    # GPU utilization by hour (mock)
    hourly = {h: 0.0 for h in range(24)}
    for j in jobs:
        h = int(j.submitted_at_hr) % 24
        hourly[h] += j.estimated_hr

    return {
        "n_jobs": len(jobs),
        "baseline_cost_usd": round(baseline_cost, 2),
        "optimized_cost_usd": round(optimized_cost, 2),
        "total_savings_usd": round(combined_savings, 2),
        "total_savings_pct": round(total_savings_pct, 1),
        "strategies": [
            {"name": s.name, "description": s.description,
             "savings_pct": s.savings_pct, "applicable_jobs": s.applicable_jobs,
             "risk": s.risk}
            for s in strategies
        ],
        "hourly_load": hourly,
        "jobs": [
            {"id": j.job_id, "partner": j.partner, "gpu": j.gpu_type,
             "steps": j.n_steps, "cost": round(j.estimated_hr * RATES[j.gpu_type]["on_demand"], 4),
             "urgent": j.is_urgent}
            for j in jobs
        ],
    }


# ── HTML report ───────────────────────────────────────────────────────────────

def render_html(data: dict) -> str:
    strategies = data["strategies"]
    hourly = data["hourly_load"]

    # SVG: hourly load heatmap (bar chart by hour)
    w, h = 560, 100
    max_load = max(hourly.values()) or 1
    svg_hourly = f'<svg width="{w}" height="{h}" style="background:#0f172a;border-radius:8px">'
    bar_w = (w - 40) / 24 - 1
    for hr, load in hourly.items():
        bh = max(2, (load / max_load) * (h - 30))
        x = 20 + hr * ((w - 40) / 24)
        col = "#ef4444" if 8 <= hr <= 22 else "#22c55e"
        svg_hourly += (f'<rect x="{x:.1f}" y="{h-10-bh:.1f}" width="{bar_w:.1f}" '
                       f'height="{bh:.1f}" fill="{col}" rx="1" opacity="0.8"/>')
    # Label 0, 8, 18, 22
    for lbl, x_frac in [(0, 0), (8, 8/24), (18, 18/24), (22, 22/24)]:
        x = 20 + x_frac * (w - 40)
        svg_hourly += f'<text x="{x:.1f}" y="{h-1}" fill="#64748b" font-size="9">{lbl:02d}h</text>'
    svg_hourly += ('  <text x="22" y="12" fill="#ef4444" font-size="9">■ peak</text>'
                   '  <text x="70" y="12" fill="#22c55e" font-size="9">■ off-peak</text>')
    svg_hourly += '</svg>'

    # SVG: savings breakdown bar chart
    max_sp = max((s["savings_pct"] for s in strategies), default=1)
    w2, h2 = 400, 120
    svg_strat = f'<svg width="{w2}" height="{h2}" style="background:#0f172a;border-radius:8px">'
    bar_h = (h2 - 30) / len(strategies) - 4
    SCOLS = {"low": "#22c55e", "medium": "#f59e0b", "high": "#ef4444"}
    for i, s in enumerate(strategies):
        bw = max(4, s["savings_pct"] / max_sp * (w2 - 150))
        y = 15 + i * ((h2 - 20) / len(strategies))
        col = SCOLS[s["risk"]]
        svg_strat += (f'<rect x="130" y="{y:.1f}" width="{bw:.1f}" height="{bar_h:.1f}" '
                      f'fill="{col}" rx="2" opacity="0.8"/>')
        svg_strat += (f'<text x="128" y="{y + bar_h/2 + 3:.1f}" fill="#94a3b8" font-size="10" '
                      f'text-anchor="end">{s["name"].replace("_", " ")}</text>')
        svg_strat += (f'<text x="{133+bw:.1f}" y="{y + bar_h/2 + 3:.1f}" fill="{col}" '
                      f'font-size="10">{s["savings_pct"]:.1f}%</text>')
    svg_strat += '</svg>'

    rows = ""
    for s in sorted(strategies, key=lambda x: -x["savings_pct"]):
        risk_col = SCOLS[s["risk"]]
        rows += f"""<tr>
          <td style="color:#e2e8f0">{s['name'].replace('_', ' ')}</td>
          <td style="color:#22c55e">{s['savings_pct']:.1f}%</td>
          <td>{s['applicable_jobs']}</td>
          <td style="color:{risk_col}">{s['risk']}</td>
          <td style="color:#64748b;font-size:11px">{s['description']}</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>GPU Cost Optimizer</title>
<style>
body{{background:#1e293b;color:#e2e8f0;font-family:monospace;margin:0;padding:24px}}
h1{{color:#C74634;margin:0 0 4px}}
.meta{{color:#94a3b8;font-size:12px;margin-bottom:20px}}
.grid{{display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:12px;margin-bottom:20px}}
.card{{background:#0f172a;border-radius:8px;padding:14px}}
.card h3{{color:#94a3b8;font-size:11px;text-transform:uppercase;margin:0 0 4px}}
.big{{font-size:28px;font-weight:bold}}
.charts{{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:20px}}
table{{width:100%;border-collapse:collapse;font-size:12px}}
th{{color:#94a3b8;text-align:left;padding:5px 8px;border-bottom:1px solid #334155}}
td{{padding:4px 8px;border-bottom:1px solid #1e293b}}
</style></head>
<body>
<h1>GPU Cost Optimizer</h1>
<div class="meta">{data['n_jobs']} training jobs analyzed · OCI A100/A10 fleet</div>

<div class="grid">
  <div class="card"><h3>Baseline Cost</h3>
    <div class="big" style="color:#ef4444">${data['baseline_cost_usd']:.2f}</div></div>
  <div class="card"><h3>Optimized Cost</h3>
    <div class="big" style="color:#22c55e">${data['optimized_cost_usd']:.2f}</div></div>
  <div class="card"><h3>Total Savings</h3>
    <div class="big" style="color:#22c55e">${data['total_savings_usd']:.2f}</div></div>
  <div class="card"><h3>Savings %</h3>
    <div class="big" style="color:#22c55e">{data['total_savings_pct']:.1f}%</div></div>
</div>

<div class="charts">
  <div>
    <h3 style="color:#94a3b8;font-size:11px;text-transform:uppercase;margin-bottom:8px">Savings by Strategy</h3>
    {svg_strat}
  </div>
  <div>
    <h3 style="color:#94a3b8;font-size:11px;text-transform:uppercase;margin-bottom:8px">Job Submission by Hour</h3>
    {svg_hourly}
    <div style="color:#64748b;font-size:11px;margin-top:4px">Red = peak (8am–10pm), Green = off-peak</div>
  </div>
</div>

<table>
  <tr><th>Strategy</th><th>Savings</th><th>Jobs</th><th>Risk</th><th>Description</th></tr>
  {rows}
</table>

<div style="color:#64748b;font-size:11px;margin-top:16px">
  Priority: spot_instances + off_peak_scheduling → {data['total_savings_pct']:.1f}% total savings.<br>
  OCI spot A10: $0.52/hr vs $1.50 on-demand. OCI spot A100: $1.47/hr vs $4.20 on-demand.
</div>
</body></html>"""


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="GPU cost optimization for OCI Robot Cloud")
    parser.add_argument("--mock",   action="store_true", default=True)
    parser.add_argument("--jobs",   type=int, default=30)
    parser.add_argument("--output", default="/tmp/gpu_cost_optimizer.html")
    parser.add_argument("--seed",   type=int, default=42)
    args = parser.parse_args()

    print(f"[gpu-cost-optimizer] Analyzing {args.jobs} training jobs...")
    t0 = time.time()

    jobs = generate_jobs(args.jobs, args.seed)
    data = analyze(jobs)

    print(f"\n  Baseline: ${data['baseline_cost_usd']:.2f}")
    print(f"  Optimized: ${data['optimized_cost_usd']:.2f}")
    print(f"  Savings: ${data['total_savings_usd']:.2f} ({data['total_savings_pct']:.1f}%)\n")
    for s in sorted(data["strategies"], key=lambda x: -x["savings_pct"]):
        print(f"  [{s['risk']:6s}] {s['name']:<25} {s['savings_pct']:5.1f}%  {s['description']}")

    print(f"\n  [{time.time()-t0:.1f}s]\n")

    html = render_html(data)
    Path(args.output).write_text(html)
    print(f"  HTML → {args.output}")

    json_out = Path(args.output).with_suffix(".json")
    json_out.write_text(json.dumps(data, indent=2))
    print(f"  JSON → {json_out}")


if __name__ == "__main__":
    main()
