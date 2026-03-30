"""Partner Milestone Tracker — FastAPI port 8410"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8410

def build_html():
    partners = ["PI_Robotics","Apptronik","1X_Tech","Machina_Labs","Wandelbots"]
    milestones = ["Onboard","Pilot","Scale","SLA","Contract","Renew"]
    # Status matrix: 0=not started, 1=in progress, 2=done, 3=blocked
    status_matrix = [
        [2,2,2,2,2,1],  # PI: all done, renewal in progress
        [2,2,1,1,1,0],  # Apptronik
        [2,2,1,0,0,0],  # 1X
        [2,1,0,3,0,0],  # Machina: blocked at SLA (DPA needed)
        [2,1,0,0,0,0],  # Wandelbots
    ]
    status_colors = {0:"#1e293b",1:"#f59e0b",2:"#22c55e",3:"#C74634"}
    status_labels = {0:"—",1:"▶",2:"✓",3:"⚠"}

    cw3, rh3 = 64, 28
    svg_m = f'<svg width="{len(milestones)*cw3+120}" height="{len(partners)*rh3+60}" style="background:#0f172a">'
    for mi, ms in enumerate(milestones):
        svg_m += f'<text x="{120+mi*cw3+32}" y="18" fill="#38bdf8" font-size="9" text-anchor="middle">{ms}</text>'
    for pi, partner in enumerate(partners):
        svg_m += f'<text x="115" y="{36+pi*rh3+16}" fill="#94a3b8" font-size="9" text-anchor="end">{partner}</text>'
        for mi, st in enumerate(status_matrix[pi]):
            col = status_colors[st]; lab = status_labels[st]
            svg_m += f'<rect x="{120+mi*cw3+2}" y="{30+pi*rh3+2}" width="{cw3-4}" height="{rh3-4}" fill="{col}" rx="3" opacity="0.85"/>'
            svg_m += f'<text x="{120+mi*cw3+32}" y="{30+pi*rh3+18}" fill="white" font-size="12" text-anchor="middle">{lab}</text>'
    svg_m += '</svg>'

    # Milestone completion rate bar
    completion = [sum(1 for s in row if s==2)/len(milestones) for row in status_matrix]
    svg_c2 = '<svg width="320" height="180" style="background:#0f172a">'
    for pi, (partner, comp) in enumerate(zip(partners, completion)):
        y = 20+pi*30; w = int(comp*260)
        col = "#22c55e" if comp >= 0.8 else "#f59e0b" if comp >= 0.5 else "#C74634"
        svg_c2 += f'<rect x="90" y="{y}" width="{w}" height="22" fill="{col}" opacity="0.85"/>'
        svg_c2 += f'<text x="85" y="{y+15}" fill="#94a3b8" font-size="9" text-anchor="end">{partner[:10]}</text>'
        svg_c2 += f'<text x="{92+w}" y="{y+15}" fill="white" font-size="9">{comp:.0%}</text>'
    svg_c2 += '<text x="200" y="170" fill="#94a3b8" font-size="9" text-anchor="middle">Milestone Completion Rate</text>'
    svg_c2 += '</svg>'

    return f"""<!DOCTYPE html><html><head><title>Partner Milestone Tracker — Port {PORT}</title>
<style>body{{background:#0f172a;color:#e2e8f0;font-family:monospace;margin:0;padding:20px}}
h1{{color:#C74634;font-size:18px}}h2{{color:#38bdf8;font-size:14px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:20px}}
.card{{background:#1e293b;padding:16px;border-radius:8px}}
.stat{{font-size:24px;color:#C74634;font-weight:bold}}
.label{{color:#94a3b8;font-size:12px}}</style></head>
<body><h1>Partner Milestone Tracker</h1>
<p style="color:#94a3b8">Port {PORT} | 5-partner × 6-milestone progress matrix</p>
<div class="card" style="margin-bottom:16px"><h2>Milestone Status Matrix (✓=Done ▶=In Progress ⚠=Blocked)</h2>{svg_m}</div>
<div class="grid">
<div class="card"><h2>Completion Rate</h2>{svg_c2}</div>
<div class="card">
<div class="stat">100%</div><div class="label">PI Robotics — fully through contract, renewal active</div>
<div class="stat" style="color:#C74634;margin-top:12px">⚠ Machina</div><div class="label">DPA BLOCKED → SLA/Contract/Renew all gated</div>
<div style="margin-top:12px;color:#94a3b8;font-size:11px">PI: expansion ready, renewal in negotiation<br>Apptronik: scaling up GPU-hrs, SLA drafting<br>1X: pilot extended, scaling pending<br>Machina: DPA sign-off needed by Apr 15<br>Wandelbots: pilot just started (API integration)</div>
</div></div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Partner Milestone Tracker")
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
