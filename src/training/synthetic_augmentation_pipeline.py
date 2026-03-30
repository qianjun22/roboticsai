#!/usr/bin/env python3
"""
synthetic_augmentation_pipeline.py -- Synthetic data augmentation pipeline for GR00T fine-tuning.

Applies 8 augmentation strategies to robot demonstration data, measures impact on
policy generalization, and recommends optimal augmentation mix for OCI training runs.
"""

import argparse
import json
import math
import random
import time
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class AugmentationStrategy:
    name: str
    description: str
    augment_factor: float
    compute_cost_factor: float
    sr_delta: float
    ood_improvement: float
    overfit_reduction: float
    compatible_with: list
    incompatible_with: list


@dataclass
class AugmentationRun:
    run_id: str
    strategies_used: list
    base_demos: int
    effective_demos: int
    sr_combined: float
    val_loss: float
    gen_gap: float
    compute_hours: float
    cost_usd: float
    rank: int


@dataclass
class AugmentationReport:
    generated_at: str
    strategies: list = field(default_factory=list)
    runs: list = field(default_factory=list)
    best_mix: list = field(default_factory=list)
    recommendations: list = field(default_factory=list)


def simulate_augmentation(seed: int = 42) -> AugmentationReport:
    rng = random.Random(seed)
    strategies = [
        AugmentationStrategy("color_jitter", "Random brightness/contrast/saturation/hue perturbations on RGB frames",
            2.0, 1.05, 0.03, 0.06, 0.12, ["gaussian_noise", "cutout", "mixup"], []),
        AugmentationStrategy("gaussian_noise", "Additive Gaussian noise on images and proprioceptive signals",
            1.5, 1.02, 0.02, 0.04, 0.08, ["color_jitter", "random_crop", "cutout"], []),
        AugmentationStrategy("random_crop", "Random spatial crops with resizing to original resolution",
            3.0, 1.08, 0.05, 0.09, 0.15, ["color_jitter", "gaussian_noise"], ["cutout"]),
        AugmentationStrategy("cutout", "Random rectangular masking of image regions (simulates occlusion)",
            1.5, 1.03, 0.04, 0.11, 0.10, ["color_jitter", "gaussian_noise", "mixup"], ["random_crop"]),
        AugmentationStrategy("mixup", "Linear interpolation between pairs of demonstrations",
            2.0, 1.15, 0.06, 0.07, 0.18, ["color_jitter", "cutout"], ["domain_randomization"]),
        AugmentationStrategy("domain_randomization", "Isaac Sim re-render with random textures, lighting, and camera pose",
            5.0, 3.20, 0.12, 0.22, 0.28, ["color_jitter", "gaussian_noise"], ["mixup"]),
        AugmentationStrategy("action_noise", "Small random perturbations added to ground-truth action labels",
            1.5, 1.01, 0.01, 0.03, 0.05,
            ["color_jitter", "gaussian_noise", "random_crop", "cutout", "mixup", "domain_randomization", "time_warp"], []),
        AugmentationStrategy("time_warp", "Non-uniform temporal resampling of demonstration trajectories",
            2.0, 1.10, 0.03, 0.05, 0.09, ["color_jitter", "gaussian_noise", "action_noise"], []),
    ]

    runs_config = [
        {"run_id": "aug_none", "strategies": [], "base_demos": 1000},
        {"run_id": "aug_color_noise", "strategies": ["color_jitter", "gaussian_noise"], "base_demos": 1000},
        {"run_id": "aug_crop_color_noise", "strategies": ["random_crop", "color_jitter", "gaussian_noise"], "base_demos": 1000},
        {"run_id": "aug_domain_rand", "strategies": ["domain_randomization", "gaussian_noise", "action_noise"], "base_demos": 1000},
        {"run_id": "aug_full_mix", "strategies": ["color_jitter", "cutout", "mixup", "action_noise", "time_warp"], "base_demos": 1000},
        {"run_id": "aug_recommended", "strategies": ["domain_randomization", "color_jitter", "gaussian_noise", "action_noise"], "base_demos": 1000},
    ]

    strat_map = {s.name: s for s in strategies}
    base_sr = 0.74
    runs = []

    for cfg in runs_config:
        used = [strat_map[s] for s in cfg["strategies"] if s in strat_map]
        if not used:
            aug_factor, sr, val_loss, gen_gap, compute = 1.0, base_sr, 0.099, 0.082, 5.2
        else:
            aug_factor = min(math.prod(s.augment_factor for s in used), 12.0)
            sr_delta_combined = sum(s.sr_delta for s in used) * (0.85 ** (len(used) - 1))
            sr = min(0.95, base_sr + sr_delta_combined + rng.gauss(0, 0.01))
            val_loss = max(0.055, 0.099 - 0.015 * len(used) + rng.gauss(0, 0.003))
            gen_gap = max(0.01, 0.082 - sum(s.overfit_reduction for s in used) * 0.4 + rng.gauss(0, 0.004))
            compute = round(5.2 * math.prod(s.compute_cost_factor for s in used), 1)
        runs.append(AugmentationRun(
            run_id=cfg["run_id"], strategies_used=cfg["strategies"],
            base_demos=cfg["base_demos"], effective_demos=int(cfg["base_demos"] * aug_factor),
            sr_combined=round(sr, 3), val_loss=round(val_loss, 4), gen_gap=round(gen_gap, 4),
            compute_hours=compute, cost_usd=round(compute * 4.10, 2), rank=0,
        ))

    runs_sorted = sorted(runs, key=lambda r: r.sr_combined, reverse=True)
    for i, r in enumerate(runs_sorted):
        r.rank = i + 1

    return AugmentationReport(
        generated_at=time.strftime("%Y-%m-%d %H:%M:%S"),
        strategies=strategies, runs=runs,
        best_mix=runs_sorted[0].strategies_used,
        recommendations=[
            f"Best mix: {', '.join(runs_sorted[0].strategies_used) or 'none'} -- SR {runs_sorted[0].sr_combined:.3f}",
            "domain_randomization alone gives +0.12 SR but costs 3.2x compute -- use only if OCI A100 available",
            "color_jitter + gaussian_noise + action_noise: cheapest effective combo (+0.06 SR, +5% compute)",
            "mixup incompatible with domain_randomization -- never use together",
            "Diminishing returns: >4 strategies rarely add more than 0.02 SR beyond 3-strategy combos",
            "All augmentations reduce generalization gap -- domain_randomization most effective (-0.28 gap)",
        ],
    )


def _sr_comparison_svg(runs: list) -> str:
    w, h = 480, 110
    n = len(runs)
    bw = 50
    gap = (w - n * bw) // (n + 1)
    svg = f'<svg width="{w}" height="{h}" style="background:#0f172a;border-radius:6px">'
    max_sr = max(r.sr_combined for r in runs)
    for i, run in enumerate(runs):
        x = gap + i * (bw + gap)
        bh = (run.sr_combined / max_sr) * (h - 28)
        by = h - bh - 14
        color = "#22c55e" if run.rank == 1 else ("#38bdf8" if run.rank <= 3 else "#64748b")
        svg += f'<rect x="{x}" y="{by:.1f}" width="{bw}" height="{bh:.1f}" fill="{color}88" stroke="{color}" stroke-width="1" rx="2"/>'
        svg += f'<text x="{x+bw//2}" y="{h-2}" text-anchor="middle" fill="#94a3b8" font-size="8">{run.run_id.replace("aug_","")}</text>'
        svg += f'<text x="{x+bw//2}" y="{by-2:.1f}" text-anchor="middle" fill="{color}" font-size="10">{run.sr_combined:.3f}</text>'
    svg += "</svg>"
    return svg


def render_html(report: AugmentationReport) -> str:
    sr_svg = _sr_comparison_svg(report.runs)
    strat_rows = "".join(
        f'<tr><td style="color:#38bdf8;padding:5px 8px">{s.name}</td>'
        f'<td style="color:#94a3b8;font-size:11px;padding:5px 8px">{s.description}</td>'
        f'<td style="text-align:center;padding:5px 8px">{s.augment_factor:.1f}x</td>'
        f'<td style="color:#22c55e;text-align:center;padding:5px 8px">+{s.sr_delta:.2f}</td>'
        f'<td style="color:#f59e0b;text-align:center;padding:5px 8px">{s.compute_cost_factor:.2f}x</td></tr>'
        for s in report.strategies
    )
    run_rows = "".join(
        f'<tr><td style="padding:5px 8px">#{r.rank}</td>'
        f'<td style="color:#C74634;padding:5px 8px">{r.run_id}</td>'
        f'<td style="color:#94a3b8;font-size:10px;padding:5px 8px">{(", ".join(r.strategies_used)) or "none"}</td>'
        f'<td style="color:{"#22c55e" if r.rank==1 else "#38bdf8"};font-weight:bold;padding:5px 8px">{r.sr_combined:.3f}</td>'
        f'<td style="padding:5px 8px">{r.effective_demos:,}</td>'
        f'<td style="color:#f59e0b;padding:5px 8px">{r.gen_gap:.4f}</td>'
        f'<td style="color:#94a3b8;padding:5px 8px">${r.cost_usd:.0f}</td></tr>'
        for r in sorted(report.runs, key=lambda x: x.rank)
    )
    recs_html = "".join(f'<li style="margin-bottom:5px;color:#cbd5e1">{r}</li>' for r in report.recommendations)
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><title>Synthetic Augmentation Pipeline</title>
<style>body{{background:#1e293b;color:#e2e8f0;font-family:'Segoe UI',Arial,sans-serif;margin:0;padding:24px}}
h1{{color:#C74634;margin:0 0 4px 0;font-size:22px}}h2{{color:#C74634;font-size:15px;margin:20px 0 10px 0;border-bottom:1px solid #334155;padding-bottom:6px}}
table{{width:100%;border-collapse:collapse}}th{{text-align:left;color:#94a3b8;font-size:11px;padding:5px 8px;font-weight:normal;border-bottom:1px solid #334155}}</style></head>
<body><h1>Synthetic Augmentation Pipeline</h1>
<div style="color:#94a3b8;font-size:12px;margin-bottom:20px">Generated {report.generated_at} \u00b7 8 strategies \u00b7 6 combos</div>
<h2>Success Rate by Augmentation Mix</h2>{sr_svg}
<h2>Augmentation Strategies</h2>
<table><tr><th>Strategy</th><th>Description</th><th style="text-align:center">Aug factor</th><th style="text-align:center">SR \u0394</th><th style="text-align:center">Compute cost</th></tr>{strat_rows}</table>
<h2>Run Comparison</h2>
<table><tr><th>Rank</th><th>Run</th><th>Strategies</th><th>SR</th><th>Eff. demos</th><th>Gen gap</th><th>Cost</th></tr>{run_rows}</table>
<h2>Recommendations</h2><ul style="padding-left:18px;line-height:1.8">{recs_html}</ul>
<div style="margin-top:24px;padding:14px;background:#0f172a;border-radius:8px;font-size:12px;color:#94a3b8">
  <strong style="color:#C74634">Best Mix:</strong> {', '.join(report.best_mix)}<br>
  All augmentations applied at dataset load time; OCI A100 GPU4 ($4.10/hr).
</div></body></html>"""


def main():
    parser = argparse.ArgumentParser(description="Synthetic augmentation pipeline analyzer")
    parser.add_argument("--mock", action="store_true", default=True)
    parser.add_argument("--output", default="/tmp/synthetic_augmentation_pipeline.html")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    report = simulate_augmentation(seed=args.seed)
    html = render_html(report)
    Path(args.output).write_text(html)
    print(f"[augmentation] Report saved to {args.output}")
    for r in sorted(report.runs, key=lambda x: x.rank):
        print(f"  #{r.rank} {r.run_id}: SR={r.sr_combined:.3f}, demos={r.effective_demos:,}, cost=${r.cost_usd:.0f}")


if __name__ == "__main__":
    main()
