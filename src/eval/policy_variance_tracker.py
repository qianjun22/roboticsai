"""Policy Variance Tracker — FastAPI port 8574"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8574

def build_html():
    models = ["bc_baseline", "dagger_run9", "groot_v2", "dagger_run10"]
    means = [0.05, 0.71, 0.78, 0.64]
    stds = [0.031, 0.038, 0.042, 0.088]
    colors = ["#64748b", "#22c55e", "#38bdf8", "#f59e0b"]
    boxes = "".join(
        f'<rect x="{40+i*120}" y="{165-int((m+s)*150)}" width="60" height="{int(s*2*150)}" fill="{c}" opacity="0.6" rx="3"/>'
        f'<line x1="{40+i*120}" y1="{165-int(m*150)}" x2="{100+i*120}" y2="{165-int(m*150)}" stroke="{c}" stroke-width="3"/>'
        f'<text x="{70+i*120}" y="185" fill="#64748b" font-size="9" text-anchor="middle">{md.split("_")[0][:8]}</text>'
        f'<text x="{70+i*120}" y="{160-int((m+s)*150)-5}" fill="#94a3b8" font-size="9" text-anchor="middle">σ={s}</text>'
        for i,(md,m,s,c) in enumerate(zip(models,means,stds,colors))
    )
    return f"""<!DOCTYPE html><html><head><title>Policy Variance Tracker</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:monospace}}
.hdr{{background:#1e293b;padding:16px 24px;border-bottom:2px solid #C74634}}
h1{{margin:0;color:#C74634;font-size:20px}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;padding:24px}}
.card{{background:#1e293b;border-radius:8px;padding:16px;border:1px solid #334155}}
.metric{{font-size:28px;color:#38bdf8;font-weight:bold}}
.lbl{{color:#64748b;font-size:12px;margin-top:4px}}</style></head>
<body><div class="hdr"><h1>Policy Variance Tracker</h1><span style="color:#64748b">SR variance across seeds | Port {PORT}</span></div>
<div class="grid">
<div class="card"><div class="metric">0.042</div><div class="lbl">groot_v2 σ (stable)</div></div>
<div class="card"><div class="metric">0.088</div><div class="lbl">run10 σ (training)</div></div>
<div class="card"><div class="metric">&lt;0.05</div><div class="lbl">Production σ Target</div></div>
<div class="card"><div class="metric">800+</div><div class="lbl">Demos for σ Stability</div></div>
<div class="card" style="grid-column:span 4">
<div style="color:#94a3b8;font-size:12px;margin-bottom:8px">SR DISTRIBUTION (10-seed box plots)</div>
<svg width="100%" height="205" viewBox="0 0 560 205">{boxes}
<line x1="20" y1="168" x2="540" y2="168" stroke="#334155" stroke-width="1"/>
</svg></div></div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Policy Variance Tracker")
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
