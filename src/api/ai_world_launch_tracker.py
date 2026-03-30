"""AI World 2026 Launch Tracker — FastAPI service on port 8278.

Tracks all launch readiness items for AI World 2026 demo (September 2026).
Dashboard: dark theme with Oracle red #C74634, sky blue #38bdf8.
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    _HAS_FASTAPI = True
except ImportError:
    _HAS_FASTAPI = False

import math
import random
import json
from datetime import datetime, date

# ---------------------------------------------------------------------------
# Mock Data
# ---------------------------------------------------------------------------

LAUNCH_ITEMS = [
    {"id": 1,  "name": "GR00T N1.6 Inference Server",   "owner": "Jun Qian",     "start": "2026-04-01", "end": "2026-05-15", "status": "DONE",        "pillar": "technical"},
    {"id": 2,  "name": "Isaac Sim SDG Pipeline",         "owner": "Jun Qian",     "start": "2026-04-10", "end": "2026-05-30", "status": "DONE",        "pillar": "technical"},
    {"id": 3,  "name": "Fine-Tuning API (port 8001)",    "owner": "Eng Team",     "start": "2026-05-01", "end": "2026-06-15", "status": "DONE",        "pillar": "technical"},
    {"id": 4,  "name": "Design Partner Pilot: Machina",  "owner": "Biz Dev",      "start": "2026-05-15", "end": "2026-07-31", "status": "IN_PROGRESS", "pillar": "customer"},
    {"id": 5,  "name": "NVIDIA Partnership Agreement",  "owner": "Legal/BD",     "start": "2026-05-01", "end": "2026-08-01", "status": "BLOCKED",     "pillar": "partnerships"},
    {"id": 6,  "name": "Demo Robot Hardware Confirmed", "owner": "Ops",           "start": "2026-06-01", "end": "2026-06-30", "status": "DONE",        "pillar": "operations"},
    {"id": 7,  "name": "Legal Review — Cloud ToS",       "owner": "Legal",         "start": "2026-06-15", "end": "2026-08-15", "status": "BLOCKED",     "pillar": "partnerships"},
    {"id": 8,  "name": "Press Kit & Media Assets",       "owner": "Marketing",    "start": "2026-07-01", "end": "2026-09-01", "status": "BLOCKED",     "pillar": "content"},
    {"id": 9,  "name": "Customer Beta Onboarding",       "owner": "Biz Dev",      "start": "2026-07-15", "end": "2026-08-31", "status": "IN_PROGRESS", "pillar": "customer"},
    {"id": 10, "name": "Multi-GPU DDP Validation",       "owner": "Eng Team",     "start": "2026-07-01", "end": "2026-08-01", "status": "IN_PROGRESS", "pillar": "technical"},
    {"id": 11, "name": "AI World Demo Script & Rehearsal","owner": "Jun Qian",    "start": "2026-08-01", "end": "2026-09-10", "status": "PLANNED",     "pillar": "content"},
    {"id": 12, "name": "Go/No-Go Review",                "owner": "Leadership",   "start": "2026-09-05", "end": "2026-09-15", "status": "PLANNED",     "pillar": "operations"},
]

PILLAR_SCORES = {
    "technical":    71,
    "partnerships":  45,
    "customer":      60,
    "content":       55,
    "operations":    80,
}

OVERALL_READINESS = 62

STATUS_COLORS = {
    "DONE":        "#22c55e",
    "IN_PROGRESS": "#38bdf8",
    "BLOCKED":     "#C74634",
    "PLANNED":     "#64748b",
}

# Date helpers
def _days_from_epoch(d_str: str) -> int:
    """Days from 2026-04-01 for SVG x-positioning."""
    base = date(2026, 4, 1)
    d = date.fromisoformat(d_str)
    return (d - base).days

TOTAL_DAYS = (date(2026, 9, 30) - date(2026, 4, 1)).days  # ~182


# ---------------------------------------------------------------------------
# SVG 1 — Gantt Chart
# ---------------------------------------------------------------------------

def build_gantt_svg() -> str:
    W, H = 820, 420
    left_margin = 200
    chart_w = W - left_margin - 20
    row_h = 28
    top_margin = 40

    # Month labels
    months = [("Apr", 0), ("May", 30), ("Jun", 61), ("Jul", 91), ("Aug", 122), ("Sep", 153)]

    lines = []
    lines.append(f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg" style="background:#1e293b;border-radius:8px">')

    # Title
    lines.append(f'<text x="{W//2}" y="22" text-anchor="middle" fill="#f1f5f9" font-size="13" font-family="monospace" font-weight="bold">AI World 2026 — Launch Gantt</text>')

    # Month grid lines + labels
    for label, day in months:
        x = left_margin + int(day / TOTAL_DAYS * chart_w)
        lines.append(f'<line x1="{x}" y1="30" x2="{x}" y2="{H-10}" stroke="#334155" stroke-width="1" stroke-dasharray="4,3"/>')
        lines.append(f'<text x="{x+3}" y="38" fill="#94a3b8" font-size="10" font-family="monospace">{label}</text>')

    # Rows
    for i, item in enumerate(LAUNCH_ITEMS):
        y = top_margin + i * row_h + 10
        x_start = left_margin + int(_days_from_epoch(item["start"]) / TOTAL_DAYS * chart_w)
        x_end   = left_margin + int(_days_from_epoch(item["end"])   / TOTAL_DAYS * chart_w)
        bar_w   = max(x_end - x_start, 6)
        color   = STATUS_COLORS[item["status"]]

        # Row label
        lines.append(f'<text x="{left_margin - 5}" y="{y+12}" text-anchor="end" fill="#cbd5e1" font-size="9" font-family="monospace">{item["name"][:28]}</text>')

        # Critical path highlight (BLOCKED items)
        if item["status"] == "BLOCKED":
            lines.append(f'<rect x="{x_start-2}" y="{y-2}" width="{bar_w+4}" height="18" fill="none" stroke="#C74634" stroke-width="2" rx="3" opacity="0.7"/>')

        # Bar
        lines.append(f'<rect x="{x_start}" y="{y}" width="{bar_w}" height="14" fill="{color}" rx="3" opacity="0.85"/>')

        # Status badge
        badge = item["status"][0]  # D/I/B/P
        lines.append(f'<text x="{x_start + bar_w + 4}" y="{y+11}" fill="{color}" font-size="8" font-family="monospace">{badge}</text>')

    # Today line
    today_day = (date(2026, 3, 30) - date(2026, 4, 1)).days  # slightly before Apr 1
    today_x = left_margin + max(0, int(today_day / TOTAL_DAYS * chart_w))
    lines.append(f'<line x1="{left_margin}" y1="30" x2="{left_margin}" y2="{H-10}" stroke="#fbbf24" stroke-width="2" stroke-dasharray="6,4"/>')
    lines.append(f'<text x="{left_margin+2}" y="{H-2}" fill="#fbbf24" font-size="9" font-family="monospace">Today</text>')

    # Legend
    lx = left_margin
    ly = H - 22
    for status, col in STATUS_COLORS.items():
        lines.append(f'<rect x="{lx}" y="{ly}" width="10" height="10" fill="{col}" rx="2"/>')
        lines.append(f'<text x="{lx+13}" y="{ly+9}" fill="#94a3b8" font-size="9" font-family="monospace">{status}</text>')
        lx += 110

    lines.append('</svg>')
    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# SVG 2 — Readiness Gauge + Pillar Bars
# ---------------------------------------------------------------------------

def build_gauge_svg() -> str:
    W, H = 820, 320
    cx, cy, r = 200, 180, 130

    lines = []
    lines.append(f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg" style="background:#1e293b;border-radius:8px">')
    lines.append(f'<text x="{W//2}" y="22" text-anchor="middle" fill="#f1f5f9" font-size="13" font-family="monospace" font-weight="bold">Launch Readiness Score &amp; Pillar Breakdown</text>')

    # Semicircle background (grey track)
    def arc_path(cx, cy, r, start_deg, end_deg):
        import math
        s = math.radians(start_deg)
        e = math.radians(end_deg)
        x1 = cx + r * math.cos(s)
        y1 = cy + r * math.sin(s)
        x2 = cx + r * math.cos(e)
        y2 = cy + r * math.sin(e)
        large = 1 if (end_deg - start_deg) > 180 else 0
        return f"M {x1:.1f} {y1:.1f} A {r} {r} 0 {large} 1 {x2:.1f} {y2:.1f}"

    # Track (180° semi-circle from 180 to 0)
    lines.append(f'<path d="{arc_path(cx, cy, r, 180, 360)}" fill="none" stroke="#334155" stroke-width="22" stroke-linecap="round"/>')

    # Score arc (0-100 mapped to 180 degrees)
    score_deg = 180 + (OVERALL_READINESS / 100) * 180
    arc_color = "#22c55e" if OVERALL_READINESS >= 75 else ("#fbbf24" if OVERALL_READINESS >= 50 else "#C74634")
    lines.append(f'<path d="{arc_path(cx, cy, r, 180, score_deg)}" fill="none" stroke="{arc_color}" stroke-width="22" stroke-linecap="round"/>')

    # Score text
    lines.append(f'<text x="{cx}" y="{cy+10}" text-anchor="middle" fill="{arc_color}" font-size="36" font-family="monospace" font-weight="bold">{OVERALL_READINESS}%</text>')
    lines.append(f'<text x="{cx}" y="{cy+32}" text-anchor="middle" fill="#94a3b8" font-size="11" font-family="monospace">Overall Readiness</text>')

    # WoW delta
    delta = "+3% WoW"
    lines.append(f'<text x="{cx}" y="{cy+52}" text-anchor="middle" fill="#38bdf8" font-size="10" font-family="monospace">{delta}</text>')

    # Needle
    needle_angle = math.radians(180 + (OVERALL_READINESS / 100) * 180)
    nx = cx + (r - 25) * math.cos(needle_angle)
    ny = cy + (r - 25) * math.sin(needle_angle)
    lines.append(f'<line x1="{cx}" y1="{cy}" x2="{nx:.1f}" y2="{ny:.1f}" stroke="#f1f5f9" stroke-width="3" stroke-linecap="round"/>')
    lines.append(f'<circle cx="{cx}" cy="{cy}" r="6" fill="#f1f5f9"/>')

    # Pillar bars (right side)
    bx = 420
    bar_max_w = 330
    row_h = 42
    pillars = list(PILLAR_SCORES.items())
    for i, (pillar, score) in enumerate(pillars):
        by = 55 + i * row_h
        bar_w = int(score / 100 * bar_max_w)
        col = "#22c55e" if score >= 70 else ("#fbbf24" if score >= 55 else "#C74634")
        # Label
        lines.append(f'<text x="{bx}" y="{by+13}" fill="#cbd5e1" font-size="11" font-family="monospace">{pillar.capitalize()}</text>')
        # Track
        lines.append(f'<rect x="{bx}" y="{by+18}" width="{bar_max_w}" height="14" fill="#334155" rx="4"/>')
        # Bar
        lines.append(f'<rect x="{bx}" y="{by+18}" width="{bar_w}" height="14" fill="{col}" rx="4" opacity="0.85"/>')
        # Value
        lines.append(f'<text x="{bx+bar_w+6}" y="{by+30}" fill="{col}" font-size="11" font-family="monospace">{score}%</text>')

    # Blocked note
    lines.append(f'<text x="{bx}" y="{H-30}" fill="#C74634" font-size="10" font-family="monospace">⚠ 3 BLOCKED items: NVIDIA meeting / Legal ToS / Press Kit</text>')
    lines.append(f'<text x="{bx}" y="{H-14}" fill="#94a3b8" font-size="10" font-family="monospace">Go/No-Go Decision: Sep 5 2026 | Critical path: partnerships track</text>')

    lines.append('</svg>')
    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# HTML Dashboard
# ---------------------------------------------------------------------------

def build_html() -> str:
    gantt = build_gantt_svg()
    gauge = build_gauge_svg()

    blocked = [i for i in LAUNCH_ITEMS if i["status"] == "BLOCKED"]
    in_prog = [i for i in LAUNCH_ITEMS if i["status"] == "IN_PROGRESS"]
    done    = [i for i in LAUNCH_ITEMS if i["status"] == "DONE"]

    blocked_rows = "".join(
        f'<tr><td style="color:#C74634">{b["name"]}</td><td>{b["owner"]}</td>'
        f'<td style="color:#fbbf24">{b["end"]}</td>'
        f'<td style="color:#C74634">BLOCKED</td></tr>'
        for b in blocked
    )

    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>AI World 2026 Launch Tracker — Port 8278</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #f1f5f9; font-family: 'Courier New', monospace; padding: 24px; }}
    h1 {{ color: #C74634; font-size: 22px; margin-bottom: 4px; }}
    .subtitle {{ color: #94a3b8; font-size: 12px; margin-bottom: 20px; }}
    .kpi-row {{ display: flex; gap: 16px; margin-bottom: 24px; flex-wrap: wrap; }}
    .kpi {{ background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 14px 20px; min-width: 160px; }}
    .kpi .val {{ font-size: 26px; font-weight: bold; }}
    .kpi .lbl {{ font-size: 10px; color: #64748b; margin-top: 4px; }}
    .section {{ margin-bottom: 28px; }}
    .section h2 {{ color: #38bdf8; font-size: 13px; margin-bottom: 12px; border-bottom: 1px solid #1e293b; padding-bottom: 6px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 11px; }}
    th {{ background: #1e293b; color: #94a3b8; padding: 8px 10px; text-align: left; }}
    td {{ padding: 7px 10px; border-bottom: 1px solid #1e293b; }}
    tr:hover td {{ background: #1e293b44; }}
    .badge-blocked {{ color: #C74634; font-weight: bold; }}
    .badge-done {{ color: #22c55e; }}
    .badge-in-progress {{ color: #38bdf8; }}
    footer {{ margin-top: 32px; color: #334155; font-size: 10px; text-align: center; }}
  </style>
</head>
<body>
  <h1>AI World 2026 Launch Tracker</h1>
  <div class="subtitle">Port 8278 &nbsp;|&nbsp; Event: September 2026 &nbsp;|&nbsp; Last refresh: 2026-03-30</div>

  <div class="kpi-row">
    <div class="kpi"><div class="val" style="color:#fbbf24">{OVERALL_READINESS}%</div><div class="lbl">Overall Readiness</div></div>
    <div class="kpi"><div class="val" style="color:#22c55e">{len(done)}</div><div class="lbl">Items DONE</div></div>
    <div class="kpi"><div class="val" style="color:#38bdf8">{len(in_prog)}</div><div class="lbl">IN PROGRESS</div></div>
    <div class="kpi"><div class="val" style="color:#C74634">{len(blocked)}</div><div class="lbl">BLOCKED</div></div>
    <div class="kpi"><div class="val" style="color:#C74634">Sep 5</div><div class="lbl">Go/No-Go Date</div></div>
    <div class="kpi"><div class="val" style="color:#94a3b8">+3%</div><div class="lbl">Readiness Δ WoW</div></div>
  </div>

  <div class="section">
    <h2>Launch Gantt — Critical Path</h2>
    {gantt}
  </div>

  <div class="section">
    <h2>Readiness Score — Gauge &amp; Pillar Breakdown</h2>
    {gauge}
  </div>

  <div class="section">
    <h2>BLOCKED Items — Resolution Required</h2>
    <table>
      <thead><tr><th>Item</th><th>Owner</th><th>Target Date</th><th>Status</th></tr></thead>
      <tbody>{blocked_rows}</tbody>
    </table>
  </div>

  <footer>OCI Robot Cloud &nbsp;|&nbsp; AI World 2026 &nbsp;|&nbsp; Powered by FastAPI + stdlib &nbsp;|&nbsp; Port 8278</footer>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# FastAPI App / stdlib fallback
# ---------------------------------------------------------------------------

if _HAS_FASTAPI:
    app = FastAPI(title="AI World Launch Tracker", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return HTMLResponse(content=build_html())

    @app.get("/api/status")
    async def api_status():
        return {
            "service": "ai_world_launch_tracker",
            "port": 8278,
            "overall_readiness_pct": OVERALL_READINESS,
            "items_total": len(LAUNCH_ITEMS),
            "items_done": len([i for i in LAUNCH_ITEMS if i["status"] == "DONE"]),
            "items_blocked": len([i for i in LAUNCH_ITEMS if i["status"] == "BLOCKED"]),
            "items_in_progress": len([i for i in LAUNCH_ITEMS if i["status"] == "IN_PROGRESS"]),
            "pillar_scores": PILLAR_SCORES,
            "go_no_go_date": "2026-09-05",
            "wow_delta_pct": 3,
        }

    @app.get("/api/items")
    async def api_items():
        return {"items": LAUNCH_ITEMS}

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "ai_world_launch_tracker", "port": 8278}

else:
    # stdlib fallback
    from http.server import HTTPServer, BaseHTTPRequestHandler

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = build_html().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            pass

    def _run_stdlib():
        srv = HTTPServer(("", 8278), _Handler)
        print("AI World Launch Tracker (stdlib fallback) running on http://0.0.0.0:8278")
        srv.serve_forever()


if __name__ == "__main__":
    if _HAS_FASTAPI:
        uvicorn.run("ai_world_launch_tracker:app", host="0.0.0.0", port=8278, reload=False)
    else:
        _run_stdlib()
