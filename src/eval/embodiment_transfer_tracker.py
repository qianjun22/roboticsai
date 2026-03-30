"""Embodiment Transfer Tracker — FastAPI port 8381"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8381

def build_html():
    random.seed(71)
    robots = [
        ("UR5e", 0.89, 45, "#22c55e"),
        ("xArm6", 0.84, 60, "#22c55e"),
        ("Stretch", 0.71, 90, "#f59e0b"),
        ("Kinova", 0.76, 75, "#f59e0b"),
        ("Spot", 0.52, 180, "#C74634"),
    ]
    
    # Adaptation curves: demos to reach 70% SR for each robot
    demo_counts = list(range(0, 201, 10))
    
    def adapt_curve(efficiency, demos_to_target, seed):
        random.seed(seed)
        baseline = 0.05
        target_sr = 0.70
        return [round(min(0.85, baseline + (target_sr - baseline) * (1 - math.exp(-d/demos_to_target*2)) + 0.01*random.uniform(-1,1)), 3) for d in demo_counts]

    robot_colors = ["#22c55e", "#38bdf8", "#f59e0b", "#a78bfa", "#C74634"]
    curves = {}
    for i, (name, eff, demos, _) in enumerate(robots):
        curves[name] = adapt_curve(eff, demos, i+1)

    curve_svgs = ""
    for i, (name, _, _, _) in enumerate(robots):
        color = robot_colors[i]
        pts = " ".join(f"{30+j*7},{180-curves[name][j]*160}" for j in range(len(demo_counts)))
        curve_svgs += f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2"/>'
    
    # 70% SR threshold line
    y_70 = 180 - 0.70 * 160
    curve_svgs += f'<line x1="30" y1="{y_70}" x2="440" y2="{y_70}" stroke="#64748b" stroke-dasharray="3,3" stroke-width="1"/>'
    curve_svgs += f'<text x="445" y="{y_70+4}" fill="#64748b" font-size="8">70% SR</text>'

    # Transfer efficiency bars
    eff_bars = ""
    for i, (name, eff, demos, color) in enumerate(robots):
        y = 20 + i * 32
        eff_w = int(eff * 280)
        eff_bars += f'<text x="55" y="{y+14}" text-anchor="end" fill="#94a3b8" font-size="9">{name}</text>'
        eff_bars += f'<rect x="60" y="{y}" width="{eff_w}" height="22" fill="{color}" opacity="0.8" rx="2"/>'
        eff_bars += f'<text x="{65+eff_w}" y="{y+14}" fill="{color}" font-size="9">{int(eff*100)}% eff | {demos} demos to SR=0.70</text>'

    return f"""<!DOCTYPE html><html><head><title>Embodiment Transfer Tracker — Port {PORT}</title>
<style>body{{background:#0f172a;color:#e2e8f0;font-family:monospace;margin:0;padding:20px}}
h1{{color:#C74634;font-size:1.4em}}h2{{color:#38bdf8;font-size:1em}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:16px}}
.card{{background:#1e293b;border-radius:8px;padding:16px}}
svg{{width:100%;height:auto}}</style></head><body>
<h1>Embodiment Transfer Tracker</h1>
<div style="display:flex;gap:24px;margin-bottom:16px">
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#22c55e">89%</div><div style="font-size:0.75em;color:#94a3b8">UR5e efficiency</div></div>
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#C74634">52%</div><div style="font-size:0.75em;color:#94a3b8">Spot efficiency</div></div>
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#22c55e">Franka</div><div style="font-size:0.75em;color:#94a3b8">Source robot</div></div>
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#38bdf8">45 demos</div><div style="font-size:0.75em;color:#94a3b8">UR5e to SR=0.70</div></div>
</div>
<div class="grid">
<div class="card"><h2>Adaptation Curves (Franka → target)</h2>
<svg viewBox="0 0 500 210"><rect width="500" height="210" fill="#0f172a" rx="4"/>
<line x1="30" y1="10" x2="30" y2="185" stroke="#334155" stroke-width="1"/>
<line x1="30" y1="185" x2="470" y2="185" stroke="#334155" stroke-width="1"/>
{curve_svgs}
<text x="250" y="200" fill="#64748b" font-size="9">Real robot demos</text>
<text x="32" y="200" fill="#64748b" font-size="8">0</text>
<text x="450" y="200" fill="#64748b" font-size="8">200</text>
{''.join(f'<text x="460" y="{180-curves[name][-1]*160+4}" fill="{robot_colors[i]}" font-size="8">{name}</text>' for i,(name,*_) in enumerate(robots))}
</svg></div>
<div class="card"><h2>Transfer Efficiency (vs training from scratch)</h2>
<svg viewBox="0 0 560 175"><rect width="560" height="175" fill="#0f172a" rx="4"/>
{eff_bars}
</svg>
<div style="margin-top:8px;font-size:0.75em;color:#64748b">UR5e/xArm6 arm morphology close to Franka — high transfer. Spot quadruped requires 4× more data.</div>
</div>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Embodiment Transfer Tracker")
    @app.get("/", response_class=HTMLResponse)
    def index(): return build_html()
    @app.get("/health")
    def health(): return {"status":"ok","port":PORT,"best_transfer":"UR5e","efficiency_pct":89}

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type","text/html")
        self.end_headers()
        self.wfile.write(build_html().encode())
    def log_message(self,*a): pass

if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        HTTPServer(("0.0.0.0",PORT), Handler).serve_forever()
