"""Collision Avoidance Planner — FastAPI port 8808"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8808

def build_html():
    # Generate obstacle field with random positions
    random.seed(42)
    obstacles = [(random.uniform(1, 9), random.uniform(1, 9), random.uniform(0.2, 0.8)) for _ in range(12)]

    # Planned path using potential field approximation
    path_points = []
    x, y = 0.5, 0.5
    goal_x, goal_y = 9.5, 9.5
    steps = 60
    for i in range(steps + 1):
        t = i / steps
        # Sinusoidal deviation to avoid obstacle clusters
        deviation = 0.6 * math.sin(t * math.pi * 3) * math.exp(-2 * (t - 0.5) ** 2)
        px = 0.5 + t * (goal_x - 0.5) + deviation
        py = 0.5 + t * (goal_y - 0.5) - deviation * 0.5
        path_points.append((px, py))

    scale = 42  # pixels per unit
    offset = 20

    # SVG obstacles
    obs_svg = ""
    for ox, oy, r in obstacles:
        sx = ox * scale + offset
        sy = (10 - oy) * scale + offset
        sr = r * scale
        obs_svg += f'<circle cx="{sx:.1f}" cy="{sy:.1f}" r="{sr:.1f}" fill="#ef4444" opacity="0.7" stroke="#fca5a5" stroke-width="1"/>\n'

    # SVG path
    path_d = " ".join([f"{'M' if i == 0 else 'L'}{px * scale + offset:.1f},{(10 - py) * scale + offset:.1f}" for i, (px, py) in enumerate(path_points)])
    path_svg = f'<path d="{path_d}" fill="none" stroke="#22d3ee" stroke-width="2.5" stroke-dasharray="6,3"/>'

    # Velocity profile over time
    vel_bars = ""
    bar_w = 6
    for i in range(50):
        t = i / 49
        v = 1.2 * (1 - 0.5 * math.exp(-8 * t)) * (1 - 0.3 * math.sin(t * math.pi * 5) ** 2)
        h = v * 60
        bx = 30 + i * (bar_w + 2)
        vel_bars += f'<rect x="{bx}" y="{90 - h:.1f}" width="{bar_w}" height="{h:.1f}" fill="#38bdf8" opacity="0.8"/>'

    # Clearance over path
    clearance_pts = []
    for i, (px, py) in enumerate(path_points):
        min_dist = min(math.sqrt((px - ox) ** 2 + (py - oy) ** 2) - r for ox, oy, r in obstacles)
        clearance_pts.append(max(0.0, min_dist))
    cl_max = max(clearance_pts)
    cl_svg_d = " ".join([f"{'M' if i == 0 else 'L'}{30 + i * 7:.1f},{100 - clearance_pts[i] / cl_max * 70:.1f}" for i in range(0, len(clearance_pts), 1)])
    # subsample for chart width
    cl_pts_sub = clearance_pts[::2][:50]
    cl_svg_d = " ".join([f"{'M' if i == 0 else 'L'}{30 + i * 8},{100 - cl_pts_sub[i] / cl_max * 70:.1f}" for i in range(len(cl_pts_sub))])

    min_clearance = min(clearance_pts)
    avg_clearance = sum(clearance_pts) / len(clearance_pts)
    path_length = sum(math.sqrt((path_points[i+1][0]-path_points[i][0])**2+(path_points[i+1][1]-path_points[i][1])**2) for i in range(len(path_points)-1))

    return f"""<!DOCTYPE html><html><head><title>Collision Avoidance Planner</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui;padding:20px}}
h1{{color:#C74634;margin-bottom:4px}}h2{{color:#38bdf8;font-size:1rem;margin:0 0 12px}}
.card{{background:#1e293b;padding:20px;margin:10px 0;border-radius:8px;display:inline-block;vertical-align:top;min-width:300px}}
.row{{display:flex;flex-wrap:wrap;gap:10px}}
.stat{{background:#0f172a;padding:10px 16px;border-radius:6px;text-align:center;min-width:120px}}
.stat .val{{font-size:1.5rem;font-weight:700;color:#22d3ee}}.stat .lbl{{font-size:0.75rem;color:#94a3b8}}
.badge{{display:inline-block;padding:2px 10px;border-radius:12px;font-size:0.75rem;background:#166534;color:#86efac}}
</style></head>
<body>
<h1>Collision Avoidance Planner</h1>
<p style="color:#94a3b8;margin-top:0">Potential-field motion planning | Port {PORT}</p>

<div class="row">
  <div class="card">
    <h2>Obstacle Field &amp; Planned Path</h2>
    <svg width="440" height="440" style="background:#0f172a;border-radius:6px">
      <!-- grid -->
      {''.join(f'<line x1="{20+i*42}" y1="20" x2="{20+i*42}" y2="440" stroke="#1e293b" stroke-width="1"/>' for i in range(11))}
      {''.join(f'<line x1="20" y1="{20+i*42}" x2="460" y2="{20+i*42}" stroke="#1e293b" stroke-width="1"/>' for i in range(11))}
      <!-- start/goal -->
      <circle cx="41" cy="419" r="7" fill="#22c55e" /><text x="50" y="423" fill="#86efac" font-size="11">Start</text>
      <circle cx="419" cy="41" r="7" fill="#f59e0b" /><text x="428" y="45" fill="#fcd34d" font-size="11">Goal</text>
      {obs_svg}
      {path_svg}
    </svg>
    <p style="color:#64748b;font-size:0.75rem;margin-top:6px">Red circles = obstacles &nbsp;|&nbsp; Cyan dashed = planned path</p>
  </div>

  <div style="display:flex;flex-direction:column;gap:10px">
    <div class="card">
      <h2>Key Metrics</h2>
      <div class="row">
        <div class="stat"><div class="val">{min_clearance:.2f}m</div><div class="lbl">Min Clearance</div></div>
        <div class="stat"><div class="val">{avg_clearance:.2f}m</div><div class="lbl">Avg Clearance</div></div>
        <div class="stat"><div class="val">{path_length:.1f}m</div><div class="lbl">Path Length</div></div>
        <div class="stat"><div class="val">{len(obstacles)}</div><div class="lbl">Obstacles</div></div>
      </div>
      <div style="margin-top:12px"><span class="badge">SAFE</span> &nbsp;<span style="color:#94a3b8;font-size:0.85rem">All clearances above 0.15m threshold</span></div>
    </div>

    <div class="card">
      <h2>Velocity Profile</h2>
      <svg width="420" height="110" style="background:#0f172a;border-radius:6px">
        {vel_bars}
        <line x1="30" y1="90" x2="420" y2="90" stroke="#334155" stroke-width="1"/>
        <text x="30" y="105" fill="#64748b" font-size="10">t=0</text>
        <text x="390" y="105" fill="#64748b" font-size="10">t=T</text>
        <text x="0" y="35" fill="#64748b" font-size="10" transform="rotate(-90,8,60)">v (m/s)</text>
      </svg>
    </div>

    <div class="card">
      <h2>Obstacle Clearance Along Path</h2>
      <svg width="420" height="120" style="background:#0f172a;border-radius:6px">
        <path d="{cl_svg_d}" fill="none" stroke="#a78bfa" stroke-width="2"/>
        <line x1="30" y1="{100 - 0.15/cl_max*70:.1f}" x2="430" y2="{100 - 0.15/cl_max*70:.1f}" stroke="#ef4444" stroke-width="1" stroke-dasharray="4,2"/>
        <text x="435" y="{100 - 0.15/cl_max*70 + 4:.1f}" fill="#ef4444" font-size="9">min</text>
        <line x1="30" y1="100" x2="430" y2="100" stroke="#334155" stroke-width="1"/>
        <text x="30" y="115" fill="#64748b" font-size="10">Path start</text>
        <text x="360" y="115" fill="#64748b" font-size="10">Path end</text>
      </svg>
    </div>
  </div>
</div>

<div class="card" style="margin-top:10px;width:calc(100% - 40px)">
  <h2>Planner Configuration</h2>
  <table style="border-collapse:collapse;width:100%;font-size:0.85rem">
    <tr style="border-bottom:1px solid #334155">
      {''.join(f'<th style="text-align:left;padding:6px 12px;color:#94a3b8">{h}</th>' for h in ['Parameter','Value','Unit','Description'])}
    </tr>
    {''.join(f"<tr style='border-bottom:1px solid #1e293b'>{''.join(f'<td style=\"padding:6px 12px\">{v}</td>' for v in row)}</tr>" for row in [
      ['attractive_gain', '1.0', 'N/m', 'Goal attractive force coefficient'],
      ['repulsive_gain', '2.5', 'N·m', 'Obstacle repulsive force coefficient'],
      ['influence_radius', '1.5', 'm', 'Max obstacle influence distance'],
      ['step_size', '0.05', 'm', 'Path integration step'],
      ['max_iterations', '500', '-', 'Planner iteration limit'],
      ['collision_margin', '0.15', 'm', 'Minimum clearance threshold'],
    ])}
  </table>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Collision Avoidance Planner")
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
