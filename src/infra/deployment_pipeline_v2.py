"""Deployment Pipeline v2 — FastAPI port 8473"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8473

def build_html():
    # 9-stage CD pipeline
    stages = [
        ("Build", "PASS", "#22c55e", 0.8),
        ("Unit Test", "PASS", "#22c55e", 2.1),
        ("Eval Gate", "PASS", "#22c55e", 18.4),
        ("Canary 10%", "PASS", "#22c55e", 45.0),
        ("Monitor 1h", "PASS", "#22c55e", 60.0),
        ("Canary 50%", "PASS", "#22c55e", 45.0),
        ("Load Test", "PASS", "#22c55e", 12.0),
        ("Promote", "PASS", "#22c55e", 3.2),
        ("Verify", "PASS", "#22c55e", 5.1),
    ]
    stage_svg = ""
    x = 15
    for i, (name, status, color, dur) in enumerate(stages):
        w = int(dur / 200 * 550)
        w = max(w, 30)
        stage_svg += f'<rect x="{x}" y="15" width="{w}" height="36" fill="{color}" rx="4" opacity="0.8"/>'
        stage_svg += f'<text x="{x + w//2}" y="28" fill="#0f172a" font-size="8" text-anchor="middle" font-weight="bold">{name}</text>'
        stage_svg += f'<text x="{x + w//2}" y="41" fill="#0f172a" font-size="8" text-anchor="middle">{dur}min</text>'
        x += w + 4
    stage_svg += f'<text x="{x-4}" y="38" fill="#22c55e" font-size="9" font-weight="bold">✓ DEPLOYED</text>'

    # deployment frequency trend
    weeks = list(range(1, 13))
    deploy_count = [1, 1, 1, 2, 2, 2, 3, 3, 3, 4, 4, 4]
    freq_pts = " ".join(f"{30+i*37:.1f},{130-deploy_count[i]/5*100:.1f}" for i in range(len(weeks)))
    freq_svg = f'<polyline points="{freq_pts}" fill="none" stroke="#22c55e" stroke-width="2.5"/>'
    for i, (w, d) in enumerate(zip(weeks, deploy_count)):
        x = 30 + i * 37
        freq_svg += f'<circle cx="{x}" cy="{130-d/5*100:.1f}" r="4" fill="#22c55e"/>'
        freq_svg += f'<text x="{x}" y="142" fill="#64748b" font-size="9" text-anchor="middle">W{w}</text>'

    # DORA metrics
    dora = [("Lead Time", "4.2h", "#22c55e"), ("Deploy Freq", "4/wk", "#22c55e"),
            ("MTTR", "8min", "#22c55e"), ("Change Fail", "4.7%", "#38bdf8")]
    dora_svg = ""
    for i, (metric, val, color) in enumerate(dora):
        x = 15 + i * 115
        dora_svg += f'<rect x="{x}" y="20" width="105" height="60" fill="#0f172a" rx="8" stroke="{color}" stroke-width="2"/>'
        dora_svg += f'<text x="{x+52}" y="48" fill="{color}" font-size="18" font-weight="bold" text-anchor="middle">{val}</text>'
        dora_svg += f'<text x="{x+52}" y="66" fill="#94a3b8" font-size="10" text-anchor="middle">{metric}</text>'

    return f"""<!DOCTYPE html>
<html>
<head><title>Deployment Pipeline v2</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',sans-serif}}
.hdr{{background:#1e293b;padding:16px 24px;border-bottom:2px solid #C74634;display:flex;align-items:center;gap:12px}}
.hdr h1{{margin:0;font-size:20px;color:#f1f5f9}}
.badge{{background:#C74634;color:#fff;padding:3px 10px;border-radius:12px;font-size:11px;font-weight:700}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;padding:20px}}
.card{{background:#1e293b;border-radius:10px;padding:18px;border:1px solid #334155}}
.card h3{{margin:0 0 12px;font-size:14px;color:#94a3b8;text-transform:uppercase;letter-spacing:.05em}}
.metrics{{padding:16px 20px}}
.dora-row{{display:flex;gap:12px;justify-content:center;padding:8px 0}}
</style>
</head>
<body>
<div class="hdr">
  <span class="badge">PORT {PORT}</span>
  <h1>Deployment Pipeline v2 — Green CD</h1>
</div>
<div class="dora-row">
  <svg viewBox="0 0 490 95" width="90%">{dora_svg}</svg>
</div>
<div class="grid">
  <div class="card" style="grid-column:1/3">
    <h3>9-Stage CD Pipeline (4.2h total lead time)</h3>
    <svg viewBox="0 0 680 60" width="100%">
      {stage_svg}
    </svg>
  </div>
  <div class="card" style="grid-column:1/2">
    <h3>Deployment Frequency (12-week trend)</h3>
    <svg viewBox="0 0 480 155" width="100%">
      <line x1="25" y1="10" x2="25" y2="138" stroke="#334155" stroke-width="1"/>
      <line x1="25" y1="138" x2="475" y2="138" stroke="#334155" stroke-width="1"/>
      {freq_svg}
      <text x="275" y="155" fill="#64748b" font-size="9" text-anchor="middle">Week</text>
    </svg>
  </div>
</div>
</body>
</html>"""

if USE_FASTAPI:
    app = FastAPI(title="Deployment Pipeline v2")
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
