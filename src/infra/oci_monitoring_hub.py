"""OCI Monitoring Hub — FastAPI port 8517"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8517

def build_html():
    signals = [
        ("GPU Util", 87, "%", "#22c55e"),
        ("CPU Load", 42, "%", "#22c55e"),
        ("Memory", 71, "%", "#38bdf8"),
        ("Network", 28, "%", "#38bdf8"),
        ("Storage", 54, "%", "#22c55e"),
        ("Latency", 226, "ms", "#22c55e"),
    ]
    
    # 6 sparklines
    sparklines = ""
    for i, (name, current, unit, col) in enumerate(signals):
        row = i // 3
        col_i = i % 3
        x_offset = col_i * 175 + 10
        y_offset = row * 80 + 5
        
        # sparkline data
        hist = [current * (0.85 + 0.3 * random.random()) for _ in range(20)]
        hist[-1] = current
        mn, mx = min(hist), max(hist)
        
        pts = []
        for j, v in enumerate(hist):
            x = x_offset + j * 8
            y = y_offset + 50 - (v - mn) / (mx - mn + 0.01) * 40
            pts.append(f"{x:.0f},{y:.1f}")
        
        sparklines += f'<text x="{x_offset}" y="{y_offset+12}" fill="{col}" font-size="10" font-weight="bold">{name}</text>'
        sparklines += f'<text x="{x_offset+130}" y="{y_offset+12}" text-anchor="end" fill="{col}" font-size="12" font-weight="bold">{current}{unit}</text>'
        sparklines += f'<polyline points="{" ".join(pts)}" fill="none" stroke="{col}" stroke-width="1.5"/>'
    
    # alert event timeline
    alerts = [
        (3, "P2", "GPU4 ECC error", "#f59e0b"),
        (8, "P3", "Storage 78%", "#38bdf8"),
        (15, "P3", "Network latency spike", "#38bdf8"),
        (22, "P2", "Memory pressure 89%", "#f59e0b"),
        (26, "P3", "CPU spike (DAgger launch)", "#38bdf8"),
    ]
    alert_svg = ""
    for day, sev, desc, col in alerts:
        x = day / 30 * 500 + 10
        r = {"P1": 10, "P2": 7, "P3": 5}[sev]
        alert_svg += f'<circle cx="{x:.1f}" cy="30" r="{r}" fill="{col}" opacity="0.9"/>'
        alert_svg += f'<text x="{x:.1f}" y="50" text-anchor="middle" fill="{col}" font-size="8" transform="rotate(-15,{x:.1f},50)">{desc[:10]}</text>'
    
    composite_score = 92.4
    
    return f"""<!DOCTYPE html><html><head><title>OCI Monitoring Hub</title>
<style>body{{margin:0;font-family:monospace;background:#0f172a;color:#e2e8f0}}
.hdr{{background:#C74634;padding:16px 24px;display:flex;justify-content:space-between;align-items:center}}
.hdr h1{{margin:0;font-size:20px;color:#fff}}.hdr span{{color:#fca5a5;font-size:13px}}
.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;padding:20px}}
.card{{background:#1e293b;border-radius:8px;padding:16px}}
.card h3{{margin:0 0 12px;color:#38bdf8;font-size:14px;text-transform:uppercase;letter-spacing:1px}}
.stat{{font-size:36px;font-weight:bold;color:#f1f5f9}}.sub{{color:#64748b;font-size:12px;margin-top:4px}}</style></head>
<body>
<div class="hdr"><h1>OCI Monitoring Hub</h1><span>port {PORT} · 6 signals</span></div>
<div class="grid">
<div class="card"><h3>Health Score</h3><div class="stat">{composite_score}</div><div class="sub">composite · 4 A100 nodes</div></div>
<div class="card"><h3>P1 Alerts (30d)</h3><div class="stat">0</div><div class="sub">zero customer-visible incidents</div></div>
<div class="card"><h3>Active Anomalies</h3><div class="stat">0</div><div class="sub">all signals nominal</div></div>
<div class="card" style="grid-column:span 3"><h3>Live Signal Dashboard</h3>
<svg width="100%" viewBox="0 0 540 165">{sparklines}</svg></div>
<div class="card" style="grid-column:span 3"><h3>Alert Event Timeline (30 days)</h3>
<svg width="100%" viewBox="0 0 510 60">{alert_svg}</svg>
<div style="font-size:11px;color:#64748b;margin-top:4px">0 P1 · 2 P2 (resolved) · 3 P3 (resolved)</div></div>
</div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="OCI Monitoring Hub")
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
