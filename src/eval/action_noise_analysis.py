#!/usr/bin/env python3
"""action_noise_analysis.py — Analyze noise characteristics of GR00T action predictions.

Distinguishes aleatoric uncertainty (inherent task ambiguity) from epistemic
uncertainty (model uncertainty) and measures how noise affects success rate.

Usage:
    python action_noise_analysis.py --mock --n-episodes 100 --output /tmp/action_noise.html
"""

import argparse
import math
import random
import statistics
import time
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class NoiseProfile:
    """Per-joint noise characteristics from GR00T action predictions."""
    joint_idx: int
    joint_name: str
    aleatoric_std: float        # Inherent task ambiguity (irreducible)
    epistemic_std: float        # Model uncertainty (reducible with more data)
    total_std: float            # Combined: sqrt(aleatoric^2 + epistemic^2)
    snr_db: float               # Signal-to-noise ratio in dB
    noise_type: str             # "structured" | "gaussian" | "outlier"


@dataclass
class EpisodeNoiseResult:
    """Per-episode noise and outcome summary."""
    episode_id: int
    success: bool
    mean_action_std: float      # Mean std across all joints in this episode
    max_action_std: float       # Max std across joints in this episode
    noise_dominant_joint: int   # Index of joint with highest noise
    aleatoric_ratio: float      # Fraction of total variance that is aleatoric (0-1)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DOF = 9  # 7 arm joints + 2 gripper
JOINT_NAMES = [
    "shoulder_pan", "shoulder_lift", "elbow",
    "wrist_1", "wrist_2", "wrist_3",
    "wrist_rotate", "gripper_left", "gripper_right",
]

# Grasp joints (indices 5, 6 → wrist_3 + wrist_rotate) and gripper (7, 8)
# have highest aleatoric noise due to contact ambiguity.
# We map "grasp" concern to indices 5,6 per spec; gripper = 7,8.
HIGH_ALEATORIC_JOINTS = {5, 6, 7, 8}

# Typical mean action magnitudes (radians / m) per joint for the LIBERO cube task
JOINT_SIGNAL_MEAN = [0.45, 0.38, 0.52, 0.30, 0.25, 0.18, 0.15, 0.40, 0.40]


# ---------------------------------------------------------------------------
# Core math helpers
# ---------------------------------------------------------------------------

def compute_snr(signal_mean: float, noise_std: float) -> float:
    """Return SNR in dB = 20 * log10(|signal_mean| / noise_std).

    Returns -999.0 if noise_std is effectively zero or signal_mean is zero.
    """
    if noise_std < 1e-12 or abs(signal_mean) < 1e-12:
        return -999.0 if noise_std >= abs(signal_mean) else 999.0
    return 20.0 * math.log10(abs(signal_mean) / noise_std)


def _classify_noise_type(aleatoric_std: float, epistemic_std: float,
                         joint_idx: int, rng: random.Random) -> str:
    """Heuristic classification of dominant noise mode."""
    ratio = aleatoric_std / (epistemic_std + 1e-12)
    if joint_idx in HIGH_ALEATORIC_JOINTS:
        return "structured"   # contact / grasp ambiguity → structured bimodal
    if ratio > 2.0:
        return "gaussian"     # aleatoric dominated → additive Gaussian
    if rng.random() < 0.15:
        return "outlier"      # occasional policy mode-switching
    return "gaussian"


# ---------------------------------------------------------------------------
# MC Dropout simulation
# ---------------------------------------------------------------------------

def monte_carlo_dropout(
    n_samples: int = 20,
    seed: int = 42,
    checkpoint: Optional[str] = None,
) -> dict:
    """Simulate MC Dropout inference to estimate epistemic uncertainty.

    In a real deployment this would run the model N times with dropout
    layers active and measure variance across forward passes.  Here we
    synthesise plausible variance values consistent with GR00T on LIBERO.

    Returns a dict keyed by joint index with list of per-sample std values,
    plus 'mean_epistemic_std' and 'variance_across_samples'.
    """
    rng = random.Random(seed)
    is_lora = checkpoint is not None and "lora" in checkpoint.lower()

    results: dict = {"samples": {}, "mean_epistemic_std": [], "variance_across_samples": []}

    for joint_idx in range(DOF):
        # LoRA fine-tuned models constrain weight updates → lower epistemic noise
        base_epistemic = 0.018 if is_lora else 0.032
        if joint_idx in HIGH_ALEATORIC_JOINTS:
            base_epistemic *= 0.85  # grasp joints are well-trained

        samples = []
        for _ in range(n_samples):
            # Each "dropout" pass yields a slightly different std estimate
            draw = base_epistemic + rng.gauss(0, base_epistemic * 0.25)
            samples.append(max(1e-6, draw))

        results["samples"][joint_idx] = samples
        results["mean_epistemic_std"].append(statistics.mean(samples))
        results["variance_across_samples"].append(statistics.variance(samples))

    return results


# ---------------------------------------------------------------------------
# Main analysis
# ---------------------------------------------------------------------------

def analyze_noise_profiles(
    checkpoint: Optional[str] = None,
    seed: int = 42,
) -> list[NoiseProfile]:
    """Analyse per-joint noise for a GR00T checkpoint.

    Steps
    -----
    1. Run MC dropout to get epistemic_std per joint.
    2. Estimate aleatoric_std from residual variance after marginalising
       over model weights (transformer_variance = epistemic, residual = aleatoric).
    3. Combine: total_std = sqrt(aleatoric^2 + epistemic^2).
    4. Compute SNR using per-joint signal mean.
    5. Classify noise type.
    """
    rng = random.Random(seed)
    mc = monte_carlo_dropout(n_samples=20, seed=seed, checkpoint=checkpoint)

    is_lora = checkpoint is not None and "lora" in checkpoint.lower()

    profiles: list[NoiseProfile] = []
    for joint_idx in range(DOF):
        epistemic_std = mc["mean_epistemic_std"][joint_idx]

        # Aleatoric: higher for grasp joints (contact ambiguity in cube lifting)
        if joint_idx in {5, 6}:            # wrist joints near grasp
            base_aleatoric = rng.gauss(0.055, 0.008)
        elif joint_idx in {7, 8}:           # gripper fingers
            base_aleatoric = rng.gauss(0.062, 0.010)
        else:
            base_aleatoric = rng.gauss(0.025, 0.006)

        aleatoric_std = max(1e-6, abs(base_aleatoric))

        # LoRA reduces epistemic but cannot reduce aleatoric
        if is_lora:
            epistemic_std *= 0.60

        total_std = math.sqrt(aleatoric_std ** 2 + epistemic_std ** 2)
        snr = compute_snr(JOINT_SIGNAL_MEAN[joint_idx], total_std)
        noise_type = _classify_noise_type(aleatoric_std, epistemic_std, joint_idx, rng)

        profiles.append(NoiseProfile(
            joint_idx=joint_idx,
            joint_name=JOINT_NAMES[joint_idx],
            aleatoric_std=round(aleatoric_std, 6),
            epistemic_std=round(epistemic_std, 6),
            total_std=round(total_std, 6),
            snr_db=round(snr, 2),
            noise_type=noise_type,
        ))

    return profiles


# ---------------------------------------------------------------------------
# Episode-level simulation
# ---------------------------------------------------------------------------

def _simulate_episodes(
    n_episodes: int,
    profiles: list[NoiseProfile],
    seed: int = 42,
) -> list[EpisodeNoiseResult]:
    """Generate synthetic episode outcomes driven by noise profiles."""
    rng = random.Random(seed + 1)
    results: list[EpisodeNoiseResult] = []

    mean_total = statistics.mean(p.total_std for p in profiles)
    max_total = max(p.total_std for p in profiles)

    for ep_id in range(n_episodes):
        # Per-episode noise is sampled around profile means with run-to-run variability
        ep_stds = [
            max(1e-6, rng.gauss(p.total_std, p.total_std * 0.15))
            for p in profiles
        ]
        ep_mean_std = statistics.mean(ep_stds)
        ep_max_std = max(ep_stds)
        dominant = ep_stds.index(ep_max_std)

        aleatoric_var = sum(p.aleatoric_std ** 2 for p in profiles)
        total_var = sum(p.total_std ** 2 for p in profiles)
        aleatoric_ratio = aleatoric_var / total_var if total_var > 1e-12 else 0.5

        # Success probability inversely related to noise level
        noise_penalty = (ep_mean_std - mean_total) / (mean_total + 1e-12)
        p_success = max(0.02, min(0.95, 0.62 - noise_penalty * 3.0))
        success = rng.random() < p_success

        results.append(EpisodeNoiseResult(
            episode_id=ep_id,
            success=success,
            mean_action_std=round(ep_mean_std, 6),
            max_action_std=round(ep_max_std, 6),
            noise_dominant_joint=dominant,
            aleatoric_ratio=round(aleatoric_ratio, 4),
        ))

    return results


# ---------------------------------------------------------------------------
# Correlation
# ---------------------------------------------------------------------------

def find_noise_failure_correlation(episodes: list[EpisodeNoiseResult]) -> float:
    """Return Pearson r between episode noise level and failure probability.

    failure = 1 if not success, 0 otherwise.
    noise   = mean_action_std.
    """
    n = len(episodes)
    if n < 2:
        return 0.0

    xs = [ep.mean_action_std for ep in episodes]
    ys = [0.0 if ep.success else 1.0 for ep in episodes]

    mean_x = sum(xs) / n
    mean_y = sum(ys) / n

    cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    std_x = math.sqrt(sum((x - mean_x) ** 2 for x in xs))
    std_y = math.sqrt(sum((y - mean_y) ** 2 for y in ys))

    if std_x < 1e-12 or std_y < 1e-12:
        return 0.0

    return round(cov / (std_x * std_y), 4)


# ---------------------------------------------------------------------------
# HTML report
# ---------------------------------------------------------------------------

def render_html(
    profiles: list[NoiseProfile],
    episodes: list[EpisodeNoiseResult],
    correlation: float,
) -> str:
    """Render a dark-themed HTML report with noise breakdown charts."""

    success_count = sum(1 for ep in episodes if ep.success)
    success_rate = success_count / len(episodes) if episodes else 0.0
    mean_noise = statistics.mean(ep.mean_action_std for ep in episodes)
    mean_aleatoric_ratio = statistics.mean(ep.aleatoric_ratio for ep in episodes)

    # ---- stacked bar data (aleatoric vs epistemic) -------------------------
    bar_labels = [f'J{p.joint_idx}<br>{p.joint_name[:7]}' for p in profiles]
    ale_vals = [p.aleatoric_std for p in profiles]
    epi_vals = [p.epistemic_std for p in profiles]
    snr_vals = [p.snr_db for p in profiles]

    max_bar = max(a + e for a, e in zip(ale_vals, epi_vals)) or 1.0

    def bar_px(val, total=max_bar, width=220):
        return max(2, int(val / total * width))

    bars_html = ""
    for i, p in enumerate(profiles):
        ale_w = bar_px(ale_vals[i])
        epi_w = bar_px(epi_vals[i])
        snr_color = "#22c55e" if p.snr_db > 18 else ("#f59e0b" if p.snr_db > 10 else "#ef4444")
        bars_html += f"""
        <tr>
          <td class="jname">{p.joint_name}</td>
          <td><div class="bar-wrap">
            <div class="bar ale" style="width:{ale_w}px" title="Aleatoric {p.aleatoric_std:.4f}"></div>
            <div class="bar epi" style="width:{epi_w}px" title="Epistemic {p.epistemic_std:.4f}"></div>
          </div></td>
          <td class="val">{p.total_std:.4f}</td>
          <td><span class="snr" style="color:{snr_color}">{p.snr_db:.1f} dB</span></td>
          <td><span class="badge {p.noise_type}">{p.noise_type}</span></td>
        </tr>"""

    # ---- scatter data (noise vs failure) ----------------------------------
    scatter_pts = []
    for ep in episodes[:200]:   # cap to keep HTML small
        colour = "#ef4444" if not ep.success else "#22c55e"
        scatter_pts.append((ep.mean_action_std, int(not ep.success), colour))

    # Normalise scatter to SVG coords 400×200
    if scatter_pts:
        xs = [p[0] for p in scatter_pts]
        min_x, max_x = min(xs), max(xs)
        range_x = max_x - min_x or 1e-6
        circles = ""
        for x_val, y_val, colour in scatter_pts:
            cx = 30 + (x_val - min_x) / range_x * 360
            cy = 170 - y_val * 130
            circles += f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="3" fill="{colour}" opacity="0.7"/>'
    else:
        circles = ""

    # ---- MC dropout variance per joint ------------------------------------
    mc_bars = ""
    max_mc = max(p.epistemic_std for p in profiles) or 1.0
    for p in profiles:
        w = int(p.epistemic_std / max_mc * 180)
        mc_bars += f"""
        <tr>
          <td class="jname">{p.joint_name}</td>
          <td><div class="bar-wrap">
            <div class="bar epi" style="width:{max(2,w)}px"></div>
          </div></td>
          <td class="val">{p.epistemic_std:.5f}</td>
        </tr>"""

    # ---- recommendations --------------------------------------------------
    recs = []
    if mean_aleatoric_ratio > 0.6:
        recs.append("Aleatoric uncertainty dominates — collect more diverse demonstrations around grasp contacts to reduce task ambiguity.")
    else:
        recs.append("Epistemic uncertainty is significant — increase training data or use LoRA fine-tuning to reduce model uncertainty.")
    if correlation > 0.3:
        recs.append(f"Strong noise-failure correlation (r={correlation:.2f}) — implement noise-aware action smoothing or ensemble averaging.")
    for p in profiles:
        if p.snr_db < 10:
            recs.append(f"Joint <b>{p.joint_name}</b> has critically low SNR ({p.snr_db:.1f} dB) — consider dedicated per-joint data augmentation.")
            break

    recs_html = "".join(f"<li>{r}</li>" for r in recs)

    timestamp = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>GR00T Action Noise Analysis</title>
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; font-size: 14px; padding: 24px; }}
  h1 {{ font-size: 22px; color: #f8fafc; margin-bottom: 4px; }}
  .subtitle {{ color: #64748b; margin-bottom: 28px; font-size: 12px; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px; margin-bottom: 28px; }}
  .card {{ background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 18px; }}
  .card .label {{ color: #94a3b8; font-size: 11px; text-transform: uppercase; letter-spacing: .06em; margin-bottom: 6px; }}
  .card .value {{ font-size: 26px; font-weight: 700; color: #f1f5f9; }}
  .card .sub {{ font-size: 11px; color: #64748b; margin-top: 4px; }}
  section {{ background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 20px; margin-bottom: 24px; }}
  section h2 {{ font-size: 15px; color: #cbd5e1; margin-bottom: 16px; border-bottom: 1px solid #334155; padding-bottom: 8px; }}
  table {{ width: 100%; border-collapse: collapse; }}
  th {{ text-align: left; color: #64748b; font-size: 11px; text-transform: uppercase; padding: 0 0 8px 0; }}
  td {{ padding: 5px 0; vertical-align: middle; }}
  .jname {{ color: #94a3b8; width: 110px; font-size: 12px; }}
  .val {{ color: #cbd5e1; text-align: right; padding-right: 12px; font-variant-numeric: tabular-nums; font-size: 12px; }}
  .bar-wrap {{ display: flex; align-items: center; gap: 2px; }}
  .bar {{ height: 14px; border-radius: 3px; }}
  .ale {{ background: #f59e0b; }}
  .epi {{ background: #6366f1; }}
  .snr {{ font-weight: 600; font-size: 12px; }}
  .badge {{ display: inline-block; padding: 2px 7px; border-radius: 4px; font-size: 10px; font-weight: 600; text-transform: uppercase; }}
  .badge.structured {{ background: #1e3a5f; color: #60a5fa; }}
  .badge.gaussian   {{ background: #1a3728; color: #34d399; }}
  .badge.outlier    {{ background: #3b1a1a; color: #f87171; }}
  .legend {{ display: flex; gap: 16px; margin-bottom: 12px; font-size: 12px; color: #94a3b8; }}
  .legend span {{ display: inline-flex; align-items: center; gap: 5px; }}
  .swatch {{ width: 12px; height: 12px; border-radius: 2px; }}
  svg {{ background: #0f172a; border-radius: 6px; width: 100%; }}
  .axis-label {{ font: 10px sans-serif; fill: #64748b; }}
  .corr-badge {{ display: inline-block; background: #1e293b; border: 1px solid #334155; border-radius: 6px; padding: 4px 10px; font-size: 13px; color: #f1f5f9; margin-bottom: 12px; }}
  ul.recs {{ padding-left: 18px; }}
  ul.recs li {{ margin-bottom: 8px; color: #cbd5e1; line-height: 1.5; }}
  footer {{ color: #334155; font-size: 11px; margin-top: 20px; text-align: center; }}
</style>
</head>
<body>

<h1>GR00T Action Noise Analysis</h1>
<div class="subtitle">Generated {timestamp} &nbsp;|&nbsp; {DOF} DOF (7 arm + 2 gripper) &nbsp;|&nbsp; {len(episodes)} episodes</div>

<div class="grid">
  <div class="card">
    <div class="label">Success Rate</div>
    <div class="value">{success_rate*100:.1f}%</div>
    <div class="sub">{success_count} / {len(episodes)} episodes</div>
  </div>
  <div class="card">
    <div class="label">Mean Action Noise</div>
    <div class="value">{mean_noise:.4f}</div>
    <div class="sub">std across joints</div>
  </div>
  <div class="card">
    <div class="label">Aleatoric Ratio</div>
    <div class="value">{mean_aleatoric_ratio*100:.0f}%</div>
    <div class="sub">of total variance</div>
  </div>
  <div class="card">
    <div class="label">Noise-Failure r</div>
    <div class="value">{correlation:+.3f}</div>
    <div class="sub">Pearson correlation</div>
  </div>
</div>

<section>
  <h2>Per-Joint Noise Breakdown — Aleatoric vs Epistemic</h2>
  <div class="legend">
    <span><div class="swatch" style="background:#f59e0b"></div> Aleatoric (task ambiguity)</span>
    <span><div class="swatch" style="background:#6366f1"></div> Epistemic (model uncertainty)</span>
  </div>
  <table>
    <thead><tr>
      <th>Joint</th>
      <th>Std breakdown</th>
      <th style="text-align:right;padding-right:12px">Total σ</th>
      <th>SNR</th>
      <th>Type</th>
    </tr></thead>
    <tbody>{bars_html}</tbody>
  </table>
</section>

<section>
  <h2>Noise vs Success — Episode Scatter (n={min(200,len(episodes))} shown)</h2>
  <div class="legend">
    <span><div class="swatch" style="background:#22c55e"></div> Success</span>
    <span><div class="swatch" style="background:#ef4444"></div> Failure</span>
  </div>
  <div class="corr-badge">Pearson r = {correlation:+.3f}</div>
  <svg viewBox="0 0 400 200" height="200">
    <line x1="30" y1="20" x2="30" y2="175" stroke="#334155" stroke-width="1"/>
    <line x1="30" y1="175" x2="395" y2="175" stroke="#334155" stroke-width="1"/>
    <text x="10" y="48" class="axis-label" transform="rotate(-90,10,48)" text-anchor="middle">Failure</text>
    <text x="10" y="155" class="axis-label" transform="rotate(-90,10,155)" text-anchor="middle">Success</text>
    <text x="210" y="195" class="axis-label" text-anchor="middle">Mean Action Std →</text>
    {circles}
  </svg>
</section>

<section>
  <h2>MC Dropout — Epistemic Variance per Joint</h2>
  <div class="legend">
    <span><div class="swatch" style="background:#6366f1"></div> Epistemic σ (20 dropout passes)</span>
  </div>
  <table>
    <thead><tr>
      <th>Joint</th>
      <th>Epistemic σ distribution</th>
      <th style="text-align:right;padding-right:12px">σ</th>
    </tr></thead>
    <tbody>{mc_bars}</tbody>
  </table>
</section>

<section>
  <h2>Recommendations</h2>
  <ul class="recs">{recs_html}</ul>
</section>

<footer>OCI Robot Cloud · GR00T N1.6 · Action Noise Analysis Report</footer>
</body>
</html>"""


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Analyze GR00T action prediction noise (aleatoric vs epistemic)."
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use synthetic data instead of live inference.",
    )
    parser.add_argument(
        "--checkpoint",
        default=None,
        help="Path to GR00T checkpoint (influences LoRA vs full-FT noise profile).",
    )
    parser.add_argument(
        "--n-episodes",
        type=int,
        default=100,
        help="Number of episodes to simulate (default: 100).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducibility (default: 42).",
    )
    parser.add_argument(
        "--output",
        default="/tmp/action_noise.html",
        help="Output HTML path (default: /tmp/action_noise.html).",
    )
    args = parser.parse_args()

    if not args.mock and args.checkpoint is None:
        print("[warn] No --checkpoint provided; running in mock mode.")
        args.mock = True

    print(f"[1/4] Analyzing noise profiles (seed={args.seed}) ...")
    profiles = analyze_noise_profiles(checkpoint=args.checkpoint, seed=args.seed)

    print(f"[2/4] Simulating {args.n_episodes} episodes ...")
    episodes = _simulate_episodes(args.n_episodes, profiles, seed=args.seed)

    print("[3/4] Computing noise-failure correlation ...")
    correlation = find_noise_failure_correlation(episodes)
    success_rate = sum(1 for ep in episodes if ep.success) / len(episodes)
    print(f"      Pearson r = {correlation:+.4f} | Success rate = {success_rate*100:.1f}%")

    print("[4/4] Rendering HTML report ...")
    html = render_html(profiles, episodes, correlation)
    with open(args.output, "w", encoding="utf-8") as fh:
        fh.write(html)
    print(f"      Report saved → {args.output}")

    # Summary table
    print("\nNoise Profile Summary:")
    print(f"  {'Joint':<15} {'Aleatoric σ':>12} {'Epistemic σ':>12} {'Total σ':>10} {'SNR':>8} {'Type'}")
    print("  " + "-" * 65)
    for p in profiles:
        print(
            f"  {p.joint_name:<15} {p.aleatoric_std:>12.5f} {p.epistemic_std:>12.5f}"
            f" {p.total_std:>10.5f} {p.snr_db:>7.1f}  {p.noise_type}"
        )


if __name__ == "__main__":
    main()
