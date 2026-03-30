#!/usr/bin/env python3
"""
api_rate_limiter.py — API rate limiting and quota management for OCI Robot Cloud services.

Simulates and analyzes rate limiting behavior across the 15+ API services (ports 8001-8020).
Models token bucket, sliding window, and leaky bucket algorithms; recommends limits per tier.

Usage:
    python src/infra/api_rate_limiter.py --mock --output /tmp/api_rate_limiter.html
"""

import argparse
import json
import math
import random
import time
from dataclasses import dataclass, field
from pathlib import Path


# ── Service definitions ────────────────────────────────────────────────────────

SERVICES = [
    # (name, port, category, cost_per_call, default_rps_limit)
    ("groot_inference",    8001, "inference",  0.0043, 10.0),
    ("data_ingest",        8003, "data",       0.0001,  5.0),
    ("finetune_launch",    8005, "training",   0.15,    0.5),
    ("eval_runner",        8006, "eval",       0.02,    2.0),
    ("checkpoint_manager", 8008, "storage",    0.001,   3.0),
    ("sdg_generator",      8010, "simulation", 0.008,   1.0),
    ("dagger_controller",  8012, "training",   0.05,    1.0),
    ("metrics_collector",  8015, "monitoring", 0.0001, 20.0),
    ("model_registry",     8018, "registry",   0.0005,  5.0),
    ("billing_api",        8020, "billing",    0.0001,  2.0),
]

PARTNER_TIERS = [
    # (tier, rps_multiplier, burst_multiplier, monthly_quota_calls, overage_rate)
    ("pilot",      0.5,  2.0,  10_000,  0.001),
    ("growth",     1.0,  3.0,  50_000,  0.0008),
    ("enterprise", 3.0,  5.0, 500_000, 0.0005),
]

ALGORITHMS = ["token_bucket", "sliding_window", "leaky_bucket", "fixed_window"]


@dataclass
class RateLimitResult:
    service: str
    port: int
    category: str
    algorithm: str
    tier: str
    requests_sent: int
    requests_accepted: int
    requests_throttled: int
    acceptance_rate: float
    avg_wait_ms: float
    burst_handled: bool
    cost_saved: float    # cost of throttled requests (prevented overload)


@dataclass
class QuotaAnalysis:
    tier: str
    monthly_quota: int
    avg_daily_usage: int
    peak_daily_usage: int
    quota_utilization: float
    overage_days: int
    overage_cost: float
    recommendation: str


@dataclass
class RateLimiterReport:
    total_simulated_calls: int
    overall_acceptance_rate: float
    best_algorithm: str
    results: list[RateLimitResult] = field(default_factory=list)
    quota_analyses: list[QuotaAnalysis] = field(default_factory=list)


# ── Simulation ─────────────────────────────────────────────────────────────────

def simulate_token_bucket(rps_limit: float, burst: float, n_requests: int,
                           arrival_rate: float, rng: random.Random) -> tuple[int, int, float]:
    """Returns (accepted, throttled, avg_wait_ms)."""
    tokens = burst
    accepted = throttled = 0
    total_wait = 0.0
    dt = 1.0 / arrival_rate  # time between requests

    for _ in range(n_requests):
        tokens = min(burst, tokens + rps_limit * dt)
        if tokens >= 1.0:
            tokens -= 1.0
            accepted += 1
        else:
            throttled += 1
            wait = (1.0 - tokens) / rps_limit * 1000  # ms
            total_wait += wait

    avg_wait = total_wait / max(1, throttled)
    return accepted, throttled, avg_wait


def simulate_sliding_window(rps_limit: float, n_requests: int,
                             arrival_rate: float, rng: random.Random) -> tuple[int, int, float]:
    """Sliding window counter per second."""
    accepted = throttled = 0
    total_wait = 0.0
    window: list[float] = []
    t = 0.0
    window_size = 1.0

    for _ in range(n_requests):
        t += 1.0 / arrival_rate
        # Remove old entries
        window = [ts for ts in window if ts > t - window_size]
        if len(window) < rps_limit:
            window.append(t)
            accepted += 1
        else:
            throttled += 1
            total_wait += rng.uniform(50, 200)

    return accepted, throttled, total_wait / max(1, throttled)


def simulate_rate_limiter(seed: int = 42) -> RateLimiterReport:
    rng = random.Random(seed)
    results = []
    total_calls = 0
    total_accepted = 0

    for svc_name, port, cat, cost, default_rps in SERVICES:
        for tier_name, rps_mult, burst_mult, _, _ in PARTNER_TIERS:
            rps_limit = default_rps * rps_mult
            burst = rps_limit * burst_mult
            n_requests = rng.randint(80, 150)
            # Arrival rate slightly above limit to test throttling
            arrival_rate = rps_limit * rng.uniform(1.1, 1.8)

            for algo in ALGORITHMS[:2]:  # just token_bucket and sliding_window for brevity
                if algo == "token_bucket":
                    acc, thr, wait = simulate_token_bucket(rps_limit, burst, n_requests, arrival_rate, rng)
                else:
                    acc, thr, wait = simulate_sliding_window(rps_limit, n_requests, arrival_rate, rng)

                acceptance = acc / max(1, n_requests)
                cost_saved = thr * cost

                results.append(RateLimitResult(
                    service=svc_name, port=port, category=cat,
                    algorithm=algo, tier=tier_name,
                    requests_sent=n_requests,
                    requests_accepted=acc,
                    requests_throttled=thr,
                    acceptance_rate=round(acceptance, 4),
                    avg_wait_ms=round(wait, 1),
                    burst_handled=(acc > rps_limit * 0.8),
                    cost_saved=round(cost_saved, 4),
                ))

                total_calls += n_requests
                total_accepted += acc

    # Quota analysis per tier
    quota_analyses = []
    for tier_name, rps_mult, _, monthly_quota, overage_rate in PARTNER_TIERS:
        avg_daily = int(monthly_quota * rps_mult * 0.12)
        peak_daily = int(avg_daily * rng.uniform(1.8, 2.5))
        util = avg_daily * 30 / monthly_quota
        overage_days = max(0, int((util - 1.0) * 30)) if util > 1.0 else rng.randint(0, 3)
        overage_cost = overage_days * max(0, peak_daily - monthly_quota / 30) * overage_rate

        rec = ("Increase quota tier" if util > 0.90 else
               "Quota appropriate" if util > 0.50 else
               "Consider downgrading tier")

        quota_analyses.append(QuotaAnalysis(
            tier=tier_name, monthly_quota=monthly_quota,
            avg_daily_usage=avg_daily, peak_daily_usage=peak_daily,
            quota_utilization=round(util, 3),
            overage_days=overage_days, overage_cost=round(overage_cost, 2),
            recommendation=rec,
        ))

    # Best algorithm: token_bucket generally better for bursty traffic
    tb_results = [r for r in results if r.algorithm == "token_bucket"]
    sw_results = [r for r in results if r.algorithm == "sliding_window"]
    avg_acc_tb = sum(r.acceptance_rate for r in tb_results) / len(tb_results) if tb_results else 0
    avg_acc_sw = sum(r.acceptance_rate for r in sw_results) / len(sw_results) if sw_results else 0
    best_algo = "token_bucket" if avg_acc_tb >= avg_acc_sw else "sliding_window"

    return RateLimiterReport(
        total_simulated_calls=total_calls,
        overall_acceptance_rate=round(total_accepted / max(1, total_calls), 4),
        best_algorithm=best_algo,
        results=results,
        quota_analyses=quota_analyses,
    )


# ── HTML ───────────────────────────────────────────────────────────────────────

def render_html(report: RateLimiterReport) -> str:
    # Per-service acceptance rate (token_bucket, enterprise tier)
    svc_results = {r.service: r for r in report.results
                   if r.algorithm == "token_bucket" and r.tier == "growth"}

    w, h = 540, 180
    n = len(svc_results)
    bar_w = (w - 60) / n * 0.7
    gap   = (w - 60) / n

    svg_bars = f'<svg width="{w}" height="{h}" style="background:#0f172a;border-radius:8px">'
    svg_bars += f'<line x1="50" y1="{h-30}" x2="{w}" y2="{h-30}" stroke="#334155" stroke-width="1"/>'

    for i, (svc, r) in enumerate(svc_results.items()):
        x = 50 + i * gap + gap * 0.15
        bh = r.acceptance_rate * (h - 50)
        col = "#22c55e" if r.acceptance_rate >= 0.80 else "#f59e0b" if r.acceptance_rate >= 0.60 else "#ef4444"
        svg_bars += (f'<rect x="{x:.1f}" y="{h-30-bh:.1f}" width="{bar_w:.1f}" '
                     f'height="{bh:.1f}" fill="{col}" opacity="0.85" rx="2"/>')
        svg_bars += (f'<text x="{x+bar_w/2:.1f}" y="{h-15}" fill="#64748b" font-size="7.5" '
                     f'text-anchor="middle" transform="rotate(-40,{x+bar_w/2:.1f},{h-15})">'
                     f'{svc.replace("_"," ")}</text>')

    svg_bars += '</svg>'

    # Table: by algorithm comparison
    algo_summary: dict[str, list] = {}
    for r in report.results:
        algo_summary.setdefault(r.algorithm, []).append(r.acceptance_rate)
    algo_rows = ""
    for algo, rates in sorted(algo_summary.items()):
        avg = sum(rates) / len(rates)
        col = "#22c55e" if avg >= 0.75 else "#f59e0b"
        algo_rows += (f'<tr><td style="color:#e2e8f0">{algo.replace("_"," ")}</td>'
                      f'<td style="color:{col}">{avg*100:.1f}%</td>'
                      f'<td style="color:#64748b">{len(rates)}</td></tr>')

    # Quota analysis rows
    quota_rows = ""
    for q in report.quota_analyses:
        util_col = "#ef4444" if q.quota_utilization > 0.90 else "#f59e0b" if q.quota_utilization > 0.70 else "#22c55e"
        tier_col = {"pilot": "#f59e0b", "growth": "#3b82f6", "enterprise": "#a855f7"}.get(q.tier, "#94a3b8")
        quota_rows += (f'<tr>'
                       f'<td style="color:{tier_col};font-weight:bold">{q.tier}</td>'
                       f'<td style="color:#94a3b8">{q.monthly_quota:,}</td>'
                       f'<td style="color:#e2e8f0">{q.avg_daily_usage:,}</td>'
                       f'<td style="color:#64748b">{q.peak_daily_usage:,}</td>'
                       f'<td style="color:{util_col}">{q.quota_utilization*100:.0f}%</td>'
                       f'<td style="color:#f59e0b">{q.overage_days}d</td>'
                       f'<td style="color:#ef4444">${q.overage_cost:.2f}</td>'
                       f'<td style="color:#64748b;font-size:10px">{q.recommendation}</td>'
                       f'</tr>')

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>API Rate Limiter</title>
<style>
body{{background:#1e293b;color:#e2e8f0;font-family:monospace;margin:0;padding:24px}}
h1{{color:#C74634;margin:0 0 4px}}
.meta{{color:#94a3b8;font-size:12px;margin-bottom:20px}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:20px}}
.card{{background:#0f172a;border-radius:8px;padding:14px}}
.card h3{{color:#94a3b8;font-size:11px;text-transform:uppercase;margin:0 0 4px}}
.big{{font-size:26px;font-weight:bold}}
.charts{{display:grid;grid-template-columns:2fr 1fr;gap:12px;margin-bottom:20px}}
table{{width:100%;border-collapse:collapse;font-size:11px;margin-bottom:20px}}
th{{color:#94a3b8;text-align:left;padding:5px 8px;border-bottom:1px solid #334155}}
td{{padding:3px 8px;border-bottom:1px solid #1e293b}}
h3.sec{{color:#94a3b8;font-size:11px;text-transform:uppercase;margin-bottom:8px}}
</style></head>
<body>
<h1>API Rate Limiter</h1>
<div class="meta">
  {len(SERVICES)} services · {len(PARTNER_TIERS)} tiers · {len(ALGORITHMS[:2])} algorithms ·
  {report.total_simulated_calls:,} simulated calls
</div>

<div class="grid">
  <div class="card"><h3>Acceptance Rate</h3>
    <div class="big" style="color:#22c55e">{report.overall_acceptance_rate*100:.1f}%</div>
  </div>
  <div class="card"><h3>Best Algorithm</h3>
    <div style="color:#3b82f6;font-size:16px;font-weight:bold">{report.best_algorithm.replace("_"," ")}</div>
  </div>
  <div class="card"><h3>Services</h3>
    <div class="big" style="color:#94a3b8">{len(SERVICES)}</div>
    <div style="color:#64748b;font-size:10px">ports 8001–8020</div>
  </div>
  <div class="card"><h3>Tiers</h3>
    <div class="big" style="color:#a855f7">{len(PARTNER_TIERS)}</div>
    <div style="color:#64748b;font-size:10px">pilot/growth/enterprise</div>
  </div>
</div>

<div class="charts">
  <div>
    <h3 class="sec">Acceptance Rate by Service (growth tier, token bucket)</h3>
    {svg_bars}
    <div style="color:#64748b;font-size:10px;margin-top:4px">
      Green ≥80% · Yellow ≥60% · Red &lt;60% acceptance
    </div>
  </div>
  <div>
    <h3 class="sec">Algorithm Comparison</h3>
    <table>
      <tr><th>Algorithm</th><th>Avg Accept</th><th>Samples</th></tr>
      {algo_rows}
    </table>
    <div style="color:#64748b;font-size:10px;margin-top:8px">
      Token bucket handles bursts best. Sliding window more accurate at steady state.
    </div>
  </div>
</div>

<h3 class="sec">Quota Analysis by Tier</h3>
<table>
  <tr><th>Tier</th><th>Monthly Quota</th><th>Avg Daily</th><th>Peak Daily</th>
      <th>Utilization</th><th>Overage Days</th><th>Overage Cost</th><th>Recommendation</th></tr>
  {quota_rows}
</table>

<div style="background:#0f172a;border-radius:8px;padding:12px;margin-top:12px">
  <div style="color:#C74634;font-size:11px;font-weight:bold;margin-bottom:6px">
    RATE LIMIT SETTINGS BY TIER
  </div>
  <div style="font-size:10px;color:#94a3b8;line-height:1.8">
    Pilot: 0.5× base RPS · 2× burst · 10K calls/mo<br>
    Growth: 1.0× base RPS · 3× burst · 50K calls/mo<br>
    Enterprise: 3.0× base RPS · 5× burst · 500K calls/mo<br>
    groot_inference: 5/10/30 RPS (pilot/growth/enterprise) · burst 10/30/150<br>
    finetune_launch: 0.25/0.5/1.5 RPS (prevents job queue overflow)
  </div>
</div>
</body></html>"""


# ── CLI ────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="API rate limiter for OCI Robot Cloud")
    parser.add_argument("--mock",   action="store_true", default=True)
    parser.add_argument("--output", default="/tmp/api_rate_limiter.html")
    parser.add_argument("--seed",   type=int, default=42)
    args = parser.parse_args()

    print(f"[rate-limiter] {len(SERVICES)} services · {len(ALGORITHMS[:2])} algorithms · {len(PARTNER_TIERS)} tiers")
    t0 = time.time()

    report = simulate_rate_limiter(args.seed)

    print(f"\n  {'Service':<25} {'Accept%':>8} {'Throttled':>10}  Wait(ms)")
    print(f"  {'─'*25} {'─'*8} {'─'*10}  {'─'*8}")
    tb_growth = {r.service: r for r in report.results
                 if r.algorithm == "token_bucket" and r.tier == "growth"}
    for svc, r in tb_growth.items():
        print(f"  {svc:<25} {r.acceptance_rate*100:>7.1f}% {r.requests_throttled:>10}  {r.avg_wait_ms:>6.1f}")

    print(f"\n  Overall acceptance: {report.overall_acceptance_rate*100:.1f}%")
    print(f"  Best algorithm: {report.best_algorithm}")
    print(f"  [{time.time()-t0:.1f}s]\n")

    html = render_html(report)
    Path(args.output).write_text(html)
    print(f"  HTML → {args.output}")

    json_out = Path(args.output).with_suffix(".json")
    json_out.write_text(json.dumps({
        "total_simulated_calls": report.total_simulated_calls,
        "overall_acceptance_rate": report.overall_acceptance_rate,
        "best_algorithm": report.best_algorithm,
        "quota_analyses": [{"tier": q.tier, "utilization": q.quota_utilization,
                             "overage_cost": q.overage_cost} for q in report.quota_analyses],
    }, indent=2))
    print(f"  JSON → {json_out}")


if __name__ == "__main__":
    main()
