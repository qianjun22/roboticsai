"""Safety Constraint Monitor V2 — FastAPI port 8884"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8884

def build_html():
    data = [round(random.uniform(0.5, 1.0) * math.sin(i/3) + 1.5, 3) for i in range(10)]
    bars = "".join(f'<rect x="{30+i*40}" y="{150-int(v*60)}" width="30" height="{int(v*60)}" fill="#C74634"/>' for i, v in enumerate(data))
    # Safety violation trend: run9=2.1/100eps, run10=1.4, target=0.5
    violation_trend = [
        {"run": "run9", "violations": 2.1, "color": "#ef4444"},
        {"run": "run10", "violations": 1.4, "color": "#f97316"},
        {"run": "target", "violations": 0.5, "color": "#22c55e"},
    ]
    trend_bars = "".join(
        f'<rect x="{40+i*120}" y="{160-int(v["violations"]*50)}" width="60" height="{int(v["violations"]*50)}" fill="{v["color"]}"/>'
        f'<text x="{70+i*120}" y="175" text-anchor="middle" fill="#e2e8f0" font-size="11">{v["run"]}</text>'
        f'<text x="{70+i*120}" y="{152-int(v["violations"]*50)}" text-anchor="middle" fill="#e2e8f0" font-size="10">{v["violations"]}</text>'
        for i, v in enumerate(violation_trend)
    )
    # Safety-SR tradeoff table
    tradeoff_rows = "".join(
        f'<tr><td style="padding:6px 12px;color:#38bdf8">{name}</td><td style="padding:6px 12px;text-align:center">{sr}%</td><td style="padding:6px 12px;text-align:center;color:#f97316">{viol}</td></tr>'
        for name, sr, viol in [
            ("Strict (all limits)", 61, 0.5),
            ("Balanced", 74, 1.4),
            ("Permissive", 83, 3.2),
        ]
    )
    return f"""<!DOCTYPE html><html><head><title>Safety Constraint Monitor V2</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui}}
h1{{color:#C74634}}h2{{color:#38bdf8}}.card{{background:#1e293b;padding:20px;margin:10px;border-radius:8px}}
table{{border-collapse:collapse;width:100%}}th{{background:#0f172a;padding:8px 12px;color:#94a3b8;text-align:left}}
tr:nth-child(even){{background:#0f172a33}}</style></head>
<body><h1>Safety Constraint Monitor V2</h1>
<div class="card"><h2>Live Constraint Metrics</h2>
<svg width="450" height="180">{bars}</svg>
<p>Current value: {data[-1]} | Peak: {max(data)} | Port: {PORT}</p>
<p style="color:#94a3b8;font-size:13px">Monitoring: joint limits · workspace envelope · force ceiling</p>
</div>
<div class="card"><h2>Violation Trend (per 100 episodes)</h2>
<svg width="450" height="190">{trend_bars}</svg>
<p style="color:#94a3b8;font-size:13px">run9=2.1 | run10=1.4 | target=0.5 &nbsp;&#x2193; improving</p>
</div>
<div class="card"><h2>Safety-SR Tradeoff</h2>
<table><tr><th>Constraint Mode</th><th>Success Rate</th><th>Violations/100eps</th></tr>{tradeoff_rows}</table>
</div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Safety Constraint Monitor V2")
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
