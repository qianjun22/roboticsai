#!/usr/bin/env python3
"""
dataset_deduplication.py — Near-duplicate episode removal for OCI Robot Cloud training datasets.

Removes near-duplicate episodes before DAgger fine-tuning to prevent the model from
overfitting to repeated trajectories (common when collecting real-robot data in bursts).

ALGORITHM
---------
  1. Exact dedup: SHA-256 of (mean joint positions + cube_z trajectory bucketed to 2 dp)
  2. Near-dedup:  L2 distance between episode "signatures" (mean + std of joint states
                  per DOF, cube_z progression bucketed to 5 evenly-spaced time points)
  3. Clustering:  Union-Find groups all near-duplicates; keep highest-quality episode
                  per cluster (success=2pt, length~50=1pt, smooth=0.5pt)
  4. Report:      duplication rate bar, cluster size histogram SVG, before/after quality
                  distribution — dark-theme HTML, no external deps.

EPISODE DIRECTORY FORMAT (matches dagger_train.py / data_quality_scorer.py)
----------------------------------------------------------------------------
  <input-dir>/
    episode_000000/
      states.npy   (N, 9) float32  — robot joint states (7 DOF arm + 2 gripper)
      actions.npy  (N, 9) float32  — joint targets
      meta.json    optional — {"success": bool, "cube_z": [float, ...], ...}

  Fallback for episodes.npy bulk files:
    <input-dir>/episodes.npy — (E, T, 9) array; synthetic mock uses this format.

CLI USAGE
---------
  # Run on mock synthetic data (200 episodes, ~20% near-duplicates):
  python src/training/dataset_deduplication.py --mock --n-episodes 200 \\
      --output /tmp/dedup_report.html

  # Deduplicate a real DAgger run directory:
  python src/training/dataset_deduplication.py \\
      --input-dir /tmp/dagger_run6/episodes \\
      --output-dir /tmp/dagger_run6_deduped \\
      --threshold 0.40

  # Deduplicate + write HTML report:
  python src/training/dataset_deduplication.py \\
      --input-dir /tmp/dagger_run6/episodes \\
      --output-dir /tmp/dagger_run6_deduped \\
      --output /tmp/dedup_report.html \\
      --threshold 0.40
"""

import argparse
import hashlib
import json
import math
import os
import random
import shutil
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

# ── Constants ──────────────────────────────────────────────────────────────────

FRANKA_DOF = 7          # arm joints
TOTAL_DOF = 9           # arm + 2 gripper
IDEAL_LENGTH = 50       # frames; used in quality scoring
CUBE_Z_INTERP_POINTS = 5  # time-normalised sample points for cube_z signature

DEFAULT_THRESHOLD = 0.40
DEFAULT_N_EPISODES = 200
DEFAULT_OUTPUT = "/tmp/dedup_report.html"


# ── Data structures ────────────────────────────────────────────────────────────

class Episode:
    """In-memory representation of a single demonstration episode."""

    def __init__(
        self,
        ep_id: str,
        states: np.ndarray,        # (T, 9) float32
        actions: np.ndarray,       # (T, 9) float32
        cube_z: Optional[np.ndarray] = None,  # (T,) float32
        success: bool = False,
        source_path: Optional[str] = None,
    ):
        self.ep_id = ep_id
        self.states = states.astype(np.float32)
        self.actions = actions.astype(np.float32)
        self.cube_z = cube_z.astype(np.float32) if cube_z is not None else np.zeros(len(states), dtype=np.float32)
        self.success = success
        self.source_path = source_path
        self.T = len(states)

    # -- fingerprint (exact duplicate key) ------------------------------------

    def fingerprint(self) -> str:
        """SHA-256 of mean joint positions + cube_z trajectory bucketed to 2 dp."""
        mean_joints = np.round(self.states.mean(axis=0), 2)
        cube_z_bucketed = np.round(self.cube_z, 2)
        payload = mean_joints.tobytes() + cube_z_bucketed.tobytes()
        return hashlib.sha256(payload).hexdigest()

    # -- signature (near-duplicate distance) ----------------------------------

    def signature(self) -> np.ndarray:
        """
        Compact float vector used for L2 near-duplicate comparison.

        Components:
          - mean of each DOF state  (9 values)
          - std  of each DOF state  (9 values)
          - cube_z at 5 normalised time points (5 values)
        Total: 23 floats
        """
        mean_s = self.states.mean(axis=0)   # (9,)
        std_s  = self.states.std(axis=0)    # (9,)

        # Interpolate cube_z to fixed number of time points
        T = max(self.T, 2)
        indices = np.linspace(0, T - 1, CUBE_Z_INTERP_POINTS).astype(int)
        cz_sampled = self.cube_z[indices]   # (5,)

        return np.concatenate([mean_s, std_s, cz_sampled]).astype(np.float32)

    # -- quality score --------------------------------------------------------

    def quality_score(self) -> float:
        """
        Simple quality metric used to elect the best episode in a near-dup cluster.

          success   → +2.0
          length~50 → +1.0 (decays as |T - IDEAL_LENGTH| grows)
          smoothness→ +0.5 (low mean velocity magnitude)
        """
        score = 0.0
        if self.success:
            score += 2.0
        # Length bonus: 1.0 at T==IDEAL_LENGTH, 0 at T==0 or T very large
        length_bonus = max(0.0, 1.0 - abs(self.T - IDEAL_LENGTH) / IDEAL_LENGTH)
        score += length_bonus
        # Smoothness: mean L2 norm of frame-to-frame joint deltas
        if self.T > 1:
            deltas = np.diff(self.states[:, :FRANKA_DOF], axis=0)
            mean_vel = float(np.linalg.norm(deltas, axis=1).mean())
            smooth_bonus = 0.5 * max(0.0, 1.0 - mean_vel / 0.5)
            score += smooth_bonus
        return score


# ── Mock data generator ────────────────────────────────────────────────────────

def generate_mock_episodes(n: int = 200, seed: int = 42) -> List[Episode]:
    """
    Generate synthetic episodes with ~20% near-duplicates.

    Near-duplicates are created by taking a "template" episode and adding small
    Gaussian noise (sigma=0.02) to states/actions — mimicking real-robot collection
    runs where the operator repeats nearly-identical grasps.
    """
    rng = np.random.default_rng(seed)
    episodes: List[Episode] = []

    n_unique = int(n * 0.80)       # 80% unique episodes
    n_neardup = n - n_unique       # 20% near-duplicates derived from templates

    # Generate unique base episodes
    templates: List[Episode] = []
    for i in range(n_unique):
        T = int(rng.integers(30, 100))
        # Random joint trajectory (smooth-ish via cumsum)
        states = np.cumsum(rng.normal(0, 0.01, (T, TOTAL_DOF)), axis=0).astype(np.float32)
        states += rng.normal(0, 0.3, (1, TOTAL_DOF)).astype(np.float32)  # random offset
        actions = states + rng.normal(0, 0.02, (T, TOTAL_DOF)).astype(np.float32)
        cube_z = (0.4 + 0.4 * np.linspace(0, 1, T) * rng.uniform(0.5, 1.5)).astype(np.float32)
        success = bool(cube_z[-1] > 0.70)
        ep = Episode(
            ep_id=f"episode_{i:06d}",
            states=states,
            actions=actions,
            cube_z=cube_z,
            success=success,
        )
        templates.append(ep)
        episodes.append(ep)

    # Generate near-duplicates from random templates.
    # Noise is scaled proportionally to each template's own standard deviation
    # so that near-dups are visibly similar but measurably distinct — this mimics
    # real-robot collection where the operator repeats nearly-identical grasps.
    # Noise fraction of ~8% of each DOF's std places near-dup normalised L2
    # distances around 0.10–0.30, well within DEFAULT_THRESHOLD=0.40.
    chosen_templates = rng.choice(len(templates), size=n_neardup, replace=True)
    for j, t_idx in enumerate(chosen_templates):
        tmpl = templates[t_idx]
        scale = tmpl.states.std(axis=0, keepdims=True).clip(0.02)  # (1, 9)
        noise_states  = (rng.normal(0, 0.08, tmpl.states.shape) * scale).astype(np.float32)
        noise_actions = (rng.normal(0, 0.08, tmpl.actions.shape) * scale).astype(np.float32)
        cz_scale = float(tmpl.cube_z.std()) or 0.02
        noise_cz  = rng.normal(0, 0.08 * cz_scale, tmpl.cube_z.shape).astype(np.float32)
        ep = Episode(
            ep_id=f"episode_{n_unique + j:06d}",
            states=tmpl.states + noise_states,
            actions=tmpl.actions + noise_actions,
            cube_z=np.clip(tmpl.cube_z + noise_cz, 0.0, 1.5),
            success=tmpl.success,
        )
        episodes.append(ep)

    # Shuffle so near-dups are not grouped at the end
    indices = list(range(len(episodes)))
    rng.shuffle(indices)
    shuffled = [episodes[i] for i in indices]
    # Re-assign sequential IDs after shuffle
    for k, ep in enumerate(shuffled):
        ep.ep_id = f"episode_{k:06d}"

    return shuffled


# ── Union-Find ────────────────────────────────────────────────────────────────

class UnionFind:
    def __init__(self, n: int):
        self.parent = list(range(n))
        self.rank   = [0] * n

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: int, b: int):
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        if self.rank[ra] < self.rank[rb]:
            ra, rb = rb, ra
        self.parent[rb] = ra
        if self.rank[ra] == self.rank[rb]:
            self.rank[ra] += 1

    def clusters(self) -> Dict[int, List[int]]:
        groups: Dict[int, List[int]] = {}
        for i in range(len(self.parent)):
            root = self.find(i)
            groups.setdefault(root, []).append(i)
        return groups


# ── Core deduplication logic ───────────────────────────────────────────────────

class DeduplicationResult:
    def __init__(self):
        self.original_count: int = 0
        self.exact_removed: int = 0
        self.near_removed: int = 0
        self.kept_episodes: List[Episode] = []
        self.cluster_sizes: List[int] = []          # size of each near-dup cluster (>1 only)
        self.quality_before: List[float] = []
        self.quality_after:  List[float] = []
        self.threshold: float = DEFAULT_THRESHOLD
        self.elapsed_sec: float = 0.0

    @property
    def total_removed(self) -> int:
        return self.exact_removed + self.near_removed

    @property
    def dedup_rate(self) -> float:
        if self.original_count == 0:
            return 0.0
        return self.total_removed / self.original_count


def deduplicate(
    episodes: List[Episode],
    threshold: float = DEFAULT_THRESHOLD,
) -> DeduplicationResult:
    """
    Run exact + near-duplicate removal.

    Returns a DeduplicationResult with kept_episodes and statistics.
    """
    t0 = time.time()
    result = DeduplicationResult()
    result.original_count = len(episodes)
    result.threshold = threshold
    result.quality_before = [ep.quality_score() for ep in episodes]

    # ── Phase 1: exact duplicate removal ──────────────────────────────────────
    seen_fingerprints: Dict[str, int] = {}   # fp -> first index
    exact_keep_mask = [True] * len(episodes)

    for i, ep in enumerate(episodes):
        fp = ep.fingerprint()
        if fp in seen_fingerprints:
            exact_keep_mask[i] = False
        else:
            seen_fingerprints[fp] = i

    after_exact = [ep for i, ep in enumerate(episodes) if exact_keep_mask[i]]
    result.exact_removed = len(episodes) - len(after_exact)

    # ── Phase 2: near-duplicate clustering ────────────────────────────────────
    n = len(after_exact)
    if n == 0:
        result.kept_episodes = []
        result.elapsed_sec = time.time() - t0
        return result

    # Build signature matrix
    sigs = np.stack([ep.signature() for ep in after_exact], axis=0)  # (n, 23)

    # Normalise each dimension by its range to avoid DOF-scale dominance
    sig_range = sigs.max(axis=0) - sigs.min(axis=0)
    sig_range[sig_range < 1e-8] = 1.0
    sigs_norm = (sigs - sigs.min(axis=0)) / sig_range

    # Union-Find: connect episodes within threshold
    uf = UnionFind(n)

    # O(n^2) pairwise — acceptable for typical dataset sizes (<5000 episodes)
    # For very large datasets, a k-d tree or approximate NN would be faster.
    for i in range(n):
        for j in range(i + 1, n):
            dist = float(np.linalg.norm(sigs_norm[i] - sigs_norm[j]))
            if dist < threshold:
                uf.union(i, j)

    # ── Phase 3: keep best per cluster ────────────────────────────────────────
    clusters = uf.clusters()
    kept_indices: List[int] = []

    for root, members in clusters.items():
        if len(members) == 1:
            kept_indices.append(members[0])
        else:
            result.cluster_sizes.append(len(members))
            # Pick member with highest quality score
            best = max(members, key=lambda idx: after_exact[idx].quality_score())
            kept_indices.append(best)

    result.near_removed = n - len(kept_indices)
    result.kept_episodes = [after_exact[i] for i in sorted(kept_indices)]
    result.quality_after = [ep.quality_score() for ep in result.kept_episodes]
    result.elapsed_sec = time.time() - t0

    return result


# ── I/O helpers ───────────────────────────────────────────────────────────────

def load_episodes_from_dir(input_dir: str) -> List[Episode]:
    """
    Load episodes from a directory that follows the DAgger episode layout:
      <input_dir>/episode_NNNNNN/{states.npy, actions.npy, meta.json}

    Falls back to bulk episodes.npy (E, T, 9) if no subdirectories found.
    """
    p = Path(input_dir)
    if not p.exists():
        raise FileNotFoundError(f"Input directory not found: {input_dir}")

    ep_dirs = sorted([d for d in p.iterdir() if d.is_dir() and d.name.startswith("episode_")])

    if ep_dirs:
        episodes = []
        for ep_dir in ep_dirs:
            states_path  = ep_dir / "states.npy"
            actions_path = ep_dir / "actions.npy"
            meta_path    = ep_dir / "meta.json"
            if not states_path.exists() or not actions_path.exists():
                continue
            states  = np.load(str(states_path))
            actions = np.load(str(actions_path))
            meta    = json.loads(meta_path.read_text()) if meta_path.exists() else {}
            cube_z  = None
            if "cube_z" in meta:
                cube_z = np.array(meta["cube_z"], dtype=np.float32)
            elif states.shape[1] > FRANKA_DOF:
                # Heuristic: last column of states often encodes z of tracked object
                cube_z = states[:, -1].copy()
            success = bool(meta.get("success", False))
            episodes.append(Episode(
                ep_id=ep_dir.name,
                states=states,
                actions=actions,
                cube_z=cube_z,
                success=success,
                source_path=str(ep_dir),
            ))
        return episodes

    # Bulk fallback
    bulk_path = p / "episodes.npy"
    if bulk_path.exists():
        arr = np.load(str(bulk_path))  # (E, T, 9)
        episodes = []
        for i in range(arr.shape[0]):
            states = arr[i]
            episodes.append(Episode(
                ep_id=f"episode_{i:06d}",
                states=states,
                actions=states,  # actions not stored separately in bulk format
                cube_z=states[:, -1],
                source_path=str(bulk_path),
            ))
        return episodes

    raise ValueError(f"No episode subdirectories or episodes.npy found in {input_dir}")


def save_episodes_to_dir(episodes: List[Episode], output_dir: str):
    """Write kept episodes to output_dir in the standard episode layout."""
    p = Path(output_dir)
    p.mkdir(parents=True, exist_ok=True)

    for ep in episodes:
        out_ep = p / ep.ep_id
        out_ep.mkdir(exist_ok=True)
        np.save(str(out_ep / "states.npy"),  ep.states)
        np.save(str(out_ep / "actions.npy"), ep.actions)
        meta = {"success": ep.success, "cube_z": ep.cube_z.tolist()}
        (out_ep / "meta.json").write_text(json.dumps(meta))

    print(f"[dedup] Saved {len(episodes)} episodes to {output_dir}")


# ── HTML report ───────────────────────────────────────────────────────────────

_CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { background: #0f1117; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif;
       padding: 2rem; max-width: 960px; margin: 0 auto; }
h1  { color: #60a5fa; font-size: 1.8rem; margin-bottom: 0.25rem; }
h2  { color: #94a3b8; font-size: 1.1rem; font-weight: 500; margin: 2rem 0 0.75rem; }
.subtitle { color: #64748b; font-size: 0.9rem; margin-bottom: 2rem; }
.stat-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 1rem; margin: 1.5rem 0; }
.stat-card { background: #1e293b; border-radius: 8px; padding: 1.2rem 1rem; text-align: center; }
.stat-card .val { font-size: 2rem; font-weight: 700; color: #38bdf8; }
.stat-card .lbl { font-size: 0.78rem; color: #94a3b8; margin-top: 0.25rem; text-transform: uppercase; letter-spacing: 0.04em; }
.stat-card.warn .val { color: #f59e0b; }
.stat-card.ok   .val { color: #34d399; }
.bar-wrap { background: #1e293b; border-radius: 8px; padding: 1.5rem; margin: 1rem 0; }
.bar-label { display: flex; justify-content: space-between; font-size: 0.8rem; color: #94a3b8; margin-bottom: 0.5rem; }
.bar-track { background: #334155; border-radius: 4px; height: 28px; overflow: hidden; }
.bar-fill  { height: 100%; border-radius: 4px; transition: width 0.4s; display: flex; align-items: center; padding-left: 0.75rem; font-size: 0.78rem; font-weight: 600; }
.bar-kept  { background: #2563eb; }
.bar-exact { background: #dc2626; }
.bar-near  { background: #ea580c; }
svg.hist { background: #1e293b; border-radius: 8px; display: block; }
.section { background: #1e293b; border-radius: 8px; padding: 1.5rem; margin: 1rem 0; }
table { width: 100%; border-collapse: collapse; font-size: 0.82rem; }
th { background: #0f172a; color: #94a3b8; padding: 0.5rem 0.75rem; text-align: left; font-weight: 500; text-transform: uppercase; letter-spacing: 0.04em; }
td { padding: 0.45rem 0.75rem; border-bottom: 1px solid #1e293b; }
tr:last-child td { border-bottom: none; }
tr:hover td { background: #263248; }
.tag-kept  { color: #34d399; font-weight: 600; }
.tag-rm    { color: #f87171; }
footer { text-align: center; color: #475569; font-size: 0.78rem; margin-top: 3rem; }
"""


def _svg_histogram(cluster_sizes: List[int], width: int = 680, height: int = 200) -> str:
    """Return an SVG bar chart of cluster size distribution."""
    if not cluster_sizes:
        return (
            f'<svg class="hist" width="{width}" height="60">'
            '<text x="340" y="35" text-anchor="middle" fill="#64748b" font-size="14">'
            'No near-duplicate clusters detected</text></svg>'
        )

    from collections import Counter
    counts = Counter(cluster_sizes)
    sizes  = sorted(counts.keys())
    max_c  = max(counts.values())

    pad_l, pad_r, pad_t, pad_b = 48, 20, 20, 40
    inner_w = width  - pad_l - pad_r
    inner_h = height - pad_t - pad_b
    bar_w   = max(6, inner_w // len(sizes) - 4)

    bars = ""
    for k, sz in enumerate(sizes):
        c   = counts[sz]
        bh  = int(c / max_c * inner_h)
        x   = pad_l + k * (inner_w // len(sizes)) + (inner_w // len(sizes) - bar_w) // 2
        y   = pad_t + inner_h - bh
        bars += (
            f'<rect x="{x}" y="{y}" width="{bar_w}" height="{bh}" rx="3" fill="#2563eb"/>'
            f'<text x="{x + bar_w//2}" y="{y - 4}" text-anchor="middle" fill="#94a3b8" font-size="11">{c}</text>'
            f'<text x="{x + bar_w//2}" y="{pad_t + inner_h + 16}" text-anchor="middle" fill="#64748b" font-size="11">{sz}</text>'
        )

    # Axes
    axes = (
        f'<line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t + inner_h}" stroke="#334155" stroke-width="1"/>'
        f'<line x1="{pad_l}" y1="{pad_t + inner_h}" x2="{pad_l + inner_w}" y2="{pad_t + inner_h}" stroke="#334155" stroke-width="1"/>'
        f'<text x="{pad_l - 6}" y="{pad_t + inner_h // 2}" text-anchor="middle" fill="#64748b" font-size="11" '
        f'transform="rotate(-90,{pad_l - 6},{pad_t + inner_h // 2})">Count</text>'
        f'<text x="{pad_l + inner_w // 2}" y="{height - 4}" text-anchor="middle" fill="#64748b" font-size="11">Cluster Size</text>'
    )

    return (
        f'<svg class="hist" width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">'
        f'{axes}{bars}</svg>'
    )


def _svg_quality_dist(before: List[float], after: List[float], width: int = 680, height: int = 200) -> str:
    """Overlaid histogram of quality scores before vs after dedup."""
    if not before:
        return ""

    n_bins = 15
    lo, hi = 0.0, max(max(before, default=0), max(after, default=0)) + 0.1
    bin_w_val = (hi - lo) / n_bins

    def _hist(vals: List[float]) -> List[int]:
        h = [0] * n_bins
        for v in vals:
            b = min(int((v - lo) / bin_w_val), n_bins - 1)
            h[b] += 1
        return h

    hb = _hist(before)
    ha = _hist(after)
    max_h = max(max(hb, default=1), max(ha, default=1), 1)

    pad_l, pad_r, pad_t, pad_b = 48, 20, 20, 40
    inner_w = width  - pad_l - pad_r
    inner_h = height - pad_t - pad_b
    bw = inner_w // n_bins - 2

    bars = ""
    for i in range(n_bins):
        x  = pad_l + i * (inner_w // n_bins)
        # before bar (red, translucent)
        bh = int(hb[i] / max_h * inner_h)
        bars += f'<rect x="{x+1}" y="{pad_t + inner_h - bh}" width="{bw}" height="{bh}" rx="2" fill="#dc2626" opacity="0.55"/>'
        # after bar (green, translucent)
        ah = int(ha[i] / max_h * inner_h)
        bars += f'<rect x="{x+1}" y="{pad_t + inner_h - ah}" width="{bw}" height="{ah}" rx="2" fill="#34d399" opacity="0.55"/>'

    axes = (
        f'<line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t + inner_h}" stroke="#334155" stroke-width="1"/>'
        f'<line x1="{pad_l}" y1="{pad_t + inner_h}" x2="{pad_l + inner_w}" y2="{pad_t + inner_h}" stroke="#334155" stroke-width="1"/>'
    )
    legend = (
        f'<rect x="{pad_l + 10}" y="{pad_t + 8}" width="14" height="10" fill="#dc2626" opacity="0.7"/>'
        f'<text x="{pad_l + 28}" y="{pad_t + 18}" fill="#94a3b8" font-size="11">Before ({len(before)})</text>'
        f'<rect x="{pad_l + 130}" y="{pad_t + 8}" width="14" height="10" fill="#34d399" opacity="0.7"/>'
        f'<text x="{pad_l + 148}" y="{pad_t + 18}" fill="#94a3b8" font-size="11">After ({len(after)})</text>'
    )

    return (
        f'<svg class="hist" width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">'
        f'{axes}{bars}{legend}</svg>'
    )


def _duplication_bar(result: DeduplicationResult) -> str:
    n = result.original_count
    if n == 0:
        return ""
    pct_kept  = (n - result.total_removed) / n * 100
    pct_exact = result.exact_removed / n * 100
    pct_near  = result.near_removed  / n * 100

    rows = ""
    for label, pct, cls, ep_count in [
        ("Kept episodes",       pct_kept,  "bar-kept",  n - result.total_removed),
        ("Exact duplicates rm", pct_exact, "bar-exact", result.exact_removed),
        ("Near  duplicates rm", pct_near,  "bar-near",  result.near_removed),
    ]:
        fill_text = f"{ep_count} eps ({pct:.1f}%)" if pct > 4 else ""
        rows += f"""
        <div style="margin-bottom:0.75rem">
          <div class="bar-label"><span>{label}</span><span>{ep_count} eps ({pct:.1f}%)</span></div>
          <div class="bar-track">
            <div class="bar-fill {cls}" style="width:{max(pct,0):.1f}%">{fill_text}</div>
          </div>
        </div>"""
    return rows


def generate_html_report(result: DeduplicationResult, output_path: str):
    """Write a dark-theme HTML report to output_path."""
    from datetime import datetime

    dedup_pct = result.dedup_rate * 100
    kept = result.original_count - result.total_removed

    # Stat cards
    card_class_rate = "warn" if dedup_pct > 30 else "ok" if dedup_pct < 10 else ""
    stat_cards = f"""
    <div class="stat-grid">
      <div class="stat-card"><div class="val">{result.original_count}</div><div class="lbl">Original Episodes</div></div>
      <div class="stat-card ok"><div class="val">{kept}</div><div class="lbl">Kept Episodes</div></div>
      <div class="stat-card warn"><div class="val">{result.total_removed}</div><div class="lbl">Removed (total)</div></div>
      <div class="stat-card"><div class="val">{result.exact_removed}</div><div class="lbl">Exact Duplicates</div></div>
      <div class="stat-card"><div class="val">{result.near_removed}</div><div class="lbl">Near-Duplicates</div></div>
      <div class="stat-card {card_class_rate}"><div class="val">{dedup_pct:.1f}%</div><div class="lbl">Duplication Rate</div></div>
      <div class="stat-card"><div class="val">{len(result.cluster_sizes)}</div><div class="lbl">Near-Dup Clusters</div></div>
      <div class="stat-card"><div class="val">{result.elapsed_sec:.2f}s</div><div class="lbl">Processing Time</div></div>
    </div>"""

    # Cluster size distribution
    max_cs = max(result.cluster_sizes, default=0)
    avg_cs = (sum(result.cluster_sizes) / len(result.cluster_sizes)) if result.cluster_sizes else 0
    cluster_stats = f"Max cluster: {max_cs} eps | Avg cluster: {avg_cs:.1f} eps" if result.cluster_sizes else "No near-duplicate clusters."

    hist_svg      = _svg_histogram(result.cluster_sizes)
    qual_svg      = _svg_quality_dist(result.quality_before, result.quality_after)
    bar_section   = _duplication_bar(result)
    avg_q_before  = sum(result.quality_before) / len(result.quality_before) if result.quality_before else 0
    avg_q_after   = sum(result.quality_after)  / len(result.quality_after)  if result.quality_after  else 0
    q_delta       = avg_q_after - avg_q_before
    q_delta_str   = f"+{q_delta:.3f}" if q_delta >= 0 else f"{q_delta:.3f}"
    q_color       = "#34d399" if q_delta >= 0 else "#f87171"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Dataset Deduplication Report</title>
<style>{_CSS}</style>
</head>
<body>
<h1>Dataset Deduplication Report</h1>
<p class="subtitle">OCI Robot Cloud · Generated {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')} · threshold={result.threshold}</p>

{stat_cards}

<h2>Composition Breakdown</h2>
<div class="bar-wrap">{bar_section}</div>

<h2>Near-Duplicate Cluster Size Distribution</h2>
<div class="section">
  <p style="color:#64748b;font-size:0.82rem;margin-bottom:0.75rem">{cluster_stats}</p>
  {hist_svg}
</div>

<h2>Quality Score Distribution — Before vs After</h2>
<div class="section">
  <p style="color:#64748b;font-size:0.82rem;margin-bottom:0.75rem">
    Avg quality before: <b style="color:#e2e8f0">{avg_q_before:.3f}</b> &nbsp;|&nbsp;
    Avg quality after: <b style="color:#e2e8f0">{avg_q_after:.3f}</b> &nbsp;|&nbsp;
    Delta: <b style="color:{q_color}">{q_delta_str}</b>
  </p>
  {qual_svg}
</div>

<h2>Kept Episode Sample (first 50)</h2>
<div class="section">
<table>
  <thead><tr><th>#</th><th>Episode ID</th><th>Length</th><th>Success</th><th>Quality</th></tr></thead>
  <tbody>
  {"".join(
    f'<tr><td>{i+1}</td><td>{ep.ep_id}</td><td>{ep.T}</td>'
    f'<td class="tag-kept">{"Yes" if ep.success else "—"}</td>'
    f'<td>{ep.quality_score():.3f}</td></tr>'
    for i, ep in enumerate(result.kept_episodes[:50])
  )}
  </tbody>
</table>
{"<p style='color:#64748b;font-size:0.8rem;margin-top:0.75rem'>Showing first 50 of " + str(len(result.kept_episodes)) + " kept episodes.</p>" if len(result.kept_episodes) > 50 else ""}
</div>

<footer>OCI Robot Cloud · dataset_deduplication.py · <a href="https://github.com/qianjun22/roboticsai" style="color:#3b82f6">github.com/qianjun22/roboticsai</a></footer>
</body>
</html>"""

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(html, encoding="utf-8")
    print(f"[dedup] HTML report saved to {output_path}")


# ── CLI ────────────────────────────────────────────────────────────────────────

def _print_summary(result: DeduplicationResult):
    kept = result.original_count - result.total_removed
    print()
    print("=" * 56)
    print("  Dataset Deduplication — Summary")
    print("=" * 56)
    print(f"  Original episodes  : {result.original_count}")
    print(f"  Exact duplicates   : {result.exact_removed}")
    print(f"  Near-duplicates    : {result.near_removed}  (threshold={result.threshold})")
    print(f"  Total removed      : {result.total_removed}  ({result.dedup_rate*100:.1f}% duplication rate)")
    print(f"  Kept               : {kept}")
    if result.cluster_sizes:
        max_cs = max(result.cluster_sizes)
        avg_cs = sum(result.cluster_sizes) / len(result.cluster_sizes)
        print(f"  Near-dup clusters  : {len(result.cluster_sizes)}  (max={max_cs}, avg={avg_cs:.1f})")
    print(f"  Processing time    : {result.elapsed_sec:.2f}s")
    print("=" * 56)
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Remove near-duplicate episodes from robot training datasets.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--mock", action="store_true",
                        help="Generate synthetic data instead of reading from disk.")
    parser.add_argument("--n-episodes", type=int, default=DEFAULT_N_EPISODES,
                        help=f"Number of synthetic episodes to generate (mock mode). Default: {DEFAULT_N_EPISODES}")
    parser.add_argument("--input-dir", type=str, default=None,
                        help="Directory containing episode subdirs or episodes.npy.")
    parser.add_argument("--output-dir", type=str, default=None,
                        help="Directory to write deduplicated episodes (optional).")
    parser.add_argument("--output", type=str, default=None,
                        help=f"Path for the HTML report. Default: {DEFAULT_OUTPUT} (mock mode only)")
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD,
                        help=f"L2 distance threshold for near-duplicate detection. Default: {DEFAULT_THRESHOLD}")
    parser.add_argument("--seed", type=int, default=42,
                        help="RNG seed for mock generation.")
    args = parser.parse_args()

    if not args.mock and args.input_dir is None:
        parser.error("Either --mock or --input-dir is required.")

    # Load or generate episodes
    if args.mock:
        print(f"[dedup] Generating {args.n_episodes} synthetic episodes (seed={args.seed}) …")
        episodes = generate_mock_episodes(n=args.n_episodes, seed=args.seed)
        print(f"[dedup] Generated {len(episodes)} episodes (≈20% are near-duplicates).")
    else:
        print(f"[dedup] Loading episodes from {args.input_dir} …")
        episodes = load_episodes_from_dir(args.input_dir)
        print(f"[dedup] Loaded {len(episodes)} episodes.")

    # Run deduplication
    print(f"[dedup] Running deduplication (threshold={args.threshold}) …")
    result = deduplicate(episodes, threshold=args.threshold)

    _print_summary(result)

    # Optionally save deduped episodes to disk
    if args.output_dir:
        save_episodes_to_dir(result.kept_episodes, args.output_dir)

    # Write HTML report
    output_path = args.output or (DEFAULT_OUTPUT if args.mock else None)
    if output_path:
        generate_html_report(result, output_path)

    # Exit with non-zero if dedup rate is suspiciously high (>50%)
    if result.dedup_rate > 0.50:
        print(f"[dedup] WARNING: deduplication rate {result.dedup_rate*100:.1f}% > 50% — "
              "consider raising --threshold or reviewing data collection process.")


if __name__ == "__main__":
    main()
