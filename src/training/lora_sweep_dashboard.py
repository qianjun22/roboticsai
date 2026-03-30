"""LoRA Sweep Dashboard — FastAPI port 8465"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8465

def build_html():
    # rank × alpha heatmap
    ranks = [4, 8, 16, 32, 64]
    alphas = [8, 16, 32, 64, 128]
    sr_table = [
        [0.61, 0.65, 0.68, 0.66, 0.63],
        [0.67, 0.71, 0.74, 0.72, 0.69],
        [0.73, 0.76, 0.78, 0.77, 0.74],
        [0.71, 0.74, 0.76, 0.75, 0.72],
        [0.68, 0.71, 0.73, 0.72, 0.70],
    ]
    heat = ""
    cell = 46
    for i, r in enumerate(ranks):
        for j, a in enumerate(alphas):
            sr = sr_table[i][j]
            x = 50 + j * cell
            y = 15 + i * cell
            if sr >= 0.76:
                color = "#22c55e"
            elif sr >= 0.70:
                color = "#38bdf8"
            elif sr >= 0.65:
                color = "#f59e0b"
            else:
                color = "#C74634"
            heat += f'<rect x="{x}" y="{y}" width="{cell-2}" height="{cell-2}" fill="{color}" opacity="{0.25+sr*0.7:.2f}" rx="4"/>'
            heat += f'<text x="{x+cell//2-1}" y="{y+cell//2+5}" fill="#e2e8f0" font-size="10" text-anchor="middle" font-weight="bold">{int(sr*100)}</text>'
        heat += f'<text x="46" y="{15+i*cell+cell//2+4}" fill="#94a3b8" font-size="10" text-anchor="end">r={r}</text>'
    for j, a in enumerate(alphas):
        heat += f'<text x="{50+j*cell+cell//2-1}" y="12" fill="#64748b" font-size="10" text-anchor="middle">α={a}</text>'
    # star on optimal
    heat += f'<text x="{50+2*cell+cell//2-1}" y="{15+2*cell+cell//2+5}" fill="#0f172a" font-size="14" text-anchor="middle" font-weight="bold">★</text>'

    # LoRA vs full fine-tune tradeoff bars
    methods = ["LoRA r=4", "LoRA r=8", "LoRA r=16\n(optimal)", "LoRA r=32", "Full Fine-tune"]
    sr_vals = [0.68, 0.74, 0.78, 0.76, 0.79]
    vram_gb = [10.2, 11.8, 13.4, 16.1, 58.3]
    speed_x = [4.2, 3.1, 2.1, 1.8, 1.0]  # relative to full
    tradeoff = ""
    for i, (m, sr, vr, sp) in enumerate(zip(methods, sr_vals, vram_gb, speed_x)):
        y = 15 + i * 38
        w_sr = int(sr / 0.82 * 180)
        w_vr = int(vr / 62 * 180)
        label = m.replace("\\n", " ")
        tradeoff += f'<rect x="150" y="{y}" width="{w_sr}" height="14" fill="#C74634" rx="2" opacity="0.85"/>'
        tradeoff += f'<rect x="150" y="{y+16}" width="{w_vr}" height="10" fill="#64748b" rx="2" opacity="0.6"/>'
        tradeoff += f'<text x="146" y="{y+11}" fill="#94a3b8" font-size="9" text-anchor="end">{label}</text>'
        tradeoff += f'<text x="{150+w_sr+4}" y="{y+11}" fill="#e2e8f0" font-size="9">SR={int(sr*100)}% {sp}×</text>'

    return f"""<!DOCTYPE html>
<html>
<head><title>LoRA Sweep Dashboard</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',sans-serif}}
.hdr{{background:#1e293b;padding:16px 24px;border-bottom:2px solid #C74634;display:flex;align-items:center;gap:12px}}
.hdr h1{{margin:0;font-size:20px;color:#f1f5f9}}
.badge{{background:#C74634;color:#fff;padding:3px 10px;border-radius:12px;font-size:11px;font-weight:700}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;padding:20px}}
.card{{background:#1e293b;border-radius:10px;padding:18px;border:1px solid #334155}}
.card h3{{margin:0 0 12px;font-size:14px;color:#94a3b8;text-transform:uppercase;letter-spacing:.05em}}
.metrics{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;padding:16px 20px}}
.m{{background:#1e293b;border-radius:8px;padding:12px 16px;border:1px solid #334155}}
.mv{{font-size:24px;font-weight:700;color:#38bdf8}}
.ml{{font-size:11px;color:#64748b;margin-top:2px}}
.delta{{font-size:12px;color:#22c55e;margin-top:4px}}
</style>
</head>
<body>
<div class="hdr">
  <span class="badge">PORT {PORT}</span>
  <h1>LoRA Sweep Dashboard — Rank × Alpha Optimization</h1>
</div>
<div class="metrics">
  <div class="m"><div class="mv">r=16, α=32</div><div class="ml">Optimal Config</div></div>
  <div class="m"><div class="mv">78%</div><div class="ml">Optimal SR</div><div class="delta">98.7% of full fine-tune</div></div>
  <div class="m"><div class="mv">13.4GB</div><div class="ml">VRAM (vs 58.3GB full)</div><div class="delta">77% savings</div></div>
  <div class="m"><div class="mv">2.1×</div><div class="ml">Training Speed vs Full</div></div>
</div>
<div class="grid">
  <div class="card">
    <h3>Rank × Alpha SR Heatmap (★ = optimal)</h3>
    <svg viewBox="0 0 290 250" width="100%">
      {heat}
    </svg>
  </div>
  <div class="card">
    <h3>SR vs VRAM Tradeoff by Config</h3>
    <svg viewBox="0 0 420 210" width="100%">
      <line x1="148" y1="10" x2="148" y2="205" stroke="#334155" stroke-width="1"/>
      {tradeoff}
      <rect x="290" y="10" width="10" height="6" fill="#C74634" opacity="0.85"/>
      <text x="304" y="18" fill="#94a3b8" font-size="9">SR</text>
      <rect x="290" y="22" width="10" height="6" fill="#64748b" opacity="0.6"/>
      <text x="304" y="30" fill="#94a3b8" font-size="9">VRAM</text>
    </svg>
  </div>
</div>
</body>
</html>"""

if USE_FASTAPI:
    app = FastAPI(title="LoRA Sweep Dashboard")
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
