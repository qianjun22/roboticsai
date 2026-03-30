"""Object Manipulation Planner — FastAPI port 8756"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8756

def build_html():
    # Generate trajectory planning data with math/random
    random.seed(42)
    num_steps = 30
    joint_angles = [math.sin(i * 0.25) * 45 + random.uniform(-3, 3) for i in range(num_steps)]
    gripper_force = [20 + math.cos(i * 0.3) * 15 + random.uniform(-2, 2) for i in range(num_steps)]
    success_rate = [min(100, 60 + i * 1.3 + random.uniform(-4, 4)) for i in range(num_steps)]

    # SVG trajectory chart
    w, h = 560, 140
    def pts(vals, mn, mx):
        return " ".join(
            f"{int(10 + i * (w - 20) / (num_steps - 1))},{int(h - 10 - (v - mn) / (mx - mn + 1e-9) * (h - 20))}"
            for i, v in enumerate(vals)
        )

    traj_pts = pts(joint_angles, min(joint_angles), max(joint_angles))
    force_pts = pts(gripper_force, min(gripper_force), max(gripper_force))
    sr_pts = pts(success_rate, 50, 100)

    # Task queue mock data
    tasks = [
        ("Pick cube A → bin 2", "92%", "#22c55e"),
        ("Stack ring on peg", "87%", "#22c55e"),
        ("Insert peg in hole", "74%", "#facc15"),
        ("Pour liquid sample", "61%", "#facc15"),
        ("Handover to robot B", "88%", "#22c55e"),
    ]
    task_rows = "".join(
        f"<tr><td style='padding:6px 12px'>{t}</td>"
        f"<td style='padding:6px 12px;color:{c};font-weight:bold'>{r}</td></tr>"
        for t, r, c in tasks
    )

    # IK solve time histogram bars
    ik_times = [random.uniform(1.2, 8.5) for _ in range(20)]
    bins = [0] * 8
    for v in ik_times:
        b = min(7, int((v - 1.2) / 7.3 * 8))
        bins[b] += 1
    bar_w = 560 // 8
    hist_bars = "".join(
        f"<rect x='{i * bar_w + 4}' y='{100 - bins[i] * 18}' width='{bar_w - 8}' height='{bins[i] * 18}' fill='#38bdf8' opacity='0.85'/>"
        for i in range(8)
    )

    return f"""<!DOCTYPE html><html><head><title>Object Manipulation Planner</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui}}
h1{{color:#C74634;padding:20px 20px 0;margin:0}}
h2{{color:#38bdf8;margin:0 0 12px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:0}}
.card{{background:#1e293b;padding:20px;margin:10px;border-radius:8px}}
.stat{{font-size:2em;font-weight:bold;color:#38bdf8}}
.label{{color:#94a3b8;font-size:0.85em;margin-top:4px}}
.stats-row{{display:flex;gap:20px;flex-wrap:wrap}}
.stat-box{{background:#0f172a;padding:12px 20px;border-radius:6px;min-width:120px}}
table{{width:100%;border-collapse:collapse}}
td{{border-bottom:1px solid #334155}}
</style></head>
<body>
<h1>Object Manipulation Planner</h1>
<p style='color:#94a3b8;padding:0 20px;margin:4px 0 0'>Port {PORT} — Real-time motion planning & grasp optimization for robot arm tasks</p>

<div class='stats-row' style='padding:10px 10px 0'>
  <div class='card stat-box'><div class='stat'>94.2%</div><div class='label'>Grasp Success Rate</div></div>
  <div class='card stat-box'><div class='stat'>3.1ms</div><div class='label'>Avg IK Solve Time</div></div>
  <div class='card stat-box'><div class='stat'>7-DOF</div><div class='label'>Arm Joints</div></div>
  <div class='card stat-box'><div class='stat'>2,847</div><div class='label'>Plans Today</div></div>
</div>

<div class='grid'>
  <div class='card'>
    <h2>Joint Angle Trajectory (deg)</h2>
    <svg width='{w}' height='{h}' style='background:#0f172a;border-radius:4px'>
      <polyline points='{traj_pts}' fill='none' stroke='#38bdf8' stroke-width='2'/>
      <text x='10' y='14' fill='#64748b' font-size='11'>J1 trajectory over 30 steps</text>
    </svg>
  </div>
  <div class='card'>
    <h2>Gripper Force Profile (N)</h2>
    <svg width='{w}' height='{h}' style='background:#0f172a;border-radius:4px'>
      <polyline points='{force_pts}' fill='none' stroke='#f59e0b' stroke-width='2'/>
      <text x='10' y='14' fill='#64748b' font-size='11'>Grip force vs. contact steps</text>
    </svg>
  </div>
  <div class='card'>
    <h2>Task Success Rate Trend (%)</h2>
    <svg width='{w}' height='{h}' style='background:#0f172a;border-radius:4px'>
      <polyline points='{sr_pts}' fill='none' stroke='#22c55e' stroke-width='2'/>
      <line x1='10' y1='{int(h - 10 - 0.5 * (h - 20))}' x2='{w - 10}' y2='{int(h - 10 - 0.5 * (h - 20))}'
            stroke='#ef4444' stroke-width='1' stroke-dasharray='4 4'/>
      <text x='10' y='14' fill='#64748b' font-size='11'>Rolling success rate (red = 75% target)</text>
    </svg>
  </div>
  <div class='card'>
    <h2>IK Solve Time Histogram</h2>
    <svg width='{w}' height='110' style='background:#0f172a;border-radius:4px'>
      {hist_bars}
      <text x='10' y='14' fill='#64748b' font-size='11'>Distribution of IK solve times (ms)</text>
    </svg>
  </div>
</div>

<div class='card' style='margin:10px'>
  <h2>Active Task Queue</h2>
  <table>{task_rows}</table>
</div>

</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Object Manipulation Planner")
    @app.get("/", response_class=HTMLResponse)
    def index(): return build_html()
    @app.get("/health")
    def health(): return {"status": "ok", "port": PORT}
    @app.get("/plan")
    def plan(obj: str = "cube", target: str = "bin_1"):
        solve_ms = round(random.uniform(1.5, 6.2), 2)
        success = random.random() > 0.08
        return {
            "object": obj, "target": target,
            "ik_solve_ms": solve_ms, "success": success,
            "joint_waypoints": [round(math.sin(i * 0.4) * 40, 2) for i in range(7)],
            "grasp_force_n": round(random.uniform(18, 35), 1)
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
