"""RLHF Preference Collector — FastAPI port 8494"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8494

def build_html():
    # preference dataset composition
    label_sources = [
        ("Human operators", 247, "#22c55e"),
        ("Auto-labeler (sim)", 183, "#38bdf8"),
        ("Simulation oracle", 70, "#f59e0b"),
    ]
    total_pairs = sum(s[1] for s in label_sources)
    
    # donut for label composition
    cx, cy, r = 80, 80, 55
    donut = ""
    start = 0
    for name, count, col in label_sources:
        angle = count / total_pairs * 360
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
    donut += f'<text x="{cx}" y="{cy-4}" text-anchor="middle" fill="white" font-size="12" font-weight="bold">{total_pairs}</text>'
    donut += f'<text x="{cx}" y="{cy+10}" text-anchor="middle" fill="#64748b" font-size="9">pairs</text>'
    
    legend = "".join([f'<div style="display:flex;align-items:center;margin-bottom:4px"><span style="background:{c};width:10px;height:10px;border-radius:2px;margin-right:6px"></span><span style="color:#94a3b8;font-size:11px">{n}: {v}</span></div>' for n,v,c in label_sources])
    
    # reward model training curve
    steps = list(range(0, 2001, 100))
    acc = [0.61 + (0.88 - 0.61) * (1 - math.exp(-i/600)) + random.uniform(-0.01, 0.01) for i in steps]
    
    pts = []
    for i, v in enumerate(acc):
        x = i * 500 / (len(steps)-1)
        y = 80 - (v - 0.55) / 0.45 * 80
        pts.append(f"{x:.1f},{y:.1f}")
    acc_svg = f'<polyline points="{" ".join(pts)}" fill="none" stroke="#38bdf8" stroke-width="2"/>'
    target_y = 80 - (0.85 - 0.55) / 0.45 * 80
    target_svg = f'<line x1="0" y1="{target_y:.1f}" x2="500" y2="{target_y:.1f}" stroke="#22c55e" stroke-width="1" stroke-dasharray="5,3"/>'
    
    # agreement matrix
    labelers = ["Human_1", "Human_2", "Auto", "Oracle"]
    agree_matrix = ""
    for i in range(4):
        for j in range(4):
            if i == j:
                val = 1.0
            elif (i < 2 and j < 2):
                val = 0.82 + random.uniform(-0.03, 0.03)
            else:
                val = 0.74 + random.uniform(-0.05, 0.05)
            col_intensity = val
            x = j * 70 + 5
            y = i * 22 + 5
            agree_matrix += f'<rect x="{x}" y="{y}" width="66" height="18" fill="#38bdf8" opacity="{col_intensity:.2f}" rx="2"/>'
            agree_matrix += f'<text x="{x+33}" y="{y+13}" text-anchor="middle" fill="white" font-size="10">{val:.2f}</text>'
    
    return f"""<!DOCTYPE html><html><head><title>RLHF Preference Collector</title>
<style>body{{margin:0;font-family:monospace;background:#0f172a;color:#e2e8f0}}
.hdr{{background:#C74634;padding:16px 24px;display:flex;justify-content:space-between;align-items:center}}
.hdr h1{{margin:0;font-size:20px;color:#fff}}.hdr span{{color:#fca5a5;font-size:13px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;padding:20px}}
.card{{background:#1e293b;border-radius:8px;padding:16px}}
.card h3{{margin:0 0 12px;color:#38bdf8;font-size:14px;text-transform:uppercase;letter-spacing:1px}}
.stat{{font-size:36px;font-weight:bold;color:#f1f5f9}}.sub{{color:#64748b;font-size:12px;margin-top:4px}}</style></head>
<body>
<div class="hdr"><h1>RLHF Preference Collector</h1><span>port {PORT} · {total_pairs} pairs labeled</span></div>
<div class="grid">
<div class="card"><h3>Total Pairs</h3><div class="stat">{total_pairs}</div><div class="sub">for reward model training</div></div>
<div class="card"><h3>Reward Model Acc</h3><div class="stat">88%</div><div class="sub">at step 2000 · target 85% ✓</div></div>
<div class="card"><h3>Label Composition</h3>
<div style="display:flex;gap:16px;align-items:center">
<svg width="160" height="160" viewBox="0 0 160 160">{donut}</svg>
<div>{legend}</div>
</div></div>
<div class="card"><h3>Labeler Agreement Matrix</h3>
<div style="font-size:11px;color:#64748b;margin-bottom:6px">{" | ".join(labelers)}</div>
<svg width="100%" viewBox="0 0 285 93">{agree_matrix}</svg></div>
<div class="card" style="grid-column:span 2"><h3>Reward Model Training Accuracy</h3>
<div style="font-size:12px;color:#64748b;margin-bottom:8px"><span style="color:#22c55e">- -</span> target 85%</div>
<svg width="100%" viewBox="0 0 500 80">{acc_svg}{target_svg}</svg></div>
</div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="RLHF Preference Collector")
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
