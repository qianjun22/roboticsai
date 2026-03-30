"""OCI A100 Utilization Report — FastAPI port 8374"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8374

def build_html():
    random.seed(77)
    hours = list(range(24))
    nodes = [
        ("GPU4 Ashburn", 91, "#22c55e"),
        ("GPU1 Ashburn", 87, "#22c55e"),
        ("GPU1 Phoenix", 62, "#f59e0b"),
        ("GPU1 Frankfurt", 71, "#38bdf8"),
    ]

    # 24h utilization heatmap per node
    heatmap_cells = ""
    for ni, (node_name, avg_util, color) in enumerate(nodes):
        for h in hours:
            # simulate realistic utilization curve
            base_util = avg_util + 8*math.sin(math.pi*(h-8)/12) + random.randint(-5,5)
            util = max(5, min(100, base_util))
            intensity = int(util * 2.0)
            fill_g = min(255, intensity)
            fill = f"#{max(0,intensity-100):02x}{fill_g:02x}{max(0,intensity-120):02x}"
            x = 80 + h * 22
            y = 20 + ni * 32
            heatmap_cells += f'<rect x="{x}" y="{y}" width="20" height="28" fill="{fill}" opacity="0.85" rx="1"/>'
            if h % 6 == 0:
                heatmap_cells += f'<text x="{x+10}" y="{y+18}" text-anchor="middle" fill="#fff" font-size="7">{int(util)}%</text>'
        heatmap_cells += f'<text x="75" y="{34+ni*32}" text-anchor="end" fill="{color}" font-size="9">{node_name[:14]}</text>'
    
    for h in range(0, 24, 3):
        heatmap_cells += f'<text x="{90+h*22}" y="15" fill="#64748b" font-size="8">{h:02d}h</text>'

    # Idle waste by hour
    random.seed(78)
    idle_by_hour = []
    for h in hours:
        is_night = h < 7 or h > 22
        is_weekend_sim = False  # simplified
        avg_waste = 38 if is_night else 12
        idle_by_hour.append(round(avg_waste + random.uniform(-5,5), 1))
    
    idle_bars = ""
    for h, waste in enumerate(idle_by_hour):
        color = "#C74634" if waste > 30 else "#f59e0b" if waste > 15 else "#22c55e"
        bar_h = int(waste * 2)
        idle_bars += f'<rect x="{20+h*22}" y="{120-bar_h}" width="18" height="{bar_h}" fill="{color}" opacity="0.8" rx="1"/>'
        if h % 4 == 0:
            idle_bars += f'<text x="{29+h*22}" y="132" text-anchor="middle" fill="#64748b" font-size="7">{h:02d}h</text>'

    avg_idle = round(sum(idle_by_hour)/len(idle_by_hour), 1)
    weekly_savings = round(avg_idle/100 * 4 * 24 * 7 * 3.50, 0)  # 4 nodes × $3.50/hr spot

    return f"""<!DOCTYPE html><html><head><title>OCI A100 Utilization Report — Port {PORT}</title>
<style>body{{background:#0f172a;color:#e2e8f0;font-family:monospace;margin:0;padding:20px}}
h1{{color:#C74634;font-size:1.4em}}h2{{color:#38bdf8;font-size:1em}}
.card{{background:#1e293b;border-radius:8px;padding:16px;margin-top:16px}}
svg{{width:100%;height:auto}}</style></head><body>
<h1>OCI A100 Utilization Report</h1>
<div style="display:flex;gap:24px;margin-bottom:16px">
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#22c55e">91%</div><div style="font-size:0.75em;color:#94a3b8">Peak (GPU4)</div></div>
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#f59e0b">62%</div><div style="font-size:0.75em;color:#94a3b8">Low (Phoenix)</div></div>
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#C74634">{avg_idle}%</div><div style="font-size:0.75em;color:#94a3b8">Avg Idle</div></div>
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#22c55e">${weekly_savings:.0f}/wk</div><div style="font-size:0.75em;color:#94a3b8">Spot Savings Opp.</div></div>
</div>
<div class="card">
<h2>24h GPU Utilization Heatmap (4 nodes)</h2>
<svg viewBox="0 0 620 160"><rect width="620" height="160" fill="#0f172a" rx="4"/>
{heatmap_cells}
</svg>
</div>
<div class="card">
<h2>Idle Waste by Hour (% avg across 4 nodes)</h2>
<svg viewBox="0 0 560 150"><rect width="560" height="150" fill="#0f172a" rx="4"/>
<line x1="15" y1="120" x2="550" y2="120" stroke="#334155" stroke-width="1"/>
{idle_bars}
<line x1="15" y1="{120-30*2}" x2="550" y2="{120-30*2}" stroke="#C74634" stroke-dasharray="3,3" stroke-width="1" opacity="0.5"/>
<text x="520" y="{115-30*2}" fill="#C74634" font-size="8">30% idle</text>
</svg>
<div style="margin-top:8px;font-size:0.75em;color:#64748b">Schedule spot preemption + idle rebalancing 22h-07h. ${weekly_savings:.0f}/wk savings opportunity.</div>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="OCI A100 Utilization Report")
    @app.get("/", response_class=HTMLResponse)
    def index(): return build_html()
    @app.get("/health")
    def health(): return {"status":"ok","port":PORT,"peak_util_pct":91,"weekly_savings_opp":124}

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
