"""Checkpoint Validation Suite — FastAPI port 8878"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8878

GATES = [
    ("Loss",      "pass"),
    ("Success Rate", "pass"),
    ("Latency",   "warn"),
    ("Memory",    "pass"),
    ("ONNX Export", "pass"),
    ("Jetson Deploy", "warn"),
    ("Safety",    "fail"),
]

CHECKPOINTS = [
    {"name": "ckpt-1000", "loss": 0.213, "sr": 0.42, "parent": None},
    {"name": "ckpt-2000", "loss": 0.157, "sr": 0.61, "parent": "ckpt-1000"},
    {"name": "ckpt-3000", "loss": 0.109, "sr": 0.78, "parent": "ckpt-2000"},
    {"name": "ckpt-best", "loss": 0.099, "sr": 0.85, "parent": "ckpt-3000"},
]

def build_html():
    data = [round(random.uniform(0.5, 1.0) * math.sin(i/3) + 1.5, 3) for i in range(10)]
    bars = "".join(f'<rect x="{30+i*40}" y="{150-int(v*60)}" width="30" height="{int(v*60)}" fill="#C74634"/>' for i, v in enumerate(data))

    gate_colors = {"pass": "#22c55e", "warn": "#f59e0b", "fail": "#ef4444"}
    gate_rows = "".join(
        f'<tr><td style="padding:6px 12px">{name}</td>'
        f'<td style="padding:6px 12px;color:{gate_colors[status]};font-weight:bold">{status.upper()}</td></tr>'
        for name, status in GATES
    )

    lineage_rows = ""
    for i, ck in enumerate(CHECKPOINTS):
        indent = "&nbsp;" * (i * 4)
        arrow = "&#8627; " if ck["parent"] else ""
        lineage_rows += (
            f'<tr><td style="padding:4px 12px;font-family:monospace">{indent}{arrow}{ck["name"]}</td>'
            f'<td style="padding:4px 12px">{ck["loss"]}</td>'
            f'<td style="padding:4px 12px">{ck["sr"]}</td></tr>'
        )

    return f"""<!DOCTYPE html><html><head><title>Checkpoint Validation Suite</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui}}
h1{{color:#C74634}}h2{{color:#38bdf8}}.card{{background:#1e293b;padding:20px;margin:10px;border-radius:8px}}
table{{border-collapse:collapse;width:100%}}th{{color:#94a3b8;text-align:left;padding:6px 12px}}</style></head>
<body><h1>Checkpoint Validation Suite</h1>
<div class="card"><h2>Validation Gate Results</h2>
<table><tr><th>Gate</th><th>Status</th></tr>{gate_rows}</table>
</div>
<div class="card"><h2>Checkpoint Lineage</h2>
<table><tr><th>Checkpoint</th><th>Loss</th><th>Success Rate</th></tr>{lineage_rows}</table>
</div>
<div class="card"><h2>Validation Signal</h2>
<svg width="450" height="180">{bars}</svg>
<p>Current value: {data[-1]} | Peak: {max(data)} | Port: {PORT}</p>
</div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Checkpoint Validation Suite")
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
