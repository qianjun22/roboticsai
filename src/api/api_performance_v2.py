"""API Performance V2 — FastAPI port 8521"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8521

def build_html():
    endpoints = ["/infer", "/health", "/eval", "/train", "/deploy", "/metrics"]
    p50 = [random.randint(18, 35) for _ in endpoints]
    p99 = [random.randint(80, 240) for _ in endpoints]
    bars50 = "".join(f'<rect x="{40+i*90}" y="{160-p}" width="30" height="{p}" fill="#38bdf8" rx="2"/>' for i, p in enumerate(p50))
    bars99 = "".join(f'<rect x="{72+i*90}" y="{160-p}" width="30" height="{p}" fill="#C74634" rx="2"/>' for i, p in enumerate(p99))
    labels = "".join(f'<text x="{55+i*90}" y="175" fill="#94a3b8" font-size="9" text-anchor="middle">{ep}</text>' for i, ep in enumerate(endpoints))
    return f"""<!DOCTYPE html><html><head><title>API Performance V2</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:monospace}}
.hdr{{background:#1e293b;padding:16px 24px;border-bottom:2px solid #C74634}}
h1{{margin:0;color:#C74634;font-size:20px}}
.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;padding:24px}}
.card{{background:#1e293b;border-radius:8px;padding:16px;border:1px solid #334155}}
.metric{{font-size:28px;color:#38bdf8;font-weight:bold}}
.lbl{{color:#64748b;font-size:12px;margin-top:4px}}</style></head>
<body><div class="hdr"><h1>API Performance V2</h1><span style="color:#64748b">Endpoint latency tracker | Port {PORT}</span></div>
<div class="grid">
<div class="card"><div class="metric">{min(p50)}ms</div><div class="lbl">Best P50</div></div>
<div class="card"><div class="metric">{max(p99)}ms</div><div class="lbl">Worst P99</div></div>
<div class="card"><div class="metric">99.97%</div><div class="lbl">SLA Compliance</div></div>
<div class="card" style="grid-column:span 3">
<div style="color:#94a3b8;font-size:12px;margin-bottom:8px">LATENCY BY ENDPOINT (ms) — <span style="color:#38bdf8">&#9632; P50</span> <span style="color:#C74634">&#9632; P99</span></div>
<svg width="100%" height="195" viewBox="0 0 580 195">
{bars50}{bars99}{labels}
<line x1="30" y1="162" x2="570" y2="162" stroke="#334155" stroke-width="1"/>
</svg></div></div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="API Performance V2")
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
