#!/usr/bin/env python3
"""
data_flywheel_tracker.py — OCI Robot Cloud Data Flywheel Metrics Tracker

Tracks how customer usage generates training data which improves the model,
which attracts more customers (the flywheel effect).

Flywheel stages:
  customers → robot_hours → demos_collected → model_quality → customer_growth

CLI: python3 data_flywheel_tracker.py --mock --output /tmp/data_flywheel_tracker.html --seed 42

stdlib only, self-contained.
"""

import argparse
import json
import math
import random
import sys
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import List


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class MonthMetrics:
    month_idx: int          # 1–12
    month_label: str        # "Jan-2026"
    n_partners: int
    robot_hours_mo: float
    demos_mo: int
    cumulative_demos: int
    mae: float
    sr: float               # success rate 0–1
    model_version: str
    revenue_mo: float       # USD
    arr: float              # annualised recurring revenue
    compute_cost_mo: float  # USD
    gross_margin_pct: float
    flywheel_velocity: float  # demos_per_partner


# ---------------------------------------------------------------------------
# Simulation
# ---------------------------------------------------------------------------

MONTH_NAMES = ["Jan","Feb","Mar","Apr","May","Jun",
               "Jul","Aug","Sep","Oct","Nov","Dec"]


def lerp(a: float, b: float, t: float) -> float:
    """Linear interpolation."""
    return a + (b - a) * t


def simulate_flywheel(seed: int = 42) -> List[MonthMetrics]:
    """
    Simulate 12 months (Jan–Dec 2026) of flywheel acceleration.

    Anchor points (month idx is 1-based):
      Month  1: 1 partner,  40 hr/mo, 200 demos,  SR 5%
      Month  6: 3 partners, 180 hr/mo, 1800 demos, SR 45%
      Month 12: 8 partners, 520 hr/mo, 8200 demos, SR 78%
    """
    rng = random.Random(seed)

    # Piecewise anchor nodes  (month, partners, robot_hours, demos_mo, sr, mae)
    anchors = [
        (1,  1, 40.0,  200,  0.05, 0.45),
        (6,  3, 180.0, 1800, 0.45, 0.18),
        (12, 8, 520.0, 8200, 0.78, 0.03),
    ]

    def interp_anchor(month: int, idx: int) -> float:
        """Interpolate anchor column `idx` (0=month,1=partners,...) for a given month."""
        for i in range(len(anchors) - 1):
            m0, m1 = anchors[i][0], anchors[i+1][0]
            if m0 <= month <= m1:
                t = (month - m0) / (m1 - m0)
                return lerp(anchors[i][idx], anchors[i+1][idx], t)
        # Clamp
        return anchors[-1][idx]

    results: List[MonthMetrics] = []
    cumulative_demos = 0
    model_major = 1
    model_minor = 0
    prev_sr = 0.0

    for m in range(1, 13):
        label = f"{MONTH_NAMES[m-1]}-2026"

        # Core flywheel metrics (interpolated + small noise)
        n_partners_f = interp_anchor(m, 1)
        n_partners = max(1, round(n_partners_f + rng.gauss(0, 0.2)))
        n_partners = min(n_partners, 8)  # cap at Dec anchor

        robot_hours_mo = max(1.0, interp_anchor(m, 2) * rng.uniform(0.93, 1.07))
        demos_mo_f = interp_anchor(m, 3)
        demos_mo = max(50, round(demos_mo_f * rng.uniform(0.95, 1.05)))
        cumulative_demos += demos_mo

        sr_target = interp_anchor(m, 4)
        # SR can only increase monotonically (model doesn't regress in production)
        sr = max(prev_sr, sr_target * rng.uniform(0.97, 1.03))
        sr = min(sr, 0.99)
        prev_sr = sr

        mae_target = interp_anchor(m, 5)
        mae = max(0.01, mae_target * rng.uniform(0.97, 1.03))

        # Model versioning: bump minor each month, major at months 4 and 9
        if m in (4, 9):
            model_major += 1
            model_minor = 0
        else:
            model_minor += 1
        model_version = f"v{model_major}.{model_minor}"

        # Revenue model: $2000/mo per partner base + $0.50/robot_hour overage
        BASE_REVENUE_PER_PARTNER = 2000.0
        OVERAGE_RATE = 0.50  # per robot-hour
        BASE_HOURS_INCLUDED = 60.0  # hours included in base fee
        overage_hours = max(0.0, robot_hours_mo - BASE_HOURS_INCLUDED * n_partners)
        revenue_mo = n_partners * BASE_REVENUE_PER_PARTNER + overage_hours * OVERAGE_RATE
        arr = revenue_mo * 12

        # Compute cost: $4.20/hr × compute_utilization (scales with demos)
        # Utilization ramps from ~20% at start to ~85% at end
        util_frac = lerp(0.20, 0.85, (m - 1) / 11)
        compute_hours = robot_hours_mo * util_frac * rng.uniform(0.98, 1.02)
        compute_cost_mo = 4.20 * compute_hours

        gross_margin_pct = (revenue_mo - compute_cost_mo) / revenue_mo * 100 if revenue_mo > 0 else 0.0

        flywheel_velocity = demos_mo / n_partners  # demos per partner this month

        results.append(MonthMetrics(
            month_idx=m,
            month_label=label,
            n_partners=n_partners,
            robot_hours_mo=round(robot_hours_mo, 1),
            demos_mo=demos_mo,
            cumulative_demos=cumulative_demos,
            mae=round(mae, 4),
            sr=round(sr, 4),
            model_version=model_version,
            revenue_mo=round(revenue_mo, 2),
            arr=round(arr, 2),
            compute_cost_mo=round(compute_cost_mo, 2),
            gross_margin_pct=round(gross_margin_pct, 1),
            flywheel_velocity=round(flywheel_velocity, 1),
        ))

    return results


# ---------------------------------------------------------------------------
# Console output
# ---------------------------------------------------------------------------

def print_table(metrics: List[MonthMetrics]) -> None:
    hdr = (
        f"{'Month':<10} {'Partners':>9} {'RobotHr':>9} {'Demos':>7} "
        f"{'CumDemos':>9} {'MAE':>7} {'SR%':>6} {'Model':<8} "
        f"{'Rev($)':>9} {'ARR($)':>11} {'CostMo($)':>10} {'Margin%':>8} {'Demo/Ptnr':>10}"
    )
    sep = "-" * len(hdr)
    print("\n=== OCI Robot Cloud — Data Flywheel Metrics 2026 ===\n")
    print(hdr)
    print(sep)
    for m in metrics:
        print(
            f"{m.month_label:<10} {m.n_partners:>9} {m.robot_hours_mo:>9.1f} {m.demos_mo:>7} "
            f"{m.cumulative_demos:>9} {m.mae:>7.4f} {m.sr*100:>5.1f}% {m.model_version:<8} "
            f"{m.revenue_mo:>9,.0f} {m.arr:>11,.0f} {m.compute_cost_mo:>10,.0f} "
            f"{m.gross_margin_pct:>7.1f}% {m.flywheel_velocity:>10.1f}"
        )
    print(sep)
    dec = metrics[-1]
    jan = metrics[0]
    print(f"\nKey takeaways (Jan → Dec 2026):")
    print(f"  Partners:    {jan.n_partners} → {dec.n_partners}  ({dec.n_partners/jan.n_partners:.0f}x)")
    print(f"  Demos/month: {jan.demos_mo:,} → {dec.demos_mo:,}  ({dec.demos_mo/jan.demos_mo:.0f}x)")
    print(f"  Success rate:{jan.sr*100:.0f}% → {dec.sr*100:.0f}%")
    print(f"  MAE:         {jan.mae:.4f} → {dec.mae:.4f}  ({dec.mae/jan.mae:.2f}x)")
    print(f"  ARR:         ${jan.arr:,.0f} → ${dec.arr:,.0f}  ({dec.arr/jan.arr:.1f}x)")
    print(f"  Gross margin:{jan.gross_margin_pct:.1f}% → {dec.gross_margin_pct:.1f}%")
    print(f"  Cumul. demos:{dec.cumulative_demos:,}")
    print()


# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------

def _svg_polyline(points: List[tuple], color: str, fill: str = "none",
                  stroke_width: int = 2, opacity: float = 1.0) -> str:
    pts = " ".join(f"{x:.2f},{y:.2f}" for x, y in points)
    if fill != "none":
        # Close path for area fill
        close = f"{points[-1][0]:.2f},{points[0][1]:.2f} {points[0][0]:.2f},{points[0][1]:.2f}"
        return (
            f'<polygon points="{pts} {close}" fill="{fill}" opacity="{opacity}" stroke="none"/>'
            f'<polyline points="{pts}" fill="none" stroke="{color}" '
            f'stroke-width="{stroke_width}" stroke-linejoin="round" stroke-linecap="round"/>'
        )
    return (
        f'<polyline points="{pts}" fill="none" stroke="{color}" '
        f'stroke-width="{stroke_width}" stroke-linejoin="round" stroke-linecap="round" opacity="{opacity}"/>'
    )


def _scale(values: List[float], v_min: float, v_max: float,
           out_lo: float, out_hi: float) -> List[float]:
    span = v_max - v_min if v_max != v_min else 1.0
    return [out_lo + (v - v_min) / span * (out_hi - out_lo) for v in values]


def build_partner_demo_chart(metrics: List[MonthMetrics]) -> str:
    """SVG area chart: partner growth + demo accumulation (dual-axis)."""
    W, H = 720, 260
    pad_l, pad_r, pad_t, pad_b = 55, 80, 20, 40
    cw = W - pad_l - pad_r
    ch = H - pad_t - pad_b

    months = [m.month_label for m in metrics]
    partners = [float(m.n_partners) for m in metrics]
    cum_demos = [float(m.cumulative_demos) for m in metrics]

    n = len(months)
    xs = [pad_l + i / (n - 1) * cw for i in range(n)]

    # Partner area (left axis, max ~10)
    p_max = max(partners) * 1.2
    p_ys = [pad_t + ch - (v / p_max) * ch for v in partners]

    # Cumulative demos (right axis)
    d_max = max(cum_demos) * 1.1
    d_ys = [pad_t + ch - (v / d_max) * ch for v in cum_demos]

    p_pts = list(zip(xs, p_ys))
    d_pts = list(zip(xs, d_ys))

    # Y-axis gridlines
    grid = ""
    for tick in range(0, 5):
        y = pad_t + tick / 4 * ch
        grid += f'<line x1="{pad_l}" y1="{y:.1f}" x2="{pad_l+cw}" y2="{y:.1f}" stroke="#334155" stroke-width="1"/>'

    # X-axis labels
    x_labels = ""
    for i, m in enumerate(months):
        x = xs[i]
        lbl = m.split("-")[0]  # "Jan"
        x_labels += f'<text x="{x:.1f}" y="{H-8}" text-anchor="middle" fill="#94a3b8" font-size="11">{lbl}</text>'

    # Left Y-axis labels (partners)
    y_labels_l = ""
    for tick in range(5):
        v = p_max * (4 - tick) / 4
        y = pad_t + tick / 4 * ch
        y_labels_l += f'<text x="{pad_l-6}" y="{y+4:.1f}" text-anchor="end" fill="#60a5fa" font-size="10">{v:.0f}</text>'
    y_labels_l += f'<text x="12" y="{H//2}" text-anchor="middle" fill="#60a5fa" font-size="11" transform="rotate(-90,12,{H//2})">Partners</text>'

    # Right Y-axis labels (cumulative demos)
    y_labels_r = ""
    for tick in range(5):
        v = d_max * (4 - tick) / 4
        y = pad_t + tick / 4 * ch
        lbl = f"{v/1000:.0f}k" if v >= 1000 else f"{v:.0f}"
        y_labels_r += f'<text x="{pad_l+cw+6}" y="{y+4:.1f}" text-anchor="start" fill="#a78bfa" font-size="10">{lbl}</text>'
    y_labels_r += (
        f'<text x="{W-10}" y="{H//2}" text-anchor="middle" fill="#a78bfa" font-size="11" '
        f'transform="rotate(90,{W-10},{H//2})">Cumul. Demos</text>'
    )

    partner_area = _svg_polyline(p_pts, "#3b82f6", fill="#1d4ed830", stroke_width=2, opacity=0.9)
    demo_area = _svg_polyline(d_pts, "#8b5cf6", fill="#5b21b620", stroke_width=2, opacity=0.9)

    # Dots
    dots = ""
    for i, (x, y) in enumerate(p_pts):
        dots += f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="#3b82f6"/>'
    for i, (x, y) in enumerate(d_pts):
        dots += f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="#8b5cf6"/>'

    # Legend
    legend = (
        f'<rect x="{pad_l}" y="{pad_t}" width="12" height="12" fill="#3b82f6" rx="2"/>'
        f'<text x="{pad_l+16}" y="{pad_t+10}" fill="#94a3b8" font-size="11">Partners</text>'
        f'<rect x="{pad_l+90}" y="{pad_t}" width="12" height="12" fill="#8b5cf6" rx="2"/>'
        f'<text x="{pad_l+106}" y="{pad_t+10}" fill="#94a3b8" font-size="11">Cumulative Demos</text>'
    )

    svg = (
        f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:{W}px">'
        f'{grid}{x_labels}{y_labels_l}{y_labels_r}'
        f'{demo_area}{partner_area}{dots}{legend}'
        f'<line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t+ch}" stroke="#475569" stroke-width="1"/>'
        f'<line x1="{pad_l}" y1="{pad_t+ch}" x2="{pad_l+cw}" y2="{pad_t+ch}" stroke="#475569" stroke-width="1"/>'
        f'</svg>'
    )
    return svg


def build_model_quality_chart(metrics: List[MonthMetrics]) -> str:
    """SVG line chart: MAE (left axis, decreasing) + SR% (right axis, increasing)."""
    W, H = 720, 260
    pad_l, pad_r, pad_t, pad_b = 55, 65, 20, 40
    cw = W - pad_l - pad_r
    ch = H - pad_t - pad_b

    months = [m.month_label for m in metrics]
    maes = [m.mae for m in metrics]
    srs = [m.sr * 100 for m in metrics]
    n = len(months)
    xs = [pad_l + i / (n - 1) * cw for i in range(n)]

    mae_max = max(maes) * 1.1
    sr_max = 100.0

    mae_ys = [pad_t + ch - (v / mae_max) * ch for v in maes]
    sr_ys  = [pad_t + ch - (v / sr_max) * ch for v in srs]

    mae_pts = list(zip(xs, mae_ys))
    sr_pts  = list(zip(xs, sr_ys))

    grid = ""
    for tick in range(5):
        y = pad_t + tick / 4 * ch
        grid += f'<line x1="{pad_l}" y1="{y:.1f}" x2="{pad_l+cw}" y2="{y:.1f}" stroke="#334155" stroke-width="1"/>'

    x_labels = ""
    for i, m in enumerate(months):
        x = xs[i]
        lbl = m.split("-")[0]
        x_labels += f'<text x="{x:.1f}" y="{H-8}" text-anchor="middle" fill="#94a3b8" font-size="11">{lbl}</text>'

    y_labels_l = ""
    for tick in range(5):
        v = mae_max * (4 - tick) / 4
        y = pad_t + tick / 4 * ch
        y_labels_l += f'<text x="{pad_l-6}" y="{y+4:.1f}" text-anchor="end" fill="#f97316" font-size="10">{v:.3f}</text>'
    y_labels_l += f'<text x="12" y="{H//2}" text-anchor="middle" fill="#f97316" font-size="11" transform="rotate(-90,12,{H//2})">MAE</text>'

    y_labels_r = ""
    for tick in range(5):
        v = sr_max * (4 - tick) / 4
        y = pad_t + tick / 4 * ch
        y_labels_r += f'<text x="{pad_l+cw+6}" y="{y+4:.1f}" text-anchor="start" fill="#22c55e" font-size="10">{v:.0f}%</text>'
    y_labels_r += (
        f'<text x="{W-10}" y="{H//2}" text-anchor="middle" fill="#22c55e" font-size="11" '
        f'transform="rotate(90,{W-10},{H//2})">Success Rate %</text>'
    )

    mae_line = _svg_polyline(mae_pts, "#f97316", stroke_width=2)
    sr_line  = _svg_polyline(sr_pts, "#22c55e", stroke_width=2)

    dots = ""
    for x, y in mae_pts:
        dots += f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="#f97316"/>'
    for x, y in sr_pts:
        dots += f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="#22c55e"/>'

    legend = (
        f'<line x1="{pad_l}" y1="{pad_t+6}" x2="{pad_l+24}" y2="{pad_t+6}" stroke="#f97316" stroke-width="2"/>'
        f'<text x="{pad_l+28}" y="{pad_t+10}" fill="#94a3b8" font-size="11">MAE (↓ better)</text>'
        f'<line x1="{pad_l+140}" y1="{pad_t+6}" x2="{pad_l+164}" y2="{pad_t+6}" stroke="#22c55e" stroke-width="2"/>'
        f'<text x="{pad_l+168}" y="{pad_t+10}" fill="#94a3b8" font-size="11">Success Rate % (↑ better)</text>'
    )

    svg = (
        f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:{W}px">'
        f'{grid}{x_labels}{y_labels_l}{y_labels_r}'
        f'{mae_line}{sr_line}{dots}{legend}'
        f'<line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t+ch}" stroke="#475569" stroke-width="1"/>'
        f'<line x1="{pad_l}" y1="{pad_t+ch}" x2="{pad_l+cw}" y2="{pad_t+ch}" stroke="#475569" stroke-width="1"/>'
        f'</svg>'
    )
    return svg


def build_revenue_cost_chart(metrics: List[MonthMetrics]) -> str:
    """SVG area chart: revenue vs compute cost — margin expansion."""
    W, H = 720, 260
    pad_l, pad_r, pad_t, pad_b = 65, 25, 20, 40
    cw = W - pad_l - pad_r
    ch = H - pad_t - pad_b

    months = [m.month_label for m in metrics]
    revenues = [m.revenue_mo for m in metrics]
    costs = [m.compute_cost_mo for m in metrics]
    n = len(months)
    xs = [pad_l + i / (n - 1) * cw for i in range(n)]

    v_max = max(revenues) * 1.1
    rev_ys  = [pad_t + ch - (v / v_max) * ch for v in revenues]
    cost_ys = [pad_t + ch - (v / v_max) * ch for v in costs]

    rev_pts  = list(zip(xs, rev_ys))
    cost_pts = list(zip(xs, cost_ys))

    grid = ""
    for tick in range(5):
        y = pad_t + tick / 4 * ch
        v = v_max * (4 - tick) / 4
        lbl = f"${v/1000:.0f}k" if v >= 1000 else f"${v:.0f}"
        grid += f'<line x1="{pad_l}" y1="{y:.1f}" x2="{pad_l+cw}" y2="{y:.1f}" stroke="#334155" stroke-width="1"/>'
        grid += f'<text x="{pad_l-6}" y="{y+4:.1f}" text-anchor="end" fill="#94a3b8" font-size="10">{lbl}</text>'

    x_labels = ""
    for i, m in enumerate(months):
        lbl = m.split("-")[0]
        x_labels += f'<text x="{xs[i]:.1f}" y="{H-8}" text-anchor="middle" fill="#94a3b8" font-size="11">{lbl}</text>'

    rev_area  = _svg_polyline(rev_pts, "#C74634", fill="#C7463430", stroke_width=2)
    cost_area = _svg_polyline(cost_pts, "#64748b", fill="#64748b25", stroke_width=2)

    dots = ""
    for x, y in rev_pts:
        dots += f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="#C74634"/>'
    for x, y in cost_pts:
        dots += f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="#64748b"/>'

    legend = (
        f'<rect x="{pad_l}" y="{pad_t}" width="12" height="12" fill="#C74634" rx="2" opacity="0.8"/>'
        f'<text x="{pad_l+16}" y="{pad_t+10}" fill="#94a3b8" font-size="11">Monthly Revenue</text>'
        f'<rect x="{pad_l+140}" y="{pad_t}" width="12" height="12" fill="#64748b" rx="2" opacity="0.6"/>'
        f'<text x="{pad_l+156}" y="{pad_t+10}" fill="#94a3b8" font-size="11">Compute Cost</text>'
    )

    svg = (
        f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:{W}px">'
        f'{grid}{x_labels}'
        f'{rev_area}{cost_area}{dots}{legend}'
        f'<line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t+ch}" stroke="#475569" stroke-width="1"/>'
        f'<line x1="{pad_l}" y1="{pad_t+ch}" x2="{pad_l+cw}" y2="{pad_t+ch}" stroke="#475569" stroke-width="1"/>'
        f'</svg>'
    )
    return svg


# ---------------------------------------------------------------------------
# HTML report
# ---------------------------------------------------------------------------

def generate_html(metrics: List[MonthMetrics]) -> str:
    dec = metrics[-1]
    jan = metrics[0]
    total_demos = dec.cumulative_demos
    final_sr = dec.sr * 100
    final_arr = dec.arr

    chart1 = build_partner_demo_chart(metrics)
    chart2 = build_model_quality_chart(metrics)
    chart3 = build_revenue_cost_chart(metrics)

    # Summary cards
    cards_data = [
        ("Design Partners (Dec)", str(dec.n_partners), "#3b82f6"),
        ("Cumulative Demos", f"{total_demos:,}", "#8b5cf6"),
        ("Final Success Rate", f"{final_sr:.0f}%", "#22c55e"),
        ("Dec ARR", f"${final_arr/1000:.0f}k", "#C74634"),
        ("Gross Margin (Dec)", f"{dec.gross_margin_pct:.0f}%", "#f59e0b"),
        ("MAE Improvement", f"{jan.mae/dec.mae:.1f}x", "#06b6d4"),
    ]

    cards_html = ""
    for label, value, color in cards_data:
        cards_html += f"""
        <div style="background:#0f172a;border:1px solid #1e3a5f;border-radius:8px;padding:20px;text-align:center;min-width:130px;flex:1;">
          <div style="font-size:28px;font-weight:700;color:{color};margin-bottom:6px;">{value}</div>
          <div style="font-size:12px;color:#94a3b8;text-transform:uppercase;letter-spacing:0.05em;">{label}</div>
        </div>"""

    # Flywheel acceleration table
    table_rows = ""
    for m in metrics:
        margin_color = "#22c55e" if m.gross_margin_pct > 60 else ("#f59e0b" if m.gross_margin_pct > 30 else "#ef4444")
        table_rows += f"""
        <tr style="border-bottom:1px solid #1e293b;">
          <td style="padding:8px 12px;color:#e2e8f0;">{m.month_label}</td>
          <td style="padding:8px 12px;text-align:center;color:#3b82f6;">{m.n_partners}</td>
          <td style="padding:8px 12px;text-align:right;color:#8b5cf6;">{m.flywheel_velocity:.0f}</td>
          <td style="padding:8px 12px;text-align:right;color:#22c55e;">{m.sr*100:.1f}%</td>
          <td style="padding:8px 12px;text-align:right;color:#f97316;">{m.mae:.4f}</td>
          <td style="padding:8px 12px;text-align:right;color:#C74634;">${m.arr/1000:.1f}k</td>
          <td style="padding:8px 12px;text-align:right;color:{margin_color};">{m.gross_margin_pct:.1f}%</td>
          <td style="padding:8px 12px;text-align:center;color:#64748b;">{m.model_version}</td>
        </tr>"""

    # Compute ARR growth multiple for callout
    arr_multiple = round(dec.arr / jan.arr, 1) if jan.arr > 0 else 0
    demo_velocity_jan = jan.flywheel_velocity
    demo_velocity_dec = dec.flywheel_velocity

    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>OCI Robot Cloud — Data Flywheel Tracker</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: #1e293b; color: #e2e8f0; min-height: 100vh; }}
    .container {{ max-width: 900px; margin: 0 auto; padding: 32px 20px; }}
    h1 {{ font-size: 26px; font-weight: 700; color: #f1f5f9; margin-bottom: 4px; }}
    .subtitle {{ font-size: 14px; color: #64748b; margin-bottom: 32px; }}
    h2 {{ font-size: 16px; font-weight: 600; color: #94a3b8; text-transform: uppercase;
          letter-spacing: 0.08em; margin-bottom: 16px; margin-top: 36px; }}
    .cards {{ display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 32px; }}
    .chart-box {{ background: #0f172a; border: 1px solid #1e3a5f; border-radius: 10px;
                  padding: 20px; margin-bottom: 28px; }}
    .chart-title {{ font-size: 14px; color: #94a3b8; margin-bottom: 14px; font-weight: 600; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
    thead tr {{ background: #0f172a; }}
    thead th {{ padding: 10px 12px; text-align: left; color: #64748b;
                font-weight: 600; text-transform: uppercase; font-size: 11px;
                letter-spacing: 0.06em; border-bottom: 2px solid #1e3a5f; }}
    thead th:not(:first-child) {{ text-align: center; }}
    thead th:nth-child(n+3) {{ text-align: right; }}
    tbody tr:hover {{ background: #1a2840; }}
    .flywheel-callout {{
      background: linear-gradient(135deg, #1a0a08 0%, #2d0f0a 100%);
      border: 1px solid #C74634;
      border-radius: 10px;
      padding: 24px;
      margin-top: 32px;
    }}
    .flywheel-callout h3 {{ color: #C74634; font-size: 16px; margin-bottom: 14px; }}
    .flywheel-callout p {{ color: #cbd5e1; font-size: 14px; line-height: 1.7; margin-bottom: 10px; }}
    .flywheel-callout ul {{ color: #94a3b8; font-size: 13px; line-height: 1.8; padding-left: 20px; }}
    .flywheel-callout li {{ margin-bottom: 4px; }}
    .flywheel-callout strong {{ color: #f1f5f9; }}
    .stage-flow {{
      display: flex; gap: 0; align-items: center; flex-wrap: wrap;
      margin: 16px 0; padding: 16px; background: #0f172a; border-radius: 8px;
    }}
    .stage {{ background: #1e3a5f; border-radius: 6px; padding: 8px 14px;
               font-size: 12px; color: #93c5fd; font-weight: 600; white-space: nowrap; }}
    .arrow {{ color: #C74634; font-size: 18px; padding: 0 6px; font-weight: 700; }}
    footer {{ margin-top: 40px; font-size: 12px; color: #475569; text-align: center; }}
    .oracle-badge {{ color: #C74634; font-weight: 700; }}
  </style>
</head>
<body>
<div class="container">

  <h1>OCI Robot Cloud — Data Flywheel Tracker</h1>
  <div class="subtitle">2026 Simulation &bull; Jan–Dec 2026 &bull; Generated {generated_at}</div>

  <h2>Summary — December 2026</h2>
  <div class="cards">
    {cards_html}
  </div>

  <div class="stage-flow">
    <div class="stage">Customers</div>
    <span class="arrow">&#8594;</span>
    <div class="stage">Robot Hours</div>
    <span class="arrow">&#8594;</span>
    <div class="stage">Demos Collected</div>
    <span class="arrow">&#8594;</span>
    <div class="stage">Model Quality ↑</div>
    <span class="arrow">&#8594;</span>
    <div class="stage">Customer Growth</div>
    <span class="arrow">&#8594;</span>
    <div class="stage" style="background:#7f1d1d;color:#fca5a5;">&#8635; Flywheel</div>
  </div>

  <h2>Partner Growth &amp; Demo Accumulation</h2>
  <div class="chart-box">
    <div class="chart-title">Partners (left) and Cumulative Demos (right) over 12 months</div>
    {chart1}
  </div>

  <h2>Model Quality Convergence</h2>
  <div class="chart-box">
    <div class="chart-title">MAE decreasing &#8595; and Success Rate increasing &#8593; — driven by data flywheel</div>
    {chart2}
  </div>

  <h2>Revenue vs Compute Cost — Margin Expansion</h2>
  <div class="chart-box">
    <div class="chart-title">Monthly Revenue (red) vs Compute Cost (gray) — margin widens as model efficiency improves</div>
    {chart3}
  </div>

  <h2>Flywheel Acceleration Table</h2>
  <div class="chart-box" style="padding:0;overflow:hidden;">
    <table>
      <thead>
        <tr>
          <th>Month</th>
          <th style="text-align:center">Partners</th>
          <th style="text-align:right">Demos/Partner</th>
          <th style="text-align:right">Success Rate</th>
          <th style="text-align:right">MAE</th>
          <th style="text-align:right">ARR</th>
          <th style="text-align:right">Gross Margin</th>
          <th style="text-align:center">Model</th>
        </tr>
      </thead>
      <tbody>
        {table_rows}
      </tbody>
    </table>
  </div>

  <div class="flywheel-callout">
    <h3>&#9881; The Flywheel Effect</h3>
    <p>OCI Robot Cloud is designed around a self-reinforcing data flywheel where each customer
    interaction accelerates improvement for all customers:</p>
    <ul>
      <li><strong>Jan 2026:</strong> 1 design partner, {demo_velocity_jan:.0f} demos/partner/month, SR {jan.sr*100:.0f}%, MAE {jan.mae:.3f}</li>
      <li><strong>Jun 2026:</strong> Flywheel gains momentum — model improvements drive partner renewals + referrals</li>
      <li><strong>Dec 2026:</strong> {dec.n_partners} partners, <strong>{demo_velocity_dec:.0f} demos/partner/month</strong>, SR {dec.sr*100:.0f}%, MAE {dec.mae:.4f}</li>
      <li>Cumulative dataset: <strong>{total_demos:,} demonstrations</strong> — proprietary moat competitors cannot replicate</li>
      <li>ARR grew <strong>{arr_multiple}x</strong> (${jan.arr/1000:.0f}k → ${dec.arr/1000:.0f}k) as margin expanded from {jan.gross_margin_pct:.0f}% to {dec.gross_margin_pct:.0f}%</li>
    </ul>
    <p style="margin-top:14px;font-size:13px;color:#64748b;">
      Key insight: <em>demos_per_partner</em> (flywheel velocity) grows {demo_velocity_dec/demo_velocity_jan:.1f}x because each new partner
      adds diverse robot configurations that improve generalization, reducing per-partner compute cost and
      increasing value delivered — a classic winner-take-most dynamic.
    </p>
  </div>

  <footer>
    <span class="oracle-badge">Oracle Cloud Infrastructure</span> &bull;
    OCI Robot Cloud &bull; Confidential &bull;
    Data Flywheel Tracker v1.0
  </footer>

</div>
</body>
</html>"""

    return html


# ---------------------------------------------------------------------------
# JSON output
# ---------------------------------------------------------------------------

def generate_json(metrics: List[MonthMetrics]) -> str:
    dec = metrics[-1]
    jan = metrics[0]
    payload = {
        "generated_at": datetime.now().isoformat(),
        "simulation": "OCI Robot Cloud Data Flywheel 2026",
        "summary": {
            "final_partners": dec.n_partners,
            "cumulative_demos": dec.cumulative_demos,
            "final_sr_pct": round(dec.sr * 100, 1),
            "final_arr_usd": dec.arr,
            "final_mae": dec.mae,
            "arr_growth_multiple": round(dec.arr / jan.arr, 2) if jan.arr else None,
            "mae_improvement_multiple": round(jan.mae / dec.mae, 2) if dec.mae else None,
            "final_gross_margin_pct": dec.gross_margin_pct,
        },
        "months": [asdict(m) for m in metrics],
    }
    return json.dumps(payload, indent=2)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="OCI Robot Cloud — Data Flywheel Metrics Tracker"
    )
    parser.add_argument("--mock", action="store_true",
                        help="Run simulation with mock/generated data (default)")
    parser.add_argument("--output", default="/tmp/data_flywheel_tracker.html",
                        help="Path for HTML output (default: /tmp/data_flywheel_tracker.html)")
    parser.add_argument("--json-output", default=None,
                        help="Optional path for JSON output")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed for simulation (default: 42)")
    parser.add_argument("--no-html", action="store_true",
                        help="Skip HTML generation (console + JSON only)")
    args = parser.parse_args()

    print("OCI Robot Cloud — Data Flywheel Tracker")
    print("=" * 50)
    print(f"Seed: {args.seed} | Output: {args.output}")

    metrics = simulate_flywheel(seed=args.seed)

    # Console table
    print_table(metrics)

    # HTML
    if not args.no_html:
        html_content = generate_html(metrics)
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(html_content)
        print(f"HTML report written to: {args.output}")

    # JSON
    json_path = args.json_output
    if json_path is None:
        import os
        base = os.path.splitext(args.output)[0]
        json_path = base + ".json"

    json_content = generate_json(metrics)
    with open(json_path, "w", encoding="utf-8") as f:
        f.write(json_content)
    print(f"JSON output written to:  {json_path}")


if __name__ == "__main__":
    main()
