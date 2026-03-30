"""Partner Billing Optimizer — FastAPI port 8765"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8765

PARTNERS = [
    {"name": "Apptronik",       "tier": "Enterprise", "base_usd": 42000, "robots": 18, "overage_rate": 0.12},
    {"name": "Agility Robotics", "tier": "Enterprise", "base_usd": 38500, "robots": 14, "overage_rate": 0.10},
    {"name": "Boston Dynamics",  "tier": "Enterprise", "base_usd": 55000, "robots": 24, "overage_rate": 0.09},
    {"name": "Unitree",          "tier": "Growth",     "base_usd": 18000, "robots": 9,  "overage_rate": 0.15},
    {"name": "Fourier Intel.",   "tier": "Growth",     "base_usd": 14500, "robots": 7,  "overage_rate": 0.14},
    {"name": "1X Technologies",  "tier": "Growth",     "base_usd": 12800, "robots": 6,  "overage_rate": 0.16},
    {"name": "Kepler Robotics",  "tier": "Starter",    "base_usd": 5200,  "robots": 3,  "overage_rate": 0.20},
    {"name": "Clone Robotics",   "tier": "Starter",    "base_usd": 4800,  "robots": 2,  "overage_rate": 0.22},
]

def compute_billing(partner, month_idx):
    """Simulate monthly billing with usage curves and overage."""
    random.seed(hash(partner["name"]) + month_idx)
    # Usage grows with a sigmoid + noise
    growth = 1 / (1 + math.exp(-0.4 * (month_idx - 5)))
    usage_factor = 0.6 + 0.7 * growth + random.gauss(0, 0.06)
    included_calls = partner["robots"] * 10000  # calls/month included
    actual_calls = int(included_calls * usage_factor)
    overage_calls = max(0, actual_calls - included_calls)
    overage_charge = overage_calls * partner["overage_rate"] / 1000.0
    gpu_hours = partner["robots"] * usage_factor * 22.4
    gpu_cost = gpu_hours * 3.50  # $3.50/hr A100
    total = partner["base_usd"] + overage_charge
    margin = (total - gpu_cost) / total if total > 0 else 0
    return {
        "total_usd": round(total, 2),
        "gpu_cost": round(gpu_cost, 2),
        "overage_usd": round(overage_charge, 2),
        "usage_factor": round(usage_factor, 3),
        "margin": round(margin, 3),
        "actual_calls": actual_calls,
    }

def build_html():
    months = ["Oct", "Nov", "Dec", "Jan", "Feb", "Mar"]
    n_months = len(months)
    CURRENT_MONTH = 5  # March = index 5

    # Current month billing for all partners
    current_bills = [compute_billing(p, CURRENT_MONTH) for p in PARTNERS]
    total_arr_monthly = sum(b["total_usd"] for b in current_bills)
    total_gpu_cost = sum(b["gpu_cost"] for b in current_bills)
    avg_margin = sum(b["margin"] for b in current_bills) / len(current_bills)
    total_overage = sum(b["overage_usd"] for b in current_bills)

    # Monthly revenue trend (stacked by tier)
    ent_partners = [p for p in PARTNERS if p["tier"] == "Enterprise"]
    growth_partners = [p for p in PARTNERS if p["tier"] == "Growth"]
    start_partners = [p for p in PARTNERS if p["tier"] == "Starter"]
    ent_rev   = [sum(compute_billing(p, m)["total_usd"] for p in ent_partners)   for m in range(n_months)]
    growth_rev = [sum(compute_billing(p, m)["total_usd"] for p in growth_partners) for m in range(n_months)]
    start_rev  = [sum(compute_billing(p, m)["total_usd"] for p in start_partners)  for m in range(n_months)]
    total_rev  = [ent_rev[m] + growth_rev[m] + start_rev[m] for m in range(n_months)]

    # SVG stacked area chart — monthly revenue
    sw, sh = 560, 200
    rev_max = max(total_rev) * 1.08
    def rx(i): return 30 + i / (n_months - 1) * (sw - 50)
    def ry(v): return sh - 20 - v / rev_max * (sh - 35)
    def stack_pts(vals, prev_vals):
        fwd = " ".join(f"{rx(i):.1f},{ry(vals[i]):.1f}" for i in range(n_months))
        bwd = " ".join(f"{rx(i):.1f},{ry(prev_vals[i]):.1f}" for i in range(n_months - 1, -1, -1))
        return fwd + " " + bwd
    z = [0] * n_months
    s1 = [start_rev[i] for i in range(n_months)]
    s2 = [start_rev[i] + growth_rev[i] for i in range(n_months)]
    s3 = [start_rev[i] + growth_rev[i] + ent_rev[i] for i in range(n_months)]
    area1 = stack_pts(s1, z)
    area2 = stack_pts(s2, s1)
    area3 = stack_pts(s3, s2)
    month_labels = "".join(
        f'<text x="{rx(i):.1f}" y="{sh-4}" font-size="9" fill="#475569" text-anchor="middle">{months[i]}</text>'
        for i in range(n_months)
    )
    rev_labels = "".join(
        f'<text x="{rx(i):.1f}" y="{ry(total_rev[i])-5:.1f}" font-size="8" fill="#e2e8f0" text-anchor="middle">${total_rev[i]/1000:.0f}k</text>'
        for i in range(n_months)
    )

    # SVG margin sparklines per partner
    spark_rows = ""
    for idx, (p, b) in enumerate(zip(PARTNERS, current_bills)):
        margins = [compute_billing(p, m)["margin"] * 100 for m in range(n_months)]
        spw, sph = 100, 28
        mmin, mmax = min(margins), max(margins)
        def spx(i): return i / (n_months - 1) * spw
        def spy(v): return sph - (v - mmin) / (mmax - mmin + 1e-9) * sph
        spts = " ".join(f"{spx(i):.1f},{spy(margins[i]):.1f}" for i in range(n_months))
        tier_colors = {"Enterprise": "#C74634", "Growth": "#f97316", "Starter": "#38bdf8"}
        tc = tier_colors.get(p["tier"], "#94a3b8")
        margin_color = "#22c55e" if b["margin"] > 0.55 else ("#eab308" if b["margin"] > 0.35 else "#ef4444")
        spark_rows += (
            f'<tr>'
            f'<td style="color:#f8fafc;font-weight:600">{p["name"]}</td>'
            f'<td><span style="background:{tc}22;color:{tc};padding:2px 8px;border-radius:4px;font-size:0.72rem">{p["tier"]}</span></td>'
            f'<td style="color:#38bdf8">{p["robots"]}</td>'
            f'<td style="color:#e2e8f0">${b["total_usd"]:,.0f}</td>'
            f'<td style="color:#f97316">${b["gpu_cost"]:,.0f}</td>'
            f'<td style="color:#ef4444">${b["overage_usd"]:,.0f}</td>'
            f'<td style="color:{margin_color};font-weight:700">{b["margin"]*100:.1f}%</td>'
            f'<td><svg width="{spw}" height="{sph}"><polyline points="{spts}" fill="none" stroke="{tc}" stroke-width="1.5"/></svg></td>'
            f'</tr>'
        )

    # Optimization recommendations
    recs = []
    for p, b in zip(PARTNERS, current_bills):
        if b["margin"] < 0.35:
            recs.append(("high", p["name"], f"Margin {b['margin']*100:.1f}% below 35% — recommend tier upgrade or rate renegotiation"))
        elif b["overage_usd"] > 2000:
            recs.append(("medium", p["name"], f"Overage ${b['overage_usd']:,.0f}/mo — offer higher-tier bundle at ${b['total_usd']*1.12:,.0f}/mo"))
        elif b["margin"] > 0.70:
            recs.append(("low", p["name"], f"Margin {b['margin']*100:.1f}% — healthy; consider volume discount to increase robot count"))
    rec_sev_color = {"high": "#ef4444", "medium": "#f97316", "low": "#22c55e"}
    rec_html = "".join(
        f'<div style="padding:8px 12px;margin:4px 0;border-left:3px solid {rec_sev_color[sev]};background:#0f172a;border-radius:4px">'
        f'<span style="color:{rec_sev_color[sev]};font-weight:700;font-size:0.75rem;text-transform:uppercase">{sev}</span> '
        f'<span style="color:#94a3b8;font-size:0.82rem">{name}:</span> '
        f'<span style="font-size:0.82rem">{msg}</span></div>'
        for sev, name, msg in recs
    ) or '<div style="color:#22c55e;padding:8px">All partners within optimal billing range.</div>'

    return f"""<!DOCTYPE html><html><head><title>Partner Billing Optimizer</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui,sans-serif}}
h1{{color:#C74634;padding:20px 20px 0;margin:0;font-size:1.6rem}}
.subtitle{{color:#94a3b8;padding:4px 20px 16px;font-size:0.85rem}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:0}}
.card{{background:#1e293b;padding:20px;margin:10px;border-radius:10px;border:1px solid #334155}}
.card-wide{{background:#1e293b;padding:20px;margin:10px;border-radius:10px;border:1px solid #334155;grid-column:span 2}}
h2{{color:#38bdf8;margin:0 0 12px;font-size:1rem;text-transform:uppercase;letter-spacing:.05em}}
.kpi-row{{display:flex;gap:16px;flex-wrap:wrap;margin-bottom:8px}}
.kpi{{background:#0f172a;border-radius:8px;padding:12px 18px;min-width:120px}}
.kpi-val{{font-size:1.6rem;font-weight:700;color:#f8fafc}}
.kpi-label{{font-size:0.72rem;color:#64748b;text-transform:uppercase;letter-spacing:.05em}}
table{{width:100%;border-collapse:collapse;font-size:0.82rem}}
td,th{{padding:7px 10px;text-align:left;border-bottom:1px solid #1e293b}}
th{{color:#64748b;font-weight:600;text-transform:uppercase;font-size:0.72rem;background:#0f172a}}
tr:hover td{{background:#0f172a40}}
</style></head>
<body>
<h1>Partner Billing Optimizer</h1>
<div class="subtitle">OCI Robot Cloud — 8-Partner Revenue Intelligence Dashboard | Port {PORT}</div>
<div class="grid">

<div class="card-wide">
<div class="kpi-row">
  <div class="kpi"><div class="kpi-val">${total_arr_monthly:,.0f}</div><div class="kpi-label">Monthly Revenue</div></div>
  <div class="kpi"><div class="kpi-val">${total_arr_monthly*12:,.0f}</div><div class="kpi-label">ARR Run Rate</div></div>
  <div class="kpi"><div class="kpi-val">${total_gpu_cost:,.0f}</div><div class="kpi-label">GPU Cost/Mo</div></div>
  <div class="kpi"><div class="kpi-val" style="color:#22c55e">{avg_margin*100:.1f}%</div><div class="kpi-label">Avg Margin</div></div>
  <div class="kpi"><div class="kpi-val" style="color:#f97316">${total_overage:,.0f}</div><div class="kpi-label">Overage Revenue</div></div>
  <div class="kpi"><div class="kpi-val">{sum(p['robots'] for p in PARTNERS)}</div><div class="kpi-label">Total Robots</div></div>
</div>
</div>

<div class="card">
<h2>Monthly Revenue Trend (Stacked by Tier)</h2>
<svg width="{sw}" height="{sh}" style="display:block">
  <rect width="{sw}" height="{sh}" fill="#0f172a" rx="6"/>
  <polygon points="{area1}" fill="#38bdf830"/>
  <polygon points="{area2}" fill="#f9731630"/>
  <polygon points="{area3}" fill="#C7463430"/>
  <polyline points="{' '.join(f'{rx(i):.1f},{ry(s1[i]):.1f}' for i in range(n_months))}" fill="none" stroke="#38bdf8" stroke-width="1.5"/>
  <polyline points="{' '.join(f'{rx(i):.1f},{ry(s2[i]):.1f}' for i in range(n_months))}" fill="none" stroke="#f97316" stroke-width="1.5"/>
  <polyline points="{' '.join(f'{rx(i):.1f},{ry(s3[i]):.1f}' for i in range(n_months))}" fill="none" stroke="#C74634" stroke-width="2"/>
  {month_labels}
  {rev_labels}
</svg>
<div style="font-size:0.72rem;color:#475569;margin-top:6px">
  <span style="color:#C74634">&#9644;</span> Enterprise &nbsp;
  <span style="color:#f97316">&#9644;</span> Growth &nbsp;
  <span style="color:#38bdf8">&#9644;</span> Starter
</div>
</div>

<div class="card">
<h2>Optimization Recommendations</h2>
{rec_html}
</div>

<div class="card-wide">
<h2>Partner Billing Detail — March 2026</h2>
<table>
<tr><th>Partner</th><th>Tier</th><th>Robots</th><th>Billed</th><th>GPU Cost</th><th>Overage</th><th>Margin</th><th>6-Mo Trend</th></tr>
{spark_rows}
</table>
</div>

</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Partner Billing Optimizer")
    @app.get("/", response_class=HTMLResponse)
    def index(): return build_html()
    @app.get("/health")
    def health(): return {"status": "ok", "port": PORT}
    @app.get("/billing/{partner_name}")
    def get_partner_billing(partner_name: str, month: int = 5):
        p = next((x for x in PARTNERS if x["name"].lower() == partner_name.lower()), None)
        if not p:
            return {"error": "partner not found", "available": [x["name"] for x in PARTNERS]}
        return {"partner": p["name"], "month": month, **compute_billing(p, month)}
    @app.get("/summary")
    def summary():
        bills = [compute_billing(p, 5) for p in PARTNERS]
        return {
            "total_monthly_usd": round(sum(b["total_usd"] for b in bills), 2),
            "total_gpu_cost_usd": round(sum(b["gpu_cost"] for b in bills), 2),
            "avg_margin_pct": round(sum(b["margin"] for b in bills) / len(bills) * 100, 2),
            "partner_count": len(PARTNERS),
            "total_robots": sum(p["robots"] for p in PARTNERS),
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
