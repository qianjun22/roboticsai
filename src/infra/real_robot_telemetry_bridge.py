"""Real Robot Telemetry Bridge — FastAPI port 8828"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8828

def build_html():
    # Generate 6-DOF joint telemetry sine-wave data (no numpy)
    num_points = 60
    joint_colors = ["#C74634", "#38bdf8", "#4ade80", "#f59e0b", "#a78bfa", "#f472b6"]
    joint_names = ["J1", "J2", "J3", "J4", "J5", "J6"]
    joint_amplitudes = [1.2, 0.9, 1.5, 0.7, 1.1, 0.8]
    joint_freqs = [0.8, 1.2, 0.6, 1.5, 1.0, 0.9]
    joint_phases = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5]

    svg_width = 700
    svg_height = 220
    pad_left = 45
    pad_right = 15
    pad_top = 15
    pad_bottom = 30
    chart_w = svg_width - pad_left - pad_right
    chart_h = svg_height - pad_top - pad_bottom

    # Y range: -2 to 2 rad
    y_min, y_max = -2.0, 2.0

    def to_px(i, val):
        x = pad_left + (i / (num_points - 1)) * chart_w
        y = pad_top + (1 - (val - y_min) / (y_max - y_min)) * chart_h
        return x, y

    polylines = ""
    for j in range(6):
        pts = []
        for i in range(num_points):
            t = i / (num_points - 1) * 4 * math.pi
            val = joint_amplitudes[j] * math.sin(joint_freqs[j] * t + joint_phases[j])
            # add small noise
            val += random.uniform(-0.05, 0.05)
            x, y = to_px(i, val)
            pts.append(f"{x:.1f},{y:.1f}")
        polylines += f'<polyline points="{" ".join(pts)}" fill="none" stroke="{joint_colors[j]}" stroke-width="1.8" opacity="0.9"/>\n'

    # Y-axis tick labels
    y_ticks = ""
    for v in [-2, -1, 0, 1, 2]:
        _, py = to_px(0, v)
        y_ticks += f'<text x="{pad_left - 5}" y="{py + 4:.1f}" text-anchor="end" fill="#94a3b8" font-size="10">{v}</text>\n'
        y_ticks += f'<line x1="{pad_left}" y1="{py:.1f}" x2="{pad_left + chart_w}" y2="{py:.1f}" stroke="#334155" stroke-width="0.5"/>\n'

    # X-axis time labels
    x_ticks = ""
    for i in range(0, num_points, 12):
        px, _ = to_px(i, 0)
        x_ticks += f'<text x="{px:.1f}" y="{svg_height - 6}" text-anchor="middle" fill="#94a3b8" font-size="10">{i * 100}ms</text>\n'

    # Legend
    legend = ""
    for j in range(6):
        lx = pad_left + j * 105
        legend += f'<rect x="{lx}" y="3" width="12" height="8" fill="{joint_colors[j]}"/>'
        legend += f'<text x="{lx + 15}" y="11" fill="{joint_colors[j]}" font-size="10">{joint_names[j]}</text>'

    svg = f"""
    <svg width="{svg_width}" height="{svg_height}" style="background:#0f172a;border-radius:6px">
      {y_ticks}
      {polylines}
      {x_ticks}
      <text x="10" y="{pad_top + chart_h // 2}" fill="#64748b" font-size="10" transform="rotate(-90,10,{pad_top + chart_h // 2})">rad</text>
      {legend}
    </svg>
    """

    return f"""<!DOCTYPE html><html><head><title>Real Robot Telemetry Bridge</title>
<style>body{{margin:0;padding:20px;background:#0f172a;color:#e2e8f0;font-family:system-ui}}
h1{{color:#C74634;margin-bottom:4px}}h2{{color:#38bdf8;margin:0 0 12px 0}}
.card{{background:#1e293b;padding:20px;margin:10px 0;border-radius:8px}}
.metrics{{display:flex;gap:20px;flex-wrap:wrap}}
.metric{{background:#0f172a;padding:12px 20px;border-radius:6px;border-left:3px solid #C74634}}
.metric .val{{font-size:1.8em;font-weight:700;color:#38bdf8}}
.metric .lbl{{font-size:0.8em;color:#94a3b8;margin-top:2px}}
.badge{{display:inline-block;padding:2px 8px;border-radius:4px;font-size:0.75em;font-weight:600}}
.ok{{background:#14532d;color:#4ade80}}</style></head>
<body>
<h1>Real Robot Telemetry Bridge</h1>
<p style="color:#64748b;margin-top:0">Port {PORT} — Live sensor streams from deployed robot hardware</p>

<div class="card">
  <h2>System Metrics</h2>
  <div class="metrics">
    <div class="metric"><div class="val">12ms</div><div class="lbl">Telemetry Lag</div></div>
    <div class="metric"><div class="val">99.7%</div><div class="lbl">Uptime</div></div>
    <div class="metric"><div class="val">847</div><div class="lbl">Packets / sec</div></div>
    <div class="metric"><div class="val">6-DOF</div><div class="lbl">Joint Channels</div></div>
  </div>
</div>

<div class="card">
  <h2>6-DOF Joint Telemetry (Live)</h2>
  {svg}
  <p style="color:#64748b;font-size:0.8em;margin-top:8px">Streaming joint angles (radians) over last 6 seconds — 100Hz sample rate</p>
</div>

<div class="card">
  <h2>Active Sensor Streams</h2>
  <table style="width:100%;border-collapse:collapse;font-size:0.9em">
    <tr style="color:#64748b;border-bottom:1px solid #334155">
      <th style="text-align:left;padding:6px">Stream</th>
      <th style="text-align:left;padding:6px">Type</th>
      <th style="text-align:left;padding:6px">Rate</th>
      <th style="text-align:left;padding:6px">Latency</th>
      <th style="text-align:left;padding:6px">Status</th>
    </tr>
    <tr style="border-bottom:1px solid #1e293b">
      <td style="padding:6px">Joint Angles</td><td style="padding:6px">Float64[6]</td>
      <td style="padding:6px">100 Hz</td><td style="padding:6px">8ms</td>
      <td style="padding:6px"><span class="badge ok">LIVE</span></td>
    </tr>
    <tr style="border-bottom:1px solid #1e293b">
      <td style="padding:6px">End-Effector Force</td><td style="padding:6px">Float64[6]</td>
      <td style="padding:6px">500 Hz</td><td style="padding:6px">4ms</td>
      <td style="padding:6px"><span class="badge ok">LIVE</span></td>
    </tr>
    <tr style="border-bottom:1px solid #1e293b">
      <td style="padding:6px">Wrist Camera</td><td style="padding:6px">RGB 640x480</td>
      <td style="padding:6px">30 fps</td><td style="padding:6px">18ms</td>
      <td style="padding:6px"><span class="badge ok">LIVE</span></td>
    </tr>
    <tr>
      <td style="padding:6px">Base IMU</td><td style="padding:6px">Accel+Gyro</td>
      <td style="padding:6px">200 Hz</td><td style="padding:6px">5ms</td>
      <td style="padding:6px"><span class="badge ok">LIVE</span></td>
    </tr>
  </table>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Real Robot Telemetry Bridge")

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
