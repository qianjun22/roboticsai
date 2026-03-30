"""Product Launch Tracker — FastAPI port 8789"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8789

PRODUCTS = [
    {"name": "OCI Robot Cloud v2",     "target": 90,  "status": "On Track",   "color": "#22c55e"},
    {"name": "GR00T Fine-Tune SDK",    "target": 75,  "status": "At Risk",    "color": "#f59e0b"},
    {"name": "Isaac Sim Connector",    "target": 85,  "status": "On Track",   "color": "#22c55e"},
    {"name": "Cosmos World Model API", "target": 60,  "status": "Delayed",    "color": "#ef4444"},
    {"name": "Jetson Edge Runtime",    "target": 95,  "status": "Launched",   "color": "#38bdf8"},
    {"name": "DAgger Auto-Retrain",    "target": 70,  "status": "At Risk",    "color": "#f59e0b"},
    {"name": "Multi-Robot Scheduler",  "target": 80,  "status": "On Track",   "color": "#22c55e"},
    {"name": "Sim-to-Real Validator",  "target": 55,  "status": "Delayed",    "color": "#ef4444"},
]

def build_html():
    random.seed(7)
    num_weeks = 24

    # Simulate cumulative launch readiness % for each product over 24 weeks
    # Each product follows an S-curve toward its target
    def s_curve(week, target, shift):
        x = (week - shift) / 4.0
        return target / (1 + math.exp(-x))

    # Burndown chart data: total open launch tasks
    ideal_burndown = [400 - 400 * w / num_weeks for w in range(num_weeks + 1)]
    actual_burndown = [400]
    for w in range(1, num_weeks + 1):
        drop = random.uniform(12, 22) if w < 18 else random.uniform(5, 10)
        actual_burndown.append(max(0, actual_burndown[-1] - drop))

    # Bar chart for product readiness (current week = 20)
    current_week = 20
    readiness = [min(p["target"], s_curve(current_week, p["target"], random.uniform(8, 14))) for p in PRODUCTS]

    # SVG burndown chart
    BW, BH = 560, 160
    pad = 24
    def bx(w): return pad + w * (BW - 2 * pad) / num_weeks
    def by(v): return BH - pad - v / 400 * (BH - 2 * pad)

    ideal_pts  = " ".join(f"{bx(w):.1f},{by(v):.1f}" for w, v in enumerate(ideal_burndown))
    actual_pts = " ".join(f"{bx(w):.1f},{by(v):.1f}" for w, v in enumerate(actual_burndown))

    # SVG horizontal bar chart for readiness
    bar_rows = ""
    bar_w_total = 420
    row_h = 30
    for i, (p, r) in enumerate(zip(PRODUCTS, readiness)):
        y = i * row_h
        bar_px = int(r / 100 * bar_w_total)
        bar_rows += (
            f'<rect x="0" y="{y+4}" width="{bar_w_total}" height="20" fill="#1e293b" rx="4"/>'
            f'<rect x="0" y="{y+4}" width="{bar_px}" height="20" fill="{p[\"color\"]}" rx="4" opacity="0.85"/>'
            f'<text x="{bar_px+6}" y="{y+18}" font-size="11" fill="#e2e8f0">{r:.0f}%</text>'
            f'<text x="{bar_w_total+8}" y="{y+18}" font-size="10" fill="#94a3b8">{p[\"name\"]}</text>'
        )
    bar_svg_h = len(PRODUCTS) * row_h + 10

    # Milestone timeline (Gantt-like, 8 milestones)
    milestones = [
        ("Alpha Release",   3,  5,  "#38bdf8"),
        ("Beta Rollout",    6,  9,  "#818cf8"),
        ("Security Audit", 8,  11, "#f59e0b"),
        ("Perf Benchmark", 10, 13, "#22c55e"),
        ("Docs Complete",  12, 16, "#a3e635"),
        ("GA Launch",      15, 18, "#C74634"),
        ("Customer Pilot", 17, 21, "#fb923c"),
        ("Post-Launch QBR",22, 24, "#94a3b8"),
    ]
    GW, GH = 560, 200
    gpad = 24
    gbar_h = 18
    row_gap = 24
    gantt_rows = ""
    for idx, (label, start, end, col) in enumerate(milestones):
        gy = gpad + idx * row_gap
        gx_start = gpad + start * (GW - 2 * gpad) / num_weeks
        gx_end   = gpad + end   * (GW - 2 * gpad) / num_weeks
        gx_width = gx_end - gx_start
        done_w   = min(gx_width, gx_width * (current_week - start) / max(1, end - start))
        done_w   = max(0, done_w)
        gantt_rows += (
            f'<rect x="{gx_start:.1f}" y="{gy}" width="{gx_width:.1f}" height="{gbar_h}" fill="#1e293b" rx="4"/>'
            f'<rect x="{gx_start:.1f}" y="{gy}" width="{done_w:.1f}" height="{gbar_h}" fill="{col}" rx="4" opacity="0.8"/>'
            f'<text x="{gx_start - 4:.1f}" y="{gy + 13}" font-size="9" fill="#94a3b8" text-anchor="end">{label}</text>'
        )
    # current week marker
    cw_x = gpad + current_week * (GW - 2 * gpad) / num_weeks
    gantt_rows += f'<line x1="{cw_x:.1f}" y1="{gpad}" x2="{cw_x:.1f}" y2="{GH - gpad}" stroke="#C74634" stroke-width="2" stroke-dasharray="4,3"/>'
    gantt_rows += f'<text x="{cw_x + 3:.1f}" y="{GH - gpad + 10}" font-size="9" fill="#C74634">Week {current_week}</text>'

    on_track  = sum(1 for p in PRODUCTS if p["status"] == "On Track")
    launched  = sum(1 for p in PRODUCTS if p["status"] == "Launched")
    at_risk   = sum(1 for p in PRODUCTS if p["status"] == "At Risk")
    delayed   = sum(1 for p in PRODUCTS if p["status"] == "Delayed")
    avg_ready = sum(readiness) / len(readiness)

    return f"""<!DOCTYPE html><html><head><title>Product Launch Tracker</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui,sans-serif}}
h1{{color:#C74634;padding:24px 32px 0;margin:0;font-size:1.6rem;letter-spacing:0.03em}}
h2{{color:#38bdf8;font-size:1.1rem;margin:0 0 12px}}
.subtitle{{color:#94a3b8;padding:4px 32px 20px;font-size:0.92rem}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;padding:0 32px 16px}}
.card{{background:#1e293b;padding:20px;border-radius:10px;border:1px solid #334155}}
.full{{grid-column:1/-1}}
.stat-row{{display:flex;gap:12px;flex-wrap:wrap;padding:0 32px 16px}}
.stat{{background:#1e293b;border-radius:8px;padding:14px 22px;border:1px solid #334155;min-width:110px}}
.stat .val{{font-size:1.5rem;font-weight:700;color:#C74634}}
.stat .lbl{{font-size:0.78rem;color:#94a3b8;margin-top:2px}}
.on-track{{color:#22c55e}}.at-risk{{color:#f59e0b}}.delayed{{color:#ef4444}}.launched{{color:#38bdf8}}
table{{border-collapse:collapse;width:100%}}
td,th{{padding:8px 12px;text-align:left;border-bottom:1px solid #334155;font-size:0.87rem}}
th{{color:#94a3b8;font-weight:600}}
</style></head>
<body>
<h1>Product Launch Tracker</h1>
<div class="subtitle">OCI Robot Cloud product portfolio launch readiness dashboard — port {PORT} | Week {current_week}/{num_weeks}</div>

<div class="stat-row">
  <div class="stat"><div class="val launched">{launched}</div><div class="lbl">Launched</div></div>
  <div class="stat"><div class="val on-track">{on_track}</div><div class="lbl">On Track</div></div>
  <div class="stat"><div class="val at-risk">{at_risk}</div><div class="lbl">At Risk</div></div>
  <div class="stat"><div class="val delayed">{delayed}</div><div class="lbl">Delayed</div></div>
  <div class="stat"><div class="val">{avg_ready:.0f}%</div><div class="lbl">Avg Readiness</div></div>
  <div class="stat"><div class="val">{len(PRODUCTS)}</div><div class="lbl">Total Products</div></div>
</div>

<div class="grid">
  <div class="card">
    <h2>Product Readiness (Current Week {current_week})</h2>
    <svg width="{bar_w_total + 180}" height="{bar_svg_h}" style="background:#0f172a;border-radius:6px;padding:8px">
      {bar_rows}
    </svg>
  </div>

  <div class="card">
    <h2>Launch Task Burndown</h2>
    <svg width="{BW}" height="{BH}" style="background:#0f172a;border-radius:6px">
      <polyline points="{ideal_pts}"  fill="none" stroke="#475569" stroke-width="1.5" stroke-dasharray="6,4"/>
      <polyline points="{actual_pts}" fill="none" stroke="#C74634"  stroke-width="2.5" stroke-linejoin="round"/>
      <text x="{pad}" y="{BH - 4}" font-size="9" fill="#64748b">Week 0</text>
      <text x="{BW - pad - 36}" y="{BH - 4}" font-size="9" fill="#64748b">Week {num_weeks}</text>
      <text x="{pad + 4}" y="{pad + 8}" font-size="9" fill="#64748b">400 tasks</text>
      <text x="{bx(num_weeks) - 18:.1f}" y="{by(actual_burndown[-1]) - 4:.1f}" font-size="9" fill="#C74634">{actual_burndown[-1]:.0f}</text>
    </svg>
    <div style="font-size:0.8rem;color:#94a3b8;margin-top:6px">
      <span style="color:#475569">--- Ideal</span>&nbsp;&nbsp;
      <span style="color:#C74634">— Actual</span>
    </div>
  </div>

  <div class="card full">
    <h2>Milestone Gantt — {num_weeks}-Week Launch Timeline</h2>
    <svg width="{GW}" height="{GH}" style="background:#0f172a;border-radius:6px">
      {gantt_rows}
    </svg>
  </div>

  <div class="card full">
    <h2>Product Status Summary</h2>
    <table>
      <tr><th>Product</th><th>Status</th><th>Target Readiness</th><th>Current Readiness</th><th>Gap</th></tr>
      {''.join(
        f'<tr><td>{p["name"]}</td>'
        f'<td style="color:{p["color"]}">{p["status"]}</td>'
        f'<td>{p["target"]}%</td>'
        f'<td>{r:.0f}%</td>'
        f'<td style="color:{"#ef4444" if p["target"]-r>15 else "#22c55e"}">{p["target"]-r:.0f}%</td></tr>'
        for p, r in zip(PRODUCTS, readiness)
      )}
    </table>
  </div>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Product Launch Tracker")
    @app.get("/", response_class=HTMLResponse)
    def index(): return build_html()
    @app.get("/health")
    def health(): return {"status": "ok", "port": PORT}
    @app.get("/products")
    def products():
        random.seed(7)
        readiness = [min(p["target"], p["target"] * 0.87 + random.uniform(-5, 5)) for p in PRODUCTS]
        return [
            {"name": p["name"], "status": p["status"], "target": p["target"], "readiness": round(r, 1)}
            for p, r in zip(PRODUCTS, readiness)
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
