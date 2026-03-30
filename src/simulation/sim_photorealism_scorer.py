"""Sim Photorealism Scorer — FastAPI port 8466"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8466

def build_html():
    # FID/SSIM/LPIPS comparison
    modes = ["Basic", "Domain Rand", "RTX Render", "Cosmos WM"]
    fid = [142.3, 89.7, 31.2, 18.3]
    ssim = [0.41, 0.58, 0.74, 0.89]
    lpips = [0.52, 0.38, 0.21, 0.11]
    colors = ["#64748b", "#38bdf8", "#f59e0b", "#22c55e"]

    fid_bars = ""
    for i, (m, f, color) in enumerate(zip(modes, fid, colors)):
        x = 20 + i * 110
        h = int(f / 160 * 140)
        fid_bars += f'<rect x="{x}" y="{150-h}" width="76" height="{h}" fill="{color}" rx="4" opacity="0.85"/>'
        fid_bars += f'<text x="{x+38}" y="165" fill="#94a3b8" font-size="10" text-anchor="middle">{m}</text>'
        fid_bars += f'<text x="{x+38}" y="{150-h-4}" fill="#e2e8f0" font-size="10" text-anchor="middle">{f}</text>'
    fid_bars += f'<line x1="15" y1="{150-18.3/160*140:.1f}" x2="470" y2="{150-18.3/160*140:.1f}" stroke="#22c55e" stroke-width="1.5" stroke-dasharray="4,3"/>'
    fid_bars += f'<text x="472" y="{150-18.3/160*140+4:.1f}" fill="#22c55e" font-size="9">Real=0</text>'

    # fidelity vs SR scatter
    scatter = ""
    fidelity_scores = [0.28, 0.45, 0.74, 0.89, 1.0]
    sr_vals_sim = [0.41, 0.55, 0.69, 0.78, 0.78]
    labels = ["Basic", "DR", "RTX", "Cosmos", "Real"]
    scatter_colors = ["#64748b", "#38bdf8", "#f59e0b", "#22c55e", "#C74634"]
    prev_x, prev_y = None, None
    for fid_n, sr, label, color in zip(fidelity_scores, sr_vals_sim, labels, scatter_colors):
        x = 30 + fid_n * 220
        y = 170 - sr * 150
        scatter += f'<circle cx="{x:.1f}" cy="{y:.1f}" r="7" fill="{color}" opacity="0.85"/>'
        scatter += f'<text x="{x+10:.1f}" y="{y+4:.1f}" fill="{color}" font-size="10">{label}</text>'
        if prev_x is not None:
            scatter += f'<line x1="{prev_x:.1f}" y1="{prev_y:.1f}" x2="{x:.1f}" y2="{y:.1f}" stroke="#334155" stroke-width="1.5" stroke-dasharray="3,3"/>'
        prev_x, prev_y = x, y

    return f"""<!DOCTYPE html>
<html>
<head><title>Sim Photorealism Scorer</title>
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
</style>
</head>
<body>
<div class="hdr">
  <span class="badge">PORT {PORT}</span>
  <h1>Sim Photorealism Scorer — FID/SSIM/LPIPS</h1>
</div>
<div class="metrics">
  <div class="m"><div class="mv">18.3</div><div class="ml">Cosmos FID (best)</div><div class="delta">vs Basic 142.3</div></div>
  <div class="m"><div class="mv">0.89</div><div class="ml">Cosmos SSIM</div></div>
  <div class="m"><div class="mv">r=0.82</div><div class="ml">Fidelity vs SR Corr</div></div>
  <div class="m"><div class="mv">Cosmos WM</div><div class="ml">Recommended Sim</div></div>
</div>
<div class="grid">
  <div class="card">
    <h3>FID Score by Rendering Mode (lower=better)</h3>
    <svg viewBox="0 0 470 180" width="100%">
      <line x1="15" y1="10" x2="15" y2="153" stroke="#334155" stroke-width="1"/>
      <line x1="15" y1="153" x2="465" y2="153" stroke="#334155" stroke-width="1"/>
      {fid_bars}
    </svg>
  </div>
  <div class="card">
    <h3>Visual Fidelity vs SR (direct correlation)</h3>
    <svg viewBox="0 0 310 195" width="100%">
      <line x1="25" y1="10" x2="25" y2="178" stroke="#334155" stroke-width="1"/>
      <line x1="25" y1="178" x2="300" y2="178" stroke="#334155" stroke-width="1"/>
      {scatter}
      <text x="165" y="193" fill="#64748b" font-size="9" text-anchor="middle">Fidelity Score →</text>
      <text x="12" y="95" fill="#64748b" font-size="9" transform="rotate(-90,12,95)">SR ↑</text>
    </svg>
  </div>
</div>
</body>
</html>"""

if USE_FASTAPI:
    app = FastAPI(title="Sim Photorealism Scorer")
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
