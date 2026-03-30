"""Customer Success Dashboard — FastAPI port 8555"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8555

def build_html():
    partners = [
        ("RoboLogic", 92, "production", 18, 72),
        ("AutoMfg Co", 78, "production", 24, 68),
        ("FlexArm Inc", 88, "production", 14, 75),
        ("BotWorks", 61, "onboarding", 32, 55),
        ("MechVision", 74, "onboarding", 22, 70),
    ]
    rows = "".join(
        f'<tr>'
        f'<td style="padding:8px;color:#38bdf8">{p[0]}</td>'
        f'<td style="padding:8px"><div style="background:#334155;border-radius:4px;height:10px;width:150px"><div style="background:{"#22c55e" if p[1]>80 else "#f59e0b"};height:10px;width:{p[1]*1.5:.0f}px;border-radius:4px"></div></div></td>'
        f'<td style="padding:8px;color:{"#22c55e" if p[2]=="production" else "#f59e0b"}">{p[2]}</td>'
        f'<td style="padding:8px;color:#e2e8f0">{p[3]}d</td>'
        f'<td style="padding:8px;color:#38bdf8">{p[4]}</td>'
        f'</tr>'
        for p in partners
    )
    return f"""<!DOCTYPE html><html><head><title>Customer Success Dashboard</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:monospace}}
.hdr{{background:#1e293b;padding:16px 24px;border-bottom:2px solid #C74634}}
h1{{margin:0;color:#C74634;font-size:20px}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;padding:24px}}
.card{{background:#1e293b;border-radius:8px;padding:16px;border:1px solid #334155}}
.metric{{font-size:28px;color:#38bdf8;font-weight:bold}}
.lbl{{color:#64748b;font-size:12px;margin-top:4px}}
table{{width:100%;border-collapse:collapse}}
th{{text-align:left;padding:8px;color:#64748b;border-bottom:1px solid #334155}}</style></head>
<body><div class="hdr"><h1>Customer Success Dashboard</h1><span style="color:#64748b">Partner health & NPS | Port {PORT}</span></div>
<div class="grid">
<div class="card"><div class="metric">3</div><div class="lbl">In Production</div></div>
<div class="card"><div class="metric">2</div><div class="lbl">In Onboarding</div></div>
<div class="card"><div class="metric">18d</div><div class="lbl">Avg Time-to-Prod</div></div>
<div class="card"><div class="metric">72</div><div class="lbl">NPS Score</div></div>
<div class="card" style="grid-column:span 4">
<table><tr><th>Partner</th><th>Health Score</th><th>Stage</th><th>Time-to-Prod</th><th>NPS</th></tr>
{rows}</table></div></div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Customer Success Dashboard")
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
