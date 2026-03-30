"""Error Analysis Dashboard — FastAPI port 8361"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8361

def build_html():
    random.seed(77)
    # Failure breakdown by phase
    total_failures = 200
    phases = [
        ("Reach", 28, "#38bdf8", ["pose_err 15", "IK_timeout 8", "collision 5"]),
        ("Grasp", 104, "#f59e0b", ["grasp_miss 52", "slip 31", "force 21"]),
        ("Lift", 47, "#22c55e", ["drop 28", "traj_deviation 12", "timeout 7"]),
        ("Place/Drop", 21, "#a78bfa", ["placement_err 14", "release_fail 7"]),
    ]

    # Sankey-style (simplified horizontal stacked bar)
    sankey = ""
    x = 30
    for name, count, color, causes in phases:
        w = int(count * 2.2)
        sankey += f'<rect x="{x}" y="40" width="{w}" height="60" fill="{color}" opacity="0.8" rx="3"/>'
        sankey += f'<text x="{x+w//2}" y="75" text-anchor="middle" fill="#fff" font-size="10" font-weight="bold">{count}</text>'
        sankey += f'<text x="{x+w//2}" y="88" text-anchor="middle" fill="#fff" font-size="8">{int(count/total_failures*100)}%</text>'
        sankey += f'<text x="{x+w//2}" y="120" text-anchor="middle" fill="{color}" font-size="9">{name}</text>'
        x += w + 6

    # Correlation matrix (5 factors x 5 factors)
    factors = ["lighting", "grasp_miss", "slip", "drop", "traj_err"]
    corr = [
        [1.0, 0.71, 0.62, 0.28, 0.31],
        [0.71, 1.0, 0.83, 0.41, 0.38],
        [0.62, 0.83, 1.0, 0.52, 0.44],
        [0.28, 0.41, 0.52, 1.0, 0.67],
        [0.31, 0.38, 0.44, 0.67, 1.0],
    ]
    heatmap_cells = ""
    for ri, row in enumerate(corr):
        for ci, val in enumerate(row):
            x = 100 + ci * 52
            y = 30 + ri * 52
            intensity = int(val * 200)
            color_hex = f"#{intensity:02x}{max(0,intensity-80):02x}{max(0,intensity-120):02x}" if ri != ci else "#334155"
            heatmap_cells += f'<rect x="{x}" y="{y}" width="48" height="48" fill="{color_hex}" rx="2"/>'
            heatmap_cells += f'<text x="{x+24}" y="{y+28}" text-anchor="middle" fill="#fff" font-size="9">{val:.2f}</text>'

    # Fix priority ranking
    fixes = [
        ("Grasp prediction head retraining", 52, "#C74634"),
        ("Force-torque feedback integration", 31, "#f97316"),
        ("Domain randomization for lighting", 28, "#f59e0b"),
        ("IK solver timeout increase", 15, "#22c55e"),
        ("Trajectory smoothing (chunk_blend)", 12, "#38bdf8"),
    ]
    fix_bars = ""
    for i, (name, reduction, color) in enumerate(fixes):
        w = int(reduction * 3.8)
        fix_bars += f'<text x="10" y="{30+i*26}" fill="#94a3b8" font-size="9">{name}</text>'
        fix_bars += f'<rect x="310" y="{18+i*26}" width="{w}" height="16" fill="{color}" opacity="0.8" rx="2"/>'
        fix_bars += f'<text x="{315+w}" y="{31+i*26}" fill="{color}" font-size="9">-{reduction} failures</text>'

    return f"""<!DOCTYPE html><html><head><title>Error Analysis Dashboard — Port {PORT}</title>
<style>body{{background:#0f172a;color:#e2e8f0;font-family:monospace;margin:0;padding:20px}}
h1{{color:#C74634;font-size:1.4em}}h2{{color:#38bdf8;font-size:1em}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:16px}}
.card{{background:#1e293b;border-radius:8px;padding:16px}}
svg{{width:100%;height:auto}}</style></head><body>
<h1>Error Analysis Dashboard</h1>
<div style="display:flex;gap:24px;margin-bottom:16px">
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#C74634">200</div><div style="font-size:0.75em;color:#94a3b8">Total Failures</div></div>
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#f59e0b">52%</div><div style="font-size:0.75em;color:#94a3b8">Grasp Phase</div></div>
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#22c55e">0.71</div><div style="font-size:0.75em;color:#94a3b8">lighting\u2194grasp r</div></div>
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#38bdf8">83</div><div style="font-size:0.75em;color:#94a3b8">Fixable (top 2)</div></div>
</div>
<div class="card"><h2>Failure Attribution by Phase (200 eps)</h2>
<svg viewBox="0 0 580 135"><rect width="580" height="135" fill="#0f172a" rx="4"/>
{sankey}
</svg></div>
<div class="grid">
<div class="card"><h2>Error Correlation Matrix</h2>
<svg viewBox="0 0 380 300"><rect width="380" height="300" fill="#0f172a" rx="4"/>
{heatmap_cells}
{''.join(f'<text x="{100+i*52+24}" y="25" text-anchor="middle" fill="#94a3b8" font-size="8">{f[:5]}</text>' for i,f in enumerate(factors))}
{''.join(f'<text x="95" y="{56+i*52}" text-anchor="end" fill="#94a3b8" font-size="8">{f[:5]}</text>' for i,f in enumerate(factors))}
</svg></div>
<div class="card"><h2>Fix Priority (Failure Reduction Impact)</h2>
<svg viewBox="0 0 580 145"><rect width="580" height="145" fill="#0f172a" rx="4"/>
{fix_bars}
</svg></div>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Error Analysis Dashboard")
    @app.get("/", response_class=HTMLResponse)
    def index(): return build_html()
    @app.get("/health")
    def health(): return {"status":"ok","port":PORT,"total_failures":200,"top_phase":"grasp"}

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
