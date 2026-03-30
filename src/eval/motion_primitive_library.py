"""Motion Primitive Library — FastAPI port 8748"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8748

# Motion primitive categories
PRIMITIVE_TYPES = [
    "reach", "grasp", "lift", "transport", "place",
    "push", "pull", "rotate", "slide", "wave"
]

def gen_primitives():
    random.seed(42)
    primitives = []
    for i, ptype in enumerate(PRIMITIVE_TYPES):
        success = 60 + random.randint(0, 38)
        avg_ms = 180 + random.randint(0, 120)
        calls = random.randint(200, 1800)
        primitives.append({
            "name": ptype,
            "success_rate": success,
            "avg_exec_ms": avg_ms,
            "call_count": calls
        })
    return primitives

def gen_trajectory_svg():
    """SVG of 3 sample trajectories using sin/cos parametric curves."""
    W, H = 480, 200
    colors = ["#38bdf8", "#f472b6", "#4ade80"]
    paths = []
    for j, c in enumerate(colors):
        pts = []
        phase = j * math.pi * 0.6
        amp = 40 + j * 15
        for i in range(60):
            t = i / 59.0
            x = 20 + t * (W - 40)
            y = H / 2 - amp * math.sin(math.pi * t * 2 + phase) * math.cos(t * math.pi + phase * 0.3)
            pts.append(f"{x:.1f},{y:.1f}")
        paths.append(f'<polyline points="{" ".join(pts)}" fill="none" stroke="{c}" stroke-width="2.5" opacity="0.85"/>')
    return f'<svg width="{W}" height="{H}" style="background:#0f172a;border-radius:6px">' + \
           ''.join(paths) + \
           f'<text x="10" y="18" fill="#94a3b8" font-size="11">Trajectory Profiles (3 primitives)</text></svg>'

def gen_exec_time_svg(primitives):
    """Horizontal bar chart of avg execution times."""
    W, H = 480, 220
    max_ms = max(p["avg_exec_ms"] for p in primitives)
    bar_h = 16
    gap = 6
    bars = []
    for i, p in enumerate(primitives):
        y = 10 + i * (bar_h + gap)
        bar_w = (p["avg_exec_ms"] / max_ms) * (W - 140)
        hue = 200 + i * 16
        bars.append(
            f'<rect x="90" y="{y}" width="{bar_w:.1f}" height="{bar_h}" rx="3" fill="hsl({hue},70%,55%)"/>'
            f'<text x="85" y="{y+12}" fill="#cbd5e1" font-size="10" text-anchor="end">{p["name"]}</text>'
            f'<text x="{90+bar_w+4:.1f}" y="{y+12}" fill="#94a3b8" font-size="10">{p["avg_exec_ms"]}ms</text>'
        )
    return f'<svg width="{W}" height="{H}" style="background:#0f172a;border-radius:6px">' + \
           ''.join(bars) + \
           f'<text x="10" y="{H-4}" fill="#94a3b8" font-size="11">Avg Execution Time per Primitive</text></svg>'

def gen_success_polar_svg(primitives):
    """Polar/radar chart of success rates."""
    CX, CY, R = 240, 140, 110
    n = len(primitives)
    rings = [25, 50, 75, 100]
    ring_svgs = []
    for rv in rings:
        ring_r = R * rv / 100
        ring_pts = []
        for i in range(n):
            angle = 2 * math.pi * i / n - math.pi / 2
            ring_pts.append(f"{CX + ring_r * math.cos(angle):.1f},{CY + ring_r * math.sin(angle):.1f}")
        ring_svgs.append(f'<polygon points="{" ".join(ring_pts)}" fill="none" stroke="#334155" stroke-width="1"/>')
        # label
        ring_svgs.append(f'<text x="{CX+3}" y="{CY - ring_r + 4:.1f}" fill="#475569" font-size="9">{rv}%</text>')
    data_pts = []
    for i, p in enumerate(primitives):
        angle = 2 * math.pi * i / n - math.pi / 2
        dr = R * p["success_rate"] / 100
        data_pts.append(f"{CX + dr * math.cos(angle):.1f},{CY + dr * math.sin(angle):.1f}")
        label_r = R + 18
        lx = CX + label_r * math.cos(angle)
        ly = CY + label_r * math.sin(angle)
        ring_svgs.append(f'<text x="{lx:.1f}" y="{ly:.1f}" fill="#94a3b8" font-size="10" text-anchor="middle">{p["name"]}</text>')
    ring_svgs.append(f'<polygon points="{" ".join(data_pts)}" fill="#38bdf855" stroke="#38bdf8" stroke-width="2"/>')
    for pt in data_pts:
        x, y = pt.split(",")
        ring_svgs.append(f'<circle cx="{x}" cy="{y}" r="4" fill="#38bdf8"/>')
    return f'<svg width="480" height="280" style="background:#0f172a;border-radius:6px">' + \
           ''.join(ring_svgs) + \
           f'<text x="10" y="270" fill="#94a3b8" font-size="11">Success Rate Radar (all primitives)</text></svg>'

def build_html():
    primitives = gen_primitives()
    traj_svg = gen_trajectory_svg()
    exec_svg = gen_exec_time_svg(primitives)
    polar_svg = gen_success_polar_svg(primitives)
    total_calls = sum(p["call_count"] for p in primitives)
    avg_success = sum(p["success_rate"] for p in primitives) / len(primitives)
    rows = "".join(
        f'<tr><td>{p["name"]}</td><td>{p["success_rate"]}%</td>'
        f'<td>{p["avg_exec_ms"]}ms</td><td>{p["call_count"]:,}</td></tr>'
        for p in primitives
    )
    return f"""<!DOCTYPE html><html><head><title>Motion Primitive Library</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui;padding:20px}}
h1{{color:#C74634;margin-bottom:4px}}h2{{color:#38bdf8;margin-top:0}}
.card{{background:#1e293b;padding:20px;margin:10px 0;border-radius:8px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:10px}}
.stat{{background:#0f172a;padding:12px 18px;border-radius:6px;text-align:center}}
.stat .val{{font-size:2em;font-weight:700;color:#38bdf8}}
.stat .lbl{{font-size:0.8em;color:#64748b}}
table{{width:100%;border-collapse:collapse;font-size:0.9em}}
th{{background:#0f172a;padding:8px;text-align:left;color:#94a3b8}}
td{{padding:7px 8px;border-bottom:1px solid #1e293b}}
tr:hover td{{background:#172033}}
</style></head>
<body>
<h1>Motion Primitive Library</h1>
<p style="color:#64748b;margin-top:0">Port {PORT} — Real-time primitive execution analytics</p>
<div class="grid">
  <div class="card">
    <div class="stat"><div class="val">{len(primitives)}</div><div class="lbl">Registered Primitives</div></div>
  </div>
  <div class="card">
    <div class="stat"><div class="val">{avg_success:.1f}%</div><div class="lbl">Avg Success Rate</div></div>
  </div>
  <div class="card">
    <div class="stat"><div class="val">{total_calls:,}</div><div class="lbl">Total Executions</div></div>
  </div>
  <div class="card">
    <div class="stat"><div class="val">226ms</div><div class="lbl">P99 Latency</div></div>
  </div>
</div>
<div class="card"><h2>Trajectory Profiles</h2>{traj_svg}</div>
<div class="card"><h2>Execution Time by Primitive</h2>{exec_svg}</div>
<div class="card"><h2>Success Rate Radar</h2>{polar_svg}</div>
<div class="card"><h2>Primitive Registry</h2>
<table><tr><th>Primitive</th><th>Success Rate</th><th>Avg Time</th><th>Calls</th></tr>
{rows}</table></div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Motion Primitive Library")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return build_html()

    @app.get("/health")
    def health():
        return {"status": "ok", "port": PORT}

    @app.get("/primitives")
    def list_primitives():
        return {"primitives": gen_primitives()}

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
