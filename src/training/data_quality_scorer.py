"""
data_quality_scorer.py — Episode quality scoring for the OCI Robot Cloud pipeline.

Scores incoming DAgger/BC episodes across 6 weighted dimensions before they enter
the training dataset, preventing low-quality demonstrations from polluting the pipeline.

SCORING DIMENSIONS (each 0–10, weighted to sum to 1.0)
-------------------------------------------------------
  1. Trajectory Smoothness   (w=0.20) — low joint-velocity jitter → high score
  2. Task Completion         (w=0.25) — did cube_z reach LIFT_THRESH (0.78m)?
  3. Episode Length          (w=0.15) — ideal window [10, 500] frames
  4. Joint Limit Margin      (w=0.15) — distance from Franka joint limits (larger = safer)
  5. Data Diversity          (w=0.15) — L2 distance of mean joint pos from dataset centroid
  6. Expert Intervention     (w=0.10) — for DAgger eps: lower beta_actual = cleaner demo

COMPOSITE SCORE & GRADES
-------------------------
  Composite = weighted sum of dimension scores (0–10)
  A ≥ 8.0  |  B ≥ 6.0  |  C ≥ 4.0  |  D < 4.0
  Accept threshold: score ≥ 5.0 (override with --min-score)

EPISODE DIRECTORY FORMAT (from dagger_train.py / save_lerobot_episode)
-----------------------------------------------------------------------
  <episodes-dir>/
    episode_000000/
      actions.npy    (N, 9) float32 — expert joint targets
      states.npy     (N, 9) float32 — actual robot joint states
      frames.npy     (N, 256, 256, 3) uint8 — camera (optional, not used here)
      meta.json      optional — {"success": bool, "beta_actual": float}

CLI USAGE
---------
  # Score all episodes in a directory, write HTML report
  python src/training/data_quality_scorer.py \\
      --episodes-dir /tmp/dagger_run6/episodes \\
      --output /tmp/quality_report.html

  # Run with a custom acceptance threshold
  python src/training/data_quality_scorer.py \\
      --episodes-dir /tmp/dagger_run6/episodes \\
      --output /tmp/quality_report.html \\
      --min-score 6.0

  # Generate 30 synthetic episodes and score them (no real data needed)
  python src/training/data_quality_scorer.py --mock

  # Output CSV only (no HTML)
  python src/training/data_quality_scorer.py \\
      --episodes-dir /tmp/dagger_run6/episodes \\
      --csv-only --output /tmp/quality_scores.csv

INTEGRATION WITH dagger_train.py
---------------------------------
  from src.training.data_quality_scorer import score_episode, DEFAULT_MIN_SCORE

  # Before adding episode to dataset:
  result = score_episode(ep_dir, dataset_centroid=existing_centroid)
  if result["composite"] >= DEFAULT_MIN_SCORE:
      save_lerobot_episode(...)
  else:
      print(f"[quality] Rejected ep (score={result['composite']:.2f}, grade={result['grade']})")

DEPENDENCIES
------------
  numpy (already in roboticsai environment) — all else is stdlib
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import random
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

# ── Constants (match dagger_train.py) ─────────────────────────────────────────
TABLE_Z = 0.7
CUBE_HALF = 0.025
LIFT_THRESH = TABLE_Z + 0.08          # 0.78 m — success threshold

MIN_FRAMES = 10
MAX_FRAMES = 500
IDEAL_MIN_FRAMES = 30                  # below ideal but still acceptable
IDEAL_MAX_FRAMES = 300                 # above ideal but still acceptable

# Franka Emika Panda joint limits (radians) — 7 arm DOF + 2 finger
# Source: official Franka spec; finger joints [0, 0.08] m mapped to radians approx
JOINT_LOWER = np.array([-2.8973, -1.7628, -2.8973, -3.0718, -2.8973, -0.0175, -2.8973,
                          0.0,     0.0])
JOINT_UPPER = np.array([ 2.8973,  1.7628,  2.8973, -0.0698,  2.8973,  3.7525,  2.8973,
                          0.08,    0.08])
JOINT_RANGE = JOINT_UPPER - JOINT_LOWER   # used to normalise margin score

DEFAULT_MIN_SCORE = 5.0

WEIGHTS = {
    "smoothness":   0.20,
    "completion":   0.25,
    "length":       0.15,
    "joint_margin": 0.15,
    "diversity":    0.15,
    "intervention": 0.10,
}
assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9, "Weights must sum to 1.0"

DIMENSION_LABELS = {
    "smoothness":   "Trajectory Smoothness",
    "completion":   "Task Completion",
    "length":       "Episode Length",
    "joint_margin": "Joint Limit Margin",
    "diversity":    "Data Diversity",
    "intervention": "Expert Intervention Ratio",
}


# ── Scoring functions ──────────────────────────────────────────────────────────

def score_smoothness(states: np.ndarray) -> float:
    """Low velocity variance (jitter) → high score.

    Velocity = finite difference of joint positions.  We use the mean of
    per-joint velocity variance across the episode.  High variance = jittery.
    Empirical range: near-zero for smooth demos, up to ~0.5 for noisy ones.
    """
    if len(states) < 2:
        return 0.0
    vel = np.diff(states, axis=0)            # (N-1, 9)
    var_per_joint = np.var(vel, axis=0)      # (9,)
    mean_var = float(np.mean(var_per_joint))
    # Empirical sigmoid mapping: mean_var=0 → 10, mean_var=0.05 → ~5, mean_var≥0.15 → ~1
    score = 10.0 / (1.0 + math.exp(40.0 * (mean_var - 0.05)))
    return float(np.clip(score, 0.0, 10.0))


def score_completion(states: np.ndarray, success: Optional[bool] = None) -> float:
    """Did the cube reach lift threshold?

    Primary: use 'success' flag from meta.json if present.
    Fallback: check if any state's 3rd joint (proxy for ee height) exceeds a
    heuristic tied to the lift threshold — or accept success=True at full credit.

    Returns 10.0 for success, partial credit for near-lift, 0.0 for clear failure.
    """
    if success is True:
        return 10.0
    if success is False:
        # Partial credit: how far did the end-effector get?
        # Use joint 2 (shoulder_lift) as a rough proxy — higher = closer to lift.
        max_j2 = float(np.max(states[:, 2])) if states.shape[1] > 2 else 0.0
        # Map [-2.9, 2.9] to [0, 3] partial score for failures
        partial = float(np.clip((max_j2 + 2.9) / 5.8 * 3.0, 0.0, 3.0))
        return partial
    # No meta available — heuristic from states
    # Treat as success if the joint configuration visits a near-lifted pose
    # (joint[1] < -0.5 often corresponds to arm reaching forward-up)
    min_j1 = float(np.min(states[:, 1])) if states.shape[1] > 1 else 0.0
    if min_j1 < -1.0:
        return 8.0   # likely success
    elif min_j1 < -0.5:
        return 5.0
    return 2.0


def score_length(n_frames: int) -> float:
    """Penalise episodes that are too short or too long."""
    if n_frames < MIN_FRAMES:
        return 0.0   # hard reject range — still score but very low
    if n_frames > MAX_FRAMES:
        # Gradually penalise beyond max
        excess = n_frames - MAX_FRAMES
        return float(max(0.0, 5.0 - excess * 0.02))
    # In [MIN_FRAMES, MAX_FRAMES]: peak score in [IDEAL_MIN_FRAMES, IDEAL_MAX_FRAMES]
    if IDEAL_MIN_FRAMES <= n_frames <= IDEAL_MAX_FRAMES:
        return 10.0
    if n_frames < IDEAL_MIN_FRAMES:
        # Linear ramp from MIN_FRAMES (0) to IDEAL_MIN_FRAMES (10)
        frac = (n_frames - MIN_FRAMES) / (IDEAL_MIN_FRAMES - MIN_FRAMES)
        return float(np.clip(frac * 10.0, 0.0, 10.0))
    # n_frames > IDEAL_MAX_FRAMES but ≤ MAX_FRAMES
    frac = 1.0 - (n_frames - IDEAL_MAX_FRAMES) / (MAX_FRAMES - IDEAL_MAX_FRAMES)
    return float(np.clip(frac * 10.0 + (1.0 - frac) * 5.0, 0.0, 10.0))


def score_joint_margin(states: np.ndarray) -> float:
    """Larger margin from joint limits throughout the episode → higher score.

    For each frame, compute the minimum normalised distance to any joint limit.
    Take the mean over the episode.  margin=0 means a joint hit its limit;
    margin=1 means maximally centred.
    """
    # Normalised position within joint range: 0 = at limit, 1 = at opposite limit
    norm = (states - JOINT_LOWER) / JOINT_RANGE   # (N, 9), in [0, 1] nominally
    norm = np.clip(norm, 0.0, 1.0)
    # Distance to nearest limit: min(norm, 1-norm) ∈ [0, 0.5]
    dist_to_limit = np.minimum(norm, 1.0 - norm)  # (N, 9)
    # Per-frame worst joint (closest to any limit)
    min_margin_per_frame = np.min(dist_to_limit, axis=1)  # (N,)
    mean_margin = float(np.mean(min_margin_per_frame))
    # mean_margin ∈ [0, 0.5]; map to [0, 10]
    return float(np.clip(mean_margin * 20.0, 0.0, 10.0))


def score_diversity(states: np.ndarray, dataset_centroid: Optional[np.ndarray]) -> float:
    """How different is this episode from the existing dataset centroid?

    Computed as L2 distance between this episode's mean joint position and the
    dataset centroid.  Episodes far from centroid contribute novel coverage.

    If no centroid is known (first episode / no dataset), return 5.0 (neutral).
    """
    if dataset_centroid is None or len(dataset_centroid) == 0:
        return 5.0
    ep_mean = np.mean(states, axis=0)   # (9,)
    centroid = np.asarray(dataset_centroid, dtype=np.float32)
    if centroid.shape != ep_mean.shape:
        return 5.0
    l2 = float(np.linalg.norm(ep_mean - centroid))
    # l2 range: 0 = identical to centroid (bad), ~2.0 = very different (great)
    # Sigmoid-ish mapping centred around 0.5
    score = 10.0 * (1.0 - math.exp(-l2 / 0.8))
    return float(np.clip(score, 0.0, 10.0))


def score_intervention(beta_actual: Optional[float]) -> float:
    """For DAgger episodes: lower beta_actual (less robot autonomy) = cleaner demo.

    beta_actual=0.0 means fully expert (ideal for early training).
    beta_actual=1.0 means fully autonomous (no expert correction — noisier).
    If unknown (BC episodes), return 8.0 (assume expert demo).
    """
    if beta_actual is None:
        return 8.0
    beta = float(np.clip(beta_actual, 0.0, 1.0))
    # 0.0 → 10, 0.5 → 5, 1.0 → 0
    return float((1.0 - beta) * 10.0)


# ── Episode loader ─────────────────────────────────────────────────────────────

@dataclass
class EpisodeMeta:
    success: Optional[bool] = None
    beta_actual: Optional[float] = None
    n_frames: int = 0
    episode_dir: str = ""


def load_episode(ep_dir: Path) -> Tuple[np.ndarray, EpisodeMeta]:
    """Load states.npy (or actions.npy fallback) + optional meta.json."""
    meta = EpisodeMeta(episode_dir=str(ep_dir))

    states_path = ep_dir / "states.npy"
    actions_path = ep_dir / "actions.npy"
    if states_path.exists():
        states = np.load(states_path).astype(np.float32)
    elif actions_path.exists():
        states = np.load(actions_path).astype(np.float32)
    else:
        raise FileNotFoundError(f"No states.npy or actions.npy in {ep_dir}")

    # Ensure shape (N, 9) — handle edge cases
    if states.ndim == 1:
        states = states.reshape(1, -1)
    if states.shape[1] < 9:
        pad = np.zeros((states.shape[0], 9 - states.shape[1]), dtype=np.float32)
        states = np.concatenate([states, pad], axis=1)
    states = states[:, :9]

    meta.n_frames = len(states)

    meta_path = ep_dir / "meta.json"
    if meta_path.exists():
        try:
            with open(meta_path) as f:
                d = json.load(f)
            meta.success = d.get("success")
            meta.beta_actual = d.get("beta_actual")
        except (json.JSONDecodeError, OSError):
            pass

    return states, meta


# ── Core scoring entry point ───────────────────────────────────────────────────

def score_episode(
    ep_dir: Path,
    dataset_centroid: Optional[np.ndarray] = None,
) -> Dict:
    """Score a single episode directory and return a result dict.

    Returns
    -------
    dict with keys:
        episode_dir, n_frames, success, beta_actual,
        dimensions: {name: float},
        composite: float,
        grade: str,
        accepted: bool
    """
    ep_dir = Path(ep_dir)
    states, meta = load_episode(ep_dir)

    dims = {
        "smoothness":   score_smoothness(states),
        "completion":   score_completion(states, meta.success),
        "length":       score_length(meta.n_frames),
        "joint_margin": score_joint_margin(states),
        "diversity":    score_diversity(states, dataset_centroid),
        "intervention": score_intervention(meta.beta_actual),
    }

    composite = sum(WEIGHTS[k] * v for k, v in dims.items())
    composite = float(np.clip(composite, 0.0, 10.0))

    grade = "A" if composite >= 8.0 else "B" if composite >= 6.0 else "C" if composite >= 4.0 else "D"
    accepted = composite >= DEFAULT_MIN_SCORE

    return {
        "episode_dir": str(ep_dir),
        "episode_name": ep_dir.name,
        "n_frames": meta.n_frames,
        "success": meta.success,
        "beta_actual": meta.beta_actual,
        "dimensions": dims,
        "composite": composite,
        "grade": grade,
        "accepted": accepted,
    }


def compute_dataset_centroid(ep_dirs: List[Path]) -> Optional[np.ndarray]:
    """Compute mean joint position across all episodes in the dataset."""
    means = []
    for ep_dir in ep_dirs:
        try:
            states, _ = load_episode(ep_dir)
            means.append(np.mean(states, axis=0))
        except (FileNotFoundError, OSError, ValueError):
            continue
    if not means:
        return None
    return np.mean(np.stack(means), axis=0)


# ── Batch scoring ──────────────────────────────────────────────────────────────

def score_directory(
    episodes_dir: Path,
    min_score: float = DEFAULT_MIN_SCORE,
) -> List[Dict]:
    """Score all episode subdirectories under episodes_dir."""
    ep_dirs = sorted([d for d in episodes_dir.iterdir() if d.is_dir()])
    if not ep_dirs:
        print(f"[scorer] No subdirectories found in {episodes_dir}", file=sys.stderr)
        return []

    print(f"[scorer] Found {len(ep_dirs)} episode directories")
    print(f"[scorer] Computing dataset centroid …", end=" ", flush=True)
    centroid = compute_dataset_centroid(ep_dirs)
    print("done")

    results = []
    for ep_dir in ep_dirs:
        try:
            r = score_episode(ep_dir, dataset_centroid=centroid)
            r["accepted"] = r["composite"] >= min_score
            results.append(r)
            status = "ACCEPT" if r["accepted"] else "REJECT"
            print(f"  {r['episode_name']:25s}  composite={r['composite']:4.2f}  "
                  f"grade={r['grade']}  [{status}]")
        except (FileNotFoundError, OSError, ValueError) as exc:
            print(f"  [warn] Could not score {ep_dir.name}: {exc}", file=sys.stderr)

    n_accept = sum(1 for r in results if r["accepted"])
    n_reject = len(results) - n_accept
    print(f"\n[scorer] Results: {n_accept} accepted / {n_reject} rejected "
          f"({100*n_accept/max(len(results),1):.1f}% pass rate)")
    return results


# ── CSV export ─────────────────────────────────────────────────────────────────

def write_csv(results: List[Dict], output_path: Path) -> None:
    """Write scoring results to a CSV file."""
    fieldnames = (
        ["episode_name", "n_frames", "composite", "grade", "accepted",
         "success", "beta_actual"]
        + list(WEIGHTS.keys())
    )
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            row = {
                "episode_name": r["episode_name"],
                "n_frames":     r["n_frames"],
                "composite":    f"{r['composite']:.4f}",
                "grade":        r["grade"],
                "accepted":     r["accepted"],
                "success":      r["success"],
                "beta_actual":  r["beta_actual"] if r["beta_actual"] is not None else "",
            }
            for dim in WEIGHTS:
                row[dim] = f"{r['dimensions'][dim]:.4f}"
            writer.writerow(row)
    print(f"[scorer] CSV written to {output_path}")


# ── HTML report ────────────────────────────────────────────────────────────────

_GRADE_COLORS = {"A": "#34d399", "B": "#60a5fa", "C": "#fbbf24", "D": "#f87171"}
_DIM_COLORS   = ["#818cf8", "#34d399", "#60a5fa", "#fbbf24", "#f472b6", "#fb923c"]

def _bar_svg(values: List[float], labels: List[str], colors: List[str],
             width: int = 320, height: int = 160) -> str:
    """Inline SVG horizontal bar chart."""
    n = len(values)
    if n == 0:
        return ""
    bar_h = max(12, (height - 20) // n - 4)
    row_h = bar_h + 4
    actual_height = n * row_h + 20
    max_val = 10.0
    bar_area = width - 140

    lines = [f'<svg width="{width}" height="{actual_height}" '
             f'xmlns="http://www.w3.org/2000/svg" style="display:block">']
    for i, (val, label, color) in enumerate(zip(values, labels, colors)):
        y = i * row_h + 10
        bar_w = int(val / max_val * bar_area)
        # Label
        lines.append(f'  <text x="0" y="{y + bar_h - 2}" '
                     f'font-size="10" fill="#9ca3af" font-family="monospace">'
                     f'{label[:16]}</text>')
        # Bar background
        lines.append(f'  <rect x="130" y="{y}" width="{bar_area}" height="{bar_h}" '
                     f'rx="2" fill="#1f2937"/>')
        # Bar fill
        if bar_w > 0:
            lines.append(f'  <rect x="130" y="{y}" width="{bar_w}" height="{bar_h}" '
                         f'rx="2" fill="{color}"/>')
        # Value text
        lines.append(f'  <text x="{130 + bar_area + 4}" y="{y + bar_h - 2}" '
                     f'font-size="10" fill="#e5e7eb" font-family="monospace">'
                     f'{val:.1f}</text>')
    lines.append('</svg>')
    return "\n".join(lines)


def _donut_svg(grade_counts: Dict[str, int], total: int,
               size: int = 200) -> str:
    """Inline SVG donut chart for grade distribution."""
    cx = cy = size // 2
    r_outer = size * 0.42
    r_inner = size * 0.25
    grades = ["A", "B", "C", "D"]
    counts = [grade_counts.get(g, 0) for g in grades]
    colors = [_GRADE_COLORS[g] for g in grades]

    lines = [f'<svg width="{size}" height="{size}" xmlns="http://www.w3.org/2000/svg">']
    start_angle = -math.pi / 2
    for g, count, color in zip(grades, counts, colors):
        if count == 0:
            continue
        sweep = 2 * math.pi * count / max(total, 1)
        end_angle = start_angle + sweep
        large = 1 if sweep > math.pi else 0
        x1 = cx + r_outer * math.cos(start_angle)
        y1 = cy + r_outer * math.sin(start_angle)
        x2 = cx + r_outer * math.cos(end_angle)
        y2 = cy + r_outer * math.sin(end_angle)
        xi1 = cx + r_inner * math.cos(end_angle)
        yi1 = cy + r_inner * math.sin(end_angle)
        xi2 = cx + r_inner * math.cos(start_angle)
        yi2 = cy + r_inner * math.sin(start_angle)
        d = (f"M {x1:.1f} {y1:.1f} "
             f"A {r_outer:.1f} {r_outer:.1f} 0 {large} 1 {x2:.1f} {y2:.1f} "
             f"L {xi1:.1f} {yi1:.1f} "
             f"A {r_inner:.1f} {r_inner:.1f} 0 {large} 0 {xi2:.1f} {yi2:.1f} Z")
        lines.append(f'  <path d="{d}" fill="{color}" stroke="#111827" stroke-width="1.5"/>')
        # Label at midpoint
        mid = start_angle + sweep / 2
        lx = cx + (r_outer + r_inner) / 2 * math.cos(mid)
        ly = cy + (r_outer + r_inner) / 2 * math.sin(mid)
        lines.append(f'  <text x="{lx:.1f}" y="{ly:.1f}" text-anchor="middle" '
                     f'dominant-baseline="middle" font-size="11" font-weight="bold" '
                     f'fill="#111827" font-family="monospace">{g}:{count}</text>')
        start_angle = end_angle

    # Centre text
    lines.append(f'  <text x="{cx}" y="{cy - 6}" text-anchor="middle" '
                 f'font-size="13" fill="#e5e7eb" font-family="monospace">{total}</text>')
    lines.append(f'  <text x="{cx}" y="{cy + 10}" text-anchor="middle" '
                 f'font-size="9" fill="#9ca3af" font-family="monospace">episodes</text>')
    lines.append('</svg>')
    return "\n".join(lines)


def write_html_report(
    results: List[Dict],
    output_path: Path,
    min_score: float = DEFAULT_MIN_SCORE,
) -> None:
    """Write a dark-theme HTML quality report with inline SVG charts."""
    n_accept = sum(1 for r in results if r["accepted"])
    n_reject = len(results) - n_accept
    pass_rate = 100 * n_accept / max(len(results), 1)
    mean_score = sum(r["composite"] for r in results) / max(len(results), 1)

    grade_counts: Dict[str, int] = {"A": 0, "B": 0, "C": 0, "D": 0}
    for r in results:
        grade_counts[r["grade"]] += 1

    dim_keys   = list(WEIGHTS.keys())
    dim_labels = [DIMENSION_LABELS[k] for k in dim_keys]

    # --- Build episode cards ---
    cards_html = []
    for r in results:
        border_color = "#34d399" if r["accepted"] else "#f87171"
        grade_color  = _GRADE_COLORS.get(r["grade"], "#9ca3af")
        dim_vals  = [r["dimensions"][k] for k in dim_keys]
        bar_chart = _bar_svg(dim_vals, dim_labels, _DIM_COLORS, width=360, height=180)
        status_badge = ('<span style="color:#34d399;font-weight:bold">ACCEPT</span>'
                        if r["accepted"] else
                        '<span style="color:#f87171;font-weight:bold">REJECT</span>')
        success_str = ("yes" if r["success"] is True else
                       "no"  if r["success"] is False else "?")
        beta_str = f"{r['beta_actual']:.2f}" if r["beta_actual"] is not None else "—"
        cards_html.append(f"""
  <div style="border:1px solid {border_color};border-radius:8px;padding:14px;
              background:#1f2937;margin-bottom:12px">
    <div style="display:flex;justify-content:space-between;align-items:center;
                margin-bottom:10px">
      <span style="font-family:monospace;font-size:13px;color:#e5e7eb">
        {r['episode_name']}</span>
      <span style="display:flex;gap:10px;align-items:center">
        <span style="font-size:20px;font-weight:bold;color:{grade_color}">{r['grade']}</span>
        <span style="font-size:13px;color:#9ca3af">{r['composite']:.2f}/10</span>
        {status_badge}
      </span>
    </div>
    <div style="display:flex;gap:16px;font-size:11px;color:#9ca3af;margin-bottom:10px">
      <span>frames: {r['n_frames']}</span>
      <span>success: {success_str}</span>
      <span>beta: {beta_str}</span>
    </div>
    {bar_chart}
  </div>""")

    cards_joined = "\n".join(cards_html)
    donut = _donut_svg(grade_counts, len(results))

    # --- Rejected episodes table ---
    rejected = [r for r in results if not r["accepted"]]
    if rejected:
        rej_rows = []
        for r in rejected:
            rej_rows.append(
                f"<tr><td>{r['episode_name']}</td>"
                f"<td style='color:{_GRADE_COLORS[r['grade']]}'>{r['grade']}</td>"
                f"<td>{r['composite']:.2f}</td>"
                f"<td>{r['n_frames']}</td>"
                f"<td>{'yes' if r['success'] else 'no' if r['success'] is False else '?'}</td>"
                f"</tr>"
            )
        rejected_section = f"""
<h2 style="color:#f87171;margin-top:32px">Rejected Episodes ({len(rejected)})</h2>
<table style="width:100%;border-collapse:collapse;font-size:12px">
  <thead>
    <tr style="color:#9ca3af;border-bottom:1px solid #374151">
      <th style="text-align:left;padding:6px">Episode</th>
      <th style="text-align:left;padding:6px">Grade</th>
      <th style="text-align:left;padding:6px">Score</th>
      <th style="text-align:left;padding:6px">Frames</th>
      <th style="text-align:left;padding:6px">Success</th>
    </tr>
  </thead>
  <tbody style="color:#e5e7eb">
    {''.join(rej_rows)}
  </tbody>
</table>"""
    else:
        rejected_section = '<p style="color:#34d399">All episodes passed!</p>'

    # --- Dimension averages bar ---
    dim_avgs = [
        sum(r["dimensions"][k] for r in results) / max(len(results), 1)
        for k in dim_keys
    ]
    avg_bar = _bar_svg(dim_avgs, dim_labels, _DIM_COLORS, width=500, height=200)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>OCI Robot Cloud — Episode Quality Report</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background: #111827;
      color: #e5e7eb;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      padding: 24px;
      max-width: 900px;
      margin: 0 auto;
    }}
    h1 {{ font-size: 20px; font-weight: 700; margin-bottom: 4px; }}
    h2 {{ font-size: 15px; font-weight: 600; margin: 24px 0 12px; color: #d1d5db; }}
    .subtitle {{ font-size: 12px; color: #6b7280; margin-bottom: 20px; }}
    .stat-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
      gap: 12px;
      margin-bottom: 24px;
    }}
    .stat-card {{
      background: #1f2937;
      border-radius: 8px;
      padding: 14px;
      text-align: center;
    }}
    .stat-value {{ font-size: 28px; font-weight: 700; margin-bottom: 4px; }}
    .stat-label {{ font-size: 11px; color: #9ca3af; }}
    .summary-row {{
      display: flex;
      gap: 24px;
      align-items: flex-start;
      margin-bottom: 24px;
      flex-wrap: wrap;
    }}
  </style>
</head>
<body>
  <h1>OCI Robot Cloud — Episode Quality Report</h1>
  <p class="subtitle">
    Threshold: {min_score:.1f}/10 &nbsp;|&nbsp;
    Weights: {', '.join(f'{k}={v}' for k,v in WEIGHTS.items())}
  </p>

  <div class="stat-grid">
    <div class="stat-card">
      <div class="stat-value" style="color:#60a5fa">{len(results)}</div>
      <div class="stat-label">Total Episodes</div>
    </div>
    <div class="stat-card">
      <div class="stat-value" style="color:#34d399">{n_accept}</div>
      <div class="stat-label">Accepted</div>
    </div>
    <div class="stat-card">
      <div class="stat-value" style="color:#f87171">{n_reject}</div>
      <div class="stat-label">Rejected</div>
    </div>
    <div class="stat-card">
      <div class="stat-value" style="color:#fbbf24">{pass_rate:.0f}%</div>
      <div class="stat-label">Pass Rate</div>
    </div>
    <div class="stat-card">
      <div class="stat-value" style="color:#a78bfa">{mean_score:.2f}</div>
      <div class="stat-label">Mean Score</div>
    </div>
  </div>

  <div class="summary-row">
    <div>
      <h2>Grade Distribution</h2>
      {donut}
    </div>
    <div>
      <h2>Dimension Averages</h2>
      {avg_bar}
    </div>
  </div>

  {rejected_section}

  <h2>All Episodes</h2>
  {cards_joined}

  <p style="margin-top:24px;font-size:11px;color:#374151;text-align:center">
    Generated by data_quality_scorer.py — OCI Robot Cloud
  </p>
</body>
</html>"""

    with open(output_path, "w") as f:
        f.write(html)
    print(f"[scorer] HTML report written to {output_path}")


# ── Mock data generator ────────────────────────────────────────────────────────

def generate_mock_episodes(out_dir: Path, n: int = 30) -> None:
    """Generate n synthetic episode directories with realistic score distributions.

    ~85% of episodes will score above the 5.0 threshold; ~15% below.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = random.Random(42)

    for i in range(n):
        ep_dir = out_dir / f"episode_{i:06d}"
        ep_dir.mkdir(exist_ok=True)

        # ~15% chance of being a low-quality episode
        bad = rng.random() < 0.15
        quality = "low" if bad else "high"

        if quality == "high":
            n_frames = rng.randint(60, 250)
            success  = rng.random() < 0.80
            beta     = rng.uniform(0.0, 0.3)
            jitter   = rng.uniform(0.001, 0.01)   # smooth
        else:
            # Pathological: too short, failed, high beta, jittery
            choice = rng.randint(0, 2)
            if choice == 0:
                n_frames = rng.randint(1, 8)        # too short
            elif choice == 1:
                n_frames = rng.randint(520, 700)    # too long
            else:
                n_frames = rng.randint(20, 80)
            success  = False
            beta     = rng.uniform(0.7, 1.0)
            jitter   = rng.uniform(0.05, 0.2)      # noisy

        # Synthesise joint states: smooth trajectory around a nominal pose
        nominal = np.array([0.0, -0.5, 0.0, -1.5, 0.0, 1.5, 0.8, 0.04, 0.04],
                           dtype=np.float32)
        t = np.linspace(0, 1, n_frames).reshape(-1, 1).astype(np.float32)
        # Smooth interpolation + noise
        states = (nominal
                  + 0.3 * np.sin(2 * math.pi * t * rng.uniform(0.5, 2.0))
                  + np.random.default_rng(i).normal(0, jitter, (n_frames, 9)).astype(np.float32))
        states = np.clip(states, JOINT_LOWER, JOINT_UPPER).astype(np.float32)

        np.save(ep_dir / "states.npy", states)
        np.save(ep_dir / "actions.npy", states)   # actions ≈ states for mock

        meta_d: Dict = {"success": success, "beta_actual": beta}
        with open(ep_dir / "meta.json", "w") as f:
            json.dump(meta_d, f)

    print(f"[mock] Generated {n} episodes in {out_dir}")


# ── CLI ────────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Score episode quality for OCI Robot Cloud training pipeline.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument(
        "--episodes-dir", "-e", type=Path, default=None,
        help="Directory containing episode_XXXXXX subdirectories.",
    )
    p.add_argument(
        "--output", "-o", type=Path, default=Path("/tmp/quality_report.html"),
        help="Output path for HTML report or CSV (default: /tmp/quality_report.html).",
    )
    p.add_argument(
        "--min-score", type=float, default=DEFAULT_MIN_SCORE,
        help=f"Acceptance threshold (default: {DEFAULT_MIN_SCORE}).",
    )
    p.add_argument(
        "--csv-only", action="store_true",
        help="Write CSV output only (no HTML). --output should end in .csv.",
    )
    p.add_argument(
        "--mock", action="store_true",
        help="Generate 30 synthetic episodes and score them (no real data needed).",
    )
    p.add_argument(
        "--mock-n", type=int, default=30,
        help="Number of mock episodes to generate (default: 30).",
    )
    p.add_argument(
        "--mock-dir", type=Path, default=Path("/tmp/mock_episodes"),
        help="Directory to place mock episodes (default: /tmp/mock_episodes).",
    )
    return p


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.mock:
        # Mock mode: generate synthetic data then score it
        generate_mock_episodes(args.mock_dir, n=args.mock_n)
        episodes_dir = args.mock_dir
    elif args.episodes_dir is not None:
        episodes_dir = args.episodes_dir
    else:
        parser.error("Provide --episodes-dir or use --mock")
        return

    if not episodes_dir.exists():
        print(f"[error] Directory not found: {episodes_dir}", file=sys.stderr)
        sys.exit(1)

    results = score_directory(episodes_dir, min_score=args.min_score)
    if not results:
        print("[scorer] No results to write.", file=sys.stderr)
        sys.exit(1)

    if args.csv_only:
        out = args.output if str(args.output).endswith(".csv") else args.output.with_suffix(".csv")
        write_csv(results, out)
    else:
        # Always write CSV alongside HTML
        csv_path = args.output.with_suffix(".csv")
        write_csv(results, csv_path)
        write_html_report(results, args.output, min_score=args.min_score)
        print(f"\nOpen report: file://{args.output.resolve()}")


if __name__ == "__main__":
    main()
