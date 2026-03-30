"""GR00T Fine-Tune Scheduler V2 — FastAPI port 8900"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8900

def build_html():
    data = [round(random.uniform(0.5, 1.0) * math.sin(i/3) + 1.5, 3) for i in range(10)]
    bars = "".join(f'<rect x="{30+i*40}" y="{150-int(v*60)}" width="30" height="{int(v*60)}" fill="#C74634"/>' for i, v in enumerate(data))
    jobs = [
        ("Gold", "DAgger", "robot-arm-01", "P1", "Running"),
        ("Gold", "BC",     "robot-arm-02", "P2", "Queued"),
        ("Silver", "DAgger", "robot-leg-01", "P3", "Queued"),
        ("Silver", "BC",   "robot-hand-01", "P4", "Pending"),
        ("Bronze", "BC",   "robot-nav-01",  "P5", "Pending"),
    ]
    rows = "".join(
        f"<tr><td>{t}</td><td>{m}</td><td>{e}</td><td>{p}</td><td>{s}</td></tr>"
        for t, m, e, p, s in jobs
    )
    gantt_bars = [
        ("DAgger-Gold",  "#C74634", 0,   120),
        ("BC-Gold",      "#e07b39", 120, 80),
        ("DAgger-Silver","#38bdf8", 200, 90),
        ("BC-Silver",    "#7dd3fc", 290, 70),
        ("BC-Bronze",    "#94a3b8", 360, 60),
    ]
    gantt = "".join(
        f'<rect x="{50+x}" y="{10+i*28}" width="{w}" height="20" fill="{c}"/><text x="{55+x}" y="{25+i*28}" fill="#e2e8f0" font-size="10">{lbl}</text>'
        for i, (lbl, c, x, w) in enumerate(gantt_bars)
    )
    return f"""<!DOCTYPE html><html><head><title>GR00T Fine-Tune Scheduler V2</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui}}
h1{{color:#C74634}}h2{{color:#38bdf8}}.card{{background:#1e293b;padding:20px;margin:10px;border-radius:8px}}
table{{border-collapse:collapse;width:100%}}th,td{{border:1px solid #334155;padding:6px 10px;text-align:left}}
th{{background:#0f172a;color:#38bdf8}}</style></head>
<body><h1>GR00T Fine-Tune Scheduler V2</h1>
<div class="card"><h2>Priority Queue — SLA-Weighted GPU Jobs</h2>
<p>Gold partners preempt Silver; DAgger preempts BC within same tier.</p>
<table><tr><th>Tier</th><th>Mode</th><th>Embodiment</th><th>Priority</th><th>Status</th></tr>{rows}</table>
</div>
<div class="card"><h2>GPU4 Gantt Timeline</h2>
<svg width="470" height="160">{gantt}</svg>
</div>
<div class="card"><h2>Throughput Metrics</h2>
<svg width="450" height="180">{bars}</svg>
<p>Current value: {data[-1]} | Peak: {max(data)} | Port: {PORT}</p>
</div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="GR00T Fine-Tune Scheduler V2")
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
