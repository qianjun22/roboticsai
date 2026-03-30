"""Cost Optimization Report v2 — FastAPI port 8697"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8697

random.seed(99)

def build_html():
    # 30-day cost simulation across OCI services
    days = 30
    # Daily GPU compute cost (A100 hours)
    gpu_cost = [round(180 + 40 * math.sin(i * math.pi / 7) + random.uniform(-15, 15), 2) for i in range(days)]
    # Storage cost (steady + growth)
    storage_cost = [round(12 + i * 0.35 + random.uniform(-1, 1), 2) for i in range(days)]
    # Inference API cost
    inference_cost = [round(55 + 20 * math.cos(i * math.pi / 10) + random.uniform(-8, 8), 2) for i in range(days)]
    # Network egress
    network_cost = [round(8 + 3 * math.sin(i * math.pi / 5) + random.uniform(-1, 1), 2) for i in range(days)]

    total_by_day = [gpu_cost[i] + storage_cost[i] + inference_cost[i] + network_cost[i] for i in range(days)]

    total_gpu = sum(gpu_cost)
    total_storage = sum(storage_cost)
    total_inference = sum(inference_cost)
    total_network = sum(network_cost)
    grand_total = total_gpu + total_storage + total_inference + total_network

    # Savings opportunities
    spot_savings = round(total_gpu * 0.31, 2)
    rightsizing_savings = round(total_inference * 0.18, 2)
    lifecycle_savings = round(total_storage * 0.22, 2)
    total_savings = spot_savings + rightsizing_savings + lifecycle_savings

    # SVG stacked area chart for daily costs (600x160)
    cw, ch = 580, 150
    pl, pr, pt, pb = 55, 15, 15, 30
    pw = cw - pl - pr
    ph = ch - pt - pb
    max_total = max(total_by_day) * 1.05

    def dx(i): return pl + i * pw / (days - 1)

    def dy(v): return pt + ph * (1 - v / max_total)

    # Build stacked area paths bottom-up: network, inference, storage, gpu
    def area_points_top(base_list, add_list):
        pts = [(dx(i), dy(base_list[i] + add_list[i])) for i in range(days)]
        return pts

    def pts_to_poly(top_pts, bot_pts):
        forward = " ".join(f"{x:.1f},{y:.1f}" for x, y in top_pts)
        backward = " ".join(f"{x:.1f},{y:.1f}" for x, y in reversed(bot_pts))
        return forward + " " + backward

    zero_pts = [(dx(i), dy(0)) for i in range(days)]
    net_top = area_points_top([0]*days, network_cost)
    inf_top = area_points_top(network_cost, inference_cost)
    sto_top = area_points_top([network_cost[i]+inference_cost[i] for i in range(days)], storage_cost)
    gpu_top = area_points_top([network_cost[i]+inference_cost[i]+storage_cost[i] for i in range(days)], gpu_cost)

    net_poly = pts_to_poly(net_top, zero_pts)
    inf_poly = pts_to_poly(inf_top, net_top)
    sto_poly = pts_to_poly(sto_top, inf_top)
    gpu_poly = pts_to_poly(gpu_top, sto_top)

    total_line = " ".join(f"{dx(i):.1f},{dy(total_by_day[i]):.1f}" for i in range(days))

    # Y-axis grid
    grid = ""
    for frac in [0.25, 0.5, 0.75, 1.0]:
        y = pt + ph * (1 - frac)
        lbl = f"${int(frac * max_total)}"
        grid += f'<line x1="{pl}" y1="{y:.1f}" x2="{pl+pw}" y2="{y:.1f}" stroke="#334155" stroke-width="1" stroke-dasharray="4,4"/>'
        grid += f'<text x="{pl-5}" y="{y+4:.1f}" fill="#94a3b8" font-size="9" text-anchor="end">{lbl}</text>'

    # X-axis sample labels (every 5 days)
    xlabels = ""
    for i in range(0, days, 5):
        xlabels += f'<text x="{dx(i):.1f}" y="{pt+ph+18:.1f}" fill="#94a3b8" font-size="9" text-anchor="middle">D{i+1}</text>'

    # Donut chart SVG for cost breakdown
    slices = [
        (total_gpu, "#6366f1", "GPU Compute"),
        (total_inference, "#22d3ee", "Inference API"),
        (total_storage, "#f59e0b", "Storage"),
        (total_network, "#34d399", "Network"),
    ]
    total_for_donut = sum(v for v, _, _ in slices)
    cx_d, cy_d, r_out, r_in = 110, 110, 90, 52
    donut_paths = ""
    angle = -math.pi / 2
    for val, color, label in slices:
        sweep = 2 * math.pi * val / total_for_donut
        x1 = cx_d + r_out * math.cos(angle)
        y1 = cy_d + r_out * math.sin(angle)
        x2 = cx_d + r_out * math.cos(angle + sweep)
        y2 = cy_d + r_out * math.sin(angle + sweep)
        xi1 = cx_d + r_in * math.cos(angle)
        yi1 = cy_d + r_in * math.sin(angle)
        xi2 = cx_d + r_in * math.cos(angle + sweep)
        yi2 = cy_d + r_in * math.sin(angle + sweep)
        large = 1 if sweep > math.pi else 0
        path = (f'M {x1:.2f} {y1:.2f} '
                f'A {r_out} {r_out} 0 {large} 1 {x2:.2f} {y2:.2f} '
                f'L {xi2:.2f} {yi2:.2f} '
                f'A {r_in} {r_in} 0 {large} 0 {xi1:.2f} {yi1:.2f} Z')
        donut_paths += f'<path d="{path}" fill="{color}" stroke="#0f172a" stroke-width="2"/>'
        mid_angle = angle + sweep / 2
        lx = cx_d + (r_out + 12) * math.cos(mid_angle)
        ly = cy_d + (r_out + 12) * math.sin(mid_angle)
        pct = val / total_for_donut * 100
        donut_paths += f'<text x="{lx:.1f}" y="{ly:.1f}" fill="{color}" font-size="9" text-anchor="middle">{pct:.0f}%</text>'
        angle += sweep

    # Savings recommendation rows
    savings_rows = [
        ("Spot/Preemptible GPU Instances", f"${spot_savings:,.0f}", "Use OCI preemptible A100s for training (non-critical)", "#22c55e"),
        ("Inference Right-Sizing", f"${rightsizing_savings:,.0f}", "Reduce inference replica count during off-peak (10pm-6am)", "#22c55e"),
        ("Storage Lifecycle Policy", f"${lifecycle_savings:,.0f}", "Move checkpoints >30d to Object Storage Standard tier", "#f59e0b"),
    ]
    savings_html = ""
    for name, amt, action, color in savings_rows:
        savings_html += f"""<tr>
          <td style="padding:6px 12px;color:#e2e8f0">{name}</td>
          <td style="padding:6px 12px;color:{color};font-weight:700">{amt}/mo</td>
          <td style="padding:6px 12px;color:#94a3b8;font-size:0.85rem">{action}</td>
        </tr>"""

    return f"""<!DOCTYPE html><html><head><title>Cost Optimization Report v2</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui}}
h1{{color:#C74634;margin:0;padding:20px 24px 8px;font-size:1.6rem}}
h2{{color:#38bdf8;font-size:1rem;margin:0 0 12px}}
.card{{background:#1e293b;padding:20px;margin:12px;border-radius:10px;display:inline-block;vertical-align:top}}
.stat{{font-size:1.9rem;font-weight:700;color:#22d3ee}}
.stat-label{{font-size:0.75rem;color:#64748b;margin-top:2px}}
.grid{{display:flex;flex-wrap:wrap}}
table{{border-collapse:collapse;width:100%}}
</style></head>
<body>
<h1>OCI Robot Cloud — Cost Optimization Report v2</h1>
<p style="color:#64748b;padding:0 24px;margin:0 0 4px">30-day rolling window &bull; All costs in USD &bull; Updated {days}d ago</p>

<div class="grid">
  <div class="card">
    <div class="stat-label">Total 30-Day Spend</div>
    <div class="stat">${grand_total:,.0f}</div>
    <div style="color:#f59e0b;font-size:0.8rem;margin-top:4px">▲ +8.3% vs prior period</div>
  </div>
  <div class="card">
    <div class="stat-label">GPU Compute</div>
    <div class="stat" style="color:#6366f1">${total_gpu:,.0f}</div>
    <div style="color:#94a3b8;font-size:0.8rem;margin-top:4px">{total_gpu/grand_total:.0%} of total</div>
  </div>
  <div class="card">
    <div class="stat-label">Inference API</div>
    <div class="stat" style="color:#22d3ee">${total_inference:,.0f}</div>
    <div style="color:#94a3b8;font-size:0.8rem;margin-top:4px">{total_inference/grand_total:.0%} of total</div>
  </div>
  <div class="card">
    <div class="stat-label">Identified Savings</div>
    <div class="stat" style="color:#22c55e">${total_savings:,.0f}</div>
    <div style="color:#22c55e;font-size:0.8rem;margin-top:4px">{total_savings/grand_total:.0%} optimization opportunity</div>
  </div>
</div>

<div class="card" style="margin:12px;display:block">
  <h2>Daily Cost Breakdown (Stacked) — Last 30 Days</h2>
  <svg width="{cw}" height="{ch}">
    {grid}
    {xlabels}
    <polygon points="{gpu_poly}" fill="#6366f1" opacity="0.7"/>
    <polygon points="{sto_poly}" fill="#f59e0b" opacity="0.7"/>
    <polygon points="{inf_poly}" fill="#22d3ee" opacity="0.7"/>
    <polygon points="{net_poly}" fill="#34d399" opacity="0.7"/>
    <polyline points="{total_line}" fill="none" stroke="#f1f5f9" stroke-width="1.5" stroke-dasharray="5,3"/>
    <text x="{pl}" y="{pt-2}" fill="#6366f1" font-size="9">GPU</text>
    <text x="{pl+32}" y="{pt-2}" fill="#f59e0b" font-size="9">Storage</text>
    <text x="{pl+82}" y="{pt-2}" fill="#22d3ee" font-size="9">Inference</text>
    <text x="{pl+148}" y="{pt-2}" fill="#34d399" font-size="9">Network</text>
  </svg>
</div>

<div style="display:flex;flex-wrap:wrap">
  <div class="card" style="margin:12px">
    <h2>Cost Distribution</h2>
    <svg width="220" height="220">
      {donut_paths}
      <text x="{cx_d}" y="{cy_d-8}" fill="#e2e8f0" font-size="11" text-anchor="middle" font-weight="700">${grand_total:,.0f}</text>
      <text x="{cx_d}" y="{cy_d+10}" fill="#64748b" font-size="9" text-anchor="middle">total</text>
    </svg>
    <div style="margin-top:6px">
      {''.join(f'<div style="margin:3px 0"><span style="display:inline-block;width:10px;height:10px;background:{c};border-radius:2px;margin-right:6px"></span><span style="color:#94a3b8;font-size:0.8rem">{n}</span></div>' for _, c, n in slices)}
    </div>
  </div>

  <div class="card" style="margin:12px;flex:1;min-width:300px">
    <h2>Cost/Performance Ratios</h2>
    <table>
      <tr><td style="padding:4px 16px 4px 0;color:#64748b">Cost per Training Step</td><td style="color:#22d3ee">$0.0043</td></tr>
      <tr><td style="padding:4px 16px 4px 0;color:#64748b">Cost per 10K Inference Calls</td><td style="color:#22d3ee">$1.24</td></tr>
      <tr><td style="padding:4px 16px 4px 0;color:#64748b">Cost per GB Dataset Stored</td><td style="color:#22d3ee">$0.018</td></tr>
      <tr><td style="padding:4px 16px 4px 0;color:#64748b">Cost per DAgger Iteration</td><td style="color:#22d3ee">$38.50</td></tr>
      <tr><td style="padding:4px 16px 4px 0;color:#64748b">Cost per Eval Episode</td><td style="color:#22d3ee">$0.11</td></tr>
      <tr><td style="padding:4px 16px 4px 0;color:#64748b">GPU Utilization (avg)</td><td style="color:#22c55e">87%</td></tr>
      <tr><td style="padding:4px 16px 4px 0;color:#64748b">Idle GPU Hours (wasted)</td><td style="color:#ef4444">63 hrs/mo</td></tr>
      <tr><td style="padding:4px 16px 4px 0;color:#64748b">On-Demand vs Reserved</td><td style="color:#f59e0b">100% on-demand</td></tr>
    </table>
  </div>
</div>

<div class="card" style="margin:12px;display:block">
  <h2>Savings Recommendations</h2>
  <table>
    <thead><tr>
      <th style="padding:6px 12px;color:#64748b;text-align:left;font-weight:500">Opportunity</th>
      <th style="padding:6px 12px;color:#64748b;text-align:left;font-weight:500">Est. Monthly Savings</th>
      <th style="padding:6px 12px;color:#64748b;text-align:left;font-weight:500">Action</th>
    </tr></thead>
    <tbody>{savings_html}</tbody>
  </table>
  <div style="margin-top:12px;padding:10px;background:#0f172a;border-radius:6px;border-left:3px solid #22c55e">
    <span style="color:#22c55e;font-weight:700">Projected optimized monthly spend: ${grand_total - total_savings:,.0f}</span>
    <span style="color:#64748b;font-size:0.8rem"> &nbsp;({total_savings/grand_total:.0%} reduction from ${grand_total:,.0f})</span>
  </div>
</div>

<p style="color:#334155;font-size:0.7rem;padding:8px 24px">OCI Robot Cloud — Cost Optimization Report v2 — port {PORT}</p>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Cost Optimization Report v2")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return build_html()

    @app.get("/health")
    def health():
        return {"status": "ok", "port": PORT, "service": "cost_optimization_report_v2"}

    @app.get("/summary")
    def summary():
        random.seed(99)
        gpu_cost = [round(180 + 40 * math.sin(i * math.pi / 7) + random.uniform(-15, 15), 2) for i in range(30)]
        storage_cost = [round(12 + i * 0.35 + random.uniform(-1, 1), 2) for i in range(30)]
        inference_cost = [round(55 + 20 * math.cos(i * math.pi / 10) + random.uniform(-8, 8), 2) for i in range(30)]
        network_cost = [round(8 + 3 * math.sin(i * math.pi / 5) + random.uniform(-1, 1), 2) for i in range(30)]
        total_gpu = sum(gpu_cost)
        total_inference = sum(inference_cost)
        total_storage = sum(storage_cost)
        total_network = sum(network_cost)
        grand_total = total_gpu + total_storage + total_inference + total_network
        return {
            "period_days": 30,
            "grand_total_usd": round(grand_total, 2),
            "gpu_compute_usd": round(total_gpu, 2),
            "inference_api_usd": round(total_inference, 2),
            "storage_usd": round(total_storage, 2),
            "network_usd": round(total_network, 2),
            "identified_savings_usd": round(total_gpu * 0.31 + total_inference * 0.18 + total_storage * 0.22, 2),
        }

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
