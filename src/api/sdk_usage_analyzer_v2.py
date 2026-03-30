"""SDK Usage Analyzer V2 — FastAPI port 8879"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8879

PARTNERS = ["AcmeCorp", "BotLabs", "CyberDyn", "DataForge"]
METHODS  = ["infer()", "train()", "eval()", "deploy()", "monitor()"]

ERRORS = [
    ("AuthError",      14),
    ("TimeoutError",   9),
    ("ShapeError",     6),
    ("RateLimitError", 4),
    ("UnknownError",   2),
]

FUNNEL = [
    ("SDK Installed",    1200),
    ("First API Call",    870),
    ("Repeated Usage",    540),
    ("Production Deploy", 210),
]

def build_html():
    data = [round(random.uniform(0.5, 1.0) * math.sin(i/3) + 1.5, 3) for i in range(10)]
    bars = "".join(f'<rect x="{30+i*40}" y="{150-int(v*60)}" width="30" height="{int(v*60)}" fill="#C74634"/>' for i, v in enumerate(data))

    # Heatmap: partners x methods
    heat_rows = ""
    for partner in PARTNERS:
        cells = "".join(
            f'<td style="padding:8px 14px;background:rgba(199,70,52,{round(random.uniform(0.1,0.95),2)});text-align:center">{random.randint(10,500)}</td>'
            for _ in METHODS
        )
        heat_rows += f'<tr><td style="padding:8px 12px;font-weight:bold">{partner}</td>{cells}</tr>'

    method_headers = "".join(f'<th style="padding:6px 14px;color:#94a3b8">{m}</th>' for m in METHODS)

    # Error breakdown
    err_rows = "".join(
        f'<tr><td style="padding:5px 12px">{name}</td>'
        f'<td style="padding:5px 12px"><div style="background:#C74634;height:14px;width:{count*8}px;border-radius:3px"></div></td>'
        f'<td style="padding:5px 12px">{count}</td></tr>'
        for name, count in ERRORS
    )

    # Adoption funnel
    funnel_rows = "".join(
        f'<tr><td style="padding:5px 12px">{stage}</td>'
        f'<td style="padding:5px 12px"><div style="background:#38bdf8;height:14px;width:{int(count/5)}px;border-radius:3px"></div></td>'
        f'<td style="padding:5px 12px">{count}</td></tr>'
        for stage, count in FUNNEL
    )

    return f"""<!DOCTYPE html><html><head><title>SDK Usage Analyzer V2</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui}}
h1{{color:#C74634}}h2{{color:#38bdf8}}.card{{background:#1e293b;padding:20px;margin:10px;border-radius:8px}}
table{{border-collapse:collapse;width:100%}}th{{text-align:left}}</style></head>
<body><h1>SDK Usage Analyzer V2</h1>
<div class="card"><h2>Partner x Method Heatmap</h2>
<table><tr><th style="padding:6px 12px">Partner</th>{method_headers}</tr>{heat_rows}</table>
</div>
<div class="card"><h2>Adoption Funnel</h2>
<table>{funnel_rows}</table>
</div>
<div class="card"><h2>Error Breakdown</h2>
<table>{err_rows}</table>
</div>
<div class="card"><h2>Telemetry Signal</h2>
<svg width="450" height="180">{bars}</svg>
<p>Current value: {data[-1]} | Peak: {max(data)} | Port: {PORT}</p>
</div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="SDK Usage Analyzer V2")
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
