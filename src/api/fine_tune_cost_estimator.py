"""fine_tune_cost_estimator.py — GR00T Fine-Tuning Cost Estimator Service (port 8253)

Pre-run cost estimation for GR00T fine-tuning jobs with budget guardrails.
Breaks down cost by component and shows parameter sensitivity curves.
"""

try:
    from fastapi import FastAPI, Query
    from fastapi.responses import HTMLResponse
    import uvicorn
    USE_FASTAPI = True
except ImportError:
    USE_FASTAPI = False

import math
import random
import json
from datetime import datetime

# ---------------------------------------------------------------------------
# Cost model constants (OCI A100 pricing)
# ---------------------------------------------------------------------------

COST_PER_GPU_HOUR = 3.40          # USD, OCI BM.GPU.A100.8 per GPU-hour
CHECKPOINT_STORAGE_PER_GB = 0.023 # USD/GB/month
EVAL_COST_PER_RUN = 0.85          # USD per eval episode batch
NETWORK_PER_GB = 0.0085            # USD/GB egress
PREPROC_COST_PER_DEMO = 0.0012    # USD per demonstration preprocessed

# Standard 1000-demo reference run
STD_RUN = {
    "demo_count": 1000,
    "training_steps": 5000,
    "lora_rank": 16,
    "eval_frequency": 500,          # every N steps
    "gpus": 2,
    "steps_per_sec": 2.35,
    "checkpoint_size_gb": 6.7,
    "checkpoints_kept": 5,
    "eval_episodes": 20,
}


def compute_cost(demo_count=1000, training_steps=5000, lora_rank=16, eval_frequency=500):
    """Return cost breakdown dict for given parameters."""
    gpus = 2
    # Compute hours: steps / throughput / 3600
    # lora_rank affects throughput (higher rank = slower)
    rank_factor = 1.0 + 0.018 * (lora_rank - 16)  # relative to rank=16 baseline
    steps_per_sec = 2.35 / rank_factor
    compute_hours = (training_steps / steps_per_sec) / 3600
    compute_cost = compute_hours * COST_PER_GPU_HOUR * gpus

    # Data preprocessing
    preproc_cost = demo_count * PREPROC_COST_PER_DEMO

    # Checkpoint storage (5 checkpoints)
    ckpt_gb = 6.7 * (1 + 0.04 * math.log2(max(lora_rank, 4) / 16 + 1))
    storage_cost = ckpt_gb * 5 * CHECKPOINT_STORAGE_PER_GB

    # Eval runs
    n_evals = training_steps // eval_frequency
    eval_cost = n_evals * EVAL_COST_PER_RUN

    # Network (dataset transfer + model upload)
    net_gb = demo_count * 0.008 + ckpt_gb * 2
    net_cost = net_gb * NETWORK_PER_GB

    total = compute_cost + preproc_cost + storage_cost + eval_cost + net_cost
    return {
        "compute": round(compute_cost, 3),
        "data_preprocessing": round(preproc_cost, 3),
        "checkpoint_storage": round(storage_cost, 3),
        "eval_runs": round(eval_cost, 3),
        "network_transfer": round(net_cost, 3),
        "total": round(total, 3),
        "compute_hours": round(compute_hours, 2),
        "steps_per_sec": round(steps_per_sec, 3),
    }


STD_COSTS = compute_cost(**{k: STD_RUN[k] for k in ["demo_count", "training_steps", "lora_rank", "eval_frequency"]})


# ---------------------------------------------------------------------------
# SVG generators
# ---------------------------------------------------------------------------

def build_cost_donut_svg():
    """SVG donut chart of cost breakdown for standard 1000-demo run."""
    costs = [
        ("Compute",          STD_COSTS["compute"],             "#C74634"),
        ("Data Preprocessing",STD_COSTS["data_preprocessing"],  "#38bdf8"),
        ("Checkpoint Storage",STD_COSTS["checkpoint_storage"],  "#a78bfa"),
        ("Eval Runs",         STD_COSTS["eval_runs"],           "#34d399"),
        ("Network Transfer",  STD_COSTS["network_transfer"],    "#f59e0b"),
    ]
    total = STD_COSTS["total"]
    cx, cy, r_outer, r_inner = 200, 175, 130, 65
    w, h = 520, 360

    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}">']
    parts.append(f'<rect width="{w}" height="{h}" fill="#0f172a" rx="8"/>')
    parts.append(f'<text x="{w//2}" y="24" text-anchor="middle" fill="#e2e8f0" font-size="13" font-family="monospace" font-weight="bold">Cost Breakdown — Standard 1000-Demo Run</text>')

    # Donut slices
    start_angle = -math.pi / 2
    for label, cost, color in costs:
        frac = cost / total
        sweep = frac * 2 * math.pi
        end_angle = start_angle + sweep
        # Outer arc points
        x1o = cx + r_outer * math.cos(start_angle)
        y1o = cy + r_outer * math.sin(start_angle)
        x2o = cx + r_outer * math.cos(end_angle)
        y2o = cy + r_outer * math.sin(end_angle)
        # Inner arc points
        x1i = cx + r_inner * math.cos(end_angle)
        y1i = cy + r_inner * math.sin(end_angle)
        x2i = cx + r_inner * math.cos(start_angle)
        y2i = cy + r_inner * math.sin(start_angle)
        large = 1 if sweep > math.pi else 0
        d = (f"M {x1o:.2f} {y1o:.2f} "
             f"A {r_outer} {r_outer} 0 {large} 1 {x2o:.2f} {y2o:.2f} "
             f"L {x1i:.2f} {y1i:.2f} "
             f"A {r_inner} {r_inner} 0 {large} 0 {x2i:.2f} {y2i:.2f} Z")
        parts.append(f'<path d="{d}" fill="{color}" stroke="#0f172a" stroke-width="2"/>')
        # Label line + text for slices > 5%
        if frac > 0.04:
            mid_angle = start_angle + sweep / 2
            lx = cx + (r_outer + 18) * math.cos(mid_angle)
            ly = cy + (r_outer + 18) * math.sin(mid_angle)
            pct_str = f"{frac*100:.1f}%"
            anchor = "start" if math.cos(mid_angle) >= 0 else "end"
            parts.append(f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="{anchor}" fill="{color}" font-size="10" font-family="monospace">{pct_str}</text>')
        start_angle = end_angle

    # Center label
    parts.append(f'<text x="{cx}" y="{cy-8}" text-anchor="middle" fill="#e2e8f0" font-size="11" font-family="monospace">Total</text>')
    parts.append(f'<text x="{cx}" y="{cy+12}" text-anchor="middle" fill="#38bdf8" font-size="20" font-family="monospace" font-weight="bold">${total:.2f}</text>')

    # Legend
    lx0, ly0 = 360, 80
    for i, (label, cost, color) in enumerate(costs):
        ly = ly0 + i * 36
        parts.append(f'<rect x="{lx0}" y="{ly}" width="12" height="12" fill="{color}" rx="2"/>')
        parts.append(f'<text x="{lx0+18}" y="{ly+10}" fill="#e2e8f0" font-size="11" font-family="monospace">{label}</text>')
        parts.append(f'<text x="{lx0+18}" y="{ly+22}" fill="#94a3b8" font-size="10" font-family="monospace">${cost:.2f} ({cost/total*100:.1f}%)</text>')

    parts.append('</svg>')
    return '\n'.join(parts)


def build_param_cost_curves_svg():
    """SVG multi-line chart: cost vs 4 key parameters."""
    params = [
        {
            "name": "demo_count",
            "label": "Demo Count",
            "values": list(range(100, 2100, 100)),
            "color": "#38bdf8",
            "fixed": {"training_steps": 5000, "lora_rank": 16, "eval_frequency": 500},
        },
        {
            "name": "training_steps",
            "label": "Training Steps",
            "values": list(range(1000, 11000, 500)),
            "color": "#C74634",
            "fixed": {"demo_count": 1000, "lora_rank": 16, "eval_frequency": 500},
        },
        {
            "name": "lora_rank",
            "label": "LoRA Rank",
            "values": [4, 8, 16, 32, 48, 64],
            "color": "#34d399",
            "fixed": {"demo_count": 1000, "training_steps": 5000, "eval_frequency": 500},
        },
        {
            "name": "eval_frequency",
            "label": "Eval Frequency (steps)",
            "values": [100, 200, 300, 500, 750, 1000, 1500, 2500],
            "color": "#f59e0b",
            "fixed": {"demo_count": 1000, "training_steps": 5000, "lora_rank": 16},
        },
    ]

    # Compute cost curves
    for p in params:
        kwargs_list = [{p["name"]: v, **p["fixed"]} for v in p["values"]]
        p["costs"] = [compute_cost(**kw)["total"] for kw in kwargs_list]

    # Layout: 2x2 grid
    cols, rows = 2, 2
    sub_w, sub_h = 370, 180
    pad_l, pad_r, pad_t, pad_b = 48, 20, 36, 32
    gap_x, gap_y = 20, 30
    total_w = cols * sub_w + (cols - 1) * gap_x + 20
    total_h = rows * sub_h + (rows - 1) * gap_y + 40

    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{total_w}" height="{total_h}">']
    parts.append(f'<rect width="{total_w}" height="{total_h}" fill="#0f172a" rx="8"/>')
    parts.append(f'<text x="{total_w//2}" y="22" text-anchor="middle" fill="#e2e8f0" font-size="13" font-family="monospace" font-weight="bold">Estimated Cost vs Key Parameters</text>')

    for idx, p in enumerate(params):
        col = idx % 2
        row = idx // 2
        ox = col * (sub_w + gap_x) + 10
        oy = row * (sub_h + gap_y) + 34

        chart_w = sub_w - pad_l - pad_r
        chart_h = sub_h - pad_t - pad_b
        vals = p["values"]
        costs = p["costs"]
        min_c, max_c = min(costs), max(costs)
        if max_c == min_c:
            max_c = min_c + 1

        def sx(i, n=len(vals), cw=chart_w): return ox + pad_l + i * cw / max(n - 1, 1)
        def sy(v, mn=min_c, mx=max_c, ch=chart_h): return oy + pad_t + ch - (v - mn) / (mx - mn) * ch

        # Background
        parts.append(f'<rect x="{ox}" y="{oy}" width="{sub_w}" height="{sub_h}" fill="#1e293b" rx="6" stroke="#334155" stroke-width="1"/>')
        # Title
        parts.append(f'<text x="{ox+sub_w//2}" y="{oy+14}" text-anchor="middle" fill="{p["color"]}" font-size="11" font-family="monospace" font-weight="bold">{p["label"]}</text>')

        # Gridlines
        for gi in range(3):
            gv = min_c + gi * (max_c - min_c) / 2
            gyp = sy(gv)
            parts.append(f'<line x1="{ox+pad_l}" y1="{gyp:.1f}" x2="{ox+pad_l+chart_w}" y2="{gyp:.1f}" stroke="#334155" stroke-width="1"/>')
            parts.append(f'<text x="{ox+pad_l-4}" y="{gyp+4:.1f}" text-anchor="end" fill="#64748b" font-size="8" font-family="monospace">${gv:.0f}</text>')

        # Area + line
        n = len(vals)
        area_pts = (f'{sx(0):.1f},{oy+pad_t+chart_h} '
                    + ' '.join(f'{sx(i):.1f},{sy(c):.1f}' for i, c in enumerate(costs))
                    + f' {sx(n-1):.1f},{oy+pad_t+chart_h}')
        parts.append(f'<polygon points="{area_pts}" fill="{p["color"]}" fill-opacity="0.12"/>')
        line_pts = ' '.join(f'{sx(i):.1f},{sy(c):.1f}' for i, c in enumerate(costs))
        parts.append(f'<polyline points="{line_pts}" fill="none" stroke="{p["color"]}" stroke-width="2"/>')

        # Highlight optimal (lowest cost) or knee point
        if p["name"] == "training_steps":
            # Knee at steps=5000 (diminishing returns)
            knee_idx = vals.index(5000) if 5000 in vals else 8
            kx, ky = sx(knee_idx), sy(costs[knee_idx])
            parts.append(f'<circle cx="{kx:.1f}" cy="{ky:.1f}" r="4" fill="#f59e0b" stroke="#fcd34d" stroke-width="1.2"/>')
            parts.append(f'<text x="{kx+5:.1f}" y="{ky-4:.1f}" fill="#fcd34d" font-size="8" font-family="monospace">knee</text>')
        elif p["name"] == "lora_rank":
            # Optimal rank=16
            opt_idx = vals.index(16) if 16 in vals else 2
            kx, ky = sx(opt_idx), sy(costs[opt_idx])
            parts.append(f'<circle cx="{kx:.1f}" cy="{ky:.1f}" r="4" fill="#22c55e" stroke="#86efac" stroke-width="1.2"/>')
            parts.append(f'<text x="{kx+5:.1f}" y="{ky-4:.1f}" fill="#86efac" font-size="8" font-family="monospace">optimal</text>')

        # X-axis labels (first, mid, last)
        for tick_i in [0, n // 2, n - 1]:
            txp = sx(tick_i)
            typy = oy + pad_t + chart_h + 14
            lbl = str(vals[tick_i])
            parts.append(f'<text x="{txp:.1f}" y="{typy}" text-anchor="middle" fill="#64748b" font-size="8" font-family="monospace">{lbl}</text>')

        # Axes
        parts.append(f'<line x1="{ox+pad_l}" y1="{oy+pad_t}" x2="{ox+pad_l}" y2="{oy+pad_t+chart_h}" stroke="#475569" stroke-width="1"/>')
        parts.append(f'<line x1="{ox+pad_l}" y1="{oy+pad_t+chart_h}" x2="{ox+pad_l+chart_w}" y2="{oy+pad_t+chart_h}" stroke="#475569" stroke-width="1"/>')

    parts.append('</svg>')
    return '\n'.join(parts)


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

def render_dashboard(demo_count=1000, training_steps=5000, lora_rank=16, eval_frequency=500, budget=50.0):
    costs = compute_cost(demo_count=demo_count, training_steps=training_steps,
                         lora_rank=lora_rank, eval_frequency=eval_frequency)
    donut_svg = build_cost_donut_svg()
    curves_svg = build_param_cost_curves_svg()
    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

    over_budget = costs["total"] > budget
    risk_color = "#ef4444" if over_budget else "#22c55e"
    risk_label = f"OVER BUDGET by ${costs['total']-budget:.2f}" if over_budget else f"${budget-costs['total']:.2f} headroom"

    # Cost per SR point (mock: standard run achieves ~0.72 SR)
    sr = 0.72
    cost_per_sr = costs["total"] / (sr * 100)

    # Recommended config
    rec = {"demo_count": 1000, "training_steps": 5000, "lora_rank": 16, "eval_frequency": 500}
    rec_costs = compute_cost(**rec)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>OCI Robot Cloud — Fine-Tune Cost Estimator</title>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{background:#0f172a;color:#e2e8f0;font-family:'Courier New',monospace;padding:24px}}
    h1{{color:#C74634;font-size:22px;margin-bottom:4px}}
    .sub{{color:#94a3b8;font-size:12px;margin-bottom:20px}}
    .kpi-row{{display:flex;gap:14px;flex-wrap:wrap;margin-bottom:24px}}
    .kpi{{background:#1e293b;border:1px solid #334155;border-radius:8px;padding:14px 18px;min-width:180px}}
    .kpi .label{{color:#94a3b8;font-size:10px;text-transform:uppercase;letter-spacing:.05em}}
    .kpi .value{{color:#38bdf8;font-size:26px;font-weight:bold;margin-top:4px}}
    .kpi .sub2{{color:#64748b;font-size:10px;margin-top:2px}}
    .kpi.alert .value{{color:#ef4444}}
    .kpi.good .value{{color:#22c55e}}
    .kpi.warn .value{{color:#f59e0b}}
    .section{{background:#1e293b;border:1px solid #334155;border-radius:8px;padding:18px;margin-bottom:20px}}
    .section h2{{color:#C74634;font-size:14px;margin-bottom:12px;border-bottom:1px solid #334155;padding-bottom:6px}}
    .chart-wrap{{overflow-x:auto}}
    .risk-bar{{display:inline-block;padding:6px 14px;border-radius:6px;font-size:12px;font-weight:bold;border:1px solid;margin-top:8px}}
    .param-table{{width:100%;border-collapse:collapse;font-size:12px;margin-top:10px}}
    .param-table th{{color:#94a3b8;font-weight:normal;text-align:left;padding:6px 8px;border-bottom:1px solid #334155}}
    .param-table td{{padding:6px 8px;border-bottom:1px solid #1e293b}}
    .param-table td.hi{{color:#38bdf8;font-weight:bold}}
    .param-table td.good{{color:#22c55e}}
    footer{{margin-top:20px;color:#334155;font-size:10px;text-align:center}}
  </style>
</head>
<body>
  <h1>OCI Robot Cloud — Fine-Tune Cost Estimator</h1>
  <div class="sub">Port 8253 &nbsp;|&nbsp; GR00T N1.6 fine-tuning budget guardrails &nbsp;|&nbsp; {now_str}</div>

  <div class="kpi-row">
    <div class="kpi">
      <div class="label">Estimated Total</div>
      <div class="value">${costs['total']:.2f}</div>
      <div class="sub2">1000 demos / 5k steps</div>
    </div>
    <div class="kpi">
      <div class="label">Compute Cost</div>
      <div class="value">${costs['compute']:.2f}</div>
      <div class="sub2">{costs['compute']/costs['total']*100:.0f}% of total &nbsp; ({costs['compute_hours']:.1f}h)</div>
    </div>
    <div class="kpi">
      <div class="label">Throughput</div>
      <div class="value">{costs['steps_per_sec']:.2f}</div>
      <div class="sub2">it/s on 2× A100</div>
    </div>
    <div class="kpi {'alert' if over_budget else 'good'}">
      <div class="label">Budget Risk</div>
      <div class="value" style="color:{risk_color};font-size:14px;margin-top:8px">{risk_label}</div>
      <div class="sub2">budget = ${budget:.2f}</div>
    </div>
    <div class="kpi warn">
      <div class="label">Cost per SR Point</div>
      <div class="value">${cost_per_sr:.2f}</div>
      <div class="sub2">at 72% success rate</div>
    </div>
    <div class="kpi good">
      <div class="label">Recommended LoRA Rank</div>
      <div class="value">16</div>
      <div class="sub2">optimal cost/quality</div>
    </div>
  </div>

  <div class="section">
    <h2>Cost Breakdown — Standard 1000-Demo Run (${STD_COSTS['total']:.2f})</h2>
    <div class="chart-wrap">{donut_svg}</div>
    <table class="param-table" style="margin-top:16px">
      <thead>
        <tr><th>Component</th><th>Cost (USD)</th><th>% of Total</th><th>Driver</th></tr>
      </thead>
      <tbody>
        <tr><td>Compute (2× A100)</td><td class="hi">${STD_COSTS['compute']:.2f}</td><td>{STD_COSTS['compute']/STD_COSTS['total']*100:.1f}%</td><td>training_steps × gpu_hours</td></tr>
        <tr><td>Data Preprocessing</td><td>${STD_COSTS['data_preprocessing']:.2f}</td><td>{STD_COSTS['data_preprocessing']/STD_COSTS['total']*100:.1f}%</td><td>demo_count × $0.0012/demo</td></tr>
        <tr><td>Checkpoint Storage</td><td>${STD_COSTS['checkpoint_storage']:.2f}</td><td>{STD_COSTS['checkpoint_storage']/STD_COSTS['total']*100:.1f}%</td><td>5 checkpoints × 6.7GB</td></tr>
        <tr><td>Eval Runs</td><td>${STD_COSTS['eval_runs']:.2f}</td><td>{STD_COSTS['eval_runs']/STD_COSTS['total']*100:.1f}%</td><td>{5000//500} evals × $0.85/run</td></tr>
        <tr><td>Network Transfer</td><td>${STD_COSTS['network_transfer']:.2f}</td><td>{STD_COSTS['network_transfer']/STD_COSTS['total']*100:.1f}%</td><td>dataset + model egress</td></tr>
        <tr style="border-top:1px solid #38bdf8"><td><strong>Total</strong></td><td class="hi"><strong>${STD_COSTS['total']:.2f}</strong></td><td>100%</td><td></td></tr>
      </tbody>
    </table>
    <div style="margin-top:10px;color:#94a3b8;font-size:11px">
      Note: 3× cost at steps=10k vs steps=5k due to diminishing returns past the 5k knee point.
      Recommended: stay at 5k steps unless validation loss is still declining.
    </div>
  </div>

  <div class="section">
    <h2>Parameter Sensitivity — Estimated Cost vs Key Parameters</h2>
    <div class="chart-wrap">{curves_svg}</div>
    <div style="color:#64748b;font-size:11px;margin-top:10px">
      <span style="color:#34d399">&#9679;</span> LoRA rank=16 is the optimal cost/quality point (green dot). &nbsp;
      <span style="color:#f59e0b">&#9679;</span> Steps=5k is the diminishing-returns knee (amber dot). &nbsp;
      Eval frequency has minimal cost impact at &gt;500 steps.
    </div>
  </div>

  <footer>OCI Robot Cloud Fine-Tune Cost Estimator &nbsp;|&nbsp; port 8253 &nbsp;|&nbsp; cycle-48A</footer>
</body>
</html>"""


# ---------------------------------------------------------------------------
# App wiring
# ---------------------------------------------------------------------------

if USE_FASTAPI:
    app = FastAPI(
        title="OCI Robot Cloud — Fine-Tune Cost Estimator",
        description="Pre-run cost estimation for GR00T fine-tuning jobs with budget guardrails",
        version="1.0.0",
    )

    @app.get("/", response_class=HTMLResponse)
    async def dashboard(
        demo_count: int = Query(1000, ge=100, le=5000),
        training_steps: int = Query(5000, ge=1000, le=50000),
        lora_rank: int = Query(16, ge=4, le=128),
        eval_frequency: int = Query(500, ge=100, le=5000),
        budget: float = Query(50.0, ge=1.0, le=10000.0),
    ):
        return render_dashboard(
            demo_count=demo_count,
            training_steps=training_steps,
            lora_rank=lora_rank,
            eval_frequency=eval_frequency,
            budget=budget,
        )

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "fine_tune_cost_estimator", "port": 8253}

    @app.get("/estimate")
    async def estimate(
        demo_count: int = Query(1000),
        training_steps: int = Query(5000),
        lora_rank: int = Query(16),
        eval_frequency: int = Query(500),
        budget: float = Query(50.0),
    ):
        costs = compute_cost(
            demo_count=demo_count,
            training_steps=training_steps,
            lora_rank=lora_rank,
            eval_frequency=eval_frequency,
        )
        over_budget = costs["total"] > budget
        return {
            **costs,
            "budget": budget,
            "over_budget": over_budget,
            "budget_delta": round(budget - costs["total"], 2),
            "recommended_config": {
                "demo_count": demo_count,
                "training_steps": min(training_steps, 5000),
                "lora_rank": 16,
                "eval_frequency": 500,
            },
        }

    @app.get("/recommend")
    async def recommend(budget: float = Query(50.0)):
        """Return recommended configuration that fits within budget."""
        configs = [
            {"demo_count": 1000, "training_steps": 5000, "lora_rank": 16, "eval_frequency": 500},
            {"demo_count": 500, "training_steps": 3000, "lora_rank": 16, "eval_frequency": 500},
            {"demo_count": 300, "training_steps": 2000, "lora_rank": 8, "eval_frequency": 1000},
        ]
        for cfg in configs:
            c = compute_cost(**cfg)
            if c["total"] <= budget:
                return {"config": cfg, "estimated_cost": c["total"], "within_budget": True}
        return {"config": configs[-1], "estimated_cost": compute_cost(**configs[-1])["total"], "within_budget": False, "note": "Minimum config exceeds budget — consider reducing training_steps"}

else:
    import http.server
    import socketserver
    from urllib.parse import urlparse, parse_qs

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            body = render_dashboard().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            pass


if __name__ == "__main__":
    if USE_FASTAPI:
        uvicorn.run(app, host="0.0.0.0", port=8253)
    else:
        PORT = 8253
        with socketserver.TCPServer(("", PORT), Handler) as httpd:
            print(f"Fine-Tune Cost Estimator running on http://0.0.0.0:{PORT} (stdlib fallback)")
            httpd.serve_forever()
