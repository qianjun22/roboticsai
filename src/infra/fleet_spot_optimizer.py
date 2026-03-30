"""Fleet Spot Optimizer — FastAPI port 8693"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8693

def build_html():
    random.seed(99)

    # Spot instance price history over 48 hours (10-min intervals)
    intervals = 288
    base_prices = {"A100": 2.80, "H100": 4.60, "A10G": 1.20}
    colors = {"A100": "#38bdf8", "H100": "#f472b6", "A10G": "#4ade80"}

    def spot_price_series(base, n):
        price = base
        out = []
        for i in range(n):
            # Mean-reverting with spike probability
            drift = (base - price) * 0.05
            noise = random.gauss(0, base * 0.04)
            spike = base * random.uniform(0.3, 0.8) if random.random() < 0.03 else 0.0
            price = max(base * 0.4, price + drift + noise + spike)
            out.append(round(price, 4))
        return out

    series = {gpu: spot_price_series(base, intervals) for gpu, base in base_prices.items()}

    chart_w, chart_h = 640, 200
    pad_l, pad_r, pad_t, pad_b = 52, 20, 30, 30
    inner_w = chart_w - pad_l - pad_r
    inner_h = chart_h - pad_t - pad_b
    all_prices = [p for s in series.values() for p in s]
    y_min_v, y_max_v = min(all_prices) * 0.95, max(all_prices) * 1.05

    def to_xy(i, v):
        x = pad_l + i / (intervals - 1) * inner_w
        y = pad_t + (1 - (v - y_min_v) / (y_max_v - y_min_v)) * inner_h
        return x, y

    def poly(s, col):
        pts = " ".join(f"{to_xy(i,v)[0]:.1f},{to_xy(i,v)[1]:.1f}" for i, v in enumerate(s))
        return f'<polyline points="{pts}" fill="none" stroke="{col}" stroke-width="1.8" stroke-linejoin="round"/>'

    # Grid lines
    grid = ""
    for tick in [y_min_v + k * (y_max_v - y_min_v) / 4 for k in range(5)]:
        _, ty = to_xy(0, tick)
        grid += f'<line x1="{pad_l}" y1="{ty:.1f}" x2="{chart_w - pad_r}" y2="{ty:.1f}" stroke="#334155" stroke-width="1" stroke-dasharray="4,3"/>'
        grid += f'<text x="{pad_l - 4}" y="{ty + 4:.1f}" fill="#94a3b8" font-size="9" text-anchor="end">${tick:.2f}</text>'

    # X axis hour labels
    xticks = ""
    for h in range(0, 49, 8):
        i = min(int(h * 6), intervals - 1)
        x, _ = to_xy(i, y_min_v)
        xticks += f'<text x="{x:.1f}" y="{chart_h - 4}" fill="#94a3b8" font-size="9" text-anchor="middle">{h}h</text>'

    price_svg = "".join(poly(series[gpu], colors[gpu]) for gpu in base_prices)

    # Savings donut — simulate on-demand vs spot
    on_demand_cost = sum(base_prices[g] * 48 for g in base_prices)
    spot_cost = sum(sum(s) / intervals * 48 for s in series.values())
    savings_pct = round((1 - spot_cost / on_demand_cost) * 100, 1)
    donut_r = 55
    donut_cx, donut_cy = 90, 90
    circ = 2 * math.pi * donut_r
    spot_arc = circ * (savings_pct / 100)
    remain_arc = circ - spot_arc

    # Fleet allocation pie — # GPUs per type
    fleet_total = 120
    alloc = {"A100": 48, "H100": 32, "A10G": 40}
    pie_r = 55
    pie_cx, pie_cy = 90, 90
    pie_svgs = ""
    angle = -math.pi / 2
    for gpu, cnt in alloc.items():
        frac = cnt / fleet_total
        sweep = 2 * math.pi * frac
        x1 = pie_cx + pie_r * math.cos(angle)
        y1 = pie_cy + pie_r * math.sin(angle)
        angle += sweep
        x2 = pie_cx + pie_r * math.cos(angle)
        y2 = pie_cy + pie_r * math.sin(angle)
        large = 1 if sweep > math.pi else 0
        pie_svgs += f'<path d="M{pie_cx},{pie_cy} L{x1:.2f},{y1:.2f} A{pie_r},{pie_r} 0 {large},1 {x2:.2f},{y2:.2f} Z" fill="{colors[gpu]}" opacity="0.85"/>'
        mid_angle = angle - sweep / 2
        lx = pie_cx + pie_r * 0.65 * math.cos(mid_angle)
        ly = pie_cy + pie_r * 0.65 * math.sin(mid_angle)
        pie_svgs += f'<text x="{lx:.1f}" y="{ly + 4:.1f}" fill="#0f172a" font-size="10" font-weight="700" text-anchor="middle">{cnt}</text>'

    # Interruption probability per GPU (random but plausible)
    intr = {gpu: round(random.uniform(3.5, 14.2), 1) for gpu in base_prices}
    intr_bars = ""
    bw, bh = 180, 140
    b_pad = 30
    bar_max = 20
    for i, (gpu, pct) in enumerate(intr.items()):
        bx = b_pad
        by = b_pad + i * 38
        bar_len = pct / bar_max * (bw - b_pad * 2)
        intr_bars += f'<rect x="{bx}" y="{by}" width="{bar_len:.1f}" height="22" fill="{colors[gpu]}" rx="3"/>'
        intr_bars += f'<text x="{bx - 4}" y="{by + 15}" fill="#94a3b8" font-size="10" text-anchor="end">{gpu}</text>'
        intr_bars += f'<text x="{bx + bar_len + 5:.1f}" y="{by + 15}" fill="#e2e8f0" font-size="10">{pct}%</text>'

    # Summary stats
    avg_spot = {gpu: round(sum(series[gpu]) / intervals, 4) for gpu in base_prices}
    budget_used = round(spot_cost, 2)
    budget_total = round(on_demand_cost, 2)

    return f"""<!DOCTYPE html><html><head><title>Fleet Spot Optimizer</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui}}
h1{{color:#C74634;padding:24px 24px 0;margin:0;font-size:1.6rem}}
h2{{color:#38bdf8;font-size:1.05rem;margin:0 0 10px}}
.subtitle{{color:#94a3b8;padding:4px 24px 16px;font-size:0.9rem}}
.grid4{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;padding:0 24px 16px}}
.card{{background:#1e293b;padding:20px;border-radius:8px}}
.stat{{font-size:2rem;font-weight:700;color:#38bdf8}}
.stat.green{{color:#4ade80}}
.label{{font-size:0.78rem;color:#64748b;margin-top:4px}}
.charts{{padding:0 24px 16px}}
.row{{display:grid;grid-template-columns:2fr 1fr 1fr;gap:16px;margin-bottom:16px}}
svg text{{font-family:system-ui}}
</style></head>
<body>
<h1>Fleet Spot Optimizer</h1>
<div class="subtitle">OCI GPU spot fleet · 120 GPUs · 48h window · Port {PORT}</div>

<div class="grid4">
  <div class="card"><div class="stat green">{savings_pct}%</div><div class="label">Spot Savings vs On-Demand</div></div>
  <div class="card"><div class="stat">${budget_used:.2f}</div><div class="label">Spot Cost (48h, all GPUs)</div></div>
  <div class="card"><div class="stat">${budget_total:.2f}</div><div class="label">On-Demand Equivalent</div></div>
  <div class="card"><div class="stat">{fleet_total}</div><div class="label">Total GPUs in Fleet</div></div>
</div>

<div class="charts">
  <div class="card" style="margin-bottom:16px">
    <h2>Spot Price History — 48h (10-min intervals)</h2>
    <svg width="{chart_w}" height="{chart_h}" style="display:block">
      {grid}{price_svg}{xticks}
      <text x="{pad_l}" y="{pad_t - 8}" fill="#94a3b8" font-size="9">$/hr</text>
      <!-- Legend -->
      {''.join(f'<rect x="{pad_l + j*80}" y="4" width="10" height="10" fill="{colors[g]}"/><text x="{pad_l + j*80 + 14}" y="13" fill="#e2e8f0" font-size="11">{g}</text>' for j, g in enumerate(base_prices))}
    </svg>
  </div>

  <div class="row">
    <div class="card">
      <h2>Interruption Risk by GPU Type</h2>
      <svg width="{bw}" height="{bh}" style="display:block">{intr_bars}</svg>
      <div style="color:#64748b;font-size:0.78rem;margin-top:8px">Estimated 1h interruption probability</div>
    </div>
    <div class="card">
      <h2>Fleet Allocation</h2>
      <svg width="180" height="180" style="display:block">{pie_svgs}</svg>
      {''.join(f'<div style="font-size:0.8rem;color:{colors[g]};margin-top:4px">{g}: {alloc[g]} GPUs</div>' for g in alloc)}
    </div>
    <div class="card">
      <h2>Avg Spot Price</h2>
      {''.join(f'<div style="margin-bottom:12px"><div style="color:{colors[g]};font-size:1.3rem;font-weight:700">${avg_spot[g]}/hr</div><div style="color:#64748b;font-size:0.78rem">{g}</div></div>' for g in base_prices)}
    </div>
  </div>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Fleet Spot Optimizer")

    @app.get("/", response_class=HTMLResponse)
    def index(): return build_html()

    @app.get("/health")
    def health(): return {"status": "ok", "port": PORT}

    @app.get("/fleet")
    def fleet():
        random.seed(99)
        return {
            "total_gpus": 120,
            "allocation": {"A100": 48, "H100": 32, "A10G": 40},
            "spot_savings_pct": 37.4,
            "avg_spot_prices": {"A100": 2.63, "H100": 4.31, "A10G": 1.09},
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
