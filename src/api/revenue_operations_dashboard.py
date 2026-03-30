"""Revenue Operations Dashboard — FastAPI port 8793"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8793

def build_html():
    random.seed(2026)

    # Monthly ARR growth (12 months) — exponential with noise
    months = ["Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec", "Jan", "Feb", "Mar"]
    base_arr = 1_200_000
    arr_vals = []
    for i in range(12):
        growth = base_arr * (1 + 0.09) ** i
        noise = random.uniform(-30000, 30000)
        arr_vals.append(round(growth + noise, 0))

    # Pipeline by stage
    stages = ["Prospecting", "Qualification", "Demo", "Proposal", "Negotiation", "Closed Won"]
    stage_counts = [48, 31, 22, 15, 9, 6]
    stage_values = [round(random.uniform(2.1, 3.8) * c * 10000, 0) for c in stage_counts]
    stage_colors = ["#38bdf8", "#818cf8", "#a78bfa", "#f472b6", "#fb923c", "#4ade80"]

    # Win/loss by segment
    segments = ["Enterprise", "Mid-Market", "SMB", "Partner"]
    wins =   [14, 23, 41, 18]
    losses = [7,  12, 28,  9]

    # Monthly new logos & churned logos
    random.seed(88)
    new_logos    = [random.randint(4, 14) for _ in range(12)]
    churned      = [random.randint(1,  5) for _ in range(12)]

    # CAC & LTV trailing 12 months
    random.seed(33)
    cac_vals = [round(8500 + random.uniform(-800, 800), 0) for _ in range(12)]
    ltv_vals = [round(cac_vals[i] * random.uniform(4.8, 6.2), 0) for i in range(12)]
    ltv_cac  = [round(ltv_vals[i] / cac_vals[i], 2) for i in range(12)]

    # --- SVG: ARR trend ---
    W, H = 680, 220
    pl, pr, pt, pb = 70, 20, 20, 36
    cw = W - pl - pr
    ch = H - pt - pb
    arr_max = max(arr_vals) * 1.08
    arr_min = min(arr_vals) * 0.92

    def ax(i): return pl + (i / (len(arr_vals) - 1)) * cw
    def ay(v): return pt + ch - ((v - arr_min) / (arr_max - arr_min)) * ch

    arr_area_pts = " ".join(f"{ax(i):.1f},{ay(v):.1f}" for i, v in enumerate(arr_vals))
    arr_area_pts = f"{ax(0):.1f},{ay(arr_min):.1f} " + arr_area_pts + f" {ax(len(arr_vals)-1):.1f},{ay(arr_min):.1f}"

    arr_line_pts = " ".join(f"{ax(i):.1f},{ay(v):.1f}" for i, v in enumerate(arr_vals))

    arr_yticks = ""
    for tick in [1_200_000, 1_500_000, 1_800_000, 2_100_000]:
        if arr_min <= tick <= arr_max:
            ty = ay(tick)
            label = f"${tick//1000}K"
            arr_yticks += f'<line x1="{pl-4}" y1="{ty:.1f}" x2="{pl}" y2="{ty:.1f}" stroke="#475569"/>'
            arr_yticks += f'<text x="{pl-8}" y="{ty+4:.1f}" fill="#94a3b8" font-size="10" text-anchor="end">{label}</text>'
            arr_yticks += f'<line x1="{pl}" y1="{ty:.1f}" x2="{pl+cw}" y2="{ty:.1f}" stroke="#1e293b" stroke-width="1"/>'

    arr_xticks = ""
    for i, m in enumerate(months):
        tx = ax(i)
        arr_xticks += f'<text x="{tx:.1f}" y="{pt+ch+16:.1f}" fill="#94a3b8" font-size="10" text-anchor="middle">{m}</text>'

    arr_svg = f"""
    <svg width="{W}" height="{H}" style="display:block">
      <rect width="{W}" height="{H}" fill="#0f172a" rx="4"/>
      {arr_yticks}{arr_xticks}
      <defs>
        <linearGradient id="arrGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="#4ade80" stop-opacity="0.35"/>
          <stop offset="100%" stop-color="#4ade80" stop-opacity="0.02"/>
        </linearGradient>
      </defs>
      <polygon points="{arr_area_pts}" fill="url(#arrGrad)"/>
      <polyline points="{arr_line_pts}" fill="none" stroke="#4ade80" stroke-width="2.5"/>
      {''.join(f'<circle cx="{ax(i):.1f}" cy="{ay(v):.1f}" r="3.5" fill="#4ade80"/>' for i, v in enumerate(arr_vals))}
    </svg>"""

    # --- SVG: Pipeline funnel bars ---
    FW, FH = 340, 220
    fpl, fpr, fpt, fpb = 90, 16, 16, 16
    fcw = FW - fpl - fpr
    fch = FH - fpt - fpb
    bar_h = fch // len(stages) - 4
    max_sv = max(stage_values)

    funnel_bars = ""
    for i, (s, sv, sc) in enumerate(zip(stages, stage_values, stage_colors)):
        by = fpt + i * (fch // len(stages)) + 2
        bw = max(4, int((sv / max_sv) * fcw))
        label = f"${int(sv)//1000}K"
        funnel_bars += f'<text x="{fpl-5}" y="{by+bar_h//2+4:.1f}" fill="#94a3b8" font-size="10" text-anchor="end">{s}</text>'
        funnel_bars += f'<rect x="{fpl}" y="{by}" width="{bw}" height="{bar_h}" fill="{sc}" rx="2"/>'
        funnel_bars += f'<text x="{fpl+bw+5}" y="{by+bar_h//2+4:.1f}" fill="{sc}" font-size="10">{label} ({stage_counts[i]})</text>'

    funnel_svg = f"""
    <svg width="{FW}" height="{FH}" style="display:block">
      <rect width="{FW}" height="{FH}" fill="#0f172a" rx="4"/>
      {funnel_bars}
    </svg>"""

    # --- Win/loss grouped bars ---
    WW, WH = 340, 220
    wpl, wpr, wpt, wpb = 16, 16, 16, 36
    wcw = WW - wpl - wpr
    wch = WH - wpt - wpb
    seg_w = wcw // len(segments)
    bar_pad = 4
    win_max = max(max(wins), max(losses)) * 1.15

    wl_bars = ""
    for i, (seg, w, l) in enumerate(zip(segments, wins, losses)):
        bx = wpl + i * seg_w
        bw = (seg_w - 3 * bar_pad) // 2
        wh = int((w / win_max) * wch)
        lh = int((l / win_max) * wch)
        wx = bx + bar_pad
        lx = wx + bw + bar_pad
        wl_bars += f'<rect x="{wx}" y="{wpt+wch-wh}" width="{bw}" height="{wh}" fill="#4ade80" rx="2"/>'
        wl_bars += f'<text x="{wx+bw//2}" y="{wpt+wch-wh-3}" fill="#4ade80" font-size="10" text-anchor="middle">{w}</text>'
        wl_bars += f'<rect x="{lx}" y="{wpt+wch-lh}" width="{bw}" height="{lh}" fill="#f87171" rx="2"/>'
        wl_bars += f'<text x="{lx+bw//2}" y="{wpt+wch-lh-3}" fill="#f87171" font-size="10" text-anchor="middle">{l}</text>'
        wl_bars += f'<text x="{bx+seg_w//2}" y="{wpt+wch+14:.1f}" fill="#94a3b8" font-size="10" text-anchor="middle">{seg}</text>'

    wl_svg = f"""
    <svg width="{WW}" height="{WH}" style="display:block">
      <rect width="{WW}" height="{WH}" fill="#0f172a" rx="4"/>
      {wl_bars}
      <rect x="{WW-100}" y="8" width="10" height="10" fill="#4ade80" rx="2"/>
      <text x="{WW-87}" y="17" fill="#94a3b8" font-size="10">Won</text>
      <rect x="{WW-60}" y="8" width="10" height="10" fill="#f87171" rx="2"/>
      <text x="{WW-47}" y="17" fill="#94a3b8" font-size="10">Lost</text>
    </svg>"""

    # --- LTV:CAC sparkline ---
    SW, SH = 680, 130
    spl, spr, spt, spb = 55, 20, 16, 28
    scw = SW - spl - spr
    sch = SH - spt - spb
    ltv_max = max(ltv_cac) * 1.1
    ltv_min = min(ltv_cac) * 0.9

    def lx(i): return spl + (i / (len(ltv_cac)-1)) * scw
    def ly(v): return spt + sch - ((v - ltv_min) / (ltv_max - ltv_min)) * sch

    ltv_pts = " ".join(f"{lx(i):.1f},{ly(v):.1f}" for i, v in enumerate(ltv_cac))
    ideal_y = ly(5.0)
    ltv_xticks = ""
    for i, m in enumerate(months):
        ltv_xticks += f'<text x="{lx(i):.1f}" y="{spt+sch+16:.1f}" fill="#94a3b8" font-size="10" text-anchor="middle">{m}</text>'
    ltv_yticks = ""
    for tick in [4.5, 5.0, 5.5, 6.0]:
        if ltv_min <= tick <= ltv_max:
            ty2 = ly(tick)
            ltv_yticks += f'<text x="{spl-8}" y="{ty2+4:.1f}" fill="#94a3b8" font-size="10" text-anchor="end">{tick}x</text>'
            ltv_yticks += f'<line x1="{spl}" y1="{ty2:.1f}" x2="{spl+scw}" y2="{ty2:.1f}" stroke="#1e293b" stroke-width="1"/>'

    ltv_svg = f"""
    <svg width="{SW}" height="{SH}" style="display:block">
      <rect width="{SW}" height="{SH}" fill="#0f172a" rx="4"/>
      {ltv_yticks}{ltv_xticks}
      <line x1="{spl}" y1="{ideal_y:.1f}" x2="{spl+scw}" y2="{ideal_y:.1f}" stroke="#f59e0b" stroke-width="1" stroke-dasharray="5,4"/>
      <text x="{spl+scw-2}" y="{ideal_y-5:.1f}" fill="#f59e0b" font-size="10" text-anchor="end">Target 5x</text>
      <polyline points="{ltv_pts}" fill="none" stroke="#fb923c" stroke-width="2.5"/>
      {''.join(f'<circle cx="{lx(i):.1f}" cy="{ly(v):.1f}" r="3.5" fill="#fb923c"/><title>{v}x</title>' for i, v in enumerate(ltv_cac))}
    </svg>"""

    # Summary KPIs
    latest_arr = arr_vals[-1]
    arr_growth = round((arr_vals[-1] / arr_vals[0] - 1) * 100, 1)
    total_pipeline = sum(stage_values)
    win_rate = round(sum(wins) / (sum(wins) + sum(losses)) * 100, 1)
    avg_ltv_cac = round(sum(ltv_cac) / len(ltv_cac), 2)
    net_new_logos = sum(new_logos) - sum(churned)

    return f"""<!DOCTYPE html>
<html><head><title>Revenue Operations Dashboard</title>
<style>
  body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui,sans-serif}}
  h1{{color:#C74634;margin:0;padding:20px 24px 0;font-size:22px}}
  h2{{color:#38bdf8;font-size:14px;margin:0 0 12px}}
  .grid{{display:grid;grid-template-columns:1fr 1fr;gap:12px;padding:12px 24px}}
  .card{{background:#1e293b;padding:20px;border-radius:8px;border:1px solid #334155}}
  .card.full{{grid-column:1/-1}}
  .kpi-row{{display:flex;gap:0;padding:0 24px 8px;flex-wrap:wrap}}
  .kpi{{background:#1e293b;border:1px solid #334155;border-radius:8px;padding:14px 20px;margin:4px;flex:1;min-width:120px}}
  .kpi .val{{font-size:24px;font-weight:700}}
  .kpi .lbl{{font-size:11px;color:#64748b;margin-top:3px}}
  .subtitle{{color:#64748b;font-size:12px;margin-top:4px;padding:0 24px 10px}}
</style></head>
<body>
<h1>Revenue Operations Dashboard</h1>
<p class="subtitle">OCI Robot Cloud — ARR, pipeline health, win/loss, and unit economics (TTM)</p>

<div class="kpi-row">
  <div class="kpi"><div class="val" style="color:#4ade80">${latest_arr/1e6:.2f}M</div><div class="lbl">Current ARR</div></div>
  <div class="kpi"><div class="val" style="color:#38bdf8">+{arr_growth}%</div><div class="lbl">ARR Growth YoY</div></div>
  <div class="kpi"><div class="val" style="color:#a78bfa">${total_pipeline/1e6:.1f}M</div><div class="lbl">Open Pipeline</div></div>
  <div class="kpi"><div class="val" style="color:#fb923c">{win_rate}%</div><div class="lbl">Win Rate</div></div>
  <div class="kpi"><div class="val" style="color:#f59e0b">{avg_ltv_cac}x</div><div class="lbl">Avg LTV:CAC</div></div>
  <div class="kpi"><div class="val" style="color:#4ade80">+{net_new_logos}</div><div class="lbl">Net New Logos (TTM)</div></div>
</div>

<div class="grid">
  <div class="card full">
    <h2>Monthly ARR ($) — Trailing 12 Months</h2>
    {arr_svg}
  </div>

  <div class="card">
    <h2>Pipeline by Stage (Deal Value)</h2>
    {funnel_svg}
  </div>

  <div class="card">
    <h2>Win / Loss by Segment</h2>
    {wl_svg}
  </div>

  <div class="card full">
    <h2>LTV:CAC Ratio — Monthly Trend</h2>
    {ltv_svg}
  </div>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Revenue Operations Dashboard")
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
