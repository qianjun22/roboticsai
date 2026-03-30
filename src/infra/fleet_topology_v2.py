"""Fleet Topology v2 — FastAPI port 8490"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8490

def build_html():
    regions = [
        ("Ashburn", 270, 80, 94.1, "PRIMARY", "#22c55e", "2×A100_80GB, 138.1.153.110"),
        ("Phoenix", 100, 200, 88.3, "EVAL", "#38bdf8", "1×A100_40GB"),
        ("Frankfurt", 440, 200, 91.2, "STAGING", "#f59e0b", "1×A100_40GB"),
    ]
    
    nodes = ""
    for name, x, y, health, role, col, desc in regions:
        nodes += f'''<circle cx="{x}" cy="{y}" r="35" fill="{col}" fill-opacity="0.15" stroke="{col}" stroke-width="2"/>
<text x="{x}" y="{y-8}" text-anchor="middle" fill="{col}" font-size="12" font-weight="bold">{name}</text>
<text x="{x}" y="{y+6}" text-anchor="middle" fill="white" font-size="10">{health}%</text>
<text x="{x}" y="{y+18}" text-anchor="middle" fill="{col}" font-size="9">{role}</text>'''
    
    # edges with latency
    edges_data = [
        (270, 80, 100, 200, "12ms", "#22c55e"),
        (270, 80, 440, 200, "71ms", "#f59e0b"),
        (100, 200, 440, 200, "98ms", "#ef4444"),
    ]
    edges = ""
    for x1, y1, x2, y2, lat, col in edges_data:
        mx, my = (x1+x2)//2, (y1+y2)//2
        edges += f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{col}" stroke-width="2" stroke-dasharray="5,3" opacity="0.6"/>'
        edges += f'<text x="{mx}" y="{my}" text-anchor="middle" fill="{col}" font-size="10">{lat}</text>'
    
    topo_svg = f'{edges}{nodes}'
    
    # health trend
    trend_data = [
        ("Ashburn", [92 + random.uniform(-1,2) for _ in range(30)], "#22c55e"),
        ("Phoenix", [87 + random.uniform(-2,2) for _ in range(30)], "#38bdf8"),
        ("Frankfurt", [90 + random.uniform(-1,2) for _ in range(30)], "#f59e0b"),
    ]
    trend_lines = ""
    for name, scores, col in trend_data:
        pts = []
        for i, v in enumerate(scores):
            x = i * 500 / 29
            y = 80 - (v - 80) / 20 * 80
            pts.append(f"{x:.1f},{y:.1f}")
        trend_lines += f'<polyline points="{" ".join(pts)}" fill="none" stroke="{col}" stroke-width="2"/>'
    
    legend = "".join([f'<span style="color:{c}">— {n}</span><span style="margin-right:12px"> </span>' for n,_,c in trend_data])
    
    return f"""<!DOCTYPE html><html><head><title>Fleet Topology v2</title>
<style>body{{margin:0;font-family:monospace;background:#0f172a;color:#e2e8f0}}
.hdr{{background:#C74634;padding:16px 24px;display:flex;justify-content:space-between;align-items:center}}
.hdr h1{{margin:0;font-size:20px;color:#fff}}.hdr span{{color:#fca5a5;font-size:13px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;padding:20px}}
.card{{background:#1e293b;border-radius:8px;padding:16px}}
.card h3{{margin:0 0 12px;color:#38bdf8;font-size:14px;text-transform:uppercase;letter-spacing:1px}}
.stat{{font-size:36px;font-weight:bold;color:#f1f5f9}}.sub{{color:#64748b;font-size:12px;margin-top:4px}}</style></head>
<body>
<div class="hdr"><h1>Fleet Topology v2</h1><span>port {PORT} · 3 regions · 4 A100s</span></div>
<div class="grid">
<div class="card"><h3>Fleet Health</h3><div class="stat">92.4%</div><div class="sub">composite score · 3 regions</div></div>
<div class="card"><h3>Ashburn↔Frankfurt</h3><div class="stat" style="color:#ef4444">71ms</div><div class="sub">borderline SLA (target &lt;100ms)</div></div>
<div class="card"><h3>Network Topology</h3>
<svg width="100%" viewBox="0 0 540 280" style="background:#0f172a">{topo_svg}</svg></div>
<div class="card"><h3>7-Day Health Trend</h3>
<div style="font-size:11px;margin-bottom:8px">{legend}</div>
<svg width="100%" viewBox="0 0 500 80">{trend_lines}</svg></div>
</div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Fleet Topology v2")
    @app.get("/", response_class=HTMLResponse)
    def index(): return build_html()
    @app.get("/health")
    def health_check(): return {"status": "ok", "port": PORT}

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
