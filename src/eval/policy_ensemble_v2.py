"""Policy Ensemble V2 — FastAPI port 8518"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8518

def build_html():
    scores = [round(random.uniform(0.70, 0.92), 3) for _ in range(8)]
    bars = "".join(f'<rect x="{30+i*70}" y="{180-int(s*160)}" width="50" height="{int(s*160)}" fill="#38bdf8" rx="3"/><text x="{55+i*70}" y="{175-int(s*160)}" fill="#94a3b8" font-size="9" text-anchor="middle">{s}</text>' for i, s in enumerate(scores))
    return f"""<!DOCTYPE html><html><head><title>Policy Ensemble V2</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:monospace}}
.hdr{{background:#1e293b;padding:16px 24px;border-bottom:2px solid #C74634}}
h1{{margin:0;color:#C74634;font-size:20px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;padding:24px}}
.card{{background:#1e293b;border-radius:8px;padding:16px;border:1px solid #334155}}
.metric{{font-size:28px;color:#38bdf8;font-weight:bold}}
.lbl{{color:#64748b;font-size:12px;margin-top:4px}}</style></head>
<body><div class="hdr"><h1>Policy Ensemble V2</h1><span style="color:#64748b">Multi-policy voting | Port {PORT}</span></div>
<div class="grid">
<div class="card"><div class="metric">{len(scores)}</div><div class="lbl">Ensemble Members</div></div>
<div class="card"><div class="metric">{round(sum(scores)/len(scores),3)}</div><div class="lbl">Mean SR</div></div>
<div class="card"><div class="metric">{max(scores)}</div><div class="lbl">Best Policy SR</div></div>
<div class="card"><div class="metric">Maj Vote</div><div class="lbl">Aggregation Method</div></div>
<div class="card" style="grid-column:span 2">
<div style="color:#94a3b8;font-size:12px;margin-bottom:8px">ENSEMBLE MEMBER SUCCESS RATES</div>
<svg width="100%" height="200" viewBox="0 0 600 200">{bars}
<line x1="30" y1="180" x2="590" y2="180" stroke="#334155" stroke-width="1"/>
</svg></div></div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Policy Ensemble V2")
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
