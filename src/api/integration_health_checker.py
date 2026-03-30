"""Integration Health Checker — port 8605
OCI Robot Cloud — cycle-136B
Monitors partner integration test matrix and health score trends.
"""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8605

# Integration test matrix
# Partners: PI, Apt, 1X, Machina, Wandelbots
# Points: auth, inference, train, eval, data, webhooks, SDK, billing
PARTNERS = ["Physical Intelligence", "Apptronik", "1X Technologies", "Machina Labs", "Wandelbots"]
PARTNER_SHORT = ["PI", "Apt", "1X", "Machina", "Wandelbots"]
INTEG_POINTS = ["Auth", "Inference", "Train", "Eval", "Data", "Webhooks", "SDK", "Billing"]

# Status: 0=PASS(green), 1=DEGRADED(amber), 2=FAIL(red), 3=N/A(gray)
MATRIX = [
    # PI: all green except webhooks=DEGRADED
    [0, 0, 0, 0, 0, 1, 0, 0],
    # Apt: mostly green, billing=DEGRADED
    [0, 0, 0, 0, 0, 0, 0, 1],
    # 1X: 3 amber (webhooks, SDK, billing)
    [0, 0, 0, 0, 0, 1, 1, 1],
    # Machina: 5 green, rest gray (not yet integrated)
    [0, 0, 0, 0, 0, 3, 3, 3],
    # Wandelbots: 4 green, 3 gray, billing gray
    [0, 0, 0, 0, 3, 3, 3, 3],
]

STATUS_COLOR = {
    0: "#16a34a",   # PASS — green
    1: "#d97706",   # DEGRADED — amber
    2: "#dc2626",   # FAIL — red
    3: "#334155",   # N/A — gray
}
STATUS_TEXT_COLOR = {
    0: "#dcfce7",
    1: "#fef3c7",
    2: "#fee2e2",
    3: "#64748b",
}
STATUS_LABEL = {0: "PASS", 1: "DEGR", 2: "FAIL", 3: "N/A"}


def build_html() -> str:
    # --- Integration test matrix SVG ---
    cell_w, cell_h = 78, 40
    label_w = 148
    header_h = 36
    mat_w = label_w + len(INTEG_POINTS) * cell_w + 16
    mat_h = header_h + len(PARTNERS) * cell_h + 16

    matrix_cells = ""
    # Column headers
    for ci, ip in enumerate(INTEG_POINTS):
        cx = label_w + ci * cell_w + cell_w // 2
        matrix_cells += f'<text x="{cx}" y="22" fill="#94a3b8" font-size="11" text-anchor="middle">{ip}</text>'

    for ri, partner in enumerate(PARTNER_SHORT):
        y = header_h + ri * cell_h
        matrix_cells += f'<text x="{label_w - 8}" y="{y + cell_h//2 + 5}" fill="#e2e8f0" font-size="12" text-anchor="end">{partner}</text>'
        for ci, ip in enumerate(INTEG_POINTS):
            status = MATRIX[ri][ci]
            x = label_w + ci * cell_w
            fc = STATUS_COLOR[status]
            tc = STATUS_TEXT_COLOR[status]
            label = STATUS_LABEL[status]
            matrix_cells += f'<rect x="{x + 2}" y="{y + 2}" width="{cell_w - 4}" height="{cell_h - 4}" rx="4" fill="{fc}" opacity="0.8"/>'
            matrix_cells += f'<text x="{x + cell_w//2}" y="{y + cell_h//2 + 5}" fill="{tc}" font-size="11" font-weight="600" text-anchor="middle">{label}</text>'

    matrix_svg = f"""
    <svg viewBox="0 0 {mat_w} {mat_h}" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:{mat_w}px;">
      <rect width="{mat_w}" height="{mat_h}" rx="8" fill="#1e293b"/>
      {matrix_cells}
    </svg>"""

    # --- Health score trend SVG (30-day rolling, 5 lines) ---
    hs_w, hs_h = 760, 220
    pad_l, pad_r, pad_t, pad_b = 50, 20, 20, 48
    plot_w = hs_w - pad_l - pad_r
    plot_h = hs_h - pad_t - pad_b
    days = 30

    # Synthetic 30-day health scores per partner (0-100)
    import math
    def score_series(base, noise_amp, dip_day=None, dip_depth=0):
        pts = []
        for d in range(days):
            v = base + noise_amp * math.sin(d * 0.4 + base)
            if dip_day and abs(d - dip_day) <= 2:
                v -= dip_depth * (1 - abs(d - dip_day) / 3.0)
            pts.append(max(0, min(100, v)))
        return pts

    partner_scores = [
        score_series(96, 1.5, dip_day=18, dip_depth=8),   # PI — dip for webhook issue
        score_series(94, 1.2, dip_day=25, dip_depth=6),   # Apt — billing dip near end
        score_series(88, 2.5, dip_day=10, dip_depth=12),  # 1X — multiple degraded
        score_series(82, 1.8),                             # Machina — stable, partial integration
        score_series(79, 2.0),                             # Wandelbots — lower, fewer points
    ]
    line_colors = ["#38bdf8", "#a3e635", "#f97316", "#c084fc", "#fb7185"]

    def sx(d):
        return pad_l + int(d / (days - 1) * plot_w)

    def sy(score):
        return pad_t + plot_h - int((score - 60) / 40.0 * plot_h)

    # Grid
    grid_svg = ""
    for mark in [70, 80, 90, 100]:
        gy = sy(mark)
        grid_svg += f'<line x1="{pad_l}" y1="{gy}" x2="{hs_w - pad_r}" y2="{gy}" stroke="#1e3a5f" stroke-width="1"/>'
        grid_svg += f'<text x="{pad_l - 6}" y="{gy + 4}" fill="#64748b" font-size="10" text-anchor="end">{mark}</text>'

    # X-axis labels
    x_labels = ""
    for d in [0, 7, 14, 21, 29]:
        x_labels += f'<text x="{sx(d)}" y="{pad_t + plot_h + 16}" fill="#64748b" font-size="10" text-anchor="middle">Day {d+1}</text>'

    # Lines
    lines_svg = ""
    for pi_idx, (scores, color) in enumerate(zip(partner_scores, line_colors)):
        pts = " ".join(f"{sx(d)},{sy(s)}" for d, s in enumerate(scores))
        lines_svg += f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2" stroke-linejoin="round" opacity="0.9"/>'
        # End dot
        last_x, last_y = sx(days - 1), sy(scores[-1])
        lines_svg += f'<circle cx="{last_x}" cy="{last_y}" r="4" fill="{color}"/>'

    # Legend
    legend_svg = ""
    for li, (ps, color) in enumerate(zip(PARTNER_SHORT, line_colors)):
        lx = pad_l + li * 140
        legend_svg += f'<rect x="{lx}" y="{hs_h - 20}" width="12" height="12" rx="2" fill="{color}"/>'
        legend_svg += f'<text x="{lx + 16}" y="{hs_h - 9}" fill="#94a3b8" font-size="11">{ps}</text>'

    trend_svg = f"""
    <svg viewBox="0 0 {hs_w} {hs_h}" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:{hs_w}px;">
      <rect width="{hs_w}" height="{hs_h}" rx="8" fill="#1e293b"/>
      {grid_svg}
      {lines_svg}
      {x_labels}
      {legend_svg}
    </svg>"""

    # --- Incident detail table ---
    incident_rows = """
      <tr>
        <td>Physical Intelligence</td>
        <td>Webhooks</td>
        <td><span class="badge badge-warn">DEGRADED</span></td>
        <td>PI SDK v3</td>
        <td>1247ms p95</td>
        <td>DNS TTL misconfiguration on PI side</td>
      </tr>
      <tr>
        <td>Apptronik</td>
        <td>Billing</td>
        <td><span class="badge badge-warn">DEGRADED</span></td>
        <td>Billing API v2</td>
        <td>+340ms overhead</td>
        <td>Invoice reconciliation batch lag</td>
      </tr>
      <tr>
        <td>1X Technologies</td>
        <td>Webhooks / SDK / Billing</td>
        <td><span class="badge badge-warn">DEGRADED</span></td>
        <td>Multiple</td>
        <td>Various</td>
        <td>Ongoing integration work — 3 endpoints degraded</td>
      </tr>
    """

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Integration Health Checker — OCI Robot Cloud</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; padding: 24px; }}
    h1 {{ color: #C74634; font-size: 1.6rem; font-weight: 700; margin-bottom: 4px; }}
    h2 {{ color: #38bdf8; font-size: 1.1rem; font-weight: 600; margin: 28px 0 12px; }}
    .subtitle {{ color: #64748b; font-size: 0.85rem; margin-bottom: 28px; }}
    .metrics {{ display: grid; grid-template-columns: repeat(4,1fr); gap: 16px; margin-bottom: 32px; }}
    .metric {{ background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 16px; }}
    .metric-label {{ color: #64748b; font-size: 0.75rem; text-transform: uppercase; letter-spacing: .05em; margin-bottom: 6px; }}
    .metric-value {{ font-size: 1.6rem; font-weight: 700; }}
    .metric-sub {{ color: #64748b; font-size: 0.78rem; margin-top: 4px; }}
    .ok {{ color: #4ade80; }}
    .warn {{ color: #facc15; }}
    .accent {{ color: #38bdf8; }}
    .red {{ color: #C74634; }}
    .card {{ background: #1e293b; border: 1px solid #334155; border-radius: 10px; padding: 20px; margin-bottom: 24px; overflow-x: auto; }}
    .badge {{ display:inline-block; padding:2px 10px; border-radius:999px; font-size:0.75rem; font-weight:600; }}
    .badge-ok {{ background:#14532d; color:#4ade80; }}
    .badge-warn {{ background:#422006; color:#facc15; }}
    .badge-fail {{ background:#450a0a; color:#f87171; }}
    table {{ width:100%; border-collapse:collapse; font-size:0.85rem; }}
    th {{ color:#64748b; text-transform:uppercase; font-size:0.72rem; letter-spacing:.05em; padding:8px 12px; text-align:left; border-bottom:1px solid #334155; }}
    td {{ padding:10px 12px; border-bottom:1px solid #1e293b; color:#cbd5e1; }}
    tr:hover td {{ background:#1e293b88; }}
    .legend {{ display:flex; gap:24px; flex-wrap:wrap; margin-top:12px; }}
    .legend-item {{ display:flex; align-items:center; gap:8px; font-size:0.8rem; color:#94a3b8; }}
    .legend-dot {{ width:14px; height:14px; border-radius:3px; }}
  </style>
</head>
<body>
  <h1>Integration Health Checker</h1>
  <p class="subtitle">OCI Robot Cloud — Partner Integration Monitor | Port {PORT}</p>

  <div class="metrics">
    <div class="metric">
      <div class="metric-label">Checks Passing</div>
      <div class="metric-value ok">39 / 40</div>
      <div class="metric-sub">1 degraded, 0 failed</div>
    </div>
    <div class="metric">
      <div class="metric-label">PI Webhooks p95</div>
      <div class="metric-value warn">1247ms</div>
      <div class="metric-sub">DNS TTL misconfiguration</div>
    </div>
    <div class="metric">
      <div class="metric-label">Fully Integrated</div>
      <div class="metric-value accent">2 / 5</div>
      <div class="metric-sub">PI + Apt all endpoints</div>
    </div>
    <div class="metric">
      <div class="metric-label">Root Cause</div>
      <div class="metric-value" style="font-size:1rem;color:#f8a04b;">DNS TTL</div>
      <div class="metric-sub">PI SDK v3 webhook timeout</div>
    </div>
  </div>

  <h2>Partner Integration Test Matrix</h2>
  <div class="card">
    {matrix_svg}
    <div class="legend">
      <div class="legend-item"><div class="legend-dot" style="background:#16a34a"></div>PASS</div>
      <div class="legend-item"><div class="legend-dot" style="background:#d97706"></div>DEGRADED</div>
      <div class="legend-item"><div class="legend-dot" style="background:#dc2626"></div>FAIL</div>
      <div class="legend-item"><div class="legend-dot" style="background:#334155"></div>Not Yet Integrated</div>
    </div>
  </div>

  <h2>Health Score Trend — 30-Day Rolling</h2>
  <div class="card">
    {trend_svg}
  </div>

  <h2>Active Incidents &amp; Degradations</h2>
  <div class="card">
    <table>
      <thead>
        <tr>
          <th>Partner</th>
          <th>Integration Point</th>
          <th>Status</th>
          <th>Component</th>
          <th>Latency / Impact</th>
          <th>Root Cause</th>
        </tr>
      </thead>
      <tbody>
        {incident_rows}
      </tbody>
    </table>
  </div>

  <p style="color:#334155;font-size:0.75rem;margin-top:32px;">OCI Robot Cloud · Integration Health Checker · Port {PORT} · cycle-136B</p>
</body>
</html>"""
    return html


if USE_FASTAPI:
    app = FastAPI(title="Integration Health Checker", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def index():
        return build_html()

    @app.get("/health")
    async def health():
        total_checks = sum(1 for row in MATRIX for s in row if s != 3)
        passing = sum(1 for row in MATRIX for s in row if s == 0)
        degraded = sum(1 for row in MATRIX for s in row if s == 1)
        failed = sum(1 for row in MATRIX for s in row if s == 2)
        return {
            "status": "ok",
            "service": "integration_health_checker",
            "port": PORT,
            "partners": len(PARTNERS),
            "integration_points": len(INTEG_POINTS),
            "checks_total": total_checks,
            "checks_passing": passing,
            "checks_degraded": degraded,
            "checks_failed": failed,
            "pi_webhook_p95_ms": 1247,
            "root_cause": "DNS TTL misconfiguration",
        }

    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=PORT)

else:
    from http.server import BaseHTTPRequestHandler, HTTPServer
    import json

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass

        def do_GET(self):
            if self.path == "/health":
                body = json.dumps({"status": "ok", "service": "integration_health_checker", "port": PORT}).encode()
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

    if __name__ == "__main__":
        print(f"Serving on http://0.0.0.0:{PORT} (stdlib HTTPServer)")
        HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
