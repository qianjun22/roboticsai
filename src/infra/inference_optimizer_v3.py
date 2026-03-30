"""Inference Optimizer V3 — FastAPI port 8871"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8871

def build_html():
    # Generate throughput and latency metrics
    requests_per_sec = [round(80 + 40 * math.sin(i / 2.5) + random.uniform(-5, 5), 1) for i in range(10)]
    p99_latency_ms = [round(max(10, 120 - 50 * math.sin(i / 2.5) + random.uniform(-8, 8)), 1) for i in range(10)]
    batch_efficiency = [round(min(0.99, 0.60 + i * 0.04 + random.uniform(-0.02, 0.02)), 3) for i in range(10)]

    throughput_bars = "".join(
        f'<rect x="{30+i*40}" y="{150-int((v/160)*120)}" width="14" height="{int((v/160)*120)}" fill="#C74634"/>'
        for i, v in enumerate(requests_per_sec)
    )
    latency_bars = "".join(
        f'<rect x="{44+i*40}" y="{150-int((v/160)*120)}" width="14" height="{int((v/160)*120)}" fill="#38bdf8"/>'
        for i, v in enumerate(p99_latency_ms)
    )

    return f"""<!DOCTYPE html><html><head><title>Inference Optimizer V3</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui}}
h1{{color:#C74634}}h2{{color:#38bdf8}}.card{{background:#1e293b;padding:20px;margin:10px;border-radius:8px}}
.metric{{display:inline-block;margin:8px 16px;text-align:center}}.metric span{{display:block;font-size:1.6em;font-weight:bold;color:#C74634}}</style></head>
<body><h1>Inference Optimizer V3</h1>
<p style="padding:0 10px;color:#94a3b8">Optimizing inference throughput and latency — dynamic batching, kernel fusion, and request scheduling for maximum efficiency.</p>
<div class="card"><h2>Throughput (req/s) &amp; P99 Latency (ms) — last 10 intervals</h2>
<svg width="450" height="180">{throughput_bars}{latency_bars}
<text x="30" y="170" fill="#C74634" font-size="11">Req/s</text>
<text x="80" y="170" fill="#38bdf8" font-size="11">P99 ms</text>
</svg>
<p>Requests/sec: {requests_per_sec[-1]} | P99 Latency: {p99_latency_ms[-1]}ms | Batch Efficiency: {batch_efficiency[-1]*100:.1f}% | Port: {PORT}</p>
</div>
<div class="card"><h2>Live Metrics</h2>
<div class="metric"><span>{requests_per_sec[-1]}</span>Req/sec</div>
<div class="metric"><span>{p99_latency_ms[-1]}ms</span>P99 Latency</div>
<div class="metric"><span>{batch_efficiency[-1]*100:.1f}%</span>Batch Efficiency</div>
<div class="metric"><span>{max(requests_per_sec)}</span>Peak Req/s</div>
</div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Inference Optimizer V3")
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
