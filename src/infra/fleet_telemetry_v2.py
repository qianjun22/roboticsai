"""Fleet Telemetry V2 — FastAPI port 8547"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8547

def build_html():
    nodes = ["GPU1", "GPU2", "GPU3", "GPU4", "GPU5", "GPU6"]
    regions = ["Ashburn", "Ashburn", "Ashburn", "Ashburn", "Phoenix", "Frankfurt"]
    gpu_util = [random.randint(78, 98) for _ in nodes]
    mem_util = [random.randint(55, 92) for _ in nodes]
    status_color = ["#22c55e" if g > 60 else "#f59e0b" for g in gpu_util]
    rows = "".join(
        f'<tr>'
        f'<td style="padding:8px;color:#38bdf8">{n}</td>'
        f'<td style="padding:8px;color:#64748b">{r}</td>'
        f'<td style="padding:8px;color:{c}">{g}%</td>'
        f'<td style="padding:8px;color:#e2e8f0">{m}%</td>'
        f'<td style="padding:8px;color:#22c55e">OK</td>'
        f'</tr>'
        for n,r,g,m,c in zip(nodes,regions,gpu_util,mem_util,status_color)
    )
    return f"""<!DOCTYPE html><html><head><title>Fleet Telemetry V2</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:monospace}}
.hdr{{background:#1e293b;padding:16px 24px;border-bottom:2px solid #C74634}}
h1{{margin:0;color:#C74634;font-size:20px}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;padding:24px}}
.card{{background:#1e293b;border-radius:8px;padding:16px;border:1px solid #334155}}
.metric{{font-size:28px;color:#38bdf8;font-weight:bold}}
.lbl{{color:#64748b;font-size:12px;margin-top:4px}}
table{{width:100%;border-collapse:collapse}}
th{{text-align:left;padding:8px;color:#64748b;border-bottom:1px solid #334155}}</style></head>
<body><div class="hdr"><h1>Fleet Telemetry V2</h1><span style="color:#64748b">6-node fleet health | Port {PORT}</span></div>
<div class="grid">
<div class="card"><div class="metric">6</div><div class="lbl">Fleet Nodes</div></div>
<div class="card"><div class="metric">14.2k</div><div class="lbl">Events/sec Peak</div></div>
<div class="card"><div class="metric">99.7%</div><div class="lbl">GPU4 Uptime</div></div>
<div class="card"><div class="metric">0</div><div class="lbl">P1 Alerts (30d)</div></div>
<div class="card" style="grid-column:span 4">
<table><tr><th>Node</th><th>Region</th><th>GPU Util</th><th>Mem Util</th><th>Status</th></tr>
{rows}</table></div></div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Fleet Telemetry V2")
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
