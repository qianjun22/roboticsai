"""Training Stability V2 — FastAPI port 8541"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8541

def build_html():
    steps = list(range(0, 5000, 100))
    grad_norms = [round(1.1 + 0.3*math.sin(s/400) + random.uniform(-0.1, 0.1), 3) for s in steps]
    # Add a spike at step 200-400 (run10)
    for i in range(2, 5):
        grad_norms[i] = round(grad_norms[i] + random.uniform(0.8, 1.4), 3)
    pts = " ".join(f"{15+i*11},{175-int(v*50)}" for i,v in enumerate(grad_norms))
    clip_events = [(i, v) for i,v in enumerate(grad_norms) if v > 1.8]
    clips = "".join(f'<circle cx="{15+i*11}" cy="{175-int(v*50)}" r="4" fill="#C74634"/>' for i,v in clip_events)
    return f"""<!DOCTYPE html><html><head><title>Training Stability V2</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:monospace}}
.hdr{{background:#1e293b;padding:16px 24px;border-bottom:2px solid #C74634}}
h1{{margin:0;color:#C74634;font-size:20px}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;padding:24px}}
.card{{background:#1e293b;border-radius:8px;padding:16px;border:1px solid #334155}}
.metric{{font-size:28px;color:#38bdf8;font-weight:bold}}
.lbl{{color:#64748b;font-size:12px;margin-top:4px}}</style></head>
<body><div class="hdr"><h1>Training Stability V2</h1><span style="color:#64748b">Gradient norm & stability | Port {PORT}</span></div>
<div class="grid">
<div class="card"><div class="metric">0.8-1.4</div><div class="lbl">Stable Grad Norm Range</div></div>
<div class="card"><div class="metric">{len(clip_events)}</div><div class="lbl">Clip Events Total</div></div>
<div class="card"><div class="metric">SAM</div><div class="lbl">Optimizer Trial</div></div>
<div class="card"><div class="metric">run10</div><div class="lbl">Instability Source</div></div>
<div class="card" style="grid-column:span 4">
<div style="color:#94a3b8;font-size:12px;margin-bottom:8px">GRADIENT NORM TRACE (5000 steps) — <span style="color:#C74634">● Clip Event</span></div>
<svg width="100%" height="200" viewBox="0 0 600 200">
<polyline points="{pts}" fill="none" stroke="#38bdf8" stroke-width="1.5"/>
{clips}
<line x1="10" y1="{175-int(1.0*50)}" x2="590" y2="{175-int(1.0*50)}" stroke="#334155" stroke-width="1" stroke-dasharray="4"/>
<line x1="10" y1="{175-int(1.8*50)}" x2="590" y2="{175-int(1.8*50)}" stroke="#C74634" stroke-width="1" stroke-dasharray="4"/>
<text x="15" y="{170-int(1.8*50)}" fill="#C74634" font-size="9">clip threshold</text>
<line x1="10" y1="178" x2="590" y2="178" stroke="#334155" stroke-width="1"/>
</svg></div></div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Training Stability V2")
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
