"""DAgger Reward Shaper — FastAPI port 8530"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8530

def build_html():
    components = ["Task Success", "Distance", "Smoothness", "Safety Penalty"]
    weights = [0.60, 0.20, 0.12, 0.08]
    sr_delta = ["+0.00", "+0.08", "+0.04", "+0.12 (w/o: -0.15)"]
    colors = ["#38bdf8", "#22c55e", "#f59e0b", "#C74634"]
    bars = "".join(f'<rect x="160" y="{20+i*50}" width="{int(w*400)}" height="35" fill="{c}" rx="3"/><text x="155" y="{42+i*50}" fill="#94a3b8" font-size="11" text-anchor="end">{comp}</text><text x="{165+int(w*400)}" y="{42+i*50}" fill="#e2e8f0" font-size="11">{w} ({d})</text>' for i,(comp,w,d,c) in enumerate(zip(components,weights,sr_delta,colors)))
    return f"""<!DOCTYPE html><html><head><title>DAgger Reward Shaper</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:monospace}}
.hdr{{background:#1e293b;padding:16px 24px;border-bottom:2px solid #C74634}}
h1{{margin:0;color:#C74634;font-size:20px}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;padding:24px}}
.card{{background:#1e293b;border-radius:8px;padding:16px;border:1px solid #334155}}
.metric{{font-size:28px;color:#38bdf8;font-weight:bold}}
.lbl{{color:#64748b;font-size:12px;margin-top:4px}}</style></head>
<body><div class="hdr"><h1>DAgger Reward Shaper</h1><span style="color:#64748b">Reward component analysis | Port {PORT}</span></div>
<div class="grid">
<div class="card"><div class="metric">4</div><div class="lbl">Reward Components</div></div>
<div class="card"><div class="metric">+0.24pp</div><div class="lbl">Shaped vs Sparse SR Lift</div></div>
<div class="card"><div class="metric">12%</div><div class="lbl">Unsafe eps w/o Safety R</div></div>
<div class="card"><div class="metric">0.08</div><div class="lbl">Safety Weight</div></div>
<div class="card" style="grid-column:span 4">
<div style="color:#94a3b8;font-size:12px;margin-bottom:8px">REWARD COMPONENT WEIGHTS & SR IMPACT</div>
<svg width="100%" height="230" viewBox="0 0 620 230">{bars}</svg>
</div></div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="DAgger Reward Shaper")
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
