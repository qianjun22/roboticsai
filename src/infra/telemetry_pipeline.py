"""
telemetry_pipeline.py — Real-time telemetry streaming pipeline for OCI Robot Cloud.

Collects robot operational data (joint states, success/fail, latency, battery, errors)
and streams to OCI Object Storage and analytics dashboard.

Port: 8067
Usage:
    python telemetry_pipeline.py --mock --port 8067 --output /tmp/telemetry_pipeline.html --seed 42
"""

import argparse
import dataclasses
import json
import math
import random
import time
import uuid
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class TelemetryEvent:
    event_id: str
    robot_id: str
    partner: str
    event_type: str          # heartbeat / success / failure / error / warning / battery_low
    timestamp: float         # unix epoch
    joint_angles: Optional[List[float]]   # 7 floats, only for success/failure
    action_latency_ms: Optional[float]
    battery_pct: Optional[float]
    error_code: Optional[str]
    metadata: Dict


@dataclasses.dataclass
class TelemetryStream:
    stream_id: str
    partner: str
    robot_id: str
    events_per_min: float
    last_event_at: float
    total_events: int
    error_count: int
    status: str              # active / stale / disconnected


# ---------------------------------------------------------------------------
# Data generation
# ---------------------------------------------------------------------------

ROBOTS = [
    ("agility_robotics", "digit-001"),
    ("agility_robotics", "digit-002"),
    ("figure_ai",        "figure-001"),
    ("figure_ai",        "figure-002"),
]

EVENT_TYPES = ["heartbeat", "success", "failure", "error", "warning", "battery_low"]
EVENT_WEIGHTS = [0.70, 0.12, 0.08, 0.05, 0.03, 0.02]

ERROR_CODES = ["E_JOINT_LIMIT", "E_MOTOR_OVERHEAT", "E_COMMS_TIMEOUT",
               "E_SENSOR_FAIL", "E_ESTOP", "E_PLAN_FAIL"]


def _random_joint_angles(rng: random.Random) -> List[float]:
    return [round(rng.uniform(-math.pi, math.pi), 4) for _ in range(7)]


def generate_telemetry_events(n: int = 500, seed: int = 42) -> List[TelemetryEvent]:
    rng = random.Random(seed)
    events: List[TelemetryEvent] = []
    now = time.time()
    start_ts = now - 3600  # spread over last hour

    # Track per-robot battery state (starts high, degrades)
    battery_state: Dict[str, float] = {rid: rng.uniform(85.0, 100.0) for _, rid in ROBOTS}

    for i in range(n):
        partner, robot_id = ROBOTS[i % len(ROBOTS)]
        ts = start_ts + (i / n) * 3600 + rng.uniform(-5, 5)
        etype = rng.choices(EVENT_TYPES, weights=EVENT_WEIGHTS, k=1)[0]

        # Degrade battery over time per robot
        battery_state[robot_id] = max(
            0.0, battery_state[robot_id] - rng.uniform(0.0, 0.25)
        )
        battery_pct = round(battery_state[robot_id], 1)

        # Latency: normal range with occasional spikes
        if rng.random() < 0.06:
            latency = round(rng.uniform(500, 900), 1)
        else:
            latency = round(rng.uniform(150, 350), 1)

        joint_angles = (
            _random_joint_angles(rng) if etype in ("success", "failure") else None
        )
        error_code = rng.choice(ERROR_CODES) if etype == "error" else None

        meta: Dict = {"sequence": i, "fw_version": "2.1.4"}
        if etype == "battery_low":
            meta["alert"] = "battery_critical"

        events.append(TelemetryEvent(
            event_id=str(uuid.UUID(int=rng.getrandbits(128))),
            robot_id=robot_id,
            partner=partner,
            event_type=etype,
            timestamp=ts,
            joint_angles=joint_angles,
            action_latency_ms=latency if etype != "heartbeat" else None,
            battery_pct=battery_pct,
            error_code=error_code,
            metadata=meta,
        ))

    events.sort(key=lambda e: e.timestamp)
    return events


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------

def compute_stream_stats(events: List[TelemetryEvent]) -> Dict[str, Dict]:
    """Per-robot aggregated stats."""
    stats: Dict[str, Dict] = {}
    for e in events:
        s = stats.setdefault(e.robot_id, {
            "partner": e.partner,
            "total": 0, "errors": 0,
            "latencies": [], "last_seen": 0.0,
            "batteries": [],
        })
        s["total"] += 1
        if e.event_type == "error":
            s["errors"] += 1
        if e.action_latency_ms is not None:
            s["latencies"].append(e.action_latency_ms)
        if e.timestamp > s["last_seen"]:
            s["last_seen"] = e.timestamp
        if e.battery_pct is not None:
            s["batteries"].append(e.battery_pct)

    result = {}
    for rid, s in stats.items():
        lats = s["latencies"]
        bats = s["batteries"]
        result[rid] = {
            "partner": s["partner"],
            "total_events": s["total"],
            "error_rate": round(s["errors"] / s["total"] * 100, 2) if s["total"] else 0,
            "avg_latency_ms": round(sum(lats) / len(lats), 1) if lats else 0,
            "last_seen": s["last_seen"],
            "battery_trend": round(bats[-1] - bats[0], 1) if len(bats) >= 2 else 0,
            "battery_current": round(bats[-1], 1) if bats else None,
        }
    return result


def detect_anomalies(events: List[TelemetryEvent]) -> List[Dict]:
    """Return list of anomaly dicts."""
    anomalies: List[Dict] = []

    # Latency spikes
    for e in events:
        if e.action_latency_ms is not None and e.action_latency_ms > 500:
            anomalies.append({
                "robot_id": e.robot_id,
                "type": "Latency Spike",
                "severity": "warning",
                "timestamp": e.timestamp,
                "detail": f"{e.action_latency_ms:.0f} ms",
                "recommendation": "Check network and motor controller load",
            })

    # Error bursts: >3 errors in any sliding window of 10 events
    by_robot: Dict[str, List[TelemetryEvent]] = {}
    for e in events:
        by_robot.setdefault(e.robot_id, []).append(e)

    for rid, evs in by_robot.items():
        for i in range(len(evs) - 9):
            window = evs[i:i + 10]
            err_count = sum(1 for x in window if x.event_type == "error")
            if err_count > 3:
                anomalies.append({
                    "robot_id": rid,
                    "type": "Error Burst",
                    "severity": "critical",
                    "timestamp": window[-1].timestamp,
                    "detail": f"{err_count} errors in 10 events",
                    "recommendation": "Inspect robot hardware; consider taking offline",
                })
                break  # one anomaly per robot

    # Battery critical
    for e in events:
        if e.battery_pct is not None and e.battery_pct < 15:
            anomalies.append({
                "robot_id": e.robot_id,
                "type": "Low Battery",
                "severity": "critical",
                "timestamp": e.timestamp,
                "detail": f"{e.battery_pct:.1f}%",
                "recommendation": "Return robot to charging station immediately",
            })

    # Consecutive failures > 5
    for rid, evs in by_robot.items():
        streak = 0
        streak_start_ts = 0.0
        for e in evs:
            if e.event_type == "failure":
                if streak == 0:
                    streak_start_ts = e.timestamp
                streak += 1
                if streak > 5:
                    anomalies.append({
                        "robot_id": rid,
                        "type": "Consecutive Failures",
                        "severity": "critical",
                        "timestamp": e.timestamp,
                        "detail": f"{streak} consecutive failures",
                        "recommendation": "Review task policy; trigger retraining pipeline",
                    })
                    streak = 0  # reset to avoid duplicate per run
            else:
                streak = 0

    # Deduplicate by (robot_id, type) keeping only latest
    seen = {}
    deduped = []
    for a in sorted(anomalies, key=lambda x: x["timestamp"], reverse=True):
        key = (a["robot_id"], a["type"])
        if key not in seen:
            seen[key] = True
            deduped.append(a)
    return deduped


# ---------------------------------------------------------------------------
# HTML Dashboard
# ---------------------------------------------------------------------------

def _fmt_ts(ts: float) -> str:
    return datetime.utcfromtimestamp(ts).strftime("%H:%M:%S UTC")


def _severity_color(sev: str) -> str:
    return {"critical": "#ef4444", "warning": "#f59e0b", "info": "#38bdf8"}.get(sev, "#94a3b8")


def _status_badge(status: str) -> str:
    colors = {"active": "#22c55e", "stale": "#f59e0b", "disconnected": "#ef4444"}
    c = colors.get(status, "#94a3b8")
    return f'<span style="background:{c};color:#fff;padding:2px 8px;border-radius:4px;font-size:11px">{status}</span>'


def build_html(events: List[TelemetryEvent]) -> str:
    stats = compute_stream_stats(events)
    anomalies = detect_anomalies(events)
    now = time.time()

    # KPIs
    total_events = len(events)
    active_streams = sum(
        1 for s in stats.values() if (now - s["last_seen"]) < 120
    )
    lat_vals = [e.action_latency_ms for e in events if e.action_latency_ms is not None]
    avg_latency = round(sum(lat_vals) / len(lat_vals), 1) if lat_vals else 0
    error_rate = round(
        sum(1 for e in events if e.event_type == "error") / total_events * 100, 2
    ) if total_events else 0
    anomaly_count = len(anomalies)

    # Event type distribution
    type_counts = {t: 0 for t in EVENT_TYPES}
    for e in events:
        type_counts[e.event_type] = type_counts.get(e.event_type, 0) + 1

    bar_colors = {
        "heartbeat": "#38bdf8",
        "success": "#22c55e",
        "failure": "#f87171",
        "error": "#ef4444",
        "warning": "#f59e0b",
        "battery_low": "#a855f7",
    }
    max_count = max(type_counts.values()) or 1
    bar_rows = ""
    bar_height = 36
    for i, (etype, cnt) in enumerate(type_counts.items()):
        bar_w = int((cnt / max_count) * 380)
        y = i * (bar_height + 6) + 10
        color = bar_colors.get(etype, "#94a3b8")
        pct = round(cnt / total_events * 100, 1) if total_events else 0
        bar_rows += (
            f'<rect x="100" y="{y}" width="{bar_w}" height="{bar_height}" '
            f'fill="{color}" rx="4"/>'
            f'<text x="95" y="{y + bar_height // 2 + 5}" text-anchor="end" '
            f'font-size="12" fill="#94a3b8">{etype}</text>'
            f'<text x="{100 + bar_w + 6}" y="{y + bar_height // 2 + 5}" '
            f'font-size="11" fill="#cbd5e1">{cnt} ({pct}%)</text>'
        )
    dist_svg_h = len(EVENT_TYPES) * (bar_height + 6) + 20

    # Latency timeline (last 50 non-heartbeat events with latency)
    lat_events = [e for e in events if e.action_latency_ms is not None][-50:]
    tl_w, tl_h = 560, 120
    tl_pad_x, tl_pad_y = 40, 15
    tl_inner_w = tl_w - tl_pad_x * 2
    tl_inner_h = tl_h - tl_pad_y * 2

    tl_points = ""
    tl_dots = ""
    if lat_events:
        lat_max = max(e.action_latency_ms for e in lat_events)
        lat_min = min(e.action_latency_ms for e in lat_events)
        lat_range = (lat_max - lat_min) or 1
        coords = []
        for j, e in enumerate(lat_events):
            px = tl_pad_x + (j / max(len(lat_events) - 1, 1)) * tl_inner_w
            py = tl_pad_y + tl_inner_h - ((e.action_latency_ms - lat_min) / lat_range) * tl_inner_h
            coords.append((px, py, e.action_latency_ms))
        tl_points = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y, _ in coords)
        for x, y, lat in coords:
            color = "#ef4444" if lat > 500 else "#38bdf8"
            tl_dots += f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="{color}"/>'

    # Anomaly table rows
    anomaly_rows = ""
    for a in anomalies[:20]:
        sc = _severity_color(a["severity"])
        badge = f'<span style="background:{sc};color:#fff;padding:1px 6px;border-radius:3px;font-size:11px">{a["severity"]}</span>'
        anomaly_rows += (
            f"<tr>"
            f"<td>{a['robot_id']}</td>"
            f"<td>{a['type']}</td>"
            f"<td>{badge}</td>"
            f"<td>{_fmt_ts(a['timestamp'])}</td>"
            f"<td style='color:#94a3b8;font-size:12px'>{a['recommendation']}</td>"
            f"</tr>"
        )

    # Stream status rows
    stream_rows = ""
    for rid, s in stats.items():
        age = now - s["last_seen"]
        status = "active" if age < 120 else ("stale" if age < 600 else "disconnected")
        bat = f"{s['battery_current']}%" if s["battery_current"] is not None else "—"
        stream_rows += (
            f"<tr>"
            f"<td>{rid}</td>"
            f"<td>{s['partner']}</td>"
            f"<td>{s['avg_latency_ms']}</td>"
            f"<td>{_fmt_ts(s['last_seen'])}</td>"
            f"<td>{s['error_rate']}%</td>"
            f"<td>{bat}</td>"
            f"<td>{_status_badge(status)}</td>"
            f"</tr>"
        )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>OCI Robot Cloud — Telemetry Pipeline</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{background:#1e293b;color:#e2e8f0;font-family:'Segoe UI',Arial,sans-serif;font-size:14px;padding:24px}}
  h1{{color:#C74634;font-size:22px;margin-bottom:4px}}
  .sub{{color:#64748b;font-size:12px;margin-bottom:24px}}
  .kpi-grid{{display:grid;grid-template-columns:repeat(5,1fr);gap:16px;margin-bottom:28px}}
  .kpi{{background:#0f172a;border:1px solid #334155;border-radius:8px;padding:16px;text-align:center}}
  .kpi .val{{font-size:28px;font-weight:700;color:#f1f5f9}}
  .kpi .lbl{{font-size:11px;color:#64748b;text-transform:uppercase;letter-spacing:.05em;margin-top:4px}}
  .section{{margin-bottom:28px}}
  .section-title{{color:#C74634;font-size:15px;font-weight:600;margin-bottom:12px;border-bottom:1px solid #334155;padding-bottom:6px}}
  .charts{{display:grid;grid-template-columns:1fr 1fr;gap:20px}}
  .chart-box{{background:#0f172a;border:1px solid #334155;border-radius:8px;padding:16px}}
  .chart-box h3{{color:#94a3b8;font-size:12px;text-transform:uppercase;letter-spacing:.05em;margin-bottom:12px}}
  table{{width:100%;border-collapse:collapse;background:#0f172a;border-radius:8px;overflow:hidden}}
  th{{background:#1e3a5f;color:#94a3b8;font-size:11px;text-transform:uppercase;letter-spacing:.05em;padding:10px 12px;text-align:left}}
  td{{padding:9px 12px;border-bottom:1px solid #1e293b;color:#cbd5e1;font-size:13px}}
  tr:last-child td{{border-bottom:none}}
  tr:hover td{{background:#1e3a5f22}}
  .footer{{color:#475569;font-size:11px;text-align:center;margin-top:32px}}
</style>
</head>
<body>
<h1>OCI Robot Cloud — Telemetry Pipeline</h1>
<div class="sub">Port 8067 &nbsp;·&nbsp; Generated {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')} &nbsp;·&nbsp; {total_events} events ingested</div>

<div class="kpi-grid">
  <div class="kpi"><div class="val">{total_events:,}</div><div class="lbl">Total Events</div></div>
  <div class="kpi"><div class="val">{active_streams}</div><div class="lbl">Active Streams</div></div>
  <div class="kpi"><div class="val">{avg_latency} ms</div><div class="lbl">Avg Latency</div></div>
  <div class="kpi"><div class="val">{error_rate}%</div><div class="lbl">Error Rate</div></div>
  <div class="kpi"><div class="val">{anomaly_count}</div><div class="lbl">Anomalies Detected</div></div>
</div>

<div class="section">
  <div class="section-title">Event Distribution &amp; Latency Timeline</div>
  <div class="charts">
    <div class="chart-box">
      <h3>Event Type Distribution</h3>
      <svg width="500" height="{dist_svg_h}" xmlns="http://www.w3.org/2000/svg">
        {bar_rows}
      </svg>
    </div>
    <div class="chart-box">
      <h3>Latency Timeline — Last 50 Events (red = spike &gt;500ms)</h3>
      <svg width="{tl_w}" height="{tl_h + 20}" xmlns="http://www.w3.org/2000/svg">
        <line x1="{tl_pad_x}" y1="{tl_pad_y}" x2="{tl_pad_x}" y2="{tl_pad_y + tl_inner_h}" stroke="#334155" stroke-width="1"/>
        <line x1="{tl_pad_x}" y1="{tl_pad_y + tl_inner_h}" x2="{tl_pad_x + tl_inner_w}" y2="{tl_pad_y + tl_inner_h}" stroke="#334155" stroke-width="1"/>
        <path d="{tl_points}" fill="none" stroke="#38bdf8" stroke-width="1.5"/>
        {tl_dots}
        <text x="{tl_pad_x - 4}" y="{tl_pad_y + 4}" text-anchor="end" font-size="10" fill="#64748b">high</text>
        <text x="{tl_pad_x - 4}" y="{tl_pad_y + tl_inner_h}" text-anchor="end" font-size="10" fill="#64748b">low</text>
      </svg>
    </div>
  </div>
</div>

<div class="section">
  <div class="section-title">Anomalies Detected ({anomaly_count})</div>
  <table>
    <thead><tr><th>Robot</th><th>Type</th><th>Severity</th><th>Timestamp</th><th>Recommendation</th></tr></thead>
    <tbody>{anomaly_rows if anomaly_rows else '<tr><td colspan="5" style="text-align:center;color:#64748b">No anomalies detected</td></tr>'}</tbody>
  </table>
</div>

<div class="section">
  <div class="section-title">Stream Status</div>
  <table>
    <thead><tr><th>Robot ID</th><th>Partner</th><th>Avg Latency (ms)</th><th>Last Seen</th><th>Error Rate</th><th>Battery</th><th>Status</th></tr></thead>
    <tbody>{stream_rows}</tbody>
  </table>
</div>

<div class="footer">OCI Robot Cloud Telemetry Pipeline · Oracle Confidential · {datetime.utcnow().year}</div>
</body>
</html>"""
    return html


# ---------------------------------------------------------------------------
# API JSON payload
# ---------------------------------------------------------------------------

def build_api_payload(events: List[TelemetryEvent]) -> Dict:
    stats = compute_stream_stats(events)
    anomalies = detect_anomalies(events)
    lat_vals = [e.action_latency_ms for e in events if e.action_latency_ms is not None]
    return {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "total_events": len(events),
        "avg_latency_ms": round(sum(lat_vals) / len(lat_vals), 1) if lat_vals else 0,
        "error_rate_pct": round(
            sum(1 for e in events if e.event_type == "error") / len(events) * 100, 2
        ) if events else 0,
        "anomaly_count": len(anomalies),
        "stream_stats": stats,
        "anomalies": anomalies,
        "recent_events": [
            {
                "event_id": e.event_id,
                "robot_id": e.robot_id,
                "partner": e.partner,
                "event_type": e.event_type,
                "timestamp": e.timestamp,
                "action_latency_ms": e.action_latency_ms,
                "battery_pct": e.battery_pct,
                "error_code": e.error_code,
            }
            for e in events[-50:]
        ],
    }


# ---------------------------------------------------------------------------
# HTTP Server
# ---------------------------------------------------------------------------

_EVENTS: List[TelemetryEvent] = []


class TelemetryHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # suppress default access log
        pass

    def do_GET(self):
        if self.path in ("/", "/dashboard"):
            body = build_html(_EVENTS).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/api/stream":
            payload = build_api_payload(_EVENTS)
            body = json.dumps(payload, indent=2, default=str).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not found")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="OCI Robot Cloud Telemetry Pipeline")
    parser.add_argument("--mock", action="store_true", help="Generate mock telemetry data")
    parser.add_argument("--port", type=int, default=8067, help="HTTP server port")
    parser.add_argument("--output", default="", help="Write HTML report to file path")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for mock data")
    parser.add_argument("--events", type=int, default=500, help="Number of mock events")
    args = parser.parse_args()

    global _EVENTS
    if args.mock:
        print(f"[telemetry] Generating {args.events} mock events (seed={args.seed}) ...")
        _EVENTS = generate_telemetry_events(n=args.events, seed=args.seed)
    else:
        print("[telemetry] No data source configured; use --mock for demo data.")

    stats = compute_stream_stats(_EVENTS)
    anomalies = detect_anomalies(_EVENTS)
    lat_vals = [e.action_latency_ms for e in _EVENTS if e.action_latency_ms is not None]
    avg_lat = round(sum(lat_vals) / len(lat_vals), 1) if lat_vals else 0
    print(f"[telemetry] Events: {len(_EVENTS)} | Streams: {len(stats)} | "
          f"Avg latency: {avg_lat} ms | Anomalies: {len(anomalies)}")

    if args.output:
        html = build_html(_EVENTS)
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"[telemetry] HTML report written to {args.output}")

    print(f"[telemetry] Starting HTTP server on port {args.port} ...")
    print(f"[telemetry]   Dashboard : http://localhost:{args.port}/")
    print(f"[telemetry]   API       : http://localhost:{args.port}/api/stream")
    server = HTTPServer(("0.0.0.0", args.port), TelemetryHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[telemetry] Shutting down.")
        server.server_close()


if __name__ == "__main__":
    main()
