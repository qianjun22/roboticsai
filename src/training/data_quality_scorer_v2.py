"""Data Quality Scorer V2 — FastAPI port 8548"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8548

def build_html():
    scores = [round(random.uniform(0.2, 1.0), 3) for _ in range(50)]
    scores.sort()
    # histogram
    bins = [0]*10
    for s in scores:
        idx = min(int(s*10), 9)
        bins[idx] += 1
    bars = "".join(f'<rect x="{20+i*54}" y="{160-bins[i]*12}" width="44" height="{bins[i]*12}" fill="{("#C74634" if i<4 else "#38bdf8")}" rx="3"/><text x="{42+i*54}" y="175" fill="#64748b" font-size="9" text-anchor="middle">{i/10:.1f}-{(i+1)/10:.1f}</text>' for i in range(10))
    rejected = sum(1 for s in scores if s < 0.4)
    return f"""<!DOCTYPE html><html><head><title>Data Quality Scorer V2</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:monospace}}
.hdr{{background:#1e293b;padding:16px 24px;border-bottom:2px solid #C74634}}
h1{{margin:0;color:#C74634;font-size:20px}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;padding:24px}}
.card{{background:#1e293b;border-radius:8px;padding:16px;border:1px solid #334155}}
.metric{{font-size:28px;color:#38bdf8;font-weight:bold}}
.lbl{{color:#64748b;font-size:12px;margin-top:4px}}</style></head>
<body><div class="hdr"><h1>Data Quality Scorer V2</h1><span style="color:#64748b">Demo quality analysis | Port {PORT}</span></div>
<div class="grid">
<div class="card"><div class="metric">{len(scores)}</div><div class="lbl">Demos Scored</div></div>
<div class="card"><div class="metric">{rejected}</div><div class="lbl">Rejected (&lt;0.4)</div></div>
<div class="card"><div class="metric">{round(sum(scores)/len(scores),3)}</div><div class="lbl">Mean Quality Score</div></div>
<div class="card"><div class="metric">0.81</div><div class="lbl">High-Quality SR</div></div>
<div class="card" style="grid-column:span 4">
<div style="color:#94a3b8;font-size:12px;margin-bottom:8px">QUALITY SCORE DISTRIBUTION — <span style="color:#C74634">&#9632; Rejected</span> <span style="color:#38bdf8">&#9632; Accepted</span></div>
<svg width="100%" height="200" viewBox="0 0 580 200">{bars}
<line x1="10" y1="163" x2="570" y2="163" stroke="#334155" stroke-width="1"/>
</svg></div></div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Data Quality Scorer V2")
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
