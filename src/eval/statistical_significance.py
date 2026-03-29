#!/usr/bin/env python3
"""
statistical_significance.py — Bootstrap confidence interval analysis for closed-loop eval results.

Robotic evals typically have small sample sizes (20 episodes) so confidence intervals
are critical for paper credibility. This script provides:
  - Bootstrap resampling (10,000 iterations) for each run
  - Permutation test p-values for pairwise comparisons
  - JSON output suitable for embedding in a paper appendix

Usage:
    python src/eval/statistical_significance.py \
        --eval-dirs /tmp/eval_bc /tmp/eval_dagger \
        --labels "BC" "DAgger" \
        --output /tmp/significance.json

    # Mock mode (synthetic data matching documented results):
    python src/eval/statistical_significance.py --mock
"""

import argparse
import json
import math
import random
import statistics
from pathlib import Path


# ── Episode loading ────────────────────────────────────────────────────────────

def load_episodes(eval_dir: Path) -> list[bool]:
    """
    Load per-episode success outcomes from an eval output directory.

    Priority:
      1. episodes.json  — list of {"success": bool, ...}
      2. summary.json   — uses success_rate + num_episodes with Binomial expansion
    Returns a list of booleans (True = success).
    """
    d = Path(eval_dir)

    # 1. Prefer episodes.json
    ep_file = d / "episodes.json"
    if ep_file.exists():
        data = json.loads(ep_file.read_text())
        if isinstance(data, list):
            return [bool(e.get("success", False)) for e in data]

    # 2. Fall back to summary.json
    for fname in ("summary.json", "eval_summary.json", "results.json"):
        sf = d / fname
        if sf.exists():
            summary = json.loads(sf.read_text())
            n = int(summary.get("num_episodes", summary.get("n_episodes", 20)))
            rate = float(summary.get("success_rate", 0.0))
            n_success = round(rate * n)
            # Expand to per-episode list (Binomial assumption)
            episodes = [True] * n_success + [False] * (n - n_success)
            random.shuffle(episodes)
            return episodes

    raise FileNotFoundError(
        f"No episodes.json or summary.json found in {eval_dir}"
    )


def mock_episodes() -> dict[str, list[bool]]:
    """
    Generate synthetic episode data consistent with documented results:
      BC baseline:    1/20 success
      DAgger iter 3: 13/20 success
    """
    bc = [True] * 1 + [False] * 19
    random.shuffle(bc)
    dagger = [True] * 13 + [False] * 7
    random.shuffle(dagger)
    return {"BC": bc, "DAgger": dagger}


# ── Bootstrap analysis ─────────────────────────────────────────────────────────

def bootstrap_ci(
    episodes: list[bool],
    n_iters: int = 10_000,
    confidence: float = 0.95,
) -> tuple[float, float, float]:
    """
    Bootstrap confidence interval for success rate.

    Returns (mean, ci_lower, ci_upper).
    """
    n = len(episodes)
    if n == 0:
        return 0.0, 0.0, 0.0

    resampled_rates = []
    for _ in range(n_iters):
        sample = [random.choice(episodes) for _ in range(n)]
        resampled_rates.append(sum(sample) / n)

    resampled_rates.sort()
    alpha = 1.0 - confidence
    lower_idx = int(math.floor(alpha / 2 * n_iters))
    upper_idx = int(math.ceil((1.0 - alpha / 2) * n_iters)) - 1
    lower_idx = max(0, lower_idx)
    upper_idx = min(n_iters - 1, upper_idx)

    mean = statistics.mean(resampled_rates)
    return mean, resampled_rates[lower_idx], resampled_rates[upper_idx]


# ── Permutation test ───────────────────────────────────────────────────────────

def permutation_test(
    episodes_a: list[bool],
    episodes_b: list[bool],
    n_iters: int = 10_000,
) -> float:
    """
    Two-sample permutation test for difference in success rates.

    Null hypothesis: the two groups are drawn from the same distribution.
    Returns p-value (fraction of permutations with |diff| >= observed |diff|).
    """
    rate_a = sum(episodes_a) / len(episodes_a) if episodes_a else 0.0
    rate_b = sum(episodes_b) / len(episodes_b) if episodes_b else 0.0
    observed_diff = abs(rate_b - rate_a)

    combined = episodes_a + episodes_b
    na = len(episodes_a)
    count_ge = 0

    for _ in range(n_iters):
        random.shuffle(combined)
        perm_a = combined[:na]
        perm_b = combined[na:]
        perm_rate_a = sum(perm_a) / len(perm_a) if perm_a else 0.0
        perm_rate_b = sum(perm_b) / len(perm_b) if perm_b else 0.0
        if abs(perm_rate_b - perm_rate_a) >= observed_diff:
            count_ge += 1

    return count_ge / n_iters


# ── Formatting helpers ─────────────────────────────────────────────────────────

def pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def significance_stars(p: float) -> str:
    if p < 0.001:
        return "***"
    if p < 0.01:
        return "**"
    if p < 0.05:
        return "*"
    return "ns"


def improvement_label(rate_a: float, rate_b: float) -> str:
    if rate_a == 0:
        return "∞×" if rate_b > 0 else "—"
    ratio = rate_b / rate_a
    return f"{ratio:.1f}×"


# ── Console report ─────────────────────────────────────────────────────────────

def print_report(runs: list[dict], pairwise: list[dict], confidence: float) -> None:
    pct_conf = int(confidence * 100)
    width = 54

    print()
    print("Statistical Significance Analysis")
    print("═" * width)

    # Per-run lines
    label_w = max(len(r["label"]) for r in runs) + 2
    for r in runs:
        label = r["label"].ljust(label_w)
        rate = pct(r["success_rate"])
        ci_lo = pct(r["ci_lower"])
        ci_hi = pct(r["ci_upper"])
        n = r["n_episodes"]
        print(f"  {label}  {rate:>6}  [{ci_lo} – {ci_hi}]  (n={n})")

    print("─" * width)

    # Pairwise lines
    for pw in pairwise:
        stars = significance_stars(pw["p_value"])
        sig_note = "CI confirmed" if pw["significant"] else "not significant"
        print(
            f"  {pw['a']} → {pw['b']}:  "
            f"p={pw['p_value']:.4f} {stars}  "
            f"({pw['improvement']} improvement, {pct_conf}% {sig_note})"
        )

    print()


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Bootstrap CI + permutation test for closed-loop eval results."
    )
    parser.add_argument(
        "--eval-dirs",
        nargs="+",
        metavar="DIR",
        help="One or more eval output directories (each must contain summary.json or episodes.json).",
    )
    parser.add_argument(
        "--labels",
        nargs="+",
        metavar="LABEL",
        help="Display labels for each eval dir (same order). Defaults to dir names.",
    )
    parser.add_argument(
        "--bootstrap-iters",
        type=int,
        default=10_000,
        metavar="N",
        help="Number of bootstrap resampling iterations (default: 10000).",
    )
    parser.add_argument(
        "--confidence",
        type=float,
        default=0.95,
        metavar="LEVEL",
        help="Confidence level for intervals, e.g. 0.95 (default: 0.95).",
    )
    parser.add_argument(
        "--output",
        default="/tmp/significance.json",
        metavar="PATH",
        help="Output JSON file (default: /tmp/significance.json).",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use synthetic data matching documented results (BC=1/20, DAgger=13/20).",
    )
    args = parser.parse_args()

    random.seed(42)

    # ── Load episodes ──────────────────────────────────────────────────────────
    if args.mock:
        episodes_map = mock_episodes()
        labels = list(episodes_map.keys())
        episodes_list = list(episodes_map.values())
        print("[mock mode] Generating synthetic episodes: BC=1/20, DAgger=13/20")
    else:
        if not args.eval_dirs:
            parser.error("--eval-dirs is required unless --mock is set.")
        dirs = [Path(d) for d in args.eval_dirs]
        labels = args.labels if args.labels else [d.name for d in dirs]
        if len(labels) != len(dirs):
            parser.error("--labels must have the same length as --eval-dirs.")
        episodes_list = []
        for d, lbl in zip(dirs, labels):
            print(f"Loading {lbl} from {d} ...")
            eps = load_episodes(d)
            print(f"  → {len(eps)} episodes, {sum(eps)} successes ({sum(eps)/len(eps)*100:.1f}%)")
            episodes_list.append(eps)

    # ── Bootstrap per run ──────────────────────────────────────────────────────
    n_iters = args.bootstrap_iters
    confidence = args.confidence
    print(f"\nRunning bootstrap ({n_iters:,} iterations, {int(confidence*100)}% CI) ...")

    run_results = []
    for lbl, eps in zip(labels, episodes_list):
        mean, ci_lo, ci_hi = bootstrap_ci(eps, n_iters=n_iters, confidence=confidence)
        run_results.append(
            {
                "label": lbl,
                "success_rate": round(sum(eps) / len(eps), 4),
                "ci_lower": round(ci_lo, 4),
                "ci_upper": round(ci_hi, 4),
                "n_episodes": len(eps),
            }
        )

    # ── Pairwise permutation tests ─────────────────────────────────────────────
    print(f"Running permutation tests ({n_iters:,} iterations) ...")
    pairwise_results = []
    for i in range(len(labels)):
        for j in range(i + 1, len(labels)):
            lbl_a, lbl_b = labels[i], labels[j]
            eps_a, eps_b = episodes_list[i], episodes_list[j]
            p = permutation_test(eps_a, eps_b, n_iters=n_iters)
            rate_a = sum(eps_a) / len(eps_a) if eps_a else 0.0
            rate_b = sum(eps_b) / len(eps_b) if eps_b else 0.0
            pairwise_results.append(
                {
                    "a": lbl_a,
                    "b": lbl_b,
                    "p_value": round(p, 4),
                    "significant": p < 0.05,
                    "improvement": improvement_label(rate_a, rate_b),
                }
            )

    # ── Console output ─────────────────────────────────────────────────────────
    print_report(run_results, pairwise_results, confidence)

    # ── Write JSON ─────────────────────────────────────────────────────────────
    output = {
        "runs": run_results,
        "pairwise": pairwise_results,
        "config": {
            "bootstrap_iters": n_iters,
            "confidence": confidence,
        },
    }
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, indent=2))
    print(f"Results written to {out_path}")


if __name__ == "__main__":
    main()
