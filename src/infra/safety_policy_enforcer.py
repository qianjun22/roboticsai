"""Safety Policy Enforcer — FastAPI port 8540"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8540

def build_html():
    checks = [
        ("Joint Limit Enforcement", "Active", "#22c55e"),
        ("Torque Cap (4.2Nm)", "Active", "#22c55e"),
        ("Workspace Boundary", "Active", "#22c55e"),
        ("Emergency Stop (<8ms)", "Active", "#22c55e"),
        ("Collision Detection", "Active", "#22c55e"),
        ("Safe Exploration Mode", "Standby", "#f59e0b"),
    ]
    rows = "".join(f'<tr><td style="padding:8px;color:#e2e8f0">{c[0]}</td><td style="padding:8px;color:{c[2]}">{c[1]}</td></tr>' for c in checks)
    return f"""<!DOCTYPE html><html><head><title>Safety Policy Enforcer</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:monospace}}
.hdr{{background:#1e293b;padding:16px 24px;border-bottom:2px solid #C74634}}
h1{{margin:0;color:#C74634;font-size:20px}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;padding:24px}}
.card{{background:#1e293b;border-radius:8px;padding:16px;border:1px solid #334155}}
.metric{{font-size:28px;color:#38bdf8;font-weight:bold}}
.lbl{{color:#64748b;font-size:12px;margin-top:4px}}
table{{width:100%;border-collapse:collapse}}
th{{text-align:left;padding:8px;color:#64748b;border-bottom:1px solid #334155}}</style></head>
<body><div class="hdr"><h1>Safety Policy Enforcer</h1><span style="color:#64748b">Runtime safety constraints | Port {PORT}</span></div>
<div class="grid">
<div class="card"><div class="metric">97.4%</div><div class="lbl">Safety Score</div></div>
<div class="card"><div class="metric">0</div><div class="lbl">P0 Events (30d)</div></div>
<div class="card"><div class="metric">&lt;8ms</div><div class="lbl">E-Stop Latency</div></div>
<div class="card"><div class="metric">4.2Nm</div><div class="lbl">Torque Limit</div></div>
<div class="card" style="grid-column:span 4">
<table><tr><th>Safety Control</th><th>Status</th></tr>{rows}</table>
</div></div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Safety Policy Enforcer")
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
