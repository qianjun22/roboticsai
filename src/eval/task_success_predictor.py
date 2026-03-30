"""
Early trajectory success prediction for GR00T episodes.
Forecasts task completion at 20% of episode to enable early termination.
"""

import argparse
import math
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Tuple


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class PredictionSample:
    episode_id: str
    task_name: str
    policy_name: str
    true_success: bool
    predicted_prob: float
    predicted_at_frame: int
    total_frames: int
    confidence: float


@dataclass
class PredictorResult:
    policy_name: str
    n_episodes: int
    auc_roc: float
    precision: float
    recall: float
    f1: float
    early_term_savings_pct: float
    false_positive_rate: float


@dataclass
class PredictorReport:
    best_policy: str
    best_auc: float
    avg_early_savings_pct: float
    results: List[PredictorResult] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Policy meta-parameters
# ---------------------------------------------------------------------------

POLICY_PARAMS = {
    "bc_baseline": {
        "success_rate": 0.25,
        "auc_roc": 0.71,
        "precision": 0.67,
        "recall": 0.72,
        "f1": 0.694,
        "early_term_savings_pct": 22.0,
        "fpr": 0.33,
    },
    "dagger_run5": {
        "success_rate": 0.40,
        "auc_roc": 0.80,
        "precision": 0.76,
        "recall": 0.77,
        "f1": 0.765,
        "early_term_savings_pct": 29.0,
        "fpr": 0.24,
    },
    "dagger_run9": {
        "success_rate": 0.60,
        "auc_roc": 0.89,
        "precision": 0.84,
        "recall": 0.81,
        "f1": 0.824,
        "early_term_savings_pct": 38.0,
        "fpr": 0.14,
    },
    "dagger_run9_lora": {
        "success_rate": 0.65,
        "auc_roc": 0.87,
        "precision": 0.82,
        "recall": 0.83,
        "f1": 0.825,
        "early_term_savings_pct": 35.0,
        "fpr": 0.17,
    },
}

TASKS = ["PickCube-v1", "StackCube-v1", "TurnFaucet-v0", "OpenDrawer-v1"]
N_EPISODES = 100
TOTAL_FRAMES = 50
PREDICT_AT_FRAME = 10  # 20% of trajectory


# ---------------------------------------------------------------------------
# Simulation helpers
# ---------------------------------------------------------------------------

def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def simulate_episode_samples(policy_name: str, seed: int) -> List[PredictionSample]:
    """Generate mock PredictionSample objects for a policy."""
    rng = random.Random(seed)
    params = POLICY_PARAMS[policy_name]
    samples: List[PredictionSample] = []

    for i in range(N_EPISODES):
        task = TASKS[i % len(TASKS)]
        true_success = rng.random() < params["success_rate"]

        # Predicted probability: correlated with true outcome, scaled by AUC quality
        # Better AUC → tighter clustering around correct value
        auc_noise_scale = 1.5 * (1.0 - params["auc_roc"])  # lower AUC → more noise
        if true_success:
            raw = rng.gauss(1.2, auc_noise_scale)
        else:
            raw = rng.gauss(-1.2, auc_noise_scale)

        predicted_prob = max(0.01, min(0.99, _sigmoid(raw)))
        # Confidence = how far the probability is from 0.5
        confidence = abs(predicted_prob - 0.5) * 2.0

        samples.append(PredictionSample(
            episode_id=f"{policy_name}_ep{i:04d}",
            task_name=task,
            policy_name=policy_name,
            true_success=true_success,
            predicted_prob=round(predicted_prob, 4),
            predicted_at_frame=PREDICT_AT_FRAME,
            total_frames=TOTAL_FRAMES,
            confidence=round(confidence, 4),
        ))

    return samples


def compute_roc_points(samples: List[PredictionSample]) -> List[Tuple[float, float]]:
    """Return list of (FPR, TPR) pairs at 10 evenly-spaced thresholds."""
    thresholds = [t / 10.0 for t in range(1, 10)]  # 0.1 … 0.9
    # Add endpoints for a complete curve
    thresholds = [0.0] + thresholds + [1.0]
    points: List[Tuple[float, float]] = []

    pos = [s for s in samples if s.true_success]
    neg = [s for s in samples if not s.true_success]
    n_pos = max(1, len(pos))
    n_neg = max(1, len(neg))

    for thr in thresholds:
        tp = sum(1 for s in pos if s.predicted_prob >= thr)
        fp = sum(1 for s in neg if s.predicted_prob >= thr)
        tpr = tp / n_pos
        fpr = fp / n_neg
        points.append((round(fpr, 4), round(tpr, 4)))

    return points


def compute_pr_points(samples: List[PredictionSample]) -> List[Tuple[float, float]]:
    """Return list of (recall, precision) pairs at thresholds."""
    thresholds = [t / 10.0 for t in range(1, 10)]
    thresholds = [0.0] + thresholds + [1.0]
    points: List[Tuple[float, float]] = []

    pos = [s for s in samples if s.true_success]
    n_pos = max(1, len(pos))

    for thr in thresholds:
        tp = sum(1 for s in samples if s.true_success and s.predicted_prob >= thr)
        fp = sum(1 for s in samples if not s.true_success and s.predicted_prob >= thr)
        predicted_pos = tp + fp
        precision = tp / max(1, predicted_pos)
        recall = tp / n_pos
        points.append((round(recall, 4), round(precision, 4)))

    return points


def build_predictor_result(policy_name: str, samples: List[PredictionSample]) -> PredictorResult:
    params = POLICY_PARAMS[policy_name]
    return PredictorResult(
        policy_name=policy_name,
        n_episodes=len(samples),
        auc_roc=params["auc_roc"],
        precision=params["precision"],
        recall=params["recall"],
        f1=params["f1"],
        early_term_savings_pct=params["early_term_savings_pct"],
        false_positive_rate=params["fpr"],
    )


def build_report(results: List[PredictorResult]) -> PredictorReport:
    best = max(results, key=lambda r: r.auc_roc)
    avg_savings = sum(r.early_term_savings_pct for r in results) / len(results)
    return PredictorReport(
        best_policy=best.policy_name,
        best_auc=best.auc_roc,
        avg_early_savings_pct=round(avg_savings, 1),
        results=results,
    )


# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------

POLICY_COLORS = {
    "bc_baseline": "#94a3b8",
    "dagger_run5": "#60a5fa",
    "dagger_run9": "#C74634",
    "dagger_run9_lora": "#34d399",
}

_W = 420
_H = 300
_PAD = 50


def _svg_axes(title: str, x_label: str, y_label: str) -> str:
    return (
        f'<svg viewBox="0 0 {_W} {_H}" xmlns="http://www.w3.org/2000/svg" '
        f'style="width:100%;max-width:{_W}px;background:#0f172a;border-radius:8px;">\n'
        f'<text x="{_W//2}" y="18" text-anchor="middle" fill="#e2e8f0" '
        f'font-size="12" font-family="monospace">{title}</text>\n'
        f'<text x="{_W//2}" y="{_H-6}" text-anchor="middle" fill="#94a3b8" '
        f'font-size="10" font-family="monospace">{x_label}</text>\n'
        f'<text x="12" y="{_H//2}" text-anchor="middle" fill="#94a3b8" '
        f'font-size="10" font-family="monospace" '
        f'transform="rotate(-90,12,{_H//2})">{y_label}</text>\n'
        # axes lines
        f'<line x1="{_PAD}" y1="{_PAD}" x2="{_PAD}" y2="{_H-_PAD}" '
        f'stroke="#475569" stroke-width="1"/>\n'
        f'<line x1="{_PAD}" y1="{_H-_PAD}" x2="{_W-_PAD//2}" y2="{_H-_PAD}" '
        f'stroke="#475569" stroke-width="1"/>\n'
    )


def _pt(x_val: float, y_val: float) -> str:
    """Convert [0,1] data coords to SVG pixel coords."""
    px = _PAD + x_val * (_W - _PAD - _PAD // 2)
    py = (_H - _PAD) - y_val * (_H - _PAD - _PAD)
    return f"{px:.1f},{py:.1f}"


def _polyline(points: List[Tuple[float, float]], color: str, width: float = 2.0) -> str:
    pts_str = " ".join(_pt(x, y) for x, y in points)
    return (
        f'<polyline points="{pts_str}" fill="none" '
        f'stroke="{color}" stroke-width="{width}" stroke-linejoin="round"/>\n'
    )


def build_roc_svg(roc_data: dict, results: List[PredictorResult]) -> str:
    svg = _svg_axes("ROC Curves — Success Predictor", "False Positive Rate", "True Positive Rate")
    # Random baseline diagonal
    svg += f'<line x1="{_pt(0,0)}" x2="{_pt(1,1)}" stroke="#475569" stroke-width="1" stroke-dasharray="4,4"/>\n'
    # Each policy
    for result in results:
        color = POLICY_COLORS[result.policy_name]
        points = roc_data[result.policy_name]
        svg += _polyline(points, color)

    # Legend
    leg_x = _PAD + 5
    leg_y = _PAD + 5
    for i, result in enumerate(results):
        color = POLICY_COLORS[result.policy_name]
        y = leg_y + i * 16
        svg += (
            f'<line x1="{leg_x}" y1="{y+5}" x2="{leg_x+16}" y2="{y+5}" '
            f'stroke="{color}" stroke-width="2"/>\n'
            f'<text x="{leg_x+20}" y="{y+9}" fill="{color}" '
            f'font-size="9" font-family="monospace">'
            f'{result.policy_name} (AUC {result.auc_roc:.2f})</text>\n'
        )
    svg += "</svg>\n"
    return svg


def build_pr_svg(pr_data: dict, results: List[PredictorResult]) -> str:
    svg = _svg_axes("Precision–Recall Curves", "Recall", "Precision")
    for result in results:
        color = POLICY_COLORS[result.policy_name]
        points = pr_data[result.policy_name]
        svg += _polyline(points, color)

    # Legend
    leg_x = _W - _PAD - 120
    leg_y = _PAD + 5
    for i, result in enumerate(results):
        color = POLICY_COLORS[result.policy_name]
        y = leg_y + i * 16
        svg += (
            f'<line x1="{leg_x}" y1="{y+5}" x2="{leg_x+16}" y2="{y+5}" '
            f'stroke="{color}" stroke-width="2"/>\n'
            f'<text x="{leg_x+20}" y="{y+9}" fill="{color}" '
            f'font-size="9" font-family="monospace">'
            f'{result.policy_name}</text>\n'
        )
    svg += "</svg>\n"
    return svg


# ---------------------------------------------------------------------------
# HTML report
# ---------------------------------------------------------------------------

def build_html_report(
    report: PredictorReport,
    roc_svg: str,
    pr_svg: str,
) -> str:
    results = report.results
    best_f1 = max(r.f1 for r in results)
    best_precision = max(r.precision for r in results)

    # Stat cards
    cards_html = f"""
    <div class="cards">
      <div class="card">
        <div class="card-value">{report.best_auc:.2f}</div>
        <div class="card-label">Best AUC-ROC</div>
        <div class="card-sub">{report.best_policy}</div>
      </div>
      <div class="card">
        <div class="card-value">{report.avg_early_savings_pct:.1f}%</div>
        <div class="card-label">Avg Early Term Savings</div>
        <div class="card-sub">across all policies</div>
      </div>
      <div class="card">
        <div class="card-value">{best_precision:.2f}</div>
        <div class="card-label">Best Precision</div>
        <div class="card-sub">{max(results, key=lambda r: r.precision).policy_name}</div>
      </div>
      <div class="card">
        <div class="card-value">{best_f1:.3f}</div>
        <div class="card-label">Best F1 Score</div>
        <div class="card-sub">{max(results, key=lambda r: r.f1).policy_name}</div>
      </div>
    </div>"""

    # Table rows
    table_rows = ""
    for r in sorted(results, key=lambda x: x.auc_roc, reverse=True):
        highlight = ' style="color:#C74634;font-weight:bold;"' if r.policy_name == report.best_policy else ""
        table_rows += f"""
        <tr{highlight}>
          <td>{r.policy_name}</td>
          <td>{r.auc_roc:.3f}</td>
          <td>{r.precision:.3f}</td>
          <td>{r.recall:.3f}</td>
          <td>{r.f1:.3f}</td>
          <td>{r.early_term_savings_pct:.1f}%</td>
          <td>{r.false_positive_rate:.3f}</td>
        </tr>"""

    # OCI cost impact calc
    oci_gpu_hr = 3.06  # A100 OCI price USD/hr
    avg_episode_min = (TOTAL_FRAMES / 30) / 60  # ~0.028 min at 30fps
    dagger9_savings = 0.38
    eps_per_run = 1000
    saved_gpu_min = eps_per_run * avg_episode_min * dagger9_savings
    saved_cost = saved_gpu_min / 60 * oci_gpu_hr

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>Task Success Predictor — GR00T Episodes</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: #1e293b;
    color: #e2e8f0;
    font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
    padding: 24px;
    line-height: 1.5;
  }}
  h1 {{
    font-size: 1.6rem;
    color: #f1f5f9;
    margin-bottom: 4px;
  }}
  .subtitle {{
    color: #94a3b8;
    font-size: 0.9rem;
    margin-bottom: 28px;
  }}
  .oracle-red {{ color: #C74634; font-weight: bold; }}
  h2 {{
    font-size: 1.1rem;
    color: #cbd5e1;
    margin: 28px 0 14px;
    border-left: 3px solid #C74634;
    padding-left: 10px;
  }}
  .cards {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 16px;
    margin-bottom: 8px;
  }}
  .card {{
    background: #0f172a;
    border: 1px solid #334155;
    border-radius: 10px;
    padding: 18px 20px;
    text-align: center;
  }}
  .card-value {{
    font-size: 2rem;
    font-weight: 700;
    color: #C74634;
  }}
  .card-label {{
    font-size: 0.82rem;
    color: #94a3b8;
    margin-top: 4px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }}
  .card-sub {{
    font-size: 0.78rem;
    color: #64748b;
    margin-top: 2px;
  }}
  .charts {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(380px, 1fr));
    gap: 20px;
    margin-bottom: 8px;
  }}
  table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 0.9rem;
    background: #0f172a;
    border-radius: 8px;
    overflow: hidden;
  }}
  thead tr {{
    background: #1e3a5f;
    color: #93c5fd;
  }}
  th, td {{
    padding: 10px 14px;
    text-align: left;
    border-bottom: 1px solid #1e293b;
  }}
  tbody tr:hover {{ background: #1e2d40; }}
  .insight {{
    background: #0f172a;
    border: 1px solid #334155;
    border-left: 4px solid #C74634;
    border-radius: 8px;
    padding: 18px 20px;
    margin-top: 8px;
    font-size: 0.9rem;
    color: #cbd5e1;
  }}
  .insight p {{ margin-bottom: 8px; }}
  .insight p:last-child {{ margin-bottom: 0; }}
  .mono {{ font-family: monospace; }}
</style>
</head>
<body>
<h1>Task Success Predictor <span class="oracle-red">OCI Robot Cloud</span></h1>
<div class="subtitle">
  Early trajectory forecasting at frame {PREDICT_AT_FRAME}/{TOTAL_FRAMES} (20%) — GR00T N1.6 episodes •
  Predicted at: {PREDICT_AT_FRAME} / {TOTAL_FRAMES} frames &nbsp;|&nbsp;
  Policies evaluated: {len(results)} &nbsp;|&nbsp;
  Episodes per policy: {N_EPISODES}
</div>

<h2>Summary Metrics</h2>
{cards_html}

<h2>ROC &amp; Precision–Recall Curves</h2>
<div class="charts">
  {roc_svg}
  {pr_svg}
</div>

<h2>Policy Comparison Table</h2>
<table>
  <thead>
    <tr>
      <th>Policy</th>
      <th>AUC-ROC</th>
      <th>Precision</th>
      <th>Recall</th>
      <th>F1</th>
      <th>Early Term Savings</th>
      <th>False Positive Rate</th>
    </tr>
  </thead>
  <tbody>
    {table_rows}
  </tbody>
</table>

<h2>Insight: Compute Savings via Early Termination</h2>
<div class="insight">
  <p>Early termination of episodes predicted to fail at the 20% trajectory mark eliminates
     wasted GPU cycles on doomed rollouts. The predictor identifies low-confidence, low-probability
     episodes and short-circuits them before the remaining 80% of frames are generated.</p>
  <p><strong>dagger_run9</strong> achieves the highest AUC-ROC of <span class="oracle-red">0.89</span>
     with 38% early termination savings — the best balance of predictive accuracy and episode efficiency
     across all evaluated policies.</p>
  <p><strong>Cost impact at OCI A100 rates (${oci_gpu_hr:.2f}/hr):</strong>
     Over {eps_per_run:,} evaluation episodes, dagger_run9's 38% savings eliminates
     ~{saved_gpu_min:.1f} GPU-minutes, saving approximately
     <span class="oracle-red">${saved_cost:.4f}</span> per full eval run.
     Scaled across nightly regression suites (10 runs/day), this compounds to
     ~<span class="oracle-red">${saved_cost*10*30:.2f}/month</span> in avoided GPU spend.</p>
  <p><span class="mono">bc_baseline</span> (AUC 0.71, 22% savings) demonstrates the baseline case:
     even a weak predictor recovers meaningful compute; the delta between bc_baseline and
     dagger_run9 represents the marginal value of policy quality on infrastructure costs.</p>
</div>
</body>
</html>
"""
    return html


# ---------------------------------------------------------------------------
# stdout results table
# ---------------------------------------------------------------------------

def print_results_table(report: PredictorReport) -> None:
    header = f"{'Policy':<24} {'AUC-ROC':>8} {'Prec':>7} {'Recall':>7} {'F1':>7} {'EarlySave%':>11} {'FPR':>7}"
    sep = "-" * len(header)
    print("\n=== Task Success Predictor — Policy Results ===")
    print(sep)
    print(header)
    print(sep)
    for r in sorted(report.results, key=lambda x: x.auc_roc, reverse=True):
        marker = " *" if r.policy_name == report.best_policy else "  "
        print(
            f"{r.policy_name:<24} {r.auc_roc:>8.3f} {r.precision:>7.3f} "
            f"{r.recall:>7.3f} {r.f1:>7.3f} {r.early_term_savings_pct:>10.1f}% "
            f"{r.false_positive_rate:>7.3f}{marker}"
        )
    print(sep)
    print(f"Best AUC: {report.best_auc:.3f} ({report.best_policy})")
    print(f"Avg early termination savings: {report.avg_early_savings_pct:.1f}%")
    print(f"  * = best policy by AUC-ROC\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Early trajectory success predictor for GR00T episodes."
    )
    parser.add_argument("--mock", action="store_true", default=True,
                        help="Run with simulated data (default: True)")
    parser.add_argument("--output", default="/tmp/task_success_predictor.html",
                        help="Output HTML report path (default: /tmp/task_success_predictor.html)")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed for reproducible simulation (default: 42)")
    args = parser.parse_args()

    print(f"[task_success_predictor] seed={args.seed}, output={args.output}")
    print(f"  Simulating {N_EPISODES} episodes × {len(POLICY_PARAMS)} policies …")

    # Simulate samples and compute metrics
    results: List[PredictorResult] = []
    roc_data: dict = {}
    pr_data: dict = {}

    for idx, policy_name in enumerate(POLICY_PARAMS):
        seed = args.seed + idx * 1000
        samples = simulate_episode_samples(policy_name, seed)
        result = build_predictor_result(policy_name, samples)
        results.append(result)
        roc_data[policy_name] = compute_roc_points(samples)
        pr_data[policy_name] = compute_pr_points(samples)
        print(f"  [{policy_name}] AUC={result.auc_roc:.3f}  "
              f"P={result.precision:.3f}  R={result.recall:.3f}  "
              f"F1={result.f1:.3f}  EarlySave={result.early_term_savings_pct:.0f}%")

    report = build_report(results)
    print_results_table(report)

    # Build charts
    roc_svg = build_roc_svg(roc_data, results)
    pr_svg = build_pr_svg(pr_data, results)

    # Build and write HTML
    html = build_html_report(report, roc_svg, pr_svg)
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    print(f"[task_success_predictor] HTML report written → {out_path}")


if __name__ == "__main__":
    main()
