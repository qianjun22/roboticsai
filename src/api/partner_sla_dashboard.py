"""Partner SLA Dashboard — FastAPI port 8423"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8423

def build_html():
    partners = ["PI_Robotics","Apptronik","1X_Tech","Machina_Labs","Wandelbots"]
    sla_dims = ["uptime_%","latency_p99","SR_threshold","support_MTTR"]
    targets = [99.5, 267, 0.65, 4.0]

    # SLA compliance matrix
    compliance = [
        [100.0, 241, 0.71, 1.2],  # PI: all green
        [99.7, 258, 0.68, 2.1],   # Apptronik: good
        [98.3, 274, 0.61, 6.2],   # 1X: latency borderline, MTTR yellow
        [None, None, None, None], # Machina: N/A
        [99.1, 263, 0.64, 3.8],   # Wandelbots: SR borderline
    ]

    cw10, rh10 = 80, 28
    svg_sla = f'<svg width="{len(sla_dims)*cw10+130}" height="{len(partners)*rh10+60}" style="background:#0f172a">'
    for di, dim in enumerate(sla_dims):
        svg_sla += f'<text x="{130+di*cw10+40}" y="18" fill="#38bdf8" font-size="8" text-anchor="middle">{dim}</text>'
        svg_sla += f'<text x="{130+di*cw10+40}" y="30" fill="#94a3b8" font-size="7" text-anchor="middle">tgt:{targets[di]}</text>'
    for pi, partner in enumerate(partners):
        svg_sla += f'<text x="125" y="{40+pi*rh10+16}" fill="#94a3b8" font-size="9" text-anchor="end">{partner[:10]}</text>'
        for di, (val, tgt) in enumerate(zip(compliance[pi], targets)):
            if val is None:
                col = "#475569"; label = "N/A"
            elif di == 0:  # uptime: higher is better
                col = "#22c55e" if val >= tgt else "#f59e0b" if val >= tgt-0.5 else "#C74634"
                label = f"{val:.1f}%"
            elif di == 1:  # latency: lower is better
                col = "#22c55e" if val <= tgt*0.95 else "#f59e0b" if val <= tgt else "#C74634"
                label = f"{val:.0f}ms"
            elif di == 2:  # SR: higher is better
                col = "#22c55e" if val >= tgt else "#f59e0b" if val >= tgt*0.95 else "#C74634"
                label = f"{val:.2f}"
            else:  # MTTR: lower is better
                col = "#22c55e" if val <= tgt*0.8 else "#f59e0b" if val <= tgt else "#C74634"
                label = f"{val:.1f}h"
            svg_sla += f'<rect x="{130+di*cw10+2}" y="{34+pi*rh10+2}" width="{cw10-4}" height="{rh10-4}" fill="{col}" rx="3" opacity="0.75"/>'
            svg_sla += f'<text x="{130+di*cw10+40}" y="{34+pi*rh10+16}" fill="white" font-size="9" text-anchor="middle">{label}</text>'
    svg_sla += '</svg>'

    # 30-day SLA trend sparklines
    svg_trend = '<svg width="420" height="200" style="background:#0f172a">'
    p_colors = ["#22c55e","#38bdf8","#f59e0b","#475569","#a78bfa"]
    for pi, (partner, pcol) in enumerate(zip(partners, p_colors)):
        y_base = 20+pi*36
        svg_trend += f'<text x="90" y="{y_base+20}" fill="#94a3b8" font-size="9" text-anchor="end">{partner[:10]}</text>'
        if compliance[pi][0] is None:
            svg_trend += f'<text x="200" y="{y_base+20}" fill="#475569" font-size="9">Pilot onboarding — SLA not active yet</text>'
            continue
        # Uptime sparkline (30 days)
        pts_sp = []
        base_up = compliance[pi][0]
        for d in range(30):
            up = base_up + random.gauss(0, 0.15)
            x = 95+d*10; y = y_base+30-max(0,(up-98.0)/2.0*25)
            pts_sp.append((x, y))
        for j in range(len(pts_sp)-1):
            x1,y1=pts_sp[j]; x2,y2=pts_sp[j+1]
            col_sp = "#22c55e" if base_up >= 99.5 else "#f59e0b" if base_up >= 98.5 else "#C74634"
            svg_trend += f'<line x1="{x1:.0f}" y1="{y1:.0f}" x2="{x2:.0f}" y2="{y2:.0f}" stroke="{col_sp}" stroke-width="1.5"/>'
        svg_trend += f'<text x="400" y="{y_base+20}" fill="#94a3b8" font-size="8">{base_up:.1f}%</text>'
    svg_trend += '<text x="245" y="195" fill="#94a3b8" font-size="9" text-anchor="middle">30-Day Uptime Trend</text>'
    svg_trend += '</svg>'

    return f"""<!DOCTYPE html><html><head><title>Partner SLA Dashboard — Port {PORT}</title>
<style>body{{background:#0f172a;color:#e2e8f0;font-family:monospace;margin:0;padding:20px}}
h1{{color:#C74634;font-size:18px}}h2{{color:#38bdf8;font-size:14px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:20px}}
.card{{background:#1e293b;padding:16px;border-radius:8px}}
.stat{{font-size:24px;color:#C74634;font-weight:bold}}
.label{{color:#94a3b8;font-size:12px}}</style></head>
<body><h1>Partner SLA Dashboard</h1>
<p style="color:#94a3b8">Port {PORT} | 5-partner x 4-SLA compliance matrix + 30-day trends</p>
<div class="grid">
<div class="card"><h2>SLA Compliance Matrix</h2>{svg_sla}
<div style="margin-top:8px;color:#f59e0b;font-size:11px">1X_Tech MTTR 6.2h &gt; 4h target — escalate CSM</div></div>
<div class="card"><h2>30-Day Uptime Trend</h2>{svg_trend}
<div style="margin-top:8px">
<div class="stat">100%</div><div class="label">PI Robotics — zero SLA breaches all-time</div>
<div style="margin-top:8px;color:#94a3b8;font-size:11px">PI: all green / Apt: all green / 1X: MTTR breach<br>Machina: SLA not yet active (DPA pending)<br>Wandelbots: SR 0.64 borderline (target 0.65)<br>Auto-alert at 80% of SLA budget consumed</div>
</div></div></div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Partner SLA Dashboard")
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
