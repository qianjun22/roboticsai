"""OCI Spot Strategy V3 — FastAPI port 8553"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8553

def build_html():
    # Preemption risk heatmap: 3 regions × 24 hours
    regions = ["Ashburn", "Phoenix", "Frankfurt"]
    hours = list(range(0, 24, 4))
    # Risk 0-10
    risk_data = [
        [2, 1, 3, 5, 7, 4],  # Ashburn
        [3, 2, 2, 4, 6, 5],  # Phoenix
        [4, 3, 4, 6, 8, 6],  # Frankfurt
    ]
    cells = "".join(
        f'<rect x="{80+j*70}" y="{20+i*50}" width="60" height="40" fill="{"#1e3a5f" if risk_data[i][j]<4 else ("#3a2e00" if risk_data[i][j]<7 else "#3a1e1e")}" rx="3"/>'
        f'<text x="{110+j*70}" y="{45+i*50}" fill="#e2e8f0" font-size="12" text-anchor="middle">{risk_data[i][j]}/10</text>'
        for i in range(3) for j in range(len(hours))
    )
    r_labels = "".join(f'<text x="70" y="{45+i*50}" fill="#94a3b8" font-size="10" text-anchor="end">{r}</text>' for i,r in enumerate(regions))
    h_labels = "".join(f'<text x="{110+i*70}" y="15" fill="#64748b" font-size="9" text-anchor="middle">{h:02d}:00</text>' for i,h in enumerate(hours))
    return f"""<!DOCTYPE html><html><head><title>OCI Spot Strategy V3</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:monospace}}
.hdr{{background:#1e293b;padding:16px 24px;border-bottom:2px solid #C74634}}
h1{{margin:0;color:#C74634;font-size:20px}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;padding:24px}}
.card{{background:#1e293b;border-radius:8px;padding:16px;border:1px solid #334155}}
.metric{{font-size:28px;color:#38bdf8;font-weight:bold}}
.lbl{{color:#64748b;font-size:12px;margin-top:4px}}</style></head>
<body><div class="hdr"><h1>OCI Spot Strategy V3</h1><span style="color:#64748b">Preemption risk optimizer | Port {PORT}</span></div>
<div class="grid">
<div class="card"><div class="metric">60/30/10</div><div class="lbl">Ash/Phx/Fra Mix %</div></div>
<div class="card"><div class="metric">2.1/wk</div><div class="lbl">Preemption Rate</div></div>
<div class="card"><div class="metric">98.7%</div><div class="lbl">Auto-Resume Success</div></div>
<div class="card"><div class="metric">8.4s</div><div class="lbl">Checkpoint Save Latency</div></div>
<div class="card" style="grid-column:span 4">
<div style="color:#94a3b8;font-size:12px;margin-bottom:8px">PREEMPTION RISK HEATMAP (region × hour)</div>
<svg width="500" height="185" viewBox="0 0 500 185">{h_labels}{r_labels}{cells}</svg>
</div></div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="OCI Spot Strategy V3")
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
