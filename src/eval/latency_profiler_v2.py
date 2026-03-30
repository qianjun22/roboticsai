"""Latency Profiler V2 — FastAPI port 8903"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8903

def build_html():
    data = [round(random.uniform(0.5, 1.0) * math.sin(i/3) + 1.5, 3) for i in range(10)]
    bars = "".join(f'<rect x="{30+i*40}" y="{150-int(v*60)}" width="30" height="{int(v*60)}" fill="#C74634"/>' for i, v in enumerate(data))

    layers = [
        ("vision_encoder", 89),
        ("cross_attention", 41),
        ("action_decoder", 18),
        ("post_process", 12),
    ]
    total_latency = sum(ms for _, ms in layers)
    waterfall_bars = ""
    x_offset = 0
    colors = ["#C74634", "#38bdf8", "#7c3aed", "#065f46"]
    scale = 3.5
    for idx, (name, ms) in enumerate(layers):
        w = int(ms * scale)
        waterfall_bars += f'<rect x="{100 + x_offset}" y="{20 + idx*30}" width="{w}" height="20" fill="{colors[idx]}"/>'
        waterfall_bars += f'<text x="{100 + x_offset + w + 4}" y="{34 + idx*30}" font-size="11" fill="#e2e8f0">{ms}ms</text>'
        waterfall_bars += f'<text x="4" y="{34 + idx*30}" font-size="11" fill="#94a3b8">{name}</text>'
        x_offset += w

    batch_sizes = [1, 2, 4, 8, 16, 32]
    batch_latencies = [round(total_latency * (1 + 0.08 * math.log(b + 1)), 1) for b in batch_sizes]
    batch_bars = "".join(
        f'<rect x="{20 + i*65}" y="{160-int(lat*0.55)}" width="40" height="{int(lat*0.55)}" fill="#38bdf8"/>'
        f'<text x="{40 + i*65}" y="178" text-anchor="middle" font-size="10" fill="#94a3b8">bs={b}</text>'
        f'<text x="{40 + i*65}" y="{152-int(lat*0.55)}" text-anchor="middle" font-size="10" fill="#e2e8f0">{lat}</text>'
        for i, (b, lat) in enumerate(zip(batch_sizes, batch_latencies))
    )

    p50, p95, p99 = 142, 187, 231
    sla = 250
    sla_ok = "PASS" if p95 < sla else "FAIL"
    sla_color = "#22c55e" if sla_ok == "PASS" else "#ef4444"

    return f"""<!DOCTYPE html><html><head><title>Latency Profiler V2</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui}}
h1{{color:#C74634}}h2{{color:#38bdf8}}.card{{background:#1e293b;padding:20px;margin:10px;border-radius:8px}}
table{{border-collapse:collapse;width:100%}}th,td{{border:1px solid #334155;padding:6px 10px;text-align:left}}
th{{background:#0f172a;color:#38bdf8}}.pass{{color:#22c55e;font-weight:bold}}.fail{{color:#ef4444;font-weight:bold}}</style></head>
<body><h1>Latency Profiler V2</h1>
<div class="card"><h2>SLA Status</h2>
<table><tr><th>Percentile</th><th>Latency (ms)</th><th>SLA (ms)</th><th>Status</th></tr>
<tr><td>p50</td><td>{p50}</td><td>—</td><td>—</td></tr>
<tr><td>p95</td><td>{p95}</td><td>{sla}</td><td><span style="color:{sla_color}">{sla_ok} ({p95} &lt; {sla})</span></td></tr>
<tr><td>p99</td><td>{p99}</td><td>—</td><td>—</td></tr>
</table>
</div>
<div class="card"><h2>Per-Layer Latency Waterfall (total: {total_latency}ms)</h2>
<svg width="450" height="140">
{waterfall_bars}
</svg>
</div>
<div class="card"><h2>Batch Size vs Latency</h2>
<svg width="450" height="190">
{batch_bars}
</svg>
</div>
<div class="card"><h2>Trend</h2>
<svg width="450" height="180">{bars}</svg>
<p>Current value: {data[-1]} | Peak: {max(data)} | Port: {PORT}</p>
</div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Latency Profiler V2")
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
