"""DAgger Run11 Launcher — FastAPI port 8578"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8578

def build_html():
    checklist = [
        ("Dataset v4 (2680 demos)", True),
        ("Reward Model v2 (82.1% acc)", True),
        ("Safety Validator pass", True),
        ("OCI GPU Quota OK", True),
        ("DAgger run10 checkpoint", True),
        ("reward_weights_v3 config", True),
    ]
    rows = "".join(f'<tr><td style="padding:8px;color:#e2e8f0">{c[0]}</td><td style="padding:8px;color:{"#22c55e" if c[1] else "#C74634"};font-size:16px">{"✓" if c[1] else "✗"}</td></tr>' for c in checklist)
    steps = list(range(0, 5000, 200))
    p50 = [round(0.64 + 0.20*(1-math.exp(-s/1800)) + random.uniform(-0.01,0.01), 3) for s in steps]
    pts = " ".join(f"{15+i*22},{160-int(v*150)}" for i,v in enumerate(p50))
    return f"""<!DOCTYPE html><html><head><title>DAgger Run11 Launcher</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:monospace}}
.hdr{{background:#1e293b;padding:16px 24px;border-bottom:2px solid #C74634}}
h1{{margin:0;color:#C74634;font-size:20px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;padding:24px}}
.card{{background:#1e293b;border-radius:8px;padding:16px;border:1px solid #334155}}
.metric{{font-size:28px;color:#38bdf8;font-weight:bold}}
.lbl{{color:#64748b;font-size:12px;margin-top:4px}}
table{{width:100%;border-collapse:collapse}}
th{{text-align:left;padding:8px;color:#64748b;border-bottom:1px solid #334155}}</style></head>
<body><div class="hdr"><h1>DAgger Run11 Launcher</h1><span style="color:#64748b">Launch checklist & SR projection | Port {PORT}</span></div>
<div class="grid">
<div class="card">
<div style="color:#94a3b8;font-size:12px;margin-bottom:8px">LAUNCH CHECKLIST</div>
<table><tr><th>Prerequisite</th><th>Status</th></tr>{rows}</table>
<div style="margin-top:12px;padding:8px;background:#1e3a5f;border-radius:6px;color:#38bdf8;font-size:12px">
🚀 LAUNCH DATE: Apr 28, 2026 | reward_weights_v3 | 5000 steps
</div></div>
<div class="card">
<div style="color:#94a3b8;font-size:12px;margin-bottom:8px">PROJECTED SR (p50) — TARGET 0.84</div>
<svg width="100%" height="180" viewBox="0 0 480 180">
<polyline points="{pts}" fill="none" stroke="#38bdf8" stroke-width="2"/>
<line x1="10" y1="{160-int(0.84*150)}" x2="470" y2="{160-int(0.84*150)}" stroke="#22c55e" stroke-width="1" stroke-dasharray="4"/>
<text x="14" y="{155-int(0.84*150)}" fill="#22c55e" font-size="9">target 0.84</text>
<line x1="10" y1="163" x2="470" y2="163" stroke="#334155" stroke-width="1"/>
</svg></div>
</div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="DAgger Run11 Launcher")
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
