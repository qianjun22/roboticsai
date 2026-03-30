"""Tactile Sensor Fusion — FastAPI port 8720"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8720

def build_html():
    random.seed(42)
    # Simulate 12 tactile sensor readings across a robot fingertip grid (4x3)
    sensors = [[round(random.uniform(0.1, 1.0) * math.sin(i * 0.7 + j * 0.4) ** 2 + 0.15, 3)
                for j in range(3)] for i in range(4)]

    # Time-series pressure waveform: 40 samples
    t_vals = [i * 0.1 for i in range(40)]
    pressure = [round(0.5 + 0.35 * math.sin(2 * math.pi * t / 2.0)
                      + 0.1 * math.cos(2 * math.pi * t / 0.8)
                      + random.gauss(0, 0.03), 4) for t in t_vals]

    # Impedance spectroscopy: 20 frequency points
    freqs = [10 * (1.5 ** i) for i in range(20)]
    impedance = [round(120 + 80 * math.exp(-f / 800) + random.gauss(0, 2), 2) for f in freqs]

    # Contact force estimate per axis (Fx, Fy, Fz) over 30 timesteps
    force_x = [round(1.2 * math.sin(2 * math.pi * i / 20) + random.gauss(0, 0.08), 3) for i in range(30)]
    force_y = [round(0.8 * math.cos(2 * math.pi * i / 15) + random.gauss(0, 0.06), 3) for i in range(30)]
    force_z = [round(3.5 + 0.6 * math.sin(2 * math.pi * i / 10) + random.gauss(0, 0.1), 3) for i in range(30)]

    # Heatmap SVG for 4x3 sensor grid
    cell_w, cell_h = 70, 70
    heatmap_cells = ""
    for i in range(4):
        for j in range(3):
            val = sensors[i][j]
            r = int(180 * val + 20)
            g = int(50 * (1 - val))
            b = int(200 * (1 - val))
            x = 20 + j * cell_w
            y = 20 + i * cell_h
            heatmap_cells += (f'<rect x="{x}" y="{y}" width="{cell_w-4}" height="{cell_h-4}" '
                              f'rx="6" fill="rgb({r},{g},{b})" opacity="0.88"/>'
                              f'<text x="{x + cell_w//2 - 2}" y="{y + cell_h//2 + 5}" '
                              f'font-size="13" fill="#fff" text-anchor="middle">{val:.2f}</text>')

    # Pressure waveform SVG polyline
    w_svg, h_svg = 520, 120
    px_pts = " ".join(
        f"{20 + int(i * (w_svg - 40) / (len(pressure) - 1))},{int(h_svg - 10 - (pressure[i] - 0.0) / 1.0 * (h_svg - 20))}"
        for i in range(len(pressure))
    )

    # Force XYZ SVG lines
    def force_polyline(vals, color, offset_y=60):
        return ("<polyline points='" +
                " ".join(f"{20 + int(i * 460 / (len(vals)-1))},{offset_y - int(vals[i] * 12)}" for i in range(len(vals))) +
                f"' fill='none' stroke='{color}' stroke-width='2'/>")

    fx_line = force_polyline(force_x, '#f59e0b')
    fy_line = force_polyline(force_y, '#34d399', offset_y=60)
    fz_line = force_polyline(force_z, '#60a5fa', offset_y=60)

    # Stats
    avg_pressure = round(sum(pressure) / len(pressure), 4)
    max_pressure = round(max(pressure), 4)
    fz_mean = round(sum(force_z) / len(force_z), 3)
    sensor_flat = [sensors[i][j] for i in range(4) for j in range(3)]
    hot_count = sum(1 for v in sensor_flat if v > 0.6)

    return f"""<!DOCTYPE html><html><head><title>Tactile Sensor Fusion</title>
<meta charset='utf-8'>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui,sans-serif}}
h1{{color:#C74634;padding:18px 24px 0;margin:0;font-size:1.6rem}}
.subtitle{{color:#94a3b8;padding:2px 26px 14px;font-size:0.92rem}}
.grid{{display:flex;flex-wrap:wrap;gap:0}}
.card{{background:#1e293b;padding:20px;margin:10px;border-radius:10px;flex:1;min-width:280px}}
h2{{color:#38bdf8;font-size:1.05rem;margin:0 0 12px}}
.stat-row{{display:flex;gap:18px;flex-wrap:wrap;margin-bottom:8px}}
.stat{{background:#0f172a;border-radius:7px;padding:10px 18px;min-width:110px}}
.stat .label{{font-size:0.75rem;color:#64748b;margin-bottom:3px}}
.stat .value{{font-size:1.3rem;color:#f8fafc;font-weight:700}}
.legend{{display:flex;gap:16px;font-size:0.8rem;margin-top:8px}}
.dot{{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:4px}}
svg{{display:block}}
</style></head>
<body>
<h1>Tactile Sensor Fusion</h1>
<div class='subtitle'>Fingertip tactile array · 12-sensor grid · real-time contact force estimation · port {PORT}</div>
<div class='grid'>

  <div class='card' style='min-width:300px;max-width:340px'>
    <h2>Fingertip Sensor Grid (4×3)</h2>
    <svg width='230' height='310'>{heatmap_cells}</svg>
    <div style='font-size:0.8rem;color:#64748b;margin-top:6px'>Pressure intensity (0–1.0) per taxel</div>
    <div class='stat-row' style='margin-top:10px'>
      <div class='stat'><div class='label'>Active Taxels (&gt;0.6)</div><div class='value' style='color:#f59e0b'>{hot_count}/12</div></div>
    </div>
  </div>

  <div class='card' style='min-width:360px'>
    <h2>Pressure Waveform (40 samples)</h2>
    <svg width='{w_svg}' height='{h_svg}' style='background:#0f172a;border-radius:6px'>
      <line x1='20' y1='10' x2='20' y2='{h_svg-10}' stroke='#334155' stroke-width='1'/>
      <line x1='20' y1='{h_svg-10}' x2='{w_svg-20}' y2='{h_svg-10}' stroke='#334155' stroke-width='1'/>
      <polyline points='{px_pts}' fill='none' stroke='#38bdf8' stroke-width='2.2'/>
    </svg>
    <div class='stat-row' style='margin-top:10px'>
      <div class='stat'><div class='label'>Avg Pressure</div><div class='value'>{avg_pressure}</div></div>
      <div class='stat'><div class='label'>Peak Pressure</div><div class='value' style='color:#f87171'>{max_pressure}</div></div>
    </div>
  </div>

  <div class='card' style='min-width:360px'>
    <h2>Contact Force: Fx / Fy / Fz (30 steps)</h2>
    <svg width='500' height='120' style='background:#0f172a;border-radius:6px'>
      <line x1='20' y1='10' x2='20' y2='110' stroke='#334155' stroke-width='1'/>
      <line x1='20' y1='60' x2='480' y2='60' stroke='#334155' stroke-width='1' stroke-dasharray='4'/>
      {fx_line}{fy_line}{fz_line}
    </svg>
    <div class='legend'>
      <span><span class='dot' style='background:#f59e0b'></span>Fx</span>
      <span><span class='dot' style='background:#34d399'></span>Fy</span>
      <span><span class='dot' style='background:#60a5fa'></span>Fz</span>
    </div>
    <div class='stat-row' style='margin-top:10px'>
      <div class='stat'><div class='label'>Mean Fz (N)</div><div class='value' style='color:#60a5fa'>{fz_mean}</div></div>
    </div>
  </div>

  <div class='card' style='min-width:340px'>
    <h2>Impedance Spectroscopy (20 pts)</h2>
    <svg width='480' height='120' style='background:#0f172a;border-radius:6px'>
      <line x1='20' y1='10' x2='20' y2='110' stroke='#334155'/>
      <line x1='20' y1='110' x2='460' y2='110' stroke='#334155'/>
      {''.join(f"<rect x='{20+i*22}' y='{int(110 - (impedance[i]-80)/120*90)}' width='18' height='{int((impedance[i]-80)/120*90)}' rx='3' fill='#a78bfa' opacity='0.82'/>" for i in range(20))}
    </svg>
    <div style='font-size:0.78rem;color:#64748b;margin-top:4px'>Frequency sweep 10 Hz – 80 kHz · Ω response</div>
  </div>

</div>
<div style='padding:8px 24px 20px;color:#475569;font-size:0.78rem'>
  Sensor model: BioTac SP equivalent · Fusion algo: Extended Kalman Filter · Update rate: 1 kHz
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Tactile Sensor Fusion")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return build_html()

    @app.get("/health")
    def health():
        return {"status": "ok", "port": PORT, "service": "tactile_sensor_fusion"}

    @app.get("/sensors")
    def sensors():
        random.seed()
        grid = [[round(random.uniform(0.05, 0.95), 3) for _ in range(3)] for _ in range(4)]
        return {"grid_4x3": grid, "hot_taxels": sum(1 for row in grid for v in row if v > 0.6)}

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
