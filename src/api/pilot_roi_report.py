"""Pilot ROI Report — FastAPI port 8471"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8471

def build_html():
    # per-pilot ROI waterfall
    partners = ["PI", "Apptronik", "1X", "Machina", "Wandelbots"]
    revenue = [14964, 7344, 4944, 0, 0]
    compute = [-4200, -2800, -2100, 0, 0]
    support = [-1800, -1400, -1200, 0, 0]
    npv = [8964, 3144, 1644, 0, 0]
    bar_colors = ["#22c55e", "#38bdf8", "#f59e0b", "#64748b", "#64748b"]

    waterfall_svg = ""
    for i, (partner, rev, comp, sup, net, color) in enumerate(zip(partners, revenue, compute, support, npv, bar_colors)):
        x = 20 + i * 95
        h_rev = int(rev / 16000 * 120)
        h_comp = int(abs(comp) / 16000 * 120)
        h_sup = int(abs(sup) / 16000 * 120)
        h_npv = int(abs(net) / 16000 * 120)
        if rev > 0:
            waterfall_svg += f'<rect x="{x}" y="{145-h_rev}" width="36" height="{h_rev}" fill="{color}" opacity="0.8" rx="3"/>'
            waterfall_svg += f'<rect x="{x+38}" y="{145}" width="20" height="{h_comp}" fill="#C74634" opacity="0.6" rx="3"/>'
            waterfall_svg += f'<rect x="{x+59}" y="{145}" width="20" height="{h_sup}" fill="#f59e0b" opacity="0.5" rx="3"/>'
            waterfall_svg += f'<text x="{x+43}" y="{145+h_comp+12}" fill="#94a3b8" font-size="8" text-anchor="middle">-${abs(comp)//1000}k</text>'
        else:
            waterfall_svg += f'<rect x="{x}" y="135" width="60" height="10" fill="#334155" rx="3"/>'
        waterfall_svg += f'<text x="{x+38}" y="168" fill="#94a3b8" font-size="10" text-anchor="middle">{partner}</text>'
        if net > 0:
            waterfall_svg += f'<text x="{x+18}" y="{145-h_rev-4}" fill="{color}" font-size="9" text-anchor="middle">NPV ${net//1000}k</text>'

    # payback period bar
    payback = [("PI", 4, "#22c55e"), ("Apptronik", 7, "#38bdf8"), ("1X", 14, "#f59e0b"), ("Machina", 18, "#64748b"), ("Wandelbots", 24, "#64748b")]
    payback_bars = ""
    for i, (partner, months, color) in enumerate(payback):
        y = 15 + i * 32
        w = int(months / 26 * 280)
        payback_bars += f'<rect x="90" y="{y}" width="{w}" height="24" fill="{color}" rx="4" opacity="0.85"/>'
        payback_bars += f'<text x="86" y="{y+16}" fill="#94a3b8" font-size="10" text-anchor="end">{partner}</text>'
        payback_bars += f'<text x="{90+w+5}" y="{y+16}" fill="#e2e8f0" font-size="10">{months}mo</text>'
    # target line at 12 months
    pb_line_x = 90 + int(12/26*280)
    payback_bars += f'<line x1="{pb_line_x}" y1="10" x2="{pb_line_x}" y2="178" stroke="#22c55e" stroke-width="1.5" stroke-dasharray="4,3"/>'
    payback_bars += f'<text x="{pb_line_x}" y="8" fill="#22c55e" font-size="9" text-anchor="middle">12mo target</text>'

    return f"""<!DOCTYPE html>
<html>
<head><title>Pilot ROI Report</title>
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
  <h1>Pilot ROI Report \u2014 Q2 2026 Cohort</h1>
</div>
<div class="metrics">
  <div class="m"><div class="mv">31%</div><div class="ml">Platform IRR</div></div>
  <div class="m"><div class="mv">$13.8k</div><div class="ml">Total NPV (active pilots)</div></div>
  <div class="m"><div class="mv">5.5mo</div><div class="ml">Avg Payback (active)</div></div>
  <div class="m"><div class="mv">71%</div><div class="ml">Gross Margin</div></div>
</div>
<div class="grid">
  <div class="card">
    <h3>Per-Pilot Revenue \u2192 Cost \u2192 NPV Waterfall</h3>
    <svg viewBox="0 0 500 185" width="100%">
      <line x1="15" y1="10" x2="15" y2="158" stroke="#334155" stroke-width="1"/>
      <line x1="15" y1="145" x2="495" y2="145" stroke="#334155" stroke-width="1"/>
      {waterfall_svg}
      <rect x="380" y="10" width="10" height="8" fill="#22c55e" opacity="0.8"/>
      <text x="394" y="18" fill="#94a3b8" font-size="9">Revenue</text>
      <rect x="380" y="23" width="10" height="8" fill="#C74634" opacity="0.6"/>
      <text x="394" y="31" fill="#94a3b8" font-size="9">Compute</text>
      <rect x="380" y="36" width="10" height="8" fill="#f59e0b" opacity="0.5"/>
      <text x="394" y="44" fill="#94a3b8" font-size="9">Support</text>
    </svg>
  </div>
  <div class="card">
    <h3>Payback Period by Partner</h3>
    <svg viewBox="0 0 420 195" width="100%">
      <line x1="88" y1="10" x2="88" y2="183" stroke="#334155" stroke-width="1"/>
      {payback_bars}
    </svg>
  </div>
</div>
</body>
</html>"""

if USE_FASTAPI:
    app = FastAPI(title="Pilot ROI Report")
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
