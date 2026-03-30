"""Multi-Step Task Evaluator — FastAPI port 8478"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8478

def build_html():
    tasks = [
        ("pick_and_place", 5, [1,1,1,1,1], "#22c55e"),
        ("stack_blocks", 4, [1,1,1,0], "#f59e0b"),
        ("pour_liquid", 6, [1,1,0,1,1,0], "#f59e0b"),
        ("open_drawer", 3, [1,1,1], "#22c55e"),
        ("wipe_surface", 4, [1,0,1,1], "#f59e0b"),
    ]
    rows = ""
    for name, steps, results, col in tasks:
        success_count = sum(results)
        rate = success_count / steps * 100
        step_icons = "".join(["<span style='color:#22c55e'>●</span>" if r else "<span style='color:#ef4444'>●</span>" for r in results])
        rows += f'<tr><td style="color:#e2e8f0">{name}</td><td>{steps}</td><td>{step_icons}</td><td style="color:{col}">{rate:.0f}%</td></tr>'
    
    # step completion heatmap
    heatmap = ""
    for row in range(5):
        for col_i in range(10):
            v = random.random()
            if v > 0.7:
                c = "#22c55e"
            elif v > 0.4:
                c = "#f59e0b"
            else:
                c = "#ef4444"
            x = col_i * 52 + 2
            y = row * 22 + 2
            heatmap += f'<rect x="{x}" y="{y}" width="48" height="18" fill="{c}" rx="3" opacity="0.8"/>'
    
    overall_sr = 68.5
    avg_steps = 4.4
    completion_rate = 72.3
    
    return f"""<!DOCTYPE html><html><head><title>Multi-Step Task Evaluator</title>
<style>body{{margin:0;font-family:monospace;background:#0f172a;color:#e2e8f0}}
.hdr{{background:#C74634;padding:16px 24px;display:flex;justify-content:space-between;align-items:center}}
.hdr h1{{margin:0;font-size:20px;color:#fff}}.hdr span{{color:#fca5a5;font-size:13px}}
.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;padding:20px}}
.card{{background:#1e293b;border-radius:8px;padding:16px}}
.card h3{{margin:0 0 12px;color:#38bdf8;font-size:14px;text-transform:uppercase;letter-spacing:1px}}
.stat{{font-size:36px;font-weight:bold;color:#f1f5f9}}.sub{{color:#64748b;font-size:12px;margin-top:4px}}
table{{width:100%;border-collapse:collapse;font-size:13px}}
th{{text-align:left;color:#64748b;padding:6px 0;border-bottom:1px solid #334155}}
td{{padding:6px 0;border-bottom:1px solid #1e293b}}</style></head>
<body>
<div class="hdr"><h1>Multi-Step Task Evaluator</h1><span>port {PORT}</span></div>
<div class="grid">
<div class="card"><h3>Overall SR</h3><div class="stat">{overall_sr}%</div><div class="sub">full task completion rate</div></div>
<div class="card"><h3>Avg Steps</h3><div class="stat">{avg_steps}</div><div class="sub">steps per task episode</div></div>
<div class="card"><h3>Step Completion</h3><div class="stat">{completion_rate}%</div><div class="sub">individual step success</div></div>
<div class="card" style="grid-column:span 3"><h3>Task Step Results</h3>
<table><tr><th>Task</th><th>Steps</th><th>Step Results</th><th>Rate</th></tr>{rows}</table></div>
<div class="card" style="grid-column:span 3"><h3>Step Completion Heatmap (5 episodes × 10 steps)</h3>
<svg width="100%" viewBox="0 0 522 112">{heatmap}</svg></div>
</div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Multi-Step Task Evaluator")
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
