"""Revenue Growth Tracker — FastAPI port 8519"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8519

def build_html():
    months = ["Oct","Nov","Dec","Jan","Feb","Mar"]
    rev = [0, 0, 2400, 4800, 8200, 14500]
    pts = " ".join(f"{50+i*80},{190-int(r/100)}" for i, r in enumerate(rev))
    dots = "".join(f'<circle cx="{50+i*80}" cy="{190-int(r/100)}" r="4" fill="#C74634"/><text x="{50+i*80}" y="{185-int(r/100)-8}" fill="#94a3b8" font-size="9" text-anchor="middle">${r:,}</text>' for i, r in enumerate(rev))
    return f"""<!DOCTYPE html><html><head><title>Revenue Growth Tracker</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:monospace}}
.hdr{{background:#1e293b;padding:16px 24px;border-bottom:2px solid #C74634}}
h1{{margin:0;color:#C74634;font-size:20px}}
.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;padding:24px}}
.card{{background:#1e293b;border-radius:8px;padding:16px;border:1px solid #334155}}
.metric{{font-size:28px;color:#38bdf8;font-weight:bold}}
.lbl{{color:#64748b;font-size:12px;margin-top:4px}}</style></head>
<body><div class="hdr"><h1>Revenue Growth Tracker</h1><span style="color:#64748b">OCI Robot Cloud ARR | Port {PORT}</span></div>
<div class="grid">
<div class="card"><div class="metric">$14.5K</div><div class="lbl">Mar MRR</div></div>
<div class="card"><div class="metric">$174K</div><div class="lbl">ARR Run Rate</div></div>
<div class="card"><div class="metric">77%</div><div class="lbl">MoM Growth</div></div>
<div class="card" style="grid-column:span 3">
<div style="color:#94a3b8;font-size:12px;margin-bottom:8px">MONTHLY RECURRING REVENUE TREND</div>
<svg width="100%" height="220" viewBox="0 0 530 220">
<polyline points="{pts}" fill="none" stroke="#38bdf8" stroke-width="2"/>
{dots}
<line x1="10" y1="195" x2="520" y2="195" stroke="#334155" stroke-width="1"/>
</svg></div></div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Revenue Growth Tracker")
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
