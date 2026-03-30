"""Fleet Health Dashboard — FastAPI service on port 8285.

Unified health dashboard for all OCI Robot Cloud GPU nodes and services.
Fallback to stdlib http.server if FastAPI/uvicorn not available.
"""

import math
import random
from datetime import date, timedelta

random.seed(42)

TODAY = date(2026, 3, 30)

# Mock fleet data: GPU nodes
NODES = [
    {
        "id": "gpu-ash-01", "region": "Ashburn",  "status": "HEALTHY",
        "gpu_pct": 91, "vram_used": 71.2, "vram_total": 80,
        "sr": 98.1, "lat_ms": 12, "primary": True,
    },
    {
        "id": "gpu-ash-02", "region": "Ashburn",  "status": "HEALTHY",
        "gpu_pct": 78, "vram_used": 58.4, "vram_total": 80,
        "sr": 97.6, "lat_ms": 14, "primary": False,
    },
    {
        "id": "gpu-phx-01", "region": "Phoenix",  "status": "HEALTHY",
        "gpu_pct": 63, "vram_used": 44.1, "vram_total": 80,
        "sr": 96.8, "lat_ms": 22, "primary": False,
    },
    {
        "id": "gpu-fra-01", "region": "Frankfurt", "status": "HEALTHY",
        "gpu_pct": 41, "vram_used": 29.6, "vram_total": 80,
        "sr": 99.2, "lat_ms": 38, "primary": False,
    },
]

REGION_SCORES = {"Ashburn": 94, "Phoenix": 88, "Frankfurt": 91}
FLEET_SCORE = 91
ACTIVE_INCIDENTS = 0

# 7-day health history (day-7 .. today)
DAYS_7 = [(TODAY - timedelta(days=6 - i)) for i in range(7)]

def _score_series(base, noise=3):
    s = []
    v = base
    for _ in range(7):
        v = max(60, min(100, v + random.uniform(-noise, noise)))
        s.append(round(v, 1))
    s[-1] = base  # pin last day to known value
    return s

HISTORY = {
    "Ashburn":   [88, 90, 91, 89, 93, 92, 94],
    "Phoenix":   [85, 84, 87, 83, 89, 87, 88],
    "Frankfurt": [90, 89, 91, 88, 92, 90, 91],
}

# Maintenance windows and incidents (day index 0..6)
EVENTS = [
    {"day": 2, "region": "Phoenix",   "type": "maintenance", "label": "OS patch"},
    {"day": 4, "region": "Ashburn",   "type": "incident",    "label": "GPU spike"},
]


def _health_color(pct: int) -> str:
    if pct >= 85:
        return "#22c55e"
    if pct >= 65:
        return "#f59e0b"
    return "#C74634"


def _node_color(status: str) -> str:
    return {"HEALTHY": "#22c55e", "DEGRADED": "#f59e0b", "OFFLINE": "#C74634"}.get(status, "#64748b")


def render_topology_svg() -> str:
    """SVG 1: Fleet topology — nodes as circles by region with sync latency lines."""
    w, h = 640, 260
    # Region x positions
    region_x = {"Ashburn": 140, "Phoenix": 320, "Frankfurt": 500}
    region_y = {"Ashburn": 110, "Phoenix": 110, "Frankfurt": 110}

    # Node positions (offset vertically if multiple per region)
    region_node_count = {}
    positions = {}
    for node in NODES:
        r = node["region"]
        cnt = region_node_count.get(r, 0)
        x = region_x[r]
        y = region_y[r] + cnt * 70 - (30 if r == "Ashburn" else 0)
        positions[node["id"]] = (x, y)
        region_node_count[r] = cnt + 1

    # Draw sync latency lines between Ashburn primary and others
    lines = []
    primary = next(n for n in NODES if n["primary"])
    px, py = positions[primary["id"]]
    for node in NODES:
        if node["id"] == primary["id"]:
            continue
        nx, ny = positions[node["id"]]
        lat = node["lat_ms"]
        stroke = "#38bdf8" if lat < 20 else "#f59e0b" if lat < 35 else "#C74634"
        lines.append(
            f'<line x1="{px}" y1="{py}" x2="{nx}" y2="{ny}" stroke="{stroke}" stroke-width="1.5" stroke-dasharray="4 3" opacity="0.6"/>'
        )
        mx, my = (px + nx) // 2, (py + ny) // 2
        lines.append(
            f'<text x="{mx}" y="{my - 4}" text-anchor="middle" font-size="9" fill="{stroke}" font-family="monospace">{lat}ms</text>'
        )

    # Draw region labels
    region_labels = []
    for r, rx in region_x.items():
        region_labels.append(
            f'<text x="{rx}" y="32" text-anchor="middle" font-size="11" fill="#38bdf8" font-family="monospace" font-weight="bold">{r}</text>'
        )
        region_labels.append(
            f'<text x="{rx}" y="46" text-anchor="middle" font-size="9" fill="#475569" font-family="monospace">SLA: {REGION_SCORES[r]}%</text>'
        )

    # Draw node circles + annotations
    circles = []
    for node in NODES:
        x, y = positions[node["id"]]
        col = _node_color(node["status"])
        r_circle = 28 if node["primary"] else 22
        circles.append(f'<circle cx="{x}" cy="{y}" r="{r_circle}" fill="{col}" opacity="0.85" stroke="#0f172a" stroke-width="2"/>')
        if node["primary"]:
            circles.append(f'<text x="{x}" y="{y - 2}" text-anchor="middle" font-size="8" fill="#0f172a" font-family="monospace" font-weight="bold">PRIMARY</text>')
            circles.append(f'<text x="{x}" y="{y + 9}" text-anchor="middle" font-size="7" fill="#0f172a" font-family="monospace">{node["id"]}</text>')
        else:
            circles.append(f'<text x="{x}" y="{y + 4}" text-anchor="middle" font-size="7" fill="#0f172a" font-family="monospace">{node["id"]}</text>')
        # Annotation box below
        ay = y + r_circle + 14
        vram_pct = round(node["vram_used"] / node["vram_total"] * 100)
        ann = f"GPU:{node['gpu_pct']}% VRAM:{node['vram_used']}G SR:{node['sr']}%"
        circles.append(f'<text x="{x}" y="{ay}" text-anchor="middle" font-size="8" fill="#94a3b8" font-family="monospace">{ann}</text>')

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" style="background:#0f172a;border-radius:8px">
  <text x="{w//2}" y="16" text-anchor="middle" font-size="13" fill="#38bdf8" font-family="monospace" font-weight="bold">Fleet Topology — OCI Robot Cloud</text>
  {''.join(region_labels)}
  {''.join(lines)}
  {''.join(circles)}
</svg>"""


def render_trend_svg() -> str:
    """SVG 2: 7-day fleet health score trend — 3 region lines with events."""
    w, h = 640, 220
    pad_l, pad_r, pad_t, pad_b = 50, 30, 30, 40
    chart_w = w - pad_l - pad_r
    chart_h = h - pad_t - pad_b
    n = 7
    x_step = chart_w / (n - 1)
    score_min, score_max = 60, 100

    def sx(i):
        return pad_l + i * x_step

    def sy(v):
        return pad_t + chart_h - (v - score_min) / (score_max - score_min) * chart_h

    region_colors = {"Ashburn": "#38bdf8", "Phoenix": "#f59e0b", "Frankfurt": "#22c55e"}

    # Y grid lines
    grid = []
    for gv in range(65, 101, 5):
        gy = sy(gv)
        grid.append(f'<line x1="{pad_l}" y1="{gy:.1f}" x2="{pad_l + chart_w}" y2="{gy:.1f}" stroke="#1e293b" stroke-width="1"/>')
        grid.append(f'<text x="{pad_l - 4}" y="{gy + 4:.1f}" text-anchor="end" font-size="8" fill="#475569" font-family="monospace">{gv}</text>')

    # X axis labels (dates)
    x_labels = []
    for i, d in enumerate(DAYS_7):
        x_labels.append(f'<text x="{sx(i):.1f}" y="{h - 8}" text-anchor="middle" font-size="8" fill="#475569" font-family="monospace">{d.strftime("%m/%d")}</text>')

    # Region lines + dots
    lines = []
    for region, scores in HISTORY.items():
        col = region_colors[region]
        pts = " ".join(f"{sx(i):.1f},{sy(v):.1f}" for i, v in enumerate(scores))
        lines.append(f'<polyline points="{pts}" fill="none" stroke="{col}" stroke-width="2" opacity="0.9"/>')
        for i, v in enumerate(scores):
            lines.append(f'<circle cx="{sx(i):.1f}" cy="{sy(v):.1f}" r="3" fill="{col}"/>')
        # Label last point
        last_x, last_y = sx(6), sy(scores[6])
        lines.append(f'<text x="{last_x + 4:.1f}" y="{last_y + 4:.1f}" font-size="9" fill="{col}" font-family="monospace">{region[:3]}</text>')

    # Event markers
    event_marks = []
    for ev in EVENTS:
        ex = sx(ev["day"])
        col = "#f59e0b" if ev["type"] == "maintenance" else "#C74634"
        event_marks.append(f'<line x1="{ex:.1f}" y1="{pad_t}" x2="{ex:.1f}" y2="{pad_t + chart_h}" stroke="{col}" stroke-width="1" stroke-dasharray="3 3" opacity="0.7"/>')
        event_marks.append(f'<text x="{ex + 2:.1f}" y="{pad_t + 10}" font-size="7" fill="{col}" font-family="monospace">{ev["label"]}</text>')

    # Legend
    legend = []
    lx = pad_l
    for region, col in region_colors.items():
        legend.append(f'<rect x="{lx}" y="{h - 26}" width="10" height="10" fill="{col}" rx="2"/>')
        legend.append(f'<text x="{lx + 14}" y="{h - 17}" font-size="8" fill="#94a3b8" font-family="monospace">{region}</text>')
        lx += 100

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" style="background:#0f172a;border-radius:8px">
  <text x="{w//2}" y="16" text-anchor="middle" font-size="13" fill="#38bdf8" font-family="monospace" font-weight="bold">7-Day Fleet Health Score by Region</text>
  {''.join(grid)}
  {''.join(event_marks)}
  {''.join(lines)}
  {''.join(x_labels)}
  {''.join(legend)}
</svg>"""


def build_html() -> str:
    svg1 = render_topology_svg()
    svg2 = render_trend_svg()

    node_rows = "".join(
        f"""<tr>
      <td>{n['id']}</td><td>{n['region']}</td>
      <td style="color:{'#22c55e' if n['status']=='HEALTHY' else '#C74634'}">{n['status']}</td>
      <td>{n['gpu_pct']}%</td>
      <td>{n['vram_used']}/{n['vram_total']} GB</td>
      <td>{n['sr']}%</td>
      <td>{n['lat_ms']} ms</td>
    </tr>"""
        for n in NODES
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Fleet Health Dashboard — OCI Robot Cloud</title>
  <style>
    body {{ background:#0f172a; color:#e2e8f0; font-family:monospace; margin:0; padding:20px; }}
    h1 {{ color:#38bdf8; border-bottom:2px solid #C74634; padding-bottom:8px; }}
    .metrics {{ display:flex; gap:20px; flex-wrap:wrap; margin:20px 0; }}
    .card {{ background:#1e293b; border-radius:8px; padding:16px 24px; min-width:150px; text-align:center; }}
    .card-val {{ font-size:2em; font-weight:bold; color:#38bdf8; }}
    .card-lbl {{ font-size:0.8em; color:#64748b; margin-top:4px; }}
    .card.ok .card-val {{ color:#22c55e; }}
    .card.warn .card-val {{ color:#f59e0b; }}
    .card.danger .card-val {{ color:#C74634; }}
    .section {{ margin:30px 0; }}
    h2 {{ color:#38bdf8; font-size:1em; letter-spacing:2px; text-transform:uppercase; }}
    table {{ border-collapse:collapse; width:100%; margin-top:12px; }}
    th {{ background:#1e293b; color:#38bdf8; padding:8px 12px; text-align:left; font-size:0.85em; }}
    td {{ padding:6px 12px; border-bottom:1px solid #1e293b; font-size:0.85em; }}
    tr:hover td {{ background:#1e293b; }}
    svg {{ display:block; max-width:100%; }}
    footer {{ color:#334155; font-size:0.75em; margin-top:40px; text-align:center; }}
  </style>
</head>
<body>
  <h1>Fleet Health Dashboard — OCI Robot Cloud</h1>

  <div class="metrics">
    <div class="card ok">
      <div class="card-val">{FLEET_SCORE}/100</div>
      <div class="card-lbl">Fleet Composite Score</div>
    </div>
    <div class="card ok">
      <div class="card-val">{len(NODES)}</div>
      <div class="card-lbl">GPU Nodes Online</div>
    </div>
    <div class="card {'ok' if ACTIVE_INCIDENTS == 0 else 'danger'}">
      <div class="card-val">{ACTIVE_INCIDENTS}</div>
      <div class="card-lbl">Active Incidents</div>
    </div>
    <div class="card warn">
      <div class="card-val">68%</div>
      <div class="card-lbl">Avg GPU Utilization</div>
    </div>
    <div class="card ok">
      <div class="card-val">30%</div>
      <div class="card-lbl">Avg VRAM Headroom</div>
    </div>
    <div class="card ok">
      <div class="card-val">99.94%</div>
      <div class="card-lbl">Multi-Region SLA</div>
    </div>
  </div>

  <div class="section">
    <h2>Fleet Topology</h2>
    {svg1}
  </div>

  <div class="section">
    <h2>7-Day Health Score Trend</h2>
    {svg2}
  </div>

  <div class="section">
    <h2>Node Inventory</h2>
    <table>
      <tr><th>Node ID</th><th>Region</th><th>Status</th><th>GPU%</th><th>VRAM</th><th>Success Rate</th><th>Sync Lat</th></tr>
      {node_rows}
    </table>
  </div>

  <footer>OCI Robot Cloud — Fleet Health Dashboard | Port 8285 | Refreshed: {TODAY}</footer>
</body>
</html>
"""


try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn

    app = FastAPI(title="Fleet Health Dashboard", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    def dashboard():
        return build_html()

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "fleet_health_dashboard", "port": 8285}

    @app.get("/api/fleet")
    def api_fleet():
        return {
            "fleet_score": FLEET_SCORE,
            "active_incidents": ACTIVE_INCIDENTS,
            "nodes": NODES,
            "region_scores": REGION_SCORES,
        }

    @app.get("/api/history")
    def api_history():
        return {
            "days": [str(d) for d in DAYS_7],
            "history": HISTORY,
            "events": EVENTS,
        }

    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=8285)

except ImportError:
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            content = build_html().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

        def log_message(self, fmt, *args):
            pass

    if __name__ == "__main__":
        server = HTTPServer(("0.0.0.0", 8285), Handler)
        print("Fleet Health Dashboard running on http://0.0.0.0:8285 (stdlib fallback)")
        server.serve_forever()
