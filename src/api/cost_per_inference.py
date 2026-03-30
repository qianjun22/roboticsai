"""Cost Per Inference v2 — FastAPI port 8406"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8406

def build_html():
    # Cost waterfall SVG
    components = ["GPU_compute","VRAM_alloc","Network_egress","Storage_IO","Overhead"]
    costs = [0.00052, 0.00019, 0.00008, 0.00005, 0.00005]
    total = sum(costs)
    colors = ["#C74634","#38bdf8","#f59e0b","#22c55e","#a78bfa"]

    svg_w = '<svg width="360" height="200" style="background:#0f172a">'
    svg_w += '<line x1="40" y1="10" x2="40" y2="170" stroke="#475569" stroke-width="1"/>'
    svg_w += '<line x1="40" y1="170" x2="340" y2="170" stroke="#475569" stroke-width="1"/>'
    bw4 = 42; running = 0
    for i, (comp, cost, col) in enumerate(zip(components, costs, colors)):
        x = 45 + i*55; h = cost/total*130; y = 170-running*130/total-h
        svg_w += f'<rect x="{x}" y="{y:.0f}" width="{bw4}" height="{h:.0f}" fill="{col}" opacity="0.85"/>'
        svg_w += f'<text x="{x+bw4//2}" y="{y-3:.0f}" fill="{col}" font-size="7" text-anchor="middle">${cost:.5f}</text>'
        short = comp.split("_")[0]
        svg_w += f'<text x="{x+bw4//2}" y="183" fill="#94a3b8" font-size="7" text-anchor="middle">{short}</text>'
        running += cost
    # Total bar
    svg_w += f'<rect x="320" y="40" width="{bw4}" height="130" fill="#475569" opacity="0.3" stroke="#94a3b8" stroke-width="1"/>'
    svg_w += f'<text x="341" y="35" fill="white" font-size="8" text-anchor="middle">${total:.5f}</text>'
    svg_w += f'<text x="341" y="183" fill="#94a3b8" font-size="7" text-anchor="middle">Total</text>'
    svg_w += '</svg>'

    # Per-partner cost bar
    partners = ["PI_Robotics","Apptronik","1X_Tech","Covariant","Wandelbots"]
    volumes = [1200, 800, 450, 2100, 320]
    discounts = [0.15, 0.10, 0.05, 0.20, 0.0]
    eff_costs = [total*(1-d) for d in discounts]

    svg_p = '<svg width="360" height="200" style="background:#0f172a">'
    max_cost = max(eff_costs)*1.1
    for pi, (partner, vol, ec) in enumerate(zip(partners, volumes, eff_costs)):
        y = 20+pi*32; w = int(ec/max_cost*250)
        col = "#22c55e" if ec < 0.00075 else "#f59e0b" if ec < 0.00085 else "#C74634"
        svg_p += f'<rect x="90" y="{y}" width="{w}" height="22" fill="{col}" opacity="0.8"/>'
        svg_p += f'<text x="85" y="{y+15}" fill="#94a3b8" font-size="9" text-anchor="end">{partner}</text>'
        svg_p += f'<text x="{92+w}" y="{y+15}" fill="white" font-size="8">${ec:.5f} ({vol}/hr)</text>'
    svg_p += '<text x="190" y="185" fill="#38bdf8" font-size="8" text-anchor="middle">TensorRT target: $0.00041/req</text>'
    svg_p += '</svg>'

    return f"""<!DOCTYPE html><html><head><title>Cost Per Inference v2 — Port {PORT}</title>
<style>body{{background:#0f172a;color:#e2e8f0;font-family:monospace;margin:0;padding:20px}}
h1{{color:#C74634;font-size:18px}}h2{{color:#38bdf8;font-size:14px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:20px}}
.card{{background:#1e293b;padding:16px;border-radius:8px}}
.stat{{font-size:24px;color:#C74634;font-weight:bold}}
.label{{color:#94a3b8;font-size:12px}}</style></head>
<body><h1>Cost Per Inference v2</h1>
<p style="color:#94a3b8">Port {PORT} | Request cost breakdown + partner pricing analysis</p>
<div class="grid">
<div class="card"><h2>Cost Breakdown Waterfall</h2>{svg_w}
<div class="stat">${total:.5f}</div><div class="label">Total cost per inference (current)</div></div>
<div class="card"><h2>Per-Partner Effective Cost</h2>{svg_p}
<div style="margin-top:8px">
<div class="stat" style="color:#22c55e">15 req/min</div><div class="label">Breakeven throughput for profitability</div>
<div style="margin-top:8px;color:#94a3b8;font-size:11px">Volume discounts: Covariant 20% / PI 15%<br>TensorRT FP8 target: $0.00041 (54% savings)<br>GPU compute dominates at 58% of cost<br>Network egress reduction via edge caching</div>
</div></div></div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Cost Per Inference v2")
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
