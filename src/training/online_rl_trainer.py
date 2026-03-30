"""Online RL Trainer — FastAPI port 8352"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8352

def build_html():
    iters = list(range(0, 201, 5))
    sr = [round(min(0.72, 0.05 + 0.67*(1 - math.exp(-i/60))), 3) for i in iters]
    policy_loss = [round(max(0.08, 1.8*math.exp(-i/50) + 0.1*random.uniform(0.9,1.1)), 3) for i in iters]
    value_loss = [round(max(0.05, 1.2*math.exp(-i/45) + 0.08*random.uniform(0.9,1.1)), 3) for i in iters]
    random.seed(42)
    
    pts_sr = " ".join(f"{50+i*2.7},{180-sr[idx]*120}" for idx,i in enumerate(iters))
    pts_pl = " ".join(f"{50+i*2.7},{180-min(1,policy_loss[idx])*80}" for idx,i in enumerate(iters))
    pts_vl = " ".join(f"{50+i*2.7},{180-min(1,value_loss[idx])*80}" for idx,i in enumerate(iters))
    
    advantage_bars = ""
    for b in range(16):
        height = int(60 * abs(math.sin(b * 0.4)) * random.uniform(0.7, 1.3))
        color = "#22c55e" if b < 10 else "#C74634"
        advantage_bars += f'<rect x="{30 + b*22}" y="{200-height}" width="18" height="{height}" fill="{color}" opacity="0.85"/>'
    random.seed(42)

    return f"""<!DOCTYPE html><html><head><title>Online RL Trainer — Port {PORT}</title>
<style>body{{background:#0f172a;color:#e2e8f0;font-family:monospace;margin:0;padding:20px}}
h1{{color:#C74634;font-size:1.4em}}h2{{color:#38bdf8;font-size:1em}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:16px}}
.card{{background:#1e293b;border-radius:8px;padding:16px}}
.stat{{display:inline-block;margin:8px;text-align:center}}
.sv{{font-size:2em;font-weight:bold;color:#22c55e}}.sl{{font-size:0.75em;color:#94a3b8}}
svg{{width:100%;height:auto}}</style></head><body>
<h1>Online RL Trainer</h1>
<div style="display:flex;gap:24px;margin-bottom:16px">
<div class="stat"><div class="sv">72%</div><div class="sl">Final SR</div></div>
<div class="stat"><div class="sv">200</div><div class="sl">Iters</div></div>
<div class="stat"><div class="sv">64</div><div class="sl">Envs</div></div>
<div class="stat"><div class="sv">PPO</div><div class="sl">Algorithm</div></div>
<div class="stat"><div class="sv">0.95</div><div class="sl">GAE λ</div></div>
</div>
<div class="grid">
<div class="card"><h2>SR + Loss Curves</h2>
<svg viewBox="0 0 600 220"><rect width="600" height="220" fill="#0f172a" rx="4"/>
<line x1="50" y1="10" x2="50" y2="190" stroke="#334155" stroke-width="1"/>
<line x1="50" y1="190" x2="590" y2="190" stroke="#334155" stroke-width="1"/>
<text x="20" y="15" fill="#94a3b8" font-size="10">SR</text>
<polyline points="{pts_sr}" fill="none" stroke="#22c55e" stroke-width="2"/>
<text x="20" y="80" fill="#94a3b8" font-size="10">Loss</text>
<polyline points="{pts_pl}" fill="none" stroke="#C74634" stroke-width="1.5"/>
<polyline points="{pts_vl}" fill="none" stroke="#38bdf8" stroke-width="1.5"/>
<line x1="50" y1="{180 - 0.75*120}" x2="590" y2="{180 - 0.75*120}" stroke="#22c55e" stroke-dasharray="4,4" stroke-width="1" opacity="0.5"/>
<text x="555" y="{175 - 0.75*120}" fill="#22c55e" font-size="9">SR=0.75</text>
<text x="52" y="205" fill="#94a3b8" font-size="9">0</text>
<text x="297" y="205" fill="#94a3b8" font-size="9">100</text>
<text x="570" y="205" fill="#94a3b8" font-size="9">200</text>
<text x="280" y="215" fill="#64748b" font-size="9">Training Iterations</text>
</svg>
<div style="font-size:0.75em;color:#64748b;margin-top:8px">
<span style="color:#22c55e">■</span> SR &nbsp;
<span style="color:#C74634">■</span> Policy Loss &nbsp;
<span style="color:#38bdf8">■</span> Value Loss
</div>
</div>
<div class="card"><h2>Advantage Distribution (Latest Rollout)</h2>
<svg viewBox="0 0 400 240"><rect width="400" height="240" fill="#0f172a" rx="4"/>
<line x1="20" y1="200" x2="390" y2="200" stroke="#334155" stroke-width="1"/>
{advantage_bars}
<text x="10" y="215" fill="#94a3b8" font-size="9">-8σ</text>
<text x="180" y="215" fill="#94a3b8" font-size="9">0</text>
<text x="345" y="215" fill="#94a3b8" font-size="9">+8σ</text>
<text x="100" y="20" fill="#64748b" font-size="10">Advantage Distribution — 64 envs × 512 steps</text>
<text x="10" y="235" fill="#64748b" font-size="9">
<tspan fill="#22c55e">■</tspan> Positive advantage (explore)  
<tspan fill="#C74634">■</tspan> Negative (penalized)
</text>
</svg>
<div style="margin-top:12px;font-size:0.8em">
<div style="color:#94a3b8">Clipping events: <span style="color:#f59e0b">26 / 200 iters</span></div>
<div style="color:#94a3b8">Mean advantage: <span style="color:#22c55e">+0.14</span></div>
<div style="color:#94a3b8">Early stop threshold: <span style="color:#38bdf8">SR = 0.75</span></div>
</div>
</div>
</div>
<div class="card" style="margin-top:16px;font-size:0.8em;color:#64748b">
PPO | GAE λ=0.95 | clip_ε=0.2 | 64 parallel envs | rollout_steps=512 | lr=3e-4 cosine | entropy_coef=0.01
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Online RL Trainer")
    @app.get("/", response_class=HTMLResponse)
    def index(): return build_html()
    @app.get("/health")
    def health(): return {"status": "ok", "port": PORT, "algo": "PPO", "sr": 0.72, "iters": 200}

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
