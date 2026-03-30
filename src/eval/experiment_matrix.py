#!/usr/bin/env python3
"""
experiment_matrix.py — Comprehensive 2D experiment comparison matrix for OCI Robot Cloud.

Compares all GR00T fine-tuning experiments across two primary axes:
  • Algorithm axis   : BC / DAgger / GAIL
  • Data-size axis   : number of demonstration episodes used for training

Secondary dimensions tracked per run: reward_type, curriculum flag, final success rate,
compute cost (USD), training steps, and free-form notes.

The report surfaces:
  1. A 2D grid (algo × data_size) showing mean success rate per cell.
  2. A Pareto frontier — runs that are non-dominated in the
     (maximize SR, minimize cost) space.
  3. Cohen's d effect size between any two SR groups.
  4. A dark-themed SVG scatter plot with the Pareto frontier connected,
     an algorithm-grouped summary stats table, a full sortable results table,
     and an annotated Pareto frontier list.

Usage:
    python src/eval/experiment_matrix.py --mock --output /tmp/experiment_matrix.html
    python src/eval/experiment_matrix.py --mock --output /tmp/experiment_matrix.html \\
        --json /tmp/experiment_data.json
    python src/eval/experiment_matrix.py --mock --seed 99 --output /tmp/em2.html

No external dependencies — stdlib only.
"""

import argparse
import json
import math
import random
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class ExperimentResult:
    """Single training-run record."""
    run_id: str
    algorithm: str          # "BC" | "DAgger" | "GAIL"
    data_size: int          # number of demo episodes
    reward_type: str        # e.g. "sparse" | "dense" | "shaped"
    curriculum: bool        # True = curriculum (easy→hard) training
    final_sr: float         # closed-loop success rate 0–1
    cost_usd: float         # estimated cloud compute cost in USD
    steps: int              # gradient steps
    notes: str = field(default="")


# ---------------------------------------------------------------------------
# Mock data generation
# ---------------------------------------------------------------------------

def _make_mock_results(seed: int = 42) -> list[ExperimentResult]:
    """Return ~20 seeded mock experiment results spanning the design space."""
    rng = random.Random(seed)

    def _jitter(base: float, sigma: float = 0.02) -> float:
        return max(0.0, min(1.0, base + rng.gauss(0, sigma)))

    runs: list[ExperimentResult] = []

    # ── BC runs ──────────────────────────────────────────────────────────────
    bc_table = [
        # (data_size, steps, base_sr, cost_usd, reward, curriculum, notes)
        (500,  5000, 0.05, 0.58, "sparse",  False, "BC 500 demos; covariate-shift ceiling ~5%."),
        (1000, 5000, 0.05, 1.16, "sparse",  False, "BC 1000 demos; loss 0.099 (↓39%), SR plateau."),
        (2000, 5000, 0.05, 2.31, "sparse",  False, "BC 2000 demos; scaling law plateaus—DAgger needed."),
        (1000, 5000, 0.10, 1.28, "dense",   False, "BC 1000 demos, dense reward shaping; marginal gain."),
        (1000, 5000, 0.08, 1.22, "shaped",  True,  "BC 1000 demos, curriculum ordering; slight benefit."),
    ]
    for i, (ds, st, sr, cost, rw, curr, note) in enumerate(bc_table):
        runs.append(ExperimentResult(
            run_id=f"bc_{ds}d_{st}s",
            algorithm="BC",
            data_size=ds,
            reward_type=rw,
            curriculum=curr,
            final_sr=_jitter(sr, 0.01),
            cost_usd=cost,
            steps=st,
            notes=note,
        ))

    # ── DAgger runs ───────────────────────────────────────────────────────────
    dagger_table = [
        ("r3", 1000, 2000, 0.65, 3.10, "sparse", False, "DAgger run3; β=0.20, 3 iters; first strong result."),
        ("r4", 1000, 5000, 0.05, 4.05, "sparse", False, "DAgger run4; 99 eps only—DAgger signal diluted."),
        ("r5", 1000, 3000, 0.32, 3.50, "sparse", False, "DAgger run5; β=0.10, 4 iters; meaningful gain."),
        ("r6", 1000, 5000, 0.40, 5.20, "sparse", False, "DAgger run6; pure on-policy (β=0); high variance."),
        ("r7", 1000, 3000, 0.55, 7.80, "sparse", False, "DAgger run7; β=0.10, 9 iters; diminishing returns."),
        ("r8", 1000, 3000, 0.60, 10.40, "sparse", False, "DAgger run8; 12 iters; approaching curriculum."),
        ("r9", 2000, 5000, 0.68, 16.20, "sparse", False, "DAgger run9; 2000-demo base; +13% vs 1000-demo."),
        ("r3_dense", 1000, 3000, 0.70, 3.80, "dense",  False, "DAgger run3 dense reward; dense reward helps."),
        ("r5_cur",   1000, 5000, 0.72, 12.60, "shaped", True, "DAgger run5 curriculum; 4-level adaptive, best."),
        ("r6_cur",   500,  5000, 0.58, 9.10, "shaped",  True, "DAgger run6 curriculum, 500 demos; cheaper."),
    ]
    for tag, ds, st, sr, cost, rw, curr, note in dagger_table:
        runs.append(ExperimentResult(
            run_id=f"dagger_{tag}",
            algorithm="DAgger",
            data_size=ds,
            reward_type=rw,
            curriculum=curr,
            final_sr=_jitter(sr, 0.015),
            cost_usd=cost,
            steps=st,
            notes=note,
        ))

    # ── GAIL runs ─────────────────────────────────────────────────────────────
    gail_table = [
        (500,  10000, 0.42, 8.50,  "adversarial", False, "GAIL 500 demos; adversarial reward; training unstable."),
        (1000, 10000, 0.55, 17.00, "adversarial", False, "GAIL 1000 demos; more stable; but costly vs DAgger."),
        (1000, 10000, 0.62, 18.20, "adversarial", True,  "GAIL 1000 demos + curriculum; competitive with DAgger."),
        (2000, 10000, 0.65, 34.00, "adversarial", False, "GAIL 2000 demos; high cost, not Pareto-optimal."),
        (500,  10000, 0.48, 9.00,  "adversarial", True,  "GAIL 500 demos + curriculum; decent SR for cost."),
    ]
    for i, (ds, st, sr, cost, rw, curr, note) in enumerate(gail_table):
        runs.append(ExperimentResult(
            run_id=f"gail_{ds}d_{i}",
            algorithm="GAIL",
            data_size=ds,
            reward_type=rw,
            curriculum=curr,
            final_sr=_jitter(sr, 0.02),
            cost_usd=cost,
            steps=st,
            notes=note,
        ))

    return runs


# ---------------------------------------------------------------------------
# Matrix construction
# ---------------------------------------------------------------------------

def build_matrix(results: list[ExperimentResult]) -> dict[str, dict[int, list[ExperimentResult]]]:
    """
    Group results into a 2D grid keyed by algorithm × data_size.

    Returns:
        dict[algo, dict[data_size, list[ExperimentResult]]]
    """
    matrix: dict[str, dict[int, list[ExperimentResult]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for r in results:
        matrix[r.algorithm][r.data_size].append(r)
    # Convert inner defaultdicts to plain dicts for cleaner downstream use
    return {algo: dict(inner) for algo, inner in matrix.items()}


# ---------------------------------------------------------------------------
# Pareto frontier
# ---------------------------------------------------------------------------

def pareto_frontier(results: list[ExperimentResult]) -> list[ExperimentResult]:
    """
    Identify Pareto-optimal runs in the (maximize final_sr, minimize cost_usd) space.

    A run r is Pareto-optimal if no other run dominates it — i.e., no other run has
    both a higher (or equal) SR *and* a lower (or equal) cost, with at least one
    dimension strictly better.

    Returns runs sorted by cost_usd ascending.
    """
    frontier: list[ExperimentResult] = []
    for candidate in results:
        dominated = False
        for other in results:
            if other is candidate:
                continue
            if (
                other.cost_usd <= candidate.cost_usd
                and other.final_sr >= candidate.final_sr
                and (other.cost_usd < candidate.cost_usd or other.final_sr > candidate.final_sr)
            ):
                dominated = True
                break
        if not dominated:
            frontier.append(candidate)
    return sorted(frontier, key=lambda r: r.cost_usd)


# ---------------------------------------------------------------------------
# Statistical helpers
# ---------------------------------------------------------------------------

def _mean(vals: list[float]) -> float:
    return sum(vals) / len(vals) if vals else 0.0


def _variance(vals: list[float]) -> float:
    if len(vals) < 2:
        return 0.0
    m = _mean(vals)
    return sum((v - m) ** 2 for v in vals) / (len(vals) - 1)


def effect_size(group_a: list[ExperimentResult], group_b: list[ExperimentResult]) -> float:
    """
    Compute Cohen's d between two groups based on their final_sr values.

    Cohen's d = (mean_A - mean_B) / pooled_std

    Returns 0.0 if either group has fewer than 2 members (undefined pooled std).
    Interpretation: |d| < 0.2 small, 0.2–0.5 medium, > 0.8 large.
    """
    a = [r.final_sr for r in group_a]
    b = [r.final_sr for r in group_b]
    if len(a) < 2 or len(b) < 2:
        return 0.0
    var_a, var_b = _variance(a), _variance(b)
    n_a, n_b = len(a), len(b)
    pooled_var = ((n_a - 1) * var_a + (n_b - 1) * var_b) / (n_a + n_b - 2)
    pooled_std = math.sqrt(pooled_var) if pooled_var > 0 else 1e-9
    return (_mean(a) - _mean(b)) / pooled_std


# ---------------------------------------------------------------------------
# Colour helpers
# ---------------------------------------------------------------------------

def _sr_colour(sr: float) -> str:
    """Map 0–1 success rate to red→yellow→green hex."""
    r = max(0.0, min(1.0, sr))
    if r <= 0.5:
        red, green, blue = 220, int(220 * r / 0.5), 40
    else:
        red, green, blue = int(220 * (1.0 - (r - 0.5) / 0.5)), 200, 40
    return f"#{red:02x}{green:02x}{blue:02x}"


_ALGO_COLOURS = {"BC": "#6688cc", "DAgger": "#44cc88", "GAIL": "#ffaa44"}


# ---------------------------------------------------------------------------
# HTML renderer
# ---------------------------------------------------------------------------

def render_html(results: list[ExperimentResult]) -> str:
    """
    Build a dark-themed HTML report containing:
      1. SVG scatter plot (cost vs SR, coloured by algorithm, Pareto frontier connected)
      2. Algorithm-grouped summary stats table (mean SR, mean cost, N, Cohen's d vs BC)
      3. Full sortable results table with best row highlighted
      4. Annotated Pareto frontier list
    """
    matrix = build_matrix(results)
    frontier = pareto_frontier(results)
    frontier_ids = {r.run_id for r in frontier}
    best = max(results, key=lambda r: r.final_sr)

    algos = sorted(matrix.keys())
    all_data_sizes = sorted({r.data_size for r in results})

    # ── SVG scatter ──────────────────────────────────────────────────────────
    max_cost = max(r.cost_usd for r in results) * 1.1 + 0.5
    PL, PT, PR, PB = 60, 36, 40, 50
    W, H = 560, 320
    pw, ph = W - PL - PR, H - PT - PB

    def tx(c: float) -> float:
        return PL + (c / max_cost) * pw

    def ty(s: float) -> float:
        return PT + ph - s * ph

    svg_lines: list[str] = []
    svg_lines.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'style="font-family:monospace;background:#1a1a2e;">'
    )
    svg_lines.append(
        f'<text x="{W//2}" y="22" text-anchor="middle" fill="#e0e0e0" '
        f'font-size="13" font-weight="bold">Cost vs Success Rate — All Experiments</text>'
    )
    # Grid + axis ticks
    for sr_t in [0.0, 0.2, 0.4, 0.6, 0.8]:
        y = ty(sr_t)
        svg_lines.append(
            f'<line x1="{PL}" y1="{y:.1f}" x2="{W-PR}" y2="{y:.1f}" '
            f'stroke="#222240" stroke-width="1"/>'
        )
        svg_lines.append(
            f'<text x="{PL-5}" y="{y+4:.1f}" text-anchor="end" '
            f'fill="#666688" font-size="10">{sr_t*100:.0f}%</text>'
        )
    cost_ticks = [0, 5, 10, 15, 20, 25, 30, 35]
    for ct in cost_ticks:
        if ct > max_cost:
            break
        x = tx(ct)
        svg_lines.append(
            f'<line x1="{x:.1f}" y1="{PT}" x2="{x:.1f}" y2="{PT+ph}" '
            f'stroke="#222240" stroke-width="1"/>'
        )
        svg_lines.append(
            f'<text x="{x:.1f}" y="{PT+ph+14}" text-anchor="middle" '
            f'fill="#666688" font-size="10">${ct}</text>'
        )
    # Axes
    svg_lines.append(
        f'<line x1="{PL}" y1="{PT}" x2="{PL}" y2="{PT+ph}" stroke="#4a4a6e" stroke-width="1.5"/>'
    )
    svg_lines.append(
        f'<line x1="{PL}" y1="{PT+ph}" x2="{W-PR}" y2="{PT+ph}" stroke="#4a4a6e" stroke-width="1.5"/>'
    )
    svg_lines.append(
        f'<text x="{W//2}" y="{H-4}" text-anchor="middle" fill="#9090b0" font-size="11">Cost (USD)</text>'
    )
    svg_lines.append(
        f'<text transform="rotate(-90,14,{PT+ph//2})" x="14" y="{PT+ph//2}" '
        f'text-anchor="middle" fill="#9090b0" font-size="11">Success Rate</text>'
    )
    # Pareto frontier line
    if len(frontier) >= 2:
        pts = " ".join(f"{tx(r.cost_usd):.1f},{ty(r.final_sr):.1f}" for r in frontier)
        svg_lines.append(
            f'<polyline points="{pts}" fill="none" stroke="#44cc88" '
            f'stroke-width="1.5" stroke-dasharray="6,3" opacity="0.75"/>'
        )
    # Points
    for r in results:
        cx, cy = tx(r.cost_usd), ty(r.final_sr)
        col = _ALGO_COLOURS.get(r.algorithm, "#aaaacc")
        is_p = r.run_id in frontier_ids
        radius = 7 if is_p else 5
        stroke_w = "1.5" if is_p else "0"
        tip = f"{r.run_id} | SR={r.final_sr*100:.0f}% | ${r.cost_usd:.2f}"
        svg_lines.append(
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{radius}" fill="{col}" '
            f'stroke="#ffffff" stroke-width="{stroke_w}" opacity="0.9">'
            f'<title>{tip}</title></circle>'
        )
    # Legend
    lx, ly = PL + 8, PT + 8
    for i, algo in enumerate(["BC", "DAgger", "GAIL"]):
        col = _ALGO_COLOURS[algo]
        svg_lines.append(f'<circle cx="{lx+6}" cy="{ly+i*16+6}" r="5" fill="{col}"/>')
        svg_lines.append(
            f'<text x="{lx+16}" y="{ly+i*16+10}" fill="#c0c0e0" font-size="10">{algo}</text>'
        )
    svg_lines.append(f'<circle cx="{lx+6}" cy="{ly+3*16+6}" r="6" fill="#888" stroke="#fff" stroke-width="1.5"/>')
    svg_lines.append(
        f'<text x="{lx+16}" y="{ly+3*16+10}" fill="#c0c0e0" font-size="10">Pareto-optimal</text>'
    )
    svg_lines.append("</svg>")
    scatter_svg = "\n".join(svg_lines)

    # ── Summary stats table ───────────────────────────────────────────────────
    bc_group = [r for r in results if r.algorithm == "BC"]
    stat_rows: list[str] = []
    for algo in algos:
        grp = [r for r in results if r.algorithm == algo]
        mean_sr = _mean([r.final_sr for r in grp])
        mean_cost = _mean([r.cost_usd for r in grp])
        d = effect_size(grp, bc_group) if algo != "BC" else 0.0
        d_str = f"{d:+.2f}" if algo != "BC" else "—"
        col = _ALGO_COLOURS.get(algo, "#aaa")
        sr_col = _sr_colour(mean_sr)
        stat_rows.append(
            f"<tr>"
            f'<td style="color:{col};font-weight:bold">{algo}</td>'
            f"<td>{len(grp)}</td>"
            f'<td style="background:{sr_col};color:#111;font-weight:bold;border-radius:3px">'
            f"{mean_sr*100:.1f}%</td>"
            f"<td>${mean_cost:.2f}</td>"
            f"<td>{d_str}</td>"
            f"</tr>"
        )

    # ── 2D matrix table (algo × data_size) ───────────────────────────────────
    matrix_header = "".join(f"<th>{ds} demos</th>" for ds in all_data_sizes)
    matrix_rows: list[str] = []
    for algo in algos:
        algo_col = _ALGO_COLOURS.get(algo, "#aaa")
        cells = f'<td style="color:{algo_col};font-weight:bold">{algo}</td>'
        for ds in all_data_sizes:
            cell_runs = matrix.get(algo, {}).get(ds, [])
            if cell_runs:
                sr = _mean([r.final_sr for r in cell_runs])
                bg = _sr_colour(sr)
                cells += (
                    f'<td style="background:{bg};color:#111;font-weight:bold;border-radius:3px">'
                    f"{sr*100:.0f}%</td>"
                )
            else:
                cells += '<td style="color:#444">—</td>'
        matrix_rows.append(f"<tr>{cells}</tr>")

    # ── Full results table ────────────────────────────────────────────────────
    sorted_results = sorted(results, key=lambda r: -r.final_sr)
    result_rows: list[str] = []
    for r in sorted_results:
        is_best = r.run_id == best.run_id
        is_pareto = r.run_id in frontier_ids
        row_style = ' style="background:#0d2e1a"' if is_best else ""
        sr_bg = _sr_colour(r.final_sr)
        pareto_badge = ' <span style="color:#44cc88;font-size:10px">★ Pareto</span>' if is_pareto else ""
        best_badge = ' <span style="color:#ffd700;font-size:10px">★ Best</span>' if is_best else ""
        algo_col = _ALGO_COLOURS.get(r.algorithm, "#aaa")
        result_rows.append(
            f"<tr{row_style}>"
            f'<td style="text-align:left;padding:5px 8px">'
            f"{r.run_id}{pareto_badge}{best_badge}</td>"
            f'<td style="color:{algo_col};font-weight:bold">{r.algorithm}</td>'
            f"<td>{r.data_size}</td>"
            f"<td>{r.reward_type}</td>"
            f"<td>{'Yes' if r.curriculum else 'No'}</td>"
            f'<td style="background:{sr_bg};color:#111;font-weight:bold;border-radius:3px">'
            f"{r.final_sr*100:.1f}%</td>"
            f"<td>${r.cost_usd:.2f}</td>"
            f"<td>{r.steps:,}</td>"
            f'<td style="font-size:10px;color:#888;text-align:left;max-width:220px;'
            f'white-space:normal">{r.notes[:100]}{"…" if len(r.notes)>100 else ""}</td>'
            f"</tr>"
        )

    # ── Pareto frontier list ──────────────────────────────────────────────────
    pareto_items: list[str] = []
    for i, r in enumerate(frontier):
        algo_col = _ALGO_COLOURS.get(r.algorithm, "#aaa")
        pareto_items.append(
            f'<li style="margin:6px 0">'
            f'<span style="color:{algo_col};font-weight:bold">[{r.algorithm}]</span> '
            f'<code>{r.run_id}</code> — '
            f'<span style="color:#44cc88">{r.final_sr*100:.1f}% SR</span> @ '
            f'<span style="color:#ffaa44">${r.cost_usd:.2f}</span> | '
            f'{r.data_size} demos | {r.notes[:80]}{"…" if len(r.notes)>80 else ""}'
            f'</li>'
        )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>OCI Robot Cloud — Experiment Matrix</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: #0d0d1a;
    color: #d0d0e8;
    font-family: 'Menlo','Monaco','Courier New',monospace;
    font-size: 13px;
    line-height: 1.5;
  }}
  .container {{ max-width: 1060px; margin: 0 auto; padding: 32px 20px; }}
  h1 {{ font-size: 21px; color: #e8e8ff; margin-bottom: 4px; }}
  .sub {{ color: #606080; font-size: 11px; margin-bottom: 26px; }}
  h2 {{
    font-size: 14px; color: #b0b0d0; margin: 28px 0 10px;
    border-left: 3px solid #44cc88; padding-left: 10px;
  }}
  .stats-row {{ display: flex; gap: 14px; flex-wrap: wrap; margin-bottom: 26px; }}
  .stat-card {{
    background: #16162a; border: 1px solid #2a2a4e;
    border-radius: 7px; padding: 12px 18px; min-width: 140px;
  }}
  .stat-val {{ font-size: 26px; font-weight: bold; color: #44cc88; }}
  .stat-lbl {{ font-size: 10px; color: #606080; margin-top: 2px; }}
  .svg-wrap {{
    background: #1a1a2e; border: 1px solid #2a2a4e;
    border-radius: 7px; padding: 14px; overflow-x: auto; margin-bottom: 14px;
  }}
  table {{
    width: 100%; border-collapse: collapse; background: #13132a;
    border-radius: 7px; overflow: hidden; font-size: 12px; margin-bottom: 14px;
  }}
  th {{
    background: #1e1e38; color: #8888b0; padding: 7px 8px;
    text-align: center; font-size: 11px; cursor: pointer;
    user-select: none; white-space: nowrap;
  }}
  th:hover {{ background: #28284a; color: #e0e0ff; }}
  td {{ padding: 5px 8px; text-align: center; border-bottom: 1px solid #1a1a2e; }}
  tr:hover td {{ background: #1c1c34; }}
  ol, ul {{ padding-left: 20px; }}
  li {{ color: #c0c0d8; font-size: 12px; }}
  .footer {{ margin-top: 40px; color: #33334a; font-size: 11px; text-align: center; }}
</style>
</head>
<body>
<div class="container">

<h1>OCI Robot Cloud — Experiment Matrix</h1>
<div class="sub">
  GR00T N1.6 fine-tuning · Franka pick-and-lift ·
  {len(results)} runs · algo × data_size grid · Pareto frontier
</div>

<div class="stats-row">
  <div class="stat-card">
    <div class="stat-val">{len(results)}</div>
    <div class="stat-lbl">Total experiments</div>
  </div>
  <div class="stat-card">
    <div class="stat-val">{best.final_sr*100:.0f}%</div>
    <div class="stat-lbl">Best SR<br/>{best.run_id}</div>
  </div>
  <div class="stat-card">
    <div class="stat-val">{len(frontier)}</div>
    <div class="stat-lbl">Pareto-optimal<br/>configurations</div>
  </div>
  <div class="stat-card">
    <div class="stat-val">${min(r.cost_usd for r in frontier):.2f}</div>
    <div class="stat-lbl">Cheapest Pareto<br/>point</div>
  </div>
</div>

<h2>Cost vs Success Rate Scatter</h2>
<div class="svg-wrap">{scatter_svg}</div>

<h2>2D Grid: Algorithm × Data Size (mean SR per cell)</h2>
<div style="overflow-x:auto">
<table>
  <thead>
    <tr><th>Algorithm</th>{matrix_header}</tr>
  </thead>
  <tbody>
    {"".join(matrix_rows)}
  </tbody>
</table>
</div>

<h2>Summary Statistics by Algorithm</h2>
<p style="color:#505068;font-size:11px;margin-bottom:8px">
  Cohen's d vs BC group (|d|&gt;0.8 = large effect).
</p>
<table>
  <thead>
    <tr>
      <th>Algorithm</th><th>N</th><th>Mean SR</th>
      <th>Mean Cost</th><th>Cohen's d vs BC</th>
    </tr>
  </thead>
  <tbody>{"".join(stat_rows)}</tbody>
</table>

<h2>Full Results Table</h2>
<p style="color:#505068;font-size:11px;margin-bottom:8px">
  Click headers to sort. Best run highlighted in green. ★ Pareto = cost-efficient frontier.
</p>
<div style="overflow-x:auto">
<table id="tbl">
  <thead>
    <tr>
      <th onclick="sort(0)" style="text-align:left">Run ID</th>
      <th onclick="sort(1)">Algo</th>
      <th onclick="sort(2)">Demos</th>
      <th onclick="sort(3)">Reward</th>
      <th onclick="sort(4)">Curriculum</th>
      <th onclick="sort(5)">SR</th>
      <th onclick="sort(6)">Cost</th>
      <th onclick="sort(7)">Steps</th>
      <th style="text-align:left">Notes</th>
    </tr>
  </thead>
  <tbody>{"".join(result_rows)}</tbody>
</table>
</div>

<h2>Pareto Frontier ({len(frontier)} runs, sorted by cost)</h2>
<ul>{"".join(pareto_items)}</ul>

<div class="footer">
  experiment_matrix.py · OCI Robot Cloud · GR00T N1.6 fine-tuning pipeline · 2026
</div>
</div>

<script>
let _dir = {{}};
function sort(col) {{
  const tb = document.getElementById('tbl').tBodies[0];
  const rows = Array.from(tb.rows);
  _dir[col] = !_dir[col];
  rows.sort((a, b) => {{
    let av = a.cells[col].textContent.trim().replace(/[%$,★Pareto Best]/g,'').trim();
    let bv = b.cells[col].textContent.trim().replace(/[%$,★Pareto Best]/g,'').trim();
    const an = parseFloat(av), bn = parseFloat(bv);
    if (!isNaN(an) && !isNaN(bn)) return _dir[col] ? an-bn : bn-an;
    return _dir[col] ? av.localeCompare(bv) : bv.localeCompare(av);
  }});
  rows.forEach(r => tb.appendChild(r));
}}
</script>
</body>
</html>"""
    return html


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate OCI Robot Cloud experiment comparison matrix.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--mock", action="store_true", default=True,
                        help="Use seeded mock data (default: True).")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed for mock data (default: 42).")
    parser.add_argument("--output", metavar="FILE", default="/tmp/experiment_matrix.html",
                        help="Path for HTML report (default: /tmp/experiment_matrix.html).")
    parser.add_argument("--json", metavar="FILE",
                        help="Also write companion JSON file.")
    args = parser.parse_args()

    results = _make_mock_results(seed=args.seed)
    print(f"Loaded {len(results)} mock experiments (seed={args.seed}).", file=sys.stderr)

    html = render_html(results)
    with open(args.output, "w") as f:
        f.write(html)
    print(f"HTML report: {args.output}", file=sys.stderr)

    if args.json:
        frontier = pareto_frontier(results)
        data = {
            "metadata": {
                "n_experiments": len(results),
                "seed": args.seed,
                "eval_protocol": "20-episode closed-loop, LIFT_THRESHOLD=0.780m",
            },
            "experiments": [asdict(r) for r in results],
            "pareto_frontier": [r.run_id for r in frontier],
            "best_run": max(results, key=lambda r: r.final_sr).run_id,
        }
        with open(args.json, "w") as f:
            json.dump(data, f, indent=2)
        print(f"JSON data: {args.json}", file=sys.stderr)

    # Print summary
    frontier = pareto_frontier(results)
    best = max(results, key=lambda r: r.final_sr)
    matrix = build_matrix(results)
    algos = sorted(matrix.keys())
    bc_group = [r for r in results if r.algorithm == "BC"]

    print(f"\n=== Experiment Matrix Summary ===")
    print(f"Total runs    : {len(results)}")
    print(f"Best run      : {best.run_id}  SR={best.final_sr*100:.1f}%  cost=${best.cost_usd:.2f}")
    print(f"Pareto-optimal: {len(frontier)} runs")
    print(f"\nAlgorithm summary:")
    for algo in algos:
        grp = [r for r in results if r.algorithm == algo]
        mean_sr = _mean([r.final_sr for r in grp])
        d = effect_size(grp, bc_group) if algo != "BC" else 0.0
        d_str = f"Cohen's d vs BC = {d:+.2f}" if algo != "BC" else "(baseline)"
        print(f"  {algo:<8}  N={len(grp)}  mean SR={mean_sr*100:.1f}%  {d_str}")
    print(f"\nPareto frontier (cheapest→best SR):")
    for r in frontier:
        print(f"  ${r.cost_usd:6.2f}  →  {r.final_sr*100:.1f}%  [{r.algorithm}]  {r.run_id}")


if __name__ == "__main__":
    main()
