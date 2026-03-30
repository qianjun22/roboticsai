"""Fleet Energy Monitor — FastAPI port 8723"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8723

def build_html():
    random.seed(7)
    n_robots = 12
    robot_ids = [f"R{str(i).zfill(3)}" for i in range(1, n_robots + 1)]
    locations = ["Warehouse-A", "Warehouse-B", "Assembly-1", "Assembly-2", "Dock"]
    models = ["GR00T-N1.6", "GR00T-N1.5", "Spot-3", "UR10e"]

    # Per-robot stats
    random.seed(7)
    robots = []
    for rid in robot_ids:
        battery = round(random.uniform(18.0, 98.0), 1)
        draw_w = round(random.uniform(120.0, 480.0), 1)
        temp_c = round(random.uniform(34.0, 68.0), 1)
        uptime_h = round(random.uniform(0.5, 23.5), 1)
        loc = random.choice(locations)
        model = random.choice(models)
        status = "charging" if battery < 25 else ("idle" if draw_w < 160 else "active")
        robots.append({
            "id": rid, "battery": battery, "draw_w": draw_w,
            "temp_c": temp_c, "uptime_h": uptime_h,
            "loc": loc, "model": model, "status": status
        })

    # Fleet totals
    total_draw_kw = round(sum(r["draw_w"] for r in robots) / 1000, 2)
    avg_battery = round(sum(r["battery"] for r in robots) / n_robots, 1)
    max_temp = max(r["temp_c"] for r in robots)
    active_count = sum(1 for r in robots if r["status"] == "active")

    # 24-hour energy consumption curve (kWh per hour, sinusoidal workday pattern)
    hours = list(range(24))
    energy_kwh = [
        round(
            2.1 + 3.8 * max(0, math.sin(math.pi * (h - 7) / 10)) +
            random.uniform(-0.3, 0.3), 2
        )
        for h in hours
    ]
    total_kwh_today = round(sum(energy_kwh), 1)
    peak_kwh = max(energy_kwh)

    # SVG bar chart for 24h energy
    svg_w, svg_h = 600, 160
    pad_l, pad_r, pad_t, pad_b = 44, 10, 14, 28
    chart_w = svg_w - pad_l - pad_r
    chart_h = svg_h - pad_t - pad_b
    bar_w = chart_w / 24 - 2
    max_val = max(energy_kwh) * 1.1

    bars = ""
    for i, v in enumerate(energy_kwh):
        bh = (v / max_val) * chart_h
        x = pad_l + i * (chart_w / 24) + 1
        y = pad_t + chart_h - bh
        color = "#f87171" if v >= peak_kwh * 0.9 else "#38bdf8"
        bars += f"<rect x='{x:.1f}' y='{y:.1f}' width='{bar_w:.1f}' height='{bh:.1f}' fill='{color}' rx='2'/>"

    def bar_y(v): return pad_t + chart_h - (v / max_val) * chart_h
    x_labels = "".join(
        f"<text x='{pad_l + i*(chart_w/24)+bar_w/2:.1f}' y='{svg_h-6}' fill='#64748b' font-size='9' text-anchor='middle'>{i:02d}</text>"
        for i in range(0, 24, 3)
    )

    # Battery gauge circles for each robot (SVG)
    gauges = ""
    cols = 6
    g_w, g_h = 80, 90
    for idx, r in enumerate(robots):
        gx = (idx % cols) * g_w + 10
        gy = (idx // cols) * g_h + 10
        cx, cy, radius = gx + 30, gy + 30, 24
        pct = r["battery"] / 100
        circ = 2 * math.pi * radius
        dash = circ * pct
        gap = circ * (1 - pct)
        color = "#4ade80" if pct > 0.5 else ("#facc15" if pct > 0.25 else "#f87171")
        status_color = {"active": "#4ade80", "idle": "#facc15", "charging": "#60a5fa"}[r["status"]]
        gauges += (
            f"<circle cx='{cx}' cy='{cy}' r='{radius}' fill='none' stroke='#334155' stroke-width='5'/>"
            f"<circle cx='{cx}' cy='{cy}' r='{radius}' fill='none' stroke='{color}' stroke-width='5'"
            f" stroke-dasharray='{dash:.1f} {gap:.1f}' stroke-linecap='round'"
            f" transform='rotate(-90 {cx} {cy})'/>"
            f"<text x='{cx}' y='{cy+4}' fill='#e2e8f0' font-size='9' text-anchor='middle' font-weight='600'>{r['battery']}%</text>"
            f"<text x='{cx}' y='{gy+66}' fill='{status_color}' font-size='8' text-anchor='middle'>{r['id']}</text>"
            f"<text x='{cx}' y='{gy+76}' fill='#64748b' font-size='7' text-anchor='middle'>{r['draw_w']}W</text>"
        )
    gauge_svg_w = cols * g_w + 20
    gauge_svg_h = (n_robots // cols) * g_h + 20

    # Robot table rows
    rows = "".join(
        f"<tr><td>{r['id']}</td><td>{r['model']}</td><td>{r['loc']}</td>"
        f"<td><span class='badge' style='background:{{'active':'#166534','idle':'#713f12','charging':'#1e3a5f'}[r['status']]};color:{{'active':'#4ade80','idle':'#facc15','charging':'#60a5fa'}[r['status']]}'>{r['status']}</span></td>"
        f"<td>{r['battery']}%</td><td>{r['draw_w']}W</td><td>{r['temp_c']}°C</td><td>{r['uptime_h']}h</td></tr>"
        for r in robots
    )

    return f"""<!DOCTYPE html><html lang='en'><head><title>Fleet Energy Monitor</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui,sans-serif}}
h1{{color:#C74634;margin:0;padding:20px 24px 4px;font-size:1.5rem;letter-spacing:.02em}}
.subtitle{{color:#64748b;padding:0 24px 16px;font-size:.85rem}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;padding:0 16px 16px}}
.card{{background:#1e293b;padding:20px;border-radius:8px}}
.card.wide{{grid-column:span 4}}
.card.half{{grid-column:span 2}}
.stat-val{{font-size:2rem;font-weight:700;color:#38bdf8}}
.stat-label{{font-size:.75rem;color:#94a3b8;margin-top:4px}}
h2{{color:#38bdf8;margin:0 0 12px;font-size:1rem}}
table{{width:100%;border-collapse:collapse;font-size:.82rem}}
th{{color:#94a3b8;font-weight:600;border-bottom:1px solid #334155;padding:6px 8px;text-align:left}}
td{{padding:6px 8px;border-bottom:1px solid #243044}}
tr:hover td{{background:#263249}}
.badge{{padding:2px 8px;border-radius:12px;font-size:.72rem;font-weight:600}}
</style></head>
<body>
<h1>Fleet Energy Monitor</h1>
<div class='subtitle'>Real-time power consumption and battery status across {n_robots}-robot fleet — port {PORT}</div>
<div class='grid'>
  <div class='card'><div class='stat-val'>{total_draw_kw} kW</div><div class='stat-label'>Fleet Draw (now)</div></div>
  <div class='card'><div class='stat-val'>{total_kwh_today} kWh</div><div class='stat-label'>Energy Used Today</div></div>
  <div class='card'><div class='stat-val'>{avg_battery}%</div><div class='stat-label'>Fleet Avg Battery</div></div>
  <div class='card'><div class='stat-val' style='color:{"#f87171" if max_temp>65 else "#4ade80"}'>{max_temp}°C</div><div class='stat-label'>Max Joint Temp</div></div>

  <div class='card wide'>
    <h2>24-Hour Energy Consumption (kWh per hour)</h2>
    <svg width='{svg_w}' height='{svg_h}' viewBox='0 0 {svg_w} {svg_h}'>
      <line x1='{pad_l}' y1='{pad_t}' x2='{pad_l}' y2='{pad_t+chart_h}' stroke='#475569'/>
      <line x1='{pad_l}' y1='{pad_t+chart_h}' x2='{pad_l+chart_w}' y2='{pad_t+chart_h}' stroke='#475569'/>
      <line x1='{pad_l}' y1='{bar_y(peak_kwh*0.9):.1f}' x2='{pad_l+chart_w}' y2='{bar_y(peak_kwh*0.9):.1f}' stroke='#f87171' stroke-dasharray='4' opacity='.5'/>
      {bars}
      {x_labels}
      <text x='{pad_l-4}' y='{pad_t+4}' fill='#64748b' font-size='9' text-anchor='end'>{max_val:.1f}</text>
      <text x='{pad_l-4}' y='{pad_t+chart_h//2}' fill='#64748b' font-size='9' text-anchor='end'>{max_val/2:.1f}</text>
      <text x='{pad_l-4}' y='{pad_t+chart_h}' fill='#64748b' font-size='9' text-anchor='end'>0</text>
      <text x='{pad_l+chart_w//2}' y='{svg_h-1}' fill='#475569' font-size='9' text-anchor='middle'>Hour (UTC)</text>
    </svg>
  </div>

  <div class='card half'>
    <h2>Battery &amp; Power per Robot</h2>
    <svg width='{gauge_svg_w}' height='{gauge_svg_h}' viewBox='0 0 {gauge_svg_w} {gauge_svg_h}'>
      {gauges}
    </svg>
    <div style='font-size:.72rem;color:#64748b;margin-top:4px'>
      <span style='color:#4ade80'>&#9679;</span> &gt;50% &nbsp;
      <span style='color:#facc15'>&#9679;</span> 25-50% &nbsp;
      <span style='color:#f87171'>&#9679;</span> &lt;25%
    </div>
  </div>

  <div class='card half'>
    <h2>Fleet Status Summary</h2>
    <table>
      <tr><th>Status</th><th>Count</th><th>Avg Draw</th></tr>
      <tr><td><span class='badge' style='background:#166534;color:#4ade80'>active</span></td>
          <td>{sum(1 for r in robots if r['status']=='active')}</td>
          <td>{round(sum(r['draw_w'] for r in robots if r['status']=='active') / max(1,sum(1 for r in robots if r['status']=='active')),1)}W</td></tr>
      <tr><td><span class='badge' style='background:#713f12;color:#facc15'>idle</span></td>
          <td>{sum(1 for r in robots if r['status']=='idle')}</td>
          <td>{round(sum(r['draw_w'] for r in robots if r['status']=='idle') / max(1,sum(1 for r in robots if r['status']=='idle')),1)}W</td></tr>
      <tr><td><span class='badge' style='background:#1e3a5f;color:#60a5fa'>charging</span></td>
          <td>{sum(1 for r in robots if r['status']=='charging')}</td>
          <td>{round(sum(r['draw_w'] for r in robots if r['status']=='charging') / max(1,sum(1 for r in robots if r['status']=='charging')),1)}W</td></tr>
    </table>
    <div style='margin-top:16px;font-size:.82rem;color:#94a3b8'>
      Est. daily cost: <strong style='color:#38bdf8'>${round(total_kwh_today * 0.12, 2)}</strong>
      &nbsp;|&nbsp; CO₂ offset: <strong style='color:#4ade80'>{round(total_kwh_today * 0.233, 1)} kg</strong>
    </div>
  </div>

  <div class='card wide'>
    <h2>All Robots — Detailed View</h2>
    <table>
      <thead><tr><th>ID</th><th>Model</th><th>Location</th><th>Status</th><th>Battery</th><th>Draw</th><th>Temp</th><th>Uptime</th></tr></thead>
      <tbody>{rows}</tbody>
    </table>
  </div>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Fleet Energy Monitor")
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
