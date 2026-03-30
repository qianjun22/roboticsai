"""Inference Cost Attribution V2 — FastAPI port 8583"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8583

def build_html():
    months = ["Oct","Nov","Dec","Jan","Feb","Mar"]
    cost_per_inf = [0.0021, 0.0019, 0.0018, 0.0017, 0.0016, 0.0015]
    pts = " ".join(f"{30+i*80},{190-int(v*80000)}" for i,v in enumerate(cost_per_inf))
    dots = "".join(f'<circle cx="{30+i*80}" cy="{190-int(v*80000)}" r="4" fill="#38bdf8"/><text x="{30+i*80}" y="{185-int(v*80000)-8}" fill="#94a3b8" font-size="9" text-anchor="middle">${v:.4f}</text>' for i,v in enumerate(cost_per_inf))
    xlabels = "".join(f'<text x="{30+i*80}" y="208" fill="#64748b" font-size="9" text-anchor="middle">{m}</text>' for i,m in enumerate(months))
    components = [("GPU Compute", 68, "#C74634"), ("Network", 12, "#38bdf8"), ("Storage", 11, "#22c55e"), ("Support", 9, "#f59e0b")]
    bars = "".join(f'<rect x="{20+i*130}" y="{160-c[1]}" width="100" height="{c[1]}" fill="{c[2]}" rx="3"/><text x="{70+i*130}" y="{155-c[1]}" fill="#94a3b8" font-size="10" text-anchor="middle">{c[1]}%</text><text x="{70+i*130}" y="178" fill="#64748b" font-size="9" text-anchor="middle">{c[0].split(" ")[0]}</text>' for i,c in enumerate(components))
    return f"""<!DOCTYPE html><html><head><title>Inference Cost Attribution V2</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:monospace}}
.hdr{{background:#1e293b;padding:16px 24px;border-bottom:2px solid #C74634}}
h1{{margin:0;color:#C74634;font-size:20px}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;padding:24px}}
.card{{background:#1e293b;border-radius:8px;padding:16px;border:1px solid #334155}}
.metric{{font-size:28px;color:#38bdf8;font-weight:bold}}
.lbl{{color:#64748b;font-size:12px;margin-top:4px}}</style></head>
<body><div class="hdr"><h1>Inference Cost Attribution V2</h1><span style="color:#64748b">Cost per inference trend | Port {PORT}</span></div>
<div class="grid">
<div class="card"><div class="metric">$0.0015</div><div class="lbl">Current Cost/Inference</div></div>
<div class="card"><div class="metric">71%</div><div class="lbl">Gross Margin</div></div>
<div class="card"><div class="metric">$0.0008</div><div class="lbl">Target at 10× Volume</div></div>
<div class="card"><div class="metric">68%</div><div class="lbl">GPU Compute Share</div></div>
<div class="card" style="grid-column:span 2">
<div style="color:#94a3b8;font-size:11px;margin-bottom:6px">COST/INFERENCE TREND</div>
<svg width="100%" height="225" viewBox="0 0 510 225">
<polyline points="{pts}" fill="none" stroke="#38bdf8" stroke-width="2"/>
{dots}{xlabels}
<line x1="10" y1="195" x2="500" y2="195" stroke="#334155" stroke-width="1"/>
</svg></div>
<div class="card" style="grid-column:span 2">
<div style="color:#94a3b8;font-size:11px;margin-bottom:6px">COST BREAKDOWN %</div>
<svg width="100%" height="200" viewBox="0 0 560 200">{bars}
<line x1="10" y1="162" x2="550" y2="162" stroke="#334155" stroke-width="1"/>
</svg></div>
</div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Inference Cost Attribution V2")
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
