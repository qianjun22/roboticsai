"""Embodiment Transfer Tracker — FastAPI port 8528"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8528

def build_html():
    robots = ["Franka","UR10","Stretch","xArm"]
    matrix = [[100,89,62,78],[74,100,55,81],[48,52,100,61],[71,75,58,100]]
    cells = "".join(
        f'<rect x="{80+j*80}" y="{40+i*60}" width="70" height="50" fill="{"#1e3a5f" if i==j else ("#38bdf8" if matrix[i][j]>80 else ("#334155" if matrix[i][j]<60 else "#1e4a3a"))}" rx="3"/>'
        f'<text x="{115+j*80}" y="{70+i*60}" fill="#e2e8f0" font-size="14" text-anchor="middle">{matrix[i][j]}%</text>'
        for i in range(4) for j in range(4)
    )
    labels = "".join(f'<text x="{115+i*80}" y="30" fill="#94a3b8" font-size="11" text-anchor="middle">{r}</text><text x="70" y="{70+i*60}" fill="#94a3b8" font-size="11" text-anchor="end">{r}</text>' for i,r in enumerate(robots))
    return f"""<!DOCTYPE html><html><head><title>Embodiment Transfer Tracker</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:monospace}}
.hdr{{background:#1e293b;padding:16px 24px;border-bottom:2px solid #C74634}}
h1{{margin:0;color:#C74634;font-size:20px}}
.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;padding:24px}}
.card{{background:#1e293b;border-radius:8px;padding:16px;border:1px solid #334155}}
.metric{{font-size:28px;color:#38bdf8;font-weight:bold}}
.lbl{{color:#64748b;font-size:12px;margin-top:4px}}</style></head>
<body><div class="hdr"><h1>Embodiment Transfer Tracker</h1><span style="color:#64748b">Cross-robot transfer efficiency | Port {PORT}</span></div>
<div class="grid">
<div class="card"><div class="metric">0.74</div><div class="lbl">GR00T Agnostic Score</div></div>
<div class="card"><div class="metric">89%</div><div class="lbl">Best Transfer (F→U)</div></div>
<div class="card"><div class="metric">31%</div><div class="lbl">Zero-Shot Baseline</div></div>
<div class="card" style="grid-column:span 3">
<div style="color:#94a3b8;font-size:12px;margin-bottom:8px">TRANSFER EFFICIENCY MATRIX (source → target)</div>
<svg width="420" height="295" viewBox="0 0 420 295">{labels}{cells}</svg>
</div></div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Embodiment Transfer Tracker")
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
