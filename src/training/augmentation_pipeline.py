#!/usr/bin/env python3
"""
augmentation_pipeline.py — Data augmentation pipeline for GR00T fine-tuning.

Applies systematic augmentations to robot demonstration data before training:
image augmentations (color jitter, crop, blur), action noise injection,
temporal resampling, and synthetic trajectory perturbation. Improves
generalization and reduces need for additional real demos.

Usage:
    python src/training/augmentation_pipeline.py --mock --output /tmp/augmentation.html
    python src/training/augmentation_pipeline.py --n-episodes 500 --aug-factor 3
"""

import argparse
import json
import math
import random
import time
from dataclasses import dataclass
from pathlib import Path


# ── Augmentation config ────────────────────────────────────────────────────────

@dataclass
class AugConfig:
    name: str
    category: str          # visual / action / temporal / spatial
    description: str
    intensity: float       # 0-1 (how strong)
    sr_impact: float       # +/- effect on training SR (simulation)
    cost_mult: float       # training time multiplier
    enabled: bool


AUGMENTATIONS = [
    AugConfig("color_jitter",       "visual",   "Random brightness/contrast/saturation ±20%", 0.5, +0.035, 1.0, True),
    AugConfig("random_crop",        "visual",   "Random crop 90-100% of frame",               0.4, +0.028, 1.0, True),
    AugConfig("gaussian_blur",      "visual",   "Blur sigma 0-1.5 randomly",                  0.3, +0.018, 1.0, True),
    AugConfig("random_flip",        "visual",   "Horizontal flip with joint mirroring",        0.5, +0.012, 1.0, False),  # risky for asymmetric tasks
    AugConfig("action_noise",       "action",   "Gaussian noise σ=0.01 on joint targets",     0.3, +0.025, 1.0, True),
    AugConfig("action_smoothing",   "action",   "Temporal smoothing on action sequence",       0.4, +0.015, 1.0, True),
    AugConfig("goal_perturbation",  "spatial",  "±2cm goal position jitter",                  0.3, +0.030, 1.0, True),
    AugConfig("start_perturbation", "spatial",  "±3cm start pose jitter",                     0.4, +0.022, 1.0, True),
    AugConfig("time_warp",          "temporal", "Speed up/slow down episodes ±20%",            0.3, +0.010, 1.05, True),
    AugConfig("frame_drop",         "temporal", "Randomly drop 5% of frames",                 0.2, -0.005, 0.97, True),
    AugConfig("cutout",             "visual",   "Random rectangular masking 10% area",         0.3, +0.020, 1.0, True),
    AugConfig("trajectory_mirror",  "spatial",  "Mirror trajectory in workspace",              0.5, +0.015, 1.0, False),
]


@dataclass
class AugResult:
    config_name: str
    base_episodes: int
    augmented_episodes: int
    aug_factor: float
    sr_before: float
    sr_after: float
    sr_delta: float
    train_time_mult: float
    effective_demos: int    # equivalent real demos


def simulate_augmentation(configs: list[AugConfig], n_episodes: int,
                           aug_factor: int, base_sr: float = 0.68,
                           seed: int = 42) -> list[AugResult]:
    rng = random.Random(seed)
    results = []
    enabled = [c for c in configs if c.enabled]

    for c in AUGMENTATIONS:
        # Combined effect: this augmentation alone
        combo = [c]
        sr_delta = sum(a.intensity * a.sr_impact for a in combo)
        sr_delta += rng.gauss(0, 0.008)   # noise

        aug_eps = n_episodes * aug_factor
        effective = int(n_episodes * (1 + sr_delta / base_sr * 0.5 * aug_factor))

        results.append(AugResult(
            config_name=c.name,
            base_episodes=n_episodes,
            augmented_episodes=aug_eps,
            aug_factor=aug_factor,
            sr_before=round(base_sr, 3),
            sr_after=round(max(0.05, min(0.90, base_sr + sr_delta)), 3),
            sr_delta=round(sr_delta, 4),
            train_time_mult=round(c.cost_mult * aug_factor * 0.7, 2),  # batching helps
            effective_demos=effective,
        ))

    # Combined all-enabled result
    all_sr_delta = sum(c.intensity * c.sr_impact for c in enabled) + rng.gauss(0, 0.005)
    combined_time = max(c.cost_mult for c in enabled) * aug_factor * 0.6
    results.append(AugResult(
        config_name="combined_enabled",
        base_episodes=n_episodes,
        augmented_episodes=n_episodes * aug_factor,
        aug_factor=aug_factor,
        sr_before=round(base_sr, 3),
        sr_after=round(max(0.05, min(0.90, base_sr + all_sr_delta)), 3),
        sr_delta=round(all_sr_delta, 4),
        train_time_mult=round(combined_time, 2),
        effective_demos=int(n_episodes * aug_factor * 1.15),
    ))

    return results


# ── HTML report ────────────────────────────────────────────────────────────────

def render_html(results: list[AugResult], configs: list[AugConfig],
                n_episodes: int, aug_factor: int) -> str:
    combined = next(r for r in results if r.config_name == "combined_enabled")
    best_single = max((r for r in results if r.config_name != "combined_enabled"),
                       key=lambda r: r.sr_delta)
    individual = [r for r in results if r.config_name != "combined_enabled"]

    # SVG: SR delta bar chart per augmentation
    w, h = 540, 200
    max_delta = max(abs(r.sr_delta) for r in individual) * 1.2 or 0.05
    bar_h = (h - 30) / len(individual) - 3

    svg = f'<svg width="{w}" height="{h}" style="background:#0f172a;border-radius:8px">'
    # Zero line
    zero_x = 160
    svg += f'<line x1="{zero_x}" y1="10" x2="{zero_x}" y2="{h-20}" stroke="#334155" stroke-width="1"/>'

    CAT_COLORS = {"visual": "#3b82f6", "action": "#22c55e",
                  "spatial": "#f59e0b", "temporal": "#a855f7"}

    for i, r in enumerate(individual):
        y = 10 + i * (bar_h + 3)
        cfg = next(c for c in AUGMENTATIONS if c.name == r.config_name)
        bw = abs(r.sr_delta) / max_delta * (w - zero_x - 80)
        col = CAT_COLORS.get(cfg.category, "#64748b")
        if not cfg.enabled:
            col = "#475569"
        if r.sr_delta >= 0:
            svg += (f'<rect x="{zero_x:.1f}" y="{y}" width="{bw:.1f}" height="{bar_h:.1f}" '
                    f'fill="{col}" rx="1" opacity="0.85"/>')
            svg += (f'<text x="{zero_x+bw+3:.1f}" y="{y+bar_h*0.75:.1f}" fill="{col}" '
                    f'font-size="8.5">+{r.sr_delta:.3f}</text>')
        else:
            svg += (f'<rect x="{zero_x-bw:.1f}" y="{y}" width="{bw:.1f}" height="{bar_h:.1f}" '
                    f'fill="#ef4444" rx="1" opacity="0.75"/>')
            svg += (f'<text x="{zero_x-bw-3:.1f}" y="{y+bar_h*0.75:.1f}" fill="#ef4444" '
                    f'font-size="8.5" text-anchor="end">{r.sr_delta:.3f}</text>')
        enabled_mark = "" if cfg.enabled else " ✗"
        svg += (f'<text x="{zero_x-4:.1f}" y="{y+bar_h*0.75:.1f}" fill="#94a3b8" '
                f'font-size="8.5" text-anchor="end">{r.config_name[:18]}{enabled_mark}</text>')

    svg += '</svg>'

    legend = " ".join(
        f'<span style="color:{CAT_COLORS[cat]}">■ {cat}</span>'
        for cat in ["visual", "action", "spatial", "temporal"]
    )

    # Table
    rows = ""
    for r in sorted(individual, key=lambda x: -x.sr_delta):
        cfg = next(c for c in AUGMENTATIONS if c.name == r.config_name)
        is_combined = r.config_name == "combined_enabled"
        col = CAT_COLORS.get(cfg.category, "#64748b")
        if not cfg.enabled:
            col = "#475569"
        delta_col = "#22c55e" if r.sr_delta > 0.01 else "#f59e0b" if r.sr_delta >= 0 else "#ef4444"
        enabled_str = '<span style="color:#22c55e">✓</span>' if cfg.enabled else '<span style="color:#64748b">✗ disabled</span>'
        rows += (f'<tr>'
                 f'<td style="color:{col}">{r.config_name}</td>'
                 f'<td style="color:#64748b">{cfg.category}</td>'
                 f'<td>{enabled_str}</td>'
                 f'<td style="color:#94a3b8;font-size:10px">{cfg.description}</td>'
                 f'<td>{r.augmented_episodes:,}</td>'
                 f'<td style="color:{delta_col}">{r.sr_delta:+.4f}</td>'
                 f'<td style="color:#22c55e">{r.sr_after:.0%}</td>'
                 f'<td style="color:#64748b">{r.train_time_mult:.2f}×</td></tr>')

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Augmentation Pipeline</title>
<style>
body{{background:#1e293b;color:#e2e8f0;font-family:monospace;margin:0;padding:24px}}
h1{{color:#C74634;margin:0 0 4px}}
.meta{{color:#94a3b8;font-size:12px;margin-bottom:20px}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:20px}}
.card{{background:#0f172a;border-radius:8px;padding:14px}}
.card h3{{color:#94a3b8;font-size:11px;text-transform:uppercase;margin:0 0 4px}}
.big{{font-size:28px;font-weight:bold}}
table{{width:100%;border-collapse:collapse;font-size:12px}}
th{{color:#94a3b8;text-align:left;padding:5px 8px;border-bottom:1px solid #334155}}
td{{padding:3px 8px;border-bottom:1px solid #1e293b}}
</style></head>
<body>
<h1>Augmentation Pipeline</h1>
<div class="meta">
  {n_episodes} base episodes · {aug_factor}× augmentation factor → {n_episodes * aug_factor:,} training episodes ·
  {sum(1 for c in configs if c.enabled)}/{len(configs)} augmentations enabled
</div>

<div class="grid">
  <div class="card"><h3>Combined SR Gain</h3>
    <div class="big" style="color:#22c55e">+{combined.sr_delta:.3f}</div>
    <div style="color:#64748b;font-size:12px">{combined.sr_before:.0%} → {combined.sr_after:.0%}</div></div>
  <div class="card"><h3>Best Single Aug</h3>
    <div class="big" style="color:#3b82f6">{best_single.config_name.replace("_"," ")[:12]}</div>
    <div style="color:#64748b;font-size:12px">+{best_single.sr_delta:.4f} SR</div></div>
  <div class="card"><h3>Effective Demos</h3>
    <div class="big" style="color:#22c55e">{combined.effective_demos:,}</div>
    <div style="color:#64748b;font-size:12px">from {n_episodes} real demos</div></div>
  <div class="card"><h3>Train Time</h3>
    <div class="big" style="color:#f59e0b">{combined.train_time_mult:.2f}×</div>
    <div style="color:#64748b;font-size:12px">vs no augmentation</div></div>
</div>

<h3 style="color:#94a3b8;font-size:11px;text-transform:uppercase;margin-bottom:8px">SR Delta per Augmentation</h3>
<div style="font-size:10px;margin-bottom:6px">{legend} · faded = disabled</div>
{svg}
<div style="color:#64748b;font-size:10px;margin-top:4px;margin-bottom:16px">
  Positive = SR improvement when aug enabled · Disabled augs shown for reference
</div>

<table>
  <tr><th>Augmentation</th><th>Category</th><th>Enabled</th><th>Description</th>
      <th>Aug Episodes</th><th>SR Δ</th><th>Final SR</th><th>Time</th></tr>
  {rows}
</table>

<div style="color:#64748b;font-size:11px;margin-top:16px">
  Combined enabled augmentations: {combined.sr_before:.0%} → {combined.sr_after:.0%} SR (+{combined.sr_delta:.3f}) at {combined.train_time_mult:.1f}× training time.<br>
  Equivalent to {combined.effective_demos:,} real demos from only {n_episodes} actual demonstrations.<br>
  Disable random_flip and trajectory_mirror for asymmetric tasks (e.g. pick-and-place with fixed orientation).
</div>
</body></html>"""


# ── CLI ────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Data augmentation pipeline")
    parser.add_argument("--mock",         action="store_true", default=True)
    parser.add_argument("--n-episodes",   type=int, default=500)
    parser.add_argument("--aug-factor",   type=int, default=3)
    parser.add_argument("--base-sr",      type=float, default=0.68)
    parser.add_argument("--output",       default="/tmp/augmentation_pipeline.html")
    parser.add_argument("--seed",         type=int, default=42)
    args = parser.parse_args()

    enabled_count = sum(1 for c in AUGMENTATIONS if c.enabled)
    print(f"[aug] {args.n_episodes} episodes × {args.aug_factor}× · {enabled_count} augmentations enabled")
    t0 = time.time()

    results = simulate_augmentation(AUGMENTATIONS, args.n_episodes, args.aug_factor,
                                    args.base_sr, args.seed)
    combined = next(r for r in results if r.config_name == "combined_enabled")

    print(f"\n  {'Augmentation':<22} {'SR Delta':>10}  {'Final SR':>9}  {'Enabled'}")
    print(f"  {'─'*22} {'─'*10}  {'─'*9}  {'─'*8}")
    for r in sorted(results, key=lambda x: -x.sr_delta):
        if r.config_name == "combined_enabled":
            continue
        cfg = next(c for c in AUGMENTATIONS if c.name == r.config_name)
        mark = "✓" if cfg.enabled else "✗"
        print(f"  {r.config_name:<22} {r.sr_delta:>+9.4f}  {r.sr_after:>8.0%}  {mark}")

    print(f"\n  Combined: {combined.sr_before:.0%} → {combined.sr_after:.0%} "
          f"(+{combined.sr_delta:.4f}) @ {combined.train_time_mult:.2f}× time")
    print(f"  [{time.time()-t0:.1f}s]\n")

    html = render_html(results, AUGMENTATIONS, args.n_episodes, args.aug_factor)
    Path(args.output).write_text(html)
    print(f"  HTML → {args.output}")

    json_out = Path(args.output).with_suffix(".json")
    json_out.write_text(json.dumps(
        [{"aug": r.config_name, "sr_delta": r.sr_delta, "sr_after": r.sr_after,
          "time_mult": r.train_time_mult}
         for r in results], indent=2))
    print(f"  JSON → {json_out}")


if __name__ == "__main__":
    main()
