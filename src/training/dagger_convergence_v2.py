"""DAgger Convergence v2 — FastAPI port 8480"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8480

def build_html():
    runs = [
        ("dagger_run5", 5000, 5.0, "#94a3b8"),
        ("dagger_run9_v2.2", 5000, 71.0, "#22c55e"),
        ("dagger_run10", 1420, 38.0, "#f59e0b"),
        ("dagger_run11", 200, 12.0, "#38bdf8"),
    ]
    bars = ""
    for name, steps, sr, col in runs:
        prog = steps / 5000 * 100
        bars += f'''<div style="margin-bottom:14px">
<div style="display:flex;justify-content:space-between;margin-bottom:4px">
<span style="color:#e2e8f0">{name}</span>
<span style="color:{col}">SR={sr:.1f}% · {steps}/5000 steps</span>
</div>
<div style="background:#334155;border-radius:4px;height:10px">
<div style="background:{col};width:{prog:.0f}%;height:10px;border-radius:4px"></div>
</div></div>'''
    
    # convergence curves
    curves = []
    for run_idx, (name, max_steps, final_sr, col) in enumerate(runs):
        pts = []
        for i in range(min(max_steps, 200)):
            frac = i / 200
            sr_val = final_sr * (1 - math.exp(-4 * frac)) + random.uniform(-2, 2)
            sr_val = max(0, sr_val)
            x = frac * 500
            y = 100 - sr_val / 80 * 100
            pts.append(f"{x:.1f},{y:.1f}")
        curves.append(f'<polyline points="{" ".join(pts)}" fill="none" stroke="{col}" stroke-width="2"/>')
    
    legend = "".join([f'<span><span style="color:{c}">—</span> {n}</span>' for n,_,_,c in runs])
    
    return f"""<!DOCTYPE html><html><head><title>DAgger Convergence v2</title>
<style>body{{margin:0;font-family:monospace;background:#0f172a;color:#e2e8f0}}
.hdr{{background:#C74634;padding:16px 24px;display:flex;justify-content:space-between;align-items:center}}
.hdr h1{{margin:0;font-size:20px;color:#fff}}.hdr span{{color:#fca5a5;font-size:13px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;padding:20px}}
.card{{background:#1e293b;border-radius:8px;padding:16px}}
.card h3{{margin:0 0 12px;color:#38bdf8;font-size:14px;text-transform:uppercase;letter-spacing:1px}}
.stat{{font-size:36px;font-weight:bold;color:#f1f5f9}}.sub{{color:#64748b;font-size:12px;margin-top:4px}}</style></head>
<body>
<div class="hdr"><h1>DAgger Convergence v2</h1><span>port {PORT} · 4 runs tracked</span></div>
<div class="grid">
<div class="card"><h3>Best SR (Production)</h3><div class="stat">71%</div><div class="sub">dagger_run9_v2.2 · 5000 steps</div></div>
<div class="card"><h3>In Training (run10)</h3><div class="stat">38%</div><div class="sub">step 1420/5000 · target 65%+</div></div>
<div class="card" style="grid-column:span 2"><h3>Run Progress</h3>{bars}</div>
<div class="card" style="grid-column:span 2"><h3>Convergence Curves</h3>
<div style="display:flex;gap:16px;margin-bottom:8px;font-size:12px">{legend}</div>
<svg width="100%" viewBox="0 0 500 100">{"" .join(curves)}</svg></div>
</div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="DAgger Convergence v2")
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
