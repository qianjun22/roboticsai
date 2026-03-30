"""Cloud Cost Dashboard V2 — FastAPI port 8445"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8445

def build_html():
    # donut SVG for cost breakdown
    categories = [("Compute", 0.52, "#C74634"), ("Storage", 0.18, "#38bdf8"),
                  ("Network", 0.12, "#f59e0b"), ("Inference", 0.11, "#22c55e"), ("Other", 0.07, "#8b5cf6")]
    cx, cy, r_outer, r_inner = 150, 130, 110, 55
    donut = ""
    angle = -math.pi / 2
    for label, frac, color in categories:
        sweep = frac * 2 * math.pi
        x1 = cx + r_outer * math.cos(angle)
        y1 = cy + r_outer * math.sin(angle)
        x2 = cx + r_outer * math.cos(angle + sweep)
        y2 = cy + r_outer * math.sin(angle + sweep)
        xi1 = cx + r_inner * math.cos(angle)
        yi1 = cy + r_inner * math.sin(angle)
        xi2 = cx + r_inner * math.cos(angle + sweep)
        yi2 = cy + r_inner * math.sin(angle + sweep)
        large = 1 if sweep > math.pi else 0
        donut += f'<path d="M {x1:.1f} {y1:.1f} A {r_outer} {r_outer} 0 {large} 1 {x2:.1f} {y2:.1f} L {xi2:.1f} {yi2:.1f} A {r_inner} {r_inner} 0 {large} 0 {xi1:.1f} {yi1:.1f} Z" fill="{color}" opacity="0.9"/>'
        mid_angle = angle + sweep / 2
        lx = cx + (r_outer + 20) * math.cos(mid_angle)
        ly = cy + (r_outer + 20) * math.sin(mid_angle)
        donut += f'<text x="{lx:.1f}" y="{ly:.1f}" fill="#e2e8f0" font-size="10" text-anchor="middle">{int(frac*100)}%</text>'
        angle += sweep

    # 6-month burn rate bars
    months = ["Oct", "Nov", "Dec", "Jan", "Feb", "Mar"]
    actuals = [18200, 19100, 21500, 22800, 24100, 26400]
    budget = 28000
    burn_svg = ""
    for i, (m, a) in enumerate(zip(months, actuals)):
        x = 40 + i * 72
        h = int(a / budget * 140)
        y = 155 - h
        color = "#22c55e" if a < budget * 0.85 else "#f59e0b" if a < budget else "#C74634"
        burn_svg += f'<rect x="{x}" y="{y}" width="44" height="{h}" fill="{color}" rx="3"/>'
        burn_svg += f'<text x="{x+22}" y="170" fill="#94a3b8" font-size="10" text-anchor="middle">{m}</text>'
        burn_svg += f'<text x="{x+22}" y="{y-4}" fill="#e2e8f0" font-size="9" text-anchor="middle">${a//1000}k</text>'
    burn_svg += f'<line x1="30" y1="{155-140}" x2="470" y2="{155-140}" stroke="#C74634" stroke-width="1.5" stroke-dasharray="4,3"/>'
    burn_svg += f'<text x="480" y="{155-136}" fill="#C74634" font-size="10">Budget ${budget//1000}k</text>'

    return f"""<!DOCTYPE html>
<html>
<head><title>Cloud Cost Dashboard V2</title>
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
.tco{{display:flex;gap:16px;padding:12px 0}}
.tco-item{{flex:1;text-align:center;padding:10px;background:#0f172a;border-radius:8px}}
.tco-val{{font-size:20px;font-weight:700}}
.legend{{display:flex;flex-wrap:wrap;gap:8px;margin-top:8px}}
.litem{{display:flex;align-items:center;gap:5px;font-size:11px}}
.ldot{{width:10px;height:10px;border-radius:50%}}
</style>
</head>
<body>
<div class="hdr">
  <span class="badge">PORT {PORT}</span>
  <h1>Cloud Cost Dashboard V2 — OCI Robot Cloud</h1>
</div>
<div class="metrics">
  <div class="m"><div class="mv">$26.4k</div><div class="ml">Mar 2026 Spend</div></div>
  <div class="m"><div class="mv">$28k</div><div class="ml">Monthly Budget</div></div>
  <div class="m"><div class="mv">94%</div><div class="ml">Budget Utilization</div></div>
  <div class="m"><div class="mv">9.6×</div><div class="ml">OCI vs AWS Savings</div></div>
</div>
<div class="grid">
  <div class="card">
    <h3>Cost Category Breakdown</h3>
    <svg viewBox="0 0 310 270" width="100%">
      {donut}
      <text x="{cx}" y="{cy-8}" fill="#e2e8f0" font-size="13" font-weight="bold" text-anchor="middle">$26.4k</text>
      <text x="{cx}" y="{cy+10}" fill="#94a3b8" font-size="10" text-anchor="middle">Mar Total</text>
    </svg>
    <div class="legend">
      {''.join(f'<div class="litem"><div class="ldot" style="background:{c}"></div>{l}</div>' for l,_,c in categories)}
    </div>
  </div>
  <div class="card">
    <h3>6-Month Burn Rate vs Budget</h3>
    <svg viewBox="0 0 530 185" width="100%">
      <line x1="30" y1="10" x2="30" y2="160" stroke="#334155" stroke-width="1"/>
      <line x1="30" y1="160" x2="520" y2="160" stroke="#334155" stroke-width="1"/>
      {burn_svg}
    </svg>
    <div class="tco">
      <div class="tco-item"><div class="tco-val" style="color:#22c55e">$0.94M</div><div style="font-size:11px;color:#64748b">OCI 3yr TCO</div></div>
      <div class="tco-item"><div class="tco-val" style="color:#C74634">$9.0M</div><div style="font-size:11px;color:#64748b">AWS 3yr TCO</div></div>
      <div class="tco-item"><div class="tco-val" style="color:#38bdf8">9.6×</div><div style="font-size:11px;color:#64748b">Savings Multiple</div></div>
    </div>
  </div>
</div>
</body>
</html>"""

if USE_FASTAPI:
    app = FastAPI(title="Cloud Cost Dashboard V2")
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
