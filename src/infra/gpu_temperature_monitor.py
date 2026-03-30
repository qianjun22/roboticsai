"""GPU Temperature Monitor — port 8604
OCI Robot Cloud — cycle-136B
Monitors thermal state across GPU nodes with heatmaps and timeline visualizations.
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8604


def build_html() -> str:
    # Thermal heatmap data: 4 GPU nodes x 8 sensors
    # Sensors: GPU_Core, GPU_Mem, VRAM, PCIe, VRM, Hotspot, Ambient, Exhaust
    nodes = ["GPU1 (Phoenix)", "GPU2 (Titan)", "GPU3 (Atlas)", "GPU4 (Forge)"]
    sensor_labels = ["GPU_Core", "GPU_Mem", "VRAM", "PCIe", "VRM", "Hotspot", "Ambient", "Exhaust"]
    temps = [
        [68, 66, 67, 65, 70, 71, 42, 55],   # GPU1 Phoenix — slightly elevated trend
        [66, 65, 66, 64, 68, 69, 41, 53],   # GPU2 Titan
        [67, 66, 67, 65, 69, 70, 42, 54],   # GPU3 Atlas
        [76, 74, 75, 72, 77, 79, 44, 61],   # GPU4 Forge — training peak
    ]

    def temp_color(t):
        # Blue (cool) 60°C -> Yellow 72°C -> Orange 78°C -> Red (hot) 85°C
        if t <= 65:
            r, g, b = 56, 189, 248   # sky blue
        elif t <= 70:
            ratio = (t - 65) / 5.0
            r = int(56 + ratio * (250 - 56))
            g = int(189 + ratio * (204 - 189))
            b = int(248 + ratio * (20 - 248))
        elif t <= 76:
            ratio = (t - 70) / 6.0
            r = int(250 + ratio * (239 - 250))
            g = int(204 + ratio * (68 - 204))
            b = int(20 + ratio * (68 - 20))
        else:
            ratio = min((t - 76) / 9.0, 1.0)
            r = int(239 + ratio * (199 - 239))
            g = int(68 + ratio * (0 - 68))
            b = int(68 + ratio * (0 - 68))
        return f"rgb({r},{g},{b})"

    # Build heatmap SVG
    cell_w, cell_h = 82, 44
    label_w, label_h = 130, 30
    hm_w = label_w + len(sensor_labels) * cell_w + 20
    hm_h = label_h + len(nodes) * cell_h + 20

    heatmap_cells = ""
    for ni, node in enumerate(nodes):
        y = label_h + ni * cell_h
        # Row label
        heatmap_cells += f'<text x="{label_w - 8}" y="{y + cell_h//2 + 5}" fill="#94a3b8" font-size="11" text-anchor="end">{node}</text>'
        for si, sensor in enumerate(sensor_labels):
            x = label_w + si * cell_w
            t = temps[ni][si]
            color = temp_color(t)
            heatmap_cells += f'<rect x="{x + 2}" y="{y + 2}" width="{cell_w - 4}" height="{cell_h - 4}" rx="4" fill="{color}" opacity="0.88"/>'
            heatmap_cells += f'<text x="{x + cell_w//2}" y="{y + cell_h//2 + 5}" fill="#0f172a" font-size="13" font-weight="bold" text-anchor="middle">{t}°C</text>'

    sensor_headers = ""
    for si, sensor in enumerate(sensor_labels):
        x = label_w + si * cell_w + cell_w // 2
        sensor_headers += f'<text x="{x}" y="20" fill="#94a3b8" font-size="10" text-anchor="middle">{sensor}</text>'

    heatmap_svg = f"""
    <svg viewBox="0 0 {hm_w} {hm_h}" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:{hm_w}px;">
      <rect width="{hm_w}" height="{hm_h}" rx="8" fill="#1e293b"/>
      {sensor_headers}
      {heatmap_cells}
    </svg>"""

    # Temperature timeline SVG — GPU4 24h
    tl_w, tl_h = 760, 200
    pad_l, pad_r, pad_t, pad_b = 50, 20, 20, 40
    plot_w = tl_w - pad_l - pad_r
    plot_h = tl_h - pad_t - pad_b
    t_min, t_max = 60, 90

    # 24 hourly data points — idle baseline 65, training peaks to 79, evening cool-down
    gpu4_temps = [
        65, 65, 65, 65, 65, 66,   # 00-05 idle night
        67, 68, 71, 75, 78, 79,   # 06-11 training ramp
        79, 78, 77, 75, 73, 71,   # 12-17 training then decay
        68, 66, 65, 65, 65, 65,   # 18-23 idle evening
    ]

    def tx(hour):
        return pad_l + int(hour / 23.0 * plot_w)

    def ty(temp):
        return pad_t + plot_h - int((temp - t_min) / (t_max - t_min) * plot_h)

    # Line path
    pts = " ".join(f"{tx(i)},{ty(t)}" for i, t in enumerate(gpu4_temps))
    area_pts = f"{tx(0)},{pad_t + plot_h} " + pts + f" {tx(23)},{pad_t + plot_h}"

    # Throttle threshold line at 83°C
    throttle_y = ty(83)
    # Y-axis gridlines
    grid = ""
    for temp_mark in [65, 70, 75, 80, 83, 85]:
        gy = ty(temp_mark)
        color = "#C74634" if temp_mark == 83 else "#334155"
        dash = "4,4" if temp_mark == 83 else "2,4"
        grid += f'<line x1="{pad_l}" y1="{gy}" x2="{tl_w - pad_r}" y2="{gy}" stroke="{color}" stroke-width="1" stroke-dasharray="{dash}"/>'
        grid += f'<text x="{pad_l - 6}" y="{gy + 4}" fill="#64748b" font-size="10" text-anchor="end">{temp_mark}°</text>'

    # X-axis labels
    x_labels = ""
    for h in [0, 6, 12, 18, 23]:
        x_labels += f'<text x="{tx(h)}" y="{pad_t + plot_h + 16}" fill="#64748b" font-size="10" text-anchor="middle">{h:02d}:00</text>'

    timeline_svg = f"""
    <svg viewBox="0 0 {tl_w} {tl_h}" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:{tl_w}px;">
      <rect width="{tl_w}" height="{tl_h}" rx="8" fill="#1e293b"/>
      {grid}
      <polyline points="{area_pts}" fill="#38bdf820" stroke="none"/>
      <polyline points="{pts}" fill="none" stroke="#38bdf8" stroke-width="2.5" stroke-linejoin="round"/>
      {x_labels}
      <text x="{throttle_y - 2}" y="{throttle_y - 6}" transform="rotate(0)" fill="#C74634" font-size="10">Throttle 83°C</text>
      <text x="{pad_l + plot_w//2}" y="{pad_t + plot_h + 32}" fill="#64748b" font-size="11" text-anchor="middle">GPU4 (Forge) — 24h Temperature Profile</text>
    </svg>"""

    # Cooling efficiency bar chart SVG
    ce_w, ce_h = 660, 220
    bar_data = [
        # node, inlet_temp, hotspot_temp, delta
        ("GPU1", 22.1, 71.0, 48.9),
        ("GPU2", 21.8, 69.0, 47.2),
        ("GPU3", 22.3, 70.0, 47.7),
        ("GPU4", 22.5, 79.0, 56.5),
    ]
    target_delta = 50.0
    ce_pad_l, ce_pad_r, ce_pad_t, ce_pad_b = 60, 20, 20, 50
    ce_plot_w = ce_w - ce_pad_l - ce_pad_r
    ce_plot_h = ce_h - ce_pad_t - ce_pad_b
    max_delta = 65.0
    bar_w = ce_plot_w // (len(bar_data) * 3 + len(bar_data) + 1)
    group_w = bar_w * 3 + bar_w

    bars_svg = ""
    legend_colors = ["#38bdf8", "#C74634", "#a3e635"]
    legend_labels = ["Inlet Temp", "Hotspot Temp", "Delta"]
    bar_series = [
        [d[1] for d in bar_data],
        [d[2] for d in bar_data],
        [d[3] for d in bar_data],
    ]

    for gi, (node, inlet, hotspot, delta) in enumerate(bar_data):
        gx = ce_pad_l + gi * (group_w + bar_w // 2)
        for si, (series, color) in enumerate(zip(bar_series, legend_colors)):
            val = series[gi]
            bh = int(val / max_delta * ce_plot_h)
            bx = gx + si * bar_w
            by = ce_pad_t + ce_plot_h - bh
            bars_svg += f'<rect x="{bx}" y="{by}" width="{bar_w - 3}" height="{bh}" rx="2" fill="{color}" opacity="0.85"/>'
        # Node label
        bars_svg += f'<text x="{gx + group_w//2 - bar_w//2}" y="{ce_pad_t + ce_plot_h + 16}" fill="#94a3b8" font-size="11" text-anchor="middle">{node}</text>'

    # Target delta line
    target_y = ce_pad_t + ce_plot_h - int(target_delta / max_delta * ce_plot_h)
    bars_svg += f'<line x1="{ce_pad_l}" y1="{target_y}" x2="{ce_w - ce_pad_r}" y2="{target_y}" stroke="#facc15" stroke-width="1.5" stroke-dasharray="6,3"/>'
    bars_svg += f'<text x="{ce_w - ce_pad_r - 2}" y="{target_y - 5}" fill="#facc15" font-size="10" text-anchor="end">Target Δ 50°C</text>'

    # Y-axis
    for mark in [0, 20, 40, 60]:
        gy = ce_pad_t + ce_plot_h - int(mark / max_delta * ce_plot_h)
        bars_svg += f'<line x1="{ce_pad_l}" y1="{gy}" x2="{ce_w - ce_pad_r}" y2="{gy}" stroke="#334155" stroke-width="1" stroke-dasharray="2,4"/>'
        bars_svg += f'<text x="{ce_pad_l - 6}" y="{gy + 4}" fill="#64748b" font-size="10" text-anchor="end">{mark}°</text>'

    # Legend
    legend_svg = ""
    for li, (lc, ll) in enumerate(zip(legend_colors, legend_labels)):
        lx = ce_pad_l + li * 130
        legend_svg += f'<rect x="{lx}" y="{ce_h - 18}" width="12" height="12" rx="2" fill="{lc}"/>'
        legend_svg += f'<text x="{lx + 16}" y="{ce_h - 7}" fill="#94a3b8" font-size="11">{ll}</text>'

    cooling_svg = f"""
    <svg viewBox="0 0 {ce_w} {ce_h}" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:{ce_w}px;">
      <rect width="{ce_w}" height="{ce_h}" rx="8" fill="#1e293b"/>
      {bars_svg}
      {legend_svg}
    </svg>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>GPU Temperature Monitor — OCI Robot Cloud</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; padding: 24px; }}
    h1 {{ color: #C74634; font-size: 1.6rem; font-weight: 700; margin-bottom: 4px; }}
    h2 {{ color: #38bdf8; font-size: 1.1rem; font-weight: 600; margin: 28px 0 12px; }}
    .subtitle {{ color: #64748b; font-size: 0.85rem; margin-bottom: 28px; }}
    .metrics {{ display: grid; grid-template-columns: repeat(4,1fr); gap: 16px; margin-bottom: 32px; }}
    .metric {{ background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 16px; }}
    .metric-label {{ color: #64748b; font-size: 0.75rem; text-transform: uppercase; letter-spacing: .05em; margin-bottom: 6px; }}
    .metric-value {{ font-size: 1.6rem; font-weight: 700; }}
    .metric-sub {{ color: #64748b; font-size: 0.78rem; margin-top: 4px; }}
    .ok {{ color: #4ade80; }}
    .warn {{ color: #facc15; }}
    .accent {{ color: #38bdf8; }}
    .card {{ background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 20px; margin-bottom: 24px; overflow-x: auto; }}
    .badge {{ display:inline-block; padding:2px 10px; border-radius:999px; font-size:0.75rem; font-weight:600; }}
    .badge-ok {{ background:#14532d; color:#4ade80; }}
    .badge-warn {{ background:#422006; color:#facc15; }}
  </style>
</head>
<body>
  <h1>GPU Temperature Monitor</h1>
  <p class="subtitle">OCI Robot Cloud — Thermal Management Dashboard | Port {PORT}</p>

  <div class="metrics">
    <div class="metric">
      <div class="metric-label">GPU4 (Forge) Peak</div>
      <div class="metric-value ok">79°C</div>
      <div class="metric-sub">Training workload &nbsp;<span class="badge badge-ok">OK</span></div>
    </div>
    <div class="metric">
      <div class="metric-label">Phoenix GPU1 Trend</div>
      <div class="metric-value warn">+1.8°C/mo</div>
      <div class="metric-sub">Gradual rise detected &nbsp;<span class="badge badge-warn">WATCH</span></div>
    </div>
    <div class="metric">
      <div class="metric-label">Throttle Events (30d)</div>
      <div class="metric-value ok">0</div>
      <div class="metric-sub">No thermal throttling</div>
    </div>
    <div class="metric">
      <div class="metric-label">Weeks to Issue</div>
      <div class="metric-value accent">14 wks</div>
      <div class="metric-sub">At Phoenix current trend</div>
    </div>
  </div>

  <h2>Thermal State Heatmap — All Nodes (Current)</h2>
  <div class="card">
    {heatmap_svg}
  </div>

  <h2>Temperature Timeline — GPU4 Forge (24h)</h2>
  <div class="card">
    {timeline_svg}
  </div>

  <h2>Cooling Efficiency by Node</h2>
  <div class="card">
    {cooling_svg}
  </div>

  <p style="color:#334155;font-size:0.75rem;margin-top:32px;">OCI Robot Cloud · GPU Temperature Monitor · Port {PORT} · cycle-136B</p>
</body>
</html>"""
    return html


if USE_FASTAPI:
    app = FastAPI(title="GPU Temperature Monitor", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def index():
        return build_html()

    @app.get("/health")
    async def health():
        return {
            "status": "ok",
            "service": "gpu_temperature_monitor",
            "port": PORT,
            "nodes": 4,
            "sensors_per_node": 8,
            "gpu4_peak_temp_c": 79,
            "throttle_events_30d": 0,
            "phoenix_trend_c_per_month": 1.8,
            "weeks_to_issue": 14,
        }

    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=PORT)

else:
    from http.server import BaseHTTPRequestHandler, HTTPServer
    import json

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass

        def do_GET(self):
            if self.path == "/health":
                body = json.dumps({"status": "ok", "service": "gpu_temperature_monitor", "port": PORT}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)
            else:
                body = build_html().encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(body)

    if __name__ == "__main__":
        print(f"Serving on http://0.0.0.0:{PORT} (stdlib HTTPServer)")
        HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
