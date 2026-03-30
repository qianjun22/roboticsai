#!/usr/bin/env python3
"""Contact force sensor analysis for robot grasping. Measures force profiles,
slip detection, and grasp quality metrics."""

import argparse
import math
import random
from dataclasses import dataclass, field
from typing import List


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class ForceFrame:
    t_ms: float
    fx: float
    fy: float
    fz: float
    tx: float
    ty: float
    tz: float
    magnitude: float
    contact_detected: bool


@dataclass
class GraspEvent:
    episode_id: int
    grasp_start_ms: float
    grasp_end_ms: float
    peak_force_n: float
    avg_force_n: float
    slip_events: int
    force_stability: float  # 0-1, higher = more stable
    grasp_success: bool


@dataclass
class ForceReport:
    policy_name: str
    n_episodes: int
    grasp_success_rate: float
    avg_peak_force: float
    avg_stability: float
    slip_rate: float
    results: List[GraspEvent] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Simulation helpers
# ---------------------------------------------------------------------------

POLICY_CONFIGS = {
    "bc_baseline":      {"grasp_sr": 0.55, "slip_rate": 0.18, "stability": 0.62, "peak_force": 12.5},
    "dagger_run5":      {"grasp_sr": 0.70, "slip_rate": 0.13, "stability": 0.74, "peak_force": 11.2},
    "dagger_run9":      {"grasp_sr": 0.82, "slip_rate": 0.06, "stability": 0.85, "peak_force": 10.4},
    "dagger_run9_lora": {"grasp_sr": 0.84, "slip_rate": 0.05, "stability": 0.91, "peak_force": 10.1},
}

N_EPISODES = 30
N_FRAMES = 120          # 50 Hz → 2.4 s
DT_MS = 20.0            # 20 ms per frame


def _noise(rng: random.Random, scale: float) -> float:
    return rng.gauss(0, scale)


def _simulate_episode(
    rng: random.Random,
    episode_id: int,
    policy_cfg: dict,
    is_success: bool,
    failure_mode: str,  # "missed", "crush", "slip"
) -> tuple[List[ForceFrame], GraspEvent]:
    """Generate 120 ForceFrames and derive a GraspEvent."""

    peak_target = policy_cfg["peak_force"]
    slip_rate = policy_cfg["slip_rate"]
    stability_base = policy_cfg["stability"]

    frames: List[ForceFrame] = []
    slip_count = 0
    contact_start = None
    contact_end = None

    # Ramp timing (in frames)
    ramp_up_end = 25
    plateau_end = 90
    ramp_down_end = 110

    forces = []

    for i in range(N_FRAMES):
        t_ms = i * DT_MS
        phase_frac = i / N_FRAMES

        if is_success:
            if i < ramp_up_end:
                base_fz = peak_target * (i / ramp_up_end)
            elif i < plateau_end:
                base_fz = peak_target * (1.0 + _noise(rng, 0.03))
            elif i < ramp_down_end:
                base_fz = peak_target * ((ramp_down_end - i) / (ramp_down_end - plateau_end))
            else:
                base_fz = 0.0
        elif failure_mode == "missed":
            # Never builds enough force
            base_fz = peak_target * 0.2 * math.sin(phase_frac * math.pi) + _noise(rng, 0.3)
            base_fz = max(0.0, base_fz)
        elif failure_mode == "crush":
            # Over-force
            if i < ramp_up_end:
                base_fz = peak_target * 1.8 * (i / ramp_up_end)
            elif i < 50:
                base_fz = peak_target * 1.9 + _noise(rng, 0.5)
            else:
                base_fz = 0.0  # object dropped after crush
        else:  # slip
            if i < ramp_up_end:
                base_fz = peak_target * (i / ramp_up_end)
            elif i < 60:
                base_fz = peak_target * (1.0 + _noise(rng, 0.04))
                # Slip event: sudden force drop
                if rng.random() < slip_rate / 2.0:
                    base_fz *= rng.uniform(0.3, 0.6)
                    slip_count += 1
            else:
                base_fz = 0.0

        # Lateral forces (fx, fy) are smaller
        fx = base_fz * rng.uniform(0.05, 0.15) + _noise(rng, 0.15)
        fy = base_fz * rng.uniform(0.05, 0.12) + _noise(rng, 0.12)
        fz = base_fz + _noise(rng, 0.2)
        fz = max(0.0, fz)

        # Torques scale with forces (Nm)
        tx = fz * rng.uniform(0.01, 0.06) + _noise(rng, 0.01)
        ty = fz * rng.uniform(0.01, 0.05) + _noise(rng, 0.01)
        tz = fz * rng.uniform(0.005, 0.03) + _noise(rng, 0.005)

        mag = math.sqrt(fx**2 + fy**2 + fz**2)
        contact = mag > 1.0

        if contact and contact_start is None:
            contact_start = t_ms
        if contact:
            contact_end = t_ms

        forces.append(fz)
        frames.append(ForceFrame(
            t_ms=t_ms, fx=fx, fy=fy, fz=fz,
            tx=tx, ty=ty, tz=tz,
            magnitude=mag, contact_detected=contact,
        ))

    grasp_start_ms = contact_start if contact_start is not None else 0.0
    grasp_end_ms = contact_end if contact_end is not None else 0.0

    peak_force = max(forces) if forces else 0.0
    contact_forces = [f for f in forces if f > 1.0]
    avg_force = sum(contact_forces) / len(contact_forces) if contact_forces else 0.0

    # Stability: 1 - (std / mean) normalized, capped 0-1
    if len(contact_forces) > 1:
        mean_f = avg_force if avg_force > 0 else 1e-6
        std_f = math.sqrt(sum((f - mean_f) ** 2 for f in contact_forces) / len(contact_forces))
        cv = std_f / mean_f
        raw_stability = max(0.0, 1.0 - cv * 2.0)
        # Blend with policy baseline
        stability = raw_stability * 0.6 + stability_base * 0.4 + _noise(rng, 0.04)
        stability = min(1.0, max(0.0, stability))
    else:
        stability = 0.1

    event = GraspEvent(
        episode_id=episode_id,
        grasp_start_ms=grasp_start_ms,
        grasp_end_ms=grasp_end_ms,
        peak_force_n=round(peak_force, 3),
        avg_force_n=round(avg_force, 3),
        slip_events=slip_count,
        force_stability=round(stability, 4),
        grasp_success=is_success,
    )
    return frames, event


def simulate_policy(policy_name: str, seed: int) -> tuple[ForceReport, List[List[ForceFrame]]]:
    """Simulate N_EPISODES for a policy. Returns report + per-episode frame lists."""
    cfg = POLICY_CONFIGS[policy_name]
    rng = random.Random(seed + hash(policy_name) % 10000)

    events: List[GraspEvent] = []
    all_frames: List[List[ForceFrame]] = []
    n_success = round(cfg["grasp_sr"] * N_EPISODES)

    # Decide which episodes succeed
    success_mask = [True] * n_success + [False] * (N_EPISODES - n_success)
    rng.shuffle(success_mask)

    failure_modes = ["missed", "crush", "slip"]

    for ep_id, is_success in enumerate(success_mask):
        if is_success:
            fm = "none"
        else:
            # Weight slip failures according to slip_rate
            r = rng.random()
            if r < cfg["slip_rate"]:
                fm = "slip"
            elif r < cfg["slip_rate"] + 0.3:
                fm = "crush"
            else:
                fm = "missed"

        frames, event = _simulate_episode(rng, ep_id, cfg, is_success, fm)
        events.append(event)
        all_frames.append(frames)

    actual_sr = sum(1 for e in events if e.grasp_success) / len(events)
    avg_peak = sum(e.peak_force_n for e in events) / len(events)
    avg_stab = sum(e.force_stability for e in events) / len(events)
    actual_slip_rate = sum(e.slip_events for e in events) / len(events) / 3.0  # normalize
    actual_slip_rate = min(1.0, actual_slip_rate)

    report = ForceReport(
        policy_name=policy_name,
        n_episodes=N_EPISODES,
        grasp_success_rate=round(actual_sr, 4),
        avg_peak_force=round(avg_peak, 3),
        avg_stability=round(avg_stab, 4),
        slip_rate=round(cfg["slip_rate"], 3),
        results=events,
    )
    return report, all_frames


# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------

def _sparkline_force(
    success_frames: List[ForceFrame],
    failure_frames: List[ForceFrame],
    width: int = 520,
    height: int = 160,
) -> str:
    """Overlaid force magnitude timeline: success (green) vs failure (red)."""

    def to_svg_points(frames: List[ForceFrame]) -> str:
        max_mag = max((f.magnitude for f in frames), default=1.0)
        max_mag = max(max_mag, 1.0)
        pts = []
        for i, fr in enumerate(frames):
            x = 40 + (i / (len(frames) - 1)) * (width - 60)
            y = height - 30 - ((fr.magnitude / max_mag) * (height - 50))
            pts.append(f"{x:.1f},{y:.1f}")
        return " ".join(pts)

    all_mags = [f.magnitude for f in success_frames + failure_frames]
    max_mag = max(all_mags) if all_mags else 1.0
    max_mag = max(max_mag, 1.0)

    def to_pts_shared(frames: List[ForceFrame]) -> str:
        pts = []
        for i, fr in enumerate(frames):
            x = 40 + (i / (len(frames) - 1)) * (width - 60)
            y = height - 30 - ((fr.magnitude / max_mag) * (height - 50))
            pts.append(f"{x:.1f},{y:.1f}")
        return " ".join(pts)

    s_pts = to_pts_shared(success_frames)
    f_pts = to_pts_shared(failure_frames)

    # Y-axis labels
    y_labels = ""
    for v in [0, 5, 10, 15, 20]:
        if v > max_mag:
            continue
        y = height - 30 - ((v / max_mag) * (height - 50))
        y_labels += f'<text x="35" y="{y+4:.1f}" fill="#94a3b8" font-size="10" text-anchor="end">{v}N</text>'
        y_labels += f'<line x1="40" y1="{y:.1f}" x2="{width-20}" y2="{y:.1f}" stroke="#334155" stroke-width="0.5"/>'

    # X-axis labels
    x_labels = ""
    for ms in [0, 600, 1200, 1800, 2400]:
        idx = ms // 20
        idx = min(idx, len(success_frames) - 1)
        x = 40 + (idx / (N_FRAMES - 1)) * (width - 60)
        x_labels += f'<text x="{x:.1f}" y="{height - 12}" fill="#94a3b8" font-size="10" text-anchor="middle">{ms}ms</text>'

    return f"""<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">
  <rect width="{width}" height="{height}" fill="#0f172a" rx="6"/>
  {y_labels}
  {x_labels}
  <polyline points="{f_pts}" fill="none" stroke="#ef4444" stroke-width="1.8" opacity="0.85"/>
  <polyline points="{s_pts}" fill="none" stroke="#22c55e" stroke-width="1.8" opacity="0.85"/>
  <circle cx="{width-90}" cy="18" r="5" fill="#22c55e"/>
  <text x="{width-82}" y="22" fill="#e2e8f0" font-size="11">Success</text>
  <circle cx="{width-30}" cy="18" r="5" fill="#ef4444"/>
  <text x="{width-22}" y="22" fill="#e2e8f0" font-size="11">Fail</text>
  <text x="38" y="15" fill="#94a3b8" font-size="10">Force magnitude (N)</text>
</svg>"""


def _bar_chart_sr(reports: List[ForceReport], width: int = 520, height: int = 180) -> str:
    """Grasp success rate bar chart per policy."""
    n = len(reports)
    bar_w = 60
    gap = (width - 40 - n * bar_w) // (n + 1)
    max_sr = 1.0
    colors = ["#64748b", "#3b82f6", "#f59e0b", "#C74634"]

    bars = ""
    for i, rpt in enumerate(reports):
        x = 40 + gap + i * (bar_w + gap)
        bar_h = rpt.grasp_success_rate * (height - 60)
        y = height - 30 - bar_h
        pct = f"{rpt.grasp_success_rate*100:.0f}%"
        short_name = rpt.policy_name.replace("dagger_run9_lora", "DR9-LoRA").replace(
            "dagger_run9", "DR9").replace("dagger_run5", "DR5").replace("bc_baseline", "BC")
        bars += f"""<rect x="{x}" y="{y:.1f}" width="{bar_w}" height="{bar_h:.1f}" fill="{colors[i]}" rx="3"/>
<text x="{x+bar_w//2}" y="{y-5:.1f}" fill="#e2e8f0" font-size="11" text-anchor="middle">{pct}</text>
<text x="{x+bar_w//2}" y="{height-14}" fill="#94a3b8" font-size="10" text-anchor="middle">{short_name}</text>"""

    # Y-axis
    y_labels = ""
    for v in [0, 25, 50, 75, 100]:
        y = height - 30 - (v / 100.0) * (height - 60)
        y_labels += f'<text x="35" y="{y+4:.1f}" fill="#94a3b8" font-size="10" text-anchor="end">{v}%</text>'
        y_labels += f'<line x1="40" y1="{y:.1f}" x2="{width-10}" y2="{y:.1f}" stroke="#334155" stroke-width="0.5"/>'

    return f"""<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">
  <rect width="{width}" height="{height}" fill="#0f172a" rx="6"/>
  {y_labels}
  {bars}
  <text x="{width//2}" y="16" fill="#94a3b8" font-size="11" text-anchor="middle">Grasp Success Rate by Policy</text>
</svg>"""


def _scatter_stability(report: ForceReport, width: int = 360, height: int = 220) -> str:
    """Force stability vs grasp success scatter for dagger_run9."""
    dots = ""
    for ev in report.results:
        x = 40 + ev.force_stability * (width - 60)
        # Jitter y slightly so dots don't stack
        y_base = 60 if ev.grasp_success else 140
        y = y_base + (hash(ev.episode_id) % 20) - 10
        color = "#22c55e" if ev.grasp_success else "#ef4444"
        tip = f"ep{ev.episode_id} stab={ev.force_stability:.2f}"
        dots += f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="{color}" opacity="0.8"><title>{tip}</title></circle>'

    # X-axis labels
    x_labels = ""
    for v in [0.0, 0.25, 0.50, 0.75, 1.0]:
        x = 40 + v * (width - 60)
        x_labels += f'<text x="{x:.1f}" y="{height-10}" fill="#94a3b8" font-size="10" text-anchor="middle">{v:.2f}</text>'

    return f"""<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">
  <rect width="{width}" height="{height}" fill="#0f172a" rx="6"/>
  <line x1="40" y1="30" x2="40" y2="{height-25}" stroke="#475569" stroke-width="1"/>
  <line x1="40" y1="{height-25}" x2="{width-10}" y2="{height-25}" stroke="#475569" stroke-width="1"/>
  {x_labels}
  <text x="{width//2}" y="18" fill="#94a3b8" font-size="11" text-anchor="middle">dagger_run9: Stability vs Success</text>
  <text x="15" y="65" fill="#22c55e" font-size="10" transform="rotate(-90 15 65)">Success</text>
  <text x="15" y="145" fill="#ef4444" font-size="10" transform="rotate(-90 15 145)">Fail</text>
  {dots}
  <text x="{width//2}" y="{height-2}" fill="#94a3b8" font-size="10" text-anchor="middle">Force Stability (0-1)</text>
</svg>"""


# ---------------------------------------------------------------------------
# HTML report
# ---------------------------------------------------------------------------

def build_html(reports: List[ForceReport], all_episode_frames: dict) -> str:
    # Stat cards
    best_sr_rpt = max(reports, key=lambda r: r.grasp_success_rate)
    lowest_slip_rpt = min(reports, key=lambda r: r.slip_rate)
    best_stab_rpt = max(reports, key=lambda r: r.avg_stability)

    cards_html = f"""
<div class="cards">
  <div class="card">
    <div class="card-label">Best Grasp SR</div>
    <div class="card-value">{best_sr_rpt.grasp_success_rate*100:.0f}%</div>
    <div class="card-sub">{best_sr_rpt.policy_name}</div>
  </div>
  <div class="card">
    <div class="card-label">Lowest Slip Rate</div>
    <div class="card-value">{lowest_slip_rpt.slip_rate*100:.0f}%</div>
    <div class="card-sub">{lowest_slip_rpt.policy_name}</div>
  </div>
  <div class="card">
    <div class="card-label">Best Force Stability</div>
    <div class="card-value">{best_stab_rpt.avg_stability:.2f}</div>
    <div class="card-sub">{best_stab_rpt.policy_name}</div>
  </div>
  <div class="card">
    <div class="card-label">Recommended Peak Force</div>
    <div class="card-value">8–13 N</div>
    <div class="card-sub">Manipulation range</div>
  </div>
</div>"""

    # Pick success/failure episodes from dagger_run9 for timeline SVG
    dr9_report = next(r for r in reports if r.policy_name == "dagger_run9")
    dr9_frames = all_episode_frames["dagger_run9"]
    success_ep = next((i for i, e in enumerate(dr9_report.results) if e.grasp_success), 0)
    failure_ep = next((i for i, e in enumerate(dr9_report.results) if not e.grasp_success), 1)
    timeline_svg = _sparkline_force(dr9_frames[success_ep], dr9_frames[failure_ep])

    bar_svg = _bar_chart_sr(reports)
    scatter_svg = _scatter_stability(dr9_report)

    # Policy table rows
    table_rows = ""
    for rpt in reports:
        sr_pct = f"{rpt.grasp_success_rate*100:.0f}%"
        table_rows += f"""<tr>
      <td class="policy-name">{rpt.policy_name}</td>
      <td>{sr_pct}</td>
      <td>{rpt.avg_peak_force:.1f} N</td>
      <td>{rpt.avg_stability:.3f}</td>
      <td>{rpt.slip_rate*100:.0f}%</td>
      <td>{rpt.n_episodes}</td>
    </tr>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>Contact Force Analyzer — OCI Robot Cloud</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #1e293b; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; padding: 24px; }}
  h1 {{ font-size: 1.6rem; font-weight: 700; color: #f1f5f9; margin-bottom: 4px; }}
  h1 span {{ color: #C74634; }}
  .subtitle {{ color: #94a3b8; font-size: 0.9rem; margin-bottom: 24px; }}
  .cards {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 28px; }}
  .card {{ background: #0f172a; border: 1px solid #334155; border-radius: 10px; padding: 18px 20px; }}
  .card-label {{ font-size: 0.78rem; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 6px; }}
  .card-value {{ font-size: 2rem; font-weight: 700; color: #C74634; line-height: 1; }}
  .card-sub {{ font-size: 0.75rem; color: #94a3b8; margin-top: 4px; }}
  .section {{ margin-bottom: 32px; }}
  .section h2 {{ font-size: 1rem; font-weight: 600; color: #cbd5e1; margin-bottom: 12px; border-left: 3px solid #C74634; padding-left: 10px; }}
  .charts-row {{ display: flex; gap: 20px; flex-wrap: wrap; }}
  .chart-box {{ background: #0f172a; border: 1px solid #334155; border-radius: 10px; padding: 14px; }}
  table {{ width: 100%; border-collapse: collapse; background: #0f172a; border-radius: 10px; overflow: hidden; }}
  thead th {{ background: #1e3a5f; color: #93c5fd; font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.04em; padding: 10px 14px; text-align: left; }}
  tbody tr {{ border-bottom: 1px solid #1e293b; }}
  tbody tr:hover {{ background: #1e293b; }}
  tbody td {{ padding: 10px 14px; font-size: 0.875rem; color: #cbd5e1; }}
  .policy-name {{ font-family: monospace; color: #7dd3fc; }}
  footer {{ margin-top: 32px; font-size: 0.75rem; color: #475569; text-align: center; }}
  @media (max-width: 900px) {{ .cards {{ grid-template-columns: repeat(2, 1fr); }} }}
</style>
</head>
<body>
<h1>OCI Robot Cloud — <span>Contact Force Analyzer</span></h1>
<p class="subtitle">Force profile analysis · Slip detection · Grasp quality metrics · 4 policies × 30 episodes</p>

{cards_html}

<div class="section">
  <h2>Force Magnitude Timeline — Success vs Failure (dagger_run9)</h2>
  <div class="chart-box" style="display:inline-block">
    {timeline_svg}
  </div>
</div>

<div class="section">
  <h2>Policy Comparison</h2>
  <div class="charts-row">
    <div class="chart-box">{bar_svg}</div>
    <div class="chart-box">{scatter_svg}</div>
  </div>
</div>

<div class="section">
  <h2>Policy Summary Table</h2>
  <table>
    <thead><tr>
      <th>Policy</th><th>Grasp SR</th><th>Avg Peak Force</th>
      <th>Avg Stability</th><th>Slip Rate</th><th>Episodes</th>
    </tr></thead>
    <tbody>{table_rows}</tbody>
  </table>
</div>

<footer>OCI Robot Cloud · Contact Force Analyzer · Simulated data (--mock) · seed=42</footer>
</body>
</html>"""


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def print_summary(reports: List[ForceReport]) -> None:
    header = f"{'Policy':<22} {'Grasp SR':>9} {'Peak F (N)':>11} {'Stability':>10} {'Slip Rate':>10} {'N Eps':>7}"
    print("\nContact Force Analysis — Policy Summary")
    print("=" * len(header))
    print(header)
    print("-" * len(header))
    for rpt in reports:
        print(
            f"{rpt.policy_name:<22} "
            f"{rpt.grasp_success_rate*100:>8.0f}% "
            f"{rpt.avg_peak_force:>10.2f}N "
            f"{rpt.avg_stability:>10.3f} "
            f"{rpt.slip_rate*100:>9.0f}% "
            f"{rpt.n_episodes:>7}"
        )
    print("=" * len(header))
    best = max(reports, key=lambda r: r.grasp_success_rate)
    print(f"\nBest policy: {best.policy_name}  ({best.grasp_success_rate*100:.0f}% grasp SR, "
          f"stability={best.avg_stability:.3f}, slip={best.slip_rate*100:.0f}%)\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Contact force sensor analyzer for robot grasping tasks."
    )
    parser.add_argument("--mock", action="store_true", default=True,
                        help="Use simulated force data (default: True)")
    parser.add_argument("--output", default="/tmp/contact_force_analyzer.html",
                        help="Output HTML report path")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    args = parser.parse_args()

    print(f"Simulating force data (seed={args.seed}) ...")
    reports: List[ForceReport] = []
    all_frames: dict = {}

    for policy_name in POLICY_CONFIGS:
        rpt, frames = simulate_policy(policy_name, seed=args.seed)
        reports.append(rpt)
        all_frames[policy_name] = frames
        print(f"  {policy_name:<22} episodes={rpt.n_episodes}  SR={rpt.grasp_success_rate*100:.0f}%")

    print_summary(reports)

    html = build_html(reports, all_frames)
    with open(args.output, "w", encoding="utf-8") as fh:
        fh.write(html)
    print(f"HTML report saved: {args.output}")


if __name__ == "__main__":
    main()
