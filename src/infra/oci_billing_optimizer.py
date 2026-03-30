"""OCI Billing Optimizer — FastAPI port 8421"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8421

def build_html():
    # 4-strategy savings waterfall
    strategies = ["PAYG_baseline","Committed_1yr","Spot_mix_30%","Reserved_cores","Preemptible_eval"]
    monthly_costs = [500, 418, 374, 358, 312]
    savings = [0, 82, 44, 16, 46]
    colors = ["#475569","#22c55e","#38bdf8","#f59e0b","#a78bfa"]

    svg_wf = '<svg width="380" height="200" style="background:#0f172a">'
    svg_wf += '<line x1="50" y1="10" x2="50" y2="170" stroke="#475569" stroke-width="1"/>'
    svg_wf += '<line x1="50" y1="170" x2="360" y2="170" stroke="#475569" stroke-width="1"/>'
    for i in range(6):
        yv = i*100; y = 170-yv*150/500
        svg_wf += f'<text x="45" y="{y+4}" fill="#94a3b8" font-size="7" text-anchor="end">${yv}</text>'
    bw7 = 52
    for si, (strat, cost, col) in enumerate(zip(strategies, monthly_costs, colors)):
        x = 55+si*58; h = cost/500*150; y = 170-h
        svg_wf += f'<rect x="{x}" y="{y:.0f}" width="{bw7}" height="{h:.0f}" fill="{col}" opacity="0.85"/>'
        svg_wf += f'<text x="{x+bw7//2}" y="{y-3:.0f}" fill="{col}" font-size="7" text-anchor="middle">${cost}</text>'
        label = strat.replace("_"," ")[:8]
        svg_wf += f'<text x="{x+bw7//2}" y="183" fill="#94a3b8" font-size="7" text-anchor="middle">{label}</text>'
    svg_wf += '</svg>'

    # 12-month TCO comparison
    months_tco = list(range(1,13))
    payg_tco = [m*500 for m in months_tco]
    opt_tco  = [m*358 + 200 for m in months_tco]  # +200 setup cost

    svg_tco = '<svg width="360" height="200" style="background:#0f172a">'
    svg_tco += '<line x1="40" y1="10" x2="40" y2="170" stroke="#475569" stroke-width="1"/>'
    svg_tco += '<line x1="40" y1="170" x2="340" y2="170" stroke="#475569" stroke-width="1"/>'
    for i in range(7):
        yv = i*1000; y = 170-yv*150/6000
        svg_tco += f'<text x="35" y="{y+4}" fill="#94a3b8" font-size="7" text-anchor="end">${yv//1000}k</text>'
    for mi, m in enumerate(months_tco):
        x = 40+(m-1)/11*290
        if m % 3 == 1:
            svg_tco += f'<text x="{x}" y="182" fill="#94a3b8" font-size="7" text-anchor="middle">M{m}</text>'
    # Breakeven month ~6
    be_x = 40+5/11*290
    svg_tco += f'<line x1="{be_x:.0f}" y1="10" x2="{be_x:.0f}" y2="170" stroke="#22c55e" stroke-width="1" stroke-dasharray="3,2"/>'
    svg_tco += f'<text x="{be_x+3:.0f}" y="25" fill="#22c55e" font-size="7">breakeven M6</text>'
    pts_payg = [(40+(m-1)/11*290, 170-v*150/6000) for m, v in zip(months_tco, payg_tco)]
    pts_opt  = [(40+(m-1)/11*290, 170-v*150/6000) for m, v in zip(months_tco, opt_tco)]
    for j in range(len(pts_payg)-1):
        x1,y1=pts_payg[j]; x2,y2=pts_payg[j+1]
        svg_tco += f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#C74634" stroke-width="1.5"/>'
    for j in range(len(pts_opt)-1):
        x1,y1=pts_opt[j]; x2,y2=pts_opt[j+1]
        svg_tco += f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#22c55e" stroke-width="1.5"/>'
    svg_tco += '<text x="330" y="{:.0f}" fill="#C74634" font-size="7">PAYG</text>'.format(170-payg_tco[-1]*150/6000)
    svg_tco += '<text x="330" y="{:.0f}" fill="#22c55e" font-size="7">Opt</text>'.format(170-opt_tco[-1]*150/6000)
    svg_tco += '</svg>'

    return f"""<!DOCTYPE html><html><head><title>OCI Billing Optimizer — Port {PORT}</title>
<style>body{{background:#0f172a;color:#e2e8f0;font-family:monospace;margin:0;padding:20px}}
h1{{color:#C74634;font-size:18px}}h2{{color:#38bdf8;font-size:14px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:20px}}
.card{{background:#1e293b;padding:16px;border-radius:8px}}
.stat{{font-size:24px;color:#C74634;font-weight:bold}}
.label{{color:#94a3b8;font-size:12px}}</style></head>
<body><h1>OCI Billing Optimizer</h1>
<p style="color:#94a3b8">Port {PORT} | 4-strategy cost reduction + 12-month TCO comparison</p>
<div class="grid">
<div class="card"><h2>Monthly Cost by Strategy</h2>{svg_wf}
<div class="stat">$142/mo</div><div class="label">Savings from committed discount (28.4%)</div></div>
<div class="card"><h2>12-Month TCO: PAYG vs Optimized</h2>{svg_tco}
<div style="margin-top:8px">
<div class="stat">Month 6</div><div class="label">Committed plan breakeven vs PAYG</div>
<div style="margin-top:8px;color:#94a3b8;font-size:11px">12mo savings: $1,704 (PAYG $6k vs Opt $4.3k)<br>Spot preemption risk: eval jobs OK, DAgger too risky<br>Preemptible eval: $46/mo additional savings<br>OCI reserved cores: 16/node at 28% discount</div>
</div></div></div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="OCI Billing Optimizer")
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
