"""OCI Robot Cloud — Partner Webhook Delivery Manager (port 8140)."""
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Optional

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
except ImportError:  # pragma: no cover
    FastAPI = None  # type: ignore
    HTTPException = None  # type: ignore
    HTMLResponse = None  # type: ignore
    JSONResponse = None  # type: ignore
    uvicorn = None  # type: ignore

# ---------------------------------------------------------------------------
# Static data
# ---------------------------------------------------------------------------

ENDPOINTS: list[dict] = [
    {
        "id": "physical_intelligence",
        "url": "https://hooks.physicalintelligence.ai/oci-robot",
        "events": ["training.complete", "eval.result", "drift.alert"],
        "status": "ACTIVE",
        "success_rate": 0.997,
        "avg_latency_ms": 142,
    },
    {
        "id": "apptronik",
        "url": "https://api.apptronik.com/webhooks/oci",
        "events": ["training.complete", "billing.update"],
        "status": "ACTIVE",
        "success_rate": 0.981,
        "avg_latency_ms": 287,
    },
    {
        "id": "1x_technologies",
        "url": "https://webhooks.1x.tech/robot-cloud",
        "events": ["eval.result"],
        "status": "ACTIVE",
        "success_rate": 0.943,
        "avg_latency_ms": 412,
    },
    {
        "id": "agility_robotics",
        "url": "https://api.agilityrobotics.com/oci-hook",
        "events": ["training.complete"],
        "status": "DEGRADED",
        "success_rate": 0.721,
        "avg_latency_ms": 891,
    },
    {
        "id": "figure_ai",
        "url": "https://hooks.figure.ai/oci-test",
        "events": [],
        "status": "INACTIVE",
        "success_rate": None,
        "avg_latency_ms": None,
    },
]

DELIVERIES: list[dict] = [
    {"timestamp": "2026-03-30T01:14:00Z", "partner": "physical_intelligence", "event": "training.complete", "status": "SUCCESS", "latency_ms": 138, "http_code": 200},
    {"timestamp": "2026-03-30T02:30:00Z", "partner": "apptronik", "event": "training.complete", "status": "SUCCESS", "latency_ms": 291, "http_code": 200},
    {"timestamp": "2026-03-30T03:45:00Z", "partner": "1x_technologies", "event": "eval.result", "status": "SUCCESS", "latency_ms": 405, "http_code": 200},
    {"timestamp": "2026-03-30T04:10:00Z", "partner": "agility_robotics", "event": "training.complete", "status": "FAILED", "latency_ms": 5001, "http_code": 504},
    {"timestamp": "2026-03-30T05:00:00Z", "partner": "physical_intelligence", "event": "eval.result", "status": "SUCCESS", "latency_ms": 145, "http_code": 200},
    {"timestamp": "2026-03-30T06:20:00Z", "partner": "apptronik", "event": "billing.update", "status": "SUCCESS", "latency_ms": 278, "http_code": 200},
    {"timestamp": "2026-03-30T07:35:00Z", "partner": "agility_robotics", "event": "training.complete", "status": "RETRYING", "latency_ms": 920, "http_code": 503},
    {"timestamp": "2026-03-30T08:50:00Z", "partner": "physical_intelligence", "event": "drift.alert", "status": "SUCCESS", "latency_ms": 131, "http_code": 200},
    {"timestamp": "2026-03-30T10:05:00Z", "partner": "1x_technologies", "event": "eval.result", "status": "SUCCESS", "latency_ms": 418, "http_code": 200},
    {"timestamp": "2026-03-30T12:00:00Z", "partner": "agility_robotics", "event": "training.complete", "status": "FAILED", "latency_ms": 5001, "http_code": 500},
    {"timestamp": "2026-03-30T14:30:00Z", "partner": "apptronik", "event": "training.complete", "status": "SUCCESS", "latency_ms": 301, "http_code": 200},
    {"timestamp": "2026-03-30T16:45:00Z", "partner": "physical_intelligence", "event": "eval.result", "status": "SUCCESS", "latency_ms": 149, "http_code": 200},
]

RETRY_POLICY: dict = {
    "max_retries": 3,
    "backoff_schedule_seconds": [30, 120, 600],
    "dead_letter_queue": True,
    "dead_letter_after": "all retries exhausted",
}

ALL_EVENT_TYPES = ["training.complete", "eval.result", "drift.alert", "billing.update"]

# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------

def _bar_chart_svg() -> str:
    """680x160 bar chart — success rate per active/degraded partner."""
    active = [ep for ep in ENDPOINTS if ep["status"] in ("ACTIVE", "DEGRADED")]
    W, H = 680, 160
    pad_left, pad_right, pad_top, pad_bot = 160, 20, 20, 30
    chart_w = W - pad_left - pad_right
    chart_h = H - pad_top - pad_bot
    bar_h = chart_h // len(active) - 8
    lines = [
        f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg">',
        f'<rect width="{W}" height="{H}" fill="#1e293b" rx="8"/>',
    ]
    for i, ep in enumerate(active):
        sr = ep["success_rate"] or 0.0
        color = "#22c55e" if sr >= 0.98 else ("#f59e0b" if sr >= 0.85 else "#ef4444")
        y = pad_top + i * (bar_h + 8)
        bw = int(chart_w * sr)
        # label
        lines.append(
            f'<text x="{pad_left - 8}" y="{y + bar_h // 2 + 5}" '
            f'text-anchor="end" fill="#94a3b8" font-size="12" font-family="monospace">{ep["id"][:18]}</text>'
        )
        # background bar
        lines.append(f'<rect x="{pad_left}" y="{y}" width="{chart_w}" height="{bar_h}" fill="#0f172a" rx="3"/>')
        # value bar
        lines.append(f'<rect x="{pad_left}" y="{y}" width="{bw}" height="{bar_h}" fill="{color}" rx="3"/>')
        # pct label
        pct = f"{sr * 100:.1f}%"
        lines.append(
            f'<text x="{pad_left + bw + 4}" y="{y + bar_h // 2 + 5}" '
            f'fill="{color}" font-size="11" font-family="monospace">{pct}</text>'
        )
    # x-axis label
    lines.append(
        f'<text x="{pad_left + chart_w // 2}" y="{H - 4}" '
        f'text-anchor="middle" fill="#64748b" font-size="10" font-family="monospace">Success Rate</text>'
    )
    lines.append("</svg>")
    return "\n".join(lines)


def _timeline_svg() -> str:
    """680x180 scatter plot — delivery timeline (x=hour, y=latency_ms)."""
    W, H = 680, 180
    pad_left, pad_right, pad_top, pad_bot = 50, 20, 15, 30
    chart_w = W - pad_left - pad_right
    chart_h = H - pad_top - pad_bot
    max_latency = 5500
    sla_ms = 500
    color_map = {"SUCCESS": "#38bdf8", "FAILED": "#ef4444", "RETRYING": "#f59e0b"}

    lines = [
        f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg">',
        f'<rect width="{W}" height="{H}" fill="#1e293b" rx="8"/>',
    ]
    # SLA line
    sla_y = pad_top + chart_h - int(chart_h * sla_ms / max_latency)
    lines.append(
        f'<line x1="{pad_left}" y1="{sla_y}" x2="{pad_left + chart_w}" y2="{sla_y}" '
        f'stroke="#f59e0b" stroke-width="1" stroke-dasharray="6,4"/>'
    )
    lines.append(
        f'<text x="{pad_left + 4}" y="{sla_y - 4}" fill="#f59e0b" font-size="10" font-family="monospace">SLA 500ms</text>'
    )
    # axes
    lines.append(f'<line x1="{pad_left}" y1="{pad_top}" x2="{pad_left}" y2="{pad_top + chart_h}" stroke="#334155" stroke-width="1"/>')
    lines.append(f'<line x1="{pad_left}" y1="{pad_top + chart_h}" x2="{pad_left + chart_w}" y2="{pad_top + chart_h}" stroke="#334155" stroke-width="1"/>')
    # x-axis ticks
    for hr in range(0, 25, 4):
        x = pad_left + int(chart_w * hr / 24)
        lines.append(f'<text x="{x}" y="{pad_top + chart_h + 14}" text-anchor="middle" fill="#64748b" font-size="9" font-family="monospace">{hr:02d}h</text>')
    # y-axis ticks
    for ms in [0, 1000, 2000, 3000, 5000]:
        y = pad_top + chart_h - int(chart_h * ms / max_latency)
        lines.append(f'<text x="{pad_left - 4}" y="{y + 4}" text-anchor="end" fill="#64748b" font-size="9" font-family="monospace">{ms}</text>')
    # points
    for d in DELIVERIES:
        try:
            dt = datetime.strptime(d["timestamp"], "%Y-%m-%dT%H:%MZ" if len(d["timestamp"]) == 17 else "%Y-%m-%dT%H:%M:%SZ")
        except Exception:
            dt = datetime(2026, 3, 30, 0, 0)
        hour_frac = dt.hour + dt.minute / 60.0
        cx = pad_left + int(chart_w * hour_frac / 24)
        lat = min(d["latency_ms"], max_latency)
        cy = pad_top + chart_h - int(chart_h * lat / max_latency)
        col = color_map.get(d["status"], "#94a3b8")
        lines.append(f'<circle cx="{cx}" cy="{cy}" r="5" fill="{col}" opacity="0.85"/>')
    # legend
    for i, (label, col) in enumerate([("SUCCESS", "#38bdf8"), ("FAILED", "#ef4444"), ("RETRYING", "#f59e0b")]):
        lx = pad_left + 20 + i * 130
        lines.append(f'<circle cx="{lx}" cy="{pad_top + 8}" r="5" fill="{col}"/>')
        lines.append(f'<text x="{lx + 9}" y="{pad_top + 12}" fill="{col}" font-size="10" font-family="monospace">{label}</text>')
    lines.append("</svg>")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def _dashboard_html() -> str:
    bar_svg = _bar_chart_svg()
    timeline_svg = _timeline_svg()

    # event type breakdown table rows
    ep_rows = ""
    for ep in ENDPOINTS:
        event_cells = "".join(
            f'<td style="text-align:center;color:{"#22c55e" if ev in ep["events"] else "#334155"};font-size:18px">{"●" if ev in ep["events"] else "○"}</td>'
            for ev in ALL_EVENT_TYPES
        )
        sr_disp = f"{ep['success_rate'] * 100:.1f}%" if ep["success_rate"] is not None else "—"
        lat_disp = f"{ep['avg_latency_ms']}ms" if ep["avg_latency_ms"] is not None else "—"
        status_color = {"ACTIVE": "#22c55e", "DEGRADED": "#f59e0b", "INACTIVE": "#64748b"}.get(ep["status"], "#fff")
        ep_rows += f"""
        <tr>
          <td style="font-family:monospace;color:#e2e8f0">{ep['id']}</td>
          <td style="color:{status_color};font-weight:600">{ep['status']}</td>
          {event_cells}
          <td style="color:#38bdf8;font-family:monospace">{sr_disp}</td>
          <td style="color:#94a3b8;font-family:monospace">{lat_disp}</td>
        </tr>"""

    # recent deliveries
    del_rows = ""
    for d in reversed(DELIVERIES):
        col = {"SUCCESS": "#22c55e", "FAILED": "#ef4444", "RETRYING": "#f59e0b"}.get(d["status"], "#fff")
        del_rows += f"""
        <tr>
          <td style="color:#64748b;font-size:12px">{d['timestamp']}</td>
          <td style="color:#e2e8f0;font-family:monospace">{d['partner']}</td>
          <td style="color:#38bdf8">{d['event']}</td>
          <td style="color:{col};font-weight:600">{d['status']}</td>
          <td style="color:#94a3b8">{d['latency_ms']}ms</td>
          <td style="color:#64748b">{d['http_code']}</td>
        </tr>"""

    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>OCI Robot Cloud — Webhook Manager</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; padding: 24px; }}
    h1 {{ color: #C74634; font-size: 22px; margin-bottom: 4px; }}
    .sub {{ color: #64748b; font-size: 13px; margin-bottom: 24px; }}
    .card {{ background: #1e293b; border-radius: 10px; padding: 20px; margin-bottom: 20px; }}
    h2 {{ color: #38bdf8; font-size: 15px; margin-bottom: 14px; text-transform: uppercase; letter-spacing: 1px; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th {{ color: #64748b; font-size: 11px; text-transform: uppercase; letter-spacing: 1px; padding: 6px 10px; text-align: left; border-bottom: 1px solid #334155; }}
    td {{ padding: 8px 10px; border-bottom: 1px solid #1e293b; font-size: 13px; }}
    tr:hover td {{ background: #0f172a22; }}
    .grid2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
    .pill {{ display: inline-block; padding: 2px 10px; border-radius: 12px; font-size: 11px; font-weight: 600; }}
    .retry-box {{ background: #0f172a; border-left: 3px solid #f59e0b; padding: 12px 16px; border-radius: 4px; font-size: 13px; line-height: 1.8; }}
    .key {{ color: #94a3b8; }} .val {{ color: #38bdf8; font-family: monospace; }}
  </style>
</head>
<body>
  <h1>OCI Robot Cloud — Partner Webhook Manager</h1>
  <div class="sub">Port 8140 · 5 registered endpoints · 12 deliveries (last 24h)</div>

  <div class="grid2">
    <div class="card">
      <h2>Delivery Success Rate</h2>
      {bar_svg}
    </div>
    <div class="card">
      <h2>Delivery Timeline</h2>
      {timeline_svg}
    </div>
  </div>

  <div class="card">
    <h2>Partner Endpoints &amp; Event Subscriptions</h2>
    <table>
      <thead><tr>
        <th>Partner</th><th>Status</th>
        {''.join(f'<th style="text-align:center">{e}</th>' for e in ALL_EVENT_TYPES)}
        <th>Success Rate</th><th>Avg Latency</th>
      </tr></thead>
      <tbody>{ep_rows}</tbody>
    </table>
  </div>

  <div class="card">
    <h2>Retry Policy</h2>
    <div class="retry-box">
      <span class="key">Max retries: </span><span class="val">3</span> &nbsp;|
      <span class="key"> Backoff: </span><span class="val">30s → 2m → 10m (exponential)</span> &nbsp;|
      <span class="key"> Dead Letter Queue: </span><span class="val">enabled (after all retries exhausted)</span>
    </div>
  </div>

  <div class="card">
    <h2>Recent Deliveries</h2>
    <table>
      <thead><tr><th>Timestamp</th><th>Partner</th><th>Event</th><th>Status</th><th>Latency</th><th>HTTP</th></tr></thead>
      <tbody>{del_rows}</tbody>
    </table>
  </div>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

if FastAPI is not None:
    app = FastAPI(
        title="OCI Robot Cloud — Webhook Manager",
        description="Partner webhook delivery manager with retry logic and dead-letter queue.",
        version="1.0.0",
    )

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return _dashboard_html()

    @app.get("/endpoints")
    async def list_endpoints():
        return {"endpoints": ENDPOINTS, "total": len(ENDPOINTS)}

    @app.get("/deliveries")
    async def list_deliveries(limit: int = 50):
        return {"deliveries": DELIVERIES[-limit:], "total": len(DELIVERIES)}

    @app.post("/test/{partner_id}")
    async def test_delivery(partner_id: str):
        ep = next((e for e in ENDPOINTS if e["id"] == partner_id), None)
        if ep is None:
            raise HTTPException(status_code=404, detail=f"Partner '{partner_id}' not found")
        if ep["status"] == "INACTIVE":
            raise HTTPException(status_code=400, detail=f"Partner '{partner_id}' is INACTIVE — no events configured")
        return {
            "partner_id": partner_id,
            "url": ep["url"],
            "test_event": "ping",
            "status": "QUEUED",
            "retry_policy": RETRY_POLICY,
            "message": "Test delivery queued. Check /deliveries for result.",
        }


if __name__ == "__main__":
    if uvicorn is None:
        raise RuntimeError("uvicorn not installed")
    uvicorn.run("webhook_manager:app", host="0.0.0.0", port=8140, reload=False)
