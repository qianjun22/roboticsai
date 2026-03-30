"""GR00T N2.0 Migration Planner — FastAPI port 8546"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8546

def build_html():
    features = ["Diffusion Head", "Bimanual Support", "Improved VLM", "API Compat", "Checkpoint Transfer"]
    n1_support = [0, 0, 0, 1, 1]
    n2_support = [1, 1, 1, 1, 0.7]
    bars_n1 = "".join(f'<rect x="130" y="{20+i*45}" width="{int(n1_support[i]*200)}" height="18" fill="#334155" rx="2"/>' for i in range(len(features)))
    bars_n2 = "".join(f'<rect x="130" y="{38+i*45}" width="{int(n2_support[i]*200)}" height="18" fill="#38bdf8" rx="2"/><text x="125" y="{32+i*45}" fill="#94a3b8" font-size="10" text-anchor="end">{features[i]}</text>' for i in range(len(features)))
    return f"""<!DOCTYPE html><html><head><title>GR00T N2.0 Migration Planner</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:monospace}}
.hdr{{background:#1e293b;padding:16px 24px;border-bottom:2px solid #C74634}}
h1{{margin:0;color:#C74634;font-size:20px}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;padding:24px}}
.card{{background:#1e293b;border-radius:8px;padding:16px;border:1px solid #334155}}
.metric{{font-size:28px;color:#38bdf8;font-weight:bold}}
.lbl{{color:#64748b;font-size:12px;margin-top:4px}}</style></head>
<body><div class="hdr"><h1>GR00T N2.0 Migration Planner</h1><span style="color:#64748b">N1.6→N2.0 upgrade plan | Port {PORT}</span></div>
<div class="grid">
<div class="card"><div class="metric">Q3 2026</div><div class="lbl">N2.0 ETA</div></div>
<div class="card"><div class="metric">12wk</div><div class="lbl">Migration Timeline</div></div>
<div class="card"><div class="metric">+$240</div><div class="lbl">Fine-tune Cost Delta</div></div>
<div class="card"><div class="metric">Medium</div><div class="lbl">Migration Risk</div></div>
<div class="card" style="grid-column:span 4">
<div style="color:#94a3b8;font-size:12px;margin-bottom:8px">N1.6 vs N2.0 FEATURES — <span style="color:#334155">■ N1.6</span> <span style="color:#38bdf8">■ N2.0</span></div>
<svg width="100%" height="{20+len(features)*45+10}" viewBox="0 680 {20+len(features)*45+10}">{bars_n1}{bars_n2}</svg>
</div></div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="GR00T N2.0 Migration Planner")
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
