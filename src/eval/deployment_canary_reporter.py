#!/usr/bin/env python3
"""
deployment_canary_reporter.py -- Canary deployment health reporter for GR00T policy rollouts.

Tracks canary vs stable traffic split, success rate divergence, latency regression,
and auto-rollback triggers across 5 recent deployment events.
"""

import argparse
import json
import math
import random
import time
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class CanaryWindow:
    timestamp_offset_h: float
    canary_sr: float
    stable_sr: float
    canary_latency_ms: float
    stable_latency_ms: float
    canary_error_rate: float
    stable_error_rate: float
    traffic_split_pct: float


@dataclass
class DeploymentEvent:
    event_id: str
    policy_version: str
    canary_version: str
    stable_version: str
    start_time: str
    duration_h: float
    outcome: str
    rollback_reason: str
    final_canary_sr: float
    final_stable_sr: float
    sr_delta: float
    latency_delta_ms: float
    peak_traffic_split_pct: float
    windows: list = field(default_factory=list)


@dataclass
class CanaryReport:
    generated_at: str
    total_deployments: int
    promoted: int
    rolled_back: int
    in_progress: int
    avg_promotion_time_h: float
    rollback_rate_pct: float
    events: list = field(default_factory=list)


def simulate_canary_deployments(seed: int = 42) -> CanaryReport:
    rng = random.Random(seed)
    events_config = [
        {"event_id": "deploy_001", "policy_version": "dagger_run7_v1.8", "canary_version": "dagger_run7_v1.8",
         "stable_version": "dagger_run6_v1.7", "start_time": "2026-01-15 08:00", "duration_h": 6.0,
         "outcome": "promoted", "rollback_reason": "", "base_canary_sr": 0.71, "base_stable_sr": 0.65, "latency_delta_ms": -8.0},
        {"event_id": "deploy_002", "policy_version": "dagger_run8_v1.9", "canary_version": "dagger_run8_v1.9",
         "stable_version": "dagger_run7_v1.8", "start_time": "2026-02-01 10:00", "duration_h": 2.5,
         "outcome": "rolled_back", "rollback_reason": "SR regression: canary 0.58 vs stable 0.71 (delta -0.13 > threshold -0.05)",
         "base_canary_sr": 0.58, "base_stable_sr": 0.71, "latency_delta_ms": 22.0},
        {"event_id": "deploy_003", "policy_version": "dagger_run8_hotfix_v1.9.1", "canary_version": "dagger_run8_hotfix_v1.9.1",
         "stable_version": "dagger_run7_v1.8", "start_time": "2026-02-08 14:00", "duration_h": 8.0,
         "outcome": "promoted", "rollback_reason": "", "base_canary_sr": 0.74, "base_stable_sr": 0.71, "latency_delta_ms": -3.0},
        {"event_id": "deploy_004", "policy_version": "dagger_run9_soap_v2.2", "canary_version": "dagger_run9_soap_v2.2",
         "stable_version": "dagger_run8_hotfix_v1.9.1", "start_time": "2026-03-10 09:00", "duration_h": 12.0,
         "outcome": "promoted", "rollback_reason": "", "base_canary_sr": 0.81, "base_stable_sr": 0.74, "latency_delta_ms": -11.0},
        {"event_id": "deploy_005", "policy_version": "ensemble_v2.3_canary", "canary_version": "ensemble_v2.3_canary",
         "stable_version": "dagger_run9_soap_v2.2", "start_time": "2026-03-28 11:00", "duration_h": 3.0,
         "outcome": "in_progress", "rollback_reason": "", "base_canary_sr": 0.83, "base_stable_sr": 0.81, "latency_delta_ms": 15.0},
    ]

    events = []
    for cfg in events_config:
        n_windows = max(3, int(cfg["duration_h"] * 2))
        windows = []
        for i in range(n_windows):
            t = cfg["duration_h"] * i / max(n_windows - 1, 1)
            if t < cfg["duration_h"] * 0.2: split = 5.0
            elif t < cfg["duration_h"] * 0.4: split = 10.0
            elif t < cfg["duration_h"] * 0.7: split = 25.0
            else: split = 50.0
            noise = rng.gauss(0, 0.015)
            windows.append(CanaryWindow(
                timestamp_offset_h=round(t, 2),
                canary_sr=round(max(0, min(1, cfg["base_canary_sr"] + noise)), 3),
                stable_sr=round(max(0, min(1, cfg["base_stable_sr"] + rng.gauss(0, 0.01))), 3),
                canary_latency_ms=round(226 + cfg["latency_delta_ms"] + rng.gauss(0, 5), 1),
                stable_latency_ms=round(226 + rng.gauss(0, 5), 1),
                canary_error_rate=round(max(0, rng.gauss(0.012, 0.004)), 4),
                stable_error_rate=round(max(0, rng.gauss(0.010, 0.003)), 4),
                traffic_split_pct=split,
            ))
        ev = DeploymentEvent(
            event_id=cfg["event_id"], policy_version=cfg["policy_version"],
            canary_version=cfg["canary_version"], stable_version=cfg["stable_version"],
            start_time=cfg["start_time"], duration_h=cfg["duration_h"],
            outcome=cfg["outcome"], rollback_reason=cfg["rollback_reason"],
            final_canary_sr=round(cfg["base_canary_sr"] + rng.gauss(0, 0.005), 3),
            final_stable_sr=round(cfg["base_stable_sr"], 3),
            sr_delta=round(cfg["base_canary_sr"] - cfg["base_stable_sr"], 3),
            latency_delta_ms=cfg["latency_delta_ms"],
            peak_traffic_split_pct=50.0 if cfg["outcome"] != "rolled_back" else 25.0,
            windows=windows,
        )
        events.append(ev)

    promoted = sum(1 for e in events if e.outcome == "promoted")
    rolled_back = sum(1 for e in events if e.outcome == "rolled_back")
    in_progress = sum(1 for e in events if e.outcome == "in_progress")
    promotion_hours = [e.duration_h for e in events if e.outcome == "promoted"]

    return CanaryReport(
        generated_at=time.strftime("%Y-%m-%d %H:%M:%S"),
        total_deployments=len(events), promoted=promoted,
        rolled_back=rolled_back, in_progress=in_progress,
        avg_promotion_time_h=round(sum(promotion_hours) / len(promotion_hours) if promotion_hours else 0, 1),
        rollback_rate_pct=round(100.0 * rolled_back / (promoted + rolled_back) if (promoted + rolled_back) > 0 else 0, 1),
        events=events,
    )


def _sr_timeseries_svg(event: DeploymentEvent) -> str:
    if not event.windows:
        return ""
    w, h = 340, 90
    times = [win.timestamp_offset_h for win in event.windows]
    c_srs = [win.canary_sr for win in event.windows]
    s_srs = [win.stable_sr for win in event.windows]
    t_max = max(times) if times else 1.0
    mn = min(min(c_srs), min(s_srs)) - 0.05
    mx = max(max(c_srs), max(s_srs)) + 0.05
    r = mx - mn if mx != mn else 1.0

    def to_pt(t, v):
        x = 20 + (t / t_max) * (w - 30)
        y = 10 + (1 - (v - mn) / r) * (h - 20)
        return f"{x:.1f},{y:.1f}"

    c_pts = " ".join(to_pt(t, v) for t, v in zip(times, c_srs))
    s_pts = " ".join(to_pt(t, v) for t, v in zip(times, s_srs))
    thresh = s_srs[0] - 0.05
    ty = 10 + (1 - (thresh - mn) / r) * (h - 20)
    return (f'<svg width="{w}" height="{h}" style="background:#0f172a;border-radius:4px">'
            f'<line x1="20" y1="{ty:.1f}" x2="{w-10}" y2="{ty:.1f}" stroke="#ef4444" stroke-width="1" stroke-dasharray="4,2"/>'
            f'<polyline points="{s_pts}" fill="none" stroke="#94a3b8" stroke-width="1.5"/>'
            f'<polyline points="{c_pts}" fill="none" stroke="#38bdf8" stroke-width="2"/>'
            f'<text x="22" y="{h-2}" fill="#94a3b8" font-size="9">0h</text>'
            f'<text x="{w-25}" y="{h-2}" fill="#94a3b8" font-size="9">{t_max:.1f}h</text></svg>')


def render_html(report: CanaryReport) -> str:
    outcome_color = {"promoted": "#22c55e", "rolled_back": "#ef4444", "in_progress": "#f59e0b"}
    outcome_badge = {"promoted": "PROMOTED", "rolled_back": "ROLLED BACK", "in_progress": "IN PROGRESS"}

    events_html = ""
    for ev in report.events:
        oc = ev.outcome
        badge_color = outcome_color.get(oc, "#94a3b8")
        badge_text = outcome_badge.get(oc, oc.upper())
        delta_color = "#22c55e" if ev.sr_delta >= 0 else "#ef4444"
        lat_color = "#22c55e" if ev.latency_delta_ms <= 0 else "#f59e0b"
        ts_svg = _sr_timeseries_svg(ev)
        rollback_row = f'<tr><td style="color:#94a3b8">Rollback reason</td><td colspan="3" style="color:#ef4444;font-size:11px">{ev.rollback_reason}</td></tr>' if ev.rollback_reason else ""
        events_html += f"""
<div style="background:#0f172a;border:1px solid #334155;border-radius:8px;padding:18px;margin-bottom:20px">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
    <div><span style="color:#C74634;font-weight:bold;font-size:15px">{ev.event_id}</span>
    <span style="color:#94a3b8;font-size:12px;margin-left:12px">{ev.start_time} \u00b7 {ev.duration_h}h</span></div>
    <span style="background:{badge_color}22;color:{badge_color};padding:3px 10px;border-radius:12px;font-size:12px;font-weight:bold">{badge_text}</span>
  </div>
  <table style="width:100%;border-collapse:collapse;font-size:12px;margin-bottom:12px">
    <tr><td style="color:#94a3b8;padding:4px 8px">Canary</td><td style="color:#e2e8f0;padding:4px 8px">{ev.canary_version}</td>
    <td style="color:#94a3b8;padding:4px 8px">Canary SR</td><td style="color:#38bdf8;font-weight:bold;padding:4px 8px">{ev.final_canary_sr:.3f}</td></tr>
    <tr><td style="color:#94a3b8;padding:4px 8px">Stable</td><td style="color:#e2e8f0;padding:4px 8px">{ev.stable_version}</td>
    <td style="color:#94a3b8;padding:4px 8px">Stable SR</td><td style="color:#94a3b8;padding:4px 8px">{ev.final_stable_sr:.3f}</td></tr>
    <tr><td style="color:#94a3b8;padding:4px 8px">SR Delta</td><td style="color:{delta_color};font-weight:bold;padding:4px 8px">{ev.sr_delta:+.3f}</td>
    <td style="color:#94a3b8;padding:4px 8px">Latency \u0394</td><td style="color:{lat_color};font-weight:bold;padding:4px 8px">{ev.latency_delta_ms:+.1f}ms</td></tr>
    {rollback_row}
  </table>
  <div style="margin-top:8px"><div style="color:#94a3b8;font-size:11px;margin-bottom:4px">SR over time \u2014 <span style="color:#38bdf8">canary</span> vs <span style="color:#94a3b8">stable</span></div>
  {ts_svg}</div>
</div>"""

    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><title>Deployment Canary Report</title>
<style>body{{background:#1e293b;color:#e2e8f0;font-family:'Segoe UI',Arial,sans-serif;margin:0;padding:24px}}
h1{{color:#C74634;margin:0 0 4px 0;font-size:22px}}h2{{color:#C74634;font-size:15px;margin:20px 0 10px 0;border-bottom:1px solid #334155;padding-bottom:6px}}
.meta{{color:#94a3b8;font-size:12px;margin-bottom:20px}}.stat-row{{display:flex;gap:16px;margin-bottom:20px;flex-wrap:wrap}}
.stat{{background:#0f172a;border:1px solid #334155;border-radius:8px;padding:12px 20px;min-width:120px}}
.stat-val{{font-size:28px;font-weight:bold;color:#38bdf8}}.stat-lbl{{font-size:11px;color:#94a3b8;margin-top:2px}}</style></head>
<body><h1>Deployment Canary Report</h1>
<div class="meta">Generated {report.generated_at} \u00b7 GR00T Policy Canary Rollouts \u00b7 OCI A100 GPU4</div>
<div class="stat-row">
  <div class="stat"><div class="stat-val">{report.total_deployments}</div><div class="stat-lbl">Total deployments</div></div>
  <div class="stat"><div class="stat-val" style="color:#22c55e">{report.promoted}</div><div class="stat-lbl">Promoted</div></div>
  <div class="stat"><div class="stat-val" style="color:#ef4444">{report.rolled_back}</div><div class="stat-lbl">Rolled back</div></div>
  <div class="stat"><div class="stat-val" style="color:#f59e0b">{report.in_progress}</div><div class="stat-lbl">In progress</div></div>
  <div class="stat"><div class="stat-val">{report.avg_promotion_time_h}h</div><div class="stat-lbl">Avg promotion time</div></div>
  <div class="stat"><div class="stat-val" style="color:#f59e0b">{report.rollback_rate_pct}%</div><div class="stat-lbl">Rollback rate</div></div>
</div>
<h2>Deployment Events</h2>{events_html}
<div style="margin-top:30px;padding:14px;background:#0f172a;border-radius:8px;font-size:12px;color:#94a3b8">
  Traffic ramp: 5% \u2192 10% \u2192 25% \u2192 50%. Auto-rollback: SR delta &lt; -0.05, error rate &gt; 3%, latency p99 &gt; +50ms.
</div></body></html>"""


def main():
    parser = argparse.ArgumentParser(description="Deployment canary reporter")
    parser.add_argument("--mock", action="store_true", default=True)
    parser.add_argument("--output", default="/tmp/deployment_canary_reporter.html")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    report = simulate_canary_deployments(seed=args.seed)
    html = render_html(report)
    out_path = Path(args.output)
    out_path.write_text(html)
    print(f"[canary] Report saved to {out_path}")
    for ev in report.events:
        print(f"  {ev.event_id}: {ev.policy_version} \u2192 {ev.outcome.upper()} (SR \u0394 {ev.sr_delta:+.3f}, lat \u0394 {ev.latency_delta_ms:+.1f}ms)")


if __name__ == "__main__":
    main()
