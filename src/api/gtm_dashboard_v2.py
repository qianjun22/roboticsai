"""GTM Dashboard V2 — FastAPI port 8907"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8907

def build_html():
    data = [round(random.uniform(0.5, 1.0) * math.sin(i/3) + 1.5, 3) for i in range(10)]
    bars = "".join(f'<rect x="{30+i*40}" y="{150-int(v*60)}" width="30" height="{int(v*60)}" fill="#C74634"/>' for i, v in enumerate(data))
    channels = [
        ("NVIDIA Referral", 142000, 38),
        ("Inbound", 98000, 27),
        ("Conference", 74000, 19),
        ("Direct", 58000, 16),
    ]
    max_pipe = max(v for _, v, _ in channels)
    channel_bars = "".join(
        f'<g><rect x="180" y="{20+i*50}" width="{int(pipe/max_pipe*380)}" height="32" fill="#C74634" opacity="0.85"/>' +
        f'<text x="175" y="{41+i*50}" text-anchor="end" fill="#e2e8f0" font-size="13">{label}</text>' +
        f'<text x="{185+int(pipe/max_pipe*380)}" y="{41+i*50}" fill="#38bdf8" font-size="13">${pipe//1000}k ({pct}%)</text></g>'
        for i, (label, pipe, pct) in enumerate(channels)
    )
    return f"""<!DOCTYPE html><html><head><title>GTM Dashboard V2</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui}}
h1{{color:#C74634}}h2{{color:#38bdf8}}.card{{background:#1e293b;padding:20px;margin:10px;border-radius:8px}}
table{{border-collapse:collapse;width:100%}}td,th{{padding:8px 12px;border:1px solid #334155}}th{{background:#0f172a;color:#38bdf8}}
.metric{{display:inline-block;margin:10px 20px;text-align:center}}.metric .val{{font-size:2em;color:#C74634;font-weight:bold}}</style></head>
<body><h1>GTM Dashboard V2</h1>
<div class="card"><h2>GTM Velocity Metrics</h2>
<div class="metric"><div class="val">$284k</div><div>NVIDIA Co-Sell Weighted</div></div>
<div class="metric"><div class="val">30×</div><div>LTV / CAC</div></div>
<div class="metric"><div class="val">$84k</div><div>GTC 2026 Pipeline (3 leads)</div></div>
<div class="metric"><div class="val">{data[-1]}</div><div>Velocity Index | Port: {PORT}</div></div>
</div>
<div class="card"><h2>Channel Pipeline Funnel</h2>
<svg width="680" height="{20+len(channels)*50+20}">{channel_bars}</svg>
</div>
<div class="card"><h2>Campaign ROI</h2>
<table>
<tr><th>Campaign</th><th>Leads</th><th>Pipeline</th><th>ROI</th></tr>
<tr><td>GTC 2026</td><td>3</td><td>$84,000</td><td>14.0×</td></tr>
<tr><td>NVIDIA Co-Sell</td><td>6</td><td>$284,000</td><td>22.4×</td></tr>
<tr><td>Inbound / SEO</td><td>12</td><td>$98,000</td><td>31.2×</td></tr>
<tr><td>Direct Outbound</td><td>5</td><td>$58,000</td><td>9.8×</td></tr>
</table>
</div>
<div class="card"><h2>Feature Distribution</h2>
<svg width="450" height="180">{bars}</svg>
<p>Current value: {data[-1]} | Peak: {max(data)}</p>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="GTM Dashboard V2")
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
