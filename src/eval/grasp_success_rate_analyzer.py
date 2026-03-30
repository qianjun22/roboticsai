"""Grasp Success Rate Analyzer — FastAPI port 8588"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8588

def build_html():
    mass_vals = [0.2, 0.5, 0.8, 1.2, 1.5, 1.8]
    sr_by_mass = [0.78, 0.74, 0.71, 0.67, 0.63, 0.61]
    pts = " ".join(f"{30+i*80},{170-int(v*170)}" for i,v in enumerate(sr_by_mass))
    dots = "".join(f'<circle cx="{30+i*80}" cy="{170-int(v*170)}" r="5" fill="#38bdf8"/><text x="{30+i*80}" y="{165-int(v*170)-8}" fill="#94a3b8" font-size="9" text-anchor="middle">{v}</text>' for i,v in enumerate(sr_by_mass))
    xlabels = "".join(f'<text x="{30+i*80}" y="188" fill="#64748b" font-size="9" text-anchor="middle">{m}kg</text>' for i,m in enumerate(mass_vals))
    return f"""<!DOCTYPE html><html><head><title>Grasp Success Rate Analyzer</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:monospace}}
.hdr{{background:#1e293b;padding:16px 24px;border-bottom:2px solid #C74634}}
h1{{margin:0;color:#C74634;font-size:20px}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;padding:24px}}
.card{{background:#1e293b;border-radius:8px;padding:16px;border:1px solid #334155}}
.metric{{font-size:28px;color:#38bdf8;font-weight:bold}}
.lbl{{color:#64748b;font-size:12px;margin-top:4px}}</style></head>
<body><div class="hdr"><h1>Grasp Success Rate Analyzer</h1><span style="color:#64748b">Object property vs SR | Port {PORT}</span></div>
<div class="grid">
<div class="card"><div class="metric">0.78</div><div class="lbl">SR at 0.2kg</div></div>
<div class="card"><div class="metric">0.61</div><div class="lbl">SR at 1.8kg (hardest)</div></div>
<div class="card"><div class="metric">0.72</div><div class="lbl">Friction Correlation ρ</div></div>
<div class="card"><div class="metric">47%</div><div class="lbl">Failures from Angle>15°</div></div>
<div class="card" style="grid-column:span 4">
<div style="color:#94a3b8;font-size:12px;margin-bottom:8px">SR vs OBJECT MASS</div>
<svg width="100%" height="210" viewBox="0 0 510 210">
<polyline points="{pts}" fill="none" stroke="#38bdf8" stroke-width="2"/>
{dots}{xlabels}
<line x1="10" y1="174" x2="500" y2="174" stroke="#334155" stroke-width="1"/>
</svg></div></div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Grasp Success Rate Analyzer")
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
