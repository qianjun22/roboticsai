"""SDK Version Manager — FastAPI port 8589"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8589

def build_html():
    weeks = list(range(1, 13))
    v1_installs = [max(0, round(100 - 8*w + random.uniform(-3,3), 0)) for w in weeks]
    v2_installs = [round(10 + 70*(1-math.exp(-w/4)) + random.uniform(-3,3), 0) for w in weeks]
    v3_installs = [round(max(0, (w-10)*8 + random.uniform(-2,2)), 0) for w in weeks]
    pts_v1 = " ".join(f"{20+i*44},{170-int(v*1.2)}" for i,v in enumerate(v1_installs))
    pts_v2 = " ".join(f"{20+i*44},{170-int(v*1.2)}" for i,v in enumerate(v2_installs))
    pts_v3 = " ".join(f"{20+i*44},{170-int(v*1.2)}" for i,v in enumerate(v3_installs))
    return f"""<!DOCTYPE html><html><head><title>SDK Version Manager</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:monospace}}
.hdr{{background:#1e293b;padding:16px 24px;border-bottom:2px solid #C74634}}
h1{{margin:0;color:#C74634;font-size:20px}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;padding:24px}}
.card{{background:#1e293b;border-radius:8px;padding:16px;border:1px solid #334155}}
.metric{{font-size:28px;color:#38bdf8;font-weight:bold}}
.lbl{{color:#64748b;font-size:12px;margin-top:4px}}</style></head>
<body><div class="hdr"><h1>SDK Version Manager</h1><span style="color:#64748b">Version adoption tracker | Port {PORT}</span></div>
<div class="grid">
<div class="card"><div class="metric">73%</div><div class="lbl">v2 Adoption</div></div>
<div class="card"><div class="metric">12%</div><div class="lbl">v3 Adoption (2wk)</div></div>
<div class="card"><div class="metric">Sep 2026</div><div class="lbl">v1 EOL Date</div></div>
<div class="card"><div class="metric">89%</div><div class="lbl">Auto-Migration Coverage</div></div>
<div class="card" style="grid-column:span 4">
<div style="color:#94a3b8;font-size:12px;margin-bottom:8px">WEEKLY ACTIVE INSTALLS — <span style="color:#C74634">■ v1</span> <span style="color:#38bdf8">■ v2</span> <span style="color:#22c55e">■ v3</span></div>
<svg width="100%" height="195" viewBox="0 0 540 195">
<polyline points="{pts_v1}" fill="none" stroke="#C74634" stroke-width="2"/>
<polyline points="{pts_v2}" fill="none" stroke="#38bdf8" stroke-width="2"/>
<polyline points="{pts_v3}" fill="none" stroke="#22c55e" stroke-width="2"/>
<line x1="10" y1="173" x2="530" y2="173" stroke="#334155" stroke-width="1"/>
</svg></div></div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="SDK Version Manager")
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
