"""OCI Network Profiler — FastAPI port 8531"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8531

def build_html():
    regions = ["Ashburn", "Phoenix", "Frankfurt"]
    latency = [[0, 28, 94], [28, 0, 112], [94, 112, 0]]
    cells = "".join(
        f'<rect x="{110+j*110}" y="{40+i*60}" width="100" height="50" fill="{"#1e293b" if i==j else ("#1e3a5f" if latency[i][j]<50 else ("#1e4a20" if latency[i][j]<100 else "#3a1e1e"))}" rx="3"/>'
        f'<text x="{160+j*110}" y="{70+i*60}" fill="{"#64748b" if i==j else "#e2e8f0"}" font-size="13" text-anchor="middle">{"\u2014" if i==j else f"{latency[i][j]}ms"}</text>'
        for i in range(3) for j in range(3)
    )
    labels = "".join(f'<text x="{160+i*110}" y="28" fill="#94a3b8" font-size="11" text-anchor="middle">{r}</text><text x="100" y="{70+i*60}" fill="#94a3b8" font-size="11" text-anchor="end">{r}</text>' for i,r in enumerate(regions))
    return f"""<!DOCTYPE html><html><head><title>OCI Network Profiler</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:monospace}}
.hdr{{background:#1e293b;padding:16px 24px;border-bottom:2px solid #C74634}}
h1{{margin:0;color:#C74634;font-size:20px}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;padding:24px}}
.card{{background:#1e293b;border-radius:8px;padding:16px;border:1px solid #334155}}
.metric{{font-size:28px;color:#38bdf8;font-weight:bold}}
.lbl{{color:#64748b;font-size:12px;margin-top:4px}}</style></head>
<body><div class="hdr"><h1>OCI Network Profiler</h1><span style="color:#64748b">Inter-region latency | Port {PORT}</span></div>
<div class="grid">
<div class="card"><div class="metric">28ms</div><div class="lbl">Ashburn\u2192Phoenix</div></div>
<div class="card"><div class="metric">4.2Gbps</div><div class="lbl">Cross-Region BW</div></div>
<div class="card"><div class="metric">0.002%</div><div class="lbl">Packet Loss</div></div>
<div class="card"><div class="metric">18min</div><div class="lbl">7GB Checkpoint Sync</div></div>
<div class="card" style="grid-column:span 4">
<div style="color:#94a3b8;font-size:12px;margin-bottom:8px">INTER-REGION LATENCY MATRIX</div>
<svg width="450" height="240" viewBox="0 0 450 240">{labels}{cells}</svg>
</div></div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="OCI Network Profiler")
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
