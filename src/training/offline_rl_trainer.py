"""Offline RL Trainer — FastAPI port 8453"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8453

def build_html():
    random.seed(19)
    steps = list(range(0, 2001, 50))
    # CQL loss convergence
    cql_loss = [3.2 * math.exp(-s / 600) + 0.41 + random.gauss(0, 0.06) for s in steps]
    q_vals = [0.08 + 0.72 * (1 - math.exp(-s / 700)) + random.gauss(0, 0.02) for s in steps]

    def poly(vals, ymax, h, x0, xscale, color, stroke=2):
        pts = " ".join(f"{x0+i*xscale:.1f},{h - v/ymax*h:.1f}" for i, v in enumerate(vals))
        return f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="{stroke}"/>'

    loss_svg = poly(cql_loss, 3.5, 130, 40, 5.5, "#C74634")
    q_svg = poly(q_vals, 1.0, 130, 40, 5.5, "#22c55e")

    # SR comparison: offline vs combined vs online
    methods = ["BC Only", "Offline RL\n(CQL)", "Offline+\nDAgger(10)", "Online\nDAgger(10)"]
    sr_vals = [0.51, 0.68, 0.78, 0.78]
    comp_bars = ""
    for i, (m, v) in enumerate(zip(methods, sr_vals)):
        x = 30 + i * 110
        h = int(v * 170)
        color = "#22c55e" if v >= 0.75 else "#38bdf8" if v >= 0.65 else "#64748b"
        comp_bars += f'<rect x="{x}" y="{180-h}" width="72" height="{h}" fill="{color}" rx="4" opacity="0.85"/>'
        label = m.replace("\\n", " ")
        comp_bars += f'<text x="{x+36}" y="196" fill="#94a3b8" font-size="9" text-anchor="middle">{label}</text>'
        comp_bars += f'<text x="{x+36}" y="{180-h-4}" fill="#e2e8f0" font-size="10" text-anchor="middle">{int(v*100)}%</text>'

    return f"""<!DOCTYPE html>
<html>
<head><title>Offline RL Trainer</title>
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
  <h1>Offline RL Trainer — CQL Conservative Q-Learning</h1>
</div>
<div class="metrics">
  <div class="m"><div class="mv">68%</div><div class="ml">Offline RL SR</div><div class="delta">0 new env interactions</div></div>
  <div class="m"><div class="mv">+17pp</div><div class="ml">vs BC Baseline</div></div>
  <div class="m"><div class="mv">0.41</div><div class="ml">CQL Loss Final</div></div>
  <div class="m"><div class="mv">84%</div><div class="ml">Combined Target</div><div class="delta">offline+DAgger</div></div>
</div>
<div class="grid">
  <div class="card">
    <h3>CQL Loss Curve</h3>
    <svg viewBox="0 0 370 150" width="100%">
      <line x1="38" y1="5" x2="38" y2="138" stroke="#334155" stroke-width="1"/>
      <line x1="38" y1="138" x2="365" y2="138" stroke="#334155" stroke-width="1"/>
      {loss_svg}
      <text x="300" y="25" fill="#C74634" font-size="10">CQL Loss</text>
    </svg>
  </div>
  <div class="card">
    <h3>Q-Value Convergence</h3>
    <svg viewBox="0 0 370 150" width="100%">
      <line x1="38" y1="5" x2="38" y2="138" stroke="#334155" stroke-width="1"/>
      <line x1="38" y1="138" x2="365" y2="138" stroke="#334155" stroke-width="1"/>
      {q_svg}
      <text x="300" y="25" fill="#22c55e" font-size="10">Q-Value</text>
    </svg>
  </div>
  <div class="card">
    <h3>SR Comparison by Method</h3>
    <svg viewBox="0 0 490 210" width="100%">
      <line x1="25" y1="10" x2="25" y2="185" stroke="#334155" stroke-width="1"/>
      <line x1="25" y1="185" x2="480" y2="185" stroke="#334155" stroke-width="1"/>
      {comp_bars}
    </svg>
  </div>
</div>
</body>
</html>"""

if USE_FASTAPI:
    app = FastAPI(title="Offline RL Trainer")
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
