"""Training Dataset Versioner — FastAPI port 8561"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8561

def build_html():
    versions = ["v1", "v2", "v3", "v4"]
    sizes = [200, 500, 1000, 2680]
    sources = {"teleop": [200, 320, 500, 680], "dagger": [0, 180, 400, 600], "augmented": [0, 0, 100, 1400]}
    colors = {"teleop": "#38bdf8", "dagger": "#22c55e", "augmented": "#C74634"}
    stacked = []
    for i in range(4):
        y = 160
        for src, vals in sources.items():
            h = int(vals[i]/20)
            stacked.append(f'<rect x="{40+i*120}" y="{y-h}" width="80" height="{h}" fill="{colors[src]}" rx="2"/>')
            y -= h
        stacked.append(f'<text x="{80+i*120}" y="178" fill="#64748b" font-size="11" text-anchor="middle">{versions[i]}</text>')
        stacked.append(f'<text x="{80+i*120}" y="{y-8}" fill="#94a3b8" font-size="10" text-anchor="middle">{sizes[i]}</text>')
    legend = "".join(f'<rect x="{10+i*90}" y="5" width="12" height="12" fill="{c}"/><text x="{25+i*90}" y="15" fill="#94a3b8" font-size="10">{s}</text>' for i,(s,c) in enumerate(colors.items()))
    return f"""<!DOCTYPE html><html><head><title>Training Dataset Versioner</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:monospace}}
.hdr{{background:#1e293b;padding:16px 24px;border-bottom:2px solid #C74634}}
h1{{margin:0;color:#C74634;font-size:20px}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;padding:24px}}
.card{{background:#1e293b;border-radius:8px;padding:16px;border:1px solid #334155}}
.metric{{font-size:28px;color:#38bdf8;font-weight:bold}}
.lbl{{color:#64748b;font-size:12px;margin-top:4px}}</style></head>
<body><div class="hdr"><h1>Training Dataset Versioner</h1><span style="color:#64748b">Dataset lineage tracker | Port {PORT}</span></div>
<div class="grid">
<div class="card"><div class="metric">v4</div><div class="lbl">Current Version</div></div>
<div class="card"><div class="metric">2,680</div><div class="lbl">Total Demos</div></div>
<div class="card"><div class="metric">100%</div><div class="lbl">Reproducibility Score</div></div>
<div class="card"><div class="metric">3f8a2c1</div><div class="lbl">Lineage Hash</div></div>
<div class="card" style="grid-column:span 4">
<div style="color:#94a3b8;font-size:12px;margin-bottom:4px">DEMO COUNT BY VERSION &amp; SOURCE</div>
<svg width="100%" height="200" viewBox="0 0 560 200">
{chr(10).join(stacked)}
{legend}
<line x1="10" y1="165" x2="550" y2="165" stroke="#334155" stroke-width="1"/>
</svg></div></div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Training Dataset Versioner")
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
