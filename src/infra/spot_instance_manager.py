"""Spot Instance Manager — FastAPI port 8355"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8355

def build_html():
    random.seed(12)
    days = list(range(1, 31))
    spot_cost = [round(47 + 4*math.sin(d/3) + random.uniform(-2, 2), 1) for d in days]
    od_cost = [round(138 + 3*math.sin(d/4) + random.uniform(-1, 1), 1) for d in days]
    savings = [round(od - sp, 1) for od, sp in zip(od_cost, spot_cost)]
    avg_savings_pct = round(sum(savings) / sum(od_cost) * 100, 1)
    
    # Availability heatmap (region × GPU type)
    REGIONS = ["Ashburn", "Phoenix", "Frankfurt"]
    GPUS = ["A100_80GB", "A100_40GB", "A10"]
    AVAIL = [
        [90, 85, 78],
        [82, 88, 71],
        [74, 80, 69],
    ]

    # Preemption timeline SVG
    preempt_events = [(4, "OOM job rescued"), (8, "spot reclaimed"), (13, "checkpoint saved"), 
                      (17, "reclaimed 3min"), (21, "rescued 8min"), (25, "reclaimed 2min"),
                      (27, "rescued 4min"), (29, "reclaimed 1min")]
    preempt_svg = ""
    for day, label in preempt_events:
        x = 30 + day * 17
        preempt_svg += f'<circle cx="{x}" cy="80" r="5" fill="#f59e0b"/>'
        preempt_svg += f'<line x1="{x}" y1="85" x2="{x}" y2="110" stroke="#f59e0b" stroke-width="1" stroke-dasharray="2,2"/>'
        preempt_svg += f'<text x="{x-20}" y="125" fill="#f59e0b" font-size="7" transform="rotate(-30,{x-20},125)">{label}</text>'

    # Cost bar chart SVG
    bar_svg = ""
    for i, d in enumerate(days):
        x = 30 + i*17
        h_spot = int(spot_cost[i] * 1.2)
        h_od = int(od_cost[i] * 1.2)
        bar_svg += f'<rect x="{x}" y="{200-h_od}" width="6" height="{h_od}" fill="#334155" opacity="0.9"/>'
        bar_svg += f'<rect x="{x+7}" y="{200-h_spot}" width="6" height="{h_spot}" fill="#22c55e" opacity="0.85"/>'

    # Availability heatmap
    heatmap_cells = ""
    for ri, region in enumerate(REGIONS):
        for gi, gpu in enumerate(GPUS):
            pct = AVAIL[ri][gi]
            color = "#22c55e" if pct >= 85 else "#f59e0b" if pct >= 75 else "#C74634"
            x = 100 + gi * 120
            y = 40 + ri * 50
            heatmap_cells += f'<rect x="{x}" y="{y}" width="100" height="40" fill="{color}" opacity="0.3" rx="3"/>'
            heatmap_cells += f'<text x="{x+50}" y="{y+26}" text-anchor="middle" fill="{color}" font-size="14" font-weight="bold">{pct}%</text>'

    return f"""<!DOCTYPE html><html><head><title>Spot Instance Manager — Port {PORT}</title>
<style>body{{background:#0f172a;color:#e2e8f0;font-family:monospace;margin:0;padding:20px}}
h1{{color:#C74634;font-size:1.4em}}h2{{color:#38bdf8;font-size:1em}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:16px}}
.card{{background:#1e293b;border-radius:8px;padding:16px}}
svg{{width:100%;height:auto}}</style></head><body>
<h1>Spot Instance Manager</h1>
<div style="display:flex;gap:24px;margin-bottom:16px">
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#22c55e">{avg_savings_pct}%</div><div style="font-size:0.75em;color:#94a3b8">Avg Savings</div></div>
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#22c55e">{len(preempt_events)}</div><div style="font-size:0.75em;color:#94a3b8">Preemptions (30d)</div></div>
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#22c55e">100%</div><div style="font-size:0.75em;color:#94a3b8">Ckpt Recovery</div></div>
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#38bdf8">90%</div><div style="font-size:0.75em;color:#94a3b8">Ashburn A100 Avail</div></div>
</div>
<div class="grid">
<div class="card"><h2>30-Day Cost: Spot vs On-Demand</h2>
<svg viewBox="0 0 540 220"><rect width="540" height="220" fill="#0f172a" rx="4"/>
<line x1="30" y1="10" x2="30" y2="200" stroke="#334155" stroke-width="1"/>
<line x1="30" y1="200" x2="530" y2="200" stroke="#334155" stroke-width="1"/>
{bar_svg}
<text x="32" y="215" fill="#64748b" font-size="8">Day 1</text>
<text x="495" y="215" fill="#64748b" font-size="8">Day 30</text>
<text x="350" y="30" fill="#334155" font-size="9">On-demand</text>
<text x="350" y="45" fill="#22c55e" font-size="9">Spot</text>
<rect x="343" y="22" width="8" height="8" fill="#334155"/>
<rect x="343" y="37" width="8" height="8" fill="#22c55e"/>
</svg>
<div style="margin-top:8px;font-size:0.8em;color:#94a3b8">
Total on-demand: <span style="color:#334155">$4,140</span> → Spot: <span style="color:#22c55e">$1,449</span> — <span style="color:#22c55e">$2,691 saved</span>
</div>
</div>
<div class="card"><h2>Preemption Events (30d)</h2>
<svg viewBox="0 0 540 150"><rect width="540" height="150" fill="#0f172a" rx="4"/>
<line x1="30" y1="80" x2="530" y2="80" stroke="#334155" stroke-width="2"/>
{preempt_svg}
<text x="32" y="100" fill="#64748b" font-size="8">Day 1</text>
<text x="500" y="100" fill="#64748b" font-size="8">Day 30</text>
<text x="200" y="20" fill="#64748b" font-size="9">8 preemption events — all checkpointed and recovered</text>
</svg>
<div style="margin-top:8px;font-size:0.8em">
<span style="color:#94a3b8">Avg recovery time: </span><span style="color:#22c55e">3.8 min</span> &nbsp;
<span style="color:#94a3b8">Checkpoint interval: </span><span style="color:#38bdf8">250 steps</span>
</div>
</div>
</div>
<div class="card" style="margin-top:16px"><h2>Spot Availability by Region / GPU Type</h2>
<svg viewBox="0 0 480 200"><rect width="480" height="200" fill="#0f172a" rx="4"/>
<text x="150" y="30" text-anchor="middle" fill="#94a3b8" font-size="11">A100_80GB</text>
<text x="270" y="30" text-anchor="middle" fill="#94a3b8" font-size="11">A100_40GB</text>
<text x="390" y="30" text-anchor="middle" fill="#94a3b8" font-size="11">A10</text>
<text x="10" y="65" fill="#94a3b8" font-size="10">Ashburn</text>
<text x="10" y="115" fill="#94a3b8" font-size="10">Phoenix</text>
<text x="10" y="165" fill="#94a3b8" font-size="10">Frankfurt</text>
{heatmap_cells}
</svg>
<div style="margin-top:8px;font-size:0.75em;color:#64748b">Recommended: Ashburn A100_80GB (90% avail, 65% savings, 226ms inference)</div>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Spot Instance Manager")
    @app.get("/", response_class=HTMLResponse)
    def index(): return build_html()
    @app.get("/health")
    def health(): return {"status": "ok", "port": PORT, "avg_savings_pct": 65, "preemptions_30d": 8}

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
