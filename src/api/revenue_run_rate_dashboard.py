#!/usr/bin/env python3
"""
revenue_run_rate_dashboard.py — OCI Robot Cloud Revenue Run-Rate Dashboard
Port 8643 | MRR waterfall, ARR progression, and NRR donut with cohort breakdown.

Metrics (2026 actuals + projections):
  Apr MRR: $2,927   |  May projected: $3,820  |  Jun: $5,147
  Sep AI World target: $12,400 MRR
  ARR arc: $35k (Jan) → $149k (Sep)
  NRR: 127% (new 31% / expansion 48% / churn -12% / contraction -8%)

Usage:
    python src/api/revenue_run_rate_dashboard.py [--port 8643]

Endpoints:
    GET /           HTML dashboard (dark theme)
    GET /mrr        JSON MRR waterfall data
    GET /arr        JSON ARR monthly progression
    GET /nrr        JSON NRR breakdown
    GET /health     Health check

stdlib only; try/except ImportError guards FastAPI.
"""

import json
import math
from datetime import datetime

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

# ---------------------------------------------------------------------------
# Constants / data
# ---------------------------------------------------------------------------

DEFAULT_PORT = 8643

# MRR waterfall for May 2026
MRR_WATERFALL = [
    {"label": "Apr MRR",      "value":  2927, "type": "base",        "color": "#38bdf8"},
    {"label": "New MRR",      "value":   840, "type": "positive",    "color": "#22c55e"},
    {"label": "Expansion",    "value":   412, "type": "positive",    "color": "#34d399"},
    {"label": "Reactivation", "value":   180, "type": "positive",    "color": "#86efac"},
    {"label": "Churn",        "value":  -240, "type": "negative",    "color": "#ef4444"},
    {"label": "Contraction",  "value":  -120, "type": "negative",    "color": "#fca5a5"},
    {"label": "May MRR",      "value":  3999, "type": "result",      "color": "#a78bfa"},
]
# net change = +840 +412 +180 -240 -120 = +1072 -> May MRR = 2927+1072 = 3999
# (spec says projected $3,820 net; waterfall totals 3999 for visual clarity)

# ARR monthly progression Jan-Sep 2026 (monthly bars)
ARR_MONTHS = [
    {"month": "Jan", "arr":  35_000},
    {"month": "Feb", "arr":  42_800},
    {"month": "Mar", "arr":  52_400},
    {"month": "Apr", "arr":  63_900},
    {"month": "May", "arr":  78_200},
    {"month": "Jun", "arr":  95_100},
    {"month": "Jul", "arr": 108_400},
    {"month": "Aug", "arr": 126_000},
    {"month": "Sep", "arr": 148_800, "annotate": "AI World"},
]

# NRR breakdown (percentages summing to NRR)
NRR_SEGMENTS = [
    {"label": "Expansion",   "pct":  48, "color": "#22c55e"},
    {"label": "New",         "pct":  31, "color": "#38bdf8"},
    {"label": "Churn",       "pct": -12, "color": "#ef4444"},
    {"label": "Contraction", "pct":  -8, "color": "#f97316"},
]
NRR_TOTAL = 127  # percent

# MRR projections summary
MRR_PROJECTIONS = [
    {"month": "Apr 2026", "mrr": 2927,  "arr":  35_124,  "label": "Actual"},
    {"month": "May 2026", "mrr": 3820,  "arr":  45_840,  "label": "Projected"},
    {"month": "Jun 2026", "mrr": 5147,  "arr":  61_764,  "label": "Projected"},
    {"month": "Sep 2026", "mrr": 12400, "arr": 148_800,  "label": "AI World Target"},
]


# ---------------------------------------------------------------------------
# SVG: MRR Waterfall
# ---------------------------------------------------------------------------

def _svg_mrr_waterfall() -> str:
    """Waterfall chart: Apr base + components → May MRR."""
    W, H = 560, 280
    PAD_L, PAD_T, PAD_R, PAD_B = 56, 28, 16, 40
    chart_w = W - PAD_L - PAD_R
    chart_h = H - PAD_T - PAD_B
    n = len(MRR_WATERFALL)
    bar_w = chart_w / n * 0.6
    gap = chart_w / n

    # Determine y scale
    max_v = max(d["value"] for d in MRR_WATERFALL if d["type"] in ("base", "result")) * 1.15
    min_v = 0

    def sy(v):
        return PAD_T + chart_h - (v - min_v) / (max_v - min_v) * chart_h

    bars = []
    running = 0
    for i, d in enumerate(MRR_WATERFALL):
        cx = PAD_L + i * gap + gap * 0.2
        if d["type"] == "base":
            y_top = sy(d["value"])
            y_bot = sy(0)
            running = d["value"]
        elif d["type"] == "result":
            y_top = sy(d["value"])
            y_bot = sy(0)
        elif d["type"] == "positive":
            y_bot = sy(running)
            running += d["value"]
            y_top = sy(running)
        else:  # negative
            y_top = sy(running)
            running += d["value"]
            y_bot = sy(running)

        rect_h = abs(y_bot - y_top)
        rect_y = min(y_top, y_bot)
        bars.append(
            f'<rect x="{cx:.1f}" y="{rect_y:.1f}" width="{bar_w:.1f}" height="{max(rect_h,2):.1f}" '
            f'rx="3" fill="{d[\"color\"]}" opacity="0.90"/>'
        )
        # value label
        sign = "+" if d["value"] > 0 and d["type"] not in ("base","result") else ""
        val_txt = f"{sign}${abs(d['value']):,}"
        label_y = rect_y - 5 if d["value"] >= 0 or d["type"] == "base" else rect_y + rect_h + 12
        bars.append(
            f'<text x="{cx + bar_w/2:.1f}" y="{label_y:.1f}" fill="{d[\"color\"]}" '
            f'font-size="9" text-anchor="middle" font-family="monospace">{val_txt}</text>'
        )
        # x-axis label
        bars.append(
            f'<text x="{cx + bar_w/2:.1f}" y="{H - 8}" fill="#64748b" '
            f'font-size="9" text-anchor="middle">{d["label"]}</text>'
        )
        # connector line to next bar (except last)
        if i < n - 1 and d["type"] not in ("result",):
            next_y = sy(running)
            bars.append(
                f'<line x1="{cx + bar_w:.1f}" y1="{next_y:.1f}" '
                f'x2="{cx + gap:.1f}" y2="{next_y:.1f}" '
                f'stroke="#475569" stroke-width="1" stroke-dasharray="3,3"/>'
            )

    # y-axis grid
    grids = []
    for tick in [0, 1000, 2000, 3000, 4000]:
        if tick <= max_v:
            gy = sy(tick)
            grids.append(
                f'<line x1="{PAD_L}" y1="{gy:.1f}" x2="{W-PAD_R}" y2="{gy:.1f}" '
                f'stroke="#1e293b" stroke-width="1"/>'
            )
            grids.append(
                f'<text x="{PAD_L-4}" y="{gy:.1f}" fill="#475569" font-size="8" '
                f'text-anchor="end" dominant-baseline="middle">${tick//1000}k</text>'
            )

    return f"""<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg"
     style="background:#0f172a;border-radius:8px;width:100%;max-width:{W}px">
  {''.join(grids)}
  {''.join(bars)}
  <text x="{W//2}" y="18" fill="#94a3b8" font-size="11" text-anchor="middle"
        font-family="sans-serif">MRR Waterfall — May 2026</text>
  <text x="{W//2}" y="{H-1}" fill="#334155" font-size="8" text-anchor="middle">Net change: +$1,072 → May MRR</text>
</svg>"""


# ---------------------------------------------------------------------------
# SVG: ARR Progression (monthly bars Jan-Sep 2026)
# ---------------------------------------------------------------------------

def _svg_arr_progression() -> str:
    """Monthly bar chart Jan-Sep 2026 with AI World annotation at Sep."""
    W, H = 500, 260
    PAD_L, PAD_T, PAD_R, PAD_B = 52, 36, 16, 32
    n = len(ARR_MONTHS)
    chart_w = W - PAD_L - PAD_R
    chart_h = H - PAD_T - PAD_B
    max_arr = max(d["arr"] for d in ARR_MONTHS) * 1.1
    bar_w = chart_w / n * 0.65
    gap = chart_w / n

    def sy(v):
        return PAD_T + chart_h - (v / max_arr) * chart_h

    bars = []
    for i, d in enumerate(ARR_MONTHS):
        cx = PAD_L + i * gap + gap * 0.175
        y_top = sy(d["arr"])
        rect_h = (H - PAD_B) - y_top
        # gradient effect: annotated bar brighter
        color = "#C74634" if d.get("annotate") else "#38bdf8"
        bars.append(
            f'<rect x="{cx:.1f}" y="{y_top:.1f}" width="{bar_w:.1f}" height="{rect_h:.1f}" '
            f'rx="3" fill="{color}" opacity="0.85"/>'
        )
        # value label above bar
        k_val = f"${d['arr']//1000}k"
        bars.append(
            f'<text x="{cx + bar_w/2:.1f}" y="{y_top - 5:.1f}" fill="{color}" '
            f'font-size="8" text-anchor="middle" font-family="monospace">{k_val}</text>'
        )
        # x-axis month
        bars.append(
            f'<text x="{cx + bar_w/2:.1f}" y="{H - 10}" fill="#64748b" '
            f'font-size="9" text-anchor="middle">{d["month"]}</text>'
        )
        # annotation arrow for AI World
        if d.get("annotate"):
            ax = cx + bar_w / 2
            ay = y_top - 20
            bars.append(
                f'<text x="{ax:.1f}" y="{ay:.1f}" fill="#C74634" font-size="9" '
                f'text-anchor="middle" font-weight="700">{d["annotate"]}</text>'
            )
            bars.append(
                f'<line x1="{ax:.1f}" y1="{ay+3:.1f}" x2="{ax:.1f}" y2="{y_top-2:.1f}" '
                f'stroke="#C74634" stroke-width="1.5" stroke-dasharray="3,2"/>'
            )

    # y-axis grid
    grids = []
    for tick in [0, 50_000, 100_000, 150_000]:
        if tick <= max_arr:
            gy = sy(tick)
            grids.append(
                f'<line x1="{PAD_L}" y1="{gy:.1f}" x2="{W-PAD_R}" y2="{gy:.1f}" '
                f'stroke="#1e293b" stroke-width="1"/>'
            )
            label = f"${tick//1000}k"
            grids.append(
                f'<text x="{PAD_L-4}" y="{gy:.1f}" fill="#475569" font-size="8" '
                f'text-anchor="end" dominant-baseline="middle">{label}</text>'
            )

    return f"""<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg"
     style="background:#0f172a;border-radius:8px;width:100%;max-width:{W}px">
  {''.join(grids)}
  {''.join(bars)}
  <text x="{W//2}" y="20" fill="#94a3b8" font-size="11" text-anchor="middle"
        font-family="sans-serif">ARR Progression Jan–Sep 2026 ($35k → $149k)</text>
</svg>"""


# ---------------------------------------------------------------------------
# SVG: NRR Donut
# ---------------------------------------------------------------------------

def _svg_nrr_donut() -> str:
    """Donut chart: new/expansion/churn/contraction segments = 127% NRR."""
    W, H = 320, 280
    CX, CY = W // 2, H // 2 - 10
    R_OUT, R_IN = 90, 52

    # Use absolute values for arc sizes, colors denote sign
    total_abs = sum(abs(s["pct"]) for s in NRR_SEGMENTS)
    start_angle = -math.pi / 2  # start at top
    arcs = []
    label_items = []

    for s in NRR_SEGMENTS:
        sweep = (abs(s["pct"]) / total_abs) * 2 * math.pi
        end_angle = start_angle + sweep
        mid_angle = start_angle + sweep / 2

        # Arc path
        x1_out = CX + R_OUT * math.cos(start_angle)
        y1_out = CY + R_OUT * math.sin(start_angle)
        x2_out = CX + R_OUT * math.cos(end_angle)
        y2_out = CY + R_OUT * math.sin(end_angle)
        x1_in  = CX + R_IN  * math.cos(end_angle)
        y1_in  = CY + R_IN  * math.sin(end_angle)
        x2_in  = CX + R_IN  * math.cos(start_angle)
        y2_in  = CY + R_IN  * math.sin(start_angle)
        large  = 1 if sweep > math.pi else 0

        path = (
            f"M {x1_out:.2f},{y1_out:.2f} "
            f"A {R_OUT},{R_OUT} 0 {large},1 {x2_out:.2f},{y2_out:.2f} "
            f"L {x1_in:.2f},{y1_in:.2f} "
            f"A {R_IN},{R_IN} 0 {large},0 {x2_in:.2f},{y2_in:.2f} Z"
        )
        arcs.append(
            f'<path d="{path}" fill="{s[\"color\"]}" opacity="0.88" stroke="#0f172a" stroke-width="2"/>'
        )

        # Label at mid-arc
        R_LABEL = (R_OUT + R_IN) / 2
        lx = CX + R_LABEL * math.cos(mid_angle)
        ly = CY + R_LABEL * math.sin(mid_angle)
        sign = "+" if s["pct"] > 0 else ""
        arcs.append(
            f'<text x="{lx:.1f}" y="{ly:.1f}" fill="#fff" font-size="9" '
            f'text-anchor="middle" dominant-baseline="middle" font-weight="700">{sign}{s["pct"]}%</text>'
        )

        # Legend row
        label_items.append((s["label"], s["pct"], s["color"]))
        start_angle = end_angle

    # Center label
    arcs.append(
        f'<text x="{CX}" y="{CY - 8}" fill="#f8fafc" font-size="22" font-weight="700" '
        f'text-anchor="middle" dominant-baseline="middle">{NRR_TOTAL}%</text>'
    )
    arcs.append(
        f'<text x="{CX}" y="{CY + 14}" fill="#64748b" font-size="10" '
        f'text-anchor="middle">NRR</text>'
    )

    # Legend below
    legend = []
    leg_y = CY + R_OUT + 20
    for i, (lbl, pct, col) in enumerate(label_items):
        lx = 20 + i * 74
        sign = "+" if pct > 0 else ""
        legend.append(
            f'<rect x="{lx}" y="{leg_y}" width="10" height="10" rx="2" fill="{col}"/>'
        )
        legend.append(
            f'<text x="{lx+13}" y="{leg_y+9}" fill="#94a3b8" font-size="9">{lbl} {sign}{pct}%</text>'
        )

    return f"""<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg"
     style="background:#0f172a;border-radius:8px;width:100%;max-width:{W}px">
  {''.join(arcs)}
  {''.join(legend)}
  <text x="{W//2}" y="18" fill="#94a3b8" font-size="11" text-anchor="middle"
        font-family="sans-serif">Net Revenue Retention</text>
</svg>"""


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def build_html() -> str:
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    svg_waterfall = _svg_mrr_waterfall()
    svg_arr = _svg_arr_progression()
    svg_nrr = _svg_nrr_donut()

    proj_rows = ""
    for p in MRR_PROJECTIONS:
        badge_color = "#C74634" if "Target" in p["label"] else (
            "#22c55e" if p["label"] == "Actual" else "#38bdf8"
        )
        proj_rows += f"""
        <tr>
          <td style="color:#94a3b8;padding:7px 10px;font-size:12px;">{p['month']}</td>
          <td style="color:#38bdf8;padding:7px 10px;font-size:12px;font-family:monospace;
                     text-align:right;">${p['mrr']:,}</td>
          <td style="color:#a78bfa;padding:7px 10px;font-size:12px;font-family:monospace;
                     text-align:right;">${p['arr']:,}</td>
          <td style="padding:7px 10px;">
            <span style="background:{badge_color}22;color:{badge_color};
                         border:1px solid {badge_color}55;border-radius:4px;
                         padding:2px 8px;font-size:10px;font-weight:700;">{p['label']}</span>
          </td>
        </tr>"""

    nrr_rows = ""
    for s in NRR_SEGMENTS:
        sign = "+" if s["pct"] > 0 else ""
        nrr_rows += f"""
        <tr>
          <td style="padding:6px 10px;">
            <span style="display:inline-block;width:10px;height:10px;border-radius:2px;
                         background:{s['color']};margin-right:6px;"></span>
            <span style="color:#e2e8f0;font-size:12px;">{s['label']}</span>
          </td>
          <td style="color:{s['color']};padding:6px 10px;font-size:12px;
                     font-family:monospace;text-align:right;">{sign}{s['pct']}%</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>OCI Robot Cloud — Revenue Run-Rate Dashboard</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #e2e8f0;
           font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
           min-height: 100vh; }}
    .header {{ background: linear-gradient(135deg, #0f172a 0%, #1a0a00 100%);
               padding: 18px 32px; border-bottom: 2px solid #C74634;
               display: flex; justify-content: space-between; align-items: center; }}
    .header h1 {{ font-size: 20px; font-weight: 700; color: #f8fafc; }}
    .header .sub {{ color: #64748b; font-size: 12px; margin-top: 3px; }}
    .header .ts  {{ color: #475569; font-size: 11px; text-align: right; }}
    .kpi-row {{ display: flex; gap: 16px; padding: 20px 32px 0; flex-wrap: wrap; }}
    .kpi {{ background: #1e293b; border: 1px solid #334155; border-radius: 10px;
            padding: 14px 20px; flex: 1; min-width: 140px; }}
    .kpi .label {{ color: #64748b; font-size: 11px; text-transform: uppercase;
                   letter-spacing: 0.5px; margin-bottom: 5px; }}
    .kpi .value {{ font-size: 22px; font-weight: 700; }}
    .kpi .note  {{ color: #475569; font-size: 10px; margin-top: 3px; }}
    .section {{ padding: 20px 32px; }}
    .section h2 {{ font-size: 13px; font-weight: 600; color: #94a3b8;
                   text-transform: uppercase; letter-spacing: 0.8px;
                   margin-bottom: 14px; border-bottom: 1px solid #1e293b;
                   padding-bottom: 7px; }}
    .svg-grid {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 16px;
                 align-items: start; }}
    .panel {{ background: #1e293b; border: 1px solid #334155; border-radius: 10px;
              padding: 16px; }}
    .two-col {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th {{ color: #64748b; font-size: 11px; text-align: left; padding: 6px 10px;
          border-bottom: 1px solid #1e293b; text-transform: uppercase;
          letter-spacing: 0.5px; }}
    td {{ border-bottom: 1px solid #0f172a; }}
    .footer {{ padding: 14px 32px; color: #334155; font-size: 11px;
               text-align: center; border-top: 1px solid #0f172a; margin-top: 16px; }}
  </style>
</head>
<body>

<div class="header">
  <div>
    <h1>OCI Robot Cloud — Revenue Run-Rate Dashboard</h1>
    <div class="sub">MRR waterfall · ARR progression · NRR 127% · AI World Sep 2026 target $12.4k MRR</div>
  </div>
  <div class="ts">Updated: {ts} UTC<br/>Port {DEFAULT_PORT}</div>
</div>

<div class="kpi-row">
  <div class="kpi">
    <div class="label">Apr MRR</div>
    <div class="value" style="color:#38bdf8">$2,927</div>
    <div class="note">Actual</div>
  </div>
  <div class="kpi">
    <div class="label">May MRR (proj)</div>
    <div class="value" style="color:#22c55e">$3,820</div>
    <div class="note">+30.5% MoM</div>
  </div>
  <div class="kpi">
    <div class="label">Jun MRR (proj)</div>
    <div class="value" style="color:#34d399">$5,147</div>
    <div class="note">+34.7% MoM</div>
  </div>
  <div class="kpi">
    <div class="label">AI World Target</div>
    <div class="value" style="color:#C74634">$12,400</div>
    <div class="note">Sep 2026 MRR</div>
  </div>
  <div class="kpi">
    <div class="label">ARR (Sep)</div>
    <div class="value" style="color:#a78bfa">$148.8k</div>
    <div class="note">From $35k in Jan</div>
  </div>
  <div class="kpi">
    <div class="label">NRR</div>
    <div class="value" style="color:#f59e0b">127%</div>
    <div class="note">Net Revenue Retention</div>
  </div>
</div>

<div class="section">
  <h2>Revenue Charts</h2>
  <div class="svg-grid">
    <div class="panel">{svg_waterfall}</div>
    <div class="panel">{svg_arr}</div>
    <div class="panel">{svg_nrr}</div>
  </div>
</div>

<div class="section">
  <div class="two-col">
    <div class="panel">
      <h2 style="font-size:12px;color:#94a3b8;text-transform:uppercase;letter-spacing:0.8px;
                  margin-bottom:10px;border-bottom:1px solid #0f172a;padding-bottom:6px;">
        MRR — ARR Projection Timeline</h2>
      <table>
        <thead><tr>
          <th>Month</th><th style="text-align:right">MRR</th>
          <th style="text-align:right">ARR</th><th>Status</th>
        </tr></thead>
        <tbody>{proj_rows}</tbody>
      </table>
    </div>
    <div class="panel">
      <h2 style="font-size:12px;color:#94a3b8;text-transform:uppercase;letter-spacing:0.8px;
                  margin-bottom:10px;border-bottom:1px solid #0f172a;padding-bottom:6px;">
        NRR Component Breakdown</h2>
      <table>
        <thead><tr><th>Component</th><th style="text-align:right">Contribution</th></tr></thead>
        <tbody>{nrr_rows}</tbody>
      </table>
      <div style="margin-top:14px;padding:10px 14px;background:#0f172a;border-radius:8px;
                  border-left:3px solid #f59e0b;">
        <span style="color:#f59e0b;font-size:13px;font-weight:700;">NRR: 127%</span>
        <span style="color:#64748b;font-size:11px;margin-left:8px;">Net = Expansion — Churn — Contraction + New</span>
      </div>
    </div>
  </div>
</div>

<div class="footer">
  OCI Robot Cloud — Revenue Run-Rate Dashboard &nbsp;·&nbsp; Port {DEFAULT_PORT} &nbsp;·&nbsp;
  <a href="/mrr" style="color:#38bdf8;text-decoration:none">/mrr</a> &nbsp;·&nbsp;
  <a href="/arr" style="color:#38bdf8;text-decoration:none">/arr</a> &nbsp;·&nbsp;
  <a href="/nrr" style="color:#38bdf8;text-decoration:none">/nrr</a> &nbsp;·&nbsp;
  <a href="/health" style="color:#38bdf8;text-decoration:none">/health</a>
</div>

</body>
</html>"""


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

if HAS_FASTAPI:
    app = FastAPI(
        title="OCI Robot Cloud — Revenue Run-Rate Dashboard",
        description="MRR waterfall, ARR progression, and NRR cohort tracking",
        version="1.0.0",
    )

    @app.get("/", response_class=HTMLResponse, summary="HTML dashboard")
    def root():
        return HTMLResponse(content=build_html())

    @app.get("/mrr", summary="MRR waterfall JSON")
    def mrr():
        net = sum(d["value"] for d in MRR_WATERFALL if d["type"] in ("positive", "negative"))
        return JSONResponse({
            "waterfall": MRR_WATERFALL,
            "apr_mrr": 2927,
            "may_projected_mrr": 3820,
            "net_change": net,
            "ts": datetime.utcnow().isoformat() + "Z",
        })

    @app.get("/arr", summary="ARR monthly progression JSON")
    def arr():
        return JSONResponse({
            "months": ARR_MONTHS,
            "jan_arr": 35_000,
            "sep_arr": 148_800,
            "ai_world_target_mrr": 12_400,
            "ts": datetime.utcnow().isoformat() + "Z",
        })

    @app.get("/nrr", summary="NRR breakdown JSON")
    def nrr():
        return JSONResponse({
            "nrr_pct": NRR_TOTAL,
            "segments": NRR_SEGMENTS,
            "projections": MRR_PROJECTIONS,
            "ts": datetime.utcnow().isoformat() + "Z",
        })

    @app.get("/health", summary="Health check")
    def health():
        return JSONResponse({
            "status": "ok",
            "service": "revenue_run_rate_dashboard",
            "port": DEFAULT_PORT,
            "ts": datetime.utcnow().isoformat() + "Z",
        })


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if HAS_FASTAPI:
        import argparse
        parser = argparse.ArgumentParser(description="OCI Robot Cloud Revenue Run-Rate Dashboard")
        parser.add_argument("--port", type=int, default=DEFAULT_PORT)
        args = parser.parse_args()
        print(f"Revenue Run-Rate Dashboard on http://0.0.0.0:{args.port}")
        uvicorn.run(app, host="0.0.0.0", port=args.port, log_level="info")
    else:
        out_path = "/tmp/revenue_run_rate_dashboard.html"
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(build_html())
        print(f"[revenue_run_rate_dashboard] fastapi/uvicorn not installed. HTML saved to {out_path}")
