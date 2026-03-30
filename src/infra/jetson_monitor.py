"""
jetson_monitor.py — Jetson AGX Orin Edge Deployment Monitor
OCI Robot Cloud | src/infra/jetson_monitor.py

Monitors deployed robot policies on Jetson AGX Orin edge devices for all
design-partner deployments. Tracks inference health, performance, and policy
drift in real time.

USAGE
-----
# Show status of all registered devices
python src/infra/jetson_monitor.py --status

# Show detailed view for a single device
python src/infra/jetson_monitor.py --device-id r1

# Generate update manifest for a remote model push
python src/infra/jetson_monitor.py --update-model --device-id r1 --checkpoint /tmp/checkpoints/gr00t_step5000.pt

# Export CSV report for monthly uptime review
python src/infra/jetson_monitor.py --export-csv /tmp/jetson_monitor.csv

# Generate HTML dashboard (saved to ./jetson_dashboard.html by default)
python src/infra/jetson_monitor.py --dashboard
python src/infra/jetson_monitor.py --dashboard --out /tmp/robot_dashboard.html

DEVICE REGISTRY
---------------
5 seeded devices:
  r1, r2  — ACME Robotics (San Jose)
  r3      — Internal Test Bench (OCI Ashburn)
  r4      — AutoBot Inc (Detroit)
  r5      — DeepManip AI (Boston)

DRIFT ALERT RULES
-----------------
  DEGRADED if:
    - success_rate_24h drops >15pp below device baseline  (e.g. baseline=0.88 → alert <0.73)
    - latest inference latency >350ms
  OFFLINE if:
    - last_seen >10 minutes ago (simulated: device marked offline explicitly)

EXIT CODES
----------
  0  — all devices healthy
  1  — one or more devices degraded or offline
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import random
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LATENCY_ALERT_MS = 350.0          # ms — flag as degraded above this
DRIFT_PP_THRESHOLD = 0.15         # percentage-point drop from baseline
OFFLINE_MINUTES = 10              # minutes without heartbeat → offline
HISTORY_READINGS = 24             # number of hourly readings kept per device
MOCK_SEED = 2026_03_29            # deterministic seed for demo reproducibility

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class DeviceRecord:
    """Static registry entry for a Jetson deployment."""
    device_id: str
    partner_id: str
    model_version: str
    ip: str
    location: str
    status: str               # healthy | degraded | offline
    last_seen: str            # ISO-8601 UTC
    baseline_success_rate: float  # partner SLA baseline (0–1)


@dataclass
class DeviceHealth:
    """Live telemetry snapshot from one poll cycle."""
    device_id: str
    latency_ms: float
    success_rate_24h: float
    memory_mb: float
    temp_c: float
    uptime_h: float
    polled_at: str            # ISO-8601 UTC
    latency_history: List[float] = field(default_factory=list)  # last 24h hourly


@dataclass
class DriftAlert:
    device_id: str
    reason: str               # "latency" | "success_rate"
    value: float
    threshold: float
    severity: str             # "warning" | "critical"


# ---------------------------------------------------------------------------
# Device registry (seeded)
# ---------------------------------------------------------------------------

DEVICE_REGISTRY: List[DeviceRecord] = [
    DeviceRecord(
        device_id="r1",
        partner_id="acme-robotics",
        model_version="gr00t-n1.6-ft-step5000",
        ip="10.18.4.11",
        location="ACME Robotics HQ — San Jose, CA",
        status="healthy",
        last_seen="2026-03-29T14:52:01Z",
        baseline_success_rate=0.88,
    ),
    DeviceRecord(
        device_id="r2",
        partner_id="acme-robotics",
        model_version="gr00t-n1.6-ft-step5000",
        ip="10.18.4.12",
        location="ACME Robotics Assembly Line B — San Jose, CA",
        status="healthy",
        last_seen="2026-03-29T14:51:47Z",
        baseline_success_rate=0.87,
    ),
    DeviceRecord(
        device_id="r3",
        partner_id="oci-internal",
        model_version="gr00t-n1.6-ft-step10000",
        ip="10.0.0.31",
        location="OCI Robot Cloud Test Bench — Ashburn, VA",
        status="healthy",
        last_seen="2026-03-29T14:52:10Z",
        baseline_success_rate=0.92,
    ),
    DeviceRecord(
        device_id="r4",
        partner_id="autobot-inc",
        model_version="gr00t-n1.6-ft-step3000",
        ip="172.20.1.55",
        location="AutoBot Inc Pilot Cell — Detroit, MI",
        status="degraded",
        last_seen="2026-03-29T14:49:03Z",
        baseline_success_rate=0.85,
    ),
    DeviceRecord(
        device_id="r5",
        partner_id="deepmanip-ai",
        model_version="gr00t-n1.6-ft-step7500",
        ip="192.168.88.20",
        location="DeepManip AI Lab — Boston, MA",
        status="offline",
        last_seen="2026-03-29T13:11:22Z",
        baseline_success_rate=0.90,
    ),
]

REGISTRY_BY_ID = {d.device_id: d for d in DEVICE_REGISTRY}

# ---------------------------------------------------------------------------
# Mock telemetry generation
# ---------------------------------------------------------------------------

def _seeded_rng(device_id: str) -> random.Random:
    seed = MOCK_SEED + sum(ord(c) for c in device_id)
    return random.Random(seed)


def _generate_latency_history(device_id: str, device_status: str) -> List[float]:
    """Generate 24 hourly latency readings (ms) with realistic noise."""
    rng = _seeded_rng(device_id)
    base = rng.uniform(185.0, 225.0)
    history = []
    for i in range(HISTORY_READINGS):
        jitter = rng.gauss(0, 12.0)
        val = base + jitter
        # Inject a degradation spike for 'degraded' devices in hour windows 18-22
        if device_status == "degraded" and 16 <= i <= 21:
            val += rng.uniform(130.0, 200.0)
        val = max(150.0, val)
        history.append(round(val, 1))
    return history


def poll_device(record: DeviceRecord) -> Optional[DeviceHealth]:
    """Simulate a heartbeat poll; returns None for offline devices."""
    if record.status == "offline":
        return None

    rng = _seeded_rng(record.device_id)

    if record.status == "degraded":
        latency_ms = round(rng.uniform(340.0, 420.0), 1)
        success_rate_24h = round(record.baseline_success_rate - rng.uniform(0.16, 0.28), 3)
        temp_c = round(rng.uniform(68.0, 79.0), 1)
        memory_mb = round(rng.uniform(5800.0, 7200.0), 0)
    else:
        latency_ms = round(rng.uniform(185.0, 245.0), 1)
        success_rate_24h = round(record.baseline_success_rate - rng.uniform(0.0, 0.04), 3)
        temp_c = round(rng.uniform(44.0, 58.0), 1)
        memory_mb = round(rng.uniform(3200.0, 4600.0), 0)

    uptime_h = round(rng.uniform(24.0, 720.0), 1)
    polled_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    latency_history = _generate_latency_history(record.device_id, record.status)

    return DeviceHealth(
        device_id=record.device_id,
        latency_ms=latency_ms,
        success_rate_24h=success_rate_24h,
        memory_mb=memory_mb,
        temp_c=temp_c,
        uptime_h=uptime_h,
        polled_at=polled_at,
        latency_history=latency_history,
    )


# ---------------------------------------------------------------------------
# Drift detection
# ---------------------------------------------------------------------------

def check_drift(record: DeviceRecord, health: DeviceHealth) -> List[DriftAlert]:
    alerts: List[DriftAlert] = []

    latency_drop = health.latency_ms - LATENCY_ALERT_MS
    if latency_drop > 0:
        severity = "critical" if latency_drop > 100 else "warning"
        alerts.append(DriftAlert(
            device_id=record.device_id,
            reason="latency",
            value=health.latency_ms,
            threshold=LATENCY_ALERT_MS,
            severity=severity,
        ))

    rate_drop = record.baseline_success_rate - health.success_rate_24h
    if rate_drop > DRIFT_PP_THRESHOLD:
        severity = "critical" if rate_drop > 0.25 else "warning"
        alerts.append(DriftAlert(
            device_id=record.device_id,
            reason="success_rate",
            value=health.success_rate_24h,
            threshold=record.baseline_success_rate - DRIFT_PP_THRESHOLD,
            severity=severity,
        ))

    return alerts


# ---------------------------------------------------------------------------
# CLI: --status
# ---------------------------------------------------------------------------

STATUS_ICONS = {
    "healthy":  "\033[92m●\033[0m",   # green
    "degraded": "\033[93m●\033[0m",   # yellow
    "offline":  "\033[91m●\033[0m",   # red
}

def cmd_status(device_filter: Optional[str] = None) -> int:
    """Print status table; return exit code (1 if any non-healthy)."""
    devices = DEVICE_REGISTRY
    if device_filter:
        devices = [d for d in DEVICE_REGISTRY if d.device_id == device_filter]
        if not devices:
            print(f"[ERROR] Unknown device-id: {device_filter}", file=sys.stderr)
            return 1

    all_healthy = True
    now = datetime.now(timezone.utc)

    header = f"{'ID':<6} {'PARTNER':<20} {'MODEL':<34} {'STATUS':<10} {'LATENCY':>9} {'SUCCESS':>8} {'MEM MB':>8} {'TEMP C':>7} {'UPTIME H':>9}"
    print(header)
    print("─" * len(header))

    for record in devices:
        health = poll_device(record)
        icon = STATUS_ICONS.get(record.status, "?")

        if health is None:
            lat = "—"
            sr = "—"
            mem = "—"
            tmp = "—"
            upt = "—"
        else:
            lat = f"{health.latency_ms:.0f}ms"
            sr = f"{health.success_rate_24h * 100:.1f}%"
            mem = f"{health.memory_mb:.0f}"
            tmp = f"{health.temp_c:.1f}"
            upt = f"{health.uptime_h:.1f}"

        status_str = f"{icon} {record.status}"
        print(
            f"{record.device_id:<6} {record.partner_id:<20} {record.model_version:<34} "
            f"{status_str:<18} {lat:>9} {sr:>8} {mem:>8} {tmp:>7} {upt:>9}"
        )

        if record.status != "healthy":
            all_healthy = False

        # Drift alerts
        if health:
            alerts = check_drift(record, health)
            for alert in alerts:
                print(f"  ⚠  DRIFT [{alert.severity.upper()}] {alert.reason}: "
                      f"{alert.value:.1f} > threshold {alert.threshold:.1f}")

    print()
    if all_healthy:
        print("All devices healthy.")
        return 0
    else:
        print("One or more devices require attention.")
        return 1


# ---------------------------------------------------------------------------
# CLI: --update-model
# ---------------------------------------------------------------------------

def cmd_update_model(device_id: str, checkpoint: str) -> int:
    if device_id not in REGISTRY_BY_ID:
        print(f"[ERROR] Unknown device-id: {device_id}", file=sys.stderr)
        return 1

    record = REGISTRY_BY_ID[device_id]
    checkpoint_path = Path(checkpoint)
    manifest = {
        "manifest_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "target_device": {
            "device_id": record.device_id,
            "partner_id": record.partner_id,
            "ip": record.ip,
            "location": record.location,
        },
        "current_model_version": record.model_version,
        "update": {
            "checkpoint_path": str(checkpoint_path),
            "checkpoint_name": checkpoint_path.name,
            "new_model_version": f"gr00t-n1.6-ft-{checkpoint_path.stem}",
            "deploy_strategy": "rolling",
            "rollback_on_degradation": True,
            "drift_threshold_pp": DRIFT_PP_THRESHOLD,
            "latency_alert_ms": LATENCY_ALERT_MS,
        },
        "instructions": [
            f"scp {checkpoint} robot@{record.ip}:/opt/oci_robot_cloud/checkpoints/",
            f"ssh robot@{record.ip} 'sudo systemctl stop gr00t-inference'",
            f"ssh robot@{record.ip} 'gr00t-serve --checkpoint /opt/oci_robot_cloud/checkpoints/{checkpoint_path.name} --port 8001 &'",
            f"ssh robot@{record.ip} 'sudo systemctl start gr00t-inference'",
        ],
    }

    out_path = f"/tmp/update_manifest_{device_id}_{checkpoint_path.stem}.json"
    with open(out_path, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"Update manifest generated: {out_path}")
    print(json.dumps(manifest, indent=2))
    return 0


# ---------------------------------------------------------------------------
# CLI: --export-csv
# ---------------------------------------------------------------------------

def cmd_export_csv(out_path: str) -> int:
    rows = []
    now_str = datetime.now(timezone.utc).isoformat(timespec="seconds")

    for record in DEVICE_REGISTRY:
        health = poll_device(record)
        row = {
            "device_id": record.device_id,
            "partner_id": record.partner_id,
            "model_version": record.model_version,
            "ip": record.ip,
            "location": record.location,
            "status": record.status,
            "last_seen": record.last_seen,
            "baseline_success_rate": record.baseline_success_rate,
            "polled_at": health.polled_at if health else now_str,
            "latency_ms": health.latency_ms if health else "",
            "success_rate_24h": health.success_rate_24h if health else "",
            "memory_mb": health.memory_mb if health else "",
            "temp_c": health.temp_c if health else "",
            "uptime_h": health.uptime_h if health else "",
        }
        if health:
            alerts = check_drift(record, health)
            row["drift_alerts"] = "; ".join(
                f"{a.reason}:{a.severity}" for a in alerts
            )
        else:
            row["drift_alerts"] = "offline"
        rows.append(row)

    fieldnames = list(rows[0].keys())
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Exported {len(rows)} device records to: {out_path}")
    return 0


# ---------------------------------------------------------------------------
# HTML dashboard (dark theme, no external deps)
# ---------------------------------------------------------------------------

_STATUS_BADGE_CSS = {
    "healthy":  ("badge-healthy",  "#22c55e"),
    "degraded": ("badge-degraded", "#f59e0b"),
    "offline":  ("badge-offline",  "#ef4444"),
}

def _sparkline_svg(values: List[float], width: int = 160, height: int = 40) -> str:
    """Render a tiny SVG polyline sparkline from a list of float values."""
    if not values:
        return ""
    mn, mx = min(values), max(values)
    rng = mx - mn if mx != mn else 1.0
    n = len(values)
    pts = []
    for i, v in enumerate(values):
        x = round(i / (n - 1) * width, 1) if n > 1 else width / 2
        y = round(height - ((v - mn) / rng) * (height - 4) - 2, 1)
        pts.append(f"{x},{y}")
    points_str = " ".join(pts)

    # Color: red if any reading > LATENCY_ALERT_MS, else cyan
    color = "#ef4444" if any(v > LATENCY_ALERT_MS for v in values) else "#22d3ee"

    return (
        f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
        f'xmlns="http://www.w3.org/2000/svg">'
        f'<polyline points="{points_str}" fill="none" stroke="{color}" '
        f'stroke-width="1.5" stroke-linejoin="round" stroke-linecap="round"/>'
        f'</svg>'
    )


def _gauge_arc(pct: float, size: int = 80) -> str:
    """SVG semicircle gauge for success rate."""
    r = size * 0.38
    cx = size / 2
    cy = size * 0.6
    circumference = math.pi * r
    arc_len = circumference * min(max(pct, 0.0), 1.0)
    gap = circumference - arc_len

    color = "#22c55e" if pct >= 0.80 else ("#f59e0b" if pct >= 0.65 else "#ef4444")

    bg_path = (
        f'M {cx - r} {cy} '
        f'A {r} {r} 0 0 1 {cx + r} {cy}'
    )
    fg_path = bg_path

    return (
        f'<svg width="{size}" height="{size // 2 + 10}" '
        f'viewBox="0 0 {size} {size // 2 + 10}" xmlns="http://www.w3.org/2000/svg">'
        # background arc
        f'<path d="{bg_path}" fill="none" stroke="#374151" stroke-width="7" stroke-linecap="round"/>'
        # foreground arc
        f'<path d="{fg_path}" fill="none" stroke="{color}" stroke-width="7" '
        f'stroke-linecap="round" '
        f'stroke-dasharray="{arc_len:.2f} {gap:.2f}"/>'
        # label
        f'<text x="{cx}" y="{cy - 4}" text-anchor="middle" '
        f'font-size="11" font-family="monospace" fill="{color}" font-weight="bold">'
        f'{pct * 100:.1f}%</text>'
        f'</svg>'
    )


def cmd_dashboard(out_path: str) -> int:
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # Build cards
    cards_html = ""
    for record in DEVICE_REGISTRY:
        health = poll_device(record)
        badge_cls, badge_color = _STATUS_BADGE_CSS.get(record.status, ("", "#6b7280"))

        if health:
            alerts = check_drift(record, health)
            sparkline = _sparkline_svg(health.latency_history)
            gauge = _gauge_arc(health.success_rate_24h)
            lat_color = "#ef4444" if health.latency_ms > LATENCY_ALERT_MS else "#22d3ee"
            alert_rows = "".join(
                f'<tr><td class="alert-cell">⚠ {a.reason} — {a.severity.upper()}: '
                f'{a.value:.1f} (threshold {a.threshold:.1f})</td></tr>'
                for a in alerts
            )
            alert_block = (
                f'<table class="alert-table">{alert_rows}</table>'
                if alert_rows else ""
            )
            stats_html = f"""
            <div class="stat-row">
              <span class="stat-label">Latency</span>
              <span class="stat-val" style="color:{lat_color}">{health.latency_ms:.0f} ms</span>
            </div>
            <div class="stat-row">
              <span class="stat-label">Memory</span>
              <span class="stat-val">{health.memory_mb:.0f} MB</span>
            </div>
            <div class="stat-row">
              <span class="stat-label">Temp</span>
              <span class="stat-val">{health.temp_c:.1f} °C</span>
            </div>
            <div class="stat-row">
              <span class="stat-label">Uptime</span>
              <span class="stat-val">{health.uptime_h:.1f} h</span>
            </div>
            <div class="stat-row">
              <span class="stat-label">Polled</span>
              <span class="stat-val ts">{health.polled_at}</span>
            </div>
            """
            sparkline_html = f'<div class="sparkline-wrap"><div class="sparkline-label">Latency 24h</div>{sparkline}</div>'
            gauge_html = f'<div class="gauge-wrap"><div class="gauge-label">Success Rate 24h</div>{gauge}</div>'
        else:
            stats_html = '<div class="stat-row"><span class="stat-val offline-msg">Device unreachable</span></div>'
            sparkline_html = ""
            gauge_html = ""
            alert_block = ""

        cards_html += f"""
        <div class="card card-{record.status}">
          <div class="card-header">
            <span class="device-id">{record.device_id}</span>
            <span class="badge" style="background:{badge_color}20;color:{badge_color};border:1px solid {badge_color}40">{record.status.upper()}</span>
          </div>
          <div class="partner">{record.partner_id}</div>
          <div class="location">{record.location}</div>
          <div class="model-ver">{record.model_version}</div>
          <div class="ip-row">IP: {record.ip}</div>
          <div class="visuals-row">
            {gauge_html}
            {sparkline_html}
          </div>
          <div class="stats">
            {stats_html}
          </div>
          {alert_block}
          <div class="last-seen">Last seen: {record.last_seen}</div>
        </div>
        """

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>OCI Robot Cloud — Jetson Monitor</title>
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: #0f172a;
    color: #e2e8f0;
    font-family: 'Segoe UI', system-ui, sans-serif;
    min-height: 100vh;
    padding: 24px;
  }}
  header {{
    display: flex;
    align-items: baseline;
    gap: 16px;
    margin-bottom: 28px;
    border-bottom: 1px solid #1e293b;
    padding-bottom: 16px;
  }}
  header h1 {{
    font-size: 1.35rem;
    font-weight: 700;
    color: #f1f5f9;
    letter-spacing: -0.02em;
  }}
  header .subtitle {{
    font-size: 0.8rem;
    color: #64748b;
  }}
  .grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
    gap: 18px;
  }}
  .card {{
    background: #1e293b;
    border-radius: 12px;
    padding: 18px;
    border: 1px solid #334155;
    display: flex;
    flex-direction: column;
    gap: 8px;
    transition: box-shadow 0.2s;
  }}
  .card:hover {{ box-shadow: 0 4px 24px #0008; }}
  .card-degraded {{ border-color: #78350f; }}
  .card-offline {{ border-color: #7f1d1d; opacity: 0.8; }}
  .card-header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
  }}
  .device-id {{
    font-size: 1.1rem;
    font-weight: 700;
    color: #f8fafc;
    font-family: monospace;
  }}
  .badge {{
    font-size: 0.65rem;
    font-weight: 700;
    padding: 2px 8px;
    border-radius: 999px;
    letter-spacing: 0.05em;
  }}
  .partner {{
    font-size: 0.85rem;
    color: #94a3b8;
    font-weight: 600;
  }}
  .location {{
    font-size: 0.75rem;
    color: #64748b;
  }}
  .model-ver {{
    font-size: 0.72rem;
    color: #38bdf8;
    font-family: monospace;
    background: #0f172a;
    border-radius: 4px;
    padding: 2px 6px;
    display: inline-block;
  }}
  .ip-row {{
    font-size: 0.72rem;
    color: #475569;
    font-family: monospace;
  }}
  .visuals-row {{
    display: flex;
    align-items: flex-end;
    gap: 14px;
    margin-top: 4px;
  }}
  .gauge-wrap, .sparkline-wrap {{
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 2px;
  }}
  .gauge-label, .sparkline-label {{
    font-size: 0.65rem;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }}
  .stats {{
    margin-top: 2px;
    display: flex;
    flex-direction: column;
    gap: 3px;
  }}
  .stat-row {{
    display: flex;
    justify-content: space-between;
    font-size: 0.78rem;
  }}
  .stat-label {{ color: #64748b; }}
  .stat-val {{ color: #cbd5e1; font-family: monospace; }}
  .stat-val.ts {{ font-size: 0.65rem; color: #475569; }}
  .offline-msg {{ color: #ef4444; font-size: 0.8rem; }}
  .alert-table {{
    width: 100%;
    margin-top: 4px;
    border-collapse: collapse;
  }}
  .alert-cell {{
    font-size: 0.72rem;
    color: #fbbf24;
    padding: 3px 6px;
    background: #451a03;
    border-radius: 4px;
    margin-bottom: 2px;
    display: block;
  }}
  .last-seen {{
    font-size: 0.68rem;
    color: #334155;
    margin-top: 4px;
    border-top: 1px solid #1e293b;
    padding-top: 6px;
  }}
  footer {{
    margin-top: 36px;
    text-align: center;
    font-size: 0.72rem;
    color: #334155;
  }}
</style>
</head>
<body>
<header>
  <h1>OCI Robot Cloud — Jetson Edge Monitor</h1>
  <span class="subtitle">Generated {generated_at} &nbsp;|&nbsp; {len(DEVICE_REGISTRY)} devices</span>
</header>
<div class="grid">
{cards_html}
</div>
<footer>OCI Robot Cloud &bull; Jetson AGX Orin Deployment Monitor &bull; Drift threshold: {DRIFT_PP_THRESHOLD*100:.0f}pp / {LATENCY_ALERT_MS:.0f}ms</footer>
</body>
</html>
"""

    with open(out_path, "w") as f:
        f.write(html)
    print(f"Dashboard saved: {out_path}")
    return 0


# ---------------------------------------------------------------------------
# Argument parsing & entry point
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Jetson AGX Orin edge deployment monitor — OCI Robot Cloud",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--status", action="store_true",
                   help="Print status table for all (or filtered) devices")
    p.add_argument("--device-id", metavar="ID",
                   help="Filter to a single device (use with --status or --update-model)")
    p.add_argument("--update-model", action="store_true",
                   help="Generate a remote model-update manifest (requires --device-id and --checkpoint)")
    p.add_argument("--checkpoint", metavar="PATH",
                   help="Path to checkpoint file for --update-model")
    p.add_argument("--export-csv", metavar="PATH",
                   help="Export device health snapshot to CSV")
    p.add_argument("--dashboard", action="store_true",
                   help="Generate HTML dashboard")
    p.add_argument("--out", metavar="PATH", default="jetson_dashboard.html",
                   help="Output path for --dashboard (default: jetson_dashboard.html)")
    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.update_model:
        if not args.device_id:
            parser.error("--update-model requires --device-id")
        if not args.checkpoint:
            parser.error("--update-model requires --checkpoint")
        return cmd_update_model(args.device_id, args.checkpoint)

    if args.export_csv:
        return cmd_export_csv(args.export_csv)

    if args.dashboard:
        return cmd_dashboard(args.out)

    # Default: --status (also explicit)
    return cmd_status(device_filter=args.device_id)


if __name__ == "__main__":
    sys.exit(main())
