"""AI World Booth Planner — FastAPI port 8839"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8839

DEMO_SLOTS_PER_DAY = 6
EXPECTED_VISITORS = 120
LIVE_ROBOT_DEMOS = 3
EVENT_DATE = "September 2026"

DEMO_SCHEDULE = [
    {"slot": 1, "time": "09:00", "title": "GR00T N1.6 Live Manipulation",    "duration_min": 20, "type": "live_robot"},
    {"slot": 2, "time": "10:30", "title": "Fine-Tuning Pipeline Walkthrough", "duration_min": 15, "type": "screen_demo"},
    {"slot": 3, "time": "12:00", "title": "OCI Robot Cloud Dashboard",        "duration_min": 15, "type": "screen_demo"},
    {"slot": 4, "time": "13:30", "title": "Sim-to-Real Transfer Demo",        "duration_min": 20, "type": "live_robot"},
    {"slot": 5, "time": "15:00", "title": "Partner Integration Showcase",     "duration_min": 15, "type": "screen_demo"},
    {"slot": 6, "time": "16:30", "title": "Closing: DAgger + Eval Results",   "duration_min": 20, "type": "live_robot"},
]

COLOR_MAP = {"live_robot": "#C74634", "screen_demo": "#38bdf8"}

def build_svg_timeline():
    start_h = 9.0
    end_h = 17.5
    total_h = end_h - start_h
    svg_w = 600
    svg_h = 260
    bar_h = 28
    y_base = 30
    gap = (svg_h - y_base - bar_h - 20) / (len(DEMO_SCHEDULE) - 1)
    rects = ""
    for i, slot in enumerate(DEMO_SCHEDULE):
        hh, mm = map(int, slot["time"].split(":"))
        t_frac = ((hh + mm / 60) - start_h) / total_h
        x = math.floor(t_frac * (svg_w - 120)) + 60
        w = math.floor((slot["duration_min"] / 60) / total_h * (svg_w - 120))
        w = max(w, 30)
        color = COLOR_MAP[slot["type"]]
        y = y_base + i * gap
        rects += f'<rect x="{x}" y="{y:.0f}" width="{w}" height="{bar_h}" fill="{color}" rx="3"/>'
        rects += f'<text x="{x + w + 4}" y="{y + 18:.0f}" fill="#e2e8f0" font-size="10">{slot["time"]} {slot["title"][:28]}</text>'
    # axis
    axis = f'<line x1="60" y1="{svg_h-10}" x2="{svg_w-20}" y2="{svg_h-10}" stroke="#475569" stroke-width="1"/>'
    for h in range(9, 18):
        xp = math.floor(((h - start_h) / total_h) * (svg_w - 120)) + 60
        axis += f'<text x="{xp}" y="{svg_h-2}" text-anchor="middle" fill="#64748b" font-size="9">{h:02d}:00</text>'
    legend = (f'<rect x="60" y="8" width="12" height="12" fill="#C74634" rx="2"/>'
              f'<text x="76" y="19" fill="#e2e8f0" font-size="10">Live Robot</text>'
              f'<rect x="150" y="8" width="12" height="12" fill="#38bdf8" rx="2"/>'
              f'<text x="166" y="19" fill="#e2e8f0" font-size="10">Screen Demo</text>')
    return f'<svg width="{svg_w}" height="{svg_h}" xmlns="http://www.w3.org/2000/svg">{legend}{axis}{rects}</svg>'

def build_html():
    chart = build_svg_timeline()
    rows = "".join(
        f'<tr><td>{s["slot"]}</td><td>{s["time"]}</td><td>{s["title"]}</td>'
        f'<td>{s["duration_min"]}m</td><td style="color:{COLOR_MAP[s["type"]]}">{
            "Live Robot" if s["type"]=="live_robot" else "Screen Demo"}</td></tr>'
        for s in DEMO_SCHEDULE
    )
    return f"""<!DOCTYPE html><html><head><title>AI World Booth Planner</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui;padding:20px}}
h1{{color:#C74634}}h2{{color:#38bdf8}}.card{{background:#1e293b;padding:20px;margin:10px;border-radius:8px}}
.metric{{display:inline-block;margin:12px 20px 0 0}}.metric .val{{font-size:2em;font-weight:bold;color:#38bdf8}}
.metric .lbl{{color:#94a3b8;font-size:0.85em}}
table{{border-collapse:collapse;width:100%}}th,td{{padding:8px 12px;text-align:left;border-bottom:1px solid #334155}}
th{{color:#38bdf8;font-weight:600}}</style></head>
<body><h1>AI World Booth Planner</h1>
<p style="color:#94a3b8">September 2026 AI World Conference Demo Schedule — port {PORT}</p>
<div class="card"><h2>Key Metrics</h2>
  <div class="metric"><div class="val">{DEMO_SLOTS_PER_DAY}</div><div class="lbl">Demo slots/day</div></div>
  <div class="metric"><div class="val">{EXPECTED_VISITORS}</div><div class="lbl">Expected visitors</div></div>
  <div class="metric"><div class="val">{LIVE_ROBOT_DEMOS}</div><div class="lbl">Live robot demos</div></div>
  <div class="metric"><div class="val">{EVENT_DATE}</div><div class="lbl">Event</div></div>
</div>
<div class="card"><h2>Daily Timeline</h2>
{chart}
</div>
<div class="card"><h2>Demo Schedule</h2>
<table><thead><tr><th>#</th><th>Time</th><th>Title</th><th>Duration</th><th>Type</th></tr></thead>
<tbody>{rows}</tbody></table>
</div>
<div class="card"><h2>Visitor Flow Notes</h2>
<p>Peak visitor windows: 10:00–11:30 and 14:00–16:00. Live robot demos draw 3× the crowd of screen demos.
Station capacity: 25 standing. Queue management via digital sign outside booth.</p>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="AI World Booth Planner")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return build_html()

    @app.get("/health")
    def health():
        return {"status": "ok", "port": PORT}

    @app.get("/schedule")
    def schedule():
        return {"event": EVENT_DATE, "slots": DEMO_SCHEDULE}

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
