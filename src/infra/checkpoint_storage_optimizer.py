"""Checkpoint Storage Optimizer — FastAPI port 8459"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8459

def build_html():
    # storage growth projection
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep"]
    actual = [22, 38, 57, 85, None, None, None, None, None]
    naive  = [None, None, None, 85, 121, 164, 212, 267, 330]
    smart  = [None, None, None, 85,  98, 112, 127, 143, 160]
    growth_svg = ""
    for i, (m, a) in enumerate(zip(months, actual)):
        if a is not None:
            x = 40 + i * 56
            h = int(a / 340 * 150)
            growth_svg += f'<circle cx="{x}" cy="{165-h}" r="4" fill="#38bdf8"/>'
            if i > 0 and actual[i-1] is not None:
                px = 40 + (i-1)*56
                ph = int(actual[i-1]/340*150)
                growth_svg += f'<line x1="{px}" y1="{165-ph}" x2="{x}" y2="{165-h}" stroke="#38bdf8" stroke-width="2"/>'
        growth_svg += f'<text x="{40+i*56}" y="180" fill="#64748b" font-size="9" text-anchor="middle">{m}</text>'
    # projections
    prev_n, prev_s = None, None
    for i, (n, s) in enumerate(zip(naive, smart)):
        x = 40 + i * 56
        if n is not None:
            hy = 165 - int(n/340*150)
            if prev_n is not None:
                growth_svg += f'<line x1="{prev_n[0]}" y1="{prev_n[1]}" x2="{x}" y2="{hy}" stroke="#C74634" stroke-width="1.5" stroke-dasharray="4,3"/>'
            prev_n = (x, hy)
        if s is not None:
            hy2 = 165 - int(s/340*150)
            if prev_s is not None:
                growth_svg += f'<line x1="{prev_s[0]}" y1="{prev_s[1]}" x2="{x}" y2="{hy2}" stroke="#22c55e" stroke-width="1.5" stroke-dasharray="4,3"/>'
            prev_s = (x, hy2)

    # deduplication savings bar
    runs = ["bc_500", "dagger_r5", "dagger_r9", "groot_v2", "groot_v3"]
    raw_gb = [18, 24, 21, 31, 19]
    dedup_gb = [18, 8, 7, 11, 14]
    dedup_bars = ""
    for i, (r, raw, ded) in enumerate(zip(runs, raw_gb, dedup_gb)):
        x = 20 + i * 85
        h_raw = int(raw / 35 * 130)
        h_ded = int(ded / 35 * 130)
        dedup_bars += f'<rect x="{x}" y="{145-h_raw}" width="35" height="{h_raw}" fill="#64748b" opacity="0.5" rx="3"/>'
        dedup_bars += f'<rect x="{x+37}" y="{145-h_ded}" width="35" height="{h_ded}" fill="#22c55e" rx="3"/>'
        dedup_bars += f'<text x="{x+36}" y="158" fill="#94a3b8" font-size="8" text-anchor="middle">{r}</text>'
        savings_pct = int((1 - ded/raw) * 100)
        dedup_bars += f'<text x="{x+18}" y="{145-h_raw-3}" fill="#f59e0b" font-size="8" text-anchor="middle">-{savings_pct}%</text>'

    return f"""<!DOCTYPE html>
<html>
<head><title>Checkpoint Storage Optimizer</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',sans-serif}}
.hdr{{background:#1e293b;padding:16px 24px;border-bottom:2px solid #C74634;display:flex;align-items:center;gap:12px}}
.hdr h1{{margin:0;font-size:20px;color:#f1f5f9}}
.badge{{background:#C74634;color:#fff;padding:3px 10px;border-radius:12px;font-size:11px;font-weight:700}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;padding:20px}}
.card{{background:#1e293b;border-radius:10px;padding:18px;border:1px solid #334155}}
.card h3{{margin:0 0 12px;font-size:14px;color:#94a3b8;text-transform:uppercase;letter-spacing:.05em}}
.metrics{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;padding:16px 20px}}
.m{{background:#1e293b;border-radius:8px;padding:12px 16px;border:1px solid #334155}}
.mv{{font-size:24px;font-weight:700;color:#38bdf8}}
.ml{{font-size:11px;color:#64748b;margin-top:2px}}
.delta{{font-size:12px;color:#22c55e;margin-top:4px}}
</style>
</head>
<body>
<div class="hdr">
  <span class="badge">PORT {PORT}</span>
  <h1>Checkpoint Storage Optimizer — Lifecycle Management</h1>
</div>
<div class="metrics">
  <div class="m"><div class="mv">85GB</div><div class="ml">Current Storage</div></div>
  <div class="m"><div class="mv">67%</div><div class="ml">Dedup Savings</div><div class="delta">delta compression</div></div>
  <div class="m"><div class="mv">$12/mo</div><div class="ml">Savings from Pruning</div></div>
  <div class="m"><div class="mv">5</div><div class="ml">Golden Checkpoints</div><div class="delta">preserved forever</div></div>
</div>
<div class="grid">
  <div class="card">
    <h3>Storage Growth: Naive vs Smart Lifecycle</h3>
    <svg viewBox="0 0 540 200" width="100%">
      <line x1="30" y1="10" x2="30" y2="168" stroke="#334155" stroke-width="1"/>
      <line x1="30" y1="168" x2="535" y2="168" stroke="#334155" stroke-width="1"/>
      {growth_svg}
      <text x="440" y="55" fill="#C74634" font-size="10">Naive: 330GB Sep</text>
      <text x="440" y="100" fill="#22c55e" font-size="10">Smart: 160GB Sep</text>
      <text x="290" y="30" fill="#38bdf8" font-size="10">Actual</text>
    </svg>
  </div>
  <div class="card">
    <h3>Delta Deduplication Savings per Run</h3>
    <svg viewBox="0 0 450 175" width="100%">
      <line x1="15" y1="10" x2="15" y2="148" stroke="#334155" stroke-width="1"/>
      <line x1="15" y1="148" x2="445" y2="148" stroke="#334155" stroke-width="1"/>
      {dedup_bars}
      <rect x="320" y="10" width="10" height="10" fill="#64748b" opacity="0.5"/>
      <text x="334" y="20" fill="#94a3b8" font-size="10">Raw</text>
      <rect x="320" y="25" width="10" height="10" fill="#22c55e"/>
      <text x="334" y="35" fill="#94a3b8" font-size="10">Deduped</text>
    </svg>
  </div>
</div>
</body>
</html>"""

if USE_FASTAPI:
    app = FastAPI(title="Checkpoint Storage Optimizer")
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
