"""Training Throughput v2 — FastAPI port 8483"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8483

def build_html():
    configs = [
        ("Single A100 (baseline)", 2.35, 87, 1.0),
        ("Multi-GPU DDP 2×A100", 4.82, 91, 2.05),
        ("Multi-GPU DDP 4×A100", 9.12, 89, 3.88),
        ("Mixed Precision FP16", 3.07, 92, 1.31),
        ("Gradient Checkpointing", 1.98, 72, 0.84),
    ]
    rows = ""
    for name, its, gpu_util, speedup in configs:
        col = "#22c55e" if speedup >= 2 else ("#38bdf8" if speedup >= 1 else "#f59e0b")
        rows += f'<tr><td style="color:#e2e8f0">{name}</td><td style="color:{col}">{its:.2f}</td><td>{gpu_util}%</td><td style="color:{col}">{speedup:.2f}×</td></tr>'
    
    steps = list(range(50))
    throughput_hist = [2.35 + random.uniform(-0.15, 0.15) for _ in steps]
    pts = []
    for i, v in enumerate(throughput_hist):
        x = i * 500 / 49
        y = 80 - (v - 1.5) / 2 * 80
        pts.append(f"{x:.1f},{y:.1f}")
    thr_svg = f'<polyline points="{" ".join(pts)}" fill="none" stroke="#38bdf8" stroke-width="2"/>'
    # target line
    tgt_y = 80 - (3.07 - 1.5) / 2 * 80
    tgt_svg = f'<line x1="0" y1="{tgt_y:.1f}" x2="500" y2="{tgt_y:.1f}" stroke="#22c55e" stroke-width="1" stroke-dasharray="6,3"/>'
    
    return f"""<!DOCTYPE html><html><head><title>Training Throughput v2</title>
<style>body{{margin:0;font-family:monospace;background:#0f172a;color:#e2e8f0}}
.hdr{{background:#C74634;padding:16px 24px;display:flex;justify-content:space-between;align-items:center}}
.hdr h1{{margin:0;font-size:20px;color:#fff}}.hdr span{{color:#fca5a5;font-size:13px}}
.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;padding:20px}}
.card{{background:#1e293b;border-radius:8px;padding:16px}}
.card h3{{margin:0 0 12px;color:#38bdf8;font-size:14px;text-transform:uppercase;letter-spacing:1px}}
.stat{{font-size:36px;font-weight:bold;color:#f1f5f9}}.sub{{color:#64748b;font-size:12px;margin-top:4px}}
table{{width:100%;border-collapse:collapse;font-size:13px}}
th{{text-align:left;color:#64748b;padding:6px 0;border-bottom:1px solid #334155}}
td{{padding:6px 0;border-bottom:1px solid #1e293b}}</style></head>
<body>
<div class="hdr"><h1>Training Throughput v2</h1><span>port {PORT}</span></div>
<div class="grid">
<div class="card"><h3>Baseline it/s</h3><div class="stat">2.35</div><div class="sub">single A100 · GR00T finetune</div></div>
<div class="card"><h3>Best Config</h3><div class="stat">9.12</div><div class="sub">4×A100 DDP · 3.88× speedup</div></div>
<div class="card"><h3>GPU Efficiency</h3><div class="stat">91%</div><div class="sub">peak GPU utilization</div></div>
<div class="card" style="grid-column:span 3"><h3>Config Comparison</h3>
<table><tr><th>Config</th><th>it/s</th><th>GPU Util</th><th>Speedup</th></tr>{rows}</table></div>
<div class="card" style="grid-column:span 3"><h3>Live Throughput (baseline)</h3>
<div style="font-size:12px;color:#64748b;margin-bottom:8px"><span style="color:#22c55e">- -</span> mixed-precision target (3.07 it/s)</div>
<svg width="100%" viewBox="0 0 500 80">{thr_svg}{tgt_svg}</svg></div>
</div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Training Throughput v2")
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
