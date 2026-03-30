"""
OCI Robot Cloud — Contact Localization Tracker
Port 8657 | Dark theme (#0f172a / #C74634 / #38bdf8) | stdlib only
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
random.seed(7)

def _gauss2d(cx, cy, sx, sy):
    return (cx + random.gauss(0, sx), cy + random.gauss(0, sy))

# 30 contact position data points
# BC: centre offset ~(2.5, 2.5) mm, std ~3.5 mm
# DAgger: centre offset ~(0.5, 0.5) mm, std ~1.8 mm
BC_POINTS   = [_gauss2d(2.5,  2.5,  3.5, 3.5)  for _ in range(15)]
DAG_POINTS  = [_gauss2d(0.5,  0.5,  1.8, 1.8)  for _ in range(15)]

# Timing histogram: BC mean=142 std=28, DAgger mean=121 std=14
BC_TIMING   = [max(60, min(220, round(random.gauss(142, 28)))) for _ in range(80)]
DAG_TIMING  = [max(60, min(220, round(random.gauss(121, 14)))) for _ in range(80)]

# Force profile 200 steps
random.seed(13)
def _bc_force(t):
    return 8 + random.gauss(0, 2.2) + 1.5 * math.sin(t * 0.15)

def _dag_force(t):
    return 8 + random.gauss(0, 0.9) + 0.6 * math.sin(t * 0.12)

BC_FORCE  = [_bc_force(t)  for t in range(200)]
DAG_FORCE = [_dag_force(t) for t in range(200)]

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Contact Localization Tracker | OCI Robot Cloud</title>
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
  .legend{display:flex;gap:1.2rem;margin-top:.75rem;font-size:.82rem}
  .dot{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:.3rem}
  footer{text-align:center;color:#475569;font-size:.78rem;margin-top:2.5rem}
</style>
</head>
<body>
<h1>Contact Localization Tracker</h1>
<p class="subtitle">OCI Robot Cloud \u2014 BC vs DAgger contact precision &nbsp;|&nbsp; Port 8657</p>

<div style="margin-bottom:1.5rem">
  <span class="badge ok">DAgger 3.8 mm vs BC 7.1 mm \u25bc46%</span>
  <span class="badge ok">DAgger timing 14% tighter</span>
  <span class="badge ok">False contact BC 12% \u2192 DAgger 3%</span>
</div>

<div class="grid">

  <!-- ── Card 1: scatter ───────────────────────────────────────────── -->
  <div class="card">
    <h2>Contact Position Scatter (mm offset from target)</h2>
    {SCATTER_SVG}
    <div class="legend">
      <span><span class="dot" style="background:#C74634"></span>BC (\u03c3\u22483.5mm)</span>
      <span><span class="dot" style="background:#38bdf8"></span>DAgger (\u03c3\u22481.8mm)</span>
      <span><span class="dot" style="background:#22c55e;border-radius:0;width:12px;height:2px;display:inline-block;vertical-align:middle;margin-right:.3rem"></span>5/10mm rings</span>
    </div>
  </div>

  <!-- ── Card 2: timing histogram ──────────────────────────────────── -->
  <div class="card">
    <h2>Contact Timing Distribution (step at first contact)</h2>
    {TIMING_SVG}
    <div class="legend">
      <span><span class="dot" style="background:#C74634"></span>BC \u03bc=142</span>
      <span><span class="dot" style="background:#38bdf8"></span>DAgger \u03bc=121</span>
    </div>
  </div>

  <!-- ── Card 3: force profile ─────────────────────────────────────── -->
  <div class="card card-wide">
    <h2>Contact Force Profile \u2014 Fz over 200 Steps</h2>
    {FORCE_SVG}
    <div class="legend">
      <span><span class="dot" style="background:#22c55e;border-radius:0;width:14px;height:3px;display:inline-block;vertical-align:middle;margin-right:.3rem"></span>Target 8 N band</span>
      <span><span class="dot" style="background:#C74634"></span>BC (noisy)</span>
      <span><span class="dot" style="background:#38bdf8"></span>DAgger (smooth)</span>
    </div>
  </div>

</div>
<footer>OCI Robot Cloud \u00b7 Contact Localization Tracker \u00b7 cycle-149B</footer>
</body>
</html>"""


# ── SVG generators ─────────────────────────────────────────────────────────────

def _scatter_svg(bc_pts, dag_pts):
    W, H = 380, 320
    cx, cy = W / 2, H / 2
    scale = 14   # pixels per mm

    parts = [f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:auto">']

    # grid
    for r_mm in [5, 10]:
        r_px = r_mm * scale
        clr  = "#22c55e" if r_mm == 5 else "#0e4c6a"
        parts.append(f'<circle cx="{cx}" cy="{cy}" r="{r_px}" fill="none" stroke="{clr}" '
                     f'stroke-width="1.2" stroke-dasharray="5,3"/>')
        parts.append(f'<text x="{cx + r_px + 3}" y="{cy + 4}" font-size="9" fill="{clr}">{r_mm}mm</text>')

    # crosshair
    parts.append(f'<line x1="{cx-12}" y1="{cy}" x2="{cx+12}" y2="{cy}" stroke="#475569" stroke-width="1"/>')
    parts.append(f'<line x1="{cx}" y1="{cy-12}" x2="{cx}" y2="{cy+12}" stroke="#475569" stroke-width="1"/>')

    # outer ring (15mm)
    parts.append(f'<circle cx="{cx}" cy="{cy}" r="{15*scale}" fill="none" stroke="#1e293b" stroke-width="1"/>')

    # BC points
    for px, py in bc_pts:
        sx = cx + px * scale
        sy = cy - py * scale
        parts.append(f'<circle cx="{sx:.1f}" cy="{sy:.1f}" r="5" fill="#C74634" fill-opacity="0.75" stroke="#f87171" stroke-width="0.8"/>')

    # DAgger points
    for px, py in dag_pts:
        sx = cx + px * scale
        sy = cy - py * scale
        parts.append(f'<circle cx="{sx:.1f}" cy="{sy:.1f}" r="5" fill="#38bdf8" fill-opacity="0.75" stroke="#7dd3fc" stroke-width="0.8"/>')

    # target
    parts.append(f'<circle cx="{cx}" cy="{cy}" r="4" fill="#fbbf24" stroke="#fde68a" stroke-width="1"/>')
    parts.append(f'<text x="{cx + 7}" y="{cy - 6}" font-size="9" fill="#fde68a">target</text>')

    parts.append("</svg>")
    return "".join(parts)


def _timing_svg(bc_t, dag_t):
    W, H = 400, 220
    pad_l, pad_b, pad_t, pad_r = 38, 38, 16, 16
    chart_w = W - pad_l - pad_r
    chart_h = H - pad_b - pad_t

    # bin into 10-step buckets 60..220
    bins = list(range(60, 221, 10))
    def _hist(data, bins):
        counts = [0] * (len(bins) - 1)
        for v in data:
            for i in range(len(bins)-1):
                if bins[i] <= v < bins[i+1]:
                    counts[i] += 1
                    break
        return counts

    bc_h  = _hist(bc_t,  bins)
    dag_h = _hist(dag_t, bins)
    max_c = max(max(bc_h), max(dag_h), 1)
    nb    = len(bc_h)
    bw    = chart_w / nb

    parts = [f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:auto">']

    # grid
    for pct in [0, 25, 50, 75, 100]:
        y = pad_t + chart_h * (1 - pct / 100)
        parts.append(f'<line x1="{pad_l}" y1="{y:.1f}" x2="{pad_l+chart_w}" y2="{y:.1f}" '
                     f'stroke="#334155" stroke-width="1" stroke-dasharray="4,3"/>')

    # BC bars (behind)
    for i, c in enumerate(bc_h):
        bh = chart_h * c / max_c
        x  = pad_l + i * bw + bw * 0.1
        y  = pad_t + chart_h - bh
        parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw*0.8:.1f}" height="{bh:.1f}" '
                     f'fill="#C74634" fill-opacity="0.55" rx="2"/>')

    # DAgger bars (in front, narrower)
    for i, c in enumerate(dag_h):
        bh = chart_h * c / max_c
        x  = pad_l + i * bw + bw * 0.25
        y  = pad_t + chart_h - bh
        parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw*0.5:.1f}" height="{bh:.1f}" '
                     f'fill="#38bdf8" fill-opacity="0.75" rx="2"/>')

    # mean lines
    def _mean_x(data):
        m = sum(data) / len(data)
        return pad_l + (m - bins[0]) / (bins[-1] - bins[0]) * chart_w

    for val, clr, lbl in [(_mean_x(bc_t), "#f87171", "BC \u03bc=142"), (_mean_x(dag_t), "#7dd3fc", "DAgger \u03bc=121")]:
        parts.append(f'<line x1="{val:.1f}" y1="{pad_t}" x2="{val:.1f}" y2="{pad_t+chart_h}" '
                     f'stroke="{clr}" stroke-width="1.5" stroke-dasharray="6,3"/>')
        parts.append(f'<text x="{val+4:.1f}" y="{pad_t+14}" font-size="9" fill="{clr}">{lbl}</text>')

    # axes
    parts.append(f'<line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t+chart_h}" stroke="#475569" stroke-width="1.5"/>')
    parts.append(f'<line x1="{pad_l}" y1="{pad_t+chart_h}" x2="{pad_l+chart_w}" y2="{pad_t+chart_h}" stroke="#475569" stroke-width="1.5"/>')

    # x tick labels
    for tick in [60, 90, 120, 150, 180, 210]:
        tx = pad_l + (tick - bins[0]) / (bins[-1] - bins[0]) * chart_w
        parts.append(f'<text x="{tx:.1f}" y="{pad_t+chart_h+13}" text-anchor="middle" font-size="9" fill="#64748b">{tick}</text>')

    parts.append(f'<text x="{pad_l+chart_w/2}" y="{H-4}" text-anchor="middle" font-size="10" fill="#64748b">Step at first contact</text>')
    parts.append("</svg>")
    return "".join(parts)


def _force_svg(bc_f, dag_f):
    W, H = 700, 220
    pad_l, pad_b, pad_t, pad_r = 44, 36, 16, 16
    chart_w = W - pad_l - pad_r
    chart_h = H - pad_b - pad_t
    n = len(bc_f)

    f_min, f_max = 0, 16
    def _fy(v):
        return pad_t + chart_h * (1 - (v - f_min) / (f_max - f_min))

    def _fx(i):
        return pad_l + i / (n - 1) * chart_w

    parts = [f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:auto">']

    # target band 7-9 N
    y_top = _fy(9)
    y_bot = _fy(7)
    parts.append(f'<rect x="{pad_l}" y="{y_top:.1f}" width="{chart_w}" height="{y_bot - y_top:.1f}" '
                 f'fill="#22c55e" fill-opacity="0.12"/>')
    parts.append(f'<line x1="{pad_l}" y1="{_fy(8):.1f}" x2="{pad_l+chart_w}" y2="{_fy(8):.1f}" '
                 f'stroke="#22c55e" stroke-width="1" stroke-dasharray="6,4"/>')
    parts.append(f'<text x="{pad_l+chart_w+3}" y="{_fy(8)+4:.1f}" font-size="9" fill="#22c55e">8N</text>')

    # grid lines
    for fv in [0, 4, 8, 12, 16]:
        y = _fy(fv)
        parts.append(f'<line x1="{pad_l}" y1="{y:.1f}" x2="{pad_l+chart_w}" y2="{y:.1f}" '
                     f'stroke="#334155" stroke-width="1" stroke-dasharray="4,3"/>')
        parts.append(f'<text x="{pad_l-5}" y="{y+4:.1f}" text-anchor="end" font-size="9" fill="#64748b">{fv}N</text>')

    # polyline builder
    def _polyline(data, clr, opacity, width):
        pts = " ".join(f"{_fx(i):.1f},{_fy(v):.1f}" for i, v in enumerate(data))
        return f'<polyline points="{pts}" fill="none" stroke="{clr}" stroke-width="{width}" stroke-opacity="{opacity}" stroke-linejoin="round"/>'

    parts.append(_polyline(bc_f,  "#C74634", 0.7, 1.4))
    parts.append(_polyline(dag_f, "#38bdf8", 0.9, 1.8))

    # axes
    parts.append(f'<line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t+chart_h}" stroke="#475569" stroke-width="1.5"/>')
    parts.append(f'<line x1="{pad_l}" y1="{pad_t+chart_h}" x2="{pad_l+chart_w}" y2="{pad_t+chart_h}" stroke="#475569" stroke-width="1.5"/>')

    # x ticks
    for step in [0, 50, 100, 150, 199]:
        tx = _fx(step)
        parts.append(f'<text x="{tx:.1f}" y="{pad_t+chart_h+13}" text-anchor="middle" font-size="9" fill="#64748b">{step}</text>')

    parts.append(f'<text x="{pad_l+chart_w/2}" y="{H-2}" text-anchor="middle" font-size="10" fill="#64748b">Step</text>')
    parts.append("</svg>")
    return "".join(parts)


def _render_html():
    html = HTML
    html = html.replace("{SCATTER_SVG}", _scatter_svg(BC_POINTS, DAG_POINTS))
    html = html.replace("{TIMING_SVG}",  _timing_svg(BC_TIMING, DAG_TIMING))
    html = html.replace("{FORCE_SVG}",   _force_svg(BC_FORCE, DAG_FORCE))
    return html


# ── FastAPI app ───────────────────────────────────────────────────────────────
if USE_FASTAPI:
    app = FastAPI(title="Contact Localization Tracker", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def index():
        return _render_html()

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "contact_localization_tracker", "port": 8657}


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
                           json.dumps({"status": "ok", "service": "contact_localization_tracker", "port": 8657}))
            else:
                self._send(200, "text/html; charset=utf-8", _render_html())

    server = HTTPServer(("0.0.0.0", 8657), Handler)
    print("Contact Localization Tracker running on http://0.0.0.0:8657 (stdlib fallback)")
    server.serve_forever()


if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run("contact_localization_tracker:app", host="0.0.0.0", port=8657, reload=False)
    else:
        _stdlib_server()
