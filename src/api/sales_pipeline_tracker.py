"""Sales Pipeline Tracker — FastAPI port 8687"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8687

def build_html():
    random.seed(7)
    # Pipeline stages
    stages = ["Prospecting", "Qualification", "Demo", "Proposal", "Negotiation", "Closed Won"]
    stage_counts = [22, 15, 11, 8, 5, 3]
    stage_values = [c * random.randint(40, 120) * 1000 for c in stage_counts]
    stage_colors = ["#60a5fa", "#34d399", "#fbbf24", "#f87171", "#a78bfa", "#22c55e"]

    # Monthly closed-won revenue (last 12 months) — sinusoidal growth trend
    months = ["Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec", "Jan", "Feb", "Mar"]
    revenue = [int(180000 + 60000 * math.sin(i * 0.5) + 15000 * i + random.uniform(-20000, 20000)) for i in range(12)]

    # Win rate trend
    win_rates = [round(28 + 12 * math.sin(i * 0.4) + random.uniform(-3, 3), 1) for i in range(12)]

    # Rep leaderboard
    reps = ["A. Chen", "M. Patel", "S. Torres", "R. Kim", "J. Okafor"]
    rep_deals = [random.randint(3, 12) for _ in reps]
    rep_revenue = [d * random.randint(60, 180) * 1000 for d in rep_deals]

    total_pipeline = sum(stage_values)
    total_closed = revenue[-1]
    avg_win_rate = sum(win_rates) / len(win_rates)
    deals_in_flight = sum(stage_counts[:-1])

    # SVG: revenue bar chart
    w, h = 560, 160
    pad = 40
    bar_w = (w - pad * 2) / len(months) - 2
    rev_max = max(revenue) * 1.1
    rev_bars = ""
    for i, (m, r) in enumerate(zip(months, revenue)):
        bh = (r / rev_max) * (h - pad * 2)
        bx = pad + i * ((w - pad * 2) / len(months))
        by = h - pad - bh
        rev_bars += f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bar_w:.1f}" height="{bh:.1f}" fill="#C74634" opacity="0.85"/>'
        rev_bars += f'<text x="{bx + bar_w/2:.1f}" y="{h - pad + 14}" text-anchor="middle" font-size="9" fill="#94a3b8">{m}</text>'

    # SVG: win rate line chart
    x_scale = (w - pad * 2) / (len(win_rates) - 1)
    wr_max = max(win_rates) + 5
    wr_pts = " ".join(f"{pad + i * x_scale:.1f},{h - pad - (v / wr_max) * (h - pad * 2):.1f}" for i, v in enumerate(win_rates))
    wr_dots = "".join(f'<circle cx="{pad + i * x_scale:.1f}" cy="{h - pad - (v / wr_max) * (h - pad * 2):.1f}" r="3" fill="#34d399"/>' for i, v in enumerate(win_rates))

    # SVG: funnel horizontal bars
    funnel_w, funnel_h = 560, 200
    fpad = 10
    max_val = max(stage_values)
    funnel_bars = ""
    row_h = (funnel_h - fpad * 2) / len(stages)
    for i, (s, v, c) in enumerate(zip(stages, stage_values, stage_colors)):
        bw = (v / max_val) * (funnel_w - 160 - fpad)
        by = fpad + i * row_h + 2
        bh = row_h - 6
        funnel_bars += f'<rect x="120" y="{by:.1f}" width="{bw:.1f}" height="{bh:.1f}" fill="{c}" opacity="0.85" rx="3"/>'
        funnel_bars += f'<text x="115" y="{by + bh/2 + 4:.1f}" text-anchor="end" font-size="11" fill="#e2e8f0">{s}</text>'
        funnel_bars += f'<text x="{120 + bw + 6:.1f}" y="{by + bh/2 + 4:.1f}" font-size="10" fill="#94a3b8">${v/1e6:.2f}M ({stage_counts[i]})</text>'

    # Rep leaderboard rows
    rep_rows = ""
    sorted_reps = sorted(zip(reps, rep_deals, rep_revenue), key=lambda x: -x[2])
    for rank, (name, deals, rev) in enumerate(sorted_reps, 1):
        medal = ["#ffd700", "#c0c0c0", "#cd7f32", "#64748b", "#64748b"][rank-1]
        rep_rows += f"""<tr>
          <td style='color:{medal};font-weight:700;padding:6px 12px'>{rank}</td>
          <td style='padding:6px 12px'>{name}</td>
          <td style='padding:6px 12px;text-align:right'>{deals}</td>
          <td style='padding:6px 12px;text-align:right;color:#22c55e'>${rev/1e6:.2f}M</td>
        </tr>"""

    return f"""<!DOCTYPE html><html><head><title>Sales Pipeline Tracker</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui,sans-serif}}
h1{{color:#C74634;padding:20px 20px 0;margin:0;font-size:1.6rem}}
.subtitle{{color:#94a3b8;padding:4px 20px 16px;font-size:0.9rem}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;padding:0 20px 20px}}
.card{{background:#1e293b;padding:20px;border-radius:8px}}
.card.wide{{grid-column:span 2}}
.card.full{{grid-column:span 4}}
h2{{color:#38bdf8;margin:0 0 12px;font-size:1rem}}
.stat{{font-size:2rem;font-weight:700;color:#f1f5f9}}
.label{{color:#64748b;font-size:0.8rem;margin-top:4px}}
table{{width:100%;border-collapse:collapse}}
th{{color:#64748b;font-size:0.8rem;text-align:left;padding:4px 12px;border-bottom:1px solid #334155}}
td{{border-bottom:1px solid #1e293b;font-size:0.9rem}}
svg text{{fill:#94a3b8;font-size:10px}}
</style></head>
<body>
<h1>Sales Pipeline Tracker</h1>
<div class="subtitle">Port {PORT} — OCI Robot Cloud design partner and enterprise deal pipeline</div>
<div class="grid">
  <div class="card">
    <h2>Total Pipeline</h2>
    <div class="stat">${total_pipeline/1e6:.1f}M</div>
    <div class="label">across all stages</div>
  </div>
  <div class="card">
    <h2>Deals In-Flight</h2>
    <div class="stat">{deals_in_flight}</div>
    <div class="label">active opportunities</div>
  </div>
  <div class="card">
    <h2>Mar Closed Won</h2>
    <div class="stat" style="color:#22c55e">${total_closed/1e3:.0f}K</div>
    <div class="label">this month</div>
  </div>
  <div class="card">
    <h2>Avg Win Rate</h2>
    <div class="stat" style="color:#fbbf24">{avg_win_rate:.1f}%</div>
    <div class="label">trailing 12 months</div>
  </div>

  <div class="card full">
    <h2>Pipeline Funnel by Stage (value + deal count)</h2>
    <svg width="{funnel_w}" height="{funnel_h}">
      {funnel_bars}
    </svg>
  </div>

  <div class="card wide">
    <h2>Monthly Closed-Won Revenue</h2>
    <svg width="{w}" height="{h}">
      <line x1="{pad}" y1="{h-pad}" x2="{w-pad}" y2="{h-pad}" stroke="#334155" stroke-width="1"/>
      <line x1="{pad}" y1="{pad}" x2="{pad}" y2="{h-pad}" stroke="#334155" stroke-width="1"/>
      <text x="{pad-4}" y="{pad+4}" text-anchor="end">${rev_max/1e3:.0f}K</text>
      {rev_bars}
    </svg>
  </div>

  <div class="card wide">
    <h2>Win Rate Trend (%)</h2>
    <svg width="{w}" height="{h}">
      <line x1="{pad}" y1="{h-pad}" x2="{w-pad}" y2="{h-pad}" stroke="#334155" stroke-width="1"/>
      <line x1="{pad}" y1="{pad}" x2="{pad}" y2="{h-pad}" stroke="#334155" stroke-width="1"/>
      <text x="{pad-4}" y="{pad+4}" text-anchor="end">{wr_max:.0f}%</text>
      <text x="{pad-4}" y="{h-pad+4}" text-anchor="end">0%</text>
      <polyline points="{wr_pts}" fill="none" stroke="#34d399" stroke-width="2"/>
      {wr_dots}
    </svg>
  </div>

  <div class="card full">
    <h2>Rep Leaderboard — Q1 2026</h2>
    <table>
      <thead><tr><th>#</th><th>Rep</th><th>Deals</th><th>Revenue</th></tr></thead>
      <tbody>{rep_rows}</tbody>
    </table>
  </div>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Sales Pipeline Tracker")
    @app.get("/", response_class=HTMLResponse)
    def index(): return build_html()
    @app.get("/health")
    def health(): return {"status": "ok", "port": PORT}

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
