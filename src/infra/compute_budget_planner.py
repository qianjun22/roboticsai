"""Compute Budget Planner — FastAPI port 8727"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8727

def build_html():
    # --- Simulate 30-day GPU cost time series ---
    days = 30
    daily_cost = []
    daily_hours = []
    for d in range(days):
        baseline = 420 + 80 * math.sin(2 * math.pi * d / 7)  # weekly cycle
        spike = 200 if d in (7, 14, 21) else 0               # training runs
        cost = max(50, baseline + spike + random.gauss(0, 25))
        daily_cost.append(cost)
        daily_hours.append(cost / 3.5)  # $3.5/hr A100

    total_cost = sum(daily_cost)
    avg_daily = total_cost / days
    peak_day = daily_cost.index(max(daily_cost)) + 1
    projected_monthly = avg_daily * 30

    # SVG area chart for daily cost
    cw, ch = 580, 150
    mn_c, mx_c = min(daily_cost), max(daily_cost)
    def cost_pt(i, v):
        x = 40 + (i / (days - 1)) * (cw - 60)
        y = 10 + (ch - 20) - ((v - mn_c) / (mx_c - mn_c + 1)) * (ch - 20)
        return x, y

    area_pts = [(40, ch)] + [cost_pt(i, v) for i, v in enumerate(daily_cost)] + [(40 + cw - 60, ch)]
    area_str = " ".join(f"{x:.1f},{y:.1f}" for x, y in area_pts)
    line_str = " ".join(f"{cost_pt(i,v)[0]:.1f},{cost_pt(i,v)[1]:.1f}" for i, v in enumerate(daily_cost))

    # --- Budget allocation donut (SVG arcs) ---
    allocations = [
        ("Fine-tuning",  0.38, "#38bdf8"),
        ("SDG / Isaac",  0.24, "#6366f1"),
        ("Inference",    0.18, "#f59e0b"),
        ("DAgger",       0.12, "#4ade80"),
        ("Evaluation",   0.08, "#f472b6"),
    ]
    donut_parts = []
    angle = -math.pi / 2
    cx2, cy2, r_out, r_in = 160, 160, 110, 60
    for label, frac, color in allocations:
        sweep = 2 * math.pi * frac
        x1 = cx2 + r_out * math.cos(angle)
        y1 = cy2 + r_out * math.sin(angle)
        x2 = cx2 + r_out * math.cos(angle + sweep)
        y2 = cy2 + r_out * math.sin(angle + sweep)
        xi1 = cx2 + r_in * math.cos(angle + sweep)
        yi1 = cy2 + r_in * math.sin(angle + sweep)
        xi2 = cx2 + r_in * math.cos(angle)
        yi2 = cy2 + r_in * math.sin(angle)
        large = 1 if sweep > math.pi else 0
        path = (f'M {x1:.1f} {y1:.1f} A {r_out} {r_out} 0 {large} 1 {x2:.1f} {y2:.1f} '
                f'L {xi1:.1f} {yi1:.1f} A {r_in} {r_in} 0 {large} 0 {xi2:.1f} {yi2:.1f} Z')
        mid_a = angle + sweep / 2
        lx = cx2 + (r_out + 22) * math.cos(mid_a)
        ly = cy2 + (r_out + 22) * math.sin(mid_a)
        donut_parts.append(
            f'<path d="{path}" fill="{color}" stroke="#0f172a" stroke-width="2"/>'
            f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="middle" fill="#e2e8f0" font-size="10">{int(frac*100)}%</text>'
        )
        angle += sweep

    # --- Instance type recommendation table ---
    instance_types = [
        ("A100 80GB",  3.50,  "BM.GPU.A100-v2.8",  "Fine-tuning",   True),
        ("A10 24GB",   1.20,  "VM.GPU3.1",          "Inference",     True),
        ("V100 16GB",  2.10,  "BM.GPU3.8",          "DAgger",        False),
        ("H100 80GB",  5.80,  "BM.GPU.H100-v2.8",   "Large FT",      False),
        ("T4 16GB",    0.55,  "VM.GPU2.1",          "Evaluation",    True),
    ]

    # --- Scaling efficiency curve (Amdahl-like) ---
    n_gpus = list(range(1, 17))
    parallelism = 0.92
    efficiency = [parallelism + (1 - parallelism) / n for n in n_gpus]
    speedup     = [n * e for n, e in zip(n_gpus, efficiency)]
    sp_max = max(speedup)
    sp_svg = " ".join(
        f"{40 + (i/(len(n_gpus)-1))*480:.1f},{130 - (s/sp_max)*110:.1f}"
        for i, s in enumerate(speedup)
    )

    return f"""<!DOCTYPE html><html><head><title>Compute Budget Planner</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui;padding:20px}}
h1{{color:#C74634;margin:0 0 4px 0;font-size:1.6rem}}
.subtitle{{color:#64748b;font-size:0.85rem;margin-bottom:20px}}
h2{{color:#38bdf8;font-size:1rem;margin:0 0 12px 0}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px;margin-bottom:16px}}
.card{{background:#1e293b;padding:20px;border-radius:8px;border:1px solid #334155}}
.stat{{font-size:2rem;font-weight:700;color:#38bdf8}}
.label{{font-size:0.75rem;color:#64748b;text-transform:uppercase;letter-spacing:.05em}}
.badge{{display:inline-block;padding:2px 8px;border-radius:999px;font-size:0.75rem;background:#1e3a5f;color:#38bdf8;margin:2px}}
table{{width:100%;border-collapse:collapse;font-size:0.85rem}}
th{{text-align:left;color:#64748b;font-weight:600;padding:6px 8px;border-bottom:1px solid #334155}}
td{{padding:6px 8px;border-bottom:1px solid #1e293b}}
.green{{color:#4ade80}}.red{{color:#f87171}}.yellow{{color:#f59e0b}}
</style></head>
<body>
<h1>Compute Budget Planner</h1>
<div class="subtitle">Port {PORT} &nbsp;·&nbsp; OCI GPU cost modeling &amp; allocation optimizer &nbsp;·&nbsp; Robotics AI Cloud</div>

<div class="grid">
  <div class="card">
    <div class="label">30-Day Spend</div>
    <div class="stat">${total_cost:,.0f}</div>
    <div style="margin-top:6px"><span class="badge">Avg ${avg_daily:.0f}/day</span></div>
  </div>
  <div class="card">
    <div class="label">Projected Monthly</div>
    <div class="stat">${projected_monthly:,.0f}</div>
    <div style="margin-top:6px"><span class="badge">Budget $18,000</span>
      <span class="badge {'green' if projected_monthly<=18000 else 'red'}">{'Under' if projected_monthly<=18000 else 'Over'}</span></div>
  </div>
  <div class="card">
    <div class="label">Peak Day</div>
    <div class="stat">Day {peak_day}</div>
    <div style="color:#f59e0b;font-size:1.1rem">${max(daily_cost):.0f}</div>
  </div>
  <div class="card">
    <div class="label">GPU Utilization</div>
    <div class="stat">{random.uniform(74,89):.1f}%</div>
    <div style="margin-top:6px"><span class="badge">A100 ×{random.randint(4,8)}</span></div>
  </div>
</div>

<div class="card" style="margin-bottom:16px">
  <h2>Daily GPU Spend (30 Days)</h2>
  <svg width="100%" viewBox="0 0 620 160" preserveAspectRatio="xMidYMid meet">
    <defs><linearGradient id="cg" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#38bdf8" stop-opacity="0.4"/>
      <stop offset="100%" stop-color="#38bdf8" stop-opacity="0.03"/>
    </linearGradient></defs>
    <polygon points="{area_str}" fill="url(#cg)"/>
    <polyline points="{line_str}" fill="none" stroke="#38bdf8" stroke-width="2"/>
    <text x="40" y="155" fill="#64748b" font-size="10">Day 1</text>
    <text x="560" y="155" fill="#64748b" font-size="10">Day {days}</text>
    <text x="10" y="15" fill="#64748b" font-size="10" transform="rotate(-90 10 15)">$/day</text>
  </svg>
</div>

<div class="grid">
  <div class="card">
    <h2>Budget Allocation</h2>
    <svg width="100%" viewBox="0 0 320 320" preserveAspectRatio="xMidYMid meet">
      {''.join(donut_parts)}
      <text x="{cx2}" y="{cy2-8}" text-anchor="middle" fill="#e2e8f0" font-size="13" font-weight="700">${total_cost:,.0f}</text>
      <text x="{cx2}" y="{cy2+12}" text-anchor="middle" fill="#64748b" font-size="11">30-day</text>
    </svg>
    <div style="margin-top:8px">
      {''.join(f'<span class="badge" style="background:{c}22;color:{c}">{lbl}</span>' for lbl,_,c in allocations)}
    </div>
  </div>

  <div class="card">
    <h2>Multi-GPU Scaling Efficiency</h2>
    <svg width="100%" viewBox="0 0 540 150" preserveAspectRatio="xMidYMid meet">
      <polyline points="{sp_svg}" fill="none" stroke="#6366f1" stroke-width="2.5"/>
      {''.join(f'<circle cx="{40+(i/15)*480:.1f}" cy="{130-(s/sp_max)*110:.1f}" r="3" fill="#6366f1"/>' for i,s in enumerate(speedup))}
      <text x="40" y="145" fill="#64748b" font-size="10">1 GPU</text>
      <text x="500" y="145" fill="#64748b" font-size="10">16 GPUs</text>
      <text x="280" y="145" fill="#64748b" font-size="10">Speedup (Amdahl p={parallelism})</text>
    </svg>
    <div style="margin-top:8px">
      <span class="badge">Linear ideal: {n_gpus[-1]}×</span>
      <span class="badge">Actual: {speedup[-1]:.1f}×</span>
      <span class="badge">Efficiency: {efficiency[-1]:.0%}</span>
    </div>
  </div>
</div>

<div class="card">
  <h2>Instance Type Recommender</h2>
  <table>
    <tr><th>GPU</th><th>$/hr (OCI)</th><th>Shape</th><th>Best For</th><th>Available</th></tr>
    {''.join(f"<tr><td>{gpu}</td><td style='color:#f59e0b'>${cost:.2f}</td><td style='font-family:monospace;font-size:0.8rem'>{shape}</td><td>{use}</td><td class='{'green' if avail else 'red'}'>{'&#10003; Yes' if avail else '&#10007; Waitlist'}</td></tr>" for gpu,cost,shape,use,avail in instance_types)}
  </table>
</div>

</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Compute Budget Planner")
    @app.get("/", response_class=HTMLResponse)
    def index(): return build_html()
    @app.get("/health")
    def health(): return {"status": "ok", "port": PORT}
    @app.get("/metrics")
    def metrics():
        return {
            "port": PORT,
            "service": "compute_budget_planner",
            "tracked_instances": 5,
            "budget_usd": 18000,
            "window_days": 30,
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
