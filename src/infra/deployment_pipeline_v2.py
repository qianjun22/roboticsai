"""Deployment Pipeline V2 — FastAPI port 8537"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8537

def build_html():
    stages = ["Lint", "Test", "Build", "Push", "Canary", "Promote"]
    times = [0.8, 3.2, 2.1, 1.4, 3.0, 1.9]
    colors = ["#38bdf8", "#38bdf8", "#38bdf8", "#38bdf8", "#f59e0b", "#22c55e"]
    x = 20
    bars = []
    for i, (s, t, c) in enumerate(zip(stages, times, colors)):
        w = int(t * 40)
        bars.append(f'<rect x="{x}" y="20" width="{w}" height="40" fill="{c}" rx="3"/><text x="{x+w//2}" y="45" fill="#0f172a" font-size="10" text-anchor="middle">{s}</text><text x="{x+w//2}" y="58" fill="#94a3b8" font-size="9" text-anchor="middle">{t}m</text>')
        x += w + 8
    total = sum(times)
    return f"""<!DOCTYPE html><html><head><title>Deployment Pipeline V2</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:monospace}}
.hdr{{background:#1e293b;padding:16px 24px;border-bottom:2px solid #C74634}}
h1{{margin:0;color:#C74634;font-size:20px}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;padding:24px}}
.card{{background:#1e293b;border-radius:8px;padding:16px;border:1px solid #334155}}
.metric{{font-size:28px;color:#38bdf8;font-weight:bold}}
.lbl{{color:#64748b;font-size:12px;margin-top:4px}}</style></head>
<body><div class="hdr"><h1>Deployment Pipeline V2</h1><span style="color:#64748b">CI/CD stage tracker | Port {PORT}</span></div>
<div class="grid">
<div class="card"><div class="metric">{total:.1f}min</div><div class="lbl">Total Deploy Time</div></div>
<div class="card"><div class="metric">0</div><div class="lbl">Rollbacks (14 deploys)</div></div>
<div class="card"><div class="metric">10%</div><div class="lbl">Canary Traffic</div></div>
<div class="card"><div class="metric">30min</div><div class="lbl">Canary Window</div></div>
<div class="card" style="grid-column:span 4">
<div style="color:#94a3b8;font-size:12px;margin-bottom:8px">PIPELINE STAGE WATERFALL</div>
<svg width="100%" height="90" viewBox="0 0 560 90">{""".""".join(bars)}</svg>
</div></div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Deployment Pipeline V2")
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
