"""Cost Forecast Dashboard — FastAPI port 8475"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8475

def build_html():
    months = ["Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec", "Jan", "Feb", "Mar"]
    # stacked costs: training, eval, inference, partner
    training = [18200, 19800, 24100, 22400, 23100, 38700, 28100, 26400, 24800, 27200, 28900, 31100]
    eval_c   = [ 6800,  7200,  8400,  7800,  8100, 12400,  9200,  8700,  8200,  9100,  9600, 10200]
    infr     = [ 4200,  4400,  5100,  4700,  4900,  8200,  5800,  5400,  5100,  5600,  5900,  6300]
    partner  = [ 1800,  2200,  3400,  3100,  3400,  5700,  4100,  3900,  3700,  4100,  4400,  4800]

    totals = [t+e+i+p for t,e,i,p in zip(training, eval_c, infr, partner)]
    max_total = max(totals) + 8000
    col_w = 44
    stacked_svg = ""
    for i, (t, e, inf_c, p, total) in enumerate(zip(training, eval_c, infr, partner, totals)):
        x = 35 + i * (col_w + 4)
        components = [(p, "#8b5cf6"), (inf_c, "#38bdf8"), (e, "#f59e0b"), (t, "#C74634")]
        y_base = 180
        for val, color in components:
            h = int(val / max_total * 155)
            y_base -= h
            stacked_svg += f'<rect x="{x}" y="{y_base}" width="{col_w}" height="{h}" fill="{color}" opacity="0.8"/>'
        stacked_svg += f'<text x="{x+col_w//2}" y="192" fill="#64748b" font-size="8" text-anchor="middle">{months[i]}</text>'
        if total > 40000:
            stacked_svg += f'<text x="{x+col_w//2}" y="{y_base-3}" fill="#C74634" font-size="7" text-anchor="middle">★Sep</text>'

    # cost driver attribution donut
    drivers = [("DAgger Runs", 0.38, "#C74634"), ("SDG", 0.22, "#38bdf8"),
               ("Inference", 0.19, "#22c55e"), ("Eval", 0.14, "#f59e0b"), ("Misc", 0.07, "#8b5cf6")]
    cx, cy, r_out, r_in = 130, 110, 90, 45
    donut = ""
    angle = -math.pi / 2
    for label, frac, color in drivers:
        sweep = frac * 2 * math.pi
        x1 = cx + r_out * math.cos(angle)
        y1 = cy + r_out * math.sin(angle)
        x2 = cx + r_out * math.cos(angle + sweep)
        y2 = cy + r_out * math.sin(angle + sweep)
        xi1 = cx + r_in * math.cos(angle)
        yi1 = cy + r_in * math.sin(angle)
        xi2 = cx + r_in * math.cos(angle + sweep)
        yi2 = cy + r_in * math.sin(angle + sweep)
        large = 1 if sweep > math.pi else 0
        donut += f'<path d="M {x1:.1f} {y1:.1f} A {r_out} {r_out} 0 {large} 1 {x2:.1f} {y2:.1f} L {xi2:.1f} {yi2:.1f} A {r_in} {r_in} 0 {large} 0 {xi1:.1f} {yi1:.1f} Z" fill="{color}" opacity="0.85"/>'
        mid = angle + sweep / 2
        lx = cx + (r_out + 15) * math.cos(mid)
        ly = cy + (r_out + 15) * math.sin(mid)
        donut += f'<text x="{lx:.1f}" y="{ly:.1f}" fill="#e2e8f0" font-size="9" text-anchor="middle">{int(frac*100)}%</text>'
        angle += sweep
    donut += f'<text x="{cx}" y="{cy+5}" fill="#e2e8f0" font-size="11" font-weight="bold" text-anchor="middle">$312k</text>'
    donut += f'<text x="{cx}" y="{cy+18}" fill="#94a3b8" font-size="9" text-anchor="middle">Annual</text>'

    return f"""<!DOCTYPE html>
<html>
<head><title>Cost Forecast Dashboard</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',sans-serif}}
.hdr{{background:#1e293b;padding:16px 24px;border-bottom:2px solid #C74634;display:flex;align-items:center;gap:12px}}
.hdr h1{{margin:0;font-size:20px;color:#f1f5f9}}
.badge{{background:#C74634;color:#fff;padding:3px 10px;border-radius:12px;font-size:11px;font-weight:700}}
.grid{{display:grid;grid-template-columns:3fr 2fr;gap:16px;padding:20px}}
.card{{background:#1e293b;border-radius:10px;padding:18px;border:1px solid #334155}}
.card h3{{margin:0 0 12px;font-size:14px;color:#94a3b8;text-transform:uppercase;letter-spacing:.05em}}
.metrics{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;padding:16px 20px}}
.m{{background:#1e293b;border-radius:8px;padding:12px 16px;border:1px solid #334155}}
.mv{{font-size:24px;font-weight:700;color:#38bdf8}}
.ml{{font-size:11px;color:#64748b;margin-top:2px}}
.delta{{font-size:12px;color:#f59e0b;margin-top:4px}}
.legend{{display:flex;flex-wrap:wrap;gap:8px;margin-top:8px}}
.li{{display:flex;align-items:center;gap:5px;font-size:11px}}
.ld{{width:10px;height:10px;border-radius:2px}}
</style>
</head>
<body>
<div class="hdr">
  <span class="badge">PORT {PORT}</span>
  <h1>Cost Forecast Dashboard — Apr 2026–Mar 2027</h1>
</div>
<div class="metrics">
  <div class="m"><div class="mv">$312k</div><div class="ml">Annual OCI Forecast</div></div>
  <div class="m"><div class="mv">$26k</div><div class="ml">Mar 2026 Current</div></div>
  <div class="m"><div class="mv">Sep ★</div><div class="ml">Peak Month (AI World)</div><div class="delta">3× normal $65k</div></div>
  <div class="m"><div class="mv">DAgger</div><div class="ml">Top Cost Driver</div><div class="delta">38% of spend</div></div>
</div>
<div class="grid">
  <div class="card">
    <h3>12-Month Stacked Cost Forecast</h3>
    <svg viewBox="0 0 600 205" width="100%">
      <line x1="30" y1="10" x2="30" y2="183" stroke="#334155" stroke-width="1"/>
      <line x1="30" y1="183" x2="595" y2="183" stroke="#334155" stroke-width="1"/>
      {stacked_svg}
    </svg>
    <div class="legend">
      <div class="li"><div class="ld" style="background:#C74634"></div>Training</div>
      <div class="li"><div class="ld" style="background:#f59e0b"></div>Eval</div>
      <div class="li"><div class="ld" style="background:#38bdf8"></div>Inference</div>
      <div class="li"><div class="ld" style="background:#8b5cf6"></div>Partner</div>
    </div>
  </div>
  <div class="card">
    <h3>Cost Driver Attribution</h3>
    <svg viewBox="0 0 280 230" width="100%">
      {donut}
    </svg>
  </div>
</div>
</body>
</html>"""

if USE_FASTAPI:
    app = FastAPI(title="Cost Forecast Dashboard")
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
