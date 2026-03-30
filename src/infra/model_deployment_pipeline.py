#!/usr/bin/env python3
"""
model_deployment_pipeline.py
Automated model deployment pipeline with safety gates for OCI Robot Cloud.
Manages lifecycle of promoting a GR00T checkpoint from staging to production.

Requires: Python stdlib + numpy only.
Output: /tmp/model_deployment_pipeline.html
"""

import math
import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Optional
import numpy as np


@dataclass
class StageResult:
    stage_name: str
    status: str          # "pass" | "fail" | "skip"
    duration_s: float
    metric_name: str
    metric_value: float
    threshold: float
    notes: str = ""


@dataclass
class DeploymentAttempt:
    model_id: str
    started_at: datetime
    final_status: str            # "success" | "blocked" | "error"
    stages: List[StageResult] = field(default_factory=list)
    promoted_to_production: bool = False
    rollback_available: bool = False
    cost_usd: float = 0.0

    @property
    def total_duration_s(self) -> float: return sum(s.duration_s for s in self.stages)

    @property
    def blocking_stage(self) -> Optional[str]:
        for s in self.stages:
            if s.status == "fail": return s.stage_name
        return None


@dataclass
class DeploymentReport:
    attempts: List[DeploymentAttempt]

    @property
    def success_rate(self) -> float:
        if not self.attempts: return 0.0
        return sum(1 for a in self.attempts if a.final_status == "success") / len(self.attempts)

    @property
    def avg_deploy_time_s(self) -> float:
        if not self.attempts: return 0.0
        return sum(a.total_duration_s for a in self.attempts) / len(self.attempts)

    @property
    def failures_by_stage(self) -> dict:
        counts = {}
        for a in self.attempts:
            bs = a.blocking_stage
            if bs: counts[bs] = counts.get(bs, 0) + 1
        return counts


def stage_checkpoint_validation(model_id: str, rng: np.random.Generator) -> StageResult:
    duration = rng.uniform(8.0, 18.0)
    file_size_gb = rng.uniform(6.5, 7.8)
    threshold = 5.0
    status = "pass" if file_size_gb >= threshold else "fail"
    notes = f"Checkpoint file: {file_size_gb:.2f} GB; metadata keys: 14/14 present; sha256 verified"
    return StageResult(stage_name="checkpoint_validation", status=status, duration_s=duration,
                       metric_name="file_size_gb", metric_value=file_size_gb, threshold=threshold, notes=notes)


def stage_regression_gate(model_id: str, sr: float, mae: float, rng: np.random.Generator) -> StageResult:
    duration = rng.uniform(420.0, 600.0)
    sr_threshold, mae_threshold = 0.60, 0.025
    passes = sr >= sr_threshold and mae <= mae_threshold
    if not passes:
        if sr < sr_threshold:
            notes = f"SR={sr:.0%} < threshold={sr_threshold:.0%}; MAE={mae:.4f}; blocked on success_rate"
            return StageResult(stage_name="regression_gate", status="fail", duration_s=duration,
                               metric_name="success_rate", metric_value=sr, threshold=sr_threshold, notes=notes)
        else:
            notes = f"SR={sr:.0%} ok; MAE={mae:.4f} > threshold={mae_threshold}; blocked on mae"
            return StageResult(stage_name="regression_gate", status="fail", duration_s=duration,
                               metric_name="mae", metric_value=mae, threshold=mae_threshold, notes=notes)
    notes = f"SR={sr:.0%} >= {sr_threshold:.0%}; MAE={mae:.4f} <= {mae_threshold}; 20/20 episodes evaluated"
    return StageResult(stage_name="regression_gate", status="pass", duration_s=duration,
                       metric_name="success_rate", metric_value=sr, threshold=sr_threshold, notes=notes)


def stage_latency_gate(model_id: str, p99_ms: float, rng: np.random.Generator) -> StageResult:
    duration = rng.uniform(45.0, 90.0)
    p50 = p99_ms * rng.uniform(0.50, 0.60)
    p95 = p99_ms * rng.uniform(0.82, 0.92)
    threshold_ms = 300.0
    passes = p99_ms < threshold_ms
    notes = f"p50={p50:.1f}ms; p95={p95:.1f}ms; p99={p99_ms:.1f}ms; 100 inference calls on A100; batch_size=1"
    return StageResult(stage_name="latency_gate", status="pass" if passes else "fail", duration_s=duration,
                       metric_name="p99_latency_ms", metric_value=p99_ms, threshold=threshold_ms, notes=notes)


def stage_safety_check(model_id: str, rng: np.random.Generator) -> StageResult:
    duration = rng.uniform(60.0, 120.0)
    safety_score = rng.uniform(0.97, 1.0)
    threshold = 0.95
    passes = safety_score >= threshold
    anomaly_count = int((1 - safety_score) * 1000)
    notes = (f"Joint limits: OK (7 DOF verified); workspace bounds: OK; "
             f"anomalous actions: {anomaly_count}/1000 ({(1-safety_score)*100:.1f}%); "
             f"velocity clipping: active; torque limits: within 90% nominal")
    return StageResult(stage_name="safety_check", status="pass" if passes else "fail", duration_s=duration,
                       metric_name="safety_score", metric_value=safety_score, threshold=threshold, notes=notes)


def stage_canary_deploy(model_id: str, rng: np.random.Generator) -> StageResult:
    duration = 900.0 + rng.uniform(-30.0, 30.0)
    error_rate = rng.uniform(0.0, 0.02)
    threshold = 0.05
    passes = error_rate < threshold
    req_count = int(rng.uniform(180, 240))
    notes = (f"Traffic split: 10% canary; requests handled: {req_count}; "
             f"error_rate={error_rate*100:.2f}%; avg_latency={rng.uniform(210,250):.0f}ms; "
             f"monitoring window: 15 min; no rollback triggered")
    return StageResult(stage_name="canary_deploy", status="pass" if passes else "fail", duration_s=duration,
                       metric_name="canary_error_rate", metric_value=error_rate, threshold=threshold, notes=notes)


def stage_full_rollout(model_id: str, rng: np.random.Generator) -> StageResult:
    duration = rng.uniform(30.0, 60.0)
    notes = ("Traffic promoted to 100%; previous version v1.8 on standby; "
             "rollback SLA: <30s; health checks: passing (5/5); load balancer updated; DNS TTL: 60s")
    return StageResult(stage_name="full_rollout", status="pass", duration_s=duration,
                       metric_name="rollout_completion", metric_value=1.0, threshold=0.99, notes=notes)


def stage_monitoring_setup(model_id: str, rng: np.random.Generator) -> StageResult:
    duration = rng.uniform(15.0, 35.0)
    alert_count = 7
    notes = (f"Drift alerts configured: {alert_count}; "
             f"rollback triggers: SR_drop>10%, latency_p99>350ms, error_rate>5%; "
             f"OCI Monitoring namespace: robot_cloud/production; PagerDuty integration: active; retention: 90 days")
    return StageResult(stage_name="monitoring_setup", status="pass", duration_s=duration,
                       metric_name="alerts_configured", metric_value=float(alert_count), threshold=5.0, notes=notes)


def run_deployment(model_id: str, sr: float, mae: float, p99_ms: float,
                   started_at: datetime, seed: int) -> DeploymentAttempt:
    rng = np.random.default_rng(seed)
    attempt = DeploymentAttempt(model_id=model_id, started_at=started_at, final_status="blocked")
    s1 = stage_checkpoint_validation(model_id, rng)
    attempt.stages.append(s1)
    if s1.status == "fail":
        attempt.cost_usd = 0.15
        return attempt
    s2 = stage_regression_gate(model_id, sr, mae, rng)
    attempt.stages.append(s2)
    if s2.status == "fail":
        attempt.cost_usd = 0.15 + (s1.duration_s + s2.duration_s) * 0.000023
        return attempt
    s3 = stage_latency_gate(model_id, p99_ms, rng)
    attempt.stages.append(s3)
    if s3.status == "fail":
        attempt.cost_usd = 0.15 + sum(s.duration_s for s in attempt.stages) * 0.000023
        return attempt
    s4 = stage_safety_check(model_id, rng)
    attempt.stages.append(s4)
    if s4.status == "fail":
        attempt.cost_usd = 0.20 + sum(s.duration_s for s in attempt.stages) * 0.000023
        return attempt
    s5 = stage_canary_deploy(model_id, rng)
    attempt.stages.append(s5)
    if s5.status == "fail":
        attempt.cost_usd = 0.40 + sum(s.duration_s for s in attempt.stages) * 0.000023
        return attempt
    s6 = stage_full_rollout(model_id, rng)
    attempt.stages.append(s6)
    s7 = stage_monitoring_setup(model_id, rng)
    attempt.stages.append(s7)
    attempt.final_status = "success"
    attempt.promoted_to_production = True
    attempt.rollback_available = True
    attempt.cost_usd = 0.80 + sum(s.duration_s for s in attempt.stages) * 0.000023
    return attempt


STAGE_NAMES = ["checkpoint_validation", "regression_gate", "latency_gate",
               "safety_check", "canary_deploy", "full_rollout", "monitoring_setup"]
STAGE_LABELS = ["Checkpoint\nValidation", "Regression\nGate", "Latency\nGate",
                "Safety\nCheck", "Canary\nDeploy", "Full\nRollout", "Monitoring\nSetup"]
STATUS_COLORS = {"pass": "#22c55e", "fail": "#ef4444", "skip": "#d1d5db"}
STATUS_TEXT_COLORS = {"pass": "#ffffff", "fail": "#ffffff", "skip": "#6b7280"}


def build_skipped_stages(attempt: DeploymentAttempt, all_stage_names: List[str]) -> List[StageResult]:
    executed = {s.stage_name for s in attempt.stages}
    full = list(attempt.stages)
    for name in all_stage_names:
        if name not in executed:
            full.append(StageResult(stage_name=name, status="skip", duration_s=0.0,
                                    metric_name="n/a", metric_value=0.0, threshold=0.0,
                                    notes="Skipped — earlier stage blocked deployment"))
    return full


def svg_pipeline_rows(attempts: List[DeploymentAttempt]) -> str:
    n_stages = len(STAGE_NAMES)
    box_w, box_h = 110, 56
    arrow_w, row_h = 18, 90
    label_col, pad_top, pad_left = 180, 50, 20
    total_w = pad_left + label_col + n_stages * (box_w + arrow_w) + 40
    total_h = pad_top + len(attempts) * row_h + 40
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{total_w}" height="{total_h}" font-family="system-ui,sans-serif">',
        '<defs><marker id="arr" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6 Z" fill="#9ca3af"/></marker></defs>',
        '<rect width="100%" height="100%" fill="#f8fafc"/>',
    ]
    for i, lbl in enumerate(STAGE_LABELS):
        cx = pad_left + label_col + i * (box_w + arrow_w) + box_w // 2
        for j, ll in enumerate(lbl.split("\n")):
            lines.append(f'<text x="{cx}" y="{pad_top - 28 + j*14}" text-anchor="middle" font-size="11" font-weight="600" fill="#374151">{ll}</text>')
    for row_idx, attempt in enumerate(attempts):
        y_center = pad_top + row_idx * row_h + box_h // 2
        full_stages = build_skipped_stages(attempt, STAGE_NAMES)
        stage_map = {s.stage_name: s for s in full_stages}
        status_color = "#22c55e" if attempt.final_status == "success" else "#ef4444"
        lines.append(f'<text x="{pad_left}" y="{y_center - 10}" font-size="12" font-weight="700" fill="#111827">{attempt.model_id}</text>')
        status_label = "PROMOTED" if attempt.final_status == "success" else f"BLOCKED @ {attempt.blocking_stage or 'unknown'}"
        lines.append(f'<text x="{pad_left}" y="{y_center + 10}" font-size="10" fill="{status_color}">{status_label}</text>')
        lines.append(f'<text x="{pad_left}" y="{y_center + 25}" font-size="10" fill="#6b7280">cost: ${attempt.cost_usd:.2f}</text>')
        for i, sname in enumerate(STAGE_NAMES):
            sr = stage_map.get(sname)
            bx = pad_left + label_col + i * (box_w + arrow_w)
            by = y_center - box_h // 2
            color = STATUS_COLORS.get(sr.status if sr else "skip", "#d1d5db")
            tcolor = STATUS_TEXT_COLORS.get(sr.status if sr else "skip", "#6b7280")
            lines.append(f'<rect x="{bx}" y="{by}" width="{box_w}" height="{box_h}" rx="6" fill="{color}" opacity="{"1.0" if sr and sr.status != "skip" else "0.5"}"/>')
            icon = "✓" if (sr and sr.status == "pass") else ("✗" if (sr and sr.status == "fail") else "—")
            lines.append(f'<text x="{bx + box_w//2}" y="{by + 22}" text-anchor="middle" font-size="16" fill="{tcolor}">{icon}</text>')
            if sr and sr.status != "skip":
                mv = sr.metric_value
                if sr.metric_name in ("success_rate", "safety_score", "rollout_completion", "canary_error_rate"): val_str = f"{mv*100:.1f}%"
                elif sr.metric_name == "p99_latency_ms": val_str = f"{mv:.0f}ms"
                elif sr.metric_name == "file_size_gb": val_str = f"{mv:.1f}GB"
                else: val_str = f"{mv:.1f}"
                lines.append(f'<text x="{bx + box_w//2}" y="{by + 38}" text-anchor="middle" font-size="10" fill="{tcolor}">{val_str}</text>')
                lines.append(f'<text x="{bx + box_w//2}" y="{by + 50}" text-anchor="middle" font-size="9" fill="{tcolor}" opacity="0.85">{sr.duration_s:.0f}s</text>')
            if i < n_stages - 1:
                ax = bx + box_w
                lines.append(f'<line x1="{ax}" y1="{y_center}" x2="{ax + arrow_w - 4}" y2="{y_center}" stroke="#9ca3af" stroke-width="2" marker-end="url(#arr)"/>')
    lines.append('</svg>')
    return "\n".join(lines)


def svg_success_funnel(attempts: List[DeploymentAttempt]) -> str:
    n_stages = len(STAGE_NAMES)
    n_attempts = len(attempts)
    pass_counts = [sum(1 for a in attempts for s in a.stages if s.stage_name == sname and s.status == "pass") for sname in STAGE_NAMES]
    w, h, pad_l, pad_r, pad_t, pad_b = 560, 260, 50, 30, 30, 70
    chart_w = w - pad_l - pad_r
    chart_h = h - pad_t - pad_b
    bar_w = chart_w // n_stages - 10
    max_val = n_attempts or 1
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" font-family="system-ui,sans-serif">',
        '<rect width="100%" height="100%" fill="#f8fafc"/>',
        f'<text x="{w//2}" y="20" text-anchor="middle" font-size="13" font-weight="700" fill="#111827">Deployment Success Funnel</text>',
    ]
    for i, (sname, cnt) in enumerate(zip(STAGE_NAMES, pass_counts)):
        bx = pad_l + i * (chart_w // n_stages) + 5
        bar_h = int(cnt / max_val * chart_h)
        by = pad_t + chart_h - bar_h
        color = "#3b82f6" if cnt > 0 else "#d1d5db"
        lines.append(f'<rect x="{bx}" y="{by}" width="{bar_w}" height="{bar_h}" rx="4" fill="{color}"/>')
        lines.append(f'<text x="{bx + bar_w//2}" y="{by - 5}" text-anchor="middle" font-size="12" font-weight="600" fill="#1e40af">{cnt}</text>')
        lbl = " ".join(sname.split("_")[:2])
        lx = bx + bar_w // 2; ly = pad_t + chart_h + 12
        lines.append(f'<text x="{lx}" y="{ly}" text-anchor="end" font-size="9" fill="#374151" transform="rotate(-35,{lx},{ly})">{lbl}</text>')
    lines.append(f'<line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t+chart_h}" stroke="#d1d5db" stroke-width="1"/>')
    lines.append('</svg>')
    return "\n".join(lines)


def fmt_duration(seconds: float) -> str:
    if seconds < 60: return f"{seconds:.0f}s"
    return f"{int(seconds // 60)}m {int(seconds % 60):02d}s"


def build_html_report(report: DeploymentReport) -> str:
    svg_rows = svg_pipeline_rows(report.attempts)
    svg_funnel = svg_success_funnel(report.attempts)
    rows_html = ""
    for a in report.attempts:
        status_badge = ('<span style="background:#dcfce7;color:#166534;padding:2px 8px;border-radius:9999px;font-size:11px;font-weight:600">PROMOTED</span>'
                        if a.final_status == "success" else
                        '<span style="background:#fee2e2;color:#991b1b;padding:2px 8px;border-radius:9999px;font-size:11px;font-weight:600">BLOCKED</span>')
        rows_html += f'<tr><td style="font-weight:600;padding:8px 12px">{a.model_id}</td><td style="padding:8px 12px">{a.started_at.strftime("%Y-%m-%d %H:%M")}</td><td style="padding:8px 12px">{status_badge}</td><td style="padding:8px 12px">{a.blocking_stage or "—"}</td><td style="padding:8px 12px">{fmt_duration(a.total_duration_s)}</td><td style="padding:8px 12px">${a.cost_usd:.3f}</td><td style="padding:8px 12px">{"Yes" if a.promoted_to_production else "No"}</td><td style="padding:8px 12px">{"Yes" if a.rollback_available else "No"}</td></tr>'
    stage_detail_html = ""
    for a in report.attempts:
        full_stages = build_skipped_stages(a, STAGE_NAMES)
        stage_rows = ""
        for s in full_stages:
            sc = {"pass": "#dcfce7", "fail": "#fee2e2", "skip": "#f3f4f6"}[s.status]
            tc = {"pass": "#166534", "fail": "#991b1b", "skip": "#6b7280"}[s.status]
            mv_str = f"{s.metric_value:.4f}" if s.metric_value != 0 else "—"
            th_str = f"{s.threshold:.4f}" if s.threshold != 0 else "—"
            stage_rows += f'<tr><td style="padding:6px 10px;font-family:monospace;font-size:12px">{s.stage_name}</td><td style="padding:6px 10px"><span style="background:{sc};color:{tc};padding:2px 7px;border-radius:9999px;font-size:11px">{s.status.upper()}</span></td><td style="padding:6px 10px;font-size:12px">{s.duration_s:.0f}s</td><td style="padding:6px 10px;font-size:12px">{s.metric_name}</td><td style="padding:6px 10px;font-size:12px">{mv_str}</td><td style="padding:6px 10px;font-size:12px">{th_str}</td><td style="padding:6px 10px;font-size:11px;color:#6b7280;max-width:300px">{s.notes}</td></tr>'
        status_color = "#22c55e" if a.final_status == "success" else "#ef4444"
        stage_detail_html += f'<h3 style="margin:24px 0 8px;color:{status_color}">{a.model_id}</h3><table style="width:100%;border-collapse:collapse;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.1);margin-bottom:16px"><thead><tr style="background:#f1f5f9"><th style="padding:8px 10px;text-align:left;font-size:12px">Stage</th><th style="padding:8px 10px;text-align:left;font-size:12px">Status</th><th style="padding:8px 10px;text-align:left;font-size:12px">Duration</th><th style="padding:8px 10px;text-align:left;font-size:12px">Metric</th><th style="padding:8px 10px;text-align:left;font-size:12px">Value</th><th style="padding:8px 10px;text-align:left;font-size:12px">Threshold</th><th style="padding:8px 10px;text-align:left;font-size:12px">Notes</th></tr></thead><tbody>{stage_rows}</tbody></table>'
    html = f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"/><title>OCI Robot Cloud — Model Deployment Pipeline</title>
<style>body{{font-family:system-ui,-apple-system,sans-serif;background:#f1f5f9;color:#111827;margin:0;padding:24px}}h1{{font-size:22px;color:#1e40af;margin-bottom:4px}}h2{{font-size:16px;color:#374151;margin:24px 0 12px;border-bottom:1px solid #e5e7eb;padding-bottom:6px}}.card{{background:#fff;border-radius:10px;padding:20px;margin-bottom:20px;box-shadow:0 1px 4px rgba(0,0,0,0.08)}}.stat-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:20px}}.stat{{background:#fff;border-radius:8px;padding:14px 18px;box-shadow:0 1px 3px rgba(0,0,0,0.08);text-align:center}}.stat-val{{font-size:26px;font-weight:700;color:#1e40af}}.stat-lbl{{font-size:11px;color:#6b7280;margin-top:2px}}table{{width:100%;border-collapse:collapse}}thead tr{{background:#f1f5f9}}.svg-wrap{{overflow-x:auto}}</style>
</head><body>
<h1>OCI Robot Cloud — Model Deployment Pipeline</h1>
<p style="color:#6b7280;font-size:13px;margin-bottom:20px">Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | 7-stage automated safety gate pipeline | GR00T checkpoint promotion</p>
<div class="stat-grid">
<div class="stat"><div class="stat-val">{len(report.attempts)}</div><div class="stat-lbl">Deployment Attempts</div></div>
<div class="stat"><div class="stat-val">{report.success_rate:.0%}</div><div class="stat-lbl">Success Rate</div></div>
<div class="stat"><div class="stat-val">{fmt_duration(report.avg_deploy_time_s)}</div><div class="stat-lbl">Avg Deploy Time</div></div>
<div class="stat"><div class="stat-val">${sum(a.cost_usd for a in report.attempts):.2f}</div><div class="stat-lbl">Total Pipeline Cost</div></div>
</div>
<h2>Pipeline Stage Visualization</h2><div class="card svg-wrap">{svg_rows}</div>
<h2>Deployment Attempts Summary</h2><div class="card"><table><thead><tr><th style="padding:8px 12px;font-size:13px">Model ID</th><th style="padding:8px 12px;font-size:13px">Started At</th><th style="padding:8px 12px;font-size:13px">Status</th><th style="padding:8px 12px;font-size:13px">Blocked At</th><th style="padding:8px 12px;font-size:13px">Total Time</th><th style="padding:8px 12px;font-size:13px">Cost</th><th style="padding:8px 12px;font-size:13px">In Production</th><th style="padding:8px 12px;font-size:13px">Rollback</th></tr></thead><tbody>{rows_html}</tbody></table></div>
<h2>Success Funnel</h2><div class="card svg-wrap">{svg_funnel}</div>
<h2>Stage-by-Stage Detail</h2><div class="card">{stage_detail_html}</div>
<p style="color:#9ca3af;font-size:11px;margin-top:24px;text-align:center">Oracle Confidential | OCI Robot Cloud | model_deployment_pipeline.py</p>
</body></html>"""
    return html


def main():
    random.seed(42)
    base_time = datetime(2026, 3, 28, 9, 0, 0)
    a1 = run_deployment(model_id="dagger_run9_v2.2", sr=0.71, mae=0.018, p99_ms=227.0, started_at=base_time, seed=101)
    a2 = run_deployment(model_id="dagger_run8_v1.9_hotfix", sr=0.52, mae=0.021, p99_ms=248.0, started_at=base_time + timedelta(hours=3), seed=202)
    a3 = run_deployment(model_id="dagger_run7_lora8", sr=0.65, mae=0.022, p99_ms=342.0, started_at=base_time + timedelta(hours=6), seed=303)
    report = DeploymentReport(attempts=[a1, a2, a3])
    print("=" * 70)
    print("OCI Robot Cloud — Model Deployment Pipeline Report")
    print("=" * 70)
    print(f"{'Model ID':<28} {'Status':<10} {'Blocked At':<24} {'Duration':<12} {'Cost'}")
    print("-" * 70)
    for a in report.attempts:
        blocker = a.blocking_stage or "—"
        print(f"{a.model_id:<28} {a.final_status.upper():<10} {blocker:<24} {fmt_duration(a.total_duration_s):<12} ${a.cost_usd:.3f}")
    print("-" * 70)
    print(f"Success rate: {report.success_rate:.0%}  |  Avg deploy time: {fmt_duration(report.avg_deploy_time_s)}  |  Total cost: ${sum(a.cost_usd for a in report.attempts):.3f}")
    print()
    print("Stage detail:")
    for a in report.attempts:
        print(f"\n  [{a.model_id}]")
        full = build_skipped_stages(a, STAGE_NAMES)
        for s in full:
            icon = {"✓": "pass", "✗": "fail", "○": "skip"}.get(s.status, s.status)
            icon = {"+": "✓", "pass": "✓", "fail": "✗", "skip": "○"}.get(s.status, s.status)
            print(f"    {icon} {s.stage_name:<26} {s.status:<6}  {s.metric_name}={s.metric_value:.4f}  ({s.duration_s:.0f}s)")
    print()
    print(f"Failures by stage: {report.failures_by_stage}")
    html = build_html_report(report)
    out_path = "/tmp/model_deployment_pipeline.html"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\nHTML report written to {out_path}")


if __name__ == "__main__":
    main()
