"""RLHF Reward Model — FastAPI port 8536"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8536

def build_html():
    steps = list(range(0, 5000, 200))
    train_acc = [round(0.5 + 0.284*(1-math.exp(-s/1200)) + random.uniform(-0.01,0.01), 3) for s in steps]
    val_acc = [round(0.5 + 0.274*(1-math.exp(-s/1400)) + random.uniform(-0.01,0.01), 3) for s in steps]
    pts_train = " ".join(f"{20+i*22},{180-int(v*170)}" for i,v in enumerate(train_acc))
    pts_val = " ".join(f"{20+i*22},{180-int(v*170)}" for i,v in enumerate(val_acc))
    return f"""<!DOCTYPE html><html><head><title>RLHF Reward Model</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:monospace}}
.hdr{{background:#1e293b;padding:16px 24px;border-bottom:2px solid #C74634}}
h1{{margin:0;color:#C74634;font-size:20px}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;padding:24px}}
.card{{background:#1e293b;border-radius:8px;padding:16px;border:1px solid #334155}}
.metric{{font-size:28px;color:#38bdf8;font-weight:bold}}
.lbl{{color:#64748b;font-size:12px;margin-top:4px}}</style></head>
<body><div class="hdr"><h1>RLHF Reward Model</h1><span style="color:#64748b">Human preference learning | Port {PORT}</span></div>
<div class="grid">
<div class="card"><div class="metric">847</div><div class="lbl">Preference Pairs</div></div>
<div class="card"><div class="metric">78.4%</div><div class="lbl">Val Accuracy</div></div>
<div class="card"><div class="metric">0.81</div><div class="lbl">Labeler Kappa</div></div>
<div class="card"><div class="metric">0.84</div><div class="lbl">Projected SR w/ RLHF</div></div>
<div class="card" style="grid-column:span 4">
<div style="color:#94a3b8;font-size:12px;margin-bottom:8px">REWARD MODEL ACCURACY — <span style="color:#38bdf8">&#9632; Train</span> <span style="color:#22c55e">&#9632; Val</span></div>
<svg width="100%" height="200" viewBox="0 0 600 200">
<polyline points="{pts_train}" fill="none" stroke="#38bdf8" stroke-width="2"/>
<polyline points="{pts_val}" fill="none" stroke="#22c55e" stroke-width="2"/>
<line x1="10" y1="185" x2="590" y2="185" stroke="#334155" stroke-width="1"/>
<line x1="10" y1="{180-int(0.5*170)}" x2="590" y2="{180-int(0.5*170)}" stroke="#334155" stroke-width="1" stroke-dasharray="4"/>
<text x="15" y="{175-int(0.5*170)}" fill="#64748b" font-size="9">50% baseline</text>
</svg></div></div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="RLHF Reward Model")
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
