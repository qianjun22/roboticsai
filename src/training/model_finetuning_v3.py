"""Model Finetuning v3 — FastAPI port 8408"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8408

def build_html():
    # 6-stage pipeline diagram
    stages = ["Freeze_backbone","Thaw_LLM","LoRA_r16","Full_finetune","Eval_gate","Promote"]
    stage_status = ["DONE","DONE","DONE","RUNNING","PENDING","PENDING"]
    stage_colors = {"DONE":"#22c55e","RUNNING":"#f59e0b","PENDING":"#475569"}

    svg_p = '<svg width="420" height="80" style="background:#0f172a">'
    sw = 55
    for i, (st, status) in enumerate(zip(stages, stage_status)):
        x = 10 + i*(sw+12); col = stage_colors[status]
        svg_p += f'<rect x="{x}" y="20" width="{sw}" height="36" fill="{col}" rx="4" opacity="0.85"/>'
        svg_p += f'<text x="{x+sw//2}" y="36" fill="white" font-size="7" text-anchor="middle">{st.split("_")[0]}</text>'
        svg_p += f'<text x="{x+sw//2}" y="48" fill="white" font-size="7" text-anchor="middle">{st.split("_")[1] if "_" in st else ""}</text>'
        svg_p += f'<text x="{x+sw//2}" y="68" fill="{col}" font-size="7" text-anchor="middle">{status}</text>'
        if i < len(stages)-1:
            svg_p += f'<line x1="{x+sw}" y1="38" x2="{x+sw+12}" y2="38" stroke="#94a3b8" stroke-width="1.5" marker-end="url(#arr)"/>'
    svg_p += '</svg>'

    # HPO surface: lr × rank → SR (25 configs)
    lrs = [1e-5, 3e-5, 1e-4, 3e-4, 1e-3]
    ranks = [4, 8, 16, 32, 64]
    sr_surface = [[max(0.3, min(0.85, 0.40 + 0.18*math.exp(-((math.log10(lr)+4.5)**2)/0.5) + 0.12*math.exp(-((r-16)**2)/200))) for lr in lrs] for r in ranks]

    cw2 = 44; rh2 = 26
    svg_h2 = f'<svg width="{len(lrs)*cw2+80}" height="{len(ranks)*rh2+60}" style="background:#0f172a">'
    for li, lr in enumerate(lrs):
        svg_h2 += f'<text x="{80+li*cw2+22}" y="18" fill="#94a3b8" font-size="8" text-anchor="middle">{lr:.0e}</text>'
    for ri, r in enumerate(ranks):
        svg_h2 += f'<text x="75" y="{36+ri*rh2+14}" fill="#94a3b8" font-size="9" text-anchor="end">r={r}</text>'
        for li, lr in enumerate(lrs):
            sr = sr_surface[ri][li]
            g = int(200*sr); red = int(255*(1-sr))
            svg_h2 += f'<rect x="{80+li*cw2}" y="{30+ri*rh2}" width="{cw2-2}" height="{rh2-2}" fill="rgb({red},{g},80)" opacity="0.85"/>'
            star = "★" if (li==1 and ri==2) else ""
            svg_h2 += f'<text x="{80+li*cw2+22}" y="{30+ri*rh2+15}" fill="white" font-size="8" text-anchor="middle">{sr:.2f}{star}</text>'
    svg_h2 += '<text x="10" y="90" fill="#94a3b8" font-size="8" transform="rotate(-90,10,90)">LoRA rank</text>'
    svg_h2 += f'<text x="{80+len(lrs)*cw2//2}" y="{30+len(ranks)*rh2+20}" fill="#94a3b8" font-size="9" text-anchor="middle">Learning Rate</text>'
    svg_h2 += '</svg>'

    return f"""<!DOCTYPE html><html><head><title>Model Finetuning v3 — Port {PORT}</title>
<style>body{{background:#0f172a;color:#e2e8f0;font-family:monospace;margin:0;padding:20px}}
h1{{color:#C74634;font-size:18px}}h2{{color:#38bdf8;font-size:14px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:20px}}
.card{{background:#1e293b;padding:16px;border-radius:8px}}
.stat{{font-size:24px;color:#C74634;font-weight:bold}}
.label{{color:#94a3b8;font-size:12px}}</style></head>
<body><h1>Model Finetuning v3</h1>
<p style="color:#94a3b8">Port {PORT} | GR00T N1.6 → v3 pipeline | 1000 demos + 5000 steps + LoRA r=16</p>
<div class="card" style="margin-bottom:16px"><h2>Pipeline Stages</h2>{svg_p}</div>
<div class="grid">
<div class="card"><h2>HPO Surface: LR × Rank → SR</h2>{svg_h2}</div>
<div class="card">
<div class="stat">0.83</div><div class="label">Target SR for v3 (est.)</div>
<div class="stat" style="color:#38bdf8;margin-top:12px">3e-5 / r=16</div><div class="label">Optimal LR / LoRA rank (★)</div>
<div class="stat" style="color:#22c55e;margin-top:12px">5000</div><div class="label">Training steps</div>
<div style="margin-top:12px;color:#94a3b8;font-size:11px">v1: SR=0.05 (BC baseline)<br>v2: SR=0.78 (DAgger+LoRA)<br>v3: SR=0.83 target (+6.4% vs v2)<br>Freeze backbone 500 steps → thaw 1000 → full 3500<br>Promote gate: SR &gt; 0.80 AND latency &lt; 240ms</div>
</div></div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Model Finetuning v3")
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
