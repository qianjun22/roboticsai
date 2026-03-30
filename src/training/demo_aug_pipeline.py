"""Demo Augmentation Pipeline — FastAPI port 8523"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8523

def build_html():
    stages = ["Raw Demos", "Filter", "Noise Inject", "Mirror", "Speed Vary", "Color Jitter", "Final"]
    counts = [1000, 920, 920, 1840, 2760, 2760, 2680]
    bars = "".join(f'<rect x="{20}" y="{15+i*32}" width="{int(c/12)}" height="22" fill="{("#38bdf8" if i<len(stages)-1 else "#22c55e")}" rx="3"/><text x="{25+int(c/12)}" y="{31+i*32}" fill="#94a3b8" font-size="11">{s} ({c})</text>' for i, (s, c) in enumerate(zip(stages, counts)))
    return f"""<!DOCTYPE html><html><head><title>Demo Augmentation Pipeline</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:monospace}}
.hdr{{background:#1e293b;padding:16px 24px;border-bottom:2px solid #C74634}}
h1{{margin:0;color:#C74634;font-size:20px}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;padding:24px}}
.card{{background:#1e293b;border-radius:8px;padding:16px;border:1px solid #334155}}
.metric{{font-size:28px;color:#38bdf8;font-weight:bold}}
.lbl{{color:#64748b;font-size:12px;margin-top:4px}}</style></head>
<body><div class="hdr"><h1>Demo Augmentation Pipeline</h1><span style="color:#64748b">Data augmentation stages | Port {PORT}</span></div>
<div class="grid">
<div class="card"><div class="metric">1,000</div><div class="lbl">Input Demos</div></div>
<div class="card"><div class="metric">2,680</div><div class="lbl">Output Demos</div></div>
<div class="card"><div class="metric">2.68×</div><div class="lbl">Augmentation Ratio</div></div>
<div class="card"><div class="metric">5</div><div class="lbl">Aug Stages</div></div>
<div class="card" style="grid-column:span 4">
<div style="color:#94a3b8;font-size:12px;margin-bottom:8px">PIPELINE STAGES</div>
<svg width="100%" height="{15+len(stages)*32+10}" viewBox="0 600 {15+len(stages)*32+10}">{bars}</svg>
</div></div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Demo Augmentation Pipeline")
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
