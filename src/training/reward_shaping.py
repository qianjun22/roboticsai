"""
reward_shaping.py — Potential-based reward shaping for GR00T RL fine-tuning.

Provides richer training signal for robotics manipulation beyond the basic
dense reward in rl_finetune.py.

Usage:
    python reward_shaping.py --benchmark --curriculum-level 1 --output /tmp/reward_landscape.svg
"""

from __future__ import annotations

import argparse
import math
import random
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class RewardConfig:
    """Weights and thresholds for each reward component."""

    # Component weights for total reward computation
    w_reach: float = 0.4
    w_grasp: float = 0.2
    w_lift: float = 0.5
    w_hold: float = 0.3
    w_smoothness: float = 0.1
    w_efficiency: float = 0.05
    w_success: float = 10.0

    # Grasp thresholds
    cube_size: float = 0.04
    grasp_margin_low: float = 0.005
    grasp_margin_high: float = 0.01

    # Lift thresholds
    table_z: float = 0.70
    target_z: float = 0.78
    lift_bonus_multiplier: float = 5.0

    # Hold penalty
    hold_drop_threshold: float = 0.02
    hold_penalty: float = -0.5

    # Smoothness
    smoothness_scale: float = 0.3
    n_joints: int = 9

    # Efficiency
    efficiency_scale: float = 0.01
    max_steps: int = 60

    @classmethod
    def from_dict(cls, d: dict) -> "RewardConfig":
        cfg = cls()
        for k, v in d.items():
            if hasattr(cfg, k):
                setattr(cfg, k, v)
        return cfg


# ---------------------------------------------------------------------------
# Curriculum weight adjustments
# ---------------------------------------------------------------------------

_CURRICULUM_OVERRIDES: Dict[int, Dict[str, float]] = {
    1: {  # Early: emphasize reaching, ignore lift/hold
        "w_reach": 0.8,
        "w_grasp": 0.3,
        "w_lift": 0.1,
        "w_hold": 0.05,
        "w_smoothness": 0.05,
        "w_efficiency": 0.01,
    },
    2: {  # Mid-early: balanced reach + grasp
        "w_reach": 0.6,
        "w_grasp": 0.4,
        "w_lift": 0.3,
        "w_hold": 0.1,
        "w_smoothness": 0.08,
        "w_efficiency": 0.02,
    },
    3: {  # Mid-late: lift becomes important
        "w_reach": 0.4,
        "w_grasp": 0.3,
        "w_lift": 0.5,
        "w_hold": 0.2,
        "w_smoothness": 0.1,
        "w_efficiency": 0.03,
    },
    4: {  # Full task: lift/hold dominant
        "w_reach": 0.2,
        "w_grasp": 0.2,
        "w_lift": 0.7,
        "w_hold": 0.5,
        "w_smoothness": 0.15,
        "w_efficiency": 0.05,
    },
}


# ---------------------------------------------------------------------------
# RewardShaper
# ---------------------------------------------------------------------------

class RewardShaper:
    """
    Potential-based reward shaping for GR00T RL fine-tuning.

    Each component returns a float in [-1, 1] or [0, 1]. The total reward
    is a weighted sum plus a large success bonus.

    Args:
        config: RewardConfig instance. If None, uses defaults.
        curriculum_level: 1–4 adjusts component weights for staged training.
    """

    def __init__(
        self,
        config: Optional[RewardConfig] = None,
        curriculum_level: Optional[int] = None,
    ) -> None:
        self.config = config or RewardConfig()

        if curriculum_level is not None:
            if curriculum_level not in _CURRICULUM_OVERRIDES:
                raise ValueError(f"curriculum_level must be 1–4, got {curriculum_level}")
            overrides = _CURRICULUM_OVERRIDES[curriculum_level]
            for k, v in overrides.items():
                setattr(self.config, k, v)

        self.curriculum_level = curriculum_level
        self._prev_reach_potential: Optional[float] = None

    # ------------------------------------------------------------------
    # Individual reward components
    # ------------------------------------------------------------------

    def reach_reward(self, ee_pos: Tuple[float, float, float],
                     cube_pos: Tuple[float, float, float]) -> float:
        """
        Potential-based shaping: Φ = -dist(ee, cube).
        Returns Φ_t - Φ_{t-1} (reward for closing the gap).
        Range: typically [-1, 1] for typical workspace distances.
        """
        dist = math.sqrt(sum((a - b) ** 2 for a, b in zip(ee_pos, cube_pos)))
        potential = -dist
        if self._prev_reach_potential is None:
            self._prev_reach_potential = potential
            return 0.0
        delta = potential - self._prev_reach_potential
        self._prev_reach_potential = potential
        # Clip to [-1, 1] — typical step displacement < 1m
        return max(-1.0, min(1.0, delta))

    def grasp_reward(self, gripper_width: float,
                     cube_size: Optional[float] = None) -> float:
        """
        Shaped bonus when gripper is in contact region around cube size.
        Returns 1.0 in contact region, 0.0 otherwise. Range: [0, 1].
        """
        cfg = self.config
        cs = cube_size if cube_size is not None else cfg.cube_size
        low = cs - cfg.grasp_margin_low
        high = cs + cfg.grasp_margin_high
        return 1.0 if low <= gripper_width <= high else 0.0

    def lift_reward(self, cube_z: float,
                    table_z: Optional[float] = None,
                    target_z: Optional[float] = None) -> float:
        """
        Proportional lift reward: (cube_z - table_z) / (target_z - table_z).
        Clipped to [0, 1]. 5× bonus (capped at 1.0) if cube_z > target_z.
        """
        cfg = self.config
        tz = table_z if table_z is not None else cfg.table_z
        tgz = target_z if target_z is not None else cfg.target_z
        span = tgz - tz
        if span <= 0:
            return 0.0
        raw = (cube_z - tz) / span
        clipped = max(0.0, min(1.0, raw))
        if cube_z > tgz:
            clipped = min(1.0, clipped * cfg.lift_bonus_multiplier)
        return clipped

    def hold_reward(self, cube_z: float, prev_cube_z: float) -> float:
        """
        Penalize dropping: -0.5 if cube_z drops >2cm in one step.
        Range: {-0.5, 0.0}.
        """
        drop = prev_cube_z - cube_z
        if drop > self.config.hold_drop_threshold:
            return self.config.hold_penalty
        return 0.0

    def smoothness_reward(self, action: Tuple[float, ...],
                           prev_action: Tuple[float, ...]) -> float:
        """
        Penalize jerky motions: -0.3 × ||Δa||² / n_joints.
        Range: [-0.3, 0.0].
        """
        cfg = self.config
        n = cfg.n_joints
        sq_norm = sum((a - b) ** 2 for a, b in zip(action, prev_action))
        return -cfg.smoothness_scale * sq_norm / n

    def efficiency_reward(self, step: int, max_steps: Optional[int] = None) -> float:
        """
        Small time penalty: -0.01 × step / max_steps.
        Encourages faster task completion. Range: [-0.01, 0.0].
        """
        cfg = self.config
        ms = max_steps if max_steps is not None else cfg.max_steps
        return -cfg.efficiency_scale * (step / ms)

    # ------------------------------------------------------------------
    # Combined compute
    # ------------------------------------------------------------------

    def compute(self, state_dict: dict) -> Tuple[float, dict]:
        """
        Compute total shaped reward and per-component breakdown.

        state_dict keys:
            ee_pos        : (x, y, z) end-effector position
            cube_pos      : (x, y, z) cube position
            gripper_width : float, current gripper opening
            cube_z        : float, cube height
            prev_cube_z   : float, cube height previous step
            action        : tuple/list of joint actions
            prev_action   : tuple/list of previous joint actions
            step          : int, current episode step
            success       : bool, whether task succeeded

        Returns:
            total_reward  : float
            breakdown     : dict with per-component values and weights
        """
        cfg = self.config

        r_reach = self.reach_reward(state_dict["ee_pos"], state_dict["cube_pos"])
        r_grasp = self.grasp_reward(state_dict["gripper_width"])
        r_lift = self.lift_reward(state_dict["cube_z"])
        r_hold = self.hold_reward(state_dict["cube_z"], state_dict["prev_cube_z"])
        r_smooth = self.smoothness_reward(state_dict["action"], state_dict["prev_action"])
        r_eff = self.efficiency_reward(state_dict["step"])
        r_success = cfg.w_success if state_dict.get("success", False) else 0.0

        total = (
            cfg.w_reach * r_reach
            + cfg.w_grasp * r_grasp
            + cfg.w_lift * r_lift
            + cfg.w_hold * r_hold
            + cfg.w_smoothness * r_smooth
            + cfg.w_efficiency * r_eff
            + r_success
        )

        breakdown = {
            "reach":      (r_reach,  cfg.w_reach),
            "grasp":      (r_grasp,  cfg.w_grasp),
            "lift":       (r_lift,   cfg.w_lift),
            "hold":       (r_hold,   cfg.w_hold),
            "smoothness": (r_smooth, cfg.w_smoothness),
            "efficiency": (r_eff,    cfg.w_efficiency),
            "success":    (r_success, 1.0),
            "total":      (total,    1.0),
        }
        return total, breakdown

    def reset(self) -> None:
        """Reset stateful potential (call at start of each episode)."""
        self._prev_reach_potential = None


# ---------------------------------------------------------------------------
# SVG reward landscape (no matplotlib)
# ---------------------------------------------------------------------------

def plot_reward_landscape(shaper: RewardShaper, output_path: str) -> None:
    """
    Generate an SVG showing reward vs cube_z and vs distance to cube.
    Uses inline SVG path math — no matplotlib dependency.
    """
    W, H = 700, 400
    pad_l, pad_r, pad_t, pad_b = 60, 30, 30, 50

    plot_w = W - pad_l - pad_r
    plot_h = H - pad_t - pad_b

    def to_svg_x(val: float, vmin: float, vmax: float) -> float:
        return pad_l + (val - vmin) / (vmax - vmin) * plot_w

    def to_svg_y(val: float, vmin: float, vmax: float) -> float:
        # SVG y-axis is inverted
        return pad_t + (1.0 - (val - vmin) / (vmax - vmin)) * plot_h

    # --- Lift reward vs cube_z ---
    z_values = [0.68 + i * 0.002 for i in range(60)]
    lift_rewards = [shaper.lift_reward(z) for z in z_values]

    def polyline(xs, ys, x_range, y_range, color, width=2):
        pts = " ".join(
            f"{to_svg_x(x, *x_range):.1f},{to_svg_y(y, *y_range):.1f}"
            for x, y in zip(xs, ys)
        )
        return f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="{width}"/>'

    lift_line = polyline(z_values, lift_rewards, (min(z_values), max(z_values)), (-0.1, 1.1),
                         "#2563eb")

    # --- Reach reward delta vs distance ---
    # Simulate shaper moving from far to close
    distances = [1.0 - i * 0.02 for i in range(50)]
    reach_deltas = []
    shaper2 = RewardShaper(config=RewardConfig())
    prev_d = None
    for d in distances:
        ee = (d, 0.0, 0.75)
        cube = (0.0, 0.0, 0.75)
        r = shaper2.reach_reward(ee, cube)
        reach_deltas.append(r)

    # Panel 1: lift reward (left half)
    half_w = plot_w // 2 - 10

    def panel_polyline(xs, ys, x_range, y_range, x_off, color):
        pts = []
        for x, y in zip(xs, ys):
            px = x_off + (x - x_range[0]) / (x_range[1] - x_range[0]) * half_w
            py = pad_t + (1.0 - (y - y_range[0]) / (y_range[1] - y_range[0])) * plot_h
            pts.append(f"{px:.1f},{py:.1f}")
        return f'<polyline points="{" ".join(pts)}" fill="none" stroke="{color}" stroke-width="2"/>'

    lift_pl = panel_polyline(z_values, lift_rewards,
                             (min(z_values), max(z_values)), (-0.05, 1.05),
                             pad_l, "#2563eb")

    x_off2 = pad_l + half_w + 20
    reach_pl = panel_polyline(distances, reach_deltas,
                              (min(distances), max(distances)), (-0.05, 0.05),
                              x_off2, "#dc2626")

    def axis_labels(x_off, xmin, xmax, ymin, ymax, title, xlabel, ylabel, y_ticks=5):
        lines = []
        # Title
        cx = x_off + half_w // 2
        lines.append(f'<text x="{cx}" y="{pad_t - 10}" text-anchor="middle" '
                     f'font-size="13" font-family="monospace" fill="#111">{title}</text>')
        # X axis
        lines.append(f'<line x1="{x_off}" y1="{pad_t + plot_h}" '
                     f'x2="{x_off + half_w}" y2="{pad_t + plot_h}" stroke="#999" stroke-width="1"/>')
        # Y axis
        lines.append(f'<line x1="{x_off}" y1="{pad_t}" '
                     f'x2="{x_off}" y2="{pad_t + plot_h}" stroke="#999" stroke-width="1"/>')
        # X ticks
        for i in range(3):
            frac = i / 2
            xv = xmin + frac * (xmax - xmin)
            px = x_off + frac * half_w
            py = pad_t + plot_h
            lines.append(f'<line x1="{px:.0f}" y1="{py}" x2="{px:.0f}" y2="{py+4}" stroke="#999"/>')
            lines.append(f'<text x="{px:.0f}" y="{py+15}" text-anchor="middle" '
                         f'font-size="10" fill="#555">{xv:.2f}</text>')
        # Y ticks
        for i in range(y_ticks + 1):
            frac = i / y_ticks
            yv = ymin + frac * (ymax - ymin)
            py = pad_t + (1.0 - frac) * plot_h
            lines.append(f'<line x1="{x_off - 4}" y1="{py:.0f}" x2="{x_off}" y2="{py:.0f}" stroke="#999"/>')
            lines.append(f'<text x="{x_off - 6}" y="{py + 4:.0f}" text-anchor="end" '
                         f'font-size="10" fill="#555">{yv:.2f}</text>')
        # Axis labels
        lines.append(f'<text x="{x_off + half_w // 2}" y="{pad_t + plot_h + 35}" '
                     f'text-anchor="middle" font-size="11" fill="#333">{xlabel}</text>')
        return "\n".join(lines)

    ax1 = axis_labels(pad_l, min(z_values), max(z_values), -0.05, 1.05,
                      "Lift Reward vs Cube Z", "cube_z (m)", "lift_reward")
    ax2 = axis_labels(x_off2, min(distances), max(distances), -0.05, 0.05,
                      "Reach Delta vs Distance", "distance (m)", "reach_delta")

    # Zero lines
    def zero_line(x_off, ymin, ymax):
        if ymin < 0 < ymax:
            frac = (0.0 - ymin) / (ymax - ymin)
            py = pad_t + (1.0 - frac) * plot_h
            return (f'<line x1="{x_off}" y1="{py:.0f}" x2="{x_off + half_w}" '
                    f'y2="{py:.0f}" stroke="#ccc" stroke-width="1" stroke-dasharray="4,3"/>')
        return ""

    z1 = zero_line(pad_l, -0.05, 1.05)
    z2 = zero_line(x_off2, -0.05, 0.05)

    legend = (
        f'<rect x="{pad_l + 5}" y="{pad_t + 5}" width="10" height="4" fill="#2563eb"/>'
        f'<text x="{pad_l + 18}" y="{pad_t + 12}" font-size="10" fill="#333">lift_reward</text>'
        f'<rect x="{x_off2 + 5}" y="{pad_t + 5}" width="10" height="4" fill="#dc2626"/>'
        f'<text x="{x_off2 + 18}" y="{pad_t + 12}" font-size="10" fill="#333">reach_delta</text>'
    )

    svg = f"""<?xml version="1.0" encoding="utf-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
  <rect width="{W}" height="{H}" fill="#f9fafb"/>
  <text x="{W//2}" y="20" text-anchor="middle" font-size="15" font-family="monospace"
        font-weight="bold" fill="#111">GR00T Reward Landscape</text>
  {ax1}
  {ax2}
  {z1}
  {z2}
  {lift_pl}
  {reach_pl}
  {legend}
</svg>
"""
    with open(output_path, "w") as f:
        f.write(svg)
    print(f"[reward_shaping] SVG saved to {output_path}")


# ---------------------------------------------------------------------------
# Benchmark
# ---------------------------------------------------------------------------

def benchmark_rewards(n_episodes: int = 100, seed: int = 42,
                      curriculum_level: Optional[int] = None) -> dict:
    """
    Mock rollout benchmark: simulate n_episodes and collect reward stats.

    Returns:
        dict with avg_total_reward, component contribution table, and
        per-component averages.
    """
    rng = random.Random(seed)

    shaper = RewardShaper(curriculum_level=curriculum_level)
    cfg = shaper.config

    component_sums: Dict[str, float] = {
        "reach": 0.0, "grasp": 0.0, "lift": 0.0,
        "hold": 0.0, "smoothness": 0.0, "efficiency": 0.0,
        "success": 0.0,
    }
    total_sum = 0.0
    success_count = 0

    for ep in range(n_episodes):
        shaper.reset()
        ep_total = 0.0
        ep_comps: Dict[str, float] = {k: 0.0 for k in component_sums}
        n_steps = rng.randint(20, cfg.max_steps)

        # Simulate a trajectory: cube starts on table, ee starts far
        cube_x = rng.uniform(-0.1, 0.1)
        cube_y = rng.uniform(-0.1, 0.1)
        cube_z = cfg.table_z
        prev_cube_z = cube_z

        ee_x = rng.uniform(-0.4, 0.4)
        ee_y = rng.uniform(-0.4, 0.4)
        ee_z = rng.uniform(0.75, 0.85)

        action = tuple(rng.uniform(-0.1, 0.1) for _ in range(9))
        gripper = rng.uniform(0.02, 0.08)

        success = False
        for step in range(n_steps):
            # Slowly move ee toward cube
            ee_x += (cube_x - ee_x) * 0.15 + rng.gauss(0, 0.01)
            ee_y += (cube_y - ee_y) * 0.15 + rng.gauss(0, 0.01)
            ee_z += (cube_z - ee_z) * 0.1 + rng.gauss(0, 0.005)

            # Simulate lift after midpoint
            if step > n_steps // 2:
                prev_cube_z = cube_z
                cube_z = min(cfg.target_z + 0.01,
                             cube_z + rng.uniform(0.0, 0.005))
                gripper = rng.uniform(cfg.cube_size - 0.004, cfg.cube_size + 0.008)
            else:
                prev_cube_z = cube_z

            prev_action = action
            action = tuple(a + rng.gauss(0, 0.03) for a in action)
            success = cube_z >= cfg.target_z and step == n_steps - 1

            state = {
                "ee_pos": (ee_x, ee_y, ee_z),
                "cube_pos": (cube_x, cube_y, cube_z),
                "gripper_width": gripper,
                "cube_z": cube_z,
                "prev_cube_z": prev_cube_z,
                "action": action,
                "prev_action": prev_action,
                "step": step,
                "success": success,
            }
            total, breakdown = shaper.compute(state)
            ep_total += total
            for k in ep_comps:
                val, w = breakdown[k]
                ep_comps[k] += val * w

        total_sum += ep_total
        for k in component_sums:
            component_sums[k] += ep_comps[k]
        if success:
            success_count += 1

    avg_total = total_sum / n_episodes
    avg_comps = {k: v / n_episodes for k, v in component_sums.items()}

    # Contribution fractions (as % of abs total)
    abs_total = sum(abs(v) for v in avg_comps.values()) or 1.0
    contributions = {k: abs(v) / abs_total * 100 for k, v in avg_comps.items()}

    result = {
        "n_episodes": n_episodes,
        "avg_total_reward": avg_total,
        "success_rate": success_count / n_episodes,
        "component_averages": avg_comps,
        "component_contributions_pct": contributions,
        "curriculum_level": curriculum_level,
    }

    # Print summary
    print("\n" + "=" * 60)
    print(f"  Reward Benchmark  |  n={n_episodes}  seed={seed}"
          + (f"  curriculum={curriculum_level}" if curriculum_level else ""))
    print("=" * 60)
    print(f"  Avg total reward : {avg_total:.4f}")
    print(f"  Success rate     : {success_count}/{n_episodes} "
          f"({result['success_rate']*100:.1f}%)")
    print()
    print(f"  {'Component':<14} {'Avg Weighted':>14} {'Contribution %':>16}")
    print("  " + "-" * 46)
    for k in ["reach", "grasp", "lift", "hold", "smoothness", "efficiency", "success"]:
        print(f"  {k:<14} {avg_comps[k]:>14.4f} {contributions[k]:>15.1f}%")
    print("=" * 60 + "\n")

    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="GR00T reward shaping module — benchmark and visualize."
    )
    parser.add_argument("--benchmark", action="store_true",
                        help="Run mock rollout benchmark")
    parser.add_argument("--n-episodes", type=int, default=100,
                        help="Number of mock episodes for benchmark (default: 100)")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed for benchmark (default: 42)")
    parser.add_argument("--curriculum-level", type=int, choices=[1, 2, 3, 4],
                        default=None, help="Curriculum level 1-4 (adjusts weights)")
    parser.add_argument("--output", type=str, default=None,
                        help="Output path for SVG reward landscape")
    args = parser.parse_args()

    shaper = RewardShaper(curriculum_level=args.curriculum_level)

    if args.benchmark:
        benchmark_rewards(
            n_episodes=args.n_episodes,
            seed=args.seed,
            curriculum_level=args.curriculum_level,
        )

    if args.output:
        plot_reward_landscape(shaper, args.output)

    if not args.benchmark and not args.output:
        parser.print_help()


if __name__ == "__main__":
    main()
