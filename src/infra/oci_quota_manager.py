"""OCI Quota Manager — FastAPI service on port 8230.

Manages OCI service quota utilization and proactive limit requests.
Dashboard: http://localhost:8230
"""

import math
import random
from datetime import date, timedelta

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    _FASTAPI = True
except ImportError:  # pragma: no cover
    _FASTAPI = False

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

TODAY = date(2026, 3, 30)

QUOTA_RESOURCES = [
    {"name": "GPU_A100_80GB",  "current": 75,  "reserved": 10, "limit": 100, "growth": 0.35},
    {"name": "GPU_A100_40GB",  "current": 52,  "reserved": 8,  "limit": 100, "growth": 0.20},
    {"name": "vCPU",           "current": 89,  "reserved": 5,  "limit": 100, "growth": 0.25},
    {"name": "RAM_TB",         "current": 61,  "reserved": 12, "limit": 100, "growth": 0.22},
    {"name": "Block_Storage",  "current": 42,  "reserved": 3,  "limit": 100, "growth": 0.15},
    {"name": "Object_Storage", "current": 38,  "reserved": 2,  "limit": 100, "growth": 0.18},
    {"name": "Network_BW",     "current": 67,  "reserved": 7,  "limit": 100, "growth": 0.12},
    {"name": "IP_Addresses",   "current": 55,  "reserved": 5,  "limit": 100, "growth": 0.10},
]

LEAD_TIME_DAYS = 45  # OCI quota increase lead time


def _color(pct: float) -> str:
    if pct >= 90:
        return "#ef4444"   # red
    if pct >= 70:
        return "#f59e0b"   # amber
    return "#22c55e"       # green


def _days_until_limit(current_pct: float, growth_monthly: float) -> int:
    """Days until utilization hits 100%, given monthly growth rate."""
    if current_pct >= 100:
        return 0
    # current_pct * (1 + growth_monthly/30)^days = 100
    daily = growth_monthly / 30
    if daily <= 0:
        return 9999
    days = math.log(100 / current_pct) / math.log(1 + daily)
    return max(0, int(days))


# ---------------------------------------------------------------------------
# SVG builders
# ---------------------------------------------------------------------------

def _svg_quota_bars() -> str:
    """Horizontal stacked bar chart for 8 resource types."""
    W, H = 700, 320
    bar_h = 22
    gap = 14
    left_pad = 140
    top_pad = 30

    rows = []
    for i, r in enumerate(QUOTA_RESOURCES):
        y = top_pad + i * (bar_h + gap)
        used_w  = (r["current"] / r["limit"]) * (W - left_pad - 20)
        rsrv_w  = (r["reserved"] / r["limit"]) * (W - left_pad - 20)
        col     = _color(r["current"])
        label   = r["name"]
        pct_txt = f"{r['current']}%"

        rows.append(
            f'<text x="{left_pad - 6}" y="{y + bar_h - 6}" '
            f'text-anchor="end" font-size="11" fill="#94a3b8">{label}</text>'
        )
        # background track
        rows.append(
            f'<rect x="{left_pad}" y="{y}" width="{W - left_pad - 20}" height="{bar_h}" '
            f'rx="3" fill="#1e293b"/>'
        )
        # used
        rows.append(
            f'<rect x="{left_pad}" y="{y}" width="{used_w:.1f}" height="{bar_h}" '
            f'rx="3" fill="{col}" opacity="0.85"/>'
        )
        # reserved overlay
        rows.append(
            f'<rect x="{left_pad + used_w:.1f}" y="{y}" width="{rsrv_w:.1f}" height="{bar_h}" '
            f'rx="3" fill="#38bdf8" opacity="0.45"/>'
        )
        # pct label
        rows.append(
            f'<text x="{left_pad + used_w + 4:.1f}" y="{y + bar_h - 6}" '
            f'font-size="11" fill="#e2e8f0">{pct_txt}</text>'
        )

    # legend
    legend_y = top_pad + len(QUOTA_RESOURCES) * (bar_h + gap) + 8
    legend = (
        f'<rect x="{left_pad}" y="{legend_y}" width="12" height="12" fill="#22c55e"/>'
        f'<text x="{left_pad + 16}" y="{legend_y + 10}" font-size="10" fill="#94a3b8">Used &lt;70%</text>'
        f'<rect x="{left_pad + 90}" y="{legend_y}" width="12" height="12" fill="#f59e0b"/>'
        f'<text x="{left_pad + 106}" y="{legend_y + 10}" font-size="10" fill="#94a3b8">70-90% AMBER</text>'
        f'<rect x="{left_pad + 210}" y="{legend_y}" width="12" height="12" fill="#ef4444"/>'
        f'<text x="{left_pad + 226}" y="{legend_y + 10}" font-size="10" fill="#94a3b8">&gt;90% CRITICAL</text>'
        f'<rect x="{left_pad + 340}" y="{legend_y}" width="12" height="12" fill="#38bdf8" opacity="0.45"/>'
        f'<text x="{left_pad + 356}" y="{legend_y + 10}" font-size="10" fill="#94a3b8">Reserved</text>'
    )

    total_h = legend_y + 24
    svg_rows = "\n".join(rows)
    return (
        f'<svg viewBox="0 0 {W} {total_h}" xmlns="http://www.w3.org/2000/svg" '
        f'style="width:100%;background:#0f172a;border-radius:8px;padding:10px">'
        f'<text x="{W//2}" y="16" text-anchor="middle" font-size="13" font-weight="bold" fill="#f1f5f9">'
        f'OCI Quota Utilization — Current vs Reserved vs Limit</text>'
        f'{svg_rows}{legend}'
        f'</svg>'
    )


def _svg_forecast_timeline() -> str:
    """90-day forecast line chart for top 3 constrained resources."""
    W, H = 700, 280
    left, right, top, bottom = 50, 30, 30, 50
    plot_w = W - left - right
    plot_h = H - top - bottom
    days = 90

    # Top 3 by current utilization
    top3 = sorted(QUOTA_RESOURCES, key=lambda r: r["current"], reverse=True)[:3]
    colors = ["#C74634", "#f59e0b", "#38bdf8"]

    def x_pos(d):
        return left + (d / days) * plot_w

    def y_pos(pct):
        return top + plot_h - (min(pct, 110) / 110) * plot_h

    lines = []
    need_by_markers = []
    # axes
    lines.append(
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_h}" stroke="#334155" stroke-width="1"/>'
        f'<line x1="{left}" y1="{top + plot_h}" x2="{left + plot_w}" y2="{top + plot_h}" stroke="#334155" stroke-width="1"/>'
    )
    # 100% danger line
    y100 = y_pos(100)
    lines.append(
        f'<line x1="{left}" y1="{y100:.1f}" x2="{left + plot_w}" y2="{y100:.1f}" '
        f'stroke="#ef4444" stroke-width="1" stroke-dasharray="4,3"/>'
        f'<text x="{left + 4}" y="{y100 - 4:.1f}" font-size="10" fill="#ef4444">100% Limit</text>'
    )

    # y-axis labels
    for pct in [0, 25, 50, 75, 100]:
        yp = y_pos(pct)
        lines.append(
            f'<text x="{left - 4}" y="{yp + 4:.1f}" text-anchor="end" font-size="9" fill="#64748b">{pct}%</text>'
            f'<line x1="{left}" y1="{yp:.1f}" x2="{left + plot_w}" y2="{yp:.1f}" stroke="#1e293b" stroke-width="1"/>'
        )

    # x-axis labels (every 15 days)
    for d in range(0, days + 1, 15):
        xp = x_pos(d)
        dt = (TODAY + timedelta(days=d)).strftime("%b %d")
        lines.append(
            f'<text x="{xp:.1f}" y="{top + plot_h + 14}" text-anchor="middle" font-size="9" fill="#64748b">{dt}</text>'
        )

    legend_items = []
    for idx, (r, col) in enumerate(zip(top3, colors)):
        daily = r["growth"] / 30
        pts = []
        for d in range(days + 1):
            pct = r["current"] * (1 + daily) ** d
            pts.append(f"{x_pos(d):.1f},{y_pos(pct):.1f}")
        polyline = " ".join(pts)
        lines.append(f'<polyline points="{polyline}" fill="none" stroke="{col}" stroke-width="2"/>')

        # "request needed by" marker
        days_left = _days_until_limit(r["current"], r["growth"])
        request_day = max(0, days_left - LEAD_TIME_DAYS)
        if 0 <= request_day <= days:
            xp = x_pos(request_day)
            lines.append(
                f'<line x1="{xp:.1f}" y1="{top}" x2="{xp:.1f}" y2="{top + plot_h}" '
                f'stroke="{col}" stroke-width="1" stroke-dasharray="3,3"/>'
                f'<text x="{xp + 2:.1f}" y="{top + 10 + idx * 12}" font-size="9" fill="{col}">'
                f'⚑ {r["name"]} req by {(TODAY + timedelta(days=request_day)).strftime("%b %d")}</text>'
            )

        legend_items.append(
            f'<rect x="{left + idx * 180}" y="{H - 14}" width="12" height="10" fill="{col}"/>'
            f'<text x="{left + idx * 180 + 16}" y="{H - 5}" font-size="10" fill="#94a3b8">{r["name"]}</text>'
        )

    svg_body = "\n".join(lines) + "\n" + "\n".join(legend_items)
    return (
        f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" '
        f'style="width:100%;background:#0f172a;border-radius:8px;padding:10px">'
        f'<text x="{W//2}" y="16" text-anchor="middle" font-size="13" font-weight="bold" fill="#f1f5f9">'
        f'90-Day Quota Exhaustion Forecast (35% MoM Growth)</text>'
        f'{svg_body}'
        f'</svg>'
    )


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def _build_dashboard() -> str:
    rows_html = ""
    for r in QUOTA_RESOURCES:
        days_left = _days_until_limit(r["current"], r["growth"])
        req_date  = (TODAY + timedelta(days=max(0, days_left - LEAD_TIME_DAYS))).strftime("%b %d, %Y")
        col       = _color(r["current"])
        badge     = "CRITICAL" if r["current"] >= 90 else ("AMBER" if r["current"] >= 70 else "OK")
        rows_html += f"""
        <tr>
          <td style="padding:8px 12px;color:#e2e8f0">{r['name']}</td>
          <td style="padding:8px 12px;color:{col};font-weight:bold">{r['current']}%</td>
          <td style="padding:8px 12px;color:#38bdf8">{r['reserved']}%</td>
          <td style="padding:8px 12px;color:{col}">
            <span style="background:{col}22;border:1px solid {col};border-radius:4px;
                         padding:2px 6px;font-size:12px">{badge}</span>
          </td>
          <td style="padding:8px 12px;color:#94a3b8">{days_left} days</td>
          <td style="padding:8px 12px;color:#f59e0b">{req_date}</td>
        </tr>"""

    svg1 = _svg_quota_bars()
    svg2 = _svg_forecast_timeline()

    ai_world_days = (date(2026, 9, 15) - TODAY).days
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>OCI Quota Manager — Port 8230</title>
  <style>
    * {{ margin:0; padding:0; box-sizing:border-box }}
    body {{ background:#0f172a; color:#e2e8f0; font-family:'Segoe UI',system-ui,sans-serif; padding:24px }}
    h1   {{ color:#C74634; font-size:22px; margin-bottom:4px }}
    h2   {{ color:#38bdf8; font-size:15px; margin:24px 0 10px }}
    .sub {{ color:#64748b; font-size:13px; margin-bottom:20px }}
    .kpi-row {{ display:flex; gap:16px; flex-wrap:wrap; margin-bottom:24px }}
    .kpi {{ background:#1e293b; border:1px solid #334155; border-radius:8px;
             padding:14px 20px; min-width:160px }}
    .kpi .val  {{ font-size:26px; font-weight:700; color:#38bdf8 }}
    .kpi .lbl  {{ font-size:12px; color:#64748b; margin-top:2px }}
    .kpi.warn .val {{ color:#f59e0b }}
    .kpi.crit .val {{ color:#ef4444 }}
    table {{ width:100%; border-collapse:collapse; background:#1e293b;
             border-radius:8px; overflow:hidden }}
    thead th {{ background:#0f172a; padding:8px 12px; text-align:left;
                font-size:12px; color:#64748b; border-bottom:1px solid #334155 }}
    tbody tr:nth-child(even) {{ background:#162032 }}
    .chart-grid {{ display:grid; grid-template-columns:1fr; gap:20px; margin-bottom:24px }}
    .badge-oracle {{ display:inline-block; background:#C7463422; border:1px solid #C74634;
                     border-radius:4px; padding:2px 8px; font-size:11px; color:#C74634;
                     margin-left:12px }}
  </style>
</head>
<body>
  <h1>OCI Quota Manager <span class="badge-oracle">PORT 8230</span></h1>
  <p class="sub">Oracle Cloud Infrastructure — Quota Utilization &amp; Proactive Limit Requests | {TODAY}</p>

  <div class="kpi-row">
    <div class="kpi crit">
      <div class="val">2</div>
      <div class="lbl">Resources &gt;70% (Action Needed)</div>
    </div>
    <div class="kpi warn">
      <div class="val">45 days</div>
      <div class="lbl">OCI Quota Request Lead Time</div>
    </div>
    <div class="kpi">
      <div class="val" style="color:#22c55e">May 2026</div>
      <div class="lbl">GPU_A100_80GB — Request Needed By</div>
    </div>
    <div class="kpi">
      <div class="val">{ai_world_days}</div>
      <div class="lbl">Days to AI World Sep 2026</div>
    </div>
    <div class="kpi">
      <div class="val" style="color:#38bdf8">42%</div>
      <div class="lbl">Storage Headroom (OK)</div>
    </div>
  </div>

  <h2>Quota Utilization Dashboard</h2>
  <div class="chart-grid">{svg1}</div>

  <h2>90-Day Forecast — Top Constrained Resources</h2>
  <div class="chart-grid" style="margin-bottom:24px">{svg2}</div>

  <h2>Resource Detail Table</h2>
  <table>
    <thead>
      <tr>
        <th>Resource</th><th>Current %</th><th>Reserved %</th>
        <th>Status</th><th>Days Until Limit</th><th>Request Needed By</th>
      </tr>
    </thead>
    <tbody>{rows_html}</tbody>
  </table>

  <p style="margin-top:20px;font-size:12px;color:#334155">
    OCI Robot Cloud — Quota Manager v1.0 | Data refreshed {TODAY} | Lead time: {LEAD_TIME_DAYS} days
  </p>
</body>
</html>"""


# ---------------------------------------------------------------------------
# FastAPI / stdlib server
# ---------------------------------------------------------------------------

if _FASTAPI:
    app = FastAPI(title="OCI Quota Manager", version="1.0")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return _build_dashboard()

    @app.get("/api/quotas")
    async def api_quotas():
        result = []
        for r in QUOTA_RESOURCES:
            days_left = _days_until_limit(r["current"], r["growth"])
            result.append({
                **r,
                "days_until_limit": days_left,
                "request_by": str(TODAY + timedelta(days=max(0, days_left - LEAD_TIME_DAYS))),
                "status": "CRITICAL" if r["current"] >= 90 else ("AMBER" if r["current"] >= 70 else "OK"),
            })
        return {"date": str(TODAY), "lead_time_days": LEAD_TIME_DAYS, "resources": result}

    @app.get("/health")
    async def health():
        return {"status": "ok", "port": 8230}

else:  # pragma: no cover — stdlib fallback
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = _build_dashboard().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):  # silence default logging
            pass


if __name__ == "__main__":
    if _FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8230)
    else:  # pragma: no cover
        print("[oci_quota_manager] fastapi not found — starting stdlib server on :8230")
        HTTPServer(("0.0.0.0", 8230), _Handler).serve_forever()
