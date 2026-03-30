"""Enterprise Deal Tracker — FastAPI port 8701"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8701

def build_html():
    random.seed(7)

    # Pipeline stages
    stages = ["Prospecting", "Discovery", "Technical", "Proposal", "Negotiation", "Closed Won"]
    stage_colors = ["#475569", "#0ea5e9", "#8b5cf6", "#f59e0b", "#C74634", "#22c55e"]
    counts = [14, 9, 7, 5, 3, 2]
    values = [round(random.uniform(0.8, 2.4) * c, 2) for c in counts]  # $M

    # Funnel SVG
    max_count = max(counts)
    funnel_svg = ""
    for i, (stage, color, cnt, val) in enumerate(zip(stages, stage_colors, counts, values)):
        w = 40 + cnt * (460 / max_count)
        x = (560 - w) / 2
        funnel_svg += (
            f'<rect x="{x:.1f}" y="{10 + i*38}" width="{w:.1f}" height="28" rx="5" fill="{color}" opacity="0.85"/>'
            f'<text x="280" y="{30 + i*38}" text-anchor="middle" fill="#fff" font-size="12" font-weight="bold">{stage} — {cnt} deals · ${val:.1f}M</text>'
        )

    # Monthly ARR trend (12 months) with growth curve
    months = ["Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec", "Jan", "Feb", "Mar"]
    base_arr = 1.2
    arr_vals = [round(base_arr * math.exp(0.09 * i) + random.uniform(-0.08, 0.08), 2) for i in range(12)]
    arr_max = max(arr_vals)
    arr_svg_h = 120
    arr_pts = []
    for i, v in enumerate(arr_vals):
        x = 40 + i * (500 / 11)
        y = arr_svg_h - 10 - (v / arr_max) * (arr_svg_h - 20)
        arr_pts.append((x, y, v))
    arr_polyline = " ".join(f"{x:.1f},{y:.1f}" for x, y, _ in arr_pts)
    arr_dots = "".join(
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="#38bdf8"/>'
        f'<text x="{x:.1f}" y="{y - 8:.1f}" text-anchor="middle" fill="#94a3b8" font-size="9">${v:.2f}M</text>'
        for x, y, v in arr_pts
    )
    arr_labels = "".join(
        f'<text x="{40 + i*500/11:.1f}" y="{arr_svg_h + 14}" text-anchor="middle" fill="#64748b" font-size="10">{m}</text>'
        for i, m in enumerate(months)
    )

    # Win rate by segment
    segments = ["SMB", "Mid-Market", "Enterprise", "Strategic"]
    win_rates = [round(random.uniform(28, 62), 1) for _ in segments]
    seg_bars = ""
    for i, (seg, wr) in enumerate(zip(segments, win_rates)):
        bw = wr * 5.2
        seg_bars += (
            f'<rect x="110" y="{8 + i*30}" width="{bw:.1f}" height="20" rx="4" fill="#38bdf8" opacity="0.75"/>'
            f'<text x="105" y="{23 + i*30}" text-anchor="end" fill="#94a3b8" font-size="12">{seg}</text>'
            f'<text x="{116 + bw:.1f}" y="{23 + i*30}" fill="#e2e8f0" font-size="12">{wr}%</text>'
        )

    # Top deals table
    deal_names = ["AcmeCorp", "GlobalMfg", "RoboFleet", "TechNova", "StellarAI"]
    deal_vals = sorted([round(random.uniform(0.5, 4.8), 2) for _ in deal_names], reverse=True)
    deal_stages = random.choices(stages, k=5)
    deal_rows = ""
    for name, val, stage in zip(deal_names, deal_vals, deal_stages):
        close_mo = random.choice(months[-4:])
        deal_rows += f"<tr><td>{name}</td><td>${val:.2f}M</td><td>{stage}</td><td>{close_mo} 2026</td></tr>\n"

    total_pipeline = round(sum(values), 2)
    total_arr = round(arr_vals[-1], 2)

    return f"""<!DOCTYPE html><html><head><title>Enterprise Deal Tracker</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui;padding:20px}}
h1{{color:#C74634;margin-bottom:4px}}h2{{color:#38bdf8;margin:0 0 12px}}
.card{{background:#1e293b;padding:20px;margin:10px 0;border-radius:8px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:10px}}
.stat{{font-size:2rem;font-weight:700;color:#38bdf8}}.sub{{font-size:0.85rem;color:#64748b}}
table{{width:100%;border-collapse:collapse;font-size:13px}}
th{{color:#64748b;text-align:left;padding:6px 10px;border-bottom:1px solid #334155}}
td{{padding:6px 10px;border-bottom:1px solid #1e293b}}
tr:hover td{{background:#263548}}
</style></head>
<body>
<h1>Enterprise Deal Tracker</h1>
<p class="sub">Port {PORT} &nbsp;|&nbsp; OCI Robot Cloud Sales Pipeline &nbsp;|&nbsp; FY2026</p>

<div class="grid">
  <div class="card">
    <h2>Total Pipeline</h2>
    <div class="stat">${total_pipeline:.2f}M</div>
    <p class="sub">{sum(counts)} active deals across {len(stages)} stages</p>
  </div>
  <div class="card">
    <h2>Current MRR (Mar 2026)</h2>
    <div class="stat">${total_arr:.2f}M</div>
    <p class="sub">+{round((arr_vals[-1]/arr_vals[0]-1)*100, 1)}% YoY growth</p>
  </div>
</div>

<div class="card">
  <h2>Deal Funnel</h2>
  <svg width="560" height="{10 + len(stages)*38}">
    {funnel_svg}
  </svg>
</div>

<div class="grid">
  <div class="card">
    <h2>Win Rate by Segment</h2>
    <svg width="400" height="{8 + len(segments)*30 + 10}">
      {seg_bars}
    </svg>
  </div>
  <div class="card">
    <h2>Top Deals</h2>
    <table>
      <tr><th>Account</th><th>Value</th><th>Stage</th><th>Close</th></tr>
      {deal_rows}
    </table>
  </div>
</div>

<div class="card">
  <h2>Monthly ARR Trend ($M)</h2>
  <svg width="560" height="{arr_svg_h + 20}" viewBox="0 0 560 {arr_svg_h + 20}">
    <line x1="40" y1="{arr_svg_h - 10}" x2="550" y2="{arr_svg_h - 10}" stroke="#334155" stroke-width="1"/>
    <polyline points="{arr_polyline}" fill="none" stroke="#38bdf8" stroke-width="2.5"/>
    {arr_dots}
    {arr_labels}
  </svg>
</div>

</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Enterprise Deal Tracker")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return build_html()

    @app.get("/health")
    def health():
        return {"status": "ok", "port": PORT}

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
