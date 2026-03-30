"""Cloud Cost Benchmarker — FastAPI port 8715"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8715

def build_html():
    random.seed(99)

    # Simulated daily cloud cost over 30 days (USD)
    days = list(range(1, 31))
    compute_costs = [120 + 40 * math.sin(d * 0.3) + random.gauss(0, 8) for d in days]
    storage_costs  = [18 + 0.4 * d + random.gauss(0, 1.5) for d in days]
    network_costs  = [9  + 5  * math.cos(d * 0.5) + random.gauss(0, 1.2) for d in days]
    total_costs    = [compute_costs[i] + storage_costs[i] + network_costs[i] for i in range(len(days))]

    # Instance benchmark table
    instance_types = [
        ("BM.GPU.A100-v2.8",  "A100 x8",  "8xA100",  3.20,  312.0, "Training"),
        ("VM.GPU3.4",         "V100 x4",  "4xV100",  1.28,  112.0, "Fine-tune"),
        ("VM.GPU.A10.2",      "A10 x2",   "2xA10",   0.56,   46.4, "Inference"),
        ("VM.Standard3.Flex", "CPU 64c",  "None",    0.21,    0.0, "Preprocess"),
        ("BM.HPC2.36",        "HPC CPU",  "None",    0.48,    0.0, "Sim"),
    ]

    # SVG stacked area chart for costs
    W, H = 580, 180
    pad = 44
    n = len(days)
    max_cost = max(total_costs) + 10
    min_cost = 0

    def sx(i): return pad + (i / (n - 1)) * (W - 2 * pad)
    def sy(v): return H - pad - (v / max_cost) * (H - 2 * pad)

    # Draw areas bottom-up: network, storage, compute
    def area_pts(base_list, top_list):
        fwd  = " ".join(f"{sx(i):.1f},{sy(top_list[i]):.1f}"  for i in range(n))
        back = " ".join(f"{sx(i):.1f},{sy(base_list[i]):.1f}" for i in range(n - 1, -1, -1))
        return fwd + " " + back

    zero_list    = [0.0] * n
    net_top      = network_costs
    store_top    = [network_costs[i] + storage_costs[i] for i in range(n)]
    compute_top  = total_costs

    area_net     = area_pts(zero_list, net_top)
    area_storage = area_pts(net_top, store_top)
    area_compute = area_pts(store_top, compute_top)

    total_line_pts = " ".join(f"{sx(i):.1f},{sy(total_costs[i]):.1f}" for i in range(n))

    # Y-axis gridlines
    gridlines = ""
    for gv in [50, 100, 150, 200]:
        gy = sy(gv)
        if pad < gy < H - pad:
            gridlines += f'<line x1="{pad}" y1="{gy:.1f}" x2="{W-pad}" y2="{gy:.1f}" stroke="#1e3a5f" stroke-width="1" stroke-dasharray="4,3"/>'
            gridlines += f'<text x="{pad-4}" y="{gy+4:.1f}" fill="#475569" font-size="9" text-anchor="end">${gv}</text>'

    # X-axis day labels every 5 days
    xlabels = ""
    for i in range(0, n, 5):
        xlabels += f'<text x="{sx(i):.1f}" y="{H-pad+14}" fill="#475569" font-size="9" text-anchor="middle">d{days[i]}</text>'

    # Cost efficiency: cost per TFLOP-hour
    eff_bars = ""
    bar_W2, bar_H2 = 580, 130
    bpad = 40
    inst_n = len(instance_types)
    bw = (bar_W2 - 2 * bpad) / inst_n - 4
    max_eff = max((row[3] / (row[4] + 0.001)) for row in instance_types) * 1.2
    for j, row in enumerate(instance_types):
        eff = row[3] / (row[4] + 0.001) if row[4] > 0 else row[3] / 1.0
        bx  = bpad + j * ((bar_W2 - 2 * bpad) / inst_n)
        bh  = max(4, (eff / max_eff) * (bar_H2 - 2 * bpad))
        by  = bar_H2 - bpad - bh
        colors = ["#C74634", "#38bdf8", "#22c55e", "#a78bfa", "#fb923c"]
        eff_bars += f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bw:.1f}" height="{bh:.1f}" fill="{colors[j % len(colors)]}" rx="3"/>'
        eff_bars += f'<text x="{bx + bw/2:.1f}" y="{bar_H2-bpad+12}" fill="#94a3b8" font-size="8" text-anchor="middle">{row[0][:10]}</text>'
        eff_bars += f'<text x="{bx + bw/2:.1f}" y="{by-3:.1f}" fill="#e2e8f0" font-size="8" text-anchor="middle">${eff:.3f}</text>'

    # Summary stats
    total_30d   = sum(total_costs)
    avg_daily   = total_30d / len(days)
    peak_day    = days[total_costs.index(max(total_costs))]
    cheapest_inst = min(instance_types, key=lambda r: r[3])

    # Instance table rows
    inst_rows = ""
    for row in instance_types:
        tflops_str = f"{row[4]:.0f}" if row[4] > 0 else "—"
        eff_str    = f"${row[3] / row[4]:.4f}/TFLOP" if row[4] > 0 else "N/A"
        inst_rows += f"<tr><td>{row[0]}</td><td>{row[1]}</td><td>{row[2]}</td><td>${row[3]:.2f}/hr</td><td>{tflops_str}</td><td>{eff_str}</td><td><span class='badge-use'>{row[5]}</span></td></tr>\n"

    return f"""<!DOCTYPE html><html><head><title>Cloud Cost Benchmarker</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui,sans-serif}}
h1{{color:#C74634;padding:20px 20px 4px;margin:0;font-size:1.6rem}}
.subtitle{{color:#94a3b8;padding:0 20px 16px;font-size:0.85rem}}
h2{{color:#38bdf8;margin:0 0 10px;font-size:1rem}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;padding:0 20px 12px}}
.card{{background:#1e293b;padding:16px 20px;border-radius:8px}}
.stat{{font-size:1.8rem;font-weight:700;color:#f1f5f9}}
.stat-label{{font-size:0.75rem;color:#64748b;text-transform:uppercase;letter-spacing:.05em;margin-top:2px}}
.good{{color:#22c55e}}.warn{{color:#f59e0b}}.accent{{color:#38bdf8}}
.chart-card{{background:#1e293b;padding:16px 20px;margin:0 20px 12px;border-radius:8px}}
.legend{{display:flex;gap:16px;margin-bottom:8px;font-size:0.75rem}}
.dot{{width:10px;height:10px;border-radius:2px;display:inline-block;margin-right:4px;vertical-align:middle}}
table{{width:100%;border-collapse:collapse;font-size:0.82rem}}
th{{color:#64748b;text-align:left;padding:6px 8px;border-bottom:1px solid #334155}}
td{{padding:5px 8px;border-bottom:1px solid #1e293b}}
.badge-use{{display:inline-block;padding:1px 7px;border-radius:9999px;font-size:0.7rem;font-weight:600;background:#1e3a5f;color:#7dd3fc}}
</style></head>
<body>
<h1>Cloud Cost Benchmarker</h1>
<div class="subtitle">OCI instance cost analysis for robotics AI workloads — port {PORT}</div>

<div class="grid">
  <div class="card"><div class="stat warn">${total_30d:,.1f}</div><div class="stat-label">30-Day Total</div></div>
  <div class="card"><div class="stat accent">${avg_daily:.1f}</div><div class="stat-label">Avg Daily Cost</div></div>
  <div class="card"><div class="stat warn">Day {peak_day}</div><div class="stat-label">Peak Cost Day</div></div>
  <div class="card"><div class="stat good">{cheapest_inst[0][:14]}</div><div class="stat-label">Cheapest Instance</div></div>
</div>

<div class="chart-card">
  <h2>Daily Cost Breakdown (30 Days)</h2>
  <div class="legend">
    <span><span class="dot" style="background:#38bdf8"></span>Compute</span>
    <span><span class="dot" style="background:#a78bfa"></span>Storage</span>
    <span><span class="dot" style="background:#fb923c"></span>Network</span>
    <span><span class="dot" style="background:#e2e8f0"></span>Total</span>
  </div>
  <svg width="100%" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg">
    {gridlines}
    <polygon points="{area_compute}" fill="#38bdf8" fill-opacity="0.25"/>
    <polygon points="{area_storage}" fill="#a78bfa" fill-opacity="0.35"/>
    <polygon points="{area_net}"     fill="#fb923c" fill-opacity="0.45"/>
    <polyline points="{total_line_pts}" fill="none" stroke="#e2e8f0" stroke-width="1.5" stroke-linejoin="round"/>
    <line x1="{pad}" y1="{pad}" x2="{pad}" y2="{H-pad}" stroke="#334155" stroke-width="1"/>
    <line x1="{pad}" y1="{H-pad}" x2="{W-pad}" y2="{H-pad}" stroke="#334155" stroke-width="1"/>
    {xlabels}
  </svg>
</div>

<div class="chart-card">
  <h2>Cost per TFLOP-Hour by Instance Type</h2>
  <svg width="100%" viewBox="0 0 {bar_W2} {bar_H2}" xmlns="http://www.w3.org/2000/svg">
    <line x1="{bpad}" y1="{bpad}" x2="{bpad}" y2="{bar_H2-bpad}" stroke="#334155" stroke-width="1"/>
    <line x1="{bpad}" y1="{bar_H2-bpad}" x2="{bar_W2-bpad}" y2="{bar_H2-bpad}" stroke="#334155" stroke-width="1"/>
    {eff_bars}
  </svg>
</div>

<div class="chart-card">
  <h2>Instance Benchmark Reference</h2>
  <table>
    <thead><tr><th>Instance</th><th>GPU</th><th>Memory</th><th>Rate</th><th>TFLOPS</th><th>Efficiency</th><th>Workload</th></tr></thead>
    <tbody>{inst_rows}</tbody>
  </table>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Cloud Cost Benchmarker")
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
