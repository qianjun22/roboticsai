"""Customer Expansion Revenue Tracker — FastAPI port 8811"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8811

def build_html():
    random.seed(99)

    # Monthly ARR expansion data (12 months)
    months = ["Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec","Jan","Feb","Mar"]
    base_arr = 420000
    arr_vals = []
    for i, m in enumerate(months):
        growth = base_arr * (1 + 0.08 * i + random.gauss(0, 0.02))
        arr_vals.append(max(growth, base_arr))
    total_arr = arr_vals[-1]

    # NRR (Net Revenue Retention) monthly
    nrr_vals = [random.uniform(108, 128) for _ in months]

    # Customer segments
    segments = ["Tier-1 Enterprise", "Mid-Market", "Growth", "Startup"]
    seg_arr = [random.uniform(280000, 480000) for _ in segments]
    seg_total = sum(seg_arr)
    seg_pcts = [v / seg_total for v in seg_arr]

    # SVG dimensions
    svg_w, svg_h = 560, 200
    bar_area_h = svg_h - 50

    max_arr = max(arr_vals)
    def arr_y(v): return svg_h - 30 - (v / max_arr) * (bar_area_h - 10)

    # Bar chart for ARR
    bar_w = (svg_w - 60) / len(months) - 4
    bars_svg = ""
    for i, (m, v) in enumerate(zip(months, arr_vals)):
        bx = 44 + i * ((svg_w - 60) / len(months))
        by = arr_y(v)
        bh = svg_h - 30 - by
        ratio = v / max_arr
        r = int(50 + ratio * 180)
        g = int(100 + ratio * 100)
        bars_svg += f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bar_w:.1f}" height="{bh:.1f}" rx="3" fill="rgb({r},{g},200)" opacity="0.85"/>'
        bars_svg += f'<text x="{bx+bar_w/2:.1f}" y="{svg_h-14}" text-anchor="middle" fill="#94a3b8" font-size="9">{m}</text>'
        if i % 3 == 0:
            bars_svg += f'<text x="{bx+bar_w/2:.1f}" y="{by-4:.1f}" text-anchor="middle" fill="#e2e8f0" font-size="8">${v/1000:.0f}K</text>'

    # NRR line overlay
    nrr_min, nrr_max = 100, 140
    nrr_pts = []
    for i, v in enumerate(nrr_vals):
        x = 44 + i * ((svg_w - 60) / len(months)) + bar_w / 2
        y = svg_h - 30 - (v - nrr_min) / (nrr_max - nrr_min) * (bar_area_h - 10)
        nrr_pts.append(f"{x:.1f},{y:.1f}")
    nrr_line = " ".join(nrr_pts)

    # Donut chart for segments
    cx, cy, r_out, r_in = 130, 130, 100, 55
    colors = ["#22d3ee", "#818cf8", "#34d399", "#fb923c"]
    donut_svg = ""
    start_angle = -math.pi / 2
    for i, (seg, pct) in enumerate(zip(segments, seg_pcts)):
        sweep = pct * 2 * math.pi
        end_angle = start_angle + sweep
        x1o = cx + r_out * math.cos(start_angle)
        y1o = cy + r_out * math.sin(start_angle)
        x2o = cx + r_out * math.cos(end_angle)
        y2o = cy + r_out * math.sin(end_angle)
        x1i = cx + r_in * math.cos(end_angle)
        y1i = cy + r_in * math.sin(end_angle)
        x2i = cx + r_in * math.cos(start_angle)
        y2i = cy + r_in * math.sin(start_angle)
        large = 1 if sweep > math.pi else 0
        d = (f"M {x1o:.2f} {y1o:.2f} "
             f"A {r_out} {r_out} 0 {large} 1 {x2o:.2f} {y2o:.2f} "
             f"L {x1i:.2f} {y1i:.2f} "
             f"A {r_in} {r_in} 0 {large} 0 {x2i:.2f} {y2i:.2f} Z")
        donut_svg += f'<path d="{d}" fill="{colors[i]}" opacity="0.88" stroke="#0f172a" stroke-width="1.5"/>'
        mid_angle = start_angle + sweep / 2
        lx = cx + (r_out + 18) * math.cos(mid_angle)
        ly = cy + (r_out + 18) * math.sin(mid_angle)
        donut_svg += f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="middle" fill="{colors[i]}" font-size="10">{pct*100:.1f}%</text>'
        start_angle = end_angle

    # Legend for donut
    legend_svg = ""
    for i, (seg, arr) in enumerate(zip(segments, seg_arr)):
        lx, ly = 270, 50 + i * 36
        legend_svg += f'<rect x="{lx}" y="{ly}" width="14" height="14" rx="3" fill="{colors[i]}"/>'
        legend_svg += f'<text x="{lx+20}" y="{ly+11}" fill="#e2e8f0" font-size="11">{seg}</text>'
        legend_svg += f'<text x="{lx+20}" y="{ly+23}" fill="#64748b" font-size="10">${arr/1000:.0f}K ARR</text>'

    # Expansion motion waterfall: new, expansion, contraction, churn
    motion_labels = ["New Biz", "Expansion", "Contraction", "Churn", "Net New"]
    motion_vals = [random.uniform(40000, 90000), random.uniform(30000, 70000),
                   -random.uniform(5000, 15000), -random.uniform(8000, 20000), 0]
    motion_vals[4] = sum(motion_vals[:4])
    motion_colors = ["#34d399","#22d3ee","#f87171","#fb923c","#818cf8"]
    wf_h = 160
    wf_max = max(abs(v) for v in motion_vals) * 1.2
    wf_bw = 62
    wf_svg = ""
    baseline = wf_h - 20
    for i, (lbl, v) in enumerate(zip(motion_labels, motion_vals)):
        bx = 20 + i * 80
        bh = abs(v) / wf_max * (wf_h - 40)
        by = baseline - bh if v >= 0 else baseline
        wf_svg += f'<rect x="{bx}" y="{by:.1f}" width="{wf_bw}" height="{bh:.1f}" rx="3" fill="{motion_colors[i]}" opacity="0.85"/>'
        wf_svg += f'<text x="{bx+wf_bw//2}" y="{by-4:.1f}" text-anchor="middle" fill="#e2e8f0" font-size="9">${abs(v)/1000:.0f}K</text>'
        wf_svg += f'<text x="{bx+wf_bw//2}" y="{wf_h-4}" text-anchor="middle" fill="#94a3b8" font-size="9">{lbl}</text>'

    avg_nrr = sum(nrr_vals) / len(nrr_vals)

    return f"""<!DOCTYPE html><html><head><title>Customer Expansion Revenue Tracker</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui,sans-serif}}
h1{{color:#C74634;padding:20px 24px 0;margin:0;font-size:1.6rem}}
.subtitle{{color:#64748b;padding:2px 24px 16px;font-size:0.9rem}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;padding:0 16px 16px}}
.card{{background:#1e293b;padding:20px;border-radius:10px;border:1px solid #334155}}
.card h2{{color:#38bdf8;margin:0 0 12px;font-size:1rem;text-transform:uppercase;letter-spacing:.05em}}
.stat-row{{display:flex;gap:16px;padding:0 16px 16px}}
.stat{{background:#1e293b;border-radius:8px;padding:14px 20px;flex:1;border:1px solid #334155}}
.stat .val{{font-size:1.9rem;font-weight:700;color:#22d3ee}}
.stat .lbl{{font-size:0.78rem;color:#64748b;margin-top:2px}}
.full{{grid-column:1/-1}}
</style></head>
<body>
<h1>Customer Expansion Revenue Tracker</h1>
<div class="subtitle">OCI Robot Cloud — ARR expansion, net revenue retention, and customer segment analytics</div>

<div class="stat-row">
  <div class="stat"><div class="val">${total_arr/1e6:.2f}M</div><div class="lbl">Current ARR</div></div>
  <div class="stat"><div class="val">{avg_nrr:.1f}%</div><div class="lbl">Avg NRR (12mo)</div></div>
  <div class="stat"><div class="val">{len(segments)}</div><div class="lbl">Customer segments</div></div>
  <div class="stat"><div class="val">${motion_vals[4]/1000:.0f}K</div><div class="lbl">Net new ARR this month</div></div>
</div>

<div class="grid">
  <div class="card full">
    <h2>Monthly ARR Growth + NRR Trend</h2>
    <svg width="100%" viewBox="0 0 {svg_w} {svg_h}" xmlns="http://www.w3.org/2000/svg">
      {bars_svg}
      <polyline points="{nrr_line}" fill="none" stroke="#fbbf24" stroke-width="2" stroke-dasharray="5,3"/>
      <line x1="40" y1="10" x2="40" y2="{svg_h-30}" stroke="#334155" stroke-width="1"/>
      <line x1="40" y1="{svg_h-30}" x2="{svg_w-10}" y2="{svg_h-30}" stroke="#334155" stroke-width="1"/>
      <!-- Legend -->
      <rect x="60" y="12" width="12" height="12" rx="2" fill="rgb(140,180,200)" opacity="0.85"/>
      <text x="76" y="22" fill="#e2e8f0" font-size="11">ARR</text>
      <line x1="115" y1="18" x2="140" y2="18" stroke="#fbbf24" stroke-width="2" stroke-dasharray="5,3"/>
      <text x="145" y="22" fill="#e2e8f0" font-size="11">NRR %</text>
    </svg>
  </div>

  <div class="card">
    <h2>ARR by Customer Segment</h2>
    <svg width="100%" viewBox="0 0 480 270" xmlns="http://www.w3.org/2000/svg">
      {donut_svg}
      {legend_svg}
      <text x="{cx}" y="{cy+6}" text-anchor="middle" fill="#e2e8f0" font-size="13" font-weight="bold">${seg_total/1e6:.2f}M</text>
      <text x="{cx}" y="{cy+20}" text-anchor="middle" fill="#64748b" font-size="10">Total ARR</text>
    </svg>
  </div>

  <div class="card">
    <h2>Revenue Expansion Motion (This Month)</h2>
    <svg width="100%" viewBox="0 0 430 {wf_h+10}" xmlns="http://www.w3.org/2000/svg">
      {wf_svg}
      <line x1="10" y1="{wf_h-20}" x2="420" y2="{wf_h-20}" stroke="#475569" stroke-width="1"/>
    </svg>
  </div>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Customer Expansion Revenue Tracker")
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
