"""Fleet Health V3 — FastAPI port 8875"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8875

def build_html():
    # Fleet node health grid (uptime, error rates, sensor drift, maintenance)
    nodes = 10
    health = [round(random.uniform(0.5, 1.0) * math.sin(i / 3) + 1.5, 3) for i in range(nodes)]
    colors = ["#22c55e" if v > 1.8 else "#f59e0b" if v > 1.2 else "#C74634" for v in health]
    grid_rects = "".join(
        f'<rect x="{20 + (i % 5) * 80}" y="{20 + (i // 5) * 70}" width="60" height="50" rx="6" fill="{colors[i]}"/>'
        f'<text x="{50 + (i % 5) * 80}" y="{50 + (i // 5) * 70}" text-anchor="middle" fill="#0f172a" font-size="11">R{i+1}</text>'
        f'<text x="{50 + (i % 5) * 80}" y="{64 + (i // 5) * 70}" text-anchor="middle" fill="#0f172a" font-size="10">{health[i]}</text>'
        for i in range(nodes)
    )
    online = sum(1 for v in health if v > 1.8)
    degraded = sum(1 for v in health if 1.2 < v <= 1.8)
    critical = sum(1 for v in health if v <= 1.2)
    return f"""<!DOCTYPE html><html><head><title>Fleet Health V3</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui}}
h1{{color:#C74634}}h2{{color:#38bdf8}}.card{{background:#1e293b;padding:20px;margin:10px;border-radius:8px}}
.badge{{display:inline-block;padding:4px 10px;border-radius:4px;font-size:0.85em;margin-right:6px}}
.ok{{background:#14532d;color:#22c55e}}.warn{{background:#451a03;color:#f59e0b}}.err{{background:#450a0a;color:#C74634}}
.meta{{color:#94a3b8;font-size:0.9em;margin-top:8px}}</style></head>
<body><h1>Fleet Health V3</h1>
<div class="card"><h2>Robot Fleet Node Health Grid</h2>
<svg width="440" height="170">{grid_rects}</svg>
<p>
  <span class="badge ok">Online: {online}</span>
  <span class="badge warn">Degraded: {degraded}</span>
  <span class="badge err">Critical: {critical}</span>
  | Port: {PORT}
</p>
<p class="meta">Uptime tracking | Error rates | Sensor drift detection | Maintenance scheduling</p>
</div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Fleet Health V3")
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
