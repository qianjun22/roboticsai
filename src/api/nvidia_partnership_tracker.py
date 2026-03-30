"""NVIDIA Partnership Tracker — FastAPI port 8785"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8785

def build_html():
    random.seed(99)

    # Partnership milestones with progress
    milestones = [
        {"name": "Isaac Sim Integration", "owner": "Robotics Infra", "status": "DONE", "progress": 100, "date": "2026-01-15"},
        {"name": "GR00T N1.6 Deployment", "owner": "ML Platform", "status": "DONE", "progress": 100, "date": "2026-02-03"},
        {"name": "Cosmos World Model API", "owner": "AI Research", "status": "DONE", "progress": 100, "date": "2026-02-28"},
        {"name": "Joint Go-To-Market Plan", "owner": "BD", "status": "IN PROGRESS", "progress": 72, "date": "2026-04-10"},
        {"name": "OCI x DGX Cloud Co-Sell", "owner": "Sales", "status": "IN PROGRESS", "progress": 55, "date": "2026-05-01"},
        {"name": "NIM Microservices on OCI", "owner": "Partnerships", "status": "IN PROGRESS", "progress": 38, "date": "2026-05-20"},
        {"name": "Joint Reference Architecture", "owner": "Solutions", "status": "PLANNED", "progress": 10, "date": "2026-06-30"},
        {"name": "AI World Demo Co-Presentation", "owner": "Marketing", "status": "PLANNED", "progress": 5, "date": "2026-07-15"},
    ]

    # Engagement activity over 8 weeks (meetings, emails, events)
    weeks = ["W1", "W2", "W3", "W4", "W5", "W6", "W7", "W8"]
    meetings = [random.randint(2, 7) for _ in weeks]
    emails = [random.randint(5, 20) for _ in weeks]
    events = [random.randint(0, 2) for _ in weeks]

    # SVG stacked bar for engagement activity
    bar_svg_w, bar_svg_h = 440, 130
    bar_max = 28
    bar_w = int((bar_svg_w - 40) / len(weeks))
    bars_svg = ""
    for idx, (w, m, e, ev) in enumerate(zip(weeks, meetings, emails, events)):
        total = m + e + ev
        bx = 20 + idx * bar_w + 3
        # meetings (green)
        mh = int((m / bar_max) * (bar_svg_h - 30))
        eh = int((e / bar_max) * (bar_svg_h - 30))
        evh = int((ev / bar_max) * (bar_svg_h - 30))
        by_ev = bar_svg_h - 20 - evh
        by_e = by_ev - eh
        by_m = by_e - mh
        bars_svg += f'<rect x="{bx}" y="{by_ev}" width="{bar_w-6}" height="{evh}" fill="#818cf8" rx="2"/>'
        bars_svg += f'<rect x="{bx}" y="{by_e}" width="{bar_w-6}" height="{eh}" fill="#38bdf8" rx="2"/>'
        bars_svg += f'<rect x="{bx}" y="{by_m}" width="{bar_w-6}" height="{mh}" fill="#34d399" rx="2"/>'
        bars_svg += f'<text x="{bx + (bar_w-6)//2}" y="{bar_svg_h - 5}" fill="#64748b" font-size="9" text-anchor="middle">{w}</text>'
        bars_svg += f'<text x="{bx + (bar_w-6)//2}" y="{by_m - 2}" fill="#e2e8f0" font-size="8" text-anchor="middle">{total}</text>'

    # Radar chart for partnership health dimensions (SVG)
    dimensions = ["Technical", "Commercial", "GTM", "Exec Alignment", "Field", "Marketing"]
    scores = [round(random.uniform(0.55, 0.97), 2) for _ in dimensions]
    radar_cx, radar_cy, radar_r = 140, 110, 85
    n = len(dimensions)
    radar_pts = []
    for i, s in enumerate(scores):
        angle = math.pi / 2 - 2 * math.pi * i / n
        x = radar_cx + radar_r * s * math.cos(angle)
        y = radar_cy - radar_r * s * math.sin(angle)
        radar_pts.append((round(x, 1), round(y, 1)))
    polygon_pts = " ".join(f"{x},{y}" for x, y in radar_pts)
    # Axis lines + labels
    axes_svg = ""
    for i, lbl in enumerate(dimensions):
        angle = math.pi / 2 - 2 * math.pi * i / n
        ex = round(radar_cx + radar_r * math.cos(angle), 1)
        ey = round(radar_cy - radar_r * math.sin(angle), 1)
        lx = round(radar_cx + (radar_r + 18) * math.cos(angle), 1)
        ly = round(radar_cy - (radar_r + 18) * math.sin(angle), 1)
        axes_svg += f'<line x1="{radar_cx}" y1="{radar_cy}" x2="{ex}" y2="{ey}" stroke="#334155" stroke-width="1"/>'
        axes_svg += f'<text x="{lx}" y="{ly}" fill="#94a3b8" font-size="9" text-anchor="middle" dominant-baseline="middle">{lbl}</text>'
    # Grid circles
    for r_frac in [0.33, 0.66, 1.0]:
        axes_svg += f'<circle cx="{radar_cx}" cy="{radar_cy}" r="{int(radar_r * r_frac)}" fill="none" stroke="#1e3a5f" stroke-width="1"/>'

    # KPIs
    total_meetings = sum(meetings)
    total_emails = sum(emails)
    done_count = sum(1 for m in milestones if m["status"] == "DONE")
    inprog_count = sum(1 for m in milestones if m["status"] == "IN PROGRESS")
    health_score = round(sum(scores) / len(scores) * 100, 1)
    pipeline_value = round(random.uniform(4.2, 6.8), 1)

    # Milestone table rows
    milestone_rows = ""
    status_class = {"DONE": "badge-ok", "IN PROGRESS": "badge-inprog", "PLANNED": "badge-plan"}
    for m in milestones:
        pct = m["progress"]
        bar_color = "#34d399" if pct == 100 else "#38bdf8" if pct >= 50 else "#fbbf24"
        prog_bar = f'<div style="background:#1e293b;border-radius:4px;height:8px;width:100px;display:inline-block;vertical-align:middle"><div style="background:{bar_color};width:{pct}px;height:8px;border-radius:4px"></div></div>'
        sc = status_class.get(m["status"], "badge-plan")
        milestone_rows += f"<tr><td>{m['name']}</td><td>{m['owner']}</td><td>{prog_bar} {pct}%</td><td><span class=\"badge {sc}\">{m['status']}</span></td><td style='color:#64748b'>{m['date']}</td></tr>"

    return f"""<!DOCTYPE html><html><head><title>NVIDIA Partnership Tracker</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui,sans-serif;padding:20px}}
h1{{color:#C74634;margin:0 0 4px 0;font-size:1.6rem}}
h2{{color:#38bdf8;font-size:1rem;margin:0 0 10px 0}}
.subtitle{{color:#64748b;font-size:0.85rem;margin-bottom:20px}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:20px}}
.card{{background:#1e293b;padding:16px;border-radius:8px;border:1px solid #334155}}
.metric{{font-size:1.8rem;font-weight:700;color:#f8fafc}}
.label{{font-size:0.75rem;color:#64748b;text-transform:uppercase;letter-spacing:.05em;margin-top:4px}}
.good{{color:#34d399}}.warn{{color:#fbbf24}}.inprog{{color:#38bdf8}}
.chart-card{{background:#1e293b;padding:16px;border-radius:8px;border:1px solid #334155;margin-bottom:14px}}
.row{{display:grid;grid-template-columns:2fr 1fr;gap:12px}}
table{{width:100%;border-collapse:collapse;font-size:0.82rem}}
th{{text-align:left;color:#64748b;padding:6px 8px;border-bottom:1px solid #334155;font-weight:500}}
td{{padding:6px 8px;border-bottom:1px solid #1e293b}}
.badge{{display:inline-block;padding:2px 8px;border-radius:4px;font-size:0.72rem;font-weight:600}}
.badge-ok{{background:#064e3b;color:#34d399}}
.badge-inprog{{background:#0c4a6e;color:#38bdf8}}
.badge-plan{{background:#1e1b4b;color:#818cf8}}
.legend{{display:flex;gap:16px;font-size:0.75rem;margin-bottom:8px}}
.dot{{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:4px;vertical-align:middle}}
</style></head>
<body>
<h1>NVIDIA Partnership Tracker</h1>
<div class="subtitle">Port {PORT} &nbsp;|&nbsp; OCI x NVIDIA Strategic Alliance &nbsp;|&nbsp; Robotics AI Go-To-Market &nbsp;|&nbsp; Updated 2026-03-30</div>

<div class="grid">
  <div class="card">
    <div class="metric good">{health_score}%</div>
    <div class="label">Partnership Health Score</div>
  </div>
  <div class="card">
    <div class="metric inprog">${pipeline_value}M</div>
    <div class="label">Co-Sell Pipeline Value</div>
  </div>
  <div class="card">
    <div class="metric">{done_count} / {len(milestones)}</div>
    <div class="label">Milestones Completed</div>
  </div>
  <div class="card">
    <div class="metric warn">{inprog_count}</div>
    <div class="label">In-Progress Initiatives</div>
  </div>
</div>

<div class="row">
  <div class="chart-card">
    <h2>8-Week Engagement Activity</h2>
    <div class="legend">
      <span><span class="dot" style="background:#34d399"></span>Meetings</span>
      <span><span class="dot" style="background:#38bdf8"></span>Emails</span>
      <span><span class="dot" style="background:#818cf8"></span>Events</span>
    </div>
    <svg width="{bar_svg_w}" height="{bar_svg_h}" style="background:#0f172a;border-radius:6px">
      {bars_svg}
      <text x="15" y="14" fill="#64748b" font-size="8">28</text>
      <text x="15" y="{bar_svg_h-22}" fill="#64748b" font-size="8">0</text>
    </svg>
    <div style="font-size:0.78rem;color:#64748b;margin-top:8px">
      Total: <span style="color:#34d399">{total_meetings} meetings</span> &nbsp; <span style="color:#38bdf8">{total_emails} emails</span> &nbsp; <span style="color:#818cf8">{sum(events)} events</span> over 8 weeks
    </div>
  </div>
  <div class="chart-card">
    <h2>Partnership Health Radar</h2>
    <svg width="280" height="220" style="background:#0f172a;border-radius:6px">
      {axes_svg}
      <polygon points="{polygon_pts}" fill="#38bdf820" stroke="#38bdf8" stroke-width="2"/>
      {''.join(f'<circle cx="{x}" cy="{y}" r="3" fill="#38bdf8"/>' for x, y in radar_pts)}
    </svg>
  </div>
</div>

<div class="chart-card">
  <h2>Initiative Milestones</h2>
  <table>
    <tr><th>Initiative</th><th>Owner</th><th>Progress</th><th>Status</th><th>Target Date</th></tr>
    {milestone_rows}
  </table>
</div>

</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="NVIDIA Partnership Tracker")
    @app.get("/", response_class=HTMLResponse)
    def index(): return build_html()
    @app.get("/health")
    def health(): return {"status": "ok", "port": PORT}
    @app.get("/summary")
    def summary():
        random.seed(99)
        scores = [round(random.uniform(0.55, 0.97), 2) for _ in range(6)]
        return {
            "partnership_health_pct": round(sum(scores) / len(scores) * 100, 1),
            "milestones_done": 3,
            "milestones_total": 8,
            "co_sell_pipeline_usd_millions": round(random.uniform(4.2, 6.8), 1),
            "port": PORT
        }

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(build_html().encode())
    def log_message(self, *a): pass

if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
