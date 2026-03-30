"""Sim Physics Calibrator — FastAPI port 8820"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8820

def build_html():
    # Generate physics calibration data
    random.seed(42)
    num_steps = 40

    # Simulated vs real joint torque error over calibration steps
    torque_errors = [abs(math.sin(i * 0.3) * 2.5 * math.exp(-i * 0.05) + random.uniform(-0.1, 0.1)) for i in range(num_steps)]
    friction_coeffs = [0.18 + 0.12 * math.exp(-i * 0.08) + random.uniform(-0.005, 0.005) for i in range(num_steps)]
    contact_stiffness = [1200 + 400 * math.cos(i * 0.2) * math.exp(-i * 0.04) + random.uniform(-10, 10) for i in range(num_steps)]

    # SVG torque error chart (line chart)
    svg_w, svg_h = 560, 160
    max_te = max(torque_errors) or 1
    te_points = " ".join(
        f"{int(10 + i * (svg_w - 20) / (num_steps - 1))},{int(svg_h - 10 - (torque_errors[i] / max_te) * (svg_h - 20))}"
        for i in range(num_steps)
    )
    te_path = "M " + " L ".join(
        f"{int(10 + i * (svg_w - 20) / (num_steps - 1))},{int(svg_h - 10 - (torque_errors[i] / max_te) * (svg_h - 20))}"
        for i in range(num_steps)
    )

    # SVG friction coefficient chart
    max_fc = max(friction_coeffs) or 1
    fc_path = "M " + " L ".join(
        f"{int(10 + i * (svg_w - 20) / (num_steps - 1))},{int(svg_h - 10 - (friction_coeffs[i] / max_fc) * (svg_h - 20))}"
        for i in range(num_steps)
    )

    # SVG contact stiffness chart
    min_cs, max_cs = min(contact_stiffness), max(contact_stiffness)
    cs_range = max_cs - min_cs or 1
    cs_path = "M " + " L ".join(
        f"{int(10 + i * (svg_w - 20) / (num_steps - 1))},{int(svg_h - 10 - ((contact_stiffness[i] - min_cs) / cs_range) * (svg_h - 20))}"
        for i in range(num_steps)
    )

    # Calibration param table
    joints = ["shoulder_pan", "shoulder_lift", "elbow", "wrist_1", "wrist_2", "wrist_3"]
    params = [
        {
            "joint": j,
            "inertia": round(0.08 + random.uniform(0, 0.04), 4),
            "damping": round(0.005 + random.uniform(0, 0.003), 5),
            "friction": round(0.15 + random.uniform(0, 0.06), 4),
            "stiffness": round(1100 + random.uniform(0, 300), 1),
            "err_pct": round(random.uniform(0.2, 2.8), 2),
        }
        for j in joints
    ]
    rows = "".join(
        f"<tr><td>{p['joint']}</td><td>{p['inertia']}</td><td>{p['damping']}</td>"
        f"<td>{p['friction']}</td><td>{p['stiffness']}</td>"
        f"<td style='color:{'#4ade80' if p['err_pct']<1.5 else '#f87171'}'>{p['err_pct']}%</td></tr>"
        for p in params
    )

    # Residual histogram (bar chart)
    bins = 12
    hist_w, hist_h = 400, 120
    residuals = [random.gauss(0, 0.3) for _ in range(300)]
    bin_edges = [-1.8 + i * (3.6 / bins) for i in range(bins + 1)]
    counts = [sum(1 for r in residuals if bin_edges[k] <= r < bin_edges[k + 1]) for k in range(bins)]
    max_count = max(counts) or 1
    bar_w = (hist_w - 20) / bins
    bars = "".join(
        f"<rect x='{10 + k * bar_w:.1f}' y='{hist_h - 10 - counts[k] / max_count * (hist_h - 20):.1f}' "
        f"width='{bar_w - 2:.1f}' height='{counts[k] / max_count * (hist_h - 20):.1f}' fill='#38bdf8' opacity='0.8'/>"
        for k in range(bins)
    )

    converged = sum(1 for e in torque_errors[-5:] if e < 0.15)
    status_color = "#4ade80" if converged >= 4 else "#facc15"
    status_text = "Converged" if converged >= 4 else "Calibrating"
    final_err = round(torque_errors[-1], 4)
    final_fc = round(friction_coeffs[-1], 5)
    final_cs = round(contact_stiffness[-1], 1)

    return f"""<!DOCTYPE html><html><head><title>Sim Physics Calibrator</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui,sans-serif}}
h1{{color:#C74634;padding:20px 20px 0;margin:0;font-size:1.6rem}}
.subtitle{{color:#94a3b8;padding:4px 20px 16px;font-size:0.9rem}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:12px;padding:0 16px 16px}}
.card{{background:#1e293b;padding:18px;border-radius:10px;border:1px solid #334155}}
.card h2{{color:#38bdf8;margin:0 0 12px;font-size:1rem;text-transform:uppercase;letter-spacing:.05em}}
.stat-row{{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:10px}}
.stat{{background:#0f172a;border-radius:8px;padding:10px 16px;flex:1;min-width:90px}}
.stat-val{{font-size:1.5rem;font-weight:700;color:#f8fafc}}
.stat-label{{font-size:0.75rem;color:#64748b;margin-top:2px}}
table{{width:100%;border-collapse:collapse;font-size:0.82rem}}
th{{background:#0f172a;color:#94a3b8;padding:6px 8px;text-align:left;font-weight:600}}
td{{padding:5px 8px;border-bottom:1px solid #1e293b;color:#cbd5e1}}
tr:hover td{{background:#1e3a5f}}
.badge{{display:inline-block;padding:3px 10px;border-radius:20px;font-size:0.8rem;font-weight:600}}
svg{{width:100%;height:auto;display:block}}
.legend{{font-size:0.75rem;color:#94a3b8;margin-top:4px}}
</style></head>
<body>
<h1>Sim Physics Calibrator</h1>
<div class="subtitle">OCI Robot Cloud — Isaac Sim contact & dynamics parameter calibration &nbsp;|&nbsp; Port {PORT}</div>

<div class="stat-row" style="padding:0 16px 4px">
  <div class="stat"><div class="stat-val" style="color:{status_color}">{status_text}</div><div class="stat-label">Calibration Status</div></div>
  <div class="stat"><div class="stat-val">{final_err}</div><div class="stat-label">Final Torque Error (Nm)</div></div>
  <div class="stat"><div class="stat-val">{final_fc}</div><div class="stat-label">Friction Coeff</div></div>
  <div class="stat"><div class="stat-val">{final_cs}</div><div class="stat-label">Contact Stiffness (N/m)</div></div>
  <div class="stat"><div class="stat-val">{num_steps}</div><div class="stat-label">Calibration Steps</div></div>
</div>

<div class="grid">
  <div class="card" style="grid-column:span 2">
    <h2>Torque Error Convergence</h2>
    <svg viewBox="0 0 {svg_w} {svg_h}" xmlns="http://www.w3.org/2000/svg">
      <rect width="{svg_w}" height="{svg_h}" fill="#0f172a" rx="4"/>
      <!-- grid lines -->
      <line x1="10" y1="{int(svg_h*0.25)}" x2="{svg_w-10}" y2="{int(svg_h*0.25)}" stroke="#1e293b" stroke-width="1"/>
      <line x1="10" y1="{int(svg_h*0.5)}" x2="{svg_w-10}" y2="{int(svg_h*0.5)}" stroke="#1e293b" stroke-width="1"/>
      <line x1="10" y1="{int(svg_h*0.75)}" x2="{svg_w-10}" y2="{int(svg_h*0.75)}" stroke="#1e293b" stroke-width="1"/>
      <polyline points="{te_points}" fill="none" stroke="#C74634" stroke-width="2"/>
      <!-- dots -->
      {''.join(f'<circle cx="{int(10 + i*(svg_w-20)/(num_steps-1))}" cy="{int(svg_h-10-(torque_errors[i]/max_te)*(svg_h-20))}" r="2.5" fill="#f87171"/>' for i in range(0,num_steps,4))}
    </svg>
    <div class="legend">Step index (0–{num_steps-1}) &nbsp;|&nbsp; Y-axis: normalized torque error</div>
  </div>

  <div class="card">
    <h2>Friction Coefficient</h2>
    <svg viewBox="0 0 {svg_w} {svg_h}" xmlns="http://www.w3.org/2000/svg">
      <rect width="{svg_w}" height="{svg_h}" fill="#0f172a" rx="4"/>
      <line x1="10" y1="{int(svg_h*0.5)}" x2="{svg_w-10}" y2="{int(svg_h*0.5)}" stroke="#1e293b" stroke-width="1"/>
      <path d="{fc_path}" fill="none" stroke="#a78bfa" stroke-width="2"/>
    </svg>
    <div class="legend">Coulomb friction μ per calibration step</div>
  </div>

  <div class="card">
    <h2>Contact Stiffness (N/m)</h2>
    <svg viewBox="0 0 {svg_w} {svg_h}" xmlns="http://www.w3.org/2000/svg">
      <rect width="{svg_w}" height="{svg_h}" fill="#0f172a" rx="4"/>
      <line x1="10" y1="{int(svg_h*0.5)}" x2="{svg_w-10}" y2="{int(svg_h*0.5)}" stroke="#1e293b" stroke-width="1"/>
      <path d="{cs_path}" fill="none" stroke="#34d399" stroke-width="2"/>
    </svg>
    <div class="legend">Spring stiffness of ground-contact model</div>
  </div>

  <div class="card">
    <h2>Residual Distribution</h2>
    <svg viewBox="0 0 {hist_w} {hist_h}" xmlns="http://www.w3.org/2000/svg">
      <rect width="{hist_w}" height="{hist_h}" fill="#0f172a" rx="4"/>
      {bars}
      <line x1="10" y1="{hist_h-10}" x2="{hist_w-10}" y2="{hist_h-10}" stroke="#475569" stroke-width="1"/>
    </svg>
    <div class="legend">300-sample Gaussian residual histogram (bins={bins})</div>
  </div>

  <div class="card" style="grid-column:span 2">
    <h2>Per-Joint Calibrated Parameters</h2>
    <table>
      <tr><th>Joint</th><th>Inertia (kg·m²)</th><th>Damping</th><th>Friction μ</th><th>Stiffness (N/m)</th><th>Sim-Real Err</th></tr>
      {rows}
    </table>
  </div>

  <div class="card">
    <h2>Calibration Config</h2>
    <table>
      <tr><th>Parameter</th><th>Value</th></tr>
      <tr><td>Simulator</td><td>Isaac Sim 4.2</td></tr>
      <tr><td>Physics Backend</td><td>PhysX 5</td></tr>
      <tr><td>Timestep</td><td>1/500 s</td></tr>
      <tr><td>Real Robot</td><td>UR5e (6-DOF)</td></tr>
      <tr><td>Calibration Method</td><td>Gradient-free BayesOpt</td></tr>
      <tr><td>Optimizer</td><td>TPE (n_trials=80)</td></tr>
      <tr><td>Convergence Threshold</td><td>0.15 Nm</td></tr>
      <tr><td>OCI Shape</td><td>VM.GPU.A10.1</td></tr>
    </table>
  </div>
</div>
</body></html>"""


if USE_FASTAPI:
    app = FastAPI(title="Sim Physics Calibrator")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return build_html()

    @app.get("/health")
    def health():
        return {"status": "ok", "port": PORT}


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
