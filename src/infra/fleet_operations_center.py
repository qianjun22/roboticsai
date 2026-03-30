"""Fleet Operations Center — FastAPI port 8835"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8835

TOTAL_UNITS = 47
ACTIVE_UNITS = 44
MAINTENANCE_UNITS = 3
FLEET_AVAILABILITY = 0.94

# Deterministic robot unit data
def _get_units():
    random.seed(55)
    tasks = ["Pick & Place", "Assembly", "Inspection", "Packaging", "Transport",
             "Welding", "Painting", "Sorting", "Loading", "Calibration"]
    units = []
    for i in range(TOTAL_UNITS):
        uid = f"RBT-{2000+i:03d}"
        if i < MAINTENANCE_UNITS:
            status = "maintenance"
            task = "Maintenance"
            uptime = 0.0
        elif i < ACTIVE_UNITS + MAINTENANCE_UNITS:
            status = "active"
            task = random.choice(tasks)
            uptime = round(random.uniform(0.88, 0.999), 3)
        else:
            status = "idle"
            task = "Idle"
            uptime = round(random.uniform(0.92, 0.99), 3)
        next_maint_days = random.randint(1, 30)
        units.append({"id": uid, "status": status, "task": task,
                      "uptime": uptime, "next_maint": next_maint_days})
    return units

def _build_fleet_grid_svg(units):
    """SVG grid of robot status indicators: green=active, amber=idle, red=maintenance."""
    cols = 8
    rows = math.ceil(len(units) / cols)
    cell = 52
    pad = 10
    w = cols * cell + pad * 2
    h = rows * cell + pad * 2

    color_map = {"active": "#4ade80", "idle": "#f59e0b", "maintenance": "#f87171"}
    stroke_map = {"active": "#166534", "idle": "#92400e", "maintenance": "#991b1b"}

    elements = []
    for idx, u in enumerate(units):
        col = idx % cols
        row = idx // cols
        cx = pad + col * cell + cell / 2
        cy = pad + row * cell + cell / 2
        r = 18
        fill = color_map[u["status"]]
        stroke = stroke_map[u["status"]]
        # Outer ring
        elements.append(
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r}" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="2" opacity="0.9"/>'
        )
        # Robot icon — simple body outline
        elements.append(
            f'<rect x="{cx-7:.1f}" y="{cy-6:.1f}" width="14" height="12" rx="2" '
            f'fill="#0f172a" opacity="0.6"/>'
        )
        elements.append(
            f'<rect x="{cx-4:.1f}" y="{cy-10:.1f}" width="8" height="6" rx="2" '
            f'fill="#0f172a" opacity="0.6"/>'
        )
        # Uptime arc (active only)
        if u["status"] == "active" and u["uptime"] > 0:
            angle = u["uptime"] * 2 * math.pi
            arc_r = r + 5
            x1 = cx + arc_r * math.sin(0)
            y1 = cy - arc_r * math.cos(0)
            x2 = cx + arc_r * math.sin(angle)
            y2 = cy - arc_r * math.cos(angle)
            large = 1 if angle > math.pi else 0
            elements.append(
                f'<path d="M {x1:.1f} {y1:.1f} A {arc_r} {arc_r} 0 {large} 1 {x2:.1f} {y2:.1f}" '
                f'fill="none" stroke="#38bdf8" stroke-width="2" opacity="0.7"/>'
            )
        # Unit ID label
        label = u["id"].replace("RBT-", "")
        elements.append(
            f'<text x="{cx:.1f}" y="{cy+r+11:.1f}" text-anchor="middle" '
            f'font-size="9" fill="#94a3b8">{label}</text>'
        )

    return (
        f'<svg viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
        f'xmlns="http://www.w3.org/2000/svg" style="border-radius:6px;background:#0f172a;">'
        + "\n".join(elements) +
        f'<rect x="0" y="0" width="{w}" height="{h}" fill="none" stroke="#334155" stroke-width="1"/>'
        f'</svg>'
    )

def _build_schedule_svg(units):
    """Maintenance schedule bar chart — days until next maintenance."""
    w, h = 480, 140
    maint_units = [u for u in units if u["status"] != "maintenance"][:12]
    n = len(maint_units)
    bar_w = (w - 60) / n
    max_days = 30
    bars = []
    for i, u in enumerate(maint_units):
        d = u["next_maint"]
        bar_h = (d / max_days) * (h - 30)
        x = 40 + i * bar_w + bar_w * 0.1
        y = h - 20 - bar_h
        urgency = "#f87171" if d <= 5 else ("#f59e0b" if d <= 14 else "#4ade80")
        bars.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w*0.8:.1f}" height="{bar_h:.1f}" '
            f'fill="{urgency}" rx="2" opacity="0.85"/>'
        )
        bars.append(
            f'<text x="{x+bar_w*0.4:.1f}" y="{y-4:.1f}" text-anchor="middle" '
            f'font-size="9" fill="#e2e8f0">{d}d</text>'
        )
        bars.append(
            f'<text x="{x+bar_w*0.4:.1f}" y="{h-6:.1f}" text-anchor="middle" '
            f'font-size="8" fill="#64748b">{u["id"].replace("RBT-","")}</text>'
        )
    # Axes
    bars.append(f'<line x1="38" y1="10" x2="38" y2="{h-18}" stroke="#334155" stroke-width="1"/>')
    bars.append(f'<line x1="38" y1="{h-18}" x2="{w-4}" y2="{h-18}" stroke="#334155" stroke-width="1"/>')
    return (
        f'<svg viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
        f'xmlns="http://www.w3.org/2000/svg" style="border-radius:6px;background:#0f172a;">'
        + "\n".join(bars) +
        f'<text x="10" y="{h//2}" font-size="9" fill="#94a3b8" transform="rotate(-90 10 {h//2})">Days</text>'
        f'</svg>'
    )

def build_html():
    units = _get_units()
    grid_svg = _build_fleet_grid_svg(units)
    sched_svg = _build_schedule_svg(units)
    avail_pct = int(FLEET_AVAILABILITY * 100)
    active_tasks = {u["task"] for u in units if u["status"] == "active"}
    return f"""<!DOCTYPE html><html><head><title>Fleet Operations Center</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui;padding:20px}}
h1{{color:#C74634;margin-bottom:4px}}h2{{color:#38bdf8;margin:12px 0 8px}}
.card{{background:#1e293b;padding:20px;margin:10px 0;border-radius:8px}}
.metrics{{display:flex;gap:20px;flex-wrap:wrap;margin-bottom:16px}}
.metric{{background:#0f172a;padding:12px 18px;border-radius:6px;text-align:center;min-width:120px}}
.metric .val{{font-size:2rem;font-weight:700;color:#38bdf8}}
.metric .lbl{{font-size:0.78rem;color:#94a3b8;margin-top:4px}}
.legend{{display:flex;gap:14px;flex-wrap:wrap;margin-top:10px;font-size:0.8rem}}
.dot{{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:4px}}
table{{width:100%;border-collapse:collapse;font-size:0.82rem}}
th{{color:#94a3b8;text-align:left;padding:6px 8px;border-bottom:1px solid #334155}}
td{{padding:5px 8px;border-bottom:1px solid #1e293b}}
.badge{{padding:2px 8px;border-radius:9999px;font-size:0.75rem;font-weight:600}}
.active{{background:#14532d;color:#4ade80}}.idle{{background:#451a03;color:#f59e0b}}.maintenance{{background:#450a0a;color:#f87171}}
</style></head>
<body>
<h1>Fleet Operations Center</h1>
<p style="color:#94a3b8;margin-top:0">Port {PORT} &nbsp;|&nbsp; Unified command center for all deployed robot units</p>

<div class="card">
  <h2>Fleet Summary</h2>
  <div class="metrics">
    <div class="metric"><div class="val">{TOTAL_UNITS}</div><div class="lbl">Total Units</div></div>
    <div class="metric"><div class="val">{ACTIVE_UNITS}</div><div class="lbl">Active Units</div></div>
    <div class="metric"><div class="val">{avail_pct}%</div><div class="lbl">Fleet Availability</div></div>
    <div class="metric"><div class="val">{MAINTENANCE_UNITS}</div><div class="lbl">In Maintenance</div></div>
    <div class="metric"><div class="val">{len(active_tasks)}</div><div class="lbl">Unique Tasks Running</div></div>
  </div>
</div>

<div class="card">
  <h2>Robot Unit Status Grid</h2>
  <p style="color:#94a3b8;font-size:0.82rem">Each circle = one robot unit. Blue arc = uptime. Numbers = unit IDs.</p>
  {grid_svg}
  <div class="legend">
    <span><span class="dot" style="background:#4ade80"></span>Active</span>
    <span><span class="dot" style="background:#f59e0b"></span>Idle</span>
    <span><span class="dot" style="background:#f87171"></span>Maintenance</span>
    <span style="color:#38bdf8">— Uptime arc</span>
  </div>
</div>

<div class="card">
  <h2>Task Assignments (Active Units)</h2>
  <table>
    <thead><tr><th>Unit ID</th><th>Task</th><th>Uptime</th><th>Next Maintenance</th></tr></thead>
    <tbody>
    {''.join(f'<tr><td>{u["id"]}</td><td>{u["task"]}</td><td>{u["uptime"]*100:.1f}%</td><td>{u["next_maint"]}d</td></tr>' for u in units if u["status"] == "active")}
    </tbody>
  </table>
</div>

<div class="card">
  <h2>Maintenance Schedule (days until next service)</h2>
  <p style="color:#94a3b8;font-size:0.82rem">Red = urgent (&le;5d), Amber = soon (&le;14d), Green = OK.</p>
  {sched_svg}
</div>

<div class="card">
  <h2>Units Currently in Maintenance</h2>
  <table>
    <thead><tr><th>Unit ID</th><th>Status</th></tr></thead>
    <tbody>
    {''.join(f'<tr><td>{u["id"]}</td><td><span class="badge maintenance">Maintenance</span></td></tr>' for u in units if u["status"] == "maintenance")}
    </tbody>
  </table>
</div>

</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Fleet Operations Center")
    @app.get("/", response_class=HTMLResponse)
    def index(): return build_html()
    @app.get("/health")
    def health(): return {"status": "ok", "port": PORT}

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
