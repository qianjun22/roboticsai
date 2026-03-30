"""Compliance Audit Dashboard — FastAPI port 8434"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8434

def build_html():
    frameworks = ["GDPR","SOC2_Type2","ISO_27001","HIPAA","CCPA"]
    scores = [0.94, 0.71, 0.83, 0.68, 0.89]
    fw_colors = ["#22c55e","#f59e0b","#22c55e","#f59e0b","#22c55e"]

    # Radar
    n = len(frameworks); angle_step = 2*math.pi/n
    cx_r, cy_r, r_r = 130, 130, 90
    svg_radar2 = '<svg width="280" height="270" style="background:#0f172a">'
    for ri in range(1,6):
        pts2 = [(cx_r+r_r*ri/5*math.cos(i*angle_step-math.pi/2), cy_r+r_r*ri/5*math.sin(i*angle_step-math.pi/2)) for i in range(n)]
        path2 = "M "+' L '.join(f'{x:.0f},{y:.0f}' for x,y in pts2)+" Z"
        svg_radar2 += f'<path d="{path2}" fill="none" stroke="#1e293b" stroke-width="1"/>'
    for i, fw in enumerate(frameworks):
        angle = i*angle_step-math.pi/2
        lx = cx_r+(r_r+16)*math.cos(angle); ly = cy_r+(r_r+16)*math.sin(angle)
        svg_radar2 += f'<text x="{lx:.0f}" y="{ly:.0f}" fill="#94a3b8" font-size="8" text-anchor="middle">{fw}</text>'
    score_pts = [(cx_r+r_r*scores[i]*math.cos(i*angle_step-math.pi/2), cy_r+r_r*scores[i]*math.sin(i*angle_step-math.pi/2)) for i in range(n)]
    path_s = "M "+' L '.join(f'{x:.0f},{y:.0f}' for x,y in score_pts)+" Z"
    svg_radar2 += f'<path d="{path_s}" fill="#38bdf8" fill-opacity="0.2" stroke="#38bdf8" stroke-width="2"/>'
    for i, (s, col) in enumerate(zip(scores, fw_colors)):
        angle = i*angle_step-math.pi/2
        px = cx_r+r_r*s*math.cos(angle); py = cy_r+r_r*s*math.sin(angle)
        svg_radar2 += f'<circle cx="{px:.0f}" cy="{py:.0f}" r="5" fill="{col}"/>'
    svg_radar2 += f'<text x="{cx_r}" y="{cy_r+5}" fill="white" font-size="10" text-anchor="middle">{sum(scores)/len(scores):.0%}</text>'
    svg_radar2 += f'<text x="{cx_r}" y="{cy_r+18}" fill="#94a3b8" font-size="7" text-anchor="middle">avg compliance</text>'
    # Scores table below radar
    for i, (fw, s, col) in enumerate(zip(frameworks, scores, fw_colors)):
        y = 240+i*0; pass
    svg_radar2 += '</svg>'

    # Finding timeline
    svg_timeline = '<svg width="380" height="200" style="background:#0f172a">'
    svg_timeline += '<line x1="40" y1="10" x2="40" y2="170" stroke="#475569" stroke-width="1"/>'
    svg_timeline += '<line x1="40" y1="170" x2="370" y2="170" stroke="#475569" stroke-width="1"/>'
    days3 = list(range(90))
    open_counts = [max(2, 18-d//8+random.randint(-1,1)) for d in days3]
    closed_counts = [min(d//5+random.randint(0,2), 18) for d in days3]
    for j in range(len(days3)-1):
        x1 = 40+days3[j]*320/89; x2 = 40+days3[j+1]*320/89
        y1 = 170-open_counts[j]*140/20; y2 = 170-open_counts[j+1]*140/20
        svg_timeline += f'<line x1="{x1:.0f}" y1="{y1:.0f}" x2="{x2:.0f}" y2="{y2:.0f}" stroke="#C74634" stroke-width="1.5"/>'
        y1c = 170-closed_counts[j]*140/20; y2c = 170-closed_counts[j+1]*140/20
        svg_timeline += f'<line x1="{x1:.0f}" y1="{y1c:.0f}" x2="{x2:.0f}" y2="{y2c:.0f}" stroke="#22c55e" stroke-width="1.5"/>'
    svg_timeline += '<text x="205" y="190" fill="#94a3b8" font-size="9" text-anchor="middle">90-Day Finding Timeline (red=open / green=closed)</text>'
    svg_timeline += '</svg>'

    return f"""<!DOCTYPE html><html><head><title>Compliance Audit Dashboard — Port {PORT}</title>
<style>body{{background:#0f172a;color:#e2e8f0;font-family:monospace;margin:0;padding:20px}}
h1{{color:#C74634;font-size:18px}}h2{{color:#38bdf8;font-size:14px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:20px}}
.card{{background:#1e293b;padding:16px;border-radius:8px}}
.stat{{font-size:24px;color:#C74634;font-weight:bold}}
.label{{color:#94a3b8;font-size:12px}}</style></head>
<body><h1>Compliance Audit Dashboard</h1>
<p style="color:#94a3b8">Port {PORT} | GDPR/SOC2/ISO27001/HIPAA/CCPA compliance radar + findings timeline</p>
<div class="grid">
<div class="card"><h2>Compliance Radar</h2>{svg_radar2}
<div style="margin-top:8px;font-size:11px;color:#94a3b8">GDPR 94% ✓ | SOC2 71% ▶ | ISO 83% ✓<br>HIPAA 68% ▶ (not required but monitored)<br>CCPA 89% ✓ | Avg: 81%</div></div>
<div class="card"><h2>Finding Lifecycle</h2>{svg_timeline}
<div style="margin-top:8px">
<div class="stat">77</div><div class="label">Total findings tracked (all-time)</div>
<div class="stat" style="color:#f59e0b;margin-top:8px">SOC2 Type II</div><div class="label">In progress — audit period closes May 31</div>
<div style="margin-top:8px;color:#94a3b8;font-size:11px">2 CRITICAL findings: both CLOSED<br>7 HIGH: all closed within 2.3 days avg<br>Data residency: all robotics data stays in US region<br>Customer data isolation: tenant-level VLAN + encryption</div>
</div></div></div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Compliance Audit Dashboard")
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
