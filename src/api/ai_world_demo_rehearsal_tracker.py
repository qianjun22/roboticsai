"""AI World Demo Rehearsal Tracker — 12-component checklist + Gantt + risk matrix (port 8949)."""

import math
import random

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8949
SERVICE_TITLE = "AI World Demo Rehearsal Tracker"

# ── checklist (12 components) ──────────────────────────────────────────────
CHECKLIST = [
    {"id": 1,  "component": "GR00T N1.6 inference server",      "status": "done",    "owner": "Jun",     "due": "Jun 15"},
    {"id": 2,  "component": "LIBERO sim environment",           "status": "done",    "owner": "Jun",     "due": "Jun 15"},
    {"id": 3,  "component": "Fine-tune pipeline (SDG→train)",   "status": "done",    "owner": "Jun",     "due": "Jun 20"},
    {"id": 4,  "component": "Closed-loop eval harness",         "status": "done",    "owner": "Jun",     "due": "Jun 20"},
    {"id": 5,  "component": "OCI FastAPI demo dashboard",       "status": "done",    "owner": "Jun",     "due": "Jun 28"},
    {"id": 6,  "component": "Reward Model V4 integration",      "status": "in-progress", "owner": "Jun", "due": "Jul 10"},
    {"id": 7,  "component": "Multi-robot task panel",           "status": "in-progress", "owner": "Team","due": "Jul 15"},
    {"id": 8,  "component": "Live telemetry stream (port 8080)","status": "in-progress", "owner": "Team","due": "Jul 20"},
    {"id": 9,  "component": "Dress rehearsal A/V setup",        "status": "pending",  "owner": "Ops",    "due": "Aug 01"},
    {"id": 10, "component": "Script + slide deck freeze",       "status": "pending",  "owner": "Jun",    "due": "Aug 10"},
    {"id": 11, "component": "Backup hardware preflight",        "status": "pending",  "owner": "Ops",    "due": "Aug 20"},
    {"id": 12, "component": "Full dress rehearsal on-site",     "status": "pending",  "owner": "All",    "due": "Sep 05"},
]

STATUS_COLOR = {"done": "#4ade80", "in-progress": "#fbbf24", "pending": "#94a3b8"}
STATUS_BG    = {"done": "#14532d", "in-progress": "#451a03", "pending": "#1e293b"}

# ── Gantt SVG ─────────────────────────────────────────────────────────────
def _gantt_svg() -> str:
    # Phases: Jun tech, Jul dress, Aug freeze, Sep 10 AI World
    phases = [
        ("Jun: Tech Build",    0,   30,  "#38bdf8"),
        ("Jul: Dress Rehearsal",31,  61,  "#C74634"),
        ("Aug: Content Freeze", 62,  92,  "#f59e0b"),
        ("Sep 10: AI World",    93, 102,  "#4ade80"),
    ]
    milestones = [
        ("Reward V4",   40),
        ("Multi-robot", 45),
        ("AV Setup",    62),
        ("Deck Freeze", 71),
        ("Preflight",   81),
        ("Dress Run",   96),
        ("AI World",   102),
    ]
    w, h = 560, 220
    pad_l, pad_r, pad_t, pad_b = 140, 20, 40, 30
    total_days = 103
    chart_w = w - pad_l - pad_r
    row_h = 28

    def dx(day): return pad_l + day / total_days * chart_w

    bars = ""
    for i, (label, d_start, d_end, color) in enumerate(phases):
        x1 = dx(d_start)
        x2 = dx(d_end)
        y = pad_t + i * row_h
        bw = max(x2 - x1, 2)
        bars += f'<rect x="{x1:.1f}" y="{y}" width="{bw:.1f}" height="{row_h - 4}" fill="{color}" rx="3" opacity="0.85"/>'
        bars += f'<text x="{pad_l - 6}" y="{y + row_h//2}" text-anchor="end" fill="#e2e8f0" font-size="11" dominant-baseline="middle">{label}</text>'

    # milestone diamonds
    m_marks = ""
    for label, day in milestones:
        x = dx(day)
        y = pad_t + len(phases) * row_h + 14
        s = 6
        m_marks += f'<polygon points="{x},{y-s} {x+s},{y} {x},{y+s} {x-s},{y}" fill="#C74634"/>'
        m_marks += f'<text x="{x}" y="{y + s + 10}" text-anchor="middle" fill="#94a3b8" font-size="9">{label}</text>'

    # today line (day 90 = Sep 30, 2026 placeholder)
    today_day = 89
    tx = dx(today_day)
    today_line = f'<line x1="{tx:.1f}" y1="{pad_t - 10}" x2="{tx:.1f}" y2="{h - pad_b}" stroke="#f87171" stroke-width="1.5" stroke-dasharray="4,3"/>'
    today_label = f'<text x="{tx:.1f}" y="{pad_t - 14}" text-anchor="middle" fill="#f87171" font-size="9">today</text>'

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" style="background:#1e293b;border-radius:8px">
  <text x="{w//2}" y="14" text-anchor="middle" fill="#38bdf8" font-size="13" font-weight="bold">Rehearsal Schedule (Jun–Sep 10 AI World)</text>
  {bars}{m_marks}{today_line}{today_label}
</svg>'''

# ── Risk matrix SVG ────────────────────────────────────────────────────────
def _risk_svg() -> str:
    # (label, probability 0-1, impact 0-1)
    risks = [
        ("Hardware failure",    0.15, 0.95),
        ("Inference latency",   0.35, 0.75),
        ("SR below 0.80",       0.40, 0.85),
        ("Network outage",      0.20, 0.70),
        ("A/V glitch",          0.45, 0.50),
        ("Demo env crash",      0.25, 0.90),
    ]
    w, h, pad = 360, 300, 50
    cw, ch = w - 2 * pad, h - 2 * pad

    def rx(p): return pad + p * cw
    def ry(im): return h - pad - im * ch

    # quadrant fills
    quads = (
        f'<rect x="{pad}" y="{pad}" width="{cw//2}" height="{ch//2}" fill="#14532d" opacity="0.3"/>'
        f'<rect x="{pad + cw//2}" y="{pad}" width="{cw//2}" height="{ch//2}" fill="#451a03" opacity="0.4"/>'
        f'<rect x="{pad}" y="{pad + ch//2}" width="{cw//2}" height="{ch//2}" fill="#0c4a6e" opacity="0.3"/>'
        f'<rect x="{pad + cw//2}" y="{pad + ch//2}" width="{cw//2}" height="{ch//2}" fill="#7f1d1d" opacity="0.4"/>'
    )
    dots = ""
    for label, prob, impact in risks:
        x, y = rx(prob), ry(impact)
        color = "#C74634" if prob * impact > 0.25 else "#fbbf24"
        dots += f'<circle cx="{x:.1f}" cy="{y:.1f}" r="6" fill="{color}" opacity="0.9"/>'
        dots += f'<text x="{x + 9:.1f}" y="{y + 4:.1f}" fill="#e2e8f0" font-size="9">{label}</text>'

    axes = (
        f'<line x1="{pad}" y1="{pad}" x2="{pad}" y2="{h - pad}" stroke="#475569" stroke-width="1"/>'
        f'<line x1="{pad}" y1="{h - pad}" x2="{w - pad}" y2="{h - pad}" stroke="#475569" stroke-width="1"/>'
        f'<text x="{w//2}" y="{h - 8}" text-anchor="middle" fill="#94a3b8" font-size="10">Probability →</text>'
        f'<text x="12" y="{h//2}" text-anchor="middle" fill="#94a3b8" font-size="10" transform="rotate(-90,12,{h//2})">Impact →</text>'
    )
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" style="background:#1e293b;border-radius:8px">
  <text x="{w//2}" y="18" text-anchor="middle" fill="#38bdf8" font-size="12" font-weight="bold">Risk Matrix</text>
  {quads}{axes}{dots}
</svg>'''

# ── checklist table ────────────────────────────────────────────────────────
def _checklist_rows() -> str:
    rows = ""
    for item in CHECKLIST:
        sc = STATUS_COLOR[item["status"]]
        sb = STATUS_BG[item["status"]]
        badge = f'<span style="background:{sb};color:{sc};padding:.15rem .5rem;border-radius:4px;font-size:.75rem;font-weight:600">{item["status"]}</span>'
        rows += f'<tr><td>{item["id"]}</td><td>{item["component"]}</td><td>{badge}</td><td>{item["owner"]}</td><td>{item["due"]}</td></tr>\n'
    return rows

done_count = sum(1 for i in CHECKLIST if i["status"] == "done")
ip_count   = sum(1 for i in CHECKLIST if i["status"] == "in-progress")
pct = round(done_count / len(CHECKLIST) * 100)

HTML = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<title>{SERVICE_TITLE}</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',sans-serif;padding:2rem}}
  h1{{color:#C74634;font-size:1.8rem;margin-bottom:.4rem}}
  h2{{color:#38bdf8;font-size:1.1rem;margin:1.4rem 0 .6rem}}
  .card{{background:#1e293b;border-radius:10px;padding:1.2rem;margin-bottom:1.2rem}}
  .stat-row{{display:flex;gap:1.2rem;flex-wrap:wrap;margin-bottom:1rem}}
  .stat{{background:#0f172a;border-radius:8px;padding:.8rem 1.2rem;min-width:140px}}
  .stat .val{{font-size:1.6rem;font-weight:700;color:#C74634}}
  .stat .lbl{{font-size:.8rem;color:#94a3b8;margin-top:.2rem}}
  .charts{{display:flex;gap:1.4rem;flex-wrap:wrap;align-items:flex-start}}
  table{{border-collapse:collapse;width:100%;font-size:.88rem}}
  th{{background:#0f172a;color:#38bdf8;padding:.5rem .8rem;text-align:left}}
  td{{padding:.45rem .8rem;border-bottom:1px solid #334155}}
  tr:hover td{{background:#0f172a}}
  .progress-bar{{background:#334155;border-radius:4px;height:12px;width:100%;margin-top:.4rem}}
  .progress-fill{{background:#C74634;border-radius:4px;height:12px;width:{pct}%}}
</style>
</head>
<body>
<h1>{SERVICE_TITLE}</h1>
<p style="color:#94a3b8;font-size:.9rem">12-component AI World demo readiness — SR target 0.80 live | Port {PORT}</p>

<div class="card">
  <h2>Overall Readiness</h2>
  <div class="stat-row">
    <div class="stat"><div class="val">{done_count}/12</div><div class="lbl">Components Done</div></div>
    <div class="stat"><div class="val">{ip_count}</div><div class="lbl">In Progress</div></div>
    <div class="stat"><div class="val">{pct}%</div><div class="lbl">Readiness</div></div>
    <div class="stat"><div class="val">0.80</div><div class="lbl">SR Target (live)</div></div>
    <div class="stat"><div class="val">Sep 10</div><div class="lbl">AI World Date</div></div>
  </div>
  <div class="progress-bar"><div class="progress-fill"></div></div>
  <p style="font-size:.8rem;color:#94a3b8;margin-top:.4rem">{pct}% complete</p>
</div>

<div class="card">
  <h2>Rehearsal Gantt &amp; Risk Matrix</h2>
  <div class="charts">
    {_gantt_svg()}
    {_risk_svg()}
  </div>
</div>

<div class="card">
  <h2>12-Component Checklist</h2>
  <table>
    <thead><tr><th>#</th><th>Component</th><th>Status</th><th>Owner</th><th>Due</th></tr></thead>
    <tbody>
      {_checklist_rows()}
    </tbody>
  </table>
</div>

<div class="card">
  <h2>Risk Mitigations</h2>
  <table>
    <thead><tr><th>Risk</th><th>Mitigation</th><th>Owner</th></tr></thead>
    <tbody>
      <tr><td>Hardware failure</td><td>Backup A100 node pre-provisioned; failover &lt;60s</td><td>Ops</td></tr>
      <tr><td>Inference latency &gt;250ms</td><td>Warm cache + batched prefill; monitor via port 8080</td><td>Jun</td></tr>
      <tr><td>SR below 0.80</td><td>DAgger data collection + hotfix fine-tune loop ready</td><td>Jun</td></tr>
      <tr><td>Network outage</td><td>Local OCI subnet demo mode; no public internet required</td><td>Ops</td></tr>
      <tr><td>A/V glitch</td><td>Pre-recorded fallback video (1MB MP4) approved by PM</td><td>Ops</td></tr>
      <tr><td>Demo env crash</td><td>Checkpoint snapshot every 15 min; restore in &lt;2 min</td><td>Jun</td></tr>
    </tbody>
  </table>
</div>
</body></html>
"""

if USE_FASTAPI:
    app = FastAPI(title=SERVICE_TITLE)

    @app.get("/", response_class=HTMLResponse)
    def index():
        return HTML

    @app.get("/health")
    def health():
        return {"status": "ok", "service": SERVICE_TITLE, "port": PORT,
                "done": done_count, "in_progress": ip_count,
                "readiness_pct": pct, "sr_target": 0.80}

else:
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class _H(BaseHTTPRequestHandler):
        def do_GET(self):
            body = HTML.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        def log_message(self, *_): pass

if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        print(f"{SERVICE_TITLE} fallback on :{PORT}")
        HTTPServer(("0.0.0.0", PORT), _H).serve_forever()
