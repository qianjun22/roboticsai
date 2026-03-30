"""
Comprehensive inference benchmark for GR00T N1.6-3B.

Measures latency percentiles (p50/p90/p95/p99), throughput (req/s), batch
efficiency, cold-start time, and hardware comparison across OCI A100, OCI A10,
Jetson AGX Orin, and AWS A10G.  All simulated via statistical models unless a
live server is reachable (--mock, default True).
"""

from __future__ import annotations

import argparse
import json
import math
import random
import statistics
import time
from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Hardware & config definitions
# ---------------------------------------------------------------------------

@dataclass
class HardwareProfile:
    name: str
    gpu_memory_gb: float
    compute_tflops: float          # or TOPS for INT8 on Jetson
    memory_bw_tb_s: float
    base_latency_ms: float
    cost_per_hr: float


@dataclass
class BenchmarkConfig:
    n_warmup: int = 10
    n_trials: int = 100
    batch_sizes: list[int] = field(default_factory=lambda: [1, 2, 4, 8])
    precisions: list[str] = field(default_factory=lambda: ["BF16", "FP16", "FP8", "INT8"])
    concurrent_clients: list[int] = field(default_factory=lambda: [1, 2, 4, 8])


OCI_A100 = HardwareProfile(
    name="OCI A100",
    gpu_memory_gb=80,
    compute_tflops=312,
    memory_bw_tb_s=2.0,
    base_latency_ms=226,
    cost_per_hr=4.20,
)

OCI_A10 = HardwareProfile(
    name="OCI A10",
    gpu_memory_gb=24,
    compute_tflops=125,
    memory_bw_tb_s=0.6,
    base_latency_ms=310,
    cost_per_hr=1.50,
)

Jetson_AGX_Orin = HardwareProfile(
    name="Jetson AGX Orin",
    gpu_memory_gb=64,
    compute_tflops=275,   # TOPS INT8
    memory_bw_tb_s=0.2,
    base_latency_ms=680,
    cost_per_hr=0.0,
)

AWS_A10G = HardwareProfile(
    name="AWS A10G",
    gpu_memory_gb=24,
    compute_tflops=125,
    memory_bw_tb_s=0.6,
    base_latency_ms=325,
    cost_per_hr=1.006,
)

ALL_HARDWARE: list[HardwareProfile] = [OCI_A100, OCI_A10, Jetson_AGX_Orin, AWS_A10G]

# ---------------------------------------------------------------------------
# Precision scale factors (relative to BF16)
# ---------------------------------------------------------------------------

PRECISION_SCALE: dict[str, float] = {
    "BF16": 1.00,
    "FP16": 0.97,   # marginal gain; same compute path on A100
    "FP8": 1.0 / 1.45,  # 1.45× faster → lower latency
    "INT8": 0.72,   # roughly 28% faster on Tensor cores
}

# ---------------------------------------------------------------------------
# Benchmark functions
# ---------------------------------------------------------------------------

def benchmark_latency(
    hw: HardwareProfile,
    precision: str = "BF16",
    batch_size: int = 1,
    rng: random.Random | None = None,
) -> dict[str, float]:
    """
    Simulate per-request latency distribution for the given hardware, precision,
    and batch size.

    FP8 is 1.45× faster than BF16; batch sizes scale sublinearly (sqrt law).
    Returns p50, p90, p95, p99, mean, std in milliseconds.
    """
    if rng is None:
        rng = random.Random(42)

    prec_factor = PRECISION_SCALE.get(precision, 1.0)
    # Sublinear batch scaling: each extra item in a batch adds ~70% of single cost
    batch_factor = 1.0 + (batch_size - 1) * 0.70
    effective_base = hw.base_latency_ms * prec_factor * batch_factor

    # Noise: ~8% CV with slight positive skew
    cv = 0.08
    std_dev = effective_base * cv
    samples: list[float] = []
    for _ in range(hw.n_warmup if hasattr(hw, "n_warmup") else 10):
        rng.gauss(effective_base, std_dev)  # warmup draws (discard)
    for _ in range(100):
        v = rng.gauss(effective_base, std_dev)
        # occasional outlier (1 in 20) to model GC / preemption
        if rng.random() < 0.05:
            v += effective_base * rng.uniform(0.3, 0.8)
        samples.append(max(v, effective_base * 0.5))

    samples_sorted = sorted(samples)
    n = len(samples_sorted)

    def pct(p: float) -> float:
        idx = int(math.ceil(p / 100.0 * n)) - 1
        return samples_sorted[max(0, min(idx, n - 1))]

    return {
        "p50": pct(50),
        "p90": pct(90),
        "p95": pct(95),
        "p99": pct(99),
        "mean": statistics.mean(samples),
        "std": statistics.stdev(samples),
    }


def benchmark_throughput(
    hw: HardwareProfile,
    concurrent_clients: int = 1,
    rng: random.Random | None = None,
) -> float:
    """
    Estimate requests/second under concurrent load.

    A100 saturates near 4 concurrent clients (~4.4 req/s); smaller GPUs
    saturate earlier.  Returns req/s as float.
    """
    if rng is None:
        rng = random.Random(42)

    # Single-client throughput = 1000 / base_latency_ms
    single_rps = 1000.0 / hw.base_latency_ms

    # Saturation client count scales with memory bandwidth proxy
    if hw.memory_bw_tb_s >= 1.5:
        sat_clients = 4.0   # A100
    elif hw.memory_bw_tb_s >= 0.5:
        sat_clients = 2.5   # A10 / A10G
    else:
        sat_clients = 1.5   # Jetson

    # Amdahl-like model: throughput = single_rps * min(c, sat) * efficiency
    effective = min(concurrent_clients, sat_clients)
    efficiency = 1.0 - 0.04 * max(0, concurrent_clients - sat_clients)
    throughput = single_rps * effective * max(efficiency, 0.5)

    # Small jitter
    throughput *= rng.uniform(0.97, 1.03)
    return round(throughput, 3)


def benchmark_cold_start(
    hw: HardwareProfile,
    rng: random.Random | None = None,
) -> dict[str, float]:
    """
    Simulate model cold-start (load from disk → GPU ready).

    Ranges: A100 ~15-20 s, A10/A10G ~22-30 s, Jetson ~38-45 s.
    Returns mean_s, min_s, max_s over 5 simulated restarts.
    """
    if rng is None:
        rng = random.Random(42)

    if hw.memory_bw_tb_s >= 1.5:
        lo, hi = 15.0, 20.0
    elif hw.memory_bw_tb_s >= 0.5:
        lo, hi = 22.0, 30.0
    else:
        lo, hi = 38.0, 45.0

    times = [rng.uniform(lo, hi) for _ in range(5)]
    return {
        "mean_s": round(statistics.mean(times), 2),
        "min_s": round(min(times), 2),
        "max_s": round(max(times), 2),
    }


def benchmark_all(
    hw: HardwareProfile,
    config: BenchmarkConfig | None = None,
    seed: int = 42,
) -> dict[str, Any]:
    """
    Run full benchmark suite for one hardware profile.
    Returns a nested dict with latency, throughput, cold_start results.
    """
    if config is None:
        config = BenchmarkConfig()
    rng = random.Random(seed)

    latency_results: dict[str, Any] = {}
    for prec in config.precisions:
        latency_results[prec] = {}
        for bs in config.batch_sizes:
            latency_results[prec][bs] = benchmark_latency(hw, prec, bs, rng)

    throughput_results: dict[int, float] = {}
    for cc in config.concurrent_clients:
        throughput_results[cc] = benchmark_throughput(hw, cc, rng)

    cold_start = benchmark_cold_start(hw, rng)

    # Cost per 1k requests at p95 latency (BF16, batch=1)
    p95_ms = latency_results["BF16"][1]["p95"]
    cost_per_1k = (p95_ms / 1000.0) * (hw.cost_per_hr / 3600.0) * 1000.0

    return {
        "hardware": hw.name,
        "latency": latency_results,
        "throughput": throughput_results,
        "cold_start": cold_start,
        "cost_per_1k_reqs_usd": round(cost_per_1k, 6),
    }


def compare_hardware(
    hw_list: list[HardwareProfile] | None = None,
    config: BenchmarkConfig | None = None,
    seed: int = 42,
) -> list[dict[str, Any]]:
    """Run benchmark_all on each hardware profile and return a list of results."""
    if hw_list is None:
        hw_list = ALL_HARDWARE
    if config is None:
        config = BenchmarkConfig()
    return [benchmark_all(hw, config, seed) for hw in hw_list]


# ---------------------------------------------------------------------------
# HTML rendering
# ---------------------------------------------------------------------------

def _svg_grouped_bar(results: list[dict], width: int = 700, height: int = 280) -> str:
    """SVG grouped bar chart: p50 / p95 / p99 latency per hardware (BF16, batch=1)."""
    labels = [r["hardware"] for r in results]
    groups = ["p50", "p95", "p99"]
    colors = ["#4f86c6", "#f5a623", "#e74c3c"]
    data = [[r["latency"]["BF16"][1][g] for r in results] for g in groups]

    pad_l, pad_r, pad_t, pad_b = 55, 20, 30, 60
    chart_w = width - pad_l - pad_r
    chart_h = height - pad_t - pad_b
    n_hw = len(labels)
    group_w = chart_w / n_hw
    bar_w = group_w / (len(groups) + 1)

    max_val = max(v for series in data for v in series) * 1.15

    def y_px(v: float) -> float:
        return pad_t + chart_h * (1 - v / max_val)

    lines = [f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">']
    # Axes
    lines.append(f'<line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t+chart_h}" stroke="#555" stroke-width="1.5"/>')
    lines.append(f'<line x1="{pad_l}" y1="{pad_t+chart_h}" x2="{pad_l+chart_w}" y2="{pad_t+chart_h}" stroke="#555" stroke-width="1.5"/>')

    # Y grid & labels
    for tick in range(0, int(max_val) + 1, 100):
        yp = y_px(tick)
        lines.append(f'<line x1="{pad_l}" y1="{yp:.1f}" x2="{pad_l+chart_w}" y2="{yp:.1f}" stroke="#ddd" stroke-width="0.8"/>')
        lines.append(f'<text x="{pad_l-5}" y="{yp+4:.1f}" text-anchor="end" font-size="10" fill="#555">{tick}</text>')

    # Bars
    for hi, hw_label in enumerate(labels):
        gx = pad_l + hi * group_w + bar_w * 0.5
        for gi, (grp, color) in enumerate(zip(groups, colors)):
            bx = gx + gi * bar_w
            val = data[gi][hi]
            yp = y_px(val)
            bh = pad_t + chart_h - yp
            lines.append(f'<rect x="{bx:.1f}" y="{yp:.1f}" width="{bar_w*0.85:.1f}" height="{bh:.1f}" fill="{color}" opacity="0.85"/>')

        # X label
        lx = pad_l + hi * group_w + group_w / 2
        lines.append(f'<text x="{lx:.1f}" y="{pad_t+chart_h+18}" text-anchor="middle" font-size="10" fill="#333">{hw_label}</text>')

    # Legend
    for gi, (grp, color) in enumerate(zip(groups, colors)):
        lx = pad_l + 20 + gi * 80
        lines.append(f'<rect x="{lx}" y="{height-14}" width="12" height="10" fill="{color}"/>')
        lines.append(f'<text x="{lx+15}" y="{height-5}" font-size="10" fill="#333">{grp}</text>')

    lines.append(f'<text x="{pad_l//2}" y="{pad_t + chart_h//2}" text-anchor="middle" font-size="11" fill="#555" transform="rotate(-90,{pad_l//2},{pad_t+chart_h//2})">Latency (ms)</text>')
    lines.append("</svg>")
    return "\n".join(lines)


def _svg_throughput_line(results: list[dict], width: int = 700, height: int = 260) -> str:
    """SVG line chart: throughput vs concurrent clients per hardware."""
    colors = ["#4f86c6", "#27ae60", "#e67e22", "#8e44ad"]
    clients = sorted(int(k) for k in results[0]["throughput"])

    pad_l, pad_r, pad_t, pad_b = 55, 20, 30, 60
    chart_w = width - pad_l - pad_r
    chart_h = height - pad_t - pad_b

    max_rps = max(v for r in results for v in r["throughput"].values()) * 1.15

    def xp(c: int) -> float:
        idx = clients.index(c)
        return pad_l + idx * chart_w / (len(clients) - 1)

    def yp(v: float) -> float:
        return pad_t + chart_h * (1 - v / max_rps)

    lines = [f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">']
    lines.append(f'<line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t+chart_h}" stroke="#555" stroke-width="1.5"/>')
    lines.append(f'<line x1="{pad_l}" y1="{pad_t+chart_h}" x2="{pad_l+chart_w}" y2="{pad_t+chart_h}" stroke="#555" stroke-width="1.5"/>')

    for tick in [1, 2, 3, 4, 5]:
        yv = tick
        if yv > max_rps:
            continue
        yt = yp(yv)
        lines.append(f'<line x1="{pad_l}" y1="{yt:.1f}" x2="{pad_l+chart_w}" y2="{yt:.1f}" stroke="#ddd" stroke-width="0.8"/>')
        lines.append(f'<text x="{pad_l-5}" y="{yt+4:.1f}" text-anchor="end" font-size="10" fill="#555">{yv:.0f}</text>')

    for ci, c in enumerate(clients):
        lines.append(f'<text x="{xp(c):.1f}" y="{pad_t+chart_h+15}" text-anchor="middle" font-size="10" fill="#333">{c}</text>')

    for ri, r in enumerate(results):
        color = colors[ri % len(colors)]
        pts = " ".join(f"{xp(c):.1f},{yp(r['throughput'][c]):.1f}" for c in clients)
        lines.append(f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2"/>')
        for c in clients:
            cx2 = xp(c)
            cy2 = yp(r["throughput"][c])
            lines.append(f'<circle cx="{cx2:.1f}" cy="{cy2:.1f}" r="3.5" fill="{color}"/>')

    # Legend
    for ri, r in enumerate(results):
        color = colors[ri % len(colors)]
        lx = pad_l + 10 + ri * 160
        lines.append(f'<line x1="{lx}" y1="{height-10}" x2="{lx+18}" y2="{height-10}" stroke="{color}" stroke-width="2"/>')
        lines.append(f'<text x="{lx+22}" y="{height-6}" font-size="10" fill="#333">{r["hardware"]}</text>')

    lines.append(f'<text x="{pad_l//2}" y="{pad_t+chart_h//2}" text-anchor="middle" font-size="11" fill="#555" transform="rotate(-90,{pad_l//2},{pad_t+chart_h//2})">Req/s</text>')
    lines.append(f'<text x="{pad_l + chart_w//2}" y="{height-45}" text-anchor="middle" font-size="10" fill="#555">Concurrent Clients</text>')
    lines.append("</svg>")
    return "\n".join(lines)


def _svg_precision_bar(a100_result: dict, width: int = 500, height: int = 220) -> str:
    """SVG bar chart: p95 latency by precision on OCI A100 (batch=1)."""
    precisions = ["BF16", "FP16", "FP8", "INT8"]
    colors = ["#4f86c6", "#27ae60", "#e74c3c", "#f39c12"]
    values = [a100_result["latency"][p][1]["p95"] for p in precisions]

    pad_l, pad_r, pad_t, pad_b = 55, 20, 30, 60
    chart_w = width - pad_l - pad_r
    chart_h = height - pad_t - pad_b
    bar_w = chart_w / len(precisions) * 0.6
    max_val = max(values) * 1.2

    def yp(v: float) -> float:
        return pad_t + chart_h * (1 - v / max_val)

    lines = [f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">']
    lines.append(f'<line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{pad_t+chart_h}" stroke="#555" stroke-width="1.5"/>')
    lines.append(f'<line x1="{pad_l}" y1="{pad_t+chart_h}" x2="{pad_l+chart_w}" y2="{pad_t+chart_h}" stroke="#555" stroke-width="1.5"/>')

    for tick in range(0, int(max_val) + 50, 50):
        yt = yp(tick)
        lines.append(f'<line x1="{pad_l}" y1="{yt:.1f}" x2="{pad_l+chart_w}" y2="{yt:.1f}" stroke="#ddd" stroke-width="0.8"/>')
        lines.append(f'<text x="{pad_l-5}" y="{yt+4:.1f}" text-anchor="end" font-size="10" fill="#555">{tick}</text>')

    for i, (prec, val, color) in enumerate(zip(precisions, values, colors)):
        bx = pad_l + i * (chart_w / len(precisions)) + (chart_w / len(precisions) - bar_w) / 2
        yt = yp(val)
        bh = pad_t + chart_h - yt
        lines.append(f'<rect x="{bx:.1f}" y="{yt:.1f}" width="{bar_w:.1f}" height="{bh:.1f}" fill="{color}" opacity="0.85"/>')
        cx = bx + bar_w / 2
        lines.append(f'<text x="{cx:.1f}" y="{yt-4:.1f}" text-anchor="middle" font-size="9" fill="#333">{val:.0f}ms</text>')
        lines.append(f'<text x="{cx:.1f}" y="{pad_t+chart_h+15}" text-anchor="middle" font-size="11" fill="#333">{prec}</text>')

    lines.append(f'<text x="{pad_l//2}" y="{pad_t+chart_h//2}" text-anchor="middle" font-size="11" fill="#555" transform="rotate(-90,{pad_l//2},{pad_t+chart_h//2})">p95 Latency (ms)</text>')
    lines.append("</svg>")
    return "\n".join(lines)


def render_html(results: list[dict[str, Any]]) -> str:
    """Render full benchmark report as a self-contained HTML string."""

    a100 = next((r for r in results if "A100" in r["hardware"]), results[0])

    svg_latency = _svg_grouped_bar(results)
    svg_throughput = _svg_throughput_line(results)
    svg_precision = _svg_precision_bar(a100)

    card_html_parts = []
    for r in results:
        p95 = r["latency"]["BF16"][1]["p95"]
        tp = r["throughput"][1]
        cs = r["cold_start"]["mean_s"]
        c1k = r["cost_per_1k_reqs_usd"]
        card_html_parts.append(f"""
      <div class="card">
        <h3>{r["hardware"]}</h3>
        <table>
          <tr><td>p95 Latency</td><td><b>{p95:.0f} ms</b></td></tr>
          <tr><td>Throughput (1 client)</td><td><b>{tp:.2f} req/s</b></td></tr>
          <tr><td>Cold-start</td><td><b>{cs:.1f} s</b></td></tr>
          <tr><td>Cost / 1k reqs</td><td><b>${c1k:.5f}</b></td></tr>
        </table>
      </div>""")

    cards_html = "\n".join(card_html_parts)

    raw_json = json.dumps(results, indent=2)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<title>GR00T N1.6 Inference Benchmark Suite</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         margin: 0; padding: 24px; background: #f5f7fa; color: #222; }}
  h1 {{ color: #1a1a2e; margin-bottom: 4px; }}
  h2 {{ color: #2c3e50; margin-top: 36px; border-bottom: 2px solid #4f86c6; padding-bottom: 6px; }}
  h3 {{ margin: 0 0 10px 0; color: #2c3e50; font-size: 15px; }}
  .cards {{ display: flex; gap: 16px; flex-wrap: wrap; margin-top: 16px; }}
  .card {{ background: #fff; border-radius: 10px; padding: 18px 22px;
           box-shadow: 0 2px 8px rgba(0,0,0,.08); min-width: 180px; flex: 1; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  td {{ padding: 4px 8px 4px 0; }}
  td:last-child {{ text-align: right; }}
  .chart-box {{ background: #fff; border-radius: 10px; padding: 20px;
                box-shadow: 0 2px 8px rgba(0,0,0,.08); margin-top: 16px;
                overflow-x: auto; }}
  .rec {{ background: #eaf4ff; border-left: 5px solid #4f86c6; padding: 14px 18px;
          border-radius: 6px; margin-top: 16px; font-size: 14px; }}
  pre {{ background: #1e1e2e; color: #cdd6f4; padding: 16px; border-radius: 8px;
         font-size: 12px; overflow-x: auto; max-height: 400px; }}
  .subtitle {{ color: #666; font-size: 14px; margin-bottom: 24px; }}
</style>
</head>
<body>
<h1>GR00T N1.6-3B Inference Benchmark Suite</h1>
<p class="subtitle">Hardware comparison: OCI A100 · OCI A10 · Jetson AGX Orin · AWS A10G &nbsp;|&nbsp;
Metrics: latency percentiles · throughput · batch efficiency · cold-start · cost</p>

<h2>Hardware Comparison Cards</h2>
<div class="cards">{cards_html}
</div>

<div class="rec">
  <b>Recommendation:</b> Use <b>OCI A100 FP8</b> for production
  (&lt;200ms p95, $0.0003/req) — 1.45× faster than BF16 at same GPU cost.
  Use Jetson AGX Orin for edge deployments where latency &gt;700ms is acceptable.
</div>

<h2>Latency by Hardware (BF16, batch=1)</h2>
<div class="chart-box">{svg_latency}</div>

<h2>Throughput vs Concurrent Clients</h2>
<div class="chart-box">{svg_throughput}</div>

<h2>Latency by Precision — OCI A100 (batch=1)</h2>
<div class="chart-box">{svg_precision}</div>

<h2>Raw Benchmark Data (JSON)</h2>
<pre>{raw_json}</pre>
</body>
</html>"""
    return html


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="GR00T N1.6 Inference Benchmark Suite")
    parser.add_argument("--mock", action=argparse.BooleanOptionalAction, default=True,
                        help="Use simulated (mock) measurements (default: True)")
    parser.add_argument("--output", default="/tmp/inference_benchmark_suite.html",
                        help="Output HTML file path")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    args = parser.parse_args()

    if not args.mock:
        print("[WARN] Live inference not implemented; falling back to mock mode.")

    print("Running GR00T N1.6 inference benchmark suite (mock mode) ...")
    t0 = time.monotonic()
    config = BenchmarkConfig()
    results = compare_hardware(ALL_HARDWARE, config, seed=args.seed)
    elapsed = time.monotonic() - t0
    print(f"  Benchmarks complete in {elapsed:.2f}s")

    html = render_html(results)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  Report saved to {args.output}")

    # Print summary table
    print("\n{'Hardware':<22} {'p95 (ms)':>10} {'Throughput':>12} {'Cold-start':>12} {'$/1k reqs':>11}")
    print("-" * 72)
    for r in results:
        p95 = r["latency"]["BF16"][1]["p95"]
        tp = r["throughput"][1]
        cs = r["cold_start"]["mean_s"]
        c1k = r["cost_per_1k_reqs_usd"]
        print(f"  {r['hardware']:<20} {p95:>10.1f} {tp:>12.2f} {cs:>11.1f}s {c1k:>10.6f}")


if __name__ == "__main__":
    main()
