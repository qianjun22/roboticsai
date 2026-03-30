"""OCI Robot Cloud — OCI Cost Forecaster v2 (port 8608)

12-month cost fan chart, cost driver stacked area, scenario comparison bars.
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False


def build_html() -> str:
    # ── Fan chart: p10/p50/p90 Apr 2026 – Mar 2027 ──────────────────────────
    months = ["Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec", "Jan", "Feb", "Mar"]
    # monthly base (p50), p10, p90  (k USD)
    p50 = [22, 23, 24, 25, 26, 42, 28, 27, 26, 25, 24, 23]
    p10 = [16, 17, 18, 19, 19, 30, 21, 20, 19, 18, 17, 17]
    p90 = [30, 32, 34, 35, 37, 58, 40, 38, 36, 34, 33, 32]

    W, H = 700, 320
    pad_l, pad_r, pad_t, pad_b = 60, 30, 30, 50
    chart_w = W - pad_l - pad_r
    chart_h = H - pad_t - pad_b
    n = len(months)
    step = chart_w / (n - 1)
    max_v, min_v = 65, 10

    def yx(i, val):
        x = pad_l + i * step
        y = pad_t + chart_h * (1 - (val - min_v) / (max_v - min_v))
        return x, y

    # build polygon points for p10-p90 band
    band_pts = []
    for i in range(n):
        band_pts.append(yx(i, p90[i]))
    for i in range(n - 1, -1, -1):
        band_pts.append(yx(i, p10[i]))
    band_str = " ".join(f"{x:.1f},{y:.1f}" for x, y in band_pts)

    p50_pts = " ".join(f"{yx(i, p50[i])[0]:.1f},{yx(i, p50[i])[1]:.1f}" for i in range(n))
    p10_pts = " ".join(f"{yx(i, p10[i])[0]:.1f},{yx(i, p10[i])[1]:.1f}" for i in range(n))
    p90_pts = " ".join(f"{yx(i, p90[i])[0]:.1f},{yx(i, p90[i])[1]:.1f}" for i in range(n))

    # Y grid lines
    y_grid = ""
    for v in [20, 30, 40, 50, 60]:
        _, gy = yx(0, v)
        y_grid += f'<line x1="{pad_l}" y1="{gy:.1f}" x2="{pad_l + chart_w}" y2="{gy:.1f}" stroke="#1e293b" stroke-width="1"/>'
        y_grid += f'<text x="{pad_l - 6}" y="{gy + 4:.1f}" fill="#94a3b8" font-size="10" text-anchor="end">${v}k</text>'

    # X labels
    x_labels = ""
    for i, m in enumerate(months):
        x, _ = yx(i, min_v)
        x_labels += f'<text x="{x:.1f}" y="{H - 12}" fill="#94a3b8" font-size="10" text-anchor="middle">{m}</text>'

    # Sep annotation
    sep_x, sep_y = yx(5, p90[5])
    annotation = f'''
        <line x1="{sep_x:.1f}" y1="{pad_t}" x2="{sep_x:.1f}" y2="{pad_t + chart_h}" stroke="#C74634" stroke-dasharray="4,3" stroke-width="1"/>
        <rect x="{sep_x - 52:.1f}" y="{pad_t + 2}" width="104" height="18" rx="3" fill="#C74634" opacity="0.15"/>
        <text x="{sep_x:.1f}" y="{pad_t + 14}" fill="#C74634" font-size="10" text-anchor="middle" font-weight="bold">AI World Sep spike</text>
    '''

    fan_svg = f'''
    <svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg" style="background:#1e293b;border-radius:8px">
      {y_grid}
      <polygon points="{band_str}" fill="#38bdf8" opacity="0.15"/>
      <polyline points="{p10_pts}" fill="none" stroke="#38bdf8" stroke-width="1" stroke-dasharray="4,3" opacity="0.6"/>
      <polyline points="{p90_pts}" fill="none" stroke="#38bdf8" stroke-width="1" stroke-dasharray="4,3" opacity="0.6"/>
      <polyline points="{p50_pts}" fill="none" stroke="#38bdf8" stroke-width="2.5"/>
      {annotation}
      {x_labels}
      <text x="{pad_l}" y="{pad_t - 10}" fill="#38bdf8" font-size="12" font-weight="bold">12-Month Cost Forecast (p10 / p50 / p90)</text>
      <text x="{pad_l + chart_w - 4}" y="{pad_t - 10}" fill="#94a3b8" font-size="10" text-anchor="end">USD (thousands)</text>
    </svg>
    '''

    # ── Stacked area: cost drivers Apr – Sep 2026 ────────────────────────────
    drivers = {
        "training":  [8,  8,  9,  9,  10, 18],
        "inference": [6,  7,  7,  8,  8,  12],
        "storage":   [3,  3,  3,  3,  3,  5],
        "network":   [3,  3,  3,  3,  3,  5],
        "misc":      [2,  2,  2,  2,  2,  2],
    }
    d_colors = {"training": "#38bdf8", "inference": "#818cf8", "storage": "#34d399",
                "network": "#fb923c", "misc": "#a3a3a3"}
    d_months = ["Apr", "May", "Jun", "Jul", "Aug", "Sep"]
    nd = 6
    SW, SH = 700, 300
    spad_l, spad_r, spad_t, spad_b = 60, 30, 30, 50
    schart_w = SW - spad_l - spad_r
    schart_h = SH - spad_t - spad_b
    sstep = schart_w / (nd - 1)
    smax = 45

    def sxy(i, val_bottom, val_top):
        x = spad_l + i * sstep
        yb = spad_t + schart_h * (1 - val_bottom / smax)
        yt = spad_t + schart_h * (1 - val_top / smax)
        return x, yb, yt

    # cumulative totals
    cum = [[0] * nd]
    for key in drivers:
        prev = cum[-1]
        cum.append([prev[i] + drivers[key][i] for i in range(nd)])

    stacked_polys = ""
    legend_items = ""
    for idx, key in enumerate(drivers):
        bottom = cum[idx]
        top = cum[idx + 1]
        fwd = []
        bwd = []
        for i in range(nd):
            x, _, yt = sxy(i, bottom[i], top[i])
            fwd.append(f"{x:.1f},{yt:.1f}")
        for i in range(nd - 1, -1, -1):
            x, yb, _ = sxy(i, bottom[i], top[i])
            bwd.append(f"{x:.1f},{yb:.1f}")
        pts = " ".join(fwd + bwd)
        stacked_polys += f'<polygon points="{pts}" fill="{d_colors[key]}" opacity="0.85"/>'
        lx = spad_l + idx * 120
        legend_items += f'<rect x="{lx}" y="{SH - 18}" width="12" height="12" fill="{d_colors[key]}"/>'
        legend_items += f'<text x="{lx + 16}" y="{SH - 7}" fill="#94a3b8" font-size="10">{key}</text>'

    s_y_grid = ""
    for v in [10, 20, 30, 40]:
        gy = spad_t + schart_h * (1 - v / smax)
        s_y_grid += f'<line x1="{spad_l}" y1="{gy:.1f}" x2="{spad_l + schart_w}" y2="{gy:.1f}" stroke="#1e293b" stroke-width="1"/>'
        s_y_grid += f'<text x="{spad_l - 6}" y="{gy + 4:.1f}" fill="#94a3b8" font-size="10" text-anchor="end">${v}k</text>'

    s_x_labels = ""
    for i, m in enumerate(d_months):
        x = spad_l + i * sstep
        s_x_labels += f'<text x="{x:.1f}" y="{SH - 24}" fill="#94a3b8" font-size="10" text-anchor="middle">{m}</text>'

    area_svg = f'''
    <svg width="{SW}" height="{SH}" xmlns="http://www.w3.org/2000/svg" style="background:#1e293b;border-radius:8px">
      {s_y_grid}
      {stacked_polys}
      {s_x_labels}
      {legend_items}
      <text x="{spad_l}" y="{spad_t - 10}" fill="#C74634" font-size="12" font-weight="bold">Cost Drivers — Stacked Area (Apr–Sep 2026)</text>
    </svg>
    '''

    # ── Scenario comparison bars ─────────────────────────────────────────────
    scenarios = [("Bear", 180, "#34d399"), ("Base", 312, "#38bdf8"), ("Bull", 480, "#C74634")]
    BW, BH = 500, 280
    bpad_l, bpad_r, bpad_t, bpad_b = 60, 30, 40, 50
    bchart_w = BW - bpad_l - bpad_r
    bchart_h = BH - bpad_t - bpad_b
    bmax = 550
    bar_gap = bchart_w / (len(scenarios) * 2 + 1)
    bar_w = bar_gap * 1.4

    bars_svg_inner = ""
    for bi, (label, val, color) in enumerate(scenarios):
        bx = bpad_l + bar_gap * (bi * 2 + 1) + (bar_gap - bar_w) / 2
        bh = bchart_h * val / bmax
        by = bpad_t + bchart_h - bh
        bars_svg_inner += f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bar_w:.1f}" height="{bh:.1f}" fill="{color}" rx="4" opacity="0.85"/>'
        bars_svg_inner += f'<text x="{bx + bar_w/2:.1f}" y="{by - 6:.1f}" fill="{color}" font-size="11" font-weight="bold" text-anchor="middle">${val}k</text>'
        bars_svg_inner += f'<text x="{bx + bar_w/2:.1f}" y="{bpad_t + bchart_h + 18:.1f}" fill="#94a3b8" font-size="11" text-anchor="middle">{label}</text>'

    b_y_grid = ""
    for v in [100, 200, 300, 400, 500]:
        gy = bpad_t + bchart_h * (1 - v / bmax)
        b_y_grid += f'<line x1="{bpad_l}" y1="{gy:.1f}" x2="{bpad_l + bchart_w}" y2="{gy:.1f}" stroke="#334155" stroke-width="1"/>'
        b_y_grid += f'<text x="{bpad_l - 6}" y="{gy + 4:.1f}" fill="#94a3b8" font-size="10" text-anchor="end">${v}k</text>'

    bar_svg = f'''
    <svg width="{BW}" height="{BH}" xmlns="http://www.w3.org/2000/svg" style="background:#1e293b;border-radius:8px">
      {b_y_grid}
      {bars_svg_inner}
      <text x="{bpad_l}" y="{bpad_t - 14}" fill="#C74634" font-size="12" font-weight="bold">Annual Scenario Comparison</text>
      <text x="{bpad_l}" y="{bpad_t - 2}" fill="#94a3b8" font-size="10">FY Apr 2026 – Mar 2027 (USD)</text>
    </svg>
    '''

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>OCI Cost Forecaster v2 — Port 8608</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif; padding: 32px; }}
    h1 {{ color: #C74634; font-size: 24px; margin-bottom: 4px; }}
    .subtitle {{ color: #94a3b8; font-size: 13px; margin-bottom: 32px; }}
    .metrics {{ display: flex; gap: 20px; flex-wrap: wrap; margin-bottom: 36px; }}
    .card {{ background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 20px 28px; min-width: 180px; }}
    .card-label {{ color: #94a3b8; font-size: 12px; text-transform: uppercase; letter-spacing: .05em; }}
    .card-value {{ color: #38bdf8; font-size: 28px; font-weight: 700; margin-top: 4px; }}
    .card-value.red {{ color: #C74634; }}
    .card-value.green {{ color: #34d399; }}
    .section {{ margin-bottom: 40px; }}
    h2 {{ color: #38bdf8; font-size: 16px; margin-bottom: 14px; }}
    .charts-row {{ display: flex; gap: 24px; flex-wrap: wrap; }}
  </style>
</head>
<body>
  <h1>OCI Cost Forecaster v2</h1>
  <p class="subtitle">12-Month Forecast &mdash; Apr 2026 &ndash; Mar 2027 &nbsp;|&nbsp; Port 8608</p>

  <div class="metrics">
    <div class="card">
      <div class="card-label">Base Case Annual</div>
      <div class="card-value">$312k</div>
    </div>
    <div class="card">
      <div class="card-label">AI World Month (Sep)</div>
      <div class="card-value red">$42k</div>
    </div>
    <div class="card">
      <div class="card-label">Sep vs Avg Month</div>
      <div class="card-value red">3&times; spike</div>
    </div>
    <div class="card">
      <div class="card-label">Committed Discount Saves</div>
      <div class="card-value green">$47k</div>
    </div>
  </div>

  <div class="section">
    <h2>12-Month Cost Fan Chart (p10 / p50 / p90)</h2>
    {fan_svg}
  </div>

  <div class="charts-row">
    <div class="section">
      <h2>Cost Drivers — Stacked Area</h2>
      {area_svg}
    </div>
    <div class="section">
      <h2>Scenario Comparison</h2>
      {bar_svg}
    </div>
  </div>
</body>
</html>
"""
    return html


if USE_FASTAPI:
    app = FastAPI(title="OCI Cost Forecaster v2", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def root():
        return build_html()

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "oci_cost_forecaster_v2", "port": 8608}

    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=8608)
else:
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/health":
                body = b'{"status":"ok","service":"oci_cost_forecaster_v2","port":8608}'
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
            else:
                body = build_html().encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            pass

    if __name__ == "__main__":
        print("OCI Cost Forecaster v2 running on port 8608 (stdlib HTTPServer)")
        HTTPServer(("0.0.0.0", 8608), Handler).serve_forever()
