"""Pricing Strategy Analyzer — FastAPI port 8737"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8737

def build_html():
    random.seed(17)

    # ── Simulated pricing tiers ──────────────────────────────────────────────
    tiers = [
        {"name": "Starter",    "price": 299,  "seats": 5,   "robots": 2},
        {"name": "Growth",     "price": 999,  "seats": 20,  "robots": 10},
        {"name": "Enterprise", "price": 4999, "seats": 200, "robots": 100},
        {"name": "Fleet",      "price": 14999,"seats": 999, "robots": 500},
    ]

    # ── Revenue model: MRR over 24 months ───────────────────────────────────
    months = 24
    mrr = []
    customers = 0.0
    for m in range(months):
        customers += 1.8 + 0.6 * math.sin(m * 0.52) + random.uniform(0, 0.8)
        avg_rev = 2400 + 400 * math.log1p(m)
        mrr.append(round(customers * avg_rev))

    max_mrr = max(mrr)
    W, H = 560, 180
    pad = 40
    chart_w = W - 2 * pad
    chart_h = H - 2 * pad

    def mrr_pts(series):
        pts = []
        for i, v in enumerate(series):
            x = pad + i * chart_w / (len(series) - 1)
            y = H - pad - (v / max_mrr) * chart_h
            pts.append(f"{x:.1f},{y:.1f}")
        return " ".join(pts)

    mrr_polyline = mrr_pts(mrr)

    # ── Churn vs Expansion revenue (stacked area approximation) ─────────────
    expansion = [round(mrr[i] * (0.12 + 0.04 * math.sin(i * 0.3 + 1)), 0) for i in range(months)]
    churn_rev  = [round(mrr[i] * (0.05 + 0.015 * math.cos(i * 0.4)), 0) for i in range(months)]

    # ── Price elasticity curve ───────────────────────────────────────────────
    prices_range = [100 + i * 50 for i in range(20)]
    demand       = [round(5000 * math.exp(-p / 2800) + random.uniform(-30, 30)) for p in prices_range]
    max_demand = max(demand)

    def elast_pts(series, max_v):
        pts = []
        for i, v in enumerate(series):
            x = pad + i * chart_w / (len(series) - 1)
            y = H - pad - (v / max_v) * chart_h
            pts.append(f"{x:.1f},{y:.1f}")
        return " ".join(pts)

    elast_polyline = elast_pts(demand, max_demand)

    # ── Tier bar chart ───────────────────────────────────────────────────────
    tier_colors = ["#a78bfa", "#38bdf8", "#34d399", "#fb923c"]
    max_price = max(t["price"] for t in tiers)
    bar_w_t = chart_w / len(tiers)
    tier_bars = ""
    tier_labels = ""
    for i, t in enumerate(tiers):
        bh = (t["price"] / max_price) * chart_h
        bx = pad + i * bar_w_t + bar_w_t * 0.1
        by = H - pad - bh
        bw = bar_w_t * 0.8
        tier_bars += f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bw:.1f}" height="{bh:.1f}" fill="{tier_colors[i]}" rx="3"/>'
        tier_labels += (f'<text x="{bx + bw/2:.1f}" y="{H - pad + 14}" '
                        f'text-anchor="middle" fill="{tier_colors[i]}" style="font-size:10px">{t["name"]}</text>')
        tier_labels += (f'<text x="{bx + bw/2:.1f}" y="{by - 3:.1f}" '
                        f'text-anchor="middle" fill="#e2e8f0" style="font-size:10px">${t["price"]:,}</text>')

    # ── Key metrics ──────────────────────────────────────────────────────────
    total_mrr      = mrr[-1]
    arr            = total_mrr * 12
    avg_deal_size  = round(sum(t["price"] for t in tiers) / len(tiers))
    ltv_cac_ratio  = round(3.2 + random.uniform(-0.2, 0.2), 1)
    payback_months = round(8.4 + random.uniform(-0.5, 0.5), 1)
    gross_margin   = round(0.782 + random.uniform(-0.01, 0.01), 3)

    return f"""<!DOCTYPE html><html><head><title>Pricing Strategy Analyzer</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui;padding:20px}}
h1{{color:#C74634;margin:0 0 4px 0}}h2{{color:#38bdf8;font-size:14px;margin:8px 0 4px 0}}
.card{{background:#1e293b;padding:18px;margin:10px 0;border-radius:8px;border:1px solid #334155}}
.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:10px}}
.metric{{background:#0f172a;border-radius:6px;padding:14px;text-align:center}}
.metric .val{{font-size:26px;font-weight:700;color:#34d399}}
.metric .lbl{{font-size:11px;color:#94a3b8;margin-top:4px}}
.tier-table{{width:100%;border-collapse:collapse;font-size:13px}}
.tier-table th{{color:#94a3b8;text-align:left;padding:6px 10px;border-bottom:1px solid #334155}}
.tier-table td{{padding:6px 10px;border-bottom:1px solid #1e293b}}
.badge{{display:inline-block;padding:2px 8px;border-radius:4px;font-size:11px}}
svg text{{font:11px system-ui;fill:#94a3b8}}
</style></head>
<body>
<h1>Pricing Strategy Analyzer</h1>
<p style="color:#64748b;font-size:13px;margin:0 0 12px 0">OCI Robot Cloud · SaaS pricing intelligence · port {PORT}</p>

<div class="grid">
  <div class="metric"><div class="val">${total_mrr:,}</div><div class="lbl">MRR (month 24)</div></div>
  <div class="metric"><div class="val">${arr:,}</div><div class="lbl">Projected ARR</div></div>
  <div class="metric"><div class="val">{ltv_cac_ratio}×</div><div class="lbl">LTV : CAC</div></div>
  <div class="metric"><div class="val">{payback_months} mo</div><div class="lbl">Payback Period</div></div>
  <div class="metric"><div class="val">{gross_margin:.1%}</div><div class="lbl">Gross Margin</div></div>
  <div class="metric"><div class="val">${avg_deal_size:,}</div><div class="lbl">Avg Deal Size</div></div>
</div>

<div class="card">
  <h2>MRR Trajectory — 24 Months</h2>
  <svg width="{W}" height="{H}" style="display:block">
    <defs><linearGradient id="g1" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#34d399" stop-opacity="0.3"/>
      <stop offset="100%" stop-color="#34d399" stop-opacity="0"/>
    </linearGradient></defs>
    <line x1="{pad}" y1="{pad}" x2="{pad}" y2="{H-pad}" stroke="#334155"/>
    <line x1="{pad}" y1="{H-pad}" x2="{W-pad}" y2="{H-pad}" stroke="#334155"/>
    <polyline points="{mrr_polyline}" fill="url(#g1)" stroke="none"/>
    <polyline points="{mrr_polyline}" fill="none" stroke="#34d399" stroke-width="2.5"/>
    <text x="{pad+4}" y="{pad+12}">$0</text>
    <text x="{pad+4}" y="{H-pad-4}">${max_mrr:,}</text>
    <text x="{pad}" y="{H-pad+14}">M1</text>
    <text x="{W-pad-18}" y="{H-pad+14}">M{months}</text>
  </svg>
</div>

<div class="card">
  <h2>Price Elasticity Curve (demand vs. monthly price)</h2>
  <svg width="{W}" height="{H}" style="display:block">
    <line x1="{pad}" y1="{pad}" x2="{pad}" y2="{H-pad}" stroke="#334155"/>
    <line x1="{pad}" y1="{H-pad}" x2="{W-pad}" y2="{H-pad}" stroke="#334155"/>
    <polyline points="{elast_polyline}" fill="none" stroke="#fb923c" stroke-width="2.5"/>
    <text x="{pad+4}" y="{pad+12}">high demand</text>
    <text x="{pad}" y="{H-pad+14}">${prices_range[0]}</text>
    <text x="{W-pad-28}" y="{H-pad+14}">${prices_range[-1]}</text>
  </svg>
</div>

<div class="card">
  <h2>Tier Pricing Comparison</h2>
  <svg width="{W}" height="{H}" style="display:block">
    <line x1="{pad}" y1="{pad}" x2="{pad}" y2="{H-pad}" stroke="#334155"/>
    <line x1="{pad}" y1="{H-pad}" x2="{W-pad}" y2="{H-pad}" stroke="#334155"/>
    {tier_bars}
    {tier_labels}
  </svg>
  <table class="tier-table" style="margin-top:12px">
    <tr><th>Tier</th><th>Monthly</th><th>Seats</th><th>Robots</th><th>$/Robot</th><th>Segment</th></tr>
    {''.join(f"<tr><td style='color:{tier_colors[i]};font-weight:600'>{t['name']}</td><td>${t['price']:,}</td><td>{t['seats']}</td><td>{t['robots']}</td><td>${t['price']//t['robots']}</td><td><span class='badge' style='background:#1e3a5f;color:#7dd3fc'>{'SMB' if t['price']<1000 else 'Mid-Market' if t['price']<5000 else 'Enterprise'}</span></td></tr>" for i,t in enumerate(tiers))}
  </table>
</div>

<div class="card">
  <h2>Recommended Actions</h2>
  <ul style="font-size:13px;line-height:1.8;color:#cbd5e1">
    <li>Introduce <strong style="color:#a78bfa">usage-based overage</strong> at $0.08/robot-hour above tier limit</li>
    <li>Bundle <strong style="color:#38bdf8">Isaac Sim SDG credits</strong> into Enterprise+ to increase ACV by ~18%</li>
    <li>Offer <strong style="color:#34d399">annual pre-pay discount</strong> of 20% to improve cash flow and reduce churn</li>
    <li>Add <strong style="color:#fb923c">Professional Services</strong> SKU ($15k/engagement) for Fortune 500 onboarding</li>
  </ul>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Pricing Strategy Analyzer")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return build_html()

    @app.get("/health")
    def health():
        return {"status": "ok", "port": PORT, "service": "pricing_strategy_analyzer"}

    @app.get("/tiers")
    def get_tiers():
        return [
            {"name": "Starter",    "price": 299,  "seats": 5,   "robots": 2},
            {"name": "Growth",     "price": 999,  "seats": 20,  "robots": 10},
            {"name": "Enterprise", "price": 4999, "seats": 200, "robots": 100},
            {"name": "Fleet",      "price": 14999,"seats": 999, "robots": 500},
        ]

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
