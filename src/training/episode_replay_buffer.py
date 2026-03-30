"""
episode_replay_buffer.py — Episode-level replay buffer strategies for DAgger online learning.

Analyzes and compares five buffer strategies across 12 DAgger rounds:
  fifo, reservoir, prioritized, stratified, quality_weighted

Usage:
    python episode_replay_buffer.py --mock --n-rounds 12 \
        --output /tmp/episode_replay_buffer.html --seed 42
"""

from __future__ import annotations

import argparse
import json
import math
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BUFFER_CAPACITY = 5000
SR_TIERS = ("GOLD", "SILVER", "BRONZE", "RECENT")

TIER_THRESHOLDS = {
    "GOLD":   0.80,
    "SILVER": 0.55,
    "BRONZE": 0.30,
}

STRATEGY_COLORS = {
    "fifo":            "#60a5fa",  # blue
    "reservoir":       "#34d399",  # green
    "prioritized":     "#f97316",  # orange
    "stratified":      "#a78bfa",  # violet
    "quality_weighted":"#f472b6",  # pink
}

TIER_COLORS = {
    "GOLD":   "#fbbf24",
    "SILVER": "#94a3b8",
    "BRONZE": "#b45309",
    "RECENT": "#22d3ee",
}

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class Episode:
    ep_id: str
    dagger_round: int          # which round produced this episode
    sr_score: float            # success rate (0-1) — quality proxy
    td_error: float            # surprise / loss proxy
    quality_score: float       # composite quality (0-1)
    length: int                # number of steps
    timestamp: int             # insertion order (monotonic)

    @property
    def tier(self) -> str:
        if self.sr_score >= TIER_THRESHOLDS["GOLD"]:
            return "GOLD"
        if self.sr_score >= TIER_THRESHOLDS["SILVER"]:
            return "SILVER"
        if self.sr_score >= TIER_THRESHOLDS["BRONZE"]:
            return "BRONZE"
        return "BRONZE"  # below bronze still goes into BRONZE bucket


@dataclass
class BufferStats:
    round_idx: int
    strategy: str
    total_size: int
    tier_counts: Dict[str, int]
    evicted_count: int
    sampled_unique: int
    diversity_score: float      # Shannon entropy over rounds represented
    sr_estimate: float


# ---------------------------------------------------------------------------
# Mock data generation
# ---------------------------------------------------------------------------

def _make_episode(ep_id: str, dagger_round: int, rng: random.Random, timestamp: int) -> Episode:
    # SR improves across rounds (but noisy)
    base_sr = 0.10 + 0.07 * dagger_round + rng.gauss(0, 0.08)
    base_sr = max(0.0, min(1.0, base_sr))

    td_error = max(0.001, rng.expovariate(2.0) * (1.0 - base_sr + 0.2))
    quality = 0.4 * base_sr + 0.3 * (1.0 - min(td_error, 1.0)) + 0.3 * rng.random()
    quality = max(0.0, min(1.0, quality))
    length = rng.randint(20, 200)

    return Episode(
        ep_id=ep_id,
        dagger_round=dagger_round,
        sr_score=base_sr,
        td_error=td_error,
        quality_score=quality,
        length=length,
        timestamp=timestamp,
    )


def generate_rounds(n_rounds: int, seed: int) -> List[List[Episode]]:
    """Return a list of n_rounds batches; each batch is a list of new Episodes."""
    rng = random.Random(seed)
    ts = 0
    rounds: List[List[Episode]] = []
    for r in range(n_rounds):
        n = rng.randint(50, 150)
        batch = []
        for i in range(n):
            ep = _make_episode(f"r{r:02d}_e{i:04d}", r, rng, ts)
            ts += 1
            batch.append(ep)
        rounds.append(batch)
    return rounds


# ---------------------------------------------------------------------------
# Buffer strategy implementations
# ---------------------------------------------------------------------------

class BaseBuffer:
    name: str = "base"

    def __init__(self, capacity: int = BUFFER_CAPACITY, seed: int = 42):
        self.capacity = capacity
        self.buffer: List[Episode] = []
        self.rng = random.Random(seed + hash(self.name) % 1000)
        self.evicted_total = 0
        self.round_stats: List[BufferStats] = []

    def add_batch(self, batch: List[Episode], round_idx: int) -> None:
        raise NotImplementedError

    def sample(self, k: int) -> List[Episode]:
        raise NotImplementedError

    def _compute_diversity(self) -> float:
        """Shannon entropy over DAgger rounds represented in buffer."""
        if not self.buffer:
            return 0.0
        counts: Dict[int, int] = {}
        for ep in self.buffer:
            counts[ep.dagger_round] = counts.get(ep.dagger_round, 0) + 1
        total = len(self.buffer)
        entropy = 0.0
        for c in counts.values():
            p = c / total
            if p > 0:
                entropy -= p * math.log2(p)
        max_entropy = math.log2(max(len(counts), 1))
        return entropy / max_entropy if max_entropy > 0 else 0.0

    def _compute_sr(self) -> float:
        if not self.buffer:
            return 0.0
        return sum(ep.sr_score for ep in self.buffer) / len(self.buffer)

    def _tier_counts(self) -> Dict[str, int]:
        counts = {t: 0 for t in SR_TIERS}
        for ep in self.buffer:
            counts[ep.tier] += 1
        # RECENT: from the last round
        if self.buffer:
            max_round = max(ep.dagger_round for ep in self.buffer)
            counts["RECENT"] = sum(1 for ep in self.buffer if ep.dagger_round == max_round)
        return counts

    def record_stats(self, round_idx: int, evicted: int, sampled_unique: int) -> None:
        stats = BufferStats(
            round_idx=round_idx,
            strategy=self.name,
            total_size=len(self.buffer),
            tier_counts=self._tier_counts(),
            evicted_count=evicted,
            sampled_unique=sampled_unique,
            diversity_score=self._compute_diversity(),
            sr_estimate=self._compute_sr(),
        )
        self.round_stats.append(stats)


class FIFOBuffer(BaseBuffer):
    name = "fifo"

    def add_batch(self, batch: List[Episode], round_idx: int) -> None:
        evicted = 0
        for ep in batch:
            if len(self.buffer) >= self.capacity:
                self.buffer.pop(0)
                evicted += 1
            self.buffer.append(ep)
        self.evicted_total += evicted
        sampled = len(self.sample(min(256, len(self.buffer))))
        sampled_unique = len(set(e.ep_id for e in self.sample(min(256, len(self.buffer)))))
        self.record_stats(round_idx, evicted, sampled_unique)

    def sample(self, k: int) -> List[Episode]:
        if not self.buffer:
            return []
        return self.rng.choices(self.buffer, k=min(k, len(self.buffer)))


class ReservoirBuffer(BaseBuffer):
    name = "reservoir"

    def __init__(self, capacity: int = BUFFER_CAPACITY, seed: int = 42):
        super().__init__(capacity, seed)
        self._stream_count = 0  # total episodes seen

    def add_batch(self, batch: List[Episode], round_idx: int) -> None:
        evicted = 0
        for ep in batch:
            self._stream_count += 1
            if len(self.buffer) < self.capacity:
                self.buffer.append(ep)
            else:
                j = self.rng.randint(0, self._stream_count - 1)
                if j < self.capacity:
                    self.buffer[j] = ep
                    evicted += 1
        self.evicted_total += evicted
        sampled_unique = len(set(e.ep_id for e in self.sample(min(256, len(self.buffer)))))
        self.record_stats(round_idx, evicted, sampled_unique)

    def sample(self, k: int) -> List[Episode]:
        if not self.buffer:
            return []
        return self.rng.choices(self.buffer, k=min(k, len(self.buffer)))


class PrioritizedBuffer(BaseBuffer):
    name = "prioritized"

    def add_batch(self, batch: List[Episode], round_idx: int) -> None:
        evicted = 0
        self.buffer.extend(batch)
        if len(self.buffer) > self.capacity:
            # Sort by td_error ascending; drop lowest-surprise (least informative)
            self.buffer.sort(key=lambda e: e.td_error)
            drop = len(self.buffer) - self.capacity
            evicted = drop
            self.buffer = self.buffer[drop:]
        self.evicted_total += evicted
        sampled_unique = len(set(e.ep_id for e in self.sample(min(256, len(self.buffer)))))
        self.record_stats(round_idx, evicted, sampled_unique)

    def sample(self, k: int) -> List[Episode]:
        if not self.buffer:
            return []
        weights = [ep.td_error + 1e-6 for ep in self.buffer]
        return self.rng.choices(self.buffer, weights=weights, k=min(k, len(self.buffer)))


class StratifiedBuffer(BaseBuffer):
    """Maintain equal counts per SR tier: GOLD / SILVER / BRONZE / RECENT."""
    name = "stratified"

    def __init__(self, capacity: int = BUFFER_CAPACITY, seed: int = 42):
        super().__init__(capacity, seed)
        self.tiers: Dict[str, List[Episode]] = {t: [] for t in ("GOLD", "SILVER", "BRONZE")}
        self.recent: List[Episode] = []

    def _rebuild_buffer(self) -> None:
        self.buffer = (
            self.tiers["GOLD"]
            + self.tiers["SILVER"]
            + self.tiers["BRONZE"]
            + self.recent
        )

    def add_batch(self, batch: List[Episode], round_idx: int) -> None:
        # New batch goes into RECENT; rotate old RECENT into their tier buckets
        for ep in self.recent:
            self.tiers[ep.tier].append(ep)
        self.recent = list(batch)

        evicted = 0
        per_bucket = self.capacity // 4

        # Trim each tier to per_bucket
        for tier_name in ("GOLD", "SILVER", "BRONZE"):
            bucket = self.tiers[tier_name]
            if len(bucket) > per_bucket:
                drop = len(bucket) - per_bucket
                evicted += drop
                # Keep highest quality
                bucket.sort(key=lambda e: e.quality_score, reverse=True)
                self.tiers[tier_name] = bucket[:per_bucket]

        # Trim RECENT too
        if len(self.recent) > per_bucket:
            evicted += len(self.recent) - per_bucket
            self.recent = self.recent[-per_bucket:]

        self.evicted_total += evicted
        self._rebuild_buffer()
        sampled_unique = len(set(e.ep_id for e in self.sample(min(256, len(self.buffer)))))
        self.record_stats(round_idx, evicted, sampled_unique)

    def sample(self, k: int) -> List[Episode]:
        if not self.buffer:
            return []
        # Equal probability across tiers, then uniform within
        result = []
        per_tier = max(1, k // 4)
        for bucket in [self.tiers["GOLD"], self.tiers["SILVER"], self.tiers["BRONZE"], self.recent]:
            if bucket:
                result.extend(self.rng.choices(bucket, k=min(per_tier, len(bucket))))
        return result[:k]

    def _tier_counts(self) -> Dict[str, int]:
        return {
            "GOLD":   len(self.tiers["GOLD"]),
            "SILVER": len(self.tiers["SILVER"]),
            "BRONZE": len(self.tiers["BRONZE"]),
            "RECENT": len(self.recent),
        }


class QualityWeightedBuffer(BaseBuffer):
    name = "quality_weighted"

    def add_batch(self, batch: List[Episode], round_idx: int) -> None:
        evicted = 0
        self.buffer.extend(batch)
        if len(self.buffer) > self.capacity:
            # Evict lowest-quality episodes
            self.buffer.sort(key=lambda e: e.quality_score)
            drop = len(self.buffer) - self.capacity
            evicted = drop
            self.buffer = self.buffer[drop:]
        self.evicted_total += evicted
        sampled_unique = len(set(e.ep_id for e in self.sample(min(256, len(self.buffer)))))
        self.record_stats(round_idx, evicted, sampled_unique)

    def sample(self, k: int) -> List[Episode]:
        if not self.buffer:
            return []
        weights = [ep.quality_score + 1e-6 for ep in self.buffer]
        return self.rng.choices(self.buffer, weights=weights, k=min(k, len(self.buffer)))


# ---------------------------------------------------------------------------
# Strategy runner
# ---------------------------------------------------------------------------

STRATEGIES = {
    "fifo":             FIFOBuffer,
    "reservoir":        ReservoirBuffer,
    "prioritized":      PrioritizedBuffer,
    "stratified":       StratifiedBuffer,
    "quality_weighted": QualityWeightedBuffer,
}


def run_simulation(n_rounds: int, seed: int) -> Dict[str, BaseBuffer]:
    rounds_data = generate_rounds(n_rounds, seed)
    buffers: Dict[str, BaseBuffer] = {}
    for name, cls in STRATEGIES.items():
        buf = cls(capacity=BUFFER_CAPACITY, seed=seed)
        for r_idx, batch in enumerate(rounds_data):
            buf.add_batch(batch, r_idx)
        buffers[name] = buf
    return buffers


# ---------------------------------------------------------------------------
# Eviction pattern: track which round's demos survive to the end
# ---------------------------------------------------------------------------

def compute_eviction_heatmap(n_rounds: int, seed: int) -> Dict[str, List[List[float]]]:
    """
    For each strategy, simulate and after each round record
    fraction of episodes from each source round that are currently in buffer.
    Returns dict: strategy -> matrix[round_observed][source_round] = fraction
    """
    rounds_data = generate_rounds(n_rounds, seed)
    result: Dict[str, List[List[float]]] = {}

    for name, cls in STRATEGIES.items():
        buf = cls(capacity=BUFFER_CAPACITY, seed=seed)
        matrix: List[List[float]] = []
        for r_idx, batch in enumerate(rounds_data):
            buf.add_batch(batch, r_idx)
            row: List[float] = []
            total = len(buf.buffer) if buf.buffer else 1
            for src_r in range(n_rounds):
                count = sum(1 for e in buf.buffer if e.dagger_round == src_r)
                row.append(count / total)
            matrix.append(row)
        result[name] = matrix

    return result


# ---------------------------------------------------------------------------
# Summary metrics computation
# ---------------------------------------------------------------------------

@dataclass
class StrategySummary:
    name: str
    effective_diversity: float       # mean diversity over rounds
    catastrophic_forgetting_rate: float  # fraction of early-round demos evicted
    convergence_speed: int           # round where SR first exceeds 0.6 (else n_rounds)
    final_sr: float
    mean_sampled_unique: float
    total_evicted: int


def compute_summaries(buffers: Dict[str, BaseBuffer], n_rounds: int) -> List[StrategySummary]:
    summaries = []
    for name, buf in buffers.items():
        stats = buf.round_stats
        if not stats:
            continue

        diversity = sum(s.diversity_score for s in stats) / len(stats)
        final_sr = stats[-1].sr_estimate if stats else 0.0

        # Catastrophic forgetting: fraction of round-0 demos that were evicted
        # proxy: 1 - (round-0 demos remaining at end) / (round-0 demos added)
        r0_demos_in_buffer = sum(1 for e in buf.buffer if e.dagger_round == 0)
        # round-0 batch size
        rounds_data = generate_rounds(n_rounds, seed=42)
        r0_added = len(rounds_data[0])
        forgetting = 1.0 - min(r0_demos_in_buffer / max(r0_added, 1), 1.0)

        # Convergence speed: first round SR > 0.6
        conv_round = n_rounds
        for s in stats:
            if s.sr_estimate >= 0.60:
                conv_round = s.round_idx
                break

        mean_unique = sum(s.sampled_unique for s in stats) / len(stats)

        summaries.append(StrategySummary(
            name=name,
            effective_diversity=diversity,
            catastrophic_forgetting_rate=forgetting,
            convergence_speed=conv_round,
            final_sr=final_sr,
            mean_sampled_unique=mean_unique,
            total_evicted=buf.evicted_total,
        ))
    return summaries


# ---------------------------------------------------------------------------
# Console output
# ---------------------------------------------------------------------------

def print_comparison_table(summaries: List[StrategySummary]) -> None:
    header = f"{'Strategy':<20} {'Diversity':>10} {'Forgetting':>12} {'Conv Round':>12} {'Final SR':>10} {'Evicted':>9}"
    print("\n" + "=" * len(header))
    print("  Episode Replay Buffer Strategy Comparison")
    print("=" * len(header))
    print(header)
    print("-" * len(header))
    for s in summaries:
        print(
            f"{s.name:<20} {s.effective_diversity:>10.3f} "
            f"{s.catastrophic_forgetting_rate:>12.3f} "
            f"{s.convergence_speed:>12d} "
            f"{s.final_sr:>10.3f} "
            f"{s.total_evicted:>9d}"
        )
    print("=" * len(header) + "\n")


# ---------------------------------------------------------------------------
# SVG generators
# ---------------------------------------------------------------------------

SVG_W = 700
SVG_H = 280
MARGIN = {"top": 30, "right": 20, "bottom": 45, "left": 55}


def _plot_w() -> int:
    return SVG_W - MARGIN["left"] - MARGIN["right"]


def _plot_h() -> int:
    return SVG_H - MARGIN["top"] - MARGIN["bottom"]


def _x_pos(i: int, n: int) -> float:
    return MARGIN["left"] + i / (n - 1) * _plot_w() if n > 1 else MARGIN["left"]


def _y_pos(v: float, vmin: float = 0.0, vmax: float = 1.0) -> float:
    frac = (v - vmin) / (vmax - vmin) if vmax != vmin else 0
    return MARGIN["top"] + _plot_h() * (1 - frac)


def svg_sr_convergence(buffers: Dict[str, BaseBuffer], n_rounds: int) -> str:
    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{SVG_W}" height="{SVG_H}" '
                 f'viewBox="0 0 {SVG_W} {SVG_H}">')
    lines.append('<rect width="100%" height="100%" fill="#1e1e2e"/>')

    # Axes
    x0 = MARGIN["left"]; y0 = MARGIN["top"]; x1 = SVG_W - MARGIN["right"]; y1 = SVG_H - MARGIN["bottom"]
    lines.append(f'<line x1="{x0}" y1="{y0}" x2="{x0}" y2="{y1}" stroke="#4a4a6a" stroke-width="1"/>')
    lines.append(f'<line x1="{x0}" y1="{y1}" x2="{x1}" y2="{y1}" stroke="#4a4a6a" stroke-width="1"/>')

    # Y grid lines
    for v in [0.2, 0.4, 0.6, 0.8, 1.0]:
        gy = _y_pos(v)
        lines.append(f'<line x1="{x0}" y1="{gy:.1f}" x2="{x1}" y2="{gy:.1f}" '
                     f'stroke="#2a2a4a" stroke-width="1" stroke-dasharray="4,4"/>')
        lines.append(f'<text x="{x0 - 6}" y="{gy + 4:.1f}" fill="#9ca3af" font-size="10" '
                     f'text-anchor="end">{v:.1f}</text>')

    # X labels
    for r in range(n_rounds):
        gx = _x_pos(r, n_rounds)
        lines.append(f'<text x="{gx:.1f}" y="{y1 + 16}" fill="#9ca3af" font-size="10" '
                     f'text-anchor="middle">R{r}</text>')

    # SR lines per strategy
    for name, buf in buffers.items():
        color = STRATEGY_COLORS.get(name, "#ffffff")
        pts = [(r, s.sr_estimate) for r, s in enumerate(buf.round_stats)]
        if not pts:
            continue
        d_parts = []
        for i, (r, sr) in enumerate(pts):
            gx = _x_pos(r, n_rounds)
            gy = _y_pos(sr)
            cmd = "M" if i == 0 else "L"
            d_parts.append(f"{cmd}{gx:.1f},{gy:.1f}")
        d = " ".join(d_parts)
        lines.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="2.5" '
                     f'stroke-linejoin="round"/>')
        # End dot
        last_r, last_sr = pts[-1]
        lx = _x_pos(last_r, n_rounds)
        ly = _y_pos(last_sr)
        lines.append(f'<circle cx="{lx:.1f}" cy="{ly:.1f}" r="4" fill="{color}"/>')

    # Legend
    legend_x = MARGIN["left"] + 10
    legend_y = MARGIN["top"] + 10
    for i, (name, color) in enumerate(STRATEGY_COLORS.items()):
        lx = legend_x + i * 130
        lines.append(f'<rect x="{lx}" y="{legend_y}" width="14" height="4" fill="{color}" rx="2"/>')
        lines.append(f'<text x="{lx + 18}" y="{legend_y + 5}" fill="#e2e8f0" font-size="10">{name}</text>')

    # Title
    lines.append(f'<text x="{SVG_W // 2}" y="16" fill="#f1f5f9" font-size="13" '
                 f'text-anchor="middle" font-weight="bold">SR Convergence by Strategy</text>')

    # Y axis label
    lines.append(f'<text x="{MARGIN["left"] // 2 - 5}" y="{SVG_H // 2}" fill="#9ca3af" '
                 f'font-size="11" text-anchor="middle" '
                 f'transform="rotate(-90,{MARGIN["left"] // 2 - 5},{SVG_H // 2})">Success Rate</text>')

    lines.append('</svg>')
    return "\n".join(lines)


def svg_buffer_composition(buf: BaseBuffer, n_rounds: int, strategy_name: str) -> str:
    """Stacked area: GOLD/SILVER/BRONZE/RECENT composition over rounds."""
    stats = buf.round_stats
    if not stats:
        return ""

    tier_order = ["RECENT", "BRONZE", "SILVER", "GOLD"]
    tier_colors_order = [TIER_COLORS[t] for t in tier_order]

    W, H = 640, 220
    ml, mr, mt, mb = 50, 20, 30, 40
    pw = W - ml - mr
    ph = H - mt - mb

    n = len(stats)
    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
                 f'viewBox="0 0 {W} {H}">')
    lines.append('<rect width="100%" height="100%" fill="#1e1e2e"/>')

    # Compute stacked percentages
    fracs: Dict[str, List[float]] = {t: [] for t in tier_order}
    for s in stats:
        total = max(s.total_size, 1)
        for t in tier_order:
            fracs[t].append(s.tier_counts.get(t, 0) / total)

    # Build stacked polygons bottom-up
    # cumulative bottom
    cum_bottom = [0.0] * n
    for tier, color in zip(tier_order, tier_colors_order):
        top_vals = [cum_bottom[i] + fracs[tier][i] for i in range(n)]
        # polygon: left to right on top, right to left on bottom
        pts_top = []
        pts_bot = []
        for i in range(n):
            x = ml + i / (n - 1) * pw if n > 1 else ml
            y_top = mt + ph * (1 - top_vals[i])
            y_bot = mt + ph * (1 - cum_bottom[i])
            pts_top.append((x, y_top))
            pts_bot.append((x, y_bot))
        poly_pts = pts_top + list(reversed(pts_bot))
        poly_str = " ".join(f"{px:.1f},{py:.1f}" for px, py in poly_pts)
        lines.append(f'<polygon points="{poly_str}" fill="{color}" opacity="0.85"/>')
        cum_bottom = top_vals

    # Axes
    x0, y0, x1, y1 = ml, mt, W - mr, H - mb
    lines.append(f'<line x1="{x0}" y1="{y0}" x2="{x0}" y2="{y1}" stroke="#4a4a6a" stroke-width="1"/>')
    lines.append(f'<line x1="{x0}" y1="{y1}" x2="{x1}" y2="{y1}" stroke="#4a4a6a" stroke-width="1"/>')

    # X labels
    for r in range(n):
        gx = ml + r / (n - 1) * pw if n > 1 else ml
        lines.append(f'<text x="{gx:.1f}" y="{y1 + 14}" fill="#9ca3af" font-size="9" '
                     f'text-anchor="middle">R{r}</text>')

    # Y labels
    for v in [0.0, 0.25, 0.5, 0.75, 1.0]:
        gy = mt + ph * (1 - v)
        lines.append(f'<text x="{x0 - 5}" y="{gy + 3:.1f}" fill="#9ca3af" font-size="9" '
                     f'text-anchor="end">{int(v * 100)}%</text>')

    # Legend
    for i, (tier, color) in enumerate(zip(tier_order, tier_colors_order)):
        lx = ml + i * 80
        lines.append(f'<rect x="{lx}" y="{H - mb + 22}" width="12" height="8" fill="{color}" rx="2"/>')
        lines.append(f'<text x="{lx + 15}" y="{H - mb + 30}" fill="#e2e8f0" font-size="9">{tier}</text>')

    # Title
    lines.append(f'<text x="{W // 2}" y="16" fill="#f1f5f9" font-size="12" '
                 f'text-anchor="middle" font-weight="bold">{strategy_name} — Buffer Composition</text>')

    lines.append('</svg>')
    return "\n".join(lines)


def svg_eviction_heatmap(heatmap: Dict[str, List[List[float]]], n_rounds: int) -> str:
    """
    Heatmap: for each strategy (row group), each observed round (y), source round (x),
    fraction of that source round's demos surviving.
    Show as a grid of small heatmaps.
    """
    strategies = list(heatmap.keys())
    n_strats = len(strategies)

    cell = 22
    pad = 8
    label_w = 100
    title_h = 28
    legend_h = 30

    grid_w = n_rounds * cell
    grid_h = n_rounds * cell
    col_w = label_w + grid_w + pad

    W = n_strats * col_w + pad
    H = title_h + grid_h + legend_h + pad * 2

    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
                 f'viewBox="0 0 {W} {H}">')
    lines.append('<rect width="100%" height="100%" fill="#1e1e2e"/>')

    # Title
    lines.append(f'<text x="{W // 2}" y="18" fill="#f1f5f9" font-size="13" '
                 f'text-anchor="middle" font-weight="bold">Eviction Heatmap: Demo Survival by Round</text>')

    def frac_to_color(v: float) -> str:
        # 0 = dark, 1 = bright teal
        r_val = int(v * 34)
        g_val = int(v * 211)
        b_val = int(130 + v * 110)
        return f"rgb({r_val},{g_val},{b_val})"

    for si, name in enumerate(strategies):
        ox = si * col_w + pad
        oy = title_h + pad
        matrix = heatmap[name]

        # Strategy label
        lines.append(f'<text x="{ox + label_w // 2}" y="{oy + grid_h // 2}" fill="#a5b4fc" '
                     f'font-size="11" text-anchor="middle" font-weight="bold" '
                     f'transform="rotate(-90,{ox + label_w // 2},{oy + grid_h // 2})">{name}</text>')

        gox = ox + label_w  # grid origin x

        for r_obs, row in enumerate(matrix):
            for src_r, frac in enumerate(row):
                cx = gox + src_r * cell
                cy = oy + r_obs * cell
                color = frac_to_color(min(frac, 1.0))
                lines.append(f'<rect x="{cx}" y="{cy}" width="{cell - 1}" height="{cell - 1}" '
                              f'fill="{color}" rx="1"/>')

        # Axis labels (only for first strategy to save space)
        if si == 0:
            for r in range(0, n_rounds, 2):
                lx = gox + r * cell + cell // 2
                lines.append(f'<text x="{lx}" y="{oy + grid_h + 14}" fill="#9ca3af" '
                              f'font-size="8" text-anchor="middle">R{r}</text>')
                ly = oy + r * cell + cell // 2 + 3
                lines.append(f'<text x="{gox - 5}" y="{ly:.1f}" fill="#9ca3af" '
                              f'font-size="8" text-anchor="end">R{r}</text>')

    # Legend bar
    leg_y = H - legend_h + 5
    leg_x = pad
    leg_w = min(200, W - pad * 4)
    for i in range(leg_w):
        v = i / leg_w
        c = frac_to_color(v)
        lines.append(f'<rect x="{leg_x + i}" y="{leg_y}" width="1" height="12" fill="{c}"/>')
    lines.append(f'<text x="{leg_x}" y="{leg_y + 24}" fill="#9ca3af" font-size="9">0%</text>')
    lines.append(f'<text x="{leg_x + leg_w}" y="{leg_y + 24}" fill="#9ca3af" '
                 f'font-size="9" text-anchor="end">100% surviving</text>')

    lines.append('</svg>')
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# HTML report
# ---------------------------------------------------------------------------

def _pct(v: float, ndigits: int = 1) -> str:
    return f"{v * 100:.{ndigits}f}%"


def build_html(
    summaries: List[StrategySummary],
    buffers: Dict[str, BaseBuffer],
    heatmap: Dict[str, List[List[float]]],
    n_rounds: int,
) -> str:
    best_strat = max(summaries, key=lambda s: s.final_sr)
    best_diversity = max(summaries, key=lambda s: s.effective_diversity)
    lowest_forgetting = min(summaries, key=lambda s: s.catastrophic_forgetting_rate)
    fastest_conv = min(summaries, key=lambda s: s.convergence_speed)

    # Build summary cards HTML
    def card(title: str, value: str, sub: str, color: str) -> str:
        return f"""
        <div style="background:#1e293b;border-left:4px solid {color};padding:16px 20px;border-radius:6px;min-width:180px">
          <div style="color:#94a3b8;font-size:12px;text-transform:uppercase;letter-spacing:1px">{title}</div>
          <div style="color:{color};font-size:22px;font-weight:700;margin:6px 0">{value}</div>
          <div style="color:#64748b;font-size:12px">{sub}</div>
        </div>"""

    cards_html = "".join([
        card("Best Strategy",      best_strat.name,          f"Final SR {_pct(best_strat.final_sr)}", "#60a5fa"),
        card("Best Diversity",     best_diversity.name,       f"Entropy {best_diversity.effective_diversity:.3f}", "#34d399"),
        card("Lowest Forgetting",  lowest_forgetting.name,   f"Rate {_pct(lowest_forgetting.catastrophic_forgetting_rate)}", "#f97316"),
        card("Fastest Convergence",fastest_conv.name,         f"Round {fastest_conv.convergence_speed}", "#a78bfa"),
    ])

    # Strategy comparison table
    def metric_color(v: float, lo: float, hi: float, inverted: bool = False) -> str:
        if hi == lo:
            return "#e2e8f0"
        t = (v - lo) / (hi - lo)
        if inverted:
            t = 1 - t
        r = int(239 * (1 - t) + 34 * t)
        g = int(68 * (1 - t) + 197 * t)
        b = int(68 * (1 - t) + 94 * t)
        return f"rgb({r},{g},{b})"

    all_div  = [s.effective_diversity for s in summaries]
    all_forg = [s.catastrophic_forgetting_rate for s in summaries]
    all_conv = [s.convergence_speed for s in summaries]
    all_sr   = [s.final_sr for s in summaries]

    table_rows = ""
    for s in summaries:
        col = STRATEGY_COLORS.get(s.name, "#ffffff")
        c_div  = metric_color(s.effective_diversity, min(all_div), max(all_div))
        c_forg = metric_color(s.catastrophic_forgetting_rate, min(all_forg), max(all_forg), inverted=True)
        c_conv = metric_color(s.convergence_speed, min(all_conv), max(all_conv), inverted=True)
        c_sr   = metric_color(s.final_sr, min(all_sr), max(all_sr))
        table_rows += f"""
        <tr>
          <td style="padding:10px 14px;border-bottom:1px solid #1e293b">
            <span style="display:inline-block;width:10px;height:10px;background:{col};border-radius:50%;margin-right:8px"></span>
            <span style="color:#f1f5f9;font-weight:600">{s.name}</span>
          </td>
          <td style="padding:10px 14px;border-bottom:1px solid #1e293b;color:{c_div};text-align:center">{s.effective_diversity:.3f}</td>
          <td style="padding:10px 14px;border-bottom:1px solid #1e293b;color:{c_forg};text-align:center">{_pct(s.catastrophic_forgetting_rate)}</td>
          <td style="padding:10px 14px;border-bottom:1px solid #1e293b;color:{c_conv};text-align:center">Round {s.convergence_speed}</td>
          <td style="padding:10px 14px;border-bottom:1px solid #1e293b;color:{c_sr};text-align:center">{_pct(s.final_sr)}</td>
          <td style="padding:10px 14px;border-bottom:1px solid #1e293b;color:#94a3b8;text-align:center">{s.total_evicted:,}</td>
          <td style="padding:10px 14px;border-bottom:1px solid #1e293b;color:#94a3b8;text-align:center">{s.mean_sampled_unique:.1f}</td>
        </tr>"""

    # Buffer composition SVGs
    comp_svgs = ""
    for name, buf in buffers.items():
        comp_svgs += f"""
        <div style="margin-bottom:24px">
          {svg_buffer_composition(buf, n_rounds, name)}
        </div>"""

    # SR convergence SVG
    sr_svg = svg_sr_convergence(buffers, n_rounds)

    # Eviction heatmap SVG
    hm_svg = svg_eviction_heatmap(heatmap, n_rounds)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1.0"/>
  <title>Episode Replay Buffer Analysis</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background: #0f172a;
      color: #e2e8f0;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      font-size: 14px;
      line-height: 1.6;
      padding: 32px;
    }}
    h1 {{ font-size: 24px; color: #f8fafc; margin-bottom: 6px; }}
    h2 {{ font-size: 16px; color: #94a3b8; text-transform: uppercase; letter-spacing: 1px;
          margin: 32px 0 12px; }}
    .subtitle {{ color: #64748b; margin-bottom: 28px; font-size: 13px; }}
    .cards {{ display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 32px; }}
    .section {{ margin-bottom: 40px; }}
    table {{ width: 100%; border-collapse: collapse; }}
    thead tr {{ background: #1e293b; }}
    thead th {{
      padding: 10px 14px; text-align: left; font-size: 11px;
      text-transform: uppercase; letter-spacing: 0.8px; color: #64748b;
      border-bottom: 2px solid #334155;
    }}
    tbody tr:hover {{ background: #1a2235; }}
    .overflow-x {{ overflow-x: auto; }}
  </style>
</head>
<body>
  <h1>Episode Replay Buffer Strategy Analysis</h1>
  <p class="subtitle">DAgger online learning — {n_rounds} rounds · 5 strategies · capacity {BUFFER_CAPACITY:,}</p>

  <h2>Summary</h2>
  <div class="cards">{cards_html}</div>

  <div class="section">
    <h2>SR Convergence Over Rounds</h2>
    {sr_svg}
  </div>

  <div class="section">
    <h2>Buffer Composition Over Rounds (per strategy)</h2>
    {comp_svgs}
  </div>

  <div class="section">
    <h2>Demo Survival Heatmap</h2>
    <p style="color:#64748b;font-size:12px;margin-bottom:12px">
      Each cell shows the fraction of demos from a source round (x-axis) still in the buffer
      after a given observed round (y-axis). Brighter = more demos surviving.
    </p>
    {hm_svg}
  </div>

  <div class="section">
    <h2>Strategy Comparison</h2>
    <div class="overflow-x">
    <table>
      <thead>
        <tr>
          <th>Strategy</th>
          <th style="text-align:center">Diversity</th>
          <th style="text-align:center">Forgetting Rate</th>
          <th style="text-align:center">Convergence</th>
          <th style="text-align:center">Final SR</th>
          <th style="text-align:center">Evicted</th>
          <th style="text-align:center">Avg Unique Sampled</th>
        </tr>
      </thead>
      <tbody>{table_rows}</tbody>
    </table>
    </div>
  </div>

  <p style="color:#334155;font-size:11px;margin-top:40px">
    Generated by episode_replay_buffer.py · OCI Robot Cloud · {n_rounds} DAgger rounds simulated
  </p>
</body>
</html>"""


# ---------------------------------------------------------------------------
# JSON export
# ---------------------------------------------------------------------------

def build_json(summaries: List[StrategySummary], buffers: Dict[str, BaseBuffer]) -> dict:
    return {
        "buffer_capacity": BUFFER_CAPACITY,
        "strategies": [
            {
                "name": s.name,
                "effective_diversity": round(s.effective_diversity, 4),
                "catastrophic_forgetting_rate": round(s.catastrophic_forgetting_rate, 4),
                "convergence_speed": s.convergence_speed,
                "final_sr": round(s.final_sr, 4),
                "total_evicted": s.total_evicted,
                "mean_sampled_unique": round(s.mean_sampled_unique, 2),
            }
            for s in summaries
        ],
        "per_round": {
            name: [
                {
                    "round": s.round_idx,
                    "size": s.total_size,
                    "diversity": round(s.diversity_score, 4),
                    "sr": round(s.sr_estimate, 4),
                    "evicted": s.evicted_count,
                    "tier_counts": s.tier_counts,
                }
                for s in buf.round_stats
            ]
            for name, buf in buffers.items()
        },
    }


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Episode replay buffer strategy analyzer for DAgger")
    parser.add_argument("--mock", action="store_true", default=True, help="Use mock simulation data")
    parser.add_argument("--n-rounds", type=int, default=12, help="Number of DAgger rounds to simulate")
    parser.add_argument("--output", default="/tmp/episode_replay_buffer.html", help="HTML output path")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    args = parser.parse_args()

    print(f"[episode_replay_buffer] Simulating {args.n_rounds} DAgger rounds (seed={args.seed})")

    buffers = run_simulation(args.n_rounds, args.seed)
    summaries = compute_summaries(buffers, args.n_rounds)
    heatmap = compute_eviction_heatmap(args.n_rounds, args.seed)

    print_comparison_table(summaries)

    # HTML
    html = build_html(summaries, buffers, heatmap, args.n_rounds)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[episode_replay_buffer] HTML report -> {args.output}")

    # JSON
    json_path = args.output.replace(".html", ".json")
    result_json = build_json(summaries, buffers)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result_json, f, indent=2)
    print(f"[episode_replay_buffer] JSON data    -> {json_path}")


if __name__ == "__main__":
    main()
