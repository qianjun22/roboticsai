"""Observation Encoder Analyzer — FastAPI port 8552"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8552

def build_html():
    modalities = ["RGB", "Depth", "Proprioception", "Language", "Wrist Cam"]
    weights = [0.28, 0.39, 0.18, 0.06, 0.09]
    sr_deltas = ["+0.07", "+0.11", "+0.05", "+0.01", "+0.08"]
    colors = ["#38bdf8", "#22c55e", "#f59e0b", "#C74634", "#a78bfa"]
    bars = "".join(
        f'<rect x="150" y="{20+i*48}" width="{int(w*400)}" height="34" fill="{c}" rx="3"/>'
        f'<text x="145" y="{41+i*48}" fill="#94a3b8" font-size="11" text-anchor="end">{m}</text>'
        f'<text x="{155+int(w*400)}" y="{41+i*48}" fill="#e2e8f0" font-size="11">{w:.0%} ({d} SR)</text>'
        for i,(m,w,d,c) in enumerate(zip(modalities,weights,sr_deltas,colors))
    )
    return f"""<!DOCTYPE html><html><head><title>Observation Encoder Analyzer</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:monospace}}
.hdr{{background:#1e293b;padding:16px 24px;border-bottom:2px solid #C74634}}
h1{{margin:0;color:#C74634;font-size:20px}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;padding:24px}}
.card{{background:#1e293b;border-radius:8px;padding:16px;border:1px solid #334155}}
.metric{{font-size:28px;color:#38bdf8;font-weight:bold}}
.lbl{{color:#64748b;font-size:12px;margin-top:4px}}</style></head>
<body><div class="hdr"><h1>Observation Encoder Analyzer</h1><span style="color:#64748b">Feature importance | Port {PORT}</span></div>
<div class="grid">
<div class="card"><div class="metric">Depth</div><div class="lbl">Most Important (+0.11pp)</div></div>
<div class="card"><div class="metric">Language</div><div class="lbl">Most Underutilized (6%)</div></div>
<div class="card"><div class="metric">Wrist</div><div class="lbl">Critical for Grasp</div></div>
<div class="card"><div class="metric">5</div><div class="lbl">Input Modalities</div></div>
<div class="card" style="grid-column:span 4">
<div style="color:#94a3b8;font-size:12px;margin-bottom:8px">MODALITY WEIGHT & SR CONTRIBUTION</div>
<svg width="100%" height="{20+len(modalities)*48+10}" viewBox="0 660 {20+len(modalities)*48+10}">{bars}</svg>
</div></div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Observation Encoder Analyzer")
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
