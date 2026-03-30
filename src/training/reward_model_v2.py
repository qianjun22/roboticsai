"""Reward Model V2 — FastAPI port 8586"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8586

def build_html():
    steps = list(range(0, 5000, 200))
    v1_acc = [round(0.5 + 0.284*(1-math.exp(-s/1400)) + random.uniform(-0.008,0.008), 3) for s in steps]
    v2_acc = [round(0.5 + 0.321*(1-math.exp(-s/1200)) + random.uniform(-0.008,0.008), 3) for s in steps]
    pts_v1 = " ".join(f"{15+i*22},{170-int(v*155)}" for i,v in enumerate(v1_acc))
    pts_v2 = " ".join(f"{15+i*22},{170-int(v*155)}" for i,v in enumerate(v2_acc))
    return f"""<!DOCTYPE html><html><head><title>Reward Model V2</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:monospace}}
.hdr{{background:#1e293b;padding:16px 24px;border-bottom:2px solid #C74634}}
h1{{margin:0;color:#C74634;font-size:20px}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;padding:24px}}
.card{{background:#1e293b;border-radius:8px;padding:16px;border:1px solid #334155}}
.metric{{font-size:28px;color:#38bdf8;font-weight:bold}}
.lbl{{color:#64748b;font-size:12px;margin-top:4px}}</style></head>
<body><div class="hdr"><h1>Reward Model V2</h1><span style="color:#64748b">Human preference v2 | Port {PORT}</span></div>
<div class="grid">
<div class="card"><div class="metric">82.1%</div><div class="lbl">V2 Val Accuracy</div></div>
<div class="card"><div class="metric">78.4%</div><div class="lbl">V1 Val Accuracy</div></div>
<div class="card"><div class="metric">+0.06pp</div><div class="lbl">SR Improvement</div></div>
<div class="card"><div class="metric">5</div><div class="lbl">Labeler Pool (was 2)</div></div>
<div class="card" style="grid-column:span 4">
<div style="color:#94a3b8;font-size:12px;margin-bottom:8px">REWARD MODEL ACCURACY — <span style="color:#64748b">■ V1</span> <span style="color:#38bdf8">■ V2</span></div>
<svg width="100%" height="190" viewBox="0 0 600 190">
<polyline points="{pts_v1}" fill="none" stroke="#64748b" stroke-width="1.5" stroke-dasharray="5"/>
<polyline points="{pts_v2}" fill="none" stroke="#38bdf8" stroke-width="2"/>
<line x1="10" y1="{170-int(0.5*155)}" x2="590" y2="{170-int(0.5*155)}" stroke="#334155" stroke-width="1" stroke-dasharray="3"/>
<text x="14" y="{165-int(0.5*155)}" fill="#64748b" font-size="9">50% baseline</text>
<line x1="10" y1="173" x2="590" y2="173" stroke="#334155" stroke-width="1"/>
</svg></div></div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Reward Model V2")
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
