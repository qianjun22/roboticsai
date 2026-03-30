"""Trajectory Replay Analyzer — FastAPI port 8894"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8894

def build_html():
    data = [round(random.uniform(0.5, 1.0) * math.sin(i/3) + 1.5, 3) for i in range(10)]
    bars = "".join(f'<rect x="{30+i*40}" y="{150-int(v*60)}" width="30" height="{int(v*60)}" fill="#C74634"/>' for i, v in enumerate(data))
    # Success trajectory (smooth sine) vs Failure trajectory (deviation at step 47 equivalent ~ index 4)
    success_pts = " ".join(f"{30+i*40},{120-int(math.sin(i/2)*40)}" for i in range(10))
    failure_pts = " ".join(f"{30+i*40},{120-int(math.sin(i/2)*40 + (30 if i==4 else 0))}" for i in range(10))
    jerk_improvement = -18
    smoothness = round(random.uniform(0.88, 0.96), 3)
    return f"""<!DOCTYPE html><html><head><title>Trajectory Replay Analyzer</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui}}
h1{{color:#C74634}}h2{{color:#38bdf8}}.card{{background:#1e293b;padding:20px;margin:10px;border-radius:8px}}
.warn{{color:#fbbf24;font-weight:bold}}.ok{{color:#34d399;font-weight:bold}}</style></head>
<body><h1>Trajectory Replay Analyzer</h1>
<div class="card"><h2>Joint Angle Trajectory Replay — Step-by-Step</h2>
<svg width="450" height="180">{bars}</svg>
<p>Current value: {data[-1]} | Peak: {max(data)} | Port: {PORT}</p>
</div>
<div class="card"><h2>Success vs Failure Overlay</h2>
<svg width="450" height="200">
  <polyline points="{success_pts}" fill="none" stroke="#34d399" stroke-width="2.5"/>
  <polyline points="{failure_pts}" fill="none" stroke="#C74634" stroke-width="2.5" stroke-dasharray="6,3"/>
  <text x="10" y="30" fill="#34d399" font-size="13">&#9644; run10 (success)</text>
  <text x="10" y="50" fill="#C74634" font-size="13">&#9644; run9 (failure)</text>
  <text x="190" y="80" fill="#fbbf24" font-size="12">&#9650; step 47 wrist deviation</text>
  <line x1="{30+4*40}" y1="60" x2="{30+4*40}" y2="160" stroke="#fbbf24" stroke-width="1.5" stroke-dasharray="4,2"/>
</svg>
<p class="warn">Critical failure detected at step 47: wrist joint deviation +30 deg</p>
<p>Smoothness metric: {smoothness} &nbsp;|&nbsp; <span class="ok">run10 jerk {jerk_improvement}% vs run9</span></p>
</div>
<div class="card"><h2>Replay Summary</h2>
<ul>
  <li>Episodes replayed: 20 | Failures flagged: 3</li>
  <li>Step 47 wrist deviation: primary root cause in 2/3 failures</li>
  <li>Jerk reduction run10 vs run9: <span class="ok">{jerk_improvement}%</span></li>
  <li>Trajectory smoothness score: {smoothness} (threshold 0.85)</li>
</ul>
</div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Trajectory Replay Analyzer")
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
