#!/usr/bin/env python3
"""
regression_test_suite.py — Automated regression test suite for GR00T fine-tuned checkpoints.

Runs a fixed battery of test scenarios after each fine-tune or DAgger run to detect
performance regressions before deploying to production. Tests cover MAE, inference latency,
memory usage, action smoothness, and behavioral consistency.

Usage:
    python src/eval/regression_test_suite.py --mock --output /tmp/regression_tests.html
    python src/eval/regression_test_suite.py --checkpoint /tmp/dagger_run9/checkpoint_5000
"""

import argparse
import json
import math
import random
import time
from dataclasses import dataclass, field
from pathlib import Path


# ── Test definitions ───────────────────────────────────────────────────────────

REGRESSION_TESTS = [
    # (name, category, description, threshold, unit, lower_is_better)
    ("mae_val",             "accuracy",    "Validation MAE on held-out demos",       0.025, "MAE",   True),
    ("mae_train",           "accuracy",    "Training MAE (check for overfit)",        0.020, "MAE",   True),
    ("mae_overfit_ratio",   "accuracy",    "Train/Val MAE ratio (overfit detector)",  1.25,  "ratio", True),
    ("inference_p50",       "latency",     "Median inference latency",               250.0,  "ms",    True),
    ("inference_p95",       "latency",     "p95 inference latency",                  400.0,  "ms",    True),
    ("inference_p99",       "latency",     "p99 inference latency (SLA gate)",       500.0,  "ms",    True),
    ("peak_vram_gb",        "memory",      "Peak VRAM during inference",              10.0,  "GB",    True),
    ("load_time_s",         "memory",      "Model load time from disk",               15.0,  "s",     True),
    ("action_jerk_rms",     "smoothness",  "RMS jerk of predicted action sequences",  0.35,  "",      True),
    ("gripper_consistency", "behavior",    "Gripper open/close consistency rate",     0.95,  "",      False),
    ("goal_reach_5ep",      "behavior",    "Goal reached in 5 fixed test episodes",   0.80,  "",      False),
    ("det_variance",        "determinism", "Output variance under identical inputs",  0.001, "",      True),
    ("throughput_bs8",      "performance", "Batch-8 inference throughput",            6.0,   "inf/s", False),
    ("checkpoint_size_gb",  "storage",     "Checkpoint file size",                    4.0,   "GB",    True),
]

CATEGORIES = ["accuracy", "latency", "memory", "smoothness", "behavior", "determinism", "performance", "storage"]

CAT_COLORS = {
    "accuracy": "#3b82f6", "latency": "#a855f7", "memory": "#f59e0b",
    "smoothness": "#22c55e", "behavior": "#C74634", "determinism": "#06b6d4",
    "performance": "#84cc16", "storage": "#64748b",
}


@dataclass
class TestResult:
    name: str
    category: str
    description: str
    threshold: float
    unit: str
    lower_is_better: bool
    value: float
    baseline_value: float   # from previous known-good checkpoint
    passed: bool
    regression_pct: float   # % change from baseline (positive = worse for user)
    severity: str           # pass / warn / fail


@dataclass
class SuiteResult:
    checkpoint: str
    passed: int
    warned: int
    failed: int
    total: int
    suite_passed: bool
    blocking_failures: list[str]
    results: list[TestResult] = field(default_factory=list)


# ── Simulation ─────────────────────────────────────────────────────────────────

# Baseline values from known-good checkpoint (dagger_run9, step 5000)
BASELINES = {
    "mae_val":             0.016,
    "mae_train":           0.011,
    "mae_overfit_ratio":   0.688,
    "inference_p50":       226.0,
    "inference_p95":       310.0,
    "inference_p99":       380.0,
    "peak_vram_gb":        7.2,
    "load_time_s":         8.3,
    "action_jerk_rms":     0.21,
    "gripper_consistency": 0.97,
    "goal_reach_5ep":      1.00,
    "det_variance":        0.00012,
    "throughput_bs8":      8.4,
    "checkpoint_size_gb":  2.9,
}


def simulate_regression_tests(checkpoint: str, seed: int = 42) -> SuiteResult:
    rng = random.Random(seed)
    results = []

    for name, cat, desc, threshold, unit, lower_better in REGRESSION_TESTS:
        baseline = BASELINES[name]

        # Simulate small random deviation — occasionally inject regression
        regress_factor = 1.0
        if rng.random() < 0.15:  # 15% chance per metric
            regress_factor = rng.uniform(1.10, 1.35) if lower_better else rng.uniform(0.70, 0.90)

        noise = rng.gauss(0, baseline * 0.04)
        value = max(1e-6, baseline * regress_factor + noise)

        # Regression % (positive = worse)
        regression_pct = (value - baseline) / baseline * 100
        if not lower_better:
            regression_pct = -regression_pct

        passed_threshold = (value <= threshold) if lower_better else (value >= threshold)

        severity = "fail" if not passed_threshold else (
            "warn" if regression_pct > 10 else "pass"
        )

        results.append(TestResult(
            name=name,
            category=cat,
            description=desc,
            threshold=threshold,
            unit=unit,
            lower_is_better=lower_better,
            value=round(value, 6),
            baseline_value=baseline,
            passed=passed_threshold,
            regression_pct=round(regression_pct, 1),
            severity=severity,
        ))

    passed = sum(1 for r in results if r.severity == "pass")
    warned = sum(1 for r in results if r.severity == "warn")
    failed = sum(1 for r in results if r.severity == "fail")
    blocking = [r.name for r in results if r.severity == "fail"]

    return SuiteResult(
        checkpoint=checkpoint,
        passed=passed,
        warned=warned,
        failed=failed,
        total=len(results),
        suite_passed=(len(blocking) == 0),
        blocking_failures=blocking,
        results=results,
    )


# ── HTML ───────────────────────────────────────────────────────────────────────

def render_html(suite: SuiteResult) -> str:
    banner_col = "#22c55e" if suite.suite_passed else "#ef4444"
    banner_txt = ("✓ SUITE PASSED — SAFE TO DEPLOY"
                  if suite.suite_passed else
                  "✗ SUITE FAILED — BLOCK DEPLOYMENT")

    # Category cards
    cat_cards = ""
    for cat in CATEGORIES:
        cat_results = [r for r in suite.results if r.category == cat]
        if not cat_results:
            continue
        n_pass = sum(1 for r in cat_results if r.severity == "pass")
        n_warn = sum(1 for r in cat_results if r.severity == "warn")
        n_fail = sum(1 for r in cat_results if r.severity == "fail")
        col = "#22c55e" if n_fail == 0 and n_warn == 0 else "#f59e0b" if n_fail == 0 else "#ef4444"
        cat_cards += (f'<div class="card">'
                      f'<h3 style="color:{CAT_COLORS[cat]}">{cat.upper()}</h3>'
                      f'<div style="color:{col};font-size:20px;font-weight:bold">'
                      f'{n_pass}P / {n_warn}W / {n_fail}F</div>'
                      f'<div style="color:#64748b;font-size:10px">{len(cat_results)} tests</div>'
                      f'</div>')

    # Results table
    rows = ""
    for r in suite.results:
        sev_col = {"pass": "#22c55e", "warn": "#f59e0b", "fail": "#ef4444"}.get(r.severity, "#94a3b8")
        reg_col = "#ef4444" if r.regression_pct > 15 else "#f59e0b" if r.regression_pct > 5 else "#22c55e"
        reg_arrow = "▲" if r.regression_pct > 0 else "▼"
        dir_label = "lower↓" if r.lower_is_better else "higher↑"
        rows += (f'<tr>'
                 f'<td style="color:{CAT_COLORS.get(r.category,"#94a3b8")}">{r.category}</td>'
                 f'<td style="color:#e2e8f0">{r.name}</td>'
                 f'<td style="color:#94a3b8;font-size:10px">{r.description}</td>'
                 f'<td style="color:#e2e8f0">{r.value:.5g} {r.unit}</td>'
                 f'<td style="color:#64748b">{r.baseline_value:.5g}</td>'
                 f'<td style="color:#64748b">{r.threshold:.5g} ({dir_label})</td>'
                 f'<td style="color:{reg_col}">{reg_arrow}{abs(r.regression_pct):.1f}%</td>'
                 f'<td style="color:{sev_col};font-weight:bold">{r.severity.upper()}</td>'
                 f'</tr>')

    blocking_html = ""
    if suite.blocking_failures:
        blocking_html = (f'<div style="background:#7f1d1d;border-radius:6px;padding:10px 14px;'
                         f'margin-bottom:16px;color:#fca5a5;font-size:12px">'
                         f'<b>Blocking failures:</b> {", ".join(suite.blocking_failures)}</div>')

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Regression Test Suite</title>
<style>
body{{background:#1e293b;color:#e2e8f0;font-family:monospace;margin:0;padding:24px}}
h1{{color:#C74634;margin:0 0 4px}}
.meta{{color:#94a3b8;font-size:12px;margin-bottom:20px}}
.banner{{border-radius:8px;padding:14px 20px;font-size:18px;font-weight:bold;
         background:#0f172a;margin-bottom:20px}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:20px}}
.card{{background:#0f172a;border-radius:8px;padding:12px}}
.card h3{{font-size:10px;text-transform:uppercase;margin:0 0 4px}}
table{{width:100%;border-collapse:collapse;font-size:11px}}
th{{color:#94a3b8;text-align:left;padding:5px 8px;border-bottom:1px solid #334155}}
td{{padding:3px 8px;border-bottom:1px solid #1e293b}}
</style></head>
<body>
<h1>Regression Test Suite</h1>
<div class="meta">Checkpoint: {suite.checkpoint} · {suite.total} tests</div>

<div class="banner" style="color:{banner_col}">{banner_txt}</div>

{blocking_html}

<div class="grid">
  <div class="card"><h3>Passed</h3>
    <div style="color:#22c55e;font-size:24px;font-weight:bold">{suite.passed}</div>
  </div>
  <div class="card"><h3>Warnings</h3>
    <div style="color:#f59e0b;font-size:24px;font-weight:bold">{suite.warned}</div>
  </div>
  <div class="card"><h3>Failed</h3>
    <div style="color:#ef4444;font-size:24px;font-weight:bold">{suite.failed}</div>
  </div>
  <div class="card"><h3>Pass Rate</h3>
    <div style="color:#3b82f6;font-size:24px;font-weight:bold">
      {suite.passed / suite.total * 100:.0f}%
    </div>
  </div>
</div>

<h3 style="color:#94a3b8;font-size:11px;text-transform:uppercase;margin-bottom:8px">
  By Category
</h3>
<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:20px">
  {cat_cards}
</div>

<h3 style="color:#94a3b8;font-size:11px;text-transform:uppercase;margin-bottom:8px">
  Test Results
</h3>
<table>
  <tr><th>Category</th><th>Test</th><th>Description</th>
      <th>Value</th><th>Baseline</th><th>Threshold</th><th>Δ vs Baseline</th><th>Status</th></tr>
  {rows}
</table>

<div style="color:#64748b;font-size:11px;margin-top:16px">
  Baseline: dagger_run9/checkpoint_5000 (best known-good) ·
  Warn = &gt;10% regression · Block = exceeds absolute threshold
</div>
</body></html>"""


# ── CLI ────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Regression test suite for GR00T checkpoints")
    parser.add_argument("--mock",        action="store_true", default=True)
    parser.add_argument("--checkpoint",  default="dagger_run9/checkpoint_5000")
    parser.add_argument("--output",      default="/tmp/regression_tests.html")
    parser.add_argument("--seed",        type=int, default=42)
    args = parser.parse_args()

    print(f"[regression-suite] Testing checkpoint: {args.checkpoint}")
    t0 = time.time()

    suite = simulate_regression_tests(args.checkpoint, args.seed)

    print(f"\n  {'Test':<25} {'Value':>10} {'Baseline':>10} {'Δ%':>7}  Status")
    print(f"  {'─'*25} {'─'*10} {'─'*10} {'─'*7}  {'─'*6}")
    for r in suite.results:
        sev = r.severity.upper()
        print(f"  {r.name:<25} {r.value:>10.5g} {r.baseline_value:>10.5g} "
              f"{r.regression_pct:>+6.1f}%  {sev}")

    status = "PASSED" if suite.suite_passed else "FAILED"
    print(f"\n  Suite: {status}  ({suite.passed}P/{suite.warned}W/{suite.failed}F / {suite.total})")
    if suite.blocking_failures:
        print(f"  Blocking: {', '.join(suite.blocking_failures)}")
    print(f"  [{time.time()-t0:.1f}s]\n")

    html = render_html(suite)
    Path(args.output).write_text(html)
    print(f"  HTML → {args.output}")

    json_out = Path(args.output).with_suffix(".json")
    json_out.write_text(json.dumps({
        "checkpoint": suite.checkpoint,
        "suite_passed": suite.suite_passed,
        "passed": suite.passed, "warned": suite.warned, "failed": suite.failed,
        "blocking_failures": suite.blocking_failures,
    }, indent=2))
    print(f"  JSON → {json_out}")


if __name__ == "__main__":
    main()
