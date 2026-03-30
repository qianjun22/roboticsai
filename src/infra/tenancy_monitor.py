"""OCI Tenancy Resource Monitor — FastAPI service on port 8190.

Tracks GPU/compute quotas, utilization, and 30-day growth trends
for the OCI Robot Cloud tenancy.
"""

from __future__ import annotations

import math
from datetime import date, timedelta
from typing import Any

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
except ImportError as e:
    raise SystemExit(f"Missing dependency: {e}. Run: pip install fastapi uvicorn") from e

app = FastAPI(title="OCI Tenancy Monitor", version="1.0.0")

# ---------------------------------------------------------------------------
# Static quota data
# ---------------------------------------------------------------------------

QUOTAS: list[dict[str, Any]] = [
    {
        "resource": "gpu_a100_80gb",
        "label": "A100 80GB GPUs",
        "unit": "GPUs",
        "limit": 4,
        "used": 2,
        "reserved": 1,
        "available": 1,
        "region": "us-ashburn-1",
    },
    {
        "resource": "gpu_a100_40gb",
        "label": "A100 40GB GPUs",
        "unit": "GPUs",
        "limit": 4,
        "used": 2,
        "reserved": 0,
        "available": 2,
        "region": "multi (phx+fra)",
    },
    {
        "resource": "object_storage_tb",
        "label": "Object Storage",
        "unit": "TB",
        "limit": 50,
        "used": 0.344,
        "reserved": 0,
        "available": 49.656,
        "region": "us-ashburn-1",
    },
    {
        "resource": "vcpu",
        "label": "vCPUs",
        "unit": "vCPUs",
        "limit": 128,
        "used": 48,
        "reserved": 16,
        "available": 64,
        "region": "us-ashburn-1",
    },
    {
        "resource": "memory_gb",
        "label": "Memory",
        "unit": "GB",
        "limit": 2048,
        "used": 384,
        "reserved": 256,
        "available": 1408,
        "region": "us-ashburn-1",
    },
    {
        "resource": "network_bandwidth_gbps",
        "label": "Network Bandwidth",
        "unit": "Gbps",
        "limit": 25,
        "used": 0.28,
        "reserved": 0,
        "available": 24.72,
        "region": "us-ashburn-1",
    },
]

# ---------------------------------------------------------------------------
# 30-day trend generation (pure Python, no numpy)
# ---------------------------------------------------------------------------

def _generate_trends() -> dict[str, list[dict[str, Any]]]:
    """Generate 30 days of daily utilization data (deterministic seed)."""
    today = date.today()
    days = [today - timedelta(days=29 - i) for i in range(30)]

    # GPU A100 80GB: grew from 1 to 2 around day-14 (mid-Feb canary-1 added)
    gpu_80gb: list[float] = []
    for i in range(30):
        val = 1.0 if i < 14 else 2.0
        # small jitter using deterministic math
        jitter = 0.05 * math.sin(i * 1.3)
        gpu_80gb.append(round(val + jitter, 3))

    # GPU A100 40GB: stable at 2
    gpu_40gb: list[float] = [round(2.0 + 0.03 * math.cos(i * 0.7), 3) for i in range(30)]

    # Object storage: 0.18 -> 0.34 TB linear growth
    storage: list[float] = [round(0.18 + (0.344 - 0.18) * i / 29, 4) for i in range(30)]

    # vCPUs: stable around 48
    vcpu: list[float] = [round(48 + 2 * math.sin(i * 0.5), 1) for i in range(30)]

    # Memory GB: stable around 384 with slight growth
    memory: list[float] = [round(370 + 14 * (i / 29), 1) for i in range(30)]

    # Network: stable ~0.28 Gbps
    network: list[float] = [round(0.25 + 0.03 * abs(math.sin(i * 0.8)), 3) for i in range(30)]

    return {
        "gpu_a100_80gb": [{"date": str(days[i]), "value": gpu_80gb[i]} for i in range(30)],
        "gpu_a100_40gb": [{"date": str(days[i]), "value": gpu_40gb[i]} for i in range(30)],
        "object_storage_tb": [{"date": str(days[i]), "value": storage[i]} for i in range(30)],
        "vcpu": [{"date": str(days[i]), "value": vcpu[i]} for i in range(30)],
        "memory_gb": [{"date": str(days[i]), "value": memory[i]} for i in range(30)],
        "network_bandwidth_gbps": [{"date": str(days[i]), "value": network[i]} for i in range(30)],
    }


TRENDS = _generate_trends()

# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------

_BAR_COLOR_GREEN = "#22c55e"
_BAR_COLOR_AMBER = "#f59e0b"
_BAR_COLOR_RED = "#ef4444"
_BAR_COLOR_RESERVED = "#6366f1"
_SKY = "#38bdf8"
_RED = "#C74634"
_BG = "#0f172a"
_PANEL = "#1e293b"
_TEXT = "#e2e8f0"
_MUTED = "#64748b"


def _bar_color(pct: float) -> str:
    if pct >= 0.8:
        return _BAR_COLOR_RED
    if pct >= 0.5:
        return _BAR_COLOR_AMBER
    return _BAR_COLOR_GREEN


def _gauge_svg(width: int = 680, height: int = 280) -> str:
    """6 horizontal gauge bars — used+reserved stacked, limit line, labels."""
    pad_left, pad_right, pad_top, pad_bottom = 170, 40, 30, 20
    bar_area_w = width - pad_left - pad_right
    n = len(QUOTAS)
    slot_h = (height - pad_top - pad_bottom) / n
    bar_h = min(slot_h * 0.45, 22)

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'style="background:{_PANEL};border-radius:8px;">',
        f'<text x="{pad_left + bar_area_w/2}" y="18" text-anchor="middle" '
        f'fill="{_TEXT}" font-size="12" font-family="monospace">Resource Quotas &amp; Utilization</text>',
    ]

    for idx, q in enumerate(QUOTAS):
        cy = pad_top + (idx + 0.5) * slot_h
        bar_y = cy - bar_h / 2

        used_pct = q["used"] / q["limit"]
        res_pct = q["reserved"] / q["limit"]
        total_pct = used_pct + res_pct
        color = _bar_color(total_pct)

        used_w = bar_area_w * used_pct
        res_w = bar_area_w * res_pct

        # background track
        lines.append(
            f'<rect x="{pad_left}" y="{bar_y:.1f}" width="{bar_area_w}" height="{bar_h:.1f}" '
            f'fill="#334155" rx="3"/>'
        )
        # used bar
        lines.append(
            f'<rect x="{pad_left}" y="{bar_y:.1f}" width="{used_w:.1f}" height="{bar_h:.1f}" '
            f'fill="{color}" rx="3"/>'
        )
        # reserved bar (stacked)
        if res_w > 0:
            lines.append(
                f'<rect x="{pad_left + used_w:.1f}" y="{bar_y:.1f}" width="{res_w:.1f}" '
                f'height="{bar_h:.1f}" fill="{_BAR_COLOR_RESERVED}" opacity="0.7" rx="2"/>'
            )
        # limit line
        lx = pad_left + bar_area_w
        lines.append(
            f'<line x1="{lx:.1f}" y1="{bar_y:.1f}" x2="{lx:.1f}" '
            f'y2="{bar_y + bar_h:.1f}" stroke="{_TEXT}" stroke-width="2"/>'
        )
        # resource label (left)
        lines.append(
            f'<text x="{pad_left - 8}" y="{cy + 4:.1f}" text-anchor="end" '
            f'fill="{_TEXT}" font-size="11" font-family="monospace">{q["label"]}</text>'
        )
        # used/limit label (right)
        pct_str = f"{total_pct*100:.0f}%"
        val_str = f"{q['used']}/{q['limit']} {q['unit']}"
        lines.append(
            f'<text x="{lx + 6}" y="{cy + 4:.1f}" fill="{color}" '
            f'font-size="10" font-family="monospace">{pct_str}</text>'
        )
        lines.append(
            f'<text x="{pad_left + used_w/2:.1f}" y="{cy + 4:.1f}" text-anchor="middle" '
            f'fill="{_BG}" font-size="9" font-family="monospace" font-weight="bold">{val_str}</text>'
        )

    # legend
    lx0 = pad_left
    ly = height - 10
    for color, label in [(_BAR_COLOR_GREEN, "<50%"), (_BAR_COLOR_AMBER, "50-80%"),
                          (_BAR_COLOR_RED, ">80%"), (_BAR_COLOR_RESERVED, "Reserved")]:
        lines.append(f'<rect x="{lx0}" y="{ly - 8}" width="12" height="8" fill="{color}" rx="1"/>')
        lines.append(f'<text x="{lx0 + 15}" y="{ly}" fill="{_MUTED}" font-size="9" font-family="monospace">{label}</text>')
        lx0 += 80

    lines.append("</svg>")
    return "\n".join(lines)


def _trend_svg(width: int = 680, height: int = 200) -> str:
    """Dual-line trend: A100_80GB count + storage TB over 30 days."""
    pad_left, pad_right, pad_top, pad_bottom = 55, 60, 30, 35
    plot_w = width - pad_left - pad_right
    plot_h = height - pad_top - pad_bottom

    gpu_vals = [d["value"] for d in TRENDS["gpu_a100_80gb"]]
    stor_vals = [d["value"] for d in TRENDS["object_storage_tb"]]
    dates = [d["date"] for d in TRENDS["gpu_a100_80gb"]]
    n = len(gpu_vals)

    gpu_min, gpu_max = 0.0, 4.0  # fix to quota limit for clarity
    stor_min, stor_max = 0.0, 1.0

    def gx(i: int) -> float:
        return pad_left + i * plot_w / (n - 1)

    def gy_gpu(v: float) -> float:
        return pad_top + plot_h - (v - gpu_min) / (gpu_max - gpu_min) * plot_h

    def gy_stor(v: float) -> float:
        return pad_top + plot_h - (v - stor_min) / (stor_max - stor_min) * plot_h

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'style="background:{_PANEL};border-radius:8px;">',
        f'<text x="{width/2}" y="18" text-anchor="middle" fill="{_TEXT}" '
        f'font-size="12" font-family="monospace">30-Day Growth Trend</text>',
    ]

    # grid lines
    for tick in [0.25, 0.5, 0.75, 1.0]:
        gy = pad_top + plot_h * (1 - tick)
        lines.append(
            f'<line x1="{pad_left}" y1="{gy:.1f}" x2="{pad_left + plot_w}" '
            f'y2="{gy:.1f}" stroke="#334155" stroke-width="1"/>'
        )

    # GPU line
    pts_gpu = " ".join(f"{gx(i):.1f},{gy_gpu(v):.1f}" for i, v in enumerate(gpu_vals))
    lines.append(f'<polyline points="{pts_gpu}" fill="none" stroke="{_SKY}" stroke-width="2"/>')

    # Storage line
    pts_stor = " ".join(f"{gx(i):.1f},{gy_stor(v):.1f}" for i, v in enumerate(stor_vals))
    lines.append(f'<polyline points="{pts_stor}" fill="none" stroke="{_RED}" stroke-width="2" stroke-dasharray="5,3"/>')

    # x-axis labels (first, mid, last)
    for idx in [0, 14, 29]:
        lines.append(
            f'<text x="{gx(idx):.1f}" y="{pad_top + plot_h + 18}" text-anchor="middle" '
            f'fill="{_MUTED}" font-size="9" font-family="monospace">{dates[idx][5:]}</text>'
        )

    # left y-axis label (GPU)
    for tick_v, label in [(1, "1"), (2, "2"), (3, "3"), (4, "4")]:
        lines.append(
            f'<text x="{pad_left - 6}" y="{gy_gpu(tick_v) + 4:.1f}" text-anchor="end" '
            f'fill="{_SKY}" font-size="9" font-family="monospace">{label}</text>'
        )
    lines.append(
        f'<text x="{pad_left - 40}" y="{pad_top + plot_h/2}" text-anchor="middle" '
        f'fill="{_SKY}" font-size="9" font-family="monospace" '
        f'transform="rotate(-90,{pad_left - 40},{pad_top + plot_h/2})">A100 80GB</text>'
    )

    # right y-axis label (Storage)
    for tick_v, label in [(0.25, ".25TB"), (0.5, ".5TB"), (0.75, ".75TB")]:
        rx = pad_left + plot_w + 6
        lines.append(
            f'<text x="{rx}" y="{gy_stor(tick_v) + 4:.1f}" fill="{_RED}" '
            f'font-size="9" font-family="monospace">{label}</text>'
        )

    # legend
    lines.append(f'<rect x="{pad_left}" y="{height-14}" width="14" height="4" fill="{_SKY}"/>')
    lines.append(f'<text x="{pad_left+18}" y="{height-10}" fill="{_SKY}" font-size="9" font-family="monospace">A100 80GB count</text>')
    lines.append(f'<rect x="{pad_left+140}" y="{height-14}" width="14" height="4" fill="{_RED}"/>')
    lines.append(f'<text x="{pad_left+158}" y="{height-10}" fill="{_RED}" font-size="9" font-family="monospace">Object Storage TB</text>')

    lines.append("</svg>")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/quotas", response_class=JSONResponse)
async def get_quotas() -> list[dict[str, Any]]:
    """Return current quota data for all 6 resources."""
    enriched = []
    for q in QUOTAS:
        used_pct = round(q["used"] / q["limit"] * 100, 1)
        total_pct = round((q["used"] + q["reserved"]) / q["limit"] * 100, 1)
        enriched.append({**q, "used_pct": used_pct, "total_committed_pct": total_pct})
    return enriched


@app.get("/trends", response_class=JSONResponse)
async def get_trends() -> dict[str, Any]:
    """Return 30-day daily utilization trend for all resources."""
    return TRENDS


@app.get("/alerts", response_class=JSONResponse)
async def get_alerts() -> list[dict[str, Any]]:
    """Return resources near quota limits (>50% committed)."""
    alerts = []
    for q in QUOTAS:
        total_pct = (q["used"] + q["reserved"]) / q["limit"]
        if total_pct >= 0.5:
            severity = "high" if total_pct >= 0.8 else "medium"
            alerts.append({
                "resource": q["resource"],
                "label": q["label"],
                "total_committed_pct": round(total_pct * 100, 1),
                "severity": severity,
                "recommendation": (
                    "Consider requesting limit increase before AI World"
                    if q["resource"] == "gpu_a100_80gb"
                    else "Monitor closely"
                ),
            })
    return sorted(alerts, key=lambda x: x["total_committed_pct"], reverse=True)


@app.get("/", response_class=HTMLResponse)
async def dashboard() -> HTMLResponse:
    gauge_svg = _gauge_svg()
    trend_svg = _trend_svg()
    alerts = await get_alerts()

    alert_rows = ""
    for a in alerts:
        color = "#ef4444" if a["severity"] == "high" else "#f59e0b"
        alert_rows += f"""
        <tr>
          <td style="color:{_TEXT};padding:6px 12px;font-family:monospace;font-size:13px;">{a['label']}</td>
          <td style="color:{color};padding:6px 12px;font-family:monospace;font-size:13px;">{a['total_committed_pct']}%</td>
          <td style="color:{color};padding:6px 12px;font-family:monospace;font-size:11px;">{a['severity'].upper()}</td>
          <td style="color:#94a3b8;padding:6px 12px;font-family:monospace;font-size:11px;">{a['recommendation']}</td>
        </tr>"""

    quota_cards = ""
    for q in QUOTAS:
        used_pct = q["used"] / q["limit"]
        total_pct = (q["used"] + q["reserved"]) / q["limit"]
        color = _bar_color(total_pct)
        quota_cards += f"""
        <div style="background:#1e293b;border-radius:8px;padding:14px;border:1px solid #334155;">
          <div style="color:#94a3b8;font-size:11px;font-family:monospace;margin-bottom:4px;">{q['region']}</div>
          <div style="color:{_TEXT};font-size:14px;font-family:monospace;font-weight:bold;">{q['label']}</div>
          <div style="margin:8px 0;">
            <div style="background:#334155;border-radius:4px;height:8px;">
              <div style="background:{color};width:{used_pct*100:.1f}%;height:8px;border-radius:4px;"></div>
            </div>
          </div>
          <div style="display:flex;justify-content:space-between;">
            <span style="color:{color};font-size:12px;font-family:monospace;">{q['used']}/{q['limit']} {q['unit']}</span>
            <span style="color:#64748b;font-size:11px;font-family:monospace;">{used_pct*100:.0f}% used</span>
          </div>
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>OCI Tenancy Monitor — Robot Cloud</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: {_BG}; color: {_TEXT}; font-family: monospace; padding: 24px; }}
    h1 {{ color: {_RED}; font-size: 22px; margin-bottom: 4px; }}
    h2 {{ color: {_SKY}; font-size: 14px; margin: 20px 0 10px; }}
    .subtitle {{ color: #64748b; font-size: 12px; margin-bottom: 24px; }}
    .grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-bottom: 24px; }}
    .svg-block {{ margin-bottom: 24px; }}
    table {{ width: 100%; border-collapse: collapse; background: #1e293b; border-radius: 8px; overflow: hidden; }}
    th {{ background: #0f172a; color: #64748b; padding: 8px 12px; text-align: left; font-size: 11px; font-family: monospace; }}
    tr:hover {{ background: #263548; }}
    .badge {{ display:inline-block;padding:2px 8px;border-radius:4px;font-size:10px; }}
  </style>
</head>
<body>
  <h1>OCI Tenancy Monitor</h1>
  <div class="subtitle">OCI Robot Cloud · us-ashburn-1 (primary) · Last updated: {date.today()}</div>

  <h2>Resource Quotas</h2>
  <div class="grid">{quota_cards}</div>

  <h2>Utilization Gauges</h2>
  <div class="svg-block">{gauge_svg}</div>

  <h2>30-Day Growth Trend</h2>
  <div class="svg-block">{trend_svg}</div>

  <h2>Active Alerts</h2>
  <table>
    <thead><tr><th>Resource</th><th>Committed %</th><th>Severity</th><th>Recommendation</th></tr></thead>
    <tbody>{alert_rows}</tbody>
  </table>

  <div style="margin-top:24px;color:#334155;font-size:10px;font-family:monospace;">
    API: /quotas · /trends · /alerts · port 8190
  </div>
</body>
</html>"""
    return HTMLResponse(content=html)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8190)
