"""Action Prediction Horizon — FastAPI port 8496"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8496

def build_html():
    # SR vs prediction horizon
    horizons = list(range(1, 21))
    sr_groot = [0.52 + (0.78 - 0.52) * (1 - math.exp(-(h-1)/4)) - max(0, (h-8)*0.012) + random.uniform(-0.01,0.01) for h in horizons]
    sr_bc = [0.40 + (0.62 - 0.40) * (1 - math.exp(-(h-1)/5)) - max(0, (h-6)*0.015) + random.uniform(-0.01,0.01) for h in horizons]
    sr_groot = [max(0.1, min(0.85, v)) for v in sr_groot]
    sr_bc = [max(0.1, min(0.75, v)) for v in sr_bc]
    
    pts_groot = []
    pts_bc = []
    for i, (sg, sb) in enumerate(zip(sr_groot, sr_bc)):
        x = i * 500 / 19
        yg = 100 - sg * 100
        yb = 100 - sb * 100
        pts_groot.append(f"{x:.1f},{yg:.1f}")
        pts_bc.append(f"{x:.1f},{yb:.1f}")
    
    groot_svg = f'<polyline points="{" ".join(pts_groot)}" fill="none" stroke="#22c55e" stroke-width="2"/>'
    bc_svg = f'<polyline points="{" ".join(pts_bc)}" fill="none" stroke="#64748b" stroke-width="2" stroke-dasharray="5,3"/>'
    
    # optimal marker at horizon=8
    opt_x = 7 * 500 / 19
    opt_y = 100 - sr_groot[7] * 100
    opt_marker = f'<circle cx="{opt_x:.1f}" cy="{opt_y:.1f}" r="6" fill="#C74634"/>'
    opt_line = f'<line x1="{opt_x:.1f}" y1="0" x2="{opt_x:.1f}" y2="100" stroke="#C74634" stroke-width="1" stroke-dasharray="4,2"/>'
    
    # joint horizon heatmap
    joints = ["J1", "J2", "J3", "J4", "J5", "J6"]
    horizon_steps = [2, 4, 6, 8, 10, 12]
    heatmap = ""
    for row_i, joint in enumerate(joints):
        for col_i, h in enumerate(horizon_steps):
            acc = 0.95 - abs(h - 8) * 0.04 + row_i * 0.01 + random.uniform(-0.03, 0.03)
            acc = max(0.3, min(0.98, acc))
            col = "#22c55e" if acc > 0.85 else ("#f59e0b" if acc > 0.7 else "#ef4444")
            x = col_i * 55 + 5
            y = row_i * 20 + 5
            heatmap += f'<rect x="{x}" y="{y}" width="50" height="16" fill="{col}" opacity="{acc:.2f}" rx="2"/>'
            heatmap += f'<text x="{x+25}" y="{y+11}" text-anchor="middle" fill="white" font-size="9">{acc:.2f}</text>'
        heatmap += f'<text x="335" y="{row_i*20+15}" fill="#64748b" font-size="10">{joint}</text>'
    
    best_sr = max(sr_groot)
    best_h = sr_groot.index(best_sr) + 1
    
    return f"""<!DOCTYPE html><html><head><title>Action Prediction Horizon</title>
<style>body{{margin:0;font-family:monospace;background:#0f172a;color:#e2e8f0}}
.hdr{{background:#C74634;padding:16px 24px;display:flex;justify-content:space-between;align-items:center}}
.hdr h1{{margin:0;font-size:20px;color:#fff}}.hdr span{{color:#fca5a5;font-size:13px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;padding:20px}}
.card{{background:#1e293b;border-radius:8px;padding:16px}}
.card h3{{margin:0 0 12px;color:#38bdf8;font-size:14px;text-transform:uppercase;letter-spacing:1px}}
.stat{{font-size:36px;font-weight:bold;color:#f1f5f9}}.sub{{color:#64748b;font-size:12px;margin-top:4px}}</style></head>
<body>
<div class="hdr"><h1>Action Prediction Horizon</h1><span>port {PORT}</span></div>
<div class="grid">
<div class="card"><h3>Optimal Horizon</h3><div class="stat">{best_h} steps</div><div class="sub">SR={best_sr:.2f} peak · GR00T_v2</div></div>
<div class="card"><h3>vs BC</h3><div class="stat">{best_sr - max(sr_bc):.2f}</div><div class="sub">SR advantage at optimal horizon</div></div>
<div class="card" style="grid-column:span 2"><h3>SR vs Prediction Horizon (1–20 steps)</h3>
<div style="font-size:11px;color:#64748b;margin-bottom:8px"><span style="color:#22c55e">—</span> GR00T_v2 <span style="color:#64748b;margin-left:8px">- -</span> BC <span style="color:#C74634;margin-left:8px">● optimal (step 8)</span></div>
<svg width="100%" viewBox="0 0 500 100">{groot_svg}{bc_svg}{opt_line}{opt_marker}</svg></div>
<div class="card" style="grid-column:span 2"><h3>Per-Joint Horizon Accuracy Heatmap</h3>
<div style="font-size:11px;color:#64748b;margin-bottom:6px">Horizon: {" | ".join(str(h) for h in horizon_steps)}</div>
<svg width="100%" viewBox="0 0 350 125">{heatmap}</svg></div>
</div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Action Prediction Horizon")
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
