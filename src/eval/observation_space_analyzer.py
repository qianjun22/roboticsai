"""Observation Space Analyzer — FastAPI port 8502"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8502

def build_html():
    modalities = [
        ("wrist_rgb", 68, "#22c55e", 0.91, "224×224 RGB image"),
        ("proprio", 19, "#38bdf8", 0.87, "joint angles, ee pose, vel"),
        ("overhead_rgb", 11, "#f59e0b", 0.74, "480×270 overhead camera"),
        ("force_torque", 2, "#a78bfa", 0.61, "6-axis F/T sensor"),
    ]
    
    # PCA variance explained donut
    cx, cy, r = 80, 80, 55
    donut = ""
    start = 0
    for name, pct, col, _ , _ in modalities:
        angle = pct / 100 * 360
        rad1 = math.radians(start)
        rad2 = math.radians(start + angle)
        x1 = cx + r * math.cos(rad1)
        y1 = cy + r * math.sin(rad1)
        x2 = cx + r * math.cos(rad2)
        y2 = cy + r * math.sin(rad2)
        large = 1 if angle > 180 else 0
        donut += f'<path d="M {cx} {cy} L {x1:.1f} {y1:.1f} A {r} {r} 0 {large} 1 {x2:.1f} {y2:.1f} Z" fill="{col}" opacity="0.85"/>'
        start += angle
    donut += f'<circle cx="{cx}" cy="{cy}" r="35" fill="#1e293b"/>'
    donut += f'<text x="{cx}" y="{cy-4}" text-anchor="middle" fill="white" font-size="11" font-weight="bold">PCA</text>'
    donut += f'<text x="{cx}" y="{cy+10}" text-anchor="middle" fill="#64748b" font-size="9">variance</text>'
    
    legend = "".join([f'<div style="display:flex;align-items:center;margin-bottom:4px"><span style="background:{c};width:10px;height:10px;border-radius:2px;margin-right:6px"></span><span style="color:#94a3b8;font-size:11px">{n} ({p}%)</span></div>' for n,p,c,_,_ in modalities])
    
    # correlation heatmap
    dims = ["j_ang", "ee_xyz", "w_rgb", "oh_rgb", "ft"]
    corr_mat = [
        [1.0, 0.87, 0.23, 0.18, 0.12],
        [0.87, 1.0, 0.29, 0.21, 0.34],
        [0.23, 0.29, 1.0, 0.61, 0.08],
        [0.18, 0.21, 0.61, 1.0, 0.06],
        [0.12, 0.34, 0.08, 0.06, 1.0],
    ]
    heatmap = ""
    for i, row in enumerate(corr_mat):
        for j, val in enumerate(row):
            col = "#ef4444" if val > 0.8 and i != j else ("#f59e0b" if val > 0.5 else "#38bdf8")
            x = j * 55 + 5
            y = i * 22 + 5
            heatmap += f'<rect x="{x}" y="{y}" width="50" height="18" fill="{col}" opacity="{val:.2f}" rx="2"/>'
            heatmap += f'<text x="{x+25}" y="{y+13}" text-anchor="middle" fill="white" font-size="9">{val:.2f}</text>'
    
    heatmap += "".join([f'<text x="{j*55+30}" y="125" text-anchor="middle" fill="#64748b" font-size="9">{d}</text>' for j,d in enumerate(dims)])
    
    # SR contribution bar
    modality_rows = ""
    for name, pct, col, sr_contribution, desc in modalities:
        modality_rows += f'<div style="margin-bottom:8px"><div style="display:flex;justify-content:space-between;margin-bottom:3px"><span style="color:{col}">{name}</span><span style="color:#94a3b8;font-size:11px">SR contrib: {sr_contribution:.2f} · {desc}</span></div><div style="background:#334155;border-radius:3px;height:8px"><div style="background:{col};width:{pct}%;height:8px;border-radius:3px"></div></div></div>'
    
    return f"""<!DOCTYPE html><html><head><title>Observation Space Analyzer</title>
<style>body{{margin:0;font-family:monospace;background:#0f172a;color:#e2e8f0}}
.hdr{{background:#C74634;padding:16px 24px;display:flex;justify-content:space-between;align-items:center}}
.hdr h1{{margin:0;font-size:20px;color:#fff}}.hdr span{{color:#fca5a5;font-size:13px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;padding:20px}}
.card{{background:#1e293b;border-radius:8px;padding:16px}}
.card h3{{margin:0 0 12px;color:#38bdf8;font-size:14px;text-transform:uppercase;letter-spacing:1px}}
.stat{{font-size:36px;font-weight:bold;color:#f1f5f9}}.sub{{color:#64748b;font-size:12px;margin-top:4px}}</style></head>
<body>
<div class="hdr"><h1>Observation Space Analyzer</h1><span>port {PORT} · 4 modalities</span></div>
<div class="grid">
<div class="card"><h3>Top Modality</h3><div class="stat">68%</div><div class="sub">wrist_rgb PCA variance</div></div>
<div class="card"><h3>Redundancy Found</h3><div class="stat" style="color:#f59e0b">0.87</div><div class="sub">j_angle ↔ ee_xyz correlation</div></div>
<div class="card"><h3>PCA Variance by Modality</h3>
<div style="display:flex;gap:16px;align-items:center">
<svg width="160" height="160" viewBox="0 0 160 160">{donut}</svg>
<div>{legend}</div></div></div>
<div class="card"><h3>Correlation Heatmap</h3>
<svg width="100%" viewBox="0 0 280 130">{heatmap}</svg></div>
<div class="card" style="grid-column:span 2"><h3>Modality SR Contribution</h3>{modality_rows}</div>
</div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Observation Space Analyzer")
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
