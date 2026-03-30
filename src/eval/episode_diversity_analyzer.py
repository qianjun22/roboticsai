"""Episode Diversity Analyzer — FastAPI port 8446"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8446

def build_html():
    random.seed(42)
    # t-SNE scatter plot simulation
    clusters = [
        ("#C74634", "Pick-Place", 40, (120, 100), 35),
        ("#38bdf8", "Push", 25, (250, 140), 30),
        ("#22c55e", "Stack", 30, (180, 200), 32),
        ("#f59e0b", "Sweep", 15, (80, 190), 25),
        ("#8b5cf6", "Bimanual", 8, (300, 90), 20),
        ("#ec4899", "Pour", 6, (330, 210), 18),
    ]
    scatter = ""
    for color, label, count, (cx, cy), spread in clusters:
        for _ in range(count):
            x = cx + random.gauss(0, spread * 0.6)
            y = cy + random.gauss(0, spread * 0.6)
            scatter += f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="{color}" opacity="0.75"/>'
        scatter += f'<text x="{cx}" y="{cy-spread-4}" fill="{color}" font-size="10" text-anchor="middle" font-weight="bold">{label}</text>'

    # coverage bar chart
    task_types = ["Pick-Place", "Push", "Stack", "Sweep", "Bimanual", "Pour"]
    coverages = [0.94, 0.87, 0.91, 0.62, 0.38, 0.41]
    bar_svg = ""
    for i, (t, c) in enumerate(zip(task_types, coverages)):
        x = 40 + i * 78
        h = int(c * 120)
        y = 140 - h
        color = "#22c55e" if c >= 0.80 else "#f59e0b" if c >= 0.55 else "#C74634"
        bar_svg += f'<rect x="{x}" y="{y}" width="50" height="{h}" fill="{color}" rx="3"/>'
        bar_svg += f'<text x="{x+25}" y="156" fill="#94a3b8" font-size="9" text-anchor="middle">{t}</text>'
        bar_svg += f'<text x="{x+25}" y="{y-4}" fill="#e2e8f0" font-size="9" text-anchor="middle">{int(c*100)}%</text>'

    return f"""<!DOCTYPE html>
<html>
<head><title>Episode Diversity Analyzer</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',sans-serif}}
.hdr{{background:#1e293b;padding:16px 24px;border-bottom:2px solid #C74634;display:flex;align-items:center;gap:12px}}
.hdr h1{{margin:0;font-size:20px;color:#f1f5f9}}
.badge{{background:#C74634;color:#fff;padding:3px 10px;border-radius:12px;font-size:11px;font-weight:700}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;padding:20px}}
.card{{background:#1e293b;border-radius:10px;padding:18px;border:1px solid #334155}}
.card h3{{margin:0 0 12px;font-size:14px;color:#94a3b8;text-transform:uppercase;letter-spacing:.05em}}
.metrics{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;padding:16px 20px}}
.m{{background:#1e293b;border-radius:8px;padding:12px 16px;border:1px solid #334155}}
.mv{{font-size:24px;font-weight:700;color:#38bdf8}}
.ml{{font-size:11px;color:#64748b;margin-top:2px}}
.warn{{font-size:12px;color:#f59e0b;margin-top:4px}}
</style>
</head>
<body>
<div class="hdr">
  <span class="badge">PORT {PORT}</span>
  <h1>Episode Diversity Analyzer — Dataset Coverage</h1>
</div>
<div class="metrics">
  <div class="m"><div class="mv">1,247</div><div class="ml">Total Episodes</div></div>
  <div class="m"><div class="mv">81%</div><div class="ml">Diversity Coverage</div></div>
  <div class="m"><div class="mv">6</div><div class="ml">Task Clusters</div><div class="warn">3 under-represented</div></div>
  <div class="m"><div class="mv">14</div><div class="ml">New Episodes Needed</div></div>
</div>
<div class="grid">
  <div class="card">
    <h3>Episode Embedding Space (t-SNE)</h3>
    <svg viewBox="0 0 380 260" width="100%">
      <rect width="380" height="260" fill="#0f172a" rx="6"/>
      {scatter}
    </svg>
  </div>
  <div class="card">
    <h3>Coverage by Task Type</h3>
    <svg viewBox="0 0 510 175" width="100%">
      <line x1="35" y1="10" x2="35" y2="148" stroke="#334155" stroke-width="1"/>
      <line x1="35" y1="148" x2="500" y2="148" stroke="#334155" stroke-width="1"/>
      <line x1="35" y1="{140-int(0.80*120)}" x2="500" y2="{140-int(0.80*120)}" stroke="#22c55e" stroke-width="1" stroke-dasharray="4,3"/>
      <text x="505" y="{140-int(0.80*120)+4}" fill="#22c55e" font-size="9">80%</text>
      {bar_svg}
    </svg>
    <p style="font-size:11px;color:#f59e0b;margin:8px 0 0">⚠ Bimanual (38%), Pour (41%), Sweep (62%) under-represented — collect 14 additional episodes to reach 80% threshold</p>
  </div>
</div>
</body>
</html>"""

if USE_FASTAPI:
    app = FastAPI(title="Episode Diversity Analyzer")
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
