"""Partner Portal Analytics — FastAPI port 8781"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8781

RANDOM_SEED = 42
random.seed(RANDOM_SEED)

# Simulated partner data
PARTNERS = [
    {"name": "AgiBot",         "tier": "Platinum", "tier_color": "#e2c97e"},
    {"name": "Boston Dynamics", "tier": "Platinum", "tier_color": "#e2c97e"},
    {"name": "Unitree",         "tier": "Gold",     "tier_color": "#fbbf24"},
    {"name": "NVIDIA Isaac",    "tier": "Gold",     "tier_color": "#fbbf24"},
    {"name": "1X Technologies", "tier": "Silver",   "tier_color": "#94a3b8"},
    {"name": "Apptronik",       "tier": "Silver",   "tier_color": "#94a3b8"},
]

def build_html():
    random.seed()

    # Monthly API call volume (last 12 months, per partner)
    months = ["Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec","Jan","Feb","Mar"]
    partner_volumes = {}
    for p in PARTNERS:
        base = random.randint(4000, 18000)
        trend = random.uniform(1.02, 1.12)
        series = []
        for m in range(12):
            val = int(base * (trend ** m) * random.uniform(0.88, 1.12))
            series.append(val)
        partner_volumes[p["name"]] = series

    # Aggregate monthly totals
    monthly_totals = [sum(partner_volumes[p["name"]][m] for p in PARTNERS) for m in range(12)]
    max_total = max(monthly_totals)

    # Current month KPIs
    total_api_calls = monthly_totals[-1]
    active_partners = len(PARTNERS)
    avg_latency_ms = round(random.uniform(180, 260), 1)
    error_rate_pct = round(random.uniform(0.3, 1.8), 2)
    pipeline_value_k = round(sum(random.uniform(80, 400) for _ in PARTNERS), 1)

    # Stacked bar chart SVG for monthly volume
    chart_w, chart_h = 680, 200
    bar_w = (chart_w - 60) // 12
    colors = ["#C74634", "#38bdf8", "#34d399", "#fbbf24", "#a78bfa", "#fb923c"]
    stacked_bars = []
    for m_idx in range(12):
        x = 30 + m_idx * bar_w
        y_offset = chart_h - 30
        for p_idx, p in enumerate(PARTNERS):
            vol = partner_volumes[p["name"]][m_idx]
            bh = int(vol / max_total * (chart_h - 50))
            y_offset -= bh
            stacked_bars.append(
                f'<rect x="{x+2}" y="{y_offset}" width="{bar_w-4}" height="{bh}" '
                f'fill="{colors[p_idx % len(colors)]}" opacity="0.85" rx="1"/>'
            )
        stacked_bars.append(
            f'<text x="{x + bar_w//2}" y="{chart_h - 12}" text-anchor="middle" '
            f'fill="#64748b" font-size="9">{months[m_idx]}</text>'
        )
    bar_svg = '\n'.join(stacked_bars)

    # Latency trend line (30-day)
    n_days = 30
    lat_pts = []
    for d in range(n_days):
        lat = 220 + 25 * math.sin(d * 0.4) + random.gauss(0, 8)
        lat_pts.append(round(lat, 1))
    lat_min, lat_max = min(lat_pts), max(lat_pts)
    lat_coords = []
    for i, v in enumerate(lat_pts):
        x = int(20 + i * (560 - 40) / (n_days - 1))
        y = int(110 - (v - lat_min) / max(lat_max - lat_min, 1) * 90)
        lat_coords.append(f"{x},{y}")
    lat_path = "M " + " L ".join(lat_coords)
    # SLA line at 250ms
    sla_y = int(110 - (250 - lat_min) / max(lat_max - lat_min, 1) * 90)
    sla_y = max(10, min(110, sla_y))

    # Error rate sparkline
    err_pts = [round(max(0.1, random.gauss(error_rate_pct, 0.3)), 2) for _ in range(30)]
    err_min, err_max = min(err_pts), max(err_pts) + 0.1
    err_coords = []
    for i, v in enumerate(err_pts):
        x = int(20 + i * 540 / 29)
        y = int(50 - (v - err_min) / (err_max - err_min) * 40)
        err_coords.append(f"{x},{y}")
    err_path = "M " + " L ".join(err_coords)

    # Partner engagement table
    partner_rows = ""
    for p_idx, p in enumerate(PARTNERS):
        calls_this_month = partner_volumes[p["name"]][-1]
        calls_last_month = partner_volumes[p["name"]][-2]
        change_pct = round((calls_this_month - calls_last_month) / calls_last_month * 100, 1)
        change_color = "#34d399" if change_pct >= 0 else "#f87171"
        change_sign = "+" if change_pct >= 0 else ""
        endpoints_used = random.randint(4, 12)
        last_active = f"{random.randint(0,4)}h ago"
        partner_rows += (
            f'<tr>'
            f'<td><span style="color:{p["tier_color"]};font-weight:600">{p["name"]}</span></td>'
            f'<td><span style="background:{p["tier_color"]}20;color:{p["tier_color"]};'
            f'padding:2px 8px;border-radius:10px;font-size:11px">{p["tier"]}</span></td>'
            f'<td style="text-align:right">{calls_this_month:,}</td>'
            f'<td style="color:{change_color};text-align:right">{change_sign}{change_pct}%</td>'
            f'<td style="text-align:center">{endpoints_used}/15</td>'
            f'<td style="color:#64748b">{last_active}</td>'
            f'</tr>'
        )

    # Top endpoints
    endpoints = [
        ("/v1/policy/infer",        random.randint(12000, 28000), "#C74634"),
        ("/v1/finetune/submit",     random.randint(6000, 15000),  "#38bdf8"),
        ("/v1/eval/run",            random.randint(5000, 12000),  "#34d399"),
        ("/v1/data/upload",         random.randint(3000, 9000),   "#fbbf24"),
        ("/v1/groot/stream",        random.randint(2000, 7000),   "#a78bfa"),
        ("/v1/sim/launch",          random.randint(1000, 5000),   "#fb923c"),
    ]
    ep_max = endpoints[0][1]
    ep_bars = []
    for i, (ep, cnt, color) in enumerate(endpoints):
        bar_len = int(cnt / ep_max * 320)
        ep_bars.append(
            f'<div style="display:flex;align-items:center;margin:5px 0;font-size:12px">'
            f'<div style="width:180px;color:#94a3b8;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{ep}</div>'
            f'<div style="background:{color};height:14px;width:{bar_len}px;border-radius:3px;margin:0 8px"></div>'
            f'<div style="color:#e2e8f0">{cnt:,}</div></div>'
        )
    ep_html = ''.join(ep_bars)

    return f"""<!DOCTYPE html><html><head><title>Partner Portal Analytics</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui;padding:20px}}
h1{{color:#C74634;margin:0 0 4px 0;font-size:1.6rem}}
h2{{color:#38bdf8;font-size:1rem;margin:0 0 12px 0}}
.card{{background:#1e293b;padding:20px;margin:10px 0;border-radius:8px;border:1px solid #334155}}
.grid2{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}
.metric{{font-size:2rem;font-weight:700;color:#38bdf8}}
.label{{font-size:12px;color:#64748b;margin-top:2px}}
table{{width:100%;border-collapse:collapse;font-size:13px}}
th{{color:#64748b;text-align:left;padding:6px 8px;border-bottom:1px solid #334155}}
td{{padding:5px 8px;border-bottom:1px solid #1e293b}}
</style></head>
<body>
<h1>Partner Portal Analytics</h1>
<p style="color:#64748b;margin:0 0 16px 0">OCI Robot Cloud — design partner API usage, engagement, and pipeline — Port {PORT}</p>

<div style="display:flex;gap:12px;margin-bottom:12px">
  <div class="card" style="flex:1;text-align:center">
    <div class="metric">{total_api_calls:,}</div><div class="label">API Calls This Month</div>
  </div>
  <div class="card" style="flex:1;text-align:center">
    <div class="metric">{active_partners}</div><div class="label">Active Partners</div>
  </div>
  <div class="card" style="flex:1;text-align:center">
    <div class="metric">{avg_latency_ms}ms</div><div class="label">Avg Latency</div>
  </div>
  <div class="card" style="flex:1;text-align:center">
    <div class="metric" style="color:#f87171">{error_rate_pct}%</div><div class="label">Error Rate</div>
  </div>
  <div class="card" style="flex:1;text-align:center">
    <div class="metric" style="color:#34d399">${pipeline_value_k}K</div><div class="label">Pipeline Value</div>
  </div>
</div>

<div class="card">
  <h2>Monthly API Volume by Partner (stacked)</h2>
  <svg width="{chart_w}" height="{chart_h}" style="display:block">
    <line x1="30" y1="{chart_h-30}" x2="{chart_w-10}" y2="{chart_h-30}" stroke="#334155" stroke-width="1"/>
    {bar_svg}
  </svg>
  <div style="margin-top:8px;display:flex;flex-wrap:wrap;gap:8px">
    {''.join(f'<span style="display:inline-flex;align-items:center;gap:4px;font-size:12px"><span style="width:10px;height:10px;background:{colors[i % len(colors)]};border-radius:2px;display:inline-block"></span>{p["name"]}</span>' for i, p in enumerate(PARTNERS))}
  </div>
</div>

<div class="grid2">
  <div class="card">
    <h2>API Latency — 30-Day Trend</h2>
    <svg width="560" height="120">
      <line x1="20" y1="{sla_y}" x2="560" y2="{sla_y}" stroke="#C74634" stroke-width="1" stroke-dasharray="5" opacity="0.7"/>
      <text x="530" y="{sla_y - 3}" fill="#C74634" font-size="9">SLA 250ms</text>
      <path d="{lat_path}" stroke="#38bdf8" stroke-width="2" fill="none"/>
    </svg>
  </div>
  <div class="card">
    <h2>Error Rate — 30-Day Sparkline</h2>
    <svg width="580" height="70">
      <path d="{err_path}" stroke="#f87171" stroke-width="2" fill="none"/>
      <line x1="20" y1="10" x2="560" y2="10" stroke="#334155" stroke-width="1" stroke-dasharray="3"/>
    </svg>
    <div style="font-size:12px;color:#64748b;margin-top:6px">
      Min: {min(err_pts)}% &nbsp; Max: {max(err_pts)}% &nbsp; Current: {err_pts[-1]}%
    </div>
  </div>
</div>

<div class="card">
  <h2>Partner Engagement</h2>
  <table>
    <thead><tr><th>Partner</th><th>Tier</th><th style="text-align:right">Calls (Mo)</th><th style="text-align:right">MoM</th><th style="text-align:center">Endpoints</th><th>Last Active</th></tr></thead>
    <tbody>{partner_rows}</tbody>
  </table>
</div>

<div class="grid2">
  <div class="card">
    <h2>Top Endpoints This Month</h2>
    {ep_html}
  </div>
  <div class="card">
    <h2>Portal Health</h2>
    <div style="font-size:13px;line-height:2">
      <div><span style="color:#34d399">●</span> Auth gateway OK</div>
      <div><span style="color:#34d399">●</span> Rate limiter OK</div>
      <div><span style="color:#34d399">●</span> Webhook delivery 99.1%</div>
      <div><span style="color:#fbbf24">●</span> SDK v2.3 deprecation notice sent</div>
      <div><span style="color:#34d399">●</span> Billing sync OK</div>
      <div><span style="color:#34d399">●</span> Docs site up</div>
    </div>
  </div>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Partner Portal Analytics")
    @app.get("/", response_class=HTMLResponse)
    def index(): return build_html()
    @app.get("/health")
    def health(): return {"status": "ok", "port": PORT}
    @app.get("/summary")
    def summary():
        return {
            "active_partners": len(PARTNERS),
            "partners": [p["name"] for p in PARTNERS],
            "avg_latency_ms": round(random.uniform(180, 260), 1),
            "error_rate_pct": round(random.uniform(0.3, 1.8), 2),
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
