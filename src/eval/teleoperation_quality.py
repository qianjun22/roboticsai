"""Teleoperation Quality — FastAPI port 8427"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8427

def build_html():
    operators = ["op_alice","op_bob","op_carol","op_dave","op_eve"]
    dims = ["smoothness","precision","speed","success","consistency"]
    scores = [
        [4.8, 4.7, 4.2, 4.9, 4.6],  # alice: top
        [4.1, 4.3, 4.6, 4.2, 4.0],  # bob: fast
        [3.8, 4.5, 3.6, 4.1, 3.9],  # carol
        [3.2, 3.8, 3.9, 3.5, 3.4],  # dave
        [4.4, 4.2, 3.8, 4.3, 4.5],  # eve
    ]
    op_colors = ["#C74634","#38bdf8","#22c55e","#f59e0b","#a78bfa"]

    # Radar chart for each operator
    n = len(dims); angle_step = 2*math.pi/n
    cx_r, cy_r, r_radar = 160, 120, 80

    svg_radar = '<svg width="320" height="240" style="background:#0f172a">'
    # Grid circles
    for ri in range(1, 6):
        pts = [(cx_r+r_radar*ri/5*math.cos(i*angle_step-math.pi/2),
                cy_r+r_radar*ri/5*math.sin(i*angle_step-math.pi/2)) for i in range(n)]
        path = "M "+' L '.join(f'{x:.0f},{y:.0f}' for x,y in pts) + ' Z'
        svg_radar += f'<path d="{path}" fill="none" stroke="#1e293b" stroke-width="1"/>'
    # Axis labels
    for i, dim in enumerate(dims):
        angle = i*angle_step-math.pi/2
        lx = cx_r+(r_radar+15)*math.cos(angle); ly = cy_r+(r_radar+15)*math.sin(angle)
        svg_radar += f'<text x="{lx:.0f}" y="{ly:.0f}" fill="#94a3b8" font-size="8" text-anchor="middle">{dim}</text>'
    # Plot each operator
    for oi, (op, scr, col) in enumerate(zip(operators, scores, op_colors)):
        pts = [(cx_r+r_radar*(s/5)*math.cos(i*angle_step-math.pi/2),
                cy_r+r_radar*(s/5)*math.sin(i*angle_step-math.pi/2)) for i, s in enumerate(scr)]
        path = "M "+' L '.join(f'{x:.0f},{y:.0f}' for x,y in pts) + ' Z'
        svg_radar += f'<path d="{path}" fill="{col}" fill-opacity="0.12" stroke="{col}" stroke-width="1.5"/>'
    # Legend
    for oi, (op, col) in enumerate(zip(operators, op_colors)):
        avg = sum(scores[oi])/len(scores[oi])
        svg_radar += f'<rect x="{10+oi*60}" y="210" width="8" height="8" fill="{col}"/>'
        svg_radar += f'<text x="{21+oi*60}" y="218" fill="{col}" font-size="7">{op[3:]} {avg:.1f}</text>'
    svg_radar += '</svg>'

    # Demo quality vs operator skill scatter
    demo_quality = []
    for oi, (op, scr) in enumerate(zip(operators, scores)):
        avg_skill = sum(scr)/len(scr)
        for _ in range(20):
            dq = avg_skill*0.92 + random.gauss(0,0.15)
            demo_quality.append((avg_skill+random.gauss(0,0.05), max(1,min(5,dq)), op_colors[oi]))

    svg_scatter = '<svg width="320" height="200" style="background:#0f172a">'
    svg_scatter += '<line x1="40" y1="10" x2="40" y2="170" stroke="#475569" stroke-width="1"/>'
    svg_scatter += '<line x1="40" y1="170" x2="300" y2="170" stroke="#475569" stroke-width="1"/>'
    for i in range(6):
        yv = 1+i*0.8; y = 170-(yv-1)/4*140
        svg_scatter += f'<text x="35" y="{y+4}" fill="#94a3b8" font-size="7" text-anchor="end">{yv:.1f}</text>'
    for i in range(6):
        xv = 2+i*0.6; x = 40+(xv-2)/3*240
        svg_scatter += f'<text x="{x}" y="183" fill="#94a3b8" font-size="7" text-anchor="middle">{xv:.1f}</text>'
    for skill, quality, col in demo_quality:
        cx2 = 40+(skill-2)/3*240; cy2 = 170-(quality-1)/4*140
        svg_scatter += f'<circle cx="{cx2:.0f}" cy="{cy2:.0f}" r="3" fill="{col}" opacity="0.6"/>'
    svg_scatter += '<text x="170" y="197" fill="#94a3b8" font-size="9" text-anchor="middle">Operator Skill Score</text>'
    svg_scatter += '</svg>'

    return f"""<!DOCTYPE html><html><head><title>Teleoperation Quality \u2014 Port {PORT}</title>
<style>body{{background:#0f172a;color:#e2e8f0;font-family:monospace;margin:0;padding:20px}}
h1{{color:#C74634;font-size:18px}}h2{{color:#38bdf8;font-size:14px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:20px}}
.card{{background:#1e293b;padding:16px;border-radius:8px}}
.stat{{font-size:24px;color:#C74634;font-weight:bold}}
.label{{color:#94a3b8;font-size:12px}}</style></head>
<body><h1>Teleoperation Quality</h1>
<p style="color:#94a3b8">Port {PORT} | Operator performance radar + demo quality correlation</p>
<div class="grid">
<div class="card"><h2>Operator Performance Radar</h2>{svg_radar}</div>
<div class="card"><h2>Demo Quality vs Skill</h2>{svg_scatter}
<div style="margin-top:8px">
<div class="stat">op_alice</div><div class="label">Top operator: 4.7/5 avg quality score</div>
<div class="stat" style="color:#22c55e;margin-top:8px">23%</div><div class="label">SR improvement from quality-weighted demo selection</div>
<div style="margin-top:8px;color:#94a3b8;font-size:11px">Quality threshold: 3.5/5 minimum for training<br>Top 30% demos = 70% of SR improvement<br>Low-quality filter: 18% demos rejected<br>Design partner self-demo: target &gt;3.5 after 2h training</div>
</div></div></div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Teleoperation Quality")
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
