"""OCI GPU Broker — FastAPI port 8481"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8481

def build_html():
    allocations = [
        ("Training: dagger_run10", "A100-GPU4", 78, "active", "#22c55e"),
        ("Training: groot_finetune_v3", "A100-GPU4", 85, "active", "#22c55e"),
        ("Inference: prod-8001", "A100-GPU4", 42, "serving", "#38bdf8"),
        ("Eval: eval-runner", "A100 Phoenix", 55, "active", "#f59e0b"),
        ("Staging: groot_finetune_v2", "A100 Frankfurt", 31, "idle", "#94a3b8"),
    ]
    rows = ""
    for job, gpu, util, status, col in allocations:
        status_bg = {"active": "#22c55e", "serving": "#38bdf8", "idle": "#94a3b8"}[status]
        rows += f'''<tr>
<td style="color:#e2e8f0">{job}</td>
<td style="color:#94a3b8">{gpu}</td>
<td><div style="background:#334155;border-radius:3px;height:6px;width:80px;display:inline-block">
<div style="background:{col};width:{util}%;height:6px;border-radius:3px"></div></div> {util}%</td>
<td><span style="background:{status_bg};color:#0f172a;padding:1px 6px;border-radius:4px;font-size:11px">{status}</span></td>
</tr>'''
    
    avail_h = [max(0, 4 - int(3*abs(math.sin(i*0.5)))) for i in range(24)]
    pts = []
    for i, v in enumerate(avail_h):
        x = i * 500 / 23
        y = 60 - v * 15
        pts.append(f"{x:.1f},{y:.1f}")
    avail_svg = f'<polyline points="{" ".join(pts)}" fill="none" stroke="#38bdf8" stroke-width="2"/>'
    area_pts = "0,60 " + " ".join(pts) + " 500,60"
    area_svg = f'<polygon points="{area_pts}" fill="#38bdf8" fill-opacity="0.1"/>'
    
    total_util = sum(a[2] for a in allocations) / len(allocations)
    active_jobs = sum(1 for a in allocations if a[3] == "active")
    
    return f"""<!DOCTYPE html><html><head><title>OCI GPU Broker</title>
<style>body{{margin:0;font-family:monospace;background:#0f172a;color:#e2e8f0}}
.hdr{{background:#C74634;padding:16px 24px;display:flex;justify-content:space-between;align-items:center}}
.hdr h1{{margin:0;font-size:20px;color:#fff}}.hdr span{{color:#fca5a5;font-size:13px}}
.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;padding:20px}}
.card{{background:#1e293b;border-radius:8px;padding:16px}}
.card h3{{margin:0 0 12px;color:#38bdf8;font-size:14px;text-transform:uppercase;letter-spacing:1px}}
.stat{{font-size:36px;font-weight:bold;color:#f1f5f9}}.sub{{color:#64748b;font-size:12px;margin-top:4px}}
table{{width:100%;border-collapse:collapse;font-size:13px}}
th{{text-align:left;color:#64748b;padding:6px 0;border-bottom:1px solid #334155}}
td{{padding:8px 4px;border-bottom:1px solid #1e293b}}</style></head>
<body>
<div class="hdr"><h1>OCI GPU Broker</h1><span>port {PORT} · 4-GPU fleet</span></div>
<div class="grid">
<div class="card"><h3>Fleet Utilization</h3><div class="stat">{total_util:.0f}%</div><div class="sub">avg across all A100s</div></div>
<div class="card"><h3>Active Jobs</h3><div class="stat">{active_jobs}</div><div class="sub">training + eval running</div></div>
<div class="card"><h3>GPU Cost/hr</h3><div class="stat">$8.40</div><div class="sub">OCI A100 · 9.6× vs AWS</div></div>
<div class="card" style="grid-column:span 3"><h3>Job Allocations</h3>
<table><tr><th>Job</th><th>GPU</th><th>Utilization</th><th>Status</th></tr>{rows}</table></div>
<div class="card" style="grid-column:span 3"><h3>Available GPU-Hours (24h)</h3>
<svg width="100%" viewBox="0 0 500 60">{area_svg}{avail_svg}</svg></div>
</div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="OCI GPU Broker")
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
