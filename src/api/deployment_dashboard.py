#!/usr/bin/env python3
"""
deployment_dashboard.py — Fleet health dashboard for deployed GR00T checkpoints.

Shows real-time status of all robot deployments using OCI-trained checkpoints,
including on-device inference metrics, task success rates, and data collection stats.

Endpoints:
  GET /              → HTML dashboard
  GET /fleet         → JSON fleet status
  GET /robot/{id}    → individual robot status
  POST /robot/{id}/retrain → queue retraining with new data
  GET /metrics/stream → SSE stream of live metrics
  GET /fleet/summary → {total, online, avg_success_rate, total_demos_today, alerts}
  GET /health        → service health

Usage:
    python src/api/deployment_dashboard.py --port 8008
    python src/api/deployment_dashboard.py --mock --port 8008
"""

import argparse
import asyncio
import json
import random
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import AsyncGenerator, List, Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse

# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------

@dataclass
class RobotStatus:
    robot_id: str
    robot_type: str
    location: str
    checkpoint_version: str
    last_seen_utc: str          # ISO-8601 or "offline"
    inference_latency_ms: Optional[float]   # None when offline
    task_success_rate_7d: Optional[float]   # 0-100, None when offline
    demos_collected_today: int
    battery_pct: Optional[int]              # None when offline
    status: str                             # "online" | "offline" | "warning"


# ---------------------------------------------------------------------------
# Mock fleet definition
# ---------------------------------------------------------------------------

def _ts(seconds_ago: int = 0) -> str:
    """Return an ISO-8601 UTC timestamp offset by seconds_ago."""
    ts = time.time() - seconds_ago
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


MOCK_FLEET: List[RobotStatus] = [
    RobotStatus(
        robot_id="robot-001",
        robot_type="Franka Panda",
        location="Lab A",
        checkpoint_version="v5.0",
        last_seen_utc=_ts(45),
        inference_latency_ms=245.0,
        task_success_rate_7d=68.0,
        demos_collected_today=3,
        battery_pct=92,
        status="online",
    ),
    RobotStatus(
        robot_id="robot-002",
        robot_type="UR5e",
        location="Warehouse B",
        checkpoint_version="v3.1",
        last_seen_utc=_ts(120),
        inference_latency_ms=312.0,
        task_success_rate_7d=41.0,
        demos_collected_today=0,
        battery_pct=67,
        status="warning",
    ),
    RobotStatus(
        robot_id="robot-003",
        robot_type="xArm7",
        location="Assembly C",
        checkpoint_version="v4.2",
        last_seen_utc=_ts(30),
        inference_latency_ms=289.0,
        task_success_rate_7d=55.0,
        demos_collected_today=7,
        battery_pct=85,
        status="online",
    ),
    RobotStatus(
        robot_id="robot-004",
        robot_type="Kinova Gen3",
        location="Research D",
        checkpoint_version="v2.0",
        last_seen_utc=_ts(10),
        inference_latency_ms=198.0,
        task_success_rate_7d=82.0,
        demos_collected_today=12,
        battery_pct=78,
        status="online",
    ),
    RobotStatus(
        robot_id="robot-005",
        robot_type="Franka Panda",
        location="Lab A",
        checkpoint_version="v5.0",
        last_seen_utc="offline",
        inference_latency_ms=None,
        task_success_rate_7d=None,
        demos_collected_today=0,
        battery_pct=None,
        status="offline",
    ),
]

# In-memory mutable copy used for SSE random-walk updates
_fleet_state: List[RobotStatus] = [
    RobotStatus(**asdict(r)) for r in MOCK_FLEET
]

# Retraining queue: robot_id → queued_at
_retrain_queue: dict = {}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_robot(robot_id: str) -> Optional[RobotStatus]:
    for r in _fleet_state:
        if r.robot_id == robot_id:
            return r
    return None


def _fleet_alerts(fleet: List[RobotStatus]) -> List[dict]:
    alerts = []
    for r in fleet:
        if r.status == "offline":
            alerts.append({
                "robot_id": r.robot_id,
                "severity": "critical",
                "message": f"{r.robot_id} ({r.robot_type}) has been offline for 2h",
            })
        elif r.task_success_rate_7d is not None and r.task_success_rate_7d < 50.0:
            alerts.append({
                "robot_id": r.robot_id,
                "severity": "warning",
                "message": (
                    f"{r.robot_id} ({r.robot_type}) has low 7-day success rate: "
                    f"{r.task_success_rate_7d:.0f}%"
                ),
            })
    return alerts


# ---------------------------------------------------------------------------
# HTML template
# ---------------------------------------------------------------------------

def _sparkline_svg(values: List[float], width: int = 56, height: int = 20) -> str:
    """Generate a minimal bar-chart SVG sparkline from 7 values (0-100)."""
    n = len(values)
    bar_w = (width - (n - 1) * 2) // n
    bars = []
    for i, v in enumerate(values):
        bar_h = max(2, int(v / 100 * height))
        x = i * (bar_w + 2)
        y = height - bar_h
        color = "#22c55e" if v >= 60 else ("#f59e0b" if v >= 40 else "#ef4444")
        bars.append(
            f'<rect x="{x}" y="{y}" width="{bar_w}" height="{bar_h}" '
            f'fill="{color}" rx="1"/>'
        )
    return (
        f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">'
        + "".join(bars)
        + "</svg>"
    )


def _mock_sparkline_data(current_rate: Optional[float]) -> List[float]:
    """Generate plausible 7-day trend ending at current_rate."""
    if current_rate is None:
        return [0] * 7
    values = []
    v = current_rate
    for _ in range(6):
        v = max(0, min(100, v + random.uniform(-8, 8)))
        values.append(round(v, 1))
    values.append(current_rate)
    return values


def _status_badge(status: str) -> str:
    colors = {
        "online": ("bg-green-100 text-green-800 border-green-300", "● Online"),
        "offline": ("bg-red-100 text-red-800 border-red-300", "● Offline"),
        "warning": ("bg-yellow-100 text-yellow-800 border-yellow-300", "⚠ Warning"),
    }
    cls, label = colors.get(status, ("bg-gray-100 text-gray-800 border-gray-300", status))
    return f'<span class="px-2 py-0.5 text-xs font-semibold rounded-full border {cls}">{label}</span>'


def _latency_bar(latency_ms: Optional[float]) -> str:
    if latency_ms is None:
        return '<div class="text-xs text-gray-400 italic">N/A</div>'
    # Green <250, yellow 250-350, red >350
    pct = min(100, int(latency_ms / 4))
    color = "bg-green-500" if latency_ms < 250 else ("bg-yellow-500" if latency_ms < 350 else "bg-red-500")
    return f"""
      <div class="flex items-center gap-2">
        <div class="w-24 bg-gray-200 rounded h-2">
          <div class="{color} h-2 rounded" style="width:{pct}%"></div>
        </div>
        <span class="text-xs text-gray-700">{latency_ms:.0f} ms</span>
      </div>"""


def _robot_card(r: RobotStatus) -> str:
    spark_data = _mock_sparkline_data(r.task_success_rate_7d)
    sparkline = _sparkline_svg(spark_data)
    badge = _status_badge(r.status)
    latency_bar = _latency_bar(r.inference_latency_ms)
    success_txt = (
        f"{r.task_success_rate_7d:.0f}%" if r.task_success_rate_7d is not None else "N/A"
    )
    battery_txt = f"{r.battery_pct}%" if r.battery_pct is not None else "N/A"
    card_border = (
        "border-red-300 bg-red-50"
        if r.status == "offline"
        else ("border-yellow-300 bg-yellow-50" if r.status == "warning" else "border-gray-200 bg-white")
    )
    return f"""
    <div class="rounded-xl border {card_border} shadow-sm p-4 flex flex-col gap-3" id="card-{r.robot_id}">
      <div class="flex items-center justify-between">
        <div>
          <div class="font-semibold text-gray-900">{r.robot_id}</div>
          <div class="text-xs text-gray-500">{r.robot_type} · {r.location}</div>
        </div>
        {badge}
      </div>

      <div class="grid grid-cols-2 gap-2 text-sm">
        <div>
          <div class="text-xs text-gray-400 uppercase tracking-wide mb-0.5">Checkpoint</div>
          <div class="font-mono text-gray-700">{r.checkpoint_version}</div>
        </div>
        <div>
          <div class="text-xs text-gray-400 uppercase tracking-wide mb-0.5">Battery</div>
          <div class="text-gray-700">{battery_txt}</div>
        </div>
      </div>

      <div>
        <div class="text-xs text-gray-400 uppercase tracking-wide mb-1">Inference Latency</div>
        {latency_bar}
      </div>

      <div class="flex items-center justify-between">
        <div>
          <div class="text-xs text-gray-400 uppercase tracking-wide mb-1">7-Day Success Rate</div>
          <div class="flex items-center gap-2">
            {sparkline}
            <span class="text-sm font-semibold text-gray-700">{success_txt}</span>
          </div>
        </div>
        <div class="text-center">
          <div class="text-xs text-gray-400 uppercase tracking-wide mb-1">Demos Today</div>
          <span class="inline-block bg-blue-100 text-blue-800 text-sm font-bold px-2.5 py-0.5 rounded-full">
            {r.demos_collected_today}
          </span>
        </div>
      </div>

      <div class="text-xs text-gray-400">Last seen: {r.last_seen_utc}</div>

      <form method="POST" action="/robot/{r.robot_id}/retrain">
        <button type="submit"
          class="w-full mt-1 px-3 py-1.5 text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg transition-colors">
          Queue Retraining
        </button>
      </form>
    </div>"""


def _build_html(fleet: List[RobotStatus]) -> str:
    online = [r for r in fleet if r.status != "offline"]
    online_count = len(online)
    total = len(fleet)
    avg_success = (
        sum(r.task_success_rate_7d for r in online if r.task_success_rate_7d is not None)
        / max(1, sum(1 for r in online if r.task_success_rate_7d is not None))
    )
    total_demos = sum(r.demos_collected_today for r in fleet)
    alerts = _fleet_alerts(fleet)

    stat_cards = f"""
    <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
      <div class="bg-white rounded-xl border border-gray-200 shadow-sm p-4 text-center">
        <div class="text-3xl font-bold text-gray-900">{total}</div>
        <div class="text-xs text-gray-500 mt-1 uppercase tracking-wide">Total Robots</div>
      </div>
      <div class="bg-white rounded-xl border border-gray-200 shadow-sm p-4 text-center">
        <div class="text-3xl font-bold text-green-600">{online_count}</div>
        <div class="text-xs text-gray-500 mt-1 uppercase tracking-wide">Online</div>
      </div>
      <div class="bg-white rounded-xl border border-gray-200 shadow-sm p-4 text-center">
        <div class="text-3xl font-bold text-indigo-600">{avg_success:.1f}%</div>
        <div class="text-xs text-gray-500 mt-1 uppercase tracking-wide">Avg Success (7d)</div>
      </div>
      <div class="bg-white rounded-xl border border-gray-200 shadow-sm p-4 text-center">
        <div class="text-3xl font-bold text-blue-600">{total_demos}</div>
        <div class="text-xs text-gray-500 mt-1 uppercase tracking-wide">Demos Today</div>
      </div>
    </div>"""

    alert_html = ""
    if alerts:
        alert_items = "".join(
            f"""<div class="flex items-start gap-2 py-1.5 border-b border-red-100 last:border-0">
                  <span class="text-{'red' if a['severity'] == 'critical' else 'yellow'}-500 mt-0.5">
                    {'🔴' if a['severity'] == 'critical' else '⚠️'}
                  </span>
                  <div>
                    <span class="font-semibold text-gray-800">{a['robot_id']}</span>
                    <span class="text-gray-600 ml-1 text-sm">{a['message']}</span>
                  </div>
                </div>"""
            for a in alerts
        )
        alert_html = f"""
        <div class="bg-red-50 border border-red-200 rounded-xl p-4 mb-8">
          <div class="font-semibold text-red-800 mb-2 flex items-center gap-2">
            <span>Active Alerts</span>
            <span class="bg-red-200 text-red-800 text-xs px-2 py-0.5 rounded-full">{len(alerts)}</span>
          </div>
          {alert_items}
        </div>"""

    robot_cards = "\n".join(_robot_card(r) for r in fleet)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>OCI Robot Cloud — Fleet Dashboard</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }}
    .live-dot {{ animation: pulse 2s infinite; }}
    @keyframes pulse {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: 0.4; }} }}
  </style>
</head>
<body class="bg-gray-50 min-h-screen">

  <header class="bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
    <div class="flex items-center gap-3">
      <div class="w-8 h-8 bg-indigo-600 rounded-lg flex items-center justify-center text-white font-bold text-sm">OCI</div>
      <div>
        <div class="font-semibold text-gray-900">Robot Cloud</div>
        <div class="text-xs text-gray-500">Fleet Deployment Dashboard</div>
      </div>
    </div>
    <div class="flex items-center gap-2 text-xs text-gray-500">
      <span class="live-dot w-2 h-2 bg-green-500 rounded-full inline-block"></span>
      Live · Updated every 3s
    </div>
  </header>

  <main class="max-w-6xl mx-auto px-6 py-8">
    <h1 class="text-xl font-bold text-gray-900 mb-6">Fleet Overview</h1>

    {stat_cards}

    {alert_html}

    <h2 class="text-lg font-semibold text-gray-800 mb-4">Robot Status</h2>
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4" id="fleet-grid">
      {robot_cards}
    </div>
  </main>

  <script>
    // SSE live metrics stream
    const es = new EventSource('/metrics/stream');
    es.onmessage = (e) => {{
      try {{
        const data = JSON.parse(e.data);
        // Minimal live update: patch latency display in card if present
        const card = document.getElementById('card-' + data.robot_id);
        if (card) {{
          // Reload page every 30 events for simplicity in this mock
        }}
      }} catch (_) {{}}
    }};
    // Full page refresh every 30s to pick up fleet-level changes
    setTimeout(() => location.reload(), 30000);
  </script>

</body>
</html>"""


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="OCI Robot Cloud — Fleet Dashboard",
    description="Production health dashboard for deployed GR00T checkpoints.",
    version="1.0.0",
)


@app.get("/", response_class=HTMLResponse, summary="HTML fleet dashboard")
async def dashboard():
    """Render the full fleet health HTML dashboard."""
    return HTMLResponse(content=_build_html(_fleet_state))


@app.get("/fleet", summary="JSON fleet status")
async def fleet():
    """Return full fleet status as JSON array."""
    return [asdict(r) for r in _fleet_state]


@app.get("/fleet/summary", summary="Fleet summary with alerts")
async def fleet_summary():
    """Return high-level fleet KPIs and active alerts."""
    online = [r for r in _fleet_state if r.status != "offline"]
    rates = [r.task_success_rate_7d for r in online if r.task_success_rate_7d is not None]
    avg_success = round(sum(rates) / len(rates), 1) if rates else 0.0
    return {
        "total": len(_fleet_state),
        "online": len(online),
        "avg_success_rate": avg_success,
        "total_demos_today": sum(r.demos_collected_today for r in _fleet_state),
        "alerts": _fleet_alerts(_fleet_state),
    }


@app.get("/robot/{robot_id}", summary="Individual robot status")
async def robot_status(robot_id: str):
    """Return status for a single robot by ID."""
    r = _get_robot(robot_id)
    if r is None:
        raise HTTPException(status_code=404, detail=f"Robot '{robot_id}' not found")
    return asdict(r)


@app.post("/robot/{robot_id}/retrain", summary="Queue retraining for a robot")
async def queue_retrain(robot_id: str):
    """Queue a fine-tuning job for the specified robot using its collected demos."""
    r = _get_robot(robot_id)
    if r is None:
        raise HTTPException(status_code=404, detail=f"Robot '{robot_id}' not found")
    queued_at = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    _retrain_queue[robot_id] = queued_at
    return {
        "robot_id": robot_id,
        "status": "queued",
        "queued_at": queued_at,
        "checkpoint_version": r.checkpoint_version,
        "demos_available": r.demos_collected_today,
        "message": (
            f"Retraining job queued for {robot_id}. "
            "A new checkpoint will be pushed once training completes."
        ),
    }


async def _sse_metrics_generator() -> AsyncGenerator[str, None]:
    """Emit a live-metrics event every 3 seconds with a random-walk update."""
    online_ids = [r.robot_id for r in _fleet_state if r.status == "online"]
    while True:
        await asyncio.sleep(3)
        if not online_ids:
            continue
        robot_id = random.choice(online_ids)
        robot = _get_robot(robot_id)
        if robot is None or robot.inference_latency_ms is None:
            continue

        # Random walk: latency ±10ms, success rate ±1%
        robot.inference_latency_ms = max(
            50.0,
            min(600.0, robot.inference_latency_ms + random.uniform(-10, 10)),
        )
        if robot.task_success_rate_7d is not None:
            robot.task_success_rate_7d = max(
                0.0,
                min(100.0, robot.task_success_rate_7d + random.uniform(-1, 1)),
            )
        robot.last_seen_utc = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        payload = json.dumps(
            {
                "robot_id": robot.robot_id,
                "inference_latency_ms": round(robot.inference_latency_ms, 1),
                "task_success_rate_7d": (
                    round(robot.task_success_rate_7d, 1)
                    if robot.task_success_rate_7d is not None
                    else None
                ),
                "last_seen_utc": robot.last_seen_utc,
            }
        )
        yield f"data: {payload}\n\n"


@app.get("/metrics/stream", summary="SSE live metrics stream")
async def metrics_stream():
    """Server-Sent Events stream of live robot metrics (updates every 3s)."""
    return StreamingResponse(
        _sse_metrics_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/health", summary="Service health check")
async def health():
    """Return service health and fleet heartbeat summary."""
    online = sum(1 for r in _fleet_state if r.status == "online")
    return {
        "status": "ok",
        "timestamp": datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "fleet_online": online,
        "fleet_total": len(_fleet_state),
        "retrain_queue_depth": len(_retrain_queue),
    }


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="OCI Robot Cloud Fleet Dashboard")
    parser.add_argument("--port", type=int, default=8008, help="Port to listen on")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument(
        "--mock",
        action="store_true",
        default=True,
        help="Use mock fleet data (default: True)",
    )
    args = parser.parse_args()

    print(f"OCI Robot Cloud Fleet Dashboard")
    print(f"  http://{args.host}:{args.port}/")
    print(f"  Mock mode: {args.mock}")
    print(f"  Fleet size: {len(_fleet_state)} robots")

    uvicorn.run(app, host=args.host, port=args.port)
