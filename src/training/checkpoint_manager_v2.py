"""Checkpoint Manager V2 — FastAPI port 8522"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8522

def build_html():
    checkpoints = [
        ("ckpt_1000", "2026-03-10", 0.142, "pruned"),
        ("ckpt_2000", "2026-03-15", 0.118, "pruned"),
        ("ckpt_3000", "2026-03-20", 0.103, "kept"),
        ("ckpt_4000", "2026-03-25", 0.099, "kept"),
        ("ckpt_5000", "2026-03-30", 0.091, "best"),
    ]
    rows = "".join(f'<tr><td style="padding:8px;color:#38bdf8">{c[0]}</td><td style="padding:8px;color:#94a3b8">{c[1]}</td><td style="padding:8px;color:#e2e8f0">{c[2]}</td><td style="padding:8px;color:{"#22c55e" if c[3]=="best" else "#64748b"}">{c[3]}</td></tr>' for c in checkpoints)
    return f"""<!DOCTYPE html><html><head><title>Checkpoint Manager V2</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:monospace}}
.hdr{{background:#1e293b;padding:16px 24px;border-bottom:2px solid #C74634}}
h1{{margin:0;color:#C74634;font-size:20px}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;padding:24px}}
.card{{background:#1e293b;border-radius:8px;padding:16px;border:1px solid #334155}}
.metric{{font-size:28px;color:#38bdf8;font-weight:bold}}
.lbl{{color:#64748b;font-size:12px;margin-top:4px}}
table{{width:100%;border-collapse:collapse}}
th{{text-align:left;padding:8px;color:#64748b;border-bottom:1px solid #334155}}</style></head>
<body><div class="hdr"><h1>Checkpoint Manager V2</h1><span style="color:#64748b">Training checkpoints | Port {PORT}</span></div>
<div class="grid">
<div class="card"><div class="metric">5</div><div class="lbl">Total Checkpoints</div></div>
<div class="card"><div class="metric">0.091</div><div class="lbl">Best Loss</div></div>
<div class="card"><div class="metric">2</div><div class="lbl">Kept</div></div>
<div class="card"><div class="metric">14.2GB</div><div class="lbl">Storage Used</div></div>
<div class="card" style="grid-column:span 4">
<table><tr><th>Checkpoint</th><th>Date</th><th>Val Loss</th><th>Status</th></tr>
{rows}</table></div></div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Checkpoint Manager V2")
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
