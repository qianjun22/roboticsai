"""OCI Robot Cloud — AI World 2026 Demo Readiness Tracker  (port 8173)"""
from __future__ import annotations
import math
import datetime

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
except ImportError as _e:
    raise SystemExit(f"Missing dependency: {_e}.  Run: pip install fastapi uvicorn") from _e

app = FastAPI(title="OCI Robot Cloud — AI World 2026 Prep", version="1.0.0")

# ---------------------------------------------------------------------------
# Static data
# ---------------------------------------------------------------------------

EVENT = {
    "name": "AI World Conference",
    "location": "Boston",
    "date": "September 2026",
    "demo_scenario": "Live GR00T Fine-Tuning on OCI — 30-minute SDG to Deployment",
}

CHECKLIST: dict[str, dict] = {
    "live_inference_service": {
        "status": "READY",
        "tested": True,
        "target": "Done",
        "notes": "Port 8001, 226ms, stable 48h",
        "start": "2026-04-01",
        "end": "2026-04-30",
    },
    "dagger_training_live": {
        "status": "READY",
        "tested": True,
        "target": "Done",
        "notes": "dagger_run10 running, 5% CL \u2192 targeting 65%+",
        "start": "2026-04-01",
        "end": "2026-05-15",
    },
    "genesis_sdg_pipeline": {
        "status": "READY",
        "tested": True,
        "target": "Done",
        "notes": "2000 demos/2.4h pipeline confirmed",
        "start": "2026-04-01",
        "end": "2026-05-01",
    },
    "sdk_installable": {
        "status": "READY",
        "tested": True,
        "target": "Done",
        "notes": "pip install oci-robot-cloud CLI working",
        "start": "2026-04-01",
        "end": "2026-04-20",
    },
    "design_partner_demo": {
        "status": "IN_PROGRESS",
        "tested": False,
        "target": "June 2026",
        "notes": "Need 1 pilot partner with real robot",
        "start": "2026-04-15",
        "end": "2026-06-30",
    },
    "jetson_edge_deploy": {
        "status": "IN_PROGRESS",
        "tested": False,
        "target": "July 2026",
        "notes": "Student model 45ms latency on Orin",
        "start": "2026-05-01",
        "end": "2026-07-31",
    },
    "corl_paper": {
        "status": "IN_PROGRESS",
        "tested": False,
        "target": "September 2026",
        "notes": "CoRL 2026 submission draft complete",
        "start": "2026-06-01",
        "end": "2026-09-01",
    },
    "booth_hardware": {
        "status": "PENDING",
        "tested": False,
        "target": "August 2026",
        "notes": "Franka Panda + workstation needed",
        "start": "2026-07-01",
        "end": "2026-08-31",
    },
}

CRITICAL_PATH = (
    "Critical path: design_partner_demo (June) \u2192 real robot results \u2192 AI World demo credibility"
)

# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------

def _readiness_gauge_svg(score_pct: float) -> str:
    """480x320 semicircle gauge showing readiness percentage."""
    W, H = 480, 320
    CX, CY = 240, 220   # centre of semicircle (near bottom)
    R_OUTER = 170
    R_INNER = 110
    NEEDLE_LEN = 155

    def polar(angle_deg: float, r: float) -> tuple[float, float]:
        """angle_deg: 0=left, 90=top, 180=right (semicircle opening downward)"""
        rad = math.radians(180 - angle_deg)   # 0°=left spoke, 180°=right spoke
        return (CX + r * math.cos(rad), CY - r * math.sin(rad))

    def arc_path(r: float, start_deg: float, end_deg: float) -> str:
        sx, sy = polar(start_deg, r)
        ex, ey = polar(end_deg, r)
        large = 1 if (end_deg - start_deg) > 180 else 0
        return f"M {sx:.1f} {sy:.1f} A {r} {r} 0 {large} 0 {ex:.1f} {ey:.1f}"

    lines: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#0f172a">',
    ]

    # Background arc (full 180°)
    lines.append(f'<path d="{arc_path(R_OUTER, 0, 180)} L {polar(180, R_INNER)[0]:.1f} {polar(180, R_INNER)[1]:.1f} {arc_path(R_INNER, 180, 0)} Z" fill="#1e293b"/>')

    # Coloured fill arc proportional to score
    fill_deg = score_pct / 100.0 * 180.0
    if fill_deg > 1:
        colour = "#22c55e" if score_pct >= 75 else ("#38bdf8" if score_pct >= 40 else "#C74634")
        ox, oy = polar(0, R_OUTER)
        ex_o, ey_o = polar(fill_deg, R_OUTER)
        ix, iy = polar(0, R_INNER)
        ex_i, ey_i = polar(fill_deg, R_INNER)
        large = 1 if fill_deg > 180 else 0
        d = (f"M {ox:.1f} {oy:.1f} A {R_OUTER} {R_OUTER} 0 {large} 0 {ex_o:.1f} {ey_o:.1f} "
             f"L {ex_i:.1f} {ey_i:.1f} A {R_INNER} {R_INNER} 0 {large} 1 {ix:.1f} {iy:.1f} Z")
        lines.append(f'<path d="{d}" fill="{colour}" opacity="0.85"/>')

    # Tick marks at 0, 25, 50, 75, 100 %
    for pct, label in [(0, "0%"), (25, "25%"), (50, "50%"), (75, "75%"), (100, "100%")]:
        deg = pct / 100 * 180
        x1, y1 = polar(deg, R_OUTER + 4)
        x2, y2 = polar(deg, R_OUTER + 16)
        tx, ty = polar(deg, R_OUTER + 28)
        lines.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#64748b" stroke-width="2"/>')
        lines.append(f'<text x="{tx:.1f}" y="{ty:.1f}" fill="#94a3b8" font-size="11" text-anchor="middle" dominant-baseline="middle">{label}</text>')

    # Oracle-red needle
    needle_deg = score_pct / 100 * 180
    nx, ny = polar(needle_deg, NEEDLE_LEN)
    bx1, by1 = polar(needle_deg - 90, 8)
    bx2, by2 = polar(needle_deg + 90, 8)
    lines.append(f'<polygon points="{nx:.1f},{ny:.1f} {bx1:.1f},{by1:.1f} {bx2:.1f},{by2:.1f}" fill="#C74634"/>')
    lines.append(f'<circle cx="{CX}" cy="{CY}" r="10" fill="#C74634"/>')

    # Score text
    lines.append(f'<text x="{CX}" y="{CY - 50}" fill="#f8fafc" font-size="36" font-weight="bold" text-anchor="middle">{score_pct:.0f}%</text>')
    lines.append(f'<text x="{CX}" y="{CY - 20}" fill="#94a3b8" font-size="14" text-anchor="middle">Overall Readiness</text>')

    lines.append("</svg>")
    return "\n".join(lines)


def _gantt_svg() -> str:
    """680x200 Gantt chart Apr–Sep 2026."""
    W, H = 680, 200
    LEFT_MARGIN = 190
    RIGHT_MARGIN = 20
    TOP = 20
    ROW_H = 22
    CHART_W = W - LEFT_MARGIN - RIGHT_MARGIN

    # Timeline: Apr 1 – Sep 30, 2026
    T_START = datetime.date(2026, 4, 1)
    T_END = datetime.date(2026, 9, 30)
    TOTAL_DAYS = (T_END - T_START).days
    TODAY = datetime.date(2026, 3, 30)
    DEMO_DATE = datetime.date(2026, 9, 15)

    def x_for(d: datetime.date) -> float:
        days = max(0, (d - T_START).days)
        return LEFT_MARGIN + (days / TOTAL_DAYS) * CHART_W

    STATUS_COLOR = {"READY": "#22c55e", "IN_PROGRESS": "#38bdf8", "PENDING": "#64748b"}

    items = list(CHECKLIST.items())
    total_h = TOP + len(items) * ROW_H + 40

    lines: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{total_h}" style="background:#0f172a">',
    ]

    # Month labels
    for month_offset, label in enumerate(["Apr", "May", "Jun", "Jul", "Aug", "Sep"]):
        d = datetime.date(2026, 4 + month_offset, 1)
        xm = x_for(d)
        lines.append(f'<text x="{xm:.1f}" y="14" fill="#64748b" font-size="11">{label}</text>')
        lines.append(f'<line x1="{xm:.1f}" y1="18" x2="{xm:.1f}" y2="{total_h - 30}" stroke="#1e293b" stroke-width="1"/>')

    # Rows
    for ri, (key, item) in enumerate(items):
        y = TOP + ri * ROW_H + 6
        bar_y = y + 2
        bar_h = ROW_H - 6
        try:
            start_d = datetime.date.fromisoformat(item["start"])
            end_d = datetime.date.fromisoformat(item["end"])
        except Exception:
            continue
        x1 = x_for(start_d)
        x2 = max(x_for(end_d), x1 + 4)
        colour = STATUS_COLOR.get(item["status"], "#64748b")
        # Label
        short = key.replace("_", " ")
        lines.append(f'<text x="{LEFT_MARGIN - 6}" y="{y + bar_h - 2}" fill="#94a3b8" font-size="11" text-anchor="end">{short}</text>')
        # Bar
        lines.append(f'<rect x="{x1:.1f}" y="{bar_y}" width="{x2 - x1:.1f}" height="{bar_h}" rx="3" fill="{colour}" opacity="0.8"/>')

    # Today line
    if T_START <= TODAY <= T_END:
        xt = x_for(TODAY)
        lines.append(f'<line x1="{xt:.1f}" y1="18" x2="{xt:.1f}" y2="{total_h - 30}" stroke="#fbbf24" stroke-width="1.5" stroke-dasharray="4,3"/>')
        lines.append(f'<text x="{xt + 2:.1f}" y="{total_h - 20}" fill="#fbbf24" font-size="10">Today</text>')

    # Demo target line
    xd = x_for(DEMO_DATE)
    lines.append(f'<line x1="{xd:.1f}" y1="18" x2="{xd:.1f}" y2="{total_h - 30}" stroke="#C74634" stroke-width="2" stroke-dasharray="6,3"/>')
    lines.append(f'<text x="{xd + 2:.1f}" y="{total_h - 20}" fill="#C74634" font-size="10">Demo</text>')

    # Legend
    lx = LEFT_MARGIN
    ly = total_h - 14
    for status, colour in STATUS_COLOR.items():
        lines.append(f'<rect x="{lx}" y="{ly - 9}" width="12" height="9" rx="2" fill="{colour}"/>')
        lines.append(f'<text x="{lx + 15}" y="{ly}" fill="#94a3b8" font-size="10">{status}</text>')
        lx += 100

    lines.append("</svg>")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Dashboard HTML
# ---------------------------------------------------------------------------

def _readiness_score() -> dict:
    total = len(CHECKLIST)
    ready = sum(1 for v in CHECKLIST.values() if v["status"] == "READY")
    in_progress = sum(1 for v in CHECKLIST.values() if v["status"] == "IN_PROGRESS")
    pending = sum(1 for v in CHECKLIST.values() if v["status"] == "PENDING")
    score_pct = round(ready / total * 100, 1)
    return {"ready": ready, "in_progress": in_progress, "pending": pending, "total": total, "score_pct": score_pct}


def _dashboard_html() -> str:
    rs = _readiness_score()
    gauge_svg = _readiness_gauge_svg(rs["score_pct"])
    gantt_svg = _gantt_svg()

    rows_html = ""
    for key, item in CHECKLIST.items():
        colour = {"READY": "#22c55e", "IN_PROGRESS": "#38bdf8", "PENDING": "#64748b"}.get(item["status"], "#64748b")
        tested_badge = "<span style='color:#22c55e;font-size:11px'>\u2713 tested</span>" if item["tested"] else "<span style='color:#64748b;font-size:11px'>\u2014 untested</span>"
        rows_html += f"""
        <tr>
          <td style='padding:7px 10px;font-weight:bold;color:#e2e8f0'>{key.replace('_', ' ')}</td>
          <td><span style='color:{colour};font-weight:bold'>{item['status']}</span></td>
          <td>{tested_badge}</td>
          <td style='color:#64748b;font-size:12px'>{item['target']}</td>
          <td style='color:#94a3b8;font-size:12px'>{item['notes']}</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AI World 2026 — Demo Readiness</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; padding: 24px; }}
  h1 {{ color: #C74634; font-size: 22px; margin-bottom: 4px; }}
  h2 {{ color: #38bdf8; font-size: 15px; margin: 20px 0 10px; }}
  .subtitle {{ color: #64748b; font-size: 13px; margin-bottom: 24px; }}
  .card {{ background: #1e293b; border-radius: 8px; padding: 16px; margin-bottom: 16px; }}
  .event-banner {{ background: linear-gradient(135deg,#1e1a0a,#1a0a07); border: 1px solid #C74634; border-radius: 8px; padding: 14px 20px; margin-bottom: 20px; }}
  .event-title {{ font-size: 17px; font-weight: bold; color: #f8fafc; }}
  .event-meta {{ font-size: 13px; color: #94a3b8; margin-top: 4px; }}
  .demo-scenario {{ color: #38bdf8; font-style: italic; margin-top: 6px; font-size: 13px; }}
  .score-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; align-items: center; }}
  table {{ width: 100%; border-collapse: collapse; }}
  tr {{ border-bottom: 1px solid #334155; }}
  th {{ padding: 7px 10px; text-align: left; color: #64748b; font-size: 12px; background: #0f172a; }}
  .critical-path {{ background: #1a0a07; border-left: 4px solid #C74634; padding: 10px 14px; border-radius: 0 6px 6px 0; color: #fca5a5; font-size: 13px; }}
  .endpoint {{ background: #0f172a; border-left: 3px solid #C74634; padding: 6px 10px; font-size: 12px; color: #94a3b8; margin-bottom: 6px; border-radius: 0 4px 4px 0; }}
  .endpoint span {{ color: #38bdf8; }}
</style>
</head>
<body>
<h1>AI World 2026 — Demo Readiness Tracker</h1>
<p class="subtitle">OCI Robot Cloud &nbsp;\u00b7&nbsp; Port 8173 &nbsp;\u00b7&nbsp; v1.0.0</p>

<div class="event-banner">
  <div class="event-title">{EVENT['name']} &mdash; {EVENT['location']}, {EVENT['date']}</div>
  <div class="event-meta">Overall readiness: <strong style="color:#38bdf8">{rs['ready']}/{rs['total']} items READY</strong></div>
  <div class="demo-scenario">Demo: {EVENT['demo_scenario']}</div>
</div>

<div class="score-grid">
  <div class="card" style="text-align:center">
    {gauge_svg}
  </div>
  <div class="card">
    <h2>Checklist Summary</h2>
    <p style="margin-top:8px;font-size:13px">\u2705 <strong style='color:#22c55e'>{rs['ready']}</strong> READY</p>
    <p style="margin-top:6px;font-size:13px">\u23f3 <strong style='color:#38bdf8'>{rs['in_progress']}</strong> IN PROGRESS</p>
    <p style="margin-top:6px;font-size:13px">\u23f8 <strong style='color:#64748b'>{rs['pending']}</strong> PENDING</p>
    <div style="margin-top:16px" class="critical-path">{CRITICAL_PATH}</div>
  </div>
</div>

<div class="card">
  <h2>Timeline (Apr \u2013 Sep 2026)</h2>
  {gantt_svg}
</div>

<div class="card">
  <h2>Checklist Detail</h2>
  <table>
    <thead><tr><th>Item</th><th>Status</th><th>Test</th><th>Target</th><th>Notes</th></tr></thead>
    <tbody>{rows_html}</tbody>
  </table>
</div>

<div class="card">
  <h2>API Endpoints</h2>
  <div class="endpoint"><span>GET /</span> — This dashboard</div>
  <div class="endpoint"><span>GET /checklist</span> — Full checklist (JSON)</div>
  <div class="endpoint"><span>GET /readiness</span> — Readiness score (JSON)</div>
  <div class="endpoint"><span>GET /critical-path</span> — Critical path statement (JSON)</div>
</div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def dashboard() -> str:
    return _dashboard_html()


@app.get("/checklist")
def get_checklist() -> JSONResponse:
    return JSONResponse(content=CHECKLIST)


@app.get("/readiness")
def get_readiness() -> JSONResponse:
    return JSONResponse(content=_readiness_score())


@app.get("/critical-path")
def get_critical_path() -> JSONResponse:
    return JSONResponse(content={"critical_path": CRITICAL_PATH, "event": EVENT})


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8173)
