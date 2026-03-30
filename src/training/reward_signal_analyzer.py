"""Reward Signal Analyzer — FastAPI port 8365"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8365

def build_html():
    random.seed(66)
    eps = list(range(1, 101))
    
    # 6-component reward breakdown per episode
    components = [
        ("reach", [round(0.12 + 0.04*math.sin(e/8) + 0.01*random.uniform(-1,1), 3) for e in eps], "#38bdf8"),
        ("grasp", [round(max(0, 0.18 + 0.06*(1-math.exp(-e/30)) + 0.02*random.uniform(-1,1)), 3) for e in eps], "#22c55e"),
        ("lift", [round(max(0, 0.22 * (1-math.exp(-e/40)) + 0.03*random.uniform(-1,1)), 3) for e in eps], "#f59e0b"),
        ("stability", [round(max(0, 0.08 + 0.04*math.sin(e/12) + 0.01*random.uniform(-1,1)), 3) for e in eps], "#a78bfa"),
        ("smooth", [round(max(0, 0.06 + 0.02*(e/100) + 0.01*random.uniform(-1,1)), 3) for e in eps], "#ec4899"),
        ("time_bonus", [round(max(0, 0.04 * (1-math.exp(-e/60))), 3) for e in eps], "#06b6d4"),
    ]

    # Build stacked area paths (simplified as lines stacked)
    stacked_svg = ""
    prev_cumulative = [0.0] * len(eps)
    for comp_name, comp_vals, color in components:
        new_cumulative = [prev_cumulative[i] + comp_vals[i] for i in range(len(eps))]
        pts_top = " ".join(f"{30+i*4.8},{180-new_cumulative[i]*120}" for i in range(len(eps)))
        pts_bot = " ".join(f"{30+i*4.8},{180-prev_cumulative[i]*120}" for i in reversed(range(len(eps))))
        stacked_svg += f'<polygon points="{pts_top} {pts_bot}" fill="{color}" opacity="0.7"/>'
        prev_cumulative = new_cumulative

    # SR comparison: sparse vs shaped_v3
    sparse_sr = [round(min(0.32, 0.02 + 0.30*(1-math.exp(-e/80)) + 0.02*random.uniform(-1,1)), 3) for e in eps]
    shaped_sr = [round(min(0.72, 0.05 + 0.67*(1-math.exp(-e/50)) + 0.02*random.uniform(-1,1)), 3) for e in eps]
    
    pts_sparse = " ".join(f"{30+i*4.8},{180-sparse_sr[i]*180}" for i in range(len(eps)))
    pts_shaped = " ".join(f"{30+i*4.8},{180-shaped_sr[i]*180}" for i in range(len(eps)))

    # Optimal weight table
    weights = [
        ("reach", 0.10, 0.15),
        ("grasp", 0.30, 0.35),
        ("lift", 0.35, 0.30),
        ("stability", 0.10, 0.10),
        ("smooth", 0.08, 0.05),
        ("time_bonus", 0.07, 0.05),
    ]
    weight_rows = ""
    for comp, v2, v3 in weights:
        diff = round(v3 - v2, 2)
        diff_color = "#22c55e" if diff > 0 else "#C74634" if diff < 0 else "#94a3b8"
        diff_str = f"+{diff}" if diff > 0 else str(diff)
        weight_rows += f"""<tr>
<td style="padding:6px;color:#e2e8f0">{comp}</td>
<td style="padding:6px;color:#94a3b8">{v2}</td>
<td style="padding:6px;color:#22c55e">{v3}</td>
<td style="padding:6px;color:{diff_color}">{diff_str}</td>
</tr>"""

    return f"""<!DOCTYPE html><html><head><title>Reward Signal Analyzer — Port {PORT}</title>
<style>body{{background:#0f172a;color:#e2e8f0;font-family:monospace;margin:0;padding:20px}}
h1{{color:#C74634;font-size:1.4em}}h2{{color:#38bdf8;font-size:1em}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:16px}}
.card{{background:#1e293b;border-radius:8px;padding:16px}}
table{{width:100%;border-collapse:collapse}}
th{{padding:6px;color:#64748b;text-align:left;border-bottom:1px solid #334155;font-size:0.8em}}
svg{{width:100%;height:auto}}</style></head><body>
<h1>Reward Signal Analyzer</h1>
<div style="display:flex;gap:24px;margin-bottom:16px">
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#22c55e">0.72</div><div style="font-size:0.75em;color:#94a3b8">shaped_v3 SR</div></div>
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#C74634">0.31</div><div style="font-size:0.75em;color:#94a3b8">sparse SR</div></div>
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#38bdf8">6</div><div style="font-size:0.75em;color:#94a3b8">Components</div></div>
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#f59e0b">run11</div><div style="font-size:0.75em;color:#94a3b8">Target</div></div>
</div>
<div class="grid">
<div class="card"><h2>Reward Component Stacked Area (100 eps)</h2>
<svg viewBox="0 0 520 200"><rect width="520" height="200" fill="#0f172a" rx="4"/>
<line x1="30" y1="180" x2="510" y2="180" stroke="#334155" stroke-width="1"/>
{stacked_svg}
<text x="260" y="195" fill="#64748b" font-size="9">Episode</text>
</svg>
<div style="font-size:0.7em;color:#64748b;margin-top:4px">
<span style="color:#38bdf8">&#9632;</span> reach &nbsp;<span style="color:#22c55e">&#9632;</span> grasp &nbsp;<span style="color:#f59e0b">&#9632;</span> lift &nbsp;<span style="color:#a78bfa">&#9632;</span> stable &nbsp;<span style="color:#ec4899">&#9632;</span> smooth &nbsp;<span style="color:#06b6d4">&#9632;</span> time
</div>
</div>
<div class="card"><h2>Sparse vs Shaped SR</h2>
<svg viewBox="0 0 520 200"><rect width="520" height="200" fill="#0f172a" rx="4"/>
<line x1="30" y1="10" x2="30" y2="185" stroke="#334155" stroke-width="1"/>
<line x1="30" y1="185" x2="510" y2="185" stroke="#334155" stroke-width="1"/>
<polyline points="{pts_sparse}" fill="none" stroke="#C74634" stroke-width="2"/>
<polyline points="{pts_shaped}" fill="none" stroke="#22c55e" stroke-width="2"/>
<text x="400" y="60" fill="#22c55e" font-size="9">shaped_v3 0.72</text>
<text x="400" y="160" fill="#C74634" font-size="9">sparse 0.31</text>
<text x="260" y="198" fill="#64748b" font-size="9">Episode</text>
</svg>
</div>
</div>
<div class="card" style="margin-top:16px">
<h2>Optimal Reward Weights (run10 v2 → run11 v3)</h2>
<table><thead><tr><th>Component</th><th>v2 weight</th><th>v3 weight</th><th>&#916;</th></tr></thead>
<tbody>{weight_rows}</tbody></table>
<div style="margin-top:8px;font-size:0.75em;color:#64748b">Grasp weight increased (+0.05) — primary failure mode per error analysis. Smooth weight reduced to allow faster exploration.</div>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Reward Signal Analyzer")
    @app.get("/", response_class=HTMLResponse)
    def index(): return build_html()
    @app.get("/health")
    def health(): return {"status":"ok","port":PORT,"shaped_sr":0.72,"sparse_sr":0.31,"components":6}

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
