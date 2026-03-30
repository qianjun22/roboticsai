"""
OCI Audit Trail - port 8677
OCI Robot Cloud | cycle-154B
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

import json
import math
import random
from datetime import datetime

# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------

def svg_event_volume() -> str:
    """90-day stacked bar chart: read/write/admin/security events per day."""
    W, H = 860, 380
    pad = {"l": 60, "r": 30, "t": 50, "b": 60}
    cw = W - pad["l"] - pad["r"]
    ch = H - pad["t"] - pad["b"]
    days = 90
    bar_w = cw / days

    # deterministic fake daily data - seed pattern
    random.seed(42)
    data = []
    for i in range(days):
        base = 800 + 60 * math.sin(i * 0.15)
        r_ev = int(base * 0.50 + random.gauss(0, 20))
        w_ev = int(base * 0.28 + random.gauss(0, 12))
        a_ev = int(base * 0.14 + random.gauss(0, 6))
        s_ev = int(base * 0.08 + random.gauss(0, 4))
        data.append((max(r_ev,0), max(w_ev,0), max(a_ev,0), max(s_ev,0)))

    # inject anomaly spikes at day 23 and day 61
    d23 = list(data[23]); d23[2] = d23[2] + 340; d23[3] = d23[3] + 180; data[23] = tuple(d23)
    d61 = list(data[61]); d61[2] = d61[2] + 290; d61[3] = d61[3] + 150; data[61] = tuple(d61)

    max_total = max(sum(d) for d in data)
    y_max = math.ceil(max_total / 200) * 200

    def sy(v): return pad["t"] + ch - (v / y_max) * ch

    colors = {"read": "#38bdf8", "write": "#22c55e", "admin": "#a78bfa", "security": "#C74634"}
    col_list = [colors["read"], colors["write"], colors["admin"], colors["security"]]

    bars = ""
    for i, (r_ev, w_ev, a_ev, s_ev) in enumerate(data):
        x = pad["l"] + i * bar_w
        layers = [r_ev, w_ev, a_ev, s_ev]
        acc = 0
        for li, val in enumerate(layers):
            bh = (val / y_max) * ch
            by = pad["t"] + ch - acc / y_max * ch - bh
            bars += f'<rect x="{x:.1f}" y="{by:.1f}" width="{max(bar_w-0.6,0.5):.1f}" height="{bh:.1f}" fill="{col_list[li]}" fill-opacity="0.85"/>'
            acc += val

    # anomaly annotations
    def ann(day_idx, label):
        x = pad["l"] + day_idx * bar_w + bar_w / 2
        total = sum(data[day_idx])
        y = sy(total) - 8
        return (f'<line x1="{x:.1f}" y1="{y:.1f}" x2="{x:.1f}" y2="{y-22:.1f}" stroke="#fbbf24" stroke-width="1.5"/>'
                f'<text x="{x:.1f}" y="{y-26:.1f}" fill="#fbbf24" font-size="9" text-anchor="middle">{label}</text>')

    anns = ann(23, "anomaly D23") + ann(61, "anomaly D61")

    # grid
    grid = ""
    for v in range(0, y_max + 1, 400):
        y = sy(v)
        grid += f'<line x1="{pad["l"]}" y1="{y:.1f}" x2="{pad["l"]+cw}" y2="{y:.1f}" stroke="#1e293b" stroke-width="1"/>'
        grid += f'<text x="{pad["l"]-6}" y="{y+4:.1f}" fill="#94a3b8" font-size="10" text-anchor="end">{v}</text>'

    # x-axis ticks every 15 days
    for d in range(0, 91, 15):
        x = pad["l"] + d * bar_w
        grid += f'<text x="{x:.1f}" y="{pad["t"]+ch+16}" fill="#94a3b8" font-size="9" text-anchor="middle">D{d}</text>'

    # legend
    leg = ""
    labels = ["read", "write", "admin", "security"]
    for li, lbl in enumerate(labels):
        lx = pad["l"] + cw - 220 + li * 56
        leg += f'<rect x="{lx}" y="{pad["t"]-20}" width="10" height="10" fill="{col_list[li]}" rx="2"/>'
        leg += f'<text x="{lx+13}" y="{pad["t"]-11}" fill="#94a3b8" font-size="10">{lbl}</text>'

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#0f172a;border-radius:8px">
  <text x="{W//2}" y="26" fill="#e2e8f0" font-size="14" font-weight="bold" text-anchor="middle">Audit Event Volume - 90 Days</text>
  {grid}
  {bars}
  {anns}
  {leg}
  <line x1="{pad['l']}" y1="{pad['t']}" x2="{pad['l']}" y2="{pad['t']+ch}" stroke="#334155" stroke-width="1.5"/>
  <line x1="{pad['l']}" y1="{pad['t']+ch}" x2="{pad['l']+cw}" y2="{pad['t']+ch}" stroke="#334155" stroke-width="1.5"/>
  <text x="{pad['l']+cw//2}" y="{H-8}" fill="#94a3b8" font-size="11" text-anchor="middle">Day</text>
  <text x="12" y="{pad['t']+ch//2}" fill="#94a3b8" font-size="11" text-anchor="middle" transform="rotate(-90,12,{pad['t']+ch//2})">Events</text>
</svg>"""


def svg_user_heatmap() -> str:
    """6 users x 24 hours heatmap; one anomalous off-hours admin pattern."""
    users = ["svc-robot", "admin-ops", "ml-trainer", "data-eng", "monitor", "intruder*"]
    hours = list(range(24))
    cell_w, cell_h = 28, 40
    lpad = 90
    tpad = 70
    W = lpad + cell_w * 24 + 40
    H = tpad + cell_h * len(users) + 50

    random.seed(7)

    def base_freq(user, hour):
        if user == "svc-robot":
            return 0.7 + 0.2 * math.sin(hour * math.pi / 12)
        if user == "admin-ops":
            return 0.8 if 8 <= hour <= 18 else 0.05
        if user == "ml-trainer":
            return 0.6 if 9 <= hour <= 21 else 0.1
        if user == "data-eng":
            return 0.5 if 8 <= hour <= 17 else 0.05
        if user == "monitor":
            return 0.4 + 0.1 * math.sin(hour * math.pi / 6)
        if user == "intruder*":
            # anomalous: high activity 0-5 AM, low otherwise
            return 0.85 if hour <= 5 else 0.05
        return 0.3

    def heat_color(v):
        # 0=dark blue, 1=bright red
        v = max(0, min(1, v))
        r = int(15 + v * (199 - 15))
        g = int(23 + v * (70 - 23) * (1 - v) * 4)
        b = int(42 + (1 - v) * (180 - 42))
        return f"rgb({r},{g},{b})"

    cells = ""
    for ri, user in enumerate(users):
        for hour in hours:
            v = base_freq(user, hour) + random.gauss(0, 0.04)
            v = max(0, min(1, v))
            x = lpad + hour * cell_w
            y = tpad + ri * cell_h
            col = heat_color(v)
            # anomaly highlight for intruder* off-hours
            stroke = ""
            if user == "intruder*" and hour <= 5:
                stroke = f' stroke="#fbbf24" stroke-width="2"'
            cells += f'<rect x="{x}" y="{y}" width="{cell_w-1}" height="{cell_h-1}" fill="{col}" rx="1"{stroke}/>'

    # row labels
    row_labels = ""
    for ri, user in enumerate(users):
        y = tpad + ri * cell_h + cell_h // 2 + 4
        color = "#fbbf24" if "*" in user else "#94a3b8"
        row_labels += f'<text x="{lpad-6}" y="{y}" fill="{color}" font-size="11" text-anchor="end">{user}</text>'

    # col labels every 4h
    col_labels = ""
    for h in range(0, 24, 4):
        x = lpad + h * cell_w + cell_w // 2
        col_labels += f'<text x="{x}" y="{tpad-10}" fill="#94a3b8" font-size="9" text-anchor="middle">{h:02d}h</text>'

    # anomaly annotation
    ann_x = lpad + 2 * cell_w + cell_w // 2
    ann_y = tpad + 5 * cell_h - 8
    ann = (f'<line x1="{ann_x}" y1="{ann_y}" x2="{ann_x+30}" y2="{ann_y-22}" stroke="#fbbf24" stroke-width="1"/>'
           f'<text x="{ann_x+32}" y="{ann_y-24}" fill="#fbbf24" font-size="9">anomalous off-hours</text>')

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#0f172a;border-radius:8px">
  <text x="{W//2}" y="26" fill="#e2e8f0" font-size="14" font-weight="bold" text-anchor="middle">User Activity Heatmap (6 Users x 24 Hours)</text>
  <text x="{W//2}" y="44" fill="#64748b" font-size="11" text-anchor="middle">amber = anomalous off-hours admin pattern (intruder*)</text>
  {cells}
  {row_labels}
  {col_labels}
  {ann}
</svg>"""


def svg_compliance_radar() -> str:
    """Radar chart: 6 frameworks x audit completeness."""
    W, H = 480, 420
    cx, cy, r_max = W // 2, H // 2 + 10, 150

    frameworks = ["GDPR", "SOC2", "ISO27001", "FedRAMP", "HIPAA", "CCPA"]
    scores = [0.96, 0.99, 0.94, 0.88, 0.91, 0.95]
    n = len(frameworks)

    def polar(i, val):
        angle = math.pi / 2 - 2 * math.pi * i / n
        rv = r_max * val
        return cx + rv * math.cos(angle), cy - rv * math.sin(angle)

    # grid polygons
    grid = ""
    for pct in [0.25, 0.50, 0.75, 1.0]:
        pts = []
        for i in range(n):
            angle = math.pi / 2 - 2 * math.pi * i / n
            rv = r_max * pct
            pts.append((cx + rv * math.cos(angle), cy - rv * math.sin(angle)))
        poly = " ".join(f"{p[0]:.1f},{p[1]:.1f}" for p in pts)
        grid += f'<polygon points="{poly}" fill="none" stroke="#1e293b" stroke-width="1"/>'
        grid += f'<text x="{cx+3}" y="{cy - r_max*pct+4:.1f}" fill="#334155" font-size="9">{int(pct*100)}%</text>'

    # spokes
    spokes = ""
    for i in range(n):
        angle = math.pi / 2 - 2 * math.pi * i / n
        ex = cx + r_max * math.cos(angle)
        ey = cy - r_max * math.sin(angle)
        spokes += f'<line x1="{cx}" y1="{cy}" x2="{ex:.1f}" y2="{ey:.1f}" stroke="#1e293b" stroke-width="1"/>'

    # data polygon
    pts_data = [polar(i, scores[i]) for i in range(n)]
    poly_data = " ".join(f"{p[0]:.1f},{p[1]:.1f}" for p in pts_data)

    # labels
    label_offset = 22
    labels_svg = ""
    for i, (name, score) in enumerate(zip(frameworks, scores)):
        angle = math.pi / 2 - 2 * math.pi * i / n
        lx = cx + (r_max + label_offset) * math.cos(angle)
        ly = cy - (r_max + label_offset) * math.sin(angle)
        col = "#fbbf24" if name == "FedRAMP" else "#38bdf8"
        labels_svg += f'<text x="{lx:.1f}" y="{ly:.1f}" fill="{col}" font-size="11" font-weight="600" text-anchor="middle" dominant-baseline="middle">{name}</text>'
        labels_svg += f'<text x="{lx:.1f}" y="{ly+13:.1f}" fill="#64748b" font-size="9" text-anchor="middle">{int(score*100)}%</text>'

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#0f172a;border-radius:8px">
  <text x="{W//2}" y="26" fill="#e2e8f0" font-size="14" font-weight="bold" text-anchor="middle">Compliance Coverage Radar</text>
  <text x="{W//2}" y="44" fill="#64748b" font-size="11" text-anchor="middle">6 frameworks - audit completeness</text>
  {grid}
  {spokes}
  <polygon points="{poly_data}" fill="#38bdf8" fill-opacity="0.15" stroke="#38bdf8" stroke-width="2"/>
  {labels_svg}
  {chr(10).join(f'<circle cx="{p[0]:.1f}" cy="{p[1]:.1f}" r="4" fill="#38bdf8"/>' for p in pts_data)}
</svg>"""


# ---------------------------------------------------------------------------
# HTML page
# ---------------------------------------------------------------------------

def build_html() -> str:
    vol_svg   = svg_event_volume()
    uheat_svg = svg_user_heatmap()
    radar_svg = svg_compliance_radar()

    metrics = [
        ("Events / Day (avg)", "847", "last 90 days", "#38bdf8"),
        ("Anomalous Events", "2", "investigated (scheduled maintenance)", "#fbbf24"),
        ("Audit Completeness", "99.3%", "overall", "#22c55e"),
        ("SOC2 Readiness", "Ready", "99% completeness", "#22c55e"),
        ("FedRAMP Coverage", "88%", "in progress", "#fbbf24"),
        ("Service Port", "8677", "oci_audit_trail", "#C74634"),
    ]

    cards = "".join(f"""
      <div style="background:#1e293b;border-radius:8px;padding:16px 20px;border-left:3px solid {c}">
        <div style="color:#64748b;font-size:11px;text-transform:uppercase;letter-spacing:.05em">{label}</div>
        <div style="color:{c};font-size:26px;font-weight:700;margin:4px 0">{val}</div>
        <div style="color:#94a3b8;font-size:12px">{sub}</div>
      </div>""" for label, val, sub, c in metrics)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>OCI Audit Trail - OCI Robot Cloud</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',system-ui,sans-serif;min-height:100vh}}
  header{{background:#0f172a;border-bottom:1px solid #1e293b;padding:18px 32px;display:flex;align-items:center;gap:16px}}
  header h1{{font-size:20px;font-weight:700;color:#e2e8f0}}
  header .badge{{background:#C74634;color:#fff;font-size:11px;padding:3px 10px;border-radius:12px;font-weight:600}}
  header .port{{background:#1e293b;color:#38bdf8;font-size:11px;padding:3px 10px;border-radius:12px}}
  .main{{padding:24px 32px;max-width:1200px;margin:0 auto}}
  .section-title{{color:#94a3b8;font-size:12px;text-transform:uppercase;letter-spacing:.08em;margin-bottom:12px;margin-top:28px}}
  .metrics{{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:12px;margin-bottom:8px}}
  .charts{{display:flex;flex-direction:column;gap:24px}}
  .chart-card{{background:#1e293b;border-radius:10px;padding:20px;overflow-x:auto}}
  .chart-card h3{{color:#94a3b8;font-size:12px;text-transform:uppercase;letter-spacing:.06em;margin-bottom:14px}}
  svg{{display:block;max-width:100%}}
  footer{{text-align:center;padding:20px;color:#334155;font-size:11px}}
</style>
</head>
<body>
<header>
  <h1>OCI Audit Trail</h1>
  <span class="badge">OCI Robot Cloud</span>
  <span class="port">:8677</span>
  <span style="margin-left:auto;color:#64748b;font-size:12px">cycle-154B</span>
</header>
<div class="main">
  <div class="section-title">Key Metrics</div>
  <div class="metrics">{cards}</div>

  <div class="section-title">Charts</div>
  <div class="charts">
    <div class="chart-card">
      <h3>Audit Event Volume - 90-Day Stacked Bar</h3>
      {vol_svg}
    </div>
    <div class="chart-card">
      <h3>User Activity Heatmap</h3>
      {uheat_svg}
    </div>
    <div class="chart-card">
      <h3>Compliance Coverage Radar</h3>
      {radar_svg}
    </div>
  </div>
</div>
<footer>OCI Robot Cloud - OCI Audit Trail | Port 8677 | {datetime.utcnow().strftime('%Y-%m-%d')}</footer>
</body>
</html>"""


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

if USE_FASTAPI:
    app = FastAPI(title="OCI Audit Trail", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return build_html()

    @app.get("/health")
    async def health():
        return JSONResponse({"status": "ok", "service": "oci_audit_trail", "port": 8677})

    @app.get("/metrics")
    async def metrics():
        return JSONResponse({
            "events_per_day_avg": 847,
            "anomalous_events_90d": 2,
            "anomaly_status": "investigated_scheduled_maintenance",
            "audit_completeness_pct": 99.3,
            "soc2_ready": True,
            "fedramp_coverage_pct": 88,
            "gdpr_coverage_pct": 96,
            "iso27001_coverage_pct": 94,
        })

    if __name__ == "__main__":
        import uvicorn
        uvicorn.run(app, host="0.0.0.0", port=8677)

else:
    from http.server import HTTPServer, BaseHTTPRequestHandler

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a): pass
        def do_GET(self):
            if self.path == "/health":
                body = json.dumps({"status": "ok", "service": "oci_audit_trail", "port": 8677}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
            else:
                body = build_html().encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    if __name__ == "__main__":
        srv = HTTPServer(("0.0.0.0", 8677), Handler)
        print("oci_audit_trail listening on :8677")
        srv.serve_forever()
