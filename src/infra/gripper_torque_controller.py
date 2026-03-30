"""Gripper Torque Controller — FastAPI port 8520"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8520

def build_html():
    angles = [i*15 for i in range(24)]
    torques = [round(2.5 + 1.8*math.sin(math.radians(a)) + random.uniform(-0.2, 0.2), 2) for a in angles]
    pts = " ".join(f"{20+i*22},{160-int(t*25)}" for i, t in enumerate(torques))
    return f"""<!DOCTYPE html><html><head><title>Gripper Torque Controller</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:monospace}}
.hdr{{background:#1e293b;padding:16px 24px;border-bottom:2px solid #C74634}}
h1{{margin:0;color:#C74634;font-size:20px}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;padding:24px}}
.card{{background:#1e293b;border-radius:8px;padding:16px;border:1px solid #334155}}
.metric{{font-size:28px;color:#38bdf8;font-weight:bold}}
.lbl{{color:#64748b;font-size:12px;margin-top:4px}}</style></head>
<body><div class="hdr"><h1>Gripper Torque Controller</h1><span style="color:#64748b">Real-time torque monitoring | Port {PORT}</span></div>
<div class="grid">
<div class="card"><div class="metric">{torques[-1]}</div><div class="lbl">Current Torque (Nm)</div></div>
<div class="card"><div class="metric">{max(torques)}</div><div class="lbl">Peak Torque (Nm)</div></div>
<div class="card"><div class="metric">4.2</div><div class="lbl">Max Safe (Nm)</div></div>
<div class="card"><div class="metric">OK</div><div class="lbl">Safety Status</div></div>
<div class="card" style="grid-column:span 4">
<div style="color:#94a3b8;font-size:12px;margin-bottom:8px">TORQUE PROFILE (24 TIMESTEPS)</div>
<svg width="100%" height="180" viewBox="0 0 550 180">
<polyline points="{pts}" fill="none" stroke="#38bdf8" stroke-width="2"/>
<line x1="10" y1="80" x2="540" y2="80" stroke="#C74634" stroke-width="1" stroke-dasharray="4"/>
<text x="14" y="77" fill="#C74634" font-size="9">max safe</text>
<line x1="10" y1="165" x2="540" y2="165" stroke="#334155" stroke-width="1"/>
</svg></div></div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Gripper Torque Controller")
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
