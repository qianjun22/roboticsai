#!/usr/bin/env python3
"""
task_curriculum_generator.py

Generates and evaluates automatic curriculum learning schedules for GR00T robot training.
Determines the optimal ordering and difficulty progression of tasks to maximize learning efficiency.

Usage:
    python task_curriculum_generator.py [--mock] [--n-episodes 500] \
        [--output /tmp/task_curriculum_generator.html] [--seed 42] \
        [--json-output /tmp/task_curriculum_results.json]

Stdlib only. Self-contained.
"""

import argparse
import json
import math
import os
import random
import sys
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Task definitions
# ---------------------------------------------------------------------------

TASKS: List[Dict] = [
    {"name": "reach_target",  "difficulty": 2},
    {"name": "push_block",    "difficulty": 3},
    {"name": "pick_cube",     "difficulty": 4},
    {"name": "open_drawer",   "difficulty": 5},
    {"name": "stack_2cubes",  "difficulty": 6},
    {"name": "pour_liquid",   "difficulty": 7},
    {"name": "insert_peg",    "difficulty": 8},
    {"name": "assemble_gear", "difficulty": 9},
]

TASK_NAMES = [t["name"] for t in TASKS]
TASK_DIFFICULTY = {t["name"]: t["difficulty"] for t in TASKS}
N_TASKS = len(TASKS)

# ---------------------------------------------------------------------------
# Transfer learning matrix
# Completing task i gives a small SR boost to harder tasks.
# transfer_matrix[i][j] = bonus fraction added to task_j base_sr when task_i SR is high.
# ---------------------------------------------------------------------------

def build_transfer_matrix() -> List[List[float]]:
    """Build an N×N transfer matrix where easier→harder transfers are positive."""
    n = N_TASKS
    matrix = [[0.0] * n for _ in range(n)]
    for i, src in enumerate(TASKS):
        for j, dst in enumerate(TASKS):
            if i == j:
                matrix[i][j] = 0.0
            elif src["difficulty"] < dst["difficulty"]:
                diff_gap = dst["difficulty"] - src["difficulty"]
                # Closer tasks transfer more; max bonus ~0.12 for adjacent tasks
                matrix[i][j] = max(0.0, 0.14 - 0.02 * diff_gap)
            else:
                matrix[i][j] = 0.0
    return matrix


TRANSFER_MATRIX = build_transfer_matrix()

# ---------------------------------------------------------------------------
# Simulation core
# ---------------------------------------------------------------------------

def task_base_sr(difficulty: int) -> float:
    """Base success rate ceiling for a task given its difficulty."""
    # Harder tasks have lower asymptotic SR without transfer
    return max(0.30, 1.0 - 0.07 * (difficulty - 1))


def learning_rate_for_difficulty(difficulty: int) -> float:
    """Logistic growth rate — harder tasks learn more slowly."""
    return max(0.04, 0.18 - 0.015 * (difficulty - 1))


def sigmoid(x: float) -> float:
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    exp_x = math.exp(x)
    return exp_x / (1.0 + exp_x)


class TaskState:
    """Tracks per-task learning state for one simulation run."""

    def __init__(self, task_idx: int, rng: random.Random):
        self.idx = task_idx
        self.name = TASKS[task_idx]["name"]
        self.difficulty = TASKS[task_idx]["difficulty"]
        self.rng = rng

        self.steps_trained = 0           # episodes spent on this task
        self.sr = 0.0                    # current estimated success rate
        self.transfer_bonus = 0.0        # accumulated from other tasks
        self._base_ceiling = task_base_sr(self.difficulty)
        self._lr = learning_rate_for_difficulty(self.difficulty)
        self.sr_history: List[float] = []   # SR after each episode (global)

    def effective_ceiling(self) -> float:
        return min(0.98, self._base_ceiling + self.transfer_bonus)

    def train_one_episode(self) -> bool:
        """Simulate one training episode. Returns whether episode succeeded."""
        self.steps_trained += 1
        ceiling = self.effective_ceiling()
        # Logistic growth in steps trained
        logit = self._lr * self.steps_trained - 3.0
        learned_sr = ceiling * sigmoid(logit)
        # Add small noise
        noise = self.rng.gauss(0, 0.02)
        self.sr = max(0.0, min(1.0, learned_sr + noise))
        return self.rng.random() < self.sr

    def apply_transfer(self, src_idx: int, src_sr: float) -> None:
        """Apply transfer bonus from another task reaching high SR."""
        bonus = TRANSFER_MATRIX[src_idx][self.idx] * src_sr
        self.transfer_bonus = min(0.25, self.transfer_bonus + bonus * 0.05)

    def forgetting_step(self) -> None:
        """Slight SR decay when not being trained (catastrophic forgetting)."""
        decay_rate = 0.001 * self.difficulty  # harder tasks forget faster
        self.sr = max(0.0, self.sr - decay_rate)


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

def simulate_fixed_order(
    n_episodes: int, rng: random.Random
) -> Tuple[List[float], Dict[str, List[float]], List[float]]:
    """
    Tasks trained in fixed order easiest→hardest.
    Each task gets n_episodes/N_TASKS episodes before moving on.
    Returns (avg_sr_over_time, per_task_sr_history, forgetting_rates).
    """
    states = [TaskState(i, rng) for i in range(N_TASKS)]
    episodes_per_task = n_episodes // N_TASKS

    avg_sr_history: List[float] = []
    per_task_sr: Dict[str, List[float]] = {t.name: [] for t in states}
    forgetting_rates: List[float] = []

    current_task_idx = 0
    task_episode_count = [0] * N_TASKS
    prev_sr_at_transition: Dict[int, float] = {}

    for ep in range(n_episodes):
        # Determine which task to train this episode
        # Each task gets a contiguous block
        block = ep // episodes_per_task
        train_idx = min(block, N_TASKS - 1)

        # Detect task transition — record forgetting
        if train_idx != current_task_idx:
            prev_sr_at_transition[current_task_idx] = states[current_task_idx].sr
            current_task_idx = train_idx

        # Train selected task
        states[train_idx].train_one_episode()

        # Apply transfer from trained task to all others
        for j, s in enumerate(states):
            if j != train_idx:
                s.apply_transfer(train_idx, states[train_idx].sr)
                if j < train_idx:
                    s.forgetting_step()

        # Compute avg SR
        avg = sum(s.sr for s in states) / N_TASKS
        avg_sr_history.append(avg)

        for s in states:
            per_task_sr[s.name].append(s.sr)

    # Forgetting rate: average relative drop for all tasks that were completed before the last task
    for i, s in enumerate(states[:-1]):
        if i in prev_sr_at_transition:
            rate = max(0.0, prev_sr_at_transition[i] - s.sr)
            forgetting_rates.append(rate)

    return avg_sr_history, per_task_sr, forgetting_rates


def simulate_adaptive(
    n_episodes: int, rng: random.Random, advance_threshold: float = 0.70
) -> Tuple[List[float], Dict[str, List[float]], List[float]]:
    """
    Adaptive curriculum: advance to next task when SR > advance_threshold.
    If all tasks mastered, cycle back to lowest-SR task.
    Returns (avg_sr_over_time, per_task_sr_history, forgetting_rates).
    """
    states = [TaskState(i, rng) for i in range(N_TASKS)]
    avg_sr_history: List[float] = []
    per_task_sr: Dict[str, List[float]] = {t.name: [] for t in states}
    forgetting_rates: List[float] = []

    current_task_idx = 0
    prev_sr_at_transition: Dict[int, float] = {}
    last_train_idx = 0

    for ep in range(n_episodes):
        train_idx = current_task_idx

        # Train selected task
        states[train_idx].train_one_episode()

        # Apply transfer
        for j, s in enumerate(states):
            if j != train_idx:
                s.apply_transfer(train_idx, states[train_idx].sr)
                if j < train_idx:
                    s.forgetting_step()

        # Check if should advance
        if states[train_idx].sr >= advance_threshold:
            next_idx = train_idx + 1
            # Find next unmastered task
            while next_idx < N_TASKS and states[next_idx].sr >= advance_threshold:
                next_idx += 1
            if next_idx >= N_TASKS:
                # All tasks above threshold — focus on lowest SR
                next_idx = min(range(N_TASKS), key=lambda i: states[i].sr)
            if next_idx != train_idx:
                prev_sr_at_transition[train_idx] = states[train_idx].sr
                current_task_idx = next_idx

        avg = sum(s.sr for s in states) / N_TASKS
        avg_sr_history.append(avg)
        for s in states:
            per_task_sr[s.name].append(s.sr)

    for i, s in enumerate(states[:-1]):
        if i in prev_sr_at_transition:
            rate = max(0.0, prev_sr_at_transition[i] - s.sr)
            forgetting_rates.append(rate)

    return avg_sr_history, per_task_sr, forgetting_rates


def simulate_interleaved(
    n_episodes: int, rng: random.Random
) -> Tuple[List[float], Dict[str, List[float]], List[float]]:
    """
    Interleaved: sample tasks with weights inversely proportional to current SR.
    Tasks with lower SR get more training time.
    Returns (avg_sr_over_time, per_task_sr_history, forgetting_rates).
    """
    states = [TaskState(i, rng) for i in range(N_TASKS)]
    avg_sr_history: List[float] = []
    per_task_sr: Dict[str, List[float]] = {t.name: [] for t in states}
    prev_counts = [0] * N_TASKS
    sr_snapshots: Dict[int, List[float]] = {i: [] for i in range(N_TASKS)}

    for ep in range(n_episodes):
        # Weights = 1 - SR (tasks with low SR get higher weight)
        weights = [max(0.05, 1.0 - s.sr) for s in states]
        total = sum(weights)
        probs = [w / total for w in weights]

        # Sample task
        r = rng.random()
        cumulative = 0.0
        train_idx = N_TASKS - 1
        for i, p in enumerate(probs):
            cumulative += p
            if r <= cumulative:
                train_idx = i
                break

        states[train_idx].train_one_episode()

        # Transfer and mild forgetting for untrained tasks
        for j, s in enumerate(states):
            if j != train_idx:
                s.apply_transfer(train_idx, states[train_idx].sr)
                s.forgetting_step()

        avg = sum(s.sr for s in states) / N_TASKS
        avg_sr_history.append(avg)
        for s in states:
            per_task_sr[s.name].append(s.sr)

    # Forgetting rate: std dev of SR oscillation for each task
    forgetting_rates: List[float] = []
    for i, s in enumerate(states):
        history = per_task_sr[s.name]
        # Measure max-drop as forgetting proxy
        if len(history) > 50:
            peaks = [history[k] for k in range(1, len(history) - 1)
                     if history[k] >= history[k-1] and history[k] >= history[k+1]]
            if peaks:
                troughs = [history[k] for k in range(1, len(history) - 1)
                           if history[k] <= history[k-1] and history[k] <= history[k+1]]
                if troughs and peaks:
                    forgetting_rates.append(max(peaks) - min(troughs))

    return avg_sr_history, per_task_sr, forgetting_rates


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def steps_to_avg_sr(avg_sr_history: List[float], target: float = 0.50) -> Optional[int]:
    """Return episode index when avg SR first crosses target, or None."""
    for i, sr in enumerate(avg_sr_history):
        if sr >= target:
            return i + 1
    return None


def final_per_task_sr(per_task_sr: Dict[str, List[float]]) -> Dict[str, float]:
    return {name: history[-1] if history else 0.0
            for name, history in per_task_sr.items()}


def avg_forgetting_rate(forgetting_rates: List[float]) -> float:
    if not forgetting_rates:
        return 0.0
    return sum(forgetting_rates) / len(forgetting_rates)


# ---------------------------------------------------------------------------
# Main simulation runner
# ---------------------------------------------------------------------------

def run_simulation(n_episodes: int, seed: int) -> Dict:
    rng_fixed = random.Random(seed)
    rng_adaptive = random.Random(seed + 1000)
    rng_interleaved = random.Random(seed + 2000)

    results = {}

    print("Simulating fixed_order strategy...")
    avg_fixed, pt_fixed, forg_fixed = simulate_fixed_order(n_episodes, rng_fixed)
    results["fixed_order"] = {
        "avg_sr_history": avg_fixed,
        "per_task_sr": pt_fixed,
        "final_avg_sr": avg_fixed[-1],
        "steps_to_50pct": steps_to_avg_sr(avg_fixed, 0.50),
        "forgetting_rate": avg_forgetting_rate(forg_fixed),
        "final_per_task": final_per_task_sr(pt_fixed),
    }

    print("Simulating adaptive strategy...")
    avg_adaptive, pt_adaptive, forg_adaptive = simulate_adaptive(n_episodes, rng_adaptive)
    results["adaptive"] = {
        "avg_sr_history": avg_adaptive,
        "per_task_sr": pt_adaptive,
        "final_avg_sr": avg_adaptive[-1],
        "steps_to_50pct": steps_to_avg_sr(avg_adaptive, 0.50),
        "forgetting_rate": avg_forgetting_rate(forg_adaptive),
        "final_per_task": final_per_task_sr(pt_adaptive),
    }

    print("Simulating interleaved strategy...")
    avg_interleaved, pt_interleaved, forg_interleaved = simulate_interleaved(n_episodes, rng_interleaved)
    results["interleaved"] = {
        "avg_sr_history": avg_interleaved,
        "per_task_sr": pt_interleaved,
        "final_avg_sr": avg_interleaved[-1],
        "steps_to_50pct": steps_to_avg_sr(avg_interleaved, 0.50),
        "forgetting_rate": avg_forgetting_rate(forg_interleaved),
        "final_per_task": final_per_task_sr(pt_interleaved),
    }

    return results


# ---------------------------------------------------------------------------
# Console output
# ---------------------------------------------------------------------------

def print_summary_table(results: Dict) -> None:
    strategies = ["fixed_order", "adaptive", "interleaved"]
    col_w = [16, 14, 18, 20]
    header = (
        f"{'Strategy':<{col_w[0]}} {'Final Avg SR':>{col_w[1]}} "
        f"{'Steps to 50% SR':>{col_w[2]}} {'Forgetting Rate':>{col_w[3]}}"
    )
    sep = "-" * sum(col_w + [3 * 2])
    print("\n" + sep)
    print("  CURRICULUM STRATEGY COMPARISON")
    print(sep)
    print(header)
    print(sep)
    for s in strategies:
        r = results[s]
        steps = r["steps_to_50pct"]
        steps_str = f"{steps}" if steps is not None else "N/A"
        print(
            f"{s:<{col_w[0]}} {r['final_avg_sr']:>{col_w[1]}.4f} "
            f"{steps_str:>{col_w[2]}} {r['forgetting_rate']:>{col_w[3]}.4f}"
        )
    print(sep)

    # Determine best
    best_sr = max(strategies, key=lambda s: results[s]["final_avg_sr"])
    best_eff_steps = {s: results[s]["steps_to_50pct"] for s in strategies
                      if results[s]["steps_to_50pct"] is not None}
    best_eff = min(best_eff_steps, key=best_eff_steps.get) if best_eff_steps else "N/A"
    best_forget = min(strategies, key=lambda s: results[s]["forgetting_rate"])

    print(f"\n  Best final SR:        {best_sr} ({results[best_sr]['final_avg_sr']:.4f})")
    if best_eff != "N/A":
        print(f"  Most efficient:       {best_eff} ({best_eff_steps[best_eff]} episodes to 50%)")
    print(f"  Least forgetting:     {best_forget} ({results[best_forget]['forgetting_rate']:.4f})")
    print(sep + "\n")


# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------

def _fmt(v: float, decimals: int = 3) -> str:
    return f"{v:.{decimals}f}"


def svg_line_chart(
    series: Dict[str, List[float]],
    width: int = 860,
    height: int = 300,
    colors: Optional[Dict[str, str]] = None,
    title: str = "",
    x_label: str = "Episode",
    y_label: str = "Avg SR",
    n_episodes: int = 500,
) -> str:
    """Generate an SVG multi-line chart."""
    if colors is None:
        colors = {}

    pad_l, pad_r, pad_t, pad_b = 60, 30, 40, 50
    chart_w = width - pad_l - pad_r
    chart_h = height - pad_t - pad_b

    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">')

    # Background
    lines.append(f'<rect width="{width}" height="{height}" fill="#1e2433" rx="8"/>')

    # Title
    if title:
        lines.append(
            f'<text x="{width//2}" y="22" text-anchor="middle" '
            f'font-family="monospace" font-size="13" fill="#c9d1e0">{title}</text>'
        )

    # Grid lines and Y axis labels
    y_ticks = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
    for yv in y_ticks:
        cy = pad_t + chart_h - int(yv * chart_h)
        lines.append(
            f'<line x1="{pad_l}" y1="{cy}" x2="{pad_l + chart_w}" y2="{cy}" '
            f'stroke="#2e3a50" stroke-width="1" stroke-dasharray="4,4"/>'
        )
        lines.append(
            f'<text x="{pad_l - 8}" y="{cy + 4}" text-anchor="end" '
            f'font-family="monospace" font-size="10" fill="#8090a8">{_fmt(yv, 1)}</text>'
        )

    # X axis labels
    x_ticks = list(range(0, n_episodes + 1, n_episodes // 5))
    for xv in x_ticks:
        cx = pad_l + int(xv / n_episodes * chart_w)
        lines.append(
            f'<text x="{cx}" y="{pad_t + chart_h + 18}" text-anchor="middle" '
            f'font-family="monospace" font-size="10" fill="#8090a8">{xv}</text>'
        )

    # Axes
    lines.append(
        f'<line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t + chart_h}" '
        f'stroke="#4a5568" stroke-width="1.5"/>'
    )
    lines.append(
        f'<line x1="{pad_l}" y1="{pad_t + chart_h}" x2="{pad_l + chart_w}" y2="{pad_t + chart_h}" '
        f'stroke="#4a5568" stroke-width="1.5"/>'
    )

    # Axis labels
    lines.append(
        f'<text x="{pad_l + chart_w // 2}" y="{height - 6}" text-anchor="middle" '
        f'font-family="monospace" font-size="11" fill="#8090a8">{x_label}</text>'
    )
    lines.append(
        f'<text x="14" y="{pad_t + chart_h // 2}" text-anchor="middle" '
        f'font-family="monospace" font-size="11" fill="#8090a8" '
        f'transform="rotate(-90, 14, {pad_t + chart_h // 2})">{y_label}</text>'
    )

    # Downsample for SVG performance
    def downsample(data: List[float], target: int = 200) -> List[Tuple[int, float]]:
        n = len(data)
        if n <= target:
            return list(enumerate(data))
        step = n / target
        return [(int(i * step), data[int(i * step)]) for i in range(target)]

    default_colors = ["#4fc3f7", "#81c784", "#ffb74d", "#f06292"]
    legend_x = pad_l + 10
    legend_y = pad_t + 10

    for ci, (name, data) in enumerate(series.items()):
        color = colors.get(name, default_colors[ci % len(default_colors)])
        pts = downsample(data)
        path_d = " ".join(
            f"{'M' if i == 0 else 'L'}"
            f"{pad_l + int(x / max(len(data) - 1, 1) * chart_w)}"
            f",{pad_t + chart_h - int(max(0.0, min(1.0, y)) * chart_h)}"
            for i, (x, y) in enumerate(pts)
        )
        lines.append(f'<path d="{path_d}" fill="none" stroke="{color}" stroke-width="2.5" stroke-linejoin="round"/>')

        # Legend
        lines.append(
            f'<rect x="{legend_x}" y="{legend_y + ci * 18}" width="14" height="4" fill="{color}" rx="2"/>'
        )
        lines.append(
            f'<text x="{legend_x + 18}" y="{legend_y + ci * 18 + 6}" '
            f'font-family="monospace" font-size="11" fill="#c9d1e0">{name}</text>'
        )

    lines.append("</svg>")
    return "\n".join(lines)


def svg_heatmap(
    data: Dict[str, Dict[str, float]],  # strategy -> task_name -> sr
    strategies: List[str],
    task_names: List[str],
    width: int = 860,
    height: int = 240,
    title: str = "Final Per-Task SR (Strategy × Task)",
) -> str:
    """Generate an SVG heatmap."""
    pad_l, pad_r, pad_t, pad_b = 110, 20, 55, 30
    chart_w = width - pad_l - pad_r
    chart_h = height - pad_t - pad_b

    cell_w = chart_w / len(task_names)
    cell_h = chart_h / len(strategies)

    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">')
    lines.append(f'<rect width="{width}" height="{height}" fill="#1e2433" rx="8"/>')

    if title:
        lines.append(
            f'<text x="{width//2}" y="22" text-anchor="middle" '
            f'font-family="monospace" font-size="13" fill="#c9d1e0">{title}</text>'
        )

    def sr_to_color(sr: float) -> str:
        # Dark blue (low) → teal → green (high)
        r = int(20 + 30 * sr)
        g = int(40 + 160 * sr)
        b = int(80 + 100 * (1 - sr))
        r = min(255, max(0, r))
        g = min(255, max(0, g))
        b = min(255, max(0, b))
        return f"#{r:02x}{g:02x}{b:02x}"

    for ri, strategy in enumerate(strategies):
        for ci, task in enumerate(task_names):
            sr = data[strategy].get(task, 0.0)
            cx = pad_l + ci * cell_w
            cy = pad_t + ri * cell_h
            color = sr_to_color(sr)
            lines.append(
                f'<rect x="{cx:.1f}" y="{cy:.1f}" width="{cell_w:.1f}" height="{cell_h:.1f}" '
                f'fill="{color}" stroke="#1e2433" stroke-width="1.5"/>'
            )
            # SR value text
            text_color = "#ffffff" if sr < 0.65 else "#000000"
            lines.append(
                f'<text x="{cx + cell_w/2:.1f}" y="{cy + cell_h/2 + 4:.1f}" '
                f'text-anchor="middle" font-family="monospace" font-size="10" fill="{text_color}">'
                f'{sr:.2f}</text>'
            )

        # Strategy label (Y axis)
        lines.append(
            f'<text x="{pad_l - 8}" y="{pad_t + ri * cell_h + cell_h/2 + 4:.1f}" '
            f'text-anchor="end" font-family="monospace" font-size="10" fill="#c9d1e0">{strategy}</text>'
        )

    # Task name labels (X axis) — rotated
    for ci, task in enumerate(task_names):
        cx = pad_l + ci * cell_w + cell_w / 2
        cy_text = pad_t - 8
        # Use transform to rotate
        short = task.replace("_", " ")
        lines.append(
            f'<text x="{cx:.1f}" y="{cy_text:.1f}" text-anchor="start" '
            f'font-family="monospace" font-size="9" fill="#8090a8" '
            f'transform="rotate(-40 {cx:.1f} {cy_text:.1f})">{short}</text>'
        )

    lines.append("</svg>")
    return "\n".join(lines)


def svg_transfer_matrix(
    matrix: List[List[float]],
    task_names: List[str],
    width: int = 500,
    height: int = 500,
    title: str = "Transfer Learning Matrix",
) -> str:
    """Generate an SVG visualization of the transfer matrix."""
    n = len(task_names)
    pad_l, pad_r, pad_t, pad_b = 100, 20, 60, 20
    chart_w = width - pad_l - pad_r
    chart_h = height - pad_t - pad_b
    cell_w = chart_w / n
    cell_h = chart_h / n

    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">')
    lines.append(f'<rect width="{width}" height="{height}" fill="#1e2433" rx="8"/>')

    if title:
        lines.append(
            f'<text x="{width//2}" y="22" text-anchor="middle" '
            f'font-family="monospace" font-size="13" fill="#c9d1e0">{title}</text>'
        )

    max_val = max(v for row in matrix for v in row) or 1.0

    for i in range(n):
        for j in range(n):
            val = matrix[i][j]
            intensity = val / max_val if max_val > 0 else 0
            r = int(20 + 200 * intensity)
            g = int(30 + 50 * intensity)
            b = int(60 + 180 * (1 - intensity * 0.7))
            color = f"#{min(255,r):02x}{min(255,g):02x}{min(255,b):02x}"
            cx = pad_l + j * cell_w
            cy = pad_t + i * cell_h
            lines.append(
                f'<rect x="{cx:.1f}" y="{cy:.1f}" width="{cell_w:.1f}" height="{cell_h:.1f}" '
                f'fill="{color}" stroke="#1e2433" stroke-width="1"/>'
            )
            if val > 0:
                text_color = "#ffffff" if intensity < 0.6 else "#111111"
                lines.append(
                    f'<text x="{cx + cell_w/2:.1f}" y="{cy + cell_h/2 + 3:.1f}" '
                    f'text-anchor="middle" font-family="monospace" font-size="8" fill="{text_color}">'
                    f'{val:.3f}</text>'
                )
            else:
                lines.append(
                    f'<text x="{cx + cell_w/2:.1f}" y="{cy + cell_h/2 + 3:.1f}" '
                    f'text-anchor="middle" font-family="monospace" font-size="8" fill="#3a4555">—</text>'
                )

        # Y axis (source task)
        short = task_names[i].replace("_", " ")
        lines.append(
            f'<text x="{pad_l - 6}" y="{pad_t + i * cell_h + cell_h/2 + 4:.1f}" '
            f'text-anchor="end" font-family="monospace" font-size="9" fill="#c9d1e0">{short}</text>'
        )

    # X axis (destination task)
    for j, task in enumerate(task_names):
        cx = pad_l + j * cell_w + cell_w / 2
        cy_text = pad_t - 8
        short = task.replace("_", " ")
        lines.append(
            f'<text x="{cx:.1f}" y="{cy_text:.1f}" text-anchor="start" '
            f'font-family="monospace" font-size="9" fill="#8090a8" '
            f'transform="rotate(-40 {cx:.1f} {cy_text:.1f})">{short}</text>'
        )

    # Axis annotations
    lines.append(
        f'<text x="{pad_l + chart_w/2:.1f}" y="{pad_t + chart_h + 16}" '
        f'text-anchor="middle" font-family="monospace" font-size="10" fill="#8090a8">'
        f'Destination Task (receives transfer)</text>'
    )
    lines.append(
        f'<text x="12" y="{pad_t + chart_h/2:.1f}" text-anchor="middle" '
        f'font-family="monospace" font-size="10" fill="#8090a8" '
        f'transform="rotate(-90, 12, {pad_t + chart_h/2:.1f})">Source Task</text>'
    )

    lines.append("</svg>")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# HTML report
# ---------------------------------------------------------------------------

def generate_html_report(results: Dict, n_episodes: int, seed: int) -> str:
    strategies = ["fixed_order", "adaptive", "interleaved"]
    strategy_colors = {
        "fixed_order": "#4fc3f7",
        "adaptive": "#81c784",
        "interleaved": "#ffb74d",
    }

    # Determine bests
    best_sr_strat = max(strategies, key=lambda s: results[s]["final_avg_sr"])
    best_eff_steps = {s: results[s]["steps_to_50pct"] for s in strategies
                      if results[s]["steps_to_50pct"] is not None}
    best_eff_strat = min(best_eff_steps, key=best_eff_steps.get) if best_eff_steps else "N/A"
    best_forget_strat = min(strategies, key=lambda s: results[s]["forgetting_rate"])

    # --- SVG: avg SR over time ---
    avg_series = {s: results[s]["avg_sr_history"] for s in strategies}
    svg_line = svg_line_chart(
        avg_series,
        width=860, height=300,
        colors=strategy_colors,
        title="Average Success Rate Over Training Episodes",
        x_label="Episode",
        y_label="Avg SR",
        n_episodes=n_episodes,
    )

    # --- SVG: heatmap ---
    heatmap_data = {s: results[s]["final_per_task"] for s in strategies}
    svg_heat = svg_heatmap(
        heatmap_data,
        strategies=strategies,
        task_names=TASK_NAMES,
        width=860, height=200,
        title="Final Per-Task Success Rate (Strategy × Task)",
    )

    # --- SVG: transfer matrix ---
    svg_transfer = svg_transfer_matrix(
        TRANSFER_MATRIX,
        task_names=TASK_NAMES,
        width=500, height=480,
        title="Transfer Learning Bonus Matrix",
    )

    def card(label: str, value: str, subtitle: str, color: str) -> str:
        return f"""
        <div class="summary-card" style="border-top: 3px solid {color};">
          <div class="card-label">{label}</div>
          <div class="card-value" style="color:{color};">{value}</div>
          <div class="card-sub">{subtitle}</div>
        </div>"""

    best_sr_val = results[best_sr_strat]["final_avg_sr"]
    best_eff_val = best_eff_steps.get(best_eff_strat, "—")
    best_forget_val = results[best_forget_strat]["forgetting_rate"]

    cards_html = (
        card("Best Strategy (Final SR)", best_sr_strat.replace("_", " ").title(),
             f"Final avg SR: {best_sr_val:.4f}", strategy_colors[best_sr_strat])
        + card("Best Avg SR", f"{best_sr_val:.4f}",
               f"Achieved by {best_sr_strat.replace('_',' ')}", "#a5d6a7")
        + card("Most Efficient", best_eff_strat.replace("_", " ").title() if best_eff_strat != "N/A" else "N/A",
               f"{best_eff_val} episodes to 50% avg SR", "#ffcc80")
        + card("Least Forgetting", best_forget_strat.replace("_", " ").title(),
               f"Avg forgetting rate: {best_forget_val:.4f}", "#b39ddb")
    )

    # Comparison table rows
    table_rows = ""
    for s in strategies:
        r = results[s]
        steps = r["steps_to_50pct"]
        steps_str = str(steps) if steps is not None else "—"
        color = strategy_colors[s]
        table_rows += f"""
        <tr>
          <td><span class="strategy-dot" style="background:{color};"></span>{s.replace('_', ' ')}</td>
          <td>{r['final_avg_sr']:.4f}</td>
          <td>{steps_str}</td>
          <td>{r['forgetting_rate']:.4f}</td>
          <td>{"★ " if s == best_sr_strat else ""}{r['final_avg_sr']:.4f}</td>
        </tr>"""

    # Per-task SR table
    per_task_rows = ""
    for task in TASK_NAMES:
        diff = TASK_DIFFICULTY[task]
        row = f"<tr><td>{task.replace('_', ' ')}</td><td>{diff}</td>"
        for s in strategies:
            sr = results[s]["final_per_task"].get(task, 0.0)
            bar_w = int(sr * 60)
            color = strategy_colors[s]
            row += (
                f'<td><div class="sr-bar-bg"><div class="sr-bar" style="width:{bar_w}px;background:{color};"></div>'
                f'<span class="sr-val">{sr:.3f}</span></div></td>'
            )
        per_task_rows += row + "</tr>"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<title>GR00T Task Curriculum Generator Report</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: #0f1520;
    color: #c9d1e0;
    font-family: 'Menlo', 'Consolas', monospace;
    padding: 32px;
    line-height: 1.6;
  }}
  h1 {{ font-size: 22px; color: #e2e8f0; margin-bottom: 4px; }}
  h2 {{ font-size: 15px; color: #94a3b8; font-weight: normal; margin-bottom: 24px; }}
  h3 {{ font-size: 14px; color: #7dd3fc; margin: 28px 0 10px; text-transform: uppercase;
        letter-spacing: 0.08em; }}
  .meta {{ color: #64748b; font-size: 11px; margin-bottom: 32px; }}
  .summary-cards {{ display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 32px; }}
  .summary-card {{
    background: #1e2433; border-radius: 8px; padding: 18px 22px;
    flex: 1; min-width: 180px;
  }}
  .card-label {{ font-size: 10px; color: #64748b; text-transform: uppercase; letter-spacing: 0.1em; }}
  .card-value {{ font-size: 20px; font-weight: bold; margin: 6px 0 4px; }}
  .card-sub {{ font-size: 11px; color: #64748b; }}
  .section {{ margin-bottom: 36px; }}
  .svg-wrap {{
    background: #1e2433; border-radius: 8px; padding: 16px;
    overflow-x: auto;
  }}
  .transfer-flex {{ display: flex; gap: 24px; flex-wrap: wrap; align-items: flex-start; }}
  .transfer-flex .svg-wrap {{ flex: 0 0 auto; }}
  .transfer-notes {{
    background: #1e2433; border-radius: 8px; padding: 18px;
    flex: 1; min-width: 220px; font-size: 12px; color: #94a3b8;
  }}
  .transfer-notes li {{ margin-bottom: 8px; }}
  table {{
    width: 100%; border-collapse: collapse; font-size: 12px;
    background: #1e2433; border-radius: 8px; overflow: hidden;
  }}
  th {{
    background: #263045; color: #94a3b8; text-align: left;
    padding: 10px 14px; font-weight: normal; font-size: 11px;
    text-transform: uppercase; letter-spacing: 0.08em;
  }}
  td {{ padding: 9px 14px; border-top: 1px solid #263045; color: #c9d1e0; }}
  tr:hover td {{ background: #232d40; }}
  .strategy-dot {{
    display: inline-block; width: 10px; height: 10px; border-radius: 50%;
    margin-right: 8px; vertical-align: middle;
  }}
  .sr-bar-bg {{ display: flex; align-items: center; gap: 8px; }}
  .sr-bar {{ height: 12px; border-radius: 3px; min-width: 2px; }}
  .sr-val {{ font-size: 11px; color: #94a3b8; }}
  footer {{ margin-top: 40px; color: #3a4555; font-size: 10px; text-align: center; }}
</style>
</head>
<body>
<h1>GR00T Task Curriculum Generator</h1>
<h2>Automatic Curriculum Learning Schedule Evaluation</h2>
<div class="meta">
  Episodes: {n_episodes} &nbsp;|&nbsp; Seed: {seed} &nbsp;|&nbsp;
  Tasks: {N_TASKS} &nbsp;|&nbsp; Strategies: 3
</div>

<h3>Summary</h3>
<div class="summary-cards">{cards_html}</div>

<div class="section">
  <h3>Average Success Rate Over Training</h3>
  <div class="svg-wrap">{svg_line}</div>
</div>

<div class="section">
  <h3>Final Per-Task SR Heatmap</h3>
  <div class="svg-wrap">{svg_heat}</div>
</div>

<div class="section">
  <h3>Transfer Learning Matrix</h3>
  <div class="transfer-flex">
    <div class="svg-wrap">{svg_transfer}</div>
    <div class="transfer-notes">
      <strong style="color:#c9d1e0;">How transfer bonuses work:</strong>
      <br/><br/>
      <ul>
        <li>Each cell shows the bonus fraction a source task (row) contributes to a destination task (column).</li>
        <li>Bonuses apply only from easier to harder tasks.</li>
        <li>Adjacent difficulty tasks transfer most (~0.12); distant tasks transfer less or nothing.</li>
        <li>Accumulated bonus increases the effective SR ceiling for the destination task.</li>
        <li>Max per-task transfer bonus is capped at 0.25.</li>
      </ul>
      <br/>
      <strong style="color:#c9d1e0;">Task difficulties:</strong>
      <br/><br/>
      {_build_task_difficulty_html()}
    </div>
  </div>
</div>

<div class="section">
  <h3>Strategy Comparison Table</h3>
  <table>
    <thead>
      <tr>
        <th>Strategy</th>
        <th>Final Avg SR</th>
        <th>Steps to 50%</th>
        <th>Forgetting Rate</th>
        <th>Best SR Marker</th>
      </tr>
    </thead>
    <tbody>{table_rows}</tbody>
  </table>
</div>

<div class="section">
  <h3>Per-Task Final Success Rate</h3>
  <table>
    <thead>
      <tr>
        <th>Task</th>
        <th>Difficulty</th>
        {"".join(f"<th>{s.replace('_',' ')}</th>" for s in strategies)}
      </tr>
    </thead>
    <tbody>{per_task_rows}</tbody>
  </table>
</div>

<footer>
  GR00T Task Curriculum Generator &nbsp;|&nbsp;
  OCI Robot Cloud &nbsp;|&nbsp;
  Generated with stdlib-only Python
</footer>
</body>
</html>
"""
    return html


# ---------------------------------------------------------------------------
# JSON output
# ---------------------------------------------------------------------------

def build_json_output(results: Dict, n_episodes: int, seed: int) -> Dict:
    strategies = ["fixed_order", "adaptive", "interleaved"]
    output = {
        "meta": {
            "n_episodes": n_episodes,
            "seed": seed,
            "n_tasks": N_TASKS,
            "tasks": [{"name": t["name"], "difficulty": t["difficulty"]} for t in TASKS],
        },
        "transfer_matrix": {
            TASK_NAMES[i]: {TASK_NAMES[j]: TRANSFER_MATRIX[i][j] for j in range(N_TASKS)}
            for i in range(N_TASKS)
        },
        "strategies": {},
    }
    for s in strategies:
        r = results[s]
        output["strategies"][s] = {
            "final_avg_sr": r["final_avg_sr"],
            "steps_to_50pct": r["steps_to_50pct"],
            "forgetting_rate": r["forgetting_rate"],
            "final_per_task_sr": r["final_per_task"],
            # Include sampled history (every 10th point to keep JSON small)
            "avg_sr_history_sampled": r["avg_sr_history"][::10],
        }

    # Recommendations
    best_sr = max(strategies, key=lambda s: results[s]["final_avg_sr"])
    valid_eff = {s: results[s]["steps_to_50pct"] for s in strategies
                 if results[s]["steps_to_50pct"] is not None}
    best_eff = min(valid_eff, key=valid_eff.get) if valid_eff else None
    best_forget = min(strategies, key=lambda s: results[s]["forgetting_rate"])
    output["recommendations"] = {
        "best_final_sr": best_sr,
        "most_efficient": best_eff,
        "least_forgetting": best_forget,
    }
    return output


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="GR00T Task Curriculum Generator — evaluates curriculum learning strategies."
    )
    parser.add_argument("--mock", action="store_true",
                        help="Run in mock mode (same as normal but prints [MOCK] prefix)")
    parser.add_argument("--n-episodes", type=int, default=500,
                        help="Number of training episodes to simulate (default: 500)")
    parser.add_argument("--output", type=str, default="/tmp/task_curriculum_generator.html",
                        help="Path for HTML report output")
    parser.add_argument("--json-output", type=str, default=None,
                        help="Optional path for JSON output")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed (default: 42)")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    prefix = "[MOCK] " if args.mock else ""

    print(f"{prefix}GR00T Task Curriculum Generator")
    print(f"{prefix}Episodes: {args.n_episodes}  |  Seed: {args.seed}  |  Tasks: {N_TASKS}")
    print(f"{prefix}Strategies: fixed_order, adaptive, interleaved")
    print()

    results = run_simulation(n_episodes=args.n_episodes, seed=args.seed)

    print_summary_table(results)

    # HTML report
    html = generate_html_report(results, n_episodes=args.n_episodes, seed=args.seed)
    output_path = args.output
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"{prefix}HTML report written to: {output_path}")

    # JSON output
    if args.json_output:
        json_data = build_json_output(results, n_episodes=args.n_episodes, seed=args.seed)
        json_path = args.json_output
        os.makedirs(os.path.dirname(os.path.abspath(json_path)), exist_ok=True)
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(json_data, f, indent=2)
        print(f"{prefix}JSON output written to: {json_path}")
    else:
        # Print compact JSON to stdout
        json_data = build_json_output(results, n_episodes=args.n_episodes, seed=args.seed)
        compact = {
            "recommendations": json_data["recommendations"],
            "strategies": {
                s: {
                    "final_avg_sr": json_data["strategies"][s]["final_avg_sr"],
                    "steps_to_50pct": json_data["strategies"][s]["steps_to_50pct"],
                    "forgetting_rate": json_data["strategies"][s]["forgetting_rate"],
                }
                for s in json_data["strategies"]
            },
        }
        print("\nJSON Summary:")
        print(json.dumps(compact, indent=2))


if __name__ == "__main__":
    main()
