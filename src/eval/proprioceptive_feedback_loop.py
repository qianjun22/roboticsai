"""Proprioceptive Feedback Loop — FastAPI port 8822"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8822

def build_html():
    # Generate joint torque/position feedback data using sin/cos
    joints = ["shoulder_pan", "shoulder_lift", "elbow", "wrist_1", "wrist_2", "wrist_3"]
    num_steps = 60
    seed = random.randint(0, 9999)
    rng = random.Random(seed)

    # Per-joint torque over time (Nm)
    torque_series = []
    for j_idx, jname in enumerate(joints):
        phase = rng.uniform(0, math.pi)
        amp = rng.uniform(8, 30)
        noise_scale = rng.uniform(0.5, 2.0)
        vals = [
            round(amp * math.sin(2 * math.pi * t / num_steps + phase) + rng.gauss(0, noise_scale), 2)
            for t in range(num_steps)
        ]
        torque_series.append((jname, vals))

    # Position error over time (rad)
    pos_errors = [
        round(0.15 * math.exp(-t / 20) * math.cos(3 * math.pi * t / num_steps) + rng.gauss(0, 0.003), 4)
        for t in range(num_steps)
    ]

    # Velocity feedback (rad/s)
    vel_series = [
        round(1.2 * math.sin(2 * math.pi * t / num_steps + 0.4) + rng.gauss(0, 0.05), 3)
        for t in range(num_steps)
    ]

    # Summary metrics
    rms_torque = round(math.sqrt(sum(v**2 for v in torque_series[0][1]) / num_steps), 3)
    peak_pos_err = round(max(abs(e) for e in pos_errors), 4)
    settling_time = next((t for t in range(num_steps) if abs(pos_errors[t]) < 0.005), num_steps)
    feedback_latency_ms = round(rng.uniform(1.8, 4.5), 2)
    loop_freq_hz = round(rng.uniform(480, 512), 1)
    compliance_score = round(rng.uniform(0.88, 0.99), 3)

    # SVG torque chart (line chart, first 3 joints)
    W, H = 520, 160
    colors = ["#38bdf8", "#f472b6", "#4ade80"]
    torque_svg_lines = ""
    for idx in range(3):
        vals = torque_series[idx][1]
        v_min, v_max = min(vals), max(vals)
        span = v_max - v_min if v_max != v_min else 1
        pts = " ".join(
            f"{int(W * t / (num_steps - 1))},{int(H - (v - v_min) / span * (H - 10) - 5)}"
            for t, v in enumerate(vals)
        )
        torque_svg_lines += f'<polyline points="{pts}" fill="none" stroke="{colors[idx]}" stroke-width="1.5" opacity="0.85"/>\n'
    legend_items = "".join(
        f'<rect x="{10 + idx * 140}" y="148" width="12" height="12" fill="{colors[idx]}"/><text x="{26 + idx * 140}" y="159" fill="#94a3b8" font-size="10">{joints[idx]}</text>'
        for idx in range(3)
    )

    # SVG position error chart
    pe_min, pe_max = min(pos_errors), max(pos_errors)
    pe_span = pe_max - pe_min if pe_max != pe_min else 1
    pe_pts = " ".join(
        f"{int(W * t / (num_steps - 1))},{int(H - (v - pe_min) / pe_span * (H - 10) - 5)}"
        for t, v in enumerate(pos_errors)
    )
    zero_y = int(H - (0 - pe_min) / pe_span * (H - 10) - 5)
    pe_svg = f"""
    <line x1="0" y1="{zero_y}" x2="{W}" y2="{zero_y}" stroke="#475569" stroke-width="1" stroke-dasharray="4,3"/>
    <polyline points="{pe_pts}" fill="none" stroke="#fb923c" stroke-width="2"/>
    """

    # SVG velocity chart
    vl_min, vl_max = min(vel_series), max(vel_series)
    vl_span = vl_max - vl_min if vl_max != vl_min else 1
    vl_pts = " ".join(
        f"{int(W * t / (num_steps - 1))},{int(H - (v - vl_min) / vl_span * (H - 10) - 5)}"
        for t, v in enumerate(vel_series)
    )
    vl_svg = f'<polyline points="{vl_pts}" fill="none" stroke="#a78bfa" stroke-width="2"/>'

    # Joint status table rows
    table_rows = ""
    for j_idx, (jname, vals) in enumerate(torque_series):
        rms = round(math.sqrt(sum(v**2 for v in vals) / num_steps), 2)
        peak = round(max(abs(v) for v in vals), 2)
        status = "NOMINAL" if rms < 20 else "WARNING"
        color = "#4ade80" if status == "NOMINAL" else "#facc15"
        table_rows += f"""
        <tr>
          <td style="padding:6px 10px;color:#e2e8f0">{jname}</td>
          <td style="padding:6px 10px;color:#38bdf8">{rms} Nm</td>
          <td style="padding:6px 10px;color:#f472b6">{peak} Nm</td>
          <td style="padding:6px 10px;color:{color};font-weight:bold">{status}</td>
        </tr>"""

    return f"""<!DOCTYPE html><html lang="en"><head><title>Proprioceptive Feedback Loop</title>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>
  body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui,sans-serif}}
  h1{{color:#C74634;padding:20px 20px 5px;margin:0;font-size:1.5rem}}
  .subtitle{{color:#64748b;padding:0 20px 15px;font-size:0.85rem}}
  h2{{color:#38bdf8;margin:0 0 10px;font-size:1rem}}
  .grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;padding:0 20px}}
  .grid2{{display:grid;grid-template-columns:1fr 1fr;gap:12px;padding:0 20px 20px}}
  .card{{background:#1e293b;padding:20px;border-radius:8px;border:1px solid #334155}}
  .stat{{font-size:2rem;font-weight:700;color:#38bdf8}}
  .label{{font-size:0.75rem;color:#64748b;margin-top:4px}}
  .warn{{color:#facc15}}.good{{color:#4ade80}}
  table{{width:100%;border-collapse:collapse}}
  th{{text-align:left;padding:6px 10px;color:#64748b;font-size:0.75rem;border-bottom:1px solid #334155}}
  tr:hover td{{background:#273548}}
  svg{{width:100%;overflow:visible}}
  .chart-bg{{fill:#0f172a;rx:4}}
</style></head>
<body>
<h1>Proprioceptive Feedback Loop</h1>
<div class="subtitle">Port {PORT} &nbsp;|&nbsp; 6-DOF arm &nbsp;|&nbsp; Loop freq: <span style="color:#38bdf8">{loop_freq_hz} Hz</span> &nbsp;|&nbsp; Latency: <span style="color:#38bdf8">{feedback_latency_ms} ms</span></div>

<div class="grid">
  <div class="card">
    <div class="stat {'good' if peak_pos_err < 0.05 else 'warn'}">{peak_pos_err} rad</div>
    <div class="label">Peak Position Error</div>
  </div>
  <div class="card">
    <div class="stat">{settling_time}</div>
    <div class="label">Settling Time (steps)</div>
  </div>
  <div class="card">
    <div class="stat {'good' if compliance_score > 0.92 else 'warn'}">{compliance_score}</div>
    <div class="label">Compliance Score</div>
  </div>
</div>

<div style="height:12px"></div>
<div class="grid2">
  <div class="card">
    <h2>Joint Torque Feedback (Nm) — 3 Joints</h2>
    <svg viewBox="0 0 {W} 170" height="170">
      <rect width="{W}" height="{H}" fill="#0f172a" rx="4"/>
      <line x1="0" y1="{H//2}" x2="{W}" y2="{H//2}" stroke="#334155" stroke-width="1" stroke-dasharray="4,3"/>
      {torque_svg_lines}
      {legend_items}
    </svg>
  </div>
  <div class="card">
    <h2>Position Error Over Time (rad)</h2>
    <svg viewBox="0 0 {W} {H}" height="{H}">
      <rect width="{W}" height="{H}" fill="#0f172a" rx="4"/>
      {pe_svg}
    </svg>
  </div>
  <div class="card">
    <h2>Wrist Velocity Feedback (rad/s)</h2>
    <svg viewBox="0 0 {W} {H}" height="{H}">
      <rect width="{W}" height="{H}" fill="#0f172a" rx="4"/>
      {vl_svg}
    </svg>
  </div>
  <div class="card">
    <h2>Joint Status</h2>
    <table>
      <thead><tr><th>Joint</th><th>RMS Torque</th><th>Peak Torque</th><th>Status</th></tr></thead>
      <tbody>{table_rows}</tbody>
    </table>
  </div>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Proprioceptive Feedback Loop")

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
    def log_message(self, *a): pass

if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
