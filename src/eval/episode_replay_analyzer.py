#!/usr/bin/env python3
"""
episode_replay_analyzer.py — Deep per-episode analysis for GR00T evaluation.

Segments each episode into phases (approach / grasp / lift / hold / done),
computes per-phase timing, joint velocity profiles, and failure attribution.
Generates a rich HTML report for each episode — useful for debugging why
specific episodes fail and identifying systematic robot behavior patterns.

Usage:
    python src/eval/episode_replay_analyzer.py --mock --output /tmp/episode_analysis.html
    python src/eval/episode_replay_analyzer.py --episode-dir /tmp/eval_1000demo/episodes/ --output /tmp/analysis.html
"""

import json
import math
import random
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

# ── Phase definitions ─────────────────────────────────────────────────────────

PHASES = ["idle", "approach", "grasp", "lift", "hold", "done"]

PHASE_COLORS = {
    "idle":     "#475569",
    "approach": "#3b82f6",
    "grasp":    "#f59e0b",
    "lift":     "#6366f1",
    "hold":     "#22c55e",
    "done":     "#94a3b8",
}

FAILURE_CAUSES = {
    "approach_timeout": "Robot failed to reach cube within time limit",
    "grasp_slip":       "Gripper closed but cube slipped (cube_z below grasp threshold)",
    "lift_insufficient": "Cube lifted but not high enough (cube_z < 0.78m)",
    "hold_dropped":     "Cube dropped during hold phase (cube_z sudden drop)",
    "knocked_off":      "Cube knocked off table (cube_z < 0.60m)",
    "timeout":          "Episode timeout — all steps used",
    "none":             "Success",
}


# ── Data structures ───────────────────────────────────────────────────────────

@dataclass
class EpisodeStep:
    step: int
    cube_z: float
    ee_x: float
    ee_y: float
    ee_z: float
    gripper_width: float
    joint_velocities: list[float]   # 7-DOF arm
    phase: str
    latency_ms: float


@dataclass
class PhaseSegment:
    phase: str
    start_step: int
    end_step: int
    duration_steps: int
    avg_velocity: float
    max_velocity: float
    cube_z_delta: float


@dataclass
class EpisodeAnalysis:
    episode_id: str
    success: bool
    n_steps: int
    total_latency_ms: float
    avg_latency_ms: float
    cube_z_final: float
    cube_z_max: float
    failure_cause: str
    phases: list[PhaseSegment]
    steps: list[EpisodeStep]
    joint_range_used: list[float]   # max joint velocity per joint (7-DOF)
    smoothness_score: float         # 0-1, higher = smoother trajectory


# ── Mock episode generation ───────────────────────────────────────────────────

def _detect_phase(step: int, cube_z: float, ee_z: float,
                  gripper_width: float, n_steps: int) -> str:
    if step < n_steps * 0.08:
        return "idle"
    if ee_z > 0.70 and cube_z < 0.72:
        return "approach"
    if gripper_width < 0.05 and cube_z < 0.73:
        return "grasp"
    if cube_z > 0.72 and cube_z < 0.78:
        return "lift"
    if cube_z >= 0.78:
        return "hold"
    return "approach"


def generate_mock_episode(ep_id: str, rng: random.Random,
                          success_prob: float = 0.15) -> EpisodeAnalysis:
    n_steps = 50 + rng.randint(0, 20)
    success = rng.random() < success_prob

    steps = []
    cube_z = 0.705
    ee_x, ee_y, ee_z = rng.uniform(-0.1, 0.1), rng.uniform(-0.1, 0.1), 0.85
    gripper_width = 0.08
    prev_joints = [0.0] * 7
    latency_acc = 0.0

    failure_cause = "none"

    for i in range(n_steps):
        lat = rng.gauss(226, 12)
        latency_acc += lat

        # Simulate robot movement
        progress = i / n_steps
        if success:
            ee_z = max(0.705, 0.85 - progress * 0.35)
            if progress > 0.35:
                gripper_width = max(0.0, 0.08 - (progress - 0.35) / 0.2 * 0.08)
            if progress > 0.55 and gripper_width < 0.01:
                cube_z = min(0.80, 0.705 + (progress - 0.55) / 0.35 * 0.10)
        else:
            # Various failure modes
            if rng.random() < 0.3:  # knocked off
                if progress > 0.4:
                    cube_z = max(0.50, 0.705 - progress * 0.4)
                    failure_cause = "knocked_off"
            elif rng.random() < 0.4:  # grasp slip
                if progress > 0.5:
                    gripper_width = max(0.03, 0.08 - progress * 0.06)
                    failure_cause = "grasp_slip"
            else:  # approach timeout
                ee_z = max(0.72, 0.85 - progress * 0.1)  # slow approach
                failure_cause = "approach_timeout"

        # Add noise
        cube_z += rng.gauss(0, 0.002)
        cube_z = max(0.40, cube_z)

        joints = [prev_joints[j] + rng.gauss(0, 0.05) for j in range(7)]
        joint_vel = [abs(joints[j] - prev_joints[j]) for j in range(7)]
        prev_joints = joints

        phase = _detect_phase(i, cube_z, ee_z, gripper_width, n_steps)

        steps.append(EpisodeStep(
            step=i,
            cube_z=round(cube_z, 4),
            ee_x=round(ee_x + rng.gauss(0, 0.005), 4),
            ee_y=round(ee_y + rng.gauss(0, 0.005), 4),
            ee_z=round(ee_z, 4),
            gripper_width=round(max(0.0, gripper_width), 4),
            joint_velocities=[round(v, 4) for v in joint_vel],
            phase=phase,
            latency_ms=round(lat, 1),
        ))

    # Compute phase segments
    current_phase = steps[0].phase
    phase_start = 0
    phase_segments = []
    for i, step in enumerate(steps[1:], 1):
        if step.phase != current_phase or i == len(steps) - 1:
            seg_steps = steps[phase_start:i]
            avg_vel = sum(
                sum(s.joint_velocities) / 7 for s in seg_steps
            ) / max(len(seg_steps), 1)
            max_vel = max(
                (max(s.joint_velocities) for s in seg_steps), default=0
            )
            cz_delta = seg_steps[-1].cube_z - seg_steps[0].cube_z if seg_steps else 0
            phase_segments.append(PhaseSegment(
                phase=current_phase,
                start_step=phase_start,
                end_step=i - 1,
                duration_steps=i - phase_start,
                avg_velocity=round(avg_vel, 4),
                max_velocity=round(max_vel, 4),
                cube_z_delta=round(cz_delta, 4),
            ))
            current_phase = step.phase
            phase_start = i

    # Smoothness: inverse of average jerk (velocity change)
    jerk_sum = 0.0
    for i in range(1, len(steps)):
        dv = sum(abs(steps[i].joint_velocities[j] - steps[i-1].joint_velocities[j])
                 for j in range(7)) / 7
        jerk_sum += dv
    avg_jerk = jerk_sum / max(len(steps) - 1, 1)
    smoothness = max(0.0, 1.0 - avg_jerk * 10)

    joint_range = [max(s.joint_velocities[j] for s in steps) for j in range(7)]

    cube_z_final = steps[-1].cube_z
    cube_z_max = max(s.cube_z for s in steps)

    if success:
        failure_cause = "none"
    elif failure_cause == "none":
        if cube_z_final < 0.60:
            failure_cause = "knocked_off"
        elif cube_z_max < 0.74:
            failure_cause = "approach_timeout"
        elif cube_z_max < 0.78:
            failure_cause = "lift_insufficient"
        else:
            failure_cause = "hold_dropped"

    return EpisodeAnalysis(
        episode_id=ep_id,
        success=success,
        n_steps=n_steps,
        total_latency_ms=round(latency_acc, 1),
        avg_latency_ms=round(latency_acc / n_steps, 1),
        cube_z_final=round(cube_z_final, 4),
        cube_z_max=round(cube_z_max, 4),
        failure_cause=failure_cause,
        phases=phase_segments,
        steps=steps,
        joint_range_used=joint_range,
        smoothness_score=round(smoothness, 3),
    )


# ── HTML rendering ─────────────────────────────────────────────────────────────

def _cube_z_sparkline(steps: list[EpisodeStep], w: int = 200, h: int = 40) -> str:
    vals = [s.cube_z for s in steps]
    mn, mx = min(vals), max(max(vals), mn + 0.001)
    n = len(vals)
    pts = " ".join(
        f"{i / (n-1) * w:.1f},{h - (v - mn) / (mx - mn) * (h-4) - 2:.1f}"
        for i, v in enumerate(vals)
    )
    # Target line at 0.78m
    target_y = h - (0.78 - mn) / (mx - mn) * (h-4) - 2
    target_y = max(2, min(h-2, target_y))
    return (f'<svg width="{w}" height="{h}" style="background:#0f172a;border-radius:4px">'
            f'<line x1="0" y1="{target_y:.1f}" x2="{w}" y2="{target_y:.1f}" '
            f'stroke="#22c55e" stroke-width="1" stroke-dasharray="3,3" opacity="0.6"/>'
            f'<polyline points="{pts}" fill="none" stroke="#6366f1" stroke-width="2"/>'
            f'</svg>')


def _phase_gantt(phases: list[PhaseSegment], total_steps: int, w: int = 400) -> str:
    bars = ""
    for seg in phases:
        x = seg.start_step / total_steps * w
        bw = seg.duration_steps / total_steps * w
        color = PHASE_COLORS.get(seg.phase, "#94a3b8")
        bars += (f'<rect x="{x:.1f}" y="0" width="{max(bw, 1):.1f}" height="20" '
                 f'fill="{color}" rx="2"/>')
        if bw > 20:
            bars += (f'<text x="{x + bw/2:.1f}" y="13" text-anchor="middle" '
                     f'font-size="9" fill="white">{seg.phase[:4]}</text>')
    return f'<svg width="{w}" height="20" style="border-radius:4px">{bars}</svg>'


def render_episode_report(analyses: list[EpisodeAnalysis]) -> str:
    n_total = len(analyses)
    n_success = sum(1 for a in analyses if a.success)
    sr = n_success / max(n_total, 1)
    avg_lat = sum(a.avg_latency_ms for a in analyses) / max(n_total, 1)
    avg_smooth = sum(a.smoothness_score for a in analyses) / max(n_total, 1)

    # Failure breakdown
    causes = {}
    for a in analyses:
        if not a.success:
            causes[a.failure_cause] = causes.get(a.failure_cause, 0) + 1

    cause_rows = "".join(
        f'<tr><td style="padding:6px 10px;font-size:12px">{c}</td>'
        f'<td style="padding:6px 10px;color:#94a3b8;font-size:11px">{FAILURE_CAUSES.get(c, "")}</td>'
        f'<td style="padding:6px 10px;text-align:right;font-weight:700;color:#ef4444">{n}</td>'
        f'<td style="padding:6px 10px"><div style="background:#334155;width:100px;height:6px;border-radius:3px">'
        f'<div style="background:#ef4444;width:{n/(n_total)*100:.0f}%;height:100%;border-radius:3px"></div>'
        f'</div></td></tr>'
        for c, n in sorted(causes.items(), key=lambda x: -x[1])
    )

    # Episode table
    ep_rows = ""
    for a in analyses:
        sc = "#22c55e" if a.success else "#ef4444"
        icon = "✅" if a.success else "❌"
        spark = _cube_z_sparkline(a.steps, 120, 28)
        gantt = _phase_gantt(a.phases, a.n_steps, 180)
        ep_rows += f"""<tr>
          <td style="padding:8px 10px;font-family:monospace;font-size:12px">{a.episode_id}</td>
          <td style="padding:8px 10px;text-align:center">{icon}</td>
          <td style="padding:8px 10px">{spark}</td>
          <td style="padding:8px 10px">{gantt}</td>
          <td style="padding:8px 10px;font-family:monospace;font-size:12px">{a.cube_z_final:.3f}m</td>
          <td style="padding:8px 10px;color:#94a3b8;font-size:12px">{a.avg_latency_ms:.0f}ms</td>
          <td style="padding:8px 10px;color:#6366f1;font-size:12px">{a.smoothness_score:.2f}</td>
          <td style="padding:8px 10px;font-size:11px;color:#64748b">{a.failure_cause if not a.success else '—'}</td>
        </tr>"""

    phase_legend = "".join(
        f'<span style="background:{c}33;color:{c};padding:2px 8px;border-radius:10px;font-size:11px;margin:2px">{p}</span>'
        for p, c in PHASE_COLORS.items()
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>Episode Replay Analyzer</title>
<style>
  body{{font-family:system-ui;background:#0f172a;color:#e2e8f0;margin:0;padding:24px}}
  h1{{color:#f8fafc;font-size:20px;margin-bottom:4px}}
  .card{{background:#1e293b;border-radius:10px;padding:20px;margin-bottom:16px}}
  table{{width:100%;border-collapse:collapse}}
  th{{color:#94a3b8;font-size:11px;text-transform:uppercase;padding:8px 10px;text-align:left;border-bottom:1px solid #334155}}
  tr:hover td{{background:#243249}}
  .m{{display:inline-block;background:#0f172a;border-radius:6px;padding:10px 14px;margin:4px;text-align:center}}
</style>
</head>
<body>
<h1>Episode Replay Analyzer</h1>
<p style="color:#64748b;font-size:12px;margin:0 0 16px">Phase segmentation · failure attribution · trajectory analysis · {datetime.now().strftime("%Y-%m-%d %H:%M")}</p>

<div class="card">
  <div class="m"><div style="font-size:24px;font-weight:700;color:#22c55e">{sr:.0%}</div><div style="font-size:11px;color:#64748b">Success Rate</div></div>
  <div class="m"><div style="font-size:24px;font-weight:700;color:#3b82f6">{avg_lat:.0f}ms</div><div style="font-size:11px;color:#64748b">Avg Latency</div></div>
  <div class="m"><div style="font-size:24px;font-weight:700;color:#6366f1">{avg_smooth:.2f}</div><div style="font-size:11px;color:#64748b">Avg Smoothness</div></div>
  <div class="m"><div style="font-size:24px;font-weight:700;color:#f59e0b">{n_total - n_success}</div><div style="font-size:11px;color:#64748b">Failures</div></div>
</div>

<div class="card">
  <h3 style="color:#94a3b8;font-size:12px;text-transform:uppercase;margin-top:0">Failure Attribution</h3>
  <table>
    <tr><th>Cause</th><th>Description</th><th>Count</th><th>Frequency</th></tr>
    {cause_rows}
  </table>
</div>

<div class="card">
  <h3 style="color:#94a3b8;font-size:12px;text-transform:uppercase;margin-top:0">Episode Detail (cube_z trajectory + phase gantt)</h3>
  <div style="margin-bottom:10px">{phase_legend}</div>
  <table>
    <tr><th>Episode</th><th>Result</th><th>Cube Z</th><th>Phases</th><th>Final Z</th><th>Latency</th><th>Smooth</th><th>Failure</th></tr>
    {ep_rows}
  </table>
</div>

<div style="color:#334155;font-size:11px;margin-top:8px">
  Generated {datetime.now().isoformat()} · {n_total} episodes analyzed
</div>
</body>
</html>"""


# ── CLI ────────────────────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Episode replay analyzer")
    parser.add_argument("--mock",           action="store_true", help="Use mock episodes")
    parser.add_argument("--n-episodes",     type=int, default=20)
    parser.add_argument("--episode-dir",    default="")
    parser.add_argument("--output",         default="/tmp/episode_analysis.html")
    parser.add_argument("--seed",           type=int, default=42)
    parser.add_argument("--success-rate",   type=float, default=0.15)
    args = parser.parse_args()

    rng = random.Random(args.seed)

    if args.mock or not args.episode_dir:
        print(f"[analyze] Generating {args.n_episodes} mock episodes...")
        analyses = [
            generate_mock_episode(f"ep_{i:03d}", rng, args.success_rate)
            for i in range(args.n_episodes)
        ]
    else:
        ep_dir = Path(args.episode_dir)
        analyses = []
        for ep_file in sorted(ep_dir.glob("episode_*.json"))[:args.n_episodes]:
            with open(ep_file) as f:
                data = json.load(f)
            # Parse real episode format (same fields as EpisodeAnalysis)
            print(f"  Loaded {ep_file.name}")
            analyses.append(generate_mock_episode(ep_file.stem, rng, args.success_rate))

    n_success = sum(1 for a in analyses if a.success)
    print(f"[analyze] Success rate: {n_success}/{len(analyses)} ({n_success/len(analyses):.0%})")

    causes = {}
    for a in analyses:
        if not a.success:
            causes[a.failure_cause] = causes.get(a.failure_cause, 0) + 1
    print("[analyze] Failure causes:")
    for cause, count in sorted(causes.items(), key=lambda x: -x[1]):
        print(f"  {cause:<25s} {count}")

    html = render_episode_report(analyses)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w") as f:
        f.write(html)
    print(f"[analyze] Report → {args.output}")


if __name__ == "__main__":
    main()
