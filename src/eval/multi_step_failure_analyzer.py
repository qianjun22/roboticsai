"""Multi-Step Failure Analyzer — FastAPI port 8860"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8860

def build_html():
    steps = ["detect_object","plan_grasp","approach","grasp","lift","place"]
    step_sr = [0.94, 0.88, 0.84, 0.81, 0.71, 0.87]
    bars = ""
    for i,(s,sr) in enumerate(zip(steps,step_sr)):
        w = int(sr*320)
        col = "#22c55e" if sr>0.85 else "#f59e0b" if sr>0.75 else "#ef4444"
        bars += f'<div style="display:flex;align-items:center;margin:6px 0"><span style="width:130px;font-size:12px">{s}</span><div style="background:{col};width:{w}px;height:20px;border-radius:3px"></div><span style="margin-left:8px;font-size:12px">{sr:.0%}</span></div>'
    causes = [("grasp_miss",52),("drop",21),("trajectory_err",15),("timeout",8),("other",4)]
    pie = ""
    angle = 0
    cols2 = ["#ef4444","#f59e0b","#38bdf8","#22c55e","#a78bfa"]
    cx,cy,r2 = 100,100,80
    for (c,p),col in zip(causes,cols2):
        sweep = p/100*2*math.pi
        x1=cx+r2*math.sin(angle); y1=cy-r2*math.cos(angle)
        x2=cx+r2*math.sin(angle+sweep); y2=cy-r2*math.cos(angle+sweep)
        lg=1 if p>50 else 0
        pie += f'<path d="M{cx},{cy} L{x1:.1f},{y1:.1f} A{r2},{r2} 0 {lg},1 {x2:.1f},{y2:.1f} Z" fill="{col}" opacity="0.9"/>'
        angle += sweep
    return f"""<!DOCTYPE html><html><head><title>Multi-Step Failure Analyzer</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui}}
h1{{color:#C74634;padding:20px 20px 0}}h2{{color:#38bdf8;margin:0 0 10px}}
.card{{background:#1e293b;padding:20px;margin:10px 20px;border-radius:8px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}</style></head>
<body><h1>Multi-Step Failure Analyzer</h1>
<p style="padding:0 20px;color:#94a3b8">port {PORT} — step-by-step failure attribution for 5-step manipulation tasks</p>
<div class="grid" style="padding:0 20px">
<div class="card"><h2>Per-Step Success Rate</h2>{bars}
<p style="color:#94a3b8;font-size:12px;margin-top:8px">lift (step 5) bottleneck: 0.71 SR → 52% of downstream failures</p></div>
<div class="card"><h2>Failure Root Causes</h2>
<svg width="200" height="200"><g transform="translate(0,0)">{pie}</g></svg>
<div style="font-size:12px;margin-top:8px">{"" .join(f"<span style='color:{c};margin-right:12px'>■ {n} {p}%</span>" for (n,p),c in zip(causes,cols2))}</div></div>
</div>
<div class="card" style="margin:10px 20px"><h2>Recovery Opportunity</h2>
<p style="color:#94a3b8">Step-3 lift correction: <span style="color:#22c55e">+0.06pp SR</span> | DAgger run11 priority target</p>
<p style="color:#94a3b8">Approach angle fix: <span style="color:#38bdf8">+0.08pp SR</span> | 47% of grasp_miss failures</p></div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Multi-Step Failure Analyzer")
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
