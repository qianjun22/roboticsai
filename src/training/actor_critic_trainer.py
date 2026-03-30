"""Actor-Critic Trainer — FastAPI port 8405"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8405

def build_html():
    # Actor + critic loss over 500 iters
    iters = list(range(0, 501, 10))
    actor_loss = [2.1*math.exp(-i/200)+0.12+random.uniform(-0.04,0.04) for i in iters]
    critic_loss = [4.2*math.exp(-i/150)+0.31+random.uniform(-0.08,0.08) for i in iters]

    svg_l = '<svg width="360" height="200" style="background:#0f172a">'
    svg_l += '<line x1="50" y1="10" x2="50" y2="170" stroke="#475569" stroke-width="1"/>'
    svg_l += '<line x1="50" y1="170" x2="340" y2="170" stroke="#475569" stroke-width="1"/>'
    # left axis actor, right axis critic
    for i in range(5):
        yv = i*0.5; y = 170-yv*130/2.5
        svg_l += f'<text x="45" y="{y+4}" fill="#C74634" font-size="7" text-anchor="end">{yv:.1f}</text>'
    for i in range(5):
        yv = i*1.0; y = 170-yv*130/5.0
        svg_l += f'<text x="345" y="{y+4}" fill="#38bdf8" font-size="7">{yv:.1f}</text>'
    # Critic converge annotation at iter 280
    cx = 50 + 280/500*280; cy = 170 - (0.31+0.05)*130/5.0
    svg_l += f'<line x1="{cx:.0f}" y1="{cy:.0f}" x2="{cx:.0f}" y2="60" stroke="#22c55e" stroke-width="1" stroke-dasharray="3,2"/>'
    svg_l += f'<text x="{cx+3:.0f}" y="58" fill="#22c55e" font-size="8">Critic converged (iter 280)</text>'
    # Plot actor
    pts_a = [(50+i/500*280, 170-al*130/2.5) for i, al in zip(iters, actor_loss)]
    for j in range(len(pts_a)-1):
        x1,y1=pts_a[j]; x2,y2=pts_a[j+1]
        svg_l += f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#C74634" stroke-width="1.5"/>'
    # Plot critic
    pts_c = [(50+i/500*280, 170-cl*130/5.0) for i, cl in zip(iters, critic_loss)]
    for j in range(len(pts_c)-1):
        x1,y1=pts_c[j]; x2,y2=pts_c[j+1]
        svg_l += f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#38bdf8" stroke-width="1.5"/>'
    svg_l += '<rect x="200" y="12" width="8" height="6" fill="#C74634"/><text x="212" y="18" fill="#C74634" font-size="8">Actor loss</text>'
    svg_l += '<rect x="200" y="24" width="8" height="6" fill="#38bdf8"/><text x="212" y="30" fill="#38bdf8" font-size="8">Critic loss (right axis)</text>'
    svg_l += '<text x="190" y="190" fill="#94a3b8" font-size="9" text-anchor="middle">Training Iterations</text>'
    svg_l += '</svg>'

    # Advantage distribution histogram
    adv_bins = [f"{-3+i*0.5:.1f}" for i in range(13)]
    adv_counts = [2,5,9,18,28,35,32,25,16,9,5,2,1]
    clip_thresh = 0.2
    svg_a = '<svg width="360" height="180" style="background:#0f172a">'
    svg_a += '<line x1="30" y1="10" x2="30" y2="150" stroke="#475569" stroke-width="1"/>'
    svg_a += '<line x1="30" y1="150" x2="340" y2="150" stroke="#475569" stroke-width="1"/>'
    bw3 = 23
    for bi, (lab, cnt) in enumerate(zip(adv_bins, adv_counts)):
        x = 32 + bi*bw3
        h = cnt*3; col = "#f59e0b" if bi in [3,4] else "#38bdf8"
        svg_a += f'<rect x="{x}" y="{150-h}" width="{bw3-2}" height="{h}" fill="{col}" opacity="0.8"/>'
        if bi % 3 == 0:
            svg_a += f'<text x="{x+bw3//2}" y="163" fill="#94a3b8" font-size="7" text-anchor="middle">{lab}</text>'
    svg_a += '<text x="190" y="175" fill="#94a3b8" font-size="9" text-anchor="middle">Normalized Advantage (clipping events highlighted)</text>'
    svg_a += '</svg>'

    return f"""<!DOCTYPE html><html><head><title>Actor-Critic Trainer — Port {PORT}</title>
<style>body{{background:#0f172a;color:#e2e8f0;font-family:monospace;margin:0;padding:20px}}
h1{{color:#C74634;font-size:18px}}h2{{color:#38bdf8;font-size:14px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:20px}}
.card{{background:#1e293b;padding:16px;border-radius:8px}}
.stat{{font-size:24px;color:#C74634;font-weight:bold}}
.label{{color:#94a3b8;font-size:12px}}</style></head>
<body><h1>Actor-Critic Trainer</h1>
<p style="color:#94a3b8">Port {PORT} | PPO actor-critic training for robotic manipulation</p>
<div class="grid">
<div class="card"><h2>Actor + Critic Loss Curves</h2>{svg_l}</div>
<div class="card"><h2>Advantage Distribution</h2>{svg_a}
<div style="margin-top:8px">
<div class="stat">280</div><div class="label">Critic convergence iteration</div>
<div class="stat" style="color:#38bdf8;margin-top:8px">0.2</div><div class="label">PPO clip ratio (ε)</div>
<div style="margin-top:8px;color:#94a3b8;font-size:11px">GAE λ=0.95, γ=0.99<br>64-env parallel rollout<br>Clip events at iter 45/127 (early instability)<br>Early stop at SR=75% (est. iter 420)</div>
</div></div></div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Actor-Critic Trainer")
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
