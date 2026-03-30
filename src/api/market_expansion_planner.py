"""Market Expansion Planner — FastAPI port 8751"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8751

def build_html():
    rng = random.Random(2026)

    # Market TAM/SAM/SOM data (USD millions)
    regions = ["North America", "Europe", "APAC", "LatAm", "MEA"]
    tam     = [4800, 3100, 5600, 1200, 900]
    sam     = [1440, 930,  1680,  360,  270]
    som     = [ 216, 140,   252,   54,   41]

    # Quarterly revenue forecast (12 quarters) using sigmoid growth
    def sigmoid_rev(q, scale, midpoint):
        return scale / (1 + math.exp(-(q - midpoint) / 2.5))

    quarters   = [f"Q{(i%4)+1}'{(2025 + i//4) % 100:02d}" for i in range(12)]
    na_rev     = [round(sigmoid_rev(i, 216, 6) + rng.gauss(0, 4), 1) for i in range(12)]
    apac_rev   = [round(sigmoid_rev(i, 252, 5) + rng.gauss(0, 5), 1) for i in range(12)]
    eu_rev     = [round(sigmoid_rev(i, 140, 7) + rng.gauss(0, 3), 1) for i in range(12)]

    # SVG stacked area chart for revenue
    chart_w, chart_h = 720, 220
    def cx(i): return int(60 + i * (chart_w - 80) / 11)
    def cy(v, mx=320): return int(chart_h - 30 - (v / mx) * (chart_h - 50))

    na_pts   = " ".join(f"{cx(i)},{cy(na_rev[i])}"   for i in range(12))
    apac_pts = " ".join(f"{cx(i)},{cy(apac_rev[i])}" for i in range(12))
    eu_pts   = " ".join(f"{cx(i)},{cy(eu_rev[i])}"   for i in range(12))

    grid_lines = "".join(
        f'<line x1="60" y1="{cy(v)}" x2="{chart_w-20}" y2="{cy(v)}" stroke="#1e293b" stroke-width="1" stroke-dasharray="4,4"/>'
        for v in [50, 100, 150, 200, 250, 300]
    )
    y_labels = "".join(
        f'<text x="4" y="{cy(v)+4}" fill="#64748b" font-size="10">${v}M</text>'
        for v in [50, 100, 150, 200, 250, 300]
    )
    x_labels = "".join(
        f'<text x="{cx(i)}" y="{chart_h-12}" fill="#64748b" font-size="9" text-anchor="middle">{quarters[i]}</text>'
        for i in range(0, 12, 2)
    )

    # TAM/SAM/SOM horizontal bar chart
    bar_w, bar_h = 500, 220
    max_bar = max(tam)
    region_bars = ""
    for idx, (r, t, sa, so) in enumerate(zip(regions, tam, sam, som)):
        by = 20 + idx * 38
        for val, color, label in [(t, "#1e3a5f", ""), (sa, "#1d4ed8", ""), (so, "#C74634", "")]:
            bw = int((val / max_bar) * (bar_w - 120))
            region_bars += f'<rect x="100" y="{by}" width="{bw}" height="14" fill="{color}" rx="2" opacity="0.9"/>'
        region_bars += f'<text x="96" y="{by+11}" fill="#94a3b8" font-size="11" text-anchor="end">{r}</text>'
        region_bars += f'<text x="{100 + int((t/max_bar)*(bar_w-120))+6}" y="{by+11}" fill="#64748b" font-size="10">${t}M</text>'

    # Competitive radar data (5 axes, 0-100)
    competitors = {
        "OCI RobotCloud": [88, 72, 91, 65, 80],
        "AWS RoboMaker":  [75, 85, 60, 78, 55],
        "Azure Robot":    [70, 80, 65, 82, 60],
    }
    axes_labels = ["Infrastructure", "SDK Maturity", "Fine-Tuning", "Enterprise", "Price"]
    cx_r, cy_r, r_max = 160, 130, 100
    n_axes = 5

    def radar_pt(val, axis_idx, cx, cy, rmax):
        angle = math.radians(axis_idx * 360 / n_axes - 90)
        d = (val / 100) * rmax
        return (cx + d * math.cos(angle), cy + d * math.sin(angle))

    # Draw radar spokes and rings
    radar_svg = ""
    for ring in [25, 50, 75, 100]:
        ring_pts = " ".join(
            f"{radar_pt(ring, i, cx_r, cy_r, r_max)[0]:.1f},{radar_pt(ring, i, cx_r, cy_r, r_max)[1]:.1f}"
            for i in range(n_axes + 1)
        )
        radar_svg += f'<polygon points="{ring_pts}" fill="none" stroke="#334155" stroke-width="0.8"/>'
    for i in range(n_axes):
        x2, y2 = radar_pt(100, i, cx_r, cy_r, r_max)
        radar_svg += f'<line x1="{cx_r}" y1="{cy_r}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#475569" stroke-width="1"/>'
        lx, ly = radar_pt(115, i, cx_r, cy_r, r_max)
        radar_svg += f'<text x="{lx:.1f}" y="{ly:.1f}" fill="#94a3b8" font-size="10" text-anchor="middle">{axes_labels[i]}</text>'

    colors_radar = ["#C74634", "#38bdf8", "#a78bfa"]
    for (name, vals), color in zip(competitors.items(), colors_radar):
        pts = " ".join(
            f"{radar_pt(v, i, cx_r, cy_r, r_max)[0]:.1f},{radar_pt(v, i, cx_r, cy_r, r_max)[1]:.1f}"
            for i, v in enumerate(vals)
        )
        radar_svg += f'<polygon points="{pts}" fill="{color}" fill-opacity="0.15" stroke="{color}" stroke-width="1.8"/>'

    # Legend for radar
    for li, (name, color) in enumerate(zip(competitors.keys(), colors_radar)):
        radar_svg += f'<rect x="330" y="{80 + li*22}" width="12" height="12" fill="{color}" rx="2"/>'
        radar_svg += f'<text x="348" y="{91 + li*22}" fill="#e2e8f0" font-size="11">{name}</text>'

    # KPI tiles
    total_pipeline = sum(som)
    win_rate = round(rng.uniform(28, 35), 1)
    avg_deal  = round(rng.uniform(0.8, 1.4), 2)
    time_close = round(rng.uniform(42, 58), 0)

    return f"""<!DOCTYPE html>
<html><head><title>Market Expansion Planner — Port 8751</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui,sans-serif}}
h1{{color:#C74634;margin:0;padding:20px 24px 4px;font-size:1.6rem}}
h2{{color:#38bdf8;font-size:1.05rem;margin:0 0 12px}}
.card{{background:#1e293b;padding:20px;margin:12px;border-radius:10px;display:inline-block;vertical-align:top}}
.badge{{display:inline-block;padding:3px 10px;border-radius:12px;font-size:12px;font-weight:600;margin:2px}}
.stat{{font-size:2rem;font-weight:700;color:#C74634}}.sublabel{{color:#64748b;font-size:0.8rem}}
table{{border-collapse:collapse}}th{{color:#94a3b8;padding:8px 14px;text-align:left;border-bottom:2px solid #334155}}
td{{padding:8px 14px;border-bottom:1px solid #334155}}
</style></head>
<body>
<h1>Market Expansion Planner</h1>
<p style="color:#64748b;margin:0 0 4px 24px">OCI Robot Cloud — Global GTM opportunity model &bull; Port {PORT}</p>

<div style="padding:4px 12px">
  <div class="card" style="width:140px;text-align:center">
    <div class="sublabel">SOM Total</div><div class="stat">${total_pipeline}M</div>
  </div>
  <div class="card" style="width:140px;text-align:center">
    <div class="sublabel">Win Rate</div><div class="stat">{win_rate}%</div>
  </div>
  <div class="card" style="width:150px;text-align:center">
    <div class="sublabel">Avg Deal (M)</div><div class="stat">${avg_deal}M</div>
  </div>
  <div class="card" style="width:160px;text-align:center">
    <div class="sublabel">Days to Close</div><div class="stat">{int(time_close)}d</div>
  </div>
</div>

<div class="card" style="margin:12px">
  <h2>Revenue Forecast by Region (Quarterly, $M)</h2>
  <svg width="{chart_w}" height="{chart_h}" style="display:block">
    <line x1="60" y1="10" x2="60" y2="{chart_h-30}" stroke="#475569" stroke-width="1.5"/>
    <line x1="60" y1="{chart_h-30}" x2="{chart_w-20}" y2="{chart_h-30}" stroke="#475569" stroke-width="1.5"/>
    {grid_lines}{y_labels}{x_labels}
    <polyline points="{na_pts}"   fill="none" stroke="#C74634" stroke-width="2.5"/>
    <polyline points="{apac_pts}" fill="none" stroke="#38bdf8" stroke-width="2.5"/>
    <polyline points="{eu_pts}"   fill="none" stroke="#a78bfa" stroke-width="2"/>
    <rect x="520" y="15" width="10" height="10" fill="#C74634" rx="2"/>
    <text x="534" y="24" fill="#e2e8f0" font-size="11">North America</text>
    <rect x="520" y="32" width="10" height="10" fill="#38bdf8" rx="2"/>
    <text x="534" y="41" fill="#e2e8f0" font-size="11">APAC</text>
    <rect x="520" y="49" width="10" height="10" fill="#a78bfa" rx="2"/>
    <text x="534" y="58" fill="#e2e8f0" font-size="11">Europe</text>
  </svg>
</div>

<div class="card">
  <h2>TAM / SAM / SOM by Region ($M)</h2>
  <svg width="{bar_w}" height="{bar_h}" style="display:block">
    {region_bars}
    <rect x="100" y="{bar_h-28}" width="14" height="10" fill="#1e3a5f" rx="2"/>
    <text x="118" y="{bar_h-20}" fill="#94a3b8" font-size="10">TAM</text>
    <rect x="150" y="{bar_h-28}" width="14" height="10" fill="#1d4ed8" rx="2"/>
    <text x="168" y="{bar_h-20}" fill="#94a3b8" font-size="10">SAM</text>
    <rect x="200" y="{bar_h-28}" width="14" height="10" fill="#C74634" rx="2"/>
    <text x="218" y="{bar_h-20}" fill="#94a3b8" font-size="10">SOM</text>
  </svg>
</div>

<div class="card">
  <h2>Competitive Positioning Radar</h2>
  <svg width="500" height="280">{radar_svg}</svg>
</div>

<div class="card" style="min-width:520px">
  <h2>Expansion Priority Scorecard</h2>
  <table>
    <thead><tr><th>Region</th><th>TAM ($M)</th><th>SOM ($M)</th><th>Priority</th><th>Status</th></tr></thead>
    <tbody>
      <tr><td>APAC</td><td>5,600</td><td>252</td><td style="color:#34d399">★★★ High</td><td><span class="badge" style="background:#064e3b;color:#34d399">Active</span></td></tr>
      <tr><td>North America</td><td>4,800</td><td>216</td><td style="color:#34d399">★★★ High</td><td><span class="badge" style="background:#064e3b;color:#34d399">Active</span></td></tr>
      <tr><td>Europe</td><td>3,100</td><td>140</td><td style="color:#fbbf24">★★ Medium</td><td><span class="badge" style="background:#451a03;color:#fb923c">Pilot</span></td></tr>
      <tr><td>LatAm</td><td>1,200</td><td>54</td><td style="color:#fbbf24">★★ Medium</td><td><span class="badge" style="background:#1c1917;color:#78716c">Planning</span></td></tr>
      <tr><td>MEA</td><td>900</td><td>41</td><td style="color:#94a3b8">★ Low</td><td><span class="badge" style="background:#1c1917;color:#78716c">Research</span></td></tr>
    </tbody>
  </table>
</div>

<div style="padding:12px 24px;color:#334155;font-size:11px">
  Market Expansion Planner v1.0 &bull; OCI Robot Cloud GTM &bull; Data: 2026-03-30 &bull; Port {PORT}
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Market Expansion Planner")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return build_html()

    @app.get("/health")
    def health():
        return {"status": "ok", "port": PORT, "service": "market_expansion_planner"}

    @app.get("/metrics")
    def metrics():
        return {
            "total_som_usd_m": 703,
            "regions": 5,
            "active_regions": 2,
            "win_rate_pct": round(random.uniform(28, 35), 1),
            "avg_deal_size_usd_m": round(random.uniform(0.8, 1.4), 2),
            "days_to_close": round(random.uniform(42, 58), 0),
        }

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
