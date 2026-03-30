"""Reward Shaping V3 — FastAPI port 8444"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8444

def build_html():
    # reward weight bar chart SVG
    categories = ["Grasp", "Lift", "Smooth", "Place", "Safety"]
    weights_v2 = [0.30, 0.25, 0.15, 0.20, 0.10]
    weights_v3 = [0.35, 0.28, 0.18, 0.12, 0.07]
    colors_v2 = "#64748b"
    colors_v3 = "#C74634"
    bar_svg = ""
    for i, (cat, w2, w3) in enumerate(zip(categories, weights_v2, weights_v3)):
        x = 60 + i * 90
        h2 = int(w2 * 400)
        h3 = int(w3 * 400)
        y2 = 200 - h2
        y3 = 200 - h3
        bar_svg += f'<rect x="{x}" y="{y2}" width="30" height="{h2}" fill="{colors_v2}" opacity="0.7"/>'
        bar_svg += f'<rect x="{x+32}" y="{y3}" width="30" height="{h3}" fill="{colors_v3}"/>'
        bar_svg += f'<text x="{x+31}" y="218" fill="#94a3b8" font-size="11" text-anchor="middle">{cat}</text>'
        bar_svg += f'<text x="{x+47}" y="{y3-4}" fill="#38bdf8" font-size="10" text-anchor="middle">{w3}</text>'

    # run comparison line chart
    runs = list(range(1, 11))
    sr_v2 = [0.05, 0.12, 0.21, 0.31, 0.38, 0.44, 0.51, 0.57, 0.62, 0.65]
    sr_v3_proj = [0.07, 0.16, 0.28, 0.39, 0.48, 0.57, 0.65, 0.72, 0.78, 0.84]
    line2 = ""
    line3 = ""
    for i, (r, v2, v3) in enumerate(zip(runs, sr_v2, sr_v3_proj)):
        x = 40 + i * 52
        y2 = int(180 - v2 * 160)
        y3 = int(180 - v3 * 160)
        if i > 0:
            px = 40 + (i-1)*52
            py2 = int(180 - sr_v2[i-1]*160)
            py3 = int(180 - sr_v3_proj[i-1]*160)
            line2 += f'<line x1="{px}" y1="{py2}" x2="{x}" y2="{y2}" stroke="#64748b" stroke-width="2"/>'
            line3 += f'<line x1="{px}" y1="{py3}" x2="{x}" y2="{y3}" stroke="#C74634" stroke-width="2.5"/>'
        line2 += f'<circle cx="{x}" cy="{y2}" r="4" fill="#64748b"/>'
        line3 += f'<circle cx="{x}" cy="{y3}" r="4" fill="#C74634"/>'

    return f"""<!DOCTYPE html>
<html>
<head><title>Reward Shaping V3</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',sans-serif}}
.hdr{{background:#1e293b;padding:16px 24px;border-bottom:2px solid #C74634;display:flex;align-items:center;gap:12px}}
.hdr h1{{margin:0;font-size:20px;color:#f1f5f9}}
.badge{{background:#C74634;color:#fff;padding:3px 10px;border-radius:12px;font-size:11px;font-weight:700}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;padding:20px}}
.card{{background:#1e293b;border-radius:10px;padding:18px;border:1px solid #334155}}
.card h3{{margin:0 0 12px;font-size:14px;color:#94a3b8;text-transform:uppercase;letter-spacing:.05em}}
.metrics{{display:grid;grid-template-columns:1fr 1fr;gap:10px;padding:16px 20px}}
.m{{background:#1e293b;border-radius:8px;padding:12px 16px;border:1px solid #334155}}
.mv{{font-size:26px;font-weight:700;color:#38bdf8}}
.ml{{font-size:11px;color:#64748b;margin-top:2px}}
.delta{{font-size:12px;color:#22c55e;margin-top:4px}}
</style>
</head>
<body>
<div class="hdr">
  <span class="badge">PORT {PORT}</span>
  <h1>Reward Shaping V3 — DAgger Run11 Optimizer</h1>
</div>
<div class="metrics">
  <div class="m"><div class="mv">0.35</div><div class="ml">Grasp Weight</div><div class="delta">▲ +0.05 vs v2</div></div>
  <div class="m"><div class="mv">0.28</div><div class="ml">Lift Weight</div><div class="delta">▲ +0.03 vs v2</div></div>
  <div class="m"><div class="mv">84%</div><div class="ml">Projected SR (run11)</div><div class="delta">▲ +19pp vs run10</div></div>
  <div class="m"><div class="mv">0.18</div><div class="ml">Smoothness Weight</div><div class="delta">▲ +0.03 vs v2</div></div>
</div>
<div class="grid">
  <div class="card">
    <h3>Reward Weights: V2 vs V3</h3>
    <svg viewBox="0 0 530 240" width="100%">
      <line x1="55" y1="10" x2="55" y2="205" stroke="#334155" stroke-width="1"/>
      <line x1="55" y1="205" x2="520" y2="205" stroke="#334155" stroke-width="1"/>
      {bar_svg}
      <rect x="360" y="15" width="12" height="12" fill="{colors_v2}" opacity="0.7"/>
      <text x="376" y="26" fill="#94a3b8" font-size="11">V2</text>
      <rect x="400" y="15" width="12" height="12" fill="{colors_v3}"/>
      <text x="416" y="26" fill="#94a3b8" font-size="11">V3 (run11)</text>
    </svg>
  </div>
  <div class="card">
    <h3>Projected SR Trajectory: V2 vs V3</h3>
    <svg viewBox="0 0 560 200" width="100%">
      <line x1="35" y1="10" x2="35" y2="185" stroke="#334155" stroke-width="1"/>
      <line x1="35" y1="185" x2="550" y2="185" stroke="#334155" stroke-width="1"/>
      {line2}
      {line3}
      <text x="530" y="185" fill="#94a3b8" font-size="10">Run 10</text>
      <text x="440" y="25" fill="#C74634" font-size="11">V3: 84% target</text>
      <text x="440" y="85" fill="#64748b" font-size="11">V2: 65% actual</text>
    </svg>
  </div>
</div>
</body>
</html>"""

if USE_FASTAPI:
    app = FastAPI(title="Reward Shaping V3")
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
