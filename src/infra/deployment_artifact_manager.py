"""Deployment Artifact Manager — FastAPI port 8826"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8826

def build_html():
    random.seed(42)

    # Generate artifact registry data
    artifact_types = ["model_weights", "docker_image", "config_bundle", "dataset_shard", "eval_checkpoint"]
    artifact_data = []
    for i, atype in enumerate(artifact_types):
        count = random.randint(12, 80)
        size_gb = round(random.uniform(0.5, 120.0), 2)
        artifact_data.append({"type": atype, "count": count, "size_gb": size_gb})

    # Deployment timeline: 30 days of deployment events
    days = list(range(1, 31))
    deployments_per_day = [max(0, int(4 + 3 * math.sin(d * 0.4) + random.gauss(0, 1))) for d in days]
    failures_per_day = [max(0, int(0.15 * dep + random.gauss(0, 0.5))) for dep in deployments_per_day]

    # SVG bar chart for deployments
    chart_w, chart_h = 560, 120
    max_dep = max(deployments_per_day) or 1
    bar_w = chart_w // len(days)
    bars_svg = ""
    for i, (dep, fail) in enumerate(zip(deployments_per_day, failures_per_day)):
        x = i * bar_w
        dep_h = int((dep / max_dep) * chart_h)
        fail_h = int((fail / max_dep) * chart_h)
        bars_svg += f'<rect x="{x+1}" y="{chart_h - dep_h}" width="{bar_w-2}" height="{dep_h}" fill="#38bdf8" opacity="0.8"/>'
        bars_svg += f'<rect x="{x+1}" y="{chart_h - fail_h}" width="{bar_w-2}" height="{fail_h}" fill="#f87171" opacity="0.9"/>'

    # Artifact size treemap (approximate as horizontal segments)
    total_size = sum(a["size_gb"] for a in artifact_data)
    seg_svg = ""
    colors = ["#38bdf8", "#818cf8", "#34d399", "#fbbf24", "#f472b6"]
    x_off = 0
    for i, a in enumerate(artifact_data):
        seg_w = int((a["size_gb"] / total_size) * 560)
        seg_svg += f'<rect x="{x_off}" y="0" width="{seg_w}" height="40" fill="{colors[i]}" rx="3"/>'
        if seg_w > 40:
            seg_svg += f'<text x="{x_off + seg_w//2}" y="25" text-anchor="middle" font-size="10" fill="#0f172a">{a["type"][:8]}</text>'
        x_off += seg_w

    # Artifact rows
    rows_html = ""
    for a in artifact_data:
        rows_html += f"""
        <tr>
          <td style="padding:8px 12px;color:#38bdf8">{a['type']}</td>
          <td style="padding:8px 12px;text-align:center">{a['count']}</td>
          <td style="padding:8px 12px;text-align:right">{a['size_gb']} GB</td>
          <td style="padding:8px 12px;text-align:center"><span style="background:#1e3a5f;color:#7dd3fc;padding:2px 8px;border-radius:4px">versioned</span></td>
        </tr>"""

    # Recent artifact events
    event_types = ["pushed", "pulled", "promoted", "archived", "validated"]
    event_colors = {"pushed": "#34d399", "pulled": "#38bdf8", "promoted": "#fbbf24", "archived": "#94a3b8", "validated": "#818cf8"}
    events_html = ""
    for i in range(8):
        ev = random.choice(event_types)
        art = random.choice(artifact_types)
        ver = f"v{random.randint(1,5)}.{random.randint(0,9)}.{random.randint(0,20)}"
        mins = random.randint(1, 120)
        events_html += f"""
        <div style="display:flex;align-items:center;gap:12px;padding:8px 0;border-bottom:1px solid #334155">
          <span style="color:{event_colors[ev]};font-weight:bold;width:80px">{ev}</span>
          <span style="color:#cbd5e1;flex:1">{art} <span style="color:#64748b">{ver}</span></span>
          <span style="color:#64748b;font-size:12px">{mins}m ago</span>
        </div>"""

    total_artifacts = sum(a["count"] for a in artifact_data)
    total_deploys = sum(deployments_per_day)
    total_failures = sum(failures_per_day)
    success_rate = round((1 - total_failures / max(total_deploys, 1)) * 100, 1)

    return f"""<!DOCTYPE html><html><head><title>Deployment Artifact Manager</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui,sans-serif}}
h1{{color:#C74634;margin:0;padding:20px 24px 0;font-size:1.6rem}}
h2{{color:#38bdf8;font-size:1rem;margin:0 0 12px}}
.card{{background:#1e293b;padding:20px;margin:12px;border-radius:8px;border:1px solid #334155}}
.grid{{display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:12px;margin:12px}}
.stat{{background:#1e293b;padding:16px;border-radius:8px;border:1px solid #334155;text-align:center}}
.stat-val{{font-size:2rem;font-weight:bold;color:#38bdf8}}
.stat-lbl{{font-size:0.75rem;color:#64748b;margin-top:4px}}
table{{width:100%;border-collapse:collapse}}
th{{background:#0f172a;padding:8px 12px;text-align:left;color:#64748b;font-size:0.75rem;text-transform:uppercase}}
tr:hover{{background:#263148}}
.subtitle{{color:#64748b;padding:4px 24px 16px;font-size:0.85rem}}
</style></head>
<body>
<h1>Deployment Artifact Manager</h1>
<div class="subtitle">OCI Robot Cloud — artifact registry, versioning &amp; deployment lifecycle</div>

<div class="grid">
  <div class="stat"><div class="stat-val">{total_artifacts}</div><div class="stat-lbl">Total Artifacts</div></div>
  <div class="stat"><div class="stat-val">{total_deploys}</div><div class="stat-lbl">Deployments (30d)</div></div>
  <div class="stat"><div class="stat-val" style="color:#34d399">{success_rate}%</div><div class="stat-lbl">Deploy Success Rate</div></div>
  <div class="stat"><div class="stat-val">{round(total_size, 1)} GB</div><div class="stat-lbl">Total Registry Size</div></div>
</div>

<div class="card">
  <h2>Daily Deployments (30 days) — blue=total, red=failures</h2>
  <svg width="560" height="130" style="display:block">
    <g transform="translate(0,5)">{bars_svg}</g>
    <line x1="0" y1="125" x2="560" y2="125" stroke="#334155" stroke-width="1"/>
  </svg>
</div>

<div class="card">
  <h2>Artifact Registry by Type</h2>
  <table>
    <thead><tr><th>Type</th><th>Count</th><th>Size</th><th>Status</th></tr></thead>
    <tbody>{rows_html}</tbody>
  </table>
</div>

<div class="card">
  <h2>Storage Distribution</h2>
  <svg width="560" height="50" style="display:block">
    <g>{seg_svg}</g>
  </svg>
  <div style="display:flex;gap:16px;margin-top:10px;flex-wrap:wrap">
    {''.join(f'<span style="font-size:0.75rem"><span style="color:{colors[i]}">&#9632;</span> {a["type"]} ({a["size_gb"]}GB)</span>' for i, a in enumerate(artifact_data))}
  </div>
</div>

<div class="card">
  <h2>Recent Artifact Events</h2>
  {events_html}
</div>

</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Deployment Artifact Manager")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return build_html()

    @app.get("/health")
    def health():
        return {"status": "ok", "port": PORT, "service": "deployment_artifact_manager"}

    @app.get("/artifacts")
    def artifacts():
        random.seed(42)
        types = ["model_weights", "docker_image", "config_bundle", "dataset_shard", "eval_checkpoint"]
        return [{"type": t, "count": random.randint(12, 80), "size_gb": round(random.uniform(0.5, 120.0), 2)} for t in types]

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
