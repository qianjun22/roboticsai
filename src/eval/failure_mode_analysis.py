#!/usr/bin/env python3
"""
failure_mode_analysis.py — Analyzes where in an episode the policy fails.

Breaks the pick-and-lift task into 4 phases and identifies which phase
the policy fails in most often. Critical for the GTC talk narrative:
"The model learned to reach but struggled with grasp" → target DAgger collection there.

Phases (based on Franka Panda joint state + cube position):
  1. Approach: end-effector moving toward cube (frames 0 → grasp contact)
  2. Grasp:    gripper closing on cube
  3. Lift:     cube z-height increasing
  4. Hold:     cube held above LIFT_THRESHOLD=0.78m

Usage:
    # Analyze a single eval run
    python src/eval/failure_mode_analysis.py --eval-dir /tmp/eval_1000demo

    # Compare two runs
    python src/eval/failure_mode_analysis.py \
        --eval-dirs /tmp/eval_1000demo /tmp/eval_dagger_final \
        --labels "1000-demo BC" "DAgger Final" \
        --output /tmp/failure_analysis.html

    # Mock mode (no real eval data needed)
    python src/eval/failure_mode_analysis.py --mock --output /tmp/failure_analysis.html
"""

import argparse
import json
import math
import random
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ── Constants ────────────────────────────────────────────────────────────────
TABLE_Z = 0.700
LIFT_THRESHOLD = TABLE_Z + 0.08  # = 0.780m

# Phase thresholds (cube z-height as proxy for phase)
PHASE_APPROACH_THRESHOLD = 0.710  # cube still on table, hand approaching
PHASE_GRASP_THRESHOLD = 0.730     # gripper making contact / slight displacement
PHASE_LIFT_THRESHOLD = LIFT_THRESHOLD  # lifting
PHASE_SUCCESS = LIFT_THRESHOLD    # success


def classify_phase(final_cube_z: float, max_cube_z: float) -> str:
    """Classify which phase the policy failed in based on cube trajectory."""
    if final_cube_z >= LIFT_THRESHOLD:
        return "success"
    if final_cube_z < TABLE_Z - 0.01:
        # Cube went below table (knocked off)
        return "knocked_off"
    if max_cube_z >= LIFT_THRESHOLD:
        # Was lifted but dropped
        return "dropped_during_hold"
    if max_cube_z >= PHASE_GRASP_THRESHOLD:
        # Grasped but failed to lift
        return "failed_lift"
    if max_cube_z >= PHASE_APPROACH_THRESHOLD:
        # Made contact but failed to grasp
        return "failed_grasp"
    # Never reached cube
    return "failed_approach"


def phase_order() -> List[str]:
    return [
        "failed_approach",
        "failed_grasp",
        "failed_lift",
        "dropped_during_hold",
        "knocked_off",
        "success",
    ]


PHASE_COLORS = {
    "success": "#34D399",
    "dropped_during_hold": "#FBBF24",
    "failed_lift": "#F87171",
    "failed_grasp": "#C74634",
    "failed_approach": "#7C3AED",
    "knocked_off": "#374151",
}

PHASE_LABELS = {
    "success": "Success (cube ≥0.78m)",
    "dropped_during_hold": "Dropped during hold",
    "failed_lift": "Grasped but failed to lift",
    "failed_grasp": "Reached but failed to grasp",
    "failed_approach": "Never reached cube",
    "knocked_off": "Cube knocked off table",
}


def load_episodes(eval_dir: str) -> Optional[List[Dict]]:
    """Load per-episode data from eval_dir/episodes.json if available."""
    ep_path = Path(eval_dir) / "episodes.json"
    if ep_path.exists():
        try:
            return json.loads(ep_path.read_text())
        except Exception:
            pass
    # Fall back to summary.json (limited info)
    summary_path = Path(eval_dir) / "summary.json"
    if summary_path.exists():
        try:
            summary = json.loads(summary_path.read_text())
            # Reconstruct episode list from category counts
            episodes = []
            cats = summary.get("failure_categories", {})
            for phase in phase_order():
                count = cats.get(phase, 0)
                for _ in range(count):
                    episodes.append({"phase": phase})
            return episodes
        except Exception:
            pass
    return None


def generate_mock_episodes(
    n: int,
    distribution: Dict[str, float],
) -> List[Dict]:
    """Generate synthetic episodes with the given failure phase distribution."""
    phases = list(distribution.keys())
    weights = list(distribution.values())
    episodes = []
    for i in range(n):
        phase = random.choices(phases, weights=weights, k=1)[0]
        if phase == "success":
            final_z = random.uniform(LIFT_THRESHOLD, LIFT_THRESHOLD + 0.05)
            max_z = final_z + random.uniform(0, 0.02)
        elif phase == "knocked_off":
            final_z = TABLE_Z - random.uniform(0.02, 0.10)
            max_z = TABLE_Z + random.uniform(0.01, 0.03)
        elif phase == "failed_approach":
            final_z = TABLE_Z + random.uniform(-0.005, 0.005)
            max_z = TABLE_Z + random.uniform(0, 0.005)
        elif phase == "failed_grasp":
            final_z = TABLE_Z + random.uniform(0, 0.01)
            max_z = TABLE_Z + random.uniform(0.01, 0.025)
        elif phase == "failed_lift":
            final_z = TABLE_Z + random.uniform(0.01, 0.04)
            max_z = TABLE_Z + random.uniform(0.04, 0.06)
        else:  # dropped_during_hold
            max_z = LIFT_THRESHOLD + random.uniform(0.01, 0.04)
            final_z = TABLE_Z + random.uniform(0.02, 0.05)
        episodes.append({
            "episode_id": i,
            "final_cube_z": final_z,
            "max_cube_z": max_z,
            "phase": phase,
        })
    return episodes


def analyze_episodes(episodes: List[Dict]) -> Dict[str, int]:
    counts = {p: 0 for p in phase_order()}
    for ep in episodes:
        # Use pre-classified phase if available, else classify from cube_z
        if "phase" in ep:
            ph = ep["phase"]
        elif "final_cube_z" in ep and "max_cube_z" in ep:
            ph = classify_phase(ep["final_cube_z"], ep["max_cube_z"])
        else:
            ph = "failed_approach"
        if ph in counts:
            counts[ph] += 1
    return counts


def make_html_report(
    run_names: List[str],
    counts_list: List[Dict[str, int]],
    n_episodes_list: List[int],
    output_path: str,
) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Build bar chart comparison
    charts = ""
    for name, counts, n in zip(run_names, counts_list, n_episodes_list):
        success = counts.get("success", 0)
        pct = success / n * 100 if n > 0 else 0
        bars = ""
        for phase in reversed(phase_order()):
            c = counts.get(phase, 0)
            w = c / n * 100 if n > 0 else 0
            if c == 0:
                continue
            color = PHASE_COLORS[phase]
            label = PHASE_LABELS[phase]
            bars += f"""
        <div style="display:flex;align-items:center;gap:12px;margin-bottom:6px;">
          <div style="width:180px;font-size:11px;color:#9CA3AF;text-align:right;">{label}</div>
          <div style="background:{color};height:20px;width:{max(4, w*3):.0f}px;border-radius:3px;"></div>
          <div style="font-size:11px;color:{color};">{c}/{n} ({w:.0f}%)</div>
        </div>"""

        charts += f"""
      <div style="background:#1C1C1E;border-radius:10px;padding:20px;margin-bottom:16px;">
        <div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:16px;">
          <div style="font-size:15px;font-weight:600;color:#E5E7EB;">{name}</div>
          <div style="font-size:22px;font-weight:700;color:#34D399;">{pct:.0f}% success</div>
        </div>
        {bars}
      </div>"""

    # Insight box
    if len(run_names) >= 2:
        c1 = counts_list[0]
        c2 = counts_list[1]
        n1, n2 = n_episodes_list[0], n_episodes_list[1]

        def _rate(c, ph, n):
            return c.get(ph, 0) / n * 100 if n > 0 else 0

        insights = []
        for ph in ["failed_approach", "knocked_off", "failed_grasp", "failed_lift"]:
            r1 = _rate(c1, ph, n1)
            r2 = _rate(c2, ph, n2)
            if r1 > 0 and r2 < r1 - 5:
                insights.append(
                    f"{PHASE_LABELS[ph]}: {r1:.0f}% → {r2:.0f}% ({r1 - r2:.0f}pp improvement)"
                )
        insight_html = ""
        if insights:
            items = "".join(f"<li>{i}</li>" for i in insights)
            insight_html = f"""
      <div style="background:#0F2027;border:1px solid #34D399;border-radius:8px;padding:16px;margin-bottom:20px;">
        <div style="color:#34D399;font-weight:600;font-size:12px;text-transform:uppercase;letter-spacing:1px;margin-bottom:8px;">Key Improvements</div>
        <ul style="color:#E5E7EB;font-size:13px;margin-left:16px;">{items}</ul>
      </div>"""
    else:
        insight_html = ""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Failure Mode Analysis — OCI Robot Cloud</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #111113; color: #E5E7EB; font-family: 'Segoe UI', system-ui, sans-serif; padding: 40px 20px; }}
  .container {{ max-width: 780px; margin: 0 auto; }}
  h1 {{ font-size: 26px; color: #FFFFFF; margin-bottom: 4px; }}
  h2 {{ font-size: 13px; color: #C74634; text-transform: uppercase; letter-spacing: 2px; margin: 28px 0 14px; }}
  .subtitle {{ color: #9CA3AF; font-size: 14px; margin-bottom: 32px; }}
  .footer {{ color: #4B5563; font-size: 11px; margin-top: 40px; text-align: center; }}
  .legend {{ display:flex;flex-wrap:wrap;gap:12px;margin-bottom:20px; }}
  .legend-item {{ display:flex;align-items:center;gap:6px; }}
  .legend-dot {{ width:10px;height:10px;border-radius:50%; }}
</style>
</head>
<body>
<div class="container">
  <h2>OCI Robot Cloud · Eval Analysis</h2>
  <h1>Failure Mode Analysis</h1>
  <p class="subtitle">Where in the pick-and-lift episode does the policy fail? · GR00T N1.6-3B · Genesis sim</p>

  {insight_html}

  <h2>Legend</h2>
  <div class="legend">
    {''.join(f'<div class="legend-item"><div class="legend-dot" style="background:{PHASE_COLORS[p]};"></div><span style="font-size:11px;color:#9CA3AF;">{PHASE_LABELS[p]}</span></div>' for p in phase_order())}
  </div>

  <h2>Failure Distribution by Run</h2>
  {charts}

  <div class="footer">
    OCI Robot Cloud · Jun Qian · Generated {ts}
  </div>
</div>
</body>
</html>"""

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(html)


def main() -> None:
    parser = argparse.ArgumentParser(description="Failure mode analysis for closed-loop eval")
    parser.add_argument("--eval-dir", help="Single eval output directory")
    parser.add_argument("--eval-dirs", nargs="*", default=[], help="Multiple eval dirs")
    parser.add_argument("--labels", nargs="*", default=[], help="Labels for each dir")
    parser.add_argument("--output", default="/tmp/failure_analysis.html")
    parser.add_argument("--mock", action="store_true",
                        help="Use synthetic data (BC=5%%, DAgger=65%%) for testing")
    args = parser.parse_args()

    if args.mock:
        # BC baseline distribution
        bc_episodes = generate_mock_episodes(20, {
            "success": 1, "knocked_off": 7, "failed_approach": 5,
            "failed_grasp": 4, "failed_lift": 2, "dropped_during_hold": 1,
        })
        # DAgger distribution (much better)
        dagger_episodes = generate_mock_episodes(20, {
            "success": 13, "knocked_off": 2, "failed_approach": 1,
            "failed_grasp": 2, "failed_lift": 1, "dropped_during_hold": 1,
        })
        runs = [("BC Baseline (5%)", bc_episodes, 20), ("DAgger Iter 3 (65%)", dagger_episodes, 20)]
    else:
        dirs = []
        if args.eval_dir:
            dirs = [args.eval_dir]
        elif args.eval_dirs:
            dirs = args.eval_dirs
        else:
            print("ERROR: provide --eval-dir, --eval-dirs, or --mock")
            return

        labels = args.labels
        while len(labels) < len(dirs):
            labels.append(f"Run {len(labels) + 1}")

        runs = []
        for label, d in zip(labels, dirs):
            eps = load_episodes(d)
            if eps is None:
                print(f"WARNING: no episode data found in {d}")
                eps = []
            runs.append((label, eps, len(eps) if eps else 20))

    run_names = [r[0] for r in runs]
    counts_list = [analyze_episodes(r[1]) for r in runs]
    n_list = [r[2] for r in runs]

    # Console summary
    print()
    print("Failure Mode Analysis")
    print("═" * 50)
    for name, counts, n in zip(run_names, counts_list, n_list):
        success = counts.get("success", 0)
        print(f"\n{name}  ({success}/{n} success, {success/n*100:.0f}%)")
        print("─" * 40)
        for ph in reversed(phase_order()):
            c = counts.get(ph, 0)
            if c > 0:
                bar = "█" * c + "░" * (n - c)
                print(f"  {PHASE_LABELS[ph]:<35}  {bar}  {c}/{n}")
    print()

    make_html_report(run_names, counts_list, n_list, args.output)
    print(f"Report written to: {args.output}")


if __name__ == "__main__":
    main()
