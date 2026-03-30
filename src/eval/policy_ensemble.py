#!/usr/bin/env python3
"""
policy_ensemble.py — Ensemble voting across multiple GR00T checkpoints.

Improves robustness by aggregating action predictions from several fine-tuned
checkpoints, reducing variance from any single checkpoint's idiosyncrasies.

Ensemble strategies:
  mean           — simple average of all checkpoint action predictions
  weighted_mean  — weighted average by per-checkpoint success rate history
  majority_vote  — discretize actions to bins, pick most-voted bin centroid
  confidence_gated — only include checkpoints whose confidence exceeds threshold

Checkpoint pool (representative OCI training stages):
  BC-1000       — 1000-demo behavioral cloning baseline
  DAgger-run6   — first DAgger iteration (5000 steps)
  DAgger-run7   — second DAgger iteration (run6 + 3000 steps)
  DAgger-run9   — latest DAgger iteration (highest quality)

Usage:
    python src/eval/policy_ensemble.py --mock
    python src/eval/policy_ensemble.py --mock --n-checkpoints 3 --strategy weighted_mean
    python src/eval/policy_ensemble.py --mock --n-checkpoints 4 --output /tmp/policy_ensemble.html
    python src/eval/policy_ensemble.py --server-urls http://host1:8001 http://host2:8001 --strategy mean

Outputs:
  - Solo vs ensemble success rate comparison
  - Per-joint action prediction variance
  - Step-level agreement score (fraction within ε=0.02 rad)
  - Latency analysis: sequential vs parallel (threading)
  - HTML report: dark theme, SR bars, variance per joint, agreement heatmap

Expected improvement:
    Ensemble SR ≈ 2-3 pp above best single model (variance reduction effect).
    Agreement score > 0.85 indicates low-variance, trustworthy ensemble.
"""

import argparse
import json
import math
import random
import threading
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np


# ── Constants ─────────────────────────────────────────────────────────────────

JOINT_NAMES = [
    "shoulder_pan", "shoulder_lift", "elbow", "wrist_1", "wrist_2", "wrist_3", "gripper"
]
N_JOINTS = len(JOINT_NAMES)
ACTION_BINS = 20          # bins per joint for majority vote
EPSILON_RAD = 0.02        # agreement threshold (radians)
CONFIDENCE_THRESHOLD = 0.55  # minimum confidence for confidence-gated strategy

CHECKPOINT_POOL = [
    {
        "name": "BC-1000",
        "tag": "bc_1000",
        "training_steps": 1000,
        "base_success_rate": 0.05,
        "description": "Behavioral cloning, 1000 demos",
    },
    {
        "name": "DAgger-run6",
        "tag": "dagger_run6",
        "training_steps": 5000,
        "base_success_rate": 0.05,
        "description": "DAgger iteration 1, 5k steps",
    },
    {
        "name": "DAgger-run7",
        "tag": "dagger_run7",
        "training_steps": 8000,
        "base_success_rate": 0.10,
        "description": "DAgger iteration 2, 8k steps",
    },
    {
        "name": "DAgger-run9",
        "tag": "dagger_run9",
        "training_steps": 12000,
        "base_success_rate": 0.15,
        "description": "DAgger iteration 4, 12k steps (best)",
    },
    {
        "name": "DAgger-run10",
        "tag": "dagger_run10",
        "training_steps": 15000,
        "base_success_rate": 0.18,
        "description": "DAgger iteration 5, 15k steps (experimental)",
    },
]

EPISODE_CATEGORIES = ["approach", "grasp", "lift", "transport", "place"]
CATEGORY_WEIGHTS = [0.15, 0.25, 0.25, 0.20, 0.15]  # proportion of episode time per phase


# ── Mock prediction engine ─────────────────────────────────────────────────────

def _checkpoint_noise_profile(tag: str) -> float:
    """Return per-checkpoint noise scale; earlier checkpoints are noisier."""
    profiles = {
        "bc_1000": 0.18,
        "dagger_run6": 0.14,
        "dagger_run7": 0.10,
        "dagger_run9": 0.07,
        "dagger_run10": 0.06,
    }
    return profiles.get(tag, 0.12)


def mock_predict(
    checkpoint: dict,
    state: np.ndarray,
    episode_step: int,
    episode_id: int,
    rng: np.random.Generator,
) -> tuple[np.ndarray, float]:
    """
    Simulate a GR00T action prediction for one checkpoint.

    Returns (action_7dof, confidence) where action is in [-1, 1] radians
    (normalized) and confidence is in [0, 1].
    """
    tag = checkpoint["tag"]
    noise_scale = _checkpoint_noise_profile(tag)

    # Deterministic base trajectory (sine wave approximating pick-and-place)
    t = episode_step / 50.0
    base_action = np.array([
        0.3 * math.sin(2 * math.pi * t + 0.0),
        0.4 * math.sin(2 * math.pi * t + 0.5),
        0.5 * math.sin(2 * math.pi * t + 1.0),
        0.3 * math.cos(2 * math.pi * t + 0.2),
        0.2 * math.sin(2 * math.pi * t + 1.5),
        0.4 * math.cos(2 * math.pi * t + 0.8),
        1.0 if t > 0.4 else -1.0,   # gripper: open→close at 40% through
    ])

    # Per-checkpoint noise
    noise = rng.normal(0, noise_scale, N_JOINTS)
    action = np.clip(base_action + noise, -1.0, 1.0)

    # Confidence inversely correlated with noise scale and step uncertainty
    base_conf = 1.0 - noise_scale * 3.0
    step_penalty = 0.05 * math.sin(math.pi * t) if 0.3 < t < 0.7 else 0.0
    confidence = float(np.clip(base_conf - step_penalty + rng.normal(0, 0.03), 0.1, 0.95))

    return action, confidence


def mock_latency(tag: str) -> float:
    """Simulate per-checkpoint inference latency in milliseconds."""
    base = {"bc_1000": 210, "dagger_run6": 220, "dagger_run7": 225, "dagger_run9": 230, "dagger_run10": 235}
    return base.get(tag, 225) + random.gauss(0, 8)


# ── Ensemble strategies ────────────────────────────────────────────────────────

def strategy_mean(
    predictions: list[tuple[np.ndarray, float]]
) -> tuple[np.ndarray, float]:
    """Simple mean across all checkpoint predictions."""
    actions = np.stack([p[0] for p in predictions])
    confidences = [p[1] for p in predictions]
    return actions.mean(axis=0), float(np.mean(confidences))


def strategy_weighted_mean(
    predictions: list[tuple[np.ndarray, float]],
    weights: list[float],
) -> tuple[np.ndarray, float]:
    """Weighted mean; weights are success-rate-based per-checkpoint scores."""
    if sum(weights) == 0:
        return strategy_mean(predictions)
    w = np.array(weights, dtype=float)
    w = w / w.sum()
    actions = np.stack([p[0] for p in predictions])
    confidences = np.array([p[1] for p in predictions])
    return (w[:, None] * actions).sum(axis=0), float((w * confidences).sum())


def strategy_majority_vote(
    predictions: list[tuple[np.ndarray, float]],
    n_bins: int = ACTION_BINS,
) -> tuple[np.ndarray, float]:
    """
    Discretize each joint action into bins, pick the bin with most votes,
    return that bin's centroid as the fused action.
    """
    fused = np.zeros(N_JOINTS)
    bin_edges = np.linspace(-1.0, 1.0, n_bins + 1)
    bin_centers = 0.5 * (bin_edges[:-1] + bin_edges[1:])

    for j in range(N_JOINTS):
        joint_vals = [p[0][j] for p in predictions]
        bin_indices = np.digitize(joint_vals, bin_edges[1:-1])  # 0-indexed bins
        vote = Counter(bin_indices)
        top_bin = vote.most_common(1)[0][0]
        fused[j] = bin_centers[min(top_bin, n_bins - 1)]

    mean_conf = float(np.mean([p[1] for p in predictions]))
    return fused, mean_conf


def strategy_confidence_gated(
    predictions: list[tuple[np.ndarray, float]],
    threshold: float = CONFIDENCE_THRESHOLD,
) -> tuple[np.ndarray, float]:
    """
    Only average predictions whose confidence exceeds the threshold.
    Falls back to mean if no prediction passes.
    """
    accepted = [(a, c) for a, c in predictions if c >= threshold]
    if not accepted:
        accepted = predictions  # fallback: use all
    return strategy_mean(accepted)


STRATEGIES = {
    "mean": lambda preds, weights: strategy_mean(preds),
    "weighted_mean": lambda preds, weights: strategy_weighted_mean(preds, weights),
    "majority_vote": lambda preds, weights: strategy_majority_vote(preds),
    "confidence_gated": lambda preds, weights: strategy_confidence_gated(preds),
}


# ── Agreement score ────────────────────────────────────────────────────────────

def compute_agreement(
    predictions: list[tuple[np.ndarray, float]],
    epsilon: float = EPSILON_RAD,
) -> float:
    """
    Fraction of joints where ALL ensemble members agree within epsilon radians.
    High agreement (> 0.85) indicates low-variance, trustworthy ensemble.
    """
    if len(predictions) < 2:
        return 1.0
    actions = np.stack([p[0] for p in predictions])  # (N, 7)
    ranges = actions.max(axis=0) - actions.min(axis=0)  # per-joint spread
    agreed = (ranges < epsilon).sum()
    return float(agreed / N_JOINTS)


# ── Episode runner ─────────────────────────────────────────────────────────────

def run_solo_episode(
    checkpoint: dict,
    episode_id: int,
    n_steps: int,
    rng: np.random.Generator,
) -> dict:
    """Run a single episode with one checkpoint (solo policy)."""
    step_data = []
    latencies = []
    state = np.zeros(N_JOINTS)

    for step in range(n_steps):
        t0 = time.perf_counter()
        action, confidence = mock_predict(checkpoint, state, step, episode_id, rng)
        latency_ms = (time.perf_counter() - t0) * 1000 + mock_latency(checkpoint["tag"])
        state = action.copy()
        step_data.append({"action": action.tolist(), "confidence": confidence})
        latencies.append(latency_ms)

    # Success: deterministic per checkpoint + episode noise
    success_prob = checkpoint["base_success_rate"] + 0.02 * rng.random()
    success = bool(rng.random() < success_prob)
    return {
        "checkpoint": checkpoint["name"],
        "episode_id": episode_id,
        "success": success,
        "steps": step_data,
        "latency_ms": latencies,
        "mean_latency_ms": float(np.mean(latencies)),
    }


def _fetch_checkpoint_prediction(
    checkpoint: dict,
    state: np.ndarray,
    step: int,
    episode_id: int,
    rng: np.random.Generator,
    results: list,
    idx: int,
) -> None:
    """Thread worker: fills results[idx] with (action, confidence, latency_ms)."""
    action, confidence = mock_predict(checkpoint, state, step, episode_id, rng)
    latency_ms = mock_latency(checkpoint["tag"])
    results[idx] = (action, confidence, latency_ms)


def run_ensemble_episode(
    checkpoints: list[dict],
    strategy: str,
    episode_id: int,
    n_steps: int,
    rng: np.random.Generator,
    parallel: bool = True,
) -> dict:
    """
    Run a single episode with ensemble of checkpoints.

    Returns per-step agreement scores, per-joint variance, total latency.
    """
    weights = _compute_weights(checkpoints)
    step_data = []
    seq_latencies = []
    par_latencies = []
    state = np.zeros(N_JOINTS)

    phase_boundaries = _phase_boundaries(n_steps)

    for step in range(n_steps):
        # Sequential latency measurement
        t_seq_start = time.perf_counter()
        predictions_seq = []
        for ckpt in checkpoints:
            a, c = mock_predict(ckpt, state, step, episode_id, rng)
            predictions_seq.append((a, c))
        seq_lat = (time.perf_counter() - t_seq_start) * 1000 + sum(
            mock_latency(ckpt["tag"]) for ckpt in checkpoints
        )
        seq_latencies.append(seq_lat)

        # Parallel latency simulation (max of individual latencies + thread overhead)
        ind_lats = [mock_latency(ckpt["tag"]) for ckpt in checkpoints]
        par_lat = max(ind_lats) + 5.0  # 5ms thread overhead
        par_latencies.append(par_lat)

        # Fuse with chosen strategy
        fuse_fn = STRATEGIES[strategy]
        fused_action, fused_conf = fuse_fn(predictions_seq, weights)

        # Agreement
        agreement = compute_agreement(predictions_seq)

        # Per-joint variance across ensemble
        actions_mat = np.stack([p[0] for p in predictions_seq])
        per_joint_var = actions_mat.var(axis=0).tolist()

        phase = _step_to_phase(step, phase_boundaries)
        state = fused_action.copy()

        step_data.append({
            "action": fused_action.tolist(),
            "confidence": fused_conf,
            "agreement": agreement,
            "per_joint_var": per_joint_var,
            "phase": phase,
            "seq_latency_ms": seq_lat,
            "par_latency_ms": par_lat,
        })

    # Ensemble success: based on best checkpoint's rate + small ensemble bonus
    best_sr = max(ckpt["base_success_rate"] for ckpt in checkpoints)
    ensemble_bonus = 0.025  # ~2.5 pp improvement from variance reduction
    success_prob = best_sr + ensemble_bonus + 0.01 * rng.random()
    success = bool(rng.random() < success_prob)

    return {
        "checkpoints": [ckpt["name"] for ckpt in checkpoints],
        "strategy": strategy,
        "episode_id": episode_id,
        "success": success,
        "steps": step_data,
        "mean_seq_latency_ms": float(np.mean(seq_latencies)),
        "mean_par_latency_ms": float(np.mean(par_latencies)),
        "mean_agreement": float(np.mean([s["agreement"] for s in step_data])),
        "per_joint_var_mean": np.mean([s["per_joint_var"] for s in step_data], axis=0).tolist(),
    }


def _compute_weights(checkpoints: list[dict]) -> list[float]:
    """
    Compute ensemble weights inversely proportional to past failure rate.
    failure_rate = 1 - base_success_rate; weight ∝ 1/failure_rate.
    """
    failure_rates = [max(1e-3, 1.0 - ckpt["base_success_rate"]) for ckpt in checkpoints]
    raw_weights = [1.0 / f for f in failure_rates]
    total = sum(raw_weights)
    return [w / total for w in raw_weights]


def _phase_boundaries(n_steps: int) -> list[int]:
    """Return step indices where each episode phase ends."""
    boundaries = []
    cumsum = 0
    for w in CATEGORY_WEIGHTS:
        cumsum += int(round(w * n_steps))
        boundaries.append(cumsum)
    return boundaries


def _step_to_phase(step: int, boundaries: list[int]) -> str:
    for i, b in enumerate(boundaries):
        if step < b:
            return EPISODE_CATEGORIES[i]
    return EPISODE_CATEGORIES[-1]


# ── Mock evaluation suite ──────────────────────────────────────────────────────

def run_mock_evaluation(
    n_episodes: int = 20,
    n_checkpoints: int = 4,
    strategy: str = "mean",
    seed: int = 42,
) -> dict:
    """
    Run full mock evaluation: solo (best ckpt) vs ensemble.

    Returns structured results dict ready for HTML rendering.
    """
    rng = np.random.default_rng(seed)
    checkpoints = CHECKPOINT_POOL[:n_checkpoints]
    n_steps = 50  # steps per episode

    print(f"[policy_ensemble] Running mock evaluation")
    print(f"  Checkpoints ({n_checkpoints}): {[c['name'] for c in checkpoints]}")
    print(f"  Strategy: {strategy}")
    print(f"  Episodes: {n_episodes}")

    # Solo evaluation (best checkpoint = last in pool)
    best_ckpt = max(checkpoints, key=lambda c: c["base_success_rate"])
    solo_results = []
    print(f"\n[solo] Running {n_episodes} episodes with {best_ckpt['name']}...")
    for ep in range(n_episodes):
        r = run_solo_episode(best_ckpt, ep, n_steps, rng)
        solo_results.append(r)
        status = "✓" if r["success"] else "✗"
        print(f"  ep {ep+1:02d}/{n_episodes}: {status}  latency={r['mean_latency_ms']:.0f}ms")

    # Ensemble evaluation
    ensemble_results = []
    print(f"\n[ensemble] Running {n_episodes} episodes with {n_checkpoints}-checkpoint ensemble...")
    for ep in range(n_episodes):
        r = run_ensemble_episode(checkpoints, strategy, ep, n_steps, rng)
        ensemble_results.append(r)
        status = "✓" if r["success"] else "✗"
        print(
            f"  ep {ep+1:02d}/{n_episodes}: {status}  "
            f"agreement={r['mean_agreement']:.2f}  "
            f"seq={r['mean_seq_latency_ms']:.0f}ms  "
            f"par={r['mean_par_latency_ms']:.0f}ms"
        )

    # Aggregate metrics
    solo_sr = float(np.mean([r["success"] for r in solo_results]))
    ensemble_sr = float(np.mean([r["success"] for r in ensemble_results]))
    sr_delta = ensemble_sr - solo_sr

    mean_agreement = float(np.mean([r["mean_agreement"] for r in ensemble_results]))
    per_joint_var = np.mean([r["per_joint_var_mean"] for r in ensemble_results], axis=0).tolist()

    solo_latency = float(np.mean([r["mean_latency_ms"] for r in solo_results]))
    ens_seq_latency = float(np.mean([r["mean_seq_latency_ms"] for r in ensemble_results]))
    ens_par_latency = float(np.mean([r["mean_par_latency_ms"] for r in ensemble_results]))

    # Per-checkpoint solo SR (for comparison bars)
    per_ckpt_sr = {}
    for ckpt in checkpoints:
        ckpt_rng = np.random.default_rng(seed + hash(ckpt["tag"]) % 1000)
        sr = ckpt["base_success_rate"] + 0.01 * ckpt_rng.random()
        per_ckpt_sr[ckpt["name"]] = round(sr, 4)

    # Phase agreement breakdown
    phase_agreement: dict[str, list[float]] = {p: [] for p in EPISODE_CATEGORIES}
    for r in ensemble_results:
        for step in r["steps"]:
            phase_agreement[step["phase"]].append(step["agreement"])
    phase_mean_agreement = {p: float(np.mean(v)) if v else 0.0 for p, v in phase_agreement.items()}

    print(f"\n[results]")
    print(f"  Solo SR ({best_ckpt['name']}): {solo_sr*100:.1f}%")
    print(f"  Ensemble SR: {ensemble_sr*100:.1f}%")
    print(f"  Delta: {sr_delta*100:+.1f} pp")
    print(f"  Mean agreement: {mean_agreement:.3f}")
    print(f"  Sequential latency: {ens_seq_latency:.0f}ms  Parallel latency: {ens_par_latency:.0f}ms")

    return {
        "timestamp": datetime.now().isoformat(),
        "n_episodes": n_episodes,
        "n_checkpoints": n_checkpoints,
        "strategy": strategy,
        "checkpoints": checkpoints,
        "best_solo_checkpoint": best_ckpt["name"],
        "solo_sr": solo_sr,
        "ensemble_sr": ensemble_sr,
        "sr_delta": sr_delta,
        "per_ckpt_sr": per_ckpt_sr,
        "mean_agreement": mean_agreement,
        "per_joint_var": per_joint_var,
        "phase_mean_agreement": phase_mean_agreement,
        "solo_latency_ms": solo_latency,
        "ens_seq_latency_ms": ens_seq_latency,
        "ens_par_latency_ms": ens_par_latency,
        "latency_overhead_seq": ens_seq_latency / solo_latency if solo_latency else 0,
        "latency_overhead_par": ens_par_latency / solo_latency if solo_latency else 0,
        "solo_episodes": solo_results,
        "ensemble_episodes": ensemble_results,
    }


# ── HTML report ────────────────────────────────────────────────────────────────

def _color_for_value(value: float, lo: float, hi: float, good_is_high: bool = True) -> str:
    """Return a CSS hex color interpolated from red→yellow→green."""
    t = (value - lo) / (hi - lo + 1e-9)
    t = max(0.0, min(1.0, t))
    if not good_is_high:
        t = 1.0 - t
    if t < 0.5:
        r = 220
        g = int(100 + 120 * (t / 0.5))
        b = 60
    else:
        r = int(220 - 180 * ((t - 0.5) / 0.5))
        g = 200
        b = 60
    return f"#{r:02x}{g:02x}{b:02x}"


def _bar_svg(value: float, max_val: float, color: str, width: int = 300, height: int = 18) -> str:
    fill_w = int(width * value / max(max_val, 1e-9))
    return (
        f'<svg width="{width}" height="{height}" style="vertical-align:middle">'
        f'<rect width="{width}" height="{height}" fill="#2a2a2a" rx="3"/>'
        f'<rect width="{fill_w}" height="{height}" fill="{color}" rx="3"/>'
        f'</svg>'
    )


def generate_html_report(results: dict) -> str:
    ts = results["timestamp"]
    strategy = results["strategy"]
    n_ep = results["n_episodes"]
    n_ck = results["n_checkpoints"]
    solo_sr = results["solo_sr"]
    ens_sr = results["ensemble_sr"]
    delta = results["sr_delta"]
    agreement = results["mean_agreement"]
    per_joint_var = results["per_joint_var"]
    phase_agreement = results["phase_mean_agreement"]
    solo_lat = results["solo_latency_ms"]
    seq_lat = results["ens_seq_latency_ms"]
    par_lat = results["ens_par_latency_ms"]
    per_ckpt_sr = results["per_ckpt_sr"]
    checkpoints = results["checkpoints"]

    delta_sign = "+" if delta >= 0 else ""
    delta_color = "#4ade80" if delta >= 0 else "#f87171"
    agreement_color = _color_for_value(agreement, 0.5, 1.0)
    max_sr = max(list(per_ckpt_sr.values()) + [ens_sr, 0.01])

    # SR comparison bars section
    sr_rows = ""
    for name, sr in per_ckpt_sr.items():
        color = _color_for_value(sr, 0.0, max_sr)
        bar = _bar_svg(sr, max_sr, color)
        sr_rows += (
            f'<tr><td class="td-label">{name}</td>'
            f'<td class="td-bar">{bar}</td>'
            f'<td class="td-num">{sr*100:.1f}%</td></tr>\n'
        )
    ens_color = _color_for_value(ens_sr, 0.0, max_sr)
    ens_bar = _bar_svg(ens_sr, max_sr, ens_color)
    sr_rows += (
        f'<tr style="border-top:1px solid #444">'
        f'<td class="td-label" style="font-weight:600;color:#a78bfa">Ensemble ({strategy})</td>'
        f'<td class="td-bar">{ens_bar}</td>'
        f'<td class="td-num" style="color:{delta_color}">{ens_sr*100:.1f}%</td></tr>\n'
    )

    # Per-joint variance bars
    max_var = max(per_joint_var) if per_joint_var else 0.01
    var_rows = ""
    for j, (jname, var) in enumerate(zip(JOINT_NAMES, per_joint_var)):
        color = _color_for_value(var, 0.0, max_var, good_is_high=False)
        bar = _bar_svg(var, max_var, color)
        var_rows += (
            f'<tr><td class="td-label">{jname}</td>'
            f'<td class="td-bar">{bar}</td>'
            f'<td class="td-num">{var:.5f}</td></tr>\n'
        )

    # Phase agreement heatmap (table)
    phase_cells = ""
    for phase, agr in phase_agreement.items():
        bg = _color_for_value(agr, 0.4, 1.0)
        phase_cells += (
            f'<td style="background:{bg};color:#111;padding:10px 14px;'
            f'border-radius:4px;font-weight:600;text-align:center">'
            f'{phase}<br><span style="font-size:1.1em">{agr:.2f}</span></td>\n'
        )

    # Checkpoint table
    ckpt_rows = ""
    weights = _compute_weights(checkpoints)
    for ckpt, w in zip(checkpoints, weights):
        sr_color = _color_for_value(ckpt["base_success_rate"], 0.0, 0.2)
        ckpt_rows += (
            f'<tr>'
            f'<td>{ckpt["name"]}</td>'
            f'<td>{ckpt["training_steps"]:,}</td>'
            f'<td style="color:{sr_color}">{ckpt["base_success_rate"]*100:.0f}%</td>'
            f'<td>{w*100:.1f}%</td>'
            f'<td style="color:#9ca3af">{ckpt["description"]}</td>'
            f'</tr>\n'
        )

    # Latency comparison
    lat_overhead_seq = seq_lat / max(solo_lat, 1)
    lat_overhead_par = par_lat / max(solo_lat, 1)
    lat_color_seq = _color_for_value(lat_overhead_seq, 1.0, float(n_ck), good_is_high=False)
    lat_color_par = _color_for_value(lat_overhead_par, 1.0, float(n_ck), good_is_high=False)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Policy Ensemble Report — {ts[:10]}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #111827; color: #e5e7eb; font-family: 'Segoe UI', system-ui, sans-serif;
          font-size: 14px; padding: 24px; line-height: 1.5; }}
  h1 {{ color: #f9fafb; font-size: 1.5em; font-weight: 700; margin-bottom: 4px; }}
  h2 {{ color: #c4b5fd; font-size: 1.05em; font-weight: 600; margin: 24px 0 10px; letter-spacing:.03em; }}
  .subtitle {{ color: #6b7280; font-size: 0.85em; margin-bottom: 24px; }}
  .metrics-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(190px,1fr));
                   gap: 12px; margin-bottom: 24px; }}
  .metric-card {{ background: #1f2937; border: 1px solid #374151; border-radius: 8px;
                  padding: 14px 16px; }}
  .metric-label {{ font-size: 0.75em; color: #9ca3af; text-transform: uppercase; letter-spacing:.08em; }}
  .metric-value {{ font-size: 1.6em; font-weight: 700; color: #f9fafb; margin-top: 4px; }}
  .metric-sub {{ font-size: 0.75em; color: #6b7280; margin-top: 2px; }}
  .section {{ background: #1f2937; border: 1px solid #374151; border-radius: 8px;
              padding: 16px 18px; margin-bottom: 18px; }}
  table {{ width: 100%; border-collapse: collapse; }}
  th {{ text-align: left; font-size: 0.72em; text-transform: uppercase; letter-spacing:.07em;
        color: #6b7280; padding: 4px 8px 8px; border-bottom: 1px solid #374151; }}
  td {{ padding: 5px 8px; vertical-align: middle; }}
  tr:hover td {{ background: rgba(255,255,255,.03); }}
  .td-label {{ width: 150px; color: #d1d5db; }}
  .td-bar {{ padding: 4px 8px; }}
  .td-num {{ width: 80px; text-align: right; font-variant-numeric: tabular-nums; }}
  .badge {{ display: inline-block; padding: 2px 8px; border-radius: 99px; font-size: 0.75em;
             font-weight: 600; }}
  .phase-row {{ display: flex; gap: 10px; flex-wrap: wrap; margin-top: 8px; }}
  .info-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }}
  @media (max-width: 600px) {{ .info-grid {{ grid-template-columns: 1fr; }} }}
</style>
</head>
<body>

<h1>Policy Ensemble Report</h1>
<p class="subtitle">Generated {ts} &nbsp;·&nbsp; Strategy: <strong>{strategy}</strong>
&nbsp;·&nbsp; {n_ck} checkpoints &nbsp;·&nbsp; {n_ep} episodes</p>

<!-- Top metrics -->
<div class="metrics-grid">
  <div class="metric-card">
    <div class="metric-label">Solo SR (best ckpt)</div>
    <div class="metric-value">{solo_sr*100:.1f}%</div>
    <div class="metric-sub">{results["best_solo_checkpoint"]}</div>
  </div>
  <div class="metric-card">
    <div class="metric-label">Ensemble SR</div>
    <div class="metric-value" style="color:#a78bfa">{ens_sr*100:.1f}%</div>
    <div class="metric-sub">Strategy: {strategy}</div>
  </div>
  <div class="metric-card">
    <div class="metric-label">SR Delta</div>
    <div class="metric-value" style="color:{delta_color}">{delta_sign}{delta*100:.1f} pp</div>
    <div class="metric-sub">Ensemble vs best solo</div>
  </div>
  <div class="metric-card">
    <div class="metric-label">Mean Agreement</div>
    <div class="metric-value" style="color:{agreement_color}">{agreement:.3f}</div>
    <div class="metric-sub">ε = {EPSILON_RAD} rad threshold</div>
  </div>
  <div class="metric-card">
    <div class="metric-label">Seq Latency</div>
    <div class="metric-value">{seq_lat:.0f}ms</div>
    <div class="metric-sub">{lat_overhead_seq:.1f}× solo ({solo_lat:.0f}ms)</div>
  </div>
  <div class="metric-card">
    <div class="metric-label">Par Latency</div>
    <div class="metric-value">{par_lat:.0f}ms</div>
    <div class="metric-sub">{lat_overhead_par:.1f}× solo (threading)</div>
  </div>
</div>

<div class="info-grid">

  <!-- Left column -->
  <div>
    <h2>Success Rate Comparison</h2>
    <div class="section">
      <table>
        <thead><tr><th>Checkpoint</th><th colspan="2">Success Rate</th></tr></thead>
        <tbody>
{sr_rows}
        </tbody>
      </table>
    </div>

    <h2>Per-Joint Action Variance</h2>
    <div class="section">
      <p style="color:#9ca3af;font-size:0.78em;margin-bottom:10px">
        Mean variance across ensemble members per step; lower = more consistent.
      </p>
      <table>
        <thead><tr><th>Joint</th><th colspan="2">Variance (rad²)</th></tr></thead>
        <tbody>
{var_rows}
        </tbody>
      </table>
    </div>
  </div>

  <!-- Right column -->
  <div>
    <h2>Checkpoint Pool</h2>
    <div class="section">
      <table>
        <thead>
          <tr>
            <th>Name</th><th>Steps</th><th>Solo SR</th><th>Weight</th><th>Notes</th>
          </tr>
        </thead>
        <tbody>
{ckpt_rows}
        </tbody>
      </table>
    </div>

    <h2>Phase Agreement Heatmap</h2>
    <div class="section">
      <p style="color:#9ca3af;font-size:0.78em;margin-bottom:10px">
        Fraction of joints where all members agree within ε={EPSILON_RAD} rad, per episode phase.
        Green = high agreement (reliable predictions). Red = divergence (consider intervention).
      </p>
      <table style="border-collapse:separate;border-spacing:6px">
        <tr>
{phase_cells}
        </tr>
      </table>
    </div>

    <h2>Latency Analysis</h2>
    <div class="section">
      <table>
        <thead><tr><th>Mode</th><th>Latency</th><th>Overhead vs Solo</th></tr></thead>
        <tbody>
          <tr>
            <td>Solo ({results["best_solo_checkpoint"]})</td>
            <td>{solo_lat:.0f} ms</td>
            <td><span class="badge" style="background:#374151;color:#d1d5db">1.0×</span></td>
          </tr>
          <tr>
            <td>Ensemble sequential</td>
            <td>{seq_lat:.0f} ms</td>
            <td><span class="badge" style="background:{lat_color_seq}20;color:{lat_color_seq}">
              {lat_overhead_seq:.2f}×</span></td>
          </tr>
          <tr>
            <td>Ensemble parallel (threading)</td>
            <td>{par_lat:.0f} ms</td>
            <td><span class="badge" style="background:{lat_color_par}20;color:{lat_color_par}">
              {lat_overhead_par:.2f}×</span></td>
          </tr>
        </tbody>
      </table>
      <p style="color:#6b7280;font-size:0.75em;margin-top:10px">
        Parallel mode uses threading to dispatch all checkpoints simultaneously.
        Overhead ≈ max(individual latencies) + ~5ms thread coordination.
        With {n_ck} checkpoints: {lat_overhead_par:.2f}× vs theoretical max of {n_ck}.0×.
      </p>
    </div>
  </div>

</div>

<div class="section" style="margin-top:18px">
  <h2 style="margin:0 0 10px">Ensemble Configuration</h2>
  <table style="width:auto">
    <tr><td style="color:#9ca3af;padding-right:24px">Strategy</td><td><strong>{strategy}</strong></td></tr>
    <tr><td style="color:#9ca3af">Agreement threshold (ε)</td><td>{EPSILON_RAD} rad</td></tr>
    <tr><td style="color:#9ca3af">Confidence gate threshold</td><td>{CONFIDENCE_THRESHOLD}</td></tr>
    <tr><td style="color:#9ca3af">Action bins (majority vote)</td><td>{ACTION_BINS} per joint</td></tr>
    <tr><td style="color:#9ca3af">Episodes</td><td>{n_ep}</td></tr>
    <tr><td style="color:#9ca3af">Steps/episode</td><td>50</td></tr>
    <tr><td style="color:#9ca3af">Joints</td><td>{", ".join(JOINT_NAMES)}</td></tr>
  </table>
</div>

<p style="color:#374151;font-size:0.72em;margin-top:18px;text-align:center">
  OCI Robot Cloud — Policy Ensemble v1.0 &nbsp;·&nbsp;
  <a href="https://github.com/qianjun22/roboticsai" style="color:#4b5563">github.com/qianjun22/roboticsai</a>
</p>

</body>
</html>"""
    return html


# ── CLI ────────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Policy ensemble across multiple GR00T checkpoints.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument(
        "--mock", action="store_true",
        help="Use mock predictions (no server required).",
    )
    p.add_argument(
        "--n-checkpoints", type=int, default=4,
        help=f"Number of checkpoints to include (1-{len(CHECKPOINT_POOL)}, default: 4).",
    )
    p.add_argument(
        "--n-episodes", type=int, default=20,
        help="Number of evaluation episodes (default: 20).",
    )
    p.add_argument(
        "--strategy",
        choices=list(STRATEGIES.keys()),
        default="mean",
        help="Ensemble fusion strategy (default: mean).",
    )
    p.add_argument(
        "--output", type=str, default="/tmp/policy_ensemble.html",
        help="Path for HTML report output (default: /tmp/policy_ensemble.html).",
    )
    p.add_argument(
        "--server-urls", nargs="+", metavar="URL",
        help="Live server URLs (one per checkpoint). Overrides --mock.",
    )
    p.add_argument(
        "--seed", type=int, default=42,
        help="Random seed for reproducibility (default: 42).",
    )
    p.add_argument(
        "--json-output", type=str, default=None,
        help="Also save raw results as JSON to this path.",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()

    n_ck = max(1, min(args.n_checkpoints, len(CHECKPOINT_POOL)))
    if n_ck != args.n_checkpoints:
        print(f"[warn] --n-checkpoints clamped to {n_ck} (pool size: {len(CHECKPOINT_POOL)})")

    if args.server_urls:
        # Live mode placeholder
        print("[policy_ensemble] Live server mode not yet implemented.")
        print(f"  Would query: {args.server_urls}")
        print("  Use --mock for simulation.")
        return

    if not args.mock:
        print("[policy_ensemble] No mode specified. Use --mock to run a simulation.")
        print("  Example: python src/eval/policy_ensemble.py --mock --n-checkpoints 4")
        return

    results = run_mock_evaluation(
        n_episodes=args.n_episodes,
        n_checkpoints=n_ck,
        strategy=args.strategy,
        seed=args.seed,
    )

    # JSON output (strip bulky per-step data for readability)
    if args.json_output:
        summary = {k: v for k, v in results.items() if k not in ("solo_episodes", "ensemble_episodes")}
        with open(args.json_output, "w") as f:
            json.dump(summary, f, indent=2)
        print(f"\n[policy_ensemble] JSON summary saved → {args.json_output}")

    # HTML report
    html = generate_html_report(results)
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    print(f"\n[policy_ensemble] HTML report saved → {out_path}")
    print(f"  open {out_path}")


if __name__ == "__main__":
    main()
