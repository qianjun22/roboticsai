"""Partner Capacity Advisor — FastAPI port 8498"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8498

def build_html():
    partners = [
        ("Apptronik", 2, 4, "upgrade", "#22c55e", "pilot scale-up"),
        ("Figure AI", 1, 1, "maintain", "#38bdf8", "stable usage"),
        ("1X Technologies", 2, 1, "downgrade", "#ef4444", "churn risk"),
        ("Skild AI", 1, 2, "upgrade", "#f59e0b", "growing fast"),
        ("Covariant", 1, 1, "maintain", "#64748b", "evaluation phase"),
    ]
    
    forecast_rows = ""
    for name, current_gpu, projected_gpu, rec, col, note in partners:
        arrow = "↑" if projected_gpu > current_gpu else ("↓" if projected_gpu < current_gpu else "→")
        rec_bg = {"upgrade": "#22c55e", "maintain": "#38bdf8", "downgrade": "#ef4444"}[rec]
        forecast_rows += f'''<tr>
<td style="color:#e2e8f0">{name}</td>
<td style="text-align:center">{current_gpu}×A100</td>
<td style="text-align:center;color:{col}">{projected_gpu}×A100 {arrow}</td>
<td><span style="background:{rec_bg};color:#0f172a;padding:1px 6px;border-radius:3px;font-size:11px">{rec}</span></td>
<td style="color:#64748b;font-size:11px">{note}</td>
</tr>'''
    
    # demand forecast chart
    months = ["Apr", "May", "Jun", "Jul", "Aug", "Sep"]
    demands = {
        "Apptronik": [2, 3, 4, 4, 4, 4],
        "Figure AI": [1, 1, 1, 1, 1, 1],
        "1X Tech": [2, 2, 1, 1, 1, 1],
        "Skild AI": [1, 1, 2, 2, 2, 2],
    }
    colors = {"Apptronik": "#22c55e", "Figure AI": "#38bdf8", "1X Tech": "#ef4444", "Skild AI": "#f59e0b"}
    demand_svgs = ""
    for partner, vals in demands.items():
        pts = []
        for i, v in enumerate(vals):
            x = i * 500 / 5
            y = 80 - v * 18
            pts.append(f"{x:.1f},{y:.1f}")
        demand_svgs += f'<polyline points="{" ".join(pts)}" fill="none" stroke="{colors[partner]}" stroke-width="2"/>'
    
    legend = "".join([f'<span style="color:{v}">— {k}</span><span style="margin-right:10px"> </span>' for k,v in colors.items()])
    
    total_current = sum(p[1] for p in partners)
    total_projected = sum(p[2] for p in partners)
    
    return f"""<!DOCTYPE html><html><head><title>Partner Capacity Advisor</title>
<style>body{{margin:0;font-family:monospace;background:#0f172a;color:#e2e8f0}}
.hdr{{background:#C74634;padding:16px 24px;display:flex;justify-content:space-between;align-items:center}}
.hdr h1{{margin:0;font-size:20px;color:#fff}}.hdr span{{color:#fca5a5;font-size:13px}}
.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;padding:20px}}
.card{{background:#1e293b;border-radius:8px;padding:16px}}
.card h3{{margin:0 0 12px;color:#38bdf8;font-size:14px;text-transform:uppercase;letter-spacing:1px}}
.stat{{font-size:36px;font-weight:bold;color:#f1f5f9}}.sub{{color:#64748b;font-size:12px;margin-top:4px}}
table{{width:100%;border-collapse:collapse;font-size:12px}}
th{{text-align:left;color:#64748b;padding:6px 0;border-bottom:1px solid #334155}}
td{{padding:6px 4px;border-bottom:1px solid #1e293b}}</style></head>
<body>
<div class="hdr"><h1>Partner Capacity Advisor</h1><span>port {PORT} · 5 partners</span></div>
<div class="grid">
<div class="card"><h3>Current GPUs</h3><div class="stat">{total_current}×</div><div class="sub">A100 allocated to partners</div></div>
<div class="card"><h3>6-Month Projected</h3><div class="stat">{total_projected}×</div><div class="sub">A100 needed by Sep 2026</div></div>
<div class="card"><h3>Upgrades Needed</h3><div class="stat">2</div><div class="sub">Apt + Skild · pre-provision now</div></div>
<div class="card" style="grid-column:span 3"><h3>Capacity Recommendations</h3>
<table><tr><th>Partner</th><th>Current</th><th>+6 Month</th><th>Action</th><th>Note</th></tr>{forecast_rows}</table></div>
<div class="card" style="grid-column:span 3"><h3>GPU Demand Forecast (Apr–Sep 2026)</h3>
<div style="font-size:11px;margin-bottom:8px">{legend}</div>
<svg width="100%" viewBox="0 0 500 80">{demand_svgs}</svg></div>
</div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Partner Capacity Advisor")
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
