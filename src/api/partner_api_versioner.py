"""Partner API Versioner — FastAPI port 8441"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8441

def build_html():
    # API version lifecycle Gantt
    versions = [
        ("v1.0","DEPRECATED","2026-01","2026-06","#475569",18),
        ("v2.0","CURRENT","2026-03","2027-09","#22c55e",18),
        ("v3.0_beta","BETA","2026-05","2027-11","#38bdf8",18),
    ]
    # Timeline: Apr 2026 to Dec 2027 = 21 months
    months = ["A26","M","J","J","A","S","O","N","D","J27","F","M","A","M","J","J","A","S","O","N","D"]
    month_to_idx = {m:i for i,m in enumerate(months)}

    svg_gantt = '<svg width="420" height="140" style="background:#0f172a">'
    for i in range(len(months)):
        x = 50+i*17
        if i % 3 == 0:
            svg_gantt += f'<text x="{x}" y="12" fill="#94a3b8" font-size="7" text-anchor="middle">{months[i]}</text>'
        svg_gantt += f'<line x1="{x}" y1="15" x2="{x}" y2="120" stroke="#1e293b" stroke-width="1"/>'
    for vi, (ver, status, start, end, col, _) in enumerate(versions):
        # Map months to index (simplified)
        start_idx = {"2026-01":0,"2026-03":2,"2026-05":4}.get(start,0)
        end_idx = {"2026-06":2,"2027-09":17,"2027-11":19}.get(end,20)
        x1 = 50+start_idx*17; x2 = 50+end_idx*17
        y = 25+vi*30
        svg_gantt += f'<rect x="{x1}" y="{y}" width="{x2-x1}" height="22" fill="{col}" rx="4" opacity="0.8"/>'
        svg_gantt += f'<text x="{x1+4}" y="{y+15}" fill="white" font-size="9">{ver} ({status})</text>'
    svg_gantt += '</svg>'

    # Partner version adoption
    partners_v = ["PI_Robotics","Apptronik","1X_Tech","Machina_Labs","Wandelbots"]
    v1_pct = [0, 40, 60, 80, 70]
    v2_pct = [100, 60, 40, 0, 30]
    v3b_pct= [0, 0, 0, 0, 0]

    svg_adopt = '<svg width="360" height="200" style="background:#0f172a">'
    bw11 = 18; grp_w3 = bw11*3+6
    for pi, partner in enumerate(partners_v):
        for vi, (pct, col) in enumerate(zip([v1_pct[pi],v2_pct[pi],v3b_pct[pi]],("#475569","#22c55e","#38bdf8"))):
            x = 30+pi*grp_w3+vi*bw11; h = pct*120/100; y = 170-h
            svg_adopt += f'<rect x="{x}" y="{y:.0f}" width="{bw11-2}" height="{h:.0f}" fill="{col}" opacity="0.85"/>'
        tx = 30+pi*grp_w3+bw11*3//2
        name = partner[:5]
        svg_adopt += f'<text x="{tx}" y="183" fill="#94a3b8" font-size="7" text-anchor="middle">{name}</text>'
    # Legend
    for li, (label, col) in enumerate(zip(["v1(dep)","v2(cur)","v3(beta)"],["#475569","#22c55e","#38bdf8"])):
        svg_adopt += f'<rect x="{50+li*80}" y="195" width="10" height="8" fill="{col}"/>'
        svg_adopt += f'<text x="{63+li*80}" y="203" fill="#94a3b8" font-size="7">{label}</text>'
    svg_adopt += '</svg>'

    return f"""<!DOCTYPE html><html><head><title>Partner API Versioner — Port {PORT}</title>
<style>body{{background:#0f172a;color:#e2e8f0;font-family:monospace;margin:0;padding:20px}}
h1{{color:#C74634;font-size:18px}}h2{{color:#38bdf8;font-size:14px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:20px}}
.card{{background:#1e293b;padding:16px;border-radius:8px}}
.stat{{font-size:24px;color:#C74634;font-weight:bold}}
.label{{color:#94a3b8;font-size:12px}}</style></head>
<body><h1>Partner API Versioner</h1>
<p style="color:#94a3b8">Port {PORT} | API version lifecycle + partner adoption tracking</p>
<div class="grid">
<div class="card"><h2>Version Lifecycle Gantt</h2>{svg_gantt}
<div style="margin-top:8px;color:#94a3b8;font-size:11px">v1.0: deprecated Jun 2026 (18mo support)<br>v2.0: current, supported through Sep 2027<br>v3.0 beta: bimanual endpoint + streaming inference<br>Breaking changes: /infer signature + action_format</div>
</div>
<div class="card"><h2>Partner Version Adoption</h2>{svg_adopt}
<div style="margin-top:8px">
<div class="stat">PI: 100%</div><div class="label">PI Robotics fully migrated to v2.0</div>
<div style="margin-top:8px;color:#94a3b8;font-size:11px">1X/Machina still on v1: migration guide sent<br>v3 beta: no partners yet (bimanual requires N2.0)<br>Auto-migration script: v1\u2192v2 in 2h downtime<br>Deprecation reminder: emails sent 90/60/30 days out</div>
</div></div></div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Partner API Versioner")
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
