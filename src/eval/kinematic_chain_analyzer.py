"""Kinematic Chain Analyzer — FastAPI port 8764"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8764

# Joint definitions for a 7-DOF robot arm
JOINTS = [
    {"name": "shoulder_pan",   "min": -3.14, "max": 3.14,  "mass_kg": 4.2},
    {"name": "shoulder_lift",  "min": -2.09, "max": 2.09,  "mass_kg": 3.8},
    {"name": "elbow_flex",     "min": -3.14, "max": 3.14,  "mass_kg": 2.9},
    {"name": "forearm_roll",   "min": -3.14, "max": 3.14,  "mass_kg": 1.7},
    {"name": "wrist_flex",     "min": -2.09, "max": 2.09,  "mass_kg": 1.2},
    {"name": "wrist_roll",     "min": -3.14, "max": 3.14,  "mass_kg": 0.8},
    {"name": "gripper",        "min":  0.00, "max": 0.085, "mass_kg": 0.5},
]

def forward_kinematics(angles):
    """Simplified planar FK for visualization — returns (x, y, z) end-effector."""
    link_lengths = [0.34, 0.40, 0.32, 0.24, 0.17, 0.10, 0.05]
    x = y = z = 0.0
    cum_angle = 0.0
    for i, (a, l) in enumerate(zip(angles, link_lengths)):
        cum_angle += a
        x += l * math.cos(cum_angle)
        y += l * math.sin(cum_angle)
        z += l * 0.12 * math.sin(a)   # minor z component
    return round(x, 4), round(y, 4), round(z, 4)

def jacobian_condition_number(angles):
    """Approximate condition number via finite differences of Jacobian columns."""
    eps = 1e-5
    cols = []
    base_x, base_y, base_z = forward_kinematics(angles)
    for i in range(len(angles)):
        perturbed = list(angles)
        perturbed[i] += eps
        px, py, pz = forward_kinematics(perturbed)
        cols.append([( px - base_x) / eps, (py - base_y) / eps, (pz - base_z) / eps])
    # Frobenius norm proxy for condition
    frob = math.sqrt(sum(c[0]**2 + c[1]**2 + c[2]**2 for c in cols))
    return round(frob, 3)

def build_html():
    random.seed(42)
    # Generate 40 trajectory waypoints
    n = 40
    t_vals = [i / (n - 1) * 2 * math.pi for i in range(n)]
    angles_traj = [
        [0.6 * math.sin(t + j * 0.7) for j in range(7)]
        for t in t_vals
    ]
    ee_positions = [forward_kinematics(a) for a in angles_traj]
    cond_nums = [jacobian_condition_number(a) for a in angles_traj]

    # Joint torque estimates (tau = m * g * l * cos(theta))
    g = 9.81
    sample_angles = angles_traj[n // 2]
    torques = []
    cum = 0.0
    link_lengths = [0.34, 0.40, 0.32, 0.24, 0.17, 0.10, 0.05]
    for i, j in enumerate(JOINTS):
        cum += j["mass_kg"]
        tau = cum * g * link_lengths[i] * abs(math.cos(sample_angles[i]))
        torques.append(round(tau, 2))

    # Workspace envelope — scatter of reachable EE positions
    ws_pts = []
    random.seed(7)
    for _ in range(120):
        rand_a = [random.uniform(j["min"] * 0.8, j["max"] * 0.8) for j in JOINTS]
        px, py, _ = forward_kinematics(rand_a)
        ws_pts.append((round(px, 3), round(py, 3)))

    # SVG: EE trajectory (x vs y)
    svg_w, svg_h = 420, 220
    ex = [p[0] for p in ee_positions]
    ey = [p[1] for p in ee_positions]
    min_ex, max_ex = min(ex), max(ex)
    min_ey, max_ey = min(ey), max(ey)
    def sx(v): return 20 + (v - min_ex) / (max_ex - min_ex + 1e-9) * (svg_w - 40)
    def sy(v): return svg_h - 20 - (v - min_ey) / (max_ey - min_ey + 1e-9) * (svg_h - 40)
    traj_pts = " ".join(f"{sx(ex[i]):.1f},{sy(ey[i]):.1f}" for i in range(n))
    ws_circles = "".join(
        f'<circle cx="{sx(p[0]):.1f}" cy="{sy(p[1]):.1f}" r="2" fill="#38bdf880"/>'
        for p in ws_pts
    )

    # SVG: condition number over trajectory
    cn_w, cn_h = 420, 160
    cn_min, cn_max = min(cond_nums), max(cond_nums)
    def cnx(i): return 20 + i / (n - 1) * (cn_w - 40)
    def cny(v): return cn_h - 15 - (v - cn_min) / (cn_max - cn_min + 1e-9) * (cn_h - 30)
    cn_pts = " ".join(f"{cnx(i):.1f},{cny(cond_nums[i]):.1f}" for i in range(n))
    cn_fill = cn_pts + f" {cnx(n-1):.1f},{cn_h-15} {cnx(0):.1f},{cn_h-15}"

    # Torque bar chart
    bar_w, bar_h = 420, 160
    bar_max = max(torques)
    bar_colors = ["#C74634", "#f97316", "#eab308", "#22c55e", "#38bdf8", "#818cf8", "#e879f9"]
    bar_rects = ""
    bw = (bar_w - 40) / len(torques)
    for i, (t, c) in enumerate(zip(torques, bar_colors)):
        bh = max(2, (t / bar_max) * (bar_h - 30))
        bx = 20 + i * bw + bw * 0.1
        by = bar_h - 15 - bh
        bar_rects += f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bw*0.8:.1f}" height="{bh:.1f}" fill="{c}" rx="2"/>'
        bar_rects += f'<text x="{bx + bw*0.4:.1f}" y="{bar_h - 2}" font-size="8" fill="#94a3b8" text-anchor="middle">{JOINTS[i]["name"][:6]}</text>'
        bar_rects += f'<text x="{bx + bw*0.4:.1f}" y="{by - 3:.1f}" font-size="9" fill="#e2e8f0" text-anchor="middle">{t}</text>'

    ex_now, ey_now, ez_now = ee_positions[n // 2]
    cond_now = cond_nums[n // 2]
    singularity_warn = "NEAR SINGULARITY" if cond_now > 18 else "nominal"
    sing_color = "#ef4444" if singularity_warn == "NEAR SINGULARITY" else "#22c55e"

    return f"""<!DOCTYPE html><html><head><title>Kinematic Chain Analyzer</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui,sans-serif}}
h1{{color:#C74634;padding:20px 20px 0;margin:0;font-size:1.6rem}}
.subtitle{{color:#94a3b8;padding:4px 20px 16px;font-size:0.85rem}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:0}}
.card{{background:#1e293b;padding:20px;margin:10px;border-radius:10px;border:1px solid #334155}}
.card-wide{{background:#1e293b;padding:20px;margin:10px;border-radius:10px;border:1px solid #334155;grid-column:span 2}}
h2{{color:#38bdf8;margin:0 0 12px;font-size:1rem;text-transform:uppercase;letter-spacing:.05em}}
.kpi-row{{display:flex;gap:16px;flex-wrap:wrap;margin-bottom:16px}}
.kpi{{background:#0f172a;border-radius:8px;padding:12px 18px;min-width:100px}}
.kpi-val{{font-size:1.6rem;font-weight:700;color:#f8fafc}}
.kpi-label{{font-size:0.72rem;color:#64748b;text-transform:uppercase;letter-spacing:.05em}}
.badge{{display:inline-block;padding:3px 10px;border-radius:9999px;font-size:0.75rem;font-weight:600}}
table{{width:100%;border-collapse:collapse;font-size:0.82rem}}
td,th{{padding:6px 10px;text-align:left;border-bottom:1px solid #334155}}
th{{color:#64748b;font-weight:600;text-transform:uppercase;font-size:0.72rem}}
</style></head>
<body>
<h1>Kinematic Chain Analyzer</h1>
<div class="subtitle">7-DOF Robot Arm — Real-time FK / Jacobian / Torque Analysis | Port {PORT}</div>
<div class="grid">

<div class="card-wide">
<div class="kpi-row">
  <div class="kpi"><div class="kpi-val">{ex_now:.3f}</div><div class="kpi-label">EE X (m)</div></div>
  <div class="kpi"><div class="kpi-val">{ey_now:.3f}</div><div class="kpi-label">EE Y (m)</div></div>
  <div class="kpi"><div class="kpi-val">{ez_now:.3f}</div><div class="kpi-label">EE Z (m)</div></div>
  <div class="kpi"><div class="kpi-val">{cond_now:.2f}</div><div class="kpi-label">Jacobian Cond#</div></div>
  <div class="kpi"><div class="kpi-val" style="color:{sing_color}">{singularity_warn}</div><div class="kpi-label">Singularity Status</div></div>
  <div class="kpi"><div class="kpi-val">{sum(torques):.1f}</div><div class="kpi-label">Total Torque (Nm)</div></div>
</div>
</div>

<div class="card">
<h2>End-Effector Workspace (XY Plane)</h2>
<svg width="{svg_w}" height="{svg_h}" style="display:block">
  <rect width="{svg_w}" height="{svg_h}" fill="#0f172a" rx="6"/>
  {ws_circles}
  <polyline points="{traj_pts}" fill="none" stroke="#C74634" stroke-width="2"/>
  <circle cx="{sx(ex_now):.1f}" cy="{sy(ey_now):.1f}" r="5" fill="#f97316"/>
  <text x="{sx(min_ex):.0f}" y="{svg_h-4}" font-size="9" fill="#475569">{min_ex:.2f}</text>
  <text x="{sx(max_ex)-20:.0f}" y="{svg_h-4}" font-size="9" fill="#475569">{max_ex:.2f}</text>
</svg>
<div style="font-size:0.72rem;color:#475569;margin-top:6px">Orange dot = current EE | Red = trajectory | Blue scatter = workspace envelope</div>
</div>

<div class="card">
<h2>Jacobian Condition Number — Trajectory</h2>
<svg width="{cn_w}" height="{cn_h}" style="display:block">
  <rect width="{cn_w}" height="{cn_h}" fill="#0f172a" rx="6"/>
  <polygon points="{cn_fill}" fill="#38bdf820"/>
  <polyline points="{cn_pts}" fill="none" stroke="#38bdf8" stroke-width="2"/>
  <line x1="20" y1="{cny(20):.1f}" x2="{cn_w-20}" y2="{cny(20):.1f}" stroke="#ef444440" stroke-width="1" stroke-dasharray="4,3"/>
  <text x="{cn_w-18}" y="{cny(20)+4:.1f}" font-size="9" fill="#ef4444">singularity</text>
  <text x="20" y="14" font-size="9" fill="#475569">max={cn_max:.1f}</text>
  <text x="20" y="{cn_h-3}" font-size="9" fill="#475569">min={cn_min:.1f}</text>
</svg>
<div style="font-size:0.72rem;color:#475569;margin-top:6px">Dashed red = singularity threshold (cond# &gt; 20)</div>
</div>

<div class="card">
<h2>Joint Torque Estimates (Mid-Trajectory)</h2>
<svg width="{bar_w}" height="{bar_h}" style="display:block">
  <rect width="{bar_w}" height="{bar_h}" fill="#0f172a" rx="6"/>
  {bar_rects}
</svg>
<div style="font-size:0.72rem;color:#475569;margin-top:6px">Torque (Nm) = cumulative mass × g × link_length × |cos(θ)|</div>
</div>

<div class="card">
<h2>Joint Configuration</h2>
<table>
<tr><th>Joint</th><th>Angle (rad)</th><th>Range</th><th>Mass (kg)</th><th>Torque (Nm)</th></tr>
" + "".join(
    f'<tr><td>{j["name"]}</td><td style="color:#38bdf8">{sample_angles[i]:.3f}</td>'
    f'<td style="color:#94a3b8">[{j["min"]:.2f}, {j["max"]:.2f}]</td>'
    f'<td>{j["mass_kg"]}</td>'
    f'<td style="color:#f97316">{torques[i]}</td></tr>'
    for i, j in enumerate(JOINTS)
) + """
</table>
</div>

</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Kinematic Chain Analyzer")
    @app.get("/", response_class=HTMLResponse)
    def index(): return build_html()
    @app.get("/health")
    def health(): return {"status": "ok", "port": PORT}
    @app.get("/fk")
    def fk(q0: float = 0.0, q1: float = 0.0, q2: float = 0.0,
           q3: float = 0.0, q4: float = 0.0, q5: float = 0.0, q6: float = 0.0):
        angles = [q0, q1, q2, q3, q4, q5, q6]
        x, y, z = forward_kinematics(angles)
        cond = jacobian_condition_number(angles)
        return {"ee_position": {"x": x, "y": y, "z": z},
                "jacobian_condition_number": cond,
                "near_singularity": cond > 18}

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
