#!/usr/bin/env python3
"""
policy_rollout_debugger.py — Step-by-step GR00T policy rollout inspector.

Replays a saved episode and shows what the policy "sees" at each step —
joint states, action chunk predictions, phase transitions, and failure signals.
Used to diagnose why a policy fails on a specific episode.

Usage:
    python src/eval/policy_rollout_debugger.py --mock --steps 60
    python src/eval/policy_rollout_debugger.py \
        --episode-file /tmp/eval_1000demo/episodes/ep_005.json \
        --output /tmp/rollout_debug_ep005.html
"""

import argparse
import json
import math
import random
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ── Data structures ───────────────────────────────────────────────────────────

@dataclass
class RolloutStep:
    step: int
    timestamp_ms: float
    joint_states: list[float]       # 9-DOF
    action_chunk: list[list[float]] # 16 steps × 9 DOF (full chunk from GR00T)
    applied_action: list[float]     # chunk[0] — what was actually applied
    cube_z: float
    phase: str                      # approach/grasp/lift/hold/done/failed
    policy_latency_ms: float
    notes: str = ""


@dataclass
class RolloutEpisode:
    episode_id: str
    checkpoint: str
    success: bool
    n_steps: int
    steps: list[RolloutStep] = field(default_factory=list)
    failure_step: Optional[int] = None
    failure_reason: str = ""


# ── Phase detection ───────────────────────────────────────────────────────────

LIFT_THRESHOLD = 0.78   # meters above floor
GRASP_THRESHOLD = 0.73  # cube_z when gripper closes on cube
TABLE_Z = 0.72

def detect_phase(cube_z: float, step: int, prev_phase: str) -> str:
    if cube_z >= LIFT_THRESHOLD:
        return "done"
    if cube_z >= GRASP_THRESHOLD and prev_phase in ("approach", "grasp"):
        return "grasp"
    if cube_z >= GRASP_THRESHOLD and prev_phase in ("grasp", "lift"):
        return "lift"
    if cube_z >= GRASP_THRESHOLD:
        return "lift"
    if step < 15:
        return "approach"
    return "approach"


def detect_failure(steps: list[RolloutStep]) -> tuple[Optional[int], str]:
    """Returns (failure_step, reason) or (None, '')."""
    if not steps:
        return None, ""
    last = steps[-1]
    if last.cube_z < LIFT_THRESHOLD:
        # Find where it went wrong
        max_z_step = max(steps, key=lambda s: s.cube_z)
        if max_z_step.cube_z < GRASP_THRESHOLD:
            return 0, "never_grasped"
        # Found grasp but dropped
        for i in range(len(steps) - 1):
            if steps[i].cube_z > steps[i+1].cube_z + 0.02:
                return i, "dropped_during_lift"
        return len(steps) - 1, "insufficient_lift"
    return None, ""


# ── Mock episode generator ────────────────────────────────────────────────────

def generate_mock_episode(ep_id: str = "mock_001",
                           success: bool = False,
                           n_steps: int = 60,
                           seed: int = 42) -> RolloutEpisode:
    rng = random.Random(seed)

    # Simulate cube_z trajectory
    cube_zs = []
    z = TABLE_Z
    for i in range(n_steps):
        if i < 10:  # approach
            z += rng.gauss(0, 0.002)
        elif i < 20:  # grasp attempt
            z += rng.uniform(0, 0.003)
        elif i < 40:  # lift phase
            if success:
                z += rng.uniform(0.005, 0.012)
            else:
                z += rng.gauss(0.002, 0.004)
        else:  # hold
            z += rng.gauss(0, 0.001)
        z = max(TABLE_Z - 0.05, min(z, 0.95))
        cube_zs.append(round(z, 4))

    if success:
        # Force success at step 45
        for i in range(40, n_steps):
            cube_zs[i] = min(0.90, LIFT_THRESHOLD + (i - 40) * 0.003 + rng.gauss(0, 0.001))

    steps = []
    prev_phase = "approach"
    for i, cz in enumerate(cube_zs):
        joint_states = [rng.gauss(0, 0.4) for _ in range(9)]
        # 16-step action chunk: small deltas around current joints
        action_chunk = [[joint_states[j] + rng.gauss(0, 0.05) for j in range(9)]
                        for _ in range(16)]
        applied = action_chunk[0]
        phase = detect_phase(cz, i, prev_phase)
        prev_phase = phase
        latency = rng.gauss(226, 15)

        steps.append(RolloutStep(
            step=i,
            timestamp_ms=i * (latency + 10),
            joint_states=joint_states,
            action_chunk=action_chunk,
            applied_action=applied,
            cube_z=cz,
            phase=phase,
            policy_latency_ms=round(latency, 1),
        ))

    failure_step, failure_reason = detect_failure(steps)
    return RolloutEpisode(
        episode_id=ep_id,
        checkpoint="/tmp/finetune_1000_5k/checkpoint-5000",
        success=success,
        n_steps=n_steps,
        steps=steps,
        failure_step=failure_step,
        failure_reason=failure_reason,
    )


# ── Terminal inspector ────────────────────────────────────────────────────────

PHASE_COLOR = {
    "approach": "\033[94m",
    "grasp":    "\033[93m",
    "lift":     "\033[92m",
    "hold":     "\033[92m",
    "done":     "\033[32m",
    "failed":   "\033[91m",
}
RESET = "\033[0m"

def print_step(s: RolloutStep, verbose: bool = False) -> None:
    col = PHASE_COLOR.get(s.phase, "")
    bar_len = int((s.cube_z - TABLE_Z + 0.05) / 0.28 * 20)
    bar_len = max(0, min(20, bar_len))
    bar = "█" * bar_len + "░" * (20 - bar_len)
    lift_ok = "✓" if s.cube_z >= LIFT_THRESHOLD else " "
    print(f"  [{s.step:3d}] {col}{s.phase:<8}{RESET} "
          f"cube_z={s.cube_z:.4f}m {lift_ok} |{bar}| "
          f"lat={s.policy_latency_ms:.0f}ms"
          + (f"  ← {s.notes}" if s.notes else ""))
    if verbose:
        joints = " ".join(f"{v:+.2f}" for v in s.joint_states[:6])
        print(f"       joints[0:6]: [{joints}]")
        chunk_norms = [math.sqrt(sum(a**2 for a in row)) for row in s.action_chunk[:4]]
        print(f"       chunk norms (first 4 steps): {[round(n,3) for n in chunk_norms]}")


def inspect_terminal(ep: RolloutEpisode, verbose: bool = False, slow: bool = False) -> None:
    print(f"\n\033[1mPolicy Rollout Debugger — {ep.episode_id}\033[0m")
    print(f"  Checkpoint: {ep.checkpoint}")
    print(f"  Steps: {ep.n_steps}  |  Success: {'YES' if ep.success else 'NO'}")
    if ep.failure_reason:
        print(f"  Failure: step {ep.failure_step} — {ep.failure_reason}\n")
    else:
        print()

    phase_changes = []
    prev = ""
    for s in ep.steps:
        if s.phase != prev:
            phase_changes.append((s.step, s.phase))
            prev = s.phase

    print(f"  Phase transitions: " +
          " → ".join(f"{p}@{i}" for i, p in phase_changes))
    print()

    for s in ep.steps:
        # Annotate failure step
        if s.step == ep.failure_step:
            s.notes = f"FAILURE ({ep.failure_reason})"
        print_step(s, verbose=verbose)
        if slow:
            time.sleep(0.05)

    # Summary stats
    avg_lat = sum(s.policy_latency_ms for s in ep.steps) / len(ep.steps)
    max_z = max(s.cube_z for s in ep.steps)
    print(f"\n  Avg latency: {avg_lat:.0f}ms  |  Max cube_z: {max_z:.4f}m  |  "
          f"Lift threshold: {LIFT_THRESHOLD}m")
    print(f"  {'✓ SUCCESS' if ep.success else '✗ FAILURE: ' + ep.failure_reason}\n")


# ── HTML report ───────────────────────────────────────────────────────────────

def render_html(ep: RolloutEpisode) -> str:
    # cube_z sparkline SVG
    zs = [s.cube_z for s in ep.steps]
    w, h = 700, 140
    z_min = min(zs) - 0.01
    z_max = max(zs) + 0.01
    x_scale = (w - 40) / max(len(zs) - 1, 1)
    y_scale = (h - 30) / (z_max - z_min)

    pts = " ".join(
        f"{20 + i * x_scale:.1f},{h-10-(z-z_min)*y_scale:.1f}"
        for i, z in enumerate(zs)
    )
    # Lift threshold line
    thr_y = h - 10 - (LIFT_THRESHOLD - z_min) * y_scale
    svg = (
        f'<svg width="{w}" height="{h}" style="background:#0f172a;border-radius:6px">'
        f'<line x1="20" y1="{thr_y:.1f}" x2="{w}" y2="{thr_y:.1f}" '
        f'stroke="#22c55e" stroke-width="1" stroke-dasharray="4,3"/>'
        f'<text x="22" y="{thr_y-3:.1f}" fill="#22c55e" font-size="10">lift threshold {LIFT_THRESHOLD}m</text>'
        f'<polyline points="{pts}" fill="none" stroke="#C74634" stroke-width="2"/>'
    )
    # Mark failure step
    if ep.failure_step is not None:
        fx = 20 + ep.failure_step * x_scale
        fy = h - 10 - (zs[ep.failure_step] - z_min) * y_scale
        svg += f'<circle cx="{fx:.1f}" cy="{fy:.1f}" r="6" fill="#ef4444"/>'
        svg += f'<text x="{fx+8:.1f}" y="{fy+4:.1f}" fill="#ef4444" font-size="10">failure</text>'
    svg += '</svg>'

    # Phase color map
    PHASE_COLORS_CSS = {
        "approach": "#3b82f6",
        "grasp": "#f59e0b",
        "lift": "#22c55e",
        "hold": "#22c55e",
        "done": "#10b981",
        "failed": "#ef4444",
    }

    # Action chunk heatmap for a few interesting steps (step 0, 20, failure, last)
    interesting_steps = [0, len(ep.steps)//3, len(ep.steps)*2//3, len(ep.steps)-1]
    if ep.failure_step:
        interesting_steps.append(ep.failure_step)
    interesting_steps = sorted(set(interesting_steps))

    chunk_html = ""
    for si in interesting_steps:
        if si >= len(ep.steps):
            continue
        s = ep.steps[si]
        # 16×9 heatmap cells
        cells = ""
        for row in s.action_chunk:
            for val in row:
                norm = (val + 1.5) / 3.0  # normalize to 0-1
                r = int(255 * min(1, max(0, 2 * norm - 1)))
                b = int(255 * min(1, max(0, 2 * (1 - norm))))
                cells += f'<td style="background:rgb({r},50,{b});width:14px;height:10px"></td>'
            cells += "</tr><tr>"
        col = PHASE_COLORS_CSS.get(s.phase, "#94a3b8")
        chunk_html += f"""
        <div style="display:inline-block;margin:8px;vertical-align:top">
          <div style="color:{col};font-size:11px;margin-bottom:4px">
            step {s.step} · {s.phase} · cube_z={s.cube_z:.3f}m · {s.policy_latency_ms:.0f}ms
          </div>
          <table style="border-collapse:collapse;font-size:0"><tr>{cells}</tr></table>
        </div>"""

    # Phase timeline
    timeline = ""
    prev_phase = ""
    for s in ep.steps:
        if s.phase != prev_phase:
            col = PHASE_COLORS_CSS.get(s.phase, "#94a3b8")
            timeline += f'<span style="background:{col};color:#fff;padding:2px 6px;margin:2px;border-radius:3px;font-size:11px">{s.phase}@{s.step}</span>'
            prev_phase = s.phase

    sr_col = "#22c55e" if ep.success else "#ef4444"
    avg_lat = sum(s.policy_latency_ms for s in ep.steps) / len(ep.steps)
    max_z = max(s.cube_z for s in ep.steps)

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<title>Policy Rollout Debugger — {ep.episode_id}</title>
<style>
body{{background:#1e293b;color:#e2e8f0;font-family:monospace;margin:0;padding:24px}}
h1{{color:#C74634;margin:0 0 4px}}
.meta{{color:#94a3b8;font-size:12px;margin-bottom:20px}}
.stat{{display:inline-block;background:#0f172a;border-radius:6px;padding:10px 18px;margin:4px}}
.stat .val{{font-size:28px;font-weight:bold}}
.section{{margin-top:20px}}
h3{{color:#94a3b8;font-size:11px;text-transform:uppercase;margin:0 0 8px}}
</style></head>
<body>
<h1>Policy Rollout Debugger — {ep.episode_id}</h1>
<div class="meta">Checkpoint: {ep.checkpoint} · Steps: {ep.n_steps}</div>

<div>
  <div class="stat"><div style="color:#94a3b8;font-size:11px">Result</div>
    <div class="val" style="color:{sr_col}">{'SUCCESS' if ep.success else 'FAILURE'}</div>
    <div style="color:#64748b;font-size:11px">{ep.failure_reason or 'cube lifted ≥0.78m'}</div>
  </div>
  <div class="stat"><div style="color:#94a3b8;font-size:11px">Max cube_z</div>
    <div class="val">{max_z:.3f}m</div></div>
  <div class="stat"><div style="color:#94a3b8;font-size:11px">Avg Latency</div>
    <div class="val">{avg_lat:.0f}ms</div></div>
  <div class="stat"><div style="color:#94a3b8;font-size:11px">Failure Step</div>
    <div class="val" style="color:#ef4444">{ep.failure_step if ep.failure_step is not None else '—'}</div></div>
</div>

<div class="section"><h3>Phase Timeline</h3>{timeline}</div>
<div class="section"><h3>cube_z Trajectory</h3>{svg}</div>
<div class="section"><h3>Action Chunk Heatmaps (16 steps × 9 DOF — red=positive, blue=negative)</h3>
  {chunk_html}
</div>

<div style="color:#64748b;font-size:11px;margin-top:20px">
  OCI A100 GPU4 (138.1.153.110) · GR00T N1.6-3B fine-tuned checkpoint
</div>
</body></html>"""


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Policy rollout step-by-step debugger")
    parser.add_argument("--mock",         action="store_true", default=True)
    parser.add_argument("--steps",        type=int, default=60)
    parser.add_argument("--success",      action="store_true", help="Mock a successful episode")
    parser.add_argument("--episode-file", help="Path to episode JSON")
    parser.add_argument("--ep-id",        default="mock_001")
    parser.add_argument("--output",       help="HTML output path")
    parser.add_argument("--verbose",      action="store_true", help="Print joint states + chunk norms")
    parser.add_argument("--slow",         action="store_true", help="50ms delay between steps (live feel)")
    parser.add_argument("--seed",         type=int, default=42)
    args = parser.parse_args()

    if args.episode_file:
        data = json.loads(Path(args.episode_file).read_text())
        steps = [RolloutStep(**s) for s in data["steps"]]
        ep = RolloutEpisode(
            episode_id=data["episode_id"],
            checkpoint=data.get("checkpoint", ""),
            success=data["success"],
            n_steps=data["n_steps"],
            steps=steps,
        )
        ep.failure_step, ep.failure_reason = detect_failure(steps)
    else:
        ep = generate_mock_episode(
            ep_id=args.ep_id,
            success=args.success,
            n_steps=args.steps,
            seed=args.seed,
        )

    inspect_terminal(ep, verbose=args.verbose, slow=args.slow)

    out = args.output or f"/tmp/rollout_debug_{ep.episode_id}.html"
    html = render_html(ep)
    Path(out).write_text(html)
    print(f"  HTML report → {out}")


if __name__ == "__main__":
    main()
