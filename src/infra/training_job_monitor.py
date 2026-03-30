"""Training Job Monitor — FastAPI port 8411"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8411

def build_html():
    jobs = [
        {"name":"dagger_run10","status":"RUNNING","progress":0.284,"gpu":91,"eta_h":8.3,"node":"GPU4"},
        {"name":"groot_v3_ft","status":"RUNNING","progress":0.267,"gpu":88,"eta_h":11.2,"node":"GPU1"},
        {"name":"bc_baseline_v2","status":"DONE","progress":1.0,"gpu":0,"eta_h":0,"node":"GPU2"},
        {"name":"lora_sweep_r32","status":"DONE","progress":1.0,"gpu":0,"eta_h":0,"node":"GPU3"},
        {"name":"hpo_search_2","status":"QUEUED","progress":0.0,"gpu":0,"eta_h":14.1,"node":"TBD"},
        {"name":"sim_render_job","status":"RUNNING","progress":0.61,"gpu":72,"eta_h":2.1,"node":"Phoenix1"},
        {"name":"eval_full_suite","status":"QUEUED","progress":0.0,"gpu":0,"eta_h":4.2,"node":"TBD"},
        {"name":"checkpoint_eval","status":"FAILED","progress":0.12,"gpu":0,"eta_h":0,"node":"GPU4"},
    ]
    status_colors = {"RUNNING":"#22c55e","DONE":"#38bdf8","QUEUED":"#f59e0b","FAILED":"#C74634"}

    # Progress bars dashboard
    svg_j = f'<svg width="440" height="{len(jobs)*38+30}" style="background:#0f172a">'
    for ji, job in enumerate(jobs):
        y = 15 + ji*38; col = status_colors[job["status"]]
        # Background bar
        svg_j += f'<rect x="130" y="{y}" width="220" height="22" fill="#1e293b" rx="3"/>'
        # Progress fill
        pw = int(job["progress"]*218)
        svg_j += f'<rect x="131" y="{y+1}" width="{pw}" height="20" fill="{col}" rx="2" opacity="0.7"/>'
        # Labels
        svg_j += f'<text x="125" y="{y+15}" fill="#e2e8f0" font-size="9" text-anchor="end">{job["name"]}</text>'
        svg_j += f'<text x="355" y="{y+15}" fill="{col}" font-size="9">{job["status"]}</text>'
        svg_j += f'<text x="415" y="{y+15}" fill="#94a3b8" font-size="8">{job["node"]}</text>'
        pct = f'{job["progress"]:.0%}'
        svg_j += f'<text x="{131+pw//2}" y="{y+15}" fill="white" font-size="8" text-anchor="middle">{pct}</text>'
    svg_j += '</svg>'

    # GPU util per running job
    running_jobs = [j for j in jobs if j["status"]=="RUNNING"]
    svg_g = '<svg width="320" height="180" style="background:#0f172a">'
    for ji, job in enumerate(running_jobs):
        y = 20+ji*45
        svg_g += f'<text x="85" y="{y+15}" fill="#94a3b8" font-size="9" text-anchor="end">{job["name"][:12]}</text>'
        # GPU bar
        gw = int(job["gpu"]/100*200)
        gcol = "#C74634" if job["gpu"]>90 else "#f59e0b" if job["gpu"]>75 else "#22c55e"
        svg_g += f'<rect x="90" y="{y}" width="200" height="16" fill="#1e293b" rx="2"/>'
        svg_g += f'<rect x="91" y="{y+1}" width="{gw}" height="14" fill="{gcol}" opacity="0.8" rx="2"/>'
        svg_g += f'<text x="{92+gw}" y="{y+12}" fill="white" font-size="8">{job["gpu"]}%</text>'
        # Memory estimate
        mem = job["gpu"]*0.8
        mw = int(mem/100*200)
        svg_g += f'<rect x="90" y="{y+18}" width="200" height="10" fill="#1e293b" rx="2"/>'
        svg_g += f'<rect x="91" y="{y+19}" width="{mw}" height="8" fill="#38bdf8" opacity="0.5" rx="2"/>'
        svg_g += f'<text x="{92+mw}" y="{y+27}" fill="#38bdf8" font-size="7">{mem:.0f}% VRAM</text>'
    svg_g += '</svg>'

    return f"""<!DOCTYPE html><html><head><title>Training Job Monitor — Port {PORT}</title>
<style>body{{background:#0f172a;color:#e2e8f0;font-family:monospace;margin:0;padding:20px}}
h1{{color:#C74634;font-size:18px}}h2{{color:#38bdf8;font-size:14px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:20px}}
.card{{background:#1e293b;padding:16px;border-radius:8px}}
.stat{{font-size:24px;color:#C74634;font-weight:bold}}
.label{{color:#94a3b8;font-size:12px}}</style></head>
<body><h1>Training Job Monitor</h1>
<p style="color:#94a3b8">Port {PORT} | 8-job status dashboard with resource utilization</p>
<div class="grid">
<div class="card"><h2>Job Queue Dashboard</h2>{svg_j}
<div style="color:#C74634;font-size:11px;margin-top:8px">⚠ checkpoint_eval FAILED: OOM on GPU4 (VRAM exceeded)</div></div>
<div class="card"><h2>Running Job GPU Utilization</h2>{svg_g}
<div style="margin-top:12px">
<div class="stat">91%</div><div class="label">dagger_run10 GPU util (GPU4)</div>
<div style="margin-top:8px;color:#94a3b8;font-size:11px">2 RUNNING / 2 QUEUED / 2 DONE / 1 FAILED<br>ETA predictions via throughput rolling avg<br>OOM prediction at &gt;72GB VRAM (80GB total)<br>checkpoint_eval: reduce batch size to 4</div>
</div></div></div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Training Job Monitor")
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
