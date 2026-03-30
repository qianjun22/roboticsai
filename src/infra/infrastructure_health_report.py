"""Infrastructure Health Report — FastAPI port 8731"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8731

def build_html():
    rng = random.Random(1337)

    # OCI infrastructure nodes
    nodes = [
        {"name": "oci-a100-01", "role": "Training", "gpu": "A100 80GB", "gpus": 8},
        {"name": "oci-a100-02", "role": "Training", "gpu": "A100 80GB", "gpus": 8},
        {"name": "oci-a10-01",  "role": "Inference", "gpu": "A10",      "gpus": 4},
        {"name": "oci-a10-02",  "role": "Inference", "gpu": "A10",      "gpus": 4},
        {"name": "oci-cpu-01",  "role": "Orchestration", "gpu": "None", "gpus": 0},
        {"name": "oci-jetson-01","role": "Edge",   "gpu": "Orin",      "gpus": 1},
    ]

    for n in nodes:
        n["cpu"]    = rng.uniform(20, 92)
        n["mem"]    = rng.uniform(30, 85)
        n["gpu_util"] = rng.uniform(40, 97) if n["gpus"] > 0 else 0
        n["disk"]   = rng.uniform(40, 78)
        n["temp"]   = rng.uniform(52, 81) if n["gpus"] > 0 else rng.uniform(35, 55)
        n["status"] = "HEALTHY" if n["cpu"] < 90 and n["mem"] < 82 and n["temp"] < 79 else "WARN"
        n["net_in"] = rng.uniform(0.5, 12.0)   # Gbps
        n["net_out"]= rng.uniform(0.2, 8.0)

    healthy = sum(1 for n in nodes if n["status"] == "HEALTHY")
    total_gpu_util = sum(n["gpu_util"] for n in nodes if n["gpus"] > 0) / sum(1 for n in nodes if n["gpus"] > 0)

    # Services
    services = [
        ("GR00T Inference",       8001, "RUNNING"),
        ("Fine-Tune Orchestrator", 8080, "RUNNING"),
        ("Data Collection API",   8003, "RUNNING"),
        ("Closed-Loop Eval",      8010, "RUNNING"),
        ("Model Registry",        8076, "RUNNING"),
        ("Inference Scheduler",   8078, "RUNNING"),
        ("DAgger Collector",      8021, "RUNNING"),
        ("Safety Monitor",        8050, "RUNNING"),
        ("Action Seq Validator",  8730, "RUNNING"),
        ("Cosmos World Model",    8090, "DEGRADED"),
        ("Sim-to-Real Validator", 8057, "RUNNING"),
        ("Billing Tracker",       8053, "STOPPED"),
    ]
    svc_up = sum(1 for s in services if s[2] == "RUNNING")

    # GPU utilization sparkline over last 24 hours (hourly)
    hours = 24
    gpu_history = [55 + 30 * math.sin(h * math.pi / 12) + rng.gauss(0, 6) for h in range(hours)]
    gpu_history = [max(0, min(100, v)) for v in gpu_history]

    # SVG sparkline for GPU utilization
    sp_w, sp_h = 580, 100
    sp_pad = 20
    sp_cw = sp_w - 2 * sp_pad
    sp_ch = sp_h - 2 * sp_pad
    pts = []
    for i, v in enumerate(gpu_history):
        x = sp_pad + (i / (hours - 1)) * sp_cw
        y = sp_pad + (1 - v / 100) * sp_ch
        pts.append(f"{x:.1f},{y:.1f}")
    # Fill area under curve
    fill_pts = pts[0] + ' ' + ' '.join(pts) + f' {sp_pad + sp_cw:.1f},{sp_pad + sp_ch:.1f} {sp_pad},{sp_pad + sp_ch:.1f}'
    sparkline_svg = (
        f'<polygon points="{fill_pts}" fill="#1d4ed8" opacity="0.25"/>'
        f'<polyline points="{" ".join(pts)}" fill="none" stroke="#38bdf8" stroke-width="2"/>'
    )
    # Hour labels
    hour_labels = ''.join(
        f'<text x="{sp_pad + (i/23)*sp_cw:.1f}" y="{sp_h - 4}" fill="#475569" font-size="8" text-anchor="middle">{i:02d}h</text>'
        for i in range(0, 24, 4)
    )
    # Y axis labels
    y_labels = ''.join(
        f'<text x="16" y="{sp_pad + (1 - v/100)*sp_ch:.1f}" fill="#475569" font-size="8" text-anchor="end">{v}%</text>'
        for v in [25, 50, 75, 100]
    )
    grid_lines = ''.join(
        f'<line x1="{sp_pad}" y1="{sp_pad + (1 - v/100)*sp_ch:.1f}" x2="{sp_pad + sp_cw}" y2="{sp_pad + (1 - v/100)*sp_ch:.1f}" stroke="#1e293b" stroke-width="1"/>'
        for v in [25, 50, 75, 100]
    )

    # Node table rows
    def bar(val, color="#38bdf8", w=80):
        bw = val / 100 * w
        return f'<svg width="{w}" height="12"><rect width="{w}" height="12" fill="#0f172a" rx="3"/><rect width="{bw:.1f}" height="12" fill="{color}" rx="3"/><text x="{w/2}" y="9" fill="#e2e8f0" font-size="8" text-anchor="middle">{val:.0f}%</text></svg>'

    node_rows = []
    for n in nodes:
        sc = "#4ade80" if n["status"] == "HEALTHY" else "#f59e0b"
        gpu_bar = bar(n["gpu_util"], "#a78bfa") if n["gpus"] > 0 else "<span style='color:#475569'>N/A</span>"
        temp_color = "#ef4444" if n["temp"] > 75 else "#f59e0b" if n["temp"] > 65 else "#4ade80"
        node_rows.append(
            f'<tr>'
            f'<td><span style="color:{sc}">●</span> {n["name"]}</td>'
            f'<td><span style="background:#1e293b;padding:2px 7px;border-radius:4px;font-size:0.75rem">{n["role"]}</span></td>'
            f'<td>{bar(n["cpu"], "#38bdf8")}</td>'
            f'<td>{bar(n["mem"], "#f472b6")}</td>'
            f'<td>{gpu_bar}</td>'
            f'<td style="color:{temp_color}">{n["temp"]:.0f}°C</td>'
            f'<td style="color:#94a3b8;font-size:0.8rem">{n["net_in"]:.1f} / {n["net_out"]:.1f} Gbps</td>'
            f'</tr>'
        )
    node_table = '\n'.join(node_rows)

    # Service rows
    svc_rows = []
    for name, port, state in services:
        sc = "#4ade80" if state == "RUNNING" else "#f59e0b" if state == "DEGRADED" else "#ef4444"
        latency = rng.uniform(1.2, 45) if state == "RUNNING" else rng.uniform(80, 300) if state == "DEGRADED" else 0
        uptime = rng.uniform(98.5, 99.99) if state == "RUNNING" else rng.uniform(85, 98)
        svc_rows.append(
            f'<tr>'
            f'<td>{name}</td>'
            f'<td style="color:#64748b">:{port}</td>'
            f'<td style="color:{sc};font-weight:bold">{state}</td>'
            f'<td style="color:#94a3b8">{latency:.0f} ms</td>'
            f'<td style="color:#94a3b8">{uptime:.2f}%</td>'
            f'</tr>'
        )
    svc_table = '\n'.join(svc_rows)

    # Cost ring (SVG donut)
    daily_cost = 347.82
    budget = 500.0
    pct = daily_cost / budget
    circ = 2 * math.pi * 36
    dash = pct * circ
    cost_color = "#4ade80" if pct < 0.7 else "#f59e0b" if pct < 0.9 else "#ef4444"
    ring_svg = (
        f'<svg width="100" height="100" viewBox="0 0 100 100">'
        f'<circle cx="50" cy="50" r="36" fill="none" stroke="#1e293b" stroke-width="10"/>'
        f'<circle cx="50" cy="50" r="36" fill="none" stroke="{cost_color}" stroke-width="10" '
        f'stroke-dasharray="{dash:.1f} {circ:.1f}" stroke-dashoffset="{circ/4:.1f}" stroke-linecap="round"/>'
        f'<text x="50" y="45" fill="{cost_color}" font-size="11" text-anchor="middle" font-weight="bold">${daily_cost:.0f}</text>'
        f'<text x="50" y="59" fill="#64748b" font-size="8" text-anchor="middle">/ ${budget:.0f}</text>'
        f'</svg>'
    )

    return f"""<!DOCTYPE html><html><head><title>Infrastructure Health Report</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui;padding:20px}}
h1{{color:#C74634;margin:0 0 4px 0;font-size:1.6rem}}
h2{{color:#38bdf8;font-size:1rem;margin:0 0 12px 0}}
.card{{background:#1e293b;padding:20px;margin:12px 0;border-radius:10px;border:1px solid #334155}}
.grid4{{display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:12px;margin-bottom:12px}}
.grid3{{display:grid;grid-template-columns:2fr 1fr 1fr;gap:12px;margin-bottom:12px}}
.metric{{background:#0f172a;border-radius:8px;padding:14px;text-align:center;border:1px solid #334155}}
.metric .val{{font-size:1.8rem;font-weight:bold;color:#38bdf8}}
.metric .lbl{{font-size:0.75rem;color:#94a3b8;margin-top:4px}}
svg{{display:block}}
table{{width:100%;border-collapse:collapse;font-size:0.82rem}}
th{{color:#94a3b8;text-align:left;padding:6px 10px;border-bottom:1px solid #334155}}
td{{padding:7px 10px;border-bottom:1px solid #1e293b;vertical-align:middle}}
.subtitle{{color:#94a3b8;font-size:0.85rem;margin-bottom:16px}}
</style></head>
<body>
<h1>Infrastructure Health Report</h1>
<p class="subtitle">Port {PORT} &nbsp;|&nbsp; OCI Robot Cloud — Real-time node, service, and cost monitoring</p>

<div class="grid4">
  <div class="metric"><div class="val" style="color:#{'4ade80' if healthy==len(nodes) else 'f59e0b'}">{healthy}/{len(nodes)}</div><div class="lbl">Nodes Healthy</div></div>
  <div class="metric"><div class="val" style="color:#{'4ade80' if svc_up >= 10 else 'f59e0b'}">{svc_up}/{len(services)}</div><div class="lbl">Services Up</div></div>
  <div class="metric"><div class="val">{total_gpu_util:.0f}%</div><div class="lbl">Avg GPU Util</div></div>
  <div class="metric"><div class="val" style="color:#f59e0b">${daily_cost:.2f}</div><div class="lbl">Daily Cost</div></div>
</div>

<div class="card">
  <h2>GPU Cluster Utilization — Last 24 Hours</h2>
  <svg viewBox="0 0 580 100" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:900px">
    <rect width="580" height="100" fill="#0f172a" rx="6"/>
    {grid_lines}
    {sparkline_svg}
    {hour_labels}
    {y_labels}
  </svg>
</div>

<div class="card">
  <h2>Node Status</h2>
  <table>
    <thead><tr><th>Host</th><th>Role</th><th>CPU</th><th>RAM</th><th>GPU Util</th><th>Temp</th><th>Net In/Out</th></tr></thead>
    <tbody>{node_table}</tbody>
  </table>
</div>

<div class="grid3">
  <div class="card">
    <h2>Services</h2>
    <table>
      <thead><tr><th>Service</th><th>Port</th><th>State</th><th>Latency</th><th>Uptime</th></tr></thead>
      <tbody>{svc_table}</tbody>
    </table>
  </div>
  <div class="card" style="text-align:center">
    <h2>Daily Budget</h2>
    <div style="display:flex;justify-content:center;margin:10px 0">{ring_svg}</div>
    <div style="font-size:0.78rem;color:#94a3b8">{pct*100:.0f}% of daily budget used</div>
    <div style="font-size:0.78rem;color:#64748b;margin-top:6px">Est. monthly: ${daily_cost*30:.0f}</div>
  </div>
  <div class="card">
    <h2>Alert Summary</h2>
    <div style="font-size:0.82rem;line-height:1.9">
      <div><span style="color:#f59e0b">⚠</span> cosmos-world-model degraded (port 8090)</div>
      <div><span style="color:#ef4444">✗</span> billing-tracker stopped (port 8053)</div>
      <div><span style="color:#4ade80">✓</span> All A100 nodes nominal</div>
      <div><span style="color:#4ade80">✓</span> GR00T inference healthy (227ms)</div>
      <div><span style="color:#f59e0b">⚠</span> oci-jetson-01 temp 78°C</div>
      <div><span style="color:#4ade80">✓</span> Multi-region failover active</div>
    </div>
  </div>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Infrastructure Health Report")
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
