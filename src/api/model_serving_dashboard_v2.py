"""Model Serving Dashboard v2 — FastAPI port 8379"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8379

def build_html():
    random.seed(25)
    partners = ["PI Robotics", "Apptronik", "Covariant", "1X Tech", "Skild"]
    shares = [0.34, 0.22, 0.26, 0.11, 0.07]
    colors = ["#22c55e", "#38bdf8", "#f59e0b", "#C74634", "#a78bfa"]
    
    # Donut chart for partner traffic
    donut_slices = ""
    cx, cy, r_outer, r_inner = 120, 120, 90, 50
    angle = -math.pi/2
    for share, color, name in zip(shares, colors, partners):
        arc_len = 2 * math.pi * share
        x1 = cx + r_outer * math.cos(angle)
        y1 = cy + r_outer * math.sin(angle)
        x2 = cx + r_outer * math.cos(angle + arc_len)
        y2 = cy + r_outer * math.sin(angle + arc_len)
        x3 = cx + r_inner * math.cos(angle + arc_len)
        y3 = cy + r_inner * math.sin(angle + arc_len)
        x4 = cx + r_inner * math.cos(angle)
        y4 = cy + r_inner * math.sin(angle)
        large_arc = 1 if arc_len > math.pi else 0
        donut_slices += f'<path d="M {x1} {y1} A {r_outer} {r_outer} 0 {large_arc} 1 {x2} {y2} L {x3} {y3} A {r_inner} {r_inner} 0 {large_arc} 0 {x4} {y4} Z" fill="{color}" opacity="0.85"/>'
        mid_angle = angle + arc_len/2
        lx = cx + (r_outer + 15) * math.cos(mid_angle)
        ly = cy + (r_outer + 15) * math.sin(mid_angle)
        if share > 0.1:
            donut_slices += f'<text x="{lx}" y="{ly+4}" text-anchor="middle" fill="{color}" font-size="9">{int(share*100)}%</text>'
        angle += arc_len
    donut_slices += f'<text x="{cx}" y="{cy}" text-anchor="middle" fill="#e2e8f0" font-size="10">847</text>'
    donut_slices += f'<text x="{cx}" y="{cy+14}" text-anchor="middle" fill="#64748b" font-size="8">req/hr</text>'

    # 7-day p50/p95/p99 trend
    days = list(range(1, 8))
    random.seed(26)
    p50_daily = [round(226 + random.uniform(-4,4), 1) for _ in days]
    p95_daily = [round(268 + random.uniform(-6,6), 1) for _ in days]
    p99_daily = [round(291 + random.uniform(-8,8), 1) for _ in days]
    
    def pts(vals, y_scale=0.4, y_base=200):
        return " ".join(f"{30+i*78},{y_base-v*y_scale}" for i,v in enumerate(vals))

    pts_p50 = pts(p50_daily)
    pts_p95 = pts(p95_daily)
    pts_p99 = pts(p99_daily)
    
    # SLA bands
    sla_300 = 200 - 300*0.4
    sla_200 = 200 - 200*0.4

    # Auto-scale events
    events = [
        ("Apr 1", "Scale up: PI burst", "#22c55e"),
        ("Apr 3", "Scale down: off-peak", "#38bdf8"),
        ("Apr 5", "Scale up: Covariant eval", "#22c55e"),
    ]
    event_rows = ""
    for ts, desc, color in events:
        event_rows += f'<div style="padding:4px 0;border-bottom:1px solid #1e293b;font-size:0.8em"><span style="color:{color}">{ts}</span> — <span style="color:#94a3b8">{desc}</span></div>'

    return f"""<!DOCTYPE html><html><head><title>Model Serving Dashboard v2 — Port {PORT}</title>
<style>body{{background:#0f172a;color:#e2e8f0;font-family:monospace;margin:0;padding:20px}}
h1{{color:#C74634;font-size:1.4em}}h2{{color:#38bdf8;font-size:1em}}
.grid{{display:grid;grid-template-columns:1fr 2fr;gap:16px;margin-top:16px}}
.card{{background:#1e293b;border-radius:8px;padding:16px}}
svg{{width:100%;height:auto}}</style></head><body>
<h1>Model Serving Dashboard v2</h1>
<div style="display:flex;gap:24px;margin-bottom:16px">
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#22c55e">99.72%</div><div style="font-size:0.75em;color:#94a3b8">Success Rate</div></div>
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#22c55e">226ms</div><div style="font-size:0.75em;color:#94a3b8">p50</div></div>
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#f59e0b">267ms</div><div style="font-size:0.75em;color:#94a3b8">p99</div></div>
<div style="text-align:center"><div style="font-size:2em;font-weight:bold;color:#38bdf8">847</div><div style="font-size:0.75em;color:#94a3b8">Peak Req/hr</div></div>
</div>
<div class="grid">
<div class="card"><h2>Live Traffic (by partner)</h2>
<svg viewBox="0 0 250 250"><rect width="250" height="250" fill="#0f172a" rx="4"/>
{donut_slices}
</svg>
<div style="font-size:0.75em;margin-top:4px">
{''.join(f'<div><span style="color:{c}">■</span> {p}</div>' for p,c in zip(partners,colors))}
</div>
</div>
<div class="card"><h2>7-Day Latency Trend (p50/p95/p99)</h2>
<svg viewBox="0 0 530 220"><rect width="530" height="220" fill="#0f172a" rx="4"/>
<line x1="30" y1="10" x2="30" y2="205" stroke="#334155" stroke-width="1"/>
<line x1="30" y1="205" x2="520" y2="205" stroke="#334155" stroke-width="1"/>
<line x1="30" y1="{sla_300}" x2="520" y2="{sla_300}" stroke="#C74634" stroke-dasharray="3,3" stroke-width="1" opacity="0.6"/>
<text x="490" y="{sla_300-3}" fill="#C74634" font-size="8">SLA 300ms</text>
<line x1="30" y1="{sla_200}" x2="520" y2="{sla_200}" stroke="#22c55e" stroke-dasharray="3,3" stroke-width="1" opacity="0.4"/>
<text x="490" y="{sla_200-3}" fill="#22c55e" font-size="8">target 200ms</text>
<polyline points="{pts_p99}" fill="none" stroke="#C74634" stroke-width="1.5" opacity="0.8"/>
<polyline points="{pts_p95}" fill="none" stroke="#f59e0b" stroke-width="1.5" opacity="0.8"/>
<polyline points="{pts_p50}" fill="none" stroke="#22c55e" stroke-width="2"/>
{''.join(f'<text x="{30+i*78}" y="215" text-anchor="middle" fill="#64748b" font-size="8">Apr{i+1}</text>' for i in range(7))}
<text x="420" y="80" fill="#C74634" font-size="8">p99</text>
<text x="420" y="95" fill="#f59e0b" font-size="8">p95</text>
<text x="420" y="110" fill="#22c55e" font-size="8">p50</text>
</svg>
</div>
</div>
<div class="card" style="margin-top:16px">
<h2>Auto-Scale Events (7d)</h2>
{event_rows}
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Model Serving Dashboard v2")
    @app.get("/", response_class=HTMLResponse)
    def index(): return build_html()
    @app.get("/health")
    def health(): return {"status":"ok","port":PORT,"success_rate":0.9972,"p50_ms":226,"p99_ms":267}

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type","text/html")
        self.end_headers()
        self.wfile.write(build_html().encode())
    def log_message(self,*a): pass

if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        HTTPServer(("0.0.0.0",PORT), Handler).serve_forever()
