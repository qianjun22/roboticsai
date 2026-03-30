"""CSAT Trend Analyzer — FastAPI port 8398"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8398

PARTNERS = ["PI", "Apt", "1X", "Covariant", "Figure"]
COLORS = ["#38bdf8", "#a78bfa", "#f87171", "#34d399", "#fbbf24"]
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun"]
DATA = {
    "PI":       [4.1, 4.2, 4.4, 4.5, 4.6, 4.7],
    "Apt":      [3.9, 4.0, 4.1, 4.0, 4.2, 4.3],
    "1X":       [3.4, 3.1, 2.9, 2.8, 2.6, 2.8],
    "Covariant":[4.0, 4.1, 4.2, 3.6, 4.3, 4.4],
    "Figure":   [3.7, 3.8, 3.9, 4.0, 4.0, 4.1],
}
AVG = [3.8, 3.8, 3.9, 3.8, 3.9, 4.1]
SR_DATA = {"PI": (4.5, 18), "Apt": (4.1, 32), "1X": (2.8, 89), "Covariant": (4.1, 41), "Figure": (3.9, 55)}
DONUT_CATS = [("Integration", 35, "#38bdf8"), ("Performance", 22, "#a78bfa"),
              ("Billing", 18, "#fbbf24"), ("Feature Req", 15, "#34d399"), ("Data", 10, "#f87171")]

def make_trend_svg():
    W, H, ml, mr, mt, mb = 560, 260, 50, 20, 20, 40
    pw, ph = W - ml - mr, H - mt - mb
    ymin, ymax = 2.4, 5.0
    def px(i): return ml + i * pw / 5
    def py(v): return mt + ph - (v - ymin) / (ymax - ymin) * ph
    lines = []
    # grid
    for v in [2.5, 3.0, 3.5, 4.0, 4.5, 5.0]:
        y = py(v)
        lines.append(f'<line x1="{ml}" y1="{y:.1f}" x2="{ml+pw}" y2="{y:.1f}" stroke="#1e3a5f" stroke-width="1"/>')
        lines.append(f'<text x="{ml-6}" y="{y+4:.1f}" fill="#94a3b8" font-size="10" text-anchor="end">{v}</text>')
    # month labels
    for i, m in enumerate(MONTHS):
        lines.append(f'<text x="{px(i):.1f}" y="{H-8}" fill="#94a3b8" font-size="11" text-anchor="middle">{m}</text>')
    # NPS target dashed
    yt = py(4.5)
    lines.append(f'<line x1="{ml}" y1="{yt:.1f}" x2="{ml+pw}" y2="{yt:.1f}" stroke="#64748b" stroke-width="1.5" stroke-dasharray="6,4"/>')
    lines.append(f'<text x="{ml+pw+2}" y="{yt+4:.1f}" fill="#64748b" font-size="9">Target</text>')
    # partner lines
    for pi, (name, color) in enumerate(zip(PARTNERS, COLORS)):
        vals = DATA[name]
        pts = " ".join(f"{px(i):.1f},{py(v):.1f}" for i, v in enumerate(vals))
        lines.append(f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2"/>')
        for i, v in enumerate(vals):
            lines.append(f'<circle cx="{px(i):.1f}" cy="{py(v):.1f}" r="3.5" fill="{color}"/>')
    # avg bold red
    pts = " ".join(f"{px(i):.1f},{py(v):.1f}" for i, v in enumerate(AVG))
    lines.append(f'<polyline points="{pts}" fill="none" stroke="#C74634" stroke-width="3"/>')
    # legend
    lx = ml
    for i, (name, color) in enumerate(zip(PARTNERS, COLORS)):
        lines.append(f'<rect x="{lx+i*100}" y="2" width="12" height="8" fill="{color}"/>')
        lines.append(f'<text x="{lx+i*100+15}" y="10" fill="#e2e8f0" font-size="9">{name}</text>')
    lines.append(f'<rect x="{lx+500}" y="2" width="12" height="8" fill="#C74634"/>')
    lines.append(f'<text x="{lx+515}" y="10" fill="#e2e8f0" font-size="9">Avg</text>')
    return f'<svg width="{W}" height="{H}" style="background:#0f172a">{chr(10).join(lines)}</svg>'

def make_scatter_svg():
    W, H, m = 400, 300, 50
    pw, ph = W - 2*m, H - 2*m
    # x=SR tickets 10-100, y=CSAT 2.4-5.0
    xmin, xmax, ymin, ymax = 10, 100, 2.4, 5.0
    def px(v): return m + (v - xmin) / (xmax - xmin) * pw
    def py(v): return m + ph - (v - ymin) / (ymax - ymin) * ph
    lines = []
    for v in [3.0, 3.5, 4.0, 4.5, 5.0]:
        lines.append(f'<line x1="{m}" y1="{py(v):.1f}" x2="{m+pw}" y2="{py(v):.1f}" stroke="#1e3a5f" stroke-width="1"/>')
    for v in [20, 40, 60, 80, 100]:
        lines.append(f'<line x1="{px(v):.1f}" y1="{m}" x2="{px(v):.1f}" y2="{m+ph}" stroke="#1e3a5f" stroke-width="1"/>')
        lines.append(f'<text x="{px(v):.1f}" y="{m+ph+15}" fill="#94a3b8" font-size="9" text-anchor="middle">{v}</text>')
    lines.append(f'<text x="{W//2}" y="{H-2}" fill="#94a3b8" font-size="10" text-anchor="middle">Support Tickets / Month</text>')
    lines.append(f'<text x="12" y="{H//2}" fill="#94a3b8" font-size="10" text-anchor="middle" transform="rotate(-90,12,{H//2})">CSAT</text>')
    # regression line approx
    lines.append(f'<line x1="{px(18):.1f}" y1="{py(4.7):.1f}" x2="{px(89):.1f}" y2="{py(2.8):.1f}" stroke="#C74634" stroke-width="1.5" stroke-dasharray="5,3"/>')
    for i, (name, color) in enumerate(zip(PARTNERS, COLORS)):
        csat, sr = SR_DATA[name]
        lines.append(f'<circle cx="{px(sr):.1f}" cy="{py(csat):.1f}" r="7" fill="{color}" opacity="0.85"/>')
        lines.append(f'<text x="{px(sr):.1f}" y="{py(csat)-10:.1f}" fill="{color}" font-size="10" text-anchor="middle">{name}</text>')
    lines.append(f'<text x="{m+pw-5}" y="{m+15}" fill="#94a3b8" font-size="10" text-anchor="end">r=0.73</text>')
    return f'<svg width="{W}" height="{H}" style="background:#0f172a">{chr(10).join(lines)}</svg>'

def make_donut_svg():
    W, H, cx, cy, R, r = 320, 280, 160, 140, 110, 60
    lines = []
    total = sum(p for _, p, _ in DONUT_CATS)
    angle = -math.pi / 2
    for label, pct, color in DONUT_CATS:
        sweep = 2 * math.pi * pct / total
        x1, y1 = cx + R * math.cos(angle), cy + R * math.sin(angle)
        x2, y2 = cx + R * math.cos(angle + sweep), cy + R * math.sin(angle + sweep)
        x1i, y1i = cx + r * math.cos(angle), cy + r * math.sin(angle)
        x2i, y2i = cx + r * math.cos(angle + sweep), cy + r * math.sin(angle + sweep)
        la = 1 if sweep > math.pi else 0
        d = f"M {x1:.1f},{y1:.1f} A {R},{R} 0 {la},1 {x2:.1f},{y2:.1f} L {x2i:.1f},{y2i:.1f} A {r},{r} 0 {la},0 {x1i:.1f},{y1i:.1f} Z"
        lines.append(f'<path d="{d}" fill="{color}" stroke="#0f172a" stroke-width="2"/>')
        mid = angle + sweep / 2
        lx, ly = cx + (R + r) / 2 * math.cos(mid), cy + (R + r) / 2 * math.sin(mid)
        lines.append(f'<text x="{lx:.1f}" y="{ly:.1f}" fill="#0f172a" font-size="10" text-anchor="middle" font-weight="bold">{pct}%</text>')
        angle += sweep
    # legend
    for i, (label, pct, color) in enumerate(DONUT_CATS):
        ly2 = H - 90 + i * 17
        lines.append(f'<rect x="10" y="{ly2}" width="12" height="10" fill="{color}"/>')
        lines.append(f'<text x="26" y="{ly2+9}" fill="#e2e8f0" font-size="11">{label} {pct}%</text>')
    return f'<svg width="{W}" height="{H}" style="background:#0f172a">{chr(10).join(lines)}</svg>'

def build_html():
    trend = make_trend_svg()
    scatter = make_scatter_svg()
    donut = make_donut_svg()
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>CSAT Trend Analyzer</title>
<style>body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:sans-serif;padding:20px}}
h1{{color:#C74634;margin-bottom:4px}}h2{{color:#38bdf8;font-size:14px;margin:16px 0 6px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:20px}}.card{{background:#1e293b;border-radius:8px;padding:16px}}
.stats{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-top:20px}}
.stat{{background:#1e293b;border-radius:8px;padding:12px;text-align:center}}
.stat-v{{font-size:24px;font-weight:bold;color:#38bdf8}}.stat-l{{font-size:11px;color:#94a3b8;margin-top:4px}}
.alert{{color:#f87171}}.good{{color:#34d399}}</style></head><body>
<h1>CSAT Trend Analyzer</h1><p style="color:#94a3b8;margin:0">Port 8398 — Design Partner Satisfaction Analytics</p>
<div class="grid" style="margin-top:20px">
<div class="card"><h2>6-Month CSAT Trend (Jan–Jun 2026)</h2>{trend}</div>
<div class="card"><h2>CSAT vs Support Tickets Correlation</h2>{scatter}</div>
</div>
<div style="display:grid;grid-template-columns:1fr 2fr;gap:20px;margin-top:20px">
<div class="card"><h2>Ticket Category Breakdown</h2>{donut}</div>
<div class="card"><h2>Key Insights</h2>
<ul style="color:#e2e8f0;line-height:1.8;font-size:13px">
<li><span class="good">PI 4.7/5</span> — best performer, rising trend</li>
<li><span class="alert">1X 2.8/5</span> — needs intervention, 89 tickets/mo</li>
<li>Covariant: spike May 3.6 (API outage), recovered Jun 4.4</li>
<li>Avg CSAT: 3.8 Mar → 4.1 Jun, trending to 4.4 Jun target</li>
<li>SR correlation r=0.73 — ticket volume predicts CSAT</li>
<li>Integration issues dominate (35% of tickets)</li>
<li>47 tickets avg/partner/month in Mar baseline</li>
</ul></div></div>
<div class="stats">
<div class="stat"><div class="stat-v good">4.1</div><div class="stat-l">Avg CSAT Mar</div></div>
<div class="stat"><div class="stat-v" style="color:#38bdf8">4.7</div><div class="stat-l">Best (PI) Jun</div></div>
<div class="stat"><div class="stat-v alert">2.8</div><div class="stat-l">Lowest (1X) Jun</div></div>
<div class="stat"><div class="stat-v" style="color:#fbbf24">47</div><div class="stat-l">Avg Tickets/Mar</div></div>
</div></body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="CSAT Trend Analyzer")
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
