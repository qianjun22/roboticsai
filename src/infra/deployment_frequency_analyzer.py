"""
OCI Robot Cloud — Deployment Frequency Analyzer
Port 8656 | Dark theme (#0f172a / #C74634 / #38bdf8) | stdlib only
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

import math
import random

# ── reproducible sample data ──────────────────────────────────────────────────
random.seed(42)

# 91-day heatmap: generate deploy counts per day (13 weeks × 7 days)
_HEATMAP = []
for week in range(13):
    row = []
    for day in range(7):
        # more recent weeks have higher activity
        base = 0.3 + week * 0.055
        val = max(0, min(6, round(random.gauss(base * 4, 0.8))))
        row.append(val)
    _HEATMAP.append(row)

# Deployment size histogram buckets
_SIZE_BUCKETS = [
    ("1\u20132 files",  60),
    ("3\u20135 files",  30),
    ("6\u201310 files",  8),
    ("11+ files",   2),
]

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Deployment Frequency Analyzer | OCI Robot Cloud</title>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',system-ui,sans-serif;min-height:100vh;padding:2rem}
  h1{color:#38bdf8;font-size:1.6rem;margin-bottom:.25rem}
  .subtitle{color:#94a3b8;font-size:.9rem;margin-bottom:2rem}
  .grid{display:grid;grid-template-columns:1fr 1fr;gap:1.5rem}
  .card{background:#1e293b;border-radius:12px;padding:1.5rem;border:1px solid #334155}
  .card-wide{grid-column:span 2}
  .card h2{color:#C74634;font-size:1rem;margin-bottom:1rem;text-transform:uppercase;letter-spacing:.08em}
  svg text{font-family:'Segoe UI',system-ui,sans-serif}
  .badge{display:inline-block;background:#0f172a;border:1px solid #38bdf8;color:#38bdf8;
         border-radius:999px;padding:.2rem .75rem;font-size:.78rem;margin:.2rem}
  .badge.ok{border-color:#22c55e;color:#22c55e}
  footer{text-align:center;color:#475569;font-size:.78rem;margin-top:2.5rem}
</style>
</head>
<body>
<h1>Deployment Frequency Analyzer</h1>
<p class="subtitle">OCI Robot Cloud \u2014 DORA metrics dashboard &nbsp;|&nbsp; Port 8656</p>

<div style="margin-bottom:1.5rem">
  <span class="badge">3.8 deploys/week \u25b2</span>
  <span class="badge ok">4.2 hr lead time \u2713</span>
  <span class="badge ok">4.7% change-fail &lt;5% \u2713</span>
  <span class="badge ok">100% zero-downtime \u2713</span>
</div>

<div class="grid">

  <!-- ── Card 1: Calendar heatmap ─────────────────────────────────── -->
  <div class="card card-wide">
    <h2>Deployment Calendar \u2014 Last 13 Weeks</h2>
    {HEATMAP_SVG}
  </div>

  <!-- ── Card 2: DORA 4-panel ──────────────────────────────────────── -->
  <div class="card">
    <h2>DORA Metrics</h2>
    {DORA_SVG}
  </div>

  <!-- ── Card 3: Deployment size histogram ─────────────────────────── -->
  <div class="card">
    <h2>Deployment Size Distribution</h2>
    {HIST_SVG}
  </div>

</div>
<footer>OCI Robot Cloud \u00b7 Deployment Frequency Analyzer \u00b7 cycle-149B</footer>
</body>
</html>"""


# ── SVG generators ─────────────────────────────────────────────────────────────

def _heatmap_svg(data):
    cell = 16
    gap = 3
    cols = len(data)       # 13 weeks
    rows = 7               # days
    pad_left = 34
    pad_top  = 28
    w = pad_left + cols * (cell + gap) + 20
    h = pad_top  + rows * (cell + gap) + 28

    day_labels = ["Sun","Mon","Tue","Wed","Thu","Fri","Sat"]
    # color stops: 0 → #1e293b, 1 → faint, 2 → medium, 3+ → bright
    def color(v):
        if v == 0: return "#1e293b"
        if v == 1: return "#0e4c6a"
        if v == 2: return "#0e7490"
        if v == 3: return "#0284c7"
        if v == 4: return "#38bdf8"
        return "#7dd3fc"

    parts = [f'<svg viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:auto">']

    # day-of-week labels
    for r, lbl in enumerate(day_labels):
        y = pad_top + r * (cell + gap) + cell * 0.7
        parts.append(f'<text x="{pad_left - 6}" y="{y}" text-anchor="end" font-size="9" fill="#64748b">{lbl}</text>')

    # week labels (every 2 weeks)
    for c in range(0, cols, 2):
        x = pad_left + c * (cell + gap) + cell * 0.5
        wk = cols - c
        parts.append(f'<text x="{x}" y="{pad_top - 8}" text-anchor="middle" font-size="9" fill="#64748b">-{wk}w</text>')

    # cells
    for c, week in enumerate(data):
        for r, val in enumerate(week):
            x = pad_left + c * (cell + gap)
            y = pad_top  + r * (cell + gap)
            clr = color(val)
            parts.append(f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="3" fill="{clr}"/>')
            if val > 0:
                tx, ty = x + cell/2, y + cell/2 + 3.5
                parts.append(f'<text x="{tx}" y="{ty}" text-anchor="middle" font-size="8" fill="#e2e8f0">{val}</text>')

    # legend
    lx = pad_left
    ly = h - 14
    parts.append(f'<text x="{lx}" y="{ly + 9}" font-size="9" fill="#64748b">Deploys/day:</text>')
    for i, (label, clr) in enumerate([(0,"#1e293b"),(1,"#0e4c6a"),(2,"#0284c7"),(4,"#38bdf8"),(6,"#7dd3fc")]):
        rx = lx + 75 + i * 22
        parts.append(f'<rect x="{rx}" y="{ly}" width="{cell}" height="{cell}" rx="3" fill="{clr}"/>')
        parts.append(f'<text x="{rx + cell/2}" y="{ly + cell/2 + 3.5}" text-anchor="middle" font-size="8" fill="#e2e8f0">{label}</text>')

    parts.append("</svg>")
    return "".join(parts)


def _dora_svg():
    W, H = 520, 200
    panels = [
        ("Deploy Freq",  "3.8/wk",  "\u25b2 +280%", "#38bdf8"),
        ("Lead Time",    "4.2 hr",  "\u25bc \u221250%",  "#22c55e"),
        ("MTTR",         "8 min",   "\u25bc \u221240%",  "#22c55e"),
        ("Change Fail",  "4.7%",    "\u25bc <5% \u2713", "#22c55e"),
    ]
    pw = W / len(panels)
    parts = [f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:auto">']

    for i, (title, val, trend, clr) in enumerate(panels):
        x = i * pw
        cx = x + pw / 2

        # panel bg
        parts.append(f'<rect x="{x+4}" y="4" width="{pw-8}" height="{H-8}" rx="10" fill="#0f172a"/>')

        # gauge arc (semicircle)
        r = 44
        gx, gy = cx, 100
        # background arc
        parts.append(f'<path d="M {gx-r} {gy} A {r} {r} 0 0 1 {gx+r} {gy}" stroke="#334155" stroke-width="8" fill="none"/>')
        # fill arc — map to 0..1 based on panel
        pcts = [0.76, 0.50, 0.87, 0.93]
        pct = pcts[i]
        end_x = gx + r * math.cos(math.pi * (1 - pct))
        end_y = gy - r * math.sin(math.pi * pct)
        large = 1 if pct > 0.5 else 0
        parts.append(f'<path d="M {gx-r} {gy} A {r} {r} 0 {large} 1 {end_x:.1f} {end_y:.1f}" '
                     f'stroke="{clr}" stroke-width="8" fill="none" stroke-linecap="round"/>')

        # value text
        parts.append(f'<text x="{cx}" y="{gy + 6}" text-anchor="middle" font-size="18" font-weight="700" fill="{clr}">{val}</text>')
        parts.append(f'<text x="{cx}" y="{gy + 24}" text-anchor="middle" font-size="10" fill="#94a3b8">{trend}</text>')
        parts.append(f'<text x="{cx}" y="162" text-anchor="middle" font-size="11" fill="#cbd5e1">{title}</text>')

    parts.append("</svg>")
    return "".join(parts)


def _histogram_svg(buckets):
    W, H = 420, 210
    pad_l, pad_b, pad_t, pad_r = 44, 40, 20, 20
    chart_w = W - pad_l - pad_r
    chart_h = H - pad_b - pad_t

    max_val = max(v for _, v in buckets)
    bw = chart_w / len(buckets)
    bar_w = bw * 0.6
    colors = ["#38bdf8", "#0284c7", "#0e4c6a", "#1e293b"]

    parts = [f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:auto">']

    # grid lines
    for pct in [0, 25, 50, 75, 100]:
        y = pad_t + chart_h * (1 - pct / 100)
        parts.append(f'<line x1="{pad_l}" y1="{y:.1f}" x2="{pad_l + chart_w}" y2="{y:.1f}" '
                     f'stroke="#334155" stroke-width="1" stroke-dasharray="4,3"/>')
        parts.append(f'<text x="{pad_l - 5}" y="{y + 4:.1f}" text-anchor="end" font-size="9" fill="#64748b">{pct}%</text>')

    # bars
    for i, (label, val) in enumerate(buckets):
        bh = chart_h * val / 100
        x  = pad_l + i * bw + (bw - bar_w) / 2
        y  = pad_t + chart_h - bh
        clr = colors[i % len(colors)]
        parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{bh:.1f}" rx="4" fill="{clr}"/>')
        # value label
        parts.append(f'<text x="{x + bar_w/2:.1f}" y="{y - 5:.1f}" text-anchor="middle" font-size="11" font-weight="600" fill="#e2e8f0">{val}%</text>')
        # x label
        lx = pad_l + i * bw + bw / 2
        parts.append(f'<text x="{lx:.1f}" y="{pad_t + chart_h + 16}" text-anchor="middle" font-size="10" fill="#94a3b8">{label}</text>')

    # axes
    parts.append(f'<line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t + chart_h}" stroke="#475569" stroke-width="1.5"/>')
    parts.append(f'<line x1="{pad_l}" y1="{pad_t + chart_h}" x2="{pad_l + chart_w}" y2="{pad_t + chart_h}" stroke="#475569" stroke-width="1.5"/>')

    # axis title
    parts.append(f'<text x="{pad_l + chart_w / 2}" y="{H - 2}" text-anchor="middle" font-size="10" fill="#64748b">Files changed per deployment</text>')

    parts.append("</svg>")
    return "".join(parts)


def _render_html():
    html = HTML
    html = html.replace("{HEATMAP_SVG}", _heatmap_svg(_HEATMAP))
    html = html.replace("{DORA_SVG}",    _dora_svg())
    html = html.replace("{HIST_SVG}",    _histogram_svg(_SIZE_BUCKETS))
    return html


# ── FastAPI app ───────────────────────────────────────────────────────────────
if USE_FASTAPI:
    app = FastAPI(title="Deployment Frequency Analyzer", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def index():
        return _render_html()

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "deployment_frequency_analyzer", "port": 8656}


# ── stdlib fallback ───────────────────────────────────────────────────────────
def _stdlib_server():
    from http.server import BaseHTTPRequestHandler, HTTPServer
    import json

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass

        def _send(self, code, ctype, body):
            b = body.encode() if isinstance(body, str) else body
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)

        def do_GET(self):
            if self.path == "/health":
                self._send(200, "application/json",
                           json.dumps({"status": "ok", "service": "deployment_frequency_analyzer", "port": 8656}))
            else:
                self._send(200, "text/html; charset=utf-8", _render_html())

    server = HTTPServer(("0.0.0.0", 8656), Handler)
    print("Deployment Frequency Analyzer running on http://0.0.0.0:8656 (stdlib fallback)")
    server.serve_forever()


if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run("deployment_frequency_analyzer:app", host="0.0.0.0", port=8656, reload=False)
    else:
        _stdlib_server()
