"""Customer Activation Dashboard — FastAPI port 8717"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8717

def build_html():
    random.seed(99)

    # Monthly activation cohort (12 months)
    months = ["Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec", "Jan", "Feb", "Mar"]
    new_signups   = [random.randint(18, 42) for _ in months]
    activated     = [int(n * (0.55 + 0.3 * math.sin(i / 3.5) + random.gauss(0, 0.05))) for i, n in enumerate(new_signups)]
    activated     = [max(5, min(a, n)) for a, n in zip(activated, new_signups)]
    activation_r  = [round(a / n, 3) for a, n in zip(activated, new_signups)]

    # Funnel stages
    funnel_stages = ["Signed Up", "Onboarded", "First Deploy", "3 Runs", "Design Partner"]
    funnel_vals   = [340, 241, 178, 112, 47]
    funnel_colors = ["#38bdf8", "#818cf8", "#34d399", "#fb923c", "#C74634"]

    # Time-to-activate distribution (days, log-normal-ish)
    tta_buckets   = ["0-1d", "1-3d", "3-7d", "7-14d", "14-30d", ">30d"]
    tta_counts    = [28, 54, 61, 39, 22, 14]

    # Revenue by segment
    segments      = ["Enterprise", "Mid-Market", "Startup", "Research", "Gov"]
    rev_k         = [round(random.uniform(210, 380), 1) for _ in segments]

    # KPIs
    total_signups   = sum(new_signups)
    total_activated = sum(activated)
    overall_rate    = round(total_activated / total_signups * 100, 1)
    median_tta_days = 4.7
    churn_rate      = round(random.uniform(3.1, 4.8), 1)
    nps             = random.randint(52, 68)
    mrr_k           = round(sum(rev_k) / 12, 1)

    # --- SVG: Monthly bar chart (signups vs activated) ---
    bc_w, bc_h = 620, 180
    bc_pad = 40
    n_bars  = len(months)
    slot_w  = (bc_w - 2 * bc_pad) / n_bars
    bar_w   = slot_w * 0.38
    max_val = max(new_signups) + 4

    def by(v):
        return bc_pad + (bc_h - 2 * bc_pad) * (1 - v / max_val)

    bars = ""
    for i, (s, a, m) in enumerate(zip(new_signups, activated, months)):
        bx_s = bc_pad + i * slot_w + 2
        bx_a = bx_s + bar_w + 2
        # signups bar
        bars += f'<rect x="{bx_s:.1f}" y="{by(s):.1f}" width="{bar_w:.1f}" height="{bc_h - bc_pad - by(s):.1f}" fill="#334155" rx="2"/>'
        # activated bar
        bars += f'<rect x="{bx_a:.1f}" y="{by(a):.1f}" width="{bar_w:.1f}" height="{bc_h - bc_pad - by(a):.1f}" fill="#38bdf8" rx="2"/>'
        bars += f'<text x="{bx_s + bar_w:.1f}" y="{bc_h - bc_pad + 13}" fill="#64748b" font-size="10" text-anchor="middle">{m}</text>'

    # --- SVG: Funnel ---
    fn_w, fn_h = 320, 200
    fn_pad = 20
    fn_max = funnel_vals[0]
    fn_bars = ""
    for i, (stage, val, col) in enumerate(zip(funnel_stages, funnel_vals, funnel_colors)):
        bw = fn_pad + (fn_w - 2 * fn_pad) * val / fn_max
        bx = (fn_w - bw) / 2
        by_f = fn_pad + i * (fn_h - 2 * fn_pad) / len(funnel_stages)
        bh = (fn_h - 2 * fn_pad) / len(funnel_stages) - 4
        fn_bars += f'<rect x="{bx:.1f}" y="{by_f:.1f}" width="{bw:.1f}" height="{bh:.1f}" fill="{col}" rx="3" opacity="0.85"/>'
        fn_bars += f'<text x="{fn_w/2:.1f}" y="{by_f + bh/2 + 4:.1f}" fill="#f1f5f9" font-size="11" text-anchor="middle" font-weight="600">{stage} ({val})</text>'

    # --- SVG: TTA histogram ---
    tta_w, tta_h = 320, 160
    tta_pad = 30
    tta_slot = (tta_w - 2 * tta_pad) / len(tta_buckets)
    tta_bw   = tta_slot * 0.7
    tta_max  = max(tta_counts)
    tta_bars = ""
    for i, (b, c) in enumerate(zip(tta_buckets, tta_counts)):
        bx = tta_pad + i * tta_slot + (tta_slot - tta_bw) / 2
        bh = (tta_h - 2 * tta_pad) * c / tta_max
        by_t = tta_pad + (tta_h - 2 * tta_pad) - bh
        tta_bars += f'<rect x="{bx:.1f}" y="{by_t:.1f}" width="{tta_bw:.1f}" height="{bh:.1f}" fill="#818cf8" rx="3"/>'
        tta_bars += f'<text x="{bx + tta_bw/2:.1f}" y="{tta_h - tta_pad + 13}" fill="#64748b" font-size="9" text-anchor="middle">{b}</text>'
        tta_bars += f'<text x="{bx + tta_bw/2:.1f}" y="{by_t - 3:.1f}" fill="#e2e8f0" font-size="9" text-anchor="middle">{c}</text>'

    # --- Activation rate sparkline ---
    sp_w, sp_h = 620, 60
    sp_pad = 10
    sp_pts = " ".join(
        f"{sp_pad + i * (sp_w - 2*sp_pad)/(len(activation_r)-1):.1f},{sp_pad + (sp_h - 2*sp_pad)*(1 - (r - 0.4)/0.6):.1f}"
        for i, r in enumerate(activation_r)
    )

    return f"""<!DOCTYPE html><html><head><title>Customer Activation Dashboard</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui,sans-serif}}
h1{{color:#C74634;margin:0;padding:20px 24px 4px;font-size:1.6rem}}
.subtitle{{color:#94a3b8;padding:0 24px 16px;font-size:0.9rem}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;padding:0 16px 24px}}
.card{{background:#1e293b;padding:18px 20px;border-radius:10px;border:1px solid #334155}}
.card h2{{color:#38bdf8;margin:0 0 10px;font-size:0.85rem;text-transform:uppercase;letter-spacing:.06em}}
.kpi{{font-size:1.9rem;font-weight:700;color:#f1f5f9}}
.kpi-sub{{font-size:0.78rem;color:#64748b;margin-top:3px}}
.wide{{grid-column:span 2}}.full{{grid-column:span 4}}
.legend{{display:flex;gap:16px;margin-top:6px;font-size:0.8rem;color:#94a3b8}}
.dot{{width:10px;height:10px;border-radius:2px;display:inline-block;margin-right:4px;vertical-align:middle}}
</style></head>
<body>
<h1>Customer Activation Dashboard</h1>
<p class="subtitle">OCI Robot Cloud — design partner pipeline &amp; activation funnel &nbsp;|&nbsp; Port {PORT}</p>

<div class="grid">
  <div class="card">
    <h2>Activation Rate</h2>
    <div class="kpi">{overall_rate}%</div>
    <div class="kpi-sub">{total_activated} / {total_signups} signups</div>
  </div>
  <div class="card">
    <h2>Median Time-to-Activate</h2>
    <div class="kpi">{median_tta_days}d</div>
    <div class="kpi-sub">signup → first successful deploy</div>
  </div>
  <div class="card">
    <h2>MRR (avg / mo)</h2>
    <div class="kpi">${mrr_k:.1f}k</div>
    <div class="kpi-sub">across all segments</div>
  </div>
  <div class="card">
    <h2>NPS Score</h2>
    <div class="kpi">{nps}</div>
    <div class="kpi-sub">n=83 responses this quarter</div>
  </div>

  <div class="card full">
    <h2>Monthly Signups vs Activated (12-month rolling)</h2>
    <svg width="{bc_w}" height="{bc_h}" viewBox="0 0 {bc_w} {bc_h}">
      <line x1="{bc_pad}" y1="{bc_pad}" x2="{bc_pad}" y2="{bc_h-bc_pad}" stroke="#334155" stroke-width="1"/>
      <line x1="{bc_pad}" y1="{bc_h-bc_pad}" x2="{bc_w-bc_pad}" y2="{bc_h-bc_pad}" stroke="#334155" stroke-width="1"/>
      <text x="{bc_pad-4}" y="{bc_pad+4}" fill="#64748b" font-size="10" text-anchor="end">{max_val}</text>
      <text x="{bc_pad-4}" y="{bc_h-bc_pad}" fill="#64748b" font-size="10" text-anchor="end">0</text>
      {bars}
    </svg>
    <div class="legend">
      <span><span class="dot" style="background:#334155"></span>Signups</span>
      <span><span class="dot" style="background:#38bdf8"></span>Activated</span>
    </div>
  </div>

  <div class="card full">
    <h2>Activation Rate Trend</h2>
    <svg width="{sp_w}" height="{sp_h}" viewBox="0 0 {sp_w} {sp_h}">
      <polyline points="{sp_pts}" fill="none" stroke="#34d399" stroke-width="2" stroke-linejoin="round"/>
      {''.join(f'<circle cx="{sp_pad + i*(sp_w-2*sp_pad)/(len(activation_r)-1):.1f}" cy="{sp_pad + (sp_h-2*sp_pad)*(1-(r-0.4)/0.6):.1f}" r="3" fill="#34d399"/>' for i, r in enumerate(activation_r))}
    </svg>
  </div>

  <div class="card wide">
    <h2>Activation Funnel</h2>
    <svg width="{fn_w}" height="{fn_h}" viewBox="0 0 {fn_w} {fn_h}">
      {fn_bars}
    </svg>
  </div>

  <div class="card wide">
    <h2>Time-to-Activate Distribution</h2>
    <svg width="{tta_w}" height="{tta_h}" viewBox="0 0 {tta_w} {tta_h}">
      <line x1="{tta_pad}" y1="{tta_pad}" x2="{tta_pad}" y2="{tta_h-tta_pad}" stroke="#334155" stroke-width="1"/>
      <line x1="{tta_pad}" y1="{tta_h-tta_pad}" x2="{tta_w-tta_pad}" y2="{tta_h-tta_pad}" stroke="#334155" stroke-width="1"/>
      {tta_bars}
    </svg>
  </div>

  <div class="card">
    <h2>Design Partners</h2>
    <div class="kpi">47</div>
    <div class="kpi-sub">+9 this quarter</div>
  </div>
  <div class="card">
    <h2>Churn Rate</h2>
    <div class="kpi">{churn_rate}%</div>
    <div class="kpi-sub">monthly, activated cohort</div>
  </div>
  <div class="card">
    <h2>Avg Deploys / Partner</h2>
    <div class="kpi">14.3</div>
    <div class="kpi-sub">trailing 30 days</div>
  </div>
  <div class="card">
    <h2>Support Tickets</h2>
    <div class="kpi">23</div>
    <div class="kpi-sub">open &nbsp;|&nbsp; p50 resolve: 1.2d</div>
  </div>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Customer Activation Dashboard")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return build_html()

    @app.get("/health")
    def health():
        return {"status": "ok", "port": PORT}

    @app.get("/metrics")
    def metrics():
        random.seed()
        return {
            "port": PORT,
            "activation_rate_pct": round(random.uniform(62, 74), 1),
            "median_tta_days": round(random.uniform(3.5, 6.2), 1),
            "design_partners": 47,
            "mrr_k": round(random.uniform(95, 130), 1),
            "nps": random.randint(52, 68),
            "churn_rate_pct": round(random.uniform(3.0, 5.0), 1),
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
