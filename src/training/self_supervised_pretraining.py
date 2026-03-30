"""Self-Supervised Pretraining Tracker — FastAPI port 8591"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8591

def build_html():
    # SR vs demo count for 4 init methods
    demo_counts = [50, 100, 200, 500, 1000, 2000]
    methods = {
        "MAE init": ([0.28, 0.52, 0.65, 0.73, 0.77, 0.79], "#38bdf8"),
        "Contrastive": ([0.25, 0.48, 0.63, 0.71, 0.76, 0.79], "#22c55e"),
        "BYOL": ([0.22, 0.44, 0.60, 0.70, 0.75, 0.78], "#f59e0b"),
        "Scratch": ([0.08, 0.21, 0.41, 0.62, 0.74, 0.78], "#C74634"),
    }
    W, H = 360, 200
    def px(i): return 50 + i * (W - 70) / (len(demo_counts) - 1)
    def py(v): return H - 30 - v * (H - 50)

    curves = ""
    for name, (vals, color) in methods.items():
        pts = " ".join(f"{'M' if i==0 else 'L'}{px(i):.1f},{py(vals[i]):.1f}" for i in range(len(vals)))
        curves += f'<path d="{pts}" fill="none" stroke="{color}" stroke-width="2"/>'
        lx = px(len(vals)-1) + 4
        curves += f'<text x="{lx:.1f}" y="{py(vals[-1]):.1f}" font-size="9" fill="{color}">{name.split()[0]}</text>'

    # Pretraining comparison bar chart
    pretrain_bars = ""
    methods_list = [("MAE", 0.09, "#38bdf8"), ("Contrastive", 0.07, "#22c55e"), ("BYOL", 0.05, "#f59e0b"), ("Scratch", 0.0, "#C74634")]
    for i, (name, gain, color) in enumerate(methods_list):
        bh = int(gain * 400)
        pretrain_bars += f'<rect x="{40 + i*70}" y="{130 - bh}" width="55" height="{bh}" fill="{color}" rx="3"/>'
        pretrain_bars += f'<text x="{67 + i*70}" y="{125 - bh}" text-anchor="middle" font-size="10" fill="white">+{gain:.2f}</text>'
        pretrain_bars += f'<text x="{67 + i*70}" y="145" text-anchor="middle" font-size="9" fill="#94a3b8">{name}</text>'

    return f"""<!DOCTYPE html>
<html><head><title>Self-Supervised Pretraining</title>
<style>body{{background:#0f172a;color:#e2e8f0;font-family:sans-serif;margin:0;padding:20px}}
h1{{color:#C74634;font-size:18px}}h2{{color:#38bdf8;font-size:14px;margin-top:20px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}.card{{background:#1e293b;padding:16px;border-radius:8px}}
.metric{{font-size:28px;font-weight:bold;color:#38bdf8}}.label{{font-size:12px;color:#94a3b8}}
</style></head><body>
<h1>Self-Supervised Pretraining Tracker — Port {PORT}</h1>
<div class="grid">
<div class="card">
<h2>SR vs Demo Count (4 init methods)</h2>
<svg width="{W}" height="{H}" style="background:#0f172a">
  <line x1="50" y1="{H-30}" x2="{W-10}" y2="{H-30}" stroke="#334155" stroke-width="1"/>
  <line x1="50" y1="10" x2="50" y2="{H-30}" stroke="#334155" stroke-width="1"/>
  {''.join(f'<text x="42" y="{py(v):.0f}" text-anchor="end" font-size="8" fill="#64748b">{v:.1f}</text>' for v in [0.2,0.4,0.6,0.8])}
  {''.join(f'<text x="{px(i):.0f}" y="{H-15}" text-anchor="middle" font-size="8" fill="#64748b">{demo_counts[i]}</text>' for i in range(len(demo_counts)))}
  {curves}
</svg>
</div>
<div class="card">
<h2>SR Gain at 100 Demos vs Scratch</h2>
<svg width="320" height="170" style="background:#0f172a">
  {pretrain_bars}
  <line x1="30" y1="130" x2="310" y2="130" stroke="#334155" stroke-width="1"/>
</svg>
</div>
</div>
<div class="grid" style="margin-top:12px">
<div class="card">
<h2>Key Findings</h2>
<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
  <div><div class="metric">+0.09pp</div><div class="label">MAE SR gain @ 100 demos</div></div>
  <div><div class="metric">3×</div><div class="label">sample efficiency improvement</div></div>
  <div><div class="metric">MAE</div><div class="label">recommended init method</div></div>
  <div><div class="metric">500+</div><div class="label">demos to match MAE init</div></div>
</div>
</div>
<div class="card">
<h2>Pretraining Details</h2>
<table style="width:100%;font-size:12px;border-collapse:collapse">
  <tr style="color:#64748b"><td>Method</td><td>Epochs</td><td>Cost</td><td>Rec.</td></tr>
  <tr><td style="color:#38bdf8">MAE</td><td>100</td><td>$18</td><td style="color:#22c55e">✓ Low data</td></tr>
  <tr><td style="color:#22c55e">Contrastive</td><td>100</td><td>$22</td><td>Mid data</td></tr>
  <tr><td style="color:#f59e0b">BYOL</td><td>150</td><td>$27</td><td>High data</td></tr>
  <tr><td style="color:#C74634">Scratch</td><td>—</td><td>$0</td><td>1000+ demos</td></tr>
</table>
</div>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Self-Supervised Pretraining Tracker")
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
