"""Observation Encoder Benchmark — FastAPI port 8424"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8424

def build_html():
    encoders = ["ViT-S/16","ViT-B/16","ViT-L/16","DINOv2-B","CLIP-B","Custom-CNN"]
    sr_vals =  [0.69, 0.78, 0.80, 0.76, 0.73, 0.64]
    lat_vals = [21, 42, 89, 38, 45, 15]
    param_m =  [22, 86, 307, 86, 86, 12]
    colors_enc = ["#94a3b8","#C74634","#f59e0b","#38bdf8","#a78bfa","#22c55e"]

    # SR+latency scatter (Pareto)
    svg_sc = '<svg width="320" height="220" style="background:#0f172a">'
    svg_sc += '<line x1="40" y1="10" x2="40" y2="170" stroke="#475569" stroke-width="1"/>'
    svg_sc += '<line x1="40" y1="170" x2="300" y2="170" stroke="#475569" stroke-width="1"/>'
    for i in range(5):
        yv = 0.6+i*0.05; y = 170-(yv-0.6)/0.25*140
        svg_sc += f'<text x="35" y="{y+4}" fill="#94a3b8" font-size="7" text-anchor="end">{yv:.2f}</text>'
    for i in range(5):
        xv = i*25; x = 40+xv*240/100
        svg_sc += f'<text x="{x}" y="183" fill="#94a3b8" font-size="7" text-anchor="middle">{xv}</text>'
    # Pareto frontier line
    pareto_pts = sorted(zip(lat_vals, sr_vals), key=lambda x: x[0])
    pareto_front = []
    max_sr = 0
    for lat, sr in pareto_pts:
        if sr >= max_sr:
            pareto_front.append((lat, sr))
            max_sr = sr
    pf = [(40+lat*240/100, 170-(sr-0.6)/0.25*140) for lat,sr in pareto_front]
    for j in range(len(pf)-1):
        x1,y1=pf[j]; x2,y2=pf[j+1]
        svg_sc += f'<line x1="{x1:.0f}" y1="{y1:.0f}" x2="{x2:.0f}" y2="{y2:.0f}" stroke="#22c55e" stroke-width="1" stroke-dasharray="3,2" opacity="0.5"/>'
    for enc, sr, lat, pm, col in zip(encoders, sr_vals, lat_vals, param_m, colors_enc):
        cx = 40+lat*240/100; cy = 170-(sr-0.6)/0.25*140
        r = max(4, min(12, pm//30))
        svg_sc += f'<circle cx="{cx:.0f}" cy="{cy:.0f}" r="{r}" fill="{col}" opacity="0.8"/>'
        svg_sc += f'<text x="{cx+r+2:.0f}" y="{cy+4:.0f}" fill="{col}" font-size="7">{enc[:5]}</text>'
    svg_sc += '<text x="170" y="198" fill="#94a3b8" font-size="9" text-anchor="middle">Latency (ms)</text>'
    svg_sc += '<text x="12" y="90" fill="#94a3b8" font-size="9" text-anchor="middle" transform="rotate(-90,12,90)">SR</text>'
    svg_sc += '</svg>'

    # Ablation bar (wrist/overhead/proprio/force contribution)
    modalities = ["wrist_rgb","overhead_rgb","proprioception","force_torque"]
    contributions = [0.41, 0.28, 0.19, 0.08]
    mod_colors = ["#C74634","#38bdf8","#22c55e","#f59e0b"]
    svg_ab = '<svg width="320" height="180" style="background:#0f172a">'
    for mi, (mod, cont, col) in enumerate(zip(modalities, contributions, mod_colors)):
        y = 20+mi*36; w = int(cont*600)
        svg_ab += f'<rect x="120" y="{y}" width="{w}" height="26" fill="{col}" opacity="0.85" rx="3"/>'
        svg_ab += f'<text x="115" y="{y+17}" fill="#94a3b8" font-size="9" text-anchor="end">{mod}</text>'
        svg_ab += f'<text x="{122+w}" y="{y+17}" fill="white" font-size="9">{cont:.0%}</text>'
    svg_ab += '<text x="190" y="170" fill="#94a3b8" font-size="9" text-anchor="middle">SR Contribution (ablation)</text>'
    svg_ab += '</svg>'

    return f"""<!DOCTYPE html><html><head><title>Obs Encoder Benchmark — Port {PORT}</title>
<style>body{{background:#0f172a;color:#e2e8f0;font-family:monospace;margin:0;padding:20px}}
h1{{color:#C74634;font-size:18px}}h2{{color:#38bdf8;font-size:14px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:20px}}
.card{{background:#1e293b;padding:16px;border-radius:8px}}
.stat{{font-size:24px;color:#C74634;font-weight:bold}}
.label{{color:#94a3b8;font-size:12px}}</style></head>
<body><h1>Observation Encoder Benchmark</h1>
<p style="color:#94a3b8">Port {PORT} | 6-encoder SR vs latency Pareto + modality ablation</p>
<div class="grid">
<div class="card"><h2>SR vs Latency (bubble=params)</h2>{svg_sc}
<div class="stat">ViT-B/16</div><div class="label">Optimal: SR=0.78, 42ms, 86M params</div></div>
<div class="card"><h2>Modality Contribution</h2>{svg_ab}
<div style="margin-top:8px">
<div class="stat">41%</div><div class="label">wrist_rgb top contributor</div>
<div style="margin-top:8px;color:#94a3b8;font-size:11px">ViT-L: marginal +0.02 SR at +47ms cost<br>DINOv2: good SR but slower than ViT-B<br>Custom-CNN: fast (15ms) but -14pp SR vs ViT-B<br>Force-torque: +8pp for contact-heavy tasks only</div>
</div></div></div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Obs Encoder Benchmark")
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
