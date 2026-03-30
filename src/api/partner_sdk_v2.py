"""Partner SDK v2 — FastAPI port 8513"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8513

def build_html():
    features = [
        ("Synchronous inference", 100, 100, "#22c55e"),
        ("Model management API", 94, 100, "#22c55e"),
        ("Streaming inference", 0, 78, "#38bdf8"),
        ("Async batch API", 0, 71, "#38bdf8"),
        ("RLHF feedback loop", 0, 41, "#f59e0b"),
        ("Bimanual support", 0, 28, "#f59e0b"),
        ("Edge (Jetson) deploy", 62, 89, "#a78bfa"),
        ("Custom eval hooks", 0, 54, "#64748b"),
    ]
    
    feature_bars = ""
    for name, v1_adopt, v2_adopt, col in features:
        feature_bars += f'''<div style="margin-bottom:8px">
<div style="display:flex;justify-content:space-between;margin-bottom:3px">
<span style="color:#e2e8f0;font-size:12px">{name}</span>
<span style="color:#64748b;font-size:11px">v1: {v1_adopt}% → v2: <span style="color:{col}">{v2_adopt}%</span></span>
</div>
<div style="display:flex;gap:3px">
<div style="background:#334155;border-radius:2px;height:6px;flex:1">
<div style="background:#64748b;width:{v1_adopt}%;height:6px;border-radius:2px"></div></div>
<div style="background:#334155;border-radius:2px;height:6px;flex:1">
<div style="background:{col};width:{v2_adopt}%;height:6px;border-radius:2px"></div></div>
</div></div>'''
    
    # partner endpoint usage heatmap
    partners = ["PI", "Apt", "1X", "Skild", "Covariant"]
    endpoints = ["/inference", "/model", "/eval", "/dagger", "/partner", "/billing"]
    
    heatmap = ""
    for p_i, partner in enumerate(partners):
        for e_i, endpoint in enumerate(endpoints):
            usage = random.uniform(0.1, 1.0)
            if endpoint == "/inference":
                usage = min(1.0, usage + 0.5)
            x = e_i * 72 + 5
            y = p_i * 20 + 5
            col = "#22c55e" if usage > 0.7 else ("#38bdf8" if usage > 0.4 else "#334155")
            heatmap += f'<rect x="{x}" y="{y}" width="68" height="16" fill="{col}" opacity="{usage:.2f}" rx="2"/>'
        heatmap += f'<text x="440" y="{p_i*20+15}" fill="#64748b" font-size="9">{partner}</text>'
    
    for e_i, ep in enumerate(endpoints):
        heatmap += f'<text x="{e_i*72+39}" y="115" text-anchor="middle" fill="#64748b" font-size="8" transform="rotate(-15,{e_i*72+39},115)">{ep}</text>'
    
    adoption_rate = 73
    latency_reduction = 34
    
    return f"""<!DOCTYPE html><html><head><title>Partner SDK v2</title>
<style>body{{margin:0;font-family:monospace;background:#0f172a;color:#e2e8f0}}
.hdr{{background:#C74634;padding:16px 24px;display:flex;justify-content:space-between;align-items:center}}
.hdr h1{{margin:0;font-size:20px;color:#fff}}.hdr span{{color:#fca5a5;font-size:13px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;padding:20px}}
.card{{background:#1e293b;border-radius:8px;padding:16px}}
.card h3{{margin:0 0 12px;color:#38bdf8;font-size:14px;text-transform:uppercase;letter-spacing:1px}}
.stat{{font-size:36px;font-weight:bold;color:#f1f5f9}}.sub{{color:#64748b;font-size:12px;margin-top:4px}}</style></head>
<body>
<div class="hdr"><h1>Partner SDK v2</h1><span>port {PORT} · v2 migration tracker</span></div>
<div class="grid">
<div class="card"><h3>v2 Adoption</h3><div class="stat">{adoption_rate}%</div><div class="sub">of active partners on v2</div></div>
<div class="card"><h3>Latency Reduction</h3><div class="stat">{latency_reduction}ms</div><div class="sub">streaming reduces first-token latency</div></div>
<div class="card"><h3>Feature Adoption (v1 → v2)</h3>{feature_bars}</div>
<div class="card"><h3>Partner × Endpoint Usage Heatmap</h3>
<svg width="100%" viewBox="0 0 460 125">{heatmap}</svg></div>
</div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Partner SDK v2")
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
