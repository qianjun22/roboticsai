"""Series A Readiness — FastAPI port 8757"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8757

def build_html():
    random.seed(99)

    # MRR growth curve (months 1-18)
    mrr = [round(12000 * math.exp(0.18 * i) + random.uniform(-800, 800)) for i in range(18)]
    mrr_max = max(mrr)
    w, h = 560, 140

    def pts(vals, mn, mx):
        n = len(vals)
        return " ".join(
            f"{int(10 + i * (w - 20) / (n - 1))},{int(h - 10 - (v - mn) / (mx - mn + 1) * (h - 20))}"
            for i, v in enumerate(vals)
        )

    mrr_pts = pts(mrr, 0, mrr_max)

    # Runway burn (monthly burn rate)
    burn = [round(85000 + i * 3200 + random.uniform(-4000, 4000)) for i in range(18)]
    burn_pts = pts(burn, min(burn), max(burn))

    # Customer count
    customers = [int(3 * math.exp(0.16 * i) + random.uniform(0, 2)) for i in range(18)]
    cust_pts = pts(customers, 0, max(customers))

    # Radar chart for investor readiness (6 dimensions)
    dims = ["Product", "GTM", "Team", "Revenue", "Tech Moat", "Market"]
    scores = [88, 72, 91, 65, 94, 78]
    cx, cy, r = 140, 120, 95
    n = len(dims)
    def radar_pt(i, val):
        angle = math.pi / 2 - 2 * math.pi * i / n
        rv = r * val / 100
        return cx + rv * math.cos(angle), cy - rv * math.sin(angle)
    def grid_pt(i, frac):
        angle = math.pi / 2 - 2 * math.pi * i / n
        rv = r * frac
        return cx + rv * math.cos(angle), cy - rv * math.sin(angle)

    radar_polygon = " ".join(f"{radar_pt(i, scores[i])[0]:.1f},{radar_pt(i, scores[i])[1]:.1f}" for i in range(n))
    grid_lines = ""
    for frac in [0.25, 0.5, 0.75, 1.0]:
        gpts = " ".join(f"{grid_pt(i, frac)[0]:.1f},{grid_pt(i, frac)[1]:.1f}" for i in range(n))
        grid_lines += f"<polygon points='{gpts}' fill='none' stroke='#334155' stroke-width='1'/>"
    spokes = ""
    labels = ""
    for i in range(n):
        ox, oy = grid_pt(i, 0)
        ex, ey = grid_pt(i, 1.0)
        spokes += f"<line x1='{ox:.1f}' y1='{oy:.1f}' x2='{ex:.1f}' y2='{ey:.1f}' stroke='#334155' stroke-width='1'/>"
        lx, ly = grid_pt(i, 1.22)
        labels += f"<text x='{lx:.1f}' y='{ly:.1f}' text-anchor='middle' fill='#94a3b8' font-size='10'>{dims[i]}</text>"

    # KPI rows
    kpis = [
        ("ARR (projected)", f"${mrr[-1] * 12 / 1000:.0f}K", "+{:.0f}%".format((mrr[-1] / mrr[0] - 1) * 100), "#22c55e"),
        ("Monthly Burn", f"${burn[-1] / 1000:.0f}K", "↑ controlled", "#facc15"),
        ("Runway", "14 months", "post-seed", "#38bdf8"),
        ("NPS Score", "67", "enterprise avg", "#22c55e"),
        ("CAC", "$18,400", "LTV/CAC 4.2×", "#22c55e"),
        ("Design Partners", str(customers[-1]), "paying pilots", "#38bdf8"),
    ]
    kpi_rows = "".join(
        f"<tr><td style='padding:6px 12px;color:#94a3b8'>{k}</td>"
        f"<td style='padding:6px 12px;font-weight:bold;font-size:1.1em'>{v}</td>"
        f"<td style='padding:6px 12px;color:{c}'>{note}</td></tr>"
        for k, v, note, c in kpis
    )

    return f"""<!DOCTYPE html><html><head><title>Series A Readiness</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui}}
h1{{color:#C74634;padding:20px 20px 0;margin:0}}
h2{{color:#38bdf8;margin:0 0 12px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:0}}
.card{{background:#1e293b;padding:20px;margin:10px;border-radius:8px}}
.stat{{font-size:2em;font-weight:bold;color:#38bdf8}}
.label{{color:#94a3b8;font-size:0.85em;margin-top:4px}}
.stats-row{{display:flex;gap:0;flex-wrap:wrap}}
.stat-box{{background:#1e293b;padding:14px 22px;margin:10px;border-radius:8px;min-width:130px}}
table{{width:100%;border-collapse:collapse}}
td{{border-bottom:1px solid #334155}}
.badge{{display:inline-block;padding:3px 10px;border-radius:12px;font-size:0.8em;font-weight:bold}}
</style></head>
<body>
<h1>Series A Readiness Dashboard</h1>
<p style='color:#94a3b8;padding:0 20px;margin:4px 0 0'>Port {PORT} — OCI Robot Cloud fundraising metrics & investor readiness tracker</p>

<div class='stats-row'>
  <div class='stat-box'><div class='stat'>${mrr[-1]/1000:.0f}K</div><div class='label'>Current MRR</div></div>
  <div class='stat-box'><div class='stat'>94%</div><div class='label'>Investor Readiness</div></div>
  <div class='stat-box'><div class='stat'>$12M</div><div class='label'>Series A Target</div></div>
  <div class='stat-box'><div class='stat'>14mo</div><div class='label'>Runway</div></div>
</div>

<div class='grid'>
  <div class='card'>
    <h2>MRR Growth (18 months)</h2>
    <svg width='{w}' height='{h}' style='background:#0f172a;border-radius:4px'>
      <defs><linearGradient id='mgrad' x1='0' x2='0' y1='0' y2='1'>
        <stop offset='0%' stop-color='#38bdf8' stop-opacity='0.3'/>
        <stop offset='100%' stop-color='#38bdf8' stop-opacity='0'/>
      </linearGradient></defs>
      <polyline points='{mrr_pts}' fill='none' stroke='#38bdf8' stroke-width='2.5'/>
      <text x='10' y='14' fill='#64748b' font-size='11'>Monthly Recurring Revenue ($)</text>
    </svg>
  </div>
  <div class='card'>
    <h2>Investor Readiness Radar</h2>
    <svg width='280' height='240' style='background:#0f172a;border-radius:4px'>
      {grid_lines}
      {spokes}
      {labels}
      <polygon points='{radar_polygon}' fill='#38bdf8' fill-opacity='0.25' stroke='#38bdf8' stroke-width='2'/>
    </svg>
  </div>
  <div class='card'>
    <h2>Monthly Burn Rate ($)</h2>
    <svg width='{w}' height='{h}' style='background:#0f172a;border-radius:4px'>
      <polyline points='{burn_pts}' fill='none' stroke='#f59e0b' stroke-width='2'/>
      <text x='10' y='14' fill='#64748b' font-size='11'>Burn rate over 18 months</text>
    </svg>
  </div>
  <div class='card'>
    <h2>Design Partners / Paying Pilots</h2>
    <svg width='{w}' height='{h}' style='background:#0f172a;border-radius:4px'>
      <polyline points='{cust_pts}' fill='none' stroke='#22c55e' stroke-width='2'/>
      <text x='10' y='14' fill='#64748b' font-size='11'>Cumulative paying customers</text>
    </svg>
  </div>
</div>

<div class='card' style='margin:10px'>
  <h2>Key Performance Indicators</h2>
  <table>{kpi_rows}</table>
</div>

<div class='card' style='margin:10px'>
  <h2>Series A Checklist</h2>
  {''.join(f"<div style='padding:5px 0;border-bottom:1px solid #334155'><span class='badge' style='background:#15803d;margin-right:10px'>DONE</span>{item}</div>" for item in [
    'Product-market fit validated with 3+ enterprise pilots',
    'GR00T N1.6 fine-tuning pipeline benchmarked (MAE 0.013)',
    'Multi-GPU DDP training (3.07× throughput) on OCI A100s',
    'Closed-loop eval infrastructure in production',
    'OCI Robot Cloud SDK published (pip install oci-robot-cloud)',
    'Safety monitor + teleoperation collector deployed',
    'CoRL paper draft submitted',
  ])}
  {''.join(f"<div style='padding:5px 0;border-bottom:1px solid #334155'><span class='badge' style='background:#92400e;margin-right:10px'>WIP</span>{item}</div>" for item in [
    'Expand to 10 design partner logos',
    'Series A deck final review with Oracle Ventures',
    'Term sheet negotiation — $12M @ $60M pre-money',
  ])}
</div>

</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Series A Readiness")
    @app.get("/", response_class=HTMLResponse)
    def index(): return build_html()
    @app.get("/health")
    def health(): return {"status": "ok", "port": PORT}
    @app.get("/metrics")
    def metrics():
        return {
            "mrr_usd": round(12000 * math.exp(0.18 * 17) + random.uniform(-800, 800)),
            "runway_months": 14,
            "investor_readiness_pct": 94,
            "series_a_target_usd": 12_000_000,
            "design_partners": int(3 * math.exp(0.16 * 17) + 1),
            "nps": 67,
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
