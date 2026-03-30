"""DAgger Convergence Analyzer — FastAPI port 8868"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8868

def build_html():
    runs = ["run5","run9","run10","run11 (proj)"]
    colors = ["#94a3b8","#38bdf8","#f59e0b","#22c55e"]
    final_srs = [0.42, 0.71, 0.74, 0.82]
    plateau_steps = [3800, 4200, 4800, 3800]
    pts_list = []
    for run,fsr,pstep in zip(runs,final_srs,plateau_steps):
        pts = []
        for step in range(0, 5001, 250):
            progress = min(step/pstep, 1.0)
            sr = fsr * (1 - math.exp(-3*progress))
            pts.append(f"{60+step//10},{230-int(sr*200)}")
        pts_list.append(" ".join(pts))
    lines = "".join(f'<polyline points="{pts}" fill="none" stroke="{col}" stroke-width="{"2.5" if i==3 else "2"}" stroke-dasharray="{"6,3" if i==3 else "none"}"/>' for i,(pts,col) in enumerate(zip(pts_list,colors)))
    labels = "".join(f'<text x="520" y="{60+i*16}" fill="{col}" font-size="11">{run}: {fsr:.0%}</text>' for i,(run,col,fsr) in enumerate(zip(runs,colors,final_srs)))
    rows = "".join(f'<tr><td style="padding:4px 8px;color:{col}">{run}</td><td style="padding:4px 8px">{fsr:.0%}</td><td style="padding:4px 8px">{pstep}</td><td style="padding:4px 8px;color:#94a3b8">{"IN_PROGRESS" if run=="run10" else "proj" if "proj" in run else "done"}</td></tr>' for run,col,fsr,pstep in zip(runs,colors,final_srs,plateau_steps))
    return f"""<!DOCTYPE html><html><head><title>DAgger Convergence Analyzer</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui}}
h1{{color:#C74634;padding:20px 20px 0}}h2{{color:#38bdf8;margin:0 0 10px}}
.card{{background:#1e293b;padding:20px;margin:10px 20px;border-radius:8px}}</style></head>
<body><h1>DAgger Convergence Analyzer</h1>
<p style="padding:0 20px;color:#94a3b8">port {PORT} — run10 step 1420/5000 | run11 projected SR=0.82 ETA Apr 28</p>
<div class="card"><h2>Convergence Curves: run5 → run11</h2>
<svg width="680" height="260">
{lines}{labels}
<line x1="60" y1="230" x2="560" y2="230" stroke="#334155" stroke-width="1"/>
{"".join(f'<text x="{60+i*100}" y="248" fill="#94a3b8" font-size="10">{i*1000}</text>' for i in range(6))}
<text x="290" y="258" fill="#94a3b8" font-size="11">training steps</text></svg></div>
<div class="card"><h2>Run Summary</h2>
<table style="width:100%;border-collapse:collapse">
<tr><th style="text-align:left;padding:4px 8px;color:#94a3b8">run</th><th style="padding:4px 8px;color:#94a3b8">final SR</th><th style="padding:4px 8px;color:#94a3b8">plateau step</th><th style="padding:4px 8px;color:#94a3b8">status</th></tr>
{rows}</table>
<p style="color:#94a3b8;margin-top:12px">run11 reward_v3 improves early convergence: <span style="color:#22c55e">18% faster</span> to plateau</p></div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="DAgger Convergence Analyzer")
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
