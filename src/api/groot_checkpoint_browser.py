"""GR00T Checkpoint Browser — FastAPI port 8426"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8426

def build_html():
    # Checkpoint data: step, SR, model_family, status
    checkpoints = []
    families = [("bc","#94a3b8",[(500,0.05),(1000,0.05),(2000,0.05),(3000,0.05),(5000,0.05)]),
                ("dagger_r5","#38bdf8",[(500,0.05),(1000,0.07),(2000,0.09),(3000,0.10),(5000,0.11)]),
                ("dagger_r9","#f59e0b",[(500,0.08),(1000,0.14),(2000,0.28),(3000,0.51),(5000,0.71)]),
                ("groot_v2","#C74634",[(500,0.12),(1000,0.32),(2000,0.58),(3000,0.71),(5000,0.78)]),
                ("groot_v3p","#22c55e",[(500,0.15),(1000,0.38),(2000,0.65),(3000,0.75),(4000,0.79)])]

    # Gallery scatter
    svg_gal = '<svg width="420" height="220" style="background:#0f172a">'
    svg_gal += '<line x1="50" y1="10" x2="50" y2="170" stroke="#475569" stroke-width="1"/>'
    svg_gal += '<line x1="50" y1="170" x2="400" y2="170" stroke="#475569" stroke-width="1"/>'
    for i in range(5):
        yv = i*0.2; y = 170-yv*140
        svg_gal += f'<text x="45" y="{y+4}" fill="#94a3b8" font-size="7" text-anchor="end">{yv:.1f}</text>'
    for i in range(6):
        xv = i*1000; x = 50+xv*340/5000
        svg_gal += f'<text x="{x}" y="183" fill="#94a3b8" font-size="7" text-anchor="middle">{xv}</text>'
    for fam, col, pts in families:
        fpts = [(50+step*340/5000, 170-sr*140) for step,sr in pts]
        for j in range(len(fpts)-1):
            x1,y1=fpts[j]; x2,y2=fpts[j+1]
            svg_gal += f'<line x1="{x1:.0f}" y1="{y1:.0f}" x2="{x2:.0f}" y2="{y2:.0f}" stroke="{col}" stroke-width="1.5" opacity="0.6"/>'
        for (step,sr), (cx,cy) in zip(pts, fpts):
            # Golden ckpt: groot_v2 step 5000
            is_golden = (fam=="groot_v2" and step==5000)
            svg_gal += f'<circle cx="{cx:.0f}" cy="{cy:.0f}" r="{"7" if is_golden else "4"}" fill="{col}" opacity="0.85"/>'
            if is_golden:
                svg_gal += f'<text x="{cx+10:.0f}" y="{cy+4:.0f}" fill="white" font-size="7">\u2605GOLDEN</text>'
        svg_gal += f'<text x="405" y="{fpts[-1][1]+4:.0f}" fill="{col}" font-size="7">{fam[:6]}</text>'
    svg_gal += '<text x="225" y="200" fill="#94a3b8" font-size="9" text-anchor="middle">Training Step</text>'
    svg_gal += '</svg>'

    # SR vs step training curves
    svg_curves = '<svg width="320" height="200" style="background:#0f172a">'
    svg_curves += '<line x1="40" y1="10" x2="40" y2="170" stroke="#475569" stroke-width="1"/>'
    svg_curves += '<line x1="40" y1="170" x2="300" y2="170" stroke="#475569" stroke-width="1"/>'
    for i in range(5):
        yv = i*0.2; y = 170-yv*140
        svg_curves += f'<text x="35" y="{y+4}" fill="#94a3b8" font-size="7" text-anchor="end">{yv:.1f}</text>'
    for fam, col, pts in families:
        fpts = [(40+step*250/5000, 170-sr*140) for step,sr in pts]
        for j in range(len(fpts)-1):
            x1,y1=fpts[j]; x2,y2=fpts[j+1]
            svg_curves += f'<line x1="{x1:.0f}" y1="{y1:.0f}" x2="{x2:.0f}" y2="{y2:.0f}" stroke="{col}" stroke-width="2"/>'
    svg_curves += '</svg>'

    return f"""<!DOCTYPE html><html><head><title>GR00T Checkpoint Browser \u2014 Port {PORT}</title>
<style>body{{background:#0f172a;color:#e2e8f0;font-family:monospace;margin:0;padding:20px}}
h1{{color:#C74634;font-size:18px}}h2{{color:#38bdf8;font-size:14px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:20px}}
.card{{background:#1e293b;padding:16px;border-radius:8px}}
.stat{{font-size:24px;color:#C74634;font-weight:bold}}
.label{{color:#94a3b8;font-size:12px}}</style></head>
<body><h1>GR00T Checkpoint Browser</h1>
<p style="color:#94a3b8">Port {PORT} | 45 checkpoints across 5 model families</p>
<div class="card" style="margin-bottom:16px"><h2>Checkpoint Gallery (step \u00d7 SR, \u2605=GOLDEN)</h2>{svg_gal}</div>
<div class="grid">
<div class="card"><h2>Training Curves</h2>{svg_curves}</div>
<div class="card">
<div class="stat">groot_v2 step 5000</div><div class="label">GOLDEN checkpoint: SR=0.78, PRODUCTION</div>
<div class="stat" style="color:#22c55e;margin-top:12px">45</div><div class="label">Total checkpoints tracked across all families</div>
<div style="margin-top:12px;color:#94a3b8;font-size:11px">dagger_r9: best ROI (71% SR, 5000 steps)<br>groot_v3p: 800/3000 steps, projected 0.83<br>BC family: plateaus at 5% (100 demos insufficient)<br>Metadata: step/SR/latency/VRAM/commit_hash</div>
</div></div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="GR00T Checkpoint Browser")
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
