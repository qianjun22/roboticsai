"""Token Budget Optimizer — FastAPI port 8370"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8370

def build_html():
    random.seed(9)
    # Token allocation strategies
    strategies = [
        ("baseline_100pct", {"visual": 68, "action": 12, "sys_prompt": 12, "history": 8}, 0.78, 847),
        ("optimized_75pct", {"visual": 75, "action": 12, "sys_prompt": 8, "history": 5}, 0.77, 635),
        ("visual_heavy_85pct", {"visual": 85, "action": 8, "sys_prompt": 5, "history": 2}, 0.75, 720),
        ("context_heavy", {"visual": 55, "action": 10, "sys_prompt": 15, "history": 20}, 0.71, 912),
        ("minimal", {"visual": 90, "action": 7, "sys_prompt": 2, "history": 1}, 0.68, 510),
    ]

    # SR vs token count scatter
    scatter_pts = ""
    colors_sc = ["#22c55e", "#22c55e", "#f59e0b", "#f59e0b", "#C74634"]
    for i, (name, alloc, sr, tokens) in enumerate(strategies):
        x = 40 + (tokens/10)
        y = 190 - sr*180
        color = colors_sc[i]
        scatter_pts += f'<circle cx="{x}" cy="{y}" r="6" fill="{color}" opacity="0.85"/>'
        scatter_pts += f'<text x="{x+8}" y="{y+4}" fill="{color}" font-size="8">{name[:15]}</text>'

    # Pareto frontier
    pareto = [(635, 0.77), (847, 0.78)]
    pareto_pts = " ".join(f"{40+t/10},{190-sr*180}" for t,sr in sorted(pareto))

    # Stacked allocation bar chart
    alloc_bars = ""
    comp_colors = {"visual": "#22c55e", "action": "#38bdf8", "sys_prompt": "#f59e0b", "history": "#a78bfa"}
    for si, (name, alloc, sr, tokens) in enumerate(strategies):
        x_offset = 30
        y = 30 + si * 38
        total = sum(alloc.values())
        for comp, pct in alloc.items():
            w = int(pct * 3.8)
            alloc_bars += f'<rect x="{x_offset}" y="{y}" width="{w}" height="26" fill="{comp_colors[comp]}" opacity="0.8"/>'
            if pct >= 8:
                alloc_bars += f'<text x="{x_offset+w//2}" y="{y+17}" text-anchor="middle" fill="#fff" font-size="8">{pct}%</text>'
            x_offset += w
        sr_color = "#22c55e" if sr >= 0.75 else "#f59e0b" if sr >= 0.70 else "#C74634"
        alloc_bars += f'<text x="410" y="{y+17}" fill="{sr_color}" font-size="9">SR={sr} | {tokens}tok</text>'
        alloc_bars += f'<text x="25" y="{y+17}" text-anchor="end" fill="#94a3b8" font-size="8">{name[:12]}</text>'

    return f"""<!DOCTYPE html><html><head><title>Token Budget Optimizer — Port {PORT}</title>
<style>body{{background:#0f172a;color:#e2e8f0;font-family:monospace;margin:0;padding:20px}}
h1{{color:#C74634;font-size:1.4em}}h2{{color:#38bdf8;font-size:1em}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:16px}}
.card{{background:#1e293b;border-radius:8px;padding:16px}}
svg{{width:100%;height:auto}}</style></head><body>
<h1>Token Budget Optimizer</h1>
<div style="display:flex;gap:24px;margin-bottom:16px">
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#22c55e">75%</div><div style="font-size:0.75em;color:#94a3b8">Optimal Visual</div></div>
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#22c55e">SR 0.77</div><div style="font-size:0.75em;color:#94a3b8">vs 0.78 full</div></div>
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#38bdf8">-25%</div><div style="font-size:0.75em;color:#94a3b8">Compute Cost</div></div>
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#f59e0b">847 tok</div><div style="font-size:0.75em;color:#94a3b8">Avg/Request</div></div>
</div>
<div class="card"><h2>Token Allocation Strategies</h2>
<svg viewBox="0 550 600 210" style="height:220px">
<rect width="600" height="550" fill="#0f172a" rx="4"/>
{alloc_bars}
</svg>
<div style="font-size:0.75em;color:#64748b;margin-top:4px">
<span style="color:#22c55e">■</span> visual &nbsp;
<span style="color:#38bdf8">■</span> action &nbsp;
<span style="color:#f59e0b">■</span> sys_prompt &nbsp;
<span style="color:#a78bfa">■</span> history
</div>
</div>
<div class="card" style="margin-top:16px"><h2>SR vs Token Budget — Pareto Analysis</h2>
<svg viewBox="0 0 500 220"><rect width="500" height="220" fill="#0f172a" rx="4"/>
<line x1="30" y1="10" x2="30" y2="200" stroke="#334155" stroke-width="1"/>
<line x1="30" y1="200" x2="490" y2="200" stroke="#334155" stroke-width="1"/>
<polyline points="{pareto_pts}" fill="none" stroke="#22c55e" stroke-width="1.5" stroke-dasharray="4,3"/>
{scatter_pts}
<text x="250" y="215" fill="#64748b" font-size="9">Tokens per Request</text>
<text x="32" y="215" fill="#64748b" font-size="8">400</text>
<text x="430" y="215" fill="#64748b" font-size="8">950</text>
<text x="5" y="120" fill="#64748b" font-size="9" transform="rotate(-90,5,120)">SR</text>
</svg></div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Token Budget Optimizer")
    @app.get("/", response_class=HTMLResponse)
    def index(): return build_html()
    @app.get("/health")
    def health(): return {"status":"ok","port":PORT,"optimal_visual_pct":75,"sr":0.77,"compute_savings_pct":25}

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
