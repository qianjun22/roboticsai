# OCI Region Failover Tester — port 8621
# OCI Robot Cloud | cycle-140B

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = 8621


def build_html() -> str:
    # -------------------------------------------------------
    # SVG 1: Failover scenario matrix heatmap
    # rows = scenarios, cols = regions
    # recovery_time (seconds) drives colour
    # -------------------------------------------------------
    scenarios = ["primary_down", "network_partition", "GPU_OOM", "datacenter_loss"]
    regions   = ["Ashburn", "Phoenix", "Frankfurt"]
    # recovery_times[scenario][region] in seconds
    recovery_times = [
        [18,  22,  26 ],   # primary_down
        [28,  31,  35 ],   # network_partition
        [12,  14,  16 ],   # GPU_OOM
        [1080, 1080, 1080], # datacenter_loss (18 min)
    ]

    def cell_color(t):
        if t < 30:   return "#16a34a"   # green
        if t <= 120: return "#d97706"   # amber
        return "#dc2626"                # red

    cell_w, cell_h = 100, 44
    pad_l, pad_t = 130, 50
    hmap_w = pad_l + len(regions)   * cell_w + 20
    hmap_h = pad_t + len(scenarios) * cell_h + 30

    cells = ""
    for ri, region in enumerate(regions):
        cx = pad_l + ri * cell_w + cell_w // 2
        cells += f'<text x="{cx}" y="{pad_t - 10}" text-anchor="middle" fill="#94a3b8" font-size="11" font-weight="bold">{region}</text>'
    for si, scen in enumerate(scenarios):
        sy = pad_t + si * cell_h
        cells += f'<text x="{pad_l - 8}" y="{sy + cell_h//2 + 4}" text-anchor="end" fill="#94a3b8" font-size="11">{scen}</text>'
        for ri, region in enumerate(regions):
            t = recovery_times[si][ri]
            sx = pad_l + ri * cell_w
            color = cell_color(t)
            label = f"{t}s" if t < 1000 else f"{t//60}m"
            cells += (
                f'<rect x="{sx + 2}" y="{sy + 2}" width="{cell_w - 4}" height="{cell_h - 4}" fill="{color}" rx="4" opacity="0.85"/>'
                f'<text x="{sx + cell_w//2}" y="{sy + cell_h//2 + 5}" text-anchor="middle" fill="#fff" font-size="12" font-weight="bold">{label}</text>'
            )
    # legend
    legend = (
        '<rect x="140" y="{h}" width="14" height="10" fill="#16a34a" rx="2"/>'
        '<text x="158" y="{h2}" fill="#94a3b8" font-size="10">&lt;30s auto</text>'
        '<rect x="240" y="{h}" width="14" height="10" fill="#d97706" rx="2"/>'
        '<text x="258" y="{h2}" fill="#94a3b8" font-size="10">30-120s amber</text>'
        '<rect x="370" y="{h}" width="14" height="10" fill="#dc2626" rx="2"/>'
        '<text x="388" y="{h2}" fill="#94a3b8" font-size="10">&gt;120s manual</text>'
    ).format(h=hmap_h - 18, h2=hmap_h - 8)

    svg1 = f"""
    <svg width="{hmap_w}" height="{hmap_h}" xmlns="http://www.w3.org/2000/svg" style="background:#1e293b;border-radius:8px;">
      <text x="{hmap_w//2}" y="26" text-anchor="middle" fill="#C74634" font-size="14" font-weight="bold">Failover Scenario Matrix</text>
      {cells}
      {legend}
    </svg>
    """

    # -------------------------------------------------------
    # SVG 2: Recovery time bar chart per scenario
    # using best-region (min) recovery time
    # -------------------------------------------------------
    best_times = [18, 28, 12, 1080]   # min across regions per scenario
    bar_labels = ["primary_down", "net_partition", "GPU_OOM", "dc_loss"]
    threshold  = 30   # seconds
    W2, H2, padx, pady = 460, 200, 80, 20
    max_t = 1100
    chart_h2 = H2 - pady - 40

    bars2 = ""
    bar_w2 = 60
    spacing = (W2 - padx - 20) / len(best_times)
    for i, (t, lbl) in enumerate(zip(best_times, bar_labels)):
        bh = min(int((t / max_t) * chart_h2), chart_h2)
        x  = padx + i * spacing + spacing // 2 - bar_w2 // 2
        y  = pady + chart_h2 - bh
        color = cell_color(t)
        label = f"{t}s" if t < 1000 else f"{t//60}m"
        bars2 += (
            f'<rect x="{x:.0f}" y="{y:.0f}" width="{bar_w2}" height="{bh:.0f}" fill="{color}" rx="3"/>'
            f'<text x="{x + bar_w2//2:.0f}" y="{y - 4:.0f}" text-anchor="middle" fill="#e2e8f0" font-size="11">{label}</text>'
            f'<text x="{x + bar_w2//2:.0f}" y="{pady + chart_h2 + 14:.0f}" text-anchor="middle" fill="#94a3b8" font-size="10">{lbl}</text>'
        )
    # threshold line at 30s
    thresh_y = pady + chart_h2 - int((threshold / max_t) * chart_h2)
    bars2 += (
        f'<line x1="{padx}" y1="{thresh_y}" x2="{W2 - 10}" y2="{thresh_y}" stroke="#f59e0b" stroke-width="1.5" stroke-dasharray="5,3"/>'
        f'<text x="{W2 - 8}" y="{thresh_y - 3}" text-anchor="end" fill="#f59e0b" font-size="10">30s SLA</text>'
    )

    svg2 = f"""
    <svg width="{W2}" height="{H2}" xmlns="http://www.w3.org/2000/svg" style="background:#1e293b;border-radius:8px;">
      <text x="{W2//2}" y="18" text-anchor="middle" fill="#C74634" font-size="14" font-weight="bold">Recovery Time per Scenario (best region)</text>
      {bars2}
      <line x1="{padx}" y1="{pady}" x2="{padx}" y2="{pady + chart_h2}" stroke="#334155" stroke-width="1"/>
      <line x1="{padx}" y1="{pady + chart_h2}" x2="{W2 - 10}" y2="{pady + chart_h2}" stroke="#334155" stroke-width="1"/>
    </svg>
    """

    # -------------------------------------------------------
    # SVG 3: Traffic rerouting flow diagram
    # Ashburn → Phoenix (+8ms) → Frankfurt (+31ms)
    # -------------------------------------------------------
    svg3 = """
    <svg width="500" height="180" xmlns="http://www.w3.org/2000/svg" style="background:#1e293b;border-radius:8px;">
      <text x="250" y="22" text-anchor="middle" fill="#C74634" font-size="14" font-weight="bold">Traffic Rerouting Flow (Cascade)</text>

      <!-- Ashburn node -->
      <rect x="20" y="70" width="110" height="44" rx="8" fill="#16a34a" opacity="0.85"/>
      <text x="75" y="87" text-anchor="middle" fill="#fff" font-size="12" font-weight="bold">Ashburn</text>
      <text x="75" y="103" text-anchor="middle" fill="#dcfce7" font-size="10">PRIMARY</text>

      <!-- Arrow Ashburn → Phoenix -->
      <line x1="130" y1="92" x2="190" y2="92" stroke="#38bdf8" stroke-width="2" marker-end="url(#arr)"/>
      <text x="160" y="84" text-anchor="middle" fill="#38bdf8" font-size="11">+8 ms</text>

      <!-- Phoenix node -->
      <rect x="190" y="70" width="110" height="44" rx="8" fill="#d97706" opacity="0.85"/>
      <text x="245" y="87" text-anchor="middle" fill="#fff" font-size="12" font-weight="bold">Phoenix</text>
      <text x="245" y="103" text-anchor="middle" fill="#fef3c7" font-size="10">SECONDARY</text>

      <!-- Arrow Phoenix → Frankfurt -->
      <line x1="300" y1="92" x2="360" y2="92" stroke="#38bdf8" stroke-width="2" marker-end="url(#arr)"/>
      <text x="330" y="84" text-anchor="middle" fill="#38bdf8" font-size="11">+31 ms</text>

      <!-- Frankfurt node -->
      <rect x="360" y="70" width="120" height="44" rx="8" fill="#6366f1" opacity="0.85"/>
      <text x="420" y="87" text-anchor="middle" fill="#fff" font-size="12" font-weight="bold">Frankfurt</text>
      <text x="420" y="103" text-anchor="middle" fill="#e0e7ff" font-size="10">TERTIARY</text>

      <!-- Failure label -->
      <text x="75" y="140" text-anchor="middle" fill="#94a3b8" font-size="10">Failure triggers</text>
      <text x="75" y="153" text-anchor="middle" fill="#94a3b8" font-size="10">cascade reroute</text>

      <!-- Arrow def -->
      <defs>
        <marker id="arr" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
          <path d="M0,0 L0,6 L8,3 z" fill="#38bdf8"/>
        </marker>
      </defs>
    </svg>
    """

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>OCI Region Failover Tester | OCI Robot Cloud</title>
  <style>
    body {{ background:#0f172a; color:#e2e8f0; font-family:'Segoe UI',Arial,sans-serif; margin:0; padding:24px; }}
    h1 {{ color:#C74634; font-size:1.7rem; margin-bottom:4px; }}
    h2 {{ color:#C74634; font-size:1.1rem; margin:18px 0 8px; }}
    .subtitle {{ color:#94a3b8; font-size:.95rem; margin-bottom:24px; }}
    .grid {{ display:flex; flex-wrap:wrap; gap:24px; margin-bottom:28px; }}
    .card {{ background:#1e293b; border-radius:10px; padding:20px; }}
    .metric-row {{ display:flex; gap:18px; flex-wrap:wrap; margin-bottom:24px; }}
    .metric {{ background:#1e293b; border-radius:8px; padding:14px 20px; min-width:190px; }}
    .metric .val {{ font-size:1.5rem; font-weight:700; color:#38bdf8; }}
    .metric .lbl {{ font-size:.82rem; color:#94a3b8; margin-top:2px; }}
    footer {{ color:#475569; font-size:.8rem; margin-top:32px; }}
  </style>
</head>
<body>
  <h1>OCI Region Failover Tester</h1>
  <div class="subtitle">OCI Robot Cloud &mdash; Multi-Region HA | Port {PORT}</div>

  <div class="metric-row">
    <div class="metric"><div class="val">100%</div><div class="lbl">Automated failover (compute failures)</div></div>
    <div class="metric"><div class="val">18 min</div><div class="lbl">Manual recovery — datacenter_loss</div></div>
    <div class="metric"><div class="val">+8 ms</div><div class="lbl">Ashburn → Phoenix latency delta</div></div>
    <div class="metric"><div class="val">+31 ms</div><div class="lbl">Ashburn → Frankfurt latency delta</div></div>
  </div>

  <h2>Scenario Matrix Heatmap</h2>
  <div class="card">{svg1}</div>

  <div class="grid">
    <div>
      <h2>Recovery Time per Scenario</h2>
      <div class="card">{svg2}</div>
    </div>
    <div>
      <h2>Traffic Rerouting Flow</h2>
      <div class="card">{svg3}</div>
    </div>
  </div>

  <footer>OCI Robot Cloud &bull; cycle-140B &bull; OCI Region Failover Tester &bull; port {PORT}</footer>
</body>
</html>"""
    return html


if USE_FASTAPI:
    app = FastAPI(title="OCI Region Failover Tester", version="1.0.0")

    @app.get("/", response_class=HTMLResponse)
    async def root():
        return HTMLResponse(content=build_html())

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "oci_region_failover_tester", "port": PORT}

    if __name__ == "__main__":
        uvicorn.run(app, host="0.0.0.0", port=PORT)

else:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/health":
                body = b'{"status":"ok","service":"oci_region_failover_tester"}'
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
        print(f"[oci_region_failover_tester] Serving on http://0.0.0.0:{PORT}")
        HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
