#!/usr/bin/env python3
"""OCI Robot Cloud — Inference Server Health Monitor.

Monitors the GR00T inference server (port 8001) and all supporting API
services, providing real-time status and alerting for production deployments.

Endpoints monitored (12 total):
  groot_inference  8001 | data_collector   8003 | finetune_service 8005
  eval_service     8006 | checkpoint_api   8008 | dagger_controller 8012
  metrics_api      8015 | model_registry   8018 | billing_api       8020
  safety_monitor   8022 | telemetry        8024 | ab_test_controller 8026

Health states: healthy / degraded / down / unknown

Alert rules:
  latency > 500ms          → warn
  consecutive_failures >= 3 → critical
  uptime_pct < 95%         → warn

SLA target: 99.5% uptime per service.

Usage:
    python inference_server_health_monitor.py --mock
    python inference_server_health_monitor.py --mock --output /tmp/health.html --seed 42
    python inference_server_health_monitor.py --host 138.1.153.110
"""

from __future__ import annotations

import argparse
import datetime
import http.server
import json
import math
import os
import random
import sys
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VERSION = "1.0.0"
MONITOR_PORT = 8073
SLA_TARGET_PCT = 99.5
LATENCY_WARN_MS = 500.0
CONSECUTIVE_FAIL_CRITICAL = 3
UPTIME_WARN_THRESHOLD = 95.0
HISTORY_HOURS = 24
INCIDENT_BUCKET_MINUTES = 5  # resolution of uptime timeline

# Colors for console output
class C:
    RESET  = "\033[0m"
    BOLD   = "\033[1m"
    GREEN  = "\033[92m"
    YELLOW = "\033[93m"
    RED    = "\033[91m"
    CYAN   = "\033[96m"
    GRAY   = "\033[90m"
    WHITE  = "\033[97m"


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class EndpointSpec:
    name: str
    port: int
    health_path: str = "/health"
    extra_metric_name: Optional[str] = None   # label for the extra metric
    extra_metric_path: Optional[str] = None   # path to fetch it (or mocked)


@dataclass
class HealthSample:
    """A single health probe result."""
    ts: float           # unix timestamp
    latency_ms: float   # -1 if unreachable
    status: str         # healthy / degraded / down


@dataclass
class EndpointStatus:
    spec: EndpointSpec
    state: str = "unknown"          # healthy / degraded / down / unknown
    latency_ms: float = -1.0
    uptime_pct: float = 100.0       # last 24h
    last_error: str = ""
    consecutive_failures: int = 0
    extra_metric_value: Any = None  # queue depth, active jobs, etc.
    history: List[HealthSample] = field(default_factory=list)  # 24h of 5-min buckets


# ---------------------------------------------------------------------------
# Endpoint definitions
# ---------------------------------------------------------------------------

ENDPOINT_SPECS: List[EndpointSpec] = [
    EndpointSpec("groot_inference",    8001, "/health",  "predict_ms",     "/predict"),
    EndpointSpec("data_collector",     8003, "/health",  "queue_depth",    "/status"),
    EndpointSpec("finetune_service",   8005, "/health",  "active_jobs",    "/jobs"),
    EndpointSpec("eval_service",       8006, "/health",  "pending_evals",  "/evals"),
    EndpointSpec("checkpoint_api",     8008, "/health",  "disk_free_gb",   "/storage"),
    EndpointSpec("dagger_controller",  8012, "/health",  "current_round",  "/status"),
    EndpointSpec("metrics_api",        8015, "/health"),
    EndpointSpec("model_registry",     8018, "/health"),
    EndpointSpec("billing_api",        8020, "/health"),
    EndpointSpec("safety_monitor",     8022, "/health",  "alert_count",    "/alerts"),
    EndpointSpec("telemetry",          8024, "/health",  "events_per_sec", "/stats"),
    EndpointSpec("ab_test_controller", 8026, "/health"),
]


# ---------------------------------------------------------------------------
# Mock data generator
# ---------------------------------------------------------------------------

def _simulate_history(
    spec: EndpointSpec,
    seed: int,
    now: float,
    groot_incident_start: float,
    groot_incident_end: float,
    checkpoint_incident_start: float,
    checkpoint_incident_end: float,
) -> List[HealthSample]:
    """Generate 24h of 5-minute health samples with 2 scripted incidents."""
    rng = random.Random(seed + spec.port)
    samples: List[HealthSample] = []
    start = now - HISTORY_HOURS * 3600
    t = start
    while t <= now:
        # Determine base latency for this service
        base_latency = {
            8001: 230.0,
            8003:  45.0,
            8005: 120.0,
            8006:  80.0,
            8008:  60.0,
            8012:  95.0,
            8015:  35.0,
            8018:  50.0,
            8020:  40.0,
            8022:  30.0,
            8024:  25.0,
            8026:  55.0,
        }.get(spec.port, 60.0)

        # Inject scripted incidents
        if spec.port == 8001 and groot_incident_start <= t <= groot_incident_end:
            # groot degraded: elevated latency, no full outage
            latency_ms = base_latency * rng.uniform(3.0, 6.0)
            status = "degraded"
        elif spec.port == 8008 and checkpoint_incident_start <= t <= checkpoint_incident_end:
            # checkpoint_api fully down
            latency_ms = -1.0
            status = "down"
        else:
            # Normal operations: small random jitter
            jitter = rng.gauss(0, base_latency * 0.08)
            latency_ms = max(5.0, base_latency + jitter)
            # Rare random blips (1% of buckets)
            if rng.random() < 0.01:
                latency_ms = base_latency * rng.uniform(1.5, 2.5)
                status = "degraded"
            else:
                status = "healthy"

        samples.append(HealthSample(ts=t, latency_ms=latency_ms, status=status))
        t += INCIDENT_BUCKET_MINUTES * 60

    return samples


def _compute_uptime(history: List[HealthSample]) -> float:
    if not history:
        return 100.0
    good = sum(1 for s in history if s.status in ("healthy", "degraded"))
    return round(100.0 * good / len(history), 2)


def _current_extra_metric(spec: EndpointSpec, rng: random.Random) -> Any:
    mapping = {
        "predict_ms":    lambda: round(rng.gauss(227, 15), 1),
        "queue_depth":   lambda: rng.randint(0, 12),
        "active_jobs":   lambda: rng.randint(0, 3),
        "pending_evals": lambda: rng.randint(0, 5),
        "disk_free_gb":  lambda: round(rng.uniform(180, 450), 1),
        "current_round": lambda: rng.randint(1, 8),
        "alert_count":   lambda: rng.randint(0, 2),
        "events_per_sec": lambda: round(rng.uniform(800, 2400), 0),
    }
    fn = mapping.get(spec.extra_metric_name)
    return fn() if fn else None


def build_mock_statuses(seed: int = 42) -> List[EndpointStatus]:
    rng = random.Random(seed)
    now = time.time()

    # --- scripted incidents ---
    # groot degraded for 45 min ending ~3h ago
    groot_end   = now - 3 * 3600
    groot_start = groot_end - 45 * 60
    # checkpoint_api down for 12 min ending ~8h ago
    ck_end   = now - 8 * 3600
    ck_start = ck_end - 12 * 60

    statuses: List[EndpointStatus] = []
    for spec in ENDPOINT_SPECS:
        history = _simulate_history(
            spec, seed, now,
            groot_start, groot_end,
            ck_start, ck_end,
        )
        uptime_pct = _compute_uptime(history)

        # Current (live) state
        base_latency = {
            8001: 231.0, 8003: 44.0,  8005: 118.0, 8006: 82.0,
            8008: 61.0,  8012: 93.0,  8015: 34.0,  8018: 51.0,
            8020: 41.0,  8022: 29.0,  8024: 26.0,  8026: 54.0,
        }.get(spec.port, 60.0)
        latency_ms = round(base_latency + rng.gauss(0, base_latency * 0.05), 1)
        state = "healthy"
        last_error = ""
        consecutive_failures = 0

        extra = _current_extra_metric(spec, rng)

        statuses.append(EndpointStatus(
            spec=spec,
            state=state,
            latency_ms=latency_ms,
            uptime_pct=uptime_pct,
            last_error=last_error,
            consecutive_failures=consecutive_failures,
            extra_metric_value=extra,
            history=history,
        ))

    return statuses


# ---------------------------------------------------------------------------
# Live probe
# ---------------------------------------------------------------------------

def _probe(url: str, timeout: float = 5.0) -> Tuple[float, bool, str]:
    """Return (latency_ms, ok, error_msg)."""
    t0 = time.time()
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "OCI-HealthMonitor/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            resp.read()
            latency_ms = (time.time() - t0) * 1000
            return latency_ms, True, ""
    except Exception as exc:
        latency_ms = (time.time() - t0) * 1000
        return latency_ms, False, str(exc)


def _apply_alert_rules(es: EndpointStatus) -> None:
    """Mutate es.state based on alert rules."""
    if es.state == "down":
        return  # already down
    if es.consecutive_failures >= CONSECUTIVE_FAIL_CRITICAL:
        es.state = "down"
    elif es.latency_ms > LATENCY_WARN_MS:
        es.state = "degraded"
    elif es.uptime_pct < UPTIME_WARN_THRESHOLD:
        es.state = "degraded"


def probe_live(host: str, statuses: List[EndpointStatus]) -> None:
    for es in statuses:
        url = f"http://{host}:{es.spec.port}{es.spec.health_path}"
        latency_ms, ok, err = _probe(url)
        if ok:
            es.latency_ms = round(latency_ms, 1)
            es.consecutive_failures = 0
            es.last_error = ""
            if latency_ms > LATENCY_WARN_MS:
                es.state = "degraded"
            else:
                es.state = "healthy"
        else:
            es.consecutive_failures += 1
            es.last_error = err[:120]
            if es.consecutive_failures >= CONSECUTIVE_FAIL_CRITICAL:
                es.state = "down"
            else:
                es.state = "unknown"
        _apply_alert_rules(es)


# ---------------------------------------------------------------------------
# Overall system status
# ---------------------------------------------------------------------------

def overall_status(statuses: List[EndpointStatus]) -> str:
    states = {es.state for es in statuses}
    if "down" in states:
        return "INCIDENT"
    if "degraded" in states or "unknown" in states:
        return "DEGRADED"
    return "ALL SYSTEMS OPERATIONAL"


# ---------------------------------------------------------------------------
# Incident log (derived from history)
# ---------------------------------------------------------------------------

@dataclass
class Incident:
    service: str
    start_ts: float
    end_ts: float
    severity: str  # degraded / down
    duration_min: float

    @property
    def start_str(self) -> str:
        return datetime.datetime.fromtimestamp(self.start_ts).strftime("%Y-%m-%d %H:%M")

    @property
    def end_str(self) -> str:
        return datetime.datetime.fromtimestamp(self.end_ts).strftime("%Y-%m-%d %H:%M")


def extract_incidents(statuses: List[EndpointStatus]) -> List[Incident]:
    incidents: List[Incident] = []
    for es in statuses:
        in_incident = False
        inc_start = 0.0
        inc_severity = ""
        prev_ts = 0.0
        for sample in es.history:
            bad = sample.status in ("degraded", "down")
            if bad and not in_incident:
                in_incident = True
                inc_start = sample.ts
                inc_severity = sample.status
            elif not bad and in_incident:
                in_incident = False
                duration = (prev_ts - inc_start) / 60
                incidents.append(Incident(
                    service=es.spec.name,
                    start_ts=inc_start,
                    end_ts=prev_ts,
                    severity=inc_severity,
                    duration_min=round(duration, 1),
                ))
            if bad:
                inc_severity = sample.status  # escalate if needed
            prev_ts = sample.ts
        # close open incident
        if in_incident and prev_ts > inc_start:
            duration = (prev_ts - inc_start) / 60
            incidents.append(Incident(
                service=es.spec.name,
                start_ts=inc_start,
                end_ts=prev_ts,
                severity=inc_severity,
                duration_min=round(duration, 1),
            ))
    # Sort newest first, keep last 10
    incidents.sort(key=lambda i: i.start_ts, reverse=True)
    return incidents[:10]


# ---------------------------------------------------------------------------
# Console output
# ---------------------------------------------------------------------------

def _state_color(state: str) -> str:
    return {
        "healthy":  C.GREEN,
        "degraded": C.YELLOW,
        "down":     C.RED,
        "unknown":  C.GRAY,
    }.get(state, C.GRAY)


def print_console_table(statuses: List[EndpointStatus]) -> None:
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sys_status = overall_status(statuses)
    sys_color = C.GREEN if sys_status == "ALL SYSTEMS OPERATIONAL" else (
        C.RED if sys_status == "INCIDENT" else C.YELLOW)

    print()
    print(f"{C.BOLD}{C.CYAN}OCI Robot Cloud — Inference Server Health Monitor v{VERSION}{C.RESET}")
    print(f"  {C.GRAY}Checked at: {now_str}{C.RESET}")
    print(f"  System: {sys_color}{C.BOLD}{sys_status}{C.RESET}")
    print()

    header = (
        f"  {'SERVICE':<22} {'PORT':>5}  {'STATE':>9}  {'LATENCY':>10}  "
        f"{'UPTIME(24h)':>11}  {'CONSEC.FAIL':>11}  EXTRA METRIC"
    )
    print(C.BOLD + header + C.RESET)
    print("  " + "-" * 100)

    for es in statuses:
        col = _state_color(es.state)
        lat_str = f"{es.latency_ms:.1f} ms" if es.latency_ms >= 0 else "   n/a   "
        up_str  = f"{es.uptime_pct:.2f}%"
        cf_str  = str(es.consecutive_failures)
        extra_str = ""
        if es.spec.extra_metric_name and es.extra_metric_value is not None:
            extra_str = f"{es.spec.extra_metric_name}={es.extra_metric_value}"

        # Warn indicator
        warn = ""
        if es.latency_ms > LATENCY_WARN_MS:
            warn = f" {C.YELLOW}[SLOW]{C.RESET}"
        if es.uptime_pct < UPTIME_WARN_THRESHOLD:
            warn += f" {C.YELLOW}[LOW-UPTIME]{C.RESET}"
        if es.consecutive_failures >= CONSECUTIVE_FAIL_CRITICAL:
            warn += f" {C.RED}[CRITICAL]{C.RESET}"

        print(
            f"  {col}{es.spec.name:<22}{C.RESET} "
            f"{es.spec.port:>5}  "
            f"{col}{es.state:>9}{C.RESET}  "
            f"{lat_str:>10}  "
            f"{up_str:>11}  "
            f"{cf_str:>11}  "
            f"{extra_str}{warn}"
        )

    print()
    # SLA compliance
    print(f"{C.BOLD}  SLA Compliance (target {SLA_TARGET_PCT}%):{C.RESET}")
    for es in statuses:
        ok = es.uptime_pct >= SLA_TARGET_PCT
        col = C.GREEN if ok else C.RED
        badge = "PASS" if ok else "FAIL"
        print(f"    {es.spec.name:<22} {col}{es.uptime_pct:.2f}% [{badge}]{C.RESET}")
    print()


# ---------------------------------------------------------------------------
# SVG uptime timeline
# ---------------------------------------------------------------------------

def _uptime_svg(history: List[HealthSample], width: int = 340, height: int = 20) -> str:
    """Return an inline SVG showing green/yellow/red bands over 24h."""
    if not history:
        return f'<svg width="{width}" height="{height}"></svg>'

    total = len(history)
    bw = width / total  # bucket width in px

    rects = []
    for i, sample in enumerate(history):
        color = {
            "healthy":  "#22c55e",
            "degraded": "#eab308",
            "down":     "#ef4444",
            "unknown":  "#6b7280",
        }.get(sample.status, "#6b7280")
        x = round(i * bw, 2)
        w = max(1, round(bw + 0.5, 2))
        rects.append(f'<rect x="{x}" y="0" width="{w}" height="{height}" fill="{color}"/>')

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'style="border-radius:4px;overflow:hidden;">'
        + "".join(rects)
        + "</svg>"
    )


# ---------------------------------------------------------------------------
# HTML report
# ---------------------------------------------------------------------------

_STATE_CSS = {
    "healthy":  ("#22c55e", "#14532d"),
    "degraded": ("#eab308", "#422006"),
    "down":     ("#ef4444", "#450a0a"),
    "unknown":  ("#9ca3af", "#1e293b"),
}

_BANNER_CSS = {
    "ALL SYSTEMS OPERATIONAL": ("background:#166534;color:#4ade80;"),
    "DEGRADED":                ("background:#78350f;color:#fde68a;"),
    "INCIDENT":                ("background:#7f1d1d;color:#fca5a5;"),
}


def build_html(statuses: List[EndpointStatus]) -> str:
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
    sys_status = overall_status(statuses)
    banner_style = _BANNER_CSS.get(sys_status, "")
    incidents = extract_incidents(statuses)

    # ---- cards ----
    cards_html = ""
    for es in statuses:
        fg, bg = _STATE_CSS.get(es.state, ("#9ca3af", "#1e293b"))
        lat_str = f"{es.latency_ms:.1f} ms" if es.latency_ms >= 0 else "n/a"
        up_warn = " ⚠" if es.uptime_pct < UPTIME_WARN_THRESHOLD else ""
        cf_badge = (
            f'<span style="background:#7f1d1d;color:#fca5a5;border-radius:4px;'
            f'padding:1px 6px;font-size:11px;margin-left:6px;">CRITICAL</span>'
            if es.consecutive_failures >= CONSECUTIVE_FAIL_CRITICAL else ""
        )
        extra_html = ""
        if es.spec.extra_metric_name and es.extra_metric_value is not None:
            extra_html = (
                f'<div style="margin-top:6px;font-size:12px;color:#94a3b8;">'
                f'{es.spec.extra_metric_name}: '
                f'<b style="color:#e2e8f0;">{es.extra_metric_value}</b></div>'
            )
        svg_html = _uptime_svg(es.history)
        sla_ok   = es.uptime_pct >= SLA_TARGET_PCT
        sla_col  = "#4ade80" if sla_ok else "#f87171"
        sla_lbl  = "PASS" if sla_ok else "FAIL"
        err_html = ""
        if es.last_error:
            err_html = (
                f'<div style="margin-top:6px;font-size:11px;color:#f87171;word-break:break-all;">'
                f'Error: {es.last_error}</div>'
            )

        cards_html += f"""
        <div style="background:{bg};border:1px solid {fg}33;border-radius:10px;
                    padding:14px 16px;display:flex;flex-direction:column;gap:4px;">
          <div style="display:flex;align-items:center;justify-content:space-between;">
            <span style="font-weight:700;font-size:14px;color:#f1f5f9;">
              {es.spec.name}
            </span>
            <span style="background:{fg}22;color:{fg};border:1px solid {fg};
                         border-radius:20px;padding:2px 10px;font-size:12px;font-weight:600;">
              {es.state.upper()}
            </span>
          </div>
          <div style="font-size:12px;color:#94a3b8;">Port {es.spec.port}</div>
          <div style="display:flex;gap:16px;margin-top:4px;font-size:13px;color:#cbd5e1;">
            <span>Latency: <b style="color:{fg};">{lat_str}</b></span>
            <span>Uptime: <b style="color:{sla_col};">{es.uptime_pct:.2f}%{up_warn}</b>
              <span style="font-size:10px;color:{sla_col};margin-left:4px;">[SLA {sla_lbl}]</span>
            </b></span>
            {cf_badge}
          </div>
          {extra_html}
          <div style="margin-top:8px;">
            <div style="font-size:10px;color:#64748b;margin-bottom:3px;">24h uptime timeline</div>
            {svg_html}
          </div>
          {err_html}
        </div>
"""

    # ---- incident log ----
    if incidents:
        rows = ""
        for inc in incidents:
            sev_col = "#eab308" if inc.severity == "degraded" else "#ef4444"
            rows += f"""
            <tr>
              <td>{inc.start_str}</td>
              <td>{inc.end_str}</td>
              <td style="color:#e2e8f0;">{inc.service}</td>
              <td style="color:{sev_col};">{inc.severity.upper()}</td>
              <td>{inc.duration_min} min</td>
            </tr>"""
        incident_html = f"""
        <div style="margin-top:32px;">
          <h2 style="color:#94a3b8;font-size:16px;margin-bottom:12px;">
            Incident Log (last {len(incidents)})
          </h2>
          <table style="width:100%;border-collapse:collapse;font-size:13px;">
            <thead>
              <tr style="color:#64748b;text-align:left;border-bottom:1px solid #334155;">
                <th style="padding:6px 12px;">Start</th>
                <th style="padding:6px 12px;">End</th>
                <th style="padding:6px 12px;">Service</th>
                <th style="padding:6px 12px;">Severity</th>
                <th style="padding:6px 12px;">Duration</th>
              </tr>
            </thead>
            <tbody style="color:#94a3b8;">{rows}</tbody>
          </table>
        </div>"""
    else:
        incident_html = '<div style="margin-top:32px;color:#4ade80;">No incidents in the last 24h.</div>'

    # ---- SLA table ----
    sla_rows = ""
    for es in statuses:
        ok = es.uptime_pct >= SLA_TARGET_PCT
        col = "#4ade80" if ok else "#f87171"
        delta = es.uptime_pct - SLA_TARGET_PCT
        delta_str = f"+{delta:.2f}%" if delta >= 0 else f"{delta:.2f}%"
        sla_rows += f"""
            <tr>
              <td style="color:#e2e8f0;">{es.spec.name}</td>
              <td style="color:#94a3b8;">{es.spec.port}</td>
              <td style="color:#94a3b8;">{SLA_TARGET_PCT}%</td>
              <td style="color:{col};">{es.uptime_pct:.2f}%</td>
              <td style="color:{col};">{delta_str}</td>
              <td style="color:{col};">{"PASS" if ok else "FAIL"}</td>
            </tr>"""

    sla_html = f"""
        <div style="margin-top:32px;">
          <h2 style="color:#94a3b8;font-size:16px;margin-bottom:12px;">SLA Compliance</h2>
          <table style="width:100%;border-collapse:collapse;font-size:13px;">
            <thead>
              <tr style="color:#64748b;text-align:left;border-bottom:1px solid #334155;">
                <th style="padding:6px 12px;">Service</th>
                <th style="padding:6px 12px;">Port</th>
                <th style="padding:6px 12px;">Target</th>
                <th style="padding:6px 12px;">Actual</th>
                <th style="padding:6px 12px;">Delta</th>
                <th style="padding:6px 12px;">Status</th>
              </tr>
            </thead>
            <tbody>{sla_rows}</tbody>
          </table>
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta http-equiv="refresh" content="30">
  <title>OCI Robot Cloud — Health Monitor</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: #0f172a;
      color: #cbd5e1;
      min-height: 100vh;
    }}
    a {{ color: #C74634; }}
    table td, table th {{ padding: 6px 12px; border-bottom: 1px solid #1e293b; }}
  </style>
</head>
<body>
  <!-- Header -->
  <div style="background:#1e293b;border-bottom:2px solid #C74634;padding:18px 32px;
              display:flex;align-items:center;justify-content:space-between;">
    <div>
      <span style="color:#C74634;font-weight:800;font-size:20px;letter-spacing:0.5px;">
        OCI Robot Cloud
      </span>
      <span style="color:#94a3b8;font-size:14px;margin-left:12px;">
        Inference Server Health Monitor v{VERSION}
      </span>
    </div>
    <div style="font-size:12px;color:#64748b;">Last updated: {now_str} &nbsp;|&nbsp; auto-refresh 30s</div>
  </div>

  <!-- System status banner -->
  <div style="{banner_style}padding:14px 32px;font-size:18px;font-weight:700;
              text-align:center;letter-spacing:0.5px;">
    {sys_status}
  </div>

  <!-- Main content -->
  <div style="max-width:1400px;margin:32px auto;padding:0 24px;">

    <!-- Endpoint cards 2×6 grid -->
    <h2 style="color:#94a3b8;font-size:16px;margin-bottom:16px;">
      Endpoint Status (12 services)
    </h2>
    <div style="display:grid;grid-template-columns:repeat(2,1fr);gap:16px;">
      {cards_html}
    </div>

    {incident_html}
    {sla_html}

    <div style="margin-top:32px;font-size:11px;color:#334155;text-align:center;">
      Alert rules: latency &gt; {LATENCY_WARN_MS:.0f}ms → warn &nbsp;|&nbsp;
      consecutive failures ≥ {CONSECUTIVE_FAIL_CRITICAL} → critical &nbsp;|&nbsp;
      uptime &lt; {UPTIME_WARN_THRESHOLD}% → warn &nbsp;|&nbsp;
      SLA target {SLA_TARGET_PCT}%
      &nbsp;|&nbsp; Monitor port {MONITOR_PORT}
    </div>
  </div>
</body>
</html>"""
    return html


# ---------------------------------------------------------------------------
# JSON output
# ---------------------------------------------------------------------------

def build_json(statuses: List[EndpointStatus]) -> dict:
    incidents = extract_incidents(statuses)
    return {
        "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
        "overall_status": overall_status(statuses),
        "sla_target_pct": SLA_TARGET_PCT,
        "services": [
            {
                "name": es.spec.name,
                "port": es.spec.port,
                "state": es.state,
                "latency_ms": es.latency_ms,
                "uptime_pct": es.uptime_pct,
                "consecutive_failures": es.consecutive_failures,
                "last_error": es.last_error,
                "extra_metric": {
                    "name": es.spec.extra_metric_name,
                    "value": es.extra_metric_value,
                } if es.spec.extra_metric_name else None,
                "sla_pass": es.uptime_pct >= SLA_TARGET_PCT,
            }
            for es in statuses
        ],
        "incidents": [
            {
                "service": inc.service,
                "start": inc.start_str,
                "end": inc.end_str,
                "severity": inc.severity,
                "duration_min": inc.duration_min,
            }
            for inc in incidents
        ],
    }


# ---------------------------------------------------------------------------
# HTTP server (optional, serves latest HTML on port 8073)
# ---------------------------------------------------------------------------

class _Handler(http.server.BaseHTTPRequestHandler):
    html_content: bytes = b""

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(_Handler.html_content)))
        self.end_headers()
        self.wfile.write(_Handler.html_content)

    def log_message(self, *_):
        pass  # silence default access log


def _start_http_server(statuses: List[EndpointStatus]) -> None:
    _Handler.html_content = build_html(statuses).encode()
    server = http.server.HTTPServer(("0.0.0.0", MONITOR_PORT), _Handler)
    print(f"  {C.CYAN}HTTP dashboard: http://localhost:{MONITOR_PORT}/{C.RESET}")
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="OCI Robot Cloud — Inference Server Health Monitor",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--mock",   action="store_true",
                   help="Use simulated data instead of live probes")
    p.add_argument("--host",   default="localhost",
                   help="Hostname/IP of the inference stack (default: localhost)")
    p.add_argument("--output", default=None,
                   help="Write HTML report to this path (default: stdout summary only)")
    p.add_argument("--json",   default=None,
                   help="Write JSON report to this path")
    p.add_argument("--seed",   type=int, default=42,
                   help="RNG seed for mock data (default: 42)")
    p.add_argument("--serve",  action="store_true",
                   help=f"Start HTTP server on port {MONITOR_PORT} (blocks)")
    p.add_argument("--once",   action="store_true",
                   help="Run a single check then exit (no loop)")
    p.add_argument("--interval", type=int, default=30,
                   help="Seconds between live probe cycles (default: 30)")
    return p.parse_args()


def _run_once(args: argparse.Namespace) -> List[EndpointStatus]:
    if args.mock:
        statuses = build_mock_statuses(seed=args.seed)
    else:
        # Build skeleton statuses then probe live
        statuses = []
        for spec in ENDPOINT_SPECS:
            statuses.append(EndpointStatus(spec=spec))
        probe_live(args.host, statuses)
    return statuses


def main() -> None:
    args = _parse_args()

    # --- single run ---
    statuses = _run_once(args)

    print_console_table(statuses)

    # HTML output
    html_path = args.output
    if html_path:
        html = build_html(statuses)
        Path(html_path).write_text(html, encoding="utf-8")
        print(f"  {C.GREEN}HTML report written: {html_path}{C.RESET}")

    # JSON output
    if args.json:
        data = build_json(statuses)
        Path(args.json).write_text(
            json.dumps(data, indent=2, default=str), encoding="utf-8"
        )
        print(f"  {C.GREEN}JSON report written: {args.json}{C.RESET}")

    # Print JSON summary to stdout regardless
    data = build_json(statuses)
    print(f"\n{C.BOLD}JSON Summary:{C.RESET}")
    print(json.dumps({
        "overall_status": data["overall_status"],
        "generated_at":   data["generated_at"],
        "services_healthy": sum(1 for s in data["services"] if s["state"] == "healthy"),
        "services_total":   len(data["services"]),
        "incidents_last24h": len(data["incidents"]),
    }, indent=2))

    if args.once:
        return

    # Live dashboard + optional HTTP server
    if args.serve or not (args.mock or args.once):
        _start_http_server(statuses)

    if args.mock:
        return  # mock mode done after one pass

    # Continuous loop for live probing
    print(f"\n{C.CYAN}Monitoring {args.host} every {args.interval}s. Ctrl-C to stop.{C.RESET}\n")
    try:
        while True:
            time.sleep(args.interval)
            statuses = _run_once(args)
            print_console_table(statuses)
            if args.serve:
                _Handler.html_content = build_html(statuses).encode()
            if html_path:
                Path(html_path).write_text(build_html(statuses), encoding="utf-8")
    except KeyboardInterrupt:
        print(f"\n{C.GRAY}Monitor stopped.{C.RESET}")


if __name__ == "__main__":
    main()
