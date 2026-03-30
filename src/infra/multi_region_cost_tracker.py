"""Multi-Region Cost Tracker — FastAPI port 8497"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8497

def build_html():
    regions = [
        ("Ashburn (Primary)", 142, 28, 18, "#22c55e", "138.1.153.110"),
        ("Phoenix (Eval)", 34, 8, 6, "#38bdf8", "A100_40GB"),
        ("Frankfurt (Staging)", 24, 6, 4, "#f59e0b", "A100_40GB"),
    ]
    
    total = sum(r[1]+r[2]+r[3] for r in regions)
    
    stacked_bars = ""
    for name, compute, storage, network, col, node_id in regions:
        region_total = compute + storage + network
        c_pct = compute / region_total * 100
        s_pct = storage / region_total * 100
        n_pct = network / region_total * 100
        
        stacked_bars += f'''<div style="margin-bottom:12px">
<div style="display:flex;justify-content:space-between;margin-bottom:4px">
<span style="color:{col}">{name}</span>
<span style="color:#94a3b8;font-size:12px">${region_total}/mo · {node_id}</span>
</div>
<div style="display:flex;border-radius:4px;overflow:hidden;height:12px">
<div style="background:{col};width:{c_pct:.0f}%;height:12px" title="Compute ${compute}"></div>
<div style="background:#38bdf8;width:{s_pct:.0f}%;height:12px;opacity:0.6" title="Storage ${storage}"></div>
<div style="background:#f59e0b;width:{n_pct:.0f}%;height:12px;opacity:0.4" title="Network ${network}"></div>
</div>
<div style="font-size:10px;color:#64748b;margin-top:3px">Compute ${compute} · Storage ${storage} · Network ${network}</div>
</div>'''
    
    # efficiency score
    eff_data = [
        ("Ashburn", 94.1, 91.0, "#22c55e"),
        ("Phoenix", 88.3, 62.0, "#38bdf8"),
        ("Frankfurt", 91.2, 71.0, "#f59e0b"),
    ]
    eff_bars = ""
    for name, health, util, col in eff_data:
        eff_score = (health * 0.4 + util * 0.6)
        eff_bars += f'''<div style="margin-bottom:10px">
<div style="display:flex;justify-content:space-between;margin-bottom:3px">
<span style="color:{col}">{name}</span>
<span style="color:#94a3b8;font-size:12px">eff: {eff_score:.1f}%</span>
</div>
<div style="background:#334155;border-radius:3px;height:8px">
<div style="background:{col};width:{eff_score:.0f}%;height:8px;border-radius:3px"></div>
</div></div>'''
    
    # monthly trend
    months = list(range(6))
    region_trends = {
        "Ashburn": [115, 128, 135, 138, 140, 142],
        "Phoenix": [28, 30, 32, 33, 34, 34],
        "Frankfurt": [19, 21, 22, 23, 23, 24],
    }
    cols = {"Ashburn": "#22c55e", "Phoenix": "#38bdf8", "Frankfurt": "#f59e0b"}
    trend_svgs = ""
    for region, vals in region_trends.items():
        pts = []
        for i, v in enumerate(vals):
            x = i * 500 / 5
            y = 80 - (v - 15) / 135 * 80
            pts.append(f"{x:.1f},{y:.1f}")
        trend_svgs += f'<polyline points="{" ".join(pts)}" fill="none" stroke="{cols[region]}" stroke-width="2"/>'
    
    legend = "".join([f'<span style="color:{v}">— {k}</span><span style="margin-right:10px"> </span>' for k,v in cols.items()])
    
    return f"""<!DOCTYPE html><html><head><title>Multi-Region Cost Tracker</title>
<style>body{{margin:0;font-family:monospace;background:#0f172a;color:#e2e8f0}}
.hdr{{background:#C74634;padding:16px 24px;display:flex;justify-content:space-between;align-items:center}}
.hdr h1{{margin:0;font-size:20px;color:#fff}}.hdr span{{color:#fca5a5;font-size:13px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;padding:20px}}
.card{{background:#1e293b;border-radius:8px;padding:16px}}
.card h3{{margin:0 0 12px;color:#38bdf8;font-size:14px;text-transform:uppercase;letter-spacing:1px}}
.stat{{font-size:36px;font-weight:bold;color:#f1f5f9}}.sub{{color:#64748b;font-size:12px;margin-top:4px}}</style></head>
<body>
<div class="hdr"><h1>Multi-Region Cost Tracker</h1><span>port {PORT} · 3 regions</span></div>
<div class="grid">
<div class="card"><h3>Total Monthly</h3><div class="stat">${total}</div><div class="sub">of $500 budget · 55% headroom</div></div>
<div class="card"><h3>Ashburn Share</h3><div class="stat">63%</div><div class="sub">primary region · 2×A100_80GB</div></div>
<div class="card"><h3>Regional Cost Breakdown</h3>{stacked_bars}
<div style="font-size:10px;color:#64748b"><span style="color:#22c55e">■</span> compute <span style="color:#38bdf8;margin-left:8px">■</span> storage <span style="color:#f59e0b;margin-left:8px">■</span> network</div></div>
<div class="card"><h3>GPU Efficiency Score</h3>{eff_bars}</div>
<div class="card" style="grid-column:span 2"><h3>Cost Trend (6 months)</h3>
<div style="font-size:11px;margin-bottom:8px">{legend}</div>
<svg width="100%" viewBox="0 0 500 80">{trend_svgs}</svg></div>
</div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Multi-Region Cost Tracker")
    @app.get("/", response_class=HTMLResponse)
    def index(): return build_html()
    @app.get("/health")
    def health(): return {"status": "ok", "port": PORT}

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
