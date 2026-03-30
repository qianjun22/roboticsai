"""Wrist Force Torque Analyzer — FastAPI port 8558"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8558

def build_html():
    steps = list(range(0, 500, 10))
    fz = [round(2 + 6*max(0, math.sin((s-150)/40)) + random.uniform(-0.3,0.3), 2) for s in steps]
    tz = [round(0.1*math.sin(s/30) + random.uniform(-0.05,0.05), 3) for s in steps]
    pts_fz = " ".join(f"{10+i*11},{160-int(v*12)}" for i,v in enumerate(fz))
    pts_tz = " ".join(f"{10+i*11},{200-int(v*60)}" for i,v in enumerate(tz))
    return f"""<!DOCTYPE html><html><head><title>Wrist Force Torque Analyzer</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:monospace}}
.hdr{{background:#1e293b;padding:16px 24px;border-bottom:2px solid #C74634}}
h1{{margin:0;color:#C74634;font-size:20px}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;padding:24px}}
.card{{background:#1e293b;border-radius:8px;padding:16px;border:1px solid #334155}}
.metric{{font-size:28px;color:#38bdf8;font-weight:bold}}
.lbl{{color:#64748b;font-size:12px;margin-top:4px}}</style></head>
<body><div class="hdr"><h1>Wrist Force Torque Analyzer</h1><span style="color:#64748b">6-axis F/T sensor | Port {PORT}</span></div>
<div class="grid">
<div class="card"><div class="metric">8±1N</div><div class="lbl">Target Contact Force Fz</div></div>
<div class="card"><div class="metric">94%</div><div class="lbl">Within Target Range</div></div>
<div class="card"><div class="metric">0</div><div class="lbl">Torque Violations</div></div>
<div class="card"><div class="metric">±0.3Nm</div><div class="lbl">Wrist Tz Variance</div></div>
<div class="card" style="grid-column:span 4">
<div style="color:#94a3b8;font-size:12px;margin-bottom:4px">Fz CONTACT FORCE (N)</div>
<svg width="100%" height="180" viewBox="0 0 570 180">
<polyline points="{pts_fz}" fill="none" stroke="#38bdf8" stroke-width="1.5"/>
<line x1="10" y1="{160-int(9*12)}" x2="560" y2="{160-int(9*12)}" stroke="#22c55e" stroke-width="1" stroke-dasharray="4"/>
<line x1="10" y1="{160-int(7*12)}" x2="560" y2="{160-int(7*12)}" stroke="#22c55e" stroke-width="1" stroke-dasharray="4"/>
<text x="14" y="{155-int(9*12)}" fill="#22c55e" font-size="9">9N</text>
<text x="14" y="{155-int(7*12)}" fill="#22c55e" font-size="9">7N</text>
<line x1="10" y1="163" x2="560" y2="163" stroke="#334155" stroke-width="1"/>
</svg></div></div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Wrist Force Torque Analyzer")
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
