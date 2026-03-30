"""OCI Security Scorecard — FastAPI port 8525"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8525

def build_html():
    checks = [
        ("Network Isolation", 100, "pass"),
        ("IAM Policies", 95, "pass"),
        ("Encryption at Rest", 100, "pass"),
        ("Encryption in Transit", 100, "pass"),
        ("Audit Logging", 88, "warn"),
        ("Vulnerability Scan", 92, "pass"),
        ("Secrets Management", 97, "pass"),
        ("Compliance (SOC2)", 85, "warn"),
    ]
    rows = "".join(f'<tr><td style="padding:8px;color:#e2e8f0">{c[0]}</td><td style="padding:8px"><div style="background:#334155;border-radius:4px;height:12px;width:200px"><div style="background:{"#22c55e" if c[2]=="pass" else "#f59e0b"};height:12px;width:{c[1]*2}px;border-radius:4px"></div></div></td><td style="padding:8px;color:{"#22c55e" if c[2]=="pass" else "#f59e0b'}">{c[1]}%</td></tr>' for c in checks)
    overall = int(sum(c[1] for c in checks)/len(checks))
    return f"""<!DOCTYPE html><html><head><title>OCI Security Scorecard</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:monospace}}
.hdr{{background:#1e293b;padding:16px 24px;border-bottom:2px solid #C74634}}
h1{{margin:0;color:#C74634;font-size:20px}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;padding:24px}}
.card{{background:#1e293b;border-radius:8px;padding:16px;border:1px solid #334155}}
.metric{{font-size:28px;color:#38bdf8;font-weight:bold}}
.lbl{{color:#64748b;font-size:12px;margin-top:4px}}
table{{width:100%;border-collapse:collapse}}
th{{text-align:left;padding:8px;color:#64748b;border-bottom:1px solid #334155}}</style></head>
<body><div class="hdr"><h1>OCI Security Scorecard</h1><span style="color:#64748b">Compliance & security | Port {PORT}</span></div>
<div class="grid">
<div class="card"><div class="metric">{overall}%</div><div class="lbl">Overall Score</div></div>
<div class="card"><div class="metric">{sum(1 for c in checks if c[2]=="pass")}</div><div class="lbl">Checks Passed</div></div>
<div class="card"><div class="metric">{sum(1 for c in checks if c[2]=="warn")}</div><div class="lbl">Warnings</div></div>
<div class="card"><div class="metric">A-</div><div class="lbl">Security Grade</div></div>
<div class="card" style="grid-column:span 4">
<table><tr><th>Control</th><th>Score</th><th>Status</th></tr>{rows}</table>
</div></div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="OCI Security Scorecard")
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
