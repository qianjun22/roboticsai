"""Partner ROI Report v2 — FastAPI port 8719"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8719

PARTNERS = [
    {"name": "Boston Dynamics",  "tier": "Platinum", "contract": 480_000, "months": 14},
    {"name": "Agility Robotics", "tier": "Gold",     "contract": 310_000, "months": 9},
    {"name": "Apptronik",        "tier": "Gold",     "contract": 275_000, "months": 11},
    {"name": "Figure AI",        "tier": "Silver",   "contract": 190_000, "months": 6},
    {"name": "1X Technologies",  "tier": "Silver",   "contract": 145_000, "months": 8},
    {"name": "Sanctuary AI",     "tier": "Bronze",   "contract": 95_000,  "months": 5},
]

TIER_COLOR = {
    "Platinum": "#e2e8f0",
    "Gold":     "#fbbf24",
    "Silver":   "#94a3b8",
    "Bronze":   "#c2855a",
}

def build_html():
    random.seed(7)

    # Compute ROI metrics per partner
    enriched = []
    for p in PARTNERS:
        infra_cost = p["contract"] * random.uniform(0.28, 0.38)
        support_cost = p["contract"] * random.uniform(0.08, 0.14)
        total_cost = infra_cost + support_cost
        gross_margin = p["contract"] - total_cost
        roi_pct = (gross_margin / total_cost) * 100
        # Pipeline: demos run, models deployed, avg latency
        demos = int(p["months"] * random.uniform(8, 18))
        deployments = int(demos * random.uniform(0.4, 0.75))
        avg_latency = random.uniform(180, 340)
        enriched.append({
            **p,
            "infra": infra_cost,
            "support": support_cost,
            "gross_margin": gross_margin,
            "roi_pct": roi_pct,
            "demos": demos,
            "deployments": deployments,
            "avg_latency_ms": avg_latency,
        })

    total_arr = sum(p["contract"] for p in enriched)
    total_margin = sum(p["gross_margin"] for p in enriched)
    avg_roi = sum(p["roi_pct"] for p in enriched) / len(enriched)
    total_deployments = sum(p["deployments"] for p in enriched)

    # SVG donut chart — ARR by partner
    donut_cx, donut_cy, donut_r, donut_inner = 130, 130, 100, 55
    total_arr_f = float(total_arr)
    arc_paths = ""
    legend_items = ""
    angle = -math.pi / 2
    donut_colors = ["#C74634", "#38bdf8", "#a78bfa", "#34d399", "#fb923c", "#f472b6"]
    for i, p in enumerate(enriched):
        frac = p["contract"] / total_arr_f
        sweep = frac * 2 * math.pi
        x1 = donut_cx + donut_r * math.cos(angle)
        y1 = donut_cy + donut_r * math.sin(angle)
        x2 = donut_cx + donut_r * math.cos(angle + sweep)
        y2 = donut_cy + donut_r * math.sin(angle + sweep)
        xi1 = donut_cx + donut_inner * math.cos(angle)
        yi1 = donut_cy + donut_inner * math.sin(angle)
        xi2 = donut_cx + donut_inner * math.cos(angle + sweep)
        yi2 = donut_cy + donut_inner * math.sin(angle + sweep)
        large = 1 if sweep > math.pi else 0
        color = donut_colors[i % len(donut_colors)]
        path = (f'M {x1:.1f} {y1:.1f} A {donut_r} {donut_r} 0 {large} 1 {x2:.1f} {y2:.1f} '
                f'L {xi2:.1f} {yi2:.1f} A {donut_inner} {donut_inner} 0 {large} 0 {xi1:.1f} {yi1:.1f} Z')
        arc_paths += f'<path d="{path}" fill="{color}" opacity="0.9"/>'
        legend_items += (f'<div style="display:flex;align-items:center;margin:3px 0">'
                         f'<div style="width:10px;height:10px;border-radius:2px;background:{color};margin-right:6px;flex-shrink:0"></div>'
                         f'<span style="font-size:0.75rem;color:#cbd5e1">{p["name"]}</span>'
                         f'<span style="margin-left:auto;font-size:0.75rem;color:#94a3b8">${p["contract"]//1000}k</span>'
                         f'</div>')
        angle += sweep

    # SVG bar chart — ROI % per partner
    bar_h = 18
    bar_gap = 6
    bar_max_w = 220
    max_roi = max(p["roi_pct"] for p in enriched)
    roi_bars = ""
    for i, p in enumerate(enriched):
        bw = int((p["roi_pct"] / max_roi) * bar_max_w)
        y = i * (bar_h + bar_gap)
        color = donut_colors[i % len(donut_colors)]
        roi_bars += (f'<rect x="0" y="{y}" width="{bw}" height="{bar_h}" fill="{color}" rx="3" opacity="0.85"/>'
                     f'<text x="{bw + 4}" y="{y + bar_h - 4}" fill="#e2e8f0" font-size="10">{p["roi_pct"]:.0f}%</text>'
                     f'<text x="-4" y="{y + bar_h - 4}" fill="#94a3b8" font-size="9" text-anchor="end">{p["name"].split()[0]}</text>')
    roi_svg_h = len(enriched) * (bar_h + bar_gap)

    # Monthly revenue trend — sine + linear growth
    months_back = 12
    trend_w = 480
    trend_h = 100
    step_x = trend_w / (months_back - 1)
    trend_points = []
    for m in range(months_back):
        rev = total_arr_f / 12 * (0.7 + 0.3 * m / months_back) + 15000 * math.sin(m * 0.8) + random.gauss(0, 8000)
        px = int(m * step_x) + 40
        py = trend_h - int((rev / (total_arr_f / 12 * 1.1)) * (trend_h - 10)) + 5
        trend_points.append(f"{px},{py}")
    trend_polyline = " ".join(trend_points)

    # Partner rows table
    table_rows = ""
    for i, p in enumerate(enriched):
        tier_c = TIER_COLOR[p["tier"]]
        table_rows += (
            f'<tr style="border-bottom:1px solid #1e293b">'
            f'<td style="padding:8px 12px;color:{donut_colors[i % len(donut_colors)]};font-weight:600">{p["name"]}</td>'
            f'<td style="padding:8px 12px"><span style="color:{tier_c};font-size:0.78rem">{p["tier"]}</span></td>'
            f'<td style="padding:8px 12px;text-align:right">${p["contract"]:,}</td>'
            f'<td style="padding:8px 12px;text-align:right;color:#22c55e">{p["roi_pct"]:.1f}%</td>'
            f'<td style="padding:8px 12px;text-align:right">{p["demos"]}</td>'
            f'<td style="padding:8px 12px;text-align:right">{p["deployments"]}</td>'
            f'<td style="padding:8px 12px;text-align:right;color:#38bdf8">{p["avg_latency_ms"]:.0f} ms</td>'
            f'</tr>'
        )

    return f"""<!DOCTYPE html><html><head><title>Partner ROI Report v2</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui;padding:20px}}
h1{{color:#C74634;margin:0 0 4px 0;font-size:1.6rem}}
h2{{color:#38bdf8;font-size:1rem;margin:0 0 12px 0}}
h3{{color:#94a3b8;font-size:0.82rem;margin:0 0 10px 0;text-transform:uppercase;letter-spacing:.06em}}
.grid{{display:grid;grid-template-columns:280px 1fr;gap:12px;margin-bottom:12px}}
.grid3{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;margin-bottom:12px}}
.card{{background:#1e293b;padding:20px;border-radius:8px}}
.card.wide{{grid-column:1/-1}}
.stat .val{{font-size:1.6rem;font-weight:700;color:#f8fafc}}
.stat .lbl{{font-size:0.7rem;color:#64748b;text-transform:uppercase;margin-top:2px}}
table{{width:100%;border-collapse:collapse;font-size:0.82rem}}
th{{text-align:left;padding:6px 12px;color:#64748b;font-weight:500;border-bottom:2px solid #334155;font-size:0.72rem;text-transform:uppercase}}
th.r{{text-align:right}}
tr:hover{{background:#263548}}
</style></head>
<body>
<h1>Partner ROI Report v2</h1>
<h2>OCI Robot Cloud — Design Partner Performance &nbsp; Q1 2026</h2>

<div class="grid3">
  <div class="card stat"><div class="val">${total_arr/1e6:.2f}M</div><div class="lbl">Total ARR</div></div>
  <div class="card stat"><div class="val" style="color:#22c55e">{avg_roi:.0f}%</div><div class="lbl">Avg Partner ROI</div></div>
  <div class="card stat"><div class="val">{total_deployments}</div><div class="lbl">Total Model Deployments</div></div>
</div>

<div class="grid">
  <div class="card">
    <h3>ARR Breakdown</h3>
    <svg width="260" height="260">
      {arc_paths}
      <text x="{donut_cx}" y="{donut_cy - 6}" fill="#f8fafc" font-size="13" font-weight="700" text-anchor="middle">${total_arr//1000}k</text>
      <text x="{donut_cx}" y="{donut_cy + 12}" fill="#64748b" font-size="9" text-anchor="middle">total ARR</text>
    </svg>
    {legend_items}
  </div>
  <div class="card">
    <h3>ROI % by Partner</h3>
    <svg width="320" height="{roi_svg_h + 10}">
      <g transform="translate(70, 0)">
        {roi_bars}
      </g>
    </svg>
    <div style="margin-top:16px">
      <h3>Monthly Revenue Trend</h3>
      <svg width="530" height="{trend_h + 24}">
        <line x1="40" y1="{trend_h + 5}" x2="{40 + trend_w}" y2="{trend_h + 5}" stroke="#334155" stroke-width="1"/>
        <polyline points="{trend_polyline}" fill="none" stroke="#C74634" stroke-width="2.5"/>
        {''.join(f'<circle cx="{trend_points[m].split(",")[0]}" cy="{trend_points[m].split(",")[1]}" r="3" fill="#C74634"/>' for m in range(months_back))}
        <text x="40" y="{trend_h + 20}" fill="#475569" font-size="8">Mar 2025</text>
        <text x="{40 + trend_w - 10}" y="{trend_h + 20}" fill="#475569" font-size="8" text-anchor="end">Feb 2026</text>
      </svg>
    </div>
  </div>
</div>

<div class="card">
  <h3>Partner Detail</h3>
  <table>
    <thead><tr>
      <th>Partner</th><th>Tier</th><th class="r">ARR</th><th class="r">ROI</th>
      <th class="r">Demos</th><th class="r">Deployed</th><th class="r">Avg Latency</th>
    </tr></thead>
    <tbody>{table_rows}</tbody>
  </table>
</div>

<div style="font-size:0.72rem;color:#475569;margin-top:10px">Port {PORT} — OCI Robot Cloud CRM — Data refreshed 2026-03-30</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Partner ROI Report v2")

    @app.get("/", response_class=HTMLResponse)
    def index(): return build_html()

    @app.get("/health")
    def health(): return {"status": "ok", "port": PORT}

    @app.get("/summary")
    def summary():
        return {
            "port": PORT,
            "total_arr": sum(p["contract"] for p in PARTNERS),
            "partners": len(PARTNERS),
            "tiers": {t: sum(1 for p in PARTNERS if p["tier"] == t) for t in ["Platinum", "Gold", "Silver", "Bronze"]},
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
