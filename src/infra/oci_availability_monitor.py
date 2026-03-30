"""OCI Availability Monitor — FastAPI port 8585"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8585

def build_html():
    services = [
        ("Compute (A100)", 99.97, "#22c55e"),
        ("Block Storage", 99.91, "#f59e0b"),
        ("Object Storage", 100.0, "#22c55e"),
        ("VCN/Networking", 99.99, "#22c55e"),
        ("IAM", 100.0, "#22c55e"),
        ("Functions", 99.94, "#22c55e"),
    ]
    rows = "".join(
        f'<tr>'
        f'<td style="padding:8px;color:#e2e8f0">{s[0]}</td>'
        f'<td style="padding:8px"><div style="background:#334155;border-radius:4px;height:10px;width:200px"><div style="background:{s[2]};height:10px;width:{int((s[1]-99)*200):.0f}px;border-radius:4px"></div></div></td>'
        f'<td style="padding:8px;color:{s[2]}">{s[1]}%</td>'
        f'</tr>'
        for s in services
    )
    return f"""<!DOCTYPE html><html><head><title>OCI Availability Monitor</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:monospace}}
.hdr{{background:#1e293b;padding:16px 24px;border-bottom:2px solid #C74634}}
h1{{margin:0;color:#C74634;font-size:20px}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;padding:24px}}
.card{{background:#1e293b;border-radius:8px;padding:16px;border:1px solid #334155}}
.metric{{font-size:28px;color:#38bdf8;font-weight:bold}}
.lbl{{color:#64748b;font-size:12px;margin-top:4px}}
table{{width:100%;border-collapse:collapse}}
th{{text-align:left;padding:8px;color:#64748b;border-bottom:1px solid #334155}}</style></head>
<body><div class="hdr"><h1>OCI Availability Monitor</h1><span style="color:#64748b">Service availability | Port {PORT}</span></div>
<div class="grid">
<div class="card"><div class="metric">99.97%</div><div class="lbl">Compute SLA</div></div>
<div class="card"><div class="metric">0</div><div class="lbl">Full Outages (90d)</div></div>
<div class="card"><div class="metric">8.4min</div><div class="lbl">MTTR</div></div>
<div class="card"><div class="metric">1x</div><div class="lbl">Multi-Region Failover Used</div></div>
<div class="card" style="grid-column:span 4">
<table><tr><th>OCI Service</th><th>Availability (90d)</th><th>Uptime %</th></tr>
{rows}</table></div></div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="OCI Availability Monitor")
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
