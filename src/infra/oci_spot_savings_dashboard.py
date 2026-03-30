"""OCI Spot Savings Dashboard — FastAPI port 8703"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8703

# OCI GPU shapes and their on-demand vs preemptible pricing
SHAPES = [
    {"name": "BM.GPU.A100-v2.8",  "od": 32.00, "spot": 9.60,  "vcpu": 128, "mem": 2048},
    {"name": "BM.GPU4.8",          "od": 28.40, "spot": 8.52,  "vcpu": 64,  "mem": 1024},
    {"name": "VM.GPU3.4",          "od": 12.60, "spot": 3.78,  "vcpu": 24,  "mem": 360},
    {"name": "VM.GPU3.2",          "od": 6.30,  "spot": 1.89,  "vcpu": 12,  "mem": 180},
    {"name": "BM.GPU.H100.8",      "od": 48.00, "spot": 14.40, "vcpu": 160, "mem": 2048},
]

WORKLOADS = ["Fine-Tuning", "SDG", "Eval", "Inference", "DAgger", "HPO"]

def generate_daily_savings(days=30, seed=77):
    """Generate 30-day spot vs on-demand cost comparison."""
    random.seed(seed)
    data = []
    for d in range(days):
        t = d / (days - 1)
        # On-demand baseline with weekly pattern
        weekday_factor = 1.0 + 0.25 * math.sin(2 * math.pi * d / 7)
        od_base = 840 * weekday_factor * (1 + 0.08 * math.sin(2 * math.pi * t))
        od_cost = od_base + random.gauss(0, 30)
        # Spot savings 60-72% with interruption noise
        discount = 0.68 + 0.06 * math.sin(2 * math.pi * d / 14) + random.gauss(0, 0.025)
        spot_cost = od_cost * (1 - max(0.55, min(0.75, discount)))
        # Interruption events (random outages)
        interruptions = max(0, int(random.gauss(1.2, 0.8)))
        data.append({
            "day": d + 1,
            "od_cost": round(max(200, od_cost), 2),
            "spot_cost": round(max(80, spot_cost), 2),
            "saved": round(max(100, od_cost - spot_cost), 2),
            "interruptions": interruptions,
            "discount_pct": round(discount * 100, 1)
        })
    return data

def generate_shape_utilization():
    """Spot instance utilization by shape over past week."""
    random.seed(55)
    util = {}
    for shape in SHAPES:
        hours = []
        for h in range(168):  # 7 days * 24h
            base = 0.72 + 0.18 * math.sin(2 * math.pi * h / 24)
            hours.append(round(max(0.1, min(1.0, base + random.gauss(0, 0.08))), 3))
        util[shape["name"]] = hours
    return util

def build_html():
    daily = generate_daily_savings()
    total_od = sum(d["od_cost"] for d in daily)
    total_spot = sum(d["spot_cost"] for d in daily)
    total_saved = total_od - total_spot
    avg_discount = total_saved / total_od * 100
    total_interruptions = sum(d["interruptions"] for d in daily)

    # SVG line chart for daily costs (30 days)
    svg_w, svg_h = 640, 200
    pad_l, pad_r, pad_t, pad_b = 60, 20, 20, 30
    chart_w = svg_w - pad_l - pad_r
    chart_h = svg_h - pad_t - pad_b

    max_cost = max(d["od_cost"] for d in daily) * 1.05
    min_cost = min(d["spot_cost"] for d in daily) * 0.95

    def cx(day_idx):
        return pad_l + (day_idx / (len(daily) - 1)) * chart_w

    def cy(val):
        return pad_t + chart_h - (val - min_cost) / (max_cost - min_cost) * chart_h

    od_points = " ".join(f"{cx(i):.1f},{cy(d['od_cost']):.1f}" for i, d in enumerate(daily))
    spot_points = " ".join(f"{cx(i):.1f},{cy(d['spot_cost']):.1f}" for i, d in enumerate(daily))

    # Shaded area between lines (simplified as polygon)
    top_pts = " ".join(f"{cx(i):.1f},{cy(d['od_cost']):.1f}" for i, d in enumerate(daily))
    bot_pts = " ".join(f"{cx(i):.1f},{cy(d['spot_cost']):.1f}" for i, d in reversed(list(enumerate(daily))))
    fill_poly = top_pts + " " + bot_pts

    # Grid
    grid_lines = ""
    for pct in [0, 25, 50, 75, 100]:
        val = min_cost + (pct / 100) * (max_cost - min_cost)
        y = cy(val)
        grid_lines += f'<line x1="{pad_l}" y1="{y:.1f}" x2="{svg_w - pad_r}" y2="{y:.1f}" stroke="#334155" stroke-width="1"/>'
        grid_lines += f'<text x="{pad_l - 5}" y="{y + 4:.1f}" text-anchor="end" fill="#64748b" font-size="9">${val:.0f}</text>'

    # Day labels
    day_labels = ""
    for i in range(0, 30, 5):
        x = cx(i)
        day_labels += f'<text x="{x:.1f}" y="{svg_h - 4}" text-anchor="middle" fill="#64748b" font-size="9">D{i+1}</text>'

    # Bar chart for savings by shape
    bar_shapes = SHAPES
    bar_h_max = 120
    bar_w2 = 60
    bar_gap2 = 20
    bars2_svg = ""
    shape_colors = ["#38bdf8", "#4ade80", "#a78bfa", "#fb923c", "#f472b6"]
    for i, shape in enumerate(bar_shapes):
        saving_pct = (shape["od"] - shape["spot"]) / shape["od"]
        bh = int(saving_pct * bar_h_max)
        x = 40 + i * (bar_w2 + bar_gap2)
        y = 20 + bar_h_max - bh
        bars2_svg += f'<rect x="{x}" y="{y}" width="{bar_w2}" height="{bh}" fill="{shape_colors[i]}" rx="3" opacity="0.85"/>'
        bars2_svg += f'<text x="{x + bar_w2//2}" y="{y - 5}" text-anchor="middle" fill="#e2e8f0" font-size="11" font-weight="600">{int(saving_pct*100)}%</text>'
        short = shape["name"].split(".")[2] if len(shape["name"].split(".")) > 2 else shape["name"][:8]
        bars2_svg += f'<text x="{x + bar_w2//2}" y="{20 + bar_h_max + 14}" text-anchor="middle" fill="#94a3b8" font-size="8">{short}</text>'
        bars2_svg += f'<text x="{x + bar_w2//2}" y="{20 + bar_h_max + 25}" text-anchor="middle" fill="#64748b" font-size="8">${shape["spot"]:.2f}/h</text>'

    # Workload breakdown table
    random.seed(88)
    workload_rows = ""
    for wl in WORKLOADS:
        od_h = random.uniform(20, 120)
        spot_h = od_h * random.uniform(0.92, 1.0)
        od_cost_wl = od_h * 28.4
        spot_cost_wl = spot_h * 8.52
        saved_wl = od_cost_wl - spot_cost_wl
        interrupts = random.randint(0, 4)
        workload_rows += f"""
        <tr>
          <td style="padding:5px 12px;color:#e2e8f0">{wl}</td>
          <td style="text-align:center;padding:5px 8px;color:#94a3b8">{od_h:.0f}h</td>
          <td style="text-align:center;padding:5px 8px;color:#fb923c">${od_cost_wl:,.0f}</td>
          <td style="text-align:center;padding:5px 8px;color:#4ade80">${spot_cost_wl:,.0f}</td>
          <td style="text-align:center;padding:5px 8px;color:#38bdf8;font-weight:700">${saved_wl:,.0f}</td>
          <td style="text-align:center;padding:5px 8px;color:{"#f87171" if interrupts>2 else "#facc15" if interrupts>0 else "#4ade80"}">{interrupts}</td>
        </tr>"""

    # Shape pricing table
    shape_rows = ""
    for shape in SHAPES:
        monthly_savings = (shape["od"] - shape["spot"]) * 24 * 30
        shape_rows += f"""
        <tr>
          <td style="padding:5px 12px;color:#e2e8f0;font-family:monospace;font-size:11px">{shape["name"]}</td>
          <td style="text-align:center;padding:5px 8px;color:#94a3b8">{shape["vcpu"]}</td>
          <td style="text-align:center;padding:5px 8px;color:#94a3b8">{shape["mem"]}GB</td>
          <td style="text-align:center;padding:5px 8px;color:#fb923c">${shape["od"]:.2f}/h</td>
          <td style="text-align:center;padding:5px 8px;color:#4ade80">${shape["spot"]:.2f}/h</td>
          <td style="text-align:center;padding:5px 8px;color:#38bdf8;font-weight:700">${monthly_savings:,.0f}/mo</td>
        </tr>"""

    bars2_total_w = 40 + len(SHAPES) * (bar_w2 + bar_gap2)

    return f"""<!DOCTYPE html><html><head><title>OCI Spot Savings Dashboard</title>
<meta charset="utf-8">
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui,sans-serif}}
h1{{color:#C74634;margin:0;padding:20px 24px 4px;font-size:22px}}
.subtitle{{color:#64748b;padding:0 24px 16px;font-size:13px}}
h2{{color:#38bdf8;margin:0 0 12px;font-size:15px}}
.card{{background:#1e293b;padding:20px;margin:10px 16px;border-radius:8px;border:1px solid #334155}}
.stat-row{{display:flex;gap:12px;margin:0 16px 4px}}
.stat{{background:#1e293b;border-radius:6px;padding:12px 16px;flex:1;text-align:center;border:1px solid #334155}}
.stat-val{{font-size:24px;font-weight:700}}
.stat-lbl{{font-size:11px;color:#64748b;margin-top:2px}}
table{{border-collapse:collapse;width:100%;font-size:12px}}
th{{background:#0f172a;padding:6px 8px;color:#94a3b8;font-weight:600}}
tr:nth-child(even){{background:#162032}}
.green{{color:#4ade80}}.orange{{color:#fb923c}}.blue{{color:#38bdf8}}
</style></head>
<body>
<h1>OCI Spot Savings Dashboard</h1>
<div class="subtitle">Preemptible GPU instance cost analysis for robotics training workloads | 30-day window | Updated 2026-03-30</div>

<div class="stat-row">
  <div class="stat"><div class="stat-val green">${total_saved:,.0f}</div><div class="stat-lbl">30-Day Total Saved</div></div>
  <div class="stat"><div class="stat-val" style="color:#fb923c">${total_od:,.0f}</div><div class="stat-lbl">On-Demand Cost</div></div>
  <div class="stat"><div class="stat-val green">${total_spot:,.0f}</div><div class="stat-lbl">Spot Actual Cost</div></div>
  <div class="stat"><div class="stat-val blue">{avg_discount:.1f}%</div><div class="stat-lbl">Avg Discount</div></div>
  <div class="stat"><div class="stat-val" style="color:#facc15">{total_interruptions}</div><div class="stat-lbl">Interruptions (30d)</div></div>
</div>

<div class="card">
  <h2>Daily Cost Comparison — On-Demand vs Spot (USD)</h2>
  <svg width="{svg_w}" height="{svg_h}" style="display:block">
    {grid_lines}
    {day_labels}
    <polygon points="{fill_poly}" fill="#38bdf8" opacity="0.08"/>
    <polyline points="{od_points}" fill="none" stroke="#fb923c" stroke-width="2"/>
    <polyline points="{spot_points}" fill="none" stroke="#4ade80" stroke-width="2"/>
    <rect x="{pad_l + 10}" y="{pad_t + 5}" width="90" height="30" fill="#0f172a" rx="4"/>
    <line x1="{pad_l + 15}" y1="{pad_t + 15}" x2="{pad_l + 28}" y2="{pad_t + 15}" stroke="#fb923c" stroke-width="2"/>
    <text x="{pad_l + 32}" y="{pad_t + 19}" fill="#e2e8f0" font-size="9">On-Demand</text>
    <line x1="{pad_l + 15}" y1="{pad_t + 28}" x2="{pad_l + 28}" y2="{pad_t + 28}" stroke="#4ade80" stroke-width="2"/>
    <text x="{pad_l + 32}" y="{pad_t + 32}" fill="#e2e8f0" font-size="9">Spot</text>
  </svg>
</div>

<div class="card">
  <h2>Spot Discount % by GPU Shape</h2>
  <svg width="{bars2_total_w}" height="{20 + bar_h_max + 40}" style="display:block">
    {''.join(f'<line x1="38" y1="{20 + bar_h_max - int(pct/100*bar_h_max)}" x2="{bars2_total_w-10}" y2="{20 + bar_h_max - int(pct/100*bar_h_max)}" stroke="#334155" stroke-width="1"/><text x="32" y="{20 + bar_h_max - int(pct/100*bar_h_max) + 4}" text-anchor="end" fill="#64748b" font-size="9">{pct}%</text>' for pct in [0,25,50,75,100])}
    {bars2_svg}
  </svg>
</div>

<div class="card">
  <h2>Workload Breakdown (Past 30 Days)</h2>
  <table>
    <thead><tr>
      <th style="text-align:left">Workload</th>
      <th>GPU Hours</th>
      <th>OD Cost</th>
      <th>Spot Cost</th>
      <th>Saved</th>
      <th>Interrupts</th>
    </tr></thead>
    <tbody>{workload_rows}</tbody>
  </table>
</div>

<div class="card" style="margin-bottom:20px">
  <h2>Shape Pricing Reference</h2>
  <table>
    <thead><tr>
      <th style="text-align:left">Shape</th>
      <th>vCPU</th>
      <th>Memory</th>
      <th>On-Demand</th>
      <th>Spot</th>
      <th>Monthly Savings</th>
    </tr></thead>
    <tbody>{shape_rows}</tbody>
  </table>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="OCI Spot Savings Dashboard")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return build_html()

    @app.get("/health")
    def health():
        return {"status": "ok", "port": PORT}

    @app.get("/api/summary")
    def api_summary():
        daily = generate_daily_savings()
        total_od = sum(d["od_cost"] for d in daily)
        total_spot = sum(d["spot_cost"] for d in daily)
        return {
            "total_saved_usd": round(total_od - total_spot, 2),
            "on_demand_usd": round(total_od, 2),
            "spot_usd": round(total_spot, 2),
            "avg_discount_pct": round((total_od - total_spot) / total_od * 100, 1),
            "shapes": [{"name": s["name"], "od_per_hr": s["od"], "spot_per_hr": s["spot"]} for s in SHAPES]
        }

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
