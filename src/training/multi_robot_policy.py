"""Multi-Robot Policy Tracker — FastAPI port 8401"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8401

def build_html():
    robots = ["Franka","UR5e","xArm6","Stretch","Spot"]
    tasks = ["pick_place","stack","pour","insert","fold"]
    sr_matrix = [
        [0.78,0.71,0.62,0.54,0.41],
        [0.73,0.68,0.57,0.49,0.37],
        [0.71,0.65,0.55,0.47,0.34],
        [0.58,0.51,0.43,0.38,0.27],
        [0.44,0.39,0.31,0.26,0.18]
    ]
    # Cross-robot SR grouped bar
    colors = ["#C74634","#38bdf8","#22c55e","#f59e0b","#a78bfa"]
    bw = 28; gap = 8; grp = len(robots)*(bw+2)+gap
    svg_b = f'<svg width="420" height="200" style="background:#0f172a">'
    svg_b += '<line x1="50" y1="10" x2="50" y2="170" stroke="#475569" stroke-width="1"/>'
    svg_b += '<line x1="50" y1="170" x2="410" y2="170" stroke="#475569" stroke-width="1"/>'
    for i in range(6):
        yv = i*0.2; y = 170-yv*140/1.0
        svg_b += f'<line x1="48" y1="{y}" x2="410" y2="{y}" stroke="#1e293b" stroke-width="1"/>'
        svg_b += f'<text x="45" y="{y+4}" fill="#94a3b8" font-size="8" text-anchor="end">{yv:.1f}</text>'
    for ti, task in enumerate(tasks):
        for ri, (robot, col) in enumerate(zip(robots, colors)):
            sr = sr_matrix[ri][ti]
            x = 55 + ti*grp + ri*(bw+2)
            h = sr*140; y = 170-h
            svg_b += f'<rect x="{x}" y="{y:.0f}" width="{bw}" height="{h:.0f}" fill="{col}" opacity="0.85"/>'
        tx = 55 + ti*grp + (len(robots)*(bw+2))//2
        svg_b += f'<text x="{tx}" y="182" fill="#94a3b8" font-size="8" text-anchor="middle">{task}</text>'
    for ri, (robot, col) in enumerate(zip(robots, colors)):
        svg_b += f'<rect x="{55+ri*70}" y="192" width="12" height="8" fill="{col}"/>'
        svg_b += f'<text x="{70+ri*70}" y="200" fill="#94a3b8" font-size="8">{robot}</text>'
    svg_b += '</svg>'

    # Transfer efficiency bar
    eff = [1.0, 0.89, 0.85, 0.71, 0.52]
    svg_t = '<svg width="320" height="180" style="background:#0f172a">'
    for ri, (robot, e, col) in enumerate(zip(robots, eff, colors)):
        y = 20+ri*30; w = int(e*220)
        svg_t += f'<rect x="80" y="{y}" width="{w}" height="20" fill="{col}" opacity="0.85"/>'
        svg_t += f'<text x="75" y="{y+14}" fill="#94a3b8" font-size="10" text-anchor="end">{robot}</text>'
        svg_t += f'<text x="{82+w}" y="{y+14}" fill="white" font-size="10">{e:.0%}</text>'
    svg_t += '<text x="190" y="170" fill="#94a3b8" font-size="9" text-anchor="middle">Transfer Efficiency vs Franka Baseline</text>'
    svg_t += '</svg>'

    return f"""<!DOCTYPE html><html><head><title>Multi-Robot Policy — Port {PORT}</title>
<style>body{{background:#0f172a;color:#e2e8f0;font-family:monospace;margin:0;padding:20px}}
h1{{color:#C74634;font-size:18px}}h2{{color:#38bdf8;font-size:14px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:20px}}
.card{{background:#1e293b;padding:16px;border-radius:8px}}
.stat{{font-size:24px;color:#C74634;font-weight:bold}}
.label{{color:#94a3b8;font-size:12px}}</style></head>
<body><h1>Multi-Robot Policy Tracker</h1>
<p style="color:#94a3b8">Port {PORT} | Shared backbone + per-robot adapter heads</p>
<div class="grid">
<div class="card"><h2>Cross-Robot SR by Task</h2>{svg_b}</div>
<div class="card"><h2>Transfer Efficiency vs Franka</h2>{svg_t}
<div style="margin-top:10px">
<div class="stat">0.78</div><div class="label">Franka source SR (best)</div>
<div class="stat" style="color:#38bdf8;margin-top:8px">89%</div><div class="label">UR5e transfer efficiency</div>
<div style="margin-top:8px;color:#94a3b8;font-size:11px">Architecture: shared ViT backbone + LoRA adapters<br>Spot worst: 52% transfer (morphology gap)<br>UR5e/xArm6 best: similar kinematics to Franka<br>Stretch: extended reach changes grasp strategy</div>
</div></div></div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Multi-Robot Policy Tracker")
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
