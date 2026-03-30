"""Skill Composition Evaluator — FastAPI port 8492"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8492

def build_html():
    skills = [
        ("reach", 0.94, "mastered"),
        ("grasp", 0.82, "mastered"),
        ("lift", 0.78, "strong"),
        ("place", 0.75, "strong"),
        ("pour", 0.61, "learning"),
        ("insert", 0.53, "learning"),
        ("open", 0.71, "strong"),
        ("wipe", 0.58, "learning"),
        ("stack", 0.69, "learning"),
        ("fold", 0.31, "early"),
        ("handoff", 0.42, "early"),
        ("bimanual_place", 0.28, "early"),
    ]
    
    skill_bars = ""
    for name, sr, status in skills:
        col = {"mastered": "#22c55e", "strong": "#38bdf8", "learning": "#f59e0b", "early": "#ef4444"}[status]
        skill_bars += f'''<div style="display:flex;align-items:center;margin-bottom:5px">
<span style="width:120px;color:#e2e8f0;font-size:12px">{name}</span>
<div style="background:#334155;border-radius:2px;height:8px;width:200px">
<div style="background:{col};width:{sr*100:.0f}%;height:8px;border-radius:2px"></div></div>
<span style="margin-left:8px;color:{col};font-size:11px">SR={sr:.2f}</span>
</div>'''
    
    # composition chain degradation
    chains = [1, 2, 3, 4]
    sr_groot = [0.94, 0.78, 0.61, 0.44]
    sr_bc = [0.82, 0.51, 0.31, 0.18]
    
    pts_groot = []
    pts_bc = []
    for i, (c, sg, sb) in enumerate(zip(chains, sr_groot, sr_bc)):
        x = (c-1) * 160 + 20
        yg = 100 - sg * 90
        yb = 100 - sb * 90
        pts_groot.append(f"{x:.0f},{yg:.1f}")
        pts_bc.append(f"{x:.0f},{yb:.1f}")
        groot_col = "#22c55e" if sg > 0.7 else ("#f59e0b" if sg > 0.5 else "#ef4444")
        bc_col = "#64748b"
        chain_svg_extra = f'<circle cx="{x}" cy="{yg:.1f}" r="5" fill="{groot_col}"/>'
        chain_svg_extra += f'<circle cx="{x}" cy="{yb:.1f}" r="5" fill="{bc_col}"/>'
    
    chain_svg = f'<polyline points="{" ".join(pts_groot)}" fill="none" stroke="#22c55e" stroke-width="2"/>'
    chain_svg += f'<polyline points="{" ".join(pts_bc)}" fill="none" stroke="#64748b" stroke-width="2" stroke-dasharray="5,3"/>'
    for i, (c, sg, sb) in enumerate(zip(chains, sr_groot, sr_bc)):
        x = (c-1) * 160 + 20
        yg = 100 - sg * 90
        yb = 100 - sb * 90
        chain_svg += f'<circle cx="{x}" cy="{yg:.1f}" r="5" fill="#22c55e"/>'
        chain_svg += f'<circle cx="{x}" cy="{yb:.1f}" r="5" fill="#64748b"/>'
        chain_svg += f'<text x="{x}" y="115" text-anchor="middle" fill="#64748b" font-size="10">{c}-skill</text>'
    
    return f"""<!DOCTYPE html><html><head><title>Skill Composition Evaluator</title>
<style>body{{margin:0;font-family:monospace;background:#0f172a;color:#e2e8f0}}
.hdr{{background:#C74634;padding:16px 24px;display:flex;justify-content:space-between;align-items:center}}
.hdr h1{{margin:0;font-size:20px;color:#fff}}.hdr span{{color:#fca5a5;font-size:13px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;padding:20px}}
.card{{background:#1e293b;border-radius:8px;padding:16px}}
.card h3{{margin:0 0 12px;color:#38bdf8;font-size:14px;text-transform:uppercase;letter-spacing:1px}}
.stat{{font-size:36px;font-weight:bold;color:#f1f5f9}}.sub{{color:#64748b;font-size:12px;margin-top:4px}}</style></head>
<body>
<div class="hdr"><h1>Skill Composition Evaluator</h1><span>port {PORT} · 12 primitive skills</span></div>
<div class="grid">
<div class="card"><h3>Mastered Skills</h3><div class="stat">2</div><div class="sub">reach 0.94 · grasp 0.82</div></div>
<div class="card"><h3>4-Skill Chain SR</h3><div class="stat">44%</div><div class="sub">0.94^4 degradation · GR00T_v2</div></div>
<div class="card"><h3>Skill SR Breakdown</h3>{skill_bars}</div>
<div class="card"><h3>Chain SR: GR00T_v2 vs BC</h3>
<div style="font-size:11px;color:#64748b;margin-bottom:8px"><span style="color:#22c55e">—</span> GR00T_v2 <span style="color:#64748b;margin-left:8px">- -</span> BC</div>
<svg width="100%" viewBox="0 0 500 125">{chain_svg}</svg></div>
</div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Skill Composition Evaluator")
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
