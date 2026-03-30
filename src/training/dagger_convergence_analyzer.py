#!/usr/bin/env python3
"""
DAgger Convergence Analyzer
Detects policy convergence (SR plateau), identifies optimal stopping point,
and compares convergence speed across DAgger run configurations.

Usage:
    python dagger_convergence_analyzer.py [--mock] [--n-iters 15]
        [--output /tmp/dagger_convergence_analyzer.html] [--seed 42]
"""

import argparse
import math
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class IterationResult:
    iteration: int
    demos_collected: int
    steps_trained: int
    val_loss: float
    eval_sr: float
    sr_delta: float        # vs previous iteration
    cost_usd: float
    wall_time_min: float


@dataclass
class DAggerRun:
    run_id: str
    config: Dict
    iterations: List[IterationResult] = field(default_factory=list)
    converged: bool = False
    converged_at_iter: int = -1
    final_sr: float = 0.0
    total_cost_usd: float = 0.0


# ---------------------------------------------------------------------------
# Preset configurations
# ---------------------------------------------------------------------------

CONFIGS = {
    "fast": {
        "lr": 5e-4,
        "batch_size": 32,
        "n_demos_per_iter": 20,
        "quality_threshold": 0.3,
        "description": "Low quality gate, fast iteration",
    },
    "balanced": {
        "lr": 2e-4,
        "batch_size": 64,
        "n_demos_per_iter": 50,
        "quality_threshold": 0.5,
        "description": "Balanced speed vs quality",
    },
    "thorough": {
        "lr": 1e-4,
        "batch_size": 64,
        "n_demos_per_iter": 100,
        "quality_threshold": 0.75,
        "description": "High quality gate, 3-phase training",
    },
    "lora_efficient": {
        "lr": 3e-4,
        "batch_size": 32,
        "n_demos_per_iter": 30,
        "quality_threshold": 0.45,
        "description": "LoRA adapter, parameter-efficient",
    },
    "dagger_run9_style": {
        "lr": 1.5e-4,
        "batch_size": 48,
        "n_demos_per_iter": 80,
        "quality_threshold": 0.65,
        "description": "Mirrors production DAgger run 9 config",
    },
}


# ---------------------------------------------------------------------------
# Simulation
# ---------------------------------------------------------------------------

def simulate_dagger_run(
    run_id: str,
    n_iters: int = 15,
    config: Optional[Dict] = None,
    seed: int = 42,
) -> DAggerRun:
    """Simulate a DAgger learning curve with realistic SR progression."""
    if config is None:
        config = CONFIGS["balanced"]

    rng = random.Random(seed + abs(hash(run_id)) % 10_000)

    qt = config.get("quality_threshold", 0.5)
    n_demos = config.get("n_demos_per_iter", 50)
    lr = config.get("lr", 2e-4)

    # Convergence speed inversely related to quality threshold:
    # higher threshold → slower but better peak SR
    speed_factor = 0.55 - 0.25 * qt           # 0.30 (thorough) .. 0.47 (fast)
    peak_sr = 0.55 + 0.35 * qt                # 0.66 (fast) .. 0.81 (thorough)
    noise_scale = 0.015 + 0.010 * (1.0 - qt)

    # Cost model: ~$0.012 per demo + $0.0003 per training step
    steps_per_iter = int(n_demos * 80 * (lr / 2e-4) ** -0.3)
    cost_per_iter = n_demos * 0.012 + steps_per_iter * 0.0003

    run = DAggerRun(run_id=run_id, config=config)
    prev_sr = 0.05  # BC baseline
    val_loss = 0.55

    for i in range(1, n_iters + 1):
        # Logistic-style SR growth
        progress = 1.0 - math.exp(-speed_factor * i)
        base_sr = 0.05 + (peak_sr - 0.05) * progress
        noise = rng.gauss(0, noise_scale)
        sr = max(0.0, min(1.0, base_sr + noise))

        # val_loss decays roughly in sync
        val_loss = max(0.05, val_loss * (0.97 - 0.01 * speed_factor) + rng.gauss(0, 0.005))

        delta = sr - prev_sr
        wall_time = n_demos * 0.08 + steps_per_iter * 0.00015

        result = IterationResult(
            iteration=i,
            demos_collected=n_demos,
            steps_trained=steps_per_iter,
            val_loss=round(val_loss, 4),
            eval_sr=round(sr, 4),
            sr_delta=round(delta, 4),
            cost_usd=round(cost_per_iter, 4),
            wall_time_min=round(wall_time, 2),
        )
        run.iterations.append(result)
        run.total_cost_usd += cost_per_iter
        prev_sr = sr

    run.final_sr = run.iterations[-1].eval_sr
    run.total_cost_usd = round(run.total_cost_usd, 4)

    conv_iter = detect_convergence(run.iterations)
    if conv_iter >= 0:
        run.converged = True
        run.converged_at_iter = conv_iter

    return run


# ---------------------------------------------------------------------------
# Convergence detection
# ---------------------------------------------------------------------------

def detect_convergence(
    iterations: List[IterationResult],
    window: int = 3,
    delta_threshold: float = 0.02,
) -> int:
    """Return iteration number where convergence is detected, or -1."""
    if len(iterations) < window:
        return -1

    for idx in range(window - 1, len(iterations)):
        window_iters = iterations[idx - window + 1 : idx + 1]
        deltas = [abs(it.sr_delta) for it in window_iters]
        if all(d < delta_threshold for d in deltas):
            return iterations[idx - window + 1].iteration

    return -1


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------

def compare_runs(runs: List[DAggerRun]) -> Dict:
    """Return best final SR, fastest convergence, most cost-efficient run."""
    best_sr_run = max(runs, key=lambda r: r.final_sr)
    converged = [r for r in runs if r.converged]
    fastest = min(converged, key=lambda r: r.converged_at_iter) if converged else None
    efficient = max(runs, key=lambda r: r.final_sr / max(r.total_cost_usd, 0.001))
    return {
        "best_sr": best_sr_run,
        "fastest": fastest,
        "most_efficient": efficient,
    }


# ---------------------------------------------------------------------------
# HTML / SVG report
# ---------------------------------------------------------------------------

COLORS = ["#38bdf8", "#C74634", "#4ade80", "#facc15", "#a78bfa"]


def _sr_chart_svg(runs: List[DAggerRun], width: int = 700, height: int = 320) -> str:
    pad = {"top": 20, "right": 20, "bottom": 50, "left": 55}
    iw = width - pad["left"] - pad["right"]
    ih = height - pad["top"] - pad["bottom"]

    max_iter = max(len(r.iterations) for r in runs)
    min_sr, max_sr = 0.0, 1.0

    def tx(i_idx: int) -> float:
        return pad["left"] + i_idx / max(max_iter - 1, 1) * iw

    def ty(sr: float) -> float:
        return pad["top"] + (1.0 - (sr - min_sr) / (max_sr - min_sr)) * ih

    lines = []
    markers = []

    for run_idx, run in enumerate(runs):
        color = COLORS[run_idx % len(COLORS)]
        pts = " ".join(
            f"{tx(it.iteration - 1):.1f},{ty(it.eval_sr):.1f}"
            for it in run.iterations
        )
        lines.append(
            f'<polyline points="{pts}" fill="none" stroke="{color}" '
            f'stroke-width="2.5" opacity="0.9"/>'
        )
        # Convergence marker
        if run.converged and run.converged_at_iter >= 1:
            ci = run.converged_at_iter - 1
            sr_at = run.iterations[ci].eval_sr
            cx, cy = tx(ci), ty(sr_at)
            markers.append(
                f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="7" fill="{color}" '
                f'stroke="#fff" stroke-width="1.5" opacity="0.95">'
                f'<title>{run.run_id} converged @ iter {run.converged_at_iter}</title>'
                f'</circle>'
            )

    # Axes
    axis_color = "#94a3b8"
    grid_lines = []
    for sr_tick in [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]:
        y = ty(sr_tick)
        grid_lines.append(
            f'<line x1="{pad["left"]}" y1="{y:.1f}" x2="{pad["left"]+iw}" y2="{y:.1f}" '
            f'stroke="#334155" stroke-dasharray="4"/>'
        )
        grid_lines.append(
            f'<text x="{pad["left"]-8}" y="{y+4:.1f}" fill="{axis_color}" '
            f'font-size="11" text-anchor="end">{sr_tick:.1f}</text>'
        )

    x_ticks = []
    for i in range(0, max_iter, max(1, max_iter // 5)):
        x = tx(i)
        x_ticks.append(
            f'<text x="{x:.1f}" y="{height-12}" fill="{axis_color}" '
            f'font-size="11" text-anchor="middle">{i+1}</text>'
        )

    # Legend
    legend = []
    for run_idx, run in enumerate(runs):
        lx = pad["left"] + run_idx * 140
        color = COLORS[run_idx % len(COLORS)]
        legend.append(
            f'<line x1="{lx}" y1="{height-34}" x2="{lx+22}" y2="{height-34}" '
            f'stroke="{color}" stroke-width="2.5"/>'
        )
        legend.append(
            f'<text x="{lx+26}" y="{height-30}" fill="{axis_color}" font-size="11">'
            f'{run.run_id}</text>'
        )

    axis_labels = [
        f'<text x="{pad["left"]+iw//2}" y="{height-2}" fill="{axis_color}" '
        f'font-size="12" text-anchor="middle">DAgger Iteration</text>',
        f'<text x="14" y="{pad["top"]+ih//2}" fill="{axis_color}" font-size="12" '
        f'text-anchor="middle" transform="rotate(-90,14,{pad["top"]+ih//2})">Success Rate</text>',
    ]

    svg_inner = "\n".join(grid_lines + x_ticks + lines + markers + legend + axis_labels)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'style="background:#0f172a;border-radius:8px">\n{svg_inner}\n</svg>'
    )


def _pareto_svg(runs: List[DAggerRun], width: int = 500, height: int = 300) -> str:
    pad = {"top": 20, "right": 20, "bottom": 50, "left": 65}
    iw = width - pad["left"] - pad["right"]
    ih = height - pad["top"] - pad["bottom"]

    costs = [r.total_cost_usd for r in runs]
    srs = [r.final_sr for r in runs]
    min_c, max_c = min(costs), max(costs)
    min_sr, max_sr = 0.0, 1.0

    def tx(c: float) -> float:
        span = max(max_c - min_c, 0.01)
        return pad["left"] + (c - min_c) / span * iw

    def ty(sr: float) -> float:
        return pad["top"] + (1.0 - (sr - min_sr) / (max_sr - min_sr)) * ih

    # Pareto frontier
    sorted_runs = sorted(runs, key=lambda r: r.total_cost_usd)
    pareto = []
    best = -1.0
    for r in sorted_runs:
        if r.final_sr > best:
            pareto.append(r)
            best = r.final_sr

    pareto_pts = " ".join(f"{tx(r.total_cost_usd):.1f},{ty(r.final_sr):.1f}" for r in pareto)

    elements = []
    if len(pareto) > 1:
        elements.append(
            f'<polyline points="{pareto_pts}" fill="none" stroke="#C74634" '
            f'stroke-width="1.5" stroke-dasharray="6 3" opacity="0.7"/>'
        )

    axis_color = "#94a3b8"
    for sr_tick in [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]:
        y = ty(sr_tick)
        elements.append(
            f'<line x1="{pad["left"]}" y1="{y:.1f}" x2="{pad["left"]+iw}" y2="{y:.1f}" '
            f'stroke="#334155" stroke-dasharray="4"/>'
        )
        elements.append(
            f'<text x="{pad["left"]-8}" y="{y+4:.1f}" fill="{axis_color}" '
            f'font-size="11" text-anchor="end">{sr_tick:.1f}</text>'
        )

    for run_idx, run in enumerate(runs):
        color = COLORS[run_idx % len(COLORS)]
        cx, cy = tx(run.total_cost_usd), ty(run.final_sr)
        elements.append(
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="8" fill="{color}" opacity="0.85">'
            f'<title>{run.run_id}: SR={run.final_sr:.3f}, cost=${run.total_cost_usd:.2f}</title>'
            f'</circle>'
        )
        elements.append(
            f'<text x="{cx+11:.1f}" y="{cy+4:.1f}" fill="{color}" font-size="11">'
            f'{run.run_id}</text>'
        )

    axis_labels = [
        f'<text x="{pad["left"]+iw//2}" y="{height-4}" fill="{axis_color}" '
        f'font-size="12" text-anchor="middle">Total Cost (USD)</text>',
        f'<text x="14" y="{pad["top"]+ih//2}" fill="{axis_color}" font-size="12" '
        f'text-anchor="middle" transform="rotate(-90,14,{pad["top"]+ih//2})">Final SR</text>',
    ]
    elements.extend(axis_labels)

    svg_inner = "\n".join(elements)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'style="background:#0f172a;border-radius:8px">\n{svg_inner}\n</svg>'
    )


def generate_html_report(runs: List[DAggerRun], n_iters: int) -> str:
    comparison = compare_runs(runs)
    best_sr_run = comparison["best_sr"]
    fastest_run = comparison["fastest"]
    efficient_run = comparison["most_efficient"]

    # KPI cards
    kpi_fastest = (
        f"Iter {fastest_run.converged_at_iter} ({fastest_run.run_id})"
        if fastest_run else "None converged"
    )
    kpi_efficient = f"{efficient_run.run_id} ({efficient_run.final_sr/max(efficient_run.total_cost_usd,0.001):.2f} SR/$)"

    kpi_html = f"""
    <div class="kpi-row">
      <div class="kpi-card">
        <div class="kpi-label">Best SR Achieved</div>
        <div class="kpi-value">{best_sr_run.final_sr:.1%}</div>
        <div class="kpi-sub">{best_sr_run.run_id}</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Fastest Convergence</div>
        <div class="kpi-value">{kpi_fastest}</div>
        <div class="kpi-sub">window=3, δ&lt;0.02</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Most Efficient</div>
        <div class="kpi-value">{kpi_efficient}</div>
        <div class="kpi-sub">SR per dollar</div>
      </div>
    </div>"""

    # Convergence summary table
    conv_rows = []
    for run in runs:
        conv_str = f"Iter {run.converged_at_iter}" if run.converged else "Not converged"
        cfg = run.config
        cfg_summary = (
            f"lr={cfg.get('lr','-')}, bs={cfg.get('batch_size','-')}, "
            f"demos={cfg.get('n_demos_per_iter','-')}, qt={cfg.get('quality_threshold','-')}"
        )
        conv_rows.append(
            f"<tr><td>{run.run_id}</td><td>{cfg_summary}</td>"
            f"<td>{conv_str}</td><td>{run.final_sr:.1%}</td>"
            f"<td>${run.total_cost_usd:.2f}</td><td>{len(run.iterations)}</td></tr>"
        )
    conv_table = "\n".join(conv_rows)

    # Per-iteration detail for best run
    detail_rows = []
    for it in best_sr_run.iterations:
        delta_cls = "pos" if it.sr_delta >= 0 else "neg"
        sign = "+" if it.sr_delta >= 0 else ""
        detail_rows.append(
            f"<tr><td>{it.iteration}</td><td>{it.demos_collected}</td>"
            f"<td>{it.eval_sr:.1%}</td>"
            f'<td class="{delta_cls}">{sign}{it.sr_delta:.1%}</td>'
            f"<td>${it.cost_usd:.4f}</td></tr>"
        )
    detail_table = "\n".join(detail_rows)

    sr_svg = _sr_chart_svg(runs)
    pareto_svg = _pareto_svg(runs)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>DAgger Convergence Analyzer</title>
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #1e293b; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif;
          padding: 24px 32px; }}
  h1 {{ color: #C74634; font-size: 1.7rem; margin-bottom: 4px; }}
  h2 {{ color: #C74634; font-size: 1.2rem; margin: 28px 0 12px; }}
  .subtitle {{ color: #94a3b8; font-size: 0.88rem; margin-bottom: 28px; }}
  .kpi-row {{ display: flex; gap: 18px; margin-bottom: 28px; flex-wrap: wrap; }}
  .kpi-card {{ background: #0f172a; border: 1px solid #334155; border-radius: 10px;
               padding: 18px 24px; flex: 1; min-width: 200px; }}
  .kpi-label {{ color: #64748b; font-size: 0.78rem; text-transform: uppercase;
                letter-spacing: .05em; margin-bottom: 6px; }}
  .kpi-value {{ color: #f1f5f9; font-size: 1.6rem; font-weight: 700; }}
  .kpi-sub {{ color: #94a3b8; font-size: 0.78rem; margin-top: 4px; }}
  .charts {{ display: flex; gap: 24px; flex-wrap: wrap; margin-bottom: 28px; }}
  .chart-box {{ background: #0f172a; border: 1px solid #334155; border-radius: 10px;
                padding: 16px; }}
  .chart-title {{ color: #94a3b8; font-size: 0.82rem; text-transform: uppercase;
                  letter-spacing: .05em; margin-bottom: 10px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.85rem; }}
  th {{ background: #0f172a; color: #C74634; font-weight: 600; padding: 9px 12px;
        text-align: left; border-bottom: 1px solid #334155; }}
  td {{ padding: 8px 12px; border-bottom: 1px solid #1e293b; color: #cbd5e1; }}
  tr:hover td {{ background: #1e3a5f22; }}
  .pos {{ color: #4ade80; }}
  .neg {{ color: #f87171; }}
  .section {{ background: #0f172a; border: 1px solid #334155; border-radius: 10px;
              padding: 18px 22px; margin-bottom: 22px; }}
  footer {{ color: #475569; font-size: 0.75rem; margin-top: 32px; text-align: center; }}
</style>
</head>
<body>
<h1>DAgger Convergence Analyzer</h1>
<p class="subtitle">
  Analyzing {len(runs)} configurations over up to {n_iters} iterations each.
  Convergence: |SR delta| &lt; 0.02 for 3 consecutive iterations.
</p>

{kpi_html}

<h2>Success Rate Progression</h2>
<div class="charts">
  <div class="chart-box">
    <div class="chart-title">SR over Iterations — circles mark convergence point</div>
    {sr_svg}
  </div>
</div>

<h2>Cost vs Final SR — Pareto Frontier</h2>
<div class="charts">
  <div class="chart-box">
    <div class="chart-title">Dashed line = Pareto frontier; higher-left is better</div>
    {pareto_svg}
  </div>
</div>

<h2>Convergence Summary</h2>
<div class="section">
  <table>
    <thead>
      <tr>
        <th>Run ID</th><th>Config Summary</th><th>Converged At</th>
        <th>Final SR</th><th>Total Cost</th><th>Iterations Run</th>
      </tr>
    </thead>
    <tbody>{conv_table}</tbody>
  </table>
</div>

<h2>Per-Iteration Detail — {best_sr_run.run_id} (best SR)</h2>
<div class="section">
  <table>
    <thead>
      <tr><th>Iter</th><th>Demos</th><th>SR</th><th>SR Delta</th><th>Cost</th></tr>
    </thead>
    <tbody>{detail_table}</tbody>
  </table>
</div>

<footer>OCI Robot Cloud — DAgger Convergence Analyzer | Oracle Confidential</footer>
</body>
</html>"""


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="DAgger Convergence Analyzer")
    parser.add_argument("--mock", action="store_true", default=True,
                        help="Use simulated data (default: True)")
    parser.add_argument("--n-iters", type=int, default=15,
                        help="Number of DAgger iterations to simulate (default: 15)")
    parser.add_argument("--output", default="/tmp/dagger_convergence_analyzer.html",
                        help="Output HTML path")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed for reproducibility")
    args = parser.parse_args()

    print(f"[DAgger Convergence Analyzer] Simulating {len(CONFIGS)} configs x {args.n_iters} iters ...")

    runs: List[DAggerRun] = []
    for run_id, cfg in CONFIGS.items():
        run = simulate_dagger_run(
            run_id=run_id,
            n_iters=args.n_iters,
            config=cfg,
            seed=args.seed,
        )
        conv_str = f"iter {run.converged_at_iter}" if run.converged else "not converged"
        print(
            f"  {run_id:<22} final_sr={run.final_sr:.3f}  "
            f"converged={conv_str:<18}  cost=${run.total_cost_usd:.2f}"
        )
        runs.append(run)

    comparison = compare_runs(runs)
    print("\n[Summary]")
    print(f"  Best SR   : {comparison['best_sr'].run_id}  ({comparison['best_sr'].final_sr:.1%})")
    if comparison["fastest"]:
        print(f"  Fastest   : {comparison['fastest'].run_id}  "
              f"(iter {comparison['fastest'].converged_at_iter})")
    print(f"  Efficient : {comparison['most_efficient'].run_id}")

    html = generate_html_report(runs, args.n_iters)
    with open(args.output, "w", encoding="utf-8") as fh:
        fh.write(html)
    print(f"\n[Report] Saved to {args.output}")


if __name__ == "__main__":
    main()
