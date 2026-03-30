"""Hyperparameter Sensitivity V2 — FastAPI port 8568"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8568

def build_html():
    params = ["LR", "chunk_size", "batch", "dropout", "warmup", "weight_decay", "grad_clip", "aug_prob"]
    impact = [0.18, 0.14, 0.09, 0.05, 0.04, 0.03, 0.02, 0.02]
    colors = ["#C74634" if i >= 0.10 else ("#f59e0b" if i >= 0.05 else "#38bdf8") for i in impact]
    bars = "".join(f'<rect x="{int(160-v*400)}" y="{20+i*42}" width="{int(v*400)}" height="30" fill="{c}" rx="3"/><text x="{165}" y="{39+i*42}" fill="#94a3b8" font-size="11">{p}</text><text x="{155-int(v*400)}" y="{39+i*42}" fill="#e2e8f0" font-size="11" text-anchor="end">{v:.2f}pp</text>' for i,(p,v,c) in enumerate(zip(params,impact,colors)))
    return f"""<!DOCTYPE html><html><head><title>Hyperparameter Sensitivity V2</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:monospace}}
.hdr{{background:#1e293b;padding:16px 24px;border-bottom:2px solid #C74634}}
h1{{margin:0;color:#C74634;font-size:20px}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;padding:24px}}
.card{{background:#1e293b;border-radius:8px;padding:16px;border:1px solid #334155}}
.metric{{font-size:28px;color:#38bdf8;font-weight:bold}}
.lbl{{color:#64748b;font-size:12px;margin-top:4px}}</style></head>
<body><div class="hdr"><h1>Hyperparameter Sensitivity V2</h1><span style="color:#64748b">SR impact per param | Port {PORT}</span></div>
<div class="grid">
<div class="card"><div class="metric">LR</div><div class="lbl">Most Sensitive (+0.18pp/0.5×)</div></div>
<div class="card"><div class="metric">chunk=16</div><div class="lbl">Optimal Chunk Size</div></div>
<div class="card"><div class="metric">&lt;0.02pp</div><div class="lbl">Dropout Impact</div></div>
<div class="card"><div class="metric">$180</div><div class="lbl">Full Sweep Cost</div></div>
<div class="card" style="grid-column:span 4">
<div style="color:#94a3b8;font-size:12px;margin-bottom:8px">SR SENSITIVITY TORNADO (pp per 0.5× change)</div>
<svg width="100%" height="{20+len(params)*42+10}" viewBox="0 600 {20+len(params)*42+10}">{bars}</svg>
</div></div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Hyperparameter Sensitivity V2")
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
