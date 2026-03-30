"""Action Sequence Validator — FastAPI port 8730"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8730

def build_html():
    random.seed(42)
    # Generate action sequence validation data
    n_steps = 20
    joint_names = ["shoulder_pan", "shoulder_lift", "elbow", "wrist_1", "wrist_2", "wrist_3", "gripper"]
    # Simulate predicted vs ground-truth joint trajectories
    gt_traj = [[math.sin(i * 0.3 + j * 0.7) * 60 + random.gauss(0, 2) for i in range(n_steps)] for j in range(7)]
    pred_traj = [[gt_traj[j][i] + random.gauss(0, 5 + 2 * math.sin(i * 0.5)) for i in range(n_steps)] for j in range(7)]
    errors = [[abs(pred_traj[j][i] - gt_traj[j][i]) for i in range(n_steps)] for j in range(7)]
    mae_per_joint = [sum(errors[j]) / n_steps for j in range(7)]
    overall_mae = sum(mae_per_joint) / 7
    max_err = max(max(e) for e in errors)

    # Validation pass/fail per step (fail if any joint error > threshold)
    threshold = 12.0
    step_status = ["PASS" if all(errors[j][i] < threshold else False for j in range(7)) else "FAIL" for i in range(n_steps)]
    pass_rate = step_status.count("PASS") / n_steps * 100

    # SVG: joint trajectory comparison (first 3 joints), width=600 h=160
    svg_w, svg_h = 600, 160
    pad = 30
    chart_w = svg_w - 2 * pad
    chart_h = svg_h - 2 * pad
    colors = ["#38bdf8", "#f472b6", "#4ade80", "#fb923c", "#a78bfa", "#facc15", "#f87171"]

    def traj_path(traj_vals, color, dashed=False):
        mn, mx = -80, 80
        pts = []
        for i, v in enumerate(traj_vals):
            x = pad + (i / (n_steps - 1)) * chart_w
            y = pad + (1 - (v - mn) / (mx - mn)) * chart_h
            pts.append(f"{x:.1f},{y:.1f}")
        dash = 'stroke-dasharray="6,3"' if dashed else ''
        return f'<polyline points="{" ".join(pts)}" fill="none" stroke="{color}" stroke-width="1.8" {dash}/>'

    traj_svg_lines = []
    for j in range(3):
        traj_svg_lines.append(traj_path(gt_traj[j], colors[j]))
        traj_svg_lines.append(traj_path(pred_traj[j], colors[j], dashed=True))
    traj_svg = '\n'.join(traj_svg_lines)

    # SVG: MAE bar chart per joint
    bar_svg_w, bar_svg_h = 600, 140
    bar_pad = 35
    bar_w = (bar_svg_w - 2 * bar_pad) / 7 - 6
    max_mae = max(mae_per_joint) * 1.2 or 1
    bars = []
    for j, mae in enumerate(mae_per_joint):
        bx = bar_pad + j * ((bar_svg_w - 2 * bar_pad) / 7)
        bh = (mae / max_mae) * (bar_svg_h - 2 * bar_pad)
        by = bar_svg_h - bar_pad - bh
        fill = "#ef4444" if mae > threshold * 0.6 else "#38bdf8"
        bars.append(f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bar_w:.1f}" height="{bh:.1f}" fill="{fill}" rx="3"/>')
        bars.append(f'<text x="{bx + bar_w/2:.1f}" y="{bar_svg_h - 12}" fill="#94a3b8" font-size="9" text-anchor="middle">{joint_names[j][:6]}</text>')
        bars.append(f'<text x="{bx + bar_w/2:.1f}" y="{by - 4:.1f}" fill="{fill}" font-size="9" text-anchor="middle">{mae:.1f}°</text>')
    bar_svg = '\n'.join(bars)

    # Step status row
    status_cells = []
    for i, st in enumerate(step_status):
        col = "#4ade80" if st == "PASS" else "#ef4444"
        status_cells.append(f'<rect x="{15 + i * 27}" y="5" width="20" height="20" fill="{col}" rx="3" opacity="0.85"/><text x="{25 + i * 27}" y="19" fill="#0f172a" font-size="8" text-anchor="middle" font-weight="bold">{i+1}</text>')
    status_svg = '\n'.join(status_cells)

    # Recent validations table data
    recent = []
    models = ["gr00t-n1.6-finetuned", "gr00t-n1.6-baseline", "openvla-7b", "gr00t-n1.6-dagger5", "pi0-base"]
    for k in range(5):
        r = random.Random(k * 77)
        m = models[k]
        mae_v = r.uniform(3.5, 18.0)
        pr = r.uniform(55, 98)
        status = "PASS" if mae_v < 12 and pr > 70 else "FAIL"
        clr = "#4ade80" if status == "PASS" else "#ef4444"
        recent.append(f'<tr><td>{m}</td><td>{mae_v:.2f}°</td><td>{pr:.1f}%</td><td style="color:{clr};font-weight:bold">{status}</td></tr>')
    recent_rows = '\n'.join(recent)

    return f"""<!DOCTYPE html><html><head><title>Action Sequence Validator</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui;padding:20px}}
h1{{color:#C74634;margin:0 0 4px 0;font-size:1.6rem}}
h2{{color:#38bdf8;font-size:1rem;margin:0 0 10px 0}}
.card{{background:#1e293b;padding:20px;margin:12px 0;border-radius:10px;border:1px solid #334155}}
.grid{{display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:12px;margin-bottom:12px}}
.metric{{background:#0f172a;border-radius:8px;padding:14px;text-align:center;border:1px solid #334155}}
.metric .val{{font-size:1.8rem;font-weight:bold;color:#38bdf8}}
.metric .lbl{{font-size:0.75rem;color:#94a3b8;margin-top:4px}}
.pass{{color:#4ade80}}.fail{{color:#ef4444}}
svg{{display:block;width:100%}}
table{{width:100%;border-collapse:collapse;font-size:0.82rem}}
th{{color:#94a3b8;text-align:left;padding:6px 10px;border-bottom:1px solid #334155}}
td{{padding:6px 10px;border-bottom:1px solid #1e293b}}
.subtitle{{color:#94a3b8;font-size:0.85rem;margin-bottom:16px}}
.legend{{display:flex;gap:16px;font-size:0.75rem;color:#94a3b8;margin-top:6px}}
.dot{{display:inline-block;width:12px;height:3px;margin-right:4px;vertical-align:middle}}
</style></head>
<body>
<h1>Action Sequence Validator</h1>
<p class="subtitle">Port {PORT} &nbsp;|&nbsp; Validates robot action chunk trajectories against ground-truth demonstrations</p>

<div class="grid">
  <div class="metric"><div class="val" style="color:#{'4ade80' if overall_mae < 10 else 'ef4444'}">{overall_mae:.2f}°</div><div class="lbl">Overall MAE</div></div>
  <div class="metric"><div class="val" style="color:#{'4ade80' if pass_rate >= 75 else 'f59e0b'}">{pass_rate:.0f}%</div><div class="lbl">Step Pass Rate</div></div>
  <div class="metric"><div class="val">{max_err:.1f}°</div><div class="lbl">Peak Error</div></div>
  <div class="metric"><div class="val">{n_steps}</div><div class="lbl">Sequence Steps</div></div>
</div>

<div class="card">
  <h2>Joint Trajectory: Predicted (dashed) vs Ground Truth (solid)</h2>
  <svg viewBox="0 0 600 160" xmlns="http://www.w3.org/2000/svg">
    <rect width="600" height="160" fill="#0f172a" rx="6"/>
    <!-- grid lines -->
    {''.join(f'<line x1="30" y1="{30 + k*25}" x2="570" y2="{30 + k*25}" stroke="#1e293b" stroke-width="1"/>' for k in range(5))}
    {''.join(f'<line x1="{30 + k*54}" y1="30" x2="{30 + k*54}" y2="130" stroke="#1e293b" stroke-width="1"/>' for k in range(11))}
    {traj_svg}
    <text x="300" y="155" fill="#475569" font-size="9" text-anchor="middle">Step</text>
    <text x="14" y="85" fill="#475569" font-size="9" text-anchor="middle" transform="rotate(-90,14,85)">Angle (°)</text>
  </svg>
  <div class="legend">
    {''.join(f'<span><span class="dot" style="background:{colors[j]}"></span>{joint_names[j]}</span>' for j in range(3))}
    <span style="margin-left:12px">— ground truth &nbsp; - - - predicted</span>
  </div>
</div>

<div class="card">
  <h2>MAE per Joint (threshold = {threshold:.0f}°)</h2>
  <svg viewBox="0 0 600 140" xmlns="http://www.w3.org/2000/svg">
    <rect width="600" height="140" fill="#0f172a" rx="6"/>
    <line x1="35" y1="10" x2="35" y2="110" stroke="#334155" stroke-width="1"/>
    <line x1="35" y1="110" x2="580" y2="110" stroke="#334155" stroke-width="1"/>
    {bar_svg}
  </svg>
</div>

<div class="card">
  <h2>Step-by-Step Validation Status</h2>
  <svg viewBox="0 0 {15 + n_steps * 27} 30" xmlns="http://www.w3.org/2000/svg">
    {status_svg}
  </svg>
  <div style="font-size:0.78rem;color:#94a3b8;margin-top:8px">
    <span class="pass">PASS</span> = all joints within {threshold:.0f}° threshold &nbsp;|&nbsp; <span class="fail">FAIL</span> = at least one joint exceeded threshold
  </div>
</div>

<div class="card">
  <h2>Recent Model Validations</h2>
  <table>
    <thead><tr><th>Model</th><th>MAE</th><th>Pass Rate</th><th>Verdict</th></tr></thead>
    <tbody>{recent_rows}</tbody>
  </table>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Action Sequence Validator")
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
