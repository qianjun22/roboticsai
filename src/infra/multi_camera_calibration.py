"""Multi-Camera Calibration — FastAPI port 8556"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8556

def build_html():
    cameras = ["Wrist", "Ext-1 (front)", "Ext-2 (side)", "Ext-3 (top)"]
    rms = [round(random.uniform(0.18, 0.45), 3) for _ in cameras]
    drift = [round(random.uniform(0.02, 0.12), 3) for _ in cameras]
    bars_rms = "".join(f'<rect x="{30+i*120}" y="{130-int(r*200)}" width="50" height="{int(r*200)}" fill="{("#22c55e" if r<0.5 else "#f59e0b")}" rx="3"/><text x="{55+i*120}" y="{125-int(r*200)}" fill="#94a3b8" font-size="9" text-anchor="middle">{r}px</text><text x="{55+i*120}" y="148" fill="#64748b" font-size="9" text-anchor="middle">{c.split(" ")[0]}</text>' for i,(c,r) in enumerate(zip(cameras,rms)))
    return f"""<!DOCTYPE html><html><head><title>Multi-Camera Calibration</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:monospace}}
.hdr{{background:#1e293b;padding:16px 24px;border-bottom:2px solid #C74634}}
h1{{margin:0;color:#C74634;font-size:20px}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;padding:24px}}
.card{{background:#1e293b;border-radius:8px;padding:16px;border:1px solid #334155}}
.metric{{font-size:28px;color:#38bdf8;font-weight:bold}}
.lbl{{color:#64748b;font-size:12px;margin-top:4px}}</style></head>
<body><div class="hdr"><h1>Multi-Camera Calibration</h1><span style="color:#64748b">4-camera rig accuracy | Port {PORT}</span></div>
<div class="grid">
<div class="card"><div class="metric">4</div><div class="lbl">Camera Rig Size</div></div>
<div class="card"><div class="metric">0.31px</div><div class="lbl">Best RMS Error</div></div>
<div class="card"><div class="metric">2.1%</div><div class="lbl">Depth Error @ 1m</div></div>
<div class="card"><div class="metric">0.8px</div><div class="lbl">Auto-Recal Trigger</div></div>
<div class="card" style="grid-column:span 4">
<div style="color:#94a3b8;font-size:12px;margin-bottom:8px">RMS REPROJECTION ERROR (px) PER CAMERA</div>
<svg width="100%" height="165" viewBox="0 0 520 165">{bars_rms}
<line x1="10" y1="{130-int(0.5*200)}" x2="510" y2="{130-int(0.5*200)}" stroke="#f59e0b" stroke-width="1" stroke-dasharray="4"/>
<text x="15" y="{125-int(0.5*200)}" fill="#f59e0b" font-size="9">warn 0.5px</text>
<line x1="10" y1="133" x2="510" y2="133" stroke="#334155" stroke-width="1"/>
</svg></div></div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Multi-Camera Calibration")
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
