"""Sim Fidelity V3 — FastAPI port 8874"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8874

def build_html():
    # Fidelity scores over episodes (sim-to-real transfer, domain randomization, render quality)
    scores = [round(random.uniform(0.7, 1.0) * math.sin(i / 3) + 1.3, 3) for i in range(10)]
    # SVG line chart
    points = " ".join(f"{45 + i * 40},{150 - int(scores[i] * 70)}" for i in range(10))
    dots = "".join(f'<circle cx="{45 + i * 40}" cy="{150 - int(scores[i] * 70)}" r="5" fill="#C74634"/>' for i in range(10))
    return f"""<!DOCTYPE html><html><head><title>Sim Fidelity V3</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui}}
h1{{color:#C74634}}h2{{color:#38bdf8}}.card{{background:#1e293b;padding:20px;margin:10px;border-radius:8px}}
.meta{{color:#94a3b8;font-size:0.9em;margin-top:8px}}</style></head>
<body><h1>Sim Fidelity V3</h1>
<div class="card"><h2>Sim-to-Real Transfer Fidelity</h2>
<svg width="450" height="180">
  <polyline points="{points}" fill="none" stroke="#C74634" stroke-width="2"/>
  {dots}
  <text x="10" y="170" fill="#94a3b8" font-size="12">Episodes</text>
  <text x="10" y="20" fill="#94a3b8" font-size="12">Fidelity</text>
</svg>
<p>Latest fidelity score: {scores[-1]} | Peak: {max(scores)} | Port: {PORT}</p>
<p class="meta">Domain randomization coverage | Render quality metrics | Transfer fidelity tracking</p>
</div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Sim Fidelity V3")
    @app.get("/", response_class=HTMLResponse)
    def index(): return build_html()
    @app.get("/health")
    def health(): return {"status": "ok", "port": PORT}

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(build_html().encode())
    def log_message(self, *a): pass

if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
