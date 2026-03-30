"""Revenue Forecast V2 — FastAPI port 8539"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8539

def build_html():
    months = ["Mar","Apr","May","Jun","Jul","Aug","Sep"]
    base = [2927, 5200, 8400, 12000, 16500, 21000, 28000]
    bull = [2927, 6100, 10800, 17000, 26000, 38000, 56000]
    bear = [2927, 3800, 5200, 7000, 9000, 11000, 14000]
    pts_base = " ".join(f"{40+i*80},{220-int(v/180)}" for i,v in enumerate(base))
    pts_bull = " ".join(f"{40+i*80},{220-int(v/180)}" for i,v in enumerate(bull))
    pts_bear = " ".join(f"{40+i*80},{220-int(v/180)}" for i,v in enumerate(bear))
    xlabels = "".join(f'<text x="{40+i*80}" y="238" fill="#64748b" font-size="10" text-anchor="middle">{m}</text>' for i,m in enumerate(months))
    return f"""<!DOCTYPE html><html><head><title>Revenue Forecast V2</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:monospace}}
.hdr{{background:#1e293b;padding:16px 24px;border-bottom:2px solid #C74634}}
h1{{margin:0;color:#C74634;font-size:20px}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;padding:24px}}
.card{{background:#1e293b;border-radius:8px;padding:16px;border:1px solid #334155}}
.metric{{font-size:28px;color:#38bdf8;font-weight:bold}}
.lbl{{color:#64748b;font-size:12px;margin-top:4px}}</style></head>
<body><div class="hdr"><h1>Revenue Forecast V2</h1><span style="color:#64748b">Monte Carlo ARR projection | Port {PORT}</span></div>
<div class="grid">
<div class="card"><div class="metric">$180K</div><div class="lbl">Base ARR (Sep 2026)</div></div>
<div class="card"><div class="metric">$340K</div><div class="lbl">Bull ARR (3 enterprise)</div></div>
<div class="card"><div class="metric">$72K</div><div class="lbl">Bear ARR (1 partner)</div></div>
<div class="card"><div class="metric">6.8/10</div><div class="lbl">Series A Readiness</div></div>
<div class="card" style="grid-column:span 4">
<div style="color:#94a3b8;font-size:12px;margin-bottom:8px">MRR SCENARIOS — <span style="color:#38bdf8">■ Base</span> <span style="color:#22c55e">■ Bull</span> <span style="color:#C74634">■ Bear</span></div>
<svg width="100%" height="255" viewBox="0 0 560 255">
<polyline points="{pts_bear}" fill="none" stroke="#C74634" stroke-width="1.5" stroke-dasharray="5"/>
<polyline points="{pts_base}" fill="none" stroke="#38bdf8" stroke-width="2"/>
<polyline points="{pts_bull}" fill="none" stroke="#22c55e" stroke-width="1.5" stroke-dasharray="5"/>
{xlabels}
<line x1="20" y1="225" x2="540" y2="225" stroke="#334155" stroke-width="1"/>
</svg></div></div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Revenue Forecast V2")
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
