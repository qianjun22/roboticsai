"""GPU Quota Forecaster — FastAPI port 8403"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8403

def build_html():
    months = ["Apr","May","Jun","Jul","Aug","Sep"]
    # Stacked GPU demand by use case (GPU-hrs/day)
    training = [48, 52, 64, 68, 72, 80]
    dagger =   [24, 28, 32, 36, 38, 42]
    eval_hrs = [12, 14, 16, 18, 20, 22]
    inference= [8,  10, 14, 18, 24, 32]
    capacity = [96, 96, 192, 192, 288, 288]  # after node expansions

    max_val = 200
    bw = 40; gap = 10
    svg_d = '<svg width="380" height="220" style="background:#0f172a">'
    svg_d += '<line x1="50" y1="10" x2="50" y2="175" stroke="#475569" stroke-width="1"/>'
    svg_d += '<line x1="50" y1="175" x2="360" y2="175" stroke="#475569" stroke-width="1"/>'
    for i in range(5):
        yv = i*50; y = 175 - yv*160/max_val
        svg_d += f'<text x="45" y="{y+4}" fill="#94a3b8" font-size="8" text-anchor="end">{yv}</text>'
        svg_d += f'<line x1="50" y1="{y}" x2="360" y2="{y}" stroke="#1e293b" stroke-width="1"/>'
    layer_colors = ["#C74634","#38bdf8","#22c55e","#f59e0b"]
    layers = list(zip(training, dagger, eval_hrs, inference))
    labels = ["training","dagger","eval","inference"]
    for mi, month in enumerate(months):
        x = 55 + mi*(bw+gap)
        bottom = 175
        vals = [training[mi], dagger[mi], eval_hrs[mi], inference[mi]]
        for v, col in zip(vals, layer_colors):
            h = v*160/max_val
            svg_d += f'<rect x="{x}" y="{bottom-h:.0f}" width="{bw}" height="{h:.0f}" fill="{col}" opacity="0.85"/>'
            bottom -= h
        # Capacity line point
        cap_y = 175 - capacity[mi]*160/max_val
        if mi > 0:
            prev_cap_y = 175 - capacity[mi-1]*160/max_val
            prev_x = 55+(mi-1)*(bw+gap)+bw//2
            svg_d += f'<line x1="{prev_x}" y1="{prev_cap_y:.0f}" x2="{x+bw//2}" y2="{cap_y:.0f}" stroke="white" stroke-width="1.5" stroke-dasharray="4,3"/>'
        svg_d += f'<circle cx="{x+bw//2}" cy="{cap_y:.0f}" r="3" fill="white"/>'
        svg_d += f'<text x="{x+bw//2}" y="187" fill="#94a3b8" font-size="8" text-anchor="middle">{month}</text>'
    svg_d += '<text x="200" y="205" fill="#94a3b8" font-size="9" text-anchor="middle">GPU-hrs/day demand vs capacity (dashed)</text>'
    svg_d += '</svg>'

    # Quota request timeline bars
    requests = [("Now: 4×A100_80GB","current",0),("Jun: +2 nodes","pending",90),("Aug: +1 node","planned",150)]
    svg_q = '<svg width="320" height="120" style="background:#0f172a">'
    for i, (label, status, start) in enumerate(requests):
        col = "#22c55e" if status=="current" else "#f59e0b" if status=="pending" else "#94a3b8"
        w = 120 if status=="current" else 80 if status=="pending" else 60
        svg_q += f'<rect x="{50+start}" y="{20+i*30}" width="{w}" height="20" fill="{col}" rx="3" opacity="0.8"/>'
        svg_q += f'<text x="{50+start+w+5}" y="{20+i*30+14}" fill="#e2e8f0" font-size="9">{label}</text>'
    svg_q += '</svg>'

    return f"""<!DOCTYPE html><html><head><title>GPU Quota Forecaster — Port {PORT}</title>
<style>body{{background:#0f172a;color:#e2e8f0;font-family:monospace;margin:0;padding:20px}}
h1{{color:#C74634;font-size:18px}}h2{{color:#38bdf8;font-size:14px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:20px}}
.card{{background:#1e293b;padding:16px;border-radius:8px}}
.stat{{font-size:24px;color:#C74634;font-weight:bold}}
.label{{color:#94a3b8;font-size:12px}}</style></head>
<body><h1>GPU Quota Forecaster</h1>
<p style="color:#94a3b8">Port {PORT} | 6-month demand forecast + OCI quota request timeline</p>
<div class="grid">
<div class="card"><h2>GPU Demand vs Capacity (Apr–Sep)</h2>{svg_d}</div>
<div class="card"><h2>Quota Request Timeline</h2>{svg_q}
<div style="margin-top:10px">
<div class="stat">21 days</div><div class="label">OCI quota request lead time</div>
<div class="stat" style="color:#f59e0b;margin-top:8px">Jun</div><div class="label">+2 nodes needed (AI World prep)</div>
<div style="margin-top:8px;color:#94a3b8;font-size:11px">Sep AI World demand spike: 176 GPU-hrs/day<br>Current capacity: 96 GPU-hrs/day (4 nodes)<br>Jun expansion to 192: covers pilot growth<br>Aug +1 node → 288: AI World buffer</div>
</div></div></div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="GPU Quota Forecaster")
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
