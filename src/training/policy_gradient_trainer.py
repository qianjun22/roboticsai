#!/usr/bin/env python3
"""
PPO-Based Policy Gradient Fine-Tuning Simulation for GR00T Robot Policy.

Simulates a full Proximal Policy Optimization training loop for the GR00T robot
policy without requiring PyTorch or GPU — all numerics are handled in pure Python
stdlib (math, random) with no third-party imports.

Builds on the DAgger infrastructure established in dagger_train.py and
rl_finetune.py, sharing the same task setup: Franka pick-and-lift, success when
the cube is lifted > 8 cm above table (z > 0.78 m).

Architecture (simulated):
  Actor  (GR00T policy head)  → action distribution (mean, log_std)
  Critic (value function)     → scalar V(s)

PPO hyper-parameters:
  rollout_steps   = 2048    (per iteration, across 64 envs)
  num_envs        = 64
  ppo_epochs      = 4
  minibatch_size  = 256
  clip_eps        = 0.2
  entropy_coef    = 0.01
  value_coef      = 0.5
  gamma           = 0.99
  gae_lambda      = 0.95

Learning rate schedule: linear warmup (100 steps) → cosine decay to 1e-6.

Early stopping: success rate > 0.85 for 3 consecutive iterations.

Reward shaping:
  +10.0   task completion (cube lifted above threshold)
  -0.01   per-step penalty
  +r_goal goal-distance proportional reward (0–1 range)
  -1.0    collision penalty

Convergence model: SR starts at ~5% (BC / DAgger baseline), follows a logistic
growth curve peaking around ~78% by iter 150, matching the empirical trajectory
documented in the session notes (BC 5%, DAgger run5 5%, fine-tuned target ~78%).

Usage:
    python src/training/policy_gradient_trainer.py --mock
    python src/training/policy_gradient_trainer.py --mock --n-iters 100 --seed 7
    python src/training/policy_gradient_trainer.py --mock --output /tmp/ppo_report.html

References:
    Schulman et al. 2017 — Proximal Policy Optimization Algorithms
    Black et al. 2024   — π0 flow matching as RL objective
    rl_finetune.py      — residual PPO head over frozen GR00T server
    dagger_train.py     — DAgger iterative rollout / expert correction
"""

from __future__ import annotations

import argparse
import json
import math
import random
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


# ─────────────────────────────────────────────────────────────────────────────
# Dataclasses
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class PPOConfig:
    """All hyper-parameters for the PPO training run."""
    # rollout
    rollout_steps: int = 2048
    num_envs: int = 64
    # PPO update
    ppo_epochs: int = 4
    minibatch_size: int = 256
    clip_eps: float = 0.2
    entropy_coef: float = 0.01
    value_coef: float = 0.5
    # GAE
    gamma: float = 0.99
    gae_lambda: float = 0.95
    # LR schedule
    lr_init: float = 3e-4
    lr_min: float = 1e-6
    warmup_steps: int = 100
    # early stopping
    early_stop_threshold: float = 0.85
    early_stop_patience: int = 3
    # reward shaping
    reward_task_complete: float = 10.0
    reward_step_penalty: float = -0.01
    reward_collision: float = -1.0
    # misc
    n_iters: int = 200
    seed: int = 42


@dataclass
class IterationMetrics:
    """Metrics recorded for a single PPO iteration."""
    iteration: int
    policy_loss: float
    value_loss: float
    entropy: float
    kl_divergence: float
    clip_fraction: float
    explained_variance: float
    episode_reward_mean: float
    episode_reward_std: float
    episode_length_mean: float
    success_rate: float
    learning_rate: float
    grad_norm: float
    fps: float
    total_env_steps: int
    elapsed_seconds: float
    early_stop: bool = False


@dataclass
class TrainingResult:
    """Aggregate result of the full PPO training run."""
    config: PPOConfig
    checkpoint: str
    metrics: List[IterationMetrics] = field(default_factory=list)
    final_success_rate: float = 0.0
    best_success_rate: float = 0.0
    best_iteration: int = 0
    early_stopped: bool = False
    early_stop_iteration: Optional[int] = None
    total_env_steps: int = 0
    total_elapsed_seconds: float = 0.0


# ─────────────────────────────────────────────────────────────────────────────
# Learning rate schedule
# ─────────────────────────────────────────────────────────────────────────────

def lr_schedule(step: int, config: PPOConfig) -> float:
    """Linear warmup (warmup_steps) followed by cosine decay to lr_min."""
    if step < config.warmup_steps:
        return config.lr_init * (step + 1) / config.warmup_steps
    total_decay = max(config.n_iters * config.ppo_epochs - config.warmup_steps, 1)
    t = min(step - config.warmup_steps, total_decay)
    cosine = 0.5 * (1.0 + math.cos(math.pi * t / total_decay))
    return config.lr_min + (config.lr_init - config.lr_min) * cosine


# ─────────────────────────────────────────────────────────────────────────────
# Simulation helpers — pure stdlib
# ─────────────────────────────────────────────────────────────────────────────

def _sigmoid(x: float) -> float:
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    e = math.exp(x)
    return e / (1.0 + e)


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def simulate_success_rate(iteration: int, rng: random.Random) -> float:
    """
    Logistic growth curve for success rate, calibrated to:
      iter   0 → ~5%   (BC / DAgger baseline — matches closed_loop_eval.py 5%)
      iter  75 → ~30%
      iter 150 → ~78%
      iter 200 → ~82%
    """
    L  = 0.86    # asymptote
    k  = 0.056   # growth rate
    x0 = 100.0   # midpoint

    base = L * _sigmoid(k * (iteration - x0))
    base = max(0.04, base)

    # organic noise: sinusoidal oscillation + white noise
    noise = 0.025 * math.sin(iteration * 0.41) + rng.gauss(0, 0.018)
    return _clamp(base + noise, 0.02, 0.99)


def simulate_episode_reward(
    sr: float,
    rng: random.Random,
    config: PPOConfig,
) -> tuple[float, float, float]:
    """Return (reward_mean, reward_std, ep_length_mean)."""
    max_steps = 500
    success_steps = 250   # average steps on a successful episode

    goal_reward_success = 0.8
    goal_reward_fail    = 0.2
    collision_rate      = 0.05   # 5% of failed episodes hit something

    r_success = (config.reward_task_complete
                 + config.reward_step_penalty * success_steps
                 + goal_reward_success)   # ≈ +7.3

    r_fail = (config.reward_step_penalty * max_steps
              + goal_reward_fail
              + collision_rate * config.reward_collision)   # ≈ −5.05

    mean_r = sr * r_success + (1.0 - sr) * r_fail + rng.gauss(0, 0.4)
    std_r  = max(0.5, 2.5 + 3.0 * (1.0 - sr) + rng.gauss(0, 0.3))
    ep_len = max_steps - sr * (max_steps - success_steps) + rng.gauss(0, 12)
    return mean_r, std_r, ep_len


def simulate_ppo_losses(
    iteration: int,
    rng: random.Random,
) -> tuple[float, float, float, float, float, float]:
    """Return (policy_loss, value_loss, entropy, kl_div, clip_frac, grad_norm)."""
    p = min(iteration / 200.0, 1.0)

    policy_loss = max(0.005, 0.15  * math.exp(-2.5  * p) + 0.020 + rng.gauss(0, 0.008))
    value_loss  = max(0.010, 0.80  * math.exp(-3.0  * p) + 0.050 + rng.gauss(0, 0.030))
    entropy     = max(0.050, 1.20  * math.exp(-1.8  * p) + 0.300 + rng.gauss(0, 0.050))
    kl_div      = max(1e-4,  0.012 + 0.008 * (1.0 - p)         + rng.gauss(0, 0.003))
    clip_frac   = _clamp(0.25 * math.exp(-2.0 * p) + 0.05       + rng.gauss(0, 0.020), 0.0, 1.0)
    grad_norm   = max(0.05,  0.40  * math.exp(-2.0  * p) + 0.080 + rng.gauss(0, 0.030))
    return policy_loss, value_loss, entropy, kl_div, clip_frac, grad_norm


def simulate_explained_variance(sr: float, rng: random.Random) -> float:
    """Critic explained variance improves as SR improves."""
    return _clamp(_clamp(sr * 1.05, 0.0, 0.95) + rng.gauss(0, 0.04), -0.1, 1.0)


def simulate_gae(
    rewards: List[float],
    values: List[float],
    dones: List[float],
    config: PPOConfig,
) -> List[float]:
    """
    Generalised Advantage Estimation (GAE-λ).

    delta_t   = r_t + γ * V(s_{t+1}) * (1 − done_t) − V(s_t)
    A(t)      = Σ_{l≥0} (γλ)^l * delta_{t+l}
    """
    T = len(rewards)
    advantages = [0.0] * T
    last_adv = 0.0
    for t in reversed(range(T)):
        next_val = values[t + 1] if t + 1 < len(values) else 0.0
        delta = rewards[t] + config.gamma * next_val * (1.0 - dones[t]) - values[t]
        last_adv = delta + config.gamma * config.gae_lambda * (1.0 - dones[t]) * last_adv
        advantages[t] = last_adv
    return advantages


# ─────────────────────────────────────────────────────────────────────────────
# Main training loop
# ─────────────────────────────────────────────────────────────────────────────

def run_ppo_training(config: PPOConfig, checkpoint: str) -> TrainingResult:
    """
    Simulate a full PPO training run and return structured results.

    Per-iteration pipeline:
      1. Collect rollout_steps × num_envs transitions (simulated)
      2. Compute GAE advantages over a representative buffer
      3. Run ppo_epochs PPO update epochs across minibatches
      4. Record all metrics
      5. Apply early stopping when SR criterion is met
    """
    rng = random.Random(config.seed)
    result = TrainingResult(config=config, checkpoint=checkpoint)

    run_start = time.time()
    lr_step = 0
    consecutive_hits = 0
    prev_sr = 0.05

    print(
        f"\n{'─' * 88}\n"
        f"  OCI Robot Cloud — PPO Policy Gradient Trainer\n"
        f"  Checkpoint: {checkpoint}\n"
        f"  GR00T N1.6 · Franka pick-and-lift · "
        f"{config.num_envs} envs × {config.rollout_steps} rollout steps\n"
        f"  γ={config.gamma}  λ={config.gae_lambda}  "
        f"clip_ε={config.clip_eps}  entropy={config.entropy_coef}  "
        f"value={config.value_coef}  seed={config.seed}\n"
        f"{'─' * 88}"
    )
    _print_header()

    for iteration in range(config.n_iters):
        # ── Simulated rollout buffer ──────────────────────────────────────────
        n_buf = 32   # representative buffer size for GAE demo
        rewards = [rng.gauss(0.1, 0.5) + config.reward_step_penalty for _ in range(n_buf)]
        values  = [rng.gauss(1.0, 0.3) for _ in range(n_buf + 1)]
        dones   = [1.0 if rng.random() < 0.02 else 0.0 for _ in range(n_buf)]
        _advantages = simulate_gae(rewards, values, dones, config)  # noqa: unused

        # ── Metrics ───────────────────────────────────────────────────────────
        raw_sr = simulate_success_rate(iteration, rng)
        sr = _clamp(0.7 * raw_sr + 0.3 * prev_sr + rng.gauss(0, 0.005), 0.01, 0.99)
        prev_sr = sr

        reward_mean, reward_std, ep_len = simulate_episode_reward(sr, rng, config)
        policy_loss, value_loss, entropy, kl_div, clip_frac, grad_norm = (
            simulate_ppo_losses(iteration, rng)
        )
        explained_var = simulate_explained_variance(sr, rng)

        lr_step += config.ppo_epochs
        lr = lr_schedule(lr_step, config)

        # Simulated throughput: ~3000 fps across 64 envs
        rollout_frames = config.num_envs * config.rollout_steps
        fps = rollout_frames / (rollout_frames / (3000.0 + rng.gauss(0, 200.0)))

        total_env_steps = (iteration + 1) * rollout_frames
        elapsed = time.time() - run_start

        stop_flag = False
        if sr >= config.early_stop_threshold:
            consecutive_hits += 1
        else:
            consecutive_hits = 0
        if consecutive_hits >= config.early_stop_patience:
            stop_flag = True

        m = IterationMetrics(
            iteration=iteration,
            policy_loss=policy_loss,
            value_loss=value_loss,
            entropy=entropy,
            kl_divergence=kl_div,
            clip_fraction=clip_frac,
            explained_variance=explained_var,
            episode_reward_mean=reward_mean,
            episode_reward_std=reward_std,
            episode_length_mean=ep_len,
            success_rate=sr,
            learning_rate=lr,
            grad_norm=grad_norm,
            fps=fps,
            total_env_steps=total_env_steps,
            elapsed_seconds=elapsed,
            early_stop=stop_flag,
        )
        result.metrics.append(m)

        if sr > result.best_success_rate:
            result.best_success_rate = sr
            result.best_iteration = iteration

        _print_row(m)

        if stop_flag:
            print(
                f"\n  [EarlyStopping] SR={sr:.1%} ≥ {config.early_stop_threshold:.0%} "
                f"for {config.early_stop_patience} consecutive iterations — "
                f"stopping at iter {iteration}."
            )
            result.early_stopped = True
            result.early_stop_iteration = iteration
            break

    result.final_success_rate = result.metrics[-1].success_rate
    result.total_env_steps     = result.metrics[-1].total_env_steps
    result.total_elapsed_seconds = time.time() - run_start

    status = "CONVERGED" if result.early_stopped else "MAX_ITERS"
    print(f"\n{'─' * 88}")
    print(f"  {status} | {len(result.metrics)} iterations | "
          f"Final SR={result.final_success_rate:.1%} | "
          f"Best SR={result.best_success_rate:.1%} @ iter {result.best_iteration}")
    print(f"  Total env steps: {result.total_env_steps:,} | "
          f"Wall time: {result.total_elapsed_seconds:.2f}s (simulation)")
    print(f"{'─' * 88}\n")

    return result


# ─────────────────────────────────────────────────────────────────────────────
# Console table
# ─────────────────────────────────────────────────────────────────────────────

def _print_header() -> None:
    print(
        f"  {'Iter':>5}  {'Reward±σ':>13}  {'SR':>6}  "
        f"{'P.Loss':>7}  {'V.Loss':>7}  {'KL':>8}  {'ClipFr':>7}"
    )
    print(f"  {'─'*5}  {'─'*13}  {'─'*6}  {'─'*7}  {'─'*7}  {'─'*8}  {'─'*7}")


def _print_row(m: IterationMetrics) -> None:
    if m.iteration % 10 == 0 or m.success_rate >= 0.75 or m.early_stop:
        reward_str = f"{m.episode_reward_mean:+.2f}±{m.episode_reward_std:.2f}"
        print(
            f"  {m.iteration:5d}  {reward_str:>13}  {m.success_rate:5.1%}  "
            f"{m.policy_loss:7.4f}  {m.value_loss:7.4f}  "
            f"{m.kl_divergence:8.5f}  {m.clip_fraction:7.3f}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# SVG chart builders — pure stdlib
# ─────────────────────────────────────────────────────────────────────────────

def _svg_chart(
    *,
    width: int = 760,
    height: int = 260,
    primary_series: List[dict],
    secondary_series: Optional[List[dict]] = None,
    x_label: str = "Iteration",
    y_label: str = "",
    y2_label: str = "",
    convergence_x: Optional[int] = None,
    pad: tuple[int, int, int, int] = (24, 60, 48, 64),   # top, left, bottom, right
) -> str:
    """
    Build a self-contained SVG line chart.

    primary_series  items: {"label", "color", "xs": List, "ys": List,
                             optionally "fill_hi": List, "fill_lo": List}
    secondary_series items: same schema, plotted on an independent y-axis (right side)
    """
    pad_top, pad_left, pad_bottom, pad_right = pad
    inner_w = width  - pad_left - pad_right
    inner_h = height - pad_top  - pad_bottom

    all_xs = [x for s in primary_series for x in s["xs"]]
    all_ys = [y for s in primary_series for y in s["ys"]]
    if not all_xs:
        return "<svg></svg>"

    x_min, x_max = min(all_xs), max(all_xs)
    y_range_raw   = max(all_ys) - min(all_ys) or 1.0
    y_min = min(all_ys) - 0.08 * y_range_raw
    y_max = max(all_ys) + 0.08 * y_range_raw
    y_span = y_max - y_min or 1.0

    def px(x: float) -> float:
        return pad_left + (x - x_min) / (x_max - x_min + 1e-9) * inner_w

    def py(y: float, lo: float = y_min, span: float = y_span) -> float:
        return pad_top + (1.0 - (y - lo) / span) * inner_h

    # Secondary axis range
    py2 = None
    if secondary_series:
        all_y2 = [y for s in secondary_series for y in s["ys"]]
        y2_span_raw = max(all_y2) - min(all_y2) or 1.0
        y2_min = min(all_y2) - 0.08 * y2_span_raw
        y2_max = max(all_y2) + 0.08 * y2_span_raw
        y2_span = y2_max - y2_min or 1.0

        def py2(y: float) -> float:  # type: ignore[misc]
            return pad_top + (1.0 - (y - y2_min) / y2_span) * inner_h

    elems: List[str] = []

    # ── Grid ─────────────────────────────────────────────────────────────────
    n_grid = 5
    for i in range(n_grid + 1):
        yv = y_min + i * y_span / n_grid
        yp = py(yv)
        elems.append(
            f'<line x1="{pad_left}" y1="{yp:.1f}" '
            f'x2="{pad_left + inner_w}" y2="{yp:.1f}" '
            f'stroke="#334155" stroke-dasharray="3,3" stroke-width="0.8"/>'
        )
        elems.append(
            f'<text x="{pad_left - 5}" y="{yp + 4:.1f}" '
            f'font-size="9" fill="#64748b" text-anchor="end">{yv:.3g}</text>'
        )

    # ── X-axis ticks ─────────────────────────────────────────────────────────
    x_span = x_max - x_min
    n_xticks = min(10, max(2, int(x_span / 20)))
    tick_step = max(1, round(x_span / n_xticks / 10) * 10)
    xt = (int(x_min / tick_step) + 1) * tick_step
    while xt <= x_max:
        xp = px(xt)
        elems.append(
            f'<line x1="{xp:.1f}" y1="{pad_top + inner_h}" '
            f'x2="{xp:.1f}" y2="{pad_top + inner_h + 4}" stroke="#475569"/>'
        )
        elems.append(
            f'<text x="{xp:.1f}" y="{pad_top + inner_h + 16}" '
            f'font-size="9" fill="#64748b" text-anchor="middle">{int(xt)}</text>'
        )
        xt += tick_step

    # ── Convergence marker ───────────────────────────────────────────────────
    if convergence_x is not None:
        xp = px(convergence_x)
        elems.append(
            f'<line x1="{xp:.1f}" y1="{pad_top}" '
            f'x2="{xp:.1f}" y2="{pad_top + inner_h}" '
            f'stroke="#f59e0b" stroke-dasharray="6,3" stroke-width="1.5"/>'
        )
        elems.append(
            f'<text x="{xp + 4:.1f}" y="{pad_top + 13}" '
            f'font-size="9" fill="#f59e0b">converged</text>'
        )

    # ── Fill bands ───────────────────────────────────────────────────────────
    for s in primary_series:
        if "fill_hi" in s and "fill_lo" in s:
            fwd = " ".join(
                f"{px(x):.1f},{py(y):.1f}"
                for x, y in zip(s["xs"], s["fill_hi"])
            )
            rev = " ".join(
                f"{px(x):.1f},{py(y):.1f}"
                for x, y in zip(reversed(s["xs"]), reversed(s["fill_lo"]))
            )
            elems.append(
                f'<polygon points="{fwd} {rev}" fill="{s["color"]}" opacity="0.12"/>'
            )

    # ── Primary lines ─────────────────────────────────────────────────────────
    for s in primary_series:
        pts = " ".join(f"{px(x):.1f},{py(y):.1f}" for x, y in zip(s["xs"], s["ys"]))
        elems.append(
            f'<polyline points="{pts}" fill="none" '
            f'stroke="{s["color"]}" stroke-width="2" stroke-linejoin="round"/>'
        )

    # ── Secondary lines (right axis) ─────────────────────────────────────────
    if secondary_series and py2 is not None:
        for s in secondary_series:
            pts = " ".join(f"{px(x):.1f},{py2(y):.1f}" for x, y in zip(s["xs"], s["ys"]))
            elems.append(
                f'<polyline points="{pts}" fill="none" '
                f'stroke="{s["color"]}" stroke-width="2" stroke-dasharray="5,3" '
                f'stroke-linejoin="round"/>'
            )
        # Right y-axis tick labels
        for i in range(n_grid + 1):
            yv = y2_min + i * y2_span / n_grid   # type: ignore[possibly-undefined]
            yp = py2(yv)
            elems.append(
                f'<text x="{pad_left + inner_w + 5}" y="{yp + 4:.1f}" '
                f'font-size="9" fill="#64748b">{yv:.3g}</text>'
            )
        if y2_label:
            mx = pad_left + inner_w + pad_right - 6
            my = pad_top + inner_h / 2
            elems.append(
                f'<text transform="rotate(90,{mx:.1f},{my:.1f})" '
                f'x="{mx:.1f}" y="{my:.1f}" '
                f'font-size="10" fill="#475569" text-anchor="middle">{y2_label}</text>'
            )

    # ── Axes ─────────────────────────────────────────────────────────────────
    elems.append(
        f'<line x1="{pad_left}" y1="{pad_top}" '
        f'x2="{pad_left}" y2="{pad_top + inner_h}" stroke="#475569" stroke-width="1"/>'
    )
    elems.append(
        f'<line x1="{pad_left}" y1="{pad_top + inner_h}" '
        f'x2="{pad_left + inner_w}" y2="{pad_top + inner_h}" stroke="#475569" stroke-width="1"/>'
    )

    # Axis labels
    elems.append(
        f'<text x="{pad_left + inner_w / 2:.1f}" y="{height - 4}" '
        f'font-size="10" fill="#475569" text-anchor="middle">{x_label}</text>'
    )
    if y_label:
        cx = 12
        cy = pad_top + inner_h / 2
        elems.append(
            f'<text transform="rotate(-90,{cx},{cy:.1f})" '
            f'x="{cx}" y="{cy:.1f}" '
            f'font-size="10" fill="#475569" text-anchor="middle">{y_label}</text>'
        )

    # ── Legend ───────────────────────────────────────────────────────────────
    all_legend = list(primary_series) + (secondary_series or [])
    lx, ly = pad_left + 8, pad_top + 14
    for i, s in enumerate(all_legend):
        ox = lx + i * 150
        is_sec = i >= len(primary_series)
        dash = ' stroke-dasharray="5,3"' if is_sec else ""
        elems.append(
            f'<line x1="{ox}" y1="{ly - 4}" x2="{ox + 20}" y2="{ly - 4}" '
            f'stroke="{s["color"]}" stroke-width="2"{dash}/>'
        )
        elems.append(
            f'<text x="{ox + 24}" y="{ly}" '
            f'font-size="10" fill="#cbd5e1">{s["label"]}</text>'
        )

    inner_svg = "\n  ".join(elems)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{width}" height="{height}" '
        f'style="background:#0f172a;border-radius:8px;display:block;">'
        f'\n  {inner_svg}\n</svg>'
    )


# ─────────────────────────────────────────────────────────────────────────────
# HTML report
# ─────────────────────────────────────────────────────────────────────────────

def render_html(result: TrainingResult, output_path: str) -> None:
    """Render a dark-theme HTML report with SVG charts and metrics table."""
    metrics = result.metrics
    cfg     = result.config
    n       = len(metrics)

    xs              = [m.iteration         for m in metrics]
    reward_means    = [m.episode_reward_mean for m in metrics]
    reward_hi       = [m.episode_reward_mean + m.episode_reward_std for m in metrics]
    reward_lo       = [m.episode_reward_mean - m.episode_reward_std for m in metrics]
    success_rates   = [m.success_rate * 100  for m in metrics]
    policy_losses   = [m.policy_loss          for m in metrics]
    value_losses    = [m.value_loss           for m in metrics]

    # Convergence marker x
    conv_x: Optional[int] = result.early_stop_iteration
    if conv_x is None:
        conv_x = next((m.iteration for m in metrics if m.success_rate >= 0.50), None)

    # ── Chart 1: Episode reward ───────────────────────────────────────────────
    chart_reward = _svg_chart(
        width=760, height=260,
        primary_series=[{
            "label": "Episode Reward (mean)",
            "color": "#38bdf8",
            "xs": xs,
            "ys": reward_means,
            "fill_hi": reward_hi,
            "fill_lo": reward_lo,
        }],
        x_label="Iteration",
        y_label="Reward",
    )

    # ── Chart 2: Success rate ─────────────────────────────────────────────────
    chart_sr = _svg_chart(
        width=760, height=260,
        primary_series=[{
            "label": "Success Rate (%)",
            "color": "#4ade80",
            "xs": xs,
            "ys": success_rates,
        }],
        x_label="Iteration",
        y_label="SR (%)",
        convergence_x=conv_x,
    )

    # ── Chart 3: PPO losses — dual axis ──────────────────────────────────────
    chart_losses = _svg_chart(
        width=760, height=260,
        primary_series=[{
            "label": "Policy Loss",
            "color": "#C74634",
            "xs": xs,
            "ys": policy_losses,
        }],
        secondary_series=[{
            "label": "Value Loss",
            "color": "#fb923c",
            "xs": xs,
            "ys": value_losses,
        }],
        x_label="Iteration",
        y_label="Policy Loss",
        y2_label="Value Loss",
    )

    # ── Summary values ────────────────────────────────────────────────────────
    minutes   = result.total_elapsed_seconds / 60.0
    steps_m   = result.total_env_steps / 1_000_000
    sr_color  = "#4ade80" if result.final_success_rate >= 0.8 else (
                "#facc15" if result.final_success_rate >= 0.5 else "#f87171")
    conv_badge = (
        '<span style="color:#4ade80;font-weight:600">CONVERGED</span>'
        if result.early_stopped else
        '<span style="color:#f59e0b">MAX_ITERS</span>'
    )

    # ── Last-20 table rows ────────────────────────────────────────────────────
    table_rows = ""
    for m in metrics[-20:]:
        c = ("#4ade80" if m.success_rate >= 0.8 else
             "#facc15" if m.success_rate >= 0.5 else "#f87171")
        kl_c = "#f87171" if m.kl_divergence > 0.015 else "#94a3b8"
        table_rows += (
            f"<tr>"
            f"<td>{m.iteration}</td>"
            f"<td>{m.episode_reward_mean:+.2f} ± {m.episode_reward_std:.2f}</td>"
            f'<td style="color:{c};font-weight:600">{m.success_rate:.1%}</td>'
            f"<td>{m.policy_loss:.5f}</td>"
            f"<td>{m.value_loss:.5f}</td>"
            f"<td>{m.entropy:.4f}</td>"
            f'<td style="color:{kl_c}">{m.kl_divergence:.5f}</td>'
            f"<td>{m.clip_fraction*100:.1f}%</td>"
            f"<td>{m.explained_variance:.3f}</td>"
            f"<td>{m.learning_rate:.2e}</td>"
            f"<td>{m.grad_norm:.3f}</td>"
            f"</tr>\n"
        )

    early_note = (
        f'<p style="color:#f59e0b;margin:4px 0 0;font-size:0.85rem;">'
        f'Early stopping at iteration {result.early_stop_iteration}: '
        f'SR ≥ {cfg.early_stop_threshold:.0%} for '
        f'{cfg.early_stop_patience} consecutive iterations.</p>'
    ) if result.early_stopped else ""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>OCI Robot Cloud — PPO Policy Gradient Trainer</title>
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, ui-monospace, monospace;
    background: #1e293b;
    color: #e2e8f0;
    padding: 32px 40px;
    line-height: 1.55;
  }}
  h1 {{ color: #C74634; font-size: 1.55rem; margin-bottom: 4px; }}
  h2 {{ color: #C74634; font-size: 1.1rem; margin: 28px 0 10px;
        border-bottom: 1px solid #334155; padding-bottom: 6px; }}
  .subtitle {{ color: #94a3b8; font-size: 0.83rem; margin-bottom: 24px; }}
  .cards {{
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 14px;
    margin-bottom: 24px;
  }}
  .card {{
    background: #0f172a;
    border: 1px solid #334155;
    border-radius: 10px;
    padding: 16px 18px;
  }}
  .card .label {{
    font-size: 0.72rem;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }}
  .card .value {{ font-size: 1.65rem; font-weight: 700; color: #f1f5f9; margin-top: 4px; }}
  .card .sub   {{ font-size: 0.76rem; color: #64748b; margin-top: 2px; }}
  .chart-box {{
    background: #0f172a;
    border: 1px solid #334155;
    border-radius: 10px;
    padding: 14px 16px;
    margin-bottom: 18px;
    overflow-x: auto;
  }}
  .chart-caption {{
    font-size: 0.78rem;
    color: #64748b;
    margin-bottom: 8px;
  }}
  table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 0.78rem;
  }}
  th {{
    background: #0f172a;
    color: #C74634;
    padding: 7px 10px;
    text-align: right;
    font-weight: 600;
    border-bottom: 1px solid #334155;
    white-space: nowrap;
  }}
  th:first-child {{ text-align: center; }}
  td {{
    padding: 5px 10px;
    text-align: right;
    border-bottom: 1px solid #1e293b;
    color: #cbd5e1;
  }}
  td:first-child {{ text-align: center; color: #94a3b8; }}
  tr:hover td {{ background: #1e293b; }}
  .cfg-grid {{
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 6px 20px;
    font-size: 0.8rem;
    background: #0f172a;
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 14px 18px;
  }}
  .cfg-item {{ color: #64748b; }}
  .cfg-item span {{ color: #e2e8f0; font-weight: 500; }}
  footer {{
    margin-top: 36px;
    font-size: 0.73rem;
    color: #475569;
    text-align: center;
  }}
</style>
</head>
<body>

<h1>OCI Robot Cloud — PPO Policy Gradient Trainer</h1>
<p class="subtitle">
  Checkpoint: <strong style="color:#e2e8f0">{result.checkpoint}</strong> ·
  GR00T N1.6 · Franka pick-and-lift ·
  {cfg.num_envs} envs × {cfg.rollout_steps} rollout steps ·
  seed {cfg.seed} · {conv_badge}
</p>

<h2>Summary</h2>
<div class="cards">
  <div class="card">
    <div class="label">Iterations Run</div>
    <div class="value">{n}</div>
    <div class="sub">of {cfg.n_iters} max</div>
  </div>
  <div class="card">
    <div class="label">Final Success Rate</div>
    <div class="value" style="color:{sr_color}">{result.final_success_rate:.1%}</div>
    <div class="sub">last iteration</div>
  </div>
  <div class="card">
    <div class="label">Best Success Rate</div>
    <div class="value">{result.best_success_rate:.1%}</div>
    <div class="sub">@ iteration {result.best_iteration}</div>
  </div>
  <div class="card">
    <div class="label">Env Steps</div>
    <div class="value">{steps_m:.2f}M</div>
    <div class="sub">sim wall time ~{minutes:.1f} min</div>
  </div>
</div>
{early_note}

<h2>Episode Reward over Training</h2>
<div class="chart-box">
  <div class="chart-caption">Mean episode reward per PPO iteration with ±1σ band (shaded)</div>
  {chart_reward}
</div>

<h2>Success Rate over Training</h2>
<div class="chart-box">
  <div class="chart-caption">
    Task success rate (%) — BC baseline ≈5% → converges toward ~78% by iter 150
    {" · amber line = convergence / 50% milestone marker" if conv_x is not None else ""}
  </div>
  {chart_sr}
</div>

<h2>PPO Losses</h2>
<div class="chart-box">
  <div class="chart-caption">
    Policy loss (solid, left axis, Oracle red) · Value loss (dashed, right axis, orange)
  </div>
  {chart_losses}
</div>

<h2>Last 20 Iterations Detail</h2>
<div style="overflow-x:auto;">
<table>
  <thead>
    <tr>
      <th>Iter</th><th>Reward ± σ</th><th>SR</th>
      <th>Policy Loss</th><th>Value Loss</th><th>Entropy</th>
      <th>KL Div</th><th>Clip %</th><th>Expl Var</th>
      <th>LR</th><th>Grad Norm</th>
    </tr>
  </thead>
  <tbody>
    {table_rows}
  </tbody>
</table>
</div>

<h2>Training Configuration</h2>
<div class="cfg-grid">
  <div class="cfg-item">rollout_steps <span>{cfg.rollout_steps}</span></div>
  <div class="cfg-item">num_envs <span>{cfg.num_envs}</span></div>
  <div class="cfg-item">ppo_epochs <span>{cfg.ppo_epochs}</span></div>
  <div class="cfg-item">minibatch_size <span>{cfg.minibatch_size}</span></div>
  <div class="cfg-item">clip_eps <span>{cfg.clip_eps}</span></div>
  <div class="cfg-item">entropy_coef <span>{cfg.entropy_coef}</span></div>
  <div class="cfg-item">value_coef <span>{cfg.value_coef}</span></div>
  <div class="cfg-item">gamma <span>{cfg.gamma}</span></div>
  <div class="cfg-item">gae_lambda <span>{cfg.gae_lambda}</span></div>
  <div class="cfg-item">lr_init <span>{cfg.lr_init:.0e}</span></div>
  <div class="cfg-item">lr_min <span>{cfg.lr_min:.0e}</span></div>
  <div class="cfg-item">warmup_steps <span>{cfg.warmup_steps}</span></div>
  <div class="cfg-item">early_stop_thresh <span>{cfg.early_stop_threshold:.0%}</span></div>
  <div class="cfg-item">early_stop_patience <span>{cfg.early_stop_patience}</span></div>
  <div class="cfg-item">reward_task_complete <span>{cfg.reward_task_complete}</span></div>
  <div class="cfg-item">reward_step_penalty <span>{cfg.reward_step_penalty}</span></div>
</div>

<footer>
  OCI Robot Cloud · PPO Policy Gradient Trainer ·
  GR00T N1.6 fine-tuning simulation ·
  Generated {time.strftime("%Y-%m-%d %H:%M:%S")}
</footer>

</body>
</html>
"""

    with open(output_path, "w", encoding="utf-8") as fh:
        fh.write(html)
    print(f"  HTML report → {output_path}")


# ─────────────────────────────────────────────────────────────────────────────
# JSON output
# ─────────────────────────────────────────────────────────────────────────────

def write_json(result: TrainingResult, json_path: str) -> None:
    """Serialize the full training result to JSON."""
    data = {
        "config": {
            "rollout_steps":        result.config.rollout_steps,
            "num_envs":             result.config.num_envs,
            "ppo_epochs":           result.config.ppo_epochs,
            "minibatch_size":       result.config.minibatch_size,
            "clip_eps":             result.config.clip_eps,
            "entropy_coef":         result.config.entropy_coef,
            "value_coef":           result.config.value_coef,
            "gamma":                result.config.gamma,
            "gae_lambda":           result.config.gae_lambda,
            "lr_init":              result.config.lr_init,
            "lr_min":               result.config.lr_min,
            "warmup_steps":         result.config.warmup_steps,
            "n_iters":              result.config.n_iters,
            "seed":                 result.config.seed,
            "early_stop_threshold": result.config.early_stop_threshold,
            "early_stop_patience":  result.config.early_stop_patience,
        },
        "summary": {
            "checkpoint":             result.checkpoint,
            "total_iterations":       len(result.metrics),
            "final_success_rate":     result.final_success_rate,
            "best_success_rate":      result.best_success_rate,
            "best_iteration":         result.best_iteration,
            "early_stopped":          result.early_stopped,
            "early_stop_iteration":   result.early_stop_iteration,
            "total_env_steps":        result.total_env_steps,
            "total_elapsed_seconds":  result.total_elapsed_seconds,
        },
        "final_metrics": (
            {
                "policy_loss":         result.metrics[-1].policy_loss,
                "value_loss":          result.metrics[-1].value_loss,
                "entropy":             result.metrics[-1].entropy,
                "kl_divergence":       result.metrics[-1].kl_divergence,
                "clip_fraction":       result.metrics[-1].clip_fraction,
                "explained_variance":  result.metrics[-1].explained_variance,
                "episode_reward_mean": result.metrics[-1].episode_reward_mean,
                "episode_reward_std":  result.metrics[-1].episode_reward_std,
                "episode_length_mean": result.metrics[-1].episode_length_mean,
                "grad_norm":           result.metrics[-1].grad_norm,
                "learning_rate":       result.metrics[-1].learning_rate,
                "fps":                 result.metrics[-1].fps,
            }
            if result.metrics else {}
        ),
        "per_iteration": [
            {
                "iteration":           m.iteration,
                "success_rate":        m.success_rate,
                "episode_reward_mean": m.episode_reward_mean,
                "episode_reward_std":  m.episode_reward_std,
                "episode_length_mean": m.episode_length_mean,
                "policy_loss":         m.policy_loss,
                "value_loss":          m.value_loss,
                "entropy":             m.entropy,
                "kl_divergence":       m.kl_divergence,
                "clip_fraction":       m.clip_fraction,
                "explained_variance":  m.explained_variance,
                "grad_norm":           m.grad_norm,
                "learning_rate":       m.learning_rate,
                "fps":                 m.fps,
                "total_env_steps":     m.total_env_steps,
            }
            for m in result.metrics
        ],
    }
    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
    print(f"  JSON metrics → {json_path}")


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="PPO policy gradient fine-tuning simulation for GR00T.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument(
        "--mock", action="store_true", default=True,
        help="Simulation mode (no GPU/robot required). Currently only mock is supported.",
    )
    p.add_argument(
        "--checkpoint", default="dagger_run9/checkpoint_5000",
        help="Path or identifier of the GR00T starting checkpoint.",
    )
    p.add_argument(
        "--n-iters", type=int, default=200,
        metavar="INT",
        help="Maximum number of PPO iterations.",
    )
    p.add_argument(
        "--output", default="/tmp/policy_gradient_trainer.html",
        metavar="PATH",
        help="Destination for the HTML report.",
    )
    p.add_argument(
        "--seed", type=int, default=42,
        metavar="INT",
        help="Random seed for reproducibility.",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()

    if not args.mock:
        print(
            "[WARNING] Real robot/GPU mode requires PyTorch + Genesis. "
            "Falling back to --mock simulation."
        )

    config = PPOConfig(n_iters=args.n_iters, seed=args.seed)
    result = run_ppo_training(config, checkpoint=args.checkpoint)

    render_html(result, args.output)

    base_path = Path(args.output)
    json_path = str(base_path.with_suffix(".json"))
    write_json(result, json_path)

    print(f"\n  Done. Open report: open {args.output}\n")


if __name__ == "__main__":
    main()
