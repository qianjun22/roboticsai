"""DAgger Run 10 Evaluator — FastAPI port 8696"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8696

random.seed(42)

def build_html():
    # Generate DAgger iteration metrics
    n_iters = 10
    success_rates = [round(0.05 + 0.09 * i + random.uniform(-0.02, 0.02), 3) for i in range(n_iters)]
    loss_vals = [round(0.42 - 0.035 * i + random.uniform(-0.005, 0.005), 4) for i in range(n_iters)]
    demo_counts = [100 + i * 85 + random.randint(-10, 10) for i in range(n_iters)]
    intervention_rates = [round(0.88 - 0.08 * i + random.uniform(-0.01, 0.01), 3) for i in range(n_iters)]

    final_success = success_rates[-1]
    final_loss = loss_vals[-1]
    total_demos = sum(demo_counts)
    avg_intervention = round(sum(intervention_rates) / n_iters, 3)

    # SVG success rate line chart (600x160)
    chart_w, chart_h = 560, 130
    pad_l, pad_r, pad_t, pad_b = 45, 20, 15, 30
    plot_w = chart_w - pad_l - pad_r
    plot_h = chart_h - pad_t - pad_b

    def sx(i): return pad_l + i * plot_w / (n_iters - 1)
    def sy_sr(v): return pad_t + plot_h * (1 - (v / 1.0))
    def sy_loss(v): return pad_t + plot_h * (1 - ((0.42 - v) / 0.42 + 0.5) * 0.5)

    sr_points = " ".join(f"{sx(i):.1f},{sy_sr(success_rates[i]):.1f}" for i in range(n_iters))
    loss_points = " ".join(f"{sx(i):.1f},{sy_loss(loss_vals[i]):.1f}" for i in range(n_iters))

    # Y-axis grid lines
    grid_lines = ""
    for frac in [0.0, 0.25, 0.5, 0.75, 1.0]:
        y = pad_t + plot_h * (1 - frac)
        label = f"{frac:.0%}"
        grid_lines += f'<line x1="{pad_l}" y1="{y:.1f}" x2="{pad_l+plot_w}" y2="{y:.1f}" stroke="#334155" stroke-width="1" stroke-dasharray="4,4"/>'
        grid_lines += f'<text x="{pad_l-5}" y="{y+4:.1f}" fill="#94a3b8" font-size="9" text-anchor="end">{label}</text>'

    # X-axis labels
    x_labels = ""
    for i in range(n_iters):
        x_labels += f'<text x="{sx(i):.1f}" y="{pad_t+plot_h+18:.1f}" fill="#94a3b8" font-size="9" text-anchor="middle">R{i+1}</text>'

    # Dots on success line
    sr_dots = "".join(
        f'<circle cx="{sx(i):.1f}" cy="{sy_sr(success_rates[i]):.1f}" r="3.5" fill="#22d3ee"/>'
        for i in range(n_iters)
    )

    # Loss dots
    loss_dots = "".join(
        f'<circle cx="{sx(i):.1f}" cy="{sy_loss(loss_vals[i]):.1f}" r="3" fill="#f59e0b"/>'
        for i in range(n_iters)
    )

    # Bar chart for demo counts (separate SVG)
    bar_w_total = 560
    bar_h_total = 130
    bar_pad_l, bar_pad_b = 50, 30
    bar_plot_w = bar_w_total - bar_pad_l - 20
    bar_plot_h = bar_h_total - bar_pad_b - 15
    max_demos = max(demo_counts)
    bar_width = bar_plot_w / n_iters * 0.65
    bar_gap = bar_plot_w / n_iters

    bars = ""
    for i, cnt in enumerate(demo_counts):
        bh = (cnt / max_demos) * bar_plot_h
        bx = bar_pad_l + i * bar_gap + (bar_gap - bar_width) / 2
        by = 15 + bar_plot_h - bh
        bars += f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bar_width:.1f}" height="{bh:.1f}" fill="#6366f1" rx="2"/>'
        bars += f'<text x="{bx + bar_width/2:.1f}" y="{by - 3:.1f}" fill="#94a3b8" font-size="8" text-anchor="middle">{cnt}</text>'
        bars += f'<text x="{bx + bar_width/2:.1f}" y="{15 + bar_plot_h + 18:.1f}" fill="#94a3b8" font-size="9" text-anchor="middle">R{i+1}</text>'

    bar_grid = ""
    for frac in [0.25, 0.5, 0.75, 1.0]:
        y = 15 + bar_plot_h * (1 - frac)
        lbl = int(frac * max_demos)
        bar_grid += f'<line x1="{bar_pad_l}" y1="{y:.1f}" x2="{bar_w_total-20}" y2="{y:.1f}" stroke="#334155" stroke-width="1" stroke-dasharray="4,4"/>'
        bar_grid += f'<text x="{bar_pad_l-5}" y="{y+4:.1f}" fill="#94a3b8" font-size="9" text-anchor="end">{lbl}</text>'

    # Intervention rate radar-style arc display
    ir_rows = ""
    for i, ir in enumerate(intervention_rates):
        pct = int(ir * 100)
        color = "#ef4444" if ir > 0.7 else "#f59e0b" if ir > 0.4 else "#22c55e"
        ir_rows += f'<tr><td style="padding:4px 12px;color:#94a3b8">Run {i+1}</td>'
        ir_rows += f'<td style="padding:4px 12px"><div style="background:#0f172a;border-radius:4px;height:14px;width:200px">'
        ir_rows += f'<div style="background:{color};height:14px;width:{pct*2}px;border-radius:4px"></div></div></td>'
        ir_rows += f'<td style="padding:4px 12px;color:{color}">{pct}%</td></tr>'

    return f"""<!DOCTYPE html><html><head><title>DAgger Run 10 Evaluator</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui}}
h1{{color:#C74634;margin:0;padding:20px 24px 8px;font-size:1.6rem}}
h2{{color:#38bdf8;font-size:1rem;margin:0 0 12px}}
.card{{background:#1e293b;padding:20px;margin:12px;border-radius:10px;display:inline-block;vertical-align:top}}
.stat{{font-size:2rem;font-weight:700;color:#22d3ee}}
.stat-label{{font-size:0.75rem;color:#64748b;margin-top:2px}}
.grid{{display:flex;flex-wrap:wrap}}
.badge{{display:inline-block;padding:2px 8px;border-radius:12px;font-size:0.75rem;font-weight:600}}
table{{border-collapse:collapse}}
</style></head>
<body>
<h1>DAgger Run 10 — Policy Evaluator</h1>
<p style="color:#64748b;padding:0 24px;margin:0 0 4px">Dataset Aggregation reinforcement loop — 10 iterations, GR00T N1.6 backbone</p>
<div class="grid">
  <div class="card">
    <div class="stat-label">Final Success Rate</div>
    <div class="stat">{final_success:.1%}</div>
    <div style="color:#22c55e;font-size:0.8rem;margin-top:4px">▲ +{(final_success - success_rates[0]):.1%} vs baseline</div>
  </div>
  <div class="card">
    <div class="stat-label">Final Policy Loss</div>
    <div class="stat" style="color:#f59e0b">{final_loss:.4f}</div>
    <div style="color:#22c55e;font-size:0.8rem;margin-top:4px">▼ {((loss_vals[0]-final_loss)/loss_vals[0]):.1%} reduction</div>
  </div>
  <div class="card">
    <div class="stat-label">Total Demos Collected</div>
    <div class="stat" style="color:#a78bfa">{total_demos:,}</div>
    <div style="color:#64748b;font-size:0.8rem;margin-top:4px">across {n_iters} DAgger iterations</div>
  </div>
  <div class="card">
    <div class="stat-label">Avg Intervention Rate</div>
    <div class="stat" style="color:#fb923c">{avg_intervention:.1%}</div>
    <div style="color:#22c55e;font-size:0.8rem;margin-top:4px">▼ Decreasing — policy gaining autonomy</div>
  </div>
</div>

<div class="card" style="margin:12px;display:block">
  <h2>Success Rate &amp; Loss Over DAgger Iterations</h2>
  <svg width="{chart_w}" height="{chart_h}">
    {grid_lines}
    {x_labels}
    <polyline points="{sr_points}" fill="none" stroke="#22d3ee" stroke-width="2.5"/>
    <polyline points="{loss_points}" fill="none" stroke="#f59e0b" stroke-width="2" stroke-dasharray="6,3"/>
    {sr_dots}
    {loss_dots}
    <text x="{pad_l}" y="{pad_t-3}" fill="#22d3ee" font-size="10">— Success Rate</text>
    <text x="{pad_l+110}" y="{pad_t-3}" fill="#f59e0b" font-size="10">- - Loss (normalized)</text>
  </svg>
</div>

<div class="card" style="margin:12px;display:block">
  <h2>Demonstrations Collected Per Iteration</h2>
  <svg width="{bar_w_total}" height="{bar_h_total}">
    {bar_grid}
    {bars}
  </svg>
</div>

<div class="card" style="margin:12px;display:block">
  <h2>Expert Intervention Rate by Iteration</h2>
  <table>
    {ir_rows}
  </table>
  <p style="color:#64748b;font-size:0.75rem;margin:8px 0 0">Red &gt;70% &nbsp; Amber 40-70% &nbsp; Green &lt;40% — lower is better (policy more autonomous)</p>
</div>

<div class="card" style="margin:12px">
  <h2>Run Configuration</h2>
  <table>
    <tr><td style="padding:3px 16px 3px 0;color:#64748b">Model</td><td>GR00T N1.6 (7B)</td></tr>
    <tr><td style="padding:3px 16px 3px 0;color:#64748b">Task</td><td>PickAndPlace — cube-on-plate</td></tr>
    <tr><td style="padding:3px 16px 3px 0;color:#64748b">Env</td><td>LIBERO-Spatial (Isaac Sim 4.2)</td></tr>
    <tr><td style="padding:3px 16px 3px 0;color:#64748b">Backbone LR</td><td>1e-5</td></tr>
    <tr><td style="padding:3px 16px 3px 0;color:#64748b">Action Head LR</td><td>1e-4</td></tr>
    <tr><td style="padding:3px 16px 3px 0;color:#64748b">Batch Size</td><td>32 (4× A100 DDP)</td></tr>
    <tr><td style="padding:3px 16px 3px 0;color:#64748b">Steps/Iter</td><td>2,000</td></tr>
    <tr><td style="padding:3px 16px 3px 0;color:#64748b">OCI Shape</td><td>BM.GPU.A100.8 (4 used)</td></tr>
    <tr><td style="padding:3px 16px 3px 0;color:#64748b">Eval Episodes</td><td>20 per checkpoint</td></tr>
  </table>
</div>

<p style="color:#334155;font-size:0.7rem;padding:8px 24px">OCI Robot Cloud — DAgger Run 10 — port {PORT}</p>
</body></html>"""

if USE_FASTAPI:
    app = FastAPI(title="DAgger Run 10 Evaluator")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return build_html()

    @app.get("/health")
    def health():
        return {"status": "ok", "port": PORT, "service": "dagger_run10_evaluator"}

    @app.get("/metrics")
    def metrics():
        random.seed(42)
        success_rates = [round(0.05 + 0.09 * i + random.uniform(-0.02, 0.02), 3) for i in range(10)]
        loss_vals = [round(0.42 - 0.035 * i + random.uniform(-0.005, 0.005), 4) for i in range(10)]
        return {
            "run": 10,
            "iterations": 10,
            "final_success_rate": success_rates[-1],
            "final_loss": loss_vals[-1],
            "baseline_success_rate": success_rates[0],
            "improvement": round(success_rates[-1] - success_rates[0], 3),
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
