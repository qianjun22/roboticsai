#!/usr/bin/env python3
"""
deployment_rollback_manager.py

Manages safe deployment and automated rollback for GR00T model updates in production.

Deployment slots: blue (active), green (canary), rollback (last-known-good)
Canary traffic ramp: 10% → 25% → 50% → 100% over 4 phases
Rollback triggers: SR drop >15% rel, p95 >450ms, error_rate >2%, MAE regression >20%

CLI:  python deployment_rollback_manager.py --mock --output /tmp/deployment_rollback_manager.html --seed 42
"""

from __future__ import annotations

import argparse
import json
import math
import random
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

TRAFFIC_PHASES = [10, 25, 50, 100]

ROLLBACK_THRESHOLDS = {
    "sr_drop_rel": 0.15,    # 15% relative drop in success rate
    "p95_ms": 450.0,
    "error_rate": 0.02,
    "mae_regression_rel": 0.20,  # 20% relative increase in MAE
}


@dataclass
class PhaseMetrics:
    phase: int                 # 1-based
    traffic_pct: int
    sr: float
    p50_ms: float
    p95_ms: float
    error_rate: float
    mae: float
    status: str                # "advancing" | "promoted" | "rolled_back"
    rollback_reason: Optional[str] = None


@dataclass
class ScenarioResult:
    name: str
    description: str
    outcome: str               # "promoted" | "rolled_back"
    baseline: dict
    phases: list[PhaseMetrics] = field(default_factory=list)
    promotion_time_s: Optional[float] = None
    rollback_at_phase: Optional[int] = None


# ---------------------------------------------------------------------------
# Rollback evaluation
# ---------------------------------------------------------------------------

def check_rollback_triggers(metrics: PhaseMetrics, baseline: dict) -> Optional[str]:
    """Return a reason string if any rollback trigger fires, else None."""
    # Success-rate relative drop
    sr_drop = (baseline["sr"] - metrics.sr) / baseline["sr"]
    if sr_drop > ROLLBACK_THRESHOLDS["sr_drop_rel"]:
        return (
            f"SR regression: {metrics.sr:.1%} vs baseline {baseline['sr']:.1%} "
            f"({sr_drop:.1%} relative drop)"
        )

    # p95 latency ceiling
    if metrics.p95_ms > ROLLBACK_THRESHOLDS["p95_ms"]:
        return f"p95 latency: {metrics.p95_ms:.0f}ms > {ROLLBACK_THRESHOLDS['p95_ms']:.0f}ms"

    # Error rate
    if metrics.error_rate > ROLLBACK_THRESHOLDS["error_rate"]:
        return (
            f"Error rate: {metrics.error_rate:.2%} > "
            f"{ROLLBACK_THRESHOLDS['error_rate']:.2%}"
        )

    # MAE regression
    mae_regression = (metrics.mae - baseline["mae"]) / baseline["mae"]
    if mae_regression > ROLLBACK_THRESHOLDS["mae_regression_rel"]:
        return (
            f"MAE regression: {metrics.mae:.4f} vs baseline {baseline['mae']:.4f} "
            f"({mae_regression:.1%} relative increase)"
        )

    return None


# ---------------------------------------------------------------------------
# Scenario simulations
# ---------------------------------------------------------------------------

def simulate_scenario(name: str, rng: random.Random) -> ScenarioResult:
    """Dispatch to per-scenario simulation."""
    scenarios = {
        "clean_deploy": _scenario_clean_deploy,
        "latency_spike": _scenario_latency_spike,
        "sr_regression": _scenario_sr_regression,
        "error_burst": _scenario_error_burst,
        "gradual_degradation": _scenario_gradual_degradation,
        "hotfix_deploy": _scenario_hotfix_deploy,
    }
    return scenarios[name](rng)


def _make_baseline(sr=0.82, p50=95.0, p95=210.0, error_rate=0.005, mae=0.103) -> dict:
    return dict(sr=sr, p50_ms=p50, p95_ms=p95, error_rate=error_rate, mae=mae)


def _run_phases(
    baseline: dict,
    phase_overrides: dict,   # phase_num (1-based) -> partial metric overrides
    name: str,
    description: str,
    rng: random.Random,
    hotfix: bool = False,
) -> ScenarioResult:
    """Generic phase runner: apply overrides per phase, check triggers."""
    result = ScenarioResult(
        name=name,
        description=description,
        outcome="promoted",
        baseline=baseline,
    )
    start = time.monotonic()

    for i, traffic_pct in enumerate(TRAFFIC_PHASES, start=1):
        # Base metrics slightly better than baseline (healthy canary)
        m = dict(
            sr=baseline["sr"] * rng.uniform(1.005, 1.02),
            p50_ms=baseline["p50_ms"] * rng.uniform(0.90, 1.05),
            p95_ms=baseline["p95_ms"] * rng.uniform(0.90, 1.08),
            error_rate=baseline["error_rate"] * rng.uniform(0.8, 1.1),
            mae=baseline["mae"] * rng.uniform(0.92, 0.99),
        )
        # Apply overrides for this phase
        if i in phase_overrides:
            m.update(phase_overrides[i])

        pm = PhaseMetrics(
            phase=i,
            traffic_pct=traffic_pct,
            sr=m["sr"],
            p50_ms=m["p50_ms"],
            p95_ms=m["p95_ms"],
            error_rate=m["error_rate"],
            mae=m["mae"],
            status="advancing",
        )

        trigger = check_rollback_triggers(pm, baseline)
        if trigger:
            pm.status = "rolled_back"
            pm.rollback_reason = trigger
            result.phases.append(pm)
            result.outcome = "rolled_back"
            result.rollback_at_phase = i
            break

        if i == 4:
            pm.status = "promoted"
            result.promotion_time_s = round(time.monotonic() - start, 4)
        result.phases.append(pm)

    return result


def _scenario_clean_deploy(rng: random.Random) -> ScenarioResult:
    baseline = _make_baseline()
    overrides = {
        1: dict(sr=0.845, p95_ms=195.0, error_rate=0.003, mae=0.095),
        2: dict(sr=0.852, p95_ms=188.0, error_rate=0.003, mae=0.094),
        3: dict(sr=0.860, p95_ms=182.0, error_rate=0.002, mae=0.092),
        4: dict(sr=0.868, p95_ms=178.0, error_rate=0.002, mae=0.091),
    }
    return _run_phases(
        baseline, overrides,
        name="clean_deploy",
        description="Metrics improve at each phase → promoted to 100%",
        rng=rng,
    )


def _scenario_latency_spike(rng: random.Random) -> ScenarioResult:
    baseline = _make_baseline()
    overrides = {
        1: dict(sr=0.840, p95_ms=200.0, error_rate=0.004, mae=0.100),
        2: dict(sr=0.838, p95_ms=512.0, error_rate=0.006, mae=0.101),  # spike!
    }
    return _run_phases(
        baseline, overrides,
        name="latency_spike",
        description="p95 spike at phase 2 → rollback",
        rng=rng,
    )


def _scenario_sr_regression(rng: random.Random) -> ScenarioResult:
    baseline = _make_baseline()
    overrides = {
        1: dict(sr=0.825, p95_ms=205.0, error_rate=0.005, mae=0.104),
        2: dict(sr=0.810, p95_ms=215.0, error_rate=0.006, mae=0.106),
        3: dict(sr=0.685, p95_ms=220.0, error_rate=0.007, mae=0.108),  # SR drops 16.7%
    }
    return _run_phases(
        baseline, overrides,
        name="sr_regression",
        description="SR drops 16.7% at phase 3 → rollback",
        rng=rng,
    )


def _scenario_error_burst(rng: random.Random) -> ScenarioResult:
    baseline = _make_baseline()
    overrides = {
        1: dict(sr=0.830, p95_ms=208.0, error_rate=0.038, mae=0.105),  # error burst!
    }
    return _run_phases(
        baseline, overrides,
        name="error_burst",
        description="Error rate spike at phase 1 → immediate rollback",
        rng=rng,
    )


def _scenario_gradual_degradation(rng: random.Random) -> ScenarioResult:
    baseline = _make_baseline()
    # SR creeps down slowly — only crosses threshold at phase 4
    overrides = {
        1: dict(sr=0.816, p95_ms=212.0, error_rate=0.005, mae=0.105),
        2: dict(sr=0.803, p95_ms=218.0, error_rate=0.006, mae=0.107),
        3: dict(sr=0.793, p95_ms=224.0, error_rate=0.007, mae=0.109),
        4: dict(sr=0.692, p95_ms=230.0, error_rate=0.008, mae=0.112),  # crosses 15%
    }
    return _run_phases(
        baseline, overrides,
        name="gradual_degradation",
        description="Slow SR degradation detected at phase 4 → rollback",
        rng=rng,
    )


def _scenario_hotfix_deploy(rng: random.Random) -> ScenarioResult:
    """Emergency hotfix: bypass canary, fast-track to 100%."""
    baseline = _make_baseline()
    # Only 2 phases: 10% → 100% (bypass 25/50)
    result = ScenarioResult(
        name="hotfix_deploy",
        description="Emergency deploy with bypass → fast-track to 100%",
        outcome="promoted",
        baseline=baseline,
    )
    start = time.monotonic()

    hotfix_phases = [(1, 10), (4, 100)]  # phase index, traffic_pct
    hotfix_metrics = {
        1: dict(sr=0.855, p95_ms=185.0, error_rate=0.003, mae=0.098),
        4: dict(sr=0.862, p95_ms=180.0, error_rate=0.002, mae=0.097),
    }

    for phase_num, traffic_pct in hotfix_phases:
        m = hotfix_metrics[phase_num]
        pm = PhaseMetrics(
            phase=phase_num,
            traffic_pct=traffic_pct,
            sr=m["sr"],
            p50_ms=baseline["p50_ms"] * rng.uniform(0.88, 0.95),
            p95_ms=m["p95_ms"],
            error_rate=m["error_rate"],
            mae=m["mae"],
            status="advancing" if phase_num != 4 else "promoted",
        )
        trigger = check_rollback_triggers(pm, baseline)
        if trigger:
            pm.status = "rolled_back"
            pm.rollback_reason = trigger
            result.phases.append(pm)
            result.outcome = "rolled_back"
            result.rollback_at_phase = phase_num
            return result
        result.phases.append(pm)

    result.promotion_time_s = round(time.monotonic() - start, 4)
    return result


# ---------------------------------------------------------------------------
# Run all scenarios
# ---------------------------------------------------------------------------

SCENARIO_NAMES = [
    "clean_deploy",
    "latency_spike",
    "sr_regression",
    "error_burst",
    "gradual_degradation",
    "hotfix_deploy",
]


def run_all_scenarios(seed: int = 42) -> list[ScenarioResult]:
    rng = random.Random(seed)
    return [simulate_scenario(name, rng) for name in SCENARIO_NAMES]


# ---------------------------------------------------------------------------
# Console output
# ---------------------------------------------------------------------------

def print_console_table(results: list[ScenarioResult]) -> None:
    print("\n" + "=" * 80)
    print("  GR00T Deployment Rollback Manager — Scenario Results")
    print("=" * 80)
    header = f"{'Scenario':<25} {'Outcome':<14} {'Phases':<8} {'Rollback @':<12} {'Promo Time'}"
    print(header)
    print("-" * 80)
    for r in results:
        rb_phase = f"Phase {r.rollback_at_phase}" if r.rollback_at_phase else "—"
        promo = f"{r.promotion_time_s:.4f}s" if r.promotion_time_s else "—"
        outcome_tag = "PROMOTED" if r.outcome == "promoted" else "ROLLED_BACK"
        print(f"{r.name:<25} {outcome_tag:<14} {len(r.phases):<8} {rb_phase:<12} {promo}")
    print("=" * 80)

    promoted = [r for r in results if r.outcome == "promoted"]
    rolled_back = [r for r in results if r.outcome == "rolled_back"]
    avg_promo = (
        sum(r.promotion_time_s for r in promoted if r.promotion_time_s)
        / len(promoted)
        if promoted else 0
    )
    print(f"\n  Promoted: {len(promoted)}   Rolled Back: {len(rolled_back)}")
    print(f"  Avg promotion time: {avg_promo:.4f}s\n")


# ---------------------------------------------------------------------------
# SVG timeline helpers
# ---------------------------------------------------------------------------

def _build_svg_timeline(results: list[ScenarioResult]) -> str:
    """Generate an SVG showing traffic % ramp per scenario."""
    W, H = 820, 340
    pad_l, pad_r, pad_t, pad_b = 160, 30, 30, 50

    chart_w = W - pad_l - pad_r
    chart_h = H - pad_t - pad_b

    # Color palette
    COLOR_PROMOTED = "#4ade80"
    COLOR_ROLLED = "#f87171"
    COLOR_GRID = "#374151"
    COLOR_AXIS = "#9ca3af"
    COLOR_TEXT = "#e5e7eb"
    COLOR_BG = "#1f2937"

    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}">')
    lines.append(f'  <rect width="{W}" height="{H}" fill="{COLOR_BG}" rx="8"/>')

    # Title
    lines.append(
        f'  <text x="{W//2}" y="20" fill="{COLOR_TEXT}" font-size="13" '
        f'font-family="monospace" text-anchor="middle" font-weight="bold">'
        f'Canary Traffic Ramp by Scenario</text>'
    )

    # Grid lines (y: 0, 25, 50, 75, 100)
    for pct in [0, 25, 50, 75, 100]:
        y = pad_t + chart_h - (pct / 100) * chart_h
        lines.append(
            f'  <line x1="{pad_l}" y1="{y:.1f}" x2="{pad_l+chart_w}" y2="{y:.1f}" '
            f'stroke="{COLOR_GRID}" stroke-width="1" stroke-dasharray="4,3"/>'
        )
        lines.append(
            f'  <text x="{pad_l-8}" y="{y+4:.1f}" fill="{COLOR_AXIS}" '
            f'font-size="10" font-family="monospace" text-anchor="end">{pct}%</text>'
        )

    # X axis label
    lines.append(
        f'  <text x="{pad_l + chart_w//2}" y="{H-4}" fill="{COLOR_AXIS}" '
        f'font-size="10" font-family="monospace" text-anchor="middle">Deployment Phase</text>'
    )

    # Phase x positions (phases 1-4, with 0 as origin = 0%)
    all_phases = [0, 1, 2, 3, 4]
    x_positions = {p: pad_l + (p / 4) * chart_w for p in all_phases}

    # X tick labels
    for p in [1, 2, 3, 4]:
        x = x_positions[p]
        lines.append(
            f'  <text x="{x:.1f}" y="{pad_t + chart_h + 16}" fill="{COLOR_AXIS}" '
            f'font-size="10" font-family="monospace" text-anchor="middle">{p}</text>'
        )

    # Draw scenario lines
    for idx, r in enumerate(results):
        color = COLOR_PROMOTED if r.outcome == "promoted" else COLOR_ROLLED

        # Build (x, y) points: start at (0, 0%) then each phase
        points = [(x_positions[0], pad_t + chart_h)]
        for pm in r.phases:
            x = x_positions[pm.phase]
            y = pad_t + chart_h - (pm.traffic_pct / 100) * chart_h
            points.append((x, y))

        # Polyline
        pts_str = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
        lines.append(
            f'  <polyline points="{pts_str}" fill="none" stroke="{color}" '
            f'stroke-width="2.2" opacity="0.85"/>'
        )

        # Dots at each phase
        for pm in r.phases:
            x = x_positions[pm.phase]
            y = pad_t + chart_h - (pm.traffic_pct / 100) * chart_h
            dot_color = COLOR_ROLLED if pm.status == "rolled_back" else color
            r_dot = 5 if pm.status == "rolled_back" else 3.5
            lines.append(
                f'  <circle cx="{x:.1f}" cy="{y:.1f}" r="{r_dot}" '
                f'fill="{dot_color}" stroke="#111827" stroke-width="1"/>'
            )

        # Label on the right
        if points:
            lx, ly = points[-1]
            lines.append(
                f'  <text x="{lx+6:.1f}" y="{ly+4:.1f}" fill="{color}" '
                f'font-size="9" font-family="monospace">{r.name}</text>'
            )

    lines.append("</svg>")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# HTML generation
# ---------------------------------------------------------------------------

def _phase_card_html(phase: PhaseMetrics, baseline: dict) -> str:
    if phase.status == "rolled_back":
        border = "#ef4444"
        badge = '<span style="background:#ef4444;color:#fff;padding:2px 8px;border-radius:4px;font-size:11px;">ROLLED_BACK</span>'
    elif phase.status == "promoted":
        border = "#4ade80"
        badge = '<span style="background:#4ade80;color:#111;padding:2px 8px;border-radius:4px;font-size:11px;">PROMOTED</span>'
    else:
        border = "#3b82f6"
        badge = '<span style="background:#3b82f6;color:#fff;padding:2px 8px;border-radius:4px;font-size:11px;">ADVANCING</span>'

    sr_delta = phase.sr - baseline["sr"]
    sr_color = "#4ade80" if sr_delta >= 0 else "#f87171"
    mae_delta = phase.mae - baseline["mae"]
    mae_color = "#f87171" if mae_delta > 0 else "#4ade80"
    p95_color = "#f87171" if phase.p95_ms > ROLLBACK_THRESHOLDS["p95_ms"] else "#9ca3af"
    err_color = "#f87171" if phase.error_rate > ROLLBACK_THRESHOLDS["error_rate"] else "#9ca3af"

    rb_html = ""
    if phase.rollback_reason:
        rb_html = f'<div style="margin-top:6px;padding:6px 8px;background:#450a0a;border-left:3px solid #ef4444;font-size:11px;color:#fca5a5;border-radius:2px;">Trigger: {phase.rollback_reason}</div>'

    return f"""
      <div style="border:1px solid {border};border-radius:6px;padding:12px;background:#1f2937;flex:1;min-width:140px;">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
          <span style="color:#9ca3af;font-size:11px;font-family:monospace;">Phase {phase.phase} ({phase.traffic_pct}%)</span>
          {badge}
        </div>
        <table style="width:100%;font-size:12px;border-collapse:collapse;">
          <tr><td style="color:#6b7280;padding:2px 0;">SR</td>
              <td style="color:{sr_color};text-align:right;">{phase.sr:.1%} ({sr_delta:+.1%})</td></tr>
          <tr><td style="color:#6b7280;padding:2px 0;">p50</td>
              <td style="color:#9ca3af;text-align:right;">{phase.p50_ms:.0f}ms</td></tr>
          <tr><td style="color:#6b7280;padding:2px 0;">p95</td>
              <td style="color:{p95_color};text-align:right;">{phase.p95_ms:.0f}ms</td></tr>
          <tr><td style="color:#6b7280;padding:2px 0;">Error</td>
              <td style="color:{err_color};text-align:right;">{phase.error_rate:.2%}</td></tr>
          <tr><td style="color:#6b7280;padding:2px 0;">MAE</td>
              <td style="color:{mae_color};text-align:right;">{phase.mae:.4f} ({mae_delta:+.4f})</td></tr>
        </table>
        {rb_html}
      </div>"""


def _scenario_section_html(r: ScenarioResult) -> str:
    outcome_color = "#4ade80" if r.outcome == "promoted" else "#ef4444"
    outcome_label = "PROMOTED" if r.outcome == "promoted" else "ROLLED BACK"
    promo_info = ""
    if r.promotion_time_s is not None:
        promo_info = f' &nbsp;|&nbsp; Promotion time: {r.promotion_time_s:.4f}s'
    rb_info = ""
    if r.rollback_at_phase:
        rb_info = f' &nbsp;|&nbsp; Rollback at phase {r.rollback_at_phase}'

    phase_cards = "".join(_phase_card_html(p, r.baseline) for p in r.phases)

    return f"""
    <div style="margin-bottom:28px;border:1px solid #374151;border-radius:10px;overflow:hidden;">
      <div style="background:#111827;padding:12px 18px;display:flex;justify-content:space-between;align-items:center;">
        <div>
          <span style="font-family:monospace;font-size:15px;color:#e5e7eb;font-weight:700;">{r.name}</span>
          <span style="color:#6b7280;font-size:12px;margin-left:12px;">{r.description}</span>
        </div>
        <div style="font-size:13px;">
          <span style="color:{outcome_color};font-weight:700;">{outcome_label}</span>
          <span style="color:#6b7280;font-size:11px;">{promo_info}{rb_info}</span>
        </div>
      </div>
      <div style="padding:14px 14px 14px;">
        <div style="font-size:11px;color:#6b7280;margin-bottom:8px;">
          Baseline: SR {r.baseline['sr']:.1%} &nbsp;|&nbsp;
          p95 {r.baseline['p95_ms']:.0f}ms &nbsp;|&nbsp;
          Error {r.baseline['error_rate']:.2%} &nbsp;|&nbsp;
          MAE {r.baseline['mae']:.4f}
        </div>
        <div style="display:flex;gap:10px;flex-wrap:wrap;">
          {phase_cards}
        </div>
      </div>
    </div>"""


def _rollback_trigger_table(results: list[ScenarioResult]) -> str:
    trigger_counts = {
        "SR regression (>15% rel)": 0,
        "p95 latency (>450ms)": 0,
        "Error rate (>2%)": 0,
        "MAE regression (>20% rel)": 0,
    }
    for r in results:
        for p in r.phases:
            if p.rollback_reason:
                reason = p.rollback_reason
                if reason.startswith("SR regression"):
                    trigger_counts["SR regression (>15% rel)"] += 1
                elif reason.startswith("p95 latency"):
                    trigger_counts["p95 latency (>450ms)"] += 1
                elif reason.startswith("Error rate"):
                    trigger_counts["Error rate (>2%)"] += 1
                elif reason.startswith("MAE regression"):
                    trigger_counts["MAE regression (>20% rel)"] += 1

    rows = ""
    for trigger, count in trigger_counts.items():
        bar_w = count * 60
        bar_html = (
            f'<div style="display:inline-block;width:{bar_w}px;height:12px;'
            f'background:#ef4444;border-radius:2px;vertical-align:middle;"></div>'
            if count > 0 else "<span style='color:#4b5563'>—</span>"
        )
        rows += f"""
          <tr>
            <td style="padding:8px 14px;color:#e5e7eb;font-family:monospace;font-size:12px;">{trigger}</td>
            <td style="padding:8px 14px;text-align:center;color:#f87171;font-weight:700;">{count}</td>
            <td style="padding:8px 14px;">{bar_html}</td>
          </tr>"""

    return f"""
    <h2 style="color:#e5e7eb;font-size:16px;margin:28px 0 12px;font-family:monospace;">
      Rollback Trigger Frequency
    </h2>
    <table style="width:100%;border-collapse:collapse;background:#1f2937;border-radius:8px;overflow:hidden;">
      <thead>
        <tr style="background:#111827;">
          <th style="padding:10px 14px;text-align:left;color:#9ca3af;font-size:12px;">Trigger Condition</th>
          <th style="padding:10px 14px;text-align:center;color:#9ca3af;font-size:12px;">Fires</th>
          <th style="padding:10px 14px;color:#9ca3af;font-size:12px;">Frequency</th>
        </tr>
      </thead>
      <tbody>{rows}</tbody>
    </table>"""


def generate_html(results: list[ScenarioResult]) -> str:
    promoted = [r for r in results if r.outcome == "promoted"]
    rolled_back = [r for r in results if r.outcome == "rolled_back"]
    avg_promo = (
        sum(r.promotion_time_s for r in promoted if r.promotion_time_s) / len(promoted)
        if promoted else 0
    )
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    svg_timeline = _build_svg_timeline(results)
    scenario_sections = "".join(_scenario_section_html(r) for r in results)
    trigger_table = _rollback_trigger_table(results)

    summary_cards = f"""
    <div style="display:flex;gap:16px;flex-wrap:wrap;margin-bottom:24px;">
      <div style="flex:1;min-width:160px;background:#1f2937;border-radius:8px;padding:16px;border-left:4px solid #4ade80;">
        <div style="color:#6b7280;font-size:12px;font-family:monospace;">Promoted</div>
        <div style="color:#4ade80;font-size:32px;font-weight:700;">{len(promoted)}</div>
        <div style="color:#4b5563;font-size:11px;">of {len(results)} scenarios</div>
      </div>
      <div style="flex:1;min-width:160px;background:#1f2937;border-radius:8px;padding:16px;border-left:4px solid #ef4444;">
        <div style="color:#6b7280;font-size:12px;font-family:monospace;">Rolled Back</div>
        <div style="color:#ef4444;font-size:32px;font-weight:700;">{len(rolled_back)}</div>
        <div style="color:#4b5563;font-size:11px;">of {len(results)} scenarios</div>
      </div>
      <div style="flex:1;min-width:160px;background:#1f2937;border-radius:8px;padding:16px;border-left:4px solid #60a5fa;">
        <div style="color:#6b7280;font-size:12px;font-family:monospace;">Avg Promo Time</div>
        <div style="color:#60a5fa;font-size:32px;font-weight:700;">{avg_promo:.3f}s</div>
        <div style="color:#4b5563;font-size:11px;">promoted scenarios</div>
      </div>
      <div style="flex:1;min-width:160px;background:#1f2937;border-radius:8px;padding:16px;border-left:4px solid #a78bfa;">
        <div style="color:#6b7280;font-size:12px;font-family:monospace;">Traffic Ramp</div>
        <div style="color:#a78bfa;font-size:22px;font-weight:700;">10→25→50→100%</div>
        <div style="color:#4b5563;font-size:11px;">4-phase canary</div>
      </div>
    </div>"""

    best_practices = """
    <h2 style="color:#e5e7eb;font-size:16px;margin:28px 0 12px;font-family:monospace;">
      Best Practices
    </h2>
    <div style="background:#1f2937;border-radius:8px;padding:18px;font-size:13px;color:#d1d5db;line-height:1.8;">
      <div style="margin-bottom:6px;">
        <span style="color:#4ade80;">&#10003;</span>
        <strong>Always keep a rollback slot:</strong> Maintain <code style="background:#111827;padding:1px 5px;border-radius:3px;">rollback</code> slot pointing to last-known-good before any promotion.
      </div>
      <div style="margin-bottom:6px;">
        <span style="color:#4ade80;">&#10003;</span>
        <strong>Evaluate metrics at every phase:</strong> Don't skip intermediate canary checks — latency and error spikes often appear before full traffic.
      </div>
      <div style="margin-bottom:6px;">
        <span style="color:#4ade80;">&#10003;</span>
        <strong>Relative thresholds beat absolute:</strong> SR and MAE triggers use relative change to handle different baseline models gracefully.
      </div>
      <div style="margin-bottom:6px;">
        <span style="color:#4ade80;">&#10003;</span>
        <strong>Hotfix bypass with caution:</strong> Fast-track skips phases 2-3; only use when security/critical regression outweighs canary safety.
      </div>
      <div style="margin-bottom:6px;">
        <span style="color:#4ade80;">&#10003;</span>
        <strong>Automated rollback is non-negotiable:</strong> Human review is too slow for p95 spikes in real-time inference; automate the trigger, notify async.
      </div>
      <div>
        <span style="color:#4ade80;">&#10003;</span>
        <strong>Slot swap is atomic:</strong> Blue/green routing update must be a single pointer swap — never tear down blue before green is validated.
      </div>
    </div>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>GR00T Deployment Rollback Manager</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #111827; color: #e5e7eb; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; padding: 24px; }}
    code {{ font-family: monospace; }}
    a {{ color: #60a5fa; }}
  </style>
</head>
<body>
  <div style="max-width:960px;margin:0 auto;">
    <div style="margin-bottom:24px;">
      <h1 style="font-size:22px;font-weight:700;color:#f9fafb;font-family:monospace;">
        GR00T Deployment Rollback Manager
      </h1>
      <p style="color:#6b7280;font-size:12px;margin-top:4px;">
        Generated: {ts} &nbsp;|&nbsp; Slots: blue (active) / green (canary) / rollback (LKG)
      </p>
    </div>

    <h2 style="color:#e5e7eb;font-size:16px;margin:0 0 14px;font-family:monospace;">Summary</h2>
    {summary_cards}

    <h2 style="color:#e5e7eb;font-size:16px;margin:0 0 14px;font-family:monospace;">
      Canary Traffic Ramp — All Scenarios
    </h2>
    <div style="margin-bottom:28px;border-radius:8px;overflow:hidden;">
      {svg_timeline}
    </div>

    <h2 style="color:#e5e7eb;font-size:16px;margin:0 0 14px;font-family:monospace;">
      Per-Scenario Phase Detail
    </h2>
    {scenario_sections}

    {trigger_table}
    {best_practices}

    <p style="margin-top:28px;color:#374151;font-size:11px;text-align:center;font-family:monospace;">
      OCI Robot Cloud · GR00T N1.6 · Deployment Rollback Manager v1.0
    </p>
  </div>
</body>
</html>"""
    return html


# ---------------------------------------------------------------------------
# JSON output
# ---------------------------------------------------------------------------

def build_json_output(results: list[ScenarioResult]) -> dict:
    promoted = [r for r in results if r.outcome == "promoted"]
    rolled_back = [r for r in results if r.outcome == "rolled_back"]
    avg_promo = (
        sum(r.promotion_time_s for r in promoted if r.promotion_time_s) / len(promoted)
        if promoted else None
    )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "total_scenarios": len(results),
            "promoted": len(promoted),
            "rolled_back": len(rolled_back),
            "avg_promotion_time_s": avg_promo,
        },
        "thresholds": ROLLBACK_THRESHOLDS,
        "traffic_phases_pct": TRAFFIC_PHASES,
        "scenarios": [
            {
                "name": r.name,
                "description": r.description,
                "outcome": r.outcome,
                "rollback_at_phase": r.rollback_at_phase,
                "promotion_time_s": r.promotion_time_s,
                "baseline": r.baseline,
                "phases": [asdict(p) for p in r.phases],
            }
            for r in results
        ],
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="GR00T Deployment Rollback Manager — simulates canary deployments with automated rollback"
    )
    parser.add_argument("--mock", action="store_true", help="Run with simulated data (default mode)")
    parser.add_argument("--output", default="/tmp/deployment_rollback_manager.html", help="HTML output path")
    parser.add_argument("--json-output", default="/tmp/deployment_rollback_manager.json", help="JSON output path")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    args = parser.parse_args()

    print(f"[deployment_rollback_manager] Running {len(SCENARIO_NAMES)} scenarios (seed={args.seed}) ...")
    results = run_all_scenarios(seed=args.seed)

    print_console_table(results)

    # HTML
    html = generate_html(results)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[HTML] Written to {args.output}")

    # JSON
    data = build_json_output(results)
    with open(args.json_output, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"[JSON] Written to {args.json_output}")


if __name__ == "__main__":
    main()
