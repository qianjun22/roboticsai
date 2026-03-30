"""OCI Reserved Instance Planner — FastAPI port 8763"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8763

# OCI GPU shape catalog
SHAPES = [
    {"shape": "BM.GPU.A100-v2.8",  "gpus": 8,  "on_demand": 32.00, "1yr_ri": 20.80, "3yr_ri": 14.40},
    {"shape": "BM.GPU4.8",          "gpus": 8,  "on_demand": 28.00, "1yr_ri": 18.20, "3yr_ri": 12.60},
    {"shape": "BM.GPU.H100.8",      "gpus": 8,  "on_demand": 52.00, "1yr_ri": 33.80, "3yr_ri": 23.40},
    {"shape": "VM.GPU3.4",           "gpus": 4,  "on_demand": 12.50, "1yr_ri": 8.13,  "3yr_ri": 5.63},
    {"shape": "VM.GPU.A10.2",        "gpus": 2,  "on_demand": 6.80,  "1yr_ri": 4.42,  "3yr_ri": 3.06},
]

def build_html():
    random.seed(42)
    months = 36

    # Simulate monthly GPU-hours demand: baseline + growth + seasonality + noise
    baseline = 4800
    demand = [
        round(baseline * (1 + 0.04 * m) + 600 * math.sin(2 * math.pi * m / 12) + random.uniform(-200, 200))
        for m in range(months)
    ]

    # Recommended RI coverage: 70% of smoothed demand (12-month rolling min)
    def rolling_min(series, w=3):
        return [min(series[max(0, i-w):i+1]) for i in range(len(series))]

    smooth = rolling_min(demand)
    ri_coverage = [int(v * 0.70) for v in smooth]
    on_demand_overage = [max(demand[i] - ri_coverage[i], 0) for i in range(months)]

    # Cost calculation ($/hr * hours)
    shape = SHAPES[0]  # A100
    # RI hours cost at 3yr rate, overage at on-demand rate
    monthly_cost_ri = [round(ri_coverage[i] * shape["3yr_ri"], 0) for i in range(months)]
    monthly_cost_od = [round(on_demand_overage[i] * shape["on_demand"], 0) for i in range(months)]
    monthly_cost_total = [monthly_cost_ri[i] + monthly_cost_od[i] for i in range(months)]
    monthly_cost_all_od = [round(demand[i] * shape["on_demand"], 0) for i in range(months)]
    total_savings = sum(monthly_cost_all_od) - sum(monthly_cost_total)
    savings_pct = round(100 * total_savings / max(sum(monthly_cost_all_od), 1), 1)

    # SVG demand + RI coverage chart
    svg_w, svg_h = 700, 150
    max_d = max(demand) * 1.1

    def to_pts(values):
        pts = []
        for i, v in enumerate(values):
            x = int(i * svg_w / (months - 1))
            y = svg_h - int(v / max_d * svg_h)
            pts.append(f"{x},{y}")
        return " ".join(pts)

    demand_pts = to_pts(demand)
    ri_pts = to_pts(ri_coverage)
    od_pts = to_pts(on_demand_overage)

    # Cost bar chart (36 bars, compressed)
    bar_w = svg_w / months
    cost_max = max(monthly_cost_total) * 1.1
    bars_ri = "".join(
        f"<rect x='{int(i*bar_w)}' y='{svg_h - int(monthly_cost_ri[i]/cost_max*svg_h)}' "
        f"width='{max(int(bar_w)-1,1)}' height='{int(monthly_cost_ri[i]/cost_max*svg_h)}' fill='#38bdf8' opacity='0.85'/>"
        for i in range(months)
    )
    bars_od = "".join(
        f"<rect x='{int(i*bar_w)}' y='{svg_h - int(monthly_cost_total[i]/cost_max*svg_h)}' "
        f"width='{max(int(bar_w)-1,1)}' height='{int(monthly_cost_od[i]/cost_max*svg_h)}' fill='#f59e0b' opacity='0.85'/>"
        for i in range(months)
    )

    # Shape comparison table
    shape_rows = "".join(
        f"<tr><td>{s['shape']}</td><td>{s['gpus']}</td>"
        f"<td>${s['on_demand']:.2f}</td><td>${s['1yr_ri']:.2f} ({round(100*(1-s['1yr_ri']/s['on_demand']))}%)</td>"
        f"<td>${s['3yr_ri']:.2f} ({round(100*(1-s['3yr_ri']/s['on_demand']))}%)</td></tr>"
        for s in SHAPES
    )

    return f"""<!DOCTYPE html><html><head><title>OCI Reserved Instance Planner</title>
<meta charset='utf-8'>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui,sans-serif}}
h1{{color:#C74634;padding:20px 20px 0;margin:0}}h2{{color:#38bdf8;margin-top:0}}
.card{{background:#1e293b;padding:20px;margin:10px;border-radius:8px}}
.grid2{{display:grid;grid-template-columns:1fr 1fr;gap:0}}
table{{width:100%;border-collapse:collapse}}th,td{{padding:7px 10px;border-bottom:1px solid #334155;text-align:left}}
th{{color:#94a3b8;font-size:0.82em}}
.metric{{font-size:2em;font-weight:bold;color:#f0f9ff}}
.label{{color:#94a3b8;font-size:0.8em;margin-bottom:4px}}
.green{{color:#22c55e}}.amber{{color:#f59e0b}}
</style></head>
<body>
<h1>OCI Reserved Instance Planner</h1>
<p style='color:#94a3b8;padding:0 20px;margin:4px 0 0'>Port {PORT} &mdash; 36-month GPU capacity &amp; cost optimization</p>

<div class='grid2'>
<div class='card'>
  <h2>3-Year Cost Summary (BM.GPU.A100-v2.8)</h2>
  <div style='display:flex;gap:28px;flex-wrap:wrap'>
    <div><div class='label'>Total RI+OD Cost</div><div class='metric'>${sum(monthly_cost_total):,.0f}</div></div>
    <div><div class='label'>All On-Demand Cost</div><div class='metric' style='color:#94a3b8'>${sum(monthly_cost_all_od):,.0f}</div></div>
    <div><div class='label'>Total Savings</div><div class='metric green'>${total_savings:,.0f}</div></div>
    <div><div class='label'>Savings %</div><div class='metric green'>{savings_pct}%</div></div>
  </div>
</div>
<div class='card'>
  <h2>Recommended RI Allocation (Month 36)</h2>
  <div style='display:flex;gap:28px;flex-wrap:wrap'>
    <div><div class='label'>Peak Demand (GPU-hrs)</div><div class='metric'>{max(demand):,}</div></div>
    <div><div class='label'>RI Coverage</div><div class='metric green'>{ri_coverage[-1]:,}</div></div>
    <div><div class='label'>OD Overage</div><div class='metric amber'>{on_demand_overage[-1]:,}</div></div>
    <div><div class='label'>Coverage Ratio</div><div class='metric'>70%</div></div>
  </div>
</div>
</div>

<div class='card'>
  <h2>GPU-Hour Demand vs RI Coverage (36 months)</h2>
  <svg width='{svg_w}' height='{svg_h}' style='display:block;background:#0f172a;border-radius:4px'>
    <polyline points='{demand_pts}' fill='none' stroke='#e2e8f0' stroke-width='1.5' stroke-dasharray='4,2'/>
    <polyline points='{ri_pts}' fill='none' stroke='#38bdf8' stroke-width='2.5'/>
    <text x='8' y='14' fill='#e2e8f0' font-size='11'>&#9472;&#9472; Demand</text>
    <text x='90' y='14' fill='#38bdf8' font-size='11'>&#9472;&#9472; RI Coverage (70%)</text>
  </svg>
</div>

<div class='card'>
  <h2>Monthly Cost: RI (blue) + On-Demand Overage (amber)</h2>
  <svg width='{svg_w}' height='{svg_h}' style='display:block;background:#0f172a;border-radius:4px'>
    {bars_ri}
    {bars_od}
    <text x='8' y='14' fill='#38bdf8' font-size='11'>&#9646; RI Cost</text>
    <text x='70' y='14' fill='#f59e0b' font-size='11'>&#9646; OD Overage</text>
  </svg>
</div>

<div class='card'>
  <h2>OCI GPU Shape Pricing Comparison</h2>
  <table>
    <thead><tr><th>Shape</th><th>GPUs</th><th>On-Demand $/hr</th><th>1-Yr RI</th><th>3-Yr RI</th></tr></thead>
    <tbody>{shape_rows}</tbody>
  </table>
</div>

</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="OCI Reserved Instance Planner")
    @app.get("/", response_class=HTMLResponse)
    def index(): return build_html()
    @app.get("/health")
    def health(): return {"status": "ok", "port": PORT}
    @app.get("/recommendation")
    def recommendation():
        return {
            "recommended_shape": "BM.GPU.A100-v2.8",
            "ri_term": "3yr",
            "coverage_pct": 70,
            "estimated_savings_pct": 35,
            "notes": "Cover 70% of smoothed demand with 3yr RI; handle peaks on-demand"
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
