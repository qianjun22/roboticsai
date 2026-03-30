#!/usr/bin/env python3
"""
robot_calibration_verifier.py — Pre-inference robot calibration quality check.

Verifies joint encoder accuracy, TCP position error, camera-robot extrinsic
calibration, force/torque sensor drift, and gripper width calibration before
running inference. Prevents policy failure from uncalibrated robots.

Usage:
    # Mock run (no hardware):
    python src/eval/robot_calibration_verifier.py --mock --robot franka-01 --output /tmp/robot_calibration.html

    # With specific health level (for demo/testing):
    python src/eval/robot_calibration_verifier.py --mock --robot franka-01 --health 0.75 --output /tmp/robot_calibration.html
"""

import argparse
import math
import random
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class CalibrationCheck:
    check_id: str
    component: str          # joint_encoders / tcp_position / camera_extrinsics / ft_sensor / gripper_width
    measured_value: float
    expected_value: float
    tolerance: float
    unit: str
    error_pct: float
    status: str             # pass / warn / fail
    recommendation: str


@dataclass
class CalibrationReport:
    robot_id: str
    timestamp: str
    overall_status: str     # READY / NEEDS_RECAL / CRITICAL
    checks: List[CalibrationCheck] = field(default_factory=list)
    confidence_score: float = 1.0
    recommended_action: str = ""


# ── Check generation ──────────────────────────────────────────────────────────

def _status_from_error(error_pct: float, warn_threshold: float = 60.0) -> str:
    """Map error percentage of tolerance to pass/warn/fail."""
    if error_pct <= warn_threshold:
        return "pass"
    elif error_pct <= 100.0:
        return "warn"
    else:
        return "fail"


def generate_calibration_checks(
    robot_id: str,
    health: float = 0.9,
    seed: int = 42,
) -> List[CalibrationCheck]:
    """
    Generate 18 calibration checks across 5 components.

    health: 0.0–1.0 controls how well-calibrated the robot is.
            1.0 = perfect; 0.5 = many borderline/failing checks.
    """
    rng = random.Random(seed)
    checks: List[CalibrationCheck] = []

    def noisy(base: float, scale: float) -> float:
        """Add zero-mean Gaussian noise scaled inversely by health."""
        degradation = 1.0 + (1.0 - health) * 4.0   # range: 1× to 5×
        return base + rng.gauss(0, scale * degradation)

    def make_check(
        check_id: str,
        component: str,
        measured: float,
        expected: float,
        tolerance: float,
        unit: str,
        rec_pass: str,
        rec_warn: str,
        rec_fail: str,
    ) -> CalibrationCheck:
        abs_error = abs(measured - expected)
        error_pct = (abs_error / tolerance) * 100.0
        status = _status_from_error(error_pct)
        if status == "pass":
            rec = rec_pass
        elif status == "warn":
            rec = rec_warn
        else:
            rec = rec_fail
        return CalibrationCheck(
            check_id=check_id,
            component=component,
            measured_value=round(measured, 4),
            expected_value=round(expected, 4),
            tolerance=tolerance,
            unit=unit,
            error_pct=round(error_pct, 1),
            status=status,
            recommendation=rec,
        )

    # ── joint_encoders: 7 joints, position error in degrees ──────────────────
    joint_tol = 0.05  # ±0.05 deg
    for j in range(1, 8):
        measured = noisy(0.0, 0.015)
        checks.append(make_check(
            check_id=f"JE-J{j}",
            component="joint_encoders",
            measured=measured,
            expected=0.0,
            tolerance=joint_tol,
            unit="deg",
            rec_pass=f"Joint {j} encoder nominal",
            rec_warn=f"Joint {j} encoder near limit — schedule recalibration",
            rec_fail=f"Joint {j} encoder out of spec — recalibrate before inference",
        ))

    # ── tcp_position: X/Y/Z in mm, rotation in deg ───────────────────────────
    tcp_pos_tol = 0.5   # ±0.5 mm
    tcp_rot_tol = 0.1   # ±0.1 deg
    for axis in ["X", "Y", "Z"]:
        measured = noisy(0.0, 0.12)
        checks.append(make_check(
            check_id=f"TCP-{axis}",
            component="tcp_position",
            measured=measured,
            expected=0.0,
            tolerance=tcp_pos_tol,
            unit="mm",
            rec_pass=f"TCP {axis}-axis position nominal",
            rec_warn=f"TCP {axis}-axis drift — re-run tool calibration routine",
            rec_fail=f"TCP {axis}-axis error exceeds limit — recalibrate TCP immediately",
        ))
    measured_rot = noisy(0.0, 0.03)
    checks.append(make_check(
        check_id="TCP-ROT",
        component="tcp_position",
        measured=measured_rot,
        expected=0.0,
        tolerance=tcp_rot_tol,
        unit="deg",
        rec_pass="TCP rotation nominal",
        rec_warn="TCP rotation drift — re-run tool calibration routine",
        rec_fail="TCP rotation error exceeds limit — recalibrate TCP",
    ))

    # ── camera_extrinsics: translation mm, rotation deg, reprojection px ─────
    cam_trans_tol = 1.0   # ±1.0 mm
    cam_rot_tol   = 0.3   # ±0.3 deg
    cam_reproj_tol = 0.8  # ±0.8 px

    cam_trans = noisy(0.0, 0.25)
    checks.append(make_check(
        check_id="CAM-TRANS",
        component="camera_extrinsics",
        measured=cam_trans,
        expected=0.0,
        tolerance=cam_trans_tol,
        unit="mm",
        rec_pass="Camera translation calibration nominal",
        rec_warn="Camera translation drift — re-run hand-eye calibration",
        rec_fail="Camera translation error critical — hand-eye recalibration required",
    ))

    cam_rot = noisy(0.0, 0.07)
    checks.append(make_check(
        check_id="CAM-ROT",
        component="camera_extrinsics",
        measured=cam_rot,
        expected=0.0,
        tolerance=cam_rot_tol,
        unit="deg",
        rec_pass="Camera rotation calibration nominal",
        rec_warn="Camera rotation drift — re-run hand-eye calibration",
        rec_fail="Camera rotation error critical — hand-eye recalibration required",
    ))

    reproj = abs(noisy(0.0, 0.18)) + 0.05 * (1.0 - health)
    checks.append(make_check(
        check_id="CAM-REPROJ",
        component="camera_extrinsics",
        measured=reproj,
        expected=0.0,
        tolerance=cam_reproj_tol,
        unit="px",
        rec_pass="Reprojection error nominal",
        rec_warn="Reprojection error elevated — collect more calibration targets",
        rec_fail="Reprojection error too high — redo full camera calibration",
    ))

    # ── ft_sensor: zero-drift N and Nm, range test ───────────────────────────
    ft_force_tol  = 0.5   # ±0.5 N
    ft_torque_tol = 0.05  # ±0.05 Nm

    ft_force = noisy(0.0, 0.12)
    checks.append(make_check(
        check_id="FT-ZERO-F",
        component="ft_sensor",
        measured=ft_force,
        expected=0.0,
        tolerance=ft_force_tol,
        unit="N",
        rec_pass="F/T force zero-drift nominal",
        rec_warn="F/T force zero-drift elevated — re-zero sensor before session",
        rec_fail="F/T force zero-drift critical — sensor may be damaged, replace or service",
    ))

    ft_torque = noisy(0.0, 0.012)
    checks.append(make_check(
        check_id="FT-ZERO-T",
        component="ft_sensor",
        measured=ft_torque,
        expected=0.0,
        tolerance=ft_torque_tol,
        unit="Nm",
        rec_pass="F/T torque zero-drift nominal",
        rec_warn="F/T torque zero-drift elevated — re-zero sensor",
        rec_fail="F/T torque zero-drift critical — service required",
    ))

    ft_range_measured = noisy(9.81, 0.18)  # gravity vector magnitude check
    ft_range_expected = 9.81
    checks.append(make_check(
        check_id="FT-RANGE",
        component="ft_sensor",
        measured=ft_range_measured,
        expected=ft_range_expected,
        tolerance=0.3,
        unit="N",
        rec_pass="F/T range test passed",
        rec_warn="F/T range response off — verify sensor mounting",
        rec_fail="F/T range test failed — sensor may need replacement",
    ))

    # ── gripper_width: width error mm, force calibration % ───────────────────
    grip_width_tol = 0.3  # ±0.3 mm
    grip_force_tol = 5.0  # ±5%

    grip_width = noisy(0.0, 0.07)
    checks.append(make_check(
        check_id="GRIP-WIDTH",
        component="gripper_width",
        measured=grip_width,
        expected=0.0,
        tolerance=grip_width_tol,
        unit="mm",
        rec_pass="Gripper width calibration nominal",
        rec_warn="Gripper width drift — re-run gripper calibration sequence",
        rec_fail="Gripper width error exceeds spec — recalibrate gripper",
    ))

    grip_force_err = abs(noisy(0.0, 1.2))
    checks.append(make_check(
        check_id="GRIP-FORCE",
        component="gripper_width",
        measured=grip_force_err,
        expected=0.0,
        tolerance=grip_force_tol,
        unit="%",
        rec_pass="Gripper force calibration nominal",
        rec_warn="Gripper force calibration off — verify finger condition",
        rec_fail="Gripper force error too large — check finger wear and recalibrate",
    ))

    return checks


# ── Confidence scoring ────────────────────────────────────────────────────────

def compute_confidence(checks: List[CalibrationCheck]) -> float:
    """
    Weighted confidence score 0–1.
    Joint encoder failures weighted 3×; TCP failures 2×; others 1×.
    """
    weights = {
        "joint_encoders":    3.0,
        "tcp_position":      2.0,
        "camera_extrinsics": 1.0,
        "ft_sensor":         1.0,
        "gripper_width":     1.0,
    }
    status_score = {"pass": 1.0, "warn": 0.5, "fail": 0.0}

    total_weight = 0.0
    weighted_score = 0.0
    for c in checks:
        w = weights.get(c.component, 1.0)
        total_weight += w
        weighted_score += w * status_score.get(c.status, 0.0)

    return round(weighted_score / total_weight, 3) if total_weight > 0 else 0.0


# ── Overall status ────────────────────────────────────────────────────────────

def compute_overall_status(checks: List[CalibrationCheck]) -> str:
    fail_count = sum(1 for c in checks if c.status == "fail")
    warn_count = sum(1 for c in checks if c.status == "warn")
    if fail_count > 0:
        return "CRITICAL"
    elif warn_count > 0:
        return "NEEDS_RECAL"
    else:
        return "READY"


# ── Recommendation ────────────────────────────────────────────────────────────

def generate_recommendation(report: CalibrationReport) -> str:
    if report.overall_status == "CRITICAL":
        bad_joints = [
            c.check_id.replace("JE-J", "J")
            for c in report.checks
            if c.component == "joint_encoders" and c.status == "fail"
        ]
        bad_others = [
            c.check_id
            for c in report.checks
            if c.component != "joint_encoders" and c.status == "fail"
        ]
        parts = []
        if bad_joints:
            parts.append(f"recalibrate joints {', '.join(bad_joints)}")
        if bad_others:
            parts.append(f"address failing checks: {', '.join(bad_others)}")
        detail = "; ".join(parts) if parts else "recalibrate all failing components"
        return f"Do not run inference — {detail}."
    elif report.overall_status == "NEEDS_RECAL":
        return (
            "Minor drift detected — recalibrate before next DAgger session. "
            "Inference may proceed with caution for non-critical tasks."
        )
    else:
        return "Robot ready for inference. All calibration checks within tolerance."


# ── HTML report ───────────────────────────────────────────────────────────────

_BANNER_COLOR = {
    "READY":       ("#16a34a", "#dcfce7"),   # green
    "NEEDS_RECAL": ("#d97706", "#fef3c7"),   # amber
    "CRITICAL":    ("#dc2626", "#fee2e2"),   # red
}

_STATUS_BADGE = {
    "pass": ('<span style="background:#16a34a;color:#fff;padding:2px 8px;border-radius:4px;font-size:11px;">PASS</span>'),
    "warn": ('<span style="background:#d97706;color:#fff;padding:2px 8px;border-radius:4px;font-size:11px;">WARN</span>'),
    "fail": ('<span style="background:#dc2626;color:#fff;padding:2px 8px;border-radius:4px;font-size:11px;">FAIL</span>'),
}

_COMPONENT_LABELS = {
    "joint_encoders":    "Joint Encoders",
    "tcp_position":      "TCP Position",
    "camera_extrinsics": "Camera Extrinsics",
    "ft_sensor":         "F/T Sensor",
    "gripper_width":     "Gripper",
}

_COMPONENT_ORDER = [
    "joint_encoders", "tcp_position", "camera_extrinsics", "ft_sensor", "gripper_width"
]


def _component_worst_status(checks: List[CalibrationCheck], component: str) -> str:
    statuses = [c.status for c in checks if c.component == component]
    if "fail" in statuses:
        return "fail"
    elif "warn" in statuses:
        return "warn"
    elif "pass" in statuses:
        return "pass"
    return "pass"


def _status_color(status: str) -> str:
    return {"pass": "#16a34a", "warn": "#d97706", "fail": "#dc2626"}.get(status, "#64748b")


def _build_svg_bars(checks: List[CalibrationCheck]) -> str:
    bar_h = 28
    gap = 10
    label_w = 130
    bar_max_w = 340
    total_h = len(_COMPONENT_ORDER) * (bar_h + gap) + 20
    svg_lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{label_w + bar_max_w + 60}" height="{total_h}" style="font-family:sans-serif;">',
    ]
    for i, comp in enumerate(_COMPONENT_ORDER):
        worst = _component_worst_status(checks, comp)
        color = _status_color(worst)
        comp_checks = [c for c in checks if c.component == comp]
        avg_error = sum(c.error_pct for c in comp_checks) / len(comp_checks) if comp_checks else 0
        # bar fill = how healthy (inverse of avg_error/100, clamped)
        health_frac = max(0.0, min(1.0, 1.0 - avg_error / 150.0))
        bar_w = int(bar_max_w * health_frac)
        y = i * (bar_h + gap) + 10
        label = _COMPONENT_LABELS.get(comp, comp)
        # Background track
        svg_lines.append(
            f'<rect x="{label_w}" y="{y}" width="{bar_max_w}" height="{bar_h}" rx="4" fill="#334155"/>'
        )
        # Filled bar
        if bar_w > 0:
            svg_lines.append(
                f'<rect x="{label_w}" y="{y}" width="{bar_w}" height="{bar_h}" rx="4" fill="{color}"/>'
            )
        # Label
        svg_lines.append(
            f'<text x="{label_w - 8}" y="{y + bar_h // 2 + 5}" text-anchor="end" '
            f'fill="#cbd5e1" font-size="12">{label}</text>'
        )
        # Percentage text
        pct_text = f"{health_frac*100:.0f}%"
        svg_lines.append(
            f'<text x="{label_w + bar_max_w + 6}" y="{y + bar_h // 2 + 5}" '
            f'fill="{color}" font-size="12" font-weight="bold">{pct_text}</text>'
        )
    svg_lines.append("</svg>")
    return "\n".join(svg_lines)


def _worst_component(checks: List[CalibrationCheck]) -> str:
    for comp in _COMPONENT_ORDER:
        if _component_worst_status(checks, comp) == "fail":
            return _COMPONENT_LABELS.get(comp, comp)
    for comp in _COMPONENT_ORDER:
        if _component_worst_status(checks, comp) == "warn":
            return _COMPONENT_LABELS.get(comp, comp)
    return "None"


def build_html_report(report: CalibrationReport) -> str:
    banner_fg, banner_bg = _BANNER_COLOR.get(
        report.overall_status, ("#6b7280", "#f3f4f6")
    )
    n_pass = sum(1 for c in report.checks if c.status == "pass")
    n_total = len(report.checks)
    worst_comp = _worst_component(report.checks)
    svg_bars = _build_svg_bars(report.checks)

    # Check table rows
    rows_html = ""
    for c in report.checks:
        badge = _STATUS_BADGE.get(c.status, "")
        err_color = _status_color(c.status)
        rows_html += f"""
        <tr>
          <td style="padding:8px 10px;color:#94a3b8;font-size:12px;">{c.check_id}</td>
          <td style="padding:8px 10px;color:#e2e8f0;font-size:12px;">{_COMPONENT_LABELS.get(c.component, c.component)}</td>
          <td style="padding:8px 10px;text-align:right;color:#e2e8f0;font-size:12px;">{c.measured_value:.4f} {c.unit}</td>
          <td style="padding:8px 10px;text-align:right;color:#94a3b8;font-size:12px;">±{c.tolerance} {c.unit}</td>
          <td style="padding:8px 10px;text-align:right;color:{err_color};font-size:12px;font-weight:bold;">{c.error_pct:.1f}%</td>
          <td style="padding:8px 10px;text-align:center;">{badge}</td>
          <td style="padding:8px 10px;color:#94a3b8;font-size:11px;">{c.recommendation}</td>
        </tr>"""

    action_bg = {"READY": "#14532d", "NEEDS_RECAL": "#78350f", "CRITICAL": "#7f1d1d"}.get(
        report.overall_status, "#1e293b"
    )
    action_border = banner_fg

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Robot Calibration Report — {report.robot_id}</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #1e293b; color: #e2e8f0; font-family: 'Segoe UI', Arial, sans-serif; padding: 32px; }}
    h1 {{ color: #C74634; font-size: 22px; margin-bottom: 4px; }}
    .subtitle {{ color: #64748b; font-size: 13px; margin-bottom: 24px; }}
    .banner {{ background: {banner_bg}; color: {banner_fg}; border-radius: 10px;
               padding: 18px 28px; font-size: 32px; font-weight: 900;
               letter-spacing: 3px; text-align: center; margin-bottom: 28px; }}
    .kpi-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 28px; }}
    .kpi {{ background: #0f172a; border-radius: 8px; padding: 18px; text-align: center; }}
    .kpi .val {{ font-size: 26px; font-weight: 700; color: #f8fafc; }}
    .kpi .lbl {{ font-size: 11px; color: #64748b; margin-top: 4px; text-transform: uppercase; letter-spacing: 1px; }}
    .section {{ background: #0f172a; border-radius: 8px; padding: 20px 24px; margin-bottom: 24px; }}
    .section h2 {{ color: #C74634; font-size: 14px; text-transform: uppercase;
                   letter-spacing: 1px; margin-bottom: 16px; }}
    table {{ width: 100%; border-collapse: collapse; }}
    thead th {{ background: #1e293b; color: #64748b; font-size: 11px; text-transform: uppercase;
                letter-spacing: 1px; padding: 8px 10px; text-align: left; }}
    tbody tr:nth-child(even) {{ background: #0a1120; }}
    tbody tr:hover {{ background: #1a2744; }}
    .action-box {{ background: {action_bg}; border: 2px solid {action_border};
                   border-radius: 8px; padding: 16px 22px; }}
    .action-box .action-title {{ color: {banner_fg}; font-weight: 700; font-size: 13px;
                                  text-transform: uppercase; letter-spacing: 1px; margin-bottom: 6px; }}
    .action-box .action-text {{ color: #f8fafc; font-size: 14px; line-height: 1.6; }}
    .footer {{ color: #334155; font-size: 11px; text-align: center; margin-top: 24px; }}
  </style>
</head>
<body>
  <h1>OCI Robot Cloud — Calibration Verifier</h1>
  <div class="subtitle">Robot: {report.robot_id} &nbsp;|&nbsp; {report.timestamp}</div>

  <div class="banner">{report.overall_status}</div>

  <div class="kpi-grid">
    <div class="kpi">
      <div class="val" style="color:{banner_fg};">{report.overall_status}</div>
      <div class="lbl">Overall Status</div>
    </div>
    <div class="kpi">
      <div class="val">{report.confidence_score:.2f}</div>
      <div class="lbl">Confidence Score</div>
    </div>
    <div class="kpi">
      <div class="val">{n_pass}/{n_total}</div>
      <div class="lbl">Checks Passed</div>
    </div>
    <div class="kpi">
      <div class="val" style="font-size:18px;">{worst_comp}</div>
      <div class="lbl">Worst Component</div>
    </div>
  </div>

  <div class="section">
    <h2>Component Health</h2>
    {svg_bars}
  </div>

  <div class="section">
    <h2>Calibration Checks ({n_total} total)</h2>
    <table>
      <thead>
        <tr>
          <th>Check ID</th>
          <th>Component</th>
          <th style="text-align:right;">Measured</th>
          <th style="text-align:right;">Tolerance</th>
          <th style="text-align:right;">Error %</th>
          <th style="text-align:center;">Status</th>
          <th>Recommendation</th>
        </tr>
      </thead>
      <tbody>{rows_html}
      </tbody>
    </table>
  </div>

  <div class="section">
    <h2>Recommended Action</h2>
    <div class="action-box">
      <div class="action-title">Next Step</div>
      <div class="action-text">{report.recommended_action}</div>
    </div>
  </div>

  <div class="footer">
    Generated by robot_calibration_verifier.py &nbsp;|&nbsp; OCI Robot Cloud &nbsp;|&nbsp; {report.timestamp}
  </div>
</body>
</html>"""
    return html


# ── CLI entry point ───────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Verify robot calibration quality before inference."
    )
    parser.add_argument("--mock", action="store_true",
                        help="Generate mock calibration data (no hardware required)")
    parser.add_argument("--robot", default="franka-01",
                        help="Robot ID (default: franka-01)")
    parser.add_argument("--health", type=float, default=0.92,
                        help="Simulated health level 0.0–1.0 (default: 0.92)")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed for reproducible mock data")
    parser.add_argument("--output", default="/tmp/robot_calibration.html",
                        help="Path for HTML output (default: /tmp/robot_calibration.html)")
    args = parser.parse_args()

    if not args.mock:
        print("[WARN] Live hardware mode not yet implemented — falling back to mock.")

    print(f"[calibration] Generating checks for robot '{args.robot}' (health={args.health:.2f}) ...")
    checks = generate_calibration_checks(
        robot_id=args.robot,
        health=args.health,
        seed=args.seed,
    )

    overall_status = compute_overall_status(checks)
    confidence = compute_confidence(checks)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    report = CalibrationReport(
        robot_id=args.robot,
        timestamp=timestamp,
        overall_status=overall_status,
        checks=checks,
        confidence_score=confidence,
    )
    report.recommended_action = generate_recommendation(report)

    n_pass = sum(1 for c in checks if c.status == "pass")
    n_warn = sum(1 for c in checks if c.status == "warn")
    n_fail = sum(1 for c in checks if c.status == "fail")
    print(f"[calibration] Status: {overall_status}  |  Confidence: {confidence:.2f}")
    print(f"[calibration] Checks — pass: {n_pass}  warn: {n_warn}  fail: {n_fail}")
    print(f"[calibration] Action: {report.recommended_action}")

    html = build_html_report(report)
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    print(f"[calibration] HTML report saved → {out_path}")


if __name__ == "__main__":
    main()
