"""Deal Desk Analyzer — FastAPI port 8741"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8741

def build_html():
    random.seed(2026)

    # --- Deal pipeline data ---
    stages = ["Prospect", "Qualify", "Demo", "Proposal", "Negotiation", "Closed Won"]
    stage_counts = [24, 17, 11, 8, 5, 3]
    stage_values = [round(random.uniform(0.8, 2.5) * c, 2) for c in stage_counts]  # $M
    stage_colors = ["#38bdf8", "#818cf8", "#a78bfa", "#fbbf24", "#f97316", "#34d399"]

    # --- Monthly ARR trend (12 months) with growth curve ---
    months = ["Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec", "Jan", "Feb", "Mar"]
    base_arr = 1.2
    arr_vals = []
    for i in range(12):
        growth = base_arr * math.exp(0.08 * i)
        noise = random.uniform(-0.05, 0.05)
        arr_vals.append(round(growth + noise, 3))
    arr_max = max(arr_vals) * 1.1

    # --- Win rate by segment ---
    segments = ["Enterprise", "Mid-Market", "SMB", "Public Sector", "ISV"]
    win_rates = [random.uniform(0.28, 0.55) for _ in segments]
    avg_deal_size = [random.uniform(120, 850) for _ in segments]  # $K

    # --- Discount distribution (bell-curve-like) ---
    disc_buckets = ["0-5%", "5-10%", "10-15%", "15-20%", "20-25%", "25%+"]
    disc_vals = []
    for i, label in enumerate(disc_buckets):
        v = int(40 * math.exp(-((i - 1.8)**2) / 2.0) + random.uniform(-2, 2))
        disc_vals.append(max(1, v))
    disc_max = max(disc_vals)

    # --- Deal velocity: scatter of deal_age vs deal_size ---
    scatter_pts = []
    for _ in range(40):
        age = random.uniform(14, 180)
        size = random.uniform(50, 900)
        won = random.random() < (1 / (1 + math.exp((age - 90) / 30)))
        scatter_pts.append((age, size, won))

    # --- Funnel SVG ---
    funnel_svg_w, funnel_svg_h = 420, 280
    total_count = stage_counts[0]
    funnel_shapes = ""
    for i, (stage, count, val, color) in enumerate(zip(stages, stage_counts, stage_values, stage_colors)):
        frac = count / total_count
        bar_w = max(40, int(frac * (funnel_svg_w - 100)))
        bar_h = 36
        bx = (funnel_svg_w - 60 - bar_w) // 2
        by = 10 + i * (bar_h + 6)
        funnel_shapes += f'<rect x="{bx}" y="{by}" width="{bar_w}" height="{bar_h}" fill="{color}" rx="4" opacity="0.88"/>'
        funnel_shapes += f'<text x="{bx + 8}" y="{by + 23}" fill="#0f172a" font-size="12" font-weight="600">{stage}</text>'
        funnel_shapes += f'<text x="{bx + bar_w - 6}" y="{by + 14}" fill="#0f172a" font-size="10" text-anchor="end">{count} deals</text>'
        funnel_shapes += f'<text x="{bx + bar_w - 6}" y="{by + 28}" fill="#0f172a" font-size="10" text-anchor="end">${val:.1f}M</text>'

    # --- ARR trend SVG ---
    arr_svg_w, arr_svg_h = 520, 120
    arr_pts = []
    for i, v in enumerate(arr_vals):
        px = 40 + i * (arr_svg_w - 50) / 11
        py = 10 + (1 - v / arr_max) * (arr_svg_h - 20)
        arr_pts.append((px, py))
    arr_path = "M " + " L ".join(f"{px:.1f},{py:.1f}" for px, py in arr_pts)
    arr_fill = arr_path + f" L {arr_pts[-1][0]:.1f},{arr_svg_h - 10} L {arr_pts[0][0]:.1f},{arr_svg_h - 10} Z"
    arr_dots = "".join(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="3" fill="#34d399"/>' for px, py in arr_pts)
    month_labels = "".join(
        f'<text x="{40 + i * (arr_svg_w - 50) / 11:.1f}" y="{arr_svg_h + 2}" fill="#64748b" font-size="9" text-anchor="middle">{m}</text>'
        for i, m in enumerate(months)
    )
    arr_gridlines = "".join(
        f'<line x1="40" y1="{10 + j * (arr_svg_h - 20) // 4}" x2="{arr_svg_w - 10}" y2="{10 + j * (arr_svg_h - 20) // 4}" stroke="#334155" stroke-width="0.5"/>'
        for j in range(5)
    )

    # --- Win rate bar SVG ---
    wr_svg_w, wr_svg_h = 420, 160
    wr_bar_h = 22
    wr_shapes = ""
    for i, (seg, wr, ads) in enumerate(zip(segments, win_rates, avg_deal_size)):
        bar_w = int(wr * (wr_svg_w - 160))
        by = 10 + i * (wr_bar_h + 8)
        wr_shapes += f'<rect x="110" y="{by}" width="{bar_w}" height="{wr_bar_h}" fill="#C74634" rx="3" opacity="0.82"/>'
        wr_shapes += f'<text x="105" y="{by + 15}" fill="#94a3b8" font-size="11" text-anchor="end">{seg}</text>'
        wr_shapes += f'<text x="{110 + bar_w + 6}" y="{by + 15}" fill="#e2e8f0" font-size="10">{wr*100:.0f}% · ${ads:.0f}K avg</text>'

    # --- Discount histogram SVG ---
    disc_svg_w, disc_svg_h = 380, 120
    disc_bw = int((disc_svg_w - 60) / len(disc_buckets))
    disc_bars = ""
    for i, (label, v) in enumerate(zip(disc_buckets, disc_vals)):
        bh = int(v / disc_max * (disc_svg_h - 30))
        bx = 30 + i * disc_bw
        by = disc_svg_h - 20 - bh
        disc_bars += f'<rect x="{bx + 4}" y="{by}" width="{disc_bw - 8}" height="{bh}" fill="#fbbf24" rx="3" opacity="0.85"/>'
        disc_bars += f'<text x="{bx + disc_bw // 2}" y="{disc_svg_h - 6}" fill="#64748b" font-size="9" text-anchor="middle">{label}</text>'
        disc_bars += f'<text x="{bx + disc_bw // 2}" y="{by - 3}" fill="#e2e8f0" font-size="9" text-anchor="middle">{v}</text>'

    # --- Velocity scatter SVG ---
    scat_svg_w, scat_svg_h = 380, 140
    scat_dots = ""
    for age, size, won in scatter_pts:
        sx = 40 + (age / 200) * (scat_svg_w - 50)
        sy = 10 + (1 - size / 1000) * (scat_svg_h - 20)
        color = "#34d399" if won else "#C74634"
        scat_dots += f'<circle cx="{sx:.1f}" cy="{sy:.1f}" r="5" fill="{color}" opacity="0.75"/>'
    scat_gridlines = "".join(
        f'<line x1="40" y1="{10 + j * (scat_svg_h - 20) // 4}" x2="{scat_svg_w - 10}" y2="{10 + j * (scat_svg_h - 20) // 4}" stroke="#334155" stroke-width="0.5"/>'
        for j in range(5)
    )
    # Logistic boundary line
    boundary_pts = []
    for deg_i in range(0, scat_svg_w - 50, 8):
        age_val = deg_i / (scat_svg_w - 50) * 200
        p = 1 / (1 + math.exp((age_val - 90) / 30))
        size_val = p * 800 + 50
        sx = 40 + deg_i
        sy = 10 + (1 - size_val / 1000) * (scat_svg_h - 20)
        boundary_pts.append(f"{sx:.1f},{sy:.1f}")
    boundary_path = "M " + " L ".join(boundary_pts)

    # --- Summary stats ---
    total_pipeline = sum(stage_values)
    total_deals = sum(stage_counts)
    weighted_arr = sum(arr_vals[-3:]) / 3
    avg_disc = sum(i * v for i, v in enumerate(disc_vals)) / max(1, sum(disc_vals)) * 5
    avg_win = sum(win_rates) / len(win_rates)

    return f"""<!DOCTYPE html><html><head><title>Deal Desk Analyzer</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui,sans-serif;padding:20px}}
h1{{color:#C74634;margin:0 0 4px 0;font-size:1.6rem}}
.subtitle{{color:#64748b;font-size:0.85rem;margin-bottom:20px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:14px}}
.card{{background:#1e293b;padding:20px;border-radius:10px;border:1px solid #334155}}
h2{{color:#38bdf8;margin:0 0 12px 0;font-size:1rem;text-transform:uppercase;letter-spacing:0.05em}}
.stat-row{{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:16px}}
.stat{{background:#0f172a;border-radius:8px;padding:10px 16px;min-width:110px}}
.stat-val{{font-size:1.5rem;font-weight:700;color:#C74634}}
.stat-lbl{{font-size:0.75rem;color:#64748b;margin-top:2px}}
.legend{{display:flex;gap:12px;flex-wrap:wrap;margin-top:8px;font-size:0.8rem}}
.legend-dot{{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:4px;vertical-align:middle}}
.badge{{display:inline-block;background:#C74634;color:#fff;border-radius:4px;padding:2px 8px;font-size:0.75rem;margin-left:8px}}
svg{{display:block;overflow:visible}}
</style></head>
<body>
<h1>Deal Desk Analyzer <span class="badge">PORT {PORT}</span></h1>
<div class="subtitle">Sales pipeline intelligence, ARR forecasting &amp; discount analytics — OCI Robot Cloud</div>

<div class="stat-row">
  <div class="stat"><div class="stat-val">${total_pipeline:.1f}M</div><div class="stat-lbl">Total Pipeline</div></div>
  <div class="stat"><div class="stat-val">{total_deals}</div><div class="stat-lbl">Active Deals</div></div>
  <div class="stat"><div class="stat-val">{avg_win*100:.0f}%</div><div class="stat-lbl">Avg Win Rate</div></div>
  <div class="stat"><div class="stat-val">${weighted_arr:.2f}M</div><div class="stat-lbl">Trailing 3-mo ARR</div></div>
  <div class="stat"><div class="stat-val">{avg_disc:.1f}%</div><div class="stat-lbl">Avg Discount</div></div>
</div>

<div class="grid">
  <div class="card">
    <h2>Deal Funnel by Stage</h2>
    <svg width="{funnel_svg_w}" height="{funnel_svg_h}">
      {funnel_shapes}
    </svg>
  </div>

  <div class="card" style="grid-column:span 2">
    <h2>Monthly ARR Trend (Apr 2025 – Mar 2026)</h2>
    <svg width="{arr_svg_w}" height="{arr_svg_h + 20}">
      {arr_gridlines}
      <path d="{arr_fill}" fill="#34d399" opacity="0.12"/>
      <path d="{arr_path}" fill="none" stroke="#34d399" stroke-width="2.5"/>
      {arr_dots}
      {month_labels}
      {''.join(f'<text x="32" y="{10 + j * (arr_svg_h - 20) // 4 + 4:.0f}" fill="#64748b" font-size="9" text-anchor="end">${arr_max * (1 - j/4):.1f}M</text>' for j in range(5))}
    </svg>
  </div>

  <div class="card">
    <h2>Win Rate &amp; Avg Deal Size by Segment</h2>
    <svg width="{wr_svg_w}" height="{wr_svg_h}">
      {wr_shapes}
    </svg>
  </div>

  <div class="card">
    <h2>Discount Distribution</h2>
    <svg width="{disc_svg_w}" height="{disc_svg_h + 20}">
      <rect x="30" y="0" width="{disc_svg_w - 40}" height="{disc_svg_h - 20}" fill="#0f172a" rx="4"/>
      {disc_bars}
      <text x="{disc_svg_w // 2}" y="{disc_svg_h + 14}" fill="#64748b" font-size="10" text-anchor="middle">Discount Range (# deals)</text>
    </svg>
  </div>

  <div class="card" style="grid-column:span 2">
    <h2>Deal Velocity — Age vs. Size (Won / Lost)</h2>
    <svg width="{scat_svg_w}" height="{scat_svg_h + 30}">
      <rect x="40" y="10" width="{scat_svg_w - 50}" height="{scat_svg_h - 20}" fill="#0f172a" rx="4"/>
      {scat_gridlines}
      <path d="{boundary_path}" fill="none" stroke="#f59e0b" stroke-width="1.5" stroke-dasharray="5,4" opacity="0.7"/>
      {scat_dots}
      <text x="{40 + (scat_svg_w - 50)//2}" y="{scat_svg_h + 20}" fill="#64748b" font-size="11" text-anchor="middle">Deal Age (days)</text>
      <text x="14" y="{scat_svg_h//2}" fill="#64748b" font-size="11" text-anchor="middle" transform="rotate(-90 14 {scat_svg_h//2})">Size ($K)</text>
    </svg>
    <div class="legend">
      <span><span class="legend-dot" style="background:#34d399"></span>Won</span>
      <span><span class="legend-dot" style="background:#C74634"></span>Lost</span>
      <span style="color:#f59e0b">&#9135; Logistic decision boundary</span>
    </div>
  </div>
</div>

<div style="color:#475569;font-size:0.75rem;margin-top:20px">
  OCI Robot Cloud · Deal Desk Analyzer · port {PORT} · 2026
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Deal Desk Analyzer")

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
