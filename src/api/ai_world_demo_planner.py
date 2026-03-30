"""AI World Demo Planner — FastAPI port 8767"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8767

# Demo schedule for AI World 2026 booth
DEMO_SCHEDULE = [
    {"time": "09:00", "demo": "GR00T Fine-Tune Live",     "duration": 20, "audience": "engineers",   "risk": "low"},
    {"time": "09:30", "demo": "Closed-Loop Eval",         "duration": 15, "audience": "executives",  "risk": "low"},
    {"time": "10:00", "demo": "SDG Isaac Sim",            "duration": 25, "audience": "mixed",       "risk": "medium"},
    {"time": "10:30", "demo": "DAgger Live Roll-Out",     "duration": 20, "audience": "engineers",   "risk": "high"},
    {"time": "11:00", "demo": "Multi-Task Policy",        "duration": 20, "audience": "mixed",       "risk": "medium"},
    {"time": "11:30", "demo": "OCI Cost Dashboard",       "duration": 10, "audience": "executives",  "risk": "low"},
    {"time": "13:00", "demo": "Cosmos World Model",       "duration": 30, "audience": "press",       "risk": "medium"},
    {"time": "13:30", "demo": "Jetson Edge Deploy",       "duration": 20, "audience": "engineers",   "risk": "medium"},
    {"time": "14:00", "demo": "Sim-to-Real Validator",    "duration": 15, "audience": "mixed",       "risk": "low"},
    {"time": "14:30", "demo": "CEO Keynote: OCI Robots",  "duration": 30, "audience": "all",         "risk": "low"},
    {"time": "15:15", "demo": "Partner API Showcase",     "duration": 20, "audience": "partners",    "risk": "low"},
    {"time": "16:00", "demo": "Data Flywheel Demo",        "duration": 25, "audience": "engineers",   "risk": "medium"},
]

STATUS_COLOR = {"low": "#22d3ee", "medium": "#f59e0b", "high": "#f87171"}

def build_html():
    random.seed(99)

    # Booth traffic simulation: hourly visitors (sinusoidal day curve)
    hours = list(range(9, 18))
    visitors = [int(40 + 55 * math.sin(math.pi * (h - 8) / 10) + random.randint(-8, 8)) for h in hours]
    max_v = max(visitors)
    w, h_svg, pad = 420, 110, 14
    bar_w = (w - 2*pad) / len(hours) - 3
    visitor_bars = "".join(
        f'<rect x="{pad + i*(bar_w+3):.1f}" y="{h_svg - pad - visitors[i]/max_v*(h_svg-2*pad):.1f}" '
        f'width="{bar_w:.1f}" height="{visitors[i]/max_v*(h_svg-2*pad):.1f}" fill="#818cf8" opacity="0.85" rx="2"/>'
        f'<text x="{pad + i*(bar_w+3) + bar_w/2:.1f}" y="{h_svg-2:.0f}" text-anchor="middle" font-size="8" fill="#94a3b8">{hours[i]}</text>'
        for i in range(len(hours))
    )

    # Readiness radar chart (hexagonal, 6 axes)
    axes_labels = ["HW Ready", "SW Deploy", "Demo Script", "Backup Plan", "Staff Brief", "Connectivity"]
    scores = [random.uniform(0.72, 0.99) for _ in axes_labels]
    cx, cy, r = 110, 110, 85
    N = len(axes_labels)
    def radar_pt(i, score):
        angle = math.pi / 2 - 2 * math.pi * i / N
        return cx + score * r * math.cos(angle), cy - score * r * math.sin(angle)
    # Grid circles
    grid_circles = "".join(
        f'<circle cx="{cx}" cy="{cy}" r="{r*lvl:.0f}" fill="none" stroke="#334155" stroke-width="0.8"/>'
        for lvl in [0.25, 0.5, 0.75, 1.0]
    )
    # Axis lines
    axis_lines = "".join(
        f'<line x1="{cx}" y1="{cy}" x2="{cx + r*math.cos(math.pi/2-2*math.pi*i/N):.1f}" '
        f'y2="{cy - r*math.sin(math.pi/2-2*math.pi*i/N):.1f}" stroke="#334155" stroke-width="0.8"/>'
        for i in range(N)
    )
    # Radar polygon
    pts = [radar_pt(i, scores[i]) for i in range(N)]
    poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    # Labels
    label_elems = "".join(
        f'<text x="{cx + (r+14)*math.cos(math.pi/2-2*math.pi*i/N):.1f}" '
        f'y="{cy - (r+14)*math.sin(math.pi/2-2*math.pi*i/N) + 4:.1f}" '
        f'text-anchor="middle" font-size="8" fill="#94a3b8">{axes_labels[i]}</text>'
        for i in range(N)
    )
    score_dots = "".join(
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="#22d3ee"/>'
        for x, y in pts
    )
    overall_readiness = round(sum(scores) / len(scores) * 100, 1)

    # Countdown timer (days to event)
    event_date_days = 18  # days until AI World
    hours_left = event_date_days * 24
    prep_pct = round((1 - event_date_days / 30) * 100, 1)

    # Schedule table rows
    schedule_rows = "".join(
        f'<tr><td class="mono">{d["time"]}</td>'
        f'<td>{d["demo"]}</td>'
        f'<td>{d["duration"]}m</td>'
        f'<td style="color:{STATUS_COLOR[d["audience"] if d["audience"] in STATUS_COLOR else "low"]}">{d["audience"]}</td>'
        f'<td><span style="background:{STATUS_COLOR[d["risk"]]};color:#0f172a;padding:1px 8px;border-radius:10px;font-size:0.75rem">{d["risk"]}</span></td>'
        f'</tr>'
        for d in DEMO_SCHEDULE
    )

    # Timeline SVG — Gantt-like (420 wide, 12 demos)
    gantt_h = len(DEMO_SCHEDULE) * 18 + 20
    day_start = 9 * 60  # 9:00am in minutes
    day_end = 17 * 60
    day_span = day_end - day_start

    def time_to_min(t):
        hh, mm = map(int, t.split(":"))
        return hh * 60 + mm

    gantt_bars = "".join(
        f'<rect x="{pad + (time_to_min(d["time"]) - day_start) / day_span * (w - 2*pad):.1f}" '
        f'y="{20 + i*18:.0f}" '
        f'width="{d["duration"] / day_span * (w - 2*pad):.1f}" '
        f'height="14" rx="3" fill="{STATUS_COLOR[d["risk"]]}" opacity="0.82"/>'
        f'<text x="{pad + (time_to_min(d["time"]) - day_start) / day_span * (w - 2*pad) + 3:.1f}" '
        f'y="{30 + i*18:.0f}" font-size="8" fill="#0f172a" font-weight="bold">{d["demo"][:22]}</text>'
        for i, d in enumerate(DEMO_SCHEDULE)
    )
    # Hour tick marks
    hour_ticks = "".join(
        f'<line x1="{pad + (hh*60-day_start)/day_span*(w-2*pad):.1f}" y1="10" '
        f'x2="{pad + (hh*60-day_start)/day_span*(w-2*pad):.1f}" y2="{gantt_h}" '
        f'stroke="#334155" stroke-width="0.7"/>'
        f'<text x="{pad + (hh*60-day_start)/day_span*(w-2*pad):.1f}" y="10" font-size="8" fill="#64748b">{hh:02d}h</text>'
        for hh in range(9, 18)
    )

    return f"""<!DOCTYPE html><html><head><title>AI World Demo Planner</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui;padding:20px}}
h1{{color:#C74634;margin-bottom:4px}}h2{{color:#38bdf8;font-size:0.95rem;margin:0 0 8px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:14px;max-width:1100px}}
.card{{background:#1e293b;padding:18px;border-radius:10px;border:1px solid #334155}}
.stat{{font-size:2rem;font-weight:700;color:#818cf8}}.label{{font-size:0.75rem;color:#94a3b8;margin-top:2px}}
.row{{display:flex;gap:14px}}.badge{{background:#0f172a;border:1px solid #818cf8;padding:3px 10px;border-radius:20px;font-size:0.78rem;color:#818cf8}}
.mono{{font-family:monospace;font-size:0.82rem}}
table{{border-collapse:collapse;width:100%}}td,th{{padding:5px 10px;text-align:left;font-size:0.81rem}}
th{{color:#94a3b8;border-bottom:1px solid #334155}}tr:nth-child(even){{background:#0f172a50}}
.progress{{background:#0f172a;border-radius:6px;height:10px;overflow:hidden;margin-top:4px}}
.progress-bar{{height:100%;border-radius:6px;background:linear-gradient(90deg,#818cf8,#22d3ee)}}
</style></head>
<body>
<h1>AI World Demo Planner</h1>
<p style="color:#94a3b8;margin:0 0 16px">OCI Robot Cloud — AI World 2026 Booth Operations &nbsp;
<span class="badge">port {PORT}</span>
<span class="badge" style="border-color:#22d3ee;color:#22d3ee">T-{event_date_days}d</span>
<span class="badge" style="border-color:#f59e0b;color:#f59e0b">{len(DEMO_SCHEDULE)} demos scheduled</span>
</p>

<div class="row" style="margin-bottom:14px">
  <div class="card" style="flex:1">
    <div class="label">Days to AI World</div><div class="stat">{event_date_days}</div>
    <div class="label">{hours_left}h remaining</div>
  </div>
  <div class="card" style="flex:1">
    <div class="label">Prep Completion</div><div class="stat">{prep_pct}%</div>
    <div class="progress"><div class="progress-bar" style="width:{prep_pct}%"></div></div>
  </div>
  <div class="card" style="flex:1">
    <div class="label">Overall Readiness</div><div class="stat">{overall_readiness}%</div>
    <div class="label">6-axis radar score</div>
  </div>
  <div class="card" style="flex:1">
    <div class="label">Expected Visitors</div><div class="stat">{sum(visitors):,}</div>
    <div class="label">projected day total</div>
  </div>
</div>

<div class="grid">
  <div class="card">
    <h2>Booth Traffic Forecast (Hourly Visitors)</h2>
    <svg width="{w}" height="{h_svg}">
      {visitor_bars}
      <line x1="{pad}" y1="{h_svg-pad}" x2="{w-pad}" y2="{h_svg-pad}" stroke="#334155"/>
    </svg>
  </div>

  <div class="card">
    <h2>Readiness Radar</h2>
    <svg width="220" height="220">
      {grid_circles}
      {axis_lines}
      <polygon points="{poly}" fill="#818cf8" fill-opacity="0.25" stroke="#818cf8" stroke-width="1.5"/>
      {score_dots}
      {label_elems}
    </svg>
  </div>

  <div class="card" style="grid-column:span 2">
    <h2>Demo Gantt Chart</h2>
    <div style="overflow-x:auto">
    <svg width="{w}" height="{gantt_h}">
      {hour_ticks}
      {gantt_bars}
    </svg>
    </div>
    <div style="margin-top:4px;font-size:0.73rem;color:#94a3b8">
      <span style="color:#22d3ee">■</span> low risk &nbsp;
      <span style="color:#f59e0b">■</span> medium risk &nbsp;
      <span style="color:#f87171">■</span> high risk
    </div>
  </div>
</div>

<div class="card" style="margin-top:14px;max-width:1100px">
  <h2>Full Demo Schedule</h2>
  <table>
    <tr><th>Time</th><th>Demo</th><th>Duration</th><th>Audience</th><th>Risk</th></tr>
    {schedule_rows}
  </table>
</div>

<div class="card" style="margin-top:14px;max-width:1100px">
  <h2>Pre-Flight Checklist</h2>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;font-size:0.83rem">
    {''.join(f'<div style="padding:6px 10px;background:#0f172a;border-radius:6px;border-left:3px solid {"#22d3ee" if i%3!=2 else "#f59e0b"}">{item}</div>' for i, item in enumerate(["OCI A100 instance running", "GR00T model weights loaded", "LIBERO env validated", "Isaac Sim licensed + GPU OK", "Demo script rehearsed x3", "Backup slides ready", "Internet failover (4G)", "Staff roles assigned", "Badge scanner tested", "AV equipment checked", "Water/snacks stocked", "Emergency contact list"]))}
  </div>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="AI World Demo Planner")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return build_html()

    @app.get("/health")
    def health():
        return {"status": "ok", "port": PORT, "service": "ai_world_demo_planner"}

    @app.get("/schedule")
    def schedule():
        return {"demos": DEMO_SCHEDULE, "total": len(DEMO_SCHEDULE)}

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(build_html().encode())
    def log_message(self, *a):
        pass

if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
