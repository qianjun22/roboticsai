"""Partner Cohort Analyzer — FastAPI port 8639"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8639

def build_html():
    random.seed(99)

    # ---- SVG 1: Cohort KPI Comparison Grouped Bar Chart ----
    kpi_labels = ["Deploy\nTime", "API\nAdoption", "Support\nTickets", "Ramp\nRate", "Retention", "NPS", "Expansion", "TTV"]
    kpi_short  = ["Deploy", "Adoption", "Support", "Ramp", "Retain", "NPS", "Expand", "TTV"]
    # cohort-2 is consistently higher (better) for most KPIs
    c1_vals = [72, 61, 55, 58, 74, 62, 48, 66]
    c2_vals = [84, 79, 68, 82, 81, 77, 71, 78]
    c1_color = "#38bdf8"
    c2_color = "#a3e635"
    chart_h = 200
    max_val = 100
    svg1_bars = ""
    bar_w = 26
    group_gap = 72
    for i, (v1, v2, lbl) in enumerate(zip(c1_vals, c2_vals, kpi_short)):
        gx = 55 + i * group_gap
        h1 = v1 / max_val * chart_h
        h2 = v2 / max_val * chart_h
        by1 = 230 - h1
        by2 = 230 - h2
        svg1_bars += f'<rect x="{gx}" y="{by1:.1f}" width="{bar_w}" height="{h1:.1f}" fill="{c1_color}" opacity="0.85" rx="3"/>'
        svg1_bars += f'<rect x="{gx+bar_w+3}" y="{by2:.1f}" width="{bar_w}" height="{h2:.1f}" fill="{c2_color}" opacity="0.85" rx="3"/>'
        svg1_bars += f'<text x="{gx+28}" y="246" fill="#94a3b8" font-size="10" font-family="monospace" text-anchor="middle">{lbl}</text>'
        svg1_bars += f'<text x="{gx+13}" y="{by1-4:.0f}" fill="{c1_color}" font-size="9" font-family="monospace" text-anchor="middle">{v1}</text>'
        svg1_bars += f'<text x="{gx+bar_w+16}" y="{by2-4:.0f}" fill="{c2_color}" font-size="9" font-family="monospace" text-anchor="middle">{v2}</text>'

    svg1 = f'''
    <svg viewBox="0 0 720 270" xmlns="http://www.w3.org/2000/svg" style="width:100%;background:#1e293b;border-radius:8px">
      <text x="360" y="22" fill="#C74634" font-size="14" font-family="monospace" text-anchor="middle" font-weight="bold">Cohort KPI Comparison — 8 Dimensions</text>
      <!-- Grid -->
      <line x1="50" y1="230" x2="700" y2="230" stroke="#334155" stroke-width="1"/>
      <line x1="50" y1="190" x2="700" y2="190" stroke="#334155" stroke-width="0.5" stroke-dasharray="4,3"/>
      <line x1="50" y1="150" x2="700" y2="150" stroke="#334155" stroke-width="0.5" stroke-dasharray="4,3"/>
      <line x1="50" y1="110" x2="700" y2="110" stroke="#334155" stroke-width="0.5" stroke-dasharray="4,3"/>
      <line x1="50" y1="70"  x2="700" y2="70"  stroke="#334155" stroke-width="0.5" stroke-dasharray="4,3"/>
      <text x="44" y="234" fill="#64748b" font-size="9" font-family="monospace" text-anchor="end">0</text>
      <text x="44" y="194" fill="#64748b" font-size="9" font-family="monospace" text-anchor="end">20</text>
      <text x="44" y="154" fill="#64748b" font-size="9" font-family="monospace" text-anchor="end">50</text>
      <text x="44" y="114" fill="#64748b" font-size="9" font-family="monospace" text-anchor="end">75</text>
      <text x="44" y="74"  fill="#64748b" font-size="9" font-family="monospace" text-anchor="end">100</text>
      {svg1_bars}
      <!-- Legend -->
      <rect x="380" y="258" width="14" height="8" fill="{c1_color}" rx="2"/>
      <text x="398" y="266" fill="#94a3b8" font-size="11" font-family="monospace">Cohort-1  (PI / Apt / 1X)</text>
      <rect x="570" y="258" width="14" height="8" fill="{c2_color}" rx="2"/>
      <text x="588" y="266" fill="#94a3b8" font-size="11" font-family="monospace">Cohort-2  (Machina / Wandelbots)</text>
    </svg>
    '''

    # ---- SVG 2: LTV Projection (2 lines over 18 months) ----
    months = list(range(0, 19))
    # Cohort-1 plateaus at $24k by month 18
    def ltv1(m):
        return 24000 * (1 - math.exp(-0.22 * m))
    # Cohort-2 ramps faster, projected $31k by month 18
    def ltv2(m):
        return 31000 * (1 - math.exp(-0.30 * m)) + random.gauss(0, 200) * (m / 18)
    random.seed(5)
    c1_ltv = [ltv1(m) for m in months]
    c2_ltv = [ltv2(m) for m in months]

    svg2_w = 640
    svg2_h = 180
    x0, y0 = 60, 10

    def ltv_pt(m, v, max_v=35000):
        px = x0 + m * (svg2_w / 18)
        py = y0 + svg2_h - v / max_v * svg2_h
        return f"{px:.1f},{py:.1f}"

    pts1 = " ".join(ltv_pt(m, v) for m, v in zip(months, c1_ltv))
    pts2 = " ".join(ltv_pt(m, v) for m, v in zip(months, c2_ltv))

    # Area fill paths
    area1_start = ltv_pt(0, 0)
    area1_end   = ltv_pt(18, 0)
    area2_start = ltv_pt(0, 0)
    area2_end   = ltv_pt(18, 0)

    svg2 = f'''
    <svg viewBox="0 0 720 230" xmlns="http://www.w3.org/2000/svg" style="width:100%;background:#1e293b;border-radius:8px">
      <text x="360" y="22" fill="#C74634" font-size="14" font-family="monospace" text-anchor="middle" font-weight="bold">Partner LTV Projection — 18-Month Horizon</text>
      <!-- Grid -->
      <line x1="60" y1="190" x2="700" y2="190" stroke="#334155" stroke-width="1"/>
      <line x1="60" y1="10"  x2="60"  y2="190" stroke="#334155" stroke-width="1"/>
      <line x1="60" y1="145" x2="700" y2="145" stroke="#334155" stroke-width="0.5" stroke-dasharray="4,3"/>
      <line x1="60" y1="100" x2="700" y2="100" stroke="#334155" stroke-width="0.5" stroke-dasharray="4,3"/>
      <line x1="60" y1="55"  x2="700" y2="55"  stroke="#334155" stroke-width="0.5" stroke-dasharray="4,3"/>
      <!-- Y labels -->
      <text x="54" y="194" fill="#64748b" font-size="10" font-family="monospace" text-anchor="end">$0</text>
      <text x="54" y="149" fill="#64748b" font-size="10" font-family="monospace" text-anchor="end">$10k</text>
      <text x="54" y="104" fill="#64748b" font-size="10" font-family="monospace" text-anchor="end">$20k</text>
      <text x="54" y="59"  fill="#64748b" font-size="10" font-family="monospace" text-anchor="end">$30k</text>
      <!-- X labels -->
      <text x="60"  y="205" fill="#64748b" font-size="10" font-family="monospace" text-anchor="middle">0</text>
      <text x="240" y="205" fill="#64748b" font-size="10" font-family="monospace" text-anchor="middle">6mo</text>
      <text x="418" y="205" fill="#64748b" font-size="10" font-family="monospace" text-anchor="middle">12mo</text>
      <text x="700" y="205" fill="#64748b" font-size="10" font-family="monospace" text-anchor="middle">18mo</text>
      <!-- Plateau annotation C1 -->
      <line x1="60" y1="{10+180-24000/35000*180:.1f}" x2="700" y2="{10+180-24000/35000*180:.1f}" stroke="#38bdf8" stroke-width="0.8" stroke-dasharray="6,4" opacity="0.5"/>
      <text x="704" y="{10+180-24000/35000*180+4:.1f}" fill="#38bdf8" font-size="10" font-family="monospace">$24k</text>
      <!-- Projection annotation C2 -->
      <line x1="60" y1="{10+180-31000/35000*180:.1f}" x2="700" y2="{10+180-31000/35000*180:.1f}" stroke="#a3e635" stroke-width="0.8" stroke-dasharray="6,4" opacity="0.5"/>
      <text x="704" y="{10+180-31000/35000*180+4:.1f}" fill="#a3e635" font-size="10" font-family="monospace">$31k*</text>
      <!-- Lines -->
      <polyline points="{pts1}" fill="none" stroke="#38bdf8" stroke-width="2.5" stroke-linejoin="round"/>
      <polyline points="{pts2}" fill="none" stroke="#a3e635" stroke-width="2.5" stroke-linejoin="round" stroke-dasharray="6,3"/>
      <!-- Legend -->
      <line x1="200" y1="220" x2="220" y2="220" stroke="#38bdf8" stroke-width="2.5"/>
      <text x="224" y="224" fill="#94a3b8" font-size="11" font-family="monospace">Cohort-1  ($24k plateau)</text>
      <line x1="440" y1="220" x2="460" y2="220" stroke="#a3e635" stroke-width="2.5" stroke-dasharray="6,3"/>
      <text x="464" y="224" fill="#94a3b8" font-size="11" font-family="monospace">Cohort-2  ($31k projected*)</text>
    </svg>
    '''

    # ---- SVG 3: Cohort Health Radar (5 axes) ----
    axes = ["Self-serve\nRate", "API\nAdoption", "Support\nLoad", "Expansion", "Retention"]
    axes_short = ["SR", "Adoption", "Support", "Expansion", "Retention"]
    c1_radar = [0.72, 0.65, 0.60, 0.52, 0.78]
    c2_radar = [0.85, 0.82, 0.73, 0.74, 0.84]
    cx, cy, r = 200, 130, 100
    n = 5

    def radar_pt(val, axis_i, radius=r):
        angle = math.pi / 2 + axis_i * 2 * math.pi / n
        px = cx + val * radius * math.cos(angle)
        py = cy - val * radius * math.sin(angle)
        return px, py

    # Axis lines + labels
    radar_axes_svg = ""
    for i, lbl in enumerate(axes_short):
        ex, ey = radar_pt(1.0, i)
        radar_axes_svg += f'<line x1="{cx}" y1="{cy}" x2="{ex:.1f}" y2="{ey:.1f}" stroke="#334155" stroke-width="1"/>'
        lx, ly = radar_pt(1.18, i)
        radar_axes_svg += f'<text x="{lx:.1f}" y="{ly:.1f}" fill="#64748b" font-size="10" font-family="monospace" text-anchor="middle">{lbl}</text>'

    # Concentric rings
    for ring in [0.25, 0.5, 0.75, 1.0]:
        ring_pts = [f"{radar_pt(ring, i)[0]:.1f},{radar_pt(ring, i)[1]:.1f}" for i in range(n)]
        ring_pts_closed = ring_pts + [ring_pts[0]]
        radar_axes_svg += f'<polygon points="{" ".join(ring_pts_closed)}" fill="none" stroke="#334155" stroke-width="0.8"/>'

    def polygon_path(vals):
        pts = [f"{radar_pt(v, i)[0]:.1f},{radar_pt(v, i)[1]:.1f}" for i, v in enumerate(vals)]
        pts.append(pts[0])
        return " ".join(pts)

    radar_c1 = polygon_path(c1_radar)
    radar_c2 = polygon_path(c2_radar)

    # Second radar: cohort-2 centered at 520,130
    cx2 = 520
    def radar_pt2(val, axis_i, radius=r):
        angle = math.pi / 2 + axis_i * 2 * math.pi / n
        px = cx2 + val * radius * math.cos(angle)
        py = cy - val * radius * math.sin(angle)
        return px, py

    radar_axes2_svg = ""
    for i, lbl in enumerate(axes_short):
        ex, ey = radar_pt2(1.0, i)
        radar_axes2_svg += f'<line x1="{cx2}" y1="{cy}" x2="{ex:.1f}" y2="{ey:.1f}" stroke="#334155" stroke-width="1"/>'
        lx, ly = radar_pt2(1.18, i)
        radar_axes2_svg += f'<text x="{lx:.1f}" y="{ly:.1f}" fill="#64748b" font-size="10" font-family="monospace" text-anchor="middle">{lbl}</text>'
    for ring in [0.25, 0.5, 0.75, 1.0]:
        ring_pts = [f"{radar_pt2(ring, i)[0]:.1f},{radar_pt2(ring, i)[1]:.1f}" for i in range(n)]
        ring_pts_closed = ring_pts + [ring_pts[0]]
        radar_axes2_svg += f'<polygon points="{" ".join(ring_pts_closed)}" fill="none" stroke="#334155" stroke-width="0.8"/>'

    def polygon_path2(vals):
        pts = [f"{radar_pt2(v, i)[0]:.1f},{radar_pt2(v, i)[1]:.1f}" for i, v in enumerate(vals)]
        pts.append(pts[0])
        return " ".join(pts)

    radar2_c2 = polygon_path2(c2_radar)
    radar2_c1 = polygon_path2(c1_radar)

    svg3 = f'''
    <svg viewBox="0 0 720 270" xmlns="http://www.w3.org/2000/svg" style="width:100%;background:#1e293b;border-radius:8px">
      <text x="360" y="22" fill="#C74634" font-size="14" font-family="monospace" text-anchor="middle" font-weight="bold">Cohort Health Radar — 5 Dimensions</text>
      <!-- Titles -->
      <text x="200" y="45" fill="#38bdf8" font-size="12" font-family="monospace" text-anchor="middle">Cohort-1  (PI / Apt / 1X)</text>
      <text x="520" y="45" fill="#a3e635" font-size="12" font-family="monospace" text-anchor="middle">Cohort-2  (Machina / Wandelbots)</text>
      <!-- Cohort-1 radar -->
      {radar_axes_svg}
      <polygon points="{radar_c1}" fill="#38bdf8" fill-opacity="0.15" stroke="#38bdf8" stroke-width="2"/>
      <!-- Cohort-2 overlay on C1 radar (dimmed) -->
      <polygon points="{radar_c2}" fill="#a3e635" fill-opacity="0.08" stroke="#a3e635" stroke-width="1.5" stroke-dasharray="5,3" opacity="0.5"/>
      <!-- Cohort-2 radar -->
      {radar_axes2_svg}
      <polygon points="{radar2_c1}" fill="#38bdf8" fill-opacity="0.08" stroke="#38bdf8" stroke-width="1.5" stroke-dasharray="5,3" opacity="0.5"/>
      <polygon points="{radar2_c2}" fill="#a3e635" fill-opacity="0.18" stroke="#a3e635" stroke-width="2"/>
      <!-- Legend -->
      <rect x="240" y="256" width="12" height="8" fill="#38bdf8" opacity="0.8" rx="2"/>
      <text x="256" y="264" fill="#94a3b8" font-size="11" font-family="monospace">Cohort-1</text>
      <rect x="370" y="256" width="12" height="8" fill="#a3e635" opacity="0.8" rx="2"/>
      <text x="386" y="264" fill="#94a3b8" font-size="11" font-family="monospace">Cohort-2</text>
      <text x="490" y="264" fill="#64748b" font-size="10" font-family="monospace">(dashed = comparison overlay)</text>
    </svg>
    '''

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Partner Cohort Analyzer — Port {PORT}</title>
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
    .card .val.green {{ color: #a3e635; }}
    .card .lbl {{ color: #64748b; font-size: 0.78rem; margin-top: 5px; }}
    .card .note {{ color: #94a3b8; font-size: 0.75rem; margin-top: 4px; }}
    .chart-wrap {{ background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 16px; margin-bottom: 22px; }}
    .cohort-row {{ display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-bottom: 22px; }}
    .cohort-card {{
      background: #1e293b; border: 1px solid #334155; border-radius: 8px;
      padding: 14px 16px;
    }}
    .cohort-card h3 {{ color: #38bdf8; font-size: 0.95rem; margin-bottom: 8px; }}
    .cohort-card.c2 h3 {{ color: #a3e635; }}
    .cohort-card p {{ color: #94a3b8; font-size: 0.82rem; line-height: 1.55; }}
    footer {{ color: #334155; font-size: 0.75rem; margin-top: 36px; text-align: center; }}
  </style>
</head>
<body>
  <h1>Partner Cohort Analyzer</h1>
  <div class="subtitle">Design Partner Cohort Performance  |  Port {PORT}  |  OCI Robot Cloud</div>

  <div class="metrics">
    <div class="card"><div class="val">$24k</div><div class="lbl">Cohort-1 LTV</div><div class="note">18-month plateau</div></div>
    <div class="card"><div class="val green">$31k</div><div class="lbl">Cohort-2 LTV</div><div class="note">18-month projected</div></div>
    <div class="card"><div class="val">-41%</div><div class="lbl">Time-to-Value</div><div class="note">self-serve onboarding</div></div>
    <div class="card"><div class="val green">+29%</div><div class="lbl">C2 Ramp Rate</div><div class="note">vs cohort-1 baseline</div></div>
  </div>

  <div class="cohort-row">
    <div class="cohort-card">
      <h3>Cohort-1 — Pioneer / Aptiv / 1X</h3>
      <p>Early adopters. Longer integration cycles. Deep customization requirements. LTV plateaus at $24k/18mo driven by stable enterprise contracts. Support load moderate; expansion limited by OEM procurement cycles.</p>
    </div>
    <div class="cohort-card c2">
      <h3>Cohort-2 — Machina Labs / Wandelbots</h3>
      <p>Faster ramp via self-serve SDK. Higher API adoption (82%) and expansion rate (74%). Projected LTV $31k/18mo — 29% above cohort-1. Self-serve onboarding cut time-to-value by 41%. Strong retention signal at 84%.</p>
    </div>
  </div>

  <h2>KPI Comparison — Cohort-1 vs Cohort-2 (8 Dimensions)</h2>
  <div class="chart-wrap">{svg1}</div>

  <h2>Partner LTV Projection — 18-Month Horizon</h2>
  <div class="chart-wrap">{svg2}</div>

  <h2>Cohort Health Radar</h2>
  <div class="chart-wrap">{svg3}</div>

  <footer>OCI Robot Cloud · Partner Cohort Analyzer · Port {PORT} · cycle-145A</footer>
</body>
</html>"""


if USE_FASTAPI:
    app = FastAPI(title="Partner Cohort Analyzer")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return build_html()

    @app.get("/health")
    def health():
        return {"status": "ok", "port": PORT}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            body = b'{"status":"ok","port":8639}'
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
