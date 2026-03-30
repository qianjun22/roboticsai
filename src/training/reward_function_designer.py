"""Reward function design and evaluation for GR00T RL fine-tuning.
Compares shaping strategies and convergence properties.
"""

from __future__ import annotations

import argparse
import math
import random
from dataclasses import dataclass, field
from typing import List, Optional


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class RewardComponent:
    name: str
    weight: float
    formula_desc: str
    range_min: float
    range_max: float


@dataclass
class RewardFunction:
    name: str
    components: List[RewardComponent]
    total_weight: float


@dataclass
class RLResult:
    reward_fn_name: str
    final_sr: float
    convergence_iters: int
    avg_reward: float
    reward_variance: float
    sr_at_50iter: float
    sr_at_100iter: float
    sr_curve: List[float] = field(default_factory=list)  # SR every 10 iters, 200 total


@dataclass
class RewardReport:
    best_fn: str
    fastest_convergence_fn: str
    results: List[RLResult]


# ---------------------------------------------------------------------------
# Reward function definitions
# ---------------------------------------------------------------------------

def build_reward_functions() -> List[RewardFunction]:
    sparse = RewardFunction(
        name="sparse",
        components=[
            RewardComponent(
                name="task_success",
                weight=1.0,
                formula_desc="+1.0 if object placed in goal region, else 0",
                range_min=0.0,
                range_max=1.0,
            )
        ],
        total_weight=1.0,
    )

    dense_distance = RewardFunction(
        name="dense_distance",
        components=[
            RewardComponent(
                name="gripper_to_object",
                weight=0.4,
                formula_desc="exp(-3 * dist(gripper, object))",
                range_min=0.0,
                range_max=0.4,
            ),
            RewardComponent(
                name="object_to_goal",
                weight=0.6,
                formula_desc="exp(-5 * dist(object, goal))",
                range_min=0.0,
                range_max=0.6,
            ),
        ],
        total_weight=1.0,
    )

    dense_plus_sparse = RewardFunction(
        name="dense_plus_sparse",
        components=[
            RewardComponent(
                name="gripper_to_object",
                weight=0.25,
                formula_desc="exp(-3 * dist(gripper, object))",
                range_min=0.0,
                range_max=0.25,
            ),
            RewardComponent(
                name="object_to_goal",
                weight=0.35,
                formula_desc="exp(-5 * dist(object, goal))",
                range_min=0.0,
                range_max=0.35,
            ),
            RewardComponent(
                name="success_bonus",
                weight=0.4,
                formula_desc="+0.4 on task completion",
                range_min=0.0,
                range_max=0.4,
            ),
        ],
        total_weight=1.0,
    )

    potential_based = RewardFunction(
        name="potential_based",
        components=[
            RewardComponent(
                name="potential_shaping",
                weight=0.5,
                formula_desc="gamma*Phi(s') - Phi(s); Phi = -dist(obj,goal)",
                range_min=-0.5,
                range_max=0.5,
            ),
            RewardComponent(
                name="task_success",
                weight=0.5,
                formula_desc="+0.5 on goal achievement",
                range_min=0.0,
                range_max=0.5,
            ),
        ],
        total_weight=1.0,
    )

    curriculum = RewardFunction(
        name="curriculum",
        components=[
            RewardComponent(
                name="sparse_base",
                weight=0.6,
                formula_desc="+0.6 success; weight decays to 0.2 over training",
                range_min=0.0,
                range_max=0.6,
            ),
            RewardComponent(
                name="shaping_ramp",
                weight=0.4,
                formula_desc="distance reward; weight grows from 0.1 to 0.8 over training",
                range_min=0.0,
                range_max=0.4,
            ),
        ],
        total_weight=1.0,
    )

    return [sparse, dense_distance, dense_plus_sparse, potential_based, curriculum]


# ---------------------------------------------------------------------------
# Convergence simulation
# ---------------------------------------------------------------------------

def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def simulate_convergence(
    reward_fn: RewardFunction,
    seed: int = 42,
    n_iters: int = 200,
) -> List[float]:
    """Return SR curve sampled every 10 iterations (20 values total)."""
    rng = random.Random(seed)

    # Per-function target parameters (final SR, inflection point, steepness)
    params = {
        "sparse":           (0.71, 180, 0.04),
        "dense_distance":   (0.78, 100, 0.06),
        "dense_plus_sparse":(0.81, 90,  0.07),
        "potential_based":  (0.84, 120, 0.05),
        "curriculum":       (0.80, 110, 0.06),
    }

    final_sr, inflection, steepness = params.get(
        reward_fn.name, (0.75, 130, 0.05)
    )

    curve = []
    for step in range(10, n_iters + 1, 10):
        base = final_sr * _sigmoid(steepness * (step - inflection))
        noise = rng.gauss(0, 0.015)
        sr = max(0.0, min(1.0, base + noise))
        curve.append(round(sr, 4))
    return curve


def _convergence_iter(curve: List[float], threshold: float = 0.95) -> int:
    """Return iteration number at which SR first reaches threshold * final_sr."""
    if not curve:
        return 200
    target = threshold * curve[-1]
    for i, sr in enumerate(curve):
        if sr >= target:
            return (i + 1) * 10
    return 200


def evaluate_reward_function(
    reward_fn: RewardFunction, seed: int = 42
) -> RLResult:
    curve = simulate_convergence(reward_fn, seed=seed)
    final_sr = curve[-1]
    convergence_iters = _convergence_iter(curve)
    avg_reward = round(sum(curve) / len(curve), 4)
    variance = round(
        sum((v - avg_reward) ** 2 for v in curve) / len(curve), 6
    )
    sr_at_50 = curve[4] if len(curve) > 4 else 0.0   # index 4 = 50 iters
    sr_at_100 = curve[9] if len(curve) > 9 else 0.0  # index 9 = 100 iters

    return RLResult(
        reward_fn_name=reward_fn.name,
        final_sr=final_sr,
        convergence_iters=convergence_iters,
        avg_reward=avg_reward,
        reward_variance=variance,
        sr_at_50iter=round(sr_at_50, 4),
        sr_at_100iter=round(sr_at_100, 4),
        sr_curve=curve,
    )


def build_report(
    reward_fns: List[RewardFunction], seed: int = 42
) -> RewardReport:
    results = [evaluate_reward_function(rf, seed=seed) for rf in reward_fns]
    best_fn = max(results, key=lambda r: r.final_sr).reward_fn_name
    fastest_fn = min(results, key=lambda r: r.convergence_iters).reward_fn_name
    return RewardReport(
        best_fn=best_fn,
        fastest_convergence_fn=fastest_fn,
        results=results,
    )


# ---------------------------------------------------------------------------
# HTML report
# ---------------------------------------------------------------------------

_COLORS = [
    "#C74634",  # Oracle red
    "#60a5fa",  # blue-400
    "#34d399",  # emerald-400
    "#fbbf24",  # amber-400
    "#a78bfa",  # violet-400
]

_LABEL_MAP = {
    "sparse": "Sparse",
    "dense_distance": "Dense Dist.",
    "dense_plus_sparse": "Dense+Sparse",
    "potential_based": "Potential-Based",
    "curriculum": "Curriculum",
}


def _build_convergence_svg(results: List[RLResult]) -> str:
    W, H = 600, 300
    PAD_L, PAD_R, PAD_T, PAD_B = 55, 20, 20, 45

    chart_w = W - PAD_L - PAD_R
    chart_h = H - PAD_T - PAD_B

    n_points = len(results[0].sr_curve)
    x_step = chart_w / (n_points - 1)

    def px(i: int) -> float:
        return PAD_L + i * x_step

    def py(sr: float) -> float:
        return PAD_T + chart_h * (1.0 - sr)

    lines = []
    # Grid lines
    for tick in [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]:
        y = py(tick)
        lines.append(
            f'<line x1="{PAD_L}" y1="{y:.1f}" x2="{W - PAD_R}" y2="{y:.1f}" '
            f'stroke="#334155" stroke-width="1"/>'
        )
        lines.append(
            f'<text x="{PAD_L - 6}" y="{y + 4:.1f}" fill="#94a3b8" '
            f'font-size="11" text-anchor="end">{tick:.1f}</text>'
        )

    # X-axis ticks
    for i in range(n_points):
        iter_val = (i + 1) * 10
        x = px(i)
        if iter_val % 50 == 0 or iter_val == 10:
            lines.append(
                f'<text x="{x:.1f}" y="{H - PAD_B + 16}" fill="#94a3b8" '
                f'font-size="11" text-anchor="middle">{iter_val}</text>'
            )

    # Curves
    for idx, result in enumerate(results):
        color = _COLORS[idx % len(_COLORS)]
        pts = " ".join(
            f"{px(i):.1f},{py(sr):.1f}"
            for i, sr in enumerate(result.sr_curve)
        )
        lines.append(
            f'<polyline points="{pts}" fill="none" stroke="{color}" '
            f'stroke-width="2.5" stroke-linejoin="round"/>'
        )

    # Legend
    for idx, result in enumerate(results):
        color = _COLORS[idx % len(_COLORS)]
        lx = PAD_L + idx * 110
        ly = H - 8
        lines.append(
            f'<rect x="{lx}" y="{ly - 8}" width="14" height="8" fill="{color}" rx="2"/>'
        )
        label = _LABEL_MAP.get(result.reward_fn_name, result.reward_fn_name)
        lines.append(
            f'<text x="{lx + 18}" y="{ly}" fill="#cbd5e1" font-size="10">{label}</text>'
        )

    # Axis labels
    lines.append(
        f'<text x="{W // 2}" y="{H - PAD_B + 32}" fill="#94a3b8" font-size="12" '
        f'text-anchor="middle">Training Iterations</text>'
    )
    lines.append(
        f'<text x="14" y="{H // 2}" fill="#94a3b8" font-size="12" '
        f'text-anchor="middle" transform="rotate(-90 14 {H // 2})">Success Rate</text>'
    )

    inner = "\n".join(lines)
    return (
        f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" '
        f'style="width:100%;max-width:{W}px;background:#0f172a;border-radius:8px;">'
        f'{inner}</svg>'
    )


def _build_component_bar_svg(reward_fns: List[RewardFunction]) -> str:
    W, H = 600, 280
    PAD_L, PAD_R, PAD_T, PAD_B = 130, 20, 20, 40

    chart_w = W - PAD_L - PAD_R
    chart_h = H - PAD_T - PAD_B

    n_fns = len(reward_fns)
    bar_h = (chart_h / n_fns) * 0.65
    bar_gap = chart_h / n_fns

    # Collect all unique component names for color assignment
    all_comp_names: list[str] = []
    for rf in reward_fns:
        for c in rf.components:
            if c.name not in all_comp_names:
                all_comp_names.append(c.name)

    comp_colors = {name: _COLORS[i % len(_COLORS)] for i, name in enumerate(all_comp_names)}

    lines = []

    # Grid
    for tick in [0.0, 0.25, 0.5, 0.75, 1.0]:
        x = PAD_L + tick * chart_w
        lines.append(
            f'<line x1="{x:.1f}" y1="{PAD_T}" x2="{x:.1f}" y2="{PAD_T + chart_h}" '
            f'stroke="#334155" stroke-width="1"/>'
        )
        lines.append(
            f'<text x="{x:.1f}" y="{H - PAD_B + 16}" fill="#94a3b8" '
            f'font-size="11" text-anchor="middle">{tick:.2f}</text>'
        )

    # Bars
    for i, rf in enumerate(reward_fns):
        y = PAD_T + i * bar_gap + (bar_gap - bar_h) / 2
        label = _LABEL_MAP.get(rf.name, rf.name)
        lines.append(
            f'<text x="{PAD_L - 8}" y="{y + bar_h / 2 + 4:.1f}" fill="#cbd5e1" '
            f'font-size="11" text-anchor="end">{label}</text>'
        )
        x_start = PAD_L
        for comp in rf.components:
            seg_w = comp.weight * chart_w
            color = comp_colors.get(comp.name, "#94a3b8")
            lines.append(
                f'<rect x="{x_start:.1f}" y="{y:.1f}" width="{seg_w:.1f}" '
                f'height="{bar_h:.1f}" fill="{color}" rx="2"/>'
            )
            if seg_w > 30:
                lines.append(
                    f'<text x="{x_start + seg_w / 2:.1f}" y="{y + bar_h / 2 + 4:.1f}" '
                    f'fill="#0f172a" font-size="10" font-weight="bold" text-anchor="middle">'
                    f'{comp.weight:.2f}</text>'
                )
            x_start += seg_w

    # Legend (unique components)
    leg_y = H - 12
    for idx, name in enumerate(all_comp_names):
        color = comp_colors[name]
        lx = PAD_L + idx * 130
        lines.append(
            f'<rect x="{lx}" y="{leg_y - 8}" width="12" height="8" fill="{color}" rx="2"/>'
        )
        lines.append(
            f'<text x="{lx + 16}" y="{leg_y}" fill="#cbd5e1" font-size="10">{name}</text>'
        )

    inner = "\n".join(lines)
    return (
        f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" '
        f'style="width:100%;max-width:{W}px;background:#0f172a;border-radius:8px;">'
        f'{inner}</svg>'
    )


def _build_html(
    report: RewardReport,
    reward_fns: List[RewardFunction],
) -> str:
    best_result = next(r for r in report.results if r.reward_fn_name == report.best_fn)
    fastest_result = next(
        r for r in report.results if r.reward_fn_name == report.fastest_convergence_fn
    )
    lowest_variance = min(report.results, key=lambda r: r.reward_variance)

    def card(title: str, value: str, sub: str) -> str:
        return f"""
        <div class="card">
          <div class="card-title">{title}</div>
          <div class="card-value">{value}</div>
          <div class="card-sub">{sub}</div>
        </div>"""

    cards = "".join([
        card("Best Final SR",
             f"{best_result.final_sr:.3f}",
             report.best_fn),
        card("Fastest Convergence",
             f"{fastest_result.convergence_iters} iters",
             report.fastest_convergence_fn),
        card("Lowest Reward Variance",
             f"{lowest_variance.reward_variance:.6f}",
             lowest_variance.reward_fn_name),
        card("Recommended",
             report.best_fn,
             "highest SR + good convergence"),
    ])

    def tr(result: RLResult) -> str:
        return (
            f"<tr>"
            f"<td>{result.reward_fn_name}</td>"
            f"<td>{result.final_sr:.4f}</td>"
            f"<td>{result.convergence_iters}</td>"
            f"<td>{result.avg_reward:.4f}</td>"
            f"<td>{result.reward_variance:.6f}</td>"
            f"<td>{result.sr_at_50iter:.4f}</td>"
            f"<td>{result.sr_at_100iter:.4f}</td>"
            f"</tr>"
        )

    table_rows = "\n".join(tr(r) for r in report.results)

    # Component detail tables
    comp_sections = []
    for rf in reward_fns:
        rows = ""
        for c in rf.components:
            rows += (
                f"<tr><td>{c.name}</td><td>{c.weight}</td>"
                f"<td>{c.formula_desc}</td>"
                f"<td>[{c.range_min}, {c.range_max}]</td></tr>"
            )
        comp_sections.append(f"""
        <div class="section">
          <h3>{rf.name} <span class="badge">total weight: {rf.total_weight}</span></h3>
          <table>
            <thead><tr>
              <th>Component</th><th>Weight</th><th>Formula</th><th>Range</th>
            </tr></thead>
            <tbody>{rows}</tbody>
          </table>
        </div>""")

    comp_html = "\n".join(comp_sections)

    convergence_svg = _build_convergence_svg(report.results)
    bar_svg = _build_component_bar_svg(reward_fns)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Reward Function Designer — GR00T RL Fine-Tuning</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: #1e293b;
    color: #e2e8f0;
    font-family: system-ui, -apple-system, sans-serif;
    padding: 24px;
    line-height: 1.5;
  }}
  h1 {{ color: #f8fafc; font-size: 1.6rem; margin-bottom: 4px; }}
  h2 {{ color: #94a3b8; font-size: 1rem; font-weight: 400; margin-bottom: 24px; }}
  h3 {{ color: #cbd5e1; font-size: 1rem; margin-bottom: 12px; }}
  .badge {{
    background: #334155; color: #94a3b8; font-size: 0.75rem;
    padding: 2px 8px; border-radius: 9999px; font-weight: 400;
  }}
  .header-bar {{
    border-left: 4px solid #C74634;
    padding-left: 14px;
    margin-bottom: 28px;
  }}
  .cards {{ display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 32px; }}
  .card {{
    background: #0f172a; border: 1px solid #334155;
    border-radius: 10px; padding: 18px 22px; flex: 1; min-width: 180px;
  }}
  .card-title {{ color: #94a3b8; font-size: 0.78rem; text-transform: uppercase;
    letter-spacing: .05em; margin-bottom: 6px; }}
  .card-value {{ color: #C74634; font-size: 1.9rem; font-weight: 700; }}
  .card-sub {{ color: #64748b; font-size: 0.8rem; margin-top: 4px; }}
  .section {{ margin-bottom: 36px; }}
  .section > h3 {{ margin-bottom: 12px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.875rem; }}
  th {{
    background: #0f172a; color: #94a3b8; font-weight: 600;
    text-transform: uppercase; font-size: 0.75rem; letter-spacing: .04em;
    padding: 10px 14px; border-bottom: 1px solid #334155; text-align: left;
  }}
  td {{ padding: 9px 14px; border-bottom: 1px solid #1e293b; color: #cbd5e1; }}
  tr:hover td {{ background: #0f172a44; }}
  .chart-wrap {{ margin-bottom: 12px; }}
  .divider {{ border: none; border-top: 1px solid #334155; margin: 32px 0; }}
</style>
</head>
<body>
<div class="header-bar">
  <h1>Reward Function Designer</h1>
  <h2>GR00T RL Fine-Tuning — Pick &amp; Place Task — Shaping Strategy Comparison</h2>
</div>

<div class="cards">
{cards}
</div>

<hr class="divider"/>

<div class="section">
  <h3>Convergence Curves <span class="badge">success rate vs. training iterations</span></h3>
  <div class="chart-wrap">{convergence_svg}</div>
</div>

<div class="section">
  <h3>Reward Component Breakdown <span class="badge">stacked weight per function</span></h3>
  <div class="chart-wrap">{bar_svg}</div>
</div>

<hr class="divider"/>

<div class="section">
  <h3>Summary Table</h3>
  <table>
    <thead><tr>
      <th>Reward Fn</th>
      <th>Final SR</th>
      <th>Conv. Iters</th>
      <th>Avg Reward</th>
      <th>Variance</th>
      <th>SR@50</th>
      <th>SR@100</th>
    </tr></thead>
    <tbody>
{table_rows}
    </tbody>
  </table>
</div>

<hr class="divider"/>

<div class="section">
  <h3>Component Detail</h3>
  {comp_html}
</div>

</body>
</html>"""


# ---------------------------------------------------------------------------
# CLI helpers
# ---------------------------------------------------------------------------

def print_results_table(results: List[RLResult]) -> None:
    header = (
        f"{'Reward Fn':<22} {'Final SR':>9} {'Conv Iters':>11} "
        f"{'Avg Reward':>11} {'Variance':>12} {'SR@50':>7} {'SR@100':>8}"
    )
    sep = "-" * len(header)
    print(sep)
    print(header)
    print(sep)
    for r in results:
        print(
            f"{r.reward_fn_name:<22} {r.final_sr:>9.4f} {r.convergence_iters:>11} "
            f"{r.avg_reward:>11.4f} {r.reward_variance:>12.6f} "
            f"{r.sr_at_50iter:>7.4f} {r.sr_at_100iter:>8.4f}"
        )
    print(sep)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Design and evaluate reward functions for GR00T RL fine-tuning."
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use deterministic mock simulation (no real training).",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="/tmp/reward_function_designer.html",
        help="Path for HTML report output.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for simulation noise.",
    )
    args = parser.parse_args()

    print("=== Reward Function Designer — GR00T RL Fine-Tuning ===")
    print(f"Task       : pick_and_place")
    print(f"Seed       : {args.seed}")
    print(f"Mode       : {'mock simulation' if args.mock else 'mock simulation'}")
    print()

    reward_fns = build_reward_functions()
    print(f"Evaluating {len(reward_fns)} reward functions ...")
    report = build_report(reward_fns, seed=args.seed)

    print_results_table(report.results)
    print()
    print(f"  Best final SR          : {report.best_fn}")
    print(f"  Fastest convergence    : {report.fastest_convergence_fn}")
    best_result = next(r for r in report.results if r.reward_fn_name == report.best_fn)
    print(f"  Best SR                : {best_result.final_sr:.4f}")
    print()

    html = _build_html(report, reward_fns)
    with open(args.output, "w", encoding="utf-8") as fh:
        fh.write(html)
    print(f"HTML report saved to: {args.output}")


if __name__ == "__main__":
    main()
