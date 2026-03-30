"""Training Throughput Optimizer V2 — FastAPI port 8876"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8876

# Throughput data: FP16 mixed precision + gradient accumulation + multi-GPU scaling
# Simulated sweep from single-GPU baseline (2.35 it/s) to 8xA100 optimized (4.1 it/s)
THROUGHPUT_CONFIGS = [
    {"label": "Baseline", "itps": 2.35, "gpus": 1, "batch": 8, "fp16": False},
    {"label": "FP16",     "itps": 2.81, "gpus": 1, "batch": 8, "fp16": True},
    {"label": "GradAcc2", "itps": 3.04, "gpus": 1, "batch": 16, "fp16": True},
    {"label": "GradAcc4", "itps": 3.22, "gpus": 1, "batch": 32, "fp16": True},
    {"label": "2xGPU",    "itps": 3.55, "gpus": 2, "batch": 32, "fp16": True},
    {"label": "4xGPU",    "itps": 3.78, "gpus": 4, "batch": 64, "fp16": True},
    {"label": "8xGPU",    "itps": 3.97, "gpus": 8, "batch": 128, "fp16": True},
    {"label": "Optimized","itps": 4.10, "gpus": 8, "batch": 256, "fp16": True},
]

BATCH_SWEEP = [8, 16, 32, 64, 128, 256, 512]
BATCH_ITPS  = [2.35, 2.61, 2.88, 3.14, 3.55, 3.97, 3.89]  # drops at 512 due to memory pressure

def build_html():
    # Throughput bar chart
    max_tp = max(c["itps"] for c in THROUGHPUT_CONFIGS)
    bars = "".join(
        f'<rect x="{20+i*52}" y="{160-int(c["itps"]/max_tp*130)}" width="38" '
        f'height="{int(c["itps"]/max_tp*130)}" fill="#C74634"/>'
        f'<text x="{39+i*52}" y="175" text-anchor="middle" fill="#94a3b8" font-size="9">{c["label"]}</text>'
        f'<text x="{39+i*52}" y="{155-int(c["itps"]/max_tp*130)}" text-anchor="middle" fill="#e2e8f0" font-size="9">{c["itps"]}</text>'
        for i, c in enumerate(THROUGHPUT_CONFIGS)
    )
    # Batch sweep line chart
    pts = " ".join(
        f"{20+i*55},{160-int(v/max(BATCH_ITPS)*130)}"
        for i, v in enumerate(BATCH_ITPS)
    )
    batch_labels = "".join(
        f'<text x="{20+i*55}" y="175" text-anchor="middle" fill="#94a3b8" font-size="9">{b}</text>'
        for i, b in enumerate(BATCH_SWEEP)
    )
    rows = "".join(
        f"<tr><td>{c['label']}</td><td>{c['itps']}</td><td>{c['gpus']}</td>"
        f"<td>{c['batch']}</td><td>{'Yes' if c['fp16'] else 'No'}</td></tr>"
        for c in THROUGHPUT_CONFIGS
    )
    return f"""<!DOCTYPE html><html><head><title>Training Throughput Optimizer V2</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui;padding:20px}}
h1{{color:#C74634}}h2{{color:#38bdf8}}.card{{background:#1e293b;padding:20px;margin:10px;border-radius:8px}}
table{{border-collapse:collapse;width:100%}}th,td{{padding:6px 12px;text-align:left;border-bottom:1px solid #334155}}
th{{color:#38bdf8}}.badge{{background:#C74634;color:#fff;padding:2px 8px;border-radius:4px;font-size:12px}}</style></head>
<body><h1>Training Throughput Optimizer V2</h1>
<p>GR00T fine-tuning throughput optimization: FP16 mixed precision, gradient accumulation, multi-GPU DDP scaling.</p>
<div class="card"><h2>Throughput by Configuration (it/s)</h2>
<svg width="450" height="185">{bars}</svg>
<p>Baseline: <span class="badge">2.35 it/s</span> &rarr; Optimized: <span class="badge">4.10 it/s</span> &nbsp;|&nbsp; <strong>1.74&times; speedup</strong> &nbsp;|&nbsp; Port: {PORT}</p>
</div>
<div class="card"><h2>Batch Size Sweep (8xA100, FP16)</h2>
<svg width="380" height="185">
  <polyline points="{pts}" fill="none" stroke="#38bdf8" stroke-width="2"/>
  {batch_labels}
</svg>
<p>Optimal batch size: <span class="badge">256</span> — beyond 256 memory pressure reduces throughput.</p>
</div>
<div class="card"><h2>Configuration Table</h2>
<table><tr><th>Config</th><th>it/s</th><th>GPUs</th><th>Batch</th><th>FP16</th></tr>{rows}</table>
</div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Training Throughput Optimizer V2")
    @app.get("/", response_class=HTMLResponse)
    def index(): return build_html()
    @app.get("/health")
    def health(): return {"status": "ok", "port": PORT}
    @app.get("/metrics")
    def metrics(): return {"configs": THROUGHPUT_CONFIGS, "batch_sweep": dict(zip(BATCH_SWEEP, BATCH_ITPS))}

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
