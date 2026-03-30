"""Security Audit Tracker — FastAPI service on port 8346.

Tracks security audit findings, remediation progress, and compliance posture.
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

import math
import random
import json
from datetime import datetime, timedelta

PORT = 8346

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

SEVERITY_DATA = [
    {"level": "CRITICAL", "total": 2,  "closed": 2,  "open": 0,  "color": "#ef4444", "mttr": 2.3},
    {"level": "HIGH",     "total": 7,  "closed": 7,  "open": 0,  "color": "#f97316", "mttr": 4.1},
    {"level": "MEDIUM",   "total": 14, "closed": 0,  "open": 14, "color": "#eab308", "mttr": 12.0},
    {"level": "LOW",      "total": 23, "closed": 10, "open": 13, "color": "#38bdf8", "mttr": 18.5},
    {"level": "INFO",     "total": 31, "closed": 18, "open": 13, "color": "#94a3b8", "mttr": 25.0},
]

NOTABLE_FINDINGS = [
    {"id": "SEC-001", "severity": "CRITICAL", "title": "API auth bypass via malformed JWT",      "status": "CLOSED", "closed_date": "2026-03-10"},
    {"id": "SEC-002", "severity": "CRITICAL", "title": "Unencrypted model weights in transit",    "status": "CLOSED", "closed_date": "2026-03-12"},
    {"id": "SEC-014", "severity": "MEDIUM",   "title": "Weak TLS config on inference endpoint", "status": "OPEN",   "deadline": "2026-04-30"},
    {"id": "SEC-021", "severity": "MEDIUM",   "title": "Missing rate-limiting on /infer API",   "status": "OPEN",   "deadline": "2026-04-30"},
]

TOTAL_FINDINGS = sum(s["total"] for s in SEVERITY_DATA)
TOTAL_OPEN     = sum(s["open"]  for s in SEVERITY_DATA)
TOTAL_CLOSED   = sum(s["closed"] for s in SEVERITY_DATA)
COMPLIANCE_SCORE = round((TOTAL_CLOSED / TOTAL_FINDINGS) * 100, 1)


def _timeline_rows() -> list:
    """Generate 30 days of finding/closure mock data."""
    random.seed(42)
    base = datetime(2026, 3, 1)
    rows = []
    cumulative_open = 5
    for i in range(30):
        day = base + timedelta(days=i)
        new_findings = random.randint(0, 4) if i < 15 else random.randint(0, 2)
        closures = random.randint(0, 3) if i < 15 else random.randint(1, 4)
        cumulative_open = max(0, cumulative_open + new_findings - closures)
        rows.append({
            "date": day.strftime("%m/%d"),
            "day": i,
            "new": new_findings,
            "closed": closures,
            "open": cumulative_open,
        })
    return rows

TIMELINE = _timeline_rows()


# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------

def _donut_svg() -> str:
    """Severity donut chart showing open vs closed per severity."""
    cx, cy, r_outer, r_inner = 220, 190, 140, 75
    total_items = TOTAL_FINDINGS
    segments = []
    angle = -90.0
    for sev in SEVERITY_DATA:
        frac = sev["total"] / total_items
        sweep = frac * 360
        # Closed arc (solid)
        if sev["closed"] > 0:
            cf = sev["closed"] / total_items
            cs = cf * 360
            x1 = cx + r_outer * math.cos(math.radians(angle))
            y1 = cy + r_outer * math.sin(math.radians(angle))
            x2 = cx + r_outer * math.cos(math.radians(angle + cs))
            y2 = cy + r_outer * math.sin(math.radians(angle + cs))
            xi1 = cx + r_inner * math.cos(math.radians(angle + cs))
            yi1 = cy + r_inner * math.sin(math.radians(angle + cs))
            xi2 = cx + r_inner * math.cos(math.radians(angle))
            yi2 = cy + r_inner * math.sin(math.radians(angle))
            laf = 1 if cs > 180 else 0
            d = (f"M {x1:.1f} {y1:.1f} A {r_outer} {r_outer} 0 {laf} 1 {x2:.1f} {y2:.1f} "
                 f"L {xi1:.1f} {yi1:.1f} A {r_inner} {r_inner} 0 {laf} 0 {xi2:.1f} {yi2:.1f} Z")
            segments.append(f'<path d="{d}" fill="{sev["color"]}" opacity="0.9"/>')
            angle += cs
        # Open arc (hatched / lighter)
        if sev["open"] > 0:
            of_ = sev["open"] / total_items
            os_ = of_ * 360
            x1 = cx + r_outer * math.cos(math.radians(angle))
            y1 = cy + r_outer * math.sin(math.radians(angle))
            x2 = cx + r_outer * math.cos(math.radians(angle + os_))
            y2 = cy + r_outer * math.sin(math.radians(angle + os_))
            xi1 = cx + r_inner * math.cos(math.radians(angle + os_))
            yi1 = cy + r_inner * math.sin(math.radians(angle + os_))
            xi2 = cx + r_inner * math.cos(math.radians(angle))
            yi2 = cy + r_inner * math.sin(math.radians(angle))
            laf = 1 if os_ > 180 else 0
            d = (f"M {x1:.1f} {y1:.1f} A {r_outer} {r_outer} 0 {laf} 1 {x2:.1f} {y2:.1f} "
                 f"L {xi1:.1f} {yi1:.1f} A {r_inner} {r_inner} 0 {laf} 0 {xi2:.1f} {yi2:.1f} Z")
            segments.append(f'<path d="{d}" fill="{sev["color"]}" opacity="0.35" stroke="{sev["color"]}" stroke-width="1"/>')
            angle += os_

    seg_html = "\n".join(segments)

    # Legend
    legend_items = ""
    for i, sev in enumerate(SEVERITY_DATA):
        lx, ly = 390, 100 + i * 38
        legend_items += (
            f'<rect x="{lx}" y="{ly}" width="14" height="14" rx="3" fill="{sev["color"]}"/>'
            f'<text x="{lx+20}" y="{ly+11}" fill="#e2e8f0" font-size="12" font-family="monospace">'
            f'{sev["level"]}: {sev["closed"]}/{sev["total"]} closed</text>'
        )

    return f"""
<svg width="580" height="380" xmlns="http://www.w3.org/2000/svg" style="background:#1e293b;border-radius:12px">
  <text x="290" y="28" text-anchor="middle" fill="#38bdf8" font-size="15" font-weight="bold" font-family="monospace">FINDINGS BY SEVERITY — OPEN vs CLOSED</text>
  {seg_html}
  <!-- centre label -->
  <text x="{cx}" y="{cy-10}" text-anchor="middle" fill="#f8fafc" font-size="22" font-weight="bold" font-family="monospace">{TOTAL_FINDINGS}</text>
  <text x="{cx}" y="{cy+14}" text-anchor="middle" fill="#94a3b8" font-size="11" font-family="monospace">Total</text>
  <text x="{cx}" y="{cy+32}" text-anchor="middle" fill="#4ade80" font-size="11" font-family="monospace">{TOTAL_CLOSED} closed</text>
  {legend_items}
  <!-- solid/open legend -->
  <rect x="390" y="310" width="14" height="14" rx="3" fill="#64748b" opacity="0.9"/>
  <text x="410" y="321" fill="#94a3b8" font-size="11" font-family="monospace">solid = closed</text>
  <rect x="390" y="330" width="14" height="14" rx="3" fill="#64748b" opacity="0.35"/>
  <text x="410" y="341" fill="#94a3b8" font-size="11" font-family="monospace">faded = open</text>
</svg>"""


def _timeline_svg() -> str:
    """30-day remediation timeline: finding rate vs closure rate."""
    W, H = 680, 300
    pad_l, pad_r, pad_t, pad_b = 55, 20, 40, 50
    chart_w = W - pad_l - pad_r
    chart_h = H - pad_t - pad_b
    n = len(TIMELINE)
    max_val = max(max(r["new"], r["closed"]) for r in TIMELINE) + 1

    def sx(i): return pad_l + i * chart_w / (n - 1)
    def sy(v): return pad_t + chart_h - v * chart_h / max_val

    # Grid lines
    grid = ""
    for v in range(0, max_val + 1):
        y = sy(v)
        grid += f'<line x1="{pad_l}" y1="{y:.1f}" x2="{W-pad_r}" y2="{y:.1f}" stroke="#334155" stroke-width="0.5"/>'
        grid += f'<text x="{pad_l-6}" y="{y+4:.1f}" fill="#64748b" font-size="9" text-anchor="end" font-family="monospace">{v}</text>'

    # New findings line (red)
    new_pts = " ".join(f"{sx(i):.1f},{sy(r['new']):.1f}" for i, r in enumerate(TIMELINE))
    # Closure line (green)
    close_pts = " ".join(f"{sx(i):.1f},{sy(r['closed']):.1f}" for i, r in enumerate(TIMELINE))

    # X-axis labels (every 5 days)
    xlabels = ""
    for i, r in enumerate(TIMELINE):
        if i % 5 == 0:
            xlabels += f'<text x="{sx(i):.1f}" y="{H-pad_b+14}" text-anchor="middle" fill="#64748b" font-size="9" font-family="monospace">{r["date"]}</text>'

    # MTTR annotations
    mttr_labels = ""
    mttr_data = [("CRIT 2.3d", "#ef4444"), ("HIGH 4.1d", "#f97316"), ("MED 12d", "#eab308")]
    for i, (txt, col) in enumerate(mttr_data):
        mttr_labels += f'<rect x="{pad_l + 10 + i*145}" y="{pad_t+6}" width="130" height="18" rx="4" fill="{col}" opacity="0.25"/>'
        mttr_labels += f'<text x="{pad_l + 75 + i*145}" y="{pad_t+18}" text-anchor="middle" fill="{col}" font-size="10" font-family="monospace">MTTR {txt}</text>'

    return f"""
<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg" style="background:#1e293b;border-radius:12px">
  <text x="{W//2}" y="22" text-anchor="middle" fill="#38bdf8" font-size="14" font-weight="bold" font-family="monospace">30-DAY REMEDIATION TIMELINE</text>
  {grid}
  <polyline points="{new_pts}" fill="none" stroke="#ef4444" stroke-width="2" stroke-linejoin="round"/>
  <polyline points="{close_pts}" fill="none" stroke="#4ade80" stroke-width="2" stroke-linejoin="round" stroke-dasharray="6,3"/>
  {xlabels}
  {mttr_labels}
  <!-- legend -->
  <line x1="{W-160}" y1="{H-30}" x2="{W-145}" y2="{H-30}" stroke="#ef4444" stroke-width="2"/>
  <text x="{W-140}" y="{H-26}" fill="#ef4444" font-size="10" font-family="monospace">New findings</text>
  <line x1="{W-160}" y1="{H-14}" x2="{W-145}" y2="{H-14}" stroke="#4ade80" stroke-width="2" stroke-dasharray="6,3"/>
  <text x="{W-140}" y="{H-10}" fill="#4ade80" font-size="10" font-family="monospace">Closures</text>
  <text x="{pad_l}" y="{H-8}" fill="#64748b" font-size="9" font-family="monospace">Positive trend: closures &gt; findings last 2 weeks</text>
</svg>"""


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def _html() -> str:
    notable_rows = ""
    for f in NOTABLE_FINDINGS:
        badge_color = "#4ade80" if f["status"] == "CLOSED" else "#eab308"
        extra = f['closed_date'] if f['status'] == 'CLOSED' else f'deadline {f.get("deadline","TBD")}'
        notable_rows += f"""
        <tr>
          <td style="padding:8px 12px;color:#94a3b8;font-family:monospace">{f['id']}</td>
          <td style="padding:8px 12px"><span style="background:{[s['color'] for s in SEVERITY_DATA if s['level']==f['severity']][0]}22;color:{[s['color'] for s in SEVERITY_DATA if s['level']==f['severity']][0]};padding:2px 8px;border-radius:4px;font-size:12px;font-family:monospace">{f['severity']}</span></td>
          <td style="padding:8px 12px;color:#e2e8f0;font-family:monospace;font-size:13px">{f['title']}</td>
          <td style="padding:8px 12px"><span style="background:{badge_color}22;color:{badge_color};padding:2px 8px;border-radius:4px;font-size:12px;font-family:monospace">{f['status']}</span></td>
          <td style="padding:8px 12px;color:#64748b;font-family:monospace;font-size:12px">{extra}</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Security Audit Tracker — Port {PORT}</title>
  <style>
    * {{ margin:0; padding:0; box-sizing:border-box; }}
    body {{ background:#0f172a; color:#e2e8f0; font-family:monospace; }}
    header {{ background:#1e293b; border-bottom:2px solid #C74634; padding:18px 32px; display:flex; align-items:center; gap:16px; }}
    .logo {{ width:36px; height:36px; background:#C74634; border-radius:8px; display:flex; align-items:center; justify-content:center; font-weight:bold; font-size:18px; color:#fff; }}
    h1 {{ font-size:20px; color:#f8fafc; }}
    h1 span {{ color:#C74634; }}
    .badge {{ background:#38bdf822; color:#38bdf8; border:1px solid #38bdf8; border-radius:20px; padding:3px 12px; font-size:12px; margin-left:auto; }}
    .metrics {{ display:grid; grid-template-columns:repeat(4,1fr); gap:16px; padding:24px 32px; }}
    .card {{ background:#1e293b; border-radius:12px; padding:20px; border-left:4px solid #C74634; }}
    .card.green {{ border-left-color:#4ade80; }}
    .card.yellow {{ border-left-color:#eab308; }}
    .card.blue {{ border-left-color:#38bdf8; }}
    .card-val {{ font-size:32px; font-weight:bold; color:#f8fafc; }}
    .card-label {{ font-size:12px; color:#64748b; margin-top:4px; }}
    .charts {{ display:flex; gap:20px; padding:0 32px 24px; flex-wrap:wrap; }}
    .section {{ padding:0 32px 32px; }}
    section-title {{ font-size:14px; color:#38bdf8; margin-bottom:12px; display:block; }}
    table {{ width:100%; border-collapse:collapse; background:#1e293b; border-radius:12px; overflow:hidden; }}
    thead th {{ background:#0f172a; color:#94a3b8; padding:10px 12px; text-align:left; font-size:12px; }}
    tbody tr:hover {{ background:#0f172a44; }}
    .footer {{ text-align:center; padding:16px; color:#334155; font-size:11px; }}
  </style>
</head>
<body>
  <header>
    <div class="logo">S</div>
    <div>
      <h1><span>OCI</span> Security Audit Tracker</h1>
      <div style="color:#64748b;font-size:12px">RoboticsAI Platform — Compliance Dashboard</div>
    </div>
    <div class="badge">Port {PORT}</div>
  </header>

  <div class="metrics">
    <div class="card">
      <div class="card-val" style="color:#ef4444">{TOTAL_OPEN}</div>
      <div class="card-label">Open Findings</div>
    </div>
    <div class="card green">
      <div class="card-val" style="color:#4ade80">{TOTAL_CLOSED}</div>
      <div class="card-label">Closed Findings</div>
    </div>
    <div class="card yellow">
      <div class="card-val" style="color:#eab308">{COMPLIANCE_SCORE}%</div>
      <div class="card-label">Compliance Score</div>
    </div>
    <div class="card blue">
      <div class="card-val" style="color:#38bdf8">2.3d</div>
      <div class="card-label">MTTR Critical</div>
    </div>
  </div>

  <div class="charts">
    {_donut_svg()}
    {_timeline_svg()}
  </div>

  <div class="section">
    <div style="color:#38bdf8;font-size:14px;margin-bottom:12px">NOTABLE FINDINGS</div>
    <table>
      <thead><tr><th>ID</th><th>Severity</th><th>Title</th><th>Status</th><th>Date / Deadline</th></tr></thead>
      <tbody>{notable_rows}</tbody>
    </table>
  </div>

  <div class="section">
    <div style="color:#38bdf8;font-size:14px;margin-bottom:12px">MTTR BY SEVERITY</div>
    <div style="display:flex;gap:16px;flex-wrap:wrap">"""

# Build MTTR bars inline
def _mttr_bars() -> str:
    bars = ""
    max_mttr = max(s["mttr"] for s in SEVERITY_DATA)
    for sev in SEVERITY_DATA:
        pct = sev["mttr"] / max_mttr * 100
        bars += f"""<div style="background:#1e293b;border-radius:8px;padding:14px 18px;min-width:160px">
      <div style="color:{sev['color']};font-size:12px;margin-bottom:6px">{sev['level']}</div>
      <div style="background:#0f172a;border-radius:4px;height:8px;margin-bottom:6px">
        <div style="background:{sev['color']};width:{pct:.0f}%;height:8px;border-radius:4px"></div>
      </div>
      <div style="color:#f8fafc;font-size:20px;font-weight:bold">{sev['mttr']}d</div>
      <div style="color:#64748b;font-size:11px">avg MTTR</div>
    </div>"""
    return bars


def build_html() -> str:
    notable_rows = ""
    for f in NOTABLE_FINDINGS:
        sev_color = next(s["color"] for s in SEVERITY_DATA if s["level"] == f["severity"])
        badge_color = "#4ade80" if f["status"] == "CLOSED" else "#eab308"
        extra = f['closed_date'] if f['status'] == 'CLOSED' else f'deadline {f.get("deadline", "TBD")}'
        notable_rows += f"""
        <tr>
          <td style="padding:8px 12px;color:#94a3b8;font-family:monospace">{f['id']}</td>
          <td style="padding:8px 12px"><span style="background:{sev_color}22;color:{sev_color};padding:2px 8px;border-radius:4px;font-size:12px;font-family:monospace">{f['severity']}</span></td>
          <td style="padding:8px 12px;color:#e2e8f0;font-family:monospace;font-size:13px">{f['title']}</td>
          <td style="padding:8px 12px"><span style="background:{badge_color}22;color:{badge_color};padding:2px 8px;border-radius:4px;font-size:12px;font-family:monospace">{f['status']}</span></td>
          <td style="padding:8px 12px;color:#64748b;font-family:monospace;font-size:12px">{extra}</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Security Audit Tracker — Port {PORT}</title>
  <style>
    * {{ margin:0; padding:0; box-sizing:border-box; }}
    body {{ background:#0f172a; color:#e2e8f0; font-family:monospace; }}
    header {{ background:#1e293b; border-bottom:2px solid #C74634; padding:18px 32px; display:flex; align-items:center; gap:16px; }}
    .logo {{ width:36px; height:36px; background:#C74634; border-radius:8px; display:flex; align-items:center; justify-content:center; font-weight:bold; font-size:18px; color:#fff; }}
    h1 {{ font-size:20px; color:#f8fafc; }}
    h1 span {{ color:#C74634; }}
    .badge {{ background:#38bdf822; color:#38bdf8; border:1px solid #38bdf8; border-radius:20px; padding:3px 12px; font-size:12px; margin-left:auto; }}
    .metrics {{ display:grid; grid-template-columns:repeat(4,1fr); gap:16px; padding:24px 32px; }}
    .card {{ background:#1e293b; border-radius:12px; padding:20px; border-left:4px solid #C74634; }}
    .card.green {{ border-left-color:#4ade80; }}
    .card.yellow {{ border-left-color:#eab308; }}
    .card.blue {{ border-left-color:#38bdf8; }}
    .card-val {{ font-size:32px; font-weight:bold; color:#f8fafc; }}
    .card-label {{ font-size:12px; color:#64748b; margin-top:4px; }}
    .charts {{ display:flex; gap:20px; padding:0 32px 24px; flex-wrap:wrap; }}
    .section {{ padding:0 32px 32px; }}
    table {{ width:100%; border-collapse:collapse; background:#1e293b; border-radius:12px; overflow:hidden; }}
    thead th {{ background:#0f172a; color:#94a3b8; padding:10px 12px; text-align:left; font-size:12px; }}
    tbody tr:hover {{ background:#0f172a44; }}
    .footer {{ text-align:center; padding:16px; color:#334155; font-size:11px; }}
  </style>
</head>
<body>
  <header>
    <div class="logo">S</div>
    <div>
      <h1><span>OCI</span> Security Audit Tracker</h1>
      <div style="color:#64748b;font-size:12px">RoboticsAI Platform — Compliance Dashboard</div>
    </div>
    <div class="badge">Port {PORT}</div>
  </header>

  <div class="metrics">
    <div class="card">
      <div class="card-val" style="color:#ef4444">{TOTAL_OPEN}</div>
      <div class="card-label">Open Findings</div>
    </div>
    <div class="card green">
      <div class="card-val" style="color:#4ade80">{TOTAL_CLOSED}</div>
      <div class="card-label">Closed Findings</div>
    </div>
    <div class="card yellow">
      <div class="card-val" style="color:#eab308">{COMPLIANCE_SCORE}%</div>
      <div class="card-label">Compliance Score</div>
    </div>
    <div class="card blue">
      <div class="card-val" style="color:#38bdf8">2.3d</div>
      <div class="card-label">MTTR Critical</div>
    </div>
  </div>

  <div class="charts">
    {_donut_svg()}
    {_timeline_svg()}
  </div>

  <div class="section">
    <div style="color:#38bdf8;font-size:14px;margin-bottom:12px">NOTABLE FINDINGS</div>
    <table>
      <thead><tr><th>ID</th><th>Severity</th><th>Title</th><th>Status</th><th>Date / Deadline</th></tr></thead>
      <tbody>{notable_rows}</tbody>
    </table>
  </div>

  <div class="section">
    <div style="color:#38bdf8;font-size:14px;margin-bottom:12px">MTTR BY SEVERITY</div>
    <div style="display:flex;gap:16px;flex-wrap:wrap">
      {_mttr_bars()}
    </div>
  </div>

  <div class="footer">Security Audit Tracker v1.0 | OCI RoboticsAI | Port {PORT} | {TOTAL_FINDINGS} total findings | Compliance {COMPLIANCE_SCORE}%</div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# App wiring
# ---------------------------------------------------------------------------

if USE_FASTAPI:
    app = FastAPI(title="Security Audit Tracker", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return build_html()

    @app.get("/health")
    async def health():
        return {"status": "ok", "port": PORT, "total_findings": TOTAL_FINDINGS,
                "open": TOTAL_OPEN, "closed": TOTAL_CLOSED, "compliance": COMPLIANCE_SCORE}

    @app.get("/api/findings")
    async def findings():
        return {"severities": SEVERITY_DATA, "notable": NOTABLE_FINDINGS,
                "timeline": TIMELINE, "summary": {
                    "total": TOTAL_FINDINGS, "open": TOTAL_OPEN,
                    "closed": TOTAL_CLOSED, "compliance_score": COMPLIANCE_SCORE}}

else:
    import http.server
    import socketserver

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            body = build_html().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        def log_message(self, fmt, *args):
            pass


if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        print(f"FastAPI unavailable — falling back to stdlib http.server on port {PORT}")
        with socketserver.TCPServer(("", PORT), Handler) as httpd:
            httpd.serve_forever()
