"""Robot State Estimator — FastAPI port 8638"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8638

def build_html():
    # Generate joint state data: 200 steps, 7 joints
    random.seed(42)
    steps = list(range(200))
    joint_colors = ["#38bdf8", "#C74634", "#a3e635", "#fb923c", "#e879f9", "#34d399", "#facc15"]
    joint_names = ["J1", "J2", "J3", "J4", "J5", "J6", "J7"]

    # Generate smooth joint trajectories
    def smooth_signal(amp, freq, phase, noise=0.05):
        return [amp * math.sin(2 * math.pi * freq * t / 200 + phase) + random.gauss(0, noise) for t in range(200)]

    positions = [smooth_signal(amp=1.2 + 0.15*i, freq=0.8 + 0.1*i, phase=i*0.45) for i in range(7)]
    velocities = [smooth_signal(amp=0.4 + 0.05*i, freq=1.2 + 0.15*i, phase=i*0.6, noise=0.02) for i in range(7)]
    efforts   = [smooth_signal(amp=2.5 + 0.3*i,  freq=0.6 + 0.08*i, phase=i*0.3, noise=0.1)  for i in range(7)]

    def polyline(data, x_scale, y_offset, y_scale, svg_width=700):
        pts = []
        for i, v in enumerate(data):
            x = i * (svg_width / len(data))
            y = y_offset - v * y_scale
            pts.append(f"{x:.1f},{y:.1f}")
        return " ".join(pts)

    # --- SVG 1: Joint State Panel (3 subplots) ---
    svg1_lines_pos = ""
    svg1_lines_vel = ""
    svg1_lines_eff = ""
    for i in range(7):
        c = joint_colors[i]
        svg1_lines_pos += f'<polyline points="{polyline(positions[i], 700, 80, 45)}" fill="none" stroke="{c}" stroke-width="1.5" opacity="0.9"/>\n'
        svg1_lines_vel += f'<polyline points="{polyline(velocities[i], 700, 240, 120)}" fill="none" stroke="{c}" stroke-width="1.5" opacity="0.9"/>\n'
        svg1_lines_eff += f'<polyline points="{polyline(efforts[i], 700, 400, 35)}" fill="none" stroke="{c}" stroke-width="1.5" opacity="0.9"/>\n'

    legend_items = ""
    for i, (name, color) in enumerate(zip(joint_names, joint_colors)):
        lx = 20 + i * 92
        legend_items += f'<rect x="{lx}" y="438" width="12" height="12" fill="{color}" rx="2"/>'
        legend_items += f'<text x="{lx+16}" y="449" fill="#94a3b8" font-size="11" font-family="monospace">{name}</text>'

    svg1 = f'''
    <svg viewBox="0 0 720 465" xmlns="http://www.w3.org/2000/svg" style="width:100%;background:#1e293b;border-radius:8px">
      <!-- Grid lines -->
      <line x1="0" y1="110" x2="720" y2="110" stroke="#334155" stroke-width="0.5"/>
      <line x1="0" y1="270" x2="720" y2="270" stroke="#334155" stroke-width="0.5"/>
      <line x1="0" y1="430" x2="720" y2="430" stroke="#334155" stroke-width="0.5"/>
      <!-- Y axis labels -->
      <text x="4" y="14" fill="#38bdf8" font-size="11" font-family="monospace">Position (rad)</text>
      <text x="4" y="175" fill="#38bdf8" font-size="11" font-family="monospace">Velocity (rad/s)</text>
      <text x="4" y="335" fill="#38bdf8" font-size="11" font-family="monospace">Effort (Nm)</text>
      <!-- Zero lines -->
      <line x1="0" y1="80" x2="720" y2="80" stroke="#475569" stroke-width="0.5" stroke-dasharray="4,4"/>
      <line x1="0" y1="240" x2="720" y2="240" stroke="#475569" stroke-width="0.5" stroke-dasharray="4,4"/>
      <line x1="0" y1="400" x2="720" y2="400" stroke="#475569" stroke-width="0.5" stroke-dasharray="4,4"/>
      <!-- Subplot separators -->
      <line x1="0" y1="108" x2="720" y2="108" stroke="#0f172a" stroke-width="3"/>
      <line x1="0" y1="268" x2="720" y2="268" stroke="#0f172a" stroke-width="3"/>
      <!-- Position lines -->
      {svg1_lines_pos}
      <!-- Velocity lines -->
      {svg1_lines_vel}
      <!-- Effort lines -->
      {svg1_lines_eff}
      <!-- X axis label -->
      <text x="340" y="462" fill="#64748b" font-size="10" font-family="monospace" text-anchor="middle">Steps (0 – 200)</text>
      <!-- Legend -->
      {legend_items}
    </svg>
    '''

    # --- SVG 2: Kalman Filter Noise Reduction Bar Chart ---
    raw_sigmas = [2.1, 1.8, 2.4, 1.6, 2.9, 3.1, 2.7]
    kf_sigmas  = [1.22, 1.04, 1.39, 0.93, 1.68, 1.80, 1.57]
    svg2_bars = ""
    bar_w = 28
    for i, (raw, kf) in enumerate(zip(raw_sigmas, kf_sigmas)):
        bx = 60 + i * 88
        raw_h = raw * 40
        kf_h  = kf  * 40
        by_raw = 200 - raw_h
        by_kf  = 200 - kf_h
        svg2_bars += f'<rect x="{bx}" y="{by_raw:.1f}" width="{bar_w}" height="{raw_h:.1f}" fill="#C74634" opacity="0.85" rx="3"/>'
        svg2_bars += f'<rect x="{bx+bar_w+4}" y="{by_kf:.1f}" width="{bar_w}" height="{kf_h:.1f}" fill="#38bdf8" opacity="0.85" rx="3"/>'
        svg2_bars += f'<text x="{bx+30}" y="215" fill="#94a3b8" font-size="11" font-family="monospace" text-anchor="middle">{joint_names[i]}</text>'
        pct = int((1 - kf/raw)*100)
        svg2_bars += f'<text x="{bx+30}" y="{by_kf-5:.0f}" fill="#a3e635" font-size="10" font-family="monospace" text-anchor="middle">-{pct}%</text>'

    svg2 = f'''
    <svg viewBox="0 0 720 240" xmlns="http://www.w3.org/2000/svg" style="width:100%;background:#1e293b;border-radius:8px">
      <text x="360" y="22" fill="#C74634" font-size="14" font-family="monospace" text-anchor="middle" font-weight="bold">Kalman Filter Noise Reduction — Raw σ vs KF σ</text>
      <!-- Grid -->
      <line x1="50" y1="200" x2="680" y2="200" stroke="#334155" stroke-width="1"/>
      <line x1="50" y1="160" x2="680" y2="160" stroke="#334155" stroke-width="0.5" stroke-dasharray="4,3"/>
      <line x1="50" y1="120" x2="680" y2="120" stroke="#334155" stroke-width="0.5" stroke-dasharray="4,3"/>
      <line x1="50" y1="80"  x2="680" y2="80"  stroke="#334155" stroke-width="0.5" stroke-dasharray="4,3"/>
      <!-- Y axis labels -->
      <text x="44" y="204" fill="#64748b" font-size="10" font-family="monospace" text-anchor="end">0</text>
      <text x="44" y="164" fill="#64748b" font-size="10" font-family="monospace" text-anchor="end">1</text>
      <text x="44" y="124" fill="#64748b" font-size="10" font-family="monospace" text-anchor="end">2</text>
      <text x="44" y="84"  fill="#64748b" font-size="10" font-family="monospace" text-anchor="end">3</text>
      <text x="4"  y="120" fill="#94a3b8" font-size="11" font-family="monospace" transform="rotate(-90,4,120)">σ (mm)</text>
      {svg2_bars}
      <!-- Legend -->
      <rect x="480" y="228" width="14" height="8" fill="#C74634" rx="2"/>
      <text x="498" y="236" fill="#94a3b8" font-size="11" font-family="monospace">Raw σ</text>
      <rect x="560" y="228" width="14" height="8" fill="#38bdf8" rx="2"/>
      <text x="578" y="236" fill="#94a3b8" font-size="11" font-family="monospace">KF σ  (42% avg ↓)</text>
    </svg>
    '''

    # --- SVG 3: State Estimation Error Histogram ---
    sigma_mm = 0.8
    bins = 30
    bin_edges = [-3.0 + i * (6.0 / bins) for i in range(bins + 1)]
    bin_centers = [(bin_edges[i] + bin_edges[i+1]) / 2 for i in range(bins)]
    bin_width_px = 620 / bins
    random.seed(7)
    errors = [random.gauss(0, sigma_mm) for _ in range(2000)]
    counts = [0] * bins
    for e in errors:
        for j in range(bins):
            if bin_edges[j] <= e < bin_edges[j+1]:
                counts[j] += 1
                break
    max_count = max(counts)
    svg3_bars = ""
    for j in range(bins):
        bh = counts[j] / max_count * 130
        bx = 50 + j * bin_width_px
        by = 170 - bh
        svg3_bars += f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bin_width_px-1:.1f}" height="{bh:.1f}" fill="#38bdf8" opacity="0.75" rx="1"/>'
    # Gaussian curve
    curve_pts = []
    for j, cx in enumerate(bin_centers):
        gauss_y = math.exp(-0.5 * (cx / sigma_mm)**2) / (sigma_mm * math.sqrt(2 * math.pi))
        norm_y = gauss_y / (1.0 / (sigma_mm * math.sqrt(2 * math.pi)))  # normalize to 1
        px = 50 + (j + 0.5) * bin_width_px
        py = 170 - norm_y * 130
        curve_pts.append(f"{px:.1f},{py:.1f}")
    sigma_x = 50 + (sigma_mm + 3.0) / 6.0 * 620
    neg_sigma_x = 50 + (-sigma_mm + 3.0) / 6.0 * 620

    svg3 = f'''
    <svg viewBox="0 0 720 210" xmlns="http://www.w3.org/2000/svg" style="width:100%;background:#1e293b;border-radius:8px">
      <text x="360" y="20" fill="#C74634" font-size="14" font-family="monospace" text-anchor="middle" font-weight="bold">Position Error Histogram  (σ = 0.8 mm)</text>
      <line x1="50" y1="170" x2="670" y2="170" stroke="#334155" stroke-width="1"/>
      <line x1="50" y1="40"  x2="50"  y2="170" stroke="#334155" stroke-width="1"/>
      {svg3_bars}
      <!-- Gaussian curve -->
      <polyline points="{' '.join(curve_pts)}" fill="none" stroke="#facc15" stroke-width="2" opacity="0.9"/>
      <!-- Sigma lines -->
      <line x1="{sigma_x:.1f}" y1="40" x2="{sigma_x:.1f}" y2="170" stroke="#e879f9" stroke-width="1.5" stroke-dasharray="5,3"/>
      <line x1="{neg_sigma_x:.1f}" y1="40" x2="{neg_sigma_x:.1f}" y2="170" stroke="#e879f9" stroke-width="1.5" stroke-dasharray="5,3"/>
      <text x="{sigma_x+3:.1f}" y="55" fill="#e879f9" font-size="10" font-family="monospace">+σ</text>
      <text x="{neg_sigma_x-18:.1f}" y="55" fill="#e879f9" font-size="10" font-family="monospace">-σ</text>
      <!-- X labels -->
      <text x="50"  y="185" fill="#64748b" font-size="10" font-family="monospace" text-anchor="middle">-3</text>
      <text x="205" y="185" fill="#64748b" font-size="10" font-family="monospace" text-anchor="middle">-1.5</text>
      <text x="360" y="185" fill="#64748b" font-size="10" font-family="monospace" text-anchor="middle">0</text>
      <text x="515" y="185" fill="#64748b" font-size="10" font-family="monospace" text-anchor="middle">1.5</text>
      <text x="670" y="185" fill="#64748b" font-size="10" font-family="monospace" text-anchor="middle">3</text>
      <text x="360" y="200" fill="#64748b" font-size="10" font-family="monospace" text-anchor="middle">Position Error (mm)</text>
      <!-- Legend -->
      <rect x="490" y="32" width="14" height="8" fill="#38bdf8" opacity="0.75" rx="2"/>
      <text x="508" y="40" fill="#94a3b8" font-size="10" font-family="monospace">Measured errors</text>
      <line x1="490" y1="52" x2="504" y2="52" stroke="#facc15" stroke-width="2"/>
      <text x="508" y="56" fill="#94a3b8" font-size="10" font-family="monospace">Gaussian fit</text>
    </svg>
    '''

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Robot State Estimator — Port {PORT}</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #e2e8f0; font-family: 'Courier New', monospace; padding: 28px; }}
    h1   {{ color: #C74634; font-size: 1.6rem; letter-spacing: 0.04em; margin-bottom: 6px; }}
    h2   {{ color: #C74634; font-size: 1.1rem; margin: 28px 0 10px; letter-spacing: 0.03em; }}
    .subtitle {{ color: #64748b; font-size: 0.85rem; margin-bottom: 24px; }}
    .metrics {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin-bottom: 30px; }}
    .card {{
      background: #1e293b; border: 1px solid #334155; border-radius: 8px;
      padding: 16px 14px; text-align: center;
    }}
    .card .val {{ color: #38bdf8; font-size: 1.6rem; font-weight: bold; }}
    .card .lbl {{ color: #64748b; font-size: 0.78rem; margin-top: 5px; }}
    .card .note {{ color: #94a3b8; font-size: 0.75rem; margin-top: 4px; }}
    .chart-wrap {{ background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 16px; margin-bottom: 22px; }}
    .alert {{
      background: #1e293b; border-left: 3px solid #C74634;
      padding: 12px 16px; border-radius: 4px; margin-bottom: 22px;
      color: #fca5a5; font-size: 0.88rem;
    }}
    footer {{ color: #334155; font-size: 0.75rem; margin-top: 36px; text-align: center; }}
  </style>
</head>
<body>
  <h1>Robot State Estimator</h1>
  <div class="subtitle">7-DOF Kalman Filter State Estimation  |  Port {PORT}  |  OCI Robot Cloud</div>

  <div class="metrics">
    <div class="card"><div class="val">4 ms</div><div class="lbl">KF Latency</div><div class="note">per cycle</div></div>
    <div class="card"><div class="val">0.8 mm</div><div class="lbl">Position σ</div><div class="note">post-filter</div></div>
    <div class="card"><div class="val">0.12 rad/s</div><div class="lbl">Velocity σ</div><div class="note">post-filter</div></div>
    <div class="card"><div class="val">42%</div><div class="lbl">Noise Reduction</div><div class="note">avg across joints</div></div>
  </div>

  <div class="alert">Highest uncertainty: wrist joints (J5–J7) during grasp phase — KF prediction weight increased 1.4×</div>

  <h2>7-DOF Joint State Panel (Position / Velocity / Effort)</h2>
  <div class="chart-wrap">{svg1}</div>

  <h2>Kalman Filter Noise Reduction — Raw σ vs KF σ per Joint</h2>
  <div class="chart-wrap">{svg2}</div>

  <h2>State Estimation Error Distribution</h2>
  <div class="chart-wrap">{svg3}</div>

  <footer>OCI Robot Cloud · Robot State Estimator · Port {PORT} · cycle-145A</footer>
</body>
</html>"""


if USE_FASTAPI:
    app = FastAPI(title="Robot State Estimator")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return build_html()

    @app.get("/health")
    def health():
        return {"status": "ok", "port": PORT}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            body = b'{"status":"ok","port":8638}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
        else:
            body = build_html().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
