"""Simulation Stress Tester — FastAPI port 8776"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8776

def build_html():
    random.seed(42)

    # Generate stress test scenario data
    scenarios = [
        ("Pick-and-Place", 1200, 98.3, 0.87),
        ("Stack Blocks",   850,  95.1, 1.24),
        ("Door Opening",   640,  91.7, 2.01),
        ("Bin Sorting",    1500, 97.6, 0.92),
        ("Cable Routing",  420,  88.4, 3.15),
        ("Bolt Assembly",  780,  93.2, 1.68),
    ]

    # Frame-time series (sinusoidal load spikes)
    n = 60
    times   = [i for i in range(n)]
    fps_vals = [60 - 8 * math.sin(i * 0.3) - 4 * math.sin(i * 1.1) + random.uniform(-1.5, 1.5) for i in range(n)]
    mem_vals = [3.2 + 0.6 * math.sin(i * 0.15) + 0.2 * random.random() for i in range(n)]

    # SVG frame-rate sparkline
    svg_w, svg_h = 600, 120
    fps_min, fps_max = min(fps_vals), max(fps_vals)
    def fx(i): return int(svg_w * i / (n - 1))
    def fy(v): return int(svg_h - (v - fps_min) / (fps_max - fps_min + 1e-9) * (svg_h - 10) - 5)
    polyline_pts = " ".join(f"{fx(i)},{fy(v)}" for i, v in enumerate(fps_vals))

    # Memory area chart
    mem_min, mem_max = min(mem_vals), max(mem_vals)
    def my(v): return int(svg_h - (v - mem_min) / (mem_max - mem_min + 1e-9) * (svg_h - 10) - 5)
    mem_area = " ".join(f"{fx(i)},{my(v)}" for i, v in enumerate(mem_vals))
    mem_area_closed = f"{fx(0)},{svg_h} " + mem_area + f" {fx(n-1)},{svg_h}"

    # Scenario rows HTML
    rows = ""
    for name, eps, sr, lat in scenarios:
        bar_w = int(sr * 2)
        color = "#22c55e" if sr >= 95 else "#f59e0b" if sr >= 90 else "#ef4444"
        rows += f"""
        <tr>
          <td style='padding:8px 12px;font-weight:600'>{name}</td>
          <td style='padding:8px 12px;color:#94a3b8'>{eps:,}</td>
          <td style='padding:8px 12px'>
            <div style='background:#334155;border-radius:4px;height:14px;width:200px'>
              <div style='background:{color};width:{bar_w}px;height:14px;border-radius:4px'></div>
            </div>
            <span style='color:{color};font-size:12px;margin-left:6px'>{sr}%</span>
          </td>
          <td style='padding:8px 12px;color:#38bdf8'>{lat}s</td>
        </tr>"""

    # Radar chart for system health (hexagonal)
    cx, cy, r = 160, 140, 110
    metrics = [
        ("CPU",     0.83),
        ("GPU",     0.91),
        ("Memory",  0.74),
        ("I/O",     0.88),
        ("Network", 0.67),
        ("Physics", 0.95),
    ]
    angles = [math.pi / 2 + 2 * math.pi * i / len(metrics) for i in range(len(metrics))]
    outer_pts = " ".join(f"{cx + r * math.cos(a):.1f},{cy - r * math.sin(a):.1f}" for a in angles)
    inner_pts = " ".join(f"{cx + r * v * math.cos(a):.1f},{cy - r * v * math.sin(a):.1f}"
                          for (_, v), a in zip(metrics, angles))
    axis_lines = "".join(
        f"<line x1='{cx}' y1='{cy}' x2='{cx + r * math.cos(a):.1f}' y2='{cy - r * math.sin(a):.1f}'"
        f" stroke='#334155' stroke-width='1'/>"
        f"<text x='{cx + (r + 18) * math.cos(a):.1f}' y='{cy - (r + 18) * math.sin(a):.1f}'"
        f" fill='#94a3b8' font-size='11' text-anchor='middle'>{name}</text>"
        for (name, _), a in zip(metrics, angles)
    )

    overall_fps  = sum(fps_vals) / len(fps_vals)
    overall_mem  = sum(mem_vals) / len(mem_vals)
    total_eps    = sum(s[1] for s in scenarios)
    avg_sr       = sum(s[2] for s in scenarios) / len(scenarios)

    return f"""<!DOCTYPE html><html><head><title>Simulation Stress Tester</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui,sans-serif}}
h1{{color:#C74634;margin:0;padding:24px 24px 0}}
h2{{color:#38bdf8;margin:0 0 14px}}
.card{{background:#1e293b;padding:20px;margin:14px;border-radius:10px;box-shadow:0 2px 12px #0004}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;padding:0 14px}}
.kpi{{background:#1e293b;border-radius:10px;padding:18px;text-align:center}}
.kpi .val{{font-size:2rem;font-weight:700;color:#f8fafc}}
.kpi .lbl{{color:#64748b;font-size:13px;margin-top:4px}}
table{{width:100%;border-collapse:collapse}}
tr:hover td{{background:#263244}}
td{{border-bottom:1px solid #1e293b}}
.badge{{display:inline-block;background:#0f172a;border:1px solid #C74634;color:#C74634;font-size:11px;border-radius:4px;padding:2px 8px;margin-left:8px}}
</style></head><body>
<h1>Simulation Stress Tester <span class='badge'>port {PORT}</span></h1>

<div class='grid'>
  <div class='kpi'><div class='val'>{overall_fps:.1f}</div><div class='lbl'>Avg FPS</div></div>
  <div class='kpi'><div class='val'>{overall_mem:.2f} GB</div><div class='lbl'>Avg Memory</div></div>
  <div class='kpi'><div class='val'>{total_eps:,}</div><div class='lbl'>Total Episodes</div></div>
  <div class='kpi'><div class='val'>{avg_sr:.1f}%</div><div class='lbl'>Avg Success Rate</div></div>
</div>

<div style='display:grid;grid-template-columns:1fr 1fr;'>

<div class='card'>
  <h2>Frame Rate Over Time</h2>
  <svg width='{svg_w}' height='{svg_h}' style='display:block'>
    <defs><linearGradient id='fps_grad' x1='0' y1='0' x2='0' y2='1'>
      <stop offset='0%' stop-color='#38bdf8' stop-opacity='0.3'/>
      <stop offset='100%' stop-color='#38bdf8' stop-opacity='0'/>
    </linearGradient></defs>
    <polygon points='{fx(0)},{svg_h} {polyline_pts} {fx(n-1)},{svg_h}' fill='url(#fps_grad)'/>
    <polyline points='{polyline_pts}' fill='none' stroke='#38bdf8' stroke-width='2'/>
    <text x='8' y='14' fill='#64748b' font-size='10'>FPS {fps_max:.0f}</text>
    <text x='8' y='{svg_h-2}' fill='#64748b' font-size='10'>FPS {fps_min:.0f}</text>
  </svg>
</div>

<div class='card'>
  <h2>Memory Usage (GB)</h2>
  <svg width='{svg_w}' height='{svg_h}' style='display:block'>
    <defs><linearGradient id='mem_grad' x1='0' y1='0' x2='0' y2='1'>
      <stop offset='0%' stop-color='#a78bfa' stop-opacity='0.35'/>
      <stop offset='100%' stop-color='#a78bfa' stop-opacity='0'/>
    </linearGradient></defs>
    <polygon points='{mem_area_closed}' fill='url(#mem_grad)'/>
    <polyline points='{mem_area}' fill='none' stroke='#a78bfa' stroke-width='2'/>
    <text x='8' y='14' fill='#64748b' font-size='10'>{mem_max:.2f} GB</text>
    <text x='8' y='{svg_h-2}' fill='#64748b' font-size='10'>{mem_min:.2f} GB</text>
  </svg>
</div>

</div>

<div style='display:grid;grid-template-columns:2fr 1fr;'>

<div class='card'>
  <h2>Scenario Benchmark</h2>
  <table>
    <thead><tr style='color:#64748b;font-size:12px'>
      <th style='text-align:left;padding:6px 12px'>Scenario</th>
      <th style='text-align:left;padding:6px 12px'>Episodes</th>
      <th style='text-align:left;padding:6px 12px'>Success Rate</th>
      <th style='text-align:left;padding:6px 12px'>Avg Latency</th>
    </tr></thead>
    <tbody>{rows}</tbody>
  </table>
</div>

<div class='card'>
  <h2>System Health Radar</h2>
  <svg width='320' height='280' style='display:block;margin:auto'>
    <polygon points='{outer_pts}' fill='none' stroke='#334155' stroke-width='1'/>
    {axis_lines}
    <polygon points='{inner_pts}' fill='#38bdf855' stroke='#38bdf8' stroke-width='2'/>
    {''.join(f"<circle cx='{cx + r*v*math.cos(a):.1f}' cy='{cy - r*v*math.sin(a):.1f}' r='4' fill='#38bdf8'/>" for (_,v),a in zip(metrics,angles))}
  </svg>
</div>

</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Simulation Stress Tester")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return build_html()

    @app.get("/health")
    def health():
        return {"status": "ok", "port": PORT, "service": "simulation_stress_tester"}

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
