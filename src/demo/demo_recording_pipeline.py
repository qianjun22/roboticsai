"""
Teleoperation demo recording pipeline manager. Tracks session quality, operator
performance, and filtering for GR00T fine-tuning datasets.
"""

from __future__ import annotations

import argparse
import math
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class RecordingSession:
    session_id: str
    operator_id: str
    robot_name: str
    task_name: str
    start_time: datetime
    n_demos_attempted: int
    n_demos_accepted: int
    n_demos_rejected: int
    reject_reasons: dict[str, int]
    avg_duration_s: float
    avg_quality_score: float
    session_notes: str


@dataclass
class DemoFilter:
    filter_name: str
    n_input: int
    n_passed: int
    n_rejected: int
    rejection_rate: float
    common_reject_reason: str


@dataclass
class RecordingReport:
    total_sessions: int
    total_accepted: int
    total_rejected: int
    acceptance_rate: float
    quality_distribution: dict[str, int]
    best_operator: str
    filters: list[DemoFilter]
    sessions: list[RecordingSession]


# ---------------------------------------------------------------------------
# Simulation helpers
# ---------------------------------------------------------------------------

REJECT_REASON_KEYS = [
    "too_short",
    "collision_detected",
    "incomplete_grasp",
    "poor_trajectory",
    "timeout",
]

OPERATOR_SKILL = {
    "operator_alice": 0.88,
    "operator_bob": 0.71,
    "operator_charlie": 0.64,
}

TASK_DIFFICULTY = {
    "pick_and_place": 0.0,   # easier — no penalty
    "door_opening": -0.10,   # harder — penalty on acceptance
}


def _gauss_clamp(rng: random.Random, mean: float, sigma: float,
                 lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, rng.gauss(mean, sigma)))


def simulate_session(
    session_idx: int,
    operator_id: str,
    task_name: str,
    rng: random.Random,
) -> RecordingSession:
    skill = OPERATOR_SKILL[operator_id]
    task_adj = TASK_DIFFICULTY[task_name]
    effective_skill = skill + task_adj

    n_attempted = rng.randint(20, 30)
    accept_prob = max(0.30, min(0.95, effective_skill + rng.gauss(0, 0.05)))
    n_accepted = round(n_attempted * accept_prob)
    n_rejected = n_attempted - n_accepted

    # Distribute rejection reasons proportionally
    reject_reasons: dict[str, int] = {k: 0 for k in REJECT_REASON_KEYS}
    for _ in range(n_rejected):
        # Weights depend on skill: low-skill → more collision / poor_trajectory
        weights = [
            max(0.05, 0.35 - effective_skill * 0.30),   # too_short
            max(0.05, 0.30 - effective_skill * 0.20),   # collision_detected
            max(0.05, 0.25 - effective_skill * 0.15),   # incomplete_grasp
            max(0.05, 0.20 - effective_skill * 0.10),   # poor_trajectory
            0.05,                                        # timeout (constant)
        ]
        chosen = rng.choices(REJECT_REASON_KEYS, weights=weights, k=1)[0]
        reject_reasons[chosen] += 1

    avg_duration_s = _gauss_clamp(rng, 8.0 + skill * 5.0, 1.5, lo=3.0, hi=25.0)
    avg_quality_score = _gauss_clamp(rng, skill + task_adj * 0.5, 0.07)

    notes_map = {
        "operator_alice": "Smooth and consistent trajectories.",
        "operator_bob": "Occasional hesitations mid-trajectory.",
        "operator_charlie": "Needs coaching on grasp approach angle.",
    }

    session = RecordingSession(
        session_id=f"sess_{session_idx:03d}",
        operator_id=operator_id,
        robot_name="gr00t_arm_v2",
        task_name=task_name,
        start_time=datetime(2026, 3, 20, 9, 0, 0) + timedelta(hours=session_idx * 2),
        n_demos_attempted=n_attempted,
        n_demos_accepted=n_accepted,
        n_demos_rejected=n_rejected,
        reject_reasons=reject_reasons,
        avg_duration_s=round(avg_duration_s, 2),
        avg_quality_score=round(avg_quality_score, 3),
        session_notes=notes_map[operator_id],
    )
    return session


def simulate_all_sessions(rng: random.Random) -> list[RecordingSession]:
    # 8 sessions distributed across 3 operators × 2 tasks
    schedule = [
        ("operator_alice",   "pick_and_place"),
        ("operator_alice",   "door_opening"),
        ("operator_bob",     "pick_and_place"),
        ("operator_bob",     "door_opening"),
        ("operator_charlie", "pick_and_place"),
        ("operator_charlie", "door_opening"),
        ("operator_alice",   "pick_and_place"),  # second run
        ("operator_bob",     "pick_and_place"),  # second run
    ]
    return [simulate_session(i + 1, op, task, rng) for i, (op, task) in enumerate(schedule)]


# ---------------------------------------------------------------------------
# Filtering stage
# ---------------------------------------------------------------------------

def apply_filters(sessions: list[RecordingSession], rng: random.Random) -> list[DemoFilter]:
    total_attempted = sum(s.n_demos_attempted for s in sessions)
    total_accepted_raw = sum(s.n_demos_accepted for s in sessions)

    # Filter 1: min_length (reject <10 frames) — ~5% of accepted
    f1_rejected = round(total_accepted_raw * rng.uniform(0.04, 0.06))
    f1_passed = total_accepted_raw - f1_rejected
    f1 = DemoFilter(
        filter_name="min_length",
        n_input=total_accepted_raw,
        n_passed=f1_passed,
        n_rejected=f1_rejected,
        rejection_rate=round(f1_rejected / total_accepted_raw, 4),
        common_reject_reason="too_short (<10 frames)",
    )

    # Filter 2: collision_free — ~8% of remaining
    f2_rejected = round(f1_passed * rng.uniform(0.07, 0.09))
    f2_passed = f1_passed - f2_rejected
    f2 = DemoFilter(
        filter_name="collision_free",
        n_input=f1_passed,
        n_passed=f2_passed,
        n_rejected=f2_rejected,
        rejection_rate=round(f2_rejected / f1_passed, 4),
        common_reject_reason="collision_detected",
    )

    # Filter 3: quality_threshold (reject quality <0.55) — ~10% of remaining
    f3_rejected = round(f2_passed * rng.uniform(0.09, 0.11))
    f3_passed = f2_passed - f3_rejected
    f3 = DemoFilter(
        filter_name="quality_threshold",
        n_input=f2_passed,
        n_passed=f3_passed,
        n_rejected=f3_rejected,
        rejection_rate=round(f3_rejected / f2_passed, 4),
        common_reject_reason="quality score < 0.55",
    )

    # Filter 4: diversity_check (reject near-duplicates) — ~3% of remaining
    f4_rejected = round(f3_passed * rng.uniform(0.02, 0.04))
    f4_passed = f3_passed - f4_rejected
    f4 = DemoFilter(
        filter_name="diversity_check",
        n_input=f3_passed,
        n_passed=f4_passed,
        n_rejected=f4_rejected,
        rejection_rate=round(f4_rejected / f3_passed, 4),
        common_reject_reason="near-duplicate trajectory",
    )

    return [f1, f2, f3, f4]


# ---------------------------------------------------------------------------
# Report assembly
# ---------------------------------------------------------------------------

def build_report(sessions: list[RecordingSession],
                 filters: list[DemoFilter]) -> RecordingReport:
    total_accepted = sum(s.n_demos_accepted for s in sessions)
    total_rejected = sum(s.n_demos_rejected for s in sessions)
    total_attempted = total_accepted + total_rejected
    acceptance_rate = round(total_accepted / total_attempted, 4)

    # Quality distribution buckets
    quality_dist: dict[str, int] = {"0.0-0.6": 0, "0.6-0.7": 0, "0.7-0.8": 0, "0.8-0.9": 0, "0.9-1.0": 0}
    for s in sessions:
        q = s.avg_quality_score
        if q < 0.6:
            quality_dist["0.0-0.6"] += s.n_demos_accepted
        elif q < 0.7:
            quality_dist["0.6-0.7"] += s.n_demos_accepted
        elif q < 0.8:
            quality_dist["0.7-0.8"] += s.n_demos_accepted
        elif q < 0.9:
            quality_dist["0.8-0.9"] += s.n_demos_accepted
        else:
            quality_dist["0.9-1.0"] += s.n_demos_accepted

    # Best operator: highest avg quality across sessions
    op_scores: dict[str, list[float]] = {}
    for s in sessions:
        op_scores.setdefault(s.operator_id, []).append(s.avg_quality_score)
    best_operator = max(op_scores, key=lambda op: sum(op_scores[op]) / len(op_scores[op]))

    return RecordingReport(
        total_sessions=len(sessions),
        total_accepted=total_accepted,
        total_rejected=total_rejected,
        acceptance_rate=acceptance_rate,
        quality_distribution=quality_dist,
        best_operator=best_operator,
        filters=filters,
        sessions=sessions,
    )


# ---------------------------------------------------------------------------
# Stdout table
# ---------------------------------------------------------------------------

def print_session_table(sessions: list[RecordingSession]) -> None:
    header = (
        f"{'Session':<12} {'Operator':<20} {'Task':<18} "
        f"{'Attempted':>9} {'Accepted':>8} {'Rejected':>8} "
        f"{'Quality':>7} {'Top Reject':<22}"
    )
    print("\n" + "=" * len(header))
    print("  TELEOPERATION RECORDING SESSIONS")
    print("=" * len(header))
    print(header)
    print("-" * len(header))
    for s in sessions:
        top_reason = max(s.reject_reasons, key=lambda k: s.reject_reasons[k]) if s.n_demos_rejected else "—"
        print(
            f"{s.session_id:<12} {s.operator_id:<20} {s.task_name:<18} "
            f"{s.n_demos_attempted:>9} {s.n_demos_accepted:>8} {s.n_demos_rejected:>8} "
            f"{s.avg_quality_score:>7.3f} {top_reason:<22}"
        )
    total_att = sum(s.n_demos_attempted for s in sessions)
    total_acc = sum(s.n_demos_accepted for s in sessions)
    total_rej = sum(s.n_demos_rejected for s in sessions)
    print("-" * len(header))
    print(
        f"{'TOTAL':<12} {'':<20} {'':<18} "
        f"{total_att:>9} {total_acc:>8} {total_rej:>8} "
        f"{'':>7} {'':<22}"
    )
    print("=" * len(header) + "\n")


# ---------------------------------------------------------------------------
# HTML / SVG generation
# ---------------------------------------------------------------------------

BG = "#1e293b"
BG_CARD = "#263348"
BG_TABLE_ALT = "#1a2a3a"
ORACLE_RED = "#C74634"
BLUE = "#3b82f6"
GREEN = "#22c55e"
AMBER = "#f59e0b"
GRAY_TEXT = "#94a3b8"
WHITE_TEXT = "#f1f5f9"
BORDER = "#334155"


def _bar_chart_sessions(sessions: list[RecordingSession]) -> str:
    """Stacked bar chart: accepted (green) / rejected (red) per session."""
    W, H = 720, 260
    pad_l, pad_r, pad_t, pad_b = 50, 20, 20, 40
    chart_w = W - pad_l - pad_r
    chart_h = H - pad_t - pad_b

    max_val = max(s.n_demos_attempted for s in sessions)
    n = len(sessions)
    bar_w = chart_w / n * 0.6
    gap = chart_w / n

    svg_lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'style="background:{BG_CARD};border-radius:8px;">',
        f'<text x="{W//2}" y="16" text-anchor="middle" '
        f'font-size="12" fill="{GRAY_TEXT}" font-family="sans-serif">'
        f'Session Recording Volume</text>',
    ]

    # Y axis ticks
    for tick in [0, 5, 10, 15, 20, 25, 30]:
        if tick > max_val + 2:
            break
        y = pad_t + chart_h - (tick / max_val) * chart_h
        svg_lines.append(
            f'<line x1="{pad_l}" y1="{y:.1f}" x2="{pad_l+chart_w}" y2="{y:.1f}" '
            f'stroke="{BORDER}" stroke-width="0.5"/>'
        )
        svg_lines.append(
            f'<text x="{pad_l-4}" y="{y+4:.1f}" text-anchor="end" '
            f'font-size="9" fill="{GRAY_TEXT}" font-family="sans-serif">{tick}</text>'
        )

    for i, s in enumerate(sessions):
        x_center = pad_l + i * gap + gap / 2
        x = x_center - bar_w / 2
        acc_h = (s.n_demos_accepted / max_val) * chart_h
        rej_h = (s.n_demos_rejected / max_val) * chart_h
        base_y = pad_t + chart_h

        # accepted (bottom)
        svg_lines.append(
            f'<rect x="{x:.1f}" y="{base_y - acc_h:.1f}" '
            f'width="{bar_w:.1f}" height="{acc_h:.1f}" fill="{GREEN}" rx="2"/>'
        )
        # rejected (stacked on top)
        svg_lines.append(
            f'<rect x="{x:.1f}" y="{base_y - acc_h - rej_h:.1f}" '
            f'width="{bar_w:.1f}" height="{rej_h:.1f}" fill="{ORACLE_RED}" rx="2"/>'
        )
        # label
        svg_lines.append(
            f'<text x="{x_center:.1f}" y="{base_y+14}" text-anchor="middle" '
            f'font-size="9" fill="{GRAY_TEXT}" font-family="sans-serif">'
            f'{s.session_id}</text>'
        )

    # legend
    lx = W - pad_r - 120
    ly = pad_t + 10
    for color, label in [(GREEN, "Accepted"), (ORACLE_RED, "Rejected")]:
        svg_lines.append(f'<rect x="{lx}" y="{ly}" width="10" height="10" fill="{color}" rx="2"/>')
        svg_lines.append(
            f'<text x="{lx+14}" y="{ly+9}" font-size="10" fill="{GRAY_TEXT}" font-family="sans-serif">{label}</text>'
        )
        ly += 18

    svg_lines.append("</svg>")
    return "\n".join(svg_lines)


def _bar_chart_operators(sessions: list[RecordingSession]) -> str:
    """Grouped bar chart: acceptance rate + avg quality per operator."""
    operators = list(OPERATOR_SKILL.keys())
    op_stats: dict[str, dict] = {}
    for op in operators:
        op_sess = [s for s in sessions if s.operator_id == op]
        if not op_sess:
            continue
        total_att = sum(s.n_demos_attempted for s in op_sess)
        total_acc = sum(s.n_demos_accepted for s in op_sess)
        avg_q = sum(s.avg_quality_score for s in op_sess) / len(op_sess)
        op_stats[op] = {
            "accept_rate": total_acc / total_att,
            "avg_quality": avg_q,
        }

    W, H = 520, 240
    pad_l, pad_r, pad_t, pad_b = 50, 20, 20, 50
    chart_w = W - pad_l - pad_r
    chart_h = H - pad_t - pad_b

    n = len(op_stats)
    group_w = chart_w / n
    bar_w = group_w * 0.3
    colors = [BLUE, AMBER]

    svg_lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'style="background:{BG_CARD};border-radius:8px;">',
        f'<text x="{W//2}" y="16" text-anchor="middle" '
        f'font-size="12" fill="{GRAY_TEXT}" font-family="sans-serif">'
        f'Operator Performance Comparison</text>',
    ]

    for tick_pct in [0, 25, 50, 75, 100]:
        y = pad_t + chart_h - (tick_pct / 100) * chart_h
        svg_lines.append(
            f'<line x1="{pad_l}" y1="{y:.1f}" x2="{pad_l+chart_w}" y2="{y:.1f}" '
            f'stroke="{BORDER}" stroke-width="0.5"/>'
        )
        svg_lines.append(
            f'<text x="{pad_l-4}" y="{y+4:.1f}" text-anchor="end" '
            f'font-size="9" fill="{GRAY_TEXT}" font-family="sans-serif">{tick_pct}%</text>'
        )

    for gi, (op, stats) in enumerate(op_stats.items()):
        gx = pad_l + gi * group_w + group_w / 2
        metrics = [stats["accept_rate"], stats["avg_quality"]]
        for bi, (val, color) in enumerate(zip(metrics, colors)):
            bx = gx + (bi - 0.5) * bar_w * 1.4
            bh = val * chart_h
            by = pad_t + chart_h - bh
            svg_lines.append(
                f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bar_w:.1f}" '
                f'height="{bh:.1f}" fill="{color}" rx="2"/>'
            )
            svg_lines.append(
                f'<text x="{bx + bar_w/2:.1f}" y="{by-3:.1f}" text-anchor="middle" '
                f'font-size="8" fill="{WHITE_TEXT}" font-family="sans-serif">'
                f'{val*100:.0f}%</text>'
            )
        short_name = op.replace("operator_", "").capitalize()
        svg_lines.append(
            f'<text x="{gx:.1f}" y="{pad_t+chart_h+14}" text-anchor="middle" '
            f'font-size="10" fill="{GRAY_TEXT}" font-family="sans-serif">{short_name}</text>'
        )

    # legend
    lx = W - pad_r - 130
    ly = pad_t + 10
    for color, label in [(BLUE, "Acceptance Rate"), (AMBER, "Avg Quality")]:
        svg_lines.append(f'<rect x="{lx}" y="{ly}" width="10" height="10" fill="{color}" rx="2"/>')
        svg_lines.append(
            f'<text x="{lx+14}" y="{ly+9}" font-size="10" fill="{GRAY_TEXT}" font-family="sans-serif">{label}</text>'
        )
        ly += 18

    svg_lines.append("</svg>")
    return "\n".join(svg_lines)


def _funnel_chart(report: RecordingReport) -> str:
    """Funnel: raw demos → after each filter → final accepted."""
    total_attempted = report.total_accepted + report.total_rejected
    stages = [("Raw Demos", total_attempted)]
    current = report.total_accepted  # start of filter chain (already session-filtered)
    for f in report.filters:
        stages.append((f.filter_name.replace("_", " ").title(), f.n_passed))
        current = f.n_passed

    W, H = 480, 300
    pad_x, pad_y = 80, 30
    inner_w = W - 2 * pad_x
    inner_h = H - 2 * pad_y
    max_val = stages[0][1]

    svg_lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'style="background:{BG_CARD};border-radius:8px;">',
        f'<text x="{W//2}" y="20" text-anchor="middle" '
        f'font-size="12" fill="{GRAY_TEXT}" font-family="sans-serif">'
        f'Demo Filtering Funnel</text>',
    ]

    n_stages = len(stages)
    stage_h = inner_h / n_stages

    for i, (label, val) in enumerate(stages):
        ratio = val / max_val
        bar_half = (inner_w * ratio) / 2
        cx = W / 2
        y = pad_y + i * stage_h + stage_h * 0.1
        h = stage_h * 0.7
        # gradient from oracle red (top) to blue (bottom)
        t = i / max(n_stages - 1, 1)
        r = int(0xC7 + t * (0x3b - 0xC7))
        g = int(0x46 + t * (0x82 - 0x46))
        b = int(0x34 + t * (0xf6 - 0x34))
        color = f"#{r:02x}{g:02x}{b:02x}"

        svg_lines.append(
            f'<rect x="{cx-bar_half:.1f}" y="{y:.1f}" '
            f'width="{bar_half*2:.1f}" height="{h:.1f}" fill="{color}" rx="3" opacity="0.85"/>'
        )
        pct = val / max_val * 100
        svg_lines.append(
            f'<text x="{cx:.1f}" y="{y + h/2 + 4:.1f}" text-anchor="middle" '
            f'font-size="11" fill="{WHITE_TEXT}" font-family="sans-serif" font-weight="bold">'
            f'{val} ({pct:.0f}%)</text>'
        )
        svg_lines.append(
            f'<text x="{cx - bar_half - 6:.1f}" y="{y + h/2 + 4:.1f}" text-anchor="end" '
            f'font-size="10" fill="{GRAY_TEXT}" font-family="sans-serif">{label}</text>'
        )

    svg_lines.append("</svg>")
    return "\n".join(svg_lines)


def _session_table_html(sessions: list[RecordingSession]) -> str:
    rows = []
    for i, s in enumerate(sessions):
        bg = BG if i % 2 == 0 else BG_TABLE_ALT
        top_reason = max(s.reject_reasons, key=lambda k: s.reject_reasons[k]) if s.n_demos_rejected else "—"
        other_reasons = ", ".join(
            f"{k}:{v}" for k, v in s.reject_reasons.items()
            if v > 0 and k != top_reason
        ) or "—"
        quality_color = GREEN if s.avg_quality_score >= 0.80 else (AMBER if s.avg_quality_score >= 0.65 else ORACLE_RED)
        rows.append(f"""
        <tr style="background:{bg};">
          <td>{s.session_id}</td>
          <td>{s.operator_id.replace('operator_','')}</td>
          <td>{s.task_name.replace('_',' ')}</td>
          <td style="text-align:right;">{s.n_demos_attempted}</td>
          <td style="text-align:right;color:{GREEN};">{s.n_demos_accepted}</td>
          <td style="text-align:right;color:{ORACLE_RED};">{s.n_demos_rejected}</td>
          <td style="text-align:right;color:{quality_color};">{s.avg_quality_score:.3f}</td>
          <td style="color:{AMBER};">{top_reason.replace('_',' ')}</td>
          <td style="font-size:11px;color:{GRAY_TEXT};">{other_reasons}</td>
        </tr>""")
    return "\n".join(rows)


def generate_html(report: RecordingReport) -> str:
    svg_sessions = _bar_chart_sessions(report.sessions)
    svg_operators = _bar_chart_operators(report.sessions)
    svg_funnel = _funnel_chart(report)
    table_rows = _session_table_html(report.sessions)

    final_accepted = report.filters[-1].n_passed if report.filters else report.total_accepted
    final_pct = final_accepted / (report.total_accepted + report.total_rejected) * 100

    avg_q = sum(s.avg_quality_score for s in report.sessions) / len(report.sessions)

    stat_cards = f"""
    <div class="stat-card">
      <div class="stat-label">Total Accepted</div>
      <div class="stat-value" style="color:{GREEN};">{report.total_accepted}</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Acceptance Rate</div>
      <div class="stat-value">{report.acceptance_rate*100:.1f}%</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Best Operator</div>
      <div class="stat-value" style="color:{AMBER};">{report.best_operator.replace('operator_','').title()}</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Avg Quality Score</div>
      <div class="stat-value" style="color:{BLUE};">{avg_q:.3f}</div>
    </div>
    """

    filter_rows = ""
    for f in report.filters:
        filter_rows += f"""
        <tr>
          <td>{f.filter_name.replace('_',' ').title()}</td>
          <td style="text-align:right;">{f.n_input}</td>
          <td style="text-align:right;color:{GREEN};">{f.n_passed}</td>
          <td style="text-align:right;color:{ORACLE_RED};">{f.n_rejected}</td>
          <td style="text-align:right;">{f.rejection_rate*100:.1f}%</td>
          <td style="color:{GRAY_TEXT};font-size:12px;">{f.common_reject_reason}</td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Demo Recording Pipeline — GR00T Fine-Tuning</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: {BG}; color: {WHITE_TEXT}; font-family: 'Segoe UI', sans-serif; padding: 24px; }}
  h1 {{ font-size: 22px; margin-bottom: 4px; }}
  .subtitle {{ color: {GRAY_TEXT}; font-size: 13px; margin-bottom: 24px; }}
  .oracle-red {{ color: {ORACLE_RED}; }}
  .stat-cards {{ display: flex; gap: 16px; margin-bottom: 28px; flex-wrap: wrap; }}
  .stat-card {{ background: {BG_CARD}; border: 1px solid {BORDER}; border-radius: 8px;
                padding: 16px 24px; flex: 1; min-width: 140px; }}
  .stat-label {{ font-size: 11px; color: {GRAY_TEXT}; text-transform: uppercase; letter-spacing: 0.05em; }}
  .stat-value {{ font-size: 28px; font-weight: 700; margin-top: 4px; }}
  .charts-row {{ display: flex; gap: 16px; margin-bottom: 28px; flex-wrap: wrap; align-items: flex-start; }}
  .charts-row svg {{ max-width: 100%; }}
  section {{ margin-bottom: 32px; }}
  h2 {{ font-size: 15px; margin-bottom: 12px; color: {GRAY_TEXT}; text-transform: uppercase; letter-spacing: 0.05em; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  th {{ background: {BG_CARD}; padding: 10px 12px; text-align: left; color: {GRAY_TEXT};
        font-size: 11px; text-transform: uppercase; letter-spacing: 0.04em;
        border-bottom: 1px solid {BORDER}; }}
  td {{ padding: 9px 12px; border-bottom: 1px solid {BORDER}; }}
  .footer {{ margin-top: 40px; color: {GRAY_TEXT}; font-size: 11px; text-align: center; }}
</style>
</head>
<body>
<h1>GR00T Fine-Tuning — <span class="oracle-red">Demo Recording Pipeline</span></h1>
<p class="subtitle">
  {report.total_sessions} sessions &nbsp;|&nbsp;
  {report.total_accepted + report.total_rejected} total demos attempted &nbsp;|&nbsp;
  {final_accepted} demos after filtering ({final_pct:.1f}%) &nbsp;|&nbsp;
  Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}
</p>

<div class="stat-cards">{stat_cards}</div>

<section>
  <h2>Recording Volume by Session</h2>
  <div class="charts-row">
    {svg_sessions}
  </div>
</section>

<section>
  <h2>Operator Performance &amp; Filtering Funnel</h2>
  <div class="charts-row">
    {svg_operators}
    {svg_funnel}
  </div>
</section>

<section>
  <h2>Filter Pipeline Summary</h2>
  <table>
    <thead>
      <tr>
        <th>Filter</th><th>Input</th><th>Passed</th><th>Rejected</th>
        <th>Reject Rate</th><th>Common Reason</th>
      </tr>
    </thead>
    <tbody>{filter_rows}</tbody>
  </table>
</section>

<section>
  <h2>Session Detail</h2>
  <table>
    <thead>
      <tr>
        <th>Session</th><th>Operator</th><th>Task</th>
        <th>Attempted</th><th>Accepted</th><th>Rejected</th>
        <th>Quality</th><th>Top Reject</th><th>Other Rejects</th>
      </tr>
    </thead>
    <tbody>{table_rows}</tbody>
  </table>
</section>

<div class="footer">OCI Robot Cloud &mdash; Teleoperation Data Collection Pipeline</div>
</body>
</html>"""
    return html


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Teleoperation demo recording pipeline manager for GR00T fine-tuning."
    )
    parser.add_argument("--mock", action="store_true", default=True,
                        help="Use simulated data (default: True)")
    parser.add_argument("--output", default="/tmp/demo_recording_pipeline.html",
                        help="Output HTML file path")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed for reproducibility")
    args = parser.parse_args()

    rng = random.Random(args.seed)

    print(f"[pipeline] Simulating recording sessions (seed={args.seed}) ...")
    sessions = simulate_all_sessions(rng)

    print("[pipeline] Applying quality filters ...")
    filters = apply_filters(sessions, rng)

    report = build_report(sessions, filters)

    print_session_table(sessions)

    # Filter summary
    print("Filter pipeline:")
    total_att = report.total_accepted + report.total_rejected
    print(f"  Raw demos attempted : {total_att}")
    print(f"  Session-accepted    : {report.total_accepted}  ({report.acceptance_rate*100:.1f}%)")
    for f in filters:
        print(f"  After {f.filter_name:<20}: {f.n_passed}  ({f.rejection_rate*100:.1f}% rejected — {f.common_reject_reason})")
    print(f"\n  Final dataset size  : {filters[-1].n_passed} demos")
    print(f"  Best operator       : {report.best_operator}")

    print(f"\n[pipeline] Writing HTML report to {args.output} ...")
    html = generate_html(report)
    with open(args.output, "w") as fh:
        fh.write(html)
    print(f"[pipeline] Done. Open: file://{args.output}")


if __name__ == "__main__":
    main()
