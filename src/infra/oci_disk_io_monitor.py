"""OCI Disk I/O Monitor — FastAPI port 8560"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8560

def build_html():
    hours = list(range(0, 24, 2))
    read_iops = [random.randint(8000, 45000) for _ in hours]
    write_iops = [random.randint(2000, 18000) for _ in hours]
    max_iops = max(read_iops + write_iops)
    pts_r = " ".join(f"{20+i*46},{180-int(v/max_iops*150)}" for i,v in enumerate(read_iops))
    pts_w = " ".join(f"{20+i*46},{180-int(v/max_iops*150)}" for i,v in enumerate(write_iops))
    xlabels = "".join(f'<text x="{20+i*46}" y="196" fill="#64748b" font-size="9" text-anchor="middle">{h:02d}h</text>' for i,h in enumerate(hours))
    return f"""<!DOCTYPE html><html><head><title>OCI Disk I/O Monitor</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:monospace}}
.hdr{{background:#1e293b;padding:16px 24px;border-bottom:2px solid #C74634}}
h1{{margin:0;color:#C74634;font-size:20px}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;padding:24px}}
.card{{background:#1e293b;border-radius:8px;padding:16px;border:1px solid #334155}}
.metric{{font-size:28px;color:#38bdf8;font-weight:bold}}
.lbl{{color:#64748b;font-size:12px;margin-top:4px}}</style></head>
<body><div class="hdr"><h1>OCI Disk I/O Monitor</h1><span style="color:#64748b">NVMe volume IOPS | Port {PORT}</span></div>
<div class="grid">
<div class="card"><div class="metric">1.2GB/s</div><div class="lbl">Demo Data Read</div></div>
<div class="card"><div class="metric">4.8GB/s</div><div class="lbl">Checkpoint Write Burst</div></div>
<div class="card"><div class="metric">18%</div><div class="lbl">I/O Bottleneck of Step</div></div>
<div class="card"><div class="metric">QD=32</div><div class="lbl">Saturation Depth</div></div>
<div class="card" style="grid-column:span 4">
<div style="color:#94a3b8;font-size:12px;margin-bottom:8px">IOPS 24H — <span style="color:#38bdf8">&#9632; Read</span> <span style="color:#C74634">&#9632; Write</span></div>
<svg width="100%" height="210" viewBox="0 0 560 210">
<polyline points="{pts_r}" fill="none" stroke="#38bdf8" stroke-width="2"/>
<polyline points="{pts_w}" fill="none" stroke="#C74634" stroke-width="2"/>
{xlabels}
<line x1="10" y1="183" x2="550" y2="183" stroke="#334155" stroke-width="1"/>
</svg></div></div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="OCI Disk I/O Monitor")
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
