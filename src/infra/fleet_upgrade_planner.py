"""Fleet Upgrade Planner — FastAPI port 8587"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8587

def build_html():
    upgrades = [
        ("groot_finetune_v2→prod", "Apr 2026", "staging→production", "#f59e0b", "pending canary"),
        ("Isaac Sim 4.3", "Q2 2026", "non-breaking infra", "#38bdf8", "scheduled"),
        ("GR00T N2.0 migration", "Q3 2026", "model upgrade", "#a78bfa", "planning"),
        ("A100→H100 migration", "Q4 2026", "hardware upgrade 2×", "#22c55e", "TBD/OCI alloc"),
    ]
    rows = "".join(
        f'<tr>'
        f'<td style="padding:8px;color:#38bdf8;font-size:11px">{u[0]}</td>'
        f'<td style="padding:8px;color:#94a3b8;font-size:11px">{u[1]}</td>'
        f'<td style="padding:8px;color:#e2e8f0;font-size:11px">{u[2]}</td>'
        f'<td style="padding:8px;color:{u[3]};font-size:11px">{u[4]}</td>'
        f'</tr>'
        for u in upgrades
    )
    return f"""<!DOCTYPE html><html><head><title>Fleet Upgrade Planner</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:monospace}}
.hdr{{background:#1e293b;padding:16px 24px;border-bottom:2px solid #C74634}}
h1{{margin:0;color:#C74634;font-size:20px}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;padding:24px}}
.card{{background:#1e293b;border-radius:8px;padding:16px;border:1px solid #334155}}
.metric{{font-size:28px;color:#38bdf8;font-weight:bold}}
.lbl{{color:#64748b;font-size:12px;margin-top:4px}}
table{{width:100%;border-collapse:collapse}}
th{{text-align:left;padding:8px;color:#64748b;border-bottom:1px solid #334155;font-size:11px}}</style></head>
<body><div class="hdr"><h1>Fleet Upgrade Planner</h1><span style="color:#64748b">Upgrade roadmap | Port {PORT}</span></div>
<div class="grid">
<div class="card"><div class="metric">4</div><div class="lbl">Planned Upgrades</div></div>
<div class="card"><div class="metric">48hr</div><div class="lbl">Canary Window</div></div>
<div class="card"><div class="metric">2×</div><div class="lbl">H100 Throughput Gain</div></div>
<div class="card"><div class="metric">Zero</div><div class="lbl">Downtime Target</div></div>
<div class="card" style="grid-column:span 4">
<table><tr><th>Upgrade</th><th>Timeline</th><th>Type</th><th>Status</th></tr>
{rows}</table></div></div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Fleet Upgrade Planner")
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
