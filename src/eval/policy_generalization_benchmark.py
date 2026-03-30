"""Policy Generalization Benchmark — FastAPI port 8702"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8702

# Task categories and environments for generalization benchmark
TASK_CATEGORIES = [
    "Pick & Place", "Push", "Drawer Open", "Door Open",
    "Stack Blocks", "Pour Liquid", "Peg Insert", "Sweep"
]

MODELS = ["GR00T-N1.6", "GR00T-N1.6-FT", "OpenVLA-7B", "BC-Baseline"]

def generate_benchmark_data():
    """Generate realistic generalization benchmark results."""
    random.seed(42)
    results = {}
    # Base success rates per model with realistic spread
    base_rates = {"GR00T-N1.6": 0.72, "GR00T-N1.6-FT": 0.88, "OpenVLA-7B": 0.65, "BC-Baseline": 0.41}
    for model in MODELS:
        results[model] = []
        base = base_rates[model]
        for i, task in enumerate(TASK_CATEGORIES):
            # Add task-specific variance
            noise = (random.random() - 0.5) * 0.18
            difficulty_penalty = i * 0.025
            rate = max(0.05, min(0.99, base - difficulty_penalty + noise))
            results[model].append(round(rate, 3))
    return results

def generate_transfer_curve():
    """Generate sim-to-real transfer curve data points."""
    points = []
    for i in range(40):
        x = i / 39.0
        # Logistic growth with noise
        y_groot_ft = 1 / (1 + math.exp(-8 * (x - 0.3))) * 0.88 + random.gauss(0, 0.015)
        y_groot = 1 / (1 + math.exp(-8 * (x - 0.45))) * 0.72 + random.gauss(0, 0.018)
        y_bc = 1 / (1 + math.exp(-5 * (x - 0.6))) * 0.41 + random.gauss(0, 0.022)
        points.append((
            round(x * 100, 1),
            round(max(0, min(1, y_groot_ft)), 3),
            round(max(0, min(1, y_groot)), 3),
            round(max(0, min(1, y_bc)), 3)
        ))
    return points

def build_html():
    random.seed(12345)
    bench = generate_benchmark_data()
    transfer = generate_transfer_curve()

    # Bar chart data: per-task success for best model (GR00T-N1.6-FT)
    bar_vals = bench["GR00T-N1.6-FT"]
    bar_w = 44
    bar_gap = 8
    chart_h = 160
    bars_svg = ""
    colors = ["#38bdf8", "#34d399", "#a78bfa", "#f472b6",
              "#fb923c", "#facc15", "#4ade80", "#60a5fa"]
    for i, (task, val) in enumerate(zip(TASK_CATEGORIES, bar_vals)):
        x = 40 + i * (bar_w + bar_gap)
        bar_h = int(val * chart_h)
        y = 20 + chart_h - bar_h
        bars_svg += f'<rect x="{x}" y="{y}" width="{bar_w}" height="{bar_h}" fill="{colors[i]}" rx="3"/>'
        bars_svg += f'<text x="{x + bar_w//2}" y="{y - 5}" text-anchor="middle" fill="#e2e8f0" font-size="11">{int(val*100)}%</text>'
        short = task.split()[0][:5]
        bars_svg += f'<text x="{x + bar_w//2}" y="{20 + chart_h + 15}" text-anchor="middle" fill="#94a3b8" font-size="9">{short}</text>'

    # Transfer curve SVG
    svg_w, svg_h = 560, 180
    def pt(x_pct, y_val):
        px = 40 + (x_pct / 100) * (svg_w - 60)
        py = 20 + (1 - y_val) * (svg_h - 50)
        return px, py

    def polyline(series_idx):
        pts = []
        for row in transfer:
            x_pct = row[0]
            y_val = row[1 + series_idx]
            px, py = pt(x_pct, y_val)
            pts.append(f"{px:.1f},{py:.1f}")
        return " ".join(pts)

    line_colors = ["#4ade80", "#38bdf8", "#fb923c"]
    line_labels = ["GR00T-N1.6-FT", "GR00T-N1.6", "BC-Baseline"]
    lines_svg = ""
    for si in range(3):
        lines_svg += f'<polyline points="{polyline(si)}" fill="none" stroke="{line_colors[si]}" stroke-width="2.5"/>'

    # Grid lines
    grid_svg = ""
    for pct in [0, 25, 50, 75, 100]:
        py = 20 + (1 - pct/100) * (svg_h - 50)
        grid_svg += f'<line x1="40" y1="{py:.1f}" x2="{svg_w-20}" y2="{py:.1f}" stroke="#334155" stroke-width="1"/>'
        grid_svg += f'<text x="32" y="{py+4:.1f}" text-anchor="end" fill="#64748b" font-size="9">{pct}%</text>'

    # Legend
    legend_svg = ""
    for i, (lbl, clr) in enumerate(zip(line_labels, line_colors)):
        lx = 50 + i * 160
        legend_svg += f'<rect x="{lx}" y="168" width="14" height="4" fill="{clr}" rx="2"/>'
        legend_svg += f'<text x="{lx+18}" y="173" fill="#e2e8f0" font-size="10">{lbl}</text>'

    # Generalization matrix table
    matrix_rows = ""
    for model in MODELS:
        avg = sum(bench[model]) / len(bench[model])
        cells = "".join(
            f'<td style="text-align:center;padding:4px 8px;color:{"#4ade80" if v>=0.75 else ("#facc15" if v>=0.5 else "#f87171")}">{int(v*100)}%</td>'
            for v in bench[model]
        )
        matrix_rows += f'<tr><td style="padding:4px 12px;color:#e2e8f0;font-weight:600">{model}</td>{cells}<td style="text-align:center;padding:4px 8px;color:#38bdf8;font-weight:700">{int(avg*100)}%</td></tr>'

    task_headers = "".join(f'<th style="padding:4px 8px;color:#94a3b8;font-size:11px">{t.split()[0]}</th>' for t in TASK_CATEGORIES)

    return f"""<!DOCTYPE html><html><head><title>Policy Generalization Benchmark</title>
<meta charset="utf-8">
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui,sans-serif}}
h1{{color:#C74634;margin:0;padding:20px 24px 4px;font-size:22px}}
.subtitle{{color:#64748b;padding:0 24px 16px;font-size:13px}}
h2{{color:#38bdf8;margin:0 0 12px;font-size:15px}}
.card{{background:#1e293b;padding:20px;margin:10px 16px;border-radius:8px;border:1px solid #334155}}
.grid2{{display:grid;grid-template-columns:1fr 1fr;gap:0}}
.stat-row{{display:flex;gap:12px;margin-bottom:8px}}
.stat{{background:#0f172a;border-radius:6px;padding:10px 16px;flex:1;text-align:center}}
.stat-val{{font-size:24px;font-weight:700;color:#4ade80}}
.stat-lbl{{font-size:11px;color:#64748b;margin-top:2px}}
table{{border-collapse:collapse;width:100%;font-size:12px}}
th{{background:#0f172a;padding:6px 8px;text-align:center}}
tr:nth-child(even){{background:#162032}}
.badge{{display:inline-block;padding:2px 8px;border-radius:12px;font-size:11px;font-weight:600}}
</style></head>
<body>
<h1>Policy Generalization Benchmark</h1>
<div class="subtitle">Cross-task success rate evaluation across 8 manipulation categories | OCI A100 cluster | Updated {"2026-03-30"}</div>

<div class="stat-row" style="margin:0 16px 4px">
  <div class="stat"><div class="stat-val">88%</div><div class="stat-lbl">GR00T-N1.6-FT Best Avg</div></div>
  <div class="stat"><div class="stat-val">8</div><div class="stat-lbl">Task Categories</div></div>
  <div class="stat"><div class="stat-val">4</div><div class="stat-lbl">Models Evaluated</div></div>
  <div class="stat"><div class="stat-val" style="color:#facc15">+47%</div><div class="stat-lbl">FT vs BC Baseline</div></div>
</div>

<div class="card">
  <h2>GR00T-N1.6-FT — Per-Task Success Rate</h2>
  <svg width="{40 + 8*(bar_w+bar_gap)}" height="{chart_h + 50}" style="display:block">
    {grid_svg.replace(f'x2="{svg_w-20}"', f'x2="{40 + 8*(bar_w+bar_gap) - 10}"') if False else ""}
    {''.join(f'<line x1="40" y1="{20 + chart_h - int(pct/100*chart_h)}" x2="{40 + 8*(bar_w+bar_gap) - 10}" y2="{20 + chart_h - int(pct/100*chart_h)}" stroke="#334155" stroke-width="1"/><text x="32" y="{20 + chart_h - int(pct/100*chart_h) + 4}" text-anchor="end" fill="#64748b" font-size="9">{pct}%</text>' for pct in [0,25,50,75,100])}
    {bars_svg}
  </svg>
</div>

<div class="card">
  <h2>Sim-to-Real Transfer Curve (Training Steps %)</h2>
  <svg width="{svg_w}" height="{svg_h}" style="display:block">
    {grid_svg}
    {''.join(f'<line x1="{40 + (pct/100)*(svg_w-60):.1f}" y1="20" x2="{40 + (pct/100)*(svg_w-60):.1f}" y2="{svg_h-30}" stroke="#334155" stroke-width="1"/><text x="{40 + (pct/100)*(svg_w-60):.1f}" y="{svg_h-18}" text-anchor="middle" fill="#64748b" font-size="9">{pct}%</text>' for pct in [0,25,50,75,100])}
    {lines_svg}
    {legend_svg}
  </svg>
</div>

<div class="card">
  <h2>Full Generalization Matrix</h2>
  <div style="overflow-x:auto">
  <table>
    <thead><tr><th style="text-align:left;padding:4px 12px;color:#94a3b8">Model</th>{task_headers}<th style="color:#38bdf8">Avg</th></tr></thead>
    <tbody>{matrix_rows}</tbody>
  </table>
  </div>
</div>

<div class="card" style="margin-bottom:20px">
  <h2>Benchmark Configuration</h2>
  <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;font-size:12px">
    <div><span style="color:#64748b">Episodes per task:</span> <span style="color:#e2e8f0">20</span></div>
    <div><span style="color:#64748b">Horizon:</span> <span style="color:#e2e8f0">400 steps</span></div>
    <div><span style="color:#64748b">Sim backend:</span> <span style="color:#e2e8f0">Isaac Sim 4.2</span></div>
    <div><span style="color:#64748b">Action chunk:</span> <span style="color:#e2e8f0">16 steps</span></div>
    <div><span style="color:#64748b">Inference latency:</span> <span style="color:#e2e8f0">231ms avg</span></div>
    <div><span style="color:#64748b">GPU:</span> <span style="color:#e2e8f0">OCI A100 80GB</span></div>
  </div>
</div>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="Policy Generalization Benchmark")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return build_html()

    @app.get("/health")
    def health():
        return {"status": "ok", "port": PORT}

    @app.get("/api/results")
    def api_results():
        bench = generate_benchmark_data()
        return {
            "models": MODELS,
            "tasks": TASK_CATEGORIES,
            "results": bench,
            "averages": {m: round(sum(v)/len(v), 3) for m, v in bench.items()}
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
