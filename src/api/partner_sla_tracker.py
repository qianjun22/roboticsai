"""Partner SLA Tracker — OCI Robot Cloud
Port 8166: Per-partner SLA tracking with breach detection and credit calculation.
"""
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
except ImportError:
    FastAPI = None

from datetime import datetime

# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

PARTNERS = [
    {
        "id": "physical_intelligence",
        "display_name": "Physical Intelligence",
        "tier": "enterprise",
        "uptime_target": 99.9,
        "actual_30d_uptime": 99.94,
        "p99_target_ms": 300,
        "actual_p99_ms": 287,
        "fine_tune_queue_target_h": 4,
        "actual_queue_h": 2.8,
        "status": "ALL_MET",
        "credit_owed": 0.0,
        "monthly_fee": 499.0,
    },
    {
        "id": "apptronik",
        "display_name": "Apptronik",
        "tier": "growth",
        "uptime_target": 99.5,
        "actual_30d_uptime": 99.71,
        "p99_target_ms": 350,
        "actual_p99_ms": 294,
        "fine_tune_queue_target_h": 8,
        "actual_queue_h": 4.2,
        "status": "ALL_MET",
        "credit_owed": 0.0,
        "monthly_fee": 199.0,
    },
    {
        "id": "1x_technologies",
        "display_name": "1X Technologies",
        "tier": "starter",
        "uptime_target": 99.0,
        "actual_30d_uptime": 98.7,
        "p99_target_ms": 500,
        "actual_p99_ms": 301,
        "fine_tune_queue_target_h": 24,
        "actual_queue_h": 6.1,
        "status": "BREACH",
        "breach_reason": "uptime",
        "credit_owed": 14.94,
        "monthly_fee": 49.80,
    },
    {
        "id": "agility_robotics",
        "display_name": "Agility Robotics",
        "tier": "starter",
        "uptime_target": 99.0,
        "actual_30d_uptime": 99.12,
        "p99_target_ms": 500,
        "actual_p99_ms": 348,
        "fine_tune_queue_target_h": 24,
        "actual_queue_h": 8.3,
        "status": "ALL_MET",
        "credit_owed": 0.0,
        "monthly_fee": 49.80,
    },
]

# 3-month uptime history (month-3, month-2, last_month)
UPTIME_HISTORY = {
    "physical_intelligence": [99.82, 99.89, 99.94],
    "apptronik":             [99.41, 99.58, 99.71],
    "1x_technologies":       [98.21, 98.45, 98.70],
    "agility_robotics":      [98.87, 99.01, 99.12],
}

PARTNER_COLORS = {
    "physical_intelligence": "#38bdf8",
    "apptronik":             "#f59e0b",
    "1x_technologies":       "#34d399",
    "agility_robotics":      "#a78bfa",
}

# ---------------------------------------------------------------------------
# SVG Helpers
# ---------------------------------------------------------------------------

def _radar_svg() -> str:
    """SLA compliance radar: 3 axes x 4 partners."""
    W, H = 520, 340
    cx, cy, r = 260, 175, 120

    import math

    # axes: uptime, p99, queue_time  (equally spaced)
    axes = [
        ("Uptime",     0),
        ("P99 Latency", 1),
        ("Queue Time",  2),
    ]
    n = len(axes)
    angles = [math.pi / 2 + i * 2 * math.pi / n for i in range(n)]

    def axis_pt(angle: float, frac: float):
        return (cx + frac * r * math.cos(angle),
                cy - frac * r * math.sin(angle))

    svg_parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'style="background:#1e293b;border-radius:8px;">',
    ]

    # Rings at 25%, 50%, 75%, 100%
    for frac in [0.25, 0.5, 0.75, 1.0]:
        pts = [axis_pt(a, frac) for a in angles]
        pts_str = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        color = "#38bdf8" if frac == 1.0 else "#334155"
        lw = 1.5 if frac == 1.0 else 0.8
        svg_parts.append(
            f'<polygon points="{pts_str}" fill="none" stroke="{color}" stroke-width="{lw}"/>'
        )
        if frac == 1.0:
            x0, y0 = axis_pt(angles[0], frac)
            svg_parts.append(
                f'<text x="{x0+4:.1f}" y="{y0-4:.1f}" fill="#38bdf8" font-size="9" font-family="monospace">target</text>'
            )

    # Axis lines + labels
    for idx, (label, _) in enumerate(axes):
        x1, y1 = axis_pt(angles[idx], 1.0)
        svg_parts.append(
            f'<line x1="{cx}" y1="{cy}" x2="{x1:.1f}" y2="{y1:.1f}" '
            f'stroke="#475569" stroke-width="1"/>'
        )
        lx, ly = axis_pt(angles[idx], 1.18)
        svg_parts.append(
            f'<text x="{lx:.1f}" y="{ly:.1f}" fill="#94a3b8" font-size="11" '
            f'font-family="sans-serif" text-anchor="middle">{label}</text>'
        )

    # Partner polygons
    for p in PARTNERS:
        pid = p["id"]
        color = PARTNER_COLORS[pid]

        # Compute fracs (ratio of actual/target, capped at 1.0)
        uptime_frac = min(p["actual_30d_uptime"] / p["uptime_target"], 1.0)
        # For p99 and queue: lower is better, invert
        p99_frac = min(p["p99_target_ms"] / max(p["actual_p99_ms"], 1), 1.0)
        queue_frac = min(p["fine_tune_queue_target_h"] / max(p["actual_queue_h"], 0.01), 1.0)

        fracs = [uptime_frac, p99_frac, queue_frac]
        pts = [axis_pt(angles[i], fracs[i]) for i in range(n)]
        pts_str = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        svg_parts.append(
            f'<polygon points="{pts_str}" fill="{color}" fill-opacity="0.15" '
            f'stroke="{color}" stroke-width="2"/>'
        )
        for x, y in pts:
            svg_parts.append(
                f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="{color}"/>'
            )

    # Legend
    lx0, ly0 = 10, 290
    svg_parts.append(
        f'<text x="{lx0}" y="{ly0 - 10}" fill="#94a3b8" font-size="10" font-family="sans-serif">Partners:</text>'
    )
    for i, p in enumerate(PARTNERS):
        color = PARTNER_COLORS[p["id"]]
        lx = lx0 + i * 126
        svg_parts.append(
            f'<rect x="{lx}" y="{ly0}" width="12" height="12" fill="{color}" rx="2"/>'
        )
        svg_parts.append(
            f'<text x="{lx + 16}" y="{ly0 + 10}" fill="#e2e8f0" font-size="10" font-family="sans-serif">{p["display_name"]}</text>'
        )

    svg_parts.append("</svg>")
    return "\n".join(svg_parts)


def _credit_bar_svg() -> str:
    """Credit owed bar chart."""
    W, H = 680, 160
    pad_left, pad_right, pad_top, pad_bottom = 160, 40, 20, 40
    chart_w = W - pad_left - pad_right
    chart_h = H - pad_top - pad_bottom

    max_credit = 20.0  # axis max
    n = len(PARTNERS)
    bar_w = chart_w / n * 0.5
    total_credit = sum(p["credit_owed"] for p in PARTNERS)

    svg_parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'style="background:#1e293b;border-radius:8px;">',
    ]

    # Y-axis gridlines
    for frac in [0.25, 0.5, 0.75, 1.0]:
        y = pad_top + chart_h * (1 - frac)
        val = max_credit * frac
        svg_parts.append(
            f'<line x1="{pad_left}" y1="{y:.1f}" x2="{W - pad_right}" y2="{y:.1f}" '
            f'stroke="#334155" stroke-width="0.8" stroke-dasharray="4,3"/>'
        )
        svg_parts.append(
            f'<text x="{pad_left - 8}" y="{y + 4:.1f}" fill="#94a3b8" font-size="10" '
            f'font-family="monospace" text-anchor="end">${val:.0f}</text>'
        )

    # Bars
    for i, p in enumerate(PARTNERS):
        credit = p["credit_owed"]
        color = "#ef4444" if credit > 0 else "#22c55e"
        bar_h = (credit / max_credit) * chart_h if credit > 0 else 4
        bx = pad_left + i * (chart_w / n) + (chart_w / n - bar_w) / 2
        by = pad_top + chart_h - bar_h
        svg_parts.append(
            f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bar_w:.1f}" height="{bar_h:.1f}" '
            f'fill="{color}" rx="3"/>'
        )
        label = f"${credit:.2f}" if credit > 0 else "$0"
        svg_parts.append(
            f'<text x="{bx + bar_w/2:.1f}" y="{by - 5:.1f}" fill="{color}" '
            f'font-size="11" font-family="monospace" text-anchor="middle">{label}</text>'
        )
        svg_parts.append(
            f'<text x="{bx + bar_w/2:.1f}" y="{H - 8}" fill="#94a3b8" '
            f'font-size="10" font-family="sans-serif" text-anchor="middle">{p["display_name"]}</text>'
        )

    # Title + total
    svg_parts.append(
        f'<text x="{pad_left}" y="14" fill="#e2e8f0" font-size="12" font-family="sans-serif" font-weight="bold">Credit Owed (30d)</text>'
    )
    svg_parts.append(
        f'<text x="{W - pad_right}" y="14" fill="#ef4444" font-size="12" font-family="monospace" text-anchor="end">Total: ${total_credit:.2f}</text>'
    )

    svg_parts.append("</svg>")
    return "\n".join(svg_parts)


def _uptime_trend_svg() -> str:
    """Month-over-month uptime trend (3 months)."""
    W, H = 680, 180
    pad_left, pad_right, pad_top, pad_bottom = 60, 140, 20, 40
    chart_w = W - pad_left - pad_right
    chart_h = H - pad_top - pad_bottom

    months = ["2 months ago", "Last month", "This month"]
    y_min, y_max = 97.5, 100.5

    def to_px(month_idx: int, uptime: float):
        x = pad_left + month_idx * chart_w / (len(months) - 1)
        y = pad_top + chart_h * (1 - (uptime - y_min) / (y_max - y_min))
        return x, y

    svg_parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'style="background:#1e293b;border-radius:8px;">',
    ]

    # Gridlines
    for val in [98.0, 98.5, 99.0, 99.5, 100.0]:
        _, y = to_px(0, val)
        svg_parts.append(
            f'<line x1="{pad_left}" y1="{y:.1f}" x2="{W - pad_right}" y2="{y:.1f}" '
            f'stroke="#334155" stroke-width="0.8" stroke-dasharray="4,3"/>'
        )
        svg_parts.append(
            f'<text x="{pad_left - 8}" y="{y + 4:.1f}" fill="#94a3b8" font-size="9" '
            f'font-family="monospace" text-anchor="end">{val:.1f}%</text>'
        )

    # Month labels
    for mi, label in enumerate(months):
        x, _ = to_px(mi, y_min)
        svg_parts.append(
            f'<text x="{x:.1f}" y="{H - 8}" fill="#94a3b8" font-size="10" '
            f'font-family="sans-serif" text-anchor="middle">{label}</text>'
        )

    # Lines per partner
    for p in PARTNERS:
        pid = p["id"]
        color = PARTNER_COLORS[pid]
        history = UPTIME_HISTORY[pid]
        pts = [to_px(i, v) for i, v in enumerate(history)]
        path_d = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        svg_parts.append(
            f'<path d="{path_d}" fill="none" stroke="{color}" stroke-width="2.5"/>'
        )
        for x, y in pts:
            svg_parts.append(
                f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="{color}"/>'
            )

    # Legend
    lx0 = W - pad_right + 10
    for i, p in enumerate(PARTNERS):
        color = PARTNER_COLORS[p["id"]]
        ly = pad_top + i * 22
        svg_parts.append(
            f'<rect x="{lx0}" y="{ly}" width="14" height="14" fill="{color}" rx="2"/>'
        )
        svg_parts.append(
            f'<text x="{lx0 + 18}" y="{ly + 11}" fill="#e2e8f0" font-size="10" font-family="sans-serif">{p["display_name"]}</text>'
        )

    svg_parts.append("</svg>")
    return "\n".join(svg_parts)


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

if FastAPI is None:
    raise RuntimeError("fastapi not installed — run: pip install fastapi uvicorn")

app = FastAPI(title="Partner SLA Tracker", version="1.0.0")


@app.get("/", response_class=HTMLResponse)
def dashboard():
    radar_svg = _radar_svg()
    credit_svg = _credit_bar_svg()
    trend_svg = _uptime_trend_svg()

    breach_count = sum(1 for p in PARTNERS if p["status"] == "BREACH")
    total_credit = sum(p["credit_owed"] for p in PARTNERS)
    all_met = sum(1 for p in PARTNERS if p["status"] == "ALL_MET")

    partner_rows = ""
    for p in PARTNERS:
        status_color = "#ef4444" if p["status"] == "BREACH" else "#22c55e"
        uptime_ok = p["actual_30d_uptime"] >= p["uptime_target"]
        p99_ok = p["actual_p99_ms"] <= p["p99_target_ms"]
        queue_ok = p["actual_queue_h"] <= p["fine_tune_queue_target_h"]
        def cell(ok, val):
            c = "#22c55e" if ok else "#ef4444"
            return f'<td style="color:{c};text-align:right">{val}</td>'
        partner_rows += f"""
        <tr style="border-bottom:1px solid #1e293b">
          <td style="padding:8px 12px;color:#e2e8f0;font-weight:600">{p['display_name']}</td>
          <td style="padding:8px 12px;color:#94a3b8">{p['tier'].upper()}</td>
          {cell(uptime_ok, f"{p['actual_30d_uptime']:.2f}% / {p['uptime_target']:.1f}%")}
          {cell(p99_ok, f"{p['actual_p99_ms']}ms / {p['p99_target_ms']}ms")}
          {cell(queue_ok, f"{p['actual_queue_h']:.1f}h / {p['fine_tune_queue_target_h']}h")}
          <td style="padding:8px 12px;color:{status_color};font-weight:700;text-align:center">{p['status']}</td>
          <td style="padding:8px 12px;color:{'#ef4444' if p['credit_owed'] > 0 else '#22c55e'};text-align:right">${p['credit_owed']:.2f}</td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Partner SLA Tracker — OCI Robot Cloud</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; padding: 24px; }}
    h1 {{ color: #C74634; font-size: 1.6rem; margin-bottom: 4px; }}
    .subtitle {{ color: #64748b; font-size: 0.85rem; margin-bottom: 24px; }}
    .kpis {{ display: flex; gap: 16px; margin-bottom: 28px; flex-wrap: wrap; }}
    .kpi {{ background: #1e293b; border-radius: 8px; padding: 16px 24px; min-width: 160px; }}
    .kpi .val {{ font-size: 2rem; font-weight: 700; font-family: monospace; }}
    .kpi .lbl {{ color: #94a3b8; font-size: 0.8rem; margin-top: 4px; }}
    .section {{ margin-bottom: 32px; }}
    .section h2 {{ color: #38bdf8; font-size: 1rem; margin-bottom: 14px; letter-spacing: 0.05em; text-transform: uppercase; }}
    table {{ width: 100%; border-collapse: collapse; background: #1e293b; border-radius: 8px; overflow: hidden; }}
    th {{ background: #0f172a; color: #94a3b8; font-size: 0.78rem; text-transform: uppercase; padding: 10px 12px; text-align: left; }}
    th:not(:first-child):not(:nth-child(2)) {{ text-align: right; }}
    td {{ padding: 8px 12px; font-size: 0.88rem; }}
    .svgwrap {{ margin-top: 8px; overflow-x: auto; }}
  </style>
</head>
<body>
  <h1>Partner SLA Tracker</h1>
  <div class="subtitle">OCI Robot Cloud · Port 8166 · Updated {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</div>

  <div class="kpis">
    <div class="kpi">
      <div class="val" style="color:#22c55e">{all_met}</div>
      <div class="lbl">Partners — All SLAs Met</div>
    </div>
    <div class="kpi">
      <div class="val" style="color:#ef4444">{breach_count}</div>
      <div class="lbl">Active SLA Breaches</div>
    </div>
    <div class="kpi">
      <div class="val" style="color:#f59e0b">${total_credit:.2f}</div>
      <div class="lbl">Total Credits Owed (30d)</div>
    </div>
    <div class="kpi">
      <div class="val" style="color:#38bdf8">{len(PARTNERS)}</div>
      <div class="lbl">Active Partners</div>
    </div>
  </div>

  <div class="section">
    <h2>Partner SLA Status</h2>
    <table>
      <thead>
        <tr>
          <th>Partner</th><th>Tier</th><th>Uptime (Actual / Target)</th>
          <th>P99 (Actual / Target)</th><th>Queue (Actual / Target)</th>
          <th style="text-align:center">Status</th><th>Credit Owed</th>
        </tr>
      </thead>
      <tbody>{partner_rows}</tbody>
    </table>
  </div>

  <div class="section">
    <h2>SLA Compliance Radar</h2>
    <div class="svgwrap">{radar_svg}</div>
  </div>

  <div class="section">
    <h2>Credit Owed (30-Day)</h2>
    <div class="svgwrap">{credit_svg}</div>
  </div>

  <div class="section">
    <h2>Uptime Trend (3 Months)</h2>
    <div class="svgwrap">{trend_svg}</div>
  </div>
</body>
</html>"""
    return HTMLResponse(content=html)


@app.get("/partners")
def list_partners():
    return JSONResponse(content={"partners": PARTNERS, "total": len(PARTNERS)})


@app.get("/partners/{partner_id}")
def get_partner(partner_id: str):
    for p in PARTNERS:
        if p["id"] == partner_id:
            return JSONResponse(content=p)
    return JSONResponse(status_code=404, content={"error": "Partner not found", "id": partner_id})


@app.get("/breaches")
def list_breaches():
    breaches = [p for p in PARTNERS if p["status"] == "BREACH"]
    return JSONResponse(content={"breaches": breaches, "count": len(breaches)})


@app.get("/credits")
def list_credits():
    credits = [{"id": p["id"], "display_name": p["display_name"],
                "credit_owed": p["credit_owed"], "tier": p["tier"]}
               for p in PARTNERS]
    total = sum(p["credit_owed"] for p in PARTNERS)
    return JSONResponse(content={"credits": credits, "total_owed": total})


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8166)
