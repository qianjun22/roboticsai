"""Policy Generalization Tester — FastAPI port 8452"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8452

def build_html():
    # 3-category generalization bar
    categories = ["In-Distribution", "Near-OOD", "Far-OOD (Adversarial)"]
    sr_groot = [0.78, 0.71, 0.39]
    sr_bc = [0.51, 0.31, 0.12]
    gen_bars = ""
    for i, (cat, sg, sb) in enumerate(zip(categories, sr_groot, sr_bc)):
        x = 20 + i * 155
        hg = int(sg * 160)
        hb = int(sb * 160)
        gen_bars += f'<rect x="{x}" y="{170-hg}" width="55" height="{hg}" fill="#C74634" rx="3"/>'
        gen_bars += f'<rect x="{x+58}" y="{170-hb}" width="55" height="{hb}" fill="#64748b" opacity="0.7" rx="3"/>'
        gen_bars += f'<text x="{x+57}" y="186" fill="#94a3b8" font-size="9" text-anchor="middle">{cat}</text>'
        gen_bars += f'<text x="{x+28}" y="{170-hg-4}" fill="#38bdf8" font-size="9" text-anchor="middle">{int(sg*100)}%</text>'
        gen_bars += f'<text x="{x+86}" y="{170-hb-4}" fill="#94a3b8" font-size="9" text-anchor="middle">{int(sb*100)}%</text>'

    # failure mode heatmap
    failure_categories = ["Lighting", "Texture", "Position", "Object Size", "Clutter"]
    ood_types = ["Near-OOD", "Far-OOD"]
    failure_rates = [[0.12, 0.18, 0.21, 0.15, 0.24], [0.41, 0.55, 0.48, 0.38, 0.63]]
    heat = ""
    for j, ood in enumerate(ood_types):
        for i, cat in enumerate(failure_categories):
            v = failure_rates[j][i]
            x = 100 + i * 80
            y = 20 + j * 50
            if v < 0.20:
                color = "#22c55e"
            elif v < 0.40:
                color = "#f59e0b"
            else:
                color = "#C74634"
            heat += f'<rect x="{x}" y="{y}" width="74" height="42" fill="{color}" opacity="0.8" rx="4"/>'
            heat += f'<text x="{x+37}" y="{y+25}" fill="#0f172a" font-size="12" font-weight="bold" text-anchor="middle">{int(v*100)}%</text>'
        heat += f'<text x="95" y="{20+j*50+25}" fill="#94a3b8" font-size="11" text-anchor="end">{ood}</text>'
    for i, cat in enumerate(failure_categories):
        heat += f'<text x="{137+i*80}" y="130" fill="#94a3b8" font-size="10" text-anchor="middle">{cat}</text>'

    return f"""<!DOCTYPE html>
<html>
<head><title>Policy Generalization Tester</title>
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
.delta{{font-size:12px;color:#22c55e;margin-top:4px}}
.legend{{display:flex;gap:12px;margin-top:8px}}
.li{{display:flex;align-items:center;gap:5px;font-size:11px}}
.ld{{width:12px;height:12px;border-radius:2px}}
</style>
</head>
<body>
<div class="hdr">
  <span class="badge">PORT {PORT}</span>
  <h1>Policy Generalization Tester — OOD Robustness</h1>
</div>
<div class="metrics">
  <div class="m"><div class="mv">78%</div><div class="ml">In-Distribution SR</div></div>
  <div class="m"><div class="mv">71%</div><div class="ml">Near-OOD SR</div><div class="delta">-7pp drop</div></div>
  <div class="m"><div class="mv">39%</div><div class="ml">Far-OOD SR</div></div>
  <div class="m"><div class="mv">63%</div><div class="ml">BC Near-OOD Failure</div></div>
</div>
<div class="grid">
  <div class="card">
    <h3>SR by Generalization Category</h3>
    <svg viewBox="0 0 500 200" width="100%">
      <line x1="15" y1="5" x2="15" y2="175" stroke="#334155" stroke-width="1"/>
      <line x1="15" y1="175" x2="490" y2="175" stroke="#334155" stroke-width="1"/>
      {gen_bars}
    </svg>
    <div class="legend">
      <div class="li"><div class="ld" style="background:#C74634"></div>GR00T_v2</div>
      <div class="li"><div class="ld" style="background:#64748b;opacity:0.7"></div>BC Baseline</div>
    </div>
  </div>
  <div class="card">
    <h3>Failure Mode Heatmap by OOD Type</h3>
    <svg viewBox="0 0 510 145" width="100%">
      {heat}
    </svg>
    <p style="font-size:11px;color:#f59e0b;margin:8px 0 0">Clutter + far-OOD 63% failure rate — priority target for augmentation sprint</p>
  </div>
</div>
</body>
</html>"""

if USE_FASTAPI:
    app = FastAPI(title="Policy Generalization Tester")
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
