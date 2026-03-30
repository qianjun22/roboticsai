"""Partner Referral Tracker — FastAPI port 8797"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8797

def build_html():
    random.seed(2026)

    partners = [
        {"name": "Intrinsic",    "tier": "Platinum", "referrals": 47, "arr": 840000,  "conv": 0.68},
        {"name": "Agility",      "tier": "Gold",     "referrals": 31, "arr": 520000,  "conv": 0.55},
        {"name": "Apptronik",    "tier": "Gold",     "referrals": 28, "arr": 410000,  "conv": 0.50},
        {"name": "Boston Dyn.",  "tier": "Platinum", "referrals": 52, "arr": 1100000, "conv": 0.71},
        {"name": "Sanctuary AI", "tier": "Silver",   "referrals": 14, "arr": 190000,  "conv": 0.38},
        {"name": "Figure AI",    "tier": "Gold",     "referrals": 22, "arr": 360000,  "conv": 0.47},
        {"name": "1X Tech",      "tier": "Silver",   "referrals": 9,  "arr": 95000,   "conv": 0.33},
        {"name": "Neura Rob.",   "tier": "Bronze",   "referrals": 5,  "arr": 42000,   "conv": 0.22},
    ]

    tier_color = {"Platinum": "#e2e8f0", "Gold": "#fbbf24", "Silver": "#94a3b8", "Bronze": "#c2825c"}

    # Bar chart — referrals per partner
    max_ref = max(p["referrals"] for p in partners)
    bar_w = 52
    bars_svg = ""
    for i, p in enumerate(partners):
        bh = int(p["referrals"] / max_ref * 110)
        bx = 30 + i * (bar_w + 8)
        color = {"Platinum": "#C74634", "Gold": "#fbbf24", "Silver": "#94a3b8", "Bronze": "#c2825c"}[p["tier"]]
        bars_svg += (
            f'<rect x="{bx}" y="{130-bh}" width="{bar_w}" height="{bh}" fill="{color}" rx="3" opacity="0.9"/>'
            f'<text x="{bx + bar_w//2}" y="145" text-anchor="middle" fill="#94a3b8" font-size="8">{p["name"][:8]}</text>'
            f'<text x="{bx + bar_w//2}" y="{125-bh}" text-anchor="middle" fill="#e2e8f0" font-size="9">{p["referrals"]}</text>'
        )

    # Monthly pipeline trend (last 12 months)
    months = ["Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec","Jan","Feb","Mar"]
    pipeline = []
    v = 280000
    for _ in months:
        v = v * (1 + random.uniform(0.01, 0.09))
        pipeline.append(v)
    max_p = max(pipeline)
    trend_pts = []
    fill_pts = ["30,130"]
    for i, val in enumerate(pipeline):
        tx = 30 + i * 44
        ty = 130 - int(val / max_p * 110)
        trend_pts.append(f"{tx},{ty}")
        fill_pts.append(f"{tx},{ty}")
    fill_pts.append(f"{30 + 11*44},130")
    trend_line = " ".join(trend_pts)
    fill_poly = " ".join(fill_pts)

    # Conversion funnel
    funnel_stages = [
        ("Leads", 208, "#C74634"),
        ("Qualified", 147, "#ef4444"),
        ("Demo", 98, "#f97316"),
        ("Proposal", 61, "#fbbf24"),
        ("Closed", 38, "#22c55e"),
    ]
    funnel_svg = ""
    max_fv = funnel_stages[0][1]
    for i, (stage, val, color) in enumerate(funnel_stages):
        fw = int(val / max_fv * 260)
        fx = 150 - fw // 2
        fy = 20 + i * 38
        funnel_svg += (
            f'<rect x="{fx}" y="{fy}" width="{fw}" height="28" fill="{color}" rx="3" opacity="0.85"/>'
            f'<text x="150" y="{fy+19}" text-anchor="middle" fill="#0f172a" font-size="11" font-weight="700">{stage}: {val}</text>'
        )

    # ARR donut (approximate with arcs)
    total_arr = sum(p["arr"] for p in partners)
    donut_paths = ""
    angle = -math.pi / 2
    colors_donut = ["#C74634","#fbbf24","#38bdf8","#a78bfa","#34d399","#f97316","#94a3b8","#c2825c"]
    cx_d, cy_d, r_out, r_in = 160, 150, 110, 60
    for i, p in enumerate(partners):
        sweep = 2 * math.pi * p["arr"] / total_arr
        a1, a2 = angle, angle + sweep
        # outer arc
        x1o = cx_d + r_out * math.cos(a1)
        y1o = cy_d + r_out * math.sin(a1)
        x2o = cx_d + r_out * math.cos(a2)
        y2o = cy_d + r_out * math.sin(a2)
        # inner arc (reversed)
        x1i = cx_d + r_in * math.cos(a2)
        y1i = cy_d + r_in * math.sin(a2)
        x2i = cx_d + r_in * math.cos(a1)
        y2i = cy_d + r_in * math.sin(a1)
        laf = 1 if sweep > math.pi else 0
        color = colors_donut[i % len(colors_donut)]
        donut_paths += (
            f'<path d="M{x1o:.1f},{y1o:.1f} A{r_out},{r_out} 0 {laf},1 {x2o:.1f},{y2o:.1f} '
            f'L{x1i:.1f},{y1i:.1f} A{r_in},{r_in} 0 {laf},0 {x2i:.1f},{y2i:.1f} Z" '
            f'fill="{color}" opacity="0.88"/>'
        )
        angle += sweep

    total_arr_m = total_arr / 1e6
    total_ref = sum(p["referrals"] for p in partners)
    avg_conv = sum(p["conv"] for p in partners) / len(partners)
    top = max(partners, key=lambda p: p["arr"])

    metrics = [
        ("Total ARR", f"${total_arr_m:.2f}M"),
        ("Total Referrals", str(total_ref)),
        ("Avg Conversion", f"{avg_conv*100:.1f}%"),
        ("Active Partners", str(len(partners))),
        ("Top Partner", top["name"]),
        ("Pipeline MoM", "+7.2%"),
    ]
    metric_cards = "".join(
        f'<div class="metric"><div class="mlabel">{lbl}</div><div class="mval">{val}</div></div>'
        for lbl, val in metrics
    )

    partner_rows = "".join(
        f'<tr><td>{p["name"]}</td>'
        f'<td style="color:{tier_color[p["tier"]]}">{p["tier"]}</td>'
        f'<td>{p["referrals"]}</td>'
        f'<td>${p["arr"]/1000:.0f}K</td>'
        f'<td>{p["conv"]*100:.0f}%</td></tr>'
        for p in sorted(partners, key=lambda p: p["arr"], reverse=True)
    )

    return f"""<!DOCTYPE html><html><head><title>Partner Referral Tracker</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui;padding:20px}}
h1{{color:#C74634;margin:0 0 4px 0}}h2{{color:#38bdf8;font-size:14px;margin:6px 0}}
.card{{background:#1e293b;padding:16px;margin:10px 0;border-radius:8px;border:1px solid #334155}}
.grid2{{display:grid;grid-template-columns:1fr 1fr;gap:10px}}
.grid3{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px}}
.metrics{{display:flex;flex-wrap:wrap;gap:8px;margin:10px 0}}
.metric{{background:#0f172a;border:1px solid #334155;border-radius:6px;padding:10px 16px;min-width:120px}}
.mlabel{{font-size:11px;color:#94a3b8}}.mval{{font-size:20px;font-weight:700;color:#38bdf8}}
.sub{{font-size:12px;color:#64748b;margin-bottom:12px}}
table{{width:100%;border-collapse:collapse;font-size:13px}}
th{{color:#94a3b8;text-align:left;padding:6px 8px;border-bottom:1px solid #334155}}
td{{padding:6px 8px;border-bottom:1px solid #1e293b}}
tr:hover td{{background:#0f172a}}
</style></head>
<body>
<h1>Partner Referral Tracker</h1>
<p class="sub">Port {PORT} — OCI Robot Cloud partner pipeline, ARR attribution, conversion funnels</p>
<div class="metrics">{metric_cards}</div>
<div class="grid3">
<div class="card" style="grid-column:span 2">
<h2>Referrals by Partner</h2>
<svg width="100%" height="160" viewBox="0 0 520 160" style="display:block">
  <rect width="520" height="160" fill="#0f172a" rx="6"/>
  {bars_svg}
  <line x1="20" y1="130" x2="500" y2="130" stroke="#475569" stroke-width="1"/>
</svg>
</div>
<div class="card">
<h2>ARR Attribution</h2>
<svg width="100%" height="310" viewBox="0 0 320 310" style="display:block;margin:auto">
  <rect width="320" height="310" fill="#0f172a" rx="6"/>
  {donut_paths}
  <text x="160" y="145" text-anchor="middle" fill="#e2e8f0" font-size="13" font-weight="700">${total_arr_m:.1f}M</text>
  <text x="160" y="162" text-anchor="middle" fill="#94a3b8" font-size="10">Total ARR</text>
</svg>
</div>
</div>
<div class="grid2">
<div class="card">
<h2>Pipeline Trend (12 months)</h2>
<svg width="100%" height="150" viewBox="0 0 520 150" style="display:block">
  <rect width="520" height="150" fill="#0f172a" rx="6"/>
  <defs><linearGradient id="tg" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0%" stop-color="#38bdf8" stop-opacity="0.4"/>
    <stop offset="100%" stop-color="#38bdf8" stop-opacity="0.02"/>
  </linearGradient></defs>
  <polygon points="{fill_poly}" fill="url(#tg)"/>
  <polyline points="{trend_line}" fill="none" stroke="#38bdf8" stroke-width="2.5"/>
  <line x1="30" y1="130" x2="510" y2="130" stroke="#475569" stroke-width="1"/>
  {''.join(f'<text x="{30+i*44}" y="145" text-anchor="middle" fill="#64748b" font-size="8">{m}</text>' for i,m in enumerate(months))}
</svg>
</div>
<div class="card">
<h2>Conversion Funnel</h2>
<svg width="100%" height="210" viewBox="0 0 300 210" style="display:block;margin:auto">
  <rect width="300" height="210" fill="#0f172a" rx="6"/>
  {funnel_svg}
</svg>
</div>
</div>
<div class="card">
<h2>Partner Leaderboard</h2>
<table>
<tr><th>Partner</th><th>Tier</th><th>Referrals</th><th>ARR</th><th>Conv%</th></tr>
{partner_rows}
</table>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Partner Referral Tracker")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return build_html()

    @app.get("/health")
    def health():
        return {"status": "ok", "port": PORT}

    @app.get("/partners")
    def partners():
        return {
            "partners": [
                {"name": "Boston Dyn.",  "tier": "Platinum", "referrals": 52, "arr_usd": 1100000, "conversion": 0.71},
                {"name": "Intrinsic",    "tier": "Platinum", "referrals": 47, "arr_usd": 840000,  "conversion": 0.68},
                {"name": "Agility",      "tier": "Gold",     "referrals": 31, "arr_usd": 520000,  "conversion": 0.55},
                {"name": "Apptronik",    "tier": "Gold",     "referrals": 28, "arr_usd": 410000,  "conversion": 0.50},
                {"name": "Figure AI",    "tier": "Gold",     "referrals": 22, "arr_usd": 360000,  "conversion": 0.47},
                {"name": "Sanctuary AI", "tier": "Silver",   "referrals": 14, "arr_usd": 190000,  "conversion": 0.38},
                {"name": "1X Tech",      "tier": "Silver",   "referrals": 9,  "arr_usd": 95000,   "conversion": 0.33},
                {"name": "Neura Rob.",   "tier": "Bronze",   "referrals": 5,  "arr_usd": 42000,   "conversion": 0.22},
            ]
        }

    @app.get("/summary")
    def summary():
        return {
            "total_arr_usd": 3557000,
            "total_referrals": 208,
            "avg_conversion_pct": 48.0,
            "active_partners": 8,
            "pipeline_mom_pct": 7.2,
        }

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
