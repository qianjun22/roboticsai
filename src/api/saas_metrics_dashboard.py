"""SaaS Metrics Dashboard — FastAPI port 8813"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8813

def build_html():
    random.seed(77)

    # --- MRR growth over 12 months (compound growth with noise) ---
    base_mrr = 18400.0
    mrr_series = []
    for m in range(12):
        growth = 1.0 + 0.068 + random.uniform(-0.015, 0.025)
        base_mrr *= growth
        mrr_series.append(base_mrr)
    current_mrr = mrr_series[-1]
    mrr_growth_pct = (mrr_series[-1] / mrr_series[0] - 1) * 100

    # --- Churn rate per month (%) ---
    churn_series = [2.1 + 0.8 * math.sin(m * 0.5) + random.uniform(-0.3, 0.3) for m in range(12)]
    avg_churn = sum(churn_series) / len(churn_series)

    # --- CAC and LTV ---
    cac = 1240 + random.uniform(-80, 80)
    ltv = current_mrr / (avg_churn / 100) / 120  # simplified
    ltv_cac = ltv / cac

    # --- Active seats by tier ---
    tiers = ["Starter", "Growth", "Pro", "Enterprise"]
    seats = [random.randint(210, 340), random.randint(140, 220), random.randint(80, 140), random.randint(30, 70)]
    total_seats = sum(seats)
    tier_colors = ["#38bdf8", "#818cf8", "#34d399", "#C74634"]

    # --- MRR line chart ---
    months = ["Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec", "Jan", "Feb", "Mar"]
    chart_w, chart_h = 380, 100
    min_mrr, max_mrr = min(mrr_series), max(mrr_series)
    mrr_pts = []
    for i, v in enumerate(mrr_series):
        x = i * (chart_w / 11)
        y = chart_h - (v - min_mrr) / (max_mrr - min_mrr + 1) * chart_h
        mrr_pts.append((x, max(2, min(chart_h - 2, y))))
    mrr_poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in mrr_pts)
    mrr_fill = mrr_poly + f" {chart_w},{chart_h} 0,{chart_h}"

    # X-axis labels every 2 months
    mrr_xlabels = ""
    for i, label in enumerate(months):
        if i % 2 == 0:
            x = i * (chart_w / 11)
            mrr_xlabels += f'<text x="{x:.1f}" y="115" fill="#64748b" font-size="8" text-anchor="middle">{label}</text>'

    # --- Churn bar chart ---
    churn_svg = ""
    bar_w = chart_w / 12 - 4
    max_churn = max(churn_series)
    for i, (m, ch) in enumerate(zip(months, churn_series)):
        bh = int(ch / max_churn * 70)
        x = i * (chart_w / 12) + 2
        color = "#C74634" if ch > avg_churn * 1.1 else "#38bdf8"
        churn_svg += f'<rect x="{x:.1f}" y="{75 - bh}" width="{bar_w:.1f}" height="{bh}" rx="2" fill="{color}" opacity="0.85"/>'
        if i % 2 == 0:
            churn_svg += f'<text x="{x + bar_w/2:.1f}" y="90" fill="#64748b" font-size="8" text-anchor="middle">{m}</text>'

    # --- Tier donut chart (approximated with arcs) ---
    donut_cx, donut_cy, donut_r, donut_ir = 120, 100, 80, 48
    total = sum(seats)
    donut_slices = ""
    start_angle = -math.pi / 2
    for seat, color in zip(seats, tier_colors):
        sweep = (seat / total) * 2 * math.pi
        end_angle = start_angle + sweep
        x1o = donut_cx + donut_r * math.cos(start_angle)
        y1o = donut_cy + donut_r * math.sin(start_angle)
        x2o = donut_cx + donut_r * math.cos(end_angle)
        y2o = donut_cy + donut_r * math.sin(end_angle)
        x1i = donut_cx + donut_ir * math.cos(start_angle)
        y1i = donut_cy + donut_ir * math.sin(start_angle)
        x2i = donut_cx + donut_ir * math.cos(end_angle)
        y2i = donut_cy + donut_ir * math.sin(end_angle)
        large = 1 if sweep > math.pi else 0
        d = (f"M {x1o:.1f} {y1o:.1f} "
             f"A {donut_r} {donut_r} 0 {large} 1 {x2o:.1f} {y2o:.1f} "
             f"L {x2i:.1f} {y2i:.1f} "
             f"A {donut_ir} {donut_ir} 0 {large} 0 {x1i:.1f} {y1i:.1f} Z")
        donut_slices += f'<path d="{d}" fill="{color}" opacity="0.9" stroke="#0f172a" stroke-width="2"/>'
        start_angle = end_angle

    legend_svg = ""
    for i, (tier, seat, color) in enumerate(zip(tiers, seats, tier_colors)):
        ly = 40 + i * 24
        legend_svg += f'<rect x="255" y="{ly}" width="12" height="12" rx="2" fill="{color}"/>'
        legend_svg += f'<text x="272" y="{ly+10}" fill="#e2e8f0" font-size="11">{tier}: {seat}</text>'

    return f"""<!DOCTYPE html><html><head><title>SaaS Metrics Dashboard</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui,sans-serif}}
h1{{color:#C74634;padding:20px 20px 4px;margin:0;font-size:1.5rem}}
.subtitle{{color:#64748b;padding:0 20px 16px;font-size:0.85rem}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:0}}
.card{{background:#1e293b;padding:20px;margin:10px;border-radius:8px;border:1px solid #334155}}
h2{{color:#38bdf8;margin:0 0 12px;font-size:1rem}}
.kpi-row{{display:flex;gap:12px;margin:0 10px 0}}
.kpi{{background:#1e293b;border:1px solid #334155;border-radius:6px;padding:14px 16px;flex:1;text-align:center}}
.kpi .val{{font-size:1.55rem;font-weight:700;color:#38bdf8}}
.kpi .lbl{{font-size:0.72rem;color:#64748b;margin-top:2px}}
.kpi.warn .val{{color:#fb923c}}
.kpi.good .val{{color:#4ade80}}
</style></head>
<body>
<h1>SaaS Metrics Dashboard</h1>
<div class="subtitle">Port {PORT} &nbsp;|&nbsp; OCI Robot Cloud subscription analytics &nbsp;|&nbsp; Trailing 12 months</div>

<div class="kpi-row">
  <div class="kpi good"><div class="val">${current_mrr:,.0f}</div><div class="lbl">Current MRR</div></div>
  <div class="kpi good"><div class="val">+{mrr_growth_pct:.1f}%</div><div class="lbl">MRR Growth (12mo)</div></div>
  <div class="kpi {"warn" if avg_churn > 2.5 else "good"}"><div class="val">{avg_churn:.2f}%</div><div class="lbl">Avg Monthly Churn</div></div>
  <div class="kpi good"><div class="val">{ltv_cac:.1f}x</div><div class="lbl">LTV / CAC</div></div>
  <div class="kpi"><div class="val">{total_seats:,}</div><div class="lbl">Active Seats</div></div>
</div>

<div class="grid">
  <div class="card">
    <h2>MRR Growth (12 months)</h2>
    <svg width="100%" height="130" viewBox="0 0 380 120" preserveAspectRatio="none">
      <defs><linearGradient id="mrg" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="#4ade80" stop-opacity="0.35"/>
        <stop offset="100%" stop-color="#4ade80" stop-opacity="0.02"/>
      </linearGradient></defs>
      <polygon points="{mrr_fill}" fill="url(#mrg)"/>
      <polyline points="{mrr_poly}" fill="none" stroke="#4ade80" stroke-width="2.5"/>
      {''.join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="#4ade80"/>' for x, y in mrr_pts)}
      {mrr_xlabels}
    </svg>
  </div>

  <div class="card">
    <h2>Monthly Churn Rate (%)</h2>
    <svg width="100%" height="110" viewBox="0 0 380 100">
      {churn_svg}
      <line x1="0" y1="{75 - int(avg_churn/max_churn*70)}" x2="{chart_w}" y2="{75 - int(avg_churn/max_churn*70)}" stroke="#f59e0b" stroke-width="1" stroke-dasharray="4,3"/>
      <text x="{chart_w-2}" y="{75 - int(avg_churn/max_churn*70) - 3}" fill="#f59e0b" font-size="8" text-anchor="end">avg {avg_churn:.2f}%</text>
    </svg>
  </div>

  <div class="card" style="grid-column:1/-1">
    <h2>Active Seats by Tier</h2>
    <svg width="100%" height="220" viewBox="0 0 400 210">
      {donut_slices}
      <text x="{donut_cx}" y="{donut_cy - 6}" fill="#e2e8f0" font-size="14" font-weight="700" text-anchor="middle">{total_seats}</text>
      <text x="{donut_cx}" y="{donut_cy + 12}" fill="#64748b" font-size="9" text-anchor="middle">total seats</text>
      {legend_svg}
      <text x="200" y="198" fill="#475569" font-size="9" text-anchor="middle">CAC: ${cac:,.0f} &nbsp;|&nbsp; LTV: ${ltv:,.0f} &nbsp;|&nbsp; LTV/CAC: {ltv_cac:.1f}x</text>
    </svg>
  </div>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="SaaS Metrics Dashboard")
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
