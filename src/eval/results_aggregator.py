#!/usr/bin/env python3
"""
results_aggregator.py — Aggregate eval results across runs into a progress report.

Reads multiple closed_loop_eval JSON outputs and optionally DAgger results,
then generates a single HTML dashboard showing improvement over time.

Usage:
    python src/eval/results_aggregator.py \
        --results /tmp/eval_500demo /tmp/eval_1000demo /tmp/eval_dagger_final \
        --labels "500-demo BC" "1000-demo BC" "DAgger iter3" \
        --dagger-log /tmp/dagger_run4/dagger_results.json \
        --output /tmp/progress_dashboard.html

Auto-discover mode (scans a directory tree):
    python src/eval/results_aggregator.py --scan /tmp --output /tmp/progress.html
"""

import argparse
import json
from datetime import datetime
from pathlib import Path

import numpy as np


# ── Loaders ───────────────────────────────────────────────────────────────────

def load_eval_dir(path: Path) -> dict | None:
    """Load summary.json or infer from episodes.json in a closed_loop_eval output dir."""
    p = Path(path)
    # Try summary.json first
    for fname in ["summary.json", "eval_summary.json", "results.json"]:
        f = p / fname
        if f.exists():
            data = json.loads(f.read_text())
            return data

    # Try scanning for episode result files
    ep_files = sorted(p.glob("episode_*.json"))
    if ep_files:
        episodes = [json.loads(f.read_text()) for f in ep_files]
        n = len(episodes)
        n_success = sum(1 for e in episodes if e.get("success", False))
        return {
            "n_episodes": n,
            "n_success": n_success,
            "success_rate": n_success / n if n > 0 else 0,
            "episodes": episodes,
        }
    return None


def scan_eval_dirs(root: Path) -> list[tuple[str, dict]]:
    """Scan a directory tree for closed_loop_eval output directories."""
    results = []
    for d in sorted(root.rglob("summary.json")):
        data = load_eval_dir(d.parent)
        if data:
            results.append((str(d.parent.name), data))
    return results


# ── HTML ──────────────────────────────────────────────────────────────────────

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Training Progress Dashboard — OCI Robot Cloud</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{ font-family: 'Segoe UI', system-ui, sans-serif; background: #0f172a; color: #e2e8f0;
         margin: 0; padding: 24px 32px; }}
  h1 {{ color: #C74634; font-size: 1.8em; margin-bottom: 4px; }}
  .subtitle {{ color: #64748b; margin-bottom: 32px; font-size: 0.9em; }}
  .grid-4 {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 32px; }}
  .stat-card {{ background: #1e293b; border-radius: 10px; padding: 18px; text-align: center; }}
  .stat-card .val {{ font-size: 2.5em; font-weight: bold; color: #f8fafc; margin: 6px 0; }}
  .stat-card .val.green {{ color: #10b981; }}
  .stat-card .val.amber {{ color: #f59e0b; }}
  .stat-card .val.red {{ color: #ef4444; }}
  .stat-card .lbl {{ color: #94a3b8; font-size: 0.8em; text-transform: uppercase;
                     letter-spacing: 0.06em; }}
  .section {{ margin-bottom: 32px; }}
  h2 {{ color: #94a3b8; text-transform: uppercase; letter-spacing: 0.08em;
        font-size: 0.75em; margin-bottom: 14px; border-bottom: 1px solid #1e293b;
        padding-bottom: 6px; }}
  /* Bar chart */
  .chart {{ display: flex; align-items: flex-end; gap: 10px; height: 160px; padding: 0 8px; }}
  .bar-wrap {{ flex: 1; display: flex; flex-direction: column; align-items: center; gap: 4px; }}
  .bar {{ width: 100%; border-radius: 6px 6px 0 0; min-height: 4px;
          transition: height 0.3s; position: relative; }}
  .bar-val {{ font-size: 0.85em; font-weight: bold; color: #f8fafc; }}
  .bar-lbl {{ font-size: 0.7em; color: #64748b; text-align: center;
              max-width: 80px; word-wrap: break-word; }}
  /* Table */
  table {{ width: 100%; border-collapse: collapse; }}
  th {{ background: #C74634; color: white; padding: 10px 14px; text-align: left;
        font-size: 0.85em; }}
  td {{ padding: 9px 14px; border-bottom: 1px solid #1e293b; font-size: 0.9em; }}
  tr:nth-child(even) td {{ background: #172033; }}
  .pill {{ display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: 0.78em;
           font-weight: 600; }}
  .pill.green {{ background: #064e3b; color: #6ee7b7; }}
  .pill.amber {{ background: #451a03; color: #fcd34d; }}
  .pill.red {{ background: #450a0a; color: #fca5a5; }}
  /* DAgger table */
  .dagger-grid {{ display: grid; grid-template-columns: repeat(5, 1fr); gap: 8px; }}
  .dagger-card {{ background: #1e293b; border-radius: 8px; padding: 14px; text-align: center; }}
  .dagger-card .iter {{ color: #94a3b8; font-size: 0.75em; margin-bottom: 6px; }}
  .dagger-card .beta {{ font-size: 1.4em; font-weight: bold; color: #f8fafc; }}
  .dagger-card .sub {{ color: #64748b; font-size: 0.75em; margin-top: 4px; }}
  .arrow {{ color: #C74634; font-size: 1.2em; align-self: center; }}
  .meta {{ color: #475569; font-size: 0.8em; margin-top: 32px; }}
</style>
</head>
<body>
<h1>Training Progress Dashboard</h1>
<p class="subtitle">OCI Robot Cloud · GR00T N1.6-3B · Franka pick-and-lift · Generated {timestamp}</p>

<!-- Summary KPIs -->
<div class="grid-4">
  <div class="stat-card">
    <div class="lbl">Best success rate</div>
    <div class="val {best_cls}">{best_rate:.0%}</div>
    <div class="lbl">{best_label}</div>
  </div>
  <div class="stat-card">
    <div class="lbl">Improvement over BC</div>
    <div class="val green">+{improvement:.0f}pp</div>
    <div class="lbl">percentage points</div>
  </div>
  <div class="stat-card">
    <div class="lbl">Total runs evaluated</div>
    <div class="val">{n_runs}</div>
    <div class="lbl">checkpoints</div>
  </div>
  <div class="stat-card">
    <div class="lbl">Total episodes</div>
    <div class="val">{total_eps}</div>
    <div class="lbl">closed-loop rollouts</div>
  </div>
</div>

<!-- Bar chart -->
<div class="section">
<h2>Success Rate by Checkpoint</h2>
<div class="chart">
{bars}
</div>
</div>

<!-- Runs table -->
<div class="section">
<h2>All Runs</h2>
<table>
  <tr><th>#</th><th>Label</th><th>Episodes</th><th>Successes</th>
      <th>Success Rate</th><th>Avg max cube z</th><th>Status</th></tr>
  {table_rows}
</table>
</div>

{dagger_section}

<p class="meta">OCI Robot Cloud · github.com/qianjun22/roboticsai · {timestamp}</p>
</body>
</html>
"""

DAGGER_SECTION_TEMPLATE = """
<div class="section">
<h2>DAgger Iteration Progress</h2>
<div class="dagger-grid">
{dagger_cards}
</div>
</div>
"""

DAGGER_CARD = """
<div class="dagger-card">
  <div class="iter">Iter {iter}</div>
  <div class="beta">&beta; = {beta:.2f}</div>
  <div class="sub">Success: {rate:.0%}</div>
  <div class="sub">Expert: {interventions:.1f}/ep</div>
</div>
"""

BAR_COLORS = ["#C74634", "#3b82f6", "#10b981", "#f59e0b", "#8b5cf6",
              "#06b6d4", "#ec4899", "#84cc16"]


def rate_pill(rate: float) -> str:
    if rate >= 0.5:
        cls = "green"
    elif rate >= 0.1:
        cls = "amber"
    else:
        cls = "red"
    return f'<span class="pill {cls}">{rate:.0%}</span>'


def make_html(labels: list, summaries: list, dagger_data: dict | None) -> str:
    rates = [s.get("success_rate", s.get("n_success", 0) / max(s.get("n_episodes", 1), 1))
             for s in summaries]
    n_eps = [s.get("n_episodes", s.get("total_episodes", 20)) for s in summaries]
    n_success = [s.get("n_success", int(r * n)) for r, n in zip(rates, n_eps)]
    avg_z = []
    for s in summaries:
        eps = s.get("episodes", [])
        if eps and "max_cube_z" in eps[0]:
            avg_z.append(np.mean([e["max_cube_z"] for e in eps]))
        else:
            avg_z.append(float("nan"))

    best_idx = int(np.argmax(rates))
    best_rate = rates[best_idx]
    best_label = labels[best_idx]
    bc_rate = rates[0] if rates else 0
    improvement = (best_rate - bc_rate) * 100
    n_runs = len(labels)
    total_eps = sum(n_eps)

    best_cls = "green" if best_rate >= 0.5 else ("amber" if best_rate >= 0.1 else "red")

    # Bars
    max_rate = max(rates) if rates else 1.0
    bars = []
    for i, (label, rate) in enumerate(zip(labels, rates)):
        h = max(8, int(120 * rate / max(max_rate, 0.01)))
        color = BAR_COLORS[i % len(BAR_COLORS)]
        bars.append(
            f'<div class="bar-wrap">'
            f'<div class="bar-val">{rate:.0%}</div>'
            f'<div class="bar" style="height:{h}px; background:{color};"></div>'
            f'<div class="bar-lbl">{label}</div>'
            f'</div>'
        )

    # Table rows
    table_rows = []
    for i, (label, rate, ns, ne, z) in enumerate(zip(labels, rates, n_success, n_eps, avg_z)):
        z_str = f"{z:.3f}m" if not np.isnan(z) else "—"
        table_rows.append(
            f"<tr><td>{i+1}</td><td><b>{label}</b></td><td>{ne}</td><td>{ns}</td>"
            f"<td>{rate_pill(rate)}</td><td>{z_str}</td>"
            f"<td>{'Best' if i == best_idx else ''}</td></tr>"
        )

    # DAgger section
    dagger_section = ""
    if dagger_data and "results" in dagger_data:
        cards = []
        for entry in dagger_data["results"]:
            cards.append(DAGGER_CARD.format(
                iter=entry.get("iter", "?"),
                beta=entry.get("beta", 0),
                rate=entry.get("success_rate", 0),
                interventions=entry.get("avg_diverged_steps", 0),
            ))
        dagger_section = DAGGER_SECTION_TEMPLATE.format(dagger_cards="\n".join(cards))

    return HTML_TEMPLATE.format(
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M"),
        best_rate=best_rate,
        best_cls=best_cls,
        best_label=best_label,
        improvement=max(0, improvement),
        n_runs=n_runs,
        total_eps=total_eps,
        bars="\n".join(bars),
        table_rows="\n".join(table_rows),
        dagger_section=dagger_section,
    )


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Aggregate eval results into progress dashboard")
    parser.add_argument("--results", nargs="+", help="Eval output directories in order")
    parser.add_argument("--labels", nargs="+", help="Labels for each eval dir")
    parser.add_argument("--dagger-log", help="Path to dagger_results.json")
    parser.add_argument("--scan", help="Auto-scan this directory for eval outputs")
    parser.add_argument("--output", default="/tmp/progress_dashboard.html")
    args = parser.parse_args()

    labels = []
    summaries = []

    if args.scan:
        found = scan_eval_dirs(Path(args.scan))
        labels = [label for label, _ in found]
        summaries = [data for _, data in found]
        print(f"[aggregator] Found {len(found)} eval directories in {args.scan}")
    elif args.results:
        labels = args.labels or [Path(r).name for r in args.results]
        if len(labels) < len(args.results):
            labels += [Path(r).name for r in args.results[len(labels):]]
        for r_path in args.results:
            data = load_eval_dir(Path(r_path))
            if data is None:
                print(f"[aggregator] WARNING: no eval data found in {r_path}")
                data = {"n_episodes": 0, "n_success": 0, "success_rate": 0.0}
            summaries.append(data)
    else:
        parser.error("Provide either --results or --scan")

    dagger_data = None
    if args.dagger_log and Path(args.dagger_log).exists():
        raw = json.loads(Path(args.dagger_log).read_text())
        # Support both {"results": [...]} and plain list
        if isinstance(raw, list):
            dagger_data = {"results": raw}
        else:
            dagger_data = raw

    html = make_html(labels, summaries, dagger_data)
    Path(args.output).write_text(html)
    print(f"[aggregator] Dashboard saved: {args.output}")

    # Print summary table to stdout
    print(f"\n{'Label':<30} {'Success':>8} {'Rate':>8}")
    print("-" * 50)
    for label, s in zip(labels, summaries):
        rate = s.get("success_rate", s.get("n_success", 0) / max(s.get("n_episodes", 1), 1))
        ns = s.get("n_success", int(rate * s.get("n_episodes", 20)))
        n = s.get("n_episodes", 20)
        print(f"{label:<30} {ns:>4}/{n:<3} {rate:>7.0%}")


if __name__ == "__main__":
    main()
