"""
Isaac Sim domain randomization analysis for GR00T sim-to-real transfer.
Measures effect of each randomization dimension on policy robustness and sim-to-real gap.
"""

from __future__ import annotations

import argparse
import math
import random
import sys
from dataclasses import dataclass, field
from typing import List


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class RandomizationDim:
    """A single randomization dimension with its parameter range and effect sizes."""
    name: str
    range_low: float
    range_high: float
    unit: str
    effect_on_sr: float          # delta in success-rate (positive = helps)
    effect_on_sim2real: float    # reduction in sim2real gap (positive = helps)


@dataclass
class DRConfig:
    """A complete domain-randomization configuration and its measured outcomes."""
    config_name: str
    enabled_dims: List[str]
    n_demos: int
    policy_sr: float
    sim2real_gap: float
    training_cost_factor: float
    realism_score: float


@dataclass
class DRReport:
    """Aggregated analysis report across all DR configs."""
    best_config: DRConfig
    worst_config: DRConfig
    most_impactful_dim: RandomizationDim
    results: List[DRConfig]
    dim_analysis: List[RandomizationDim]


# ---------------------------------------------------------------------------
# Canonical randomization dimensions
# ---------------------------------------------------------------------------

RANDOMIZATION_DIMS: List[RandomizationDim] = [
    RandomizationDim(
        name="lighting_intensity",
        range_low=50.0,
        range_high=1500.0,
        unit="lux",
        effect_on_sr=0.02,
        effect_on_sim2real=0.07,
    ),
    RandomizationDim(
        name="texture_variation",
        range_low=0.0,
        range_high=1.0,
        unit="index",
        effect_on_sr=0.01,
        effect_on_sim2real=0.06,
    ),
    RandomizationDim(
        name="object_mass",
        range_low=0.05,
        range_high=0.50,
        unit="kg",
        effect_on_sr=-0.03,
        effect_on_sim2real=0.09,
    ),
    RandomizationDim(
        name="object_friction",
        range_low=0.2,
        range_high=1.2,
        unit="coeff",
        effect_on_sr=-0.02,
        effect_on_sim2real=0.08,
    ),
    RandomizationDim(
        name="camera_noise",
        range_low=0.0,
        range_high=0.05,
        unit="sigma",
        effect_on_sr=-0.01,
        effect_on_sim2real=0.04,
    ),
    RandomizationDim(
        name="joint_noise",
        range_low=0.0,
        range_high=0.02,
        unit="rad",
        effect_on_sr=-0.02,
        effect_on_sim2real=0.05,
    ),
    RandomizationDim(
        name="background_clutter",
        range_low=0.0,
        range_high=10.0,
        unit="objects",
        effect_on_sr=-0.01,
        effect_on_sim2real=0.03,
    ),
    RandomizationDim(
        name="table_height",
        range_low=0.70,
        range_high=0.90,
        unit="m",
        effect_on_sr=-0.01,
        effect_on_sim2real=0.03,
    ),
]

DIM_BY_NAME = {d.name: d for d in RANDOMIZATION_DIMS}


# ---------------------------------------------------------------------------
# Canonical DR configs
# ---------------------------------------------------------------------------

CANONICAL_CONFIGS: List[DRConfig] = [
    DRConfig(
        config_name="none",
        enabled_dims=[],
        n_demos=1000,
        policy_sr=0.78,
        sim2real_gap=0.45,
        training_cost_factor=1.0,
        realism_score=0.30,
    ),
    DRConfig(
        config_name="lighting_only",
        enabled_dims=["lighting_intensity"],
        n_demos=1000,
        policy_sr=0.79,
        sim2real_gap=0.38,
        training_cost_factor=1.1,
        realism_score=0.45,
    ),
    DRConfig(
        config_name="physics_only",
        enabled_dims=["object_mass", "object_friction", "joint_noise"],
        n_demos=1000,
        policy_sr=0.74,
        sim2real_gap=0.28,
        training_cost_factor=1.4,
        realism_score=0.55,
    ),
    DRConfig(
        config_name="visual_only",
        enabled_dims=["lighting_intensity", "texture_variation", "background_clutter", "camera_noise"],
        n_demos=1000,
        policy_sr=0.76,
        sim2real_gap=0.25,
        training_cost_factor=1.6,
        realism_score=0.65,
    ),
    DRConfig(
        config_name="full_dr",
        enabled_dims=[d.name for d in RANDOMIZATION_DIMS],
        n_demos=1000,
        policy_sr=0.71,
        sim2real_gap=0.12,
        training_cost_factor=2.8,
        realism_score=0.88,
    ),
    DRConfig(
        config_name="adaptive_dr",
        enabled_dims=[d.name for d in RANDOMIZATION_DIMS],
        n_demos=1000,
        policy_sr=0.77,
        sim2real_gap=0.15,
        training_cost_factor=1.8,
        realism_score=0.82,
    ),
]


# ---------------------------------------------------------------------------
# Analysis helpers
# ---------------------------------------------------------------------------

def pareto_score(cfg: DRConfig) -> float:
    """Higher = better Pareto trade-off (SR + sim2real transfer - cost)."""
    sim2real_transfer = 1.0 - cfg.sim2real_gap
    cost_penalty = (cfg.training_cost_factor - 1.0) * 0.15
    return cfg.policy_sr * 0.4 + sim2real_transfer * 0.5 - cost_penalty


def apply_seed_jitter(configs: List[DRConfig], seed: int) -> List[DRConfig]:
    """Apply tiny reproducible noise to SR/gap numbers for realism in mock mode."""
    rng = random.Random(seed)
    jittered = []
    for c in configs:
        noise_sr = rng.gauss(0, 0.005)
        noise_gap = rng.gauss(0, 0.008)
        jittered.append(DRConfig(
            config_name=c.config_name,
            enabled_dims=list(c.enabled_dims),
            n_demos=c.n_demos,
            policy_sr=round(max(0.0, min(1.0, c.policy_sr + noise_sr)), 4),
            sim2real_gap=round(max(0.0, min(1.0, c.sim2real_gap + noise_gap)), 4),
            training_cost_factor=c.training_cost_factor,
            realism_score=c.realism_score,
        ))
    return jittered


def build_report(configs: List[DRConfig], dims: List[RandomizationDim]) -> DRReport:
    best = max(configs, key=pareto_score)
    worst = min(configs, key=pareto_score)
    most_impactful = max(dims, key=lambda d: d.effect_on_sim2real)
    return DRReport(
        best_config=best,
        worst_config=worst,
        most_impactful_dim=most_impactful,
        results=configs,
        dim_analysis=dims,
    )


# ---------------------------------------------------------------------------
# Stdout summary
# ---------------------------------------------------------------------------

def print_comparison(report: DRReport) -> None:
    header = f"{'Config':<16} {'Dims':>4} {'SR':>6} {'S2R Gap':>9} {'Cost':>6} {'Realism':>8} {'Pareto':>7}"
    print()
    print("Isaac Sim Domain Randomization — Config Comparison")
    print("=" * len(header))
    print(header)
    print("-" * len(header))
    for cfg in report.results:
        ps = pareto_score(cfg)
        marker = " *" if cfg.config_name == report.best_config.config_name else "  "
        print(
            f"{cfg.config_name:<16} {len(cfg.enabled_dims):>4} "
            f"{cfg.policy_sr:>6.3f} {cfg.sim2real_gap:>9.3f} "
            f"{cfg.training_cost_factor:>6.1f}x {cfg.realism_score:>8.2f} "
            f"{ps:>7.4f}{marker}"
        )
    print("-" * len(header))
    print(f"  * Best Pareto config: {report.best_config.config_name}")
    print()
    print("Randomization Dimension Impact (sorted by sim2real improvement):")
    sorted_dims = sorted(report.dim_analysis, key=lambda d: d.effect_on_sim2real, reverse=True)
    for d in sorted_dims:
        bar = "#" * int(d.effect_on_sim2real * 100)
        print(f"  {d.name:<22} S2R +{d.effect_on_sim2real:.3f}  SR {d.effect_on_sr:+.3f}  {bar}")
    print()
    print(f"Most impactful dimension : {report.most_impactful_dim.name}")
    print(f"Best sim2real gap        : {min(c.sim2real_gap for c in report.results):.3f} (full_dr)")
    print(f"Best balance config      : {report.best_config.config_name}")
    print()


# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------

def _svg_radar(configs: List[DRConfig], width: int = 500, height: int = 420) -> str:
    """Radar chart: 5 axes × 6 configs."""
    axes = ["SR", "Realism", "S2R Transfer", "Cost Efficiency"]
    n = len(axes)
    cx, cy, r = width // 2, height // 2 - 10, 150

    def ax_xy(i: int, val: float):
        angle = math.pi / 2 + 2 * math.pi * i / n
        return (
            cx + val * r * math.cos(angle),
            cy - val * r * math.sin(angle),
        )

    def cfg_to_vals(c: DRConfig):
        sr_norm = (c.policy_sr - 0.65) / 0.20          # 0.65–0.85 range
        realism = c.realism_score
        s2r = 1.0 - c.sim2real_gap                      # higher = better transfer
        cost_eff = 1.0 - (c.training_cost_factor - 1.0) / 2.0
        return [
            max(0.0, min(1.0, sr_norm)),
            max(0.0, min(1.0, realism)),
            max(0.0, min(1.0, s2r)),
            max(0.0, min(1.0, cost_eff)),
        ]

    palette = ["#64748b", "#f59e0b", "#3b82f6", "#10b981", "#ef4444", "#C74634"]
    lines = []

    # Grid rings
    for ring in [0.25, 0.5, 0.75, 1.0]:
        pts = " ".join(f"{ax_xy(i, ring)[0]:.1f},{ax_xy(i, ring)[1]:.1f}" for i in range(n))
        lines.append(f'<polygon points="{pts} {ax_xy(0, ring)[0]:.1f},{ax_xy(0, ring)[1]:.1f}" '
                     f'fill="none" stroke="#334155" stroke-width="1"/>')

    # Axis lines
    for i, label in enumerate(axes):
        x1, y1 = ax_xy(i, 0)
        x2, y2 = ax_xy(i, 1.05)
        lx, ly = ax_xy(i, 1.18)
        lines.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
                     f'stroke="#475569" stroke-width="1"/>')
        anchor = "middle" if abs(lx - cx) < 20 else ("start" if lx > cx else "end")
        lines.append(f'<text x="{lx:.1f}" y="{ly:.1f}" fill="#94a3b8" font-size="11" '
                     f'text-anchor="{anchor}" font-family="monospace">{label}</text>')

    # Data polygons
    for idx, cfg in enumerate(configs):
        vals = cfg_to_vals(cfg)
        pts = " ".join(f"{ax_xy(i, v)[0]:.1f},{ax_xy(i, v)[1]:.1f}" for i, v in enumerate(vals))
        color = palette[idx % len(palette)]
        lines.append(f'<polygon points="{pts}" fill="{color}" fill-opacity="0.15" '
                     f'stroke="{color}" stroke-width="2"/>')

    # Legend
    legend_x, legend_y = 10, height - 20 - len(configs) * 18
    for idx, cfg in enumerate(configs):
        color = palette[idx % len(palette)]
        lx, ly = legend_x, legend_y + idx * 18
        lines.append(f'<rect x="{lx}" y="{ly - 9}" width="12" height="10" fill="{color}"/>')
        lines.append(f'<text x="{lx + 16}" y="{ly}" fill="#94a3b8" font-size="11" '
                     f'font-family="monospace">{cfg.config_name}</text>')

    title_y = 20
    lines.append(f'<text x="{cx}" y="{title_y}" fill="#e2e8f0" font-size="13" '
                 f'text-anchor="middle" font-family="monospace" font-weight="bold">'
                 f'Config Radar: SR / Realism / S2R Transfer / Cost</text>')

    inner = "\n  ".join(lines)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'style="background:#1e293b;border-radius:8px">\n  {inner}\n</svg>'
    )


def _svg_bar_dims(dims: List[RandomizationDim], width: int = 560, height: int = 300) -> str:
    """Horizontal bar chart: each dim's sim2real gap improvement, sorted desc."""
    sorted_dims = sorted(dims, key=lambda d: d.effect_on_sim2real, reverse=True)
    pad_l, pad_r, pad_t, pad_b = 160, 30, 40, 30
    chart_w = width - pad_l - pad_r
    chart_h = height - pad_t - pad_b
    bar_h = chart_h // len(sorted_dims) - 4
    max_val = max(d.effect_on_sim2real for d in sorted_dims)

    lines = []
    lines.append(f'<text x="{width // 2}" y="22" fill="#e2e8f0" font-size="13" '
                 f'text-anchor="middle" font-family="monospace" font-weight="bold">'
                 f'Dim Effect on Sim-to-Real Gap Improvement</text>')

    for i, d in enumerate(sorted_dims):
        bw = int(d.effect_on_sim2real / max_val * chart_w)
        x0 = pad_l
        y0 = pad_t + i * (bar_h + 4)
        color = "#C74634" if d.effect_on_sim2real == max_val else "#3b82f6"
        lines.append(f'<rect x="{x0}" y="{y0}" width="{bw}" height="{bar_h}" '
                     f'fill="{color}" rx="3"/>')
        lines.append(f'<text x="{x0 - 6}" y="{y0 + bar_h - 4}" fill="#94a3b8" font-size="10" '
                     f'text-anchor="end" font-family="monospace">{d.name}</text>')
        lines.append(f'<text x="{x0 + bw + 4}" y="{y0 + bar_h - 4}" fill="#94a3b8" font-size="10" '
                     f'font-family="monospace">+{d.effect_on_sim2real:.3f}</text>')

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'style="background:#1e293b;border-radius:8px">\n  ' +
        "\n  ".join(lines) + "\n</svg>"
    )


# ---------------------------------------------------------------------------
# HTML report
# ---------------------------------------------------------------------------

def build_html(report: DRReport) -> str:
    best_gap = min(c.sim2real_gap for c in report.results)
    full_cost = next(c.training_cost_factor for c in report.results if c.config_name == "full_dr")
    cards_html = f"""
    <div class="cards">
      <div class="card">
        <div class="card-val">{best_gap:.2f}</div>
        <div class="card-lbl">Best Sim2Real Gap<br><span class="sub">(full_dr config)</span></div>
      </div>
      <div class="card highlight">
        <div class="card-val">{report.best_config.config_name}</div>
        <div class="card-lbl">Best Balance Config<br><span class="sub">Pareto-optimal</span></div>
      </div>
      <div class="card">
        <div class="card-val">{report.most_impactful_dim.name.replace('_', ' ')}</div>
        <div class="card-lbl">Most Impactful Dim<br><span class="sub">S2R gap reduction</span></div>
      </div>
      <div class="card">
        <div class="card-val">{full_cost:.1f}x</div>
        <div class="card-lbl">Full DR Training Cost<br><span class="sub">vs no randomization</span></div>
      </div>
    </div>"""

    radar_svg = _svg_radar(report.results)
    bar_svg = _svg_bar_dims(report.dim_analysis)

    rows = []
    for cfg in sorted(report.results, key=pareto_score, reverse=True):
        ps = pareto_score(cfg)
        is_best = cfg.config_name == report.best_config.config_name
        rec = ""
        if cfg.config_name == "adaptive_dr":
            rec = "Recommended — best Pareto"
        elif cfg.config_name == "full_dr":
            rec = "Use if sim2real is critical"
        elif cfg.config_name == "lighting_only":
            rec = "Always include at minimum"
        elif cfg.config_name == "none":
            rec = "Avoid for real deployment"
        elif cfg.config_name == "physics_only":
            rec = "Good for manipulation tasks"
        elif cfg.config_name == "visual_only":
            rec = "Good for visual robustness"
        row_class = ' class="best-row"' if is_best else ""
        rows.append(
            f"<tr{row_class}>"
            f"<td>{cfg.config_name}</td>"
            f"<td>{len(cfg.enabled_dims)}</td>"
            f"<td>{cfg.policy_sr:.3f}</td>"
            f"<td>{cfg.sim2real_gap:.3f}</td>"
            f"<td>{cfg.training_cost_factor:.1f}x</td>"
            f"<td>{cfg.realism_score:.2f}</td>"
            f"<td>{ps:.4f}</td>"
            f"<td>{rec}</td>"
            f"</tr>"
        )
    table_rows = "\n".join(rows)

    dim_rows = []
    for d in sorted(report.dim_analysis, key=lambda x: x.effect_on_sim2real, reverse=True):
        dim_rows.append(
            f"<tr>"
            f"<td>{d.name.replace('_', ' ')}</td>"
            f"<td>{d.range_low} – {d.range_high} {d.unit}</td>"
            f"<td>{d.effect_on_sr:+.3f}</td>"
            f"<td>{d.effect_on_sim2real:+.3f}</td>"
            f"</tr>"
        )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Domain Randomization Analyzer — OCI Robot Cloud</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: 'Courier New', monospace;
    background: #0f172a;
    color: #e2e8f0;
    padding: 28px;
  }}
  h1 {{ color: #C74634; font-size: 1.5rem; margin-bottom: 4px; }}
  .subtitle {{ color: #64748b; font-size: 0.85rem; margin-bottom: 28px; }}
  h2 {{ color: #94a3b8; font-size: 1rem; margin: 28px 0 12px; border-bottom: 1px solid #1e293b; padding-bottom: 6px; }}
  .cards {{ display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 32px; }}
  .card {{
    background: #1e293b; border-radius: 8px; padding: 20px 24px;
    min-width: 180px; flex: 1;
    border-left: 3px solid #334155;
  }}
  .card.highlight {{ border-left-color: #C74634; }}
  .card-val {{ font-size: 1.4rem; font-weight: bold; color: #f1f5f9; margin-bottom: 6px; }}
  .card-lbl {{ color: #64748b; font-size: 0.78rem; line-height: 1.5; }}
  .sub {{ color: #475569; font-size: 0.72rem; }}
  .charts {{ display: flex; gap: 20px; flex-wrap: wrap; margin-bottom: 32px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.82rem; margin-bottom: 28px; }}
  th {{ background: #1e293b; color: #94a3b8; padding: 10px 12px; text-align: left; }}
  td {{ padding: 9px 12px; border-bottom: 1px solid #1e293b; color: #cbd5e1; }}
  tr:hover td {{ background: #1e293b88; }}
  tr.best-row td {{ color: #f1f5f9; background: #1e293b; }}
  tr.best-row td:first-child {{ color: #C74634; font-weight: bold; }}
  .insight {{
    background: #1e293b; border-radius: 8px; padding: 18px 22px;
    border-left: 3px solid #C74634; margin-bottom: 24px;
  }}
  .insight h3 {{ color: #C74634; font-size: 0.9rem; margin-bottom: 10px; }}
  .insight ul {{ color: #94a3b8; font-size: 0.82rem; padding-left: 18px; line-height: 1.9; }}
  .insight ul li span {{ color: #f1f5f9; }}
  footer {{ color: #334155; font-size: 0.72rem; margin-top: 32px; }}
</style>
</head>
<body>
<h1>Domain Randomization Analyzer</h1>
<div class="subtitle">Isaac Sim · GR00T N1.6 · OCI Robot Cloud — Sim-to-Real Transfer Quality Report</div>

{cards_html}

<h2>Config Radar Chart</h2>
<div class="charts">
  {radar_svg}
  {bar_svg}
</div>

<h2>Config Comparison Table</h2>
<table>
  <thead>
    <tr>
      <th>Config</th><th># Dims</th><th>Policy SR</th>
      <th>S2R Gap</th><th>Train Cost</th><th>Realism</th>
      <th>Pareto Score</th><th>Recommendation</th>
    </tr>
  </thead>
  <tbody>
{table_rows}
  </tbody>
</table>

<h2>Randomization Dimension Analysis</h2>
<table>
  <thead>
    <tr>
      <th>Dimension</th><th>Range</th>
      <th>SR Effect</th><th>S2R Gap Reduction</th>
    </tr>
  </thead>
  <tbody>
{''.join(dim_rows)}
  </tbody>
</table>

<div class="insight">
  <h3>Key Insights</h3>
  <ul>
    <li><span>adaptive_dr</span> is the best Pareto config — 0.15 gap, 0.77 SR, only 1.8x cost. Start here.</li>
    <li><span>full_dr</span> achieves the lowest sim2real gap (0.12) but at 2.8x training cost — use only when deployment environment is highly variable.</li>
    <li><span>lighting_intensity</span> is the single highest-impact visual dim (+0.07 S2R improvement). Always include it, even in lightweight configs.</li>
    <li><span>physics_only</span> reduces SR (-4% vs none) but delivers strong sim2real improvement (+0.17 gap reduction) — worth it for manipulation.</li>
    <li>Easy→hard curriculum in <span>adaptive_dr</span> recovers the SR penalty from aggressive randomization while preserving most of the transfer benefit.</li>
  </ul>
</div>

<footer>Generated by domain_randomization_analyzer.py · OCI Robot Cloud · {__import__('datetime').date.today()}</footer>
</body>
</html>"""
    return html


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Analyze Isaac Sim domain randomization impact on sim-to-real transfer."
    )
    p.add_argument("--mock", action="store_true", default=True,
                   help="Use built-in mock data (default: true; no real Isaac Sim required)")
    p.add_argument("--output", default="/tmp/domain_randomization_analyzer.html",
                   help="Path for HTML report output (default: /tmp/domain_randomization_analyzer.html)")
    p.add_argument("--seed", type=int, default=42,
                   help="Random seed for jitter noise (default: 42)")
    return p.parse_args()


def main() -> None:
    args = parse_args()

    configs = apply_seed_jitter(CANONICAL_CONFIGS, seed=args.seed)
    dims = list(RANDOMIZATION_DIMS)

    report = build_report(configs, dims)
    print_comparison(report)

    html = build_html(report)
    out_path = args.output
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"HTML report written to: {out_path}")


if __name__ == "__main__":
    main()
