"""Training throughput analysis and optimization tracker — port 8174."""

try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse
    import uvicorn
except ImportError as e:
    raise SystemExit(f"Missing dependency: {e}. Install with: pip install fastapi uvicorn") from e

app = FastAPI(title="Training Throughput Analyzer", version="1.0.0")

# ---------------------------------------------------------------------------
# Static data
# ---------------------------------------------------------------------------

CONFIGS = [
    {
        "name": "single_gpu_fp32",
        "gpus": 1,
        "precision": "fp32",
        "batch": 32,
        "it_per_sec": 1.12,
        "gpu_mem_gb": 71.4,
        "efficiency": 0.61,
        "cost_per_10k": round(0.0043 * (1.12 / 4.47), 4),
    },
    {
        "name": "single_gpu_fp16",
        "gpus": 1,
        "precision": "fp16",
        "batch": 64,
        "it_per_sec": 2.35,
        "gpu_mem_gb": 38.7,
        "efficiency": 0.87,
        "cost_per_10k": round(0.0043 * (2.35 / 4.47), 4),
    },
    {
        "name": "single_gpu_bf16",
        "gpus": 1,
        "precision": "bf16",
        "batch": 64,
        "it_per_sec": 2.41,
        "gpu_mem_gb": 37.2,
        "efficiency": 0.89,
        "cost_per_10k": round(0.0043 * (2.41 / 4.47), 4),
    },
    {
        "name": "dual_gpu_ddp",
        "gpus": 2,
        "precision": "fp16",
        "batch": 128,
        "it_per_sec": 4.47,
        "gpu_mem_gb": 38.1,
        "efficiency": 0.95,
        "cost_per_10k": 0.0043,
    },
    {
        "name": "dual_gpu_fsdp",
        "gpus": 2,
        "precision": "bf16",
        "batch": 128,
        "it_per_sec": 4.62,
        "gpu_mem_gb": 34.8,
        "efficiency": 0.98,
        "cost_per_10k": round(0.0043 * (4.47 / 4.62), 4),
    },
]

CURRENT_CONFIG = "dual_gpu_ddp"
TARGET_STEPS = 5000
COST_PER_10K = 0.0043
FULL_RUN_COST = round(COST_PER_10K * TARGET_STEPS / 10000, 2)

OPTIMIZATION_PATH = (
    "fp32→fp16: +110% throughput, -46% memory. "
    "DDP→FSDP: +3.3% throughput, -8.7% memory. "
    "Next: FP8 target +40% over bf16"
)

# precision color map
PRECISION_COLOR = {"fp32": "#6b7280", "fp16": "#38bdf8", "bf16": "#4ade80"}


# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------

def _throughput_bar_chart() -> str:
    """Horizontal bar chart of it/s per config, sorted ascending."""
    W, H = 680, 200
    pad_left, pad_right, pad_top, pad_bottom = 160, 20, 20, 30
    chart_w = W - pad_left - pad_right
    chart_h = H - pad_top - pad_bottom

    sorted_cfgs = sorted(CONFIGS, key=lambda c: c["it_per_sec"])
    max_val = max(c["it_per_sec"] for c in sorted_cfgs) * 1.15
    n = len(sorted_cfgs)
    bar_area = chart_h / n
    bar_h_single = bar_area * 0.45
    bar_h_dual = bar_area * 0.62

    lines = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#0f172a;border-radius:8px">']

    # x-axis ticks
    for tick in [0, 1, 2, 3, 4, 5]:
        x = pad_left + (tick / max_val) * chart_w
        lines.append(f'<line x1="{x:.1f}" y1="{pad_top}" x2="{x:.1f}" y2="{pad_top+chart_h}" stroke="#1e293b" stroke-width="1"/>')
        lines.append(f'<text x="{x:.1f}" y="{H-6}" fill="#64748b" font-size="10" text-anchor="middle">{tick}</text>')

    for i, cfg in enumerate(sorted_cfgs):
        bh = bar_h_dual if cfg["gpus"] == 2 else bar_h_single
        center_y = pad_top + (i + 0.5) * bar_area
        y = center_y - bh / 2
        bar_w = (cfg["it_per_sec"] / max_val) * chart_w
        color = PRECISION_COLOR[cfg["precision"]]
        cost = cfg["cost_per_10k"]

        # bar
        lines.append(f'<rect x="{pad_left}" y="{y:.1f}" width="{bar_w:.1f}" height="{bh:.1f}" fill="{color}" rx="3" opacity="0.85"/>')
        # label
        lines.append(f'<text x="{pad_left-8}" y="{center_y+4:.1f}" fill="#cbd5e1" font-size="11" text-anchor="end">{cfg["name"]}</text>')
        # annotation
        ann_x = pad_left + bar_w + 6
        lines.append(f'<text x="{ann_x:.1f}" y="{center_y+4:.1f}" fill="#94a3b8" font-size="10">{cfg["it_per_sec"]} it/s · ${cost}/10k</text>')

    # axis label
    lines.append(f'<text x="{pad_left + chart_w/2:.1f}" y="{H-1}" fill="#64748b" font-size="10" text-anchor="middle">iterations / second</text>')
    lines.append('</svg>')
    return '\n'.join(lines)


def _efficiency_scatter() -> str:
    """Scatter: x=gpu_mem_gb, y=it_per_sec; bubble size ~ efficiency."""
    W, H = 680, 200
    pad_left, pad_right, pad_top, pad_bottom = 50, 20, 20, 30
    chart_w = W - pad_left - pad_right
    chart_h = H - pad_top - pad_bottom

    mem_vals = [c["gpu_mem_gb"] for c in CONFIGS]
    spd_vals = [c["it_per_sec"] for c in CONFIGS]
    min_mem, max_mem = 30, 80
    min_spd, max_spd = 0, 5.5

    def cx(m):
        return pad_left + (m - min_mem) / (max_mem - min_mem) * chart_w

    def cy(s):
        return pad_top + chart_h - (s - min_spd) / (max_spd - min_spd) * chart_h

    lines = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#0f172a;border-radius:8px">']

    # grid
    for tick in [30, 40, 50, 60, 70, 80]:
        x = cx(tick)
        lines.append(f'<line x1="{x:.1f}" y1="{pad_top}" x2="{x:.1f}" y2="{pad_top+chart_h}" stroke="#1e293b" stroke-width="1"/>')
        lines.append(f'<text x="{x:.1f}" y="{H-4}" fill="#64748b" font-size="9" text-anchor="middle">{tick}GB</text>')
    for tick in [1, 2, 3, 4, 5]:
        y = cy(tick)
        lines.append(f'<line x1="{pad_left}" y1="{y:.1f}" x2="{W-pad_right}" y2="{y:.1f}" stroke="#1e293b" stroke-width="1"/>')
        lines.append(f'<text x="{pad_left-4}" y="{y+4:.1f}" fill="#64748b" font-size="9" text-anchor="end">{tick}</text>')

    # Pareto frontier (sort by mem, pick non-dominated points in speed)
    sorted_by_mem = sorted(CONFIGS, key=lambda c: c["gpu_mem_gb"])
    pareto = []
    best_spd = -1.0
    for c in sorted_by_mem:
        if c["it_per_sec"] > best_spd:
            best_spd = c["it_per_sec"]
            pareto.append(c)
    if len(pareto) >= 2:
        pts = " ".join(f"{cx(c['gpu_mem_gb']):.1f},{cy(c['it_per_sec']):.1f}" for c in pareto)
        lines.append(f'<polyline points="{pts}" fill="none" stroke="#C74634" stroke-width="1.5" stroke-dasharray="4 3" opacity="0.7"/>')

    # bubbles
    colors = ["#6b7280", "#38bdf8", "#4ade80", "#a78bfa", "#fb923c"]
    for i, cfg in enumerate(CONFIGS):
        r = 6 + cfg["efficiency"] * 14
        x, y = cx(cfg["gpu_mem_gb"]), cy(cfg["it_per_sec"])
        lines.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" fill="{colors[i]}" opacity="0.75"/>')
        lines.append(f'<text x="{x:.1f}" y="{y-r-3:.1f}" fill="#cbd5e1" font-size="9" text-anchor="middle">{cfg["name"]}</text>')

    lines.append('</svg>')
    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def dashboard() -> str:
    bar_svg = _throughput_bar_chart()
    scatter_svg = _efficiency_scatter()
    current = next(c for c in CONFIGS if c["name"] == CURRENT_CONFIG)

    legend_items = "".join(
        f'<span style="display:inline-flex;align-items:center;gap:4px;margin-right:14px">'
        f'<span style="width:12px;height:12px;border-radius:2px;background:{PRECISION_COLOR[p]};display:inline-block"></span>'
        f'<span style="color:#94a3b8;font-size:12px">{p}</span></span>'
        for p in ["fp32", "fp16", "bf16"]
    )

    config_rows = "".join(
        f"""<tr style="border-bottom:1px solid #1e293b">
          <td style="padding:8px 12px;color:{'#C74634' if c['name']==CURRENT_CONFIG else '#cbd5e1'};font-weight:{'600' if c['name']==CURRENT_CONFIG else 'normal'}">{c['name']} {'★' if c['name']==CURRENT_CONFIG else ''}</td>
          <td style="padding:8px 12px;color:#94a3b8">{c['gpus']}</td>
          <td style="padding:8px 12px;color:{PRECISION_COLOR[c['precision']]}">{c['precision']}</td>
          <td style="padding:8px 12px;color:#e2e8f0">{c['it_per_sec']}</td>
          <td style="padding:8px 12px;color:#38bdf8">{c['gpu_mem_gb']} GB</td>
          <td style="padding:8px 12px;color:#4ade80">{int(c['efficiency']*100)}%</td>
          <td style="padding:8px 12px;color:#f59e0b">${c['cost_per_10k']}</td>
        </tr>"""
        for c in CONFIGS
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <title>Training Throughput Analyzer — Port 8174</title>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{background:#0f172a;color:#e2e8f0;font-family:'Segoe UI',system-ui,sans-serif;padding:24px}}
    h1{{color:#C74634;font-size:22px;margin-bottom:4px}}
    .sub{{color:#64748b;font-size:13px;margin-bottom:24px}}
    .stat-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:24px}}
    .card{{background:#1e293b;border-radius:8px;padding:16px;border-left:3px solid #C74634}}
    .card-val{{font-size:24px;font-weight:700;color:#38bdf8}}
    .card-lbl{{font-size:12px;color:#64748b;margin-top:4px}}
    .section{{margin-bottom:24px}}
    .section-title{{color:#94a3b8;font-size:13px;text-transform:uppercase;letter-spacing:.05em;margin-bottom:10px}}
    table{{width:100%;border-collapse:collapse;background:#1e293b;border-radius:8px;overflow:hidden}}
    th{{padding:10px 12px;color:#64748b;font-size:12px;text-align:left;background:#0f172a;text-transform:uppercase}}
    .opt-box{{background:#1e293b;border-radius:8px;padding:14px 18px;border-left:3px solid #38bdf8;color:#94a3b8;font-size:13px;line-height:1.6}}
    .legend{{margin-bottom:8px}}
  </style>
</head>
<body>
  <h1>Training Throughput Analyzer</h1>
  <div class="sub">OCI Robot Cloud · Port 8174 · GR00T N1.6 Fine-tuning Performance</div>

  <div class="stat-grid">
    <div class="card"><div class="card-val">{current['it_per_sec']} it/s</div><div class="card-lbl">Current throughput (DDP fp16)</div></div>
    <div class="card"><div class="card-val">${COST_PER_10K}</div><div class="card-lbl">Cost per 10k steps</div></div>
    <div class="card"><div class="card-val">${FULL_RUN_COST}</div><div class="card-lbl">Full training run ({TARGET_STEPS} steps)</div></div>
    <div class="card"><div class="card-val" style="color:#4ade80">{int(current['efficiency']*100)}%</div><div class="card-lbl">GPU utilization efficiency</div></div>
  </div>

  <div class="section">
    <div class="section-title">Throughput Comparison (it/s)</div>
    <div class="legend">{legend_items}</div>
    {bar_svg}
  </div>

  <div class="section">
    <div class="section-title">Efficiency Scatter: Memory vs Throughput (bubble = efficiency)</div>
    <div style="color:#64748b;font-size:11px;margin-bottom:6px">Pareto frontier in red dashed; lower-left = better memory; higher = faster training</div>
    {scatter_svg}
  </div>

  <div class="section">
    <div class="section-title">All Configurations</div>
    <table>
      <thead><tr>
        <th>Config</th><th>GPUs</th><th>Precision</th><th>it/s</th><th>GPU Mem</th><th>Efficiency</th><th>$/10k steps</th>
      </tr></thead>
      <tbody>{config_rows}</tbody>
    </table>
  </div>

  <div class="section">
    <div class="section-title">Optimization Path</div>
    <div class="opt-box">{OPTIMIZATION_PATH}</div>
  </div>
</body>
</html>"""
    return HTMLResponse(content=html)


@app.get("/configs")
def get_configs():
    return JSONResponse(content=CONFIGS)


@app.get("/current")
def get_current():
    cfg = next(c for c in CONFIGS if c["name"] == CURRENT_CONFIG)
    return JSONResponse(content={
        **cfg,
        "target_steps": TARGET_STEPS,
        "full_run_cost_usd": FULL_RUN_COST,
        "optimization_path": OPTIMIZATION_PATH,
    })


@app.get("/comparison")
def get_comparison():
    baseline = next(c for c in CONFIGS if c["name"] == "single_gpu_fp32")
    rows = []
    for c in CONFIGS:
        speedup = round(c["it_per_sec"] / baseline["it_per_sec"], 2)
        mem_delta_pct = round((c["gpu_mem_gb"] - baseline["gpu_mem_gb"]) / baseline["gpu_mem_gb"] * 100, 1)
        rows.append({
            "name": c["name"],
            "speedup_vs_fp32": speedup,
            "mem_delta_pct_vs_fp32": mem_delta_pct,
            "efficiency": c["efficiency"],
        })
    return JSONResponse(content={"baseline": "single_gpu_fp32", "comparison": rows})


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8174)
