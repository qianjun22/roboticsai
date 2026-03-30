"""Model Architecture Benchmarker — FastAPI port 8504"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8504

def build_html():
    models = [
        ("GR00T N1.6-3B", 0.78, 226, 3.0, 9.6, "#22c55e"),
        ("OpenVLA-7B", 0.71, 412, 7.0, 1.0, "#38bdf8"),
        ("Octo-1B", 0.62, 108, 1.0, 7.8, "#f59e0b"),
        ("ACT", 0.69, 89, 0.3, 12.1, "#a78bfa"),
        ("Diffusion Policy", 0.64, 340, 0.8, 4.2, "#64748b"),
        ("BC (ViT-B)", 0.51, 67, 0.3, 14.3, "#94a3b8"),
    ]
    
    # SR vs Latency scatter
    scatter = ""
    for name, sr, lat, params, oci_mult, col in models:
        x = lat / 450 * 400 + 20
        y = 100 - sr * 100
        r = max(5, params * 2)
        scatter += f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.0f}" fill="{col}" opacity="0.8"/>'
        scatter += f'<text x="{x+r+3:.1f}" y="{y+4:.1f}" fill="{col}" font-size="9">{name.split()[0]}</text>'
    scatter += f'<text x="210" y="115" text-anchor="middle" fill="#64748b" font-size="9">Latency (0\u2013450ms)</text>'
    scatter += f'<text x="5" y="55" fill="#64748b" font-size="9" transform="rotate(-90,5,55)">SR</text>'
    
    # FLOP efficiency bar (SR per GFLOP)
    model_rows = ""
    for name, sr, lat, params, oci_mult, col in models:
        flops = params * 2  # rough estimate GFLOPs
        flop_eff = sr / flops * 100
        oci_cost_str = f"{oci_mult:.1f}\u00d7" if oci_mult > 1 else "baseline"
        model_rows += f'<tr><td style="color:{col}">{name}</td><td>{sr:.2f}</td><td>{lat}ms</td><td>{params}B</td><td style="color:{col}">{oci_mult:.1f}\u00d7</td></tr>'
    
    # Pareto frontier highlight
    pareto = [("GR00T", 0.78, 226, "#22c55e"), ("Octo", 0.62, 108, "#f59e0b"), ("ACT", 0.69, 89, "#a78bfa")]
    pareto_pts = " ".join([f"{lat/450*400+20:.1f},{100-sr*100:.1f}" for _,sr,lat,_ in pareto])
    pareto_svg = f'<polyline points="{pareto_pts}" fill="none" stroke="#C74634" stroke-width="1.5" stroke-dasharray="4,2"/>'
    
    return f"""<!DOCTYPE html><html><head><title>Model Architecture Benchmarker</title>
<style>body{{margin:0;font-family:monospace;background:#0f172a;color:#e2e8f0}}
.hdr{{background:#C74634;padding:16px 24px;display:flex;justify-content:space-between;align-items:center}}
.hdr h1{{margin:0;font-size:20px;color:#fff}}.hdr span{{color:#fca5a5;font-size:13px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;padding:20px}}
.card{{background:#1e293b;border-radius:8px;padding:16px}}
.card h3{{margin:0 0 12px;color:#38bdf8;font-size:14px;text-transform:uppercase;letter-spacing:1px}}
.stat{{font-size:36px;font-weight:bold;color:#f1f5f9}}.sub{{color:#64748b;font-size:12px;margin-top:4px}}
table{{width:100%;border-collapse:collapse;font-size:12px}}
th{{text-align:left;color:#64748b;padding:6px 0;border-bottom:1px solid #334155}}
td{{padding:6px 0;border-bottom:1px solid #1e293b}}</style></head>
<body>
<div class="hdr"><h1>Model Architecture Benchmarker</h1><span>port {PORT} \u00b7 6 VLA architectures</span></div>
<div class="grid">
<div class="card"><h3>Best SR</h3><div class="stat">0.78</div><div class="sub">GR00T N1.6-3B \u00b7 226ms</div></div>
<div class="card"><h3>OCI Cost Advantage</h3><div class="stat">9.6\u00d7</div><div class="sub">GR00T on OCI vs AWS OpenVLA</div></div>
<div class="card"><h3>SR vs Latency (bubble=params)</h3>
<div style="font-size:11px;color:#64748b;margin-bottom:8px"><span style="color:#C74634">- -</span> Pareto frontier</div>
<svg width="100%" viewBox="0 0 450 120">{scatter}{pareto_svg}</svg></div>
<div class="card"><h3>Architecture Comparison</h3>
<table><tr><th>Model</th><th>SR</th><th>Latency</th><th>Params</th><th>OCI Multiplier</th></tr>{model_rows}</table></div>
</div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Model Architecture Benchmarker")
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
