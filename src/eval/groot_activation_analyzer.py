"""GR00T Activation Analyzer — FastAPI port 8489"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8489

def build_html():
    # per-layer activation norms
    layers = list(range(1, 13))
    norms = [2.1, 2.8, 3.4, 4.1, 3.9, 4.7, 4.3, 5.1, 4.8, 3.2, 2.7, 1.9]
    probe_acc = [0.41, 0.52, 0.61, 0.68, 0.72, 0.76, 0.79, 0.84, 0.81, 0.74, 0.69, 0.63]
    
    max_norm = max(norms)
    norm_bars = ""
    for i, (layer, norm, acc) in enumerate(zip(layers, norms, probe_acc)):
        col = "#38bdf8" if i == 7 else "#64748b"
        w = norm / max_norm * 300
        norm_bars += f'''<div style="display:flex;align-items:center;margin-bottom:4px">
<span style="width:60px;color:#64748b;font-size:11px">Layer {layer}</span>
<div style="background:#334155;border-radius:2px;height:10px;width:{w:.0f}px">
<div style="background:{col};width:100%;height:10px;border-radius:2px"></div></div>
<span style="margin-left:8px;color:{col};font-size:11px">{norm:.1f}</span>
<span style="margin-left:16px;color:#22c55e;font-size:11px">probe {acc:.2f}</span>
</div>'''
    
    # PCA scatter simulation
    tasks = [
        ("pick_place", "#22c55e", [(1.2, 0.8), (1.5, 0.9), (1.1, 1.1), (1.3, 0.7), (1.4, 1.0)]),
        ("stack", "#38bdf8", [(-0.8, 1.2), (-1.0, 0.9), (-0.7, 1.3), (-0.9, 1.0), (-1.1, 1.1)]),
        ("pour", "#f59e0b", [(0.2, -1.4), (0.4, -1.2), (0.1, -1.5), (0.3, -1.1), (0.5, -1.3)]),
        ("wipe", "#a78bfa", [(-0.5, -0.8), (-0.3, -1.0), (-0.6, -0.7), (-0.4, -0.9), (-0.7, -0.8)]),
    ]
    
    scatter_pts = ""
    cx, cy = 150, 100
    scale = 40
    for task, col, pts in tasks:
        for px, py in pts:
            sx = cx + px * scale
            sy = cy - py * scale
            scatter_pts += f'<circle cx="{sx:.1f}" cy="{sy:.1f}" r="5" fill="{col}" opacity="0.8"/>'
    
    scatter_pts += f'<line x1="0" y1="{cy}" x2="300" y2="{cy}" stroke="#334155" stroke-width="1"/>'
    scatter_pts += f'<line x1="{cx}" y1="0" x2="{cx}" y2="200" stroke="#334155" stroke-width="1"/>'
    scatter_pts += f'<text x="270" y="{cy-5}" fill="#64748b" font-size="10">PC1</text>'
    scatter_pts += f'<text x="{cx+5}" y="15" fill="#64748b" font-size="10">PC2</text>'
    
    legend = "".join([f'<span style="margin-right:8px"><span style="color:{c}">●</span> {n}</span>' for n,c,_ in tasks])
    
    return f"""<!DOCTYPE html><html><head><title>GR00T Activation Analyzer</title>
<style>body{{margin:0;font-family:monospace;background:#0f172a;color:#e2e8f0}}
.hdr{{background:#C74634;padding:16px 24px;display:flex;justify-content:space-between;align-items:center}}
.hdr h1{{margin:0;font-size:20px;color:#fff}}.hdr span{{color:#fca5a5;font-size:13px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;padding:20px}}
.card{{background:#1e293b;border-radius:8px;padding:16px}}
.card h3{{margin:0 0 12px;color:#38bdf8;font-size:14px;text-transform:uppercase;letter-spacing:1px}}
.stat{{font-size:36px;font-weight:bold;color:#f1f5f9}}.sub{{color:#64748b;font-size:12px;margin-top:4px}}</style></head>
<body>
<div class="hdr"><h1>GR00T Activation Analyzer</h1><span>port {PORT} · 12-layer ViT-LLM</span></div>
<div class="grid">
<div class="card"><h3>Best Probe Layer</h3><div class="stat">8</div><div class="sub">probe acc 0.84 · grasp geometry</div></div>
<div class="card"><h3>Task Cluster Purity</h3><div class="stat">0.91</div><div class="sub">PCA PC1+PC2 separation</div></div>
<div class="card"><h3>Layer Norms + Probe Accuracy</h3>
<div style="font-size:11px;color:#38bdf8;margin-bottom:8px">★ Layer 8: best grasp geometry probe (0.84)</div>
{norm_bars}</div>
<div class="card"><h3>Activation PCA (Layer 8)</h3>
<div style="font-size:11px;margin-bottom:8px">{legend}</div>
<svg width="100%" viewBox="0 0 300 200">{scatter_pts}</svg></div>
</div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="GR00T Activation Analyzer")
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
