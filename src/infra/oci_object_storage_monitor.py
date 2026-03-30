"""OCI Object Storage Monitor — FastAPI port 8535"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8535

def build_html():
    buckets = ["demo_data", "checkpoints", "logs", "artifacts"]
    sizes_tb = [11.2, 4.8, 1.6, 0.8]
    colors = ["#38bdf8", "#C74634", "#22c55e", "#f59e0b"]
    total = sum(sizes_tb)
    bars = "".join(f'<rect x="120" y="{20+i*55}" width="{int(s*30)}" height="40" fill="{c}" rx="3"/><text x="115" y="{45+i*55}" fill="#94a3b8" font-size="11" text-anchor="end">{b}</text><text x="{125+int(s*30)}" y="{45+i*55}" fill="#e2e8f0" font-size="11">{s}TB ({int(s/total*100)}%)</text>' for i,(b,s,c) in enumerate(zip(buckets,sizes_tb,colors)))
    return f"""<!DOCTYPE html><html><head><title>OCI Object Storage Monitor</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:monospace}}
.hdr{{background:#1e293b;padding:16px 24px;border-bottom:2px solid #C74634}}
h1{{margin:0;color:#C74634;font-size:20px}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;padding:24px}}
.card{{background:#1e293b;border-radius:8px;padding:16px;border:1px solid #334155}}
.metric{{font-size:28px;color:#38bdf8;font-weight:bold}}
.lbl{{color:#64748b;font-size:12px;margin-top:4px}}</style></head>
<body><div class="hdr"><h1>OCI Object Storage Monitor</h1><span style="color:#64748b">Storage by bucket | Port {PORT}</span></div>
<div class="grid">
<div class="card"><div class="metric">18.4TB</div><div class="lbl">Total Storage</div></div>
<div class="card"><div class="metric">61%</div><div class="lbl">Demo Data %</div></div>
<div class="card"><div class="metric">$340/mo</div><div class="lbl">Tiering Savings</div></div>
<div class="card"><div class="metric">90d</div><div class="lbl">Archive Threshold</div></div>
<div class="card" style="grid-column:span 4">
<div style="color:#94a3b8;font-size:12px;margin-bottom:8px">STORAGE BY BUCKET</div>
<svg width="100%" height="250" viewBox="0 0 620 250">{bars}</svg>
</div></div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="OCI Object Storage Monitor")
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
