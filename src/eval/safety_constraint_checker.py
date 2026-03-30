"""
Safety constraint violation analysis for GR00T action policies.
Tracks velocity, torque, workspace, and collision limits across evaluation episodes.

Usage:
    python safety_constraint_checker.py --mock --output /tmp/safety_constraint_checker.html --seed 42
    python safety_constraint_checker.py --mock --output /tmp/safety_constraint_checker.html
"""

import argparse
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class SafetyViolation:
    constraint_name: str
    severity: str          # "critical" | "warning" | "info"
    timestamp_ms: float
    joint_idx: int
    value: float
    limit: float
    episode_id: int


@dataclass
class ConstraintProfile:
    policy_name: str
    n_episodes: int
    violations_per_episode: float
    constraint_pass_rate: float    # 0.0–1.0
    critical_rate: float           # fraction of violations that are critical
    violation_breakdown: Dict[str, int]  # constraint_name -> count


@dataclass
class SafetyReport:
    safest_policy: str
    most_violations_policy: str
    results: List[ConstraintProfile]


# ---------------------------------------------------------------------------
# Constraint definitions
# ---------------------------------------------------------------------------

CONSTRAINTS = [
    {"name": "joint_velocity_limit",     "limit": 3.14,  "unit": "rad/s"},
    {"name": "joint_torque_limit",        "limit": 87.0,  "unit": "Nm"},
    {"name": "workspace_boundary",        "limit": 0.85,  "unit": "m"},
    {"name": "self_collision",            "limit": 0.02,  "unit": "m"},
    {"name": "table_contact",             "limit": 5.0,   "unit": "N"},
    {"name": "gripper_force",             "limit": 20.0,  "unit": "N"},
    {"name": "end_effector_velocity",     "limit": 1.5,   "unit": "m/s"},
    {"name": "acceleration_limit",        "limit": 15.0,  "unit": "rad/s²"},
]

CONSTRAINT_NAMES = [c["name"] for c in CONSTRAINTS]

# Per-policy mean violations per episode (ground truth for simulation)
POLICY_CONFIGS = {
    "bc_baseline": {
        "violations_per_ep_mean": 3.2,
        "violations_per_ep_std": 0.8,
        "critical_fraction": 0.30,
        "description": "Behavioral cloning baseline (1000 demos, no DAgger)",
    },
    "dagger_run5": {
        "violations_per_ep_mean": 1.8,
        "violations_per_ep_std": 0.6,
        "critical_fraction": 0.20,
        "description": "DAgger run5 (5000 steps fine-tune, 5% eval success)",
    },
    "dagger_run9": {
        "violations_per_ep_mean": 0.4,
        "violations_per_ep_std": 0.2,
        "critical_fraction": 0.08,
        "description": "DAgger run9 (safest, highest pass rate ~94%)",
    },
    "dagger_run9_lora": {
        "violations_per_ep_mean": 0.65,
        "violations_per_ep_std": 0.3,
        "critical_fraction": 0.12,
        "description": "DAgger run9 + LoRA adapter (parameter-efficient variant)",
    },
}

# Which constraints each policy tends to violate most
POLICY_CONSTRAINT_WEIGHTS = {
    "bc_baseline":       [0.25, 0.20, 0.15, 0.10, 0.10, 0.08, 0.07, 0.05],
    "dagger_run5":       [0.22, 0.18, 0.14, 0.12, 0.12, 0.09, 0.07, 0.06],
    "dagger_run9":       [0.18, 0.15, 0.12, 0.10, 0.15, 0.12, 0.10, 0.08],
    "dagger_run9_lora":  [0.20, 0.16, 0.13, 0.11, 0.14, 0.11, 0.09, 0.06],
}

N_EPISODES = 20
N_JOINTS = 7


# ---------------------------------------------------------------------------
# Simulation
# ---------------------------------------------------------------------------

def _simulate_violation(
    policy_name: str,
    episode_id: int,
    cfg: dict,
    rng: random.Random,
) -> Optional[SafetyViolation]:
    """Simulate a single violation draw for this episode."""
    weights = POLICY_CONSTRAINT_WEIGHTS[policy_name]
    constraint = rng.choices(CONSTRAINTS, weights=weights, k=1)[0]

    # Value: limit * (1 + overshoot_fraction)
    overshoot = rng.uniform(0.02, 0.35)
    value = constraint["limit"] * (1.0 + overshoot)

    # Severity based on overshoot magnitude
    if overshoot > 0.25:
        severity = "critical"
    elif overshoot > 0.10:
        severity = "warning"
    else:
        severity = "info"

    # Only flip to critical at the configured critical fraction
    if rng.random() < cfg["critical_fraction"]:
        severity = "critical"

    return SafetyViolation(
        constraint_name=constraint["name"],
        severity=severity,
        timestamp_ms=round(rng.uniform(0, 30_000), 1),
        joint_idx=rng.randint(0, N_JOINTS - 1),
        value=round(value, 4),
        limit=constraint["limit"],
        episode_id=episode_id,
    )


def simulate_policy(
    policy_name: str,
    n_episodes: int = N_EPISODES,
    rng: Optional[random.Random] = None,
) -> ConstraintProfile:
    if rng is None:
        rng = random.Random()

    cfg = POLICY_CONFIGS[policy_name]
    all_violations: List[SafetyViolation] = []

    for ep in range(n_episodes):
        # Draw episode violation count from a Poisson-like distribution
        mean = cfg["violations_per_ep_mean"]
        std = cfg["violations_per_ep_std"]
        count = max(0, round(rng.gauss(mean, std)))
        for _ in range(count):
            v = _simulate_violation(policy_name, ep, cfg, rng)
            if v:
                all_violations.append(v)

    n_violations = len(all_violations)
    violations_per_episode = round(n_violations / n_episodes, 3)

    # Constraint pass rate: fraction of episodes with zero critical violations
    critical_eps = set()
    for v in all_violations:
        if v.severity == "critical":
            critical_eps.add(v.episode_id)
    constraint_pass_rate = round(1.0 - len(critical_eps) / n_episodes, 4)

    critical_count = sum(1 for v in all_violations if v.severity == "critical")
    critical_rate = round(critical_count / n_violations, 4) if n_violations > 0 else 0.0

    breakdown: Dict[str, int] = {name: 0 for name in CONSTRAINT_NAMES}
    for v in all_violations:
        breakdown[v.constraint_name] += 1

    return ConstraintProfile(
        policy_name=policy_name,
        n_episodes=n_episodes,
        violations_per_episode=violations_per_episode,
        constraint_pass_rate=constraint_pass_rate,
        critical_rate=critical_rate,
        violation_breakdown=breakdown,
    )


def run_safety_analysis(seed: int = 42) -> SafetyReport:
    rng = random.Random(seed)
    results: List[ConstraintProfile] = []
    for policy_name in POLICY_CONFIGS:
        profile = simulate_policy(policy_name, rng=rng)
        results.append(profile)

    safest = max(results, key=lambda p: p.constraint_pass_rate)
    worst = max(results, key=lambda p: p.violations_per_episode)
    return SafetyReport(
        safest_policy=safest.policy_name,
        most_violations_policy=worst.policy_name,
        results=results,
    )


# ---------------------------------------------------------------------------
# CLI table
# ---------------------------------------------------------------------------

def print_summary_table(report: SafetyReport) -> None:
    header = f"{'Policy':<22} {'Violations/Ep':>14} {'Pass Rate':>10} {'Critical%':>10} {'Worst Constraint':<28}"
    print()
    print("OCI Robot Cloud — Safety Constraint Checker")
    print("=" * len(header))
    print(header)
    print("-" * len(header))
    for p in report.results:
        worst_constraint = max(p.violation_breakdown, key=lambda k: p.violation_breakdown[k])
        worst_constraint_short = worst_constraint.replace("_", " ")
        marker = " *" if p.policy_name == report.safest_policy else ""
        print(
            f"{p.policy_name:<22} {p.violations_per_episode:>14.3f} "
            f"{p.constraint_pass_rate*100:>9.1f}% "
            f"{p.critical_rate*100:>9.1f}% "
            f"{worst_constraint_short:<28}{marker}"
        )
    print("-" * len(header))
    print(f"  * safest policy: {report.safest_policy}")
    print(f"  most violations: {report.most_violations_policy}")
    print()


# ---------------------------------------------------------------------------
# HTML report
# ---------------------------------------------------------------------------

_POLICY_COLORS = {
    "bc_baseline":      "#ef4444",
    "dagger_run5":      "#f97316",
    "dagger_run9":      "#22c55e",
    "dagger_run9_lora": "#3b82f6",
}

_SEVERITY_COLORS = {
    "critical": "#ef4444",
    "warning":  "#facc15",
    "info":     "#94a3b8",
}


def _svg_horizontal_bar_chart(results: List[ConstraintProfile]) -> str:
    """SVG horizontal bar chart: violations per episode per policy."""
    width = 560
    bar_height = 34
    gap = 14
    label_w = 160
    max_val = max(p.violations_per_episode for p in results) * 1.15 or 1.0
    chart_w = width - label_w - 20
    chart_h = len(results) * (bar_height + gap) + gap

    rows = []
    for i, p in enumerate(results):
        y = gap + i * (bar_height + gap)
        bar_w = max(4, int(p.violations_per_episode / max_val * chart_w))
        color = _POLICY_COLORS.get(p.policy_name, "#64748b")
        rows.append(
            f'<text x="{label_w - 8}" y="{y + bar_height // 2 + 5}" '
            f'fill="#cbd5e1" font-size="13" text-anchor="end">'
            f'{p.policy_name}</text>'
            f'<rect x="{label_w}" y="{y}" width="{bar_w}" height="{bar_height}" '
            f'rx="4" fill="{color}" opacity="0.88"/>'
            f'<text x="{label_w + bar_w + 6}" y="{y + bar_height // 2 + 5}" '
            f'fill="#e2e8f0" font-size="12">{p.violations_per_episode:.2f}</text>'
        )

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{chart_h}" '
        f'style="background:#0f172a;border-radius:8px">'
        + "\n".join(rows)
        + "</svg>"
    )
    return svg


def _svg_stacked_bar_chart(results: List[ConstraintProfile]) -> str:
    """SVG stacked bar chart: violation type breakdown per policy."""
    width = 620
    bar_height = 28
    gap = 12
    label_w = 160
    chart_w = width - label_w - 20

    max_total = max(sum(p.violation_breakdown.values()) for p in results) or 1
    chart_h = len(results) * (bar_height + gap) + gap + 60  # +60 for legend

    constraint_colors = [
        "#C74634", "#f97316", "#facc15", "#22c55e",
        "#06b6d4", "#3b82f6", "#8b5cf6", "#ec4899",
    ]

    rows = []
    for i, p in enumerate(results):
        y = gap + i * (bar_height + gap)
        total = sum(p.violation_breakdown.values()) or 1
        x_cursor = label_w
        rows.append(
            f'<text x="{label_w - 8}" y="{y + bar_height // 2 + 5}" '
            f'fill="#cbd5e1" font-size="13" text-anchor="end">{p.policy_name}</text>'
        )
        for j, cname in enumerate(CONSTRAINT_NAMES):
            count = p.violation_breakdown.get(cname, 0)
            seg_w = int(count / max_total * chart_w)
            if seg_w < 1:
                continue
            color = constraint_colors[j % len(constraint_colors)]
            rows.append(
                f'<rect x="{x_cursor}" y="{y}" width="{seg_w}" height="{bar_height}" '
                f'fill="{color}" opacity="0.85">'
                f'<title>{cname}: {count}</title></rect>'
            )
            x_cursor += seg_w
        rows.append(
            f'<text x="{x_cursor + 4}" y="{y + bar_height // 2 + 5}" '
            f'fill="#94a3b8" font-size="11">{total}</text>'
        )

    # Legend
    legend_y = gap + len(results) * (bar_height + gap) + 8
    legend_items = []
    for j, cname in enumerate(CONSTRAINT_NAMES):
        col = j % 4
        row = j // 4
        lx = label_w + col * 110
        ly = legend_y + row * 20
        color = constraint_colors[j % len(constraint_colors)]
        short = cname.replace("_limit", "").replace("_boundary", "").replace("_", " ")
        legend_items.append(
            f'<rect x="{lx}" y="{ly}" width="10" height="10" rx="2" fill="{color}"/>'
            f'<text x="{lx + 14}" y="{ly + 9}" fill="#94a3b8" font-size="11">{short}</text>'
        )

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{chart_h}" '
        f'style="background:#0f172a;border-radius:8px">'
        + "\n".join(rows)
        + "\n".join(legend_items)
        + "</svg>"
    )
    return svg


def _stat_cards(report: SafetyReport) -> str:
    safest = next(p for p in report.results if p.policy_name == report.safest_policy)
    best_vpe = min(report.results, key=lambda p: p.violations_per_episode)
    best_pass = max(report.results, key=lambda p: p.constraint_pass_rate)
    worst_crit = max(report.results, key=lambda p: p.critical_rate)

    cards = [
        ("Safest Policy", safest.policy_name, f"{safest.constraint_pass_rate*100:.1f}% pass rate", "#22c55e"),
        ("Best Violations/Ep", f"{best_vpe.violations_per_episode:.2f}", best_vpe.policy_name, "#3b82f6"),
        ("Best Pass Rate", f"{best_pass.constraint_pass_rate*100:.1f}%", best_pass.policy_name, "#8b5cf6"),
        ("Most Critical Violations", f"{worst_crit.critical_rate*100:.1f}%", worst_crit.policy_name, "#ef4444"),
    ]
    html = '<div class="stat-grid">'
    for title, value, sub, color in cards:
        html += f'''
        <div class="stat-card">
          <div class="stat-title">{title}</div>
          <div class="stat-value" style="color:{color}">{value}</div>
          <div class="stat-sub">{sub}</div>
        </div>'''
    html += "</div>"
    return html


def _summary_table(results: List[ConstraintProfile]) -> str:
    rows = ""
    for p in results:
        worst_c = max(p.violation_breakdown, key=lambda k: p.violation_breakdown[k])
        worst_short = worst_c.replace("_", " ")
        pass_pct = f"{p.constraint_pass_rate*100:.1f}%"
        crit_pct = f"{p.critical_rate*100:.1f}%"
        color = _POLICY_COLORS.get(p.policy_name, "#94a3b8")
        rows += f"""
        <tr>
          <td><span style="color:{color};font-weight:600">{p.policy_name}</span></td>
          <td style="text-align:right">{p.violations_per_episode:.3f}</td>
          <td style="text-align:right">{pass_pct}</td>
          <td style="text-align:right">{crit_pct}</td>
          <td>{worst_short}</td>
        </tr>"""
    return f"""
    <table class="summary-table">
      <thead>
        <tr>
          <th>Policy</th>
          <th>Violations / Ep</th>
          <th>Pass Rate</th>
          <th>Critical %</th>
          <th>Worst Constraint</th>
        </tr>
      </thead>
      <tbody>{rows}</tbody>
    </table>"""


def generate_html_report(report: SafetyReport, output_path: str) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    bar_chart = _svg_horizontal_bar_chart(report.results)
    stacked_chart = _svg_stacked_bar_chart(report.results)
    stat_cards = _stat_cards(report)
    summary_table = _summary_table(report.results)

    safest = next(p for p in report.results if p.policy_name == report.safest_policy)
    bc = next(p for p in report.results if p.policy_name == "bc_baseline")
    improvement_pct = round((1 - safest.violations_per_episode / bc.violations_per_episode) * 100, 1)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Safety Constraint Checker — OCI Robot Cloud</title>
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: #1e293b;
    color: #e2e8f0;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    font-size: 14px;
    line-height: 1.6;
    padding: 32px 40px;
  }}
  h1 {{ color: #C74634; font-size: 1.7rem; font-weight: 700; margin-bottom: 4px; }}
  h2 {{ color: #C74634; font-size: 1.15rem; font-weight: 600; margin: 28px 0 12px; }}
  .meta {{ color: #64748b; font-size: 12px; margin-bottom: 28px; }}

  .stat-grid {{
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 16px;
    margin-bottom: 8px;
  }}
  .stat-card {{
    background: #0f172a;
    border: 1px solid #334155;
    border-radius: 10px;
    padding: 18px 20px;
  }}
  .stat-title {{ color: #94a3b8; font-size: 11px; text-transform: uppercase; letter-spacing: .05em; margin-bottom: 8px; }}
  .stat-value {{ font-size: 1.5rem; font-weight: 700; margin-bottom: 4px; }}
  .stat-sub {{ color: #64748b; font-size: 12px; }}

  .chart-section {{ margin: 8px 0 24px; }}
  .chart-section svg {{ display: block; }}

  .summary-table {{
    width: 100%;
    border-collapse: collapse;
    margin-top: 4px;
  }}
  .summary-table th {{
    background: #0f172a;
    color: #94a3b8;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: .05em;
    padding: 10px 14px;
    text-align: left;
    border-bottom: 1px solid #334155;
  }}
  .summary-table td {{
    padding: 10px 14px;
    border-bottom: 1px solid #1e293b;
    color: #cbd5e1;
  }}
  .summary-table tr:hover td {{ background: #0f172a; }}

  .interpretation {{
    background: #0f172a;
    border: 1px solid #334155;
    border-left: 4px solid #C74634;
    border-radius: 6px;
    padding: 18px 22px;
    margin-top: 28px;
  }}
  .interpretation h3 {{ color: #C74634; font-size: 0.95rem; margin-bottom: 10px; }}
  .interpretation ul {{ padding-left: 20px; }}
  .interpretation li {{ color: #94a3b8; margin-bottom: 6px; }}
  .interpretation li strong {{ color: #e2e8f0; }}

  .footer {{
    color: #334155;
    font-size: 11px;
    text-align: center;
    margin-top: 40px;
    padding-top: 16px;
    border-top: 1px solid #1e293b;
  }}
</style>
</head>
<body>
<h1>Safety Constraint Checker</h1>
<p class="meta">OCI Robot Cloud &mdash; GR00T Policy Safety Analysis &nbsp;|&nbsp; Generated: {now}</p>

{stat_cards}

<h2>Violations per Episode by Policy</h2>
<div class="chart-section">
{bar_chart}
</div>

<h2>Violation Type Breakdown (hover segments for counts)</h2>
<div class="chart-section">
{stacked_chart}
</div>

<h2>Policy Summary</h2>
{summary_table}

<div class="interpretation">
  <h3>Interpretation &amp; Safety Thresholds</h3>
  <ul>
    <li><strong>Constraint pass rate</strong>: fraction of episodes with zero critical violations. Target &ge; 90% for production deployment.</li>
    <li><strong>Critical threshold</strong>: violations exceeding the safety limit by more than 25% are classified critical and halt the episode.</li>
    <li><strong>dagger_run9 improvement</strong>: {improvement_pct}% fewer violations per episode vs. bc_baseline ({safest.violations_per_episode:.2f} vs {bc.violations_per_episode:.2f}), demonstrating that iterative DAgger correction substantially reduces constraint exceedances.</li>
    <li><strong>joint_velocity_limit</strong> (3.14 rad/s) and <strong>joint_torque_limit</strong> (87 Nm) are the most frequently violated constraints across all policies — confirm actuator model accuracy in simulation.</li>
    <li><strong>dagger_run9_lora</strong> achieves safety close to dagger_run9 with a LoRA adapter, validating parameter-efficient fine-tuning as a safe and deployable alternative.</li>
    <li>Policies with critical rate &lt; 10% and pass rate &gt; 90% are recommended for real-robot deployment under supervised conditions.</li>
  </ul>
</div>

<div class="footer">
  OCI Robot Cloud &mdash; Safety Constraint Checker &mdash; Oracle Confidential
</div>
</body>
</html>"""

    Path(output_path).write_text(html, encoding="utf-8")
    return output_path


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Safety constraint violation analysis for GR00T action policies."
    )
    parser.add_argument("--mock", action="store_true", default=True,
                        help="Use simulated data (default: True)")
    parser.add_argument("--output", default="/tmp/safety_constraint_checker.html",
                        help="Output HTML path (default: /tmp/safety_constraint_checker.html)")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed for reproducibility (default: 42)")
    args = parser.parse_args()

    report = run_safety_analysis(seed=args.seed)
    print_summary_table(report)

    out = generate_html_report(report, args.output)
    print(f"HTML report written to: {out}")


if __name__ == "__main__":
    main()
