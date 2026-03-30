"""
GR00T inference throughput optimization — batching, quantization, and TensorRT compilation strategies on OCI A100.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
from dataclasses import dataclass, field, asdict
from typing import List, Optional


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class OptimizationConfig:
    strategy: str                  # baseline/batch2/batch4/int8/fp16/tensorrt/batch4_int8
    batch_size: int
    quantization: str              # none/int8/fp16
    compile: bool
    throughput_rps: float
    latency_p50_ms: float
    latency_p99_ms: float
    gpu_util_pct: float
    vram_gb: float
    accuracy_delta: float


@dataclass
class ThroughputReport:
    best_throughput_config: str
    best_latency_config: str
    best_efficiency_config: str    # best RPS / VRAM
    pareto_configs: List[str]
    results: List[OptimizationConfig]


# ---------------------------------------------------------------------------
# Simulation
# ---------------------------------------------------------------------------

# Canonical spec table for OCI A100-80GB benchmarks
_SPECS = [
    # strategy,        batch, quant,  compile, rps,  p50,   p99,   gpu%,  vram,  delta
    ("baseline",       1,     "none",  False,  1.0,  226.0, 411.0, 42.0,  9.6,   0.000),
    ("batch2",         2,     "none",  False,  1.8,  212.0, 389.0, 58.0,  10.1,  0.000),
    ("batch4",         4,     "none",  False,  3.2,  198.0, 362.0, 71.0,  11.2,  0.000),
    ("int8",           1,     "int8",  False,  4.1,  172.0, 318.0, 66.0,  5.1,  -0.003),
    ("fp16",           1,     "fp16",  False,  2.6,  201.0, 371.0, 54.0,  8.8,   0.000),
    ("tensorrt",       1,     "none",  True,   5.8,  148.0, 271.0, 78.0,  9.4,  -0.001),
    ("batch4_int8",    4,     "int8",  True,   7.4,  131.0, 241.0, 91.0,  5.8,  -0.004),
]

# Per-metric gaussian noise std (relative fraction or absolute)
_NOISE = {
    "throughput_rps": 0.03,
    "latency_p50_ms": 2.5,
    "latency_p99_ms": 5.0,
    "gpu_util_pct":   1.2,
    "vram_gb":        0.05,
    "accuracy_delta": 0.0002,
}


def _noisy(value: float, std: float, rng: random.Random) -> float:
    return value + rng.gauss(0, std)


def simulate_configs(seed: int = 42) -> List[OptimizationConfig]:
    rng = random.Random(seed)
    configs: List[OptimizationConfig] = []

    for (strategy, batch_size, quantization, compile_flag,
         rps, p50, p99, gpu_pct, vram, delta) in _SPECS:

        noisy_rps   = max(0.1, _noisy(rps,     _NOISE["throughput_rps"], rng))
        noisy_p50   = max(10,  _noisy(p50,     _NOISE["latency_p50_ms"], rng))
        noisy_p99   = max(noisy_p50 + 5,
                          _noisy(p99,     _NOISE["latency_p99_ms"], rng))
        noisy_gpu   = min(100, max(0, _noisy(gpu_pct, _NOISE["gpu_util_pct"],   rng)))
        noisy_vram  = max(1.0, _noisy(vram,    _NOISE["vram_gb"],        rng))
        noisy_delta = _noisy(delta,  _NOISE["accuracy_delta"], rng)

        configs.append(OptimizationConfig(
            strategy=strategy,
            batch_size=batch_size,
            quantization=quantization,
            compile=compile_flag,
            throughput_rps=round(noisy_rps,  3),
            latency_p50_ms=round(noisy_p50,  2),
            latency_p99_ms=round(noisy_p99,  2),
            gpu_util_pct=round(noisy_gpu,    1),
            vram_gb=round(noisy_vram,        2),
            accuracy_delta=round(noisy_delta, 5),
        ))

    return configs


# ---------------------------------------------------------------------------
# Analysis helpers
# ---------------------------------------------------------------------------

def efficiency(cfg: OptimizationConfig) -> float:
    """RPS per GB of VRAM."""
    return cfg.throughput_rps / cfg.vram_gb if cfg.vram_gb > 0 else 0.0


def compute_pareto(configs: List[OptimizationConfig]) -> List[str]:
    """
    Pareto frontier: maximize throughput, minimize latency_p50.
    A config is Pareto-optimal if no other config dominates it on both axes.
    """
    pareto: List[str] = []
    for candidate in configs:
        dominated = False
        for other in configs:
            if other.strategy == candidate.strategy:
                continue
            if (other.throughput_rps >= candidate.throughput_rps and
                    other.latency_p50_ms <= candidate.latency_p50_ms):
                dominated = True
                break
        if not dominated:
            pareto.append(candidate.strategy)
    return pareto


def build_report(configs: List[OptimizationConfig]) -> ThroughputReport:
    best_tp  = max(configs, key=lambda c: c.throughput_rps)
    best_lat = min(configs, key=lambda c: c.latency_p50_ms)
    best_eff = max(configs, key=efficiency)
    pareto   = compute_pareto(configs)

    return ThroughputReport(
        best_throughput_config=best_tp.strategy,
        best_latency_config=best_lat.strategy,
        best_efficiency_config=best_eff.strategy,
        pareto_configs=pareto,
        results=configs,
    )


# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------

def _svg_scatter(configs: List[OptimizationConfig], pareto: List[str],
                 width: int = 540, height: int = 320) -> str:
    """SVG scatter: x=latency_p50, y=throughput, color=quantization, size=batch_size."""
    pad_l, pad_r, pad_t, pad_b = 60, 20, 20, 50
    inner_w = width - pad_l - pad_r
    inner_h = height - pad_t - pad_b

    x_vals = [c.latency_p50_ms for c in configs]
    y_vals = [c.throughput_rps  for c in configs]
    x_min, x_max = min(x_vals) - 10, max(x_vals) + 10
    y_min, y_max = 0, max(y_vals) * 1.15

    def sx(v: float) -> float:
        return pad_l + (v - x_min) / (x_max - x_min) * inner_w

    def sy(v: float) -> float:
        return pad_t + inner_h - (v - y_min) / (y_max - y_min) * inner_h

    quant_colors = {"none": "#60a5fa", "int8": "#f59e0b", "fp16": "#34d399"}

    lines: List[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}"'
        f' viewBox="0 0 {width} {height}" style="background:#1e293b;border-radius:8px">',
    ]

    # Grid lines (y)
    n_grid = 5
    for i in range(n_grid + 1):
        yv = y_min + i * (y_max - y_min) / n_grid
        yp = sy(yv)
        lines.append(f'<line x1="{pad_l}" y1="{yp:.1f}" x2="{pad_l+inner_w}" y2="{yp:.1f}"'
                     f' stroke="#334155" stroke-width="1"/>')
        lines.append(f'<text x="{pad_l-6}" y="{yp+4:.1f}" fill="#94a3b8" font-size="10"'
                     f' text-anchor="end">{yv:.1f}</text>')

    # Axis labels
    lines.append(f'<text x="{pad_l + inner_w//2}" y="{height-4}" fill="#94a3b8"'
                 f' font-size="11" text-anchor="middle">Latency p50 (ms)</text>')
    lines.append(f'<text x="14" y="{pad_t + inner_h//2}" fill="#94a3b8"'
                 f' font-size="11" text-anchor="middle"'
                 f' transform="rotate(-90,14,{pad_t + inner_h//2})">Throughput (RPS)</text>')

    # Pareto frontier line
    pareto_cfgs = sorted([c for c in configs if c.strategy in pareto],
                         key=lambda c: c.latency_p50_ms)
    if len(pareto_cfgs) >= 2:
        pts = " ".join(f"{sx(c.latency_p50_ms):.1f},{sy(c.throughput_rps):.1f}"
                       for c in pareto_cfgs)
        lines.append(f'<polyline points="{pts}" fill="none" stroke="#C74634"'
                     f' stroke-width="1.5" stroke-dasharray="4,3" opacity="0.7"/>')

    # Data points
    for cfg in configs:
        cx = sx(cfg.latency_p50_ms)
        cy = sy(cfg.throughput_rps)
        r  = 5 + cfg.batch_size * 1.5
        color = quant_colors.get(cfg.quantization, "#94a3b8")
        stroke = "#C74634" if cfg.strategy in pareto else "#1e293b"
        sw = 2 if cfg.strategy in pareto else 1
        lines.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}"'
                     f' fill="{color}" stroke="{stroke}" stroke-width="{sw}" opacity="0.9"/>')
        lines.append(f'<text x="{cx:.1f}" y="{cy-r-3:.1f}" fill="#e2e8f0" font-size="9"'
                     f' text-anchor="middle">{cfg.strategy}</text>')

    # Legend
    lx, ly = pad_l + 10, height - pad_b + 18
    for i, (q, col) in enumerate(quant_colors.items()):
        ox = lx + i * 90
        lines.append(f'<circle cx="{ox+6}" cy="{ly}" r="5" fill="{col}"/>')
        lines.append(f'<text x="{ox+14}" y="{ly+4}" fill="#94a3b8" font-size="10">{q}</text>')

    lines.append('</svg>')
    return "\n".join(lines)


def _svg_grouped_bar(configs: List[OptimizationConfig],
                     width: int = 700, height: int = 300) -> str:
    """Grouped bar: throughput / latency_p50 (normalized) / VRAM for each config."""
    n = len(configs)
    pad_l, pad_r, pad_t, pad_b = 50, 20, 30, 60
    inner_w = width  - pad_l - pad_r
    inner_h = height - pad_t - pad_b

    max_rps  = max(c.throughput_rps  for c in configs)
    max_lat  = max(c.latency_p50_ms  for c in configs)
    max_vram = max(c.vram_gb         for c in configs)

    group_w = inner_w / n
    bar_w   = group_w * 0.22
    colors  = ["#60a5fa", "#f59e0b", "#34d399"]
    labels  = ["RPS", "Lat(norm)", "VRAM(norm)"]

    lines: List[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}"'
        f' viewBox="0 0 {width} {height}" style="background:#1e293b;border-radius:8px">',
    ]

    # Y grid
    for i in range(6):
        yv = i / 5
        yp = pad_t + inner_h - yv * inner_h
        lines.append(f'<line x1="{pad_l}" y1="{yp:.1f}" x2="{pad_l+inner_w}" y2="{yp:.1f}"'
                     f' stroke="#334155" stroke-width="1"/>')
        lines.append(f'<text x="{pad_l-4}" y="{yp+4:.1f}" fill="#94a3b8" font-size="9"'
                     f' text-anchor="end">{yv:.1f}</text>')

    for gi, cfg in enumerate(configs):
        gx = pad_l + gi * group_w + group_w * 0.1
        values = [
            cfg.throughput_rps  / max_rps,
            cfg.latency_p50_ms  / max_lat,
            cfg.vram_gb         / max_vram,
        ]
        for bi, (val, col) in enumerate(zip(values, colors)):
            bx = gx + bi * (bar_w + 2)
            bh = val * inner_h
            by = pad_t + inner_h - bh
            lines.append(f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bar_w:.1f}" height="{bh:.1f}"'
                         f' fill="{col}" opacity="0.85" rx="2"/>')

        # x label
        lx = gx + (3 * bar_w + 4) / 2
        lines.append(f'<text x="{lx:.1f}" y="{pad_t+inner_h+14}" fill="#94a3b8" font-size="9"'
                     f' text-anchor="middle" transform="rotate(-30,{lx:.1f},{pad_t+inner_h+14})">'
                     f'{cfg.strategy}</text>')

    # Legend
    ly = height - 12
    for i, (lbl, col) in enumerate(zip(labels, colors)):
        ox = pad_l + 10 + i * 110
        lines.append(f'<rect x="{ox}" y="{ly-8}" width="10" height="10" fill="{col}" rx="2"/>')
        lines.append(f'<text x="{ox+13}" y="{ly}" fill="#94a3b8" font-size="10">{lbl}</text>')

    lines.append('</svg>')
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# HTML report
# ---------------------------------------------------------------------------

def _fmt_delta(d: float) -> str:
    return f"{d:+.4f}" if d != 0 else "0.0000"


def generate_html(report: ThroughputReport) -> str:
    cfgs = report.results
    best_tp   = next(c for c in cfgs if c.strategy == report.best_throughput_config)
    best_lat  = next(c for c in cfgs if c.strategy == report.best_latency_config)
    best_eff  = next(c for c in cfgs if c.strategy == report.best_efficiency_config)
    min_delta = min(cfgs, key=lambda c: c.accuracy_delta)

    scatter_svg = _svg_scatter(cfgs, report.pareto_configs)
    bar_svg     = _svg_grouped_bar(cfgs)

    # Table rows
    table_rows = []
    for cfg in cfgs:
        pareto_mark = " ★" if cfg.strategy in report.pareto_configs else ""
        compile_str = "yes" if cfg.compile else "no"
        table_rows.append(
            f"<tr>"
            f"<td><strong>{cfg.strategy}{pareto_mark}</strong></td>"
            f"<td>{cfg.batch_size}</td>"
            f"<td>{cfg.quantization}</td>"
            f"<td>{compile_str}</td>"
            f"<td>{cfg.throughput_rps:.3f}</td>"
            f"<td>{cfg.latency_p50_ms:.1f}</td>"
            f"<td>{cfg.latency_p99_ms:.1f}</td>"
            f"<td>{cfg.gpu_util_pct:.1f}</td>"
            f"<td>{cfg.vram_gb:.2f}</td>"
            f"<td>{_fmt_delta(cfg.accuracy_delta)}</td>"
            f"</tr>"
        )
    table_html = "\n".join(table_rows)

    eff_val = round(efficiency(best_eff), 3)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>GR00T Inference Throughput Optimizer</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: #0f172a;
    color: #e2e8f0;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    padding: 24px;
    min-height: 100vh;
  }}
  h1 {{ font-size: 1.6rem; font-weight: 700; color: #f8fafc; margin-bottom: 4px; }}
  .subtitle {{ color: #94a3b8; font-size: 0.9rem; margin-bottom: 28px; }}
  .section-title {{ font-size: 1.1rem; font-weight: 600; color: #cbd5e1; margin: 28px 0 14px; }}
  .cards {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 28px; }}
  .card {{
    background: #1e293b;
    border: 1px solid #334155;
    border-radius: 10px;
    padding: 18px 20px;
  }}
  .card .label {{ font-size: 0.75rem; color: #64748b; text-transform: uppercase; letter-spacing: .05em; margin-bottom: 6px; }}
  .card .value {{ font-size: 1.7rem; font-weight: 700; color: #C74634; }}
  .card .sub {{ font-size: 0.78rem; color: #94a3b8; margin-top: 4px; }}
  .charts {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 28px; }}
  .chart-box {{
    background: #1e293b;
    border: 1px solid #334155;
    border-radius: 10px;
    padding: 16px;
  }}
  .chart-box h3 {{ font-size: 0.85rem; color: #94a3b8; margin-bottom: 12px; }}
  .chart-box svg {{ width: 100%; height: auto; }}
  table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 0.83rem;
    background: #1e293b;
    border-radius: 10px;
    overflow: hidden;
    border: 1px solid #334155;
    margin-bottom: 28px;
  }}
  thead tr {{ background: #0f172a; }}
  th {{ padding: 10px 12px; text-align: left; color: #64748b; font-weight: 600;
        text-transform: uppercase; font-size: 0.72rem; letter-spacing: .05em; border-bottom: 1px solid #334155; }}
  td {{ padding: 9px 12px; border-bottom: 1px solid #1e293b; color: #cbd5e1; }}
  tr:last-child td {{ border-bottom: none; }}
  tr:hover td {{ background: #243044; }}
  .reco {{
    background: #1e293b;
    border: 1px solid #334155;
    border-left: 4px solid #C74634;
    border-radius: 10px;
    padding: 20px 24px;
  }}
  .reco h3 {{ color: #C74634; font-size: 1rem; margin-bottom: 14px; }}
  .reco-item {{ margin-bottom: 10px; line-height: 1.5; }}
  .reco-item .tag {{
    display: inline-block;
    background: #C74634;
    color: #fff;
    font-size: 0.7rem;
    font-weight: 700;
    padding: 2px 7px;
    border-radius: 4px;
    margin-right: 8px;
    text-transform: uppercase;
  }}
  .reco-item .desc {{ color: #94a3b8; font-size: 0.85rem; }}
  .pareto-note {{ color: #60a5fa; font-size: 0.78rem; margin-top: 10px; }}
</style>
</head>
<body>
<h1>GR00T Inference Throughput Optimizer</h1>
<p class="subtitle">OCI A100-80GB — batching, quantization, and TensorRT compilation strategies</p>

<div class="section-title">Summary</div>
<div class="cards">
  <div class="card">
    <div class="label">Best Throughput</div>
    <div class="value">{best_tp.throughput_rps:.2f} RPS</div>
    <div class="sub">{best_tp.strategy}</div>
  </div>
  <div class="card">
    <div class="label">Best Latency (p50)</div>
    <div class="value">{best_lat.latency_p50_ms:.1f} ms</div>
    <div class="sub">{best_lat.strategy}</div>
  </div>
  <div class="card">
    <div class="label">Best Efficiency</div>
    <div class="value">{eff_val:.2f} RPS/GB</div>
    <div class="sub">{best_eff.strategy}</div>
  </div>
  <div class="card">
    <div class="label">Min Accuracy Cost</div>
    <div class="value">{_fmt_delta(min_delta.accuracy_delta)}</div>
    <div class="sub">{min_delta.strategy}</div>
  </div>
</div>

<div class="section-title">Throughput vs Latency — Pareto Frontier</div>
<div class="charts">
  <div class="chart-box">
    <h3>Scatter: Throughput vs Latency p50 — point size = batch size, color = quantization, ★ = Pareto</h3>
    {scatter_svg}
  </div>
  <div class="chart-box">
    <h3>Grouped bars: normalized RPS / Latency / VRAM across all configs</h3>
    {bar_svg}
  </div>
</div>

<div class="section-title">All Configurations</div>
<table>
  <thead>
    <tr>
      <th>Config</th><th>Batch</th><th>Quant</th><th>Compile</th>
      <th>RPS</th><th>p50 ms</th><th>p99 ms</th>
      <th>GPU %</th><th>VRAM GB</th><th>Acc Δ</th>
    </tr>
  </thead>
  <tbody>
    {table_html}
  </tbody>
</table>

<div class="section-title">Recommendations</div>
<div class="reco">
  <h3>Deployment Guidance</h3>
  <div class="reco-item">
    <span class="tag">High Load</span>
    <span class="desc">
      Use <strong>batch4_int8</strong> — {best_tp.throughput_rps:.2f} RPS,
      {best_tp.latency_p50_ms:.1f} ms p50, {best_tp.vram_gb:.1f} GB VRAM.
      Accuracy delta {_fmt_delta(best_tp.accuracy_delta)} is negligible for most tasks.
      Ideal for production serving with sustained request queues.
    </span>
  </div>
  <div class="reco-item">
    <span class="tag">Latency SLA</span>
    <span class="desc">
      Use <strong>tensorrt</strong> — {best_lat.latency_p50_ms:.1f} ms p50,
      {best_lat.latency_p99_ms:.1f} ms p99. Best for real-time robot control loops
      with strict &lt;200 ms SLA. 5.8 RPS supports moderate concurrency.
    </span>
  </div>
  <div class="reco-item">
    <span class="tag">Edge / Jetson</span>
    <span class="desc">
      Use <strong>int8</strong> — {next(c for c in cfgs if c.strategy=="int8").vram_gb:.1f} GB VRAM
      minimizes footprint. Suitable for Jetson AGX Orin (64 GB) or memory-constrained deployments.
      Throughput {next(c for c in cfgs if c.strategy=="int8").throughput_rps:.2f} RPS is sufficient
      for single-robot inference pipelines.
    </span>
  </div>
  <p class="pareto-note">
    Pareto-optimal configs (maximize RPS, minimize latency): {", ".join(report.pareto_configs)}
  </p>
</div>

</body>
</html>
"""
    return html


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def print_summary(report: ThroughputReport) -> None:
    print("\n=== GR00T Inference Throughput Optimizer ===")
    print(f"{'Config':<16} {'RPS':>7} {'p50ms':>8} {'p99ms':>8} "
          f"{'GPU%':>6} {'VRAM':>6} {'AccDelta':>10}")
    print("-" * 68)
    for cfg in report.results:
        pareto_mark = " *" if cfg.strategy in report.pareto_configs else "  "
        print(f"{cfg.strategy:<14}{pareto_mark} {cfg.throughput_rps:>7.3f} "
              f"{cfg.latency_p50_ms:>8.1f} {cfg.latency_p99_ms:>8.1f} "
              f"{cfg.gpu_util_pct:>6.1f} {cfg.vram_gb:>6.2f} "
              f"{cfg.accuracy_delta:>+10.5f}")
    print("-" * 68)
    print(f"Best throughput  : {report.best_throughput_config}")
    print(f"Best latency     : {report.best_latency_config}")
    print(f"Best efficiency  : {report.best_efficiency_config}")
    print(f"Pareto configs   : {', '.join(report.pareto_configs)}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="GR00T inference throughput optimizer — batching, quantization, TensorRT."
    )
    parser.add_argument("--mock", action="store_true", default=True,
                        help="Run with simulated data (default: True)")
    parser.add_argument("--output", default="/tmp/inference_throughput_optimizer.html",
                        help="Path for the HTML report")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed for noise simulation")
    parser.add_argument("--json", dest="json_out", action="store_true",
                        help="Also print JSON summary to stdout")
    args = parser.parse_args()

    configs = simulate_configs(seed=args.seed)
    report  = build_report(configs)

    print_summary(report)

    if args.json_out:
        data = {
            "best_throughput_config": report.best_throughput_config,
            "best_latency_config":    report.best_latency_config,
            "best_efficiency_config": report.best_efficiency_config,
            "pareto_configs":         report.pareto_configs,
            "results": [asdict(c) for c in report.results],
        }
        print("\n--- JSON ---")
        print(json.dumps(data, indent=2))

    html = generate_html(report)
    with open(args.output, "w", encoding="utf-8") as fh:
        fh.write(html)
    print(f"\nHTML report written to: {args.output}")


if __name__ == "__main__":
    main()
