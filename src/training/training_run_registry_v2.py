"""Training Run Registry V2 — FastAPI port 8551"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8551

def build_html():
    runs = [
        ("bc_baseline", "BC", 0.05, 0.142, 231, 0.43, "archived"),
        ("dagger_run5", "DAgger", 0.05, 0.118, 228, 0.43, "archived"),
        ("dagger_run9", "DAgger", 0.71, 0.099, 226, 0.43, "production"),
        ("groot_finetune_v2", "Fine-tune", 0.78, 0.091, 226, 1.20, "staging"),
        ("dagger_run10", "DAgger", None, None, None, None, "training"),
    ]
    rows = "".join(
        f'<tr>'
        f'<td style="padding:6px;color:#38bdf8;font-size:11px">{r[0]}</td>'
        f'<td style="padding:6px;color:#94a3b8;font-size:11px">{r[1]}</td>'
        f'<td style="padding:6px;color:#e2e8f0;font-size:11px">{"\u2014" if r[2] is None else r[2]}</td>'
        f'<td style="padding:6px;color:#e2e8f0;font-size:11px">{"\u2014" if r[3] is None else r[3]}</td>'
        f'<td style="padding:6px;color:#e2e8f0;font-size:11px">{"\u2014" if r[4] is None else f"{r[4]}ms"}</td>'
        f'<td style="padding:6px;color:{"#22c55e" if r[6]=="production" else ("#f59e0b" if r[6]=="staging" else ("#38bdf8" if r[6]=="training" else "#64748b"))};font-size:11px">{r[6]}</td>'
        f'</tr>'
        for r in runs
    )
    return f"""<!DOCTYPE html><html><head><title>Training Run Registry V2</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:monospace}}
.hdr{{background:#1e293b;padding:16px 24px;border-bottom:2px solid #C74634}}
h1{{margin:0;color:#C74634;font-size:20px}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;padding:24px}}
.card{{background:#1e293b;border-radius:8px;padding:16px;border:1px solid #334155}}
.metric{{font-size:28px;color:#38bdf8;font-weight:bold}}
.lbl{{color:#64748b;font-size:12px;margin-top:4px}}
table{{width:100%;border-collapse:collapse}}
th{{text-align:left;padding:6px;color:#64748b;border-bottom:1px solid #334155;font-size:11px}}</style></head>
<body><div class="hdr"><h1>Training Run Registry V2</h1><span style="color:#64748b">All runs tracker | Port {PORT}</span></div>
<div class="grid">
<div class="card"><div class="metric">{len(runs)}</div><div class="lbl">Total Runs</div></div>
<div class="card"><div class="metric">0.78</div><div class="lbl">Best SR (staging)</div></div>
<div class="card"><div class="metric">$0.43</div><div class="lbl">Min Cost/Run</div></div>
<div class="card"><div class="metric">groot_v2</div><div class="lbl">Pareto Champion</div></div>
<div class="card" style="grid-column:span 4">
<table><tr><th>Run</th><th>Type</th><th>SR</th><th>Val Loss</th><th>Latency</th><th>Status</th></tr>
{rows}</table></div></div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Training Run Registry V2")
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
