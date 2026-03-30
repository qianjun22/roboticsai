"""OCI Robot Cloud — Fleet Health Aggregator (port 8609)

6-node fleet radar grid, 90-day health timeline, top-10 alert feed.
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

import math

# ── Node definitions ─────────────────────────────────────────────────────────
NODES = [
    {"name": "Phoenix GPU1",  "status": "WATCH",   "color": "#fb923c",
     "dims": [0.72, 0.68, 0.80, 0.91, 0.85, 0.71]},
    {"name": "Phoenix GPU2",  "status": "OK",      "color": "#34d399",
     "dims": [0.95, 0.91, 0.88, 0.93, 0.90, 0.96]},
    {"name": "Ashburn GPU3",  "status": "OK",      "color": "#34d399",
     "dims": [0.97, 0.94, 0.92, 0.95, 0.93, 0.98]},
    {"name": "Ashburn GPU4",  "status": "OK",      "color": "#34d399",
     "dims": [0.99, 0.98, 0.97, 0.99, 0.98, 0.99]},
    {"name": "London GPU5",   "status": "OK",      "color": "#38bdf8",
     "dims": [0.93, 0.90, 0.88, 0.91, 0.89, 0.94]},
    {"name": "Tokyo GPU6",    "status": "OK",      "color": "#38bdf8",
     "dims": [0.91, 0.88, 0.85, 0.90, 0.87, 0.92]},
]
DIM_LABELS = ["GPU", "CPU", "Mem", "Disk", "Net", "Temp"]

# ── Radar helper ─────────────────────────────────────────────────────────────
def radar_svg(node, cx, cy, r=52, label_r=66):
    n = len(node["dims"])
    color = node["color"]
    # background spokes and rings
    spokes = ""
    rings = ""
    for k in range(n):
        angle = math.pi / 2 - 2 * math.pi * k / n  # start at top
        sx = cx + r * math.cos(angle)
        sy = cy - r * math.sin(angle)
        spokes += f'<line x1="{cx:.1f}" y1="{cy:.1f}" x2="{sx:.1f}" y2="{sy:.1f}" stroke="#334155" stroke-width="1"/>'
        # dim labels
        lx = cx + label_r * math.cos(angle)
        ly = cy - label_r * math.sin(angle)
        spokes += f'<text x="{lx:.1f}" y="{ly + 4:.1f}" fill="#94a3b8" font-size="9" text-anchor="middle">{DIM_LABELS[k]}</text>'
    for frac in [0.33, 0.67, 1.0]:
        ring_pts = []
        for k in range(n):
            angle = math.pi / 2 - 2 * math.pi * k / n
            ring_pts.append(f"{cx + r*frac*math.cos(angle):.1f},{cy - r*frac*math.sin(angle):.1f}")
        ring_pts.append(ring_pts[0])
        rings += f'<polyline points="{" ".join(ring_pts)}" fill="none" stroke="#334155" stroke-width="0.8" opacity="0.7"/>'

    # data polygon
    pts = []
    for k in range(n):
        angle = math.pi / 2 - 2 * math.pi * k / n
        d = node["dims"][k]
        pts.append(f"{cx + r*d*math.cos(angle):.1f},{cy - r*d*math.sin(angle):.1f}")
    poly_pts = " ".join(pts)
    poly = f'<polygon points="{poly_pts}" fill="{color}" fill-opacity="0.25" stroke="{color}" stroke-width="1.8"/>'

    # node name
    status_color = {"OK": "#34d399", "WATCH": "#fb923c", "CRITICAL": "#C74634"}.get(node["status"], "#94a3b8")
    title = f'<text x="{cx:.1f}" y="{cy + r + 22:.1f}" fill="{color}" font-size="10" font-weight="bold" text-anchor="middle">{node["name"]}</text>'
    badge = f'<text x="{cx:.1f}" y="{cy + r + 34:.1f}" fill="{status_color}" font-size="9" text-anchor="middle">[{node["status"]}]</text>'
    return spokes + rings + poly + title + badge


def build_radar_grid_svg():
    cols, rows = 3, 2
    cell_w, cell_h = 240, 220
    W = cols * cell_w
    H = rows * cell_h + 30
    inner = ""
    inner += f'<text x="20" y="22" fill="#C74634" font-size="13" font-weight="bold">Fleet Node Radar Grid — 6 Nodes</text>'
    for i, node in enumerate(NODES):
        row = i // cols
        col = i % cols
        cx = col * cell_w + cell_w / 2
        cy = row * cell_h + cell_h / 2 + 30
        inner += radar_svg(node, cx, cy)
    return f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg" style="background:#1e293b;border-radius:8px">{inner}</svg>'


# ── Timeline SVG ─────────────────────────────────────────────────────────────
def build_timeline_svg():
    import random
    random.seed(42)
    W, H = 760, 300
    pad_l, pad_r, pad_t, pad_b = 60, 20, 40, 50
    chart_w = W - pad_l - pad_r
    chart_h = H - pad_t - pad_b
    days = 90
    step = chart_w / (days - 1)

    def noisy(base, sigma=0.02):
        vals = []
        v = base
        for _ in range(days):
            v = max(0.5, min(1.0, v + random.gauss(0, sigma)))
            vals.append(v)
        return vals

    timelines = {n["name"]: noisy(n["dims"][0], 0.018) for n in NODES}
    # inject two outage dips
    for n in NODES:
        timelines[n["name"]][28] = 0.55
        timelines[n["name"]][29] = 0.60
    timelines["Phoenix GPU1"][55] = 0.45
    timelines["Phoenix GPU1"][56] = 0.50

    lines_svg = ""
    for node in NODES:
        pts = []
        for d, v in enumerate(timelines[node["name"]]):
            x = pad_l + d * step
            y = pad_t + chart_h * (1 - (v - 0.4) / 0.65)
            pts.append(f"{x:.1f},{y:.1f}")
        lines_svg += f'<polyline points="{" ".join(pts)}" fill="none" stroke="{node["color"]}" stroke-width="1.6" opacity="0.85"/>'

    # outage markers
    def outage_mark(day, label):
        x = pad_l + day * step
        return (f'<line x1="{x:.1f}" y1="{pad_t}" x2="{x:.1f}" y2="{pad_t + chart_h}" stroke="#C74634" stroke-dasharray="4,3" stroke-width="1"/>'
                f'<text x="{x + 3:.1f}" y="{pad_t + 14}" fill="#C74634" font-size="9">{label}</text>')

    outages = outage_mark(28, "Outage A") + outage_mark(55, "Phoenix") 

    y_labels = ""
    for v_frac, label in [(0, "50%"), (0.33, "72%"), (0.67, "88%"), (1.0, "100%")]:
        gy = pad_t + chart_h * (1 - v_frac)
        y_labels += f'<line x1="{pad_l}" y1="{gy:.1f}" x2="{pad_l + chart_w}" y2="{gy:.1f}" stroke="#334155" stroke-width="1"/>'
        y_labels += f'<text x="{pad_l - 6}" y="{gy + 4:.1f}" fill="#94a3b8" font-size="9" text-anchor="end">{label}</text>'

    x_labels = ""
    for d in [0, 14, 29, 44, 59, 74, 89]:
        x = pad_l + d * step
        x_labels += f'<text x="{x:.1f}" y="{H - 12}" fill="#94a3b8" font-size="9" text-anchor="middle">d-{90-d}</text>'

    legend = ""
    for i, node in enumerate(NODES):
        lx = pad_l + i * 110
        legend += f'<rect x="{lx}" y="{H - 34}" width="10" height="10" fill="{node["color"]}"/>'
        legend += f'<text x="{lx + 13}" y="{H - 25}" fill="#94a3b8" font-size="9">{node["name"].split()[1]}</text>'

    return f'''
    <svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg" style="background:#1e293b;border-radius:8px">
      {y_labels}
      {outages}
      {lines_svg}
      {x_labels}
      {legend}
      <text x="{pad_l}" y="{pad_t - 14}" fill="#C74634" font-size="12" font-weight="bold">Fleet Health Timeline — 90-Day Rolling</text>
      <text x="{pad_l}" y="{pad_t - 2}" fill="#94a3b8" font-size="10">GPU utilization health score per node</text>
    </svg>
    '''


# ── Alert feed SVG ────────────────────────────────────────────────────────────
ALERTS = [
    ("CRITICAL", "2026-03-30 02:14", "Phoenix GPU1",  "GPU temp exceeded 88°C — throttling active"),
    ("HIGH",     "2026-03-30 01:47", "Phoenix GPU1",  "Memory bandwidth degradation detected (−18%)"),
    ("HIGH",     "2026-03-29 23:02", "Tokyo GPU6",    "Network latency spike 420ms (threshold 200ms)"),
    ("MEDIUM",   "2026-03-29 21:33", "London GPU5",   "Disk I/O queue depth > 64 for 5 min"),
    ("MEDIUM",   "2026-03-29 19:11", "Ashburn GPU3",  "CPU steal time 8% — noisy neighbor suspected"),
    ("MEDIUM",   "2026-03-29 17:45", "Phoenix GPU2",  "Model checkpoint write latency 4.2s"),
    ("MEDIUM",   "2026-03-29 14:22", "Tokyo GPU6",    "Inference p99 latency 980ms (SLO 800ms)"),
    ("MEDIUM",   "2026-03-29 11:08", "London GPU5",   "Training job queue depth 12 (warn > 10)"),
    ("MEDIUM",   "2026-03-29 08:55", "Ashburn GPU4",  "Health check response 312ms (warn > 300ms)"),
    ("MEDIUM",   "2026-03-28 22:30", "Phoenix GPU2",  "Log volume spike 3× baseline"),
]
SEVERITY_COLOR = {"CRITICAL": "#C74634", "HIGH": "#fb923c", "MEDIUM": "#facc15"}


def build_alert_svg():
    row_h = 34
    W = 760
    H = len(ALERTS) * row_h + 54
    rows = ""
    for i, (sev, ts, node, msg) in enumerate(ALERTS):
        y = 48 + i * row_h
        bg = "#1e293b" if i % 2 == 0 else "#243147"
        sc = SEVERITY_COLOR[sev]
        rows += f'<rect x="0" y="{y - 14}" width="{W}" height="{row_h}" fill="{bg}"/>'
        # severity badge
        rows += f'<rect x="12" y="{y - 10}" width="62" height="18" rx="4" fill="{sc}" opacity="0.2"/>'
        rows += f'<text x="43" y="{y + 3}" fill="{sc}" font-size="10" font-weight="bold" text-anchor="middle">{sev}</text>'
        rows += f'<text x="84" y="{y + 3}" fill="#64748b" font-size="10">{ts}</text>'
        rows += f'<text x="230" y="{y + 3}" fill="#38bdf8" font-size="10" font-weight="bold">{node}</text>'
        rows += f'<text x="370" y="{y + 3}" fill="#e2e8f0" font-size="10">{msg}</text>'

    header = (f'<rect x="0" y="0" width="{W}" height="36" fill="#0f172a"/>'
              f'<text x="12" y="22" fill="#C74634" font-size="12" font-weight="bold">Top-10 Alert Feed</text>'
              f'<text x="84" y="22" fill="#94a3b8" font-size="10">Timestamp (UTC)</text>'
              f'<text x="230" y="22" fill="#94a3b8" font-size="10">Node</text>'
              f'<text x="370" y="22" fill="#94a3b8" font-size="10">Message</text>')

    return f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg" style="background:#1e293b;border-radius:8px">{header}{rows}</svg>'


# ── HTML builder ─────────────────────────────────────────────────────────────
def build_html() -> str:
    radar_svg_str = build_radar_grid_svg()
    timeline_svg_str = build_timeline_svg()
    alert_svg_str = build_alert_svg()

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Fleet Health Aggregator — Port 8609</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; padding: 32px; }}
    h1 {{ color: #C74634; font-size: 24px; margin-bottom: 4px; }}
    .subtitle {{ color: #94a3b8; font-size: 13px; margin-bottom: 32px; }}
    .metrics {{ display: flex; gap: 20px; flex-wrap: wrap; margin-bottom: 36px; }}
    .card {{ background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 20px 28px; min-width: 180px; }}
    .card-label {{ color: #94a3b8; font-size: 12px; text-transform: uppercase; letter-spacing: .05em; }}
    .card-value {{ color: #38bdf8; font-size: 28px; font-weight: 700; margin-top: 4px; }}
    .card-value.green {{ color: #34d399; }}
    .card-value.orange {{ color: #fb923c; }}
    .section {{ margin-bottom: 40px; }}
    h2 {{ color: #38bdf8; font-size: 15px; margin-bottom: 14px; }}
  </style>
</head>
<body>
  <h1>Fleet Health Aggregator</h1>
  <p class="subtitle">6-Node OCI Robot Cloud Fleet &nbsp;|&nbsp; Port 8609</p>

  <div class="metrics">
    <div class="card">
      <div class="card-label">Fleet Health Score</div>
      <div class="card-value green">97.2%</div>
    </div>
    <div class="card">
      <div class="card-label">P0 Events (30d)</div>
      <div class="card-value green">0</div>
    </div>
    <div class="card">
      <div class="card-label">Phoenix GPU1</div>
      <div class="card-value orange">WATCH</div>
    </div>
    <div class="card">
      <div class="card-label">Ashburn GPU4 Uptime</div>
      <div class="card-value">99.9%</div>
    </div>
  </div>

  <div class="section">
    <h2>Node Radar Grid</h2>
    {radar_svg_str}
  </div>

  <div class="section">
    <h2>Fleet Health Timeline (90-Day Rolling)</h2>
    {timeline_svg_str}
  </div>

  <div class="section">
    <h2>Top-10 Alert Feed</h2>
    {alert_svg_str}
  </div>
</body>
</html>
"""
    return html


# ── Server ────────────────────────────────────────────────────────────────────
if USE_FASTAPI:
    app = FastAPI(title="Fleet Health Aggregator", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def root():
        return build_html()

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "fleet_health_aggregator", "port": 8609,
                "fleet_health_pct": 97.2, "p0_events_30d": 0}

    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=8609)
else:
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/health":
                body = b'{"status":"ok","service":"fleet_health_aggregator","port":8609}'
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
            else:
                body = build_html().encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            pass

    if __name__ == "__main__":
        print("Fleet Health Aggregator running on port 8609 (stdlib HTTPServer)")
        HTTPServer(("0.0.0.0", 8609), Handler).serve_forever()
