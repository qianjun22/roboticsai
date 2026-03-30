#!/usr/bin/env python3
"""
eval_dataset_curator.py — Canonical evaluation dataset curator for OCI Robot Cloud.

Curates a locked, versioned set of evaluation episodes so every checkpoint is
benchmarked on the same diverse, balanced starting conditions.  Once a dataset
version has been used in at least one eval run it becomes immutable; subsequent
runs must reference the same file or create a new version.

Cube position taxonomy
----------------------
  center     : |cube_x| < 0.05 m
  left       : -0.25 < cube_x <= -0.05 m
  right      :  0.05 < cube_x <  0.25 m
  far_edge   : |cube_x| >= 0.25 m   (hardest reach)

Difficulty labels (1 = easiest → 4 = hardest)
----------------------------------------------
  1  easy       : |cube_x| < 0.05
  2  medium     : 0.05 <= |cube_x| < 0.15
  3  hard       : 0.15 <= |cube_x| < 0.25
  4  very_hard  : |cube_x| >= 0.25

CLI
---
  # Create a new canonical dataset
  python src/eval/eval_dataset_curator.py --create --n-episodes 20 \
      --output /tmp/eval_canonical_v1.json

  # Validate an existing dataset file
  python src/eval/eval_dataset_curator.py --validate \
      --dataset /tmp/eval_canonical_v1.json

  # Generate stratified HTML report from eval results
  python src/eval/eval_dataset_curator.py --report \
      --results /tmp/eval_results.json \
      --dataset /tmp/eval_canonical_v1.json \
      --output /tmp/eval_report_canonical.html

LeRobot v2 manifest
-------------------
The --create command writes a JSON file that doubles as a LeRobot v2 test-split
manifest.  Each entry has the keys expected by lerobot.datasets.EpisodeDataset:
  episode_index, task, language_instruction, initial_state, metadata.

No external dependencies beyond the Python standard library.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ── Physical constants (must match genesis_sdg_planned.py) ─────────────────────

TABLE_Z        = 0.700   # table surface [m]
CUBE_HALF      = 0.025   # half cube side [m]
CUBE_Z_SPAWN   = TABLE_Z + CUBE_HALF          # 0.725 m
WORKSPACE_X    = (-0.35, 0.35)                # reachable x range [m]
WORKSPACE_Y    = (0.20,  0.65)                # reachable y range [m]
MIN_SEP_L2     = 0.06    # min L2 distance between any two cube XY positions [m]

# ── Position buckets ────────────────────────────────────────────────────────────

POSITION_BUCKETS: dict[str, tuple[float, float]] = {
    # name : (cube_x_min, cube_x_max)  — Y is sampled uniformly within workspace
    "center":   (-0.05,  0.05),
    "left":     (-0.25, -0.05),
    "right":    ( 0.05,  0.25),
    "far_edge": None,          # special: |x| >= 0.25, sampled from both sides
}

EPISODES_PER_BUCKET = 5       # default — 4 × 5 = 20 total

# ── Difficulty mapping ──────────────────────────────────────────────────────────

def difficulty_label(cube_x: float) -> tuple[int, str]:
    """Return (level 1-4, name) for a given cube_x position."""
    ax = abs(cube_x)
    if ax < 0.05:
        return 1, "easy"
    if ax < 0.15:
        return 2, "medium"
    if ax < 0.25:
        return 3, "hard"
    return 4, "very_hard"

# ── Version helpers ─────────────────────────────────────────────────────────────

def next_version(output_path: Path) -> str:
    """Infer next version tag by scanning siblings named *_v<N>.json."""
    parent = output_path.parent
    stem   = output_path.stem  # e.g. "eval_canonical_v1"
    # strip trailing _vN if present so we can re-version
    base = stem
    import re
    base = re.sub(r"_v\d+$", "", base)
    existing = sorted(parent.glob(f"{base}_v*.json"))
    if not existing:
        return "v1"
    # find highest N
    nums = []
    for p in existing:
        m = re.search(r"_v(\d+)\.json$", p.name)
        if m:
            nums.append(int(m.group(1)))
    return f"v{max(nums) + 1}" if nums else "v1"


# ── Episode generation ──────────────────────────────────────────────────────────

def _sample_far_edge_x(rng: random.Random) -> float:
    """Sample x uniformly from both far-edge sides."""
    left_range  = (WORKSPACE_X[0], -0.25)   # -0.35 to -0.25
    right_range = ( 0.25, WORKSPACE_X[1])   #  0.25 to  0.35
    if rng.random() < 0.5:
        return rng.uniform(*left_range)
    return rng.uniform(*right_range)


def _sample_position_for_bucket(bucket: str, rng: random.Random) -> tuple[float, float]:
    """Sample (cube_x, cube_y) for a given bucket."""
    if bucket == "far_edge":
        x = _sample_far_edge_x(rng)
    else:
        lo, hi = POSITION_BUCKETS[bucket]
        x = rng.uniform(lo, hi)
    y = rng.uniform(*WORKSPACE_Y)
    return x, y


def _l2_xy(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)


def _within_workspace(x: float, y: float) -> bool:
    return WORKSPACE_X[0] <= x <= WORKSPACE_X[1] and WORKSPACE_Y[0] <= y <= WORKSPACE_Y[1]


def generate_canonical_episodes(
    n_per_bucket: int = EPISODES_PER_BUCKET,
    seed: int = 42,
    max_attempts: int = 10_000,
) -> list[dict[str, Any]]:
    """
    Generate a balanced canonical episode list.

    Returns a list of episode dicts with keys:
      episode_index, bucket, difficulty_level, difficulty_name,
      initial_state, task, language_instruction, metadata
    """
    rng = random.Random(seed)
    episodes: list[dict[str, Any]] = []
    all_xy: list[tuple[float, float]] = []
    ep_idx = 0

    for bucket in POSITION_BUCKETS:
        count = 0
        attempts = 0
        while count < n_per_bucket:
            if attempts >= max_attempts:
                raise RuntimeError(
                    f"Could not generate {n_per_bucket} diverse episodes for "
                    f"bucket '{bucket}' after {max_attempts} attempts. "
                    "Consider reducing MIN_SEP_L2 or n_per_bucket."
                )
            x, y = _sample_position_for_bucket(bucket, rng)
            attempts += 1

            # Workspace bounds check
            if not _within_workspace(x, y):
                continue

            # Diversity check — reject near-duplicates
            xy = (x, y)
            if any(_l2_xy(xy, prev) < MIN_SEP_L2 for prev in all_xy):
                continue

            # Difficulty
            diff_level, diff_name = difficulty_label(x)

            initial_state = {
                "cube_x": round(x, 4),
                "cube_y": round(y, 4),
                "cube_z": round(CUBE_Z_SPAWN, 4),
                "cube_quat": [1.0, 0.0, 0.0, 0.0],   # upright
                "robot_qpos": [0.0, -0.3, 0.0, -2.0, 0.0, 1.8, 0.7, 0.04, 0.04],
            }

            episode = {
                "episode_index": ep_idx,
                "bucket": bucket,
                "difficulty_level": diff_level,
                "difficulty_name": diff_name,
                "initial_state": initial_state,
                "task": "FrankaCubeLift",
                "language_instruction": "Pick up the cube and lift it above the table.",
                "metadata": {
                    "generator": "eval_dataset_curator",
                    "seed": seed,
                    "min_sep_l2": MIN_SEP_L2,
                    "created_utc": datetime.now(timezone.utc).isoformat(),
                },
            }

            episodes.append(episode)
            all_xy.append(xy)
            count += 1
            ep_idx += 1

    return episodes


# ── Dataset file schema ─────────────────────────────────────────────────────────

def build_dataset(
    episodes: list[dict[str, Any]],
    version: str,
    description: str = "",
) -> dict[str, Any]:
    """Wrap episodes in the top-level dataset manifest."""
    return {
        "schema_version": "eval_dataset_v1",
        "lerobot_compat": "v2",
        "dataset_version": version,
        "locked": False,            # set to True once first eval run references this file
        "description": description or f"Canonical evaluation dataset {version}",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "n_episodes": len(episodes),
        "n_per_bucket": EPISODES_PER_BUCKET,
        "buckets": list(POSITION_BUCKETS.keys()),
        "workspace_x": list(WORKSPACE_X),
        "workspace_y": list(WORKSPACE_Y),
        "min_sep_l2": MIN_SEP_L2,
        "episodes": episodes,
        # LeRobot v2 split manifest fields
        "splits": {
            "test": list(range(len(episodes))),
            "quick_eval": [ep["episode_index"] for ep in episodes[:1]
                           # one per bucket
                           ] + _quick_eval_indices(episodes),
        },
        "eval_runs": [],            # populated by lock_dataset()
    }


def _quick_eval_indices(episodes: list[dict[str, Any]]) -> list[int]:
    """Pick one episode per bucket (5 total → quick-eval subset)."""
    seen: set[str] = set()
    indices: list[int] = []
    for ep in episodes:
        b = ep["bucket"]
        if b not in seen:
            seen.add(b)
            indices.append(ep["episode_index"])
        if len(indices) >= len(POSITION_BUCKETS):
            break
    return indices


# ── Lock / version control ──────────────────────────────────────────────────────

def lock_dataset(dataset: dict[str, Any], run_id: str) -> dict[str, Any]:
    """
    Mark dataset as locked after first eval run.
    Records the run_id that triggered the lock.
    """
    ds = deepcopy(dataset)
    ds["locked"] = True
    ds["eval_runs"].append({
        "run_id": run_id,
        "locked_at_utc": datetime.now(timezone.utc).isoformat(),
    })
    return ds


def check_locked(dataset: dict[str, Any]) -> bool:
    return bool(dataset.get("locked", False))


# ── Validation ──────────────────────────────────────────────────────────────────

REQUIRED_EPISODE_FIELDS = {
    "episode_index", "bucket", "difficulty_level", "difficulty_name",
    "initial_state", "task", "language_instruction",
}

REQUIRED_STATE_FIELDS = {
    "cube_x", "cube_y", "cube_z", "robot_qpos",
}

def validate_dataset(dataset: dict[str, Any]) -> list[str]:
    """
    Validate the dataset.  Returns a list of error strings (empty = valid).
    """
    errors: list[str] = []

    # Top-level schema
    if dataset.get("schema_version") != "eval_dataset_v1":
        errors.append(f"Unknown schema_version: {dataset.get('schema_version')}")

    episodes = dataset.get("episodes", [])
    if not episodes:
        errors.append("No episodes found in dataset.")
        return errors

    xy_positions: list[tuple[float, float]] = []
    bucket_counts: dict[str, int] = {}

    for i, ep in enumerate(episodes):
        prefix = f"Episode {i}"

        # Required fields
        missing = REQUIRED_EPISODE_FIELDS - ep.keys()
        if missing:
            errors.append(f"{prefix}: missing fields {missing}")
            continue

        # Initial state fields
        state = ep.get("initial_state", {})
        missing_state = REQUIRED_STATE_FIELDS - state.keys()
        if missing_state:
            errors.append(f"{prefix}: initial_state missing {missing_state}")

        # Workspace bounds
        x, y = state.get("cube_x", 0), state.get("cube_y", 0)
        if not _within_workspace(x, y):
            errors.append(
                f"{prefix}: cube position ({x:.3f}, {y:.3f}) out of workspace "
                f"x={WORKSPACE_X}, y={WORKSPACE_Y}"
            )

        # Cube Z sanity
        z = state.get("cube_z", 0)
        if abs(z - CUBE_Z_SPAWN) > 0.01:
            errors.append(
                f"{prefix}: unexpected cube_z={z:.4f} (expected ~{CUBE_Z_SPAWN:.4f})"
            )

        # Difficulty label consistency
        expected_level, expected_name = difficulty_label(x)
        if ep.get("difficulty_level") != expected_level:
            errors.append(
                f"{prefix}: difficulty_level={ep['difficulty_level']} "
                f"but cube_x={x:.4f} implies {expected_level} ({expected_name})"
            )

        xy_positions.append((x, y))
        bucket_counts[ep["bucket"]] = bucket_counts.get(ep["bucket"], 0) + 1

    # Diversity check across all episode pairs
    n = len(xy_positions)
    for i in range(n):
        for j in range(i + 1, n):
            d = _l2_xy(xy_positions[i], xy_positions[j])
            if d < MIN_SEP_L2:
                errors.append(
                    f"Episodes {i} and {j} are too close: L2={d:.4f}m < {MIN_SEP_L2}m"
                )

    # Balance check
    for bucket in POSITION_BUCKETS:
        c = bucket_counts.get(bucket, 0)
        if c == 0:
            errors.append(f"No episodes in bucket '{bucket}'")
        elif c != EPISODES_PER_BUCKET:
            errors.append(
                f"Bucket '{bucket}' has {c} episodes (expected {EPISODES_PER_BUCKET})"
            )

    return errors


# ── Stratified reporting ────────────────────────────────────────────────────────

def compute_stratified_results(
    eval_results: dict[str, Any],
    dataset: dict[str, Any],
) -> dict[str, Any]:
    """
    Join eval episode results with dataset metadata to produce stratified stats.

    eval_results must contain an "episodes" list; each episode must have
    "episode_index" and "success" keys (matching closed_loop_eval.py output).
    """
    episodes_meta = {ep["episode_index"]: ep for ep in dataset["episodes"]}

    # Collect results
    by_difficulty: dict[str, list[bool]] = {
        "easy": [], "medium": [], "hard": [], "very_hard": [],
    }
    by_bucket: dict[str, list[bool]] = {b: [] for b in POSITION_BUCKETS}
    overall: list[bool] = []

    missing_meta: list[int] = []

    for ep_result in eval_results.get("episodes", []):
        idx     = ep_result.get("episode_index")
        success = bool(ep_result.get("success", False))
        meta    = episodes_meta.get(idx)
        if meta is None:
            missing_meta.append(idx)
            continue

        diff_name = meta["difficulty_name"]
        bucket    = meta["bucket"]

        by_difficulty[diff_name].append(success)
        by_bucket[bucket].append(success)
        overall.append(success)

    def sr(lst: list[bool]) -> float | None:
        if not lst:
            return None
        return round(sum(lst) / len(lst), 4)

    stratified = {
        "overall": {
            "n": len(overall),
            "success_rate": sr(overall),
            "n_success": sum(overall),
        },
        "by_difficulty": {
            name: {
                "n": len(results),
                "success_rate": sr(results),
                "n_success": sum(results),
            }
            for name, results in by_difficulty.items()
        },
        "by_bucket": {
            bucket: {
                "n": len(results),
                "success_rate": sr(results),
                "n_success": sum(results),
            }
            for bucket, results in by_bucket.items()
        },
        "missing_meta_indices": missing_meta,
    }
    return stratified


# ── Subset sampling ─────────────────────────────────────────────────────────────

def get_subset(dataset: dict[str, Any], mode: str = "full") -> list[dict[str, Any]]:
    """
    Return episode list for a given eval mode.

    mode:
      "full"       — all 20 episodes
      "quick_eval" — 1 per bucket (4 episodes)
    """
    if mode == "full":
        return dataset["episodes"]
    if mode == "quick_eval":
        indices = set(dataset["splits"].get("quick_eval", []))
        return [ep for ep in dataset["episodes"] if ep["episode_index"] in indices]
    raise ValueError(f"Unknown mode '{mode}'. Use 'full' or 'quick_eval'.")


# ── HTML report ─────────────────────────────────────────────────────────────────

_DARK_CSS = """
  :root {
    --bg: #0f1117;
    --surface: #1a1d27;
    --border: #2a2d3e;
    --text: #e2e8f0;
    --muted: #94a3b8;
    --accent: #6366f1;
    --success: #22c55e;
    --fail: #ef4444;
    --warn: #f59e0b;
    --easy: #22c55e;
    --medium: #3b82f6;
    --hard: #f59e0b;
    --very_hard: #ef4444;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background: var(--bg);
    color: var(--text);
    font-family: 'Inter', 'Segoe UI', system-ui, sans-serif;
    font-size: 14px;
    padding: 2rem;
    line-height: 1.6;
  }
  h1 { font-size: 1.6rem; font-weight: 700; color: var(--text); margin-bottom: 0.25rem; }
  h2 { font-size: 1.1rem; font-weight: 600; color: var(--accent); margin: 1.5rem 0 0.75rem; }
  .meta { color: var(--muted); font-size: 0.85rem; margin-bottom: 1.5rem; }
  .card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 1.25rem 1.5rem;
    margin-bottom: 1.25rem;
  }
  .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 1.25rem; }
  .grid-4 { display: grid; grid-template-columns: repeat(4, 1fr); gap: 1rem; }
  .stat-label { font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--muted); }
  .stat-value { font-size: 2rem; font-weight: 700; margin-top: 0.2rem; }
  .badge {
    display: inline-block;
    padding: 0.15rem 0.55rem;
    border-radius: 999px;
    font-size: 0.75rem;
    font-weight: 600;
  }
  .badge-success { background: #14532d; color: var(--success); }
  .badge-fail    { background: #450a0a; color: var(--fail); }
  .badge-easy     { background: #14532d; color: var(--easy); }
  .badge-medium   { background: #1e3a5f; color: var(--medium); }
  .badge-hard     { background: #451a03; color: var(--hard); }
  .badge-very_hard{ background: #450a0a; color: var(--very_hard); }
  table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
  th, td { padding: 0.55rem 0.75rem; text-align: left; }
  th { border-bottom: 1px solid var(--border); color: var(--muted); font-weight: 500; }
  tr:not(:last-child) td { border-bottom: 1px solid #1e2030; }
  tr:hover td { background: #1e2030; }
  .bar-bg {
    background: #1e2030;
    border-radius: 4px;
    height: 8px;
    overflow: hidden;
    min-width: 80px;
  }
  .bar-fill {
    height: 100%;
    border-radius: 4px;
    transition: width 0.3s;
  }
  .locked-banner {
    background: #1a2744;
    border: 1px solid #2563eb;
    border-radius: 8px;
    padding: 0.6rem 1rem;
    color: #93c5fd;
    font-size: 0.85rem;
    margin-bottom: 1.25rem;
  }
  footer {
    margin-top: 2rem;
    color: var(--muted);
    font-size: 0.75rem;
    text-align: center;
  }
"""

def _pct(val: float | None) -> str:
    if val is None:
        return "—"
    return f"{val * 100:.1f}%"


def _bar(val: float | None, color: str = "#6366f1") -> str:
    w = int((val or 0) * 100)
    return (
        f'<div class="bar-bg"><div class="bar-fill" '
        f'style="width:{w}%;background:{color};"></div></div>'
    )


def _diff_color(name: str) -> str:
    return {"easy": "#22c55e", "medium": "#3b82f6",
            "hard": "#f59e0b", "very_hard": "#ef4444"}.get(name, "#6366f1")


def render_html_report(
    dataset: dict[str, Any],
    stratified: dict[str, Any],
    eval_results: dict[str, Any],
) -> str:
    """Render a dark-theme HTML report from stratified results."""
    now_str    = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    ds_ver     = dataset.get("dataset_version", "unknown")
    locked_str = ("Locked" if dataset.get("locked") else "Not locked")
    overall    = stratified["overall"]

    # Overall stat color
    sr = overall.get("success_rate") or 0
    sr_color = "#22c55e" if sr >= 0.7 else "#f59e0b" if sr >= 0.4 else "#ef4444"

    # Build difficulty rows
    diff_order = ["easy", "medium", "hard", "very_hard"]
    diff_rows  = ""
    for d in diff_order:
        info  = stratified["by_difficulty"].get(d, {})
        n     = info.get("n", 0)
        ns    = info.get("n_success", 0)
        rate  = info.get("success_rate")
        color = _diff_color(d)
        diff_rows += (
            f"<tr><td><span class='badge badge-{d}'>{d.replace('_',' ')}</span></td>"
            f"<td>{ns}/{n}</td>"
            f"<td>{_pct(rate)}</td>"
            f"<td>{_bar(rate, color)}</td></tr>\n"
        )

    # Build bucket rows
    bucket_rows = ""
    for b in POSITION_BUCKETS:
        info  = stratified["by_bucket"].get(b, {})
        n     = info.get("n", 0)
        ns    = info.get("n_success", 0)
        rate  = info.get("success_rate")
        bucket_rows += (
            f"<tr><td><code>{b}</code></td>"
            f"<td>{ns}/{n}</td>"
            f"<td>{_pct(rate)}</td>"
            f"<td>{_bar(rate)}</td></tr>\n"
        )

    # Per-episode table
    ep_meta = {ep["episode_index"]: ep for ep in dataset.get("episodes", [])}
    ep_rows = ""
    for ep_r in sorted(
        eval_results.get("episodes", []), key=lambda e: e.get("episode_index", 0)
    ):
        idx     = ep_r.get("episode_index", "?")
        success = ep_r.get("success", False)
        meta    = ep_meta.get(idx, {})
        bucket  = meta.get("bucket", "—")
        diff    = meta.get("difficulty_name", "—")
        cx      = meta.get("initial_state", {}).get("cube_x", "?")
        cy      = meta.get("initial_state", {}).get("cube_y", "?")
        steps   = ep_r.get("n_steps", "—")
        ok_cls  = "badge-success" if success else "badge-fail"
        ok_lbl  = "success" if success else "fail"
        ep_rows += (
            f"<tr>"
            f"<td>{idx}</td>"
            f"<td><code>{bucket}</code></td>"
            f"<td><span class='badge badge-{diff}'>{diff.replace('_',' ')}</span></td>"
            f"<td>{cx:.4f}</td>"
            f"<td>{cy:.4f}</td>"
            f"<td>{steps}</td>"
            f"<td><span class='badge {ok_cls}'>{ok_lbl}</span></td>"
            f"</tr>\n"
        )

    locked_banner = ""
    if dataset.get("locked"):
        runs = dataset.get("eval_runs", [])
        first_run = runs[0].get("run_id", "?") if runs else "?"
        locked_banner = (
            f"<div class='locked-banner'>"
            f"Dataset <strong>{ds_ver}</strong> is <strong>locked</strong> "
            f"(first eval run: <code>{first_run}</code>). "
            "Episode list is immutable — use a new version file for any changes."
            "</div>"
        )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Canonical Eval Report — {ds_ver}</title>
  <style>{_DARK_CSS}</style>
</head>
<body>
  <h1>Canonical Eval Report</h1>
  <p class="meta">Dataset: <strong>{ds_ver}</strong> &nbsp;|&nbsp; Status: {locked_str}
    &nbsp;|&nbsp; Generated: {now_str}</p>

  {locked_banner}

  <h2>Overall</h2>
  <div class="grid-4">
    <div class="card">
      <div class="stat-label">Success Rate</div>
      <div class="stat-value" style="color:{sr_color}">{_pct(overall.get("success_rate"))}</div>
    </div>
    <div class="card">
      <div class="stat-label">Episodes Evaluated</div>
      <div class="stat-value">{overall.get("n", 0)}</div>
    </div>
    <div class="card">
      <div class="stat-label">Successes</div>
      <div class="stat-value" style="color:#22c55e">{overall.get("n_success", 0)}</div>
    </div>
    <div class="card">
      <div class="stat-label">Dataset Episodes</div>
      <div class="stat-value">{dataset.get("n_episodes", 0)}</div>
    </div>
  </div>

  <div class="grid-2">
    <div class="card">
      <h2>By Difficulty</h2>
      <table>
        <thead><tr><th>Level</th><th>n_success/n</th><th>Rate</th><th>Bar</th></tr></thead>
        <tbody>{diff_rows}</tbody>
      </table>
    </div>
    <div class="card">
      <h2>By Cube Position</h2>
      <table>
        <thead><tr><th>Bucket</th><th>n_success/n</th><th>Rate</th><th>Bar</th></tr></thead>
        <tbody>{bucket_rows}</tbody>
      </table>
    </div>
  </div>

  <div class="card">
    <h2>Per-Episode Results</h2>
    <table>
      <thead>
        <tr>
          <th>#</th><th>Bucket</th><th>Difficulty</th>
          <th>cube_x</th><th>cube_y</th><th>Steps</th><th>Result</th>
        </tr>
      </thead>
      <tbody>{ep_rows}</tbody>
    </table>
  </div>

  <footer>OCI Robot Cloud — eval_dataset_curator.py &nbsp;|&nbsp; {now_str}</footer>
</body>
</html>"""
    return html


# ── CLI ─────────────────────────────────────────────────────────────────────────

def cmd_create(args: argparse.Namespace) -> None:
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    # Auto-version if output already exists
    version = next_version(output) if output.exists() else "v1"
    import re
    if re.search(r"_v\d+$", output.stem):
        # user supplied explicit versioned name — honour it
        version = re.search(r"_v(\d+)$", output.stem).group(0).lstrip("_")

    n_per_bucket = max(1, args.n_episodes // len(POSITION_BUCKETS))
    print(f"Generating {n_per_bucket} episodes per bucket "
          f"({n_per_bucket * len(POSITION_BUCKETS)} total) with seed={args.seed} …")

    episodes = generate_canonical_episodes(
        n_per_bucket=n_per_bucket,
        seed=args.seed,
    )
    dataset = build_dataset(episodes, version=version)

    output.write_text(json.dumps(dataset, indent=2))
    print(f"Saved {len(episodes)} episodes → {output}")

    # Quick validation
    errors = validate_dataset(dataset)
    if errors:
        print(f"WARNING: {len(errors)} validation issue(s):")
        for e in errors:
            print(f"  • {e}")
    else:
        print("Validation passed.")

    # Show subset sizes
    quick = get_subset(dataset, "quick_eval")
    print(f"Subsets — full: {len(episodes)}, quick_eval: {len(quick)}")


def cmd_validate(args: argparse.Namespace) -> None:
    path = Path(args.dataset)
    if not path.exists():
        print(f"ERROR: file not found: {path}", file=sys.stderr)
        sys.exit(1)

    dataset = json.loads(path.read_text())
    errors  = validate_dataset(dataset)

    if not errors:
        n = dataset.get("n_episodes", 0)
        ver = dataset.get("dataset_version", "?")
        locked = "locked" if dataset.get("locked") else "not locked"
        print(f"OK — {n} episodes, version={ver}, {locked}.")
    else:
        print(f"FAIL — {len(errors)} error(s):")
        for e in errors:
            print(f"  • {e}")
        sys.exit(1)


def cmd_report(args: argparse.Namespace) -> None:
    results_path = Path(args.results)
    dataset_path = Path(args.dataset)

    for p in (results_path, dataset_path):
        if not p.exists():
            print(f"ERROR: file not found: {p}", file=sys.stderr)
            sys.exit(1)

    eval_results = json.loads(results_path.read_text())
    dataset      = json.loads(dataset_path.read_text())

    # Validate dataset first
    errors = validate_dataset(dataset)
    if errors:
        print(f"WARNING: dataset has {len(errors)} validation issue(s) (continuing):")
        for e in errors:
            print(f"  • {e}")

    stratified = compute_stratified_results(eval_results, dataset)

    # Print summary to stdout
    ov = stratified["overall"]
    print(f"Overall success rate : {_pct(ov.get('success_rate'))}  "
          f"({ov.get('n_success',0)}/{ov.get('n',0)})")
    print("By difficulty:")
    for d in ["easy", "medium", "hard", "very_hard"]:
        info = stratified["by_difficulty"][d]
        print(f"  {d:12s}  {_pct(info.get('success_rate'))}  "
              f"({info.get('n_success',0)}/{info.get('n',0)})")
    print("By bucket:")
    for b in POSITION_BUCKETS:
        info = stratified["by_bucket"][b]
        print(f"  {b:12s}  {_pct(info.get('success_rate'))}  "
              f"({info.get('n_success',0)}/{info.get('n',0)})")

    # HTML output
    output_path = Path(args.output) if args.output else results_path.with_suffix(".html")
    html = render_html_report(dataset, stratified, eval_results)
    output_path.write_text(html)
    print(f"\nHTML report → {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Canonical evaluation dataset curator for OCI Robot Cloud.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="command")

    # --create
    p_create = sub.add_parser("create", help="Generate a new canonical eval dataset.")
    p_create.add_argument("--n-episodes", type=int, default=20,
                          help="Total episodes to generate (default 20, must be divisible by 4).")
    p_create.add_argument("--output", required=True,
                          help="Output JSON path, e.g. /tmp/eval_canonical_v1.json")
    p_create.add_argument("--seed", type=int, default=42,
                          help="Random seed for reproducibility (default 42).")

    # --validate
    p_val = sub.add_parser("validate", help="Validate an existing dataset file.")
    p_val.add_argument("--dataset", required=True, help="Path to dataset JSON.")

    # --report
    p_rep = sub.add_parser("report", help="Generate stratified HTML report.")
    p_rep.add_argument("--results", required=True,
                       help="Eval results JSON (from closed_loop_eval.py).")
    p_rep.add_argument("--dataset", required=True, help="Canonical dataset JSON.")
    p_rep.add_argument("--output", default=None,
                       help="Output HTML path (default: results file with .html extension).")

    # Legacy flat --flag style (matches docstring CLI examples)
    parser.add_argument("--create",   action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--validate", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--report",   action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--n-episodes", type=int, default=20, help=argparse.SUPPRESS)
    parser.add_argument("--output",  default=None, help=argparse.SUPPRESS)
    parser.add_argument("--seed",    type=int,    default=42, help=argparse.SUPPRESS)
    parser.add_argument("--dataset", default=None, help=argparse.SUPPRESS)
    parser.add_argument("--results", default=None, help=argparse.SUPPRESS)

    args = parser.parse_args()

    # Route: subcommand takes priority, then flat flags
    command = args.command
    if command is None:
        if getattr(args, "create", False):
            command = "create"
        elif getattr(args, "validate", False):
            command = "validate"
        elif getattr(args, "report", False):
            command = "report"
        else:
            parser.print_help()
            sys.exit(0)

    if command == "create":
        if not args.output:
            parser.error("--output is required for --create")
        cmd_create(args)
    elif command == "validate":
        if not args.dataset:
            parser.error("--dataset is required for --validate")
        cmd_validate(args)
    elif command == "report":
        if not args.results:
            parser.error("--results is required for --report")
        if not args.dataset:
            parser.error("--dataset is required for --report")
        cmd_report(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
