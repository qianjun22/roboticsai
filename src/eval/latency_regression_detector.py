"""Latency Regression Detector — FastAPI port 8606"""
import json, math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8606

def build_html():
    # --- Control Chart Data (30 days) ---
    random.seed(42)
    ucl = 280
    lcl = 180
    mean = 230
    values = []
    for i in range(30):
        v = mean + random.gauss(0, 18)
        values.append(round(v, 1))
    # Force 3 anomalies
    values[7]  = 291.5
    values[18] = 294.2
    values[25] = 298.7

    chart_w, chart_h = 560, 200
    pad_l, pad_r, pad_t, pad_b = 48, 16, 16, 32
    plot_w = chart_w - pad_l - pad_r
    plot_h = chart_h - pad_t - pad_b
    v_min, v_max = 150, 320

    def cx(i): return pad_l + i * plot_w / 29
    def cy(v): return pad_t + plot_h * (1 - (v - v_min) / (v_max - v_min))

    line_pts = " ".join(f"{cx(i):.1f},{cy(v):.1f}" for i, v in enumerate(values))
    ucl_y = cy(ucl)
    lcl_y = cy(lcl)
    mean_y = cy(mean)

    dots_normal = ""
    dots_anomaly = ""
    anomaly_indices = {7, 18, 25}
    for i, v in enumerate(values):
        x, y = cx(i), cy(v)
        if i in anomaly_indices:
            dots_anomaly += f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="#ef4444" stroke="#fca5a5" stroke-width="1.5"/>\n'
        else:
            dots_normal += f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="#38bdf8"/>\n'

    x_labels = "".join(
        f'<text x="{cx(i):.1f}" y="{chart_h - 6}" text-anchor="middle" font-size="9" fill="#94a3b8">d{i+1}</text>'
        for i in range(0, 30, 5)
    )
    y_labels = "".join(
        f'<text x="{pad_l - 6}" y="{cy(v) + 4:.1f}" text-anchor="end" font-size="9" fill="#94a3b8">{v}</text>'
        for v in [160, 180, 200, 220, 240, 260, 280, 300, 320]
        if v_min <= v <= v_max
    )

    control_chart_svg = f"""
    <svg width="{chart_w}" height="{chart_h}" xmlns="http://www.w3.org/2000/svg">
      <!-- UCL band -->
      <rect x="{pad_l}" y="{pad_t}" width="{plot_w}" height="{ucl_y - pad_t:.1f}"
            fill="#ef444415" />
      <!-- LCL band -->
      <rect x="{pad_l}" y="{lcl_y:.1f}" width="{plot_w}" height="{pad_t + plot_h - lcl_y:.1f}"
            fill="#ef444415" />
      <!-- UCL line -->
      <line x1="{pad_l}" y1="{ucl_y:.1f}" x2="{pad_l + plot_w}" y2="{ucl_y:.1f}"
            stroke="#ef4444" stroke-width="1" stroke-dasharray="4,3"/>
      <text x="{pad_l + plot_w - 2}" y="{ucl_y - 3:.1f}" text-anchor="end" font-size="9" fill="#ef4444">UCL 280ms</text>
      <!-- LCL line -->
      <line x1="{pad_l}" y1="{lcl_y:.1f}" x2="{pad_l + plot_w}" y2="{lcl_y:.1f}"
            stroke="#f97316" stroke-width="1" stroke-dasharray="4,3"/>
      <text x="{pad_l + plot_w - 2}" y="{lcl_y - 3:.1f}" text-anchor="end" font-size="9" fill="#f97316">LCL 180ms</text>
      <!-- Mean line -->
      <line x1="{pad_l}" y1="{mean_y:.1f}" x2="{pad_l + plot_w}" y2="{mean_y:.1f}"
            stroke="#64748b" stroke-width="1" stroke-dasharray="2,2"/>
      <!-- Data line -->
      <polyline points="{line_pts}" fill="none" stroke="#38bdf8" stroke-width="1.8"/>
      {dots_normal}
      {dots_anomaly}
      {x_labels}
      {y_labels}
      <!-- Anomaly labels -->
      <text x="{cx(7):.1f}" y="{cy(values[7]) - 9:.1f}" text-anchor="middle" font-size="8" fill="#ef4444">!</text>
      <text x="{cx(18):.1f}" y="{cy(values[18]) - 9:.1f}" text-anchor="middle" font-size="8" fill="#ef4444">!</text>
      <text x="{cx(25):.1f}" y="{cy(values[25]) - 9:.1f}" text-anchor="middle" font-size="8" fill="#ef4444">!</text>
    </svg>
    """

    # --- Attribution Bar Chart ---
    attribs = [
        ("model_version", 42, "#C74634"),
        ("infra",         28, "#f97316"),
        ("load",          18, "#facc15"),
        ("data_dist",     12, "#38bdf8"),
    ]
    bar_w, bar_h = 560, 160
    a_pad_l, a_pad_r, a_pad_t, a_pad_b = 110, 60, 16, 28
    a_plot_w = bar_w - a_pad_l - a_pad_r
    a_plot_h = bar_h - a_pad_t - a_pad_b
    row_h = a_plot_h / len(attribs)

    attrib_bars = ""
    for idx, (label, pct, color) in enumerate(attribs):
        bw = a_plot_w * pct / 100
        y = a_pad_t + idx * row_h + row_h * 0.15
        bh = row_h * 0.7
        attrib_bars += f"""
        <text x="{a_pad_l - 8}" y="{y + bh / 2 + 4:.1f}" text-anchor="end" font-size="11" fill="#cbd5e1">{label}</text>
        <rect x="{a_pad_l}" y="{y:.1f}" width="{bw:.1f}" height="{bh:.1f}" rx="3" fill="{color}" opacity="0.85"/>
        <text x="{a_pad_l + bw + 6:.1f}" y="{y + bh / 2 + 4:.1f}" font-size="11" fill="#e2e8f0">{pct}%</text>
        """
    x_ticks = "".join(
        f'<text x="{a_pad_l + a_plot_w * v / 100:.1f}" y="{bar_h - 8}" text-anchor="middle" font-size="9" fill="#64748b">{v}%</text>'
        for v in [0, 25, 50, 75, 100]
    )
    x_gridlines = "".join(
        f'<line x1="{a_pad_l + a_plot_w * v / 100:.1f}" y1="{a_pad_t}" x2="{a_pad_l + a_plot_w * v / 100:.1f}" y2="{a_pad_t + a_plot_h}" stroke="#1e293b" stroke-width="1"/>'
        for v in [25, 50, 75, 100]
    )
    attrib_svg = f"""
    <svg width="{bar_w}" height="{bar_h}" xmlns="http://www.w3.org/2000/svg">
      {x_gridlines}
      {attrib_bars}
      {x_ticks}
    </svg>
    """

    # --- Latency CDF Comparison ---
    cdf_w, cdf_h = 560, 200
    c_pad_l, c_pad_r, c_pad_t, c_pad_b = 48, 16, 16, 32
    c_plot_w = cdf_w - c_pad_l - c_pad_r
    c_plot_h = cdf_h - c_pad_t - c_pad_b

    def normal_cdf(x, mu, sigma):
        return 0.5 * (1 + math.erf((x - mu) / (sigma * math.sqrt(2))))

    latency_pts = list(range(100, 420, 5))
    baseline_mu, baseline_sigma = 210, 25
    current_mu,  current_sigma  = 248, 32

    def lx(v): return c_pad_l + (v - 100) / (420 - 100) * c_plot_w
    def ly(p): return c_pad_t + c_plot_h * (1 - p)

    baseline_pts = [(lx(v), ly(normal_cdf(v, baseline_mu, baseline_sigma))) for v in latency_pts]
    current_pts  = [(lx(v), ly(normal_cdf(v, current_mu,  current_sigma)))  for v in latency_pts]

    baseline_poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in baseline_pts)
    current_poly  = " ".join(f"{x:.1f},{y:.1f}" for x, y in current_pts)

    # fill between: go along current fwd, baseline bwd
    fill_pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in current_pts)
    fill_pts += " " + " ".join(f"{x:.1f},{y:.1f}" for x, y in reversed(baseline_pts))

    c_x_labels = "".join(
        f'<text x="{lx(v):.1f}" y="{cdf_h - 6}" text-anchor="middle" font-size="9" fill="#94a3b8">{v}</text>'
        for v in range(100, 421, 60)
    )
    c_y_labels = "".join(
        f'<text x="{c_pad_l - 6}" y="{ly(p) + 4:.1f}" text-anchor="end" font-size="9" fill="#94a3b8">{int(p*100)}%</text>'
        for p in [0.0, 0.25, 0.5, 0.75, 1.0]
    )

    cdf_svg = f"""
    <svg width="{cdf_w}" height="{cdf_h}" xmlns="http://www.w3.org/2000/svg">
      <!-- Regression area -->
      <polygon points="{fill_pts}" fill="#ef444420"/>
      <!-- Baseline -->
      <polyline points="{baseline_poly}" fill="none" stroke="#38bdf8" stroke-width="2"/>
      <!-- Current -->
      <polyline points="{current_poly}" fill="none" stroke="#C74634" stroke-width="2"/>
      {c_x_labels}
      {c_y_labels}
      <!-- Legend -->
      <rect x="{c_pad_l + 10}" y="{c_pad_t + 10}" width="12" height="3" fill="#38bdf8"/>
      <text x="{c_pad_l + 26}" y="{c_pad_t + 16}" font-size="10" fill="#94a3b8">Baseline (p50=210ms)</text>
      <rect x="{c_pad_l + 10}" y="{c_pad_t + 26}" width="12" height="3" fill="#C74634"/>
      <text x="{c_pad_l + 26}" y="{c_pad_t + 32}" font-size="10" fill="#94a3b8">Current (p50=248ms)</text>
      <rect x="{c_pad_l + 10}" y="{c_pad_t + 42}" width="12" height="8" fill="#ef444420"/>
      <text x="{c_pad_l + 26}" y="{c_pad_t + 50}" font-size="10" fill="#94a3b8">Regression area</text>
      <!-- x-axis label -->
      <text x="{c_pad_l + c_plot_w / 2:.1f}" y="{cdf_h - 2}" text-anchor="middle" font-size="9" fill="#64748b">Latency (ms)</text>
    </svg>
    """

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>Latency Regression Detector — Port 8606</title>
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; padding: 24px; }}
  h1 {{ color: #C74634; font-size: 1.5rem; margin-bottom: 4px; }}
  .subtitle {{ color: #64748b; font-size: 0.85rem; margin-bottom: 24px; }}
  .grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 24px; }}
  .card {{ background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 18px; }}
  .card-label {{ color: #64748b; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 6px; }}
  .card-value {{ font-size: 1.6rem; font-weight: 700; }}
  .card-value.red   {{ color: #ef4444; }}
  .card-value.amber {{ color: #f59e0b; }}
  .card-value.cyan  {{ color: #38bdf8; }}
  .card-value.green {{ color: #34d399; }}
  .card-sub {{ color: #94a3b8; font-size: 0.75rem; margin-top: 4px; }}
  .panel {{ background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 20px; margin-bottom: 20px; }}
  .panel-title {{ color: #38bdf8; font-size: 0.9rem; font-weight: 600; margin-bottom: 14px; }}
  .badge {{ display: inline-block; padding: 2px 10px; border-radius: 999px; font-size: 0.72rem; font-weight: 600; }}
  .badge-red   {{ background: #7f1d1d; color: #fca5a5; }}
  .badge-amber {{ background: #78350f; color: #fcd34d; }}
  footer {{ color: #334155; font-size: 0.75rem; text-align: center; margin-top: 24px; }}
</style>
</head>
<body>
<h1>Latency Regression Detector</h1>
<p class="subtitle">OCI Robot Cloud · Port 8606 · Real-time p99 regression monitoring with auto-gate</p>

<div class="grid">
  <div class="card">
    <div class="card-label">Regressions Detected</div>
    <div class="card-value red">2</div>
    <div class="card-sub">last 30 days · ≥UCL violations</div>
  </div>
  <div class="card">
    <div class="card-label">Gate Status</div>
    <div class="card-value amber">HOLD</div>
    <div class="card-sub">auto-triggered on anomaly</div>
  </div>
  <div class="card">
    <div class="card-label">MTTR Avg</div>
    <div class="card-value cyan">4.2 hr</div>
    <div class="card-sub">mean time to remediate</div>
  </div>
  <div class="card">
    <div class="card-label">Current p99</div>
    <div class="card-value red">267ms</div>
    <div class="card-sub">UCL = 280ms · LCL = 180ms</div>
  </div>
</div>

<div class="panel">
  <div class="panel-title">p99 Control Chart — 30-Day Window
    <span class="badge badge-red" style="margin-left:10px">3 anomalies highlighted</span>
  </div>
  {control_chart_svg}
</div>

<div class="panel">
  <div class="panel-title">Regression Attribution — Contribution by Factor</div>
  {attrib_svg}
</div>

<div class="panel">
  <div class="panel-title">Latency CDF — Current vs Baseline
    <span class="badge badge-amber" style="margin-left:10px">+38ms p50 regression</span>
  </div>
  {cdf_svg}
</div>

<footer>OCI Robot Cloud · Latency Regression Detector · cycle-137A</footer>
</body>
</html>"""

if USE_FASTAPI:
    app = FastAPI(title="Latency Regression Detector")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return build_html()

    @app.get("/health")
    def health():
        return {"status": "ok", "port": PORT, "service": "latency_regression_detector"}

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            body = json.dumps({"status": "ok", "port": PORT}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)
        else:
            body = build_html().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(body)

    def log_message(self, *a):
        pass

if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
