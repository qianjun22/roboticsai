"""Fleet Incident Logger — FastAPI port 8505"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8505

def build_html():
    incidents = [
        (3, "Jan", "P1", "OOM A100-GPU4 (DAgger launch)", 2.3, "#ef4444"),
        (12, "Jan", "P2", "Network partition Ashburn\u2194Phoenix", 0.8, "#f59e0b"),
        (28, "Jan", "P3", "Checkpoint storage 95% full", 0.1, "#38bdf8"),
        (5, "Feb", "P2", "Spot preemption during eval run", 0.3, "#f59e0b"),
        (15, "Feb", "P1", "Inference service OOM (batch size)", 1.8, "#ef4444"),
        (22, "Feb", "P3", "Log rotation failure Frankfurt", 0.05, "#38bdf8"),
        (8, "Mar", "P1", "GPU4 ECC errors (correctable)", 2.1, "#ef4444"),
        (18, "Mar", "P2", "Spot preemption (no checkpoint)", 0.6, "#f59e0b"),
        (25, "Mar", "P3", "DNS resolution latency spike", 0.08, "#38bdf8"),
    ]
    
    # timeline SVG (90 days)
    timeline_svg = ""
    for day_offset, month, sev, desc, mttr, col in incidents:
        months = {"Jan": 0, "Feb": 30, "Mar": 60}
        abs_day = months[month] + day_offset
        x = abs_day / 90 * 520 + 10
        r = {"P1": 10, "P2": 7, "P3": 5}[sev]
        y = {"P1": 30, "P2": 55, "P3": 75}[sev]
        timeline_svg += f'<circle cx="{x:.1f}" cy="{y}" r="{r}" fill="{col}" opacity="0.9"/>'
        # MTTR bar
        bar_h = mttr / 2.5 * 20
        timeline_svg += f'<rect x="{x-3:.1f}" y="{y}" width="6" height="{bar_h:.0f}" fill="{col}" opacity="0.4"/>'
    
    # axis labels
    for month, x_frac in [("Jan", 0.17), ("Feb", 0.5), ("Mar", 0.83)]:
        timeline_svg += f'<text x="{x_frac*540:.0f}" y="95" text-anchor="middle" fill="#64748b" font-size="9">{month} 2026</text>'
    timeline_svg += f'<text x="10" y="33" fill="#ef4444" font-size="8">P1</text>'
    timeline_svg += f'<text x="10" y="58" fill="#f59e0b" font-size="8">P2</text>'
    timeline_svg += f'<text x="10" y="78" fill="#38bdf8" font-size="8">P3</text>'
    
    # category donut
    categories = [
        ("OOM", 35, "#ef4444"),
        ("Network", 28, "#f59e0b"),
        ("Preemption", 22, "#38bdf8"),
        ("Disk/Log", 15, "#64748b"),
    ]
    cx, cy, r = 80, 80, 55
    donut = ""
    start = 0
    for name, pct, col in categories:
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
    donut += f'<text x="{cx}" y="{cy-4}" text-anchor="middle" fill="white" font-size="11">9 inc</text>'
    donut += f'<text x="{cx}" y="{cy+10}" text-anchor="middle" fill="#64748b" font-size="9">90 days</text>'
    
    cat_legend = "".join([f'<div style="display:flex;align-items:center;margin-bottom:4px"><span style="background:{c};width:10px;height:10px;border-radius:2px;margin-right:6px"></span><span style="color:#94a3b8;font-size:11px">{n} {p}%</span></div>' for n,p,c in categories])
    
    return f"""<!DOCTYPE html><html><head><title>Fleet Incident Logger</title>
<style>body{{margin:0;font-family:monospace;background:#0f172a;color:#e2e8f0}}
.hdr{{background:#C74634;padding:16px 24px;display:flex;justify-content:space-between;align-items:center}}
.hdr h1{{margin:0;font-size:20px;color:#fff}}.hdr span{{color:#fca5a5;font-size:13px}}
.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;padding:20px}}
.card{{background:#1e293b;border-radius:8px;padding:16px}}
.card h3{{margin:0 0 12px;color:#38bdf8;font-size:14px;text-transform:uppercase;letter-spacing:1px}}
.stat{{font-size:36px;font-weight:bold;color:#f1f5f9}}.sub{{color:#64748b;font-size:12px;margin-top:4px}}</style></head>
<body>
<div class="hdr"><h1>Fleet Incident Logger</h1><span>port {PORT} \u00b7 90-day view</span></div>
<div class="grid">
<div class="card"><h3>MTTR Trend</h3><div class="stat">18min</div><div class="sub">from 2.3h Jan \u2192 18min Mar (8\u00d7)</div></div>
<div class="card"><h3>P1 Incidents</h3><div class="stat">3</div><div class="sub">Jan-Mar \u00b7 all resolved \u00b7 0 in last 30d</div></div>
<div class="card"><h3>Uptime</h3><div class="stat">99.94%</div><div class="sub">Ashburn SLA \u2713 \u00b7 no customer P1</div></div>
<div class="card" style="grid-column:span 3"><h3>Incident Timeline (90 days \u00b7 bubble=severity, bar=MTTR)</h3>
<svg width="100%" viewBox="0 0 540 100">{timeline_svg}</svg></div>
<div class="card"><h3>Incident by Category</h3>
<div style="display:flex;gap:12px;align-items:center">
<svg width="160" height="160" viewBox="0 0 160 160">{donut}</svg>
<div>{cat_legend}</div></div></div>
<div class="card" style="grid-column:span 2"><h3>Key Improvements</h3>
<div style="font-size:13px;line-height:1.8;color:#94a3b8">
<div style="color:#22c55e">\u2713</div> OOM: batch_size guard + VRAM monitor alert (prevents P1)
<div style="color:#22c55e">\u2713</div> Spot preemption: 15-min checkpoint cadence (100% recovery)
<div style="color:#22c55e">\u2713</div> Storage: auto-prune lifecycle policy (alert at 80%)
<div style="color:#f59e0b">\u23f3</div> Network: cross-region latency SLA breaker (in progress)
</div></div>
</div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Fleet Incident Logger")
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
