"""Cost Per Demo — FastAPI port 8503"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8503

def build_html():
    demo_types = [
        ("Auto IK (Genesis sim)", 0.0017, 0.74, 312, "#22c55e"),
        ("Human teleop (Franka)", 3.40, 0.91, 28, "#C74634"),
        ("DAgger online", 0.043, 0.82, 47, "#38bdf8"),
        ("Sim SDG (Isaac RTX)", 0.012, 0.79, 89, "#f59e0b"),
        ("Hybrid auto+QA", 0.18, 0.86, 74, "#a78bfa"),
    ]
    
    # quality-adjusted cost ($/quality-point)
    qa_bars = ""
    for name, cost, quality, rate, col in demo_types:
        if quality > 0:
            qa_cost = cost / quality
        else:
            qa_cost = 0
        max_qa = max(dt[1]/dt[2] for dt in demo_types if dt[2] > 0)
        bar_w = qa_cost / (human_cost := 3.40/0.91) * 100
        qa_bars += f'''<div style="margin-bottom:10px">
<div style="display:flex;justify-content:space-between;margin-bottom:3px">
<span style="color:{col}">{name}</span>
<span style="color:#94a3b8;font-size:11px">${cost:.4f}/demo · Q={quality:.2f} · {rate}/day</span>
</div>
<div style="background:#334155;border-radius:3px;height:8px">
<div style="background:{col};width:{min(100,bar_w):.0f}%;height:8px;border-radius:3px"></div>
</div></div>'''
    
    # cost vs quality scatter
    scatter_pts = ""
    for name, cost, quality, rate, col in demo_types:
        log_cost = math.log10(max(cost, 0.001)) + 3  # normalize 0.001-10 → 0-4
        x = log_cost / 4 * 300 + 20
        y = 100 - quality * 100
        scatter_pts += f'<circle cx="{x:.1f}" cy="{y:.1f}" r="8" fill="{col}" opacity="0.8"/>'
        scatter_pts += f'<text x="{x+10:.1f}" y="{y+4:.1f}" fill="{col}" font-size="9">{name[:10]}</text>'
    
    scatter_pts += f'<line x1="20" y1="100" x2="320" y2="0" stroke="#334155" stroke-width="1" stroke-dasharray="4,2"/>'
    scatter_pts += f'<text x="170" y="115" text-anchor="middle" fill="#64748b" font-size="9">log(cost per demo)</text>'
    scatter_pts += f'<text x="5" y="55" fill="#64748b" font-size="9" transform="rotate(-90,5,55)">Quality</text>'
    
    # optimal mix analysis
    opt_mix = [
        ("Auto IK (40%)", 0.40, "#22c55e"),
        ("DAgger (25%)", 0.25, "#38bdf8"),
        ("Sim SDG (20%)", 0.20, "#f59e0b"),
        ("Human (15%)", 0.15, "#C74634"),
    ]
    mix_total_cost = sum(m[1] * next(d[1] for d in demo_types if d[0].split(" (")[0] in m[0]) for m in opt_mix)
    mix_quality = sum(m[1] * next(d[2] for d in demo_types if d[0].split(" (")[0] in m[0]) for m in opt_mix)
    
    cx, cy, r = 80, 80, 60
    donut = ""
    start = 0
    for name, frac, col in opt_mix:
        angle = frac * 360
        rad1 = math.radians(start)
        rad2 = math.radians(start + angle)
        x1 = cx + r * math.cos(rad1)
        y1 = cy + r * math.sin(rad1)
        x2 = cx + r * math.cos(rad2)
        y2 = cy + r * math.sin(rad2)
        large = 1 if angle > 180 else 0
        donut += f'<path d="M {cx} {cy} L {x1:.1f} {y1:.1f} A {r} {r} 0 {large} 1 {x2:.1f} {y2:.1f} Z" fill="{col}" opacity="0.85"/>'
        start += angle
    donut += f'<circle cx="{cx}" cy="{cy}" r="38" fill="#1e293b"/>'
    donut += f'<text x="{cx}" y="{cy-6}" text-anchor="middle" fill="white" font-size="11">${mix_total_cost:.3f}</text>'
    donut += f'<text x="{cx}" y="{cy+8}" text-anchor="middle" fill="#64748b" font-size="9">/demo avg</text>'
    
    opt_legend = "".join([f'<div style="display:flex;align-items:center;margin-bottom:4px"><span style="background:{c};width:10px;height:10px;border-radius:2px;margin-right:6px"></span><span style="color:#94a3b8;font-size:11px">{n}</span></div>' for n,_,c in opt_mix])
    
    return f"""<!DOCTYPE html><html><head><title>Cost Per Demo</title>
<style>body{{margin:0;font-family:monospace;background:#0f172a;color:#e2e8f0}}
.hdr{{background:#C74634;padding:16px 24px;display:flex;justify-content:space-between;align-items:center}}
.hdr h1{{margin:0;font-size:20px;color:#fff}}.hdr span{{color:#fca5a5;font-size:13px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;padding:20px}}
.card{{background:#1e293b;border-radius:8px;padding:16px}}
.card h3{{margin:0 0 12px;color:#38bdf8;font-size:14px;text-transform:uppercase;letter-spacing:1px}}
.stat{{font-size:36px;font-weight:bold;color:#f1f5f9}}.sub{{color:#64748b;font-size:12px;margin-top:4px}}</style></head>
<body>
<div class="hdr"><h1>Cost Per Demo</h1><span>port {PORT} · 5 demo types</span></div>
<div class="grid">
<div class="card"><h3>Cheapest</h3><div class="stat">$0.0017</div><div class="sub">Auto IK · 312/day throughput</div></div>
<div class="card"><h3>Highest Quality</h3><div class="stat">Q=0.91</div><div class="sub">Human teleop · $3.40/demo</div></div>
<div class="card" style="grid-column:span 2"><h3>Demo Type Comparison (cost · quality · throughput)</h3>{qa_bars}</div>
<div class="card"><h3>Cost vs Quality Scatter</h3>
<svg width="100%" viewBox="0 0 340 120">{scatter_pts}</svg></div>
<div class="card"><h3>Optimal Mix (SR=0.78 target)</h3>
<div style="display:flex;gap:12px;align-items:center">
<svg width="160" height="160" viewBox="0 0 160 160">{donut}</svg>
<div>{opt_legend}
<div style="margin-top:8px;color:#22c55e;font-size:12px">Blended quality: {mix_quality:.2f}</div>
</div></div></div>
</div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Cost Per Demo")
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
