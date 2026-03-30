"""Synthetic Demo Generator — FastAPI port 8413"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8413

def build_html():
    # Pipeline stages
    pipeline_stages = [
        ("Scene\nSample","sample 10k variants"),
        ("IK\nSolve","filter 7k feasible"),
        ("Physics\nSim","run 5k episodes"),
        ("Render\n+Depth","4.2k success"),
        ("Label\n+QA","3.8k labeled"),
        ("Filter","3.1k final"),
    ]
    stage_colors = ["#38bdf8","#22c55e","#f59e0b","#C74634","#a78bfa","#38bdf8"]

    svg_pipe = '<svg width="420" height="100" style="background:#0f172a">'
    sw2 = 56
    for i, ((name, sub), col) in enumerate(zip(pipeline_stages, stage_colors)):
        x = 10 + i*(sw2+14)
        svg_pipe += f'<rect x="{x}" y="15" width="{sw2}" height="50" fill="{col}" rx="4" opacity="0.75"/>'
        lines = name.split("\n")
        svg_pipe += f'<text x="{x+sw2//2}" y="37" fill="white" font-size="8" text-anchor="middle">{lines[0]}</text>'
        svg_pipe += f'<text x="{x+sw2//2}" y="49" fill="white" font-size="8" text-anchor="middle">{lines[1] if len(lines)>1 else ""}</text>'
        svg_pipe += f'<text x="{x+sw2//2}" y="78" fill="{col}" font-size="7" text-anchor="middle">{sub}</text>'
        if i < len(pipeline_stages)-1:
            svg_pipe += f'<line x1="{x+sw2}" y1="40" x2="{x+sw2+14}" y2="40" stroke="#94a3b8" stroke-width="1.5"/>'
    svg_pipe += '</svg>'

    # Quality vs quantity frontier scatter
    # x = synthetic ratio (0-100%), y = SR
    pts_qv = []
    for i in range(30):
        ratio = random.uniform(0.05, 0.95)
        if ratio < 0.2:
            sr = 0.62 + random.uniform(-0.04,0.04)
        elif ratio < 0.5:
            sr = 0.74 + (ratio-0.2)*0.15 + random.uniform(-0.03,0.03)
        else:
            sr = 0.79 - (ratio-0.5)*0.1 + random.uniform(-0.03,0.03)
        pts_qv.append((ratio, max(0.5, min(0.85, sr))))

    svg_q2 = '<svg width="320" height="200" style="background:#0f172a">'
    svg_q2 += '<line x1="40" y1="10" x2="40" y2="170" stroke="#475569" stroke-width="1"/>'
    svg_q2 += '<line x1="40" y1="170" x2="300" y2="170" stroke="#475569" stroke-width="1"/>'
    for i in range(6):
        yv = 0.5+i*0.07; y = 170-(yv-0.5)/0.35*140
        svg_q2 += f'<text x="35" y="{y+4}" fill="#94a3b8" font-size="7" text-anchor="end">{yv:.2f}</text>'
    for i in range(6):
        xv = i*0.2; x = 40+xv*240
        svg_q2 += f'<text x="{x}" y="182" fill="#94a3b8" font-size="7" text-anchor="middle">{xv:.0%}</text>'
    for (ratio, sr) in pts_qv:
        cx = 40+ratio*240; cy = 170-(sr-0.5)/0.35*140
        col = "#22c55e" if sr > 0.76 else "#f59e0b" if sr > 0.68 else "#C74634"
        svg_q2 += f'<circle cx="{cx:.0f}" cy="{cy:.0f}" r="4" fill="{col}" opacity="0.8"/>'
    # Optimal point annotation
    opt_x = 40+0.40*240; opt_y = 170-(0.79-0.5)/0.35*140
    svg_q2 += f'<circle cx="{opt_x:.0f}" cy="{opt_y:.0f}" r="7" fill="none" stroke="white" stroke-width="2"/>'
    svg_q2 += f'<text x="{opt_x+10:.0f}" y="{opt_y-5:.0f}" fill="white" font-size="8">optimal (40%)</text>'
    svg_q2 += '<text x="170" y="196" fill="#94a3b8" font-size="9" text-anchor="middle">Synthetic Ratio in Training Set</text>'
    svg_q2 += '</svg>'

    return f"""<!DOCTYPE html><html><head><title>Synthetic Demo Generator — Port {PORT}</title>
<style>body{{background:#0f172a;color:#e2e8f0;font-family:monospace;margin:0;padding:20px}}
h1{{color:#C74634;font-size:18px}}h2{{color:#38bdf8;font-size:14px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:20px}}
.card{{background:#1e293b;padding:16px;border-radius:8px}}
.stat{{font-size:24px;color:#C74634;font-weight:bold}}
.label{{color:#94a3b8;font-size:12px}}</style></head>
<body><h1>Synthetic Demo Generator</h1>
<p style="color:#94a3b8">Port {PORT} | Genesis SDG pipeline + quality vs quantity frontier</p>
<div class="card" style="margin-bottom:16px"><h2>Generation Pipeline</h2>{svg_pipe}</div>
<div class="grid">
<div class="card"><h2>Synthetic Ratio vs SR Frontier</h2>{svg_q2}</div>
<div class="card">
<div class="stat">312</div><div class="label">Demos/hour (Genesis SDG throughput)</div>
<div class="stat" style="color:#38bdf8;margin-top:12px">$0.0017</div><div class="label">Cost per synthetic demo</div>
<div class="stat" style="color:#22c55e;margin-top:12px">40%</div><div class="label">Optimal synthetic ratio for SR=0.79</div>
<div style="margin-top:12px;color:#94a3b8;font-size:11px">Pipeline: 10k scenes → 3.1k final demos (69% filter rate)<br>IK failure: 30% infeasible grasps<br>Physics reject: 16% unstable contact<br>&lt;20% synthetic: insufficient diversity<br>&gt;60% synthetic: domain gap hurts real-world SR</div>
</div></div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Synthetic Demo Generator")
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
