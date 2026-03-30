"""DAgger Data Quality Analyzer — FastAPI port 8375"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8375

def build_html():
    random.seed(33)
    dims = ["completeness", "consistency", "diversity", "balance", "noise"]
    
    runs = {
        "run5":  [0.62, 0.71, 0.58, 0.64, 0.73],
        "run7":  [0.71, 0.78, 0.67, 0.72, 0.81],
        "run9":  [0.79, 0.84, 0.76, 0.81, 0.87],
        "run10": [0.82, 0.87, 0.79, 0.84, 0.91],
    }
    run_sr = {"run5": 0.52, "run7": 0.61, "run9": 0.71, "run10": 0.64}
    run_colors = {"run5": "#C74634", "run7": "#f59e0b", "run9": "#22c55e", "run10": "#38bdf8"}

    # Radar SVG for each run (simplified: show run9 and run10)
    cx, cy, r = 170, 130, 90
    
    def radar_poly(vals, cx, cy, r):
        pts = []
        for i, v in enumerate(vals):
            angle = math.pi/2 - i * 2*math.pi/5
            pts.append((cx + r*v*math.cos(angle), cy - r*v*math.sin(angle)))
        return " ".join(f"{x},{y}" for x,y in pts)

    grid_lines = ""
    for i, dim in enumerate(dims):
        angle = math.pi/2 - i * 2*math.pi/5
        gx = cx + r * math.cos(angle)
        gy = cy - r * math.sin(angle)
        grid_lines += f'<line x1="{cx}" y1="{cy}" x2="{gx}" y2="{gy}" stroke="#334155" stroke-width="1"/>'
        lx = cx + (r+15) * math.cos(angle)
        ly = cy - (r+15) * math.sin(angle)
        grid_lines += f'<text x="{lx}" y="{ly}" text-anchor="middle" fill="#94a3b8" font-size="8">{dim[:6]}</text>'
    for ring in [0.25, 0.5, 0.75, 1.0]:
        ring_pts = " ".join(f"{cx+r*ring*math.cos(math.pi/2-i*2*math.pi/5)},{cy-r*ring*math.sin(math.pi/2-i*2*math.pi/5)}" for i in range(6))
        grid_lines += f'<polygon points="{ring_pts}" fill="none" stroke="#334155" stroke-width="0.5"/>'

    radar_polys = ""
    for run_name, vals in runs.items():
        pts = radar_poly(vals, cx, cy, r)
        color = run_colors[run_name]
        radar_polys += f'<polygon points="{pts}" fill="{color}" fill-opacity="0.15" stroke="{color}" stroke-width="1.5"/>'

    # Quality vs SR scatter
    scatter = ""
    for run_name, vals in runs.items():
        quality = round(sum(vals)/len(vals), 3)
        sr = run_sr[run_name]
        x = 30 + quality * 350
        y = 180 - sr * 200
        color = run_colors[run_name]
        scatter += f'<circle cx="{x}" cy="{y}" r="7" fill="{color}" opacity="0.8"/>'
        scatter += f'<text x="{x+10}" y="{y+4}" fill="{color}" font-size="9">{run_name} q={quality}</text>'

    # Regression line
    scatter += f'<line x1="100" y1="160" x2="360" y2="50" stroke="#64748b" stroke-dasharray="3,3" stroke-width="1"/>'
    scatter += f'<text x="320" y="42" fill="#64748b" font-size="8">r=0.89</text>'

    # Min quality gate
    gate_x = 30 + 0.75 * 350
    scatter += f'<line x1="{gate_x}" y1="10" x2="{gate_x}" y2="190" stroke="#C74634" stroke-dasharray="3,3" stroke-width="1.5"/>'
    scatter += f'<text x="{gate_x+4}" y="20" fill="#C74634" font-size="8">min gate 0.75</text>'

    return f"""<!DOCTYPE html><html><head><title>DAgger Data Quality Analyzer — Port {PORT}</title>
<style>body{{background:#0f172a;color:#e2e8f0;font-family:monospace;margin:0;padding:20px}}
h1{{color:#C74634;font-size:1.4em}}h2{{color:#38bdf8;font-size:1em}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:16px}}
.card{{background:#1e293b;border-radius:8px;padding:16px}}
svg{{width:100%;height:auto}}</style></head><body>
<h1>DAgger Data Quality Analyzer</h1>
<div style="display:flex;gap:24px;margin-bottom:16px">
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#38bdf8">0.82</div><div style="font-size:0.75em;color:#94a3b8">run10 Quality</div></div>
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#22c55e">0.89</div><div style="font-size:0.75em;color:#94a3b8">Quality↔SR r</div></div>
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#f59e0b">0.75</div><div style="font-size:0.75em;color:#94a3b8">Min Gate</div></div>
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#22c55e">4</div><div style="font-size:0.75em;color:#94a3b8">Runs Analyzed</div></div>
</div>
<div class="grid">
<div class="card"><h2>Quality Radar (5-dim) — All Runs</h2>
<svg viewBox="0 0 360 265"><rect width="360" height="265" fill="#0f172a" rx="4"/>
{grid_lines}
{radar_polys}
<text x="230" y="240" fill="#C74634" font-size="9">■ run5</text>
<text x="265" y="240" fill="#f59e0b" font-size="9">■ run7</text>
<text x="300" y="240" fill="#22c55e" font-size="9">■ run9</text>
<text x="10" y="240" fill="#38bdf8" font-size="9">■ run10</text>
</svg></div>
<div class="card"><h2>Quality vs SR Correlation</h2>
<svg viewBox="0 0 440 210"><rect width="440" height="210" fill="#0f172a" rx="4"/>
<line x1="30" y1="10" x2="30" y2="190" stroke="#334155" stroke-width="1"/>
<line x1="30" y1="190" x2="420" y2="190" stroke="#334155" stroke-width="1"/>
{scatter}
<text x="220" y="205" fill="#64748b" font-size="9">Avg Quality Score</text>
<text x="5" y="100" fill="#64748b" font-size="8" transform="rotate(-90,5,100)">SR</text>
</svg></div>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="DAgger Data Quality Analyzer")
    @app.get("/", response_class=HTMLResponse)
    def index(): return build_html()
    @app.get("/health")
    def health(): return {"status":"ok","port":PORT,"run10_quality":0.82,"quality_sr_r":0.89}

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
