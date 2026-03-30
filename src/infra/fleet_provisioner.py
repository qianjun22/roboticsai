"""Fleet Provisioner — FastAPI port 8468"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8468

def build_html():
    # provisioning Gantt SVG
    nodes = [
        ("Ashburn GPU1", "A100_80GB", "Mar 2026", "active", "#22c55e"),
        ("Ashburn GPU2", "A100_80GB", "Mar 2026", "active", "#22c55e"),
        ("Phoenix GPU1", "A100_40GB", "Mar 2026", "active", "#22c55e"),
        ("Frankfurt GPU1","A100_40GB", "Mar 2026", "active", "#22c55e"),
        ("Ashburn GPU3", "A100_80GB", "Jun 2026", "planned", "#38bdf8"),
        ("Ashburn GPU4", "A100_80GB", "Jun 2026", "planned", "#38bdf8"),
        ("Ashburn GPU5", "H100_80GB", "Sep 2026", "future", "#f59e0b"),
        ("Ashburn GPU6", "H100_80GB", "Sep 2026", "future", "#f59e0b"),
    ]
    months = ["Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct"]
    month_x = {m: 120 + i * 58 for i, m in enumerate(months)}
    gantt = ""
    for i, (name, gpu_type, start_m, status, color) in enumerate(nodes):
        y = 15 + i * 32
        x_start = month_x.get(start_m.split()[0], 120)
        width = 550 - x_start
        gantt += f'<rect x="{x_start}" y="{y}" width="{width}" height="24" fill="{color}" opacity="0.8" rx="4"/>'
        gantt += f'<text x="{x_start + 6}" y="{y+16}" fill="#0f172a" font-size="10" font-weight="bold">{gpu_type}</text>'
        gantt += f'<text x="116" y="{y+16}" fill="#94a3b8" font-size="10" text-anchor="end">{name}</text>'
    for m, x in month_x.items():
        gantt += f'<line x1="{x}" y1="10" x2="{x}" y2="275" stroke="#334155" stroke-width="1"/>'
        gantt += f'<text x="{x+29}" y="290" fill="#64748b" font-size="10" text-anchor="middle">{m}</text>'
    # current time marker
    gantt += f'<line x1="120" y1="10" x2="120" y2="275" stroke="#C74634" stroke-width="2"/>'
    gantt += f'<text x="120" y="8" fill="#C74634" font-size="9" text-anchor="middle">NOW</text>'

    # lead time bars
    resources = ["GPU A100_80GB", "GPU A100_40GB", "GPU H100_80GB", "Network 100G", "Storage 50TB", "IP/DNS"]
    lead_days = [21, 14, 45, 7, 3, 2]
    lead_bars = ""
    for i, (res, days) in enumerate(zip(resources, lead_days)):
        x = 15 + i * 82
        h = int(days / 50 * 120)
        color = "#C74634" if days >= 30 else "#f59e0b" if days >= 14 else "#22c55e"
        lead_bars += f'<rect x="{x}" y="{135-h}" width="60" height="{h}" fill="{color}" rx="3" opacity="0.85"/>'
        label = res.replace(" ", "\n")
        lead_bars += f'<text x="{x+30}" y="150" fill="#94a3b8" font-size="8" text-anchor="middle">{res[:12]}</text>'
        lead_bars += f'<text x="{x+30}" y="{135-h-4}" fill="#e2e8f0" font-size="9" text-anchor="middle">{days}d</text>'

    return f"""<!DOCTYPE html>
<html>
<head><title>Fleet Provisioner</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',sans-serif}}
.hdr{{background:#1e293b;padding:16px 24px;border-bottom:2px solid #C74634;display:flex;align-items:center;gap:12px}}
.hdr h1{{margin:0;font-size:20px;color:#f1f5f9}}
.badge{{background:#C74634;color:#fff;padding:3px 10px;border-radius:12px;font-size:11px;font-weight:700}}
.grid{{display:grid;grid-template-columns:2fr 1fr;gap:16px;padding:20px}}
.card{{background:#1e293b;border-radius:10px;padding:18px;border:1px solid #334155}}
.card h3{{margin:0 0 12px;font-size:14px;color:#94a3b8;text-transform:uppercase;letter-spacing:.05em}}
.metrics{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;padding:16px 20px}}
.m{{background:#1e293b;border-radius:8px;padding:12px 16px;border:1px solid #334155}}
.mv{{font-size:24px;font-weight:700;color:#38bdf8}}
.ml{{font-size:11px;color:#64748b;margin-top:2px}}
.delta{{font-size:12px;color:#22c55e;margin-top:4px}}
.legend{{display:flex;gap:12px;margin-top:8px}}
.li{{display:flex;align-items:center;gap:5px;font-size:11px}}
.ld{{width:14px;height:8px;border-radius:2px}}
</style>
</head>
<body>
<div class="hdr">
  <span class="badge">PORT {PORT}</span>
  <h1>Fleet Provisioner — OCI Capacity Plan</h1>
</div>
<div class="metrics">
  <div class="m"><div class="mv">4 nodes</div><div class="ml">Current Fleet</div></div>
  <div class="m"><div class="mv">+2 Jun</div><div class="ml">Next Expansion</div><div class="delta">A100_80GB x2</div></div>
  <div class="m"><div class="mv">8 nodes</div><div class="ml">Sep 2026 Target</div></div>
  <div class="m"><div class="mv">21 days</div><div class="ml">GPU Lead Time</div><div class="delta">⚠ request now for Jun</div></div>
</div>
<div class="grid">
  <div class="card">
    <h3>Fleet Provisioning Timeline (Mar–Oct 2026)</h3>
    <svg viewBox="0 0 570 300" width="100%">
      {gantt}
    </svg>
    <div class="legend">
      <div class="li"><div class="ld" style="background:#22c55e"></div>Active</div>
      <div class="li"><div class="ld" style="background:#38bdf8"></div>Planned (Jun)</div>
      <div class="li"><div class="ld" style="background:#f59e0b"></div>Future (Sep)</div>
    </div>
  </div>
  <div class="card">
    <h3>Resource Lead Time (days)</h3>
    <svg viewBox="0 0 510 165" width="100%">
      <line x1="10" y1="10" x2="10" y2="138" stroke="#334155" stroke-width="1"/>
      <line x1="10" y1="138" x2="505" y2="138" stroke="#334155" stroke-width="1"/>
      {lead_bars}
    </svg>
    <p style="font-size:11px;color:#C74634;margin:8px 0 0">H100 45-day lead time — submit Jun quota request by Apr 15</p>
  </div>
</div>
</body>
</html>"""

if USE_FASTAPI:
    app = FastAPI(title="Fleet Provisioner")
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
