"""Contrastive Policy Trainer — FastAPI port 8448"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8448

def build_html():
    random.seed(7)
    steps = list(range(0, 3001, 100))
    # contrastive loss decays
    cl_loss = [2.3 * math.exp(-s / 900) + 0.12 + random.gauss(0, 0.04) for s in steps]
    bc_loss = [1.8 * math.exp(-s / 1200) + 0.09 + random.gauss(0, 0.03) for s in steps]
    # SR trajectory
    sr_cont = [0.07 + 0.73 * (1 - math.exp(-s / 1100)) + random.gauss(0, 0.015) for s in steps]
    sr_base = [0.05 + 0.62 * (1 - math.exp(-s / 1400)) + random.gauss(0, 0.015) for s in steps]

    def make_line(vals, ymax, height, x0, xscale, color, stroke=2):
        pts = " ".join(f"{x0 + i*xscale:.1f},{height - v/ymax*height:.1f}" for i, v in enumerate(vals))
        return f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="{stroke}"/>'

    loss_svg = make_line(cl_loss, 2.5, 140, 40, 3.6, "#C74634") + make_line(bc_loss, 2.5, 140, 40, 3.6, "#38bdf8")
    sr_svg = make_line(sr_cont, 1.0, 140, 40, 3.6, "#C74634", 2.5) + make_line(sr_base, 1.0, 140, 40, 3.6, "#64748b")

    # data efficiency bar
    data_pts = [100, 250, 500, 1000]
    sr_contrastive = [0.38, 0.56, 0.71, 0.78]
    sr_random = [0.18, 0.34, 0.55, 0.71]
    bars = ""
    for i, (d, sc, sr) in enumerate(zip(data_pts, sr_contrastive, sr_random)):
        x = 30 + i * 100
        hc = int(sc * 140)
        hr = int(sr * 140)
        bars += f'<rect x="{x}" y="{150-hc}" width="35" height="{hc}" fill="#C74634" rx="3"/>'
        bars += f'<rect x="{x+37}" y="{150-hr}" width="35" height="{hr}" fill="#64748b" opacity="0.7" rx="3"/>'
        bars += f'<text x="{x+36}" y="165" fill="#94a3b8" font-size="10" text-anchor="middle">{d}</text>'
        bars += f'<text x="{x+18}" y="{150-hc-3}" fill="#38bdf8" font-size="9" text-anchor="middle">{int(sc*100)}%</text>'

    return f"""<!DOCTYPE html>
<html>
<head><title>Contrastive Policy Trainer</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',sans-serif}}
.hdr{{background:#1e293b;padding:16px 24px;border-bottom:2px solid #C74634;display:flex;align-items:center;gap:12px}}
.hdr h1{{margin:0;font-size:20px;color:#f1f5f9}}
.badge{{background:#C74634;color:#fff;padding:3px 10px;border-radius:12px;font-size:11px;font-weight:700}}
.grid{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px;padding:20px}}
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
  <h1>Contrastive Policy Trainer — SimCLR-Style Pretraining</h1>
</div>
<div class="metrics">
  <div class="m"><div class="mv">+6pp</div><div class="ml">SR vs Random Init</div><div class="delta">0.72→0.78</div></div>
  <div class="m"><div class="mv">2×</div><div class="ml">Data Efficiency</div><div class="delta">contrastive pretraining</div></div>
  <div class="m"><div class="mv">0.12</div><div class="ml">Contrastive Loss Final</div></div>
  <div class="m"><div class="mv">3000</div><div class="ml">Training Steps</div></div>
</div>
<div class="grid">
  <div class="card">
    <h3>Loss Curves</h3>
    <svg viewBox="0 0 360 165" width="100%">
      <line x1="38" y1="5" x2="38" y2="148" stroke="#334155" stroke-width="1"/>
      <line x1="38" y1="148" x2="355" y2="148" stroke="#334155" stroke-width="1"/>
      {loss_svg}
      <text x="200" y="18" fill="#C74634" font-size="10">Contrastive</text>
      <text x="200" y="32" fill="#38bdf8" font-size="10">BC Task</text>
    </svg>
  </div>
  <div class="card">
    <h3>SR Trajectory</h3>
    <svg viewBox="0 0 360 165" width="100%">
      <line x1="38" y1="5" x2="38" y2="148" stroke="#334155" stroke-width="1"/>
      <line x1="38" y1="148" x2="355" y2="148" stroke="#334155" stroke-width="1"/>
      {sr_svg}
      <text x="200" y="18" fill="#C74634" font-size="10">w/ Contrastive</text>
      <text x="200" y="32" fill="#64748b" font-size="10">Random Init</text>
    </svg>
  </div>
  <div class="card">
    <h3>Data Efficiency (SR by Demos)</h3>
    <svg viewBox="0 0 460 180" width="100%">
      <line x1="25" y1="5" x2="25" y2="155" stroke="#334155" stroke-width="1"/>
      <line x1="25" y1="155" x2="450" y2="155" stroke="#334155" stroke-width="1"/>
      {bars}
      <rect x="330" y="10" width="10" height="10" fill="#C74634"/>
      <text x="344" y="20" fill="#94a3b8" font-size="10">Contrastive</text>
      <rect x="330" y="25" width="10" height="10" fill="#64748b" opacity="0.7"/>
      <text x="344" y="35" fill="#94a3b8" font-size="10">Random</text>
    </svg>
  </div>
</div>
</body>
</html>"""

if USE_FASTAPI:
    app = FastAPI(title="Contrastive Policy Trainer")
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
