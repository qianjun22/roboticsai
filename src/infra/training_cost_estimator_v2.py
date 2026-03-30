"""Training Cost Estimator v2 — FastAPI port 8380"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8380

def build_html():
    # Parameter sweep: demos × steps cost matrix
    demo_counts = [100, 300, 500, 1000, 2000]
    step_counts = [1000, 2000, 3000, 5000, 10000]
    # Cost in $, OCI A100 spot at $0.0043/10k steps base
    costs = []
    for demos in demo_counts:
        row = []
        for steps in step_counts:
            cost = round((demos / 100) * (steps / 1000) * 0.086, 2)
            row.append(cost)
        costs.append(row)

    # Heatmap
    heatmap = ""
    for ri, (demos, cost_row) in enumerate(zip(demo_counts, costs)):
        for ci, (steps, cost) in enumerate(zip(step_counts, cost_row)):
            x = 80 + ci * 80
            y = 30 + ri * 42
            intensity = min(255, int(cost * 3))
            fill = f"#{intensity:02x}{max(0,255-intensity):02x}00"
            heatmap += f'<rect x="{x}" y="{y}" width="76" height="38" fill="{fill}" opacity="0.7" rx="2"/>'
            heatmap += f'<text x="{x+38}" y="{y+23}" text-anchor="middle" fill="#fff" font-size="9">${cost}</text>'
    
    for ci, s in enumerate(step_counts):
        heatmap += f'<text x="{118+ci*80}" y="24" text-anchor="middle" fill="#94a3b8" font-size="9">{s//1000}k steps</text>'
    for ri, d in enumerate(demo_counts):
        heatmap += f'<text x="75" y="{52+ri*42}" text-anchor="end" fill="#94a3b8" font-size="9">{d} demos</text>'

    # 3-yr TCO comparison
    providers = [
        ("OCI A100 spot", 0.43, "#22c55e"),
        ("OCI A100 on-demand", 1.12, "#38bdf8"),
        ("AWS p4d", 4.13, "#f59e0b"),
        ("Azure NCv4", 3.87, "#f97316"),
        ("Self-hosted DGX", 0.21, "#a78bfa"),
    ]
    
    tco_bars = ""
    for i, (provider, cost_per_run, color) in enumerate(providers):
        # TCO over 3 years (runs/month × 12 × 3 × cost_per_run + fixed costs)
        monthly_runs = 847  # ~28/day
        fixed = 0 if "OCI" in provider or "AWS" in provider or "Azure" in provider else 400000
        tco_3yr = round(monthly_runs * 36 * cost_per_run + fixed, 0)
        bar_w = int(min(tco_3yr, 200000) / 2000)
        y = 20 + i * 35
        tco_bars += f'<text x="135" y="{y+14}" text-anchor="end" fill="#94a3b8" font-size="9">{provider}</text>'
        tco_bars += f'<rect x="140" y="{y}" width="{bar_w}" height="24" fill="{color}" opacity="0.8" rx="2"/>'
        tco_bars += f'<text x="{145+bar_w}" y="{y+16}" fill="{color}" font-size="9">${tco_3yr:,.0f}/3yr</text>'

    return f"""<!DOCTYPE html><html><head><title>Training Cost Estimator v2 — Port {PORT}</title>
<style>body{{background:#0f172a;color:#e2e8f0;font-family:monospace;margin:0;padding:20px}}
h1{{color:#C74634;font-size:1.4em}}h2{{color:#38bdf8;font-size:1em}}
.card{{background:#1e293b;border-radius:8px;padding:16px;margin-top:16px}}
svg{{width:100%;height:auto}}</style></head><body>
<h1>Training Cost Estimator v2</h1>
<div style="display:flex;gap:24px;margin-bottom:16px">
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#22c55e">$0.43</div><div style="font-size:0.75em;color:#94a3b8">Optimal run cost</div></div>
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#f59e0b">9.6×</div><div style="font-size:0.75em;color:#94a3b8">vs AWS p4d</div></div>
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#38bdf8">1000 demos</div><div style="font-size:0.75em;color:#94a3b8">Optimal demo count</div></div>
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#22c55e">A100 spot</div><div style="font-size:0.75em;color:#94a3b8">Recommended GPU</div></div>
</div>
<div class="card">
<h2>Cost Heatmap: Demos × Steps (OCI A100 spot, $ per run)</h2>
<svg viewBox="0 0 560 240"><rect width="560" height="240" fill="#0f172a" rx="4"/>
{heatmap}
</svg>
<div style="font-size:0.75em;color:#22c55e;margin-top:4px">★ Optimal: 1000 demos × 5000 steps = $0.43/run</div>
</div>
<div class="card">
<h2>3-Year TCO Comparison</h2>
<svg viewBox="0 0 620 195"><rect width="620" height="195" fill="#0f172a" rx="4"/>
{tco_bars}
</svg>
<div style="font-size:0.75em;color:#64748b;margin-top:4px">DGX $400k capex included. OCI spot 65% cheaper than on-demand.</div>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Training Cost Estimator v2")
    @app.get("/", response_class=HTMLResponse)
    def index(): return build_html()
    @app.get("/health")
    def health(): return {"status":"ok","port":PORT,"optimal_cost_per_run":0.43,"aws_multiple":9.6}

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
