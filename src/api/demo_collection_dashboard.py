"""Demo Collection Dashboard — FastAPI port 8486"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8486

def build_html():
    tasks = [
        ("pick_place", 420, 500, "#22c55e"),
        ("stack_blocks", 180, 300, "#f59e0b"),
        ("pour_liquid", 95, 200, "#ef4444"),
        ("open_drawer", 210, 250, "#22c55e"),
        ("wipe_surface", 130, 200, "#f59e0b"),
        ("fold_cloth", 42, 150, "#ef4444"),
    ]
    
    bars = ""
    for task, actual, target, col in tasks:
        pct = actual / target * 100
        bars += f'''<div style="margin-bottom:10px">
<div style="display:flex;justify-content:space-between;margin-bottom:3px">
<span style="color:#e2e8f0">{task}</span>
<span style="color:{col}">{actual}/{target} ({pct:.0f}%)</span>
</div>
<div style="background:#334155;border-radius:4px;height:8px">
<div style="background:{col};width:{min(pct,100):.0f}%;height:8px;border-radius:4px"></div>
</div></div>'''
    
    operators = [
        ("Op-1 (PI)", 4.8, 38, "#22c55e"),
        ("Op-2 (Apt)", 4.3, 29, "#22c55e"),
        ("Op-3 (1X)", 3.9, 22, "#38bdf8"),
        ("Op-4 (internal)", 4.1, 31, "#38bdf8"),
        ("Op-5 (contract)", 3.4, 18, "#f59e0b"),
    ]
    op_rows = ""
    for name, quality, rate, col in operators:
        op_rows += f'<tr><td style="color:#e2e8f0">{name}</td><td style="color:{col}">{quality}/5.0</td><td>{rate}/day</td></tr>'
    
    # collection rate trend
    days = list(range(30))
    rates = [20 + i*0.3 + random.uniform(-3,3) for i in days]
    target_rate = 38
    pts = []
    for i, v in enumerate(rates):
        x = i * 500 / 29
        y = 60 - (v - 10) / 35 * 60
        pts.append(f"{x:.1f},{y:.1f}")
    trend_svg = f'<polyline points="{" ".join(pts)}" fill="none" stroke="#38bdf8" stroke-width="2"/>'
    tgt_y = 60 - (target_rate - 10) / 35 * 60
    tgt_svg = f'<line x1="0" y1="{tgt_y:.1f}" x2="500" y2="{tgt_y:.1f}" stroke="#ef4444" stroke-width="1" stroke-dasharray="6,3"/>'
    
    total = sum(t[1] for t in tasks)
    target_total = sum(t[2] for t in tasks)
    
    return f"""<!DOCTYPE html><html><head><title>Demo Collection Dashboard</title>
<style>body{{margin:0;font-family:monospace;background:#0f172a;color:#e2e8f0}}
.hdr{{background:#C74634;padding:16px 24px;display:flex;justify-content:space-between;align-items:center}}
.hdr h1{{margin:0;font-size:20px;color:#fff}}.hdr span{{color:#fca5a5;font-size:13px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;padding:20px}}
.card{{background:#1e293b;border-radius:8px;padding:16px}}
.card h3{{margin:0 0 12px;color:#38bdf8;font-size:14px;text-transform:uppercase;letter-spacing:1px}}
.stat{{font-size:36px;font-weight:bold;color:#f1f5f9}}.sub{{color:#64748b;font-size:12px;margin-top:4px}}
table{{width:100%;border-collapse:collapse;font-size:13px}}
th{{text-align:left;color:#64748b;padding:6px 0;border-bottom:1px solid #334155}}
td{{padding:6px 0;border-bottom:1px solid #1e293b}}</style></head>
<body>
<div class="hdr"><h1>Demo Collection Dashboard</h1><span>port {PORT} · 5 operators</span></div>
<div class="grid">
<div class="card"><h3>Total Demos</h3><div class="stat">{total:,}</div><div class="sub">of {target_total} target · June deadline</div></div>
<div class="card"><h3>Collection Rate</h3><div class="stat">28/day</div><div class="sub">need 38/day for June · gap: 10/day</div></div>
<div class="card"><h3>Per-Task Progress</h3>{bars}</div>
<div class="card"><h3>Operator Leaderboard</h3>
<table><tr><th>Operator</th><th>Quality</th><th>Rate</th></tr>{op_rows}</table></div>
<div class="card" style="grid-column:span 2"><h3>Collection Rate Trend (30 days)</h3>
<div style="font-size:12px;color:#64748b;margin-bottom:8px"><span style="color:#ef4444">- -</span> target 38/day</div>
<svg width="100%" viewBox="0 0 500 60">{trend_svg}{tgt_svg}</svg></div>
</div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Demo Collection Dashboard")
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
