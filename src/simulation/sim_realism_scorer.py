"""Sim Realism Scorer — FastAPI port 8482"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8482

def build_html():
    categories = [
        ("Visual Fidelity", 87.3, "texture resolution, lighting, shadow quality"),
        ("Physics Accuracy", 82.1, "contact forces, friction, collision response"),
        ("Sensor Noise Model", 76.4, "camera noise, depth artifacts, IMU drift"),
        ("Object Dynamics", 89.2, "rigid body, deformable, fluid simulation"),
        ("Lighting Variation", 71.8, "HDR, directional, ambient occlusion"),
        ("Camera Parameters", 93.5, "FOV, distortion, exposure matching"),
    ]
    bars = ""
    for cat, score, desc in categories:
        col = "#22c55e" if score >= 85 else ("#f59e0b" if score >= 75 else "#ef4444")
        bars += f'''<div style="margin-bottom:12px">
<div style="display:flex;justify-content:space-between;margin-bottom:4px">
<div><span style="color:#e2e8f0">{cat}</span><span style="color:#64748b;font-size:11px;margin-left:8px">{desc}</span></div>
<span style="color:{col}">{score:.1f}</span>
</div>
<div style="background:#334155;border-radius:4px;height:8px">
<div style="background:{col};width:{score}%;height:8px;border-radius:4px"></div>
</div></div>'''
    
    overall = sum(c[1] for c in categories) / len(categories)
    sim2real_gap = 100 - overall * 0.85
    
    trend = [overall - 8 + i * 0.3 + random.uniform(-1, 1) for i in range(30)]
    pts = []
    for i, v in enumerate(trend):
        x = i * 500 / 29
        y = 100 - (v - 60) / 40 * 100
        pts.append(f"{x:.1f},{y:.1f}")
    trend_svg = f'<polyline points="{" ".join(pts)}" fill="none" stroke="#38bdf8" stroke-width="2"/>'
    
    return f"""<!DOCTYPE html><html><head><title>Sim Realism Scorer</title>
<style>body{{margin:0;font-family:monospace;background:#0f172a;color:#e2e8f0}}
.hdr{{background:#C74634;padding:16px 24px;display:flex;justify-content:space-between;align-items:center}}
.hdr h1{{margin:0;font-size:20px;color:#fff}}.hdr span{{color:#fca5a5;font-size:13px}}
.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;padding:20px}}
.card{{background:#1e293b;border-radius:8px;padding:16px}}
.card h3{{margin:0 0 12px;color:#38bdf8;font-size:14px;text-transform:uppercase;letter-spacing:1px}}
.stat{{font-size:36px;font-weight:bold;color:#f1f5f9}}.sub{{color:#64748b;font-size:12px;margin-top:4px}}</style></head>
<body>
<div class="hdr"><h1>Sim Realism Scorer</h1><span>port {PORT} · Isaac Sim quality</span></div>
<div class="grid">
<div class="card"><h3>Overall Score</h3><div class="stat">{overall:.1f}</div><div class="sub">weighted average / 100</div></div>
<div class="card"><h3>Sim-to-Real Gap</h3><div class="stat">{sim2real_gap:.1f}%</div><div class="sub">estimated transfer degradation</div></div>
<div class="card"><h3>Top Category</h3><div class="stat">93.5</div><div class="sub">Camera Parameters matching</div></div>
<div class="card" style="grid-column:span 3"><h3>Category Scores</h3>{bars}</div>
<div class="card" style="grid-column:span 3"><h3>Score Trend (30 days)</h3>
<svg width="100%" viewBox="0 0 500 100">{trend_svg}</svg></div>
</div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Sim Realism Scorer")
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
