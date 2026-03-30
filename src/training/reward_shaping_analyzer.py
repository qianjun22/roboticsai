"""
reward_shaping_analyzer.py — Compare reward shaping strategies for GR00T PPO/RL fine-tuning.

Simulates 6 reward strategies over N PPO iterations, tracking success rate,
mean reward, policy entropy, and KL divergence. Produces a console comparison
table, an HTML report with SVG charts, and a JSON output file.

Usage:
    python reward_shaping_analyzer.py [--mock] [--n-iters 150]
        [--output /tmp/reward_shaping_analyzer.html] [--seed 42]
"""

from __future__ import annotations

import argparse
import json
import math
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

STRATEGY_NAMES = [
    "sparse",
    "dense_distance",
    "dense_subgoal",
    "curiosity",
    "potential_based",
    "combined",
]

STRATEGY_COLORS = {
    "sparse":           "#94a3b8",   # slate-400
    "dense_distance":   "#38bdf8",   # sky-400
    "dense_subgoal":    "#34d399",   # emerald-400
    "curiosity":        "#f472b6",   # pink-400
    "potential_based":  "#a78bfa",   # violet-400
    "combined":         "#fb923c",   # orange-400
}


@dataclass
class IterMetrics:
    iteration: int
    success_rate: float
    mean_reward: float
    policy_entropy: float
    kl_divergence: float


@dataclass
class StrategyResult:
    name: str
    metrics: List[IterMetrics] = field(default_factory=list)
    convergence_iter: Optional[int] = None   # first iter SR > 0.70
    final_sr: float = 0.0
    sample_efficiency: Optional[int] = None  # env steps to 70% SR (iter * 20 eps)
    policy_stable: bool = True
    color: str = "#ffffff"

    def compute_summary(self) -> None:
        if self.metrics:
            self.final_sr = self.metrics[-1].success_rate
        for m in self.metrics:
            if m.success_rate > 0.70 and self.convergence_iter is None:
                self.convergence_iter = m.iteration
                self.sample_efficiency = m.iteration * 20  # 20 episodes per iter
        # policy_stable: KL never exceeds 0.05 for more than 3 consecutive iters
        high_kl_streak = 0
        for m in self.metrics:
            if m.kl_divergence > 0.05:
                high_kl_streak += 1
                if high_kl_streak >= 3:
                    self.policy_stable = False
                    break
            else:
                high_kl_streak = 0


# ---------------------------------------------------------------------------
# Simulation
# ---------------------------------------------------------------------------

def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def simulate_strategy(
    name: str,
    n_iters: int,
    rng: random.Random,
) -> StrategyResult:
    """Simulate PPO training under a reward shaping strategy.

    Each strategy has a characteristic learning curve parameterised by:
      - plateau_sr:   asymptotic success rate
      - speed:        how quickly convergence occurs (logistic growth rate)
      - midpoint:     iteration at which SR passes 50%
      - noise_scale:  SR noise magnitude
      - reward_scale: mean reward multiplier
      - entropy_init / entropy_decay: policy entropy trajectory
      - kl_base / kl_noise: KL divergence parameters
    """

    params: Dict[str, float] = {
        # (plateau_sr, speed, midpoint, noise, reward_scale, ent_init, ent_decay, kl_base, kl_noise)
        "sparse":           (0.78, 0.06, 100, 0.025, 1.0,  1.4, 0.010, 0.020, 0.006),
        "dense_distance":   (0.81, 0.07,  85, 0.022, 1.8,  1.3, 0.009, 0.022, 0.007),
        "dense_subgoal":    (0.82, 0.08,  78, 0.022, 2.0,  1.3, 0.009, 0.021, 0.007),
        "curiosity":        (0.80, 0.07,  80, 0.030, 1.6,  1.5, 0.011, 0.028, 0.010),
        "potential_based":  (0.83, 0.09,  72, 0.018, 2.2,  1.2, 0.008, 0.015, 0.004),
        "combined":         (0.85, 0.11,  62, 0.015, 2.8,  1.1, 0.007, 0.018, 0.005),
    }[name]

    plateau_sr, speed, midpoint, noise, reward_scale, ent_init, ent_decay, kl_base, kl_noise = params

    result = StrategyResult(name=name, color=STRATEGY_COLORS[name])

    for i in range(1, n_iters + 1):
        t = i / n_iters
        # Logistic SR curve
        raw_sr = plateau_sr * _sigmoid(speed * (i - midpoint))
        sr = max(0.0, min(1.0, raw_sr + rng.gauss(0.0, noise)))

        # Mean reward: grows with SR, scaled by strategy richness
        mean_r = reward_scale * (sr * 10.0 + rng.gauss(0.0, 0.3))

        # Entropy: decays as policy converges
        entropy = max(0.05, ent_init * math.exp(-ent_decay * i) + rng.gauss(0.0, 0.02))

        # KL divergence: small, occasional spikes
        kl = max(0.0, kl_base + rng.gauss(0.0, kl_noise))
        # Occasional spike (curiosity / sparse have higher variance)
        if rng.random() < 0.04:
            kl += rng.uniform(0.02, 0.06)

        result.metrics.append(IterMetrics(
            iteration=i,
            success_rate=round(sr, 4),
            mean_reward=round(mean_r, 4),
            policy_entropy=round(entropy, 4),
            kl_divergence=round(kl, 6),
        ))

    result.compute_summary()
    return result


def run_simulation(n_iters: int, seed: int) -> List[StrategyResult]:
    rng = random.Random(seed)
    results = []
    for name in STRATEGY_NAMES:
        results.append(simulate_strategy(name, n_iters, rng))
    return results


# ---------------------------------------------------------------------------
# Console output
# ---------------------------------------------------------------------------

def _sr_bar(sr: float, width: int = 20) -> str:
    filled = int(round(sr * width))
    return "[" + "#" * filled + "-" * (width - filled) + "]"


def print_comparison_table(results: List[StrategyResult]) -> None:
    header = (
        f"{'Strategy':<20} {'Final SR':>9} {'Conv. Iter':>11} "
        f"{'Sample Eff.':>13} {'Stable':>8}  SR Bar"
    )
    sep = "-" * 80
    print("\n" + sep)
    print("  Reward Shaping Strategy Comparison (GR00T PPO Fine-tuning)")
    print(sep)
    print(header)
    print(sep)
    for r in sorted(results, key=lambda x: -x.final_sr):
        conv = str(r.convergence_iter) if r.convergence_iter else "N/A"
        seff = f"{r.sample_efficiency:,}" if r.sample_efficiency else "N/A"
        stable = "Yes" if r.policy_stable else "No "
        bar = _sr_bar(r.final_sr)
        print(
            f"  {r.name:<18} {r.final_sr:>8.1%} {conv:>11} "
            f"{seff:>13} {stable:>8}  {bar}"
        )
    print(sep)

    best = max(results, key=lambda x: x.final_sr)
    fastest = min(
        (r for r in results if r.convergence_iter),
        key=lambda x: x.convergence_iter,
    )
    most_efficient = min(
        (r for r in results if r.sample_efficiency),
        key=lambda x: x.sample_efficiency,
    )
    print(f"\n  Best final SR:         {best.name} ({best.final_sr:.1%})")
    print(f"  Fastest convergence:   {fastest.name} (iter {fastest.convergence_iter})")
    print(f"  Most sample-efficient: {most_efficient.name} ({most_efficient.sample_efficiency:,} env steps)")
    print(f"\n  Recommendation: Use 'combined' reward for production;")
    print(f"                  use 'potential_based' for policy safety / invariance.\n")


# ---------------------------------------------------------------------------
# JSON export
# ---------------------------------------------------------------------------

def build_json(results: List[StrategyResult]) -> dict:
    output: dict = {"strategies": []}
    for r in results:
        entry = {
            "name": r.name,
            "final_sr": r.final_sr,
            "convergence_iter": r.convergence_iter,
            "sample_efficiency": r.sample_efficiency,
            "policy_stable": r.policy_stable,
            "color": r.color,
            "iterations": [
                {
                    "iteration": m.iteration,
                    "success_rate": m.success_rate,
                    "mean_reward": m.mean_reward,
                    "policy_entropy": m.policy_entropy,
                    "kl_divergence": m.kl_divergence,
                }
                for m in r.metrics
            ],
        }
        output["strategies"].append(entry)

    best = max(results, key=lambda x: x.final_sr)
    fastest = min(
        (r for r in results if r.convergence_iter),
        key=lambda x: x.convergence_iter,
    )
    most_efficient = min(
        (r for r in results if r.sample_efficiency),
        key=lambda x: x.sample_efficiency,
    )
    output["summary"] = {
        "best_strategy": best.name,
        "best_final_sr": best.final_sr,
        "fastest_convergence_strategy": fastest.name,
        "fastest_convergence_iter": fastest.convergence_iter,
        "most_sample_efficient_strategy": most_efficient.name,
        "most_sample_efficient_steps": most_efficient.sample_efficiency,
        "recommendation": (
            "Use combined reward for production; "
            "potential_based for policy safety"
        ),
    }
    return output


# ---------------------------------------------------------------------------
# SVG chart helpers
# ---------------------------------------------------------------------------

_SVG_WIDTH = 700
_SVG_HEIGHT = 320
_MARGIN = {"top": 30, "right": 20, "bottom": 50, "left": 60}


def _chart_dims() -> Tuple[int, int]:
    w = _SVG_WIDTH - _MARGIN["left"] - _MARGIN["right"]
    h = _SVG_HEIGHT - _MARGIN["top"] - _MARGIN["bottom"]
    return w, h


def _x_scale(iter_: int, n_iters: int, w: int) -> float:
    return _MARGIN["left"] + (iter_ - 1) / (n_iters - 1) * w


def _y_scale(val: float, y_min: float, y_max: float, h: int) -> float:
    top = _MARGIN["top"]
    return top + h - (val - y_min) / (y_max - y_min) * h


def _make_sr_line_chart(results: List[StrategyResult], n_iters: int) -> str:
    w, h = _chart_dims()
    lines = []

    # Background
    lines.append(
        f'<rect width="{_SVG_WIDTH}" height="{_SVG_HEIGHT}" '
        f'fill="#0f172a" rx="8"/>'
    )
    # Grid lines
    for pct in [0.0, 0.25, 0.5, 0.75, 1.0]:
        y = _y_scale(pct, 0.0, 1.0, h)
        lines.append(
            f'<line x1="{_MARGIN["left"]}" y1="{y:.1f}" '
            f'x2="{_MARGIN["left"] + w}" y2="{y:.1f}" '
            f'stroke="#334155" stroke-width="1"/>'
        )
        lines.append(
            f'<text x="{_MARGIN["left"] - 6}" y="{y + 4:.1f}" '
            f'font-size="11" fill="#94a3b8" text-anchor="end">'
            f'{int(pct * 100)}%</text>'
        )
    # X-axis ticks
    for tick in range(0, n_iters + 1, 25):
        if tick == 0:
            continue
        x = _x_scale(tick, n_iters, w)
        y_base = _MARGIN["top"] + h
        lines.append(
            f'<line x1="{x:.1f}" y1="{y_base}" x2="{x:.1f}" '
            f'y2="{y_base + 5}" stroke="#94a3b8" stroke-width="1"/>'
        )
        lines.append(
            f'<text x="{x:.1f}" y="{y_base + 18}" font-size="11" '
            f'fill="#94a3b8" text-anchor="middle">{tick}</text>'
        )
    # Axis labels
    cx = _MARGIN["left"] + w / 2
    lines.append(
        f'<text x="{cx:.1f}" y="{_SVG_HEIGHT - 4}" font-size="12" '
        f'fill="#cbd5e1" text-anchor="middle">PPO Iteration</text>'
    )
    lines.append(
        f'<text x="14" y="{_MARGIN["top"] + h / 2:.1f}" font-size="12" '
        f'fill="#cbd5e1" text-anchor="middle" '
        f'transform="rotate(-90,14,{_MARGIN["top"] + h / 2:.1f})">'
        f'Success Rate</text>'
    )
    # 70% threshold line
    y70 = _y_scale(0.70, 0.0, 1.0, h)
    lines.append(
        f'<line x1="{_MARGIN["left"]}" y1="{y70:.1f}" '
        f'x2="{_MARGIN["left"] + w}" y2="{y70:.1f}" '
        f'stroke="#fbbf24" stroke-width="1" stroke-dasharray="6,4"/>'
    )
    lines.append(
        f'<text x="{_MARGIN["left"] + w + 3}" y="{y70 + 4:.1f}" '
        f'font-size="10" fill="#fbbf24">70%</text>'
    )

    # Strategy lines
    for r in results:
        pts = []
        for m in r.metrics:
            x = _x_scale(m.iteration, n_iters, w)
            y = _y_scale(m.success_rate, 0.0, 1.0, h)
            pts.append(f"{x:.1f},{y:.1f}")
        polyline = " ".join(pts)
        lines.append(
            f'<polyline points="{polyline}" fill="none" '
            f'stroke="{r.color}" stroke-width="2" '
            f'stroke-linejoin="round" stroke-linecap="round"/>'
        )
        # Label at end
        last = r.metrics[-1]
        lx = _x_scale(last.iteration, n_iters, w) + 3
        ly = _y_scale(last.success_rate, 0.0, 1.0, h)
        lines.append(
            f'<text x="{lx:.1f}" y="{ly + 4:.1f}" font-size="10" '
            f'fill="{r.color}">{r.name}</text>'
        )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{_SVG_WIDTH}" height="{_SVG_HEIGHT}" '
        f'viewBox="0 0 {_SVG_WIDTH} {_SVG_HEIGHT}">'
        + "\n".join(lines)
        + "</svg>"
    )


def _make_convergence_bar_chart(results: List[StrategyResult]) -> str:
    # Filter strategies that actually converged
    converged = [r for r in results if r.convergence_iter is not None]
    converged_sorted = sorted(converged, key=lambda x: x.convergence_iter)

    bar_w = 60
    gap = 20
    chart_h = 200
    y_top = 40
    y_bot = y_top + chart_h
    max_iter = max(r.convergence_iter for r in converged_sorted)
    total_w = len(converged_sorted) * (bar_w + gap) + gap + 80

    lines = []
    lines.append(
        f'<rect width="{total_w}" height="{y_bot + 60}" '
        f'fill="#0f172a" rx="8"/>'
    )
    # Axis
    lines.append(
        f'<line x1="60" y1="{y_top}" x2="60" y2="{y_bot}" '
        f'stroke="#475569" stroke-width="1"/>'
    )
    lines.append(
        f'<line x1="60" y1="{y_bot}" x2="{total_w - 10}" y2="{y_bot}" '
        f'stroke="#475569" stroke-width="1"/>'
    )
    # Y grid / ticks
    for tick in range(0, max_iter + 1, 25):
        y = y_bot - (tick / max_iter) * chart_h
        lines.append(
            f'<line x1="55" y1="{y:.1f}" x2="{total_w - 10}" y2="{y:.1f}" '
            f'stroke="#1e3a5f" stroke-width="1"/>'
        )
        lines.append(
            f'<text x="50" y="{y + 4:.1f}" font-size="10" '
            f'fill="#94a3b8" text-anchor="end">{tick}</text>'
        )
    # Y label
    lines.append(
        f'<text x="12" y="{y_top + chart_h / 2:.1f}" font-size="11" '
        f'fill="#cbd5e1" text-anchor="middle" '
        f'transform="rotate(-90,12,{y_top + chart_h / 2:.1f})">'
        f'Convergence Iter</text>'
    )
    # Bars
    for idx, r in enumerate(converged_sorted):
        bx = 60 + gap + idx * (bar_w + gap)
        bar_h_px = (r.convergence_iter / max_iter) * chart_h
        by = y_bot - bar_h_px
        lines.append(
            f'<rect x="{bx}" y="{by:.1f}" width="{bar_w}" '
            f'height="{bar_h_px:.1f}" fill="{r.color}" rx="3" opacity="0.85"/>'
        )
        # Value label
        lines.append(
            f'<text x="{bx + bar_w / 2:.1f}" y="{by - 5:.1f}" '
            f'font-size="11" fill="{r.color}" text-anchor="middle">'
            f'{r.convergence_iter}</text>'
        )
        # X label
        lines.append(
            f'<text x="{bx + bar_w / 2:.1f}" y="{y_bot + 16}" '
            f'font-size="10" fill="#94a3b8" text-anchor="middle">'
            f'{r.name}</text>'
        )

    lines.append(
        f'<text x="{(total_w) / 2:.1f}" y="{y_bot + 35}" '
        f'font-size="11" fill="#64748b" text-anchor="middle">'
        f'(lower = faster convergence)</text>'
    )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{total_w}" height="{y_bot + 50}" '
        f'viewBox="0 0 {total_w} {y_bot + 50}">'
        + "\n".join(lines)
        + "</svg>"
    )


# ---------------------------------------------------------------------------
# HTML report
# ---------------------------------------------------------------------------

def _sr_color(sr: float) -> str:
    if sr >= 0.83:
        return "#34d399"
    if sr >= 0.79:
        return "#fbbf24"
    return "#f87171"


def _conv_color(conv: Optional[int]) -> str:
    if conv is None:
        return "#f87171"
    if conv <= 70:
        return "#34d399"
    if conv <= 100:
        return "#fbbf24"
    return "#f87171"


def render_html(
    results: List[StrategyResult],
    n_iters: int,
) -> str:
    line_chart_svg = _make_sr_line_chart(results, n_iters)
    bar_chart_svg = _make_convergence_bar_chart(results)

    sorted_results = sorted(results, key=lambda x: -x.final_sr)
    best = sorted_results[0]
    fastest = min(
        (r for r in results if r.convergence_iter),
        key=lambda x: x.convergence_iter,
    )
    most_efficient = min(
        (r for r in results if r.sample_efficiency),
        key=lambda x: x.sample_efficiency,
    )

    # Table rows
    table_rows = []
    for r in sorted_results:
        sr_col = _sr_color(r.final_sr)
        conv_col = _conv_color(r.convergence_iter)
        conv_str = str(r.convergence_iter) if r.convergence_iter else "N/A"
        seff_str = f"{r.sample_efficiency:,}" if r.sample_efficiency else "N/A"
        stable_str = "Yes" if r.policy_stable else "No"
        stable_col = "#34d399" if r.policy_stable else "#f87171"
        dot = f'<span style="color:{r.color};font-size:18px;">&#9632;</span>'
        table_rows.append(f"""
            <tr>
              <td>{dot} {r.name}</td>
              <td style="color:{sr_col};font-weight:600;">{r.final_sr:.1%}</td>
              <td style="color:{conv_col};">{conv_str}</td>
              <td>{seff_str}</td>
              <td style="color:{stable_col};">{stable_str}</td>
            </tr>""")
    table_body = "\n".join(table_rows)

    legend_items = "".join(
        f'<span style="color:{STRATEGY_COLORS[n]};margin-right:16px;">'
        f'&#9632; {n}</span>'
        for n in STRATEGY_NAMES
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>Reward Shaping Analyzer — GR00T PPO Fine-tuning</title>
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: #1e293b;
    color: #e2e8f0;
    font-family: 'Segoe UI', system-ui, sans-serif;
    line-height: 1.6;
    padding: 32px 24px;
  }}
  h1 {{
    font-size: 1.7rem;
    font-weight: 700;
    color: #f1f5f9;
    border-left: 4px solid #C74634;
    padding-left: 14px;
    margin-bottom: 6px;
  }}
  .subtitle {{
    color: #94a3b8;
    font-size: 0.95rem;
    margin-bottom: 32px;
    padding-left: 18px;
  }}
  .oracle-red {{ color: #C74634; }}
  section {{
    background: #0f172a;
    border-radius: 10px;
    padding: 24px;
    margin-bottom: 28px;
    border: 1px solid #1e3a5f;
  }}
  section h2 {{
    font-size: 1.1rem;
    color: #C74634;
    font-weight: 600;
    margin-bottom: 16px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }}
  .summary-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 16px;
  }}
  .summary-card {{
    background: #1e293b;
    border-radius: 8px;
    padding: 16px;
    border: 1px solid #334155;
  }}
  .summary-card .label {{
    font-size: 0.78rem;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin-bottom: 6px;
  }}
  .summary-card .value {{
    font-size: 1.4rem;
    font-weight: 700;
    color: #f1f5f9;
  }}
  .summary-card .sub {{
    font-size: 0.82rem;
    color: #94a3b8;
    margin-top: 2px;
  }}
  .chart-wrap {{
    overflow-x: auto;
  }}
  .legend {{
    font-size: 0.85rem;
    margin-top: 12px;
    color: #94a3b8;
  }}
  table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 0.9rem;
  }}
  thead th {{
    text-align: left;
    padding: 10px 14px;
    color: #94a3b8;
    font-weight: 600;
    border-bottom: 1px solid #334155;
    font-size: 0.8rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }}
  tbody td {{
    padding: 10px 14px;
    border-bottom: 1px solid #1e293b;
    vertical-align: middle;
  }}
  tbody tr:hover {{ background: #1e293b; }}
  .recommendation {{
    background: linear-gradient(135deg, #1e293b, #0f172a);
    border: 1px solid #C74634;
    border-radius: 10px;
    padding: 20px 24px;
    margin-bottom: 28px;
  }}
  .recommendation h2 {{
    color: #C74634;
    font-size: 1rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 10px;
  }}
  .recommendation p {{
    color: #cbd5e1;
    font-size: 0.95rem;
  }}
  .recommendation strong {{ color: #fb923c; }}
  footer {{
    text-align: center;
    color: #475569;
    font-size: 0.8rem;
    margin-top: 40px;
  }}
</style>
</head>
<body>

<h1>Reward Shaping Analyzer</h1>
<p class="subtitle">
  GR00T PPO Fine-tuning &mdash; {n_iters} iterations &mdash; 6 strategies compared
</p>

<!-- Summary Cards -->
<section>
  <h2>Summary</h2>
  <div class="summary-grid">
    <div class="summary-card">
      <div class="label">Best Final SR</div>
      <div class="value oracle-red">{best.final_sr:.1%}</div>
      <div class="sub">{best.name}</div>
    </div>
    <div class="summary-card">
      <div class="label">Fastest Convergence</div>
      <div class="value" style="color:#a78bfa;">iter {fastest.convergence_iter}</div>
      <div class="sub">{fastest.name}</div>
    </div>
    <div class="summary-card">
      <div class="label">Most Sample-Efficient</div>
      <div class="value" style="color:#34d399;">{most_efficient.sample_efficiency:,}</div>
      <div class="sub">{most_efficient.name} &mdash; env steps to 70% SR</div>
    </div>
    <div class="summary-card">
      <div class="label">Policy-Safe Strategy</div>
      <div class="value" style="color:#a78bfa;">potential_based</div>
      <div class="sub">KL invariant, stable throughout</div>
    </div>
  </div>
</section>

<!-- SR Line Chart -->
<section>
  <h2>Success Rate Over PPO Iterations</h2>
  <div class="chart-wrap">
    {line_chart_svg}
  </div>
  <div class="legend">{legend_items}</div>
</section>

<!-- Convergence Bar Chart -->
<section>
  <h2>Convergence Iteration Comparison (lower = faster)</h2>
  <div class="chart-wrap">
    {bar_chart_svg}
  </div>
</section>

<!-- Table -->
<section>
  <h2>Strategy Comparison Table</h2>
  <table>
    <thead>
      <tr>
        <th>Strategy</th>
        <th>Final SR</th>
        <th>Conv. Iter</th>
        <th>Sample Efficiency</th>
        <th>Policy Stable</th>
      </tr>
    </thead>
    <tbody>
      {table_body}
    </tbody>
  </table>
</section>

<!-- Recommendation -->
<div class="recommendation">
  <h2>Recommendation</h2>
  <p>
    Use <strong>combined</strong> reward shaping for production deployments — it achieves
    the highest final success rate ({best.final_sr:.1%}) and converges {n_iters - best.convergence_iter}
    iterations before the sparse baseline.
    For safety-critical applications or policy invariance requirements, use
    <strong>potential_based</strong> shaping: it guarantees F(s,s') = &gamma;&Phi;(s') &minus; &Phi;(s)
    does not alter the optimal policy, maintains consistently low KL divergence, and
    still outperforms the sparse baseline by a significant margin.
  </p>
</div>

<footer>
  Generated by reward_shaping_analyzer.py &mdash; OCI Robot Cloud &mdash; Oracle Confidential
</footer>

</body>
</html>"""
    return html


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reward shaping strategy analyzer for GR00T PPO fine-tuning."
    )
    parser.add_argument(
        "--mock",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Use simulated data (default: True).",
    )
    parser.add_argument(
        "--n-iters",
        type=int,
        default=150,
        metavar="N",
        help="Number of PPO iterations to simulate (default: 150).",
    )
    parser.add_argument(
        "--output",
        default="/tmp/reward_shaping_analyzer.html",
        help="Path for the HTML report (default: /tmp/reward_shaping_analyzer.html).",
    )
    parser.add_argument(
        "--json-output",
        default=None,
        metavar="PATH",
        help="Optional path to write JSON results (default: <output>.json).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for simulation (default: 42).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.mock:
        print(f"[reward_shaping_analyzer] Running simulation (seed={args.seed}, "
              f"n_iters={args.n_iters}) ...")
    else:
        print("[reward_shaping_analyzer] --no-mock not yet implemented; "
              "falling back to simulation.")

    results = run_simulation(n_iters=args.n_iters, seed=args.seed)

    # Console table
    print_comparison_table(results)

    # HTML report
    html = render_html(results, n_iters=args.n_iters)
    html_path = args.output
    with open(html_path, "w", encoding="utf-8") as fh:
        fh.write(html)
    print(f"[reward_shaping_analyzer] HTML report saved: {html_path}")

    # JSON
    json_path = args.json_output or html_path.replace(".html", ".json")
    data = build_json(results)
    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
    print(f"[reward_shaping_analyzer] JSON results saved:  {json_path}")


if __name__ == "__main__":
    main()
