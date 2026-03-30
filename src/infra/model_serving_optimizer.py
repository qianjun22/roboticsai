"""Model Serving Optimizer — FastAPI port 8455"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8455

def build_html():
    # serving strategy comparison
    strategies = ["PyTorch", "TorchScript", "ONNX", "TensorRT"]
    latencies_p50 = [226, 198, 156, 109]
    latencies_p99 = [312, 267, 214, 148]
    throughputs = [1240, 1680, 2100, 3200]
    colors = ["#64748b", "#38bdf8", "#f59e0b", "#22c55e"]

    strat_bars = ""
    for i, (s, lp50, lp99, thr, color) in enumerate(zip(strategies, latencies_p50, latencies_p99, throughputs, colors)):
        x = 20 + i * 120
        h50 = int(lp50 / 240 * 140)
        h99 = int(lp99 / 340 * 140)
        strat_bars += f'<rect x="{x}" y="{155-h50}" width="44" height="{h50}" fill="{color}" rx="3"/>'
        strat_bars += f'<rect x="{x+46}" y="{155-h99}" width="44" height="{h99}" fill="{color}" opacity="0.5" rx="3"/>'
        strat_bars += f'<text x="{x+46}" y="170" fill="#94a3b8" font-size="10" text-anchor="middle">{s}</text>'
        strat_bars += f'<text x="{x+22}" y="{155-h50-4}" fill="{color}" font-size="9" text-anchor="middle">{lp50}ms</text>'

    # batch size tradeoff curve
    batch_sizes = [1, 2, 4, 8, 16, 32]
    latency = [109, 118, 134, 167, 234, 421]
    throughput_b = [850, 1480, 2240, 3200, 3840, 4100]

    lat_pts = " ".join(f"{35+i*62:.1f},{155-latency[i]/440*130:.1f}" for i in range(len(batch_sizes)))
    thr_pts = " ".join(f"{35+i*62:.1f},{155-throughput_b[i]/4500*130:.1f}" for i in range(len(batch_sizes)))

    # SLA line at 300ms for p99
    sla_y = 155 - 300/440*130
    batch_svg = f'<polyline points="{lat_pts}" fill="none" stroke="#C74634" stroke-width="2.5"/>'
    batch_svg += f'<polyline points="{thr_pts}" fill="none" stroke="#22c55e" stroke-width="2"/>'
    batch_svg += f'<line x1="30" y1="{sla_y:.1f}" x2="380" y2="{sla_y:.1f}" stroke="#f59e0b" stroke-width="1.5" stroke-dasharray="4,3"/>'
    batch_svg += f'<text x="385" y="{sla_y+4:.1f}" fill="#f59e0b" font-size="9">300ms SLA</text>'
    for i, b in enumerate(batch_sizes):
        batch_svg += f'<text x="{35+i*62}" y="165" fill="#64748b" font-size="10" text-anchor="middle">b={b}</text>'
    # optimal marker at batch=8
    opt_x = 35 + 3*62
    opt_y = 155 - latency[3]/440*130
    batch_svg += f'<circle cx="{opt_x}" cy="{opt_y:.1f}" r="6" fill="#38bdf8"/>'
    batch_svg += f'<text x="{opt_x+8}" y="{opt_y-6:.1f}" fill="#38bdf8" font-size="9">optimal</text>'

    return f"""<!DOCTYPE html>
<html>
<head><title>Model Serving Optimizer</title>
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
  <h1>Model Serving Optimizer — TensorRT Benchmarks</h1>
</div>
<div class="metrics">
  <div class="m"><div class="mv">109ms</div><div class="ml">TensorRT p50</div><div class="delta">vs 226ms PyTorch</div></div>
  <div class="m"><div class="mv">3,200</div><div class="ml">req/hr (TensorRT)</div></div>
  <div class="m"><div class="mv">batch=8</div><div class="ml">Optimal Batch Size</div></div>
  <div class="m"><div class="mv">91%</div><div class="ml">GPU Utilization</div></div>
</div>
<div class="grid">
  <div class="card">
    <h3>Strategy Comparison (p50 / p99)</h3>
    <svg viewBox="0 0 510 185" width="100%">
      <line x1="15" y1="10" x2="15" y2="160" stroke="#334155" stroke-width="1"/>
      <line x1="15" y1="160" x2="505" y2="160" stroke="#334155" stroke-width="1"/>
      {strat_bars}
      <rect x="360" y="15" width="10" height="10" fill="#94a3b8"/>
      <text x="374" y="24" fill="#94a3b8" font-size="10">p50</text>
      <rect x="360" y="30" width="10" height="10" fill="#94a3b8" opacity="0.5"/>
      <text x="374" y="39" fill="#94a3b8" font-size="10">p99</text>
    </svg>
  </div>
  <div class="card">
    <h3>Batch Size: Latency vs Throughput</h3>
    <svg viewBox="0 0 440 185" width="100%">
      <line x1="28" y1="10" x2="28" y2="158" stroke="#334155" stroke-width="1"/>
      <line x1="28" y1="158" x2="430" y2="158" stroke="#334155" stroke-width="1"/>
      {batch_svg}
      <rect x="290" y="15" width="10" height="3" fill="#C74634"/>
      <text x="304" y="20" fill="#C74634" font-size="10">Latency</text>
      <rect x="290" y="26" width="10" height="3" fill="#22c55e"/>
      <text x="304" y="31" fill="#22c55e" font-size="10">Throughput</text>
    </svg>
  </div>
</div>
</body>
</html>"""

if USE_FASTAPI:
    app = FastAPI(title="Model Serving Optimizer")
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
