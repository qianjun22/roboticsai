"""Data Flywheel V3 — FastAPI port 8570"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8570

def build_html():
    days = list(range(1, 31))
    teleop = [round(18 + random.uniform(-3, 3), 1) for _ in days]
    dagger = [round(42 + random.uniform(-5, 5), 1) for _ in days]
    cumulative = []
    total = 1000
    for t, d in zip(teleop, dagger):
        total += t + d
        cumulative.append(total)
    pts_cum = " ".join(f"{15+i*18},{185-int(v/25)}" for i,v in enumerate(cumulative))
    return f"""<!DOCTYPE html><html><head><title>Data Flywheel V3</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:monospace}}
.hdr{{background:#1e293b;padding:16px 24px;border-bottom:2px solid #C74634}}
h1{{margin:0;color:#C74634;font-size:20px}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;padding:24px}}
.card{{background:#1e293b;border-radius:8px;padding:16px;border:1px solid #334155}}
.metric{{font-size:28px;color:#38bdf8;font-weight:bold}}
.lbl{{color:#64748b;font-size:12px;margin-top:4px}}</style></head>
<body><div class="hdr"><h1>Data Flywheel V3</h1><span style="color:#64748b">Demo accumulation | Port {PORT}</span></div>
<div class="grid">
<div class="card"><div class="metric">18/hr</div><div class="lbl">Teleoperation Rate</div></div>
<div class="card"><div class="metric">42/hr</div><div class="lbl">DAgger Online Rate</div></div>
<div class="card"><div class="metric">72hr</div><div class="lbl">Cycle Time Target</div></div>
<div class="card"><div class="metric">5,000</div><div class="lbl">v4 Demo Target (Q3)</div></div>
<div class="card" style="grid-column:span 4">
<div style="color:#94a3b8;font-size:12px;margin-bottom:8px">CUMULATIVE DEMO ACCUMULATION (30 days)</div>
<svg width="100%" height="205" viewBox="0 0 560 205">
<polyline points="{pts_cum}" fill="none" stroke="#38bdf8" stroke-width="2"/>
<line x1="10" y1="{185-int(5000/25)}" x2="550" y2="{185-int(5000/25)}" stroke="#22c55e" stroke-width="1" stroke-dasharray="4"/>
<text x="14" y="{180-int(5000/25)}" fill="#22c55e" font-size="9">5k target</text>
<line x1="10" y1="188" x2="550" y2="188" stroke="#334155" stroke-width="1"/>
</svg></div></div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Data Flywheel V3")
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
