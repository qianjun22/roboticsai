"""Sim Asset Manager — FastAPI port 8901"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8901

def build_html():
    data = [round(random.uniform(0.5, 1.0) * math.sin(i/3) + 1.5, 3) for i in range(10)]
    bars = "".join(f'<rect x="{30+i*40}" y="{150-int(v*60)}" width="30" height="{int(v*60)}" fill="#C74634"/>' for i, v in enumerate(data))
    assets = [
        ("Red Cube",       94, "#C74634"),
        ("Blue Bottle",    71, "#38bdf8"),
        ("Green Cylinder", 58, "#4ade80"),
        ("Yellow Tray",    45, "#facc15"),
        ("Grey Block",     33, "#94a3b8"),
        ("Orange Cone",    27, "#fb923c"),
    ]
    heatmap_bars = "".join(
        f'<rect x="20" y="{10+i*28}" width="{int(pct*3)}" height="20" fill="{c}"/>'
        f'<text x="{25+int(pct*3)}" y="{25+i*28}" fill="#e2e8f0" font-size="11">{name} {pct}%</text>'
        for i, (name, pct, c) in enumerate(assets)
    )
    diversity = [
        ("v1", 12, "#94a3b8"),
        ("v1.5", 24, "#38bdf8"),
        ("v2", 48, "#C74634"),
    ]
    div_bars = "".join(
        f'<rect x="{40+i*120}" y="{160-int(n*2.5)}" width="60" height="{int(n*2.5)}" fill="{c}"/>'
        f'<text x="{45+i*120}" y="{175}" fill="#e2e8f0" font-size="11">{lbl}: {n}</text>'
        for i, (lbl, n, c) in enumerate(diversity)
    )
    return f"""<!DOCTYPE html><html><head><title>Sim Asset Manager</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui}}
h1{{color:#C74634}}h2{{color:#38bdf8}}.card{{background:#1e293b;padding:20px;margin:10px;border-radius:8px}}</style></head>
<body><h1>Sim Asset Manager</h1>
<div class="card"><h2>Isaac Sim Asset Library</h2>
<p>48 objects &nbsp;|&nbsp; 12 robot configs &nbsp;|&nbsp; 8 scenes</p>
</div>
<div class="card"><h2>Asset Usage Heatmap</h2>
<svg width="450" height="180">{heatmap_bars}</svg>
</div>
<div class="card"><h2>Asset Diversity Score (objects in library)</h2>
<svg width="450" height="190">{div_bars}</svg>
<p>v1 → v2: 12 → 48 objects (4× diversity improvement)</p>
</div>
<div class="card"><h2>Throughput Metrics</h2>
<svg width="450" height="180">{bars}</svg>
<p>Current value: {data[-1]} | Peak: {max(data)} | Port: {PORT}</p>
</div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Sim Asset Manager")
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
