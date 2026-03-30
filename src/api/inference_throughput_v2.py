"""Inference Throughput V2 — FastAPI port 8529"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8529

def build_html():
    gpus = [1, 2, 4, 8]
    rps = [847, 1650, 3200, 5800]
    pts = " ".join(f"{50+i*120},{200-int(r/35)}" for i, r in enumerate(rps))
    dots = "".join(f'<circle cx="{50+i*120}" cy="{200-int(r/35)}" r="5" fill="#C74634"/><text x="{50+i*120}" y="{195-int(r/35)-10}" fill="#94a3b8" font-size="10" text-anchor="middle">{r}</text>' for i,r in enumerate(rps))
    xlabels = "".join(f'<text x="{50+i*120}" y="220" fill="#64748b" font-size="10" text-anchor="middle">{g}×A100</text>' for i,g in enumerate(gpus))
    return f"""<!DOCTYPE html><html><head><title>Inference Throughput V2</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:monospace}}
.hdr{{background:#1e293b;padding:16px 24px;border-bottom:2px solid #C74634}}
h1{{margin:0;color:#C74634;font-size:20px}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;padding:24px}}
.card{{background:#1e293b;border-radius:8px;padding:16px;border:1px solid #334155}}
.metric{{font-size:28px;color:#38bdf8;font-weight:bold}}
.lbl{{color:#64748b;font-size:12px;margin-top:4px}}</style></head>
<body><div class="hdr"><h1>Inference Throughput V2</h1><span style="color:#64748b">Multi-GPU scaling | Port {PORT}</span></div>
<div class="grid">
<div class="card"><div class="metric">847</div><div class="lbl">Current req/hr (1×GPU)</div></div>
<div class="card"><div class="metric">3,200</div><div class="lbl">Target req/hr (4×GPU)</div></div>
<div class="card"><div class="metric">6.9×</div><div class="lbl">8-GPU Scaling</div></div>
<div class="card"><div class="metric">226ms</div><div class="lbl">P50 Latency</div></div>
<div class="card" style="grid-column:span 4">
<div style="color:#94a3b8;font-size:12px;margin-bottom:8px">THROUGHPUT vs GPU COUNT (req/hr)</div>
<svg width="100%" height="240" viewBox="0 0 480 240">
<polyline points="{pts}" fill="none" stroke="#38bdf8" stroke-width="2"/>
{dots}{xlabels}
<line x1="20" y1="205" x2="460" y2="205" stroke="#334155" stroke-width="1"/>
</svg></div></div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Inference Throughput V2")
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
