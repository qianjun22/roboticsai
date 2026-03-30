"""Proprioceptive State Estimator — FastAPI port 8780"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8780

def build_html():
    # Generate joint angle data using sine waves + noise
    n_joints = 7
    n_steps = 60
    joint_names = ["shoulder_pan", "shoulder_lift", "elbow", "wrist_1", "wrist_2", "wrist_3", "gripper"]
    joint_colors = ["#C74634", "#38bdf8", "#34d399", "#fbbf24", "#a78bfa", "#f472b6", "#fb923c"]

    # Simulate joint angle trajectories
    trajectories = []
    for j in range(n_joints):
        phase = j * math.pi / n_joints
        freq = 0.8 + j * 0.15
        amp = 30 + j * 8
        pts = []
        for t in range(n_steps):
            angle = amp * math.sin(freq * t * 0.18 + phase) + random.gauss(0, 2.0)
            pts.append(round(angle, 3))
        trajectories.append(pts)

    # Force/torque estimates
    ft_labels = ["Fx", "Fy", "Fz", "Tx", "Ty", "Tz"]
    ft_values = [round(random.gauss(0, 4) + math.sin(i * 0.8) * 6, 2) for i in range(6)]
    ft_max = 20.0

    # IMU orientation data (roll, pitch, yaw)
    t_now = random.uniform(0, 2 * math.pi)
    roll  = round(math.degrees(0.12 * math.sin(t_now)), 2)
    pitch = round(math.degrees(0.08 * math.cos(t_now * 1.3)), 2)
    yaw   = round(math.degrees(0.05 * math.sin(t_now * 0.7 + 1.1)), 2)

    # Contact state probabilities
    contact_probs = [round(max(0.0, min(1.0, random.gauss(0.6, 0.18))), 3) for _ in range(4)]
    contact_labels = ["Left Palm", "Right Palm", "Left Finger", "Right Finger"]

    # Build SVG for joint angle chart
    chart_w, chart_h = 700, 180
    svg_lines = []
    for j_idx, pts in enumerate(trajectories):
        min_v, max_v = -80, 80
        coords = []
        for i, v in enumerate(pts):
            x = int(i * (chart_w - 40) / (n_steps - 1)) + 20
            y = int(chart_h - 20 - (v - min_v) / (max_v - min_v) * (chart_h - 40))
            coords.append(f"{x},{y}")
        path_d = "M " + " L ".join(coords)
        svg_lines.append(f'<path d="{path_d}" stroke="{joint_colors[j_idx]}" stroke-width="1.5" fill="none" opacity="0.85"/>')

    joint_svg = '\n'.join(svg_lines)

    # Build SVG for FT bar chart
    ft_bars = []
    for i, (label, val) in enumerate(zip(ft_labels, ft_values)):
        bar_x = 30 + i * 90
        bar_h = int(abs(val) / ft_max * 80)
        bar_y = 100 - bar_h if val >= 0 else 100
        color = "#38bdf8" if val >= 0 else "#f87171"
        ft_bars.append(
            f'<rect x="{bar_x}" y="{bar_y}" width="60" height="{bar_h}" fill="{color}" rx="3"/>'
            f'<text x="{bar_x+30}" y="115" text-anchor="middle" fill="#94a3b8" font-size="11">{label}</text>'
            f'<text x="{bar_x+30}" y="{bar_y - 4}" text-anchor="middle" fill="#e2e8f0" font-size="10">{val}</text>'
        )
    ft_svg = '\n'.join(ft_bars)

    # Contact probability arcs (simple semicircle gauges)
    contact_svgs = []
    for i, (label, prob) in enumerate(zip(contact_labels, contact_probs)):
        cx, cy, r = 60, 55, 40
        angle = prob * math.pi
        ex = cx + r * math.cos(math.pi - angle)
        ey = cy - r * math.sin(math.pi - angle)
        large = 1 if angle > math.pi / 2 else 0
        color = "#34d399" if prob > 0.5 else "#fbbf24"
        contact_svgs.append(
            f'<div style="display:inline-block;text-align:center;margin:0 8px">'
            f'<svg width="120" height="70">'
            f'<path d="M {cx-r},{cy} A {r},{r} 0 0,1 {cx+r},{cy}" stroke="#334155" stroke-width="8" fill="none"/>'
            f'<path d="M {cx-r},{cy} A {r},{r} 0 {large},1 {ex},{ey}" stroke="{color}" stroke-width="8" fill="none"/>'
            f'<text x="{cx}" y="{cy+5}" text-anchor="middle" fill="#e2e8f0" font-size="13" font-weight="bold">{int(prob*100)}%</text>'
            f'</svg>'
            f'<div style="font-size:11px;color:#94a3b8">{label}</div></div>'
        )
    contact_html = ''.join(contact_svgs)

    # Velocity & acceleration estimates
    vel_data = [round(random.gauss(0, 0.3), 3) for _ in range(n_joints)]
    acc_data = [round(random.gauss(0, 0.8), 3) for _ in range(n_joints)]

    joint_rows = ""
    for j in range(n_joints):
        last_angle = round(trajectories[j][-1], 2)
        status_color = "#34d399" if abs(last_angle) < 60 else "#fbbf24"
        joint_rows += (
            f'<tr><td style="color:{joint_colors[j]}">{joint_names[j]}</td>'
            f'<td style="color:{status_color}">{last_angle}°</td>'
            f'<td>{vel_data[j]} rad/s</td>'
            f'<td>{acc_data[j]} rad/s²</td></tr>'
        )

    return f"""<!DOCTYPE html><html><head><title>Proprioceptive State Estimator</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui;padding:20px}}
h1{{color:#C74634;margin:0 0 4px 0;font-size:1.6rem}}
h2{{color:#38bdf8;font-size:1rem;margin:0 0 12px 0}}
.card{{background:#1e293b;padding:20px;margin:10px 0;border-radius:8px;border:1px solid #334155}}
.grid2{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}
.badge{{display:inline-block;padding:3px 10px;border-radius:12px;font-size:12px;font-weight:600;margin-right:6px}}
table{{width:100%;border-collapse:collapse;font-size:13px}}
th{{color:#64748b;text-align:left;padding:6px 8px;border-bottom:1px solid #334155}}
td{{padding:5px 8px;border-bottom:1px solid #1e293b}}
.metric{{font-size:2rem;font-weight:700;color:#38bdf8}}
.label{{font-size:12px;color:#64748b;margin-top:2px}}
</style></head>
<body>
<h1>Proprioceptive State Estimator</h1>
<p style="color:#64748b;margin:0 0 16px 0">Real-time joint state estimation from encoder + IMU + F/T sensor fusion — Port {PORT}</p>

<div style="display:flex;gap:12px;margin-bottom:12px">
  <div class="card" style="flex:1;text-align:center">
    <div class="metric">{roll}°</div><div class="label">Roll</div>
  </div>
  <div class="card" style="flex:1;text-align:center">
    <div class="metric">{pitch}°</div><div class="label">Pitch</div>
  </div>
  <div class="card" style="flex:1;text-align:center">
    <div class="metric">{yaw}°</div><div class="label">Yaw (IMU)</div>
  </div>
  <div class="card" style="flex:1;text-align:center">
    <div class="metric" style="color:#34d399">227ms</div><div class="label">Latency</div>
  </div>
</div>

<div class="card">
  <h2>Joint Angle Trajectories (last {n_steps} steps)</h2>
  <svg width="{chart_w}" height="{chart_h}" style="display:block">
    <line x1="20" y1="{chart_h//2}" x2="{chart_w-20}" y2="{chart_h//2}" stroke="#334155" stroke-width="1" stroke-dasharray="4"/>
    {joint_svg}
  </svg>
  <div style="margin-top:8px;display:flex;flex-wrap:wrap;gap:8px">
    {''.join(f'<span class="badge" style="background:{joint_colors[j]}20;color:{joint_colors[j]}">{joint_names[j]}</span>' for j in range(n_joints))}
  </div>
</div>

<div class="grid2">
  <div class="card">
    <h2>Joint State Table</h2>
    <table>
      <thead><tr><th>Joint</th><th>Angle</th><th>Velocity</th><th>Acceleration</th></tr></thead>
      <tbody>{joint_rows}</tbody>
    </table>
  </div>
  <div class="card">
    <h2>Force / Torque Estimates (N, Nm)</h2>
    <svg width="560" height="130">
      <line x1="0" y1="100" x2="560" y2="100" stroke="#334155" stroke-width="1"/>
      <line x1="0" y1="20" x2="560" y2="20" stroke="#334155" stroke-width="1" stroke-dasharray="3"/>
      {ft_svg}
    </svg>
  </div>
</div>

<div class="card">
  <h2>Contact State Probabilities</h2>
  <div style="display:flex;justify-content:space-around;flex-wrap:wrap;padding:8px 0">
    {contact_html}
  </div>
</div>

<div class="card" style="background:#0f172a;border-color:#C7463440">
  <h2 style="color:#C74634">Estimator Health</h2>
  <div style="display:flex;gap:20px;flex-wrap:wrap;font-size:13px">
    <span><span style="color:#34d399">●</span> Encoder fusion OK</span>
    <span><span style="color:#34d399">●</span> IMU sync OK</span>
    <span><span style="color:#34d399">●</span> F/T calibration OK</span>
    <span><span style="color:#fbbf24">●</span> Slip detection WARN</span>
    <span><span style="color:#34d399">●</span> Kalman filter converged</span>
  </div>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Proprioceptive State Estimator")
    @app.get("/", response_class=HTMLResponse)
    def index(): return build_html()
    @app.get("/health")
    def health(): return {"status": "ok", "port": PORT}
    @app.get("/state")
    def state():
        n_joints = 7
        joint_names = ["shoulder_pan","shoulder_lift","elbow","wrist_1","wrist_2","wrist_3","gripper"]
        return {
            "joints": [
                {"name": joint_names[j], "angle_deg": round(random.gauss(0, 30), 3),
                 "velocity_rad_s": round(random.gauss(0, 0.3), 3)}
                for j in range(n_joints)
            ],
            "imu": {"roll": round(random.gauss(0, 5), 2), "pitch": round(random.gauss(0, 5), 2),
                    "yaw": round(random.gauss(0, 5), 2)},
            "contact_probs": [round(random.random(), 3) for _ in range(4)]
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
