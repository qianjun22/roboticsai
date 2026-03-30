"""Fleet Cost Optimizer V2 — FastAPI port 8527"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8527

def build_html():
    days = list(range(1, 8))
    spot = [round(random.uniform(1.8, 3.2), 2) for _ in days]
    ondemand = [9.80] * 7
    pts_spot = " ".join(f"{40+i*80},{180-int(v*15)}" for i, v in enumerate(spot))
    pts_od = " ".join(f"{40+i*80},{180-int(v*15)}" for i, v in enumerate(ondemand))
    savings = sum(o-s for o,s in zip(ondemand, spot))
    return f"""<!DOCTYPE html><html><head><title>Fleet Cost Optimizer V2</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:monospace}}
.hdr{{background:#1e293b;padding:16px 24px;border-bottom:2px solid #C74634}}
h1{{margin:0;color:#C74634;font-size:20px}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;padding:24px}}
.card{{background:#1e293b;border-radius:8px;padding:16px;border:1px solid #334155}}
.metric{{font-size:28px;color:#38bdf8;font-weight:bold}}
.lbl{{color:#64748b;font-size:12px;margin-top:4px}}</style></head>
<body><div class="hdr"><h1>Fleet Cost Optimizer V2</h1><span style="color:#64748b">Spot vs on-demand savings | Port {PORT}</span></div>
<div class="grid">
<div class="card"><div class="metric">$2.47</div><div class="lbl">Avg Spot $/hr</div></div>
<div class="card"><div class="metric">$9.80</div><div class="lbl">On-Demand $/hr</div></div>
<div class="card"><div class="metric">${round(savings,0):.0f}</div><div class="lbl">7-Day Savings</div></div>
<div class="card"><div class="metric">75%</div><div class="lbl">Cost Reduction</div></div>
<div class="card" style="grid-column:span 4">
<div style="color:#94a3b8;font-size:12px;margin-bottom:8px">SPOT vs ON-DEMAND ($/hr) — <span style="color:#38bdf8">&#9632; Spot</span> <span style="color:#C74634">&#9632; On-Demand</span></div>
<svg width="100%" height="210" viewBox="0 0 600 210">
<polyline points="{pts_od}" fill="none" stroke="#C74634" stroke-width="2" stroke-dasharray="6"/>
<polyline points="{pts_spot}" fill="none" stroke="#38bdf8" stroke-width="2"/>
<line x1="20" y1="185" x2="590" y2="185" stroke="#334155" stroke-width="1"/>
</svg></div></div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Fleet Cost Optimizer V2")
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
