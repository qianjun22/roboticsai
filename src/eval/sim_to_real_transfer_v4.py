"""Sim-to-Real Transfer v4 — FastAPI port 8516"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8516

def build_html():
    milestones = [
        ("v1 (Genesis baseline)", 0, 27, "#94a3b8"),
        ("v2 (+Domain Rand)", 2, 22, "#64748b"),
        ("v2.5 (+Real demos)", 6, 18, "#38bdf8"),
        ("v3 (+Cosmos WM)", 10, 13, "#22c55e"),
        ("v3.5 (+DAgger r10)", 14, 10, "#22c55e"),
        ("v4 (+RLHF reward)", 20, 7, "#22c55e"),  # projected
    ]
    
    # gap closing timeline
    gap_pts = []
    for i, (name, month, gap, col) in enumerate(milestones):
        x = month / 22 * 500
        y = 100 - (27 - gap) / 20 * 100
        gap_pts.append(f"{x:.1f},{y:.1f}")
    gap_svg = f'<polyline points="{" ".join(gap_pts)}" fill="none" stroke="#38bdf8" stroke-width="2"/>'
    
    for i, (name, month, gap, col) in enumerate(milestones):
        x = month / 22 * 500
        y = 100 - (27 - gap) / 20 * 100
        gap_svg += f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="{col}"/>'
        if i % 2 == 0:
            gap_svg += f'<text x="{x:.1f}" y="{y-8:.1f}" text-anchor="middle" fill="{col}" font-size="8">{name[:8]}</text>'
    
    # target line at gap=5pp
    target_y = 100 - (27-5)/20*100
    gap_svg += f'<line x1="0" y1="{target_y:.1f}" x2="500" y2="{target_y:.1f}" stroke="#22c55e" stroke-width="1" stroke-dasharray="4,2"/>'
    
    # per-axis fidelity radar v3 vs v4
    axes = ["visual", "physics", "sensor", "contact", "lighting", "texture", "timing", "depth"]
    v3_scores = [0.87, 0.82, 0.76, 0.79, 0.71, 0.68, 0.84, 0.73]
    v4_scores = [0.89, 0.85, 0.81, 0.84, 0.78, 0.74, 0.87, 0.78]
    
    cx, cy, r = 160, 120, 90
    n = len(axes)
    
    v3_pts = []
    v4_pts = []
    for i, (a, s3, s4) in enumerate(zip(axes, v3_scores, v4_scores)):
        angle = math.radians(i * 360 / n - 90)
        x3 = cx + r * s3 * math.cos(angle)
        y3 = cy + r * s3 * math.sin(angle)
        x4 = cx + r * s4 * math.cos(angle)
        y4 = cy + r * s4 * math.sin(angle)
        v3_pts.append(f"{x3:.1f},{y3:.1f}")
        v4_pts.append(f"{x4:.1f},{y4:.1f}")
    
    radar_svg = f'<polygon points="{" ".join(v3_pts)}" fill="#38bdf8" fill-opacity="0.15" stroke="#38bdf8" stroke-width="1.5"/>'
    radar_svg += f'<polygon points="{" ".join(v4_pts)}" fill="#22c55e" fill-opacity="0.15" stroke="#22c55e" stroke-width="1.5"/>'
    
    for i, axis in enumerate(axes):
        angle = math.radians(i * 360 / n - 90)
        ax = cx + (r+15) * math.cos(angle)
        ay = cy + (r+15) * math.sin(angle)
        radar_svg += f'<text x="{ax:.1f}" y="{ay:.1f}" text-anchor="middle" fill="#64748b" font-size="9">{axis}</text>'
        radar_svg += f'<line x1="{cx}" y1="{cy}" x2="{cx + r * math.cos(angle):.1f}" y2="{cy + r * math.sin(angle):.1f}" stroke="#334155" stroke-width="0.5"/>'
    
    return f"""<!DOCTYPE html><html><head><title>Sim-to-Real Transfer v4</title>
<style>body{{margin:0;font-family:monospace;background:#0f172a;color:#e2e8f0}}
.hdr{{background:#C74634;padding:16px 24px;display:flex;justify-content:space-between;align-items:center}}
.hdr h1{{margin:0;font-size:20px;color:#fff}}.hdr span{{color:#fca5a5;font-size:13px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;padding:20px}}
.card{{background:#1e293b;border-radius:8px;padding:16px}}
.card h3{{margin:0 0 12px;color:#38bdf8;font-size:14px;text-transform:uppercase;letter-spacing:1px}}
.stat{{font-size:36px;font-weight:bold;color:#f1f5f9}}.sub{{color:#64748b;font-size:12px;margin-top:4px}}</style></head>
<body>
<div class="hdr"><h1>Sim-to-Real Transfer v4</h1><span>port {PORT}</span></div>
<div class="grid">
<div class="card"><h3>Current Gap</h3><div class="stat">10pp</div><div class="sub">SR: sim 0.81 → real 0.71</div></div>
<div class="card"><h3>v4 Target Gap</h3><div class="stat">7pp</div><div class="sub">with RLHF reward model</div></div>
<div class="card" style="grid-column:span 2"><h3>Gap Closing Timeline (27pp → 7pp)</h3>
<div style="font-size:11px;color:#64748b;margin-bottom:8px"><span style="color:#22c55e">- -</span> 5pp target</div>
<svg width="100%" viewBox="0 0 500 100">{gap_svg}</svg></div>
<div class="card"><h3>Fidelity Radar v3 vs v4</h3>
<div style="font-size:11px;color:#64748b;margin-bottom:8px"><span style="color:#38bdf8">— v3</span> <span style="color:#22c55e;margin-left:8px">— v4</span></div>
<svg width="100%" viewBox="0 0 320 240">{radar_svg}</svg></div>
<div class="card"><h3>Biggest Gap Reducers</h3>
<div style="font-size:13px;line-height:2;color:#94a3b8">
<div style="color:#22c55e">-5pp</div> Cosmos WM photorealistic rendering (v3)
<div style="color:#22c55e">-4pp</div> DAgger real-world feedback (v3.5)
<div style="color:#38bdf8">-4pp</div> Domain randomization v2 (v2)
<div style="color:#38bdf8">-3pp</div> Real demonstration dataset (v2.5)
<div style="color:#f59e0b">-3pp</div> RLHF reward alignment (v4, projected)
</div></div>
</div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Sim-to-Real Transfer v4")
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
