"""Inference SLA Monitor V2 — FastAPI port 8557"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8557

def build_html():
    partners = [
        ("RoboLogic", "Basic", 99.97, 218, "compliant"),
        ("AutoMfg Co", "Pro", 99.82, 231, "compliant"),
        ("FlexArm Inc", "Enterprise", 100.0, 198, "compliant"),
        ("BotWorks", "Pro", 98.94, 312, "breach"),
        ("MechVision", "Basic", 99.71, 224, "compliant"),
    ]
    rows = "".join(
        f'<tr>'
        f'<td style="padding:8px;color:#38bdf8">{p[0]}</td>'
        f'<td style="padding:8px;color:#64748b">{p[1]}</td>'
        f'<td style="padding:8px;color:#e2e8f0">{p[2]}%</td>'
        f'<td style="padding:8px;color:{"#C74634" if p[3]>250 else "#e2e8f0"}">{p[3]}ms</td>'
        f'<td style="padding:8px;color:{"#22c55e" if p[4]=="compliant" else "#C74634"}">{p[4]}</td>'
        f'</tr>'
        for p in partners
    )
    return f"""<!DOCTYPE html><html><head><title>Inference SLA Monitor V2</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:monospace}}
.hdr{{background:#1e293b;padding:16px 24px;border-bottom:2px solid #C74634}}
h1{{margin:0;color:#C74634;font-size:20px}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;padding:24px}}
.card{{background:#1e293b;border-radius:8px;padding:16px;border:1px solid #334155}}
.metric{{font-size:28px;color:#38bdf8;font-weight:bold}}
.lbl{{color:#64748b;font-size:12px;margin-top:4px}}
table{{width:100%;border-collapse:collapse}}
th{{text-align:left;padding:8px;color:#64748b;border-bottom:1px solid #334155}}</style></head>
<body><div class="hdr"><h1>Inference SLA Monitor V2</h1><span style="color:#64748b">Per-partner SLA compliance | Port {PORT}</span></div>
<div class="grid">
<div class="card"><div class="metric">99.94%</div><div class="lbl">Overall SLA Compliance</div></div>
<div class="card"><div class="metric">2</div><div class="lbl">Minor Breaches (30d)</div></div>
<div class="card"><div class="metric">312ms</div><div class="lbl">Worst P99 (BotWorks)</div></div>
<div class="card"><div class="metric">250ms</div><div class="lbl">Enterprise SLA Limit</div></div>
<div class="card" style="grid-column:span 4">
<table><tr><th>Partner</th><th>Tier</th><th>Uptime</th><th>P99</th><th>Status</th></tr>
{rows}</table></div></div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Inference SLA Monitor V2")
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
