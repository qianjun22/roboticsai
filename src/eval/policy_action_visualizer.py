"""Policy Action Visualizer — FastAPI port 8554"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8554

def build_html():
    joints = ["J1","J2","J3","J4","J5","J6","Grip"]
    colors = ["#38bdf8","#22c55e","#f59e0b","#C74634","#a78bfa","#fb923c","#e2e8f0"]
    steps = list(range(0, 200, 8))
    trajectories = {
        j: [round(0.3*math.sin(s/20 + i*0.8) + random.uniform(-0.05,0.05), 3) for s in steps]
        for i,j in enumerate(joints[:-1])
    }
    # Gripper: binary
    grip = [1.0 if s > 100 else 0.0 for s in steps]
    lines = "".join(
        f'<polyline points="{" ".join(f"{10+k*14},{120-int(v*60)}" for k,v in enumerate(trajectories[j]))}" fill="none" stroke="{c}" stroke-width="1.5"/>'
        for j,c in zip(joints[:-1], colors[:-1])
    )
    grip_pts = " ".join(f"{10+k*14},{120-int(v*40)}" for k,v in enumerate(grip))
    legend = "".join(f'<rect x="{10+i*60}" y="5" width="10" height="10" fill="{c}"/><text x="{23+i*60}" y="14" fill="#94a3b8" font-size="9">{j}</text>' for i,(j,c) in enumerate(zip(joints,colors)))
    return f"""<!DOCTYPE html><html><head><title>Policy Action Visualizer</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:monospace}}
.hdr{{background:#1e293b;padding:16px 24px;border-bottom:2px solid #C74634}}
h1{{margin:0;color:#C74634;font-size:20px}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;padding:24px}}
.card{{background:#1e293b;border-radius:8px;padding:16px;border:1px solid #334155}}
.metric{{font-size:28px;color:#38bdf8;font-weight:bold}}
.lbl{{color:#64748b;font-size:12px;margin-top:4px}}</style></head>
<body><div class="hdr"><h1>Policy Action Visualizer</h1><span style="color:#64748b">Joint trajectory analysis | Port {PORT}</span></div>
<div class="grid">
<div class="card"><div class="metric">J6</div><div class="lbl">Most Active Joint</div></div>
<div class="card"><div class="metric">120±8</div><div class="lbl">Contact Step</div></div>
<div class="card"><div class="metric">94%</div><div class="lbl">Clean Grip Transitions</div></div>
<div class="card"><div class="metric">200</div><div class="lbl">Trajectory Steps</div></div>
<div class="card" style="grid-column:span 4">
<div style="color:#94a3b8;font-size:12px;margin-bottom:8px">7-DOF JOINT TRAJECTORIES</div>
<svg width="100%" height="165" viewBox="0 0 590 165">
<g transform="translate(0,22)">{lines}
<polyline points="{grip_pts}" fill="none" stroke="#e2e8f0" stroke-width="1" stroke-dasharray="3"/>
</g>
{legend}
<line x1="10" y1="144" x2="580" y2="144" stroke="#334155" stroke-width="1"/>
</svg></div></div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Policy Action Visualizer")
    @app.get("/", response_class=HTMLResponse)
    def index(): return build_html()
    @app.get("/health")
    def health(): return {"status": "ok", "port": PORT}

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.send_header("Content-Type","text/html"); self.end_headers()
        self.wfile.write(build_html().encode())
    def log_message(self, *a): pass

if __name__ == "__main__":
    if USE_FASTAPI: uvicorn.run(app, host="0.0.0.0", port=PORT)
    else: HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
