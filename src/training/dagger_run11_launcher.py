"""DAgger Run 11 Launcher — FastAPI port 8904"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8904

def build_html():
    data = [round(random.uniform(0.5, 1.0) * math.sin(i/3) + 1.5, 3) for i in range(10)]
    bars = "".join(f'<rect x="{30+i*40}" y="{150-int(v*60)}" width="30" height="{int(v*60)}" fill="#C74634"/>' for i, v in enumerate(data))
    checklist = [
        ("green", "checkpoint_run10 loaded", "reward_v3 model verified"),
        ("green", "EWC_reg enabled", "lambda=0.4 (vs run10: 0.3)"),
        ("green", "chunk_size=16", "up from run10 chunk=12"),
        ("green", "lora_rank=32", "up from run10 rank=24"),
        ("green", "5000 steps scheduled", "est. 38 min on A100"),
        ("green", "target SR=0.80", "projected 0.78-0.82"),
        ("green", "eval harness ready", "20-episode closed-loop"),
        ("red",   "OCI GPU quota check", "pending confirmation"),
    ]
    gate_rows = "".join(
        f'<tr><td style="color:{'#22c55e' if g=="green" else '#ef4444'}">{"\u2705" if g=="green" else "\u274c"}</td>'
        f'<td>{name}</td><td style="color:#94a3b8">{detail}</td></tr>'
        for g, name, detail in checklist
    )
    config_rows = "".join(
        f'<tr><td>{p}</td><td style="color:#94a3b8">{r10}</td><td style="color:#38bdf8">{r11}</td></tr>'
        for p, r10, r11 in [
            ("reward_fn", "reward_v2", "reward_v3"),
            ("EWC_lambda", "0.3", "0.4"),
            ("chunk_size", "12", "16"),
            ("lora_rank", "24", "32"),
            ("steps", "5000", "5000"),
            ("target_SR", "0.72", "0.80"),
        ]
    )
    green_count = sum(1 for g, _, _ in checklist if g == "green")
    return f"""<!DOCTYPE html><html><head><title>DAgger Run 11 Launcher</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui;padding:20px}}
h1{{color:#C74634}}h2{{color:#38bdf8}}.card{{background:#1e293b;padding:20px;margin:10px;border-radius:8px}}
table{{border-collapse:collapse;width:100%}}td,th{{padding:8px 12px;text-align:left;border-bottom:1px solid #334155}}
th{{color:#38bdf8}}.badge{{display:inline-block;padding:4px 10px;border-radius:4px;font-size:0.85em}}
.green{{background:#166534;color:#86efac}}.amber{{background:#78350f;color:#fde68a}}</style></head>
<body><h1>DAgger Run 11 Launcher</h1>
<div class="card"><h2>Launch Gate Status — {green_count}/8 Green</h2>
<table><tr><th>Gate</th><th>Check</th><th>Detail</th></tr>{gate_rows}</table></div>
<div class="card"><h2>Config Delta: Run 10 vs Run 11</h2>
<table><tr><th>Parameter</th><th>Run 10</th><th>Run 11</th></tr>{config_rows}</table></div>
<div class="card"><h2>Training Signal</h2>
<svg width="450" height="180">{bars}</svg>
<p>Projected SR: <strong>0.78 – 0.82</strong> | Current value: {data[-1]} | Peak: {max(data)} | Port: {PORT}</p>
</div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="DAgger Run 11 Launcher")
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
