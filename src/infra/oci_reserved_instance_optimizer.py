"""OCI Reserved Instance Optimizer — FastAPI port 8565"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8565

def build_html():
    strategies = ["On-Demand Only", "Spot Only", "Reserved 2× + Spot 4×", "All Reserved"]
    annual_cost = [85848, 21600, 47200, 59808]
    colors = ["#C74634", "#22c55e", "#38bdf8", "#f59e0b"]
    bars = "".join(f'<rect x="{20+i*130}" y="{160-int(c/1000)}" width="100" height="{int(c/1000)}" fill="{col}" rx="3"/><text x="{70+i*130}" y="{155-int(c/1000)}" fill="#94a3b8" font-size="9" text-anchor="middle">${c:,}</text><text x="{70+i*130}" y="178" fill="#64748b" font-size="9" text-anchor="middle">{s.split(" ")[0]}</text>' for i,(s,c,col) in enumerate(zip(strategies,annual_cost,colors)))
    return f"""<!DOCTYPE html><html><head><title>OCI Reserved Instance Optimizer</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:monospace}}
.hdr{{background:#1e293b;padding:16px 24px;border-bottom:2px solid #C74634}}
h1{{margin:0;color:#C74634;font-size:20px}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;padding:24px}}
.card{{background:#1e293b;border-radius:8px;padding:16px;border:1px solid #334155}}
.metric{{font-size:28px;color:#38bdf8;font-weight:bold}}
.lbl{{color:#64748b;font-size:12px;margin-top:4px}}</style></head>
<body><div class="hdr"><h1>OCI Reserved Instance Optimizer</h1><span style="color:#64748b">Annual cost by strategy | Port {PORT}</span></div>
<div class="grid">
<div class="card"><div class="metric">$8.2K</div><div class="lbl">Annual Savings (vs On-Demand)</div></div>
<div class="card"><div class="metric">30%</div><div class="lbl">Reserved vs On-Demand Discount</div></div>
<div class="card"><div class="metric">18mo</div><div class="lbl">ROI Payback Period</div></div>
<div class="card"><div class="metric">2+4</div><div class="lbl">Rec: 2×Reserved + 4×Spot</div></div>
<div class="card" style="grid-column:span 4">
<div style="color:#94a3b8;font-size:12px;margin-bottom:8px">ANNUAL COST BY STRATEGY</div>
<svg width="100%" height="200" viewBox="0 0 560 200">{bars}
<line x1="10" y1="162" x2="550" y2="162" stroke="#334155" stroke-width="1"/>
</svg></div></div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="OCI Reserved Instance Optimizer")
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
