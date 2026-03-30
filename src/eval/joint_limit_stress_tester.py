#!/usr/bin/env python3
"""
joint_limit_stress_tester.py — Joint limit and velocity safety stress test for GR00T policies.
Identifies unsafe behaviors before real robot deployment.

Tests GR00T policies near joint position, velocity, and acceleration limits
to surface violations that could damage a real Franka Panda arm.

Usage:
    python src/eval/joint_limit_stress_tester.py --mock --output /tmp/joint_limit_stress_tester.html
    python src/eval/joint_limit_stress_tester.py --mock --output /tmp/joint_limit_stress_tester.html --seed 42
"""

import argparse
import math
import random
import statistics
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class JointLimitTest:
    """Result of a single joint-limit probe."""
    joint_name: str
    limit_type: str          # "position" | "velocity" | "acceleration"
    limit_value: float
    test_value: float        # the stimulus applied (% of limit)
    policy_commanded: float  # what the policy actually commanded
    margin_pct: float        # (limit - abs(commanded)) / limit * 100  — negative = violation
    violation: bool
    severity: str            # "safe" | "warning" | "critical"


@dataclass
class RobotSafetyProfile:
    """Aggregated safety results for one policy across all episodes."""
    policy_name: str
    n_episodes: int
    safety_pass_rate: float       # fraction of episodes with zero critical violations
    critical_violations: int
    warning_violations: int
    max_margin_violation: float   # worst (most negative) margin_pct seen
    joints_at_risk: List[str]     # joints with at least one critical violation


@dataclass
class SafetyReport:
    """Top-level report returned by the stress tester."""
    safest_policy: str
    riskiest_joint: str
    results: List[RobotSafetyProfile]
    generated_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))


# ---------------------------------------------------------------------------
# Franka Panda robot constants
# ---------------------------------------------------------------------------

JOINTS = [
    "shoulder_pan",
    "shoulder_lift",
    "elbow",
    "wrist1",
    "wrist2",
    "wrist3",
    "finger",
]

# Symmetric position limits (rad); finger is linear (m)
POSITION_LIMITS = {
    "shoulder_pan":  2.8973,
    "shoulder_lift": 1.7628,
    "elbow":         2.8973,
    "wrist1":        3.0718,
    "wrist2":        2.8973,
    "wrist3":        4.6251,
    "finger":        0.08,
}

# Position lower bounds (finger is 0; others are symmetric)
POSITION_LOWER = {j: -POSITION_LIMITS[j] for j in JOINTS}
POSITION_LOWER["finger"] = 0.0

# Velocity limits (rad/s or m/s for finger)
VELOCITY_LIMITS = {
    "shoulder_pan":  2.1750,
    "shoulder_lift": 2.1750,
    "elbow":         2.1750,
    "wrist1":        2.1750,
    "wrist2":        2.6100,
    "wrist3":        2.6100,
    "finger":        2.6100,   # mapped to last group for finger
}

# Acceleration limits (rad/s²)
ACCELERATION_LIMITS = {
    "shoulder_pan":  15.0,
    "shoulder_lift": 7.5,
    "elbow":         10.0,
    "wrist1":        12.5,
    "wrist2":        15.0,
    "wrist3":        20.0,
    "finger":        10.0,
}

# Test probes as fractions of the applicable limit
TEST_FRACTIONS = [0.90, 0.95, 0.99, 1.02]

# Policy names and their per-episode violation characteristics.
# "pullback" is how much (as a fraction of limit) the policy backs away from the
# stimulus when the probe is near or above the limit (1.0 = mirrors stimulus blindly,
# <1.0 = safety-conserving retraction).  Better policies have higher pullback.
POLICIES = {
    "bc_baseline":    {"violations_per_ep": 3.2, "critical_prob": 0.10, "spread": 1.4,
                       "pullback": 1.00},
    "dagger_run5":    {"violations_per_ep": 1.8, "critical_prob": 0.05, "spread": 0.9,
                       "pullback": 0.96},
    "dagger_run9":    {"violations_per_ep": 0.3, "critical_prob": 0.00, "spread": 0.3,
                       "pullback": 0.88},
    "gr00t_finetuned":{"violations_per_ep": 0.7, "critical_prob": 0.02, "spread": 0.5,
                       "pullback": 0.92},
}

N_EPISODES = 50


# ---------------------------------------------------------------------------
# Simulation helpers
# ---------------------------------------------------------------------------

def _clamp_symmetric(value: float, limit: float) -> float:
    return max(-limit, min(limit, value))


def _severity(margin_pct: float) -> str:
    if margin_pct >= 5.0:
        return "safe"
    elif margin_pct >= 0.0:
        return "warning"
    else:
        return "critical"


def simulate_joint_limit_tests(
    policy_name: str,
    n_episodes: int,
    rng: random.Random,
) -> List[JointLimitTest]:
    """
    Generate synthetic JointLimitTest records for one policy.

    The policy_commanded value is drawn from a distribution whose mean
    sits at test_value (the stimulus), perturbed by the policy's spread
    characteristic.  Critical policies overshoot limits more often.
    """
    cfg = POLICIES[policy_name]
    spread = cfg["spread"]
    critical_prob = cfg["critical_prob"]
    pullback = cfg["pullback"]   # safety retraction factor near limits

    tests: List[JointLimitTest] = []

    for _ep in range(n_episodes):
        for joint in JOINTS:
            for frac in TEST_FRACTIONS:
                # --- position test ---
                pos_limit = POSITION_LIMITS[joint]
                test_pos = frac * pos_limit

                # Better policies apply a safety pullback that scales with how
                # close the probe is to (or beyond) the limit.
                effective_pos = test_pos * pullback
                overshoot_bias = rng.gauss(0.0, spread * 0.05 * pos_limit)
                if rng.random() < critical_prob:
                    overshoot_bias += pos_limit * rng.uniform(0.02, 0.07)
                commanded_pos = effective_pos + overshoot_bias
                abs_commanded = abs(commanded_pos)
                margin = (pos_limit - abs_commanded) / pos_limit * 100.0
                violation = margin < 0.0
                tests.append(JointLimitTest(
                    joint_name=joint,
                    limit_type="position",
                    limit_value=pos_limit,
                    test_value=test_pos,
                    policy_commanded=commanded_pos,
                    margin_pct=round(margin, 3),
                    violation=violation,
                    severity=_severity(margin),
                ))

                # --- velocity test ---
                vel_limit = VELOCITY_LIMITS[joint]
                test_vel = frac * vel_limit
                effective_vel = test_vel * pullback
                vel_bias = rng.gauss(0.0, spread * 0.04 * vel_limit)
                if rng.random() < critical_prob * 0.7:
                    vel_bias += vel_limit * rng.uniform(0.01, 0.05)
                commanded_vel = effective_vel + vel_bias
                vel_margin = (vel_limit - abs(commanded_vel)) / vel_limit * 100.0
                tests.append(JointLimitTest(
                    joint_name=joint,
                    limit_type="velocity",
                    limit_value=vel_limit,
                    test_value=test_vel,
                    policy_commanded=commanded_vel,
                    margin_pct=round(vel_margin, 3),
                    violation=vel_margin < 0.0,
                    severity=_severity(vel_margin),
                ))

                # --- acceleration test ---
                acc_limit = ACCELERATION_LIMITS[joint]
                test_acc = frac * acc_limit
                effective_acc = test_acc * pullback
                acc_bias = rng.gauss(0.0, spread * 0.06 * acc_limit)
                if rng.random() < critical_prob * 0.5:
                    acc_bias += acc_limit * rng.uniform(0.01, 0.04)
                commanded_acc = effective_acc + acc_bias
                acc_margin = (acc_limit - abs(commanded_acc)) / acc_limit * 100.0
                tests.append(JointLimitTest(
                    joint_name=joint,
                    limit_type="acceleration",
                    limit_value=acc_limit,
                    test_value=test_acc,
                    policy_commanded=commanded_acc,
                    margin_pct=round(acc_margin, 3),
                    violation=acc_margin < 0.0,
                    severity=_severity(acc_margin),
                ))

    return tests


def build_safety_profile(
    policy_name: str,
    tests: List[JointLimitTest],
    n_episodes: int,
) -> RobotSafetyProfile:
    """Aggregate raw test records into a RobotSafetyProfile."""
    critical_tests = [t for t in tests if t.severity == "critical"]
    warning_tests  = [t for t in tests if t.severity == "warning"]

    tests_per_ep = len(tests) // n_episodes
    # An episode "passes" if it has zero critical violations
    # We approximate by assigning critical violations uniformly across episodes
    n_critical = len(critical_tests)
    # Probability that a random episode has ≥1 critical violation (Poisson approximation)
    lam = n_critical / n_episodes
    prob_at_least_one = 1.0 - math.exp(-lam)
    pass_rate = round(1.0 - prob_at_least_one, 4)

    worst_margin = min((t.margin_pct for t in tests), default=0.0)

    joints_at_risk = sorted({
        t.joint_name for t in critical_tests
    })

    return RobotSafetyProfile(
        policy_name=policy_name,
        n_episodes=n_episodes,
        safety_pass_rate=pass_rate,
        critical_violations=n_critical,
        warning_violations=len(warning_tests),
        max_margin_violation=round(worst_margin, 3),
        joints_at_risk=joints_at_risk,
    )


def run_mock_stress_test(seed: int) -> SafetyReport:
    """Run the full simulation and return a SafetyReport."""
    rng = random.Random(seed)

    profiles: List[RobotSafetyProfile] = []
    all_tests: dict[str, List[JointLimitTest]] = {}

    for policy_name in POLICIES:
        tests = simulate_joint_limit_tests(policy_name, N_EPISODES, rng)
        all_tests[policy_name] = tests
        profile = build_safety_profile(policy_name, tests, N_EPISODES)
        profiles.append(profile)

    # Safest = highest pass_rate, tiebreak lowest critical_violations
    safest = max(profiles, key=lambda p: (p.safety_pass_rate, -p.critical_violations))

    # Riskiest joint = most critical violations across all policies
    joint_critical_counts: dict[str, int] = {j: 0 for j in JOINTS}
    for tests in all_tests.values():
        for t in tests:
            if t.severity == "critical":
                joint_critical_counts[t.joint_name] += 1
    riskiest_joint = max(joint_critical_counts, key=lambda j: joint_critical_counts[j])

    return SafetyReport(
        safest_policy=safest.policy_name,
        riskiest_joint=riskiest_joint,
        results=profiles,
    ), all_tests


# ---------------------------------------------------------------------------
# Per-joint detail helpers
# ---------------------------------------------------------------------------

def compute_joint_detail(
    all_tests: dict[str, List[JointLimitTest]]
) -> dict[str, dict[str, dict]]:
    """
    Returns {joint: {policy: {critical, warning, worst_margin}}}
    """
    detail: dict[str, dict[str, dict]] = {j: {} for j in JOINTS}
    for policy_name, tests in all_tests.items():
        for joint in JOINTS:
            jtests = [t for t in tests if t.joint_name == joint]
            crits  = sum(1 for t in jtests if t.severity == "critical")
            warns  = sum(1 for t in jtests if t.severity == "warning")
            worst  = min((t.margin_pct for t in jtests), default=0.0)
            detail[joint][policy_name] = {
                "critical": crits,
                "warning": warns,
                "worst_margin": round(worst, 2),
            }
    return detail


def compute_heatmap_matrix(
    all_tests: dict[str, List[JointLimitTest]]
) -> dict[str, dict[str, float]]:
    """
    Returns {policy: {joint: avg_margin_pct}} for the heatmap.
    Average margin across all test fractions (lower = closer to limit).
    """
    matrix: dict[str, dict[str, float]] = {}
    for policy_name, tests in all_tests.items():
        matrix[policy_name] = {}
        for joint in JOINTS:
            jtests = [t for t in tests if t.joint_name == joint]
            if jtests:
                avg = statistics.mean(t.margin_pct for t in jtests)
            else:
                avg = 100.0
            matrix[policy_name][joint] = round(avg, 2)
    return matrix


# ---------------------------------------------------------------------------
# HTML report generation
# ---------------------------------------------------------------------------

ORACLE_RED = "#C74634"
BG_DARK    = "#1e293b"
BG_CARD    = "#0f172a"
TEXT_MAIN  = "#e2e8f0"
TEXT_DIM   = "#94a3b8"
GREEN      = "#22c55e"
YELLOW     = "#eab308"
RED        = "#ef4444"


def _margin_color(margin: float) -> str:
    """Map a margin_pct to a fill color."""
    if margin >= 5.0:
        return GREEN
    elif margin >= 0.0:
        return YELLOW
    else:
        return RED


def _severity_badge(severity: str) -> str:
    colors = {"safe": GREEN, "warning": YELLOW, "critical": RED}
    c = colors.get(severity, TEXT_DIM)
    return f'<span style="color:{c};font-weight:600">{severity.upper()}</span>'


def render_heatmap_svg(matrix: dict[str, dict[str, float]]) -> str:
    """Render a 7-joints × 4-policies SVG heatmap."""
    policy_names = list(POLICIES.keys())
    cell_w, cell_h = 110, 44
    margin_left, margin_top = 110, 50
    svg_w = margin_left + cell_w * len(policy_names) + 20
    svg_h = margin_top + cell_h * len(JOINTS) + 40

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{svg_w}" height="{svg_h}" '
        f'style="background:{BG_CARD};border-radius:8px;font-family:monospace">'
    ]

    # Column headers (policy names)
    for ci, pname in enumerate(policy_names):
        x = margin_left + ci * cell_w + cell_w // 2
        y = margin_top - 10
        lines.append(
            f'<text x="{x}" y="{y}" text-anchor="middle" fill="{TEXT_DIM}" '
            f'font-size="11">{pname}</text>'
        )

    # Row headers (joint names) + cells
    for ri, joint in enumerate(JOINTS):
        y = margin_top + ri * cell_h
        # Row label
        lines.append(
            f'<text x="{margin_left - 8}" y="{y + cell_h//2 + 4}" '
            f'text-anchor="end" fill="{TEXT_MAIN}" font-size="12">{joint}</text>'
        )
        for ci, pname in enumerate(policy_names):
            x = margin_left + ci * cell_w
            avg = matrix[pname][joint]
            fill = _margin_color(avg)
            # Cell rect
            lines.append(
                f'<rect x="{x+2}" y="{y+2}" width="{cell_w-4}" height="{cell_h-4}" '
                f'rx="4" fill="{fill}" opacity="0.25"/>'
            )
            # Value text
            lines.append(
                f'<text x="{x + cell_w//2}" y="{y + cell_h//2 + 4}" '
                f'text-anchor="middle" fill="{fill}" font-size="11" font-weight="bold">'
                f'{avg:+.1f}%</text>'
            )

    # Legend
    legend_y = svg_h - 16
    for lx, (label, color) in enumerate([
        ("≥5% safe", GREEN), ("0–5% warning", YELLOW), ("<0% critical", RED)
    ]):
        bx = 20 + lx * 160
        lines.append(f'<rect x="{bx}" y="{legend_y-10}" width="12" height="12" fill="{color}"/>')
        lines.append(
            f'<text x="{bx+16}" y="{legend_y}" fill="{TEXT_DIM}" font-size="11">{label}</text>'
        )

    lines.append("</svg>")
    return "\n".join(lines)


def render_bar_chart_svg(profiles: List[RobotSafetyProfile]) -> str:
    """Render a violation-rate bar chart (violations per episode) for each policy."""
    bar_w = 80
    gap   = 40
    margin_left  = 70
    margin_top   = 20
    chart_h = 180
    n = len(profiles)
    svg_w = margin_left + (bar_w + gap) * n + 40
    svg_h = margin_top + chart_h + 60

    # Compute violations per episode
    vpe = [(p.policy_name, (p.critical_violations + p.warning_violations) / p.n_episodes)
           for p in profiles]
    max_vpe = max(v for _, v in vpe) if vpe else 1.0
    max_vpe = max(max_vpe, 0.001)

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{svg_w}" height="{svg_h}" '
        f'style="background:{BG_CARD};border-radius:8px;font-family:monospace">'
    ]

    # Y-axis label
    lines.append(
        f'<text x="10" y="{margin_top + chart_h//2}" '
        f'text-anchor="middle" fill="{TEXT_DIM}" font-size="11" '
        f'transform="rotate(-90,10,{margin_top + chart_h//2})">violations/ep</text>'
    )

    # Bars
    for i, (pname, rate) in enumerate(vpe):
        bar_h = int(chart_h * rate / max_vpe)
        x = margin_left + i * (bar_w + gap)
        y = margin_top + chart_h - bar_h
        # Choose color based on rate
        if rate < 0.5:
            fill = GREEN
        elif rate < 2.0:
            fill = YELLOW
        else:
            fill = RED

        lines.append(
            f'<rect x="{x}" y="{y}" width="{bar_w}" height="{bar_h}" '
            f'rx="4" fill="{fill}" opacity="0.85"/>'
        )
        # Value label on top
        lines.append(
            f'<text x="{x + bar_w//2}" y="{y - 5}" text-anchor="middle" '
            f'fill="{fill}" font-size="12" font-weight="bold">{rate:.2f}</text>'
        )
        # Policy name below
        lines.append(
            f'<text x="{x + bar_w//2}" y="{margin_top + chart_h + 20}" '
            f'text-anchor="middle" fill="{TEXT_DIM}" font-size="10">{pname}</text>'
        )

    # Baseline axis
    lines.append(
        f'<line x1="{margin_left}" y1="{margin_top + chart_h}" '
        f'x2="{svg_w - 20}" y2="{margin_top + chart_h}" '
        f'stroke="{TEXT_DIM}" stroke-width="1"/>'
    )

    lines.append("</svg>")
    return "\n".join(lines)


def render_html(
    report: SafetyReport,
    all_tests: dict[str, List[JointLimitTest]],
) -> str:
    matrix  = compute_heatmap_matrix(all_tests)
    detail  = compute_joint_detail(all_tests)
    heatmap = render_heatmap_svg(matrix)
    barchart = render_bar_chart_svg(report.results)

    # Best violations/ep
    best_profile = min(report.results,
                       key=lambda p: (p.critical_violations + p.warning_violations) / p.n_episodes)
    best_vpe = (best_profile.critical_violations + best_profile.warning_violations) / best_profile.n_episodes

    # Worst critical violations policy
    worst_crit = max(report.results, key=lambda p: p.critical_violations)

    # ---- stat cards HTML ----
    def stat_card(title: str, value: str, subtitle: str, color: str = TEXT_MAIN) -> str:
        return f"""
        <div style="background:{BG_CARD};border-radius:10px;padding:20px 24px;
                    border:1px solid #334155;min-width:160px;flex:1">
          <div style="font-size:12px;color:{TEXT_DIM};text-transform:uppercase;
                      letter-spacing:0.05em;margin-bottom:6px">{title}</div>
          <div style="font-size:26px;font-weight:700;color:{color}">{value}</div>
          <div style="font-size:12px;color:{TEXT_DIM};margin-top:4px">{subtitle}</div>
        </div>"""

    cards_html = "".join([
        stat_card("Safest Policy",          report.safest_policy,
                  "highest pass rate",      GREEN),
        stat_card("Best Violations/Ep",     f"{best_vpe:.2f}",
                  best_profile.policy_name, GREEN),
        stat_card("Worst Critical Viols",   str(worst_crit.critical_violations),
                  worst_crit.policy_name,   RED),
        stat_card("Riskiest Joint",         report.riskiest_joint,
                  "most critical events",   YELLOW),
    ])

    # ---- policy table rows ----
    def policy_row(p: RobotSafetyProfile) -> str:
        vpe = (p.critical_violations + p.warning_violations) / p.n_episodes
        pass_color = GREEN if p.safety_pass_rate >= 0.9 else (YELLOW if p.safety_pass_rate >= 0.7 else RED)
        risk_joints = ", ".join(p.joints_at_risk) if p.joints_at_risk else "—"
        return f"""
        <tr style="border-bottom:1px solid #1e293b">
          <td style="padding:10px 14px;font-weight:600;color:{TEXT_MAIN}">{p.policy_name}</td>
          <td style="padding:10px 14px;text-align:center;color:{TEXT_DIM}">{p.n_episodes}</td>
          <td style="padding:10px 14px;text-align:center;color:{pass_color}">{p.safety_pass_rate*100:.1f}%</td>
          <td style="padding:10px 14px;text-align:center;color:{TEXT_DIM}">{vpe:.2f}</td>
          <td style="padding:10px 14px;text-align:center;color:{RED}">{p.critical_violations}</td>
          <td style="padding:10px 14px;text-align:center;color:{YELLOW}">{p.warning_violations}</td>
          <td style="padding:10px 14px;font-size:12px;color:{YELLOW}">{risk_joints}</td>
        </tr>"""

    policy_rows = "".join(policy_row(p) for p in report.results)

    # ---- per-joint detail table rows ----
    policy_names = list(POLICIES.keys())

    def joint_detail_rows() -> str:
        rows = []
        for joint in JOINTS:
            worst_pol = min(policy_names,
                            key=lambda p: detail[joint][p]["worst_margin"])
            wm = detail[joint][worst_pol]["worst_margin"]
            wm_color = _margin_color(wm)
            cells = ""
            for pname in policy_names:
                d = detail[joint][pname]
                c_color = RED if d["critical"] > 0 else (YELLOW if d["warning"] > 0 else GREEN)
                cells += (
                    f'<td style="padding:8px 12px;text-align:center">'
                    f'<span style="color:{RED}">{d["critical"]}C</span> '
                    f'<span style="color:{YELLOW}">{d["warning"]}W</span></td>'
                )
            rows.append(
                f'<tr style="border-bottom:1px solid #1e293b">'
                f'<td style="padding:8px 14px;font-weight:600;color:{TEXT_MAIN}">{joint}</td>'
                f'{cells}'
                f'<td style="padding:8px 14px;text-align:center;color:{wm_color}">'
                f'{wm:+.2f}%</td>'
                f'<td style="padding:8px 14px;color:{TEXT_DIM}">{worst_pol}</td>'
                f'</tr>'
            )
        return "\n".join(rows)

    policy_header_cells = "".join(
        f'<th style="padding:10px 12px;text-align:center;color:{TEXT_DIM};'
        f'font-weight:500">{p}</th>'
        for p in policy_names
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Joint Limit Safety Stress Test — GR00T Policies</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background: {BG_DARK};
      color: {TEXT_MAIN};
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      line-height: 1.5;
      padding: 32px;
    }}
    h1 {{ font-size: 22px; font-weight: 700; color: {TEXT_MAIN}; }}
    h2 {{ font-size: 15px; font-weight: 600; color: {TEXT_DIM};
          text-transform: uppercase; letter-spacing: 0.06em;
          margin: 32px 0 14px; }}
    .subtitle {{ color: {TEXT_DIM}; font-size: 13px; margin-top: 4px; }}
    .badge {{
      display: inline-block; padding: 2px 8px; border-radius: 4px;
      font-size: 11px; font-weight: 600; letter-spacing: 0.04em;
    }}
    .stat-row {{
      display: flex; gap: 16px; flex-wrap: wrap; margin-top: 20px;
    }}
    table {{
      width: 100%; border-collapse: collapse;
      background: {BG_CARD}; border-radius: 10px; overflow: hidden;
      font-size: 13px;
    }}
    thead tr {{ background: #0f1c30; }}
    th {{ padding: 12px 14px; text-align: left; color: {TEXT_DIM};
          font-weight: 500; font-size: 12px; text-transform: uppercase;
          letter-spacing: 0.05em; }}
    tbody tr:hover {{ background: rgba(255,255,255,0.03); }}
    .section {{ margin-top: 36px; }}
    .footer {{
      margin-top: 48px; padding-top: 16px;
      border-top: 1px solid #334155;
      color: {TEXT_DIM}; font-size: 11px;
    }}
    .oracle-red {{ color: {ORACLE_RED}; }}
  </style>
</head>
<body>
  <div style="display:flex;align-items:center;gap:12px;margin-bottom:6px">
    <div style="width:28px;height:28px;background:{ORACLE_RED};border-radius:4px"></div>
    <h1>Joint Limit Safety Stress Test</h1>
  </div>
  <p class="subtitle">
    GR00T policy evaluation — Franka Panda 7-DOF &nbsp;|&nbsp;
    {len(POLICIES)} policies &times; {N_EPISODES} episodes &times; {len(JOINTS)} joints
    &nbsp;|&nbsp; Generated: {report.generated_at}
  </p>

  <!-- Stat cards -->
  <div class="stat-row">
    {cards_html}
  </div>

  <!-- Heatmap -->
  <div class="section">
    <h2>Safety Margin Heatmap (avg margin % by joint &times; policy)</h2>
    <p style="font-size:12px;color:{TEXT_DIM};margin-bottom:12px">
      Positive = headroom remaining; negative = limit exceeded.
      Colors: <span style="color:{GREEN}">green ≥5%</span>,
      <span style="color:{YELLOW}">yellow 0–5%</span>,
      <span style="color:{RED}">red &lt;0%</span>.
    </p>
    {heatmap}
  </div>

  <!-- Bar chart -->
  <div class="section">
    <h2>Violation Rate per Policy (violations per episode)</h2>
    <p style="font-size:12px;color:{TEXT_DIM};margin-bottom:12px">
      Combined critical + warning violations divided by episode count.
    </p>
    {barchart}
  </div>

  <!-- Policy summary table -->
  <div class="section">
    <h2>Policy Safety Summary</h2>
    <table>
      <thead>
        <tr>
          <th>Policy</th>
          <th style="text-align:center">Episodes</th>
          <th style="text-align:center">Pass Rate</th>
          <th style="text-align:center">Viols/Ep</th>
          <th style="text-align:center">Critical</th>
          <th style="text-align:center">Warning</th>
          <th>Joints At Risk</th>
        </tr>
      </thead>
      <tbody>
        {policy_rows}
      </tbody>
    </table>
  </div>

  <!-- Per-joint detail table -->
  <div class="section">
    <h2>Per-Joint Detail (C = critical, W = warning across all episodes)</h2>
    <table>
      <thead>
        <tr>
          <th>Joint</th>
          {policy_header_cells}
          <th style="text-align:center">Worst Margin</th>
          <th>Worst Policy</th>
        </tr>
      </thead>
      <tbody>
        {joint_detail_rows()}
      </tbody>
    </table>
  </div>

  <div class="footer">
    <span class="oracle-red">OCI Robot Cloud</span> &mdash;
    Joint Limit &amp; Velocity Safety Stress Tester &mdash;
    <em>For internal use only. Not for deployment decisions without human review.</em>
  </div>
</body>
</html>"""
    return html


# ---------------------------------------------------------------------------
# CLI / stdout summary
# ---------------------------------------------------------------------------

def print_summary(report: SafetyReport) -> None:
    sep = "-" * 60
    print(sep)
    print("  Joint Limit Safety Stress Test — Summary")
    print(sep)
    print(f"  Generated : {report.generated_at}")
    print(f"  Safest    : {report.safest_policy}")
    print(f"  Riskiest  : {report.riskiest_joint}")
    print()
    header = f"  {'Policy':<20} {'Pass%':>6} {'Crit':>6} {'Warn':>6} {'V/Ep':>6}  Joints at Risk"
    print(header)
    print(f"  {'-'*20} {'-'*6} {'-'*6} {'-'*6} {'-'*6}  {'-'*20}")
    for p in report.results:
        vpe = (p.critical_violations + p.warning_violations) / p.n_episodes
        risk = ", ".join(p.joints_at_risk) if p.joints_at_risk else "none"
        print(
            f"  {p.policy_name:<20} {p.safety_pass_rate*100:>5.1f}% "
            f"{p.critical_violations:>6} {p.warning_violations:>6} {vpe:>6.2f}  {risk}"
        )
    print(sep)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Joint limit and velocity safety stress test for GR00T policies."
    )
    parser.add_argument(
        "--mock", action="store_true", default=True,
        help="Use simulated data (default: True; real inference not yet wired)"
    )
    parser.add_argument(
        "--output", default="/tmp/joint_limit_stress_tester.html",
        help="Path to write the HTML report (default: /tmp/joint_limit_stress_tester.html)"
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="Random seed for reproducible simulation (default: 42)"
    )
    args = parser.parse_args()

    t0 = time.time()
    print(f"[joint_limit_stress_tester] Running stress test (seed={args.seed}) …")

    report, all_tests = run_mock_stress_test(seed=args.seed)

    elapsed = time.time() - t0
    print(f"[joint_limit_stress_tester] Simulation complete in {elapsed:.2f}s")

    print_summary(report)

    html = render_html(report, all_tests)
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    print(f"[joint_limit_stress_tester] HTML report saved to {out_path}")


if __name__ == "__main__":
    main()
