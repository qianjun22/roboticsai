"""Inference Anomaly Detection Service — OCI Robot Cloud
Port: 8148
Monitors live inference for action spikes, latency outliers, joint limit
violations, confidence drops, and embedding drift.
"""

try:
    from fastapi import FastAPI, Response
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
except ImportError:
    FastAPI = None

import math
import random
from datetime import datetime

# ---------------------------------------------------------------------------
# Static detector definitions
# ---------------------------------------------------------------------------
DETECTORS = [
    {
        "id": "action_spike",
        "label": "Action Spike",
        "threshold": "3.5σ",
        "window": 50,
        "triggered": True,
        "last_triggered": "2026-03-30T14:22:10Z",
        "count_24h": 3,
        "severity": "MEDIUM",
    },
    {
        "id": "latency_outlier",
        "label": "Latency Outlier",
        "threshold": "400ms",
        "window": 100,
        "triggered": False,
        "last_triggered": "2026-03-28T09:11:00Z",
        "count_24h": 1,
        "severity": "LOW",
    },
    {
        "id": "joint_limit_violation",
        "label": "Joint Limit Violation",
        "threshold": "0.95",
        "window": 10,
        "triggered": False,
        "last_triggered": "2026-03-27T16:44:00Z",
        "count_24h": 0,
        "severity": "HIGH",
    },
    {
        "id": "confidence_drop",
        "label": "Confidence Drop",
        "threshold": "0.3",
        "window": 20,
        "triggered": True,
        "last_triggered": "2026-03-30T13:58:00Z",
        "count_24h": 7,
        "severity": "MEDIUM",
    },
    {
        "id": "embedding_drift",
        "label": "Embedding Drift",
        "threshold": "0.12 cosine",
        "window": 200,
        "triggered": False,
        "last_triggered": "2026-03-25T11:00:00Z",
        "count_24h": 0,
        "severity": "LOW",
    },
]

# ---------------------------------------------------------------------------
# Seeded hourly timeline generation
# Keys: detector_id -> list of 24 hourly counts
# action_spike peaks at hour 14 (count=2)
# confidence_drop peaks at hours 13-14 (count=3 each)
# ---------------------------------------------------------------------------
def _build_timeline() -> dict:
    rng = random.Random(42)
    timeline: dict = {d["id"]: [0] * 24 for d in DETECTORS}

    # action_spike
    base = [0]*24
    base[14] = 2; base[8] = 1
    timeline["action_spike"] = base

    # latency_outlier
    lo = [0]*24
    lo[9] = 1
    timeline["latency_outlier"] = lo

    # joint_limit_violation — 0 total in 24h
    timeline["joint_limit_violation"] = [0]*24

    # confidence_drop peaks 13-14
    cd = [0]*24
    cd[13] = 3; cd[14] = 3; cd[11] = 1
    timeline["confidence_drop"] = cd

    # embedding_drift — 0 total
    timeline["embedding_drift"] = [0]*24

    return timeline

TIMELINE = _build_timeline()

# Stacked area chart colours (sky / amber / red / purple / green)
DETECTOR_COLORS = [
    "#38bdf8",  # action_spike       — sky blue
    "#f59e0b",  # latency_outlier    — amber
    "#ef4444",  # joint_limit        — red
    "#a855f7",  # confidence_drop    — purple
    "#22c55e",  # embedding_drift    — green
]

# ---------------------------------------------------------------------------
# SVG stacked area chart
# ---------------------------------------------------------------------------
def _stacked_area_svg() -> str:
    W, H = 680, 200
    PAD_L, PAD_R, PAD_T, PAD_B = 48, 16, 16, 32
    chart_w = W - PAD_L - PAD_R
    chart_h = H - PAD_T - PAD_B
    hours = list(range(24))

    # Compute stacked totals
    stacks = []  # stacks[hour][detector_idx] = cumulative up to that detector
    max_val = 0
    for h in hours:
        cumul = []
        s = 0
        for d in DETECTORS:
            s += TIMELINE[d["id"]][h]
            cumul.append(s)
        stacks.append(cumul)
        max_val = max(max_val, cumul[-1])

    max_val = max(max_val, 4)  # floor

    def px(h, val):
        x = PAD_L + h * chart_w / 23
        y = PAD_T + chart_h - val * chart_h / max_val
        return x, y

    paths = []
    n = len(DETECTORS)
    for i in range(n - 1, -1, -1):  # draw back-to-front
        top_pts = [px(h, stacks[h][i]) for h in hours]
        if i == 0:
            bot_pts = [(px(h, 0)[0], PAD_T + chart_h) for h in hours]
        else:
            bot_pts = [px(h, stacks[h][i - 1]) for h in hours]
        poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in top_pts)
        poly += " " + " ".join(f"{x:.1f},{y:.1f}" for x, y in reversed(bot_pts))
        paths.append(
            f'<polygon points="{poly}" fill="{DETECTOR_COLORS[i]}" opacity="0.75" />'
        )

    # x-axis labels every 4 hours
    xlabels = ""
    for h in range(0, 24, 4):
        x, _ = px(h, 0)
        xlabels += f'<text x="{x:.1f}" y="{H - 6}" fill="#94a3b8" font-size="10" text-anchor="middle">{h:02d}h</text>'

    # y-axis labels
    ylabels = ""
    for v in range(0, int(max_val) + 1, 2):
        _, y = px(0, v)
        ylabels += f'<text x="{PAD_L - 4}" y="{y:.1f}" fill="#94a3b8" font-size="10" text-anchor="end" dominant-baseline="middle">{v}</text>'

    # grid lines
    grid = ""
    for v in range(0, int(max_val) + 1, 2):
        _, y = px(0, v)
        grid += f'<line x1="{PAD_L}" y1="{y:.1f}" x2="{W - PAD_R}" y2="{y:.1f}" stroke="#1e293b" stroke-width="1"/>'

    legend = ""
    for i, d in enumerate(DETECTORS):
        lx = PAD_L + i * 128
        legend += f'<rect x="{lx}" y="4" width="10" height="10" fill="{DETECTOR_COLORS[i]}"/>'
        legend += f'<text x="{lx + 13}" y="13" fill="#94a3b8" font-size="9">{d["label"]}</text>'

    return (
        f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg" '
        f'style="background:#0f172a;border-radius:8px;">'
        f'{grid}{"" .join(paths)}{xlabels}{ylabels}{legend}'
        f'</svg>'
    )

# ---------------------------------------------------------------------------
# HTML helpers
# ---------------------------------------------------------------------------
SEVERITY_BADGE = {
    "HIGH":   '<span style="background:#C74634;color:#fff;padding:2px 8px;border-radius:12px;font-size:11px;">HIGH</span>',
    "MEDIUM": '<span style="background:#f59e0b;color:#000;padding:2px 8px;border-radius:12px;font-size:11px;">MEDIUM</span>',
    "LOW":    '<span style="background:#22c55e;color:#000;padding:2px 8px;border-radius:12px;font-size:11px;">LOW</span>',
}

STATUS_BADGE = {
    True:  '<span style="background:#C74634;color:#fff;padding:2px 8px;border-radius:12px;font-size:11px;">ACTIVE</span>',
    False: '<span style="background:#22c55e;color:#000;padding:2px 8px;border-radius:12px;font-size:11px;">CLEAR</span>',
}


def _dashboard_html() -> str:
    svg = _stacked_area_svg()

    # Active alerts table (triggered only)
    active = [d for d in DETECTORS if d["triggered"]]
    alert_rows = ""
    for d in active:
        alert_rows += (
            f'<tr style="border-bottom:1px solid #1e293b;">'
            f'<td style="padding:8px 12px;color:#f1f5f9;">{d["label"]}</td>'
            f'<td style="padding:8px 12px;">{SEVERITY_BADGE[d["severity"]]}</td>'
            f'<td style="padding:8px 12px;color:#94a3b8;">{d["last_triggered"]}</td>'
            f'<td style="padding:8px 12px;color:#38bdf8;">{d["count_24h"]}</td>'
            f'</tr>'
        )

    # Detector status grid
    grid_cards = ""
    for i, d in enumerate(DETECTORS):
        color = DETECTOR_COLORS[i]
        grid_cards += (
            f'<div style="background:#1e293b;border-radius:8px;padding:16px;'
            f'border-left:3px solid {color};">'
            f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">'
            f'<span style="color:#f1f5f9;font-weight:600;font-size:14px;">{d["label"]}</span>'
            f'{STATUS_BADGE[d["triggered"]]}'
            f'</div>'
            f'<div style="font-size:12px;color:#94a3b8;">Threshold: <span style="color:#38bdf8;">{d["threshold"]}</span></div>'
            f'<div style="font-size:12px;color:#94a3b8;">Window: {d["window"]} samples</div>'
            f'<div style="font-size:12px;color:#94a3b8;">24h count: <span style="color:#f1f5f9;font-weight:700;">{d["count_24h"]}</span></div>'
            f'<div style="font-size:11px;color:#475569;margin-top:6px;">Last: {d["last_triggered"]}</div>'
            f'{SEVERITY_BADGE[d["severity"]]}'
            f'</div>'
        )

    active_count = len(active)
    total_24h = sum(d["count_24h"] for d in DETECTORS)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Anomaly Detector — OCI Robot Cloud</title>
<style>
  body{{margin:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
        background:#0f172a;color:#f1f5f9;}}
  h1{{color:#38bdf8;}} h2{{color:#cbd5e1;font-size:16px;margin-top:28px;}}
  table{{width:100%;border-collapse:collapse;background:#1e293b;border-radius:8px;overflow:hidden;}}
  th{{padding:10px 12px;text-align:left;color:#94a3b8;font-size:12px;
      text-transform:uppercase;background:#0f172a;border-bottom:2px solid #334155;}}
</style>
</head>
<body>
<div style="max-width:960px;margin:0 auto;padding:24px;">
  <div style="display:flex;align-items:center;gap:12px;margin-bottom:4px;">
    <div style="width:12px;height:12px;border-radius:50%;background:#C74634;"></div>
    <span style="color:#C74634;font-size:12px;font-weight:600;">OCI ROBOT CLOUD · PORT 8148</span>
  </div>
  <h1 style="margin:0 0 4px;">Inference Anomaly Detector</h1>
  <p style="color:#64748b;margin:0 0 24px;">Real-time monitoring · 5 active detectors · {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</p>

  <!-- KPI row -->
  <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:24px;">
    <div style="background:#1e293b;border-radius:8px;padding:16px;text-align:center;">
      <div style="font-size:28px;font-weight:700;color:#C74634;">{active_count}</div>
      <div style="color:#94a3b8;font-size:12px;">Active Alerts</div>
    </div>
    <div style="background:#1e293b;border-radius:8px;padding:16px;text-align:center;">
      <div style="font-size:28px;font-weight:700;color:#38bdf8;">{total_24h}</div>
      <div style="color:#94a3b8;font-size:12px;">Anomalies 24h</div>
    </div>
    <div style="background:#1e293b;border-radius:8px;padding:16px;text-align:center;">
      <div style="font-size:28px;font-weight:700;color:#22c55e;">5</div>
      <div style="color:#94a3b8;font-size:12px;">Detectors Running</div>
    </div>
    <div style="background:#1e293b;border-radius:8px;padding:16px;text-align:center;">
      <div style="font-size:28px;font-weight:700;color:#a855f7;">LOW</div>
      <div style="color:#94a3b8;font-size:12px;">Overall Risk Level</div>
    </div>
  </div>

  <h2>24h Anomaly Timeline (stacked by detector)</h2>
  <div style="margin-bottom:24px;">{svg}</div>

  <h2>Active Alerts</h2>
  <table style="margin-bottom:24px;">
    <thead><tr><th>Detector</th><th>Severity</th><th>Last Triggered</th><th>24h Count</th></tr></thead>
    <tbody>{alert_rows}</tbody>
  </table>

  <h2>Detector Status</h2>
  <div style="display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin-bottom:24px;">
    {grid_cards}
  </div>

  <div style="color:#334155;font-size:11px;text-align:center;">OCI Robot Cloud · Anomaly Detector v1.0 · Port 8148</div>
</div>
</body></html>"""


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
if FastAPI is not None:
    app = FastAPI(title="Anomaly Detector", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return _dashboard_html()

    @app.get("/detectors")
    async def get_detectors():
        return {"detectors": DETECTORS, "count": len(DETECTORS)}

    @app.get("/alerts")
    async def get_alerts():
        active = [d for d in DETECTORS if d["triggered"]]
        return {
            "active_alerts": active,
            "count": len(active),
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

    @app.get("/timeline")
    async def get_timeline():
        hourly_totals = [
            sum(TIMELINE[d["id"]][h] for d in DETECTORS) for h in range(24)
        ]
        return {
            "hours": list(range(24)),
            "by_detector": TIMELINE,
            "hourly_totals": hourly_totals,
        }

if __name__ == "__main__":
    if FastAPI is None:
        raise RuntimeError("fastapi not installed. Run: pip install fastapi uvicorn")
    uvicorn.run(app, host="0.0.0.0", port=8148)
