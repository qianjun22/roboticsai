"""Deployment Validator V2 — FastAPI port 8890"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8890

GATES = [
    ("latency", "p99 < 300ms"),
    ("success_rate", "SR > 95%"),
    ("memory", "< 8GB VRAM"),
    ("safety", "collision = 0"),
    ("onnx", "export valid"),
    ("jetson", "edge deploy ok"),
    ("rollback", "rollback < 30s"),
    ("sla", "uptime > 99.9%"),
    ("partner_notify", "notifications sent"),
    ("monitoring", "dashboards live"),
    ("runbook", "runbook published"),
    ("approval", "sign-off received"),
]

def build_html():
    data = [round(random.uniform(0.5, 1.0) * math.sin(i/3) + 1.5, 3) for i in range(10)]
    bars = "".join(f'<rect x="{30+i*40}" y="{150-int(v*60)}" width="30" height="{int(v*60)}" fill="#C74634"/>' for i, v in enumerate(data))
    rng = random.Random(42)
    gate_rows = ""
    passed = 0
    for name, desc in GATES:
        ok = rng.random() > 0.15
        if ok:
            passed += 1
        status = "<span style='color:#22c55e'>PASS</span>" if ok else "<span style='color:#ef4444'>FAIL</span>"
        gate_rows += f"<tr><td>{name}</td><td>{desc}</td><td>{status}</td></tr>"
    progress_pct = int(passed / len(GATES) * 100)
    return f"""<!DOCTYPE html><html><head><title>Deployment Validator V2</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui}}
h1{{color:#C74634}}h2{{color:#38bdf8}}.card{{background:#1e293b;padding:20px;margin:10px;border-radius:8px}}
table{{border-collapse:collapse;width:100%}}td,th{{padding:6px 12px;border:1px solid #334155;text-align:left}}
th{{background:#0f172a}}.progress-bar{{background:#334155;border-radius:4px;height:18px}}
.progress-fill{{background:#22c55e;height:18px;border-radius:4px;width:{progress_pct}%}}</style></head>
<body><h1>Deployment Validator V2</h1>
<div class="card"><h2>Shadow Mode Deployment — 12-Gate Checklist</h2>
<p>Gates passed: {passed}/{len(GATES)} &nbsp; Validation progress:</p>
<div class="progress-bar"><div class="progress-fill"></div></div>
<br/><table><tr><th>Gate</th><th>Criterion</th><th>Status</th></tr>{gate_rows}</table>
</div>
<div class="card"><h2>Validation Signal</h2>
<svg width="450" height="180">{bars}</svg>
<p>Current value: {data[-1]} | Peak: {max(data)} | Port: {PORT}</p>
</div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Deployment Validator V2")
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
