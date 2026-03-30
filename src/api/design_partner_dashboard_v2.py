"""Design Partner Dashboard v2 — FastAPI port 8861"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8861

def build_html():
    partners = [
        ("Physical Intelligence","Gold",0.82,1247,"production",94),
        ("Apptronik","Gold",0.71,847,"production",81),
        ("Skild AI","Silver",0.64,412,"pilot",72),
        ("Covariant","Silver",0.69,280,"pilot",68),
        ("1X Technologies","Silver",0.41,141,"at_risk",31),
    ]
    cards = ""
    for name,tier,sr,mrr,stage,health in partners:
        tcol = "#f59e0b" if tier=="Gold" else "#94a3b8"
        hcol = "#22c55e" if health>70 else "#f59e0b" if health>50 else "#ef4444"
        cards += f"""<div style="background:#1e293b;padding:16px;border-radius:8px;border-left:3px solid {tcol}">
<div style="display:flex;justify-content:space-between;align-items:center">
<strong style="color:#e2e8f0">{name}</strong>
<span style="background:{tcol};color:#0f172a;padding:2px 8px;border-radius:10px;font-size:11px">{tier}</span></div>
<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;margin-top:12px">
<div><div style="color:#94a3b8;font-size:11px">SR</div><div style="color:#38bdf8;font-size:18px;font-weight:bold">{sr:.0%}</div></div>
<div><div style="color:#94a3b8;font-size:11px">MRR</div><div style="color:#22c55e;font-size:18px;font-weight:bold">${mrr}</div></div>
<div><div style="color:#94a3b8;font-size:11px">Health</div><div style="color:{hcol};font-size:18px;font-weight:bold">{health}</div></div>
</div>
<div style="margin-top:8px;font-size:11px;color:#94a3b8">Stage: {stage}</div></div>"""
    total_mrr = sum(p[3] for p in partners)
    return f"""<!DOCTYPE html><html><head><title>Design Partner Dashboard v2</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui}}
h1{{color:#C74634;padding:20px 20px 0}}h2{{color:#38bdf8;margin:0 0 10px}}
.card{{background:#1e293b;padding:20px;margin:10px 20px;border-radius:8px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin:10px 20px}}</style></head>
<body><h1>Design Partner Dashboard v2</h1>
<p style="padding:0 20px;color:#94a3b8">port {PORT} — 5 design partners | Total MRR: <span style="color:#22c55e">${total_mrr:,}</span></p>
<div class="grid">{cards}</div>
<div class="card"><h2>Pipeline Value</h2>
<p style="color:#94a3b8">Current MRR: <span style="color:#22c55e">${total_mrr:,}</span> | Upsell pipeline: <span style="color:#38bdf8">$84,000 ARR</span> | Pending pilots: <span style="color:#f59e0b">3 × $40k</span></p>
<p style="color:#94a3b8">Critical path: <span style="color:#ef4444">Machina DPA unblock</span> → go-live Jun 12</p></div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Design Partner Dashboard v2")
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
