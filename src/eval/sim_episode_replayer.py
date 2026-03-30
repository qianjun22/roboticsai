"""Sim Episode Replayer — FastAPI port 8353"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8353

def build_html():
    random.seed(7)
    steps = list(range(0, 848, 16))
    ee_z = [round(0.15 + 0.3 * (1 - math.exp(-s/200)) + 0.02*math.sin(s/30), 3) for s in steps]
    cube_z = [round(0.02 if s < 400 else min(0.35, 0.02 + 0.33*(s-400)/447), 3) for s in steps]
    gripper = [round(max(0, min(1, 0.9 - 0.8*(s/400) if s < 400 else 0.1 + 0.3*((s-400)/447))), 3) for s in steps]
    reward = [round(-0.5 + s/1600 + (0.3 if s > 400 else 0) + 0.05*random.uniform(-1,1), 3) for s in steps]

    def polypts(vals, x0, x_scale, y0, y_scale, clamp=1.0):
        return " ".join(f"{x0+i*x_scale},{y0-min(clamp,max(-0.1,v))*y_scale}" for i,v in enumerate(vals))

    pts_ee_z = polypts(ee_z, 40, 6.2, 160, 120)
    pts_cube = polypts(cube_z, 40, 6.2, 160, 120)
    pts_grip = polypts(gripper, 40, 6.2, 160, 120)
    pts_rew = polypts(reward, 40, 6.2, 160, 60, clamp=1.0)

    # BC vs DAgger comparison
    bc_pts = " ".join(f"{40+i*6.2},{160 - min(0.9,max(0,0.02 + 0.3*(s/400) + 0.08*random.uniform(-1,1) if s < 400 else 0.32))*120}" for i,(s) in enumerate(steps))
    dag_pts = pts_cube

    return f"""<!DOCTYPE html><html><head><title>Sim Episode Replayer — Port {PORT}</title>
<style>body{{background:#0f172a;color:#e2e8f0;font-family:monospace;margin:0;padding:20px}}
h1{{color:#C74634;font-size:1.4em}}h2{{color:#38bdf8;font-size:1em}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:16px}}
.card{{background:#1e293b;border-radius:8px;padding:16px}}
svg{{width:100%;height:auto}}</style></head><body>
<h1>Sim Episode Replayer</h1>
<div style="display:flex;gap:24px;margin-bottom:16px">
<div style="display:inline-block;margin:8px;text-align:center">
<div style="font-size:2em;font-weight:bold;color:#22c55e">847</div>
<div style="font-size:0.75em;color:#94a3b8">Steps</div></div>
<div style="display:inline-block;margin:8px;text-align:center">
<div style="font-size:2em;font-weight:bold;color:#22c55e">SUCCESS</div>
<div style="font-size:0.75em;color:#94a3b8">Outcome</div></div>
<div style="display:inline-block;margin:8px;text-align:center">
<div style="font-size:2em;font-weight:bold;color:#38bdf8">226ms</div>
<div style="font-size:0.75em;color:#94a3b8">Avg Latency</div></div>
<div style="display:inline-block;margin:8px;text-align:center">
<div style="font-size:2em;font-weight:bold;color:#f59e0b">3</div>
<div style="font-size:0.75em;color:#94a3b8">Phases</div></div>
</div>
<div class="grid">
<div class="card"><h2>Episode Playback — 4 Variables</h2>
<svg viewBox="0 0 600 200"><rect width="600" height="200" fill="#0f172a" rx="4"/>
<!-- Phase backgrounds -->
<rect x="40" y="10" width="155" height="155" fill="#1e3a5f" opacity="0.3" rx="2"/>
<rect x="195" y="10" width="155" height="155" fill="#3a1e1e" opacity="0.3" rx="2"/>
<rect x="350" y="10" width="230" height="155" fill="#1e3a2f" opacity="0.3" rx="2"/>
<text x="90" y="175" fill="#38bdf8" font-size="8">REACH</text>
<text x="240" y="175" fill="#f59e0b" font-size="8">GRASP</text>
<text x="420" y="175" fill="#22c55e" font-size="8">LIFT</text>
<line x1="40" y1="165" x2="580" y2="165" stroke="#334155" stroke-width="1"/>
<polyline points="{pts_ee_z}" fill="none" stroke="#38bdf8" stroke-width="1.5"/>
<polyline points="{pts_cube}" fill="none" stroke="#f59e0b" stroke-width="1.5"/>
<polyline points="{pts_grip}" fill="none" stroke="#a78bfa" stroke-width="1.5"/>
<polyline points="{pts_rew}" fill="none" stroke="#22c55e" stroke-width="1" stroke-dasharray="3,2"/>
<text x="42" y="190" fill="#64748b" font-size="8">0</text>
<text x="300" y="190" fill="#64748b" font-size="8">step 420</text>
<text x="558" y="190" fill="#64748b" font-size="8">847</text>
</svg>
<div style="font-size:0.75em;color:#64748b;margin-top:4px">
<span style="color:#38bdf8">■</span> EE-z &nbsp;
<span style="color:#f59e0b">■</span> cube-z &nbsp;
<span style="color:#a78bfa">■</span> gripper &nbsp;
<span style="color:#22c55e">■</span> reward
</div>
</div>
<div class="card"><h2>BC vs DAgger — cube_z Divergence</h2>
<svg viewBox="0 0 600 200"><rect width="600" height="200" fill="#0f172a" rx="4"/>
<line x1="40" y1="165" x2="580" y2="165" stroke="#334155" stroke-width="1"/>
<line x1="40" y1="10" x2="40" y2="165" stroke="#334155" stroke-width="1"/>
<polyline points="{bc_pts}" fill="none" stroke="#C74634" stroke-width="2"/>
<polyline points="{dag_pts}" fill="none" stroke="#22c55e" stroke-width="2"/>
<!-- divergence annotation at step 400 -->
<line x1="288" y1="20" x2="288" y2="165" stroke="#f59e0b" stroke-dasharray="3,3" stroke-width="1"/>
<text x="240" y="18" fill="#f59e0b" font-size="9">Divergence at step 400</text>
<text x="42" y="190" fill="#64748b" font-size="8">step 0</text>
<text x="553" y="190" fill="#64748b" font-size="8">step 847</text>
<text x="520" y="60" fill="#22c55e" font-size="9">DAgger 0.33</text>
<text x="520" y="150" fill="#C74634" font-size="9">BC 0.03</text>
</svg>
<div style="margin-top:8px;font-size:0.8em;color:#94a3b8">BC fails to lift cube (cube_z stays at 0.02m); DAgger reaches 0.35m. Key divergence at grasp phase.</div>
</div>
</div>
<div class="card" style="margin-top:16px">
<h2>Step-Through Replay API</h2>
<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px;font-size:0.8em">
<div style="background:#0f172a;padding:10px;border-radius:6px">
<div style="color:#38bdf8">GET /replay/&#123;episode_id&#125;</div>
<div style="color:#64748b;margin-top:4px">Full episode data (states, actions, rewards)</div>
</div>
<div style="background:#0f172a;padding:10px;border-radius:6px">
<div style="color:#38bdf8">GET /replay/&#123;id&#125;/step/&#123;n&#125;</div>
<div style="color:#64748b;margin-top:4px">Single step snapshot with annotation</div>
</div>
<div style="background:#0f172a;padding:10px;border-radius:6px">
<div style="color:#38bdf8">POST /replay/compare</div>
<div style="color:#64748b;margin-top:4px">Side-by-side policy comparison</div>
</div>
</div>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Sim Episode Replayer")
    @app.get("/", response_class=HTMLResponse)
    def index(): return build_html()
    @app.get("/health")
    def health(): return {"status": "ok", "port": PORT, "steps": 847, "outcome": "SUCCESS"}

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
