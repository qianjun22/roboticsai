"""Action Sequence Planner — FastAPI port 8566"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8566

def build_html():
    subtasks = ["Approach", "Pre-grasp", "Grasp", "Lift", "Transport", "Position", "Place", "Release"]
    sr = [0.84, 0.91, 0.94, 0.96, 0.97, 0.89, 0.92, 0.98]
    product = 1.0
    for v in sr: product *= v
    bars = "".join(f'<rect x="{20+i*68}" y="{160-int(v*130)}" width="54" height="{int(v*130)}" fill="{("#C74634" if v==min(sr) else "#38bdf8")}" rx="3"/><text x="{47+i*68}" y="{155-int(v*130)}" fill="#94a3b8" font-size="9" text-anchor="middle">{v}</text><text x="{47+i*68}" y="177" fill="#64748b" font-size="9" text-anchor="middle">{s[:6]}</text>' for i,(s,v) in enumerate(zip(subtasks,sr)))
    return f"""<!DOCTYPE html><html><head><title>Action Sequence Planner</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:monospace}}
.hdr{{background:#1e293b;padding:16px 24px;border-bottom:2px solid #C74634}}
h1{{margin:0;color:#C74634;font-size:20px}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;padding:24px}}
.card{{background:#1e293b;border-radius:8px;padding:16px;border:1px solid #334155}}
.metric{{font-size:28px;color:#38bdf8;font-weight:bold}}
.lbl{{color:#64748b;font-size:12px;margin-top:4px}}</style></head>
<body><div class="hdr"><h1>Action Sequence Planner</h1><span style="color:#64748b">Subtask SR breakdown | Port {PORT}</span></div>
<div class="grid">
<div class="card"><div class="metric">8</div><div class="lbl">Subtasks</div></div>
<div class="card"><div class="metric">{round(product,3)}</div><div class="lbl">Chain SR (product)</div></div>
<div class="card"><div class="metric">Approach</div><div class="lbl">Weakest Subtask (0.84)</div></div>
<div class="card"><div class="metric">Release</div><div class="lbl">Best Subtask (0.98)</div></div>
<div class="card" style="grid-column:span 4">
<div style="color:#94a3b8;font-size:12px;margin-bottom:8px">SUBTASK SUCCESS RATE — <span style="color:#C74634">■ Bottleneck</span></div>
<svg width="100%" height="200" viewBox="0 0 570 200">{bars}
<line x1="10" y1="162" x2="560" y2="162" stroke="#334155" stroke-width="1"/>
</svg></div></div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Action Sequence Planner")
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
