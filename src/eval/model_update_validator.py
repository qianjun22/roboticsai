"""Model Update Validator — FastAPI port 8428"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8428

def build_html():
    gates = [
        ("SR_delta","SR ≥ prev - 2pp","0.78 vs 0.71","PASS","#22c55e"),
        ("latency_p99","p99 ≤ 280ms","241ms","PASS","#22c55e"),
        ("regression_check","No control chart breach","0 breaches","PASS","#22c55e"),
        ("safety_eval","0 hard stops in 20 eps","0/20","PASS","#22c55e"),
        ("VRAM_budget","VRAM ≤ 75GB","71.2GB","PASS","#22c55e"),
        ("throughput","≥ 800 req/hr @ load","847 req/hr","PASS","#22c55e"),
        ("api_compat","All endpoints respond 200","20/20","PASS","#22c55e"),
        ("load_test","p99 ≤ 300ms at 2× load","268ms","PASS","#22c55e"),
    ]

    svg_gates = f'<svg width="420" height="{len(gates)*38+30}" style="background:#0f172a">'
    for gi, (name, criterion, result, status, col) in enumerate(gates):
        y = 15+gi*38
        svg_gates += f'<rect x="10" y="{y}" width="400" height="28" fill="#1e293b" rx="4"/>'
        svg_gates += f'<rect x="10" y="{y}" width="4" height="28" fill="{col}" rx="2"/>'
        svg_gates += f'<text x="22" y="{y+17}" fill="white" font-size="10" font-weight="bold">{name}</text>'
        svg_gates += f'<text x="155" y="{y+17}" fill="#94a3b8" font-size="8">{criterion}</text>'
        svg_gates += f'<text x="295" y="{y+17}" fill="{col}" font-size="9" font-weight="bold">{result}</text>'
        svg_gates += f'<rect x="370" y="{y+4}" width="36" height="20" fill="{col}" rx="3" opacity="0.8"/>'
        svg_gates += f'<text x="388" y="{y+17}" fill="white" font-size="8" text-anchor="middle">{status}</text>'
    svg_gates += '</svg>'

    # Decision summary
    all_pass = all(g[3]=="PASS" for g in gates)
    decision = "PROMOTE" if all_pass else "BLOCK"
    dec_color = "#22c55e" if all_pass else "#C74634"

    return f"""<!DOCTYPE html><html><head><title>Model Update Validator — Port {PORT}</title>
<style>body{{background:#0f172a;color:#e2e8f0;font-family:monospace;margin:0;padding:20px}}
h1{{color:#C74634;font-size:18px}}h2{{color:#38bdf8;font-size:14px}}
.card{{background:#1e293b;padding:16px;border-radius:8px;margin-bottom:16px}}
.stat{{font-size:36px;font-weight:bold}}
.label{{color:#94a3b8;font-size:12px}}</style></head>
<body><h1>Model Update Validator</h1>
<p style="color:#94a3b8">Port {PORT} | 8-gate automated validation for groot_v2 → production</p>
<div class="card"><h2>Validation Gates</h2>{svg_gates}</div>
<div class="card" style="text-align:center">
<div class="stat" style="color:{dec_color}">{decision}</div>
<div class="label">Automated gate decision ({sum(1 for g in gates if g[3]=="PASS")}/{len(gates)} gates passed)</div>
<div style="margin-top:16px;color:#94a3b8;font-size:11px;text-align:left">groot_v2 promoted: Apr 5 scheduled (blue-green deploy)<br>Traffic cutover: 10% → 50% → 100% over 6 hours<br>Rollback trigger: SR drop >3pp or latency >300ms<br>Shadow mode: 7 days before PRODUCTION designation</div>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Model Update Validator")
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
