"""
Wrist Camera Calibrator — port 8660
OCI Robot Cloud | cycle-150B
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

# ── SVG helpers ────────────────────────────────────────────────────────────────

def svg_reprojection_scatter() -> str:
    random.seed(42)
    dots = []
    for i in range(50):
        x = random.uniform(30, 610)
        y = random.uniform(30, 450)
        err = abs(random.gauss(0.28, 0.18))
        if err < 0.3:
            color = "#22c55e"
        elif err < 0.8:
            color = "#facc15"
        else:
            color = "#ef4444"
        r = 4 + err * 3
        dots.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" fill="{color}" fill-opacity="0.82" stroke="#0f172a" stroke-width="0.8"/>')

    dots_svg = "\n    ".join(dots)

    return f"""<svg viewBox="0 0 680 520" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:680px;background:#1e293b;border-radius:10px;">
  <!-- title -->
  <text x="340" y="30" text-anchor="middle" fill="#e2e8f0" font-size="15" font-weight="bold" font-family="monospace">Reprojection Error Scatter — 50 Checkerboard Corners</text>
  <!-- axes background -->
  <rect x="50" y="45" width="610" height="450" fill="#0f172a" rx="4"/>
  <!-- grid lines -->
  {"".join(f'<line x1="50" y1="{45+i*90}" x2="660" y2="{45+i*90}" stroke="#334155" stroke-width="0.7"/>' for i in range(6))}
  {"".join(f'<line x1="{50+i*122}" y1="45" x2="{50+i*122}" y2="495" stroke="#334155" stroke-width="0.7"/>' for i in range(6))}
  <!-- axis labels -->
  <text x="355" y="514" text-anchor="middle" fill="#94a3b8" font-size="11" font-family="monospace">Image X (px)</text>
  <text x="14" y="270" text-anchor="middle" fill="#94a3b8" font-size="11" font-family="monospace" transform="rotate(-90,14,270)">Image Y (px)</text>
  <!-- x ticks -->
  {"".join(f'<text x="{50+i*122}" y="509" text-anchor="middle" fill="#64748b" font-size="10" font-family="monospace">{i*128}</text>' for i in range(6))}
  <!-- y ticks -->
  {"".join(f'<text x="44" y="{50+i*90}" text-anchor="end" fill="#64748b" font-size="10" font-family="monospace">{480-i*96}</text>' for i in range(6))}
  <!-- dots -->
  {dots_svg}
  <!-- RMS label -->
  <rect x="480" y="52" width="170" height="28" fill="#1e293b" rx="4" stroke="#38bdf8" stroke-width="1"/>
  <text x="565" y="71" text-anchor="middle" fill="#38bdf8" font-size="12" font-weight="bold" font-family="monospace">RMS = 0.31 px ✓ excellent</text>
  <!-- legend -->
  <circle cx="60" cy="60" r="5" fill="#22c55e"/>
  <text x="70" y="64" fill="#94a3b8" font-size="10" font-family="monospace"> &lt;0.3px</text>
  <circle cx="105" cy="60" r="5" fill="#facc15"/>
  <text x="115" y="64" fill="#94a3b8" font-size="10" font-family="monospace"> &lt;0.8px</text>
  <circle cx="150" cy="60" r="5" fill="#ef4444"/>
  <text x="160" y="64" fill="#94a3b8" font-size="10" font-family="monospace"> &gt;0.8px</text>
</svg>"""


def svg_drift_timeline() -> str:
    random.seed(7)
    days = list(range(30))
    drifts = [round(0.02 + random.uniform(0, 0.06) + (0.001 * d), 4) for d in days]
    # clamp
    drifts = [min(d, 0.079) for d in drifts]

    W, H = 680, 340
    pad_l, pad_r, pad_t, pad_b = 60, 20, 40, 50
    plot_w = W - pad_l - pad_r
    plot_h = H - pad_t - pad_b

    def tx(d): return pad_l + d / 29 * plot_w
    def ty(v): return pad_t + (0.10 - v) / 0.10 * plot_h

    pts = " ".join(f"{tx(d):.1f},{ty(v):.1f}" for d, v in zip(days, drifts))
    threshold_y = ty(0.08)
    last_cal_x = tx(16)

    lines_h = "".join(f'<line x1="{pad_l}" y1="{ty(v):.1f}" x2="{W-pad_r}" y2="{ty(v):.1f}" stroke="#334155" stroke-width="0.7"/>' for v in [0.02, 0.04, 0.06, 0.08, 0.10])
    x_ticks = "".join(f'<text x="{tx(d):.1f}" y="{H-pad_b+14}" text-anchor="middle" fill="#64748b" font-size="9" font-family="monospace">D{d}</text>' for d in range(0, 30, 5))
    y_ticks = "".join(f'<text x="{pad_l-6}" y="{ty(v):.1f}" text-anchor="end" fill="#64748b" font-size="9" font-family="monospace">{v:.2f}</text>' for v in [0.02, 0.04, 0.06, 0.08, 0.10])

    return f"""<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:{W}px;background:#1e293b;border-radius:10px;">
  <text x="{W//2}" y="24" text-anchor="middle" fill="#e2e8f0" font-size="15" font-weight="bold" font-family="monospace">Camera Drift — 30-Day Timeline</text>
  <rect x="{pad_l}" y="{pad_t}" width="{plot_w}" height="{plot_h}" fill="#0f172a" rx="4"/>
  {lines_h}
  {x_ticks}
  {y_ticks}
  <!-- drift threshold -->
  <line x1="{pad_l}" y1="{threshold_y:.1f}" x2="{W-pad_r}" y2="{threshold_y:.1f}" stroke="#ef4444" stroke-width="1.5" stroke-dasharray="6,4"/>
  <text x="{W-pad_r-2}" y="{threshold_y-5:.1f}" text-anchor="end" fill="#ef4444" font-size="10" font-family="monospace">recal. threshold 0.08px</text>
  <!-- last calibration marker -->
  <line x1="{last_cal_x:.1f}" y1="{pad_t}" x2="{last_cal_x:.1f}" y2="{pad_t+plot_h}" stroke="#C74634" stroke-width="1.5" stroke-dasharray="4,3"/>
  <text x="{last_cal_x+3:.1f}" y="{pad_t+14}" fill="#C74634" font-size="9" font-family="monospace">last cal. D16</text>
  <!-- drift line -->
  <polyline points="{pts}" fill="none" stroke="#38bdf8" stroke-width="2.2" stroke-linejoin="round"/>
  <!-- dots -->
  {"".join(f'<circle cx="{tx(d):.1f}" cy="{ty(v):.1f}" r="3" fill="#38bdf8"/>' for d, v in zip(days, drifts))}
  <!-- axis labels -->
  <text x="{pad_l + plot_w//2}" y="{H-4}" text-anchor="middle" fill="#94a3b8" font-size="11" font-family="monospace">Day</text>
  <text x="12" y="{pad_t + plot_h//2}" text-anchor="middle" fill="#94a3b8" font-size="11" font-family="monospace" transform="rotate(-90,12,{pad_t + plot_h//2})">Drift (px/day)</text>
  <!-- annotation -->
  <rect x="420" y="48" width="230" height="22" fill="#1e293b" rx="4" stroke="#22c55e" stroke-width="1"/>
  <text x="535" y="63" text-anchor="middle" fill="#22c55e" font-size="11" font-family="monospace">avg 0.04 px/day · recal every 14d</text>
</svg>"""


def svg_accuracy_comparison() -> str:
    W, H = 680, 360
    # Before/After pairs: depth_error; pick accuracy at 0.3/0.6/0.9m
    categories = ["Depth Error (mm)", "Pick Acc 0.3m", "Pick Acc 0.6m", "Pick Acc 0.9m"]
    before = [8.0, 3.4, 5.1, 7.8]
    after  = [2.1, 0.9, 1.4, 2.3]
    max_val = 10.0

    pad_l, pad_r, pad_t, pad_b = 150, 30, 50, 50
    plot_w = W - pad_l - pad_r
    plot_h = H - pad_t - pad_b

    bar_h = 28
    group_h = 72
    bar_before_color = "#C74634"
    bar_after_color  = "#22c55e"

    def bw(v): return v / max_val * plot_w

    bars = []
    for i, (cat, bv, av) in enumerate(zip(categories, before, after)):
        gy = pad_t + i * group_h
        # before bar
        bars.append(f'<rect x="{pad_l}" y="{gy+4}" width="{bw(bv):.1f}" height="{bar_h}" fill="{bar_before_color}" rx="3"/>')
        bars.append(f'<text x="{pad_l + bw(bv) + 5:.1f}" y="{gy+4+bar_h//2+4}" fill="#e2e8f0" font-size="11" font-family="monospace">{bv}</text>')
        # after bar
        bars.append(f'<rect x="{pad_l}" y="{gy+38}" width="{bw(av):.1f}" height="{bar_h}" fill="{bar_after_color}" rx="3"/>')
        bars.append(f'<text x="{pad_l + bw(av) + 5:.1f}" y="{gy+38+bar_h//2+4}" fill="#e2e8f0" font-size="11" font-family="monospace">{av}</text>')
        # category label
        bars.append(f'<text x="{pad_l-6}" y="{gy+24}" text-anchor="end" fill="#94a3b8" font-size="11" font-family="monospace">{cat}</text>')
        # separator
        if i < len(categories) - 1:
            bars.append(f'<line x1="{pad_l}" y1="{gy+group_h}" x2="{W-pad_r}" y2="{gy+group_h}" stroke="#1e293b" stroke-width="1.5"/>')

    # x-axis ticks
    x_ticks = "".join(f'<text x="{pad_l + v/max_val*plot_w:.1f}" y="{H-pad_b+14}" text-anchor="middle" fill="#64748b" font-size="9" font-family="monospace">{v:.0f}</text>' for v in [0, 2, 4, 6, 8, 10])
    grid = "".join(f'<line x1="{pad_l + v/max_val*plot_w:.1f}" y1="{pad_t}" x2="{pad_l + v/max_val*plot_w:.1f}" y2="{pad_t+plot_h}" stroke="#334155" stroke-width="0.7"/>' for v in [2, 4, 6, 8, 10])

    bars_svg = "\n  ".join(bars)

    return f"""<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:{W}px;background:#1e293b;border-radius:10px;">
  <text x="{W//2}" y="28" text-anchor="middle" fill="#e2e8f0" font-size="15" font-weight="bold" font-family="monospace">Calibration Accuracy — Before vs After</text>
  <rect x="{pad_l}" y="{pad_t}" width="{plot_w}" height="{plot_h}" fill="#0f172a" rx="4"/>
  {grid}
  {bars_svg}
  {x_ticks}
  <text x="{pad_l + plot_w//2}" y="{H-6}" text-anchor="middle" fill="#94a3b8" font-size="11" font-family="monospace">Error (mm or px)</text>
  <!-- legend -->
  <rect x="{pad_l}" y="34" width="14" height="10" fill="{bar_before_color}" rx="2"/>
  <text x="{pad_l+18}" y="43" fill="#94a3b8" font-size="11" font-family="monospace">Before</text>
  <rect x="{pad_l+80}" y="34" width="14" height="10" fill="{bar_after_color}" rx="2"/>
  <text x="{pad_l+98}" y="43" fill="#94a3b8" font-size="11" font-family="monospace">After</text>
</svg>"""


# ── HTML page ──────────────────────────────────────────────────────────────────

def build_html() -> str:
    scatter = svg_reprojection_scatter()
    drift   = svg_drift_timeline()
    compare = svg_accuracy_comparison()

    metrics = [
        ("RMS Reprojection", "0.31 px", "excellent", "#22c55e"),
        ("Drift Rate",       "0.04 px/day", "stable",    "#38bdf8"),
        ("Recal Interval",   "14 days", "recommended", "#facc15"),
        ("Depth Improvement","8 mm → 2.1 mm", "−74%",  "#C74634"),
    ]

    metric_cards = "".join(f"""
      <div style="background:#1e293b;border:1px solid #334155;border-radius:8px;padding:16px 20px;min-width:160px;flex:1;">
        <div style="color:#64748b;font-size:11px;margin-bottom:4px;">{m[0]}</div>
        <div style="color:#e2e8f0;font-size:22px;font-weight:bold;">{m[1]}</div>
        <div style="color:{m[3]};font-size:12px;margin-top:2px;">{m[2]}</div>
      </div>""" for m in metrics)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Wrist Camera Calibrator — OCI Robot Cloud</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0;}}
  body{{background:#0f172a;color:#e2e8f0;font-family:'Courier New',monospace;padding:24px;}}
  h1{{font-size:22px;color:#38bdf8;margin-bottom:4px;}}
  .subtitle{{color:#64748b;font-size:13px;margin-bottom:24px;}}
  .metrics{{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:28px;}}
  .chart-block{{background:#1e293b;border:1px solid #334155;border-radius:10px;padding:20px;margin-bottom:20px;}}
  .chart-title{{color:#94a3b8;font-size:13px;margin-bottom:12px;letter-spacing:.05em;text-transform:uppercase;}}
  .badge{{display:inline-block;background:#C74634;color:#fff;font-size:11px;padding:2px 8px;border-radius:4px;margin-left:8px;vertical-align:middle;}}
</style>
</head>
<body>
<h1>Wrist Camera Calibrator <span class="badge">port 8660</span></h1>
<div class="subtitle">OCI Robot Cloud · cycle-150B · intrinsic + extrinsic calibration pipeline</div>

<div class="metrics">
  {metric_cards}
</div>

<div class="chart-block">
  <div class="chart-title">Reprojection Error Scatter</div>
  {scatter}
</div>

<div class="chart-block">
  <div class="chart-title">Camera Drift — 30-Day Timeline</div>
  {drift}
</div>

<div class="chart-block">
  <div class="chart-title">Calibration Accuracy Comparison</div>
  {compare}
</div>

<div style="color:#334155;font-size:11px;margin-top:16px;text-align:center;">
  OCI Robot Cloud · Wrist Camera Calibrator · port 8660 · stdlib-only fallback supported
</div>
</body>
</html>"""


# ── App ────────────────────────────────────────────────────────────────────────

if USE_FASTAPI:
    app = FastAPI(title="Wrist Camera Calibrator", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return build_html()

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "wrist_camera_calibrator", "port": 8660}

    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=8660)

else:
    from http.server import HTTPServer, BaseHTTPRequestHandler

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a): pass
        def do_GET(self):
            if self.path == "/health":
                body = b'{"status":"ok","service":"wrist_camera_calibrator","port":8660}'
                ct = b"application/json"
            else:
                body = build_html().encode()
                ct = b"text/html"
            self.send_response(200)
            self.send_header("Content-Type", ct.decode())
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    if __name__ == "__main__":
        srv = HTTPServer(("0.0.0.0", 8660), Handler)
        print("Wrist Camera Calibrator running on port 8660 (stdlib)")
        srv.serve_forever()
