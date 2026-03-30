"""Eval Dataset Curator V2 — FastAPI port 8882"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8882

def build_html():
    data = [round(random.uniform(0.5, 1.0) * math.sin(i/3) + 1.5, 3) for i in range(10)]
    bars = "".join(f'<rect x="{30+i*40}" y="{150-int(v*60)}" width="30" height="{int(v*60)}" fill="#C74634"/>' for i, v in enumerate(data))
    difficulty_dist = {"easy": round(random.uniform(0.3, 0.4), 2), "medium": round(random.uniform(0.35, 0.45), 2), "hard": round(random.uniform(0.15, 0.25), 2)}
    quality_scores = {"pick_cube": round(random.uniform(0.88, 0.97), 3), "stack_blocks": round(random.uniform(0.82, 0.93), 3), "pour_liquid": round(random.uniform(0.75, 0.88), 3), "open_drawer": round(random.uniform(0.84, 0.95), 3)}
    diff_rows = "".join(f'<tr><td>{k}</td><td>{v*100:.1f}%</td><td>{"█" * int(v*20)}</td></tr>' for k, v in difficulty_dist.items())
    qual_rows = "".join(f'<tr><td>{k}</td><td>{v}</td><td style="color:{"#4ade80" if v > 0.9 else "#facc15" if v > 0.82 else "#f87171"}">{"PASS" if v > 0.82 else "REVIEW"}</td></tr>' for k, v in quality_scores.items())
    return f"""<!DOCTYPE html><html><head><title>Eval Dataset Curator V2</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui}}
h1{{color:#C74634}}h2{{color:#38bdf8}}.card{{background:#1e293b;padding:20px;margin:10px;border-radius:8px}}
table{{width:100%;border-collapse:collapse}}td,th{{padding:8px;border-bottom:1px solid #334155;text-align:left}}
th{{color:#38bdf8}}.badge{{background:#C74634;padding:2px 8px;border-radius:4px;font-size:12px}}</style></head>
<body><h1>Eval Dataset Curator V2</h1>
<p class="badge">Port {PORT} | Episode Difficulty Stratification &amp; Quality Metrics</p>
<div class="card"><h2>Episode Quality Metrics (10 recent batches)</h2>
<svg width="450" height="180">{bars}</svg>
<p>Current value: {data[-1]} | Peak: {max(data)} | Port: {PORT}</p>
</div>
<div class="card"><h2>Difficulty Distribution</h2>
<table><tr><th>Tier</th><th>Share</th><th>Volume</th></tr>{diff_rows}</table>
</div>
<div class="card"><h2>Dataset Quality Scores per Task</h2>
<table><tr><th>Task</th><th>Quality Score</th><th>Status</th></tr>{qual_rows}</table>
<p style="color:#94a3b8;font-size:13px">Automated curation pipeline: filter low-quality episodes → stratify by difficulty → balance dataset distribution</p>
</div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Eval Dataset Curator V2")
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
