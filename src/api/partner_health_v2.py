"""Partner Health V2 — FastAPI port 8533"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8533

def build_html():
    partners = [
        ("RoboLogic", 99.97, 218, 0.03, "healthy"),
        ("AutoMfg Co", 99.82, 287, 0.18, "watch"),
        ("FlexArm Inc", 100.0, 203, 0.00, "healthy"),
        ("BotWorks", 98.94, 342, 0.82, "at-risk"),
        ("MechVision", 99.71, 231, 0.11, "healthy"),
    ]
    rows = "".join(
        f'<tr>'
        f'<td style="padding:8px;color:#38bdf8">{p[0]}</td>'
        f'<td style="padding:8px;color:#e2e8f0">{p[1]}%</td>'
        f'<td style="padding:8px;color:#e2e8f0">{p[2]}ms</td>'
        f'<td style="padding:8px;color:#e2e8f0">{p[3]}%</td>'
        f'<td style="padding:8px;color:{"#22c55e" if p[4]=="healthy" else ("#f59e0b" if p[4]=="watch" else "#C74634")}">{p[4]}</td>'
        f'</tr>'
        for p in partners
    )
    return f"""<!DOCTYPE html><html><head><title>Partner Health V2</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:monospace}}
.hdr{{background:#1e293b;padding:16px 24px;border-bottom:2px solid #C74634}}
h1{{margin:0;color:#C74634;font-size:20px}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;padding:24px}}
.card{{background:#1e293b;border-radius:8px;padding:16px;border:1px solid #334155}}
.metric{{font-size:28px;color:#38bdf8;font-weight:bold}}
.lbl{{color:#64748b;font-size:12px;margin-top:4px}}
table{{width:100%;border-collapse:collapse}}
th{{text-align:left;padding:8px;color:#64748b;border-bottom:1px solid #334155}}</style></head>
<body><div class="hdr"><h1>Partner Health V2</h1><span style="color:#64748b">API health scorecard | Port {PORT}</span></div>
<div class="grid">
<div class="card"><div class="metric">5</div><div class="lbl">Active Partners</div></div>
<div class="card"><div class="metric">3</div><div class="lbl">Healthy</div></div>
<div class="card"><div class="metric">1</div><div class="lbl">At Risk</div></div>
<div class="card"><div class="metric">68%</div><div class="lbl">Churn Risk (BotWorks)</div></div>
<div class="card" style="grid-column:span 4">
<table><tr><th>Partner</th><th>Uptime</th><th>Latency</th><th>Error Rate</th><th>Status</th></tr>
{rows}</table></div></div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Partner Health V2")
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
