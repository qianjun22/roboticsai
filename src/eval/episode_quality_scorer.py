#!/usr/bin/env python3
"""
episode_quality_scorer.py — Scores robot demonstration episodes for training data quality.

Analyzes collected episodes across 6 quality dimensions, assigns tier labels
(GOLD/SILVER/BRONZE/REJECT), and recommends which demos to include in the
fine-tuning buffer. Encourages a high-quality, diverse training set.

Usage:
    python src/eval/episode_quality_scorer.py --mock --n-episodes 200 --seed 42
    python src/eval/episode_quality_scorer.py --mock --output /tmp/episode_quality_scorer.html
"""

import argparse
import json
import math
import random
import time
from dataclasses import dataclass, field
from pathlib import Path


# ── Tiers ─────────────────────────────────────────────────────────────────────

GOLD   = "GOLD"
SILVER = "SILVER"
BRONZE = "BRONZE"
REJECT = "REJECT"

TIER_THRESHOLDS = {
    GOLD:   0.85,
    SILVER: 0.65,
    BRONZE: 0.45,
    REJECT: 0.00,
}

TIER_COLORS = {
    GOLD:   "#f59e0b",
    SILVER: "#94a3b8",
    BRONZE: "#c97c3a",
    REJECT: "#ef4444",
}

# Composite score weights (must sum to 1.0)
SCORE_WEIGHTS = {
    "task_completion":       0.35,
    "trajectory_smoothness": 0.20,
    "efficiency":            0.15,
    "grasp_stability":       0.15,
    "demonstration_novelty": 0.10,
    "recovery_penalty":      0.05,
}


# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class Episode:
    ep_id: str
    task: str
    source: str           # human / dagger / bc_rollout / synthetic

    # 6 quality dimensions (0-1 each)
    task_completion:       float
    trajectory_smoothness: float
    efficiency:            float
    grasp_stability:       float
    demonstration_novelty: float
    recovery_penalty:      float   # already inverted: 1 = no recovery needed

    composite: float  # weighted average of the 6 dims
    tier: str         # GOLD / SILVER / BRONZE / REJECT

    n_frames:   int
    duration_s: float
    success:    bool


TASKS = ["pick_and_place", "stack_blocks", "open_drawer", "peg_insert", "handover"]


# ── Scoring helpers ────────────────────────────────────────────────────────────

def compute_composite(dims: dict) -> float:
    return round(
        sum(SCORE_WEIGHTS[k] * dims[k] for k in SCORE_WEIGHTS),
        4,
    )


def assign_tier(score: float) -> str:
    if score >= TIER_THRESHOLDS[GOLD]:
        return GOLD
    if score >= TIER_THRESHOLDS[SILVER]:
        return SILVER
    if score >= TIER_THRESHOLDS[BRONZE]:
        return BRONZE
    return REJECT


# ── Episode simulation ────────────────────────────────────────────────────────
#
# Target distribution:
#   GOLD   ~15% (score ≥ 0.85)
#   SILVER ~30% (0.65–0.85)
#   BRONZE ~15% (0.45–0.65)
#   REJECT ~40% (< 0.45)
#
# We generate episodes from two quality pools:
#   • good pool (60%): mean composite ≈ 0.78, σ = 0.08  → lands in GOLD+SILVER+some BRONZE
#   • poor pool (40%): mean composite ≈ 0.35, σ = 0.10  → mostly REJECT

def generate_episodes(n: int = 200, seed: int = 42) -> list:
    rng = random.Random(seed)
    episodes = []

    # Pre-build a small "existing buffer" of representative feature vectors
    # used to compute Euclidean novelty for each new episode.
    buffer_size = 20
    buffer = []
    for _ in range(buffer_size):
        buffer.append([rng.gauss(0.65, 0.15) for _ in range(5)])

    def euclidean_novelty(feat):
        min_dist = min(
            math.sqrt(sum((a - b) ** 2 for a, b in zip(feat, bf)))
            for bf in buffer
        )
        # normalise: max possible distance in [0,1]^5 is sqrt(5) ≈ 2.236
        return min(1.0, min_dist / math.sqrt(5))

    source_probs   = {"human": 0.15, "dagger": 0.45, "bc_rollout": 0.30, "synthetic": 0.10}
    # Source quality modifier added on top of pool base
    source_boost = {"human": 0.10, "dagger": 0.02, "bc_rollout": -0.04, "synthetic": 0.00}

    # Pool parameters chosen so final distribution hits:
    #   GOLD ~15%, SILVER ~30%, BRONZE ~15%, REJECT ~40%  (60% pass)
    # good-pool base mean ≈ 0.82 → composite ≈ 0.78-0.88 range
    # poor-pool base mean ≈ 0.28 → composite < 0.45 (REJECT)
    GOOD_MEAN, GOOD_STD = 0.82, 0.09
    POOR_MEAN, POOR_STD = 0.28, 0.10

    for i in range(n):
        source = rng.choices(list(source_probs), weights=list(source_probs.values()))[0]
        task   = rng.choice(TASKS)

        # Choose pool: 60% good, 40% poor
        good_pool = (rng.random() < 0.60)
        pool_base = rng.gauss(GOOD_MEAN, GOOD_STD) if good_pool \
                    else rng.gauss(POOR_MEAN, POOR_STD)
        base = max(0.05, min(0.98, pool_base + source_boost[source]))

        def clamp(v, lo=0.0, hi=1.0):
            return max(lo, min(hi, v))

        # task_completion: binary success + partial credit
        raw_completion = clamp(base + rng.gauss(0, 0.10))
        success = raw_completion >= 0.70
        task_completion = raw_completion if success else raw_completion * 0.5

        # trajectory_smoothness: penalises erratic joint motion
        trajectory_smoothness = clamp(base + rng.gauss(0, 0.09))

        # efficiency: path length vs optimal; poor demos waste motion
        path_overhead = clamp(1.0 - abs(rng.gauss(0, 0.15)) * (1.5 - base))
        efficiency = clamp(path_overhead)

        # grasp_stability: gripper force consistency
        grasp_stability = clamp(base + rng.gauss(0, 0.10))

        # recovery_penalty (inverted): 1 = minimal corrections needed
        corrections = abs(rng.gauss(0, 0.18)) * (2.0 - base)
        recovery_penalty = clamp(1.0 - corrections)

        # demonstration_novelty: Euclidean distance from buffer
        feat = [task_completion, trajectory_smoothness, efficiency,
                grasp_stability, recovery_penalty]
        demonstration_novelty = euclidean_novelty(feat)

        dims = {
            "task_completion":       round(task_completion, 4),
            "trajectory_smoothness": round(trajectory_smoothness, 4),
            "efficiency":            round(efficiency, 4),
            "grasp_stability":       round(grasp_stability, 4),
            "demonstration_novelty": round(demonstration_novelty, 4),
            "recovery_penalty":      round(recovery_penalty, 4),
        }

        composite = compute_composite(dims)
        tier = assign_tier(composite)

        n_frames  = max(20, int(rng.gauss(180, 40)))
        duration  = round(n_frames / 30.0, 1)

        episodes.append(Episode(
            ep_id=f"ep-{i+1:04d}",
            task=task,
            source=source,
            n_frames=n_frames,
            duration_s=duration,
            success=success,
            **dims,
            composite=composite,
            tier=tier,
        ))

    return episodes


# ── Stats helpers ─────────────────────────────────────────────────────────────

def _mean(vals):
    return sum(vals) / len(vals) if vals else 0.0

def compute_stats(episodes: list) -> dict:
    if not episodes:
        return {}

    composites = [e.composite for e in episodes]

    tier_groups = {t: [e for e in episodes if e.tier == t]
                   for t in [GOLD, SILVER, BRONZE, REJECT]}

    dim_avgs = {
        dim: round(_mean([getattr(e, dim) for e in episodes]), 4)
        for dim in SCORE_WEIGHTS
    }

    tier_stats = {}
    for t, eps in tier_groups.items():
        tier_stats[t] = {
            "count":          len(eps),
            "avg_composite":  round(_mean([e.composite for e in eps]), 4),
            "avg_completion": round(_mean([e.task_completion for e in eps]), 4),
            "in_training":    t in (GOLD, SILVER),
        }

    return {
        "total":         len(episodes),
        "pass_count":    sum(1 for e in episodes if e.tier != REJECT),
        "pass_rate":     round(sum(1 for e in episodes if e.tier != REJECT) / len(episodes), 4),
        "gold_count":    len(tier_groups[GOLD]),
        "avg_composite": round(_mean(composites), 4),
        "tier_stats":    tier_stats,
        "dim_avgs":      dim_avgs,
        "composites":    composites,
    }


def compute_dim_avgs_for_tier(episodes: list, tier: str) -> dict:
    eps = [e for e in episodes if e.tier == tier]
    if not eps:
        return {dim: 0.0 for dim in SCORE_WEIGHTS}
    return {dim: round(_mean([getattr(e, dim) for e in eps]), 4) for dim in SCORE_WEIGHTS}


# ── Console output ────────────────────────────────────────────────────────────

def print_summary(episodes: list, stats: dict) -> None:
    print()
    print("  ┌─ Quality Tier Distribution ──────────────────────────────────────┐")
    for tier in [GOLD, SILVER, BRONZE, REJECT]:
        ts = stats["tier_stats"][tier]
        bar_len = round(ts["count"] / stats["total"] * 40)
        bar = "█" * bar_len
        tag = "✓ training" if ts["in_training"] else "✗ filtered"
        print(f"  │  {tier:<6}  {ts['count']:>3}  {ts['avg_composite']:.3f}  "
              f"{bar:<40}  {tag}")
    print("  └───────────────────────────────────────────────────────────────────┘")

    print(f"\n  Total: {stats['total']}  "
          f"Pass (≥BRONZE): {stats['pass_count']} ({stats['pass_rate']:.0%})  "
          f"GOLD: {stats['gold_count']}  "
          f"Avg composite: {stats['avg_composite']:.3f}")

    by_comp = sorted(episodes, key=lambda e: -e.composite)
    print("\n  Top-10 episodes:")
    print(f"  {'ID':<10} {'Tier':<7} {'Composite':>10}  {'Completion':>10}  "
          f"{'Smoothness':>11}  {'Task'}")
    for e in by_comp[:10]:
        print(f"  {e.ep_id:<10} {e.tier:<7} {e.composite:>10.4f}  "
              f"{e.task_completion:>10.4f}  {e.trajectory_smoothness:>11.4f}  {e.task}")

    print("\n  Bottom-10 episodes:")
    print(f"  {'ID':<10} {'Tier':<7} {'Composite':>10}  {'Completion':>10}  "
          f"{'Smoothness':>11}  {'Task'}")
    for e in by_comp[-10:]:
        print(f"  {e.ep_id:<10} {e.tier:<7} {e.composite:>10.4f}  "
              f"{e.task_completion:>10.4f}  {e.trajectory_smoothness:>11.4f}  {e.task}")

    print("\n  Fine-tuning buffer: GOLD + SILVER only")
    training = [e for e in episodes if e.tier in (GOLD, SILVER)]
    print(f"  Before filter: {stats['total']} episodes")
    print(f"  After filter:  {len(training)} episodes ({len(training)/stats['total']:.0%} retained)")


# ── SVG builders ──────────────────────────────────────────────────────────────

def svg_histogram(episodes: list) -> str:
    """Score distribution histogram with 20 bins, color-coded by tier."""
    W, H = 560, 160
    n_bins = 20
    bins   = [[] for _ in range(n_bins)]
    for e in episodes:
        idx = min(n_bins - 1, int(e.composite * n_bins))
        bins[idx].append(e.tier)

    max_count = max((len(b) for b in bins), default=1)
    bar_w = (W - 50) / n_bins
    plot_h = H - 35

    def tier_color(bin_idx):
        score_mid = (bin_idx + 0.5) / n_bins
        t = assign_tier(score_mid)
        return TIER_COLORS[t]

    parts = [
        f'<svg width="{W}" height="{H}" '
        f'style="background:#0f172a;border-radius:8px;overflow:visible">'
    ]
    # axes
    parts.append(
        f'<line x1="40" y1="{plot_h}" x2="{W-10}" y2="{plot_h}" '
        f'stroke="#334155" stroke-width="1"/>'
    )

    # tier threshold lines
    for tier_name, thresh in [(SILVER, 0.65), (GOLD, 0.85), (BRONZE, 0.45)]:
        tx = 40 + thresh * (W - 50)
        col = TIER_COLORS[tier_name]
        parts.append(
            f'<line x1="{tx:.1f}" y1="5" x2="{tx:.1f}" y2="{plot_h}" '
            f'stroke="{col}" stroke-width="1.2" stroke-dasharray="4,3"/>'
        )
        parts.append(
            f'<text x="{tx+3:.1f}" y="14" fill="{col}" font-size="9">{tier_name}</text>'
        )

    for i, bucket in enumerate(bins):
        cnt  = len(bucket)
        bh   = cnt / max_count * (plot_h - 15)
        x    = 40 + i * bar_w
        col  = tier_color(i)
        parts.append(
            f'<rect x="{x:.1f}" y="{plot_h - bh:.1f}" '
            f'width="{bar_w - 1.5:.1f}" height="{bh:.1f}" '
            f'fill="{col}" rx="2" opacity="0.85"/>'
        )
        # x-axis labels every 4 bins
        if i % 4 == 0:
            parts.append(
                f'<text x="{x + bar_w/2:.1f}" y="{H - 5}" '
                f'fill="#64748b" font-size="8.5" text-anchor="middle">'
                f'{i/n_bins:.2f}</text>'
            )
        if cnt > 0:
            parts.append(
                f'<text x="{x + bar_w/2:.1f}" y="{plot_h - bh - 3:.1f}" '
                f'fill="#94a3b8" font-size="7.5" text-anchor="middle">{cnt}</text>'
            )

    parts.append('</svg>')
    return "".join(parts)


def svg_radar(gold_avgs: dict, reject_avgs: dict) -> str:
    """Hexagonal radar chart comparing GOLD vs REJECT avg dimension scores."""
    W, H   = 340, 300
    cx, cy = W // 2, H // 2
    r      = 110
    dims   = list(SCORE_WEIGHTS.keys())
    n      = len(dims)

    def point(angle_deg, radius):
        a = math.radians(angle_deg - 90)
        return cx + radius * math.cos(a), cy + radius * math.sin(a)

    parts = [
        f'<svg width="{W}" height="{H}" '
        f'style="background:#0f172a;border-radius:8px">'
    ]

    # grid rings
    for level in [0.25, 0.50, 0.75, 1.0]:
        pts = [point(360 / n * i, r * level) for i in range(n)]
        poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        parts.append(
            f'<polygon points="{poly}" fill="none" '
            f'stroke="#334155" stroke-width="0.8"/>'
        )

    # spokes
    for i in range(n):
        ox, oy = point(360 / n * i, r)
        parts.append(
            f'<line x1="{cx}" y1="{cy}" x2="{ox:.1f}" y2="{oy:.1f}" '
            f'stroke="#1e3a5f" stroke-width="0.8"/>'
        )

    # axis labels
    label_map = {
        "task_completion":       "Completion",
        "trajectory_smoothness": "Smoothness",
        "efficiency":            "Efficiency",
        "grasp_stability":       "Grasp",
        "demonstration_novelty": "Novelty",
        "recovery_penalty":      "Recovery",
    }
    for i, dim in enumerate(dims):
        lx, ly = point(360 / n * i, r + 18)
        parts.append(
            f'<text x="{lx:.1f}" y="{ly:.1f}" fill="#94a3b8" font-size="9.5" '
            f'text-anchor="middle" dominant-baseline="middle">{label_map[dim]}</text>'
        )

    def polygon_for(avgs, color, opacity):
        pts = [point(360 / n * i, r * avgs[dim]) for i, dim in enumerate(dims)]
        poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        return (
            f'<polygon points="{poly}" fill="{color}" fill-opacity="{opacity}" '
            f'stroke="{color}" stroke-width="1.5"/>'
        )

    parts.append(polygon_for(reject_avgs, TIER_COLORS[REJECT], 0.25))
    parts.append(polygon_for(gold_avgs,   TIER_COLORS[GOLD],   0.30))

    # legend
    parts.append(
        f'<circle cx="20" cy="{H-20}" r="5" fill="{TIER_COLORS[GOLD]}"/>'
        f'<text x="28" y="{H-16}" fill="#e2e8f0" font-size="10">GOLD avg</text>'
        f'<circle cx="100" cy="{H-20}" r="5" fill="{TIER_COLORS[REJECT]}"/>'
        f'<text x="108" y="{H-16}" fill="#e2e8f0" font-size="10">REJECT avg</text>'
    )

    parts.append('</svg>')
    return "".join(parts)


def svg_scatter(episodes: list) -> str:
    """Efficiency vs Smoothness scatter plot, colored by tier."""
    W, H = 360, 280
    pad  = {"l": 45, "r": 20, "t": 20, "b": 40}
    pw   = W - pad["l"] - pad["r"]
    ph   = H - pad["t"] - pad["b"]

    parts = [
        f'<svg width="{W}" height="{H}" '
        f'style="background:#0f172a;border-radius:8px">'
    ]

    # grid
    for v in [0, 0.25, 0.50, 0.75, 1.0]:
        # horizontal
        y = pad["t"] + ph * (1 - v)
        parts.append(
            f'<line x1="{pad["l"]}" y1="{y:.1f}" '
            f'x2="{pad["l"]+pw}" y2="{y:.1f}" '
            f'stroke="#334155" stroke-width="0.7"/>'
        )
        parts.append(
            f'<text x="{pad["l"]-4}" y="{y+3:.1f}" fill="#64748b" '
            f'font-size="8.5" text-anchor="end">{v:.2f}</text>'
        )
        # vertical
        x = pad["l"] + pw * v
        parts.append(
            f'<line x1="{x:.1f}" y1="{pad["t"]}" '
            f'x2="{x:.1f}" y2="{pad["t"]+ph}" '
            f'stroke="#334155" stroke-width="0.7"/>'
        )
        parts.append(
            f'<text x="{x:.1f}" y="{H-5}" fill="#64748b" '
            f'font-size="8.5" text-anchor="middle">{v:.2f}</text>'
        )

    # axis labels
    parts.append(
        f'<text x="{pad["l"]+pw//2}" y="{H}" fill="#94a3b8" '
        f'font-size="10" text-anchor="middle">Efficiency</text>'
    )
    parts.append(
        f'<text x="10" y="{pad["t"]+ph//2}" fill="#94a3b8" '
        f'font-size="10" text-anchor="middle" '
        f'transform="rotate(-90,10,{pad["t"]+ph//2})">Smoothness</text>'
    )

    # points
    for e in episodes:
        x = pad["l"] + e.efficiency * pw
        y = pad["t"] + (1 - e.trajectory_smoothness) * ph
        col = TIER_COLORS[e.tier]
        parts.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.5" '
            f'fill="{col}" fill-opacity="0.70" stroke="none"/>'
        )

    # legend (bottom-right)
    lx, ly = pad["l"] + pw - 100, pad["t"] + 10
    for i, tier in enumerate([GOLD, SILVER, BRONZE, REJECT]):
        parts.append(
            f'<circle cx="{lx+6}" cy="{ly + i*14}" r="4" fill="{TIER_COLORS[tier]}"/>'
            f'<text x="{lx+14}" y="{ly+4 + i*14}" fill="#e2e8f0" font-size="9">'
            f'{tier}</text>'
        )

    parts.append('</svg>')
    return "".join(parts)


# ── HTML report ────────────────────────────────────────────────────────────────

def render_html(episodes: list, stats: dict) -> str:
    gold_avgs   = compute_dim_avgs_for_tier(episodes, GOLD)
    reject_avgs = compute_dim_avgs_for_tier(episodes, REJECT)

    hist    = svg_histogram(episodes)
    radar   = svg_radar(gold_avgs, reject_avgs)
    scatter = svg_scatter(episodes)

    # Quality tier summary table
    tier_rows = []
    for tier in [GOLD, SILVER, BRONZE, REJECT]:
        ts  = stats["tier_stats"][tier]
        col = TIER_COLORS[tier]
        inc = "Yes" if ts["in_training"] else "No"
        inc_col = "#22c55e" if ts["in_training"] else "#ef4444"
        tier_rows.append(
            f'<tr>'
            f'<td style="color:{col};font-weight:bold">{tier}</td>'
            f'<td>{ts["count"]}</td>'
            f'<td>{ts["count"]/stats["total"]*100:.0f}%</td>'
            f'<td>{ts["avg_composite"]:.3f}</td>'
            f'<td>{ts["avg_completion"]:.3f}</td>'
            f'<td style="color:{inc_col};font-weight:bold">{inc}</td>'
            f'</tr>'
        )

    # top-10 / bottom-10 episode rows
    by_comp = sorted(episodes, key=lambda e: -e.composite)

    def ep_row(e):
        col = TIER_COLORS[e.tier]
        return (
            f'<tr>'
            f'<td style="color:#94a3b8">{e.ep_id}</td>'
            f'<td style="color:{col};font-weight:bold">{e.tier}</td>'
            f'<td>{e.task}</td>'
            f'<td>{e.task_completion:.3f}</td>'
            f'<td>{e.trajectory_smoothness:.3f}</td>'
            f'<td>{e.efficiency:.3f}</td>'
            f'<td>{e.grasp_stability:.3f}</td>'
            f'<td>{e.demonstration_novelty:.3f}</td>'
            f'<td>{e.recovery_penalty:.3f}</td>'
            f'<td style="color:{col};font-weight:bold">{e.composite:.4f}</td>'
            f'</tr>'
        )

    top10_rows    = "".join(ep_row(e) for e in by_comp[:10])
    bottom10_rows = "".join(ep_row(e) for e in by_comp[-10:])

    training_count = sum(1 for e in episodes if e.tier in (GOLD, SILVER))

    weights_desc = " · ".join(
        f"{k.replace('_', ' ')} {v:.0%}" for k, v in SCORE_WEIGHTS.items()
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Episode Quality Scorer</title>
<style>
  *, *::before, *::after {{ box-sizing: border-box; }}
  body {{
    background: #1e293b;
    color: #e2e8f0;
    font-family: ui-monospace, "Cascadia Code", "Source Code Pro", monospace;
    margin: 0;
    padding: 28px 32px;
  }}
  h1 {{ color: #C74634; margin: 0 0 4px; font-size: 22px; }}
  .meta {{ color: #64748b; font-size: 11.5px; margin-bottom: 22px; }}
  .cards {{
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 14px;
    margin-bottom: 24px;
  }}
  .card {{
    background: #0f172a;
    border-radius: 10px;
    padding: 16px 18px;
  }}
  .card-label {{
    color: #64748b;
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 6px;
  }}
  .card-value {{
    font-size: 30px;
    font-weight: 700;
    line-height: 1;
  }}
  .card-sub {{ color: #475569; font-size: 11px; margin-top: 4px; }}
  .charts-row {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
    margin-bottom: 24px;
  }}
  .charts-row3 {{
    display: grid;
    grid-template-columns: 2fr 1fr 1fr;
    gap: 16px;
    margin-bottom: 24px;
  }}
  .chart-box {{
    background: #0f172a;
    border-radius: 10px;
    padding: 14px 16px;
  }}
  .chart-title {{
    color: #94a3b8;
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin-bottom: 10px;
  }}
  table {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
  th {{
    color: #64748b;
    text-align: left;
    padding: 6px 9px;
    border-bottom: 1px solid #334155;
    white-space: nowrap;
  }}
  td {{ padding: 4px 9px; border-bottom: 1px solid #1e293b; }}
  tr:hover td {{ background: #0f172a; }}
  .section-title {{
    color: #94a3b8;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin: 22px 0 10px;
  }}
  .note {{
    color: #475569;
    font-size: 11px;
    margin-top: 18px;
    line-height: 1.6;
  }}
</style>
</head>
<body>

<h1>Episode Quality Scorer</h1>
<div class="meta">
  {stats['total']} episodes evaluated &nbsp;·&nbsp;
  Pass rate (≥BRONZE): {stats['pass_rate']:.0%} &nbsp;·&nbsp;
  GOLD + SILVER for fine-tuning: {training_count} episodes &nbsp;·&nbsp;
  Composite weights: {weights_desc}
</div>

<!-- Summary cards -->
<div class="cards">
  <div class="card">
    <div class="card-label">Total Episodes</div>
    <div class="card-value">{stats['total']}</div>
    <div class="card-sub">evaluated</div>
  </div>
  <div class="card">
    <div class="card-label">Pass Rate (≥BRONZE)</div>
    <div class="card-value" style="color:#22c55e">{stats['pass_rate']:.0%}</div>
    <div class="card-sub">{stats['pass_count']} episodes</div>
  </div>
  <div class="card">
    <div class="card-label">GOLD Episodes</div>
    <div class="card-value" style="color:{TIER_COLORS[GOLD]}">{stats['gold_count']}</div>
    <div class="card-sub">score ≥ 0.85</div>
  </div>
  <div class="card">
    <div class="card-label">Avg Composite Score</div>
    <div class="card-value" style="color:#3b82f6">{stats['avg_composite']:.3f}</div>
    <div class="card-sub">all episodes</div>
  </div>
</div>

<!-- Charts row -->
<div class="charts-row3">
  <div class="chart-box">
    <div class="chart-title">Score Distribution — 20 bins, color-coded by tier</div>
    {hist}
  </div>
  <div class="chart-box">
    <div class="chart-title">Radar — GOLD vs REJECT avg dims</div>
    {radar}
  </div>
  <div class="chart-box">
    <div class="chart-title">Efficiency vs Smoothness by Tier</div>
    {scatter}
  </div>
</div>

<!-- Quality tier table -->
<div class="section-title">Quality Tier Summary</div>
<table>
  <thead>
    <tr>
      <th>Tier</th>
      <th>Count</th>
      <th>Share</th>
      <th>Avg Composite</th>
      <th>Avg Completion</th>
      <th>Include in Training</th>
    </tr>
  </thead>
  <tbody>
    {"".join(tier_rows)}
  </tbody>
</table>

<!-- Top-10 -->
<div class="section-title">Top-10 Highest-Quality Episodes</div>
<table>
  <thead>
    <tr>
      <th>ID</th><th>Tier</th><th>Task</th>
      <th>Completion</th><th>Smoothness</th><th>Efficiency</th>
      <th>Grasp</th><th>Novelty</th><th>Recovery</th>
      <th>Composite</th>
    </tr>
  </thead>
  <tbody>{top10_rows}</tbody>
</table>

<!-- Bottom-10 -->
<div class="section-title">Bottom-10 Lowest-Quality Episodes (REJECT)</div>
<table>
  <thead>
    <tr>
      <th>ID</th><th>Tier</th><th>Task</th>
      <th>Completion</th><th>Smoothness</th><th>Efficiency</th>
      <th>Grasp</th><th>Novelty</th><th>Recovery</th>
      <th>Composite</th>
    </tr>
  </thead>
  <tbody>{bottom10_rows}</tbody>
</table>

<div class="note">
  Tiers: GOLD ≥ 0.85 &nbsp;·&nbsp; SILVER 0.65–0.85 &nbsp;·&nbsp;
  BRONZE 0.45–0.65 &nbsp;·&nbsp; REJECT &lt; 0.45<br>
  Recommendation: include GOLD + SILVER ({training_count} episodes) in the fine-tuning buffer for
  highest training signal quality. BRONZE may be added for low-data regimes.
  REJECT demos are discarded.<br>
  Composite = completion×35% + smoothness×20% + efficiency×15% + grasp×15% + novelty×10% + recovery×5%
</div>

</body>
</html>"""


# ── CLI ────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Episode quality scorer and data filter")
    parser.add_argument("--mock",       action="store_true", default=True,
                        help="Use simulated episodes (always on in current implementation)")
    parser.add_argument("--n-episodes", type=int,   default=200,
                        help="Number of episodes to simulate (default: 200)")
    parser.add_argument("--output",     type=str,   default="/tmp/episode_quality_scorer.html",
                        help="HTML output path")
    parser.add_argument("--seed",       type=int,   default=42,
                        help="Random seed for reproducibility")
    args = parser.parse_args()

    print(f"[episode-quality-scorer] Simulating {args.n_episodes} episodes "
          f"(seed={args.seed})")
    t0 = time.time()

    episodes = generate_episodes(args.n_episodes, args.seed)
    stats    = compute_stats(episodes)

    print_summary(episodes, stats)
    print(f"\n  Elapsed: {time.time()-t0:.2f}s")

    # HTML
    html = render_html(episodes, stats)
    out  = Path(args.output)
    out.write_text(html, encoding="utf-8")
    print(f"\n  HTML → {out}")

    # JSON
    out_json = out.with_suffix(".json")

    # Build JSON-serialisable episode list
    ep_list = []
    for e in episodes:
        ep_list.append({
            "ep_id":                  e.ep_id,
            "task":                   e.task,
            "source":                 e.source,
            "tier":                   e.tier,
            "composite":              e.composite,
            "task_completion":        e.task_completion,
            "trajectory_smoothness":  e.trajectory_smoothness,
            "efficiency":             e.efficiency,
            "grasp_stability":        e.grasp_stability,
            "demonstration_novelty":  e.demonstration_novelty,
            "recovery_penalty":       e.recovery_penalty,
            "n_frames":               e.n_frames,
            "duration_s":             e.duration_s,
            "success":                e.success,
        })

    out_json.write_text(
        json.dumps({"summary": stats, "episodes": ep_list}, indent=2),
        encoding="utf-8",
    )
    print(f"  JSON → {out_json}")


if __name__ == "__main__":
    main()
