"""Model Explainability Dashboard — FastAPI port 8559"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8559

def build_html():
    features = ["Wrist Cam", "RGB", "Depth", "Proprioception", "Language"]
    shap = [0.38, 0.28, 0.21, 0.09, 0.04]
    colors = ["#38bdf8","#22c55e","#f59e0b","#C74634","#a78bfa"]
    bars = "".join(f'<rect x="150" y="{20+i*46}" width="{int(s*500)}" height="32" fill="{c}" rx="3"/><text x="145" y="{40+i*46}" fill="#94a3b8" font-size="11" text-anchor="end">{f}</text><text x="{155+int(s*500)}" y="{40+i*46}" fill="#e2e8f0" font-size="11">{s:.0%}</text>' for i,(f,s,c) in enumerate(zip(features,shap,colors)))
    return f"""<!DOCTYPE html><html><head><title>Model Explainability Dashboard</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:monospace}}
.hdr{{background:#1e293b;padding:16px 24px;border-bottom:2px solid #C74634}}
h1{{margin:0;color:#C74634;font-size:20px}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;padding:24px}}
.card{{background:#1e293b;border-radius:8px;padding:16px;border:1px solid #334155}}
.metric{{font-size:28px;color:#38bdf8;font-weight:bold}}
.lbl{{color:#64748b;font-size:12px;margin-top:4px}}</style></head>
<body><div class="hdr"><h1>Model Explainability Dashboard</h1><span style="color:#64748b">SHAP feature attribution | Port {PORT}</span></div>
<div class="grid">
<div class="card"><div class="metric">Wrist Cam</div><div class="lbl">Top Feature (38%)</div></div>
<div class="card"><div class="metric">74%</div><div class="lbl">Grasp Attention on Gripper</div></div>
<div class="card"><div class="metric">3</div><div class="lbl">Behavioral Clusters</div></div>
<div class="card"><div class="metric">18%</div><div class="lbl">Early Contact Failures</div></div>
<div class="card" style="grid-column:span 4">
<div style="color:#94a3b8;font-size:12px;margin-bottom:8px">SHAP FEATURE IMPORTANCE</div>
<svg width="100%" height="{20+len(features)*46+10}" viewBox="0 660 {20+len(features)*46+10}">{bars}</svg>
</div></div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Model Explainability Dashboard")
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
