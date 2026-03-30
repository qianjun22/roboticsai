"""Data Diversity Scheduler — FastAPI port 8461"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8461

def build_html():
    # coverage gap heatmap: task × scene
    tasks = ["Pick-Place", "Push", "Stack", "Pour", "Fold", "Insert"]
    scenes = ["Tabletop", "Kitchen", "Shelf", "Floor", "Cluttered"]
    coverage = [
        [0.94, 0.88, 0.76, 0.82, 0.71],
        [0.87, 0.79, 0.68, 0.74, 0.63],
        [0.81, 0.72, 0.61, 0.69, 0.58],
        [0.42, 0.38, 0.29, 0.31, 0.22],
        [0.31, 0.27, 0.21, 0.24, 0.18],
        [0.38, 0.34, 0.27, 0.29, 0.21],
    ]
    heat = ""
    for i, (task, row) in enumerate(zip(tasks, coverage)):
        for j, (scene, val) in enumerate(zip(scenes, row)):
            x = 90 + j * 80
            y = 15 + i * 44
            color = "#22c55e" if val >= 0.75 else "#f59e0b" if val >= 0.50 else "#C74634"
            heat += f'<rect x="{x}" y="{y}" width="74" height="36" fill="{color}" opacity="{0.25+val*0.65:.2f}" rx="4"/>'
            heat += f'<text x="{x+37}" y="{y+22}" fill="#e2e8f0" font-size="10" font-weight="bold" text-anchor="middle">{int(val*100)}%</text>'
        heat += f'<text x="86" y="{y+22}" fill="#94a3b8" font-size="10" text-anchor="end">{task}</text>'
    for j, scene in enumerate(scenes):
        heat += f'<text x="{127+j*80}" y="12" fill="#64748b" font-size="10" text-anchor="middle">{scene}</text>'

    # collection priority bars
    demo_types = ["Pour+Kitchen", "Fold+Any", "Insert+Shelf", "Stack+Cluttered", "Pour+Floor", "Insert+Kitchen", "Push+Cluttered", "Pick+Shelf"]
    sr_gain = [0.087, 0.074, 0.068, 0.051, 0.049, 0.044, 0.031, 0.022]
    priority_bars = ""
    for i, (dt, gain) in enumerate(zip(demo_types, sr_gain)):
        y = 15 + i * 26
        w = int(gain / 0.10 * 260)
        color = "#C74634" if gain >= 0.07 else "#f59e0b" if gain >= 0.045 else "#64748b"
        priority_bars += f'<rect x="155" y="{y}" width="{w}" height="20" fill="{color}" rx="3" opacity="0.85"/>'
        priority_bars += f'<text x="151" y="{y+14}" fill="#94a3b8" font-size="9" text-anchor="end">{dt}</text>'
        priority_bars += f'<text x="{155+w+5}" y="{y+14}" fill="#e2e8f0" font-size="9">+{int(gain*1000)/10}pp</text>'

    return f"""<!DOCTYPE html>
<html>
<head><title>Data Diversity Scheduler</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',sans-serif}}
.hdr{{background:#1e293b;padding:16px 24px;border-bottom:2px solid #C74634;display:flex;align-items:center;gap:12px}}
.hdr h1{{margin:0;font-size:20px;color:#f1f5f9}}
.badge{{background:#C74634;color:#fff;padding:3px 10px;border-radius:12px;font-size:11px;font-weight:700}}
.grid{{display:grid;grid-template-columns:3fr 2fr;gap:16px;padding:20px}}
.card{{background:#1e293b;border-radius:10px;padding:18px;border:1px solid #334155}}
.card h3{{margin:0 0 12px;font-size:14px;color:#94a3b8;text-transform:uppercase;letter-spacing:.05em}}
.metrics{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;padding:16px 20px}}
.m{{background:#1e293b;border-radius:8px;padding:12px 16px;border:1px solid #334155}}
.mv{{font-size:24px;font-weight:700;color:#38bdf8}}
.ml{{font-size:11px;color:#64748b;margin-top:2px}}
.delta{{font-size:12px;color:#22c55e;margin-top:4px}}
</style>
</head>
<body>
<div class="hdr">
  <span class="badge">PORT {PORT}</span>
  <h1>Data Diversity Scheduler — Collection Priority</h1>
</div>
<div class="metrics">
  <div class="m"><div class="mv">81%</div><div class="ml">Current Coverage</div></div>
  <div class="m"><div class="mv">14</div><div class="ml">Targeted Demos Needed</div><div class="delta">81%→90% coverage</div></div>
  <div class="m"><div class="mv">Pour</div><div class="ml">Most Under-Covered</div><div class="delta">avg 32% coverage</div></div>
  <div class="m"><div class="mv">5×</div><div class="ml">Pour Value vs Pick-Place</div></div>
</div>
<div class="grid">
  <div class="card">
    <h3>Coverage Heatmap: Task × Scene</h3>
    <svg viewBox="0 0 510 285" width="100%">
      {heat}
    </svg>
    <p style="font-size:10px;color:#C74634;margin:6px 0 0">Red cells = &lt;50% coverage — priority collection targets</p>
  </div>
  <div class="card">
    <h3>Collection Priority (SR gain / demo)</h3>
    <svg viewBox="0 0 480 230" width="100%">
      <line x1="153" y1="10" x2="153" y2="225" stroke="#334155" stroke-width="1"/>
      {priority_bars}
    </svg>
  </div>
</div>
</body>
</html>"""

if USE_FASTAPI:
    app = FastAPI(title="Data Diversity Scheduler")
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
