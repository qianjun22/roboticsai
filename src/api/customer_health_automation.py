"""Customer Health Automation — FastAPI port 8755"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8755

def build_html():
    random.seed(99)

    # Customer health score data
    customers = [
        ("Acme Robotics", 91, "Enterprise"),
        ("NovaDyne Labs", 78, "Growth"),
        ("Apex Systems", 55, "Starter"),
        ("Helios AI", 88, "Enterprise"),
        ("Zenith Mfg", 43, "Starter"),
        ("Vertex Inc", 72, "Growth"),
        ("OrbitTech", 66, "Growth"),
        ("CoreLogic", 95, "Enterprise"),
        ("Pulse Dynamics", 39, "Starter"),
        ("SkyNet ML", 83, "Growth"),
    ]

    def score_color(s):
        if s >= 80: return "#34d399"
        if s >= 60: return "#f59e0b"
        return "#f87171"

    def risk_label(s):
        if s >= 80: return "Healthy"
        if s >= 60: return "At Risk"
        return "Critical"

    # Table rows
    rows = ""
    for name, score, tier in customers:
        color = score_color(score)
        risk = risk_label(score)
        bar_w = int(score * 1.4)
        rows += f"""<tr>
          <td style="padding:10px 14px;color:#e2e8f0">{name}</td>
          <td style="padding:10px 14px;color:#94a3b8">{tier}</td>
          <td style="padding:10px 14px">
            <svg width="150" height="16"><rect x="0" y="4" width="140" height="8" fill="#334155" rx="4"/>
            <rect x="0" y="4" width="{bar_w}" height="8" fill="{color}" rx="4"/></svg>
          </td>
          <td style="padding:10px 14px;color:{color};font-weight:700">{score}</td>
          <td style="padding:10px 14px"><span style="background:{color}22;color:{color};padding:3px 10px;border-radius:12px;font-size:0.78rem">{risk}</span></td>
        </tr>"""

    # Trend chart: health scores over 30 days (sine-based drift per customer)
    trend_lines = ""
    trend_colors = ["#38bdf8", "#34d399", "#f59e0b", "#f87171", "#c084fc"]
    featured = customers[:5]
    legend = ""
    for ti, (name, base_score, _) in enumerate(featured):
        pts = []
        score = base_score
        for day in range(30):
            drift = 3 * math.sin(day * 0.4 + ti) + random.gauss(0, 1.5)
            score = max(10, min(100, score + drift * 0.4))
            cx = 30 + day * 17
            cy = 170 - int(score * 1.5)
            pts.append(f"{cx},{cy}")
        color = trend_colors[ti]
        trend_lines += f'<polyline points="{", ".join(pts)}" fill="none" stroke="{color}" stroke-width="2" opacity="0.9"/>'
        legend += f'<rect x="{10 + ti * 120}" y="180" width="12" height="12" fill="{color}" rx="2"/>'
        legend += f'<text x="{26 + ti * 120}" y="190" font-size="10" fill="#e2e8f0">{name[:12]}</text>'

    # Donut chart: tier distribution
    tier_counts = {"Enterprise": 3, "Growth": 4, "Starter": 3}
    tier_colors_map = {"Enterprise": "#38bdf8", "Growth": "#34d399", "Starter": "#f59e0b"}
    total = sum(tier_counts.values())
    donut_segs = ""
    start_angle = -math.pi / 2
    cx_d, cy_d, r_outer, r_inner = 90, 90, 75, 45
    for tier_name, count in tier_counts.items():
        angle = (count / total) * 2 * math.pi
        x1 = cx_d + r_outer * math.cos(start_angle)
        y1 = cy_d + r_outer * math.sin(start_angle)
        x2 = cx_d + r_outer * math.cos(start_angle + angle)
        y2 = cy_d + r_outer * math.sin(start_angle + angle)
        ix1 = cx_d + r_inner * math.cos(start_angle + angle)
        iy1 = cy_d + r_inner * math.sin(start_angle + angle)
        ix2 = cx_d + r_inner * math.cos(start_angle)
        iy2 = cy_d + r_inner * math.sin(start_angle)
        large = 1 if angle > math.pi else 0
        color = tier_colors_map[tier_name]
        donut_segs += (f'<path d="M {x1:.1f} {y1:.1f} A {r_outer} {r_outer} 0 {large} 1 {x2:.1f} {y2:.1f} '
                       f'L {ix1:.1f} {iy1:.1f} A {r_inner} {r_inner} 0 {large} 0 {ix2:.1f} {iy2:.1f} Z" '
                       f'fill="{color}" opacity="0.85"/>'
                       f'<text x="{cx_d + (r_outer + 10) * math.cos(start_angle + angle/2):.1f}" '
                       f'y="{cy_d + (r_outer + 10) * math.sin(start_angle + angle/2):.1f}" '
                       f'font-size="10" fill="#e2e8f0" text-anchor="middle">{tier_name}</text>')
        start_angle += angle

    healthy_count = sum(1 for _, s, _ in customers if s >= 80)
    at_risk_count = sum(1 for _, s, _ in customers if 60 <= s < 80)
    critical_count = sum(1 for _, s, _ in customers if s < 60)
    avg_health = sum(s for _, s, _ in customers) / len(customers)

    return f"""<!DOCTYPE html><html><head><title>Customer Health Automation</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui,sans-serif}}
h1{{color:#C74634;padding:24px 24px 0;margin:0;font-size:1.6rem}}
h2{{color:#38bdf8;margin:0 0 14px;font-size:1.1rem}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;padding:16px}}
.card{{background:#1e293b;padding:20px;border-radius:8px;border:1px solid #334155}}
.full{{grid-column:1/-1}}
.stat{{display:inline-block;margin:8px 16px 8px 0}}
.stat-val{{font-size:1.8rem;font-weight:700}}
.stat-lbl{{font-size:0.75rem;color:#94a3b8;text-transform:uppercase}}
table{{width:100%;border-collapse:collapse}}
thead tr{{background:#0f172a}}
thead th{{padding:10px 14px;color:#64748b;font-size:0.78rem;text-align:left;text-transform:uppercase}}
tbody tr:hover{{background:#273548}}
</style></head>
<body>
<h1>Customer Health Automation</h1>
<p style="color:#94a3b8;padding:0 24px;margin:4px 0 0">Port {PORT} &mdash; Automated health scoring for {len(customers)} accounts</p>
<div class="grid">
  <div class="card full">
    <div style="display:flex;gap:40px;flex-wrap:wrap">
      <div class="stat"><div class="stat-val" style="color:#34d399">{avg_health:.1f}</div><div class="stat-lbl">Avg Health Score</div></div>
      <div class="stat"><div class="stat-val" style="color:#34d399">{healthy_count}</div><div class="stat-lbl">Healthy</div></div>
      <div class="stat"><div class="stat-val" style="color:#f59e0b">{at_risk_count}</div><div class="stat-lbl">At Risk</div></div>
      <div class="stat"><div class="stat-val" style="color:#f87171">{critical_count}</div><div class="stat-lbl">Critical</div></div>
      <div class="stat"><div class="stat-val" style="color:#38bdf8">{len(customers)}</div><div class="stat-lbl">Total Accounts</div></div>
    </div>
  </div>
  <div class="card full">
    <h2>Account Health Scores</h2>
    <table>
      <thead><tr><th>Account</th><th>Tier</th><th>Score Bar</th><th>Score</th><th>Status</th></tr></thead>
      <tbody>{rows}</tbody>
    </table>
  </div>
  <div class="card">
    <h2>30-Day Health Trends (Top 5)</h2>
    <svg width="550" height="200" style="display:block">
      <line x1="30" y1="20" x2="30" y2="170" stroke="#334155" stroke-width="1"/>
      <line x1="30" y1="170" x2="540" y2="170" stroke="#334155" stroke-width="1"/>
      {trend_lines}
      {legend}
    </svg>
  </div>
  <div class="card">
    <h2>Accounts by Tier</h2>
    <svg width="230" height="200" style="display:block;margin:auto">
      {donut_segs}
      <text x="90" y="87" font-size="22" font-weight="700" fill="#e2e8f0" text-anchor="middle">{total}</text>
      <text x="90" y="103" font-size="11" fill="#94a3b8" text-anchor="middle">Accounts</text>
    </svg>
  </div>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Customer Health Automation")

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
