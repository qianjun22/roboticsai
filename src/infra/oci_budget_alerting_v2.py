"""OCI Budget Alerting V2 — FastAPI port 8543"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8543

def build_html():
    categories = ["Compute", "Storage", "Network", "Misc"]
    budgets = [4000, 1200, 500, 300]
    actuals = [3280, 920, 340, 280]
    colors = ["#38bdf8", "#22c55e", "#f59e0b", "#C74634"]
    bars = "".join(
        f'<rect x="{30+i*120}" y="{160-int(b/30)}" width="40" height="{int(b/30)}" fill="#334155" rx="3"/>'
        f'<rect x="{30+i*120}" y="{160-int(a/30)}" width="40" height="{int(a/30)}" fill="{c}" rx="3"/>'
        f'<text x="{50+i*120}" y="175" fill="#64748b" font-size="10" text-anchor="middle">{cat}</text>'
        f'<text x="{50+i*120}" y="{155-int(b/30)}" fill="#64748b" font-size="9" text-anchor="middle">${b}</text>'
        for i,(cat,b,a,c) in enumerate(zip(categories,budgets,actuals,colors))
    )
    total_budget = sum(budgets); total_actual = sum(actuals)
    return f"""<!DOCTYPE html><html><head><title>OCI Budget Alerting V2</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:monospace}}
.hdr{{background:#1e293b;padding:16px 24px;border-bottom:2px solid #C74634}}
h1{{margin:0;color:#C74634;font-size:20px}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;padding:24px}}
.card{{background:#1e293b;border-radius:8px;padding:16px;border:1px solid #334155}}
.metric{{font-size:28px;color:#38bdf8;font-weight:bold}}
.lbl{{color:#64748b;font-size:12px;margin-top:4px}}</style></head>
<body><div class="hdr"><h1>OCI Budget Alerting V2</h1><span style="color:#64748b">Spend vs budget | Port {PORT}</span></div>
<div class="grid">
<div class="card"><div class="metric">${total_actual:,}</div><div class="lbl">Q1 Actual Spend</div></div>
<div class="card"><div class="metric">${total_budget:,}</div><div class="lbl">Q1 Budget</div></div>
<div class="card"><div class="metric">{int(total_actual/total_budget*100)}%</div><div class="lbl">Budget Used</div></div>
<div class="card"><div class="metric">0</div><div class="lbl">Threshold Breaches</div></div>
<div class="card" style="grid-column:span 4">
<div style="color:#94a3b8;font-size:12px;margin-bottom:8px">ACTUAL vs BUDGET BY CATEGORY</div>
<svg width="100%" height="200" viewBox="0 0 540 200">{bars}
<line x1="10" y1="165" x2="530" y2="165" stroke="#334155" stroke-width="1"/>
</svg></div></div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="OCI Budget Alerting V2")
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
