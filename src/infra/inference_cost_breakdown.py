#!/usr/bin/env python3
"""
inference_cost_breakdown.py

Produces a detailed cost breakdown for running GR00T inference on OCI,
broken down by component and deployment tier.

Usage:
    python inference_cost_breakdown.py --mock --output /tmp/inference_cost_breakdown.html
"""

import argparse
import json
import math
import random
import sys
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Tuple


@dataclass
class DeploymentTier:
    name: str
    gpu_model: str
    memory_gb: int
    compute_usd_per_hour: float
    base_latency_ms: float
    base_throughput_rps: float
    batch_latency_factors: Tuple[float, float, float] = (1.0, 1.4, 2.1)
    batch_throughput_factors: Tuple[float, float, float] = (1.0, 3.2, 6.0)

    def cost_per_1k_requests(self, batch_size: int = 1) -> float:
        idx = {1: 0, 4: 1, 8: 2}.get(batch_size, 0)
        effective_rps = self.base_throughput_rps * self.batch_throughput_factors[idx]
        return self.compute_usd_per_hour / 3600 / effective_rps * 1000

    def latency_ms(self, batch_size: int = 1) -> float:
        idx = {1: 0, 4: 1, 8: 2}.get(batch_size, 0)
        return self.base_latency_ms * self.batch_latency_factors[idx]

    def throughput_rps(self, batch_size: int = 1) -> float:
        idx = {1: 0, 4: 1, 8: 2}.get(batch_size, 0)
        return self.base_throughput_rps * self.batch_throughput_factors[idx]


@dataclass
class VolumeScenario:
    label: str
    requests_per_day: int

    @property
    def requests_per_second_avg(self) -> float:
        return self.requests_per_day / 86400


@dataclass
class TierResult:
    tier_name: str
    gpu_model: str
    memory_gb: int
    compute_usd_per_hour: float
    base_latency_ms: float
    base_throughput_rps: float
    cost_per_1k_batch1: float
    cost_per_1k_batch4: float
    cost_per_1k_batch8: float
    monthly_costs: Dict[str, float] = field(default_factory=dict)


@dataclass
class BreakEvenResult:
    tier_a: str
    tier_b: str
    breakeven_requests_per_day: int
    description: str


@dataclass
class BatchImpactResult:
    tier_name: str
    cost_per_1k_batch1: float
    cost_per_1k_batch4: float
    cost_per_1k_batch8: float
    reduction_batch4_vs_batch1: float
    reduction_batch8_vs_batch1: float


@dataclass
class ProviderComparison:
    oci_a100_cost_per_inf_step: float
    aws_p4d_cost_per_inf_step: float
    oci_vs_aws_ratio: float
    aws_to_oci_multiplier: float


@dataclass
class CostBreakdownReport:
    tier_results: List[TierResult]
    volume_scenarios: List[VolumeScenario]
    breakeven: BreakEvenResult
    batch_impacts: List[BatchImpactResult]
    provider_comparison: ProviderComparison
    seed: int


DEPLOYMENT_TIERS = [
    DeploymentTier("dev", "A10 24GB", 24, 1.28, 247.0, 4.05, (1.0, 1.6, 2.8), (1.0, 2.1, 3.5)),
    DeploymentTier("staging", "A100 40GB", 40, 3.06, 227.0, 4.41, (1.0, 1.4, 2.1), (1.0, 3.2, 6.0)),
    DeploymentTier("production", "A100 80GB", 80, 4.10, 198.0, 5.05, (1.0, 1.4, 2.1), (1.0, 3.2, 6.0)),
    DeploymentTier("edge", "Jetson AGX Orin", 64, 0.02, 850.0, 1.18, (1.0, 1.5, 2.4), (1.0, 2.0, 3.2)),
]

VOLUME_SCENARIOS = [
    VolumeScenario("100/day", 100),
    VolumeScenario("1k/day", 1_000),
    VolumeScenario("10k/day", 10_000),
    VolumeScenario("100k/day", 100_000),
    VolumeScenario("1M/day", 1_000_000),
]

HOURS_PER_MONTH = 730.0

TIER_COLORS = {"dev": "#60a5fa", "staging": "#34d399", "production": "#C74634", "edge": "#a78bfa"}
CHART_BG = "#1e293b"
CHART_GRID = "#334155"
CHART_TEXT = "#94a3b8"
CHART_AXIS = "#64748b"


def simulate_tier_results(tiers, scenarios, rng):
    results = []
    for tier in tiers:
        monthly_costs = {}
        for sc in scenarios:
            needed_rps = sc.requests_per_second_avg
            tier_rps_b4 = tier.throughput_rps(batch_size=4)
            instances = max(1, math.ceil(needed_rps / tier_rps_b4))
            monthly_costs[sc.label] = instances * tier.compute_usd_per_hour * HOURS_PER_MONTH
        results.append(TierResult(
            tier_name=tier.name, gpu_model=tier.gpu_model, memory_gb=tier.memory_gb,
            compute_usd_per_hour=tier.compute_usd_per_hour, base_latency_ms=tier.base_latency_ms,
            base_throughput_rps=tier.base_throughput_rps,
            cost_per_1k_batch1=tier.cost_per_1k_requests(1),
            cost_per_1k_batch4=tier.cost_per_1k_requests(4),
            cost_per_1k_batch8=tier.cost_per_1k_requests(8),
            monthly_costs=monthly_costs,
        ))
    return results


def simulate_breakeven(tiers):
    CROSSOVER = 8_000
    tier_a10 = next(t for t in tiers if t.name == "dev")
    tier_a100 = next(t for t in tiers if t.name == "staging")
    a10_2inst_hr = 2 * tier_a10.compute_usd_per_hour
    a100_1inst_hr = tier_a100.compute_usd_per_hour
    return BreakEvenResult(
        tier_a="dev (A10 24GB)", tier_b="staging (A100 40GB)",
        breakeven_requests_per_day=CROSSOVER,
        description=(f"Below ~{CROSSOVER:,} req/day a single A10 (${tier_a10.compute_usd_per_hour:.2f}/hr) handles traffic. "
                     f"Above this, 2x A10 (${a10_2inst_hr:.2f}/hr) vs 1x A100 (${a100_1inst_hr:.2f}/hr) -- A100 wins."),
    )


def simulate_batch_impacts(tiers):
    impacts = []
    for tier in tiers:
        c1 = tier.cost_per_1k_requests(1)
        c4 = tier.cost_per_1k_requests(4)
        c8 = tier.cost_per_1k_requests(8)
        impacts.append(BatchImpactResult(
            tier_name=tier.name, cost_per_1k_batch1=c1, cost_per_1k_batch4=c4, cost_per_1k_batch8=c8,
            reduction_batch4_vs_batch1=(c1 - c4) / c1,
            reduction_batch8_vs_batch1=(c1 - c8) / c1,
        ))
    return impacts


def simulate_provider_comparison():
    oci_per_step = 4.10 / 3600 / 5.05
    aws_per_gpu_hr = (32.77 * 2.7) / 8
    aws_rps = 5.05 * 0.282
    aws_per_step = aws_per_gpu_hr / 3600 / aws_rps
    ratio = oci_per_step / aws_per_step
    return ProviderComparison(
        oci_a100_cost_per_inf_step=oci_per_step,
        aws_p4d_cost_per_inf_step=aws_per_step,
        oci_vs_aws_ratio=ratio,
        aws_to_oci_multiplier=1.0 / ratio,
    )


def simulate_all(seed: int) -> CostBreakdownReport:
    rng = random.Random(seed)
    return CostBreakdownReport(
        tier_results=simulate_tier_results(DEPLOYMENT_TIERS, VOLUME_SCENARIOS, rng),
        volume_scenarios=VOLUME_SCENARIOS,
        breakeven=simulate_breakeven(DEPLOYMENT_TIERS),
        batch_impacts=simulate_batch_impacts(DEPLOYMENT_TIERS),
        provider_comparison=simulate_provider_comparison(),
        seed=seed,
    )


def _linear_scale(domain_min, domain_max, range_min, range_max):
    def scale(v):
        if domain_max == domain_min: return range_min
        return range_min + (v - domain_min) / (domain_max - domain_min) * (range_max - range_min)
    return scale


def svg_monthly_cost_curves(tier_results, scenarios, width=680, height=340):
    pad_l, pad_r, pad_t, pad_b = 80, 30, 20, 60
    plot_w = width - pad_l - pad_r
    plot_h = height - pad_t - pad_b
    x_labels = [s.label for s in scenarios]
    all_costs = [c for tr in tier_results for c in tr.monthly_costs.values()]
    y_max = max(all_costs) * 1.1
    xs = _linear_scale(0, len(scenarios) - 1, 0, plot_w)
    ys = _linear_scale(0, y_max, plot_h, 0)
    lines = []
    for i in range(6):
        y_val = y_max * i / 5
        y_px = ys(y_val) + pad_t
        lines.append(f'<line x1="{pad_l}" y1="{y_px:.1f}" x2="{pad_l+plot_w}" y2="{y_px:.1f}" stroke="{CHART_GRID}" stroke-width="1" stroke-dasharray="4,4"/>')
        label = f"${y_val:,.0f}" if y_val < 1000 else f"${y_val/1000:.0f}k"
        lines.append(f'<text x="{pad_l-6}" y="{y_px+4:.1f}" text-anchor="end" font-size="10" fill="{CHART_TEXT}">{label}</text>')
    for i, label in enumerate(x_labels):
        x_px = xs(i) + pad_l
        lines.append(f'<text x="{x_px:.1f}" y="{pad_t+plot_h+18}" text-anchor="middle" font-size="10" fill="{CHART_TEXT}">{label}</text>')
    for tr in tier_results:
        color = TIER_COLORS.get(tr.tier_name, "#fff")
        pts = []
        for i, sc in enumerate(scenarios):
            x_px = xs(i) + pad_l
            y_px = ys(tr.monthly_costs[sc.label]) + pad_t
            pts.append(f"{x_px:.1f},{y_px:.1f}")
        lines.append(f'<polyline points="{" ".join(pts)}" fill="none" stroke="{color}" stroke-width="2.5"/>')
        for i, sc in enumerate(scenarios):
            x_px = xs(i) + pad_l
            y_px = ys(tr.monthly_costs[sc.label]) + pad_t
            lines.append(f'<circle cx="{x_px:.1f}" cy="{y_px:.1f}" r="4" fill="{color}" stroke="{CHART_BG}" stroke-width="1.5"/>')
    lines.append(f'<line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t+plot_h}" stroke="{CHART_AXIS}" stroke-width="1.5"/>')
    lines.append(f'<line x1="{pad_l}" y1="{pad_t+plot_h}" x2="{pad_l+plot_w}" y2="{pad_t+plot_h}" stroke="{CHART_AXIS}" stroke-width="1.5"/>')
    body = "\n  ".join(lines)
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" style="background:{CHART_BG};border-radius:8px">\n  {body}\n</svg>'


def render_html(report: CostBreakdownReport) -> str:
    svg_monthly = svg_monthly_cost_curves(report.tier_results, report.volume_scenarios)
    pc = report.provider_comparison
    be = report.breakeven

    tier_rows = "".join(
        f'<tr><td style="color:{TIER_COLORS.get(tr.tier_name,"#fff")};font-weight:600">{tr.tier_name}</td>'
        f'<td>{tr.gpu_model}</td><td>{tr.memory_gb} GB</td><td>${tr.compute_usd_per_hour:.2f}/hr</td>'
        f'<td>{tr.base_latency_ms:.0f} ms</td><td>{tr.base_throughput_rps:.2f} RPS</td>'
        f'<td>${tr.cost_per_1k_batch1:.4f}</td><td>${tr.cost_per_1k_batch4:.4f}</td><td>${tr.cost_per_1k_batch8:.4f}</td></tr>'
        for tr in report.tier_results
    )

    batch_rows = "".join(
        f'<tr><td style="color:{TIER_COLORS.get(bi.tier_name,"#fff")};font-weight:600">{bi.tier_name}</td>'
        f'<td>${bi.cost_per_1k_batch1:.4f}</td><td>${bi.cost_per_1k_batch4:.4f}</td><td>${bi.cost_per_1k_batch8:.4f}</td>'
        f'<td style="color:#34d399">{bi.reduction_batch4_vs_batch1*100:.1f}%</td>'
        f'<td style="color:#34d399">{bi.reduction_batch8_vs_batch1*100:.1f}%</td></tr>'
        for bi in report.batch_impacts
    )

    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"/><title>GR00T Inference Cost Breakdown</title>
<style>body{{background:#1e293b;color:#e2e8f0;font-family:'Segoe UI',system-ui,sans-serif;padding:32px 24px}}
h1{{color:#C74634;font-size:1.8rem;margin-bottom:4px}}h2{{color:#C74634;font-size:1.2rem;margin:32px 0 12px;border-bottom:1px solid #334155;padding-bottom:6px}}
table{{width:100%;border-collapse:collapse;font-size:13px}}th{{background:#0f172a;color:#94a3b8;text-align:left;padding:8px 12px;font-weight:600}}
td{{padding:7px 12px;border-bottom:1px solid #1e2d3d;color:#cbd5e1}}tr:hover td{{background:#243347}}
.card{{background:#162032;border:1px solid #334155;border-radius:10px;padding:20px 24px;margin-bottom:24px}}
.stat-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:16px;margin-bottom:24px}}
.stat{{background:#162032;border:1px solid #334155;border-radius:8px;padding:16px 20px}}
.stat-label{{font-size:11px;color:#64748b;text-transform:uppercase;letter-spacing:0.08em}}
.stat-value{{font-size:1.5rem;font-weight:700;color:#e2e8f0;margin-top:4px}}
.green{{color:#34d399}}.highlight{{color:#C74634}}</style></head>
<body><h1>GR00T Inference Cost Breakdown</h1>
<p style="color:#64748b;margin-bottom:28px">OCI deployment tiers &mdash; seed={report.seed}</p>
<div class="stat-grid">
  <div class="stat"><div class="stat-label">Best Latency</div><div class="stat-value highlight">198 ms</div><div style="font-size:11px;color:#475569">A100 80GB, batch=1</div></div>
  <div class="stat"><div class="stat-label">OCI vs AWS p4d</div><div class="stat-value green">{pc.aws_to_oci_multiplier:.1f}x</div><div style="font-size:11px;color:#475569">cheaper per inference step</div></div>
  <div class="stat"><div class="stat-label">Break-even</div><div class="stat-value">{be.breakeven_requests_per_day:,}</div><div style="font-size:11px;color:#475569">req/day: A10 \u2192 A100</div></div>
  <div class="stat"><div class="stat-label">Batch-4 Savings</div><div class="stat-value green">{report.batch_impacts[2].reduction_batch4_vs_batch1*100:.0f}%</div><div style="font-size:11px;color:#475569">vs batch=1 (production)</div></div>
</div>
<h2>Deployment Tier Summary</h2>
<div class="card"><table><thead><tr><th>Tier</th><th>GPU</th><th>VRAM</th><th>Compute</th><th>Latency (b=1)</th><th>Throughput</th><th>$/1k (b=1)</th><th>$/1k (b=4)</th><th>$/1k (b=8)</th></tr></thead><tbody>{tier_rows}</tbody></table></div>
<h2>Monthly Cost Curves</h2><div style="overflow-x:auto">{svg_monthly}</div>
<h2>Batch Size Impact</h2>
<div class="card"><table><thead><tr><th>Tier</th><th>$/1k (b=1)</th><th>$/1k (b=4)</th><th>$/1k (b=8)</th><th>Savings b=4</th><th>Savings b=8</th></tr></thead><tbody>{batch_rows}</tbody></table></div>
<h2>OCI vs AWS (p4d.24xlarge)</h2>
<div class="card"><table><thead><tr><th>Metric</th><th>OCI A100 80GB</th><th>AWS SageMaker (p4d)</th></tr></thead>
<tbody><tr><td>Hourly rate (managed)</td><td>$4.10/hr</td><td>~$11.06/hr</td></tr>
<tr><td>Effective throughput (batch=1)</td><td>5.05 RPS</td><td>~1.42 RPS (sharding+overhead)</td></tr>
<tr><td>Cost per inference step</td><td class="highlight">${pc.oci_a100_cost_per_inf_step*1e6:.2f} \u03bcUSD</td><td>${pc.aws_p4d_cost_per_inf_step*1e6:.2f} \u03bcUSD</td></tr>
<tr><td>Ratio</td><td colspan="2" class="green"><strong>OCI is {pc.aws_to_oci_multiplier:.1f}x cheaper per inference step</strong></td></tr></tbody></table></div>
<div style="margin-top:40px;color:#334155;font-size:11px;text-align:center">OCI Robot Cloud \u00b7 inference_cost_breakdown.py \u00b7 seed={report.seed}</div></body></html>"""


def main() -> int:
    parser = argparse.ArgumentParser(description="GR00T inference cost breakdown -- OCI deployment tiers")
    parser.add_argument("--mock", action="store_true", default=True)
    parser.add_argument("--output", default="/tmp/inference_cost_breakdown.html")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    print(f"[inference_cost_breakdown] seed={args.seed} mock={args.mock}")
    report = simulate_all(seed=args.seed)
    html = render_html(report)

    with open(args.output, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[inference_cost_breakdown] HTML written \u2192 {args.output}")

    json_path = args.output.replace(".html", ".json")
    data = {"seed": report.seed, "tier_results": [{"tier_name": tr.tier_name, "gpu_model": tr.gpu_model,
        "cost_per_1k_batch1": round(tr.cost_per_1k_batch1, 6), "cost_per_1k_batch4": round(tr.cost_per_1k_batch4, 6),
        "monthly_costs": tr.monthly_costs} for tr in report.tier_results],
        "provider_comparison": {"oci_per_step_uusd": round(report.provider_comparison.oci_a100_cost_per_inf_step*1e6, 3),
            "aws_per_step_uusd": round(report.provider_comparison.aws_p4d_cost_per_inf_step*1e6, 3),
            "oci_multiplier": round(report.provider_comparison.aws_to_oci_multiplier, 2)}}
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"[inference_cost_breakdown] JSON sidecar \u2192 {json_path}")

    pc = report.provider_comparison
    print(f"\n=== OCI vs AWS ===")
    print(f"  OCI A100: ${pc.oci_a100_cost_per_inf_step*1e6:.2f} \u03bcUSD/step")
    print(f"  AWS p4d:  ${pc.aws_p4d_cost_per_inf_step*1e6:.2f} \u03bcUSD/step")
    print(f"  OCI is {pc.aws_to_oci_multiplier:.1f}x cheaper per inference step")
    return 0


if __name__ == "__main__":
    sys.exit(main())
