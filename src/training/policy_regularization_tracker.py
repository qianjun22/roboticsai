"""Policy Regularization Tracker — FastAPI port 8584"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8584

def build_html():
    steps = list(range(0, 5000, 200))
    train_loss = [round(0.35 - 0.25*(1-math.exp(-s/1200)) + random.uniform(-0.005,0.005), 4) for s in steps]
    val_loss = [round(0.38 - 0.22*(1-math.exp(-s/1400)) + random.uniform(-0.006,0.006), 4) for s in steps]
    pts_t = " ".join(f"{15+i*22},{170-int(v*400)}" for i,v in enumerate(train_loss))
    pts_v = " ".join(f"{15+i*22},{170-int(v*400)}" for i,v in enumerate(val_loss))
    strategies = ["No Reg", "L2 wd=0.01", "L2 wd=0.1", "Dropout 0.1"]
    sr = [0.75, 0.78, 0.76, 0.74]
    bars = "".join(f'<rect x="{20+i*120}" y="{130-int(v*100)}" width="90" height="{int(v*100)}" fill="{("#22c55e" if v==max(sr) else "#38bdf8")}" rx="3"/><text x="{65+i*120}" y="{125-int(v*100)}" fill="#94a3b8" font-size="10" text-anchor="middle">{v}</text><text x="{65+i*120}" y="148" fill="#64748b" font-size="9" text-anchor="middle">{s.split(" ")[0][:8]}</text>' for i,(s,v) in enumerate(zip(strategies,sr)))
    return f"""<!DOCTYPE html><html><head><title>Policy Regularization Tracker</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:monospace}}
.hdr{{background:#1e293b;padding:16px 24px;border-bottom:2px solid #C74634}}
h1{{margin:0;color:#C74634;font-size:20px}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;padding:24px}}
.card{{background:#1e293b;border-radius:8px;padding:16px;border:1px solid #334155}}
.metric{{font-size:28px;color:#38bdf8;font-weight:bold}}
.lbl{{color:#64748b;font-size:12px;margin-top:4px}}</style></head>
<body><div class="hdr"><h1>Policy Regularization Tracker</h1><span style="color:#64748b">Regularization ablation | Port {PORT}</span></div>
<div class="grid">
<div class="card"><div class="metric">L2 wd=0.01</div><div class="lbl">Optimal Strategy</div></div>
<div class="card"><div class="metric">+0.03pp</div><div class="lbl">vs No Regularization</div></div>
<div class="card"><div class="metric">-18%</div><div class="lbl">Compute Saved (early stop)</div></div>
<div class="card"><div class="metric">-0.04pp</div><div class="lbl">Dropout at Action Head</div></div>
<div class="card" style="grid-column:span 4">
<div style="color:#94a3b8;font-size:12px;margin-bottom:8px">SR BY REGULARIZATION STRATEGY</div>
<svg width="100%" height="170" viewBox="0 0 540 170">{bars}
<line x1="10" y1="133" x2="530" y2="133" stroke="#334155" stroke-width="1"/>
</svg></div></div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Policy Regularization Tracker")
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
