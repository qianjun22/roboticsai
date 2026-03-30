"""API Monetization Tracker — FastAPI port 8577"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8577

def build_html():
    endpoints = ["/infer", "/train", "/eval", "/data"]
    rev_pct = [67, 18, 11, 4]
    colors = ["#38bdf8","#22c55e","#f59e0b","#C74634"]
    bars = "".join(f'<rect x="{20+i*130}" y="{160-rev_pct[i]*2}" width="100" height="{rev_pct[i]*2}" fill="{c}" rx="3"/><text x="{70+i*130}" y="{155-rev_pct[i]*2}" fill="#94a3b8" font-size="10" text-anchor="middle">{p}%</text><text x="{70+i*130}" y="178" fill="#64748b" font-size="11" text-anchor="middle">{e}</text>' for i,(e,p,c) in enumerate(zip(endpoints,rev_pct,colors)))
    months = ["Oct","Nov","Dec","Jan","Feb","Mar"]
    arpu = [847, 921, 1048, 1180, 1290, 1420]
    pts = " ".join(f"{30+i*80},{200-int(v/10)}" for i,v in enumerate(arpu))
    dots = "".join(f'<circle cx="{30+i*80}" cy="{200-int(v/10)}" r="4" fill="#38bdf8"/><text x="{30+i*80}" y="{195-int(v/10)-8}" fill="#94a3b8" font-size="9" text-anchor="middle">${v}</text>' for i,v in enumerate(arpu))
    xlabels = "".join(f'<text x="{30+i*80}" y="215" fill="#64748b" font-size="9" text-anchor="middle">{m}</text>' for i,m in enumerate(months))
    return f"""<!DOCTYPE html><html><head><title>API Monetization Tracker</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:monospace}}
.hdr{{background:#1e293b;padding:16px 24px;border-bottom:2px solid #C74634}}
h1{{margin:0;color:#C74634;font-size:20px}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;padding:24px}}
.card{{background:#1e293b;border-radius:8px;padding:16px;border:1px solid #334155}}
.metric{{font-size:28px;color:#38bdf8;font-weight:bold}}
.lbl{{color:#64748b;font-size:12px;margin-top:4px}}</style></head>
<body><div class="hdr"><h1>API Monetization Tracker</h1><span style="color:#64748b">Revenue per endpoint | Port {PORT}</span></div>
<div class="grid">
<div class="card"><div class="metric">71%</div><div class="lbl">Gross Margin</div></div>
<div class="card"><div class="metric">$0.0015</div><div class="lbl">Blended $/Inference</div></div>
<div class="card"><div class="metric">$1,420</div><div class="lbl">Cohort 1 ARPU (Mar)</div></div>
<div class="card"><div class="metric">67%</div><div class="lbl">/infer Revenue Share</div></div>
<div class="card" style="grid-column:span 2">
<div style="color:#94a3b8;font-size:11px;margin-bottom:6px">REVENUE BY ENDPOINT</div>
<svg width="100%" height="200" viewBox="0 0 560 200">{bars}<line x1="10" y1="163" x2="550" y2="163" stroke="#334155" stroke-width="1"/></svg>
</div>
<div class="card" style="grid-column:span 2">
<div style="color:#94a3b8;font-size:11px;margin-bottom:6px">COHORT 1 ARPU TREND</div>
<svg width="100%" height="230" viewBox="0 0 500 230">
<polyline points="{pts}" fill="none" stroke="#38bdf8" stroke-width="2"/>
{dots}{xlabels}
<line x1="10" y1="205" x2="490" y2="205" stroke="#334155" stroke-width="1"/>
</svg>
</div></div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="API Monetization Tracker")
    @app.get("/", response_class=HTMLResponse)
    def index(): return build_html()
    @app.get("/health")
    def health(): return {"status": "ok", "port": PORT}

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.send_header("Content-Type","text/html"); self.end_headers()
        self.wfile.write(build_html().encode())
    def log_message(self, *a): pass

if __name__ == "__main__":
    if USE_FASTAPI: uvicorn.run(app, host="0.0.0.0", port=PORT)
    else: HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
