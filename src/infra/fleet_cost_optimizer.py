"""Fleet Cost Optimizer — FastAPI port 8396"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8396

STRATEGIES = [
    {"name": "spot_training",      "savings": 147, "risk": "LOW",  "avail": "90%"},
    {"name": "right_size",         "savings":  89, "risk": "NONE", "avail": "100%"},
    {"name": "schedule_shift",     "savings":  64, "risk": "NONE", "avail": "100%"},
    {"name": "inference_cache",    "savings":  31, "risk": "LOW",  "avail": "95%"},
    {"name": "batch_consolidate",  "savings":  18, "risk": "NONE", "avail": "100%"},
    {"name": "storage_lifecycle",  "savings":   9, "risk": "NONE", "avail": "100%"},
]
MONTHLY_SAVINGS = [358, 412, 487, 531, 524, 512]
MONTHS = ["Apr", "May", "Jun", "Jul", "Aug", "Sep"]
UNOPTIMIZED_BASE = 1270
CURRENT_OPTIMIZED = 912


def build_html():
    # --- Bar chart SVG (strategy savings) ---
    bw, bh = 520, 220
    bar_h = 24
    pad_l, pad_t = 150, 20
    max_s = max(s["savings"] for s in STRATEGIES)
    bar_scale = (bw - pad_l - 40) / max_s
    bars = ""
    for i, s in enumerate(STRATEGIES):
        y = pad_t + i * (bar_h + 8)
        w = s["savings"] * bar_scale
        color = "#22c55e" if s["savings"] > 100 else "#38bdf8"
        bars += f'<text x="{pad_l-6}" y="{y+bar_h//2+5}" fill="#cbd5e1" font-size="11" text-anchor="end">{s["name"]}</text>'
        bars += f'<rect x="{pad_l}" y="{y}" width="{w:.1f}" height="{bar_h}" fill="{color}" rx="3"/>'
        bars += f'<text x="{pad_l+w+5}" y="{y+bar_h//2+5}" fill="#f1f5f9" font-size="11">${s["savings"]}/mo</text>'
    svg1 = f'''<svg width="{bw}" height="{pad_t*2 + len(STRATEGIES)*(bar_h+8)}" xmlns="http://www.w3.org/2000/svg">
  <rect width="100%" height="100%" fill="#1e293b" rx="8"/>
  <text x="{bw//2}" y="14" fill="#f1f5f9" font-size="13" font-weight="bold" text-anchor="middle">Savings by Strategy ($/mo)</text>
  {bars}
</svg>'''

    # --- Stacked area chart SVG (Apr-Sep trend) ---
    aw, ah = 520, 200
    apad_l, apad_b, apad_t = 50, 30, 30
    inner_w = aw - apad_l - 20
    inner_h = ah - apad_b - apad_t
    months_n = len(MONTHS)
    xs = [apad_l + i * inner_w / (months_n - 1) for i in range(months_n)]
    unopt = [UNOPTIMIZED_BASE + i * 60 for i in range(months_n)]
    savings = MONTHLY_SAVINGS
    max_val = max(unopt)
    def yscale(v): return apad_t + inner_h * (1 - v / max_val)
    # unoptimized top line
    unopt_pts = " ".join(f"{xs[i]:.1f},{yscale(unopt[i]):.1f}" for i in range(months_n))
    opt_pts = " ".join(f"{xs[i]:.1f},{yscale(unopt[i]-savings[i]):.1f}" for i in range(months_n))
    # savings fill polygon
    poly_top = [(xs[i], yscale(unopt[i])) for i in range(months_n)]
    poly_bot = [(xs[i], yscale(unopt[i]-savings[i])) for i in range(months_n)]
    poly_pts = " ".join(f"{x:.1f},{y:.1f}" for x,y in poly_top) + " " + \
               " ".join(f"{x:.1f},{y:.1f}" for x,y in reversed(poly_bot))
    month_labels = "".join(f'<text x="{xs[i]:.1f}" y="{ah-8}" fill="#94a3b8" font-size="10" text-anchor="middle">{MONTHS[i]}</text>' for i in range(months_n))
    sav_labels = "".join(f'<text x="{xs[i]:.1f}" y="{yscale(unopt[i]-savings[i])-5:.1f}" fill="#22c55e" font-size="9" text-anchor="middle">${savings[i]}</text>' for i in range(months_n))
    svg2 = f'''<svg width="{aw}" height="{ah}" xmlns="http://www.w3.org/2000/svg">
  <rect width="100%" height="100%" fill="#1e293b" rx="8"/>
  <text x="{aw//2}" y="16" fill="#f1f5f9" font-size="13" font-weight="bold" text-anchor="middle">Monthly Savings vs Unoptimized (Apr–Sep 2026)</text>
  <polygon points="{poly_pts}" fill="#22c55e" opacity="0.35"/>
  <polyline points="{unopt_pts}" fill="none" stroke="#C74634" stroke-width="2"/>
  <polyline points="{opt_pts}" fill="none" stroke="#22c55e" stroke-width="2"/>
  {month_labels}
  {sav_labels}
  <text x="{apad_l-4}" y="{apad_t}" fill="#C74634" font-size="9" text-anchor="end">Unopt</text>
  <text x="{apad_l-4}" y="{apad_t+14}" fill="#22c55e" font-size="9" text-anchor="end">Opt</text>
</svg>'''

    rows = "".join(
        f'<tr><td>{s["name"]}</td><td>${s["savings"]}/mo</td>'
        f'<td style="color:{'#f59e0b' if s['risk']=='LOW' else '#22c55e'}">{s["risk"]}</td>'
        f'<td>{s["avail"]}</td></tr>'
        for s in STRATEGIES
    )
    return f"""<!DOCTYPE html><html><head><meta charset='utf-8'>
<title>Fleet Cost Optimizer</title>
<style>body{{background:#0f172a;color:#f1f5f9;font-family:sans-serif;padding:24px}}
h1{{color:#C74634}}table{{border-collapse:collapse;width:100%}}td,th{{padding:6px 12px;border:1px solid #334155;font-size:13px}}
th{{background:#1e293b;color:#38bdf8}}.stat{{display:inline-block;background:#1e293b;border-radius:8px;padding:12px 24px;margin:8px;text-align:center}}
.sv{{font-size:28px;font-weight:bold;color:#22c55e}}.sl{{font-size:12px;color:#94a3b8}}</style></head><body>
<h1>Fleet Cost Optimizer — Port {PORT}</h1>
<div class='stat'><div class='sv'>$358/mo</div><div class='sl'>Current Savings</div></div>
<div class='stat'><div class='sv'>28%</div><div class='sl'>Below Unoptimized</div></div>
<div class='stat'><div class='sv'>32%</div><div class='sl'>Target Savings</div></div>
<div class='stat'><div class='sv'>$912/mo</div><div class='sl'>Optimized Cost</div></div>
<br/>{svg1}<br/><br/>{svg2}<br/><br/>
<h2 style='color:#38bdf8'>Strategy Details</h2>
<table><tr><th>Strategy</th><th>Savings</th><th>Preemption Risk</th><th>Availability</th></tr>{rows}</table>
</body></html>"""


if USE_FASTAPI:
    app = FastAPI(title="Fleet Cost Optimizer")
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
