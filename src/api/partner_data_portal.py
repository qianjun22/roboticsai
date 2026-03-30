"""Partner Data Portal — FastAPI port 8477"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8477

def build_html():
    partners = [
        ("Apptronik", "Series B", 1240, 98.2, "#22c55e"),
        ("Figure AI", "Series B", 980, 97.8, "#22c55e"),
        ("1X Technologies", "Series A", 760, 96.5, "#38bdf8"),
        ("Skild AI", "Series A", 540, 95.1, "#38bdf8"),
        ("Covariant", "Series B", 320, 94.3, "#f59e0b"),
    ]
    bars = ""
    max_demos = max(p[2] for p in partners)
    for name, stage, demos, quality, col in partners:
        w = demos / max_demos * 100
        bars += f'''<div style="margin-bottom:12px">
<div style="display:flex;justify-content:space-between;margin-bottom:4px">
<span style="color:#e2e8f0">{name}</span>
<span style="color:{col}">{demos} demos · {quality}% quality</span>
</div>
<div style="background:#334155;border-radius:4px;height:8px">
<div style="background:{col};width:{w:.0f}%;height:8px;border-radius:4px"></div>
</div></div>'''

    total_demos = sum(p[2] for p in partners)
    avg_quality = sum(p[3] for p in partners) / len(partners)
    
    upload_days = list(range(30))
    uploads = [int(20 + 15*math.sin(d*0.4) + random.uniform(0,10)) for d in upload_days]
    pts = []
    for i, v in enumerate(uploads):
        x = i * 500 / 29
        y = 80 - v / max(uploads) * 80
        pts.append(f"{x:.1f},{y:.1f}")
    area_pts = f"0,80 " + " ".join(pts) + f" 500,80"
    svg_area = f'<polygon points="{area_pts}" fill="#38bdf8" fill-opacity="0.15"/><polyline points="{" ".join(pts)}" fill="none" stroke="#38bdf8" stroke-width="2"/>'
    
    return f"""<!DOCTYPE html><html><head><title>Partner Data Portal</title>
<style>body{{margin:0;font-family:monospace;background:#0f172a;color:#e2e8f0}}
.hdr{{background:#C74634;padding:16px 24px;display:flex;justify-content:space-between;align-items:center}}
.hdr h1{{margin:0;font-size:20px;color:#fff}}.hdr span{{color:#fca5a5;font-size:13px}}
.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;padding:20px}}
.card{{background:#1e293b;border-radius:8px;padding:16px}}
.card h3{{margin:0 0 12px;color:#38bdf8;font-size:14px;text-transform:uppercase;letter-spacing:1px}}
.stat{{font-size:36px;font-weight:bold;color:#f1f5f9}}.sub{{color:#64748b;font-size:12px;margin-top:4px}}</style></head>
<body>
<div class="hdr"><h1>Partner Data Portal</h1><span>port {PORT} · 5 design partners</span></div>
<div class="grid">
<div class="card"><h3>Total Demos</h3><div class="stat">{total_demos:,}</div><div class="sub">across 5 partners · growing</div></div>
<div class="card"><h3>Avg Quality</h3><div class="stat">{avg_quality:.1f}%</div><div class="sub">IK-validated trajectories</div></div>
<div class="card"><h3>Upload Rate</h3><div class="stat">{uploads[-1]}/day</div><div class="sub">last 24h uploads</div></div>
<div class="card" style="grid-column:span 3"><h3>Partner Demo Inventory</h3>{bars}</div>
<div class="card" style="grid-column:span 3"><h3>Upload Activity (30 days)</h3>
<svg width="100%" viewBox="0 0 500 80">{svg_area}</svg></div>
</div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Partner Data Portal")
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
