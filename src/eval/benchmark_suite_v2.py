"""Benchmark Suite V2 — FastAPI port 8872"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8872

def build_html():
    data = [round(random.uniform(0.5, 1.0) * math.sin(i/3) + 1.5, 3) for i in range(10)]
    bars = "".join(f'<rect x="{30+i*40}" y="{150-int(v*60)}" width="30" height="{int(v*60)}" fill="#C74634"/>' for i, v in enumerate(data))
    return f"""<!DOCTYPE html><html><head><title>Benchmark Suite V2</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui}}
h1{{color:#C74634}}h2{{color:#38bdf8}}.card{{background:#1e293b;padding:20px;margin:10px;border-radius:8px}}
table{{width:100%;border-collapse:collapse}}th,td{{padding:8px 12px;text-align:left;border-bottom:1px solid #334155}}
th{{color:#38bdf8}}.badge{{display:inline-block;padding:2px 8px;border-radius:4px;font-size:0.85em}}
.good{{background:#14532d;color:#86efac}}.mid{{background:#713f12;color:#fde68a}}</style></head>
<body><h1>Benchmark Suite V2</h1>
<div class="card"><h2>Benchmark Scores by Task</h2>
<svg width="450" height="180">{bars}</svg>
<p>Current value: {data[-1]} | Peak: {max(data)} | Port: {PORT}</p>
</div>
<div class="card"><h2>Policy Evaluation Metrics</h2>
<table>
<tr><th>Task</th><th>Success Rate</th><th>Inference Time</th><th>Generalization Score</th><th>Status</th></tr>
<tr><td>Pick &amp; Place</td><td>87.3%</td><td>231ms</td><td>0.82</td><td><span class="badge good">PASS</span></td></tr>
<tr><td>Stack Blocks</td><td>74.1%</td><td>245ms</td><td>0.71</td><td><span class="badge good">PASS</span></td></tr>
<tr><td>Open Drawer</td><td>91.5%</td><td>228ms</td><td>0.89</td><td><span class="badge good">PASS</span></td></tr>
<tr><td>Pour Liquid</td><td>62.8%</td><td>260ms</td><td>0.64</td><td><span class="badge mid">WARN</span></td></tr>
<tr><td>Door Handle</td><td>78.9%</td><td>237ms</td><td>0.76</td><td><span class="badge good">PASS</span></td></tr>
</table></div>
<div class="card"><h2>Aggregate Summary</h2>
<p>Mean Success Rate: <strong>78.9%</strong> | Mean Inference Time: <strong>240ms</strong> | Mean Generalization: <strong>0.764</strong></p>
<p>Benchmark suite covers 5 canonical tasks across manipulation, articulation, and dexterous categories.</p>
</div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Benchmark Suite V2")
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
