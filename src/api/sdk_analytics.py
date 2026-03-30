"""OCI Robot Cloud — SDK Usage Analytics  (port 8195)"""

import math
from datetime import datetime, timezone

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
except ImportError:
    FastAPI = None

# ---------------------------------------------------------------------------
# Static data
# ---------------------------------------------------------------------------

VERSIONS = [
    {"version": "v0.1.0", "installs": 47,  "active_users": 12, "deprecated": True,  "current": False},
    {"version": "v0.2.0", "installs": 89,  "active_users": 34, "deprecated": False, "current": False},
    {"version": "v0.3.0", "installs": 124, "active_users": 78, "deprecated": False, "current": True},
]

METHODS = [
    {"method": "RobotCloudClient.predict",         "calls": 12847, "unique_users": 4, "avg_latency_ms": 228},
    {"method": "RobotCloudClient.submit_dagger_step","calls": 8420,  "unique_users": 2, "avg_latency_ms": 314},
    {"method": "RobotCloudClient.list_checkpoints", "calls": 4821,  "unique_users": 4, "avg_latency_ms": 18},
    {"method": "RobotCloudClient.get_eval_results", "calls": 3241,  "unique_users": 4, "avg_latency_ms": 22},
    {"method": "RobotCloudClient.get_billing",      "calls": 287,   "unique_users": 4, "avg_latency_ms": 31},
    {"method": "RobotCloudClient.upload_demos",     "calls": 28,    "unique_users": 3, "avg_latency_ms": 18400},
    {"method": "RobotCloudClient.create_sdg_job",   "calls": 14,    "unique_users": 2, "avg_latency_ms": 847},
    {"method": "RobotCloudClient.finetune",         "calls": 12,    "unique_users": 3, "avg_latency_ms": 14200000},
]

# 12-week install trend (weeks ending with v0.3.0 release at week 9 = spike)
WEEKLY_TREND = [
    {"week": "Jan W1",  "installs": 3,  "annotation": None},
    {"week": "Jan W2",  "installs": 5,  "annotation": None},
    {"week": "Jan W3",  "installs": 7,  "annotation": None},
    {"week": "Jan W4",  "installs": 9,  "annotation": None},
    {"week": "Feb W1",  "installs": 11, "annotation": None},
    {"week": "Feb W2",  "installs": 13, "annotation": None},
    {"week": "Feb W3",  "installs": 14, "annotation": None},
    {"week": "Feb W4",  "installs": 16, "annotation": None},
    {"week": "Mar W1",  "installs": 22, "annotation": "v0.3.0 release"},
    {"week": "Mar W2",  "installs": 28, "annotation": None},
    {"week": "Mar W3",  "installs": 31, "annotation": None},
    {"week": "Mar W4",  "installs": 34, "annotation": None},
]

# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------


def _methods_bar_svg() -> str:
    """680x200 horizontal bar chart — sorted by calls, log-normalized."""
    width, height = 680, 200
    label_w = 260
    value_w = 70
    chart_w = width - label_w - value_w
    methods_sorted = sorted(METHODS, key=lambda m: m["calls"])
    n = len(methods_sorted)
    bar_h = max(12, (height - 20) // n - 4)
    row_h = (height - 20) // n

    max_log = math.log10(max(m["calls"] for m in methods_sorted) + 1)

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'style="background:#1e293b;border-radius:8px;font-family:monospace">',
    ]

    top_calls = max(m["calls"] for m in methods_sorted)
    for i, m in enumerate(methods_sorted):
        y_center = 10 + i * row_h + row_h // 2
        log_val = math.log10(m["calls"] + 1)
        bar_fill = int(chart_w * log_val / max_log)
        # Oracle red for top method
        color = "#C74634" if m["calls"] == top_calls else "#38bdf8"
        short_name = m["method"].replace("RobotCloudClient.", "")

        lines.append(
            f'<rect x="{label_w}" y="{y_center - bar_h//2}" width="{chart_w}" height="{bar_h}" '
            f'rx="3" fill="#334155"/>'
        )
        lines.append(
            f'<rect x="{label_w}" y="{y_center - bar_h//2}" width="{bar_fill}" height="{bar_h}" '
            f'rx="3" fill="{color}" opacity="0.85"/>'
        )
        lines.append(
            f'<text x="{label_w - 8}" y="{y_center + 4}" text-anchor="end" '
            f'font-size="11" fill="#cbd5e1">{short_name}</text>'
        )
        calls_str = f"{m['calls']:,}"
        lines.append(
            f'<text x="{label_w + bar_fill + 6}" y="{y_center + 4}" '
            f'font-size="10" fill="{color}">{calls_str}</text>'
        )

    lines.append(
        f'<text x="{label_w}" y="{height - 2}" font-size="9" fill="#64748b">log scale</text>'
    )
    lines.append("</svg>")
    return "\n".join(lines)


def _donut_svg() -> str:
    """420x260 donut chart — version adoption by active_users."""
    width, height = 420, 260
    cx, cy, r_outer, r_inner = 150, 130, 110, 60

    total_users = sum(v["active_users"] for v in VERSIONS)
    colors = ["#6b7280", "#38bdf8", "#C74634"]  # deprecated, v0.2, current
    sky = "#38bdf8"
    gray = "#6b7280"
    version_colors = [gray, "#7dd3fc", sky]

    def polar(angle_deg: float, radius: float):
        rad = math.radians(angle_deg - 90)
        return cx + radius * math.cos(rad), cy + radius * math.sin(rad)

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'style="background:#1e293b;border-radius:8px;font-family:monospace">',
    ]

    start_angle = 0.0
    for idx, v in enumerate(VERSIONS):
        sweep = v["active_users"] / total_users * 360
        end_angle = start_angle + sweep
        large_arc = 1 if sweep > 180 else 0
        color = version_colors[idx]
        if v.get("deprecated"):
            color = gray

        ox1, oy1 = polar(start_angle, r_outer)
        ox2, oy2 = polar(end_angle, r_outer)
        ix1, iy1 = polar(end_angle, r_inner)
        ix2, iy2 = polar(start_angle, r_inner)

        path = (
            f"M {ox1:.1f} {oy1:.1f} "
            f"A {r_outer} {r_outer} 0 {large_arc} 1 {ox2:.1f} {oy2:.1f} "
            f"L {ix1:.1f} {iy1:.1f} "
            f"A {r_inner} {r_inner} 0 {large_arc} 0 {ix2:.1f} {iy2:.1f} Z"
        )
        lines.append(f'<path d="{path}" fill="{color}" opacity="0.88" stroke="#1e293b" stroke-width="2"/>')
        start_angle = end_angle

    # center label
    lines.append(
        f'<text x="{cx}" y="{cy - 8}" text-anchor="middle" font-size="20" font-weight="700" fill="#e2e8f0">{total_users}</text>'
    )
    lines.append(
        f'<text x="{cx}" y="{cy + 12}" text-anchor="middle" font-size="10" fill="#94a3b8">Active Users</text>'
    )

    # legend
    lx = 280
    for idx, v in enumerate(VERSIONS):
        ly = 80 + idx * 40
        color = version_colors[idx]
        if v.get("deprecated"):
            color = gray
        lines.append(f'<rect x="{lx}" y="{ly}" width="14" height="14" rx="3" fill="{color}"/>')
        lines.append(
            f'<text x="{lx + 20}" y="{ly + 11}" font-size="12" fill="#e2e8f0" font-weight="600">{v["version"]}</text>'
        )
        tag = "(current)" if v.get("current") else ("(deprecated)" if v.get("deprecated") else "")
        lines.append(
            f'<text x="{lx + 20}" y="{ly + 25}" font-size="10" fill="#64748b">{v["active_users"]} users {tag}</text>'
        )

    lines.append("</svg>")
    return "\n".join(lines)


def _trend_svg() -> str:
    """680x160 line chart — 12-week install trend."""
    width, height = 680, 160
    pad_l, pad_r, pad_t, pad_b = 40, 20, 20, 30
    chart_w = width - pad_l - pad_r
    chart_h = height - pad_t - pad_b

    max_val = max(w["installs"] for w in WEEKLY_TREND)
    n = len(WEEKLY_TREND)

    def px(i: int) -> float:
        return pad_l + i * chart_w / (n - 1)

    def py(v: int) -> float:
        return pad_t + chart_h - (v / max_val) * chart_h

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'style="background:#1e293b;border-radius:8px;font-family:monospace">',
    ]

    # grid lines
    for g in [0, max_val // 2, max_val]:
        gy = py(g)
        lines.append(
            f'<line x1="{pad_l}" y1="{gy:.1f}" x2="{width-pad_r}" y2="{gy:.1f}" '
            f'stroke="#334155" stroke-width="1"/>'
        )
        lines.append(
            f'<text x="{pad_l - 4}" y="{gy + 4:.1f}" text-anchor="end" font-size="9" fill="#64748b">{g}</text>'
        )

    # area fill
    pts_top = " ".join(f"{px(i):.1f},{py(w['installs']):.1f}" for i, w in enumerate(WEEKLY_TREND))
    pts_area = pts_top + f" {px(n-1):.1f},{py(0):.1f} {px(0):.1f},{py(0):.1f}"
    lines.append(f'<polygon points="{pts_area}" fill="#38bdf8" opacity="0.12"/>')

    # line
    polyline_pts = " ".join(f"{px(i):.1f},{py(w['installs']):.1f}" for i, w in enumerate(WEEKLY_TREND))
    lines.append(f'<polyline points="{polyline_pts}" fill="none" stroke="#38bdf8" stroke-width="2"/>')

    # dots + annotations
    for i, w in enumerate(WEEKLY_TREND):
        x, y = px(i), py(w["installs"])
        if w["annotation"]:
            lines.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="#C74634"/>')
            lines.append(
                f'<text x="{x:.1f}" y="{y - 10:.1f}" text-anchor="middle" '
                f'font-size="9" fill="#C74634">{w["annotation"]}</text>'
            )
        else:
            lines.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="#38bdf8"/>')

    # x-axis labels (every 3 weeks)
    for i, w in enumerate(WEEKLY_TREND):
        if i % 3 == 0:
            lines.append(
                f'<text x="{px(i):.1f}" y="{height - 4}" text-anchor="middle" '
                f'font-size="9" fill="#64748b">{w["week"]}</text>'
            )

    lines.append("</svg>")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Dashboard HTML
# ---------------------------------------------------------------------------


def _dashboard_html() -> str:
    methods_svg = _methods_bar_svg()
    donut_svg = _donut_svg()
    trend_svg = _trend_svg()

    total_calls = sum(m["calls"] for m in METHODS)
    total_installs = sum(v["installs"] for v in VERSIONS)
    total_users = sum(v["active_users"] for v in VERSIONS)

    version_rows = ""
    for v in VERSIONS:
        status_color = "#6b7280" if v["deprecated"] else ("#38bdf8" if v["current"] else "#94a3b8")
        status_label = "CURRENT" if v["current"] else ("DEPRECATED" if v["deprecated"] else "STABLE")
        version_rows += f"""
        <tr>
          <td style="padding:8px 12px;color:#e2e8f0;font-weight:700">{v['version']}</td>
          <td style="padding:8px 12px">
            <span style="color:{status_color};font-size:11px;font-weight:700">{status_label}</span>
          </td>
          <td style="padding:8px 12px;color:#94a3b8">{v['installs']}</td>
          <td style="padding:8px 12px;color:#94a3b8">{v['active_users']}</td>
        </tr>
        """

    method_rows = ""
    for m in sorted(METHODS, key=lambda x: x["calls"], reverse=True):
        lat = m["avg_latency_ms"]
        lat_str = f"{lat/1000:.1f}s" if lat >= 1000 else f"{lat}ms"
        method_rows += f"""
        <tr>
          <td style="padding:8px 12px;color:#e2e8f0;font-size:12px">{m['method']}</td>
          <td style="padding:8px 12px;color:#38bdf8;font-weight:600">{m['calls']:,}</td>
          <td style="padding:8px 12px;color:#94a3b8">{m['unique_users']}</td>
          <td style="padding:8px 12px;color:#94a3b8">{lat_str}</td>
        </tr>
        """

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>OCI Robot Cloud — SDK Analytics</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; }}
    .header {{ background: linear-gradient(135deg, #1e3a5f 0%, #0f172a 100%);
               border-bottom: 2px solid #C74634; padding: 24px 32px; }}
    .header h1 {{ font-size: 22px; font-weight: 700; }}
    .header h1 span {{ color: #38bdf8; }}
    .header p {{ color: #64748b; font-size: 13px; margin-top: 4px; }}
    .kpi-bar {{ background: #1e293b; padding: 16px 32px; border-bottom: 1px solid #334155;
                display: flex; gap: 40px; }}
    .kpi {{ }}
    .kpi-val {{ font-size: 32px; font-weight: 800; color: #38bdf8; }}
    .kpi-label {{ font-size: 11px; color: #64748b; text-transform: uppercase; letter-spacing: 1px; }}
    .container {{ padding: 24px 32px; max-width: 960px; }}
    .section {{ margin-bottom: 32px; }}
    .section h2 {{ font-size: 13px; font-weight: 700; color: #38bdf8;
                   text-transform: uppercase; letter-spacing: 1px; margin-bottom: 14px; }}
    .card {{ background: #1e293b; border: 1px solid #334155; border-radius: 10px;
             overflow: hidden; }}
    .row2 {{ display: flex; gap: 20px; }}
    .row2 > div {{ flex: 1; }}
    table {{ width: 100%; border-collapse: collapse; }}
    tr:not(:last-child) {{ border-bottom: 1px solid #334155; }}
    tr:hover {{ background: #0f2235; }}
    thead tr {{ background: #0f172a; }}
    th {{ padding: 8px 12px; text-align: left; font-size: 11px; color: #64748b; font-weight: 600; }}
    .footer {{ padding: 16px 32px; color: #334155; font-size: 11px; }}
  </style>
</head>
<body>
  <div class="header">
    <h1>OCI Robot Cloud &mdash; <span>SDK Analytics</span></h1>
    <p>oci-robot-cloud pip package &nbsp;|&nbsp; Usage as of 2026-03-30 &nbsp;|&nbsp; Port 8195</p>
  </div>

  <div class="kpi-bar">
    <div class="kpi">
      <div class="kpi-val">{total_installs}</div>
      <div class="kpi-label">Total Installs</div>
    </div>
    <div class="kpi">
      <div class="kpi-val">{total_users}</div>
      <div class="kpi-label">Active Users</div>
    </div>
    <div class="kpi">
      <div class="kpi-val">{total_calls:,}</div>
      <div class="kpi-label">API Calls (30d)</div>
    </div>
    <div class="kpi">
      <div class="kpi-val" style="color:#C74634">v0.3.0</div>
      <div class="kpi-label">Current Version</div>
    </div>
  </div>

  <div class="container">
    <div class="section">
      <h2>Method Popularity (last 30 days)</h2>
      <div class="card" style="padding:12px">{methods_svg}</div>
      <div style="margin-top:6px;font-size:11px;color:#64748b">x-axis: log scale &nbsp;|&nbsp; <span style="color:#C74634">&#9646;</span> most-called method</div>
    </div>

    <div class="section row2">
      <div>
        <h2>Version Adoption</h2>
        <div class="card" style="padding:12px">{donut_svg}</div>
      </div>
      <div>
        <h2>Version Details</h2>
        <div class="card">
          <table>
            <thead><tr>
              <th>VERSION</th><th>STATUS</th><th>INSTALLS</th><th>ACTIVE USERS</th>
            </tr></thead>
            <tbody>{version_rows}</tbody>
          </table>
        </div>
      </div>
    </div>

    <div class="section">
      <h2>12-Week Install Trend</h2>
      <div class="card" style="padding:12px">{trend_svg}</div>
    </div>

    <div class="section">
      <h2>Method Call Details</h2>
      <div class="card">
        <table>
          <thead><tr>
            <th>METHOD</th><th>CALLS (30d)</th><th>UNIQUE USERS</th><th>AVG LATENCY</th>
          </tr></thead>
          <tbody>{method_rows}</tbody>
        </table>
      </div>
    </div>
  </div>

  <div class="footer">OCI Robot Cloud &copy; 2026 Oracle Corporation &mdash; Confidential</div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

if FastAPI is not None:
    app = FastAPI(
        title="OCI Robot Cloud — SDK Analytics",
        description="Track pip installs, API calls, and feature adoption for oci-robot-cloud SDK.",
        version="1.0.0",
    )

    @app.get("/", response_class=HTMLResponse, summary="Dashboard")
    def dashboard():
        return HTMLResponse(content=_dashboard_html())

    @app.get("/versions", summary="SDK version adoption data")
    def get_versions():
        return JSONResponse(content=VERSIONS)

    @app.get("/methods", summary="SDK method call counts (last 30d)")
    def get_methods():
        return JSONResponse(content=sorted(METHODS, key=lambda m: m["calls"], reverse=True))

    @app.get("/trend", summary="Weekly install trend (12 weeks)")
    def get_trend():
        return JSONResponse(content=WEEKLY_TREND)

    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=8195)
else:
    print("FastAPI not installed. Run: pip install fastapi uvicorn")
