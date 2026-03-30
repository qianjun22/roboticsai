#!/usr/bin/env python3
"""
Curriculum-Aware Evaluation Script.

Tests a GR00T checkpoint across 4 difficulty levels matching the curriculum SDG
pipeline. Runs batch eval at each level, reports per-level and aggregate success
rates, and generates an HTML report.

Levels (aligned with curriculum_sdg.py stages, extended to 4):
  Level 1 Easy   — cube within 2cm of center, no lighting variation, no rotation
  Level 2 Medium — cube ±5cm offset, mild lighting, ±15° rotation
  Level 3 Hard   — cube ±10cm offset, strong lighting variation, ±30° rotation
  Level 4 Expert — cube ±15cm offset, random lighting, ±45° rotation, distractors

Usage:
    python3 curriculum_eval.py --mock --checkpoint /path/to/ckpt --episodes 20
    python3 curriculum_eval.py --mock --output /tmp/curriculum_eval_report.html
"""

import argparse
import json
import math
import random
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# ── Level definitions ─────────────────────────────────────────────────────────

LEVELS = [
    {
        "id": 1,
        "name": "Easy",
        "cube_offset_cm": 2.0,
        "lighting": "none",
        "rotation_deg": 0.0,
        "distractors": False,
        "description": "Cube within 2 cm of center, no lighting variation, no rotation",
        "mock_success_rate": 0.40,
        "weight": 0.1,
    },
    {
        "id": 2,
        "name": "Medium",
        "cube_offset_cm": 5.0,
        "lighting": "mild",
        "rotation_deg": 15.0,
        "distractors": False,
        "description": "Cube ±5 cm offset, mild lighting, ±15° rotation",
        "mock_success_rate": 0.20,
        "weight": 0.2,
    },
    {
        "id": 3,
        "name": "Hard",
        "cube_offset_cm": 10.0,
        "lighting": "strong",
        "rotation_deg": 30.0,
        "distractors": False,
        "description": "Cube ±10 cm offset, strong lighting variation, ±30° rotation",
        "mock_success_rate": 0.08,
        "weight": 0.3,
    },
    {
        "id": 4,
        "name": "Expert",
        "cube_offset_cm": 15.0,
        "lighting": "random",
        "rotation_deg": 45.0,
        "distractors": True,
        "description": "Cube ±15 cm offset, random lighting, ±45° rotation, distractors",
        "mock_success_rate": 0.03,
        "weight": 0.4,
    },
]

LIFT_THRESHOLD_M = 0.78  # cube_z must exceed this to count as lifted (confirmed)

FAILURE_CAUSES = [
    "grasp_miss",
    "lift_incomplete",
    "drop_during_transport",
    "ik_failure",
    "collision",
    "timeout",
]

# ── Dataclasses ───────────────────────────────────────────────────────────────


@dataclass
class EpisodeResult:
    episode_idx: int
    level_id: int
    success: bool
    cube_z_final: float       # meters
    latency_ms: float
    failure_cause: Optional[str]  # None if success


@dataclass
class CurriculumResult:
    level: int
    level_name: str
    n_episodes: int
    success_rate: float
    avg_latency_ms: float
    failure_breakdown: Dict[str, int] = field(default_factory=dict)
    episodes: List[EpisodeResult] = field(default_factory=list)


# ── Mock evaluation ───────────────────────────────────────────────────────────


def mock_eval_level(
    level: dict,
    n_episodes: int,
    seed: int = 42,
) -> List[EpisodeResult]:
    """
    Simulate evaluation at a given curriculum level.

    Returns a list of EpisodeResult objects. Success rates reflect realistic
    performance for the current DAgger run5 checkpoint:
      L1=40%, L2=20%, L3=8%, L4=3%.
    """
    rng = random.Random(seed + level["id"] * 1000)
    base_sr = level["mock_success_rate"]

    # Latency baseline varies slightly by level (more complex scene = more ops)
    base_latency = 226.0 + level["id"] * 4.5

    results: List[EpisodeResult] = []
    for i in range(n_episodes):
        roll = rng.random()
        success = roll < base_sr

        # cube_z: successes lift past threshold; failures stay below
        if success:
            cube_z_final = LIFT_THRESHOLD_M + rng.uniform(0.005, 0.06)
        else:
            cube_z_final = rng.uniform(0.72, LIFT_THRESHOLD_M - 0.005)

        # Latency: normally distributed around base
        latency_ms = max(180.0, rng.gauss(base_latency, 18.0))

        if success:
            failure_cause = None
        else:
            # Weighted distribution of failure causes shifts with difficulty
            if level["id"] == 1:
                weights = [0.05, 0.50, 0.20, 0.10, 0.10, 0.05]
            elif level["id"] == 2:
                weights = [0.20, 0.35, 0.20, 0.10, 0.10, 0.05]
            elif level["id"] == 3:
                weights = [0.30, 0.25, 0.15, 0.12, 0.13, 0.05]
            else:
                weights = [0.35, 0.20, 0.10, 0.15, 0.15, 0.05]
            failure_cause = rng.choices(FAILURE_CAUSES, weights=weights, k=1)[0]

        results.append(
            EpisodeResult(
                episode_idx=i,
                level_id=level["id"],
                success=success,
                cube_z_final=round(cube_z_final, 4),
                latency_ms=round(latency_ms, 1),
                failure_cause=failure_cause,
            )
        )

    return results


# ── Scoring ───────────────────────────────────────────────────────────────────


def overall_curriculum_score(results: List[CurriculumResult]) -> float:
    """
    Weighted average across levels (L1×0.1 + L2×0.2 + L3×0.3 + L4×0.4).

    Returns a value in [0, 1]. Weights sum to 1.0, so no extra normalization
    is needed beyond ensuring the input success rates are already in [0, 1].
    """
    score = 0.0
    for cr in results:
        level_cfg = LEVELS[cr.level - 1]
        score += cr.success_rate * level_cfg["weight"]
    return score


def generalization_grade(score: float) -> str:
    """Map weighted score to letter grade."""
    if score >= 0.30:
        return "A"
    if score >= 0.15:
        return "B"
    if score >= 0.08:
        return "C"
    if score >= 0.03:
        return "D"
    return "F"


# ── Evaluation runner ─────────────────────────────────────────────────────────


def run_curriculum_eval(
    checkpoint: Optional[str],
    n_episodes: int,
    mock: bool,
    seed: int = 42,
) -> List[CurriculumResult]:
    """
    Run evaluation across all 4 curriculum levels.

    When mock=True, uses mock_eval_level(). Real inference (mock=False) requires
    the inference server running at localhost:8001 (not implemented here — extend
    as needed with requests to the FastAPI endpoint).
    """
    if not mock and checkpoint is None:
        raise ValueError("--checkpoint is required when not in --mock mode")

    curriculum_results: List[CurriculumResult] = []

    for level_cfg in LEVELS:
        lvl_id = level_cfg["id"]
        print(
            f"[curriculum_eval] Level {lvl_id} ({level_cfg['name']}) — "
            f"{n_episodes} episodes ..."
        )
        t0 = time.perf_counter()

        if mock:
            episodes = mock_eval_level(level_cfg, n_episodes, seed=seed)
        else:
            # Placeholder for real inference — extend to call inference server
            raise NotImplementedError(
                "Real inference not yet wired up. Run with --mock."
            )

        elapsed = time.perf_counter() - t0

        successes = [e for e in episodes if e.success]
        failures = [e for e in episodes if not e.success]

        success_rate = len(successes) / n_episodes if n_episodes > 0 else 0.0
        avg_latency = (
            sum(e.latency_ms for e in episodes) / len(episodes)
            if episodes
            else 0.0
        )

        # Failure breakdown
        breakdown: Dict[str, int] = {}
        for ep in failures:
            cause = ep.failure_cause or "unknown"
            breakdown[cause] = breakdown.get(cause, 0) + 1

        cr = CurriculumResult(
            level=lvl_id,
            level_name=level_cfg["name"],
            n_episodes=n_episodes,
            success_rate=round(success_rate, 4),
            avg_latency_ms=round(avg_latency, 1),
            failure_breakdown=breakdown,
            episodes=episodes,
        )
        curriculum_results.append(cr)

        n_success = len(successes)
        print(
            f"  -> {n_success}/{n_episodes} succeeded "
            f"({success_rate*100:.1f}%) | "
            f"avg latency {avg_latency:.1f} ms | "
            f"wall {elapsed:.1f}s"
        )
        if breakdown:
            top = sorted(breakdown.items(), key=lambda x: -x[1])
            print(f"     failure causes: {', '.join(f'{k}:{v}' for k,v in top)}")

    return curriculum_results


# ── HTML report ───────────────────────────────────────────────────────────────

_GRADE_COLOR = {
    "A": "#22c55e",
    "B": "#84cc16",
    "C": "#eab308",
    "D": "#f97316",
    "F": "#ef4444",
}

_LEVEL_COLORS = {
    1: "#38bdf8",   # sky-400
    2: "#a78bfa",   # violet-400
    3: "#fb923c",   # orange-400
    4: "#f87171",   # red-400
}


def _svg_stacked_bar(results: List[CurriculumResult]) -> str:
    """
    Build an SVG stacked bar chart (success/failure per level).
    Width 500, height 200, horizontal bars.
    """
    bar_h = 32
    gap = 12
    label_w = 60
    chart_w = 380
    total_h = len(results) * (bar_h + gap) + 20

    bars = []
    for i, cr in enumerate(results):
        y = 10 + i * (bar_h + gap)
        success_w = int(chart_w * cr.success_rate)
        fail_w = chart_w - success_w
        color = _LEVEL_COLORS[cr.level]

        bars.append(
            f'<text x="{label_w - 6}" y="{y + bar_h//2 + 5}" '
            f'text-anchor="end" fill="#94a3b8" font-size="12" '
            f'font-family="monospace">L{cr.level} {cr.level_name}</text>'
        )
        if success_w > 0:
            bars.append(
                f'<rect x="{label_w}" y="{y}" width="{success_w}" '
                f'height="{bar_h}" fill="{color}" rx="3"/>'
            )
        if fail_w > 0:
            bars.append(
                f'<rect x="{label_w + success_w}" y="{y}" width="{fail_w}" '
                f'height="{bar_h}" fill="#1e293b" rx="3"/>'
            )
        pct_text = f"{cr.success_rate*100:.1f}%"
        bars.append(
            f'<text x="{label_w + success_w + 6}" y="{y + bar_h//2 + 5}" '
            f'fill="#94a3b8" font-size="11" font-family="monospace">'
            f'{pct_text}</text>'
        )

    content = "\n".join(bars)
    return (
        f'<svg width="500" height="{total_h}" xmlns="http://www.w3.org/2000/svg">'
        f'{content}</svg>'
    )


def _failure_table(results: List[CurriculumResult]) -> str:
    causes = FAILURE_CAUSES
    header_cells = "".join(
        f'<th style="padding:6px 10px;text-align:center;color:#94a3b8">{c}</th>'
        for c in causes
    )
    rows = []
    for cr in results:
        cells = "".join(
            f'<td style="padding:6px 10px;text-align:center;color:#e2e8f0">'
            f'{cr.failure_breakdown.get(c, 0)}</td>'
            for c in causes
        )
        rows.append(
            f'<tr>'
            f'<td style="padding:6px 10px;color:{_LEVEL_COLORS[cr.level]};'
            f'font-weight:bold">L{cr.level} {cr.level_name}</td>'
            f'{cells}'
            f'</tr>'
        )
    rows_html = "\n".join(rows)
    return f"""
<table style="width:100%;border-collapse:collapse;background:#1e293b;
border-radius:8px;overflow:hidden;font-size:13px;font-family:monospace">
  <thead>
    <tr style="background:#0f172a">
      <th style="padding:6px 10px;text-align:left;color:#94a3b8">Level</th>
      {header_cells}
    </tr>
  </thead>
  <tbody>{rows_html}</tbody>
</table>
"""


def generate_html_report(
    results: List[CurriculumResult],
    score: float,
    grade: str,
    checkpoint: Optional[str],
    output_path: str,
) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ckpt_display = checkpoint or "(mock — no checkpoint)"
    grade_color = _GRADE_COLOR.get(grade, "#94a3b8")

    # Per-level summary rows
    level_rows = []
    for cr in results:
        color = _LEVEL_COLORS[cr.level]
        level_rows.append(
            f'<tr>'
            f'<td style="padding:8px 12px;color:{color};font-weight:bold">'
            f'L{cr.level} {cr.level_name}</td>'
            f'<td style="padding:8px 12px;text-align:right;color:#e2e8f0">'
            f'{cr.success_rate*100:.1f}%</td>'
            f'<td style="padding:8px 12px;text-align:right;color:#e2e8f0">'
            f'{cr.n_episodes - int(cr.success_rate*cr.n_episodes)}/'
            f'{cr.n_episodes}</td>'
            f'<td style="padding:8px 12px;text-align:right;color:#e2e8f0">'
            f'{cr.avg_latency_ms:.1f} ms</td>'
            f'</tr>'
        )
    level_rows_html = "\n".join(level_rows)

    svg_chart = _svg_stacked_bar(results)
    fail_table = _failure_table(results)

    # Key finding text
    best = max(results, key=lambda r: r.success_rate)
    worst = min(results, key=lambda r: r.success_rate)
    finding = (
        f"The policy achieves its highest success rate at "
        f"<strong>Level {best.level} ({best.level_name}): "
        f"{best.success_rate*100:.1f}%</strong> and drops sharply to "
        f"<strong>{worst.success_rate*100:.1f}%</strong> at "
        f"Level {worst.level} ({worst.level_name}). "
        f"The overall curriculum score of <strong>{score*100:.2f}%</strong> "
        f"(Grade {grade}) reflects limited generalization beyond easy "
        f"configurations, consistent with a DAgger run5 checkpoint trained on "
        f"~1000 demos. Increasing demo diversity at harder levels or running "
        f"additional DAgger iterations on L3/L4 is the recommended next step."
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Curriculum Evaluation Report</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background: #0f172a;
      color: #e2e8f0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      padding: 32px;
      line-height: 1.6;
    }}
    h1 {{ font-size: 24px; margin-bottom: 4px; color: #f8fafc; }}
    h2 {{ font-size: 16px; margin: 28px 0 10px; color: #94a3b8;
          text-transform: uppercase; letter-spacing: 0.05em; }}
    .meta {{ font-size: 13px; color: #64748b; margin-bottom: 32px; }}
    .card {{
      background: #1e293b;
      border-radius: 10px;
      padding: 20px 24px;
      margin-bottom: 24px;
    }}
    .grade-callout {{
      display: inline-block;
      font-size: 64px;
      font-weight: 900;
      color: {grade_color};
      line-height: 1;
      margin-right: 24px;
    }}
    .score-label {{
      font-size: 14px;
      color: #94a3b8;
      margin-top: 6px;
    }}
    .score-value {{
      font-size: 28px;
      font-weight: 700;
      color: #f8fafc;
    }}
    table {{ width: 100%; border-collapse: collapse; font-size: 14px;
             font-family: monospace; }}
    thead tr {{ background: #0f172a; }}
    th {{ padding: 8px 12px; text-align: right; color: #94a3b8; }}
    th:first-child {{ text-align: left; }}
    tbody tr:hover {{ background: #0f172a55; }}
    .finding {{
      background: #0f172a;
      border-left: 3px solid #38bdf8;
      border-radius: 0 6px 6px 0;
      padding: 14px 18px;
      font-size: 14px;
      color: #cbd5e1;
    }}
    .level-badge {{
      display: inline-block;
      width: 10px;
      height: 10px;
      border-radius: 50%;
      margin-right: 6px;
    }}
  </style>
</head>
<body>
  <h1>OCI Robot Cloud — Curriculum Evaluation Report</h1>
  <p class="meta">
    Generated: {timestamp} &nbsp;|&nbsp;
    Checkpoint: <code>{ckpt_display}</code>
  </p>

  <h2>Generalization Grade</h2>
  <div class="card" style="display:flex;align-items:center">
    <span class="grade-callout">{grade}</span>
    <div>
      <div class="score-value">{score*100:.2f}%</div>
      <div class="score-label">
        Overall Curriculum Score<br/>
        (L1×0.1 + L2×0.2 + L3×0.3 + L4×0.4)
      </div>
    </div>
  </div>

  <h2>Per-Level Success Rate</h2>
  <div class="card">
    {svg_chart}
  </div>

  <h2>Per-Level Summary</h2>
  <div class="card">
    <table>
      <thead>
        <tr>
          <th style="text-align:left">Level</th>
          <th>Success Rate</th>
          <th>Failures / Total</th>
          <th>Avg Latency</th>
        </tr>
      </thead>
      <tbody>
        {level_rows_html}
      </tbody>
    </table>
  </div>

  <h2>Failure Breakdown by Cause</h2>
  <div class="card">
    {fail_table}
  </div>

  <h2>Key Finding</h2>
  <div class="card">
    <div class="finding">{finding}</div>
  </div>
</body>
</html>
"""

    Path(output_path).write_text(html, encoding="utf-8")
    print(f"[curriculum_eval] HTML report saved to {output_path}")


# ── CLI ───────────────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Curriculum-aware GR00T checkpoint evaluation across 4 difficulty levels.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--checkpoint",
        type=str,
        default=None,
        help="Path to GR00T checkpoint directory (required unless --mock)",
    )
    parser.add_argument(
        "--episodes",
        type=int,
        default=20,
        help="Number of episodes per difficulty level",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use mock inference (no real robot/sim required)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="/tmp/curriculum_eval_report.html",
        help="Output path for HTML report",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for mock evaluation",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("OCI Robot Cloud — Curriculum Evaluation")
    print(f"Levels: {len(LEVELS)} | Episodes per level: {args.episodes}")
    print(f"Mode: {'mock' if args.mock else 'real'}")
    if args.checkpoint:
        print(f"Checkpoint: {args.checkpoint}")
    print("=" * 60)

    try:
        results = run_curriculum_eval(
            checkpoint=args.checkpoint,
            n_episodes=args.episodes,
            mock=args.mock,
            seed=args.seed,
        )
    except NotImplementedError as exc:
        print(f"[ERROR] {exc}")
        return 1
    except Exception as exc:
        print(f"[ERROR] Evaluation failed: {exc}")
        return 1

    score = overall_curriculum_score(results)
    grade = generalization_grade(score)

    print()
    print("=" * 60)
    print("CURRICULUM EVALUATION SUMMARY")
    print("=" * 60)
    for cr in results:
        print(
            f"  Level {cr.level} {cr.level_name:<8} "
            f"success={cr.success_rate*100:5.1f}%  "
            f"latency={cr.avg_latency_ms:.1f}ms"
        )
    print(f"\n  Overall Score : {score*100:.2f}%")
    print(f"  Grade         : {grade}")
    print("=" * 60)

    generate_html_report(
        results=results,
        score=score,
        grade=grade,
        checkpoint=args.checkpoint,
        output_path=args.output,
    )

    # Exit code 1 if complete failure (score below minimum threshold)
    if score < 0.05:
        print(
            f"[curriculum_eval] WARN: overall score {score:.4f} < 0.05 "
            f"— exiting with code 1 (complete failure)"
        )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
