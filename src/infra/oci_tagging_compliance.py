"""OCI Tagging Compliance — FastAPI port 8579"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8579

def build_html():
    resource_types = ["Compute", "Storage", "Network", "DB", "Functions"]
    tags = ["project", "env", "owner", "cost-center", "robot-type"]
    compliance = [
        [100, 100, 94, 88, 82],
        [100, 98, 91, 78, 71],
        [100, 100, 97, 92, 88],
        [100, 95, 89, 84, 79],
        [100, 92, 85, 72, 68],
    ]
    cells = "".join(
        f'<rect x="{70+j*80}" y="{20+i*50}" width="70" height="40" fill="{"#1e4a20" if compliance[i][j]>=95 else ("#3a2e00" if compliance[i][j]>=80 else "#3a1e1e")}" rx="3"/>'
        f'<text x="{105+j*80}" y="{44+i*50}" fill="#e2e8f0" font-size="12" text-anchor="middle">{compliance[i][j]}%</text>'
        for i in range(5) for j in range(5)
    )
    rlabels = "".join(f'<text x="60" y="{44+i*50}" fill="#94a3b8" font-size="10" text-anchor="end">{r}</text>' for i,r in enumerate(resource_types))
    clabels = "".join(f'<text x="{105+i*80}" y="15" fill="#64748b" font-size="9" text-anchor="middle">{t}</text>' for i,t in enumerate(tags))
    return f"""<!DOCTYPE html><html><head><title>OCI Tagging Compliance</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:monospace}}
.hdr{{background:#1e293b;padding:16px 24px;border-bottom:2px solid #C74634}}
h1{{margin:0;color:#C74634;font-size:20px}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;padding:24px}}
.card{{background:#1e293b;border-radius:8px;padding:16px;border:1px solid #334155}}
.metric{{font-size:28px;color:#38bdf8;font-weight:bold}}
.lbl{{color:#64748b;font-size:12px;margin-top:4px}}</style></head>
<body><div class="hdr"><h1>OCI Tagging Compliance</h1><span style="color:#64748b">Resource tagging coverage | Port {PORT}</span></div>
<div class="grid">
<div class="card"><div class="metric">23</div><div class="lbl">Untagged Resources</div></div>
<div class="card"><div class="metric">94%</div><div class="lbl">Compute Tagged</div></div>
<div class="card"><div class="metric">91%</div><div class="lbl">Storage Tagged (lowest)</div></div>
<div class="card"><div class="metric">100%</div><div class="lbl">Target Coverage</div></div>
<div class="card" style="grid-column:span 4">
<div style="color:#94a3b8;font-size:12px;margin-bottom:8px">TAG COMPLIANCE MATRIX (resource × tag)</div>
<svg width="490" height="295" viewBox="0 0 490 295">{rlabels}{clabels}{cells}</svg>
</div></div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="OCI Tagging Compliance")
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
