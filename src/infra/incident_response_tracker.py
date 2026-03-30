#!/usr/bin/env python3
"""
Incident Response Tracker — OCI Robot Cloud
FastAPI service on port 8298
Tracks production incidents, RCA completion, and post-mortem action items.
"""

import random
import math
import json
from datetime import datetime, timedelta

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

INCIDENTS = [
    # P1s
    {"id": "INC-001", "severity": "P1", "title": "Latency Spike — Inference API",
     "date": "2026-01-14", "status": "RESOLVED", "mttr_min": 47,
     "affected_partners": ["PartnerA", "PartnerC"],
     "sla_breach_hours": {"PartnerA": 0.4, "PartnerC": 0.6},
     "root_cause": "GPU memory pressure during concurrent batch requests",
     "action_items": 3, "open_actions": 0},
    {"id": "INC-007", "severity": "P1", "title": "Sync Failure — Data Pipeline",
     "date": "2026-02-03", "status": "RESOLVED", "mttr_min": 138,
     "affected_partners": ["PartnerB", "PartnerD", "PartnerE"],
     "sla_breach_hours": {"PartnerB": 1.8, "PartnerD": 2.1, "PartnerE": 1.5},
     "root_cause": "Sync lag from upstream schema change",
     "action_items": 5, "open_actions": 1},
    {"id": "INC-019", "severity": "P1", "title": "OOM Event — Training Worker",
     "date": "2026-03-21", "status": "RESOLVED", "mttr_min": 18,
     "affected_partners": ["PartnerA"],
     "sla_breach_hours": {"PartnerA": 0.1},
     "root_cause": "Dataset batch size misconfiguration after config update",
     "action_items": 2, "open_actions": 0},
    # P2s (7)
    {"id": "INC-002", "severity": "P2", "title": "Model Checkpoint Load Timeout",
     "date": "2026-01-19", "status": "RESOLVED", "mttr_min": 24,
     "affected_partners": ["PartnerA"],
     "sla_breach_hours": {"PartnerA": 0.0},
     "root_cause": "Storage IOPS saturation",
     "action_items": 2, "open_actions": 0},
    {"id": "INC-005", "severity": "P2", "title": "API Rate Limit Misconfiguration",
     "date": "2026-01-28", "status": "RESOLVED", "mttr_min": 31,
     "affected_partners": ["PartnerC", "PartnerD"],
     "sla_breach_hours": {"PartnerC": 0.2, "PartnerD": 0.3},
     "root_cause": "Config drift after rollout",
     "action_items": 3, "open_actions": 0},
    {"id": "INC-008", "severity": "P2", "title": "Inference Queue Saturation",
     "date": "2026-02-09", "status": "RESOLVED", "mttr_min": 19,
     "affected_partners": ["PartnerB"],
     "sla_breach_hours": {"PartnerB": 0.0},
     "root_cause": "Autoscaler lag during traffic burst",
     "action_items": 2, "open_actions": 1},
    {"id": "INC-011", "severity": "P2", "title": "Telemetry Ingestion Drop",
     "date": "2026-02-18", "status": "RESOLVED", "mttr_min": 42,
     "affected_partners": ["PartnerE"],
     "sla_breach_hours": {"PartnerE": 0.5},
     "root_cause": "Kafka consumer group rebalance",
     "action_items": 3, "open_actions": 0},
    {"id": "INC-014", "severity": "P2", "title": "Auth Token Expiry Loop",
     "date": "2026-02-25", "status": "MONITORING", "mttr_min": 55,
     "affected_partners": ["PartnerA", "PartnerB"],
     "sla_breach_hours": {"PartnerA": 0.4, "PartnerB": 0.6},
     "root_cause": "JWT refresh race condition",
     "action_items": 4, "open_actions": 2},
    {"id": "INC-016", "severity": "P2", "title": "DB Connection Pool Exhaustion",
     "date": "2026-03-05", "status": "RESOLVED", "mttr_min": 22,
     "affected_partners": ["PartnerC"],
     "sla_breach_hours": {"PartnerC": 0.1},
     "root_cause": "Connection leak in eval harness",
     "action_items": 2, "open_actions": 0},
    {"id": "INC-018", "severity": "P2", "title": "GR00T Inference Stall",
     "date": "2026-03-15", "status": "RESOLVED", "mttr_min": 17,
     "affected_partners": ["PartnerD"],
     "sla_breach_hours": {"PartnerD": 0.0},
     "root_cause": "Deadlock in action chunking buffer",
     "action_items": 2, "open_actions": 0},
    # P3s (12)
    *[
        {"id": f"INC-{str(i).zfill(3)}", "severity": "P3",
         "title": t, "date": d, "status": "RESOLVED", "mttr_min": m,
         "affected_partners": ["PartnerA"],
         "sla_breach_hours": {"PartnerA": 0.0},
         "root_cause": "Minor config or dependency issue",
         "action_items": 1, "open_actions": 0}
        for i, t, d, m in [
            (3,  "Slow Dashboard Load",          "2026-01-21",  8),
            (4,  "Log Rotation Delay",            "2026-01-24", 12),
            (6,  "SDK Deprecation Warning",       "2026-01-31",  6),
            (9,  "Stale Cache on Eval Endpoint",  "2026-02-12", 14),
            (10, "Minor API Timeout Spike",       "2026-02-15",  9),
            (12, "Dataset Hash Mismatch",         "2026-02-21", 11),
            (13, "Checkpoint Naming Conflict",    "2026-02-23",  7),
            (15, "Alert Noise from Monitor",      "2026-03-01",  5),
            (17, "Webhook Retry Flood",           "2026-03-11", 10),
            (20, "Low Priority Config Sync",      "2026-03-24",  6),
            (21, "Minor UI Rendering Bug",        "2026-03-26",  4),
            (22, "Deprecation Log Spam",          "2026-03-28",  3),
        ]
    ]
]

PARTNERS = ["PartnerA", "PartnerB", "PartnerC", "PartnerD", "PartnerE"]

# ---------------------------------------------------------------------------
# HTML / SVG generation helpers
# ---------------------------------------------------------------------------

def severity_color(s):
    return {"P1": "#ef4444", "P2": "#f97316", "P3": "#facc15"}.get(s, "#94a3b8")

def status_color(st):
    return {"RESOLVED": "#22c55e", "MONITORING": "#38bdf8", "OPEN": "#ef4444"}.get(st, "#94a3b8")

def severity_radius(s):
    return {"P1": 12, "P2": 8, "P3": 5}.get(s, 5)


def build_timeline_svg():
    """3-month rolling incident timeline."""
    W, H = 860, 220
    start = datetime(2026, 1, 1)
    end   = datetime(2026, 4, 1)
    total_days = (end - start).days  # 90

    def x_for_date(d_str):
        dt = datetime.strptime(d_str, "%Y-%m-%d")
        frac = (dt - start).days / total_days
        return 60 + frac * 760

    lines = []
    # background
    lines.append(f'<rect width="{W}" height="{H}" fill="#1e293b" rx="8"/>')
    # month gridlines
    for month_start, label in [
        (datetime(2026, 1, 1), "Jan 2026"),
        (datetime(2026, 2, 1), "Feb 2026"),
        (datetime(2026, 3, 1), "Mar 2026"),
        (datetime(2026, 4, 1), "Apr"),
    ]:
        xg = 60 + (month_start - start).days / total_days * 760
        lines.append(f'<line x1="{xg:.1f}" y1="30" x2="{xg:.1f}" y2="175" stroke="#334155" stroke-width="1" stroke-dasharray="4,4"/>')
        lines.append(f'<text x="{xg:.1f}" y="20" fill="#94a3b8" font-size="11" text-anchor="middle">{label}</text>')

    # center axis
    lines.append(f'<line x1="60" y1="110" x2="820" y2="110" stroke="#475569" stroke-width="2"/>')

    # incidents
    for inc in INCIDENTS:
        cx = x_for_date(inc["date"])
        r  = severity_radius(inc["severity"])
        fc = status_color(inc["status"])
        sc = severity_color(inc["severity"])
        # stagger by severity for readability
        cy = {"P1": 80, "P2": 110, "P3": 140}.get(inc["severity"], 110)
        lines.append(
            f'<circle cx="{cx:.1f}" cy="{cy}" r="{r}" fill="{fc}" '
            f'stroke="{sc}" stroke-width="2">'
            f'<title>{inc["id"]}: {inc["title"]} ({inc["status"]}, MTTR {inc["mttr_min"]}min)</title>'
            f'</circle>'
        )

    # legend
    for i, (label, col) in enumerate([
        ("P1", "#ef4444"), ("P2", "#f97316"), ("P3", "#facc15"),
        ("RESOLVED", "#22c55e"), ("MONITORING", "#38bdf8"), ("OPEN", "#ef4444")
    ]):
        lx = 60 + i * 130
        lines.append(f'<circle cx="{lx}" cy="198" r="5" fill="{col}"/>')
        lines.append(f'<text x="{lx+10}" y="202" fill="#94a3b8" font-size="10">{label}</text>')

    lines.append(f'<text x="{W//2}" y="{H-2}" fill="#64748b" font-size="9" text-anchor="middle">Hover circles for details</text>')
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}">{"".join(lines)}</svg>'


def build_heatmap_svg():
    """SLA breach impact heatmap — incidents × partners."""
    CELL = 48
    PAD_LEFT = 200
    PAD_TOP  = 80
    PAD_BOT  = 40

    # Only incidents that have SLA breach data
    inc_list = [i for i in INCIDENTS if any(v > 0 for v in i["sla_breach_hours"].values())]
    inc_list = inc_list[:12]  # cap for display

    W = PAD_LEFT + len(PARTNERS) * CELL + 20
    H = PAD_TOP + len(inc_list) * CELL + PAD_BOT

    def heat_color(hours):
        if hours <= 0:
            return "#1e293b"
        # 0 → #1e293b, max (2.1h) → #C74634
        t = min(hours / 2.2, 1.0)
        # interpolate slate→orange→red
        r = int(30  + t * (199 - 30))
        g = int(41  + t * (70  - 41))
        b = int(59  + t * (52  - 59))
        return f"rgb({r},{g},{b})"

    lines = []
    lines.append(f'<rect width="{W}" height="{H}" fill="#0f172a" rx="8"/>')

    # column headers (partners)
    for j, p in enumerate(PARTNERS):
        cx = PAD_LEFT + j * CELL + CELL // 2
        lines.append(f'<text x="{cx}" y="{PAD_TOP - 10}" fill="#94a3b8" font-size="11" text-anchor="middle">{p}</text>')
        lines.append(f'<text x="{cx}" y="{PAD_TOP - 24}" fill="#475569" font-size="9" text-anchor="middle">Partner</text>')

    for i, inc in enumerate(inc_list):
        ry = PAD_TOP + i * CELL
        # row label
        label = f"{inc['id']} {inc['severity']}"
        lines.append(f'<text x="{PAD_LEFT - 8}" y="{ry + CELL//2 + 4}" fill="#94a3b8" font-size="10" text-anchor="end">{label}</text>')
        title_short = inc["title"][:28] + ("…" if len(inc["title"]) > 28 else "")
        lines.append(f'<text x="10" y="{ry + CELL//2 + 4}" fill="#64748b" font-size="9">{title_short}</text>')

        for j, p in enumerate(PARTNERS):
            hours = inc["sla_breach_hours"].get(p, 0)
            cx = PAD_LEFT + j * CELL
            col = heat_color(hours)
            lines.append(f'<rect x="{cx+1}" y="{ry+1}" width="{CELL-2}" height="{CELL-2}" fill="{col}" rx="3"><title>{inc["id"]} × {p}: {hours:.1f}h SLA breach</title></rect>')
            if hours > 0:
                lines.append(f'<text x="{cx + CELL//2}" y="{ry + CELL//2 + 4}" fill="#f8fafc" font-size="10" text-anchor="middle">{hours:.1f}h</text>')

    # color scale legend
    scale_x = PAD_LEFT
    scale_y = H - PAD_BOT + 8
    for k in range(20):
        t = k / 19
        r = int(30  + t * (199 - 30))
        g = int(41  + t * (70  - 41))
        b = int(59  + t * (52  - 59))
        lines.append(f'<rect x="{scale_x + k*14}" y="{scale_y}" width="14" height="10" fill="rgb({r},{g},{b})"/>')
    lines.append(f'<text x="{scale_x}" y="{scale_y + 22}" fill="#64748b" font-size="9">0h</text>')
    lines.append(f'<text x="{scale_x + 280 - 20}" y="{scale_y + 22}" fill="#64748b" font-size="9">2.2h SLA breach</text>')

    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}">{"".join(lines)}</svg>'


def build_dashboard_html():
    total = len(INCIDENTS)
    p1 = sum(1 for i in INCIDENTS if i["severity"] == "P1")
    p2 = sum(1 for i in INCIDENTS if i["severity"] == "P2")
    p3 = sum(1 for i in INCIDENTS if i["severity"] == "P3")
    resolved = sum(1 for i in INCIDENTS if i["status"] == "RESOLVED")
    open_actions = sum(i["open_actions"] for i in INCIDENTS)
    avg_mttr_p1 = sum(i["mttr_min"] for i in INCIDENTS if i["severity"] == "P1") // p1
    avg_mttr_p2 = sum(i["mttr_min"] for i in INCIDENTS if i["severity"] == "P2") // p2

    timeline_svg = build_timeline_svg()
    heatmap_svg  = build_heatmap_svg()

    rows = ""
    for inc in sorted(INCIDENTS, key=lambda x: x["date"], reverse=True)[:10]:
        sc = severity_color(inc["severity"])
        stc = status_color(inc["status"])
        rows += f"""
        <tr style="border-bottom:1px solid #1e293b">
          <td style="padding:8px;color:#94a3b8;font-size:12px">{inc['id']}</td>
          <td style="padding:8px"><span style="background:{sc}22;color:{sc};padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600">{inc['severity']}</span></td>
          <td style="padding:8px;color:#e2e8f0;font-size:12px">{inc['title']}</td>
          <td style="padding:8px;color:#64748b;font-size:12px">{inc['date']}</td>
          <td style="padding:8px"><span style="background:{stc}22;color:{stc};padding:2px 8px;border-radius:4px;font-size:11px">{inc['status']}</span></td>
          <td style="padding:8px;color:#38bdf8;font-size:12px">{inc['mttr_min']}min</td>
          <td style="padding:8px;color:{'#ef4444' if inc['open_actions'] else '#22c55e'};font-size:12px">{inc['open_actions']} open</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Incident Response Tracker — OCI Robot Cloud</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; padding: 24px; }}
  h1   {{ color: #f8fafc; font-size: 22px; font-weight: 700; }}
  h2   {{ color: #94a3b8; font-size: 14px; font-weight: 600; text-transform: uppercase; letter-spacing: .08em; margin-bottom: 12px; }}
  .badge {{ display:inline-block; padding:2px 10px; border-radius:6px; font-size:12px; font-weight:600; }}
  .card  {{ background:#1e293b; border-radius:12px; padding:20px; margin-bottom:24px; }}
  table  {{ width:100%; border-collapse:collapse; }}
  th     {{ padding:8px; color:#64748b; font-size:11px; text-align:left; border-bottom:1px solid #334155; }}
  .metric-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr)); gap:16px; margin-bottom:24px; }}
  .metric {{ background:#1e293b; border-radius:10px; padding:16px; text-align:center; }}
  .metric .val {{ font-size:32px; font-weight:700; color:#38bdf8; }}
  .metric .lbl {{ font-size:11px; color:#64748b; margin-top:4px; text-transform:uppercase; }}
  .red {{ color:#ef4444 !important; }}
  .green {{ color:#22c55e !important; }}
  .orange {{ color:#f97316 !important; }}
  .header-row {{ display:flex; align-items:center; justify-content:space-between; margin-bottom:24px; }}
  .uptime {{ background:#14532d; color:#22c55e; padding:4px 14px; border-radius:20px; font-size:13px; font-weight:600; }}
  .svg-scroll {{ overflow-x:auto; }}
</style>
</head>
<body>
<div class="header-row">
  <div>
    <h1>Incident Response Tracker</h1>
    <p style="color:#64748b;font-size:13px;margin-top:4px">OCI Robot Cloud — 3-Month Rolling View (Jan–Mar 2026)</p>
  </div>
  <span class="uptime">99.94% Uptime</span>
</div>

<div class="metric-grid">
  <div class="metric"><div class="val">{total}</div><div class="lbl">Total Incidents</div></div>
  <div class="metric"><div class="val red">{p1}</div><div class="lbl">P1 Critical</div></div>
  <div class="metric"><div class="val orange">{p2}</div><div class="lbl">P2 High</div></div>
  <div class="metric"><div class="val" style="color:#facc15">{p3}</div><div class="lbl">P3 Medium</div></div>
  <div class="metric"><div class="val green">{resolved}</div><div class="lbl">Resolved</div></div>
  <div class="metric"><div class="val">{avg_mttr_p1}min</div><div class="lbl">Avg MTTR P1</div></div>
  <div class="metric"><div class="val">{avg_mttr_p2}min</div><div class="lbl">Avg MTTR P2</div></div>
  <div class="metric"><div class="val {'red' if open_actions else 'green'}">{open_actions}</div><div class="lbl">Open Actions</div></div>
</div>

<div class="card">
  <h2>Incident Timeline — 3-Month Rolling</h2>
  <p style="color:#64748b;font-size:12px;margin-bottom:12px">Row by severity · size = severity · color = status · MTTR trend improving</p>
  <div class="svg-scroll">{timeline_svg}</div>
</div>

<div class="card">
  <h2>SLA Breach Impact Heatmap — Incidents × Partners</h2>
  <p style="color:#64748b;font-size:12px;margin-bottom:12px">Color intensity = hours of SLA breach per incident per partner</p>
  <div class="svg-scroll">{heatmap_svg}</div>
</div>

<div class="card">
  <h2>Recent Incidents</h2>
  <table>
    <thead><tr>
      <th>ID</th><th>SEV</th><th>Title</th><th>Date</th><th>Status</th><th>MTTR</th><th>Actions</th>
    </tr></thead>
    <tbody>{rows}</tbody>
  </table>
</div>

<div class="card" style="background:#0f172a;border:1px solid #1e293b">
  <h2>MTTR Trend</h2>
  <div style="display:flex;gap:32px;padding:8px 0">
    <div>
      <div style="color:#ef4444;font-size:12px;margin-bottom:6px">P1 MTTR over time</div>
      <div style="display:flex;gap:16px;align-items:flex-end">
        <div style="text-align:center">
          <div style="background:#C74634;width:32px;height:80px;border-radius:4px 4px 0 0"></div>
          <div style="color:#64748b;font-size:10px;margin-top:4px">Jan<br/>47min</div>
        </div>
        <div style="text-align:center">
          <div style="background:#C74634;width:32px;height:120px;border-radius:4px 4px 0 0"></div>
          <div style="color:#64748b;font-size:10px;margin-top:4px">Feb<br/>2.3h</div>
        </div>
        <div style="text-align:center">
          <div style="background:#22c55e;width:32px;height:22px;border-radius:4px 4px 0 0"></div>
          <div style="color:#64748b;font-size:10px;margin-top:4px">Mar<br/>18min</div>
        </div>
      </div>
      <div style="color:#22c55e;font-size:11px;margin-top:8px">↓ 87% reduction Jan→Mar</div>
    </div>
    <div style="border-left:1px solid #1e293b;padding-left:32px">
      <div style="color:#94a3b8;font-size:12px;margin-bottom:8px">RCA Coverage</div>
      <div style="color:#22c55e;font-size:28px;font-weight:700">100%</div>
      <div style="color:#64748b;font-size:11px">All P1/P2 incidents have RCA</div>
      <div style="margin-top:12px;color:#94a3b8;font-size:12px">Repeat Incident Rate</div>
      <div style="color:#38bdf8;font-size:28px;font-weight:700">9%</div>
      <div style="color:#64748b;font-size:11px">Latency &amp; sync recurrence only</div>
    </div>
  </div>
</div>

<p style="color:#334155;font-size:11px;text-align:center;margin-top:16px">OCI Robot Cloud · Incident Response Tracker · Port 8298</p>
</body></html>"""


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

if HAS_FASTAPI:
    app = FastAPI(title="Incident Response Tracker", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return HTMLResponse(content=build_dashboard_html())

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "incident_response_tracker", "port": 8298}

    @app.get("/api/incidents")
    async def get_incidents():
        return {"incidents": INCIDENTS, "total": len(INCIDENTS)}

    @app.get("/api/metrics")
    async def get_metrics():
        p1 = [i for i in INCIDENTS if i["severity"] == "P1"]
        p2 = [i for i in INCIDENTS if i["severity"] == "P2"]
        return {
            "total_incidents": len(INCIDENTS),
            "p1_count": len(p1),
            "p2_count": len([i for i in INCIDENTS if i["severity"] == "P2"]),
            "p3_count": len([i for i in INCIDENTS if i["severity"] == "P3"]),
            "mttr_p1_avg_min": sum(i["mttr_min"] for i in p1) // len(p1),
            "mttr_p2_avg_min": sum(i["mttr_min"] for i in p2) // len(p2),
            "resolved_pct": round(sum(1 for i in INCIDENTS if i["status"] == "RESOLVED") / len(INCIDENTS) * 100, 1),
            "open_action_items": sum(i["open_actions"] for i in INCIDENTS),
            "uptime_pct": 99.94,
            "repeat_incident_rate_pct": 9.1,
        }

else:
    # Fallback: stdlib http.server
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = build_dashboard_html().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            pass


if __name__ == "__main__":
    if HAS_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8298)
    else:
        print("FastAPI not found — starting stdlib fallback on port 8298")
        HTTPServer(("0.0.0.0", 8298), Handler).serve_forever()
