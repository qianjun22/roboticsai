"""Competitive Pricing Monitor — FastAPI port 8823"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8823

def build_html():
    rng = random.Random(42 + random.randint(0, 99))

    # Competitor cloud robotics pricing tiers ($/hr GPU)
    competitors = [
        {"name": "OCI Robot Cloud", "color": "#C74634", "base": 2.10, "logo": "OCI"},
        {"name": "AWS RoboMaker",   "color": "#f59e0b", "base": 2.85, "logo": "AWS"},
        {"name": "GCP AutoRobot",   "color": "#38bdf8", "base": 2.65, "logo": "GCP"},
        {"name": "Azure Robotics",  "color": "#818cf8", "base": 2.72, "logo": "AZR"},
        {"name": "CoreWeave RT",    "color": "#4ade80", "base": 1.98, "logo": "CW"},
    ]

    num_days = 30
    # Simulate daily price fluctuations with random walk + sin trend
    for c in competitors:
        prices = [c["base"]]
        for d in range(1, num_days):
            delta = rng.gauss(0, 0.02) + 0.003 * math.sin(2 * math.pi * d / 14)
            prices.append(round(max(0.5, prices[-1] + delta), 4))
        c["prices"] = prices
        c["current"] = prices[-1]
        c["change"] = round(prices[-1] - prices[0], 4)
        c["pct"] = round((prices[-1] - prices[0]) / prices[0] * 100, 2)

    # Price index vs OCI (baseline)
    oci_latest = competitors[0]["current"]

    # Workload pricing tiers table
    workloads = [
        ("Fine-Tune (100 demos)",  "GR00T N1.6", 1, 8),
        ("Fine-Tune (1000 demos)", "GR00T N1.6", 8, 60),
        ("Inference (single arm)", "OpenVLA",    0, 1),
        ("DAgger Collection",      "IsaacSim",   2, 6),
        ("Batch Eval (20 eps)",    "LIBERO",      1, 3),
        ("SDG Pipeline",           "Genesis",    4, 16),
    ]
    workload_rows = ""
    for wl_name, model, gpu_min, gpu_max in workloads:
        gpu_hrs = rng.uniform(gpu_min, gpu_max)
        oci_cost  = round(gpu_hrs * competitors[0]["current"], 3)
        aws_cost  = round(gpu_hrs * competitors[1]["current"], 3)
        gcp_cost  = round(gpu_hrs * competitors[2]["current"], 3)
        savings_aws = round(aws_cost - oci_cost, 3)
        savings_gcp = round(gcp_cost - oci_cost, 3)
        workload_rows += f"""
        <tr>
          <td style="padding:7px 10px;color:#e2e8f0">{wl_name}</td>
          <td style="padding:7px 10px;color:#94a3b8;font-size:0.8rem">{model}</td>
          <td style="padding:7px 10px;color:#C74634;font-weight:bold">${oci_cost}</td>
          <td style="padding:7px 10px;color:#f59e0b">${aws_cost}</td>
          <td style="padding:7px 10px;color:#38bdf8">${gcp_cost}</td>
          <td style="padding:7px 10px;color:#4ade80">+${savings_aws} vs AWS</td>
        </tr>"""

    # SVG line chart: 30-day price history for all competitors
    W, H = 560, 160
    all_prices = [p for c in competitors for p in c["prices"]]
    p_min, p_max = min(all_prices), max(all_prices)
    p_span = p_max - p_min if p_max != p_min else 0.1

    price_lines = ""
    for c in competitors:
        pts = " ".join(
            f"{int(W * d / (num_days - 1))},{int(H - (v - p_min) / p_span * (H - 12) - 6)}"
            for d, v in enumerate(c["prices"])
        )
        price_lines += f'<polyline points="{pts}" fill="none" stroke="{c[\"color\"]}" stroke-width="{2 if c[\"logo\"] == \"OCI\" else 1.5}" opacity="{1.0 if c[\"logo\"] == \"OCI\" else 0.75}"/>\n'

    legend_svg = "".join(
        f'<rect x="{10 + i * 110}" y="152" width="10" height="10" fill="{c[\"color\"]}"/>'
        f'<text x="{24 + i * 110}" y="162" fill="#94a3b8" font-size="9">{c["logo"]}: ${c["current"]:.3f}</text>'
        for i, c in enumerate(competitors)
    )

    # Grid lines for price chart
    grid_lines = ""
    for gi in range(4):
        gy = int(H - gi * (H - 12) / 3 - 6)
        gv = round(p_min + gi * p_span / 3, 3)
        grid_lines += f'<line x1="0" y1="{gy}" x2="{W}" y2="{gy}" stroke="#334155" stroke-width="1" stroke-dasharray="3,4"/>'
        grid_lines += f'<text x="{W + 4}" y="{gy + 4}" fill="#475569" font-size="9">${gv}</text>'

    # Bar chart: current price by provider
    bar_W = W // len(competitors) - 16
    bar_max = max(c["current"] for c in competitors)
    bar_svg = ""
    for i, c in enumerate(competitors):
        bx = i * (W // len(competitors)) + 10
        bh = int((c["current"] / bar_max) * 100)
        by = 110 - bh
        bar_svg += f'<rect x="{bx}" y="{by}" width="{bar_W}" height="{bh}" fill="{c["color"]}" opacity="0.85" rx="3"/>'
        bar_svg += f'<text x="{bx + bar_W // 2}" y="{by - 4}" fill="{c["color"]}" font-size="10" text-anchor="middle">${c["current"]:.3f}</text>'
        bar_svg += f'<text x="{bx + bar_W // 2}" y="126" fill="#64748b" font-size="9" text-anchor="middle">{c["logo"]}</text>'

    # Metric cards
    oci_vs_aws_savings_pct = round((competitors[1]["current"] - oci_latest) / competitors[1]["current"] * 100, 1)
    oci_vs_gcp_savings_pct = round((competitors[2]["current"] - oci_latest) / competitors[2]["current"] * 100, 1)
    price_rank = sorted(competitors, key=lambda c: c["current"]).index(competitors[0]) + 1
    alerts = sum(1 for c in competitors if abs(c["pct"]) > 1.5)

    return f"""<!DOCTYPE html><html lang="en"><head><title>Competitive Pricing Monitor</title>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>
  body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui,sans-serif}}
  h1{{color:#C74634;padding:20px 20px 5px;margin:0;font-size:1.5rem}}
  .subtitle{{color:#64748b;padding:0 20px 15px;font-size:0.85rem}}
  h2{{color:#38bdf8;margin:0 0 10px;font-size:0.95rem}}
  .grid4{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;padding:0 20px}}
  .grid2{{display:grid;grid-template-columns:1fr 1fr;gap:12px;padding:0 20px 20px}}
  .card{{background:#1e293b;padding:20px;border-radius:8px;border:1px solid #334155}}
  .stat{{font-size:1.9rem;font-weight:700;color:#38bdf8}}
  .label{{font-size:0.75rem;color:#64748b;margin-top:4px}}
  .good{{color:#4ade80}}.warn{{color:#facc15}}.oci{{color:#C74634}}
  table{{width:100%;border-collapse:collapse}}
  th{{text-align:left;padding:7px 10px;color:#64748b;font-size:0.75rem;border-bottom:1px solid #334155}}
  tr:hover td{{background:#273548}}
  .badge{{display:inline-block;padding:2px 8px;border-radius:12px;font-size:0.75rem;font-weight:600}}
  .badge-green{{background:#052e16;color:#4ade80}}.badge-red{{background:#3f0e0e;color:#f87171}}
</style></head>
<body>
<h1>Competitive Pricing Monitor</h1>
<div class="subtitle">Port {PORT} &nbsp;|&nbsp; Cloud Robotics GPU Pricing &nbsp;|&nbsp; 30-day window &nbsp;|&nbsp;
  OCI rank: <span class="oci" style="font-weight:700">#{price_rank} of {len(competitors)}</span> &nbsp;|&nbsp;
  <span style="color:#facc15">{alerts} price alert(s)</span>
</div>

<div class="grid4">
  <div class="card">
    <div class="stat oci">${oci_latest:.3f}/hr</div>
    <div class="label">OCI Current GPU Price</div>
  </div>
  <div class="card">
    <div class="stat good">{oci_vs_aws_savings_pct}%</div>
    <div class="label">Cheaper vs AWS RoboMaker</div>
  </div>
  <div class="card">
    <div class="stat good">{oci_vs_gcp_savings_pct}%</div>
    <div class="label">Cheaper vs GCP AutoRobot</div>
  </div>
  <div class="card">
    <div class="stat">{alerts}</div>
    <div class="label">Price Movement Alerts (30d)</div>
  </div>
</div>

<div style="height:12px"></div>
<div class="grid2">
  <div class="card">
    <h2>30-Day Price Trend ($/GPU-hr)</h2>
    <svg viewBox="0 0 {W + 40} 170" height="170">
      <rect width="{W}" height="{H}" fill="#0f172a" rx="4"/>
      {grid_lines}
      {price_lines}
      {legend_svg}
    </svg>
  </div>
  <div class="card">
    <h2>Current Price Comparison ($/GPU-hr)</h2>
    <svg viewBox="0 0 {W} 135" height="135">
      <rect width="{W}" height="130" fill="#0f172a" rx="4"/>
      {bar_svg}
    </svg>
  </div>
</div>

<div style="padding:0 20px 20px">
  <div class="card">
    <h2>Workload Cost Comparison</h2>
    <table>
      <thead><tr>
        <th>Workload</th><th>Model</th>
        <th style="color:#C74634">OCI Cost</th>
        <th style="color:#f59e0b">AWS Cost</th>
        <th style="color:#38bdf8">GCP Cost</th>
        <th>OCI Advantage</th>
      </tr></thead>
      <tbody>{workload_rows}</tbody>
    </table>
  </div>
</div>

<div style="padding:0 20px 20px">
  <div class="card">
    <h2>30-Day Price Change Summary</h2>
    <table>
      <thead><tr><th>Provider</th><th>Start</th><th>Current</th><th>Change</th><th>Signal</th></tr></thead>
      <tbody>"""\
    + "".join(
        f"""<tr>
          <td style="padding:6px 10px;color:{c['color']};font-weight:bold">{c['name']}</td>
          <td style="padding:6px 10px;color:#94a3b8">${c['prices'][0]:.4f}</td>
          <td style="padding:6px 10px;color:#e2e8f0">${c['current']:.4f}</td>
          <td style="padding:6px 10px;color:{'#4ade80' if c['change'] < 0 else '#f87171'}">{'+' if c['change']>=0 else ''}{c['change']:.4f} ({c['pct']:+.2f}%)</td>
          <td style="padding:6px 10px">
            <span class="badge {'badge-green' if abs(c['pct']) < 1.0 else 'badge-red'}">{'STABLE' if abs(c['pct']) < 1.0 else 'VOLATILE'}</span>
          </td>
        </tr>"""
        for c in competitors
    ) + """
      </tbody>
    </table>
  </div>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Competitive Pricing Monitor")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return build_html()

    @app.get("/health")
    def health():
        return {"status": "ok", "port": PORT}

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
