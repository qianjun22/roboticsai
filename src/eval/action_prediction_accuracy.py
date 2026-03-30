"""Action Prediction Accuracy — FastAPI port 8526"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8526

def build_html():
    axes = ["J1","J2","J3","J4","J5","J6","grip"]
    mae = [round(random.uniform(0.008, 0.025), 4) for _ in axes]
    bars = "".join(f'<rect x="{30+i*70}" y="{160-int(m*5000)}" width="50" height="{int(m*5000)}" fill="#38bdf8" rx="3"/><text x="{55+i*70}" y="{155-int(m*5000)}" fill="#94a3b8" font-size="9" text-anchor="middle">{m}</text><text x="{55+i*70}" y="175" fill="#64748b" font-size="10" text-anchor="middle">{a}</text>' for i,(a,m) in enumerate(zip(axes,mae)))
    return f"""<!DOCTYPE html><html><head><title>Action Prediction Accuracy</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:monospace}}
.hdr{{background:#1e293b;padding:16px 24px;border-bottom:2px solid #C74634}}
h1{{margin:0;color:#C74634;font-size:20px}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;padding:24px}}
.card{{background:#1e293b;border-radius:8px;padding:16px;border:1px solid #334155}}
.metric{{font-size:28px;color:#38bdf8;font-weight:bold}}
.lbl{{color:#64748b;font-size:12px;margin-top:4px}}</style></head>
<body><div class="hdr"><h1>Action Prediction Accuracy</h1><span style="color:#64748b">Per-DOF MAE tracker | Port {PORT}</span></div>
<div class="grid">
<div class="card"><div class="metric">0.013</div><div class="lbl">Mean MAE</div></div>
<div class="card"><div class="metric">{min(mae)}</div><div class="lbl">Best DOF MAE</div></div>
<div class="card"><div class="metric">{max(mae)}</div><div class="lbl">Worst DOF MAE</div></div>
<div class="card"><div class="metric">8.7×</div><div class="lbl">vs Baseline</div></div>
<div class="card" style="grid-column:span 4">
<div style="color:#94a3b8;font-size:12px;margin-bottom:8px">MAE PER JOINT AXIS</div>
<svg width="100%" height="190" viewBox="0 0 530 190">{bars}
<line x1="20" y1="165" x2="520" y2="165" stroke="#334155" stroke-width="1"/>
</svg></div></div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Action Prediction Accuracy")
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
