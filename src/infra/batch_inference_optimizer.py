"""Batch Inference Optimizer — FastAPI port 8514"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8514

def build_html():
    batch_sizes = [1, 2, 4, 8, 16, 32]
    throughput = [280, 540, 980, 1840, 2640, 3120]
    latency_p50 = [226, 231, 238, 248, 271, 312]
    gpu_util = [41, 58, 72, 87, 92, 94]
    
    # throughput vs batch size line SVG
    thr_pts = []
    lat_pts = []
    for i, (bs, thr, lat) in enumerate(zip(batch_sizes, throughput, latency_p50)):
        x = i * 88 + 10
        y_thr = 80 - thr / 3200 * 80
        y_lat = 80 - (lat - 200) / 130 * 80
        thr_pts.append(f"{x:.0f},{y_thr:.1f}")
        lat_pts.append(f"{x:.0f},{y_lat:.1f}")
    
    thr_svg = f'<polyline points="{" ".join(thr_pts)}" fill="none" stroke="#22c55e" stroke-width="2"/>'
    lat_svg = f'<polyline points="{" ".join(lat_pts)}" fill="none" stroke="#ef4444" stroke-width="2" stroke-dasharray="5,3"/>'
    
    # optimal marker at batch=8
    opt_x = 3 * 88 + 10
    opt_svg = f'<line x1="{opt_x}" y1="0" x2="{opt_x}" y2="80" stroke="#C74634" stroke-width="1.5" stroke-dasharray="4,2"/>'
    
    labels = "".join([f'<text x="{i*88+10:.0f}" y="92" text-anchor="middle" fill="#64748b" font-size="9">bs={bs}</text>' for i,bs in enumerate(batch_sizes)])
    legend_thr = f'<span style="color:#22c55e">— throughput (req/hr)</span>'
    legend_lat = f'<span style="color:#ef4444;margin-left:12px">- - latency p50 (ms)</span>'
    
    # dynamic batching algorithm visualization
    alg_steps = [
        ("Incoming request", "#38bdf8"),
        ("Add to queue", "#38bdf8"),
        ("Batch window (20ms timeout)", "#f59e0b"),
        ("Batch size=8 reached?", "#f59e0b"),
        ("Build batch", "#22c55e"),
        ("Run inference", "#22c55e"),
        ("Return responses", "#22c55e"),
    ]
    alg_svg = ""
    for i, (step, col) in enumerate(alg_steps):
        x = i * 68 + 5
        alg_svg += f'<rect x="{x}" y="10" width="60" height="20" fill="{col}" opacity="0.7" rx="3"/>'
        alg_svg += f'<text x="{x+30}" y="24" text-anchor="middle" fill="white" font-size="7">{step[:8]}</text>'
        if i < len(alg_steps) - 1:
            alg_svg += f'<polygon points="{x+62},20 {x+68},15 {x+68},25" fill="{col}" opacity="0.7"/>'
    
    # GPU util comparison
    rows = ""
    for bs, thr, lat, util in zip(batch_sizes, throughput, latency_p50, gpu_util):
        highlight = " style='background:#1e3a5f'" if bs == 8 else ""
        rows += f'<tr{highlight}><td>bs={bs}</td><td>{thr:,}</td><td>{lat}ms</td><td>{util}%</td></tr>'
    
    return f"""<!DOCTYPE html><html><head><title>Batch Inference Optimizer</title>
<style>body{{margin:0;font-family:monospace;background:#0f172a;color:#e2e8f0}}
.hdr{{background:#C74634;padding:16px 24px;display:flex;justify-content:space-between;align-items:center}}
.hdr h1{{margin:0;font-size:20px;color:#fff}}.hdr span{{color:#fca5a5;font-size:13px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;padding:20px}}
.card{{background:#1e293b;border-radius:8px;padding:16px}}
.card h3{{margin:0 0 12px;color:#38bdf8;font-size:14px;text-transform:uppercase;letter-spacing:1px}}
.stat{{font-size:36px;font-weight:bold;color:#f1f5f9}}.sub{{color:#64748b;font-size:12px;margin-top:4px}}
table{{width:100%;border-collapse:collapse;font-size:12px}}
th{{text-align:left;color:#64748b;padding:6px 0;border-bottom:1px solid #334155}}
td{{padding:6px 0;border-bottom:1px solid #1e293b}}</style></head>
<body>
<div class="hdr"><h1>Batch Inference Optimizer</h1><span>port {PORT}</span></div>
<div class="grid">
<div class="card"><h3>Optimal Batch Size</h3><div class="stat">bs=8</div><div class="sub">3,200 req/hr · 226ms p50</div></div>
<div class="card"><h3>GPU Waste Eliminated</h3><div class="stat">41%</div><div class="sub">single-request idle GPU utilization</div></div>
<div class="card" style="grid-column:span 2"><h3>Throughput vs Latency (batch size 1–32)</h3>
<div style="font-size:11px;margin-bottom:8px">{legend_thr} {legend_lat} <span style="color:#C74634;margin-left:8px">| optimal bs=8</span></div>
<svg width="100%" viewBox="0 0 450 95">{thr_svg}{lat_svg}{opt_svg}{labels}</svg></div>
<div class="card"><h3>Batch Config Table</h3>
<table><tr><th>Batch</th><th>req/hr</th><th>p50</th><th>GPU%</th></tr>{rows}</table></div>
<div class="card"><h3>Dynamic Batching Algorithm</h3>
<svg width="100%" viewBox="0 0 475 35">{alg_svg}</svg>
<div style="font-size:11px;color:#64748b;margin-top:8px">Triggers: 20ms timeout OR batch=8 — whichever first</div></div>
</div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Batch Inference Optimizer")
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
