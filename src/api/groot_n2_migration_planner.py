"""GR00T N2 Migration Planner — FastAPI port 8447"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8447

def build_html():
    # Gantt chart SVG
    milestones = [
        ("NVIDIA N2 weights available", 1, 2, "#38bdf8"),
        ("Infra upgrade (A100 80GB → H100)", 2, 3, "#f59e0b"),
        ("Fine-tune pipeline adaptation", 3, 5, "#C74634"),
        ("DAgger run12 (N2 backbone)", 5, 7, "#C74634"),
        ("Bimanual eval suite", 6, 8, "#22c55e"),
        ("Staging validation", 8, 9, "#f59e0b"),
        ("Production cutover", 9, 10, "#22c55e"),
    ]
    gantt = ""
    month_labels = ["Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov"]
    col_w = 52
    start_x = 220
    for i, label in enumerate(month_labels):
        x = start_x + i * col_w
        gantt += f'<line x1="{x}" y1="10" x2="{x}" y2="220" stroke="#1e293b" stroke-width="1"/>'
        gantt += f'<text x="{x + col_w//2}" y="230" fill="#64748b" font-size="10" text-anchor="middle">{label}</text>'
    for i, (label, s, e, color) in enumerate(milestones):
        y = 30 + i * 26
        bx = start_x + (s - 1) * col_w
        bw = (e - s) * col_w - 4
        gantt += f'<rect x="{bx}" y="{y}" width="{bw}" height="18" fill="{color}" rx="4" opacity="0.85"/>'
        gantt += f'<text x="{bx - 8}" y="{y + 13}" fill="#94a3b8" font-size="10" text-anchor="end">{label}</text>'

    # risk matrix SVG
    risks = [
        ("N2 weights delayed", 0.35, 0.85, "#C74634"),
        ("H100 quota", 0.55, 0.65, "#f59e0b"),
        ("Fine-tune regression", 0.45, 0.55, "#f59e0b"),
        ("Partner API break", 0.25, 0.40, "#22c55e"),
        ("Cost overrun", 0.60, 0.30, "#22c55e"),
    ]
    risk_svg = ""
    for label, prob, impact, color in risks:
        rx = 30 + prob * 200
        ry = 190 - impact * 160
        risk_svg += f'<circle cx="{rx:.1f}" cy="{ry:.1f}" r="7" fill="{color}" opacity="0.85"/>'
        risk_svg += f'<text x="{rx+10:.1f}" y="{ry+4:.1f}" fill="#e2e8f0" font-size="9">{label}</text>'

    return f"""<!DOCTYPE html>
<html>
<head><title>GR00T N2 Migration Planner</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',sans-serif}}
.hdr{{background:#1e293b;padding:16px 24px;border-bottom:2px solid #C74634;display:flex;align-items:center;gap:12px}}
.hdr h1{{margin:0;font-size:20px;color:#f1f5f9}}
.badge{{background:#C74634;color:#fff;padding:3px 10px;border-radius:12px;font-size:11px;font-weight:700}}
.grid{{display:grid;grid-template-columns:2fr 1fr;gap:16px;padding:20px}}
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
  <h1>GR00T N2 Migration Planner — Jun 2026 Cutover</h1>
</div>
<div class="metrics">
  <div class="m"><div class="mv">+12pp</div><div class="ml">SR Gain (N2 vs N1.6)</div><div class="delta">71% → 83% projected</div></div>
  <div class="m"><div class="mv">Jun 2026</div><div class="ml">Production Cutover</div></div>
  <div class="m"><div class="mv">Bimanual</div><div class="ml">Key New Capability</div><div class="delta">2-arm coordination</div></div>
  <div class="m"><div class="mv">3B→7B</div><div class="ml">Param Scale (N1.6→N2)</div></div>
</div>
<div class="grid">
  <div class="card">
    <h3>Migration Timeline (Apr–Nov 2026)</h3>
    <svg viewBox="0 0 660 245" width="100%">
      {gantt}
    </svg>
  </div>
  <div class="card">
    <h3>Risk Matrix</h3>
    <svg viewBox="0 0 280 210" width="100%">
      <rect x="30" y="30" width="200" height="160" fill="#0f172a" rx="4"/>
      <line x1="130" y1="30" x2="130" y2="190" stroke="#334155" stroke-width="1" stroke-dasharray="3,3"/>
      <line x1="30" y1="110" x2="230" y2="110" stroke="#334155" stroke-width="1" stroke-dasharray="3,3"/>
      <rect x="130" y="30" width="100" height="80" fill="#C74634" opacity="0.07" rx="2"/>
      <text x="35" y="208" fill="#64748b" font-size="9">Low Prob</text>
      <text x="200" y="208" fill="#64748b" font-size="9">High Prob</text>
      <text x="15" y="190" fill="#64748b" font-size="9" transform="rotate(-90,15,190)">Impact</text>
      {risk_svg}
    </svg>
  </div>
</div>
</body>
</html>"""

if USE_FASTAPI:
    app = FastAPI(title="GR00T N2 Migration Planner")
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
