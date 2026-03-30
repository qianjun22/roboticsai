"""API Dependency Map — FastAPI port 8430"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8430

def build_html():
    # Service nodes with positions
    services = [
        ("inference","POST /infer",0.5,0.15,"#C74634",94),
        ("model_load","GET /model",0.5,0.35,"#f59e0b",89),
        ("tokenizer","POST /tokenize",0.25,0.35,"#38bdf8",99),
        ("vision_enc","POST /encode",0.75,0.35,"#38bdf8",97),
        ("dagger_step","POST /dagger",0.15,0.55,"#22c55e",88),
        ("eval_run","POST /eval",0.35,0.55,"#22c55e",92),
        ("checkpoint","GET /ckpt",0.5,0.7,"#a78bfa",99),
        ("billing","POST /bill",0.7,0.55,"#94a3b8",99),
        ("health","GET /health",0.85,0.15,"#22c55e",100),
        ("partner_api","POST /partner",0.15,0.15,"#f59e0b",98),
        ("data_upload","POST /data",0.35,0.15,"#38bdf8",96),
        ("sdk_gateway","GET /sdk",0.65,0.7,"#a78bfa",97),
    ]
    # Edges (caller -> callee, frequency)
    edges = [
        (0,1,100),(0,2,95),(0,3,90),(1,6,80),(4,0,70),(4,6,65),
        (5,0,60),(5,6,55),(9,0,40),(10,0,35),(7,0,20),(11,0,15),
    ]

    W, H = 420, 260
    svg_dep = f'<svg width="{W}" height="{H}" style="background:#0f172a">'
    # Draw edges
    for (src, dst, freq) in edges:
        sx, sy = services[src][2]*W*0.9+20, services[src][3]*H*0.9+10
        dx, dy = services[dst][2]*W*0.9+20, services[dst][3]*H*0.9+10
        stroke_w = max(1, freq//30)
        svg_dep += f'<line x1="{sx:.0f}" y1="{sy:.0f}" x2="{dx:.0f}" y2="{dy:.0f}" stroke="#475569" stroke-width="{stroke_w}" opacity="0.6"/>'
    # Draw nodes
    for name, endpoint, nx, ny, col, uptime in services:
        x = nx*W*0.9+20; y = ny*H*0.9+10
        r = 16
        svg_dep += f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{r}" fill="{col}" opacity="0.85"/>'
        svg_dep += f'<text x="{x:.0f}" y="{y+4:.0f}" fill="white" font-size="7" text-anchor="middle">{name[:6]}</text>'
        if uptime < 99:
            svg_dep += f'<circle cx="{x+14:.0f}" cy="{y-14:.0f}" r="5" fill="#C74634"/>'
    # Critical path annotation
    svg_dep += f'<text x="{W//2}" y="{H-5}" fill="#94a3b8" font-size="8" text-anchor="middle">/inference in 94% of call chains | critical path: 5 services 89ms</text>'
    svg_dep += '</svg>'

    # SPOF detection list
    spof_services = [
        ("/inference","94% dependency","#C74634","HIGH"),
        ("/model_load","89% dependency","#f59e0b","MED"),
        ("/checkpoint","80% dependency","#f59e0b","MED"),
        ("/tokenize","95% direct","#38bdf8","LOW"),
    ]
    svg_spof = '<svg width="360" height="180" style="background:#0f172a">'
    for si, (svc, dep, col, risk) in enumerate(spof_services):
        y = 20+si*38
        svg_spof += f'<rect x="10" y="{y}" width="340" height="28" fill="#1e293b" rx="4"/>'
        svg_spof += f'<rect x="10" y="{y}" width="4" height="28" fill="{col}" rx="2"/>'
        svg_spof += f'<text x="22" y="{y+17}" fill="white" font-size="10">{svc}</text>'
        svg_spof += f'<text x="140" y="{y+17}" fill="#94a3b8" font-size="8">{dep}</text>'
        risk_col = {"HIGH":"#C74634","MED":"#f59e0b","LOW":"#22c55e"}[risk]
        svg_spof += f'<rect x="320" y="{y+4}" width="28" height="20" fill="{risk_col}" rx="3" opacity="0.8"/>'
        svg_spof += f'<text x="334" y="{y+17}" fill="white" font-size="7" text-anchor="middle">{risk}</text>'
    svg_spof += '</svg>'

    return f"""<!DOCTYPE html><html><head><title>API Dependency Map — Port {PORT}</title>
<style>body{{background:#0f172a;color:#e2e8f0;font-family:monospace;margin:0;padding:20px}}
h1{{color:#C74634;font-size:18px}}h2{{color:#38bdf8;font-size:14px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:20px}}
.card{{background:#1e293b;padding:16px;border-radius:8px}}
.stat{{font-size:24px;color:#C74634;font-weight:bold}}
.label{{color:#94a3b8;font-size:12px}}</style></head>
<body><h1>API Dependency Map</h1>
<p style="color:#94a3b8">Port {PORT} | 20-endpoint service graph + critical path analysis</p>
<div class="grid">
<div class="card"><h2>Service Dependency Graph</h2>{svg_dep}</div>
<div class="card"><h2>Single Point of Failure Risk</h2>{svg_spof}
<div style="margin-top:8px">
<div class="stat">89ms</div><div class="label">Critical path: partner->inference->model->ckpt->encode->decode</div>
<div style="margin-top:8px;color:#94a3b8;font-size:11px">/inference is SPOF: HIGH risk — add circuit breaker<br>Fallback policy: cached last-checkpoint for 60s<br>Health checks: 30s interval per dependency<br>Chaos test: simulate /model_load failure -> verify fallback</div>
</div></div></div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="API Dependency Map")
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
