"""DAgger Run12 Planner — FastAPI port 8515"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8515

def build_html():
    runs = [
        ("dagger_run9", 5000, 71, "DONE", "#94a3b8"),
        ("dagger_run10", 1420, 64, "TRAINING", "#f59e0b"),
        ("dagger_run11", 0, 0, "PLANNED Apr 28", "#38bdf8"),
        ("dagger_run12", 0, 0, "PLANNED May 15", "#a78bfa"),
    ]
    
    # run progress bars
    run_bars = ""
    for name, steps, sr, status, col in runs:
        prog = steps / 5000 * 100 if steps > 0 else 0
        sr_str = f"SR={sr}%" if sr > 0 else "not started"
        run_bars += f'''<div style="margin-bottom:12px">
<div style="display:flex;justify-content:space-between;margin-bottom:4px">
<span style="color:{col}">{name}</span>
<span style="color:#94a3b8;font-size:12px">{status} · {sr_str}</span>
</div>
<div style="background:#334155;border-radius:4px;height:10px">
<div style="background:{col};width:{prog:.0f}%;height:10px;border-radius:4px"></div>
</div></div>'''
    
    # projected SR curves for run10/11/12
    steps = list(range(0, 5001, 250))
    def sr_curve(final_sr, noise=0.02):
        return [final_sr * (1 - math.exp(-4 * s/5000)) + random.uniform(-noise, noise) for s in steps]
    
    sr_r9 = sr_curve(0.71)
    sr_r10 = sr_curve(0.78)  # projected
    sr_r11 = sr_curve(0.84)  # projected
    sr_r12 = sr_curve(0.91)  # projected
    
    def to_pts(vals, col, dash=""):
        pts = []
        for i, v in enumerate(vals):
            x = i * 500 / (len(vals)-1)
            y = 100 - max(0,v) * 100
            pts.append(f"{x:.1f},{y:.1f}")
        return f'<polyline points="{" ".join(pts)}" fill="none" stroke="{col}" stroke-width="2" stroke-dasharray="{dash}"/>'
    
    curves_svg = to_pts(sr_r9, "#94a3b8") + to_pts(sr_r10, "#f59e0b", "8,4") + to_pts(sr_r11, "#38bdf8", "8,4") + to_pts(sr_r12, "#a78bfa", "8,4")
    # current step marker for run10
    cur_step_x = 1420 / 5000 * 500
    cur_sv = f'<line x1="{cur_step_x:.0f}" y1="0" x2="{cur_step_x:.0f}" y2="100" stroke="#f59e0b" stroke-width="1" stroke-dasharray="4,2"/>'
    
    # run12 config delta
    deltas = [
        ("Base model", "GR00T N1.6", "GR00T N2.0 (bimanual)", "#f59e0b"),
        ("Reward model", "shaped_v3", "RLHF reward model", "#22c55e"),
        ("Demo count", "400 (run11)", "+600 demos = 1000 total", "#22c55e"),
        ("Bimanual tasks", "0%", "20% of episodes", "#38bdf8"),
        ("Beta schedule", "adaptive_sr", "adaptive_sr + RLHF blend", "#38bdf8"),
    ]
    delta_rows = ""
    for name, before, after, col in deltas:
        delta_rows += f'<tr><td style="color:#94a3b8">{name}</td><td style="color:#64748b">{before}</td><td style="color:{col}">{after}</td></tr>'
    
    return f"""<!DOCTYPE html><html><head><title>DAgger Run12 Planner</title>
<style>body{{margin:0;font-family:monospace;background:#0f172a;color:#e2e8f0}}
.hdr{{background:#C74634;padding:16px 24px;display:flex;justify-content:space-between;align-items:center}}
.hdr h1{{margin:0;font-size:20px;color:#fff}}.hdr span{{color:#fca5a5;font-size:13px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;padding:20px}}
.card{{background:#1e293b;border-radius:8px;padding:16px}}
.card h3{{margin:0 0 12px;color:#38bdf8;font-size:14px;text-transform:uppercase;letter-spacing:1px}}
.stat{{font-size:36px;font-weight:bold;color:#f1f5f9}}.sub{{color:#64748b;font-size:12px;margin-top:4px}}
table{{width:100%;border-collapse:collapse;font-size:12px}}
th{{text-align:left;color:#64748b;padding:6px 0;border-bottom:1px solid #334155}}
td{{padding:6px 0;border-bottom:1px solid #1e293b}}</style></head>
<body>
<div class="hdr"><h1>DAgger Run12 Planner</h1><span>port {PORT} · May 15 launch target</span></div>
<div class="grid">
<div class="card"><h3>Run12 Target SR</h3><div class="stat">91%</div><div class="sub">GR00T N2.0 + RLHF + bimanual</div></div>
<div class="card"><h3>Launch Gate</h3><div class="stat">May 15</div><div class="sub">after run11 step 2000 SR≥0.75</div></div>
<div class="card"><h3>Run Progress</h3>{run_bars}</div>
<div class="card"><h3>SR Family Curves (run9→12)</h3>
<div style="font-size:10px;color:#64748b;margin-bottom:8px">
<span style="color:#94a3b8">— r9</span>
<span style="color:#f59e0b;margin-left:8px">-- r10</span>
<span style="color:#38bdf8;margin-left:8px">-- r11</span>
<span style="color:#a78bfa;margin-left:8px">-- r12</span>
</div>
<svg width="100%" viewBox="0 0 500 100">{curves_svg}{cur_sv}</svg></div>
<div class="card" style="grid-column:span 2"><h3>Run12 Config Delta (vs Run11)</h3>
<table><tr><th>Parameter</th><th>Run11</th><th>Run12</th></tr>{delta_rows}</table></div>
</div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="DAgger Run12 Planner")
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
