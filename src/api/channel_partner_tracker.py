"""Channel Partner Tracker — FastAPI port 8733"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8733

def build_html():
    random.seed(7)

    partners = [
        {"name": "Mujin Robotics",   "region": "APAC",   "tier": "Gold",   "pipeline": 4.2,  "closed": 1.8,  "demos": 14, "health": 0.88},
        {"name": "Intrinsic (Alphabet)","region": "NA",   "tier": "Platinum","pipeline": 7.1, "closed": 3.2,  "demos": 22, "health": 0.93},
        {"name": "Wandercraft",        "region": "EMEA",  "tier": "Silver", "pipeline": 1.9,  "closed": 0.6,  "demos": 7,  "health": 0.61},
        {"name": "Machina Labs",       "region": "NA",    "tier": "Gold",   "pipeline": 3.5,  "closed": 1.1,  "demos": 11, "health": 0.74},
        {"name": "Doosan Robotics",    "region": "APAC",  "tier": "Silver", "pipeline": 2.8,  "closed": 0.9,  "demos": 9,  "health": 0.68},
        {"name": "Ready Robotics",     "region": "NA",    "tier": "Gold",   "pipeline": 3.0,  "closed": 1.4,  "demos": 13, "health": 0.80},
        {"name": "Kinova Robotics",    "region": "NA",    "tier": "Silver", "pipeline": 1.4,  "closed": 0.4,  "demos": 5,  "health": 0.55},
        {"name": "Franka Emika",       "region": "EMEA",  "tier": "Gold",   "pipeline": 2.6,  "closed": 1.0,  "demos": 10, "health": 0.77},
    ]

    total_pipeline = round(sum(p["pipeline"] for p in partners), 1)
    total_closed   = round(sum(p["closed"]   for p in partners), 1)
    total_demos    = sum(p["demos"]    for p in partners)
    avg_health     = round(sum(p["health"] for p in partners) / len(partners), 2)

    tier_colors = {"Platinum": "#e879f9", "Gold": "#fbbf24", "Silver": "#94a3b8"}
    region_colors = {"NA": "#38bdf8", "EMEA": "#4ade80", "APAC": "#fb923c"}

    # Partner table rows
    partner_rows = ""
    for p in partners:
        tc = tier_colors.get(p["tier"], "#fff")
        rc = region_colors.get(p["region"], "#fff")
        hw = int(p["health"] * 80)
        hcolor = f"hsl({int(p['health']*120)},60%,45%)"
        partner_rows += (
            f'<tr><td><b>{p["name"]}</b></td>'
            f'<td><span style="color:{rc}">{p["region"]}</span></td>'
            f'<td><span style="color:{tc}">{p["tier"]}</span></td>'
            f'<td>${p["pipeline"]}M</td>'
            f'<td>${p["closed"]}M</td>'
            f'<td>{p["demos"]}</td>'
            f'<td><div style="background:#0f172a;border-radius:4px;width:100px;height:8px">'
            f'<div style="width:{hw}px;height:100%;background:{hcolor};border-radius:4px"></div></div>'
            f'<span style="font-size:0.78rem;color:{hcolor}">{int(p["health"]*100)}%</span></td></tr>'
        )

    # Monthly pipeline trend (12 months, sine wave growth)
    months = ["Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec","Jan","Feb","Mar"]
    pipeline_trend = [
        round(12 + 6 * math.sin(i / 3.5 + 1.0) + i * 0.8 + random.gauss(0, 0.5), 2)
        for i in range(12)
    ]
    closed_trend = [
        round(max(0.5, v * 0.42 + random.gauss(0, 0.3)), 2)
        for v in pipeline_trend
    ]

    pt_min, pt_max = min(pipeline_trend), max(pipeline_trend)
    def pt_y(v): return 100 - int(85 * (v - pt_min) / (pt_max - pt_min + 1e-9))
    pipe_pts = " ".join(f"{int(35 * i)},{pt_y(pipeline_trend[i])}" for i in range(12))

    ct_min, ct_max = min(closed_trend), max(closed_trend)
    def ct_y(v): return 100 - int(85 * (v - ct_min) / (ct_max - ct_min + 1e-9))
    close_pts = " ".join(f"{int(35 * i)},{ct_y(closed_trend[i])}" for i in range(12))

    # Region donut (SVG arc)
    region_totals = {}
    for p in partners:
        region_totals[p["region"]] = region_totals.get(p["region"], 0) + p["pipeline"]
    grand = sum(region_totals.values())
    cx, cy, r = 110, 100, 70
    arcs = ""
    start_angle = -math.pi / 2
    for reg, val in region_totals.items():
        sweep = 2 * math.pi * val / grand
        end_angle = start_angle + sweep
        x1 = cx + r * math.cos(start_angle)
        y1 = cy + r * math.sin(start_angle)
        x2 = cx + r * math.cos(end_angle)
        y2 = cy + r * math.sin(end_angle)
        large = 1 if sweep > math.pi else 0
        col = region_colors.get(reg, "#aaa")
        arcs += f'<path d="M{cx},{cy} L{x1:.1f},{y1:.1f} A{r},{r} 0 {large},1 {x2:.1f},{y2:.1f} Z" fill="{col}" opacity="0.85"/>'
        mid_angle = start_angle + sweep / 2
        lx = cx + (r + 22) * math.cos(mid_angle)
        ly = cy + (r + 22) * math.sin(mid_angle)
        arcs += f'<text x="{lx:.0f}" y="{ly:.0f}" fill="{col}" font-size="10" text-anchor="middle">{reg}\n${val:.1f}M</text>'
        start_angle = end_angle

    # Demo activity heatmap (8 partners x 4 weeks)
    heatmap_cells = ""
    cell_w, cell_h = 30, 22
    for pi, p in enumerate(partners):
        for wk in range(4):
            val = random.randint(0, 5)
            opacity = val / 5.0
            x = 5 + wk * (cell_w + 3)
            y = 5 + pi * (cell_h + 3)
            heatmap_cells += (
                f'<rect x="{x}" y="{y}" width="{cell_w}" height="{cell_h}" '
                f'fill="#C74634" opacity="{opacity:.2f}" rx="3"/>'
                f'<text x="{x + cell_w//2}" y="{y + 14}" fill="#e2e8f0" '
                f'font-size="9" text-anchor="middle">{val}</text>'
            )
        heatmap_cells += (
            f'<text x="140" y="{5 + pi*(cell_h+3)+14}" fill="#94a3b8" font-size="9">{p["name"][:16]}</text>'
        )

    return f"""<!DOCTYPE html>
<html><head><title>Channel Partner Tracker</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui,sans-serif}}
h1{{color:#C74634;margin:0;padding:20px 24px 8px;font-size:1.6rem}}
h2{{color:#38bdf8;font-size:1.05rem;margin:0 0 12px}}
.card{{background:#1e293b;padding:20px;margin:12px;border-radius:10px;box-shadow:0 2px 8px #0006}}
.grid2{{display:grid;grid-template-columns:1fr 1fr;gap:0}}
.grid4{{display:grid;grid-template-columns:repeat(4,1fr);gap:0}}
.stat{{background:#0f172a;border-radius:8px;padding:14px 18px;margin:6px}}
.stat-val{{font-size:1.8rem;font-weight:700;color:#f0abfc}}
.stat-lbl{{font-size:0.78rem;color:#94a3b8;margin-top:4px}}
table{{width:100%;border-collapse:collapse;font-size:0.85rem}}
th{{background:#0f172a;color:#38bdf8;padding:8px 6px;text-align:left;border-bottom:1px solid #334155}}
td{{padding:7px 6px;border-bottom:1px solid #1e293b;color:#e2e8f0;vertical-align:middle}}
tr:hover td{{background:#162032}}
.badge{{display:inline-block;padding:2px 8px;border-radius:12px;font-size:0.75rem;background:#0ea5e920;color:#38bdf8;border:1px solid #38bdf840}}
svg text{{font-family:system-ui}}
</style></head>
<body>
<h1>Channel Partner Tracker</h1>
<p style="color:#64748b;margin:0 24px 4px;font-size:0.85rem">OCI Robot Cloud partner pipeline, health scores, and demo activity — Port {PORT}</p>

<div class="card">
  <div class="grid4">
    <div class="stat">
      <div class="stat-val">${total_pipeline}M</div>
      <div class="stat-lbl">Total Pipeline</div>
    </div>
    <div class="stat">
      <div class="stat-val" style="color:#4ade80">${total_closed}M</div>
      <div class="stat-lbl">Closed (FY26)</div>
    </div>
    <div class="stat">
      <div class="stat-val" style="color:#38bdf8">{total_demos}</div>
      <div class="stat-lbl">Product Demos YTD</div>
    </div>
    <div class="stat">
      <div class="stat-val" style="color:#fbbf24">{int(avg_health*100)}%</div>
      <div class="stat-lbl">Avg Partner Health</div>
    </div>
  </div>
  <div style="margin:6px">
    <span class="badge">8 Active Partners</span>&nbsp;
    <span class="badge">3 Regions</span>&nbsp;
    <span class="badge">FY2026 Q1</span>&nbsp;
    <span class="badge">Win Rate: {round(total_closed/total_pipeline*100,1)}%</span>
  </div>
</div>

<div class="card">
  <h2>Partner Pipeline &amp; Health</h2>
  <table>
    <tr><th>Partner</th><th>Region</th><th>Tier</th><th>Pipeline</th><th>Closed</th><th>Demos</th><th>Health Score</th></tr>
    {partner_rows}
  </table>
</div>

<div class="grid2">
  <div class="card">
    <h2>Pipeline vs Closed (12-Month Trend)</h2>
    <svg width="400" height="130" viewBox="0 0 400 130">
      <rect width="400" height="130" fill="#0f172a" rx="6"/>
      <polyline points="{pipe_pts}" fill="none" stroke="#C74634" stroke-width="2" stroke-dasharray="0"/>
      <polyline points="{close_pts}" fill="none" stroke="#4ade80" stroke-width="2"/>
      <circle cx="8" cy="12" r="5" fill="#C74634"/>
      <text x="16" y="16" fill="#C74634" font-size="9">Pipeline</text>
      <circle cx="70" cy="12" r="5" fill="#4ade80"/>
      <text x="78" y="16" fill="#4ade80" font-size="9">Closed</text>
      {''.join(f'<text x="{int(35*i)}" y="118" fill="#475569" font-size="8" text-anchor="middle">{months[i]}</text>' for i in range(12))}
    </svg>
  </div>

  <div class="card">
    <h2>Pipeline by Region</h2>
    <svg width="260" height="210" viewBox="0 0 260 210">
      <rect width="260" height="210" fill="#0f172a" rx="6"/>
      {arcs}
      <circle cx="110" cy="100" r="32" fill="#0f172a"/>
      <text x="110" y="98" fill="#e2e8f0" font-size="11" text-anchor="middle">Total</text>
      <text x="110" y="112" fill="#f0abfc" font-size="12" text-anchor="middle" font-weight="700">${grand:.1f}M</text>
    </svg>
  </div>
</div>

<div class="card">
  <h2>Demo Activity Heatmap (Last 4 Weeks)</h2>
  <p style="font-size:0.8rem;color:#64748b;margin:0 0 8px">Number of demos per partner per week. Darker = more activity.</p>
  <svg width="320" height="230" viewBox="0 0 320 230">
    <rect width="320" height="230" fill="#0f172a" rx="6"/>
    {''.join(f'<text x="{5 + wk*33 + 15}" y="202" fill="#475569" font-size="9" text-anchor="middle">W{wk+1}</text>' for wk in range(4))}
    {heatmap_cells}
  </svg>
</div>

</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Channel Partner Tracker")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return build_html()

    @app.get("/health")
    def health():
        return {"status": "ok", "port": PORT, "service": "channel_partner_tracker"}

    @app.get("/partners")
    def partners():
        random.seed()
        return {
            "total_pipeline_M": round(random.uniform(26, 30), 1),
            "total_closed_M": round(random.uniform(10, 12), 1),
            "total_demos_ytd": random.randint(88, 105),
            "avg_health_pct": round(random.uniform(72, 80), 1),
            "active_partners": 8,
            "regions": ["NA", "EMEA", "APAC"],
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
