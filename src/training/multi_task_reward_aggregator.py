"""Multi-Task Reward Aggregator — FastAPI port 8880"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8880

TASKS = ["pick_place", "lift", "pour", "fold", "bimanual", "nav"]

def build_html():
    # Per-task reward weights (adaptive, sum ~1)
    weights = [round(random.uniform(0.05, 0.35), 3) for _ in range(6)]
    total = sum(weights)
    weights = [round(w / total, 3) for w in weights]
    # SR-adaptive update curve over 10 steps
    sr_curve = [round(random.uniform(0.3, 0.9) * math.sin(i / 3) + 0.6, 3) for i in range(10)]
    # Weight bars (per task)
    weight_bars = "".join(
        f'<rect x="{30 + i * 65}" y="{150 - int(weights[i] * 400)}" width="50" height="{int(weights[i] * 400)}" fill="#C74634"/>'
        f'<text x="{55 + i * 65}" y="168" text-anchor="middle" fill="#e2e8f0" font-size="11">{TASKS[i]}</text>'
        f'<text x="{55 + i * 65}" y="{145 - int(weights[i] * 400)}" text-anchor="middle" fill="#fbbf24" font-size="10">{weights[i]}</text>'
        for i in range(6)
    )
    # SR-adaptive curve line
    points = " ".join(f"{30 + i * 40},{150 - int(sr_curve[i] * 80)}" for i in range(10))
    return f"""<!DOCTYPE html><html><head><title>Multi-Task Reward Aggregator</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui}}
h1{{color:#C74634}}h2{{color:#38bdf8}}.card{{background:#1e293b;padding:20px;margin:10px;border-radius:8px}}
table{{width:100%;border-collapse:collapse}}td,th{{padding:8px;border:1px solid #334155;text-align:left}}
th{{background:#0f172a;color:#38bdf8}}</style></head>
<body><h1>Multi-Task Reward Aggregator</h1>
<div class="card"><h2>Adaptive Reward Weights (6 Tasks)</h2>
<svg width="450" height="180">{weight_bars}</svg>
<p>Tasks: {', '.join(TASKS)} | Port: {PORT}</p>
</div>
<div class="card"><h2>SR-Adaptive Update Curve</h2>
<svg width="450" height="180">
  <polyline points="{points}" fill="none" stroke="#38bdf8" stroke-width="2"/>
  {''.join(f'<circle cx="{30+i*40}" cy="{150-int(sr_curve[i]*80)}" r="4" fill="#C74634"/>' for i in range(10))}
</svg>
<p>Current SR: {sr_curve[-1]} | Peak SR: {max(sr_curve)} | Steps: 10</p>
</div>
<div class="card"><h2>Weight Table</h2>
<table><tr><th>Task</th><th>Weight</th><th>Status</th></tr>
{''.join(f'<tr><td>{TASKS[i]}</td><td>{weights[i]}</td><td style="color:#4ade80">active</td></tr>' for i in range(6))}
</table></div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Multi-Task Reward Aggregator")
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
