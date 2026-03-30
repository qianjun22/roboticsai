"""DAgger Run11 Planner — FastAPI port 8368"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8368

def build_html():
    random.seed(13)
    # SR trajectory family: run9, run10, run11 projected
    eps = list(range(0, 501, 10))
    
    def sr_curve(base, ceiling, tau, seed):
        random.seed(seed)
        return [round(min(ceiling, base + (ceiling-base)*(1-math.exp(-e/tau)) + 0.01*random.uniform(-1,1)), 3) for e in eps]
    
    run9 = sr_curve(0.05, 0.71, 120, 1)
    run10 = sr_curve(0.05, 0.78, 100, 2)
    run11 = sr_curve(0.05, 0.84, 85, 3)  # projected
    
    pts9 = " ".join(f"{30+i*5.4},{200-run9[i]*170}" for i in range(len(eps)))
    pts10 = " ".join(f"{30+i*5.4},{200-run10[i]*170}" for i in range(len(eps)))
    pts11_solid = " ".join(f"{30+i*5.4},{200-run11[i]*170}" for i in range(min(len(eps), 43)))  # up to ep 420 (current)
    pts11_dashed = " ".join(f"{30+i*5.4},{200-run11[i]*170}" for i in range(42, len(eps)))  # projected

    # Delta plan
    changes = [
        ("Reward weights", "v2 → v3 (grasp +0.05, smooth -0.03)", "#22c55e", True),
        ("Demo count", "300 new real robot demos (PI + Apt)", "#22c55e", True),
        ("Bimanual prep", "Dual-arm adapter (GR00T N2 compat)", "#38bdf8", False),
        ("DR config", "Friction + texture ranges expanded", "#22c55e", True),
        ("Chunk size", "Keep 16 (validated in action_chunking_v2)", "#22c55e", True),
        ("LoRA rank", "Increase 16→24 (test on staging first)", "#f59e0b", False),
    ]
    change_rows = ""
    for name, detail, color, confirmed in changes:
        status = "CONFIRMED" if confirmed else "PLANNED"
        status_color = "#22c55e" if confirmed else "#f59e0b"
        change_rows += f"""<div style="padding:6px 0;border-bottom:1px solid #1e293b;font-size:0.8em">
<div style="display:flex;justify-content:space-between">
<span style="color:#e2e8f0">{name}</span>
<span style="background:{status_color};color:#fff;padding:1px 6px;border-radius:3px;font-size:0.7em">{status}</span>
</div>
<div style="color:#64748b;margin-top:2px">{detail}</div>
</div>"""

    # Resource allocation
    resources = [("GPU-hrs (A100)", 48, "#22c55e"), ("Demo collection", 16, "#38bdf8"), ("Eval runs", 12, "#f59e0b"), ("HPO search", 8, "#a78bfa")]
    res_bars = ""
    for name, hrs, color in resources:
        w = int(hrs * 5)
        res_bars += f'<div style="margin:6px 0"><div style="display:flex;justify-content:space-between;font-size:0.75em"><span style="color:#94a3b8">{name}</span><span style="color:{color}">{hrs}h</span></div><div style="background:#0f172a;border-radius:3px;height:10px;margin-top:2px"><div style="width:{w}%;background:{color};height:10px;border-radius:3px"></div></div></div>'

    return f"""<!DOCTYPE html><html><head><title>DAgger Run11 Planner — Port {PORT}</title>
<style>body{{background:#0f172a;color:#e2e8f0;font-family:monospace;margin:0;padding:20px}}
h1{{color:#C74634;font-size:1.4em}}h2{{color:#38bdf8;font-size:1em}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:16px}}
.card{{background:#1e293b;border-radius:8px;padding:16px}}
svg{{width:100%;height:auto}}</style></head><body>
<h1>DAgger Run11 Planner</h1>
<div style="display:flex;gap:24px;margin-bottom:16px">
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#22c55e">0.84</div><div style="font-size:0.75em;color:#94a3b8">Target SR</div></div>
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#38bdf8">Apr 28</div><div style="font-size:0.75em;color:#94a3b8">Launch Date</div></div>
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#22c55e">300</div><div style="font-size:0.75em;color:#94a3b8">New Demos</div></div>
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#f59e0b">6</div><div style="font-size:0.75em;color:#94a3b8">Changes</div></div>
</div>
<div class="card"><h2>DAgger Family SR Projections (run9 / run10 / run11)</h2>
<svg viewBox="0 0 580 225"><rect width="580" height="225" fill="#0f172a" rx="4"/>
<line x1="30" y1="10" x2="30" y2="205" stroke="#334155" stroke-width="1"/>
<line x1="30" y1="205" x2="570" y2="205" stroke="#334155" stroke-width="1"/>
<polyline points="{pts9}" fill="none" stroke="#64748b" stroke-width="1.5"/>
<polyline points="{pts10}" fill="none" stroke="#38bdf8" stroke-width="2"/>
<polyline points="{pts11_solid}" fill="none" stroke="#22c55e" stroke-width="2.5"/>
<polyline points="{pts11_dashed}" fill="none" stroke="#22c55e" stroke-width="2" stroke-dasharray="6,4"/>
<!-- Current position run10 -->
<circle cx="{30+42*5.4}" cy="{200-run10[42]*170}" r="5" fill="#38bdf8"/>
<text x="{35+42*5.4}" cy="0" y="{195-run10[42]*170}" fill="#38bdf8" font-size="8">run10 ep420</text>
<text x="470" y="185" fill="#64748b" font-size="9">run9</text>
<text x="470" y="140" fill="#38bdf8" font-size="9">run10</text>
<text x="470" y="90" fill="#22c55e" font-size="9">run11 (proj)</text>
<line x1="257" y1="10" x2="257" y2="205" stroke="#22c55e" stroke-dasharray="2,4" stroke-width="1" opacity="0.4"/>
<text x="200" y="218" fill="#64748b" font-size="9">Episodes</text>
</svg></div>
<div class="grid">
<div class="card"><h2>Run11 Delta Plan</h2>
{change_rows}
</div>
<div class="card"><h2>Resource Budget</h2>
{res_bars}
<div style="margin-top:12px;font-size:0.8em;color:#64748b">Total: 84 GPU-hours estimated. $36.12 at OCI A100 spot rate.</div>
</div>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="DAgger Run11 Planner")
    @app.get("/", response_class=HTMLResponse)
    def index(): return build_html()
    @app.get("/health")
    def health(): return {"status":"ok","port":PORT,"target_sr":0.84,"launch_date":"2026-04-28"}

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
