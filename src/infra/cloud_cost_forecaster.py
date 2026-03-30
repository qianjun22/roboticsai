"""Cloud Cost Forecaster — FastAPI port 8895"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8895

def build_html():
    data = [round(random.uniform(0.5, 1.0) * math.sin(i/3) + 1.5, 3) for i in range(10)]
    bars = "".join(f'<rect x="{30+i*40}" y="{150-int(v*60)}" width="30" height="{int(v*60)}" fill="#C74634"/>' for i, v in enumerate(data))
    # 90-day stacked area: GPU 44%, inference 31%, eval 15%, storage 10%
    # Simulate monthly cost totals with AI World Sep spike (index 5 = month 6 ~ Sep)
    base = [8200, 8400, 8700, 9100, 9400, 14800, 10200, 9800, 9600, 10100]
    gpu =   [int(v*0.44) for v in base]
    inf =   [int(v*0.31) for v in base]
    ev  =   [int(v*0.15) for v in base]
    st  =   [int(v*0.10) for v in base]
    # Build stacked area paths (simplified as polylines per layer)
    xs = [30 + i*40 for i in range(10)]
    def poly(vals, offset_vals):
        pts = " ".join(f"{xs[i]},{170-int(vals[i]/100 + offset_vals[i]/100)}" for i in range(10))
        return pts
    gpu_top  = [int(v/100) for v in gpu]
    inf_top  = [gpu_top[i] + int(inf[i]/100) for i in range(10)]
    ev_top   = [inf_top[i] + int(ev[i]/100) for i in range(10)]
    st_top   = [ev_top[i] + int(st[i]/100) for i in range(10)]
    def layer_path(tops, bottoms):
        fwd = " ".join(f"{xs[i]},{170-tops[i]}" for i in range(10))
        bwd = " ".join(f"{xs[i]},{170-bottoms[i]}" for i in range(9, -1, -1))
        return fwd + " " + bwd
    zero = [0]*10
    path_gpu  = layer_path(gpu_top, zero)
    path_inf  = layer_path(inf_top, gpu_top)
    path_ev   = layer_path(ev_top, inf_top)
    path_st   = layer_path(st_top, ev_top)
    total_forecast = sum(base)
    h100_saving = round(random.uniform(14, 18), 1)
    return f"""<!DOCTYPE html><html><head><title>Cloud Cost Forecaster</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui}}
h1{{color:#C74634}}h2{{color:#38bdf8}}.card{{background:#1e293b;padding:20px;margin:10px;border-radius:8px}}
.spike{{color:#fbbf24;font-weight:bold}}.ok{{color:#34d399;font-weight:bold}}</style></head>
<body><h1>Cloud Cost Forecaster</h1>
<div class="card"><h2>90-Day Cost Metrics</h2>
<svg width="450" height="180">{bars}</svg>
<p>Current value: {data[-1]} | Peak: {max(data)} | Port: {PORT}</p>
</div>
<div class="card"><h2>Stacked Area Forecast — 90 Days</h2>
<svg width="450" height="200">
  <polygon points="{path_st}" fill="#38bdf8" opacity="0.5"/>
  <polygon points="{path_ev}" fill="#818cf8" opacity="0.6"/>
  <polygon points="{path_inf}" fill="#fb923c" opacity="0.65"/>
  <polygon points="{path_gpu}" fill="#C74634" opacity="0.75"/>
  <text x="10" y="20" fill="#C74634" font-size="12">GPU 44%</text>
  <text x="80" y="20" fill="#fb923c" font-size="12">Inference 31%</text>
  <text x="190" y="20" fill="#818cf8" font-size="12">Eval 15%</text>
  <text x="265" y="20" fill="#38bdf8" font-size="12">Storage 10%</text>
  <line x1="{xs[5]}" y1="30" x2="{xs[5]}" y2="175" stroke="#fbbf24" stroke-width="1.5" stroke-dasharray="4,2"/>
  <text x="{xs[5]-10}" y="28" fill="#fbbf24" font-size="11">AI World Sep</text>
</svg>
<p class="spike">AI World Sep spike: pre-provisioned +57% GPU burst capacity</p>
</div>
<div class="card"><h2>Cost Driver Decomposition</h2>
<ul>
  <li>GPU compute: 44% — A100 fleet baseline + H100 migration in progress</li>
  <li>Inference serving: 31% — auto-scaling 3× during AI World event</li>
  <li>Evaluation runs: 15% — scheduled nightly + on-demand CI evals</li>
  <li>Storage (datasets/checkpoints): 10%</li>
  <li>90-day total forecast: <strong>${total_forecast:,}</strong></li>
  <li><span class="ok">H100 migration efficiency model: {h100_saving}% cost reduction vs A100</span></li>
</ul>
</div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Cloud Cost Forecaster")
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
