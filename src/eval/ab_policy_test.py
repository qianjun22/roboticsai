#!/usr/bin/env python3
"""
ab_policy_test.py — A/B policy promotion test for GR00T checkpoints.

Splits eval episodes between a control (BC/DAgger-old) and treatment (DAgger-new)
policy, tracks success-rate difference, runs a chi-square significance test, and
recommends whether to promote the treatment to production.

Usage:
    python src/eval/ab_policy_test.py --mock
    python src/eval/ab_policy_test.py --mock --control BC-1000 --treatment DAgger-run9 \\
        --n 50 --output /tmp/ab_policy_test.html
"""

import argparse
import math
import random
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Tuple


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class ABTestConfig:
    test_id: str
    control_model: str
    treatment_model: str
    n_episodes_per_arm: int = 50
    significance_level: float = 0.05
    min_detectable_effect: float = 0.10
    task: str = "pick_and_place"
    started_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class ABTestResult:
    test_id: str
    control_sr: float
    control_n: int
    treatment_sr: float
    treatment_n: int
    sr_diff: float
    relative_improvement_pct: float
    p_value: float
    significant: bool
    power: float
    recommendation: str          # "promote" | "hold" | "reject"
    confidence_interval_95: Tuple[float, float]


# ---------------------------------------------------------------------------
# Statistical helpers (pure Python, no scipy)
# ---------------------------------------------------------------------------

def _normal_cdf(x: float) -> float:
    """Abramowitz & Stegun approximation for Φ(x)."""
    t = 1.0 / (1.0 + 0.2316419 * abs(x))
    poly = t * (0.319381530
                + t * (-0.356563782
                       + t * (1.781477937
                              + t * (-1.821255978
                                     + t * 1.330274429))))
    phi = 1.0 - (1.0 / math.sqrt(2 * math.pi)) * math.exp(-0.5 * x * x) * poly
    return phi if x >= 0 else 1.0 - phi


def _chi2_cdf_1df(x: float) -> float:
    """CDF of chi-squared distribution with 1 degree of freedom via regularized gamma."""
    # χ²(1) = Gamma(1/2, 1/2) → use incomplete gamma via series
    if x <= 0:
        return 0.0
    return math.erf(math.sqrt(x / 2.0))


def chi_square_proportion_test(n1: int, k1: int, n2: int, k2: int) -> float:
    """
    Chi-square test for equality of two proportions.

    Args:
        n1: total episodes in arm 1 (control)
        k1: successes in arm 1
        n2: total episodes in arm 2 (treatment)
        k2: successes in arm 2

    Returns:
        p_value (two-tailed)
    """
    N = n1 + n2
    K = k1 + k2
    if K == 0 or K == N:
        return 1.0  # degenerate — no information

    # Expected counts under H0 (pooled proportion)
    p_pool = K / N
    e11 = n1 * p_pool
    e12 = n1 * (1 - p_pool)
    e21 = n2 * p_pool
    e22 = n2 * (1 - p_pool)

    # Yates-corrected chi-square (better for small n)
    def yates(observed, expected):
        return (abs(observed - expected) - 0.5) ** 2 / expected

    chi2 = (yates(k1, e11) + yates(n1 - k1, e12)
            + yates(k2, e21) + yates(n2 - k2, e22))

    p_value = 1.0 - _chi2_cdf_1df(chi2)
    return max(0.0, min(1.0, p_value))


def compute_power(p1: float, p2: float, n: int, alpha: float = 0.05) -> float:
    """
    Approximate power for a two-proportion z-test (one-sided).

    Args:
        p1: control success rate
        p2: treatment success rate
        n:  episodes per arm
        alpha: significance level

    Returns:
        power in [0, 1]
    """
    if p1 == p2 or n == 0:
        return alpha
    z_alpha = 1.6449  # z_{1-α} for one-sided α=0.05
    p_bar = (p1 + p2) / 2.0
    sigma_h0 = math.sqrt(2 * p_bar * (1 - p_bar) / n)
    sigma_h1 = math.sqrt(p1 * (1 - p1) / n + p2 * (1 - p2) / n)
    if sigma_h1 == 0:
        return 1.0
    z_beta = (abs(p2 - p1) - z_alpha * sigma_h0) / sigma_h1
    return _normal_cdf(z_beta)


def _wilson_ci(k: int, n: int, alpha: float = 0.05) -> Tuple[float, float]:
    """Wilson score confidence interval."""
    z = 1.96  # z_{0.975} for 95% CI
    if n == 0:
        return (0.0, 1.0)
    p_hat = k / n
    denom = 1 + z * z / n
    center = (p_hat + z * z / (2 * n)) / denom
    half = (z / denom) * math.sqrt(p_hat * (1 - p_hat) / n + z * z / (4 * n * n))
    return (max(0.0, center - half), min(1.0, center + half))


def _diff_ci(k1: int, n1: int, k2: int, n2: int) -> Tuple[float, float]:
    """Wald CI for difference in proportions (treatment - control)."""
    p1 = k1 / n1 if n1 else 0.0
    p2 = k2 / n2 if n2 else 0.0
    se = math.sqrt(p1 * (1 - p1) / n1 + p2 * (1 - p2) / n2) if n1 and n2 else 0.0
    diff = p2 - p1
    return (diff - 1.96 * se, diff + 1.96 * se)


def _sample_size_for_power(p1: float, effect: float, power: float = 0.80,
                            alpha: float = 0.05) -> int:
    """Minimum n per arm to achieve target power."""
    p2 = p1 + effect
    p2 = min(max(p2, 0.001), 0.999)
    z_a = 1.6449
    z_b = 0.8416  # z_{0.80}
    p_bar = (p1 + p2) / 2
    n = ((z_a * math.sqrt(2 * p_bar * (1 - p_bar))
          + z_b * math.sqrt(p1 * (1 - p1) + p2 * (1 - p2))) ** 2
         / (p2 - p1) ** 2)
    return math.ceil(n)


# ---------------------------------------------------------------------------
# Test execution
# ---------------------------------------------------------------------------

# Known baselines (from memory: session 14 + session 16 evals)
_CONTROL_BASELINES = {"BC-1000": 0.05, "DAgger-run5": 0.05}
_TREATMENT_BASELINES = {"DAgger-run9": 0.68, "DAgger-run5": 0.05}
_DEFAULT_CONTROL_SR = 0.05
_DEFAULT_TREATMENT_SR = 0.68


def run_ab_test(config: ABTestConfig, seed: int = 42) -> ABTestResult:
    """
    Simulate an A/B test using known SR baselines + sampling noise.
    In a live deployment, replace the simulation block with real episode runners.
    """
    rng = random.Random(seed)
    n = config.n_episodes_per_arm

    p_ctrl = _CONTROL_BASELINES.get(config.control_model, _DEFAULT_CONTROL_SR)
    p_trt = _TREATMENT_BASELINES.get(config.treatment_model, _DEFAULT_TREATMENT_SR)

    # Simulate binomial draws
    k_ctrl = sum(1 for _ in range(n) if rng.random() < p_ctrl)
    k_trt = sum(1 for _ in range(n) if rng.random() < p_trt)

    sr_ctrl = k_ctrl / n
    sr_trt = k_trt / n
    diff = sr_trt - sr_ctrl
    rel_imp = (diff / sr_ctrl * 100) if sr_ctrl > 0 else float("inf")

    p_value = chi_square_proportion_test(n, k_ctrl, n, k_trt)
    significant = p_value < config.significance_level
    power = compute_power(p_ctrl, p_trt, n, config.significance_level)
    ci = _diff_ci(k_ctrl, n, k_trt, n)

    if significant and diff > 0:
        recommendation = "promote"
    elif significant and diff < 0:
        recommendation = "reject"
    else:
        recommendation = "hold"

    return ABTestResult(
        test_id=config.test_id,
        control_sr=sr_ctrl,
        control_n=n,
        treatment_sr=sr_trt,
        treatment_n=n,
        sr_diff=diff,
        relative_improvement_pct=rel_imp,
        p_value=p_value,
        significant=significant,
        power=power,
        recommendation=recommendation,
        confidence_interval_95=ci,
    )


def sequential_test(config: ABTestConfig, n_interim: int = 5,
                    seed: int = 42) -> Tuple[List[dict], ABTestResult]:
    """
    Sequential (group-sequential) test with Bonferroni-adjusted alpha at each look.
    Returns a list of interim records and the final ABTestResult.
    """
    rng = random.Random(seed)
    n_total = config.n_episodes_per_arm
    chunk = max(1, n_total // n_interim)
    alpha_adj = config.significance_level / n_interim  # Bonferroni correction

    p_ctrl = _CONTROL_BASELINES.get(config.control_model, _DEFAULT_CONTROL_SR)
    p_trt = _TREATMENT_BASELINES.get(config.treatment_model, _DEFAULT_TREATMENT_SR)

    all_ctrl = [1 if rng.random() < p_ctrl else 0 for _ in range(n_total)]
    all_trt = [1 if rng.random() < p_trt else 0 for _ in range(n_total)]

    interims: List[dict] = []
    stopped_early = False
    stop_look = n_interim
    for look in range(1, n_interim + 1):
        n_so_far = min(look * chunk, n_total)
        k_c = sum(all_ctrl[:n_so_far])
        k_t = sum(all_trt[:n_so_far])
        pv = chi_square_proportion_test(n_so_far, k_c, n_so_far, k_t)
        interims.append({
            "look": look,
            "n_per_arm": n_so_far,
            "control_sr": k_c / n_so_far,
            "treatment_sr": k_t / n_so_far,
            "p_value": pv,
            "threshold": alpha_adj,
            "stopped": pv < alpha_adj and not stopped_early,
        })
        if pv < alpha_adj and not stopped_early:
            stopped_early = True
            stop_look = look

    # Final result uses full data
    k_ctrl = sum(all_ctrl)
    k_trt = sum(all_trt)
    sr_ctrl = k_ctrl / n_total
    sr_trt = k_trt / n_total
    diff = sr_trt - sr_ctrl
    rel_imp = (diff / sr_ctrl * 100) if sr_ctrl > 0 else float("inf")
    p_value = chi_square_proportion_test(n_total, k_ctrl, n_total, k_trt)
    significant = p_value < config.significance_level
    power = compute_power(p_ctrl, p_trt, n_total, config.significance_level)
    ci = _diff_ci(k_ctrl, n_total, k_trt, n_total)
    recommendation = ("promote" if significant and diff > 0
                      else "reject" if significant and diff < 0
                      else "hold")

    final = ABTestResult(
        test_id=config.test_id,
        control_sr=sr_ctrl,
        control_n=n_total,
        treatment_sr=sr_trt,
        treatment_n=n_total,
        sr_diff=diff,
        relative_improvement_pct=rel_imp,
        p_value=p_value,
        significant=significant,
        power=power,
        recommendation=recommendation,
        confidence_interval_95=ci,
    )
    return interims, final


# ---------------------------------------------------------------------------
# HTML report
# ---------------------------------------------------------------------------

def _rec_color(rec: str) -> str:
    return {"promote": "#22c55e", "hold": "#f59e0b", "reject": "#ef4444"}.get(rec, "#94a3b8")


def _rec_label(rec: str) -> str:
    return {"promote": "PROMOTE to Production",
            "hold": "HOLD — Insufficient Evidence",
            "reject": "REJECT — Treatment Underperforms"}.get(rec, rec.upper())


def _rec_explanation(result: ABTestResult) -> str:
    if result.recommendation == "promote":
        return (f"Treatment <b>{result.treatment_sr:.1%}</b> SR vs control "
                f"<b>{result.control_sr:.1%}</b> SR — absolute lift "
                f"<b>+{result.sr_diff:.1%}</b> "
                f"({result.relative_improvement_pct:.1f}% relative). "
                f"p = {result.p_value:.4f} &lt; α = 0.05. Statistically significant.")
    if result.recommendation == "reject":
        return (f"Treatment SR <b>{result.treatment_sr:.1%}</b> is lower than control "
                f"<b>{result.control_sr:.1%}</b>. "
                f"p = {result.p_value:.4f}. Do not deploy.")
    return (f"p = {result.p_value:.4f} ≥ α = 0.05. "
            f"Difference of {result.sr_diff:+.1%} is not yet statistically significant. "
            f"Estimated power: {result.power:.1%}. Collect more episodes.")


def _svg_ci_plot(result: ABTestResult) -> str:
    """Two horizontal CI bars: control (gray) and treatment (Oracle red)."""
    w, h = 560, 160
    pad_l, pad_r, pad_t, pad_b = 60, 30, 30, 40

    ctrl_ci = _wilson_ci(round(result.control_sr * result.control_n), result.control_n)
    trt_ci = _wilson_ci(round(result.treatment_sr * result.treatment_n), result.treatment_n)

    lo = min(ctrl_ci[0], trt_ci[0], result.control_sr, result.treatment_sr)
    hi = max(ctrl_ci[1], trt_ci[1], result.control_sr, result.treatment_sr)
    span = max(hi - lo, 0.01)
    lo -= 0.05 * span
    hi += 0.05 * span
    span = hi - lo

    def px(v):
        return pad_l + (v - lo) / span * (w - pad_l - pad_r)

    ctrl_y = pad_t + (h - pad_t - pad_b) * 0.35
    trt_y = pad_t + (h - pad_t - pad_b) * 0.70
    ey = 8  # half-height of error-bar ticks

    lines = []

    # Axis
    lines.append(
        f'<line x1="{pad_l}" y1="{h - pad_b}" x2="{w - pad_r}" y2="{h - pad_b}" '
        f'stroke="#475569" stroke-width="1"/>'
    )

    # Tick marks on x axis
    for v in [lo + span * i / 5 for i in range(6)]:
        xp = px(v)
        lines.append(
            f'<line x1="{xp:.1f}" y1="{h - pad_b}" x2="{xp:.1f}" y2="{h - pad_b + 4}" '
            f'stroke="#475569" stroke-width="1"/>'
        )
        lines.append(
            f'<text x="{xp:.1f}" y="{h - pad_b + 16}" text-anchor="middle" '
            f'fill="#94a3b8" font-size="11">{v:.0%}</text>'
        )

    # Control vertical reference line
    ref_x = px(result.control_sr)
    lines.append(
        f'<line x1="{ref_x:.1f}" y1="{pad_t}" x2="{ref_x:.1f}" y2="{h - pad_b}" '
        f'stroke="#64748b" stroke-width="1" stroke-dasharray="4,3"/>'
    )

    for (y_c, ci, mean_v, color, label) in [
        (ctrl_y, ctrl_ci, result.control_sr, "#94a3b8", "Control"),
        (trt_y, trt_ci, result.treatment_sr, "#C74634", "Treatment"),
    ]:
        x_lo, x_hi, x_m = px(ci[0]), px(ci[1]), px(mean_v)
        # CI bar
        lines.append(
            f'<line x1="{x_lo:.1f}" y1="{y_c:.1f}" x2="{x_hi:.1f}" y2="{y_c:.1f}" '
            f'stroke="{color}" stroke-width="3"/>'
        )
        # End ticks
        for xp in [x_lo, x_hi]:
            lines.append(
                f'<line x1="{xp:.1f}" y1="{y_c - ey}" x2="{xp:.1f}" y2="{y_c + ey}" '
                f'stroke="{color}" stroke-width="2"/>'
            )
        # Mean dot
        lines.append(
            f'<circle cx="{x_m:.1f}" cy="{y_c:.1f}" r="5" fill="{color}"/>'
        )
        # Label
        lines.append(
            f'<text x="{pad_l - 8}" y="{y_c + 4:.1f}" text-anchor="end" '
            f'fill="{color}" font-size="12" font-weight="bold">{label}</text>'
        )

    return (f'<svg width="{w}" height="{h}" xmlns="http://www.w3.org/2000/svg">'
            + "".join(lines) + "</svg>")


def _svg_sequential_plot(interims: List[dict], alpha: float) -> str:
    """p-value trajectory across sequential looks with significance threshold."""
    w, h = 560, 180
    pad_l, pad_r, pad_t, pad_b = 55, 20, 20, 45

    n = len(interims)
    p_values = [im["p_value"] for im in interims]
    thresholds = [im["threshold"] for im in interims]

    def xp(i):
        return pad_l + i / (n - 1) * (w - pad_l - pad_r) if n > 1 else (w / 2)

    def yp(v):
        v = max(0.0, min(1.0, v))
        return pad_t + (1 - v) * (h - pad_t - pad_b)

    lines = []
    # Axes
    lines.append(
        f'<line x1="{pad_l}" y1="{h - pad_b}" x2="{w - pad_r}" y2="{h - pad_b}" '
        f'stroke="#475569" stroke-width="1"/>'
    )
    lines.append(
        f'<line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{h - pad_b}" '
        f'stroke="#475569" stroke-width="1"/>'
    )

    # Y-axis ticks
    for v in [0.0, 0.25, 0.5, 0.75, 1.0]:
        yv = yp(v)
        lines.append(
            f'<line x1="{pad_l - 4}" y1="{yv:.1f}" x2="{pad_l}" y2="{yv:.1f}" '
            f'stroke="#475569" stroke-width="1"/>'
        )
        lines.append(
            f'<text x="{pad_l - 8}" y="{yv + 4:.1f}" text-anchor="end" '
            f'fill="#94a3b8" font-size="11">{v:.2f}</text>'
        )

    # X-axis ticks
    for i, im in enumerate(interims):
        xv = xp(i)
        lines.append(
            f'<line x1="{xv:.1f}" y1="{h - pad_b}" x2="{xv:.1f}" y2="{h - pad_b + 4}" '
            f'stroke="#475569" stroke-width="1"/>'
        )
        lines.append(
            f'<text x="{xv:.1f}" y="{h - pad_b + 18}" text-anchor="middle" '
            f'fill="#94a3b8" font-size="11">Look {im["look"]}</text>'
        )
        lines.append(
            f'<text x="{xv:.1f}" y="{h - pad_b + 30}" text-anchor="middle" '
            f'fill="#64748b" font-size="10">n={im["n_per_arm"]}</text>'
        )

    # Significance threshold line (Bonferroni adjusted)
    thresh_y = yp(thresholds[0])
    lines.append(
        f'<line x1="{pad_l}" y1="{thresh_y:.1f}" x2="{w - pad_r}" y2="{thresh_y:.1f}" '
        f'stroke="#f59e0b" stroke-width="1.5" stroke-dasharray="5,3"/>'
    )
    lines.append(
        f'<text x="{w - pad_r + 2}" y="{thresh_y + 4:.1f}" fill="#f59e0b" font-size="10">'
        f'α*</text>'
    )

    # α=0.05 line
    alpha_y = yp(alpha)
    lines.append(
        f'<line x1="{pad_l}" y1="{alpha_y:.1f}" x2="{w - pad_r}" y2="{alpha_y:.1f}" '
        f'stroke="#64748b" stroke-width="1" stroke-dasharray="3,3"/>'
    )

    # p-value polyline
    if n >= 2:
        pts = " ".join(f"{xp(i):.1f},{yp(p):.1f}" for i, p in enumerate(p_values))
        lines.append(
            f'<polyline points="{pts}" fill="none" stroke="#C74634" stroke-width="2"/>'
        )

    # Dots
    for i, p in enumerate(p_values):
        stopped = interims[i]["stopped"]
        color = "#22c55e" if stopped else "#C74634"
        lines.append(
            f'<circle cx="{xp(i):.1f}" cy="{yp(p):.1f}" r="4" fill="{color}"/>'
        )

    return (f'<svg width="{w}" height="{h}" xmlns="http://www.w3.org/2000/svg">'
            + "".join(lines) + "</svg>")


def render_html_report(config: ABTestConfig, result: ABTestResult,
                       interims: List[dict]) -> str:
    rec_color = _rec_color(result.recommendation)
    rec_label = _rec_label(result.recommendation)
    rec_expl = _rec_explanation(result)
    ci_svg = _svg_ci_plot(result)
    seq_svg = _svg_sequential_plot(interims, config.significance_level)

    chi2_stat_approx = (
        f"{(result.sr_diff ** 2 / max(result.control_sr * (1 - result.control_sr) / result.control_n + result.treatment_sr * (1 - result.treatment_sr) / result.treatment_n, 1e-9)):.3f}"
        if result.control_n else "N/A"
    )
    effect_size = abs(result.sr_diff)
    n_needed = _sample_size_for_power(result.control_sr, config.min_detectable_effect)

    p_fmt = f"{result.p_value:.4f}"
    ci_lo, ci_hi = result.confidence_interval_95

    kpi_cards = [
        ("Control SR", f"{result.control_sr:.1%}", f"n={result.control_n}"),
        ("Treatment SR", f"{result.treatment_sr:.1%}", f"n={result.treatment_n}"),
        ("SR Difference", f"{result.sr_diff:+.1%}",
         f"{result.relative_improvement_pct:.1f}% relative"),
        ("p-value", p_fmt, "significant" if result.significant else "not significant"),
    ]

    cards_html = ""
    for title, val, sub in kpi_cards:
        cards_html += f"""
        <div class="kpi-card">
            <div class="kpi-title">{title}</div>
            <div class="kpi-value">{val}</div>
            <div class="kpi-sub">{sub}</div>
        </div>"""

    rows = [
        ("Chi-square statistic (approx)", chi2_stat_approx),
        ("p-value", p_fmt),
        ("Effect size (|Δ SR|)", f"{effect_size:.3f}"),
        ("Estimated power", f"{result.power:.1%}"),
        ("95% CI for Δ SR", f"[{ci_lo:+.3f}, {ci_hi:+.3f}]"),
        ("Control model", config.control_model),
        ("Treatment model", config.treatment_model),
        ("Episodes per arm", str(config.n_episodes_per_arm)),
        ("Significance level (α)", str(config.significance_level)),
        ("Recommendation", result.recommendation.upper()),
    ]
    table_rows = "".join(
        f"<tr><td>{k}</td><td><strong>{v}</strong></td></tr>" for k, v in rows
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>A/B Policy Test — {config.test_id}</title>
<style>
  :root {{
    --bg: #1e293b; --card: #0f172a; --border: #334155;
    --text: #e2e8f0; --muted: #94a3b8; --red: #C74634;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: var(--bg); color: var(--text); font-family: 'Segoe UI', system-ui, sans-serif; padding: 2rem; }}
  h1 {{ color: var(--red); font-size: 1.6rem; margin-bottom: 0.25rem; }}
  .subtitle {{ color: var(--muted); font-size: 0.9rem; margin-bottom: 2rem; }}
  .banner {{ border-radius: 10px; padding: 1.5rem 2rem; margin-bottom: 2rem;
             border-left: 6px solid {rec_color}; background: var(--card); }}
  .banner-rec {{ font-size: 1.8rem; font-weight: 800; color: {rec_color}; margin-bottom: 0.5rem; }}
  .banner-expl {{ color: var(--muted); font-size: 0.95rem; line-height: 1.6; }}
  .kpi-row {{ display: flex; gap: 1rem; margin-bottom: 2rem; flex-wrap: wrap; }}
  .kpi-card {{ flex: 1; min-width: 120px; background: var(--card); border: 1px solid var(--border);
               border-radius: 8px; padding: 1rem 1.2rem; }}
  .kpi-title {{ color: var(--muted); font-size: 0.75rem; text-transform: uppercase;
                letter-spacing: 0.05em; margin-bottom: 0.25rem; }}
  .kpi-value {{ font-size: 1.6rem; font-weight: 700; color: var(--text); }}
  .kpi-sub {{ color: var(--muted); font-size: 0.75rem; margin-top: 0.2rem; }}
  .section {{ background: var(--card); border: 1px solid var(--border); border-radius: 8px;
              padding: 1.25rem 1.5rem; margin-bottom: 1.5rem; }}
  .section h2 {{ color: var(--red); font-size: 1rem; margin-bottom: 1rem; text-transform: uppercase;
                 letter-spacing: 0.05em; }}
  table {{ width: 100%; border-collapse: collapse; }}
  th, td {{ padding: 0.5rem 0.75rem; border-bottom: 1px solid var(--border); text-align: left; }}
  th {{ color: var(--muted); font-size: 0.8rem; text-transform: uppercase; }}
  td {{ font-size: 0.9rem; }}
  tr:last-child td {{ border-bottom: none; }}
  .sample-calc {{ color: var(--muted); font-size: 0.9rem; line-height: 1.7; }}
  .sample-calc strong {{ color: var(--text); }}
  footer {{ color: var(--muted); font-size: 0.75rem; text-align: center; margin-top: 2rem; }}
</style>
</head>
<body>
<h1>OCI Robot Cloud — A/B Policy Test</h1>
<div class="subtitle">Test ID: {config.test_id} &nbsp;|&nbsp; Task: {config.task}
  &nbsp;|&nbsp; Started: {config.started_at[:19]} UTC</div>

<div class="banner">
  <div class="banner-rec">{rec_label}</div>
  <div class="banner-expl">{rec_expl}</div>
</div>

<div class="kpi-row">{cards_html}</div>

<div class="section">
  <h2>Confidence Intervals (95%, Wilson score)</h2>
  {ci_svg}
  <p style="color:var(--muted);font-size:0.8rem;margin-top:0.5rem;">
    Horizontal bars show 95% CI for each arm's SR. Dot = observed SR. Dashed line = control SR reference.
  </p>
</div>

<div class="section">
  <h2>Sequential Test — p-value over Interim Looks</h2>
  {seq_svg}
  <p style="color:var(--muted);font-size:0.8rem;margin-top:0.5rem;">
    Orange dashed = Bonferroni-adjusted threshold (α/{config.n_episodes_per_arm // max(len(interims),1) * len(interims)}).
    Green dot = early-stop triggered.
  </p>
</div>

<div class="section">
  <h2>Statistics Summary</h2>
  <table>
    <thead><tr><th>Metric</th><th>Value</th></tr></thead>
    <tbody>{table_rows}</tbody>
  </table>
</div>

<div class="section">
  <h2>Sample Size Calculator</h2>
  <div class="sample-calc">
    To detect a <strong>{config.min_detectable_effect:.0%}</strong> absolute improvement
    over control baseline of <strong>{result.control_sr:.1%}</strong>
    with <strong>80% power</strong> at α = {config.significance_level},
    you need <strong>{n_needed} episodes per arm</strong>
    ({n_needed * 2} total).<br><br>
    Current study: <strong>{config.n_episodes_per_arm}</strong> episodes per arm.
    {'&#x2705; Adequately powered.' if config.n_episodes_per_arm >= n_needed else '&#x26A0;&#xFE0F; Underpowered — consider increasing n.'}
  </div>
</div>

<footer>OCI Robot Cloud &nbsp;|&nbsp; GR00T Fine-tuning Pipeline &nbsp;|&nbsp; Oracle Confidential</footer>
</body>
</html>"""


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="A/B policy promotion test for GR00T")
    parser.add_argument("--mock", action="store_true",
                        help="Simulate test (no GPU/live server required)")
    parser.add_argument("--control", default="BC-1000",
                        help="Control model name (default: BC-1000)")
    parser.add_argument("--treatment", default="DAgger-run9",
                        help="Treatment model name (default: DAgger-run9)")
    parser.add_argument("--n", type=int, default=50,
                        help="Episodes per arm (default: 50)")
    parser.add_argument("--task", default="pick_and_place",
                        help="Task name (default: pick_and_place)")
    parser.add_argument("--alpha", type=float, default=0.05,
                        help="Significance level (default: 0.05)")
    parser.add_argument("--mde", type=float, default=0.10,
                        help="Min detectable effect (default: 0.10)")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--interim", type=int, default=5,
                        help="Number of interim looks for sequential test (default: 5)")
    parser.add_argument("--output", default="/tmp/ab_policy_test.html",
                        help="Output HTML report path")
    args = parser.parse_args()

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    config = ABTestConfig(
        test_id=f"ab_{args.control}_vs_{args.treatment}_{ts}",
        control_model=args.control,
        treatment_model=args.treatment,
        n_episodes_per_arm=args.n,
        significance_level=args.alpha,
        min_detectable_effect=args.mde,
        task=args.task,
        started_at=datetime.utcnow().isoformat(),
    )

    if not args.mock:
        print("[INFO] Live mode not yet wired to episode runners — falling back to mock.")

    print(f"[ab_policy_test] Running A/B test: {config.control_model} vs {config.treatment_model}")
    print(f"                 {config.n_episodes_per_arm} episodes per arm, seed={args.seed}")

    result = run_ab_test(config, seed=args.seed)
    interims, _ = sequential_test(config, n_interim=args.interim, seed=args.seed)

    print(f"\n--- Results ---")
    print(f"Control   SR : {result.control_sr:.1%}  (n={result.control_n})")
    print(f"Treatment SR : {result.treatment_sr:.1%}  (n={result.treatment_n})")
    print(f"Δ SR         : {result.sr_diff:+.1%}  ({result.relative_improvement_pct:.1f}% relative)")
    print(f"p-value      : {result.p_value:.4f}  ({'significant' if result.significant else 'not significant'})")
    print(f"Power        : {result.power:.1%}")
    print(f"95% CI (Δ)   : [{result.confidence_interval_95[0]:+.3f}, {result.confidence_interval_95[1]:+.3f}]")
    print(f"Recommendation: {result.recommendation.upper()}")

    html = render_html_report(config, result, interims)
    with open(args.output, "w", encoding="utf-8") as fh:
        fh.write(html)
    print(f"\n[ab_policy_test] HTML report saved to {args.output}")


if __name__ == "__main__":
    main()
