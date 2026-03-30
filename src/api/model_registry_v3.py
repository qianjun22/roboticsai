"""Model Registry V3 — FastAPI port 8567"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8567

def build_html():
    models = [
        ("bc_baseline", "archived", 0.05, 231, "$0.43"),
        ("dagger_run9_v2.2", "production", 0.71, 226, "$0.43"),
        ("groot_finetune_v2", "staging", 0.78, 226, "$1.20"),
        ("dagger_run10", "training", None, None, "—"),
        ("groot_finetune_v3", "training", None, None, "—"),
    ]
    rows = "".join(
        f'<tr>'
        f'<td style="padding:8px;color:#38bdf8;font-size:11px">{m[0]}</td>'
        f'<td style="padding:8px;color:{"#22c55e" if m[1]=="production" else ("#f59e0b" if m[1]=="staging" else ("#38bdf8" if m[1]=="training" else "#64748b"))};font-size:11px">{m[1]}</td>'
        f'<td style="padding:8px;color:#e2e8f0;font-size:11px">{"—" if m[2] is None else m[2]}</td>'
        f'<td style="padding:8px;color:#e2e8f0;font-size:11px">{"—" if m[3] is None else f"{m[3]}ms"}</td>'
        f'<td style="padding:8px;color:#e2e8f0;font-size:11px">{m[4]}</td>'
        f'</tr>'
        for m in models
    )
    return f"""<!DOCTYPE html><html><head><title>Model Registry V3</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:monospace}}
.hdr{{background:#1e293b;padding:16px 24px;border-bottom:2px solid #C74634}}
h1{{margin:0;color:#C74634;font-size:20px}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;padding:24px}}
.card{{background:#1e293b;border-radius:8px;padding:16px;border:1px solid #334155}}
.metric{{font-size:28px;color:#38bdf8;font-weight:bold}}
.lbl{{color:#64748b;font-size:12px;margin-top:4px}}
table{{width:100%;border-collapse:collapse}}
th{{text-align:left;padding:8px;color:#64748b;border-bottom:1px solid #334155;font-size:11px}}</style></head>
<body><div class="hdr"><h1>Model Registry V3</h1><span style="color:#64748b">Lifecycle management | Port {PORT}</span></div>
<div class="grid">
<div class="card"><div class="metric">5</div><div class="lbl">Total Models</div></div>
<div class="card"><div class="metric">78%</div><div class="lbl">Best Staging SR</div></div>
<div class="card"><div class="metric">75%</div><div class="lbl">Auto-Promote SR</div></div>
<div class="card"><div class="metric">48hr</div><div class="lbl">Canary Window</div></div>
<div class="card" style="grid-column:span 4">
<table><tr><th>Model</th><th>Stage</th><th>SR</th><th>Latency</th><th>Cost/Run</th></tr>
{rows}</table></div></div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Model Registry V3")
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
