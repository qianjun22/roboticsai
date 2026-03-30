"""Revenue Dashboard v3 — FastAPI port 8869"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8869

def build_html():
    months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep"]
    mrr = [0, 847, 2927, 3200, 3820, 5147, 7200, 10400, 19000]
    pts = " ".join(f"{60+i*70},{280-int(m/20000*240)}" for i,m in enumerate(mrr))
    fill_pts = pts + f" {60+8*70},280 60,280"
    milestones = [(3,"AI World\nPrep"),(8,"AI World\nLaunch")]
    metrics = [
        ("ARR (current)","$35,000","#22c55e"),
        ("Q2 Target","$84,000","#38bdf8"),
        ("AI World Sep","$180,000","#f59e0b"),
        ("NRR","127%","#22c55e"),
        ("Gross Margin","71%","#22c55e"),
        ("Rule of 40","68","#38bdf8"),
    ]
    metric_cards = "".join(f'<div style="background:#0f172a;padding:12px;border-radius:6px;text-align:center"><div style="color:#94a3b8;font-size:11px">{k}</div><div style="color:{c};font-size:20px;font-weight:bold;margin-top:4px">{v}</div></div>' for k,v,c in metrics)
    return f"""<!DOCTYPE html><html><head><title>Revenue Dashboard v3</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui}}
h1{{color:#C74634;padding:20px 20px 0}}h2{{color:#38bdf8;margin:0 0 10px}}
.card{{background:#1e293b;padding:20px;margin:10px 20px;border-radius:8px}}
.mgrid{{display:grid;grid-template-columns:repeat(6,1fr);gap:8px}}</style></head>
<body><h1>Revenue Dashboard v3</h1>
<p style="padding:0 20px;color:#94a3b8">port {PORT} — monthly/quarterly/annual | ARR $35k → $180k Sep | board-ready metrics</p>
<div class="card"><h2>MRR Growth 2026</h2>
<svg width="680" height="300">
<polygon points="{fill_pts}" fill="#22c55e" opacity="0.12"/>
<polyline points="{pts}" fill="none" stroke="#22c55e" stroke-width="2.5"/>
{"".join(f'<circle cx="{60+i*70}" cy="{280-int(m/20000*240)}" r="4" fill="#22c55e"/>' for i,m in enumerate(mrr))}
{"".join(f'<text x="{48+i*70}" y="298" fill="#94a3b8" font-size="10">{mo}</text>' for i,mo in enumerate(months))}
<line x1="{60+8*70}" y1="50" x2="{60+8*70}" y2="280" stroke="#f59e0b" stroke-width="1" stroke-dasharray="4,3"/>
<text x="{60+8*70-30}" y="45" fill="#f59e0b" font-size="10">AI World</text></svg></div>
<div class="card"><h2>Key Metrics</h2><div class="mgrid">{metric_cards}</div></div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Revenue Dashboard v3")
    @app.get("/", response_class=HTMLResponse)
    def index(): return build_html()
    @app.get("/health")
    def health(): return {"status":"ok","port":PORT}

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.send_header("Content-Type","text/html"); self.end_headers()
        self.wfile.write(build_html().encode())
    def log_message(self,*a): pass

if __name__=="__main__":
    if USE_FASTAPI: uvicorn.run(app,host="0.0.0.0",port=PORT)
    else: HTTPServer(("0.0.0.0",PORT),Handler).serve_forever()
