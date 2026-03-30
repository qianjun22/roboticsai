"""
replay_buffer_manager.py — Experience replay buffer manager for online robot learning.

Manages DAgger/RL replay buffers with priority sampling, deduplication, and HTML analytics.

Usage:
    python replay_buffer_manager.py --mock --output /tmp/replay_buffer_manager.html --seed 42
"""

from __future__ import annotations

import argparse
import hashlib
import math
import random
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class Experience:
    exp_id: str
    task: str
    episode: int
    step: int
    obs_hash: str          # 8-char hex
    action_norm: float     # 0-1
    reward: float
    priority: float
    timestamp: float       # unix time
    source: str            # "human" | "policy" | "synthetic"


@dataclass
class BufferConfig:
    max_size: int = 50000
    alpha: float = 0.6     # priority exponent
    beta: float = 0.4      # importance-sampling exponent
    dedup_threshold: float = 0.95
    min_priority: float = 0.01


# ---------------------------------------------------------------------------
# Mock data generator
# ---------------------------------------------------------------------------

def generate_mock_buffer(n: int = 2000, seed: int = 42) -> List[Experience]:
    rng = random.Random(seed)
    tasks = ["pick_and_place", "stack_blocks", "open_drawer"]
    sources = ["human", "policy", "synthetic"]
    source_weights = [0.20, 0.60, 0.20]

    # Per-task reward distributions (mean, std)
    task_reward_params = {
        "pick_and_place": (0.65, 0.18),
        "stack_blocks":   (0.48, 0.22),
        "open_drawer":    (0.71, 0.15),
    }

    # Pre-generate a pool of obs_hashes smaller than n to create duplicates
    hash_pool_size = int(n * 0.82)
    hash_pool = [
        hashlib.md5(f"{seed}-obs-{i}".encode()).hexdigest()[:8]
        for i in range(hash_pool_size)
    ]

    now = time.time()
    experiences: List[Experience] = []

    for i in range(n):
        task = rng.choices(tasks, weights=[0.4, 0.35, 0.25])[0]
        source = rng.choices(sources, weights=source_weights)[0]

        # Log-normal priority
        raw_pri = rng.lognormvariate(mu=-0.8, sigma=0.7)
        priority = max(0.01, min(5.0, raw_pri))

        mu, sigma = task_reward_params[task]
        reward = max(0.0, min(1.0, rng.gauss(mu, sigma)))

        action_norm = rng.uniform(0.0, 1.0)

        # Timestamps spread over ~7 days with some recency bias
        age_seconds = rng.betavariate(2, 5) * 7 * 86400
        timestamp = now - age_seconds

        obs_hash = rng.choice(hash_pool)

        exp = Experience(
            exp_id=f"exp_{i:06d}",
            task=task,
            episode=rng.randint(0, n // 20),
            step=rng.randint(0, 200),
            obs_hash=obs_hash,
            action_norm=action_norm,
            reward=reward,
            priority=priority,
            timestamp=timestamp,
            source=source,
        )
        experiences.append(exp)

    return experiences


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------

def compute_buffer_stats(
    experiences: List[Experience],
    config: BufferConfig,
) -> Dict:
    n = len(experiences)
    if n == 0:
        return {}

    source_counts: Dict[str, int] = {}
    task_counts: Dict[str, Dict] = {}
    hashes: List[str] = []
    priorities: List[float] = []
    timestamps: List[float] = []

    for exp in experiences:
        source_counts[exp.source] = source_counts.get(exp.source, 0) + 1
        hashes.append(exp.obs_hash)
        priorities.append(exp.priority)
        timestamps.append(exp.timestamp)

        if exp.task not in task_counts:
            task_counts[exp.task] = {"count": 0, "rewards": [], "priorities": []}
        task_counts[exp.task]["count"] += 1
        task_counts[exp.task]["rewards"].append(exp.reward)
        task_counts[exp.task]["priorities"].append(exp.priority)

    # Duplicate rate
    total_hashes = len(hashes)
    unique_hashes = len(set(hashes))
    duplicate_rate = 1.0 - unique_hashes / total_hashes if total_hashes > 0 else 0.0

    # Priority histogram (10 bins, log scale capped at 0..5)
    p_min, p_max = 0.0, 5.0
    bin_width = (p_max - p_min) / 10
    hist_bins = [0] * 10
    for p in priorities:
        idx = min(int((p - p_min) / bin_width), 9)
        hist_bins[idx] += 1

    # Temporal coverage
    oldest = min(timestamps)
    newest = max(timestamps)
    temporal_coverage_hours = (newest - oldest) / 3600.0

    # Per-task aggregated stats
    task_stats = {}
    for task, data in task_counts.items():
        c = data["count"]
        avg_r = sum(data["rewards"]) / c
        avg_p = sum(data["priorities"]) / c
        task_stats[task] = {
            "count": c,
            "avg_reward": avg_r,
            "avg_priority": avg_p,
        }

    # Human percentage
    human_pct = (source_counts.get("human", 0) / n * 100) if n > 0 else 0.0
    avg_priority = sum(priorities) / n if n > 0 else 0.0

    return {
        "total_size": n,
        "source_counts": source_counts,
        "priority_histogram": hist_bins,
        "duplicate_rate": duplicate_rate,
        "task_distribution": task_stats,
        "temporal_coverage_hours": temporal_coverage_hours,
        "human_pct": human_pct,
        "avg_priority": avg_priority,
        "oldest_ts": oldest,
        "newest_ts": newest,
    }


def priority_sample(
    experiences: List[Experience],
    n: int,
    config: BufferConfig,
) -> List[Experience]:
    if not experiences:
        return []
    n = min(n, len(experiences))
    weights = [max(exp.priority, config.min_priority) ** config.alpha for exp in experiences]
    total = sum(weights)
    probs = [w / total for w in weights]

    rng = random.Random()
    chosen = rng.choices(experiences, weights=probs, k=n)
    return chosen


def detect_staleness(
    experiences: List[Experience],
    n_recent: int = 500,
) -> List[Tuple[Experience, bool]]:
    if not experiences:
        return []

    timestamps = sorted([e.timestamp for e in experiences])
    p90_idx = int(len(timestamps) * 0.10)
    age_threshold = timestamps[p90_idx] if p90_idx < len(timestamps) else timestamps[0]

    results = []
    for exp in experiences:
        stale = exp.timestamp < age_threshold
        results.append((exp, stale))
    return results


# ---------------------------------------------------------------------------
# HTML report generation
# ---------------------------------------------------------------------------

def _bar_chart_svg(
    labels: List[str],
    values: List[int],
    colors: List[str],
    width: int = 520,
    height: int = 160,
) -> str:
    max_val = max(values) if values else 1
    bar_area_w = width - 140
    bar_h = 28
    gap = 12
    total_h = len(labels) * (bar_h + gap) + gap
    svg_h = max(height, total_h + 20)

    bars = ""
    for i, (label, val, color) in enumerate(zip(labels, values, colors)):
        y = gap + i * (bar_h + gap)
        bar_w = max(2, int(val / max_val * bar_area_w))
        bars += (
            f'<text x="0" y="{y + bar_h - 8}" fill="#94a3b8" font-size="12" '
            f'font-family="monospace">{label}</text>'
            f'<rect x="130" y="{y}" width="{bar_w}" height="{bar_h}" fill="{color}" rx="3"/>'
            f'<text x="{130 + bar_w + 6}" y="{y + bar_h - 8}" fill="#e2e8f0" '
            f'font-size="12" font-family="monospace">{val}</text>'
        )

    return (
        f'<svg width="{width}" height="{svg_h}" xmlns="http://www.w3.org/2000/svg">'
        f'{bars}</svg>'
    )


def _priority_hist_svg(
    hist_bins: List[int],
    width: int = 520,
    height: int = 160,
) -> str:
    n_bins = len(hist_bins)
    max_val = max(hist_bins) if hist_bins else 1
    pad_l, pad_r, pad_t, pad_b = 40, 20, 20, 30
    plot_w = width - pad_l - pad_r
    plot_h = height - pad_t - pad_b
    bar_w = plot_w / n_bins

    bars = ""
    for i, count in enumerate(hist_bins):
        bh = int(count / max_val * plot_h) if max_val > 0 else 0
        x = pad_l + i * bar_w
        y = pad_t + plot_h - bh
        lo = i * 0.5
        hi = lo + 0.5
        label = f"{lo:.1f}"
        bars += (
            f'<rect x="{x + 1}" y="{y}" width="{bar_w - 2}" height="{bh}" '
            f'fill="#C74634" rx="2" opacity="0.85"/>'
            f'<text x="{x + bar_w / 2}" y="{pad_t + plot_h + 16}" fill="#64748b" '
            f'font-size="9" text-anchor="middle" font-family="monospace">{label}</text>'
        )

    # Y axis
    axis = (
        f'<line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t + plot_h}" '
        f'stroke="#334155" stroke-width="1"/>'
        f'<line x1="{pad_l}" y1="{pad_t + plot_h}" x2="{pad_l + plot_w}" '
        f'y2="{pad_t + plot_h}" stroke="#334155" stroke-width="1"/>'
        f'<text x="{pad_l - 6}" y="{pad_t + 6}" fill="#64748b" font-size="9" '
        f'text-anchor="end" font-family="monospace">{max_val}</text>'
        f'<text x="{pad_l - 6}" y="{pad_t + plot_h}" fill="#64748b" font-size="9" '
        f'text-anchor="end" font-family="monospace">0</text>'
    )

    return (
        f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">'
        f'{axis}{bars}</svg>'
    )


def _scatter_svg(
    points: List[Tuple[float, float, str]],  # (reward, priority, source)
    width: int = 520,
    height: int = 220,
) -> str:
    source_colors = {"human": "#38bdf8", "policy": "#a78bfa", "synthetic": "#4ade80"}
    pad_l, pad_r, pad_t, pad_b = 45, 20, 20, 35

    plot_w = width - pad_l - pad_r
    plot_h = height - pad_t - pad_b

    max_p = max((p for _, p, _ in points), default=1.0)

    dots = ""
    for reward, priority, source in points:
        cx = pad_l + reward * plot_w
        cy = pad_t + plot_h - (priority / max_p) * plot_h
        color = source_colors.get(source, "#94a3b8")
        dots += f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="3" fill="{color}" opacity="0.65"/>'

    # Axes
    axes = (
        f'<line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t + plot_h}" '
        f'stroke="#334155" stroke-width="1"/>'
        f'<line x1="{pad_l}" y1="{pad_t + plot_h}" x2="{pad_l + plot_w}" '
        f'y2="{pad_t + plot_h}" stroke="#334155" stroke-width="1"/>'
        f'<text x="{pad_l + plot_w / 2}" y="{height - 4}" fill="#64748b" '
        f'font-size="10" text-anchor="middle" font-family="monospace">reward</text>'
        f'<text x="12" y="{pad_t + plot_h / 2}" fill="#64748b" font-size="10" '
        f'text-anchor="middle" font-family="monospace" '
        f'transform="rotate(-90,12,{pad_t + plot_h / 2})">priority</text>'
        # Axis labels
        f'<text x="{pad_l}" y="{pad_t + plot_h + 14}" fill="#64748b" font-size="9" '
        f'text-anchor="middle" font-family="monospace">0.0</text>'
        f'<text x="{pad_l + plot_w}" y="{pad_t + plot_h + 14}" fill="#64748b" '
        f'font-size="9" text-anchor="middle" font-family="monospace">1.0</text>'
    )

    # Legend
    legend = ""
    for i, (src, color) in enumerate(source_colors.items()):
        lx = pad_l + 10 + i * 120
        ly = pad_t + 8
        legend += (
            f'<circle cx="{lx}" cy="{ly}" r="5" fill="{color}"/>'
            f'<text x="{lx + 10}" y="{ly + 4}" fill="#94a3b8" font-size="10" '
            f'font-family="monospace">{src}</text>'
        )

    return (
        f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">'
        f'{axes}{dots}{legend}</svg>'
    )


def generate_html_report(
    experiences: List[Experience],
    config: BufferConfig,
    stats: Dict,
) -> str:
    # --- KPI values ---
    buf_size = stats.get("total_size", 0)
    dup_rate = stats.get("duplicate_rate", 0.0) * 100
    human_pct = stats.get("human_pct", 0.0)
    avg_pri = stats.get("avg_priority", 0.0)

    # --- Source bar chart ---
    src_counts = stats.get("source_counts", {})
    src_labels = ["human", "policy", "synthetic"]
    src_values = [src_counts.get(s, 0) for s in src_labels]
    src_colors = ["#38bdf8", "#a78bfa", "#4ade80"]
    bar_chart_html = _bar_chart_svg(src_labels, src_values, src_colors)

    # --- Priority histogram ---
    hist_bins = stats.get("priority_histogram", [0] * 10)
    hist_html = _priority_hist_svg(hist_bins)

    # --- Scatter: reward vs priority (200 sampled points) ---
    rng = random.Random(0)
    sample = rng.sample(experiences, min(200, len(experiences)))
    scatter_pts = [(e.reward, e.priority, e.source) for e in sample]
    scatter_html = _scatter_svg(scatter_pts)

    # --- Staleness per task ---
    stale_results = detect_staleness(experiences)
    stale_by_task: Dict[str, Dict] = {}
    for exp, stale in stale_results:
        if exp.task not in stale_by_task:
            stale_by_task[exp.task] = {"total": 0, "stale": 0}
        stale_by_task[exp.task]["total"] += 1
        if stale:
            stale_by_task[exp.task]["stale"] += 1

    # --- Task table rows ---
    task_rows = ""
    task_dist = stats.get("task_distribution", {})
    for task, tdata in sorted(task_dist.items()):
        count = tdata["count"]
        avg_r = tdata["avg_reward"]
        avg_p = tdata["avg_priority"]
        sd = stale_by_task.get(task, {})
        stale_pct = (sd.get("stale", 0) / sd.get("total", 1) * 100) if sd else 0.0
        task_rows += f"""
        <tr>
          <td>{task}</td>
          <td>{count}</td>
          <td>{avg_r:.3f}</td>
          <td>{avg_p:.3f}</td>
          <td>{stale_pct:.1f}%</td>
        </tr>"""

    temporal_h = stats.get("temporal_coverage_hours", 0.0)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>Replay Buffer Manager — Analytics</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: #1e293b;
    color: #e2e8f0;
    font-family: 'Segoe UI', system-ui, sans-serif;
    font-size: 14px;
    padding: 24px;
  }}
  h1 {{ color: #C74634; font-size: 22px; margin-bottom: 6px; letter-spacing: 0.5px; }}
  h2 {{ color: #C74634; font-size: 15px; margin: 28px 0 12px; text-transform: uppercase;
        letter-spacing: 1px; border-bottom: 1px solid #334155; padding-bottom: 6px; }}
  .subtitle {{ color: #64748b; font-size: 12px; margin-bottom: 24px; }}
  .kpi-row {{
    display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 8px;
  }}
  .kpi-card {{
    background: #0f172a;
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 16px 24px;
    min-width: 140px;
    flex: 1;
  }}
  .kpi-label {{ color: #64748b; font-size: 11px; text-transform: uppercase;
                letter-spacing: 0.8px; margin-bottom: 8px; }}
  .kpi-value {{ color: #f1f5f9; font-size: 26px; font-weight: 700; }}
  .kpi-unit  {{ color: #94a3b8; font-size: 13px; margin-left: 4px; }}
  .panel {{
    background: #0f172a;
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 20px;
    margin-bottom: 20px;
  }}
  .two-col {{ display: flex; gap: 20px; flex-wrap: wrap; }}
  .two-col .panel {{ flex: 1; min-width: 300px; }}
  table {{ width: 100%; border-collapse: collapse; }}
  thead tr {{ background: #1e293b; }}
  th {{ color: #94a3b8; font-size: 11px; text-transform: uppercase;
        letter-spacing: 0.8px; padding: 8px 12px; text-align: left;
        border-bottom: 1px solid #334155; }}
  td {{ padding: 9px 12px; border-bottom: 1px solid #1e293b; color: #e2e8f0; }}
  tbody tr:hover {{ background: #1e293b; }}
  .footer {{ color: #475569; font-size: 11px; text-align: center;
             margin-top: 32px; padding-top: 16px; border-top: 1px solid #1e293b; }}
  svg {{ display: block; }}
</style>
</head>
<body>

<h1>OCI Robot Cloud — Replay Buffer Manager</h1>
<div class="subtitle">
  Buffer analytics dashboard &nbsp;|&nbsp; Temporal coverage: {temporal_h:.1f} h
  &nbsp;|&nbsp; max_size={config.max_size:,} &nbsp;&alpha;={config.alpha}
  &nbsp;&beta;={config.beta}
</div>

<!-- KPI Cards -->
<div class="kpi-row">
  <div class="kpi-card">
    <div class="kpi-label">Buffer Size</div>
    <div class="kpi-value">{buf_size:,}</div>
  </div>
  <div class="kpi-card">
    <div class="kpi-label">Duplicate Rate</div>
    <div class="kpi-value">{dup_rate:.1f}<span class="kpi-unit">%</span></div>
  </div>
  <div class="kpi-card">
    <div class="kpi-label">Human Data</div>
    <div class="kpi-value">{human_pct:.1f}<span class="kpi-unit">%</span></div>
  </div>
  <div class="kpi-card">
    <div class="kpi-label">Avg Priority</div>
    <div class="kpi-value">{avg_pri:.3f}</div>
  </div>
</div>

<div class="two-col">
  <div class="panel">
    <h2>Source Breakdown</h2>
    {bar_chart_html}
  </div>
  <div class="panel">
    <h2>Priority Distribution</h2>
    {hist_html}
  </div>
</div>

<div class="panel">
  <h2>Reward vs Priority (200 sampled)</h2>
  {scatter_html}
</div>

<div class="panel">
  <h2>Per-Task Statistics</h2>
  <table>
    <thead>
      <tr>
        <th>Task</th>
        <th>Count</th>
        <th>Avg Reward</th>
        <th>Avg Priority</th>
        <th>Staleness %</th>
      </tr>
    </thead>
    <tbody>
      {task_rows}
    </tbody>
  </table>
</div>

<div class="footer">
  OCI Robot Cloud &mdash; Replay Buffer Manager &mdash; {buf_size} experiences
  &mdash; Generated by replay_buffer_manager.py
</div>
</body>
</html>"""
    return html


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Replay Buffer Manager — analytics for DAgger/RL experience buffers"
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        default=False,
        help="Generate a mock buffer for demonstration",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="/tmp/replay_buffer_manager.html",
        help="Path for the HTML report output",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for mock data generation",
    )
    parser.add_argument(
        "--n",
        type=int,
        default=2000,
        help="Number of mock experiences to generate",
    )
    args = parser.parse_args()

    config = BufferConfig()

    if args.mock:
        print(f"[ReplayBufferManager] Generating {args.n} mock experiences (seed={args.seed})...")
        experiences = generate_mock_buffer(n=args.n, seed=args.seed)
    else:
        print("[ReplayBufferManager] No data source specified. Use --mock to generate demo data.")
        return

    print(f"[ReplayBufferManager] Computing buffer statistics ({len(experiences)} experiences)...")
    stats = compute_buffer_stats(experiences, config)

    print(f"[ReplayBufferManager] Buffer size      : {stats['total_size']:,}")
    print(f"[ReplayBufferManager] Duplicate rate   : {stats['duplicate_rate'] * 100:.1f}%")
    print(f"[ReplayBufferManager] Human data       : {stats['human_pct']:.1f}%")
    print(f"[ReplayBufferManager] Avg priority     : {stats['avg_priority']:.4f}")
    print(f"[ReplayBufferManager] Temporal coverage: {stats['temporal_coverage_hours']:.1f} h")
    print(f"[ReplayBufferManager] Source counts    : {stats['source_counts']}")

    # Demo: priority sample
    sampled = priority_sample(experiences, n=64, config=config)
    avg_sampled_pri = sum(e.priority for e in sampled) / len(sampled)
    print(f"[ReplayBufferManager] Priority sample (n=64) avg priority: {avg_sampled_pri:.4f}")

    # Demo: staleness
    stale_results = detect_staleness(experiences)
    n_stale = sum(1 for _, stale in stale_results if stale)
    print(f"[ReplayBufferManager] Stale experiences (oldest 10%): {n_stale}/{len(experiences)}")

    print(f"[ReplayBufferManager] Generating HTML report -> {args.output}")
    html = generate_html_report(experiences, config, stats)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[ReplayBufferManager] Report saved: {args.output}")


if __name__ == "__main__":
    main()
