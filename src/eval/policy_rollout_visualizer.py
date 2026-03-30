#!/usr/bin/env python3
"""
Policy rollout visualization for GR00T episodes.
Shows joint trajectories, end-effector paths, and failure mode analysis.

Usage:
    python policy_rollout_visualizer.py --mock --output /tmp/policy_rollout_visualizer.html --seed 42
"""

import argparse
import math
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class JointFrame:
    t: float
    joints: List[float]      # 7-DOF joint angles (radians)
    ee_pos: List[float]      # [x, y, z] end-effector position (metres)
    gripper: float           # 0.0 (open) to 1.0 (closed)
    is_key_frame: bool


@dataclass
class RolloutEpisode:
    episode_id: str
    policy_name: str
    task_name: str
    success: bool
    n_frames: int
    duration_s: float
    frames: List[JointFrame]
    failure_mode: Optional[str]
    key_events: List[Dict]


@dataclass
class VisualizerReport:
    n_episodes: int
    n_policies: int
    success_rate_by_policy: Dict[str, float]
    failure_mode_breakdown: Dict[str, int]
    results: List[RolloutEpisode]


# ---------------------------------------------------------------------------
# Simulation constants
# ---------------------------------------------------------------------------

POLICIES = [
    ("bc_baseline",      0.50),
    ("dagger_run5",      0.65),
    ("dagger_run9",      0.78),
    ("dagger_run9_lora", 0.80),
]

TASKS = ["pick_and_place", "door_opening"]

FAILURE_MODES = [
    "missed_grasp",
    "dropped_object",
    "workspace_limit",
    "timeout",
    "wrong_orientation",
]

N_FRAMES      = 60     # 20 Hz × 3 s
DURATION_S    = 3.0
N_EPS_POLICY  = 5      # episodes per (policy, task)


# ---------------------------------------------------------------------------
# Simulation helpers
# ---------------------------------------------------------------------------

def _smooth(t: float, freq: float, phase: float, amp: float) -> float:
    return amp * math.sin(freq * math.pi * t + phase)


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _simulate_episode(
    policy_name: str,
    task_name: str,
    success: bool,
    failure_mode: Optional[str],
    ep_seed: int,
) -> List[JointFrame]:
    rng = random.Random(ep_seed)
    frames: List[JointFrame]= []

    # Per-joint base frequencies — slight variation per task
    task_offset = 0.3 if task_name == "door_opening" else 0.0
    joint_freqs = [1.2 + i * 0.25 + task_offset for i in range(7)]
    joint_phases = [rng.uniform(0, math.pi) for _ in range(7)]

    # EE path parameters
    ee_start = [rng.uniform(-0.05, 0.05), rng.uniform(-0.05, 0.05), 0.30]
    ee_target = [0.45, 0.10, 0.05] if task_name == "pick_and_place" else [0.55, 0.00, 0.25]

    # Failure injection frame (for non-success episodes)
    fail_frame = int(N_FRAMES * rng.uniform(0.35, 0.65))

    for f in range(N_FRAMES):
        t = f / (N_FRAMES - 1)  # 0 → 1

        # ---- joint trajectories ----
        if success:
            noise_amp = 0.02
            joints = [
                _smooth(t, joint_freqs[i], joint_phases[i], 1.1) + rng.gauss(0, noise_amp)
                for i in range(7)
            ]
        else:
            # Jerky motion: amplified noise after fail_frame
            noise_amp = 0.02 if f < fail_frame else 0.18
            jerk = 0.0 if f < fail_frame else _smooth(t, 8.0, rng.random(), 0.4)
            joints = [
                _smooth(t, joint_freqs[i], joint_phases[i], 1.1) + rng.gauss(0, noise_amp) + jerk
                for i in range(7)
            ]

        # ---- end-effector XY path ----
        if success:
            # Smooth arc towards target
            progress = t
            ee_x = ee_start[0] + (ee_target[0] - ee_start[0]) * progress + _smooth(t, 2.0, 0.5, 0.03)
            ee_y = ee_start[1] + (ee_target[1] - ee_start[1]) * progress + _smooth(t, 1.5, 1.0, 0.02)
            ee_z = ee_start[2] + (ee_target[2] - ee_start[2]) * progress + _smooth(t, 3.0, 0.0, 0.04)
        else:
            if f < fail_frame:
                progress = t / (fail_frame / (N_FRAMES - 1))
                progress = _clamp(progress, 0.0, 1.0)
                ee_x = ee_start[0] + (ee_target[0] - ee_start[0]) * progress * 0.6 + _smooth(t, 2.0, 0.5, 0.03)
                ee_y = ee_start[1] + (ee_target[1] - ee_start[1]) * progress * 0.6 + _smooth(t, 1.5, 1.0, 0.02)
                ee_z = ee_start[2] + _smooth(t, 3.0, 0.0, 0.04)
            else:
                # Drift away after failure
                drift_t = (f - fail_frame) / max(1, N_FRAMES - fail_frame)
                ee_x = ee_start[0] + 0.3 * 0.6 + rng.gauss(0, 0.04) * drift_t * 4
                ee_y = ee_start[1] + 0.1 * 0.6 + rng.gauss(0, 0.04) * drift_t * 4
                ee_z = max(0.0, ee_start[2] - drift_t * 0.25 + rng.gauss(0, 0.01))

        # ---- gripper ----
        if success:
            if t < 0.25:
                gripper = 0.0
            elif t < 0.45:
                gripper = (t - 0.25) / 0.20
            elif t < 0.80:
                gripper = 1.0
            else:
                gripper = max(0.0, 1.0 - (t - 0.80) / 0.20)
        else:
            if f < fail_frame:
                gripper = _clamp(t / 0.45, 0.0, 1.0) if t < 0.45 else 1.0
            else:
                gripper = max(0.0, 1.0 - (f - fail_frame) / 10.0)

        # ---- key frame detection ----
        is_key = f in {0, fail_frame if not success else N_FRAMES - 1, N_FRAMES // 3, 2 * N_FRAMES // 3}

        frames.append(JointFrame(
            t=round(t * DURATION_S, 4),
            joints=[round(j, 5) for j in joints],
            ee_pos=[round(ee_x, 4), round(ee_y, 4), round(ee_z, 4)],
            gripper=round(_clamp(gripper, 0.0, 1.0), 4),
            is_key_frame=is_key,
        ))

    return frames


def _build_key_events(success: bool, failure_mode: Optional[str], ep_seed: int) -> List[Dict]:
    rng = random.Random(ep_seed)
    events: List[Dict] = [
        {"frame": 0,  "t": 0.0,  "event": "approach",      "detail": "EE moving toward target"},
        {"frame": 15, "t": 0.75, "event": "grasp_attempt",  "detail": "gripper closing"},
        {"frame": 30, "t": 1.50, "event": "lift",            "detail": "object lifted"},
    ]
    if success:
        events.append({"frame": N_FRAMES - 1, "t": DURATION_S, "event": "success", "detail": "task completed"})
    else:
        fail_frame = int(N_FRAMES * rng.uniform(0.35, 0.65))
        fail_t = round(fail_frame / (N_FRAMES - 1) * DURATION_S, 2)
        events.append({"frame": fail_frame, "t": fail_t, "event": "failure",
                       "detail": failure_mode or "unknown"})
    return events


def simulate_all_episodes(rng_seed: int) -> List[RolloutEpisode]:
    rng = random.Random(rng_seed)
    episodes: List[RolloutEpisode] = []

    for pol_name, sr in POLICIES:
        for task in TASKS:
            for ep_idx in range(N_EPS_POLICY):
                ep_seed = rng.randint(0, 99999)
                success = rng.random() < sr
                failure_mode = None if success else rng.choice(FAILURE_MODES)
                frames = _simulate_episode(pol_name, task, success, failure_mode, ep_seed)
                key_events = _build_key_events(success, failure_mode, ep_seed)

                episodes.append(RolloutEpisode(
                    episode_id=f"{pol_name}__{task}__ep{ep_idx:02d}",
                    policy_name=pol_name,
                    task_name=task,
                    success=success,
                    n_frames=N_FRAMES,
                    duration_s=DURATION_S,
                    frames=frames,
                    failure_mode=failure_mode,
                    key_events=key_events,
                ))

    return episodes


def build_report(episodes: List[RolloutEpisode]) -> VisualizerReport:
    policies = sorted({ep.policy_name for ep in episodes})
    sr_by_policy: Dict[str, float] = {}
    for pol in policies:
        pol_eps = [ep for ep in episodes if ep.policy_name == pol]
        sr_by_policy[pol] = sum(1 for ep in pol_eps if ep.success) / len(pol_eps) if pol_eps else 0.0

    failure_breakdown: Dict[str, int] = {}
    for ep in episodes:
        if ep.failure_mode:
            failure_breakdown[ep.failure_mode] = failure_breakdown.get(ep.failure_mode, 0) + 1

    return VisualizerReport(
        n_episodes=len(episodes),
        n_policies=len(policies),
        success_rate_by_policy=sr_by_policy,
        failure_mode_breakdown=failure_breakdown,
        results=episodes,
    )


# ---------------------------------------------------------------------------
# Print SR matrix to stdout
# ---------------------------------------------------------------------------

def print_sr_matrix(episodes: List[RolloutEpisode]) -> None:
    policies = [p for p, _ in POLICIES]
    tasks = TASKS

    col_w = 22
    header = f"{'Policy':<20}" + "".join(f"{t:<{col_w}}" for t in tasks) + f"{'Overall':<{col_w}}"
    sep = "-" * len(header)
    print("\nPolicy x Task Success Rate Matrix")
    print(sep)
    print(header)
    print(sep)

    for pol in policies:
        row = f"{pol:<20}"
        all_pol = [ep for ep in episodes if ep.policy_name == pol]
        for task in tasks:
            subset = [ep for ep in all_pol if ep.task_name == task]
            sr = sum(1 for ep in subset if ep.success) / len(subset) if subset else 0.0
            row += f"{sr*100:>5.1f}%{'':<{col_w - 7}}"
        overall_sr = sum(1 for ep in all_pol if ep.success) / len(all_pol) if all_pol else 0.0
        row += f"{overall_sr*100:>5.1f}%"
        print(row)

    print(sep)
    print()


# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------

def _polyline(pts: List[tuple], color: str, sw: int = 2, dash: str = "") -> str:
    pts_str = " ".join(f"{x:.2f},{y:.2f}" for x, y in pts)
    dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
    return (f'<polyline points="{pts_str}" fill="none" stroke="{color}" '
            f'stroke-width="{sw}" stroke-linejoin="round"{dash_attr}/>')


def _norm_to_svg(vals: List[float], W: int, H: int,
                 vmin: Optional[float] = None, vmax: Optional[float] = None) -> List[tuple]:
    mn = vmin if vmin is not None else min(vals)
    mx = vmax if vmax is not None else max(vals)
    rng = mx - mn if mx != mn else 1.0
    n = len(vals)
    pts = []
    for i, v in enumerate(vals):
        x = i / (n - 1) * W
        y = H - ((v - mn) / rng) * (H - 6) - 3
        pts.append((x, y))
    return pts


def _svg_legend(items: List[tuple], x0: int, y0: int) -> str:
    """items: list of (color, label)"""
    parts = []
    for i, (color, label) in enumerate(items):
        y = y0 + i * 16
        parts.append(f'<rect x="{x0}" y="{y-8}" width="14" height="9" fill="{color}" rx="2"/>')
        parts.append(f'<text x="{x0+18}" y="{y}" fill="#94a3b8" font-size="10">{label}</text>')
    return "".join(parts)


# ---------------------------------------------------------------------------
# Chart: failure mode stacked horizontal bar by policy
# ---------------------------------------------------------------------------

def _failure_bar_chart(episodes: List[RolloutEpisode]) -> str:
    policies = [p for p, _ in POLICIES]
    mode_colors = {
        "missed_grasp":     "#ef4444",
        "dropped_object":   "#f97316",
        "workspace_limit":  "#eab308",
        "timeout":          "#8b5cf6",
        "wrong_orientation":"#06b6d4",
    }
    W, BAR_H, GAP, PAD_L, PAD_T = 560, 26, 10, 130, 10
    H = len(policies) * (BAR_H + GAP) + PAD_T + 30

    parts = [f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg">']

    for pi, pol in enumerate(policies):
        y = PAD_T + pi * (BAR_H + GAP)
        pol_eps = [ep for ep in episodes if ep.policy_name == pol]
        n_fail = sum(1 for ep in pol_eps if not ep.success)
        sr = sum(1 for ep in pol_eps if ep.success) / len(pol_eps) if pol_eps else 0.0

        # Policy label
        parts.append(f'<text x="{PAD_L - 6}" y="{y + BAR_H//2 + 4}" '
                     f'fill="#e2e8f0" font-size="11" text-anchor="end">{pol}</text>')

        # SR badge
        sr_color = "#22c55e" if sr >= 0.75 else ("#f59e0b" if sr >= 0.55 else "#ef4444")
        parts.append(f'<text x="{PAD_L - 6}" y="{y + BAR_H//2 + 16}" '
                     f'fill="{sr_color}" font-size="10" text-anchor="end">{sr*100:.0f}% SR</text>')

        # Background track
        track_w = W - PAD_L - 80
        parts.append(f'<rect x="{PAD_L}" y="{y}" width="{track_w}" height="{BAR_H}" '
                     f'fill="#1e293b" rx="3" stroke="#334155" stroke-width="1"/>')

        if n_fail == 0:
            # Full green bar
            parts.append(f'<rect x="{PAD_L}" y="{y}" width="{track_w}" height="{BAR_H}" '
                         f'fill="#166534" rx="3"/>')
            parts.append(f'<text x="{PAD_L + track_w//2}" y="{y + BAR_H//2 + 4}" '
                         f'fill="#22c55e" font-size="10" text-anchor="middle">all success</text>')
        else:
            # Count failures per mode
            mode_counts = {m: 0 for m in FAILURE_MODES}
            for ep in pol_eps:
                if ep.failure_mode:
                    mode_counts[ep.failure_mode] = mode_counts.get(ep.failure_mode, 0) + 1

            x_cur = PAD_L
            for mode in FAILURE_MODES:
                cnt = mode_counts.get(mode, 0)
                if cnt == 0:
                    continue
                seg_w = (cnt / n_fail) * track_w
                color = mode_colors.get(mode, "#6b7280")
                parts.append(f'<rect x="{x_cur:.1f}" y="{y}" width="{seg_w:.1f}" height="{BAR_H}" '
                              f'fill="{color}" opacity="0.85"/>')
                if seg_w > 28:
                    parts.append(f'<text x="{x_cur + seg_w/2:.1f}" y="{y + BAR_H//2 + 4}" '
                                 f'fill="white" font-size="9" text-anchor="middle">{cnt}</text>')
                x_cur += seg_w

        # Failure count label
        parts.append(f'<text x="{PAD_L + track_w + 6}" y="{y + BAR_H//2 + 4}" '
                     f'fill="#94a3b8" font-size="10">{n_fail} fail</text>')

    # Legend
    legend_y = H - 22
    lx = PAD_L
    for mode, color in mode_colors.items():
        parts.append(f'<rect x="{lx}" y="{legend_y}" width="10" height="10" fill="{color}" rx="1"/>')
        parts.append(f'<text x="{lx + 13}" y="{legend_y + 9}" fill="#94a3b8" font-size="9">'
                     f'{mode.replace("_", " ")}</text>')
        lx += len(mode) * 6 + 28

    parts.append("</svg>")
    return "".join(parts)


# ---------------------------------------------------------------------------
# Chart: EE XY path — one success vs one failure
# ---------------------------------------------------------------------------

def _ee_path_chart(success_ep: RolloutEpisode, fail_ep: RolloutEpisode) -> str:
    W, H, PAD = 420, 300, 20

    def to_svg(ep: RolloutEpisode) -> List[tuple]:
        xs = [fr.ee_pos[0] for fr in ep.frames]
        ys = [fr.ee_pos[1] for fr in ep.frames]
        all_x = xs
        all_y = ys
        xmin, xmax = min(all_x) - 0.05, max(all_x) + 0.05
        ymin, ymax = min(all_y) - 0.05, max(all_y) + 0.05
        xrng = xmax - xmin or 1.0
        yrng = ymax - ymin or 1.0
        return [
            ((x - xmin) / xrng * (W - 2 * PAD) + PAD,
             H - ((y - ymin) / yrng * (H - 2 * PAD) + PAD))
            for x, y in zip(xs, ys)
        ]

    s_pts = to_svg(success_ep)
    f_pts = to_svg(fail_ep)

    parts = [f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg">']
    # Grid
    for i in range(5):
        gx = PAD + i * (W - 2 * PAD) // 4
        gy = PAD + i * (H - 2 * PAD) // 4
        parts.append(f'<line x1="{gx}" y1="{PAD}" x2="{gx}" y2="{H-PAD}" '
                     f'stroke="#334155" stroke-width="1" stroke-dasharray="3,3"/>')
        parts.append(f'<line x1="{PAD}" y1="{gy}" x2="{W-PAD}" y2="{gy}" '
                     f'stroke="#334155" stroke-width="1" stroke-dasharray="3,3"/>')

    # Axis labels
    parts.append(f'<text x="{W//2}" y="{H-4}" fill="#64748b" font-size="10" '
                 f'text-anchor="middle">EE X (top view)</text>')
    parts.append(f'<text x="10" y="{H//2}" fill="#64748b" font-size="10" '
                 f'text-anchor="middle" transform="rotate(-90,10,{H//2})">EE Y</text>')

    # Paths
    parts.append(_polyline(s_pts, "#22c55e", sw=2))
    parts.append(_polyline(f_pts, "#ef4444", sw=2, dash="5,3"))

    # Start / end markers
    for pts, color in [(s_pts, "#22c55e"), (f_pts, "#ef4444")]:
        sx, sy = pts[0]
        ex, ey = pts[-1]
        parts.append(f'<circle cx="{sx:.1f}" cy="{sy:.1f}" r="5" fill="{color}" opacity="0.7"/>')
        parts.append(f'<circle cx="{ex:.1f}" cy="{ey:.1f}" r="5" fill="{color}"/>')

    # Legend
    parts.append(_svg_legend([("#22c55e", "success"), ("#ef4444", "failure (dashed)")], PAD + 4, PAD + 12))
    parts.append("</svg>")
    return "".join(parts)


# ---------------------------------------------------------------------------
# Chart: joint 0 velocity timeline — success vs failure
# ---------------------------------------------------------------------------

def _joint_velocity_chart(success_ep: RolloutEpisode, fail_ep: RolloutEpisode) -> str:
    W, H = 560, 150

    def velocities(ep: RolloutEpisode) -> List[float]:
        j0 = [fr.joints[0] for fr in ep.frames]
        vels = [0.0] + [j0[i] - j0[i - 1] for i in range(1, len(j0))]
        return vels

    sv = velocities(success_ep)
    fv = velocities(fail_ep)
    vmin = min(min(sv), min(fv))
    vmax = max(max(sv), max(fv))

    s_pts = _norm_to_svg(sv, W, H, vmin, vmax)
    f_pts = _norm_to_svg(fv, W, H, vmin, vmax)

    parts = [
        f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg">',
        f'<rect width="{W}" height="{H}" fill="none"/>',
    ]

    # Zero line
    zero_y = H - ((-vmin) / (vmax - vmin) * (H - 6)) - 3 if vmax != vmin else H // 2
    parts.append(f'<line x1="0" y1="{zero_y:.1f}" x2="{W}" y2="{zero_y:.1f}" '
                 f'stroke="#475569" stroke-width="1" stroke-dasharray="4,4"/>')
    parts.append(f'<text x="3" y="{zero_y - 3:.1f}" fill="#64748b" font-size="9">0</text>')

    parts.append(_polyline(s_pts, "#22c55e", sw=2))
    parts.append(_polyline(f_pts, "#ef4444", sw=2))

    # X-axis label ticks
    for i in range(0, N_FRAMES + 1, 10):
        x = i / (N_FRAMES - 1) * W
        t_s = round(i / (N_FRAMES - 1) * DURATION_S, 1)
        parts.append(f'<line x1="{x:.1f}" y1="{H-8}" x2="{x:.1f}" y2="{H}" '
                     f'stroke="#475569" stroke-width="1"/>')
        parts.append(f'<text x="{x:.1f}" y="{H}" fill="#64748b" font-size="9" '
                     f'text-anchor="middle">{t_s}s</text>')

    parts.append(_svg_legend([("#22c55e", "joint_0 vel (success)"), ("#ef4444", "joint_0 vel (failure)")],
                             8, 14))
    parts.append("</svg>")
    return "".join(parts)


# ---------------------------------------------------------------------------
# SR matrix table (HTML)
# ---------------------------------------------------------------------------

def _sr_matrix_table(episodes: List[RolloutEpisode]) -> str:
    policies = [p for p, _ in POLICIES]

    def sr_color(sr: float) -> str:
        if sr >= 0.75:
            return "#166534"
        elif sr >= 0.55:
            return "#713f12"
        return "#7f1d1d"

    def sr_text_color(sr: float) -> str:
        if sr >= 0.75:
            return "#22c55e"
        elif sr >= 0.55:
            return "#f59e0b"
        return "#ef4444"

    rows = []
    # Header
    header_cells = '<th style="text-align:left;padding:8px 14px;color:#94a3b8;font-weight:500">Policy</th>'
    for task in TASKS:
        header_cells += f'<th style="padding:8px 14px;color:#94a3b8;font-weight:500">{task}</th>'
    header_cells += '<th style="padding:8px 14px;color:#94a3b8;font-weight:500">Overall</th>'
    rows.append(f'<tr>{header_cells}</tr>')

    for pol in policies:
        pol_eps = [ep for ep in episodes if ep.policy_name == pol]
        cells = f'<td style="padding:8px 14px;color:#e2e8f0;font-weight:500">{pol}</td>'
        for task in TASKS:
            subset = [ep for ep in pol_eps if ep.task_name == task]
            sr = sum(1 for ep in subset if ep.success) / len(subset) if subset else 0.0
            bg = sr_color(sr)
            fc = sr_text_color(sr)
            cells += (f'<td style="padding:8px 14px;text-align:center;background:{bg};'
                      f'color:{fc};font-weight:700;border-radius:4px">{sr*100:.0f}%</td>')
        overall = sum(1 for ep in pol_eps if ep.success) / len(pol_eps) if pol_eps else 0.0
        bg = sr_color(overall)
        fc = sr_text_color(overall)
        cells += (f'<td style="padding:8px 14px;text-align:center;background:{bg};'
                  f'color:{fc};font-weight:700;border-radius:4px">{overall*100:.0f}%</td>')
        rows.append(f'<tr>{cells}</tr>')

    return (
        '<table style="border-collapse:separate;border-spacing:3px;width:100%">'
        + "".join(rows) +
        "</table>"
    )


# ---------------------------------------------------------------------------
# Episode cards
# ---------------------------------------------------------------------------

def _episode_cards(episodes: List[RolloutEpisode]) -> str:
    """2 cards per policy: 1 success + 1 failure."""
    policies = [p for p, _ in POLICIES]
    selected: List[RolloutEpisode] = []
    for pol in policies:
        pol_eps = [ep for ep in episodes if ep.policy_name == pol]
        successes = [ep for ep in pol_eps if ep.success]
        failures  = [ep for ep in pol_eps if not ep.success]
        if successes:
            selected.append(successes[0])
        if failures:
            selected.append(failures[0])

    cards = []
    for ep in selected:
        result_color = "#22c55e" if ep.success else "#ef4444"
        result_label = "SUCCESS" if ep.success else "FAILURE"
        fm_html = ""
        if ep.failure_mode:
            fm_html = (f'<div style="margin-top:6px;padding:4px 8px;background:#7f1d1d;'
                       f'border-radius:4px;color:#fca5a5;font-size:11px">'
                       f'Failure: {ep.failure_mode.replace("_", " ")}</div>')

        # Key event timeline
        event_dots = []
        for evt in ep.key_events:
            dot_color = ("#22c55e" if evt["event"] == "success"
                        else "#ef4444" if evt["event"] == "failure"
                        else "#f59e0b")
            pct = evt["t"] / DURATION_S * 100
            evt_name = evt["event"]
            evt_t    = evt["t"]
            event_dots.append(
                f'<div style="position:absolute;left:{pct:.0f}%;top:50%;transform:translate(-50%,-50%);'
                f'width:10px;height:10px;border-radius:50%;background:{dot_color};'
                f'border:2px solid #1e293b" title="{evt_name} @ {evt_t}s"></div>'
            )
        timeline_html = (
            '<div style="position:relative;height:10px;background:#334155;border-radius:5px;margin:8px 0">'
            + "".join(event_dots) +
            "</div>"
        )

        # Event list
        event_rows = "".join(
            f'<div style="display:flex;gap:8px;font-size:11px;margin-top:3px">'
            f'<span style="color:#64748b;min-width:40px">{evt["t"]:.2f}s</span>'
            f'<span style="color:#94a3b8">{evt["event"]}</span>'
            f'<span style="color:#64748b">{evt["detail"]}</span></div>'
            for evt in ep.key_events
        )

        cards.append(f"""
        <div style="background:#0f172a;border:1px solid #334155;border-radius:8px;
                    padding:14px 16px;min-width:240px;flex:1">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
            <span style="font-size:12px;color:#64748b;font-family:monospace">{ep.episode_id}</span>
            <span style="font-weight:700;color:{result_color};font-size:13px">{result_label}</span>
          </div>
          <div style="font-size:11px;color:#94a3b8;margin-bottom:4px">
            policy: <b style="color:#e2e8f0">{ep.policy_name}</b>
            &nbsp;|&nbsp; task: <b style="color:#e2e8f0">{ep.task_name}</b>
            &nbsp;|&nbsp; {ep.n_frames} frames / {ep.duration_s}s
          </div>
          {fm_html}
          {timeline_html}
          <div style="margin-top:6px">{event_rows}</div>
        </div>
        """)

    # Group into rows of 2
    rows_html = []
    for i in range(0, len(cards), 2):
        chunk = cards[i:i + 2]
        rows_html.append(
            '<div style="display:flex;gap:14px;margin-bottom:14px">' +
            "".join(chunk) +
            "</div>"
        )
    return "".join(rows_html)


# ---------------------------------------------------------------------------
# Stat cards
# ---------------------------------------------------------------------------

def _stat_cards(report: VisualizerReport) -> str:
    best_pol = max(report.success_rate_by_policy, key=lambda k: report.success_rate_by_policy[k])
    best_sr  = report.success_rate_by_policy[best_pol]
    overall_sr = sum(report.success_rate_by_policy.values()) / len(report.success_rate_by_policy)
    most_common_fm = (max(report.failure_mode_breakdown, key=report.failure_mode_breakdown.get)
                      if report.failure_mode_breakdown else "none")

    cards_data = [
        ("Total Episodes",     str(report.n_episodes),        "#f1f5f9"),
        ("Overall SR",         f"{overall_sr*100:.0f}%",       "#22c55e" if overall_sr >= 0.65 else "#f59e0b"),
        (f"Best Policy SR",    f"{best_sr*100:.0f}%\n({best_pol})", "#22c55e"),
        ("Top Failure Mode",   most_common_fm.replace("_", " "), "#ef4444"),
    ]

    cards_html = ""
    for label, value, color in cards_data:
        # Handle newline in value
        val_parts = value.split("\n")
        val_html = f'<div style="font-size:26px;font-weight:700;color:{color};margin-top:4px">{val_parts[0]}</div>'
        if len(val_parts) > 1:
            val_html += f'<div style="font-size:10px;color:#64748b;margin-top:2px">{val_parts[1]}</div>'
        cards_html += f"""
        <div style="background:#0f172a;border:1px solid #334155;border-radius:8px;
                    padding:16px 22px;flex:1;min-width:140px;text-align:center">
          <div style="color:#94a3b8;font-size:11px;text-transform:uppercase;letter-spacing:.8px">{label}</div>
          {val_html}
        </div>
        """
    return f'<div style="display:flex;gap:14px;margin-bottom:8px;flex-wrap:wrap">{cards_html}</div>'


# ---------------------------------------------------------------------------
# Full HTML report
# ---------------------------------------------------------------------------

def build_html_report(report: VisualizerReport) -> str:
    episodes = report.results

    # Pick one success + one failure from dagger_run9_lora for EE path / velocity charts
    run9_lora = [ep for ep in episodes if ep.policy_name == "dagger_run9_lora"]
    chart_success = next((ep for ep in run9_lora if ep.success), run9_lora[0])
    chart_fail    = next((ep for ep in run9_lora if not ep.success), run9_lora[-1])

    stat_html   = _stat_cards(report)
    fail_bar    = _failure_bar_chart(episodes)
    ee_path     = _ee_path_chart(chart_success, chart_fail)
    jvel_chart  = _joint_velocity_chart(chart_success, chart_fail)
    sr_table    = _sr_matrix_table(episodes)
    ep_cards    = _episode_cards(episodes)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>GR00T Policy Rollout Report</title>
<style>
  *, *::before, *::after {{ box-sizing: border-box; }}
  body {{
    margin: 0; padding: 24px 32px;
    background: #1e293b; color: #e2e8f0;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    font-size: 14px;
  }}
  h1 {{ color: #C74634; margin: 0 0 4px; font-size: 24px; letter-spacing: .3px; }}
  h2 {{
    color: #C74634; font-size: 15px; margin: 28px 0 10px;
    border-bottom: 1px solid #334155; padding-bottom: 5px;
  }}
  .subtitle {{ color: #94a3b8; font-size: 12px; margin-bottom: 22px; }}
  .chart-wrap {{
    background: #0f172a; border: 1px solid #334155; border-radius: 8px;
    padding: 14px 16px; overflow-x: auto; margin-bottom: 10px;
  }}
  .chart-wrap svg {{ display: block; }}
  .footer {{ margin-top: 32px; color: #475569; font-size: 11px; text-align: center; }}
  table {{ width: 100%; }}
</style>
</head>
<body>
<h1>GR00T Policy Rollout Report</h1>
<div class="subtitle">
  Multi-policy rollout summary &mdash; {report.n_episodes} episodes across
  {report.n_policies} policies &times; {len(TASKS)} tasks &mdash; OCI Robot Cloud
</div>

<h2>Summary</h2>
{stat_html}

<h2>Failure Mode Breakdown by Policy</h2>
<div class="chart-wrap">{fail_bar}</div>

<h2>End-Effector XY Path (dagger_run9_lora &mdash; success vs failure)</h2>
<div class="chart-wrap">{ee_path}</div>

<h2>Joint 0 (shoulder_pan) Velocity &mdash; Success vs Failure</h2>
<div class="chart-wrap">{jvel_chart}</div>

<h2>Policy &times; Task Success Rate Matrix</h2>
<div class="chart-wrap">{sr_table}</div>

<h2>Episode Cards (1 success + 1 failure per policy)</h2>
{ep_cards}

<div class="footer">Generated by policy_rollout_visualizer.py &mdash; OCI Robot Cloud</div>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="GR00T policy rollout visualizer — joint trajectories, EE paths, failure modes"
    )
    parser.add_argument("--mock",   action="store_true",
                        help="Use simulated rollout data (required for offline use)")
    parser.add_argument("--output", default="/tmp/policy_rollout_visualizer.html",
                        help="Output HTML path")
    parser.add_argument("--seed",   type=int, default=42, help="Random seed for simulation")
    args = parser.parse_args()

    print(f"[policy_rollout_visualizer] Simulating episodes (seed={args.seed}) ...")
    episodes = simulate_all_episodes(args.seed)

    report = build_report(episodes)
    print_sr_matrix(episodes)

    print(f"[policy_rollout_visualizer] Building HTML report ({report.n_episodes} episodes) ...")
    html = build_html_report(report)

    with open(args.output, "w", encoding="utf-8") as fh:
        fh.write(html)

    print(f"[policy_rollout_visualizer] Saved → {args.output}")
    print(f"  Policies : {report.n_policies}")
    print(f"  Episodes : {report.n_episodes}")
    print(f"  Best SR  : {max(report.success_rate_by_policy.values())*100:.0f}% "
          f"({max(report.success_rate_by_policy, key=lambda k: report.success_rate_by_policy[k])})")
    print(f"  Top fail : {max(report.failure_mode_breakdown, key=report.failure_mode_breakdown.get) if report.failure_mode_breakdown else 'none'}")


if __name__ == "__main__":
    main()
