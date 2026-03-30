"""Multi-Task Finetuning — FastAPI port 8422"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8422

def build_html():
    tasks = ["pick_place","stack","pour","insert","fold"]
    # 3 strategies: shared, per-task, LoRA-adapter
    shared_sr =   [0.71, 0.64, 0.55, 0.47, 0.38]
    pertask_sr =  [0.78, 0.72, 0.61, 0.54, 0.47]
    lora_sr =     [0.78, 0.73, 0.63, 0.56, 0.49]

    colors3 = ["#475569","#38bdf8","#C74634"]
    strategy_labels = ["Shared","Per-task","LoRA_adapt"]
    bw8 = 24; gap8 = 8

    svg_bar = '<svg width="420" height="220" style="background:#0f172a">'
    svg_bar += '<line x1="40" y1="10" x2="40" y2="170" stroke="#475569" stroke-width="1"/>'
    svg_bar += '<line x1="40" y1="170" x2="400" y2="170" stroke="#475569" stroke-width="1"/>'
    for i in range(5):
        yv = i*0.2; y = 170-yv*150
        svg_bar += f'<text x="35" y="{y+4}" fill="#94a3b8" font-size="7" text-anchor="end">{yv:.1f}</text>'
    grp_w = (bw8+2)*3+gap8
    for ti, task in enumerate(tasks):
        for si, (sr, col) in enumerate(zip([shared_sr, pertask_sr, lora_sr], colors3)):
            x = 45+ti*grp_w+si*(bw8+2)
            h = sr[ti]*150; y = 170-h
            svg_bar += f'<rect x="{x}" y="{y:.0f}" width="{bw8}" height="{h:.0f}" fill="{col}" opacity="0.85"/>'
        tx = 45+ti*grp_w+(bw8+2)*3//2
        svg_bar += f'<text x="{tx}" y="183" fill="#94a3b8" font-size="8" text-anchor="middle">{task[:5]}</text>'
    for si, (label, col) in enumerate(zip(strategy_labels, colors3)):
        svg_bar += f'<rect x="{250+si*75}" y="195" width="10" height="8" fill="{col}"/>'
        svg_bar += f'<text x="{263+si*75}" y="203" fill="#94a3b8" font-size="8">{label}</text>'
    svg_bar += '</svg>'

    # Task interference heatmap
    interference = [
        [1.0, 0.91, 0.41, 0.28, 0.12],
        [0.88, 1.0, 0.38, 0.31, 0.15],
        [0.35, 0.31, 1.0, 0.54, 0.22],
        [0.24, 0.27, 0.51, 1.0, 0.34],
        [0.11, 0.13, 0.19, 0.31, 1.0],
    ]
    cw9, rh9 = 52, 28
    svg_int = f'<svg width="{len(tasks)*cw9+90}" height="{len(tasks)*rh9+60}" style="background:#0f172a">'
    for ti, task in enumerate(tasks):
        svg_int += f'<text x="{90+ti*cw9+26}" y="18" fill="#94a3b8" font-size="8" text-anchor="middle">{task[:5]}</text>'
        svg_int += f'<text x="85" y="{36+ti*rh9+16}" fill="#94a3b8" font-size="8" text-anchor="end">{task[:5]}</text>'
    for ri in range(len(tasks)):
        for ci in range(len(tasks)):
            v = interference[ri][ci]
            col_v = "#22c55e" if v > 0.8 else "#f59e0b" if v > 0.4 else "#C74634"
            svg_int += f'<rect x="{90+ci*cw9}" y="{30+ri*rh9}" width="{cw9-2}" height="{rh9-2}" fill="{col_v}" opacity="{max(0.3,v):.2f}"/>'
            svg_int += f'<text x="{90+ci*cw9+26}" y="{30+ri*rh9+16}" fill="white" font-size="8" text-anchor="middle">{v:.2f}</text>'
    svg_int += '</svg>'

    return f"""<!DOCTYPE html><html><head><title>Multi-Task Finetuning — Port {PORT}</title>
<style>body{{background:#0f172a;color:#e2e8f0;font-family:monospace;margin:0;padding:20px}}
h1{{color:#C74634;font-size:18px}}h2{{color:#38bdf8;font-size:14px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:20px}}
.card{{background:#1e293b;padding:16px;border-radius:8px}}
.stat{{font-size:24px;color:#C74634;font-weight:bold}}
.label{{color:#94a3b8;font-size:12px}}</style></head>
<body><h1>Multi-Task Finetuning</h1>
<p style="color:#94a3b8">Port {PORT} | Shared vs per-task vs LoRA adapter comparison + task interference</p>
<div class="grid">
<div class="card"><h2>SR by Strategy per Task</h2>{svg_bar}</div>
<div class="card"><h2>Task Transfer Interference Matrix</h2>{svg_int}
<div style="margin-top:8px">
<div class="stat">+7pp</div><div class="label">LoRA adapter vs shared fine-tune (avg)</div>
<div style="margin-top:8px;color:#94a3b8;font-size:11px">pick_place → stack: 0.91 positive transfer (best pair)<br>pour/insert: negative transfer with manipulation tasks<br>fold isolated: low transfer to/from all others (0.11-0.19)<br>Recommendation: LoRA per-task for production deployment</div>
</div></div></div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Multi-Task Finetuning")
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
