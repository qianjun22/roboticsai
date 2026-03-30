"""Simulation Complexity Benchmarker — FastAPI port 8573"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8573

def build_html():
    obj_counts = [4, 6, 8, 10, 12, 14, 16]
    fps = [58, 52, 42, 36, 30, 26, 22]
    sr = [0.82, 0.78, 0.71, 0.65, 0.58, 0.52, 0.47]
    pts_fps = " ".join(f"{30+i*80},{170-int(f*2)}" for i,f in enumerate(fps))
    dots_sr = "".join(f'<circle cx="{30+i*80}" cy="{170-int(v*180)}" r="5" fill="#C74634"/>' for i,v in enumerate(sr))
    xlabels = "".join(f'<text x="{30+i*80}" y="188" fill="#64748b" font-size="9" text-anchor="middle">{o}obj</text>' for i,o in enumerate(obj_counts))
    return f"""<!DOCTYPE html><html><head><title>Simulation Complexity Benchmarker</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:monospace}}
.hdr{{background:#1e293b;padding:16px 24px;border-bottom:2px solid #C74634}}
h1{{margin:0;color:#C74634;font-size:20px}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;padding:24px}}
.card{{background:#1e293b;border-radius:8px;padding:16px;border:1px solid #334155}}
.metric{{font-size:28px;color:#38bdf8;font-weight:bold}}
.lbl{{color:#64748b;font-size:12px;margin-top:4px}}</style></head>
<body><div class="hdr"><h1>Simulation Complexity Benchmarker</h1><span style="color:#64748b">Scene complexity vs FPS/SR | Port {PORT}</span></div>
<div class="grid">
<div class="card"><div class="metric">42fps</div><div class="lbl">Nominal (8-obj scene)</div></div>
<div class="card"><div class="metric">24fps</div><div class="lbl">FPS Floor (enforced)</div></div>
<div class="card"><div class="metric">-0.024</div><div class="lbl">SR per Complexity Unit</div></div>
<div class="card"><div class="metric">Auto</div><div class="lbl">Simplification at Floor</div></div>
<div class="card" style="grid-column:span 4">
<div style="color:#94a3b8;font-size:12px;margin-bottom:8px">FPS & SR vs OBJECT COUNT — <span style="color:#38bdf8">&#9632; FPS</span> <span style="color:#C74634">&#9679; SR</span></div>
<svg width="100%" height="210" viewBox="0 0 580 210">
<polyline points="{pts_fps}" fill="none" stroke="#38bdf8" stroke-width="2"/>
{dots_sr}{xlabels}
<line x1="10" y1="{170-int(24*2)}" x2="570" y2="{170-int(24*2)}" stroke="#f59e0b" stroke-width="1" stroke-dasharray="4"/>
<text x="14" y="{165-int(24*2)}" fill="#f59e0b" font-size="9">24fps floor</text>
<line x1="10" y1="174" x2="570" y2="174" stroke="#334155" stroke-width="1"/>
</svg></div></div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Simulation Complexity Benchmarker")
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
