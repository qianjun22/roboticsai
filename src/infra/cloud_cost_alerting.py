"""Cloud Cost Alerting — FastAPI service on port 8273.

Proactive cloud cost alerting with budget thresholds and anomaly detection.
Tracks daily spend, rolling averages, and alerts on statistical anomalies.
"""

from __future__ import annotations

import math
import random
import json
from datetime import datetime, timedelta
from typing import Any

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    _USE_FASTAPI = True
except ImportError:
    _USE_FASTAPI = False

# ---------------------------------------------------------------------------
# Mock data — March 2026
# ---------------------------------------------------------------------------

random.seed(42)

MONTH_BUDGET = 500.0
MONTH_ACTUAL = 224.0   # month-to-date (day 1-30 partial)
MONTH_DAYS = 30
CURRENT_DAY = 27        # day of month so far
PROJECTED_EOD = 342.0   # projected end-of-month
ALERT_THRESHOLD_AMBER = 0.70   # 70%
ALERT_THRESHOLD_RED = 0.90     # 90%

# 30-day daily spend
_DAILY_BASE = 7.2  # baseline $/day
_daily_spend: list[float] = []
for day in range(1, MONTH_DAYS + 1):
    noise = random.gauss(0, 1.1)
    spend = max(0.5, _DAILY_BASE + noise)
    _daily_spend.append(round(spend, 2))

# Inject anomalies
_daily_spend[11] = 28.0   # day 12: DAgger run10 launch
_daily_spend[20] = 31.0   # day 21: SDG v4 batch
_daily_spend[24] = 22.5   # day 25: eval marathon (moderate)

# Rolling average (5-day window)
def _rolling_avg(data: list[float], window: int = 5) -> list[float]:
    avgs = []
    for i in range(len(data)):
        start = max(0, i - window + 1)
        avgs.append(sum(data[start:i + 1]) / (i - start + 1))
    return avgs

_rolling = _rolling_avg(_daily_spend)

# Global mean and std (excluding anomaly days for baseline)
_normal_days = [v for i, v in enumerate(_daily_spend) if i not in {11, 20, 24}]
_mu = sum(_normal_days) / len(_normal_days)
_sigma = math.sqrt(sum((x - _mu) ** 2 for x in _normal_days) / len(_normal_days))
UCL_COST = _mu + 2 * _sigma
LCL_COST = max(0.0, _mu - 2 * _sigma)

ANOMALY_DAYS = {
    12: {"label": "DAgger run10", "desc": "DAgger run10 launch — expected", "severity": "info"},
    21: {"label": "SDG v4 batch", "desc": "SDG v4 batch — alert sent", "severity": "warning"},
    25: {"label": "Eval marathon", "desc": "Eval marathon — alert sent", "severity": "warning"},
}

KEY_METRICS = {
    "budget_utilization": f"{100 * MONTH_ACTUAL / MONTH_BUDGET:.1f}%",
    "month_actual": f"${MONTH_ACTUAL:.2f}",
    "month_budget": f"${MONTH_BUDGET:.2f}",
    "projected_eom": f"${PROJECTED_EOD:.2f}",
    "anomaly_days": str(len(ANOMALY_DAYS)),
    "anomaly_detection_rate": "100%",
    "false_positive_rate": "0%",
    "projected_april": "$287 (+35% MoM)",
    "status": "ON TRACK",
}

# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------

def _build_gauge_svg() -> str:
    """Semicircle budget burn rate gauge."""
    W, H = 400, 240
    cx, cy = 200, 180
    R_outer, R_inner = 130, 80
    utilization = MONTH_ACTUAL / MONTH_BUDGET  # 0.448
    projected_util = PROJECTED_EOD / MONTH_BUDGET  # 0.684

    def arc_path(start_deg: float, end_deg: float, r_out: float, r_in: float) -> str:
        """SVG arc path for a gauge segment (clockwise from left)."""
        def polar(deg: float, r: float):
            rad = math.radians(deg)
            return cx + r * math.cos(rad), cy - r * math.sin(rad)

        x1o, y1o = polar(start_deg, r_out)
        x2o, y2o = polar(end_deg, r_out)
        x1i, y1i = polar(start_deg, r_in)
        x2i, y2i = polar(end_deg, r_in)
        large = 1 if (end_deg - start_deg) > 180 else 0
        # outer arc (counter-clockwise = going right to left in SVG coords)
        return (
            f"M {x1o:.2f} {y1o:.2f} "
            f"A {r_out} {r_out} 0 {large} 0 {x2o:.2f} {y2o:.2f} "
            f"L {x2i:.2f} {y2i:.2f} "
            f"A {r_in} {r_in} 0 {large} 1 {x1i:.2f} {y1i:.2f} Z"
        )

    # Map 0-100% utilization to 180°→0° (left to right)
    def util_to_deg(u: float) -> float:
        return 180.0 - u * 180.0

    lines: list[str] = []
    lines.append(f'<rect width="{W}" height="{H}" fill="#0f172a" rx="8"/>')

    # Zone segments: green 0-70%, amber 70-90%, red 90-100%
    zones = [
        (0.00, 0.70, "#166534", "#22c55e"),
        (0.70, 0.90, "#78350f", "#f59e0b"),
        (0.90, 1.00, "#7f1d1d", "#C74634"),
    ]
    for u_start, u_end, bg_col, _fg in zones:
        d = arc_path(util_to_deg(u_end), util_to_deg(u_start), R_outer, R_inner)
        lines.append(f'<path d="{d}" fill="{bg_col}" opacity="0.5"/>')

    # Actual spend arc (bright)
    d_actual = arc_path(util_to_deg(utilization), 180, R_outer, R_inner)
    lines.append(f'<path d="{d_actual}" fill="#38bdf8" opacity="0.9"/>')

    # Projected line marker
    proj_deg = util_to_deg(projected_util)
    rad_p = math.radians(proj_deg)
    px_o = cx + R_outer * math.cos(rad_p)
    py_o = cy - R_outer * math.sin(rad_p)
    px_i = cx + R_inner * math.cos(rad_p)
    py_i = cy - R_inner * math.sin(rad_p)
    lines.append(
        f'<line x1="{px_i:.1f}" y1="{py_i:.1f}" x2="{px_o:.1f}" y2="{py_o:.1f}" '
        f'stroke="#f59e0b" stroke-width="3" stroke-dasharray="4,2"/>'
    )

    # Center text
    lines.append(
        f'<text x="{cx}" y="{cy - 20}" fill="#38bdf8" font-size="32" '
        f'font-weight="800" text-anchor="middle">{100 * utilization:.1f}%</text>'
    )
    lines.append(
        f'<text x="{cx}" y="{cy + 2}" fill="#94a3b8" font-size="13" '
        f'text-anchor="middle">Budget Used</text>'
    )
    lines.append(
        f'<text x="{cx}" y="{cy + 20}" fill="#e2e8f0" font-size="12" '
        f'text-anchor="middle">${MONTH_ACTUAL:.0f} of ${MONTH_BUDGET:.0f}</text>'
    )

    # Scale labels
    for pct, label in [(0, "0%"), (50, "50%"), (70, "70%"), (90, "90%"), (100, "100%")]:
        deg = util_to_deg(pct / 100)
        rad = math.radians(deg)
        lx = cx + (R_outer + 16) * math.cos(rad)
        ly = cy - (R_outer + 16) * math.sin(rad)
        lines.append(
            f'<text x="{lx:.1f}" y="{ly:.1f}" fill="#64748b" font-size="9" '
            f'text-anchor="middle" dominant-baseline="middle">{label}</text>'
        )

    # Legend
    legend_items = [
        ("#38bdf8", f"Actual MTD (${MONTH_ACTUAL:.0f})"),
        ("#f59e0b", f"Projected EOM (${PROJECTED_EOD:.0f})"),
        ("#22c55e", "Zone: On Track (<70%)"),
        ("#C74634", "Zone: Over Budget (>90%)"),
    ]
    lx_base = 30
    for i, (col, label) in enumerate(legend_items):
        lx2 = lx_base + (i % 2) * 190
        ly2 = 200 + (i // 2) * 16
        lines.append(f'<rect x="{lx2}" y="{ly2 - 5}" width="10" height="10" fill="{col}" rx="2"/>')
        lines.append(
            f'<text x="{lx2 + 14}" y="{ly2 + 1}" fill="#94a3b8" font-size="9" '
            f'dominant-baseline="middle">{label}</text>'
        )

    # Title
    lines.append(
        f'<text x="{W // 2}" y="15" fill="#f1f5f9" font-size="12" '
        f'font-weight="700" text-anchor="middle">March 2026 Budget Burn Rate</text>'
    )

    inner = "\n  ".join(lines)
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">\n  {inner}\n</svg>'


def _build_anomaly_chart_svg() -> str:
    """30-day daily spend with rolling average and ±2σ bands."""
    W, H = 700, 280
    pad_l, pad_r, pad_t, pad_b = 55, 20, 20, 45
    chart_w = W - pad_l - pad_r
    chart_h = H - pad_t - pad_b

    spend_max = max(_daily_spend) * 1.15
    spend_min = 0.0
    n = len(_daily_spend)

    def sx(i: int) -> float:
        return pad_l + i / (n - 1) * chart_w

    def sy(v: float) -> float:
        return pad_t + (1 - (v - spend_min) / (spend_max - spend_min)) * chart_h

    lines: list[str] = []
    lines.append(f'<rect width="{W}" height="{H}" fill="#0f172a" rx="8"/>')

    # ±2σ band
    ucl_y = sy(UCL_COST)
    lcl_y = sy(LCL_COST)
    lines.append(
        f'<rect x="{pad_l}" y="{ucl_y:.1f}" '
        f'width="{chart_w}" height="{lcl_y - ucl_y:.1f}" '
        f'fill="#1e3a5f" opacity="0.35"/>'
    )
    lines.append(
        f'<line x1="{pad_l}" y1="{ucl_y:.1f}" x2="{pad_l + chart_w}" y2="{ucl_y:.1f}" '
        f'stroke="#f59e0b" stroke-width="1" stroke-dasharray="4,3"/>'
    )
    lines.append(
        f'<text x="{pad_l - 5}" y="{ucl_y:.1f}" fill="#f59e0b" font-size="9" '
        f'text-anchor="end" dominant-baseline="middle">+2σ</text>'
    )
    lines.append(
        f'<line x1="{pad_l}" y1="{lcl_y:.1f}" x2="{pad_l + chart_w}" y2="{lcl_y:.1f}" '
        f'stroke="#f59e0b" stroke-width="1" stroke-dasharray="4,3"/>'
    )
    lines.append(
        f'<text x="{pad_l - 5}" y="{lcl_y:.1f}" fill="#f59e0b" font-size="9" '
        f'text-anchor="end" dominant-baseline="middle">-2σ</text>'
    )

    # Mean line
    mu_y = sy(_mu)
    lines.append(
        f'<line x1="{pad_l}" y1="{mu_y:.1f}" x2="{pad_l + chart_w}" y2="{mu_y:.1f}" '
        f'stroke="#475569" stroke-width="1" stroke-dasharray="2,2"/>'
    )
    lines.append(
        f'<text x="{pad_l - 5}" y="{mu_y:.1f}" fill="#475569" font-size="9" '
        f'text-anchor="end" dominant-baseline="middle">μ</text>'
    )

    # Daily bars
    bar_w = max(2, chart_w / n - 2)
    for i, v in enumerate(_daily_spend):
        day = i + 1
        bx = sx(i) - bar_w / 2
        by = sy(v)
        bh = pad_t + chart_h - by
        is_anomaly = day in ANOMALY_DAYS
        col = "#C74634" if is_anomaly else "#334155"
        lines.append(
            f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bar_w:.1f}" height="{bh:.1f}" '
            f'fill="{col}" rx="1"/>'
        )

    # Rolling average line
    pts = " ".join(f"{sx(i):.1f},{sy(v):.1f}" for i, v in enumerate(_rolling))
    lines.append(
        f'<polyline points="{pts}" fill="none" stroke="#38bdf8" stroke-width="2"/>'
    )

    # Anomaly markers + labels
    for day, info in ANOMALY_DAYS.items():
        i = day - 1
        v = _daily_spend[i]
        cx2 = sx(i)
        cy2 = sy(v)
        lines.append(f'<circle cx="{cx2:.1f}" cy="{cy2:.1f}" r="5" fill="#C74634" stroke="#fff" stroke-width="1"/>')
        # Label above
        label = info["label"]
        lines.append(
            f'<text x="{cx2:.1f}" y="{cy2 - 10:.1f}" fill="#fca5a5" font-size="8" '
            f'text-anchor="middle">{label}</text>'
        )
        lines.append(
            f'<text x="{cx2:.1f}" y="{cy2 - 2:.1f}" fill="#fca5a5" font-size="8" '
            f'text-anchor="middle">${v:.0f}</text>'
        )

    # X-axis ticks (every 5 days)
    for day in range(1, n + 1, 5):
        i = day - 1
        x = sx(i)
        lines.append(
            f'<text x="{x:.1f}" y="{pad_t + chart_h + 14}" fill="#94a3b8" '
            f'font-size="9" text-anchor="middle">d{day}</text>'
        )

    # Y-axis ticks
    for tick in [5, 10, 15, 20, 25, 30]:
        if tick > spend_max:
            break
        ty = sy(tick)
        lines.append(
            f'<text x="{pad_l - 6}" y="{ty:.1f}" fill="#94a3b8" font-size="9" '
            f'text-anchor="end" dominant-baseline="middle">${tick}</text>'
        )
        lines.append(
            f'<line x1="{pad_l}" y1="{ty:.1f}" x2="{pad_l + chart_w}" y2="{ty:.1f}" '
            f'stroke="#1e293b" stroke-width="1"/>'
        )

    # Axes
    lines.append(
        f'<line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t + chart_h}" stroke="#475569"/>'
    )
    lines.append(
        f'<line x1="{pad_l}" y1="{pad_t + chart_h}" x2="{pad_l + chart_w}" y2="{pad_t + chart_h}" stroke="#475569"/>'
    )

    # Axis labels
    lines.append(
        f'<text x="{W // 2}" y="{H - 5}" fill="#94a3b8" font-size="10" text-anchor="middle">Day of Month (March 2026)</text>'
    )
    lines.append(
        f'<text x="12" y="{H // 2}" fill="#94a3b8" font-size="10" '
        f'text-anchor="middle" transform="rotate(-90,12,{H // 2})">Daily Spend ($)</text>'
    )

    # Legend
    lx = pad_l + 10
    ly = pad_t + 10
    for col, label in [
        ("#334155", "Daily spend"),
        ("#38bdf8", "5-day rolling avg"),
        ("#C74634", "Anomaly detected"),
        ("#f59e0b", "±2σ threshold"),
    ]:
        lines.append(f'<rect x="{lx}" y="{ly - 5}" width="10" height="10" fill="{col}" rx="2"/>')
        lines.append(
            f'<text x="{lx + 13}" y="{ly + 1}" fill="#cbd5e1" font-size="9" '
            f'dominant-baseline="middle">{label}</text>'
        )
        lx += 140

    inner = "\n  ".join(lines)
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">\n  {inner}\n</svg>'


# ---------------------------------------------------------------------------
# HTML page
# ---------------------------------------------------------------------------

def _render_html() -> str:
    gauge_svg = _build_gauge_svg()
    anomaly_svg = _build_anomaly_chart_svg()
    metrics_json = json.dumps(KEY_METRICS, indent=2)
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    status_color = "#22c55e" if KEY_METRICS["status"] == "ON TRACK" else "#C74634"

    metric_cards = ""
    for k, v in KEY_METRICS.items():
        label = k.replace("_", " ").title()
        val_color = status_color if k == "status" else "#38bdf8"
        metric_cards += f"""
        <div style="background:#1e293b;border-radius:8px;padding:14px 18px;">
          <div style="color:#94a3b8;font-size:11px;margin-bottom:4px;">{label}</div>
          <div style="color:{val_color};font-size:15px;font-weight:700;">{v}</div>
        </div>"""

    anomaly_rows = ""
    for day, info in ANOMALY_DAYS.items():
        spend = _daily_spend[day - 1]
        sev_color = "#38bdf8" if info["severity"] == "info" else "#f59e0b"
        anomaly_rows += f"""
        <tr>
          <td style="padding:8px 12px;color:#94a3b8;">Day {day}</td>
          <td style="padding:8px 12px;color:#f1f5f9;font-weight:600;">${spend:.2f}</td>
          <td style="padding:8px 12px;color:{sev_color};">{info["label"]}</td>
          <td style="padding:8px 12px;color:#cbd5e1;">{info["desc"]}</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Cloud Cost Alerting | OCI Robot Cloud</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0;}}
  body{{background:#0f172a;color:#e2e8f0;font-family:'Inter',system-ui,sans-serif;min-height:100vh;}}
  header{{background:#1e293b;border-bottom:3px solid #C74634;padding:16px 32px;display:flex;align-items:center;justify-content:space-between;}}
  .logo{{color:#C74634;font-size:20px;font-weight:800;letter-spacing:1px;}}
  .subtitle{{color:#94a3b8;font-size:13px;}}
  .badge{{background:#22c55e;color:#052e16;border-radius:20px;padding:4px 14px;font-size:12px;font-weight:700;}}
  main{{padding:28px 32px;max-width:900px;margin:0 auto;}}
  h2{{color:#f1f5f9;font-size:16px;font-weight:700;margin-bottom:14px;border-left:4px solid #C74634;padding-left:10px;}}
  .card{{background:#1e293b;border-radius:10px;padding:20px;margin-bottom:24px;}}
  .metrics-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:24px;}}
  .two-col{{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-bottom:24px;}}
  .ts{{color:#64748b;font-size:11px;text-align:right;margin-top:8px;}}
  pre{{background:#0d1b2a;border-radius:6px;padding:12px;font-size:11px;color:#94a3b8;overflow:auto;}}
  table{{width:100%;border-collapse:collapse;}}
  tr:nth-child(even){{background:#131f2e;}}
  th{{background:#1e293b;color:#94a3b8;font-size:11px;padding:8px 12px;text-align:left;}}
</style>
</head>
<body>
<header>
  <div>
    <div class="logo">OCI ROBOT CLOUD</div>
    <div class="subtitle">Cloud Cost Alerting — Port 8273</div>
  </div>
  <span class="badge">STATUS: ON TRACK</span>
</header>
<main>
  <div class="metrics-grid">{metric_cards}</div>

  <div class="two-col">
    <div class="card">
      <h2>Budget Burn Rate Gauge</h2>
      {gauge_svg}
    </div>
    <div class="card" style="display:flex;flex-direction:column;justify-content:center;">
      <h2>Alert Thresholds</h2>
      <table>
        <tr><th>Zone</th><th>Threshold</th><th>Action</th></tr>
        <tr><td style="color:#22c55e;padding:8px 12px;">Green</td><td style="padding:8px 12px;">&lt; 70%</td><td style="padding:8px 12px;color:#94a3b8;">No action</td></tr>
        <tr style="background:#131f2e;"><td style="color:#f59e0b;padding:8px 12px;">Amber</td><td style="padding:8px 12px;">70%–90%</td><td style="padding:8px 12px;color:#94a3b8;">Slack alert</td></tr>
        <tr><td style="color:#C74634;padding:8px 12px;">Red</td><td style="padding:8px 12px;">&gt; 90%</td><td style="padding:8px 12px;color:#94a3b8;">PagerDuty + email</td></tr>
      </table>
      <div style="margin-top:16px;padding:12px;background:#0d1b2a;border-radius:6px;">
        <div style="color:#94a3b8;font-size:11px;margin-bottom:6px;">Current Status</div>
        <div style="color:#38bdf8;font-size:18px;font-weight:700;">44.8% utilised</div>
        <div style="color:#64748b;font-size:12px;margin-top:4px;">Projected EOM: ${PROJECTED_EOD:.2f} (68.4%) — AMBER zone</div>
      </div>
    </div>
  </div>

  <div class="card">
    <h2>Daily Cost Anomaly Chart — March 2026 (30 days)</h2>
    {anomaly_svg}
  </div>

  <div class="card">
    <h2>Detected Anomalies</h2>
    <table>
      <tr><th>Day</th><th>Spend</th><th>Event</th><th>Description</th></tr>
      {anomaly_rows}
    </table>
  </div>

  <div class="card">
    <h2>Raw Metrics</h2>
    <pre>{metrics_json}</pre>
    <div class="ts">Last updated: {ts}</div>
  </div>
</main>
</body>
</html>"""


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

if _USE_FASTAPI:
    app = FastAPI(
        title="Cloud Cost Alerting",
        description="Proactive cloud cost alerting with anomaly detection",
        version="1.0.0",
    )

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return _render_html()

    @app.get("/api/daily")
    def get_daily():
        return JSONResponse({
            "days": [
                {
                    "day": i + 1,
                    "spend": _daily_spend[i],
                    "rolling_avg": round(_rolling[i], 3),
                    "anomaly": (i + 1) in ANOMALY_DAYS,
                    "anomaly_info": ANOMALY_DAYS.get(i + 1),
                }
                for i in range(len(_daily_spend))
            ],
            "ucl": round(UCL_COST, 3),
            "lcl": round(LCL_COST, 3),
            "mean": round(_mu, 3),
        })

    @app.get("/api/budget")
    def get_budget():
        return JSONResponse({
            "budget": MONTH_BUDGET,
            "actual": MONTH_ACTUAL,
            "projected_eom": PROJECTED_EOD,
            "utilization_pct": round(100 * MONTH_ACTUAL / MONTH_BUDGET, 2),
            "projected_utilization_pct": round(100 * PROJECTED_EOD / MONTH_BUDGET, 2),
            "status": KEY_METRICS["status"],
        })

    @app.get("/api/metrics")
    def get_metrics():
        return JSONResponse(KEY_METRICS)

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "cloud_cost_alerting", "port": 8273}

else:
    import http.server
    import socketserver

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            body = _render_html().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            pass


if __name__ == "__main__":
    if _USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8273)
    else:
        print("FastAPI not found — falling back to stdlib http.server on port 8273")
        with socketserver.TCPServer(("", 8273), _Handler) as httpd:
            print("Serving on http://0.0.0.0:8273")
            httpd.serve_forever()
