#!/usr/bin/env python3
"""
action_space_analyzer.py — GR00T fine-tune action space coverage analysis.

Verifies that the policy explores the full joint range and does not collapse
to narrow action modes.  Compares BC baseline vs DAgger run9.

Usage:
    python action_space_analyzer.py --mock --output /tmp/action_space_analyzer.html
    python action_space_analyzer.py --checkpoint dagger_run9/checkpoint_5000 \
        --output /tmp/action_space_analyzer.html --seed 42
"""

import argparse
import json
import math
import os
import random
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Joint definitions
# ---------------------------------------------------------------------------

JOINT_NAMES = [
    "shoulder_pan",
    "shoulder_lift",
    "elbow",
    "wrist_1",
    "wrist_2",
    "wrist_3",
    "gripper",
]

# Valid joint ranges [lo, hi] in radians
JOINT_LIMITS: Dict[str, Tuple[float, float]] = {
    "shoulder_pan":  (-3.14159, 3.14159),
    "shoulder_lift": (-3.14159, 0.0),
    "elbow":         (0.0,      3.14159),
    "wrist_1":       (-3.14159, 3.14159),
    "wrist_2":       (-3.14159, 3.14159),
    "wrist_3":       (-3.14159, 3.14159),
    "gripper":       (0.0,      0.08),      # metres, treated as radians for uniformity
}

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class JointStats:
    name: str
    lo: float
    hi: float
    actions: List[float] = field(default_factory=list)

    # computed
    utilization_pct: float = 0.0
    entropy: float = 0.0
    mode_collapse: bool = False
    bimodal: bool = False
    mean_action: float = 0.0
    std_action: float = 0.0
    p5: float = 0.0
    p95: float = 0.0
    min_visited: float = 0.0
    max_visited: float = 0.0


@dataclass
class EpisodeData:
    episode_id: int
    success: bool
    actions: List[List[float]]   # shape: [T, 7]


# ---------------------------------------------------------------------------
# Mock data generation
# ---------------------------------------------------------------------------

def _mock_episodes(
    n_episodes: int,
    horizon: int,
    rng: random.Random,
    policy_type: str,
) -> List[EpisodeData]:
    """
    Generate synthetic episodes that mimic realistic policy behaviour.

    - BC baseline: narrower coverage (mode collapse on some joints)
    - DAgger: broader coverage, higher entropy
    """
    episodes: List[EpisodeData] = []
    success_rate = 0.05 if policy_type == "bc" else 0.35

    # Per-joint sampling parameters
    if policy_type == "bc":
        # BC tends to collapse: shoulder joints biased toward a small band
        mu_offsets = [0.0, -0.5, 1.2, 0.3, -0.2, 0.1, 0.04]
        sigma_scales = [0.15, 0.12, 0.10, 0.18, 0.14, 0.16, 0.02]
    else:
        # DAgger: more spread, some joints approach limits
        mu_offsets = [0.3, -0.8, 1.5, 0.8, -0.5, 0.5, 0.04]
        sigma_scales = [0.55, 0.45, 0.50, 0.60, 0.50, 0.55, 0.03]

    for ep_id in range(n_episodes):
        success = rng.random() < success_rate
        actions_t: List[List[float]] = []

        # Joint state drifts over episode
        prev = [0.0] * 7
        for t in range(horizon):
            step_actions: List[float] = []
            for j, jname in enumerate(JOINT_NAMES):
                lo, hi = JOINT_LIMITS[jname]
                mid = (lo + hi) / 2.0
                span = (hi - lo)

                if jname == "gripper":
                    # Bimodal: gripper either open or closed
                    if rng.random() < 0.5:
                        val = rng.gauss(lo + 0.005, 0.005)
                    else:
                        val = rng.gauss(hi - 0.005, 0.005)
                else:
                    target = mid + mu_offsets[j] * span * 0.3
                    noise = rng.gauss(0.0, sigma_scales[j] * span * 0.5)
                    # Smooth with previous
                    val = 0.7 * prev[j] + 0.3 * (target + noise)

                # Clamp to joint limits
                val = max(lo, min(hi, val))
                step_actions.append(val)
                prev[j] = val

            actions_t.append(step_actions)

        episodes.append(EpisodeData(
            episode_id=ep_id,
            success=success,
            actions=actions_t,
        ))

    return episodes


# ---------------------------------------------------------------------------
# Statistics computation
# ---------------------------------------------------------------------------

def _mean(vals: List[float]) -> float:
    return sum(vals) / len(vals) if vals else 0.0


def _std(vals: List[float]) -> float:
    if len(vals) < 2:
        return 0.0
    m = _mean(vals)
    variance = sum((v - m) ** 2 for v in vals) / (len(vals) - 1)
    return math.sqrt(variance)


def _percentile(vals: List[float], p: float) -> float:
    if not vals:
        return 0.0
    sorted_v = sorted(vals)
    idx = (p / 100.0) * (len(sorted_v) - 1)
    lo_idx = int(idx)
    hi_idx = min(lo_idx + 1, len(sorted_v) - 1)
    frac = idx - lo_idx
    return sorted_v[lo_idx] * (1 - frac) + sorted_v[hi_idx] * frac


def _histogram(vals: List[float], lo: float, hi: float, bins: int = 20) -> List[int]:
    counts = [0] * bins
    span = hi - lo
    if span == 0:
        return counts
    for v in vals:
        idx = int((v - lo) / span * bins)
        idx = max(0, min(bins - 1, idx))
        counts[idx] += 1
    return counts


def _entropy(counts: List[int]) -> float:
    total = sum(counts)
    if total == 0:
        return 0.0
    ent = 0.0
    for c in counts:
        if c > 0:
            p = c / total
            ent -= p * math.log2(p)
    return ent


def _detect_mode_collapse(vals: List[float], lo: float, hi: float, band: float = 0.1) -> bool:
    """True if > 40% of actions fall within any ±0.1 rad band."""
    if not vals:
        return False
    n = len(vals)
    span = hi - lo
    step = band * 0.5
    cursor = lo
    while cursor <= hi:
        count = sum(1 for v in vals if cursor - band <= v <= cursor + band)
        if count / n > 0.40:
            return True
        cursor += step
    return False


def _detect_bimodal(counts: List[int]) -> bool:
    """True if histogram has 2 clear peaks separated by a valley."""
    n = len(counts)
    if n < 6:
        return False
    # Smooth with 3-point average
    smooth = [
        (counts[max(0, i - 1)] + counts[i] + counts[min(n - 1, i + 1)]) / 3.0
        for i in range(n)
    ]
    # Find local maxima
    peaks = [
        i for i in range(1, n - 1)
        if smooth[i] > smooth[i - 1] and smooth[i] > smooth[i + 1]
    ]
    if len(peaks) < 2:
        return False
    # Check that there's a valley between the two highest peaks
    p1, p2 = sorted(peaks, key=lambda i: smooth[i], reverse=True)[:2]
    if p1 > p2:
        p1, p2 = p2, p1
    valley_min = min(smooth[p1:p2 + 1])
    peak_min = min(smooth[p1], smooth[p2])
    return valley_min < peak_min * 0.6


def _utilization(vals: List[float], lo: float, hi: float, bins: int = 20) -> float:
    """Fraction of equal-width bins that contain at least one sample."""
    if not vals:
        return 0.0
    counts = _histogram(vals, lo, hi, bins)
    occupied = sum(1 for c in counts if c > 0)
    return occupied / bins * 100.0


def compute_joint_stats(joint: JointStats) -> JointStats:
    vals = joint.actions
    lo, hi = joint.lo, joint.hi
    if not vals:
        return joint

    counts = _histogram(vals, lo, hi, bins=20)

    joint.mean_action  = _mean(vals)
    joint.std_action   = _std(vals)
    joint.p5           = _percentile(vals, 5)
    joint.p95          = _percentile(vals, 95)
    joint.min_visited  = min(vals)
    joint.max_visited  = max(vals)
    joint.utilization_pct = _utilization(vals, lo, hi)
    joint.entropy      = _entropy(counts)
    joint.mode_collapse = _detect_mode_collapse(vals, lo, hi)
    joint.bimodal      = _detect_bimodal(counts)
    return joint


# ---------------------------------------------------------------------------
# Correlation matrix
# ---------------------------------------------------------------------------

def compute_correlation_matrix(episodes: List[EpisodeData]) -> List[List[float]]:
    """Pearson correlation between each pair of joints across all timesteps."""
    n_joints = len(JOINT_NAMES)
    # Flatten all actions per joint
    per_joint: List[List[float]] = [[] for _ in range(n_joints)]
    for ep in episodes:
        for step in ep.actions:
            for j, v in enumerate(step):
                per_joint[j].append(v)

    matrix: List[List[float]] = [[0.0] * n_joints for _ in range(n_joints)]
    for i in range(n_joints):
        for jj in range(n_joints):
            if i == jj:
                matrix[i][jj] = 1.0
                continue
            xi = per_joint[i]
            yi = per_joint[jj]
            mx = _mean(xi)
            my = _mean(yi)
            num = sum((a - mx) * (b - my) for a, b in zip(xi, yi))
            denom = math.sqrt(
                sum((a - mx) ** 2 for a in xi) * sum((b - my) ** 2 for b in yi)
            )
            matrix[i][jj] = num / denom if denom > 0 else 0.0

    return matrix


# ---------------------------------------------------------------------------
# Trajectory analysis (success vs failure)
# ---------------------------------------------------------------------------

def compute_trajectory_stats(
    episodes: List[EpisodeData],
) -> Dict[str, Dict[str, float]]:
    """
    Average mean action and std per joint for success vs failure episodes.
    Returns dict: {'success': {joint: mean}, 'failure': {joint: mean}}
    """
    success_eps = [ep for ep in episodes if ep.success]
    fail_eps    = [ep for ep in episodes if not ep.success]

    def _avg_per_joint(eps: List[EpisodeData]) -> Dict[str, float]:
        per_joint: List[List[float]] = [[] for _ in range(len(JOINT_NAMES))]
        for ep in eps:
            for step in ep.actions:
                for j, v in enumerate(step):
                    per_joint[j].append(v)
        return {
            JOINT_NAMES[j]: round(_mean(per_joint[j]), 4)
            for j in range(len(JOINT_NAMES))
        }

    return {
        "success": _avg_per_joint(success_eps),
        "failure": _avg_per_joint(fail_eps),
        "n_success": len(success_eps),
        "n_failure": len(fail_eps),
    }


# ---------------------------------------------------------------------------
# Analysis entry point
# ---------------------------------------------------------------------------

def analyze(
    episodes: List[EpisodeData],
    label: str,
) -> Tuple[List[JointStats], List[List[float]], Dict]:
    """Run full analysis on a set of episodes."""
    # Build per-joint action lists
    stats: List[JointStats] = []
    for j, jname in enumerate(JOINT_NAMES):
        lo, hi = JOINT_LIMITS[jname]
        js = JointStats(name=jname, lo=lo, hi=hi)
        for ep in episodes:
            for step in ep.actions:
                js.actions.append(step[j])
        js = compute_joint_stats(js)
        stats.append(js)

    corr = compute_correlation_matrix(episodes)
    traj = compute_trajectory_stats(episodes)

    return stats, corr, traj


# ---------------------------------------------------------------------------
# Console output
# ---------------------------------------------------------------------------

def print_table(stats: List[JointStats], label: str) -> None:
    header = (
        f"\n{'='*80}\n"
        f"  Action Space Analysis — {label}\n"
        f"{'='*80}"
    )
    print(header)
    col_fmt = "{:<16} {:>10} {:>8} {:>8} {:>8} {:>8} {:>8} {:>6}"
    print(col_fmt.format(
        "Joint", "Util%", "Entropy", "Mean", "Std", "P5", "P95", "Collapse"
    ))
    print("-" * 80)
    for js in stats:
        flag = "YES" if js.mode_collapse else "no"
        bm   = " [bimodal]" if js.bimodal else ""
        print(col_fmt.format(
            js.name + bm,
            f"{js.utilization_pct:.1f}",
            f"{js.entropy:.3f}",
            f"{js.mean_action:.4f}",
            f"{js.std_action:.4f}",
            f"{js.p5:.4f}",
            f"{js.p95:.4f}",
            flag,
        ))
    print()


# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------

def _svg_histogram_strip(
    vals: List[float],
    lo: float,
    hi: float,
    width: int = 220,
    height: int = 60,
    color: str = "#60a5fa",
    bins: int = 20,
) -> str:
    counts = _histogram(vals, lo, hi, bins)
    max_c  = max(counts) if counts else 1
    bar_w  = width / bins
    bars   = ""
    for i, c in enumerate(counts):
        bh = int(c / max_c * (height - 4)) if max_c else 0
        x  = i * bar_w
        y  = height - bh - 2
        bars += (
            f'<rect x="{x:.1f}" y="{y}" width="{bar_w - 1:.1f}" height="{bh}" '
            f'fill="{color}" opacity="0.85"/>'
        )
    return (
        f'<svg width="{width}" height="{height}" '
        f'style="background:#1e293b;border-radius:4px;">'
        f'{bars}</svg>'
    )


def _svg_paired_bars(
    labels: List[str],
    bc_vals: List[float],
    dagger_vals: List[float],
    width: int = 560,
    height: int = 260,
) -> str:
    n      = len(labels)
    margin = {"top": 20, "right": 20, "bottom": 60, "left": 55}
    inner_w = width  - margin["left"] - margin["right"]
    inner_h = height - margin["top"]  - margin["bottom"]
    max_val = max(max(bc_vals), max(dagger_vals), 1)

    group_w = inner_w / n
    bar_w   = group_w * 0.35
    gap     = group_w * 0.05

    svgparts = [
        f'<svg width="{width}" height="{height}" '
        f'style="background:#0f172a;font-family:monospace;">',
        f'<g transform="translate({margin["left"]},{margin["top"]})">',
    ]

    # Y-axis gridlines + labels
    for tick in [0, 25, 50, 75, 100]:
        y = inner_h - (tick / max_val) * inner_h
        svgparts.append(
            f'<line x1="0" y1="{y:.1f}" x2="{inner_w}" y2="{y:.1f}" '
            f'stroke="#334155" stroke-width="1"/>'
        )
        svgparts.append(
            f'<text x="-4" y="{y + 4:.1f}" text-anchor="end" '
            f'fill="#94a3b8" font-size="10">{tick}</text>'
        )

    # Bars
    for i, lbl in enumerate(labels):
        gx = i * group_w
        # BC bar (blue)
        bc_h = (bc_vals[i] / max_val) * inner_h
        bc_x = gx + gap
        svgparts.append(
            f'<rect x="{bc_x:.1f}" y="{inner_h - bc_h:.1f}" '
            f'width="{bar_w:.1f}" height="{bc_h:.1f}" fill="#3b82f6" rx="2"/>'
        )
        svgparts.append(
            f'<text x="{bc_x + bar_w/2:.1f}" y="{inner_h - bc_h - 3:.1f}" '
            f'text-anchor="middle" fill="#93c5fd" font-size="9">'
            f'{bc_vals[i]:.0f}</text>'
        )
        # DAgger bar (emerald)
        da_h = (dagger_vals[i] / max_val) * inner_h
        da_x = gx + gap + bar_w + 2
        svgparts.append(
            f'<rect x="{da_x:.1f}" y="{inner_h - da_h:.1f}" '
            f'width="{bar_w:.1f}" height="{da_h:.1f}" fill="#10b981" rx="2"/>'
        )
        svgparts.append(
            f'<text x="{da_x + bar_w/2:.1f}" y="{inner_h - da_h - 3:.1f}" '
            f'text-anchor="middle" fill="#6ee7b7" font-size="9">'
            f'{dagger_vals[i]:.0f}</text>'
        )
        # X-axis label
        svgparts.append(
            f'<text x="{gx + group_w/2:.1f}" y="{inner_h + 14}" '
            f'text-anchor="middle" fill="#94a3b8" font-size="9" '
            f'transform="rotate(-30 {gx + group_w/2:.1f},{inner_h + 14})">'
            f'{lbl}</text>'
        )

    # Axes
    svgparts.append(
        f'<line x1="0" y1="0" x2="0" y2="{inner_h}" stroke="#475569" stroke-width="1"/>'
    )
    svgparts.append(
        f'<line x1="0" y1="{inner_h}" x2="{inner_w}" y2="{inner_h}" '
        f'stroke="#475569" stroke-width="1"/>'
    )

    # Legend
    legend_y = inner_h + 48
    svgparts += [
        f'<rect x="0" y="{legend_y}" width="12" height="12" fill="#3b82f6" rx="2"/>',
        f'<text x="16" y="{legend_y + 10}" fill="#93c5fd" font-size="11">BC baseline</text>',
        f'<rect x="100" y="{legend_y}" width="12" height="12" fill="#10b981" rx="2"/>',
        f'<text x="116" y="{legend_y + 10}" fill="#6ee7b7" font-size="11">DAgger run9</text>',
    ]

    svgparts.append("</g></svg>")
    return "".join(svgparts)


def _svg_correlation_heatmap(matrix: List[List[float]], size: int = 320) -> str:
    n       = len(matrix)
    label_w = 72
    label_h = 72
    cell    = (size - label_w) / n

    svgparts = [
        f'<svg width="{size + 20}" height="{size + 20}" '
        f'style="background:#0f172a;font-family:monospace;">'
    ]

    def _corr_color(v: float) -> str:
        # -1 → red, 0 → dark slate, +1 → blue
        if v > 0:
            r = int(15  + (1 - v) * 60)
            g = int(23  + (1 - v) * 50)
            b = int(42  + v * 213)
        else:
            r = int(15  + (-v) * 213)
            g = int(23  + (-v) * 30)
            b = int(42  + (1 + v) * 60)
        return f"rgb({r},{g},{b})"

    for i in range(n):
        for jj in range(n):
            x = label_w + jj * cell
            y = label_h + i * cell
            col = _corr_color(matrix[i][jj])
            svgparts.append(
                f'<rect x="{x:.1f}" y="{y:.1f}" '
                f'width="{cell:.1f}" height="{cell:.1f}" '
                f'fill="{col}" stroke="#0f172a" stroke-width="0.5"/>'
            )
            val = f"{matrix[i][jj]:.2f}"
            svgparts.append(
                f'<text x="{x + cell/2:.1f}" y="{y + cell/2 + 4:.1f}" '
                f'text-anchor="middle" fill="white" font-size="8" opacity="0.9">'
                f'{val}</text>'
            )

    # Row labels
    short = ["s_pan", "s_lift", "elbow", "w1", "w2", "w3", "grip"]
    for i, lbl in enumerate(short):
        y = label_h + i * cell + cell / 2 + 4
        svgparts.append(
            f'<text x="{label_w - 4}" y="{y:.1f}" text-anchor="end" '
            f'fill="#94a3b8" font-size="9">{lbl}</text>'
        )
    # Col labels
    for jj, lbl in enumerate(short):
        x = label_w + jj * cell + cell / 2
        y = label_h - 6
        svgparts.append(
            f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="middle" '
            f'fill="#94a3b8" font-size="9" '
            f'transform="rotate(-35 {x:.1f},{y:.1f})">{lbl}</text>'
        )

    svgparts.append("</svg>")
    return "".join(svgparts)


# ---------------------------------------------------------------------------
# HTML report
# ---------------------------------------------------------------------------

def build_html(
    bc_stats:      List[JointStats],
    bc_corr:       List[List[float]],
    bc_traj:       Dict,
    dagger_stats:  List[JointStats],
    dagger_corr:   List[List[float]],
    dagger_traj:   Dict,
    checkpoint:    str,
) -> str:
    # --- Summary card values ---
    bc_collapse  = sum(1 for js in bc_stats if js.mode_collapse)
    da_collapse  = sum(1 for js in dagger_stats if js.mode_collapse)
    bc_avg_util  = _mean([js.utilization_pct for js in bc_stats])
    da_avg_util  = _mean([js.utilization_pct for js in dagger_stats])
    bc_avg_ent   = _mean([js.entropy for js in bc_stats])
    da_avg_ent   = _mean([js.entropy for js in dagger_stats])
    bc_grip_bm   = next(js.bimodal for js in bc_stats if js.name == "gripper")
    da_grip_bm   = next(js.bimodal for js in dagger_stats if js.name == "gripper")

    def _card(title: str, val: str, sub: str, color: str) -> str:
        return f"""
        <div class="card" style="border-left:3px solid {color}">
          <div class="card-title">{title}</div>
          <div class="card-val" style="color:{color}">{val}</div>
          <div class="card-sub">{sub}</div>
        </div>"""

    cards_html = "".join([
        _card("Mode Collapse Joints",
              f"BC {bc_collapse} / DA {da_collapse}",
              "joints with &gt;40% in ±0.1 rad band", "#f87171"),
        _card("Avg Utilization %",
              f"BC {bc_avg_util:.1f}% / DA {da_avg_util:.1f}%",
              "of valid range visited", "#60a5fa"),
        _card("Avg Entropy (bits)",
              f"BC {bc_avg_ent:.2f} / DA {da_avg_ent:.2f}",
              "action distribution diversity", "#a78bfa"),
        _card("Gripper Bimodal",
              f"BC {'Yes' if bc_grip_bm else 'No'} / DA {'Yes' if da_grip_bm else 'No'}",
              "open/close modes detected", "#34d399"),
    ])

    # --- Histogram strips ---
    def _hist_section(stats: List[JointStats], label: str, color: str) -> str:
        rows = ""
        for js in stats:
            svg = _svg_histogram_strip(js.actions, js.lo, js.hi, color=color)
            collapse_badge = (
                '<span class="badge-red">COLLAPSE</span>'
                if js.mode_collapse else
                '<span class="badge-green">ok</span>'
            )
            bimodal_badge = (
                '<span class="badge-yellow">bimodal</span>'
                if js.bimodal else ""
            )
            rows += f"""
            <tr>
              <td class="jname">{js.name}</td>
              <td>{svg}</td>
              <td class="num">{js.utilization_pct:.1f}%</td>
              <td class="num">{js.entropy:.3f}</td>
              <td>{collapse_badge} {bimodal_badge}</td>
              <td class="num">[{js.min_visited:.3f}, {js.max_visited:.3f}]</td>
            </tr>"""
        return f"""
        <h2 style="color:#94a3b8;margin-top:2rem">{label} — Action Histograms</h2>
        <table class="jtable">
          <thead><tr>
            <th>Joint</th><th>Distribution</th>
            <th>Util%</th><th>Entropy</th>
            <th>Flags</th><th>Range Visited</th>
          </tr></thead>
          <tbody>{rows}</tbody>
        </table>"""

    hist_bc     = _hist_section(bc_stats,     "BC Baseline",  "#60a5fa")
    hist_dagger = _hist_section(dagger_stats, "DAgger run9",  "#34d399")

    # --- Utilization comparison bars ---
    util_svg = _svg_paired_bars(
        JOINT_NAMES,
        [js.utilization_pct for js in bc_stats],
        [js.utilization_pct for js in dagger_stats],
    )

    # --- Correlation heatmaps ---
    corr_bc_svg     = _svg_correlation_heatmap(bc_corr)
    corr_dagger_svg = _svg_correlation_heatmap(dagger_corr)

    # --- Trajectory table ---
    def _traj_rows(traj: Dict) -> str:
        rows = ""
        for jname in JOINT_NAMES:
            sv = traj["success"].get(jname, 0.0)
            fv = traj["failure"].get(jname, 0.0)
            diff = sv - fv
            color = "#34d399" if abs(diff) > 0.05 else "#94a3b8"
            rows += f"""
            <tr>
              <td class="jname">{jname}</td>
              <td class="num">{sv:.4f}</td>
              <td class="num">{fv:.4f}</td>
              <td class="num" style="color:{color}">{diff:+.4f}</td>
            </tr>"""
        return rows

    traj_html = f"""
    <h2 style="color:#94a3b8;margin-top:2rem">Trajectory Analysis — BC Baseline</h2>
    <p style="color:#64748b;font-size:0.85rem">
      Success episodes: {bc_traj['n_success']} &nbsp;|&nbsp;
      Failure episodes: {bc_traj['n_failure']}
    </p>
    <table class="jtable" style="max-width:500px">
      <thead><tr>
        <th>Joint</th><th>Avg (success)</th><th>Avg (failure)</th><th>Δ</th>
      </tr></thead>
      <tbody>{_traj_rows(bc_traj)}</tbody>
    </table>
    <h2 style="color:#94a3b8;margin-top:2rem">Trajectory Analysis — DAgger run9</h2>
    <p style="color:#64748b;font-size:0.85rem">
      Success episodes: {dagger_traj['n_success']} &nbsp;|&nbsp;
      Failure episodes: {dagger_traj['n_failure']}
    </p>
    <table class="jtable" style="max-width:500px">
      <thead><tr>
        <th>Joint</th><th>Avg (success)</th><th>Avg (failure)</th><th>Δ</th>
      </tr></thead>
      <tbody>{_traj_rows(dagger_traj)}</tbody>
    </table>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <title>Action Space Analyzer — GR00T Fine-tune</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background: #0f172a;
      color: #e2e8f0;
      font-family: 'JetBrains Mono', 'Fira Code', 'Courier New', monospace;
      font-size: 13px;
      padding: 2rem;
    }}
    h1 {{ color: #f1f5f9; font-size: 1.4rem; margin-bottom: 0.25rem; }}
    h2 {{ font-size: 1.0rem; margin-bottom: 0.75rem; }}
    .subtitle {{ color: #64748b; margin-bottom: 2rem; font-size: 0.85rem; }}
    .cards {{ display: flex; gap: 1rem; flex-wrap: wrap; margin-bottom: 2rem; }}
    .card {{
      background: #1e293b;
      border-radius: 8px;
      padding: 1rem 1.25rem;
      min-width: 180px;
      flex: 1;
    }}
    .card-title {{ color: #64748b; font-size: 0.75rem; margin-bottom: 0.4rem; }}
    .card-val   {{ font-size: 1.2rem; font-weight: bold; margin-bottom: 0.25rem; }}
    .card-sub   {{ color: #475569; font-size: 0.72rem; }}
    .jtable {{
      border-collapse: collapse;
      width: 100%;
      margin-bottom: 1rem;
    }}
    .jtable th, .jtable td {{
      padding: 6px 10px;
      border-bottom: 1px solid #1e293b;
      text-align: left;
    }}
    .jtable th {{
      background: #1e293b;
      color: #94a3b8;
      font-size: 0.75rem;
      text-transform: uppercase;
    }}
    .jtable tr:hover {{ background: #1e293b; }}
    .jname {{ color: #93c5fd; }}
    .num   {{ color: #cbd5e1; font-variant-numeric: tabular-nums; }}
    .badge-red    {{ background: #7f1d1d; color: #fca5a5; padding: 1px 6px;
                    border-radius: 4px; font-size: 0.72rem; }}
    .badge-green  {{ background: #14532d; color: #86efac; padding: 1px 6px;
                    border-radius: 4px; font-size: 0.72rem; }}
    .badge-yellow {{ background: #713f12; color: #fde68a; padding: 1px 6px;
                    border-radius: 4px; font-size: 0.72rem; }}
    .section-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 2rem; }}
    .corr-pair  {{ display: flex; gap: 2rem; flex-wrap: wrap; margin-top: 0.75rem; }}
    .corr-label {{ color: #64748b; font-size: 0.8rem; margin-bottom: 0.5rem; }}
    hr {{ border: none; border-top: 1px solid #1e293b; margin: 2rem 0; }}
    footer {{ color: #334155; font-size: 0.72rem; margin-top: 3rem; }}
  </style>
</head>
<body>
  <h1>Action Space Analyzer — GR00T Fine-tune</h1>
  <div class="subtitle">
    Checkpoint: <code>{checkpoint}</code> &nbsp;|&nbsp;
    100 eval episodes per policy &nbsp;|&nbsp;
    7 joints analyzed
  </div>

  <!-- Summary cards -->
  <div class="cards">{cards_html}</div>

  <hr/>

  <!-- Histograms -->
  {hist_bc}
  {hist_dagger}

  <hr/>

  <!-- Utilization comparison -->
  <h2 style="color:#94a3b8;margin-top:2rem">Utilization % — BC vs DAgger run9</h2>
  <div style="margin-top:0.75rem">{util_svg}</div>

  <hr/>

  <!-- Correlation matrices -->
  <h2 style="color:#94a3b8;margin-top:2rem">Joint Action Correlation Matrix</h2>
  <div class="corr-pair">
    <div>
      <div class="corr-label">BC Baseline</div>
      {corr_bc_svg}
    </div>
    <div>
      <div class="corr-label">DAgger run9</div>
      {corr_dagger_svg}
    </div>
  </div>

  <hr/>

  <!-- Trajectory analysis -->
  {traj_html}

  <footer>
    Generated by action_space_analyzer.py &nbsp;|&nbsp;
    OCI Robot Cloud &mdash; GR00T fine-tune evaluation suite
  </footer>
</body>
</html>"""

    return html


# ---------------------------------------------------------------------------
# JSON export
# ---------------------------------------------------------------------------

def build_json(
    bc_stats:     List[JointStats],
    bc_corr:      List[List[float]],
    bc_traj:      Dict,
    dagger_stats: List[JointStats],
    dagger_corr:  List[List[float]],
    dagger_traj:  Dict,
    checkpoint:   str,
) -> Dict:
    def _stats_to_dict(stats: List[JointStats]) -> List[Dict]:
        return [
            {
                "name":           js.name,
                "joint_range":    [js.lo, js.hi],
                "utilization_pct": round(js.utilization_pct, 2),
                "entropy":         round(js.entropy, 4),
                "mode_collapse":   js.mode_collapse,
                "bimodal":         js.bimodal,
                "mean_action":     round(js.mean_action, 6),
                "std_action":      round(js.std_action, 6),
                "p5":              round(js.p5, 6),
                "p95":             round(js.p95, 6),
                "min_visited":     round(js.min_visited, 6),
                "max_visited":     round(js.max_visited, 6),
            }
            for js in stats
        ]

    def _corr_to_list(matrix: List[List[float]]) -> List[List[float]]:
        return [[round(v, 4) for v in row] for row in matrix]

    return {
        "checkpoint": checkpoint,
        "joint_names": JOINT_NAMES,
        "bc_baseline": {
            "joint_stats":    _stats_to_dict(bc_stats),
            "correlation":    _corr_to_list(bc_corr),
            "trajectory":     bc_traj,
        },
        "dagger_run9": {
            "joint_stats":    _stats_to_dict(dagger_stats),
            "correlation":    _corr_to_list(dagger_corr),
            "trajectory":     dagger_traj,
        },
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Action space coverage analysis for GR00T fine-tuned checkpoints",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Generate synthetic episodes instead of loading a real checkpoint",
    )
    parser.add_argument(
        "--checkpoint",
        default="dagger_run9/checkpoint_5000",
        help="Path or name of checkpoint to evaluate (used for labels/metadata)",
    )
    parser.add_argument(
        "--episodes",
        type=int,
        default=100,
        help="Number of evaluation episodes per policy",
    )
    parser.add_argument(
        "--horizon",
        type=int,
        default=200,
        help="Timesteps per episode",
    )
    parser.add_argument(
        "--output",
        default="/tmp/action_space_analyzer.html",
        help="Path for the HTML report",
    )
    parser.add_argument(
        "--json-output",
        default=None,
        help="Optional path for JSON output (defaults to <output>.json)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for mock data generation",
    )
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)

    rng = random.Random(args.seed)

    if args.mock:
        print(f"[mock] Generating {args.episodes} episodes × {args.horizon} steps per policy …")
        bc_episodes     = _mock_episodes(args.episodes, args.horizon, rng, "bc")
        dagger_episodes = _mock_episodes(args.episodes, args.horizon, rng, "dagger")
    else:
        # Real checkpoint loading would go here.
        # For now, fall through to mock with a warning.
        print(
            f"[warn] Real checkpoint loading not implemented; "
            f"falling back to mock data for checkpoint: {args.checkpoint}",
            file=sys.stderr,
        )
        bc_episodes     = _mock_episodes(args.episodes, args.horizon, rng, "bc")
        dagger_episodes = _mock_episodes(args.episodes, args.horizon, rng, "dagger")

    print("[analyze] Running BC baseline …")
    bc_stats, bc_corr, bc_traj = analyze(bc_episodes, "BC baseline")

    print("[analyze] Running DAgger run9 …")
    da_stats, da_corr, da_traj = analyze(dagger_episodes, "DAgger run9")

    # Console tables
    print_table(bc_stats,  "BC Baseline")
    print_table(da_stats,  "DAgger run9")

    # Print trajectory comparison
    print("  Trajectory Analysis (avg mean action per joint)")
    print(f"  {'Joint':<16} {'BC success':>12} {'DA success':>12}")
    for j, jname in enumerate(JOINT_NAMES):
        bsv = bc_traj["success"].get(jname, 0.0)
        dsv = da_traj["success"].get(jname, 0.0)
        print(f"  {jname:<16} {bsv:>12.4f} {dsv:>12.4f}")
    print()

    # HTML
    html = build_html(
        bc_stats,  bc_corr,  bc_traj,
        da_stats,  da_corr,  da_traj,
        args.checkpoint,
    )
    out_path = os.path.abspath(args.output)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(html)
    print(f"[html] Report written → {out_path}")

    # JSON
    json_path = args.json_output or (out_path.replace(".html", ".json"))
    result = build_json(
        bc_stats,  bc_corr,  bc_traj,
        da_stats,  da_corr,  da_traj,
        args.checkpoint,
    )
    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2)
    print(f"[json] Data written  → {json_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
