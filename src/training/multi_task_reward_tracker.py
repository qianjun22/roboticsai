"""Multi-Task Reward Tracker — FastAPI port 8532"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8532

def build_html():
    tasks = ["pick", "place", "pour", "sort"]
    colors = ["#38bdf8", "#22c55e", "#f59e0b", "#C74634"]
    steps = list(range(0, 5000, 200))
    rewards = {
        "pick": [round(0.1 + 0.7*(1-math.exp(-s/1200)) + random.uniform(-0.03,0.03), 3) for s in steps],
        "place": [round(0.08 + 0.65*(1-math.exp(-s/1400)) + random.uniform(-0.03,0.03), 3) for s in steps],
        "pour": [round(0.05 + 0.55*(1-math.exp(-s/2000)) + random.uniform(-0.04,0.04), 3) for s in steps],
        "sort": [round(0.09 + 0.60*(1-math.exp(-s/1600)) + random.uniform(-0.03,0.03), 3) for s in steps],
    }
    lines = "".join(f'<polyline points="{" ".join(f"{20+i*24},{180-int(v*140)}" for i,v in enumerate(rewards[t]))}" fill="none" stroke="{c}" stroke-width="2"/>' for t,c in zip(tasks,colors))
    legend = "".join(f'<rect x="{20+i*80}" y="8" width="12" height="12" fill="{c}"/><text x="{36+i*80}" y="19" fill="#94a3b8" font-size="10">{t}</text>' for i,(t,c) in enumerate(zip(tasks,colors)))
    return f"""<!DOCTYPE html><html><head><title>Multi-Task Reward Tracker</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:monospace}}
.hdr{{background:#1e293b;padding:16px 24px;border-bottom:2px solid #C74634}}
h1{{margin:0;color:#C74634;font-size:20px}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;padding:24px}}
.card{{background:#1e293b;border-radius:8px;padding:16px;border:1px solid #334155}}
.metric{{font-size:28px;color:#38bdf8;font-weight:bold}}
.lbl{{color:#64748b;font-size:12px;margin-top:4px}}</style></head>
<body><div class="hdr"><h1>Multi-Task Reward Tracker</h1><span style="color:#64748b">Per-task reward evolution | Port {PORT}</span></div>
<div class="grid">
<div class="card"><div class="metric">4</div><div class="lbl">Active Tasks</div></div>
<div class="card"><div class="metric">PCGrad</div><div class="lbl">Optimizer</div></div>
<div class="card"><div class="metric">-34%</div><div class="lbl">Gradient Conflict Reduction</div></div>
<div class="card"><div class="metric">pour</div><div class="lbl">Hardest Task</div></div>
<div class="card" style="grid-column:span 4">
<div style="color:#94a3b8;font-size:12px;margin-bottom:8px">REWARD EVOLUTION BY TASK</div>
<svg width="100%" height="215" viewBox="0 0 600 215">
<g transform="translate(0,25)">{lines}</g>
{legend}
<line x1="20" y1="210" x2="590" y2="210" stroke="#334155" stroke-width="1"/>
</svg></div></div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Multi-Task Reward Tracker")
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
