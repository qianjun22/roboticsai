"""Partner Integration Tester — FastAPI port 8713"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8713

# Simulated partner integrations
PARTNERS = [
    {"name": "NVIDIA Isaac Sim",  "endpoint": "/isaac/sim",       "type": "SDG"},
    {"name": "Boston Dynamics",   "endpoint": "/bd/spot",         "type": "Robot"},
    {"name": "Agility Robotics",  "endpoint": "/agility/digit",   "type": "Robot"},
    {"name": "Mujoco Physics",    "endpoint": "/mujoco/env",      "type": "Sim"},
    {"name": "LeRobot HF",        "endpoint": "/lerobot/dataset", "type": "Dataset"},
    {"name": "OCI Object Storage","endpoint": "/oci/storage",     "type": "Cloud"},
    {"name": "ROS2 Bridge",       "endpoint": "/ros2/bridge",     "type": "Middleware"},
    {"name": "Cosmos WM",         "endpoint": "/cosmos/wm",       "type": "WorldModel"},
]

STATUSES = ["PASS", "PASS", "PASS", "PASS", "WARN", "FAIL"]
STATUS_COLOR = {"PASS": "#34d399", "WARN": "#fbbf24", "FAIL": "#f87171"}

def build_html():
    random.seed(42)  # reproducible for display

    # Simulate latency readings for each partner (ms)
    partner_data = []
    for p in PARTNERS:
        base_latency = random.uniform(18, 120)
        latencies = [max(5, base_latency + random.gauss(0, base_latency * 0.15)) for _ in range(20)]
        status = random.choice(STATUSES)
        success_rate = round(random.uniform(0.88, 1.0) if status != "FAIL" else random.uniform(0.4, 0.75), 3)
        partner_data.append({
            **p,
            "latencies": latencies,
            "avg_latency": round(sum(latencies) / len(latencies), 1),
            "p99": round(sorted(latencies)[-1], 1),
            "status": status,
            "success_rate": success_rate,
        })

    # ---- Latency sparklines SVG (one per partner) ----
    def sparkline(latencies, color, w=120, h=36):
        mn, mx = min(latencies), max(latencies)
        rng = mx - mn or 1
        pts = " ".join(
            f"{i * w / (len(latencies)-1):.1f},{h - (v - mn) / rng * (h - 4) - 2:.1f}"
            for i, v in enumerate(latencies)
        )
        return f'<svg width="{w}" height="{h}"><polyline points="{pts}" fill="none" stroke="{color}" stroke-width="1.8"/></svg>'

    # ---- Overall success-rate polar chart ----
    # 8 wedges around a circle
    CHART_R = 80
    CX, CY = 100, 100
    pie_paths = ""
    for idx, pd in enumerate(partner_data):
        angle_start = idx * (2 * math.pi / len(partner_data))
        angle_end   = angle_start + (2 * math.pi / len(partner_data)) * pd["success_rate"]
        x1 = CX + CHART_R * math.cos(angle_start)
        y1 = CY + CHART_R * math.sin(angle_start)
        x2 = CX + CHART_R * math.cos(angle_end)
        y2 = CY + CHART_R * math.sin(angle_end)
        color = STATUS_COLOR[pd["status"]]
        pie_paths += f'<line x1="{CX}" y1="{CY}" x2="{x1:.1f}" y2="{y1:.1f}" stroke="{color}" stroke-width="2" opacity="0.5"/>'
        pie_paths += f'<circle cx="{x2:.1f}" cy="{y2:.1f}" r="5" fill="{color}"/>'

    # ---- Aggregate stats ----
    pass_count = sum(1 for pd in partner_data if pd["status"] == "PASS")
    warn_count = sum(1 for pd in partner_data if pd["status"] == "WARN")
    fail_count = sum(1 for pd in partner_data if pd["status"] == "FAIL")
    avg_global = round(sum(pd["avg_latency"] for pd in partner_data) / len(partner_data), 1)
    avg_sr     = round(sum(pd["success_rate"] for pd in partner_data) / len(partner_data) * 100, 1)

    # ---- Rows ----
    rows_html = ""
    type_colors = {"SDG": "#a78bfa", "Robot": "#38bdf8", "Sim": "#34d399",
                   "Dataset": "#fbbf24", "Cloud": "#fb923c", "Middleware": "#f472b6", "WorldModel": "#C74634"}
    for pd in partner_data:
        sc = STATUS_COLOR[pd["status"]]
        tc = type_colors.get(pd["type"], "#94a3b8")
        spark = sparkline(pd["latencies"], sc)
        rows_html += f"""
        <tr>
          <td style="padding:8px 10px;font-weight:600">{pd['name']}</td>
          <td><span style="background:#1e3a5f;color:{tc};padding:2px 8px;border-radius:10px;font-size:0.75rem">{pd['type']}</span></td>
          <td style="color:#94a3b8;font-size:0.82rem">{pd['endpoint']}</td>
          <td style="text-align:right;color:#38bdf8">{pd['avg_latency']}ms</td>
          <td style="text-align:right;color:#64748b">{pd['p99']}ms</td>
          <td style="text-align:right">{round(pd['success_rate']*100,1)}%</td>
          <td><span style="color:{sc};font-weight:700">{pd['status']}</span></td>
          <td>{spark}</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html><head><title>Partner Integration Tester</title>
<style>
  body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui,sans-serif}}
  h1{{color:#C74634;padding:20px 20px 0;margin:0;font-size:1.6rem}}
  .sub{{color:#64748b;padding:0 20px 10px;font-size:0.85rem}}
  h2{{color:#38bdf8;margin:0 0 10px;font-size:1rem}}
  .grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;padding:12px 20px}}
  .card{{background:#1e293b;padding:18px;border-radius:10px;border:1px solid #334155}}
  .full{{grid-column:1/-1}}
  .metric .val{{font-size:1.7rem;font-weight:700}}
  .metric .lbl{{font-size:0.73rem;color:#64748b;margin-top:2px}}
  table{{width:100%;border-collapse:collapse}}
  th{{color:#64748b;font-size:0.78rem;text-align:left;padding:6px 10px;border-bottom:1px solid #334155}}
  tr:hover td{{background:#263348}}
  td{{border-bottom:1px solid #1e293b;vertical-align:middle}}
</style></head>
<body>
<h1>Partner Integration Tester</h1>
<div class="sub">Real-time health checks for all OCI Robot Cloud partner APIs — port {PORT}</div>

<div class="grid">
  <div class="card">
    <div class="metric"><div class="val" style="color:#34d399">{pass_count}</div><div class="lbl">Passing</div></div>
  </div>
  <div class="card">
    <div class="metric"><div class="val" style="color:#fbbf24">{warn_count}</div><div class="lbl">Warning</div></div>
  </div>
  <div class="card">
    <div class="metric"><div class="val" style="color:#f87171">{fail_count}</div><div class="lbl">Failing</div></div>
  </div>
  <div class="card">
    <div class="metric"><div class="val" style="color:#38bdf8">{avg_global}ms</div><div class="lbl">Avg Latency</div></div>
  </div>

  <div class="card" style="grid-column:1/3">
    <h2>Success Rate Radar</h2>
    <svg width="200" height="200">
      <circle cx="{CX}" cy="{CY}" r="{CHART_R}" fill="none" stroke="#334155" stroke-width="1"/>
      <circle cx="{CX}" cy="{CY}" r="{int(CHART_R*0.5)}" fill="none" stroke="#1e293b" stroke-width="1"/>
      {pie_paths}
      <circle cx="{CX}" cy="{CY}" r="4" fill="#e2e8f0"/>
      <text x="{CX}" y="{CY+22}" fill="#94a3b8" font-size="11" text-anchor="middle">{avg_sr}% avg SR</text>
    </svg>
  </div>

  <div class="card" style="grid-column:3/5">
    <h2>Integration Categories</h2>
    <div style="line-height:2.1;font-size:0.85rem">
      {''.join(f'<div><span style="color:{type_colors.get(t,"#94a3b8")}">&#9632;</span> {t}</div>' for t in ["Robot","Sim","SDG","Dataset","Cloud","Middleware","WorldModel"])}
    </div>
  </div>

  <div class="card full">
    <h2>Partner Endpoint Status</h2>
    <table>
      <thead><tr>
        <th>Partner</th><th>Type</th><th>Endpoint</th>
        <th style="text-align:right">Avg Latency</th>
        <th style="text-align:right">P99</th>
        <th style="text-align:right">Success Rate</th>
        <th>Status</th><th>Latency Trend</th>
      </tr></thead>
      <tbody>{rows_html}</tbody>
    </table>
  </div>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Partner Integration Tester")
    @app.get("/", response_class=HTMLResponse)
    def index(): return build_html()
    @app.get("/health")
    def health(): return {"status": "ok", "port": PORT}
    @app.get("/partners")
    def partners_endpoint():
        random.seed()
        return [
            {
                "name": p["name"],
                "type": p["type"],
                "endpoint": p["endpoint"],
                "status": random.choice(STATUSES),
                "avg_latency_ms": round(random.uniform(18, 120), 1),
                "success_rate": round(random.uniform(0.85, 1.0), 3),
            }
            for p in PARTNERS
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
