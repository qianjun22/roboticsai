#!/usr/bin/env python3
"""
policy_rollout_visualizer.py — Rich HTML rollout trace visualizer for DAgger policy debugging.

Outputs a self-contained HTML report with:
  - KPI cards (result, frames, failure frame)
  - cube_z trajectory (success vs fail)
  - gripper_force + policy_confidence dual-axis chart
  - Joint trajectory heatmap (7 joints × N frames, downsampled)
  - Phase timeline bar
  - Failure attribution box

Usage:
    python policy_rollout_visualizer.py --mock --output /tmp/policy_rollout_visualizer.html --seed 42
"""

import argparse
import math
import random
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

PHASES = ["approach", "grasp", "lift", "transport", "release"]
PHASE_COLORS = {
    "approach":  "#3b82f6",
    "grasp":     "#f59e0b",
    "lift":      "#10b981",
    "transport": "#8b5cf6",
    "release":   "#ec4899",
}
PHASE_RANGES = {
    "approach":  (0,   60),
    "grasp":     (61,  100),
    "lift":      (101, 150),
    "transport": (151, 200),
    "release":   (201, 240),
}


@dataclass
class RolloutFrame:
    frame: int
    phase: str
    joint_angles: List[float]      # 7 floats, radians
    action: List[float]            # 7 floats
    cube_z: float                  # metres
    gripper_force: float           # N
    policy_confidence: float       # 0-1
    timestamp_ms: float


# ---------------------------------------------------------------------------
# Simulation helpers
# ---------------------------------------------------------------------------

def _phase_for_frame(f: int) -> str:
    for phase, (lo, hi) in PHASE_RANGES.items():
        if lo <= f <= hi:
            return phase
    return "release"


def _smooth(t: float, freq: float, offset: float, amp: float) -> float:
    return amp * math.sin(freq * t + offset)


def generate_rollout(success: bool = True, seed: int = 42, n_frames: int = 240) -> List[RolloutFrame]:
    """Generate a synthetic but realistic policy rollout."""
    rng = random.Random(seed)
    frames: List[RolloutFrame] = []

    CUBE_Z_REST   = 0.02   # on table
    CUBE_Z_PEAK   = 0.35   # lifted height
    FAIL_FRAME    = 130    # frame at which cube drops in failure run

    for f in range(n_frames):
        t      = f / n_frames
        phase  = _phase_for_frame(f)
        noise  = lambda: rng.gauss(0, 0.01)

        # --- joint angles ---------------------------------------------------
        joint_angles = [
            _smooth(t, 2.0 + i * 0.3, i * 0.7, 1.2) + noise()
            for i in range(7)
        ]

        # --- action (delta joints) -------------------------------------------
        action = [
            _smooth(t, 3.0 + i * 0.2, i * 1.1, 0.15) + noise()
            for i in range(7)
        ]

        # --- cube_z -----------------------------------------------------------
        if phase == "approach":
            cube_z = CUBE_Z_REST + noise() * 0.001
        elif phase == "grasp":
            frac   = (f - 61) / (100 - 61)
            cube_z = CUBE_Z_REST + frac * 0.01 + noise() * 0.002
        elif phase == "lift":
            frac   = (f - 101) / (150 - 101)
            if success:
                cube_z = CUBE_Z_REST + frac * (CUBE_Z_PEAK - CUBE_Z_REST) + noise() * 0.003
            else:
                if f < FAIL_FRAME:
                    frac2  = (f - 101) / (FAIL_FRAME - 101)
                    cube_z = CUBE_Z_REST + frac2 * 0.12 + noise() * 0.003
                else:
                    drop   = (f - FAIL_FRAME) / 30
                    cube_z = max(CUBE_Z_REST, 0.14 - drop * 0.12) + noise() * 0.003
        elif phase == "transport":
            if success:
                cube_z = CUBE_Z_PEAK + _smooth(t, 1.5, 0, 0.02) + noise() * 0.003
            else:
                cube_z = CUBE_Z_REST + noise() * 0.003
        else:  # release
            if success:
                cube_z = CUBE_Z_PEAK - ((f - 201) / 39) * (CUBE_Z_PEAK - 0.05) + noise() * 0.003
            else:
                cube_z = CUBE_Z_REST + noise() * 0.003

        # --- gripper_force ---------------------------------------------------
        if phase == "approach":
            gripper_force = 0.0 + abs(noise()) * 0.05
        elif phase == "grasp":
            frac          = (f - 61) / (100 - 61)
            gripper_force = frac * 8.0 + noise() * 0.2
        elif phase in ("lift", "transport"):
            gripper_force = 8.0 + _smooth(t, 4.0, 0, 0.5) + noise() * 0.3
            if not success and f >= FAIL_FRAME:
                drop_frac     = min(1.0, (f - FAIL_FRAME) / 15)
                gripper_force = max(0.0, gripper_force * (1 - drop_frac))
        else:
            frac          = (f - 201) / 39
            gripper_force = max(0.0, 8.0 - frac * 8.0) + abs(noise()) * 0.1

        # --- policy_confidence -----------------------------------------------
        base_conf = rng.uniform(0.7, 0.95)
        if not success and FAIL_FRAME - 15 <= f <= FAIL_FRAME + 10:
            dist          = abs(f - FAIL_FRAME)
            drop          = max(0.0, 1.0 - dist / 15) * 0.55
            policy_confidence = max(0.25, base_conf - drop)
        else:
            policy_confidence = base_conf

        frames.append(RolloutFrame(
            frame             = f,
            phase             = phase,
            joint_angles      = joint_angles,
            action            = action,
            cube_z            = round(cube_z, 4),
            gripper_force     = round(gripper_force, 3),
            policy_confidence = round(policy_confidence, 3),
            timestamp_ms      = round(f * (1000 / 30), 1),   # 30 fps
        ))

    return frames


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------

def compare_rollouts(
    success_rollout: List[RolloutFrame],
    fail_rollout: List[RolloutFrame],
    threshold: float = 0.04,
) -> Tuple[Optional[int], str]:
    """Find the frame where cube_z trajectories first diverge beyond threshold."""
    divergence_frame: Optional[int] = None
    for sf, ff in zip(success_rollout, fail_rollout):
        if abs(sf.cube_z - ff.cube_z) > threshold:
            divergence_frame = ff.frame
            break

    if divergence_frame is None:
        return None, "no divergence detected"

    phase      = _phase_for_frame(divergence_frame)
    ff_at_div  = fail_rollout[divergence_frame]
    conf       = ff_at_div.policy_confidence
    if conf < 0.45:
        cause = f"low policy confidence ({conf:.2f}) during {phase} — likely OOD state"
    elif phase == "lift":
        cause = f"gripper slip during {phase} — force insufficient to hold cube"
    else:
        cause = f"trajectory deviation during {phase} phase"

    return divergence_frame, cause


# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------

def _svg_line(
    data: List[float],
    width: int,
    height: int,
    color: str,
    stroke_width: int = 2,
    vmin: Optional[float] = None,
    vmax: Optional[float] = None,
) -> str:
    """Render a single polyline SVG path."""
    mn  = vmin if vmin is not None else min(data)
    mx  = vmax if vmax is not None else max(data)
    rng = mx - mn if mx != mn else 1.0
    pts = []
    n   = len(data)
    for i, v in enumerate(data):
        x = i / (n - 1) * width
        y = height - ((v - mn) / rng) * height
        pts.append(f"{x:.1f},{y:.1f}")
    return f'<polyline points="{" ".join(pts)}" fill="none" stroke="{color}" stroke-width="{stroke_width}" stroke-linejoin="round"/>'


def _svg_vline(x_frac: float, width: int, height: int, color: str = "#facc15") -> str:
    x = x_frac * width
    return f'<line x1="{x:.1f}" y1="0" x2="{x:.1f}" y2="{height}" stroke="{color}" stroke-width="2" stroke-dasharray="4,3"/>'


def _heatmap_svg(frames: List[RolloutFrame], cols: int = 60, cell_h: int = 22) -> str:
    """Joint trajectory heatmap: 7 joints × cols frames."""
    n_joints = 7
    total_frames = len(frames)
    step     = max(1, total_frames // cols)
    sampled  = [frames[i] for i in range(0, total_frames, step)][:cols]
    actual_cols = len(sampled)
    cell_w   = 10
    W        = actual_cols * cell_w
    H        = n_joints * cell_h
    rows = []
    # collect per-joint min/max for normalisation
    joint_vals = [[f.joint_angles[j] for f in sampled] for j in range(n_joints)]
    joint_min  = [min(v) for v in joint_vals]
    joint_max  = [max(v) for v in joint_vals]

    for j in range(n_joints):
        jmin = joint_min[j]
        jmax = joint_max[j]
        jrng = jmax - jmin if jmax != jmin else 1.0
        for ci, frm in enumerate(sampled):
            val  = frm.joint_angles[j]
            norm = (val - jmin) / jrng        # 0-1
            # cool-warm palette: blue → white → red
            if norm < 0.5:
                t = norm * 2
                r = int(59  + t * (255 - 59))
                g = int(130 + t * (255 - 130))
                b = int(246 + t * (255 - 246))
            else:
                t = (norm - 0.5) * 2
                r = 255
                g = int(255 - t * (255 - 59))
                b = int(255 - t * (255 - 59))
            color = f"rgb({r},{g},{b})"
            x     = ci * cell_w
            y     = j  * cell_h
            rows.append(f'<rect x="{x}" y="{y}" width="{cell_w}" height="{cell_h}" fill="{color}"/>')

    # joint labels
    labels = []
    for j in range(n_joints):
        y = j * cell_h + cell_h // 2 + 4
        labels.append(f'<text x="-4" y="{y}" fill="#94a3b8" font-size="9" text-anchor="end">J{j+1}</text>')

    return (
        f'<svg width="{W + 40}" height="{H + 20}" xmlns="http://www.w3.org/2000/svg">'
        f'<g transform="translate(36,4)">'
        + "".join(rows)
        + "".join(labels)
        + f'</g></svg>'
    )


# ---------------------------------------------------------------------------
# HTML report
# ---------------------------------------------------------------------------

def build_html_report(
    success_rollout: List[RolloutFrame],
    fail_rollout:    List[RolloutFrame],
    divergence_frame: Optional[int],
    failure_cause:    str,
) -> str:
    n          = len(success_rollout)
    W, H       = 700, 160
    div_frac   = divergence_frame / (n - 1) if divergence_frame is not None else None

    # --- cube_z SVG ---------------------------------------------------------
    sz    = [f.cube_z for f in success_rollout]
    fz    = [f.cube_z for f in fail_rollout]
    zmin  = min(min(sz), min(fz))
    zmax  = max(max(sz), max(fz))
    cubez_svg = (
        f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg">'
        + _svg_line(sz, W, H, "#22c55e", vmin=zmin, vmax=zmax)
        + _svg_line(fz, W, H, "#ef4444", vmin=zmin, vmax=zmax)
        + ((_svg_vline(div_frac, W, H)) if div_frac is not None else "")
        + f'<text x="8" y="14" fill="#22c55e" font-size="11">success</text>'
        + f'<text x="72" y="14" fill="#ef4444" font-size="11">fail</text>'
        + (f'<text x="{div_frac*W+4:.0f}" y="24" fill="#facc15" font-size="10">div@{divergence_frame}</text>' if div_frac else "")
        + "</svg>"
    )

    # --- gripper + confidence SVG -------------------------------------------
    gf_s  = [f.gripper_force    for f in success_rollout]
    pc_s  = [f.policy_confidence for f in success_rollout]
    gf_f  = [f.gripper_force    for f in fail_rollout]
    pc_f  = [f.policy_confidence for f in fail_rollout]

    dual_svg = (
        f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg">'
        + _svg_line(gf_s, W, H, "#38bdf8", vmin=0, vmax=10)
        + _svg_line(gf_f, W, H, "#f97316", vmin=0, vmax=10)
        + _svg_line(pc_s, W, H, "#a78bfa", vmin=0, vmax=1, stroke_width=1)
        + _svg_line(pc_f, W, H, "#fb7185", vmin=0, vmax=1, stroke_width=1)
        + ((_svg_vline(div_frac, W, H)) if div_frac is not None else "")
        + f'<text x="8"  y="14" fill="#38bdf8" font-size="10">gripper force (success)</text>'
        + f'<text x="8"  y="26" fill="#f97316" font-size="10">gripper force (fail)</text>'
        + f'<text x="8"  y="38" fill="#a78bfa" font-size="10">confidence (success)</text>'
        + f'<text x="8"  y="50" fill="#fb7185" font-size="10">confidence (fail)</text>'
        + "</svg>"
    )

    # --- heatmap ------------------------------------------------------------
    heatmap_svg = _heatmap_svg(fail_rollout)

    # --- phase timeline bar -------------------------------------------------
    BAR_W, BAR_H = 700, 36
    phase_bar_rects = []
    for phase, (lo, hi) in PHASE_RANGES.items():
        x     = lo / (n - 1) * BAR_W
        w     = (hi - lo) / (n - 1) * BAR_W
        color = PHASE_COLORS[phase]
        mid_x = x + w / 2
        phase_bar_rects.append(
            f'<rect x="{x:.1f}" y="0" width="{w:.1f}" height="{BAR_H}" fill="{color}" opacity="0.85"/>'
            f'<text x="{mid_x:.1f}" y="{BAR_H//2+5}" text-anchor="middle" fill="white" font-size="11" font-weight="600">{phase}</text>'
        )
    phase_svg = (
        f'<svg width="{BAR_W}" height="{BAR_H}" xmlns="http://www.w3.org/2000/svg">'
        + "".join(phase_bar_rects)
        + "</svg>"
    )

    # --- KPI cards ----------------------------------------------------------
    fail_frame_str = str(divergence_frame) if divergence_frame is not None else "N/A"
    kpi_html = f"""
    <div class="kpi-row">
      <div class="kpi-card">
        <div class="kpi-label">Episode Result</div>
        <div class="kpi-value" style="color:#22c55e">SUCCESS</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Total Frames</div>
        <div class="kpi-value">{n}</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Failure Frame</div>
        <div class="kpi-value" style="color:#ef4444">{fail_frame_str}</div>
      </div>
    </div>
    """

    # --- failure attribution ------------------------------------------------
    fail_phase = _phase_for_frame(divergence_frame) if divergence_frame is not None else "N/A"
    conf_at_fail = (
        f"{fail_rollout[divergence_frame].policy_confidence:.2f}"
        if divergence_frame is not None else "N/A"
    )
    recommendation = (
        "Collect more DAgger demos in the lift phase with varied cube positions."
        if "lift" in failure_cause else
        "Review grasping demonstrations — gripper contact strategy may be suboptimal."
    )
    attr_html = f"""
    <div class="attr-box">
      <div class="attr-title">Failure Attribution</div>
      <table class="attr-table">
        <tr><td>Phase</td><td><span class="badge" style="background:{PHASE_COLORS.get(fail_phase,'#6b7280')}">{fail_phase}</span></td></tr>
        <tr><td>Divergence frame</td><td>{fail_frame_str}</td></tr>
        <tr><td>Confidence at failure</td><td>{conf_at_fail}</td></tr>
        <tr><td>Failure cause</td><td>{failure_cause}</td></tr>
        <tr><td>Recommendation</td><td>{recommendation}</td></tr>
      </table>
    </div>
    """

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Policy Rollout Visualizer</title>
<style>
  *, *::before, *::after {{ box-sizing: border-box; }}
  body {{
    margin: 0; padding: 20px 28px;
    background: #1e293b; color: #e2e8f0;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    font-size: 14px;
  }}
  h1 {{ color: #C74634; margin: 0 0 4px; font-size: 22px; letter-spacing: .3px; }}
  h2 {{ color: #C74634; font-size: 15px; margin: 24px 0 8px; border-bottom: 1px solid #334155; padding-bottom: 4px; }}
  .subtitle {{ color: #94a3b8; font-size: 12px; margin-bottom: 20px; }}
  .kpi-row {{ display: flex; gap: 16px; margin-bottom: 8px; }}
  .kpi-card {{
    background: #0f172a; border: 1px solid #334155; border-radius: 8px;
    padding: 14px 22px; min-width: 160px; text-align: center;
  }}
  .kpi-label {{ color: #94a3b8; font-size: 11px; text-transform: uppercase; letter-spacing: .8px; }}
  .kpi-value  {{ font-size: 28px; font-weight: 700; margin-top: 4px; color: #f1f5f9; }}
  .chart-wrap {{
    background: #0f172a; border: 1px solid #334155; border-radius: 8px;
    padding: 12px 14px; overflow-x: auto; margin-bottom: 8px;
  }}
  .chart-wrap svg {{ display: block; }}
  .attr-box {{
    background: #0f172a; border: 1px solid #475569; border-radius: 8px;
    padding: 16px 20px; margin-top: 8px;
  }}
  .attr-title {{ font-weight: 700; color: #C74634; margin-bottom: 10px; font-size: 15px; }}
  .attr-table {{ border-collapse: collapse; width: 100%; }}
  .attr-table td {{ padding: 5px 10px; vertical-align: top; }}
  .attr-table td:first-child {{ color: #94a3b8; width: 180px; white-space: nowrap; }}
  .badge {{
    display: inline-block; padding: 1px 8px; border-radius: 4px;
    font-size: 12px; font-weight: 600; color: white;
  }}
  .footer {{ margin-top: 28px; color: #475569; font-size: 11px; text-align: center; }}
</style>
</head>
<body>
<h1>Policy Rollout Visualizer</h1>
<div class="subtitle">DAgger policy debug report — comparing success vs failure trajectories</div>

<h2>Episode Summary</h2>
{kpi_html}

<h2>Cube Height Over Time (cube_z)</h2>
<div class="chart-wrap">{cubez_svg}</div>

<h2>Gripper Force + Policy Confidence</h2>
<div class="chart-wrap">{dual_svg}</div>

<h2>Joint Trajectory Heatmap (fail episode)</h2>
<div class="chart-wrap">{heatmap_svg}</div>

<h2>Phase Timeline</h2>
<div class="chart-wrap">{phase_svg}</div>

<h2>Failure Attribution</h2>
{attr_html}

<div class="footer">Generated by policy_rollout_visualizer.py &mdash; OCI Robot Cloud</div>
</body>
</html>
"""
    return html


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Policy rollout HTML visualizer")
    parser.add_argument("--mock",   action="store_true", help="Use mock/simulated data")
    parser.add_argument("--output", default="/tmp/policy_rollout_visualizer.html",
                        help="Output HTML path (default: /tmp/policy_rollout_visualizer.html)")
    parser.add_argument("--seed",   type=int, default=42, help="Random seed")
    args = parser.parse_args()

    print(f"[policy_rollout_visualizer] Generating rollouts (seed={args.seed}) ...")
    success_rollout = generate_rollout(success=True,  seed=args.seed,      n_frames=240)
    fail_rollout    = generate_rollout(success=False, seed=args.seed + 1,  n_frames=240)

    divergence_frame, failure_cause = compare_rollouts(success_rollout, fail_rollout)
    print(f"[policy_rollout_visualizer] Divergence at frame {divergence_frame}: {failure_cause}")

    html = build_html_report(success_rollout, fail_rollout, divergence_frame, failure_cause)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"[policy_rollout_visualizer] Report saved → {args.output}")


if __name__ == "__main__":
    main()
