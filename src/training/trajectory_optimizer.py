"""Trajectory Optimizer — FastAPI port 8469"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8469

def build_html():
    random.seed(47)
    # trajectory before/after (joint 4 position)
    steps = list(range(0, 848, 8))
    # raw trajectory with noise/jerk
    raw_traj = []
    base = 0.0
    for i, s in enumerate(steps):
        base += 0.003 + random.gauss(0, 0.004)
        jerk = 0.05 * math.sin(s / 50) * random.choice([1, -1, 0, 0])
        raw_traj.append(base + jerk)

    # smoothed (learned_prior)
    smooth_traj = []
    alpha = 0.15
    v = raw_traj[0]
    for r in raw_traj:
        v = alpha * r + (1 - alpha) * v
        smooth_traj.append(v)

    max_val = max(max(raw_traj), max(smooth_traj)) + 0.05
    raw_pts = " ".join(f"{30+i*3.2:.1f},{150-raw_traj[i]/max_val*130:.1f}" for i in range(len(steps)))
    smooth_pts = " ".join(f"{30+i*3.2:.1f},{150-smooth_traj[i]/max_val*130:.1f}" for i in range(len(steps)))
    traj_svg = f'<polyline points="{raw_pts}" fill="none" stroke="#64748b" stroke-width="1.5" opacity="0.7"/>'
    traj_svg += f'<polyline points="{smooth_pts}" fill="none" stroke="#C74634" stroke-width="2.5"/>'

    # method comparison radar
    methods = ["Time-Opt", "Energy-Opt", "Jerk-Min", "Smooth-Filt", "Learned-Prior"]
    metrics_labels = ["Jerk\nReduction", "SR\nRetain", "Energy\nSave", "Speed", "Generalize"]
    method_scores = {
        "Time-Opt":      [0.45, 0.92, 0.38, 0.95, 0.65],
        "Energy-Opt":    [0.62, 0.88, 0.87, 0.71, 0.72],
        "Jerk-Min":      [0.91, 0.85, 0.73, 0.58, 0.69],
        "Smooth-Filt":   [0.78, 0.90, 0.65, 0.74, 0.71],
        "Learned-Prior": [0.87, 0.97, 0.71, 0.79, 0.84],
    }
    mcolors = {"Time-Opt": "#64748b", "Energy-Opt": "#38bdf8", "Jerk-Min": "#f59e0b",
               "Smooth-Filt": "#8b5cf6", "Learned-Prior": "#C74634"}
    n = 5
    angles = [2 * math.pi * i / n - math.pi / 2 for i in range(n)]
    cx, cy, r_rad = 130, 130, 100
    radar = ""
    for ring in [0.25, 0.5, 0.75, 1.0]:
        pts = " ".join(f"{cx + r_rad*ring*math.cos(a):.1f},{cy + r_rad*ring*math.sin(a):.1f}" for a in angles)
        radar += f'<polygon points="{pts}" fill="none" stroke="#334155" stroke-width="1"/>'
    for a, label in zip(angles, metrics_labels):
        x2 = cx + r_rad * math.cos(a)
        y2 = cy + r_rad * math.sin(a)
        radar += f'<line x1="{cx}" y1="{cy}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#334155" stroke-width="1"/>'
        lx = cx + (r_rad + 16) * math.cos(a)
        ly = cy + (r_rad + 16) * math.sin(a)
        radar += f'<text x="{lx:.1f}" y="{ly:.1f}" fill="#94a3b8" font-size="9" text-anchor="middle">{label.split(chr(10))[0]}</text>'
    for method, scores in method_scores.items():
        pts = " ".join(f"{cx + r_rad*s*math.cos(a):.1f},{cy + r_rad*s*math.sin(a):.1f}" for s, a in zip(scores, angles))
        color = mcolors[method]
        is_winner = method == "Learned-Prior"
        radar += f'<polygon points="{pts}" fill="{color}" fill-opacity="{0.25 if is_winner else 0.08}" stroke="{color}" stroke-width="{2.5 if is_winner else 1}"/>'

    return f"""<!DOCTYPE html>
<html>
<head><title>Trajectory Optimizer</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',sans-serif}}
.hdr{{background:#1e293b;padding:16px 24px;border-bottom:2px solid #C74634;display:flex;align-items:center;gap:12px}}
.hdr h1{{margin:0;font-size:20px;color:#f1f5f9}}
.badge{{background:#C74634;color:#fff;padding:3px 10px;border-radius:12px;font-size:11px;font-weight:700}}
.grid{{display:grid;grid-template-columns:3fr 2fr;gap:16px;padding:20px}}
.card{{background:#1e293b;border-radius:10px;padding:18px;border:1px solid #334155}}
.card h3{{margin:0 0 12px;font-size:14px;color:#94a3b8;text-transform:uppercase;letter-spacing:.05em}}
.metrics{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;padding:16px 20px}}
.m{{background:#1e293b;border-radius:8px;padding:12px 16px;border:1px solid #334155}}
.mv{{font-size:24px;font-weight:700;color:#38bdf8}}
.ml{{font-size:11px;color:#64748b;margin-top:2px}}
.delta{{font-size:12px;color:#22c55e;margin-top:4px}}
</style>
</head>
<body>
<div class="hdr">
  <span class="badge">PORT {PORT}</span>
  <h1>Trajectory Optimizer — 6-DOF Joint Space</h1>
</div>
<div class="metrics">
  <div class="m"><div class="mv">-23%</div><div class="ml">Jerk Reduction</div><div class="delta">learned_prior method</div></div>
  <div class="m"><div class="mv">SR unch.</div><div class="ml">No SR Regression</div><div class="delta">97% retention</div></div>
  <div class="m"><div class="mv">Learned</div><div class="ml">Best Method</div><div class="delta">Pareto optimal</div></div>
  <div class="m"><div class="mv">847 steps</div><div class="ml">Episode Length</div></div>
</div>
<div class="grid">
  <div class="card">
    <h3>Joint 4 Trajectory: Raw vs Learned-Prior Optimized</h3>
    <svg viewBox="0 0 390 170" width="100%">
      <line x1="28" y1="10" x2="28" y2="153" stroke="#334155" stroke-width="1"/>
      <line x1="28" y1="153" x2="385" y2="153" stroke="#334155" stroke-width="1"/>
      {traj_svg}
      <rect x="250" y="15" width="10" height="3" fill="#64748b" opacity="0.7"/>
      <text x="264" y="20" fill="#64748b" font-size="10">Raw</text>
      <rect x="250" y="26" width="10" height="3" fill="#C74634"/>
      <text x="264" y="31" fill="#C74634" font-size="10">Optimized</text>
    </svg>
  </div>
  <div class="card">
    <h3>Method Comparison Radar</h3>
    <svg viewBox="0 0 280 270" width="100%">
      {radar}
      <text x="130" y="248" fill="#C74634" font-size="10" text-anchor="middle" font-weight="bold">★ Learned-Prior (winner)</text>
    </svg>
  </div>
</div>
</body>
</html>"""

if USE_FASTAPI:
    app = FastAPI(title="Trajectory Optimizer")
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
