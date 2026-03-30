"""Subscription Tier Optimizer — FastAPI port 8721"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8721

TIERS = [
    {"name": "Starter",    "price": 99,   "robots": 1,  "inferences": 10_000,  "storage_gb": 10,  "support": "Community"},
    {"name": "Pro",        "price": 499,  "robots": 5,  "inferences": 100_000, "storage_gb": 100, "support": "Email 24h"},
    {"name": "Enterprise", "price": 1999, "robots": 25, "inferences": 500_000, "storage_gb": 500, "support": "Dedicated"},
    {"name": "Fleet",      "price": 7499, "robots": 100,"inferences":2_000_000,"storage_gb":2000, "support": "SLA 99.99%"},
]

def build_html():
    random.seed(7)

    # Monthly revenue simulation: 24 months, S-curve growth per tier
    months = list(range(1, 25))
    def s_curve(t, cap, mid, k):
        return cap / (1 + math.exp(-k * (t - mid)))

    tier_counts = [
        [int(s_curve(m, 420, 10, 0.38) + random.gauss(0, 8)) for m in months],  # Starter
        [int(s_curve(m, 180, 12, 0.30) + random.gauss(0, 4)) for m in months],  # Pro
        [int(s_curve(m,  55, 14, 0.25) + random.gauss(0, 2)) for m in months],  # Enterprise
        [int(s_curve(m,  18, 16, 0.22) + random.gauss(0, 1)) for m in months],  # Fleet
    ]
    tier_prices = [t["price"] for t in TIERS]
    monthly_rev = [sum(tier_counts[ti][m] * tier_prices[ti] for ti in range(4)) for m in range(24)]

    # Churn rate simulation per tier (lower for higher tiers)
    churn_rates = [
        [round(max(0.02, 0.12 - 0.003 * m + random.gauss(0, 0.008)), 4) for m in months],
        [round(max(0.01, 0.07 - 0.002 * m + random.gauss(0, 0.005)), 4) for m in months],
        [round(max(0.005, 0.04 - 0.001 * m + random.gauss(0, 0.003)), 4) for m in months],
        [round(max(0.002, 0.025 - 0.0008 * m + random.gauss(0, 0.002)), 4) for m in months],
    ]

    # LTV calculation per tier: avg_monthly_price / churn_rate
    ltvs = [round(tier_prices[ti] / (sum(churn_rates[ti]) / 24), 0) for ti in range(4)]

    # Current month snapshot (month 24)
    cur_counts = [tier_counts[ti][23] for ti in range(4)]
    cur_rev = monthly_rev[23]
    total_customers = sum(cur_counts)

    # Revenue SVG stacked area (simplified as lines per tier)
    svg_w, svg_h = 540, 150
    colors = ["#38bdf8", "#34d399", "#a78bfa", "#f59e0b"]
    rev_lines = ""
    for ti in range(4):
        tier_rev = [tier_counts[ti][m] * tier_prices[ti] for m in range(24)]
        max_r = max(monthly_rev) or 1
        pts = " ".join(
            f"{20 + int(m * (svg_w - 40) / 23)},{int(svg_h - 10 - tier_rev[m] / max_r * (svg_h - 20))}"
            for m in range(24)
        )
        rev_lines += f"<polyline points='{pts}' fill='none' stroke='{colors[ti]}' stroke-width='2'/>"

    # Total revenue line
    max_r = max(monthly_rev) or 1
    total_pts = " ".join(
        f"{20 + int(m * (svg_w - 40) / 23)},{int(svg_h - 10 - monthly_rev[m] / max_r * (svg_h - 20))}"
        for m in range(24)
    )
    rev_lines += f"<polyline points='{total_pts}' fill='none' stroke='#f8fafc' stroke-width='2.5' stroke-dasharray='5,3'/>"

    # Churn lines SVG
    churn_svg = ""
    for ti in range(4):
        max_c = max(churn_rates[0]) or 0.01
        pts = " ".join(
            f"{20 + int(m * 460 / 23)},{int(130 - churn_rates[ti][m] / max_c * 110)}"
            for m in range(24)
        )
        churn_svg += f"<polyline points='{pts}' fill='none' stroke='{colors[ti]}' stroke-width='2'/>"

    # Tier donut: pie chart approximation as SVG arcs
    total_c = sum(cur_counts) or 1
    donut_parts = ""
    angle = 0.0
    cx, cy, r_out, r_in = 90, 90, 75, 42
    for ti, cnt in enumerate(cur_counts):
        frac = cnt / total_c
        sweep = frac * 2 * math.pi
        x1 = cx + r_out * math.sin(angle)
        y1 = cy - r_out * math.cos(angle)
        x2 = cx + r_out * math.sin(angle + sweep)
        y2 = cy - r_out * math.cos(angle + sweep)
        ix1 = cx + r_in * math.sin(angle)
        iy1 = cy - r_in * math.cos(angle)
        ix2 = cx + r_in * math.sin(angle + sweep)
        iy2 = cy - r_in * math.cos(angle + sweep)
        large = 1 if sweep > math.pi else 0
        donut_parts += (
            f"<path d='M {ix1:.1f} {iy1:.1f} L {x1:.1f} {y1:.1f} "
            f"A {r_out} {r_out} 0 {large} 1 {x2:.1f} {y2:.1f} "
            f"L {ix2:.1f} {iy2:.1f} A {r_in} {r_in} 0 {large} 0 {ix1:.1f} {iy1:.1f} Z' "
            f"fill='{colors[ti]}' opacity='0.88'/>"
        )
        angle += sweep

    # Optimization recommendation: upsell score per customer
    # Score = (next_tier_ltv - cur_ltv) / cur_price * usage_saturation
    upsell_scores = []
    for ti in range(len(TIERS) - 1):
        sat = round(random.uniform(0.65, 0.98), 3)  # usage saturation
        delta_ltv = ltvs[ti + 1] - ltvs[ti]
        score = round(delta_ltv / tier_prices[ti] * sat * 100, 1)
        upsell_scores.append({"from": TIERS[ti]["name"], "to": TIERS[ti+1]["name"],
                               "saturation": sat, "upsell_score": score})

    upsell_rows = "".join(
        f"<tr><td style='color:{colors[i]}'>{u['from']}</td>"
        f"<td style='color:{colors[i+1]}'>{u['to']}</td>"
        f"<td><div style='background:#0f172a;border-radius:4px;height:10px;width:100%'>"
        f"<div style='background:{colors[i]};width:{min(int(u['saturation']*100),100)}%;height:10px;border-radius:4px'></div></div>"
        f"<span style='font-size:0.78rem'>{int(u['saturation']*100)}%</span></td>"
        f"<td style='color:#f8fafc;font-weight:700'>{u['upsell_score']}</td></tr>"
        for i, u in enumerate(upsell_scores)
    )

    tier_rows = "".join(
        f"<tr><td style='color:{colors[ti]};font-weight:600'>{TIERS[ti]['name']}</td>"
        f"<td>${TIERS[ti]['price']:,}/mo</td>"
        f"<td>{cur_counts[ti]}</td>"
        f"<td>${cur_counts[ti]*TIERS[ti]['price']:,}</td>"
        f"<td>${int(ltvs[ti]):,}</td></tr>"
        for ti in range(4)
    )

    return f"""<!DOCTYPE html><html><head><title>Subscription Tier Optimizer</title>
<meta charset='utf-8'>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui,sans-serif}}
h1{{color:#C74634;padding:18px 24px 0;margin:0;font-size:1.6rem}}
.subtitle{{color:#94a3b8;padding:2px 26px 14px;font-size:0.92rem}}
.grid{{display:flex;flex-wrap:wrap}}
.card{{background:#1e293b;padding:20px;margin:10px;border-radius:10px;flex:1;min-width:280px}}
h2{{color:#38bdf8;font-size:1.05rem;margin:0 0 12px}}
.stat-row{{display:flex;gap:16px;flex-wrap:wrap;margin-bottom:10px}}
.stat{{background:#0f172a;border-radius:7px;padding:10px 16px;min-width:100px}}
.stat .label{{font-size:0.75rem;color:#64748b;margin-bottom:3px}}
.stat .value{{font-size:1.25rem;color:#f8fafc;font-weight:700}}
table{{width:100%;border-collapse:collapse;font-size:0.88rem}}
th{{color:#64748b;text-align:left;padding:5px 8px;border-bottom:1px solid #334155}}
td{{padding:6px 8px;border-bottom:1px solid #1e293b}}
.legend{{display:flex;gap:14px;font-size:0.8rem;margin-top:6px;flex-wrap:wrap}}
.dot{{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:4px}}
</style></head>
<body>
<h1>Subscription Tier Optimizer</h1>
<div class='subtitle'>OCI Robot Cloud · 4-tier SaaS model · LTV/churn optimization · port {PORT}</div>
<div class='grid'>

  <div class='card' style='min-width:520px'>
    <h2>Monthly Recurring Revenue (24-month trajectory)</h2>
    <svg width='{svg_w}' height='{svg_h}' style='background:#0f172a;border-radius:6px'>
      <line x1='20' y1='10' x2='20' y2='{svg_h-10}' stroke='#334155'/>
      <line x1='20' y1='{svg_h-10}' x2='{svg_w-20}' y2='{svg_h-10}' stroke='#334155'/>
      {rev_lines}
    </svg>
    <div class='legend'>
      {''.join(f"<span><span class='dot' style='background:{colors[ti]}'></span>{TIERS[ti]['name']}</span>" for ti in range(4))}
      <span><span class='dot' style='background:#f8fafc'></span>Total</span>
    </div>
    <div class='stat-row' style='margin-top:12px'>
      <div class='stat'><div class='label'>Current MRR</div><div class='value' style='color:#34d399'>${cur_rev:,}</div></div>
      <div class='stat'><div class='label'>Total Customers</div><div class='value'>{total_customers}</div></div>
    </div>
  </div>

  <div class='card' style='min-width:220px;max-width:260px'>
    <h2>Customer Mix</h2>
    <svg width='180' height='180'>
      {donut_parts}
      <text x='90' y='86' font-size='13' fill='#94a3b8' text-anchor='middle'>Total</text>
      <text x='90' y='104' font-size='18' fill='#f8fafc' font-weight='bold' text-anchor='middle'>{total_customers}</text>
    </svg>
    <div class='legend' style='flex-direction:column;gap:4px'>
      {''.join(f"<span><span class='dot' style='background:{colors[ti]}'></span>{TIERS[ti]['name']}: {cur_counts[ti]}</span>" for ti in range(4))}
    </div>
  </div>

  <div class='card' style='min-width:480px'>
    <h2>Tier Performance Snapshot</h2>
    <table>
      <thead><tr><th>Tier</th><th>Price</th><th>Customers</th><th>MRR</th><th>Est. LTV</th></tr></thead>
      <tbody>{tier_rows}</tbody>
    </table>
  </div>

  <div class='card' style='min-width:480px'>
    <h2>Churn Rate by Tier (24 months)</h2>
    <svg width='500' height='140' style='background:#0f172a;border-radius:6px'>
      <line x1='20' y1='10' x2='20' y2='130' stroke='#334155'/>
      <line x1='20' y1='130' x2='480' y2='130' stroke='#334155'/>
      {churn_svg}
    </svg>
    <div class='legend'>
      {''.join(f"<span><span class='dot' style='background:{colors[ti]}'></span>{TIERS[ti]['name']}</span>" for ti in range(4))}
    </div>
  </div>

  <div class='card' style='min-width:440px'>
    <h2>Upsell Opportunity Score</h2>
    <table>
      <thead><tr><th>From</th><th>To</th><th>Usage Saturation</th><th>Upsell Score</th></tr></thead>
      <tbody>{upsell_rows}</tbody>
    </table>
    <div style='font-size:0.78rem;color:#475569;margin-top:8px'>Score = (ΔLTV / current_price) × usage_saturation × 100</div>
  </div>

</div>
<div style='padding:8px 24px 20px;color:#475569;font-size:0.78rem'>
  Model: S-curve growth · Churn: tier-stratified decay · LTV = avg_price / monthly_churn
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Subscription Tier Optimizer")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return build_html()

    @app.get("/health")
    def health():
        return {"status": "ok", "port": PORT, "service": "subscription_tier_optimizer"}

    @app.get("/tiers")
    def tiers():
        return {"tiers": TIERS}

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(build_html().encode())
    def log_message(self, *a):
        pass

if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
