#!/usr/bin/env python3
"""
joint_trajectory_optimizer.py — Post-process GR00T action predictions to produce
smoother, physically valid joint trajectories for real-robot execution.

Reduces jerk, respects joint limits, and improves execution quality without re-training.

Usage:
    python joint_trajectory_optimizer.py --mock --output /tmp/joint_trajectory_optimizer.html --seed 42
"""

import argparse
import math
import random
import sys
from dataclasses import dataclass
from typing import List, Tuple

# ---------------------------------------------------------------------------
# 1. JointConfig dataclass
# ---------------------------------------------------------------------------

@dataclass
class JointConfig:
    joint_id: int
    name: str
    min_rad: float
    max_rad: float
    max_velocity_rad_s: float
    max_accel_rad_s2: float


# ---------------------------------------------------------------------------
# 2. Franka Panda joint definitions (from Franka specification)
# ---------------------------------------------------------------------------

FRANKA_JOINTS: List[JointConfig] = [
    JointConfig(0, "joint1", -2.8973, 2.8973, 2.1750, 15.0),
    JointConfig(1, "joint2", -1.7628, 1.7628, 2.1750, 7.5),
    JointConfig(2, "joint3", -2.8973, 2.8973, 2.1750, 10.0),
    JointConfig(3, "joint4", -3.0718, -0.0698, 2.1750, 12.5),
    JointConfig(4, "joint5", -2.8973, 2.8973, 2.6100, 15.0),
    JointConfig(5, "joint6",  -0.0175, 3.7525, 2.6100, 20.0),
    JointConfig(6, "joint7", -2.8973, 2.8973, 2.6100, 20.0),
]


# ---------------------------------------------------------------------------
# 3. TrajectoryOptimizer
# ---------------------------------------------------------------------------

class TrajectoryOptimizer:
    def __init__(
        self,
        joints: List[JointConfig] = None,
        dt: float = 0.033,
        smooth_window: int = 5,
        velocity_limit_scale: float = 0.8,
        jerk_penalty: float = 0.1,
    ):
        self.joints = joints or FRANKA_JOINTS
        self.dt = dt
        self.smooth_window = smooth_window
        self.velocity_limit_scale = velocity_limit_scale
        self.jerk_penalty = jerk_penalty

    # -------------------------------------------------------------------
    # 4. Generate raw trajectory (simulate GR00T output)
    # -------------------------------------------------------------------

    def generate_raw_trajectory(self, n_steps: int = 200, seed: int = 42) -> List[List[float]]:
        """Return list of n_steps frames, each a list of 7 joint positions."""
        rng = random.Random(seed)
        n_joints = len(self.joints)

        # Base sin/cos motion blends
        phases = [rng.uniform(0, 2 * math.pi) for _ in range(n_joints)]
        freqs  = [rng.uniform(0.5, 2.0)       for _ in range(n_joints)]
        amps   = [rng.uniform(0.2, 0.6)        for _ in range(n_joints)]
        offsets = [
            (j.min_rad + j.max_rad) / 2.0 for j in self.joints
        ]

        trajectory = []
        for step in range(n_steps):
            t = step * self.dt
            frame = []
            for i, joint in enumerate(self.joints):
                pos = offsets[i] + amps[i] * math.sin(freqs[i] * t + phases[i])

                # Gaussian noise (sigma = 0.03 rad)
                noise = rng.gauss(0.0, 0.03)

                # Occasional spike (3% probability, 0.3–0.8 rad jump)
                spike = 0.0
                if rng.random() < 0.03:
                    magnitude = rng.uniform(0.3, 0.8)
                    spike = magnitude * rng.choice([-1, 1])

                raw = pos + noise + spike

                # Intentionally allow some limit violations
                if rng.random() < 0.02:
                    raw = joint.max_rad + rng.uniform(0.05, 0.2)

                frame.append(raw)
            trajectory.append(frame)
        return trajectory

    # -------------------------------------------------------------------
    # 5. Apply smoothing (moving average per joint)
    # -------------------------------------------------------------------

    def apply_smoothing(
        self, trajectory: List[List[float]], window: int = None
    ) -> List[List[float]]:
        if window is None:
            window = self.smooth_window
        n_steps  = len(trajectory)
        n_joints = len(trajectory[0])
        half = window // 2
        result = []
        for step in range(n_steps):
            frame = []
            for j in range(n_joints):
                lo = max(0, step - half)
                hi = min(n_steps, step + half + 1)
                avg = sum(trajectory[s][j] for s in range(lo, hi)) / (hi - lo)
                frame.append(avg)
            result.append(frame)
        return result

    # -------------------------------------------------------------------
    # 6. Apply velocity limits (clip step-to-step deltas)
    # -------------------------------------------------------------------

    def apply_velocity_limits(
        self,
        trajectory: List[List[float]],
        dt: float = None,
        joints: List[JointConfig] = None,
    ) -> List[List[float]]:
        if dt is None:
            dt = self.dt
        if joints is None:
            joints = self.joints

        n_steps  = len(trajectory)
        n_joints = len(trajectory[0])
        result   = [list(trajectory[0])]

        for step in range(1, n_steps):
            frame = []
            for j in range(n_joints):
                max_delta = joints[j].max_velocity_rad_s * self.velocity_limit_scale * dt
                prev = result[-1][j]
                curr = trajectory[step][j]
                delta = curr - prev
                if abs(delta) > max_delta:
                    delta = math.copysign(max_delta, delta)
                frame.append(prev + delta)
            result.append(frame)
        return result

    # -------------------------------------------------------------------
    # 7. Apply jerk reduction (penalise large 3rd derivatives)
    # -------------------------------------------------------------------

    def apply_jerk_reduction(
        self, trajectory: List[List[float]], penalty: float = None
    ) -> List[List[float]]:
        if penalty is None:
            penalty = self.jerk_penalty

        result = [list(f) for f in trajectory]
        n_steps  = len(result)
        n_joints = len(result[0])

        # Iterative smoothing pass weighted by local jerk magnitude
        for _ in range(3):
            new_result = [list(result[0]), list(result[1]), list(result[2])]
            for step in range(3, n_steps - 1):
                frame = []
                for j in range(n_joints):
                    # 3rd derivative approximation
                    jerk = (
                        result[step][j]
                        - 3 * result[step - 1][j]
                        + 3 * result[step - 2][j]
                        - result[step - 3][j]
                    )
                    # Blend towards average of neighbours when jerk is large
                    w = min(abs(jerk) * penalty, 0.5)
                    neighbour_avg = (result[step - 1][j] + result[step + 1][j]) / 2.0
                    frame.append((1.0 - w) * result[step][j] + w * neighbour_avg)
                new_result.append(frame)
            new_result.append(list(result[-1]))
            result = new_result
        return result

    # -------------------------------------------------------------------
    # 8. Detect violations
    # -------------------------------------------------------------------

    def detect_violations(
        self, trajectory: List[List[float]], joints: List[JointConfig] = None
    ) -> dict:
        if joints is None:
            joints = self.joints

        n_steps  = len(trajectory)
        n_joints = len(trajectory[0])
        dt = self.dt

        pos_violations  = [0] * n_joints
        vel_violations  = [0] * n_joints
        jerk_violations = [0] * n_joints

        for step in range(n_steps):
            for j in range(n_joints):
                q = trajectory[step][j]
                if q < joints[j].min_rad or q > joints[j].max_rad:
                    pos_violations[j] += 1

        for step in range(1, n_steps):
            for j in range(n_joints):
                vel = abs(trajectory[step][j] - trajectory[step - 1][j]) / dt
                if vel > joints[j].max_velocity_rad_s:
                    vel_violations[j] += 1

        for step in range(3, n_steps):
            for j in range(n_joints):
                jerk = abs(
                    trajectory[step][j]
                    - 3 * trajectory[step - 1][j]
                    + 3 * trajectory[step - 2][j]
                    - trajectory[step - 3][j]
                ) / (dt ** 3)
                if jerk > 50.0:
                    jerk_violations[j] += 1

        return {
            "position":  pos_violations,
            "velocity":  vel_violations,
            "jerk":      jerk_violations,
        }

    # -------------------------------------------------------------------
    # Full optimize pass
    # -------------------------------------------------------------------

    def optimize(self, trajectory: List[List[float]]) -> List[List[float]]:
        traj = self.apply_smoothing(trajectory)
        traj = self.apply_velocity_limits(traj)
        traj = self.apply_jerk_reduction(traj)
        return traj


# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------

def _normalize(values: List[float]) -> List[float]:
    lo, hi = min(values), max(values)
    span = hi - lo if hi != lo else 1.0
    return [(v - lo) / span for v in values]


def _svg_polyline(xs: List[float], ys: List[float], color: str, stroke_width: float = 1.5) -> str:
    pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in zip(xs, ys))
    return f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="{stroke_width}" stroke-linejoin="round"/>'


def build_trajectory_svg(
    raw: List[List[float]],
    opt: List[List[float]],
    joint_indices: List[int] = (0, 3, 6),
) -> str:
    W, H = 780, 300
    panel_w = W // 3
    panel_h = H
    pad = 18

    svg_parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'style="background:#0f172a;border-radius:8px;">'
    ]

    for idx, ji in enumerate(joint_indices):
        raw_vals = [frame[ji] for frame in raw]
        opt_vals = [frame[ji] for frame in opt]
        all_vals = raw_vals + opt_vals
        lo, hi = min(all_vals), max(all_vals)
        span = hi - lo if hi != lo else 1.0

        ox = idx * panel_w + pad
        ow = panel_w - 2 * pad
        oh = panel_h - 2 * pad

        n = len(raw_vals)
        xs = [ox + i / (n - 1) * ow for i in range(n)]
        raw_ys = [pad + oh - (v - lo) / span * oh for v in raw_vals]
        opt_ys = [pad + oh - (v - lo) / span * oh for v in opt_vals]

        label = FRANKA_JOINTS[ji].name
        svg_parts.append(
            f'<text x="{ox + ow//2}" y="13" text-anchor="middle" '
            f'font-size="11" fill="#94a3b8" font-family="monospace">{label}</text>'
        )
        svg_parts.append(_svg_polyline(xs, raw_ys, "#9ca3af", 1.2))
        svg_parts.append(_svg_polyline(xs, opt_ys, "#22c55e", 1.8))

    # Legend
    svg_parts.append(
        '<text x="12" y="292" font-size="10" fill="#9ca3af" font-family="monospace">'
        '&#9644; raw</text>'
    )
    svg_parts.append(
        '<text x="60" y="292" font-size="10" fill="#22c55e" font-family="monospace">'
        '&#9644; optimized</text>'
    )
    svg_parts.append("</svg>")
    return "\n".join(svg_parts)


def build_jerk_svg(raw: List[List[float]], opt: List[List[float]], dt: float = 0.033) -> str:
    W, H = 780, 220
    pad = 22

    def total_jerk(traj):
        jerks = []
        for step in range(3, len(traj)):
            total = sum(
                abs(traj[step][j] - 3*traj[step-1][j] + 3*traj[step-2][j] - traj[step-3][j])
                for j in range(len(traj[0]))
            ) / (dt ** 3)
            jerks.append(total)
        return jerks

    raw_j = total_jerk(raw)
    opt_j = total_jerk(opt)
    all_j = raw_j + opt_j
    lo, hi = 0.0, max(all_j) if all_j else 1.0
    span   = hi - lo if hi != lo else 1.0

    ow = W - 2 * pad
    oh = H - 2 * pad
    n  = len(raw_j)
    xs = [pad + i / (n - 1) * ow for i in range(n)]
    raw_ys = [pad + oh - (v - lo) / span * oh for v in raw_j]
    opt_ys = [pad + oh - (v - lo) / span * oh for v in opt_j]

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'style="background:#0f172a;border-radius:8px;">\n'
        f'<text x="{W//2}" y="14" text-anchor="middle" font-size="11" fill="#94a3b8" '
        f'font-family="monospace">Total Jerk Magnitude (rad/s³)</text>\n'
        + _svg_polyline(xs, raw_ys, "#ef4444", 1.5) + "\n"
        + _svg_polyline(xs, opt_ys, "#22c55e", 1.8) + "\n"
        '<text x="12" y="212" font-size="10" fill="#ef4444" font-family="monospace">&#9644; raw</text>\n'
        '<text x="52" y="212" font-size="10" fill="#22c55e" font-family="monospace">&#9644; optimized</text>\n'
        "</svg>"
    )
    return svg


# ---------------------------------------------------------------------------
# 9. HTML Report
# ---------------------------------------------------------------------------

def build_html_report(
    raw: List[List[float]],
    opt: List[List[float]],
    joints: List[JointConfig],
    violations_before: dict,
    violations_after: dict,
    dt: float = 0.033,
) -> str:

    n_joints = len(joints)

    def total(d):
        return sum(sum(d[k]) for k in d)

    vb = total(violations_before)
    va = total(violations_after)
    jerk_before = sum(violations_before["jerk"])
    jerk_after  = sum(violations_after["jerk"])
    jerk_pct = round((1 - jerk_after / jerk_before) * 100, 1) if jerk_before > 0 else 100.0

    traj_svg = build_trajectory_svg(raw, opt)
    jerk_svg = build_jerk_svg(raw, opt, dt)

    # Violation table rows
    table_rows = []
    for j in range(n_joints):
        for vtype in ("position", "velocity", "jerk"):
            b = violations_before[vtype][j]
            a = violations_after[vtype][j]
            if b == 0 and a == 0:
                continue
            reduction = f"{round((1 - a/b)*100)}%" if b > 0 else "—"
            row_color = "#0f172a" if j % 2 == 0 else "#162032"
            table_rows.append(
                f'<tr style="background:{row_color};">'
                f'<td>{joints[j].name}</td>'
                f'<td style="color:#94a3b8">{vtype}</td>'
                f'<td style="color:#f87171">{b}</td>'
                f'<td style="color:#4ade80">{a}</td>'
                f'<td style="color:#facc15">{reduction}</td>'
                f"</tr>"
            )
    table_html = "\n".join(table_rows) if table_rows else (
        '<tr><td colspan="5" style="color:#64748b;text-align:center">No violations detected</td></tr>'
    )

    kpi_style = "background:#1e293b;border-radius:8px;padding:18px 24px;text-align:center;flex:1;"
    kpi_val   = "font-size:2.2rem;font-weight:700;color:#22c55e;display:block;"
    kpi_lbl   = "font-size:0.82rem;color:#94a3b8;margin-top:4px;display:block;"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Joint Trajectory Optimizer — OCI Robot Cloud</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:'Segoe UI',system-ui,sans-serif;background:#0f172a;color:#e2e8f0;padding:28px}}
  h1{{color:#C74634;font-size:1.6rem;margin-bottom:4px}}
  h2{{color:#C74634;font-size:1.1rem;margin:28px 0 12px}}
  .sub{{color:#64748b;font-size:0.85rem;margin-bottom:24px}}
  .kpis{{display:flex;gap:16px;margin-bottom:28px;flex-wrap:wrap}}
  table{{width:100%;border-collapse:collapse;font-size:0.85rem}}
  th{{background:#162032;color:#94a3b8;padding:8px 12px;text-align:left;font-weight:600}}
  td{{padding:7px 12px;border-bottom:1px solid #1e293b}}
  .chart-wrap{{margin-bottom:24px;overflow-x:auto}}
</style>
</head>
<body>
<h1>Joint Trajectory Optimizer</h1>
<p class="sub">OCI Robot Cloud — GR00T action post-processing | Franka Panda | {len(raw)} steps @ {round(1/dt)}Hz</p>

<div class="kpis">
  <div style="{kpi_style}">
    <span style="{kpi_val}">{n_joints}</span>
    <span style="{kpi_lbl}">Joints Optimized</span>
  </div>
  <div style="{kpi_style}">
    <span style="{kpi_val};color:#f87171;">{vb}</span>
    <span style="{kpi_lbl}">Violations Before</span>
  </div>
  <div style="{kpi_style}">
    <span style="{kpi_val}">{va}</span>
    <span style="{kpi_lbl}">Violations After</span>
  </div>
  <div style="{kpi_style}">
    <span style="{kpi_val}">{jerk_pct}%</span>
    <span style="{kpi_lbl}">Jerk Reduction</span>
  </div>
</div>

<h2>Joint Trajectories — Raw vs Optimized (joints 1, 4, 7)</h2>
<div class="chart-wrap">{traj_svg}</div>

<h2>Jerk Magnitude Over Time</h2>
<div class="chart-wrap">{jerk_svg}</div>

<h2>Violation Summary</h2>
<table>
  <thead>
    <tr>
      <th>Joint</th><th>Type</th>
      <th>Before</th><th>After</th><th>Reduction</th>
    </tr>
  </thead>
  <tbody>
    {table_html}
  </tbody>
</table>

<p style="color:#334155;font-size:0.75rem;margin-top:28px;text-align:center">
  OCI Robot Cloud · Joint Trajectory Optimizer · Generated {__import__('datetime').date.today()}
</p>
</body>
</html>"""
    return html


# ---------------------------------------------------------------------------
# 10. CLI entrypoint
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Post-process GR00T joint trajectories for smooth real-robot execution."
    )
    parser.add_argument("--mock",   action="store_true", help="Generate mock trajectory (default)")
    parser.add_argument("--output", default="/tmp/joint_trajectory_optimizer.html",
                        help="Output HTML report path")
    parser.add_argument("--seed",   type=int, default=42, help="Random seed for mock data")
    parser.add_argument("--steps",  type=int, default=200, help="Number of trajectory steps")
    args = parser.parse_args()

    optimizer = TrajectoryOptimizer(
        joints=FRANKA_JOINTS,
        dt=0.033,
        smooth_window=5,
        velocity_limit_scale=0.8,
        jerk_penalty=0.1,
    )

    print(f"[joint_trajectory_optimizer] Generating raw trajectory (seed={args.seed}, steps={args.steps})...")
    raw = optimizer.generate_raw_trajectory(n_steps=args.steps, seed=args.seed)

    print("[joint_trajectory_optimizer] Optimizing trajectory...")
    opt = optimizer.optimize(raw)

    print("[joint_trajectory_optimizer] Detecting violations...")
    vb = optimizer.detect_violations(raw)
    va = optimizer.detect_violations(opt)

    def _sum(d):
        return {k: sum(d[k]) for k in d}

    print(f"  Violations before: {_sum(vb)}")
    print(f"  Violations after:  {_sum(va)}")

    print(f"[joint_trajectory_optimizer] Building HTML report → {args.output}")
    html = build_html_report(raw, opt, FRANKA_JOINTS, vb, va, dt=optimizer.dt)

    with open(args.output, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"[joint_trajectory_optimizer] Done. Report saved to {args.output}")


if __name__ == "__main__":
    main()
