"""Customer Satisfaction Tracker — FastAPI port 8787"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8787

def build_html():
    random.seed(42)

    # NPS scores over 12 months
    months = ["Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec","Jan","Feb","Mar"]
    nps_scores = [round(42 + 18 * math.sin(i * math.pi / 6) + random.uniform(-4, 4), 1) for i in range(12)]
    csat_scores = [round(78 + 12 * math.cos(i * math.pi / 8) + random.uniform(-3, 3), 1) for i in range(12)]

    # CSAT line chart
    svg_w, svg_h = 600, 140
    def norm(vals, lo, hi): return [int((v - lo) / (hi - lo) * (svg_h - 20) ) for v in vals]
    nps_norm = norm(nps_scores, 20, 75)
    csat_norm = norm(csat_scores, 60, 100)
    step = svg_w / 11

    nps_pts = " ".join(f"{i * step:.1f},{svg_h - nps_norm[i] - 10}" for i in range(12))
    csat_pts = " ".join(f"{i * step:.1f},{svg_h - csat_norm[i] - 10}" for i in range(12))

    # Circles on NPS line
    nps_dots = "".join(f'<circle cx="{i * step:.1f}" cy="{svg_h - nps_norm[i] - 10}" r="4" fill="#a78bfa"/>' for i in range(12))
    csat_dots = "".join(f'<circle cx="{i * step:.1f}" cy="{svg_h - csat_norm[i] - 10}" r="4" fill="#34d399"/>' for i in range(12))
    month_labels = "".join(f'<text x="{i * step:.1f}" y="{svg_h + 12}" fill="#64748b" font-size="9" text-anchor="middle">{months[i]}</text>' for i in range(12))

    # Satisfaction distribution donut (SVG arc)
    promoters = random.randint(48, 58)
    passives = random.randint(22, 30)
    detractors = 100 - promoters - passives
    total_responses = random.randint(2800, 3500)
    current_nps = round(nps_scores[-1], 1)
    current_csat = round(csat_scores[-1], 1)
    avg_resolution = round(random.uniform(3.2, 5.8), 1)

    def arc_path(cx, cy, r, start_deg, end_deg):
        s = math.radians(start_deg - 90)
        e = math.radians(end_deg - 90)
        x1, y1 = cx + r * math.cos(s), cy + r * math.sin(s)
        x2, y2 = cx + r * math.cos(e), cy + r * math.sin(e)
        lg = 1 if (end_deg - start_deg) > 180 else 0
        return f"M {cx} {cy} L {x1:.2f} {y1:.2f} A {r} {r} 0 {lg} 1 {x2:.2f} {y2:.2f} Z"

    p_end = promoters * 3.6
    pa_end = (promoters + passives) * 3.6
    donut = (
        f'<path d="{arc_path(80, 80, 70, 0, p_end)}" fill="#22c55e" opacity="0.85"/>'
        f'<path d="{arc_path(80, 80, 70, p_end, pa_end)}" fill="#facc15" opacity="0.85"/>'
        f'<path d="{arc_path(80, 80, 70, pa_end, 360)}" fill="#ef4444" opacity="0.85"/>'
        f'<circle cx="80" cy="80" r="40" fill="#1e293b"/>'
        f'<text x="80" y="76" fill="#e2e8f0" font-size="14" font-weight="bold" text-anchor="middle">{current_nps}</text>'
        f'<text x="80" y="92" fill="#94a3b8" font-size="9" text-anchor="middle">NPS</text>'
    )

    # Recent feedback table
    products = ["OCI Robot Cloud", "Isaac Sim Pipeline", "GR00T Fine-Tune", "DAgger SDK", "Cosmos SDG", "LIBERO Eval"]
    random.seed()
    rows = ""
    for p in products:
        score = round(random.uniform(3.4, 5.0), 1)
        responses = random.randint(80, 420)
        trend = round(random.uniform(-0.3, 0.5), 2)
        trend_color = "#22c55e" if trend > 0 else "#ef4444"
        trend_sym = "▲" if trend > 0 else "▼"
        stars = int(score)
        star_str = "★" * stars + "☆" * (5 - stars)
        rows += f"<tr><td>{p}</td><td style='color:#fbbf24'>{star_str}</td><td>{score}/5.0</td><td>{responses}</td><td style='color:{trend_color}'>{trend_sym} {abs(trend)}</td></tr>"

    return f"""<!DOCTYPE html><html><head><title>Customer Satisfaction Tracker</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui;padding:20px}}
h1{{color:#C74634;margin-bottom:4px}}h2{{color:#38bdf8;margin-top:0}}
.card{{background:#1e293b;padding:20px;margin:10px 0;border-radius:8px}}
.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:10px 0}}
.metric{{background:#0f172a;padding:14px;border-radius:6px;text-align:center}}
.metric .val{{font-size:2em;font-weight:bold;color:#38bdf8}}
.metric .lbl{{font-size:0.8em;color:#94a3b8;margin-top:4px}}
.two-col{{display:grid;grid-template-columns:200px 1fr;gap:20px;align-items:start}}
table{{width:100%;border-collapse:collapse;font-size:0.9em}}
th{{background:#0f172a;color:#94a3b8;padding:8px 12px;text-align:left}}
td{{padding:8px 12px;border-bottom:1px solid #334155}}
.legend{{display:flex;gap:16px;font-size:0.8em;margin-top:8px}}
.dot{{width:10px;height:10px;border-radius:50%;display:inline-block;margin-right:4px}}
</style></head>
<body>
<h1>Customer Satisfaction Tracker</h1>
<p style='color:#64748b;margin-top:0'>Port {PORT} &nbsp;|&nbsp; NPS + CSAT monitoring across OCI Robot Cloud product lines</p>

<div class="grid">
  <div class="metric"><div class="val">{current_nps}</div><div class="lbl">Current NPS Score</div></div>
  <div class="metric"><div class="val">{current_csat}%</div><div class="lbl">CSAT (This Month)</div></div>
  <div class="metric"><div class="val">{total_responses:,}</div><div class="lbl">Total Responses (12mo)</div></div>
  <div class="metric"><div class="val">{promoters}%</div><div class="lbl">Promoters</div></div>
  <div class="metric"><div class="val">{passives}%</div><div class="lbl">Passives</div></div>
  <div class="metric"><div class="val">{detractors}%</div><div class="lbl">Detractors</div></div>
</div>

<div class="card">
  <h2>NPS &amp; CSAT Trends — Last 12 Months</h2>
  <svg width="100%" viewBox="0 0 {svg_w} {svg_h + 20}" preserveAspectRatio="xMidYMid meet">
    <rect width="{svg_w}" height="{svg_h + 20}" fill="#0f172a" rx="4"/>
    <polyline points="{nps_pts}" fill="none" stroke="#a78bfa" stroke-width="2"/>
    <polyline points="{csat_pts}" fill="none" stroke="#34d399" stroke-width="2"/>
    {nps_dots}{csat_dots}{month_labels}
  </svg>
  <div class="legend">
    <span><span class="dot" style="background:#a78bfa"></span>NPS (0–100 scale)</span>
    <span><span class="dot" style="background:#34d399"></span>CSAT (%)</span>
  </div>
</div>

<div class="card">
  <h2>Satisfaction Distribution &amp; Resolution Time</h2>
  <div class="two-col">
    <svg width="160" height="160" viewBox="0 0 160 160">{donut}</svg>
    <div>
      <div style="margin-bottom:12px">
        <div style="color:#94a3b8;font-size:0.85em">Avg Resolution Time</div>
        <div style="font-size:1.8em;font-weight:bold;color:#38bdf8">{avg_resolution} days</div>
      </div>
      <div style="display:flex;flex-direction:column;gap:8px">
        <div style="display:flex;align-items:center;gap:8px">
          <div style="width:12px;height:12px;background:#22c55e;border-radius:2px"></div>
          <span>Promoters (9–10): <strong>{promoters}%</strong></span>
        </div>
        <div style="display:flex;align-items:center;gap:8px">
          <div style="width:12px;height:12px;background:#facc15;border-radius:2px"></div>
          <span>Passives (7–8): <strong>{passives}%</strong></span>
        </div>
        <div style="display:flex;align-items:center;gap:8px">
          <div style="width:12px;height:12px;background:#ef4444;border-radius:2px"></div>
          <span>Detractors (0–6): <strong>{detractors}%</strong></span>
        </div>
      </div>
    </div>
  </div>
</div>

<div class="card">
  <h2>Product Satisfaction Breakdown</h2>
  <table>
    <thead><tr><th>Product</th><th>Stars</th><th>Score</th><th>Responses</th><th>MoM Trend</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Customer Satisfaction Tracker")
    @app.get("/", response_class=HTMLResponse)
    def index(): return build_html()
    @app.get("/health")
    def health(): return {"status": "ok", "port": PORT}
    @app.get("/summary")
    def summary():
        return {
            "nps": round(random.uniform(52, 68), 1),
            "csat_pct": round(random.uniform(78, 92), 1),
            "promoters_pct": random.randint(48, 58),
            "total_responses": random.randint(2800, 3500),
            "avg_resolution_days": round(random.uniform(3.2, 5.8), 1)
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
