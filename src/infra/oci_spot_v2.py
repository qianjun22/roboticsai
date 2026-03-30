"""OCI Spot v2 — FastAPI port 8509"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8509

def build_html():
    gpu_types = [
        ("A100_80GB Ashburn", 90, 0.12, 8.40, 3.02, "#22c55e"),
        ("A100_40GB Phoenix", 85, 0.18, 5.20, 1.87, "#38bdf8"),
        ("A100_40GB Frankfurt", 78, 0.24, 5.20, 1.87, "#f59e0b"),
        ("H100_80GB Ashburn", 62, 0.31, 16.80, 5.21, "#a78bfa"),
    ]
    
    rows = ""
    for name, avail, preempt_risk, on_demand, spot, col in gpu_types:
        savings_pct = (on_demand - spot) / on_demand * 100
        rows += f'<tr><td style="color:{col}">{name}</td><td style="color:{col}">{avail}%</td><td>${on_demand:.2f}</td><td style="color:#22c55e">${spot:.2f}</td><td style="color:#22c55e">{savings_pct:.0f}%</td></tr>'
    
    # availability heatmap (7 days x 4 GPU types)
    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    heatmap = ""
    for d_idx, day in enumerate(days):
        for gpu_idx, (name, base_avail, _, _, _, col) in enumerate(gpu_types):
            avail = base_avail + random.uniform(-15, 8)
            avail = max(30, min(100, avail))
            x = d_idx * 68 + 10
            y = gpu_idx * 20 + 5
            green = max(0, int((avail - 30) / 70 * 255))
            opacity = avail / 100
            heatmap += f'<rect x="{x}" y="{y}" width="62" height="16" fill="{col}" opacity="{opacity:.2f}" rx="2"/>'
            heatmap += f'<text x="{x+31}" y="{y+11}" text-anchor="middle" fill="white" font-size="8">{avail:.0f}%</text>'
        heatmap += f'<text x="{d_idx*68+41}" y="90" text-anchor="middle" fill="#64748b" font-size="9">{day}</text>'
    
    for gpu_idx, (name, _, _, _, _, col) in enumerate(gpu_types):
        heatmap += f'<text x="490" y="{gpu_idx*20+15}" fill="{col}" font-size="8">{name[:8]}</text>'
    
    # checkpointing frequency optimizer
    ckpt_intervals = [5, 10, 15, 20, 30, 60]
    overhead_pct = [9.2, 4.8, 3.2, 2.4, 1.6, 0.8]
    recovery_pct = [99.8, 99.6, 99.1, 98.4, 97.1, 93.2]
    
    ckpt_pts = []
    rec_pts = []
    for i, (interval, overhead, recovery) in enumerate(zip(ckpt_intervals, overhead_pct, recovery_pct)):
        x = i * 88 + 10
        y_ov = 80 - overhead / 10 * 80
        y_rec = 80 - (recovery - 90) / 10 * 80
        ckpt_pts.append(f"{x:.0f},{y_ov:.1f}")
        rec_pts.append(f"{x:.0f},{y_rec:.1f}")
    
    ckpt_svg = f'<polyline points="{" ".join(ckpt_pts)}" fill="none" stroke="#ef4444" stroke-width="2"/>'
    rec_svg = f'<polyline points="{" ".join(rec_pts)}" fill="none" stroke="#22c55e" stroke-width="2"/>'
    # optimal at 15 min
    opt_x = 2 * 88 + 10
    opt_line = f'<line x1="{opt_x}" y1="0" x2="{opt_x}" y2="80" stroke="#C74634" stroke-width="1" stroke-dasharray="4,2"/>'
    ckpt_labels = "".join([f'<text x="{i*88+10:.0f}" y="92" text-anchor="middle" fill="#64748b" font-size="8">{i}min</text>' for i, interval in enumerate(ckpt_intervals)])
    
    return f"""<!DOCTYPE html><html><head><title>OCI Spot v2</title>
<style>body{{margin:0;font-family:monospace;background:#0f172a;color:#e2e8f0}}
.hdr{{background:#C74634;padding:16px 24px;display:flex;justify-content:space-between;align-items:center}}
.hdr h1{{margin:0;font-size:20px;color:#fff}}.hdr span{{color:#fca5a5;font-size:13px}}
.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;padding:20px}}
.card{{background:#1e293b;border-radius:8px;padding:16px}}
.card h3{{margin:0 0 12px;color:#38bdf8;font-size:14px;text-transform:uppercase;letter-spacing:1px}}
.stat{{font-size:36px;font-weight:bold;color:#f1f5f9}}.sub{{color:#64748b;font-size:12px;margin-top:4px}}
table{{width:100%;border-collapse:collapse;font-size:12px}}
th{{text-align:left;color:#64748b;padding:6px 0;border-bottom:1px solid #334155}}
td{{padding:6px 0;border-bottom:1px solid #1e293b}}</style></head>
<body>
<div class="hdr"><h1>OCI Spot v2</h1><span>port {PORT} · 4 GPU types</span></div>
<div class="grid">
<div class="card"><h3>Best Availability</h3><div class="stat">90%</div><div class="sub">A100_80GB Ashburn · 0 failures</div></div>
<div class="card"><h3>Daily Savings</h3><div class="stat">$51</div><div class="sub">vs $147/day on-demand · 65%</div></div>
<div class="card"><h3>Recovery Rate</h3><div class="stat">99.1%</div><div class="sub">15-min checkpoint interval</div></div>
<div class="card" style="grid-column:span 3"><h3>GPU Availability + Pricing</h3>
<table><tr><th>GPU</th><th>Availability</th><th>On-Demand</th><th>Spot</th><th>Savings</th></tr>{rows}</table></div>
<div class="card" style="grid-column:span 2"><h3>7-Day Spot Availability Heatmap</h3>
<svg width="100%" viewBox="0 0 490 100">{heatmap}</svg></div>
<div class="card"><h3>Checkpoint Frequency Optimizer</h3>
<div style="font-size:10px;color:#64748b;margin-bottom:6px"><span style="color:#ef4444">—</span> overhead% <span style="color:#22c55e;margin-left:6px">—</span> recovery% <span style="color:#C74634;margin-left:6px">| optimal=15min</span></div>
<svg width="100%" viewBox="0 0 450 95">{ckpt_svg}{rec_svg}{opt_line}{ckpt_labels}</svg></div>
</div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="OCI Spot v2")
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
