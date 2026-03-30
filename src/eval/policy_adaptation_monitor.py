"""Policy Adaptation Monitor — FastAPI port 8416"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8416

def build_html():
    tasks = ["pick_place","stack","pour","insert","fold"]
    target_sr = [0.78, 0.72, 0.61, 0.54, 0.47]
    demos_to_target = [3, 6, 11, 15, 18]
    task_colors = ["#22c55e","#38bdf8","#f59e0b","#a78bfa","#C74634"]

    # Adaptation curve SVG (SR vs demos for each task)
    svg_a = '<svg width="380" height="200" style="background:#0f172a">'
    svg_a += '<line x1="50" y1="10" x2="50" y2="170" stroke="#475569" stroke-width="1"/>'
    svg_a += '<line x1="50" y1="170" x2="360" y2="170" stroke="#475569" stroke-width="1"/>'
    for i in range(5):
        yv = i*0.2; y = 170-yv*140
        svg_a += f'<text x="45" y="{y+4}" fill="#94a3b8" font-size="7" text-anchor="end">{yv:.1f}</text>'
    for i in range(6):
        x = 50+i*(310//5)
        svg_a += f'<text x="{x}" y="183" fill="#94a3b8" font-size="7" text-anchor="middle">{i*4}</text>'
    for ti, (task, tgt, dtgt, col) in enumerate(zip(tasks, target_sr, demos_to_target, task_colors)):
        pts = []
        for d in range(21):
            sr = tgt * (1 - math.exp(-d * 2.5/dtgt)) + random.uniform(-0.02,0.02)
            x = 50 + d*(310//20); y = 170 - max(0,min(1,sr))*140
            pts.append((x,y))
        for j in range(len(pts)-1):
            x1,y1=pts[j]; x2,y2=pts[j+1]
            svg_a += f'<line x1="{x1}" y1="{y1:.1f}" x2="{x2}" y2="{y2:.1f}" stroke="{col}" stroke-width="1.5"/>'
        svg_a += f'<text x="365" y="{pts[-1][1]+4:.0f}" fill="{col}" font-size="7">{task[:5]}</text>'
    svg_a += '<text x="200" y="197" fill="#94a3b8" font-size="9" text-anchor="middle">Number of Demonstration Examples</text>'
    svg_a += '</svg>'

    # Adaptation speed bar
    svg_spd = '<svg width="320" height="180" style="background:#0f172a">'
    for ti, (task, dtgt, col) in enumerate(zip(tasks, demos_to_target, task_colors)):
        y = 20+ti*30; w = int(dtgt/20*260)
        svg_spd += f'<rect x="85" y="{y}" width="{w}" height="22" fill="{col}" opacity="0.8" rx="3"/>'
        svg_spd += f'<text x="80" y="{y+15}" fill="#94a3b8" font-size="9" text-anchor="end">{task[:10]}</text>'
        svg_spd += f'<text x="{87+w}" y="{y+15}" fill="white" font-size="9">{dtgt} demos</text>'
    svg_spd += '<text x="195" y="175" fill="#94a3b8" font-size="9" text-anchor="middle">Demos to Reach Target SR</text>'
    svg_spd += '</svg>'

    return f"""<!DOCTYPE html><html><head><title>Policy Adaptation Monitor — Port {PORT}</title>
<style>body{{background:#0f172a;color:#e2e8f0;font-family:monospace;margin:0;padding:20px}}
h1{{color:#C74634;font-size:18px}}h2{{color:#38bdf8;font-size:14px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:20px}}
.card{{background:#1e293b;padding:16px;border-radius:8px}}
.stat{{font-size:24px;color:#C74634;font-weight:bold}}
.label{{color:#94a3b8;font-size:12px}}</style></head>
<body><h1>Policy Adaptation Monitor</h1>
<p style="color:#94a3b8">Port {PORT} | Few-shot adaptation speed per task + meta-learning readiness</p>
<div class="grid">
<div class="card"><h2>Adaptation Curves (SR vs Demos)</h2>{svg_a}</div>
<div class="card"><h2>Demos to Target SR</h2>{svg_spd}
<div style="margin-top:8px">
<div class="stat">3×</div><div class="label">GR00T_v2 faster adaptation than BC</div>
<div class="stat" style="color:#22c55e;margin-top:8px">3 demos</div><div class="label">pick_place fastest adaptation</div>
<div style="margin-top:8px;color:#94a3b8;font-size:11px">fold requires 18 demos (most complex)<br>Meta-learning readiness: 0.76/1.0<br>Design partners can self-adapt with &lt;20 demos<br>Target: 5-demo adaptation for all tasks by v4</div>
</div></div></div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Policy Adaptation Monitor")
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
