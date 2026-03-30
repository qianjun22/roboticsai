"""OCI Cost Optimizer v3 — FastAPI port 8863"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8863

def build_html():
    strategies = [
        ("PAYG baseline","#ef4444",147,0),
        ("+ spot instances","#f59e0b",51,65),
        ("+ reserved 2xA100","#38bdf8",40,73),
        ("+ cache optimization","#22c55e",37,75),
        ("+ batch scheduling","#a78bfa",34,77),
    ]
    bars = ""
    for name,col,cost,save in strategies:
        w = int(cost/147*400)
        bars += f"""<div style="margin:8px 0">
<div style="font-size:12px;color:#94a3b8;margin-bottom:3px">{name}</div>
<div style="display:flex;align-items:center;gap:8px">
<div style="background:{col};width:{w}px;height:22px;border-radius:3px"></div>
<span style="color:{col};font-size:13px">${cost}/day</span>
{"<span style='color:#22c55e;font-size:11px'>-"+str(save)+"%</span>" if save else ""}
</div></div>"""
    months = ["Apr","May","Jun","Jul","Aug","Sep"]
    costs = [51, 53, 58, 64, 71, 84]
    pts = " ".join(f"{60+i*80},{220-int(c/100*140)}" for i,c in enumerate(costs))
    return f"""<!DOCTYPE html><html><head><title>OCI Cost Optimizer v3</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui}}
h1{{color:#C74634;padding:20px 20px 0}}h2{{color:#38bdf8;margin:0 0 10px}}
.card{{background:#1e293b;padding:20px;margin:10px 20px;border-radius:8px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;padding:0 20px}}</style></head>
<body><h1>OCI Cost Optimizer v3</h1>
<p style="padding:0 20px;color:#94a3b8">port {PORT} — v3 savings: $29,400/year vs PAYG | Target: $40/day Q4 2026</p>
<div class="grid">
<div class="card"><h2>Cost Waterfall: Optimization Stack</h2>{bars}</div>
<div class="card"><h2>6-Month Cost Forecast (optimized)</h2>
<svg width="580" height="240">
<polyline points="{pts}" fill="none" stroke="#38bdf8" stroke-width="2.5"/>
{chr(10).join(f'<circle cx="{60+i*80}" cy="{220-int(c/100*140)}" r="4" fill="#38bdf8"/><text x="{55+i*80}" y="{205-int(c/100*140)}" fill="#94a3b8" font-size="10">${c}</text>' for i,c in enumerate(costs))}
{chr(10).join(f'<text x="{55+i*80}" y="235" fill="#94a3b8" font-size="10">{m}</text>' for i,m in enumerate(months))}
</svg></div>
</div>
<div class="card"><h2>Strategy Details</h2>
<p style="color:#94a3b8">Committed reserved 2xA100_80GB: <span style="color:#38bdf8">30% savings</span> | $6.82/hr vs $9.80 on-demand</p>
<p style="color:#94a3b8">Spot instances 4x A100: <span style="color:#22c55e">65% savings</span> | 2.1 preemptions/week, 100% recovery</p>
<p style="color:#94a3b8">AI World Sep spike: <span style="color:#f59e0b">pre-provisioned</span> 8 nodes 48h before event</p></div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="OCI Cost Optimizer v3")
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
