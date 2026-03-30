"""NVIDIA Partnership Tracker — FastAPI service on port 8308.

Tracks NVIDIA partnership milestones, co-engineering asks, and
ecosystem integration progress for OCI Robot Cloud.
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    _HAS_FASTAPI = True
except ImportError:
    _HAS_FASTAPI = False

import random
import math
import json
from datetime import datetime

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

MILESTONES = [
    {"id": "Greg_Pavlik_intro",         "status": "IN_PROGRESS", "pct": 40,  "start": "2026-01", "end": "2026-04", "owner": "Jun Qian",   "revenue_k": 0,    "blocker": "Oracle exec path pending"},
    {"id": "Isaac_Sim_optimization",    "status": "DONE",        "pct": 100, "start": "2025-10", "end": "2026-02", "owner": "Eng Team",  "revenue_k": 120,  "blocker": None},
    {"id": "Cosmos_weights_access",     "status": "PLANNED",     "pct": 10,  "start": "2026-04", "end": "2026-07", "owner": "Jun Qian",   "revenue_k": 200,  "blocker": "NVIDIA NDA required"},
    {"id": "GR00T_co_engineering",      "status": "BLOCKED",     "pct": 5,   "start": "2026-05", "end": "2026-10", "owner": "TBD",        "revenue_k": 500,  "blocker": "Need intro via Greg Pavlik"},
    {"id": "NVIDIA_partner_program",    "status": "IN_PROGRESS", "pct": 60,  "start": "2026-01", "end": "2026-05", "owner": "BD Team",   "revenue_k": 80,   "blocker": None},
    {"id": "GTC_2027_talk",             "status": "IN_PROGRESS", "pct": 30,  "start": "2026-06", "end": "2027-03", "owner": "Jun Qian",   "revenue_k": 0,    "blocker": "Proposal drafted; CFP not open"},
    {"id": "joint_eval_suite",          "status": "PLANNED",     "pct": 0,   "start": "2026-08", "end": "2026-12", "owner": "Eng Team",  "revenue_k": 150,  "blocker": "Depends on GR00T co-eng"},
    {"id": "preferred_cloud_agreement", "status": "PLANNED",     "pct": 0,   "start": "2027-01", "end": "2027-06", "owner": "VP Sales",  "revenue_k": 2000, "blocker": "All prior milestones must complete"},
]

ECO_DIMENSIONS = [
    {"name": "Isaac_Sim",   "current": 89, "target": 95},
    {"name": "Cosmos",      "current": 15, "target": 80},
    {"name": "GR00T_N1.6", "current": 72, "target": 90},
    {"name": "Jetson",      "current": 65, "target": 85},
    {"name": "Triton",      "current": 78, "target": 90},
    {"name": "Omniverse",   "current": 30, "target": 75},
]

# ---------------------------------------------------------------------------
# Helper — derived metrics
# ---------------------------------------------------------------------------

def _metrics():
    done = sum(1 for m in MILESTONES if m["status"] == "DONE")
    blocked = sum(1 for m in MILESTONES if m["status"] == "BLOCKED")
    total_revenue = sum(m["revenue_k"] for m in MILESTONES)
    completed_revenue = sum(m["revenue_k"] for m in MILESTONES if m["status"] == "DONE")
    avg_progress = sum(m["pct"] for m in MILESTONES) / len(MILESTONES)
    eco_score = sum(d["current"] for d in ECO_DIMENSIONS) / len(ECO_DIMENSIONS)
    return {
        "milestones_done": done,
        "milestones_total": len(MILESTONES),
        "blocked_count": blocked,
        "avg_progress_pct": round(avg_progress, 1),
        "total_revenue_potential_k": total_revenue,
        "completed_revenue_k": completed_revenue,
        "integration_depth_score": round(eco_score, 1),
    }

# ---------------------------------------------------------------------------
# SVG generators
# ---------------------------------------------------------------------------

STATUS_COLOR = {
    "DONE": "#22c55e",
    "IN_PROGRESS": "#38bdf8",
    "PLANNED": "#94a3b8",
    "BLOCKED": "#ef4444",
}


def _gantt_svg() -> str:
    """Gantt-style milestone progress SVG."""
    W, H = 740, 320
    row_h = 34
    label_w = 220
    bar_area = W - label_w - 20
    # date range: 2025-10 to 2027-06  = 20 months
    MONTHS = 20
    month_w = bar_area / MONTHS

    def month_idx(s: str) -> float:
        y, m = map(int, s.split("-"))
        return (y - 2025) * 12 + (m - 10)

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
        f'<rect width="{W}" height="{H}" fill="#1e293b" rx="8"/>',
        # title
        f'<text x="{W//2}" y="22" text-anchor="middle" fill="#f1f5f9" font-size="13" font-family="monospace" font-weight="bold">Partnership Milestone Gantt</text>',
    ]
    # today marker  (2026-03 = idx 17)
    today_idx = month_idx("2026-03")
    today_x = label_w + today_idx * month_w
    lines.append(f'<line x1="{today_x:.1f}" y1="30" x2="{today_x:.1f}" y2="{H-10}" stroke="#fbbf24" stroke-width="1.5" stroke-dasharray="4,3"/>')
    lines.append(f'<text x="{today_x+3:.1f}" y="42" fill="#fbbf24" font-size="9" font-family="monospace">TODAY</text>')

    for i, ms in enumerate(MILESTONES):
        y_top = 40 + i * row_h
        cy = y_top + row_h // 2
        # label
        label = ms["id"].replace("_", " ")
        lines.append(f'<text x="{label_w - 6}" y="{cy + 4}" text-anchor="end" fill="#cbd5e1" font-size="9" font-family="monospace">{label}</text>')
        # bar background
        s_idx = month_idx(ms["start"])
        e_idx = month_idx(ms["end"])
        bx = label_w + s_idx * month_w
        bw = max(4, (e_idx - s_idx) * month_w)
        lines.append(f'<rect x="{bx:.1f}" y="{y_top+4}" width="{bw:.1f}" height="{row_h-10}" fill="#334155" rx="3"/>')
        # progress fill
        fill_w = bw * ms["pct"] / 100
        color = STATUS_COLOR.get(ms["status"], "#94a3b8")
        lines.append(f'<rect x="{bx:.1f}" y="{y_top+4}" width="{fill_w:.1f}" height="{row_h-10}" fill="{color}" rx="3" opacity="0.85"/>')
        # pct label
        lines.append(f'<text x="{bx + fill_w + 4:.1f}" y="{cy+4}" fill="{color}" font-size="9" font-family="monospace">{ms["pct"]}%</text>')

    # legend
    lx = label_w
    for k, c in STATUS_COLOR.items():
        lines.append(f'<rect x="{lx}" y="{H-18}" width="10" height="10" fill="{c}" rx="2"/>')
        lines.append(f'<text x="{lx+13}" y="{H-8}" fill="#94a3b8" font-size="9" font-family="monospace">{k}</text>')
        lx += 110

    lines.append('</svg>')
    return "\n".join(lines)


def _radar_svg() -> str:
    """Ecosystem integration readiness radar SVG."""
    W, H = 480, 380
    cx, cy = W // 2, H // 2 + 10
    R = 140
    n = len(ECO_DIMENSIONS)
    angles = [math.pi / 2 + 2 * math.pi * i / n for i in range(n)]

    def pt(r, a):
        return cx + r * math.cos(a), cy - r * math.sin(a)

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
        f'<rect width="{W}" height="{H}" fill="#1e293b" rx="8"/>',
        f'<text x="{W//2}" y="22" text-anchor="middle" fill="#f1f5f9" font-size="13" font-family="monospace" font-weight="bold">Ecosystem Integration Readiness</text>',
    ]
    # grid rings
    for ring in [25, 50, 75, 100]:
        pts = " ".join(f"{pt(R * ring/100, a)[0]:.1f},{pt(R * ring/100, a)[1]:.1f}" for a in angles)
        lines.append(f'<polygon points="{pts}" fill="none" stroke="#334155" stroke-width="1"/>')
        lines.append(f'<text x="{cx+4}" y="{cy - R*ring/100 - 2:.1f}" fill="#475569" font-size="8" font-family="monospace">{ring}%</text>')
    # axes
    for a in angles:
        x2, y2 = pt(R, a)
        lines.append(f'<line x1="{cx}" y1="{cy}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#334155" stroke-width="1"/>')
    # target polygon
    tpts = " ".join(f"{pt(R * d['target']/100, a)[0]:.1f},{pt(R * d['target']/100, a)[1]:.1f}" for d, a in zip(ECO_DIMENSIONS, angles))
    lines.append(f'<polygon points="{tpts}" fill="#C74634" fill-opacity="0.12" stroke="#C74634" stroke-width="1.5" stroke-dasharray="5,3"/>')
    # current polygon
    cpts = " ".join(f"{pt(R * d['current']/100, a)[0]:.1f},{pt(R * d['current']/100, a)[1]:.1f}" for d, a in zip(ECO_DIMENSIONS, angles))
    lines.append(f'<polygon points="{cpts}" fill="#38bdf8" fill-opacity="0.25" stroke="#38bdf8" stroke-width="2"/>')
    # dots & labels
    for d, a in zip(ECO_DIMENSIONS, angles):
        x, y = pt(R * d["current"] / 100, a)
        lines.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="#38bdf8"/>')
        lx, ly = pt(R * 1.18, a)
        lines.append(f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="middle" fill="#cbd5e1" font-size="9" font-family="monospace">{d["name"]}</text>')
        lines.append(f'<text x="{lx:.1f}" y="{ly+11:.1f}" text-anchor="middle" fill="#38bdf8" font-size="9" font-family="monospace">{d["current"]}% / {d["target"]}%</text>')
    # legend
    lines.append(f'<rect x="20" y="{H-22}" width="10" height="4" fill="#38bdf8" opacity="0.7"/>')
    lines.append(f'<text x="34" y="{H-16}" fill="#94a3b8" font-size="9" font-family="monospace">Current</text>')
    lines.append(f'<rect x="110" y="{H-22}" width="10" height="4" fill="#C74634" opacity="0.7"/>')
    lines.append(f'<text x="124" y="{H-16}" fill="#94a3b8" font-size="9" font-family="monospace">Target</text>')
    lines.append('</svg>')
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def _html() -> str:
    m = _metrics()
    gantt = _gantt_svg()
    radar = _radar_svg()
    blockers_html = "".join(
        f'<li style="color:#ef4444;margin:4px 0"><b>{ms["id"].replace("_"," ")}:</b> {ms["blocker"]}</li>'
        for ms in MILESTONES if ms["blocker"]
    )
    milestone_rows = "".join(
        f'<tr><td>{ms["id"].replace("_"," ")}</td>'
        f'<td><span style="color:{STATUS_COLOR[ms["status"]]};font-weight:bold">{ms["status"]}</span></td>'
        f'<td>{ms["pct"]}%</td>'
        f'<td>{ms["owner"]}</td>'
        f'<td>${ms["revenue_k"]:,}K</td></tr>'
        for ms in MILESTONES
    )
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<title>NVIDIA Partnership Tracker — Port 8308</title>
<style>
  body{{background:#0f172a;color:#e2e8f0;font-family:monospace;margin:0;padding:20px}}
  h1{{color:#C74634;margin:0 0 4px 0}}  .sub{{color:#94a3b8;font-size:12px;margin-bottom:20px}}
  .kpi-row{{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:20px}}
  .kpi{{background:#1e293b;border:1px solid #334155;border-radius:8px;padding:14px 20px;min-width:140px}}
  .kpi .val{{font-size:28px;font-weight:bold;color:#38bdf8}}
  .kpi .lbl{{font-size:11px;color:#94a3b8;margin-top:2px}}
  .kpi.red .val{{color:#C74634}}
  .section{{background:#1e293b;border:1px solid #334155;border-radius:8px;padding:16px;margin-bottom:18px}}
  h2{{color:#38bdf8;font-size:14px;margin:0 0 12px 0}}
  .charts{{display:flex;gap:16px;flex-wrap:wrap}}
  table{{width:100%;border-collapse:collapse;font-size:12px}}
  th{{color:#94a3b8;text-align:left;padding:6px 8px;border-bottom:1px solid #334155}}
  td{{padding:6px 8px;border-bottom:1px solid #1e293b}}
  ul{{margin:4px 0;padding-left:18px;font-size:12px}}
</style></head><body>
<h1>NVIDIA Partnership Tracker</h1>
<div class="sub">OCI Robot Cloud · Port 8308 · {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC</div>
<div class="kpi-row">
  <div class="kpi"><div class="val">{m['milestones_done']}/{m['milestones_total']}</div><div class="lbl">Milestones Done</div></div>
  <div class="kpi"><div class="val">{m['avg_progress_pct']}%</div><div class="lbl">Avg Progress</div></div>
  <div class="kpi red"><div class="val">{m['blocked_count']}</div><div class="lbl">Blocked Items</div></div>
  <div class="kpi"><div class="val">{m['integration_depth_score']}%</div><div class="lbl">Eco Depth Score</div></div>
  <div class="kpi"><div class="val">${m['total_revenue_potential_k']:,}K</div><div class="lbl">Revenue Potential</div></div>
  <div class="kpi"><div class="val">${m['completed_revenue_k']:,}K</div><div class="lbl">Completed Revenue</div></div>
</div>
<div class="section">
  <h2>Milestone Gantt &amp; Ecosystem Radar</h2>
  <div class="charts">
    <div>{gantt}</div>
    <div>{radar}</div>
  </div>
</div>
<div class="section">
  <h2>Milestone Details</h2>
  <table><tr><th>Milestone</th><th>Status</th><th>Progress</th><th>Owner</th><th>Revenue Potential</th></tr>
  {milestone_rows}
  </table>
</div>
<div class="section">
  <h2>Active Blockers</h2>
  <ul>{blockers_html}</ul>
</div>
</body></html>"""


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

if _HAS_FASTAPI:
    app = FastAPI(title="NVIDIA Partnership Tracker", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return HTMLResponse(content=_html())

    @app.get("/api/metrics")
    def metrics():
        return _metrics()

    @app.get("/api/milestones")
    def milestones():
        return {"milestones": MILESTONES}

    @app.get("/api/ecosystem")
    def ecosystem():
        return {"dimensions": ECO_DIMENSIONS}

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "nvidia_partnership_tracker", "port": 8308}

else:
    # stdlib fallback
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = _html().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            pass


if __name__ == "__main__":
    if _HAS_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8308)
    else:
        print("fastapi not found — starting stdlib http.server on port 8308")
        HTTPServer(("0.0.0.0", 8308), _Handler).serve_forever()
