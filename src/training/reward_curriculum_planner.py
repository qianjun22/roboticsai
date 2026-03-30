"""Reward Curriculum Planner — FastAPI port 8487"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8487

def build_html():
    phases = [
        ("Phase 1: Sparse", 0, 800, "SR threshold 0.1", "#94a3b8", 12.0),
        ("Phase 2: Dense", 800, 2000, "SR threshold 0.35", "#38bdf8", 45.0),
        ("Phase 3: Shaped v3", 2000, 3500, "SR threshold 0.55", "#22c55e", 64.0),
        ("Phase 4: Adaptive", 3500, 5000, "SR threshold 0.65", "#f59e0b", 71.0),
        ("Phase 5: Run11 Target", 5000, 6000, "SR threshold 0.75", "#a78bfa", 82.0),
    ]
    
    # phase timeline SVG
    phase_svg = ""
    total_steps = 6000
    for i, (name, start, end, trigger, col, target_sr) in enumerate(phases):
        x = start * 540 / total_steps
        w = (end - start) * 540 / total_steps
        y = 10
        phase_svg += f'<rect x="{x:.1f}" y="{y}" width="{w:.1f}" height="30" fill="{col}" rx="3" opacity="0.8"/>'
        label = name.split(":")[1].strip()
        phase_svg += f'<text x="{x+4:.1f}" y="29" fill="white" font-size="9">{label}</text>'
        # transition marker
        if start > 0:
            phase_svg += f'<line x1="{x:.1f}" y1="0" x2="{x:.1f}" y2="55" stroke="white" stroke-width="1" stroke-dasharray="3,2" opacity="0.6"/>'
    
    # weight evolution
    components = [
        ("reach", [0.25, 0.15, 0.12, 0.10, 0.08], "#38bdf8"),
        ("grasp", [0.40, 0.35, 0.35, 0.32, 0.30], "#22c55e"),
        ("lift", [0.25, 0.28, 0.28, 0.28, 0.28], "#f59e0b"),
        ("smooth", [0.05, 0.12, 0.15, 0.18, 0.20], "#a78bfa"),
        ("time", [0.05, 0.10, 0.10, 0.12, 0.14], "#64748b"),
    ]
    weight_svg = ""
    for comp, weights, col in components:
        pts = []
        for i, w in enumerate(weights):
            x = i * 540 / 4
            y = 80 - w * 250
            pts.append(f"{x:.1f},{y:.1f}")
        weight_svg += f'<polyline points="{" ".join(pts)}" fill="none" stroke="{col}" stroke-width="2"/>'
    
    # SR ceiling per strategy
    strategies = [
        ("Sparse only", 31, "#ef4444"),
        ("Dense only", 62, "#f59e0b"),
        ("Shaped v3", 71, "#38bdf8"),
        ("Adaptive", 76, "#22c55e"),
        ("Run11 target", 82, "#a78bfa"),
    ]
    sr_bars = ""
    for strat, sr, col in strategies:
        w = sr
        sr_bars += f'''<div style="display:flex;align-items:center;margin-bottom:8px">
<span style="width:130px;color:#e2e8f0;font-size:12px">{strat}</span>
<div style="background:#334155;border-radius:3px;height:8px;width:200px">
<div style="background:{col};width:{w:.0f}%;height:8px;border-radius:3px"></div></div>
<span style="margin-left:8px;color:{col};font-size:12px">SR={sr}%</span>
</div>'''
    
    legend = "".join([f'<span style="margin-right:12px"><span style="color:{c}">—</span> {n}</span>' for n,_,c in components])
    
    return f"""<!DOCTYPE html><html><head><title>Reward Curriculum Planner</title>
<style>body{{margin:0;font-family:monospace;background:#0f172a;color:#e2e8f0}}
.hdr{{background:#C74634;padding:16px 24px;display:flex;justify-content:space-between;align-items:center}}
.hdr h1{{margin:0;font-size:20px;color:#fff}}.hdr span{{color:#fca5a5;font-size:13px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;padding:20px}}
.card{{background:#1e293b;border-radius:8px;padding:16px}}
.card h3{{margin:0 0 12px;color:#38bdf8;font-size:14px;text-transform:uppercase;letter-spacing:1px}}
.stat{{font-size:36px;font-weight:bold;color:#f1f5f9}}.sub{{color:#64748b;font-size:12px;margin-top:4px}}</style></head>
<body>
<div class="hdr"><h1>Reward Curriculum Planner</h1><span>port {PORT} · 5-phase curriculum</span></div>
<div class="grid">
<div class="card"><h3>Phase Count</h3><div class="stat">5</div><div class="sub">SR-triggered transitions</div></div>
<div class="card"><h3>Target SR</h3><div class="stat">82%</div><div class="sub">run11 ceiling (phase 5)</div></div>
<div class="card" style="grid-column:span 2"><h3>Phase Timeline (0–6000 steps)</h3>
<svg width="100%" viewBox="0 0 540 55">{phase_svg}</svg></div>
<div class="card"><h3>Reward Weight Evolution</h3>
<div style="font-size:11px;margin-bottom:8px">{legend}</div>
<svg width="100%" viewBox="0 0 540 80">{weight_svg}</svg></div>
<div class="card"><h3>SR Ceiling Per Strategy</h3>{sr_bars}</div>
</div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Reward Curriculum Planner")
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
