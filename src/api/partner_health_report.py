"""Partner Health Report — FastAPI port 8390"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8390

PARTNERS = ["PI", "Apptronik", "1X", "Covariant", "Figure AI"]
METRICS = ["SR", "Latency", "Cost", "Support", "Data", "Engage", "Renewal"]
SCORES = [
    [4.8, 4.5, 4.2, 4.9, 4.7, 4.8, 4.2],
    [3.9, 4.1, 3.8, 3.7, 4.0, 3.9, 4.2],
    [2.8, 3.1, 3.4, 2.1, 2.9, 2.2, 1.8],
    [3.8, 3.9, 4.1, 3.5, 3.7, 3.8, 4.0],
    [3.1, 3.4, 3.8, 4.2, 3.3, 3.6, 3.8],
]
TREND = [
    [4.2, 4.4, 4.6],
    [3.7, 3.8, 3.9],
    [3.1, 2.8, 2.6],
    [3.5, 3.7, 3.8],
    [3.3, 3.4, 3.6],
]
COLORS = ["#38bdf8", "#a78bfa", "#fb923c", "#34d399", "#f472b6"]

def cell_color(v):
    if v >= 4.0: return "#16a34a"
    if v >= 3.0: return "#d97706"
    return "#dc2626"

def build_heatmap():
    cw, ch = 72, 36
    lpad, tpad = 90, 40
    W = lpad + len(METRICS) * cw + 10
    H = tpad + len(PARTNERS) * ch + 10
    parts = [f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg">']
    parts.append(f'<rect width="{W}" height="{H}" fill="#1e293b" rx="8"/>')
    for j, m in enumerate(METRICS):
        x = lpad + j * cw + cw // 2
        parts.append(f'<text x="{x}" y="26" fill="#94a3b8" font-size="11" text-anchor="middle" font-family="monospace">{m}</text>')
    for i, p in enumerate(PARTNERS):
        y = tpad + i * ch + ch // 2
        parts.append(f'<text x="{lpad - 6}" y="{y + 5}" fill="#e2e8f0" font-size="11" text-anchor="end" font-family="monospace">{p}</text>')
        for j, v in enumerate(SCORES[i]):
            x = lpad + j * cw
            cy2 = tpad + i * ch
            col = cell_color(v)
            parts.append(f'<rect x="{x+2}" y="{cy2+2}" width="{cw-4}" height="{ch-4}" fill="{col}" rx="4" opacity="0.85"/>')
            parts.append(f'<text x="{x + cw//2}" y="{cy2 + ch//2 + 5}" fill="white" font-size="11" text-anchor="middle" font-family="monospace">{v}</text>')
    parts.append('</svg>')
    return ''.join(parts)

def build_trend():
    W, H = 520, 200
    lpad, rpad, tpad, bpad = 50, 20, 20, 40
    months = ["Jan", "Feb", "Mar"]
    iW = W - lpad - rpad
    iH = H - tpad - bpad
    parts = [f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg">']
    parts.append(f'<rect width="{W}" height="{H}" fill="#1e293b" rx="8"/>')
    for gi in range(5):
        yv = 1.0 + gi
        gy = tpad + iH - int((yv / 5.0) * iH)
        parts.append(f'<line x1="{lpad}" y1="{gy}" x2="{W-rpad}" y2="{gy}" stroke="#334155" stroke-width="1"/>')
        parts.append(f'<text x="{lpad-4}" y="{gy+4}" fill="#64748b" font-size="10" text-anchor="end" font-family="monospace">{yv:.0f}</text>')
    for xi, m in enumerate(months):
        x = lpad + int(xi / (len(months) - 1) * iW)
        parts.append(f'<text x="{x}" y="{H - 10}" fill="#94a3b8" font-size="11" text-anchor="middle" font-family="monospace">{m}</text>')
    for i, partner in enumerate(PARTNERS):
        pts = []
        for xi, v in enumerate(TREND[i]):
            x = lpad + int(xi / (len(months) - 1) * iW)
            y = tpad + iH - int((v / 5.0) * iH)
            pts.append((x, y))
        path = " ".join(f"{'M' if k == 0 else 'L'}{px},{py}" for k, (px, py) in enumerate(pts))
        parts.append(f'<path d="{path}" stroke="{COLORS[i]}" stroke-width="2.5" fill="none"/>')
        for px, py in pts:
            parts.append(f'<circle cx="{px}" cy="{py}" r="4" fill="{COLORS[i]}"/>')
        parts.append(f'<text x="{pts[-1][0]+6}" y="{pts[-1][1]+4}" fill="{COLORS[i]}" font-size="10" font-family="monospace">{partner}</text>')
    parts.append('</svg>')
    return ''.join(parts)

def build_html():
    heatmap = build_heatmap()
    trend = build_trend()
    avgs = [round(sum(row)/len(row), 1) for row in SCORES]
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>Partner Health Report</title>
<style>body{{background:#0f172a;color:#e2e8f0;font-family:monospace;margin:0;padding:24px}}
h1{{color:#C74634;margin-bottom:4px}}h2{{color:#38bdf8;font-size:14px;margin:20px 0 8px}}
.stats{{display:flex;gap:16px;flex-wrap:wrap;margin-bottom:16px}}
.stat{{background:#1e293b;border-radius:8px;padding:12px 18px;min-width:160px}}
.stat .label{{color:#64748b;font-size:11px}}.stat .val{{color:#f1f5f9;font-size:18px;font-weight:bold}}
.badge-ex{{color:#16a34a}}.badge-risk{{color:#dc2626}}.badge-stable{{color:#d97706}}
svg{{max-width:100%;display:block}}</style></head><body>
<h1>Partner Health Report</h1>
<p style="color:#64748b;font-size:12px">Comprehensive health reporting for design partners — port {PORT}</p>
<div class="stats">
  <div class="stat"><div class="label">PI Health</div><div class="val badge-ex">4.6/5 EXCELLENT</div><div class="label">Flagged for expansion</div></div>
  <div class="stat"><div class="label">1X Health</div><div class="val badge-risk">2.4/5 AT_RISK</div><div class="label">Churn risk — CSM escalate</div></div>
  <div class="stat"><div class="label">Covariant</div><div class="val badge-stable">3.8/5 STABLE</div><div class="label">On track</div></div>
  <div class="stat"><div class="label">Portfolio Average</div><div class="val">3.6/5</div><div class="label">2 CSM escalations recommended</div></div>
</div>
<h2>5-Partner × 7-Metric Health Heatmap</h2>
{heatmap}
<h2>Monthly Health Trend (Jan–Mar 2026)</h2>
{trend}
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Partner Health Report")
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
