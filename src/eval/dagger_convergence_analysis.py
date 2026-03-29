"""
DAgger Convergence Analysis
============================
Reads multiple eval output directories (one per DAgger iteration) and produces
a self-contained HTML report showing success rate progression, expert intervention
decline, and latency trends.

Usage:
    # With real eval dirs:
    python src/eval/dagger_convergence_analysis.py \\
        --runs /tmp/eval_bc /tmp/eval_dag1 /tmp/eval_dag2 /tmp/eval_dag3 \\
        --labels "BC" "DAgger-1" "DAgger-2" "DAgger-3" \\
        --dagger-stats /tmp/dagger_stats.json \\
        --output /tmp/convergence_report.html

    # Mock mode (no data required):
    python src/eval/dagger_convergence_analysis.py --mock
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

# ── Defaults ──────────────────────────────────────────────────────────────────
DEFAULT_OUTPUT = "/tmp/convergence_report.html"

# Mock data matching documented run progression
MOCK_SUMMARIES = [
    {
        "label": "BC (baseline)",
        "success_rate": 0.05,
        "num_episodes": 20,
        "avg_latency_ms": 231.0,
        "failure_categories": {
            "success": 1, "partial": 2, "no_contact": 12, "knocked_off": 5
        },
    },
    {
        "label": "DAgger-1",
        "success_rate": 0.52,
        "num_episodes": 20,
        "avg_latency_ms": 228.5,
        "failure_categories": {
            "success": 10, "partial": 3, "no_contact": 4, "knocked_off": 3
        },
    },
    {
        "label": "DAgger-2",
        "success_rate": 0.55,
        "num_episodes": 20,
        "avg_latency_ms": 226.1,
        "failure_categories": {
            "success": 11, "partial": 4, "no_contact": 3, "knocked_off": 2
        },
    },
    {
        "label": "DAgger-3",
        "success_rate": 0.65,
        "num_episodes": 20,
        "avg_latency_ms": 223.4,
        "failure_categories": {
            "success": 13, "partial": 2, "no_contact": 3, "knocked_off": 2
        },
    },
]

MOCK_DAGGER_STATS = {
    "0": {"beta": 1.0,  "expert_interventions_per_ep": 0.0},   # BC — no mixing
    "1": {"beta": 0.9,  "expert_interventions_per_ep": 22.8},
    "2": {"beta": 0.5,  "expert_interventions_per_ep": 17.4},
    "3": {"beta": 0.2,  "expert_interventions_per_ep": 10.9},
}


# ── Data loading ──────────────────────────────────────────────────────────────

def load_summary(run_dir: Path) -> dict | None:
    """Load summary.json from *run_dir*. Returns None on any error."""
    path = run_dir / "summary.json"
    if not path.exists():
        print(f"  [WARN] summary.json not found in {run_dir}", file=sys.stderr)
        return None
    try:
        with path.open() as f:
            return json.load(f)
    except json.JSONDecodeError as exc:
        print(f"  [WARN] Could not parse {path}: {exc}", file=sys.stderr)
        return None


def load_dagger_stats(json_path: Path) -> dict:
    """Load optional DAgger iteration statistics JSON."""
    if not json_path.exists():
        print(f"  [WARN] dagger-stats file not found: {json_path}", file=sys.stderr)
        return {}
    with json_path.open() as f:
        return json.load(f)


# ── HTML building blocks ──────────────────────────────────────────────────────

CSS = """
:root {
    --bg: #1C1C1E;
    --card: #2C2C2E;
    --border: #3A3A3C;
    --text: #F5F5F7;
    --muted: #8E8E93;
    --accent: #C74634;
    --green: #30D158;
    --yellow: #FFD60A;
    --blue: #0A84FF;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
    background: var(--bg);
    color: var(--text);
    font-family: -apple-system, 'SF Pro Display', 'Helvetica Neue', Arial, sans-serif;
    font-size: 15px;
    line-height: 1.6;
    padding: 40px 20px 60px;
}
h1 {
    font-size: 28px;
    font-weight: 700;
    color: var(--accent);
    margin-bottom: 6px;
}
h2 {
    font-size: 18px;
    font-weight: 600;
    color: var(--text);
    margin: 32px 0 14px;
    border-left: 3px solid var(--accent);
    padding-left: 10px;
}
.subtitle { color: var(--muted); font-size: 14px; margin-bottom: 32px; }
.card {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 24px;
    margin-bottom: 24px;
}
/* Bar chart */
.chart-wrap { display: flex; flex-direction: column; gap: 10px; }
.bar-row { display: flex; align-items: center; gap: 12px; }
.bar-label { width: 110px; font-size: 13px; color: var(--muted); text-align: right; flex-shrink: 0; }
.bar-track {
    flex: 1;
    background: #3A3A3C;
    border-radius: 4px;
    height: 28px;
    position: relative;
    overflow: hidden;
}
.bar-fill {
    height: 100%;
    background: var(--accent);
    border-radius: 4px;
    transition: width 0.4s ease;
    display: flex;
    align-items: center;
    padding-left: 8px;
}
.bar-fill.best { background: var(--green); }
.bar-pct { font-size: 13px; font-weight: 600; color: #fff; white-space: nowrap; }
.bar-pct-out { font-size: 13px; font-weight: 600; color: var(--text); padding-left: 8px; }
/* Intervention mini-table */
.itv-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.itv-table th {
    text-align: left;
    padding: 8px 12px;
    background: #3A3A3C;
    color: var(--muted);
    font-weight: 500;
}
.itv-table td { padding: 8px 12px; border-bottom: 1px solid var(--border); }
.itv-table tr:last-child td { border-bottom: none; }
.cell-heat-high  { background: rgba(199,70,52,0.30); border-radius: 4px; }
.cell-heat-mid   { background: rgba(255,214,10,0.20); border-radius: 4px; }
.cell-heat-low   { background: rgba(48,209,88,0.25); border-radius: 4px; }
.cell-heat-none  { background: transparent; color: var(--muted); }
/* Full data table */
.data-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.data-table th {
    text-align: left;
    padding: 10px 12px;
    background: #3A3A3C;
    color: var(--muted);
    font-weight: 500;
    white-space: nowrap;
}
.data-table td { padding: 10px 12px; border-bottom: 1px solid var(--border); vertical-align: top; }
.data-table tr:last-child td { border-bottom: none; }
.data-table tr:hover td { background: rgba(255,255,255,0.04); }
.tag-bc     { color: var(--muted); }
.tag-dag    { color: var(--accent); font-weight: 600; }
.pct-best   { color: var(--green); font-weight: 700; }
.pct-good   { color: var(--yellow); font-weight: 600; }
.pct-poor   { color: var(--accent); }
/* Trend box */
.trend-box {
    background: rgba(199,70,52,0.12);
    border: 1px solid rgba(199,70,52,0.4);
    border-radius: 8px;
    padding: 18px 22px;
}
.trend-box .big { font-size: 36px; font-weight: 700; color: var(--green); }
.trend-box .desc { color: var(--muted); font-size: 14px; margin-top: 4px; }
footer {
    margin-top: 48px;
    color: var(--muted);
    font-size: 12px;
    text-align: center;
}
"""


def _pct_class(pct: float, best_pct: float) -> str:
    if pct >= best_pct:
        return "pct-best"
    if pct >= best_pct * 0.7:
        return "pct-good"
    return "pct-poor"


def _intervention_heat(val: float | None, max_val: float) -> str:
    if val is None:
        return "cell-heat-none"
    ratio = val / max_val if max_val > 0 else 0
    if ratio > 0.6:
        return "cell-heat-high"
    if ratio > 0.3:
        return "cell-heat-mid"
    return "cell-heat-low"


def build_bar_chart(rows: list[dict]) -> str:
    best_pct = max(r["success_rate"] * 100 for r in rows)
    html = ['<div class="chart-wrap">']
    for r in rows:
        pct = r["success_rate"] * 100
        bar_pct_css = min(pct, 100)
        is_best = (pct >= best_pct)
        fill_cls = "bar-fill best" if is_best else "bar-fill"
        # Show percentage inside bar if >= 12%, else outside
        if bar_pct_css >= 12:
            inner = f'<span class="bar-pct">{pct:.1f}%</span>'
            outer = ""
        else:
            inner = ""
            outer = f'<span class="bar-pct-out">{pct:.1f}%</span>'
        html.append(
            f'<div class="bar-row">'
            f'  <span class="bar-label">{r["label"]}</span>'
            f'  <div class="bar-track">'
            f'    <div class="{fill_cls}" style="width:{bar_pct_css:.1f}%">{inner}</div>'
            f'  </div>'
            f'  {outer}'
            f'</div>'
        )
    html.append("</div>")
    return "\n".join(html)


def build_intervention_table(rows: list[dict], dagger_stats: dict) -> str:
    if not dagger_stats:
        return "<p style='color:var(--muted);font-size:13px;'>No DAgger stats provided.</p>"

    # Find max interventions for heat scaling
    vals = [
        v.get("expert_interventions_per_ep")
        for v in dagger_stats.values()
        if v.get("expert_interventions_per_ep") is not None
    ]
    max_val = max(vals) if vals else 1.0

    html = ['<table class="itv-table"><thead><tr>']
    html.append(
        "<th>Iteration</th><th>Label</th><th>Beta (β)</th>"
        "<th>Expert Interventions / Ep</th><th>Trend</th>"
    )
    html.append("</tr></thead><tbody>")

    for i, row in enumerate(rows):
        stat = dagger_stats.get(str(i), {})
        beta  = stat.get("beta")
        itv   = stat.get("expert_interventions_per_ep")
        heat  = _intervention_heat(itv, max_val)
        beta_str = f"{beta:.2f}" if beta is not None else "—"
        itv_str  = f"{itv:.1f}" if itv is not None else "—"
        # Trend arrow vs previous
        if i == 0:
            trend = "—"
        else:
            prev_stat = dagger_stats.get(str(i - 1), {})
            prev_itv  = prev_stat.get("expert_interventions_per_ep")
            if itv is not None and prev_itv is not None:
                delta = itv - prev_itv
                if delta < 0:
                    trend = f"<span style='color:var(--green)'>↓ {abs(delta):.1f}</span>"
                elif delta > 0:
                    trend = f"<span style='color:var(--accent)'>↑ {delta:.1f}</span>"
                else:
                    trend = "→ 0.0"
            else:
                trend = "—"
        html.append(
            f"<tr>"
            f"<td>{i}</td>"
            f"<td>{row['label']}</td>"
            f"<td>{beta_str}</td>"
            f"<td class='{heat}'>{itv_str}</td>"
            f"<td>{trend}</td>"
            f"</tr>"
        )
    html.append("</tbody></table>")
    return "\n".join(html)


def build_data_table(rows: list[dict], dagger_stats: dict) -> str:
    best_pct = max(r["success_rate"] * 100 for r in rows)

    html = ['<table class="data-table"><thead><tr>']
    html.append(
        "<th>Iter</th><th>Label</th><th>Beta</th><th>Episodes</th>"
        "<th>Success %</th><th>Avg Latency</th><th>Expert ITV/ep</th>"
        "<th>Failure breakdown</th>"
    )
    html.append("</tr></thead><tbody>")

    for i, row in enumerate(rows):
        pct       = row["success_rate"] * 100
        pct_cls   = _pct_class(pct, best_pct)
        stat      = dagger_stats.get(str(i), {})
        beta      = stat.get("beta")
        itv       = stat.get("expert_interventions_per_ep")
        beta_str  = f"{beta:.2f}" if beta is not None else "—"
        itv_str   = f"{itv:.1f}" if itv is not None else "—"
        cats: dict = row.get("failure_categories", {})
        cats_str  = " | ".join(f"{k}: {v}" for k, v in cats.items()) if cats else "—"
        lbl_cls   = "tag-bc" if i == 0 else "tag-dag"
        html.append(
            f"<tr>"
            f"<td>{i}</td>"
            f"<td class='{lbl_cls}'>{row['label']}</td>"
            f"<td>{beta_str}</td>"
            f"<td>{row['num_episodes']}</td>"
            f"<td class='{pct_cls}'>{pct:.1f}%</td>"
            f"<td>{row['avg_latency_ms']:.1f} ms</td>"
            f"<td>{itv_str}</td>"
            f"<td style='color:var(--muted);font-size:12px'>{cats_str}</td>"
            f"</tr>"
        )
    html.append("</tbody></table>")
    return "\n".join(html)


def build_trend_summary(rows: list[dict]) -> str:
    bc_pct   = rows[0]["success_rate"] * 100
    best_pct = max(r["success_rate"] * 100 for r in rows)
    best_lbl = next(r["label"] for r in rows if r["success_rate"] * 100 >= best_pct)
    n_iters  = len(rows) - 1  # exclude BC

    if bc_pct > 0:
        improvement = best_pct / bc_pct
        imp_str = f"{improvement:.1f}×"
    else:
        imp_str = "∞"

    return f"""
<div class="trend-box">
  <div class="big">{imp_str}</div>
  <div class="desc">
    Success rate improved {imp_str} from BC baseline ({bc_pct:.1f}%)
    to {best_lbl} ({best_pct:.1f}%) over {n_iters} DAgger iteration(s).
  </div>
</div>
"""


def build_html(rows: list[dict], dagger_stats: dict, mock: bool) -> str:
    gen_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    mock_note = (
        '<span style="color:var(--yellow);font-size:12px"> ⚠ Mock data</span>'
        if mock else ""
    )

    bar_chart   = build_bar_chart(rows)
    itv_table   = build_intervention_table(rows, dagger_stats)
    data_table  = build_data_table(rows, dagger_stats)
    trend_html  = build_trend_summary(rows)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>DAgger Convergence Analysis</title>
  <style>{CSS}</style>
</head>
<body>
  <h1>DAgger Convergence Analysis{mock_note}</h1>
  <p class="subtitle">
    OCI Robot Cloud — GR00T N1.6 fine-tuning with iterative DAgger online training
  </p>

  <div class="card">
    <h2>Chart 1 — Success Rate by Iteration</h2>
    {bar_chart}
  </div>

  <div class="card">
    <h2>Chart 2 — Expert Intervention Decline</h2>
    <p style="color:var(--muted);font-size:13px;margin-bottom:14px">
      Lower expert interventions per episode = policy is becoming more autonomous.
    </p>
    {itv_table}
  </div>

  <div class="card">
    <h2>All Iterations — Full Data</h2>
    {data_table}
  </div>

  <div class="card">
    <h2>Trend Summary</h2>
    {trend_html}
  </div>

  <footer>
    Generated: {gen_time} &nbsp;|&nbsp; OCI Robot Cloud
    &nbsp;|&nbsp; <em>oracle.com/cloud/robotics</em>
  </footer>
</body>
</html>
"""


# ── Argument parsing ──────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="DAgger convergence analysis — generates self-contained HTML report"
    )
    p.add_argument(
        "--runs",
        nargs="+",
        metavar="DIR",
        default=[],
        help="Eval output directories, one per iteration (BC first)",
    )
    p.add_argument(
        "--labels",
        nargs="+",
        metavar="LABEL",
        default=[],
        help="Human-readable labels matching --runs (e.g. 'BC' 'DAgger-1' …)",
    )
    p.add_argument(
        "--dagger-stats",
        metavar="JSON",
        default=None,
        help=(
            "Optional JSON file with DAgger iteration stats. "
            "Format: {iter_index_str: {beta, expert_interventions_per_ep}}"
        ),
    )
    p.add_argument(
        "--output",
        default=DEFAULT_OUTPUT,
        help=f"Output HTML path (default: {DEFAULT_OUTPUT})",
    )
    p.add_argument(
        "--mock",
        action="store_true",
        help="Generate report using built-in mock data (no real eval dirs needed)",
    )
    return p.parse_args()


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    args = parse_args()

    if args.mock:
        print("Mock mode — using built-in sample data.")
        rows        = MOCK_SUMMARIES
        dagger_stats = MOCK_DAGGER_STATS
    else:
        if not args.runs:
            print(
                "Error: provide --runs or use --mock to generate sample data.",
                file=sys.stderr,
            )
            sys.exit(1)

        # Build label list — pad with "Iter-N" if fewer labels than runs
        labels = list(args.labels)
        for i in range(len(labels), len(args.runs)):
            labels.append(f"Iter-{i}" if i > 0 else "BC")

        rows = []
        for run_dir_str, label in zip(args.runs, labels):
            run_dir = Path(run_dir_str)
            summary = load_summary(run_dir)
            if summary is None:
                # Insert placeholder so indices remain aligned
                summary = {
                    "success_rate": 0.0,
                    "num_episodes": 0,
                    "avg_latency_ms": 0.0,
                    "failure_categories": {},
                }
            summary["label"] = label
            rows.append(summary)

        dagger_stats: dict = {}
        if args.dagger_stats:
            dagger_stats = load_dagger_stats(Path(args.dagger_stats))

    if not rows:
        print("No data to report.", file=sys.stderr)
        sys.exit(1)

    # Build + write HTML
    html = build_html(rows, dagger_stats, mock=args.mock)
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")

    # Stdout summary
    print(f"\nDAgger Convergence Analysis")
    print(f"{'─' * 44}")
    best_pct = max(r["success_rate"] * 100 for r in rows)
    bc_pct   = rows[0]["success_rate"] * 100
    for i, r in enumerate(rows):
        pct = r["success_rate"] * 100
        marker = " ◀ best" if pct >= best_pct else ""
        print(f"  {r['label']:<14} {pct:5.1f}%{marker}")
    print(f"{'─' * 44}")
    if bc_pct > 0:
        print(f"  Improvement: {best_pct / bc_pct:.1f}× vs BC baseline")
    else:
        print(f"  BC baseline is 0% — improvement is unbounded")
    print(f"\nReport written to: {out_path.resolve()}")
    print()


if __name__ == "__main__":
    main()
