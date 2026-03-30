"""Force-Torque Analyzer — FastAPI port 8436"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8436

def build_html():
    steps = list(range(0, 848, 8))
    # 6-axis F/T trajectory
    axes_ft = ["Fx","Fy","Fz","Tx","Ty","Tz"]
    ax_colors = ["#C74634","#38bdf8","#22c55e","#f59e0b","#a78bfa","#94a3b8"]

    # Fz trajectory with grasp event
    grasp_step = 320
    fz = []
    for s in steps:
        if s < grasp_step - 40:
            v = 0.5 + random.gauss(0, 0.3)
        elif s < grasp_step:
            v = 0.5 + (s - (grasp_step-40))/40 * 8.0 + random.gauss(0,0.4)
        elif s < grasp_step + 80:
            v = 8.2 + random.gauss(0, 0.5)
        else:
            v = 4.1 + random.gauss(0, 0.3)
        fz.append(max(-1, v))

    svg_traj = '<svg width="420" height="200" style="background:#0f172a">'
    svg_traj += '<line x1="50" y1="10" x2="50" y2="170" stroke="#475569" stroke-width="1"/>'
    svg_traj += '<line x1="50" y1="170" x2="400" y2="170" stroke="#475569" stroke-width="1"/>'
    for i in range(5):
        yv = i*3.0; y = 170-yv*140/12
        svg_traj += f'<text x="45" y="{y+4}" fill="#94a3b8" font-size="7" text-anchor="end">{yv:.0f}N</text>'
    fz_pts = [(50+(s/847)*340, 170-v*140/12) for s,v in zip(steps, fz)]
    for j in range(len(fz_pts)-1):
        x1,y1=fz_pts[j]; x2,y2=fz_pts[j+1]
        svg_traj += f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#22c55e" stroke-width="1.5"/>'
    # Grasp event marker
    gx = 50+(grasp_step/847)*340
    svg_traj += f'<line x1="{gx:.0f}" y1="10" x2="{gx:.0f}" y2="170" stroke="#C74634" stroke-width="1.5" stroke-dasharray="4,3"/>'
    svg_traj += f'<text x="{gx+3:.0f}" y="25" fill="#C74634" font-size="8">grasp (Fz=8.2N)</text>'
    # Hard contact threshold
    thresh_y = 170-15*140/12
    svg_traj += f'<line x1="50" y1="{thresh_y:.0f}" x2="400" y2="{thresh_y:.0f}" stroke="#f59e0b" stroke-width="1" stroke-dasharray="3,2"/>'
    svg_traj += f'<text x="405" y="{thresh_y:.0f}" fill="#f59e0b" font-size="7">15N limit</text>'
    svg_traj += '<text x="225" y="190" fill="#94a3b8" font-size="9" text-anchor="middle">Episode Steps — Fz Force Trajectory</text>'
    svg_traj += '</svg>'

    # Grasp quality scatter (Fz × Tz, 200 episodes)
    svg_sc2 = '<svg width="320" height="200" style="background:#0f172a">'
    svg_sc2 += '<line x1="40" y1="10" x2="40" y2="170" stroke="#475569" stroke-width="1"/>'
    svg_sc2 += '<line x1="40" y1="170" x2="300" y2="170" stroke="#475569" stroke-width="1"/>'
    for i in range(5):
        yv = i*0.2; y = 170-yv*140
        svg_sc2 += f'<text x="35" y="{y+4}" fill="#94a3b8" font-size="7" text-anchor="end">{yv:.1f}Nm</text>'
    for i in range(5):
        xv = i*3; x = 40+xv*240/12
        svg_sc2 += f'<text x="{x}" y="183" fill="#94a3b8" font-size="7" text-anchor="middle">{xv}N</text>'
    for _ in range(100):  # success
        fz_v = random.gauss(8.2, 1.2); tz_v = random.gauss(0.55, 0.08)
        cx3 = 40+max(0,fz_v)*240/12; cy3 = 170-max(0,tz_v)*140
        svg_sc2 += f'<circle cx="{cx3:.0f}" cy="{cy3:.0f}" r="3" fill="#22c55e" opacity="0.6"/>'
    for _ in range(100):  # fail
        fz_v = random.gauss(4.1, 2.0); tz_v = random.gauss(0.25, 0.12)
        cx3 = 40+max(0,fz_v)*240/12; cy3 = 170-max(0,tz_v)*140
        svg_sc2 += f'<circle cx="{cx3:.0f}" cy="{cy3:.0f}" r="3" fill="#C74634" opacity="0.6"/>'
    # Optimal region box
    opt_x = 40+6*240/12; opt_w = 40+11*240/12-opt_x
    opt_y = 170-0.75*140; opt_h = 170-0.4*140-opt_y
    svg_sc2 += f'<rect x="{opt_x:.0f}" y="{opt_y:.0f}" width="{opt_w:.0f}" height="{opt_h:.0f}" fill="none" stroke="#f59e0b" stroke-width="1.5" stroke-dasharray="4,3"/>'
    svg_sc2 += f'<text x="{opt_x+opt_w/2:.0f}" y="{opt_y-4:.0f}" fill="#f59e0b" font-size="7">optimal (6-11N, 0.4-0.75Nm)</text>'
    svg_sc2 += '<text x="170" y="197" fill="#94a3b8" font-size="9" text-anchor="middle">Fz Contact Force → Grasp Torque (green=success)</text>'
    svg_sc2 += '</svg>'

    return f"""<!DOCTYPE html><html><head><title>Force-Torque Analyzer — Port {PORT}</title>
<style>body{{background:#0f172a;color:#e2e8f0;font-family:monospace;margin:0;padding:20px}}
h1{{color:#C74634;font-size:18px}}h2{{color:#38bdf8;font-size:14px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:20px}}
.card{{background:#1e293b;padding:16px;border-radius:8px}}
.stat{{font-size:24px;color:#C74634;font-weight:bold}}
.label{{color:#94a3b8;font-size:12px}}</style></head>
<body><h1>Force-Torque Analyzer</h1>
<p style="color:#94a3b8">Port {PORT} | 6-axis F/T trajectory + grasp quality scatter</p>
<div class="grid">
<div class="card"><h2>Fz Force Trajectory (847 steps)</h2>{svg_traj}
<div class="stat">8.2N</div><div class="label">Optimal contact force at grasp event</div></div>
<div class="card"><h2>Grasp Quality (Fz × Tz)</h2>{svg_sc2}
<div style="margin-top:8px">
<div class="stat">6-11N</div><div class="label">Optimal Fz range for successful grasp</div>
<div style="margin-top:8px;color:#94a3b8;font-size:11px">Hard-contact detection threshold: &gt;15N → e-stop<br>Soft contact: 2-6N (partial grasp, higher drop rate)<br>Torque Tz 0.4-0.75Nm = stable object orientation<br>84% of failures: Fz &lt; 5N (insufficient grip force)</div>
</div></div></div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Force-Torque Analyzer")
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
