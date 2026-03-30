"""Servo Control Latency Analyzer — FastAPI port 8562"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8562

def build_html():
    stages = ["Camera\nCapture", "Inference\n(GR00T)", "Action\nDecode", "Servo\nCommand"]
    times = [12, 198, 8, 8]
    colors = ["#38bdf8", "#C74634", "#22c55e", "#f59e0b"]
    total = sum(times)
    x = 20
    bars = []
    for s, t, c in zip(stages, times, colors):
        w = int(t * 2.4)
        bars.append(f'<rect x="{x}" y="30" width="{w}" height="50" fill="{c}" rx="3"/><text x="{x+w//2}" y="59" fill="#0f172a" font-size="10" text-anchor="middle">{t}ms</text><text x="{x+w//2}" y="100" fill="#94a3b8" font-size="9" text-anchor="middle">{s.split(chr(10))[0]}</text>')
        x += w + 6
    return f"""<!DOCTYPE html><html><head><title>Servo Control Latency Analyzer</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:monospace}}
.hdr{{background:#1e293b;padding:16px 24px;border-bottom:2px solid #C74634}}
h1{{margin:0;color:#C74634;font-size:20px}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;padding:24px}}
.card{{background:#1e293b;border-radius:8px;padding:16px;border:1px solid #334155}}
.metric{{font-size:28px;color:#38bdf8;font-weight:bold}}
.lbl{{color:#64748b;font-size:12px;margin-top:4px}}</style></head>
<body><div class="hdr"><h1>Servo Control Latency Analyzer</h1><span style="color:#64748b">Control loop breakdown | Port {PORT}</span></div>
<div class="grid">
<div class="card"><div class="metric">{total}ms</div><div class="lbl">Total Loop Latency</div></div>
<div class="card"><div class="metric">4.4Hz</div><div class="lbl">Control Frequency</div></div>
<div class="card"><div class="metric">88%</div><div class="lbl">Inference Dominance</div></div>
<div class="card"><div class="metric">100ms</div><div class="lbl">Target (N2.0)</div></div>
<div class="card" style="grid-column:span 4">
<div style="color:#94a3b8;font-size:12px;margin-bottom:8px">CONTROL LOOP STAGE BREAKDOWN</div>
<svg width="100%" height="120" viewBox="0 0 600 120">{""join(bars)}</svg>
</div></div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Servo Control Latency Analyzer")
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
