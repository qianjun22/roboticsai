"""Policy Compression v2 — FastAPI port 8470"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8470

def build_html():
    # 5-method Pareto chart: SR vs latency vs size
    methods = ["Baseline", "Pruning", "INT8", "Distillation", "FP8", "FP8+Distill"]
    sr = [0.78, 0.73, 0.71, 0.76, 0.74, 0.74]
    latency_ms = [226, 187, 162, 198, 109, 109]
    size_gb = [6.7, 4.2, 3.8, 3.4, 3.2, 3.1]
    colors = ["#C74634", "#38bdf8", "#f59e0b", "#22c55e", "#8b5cf6", "#ec4899"]
    pareto_labels = [False, False, False, False, True, True]

    # SR vs latency scatter (bubble = size)
    scatter = ""
    for method, s, l, sz, color, pareto in zip(methods, sr, latency_ms, size_gb, colors, pareto_labels):
        x = 30 + (1.0 - l/250) * 240
        y = 170 - s * 170
        r = int(sz / 7.0 * 20) + 5
        scatter += f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="{color}" opacity="0.75"/>'
        lx = x + r + 4
        scatter += f'<text x="{lx:.1f}" y="{y+4:.1f}" fill="{color}" font-size="9">{method}</text>'
        if pareto:
            scatter += f'<text x="{x:.1f}" y="{y:.1f}" fill="#0f172a" font-size="9" text-anchor="middle" font-weight="bold">\u2605</text>'

    # Pareto frontier line
    pareto_pts = [(30 + (1.0 - l/250)*240, 170 - s*170) for s, l, p in zip(sr, latency_ms, pareto_labels) if p]
    pareto_pts.sort()
    if len(pareto_pts) >= 2:
        for i in range(len(pareto_pts) - 1):
            scatter += f'<line x1="{pareto_pts[i][0]:.1f}" y1="{pareto_pts[i][1]:.1f}" x2="{pareto_pts[i+1][0]:.1f}" y2="{pareto_pts[i+1][1]:.1f}" stroke="#22c55e" stroke-width="1.5" stroke-dasharray="4,3"/>'

    # compression ratio vs SR retention bar
    ret_bars = ""
    for i, (method, s, sz, color) in enumerate(zip(methods[1:], sr[1:], size_gb[1:], colors[1:])):
        retention = s / sr[0]
        compression = 1 - sz / size_gb[0]
        y = 15 + i * 34
        wr = int(retention * 220)
        wc = int(compression * 220)
        ret_bars += f'<rect x="120" y="{y}" width="{wr}" height="12" fill="{color}" opacity="0.85" rx="2"/>'
        ret_bars += f'<rect x="120" y="{y+14}" width="{wc}" height="10" fill="{color}" opacity="0.4" rx="2"/>'
        ret_bars += f'<text x="116" y="{y+10}" fill="#94a3b8" font-size="9" text-anchor="end">{method}</text>'
        ret_bars += f'<text x="{120+wr+4}" y="{y+10}" fill="#e2e8f0" font-size="9">SR {int(retention*100)}%</text>'
        ret_bars += f'<text x="{120+wc+4}" y="{y+22}" fill="#94a3b8" font-size="9">-{int(compression*100)}% size</text>'

    return f"""<!DOCTYPE html>
<html>
<head><title>Policy Compression v2</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',sans-serif}}
.hdr{{background:#1e293b;padding:16px 24px;border-bottom:2px solid #C74634;display:flex;align-items:center;gap:12px}}
.hdr h1{{margin:0;font-size:20px;color:#f1f5f9}}
.badge{{background:#C74634;color:#fff;padding:3px 10px;border-radius:12px;font-size:11px;font-weight:700}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;padding:20px}}
.card{{background:#1e293b;border-radius:10px;padding:18px;border:1px solid #334155}}
.card h3{{margin:0 0 12px;font-size:14px;color:#94a3b8;text-transform:uppercase;letter-spacing:.05em}}
.metrics{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;padding:16px 20px}}
.m{{background:#1e293b;border-radius:8px;padding:12px 16px;border:1px solid #334155}}
.mv{{font-size:24px;font-weight:700;color:#38bdf8}}
.ml{{font-size:11px;color:#64748b;margin-top:2px}}
.delta{{font-size:12px;color:#22c55e;margin-top:4px}}
</style>
</head>
<body>
<div class="hdr">
  <span class="badge">PORT {PORT}</span>
  <h1>Policy Compression v2 \u2014 Cloud+Edge Deployment</h1>
</div>
<div class="metrics">
  <div class="m"><div class="mv">FP8+Distill</div><div class="ml">Best Combined</div><div class="delta">3.1GB / 109ms / 95% SR</div></div>
  <div class="m"><div class="mv">3.1GB</div><div class="ml">Compressed Size</div><div class="delta">54% reduction</div></div>
  <div class="m"><div class="mv">109ms</div><div class="ml">TRT Latency</div></div>
  <div class="m"><div class="mv">Jetson AGX</div><div class="ml">Edge Deploy Target</div></div>
</div>
<div class="grid">
  <div class="card">
    <h3>Pareto: SR vs Latency (bubble=model size, \u2605=Pareto)</h3>
    <svg viewBox="0 0 380 195" width="100%">
      <line x1="28" y1="10" x2="28" y2="178" stroke="#334155" stroke-width="1"/>
      <line x1="28" y1="178" x2="375" y2="178" stroke="#334155" stroke-width="1"/>
      {scatter}
      <text x="205" y="193" fill="#64748b" font-size="9" text-anchor="middle">Faster (lower latency) \u2192</text>
      <text x="15" y="90" fill="#64748b" font-size="9" transform="rotate(-90,15,90)">Higher SR \u2191</text>
    </svg>
  </div>
  <div class="card">
    <h3>SR Retention vs Size Reduction</h3>
    <svg viewBox="0 0 430 215" width="100%">
      <line x1="118" y1="10" x2="118" y2="210" stroke="#334155" stroke-width="1"/>
      {ret_bars}
    </svg>
  </div>
</div>
</body>
</html>"""

if USE_FASTAPI:
    app = FastAPI(title="Policy Compression v2")
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
