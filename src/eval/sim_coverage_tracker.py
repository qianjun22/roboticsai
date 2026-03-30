"""Sim Coverage Tracker — FastAPI port 8367"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8367

def build_html():
    random.seed(44)
    tasks = ["pick_place", "stack", "pour", "push", "insert", "fold", "wipe", "handover", "door_open", "cable_route", "assembly", "inspection"]
    envs = ["Genesis", "Isaac_Sim", "LIBERO", "PyBullet", "Cosmos_WM"]
    
    coverage = [
        [1,1,1,1,0],[1,1,1,1,0],[0,1,1,0,0],[1,1,1,1,0],[0,1,0,0,0],
        [0,0,0,0,0],[1,0,1,0,0],[0,1,1,0,0],[1,1,0,1,0],[0,0,0,0,0],
        [0,1,0,0,0],[1,0,1,0,0],
    ]
    
    heatmap_cells = ""
    for ri, task in enumerate(tasks):
        for ci, env in enumerate(envs):
            cov = coverage[ri][ci]
            fill = "#22c55e" if cov else "#1e293b"
            x = 140 + ci * 72
            y = 25 + ri * 28
            heatmap_cells += f'<rect x="{x}" y="{y}" width="68" height="24" fill="{fill}" opacity="0.7" rx="2"/>'
            heatmap_cells += f'<text x="{x+34}" y="{y+16}" text-anchor="middle" fill="{"#fff" if cov else "#334155"}" font-size="8">{"✓" if cov else "✗"}</text>'
    
    # Row labels
    for ri, task in enumerate(tasks):
        heatmap_cells += f'<text x="130" y="{37+ri*28}" text-anchor="end" fill="#94a3b8" font-size="9">{task}</text>'
    # Col labels
    for ci, env in enumerate(envs):
        heatmap_cells += f'<text x="{174+ci*72}" y="18" text-anchor="middle" fill="#94a3b8" font-size="9">{env[:7]}</text>'

    # Gap analysis
    task_coverage = [sum(row) for row in coverage]
    gap_bars = ""
    for i, (task, cov_count) in enumerate(zip(tasks, task_coverage)):
        color = "#22c55e" if cov_count >= 4 else "#f59e0b" if cov_count >= 2 else "#C74634"
        w = cov_count * 60
        gap_bars += f'<text x="10" y="{22+i*22}" fill="#94a3b8" font-size="8">{task}</text>'
        gap_bars += f'<rect x="120" y="{10+i*22}" width="{w}" height="14" fill="{color}" opacity="0.8" rx="2"/>'
        gap_bars += f'<text x="{125+w}" y="{22+i*22}" fill="{color}" font-size="8">{cov_count}/5 envs</text>'

    total_cells = len(tasks) * len(envs)
    covered = sum(sum(row) for row in coverage)
    pct = round(covered / total_cells * 100)
    critical_gaps = ["pour", "fold", "cable_route", "insert"]

    return f"""<!DOCTYPE html><html><head><title>Sim Coverage Tracker — Port {PORT}</title>
<style>body{{background:#0f172a;color:#e2e8f0;font-family:monospace;margin:0;padding:20px}}
h1{{color:#C74634;font-size:1.4em}}h2{{color:#38bdf8;font-size:1em}}
.grid{{display:grid;grid-template-columns:2fr 1fr;gap:16px;margin-top:16px}}
.card{{background:#1e293b;border-radius:8px;padding:16px}}
svg{{width:100%;height:auto}}</style></head><body>
<h1>Sim Coverage Tracker</h1>
<div style="display:flex;gap:24px;margin-bottom:16px">
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#22c55e">{pct}%</div><div style="font-size:0.75em;color:#94a3b8">Overall Coverage</div></div>
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#C74634">{len(critical_gaps)}</div><div style="font-size:0.75em;color:#94a3b8">Critical Gaps</div></div>
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#38bdf8">{len(tasks)}</div><div style="font-size:0.75em;color:#94a3b8">Tasks Tracked</div></div>
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#38bdf8">{len(envs)}</div><div style="font-size:0.75em;color:#94a3b8">Environments</div></div>
</div>
<div class="card">
<h2>Task × Environment Coverage Matrix</h2>
<svg viewBox="0 640 500 340" style="height:360px">
<rect width="640" height="500" fill="#0f172a" rx="4"/>
{heatmap_cells}
</svg>
</div>
<div class="card" style="margin-top:16px">
<h2>Coverage per Task</h2>
<svg viewBox="0 0 420 285"><rect width="420" height="285" fill="#0f172a" rx="4"/>
{gap_bars}
</svg>
<div style="margin-top:8px;font-size:0.75em;color:#64748b">
Critical gaps (SDG sprint): <span style="color:#C74634">{', '.join(critical_gaps)}</span>
</div>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Sim Coverage Tracker")
    @app.get("/", response_class=HTMLResponse)
    def index(): return build_html()
    @app.get("/health")
    def health(): return {"status":"ok","port":PORT,"coverage_pct":81,"critical_gaps":4}

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
