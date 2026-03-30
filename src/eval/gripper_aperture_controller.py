"""Gripper Aperture Controller — FastAPI port 8590"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8590

def build_html():
    # Gripper width trajectory SVG: planned vs actual aperture, 200 steps
    steps = 200
    planned = []
    actual = []
    for i in range(steps):
        t = i / steps
        if t < 0.3:
            p = 0.08
        elif t < 0.5:
            p = 0.08 - (t - 0.3) / 0.2 * 0.06
        elif t < 0.7:
            p = 0.02
        else:
            p = 0.02 + (t - 0.7) / 0.3 * 0.06
        planned.append(p)
        noise = random.gauss(0, 0.0008)
        actual.append(max(0.01, p + noise))

    W, H = 620, 160
    def px(i): return 40 + i * (W - 60) / steps
    def py(v): return H - 20 - (v / 0.10) * (H - 40)

    path_p = " ".join(f"{'M' if i==0 else 'L'}{px(i):.1f},{py(planned[i]):.1f}" for i in range(steps))
    path_a = " ".join(f"{'M' if i==0 else 'L'}{px(i):.1f},{py(actual[i]):.1f}" for i in range(steps))

    # Aperture success heatmap: target width x object size
    targets = [0.02, 0.04, 0.06, 0.08]
    obj_sizes = [0.02, 0.04, 0.06, 0.08, 0.10]
    heatmap_cells = ""
    for ti, tw in enumerate(targets):
        for oi, oz in enumerate(obj_sizes):
            diff = abs(tw - oz)
            sr = max(0.3, 0.95 - diff * 8)
            r = int(255 * (1 - sr))
            g = int(200 * sr)
            b = 60
            heatmap_cells += f'<rect x="{80 + ti*70}" y="{20 + oi*40}" width="65" height="35" fill="rgb({r},{g},{b})" rx="3"/>'
            heatmap_cells += f'<text x="{112 + ti*70}" y="{42 + oi*40}" text-anchor="middle" font-size="11" fill="white">{sr:.2f}</text>'

    return f"""<!DOCTYPE html>
<html><head><title>Gripper Aperture Controller</title>
<style>body{{background:#0f172a;color:#e2e8f0;font-family:sans-serif;margin:0;padding:20px}}
h1{{color:#C74634;font-size:18px}}h2{{color:#38bdf8;font-size:14px;margin-top:20px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}.card{{background:#1e293b;padding:16px;border-radius:8px}}
.metric{{font-size:28px;font-weight:bold;color:#38bdf8}}.label{{font-size:12px;color:#94a3b8}}
</style></head><body>
<h1>Gripper Aperture Controller — Port {PORT}</h1>
<div class="grid">
<div class="card">
<h2>Aperture Trajectory (200 steps)</h2>
<svg width="{W}" height="{H}" style="background:#0f172a">
  <line x1="40" y1="{H-20}" x2="{W-20}" y2="{H-20}" stroke="#334155" stroke-width="1"/>
  <line x1="40" y1="10" x2="40" y2="{H-20}" stroke="#334155" stroke-width="1"/>
  <text x="20" y="{py(0.08):.0f}" font-size="9" fill="#64748b">8cm</text>
  <text x="20" y="{py(0.04):.0f}" font-size="9" fill="#64748b">4cm</text>
  <text x="20" y="{py(0.02):.0f}" font-size="9" fill="#64748b">2cm</text>
  <path d="{path_p}" fill="none" stroke="#38bdf8" stroke-width="2"/>
  <path d="{path_a}" fill="none" stroke="#C74634" stroke-width="1.5" stroke-dasharray="4,2"/>
  <line x1="{px(100):.1f}" y1="10" x2="{px(100):.1f}" y2="{H-20}" stroke="#f59e0b" stroke-width="1" stroke-dasharray="3,3"/>
  <text x="{px(100)-5:.0f}" y="20" font-size="9" fill="#f59e0b">contact</text>
  <text x="50" y="15" font-size="9" fill="#38bdf8">● planned</text>
  <text x="130" y="15" font-size="9" fill="#C74634">– – actual</text>
</svg>
</div>
<div class="card">
<h2>Success Rate Heatmap (target × object size)</h2>
<svg width="380" height="240" style="background:#0f172a">
  {heatmap_cells}
  <text x="80" y="15" font-size="9" fill="#64748b">2mm</text>
  <text x="150" y="15" font-size="9" fill="#64748b">4mm</text>
  <text x="220" y="15" font-size="9" fill="#64748b">6mm</text>
  <text x="290" y="15" font-size="9" fill="#64748b">8mm target</text>
  <text x="20" y="45" font-size="9" fill="#64748b" transform="rotate(-90,20,45)">obj sz</text>
</svg>
</div>
</div>
<div class="grid" style="margin-top:12px">
<div class="card">
<h2>Key Metrics</h2>
<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
  <div><div class="metric">±1.2mm</div><div class="label">aperture accuracy</div></div>
  <div><div class="metric">94%</div><div class="label">contact re-close success</div></div>
  <div><div class="metric">0.8mm</div><div class="label">position error σ</div></div>
  <div><div class="metric">16-step</div><div class="label">action chunk</div></div>
</div>
</div>
<div class="card">
<h2>Position Error Distribution</h2>
<svg width="280" height="120" style="background:#0f172a">
  {''.join(f'<rect x="{30 + i*22}" y="{100 - int(60*math.exp(-0.5*((i-6)/2)**2))}" width="20" height="{int(60*math.exp(-0.5*((i-6)/2)**2))}" fill="#38bdf8" rx="2"/>' for i in range(13))}
  <line x1="30" y1="100" x2="320" y2="100" stroke="#334155" stroke-width="1"/>
  <text x="155" y="118" text-anchor="middle" font-size="9" fill="#64748b">error (mm)</text>
</svg>
</div>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Gripper Aperture Controller")
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
