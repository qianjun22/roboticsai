"""Design Partner Pipeline — FastAPI port 8402"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8402

def build_html():
    stages = ["NVIDIA_referral","Intro_call","NDA_signed","Pilot_active","Paying"]
    counts = [12, 8, 5, 3, 1]
    colors = ["#475569","#64748b","#f59e0b","#22c55e","#C74634"]
    # Funnel SVG
    svg_f = '<svg width="320" height="220" style="background:#0f172a">'
    max_w = 280
    for i, (s, c, col) in enumerate(zip(stages, counts, colors)):
        w = int(max_w * c / counts[0]); x = (max_w - w) // 2 + 20; y = 15 + i*38
        svg_f += f'<rect x="{x}" y="{y}" width="{w}" height="28" fill="{col}" rx="4" opacity="0.85"/>'
        svg_f += f'<text x="160" y="{y+18}" fill="white" font-size="10" text-anchor="middle">{s}: {c}</text>'
    svg_f += '</svg>'

    # CRM table SVG
    prospects = [
        ("Machina_Labs","Franka","metal_forming","pilot_active","$1,247"),
        ("Wandelbots","UR5e","assembly","NDA_signed","$890"),
        ("1X_Tech","custom","household","pilot_active","$847"),
        ("Figure_AI","Figure_02","loco_manip","intro_call","$2,100"),
        ("Matic","Spot","cleaning","referral","$640"),
    ]
    svg_c = '<svg width="440" height="180" style="background:#0f172a">'
    headers = ["Company","Robot","Use Case","Status","ARR Pot"]
    widths = [90,60,90,90,70]
    x = 10
    for h, w in zip(headers, widths):
        svg_c += f'<text x="{x+w//2}" y="18" fill="#38bdf8" font-size="9" text-anchor="middle" font-weight="bold">{h}</text>'
        x += w
    for pi, (comp, robot, use, status, arr) in enumerate(prospects):
        y = 35+pi*28; x = 10
        col = "#22c55e" if "pilot" in status else "#f59e0b" if "NDA" in status else "#94a3b8"
        for val, w in zip([comp, robot, use, status, arr], widths):
            svg_c += f'<text x="{x+w//2}" y="{y+14}" fill="{col if val==status else "#e2e8f0"}" font-size="9" text-anchor="middle">{val}</text>'
            x += w
    svg_c += '</svg>'

    return f"""<!DOCTYPE html><html><head><title>Design Partner Pipeline — Port {PORT}</title>
<style>body{{background:#0f172a;color:#e2e8f0;font-family:monospace;margin:0;padding:20px}}
h1{{color:#C74634;font-size:18px}}h2{{color:#38bdf8;font-size:14px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:20px}}
.card{{background:#1e293b;padding:16px;border-radius:8px}}
.stat{{font-size:24px;color:#C74634;font-weight:bold}}
.label{{color:#94a3b8;font-size:12px}}</style></head>
<body><h1>Design Partner Pipeline</h1>
<p style="color:#94a3b8">Port {PORT} | NVIDIA-referred robotics startup pipeline</p>
<div class="grid">
<div class="card"><h2>Pipeline Funnel</h2>{svg_f}
<div class="stat">$6,327</div><div class="label">Active pilot MRR (3 partners)</div></div>
<div class="card"><h2>Prospect CRM</h2>{svg_c}
<div style="margin-top:8px;color:#94a3b8;font-size:11px">5 NVIDIA referrals pending intro<br>Machina DPA BLOCKED → critical path<br>Figure_AI highest ARR potential $2,100<br>Target: 5 paying partners by Sep 2026</div></div></div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Design Partner Pipeline")
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
