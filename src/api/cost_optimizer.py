#!/usr/bin/env python3
"""
cost_optimizer.py — Training cost optimizer for OCI Robot Cloud.

Given a target success rate and training budget, recommends the optimal:
  - Number of demos to collect
  - Training steps
  - GPU configuration (1-8 A100s for DDP)
  - DAgger iteration strategy

Optimization model is based on empirical data from OCI A100 runs:
  - BC plateau: ~5% at any data size beyond 500 demos
  - DAgger: +13% success per 20 episodes × 2000 steps
  - Cost: $0.0043/10k steps, $0.85 full pipeline

Usage:
    python src/api/cost_optimizer.py --target-success 0.65 --budget 5.0
    python src/api/cost_optimizer.py --serve --port 8013
    python src/api/cost_optimizer.py --mock
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from dataclasses import dataclass, asdict
from typing import List, Optional

# ---------------------------------------------------------------------------
# Empirical model parameters
# ---------------------------------------------------------------------------

EMPIRICAL_PARAMS = {
    "bc_base_success": 0.05,               # BC plateau (any demos >= 500)
    "dagger_success_per_iter": 0.13,        # additional success per DAgger iter
    "dagger_max_success": 0.80,             # hard ceiling
    "cost_per_10k_steps": 0.0043,           # OCI A100 per 10k steps (single GPU)
    "sdg_cost_per_demo": 0.00026,           # Genesis SDG cost ($0.85/1000 demos/3 steps)
    "dagger_collection_cost_per_ep": 0.0015,  # ~0.5 min per ep × A100 rate
    "ddp_speedup_4gpu": 3.07,              # 4× A100 DDP throughput multiplier
}

# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------

@dataclass
class TrainingScenario:
    name: str
    n_demos: int
    bc_steps: int
    dagger_iters: int
    dagger_eps_per_iter: int
    n_gpus: int
    estimated_success_rate: float
    estimated_cost_usd: float
    estimated_time_min: float

    def to_dict(self) -> dict:
        d = asdict(self)
        d["estimated_success_rate"] = round(d["estimated_success_rate"], 4)
        d["estimated_cost_usd"] = round(d["estimated_cost_usd"], 4)
        d["estimated_time_min"] = round(d["estimated_time_min"], 1)
        return d


# ---------------------------------------------------------------------------
# Core model functions
# ---------------------------------------------------------------------------

def estimate_success_rate(n_demos: int, bc_steps: int, dagger_iters: int) -> float:
    """
    Estimate policy success rate based on empirical OCI A100 data.

    BC success saturates quickly; DAgger adds +13% per iter up to 80% ceiling.
    Demo count below 500 applies a data-scaling penalty.
    """
    p = EMPIRICAL_PARAMS

    # BC base success — scale down below 500 demos
    if n_demos >= 500:
        bc_success = p["bc_base_success"]
    else:
        # Linear scale from 0 at 0 demos to bc_base at 500
        bc_success = p["bc_base_success"] * (n_demos / 500.0)

    # BC step scaling: more steps help up to ~10k
    step_factor = min(1.0, bc_steps / 10_000.0)
    bc_success = bc_success * (0.5 + 0.5 * step_factor)

    # DAgger contribution
    dagger_gain = dagger_iters * p["dagger_success_per_iter"]

    total = bc_success + dagger_gain
    return min(total, p["dagger_max_success"])


def _compute_time_min(scenario: TrainingScenario) -> float:
    """Estimate wall-clock time in minutes for a scenario."""
    p = EMPIRICAL_PARAMS

    # SDG time: ~0.1 min per demo
    sdg_time = scenario.n_demos * 0.10

    # BC training time: based on throughput (2.35 it/s single GPU, DDP scales)
    single_gpu_throughput = 2.35  # iterations per second
    if scenario.n_gpus >= 4:
        throughput = single_gpu_throughput * p["ddp_speedup_4gpu"]
    elif scenario.n_gpus >= 2:
        throughput = single_gpu_throughput * 1.85
    else:
        throughput = single_gpu_throughput

    bc_time = scenario.bc_steps / throughput / 60.0  # seconds → minutes

    # DAgger time: collection + fine-tuning
    dagger_steps_per_iter = 2000
    dagger_collection_time = scenario.dagger_iters * scenario.dagger_eps_per_iter * 0.5
    dagger_train_time = (
        scenario.dagger_iters
        * dagger_steps_per_iter
        / throughput
        / 60.0
    )
    dagger_time = dagger_collection_time + dagger_train_time

    return sdg_time + bc_time + dagger_time


def estimate_cost(scenario: TrainingScenario) -> float:
    """
    Estimate total cost in USD for a TrainingScenario.

    Components:
      1. SDG (Genesis demo collection)
      2. BC training (GPU compute)
      3. DAgger iterations (collection + fine-tune)
    """
    p = EMPIRICAL_PARAMS

    # SDG cost
    sdg_cost = scenario.n_demos * p["sdg_cost_per_demo"]

    # GPU cost rate: 4-GPU DDP does not reduce per-step cost (same A100 hours),
    # but finishes faster — cost per step is the same per GPU, so total GPU cost
    # stays proportional to total GPU-steps, not wall time.
    # For simplicity: cost_per_10k_steps is per GPU; DDP = n_gpus × rate.
    gpu_rate_multiplier = 1.0 if scenario.n_gpus == 1 else min(scenario.n_gpus, 4)

    bc_cost = (scenario.bc_steps / 10_000.0) * p["cost_per_10k_steps"] * gpu_rate_multiplier

    # DAgger cost: collection + 2000-step fine-tuning per iter
    dagger_steps_per_iter = 2000
    dagger_collection_cost = (
        scenario.dagger_iters
        * scenario.dagger_eps_per_iter
        * p["dagger_collection_cost_per_ep"]
    )
    dagger_train_cost = (
        scenario.dagger_iters
        * (dagger_steps_per_iter / 10_000.0)
        * p["cost_per_10k_steps"]
        * gpu_rate_multiplier
    )
    dagger_cost = dagger_collection_cost + dagger_train_cost

    return sdg_cost + bc_cost + dagger_cost


def _build_scenario(
    name: str,
    n_demos: int,
    bc_steps: int,
    dagger_iters: int,
    dagger_eps_per_iter: int,
    n_gpus: int,
) -> TrainingScenario:
    s = TrainingScenario(
        name=name,
        n_demos=n_demos,
        bc_steps=bc_steps,
        dagger_iters=dagger_iters,
        dagger_eps_per_iter=dagger_eps_per_iter,
        n_gpus=n_gpus,
        estimated_success_rate=0.0,
        estimated_cost_usd=0.0,
        estimated_time_min=0.0,
    )
    s.estimated_success_rate = estimate_success_rate(n_demos, bc_steps, dagger_iters)
    s.estimated_cost_usd = estimate_cost(s)
    s.estimated_time_min = _compute_time_min(s)
    return s


# ---------------------------------------------------------------------------
# Optimizer
# ---------------------------------------------------------------------------

def optimize_for_budget(
    budget_usd: float,
    target_success: float,
) -> List[TrainingScenario]:
    """
    Return a list of Pareto-optimal TrainingScenarios within budget that
    meet the target success rate.

    Four canonical scenarios are evaluated; only those within budget AND
    meeting the target are returned (or the best available if none qualify).
    """
    candidates = [
        _build_scenario(
            name="Quick start",
            n_demos=100,
            bc_steps=2_000,
            dagger_iters=3,
            dagger_eps_per_iter=20,
            n_gpus=1,
        ),
        _build_scenario(
            name="Recommended",
            n_demos=500,
            bc_steps=5_000,
            dagger_iters=5,
            dagger_eps_per_iter=20,
            n_gpus=1,
        ),
        _build_scenario(
            name="Fast multi-GPU",
            n_demos=500,
            bc_steps=5_000,
            dagger_iters=3,
            dagger_eps_per_iter=20,
            n_gpus=4,
        ),
        _build_scenario(
            name="High accuracy",
            n_demos=1_000,
            bc_steps=5_000,
            dagger_iters=8,
            dagger_eps_per_iter=20,
            n_gpus=1,
        ),
    ]

    # Filter by budget and target success
    qualifying = [
        s for s in candidates
        if s.estimated_cost_usd <= budget_usd
        and s.estimated_success_rate >= target_success
    ]

    if qualifying:
        # Pareto-prune: remove dominated scenarios (higher cost + lower success)
        pareto = []
        for s in qualifying:
            dominated = False
            for other in qualifying:
                if (
                    other is not s
                    and other.estimated_cost_usd <= s.estimated_cost_usd
                    and other.estimated_success_rate >= s.estimated_success_rate
                    and (
                        other.estimated_cost_usd < s.estimated_cost_usd
                        or other.estimated_success_rate > s.estimated_success_rate
                    )
                ):
                    dominated = True
                    break
            if not dominated:
                pareto.append(s)
        return sorted(pareto, key=lambda s: s.estimated_cost_usd)

    # Nothing meets target — return cheapest option within budget, or all if all over budget
    within_budget = [s for s in candidates if s.estimated_cost_usd <= budget_usd]
    if within_budget:
        return sorted(within_budget, key=lambda s: -s.estimated_success_rate)[:1]
    # All over budget — return closest to budget
    return sorted(candidates, key=lambda s: s.estimated_cost_usd)[:1]


# ---------------------------------------------------------------------------
# HTML report
# ---------------------------------------------------------------------------

def generate_html_report(
    scenarios: List[TrainingScenario],
    output_path: str,
    target_success: float = 0.0,
    budget_usd: float = 0.0,
) -> str:
    """
    Generate a dark-theme HTML report with:
      - Comparison table (scenarios highlighted if recommended)
      - Cost vs success rate scatter plot (inline SVG)
      - Time to value bar chart (inline SVG)
      - Budget slider concept description
    """

    # ---- Table rows --------------------------------------------------------
    def row_class(s: TrainingScenario) -> str:
        if s.name == "Recommended":
            return ' class="highlight"'
        return ""

    table_rows = ""
    for s in scenarios:
        meets = "✓" if s.estimated_success_rate >= target_success else "✗"
        in_budget = "✓" if s.estimated_cost_usd <= budget_usd else "✗"
        table_rows += f"""
        <tr{row_class(s)}>
          <td>{s.name}</td>
          <td>{s.n_demos}</td>
          <td>{s.bc_steps:,}</td>
          <td>{s.dagger_iters}</td>
          <td>{s.n_gpus}</td>
          <td>{s.estimated_success_rate:.1%}</td>
          <td>${s.estimated_cost_usd:.4f}</td>
          <td>{s.estimated_time_min:.1f} min</td>
          <td>{meets}</td>
          <td>{in_budget}</td>
        </tr>"""

    # ---- Scatter plot (SVG) ------------------------------------------------
    # Map cost and success to SVG coordinates
    SVG_W, SVG_H = 500, 300
    MARGIN = 50

    all_costs = [s.estimated_cost_usd for s in scenarios]
    all_success = [s.estimated_success_rate for s in scenarios]
    max_cost = max(all_costs) * 1.2 or 1.0
    min_cost = 0.0
    max_sr = max(all_success) * 1.2 or 1.0
    min_sr = 0.0

    def to_x(cost: float) -> float:
        return MARGIN + (cost - min_cost) / (max_cost - min_cost) * (SVG_W - 2 * MARGIN)

    def to_y(sr: float) -> float:
        return SVG_H - MARGIN - (sr - min_sr) / (max_sr - min_sr) * (SVG_H - 2 * MARGIN)

    scatter_circles = ""
    scatter_labels = ""
    colors = ["#60A5FA", "#34D399", "#F59E0B", "#F87171"]
    for i, s in enumerate(scenarios):
        cx = to_x(s.estimated_cost_usd)
        cy = to_y(s.estimated_success_rate)
        color = colors[i % len(colors)]
        r = 9 if s.name == "Recommended" else 6
        scatter_circles += f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r}" fill="{color}" stroke="#fff" stroke-width="1.5"/>\n'
        scatter_labels += f'<text x="{cx + 10:.1f}" y="{cy + 4:.1f}" fill="#D1D5DB" font-size="11">{s.name}</text>\n'

    # Axes
    ax_x1, ax_y1 = MARGIN, MARGIN
    ax_x2, ax_y2 = MARGIN, SVG_H - MARGIN
    ax_x3 = SVG_W - MARGIN

    scatter_svg = f"""
    <svg width="{SVG_W}" height="{SVG_H}" style="background:#1F2937;border-radius:8px;">
      <!-- Axes -->
      <line x1="{ax_x1}" y1="{ax_y1}" x2="{ax_x2}" y2="{ax_y2}" stroke="#6B7280" stroke-width="1"/>
      <line x1="{ax_x2}" y1="{ax_y2}" x2="{ax_x3}" y2="{ax_y2}" stroke="#6B7280" stroke-width="1"/>
      <!-- Axis labels -->
      <text x="{SVG_W//2}" y="{SVG_H - 8}" fill="#9CA3AF" font-size="12" text-anchor="middle">Cost (USD)</text>
      <text x="12" y="{SVG_H//2}" fill="#9CA3AF" font-size="12" text-anchor="middle" transform="rotate(-90,12,{SVG_H//2})">Success Rate</text>
      <!-- Target success line -->
      <line x1="{MARGIN}" y1="{to_y(target_success):.1f}" x2="{SVG_W - MARGIN}" y2="{to_y(target_success):.1f}"
            stroke="#F59E0B" stroke-width="1" stroke-dasharray="4,4"/>
      <text x="{SVG_W - MARGIN + 2}" y="{to_y(target_success) + 4:.1f}" fill="#F59E0B" font-size="10">target</text>
      {scatter_circles}
      {scatter_labels}
    </svg>"""

    # ---- Time bar chart (SVG) ----------------------------------------------
    BAR_W, BAR_H = 500, 260
    BAR_MARGIN = 50
    bar_area_w = BAR_W - 2 * BAR_MARGIN
    bar_area_h = BAR_H - 2 * BAR_MARGIN - 30
    max_time = max(s.estimated_time_min for s in scenarios) * 1.2 or 1.0
    n = len(scenarios)
    bar_width = (bar_area_w / n) * 0.6
    bar_spacing = bar_area_w / n

    bars = ""
    for i, s in enumerate(scenarios):
        bx = BAR_MARGIN + i * bar_spacing + bar_spacing * 0.2
        bh = (s.estimated_time_min / max_time) * bar_area_h
        by = BAR_H - BAR_MARGIN - 30 - bh
        color = colors[i % len(colors)]
        bars += f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bar_width:.1f}" height="{bh:.1f}" fill="{color}" rx="3"/>\n'
        bars += f'<text x="{bx + bar_width/2:.1f}" y="{by - 4:.1f}" fill="#D1D5DB" font-size="10" text-anchor="middle">{s.estimated_time_min:.1f}m</text>\n'
        label = s.name.replace(" ", "\n")
        bars += f'<text x="{bx + bar_width/2:.1f}" y="{BAR_H - BAR_MARGIN - 14:.1f}" fill="#9CA3AF" font-size="9" text-anchor="middle">{s.name[:12]}</text>\n'

    bar_svg = f"""
    <svg width="{BAR_W}" height="{BAR_H}" style="background:#1F2937;border-radius:8px;">
      <line x1="{BAR_MARGIN}" y1="{BAR_MARGIN}" x2="{BAR_MARGIN}" y2="{BAR_H - BAR_MARGIN - 30}" stroke="#6B7280" stroke-width="1"/>
      <line x1="{BAR_MARGIN}" y1="{BAR_H - BAR_MARGIN - 30}" x2="{BAR_W - BAR_MARGIN}" y2="{BAR_H - BAR_MARGIN - 30}" stroke="#6B7280" stroke-width="1"/>
      <text x="{BAR_W//2}" y="{BAR_H - 6}" fill="#9CA3AF" font-size="12" text-anchor="middle">Time to Value (minutes)</text>
      {bars}
    </svg>"""

    # ---- Full HTML ---------------------------------------------------------
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>OCI Robot Cloud — Cost Optimizer Report</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background: #111827;
      color: #F9FAFB;
      font-family: 'Inter', 'Segoe UI', sans-serif;
      padding: 2rem;
      line-height: 1.6;
    }}
    h1 {{ font-size: 1.8rem; margin-bottom: 0.25rem; color: #60A5FA; }}
    h2 {{ font-size: 1.2rem; margin: 2rem 0 0.75rem; color: #93C5FD; }}
    .subtitle {{ color: #9CA3AF; margin-bottom: 1.5rem; font-size: 0.95rem; }}
    .params-bar {{
      display: flex; gap: 2rem; margin-bottom: 1.5rem;
      background: #1F2937; padding: 0.75rem 1.25rem; border-radius: 8px;
      font-size: 0.9rem;
    }}
    .params-bar span {{ color: #9CA3AF; }}
    .params-bar strong {{ color: #34D399; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 0.88rem; margin-bottom: 1rem; }}
    th {{
      background: #374151; color: #D1D5DB;
      padding: 0.5rem 0.75rem; text-align: left;
      border-bottom: 2px solid #4B5563;
    }}
    td {{ padding: 0.5rem 0.75rem; border-bottom: 1px solid #374151; }}
    tr:hover td {{ background: #1F2937; }}
    tr.highlight td {{ background: #1E3A5F; border-left: 3px solid #60A5FA; }}
    tr.highlight td:first-child {{ font-weight: 600; color: #60A5FA; }}
    .charts {{
      display: flex; flex-wrap: wrap; gap: 2rem; margin-top: 1.5rem;
    }}
    .chart-block {{ flex: 1; min-width: 300px; }}
    .chart-block h2 {{ margin-top: 0; }}
    .budget-concept {{
      background: #1F2937; border-radius: 8px; padding: 1.25rem;
      margin-top: 2rem; border-left: 4px solid #F59E0B;
    }}
    .budget-concept h2 {{ margin-top: 0; color: #F59E0B; }}
    .budget-concept p {{ color: #D1D5DB; font-size: 0.9rem; margin-top: 0.5rem; }}
    .slider-mock {{
      width: 100%; height: 8px; background: #374151;
      border-radius: 4px; margin: 1rem 0 0.5rem; position: relative;
    }}
    .slider-fill {{
      height: 8px; background: linear-gradient(90deg, #34D399, #60A5FA);
      border-radius: 4px; width: 55%;
    }}
    footer {{ margin-top: 2.5rem; color: #6B7280; font-size: 0.8rem; text-align: center; }}
  </style>
</head>
<body>
  <h1>OCI Robot Cloud — Training Cost Optimizer</h1>
  <p class="subtitle">Pareto-optimal configurations for your target success rate and budget</p>

  <div class="params-bar">
    <div><span>Target success rate: </span><strong>{target_success:.0%}</strong></div>
    <div><span>Budget: </span><strong>${budget_usd:.2f}</strong></div>
    <div><span>Scenarios evaluated: </span><strong>{len(scenarios)}</strong></div>
  </div>

  <h2>Scenario Comparison</h2>
  <table>
    <thead>
      <tr>
        <th>Scenario</th>
        <th>Demos</th>
        <th>BC Steps</th>
        <th>DAgger Iters</th>
        <th>GPUs</th>
        <th>Success Rate</th>
        <th>Cost (USD)</th>
        <th>Time</th>
        <th>Meets Target</th>
        <th>In Budget</th>
      </tr>
    </thead>
    <tbody>
      {table_rows}
    </tbody>
  </table>

  <div class="charts">
    <div class="chart-block">
      <h2>Cost vs. Success Rate</h2>
      {scatter_svg}
    </div>
    <div class="chart-block">
      <h2>Time to Value</h2>
      {bar_svg}
    </div>
  </div>

  <div class="budget-concept">
    <h2>Interactive Budget Slider (Concept)</h2>
    <p>
      In a production UI, dragging this slider would dynamically recompute the optimal
      configuration mix, showing how additional spend unlocks higher success rates and
      faster DAgger convergence. The current view is a static snapshot at
      <strong>${budget_usd:.2f}</strong>.
    </p>
    <div class="slider-mock"><div class="slider-fill"></div></div>
    <p style="font-size:0.8rem;color:#9CA3AF;">
      $0 ────────────── ${budget_usd:.2f} ──────────── $20.00
    </p>
  </div>

  <footer>Generated by OCI Robot Cloud Cost Optimizer · empirical model v1.0</footer>
</body>
</html>"""

    with open(output_path, "w") as f:
        f.write(html)
    return output_path


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

def create_app():
    try:
        from fastapi import FastAPI, Query
        from fastapi.responses import HTMLResponse, JSONResponse
    except ImportError:
        raise RuntimeError("FastAPI not installed. Run: pip install fastapi uvicorn")

    app = FastAPI(
        title="OCI Robot Cloud Cost Optimizer",
        description="Recommends optimal training configurations to minimize cost while meeting success targets.",
        version="1.0.0",
    )

    @app.get("/optimize")
    def optimize(
        target: float = Query(0.65, description="Target success rate (0–1)"),
        budget: float = Query(5.0, description="Budget in USD"),
        fmt: str = Query("json", description="Response format: json or html"),
    ):
        scenarios = optimize_for_budget(budget_usd=budget, target_success=target)
        if fmt == "html":
            import tempfile, os
            with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as tmp:
                tmp_path = tmp.name
            generate_html_report(scenarios, tmp_path, target_success=target, budget_usd=budget)
            with open(tmp_path) as f:
                content = f.read()
            os.unlink(tmp_path)
            return HTMLResponse(content=content)
        return JSONResponse(content={
            "target_success": target,
            "budget_usd": budget,
            "scenarios": [s.to_dict() for s in scenarios],
        })

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "cost_optimizer"}

    return app


# ---------------------------------------------------------------------------
# CLI helpers
# ---------------------------------------------------------------------------

def _print_scenarios(scenarios: List[TrainingScenario], target: float, budget: float) -> None:
    sep = "─" * 78
    print(f"\n{sep}")
    print(f"  OCI Robot Cloud — Cost Optimizer")
    print(f"  Target success: {target:.0%}   Budget: ${budget:.2f}")
    print(sep)
    header = f"{'Scenario':<20} {'Demos':>6} {'BC Steps':>9} {'DAgger':>7} {'GPUs':>5} {'Success':>8} {'Cost':>8} {'Time':>8}"
    print(header)
    print("─" * 78)
    for s in scenarios:
        marker = " ★" if s.name == "Recommended" else "  "
        print(
            f"{s.name + marker:<20} {s.n_demos:>6} {s.bc_steps:>9,} {s.dagger_iters:>7} "
            f"{s.n_gpus:>5} {s.estimated_success_rate:>7.1%} "
            f"${s.estimated_cost_usd:>7.4f} {s.estimated_time_min:>6.1f}m"
        )
    print(sep + "\n")


def _mock_run() -> None:
    """Run a quick self-test with known parameters and print results."""
    print("=== Mock / Self-test ===")

    # Basic model checks
    sr_zero = estimate_success_rate(0, 0, 0)
    assert sr_zero == 0.0, f"Expected 0.0, got {sr_zero}"

    sr_base = estimate_success_rate(500, 10_000, 0)
    assert abs(sr_base - EMPIRICAL_PARAMS["bc_base_success"]) < 0.01, f"BC base mismatch: {sr_base}"

    sr_dagger = estimate_success_rate(500, 10_000, 5)
    expected = min(
        EMPIRICAL_PARAMS["bc_base_success"] + 5 * EMPIRICAL_PARAMS["dagger_success_per_iter"],
        EMPIRICAL_PARAMS["dagger_max_success"],
    )
    assert abs(sr_dagger - expected) < 0.01, f"DAgger estimate mismatch: {sr_dagger} vs {expected}"

    # Optimizer run
    scenarios = optimize_for_budget(budget_usd=5.0, target_success=0.65)
    assert len(scenarios) >= 1, "Expected at least one scenario"

    _print_scenarios(scenarios, target=0.65, budget=5.0)

    # HTML report
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as tmp:
        path = tmp.name
    generate_html_report(scenarios, path, target_success=0.65, budget_usd=5.0)
    print(f"HTML report written to: {path}")

    print("All mock checks passed ✓")


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="OCI Robot Cloud Training Cost Optimizer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--target-success",
        type=float,
        default=0.65,
        metavar="RATE",
        help="Target policy success rate (0.0–1.0). Default: 0.65",
    )
    parser.add_argument(
        "--budget",
        type=float,
        default=5.0,
        metavar="USD",
        help="Training budget in USD. Default: 5.0",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        metavar="PATH",
        help="Output path for HTML report (optional). Prints JSON to stdout if not set.",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Run self-test / mock mode and exit.",
    )
    parser.add_argument(
        "--serve",
        action="store_true",
        help="Start FastAPI server.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8013,
        help="Port for FastAPI server. Default: 8013",
    )
    args = parser.parse_args()

    if args.mock:
        _mock_run()
        return

    if args.serve:
        try:
            import uvicorn
        except ImportError:
            print("uvicorn not installed. Run: pip install uvicorn", file=sys.stderr)
            sys.exit(1)
        app = create_app()
        print(f"Starting OCI Robot Cloud Cost Optimizer on port {args.port}...")
        uvicorn.run(app, host="0.0.0.0", port=args.port)
        return

    # Default: optimize and report
    scenarios = optimize_for_budget(
        budget_usd=args.budget,
        target_success=args.target_success,
    )

    _print_scenarios(scenarios, target=args.target_success, budget=args.budget)

    if args.output:
        out = generate_html_report(
            scenarios,
            args.output,
            target_success=args.target_success,
            budget_usd=args.budget,
        )
        print(f"HTML report written to: {out}")
    else:
        print(json.dumps([s.to_dict() for s in scenarios], indent=2))


if __name__ == "__main__":
    main()
