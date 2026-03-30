"""Task Completion Analyzer — FastAPI port 8404"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8404

def build_html():
    # Per-subtask success rate Sankey-style flow
    stages = ["Reach","Grasp","Lift","Place"]
    sr = [0.92, 0.84, 0.71, 0.63]
    colors = ["#22c55e","#38bdf8","#f59e0b","#C74634"]

    svg_s = '<svg width="360" height="180" style="background:#0f172a">'
    for i, (st, s, col) in enumerate(zip(stages, sr, colors)):
        x = 30 + i*80; w = int(s*60); y_center = 90
        h = w
        svg_s += f'<rect x="{x}" y="{y_center-h//2}" width="50" height="{h}" fill="{col}" rx="4" opacity="0.85"/>'
        svg_s += f'<text x="{x+25}" y="{y_center-h//2-5}" fill="{col}" font-size="10" text-anchor="middle">{s:.0%}</text>'
        svg_s += f'<text x="{x+25}" y="{y_center+h//2+14}" fill="#94a3b8" font-size="9" text-anchor="middle">{st}</text>'
        if i < len(stages)-1:
            x2 = x+50; x3 = x+80
            svg_s += f'<line x1="{x2}" y1="{y_center}" x2="{x3}" y2="{y_center}" stroke="#475569" stroke-width="2" stroke-dasharray="3,2"/>'
    svg_s += '<text x="180" y="168" fill="#C74634" font-size="9" text-anchor="middle">Bottleneck: Lift (71%) — insufficient grasp force</text>'
    svg_s += '</svg>'

    # Episode length distribution by task
    tasks = ["pick_place","stack","pour","insert","fold"]
    task_colors = ["#22c55e","#38bdf8","#f59e0b","#a78bfa","#C74634"]
    svg_e = '<svg width="360" height="200" style="background:#0f172a">'
    svg_e += '<line x1="40" y1="10" x2="40" y2="170" stroke="#475569" stroke-width="1"/>'
    svg_e += '<line x1="40" y1="170" x2="350" y2="170" stroke="#475569" stroke-width="1"/>'
    for i in range(5):
        y = 170 - i*32; yv = i*200
        svg_e += f'<text x="35" y="{y+4}" fill="#94a3b8" font-size="8" text-anchor="end">{yv}</text>'
    bins = [200,300,400,500,600,700,800,900]
    bw2 = 34
    for ti, (task, col) in enumerate(zip(tasks, task_colors)):
        mean_len = 350 + ti*80; std_len = 100
        for bi, b in enumerate(bins):
            x = 45 + bi*bw2
            count = int(30*math.exp(-0.5*((b-mean_len)/std_len)**2))
            h = count*5
            svg_e += f'<rect x="{x}" y="{170-h}" width="{bw2-2}" height="{h}" fill="{col}" opacity="{0.5-ti*0.05:.2f}"/>'
    for bi, b in enumerate(bins):
        x = 45 + bi*bw2 + bw2//2
        svg_e += f'<text x="{x}" y="182" fill="#94a3b8" font-size="7" text-anchor="middle">{b}</text>'
    svg_e += '<text x="190" y="196" fill="#94a3b8" font-size="9" text-anchor="middle">Episode Length (steps)</text>'
    svg_e += '</svg>'

    return f"""<!DOCTYPE html><html><head><title>Task Completion Analyzer — Port {PORT}</title>
<style>body{{background:#0f172a;color:#e2e8f0;font-family:monospace;margin:0;padding:20px}}
h1{{color:#C74634;font-size:18px}}h2{{color:#38bdf8;font-size:14px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:20px}}
.card{{background:#1e293b;padding:16px;border-radius:8px}}
.stat{{font-size:24px;color:#C74634;font-weight:bold}}
.label{{color:#94a3b8;font-size:12px}}</style></head>
<body><h1>Task Completion Analyzer</h1>
<p style="color:#94a3b8">Port {PORT} | Per-subtask SR + episode length analysis</p>
<div class="grid">
<div class="card"><h2>Subtask Success Rate Flow</h2>{svg_s}
<div style="margin-top:10px">
<div class="stat">71%</div><div class="label">Lift SR — bottleneck stage</div>
<div style="margin-top:8px;color:#94a3b8;font-size:11px">Reach: 92% (strong) → Grasp: 84% → Lift: 71% → Place: 63%<br>Fix: increase grasp force threshold for lift phase<br>Partial credit scoring enabled for training signal</div>
</div></div>
<div class="card"><h2>Episode Length by Task</h2>{svg_e}
<div style="margin-top:8px;color:#94a3b8;font-size:11px">Short episodes = successful (reach fast)<br>Long episodes = failure (repeated attempts)<br>pick_place fastest: avg 350 steps<br>fold slowest: avg 750 steps</div>
</div></div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Task Completion Analyzer")
    @app.get("/", response_class=HTMLResponse)
    def index(): return build_html()
    @app.get("/health")
    def health(): return {"status": "ok", "port": PORT}

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(build_html().encode())
    def log_message(self, *a): pass

if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
