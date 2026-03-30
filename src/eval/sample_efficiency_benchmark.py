"""Sample Efficiency Benchmark — FastAPI port 8782"""
import math, random
from http.server import HTTPServer, BaseHTTPRequestHandler
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

PORT = 8782


def build_html():
    random.seed(42)
    # Generate sample efficiency curves: success rate vs number of demos
    demo_counts = [10, 25, 50, 100, 200, 500, 1000, 2000]
    # Simulate three policy types: BC, DAgger, GR00T fine-tuned
    def sigmoid(x, k=0.004, x0=300):
        return 1.0 / (1.0 + math.exp(-k * (x - x0)))

    bc_rates      = [round(sigmoid(d, k=0.007, x0=400) * 100 + random.uniform(-2, 2), 1) for d in demo_counts]
    dagger_rates  = [round(sigmoid(d, k=0.006, x0=200) * 100 + random.uniform(-2, 2), 1) for d in demo_counts]
    groot_rates   = [round(sigmoid(d, k=0.009, x0=120) * 100 + random.uniform(-2, 2), 1) for d in demo_counts]

    # SVG chart dimensions
    W, H = 560, 260
    pad_l, pad_r, pad_t, pad_b = 55, 20, 20, 45
    chart_w = W - pad_l - pad_r
    chart_h = H - pad_t - pad_b

    max_demos = math.log10(demo_counts[-1])
    min_demos = math.log10(demo_counts[0])

    def x_pos(d):
        return pad_l + (math.log10(d) - min_demos) / (max_demos - min_demos) * chart_w

    def y_pos(r):
        return pad_t + chart_h - (r / 100.0) * chart_h

    def polyline(rates, color):
        pts = " ".join(f"{x_pos(d):.1f},{y_pos(r):.1f}" for d, r in zip(demo_counts, rates))
        return f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2.5" stroke-linejoin="round"/>'

    def dots(rates, color):
        return "".join(
            f'<circle cx="{x_pos(d):.1f}" cy="{y_pos(r):.1f}" r="4" fill="{color}"/>'
            for d, r in zip(demo_counts, rates)
        )

    # X-axis tick labels (log scale)
    x_ticks = "".join(
        f'<text x="{x_pos(d):.1f}" y="{pad_t + chart_h + 18}" fill="#94a3b8" font-size="10" text-anchor="middle">{d}</text>'
        for d in demo_counts
    )
    # Y-axis ticks
    y_ticks = "".join(
        f'<text x="{pad_l - 8}" y="{y_pos(v):.1f}" fill="#94a3b8" font-size="10" text-anchor="end" dominant-baseline="middle">{v}%</text>'
        f'<line x1="{pad_l}" y1="{y_pos(v):.1f}" x2="{pad_l + chart_w}" y2="{y_pos(v):.1f}" stroke="#334155" stroke-width="0.5"/>'
        for v in [0, 20, 40, 60, 80, 100]
    )

    # Area under curve metric (trapezoidal, normalized)
    def auc(rates):
        total = 0.0
        for i in range(len(rates) - 1):
            total += (rates[i] + rates[i+1]) / 2.0
        return round(total / (len(rates) - 1), 1)

    bc_auc     = auc(bc_rates)
    dagger_auc = auc(dagger_rates)
    groot_auc  = auc(groot_rates)

    # Sample-to-threshold metrics (demos needed to hit 80%)
    def demos_to_threshold(rates, thresh=80):
        for d, r in zip(demo_counts, rates):
            if r >= thresh:
                return d
        return ">2000"

    bc_thresh     = demos_to_threshold(bc_rates)
    dagger_thresh = demos_to_threshold(dagger_rates)
    groot_thresh  = demos_to_threshold(groot_rates)

    # Learning rate sensitivity bar chart data
    lrs = [1e-5, 5e-5, 1e-4, 5e-4, 1e-3]
    lr_perf = [round(45 + 40 * math.exp(-((math.log10(lr) + 3.7) ** 2) / 0.6) + random.uniform(-1, 1), 1) for lr in lrs]
    lr_labels = ["1e-5", "5e-5", "1e-4", "5e-4", "1e-3"]

    bW, bH = 360, 160
    bpad_l, bpad_r, bpad_t, bpad_b = 50, 10, 15, 35
    bchart_w = bW - bpad_l - bpad_r
    bchart_h = bH - bpad_t - bpad_b
    bar_w = bchart_w / len(lrs) * 0.6

    max_perf = max(lr_perf)
    bars = ""
    for i, (lbl, perf) in enumerate(zip(lr_labels, lr_perf)):
        bx = bpad_l + (i + 0.5) * (bchart_w / len(lrs)) - bar_w / 2
        bh = (perf / max_perf) * bchart_h
        by = bpad_t + bchart_h - bh
        alpha = 0.5 + 0.5 * (perf / max_perf)
        fill = f"rgba(56,189,248,{alpha:.2f})"
        bars += f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bar_w:.1f}" height="{bh:.1f}" fill="{fill}" rx="2"/>'
        bars += f'<text x="{bx + bar_w/2:.1f}" y="{by - 4:.1f}" fill="#e2e8f0" font-size="10" text-anchor="middle">{perf}%</text>'
        bars += f'<text x="{bx + bar_w/2:.1f}" y="{bpad_t + bchart_h + 16}" fill="#94a3b8" font-size="10" text-anchor="middle">{lbl}</text>'

    return f"""<!DOCTYPE html><html><head><title>Sample Efficiency Benchmark</title>
<style>
body{{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui;padding:24px}}
h1{{color:#C74634;margin:0 0 4px 0;font-size:1.6rem}}
h2{{color:#38bdf8;font-size:1rem;margin:0 0 12px 0}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;max-width:1100px}}
.card{{background:#1e293b;padding:20px;border-radius:8px;border:1px solid #334155}}
.stat{{display:inline-block;background:#0f172a;border-radius:6px;padding:10px 18px;margin:4px}}
.stat .val{{font-size:1.5rem;font-weight:700;color:#38bdf8}}
.stat .lbl{{font-size:0.75rem;color:#94a3b8}}
.legend{{display:flex;gap:16px;margin-bottom:8px;font-size:0.8rem}}
.leg-item{{display:flex;align-items:center;gap:6px}}
.leg-dot{{width:12px;height:12px;border-radius:50%}}
</style></head>
<body>
<h1>Sample Efficiency Benchmark</h1>
<p style="color:#94a3b8;margin:0 0 20px 0">Policy performance vs. number of demonstrations — OCI Robot Cloud | port {PORT}</p>

<div style="display:flex;gap:12px;margin-bottom:20px;flex-wrap:wrap">
  <div class="stat"><div class="val">{groot_rates[-1]}%</div><div class="lbl">GR00T @ 2000 demos</div></div>
  <div class="stat"><div class="val">{groot_thresh}</div><div class="lbl">GR00T demos to 80%</div></div>
  <div class="stat"><div class="val">{groot_auc}%</div><div class="lbl">GR00T Avg AUC</div></div>
  <div class="stat"><div class="val">{round((groot_auc - bc_auc) / bc_auc * 100, 1)}%</div><div class="lbl">GR00T vs BC lift</div></div>
</div>

<div class="grid">
  <div class="card">
    <h2>Success Rate vs. Demo Count (log scale)</h2>
    <div class="legend">
      <div class="leg-item"><div class="leg-dot" style="background:#C74634"></div>BC</div>
      <div class="leg-item"><div class="leg-dot" style="background:#facc15"></div>DAgger</div>
      <div class="leg-item"><div class="leg-dot" style="background:#38bdf8"></div>GR00T FT</div>
    </div>
    <svg width="{W}" height="{H}" style="overflow:visible">
      {y_ticks}
      {x_ticks}
      <text x="{pad_l + chart_w/2}" y="{H - 4}" fill="#94a3b8" font-size="11" text-anchor="middle"># Demonstrations</text>
      {polyline(bc_rates, '#C74634')}
      {dots(bc_rates, '#C74634')}
      {polyline(dagger_rates, '#facc15')}
      {dots(dagger_rates, '#facc15')}
      {polyline(groot_rates, '#38bdf8')}
      {dots(groot_rates, '#38bdf8')}
      <!-- 80% threshold line -->
      <line x1="{pad_l}" y1="{y_pos(80):.1f}" x2="{pad_l + chart_w}" y2="{y_pos(80):.1f}" stroke="#4ade80" stroke-width="1" stroke-dasharray="6,3"/>
      <text x="{pad_l + chart_w - 2}" y="{y_pos(80) - 4:.1f}" fill="#4ade80" font-size="10" text-anchor="end">80% target</text>
    </svg>
  </div>

  <div class="card">
    <h2>Learning Rate Sensitivity @ 200 demos</h2>
    <svg width="{bW}" height="{bH}" style="overflow:visible">
      {bars}
      <text x="{bpad_l + bchart_w/2}" y="{bH - 4}" fill="#94a3b8" font-size="11" text-anchor="middle">Learning Rate</text>
    </svg>

    <table style="width:100%;border-collapse:collapse;margin-top:12px;font-size:0.82rem">
      <thead><tr>
        <th style="text-align:left;color:#94a3b8;padding:4px 8px">Policy</th>
        <th style="text-align:right;color:#94a3b8;padding:4px 8px">AUC Avg</th>
        <th style="text-align:right;color:#94a3b8;padding:4px 8px">Demos→80%</th>
        <th style="text-align:right;color:#94a3b8;padding:4px 8px">Peak@2k</th>
      </tr></thead>
      <tbody>
        <tr><td style="padding:4px 8px;color:#C74634">BC</td>
            <td style="text-align:right;padding:4px 8px">{bc_auc}%</td>
            <td style="text-align:right;padding:4px 8px">{bc_thresh}</td>
            <td style="text-align:right;padding:4px 8px">{bc_rates[-1]}%</td></tr>
        <tr><td style="padding:4px 8px;color:#facc15">DAgger</td>
            <td style="text-align:right;padding:4px 8px">{dagger_auc}%</td>
            <td style="text-align:right;padding:4px 8px">{dagger_thresh}</td>
            <td style="text-align:right;padding:4px 8px">{dagger_rates[-1]}%</td></tr>
        <tr style="background:#0f172a"><td style="padding:4px 8px;color:#38bdf8">GR00T FT</td>
            <td style="text-align:right;padding:4px 8px">{groot_auc}%</td>
            <td style="text-align:right;padding:4px 8px">{groot_thresh}</td>
            <td style="text-align:right;padding:4px 8px">{groot_rates[-1]}%</td></tr>
      </tbody>
    </table>
  </div>
</div>
</body></html>"""


if USE_FASTAPI:
    app = FastAPI(title="Sample Efficiency Benchmark")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return build_html()

    @app.get("/health")
    def health():
        return {"status": "ok", "port": PORT}

    @app.get("/metrics")
    def metrics():
        random.seed(42)
        demo_counts = [10, 25, 50, 100, 200, 500, 1000, 2000]
        def sigmoid(x, k=0.004, x0=300):
            return 1.0 / (1.0 + math.exp(-k * (x - x0)))
        return {
            "demo_counts": demo_counts,
            "bc_rates":     [round(sigmoid(d, k=0.007, x0=400) * 100, 1) for d in demo_counts],
            "dagger_rates": [round(sigmoid(d, k=0.006, x0=200) * 100, 1) for d in demo_counts],
            "groot_rates":  [round(sigmoid(d, k=0.009, x0=120) * 100, 1) for d in demo_counts],
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
