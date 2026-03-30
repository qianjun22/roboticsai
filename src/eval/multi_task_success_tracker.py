#!/usr/bin/env python3
"""
multi_task_success_tracker.py — Track success rates across multiple robotic tasks over time.

Shows learning progress per task and cross-task interference detection.
Generates a self-contained HTML report with SVG visualizations.

Usage:
    python multi_task_success_tracker.py --mock --output /tmp/multi_task_success_tracker.html --seed 42
"""

import argparse
import math
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Tuple

# ---------------------------------------------------------------------------
# Task definitions
# ---------------------------------------------------------------------------

TASKS = [
    {"name": "pick_and_place", "difficulty": 0.3, "category": "manipulation"},
    {"name": "stack_blocks",   "difficulty": 0.5, "category": "manipulation"},
    {"name": "pour_liquid",    "difficulty": 0.6, "category": "manipulation"},
    {"name": "open_drawer",    "difficulty": 0.4, "category": "interaction"},
    {"name": "close_door",     "difficulty": 0.35, "category": "interaction"},
    {"name": "handover",       "difficulty": 0.55, "category": "interaction"},
    {"name": "peg_insert",     "difficulty": 0.8, "category": "assembly"},
    {"name": "tool_use",       "difficulty": 0.9, "category": "assembly"},
]

ALGOS = ["BC", "DAgger", "DAgger+Curr"]

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class TrainingRun:
    run_id: str
    algo: str
    task: str
    episode: int
    success: bool
    timestamp: datetime


# ---------------------------------------------------------------------------
# Simulation
# ---------------------------------------------------------------------------

def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def simulate_training(
    algo: str,
    tasks: List[dict],
    n_episodes: int = 200,
    seed: int = 42,
) -> List[TrainingRun]:
    """
    Generate mock training runs.
    - SR improves over episodes via sigmoid curve
    - DAgger converges faster than BC; DAgger+Curr even faster
    - Harder tasks have lower asymptotic SR
    - Gaussian noise added
    """
    rng = random.Random(seed)
    runs: List[TrainingRun] = []
    base_time = datetime(2026, 3, 1, 0, 0, 0)

    # Speed of convergence per algo
    speed = {"BC": 0.025, "DAgger": 0.045, "DAgger+Curr": 0.060}[algo]
    # Asymptotic SR penalty for algo
    algo_ceiling = {"BC": 0.85, "DAgger": 0.92, "DAgger+Curr": 0.97}[algo]

    for task in tasks:
        diff = task["difficulty"]
        task_ceiling = algo_ceiling * (1.0 - 0.6 * diff)  # harder → lower ceiling
        midpoint = n_episodes * (0.4 + 0.3 * diff)         # harder → later midpoint

        for ep in range(1, n_episodes + 1):
            # Sigmoid progress
            raw_sr = task_ceiling * _sigmoid(speed * (ep - midpoint))
            # Gaussian noise (σ proportional to difficulty)
            noise = rng.gauss(0.0, 0.06 + 0.04 * diff)
            sr = max(0.0, min(1.0, raw_sr + noise))
            success = rng.random() < sr

            run_id = f"{algo}_{task['name']}_ep{ep:04d}"
            ts = base_time + timedelta(minutes=ep * 3)
            runs.append(TrainingRun(
                run_id=run_id,
                algo=algo,
                task=task["name"],
                episode=ep,
                success=success,
                timestamp=ts,
            ))

    return runs


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

def compute_task_matrix(runs: List[TrainingRun]) -> Dict[str, Dict[str, float]]:
    """
    Returns dict: algo → task → final_sr (average over last 20 episodes).
    """
    # Group runs
    buckets: Dict[Tuple[str, str], List[bool]] = {}
    ep_max: Dict[Tuple[str, str], int] = {}
    for r in runs:
        key = (r.algo, r.task)
        ep_max[key] = max(ep_max.get(key, 0), r.episode)

    for r in runs:
        key = (r.algo, r.task)
        tail = ep_max[key] - 19  # last 20 episodes
        if r.episode >= tail:
            buckets.setdefault(key, []).append(r.success)

    matrix: Dict[str, Dict[str, float]] = {}
    for (algo, task), successes in buckets.items():
        sr = sum(successes) / len(successes) if successes else 0.0
        matrix.setdefault(algo, {})[task] = round(sr, 4)

    return matrix


def detect_interference(
    matrix: Dict[str, Dict[str, float]],
) -> Dict[str, List[Tuple[str, str, float]]]:
    """
    For each algo, find task pairs where high SR on task A correlates with
    lower SR on task B (negative transfer proxy: task_b SR < mean - 1σ when
    task_a SR > mean).

    Returns algo → list of (task_a, task_b, delta) tuples.
    """
    interference: Dict[str, List[Tuple[str, str, float]]] = {}

    for algo, task_srs in matrix.items():
        tasks_list = list(task_srs.keys())
        srs = [task_srs[t] for t in tasks_list]
        mean_sr = sum(srs) / len(srs) if srs else 0.0
        var = sum((s - mean_sr) ** 2 for s in srs) / len(srs) if srs else 0.0
        std = math.sqrt(var)

        pairs: List[Tuple[str, str, float]] = []
        for ta in tasks_list:
            for tb in tasks_list:
                if ta == tb:
                    continue
                sr_a = task_srs[ta]
                sr_b = task_srs[tb]
                # Interference: task_a is above mean AND task_b is below mean - 0.5σ
                if sr_a > mean_sr and sr_b < (mean_sr - 0.5 * std):
                    delta = round(sr_b - mean_sr, 4)
                    pairs.append((ta, tb, delta))

        if pairs:
            interference[algo] = pairs

    return interference


# ---------------------------------------------------------------------------
# Episode SR curve (for SVG line chart)
# ---------------------------------------------------------------------------

def compute_episode_sr_curve(
    runs: List[TrainingRun],
    algo: str,
    window: int = 20,
) -> Dict[str, List[Tuple[int, float]]]:
    """
    Returns task → [(episode_bin, sr), ...] smoothed with a rolling window.
    Only for the given algo.
    """
    from collections import defaultdict

    task_ep_success: Dict[str, Dict[int, List[bool]]] = defaultdict(lambda: defaultdict(list))
    for r in runs:
        if r.algo == algo:
            task_ep_success[r.task][r.episode].append(r.success)

    curves: Dict[str, List[Tuple[int, float]]] = {}
    bin_size = 10  # group episodes into bins of 10

    for task, ep_dict in task_ep_success.items():
        max_ep = max(ep_dict.keys())
        bins: List[Tuple[int, float]] = []
        buffer: List[bool] = []
        for ep in range(1, max_ep + 1):
            buffer.extend(ep_dict.get(ep, []))
            if ep % bin_size == 0:
                recent = buffer[-window:] if len(buffer) >= window else buffer
                sr = sum(recent) / len(recent) if recent else 0.0
                bins.append((ep, round(sr, 4)))
        curves[task] = bins

    return curves


# ---------------------------------------------------------------------------
# HTML / SVG rendering
# ---------------------------------------------------------------------------

COLORS = [
    "#60a5fa", "#34d399", "#f59e0b", "#f87171",
    "#a78bfa", "#fb923c", "#38bdf8", "#4ade80",
]

TASK_COLORS = {t["name"]: COLORS[i] for i, t in enumerate(TASKS)}


def _sr_color(sr: float) -> str:
    """Interpolate green (#22c55e) → yellow (#eab308) → red (#ef4444) by SR."""
    if sr >= 0.5:
        # green to yellow
        t = 1.0 - (sr - 0.5) / 0.5
        r = int(34 + t * (234 - 34))
        g = int(197 + t * (179 - 197))
        b = int(94 + t * (8 - 94))
    else:
        # yellow to red
        t = sr / 0.5
        r = int(239 + t * (234 - 239))
        g = int(68 + t * (179 - 68))
        b = int(68 + t * (8 - 68))
    return f"rgb({r},{g},{b})"


def _build_heatmap_svg(matrix: Dict[str, Dict[str, float]]) -> str:
    task_names = [t["name"] for t in TASKS]
    algo_names = ALGOS
    cell_w, cell_h = 110, 40
    label_w, label_h = 130, 30
    width = label_w + len(algo_names) * cell_w + 20
    height = label_h + len(task_names) * cell_h + 10

    svg = [f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg" '
           f'style="font-family:monospace;background:#0f172a;border-radius:8px;">']

    # Column headers
    for ci, algo in enumerate(algo_names):
        x = label_w + ci * cell_w + cell_w // 2
        svg.append(f'<text x="{x}" y="20" fill="#94a3b8" font-size="12" '
                   f'text-anchor="middle" font-weight="bold">{algo}</text>')

    # Rows
    for ri, task in enumerate(task_names):
        y_top = label_h + ri * cell_h
        cy = y_top + cell_h // 2 + 5
        # Row label
        svg.append(f'<text x="{label_w - 8}" y="{cy}" fill="#cbd5e1" font-size="11" '
                   f'text-anchor="end">{task}</text>')
        for ci, algo in enumerate(algo_names):
            sr = matrix.get(algo, {}).get(task, 0.0)
            color = _sr_color(sr)
            x = label_w + ci * cell_w
            svg.append(f'<rect x="{x+2}" y="{y_top+2}" width="{cell_w-4}" '
                       f'height="{cell_h-4}" rx="4" fill="{color}" opacity="0.85"/>')
            svg.append(f'<text x="{x + cell_w//2}" y="{cy}" fill="#0f172a" '
                       f'font-size="12" text-anchor="middle" font-weight="bold">'
                       f'{sr*100:.1f}%</text>')

    svg.append('</svg>')
    return "\n".join(svg)


def _build_linechart_svg(curves: Dict[str, List[Tuple[int, float]]]) -> str:
    width, height = 700, 300
    pad_l, pad_r, pad_t, pad_b = 50, 20, 20, 40

    # Find x/y range
    all_eps = [ep for pts in curves.values() for ep, _ in pts]
    max_ep = max(all_eps) if all_eps else 200

    def px(ep: float) -> float:
        return pad_l + (ep / max_ep) * (width - pad_l - pad_r)

    def py(sr: float) -> float:
        return pad_t + (1.0 - sr) * (height - pad_t - pad_b)

    svg = [f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg" '
           f'style="font-family:monospace;background:#0f172a;border-radius:8px;">']

    # Grid lines
    for sr_tick in [0.0, 0.25, 0.5, 0.75, 1.0]:
        y = py(sr_tick)
        svg.append(f'<line x1="{pad_l}" y1="{y:.1f}" x2="{width-pad_r}" y2="{y:.1f}" '
                   f'stroke="#334155" stroke-width="1"/>')
        svg.append(f'<text x="{pad_l-6}" y="{y+4:.1f}" fill="#64748b" font-size="10" '
                   f'text-anchor="end">{int(sr_tick*100)}%</text>')

    # X-axis ticks
    for ep_tick in range(0, max_ep + 1, 40):
        x = px(ep_tick)
        svg.append(f'<text x="{x:.1f}" y="{height-5}" fill="#64748b" font-size="10" '
                   f'text-anchor="middle">{ep_tick}</text>')

    # Lines per task
    for task, pts in curves.items():
        color = TASK_COLORS.get(task, "#60a5fa")
        if not pts:
            continue
        d_parts = [f"M {px(pts[0][0]):.1f},{py(pts[0][1]):.1f}"]
        for ep, sr in pts[1:]:
            d_parts.append(f"L {px(ep):.1f},{py(sr):.1f}")
        d = " ".join(d_parts)
        svg.append(f'<path d="{d}" stroke="{color}" stroke-width="2" fill="none" opacity="0.9"/>')
        # Legend label at last point
        last_ep, last_sr = pts[-1]
        svg.append(f'<text x="{px(last_ep)+3:.1f}" y="{py(last_sr)+4:.1f}" '
                   f'fill="{color}" font-size="9">{task.replace("_"," ")}</text>')

    svg.append('</svg>')
    return "\n".join(svg)


def build_html_report(
    matrix: Dict[str, Dict[str, float]],
    interference: Dict[str, List[Tuple[str, str, float]]],
    curves: Dict[str, List[Tuple[int, float]]],
) -> str:
    task_names = [t["name"] for t in TASKS]

    # KPI cards
    all_srs = [(algo, task, sr)
               for algo, td in matrix.items()
               for task, sr in td.items()]
    avg_sr = sum(s for _, _, s in all_srs) / len(all_srs) if all_srs else 0.0
    best = max(all_srs, key=lambda x: x[2]) if all_srs else ("—", "—", 0.0)
    worst = min(all_srs, key=lambda x: x[2]) if all_srs else ("—", "—", 0.0)

    kpi_html = f"""
    <div class="kpi-row">
      <div class="kpi-card">
        <div class="kpi-label">Best Task</div>
        <div class="kpi-value">{best[1].replace('_',' ')}</div>
        <div class="kpi-sub">{best[0]} &mdash; {best[2]*100:.1f}%</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Worst Task</div>
        <div class="kpi-value">{worst[1].replace('_',' ')}</div>
        <div class="kpi-sub">{worst[0]} &mdash; {worst[2]*100:.1f}%</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Avg SR (All Tasks)</div>
        <div class="kpi-value">{avg_sr*100:.1f}%</div>
        <div class="kpi-sub">across {len(ALGOS)} algos &times; {len(TASKS)} tasks</div>
      </div>
    </div>
    """

    heatmap_svg = _build_heatmap_svg(matrix)
    linechart_svg = _build_linechart_svg(curves)

    # Table with interference warnings
    header_cells = "".join(f"<th>{a}</th>" for a in ALGOS)
    table_rows = []
    for task in task_names:
        cells = [f"<td>{task.replace('_',' ')}</td>"]
        for algo in ALGOS:
            sr = matrix.get(algo, {}).get(task, 0.0)
            warn = ""
            pairs = interference.get(algo, [])
            for ta, tb, delta in pairs:
                if tb == task:
                    warn = f' <span class="warn" title="Interference from {ta}">⚠</span>'
                    break
            bg = _sr_color(sr)
            cells.append(f'<td style="background:{bg};color:#0f172a;font-weight:bold;">'
                         f'{sr*100:.1f}%{warn}</td>')
        table_rows.append("<tr>" + "".join(cells) + "</tr>")
    table_body = "\n".join(table_rows)

    interference_notes = []
    for algo, pairs in interference.items():
        for ta, tb, delta in pairs[:5]:
            interference_notes.append(
                f"<li><b>{algo}</b>: learning <em>{ta.replace('_',' ')}</em> "
                f"may suppress <em>{tb.replace('_',' ')}</em> "
                f"(Δ {delta*100:+.1f}%)</li>"
            )
    interference_html = ("<ul>" + "\n".join(interference_notes) + "</ul>"
                         if interference_notes else "<p>No significant interference detected.</p>")

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<title>Multi-Task Success Tracker</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #1e293b; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif;
         padding: 24px; }}
  h1 {{ color: #C74634; font-size: 1.6rem; margin-bottom: 4px; }}
  h2 {{ color: #C74634; font-size: 1.1rem; margin: 24px 0 10px; border-bottom: 1px solid #334155;
        padding-bottom: 6px; }}
  .subtitle {{ color: #64748b; font-size: 0.85rem; margin-bottom: 20px; }}
  .kpi-row {{ display: flex; gap: 16px; margin-bottom: 24px; flex-wrap: wrap; }}
  .kpi-card {{ background: #0f172a; border: 1px solid #334155; border-radius: 10px;
               padding: 16px 24px; flex: 1; min-width: 160px; }}
  .kpi-label {{ color: #64748b; font-size: 0.75rem; text-transform: uppercase;
                letter-spacing: 0.08em; margin-bottom: 4px; }}
  .kpi-value {{ color: #f1f5f9; font-size: 1.4rem; font-weight: 700; }}
  .kpi-sub {{ color: #94a3b8; font-size: 0.8rem; margin-top: 4px; }}
  .section {{ background: #0f172a; border: 1px solid #334155; border-radius: 10px;
              padding: 20px; margin-bottom: 20px; overflow-x: auto; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.85rem; }}
  th {{ background: #1e293b; color: #94a3b8; padding: 8px 12px; text-align: center;
        border: 1px solid #334155; }}
  td {{ padding: 7px 12px; border: 1px solid #334155; text-align: center; }}
  td:first-child {{ text-align: left; color: #cbd5e1; font-weight: 500; }}
  .warn {{ color: #fbbf24; cursor: help; }}
  ul {{ padding-left: 20px; }}
  li {{ margin: 6px 0; color: #94a3b8; font-size: 0.85rem; }}
  em {{ color: #60a5fa; font-style: normal; }}
  b {{ color: #f1f5f9; }}
  p {{ color: #94a3b8; font-size: 0.85rem; }}
</style>
</head>
<body>
<h1>Multi-Task Success Tracker</h1>
<div class="subtitle">Generated {now} &mdash; {len(TASKS)} tasks &times; {len(ALGOS)} algorithms &times; 200 episodes</div>

{kpi_html}

<h2>Success Rate Heatmap (Task &times; Algorithm)</h2>
<div class="section">
{heatmap_svg}
</div>

<h2>Learning Curves &mdash; DAgger+Curr (all tasks)</h2>
<div class="section">
{linechart_svg}
</div>

<h2>Task &times; Algorithm SR Matrix</h2>
<div class="section">
<table>
  <thead><tr><th>Task</th>{header_cells}</tr></thead>
  <tbody>{table_body}</tbody>
</table>
</div>

<h2>Cross-Task Interference Warnings</h2>
<div class="section">
{interference_html}
</div>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Multi-task robotic success rate tracker")
    parser.add_argument("--mock", action="store_true", default=True,
                        help="Generate mock training data (default: True)")
    parser.add_argument("--output", default="/tmp/multi_task_success_tracker.html",
                        help="Output HTML file path")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    args = parser.parse_args()

    print(f"[tracker] Simulating training runs (seed={args.seed}) ...")
    all_runs: List[TrainingRun] = []
    for algo in ALGOS:
        runs = simulate_training(algo, TASKS, n_episodes=200, seed=args.seed)
        all_runs.extend(runs)
        print(f"  {algo}: {len(runs)} runs")

    print("[tracker] Computing task matrix ...")
    matrix = compute_task_matrix(all_runs)

    print("[tracker] Detecting cross-task interference ...")
    interference = detect_interference(matrix)
    for algo, pairs in interference.items():
        print(f"  {algo}: {len(pairs)} interference pair(s)")

    print("[tracker] Building episode SR curves for DAgger+Curr ...")
    curves = compute_episode_sr_curve(all_runs, "DAgger+Curr")

    print("[tracker] Rendering HTML report ...")
    html = build_html_report(matrix, interference, curves)

    with open(args.output, "w") as f:
        f.write(html)
    print(f"[tracker] Report saved → {args.output}")


if __name__ == "__main__":
    main()
