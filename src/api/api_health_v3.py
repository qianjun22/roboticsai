"""API Health v3 — FastAPI port 8395"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8395

ENDPOINTS = [
    {"ep": "/predict",          "p50": 226, "p99": 267,  "err": 0.12, "status": "GREEN"},
    {"ep": "/embed",            "p50":  41, "p99":  78,  "err": 0.08, "status": "GREEN"},
    {"ep": "/finetune/start",   "p50": 312, "p99": 891,  "err": 0.24, "status": "AMBER"},
    {"ep": "/dagger_step",      "p50": 187, "p99": 401,  "err": 0.91, "status": "AMBER"},
    {"ep": "/health",           "p50":   2, "p99":   8,  "err": 0.00, "status": "GREEN"},
    {"ep": "/models",           "p50":  18, "p99":  42,  "err": 0.00, "status": "GREEN"},
    {"ep": "/checkpoint/compare","p50": 847, "p99": 2100, "err": 1.20, "status": "RED"},
    {"ep": "/data/ingest",      "p50":  67, "p99":  98,  "err": 0.05, "status": "GREEN"},
    {"ep": "/eval/run",         "p50":  88, "p99": 120,  "err": 0.07, "status": "GREEN"},
    {"ep": "/sim/reset",        "p50":  55, "p99":  89,  "err": 0.03, "status": "GREEN"},
    {"ep": "/policy/load",      "p50":  91, "p99": 143,  "err": 0.06, "status": "GREEN"},
    {"ep": "/metrics",          "p50":   9, "p99":  22,  "err": 0.00, "status": "GREEN"},
]

TREND_EPS = ["/predict", "/embed", "/finetune/start", "/dagger_step", "/checkpoint/compare"]
TREND_BASE = {"predict": 0.10, "embed": 0.07, "finetune_start": 0.20, "dagger_step": 0.85, "checkpoint_compare": 1.10}

def build_table_svg():
    row_h = 26
    n = len(ENDPOINTS)
    w, h = 600, 60 + n * row_h
    svg = [f'<svg width="{w}" height="{h}" style="background:#1e293b;border-radius:8px">']
    svg.append(f'<text x="{w//2}" y="20" fill="#e2e8f0" font-size="13" font-weight="bold" text-anchor="middle">12-Endpoint Health Table</text>')
    headers = [("Endpoint", 10), ("p50", 230), ("p99", 310), ("Error%", 390), ("Status", 480)]
    for txt, x in headers:
        svg.append(f'<text x="{x+4}" y="40" fill="#94a3b8" font-size="11" font-weight="bold">{txt}</text>')
    svg.append(f'<line x1="0" y1="44" x2="{w}" y2="44" stroke="#334155" stroke-width="1"/>')
    STATUS_COL = {"GREEN": "#22c55e", "AMBER": "#f59e0b", "RED": "#ef4444"}
    for i, ep in enumerate(ENDPOINTS):
        y = 44 + i * row_h
        bg = "#1e293b" if i % 2 == 0 else "#243045"
        svg.append(f'<rect x="0" y="{y}" width="{w}" height="{row_h}" fill="{bg}"/>')
        ty = y + 17
        svg.append(f'<text x="14" y="{ty}" fill="#cbd5e1" font-size="11">{ep["ep"]}</text>')
        svg.append(f'<text x="234" y="{ty}" fill="#cbd5e1" font-size="11">{ep["p50"]}ms</text>')
        svg.append(f'<text x="314" y="{ty}" fill="#cbd5e1" font-size="11">{ep["p99"]}ms</text>')
        ec = "#ef4444" if ep["err"] >= 1.0 else ("#f59e0b" if ep["err"] >= 0.5 else "#cbd5e1")
        svg.append(f'<text x="394" y="{ty}" fill="{ec}" font-size="11">{ep["err"]:.2f}%</text>')
        sc = STATUS_COL.get(ep["status"], "#64748b")
        svg.append(f'<rect x="484" y="{y+6}" width="60" height="14" rx="7" fill="{sc}" opacity="0.25"/>')
        svg.append(f'<text x="514" y="{ty}" fill="{sc}" font-size="10" font-weight="bold" text-anchor="middle">{ep["status"]}</text>')
    svg.append('</svg>')
    return '\n'.join(svg)

def build_trend_svg():
    w, h = 560, 260
    pad_l, pad_b, pad_t = 50, 40, 30
    days = 30
    chart_w = w - pad_l - 20
    chart_h = h - pad_b - pad_t
    svg = [f'<svg width="{w}" height="{h}" style="background:#1e293b;border-radius:8px">']
    svg.append(f'<text x="{w//2}" y="20" fill="#e2e8f0" font-size="13" font-weight="bold" text-anchor="middle">Error Rate 30-Day Trend</text>')
    max_err = 1.5
    def ys(v): return pad_t + chart_h - int(v / max_err * chart_h)
    for grid in [0.0, 0.5, 1.0, 1.5]:
        gy = ys(grid)
        svg.append(f'<line x1="{pad_l}" y1="{gy}" x2="{w-20}" y2="{gy}" stroke="#334155" stroke-width="1"/>')
        svg.append(f'<text x="{pad_l-4}" y="{gy+4}" fill="#64748b" font-size="9" text-anchor="end">{grid:.1f}%</text>')
    colors = ["#38bdf8", "#22c55e", "#f59e0b", "#C74634", "#ef4444"]
    base_vals = list(TREND_BASE.values())
    for ci, (ep_name, base) in enumerate(zip(TREND_EPS, base_vals)):
        pts = []
        random.seed(ci * 137)
        for d in range(days):
            noise = random.gauss(0, base * 0.1)
            trend = base + noise + (0.02 if d > 20 and ci == 3 else 0)
            val = max(0, trend)
            x = pad_l + int(d / (days-1) * chart_w)
            y = ys(val)
            pts.append(f"{x},{y}")
        svg.append(f'<polyline points="{" ".join(pts)}" fill="none" stroke="{colors[ci]}" stroke-width="1.5"/>')
        lx = pad_l + chart_w + 4
        last_y = ys(base)
        ep_label = ep_name.replace("/", "").replace("_"," ")
        svg.append(f'<text x="{w-18}" y="{last_y+4}" fill="{colors[ci]}" font-size="9" text-anchor="end">{TREND_EPS[ci]}</text>')
    svg.append(f'<line x1="{pad_l}" y1="{ys(1.0)}" x2="{w-20}" y2="{ys(1.0)}" stroke="#C74634" stroke-width="1" stroke-dasharray="4,3"/>')
    svg.append(f'<text x="{pad_l+5}" y="{ys(1.0)-4}" fill="#C74634" font-size="9">SLA 1.0%</text>')
    svg.append('</svg>')
    return '\n'.join(svg)

def build_html():
    table = build_table_svg()
    trend = build_trend_svg()
    return f"""<!DOCTYPE html><html><head><meta charset='utf-8'>
<title>API Health v3</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:sans-serif;padding:24px}}
h1{{color:#38bdf8;font-size:1.4rem;margin-bottom:4px}}.sub{{color:#64748b;font-size:.85rem;margin-bottom:20px}}
.row{{display:flex;gap:20px;flex-wrap:wrap;margin-bottom:20px}}
.stat{{background:#1e293b;border:1px solid #334155;border-radius:8px;padding:14px 20px;min-width:180px}}
.sv{{font-size:1.5rem;font-weight:bold;color:#38bdf8}}
.sl{{font-size:.8rem;color:#94a3b8;margin-top:4px}}
.warn{{color:#f59e0b!important}}.red{{color:#ef4444!important}}
</style></head><body>
<h1>API Health v3</h1>
<div class='sub'>Comprehensive API endpoint health monitoring &mdash; Port {PORT}</div>
<div class='row'>
  <div class='stat'><div class='sv'>12</div><div class='sl'>Endpoints monitored</div></div>
  <div class='stat'><div class='sv'>99.72%</div><div class='sl'>Overall success rate</div></div>
  <div class='stat'><div class='sv warn'>401ms</div><div class='sl'>/dagger_step p99 (SLA=300ms) WARNING</div></div>
  <div class='stat'><div class='sv'>41ms</div><div class='sl'>/embed p50 (fastest)</div></div>
</div>
<div class='row'>
  <div>{table}</div>
  <div>{trend}</div>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="API Health v3")
    @app.get("/", response_class=HTMLResponse)
    def index(): return build_html()
    @app.get("/health")
    def health(): return {{"status": "ok", "port": PORT}}

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
