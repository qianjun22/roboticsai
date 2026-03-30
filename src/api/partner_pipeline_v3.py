"""Partner Pipeline v3 — FastAPI port 8865"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8865

def build_html():
    stages = [
        ("Referral","NVIDIA + inbound",12,480000),
        ("Qualified","Technical fit confirmed",8,320000),
        ("Demo","Live demo delivered",5,200000),
        ("Pilot","30-day trial active",3,120000),
        ("Negotiation","Contract in review",2,80000),
        ("Closed Won","Contract signed",3,84000),
    ]
    funnel = ""
    max_w = 500
    for i,(stage,desc,count,arr) in enumerate(stages):
        w = int(max_w * (len(stages)-i)/len(stages) * 0.85 + max_w*0.15)
        off = (max_w-w)//2
        col = "#22c55e" if i==len(stages)-1 else "#38bdf8" if i>=3 else "#94a3b8"
        funnel += f'<rect x="{off+10}" y="{20+i*36}" width="{w}" height="30" fill="{col}" opacity="0.8" rx="3"/>'
        funnel += f'<text x="270" y="{40+i*36}" text-anchor="middle" fill="#0f172a" font-size="11" font-weight="bold">{stage}: {count} deals | ${arr//1000}k ARR</text>'
    return f"""<!DOCTYPE html><html><head><title>Partner Pipeline v3</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui}}
h1{{color:#C74634;padding:20px 20px 0}}h2{{color:#38bdf8;margin:0 0 10px}}
.card{{background:#1e293b;padding:20px;margin:10px 20px;border-radius:8px}}</style></head>
<body><h1>Partner Pipeline v3</h1>
<p style="padding:0 20px;color:#94a3b8">port {PORT} — v3 with NVIDIA co-sell channel | $284k weighted ARR pipeline</p>
<div class="card"><h2>Pipeline Funnel</h2>
<svg width="560" height="240">{funnel}</svg></div>
<div class="card"><h2>NVIDIA Co-Sell Lane</h2>
<p style="color:#94a3b8">NVIDIA-referred deals: <span style="color:#22c55e">42% discovery&#8594;pilot</span> vs inbound 18%</p>
<p style="color:#94a3b8">3 NVIDIA-referred leads in discovery: <span style="color:#38bdf8">2 Series B robotics startups + 1 Tier-1 auto OEM</span></p>
<p style="color:#94a3b8">Co-sell ARR multiplier: <span style="color:#22c55e">3.1&#215;</span> vs inbound deals | avg deal $124k vs $40k</p>
<p style="color:#94a3b8">NVIDIA preferred-cloud agreement: <span style="color:#f59e0b">BLOCKED &#8212; Greg Pavlik intro needed</span></p></div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Partner Pipeline v3")
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
