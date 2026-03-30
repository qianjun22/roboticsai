"""Eval Failure Classifier — FastAPI port 8564"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8564

def build_html():
    modes = ["Grasp Miss", "Drop", "Collision", "Timeout", "Wrong Obj"]
    counts = [52, 18, 12, 10, 8]
    colors = ["#C74634","#f59e0b","#38bdf8","#22c55e","#a78bfa"]
    total = sum(counts)
    # Pie chart approximation with bar chart
    bars = "".join(f'<rect x="160" y="{20+i*46}" width="{int(c/total*400)}" height="32" fill="{col}" rx="3"/><text x="155" y="{40+i*46}" fill="#94a3b8" font-size="11" text-anchor="end">{m}</text><text x="{165+int(c/total*400)}" y="{40+i*46}" fill="#e2e8f0" font-size="11">{c}% ({int(c/total*100)}%)</text>' for i,(m,c,col) in enumerate(zip(modes,counts,colors)))
    return f"""<!DOCTYPE html><html><head><title>Eval Failure Classifier</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:monospace}}
.hdr{{background:#1e293b;padding:16px 24px;border-bottom:2px solid #C74634}}
h1{{margin:0;color:#C74634;font-size:20px}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;padding:24px}}
.card{{background:#1e293b;border-radius:8px;padding:16px;border:1px solid #334155}}
.metric{{font-size:28px;color:#38bdf8;font-weight:bold}}
.lbl{{color:#64748b;font-size:12px;margin-top:4px}}</style></head>
<body><div class="hdr"><h1>Eval Failure Classifier</h1><span style="color:#64748b">Failure mode taxonomy | Port {PORT}</span></div>
<div class="grid">
<div class="card"><div class="metric">52%</div><div class="lbl">Grasp Miss (top cause)</div></div>
<div class="card"><div class="metric">+0.08pp</div><div class="lbl">Est. SR from Approach Fix</div></div>
<div class="card"><div class="metric">47%</div><div class="lbl">Approach Angle Root Cause</div></div>
<div class="card"><div class="metric">5</div><div class="lbl">Failure Modes</div></div>
<div class="card" style="grid-column:span 4">
<div style="color:#94a3b8;font-size:12px;margin-bottom:8px">FAILURE MODE DISTRIBUTION</div>
<svg width="100%" height="{20+len(modes)*46+10}" viewBox="0 640 {20+len(modes)*46+10}">{bars}</svg>
</div></div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Eval Failure Classifier")
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
