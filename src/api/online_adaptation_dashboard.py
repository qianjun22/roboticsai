"""Online Adaptation Dashboard — FastAPI port 8688"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8688

def build_html():
    random.seed(42)

    # Generate adaptation loss curve (exponential decay + noise)
    steps = list(range(0, 501, 25))
    base_loss = [0.85 * math.exp(-s / 180) + 0.04 + random.uniform(-0.015, 0.015) for s in steps]
    adapt_loss = [0.85 * math.exp(-s / 90) + 0.02 + random.uniform(-0.01, 0.01) for s in steps]

    # SVG loss curve chart
    chart_w, chart_h = 560, 180
    pad_l, pad_r, pad_t, pad_b = 50, 20, 15, 35
    plot_w = chart_w - pad_l - pad_r
    plot_h = chart_h - pad_t - pad_b
    max_s = max(steps)
    max_loss = 0.92

    def px(s, l):
        x = pad_l + (s / max_s) * plot_w
        y = pad_t + plot_h - (l / max_loss) * plot_h
        return x, y

    def polyline(vals, color):
        pts = " ".join(f"{px(steps[i], vals[i])[0]:.1f},{px(steps[i], vals[i])[1]:.1f}" for i in range(len(steps)))
        return f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2.2"/>'

    # X-axis ticks
    xticks = ""
    for s in range(0, 501, 100):
        x, _ = px(s, 0)
        xticks += f'<line x1="{x:.1f}" y1="{pad_t+plot_h}" x2="{x:.1f}" y2="{pad_t+plot_h+4}" stroke="#475569"/>'
        xticks += f'<text x="{x:.1f}" y="{pad_t+plot_h+14}" text-anchor="middle" fill="#94a3b8" font-size="10">{s}</text>'

    # Y-axis ticks
    yticks = ""
    for l in [0.0, 0.2, 0.4, 0.6, 0.8]:
        _, y = px(0, l)
        yticks += f'<line x1="{pad_l-4}" y1="{y:.1f}" x2="{pad_l+plot_w}" y2="{y:.1f}" stroke="#1e3a5f" stroke-dasharray="4,3"/>'
        yticks += f'<text x="{pad_l-8}" y="{y+4:.1f}" text-anchor="end" fill="#94a3b8" font-size="10">{l:.1f}</text>'

    loss_svg = f"""
    <svg width="{chart_w}" height="{chart_h}" style="background:#0f2744;border-radius:6px">
      {yticks}{xticks}
      {polyline(base_loss, '#f97316')}
      {polyline(adapt_loss, '#38bdf8')}
      <text x="{pad_l}" y="12" fill="#f97316" font-size="10">● Baseline</text>
      <text x="{pad_l+80}" y="12" fill="#38bdf8" font-size="10">● Online Adapt</text>
      <text x="{chart_w//2}" y="{chart_h-2}" text-anchor="middle" fill="#64748b" font-size="10">Gradient Steps</text>
      <text x="14" y="{pad_t+plot_h//2}" text-anchor="middle" fill="#64748b" font-size="10" transform="rotate(-90,14,{pad_t+plot_h//2})">Loss</text>
    </svg>"""

    # Task success rate bar chart (8 tasks)
    tasks = ["PickPlace", "StackCube", "OpenDoor", "PourWater", "InsertPeg", "WipeDesk", "FoldCloth", "SortBins"]
    base_rates = [0.52, 0.41, 0.68, 0.35, 0.29, 0.61, 0.23, 0.47]
    adapt_rates = [0.81, 0.74, 0.89, 0.67, 0.58, 0.85, 0.49, 0.76]

    bar_w, bar_h = 560, 200
    bpad_l, bpad_r, bpad_t, bpad_b = 70, 20, 20, 50
    bplot_w = bar_w - bpad_l - bpad_r
    bplot_h = bar_h - bpad_t - bpad_b
    n = len(tasks)
    slot_w = bplot_w / n
    bar_single = slot_w * 0.35

    bars = ""
    for i, (t, br, ar) in enumerate(zip(tasks, base_rates, adapt_rates)):
        x_slot = bpad_l + i * slot_w
        bx = x_slot + slot_w * 0.08
        ax = bx + bar_single + 2
        by = bpad_t + bplot_h - br * bplot_h
        ay = bpad_t + bplot_h - ar * bplot_h
        bars += f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bar_single:.1f}" height="{br*bplot_h:.1f}" fill="#f97316" rx="2"/>'
        bars += f'<rect x="{ax:.1f}" y="{ay:.1f}" width="{bar_single:.1f}" height="{ar*bplot_h:.1f}" fill="#38bdf8" rx="2"/>'
        bars += f'<text x="{x_slot+slot_w*0.5:.1f}" y="{bpad_t+bplot_h+14}" text-anchor="middle" fill="#94a3b8" font-size="9" transform="rotate(-30,{x_slot+slot_w*0.5:.1f},{bpad_t+bplot_h+14})">{t}</text>'
        bars += f'<text x="{ax:.1f}" y="{ay-4:.1f}" fill="#38bdf8" font-size="9">{ar:.0%}</text>'

    # Y gridlines
    bgrids = ""
    for pct in [0.25, 0.5, 0.75, 1.0]:
        gy = bpad_t + bplot_h - pct * bplot_h
        bgrids += f'<line x1="{bpad_l}" y1="{gy:.1f}" x2="{bpad_l+bplot_w}" y2="{gy:.1f}" stroke="#1e3a5f" stroke-dasharray="4,3"/>'
        bgrids += f'<text x="{bpad_l-5}" y="{gy+4:.1f}" text-anchor="end" fill="#94a3b8" font-size="10">{int(pct*100)}%</text>'

    bar_svg = f"""
    <svg width="{bar_w}" height="{bar_h}" style="background:#0f2744;border-radius:6px">
      {bgrids}{bars}
      <text x="{bpad_l}" y="12" fill="#f97316" font-size="10">● Baseline</text>
      <text x="{bpad_l+60}" y="12" fill="#38bdf8" font-size="10">● Online Adapt</text>
    </svg>"""

    # Adaptation speed radar (pentagon — 5 dims)
    dims = ["Speed", "Stability", "Generality", "Sample Eff.", "Robustness"]
    scores_base = [0.55, 0.70, 0.48, 0.40, 0.62]
    scores_adapt = [0.82, 0.78, 0.74, 0.88, 0.81]
    cx, cy, r = 130, 130, 90
    n5 = 5

    def radar_pt(i, val):
        angle = math.pi / 2 + 2 * math.pi * i / n5
        return cx + val * r * math.cos(angle), cy - val * r * math.sin(angle)

    def radar_poly(scores, color, opacity):
        pts = " ".join(f"{radar_pt(i, s)[0]:.1f},{radar_pt(i, s)[1]:.1f}" for i, s in enumerate(scores))
        return (f'<polygon points="{pts}" fill="{color}" fill-opacity="{opacity}" '
                f'stroke="{color}" stroke-width="1.5"/>')

    # Concentric reference rings
    rings = ""
    for rv in [0.25, 0.5, 0.75, 1.0]:
        pts = " ".join(f"{radar_pt(i, rv)[0]:.1f},{radar_pt(i, rv)[1]:.1f}" for i in range(n5))
        rings += f'<polygon points="{pts}" fill="none" stroke="#1e3a5f" stroke-width="1"/>'

    # Axis lines and labels
    axes = ""
    for i, d in enumerate(dims):
        ox, oy = radar_pt(i, 1.05)
        ax2, ay2 = radar_pt(i, 0)
        ex, ey = radar_pt(i, 1.0)
        axes += f'<line x1="{cx}" y1="{cy}" x2="{ex:.1f}" y2="{ey:.1f}" stroke="#334155" stroke-width="1"/>'
        axes += f'<text x="{ox:.1f}" y="{oy:.1f}" text-anchor="middle" fill="#94a3b8" font-size="9">{d}</text>'

    radar_svg = f"""
    <svg width="260" height="260" style="background:#0f2744;border-radius:6px">
      {rings}{axes}
      {radar_poly(scores_base, '#f97316', 0.2)}
      {radar_poly(scores_adapt, '#38bdf8', 0.25)}
    </svg>"""

    # KPI summary stats
    kpis = [
        ("Adapt Speed", "2.3x", "faster convergence"),
        ("Avg Success", "74%", "+28pp vs baseline"),
        ("Sample Eff.", "88%", "fewer demos needed"),
        ("Latency", "11ms", "per adaptation step"),
        ("Episodes/hr", "312", "live rollout rate"),
        ("GPU Util", "91%", "A100 80GB"),
    ]
    kpi_cards = "".join(
        f'<div style="background:#1e293b;padding:14px 18px;border-radius:8px;border-left:3px solid #38bdf8">'
        f'<div style="font-size:11px;color:#64748b;margin-bottom:4px">{label}</div>'
        f'<div style="font-size:24px;font-weight:700;color:#38bdf8">{val}</div>'
        f'<div style="font-size:11px;color:#94a3b8">{sub}</div></div>'
        for label, val, sub in kpis
    )

    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>Online Adaptation Dashboard — Port {PORT}</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{ margin:0; background:#0f172a; color:#e2e8f0; font-family:system-ui,sans-serif; }}
  h1 {{ color:#C74634; margin:0; font-size:22px; }}
  h2 {{ color:#38bdf8; font-size:15px; margin:0 0 12px; }}
  .topbar {{ background:#1e293b; padding:16px 24px; display:flex; align-items:center; gap:16px; border-bottom:1px solid #334155; }}
  .badge {{ background:#C74634; color:#fff; font-size:11px; padding:3px 8px; border-radius:4px; }}
  .grid {{ display:grid; grid-template-columns:1fr 1fr; gap:16px; padding:20px; }}
  .card {{ background:#1e293b; padding:18px; border-radius:10px; }}
  .card.full {{ grid-column: 1 / -1; }}
  .kpi-grid {{ display:grid; grid-template-columns:repeat(3,1fr); gap:12px; }}
  .status {{ display:inline-block; width:8px; height:8px; border-radius:50%; background:#22c55e; margin-right:6px; }}
</style></head>
<body>
<div class="topbar">
  <h1>Online Adaptation Dashboard</h1>
  <span class="badge">LIVE</span>
  <span style="margin-left:auto;font-size:12px;color:#64748b">OCI Robot Cloud &nbsp;|&nbsp; <span class="status"></span>Active &nbsp;|&nbsp; Port {PORT}</span>
</div>
<div class="grid">
  <div class="card full">
    <h2>KPI Summary</h2>
    <div class="kpi-grid">{kpi_cards}</div>
  </div>
  <div class="card full">
    <h2>Adaptation Loss Curve — Baseline vs Online Adapt (MAML-style inner loop)</h2>
    {loss_svg}
  </div>
  <div class="card">
    <h2>Task Success Rate by Environment</h2>
    {bar_svg}
  </div>
  <div class="card" style="display:flex;flex-direction:column;align-items:center">
    <h2>Capability Radar</h2>
    {radar_svg}
    <div style="font-size:11px;color:#64748b;margin-top:8px">Orange = Baseline &nbsp; Blue = Online Adapt</div>
  </div>
</div>
</body></html>"""


if USE_FASTAPI:
    app = FastAPI(title="Online Adaptation Dashboard")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return build_html()

    @app.get("/health")
    def health():
        return {"status": "ok", "port": PORT, "service": "online_adaptation_dashboard"}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(build_html().encode())

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
