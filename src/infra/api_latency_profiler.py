"""API Latency Profiler — FastAPI port 8488"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8488

def build_html():
    endpoints = [
        ("/inference", 226, 267, 0.28, "#C74634"),
        ("/dagger_step", 189, 401, 1.3, "#ef4444"),
        ("/eval/run", 145, 198, 0.0, "#22c55e"),
        ("/model/checkpoint", 82, 112, 0.0, "#22c55e"),
        ("/partner/metrics", 34, 67, 0.0, "#22c55e"),
        ("/training/status", 12, 28, 0.0, "#22c55e"),
        ("/health", 3, 7, 0.0, "#22c55e"),
        ("/metrics", 5, 11, 0.0, "#22c55e"),
    ]
    
    rows = ""
    for ep, p50, p99, err, col in endpoints:
        warn = " ⚠️" if p99 > 300 else ""
        rows += f'<tr><td style="color:{col};font-family:monospace">{ep}</td><td>{p50}ms</td><td style="color:{col}">{p99}ms{warn}</td><td style="color:{"#ef4444" if err > 0 else "#22c55e"}">{err:.2f}%</td></tr>'
    
    # waterfall for /inference breakdown
    components = [
        ("auth", 1.2, "#64748b"),
        ("queue", 12.0, "#38bdf8"),
        ("tokenize", 8.4, "#a78bfa"),
        ("encode", 24.8, "#f59e0b"),
        ("model_forward", 179.6, "#C74634"),
        ("decode", 6.2, "#38bdf8"),
        ("postprocess", 4.8, "#22c55e"),
    ]
    cumulative = 0
    waterfall = ""
    total_lat = sum(c[1] for c in components)
    for name, dur, col in components:
        x = cumulative / total_lat * 480
        w = dur / total_lat * 480
        y = 15
        waterfall += f'<rect x="{x:.1f}" y="{y}" width="{w:.1f}" height="25" fill="{col}" rx="2"/>'
        if w > 30:
            waterfall += f'<text x="{x+4:.1f}" y="31" fill="white" font-size="9">{name}</text>'
        cumulative += dur
    
    return f"""<!DOCTYPE html><html><head><title>API Latency Profiler</title>
<style>body{{margin:0;font-family:monospace;background:#0f172a;color:#e2e8f0}}
.hdr{{background:#C74634;padding:16px 24px;display:flex;justify-content:space-between;align-items:center}}
.hdr h1{{margin:0;font-size:20px;color:#fff}}.hdr span{{color:#fca5a5;font-size:13px}}
.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;padding:20px}}
.card{{background:#1e293b;border-radius:8px;padding:16px}}
.card h3{{margin:0 0 12px;color:#38bdf8;font-size:14px;text-transform:uppercase;letter-spacing:1px}}
.stat{{font-size:36px;font-weight:bold;color:#f1f5f9}}.sub{{color:#64748b;font-size:12px;margin-top:4px}}
table{{width:100%;border-collapse:collapse;font-size:12px}}
th{{text-align:left;color:#64748b;padding:6px 0;border-bottom:1px solid #334155}}
td{{padding:6px 0;border-bottom:1px solid #1e293b}}</style></head>
<body>
<div class="hdr"><h1>API Latency Profiler</h1><span>port {PORT} · 8 endpoints</span></div>
<div class="grid">
<div class="card"><h3>/inference p50</h3><div class="stat">226ms</div><div class="sub">target &lt;250ms ✓</div></div>
<div class="card"><h3>/dagger_step p99</h3><div class="stat" style="color:#ef4444">401ms</div><div class="sub">⚠ above 300ms SLA</div></div>
<div class="card"><h3>Overall Success</h3><div class="stat">99.7%</div><div class="sub">across all endpoints</div></div>
<div class="card" style="grid-column:span 3"><h3>/inference Latency Breakdown ({total_lat:.0f}ms total)</h3>
<svg width="100%" viewBox="0 0 480 45">{waterfall}</svg>
<div style="font-size:11px;color:#64748b;margin-top:6px">model_forward 79.6% dominant · TRT target: 109ms</div></div>
<div class="card" style="grid-column:span 3"><h3>Endpoint p50 / p99 / Error Rate</h3>
<table><tr><th>Endpoint</th><th>p50</th><th>p99</th><th>Error%</th></tr>{rows}</table></div>
</div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="API Latency Profiler")
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
