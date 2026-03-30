"""
gpu_cluster_monitor.py — Real-time GPU cluster health monitor for OCI Robot Cloud.

Monitors all OCI A100 GPUs running GR00T workloads and alerts on
thermal / memory / utilization issues.

Dependencies: stdlib + numpy only (no CUDA bindings needed for simulation).

Usage:
    python gpu_cluster_monitor.py              # generate HTML report + print status
    python gpu_cluster_monitor.py --serve      # also start FastAPI server on port 8073
"""

from __future__ import annotations

import argparse
import datetime
import json
import math
import random
import sys
from dataclasses import dataclass, field, asdict
from typing import List, Optional

import numpy as np


@dataclass
class GPUMetrics:
    gpu_id: int
    name: str
    vram_used_gb: float
    vram_total_gb: float
    utilization_pct: float
    temp_c: float
    power_w: float
    running_job: str
    p50_latency_ms: float
    error_rate_pct: float
    timestamp: str


@dataclass
class Alert:
    gpu_id: int
    severity: str
    message: str
    threshold: float
    actual_value: float


@dataclass
class ClusterSnapshot:
    timestamp: str
    gpus: List[GPUMetrics]
    alerts: List[Alert]
    cluster_utilization_avg: float
    total_vram_used_gb: float


THRESHOLDS = {
    "critical": {"temp_c": 85.0, "vram_pct": 95.0, "utilization_pct": 98.0, "error_rate_pct": 5.0},
    "warning":  {"temp_c": 78.0, "vram_pct": 85.0, "utilization_pct": 90.0, "p50_latency_ms": 280.0},
}

BASELINE = [
    dict(gpu_id=0, name="A100-SXM4-80GB", vram_used_gb=28.4, vram_total_gb=80.0,
         utilization_pct=67.0, temp_c=71.0, power_w=210.0,
         running_job="inference-server-8001", p50_latency_ms=226.0, error_rate_pct=0.1),
    dict(gpu_id=1, name="A100-SXM4-80GB", vram_used_gb=36.8, vram_total_gb=80.0,
         utilization_pct=87.0, temp_c=79.0, power_w=310.0,
         running_job="fine-tuning", p50_latency_ms=0.0, error_rate_pct=0.2),
    dict(gpu_id=2, name="A100-SXM4-80GB", vram_used_gb=12.1, vram_total_gb=80.0,
         utilization_pct=52.0, temp_c=65.0, power_w=180.0,
         running_job="SDG-eval", p50_latency_ms=0.0, error_rate_pct=0.0),
    dict(gpu_id=3, name="A100-SXM4-80GB", vram_used_gb=6.7, vram_total_gb=80.0,
         utilization_pct=31.0, temp_c=58.0, power_w=140.0,
         running_job="staging-inference", p50_latency_ms=231.0, error_rate_pct=0.0),
]


def check_alerts(gpu: GPUMetrics) -> List[Alert]:
    alerts: List[Alert] = []
    vram_pct = (gpu.vram_used_gb / gpu.vram_total_gb) * 100.0
    if gpu.temp_c > THRESHOLDS["critical"]["temp_c"]:
        alerts.append(Alert(gpu_id=gpu.gpu_id, severity="critical",
            message=f"GPU{gpu.gpu_id} CRITICAL thermal: {gpu.temp_c:.1f}°C",
            threshold=THRESHOLDS["critical"]["temp_c"], actual_value=gpu.temp_c))
    if vram_pct > THRESHOLDS["critical"]["vram_pct"]:
        alerts.append(Alert(gpu_id=gpu.gpu_id, severity="critical",
            message=f"GPU{gpu.gpu_id} CRITICAL VRAM: {vram_pct:.1f}% ({gpu.vram_used_gb:.1f}/{gpu.vram_total_gb:.0f} GB)",
            threshold=THRESHOLDS["critical"]["vram_pct"], actual_value=vram_pct))
    if gpu.utilization_pct > THRESHOLDS["critical"]["utilization_pct"]:
        alerts.append(Alert(gpu_id=gpu.gpu_id, severity="critical",
            message=f"GPU{gpu.gpu_id} CRITICAL utilization: {gpu.utilization_pct:.1f}%",
            threshold=THRESHOLDS["critical"]["utilization_pct"], actual_value=gpu.utilization_pct))
    if gpu.error_rate_pct > THRESHOLDS["critical"]["error_rate_pct"]:
        alerts.append(Alert(gpu_id=gpu.gpu_id, severity="critical",
            message=f"GPU{gpu.gpu_id} CRITICAL error rate: {gpu.error_rate_pct:.2f}%",
            threshold=THRESHOLDS["critical"]["error_rate_pct"], actual_value=gpu.error_rate_pct))
    critical_temp_ids = {a.gpu_id for a in alerts if "thermal" in a.message}
    if gpu.gpu_id not in critical_temp_ids and gpu.temp_c > THRESHOLDS["warning"]["temp_c"]:
        alerts.append(Alert(gpu_id=gpu.gpu_id, severity="warning",
            message=f"GPU{gpu.gpu_id} WARNING thermal: {gpu.temp_c:.1f}°C",
            threshold=THRESHOLDS["warning"]["temp_c"], actual_value=gpu.temp_c))
    critical_vram_ids = {a.gpu_id for a in alerts if "VRAM" in a.message and a.severity == "critical"}
    if gpu.gpu_id not in critical_vram_ids and vram_pct > THRESHOLDS["warning"]["vram_pct"]:
        alerts.append(Alert(gpu_id=gpu.gpu_id, severity="warning",
            message=f"GPU{gpu.gpu_id} WARNING VRAM: {vram_pct:.1f}%",
            threshold=THRESHOLDS["warning"]["vram_pct"], actual_value=vram_pct))
    if THRESHOLDS["warning"]["utilization_pct"] < gpu.utilization_pct <= THRESHOLDS["critical"]["utilization_pct"]:
        alerts.append(Alert(gpu_id=gpu.gpu_id, severity="warning",
            message=f"GPU{gpu.gpu_id} WARNING high utilization: {gpu.utilization_pct:.1f}%",
            threshold=THRESHOLDS["warning"]["utilization_pct"], actual_value=gpu.utilization_pct))
    if gpu.p50_latency_ms > THRESHOLDS["warning"]["p50_latency_ms"] and gpu.p50_latency_ms > 0:
        alerts.append(Alert(gpu_id=gpu.gpu_id, severity="warning",
            message=f"GPU{gpu.gpu_id} WARNING p50 latency: {gpu.p50_latency_ms:.0f}ms",
            threshold=THRESHOLDS["warning"]["p50_latency_ms"], actual_value=gpu.p50_latency_ms))
    return alerts


def simulate_history(seed: int = 42) -> List[ClusterSnapshot]:
    rng = np.random.default_rng(seed)
    snapshots: List[ClusterSnapshot] = []
    base_time = datetime.datetime(2026, 3, 30, 0, 0, 0)
    n_steps = 288
    THERMAL_SPIKE_START, THERMAL_SPIKE_END = 96, 100
    VRAM_SPIKE_START, VRAM_SPIKE_END = 192, 194
    for step in range(n_steps):
        ts = base_time + datetime.timedelta(minutes=5 * step)
        ts_str = ts.isoformat()
        gpu_list: List[GPUMetrics] = []
        for b in BASELINE:
            gid = b["gpu_id"]
            util  = float(np.clip(b["utilization_pct"] + rng.normal(0, 3), 0, 100))
            temp  = float(np.clip(b["temp_c"]          + rng.normal(0, 1.5), 30, 95))
            vram  = float(np.clip(b["vram_used_gb"]    + rng.normal(0, 0.5), 0, b["vram_total_gb"]))
            power = float(np.clip(b["power_w"]         + rng.normal(0, 8), 100, 400))
            lat   = float(np.clip(b["p50_latency_ms"]  + rng.normal(0, 5), 0, 600)) if b["p50_latency_ms"] > 0 else 0.0
            errr  = float(np.clip(b["error_rate_pct"]  + rng.normal(0, 0.05), 0, 20))
            if gid == 1 and THERMAL_SPIKE_START <= step < THERMAL_SPIKE_END:
                temp  = float(np.clip(88.0 + rng.normal(0, 0.5), 87.0, 92.0))
                util  = float(np.clip(util + 8, 0, 100))
                power = float(np.clip(power + 40, 100, 400))
            if gid == 0 and VRAM_SPIKE_START <= step < VRAM_SPIKE_END:
                vram = float(np.clip(77.6 + rng.normal(0, 0.3), 75.0, 80.0))
            metrics = GPUMetrics(
                gpu_id=gid, name=b["name"],
                vram_used_gb=round(vram, 2), vram_total_gb=b["vram_total_gb"],
                utilization_pct=round(util, 1), temp_c=round(temp, 1),
                power_w=round(power, 1), running_job=b["running_job"],
                p50_latency_ms=round(lat, 1), error_rate_pct=round(errr, 3),
                timestamp=ts_str)
            gpu_list.append(metrics)
        all_alerts: List[Alert] = []
        for g in gpu_list:
            all_alerts.extend(check_alerts(g))
        cluster_util = float(np.mean([g.utilization_pct for g in gpu_list]))
        total_vram   = float(sum(g.vram_used_gb for g in gpu_list))
        snapshots.append(ClusterSnapshot(
            timestamp=ts_str, gpus=gpu_list, alerts=all_alerts,
            cluster_utilization_avg=round(cluster_util, 2),
            total_vram_used_gb=round(total_vram, 2)))
    return snapshots


def get_current_snapshot(history: List[ClusterSnapshot]) -> ClusterSnapshot:
    return history[-1]


def compute_stats(history: List[ClusterSnapshot]) -> dict:
    n = len(history)
    total_gpu_steps = n * 4
    critical_steps = sum(1 for s in history for a in s.alerts if a.severity == "critical")
    uptime_pct = round((1 - critical_steps / max(total_gpu_steps, 1)) * 100, 2)
    all_utils = [g.utilization_pct for s in history for g in s.gpus]
    avg_util = round(float(np.mean(all_utils)), 2)
    thermal_events = sum(1 for s in history for a in s.alerts if a.severity == "critical" and "thermal" in a.message)
    all_vram_used = [g.vram_used_gb for s in history for g in s.gpus]
    vram_peak = round(float(np.max(all_vram_used)), 2)
    step_h = 5 / 60
    gpu_hours = round(float(np.sum(all_utils)) / 100 * step_h, 2)
    return {
        "uptime_pct": uptime_pct,
        "avg_utilization_pct": avg_util,
        "thermal_events_count": thermal_events,
        "vram_peak_gb": vram_peak,
        "total_gpu_hours": gpu_hours,
        "snapshots_count": n,
    }


def _sparkline(values, x, y, width, height, color="#60a5fa", stroke_w=1.5):
    if len(values) < 2: return ""
    mn, mx = min(values), max(values)
    rng = mx - mn if mx != mn else 1.0
    pts = []
    for i, v in enumerate(values):
        px = x + (i / (len(values) - 1)) * width
        py = y + height - ((v - mn) / rng) * height
        pts.append(f"{px:.1f},{py:.1f}")
    return f'<polyline points="{" ".join(pts)}" fill="none" stroke="{color}" stroke-width="{stroke_w}" stroke-linejoin="round" stroke-linecap="round"/>'


def _text(x, y, content, font_size=12, fill="#e2e8f0", anchor="start", bold=False):
    weight = 'font-weight="bold"' if bold else ""
    return f'<text x="{x:.1f}" y="{y:.1f}" font-size="{font_size}" fill="{fill}" text-anchor="{anchor}" font-family="monospace" {weight}>{content}</text>'


def svg_gpu_cards(current: ClusterSnapshot, history: List[ClusterSnapshot]) -> str:
    card_w, card_h = 340, 200
    padding = 20
    total_w = 4 * card_w + 5 * padding
    total_h = card_h + 2 * padding
    elements = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{total_w}" height="{total_h}" style="background:#0f172a; font-family:monospace;">',
        _text(padding, 18, "GPU Status Cards — Current Snapshot", font_size=14, fill="#94a3b8", bold=True),
    ]
    severity_color = {"critical": "#ef4444", "warning": "#f59e0b", "info": "#60a5fa"}
    for idx, gpu in enumerate(current.gpus):
        cx = padding + idx * (card_w + padding)
        cy = padding + 24
        gpu_alerts = [a for a in current.alerts if a.gpu_id == gpu.gpu_id]
        border = "#1e293b"
        if any(a.severity == "critical" for a in gpu_alerts): border = "#ef4444"
        elif any(a.severity == "warning" for a in gpu_alerts): border = "#f59e0b"
        elements.append(f'<rect x="{cx}" y="{cy}" width="{card_w}" height="{card_h}" rx="8" fill="#1e293b" stroke="{border}" stroke-width="2"/>')
        elements.append(_text(cx + 12, cy + 22, f"GPU{gpu.gpu_id}", font_size=16, fill="#f1f5f9", bold=True))
        elements.append(_text(cx + 12, cy + 38, gpu.running_job, font_size=10, fill="#94a3b8"))
        vram_pct = (gpu.vram_used_gb / gpu.vram_total_gb) * 100
        rows = [("VRAM", f"{gpu.vram_used_gb:.1f}/{gpu.vram_total_gb:.0f} GB ({vram_pct:.0f}%)"),
                ("UTIL", f"{gpu.utilization_pct:.1f}%"), ("TEMP", f"{gpu.temp_c:.1f} °C"),
                ("POWER", f"{gpu.power_w:.0f} W"), ("ERR", f"{gpu.error_rate_pct:.3f}%")]
        if gpu.p50_latency_ms > 0: rows.append(("P50", f"{gpu.p50_latency_ms:.0f} ms"))
        for row_i, (label, val) in enumerate(rows):
            ry = cy + 58 + row_i * 15
            elements.append(_text(cx + 12, ry, label, font_size=10, fill="#64748b"))
            elements.append(_text(cx + 70, ry, val, font_size=10, fill="#cbd5e1"))
        spark_vals = [s.gpus[idx].utilization_pct for s in history]
        spark_x, spark_y = cx + 12, cy + 148
        spark_w, spark_h = card_w - 24, 36
        elements.append(f'<rect x="{spark_x}" y="{spark_y}" width="{spark_w}" height="{spark_h}" fill="#0f172a" rx="3"/>')
        elements.append(_text(spark_x, spark_y - 4, "24h Utilization", font_size=9, fill="#475569"))
        color = "#60a5fa" if border == "#1e293b" else border
        elements.append(_sparkline(spark_vals, spark_x, spark_y, spark_w, spark_h, color=color))
        for ai, alert in enumerate(gpu_alerts[:2]):
            badge_x = cx + 12 + ai * 95
            badge_y = cy + card_h - 14
            bc = severity_color.get(alert.severity, "#64748b")
            elements.append(f'<rect x="{badge_x}" y="{badge_y - 10}" width="90" height="12" rx="3" fill="{bc}" opacity="0.2"/>')
            elements.append(_text(badge_x + 4, badge_y, alert.severity.upper(), font_size=8, fill=bc, bold=True))
    elements.append("</svg>")
    return "\n".join(elements)


def svg_heatmap(history: List[ClusterSnapshot]) -> str:
    n_hours, n_gpus = 24, 4
    cell_w, cell_h = 36, 32
    left_margin, top_margin = 80, 50
    svg_w = left_margin + n_hours * cell_w + 20
    svg_h = top_margin + n_gpus * cell_h + 40
    matrix = np.zeros((n_gpus, n_hours))
    for hour in range(n_hours):
        start = hour * 12
        end = min(start + 12, len(history))
        for gid in range(n_gpus):
            vals = [history[s].gpus[gid].utilization_pct for s in range(start, end)]
            matrix[gid, hour] = np.mean(vals) if vals else 0.0
    def _heat_color(v):
        v = max(0.0, min(100.0, v))
        if v < 50:
            t = v / 50; r = int(30 + t * 50); g = int(100 + t * 100); b = int(200 - t * 50)
        elif v < 80:
            t = (v - 50) / 30; r = int(80 + t * 160); g = int(200 - t * 80); b = int(150 - t * 130)
        else:
            t = (v - 80) / 20; r = 240; g = int(120 - t * 100); b = 20
        return f"rgb({r},{g},{b})"
    elements = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{svg_w}" height="{svg_h}" style="background:#0f172a; font-family:monospace;">',
        _text(10, 22, "Cluster Utilization Heatmap — 4 GPUs × 24 Hours", font_size=14, fill="#94a3b8", bold=True),
    ]
    for gid in range(n_gpus):
        gy = top_margin + gid * cell_h
        elements.append(_text(left_margin - 8, gy + cell_h // 2 + 4, f"GPU{gid}", font_size=11, fill="#94a3b8", anchor="end"))
        for hour in range(n_hours):
            val = matrix[gid, hour]
            cx_ = left_margin + hour * cell_w
            fill = _heat_color(val)
            elements.append(f'<rect x="{cx_}" y="{gy}" width="{cell_w - 2}" height="{cell_h - 2}" fill="{fill}" rx="2"/>')
            if cell_w >= 30:
                elements.append(_text(cx_ + cell_w // 2 - 2, gy + cell_h // 2 + 4, f"{val:.0f}", font_size=8, fill="#000000", anchor="middle"))
    for hour in range(0, n_hours, 4):
        lx = left_margin + hour * cell_w + cell_w // 2
        ly = top_margin + n_gpus * cell_h + 16
        elements.append(_text(lx, ly, f"{hour:02d}h", font_size=9, fill="#64748b", anchor="middle"))
    elements.append("</svg>")
    return "\n".join(elements)


def svg_alert_timeline(history: List[ClusterSnapshot]) -> str:
    svg_w, svg_h = 1200, 200
    left_m, right_m, top_m = 80, 20, 40
    line_spacing, n_gpus = 30, 4
    timeline_w = svg_w - left_m - right_m
    n_steps = len(history)
    severity_colors = {"critical": "#ef4444", "warning": "#f59e0b", "info": "#60a5fa"}
    elements = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{svg_w}" height="{svg_h}" style="background:#0f172a; font-family:monospace;">',
        _text(10, 22, "Alert Timeline — 24 Hours (red=critical, amber=warning)", font_size=14, fill="#94a3b8", bold=True),
    ]
    for gid in range(n_gpus):
        ly = top_m + gid * line_spacing
        elements.append(f'<line x1="{left_m}" y1="{ly}" x2="{left_m + timeline_w}" y2="{ly}" stroke="#1e293b" stroke-width="1"/>')
        elements.append(_text(left_m - 8, ly + 4, f"GPU{gid}", font_size=10, fill="#64748b", anchor="end"))
    for step_idx, snap in enumerate(history):
        for alert in snap.alerts:
            gid = alert.gpu_id
            lx = left_m + (step_idx / max(n_steps - 1, 1)) * timeline_w
            ly = top_m + gid * line_spacing
            color = severity_colors.get(alert.severity, "#64748b")
            r = 5 if alert.severity == "critical" else 3
            elements.append(f'<circle cx="{lx:.1f}" cy="{ly:.1f}" r="{r}" fill="{color}" opacity="0.9"/>')
    for h in range(0, 25, 4):
        step_ = min(int(h * 12), n_steps - 1)
        lx = left_m + (step_ / max(n_steps - 1, 1)) * timeline_w
        ly = top_m + n_gpus * line_spacing + 16
        elements.append(_text(lx, ly, f"{h:02d}h", font_size=9, fill="#475569", anchor="middle"))
    lx0 = svg_w - 200
    for li, (sev, col) in enumerate(severity_colors.items()):
        elements.append(f'<circle cx="{lx0}" cy="{top_m + li * 18}" r="5" fill="{col}"/>')
        elements.append(_text(lx0 + 12, top_m + li * 18 + 4, sev, font_size=10, fill=col))
    elements.append("</svg>")
    return "\n".join(elements)


HTML_TEMPLATE = """\
<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"/>
<title>OCI Robot Cloud — GPU Cluster Monitor</title>
<style>*{{box-sizing:border-box;margin:0;padding:0}}body{{background:#0f172a;color:#e2e8f0;font-family:monospace;padding:24px}}h1{{color:#60a5fa;font-size:22px;margin-bottom:4px}}.subtitle{{color:#475569;font-size:13px;margin-bottom:24px}}.section{{margin-bottom:32px}}.section-title{{color:#94a3b8;font-size:14px;font-weight:bold;border-bottom:1px solid #1e293b;padding-bottom:6px;margin-bottom:12px}}.stats-grid{{display:grid;grid-template-columns:repeat(6,1fr);gap:12px;margin-bottom:24px}}.stat-card{{background:#1e293b;border-radius:8px;padding:12px;text-align:center}}.stat-value{{font-size:22px;font-weight:bold;color:#60a5fa}}.stat-label{{font-size:11px;color:#64748b;margin-top:4px}}.alert-list{{list-style:none}}.alert-list li{{padding:6px 10px;border-radius:4px;margin-bottom:4px;font-size:12px}}.alert-critical{{background:rgba(239,68,68,0.15);color:#fca5a5;border-left:3px solid #ef4444}}.alert-warning{{background:rgba(245,158,11,0.15);color:#fcd34d;border-left:3px solid #f59e0b}}.svg-wrap{{overflow-x:auto}}footer{{color:#334155;font-size:11px;margin-top:32px;text-align:center}}</style>
</head><body>
<h1>OCI Robot Cloud — GPU Cluster Monitor</h1>
<div class="subtitle">Host: 138.1.153.110 &nbsp;|&nbsp; 4× A100-SXM4-80GB &nbsp;|&nbsp; Generated: {generated_at}</div>
<div class="stats-grid">
  <div class="stat-card"><div class="stat-value">{uptime_pct}%</div><div class="stat-label">Cluster Uptime</div></div>
  <div class="stat-card"><div class="stat-value">{avg_util}%</div><div class="stat-label">Avg Utilization</div></div>
  <div class="stat-card"><div class="stat-value">{thermal_events}</div><div class="stat-label">Thermal Events</div></div>
  <div class="stat-card"><div class="stat-value">{vram_peak} GB</div><div class="stat-label">Peak VRAM Used</div></div>
  <div class="stat-card"><div class="stat-value">{gpu_hours}</div><div class="stat-label">GPU-Hours</div></div>
  <div class="stat-card"><div class="stat-value">{active_alerts}</div><div class="stat-label">Active Alerts</div></div>
</div>
<div class="section"><div class="section-title">Current Alerts</div><ul class="alert-list">{alert_items}</ul></div>
<div class="section"><div class="section-title">GPU Status Cards</div><div class="svg-wrap">{svg_cards}</div></div>
<div class="section"><div class="section-title">Utilization Heatmap</div><div class="svg-wrap">{svg_heatmap}</div></div>
<div class="section"><div class="section-title">Alert Timeline</div><div class="svg-wrap">{svg_timeline}</div></div>
<footer>OCI Robot Cloud Monitoring &mdash; GR00T N1.6 Inference + Fine-tuning + SDG + Staging</footer>
</body></html>
"""


def generate_html(history: List[ClusterSnapshot], output_path: str = "/tmp/gpu_cluster_monitor.html") -> None:
    current = get_current_snapshot(history)
    stats = compute_stats(history)
    if current.alerts:
        items = "\n".join(f'<li class="alert-{a.severity}">[{a.severity.upper()}] {a.message} (threshold={a.threshold}, actual={a.actual_value:.2f})</li>' for a in current.alerts)
    else:
        items = '<li style="color:#22c55e; padding:6px 10px;">No active alerts — all systems nominal</li>'
    html = HTML_TEMPLATE.format(
        generated_at=current.timestamp, uptime_pct=stats["uptime_pct"],
        avg_util=stats["avg_utilization_pct"], thermal_events=stats["thermal_events_count"],
        vram_peak=stats["vram_peak_gb"], gpu_hours=stats["total_gpu_hours"],
        active_alerts=len(current.alerts), alert_items=items,
        svg_cards=svg_gpu_cards(current, history),
        svg_heatmap=svg_heatmap(history),
        svg_timeline=svg_alert_timeline(history),
    )
    with open(output_path, "w") as fh:
        fh.write(html)
    print(f"[monitor] HTML report written to {output_path}")


def print_status(current: ClusterSnapshot, stats: dict) -> None:
    sep = "=" * 70
    print(sep)
    print(f"  OCI Robot Cloud — GPU Cluster Status @ {current.timestamp}")
    print(sep)
    print(f"  Cluster avg utilization : {current.cluster_utilization_avg:.1f}%")
    print(f"  Total VRAM used         : {current.total_vram_used_gb:.1f} GB / {4 * 80} GB total")
    print()
    print(f"  {'GPU':<6} {'Job':<25} {'Util':>5} {'VRAM':>16} {'Temp':>7} {'Power':>7} {'P50':>8} {'Err':>6}")
    print(f"  {'-'*6} {'-'*25} {'-'*5} {'-'*16} {'-'*7} {'-'*7} {'-'*8} {'-'*6}")
    for g in current.gpus:
        vram_pct = (g.vram_used_gb / g.vram_total_gb) * 100
        lat_str = f"{g.p50_latency_ms:.0f}ms" if g.p50_latency_ms > 0 else "  N/A"
        print(f"  GPU{g.gpu_id}  {g.running_job:<25} {g.utilization_pct:>4.1f}% {g.vram_used_gb:>5.1f}/{g.vram_total_gb:.0f}GB ({vram_pct:>3.0f}%) {g.temp_c:>5.1f}°C {g.power_w:>5.0f}W {lat_str:>7} {g.error_rate_pct:>5.3f}%")
    print()
    if current.alerts:
        print("  ALERTS:")
        for a in current.alerts:
            marker = "!! " if a.severity == "critical" else "!  "
            print(f"  {marker}[{a.severity.upper():<8}] {a.message}")
    else:
        print("  STATUS: All systems nominal — no active alerts")
    print()
    print("  24h Summary:")
    print(f"    Uptime           : {stats['uptime_pct']}%")
    print(f"    Avg Utilization  : {stats['avg_utilization_pct']}%")
    print(f"    Thermal Events   : {stats['thermal_events_count']}")
    print(f"    Peak VRAM        : {stats['vram_peak_gb']} GB")
    print(f"    GPU-Hours Used   : {stats['total_gpu_hours']}")
    print(sep)


def build_fastapi_app(history: List[ClusterSnapshot]):
    try:
        from fastapi import FastAPI
        from fastapi.responses import HTMLResponse, JSONResponse
    except ImportError:
        print("[monitor] FastAPI not installed. Run: pip install fastapi uvicorn")
        sys.exit(1)
    app = FastAPI(title="OCI GPU Cluster Monitor", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        import os
        path = "/tmp/gpu_cluster_monitor.html"
        if os.path.exists(path):
            with open(path) as fh:
                return HTMLResponse(fh.read())
        return HTMLResponse("<h1>Report not yet generated.</h1>")

    @app.get("/api/status")
    async def api_status():
        current = get_current_snapshot(history)
        stats = compute_stats(history)
        return JSONResponse({"timestamp": current.timestamp,
                             "cluster_utilization_avg": current.cluster_utilization_avg,
                             "total_vram_used_gb": current.total_vram_used_gb,
                             "gpus": [asdict(g) for g in current.gpus], "stats": stats})

    @app.get("/api/alerts")
    async def api_alerts():
        current = get_current_snapshot(history)
        all_alerts = [{"gpu_id": a.gpu_id, "severity": a.severity, "message": a.message,
                       "threshold": a.threshold, "actual_value": a.actual_value}
                      for snap in history[-12:] for a in snap.alerts]
        return JSONResponse({"current_alerts": [asdict(a) for a in current.alerts],
                             "last_hour_alerts": all_alerts})
    return app


def main() -> None:
    parser = argparse.ArgumentParser(description="OCI Robot Cloud GPU Cluster Monitor")
    parser.add_argument("--serve", action="store_true", help="Start FastAPI server on port 8073")
    parser.add_argument("--output", default="/tmp/gpu_cluster_monitor.html")
    args = parser.parse_args()
    print("[monitor] Simulating 24h of GPU telemetry (seed=42) …")
    history = simulate_history(seed=42)
    current = get_current_snapshot(history)
    stats = compute_stats(history)
    print_status(current, stats)
    generate_html(history, output_path=args.output)
    if args.serve:
        try:
            import uvicorn
        except ImportError:
            print("[monitor] uvicorn not installed. Run: pip install fastapi uvicorn")
            sys.exit(1)
        app = build_fastapi_app(history)
        print("[monitor] Starting FastAPI server on http://0.0.0.0:8073 …")
        uvicorn.run(app, host="0.0.0.0", port=8073)


if __name__ == "__main__":
    main()
