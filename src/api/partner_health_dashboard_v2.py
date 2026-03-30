"""Partner Health Dashboard v2 — FastAPI port 8705"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8705

def build_html():
    random.seed(99)

    partners = [
        {"name": "NVIDIA",     "tier": "Platinum", "integrations": 12, "uptime": 99.97, "api_calls_7d": 184200, "incidents": 0, "health": 98},
        {"name": "Boston Dyn.","tier": "Gold",     "integrations": 7,  "uptime": 99.41, "api_calls_7d": 73400,  "incidents": 1, "health": 87},
        {"name": "Agility Ro.","tier": "Gold",     "integrations": 5,  "uptime": 98.80, "api_calls_7d": 51800,  "incidents": 2, "health": 79},
        {"name": "Apptronik",  "tier": "Silver",   "integrations": 4,  "uptime": 99.12, "api_calls_7d": 28900,  "incidents": 1, "health": 83},
        {"name": "Foxconn",    "tier": "Silver",   "integrations": 6,  "uptime": 97.60, "api_calls_7d": 62100,  "incidents": 3, "health": 68},
        {"name": "Teradyne",   "tier": "Bronze",   "integrations": 3,  "uptime": 99.55, "api_calls_7d": 14300,  "incidents": 0, "health": 91},
    ]

    def health_color(h):
        if h >= 90: return "#22c55e"
        if h >= 75: return "#facc15"
        return "#f87171"

    def tier_color(t):
        return {"Platinum": "#e2e8f0", "Gold": "#fbbf24", "Silver": "#94a3b8", "Bronze": "#b45309"}.get(t, "#64748b")

    # API call sparklines per partner (7 days)
    sparklines = {}
    for p in partners:
        base = p["api_calls_7d"] / 7
        vals = [max(0, base * (0.7 + 0.6 * math.sin(d * 1.1 + random.uniform(0, 3)) + random.gauss(0, 0.1))) for d in range(7)]
        sparklines[p["name"]] = vals

    def spark_svg(vals, w=80, h=28):
        mn, mx = min(vals), max(vals)
        rng = mx - mn or 1
        pts = " ".join(f"{w * i / 6:.1f},{h - 2 - (v - mn) / rng * (h - 4):.1f}" for i, v in enumerate(vals))
        return f'<svg width="{w}" height="{h}"><polyline points="{pts}" fill="none" stroke="#38bdf8" stroke-width="1.5"/></svg>'

    partner_rows = ""
    for p in partners:
        hc = health_color(p["health"])
        tc = tier_color(p["tier"])
        spark = spark_svg(sparklines[p["name"]])
        inc_color = "#f87171" if p["incidents"] > 1 else ("#facc15" if p["incidents"] == 1 else "#22c55e")
        partner_rows += (
            f'<tr>'
            f'<td style="padding:8px 12px;font-weight:600">{p["name"]}</td>'
            f'<td style="padding:8px 12px"><span style="color:{tc};font-size:0.8rem;border:1px solid {tc};padding:2px 6px;border-radius:10px">{p["tier"]}</span></td>'
            f'<td style="padding:8px 12px">{p["integrations"]}</td>'
            f'<td style="padding:8px 12px">{p["uptime"]}%</td>'
            f'<td style="padding:8px 12px">{p["api_calls_7d"]:,}</td>'
            f'<td style="padding:8px 12px">{spark}</td>'
            f'<td style="padding:8px 12px;color:{inc_color}">{p["incidents"]}</td>'
            f'<td style="padding:8px 12px">'
            f'<div style="display:flex;align-items:center;gap:8px">'
            f'<div style="background:#1e3a5f;border-radius:4px;width:80px;height:10px">'
            f'<div style="background:{hc};width:{p["health"]}%;height:100%;border-radius:4px"></div></div>'
            f'<span style="color:{hc};font-weight:600">{p["health"]}</span></div></td>'
            f'</tr>'
        )

    # Radar chart: NVIDIA vs Foxconn across 6 dims
    dims = ["Uptime", "API Vol", "Integrations", "Latency", "Support", "Security"]
    scores_a = [0.999, 0.92, 0.86, 0.95, 0.90, 0.97]  # NVIDIA
    scores_b = [0.976, 0.71, 0.75, 0.68, 0.62, 0.80]  # Foxconn
    cx, cy, r = 200, 180, 130
    n = len(dims)

    def radar_pt(score, i, radius=r):
        angle = math.pi / 2 - 2 * math.pi * i / n
        x = cx + radius * score * math.cos(angle)
        y = cy - radius * score * math.sin(angle)
        return x, y

    # Grid rings
    rings = ""
    for ring in [0.25, 0.5, 0.75, 1.0]:
        ring_pts = " ".join(f"{radar_pt(ring, i)[0]:.1f},{radar_pt(ring, i)[1]:.1f}" for i in range(n))
        rings += f'<polygon points="{ring_pts}" fill="none" stroke="#1e3a5f" stroke-width="1"/>'
        rings += f'<text x="{cx + 5}" y="{cy - ring * r + 4:.1f}" font-size="8" fill="#475569">{int(ring*100)}%</text>'

    # Spokes
    spokes = ""
    for i, dim in enumerate(dims):
        ex, ey = radar_pt(1.0, i)
        lx, ly = radar_pt(1.18, i)
        spokes += f'<line x1="{cx}" y1="{cy}" x2="{ex:.1f}" y2="{ey:.1f}" stroke="#334155" stroke-width="1"/>'
        spokes += f'<text x="{lx:.1f}" y="{ly:.1f}" font-size="9" fill="#94a3b8" text-anchor="middle" dominant-baseline="middle">{dim}</text>'

    pts_a = " ".join(f"{radar_pt(s, i)[0]:.1f},{radar_pt(s, i)[1]:.1f}" for i, s in enumerate(scores_a))
    pts_b = " ".join(f"{radar_pt(s, i)[0]:.1f},{radar_pt(s, i)[1]:.1f}" for i, s in enumerate(scores_b))

    # Incident timeline: 14 days
    timeline_days = 14
    inc_data = {"NVIDIA": [], "Boston Dyn.": [], "Agility Ro.": [], "Foxconn": []}
    for k in inc_data:
        inc_data[k] = [random.randint(0, 2) if random.random() < 0.25 else 0 for _ in range(timeline_days)]
    tl_w, tl_h = 580, 120
    tl_pad = 40
    tl_colors = {"NVIDIA": "#22c55e", "Boston Dyn.": "#38bdf8", "Agility Ro.": "#f59e0b", "Foxconn": "#f87171"}
    tl_svg = ""
    for row_i, (name, days) in enumerate(inc_data.items()):
        row_y = 15 + row_i * 24
        tl_svg += f'<text x="0" y="{row_y + 8}" font-size="9" fill="#94a3b8">{name}</text>'
        for d_i, cnt in enumerate(days):
            bx = tl_pad + d_i * ((tl_w - tl_pad) / timeline_days)
            if cnt > 0:
                tl_svg += f'<circle cx="{bx:.1f}" cy="{row_y:.1f}" r="{4 + cnt * 2}" fill="{tl_colors[name]}" fill-opacity="0.7"/>'
                tl_svg += f'<text x="{bx:.1f}" y="{row_y + 4:.1f}" font-size="8" fill="#0f172a" text-anchor="middle">{cnt}</text>'
            else:
                tl_svg += f'<circle cx="{bx:.1f}" cy="{row_y:.1f}" r="3" fill="#1e3a5f"/>'

    total_api = sum(p["api_calls_7d"] for p in partners)
    total_incidents = sum(p["incidents"] for p in partners)
    avg_health = sum(p["health"] for p in partners) / len(partners)
    avg_uptime = sum(p["uptime"] for p in partners) / len(partners)

    return f"""<!DOCTYPE html><html><head><title>Partner Health Dashboard v2</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui;padding:20px}}
h1{{color:#C74634;margin:0 0 4px 0;font-size:1.6rem}}
h2{{color:#38bdf8;font-size:1rem;margin:0 0 12px 0}}
.card{{background:#1e293b;padding:20px;margin:12px 0;border-radius:10px;border:1px solid #334155}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:12px}}
.stat{{background:#1e293b;border-radius:8px;padding:16px;border:1px solid #334155;text-align:center}}
.stat .val{{font-size:2rem;font-weight:700;color:#38bdf8}}
.stat .lbl{{font-size:0.75rem;color:#64748b;margin-top:4px}}
table{{width:100%;border-collapse:collapse}}
thead th{{color:#64748b;font-size:0.75rem;text-align:left;padding:6px 10px;border-bottom:1px solid #334155}}
tbody tr:hover{{background:#263347}}
</style></head>
<body>
<h1>Partner Health Dashboard v2</h1>
<p style="color:#64748b;margin-bottom:16px">Port 8705 — OCI Robot Cloud partner integration monitoring, API health, and incident tracking</p>

<div class="grid">
  <div class="stat"><div class="val">{len(partners)}</div><div class="lbl">Active Partners</div></div>
  <div class="stat"><div class="val">{total_api:,}</div><div class="lbl">API Calls (7d)</div></div>
  <div class="stat"><div class="val" style="color:{health_color(avg_health)}">{avg_health:.1f}</div><div class="lbl">Avg Health Score</div></div>
  <div class="stat"><div class="val" style="color:{"#f87171" if total_incidents > 3 else "#facc15" if total_incidents > 0 else "#22c55e'}">{total_incidents}</div><div class="lbl">Open Incidents</div></div>
</div>

<div class="card">
  <h2>Partner Integration Status</h2>
  <table>
    <thead><tr><th>Partner</th><th>Tier</th><th>Integrations</th><th>Uptime</th><th>API Calls (7d)</th><th>Trend</th><th>Incidents</th><th>Health Score</th></tr></thead>
    <tbody>{partner_rows}</tbody>
  </table>
</div>

<div style="display:grid;grid-template-columns:420px 1fr;gap:12px">
  <div class="card">
    <h2>Health Radar: NVIDIA vs Foxconn</h2>
    <svg width="400" height="360" style="display:block;margin:0 auto">
      {rings}
      {spokes}
      <polygon points="{pts_a}" fill="#38bdf8" fill-opacity="0.15" stroke="#38bdf8" stroke-width="2"/>
      <polygon points="{pts_b}" fill="#f87171" fill-opacity="0.15" stroke="#f87171" stroke-width="2"/>
      <circle cx="20" cy="330" r="6" fill="#38bdf8"/>
      <text x="30" y="335" font-size="10" fill="#e2e8f0">NVIDIA</text>
      <circle cx="100" cy="330" r="6" fill="#f87171"/>
      <text x="112" y="335" font-size="10" fill="#e2e8f0">Foxconn</text>
    </svg>
  </div>
  <div class="card">
    <h2>Incident Timeline (Last 14 Days)</h2>
    <svg width="{tl_w}" height="{tl_h}" style="display:block">
      {tl_svg}
    </svg>
    <p style="color:#475569;font-size:0.75rem;margin-top:8px">Circle size proportional to incident severity. Gray = no incident.</p>
    <div style="margin-top:12px">
      {''.join(f'<span style="margin-right:16px;font-size:0.8rem"><span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:{tl_colors[n]};margin-right:4px"></span>{n}</span>' for n in tl_colors)}
    </div>
  </div>
</div>

<div class="card">
  <h2>Fleet Summary</h2>
  <div style="display:flex;gap:32px;flex-wrap:wrap">
    <div><div style="color:#64748b;font-size:0.75rem">Avg Uptime (all partners)</div><div style="font-size:1.4rem;font-weight:700;color:#38bdf8">{avg_uptime:.2f}%</div></div>
    <div><div style="color:#64748b;font-size:0.75rem">Platinum Partners</div><div style="font-size:1.4rem;font-weight:700;color:#e2e8f0">{sum(1 for p in partners if p["tier"]=="Platinum")}</div></div>
    <div><div style="color:#64748b;font-size:0.75rem">Gold Partners</div><div style="font-size:1.4rem;font-weight:700;color:#fbbf24">{sum(1 for p in partners if p["tier"]=="Gold")}</div></div>
    <div><div style="color:#64748b;font-size:0.75rem">Total Integrations</div><div style="font-size:1.4rem;font-weight:700;color:#a78bfa">{sum(p["integrations"] for p in partners)}</div></div>
  </div>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Partner Health Dashboard v2")
    @app.get("/", response_class=HTMLResponse)
    def index(): return build_html()
    @app.get("/health")
    def health(): return {"status": "ok", "port": PORT, "service": "partner_health_dashboard_v2"}
    @app.get("/partners")
    def partners():
        return [
            {"name": "NVIDIA", "tier": "Platinum", "health": 98},
            {"name": "Boston Dynamics", "tier": "Gold", "health": 87},
            {"name": "Agility Robotics", "tier": "Gold", "health": 79},
            {"name": "Apptronik", "tier": "Silver", "health": 83},
            {"name": "Foxconn", "tier": "Silver", "health": 68},
            {"name": "Teradyne", "tier": "Bronze", "health": 91},
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
