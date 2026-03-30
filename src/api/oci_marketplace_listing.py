"""OCI Marketplace Listing — FastAPI port 8803"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8803

random.seed(42)

def build_html():
    # Simulate OCI Marketplace listing metrics
    days = 30
    day_labels = list(range(1, days + 1))

    # Daily installs — growing trend with noise
    installs = [int(12 + 3 * d + 8 * math.sin(d * 0.4) + random.uniform(0, 6)) for d in day_labels]
    cumulative = []
    s = 0
    for v in installs:
        s += v
        cumulative.append(s)

    # Revenue per day (USD)
    revenue = [round(v * (2.4 + 0.3 * math.sin(d * 0.2)), 2) for d, v in zip(day_labels, installs)]
    total_revenue = sum(revenue)
    total_installs = cumulative[-1]
    avg_daily = total_installs / days

    # Ratings distribution
    ratings = {5: 187, 4: 63, 3: 21, 2: 8, 1: 4}
    total_reviews = sum(ratings.values())
    avg_rating = sum(k * v for k, v in ratings.items()) / total_reviews

    # Region breakdown
    regions = [
        ("us-ashburn-1",   int(total_installs * 0.32)),
        ("us-phoenix-1",   int(total_installs * 0.19)),
        ("eu-frankfurt-1", int(total_installs * 0.17)),
        ("ap-tokyo-1",     int(total_installs * 0.13)),
        ("ap-sydney-1",    int(total_installs * 0.09)),
        ("ca-toronto-1",   int(total_installs * 0.06)),
        ("other",          int(total_installs * 0.04)),
    ]

    # SVG line chart: daily installs (width=700, height=160)
    max_inst = max(installs)
    pts_inst = []
    for i, v in enumerate(installs):
        x = 20 + i * (660 / (days - 1))
        y = 10 + (1 - v / max_inst) * 130
        pts_inst.append((x, y))
    polyline_inst = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts_inst)
    area_inst = f"20,140 " + polyline_inst + f" {pts_inst[-1][0]:.1f},140"

    # SVG line chart: cumulative installs
    max_cum = cumulative[-1]
    pts_cum = []
    for i, v in enumerate(cumulative):
        x = 20 + i * (660 / (days - 1))
        y = 10 + (1 - v / max_cum) * 130
        pts_cum.append((x, y))
    polyline_cum = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts_cum)

    # Rating stars SVG
    def star_bar(count, max_count, color):
        w = int(count / max_count * 180)
        return f'<rect x="0" y="0" width="{w}" height="10" fill="{color}" rx="2"/>'

    rating_rows = ""
    bar_colors = ["#4ade80", "#86efac", "#fbbf24", "#fb923c", "#f87171"]
    for (stars, count), color in zip(sorted(ratings.items(), reverse=True), bar_colors):
        pct = count / total_reviews * 100
        rating_rows += (
            f'<tr><td style="text-align:right;padding-right:8px">{"★" * stars}</td>'
            f'<td><svg width="180" height="10"><rect width="180" height="10" fill="#334155" rx="2"/>'
            f'{star_bar(count, max(ratings.values()), color)}'
            f'</svg></td>'
            f'<td style="padding-left:8px;color:#94a3b8">{count} ({pct:.1f}%)</td></tr>'
        )

    # Region pie (SVG arc)
    pie_svgs = ""
    pie_colors = ["#38bdf8", "#818cf8", "#f59e0b", "#4ade80", "#fb923c", "#e879f9", "#94a3b8"]
    angle = -math.pi / 2
    cx, cy, r = 90, 90, 75
    for (region, count), color in zip(regions, pie_colors):
        frac = count / total_installs
        sweep = frac * 2 * math.pi
        x1 = cx + r * math.cos(angle)
        y1 = cy + r * math.sin(angle)
        angle += sweep
        x2 = cx + r * math.cos(angle)
        y2 = cy + r * math.sin(angle)
        large = 1 if sweep > math.pi else 0
        pie_svgs += (
            f'<path d="M {cx} {cy} L {x1:.2f} {y1:.2f} A {r} {r} 0 {large} 1 {x2:.2f} {y2:.2f} Z"'
            f' fill="{color}"><title>{region}: {count}</title></path>'
        )

    legend_items = "".join(
        f'<div style="font-size:0.78em;margin:2px 0"><span style="display:inline-block;width:10px;height:10px;background:{c};border-radius:2px;margin-right:4px"></span>{reg} ({cnt})'
        f'</div>'
        for (reg, cnt), c in zip(regions, pie_colors)
    )

    return f"""<!DOCTYPE html><html><head><title>OCI Marketplace Listing</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui}}
h1{{color:#C74634;padding:20px 20px 0;margin:0}}
h2{{color:#38bdf8;margin:0 0 12px}}
.card{{background:#1e293b;padding:20px;margin:10px;border-radius:8px;display:inline-block;vertical-align:top}}
.wide{{width:calc(100% - 60px);display:block}}
.stat{{display:inline-block;margin:0 24px 0 0}}
.stat .val{{font-size:2em;font-weight:bold;color:#38bdf8}}
.stat .lbl{{font-size:0.75em;color:#64748b;text-transform:uppercase}}
.badge{{display:inline-block;padding:3px 10px;border-radius:12px;font-size:0.8em;background:#0f4c2a;color:#4ade80;margin-right:6px}}
table{{border-collapse:collapse}}
td{{padding:4px 6px;vertical-align:middle}}
.stars{{color:#f59e0b}}
</style></head>
<body>
<h1>OCI Marketplace Listing</h1>
<div style="padding:0 10px 10px">
  <span class="badge">Port 8803</span>
  <span class="badge">OCI Robot Cloud SDK</span>
  <span class="badge">v2.12.0</span>
  <span class="badge">Published</span>
</div>

<div class="card">
  <div class="stat"><div class="val">{total_installs}</div><div class="lbl">Total Installs (30d)</div></div>
  <div class="stat"><div class="val">${total_revenue:,.0f}</div><div class="lbl">Revenue (30d)</div></div>
  <div class="stat"><div class="val">{avg_daily:.1f}</div><div class="lbl">Avg Daily Installs</div></div>
  <div class="stat"><div class="val">{avg_rating:.2f} ★</div><div class="lbl">Avg Rating</div></div>
  <div class="stat"><div class="val">{total_reviews}</div><div class="lbl">Total Reviews</div></div>
</div>

<div class="card wide">
  <h2>Daily Installs (Last 30 Days)</h2>
  <svg width="100%" viewBox="0 0 700 160" xmlns="http://www.w3.org/2000/svg">
    <line x1="20" y1="140" x2="680" y2="140" stroke="#334155" stroke-width="1"/>
    <line x1="20" y1="10" x2="20" y2="140" stroke="#334155" stroke-width="1"/>
    <polygon points="{area_inst}" fill="#38bdf820"/>
    <polyline points="{polyline_inst}" fill="none" stroke="#38bdf8" stroke-width="2"/>
    <text x="22" y="15" font-size="9" fill="#475569">peak={max_inst}</text>
    <text x="22" y="155" font-size="9" fill="#475569">Day 1</text>
    <text x="640" y="155" font-size="9" fill="#475569">Day 30</text>
  </svg>
</div>

<div class="card wide">
  <h2>Cumulative Installs</h2>
  <svg width="100%" viewBox="0 0 700 160" xmlns="http://www.w3.org/2000/svg">
    <line x1="20" y1="140" x2="680" y2="140" stroke="#334155" stroke-width="1"/>
    <line x1="20" y1="10" x2="20" y2="140" stroke="#334155" stroke-width="1"/>
    <polyline points="{polyline_cum}" fill="none" stroke="#4ade80" stroke-width="2"/>
    <text x="{pts_cum[-1][0]-40:.0f}" y="{pts_cum[-1][1]-8:.0f}" font-size="9" fill="#4ade80">{max_cum} total</text>
    <text x="22" y="155" font-size="9" fill="#475569">Day 1</text>
    <text x="640" y="155" font-size="9" fill="#475569">Day 30</text>
  </svg>
</div>

<div class="card" style="width:260px">
  <h2>Ratings</h2>
  <table>{rating_rows}</table>
  <div style="margin-top:12px;font-size:1.4em;color:#f59e0b">{avg_rating:.2f} ★</div>
  <div style="font-size:0.75em;color:#64748b">{total_reviews} reviews</div>
</div>

<div class="card" style="width:300px">
  <h2>Installs by Region</h2>
  <div style="display:flex;align-items:center;gap:16px">
    <svg width="180" height="180" viewBox="0 0 180 180" xmlns="http://www.w3.org/2000/svg">
      {pie_svgs}
    </svg>
    <div>{legend_items}</div>
  </div>
</div>

</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="OCI Marketplace Listing")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return build_html()

    @app.get("/health")
    def health():
        return {"status": "ok", "port": PORT}

    @app.get("/metrics")
    def metrics():
        return {
            "listing": "OCI Robot Cloud SDK",
            "version": "2.12.0",
            "total_installs_30d": random.randint(1200, 1400),
            "revenue_30d_usd": round(random.uniform(3200, 3800), 2),
            "avg_rating": round(random.uniform(4.5, 4.8), 2),
            "total_reviews": 283,
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
