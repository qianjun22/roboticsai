"""OCI Billing v3 — FastAPI port 8493"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8493

def build_html():
    categories = [
        ("Compute (A100)", 142, "#C74634"),
        ("Storage (NVMe)", 28, "#38bdf8"),
        ("Network egress", 18, "#f59e0b"),
        ("Object storage", 22, "#22c55e"),
        ("Misc infra", 14, "#a78bfa"),
    ]
    total = sum(c[1] for c in categories)
    
    # donut
    cx, cy, r = 100, 100, 70
    donut = ""
    start_angle = 0
    for name, val, col in categories:
        angle = val / total * 360
        rad1 = math.radians(start_angle)
        rad2 = math.radians(start_angle + angle)
        x1 = cx + r * math.cos(rad1)
        y1 = cy + r * math.sin(rad1)
        x2 = cx + r * math.cos(rad2)
        y2 = cy + r * math.sin(rad2)
        large = 1 if angle > 180 else 0
        donut += f'<path d="M {cx} {cy} L {x1:.1f} {y1:.1f} A {r} {r} 0 {large} 1 {x2:.1f} {y2:.1f} Z" fill="{col}" opacity="0.85"/>'
        start_angle += angle
    inner_r = 45
    donut += f'<circle cx="{cx}" cy="{cy}" r="{inner_r}" fill="#1e293b"/>'
    donut += f'<text x="{cx}" y="{cy-6}" text-anchor="middle" fill="white" font-size="14" font-weight="bold">${total}</text>'
    donut += f'<text x="{cx}" y="{cy+10}" text-anchor="middle" fill="#64748b" font-size="9">/month</text>'
    
    # burn rate trend
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep"]
    actuals = [142, 168, 224, None, None, None, None, None, None]
    forecasts = [None, None, 224, 256, 287, 312, 298, 324, 489]
    
    actual_pts = []
    forecast_pts = []
    for i, (a, f) in enumerate(zip(actuals, forecasts)):
        x = i * 540 / 8
        if a is not None:
            y = 80 - (a - 100) / 400 * 80
            actual_pts.append(f"{x:.1f},{y:.1f}")
        if f is not None:
            y = 80 - (f - 100) / 400 * 80
            forecast_pts.append(f"{x:.1f},{y:.1f}")
    
    actual_svg = f'<polyline points="{" ".join(actual_pts)}" fill="none" stroke="#38bdf8" stroke-width="2"/>'
    forecast_svg = f'<polyline points="{" ".join(forecast_pts)}" fill="none" stroke="#f59e0b" stroke-width="2" stroke-dasharray="6,3"/>'
    budget_y = 80 - (500 - 100) / 400 * 80
    budget_line = f'<line x1="0" y1="{budget_y:.1f}" x2="540" y2="{budget_y:.1f}" stroke="#22c55e" stroke-width="1" stroke-dasharray="4,2"/>'
    
    legend_items = "".join([f'<div style="display:flex;align-items:center;margin-bottom:4px"><span style="background:{c};width:12px;height:12px;border-radius:2px;margin-right:6px"></span><span style="color:#e2e8f0;font-size:12px">{n}</span><span style="color:{c};margin-left:auto;font-size:12px">${v}</span></div>' for n,v,c in categories])
    
    return f"""<!DOCTYPE html><html><head><title>OCI Billing v3</title>
<style>body{{margin:0;font-family:monospace;background:#0f172a;color:#e2e8f0}}
.hdr{{background:#C74634;padding:16px 24px;display:flex;justify-content:space-between;align-items:center}}
.hdr h1{{margin:0;font-size:20px;color:#fff}}.hdr span{{color:#fca5a5;font-size:13px}}
.grid{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px;padding:20px}}
.card{{background:#1e293b;border-radius:8px;padding:16px}}
.card h3{{margin:0 0 12px;color:#38bdf8;font-size:14px;text-transform:uppercase;letter-spacing:1px}}
.stat{{font-size:36px;font-weight:bold;color:#f1f5f9}}.sub{{color:#64748b;font-size:12px;margin-top:4px}}</style></head>
<body>
<div class="hdr"><h1>OCI Billing v3</h1><span>port {PORT} · Mar 2026</span></div>
<div class="grid">
<div class="card"><h3>Monthly Spend</h3><div class="stat">${total}</div><div class="sub">of $500 budget · 55% headroom</div></div>
<div class="card"><h3>Sep Forecast</h3><div class="stat">$489</div><div class="sub">AI World spike · 3× normal</div></div>
<div class="card"><h3>Cost/SR-point</h3><div class="stat">$6.71</div><div class="sub">avg · trending down</div></div>
<div class="card"><h3>Cost Breakdown</h3>
<div style="display:flex;gap:16px;align-items:center">
<svg width="200" height="200" viewBox="0 0 200 200">{donut}</svg>
<div style="flex:1">{legend_items}</div>
</div></div>
<div class="card" style="grid-column:span 2"><h3>Burn Rate (Jan–Sep 2026)</h3>
<div style="font-size:11px;color:#64748b;margin-bottom:8px"><span style="color:#38bdf8">—</span> actual <span style="color:#f59e0b;margin-left:8px">- -</span> forecast <span style="color:#22c55e;margin-left:8px">- -</span> $500 budget</div>
<svg width="100%" viewBox="0 0 540 80">{actual_svg}{forecast_svg}{budget_line}</svg></div>
</div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="OCI Billing v3")
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
