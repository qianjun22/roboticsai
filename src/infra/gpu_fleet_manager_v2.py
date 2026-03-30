"""GPU Fleet Manager v2 — FastAPI port 8867"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8867

def build_html():
    nodes = [
        ("Ashburn GPU4","A100_80GB",91,"DAgger_run10","#22c55e"),
        ("Ashburn GPU1","A100_80GB",87,"groot_finetune_v3","#22c55e"),
        ("Phoenix GPU1","A100_40GB",62,"eval × 3","#f59e0b"),
        ("Frankfurt GPU1","A100_40GB",71,"groot_v2 staging","#38bdf8"),
        ("Ashburn GPU5 (Jun)","A100_80GB",0,"PROVISIONING","#94a3b8"),
        ("Ashburn GPU6 (Jun)","A100_80GB",0,"PROVISIONING","#94a3b8"),
    ]
    cards = ""
    for name,gpu,util,job,col in nodes:
        w = int(util*1.8)
        cards += f"""<div style="background:#0f172a;padding:12px;border-radius:6px;border:1px solid #334155">
<div style="font-size:12px;font-weight:bold;color:#e2e8f0">{name}</div>
<div style="font-size:11px;color:#94a3b8">{gpu} | {job}</div>
<div style="margin-top:6px;background:#1e293b;border-radius:3px;height:8px">
<div style="background:{col};width:{w}px;height:8px;border-radius:3px"></div></div>
<div style="font-size:11px;color:{col};margin-top:2px">{util}% util</div></div>"""
    months = ["Apr","May","Jun","Jul","Aug","Sep"]
    eff_v1 = [0.78,0.79,0.80,0.81,0.82,0.83]
    eff_v2 = [0.89,0.90,0.90,0.91,0.91,0.92]
    pts_v1 = " ".join(f"{60+i*80},{220-int(e*160)}" for i,e in enumerate(eff_v1))
    pts_v2 = " ".join(f"{60+i*80},{220-int(e*160)}" for i,e in enumerate(eff_v2))
    return f"""<!DOCTYPE html><html><head><title>GPU Fleet Manager v2</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui}}
h1{{color:#C74634;padding:20px 20px 0}}h2{{color:#38bdf8;margin:0 0 10px}}
.card{{background:#1e293b;padding:20px;margin:10px 20px;border-radius:8px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;padding:0 20px}}
.ngrid{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px}}</style></head>
<body><h1>GPU Fleet Manager v2</h1>
<p style="padding:0 20px;color:#94a3b8">port {PORT} — 4 active nodes + 2 provisioning Jun | fleet efficiency 89% (v1: 78%)</p>
<div class="card"><h2>Fleet Status</h2><div class="ngrid">{cards}</div></div>
<div class="grid">
<div class="card"><h2>Fleet Efficiency: v1 vs v2</h2>
<svg width="520" height="240">
<polyline points="{pts_v1}" fill="none" stroke="#38bdf8" stroke-width="2" stroke-dasharray="4,3"/>
<polyline points="{pts_v2}" fill="none" stroke="#22c55e" stroke-width="2.5"/>
{" ".join(f'<text x="{50+i*80}" y="235" fill="#94a3b8" font-size="10">{m}</text>' for i,m in enumerate(months))}
<text x="380" y="60" fill="#38bdf8" font-size="11">v1 (78%)</text>
<text x="380" y="75" fill="#22c55e" font-size="11">v2 (89%)</text></svg></div>
<div class="card"><h2>v2 Improvements</h2>
<p style="color:#94a3b8">Predictive autoscaling: <span style="color:#22c55e">31% fewer</span> unnecessary scale events</p>
<p style="color:#94a3b8">Workload bin-packing: <span style="color:#38bdf8">GPU idle time -18%</span></p>
<p style="color:#94a3b8">AI World Sep: <span style="color:#f59e0b">8 nodes pre-provisioned</span> 48h before event</p></div>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="GPU Fleet Manager v2")
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
