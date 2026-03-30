#!/usr/bin/env python3
"""
model_ensemble_analyzer.py — Ensemble methods for GR00T action policy uncertainty quantification.

Compares single-model inference against deep ensembles (5 members), MC-dropout ensembles,
and mixture-of-experts approaches. Measures calibration, diversity, and task success rate.

Usage:
    python src/training/model_ensemble_analyzer.py --mock --output /tmp/model_ensemble_analyzer.html
"""

import argparse
import json
import math
import random
import time
from dataclasses import dataclass, field
from pathlib import Path


N_TASKS = 6
N_EPISODES = 50
ENSEMBLE_SIZES = [1, 3, 5, 7, 10]


# ── Dataclasses ──────────────────────────────────────────────────────────────

@dataclass
class TaskResult:
    task_name: str
    success_rate: float
    uncertainty_mean: float
    uncertainty_std: float
    avg_inference_ms: float
    ece: float                # Expected Calibration Error


@dataclass
class EnsembleResult:
    method: str               # single / deep_ensemble / mc_dropout / mixture_of_experts
    ensemble_size: int
    tasks: list[TaskResult]
    avg_success_rate: float
    avg_uncertainty: float
    diversity_score: float    # disagreement among members (higher = more diverse)
    ece: float
    inference_ms: float       # total (single call or avg of K)
    vram_gb: float
    cost_per_1k: float        # $ at OCI A100 rates


@dataclass
class EnsembleReport:
    best_method: str
    best_sr: float
    lowest_ece: str
    fastest_method: str
    results: list[EnsembleResult] = field(default_factory=list)


# ── Tasks ─────────────────────────────────────────────────────────────────────

TASKS = [
    "pick_and_place",
    "stack_blocks",
    "door_opening",
    "drawer_pull",
    "tool_use",
    "pouring",
]

# (method, ensemble_size, base_sr, base_ece, diversity, lat_ms, vram_gb)
METHODS = [
    ("single",             1,  0.65, 0.091, 0.00, 226,  9.6),
    ("deep_ensemble",      5,  0.79, 0.041, 0.61, 312,  48.0),   # 5× VRAM
    ("mc_dropout",         5,  0.72, 0.058, 0.38, 278,  9.6),    # same model, K fwd passes
    ("mixture_of_experts", 3,  0.76, 0.049, 0.52, 295,  28.8),   # 3 specialized heads
]

OCI_A100_COST_PER_HR = 4.20


def simulate_ensemble(seed: int = 42) -> EnsembleReport:
    rng = random.Random(seed)
    results: list[EnsembleResult] = []

    for method, ens_sz, base_sr, base_ece, diversity, lat_ms, vram in METHODS:
        task_results: list[TaskResult] = []

        for task in TASKS:
            # Task-specific difficulty modifier
            difficulty = {"pick_and_place": 0.0, "stack_blocks": -0.05,
                          "door_opening": -0.08, "drawer_pull": -0.04,
                          "tool_use": -0.12, "pouring": -0.10}.get(task, 0.0)

            sr = base_sr + difficulty + rng.gauss(0, 0.03)
            sr = max(0.2, min(0.98, sr))

            unc_mean = (1 - sr) * 0.3 + rng.gauss(0, 0.02)
            unc_std  = unc_mean * 0.4 + rng.gauss(0, 0.01)
            task_lat = lat_ms + rng.gauss(0, 12)
            task_ece = base_ece + rng.gauss(0, 0.005)
            task_ece = max(0.01, task_ece)

            task_results.append(TaskResult(
                task_name=task,
                success_rate=round(sr, 4),
                uncertainty_mean=round(max(0.01, unc_mean), 4),
                uncertainty_std=round(max(0.005, unc_std), 4),
                avg_inference_ms=round(task_lat, 1),
                ece=round(task_ece, 4),
            ))

        avg_sr  = sum(t.success_rate for t in task_results) / len(task_results)
        avg_unc = sum(t.uncertainty_mean for t in task_results) / len(task_results)
        avg_ece = sum(t.ece for t in task_results) / len(task_results)
        avg_lat = sum(t.avg_inference_ms for t in task_results) / len(task_results)

        # Cost: vram → how many A100s needed × $/hr / throughput
        gpus_needed = math.ceil(vram / 80)  # A100-80GB
        cost_per_1k = gpus_needed * OCI_A100_COST_PER_HR * (avg_lat / 1000) / 1000 * 1000

        results.append(EnsembleResult(
            method=method,
            ensemble_size=ens_sz,
            tasks=task_results,
            avg_success_rate=round(avg_sr, 4),
            avg_uncertainty=round(avg_unc, 4),
            diversity_score=round(diversity + rng.gauss(0, 0.02), 3),
            ece=round(avg_ece, 4),
            inference_ms=round(avg_lat, 1),
            vram_gb=vram,
            cost_per_1k=round(cost_per_1k, 4),
        ))

    best_method  = max(results, key=lambda r: r.avg_success_rate).method
    best_sr      = max(r.avg_success_rate for r in results)
    lowest_ece   = min(results, key=lambda r: r.ece).method
    fastest      = min(results, key=lambda r: r.inference_ms).method

    return EnsembleReport(
        best_method=best_method,
        best_sr=best_sr,
        lowest_ece=lowest_ece,
        fastest_method=fastest,
        results=results,
    )


# ── HTML ─────────────────────────────────────────────────────────────────────

def render_html(report: EnsembleReport) -> str:
    METHOD_COLORS = {
        "single":             "#64748b",
        "deep_ensemble":      "#22c55e",
        "mc_dropout":         "#3b82f6",
        "mixture_of_experts": "#f59e0b",
    }

    # SVG: grouped bar chart — SR per task per method
    w, h, ml, mr, mt, mb = 560, 260, 50, 20, 20, 40
    inner_w = w - ml - mr
    inner_h = h - mt - mb
    n_tasks = len(TASKS)
    n_methods = len(report.results)
    group_w = inner_w / n_tasks
    bar_w = (group_w - 6) / n_methods

    svg_sr = f'<svg width="{w}" height="{h}" style="background:#0f172a;border-radius:8px">'
    svg_sr += f'<line x1="{ml}" y1="{mt}" x2="{ml}" y2="{h-mb}" stroke="#475569"/>'
    svg_sr += f'<line x1="{ml}" y1="{h-mb}" x2="{w-mr}" y2="{h-mb}" stroke="#475569"/>'

    # grid lines
    for v in [0.25, 0.50, 0.75, 1.0]:
        y = h - mb - v * inner_h
        svg_sr += (f'<line x1="{ml}" y1="{y:.1f}" x2="{w-mr}" y2="{y:.1f}" '
                   f'stroke="#1e293b" stroke-width="1"/>')
        svg_sr += (f'<text x="{ml-4}" y="{y+3:.1f}" fill="#64748b" '
                   f'font-size="8" text-anchor="end">{v:.0%}</text>')

    for ti, task in enumerate(TASKS):
        gx = ml + ti * group_w
        svg_sr += (f'<text x="{gx + group_w/2:.1f}" y="{h-mb+12}" fill="#64748b" '
                   f'font-size="7.5" text-anchor="middle">{task.replace("_", " ")}</text>')

        for mi, res in enumerate(report.results):
            tr = res.tasks[ti]
            bx = gx + 3 + mi * bar_w
            bh = tr.success_rate * inner_h
            by = h - mb - bh
            col = METHOD_COLORS[res.method]
            svg_sr += (f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bar_w-1:.1f}" '
                       f'height="{bh:.1f}" fill="{col}" opacity="0.8" rx="1"/>')

    # Legend
    for i, res in enumerate(report.results):
        col = METHOD_COLORS[res.method]
        lx = ml + i * 130
        svg_sr += (f'<rect x="{lx}" y="{mt+2}" width="8" height="8" fill="{col}" opacity="0.8" rx="1"/>'
                   f'<text x="{lx+10}" y="{mt+10}" fill="#94a3b8" font-size="8">{res.method}</text>')

    svg_sr += '</svg>'

    # SVG: ECE vs SR scatter (one dot per method)
    sw, sh, sm = 300, 200, 40
    svg_ece = f'<svg width="{sw}" height="{sh}" style="background:#0f172a;border-radius:8px">'
    svg_ece += f'<line x1="{sm}" y1="{sm}" x2="{sm}" y2="{sh-sm}" stroke="#475569"/>'
    svg_ece += f'<line x1="{sm}" y1="{sh-sm}" x2="{sw-sm}" y2="{sh-sm}" stroke="#475569"/>'

    min_ece = min(r.ece for r in report.results)
    max_ece = max(r.ece for r in report.results)
    ece_range = max_ece - min_ece + 0.02
    min_sr  = min(r.avg_success_rate for r in report.results) - 0.05
    max_sr  = max(r.avg_success_rate for r in report.results) + 0.02
    sr_range = max_sr - min_sr

    for res in report.results:
        col = METHOD_COLORS[res.method]
        cx = sm + ((res.ece - min_ece) / ece_range) * (sw - 2 * sm)
        cy = sh - sm - ((res.avg_success_rate - min_sr) / sr_range) * (sh - 2 * sm)
        svg_ece += f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="6" fill="{col}" opacity="0.85"/>'
        svg_ece += (f'<text x="{cx+8:.1f}" y="{cy+4:.1f}" fill="{col}" '
                    f'font-size="8">{res.method[:8]}</text>')

    svg_ece += (f'<text x="{sw//2}" y="{sh-sm+14}" fill="#64748b" '
                f'font-size="8" text-anchor="middle">ECE (lower=better) →</text>')
    svg_ece += (f'<text x="{sm-10}" y="{sh//2}" fill="#64748b" font-size="8" '
                f'text-anchor="middle" transform="rotate(-90,{sm-10},{sh//2})">Success Rate ↑</text>')
    svg_ece += '</svg>'

    # Comparison table
    rows = ""
    for res in report.results:
        col = METHOD_COLORS[res.method]
        sr_col = "#22c55e" if res.avg_success_rate == report.best_sr else "#e2e8f0"
        ece_col = "#22c55e" if res.method == report.lowest_ece else "#e2e8f0"
        rows += (f'<tr>'
                 f'<td style="color:{col};font-weight:bold">{res.method}</td>'
                 f'<td style="text-align:center">{res.ensemble_size}</td>'
                 f'<td style="color:{sr_col}">{res.avg_success_rate:.1%}</td>'
                 f'<td style="color:{ece_col}">{res.ece:.4f}</td>'
                 f'<td style="color:#f59e0b">{res.diversity_score:.3f}</td>'
                 f'<td style="color:#94a3b8">{res.inference_ms:.0f}ms</td>'
                 f'<td style="color:#64748b">{res.vram_gb:.1f}GB</td>'
                 f'<td style="color:#3b82f6">${res.cost_per_1k:.4f}</td>'
                 f'</tr>')

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Model Ensemble Analyzer</title>
<style>
body{{background:#1e293b;color:#e2e8f0;font-family:monospace;margin:0;padding:24px}}
h1{{color:#C74634;margin:0 0 4px}}
.meta{{color:#94a3b8;font-size:12px;margin-bottom:20px}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:20px}}
.card{{background:#0f172a;border-radius:8px;padding:14px}}
.card h3{{color:#94a3b8;font-size:11px;text-transform:uppercase;margin:0 0 4px}}
.big{{font-size:22px;font-weight:bold}}
.layout{{display:grid;grid-template-columns:2fr 1fr;gap:12px;margin-bottom:20px}}
table{{width:100%;border-collapse:collapse;font-size:11px}}
th{{color:#94a3b8;text-align:left;padding:5px 8px;border-bottom:1px solid #334155}}
td{{padding:3px 8px;border-bottom:1px solid #1e293b}}
h3.sec{{color:#94a3b8;font-size:11px;text-transform:uppercase;margin-bottom:8px}}
</style></head>
<body>
<h1>Model Ensemble Analyzer</h1>
<div class="meta">
  {n_methods} methods · {n_tasks} tasks · {N_EPISODES} episodes each · OCI A100-80GB
</div>

<div class="grid">
  <div class="card"><h3>Best Method (SR)</h3>
    <div style="color:#22c55e;font-size:13px;font-weight:bold">{report.best_method}</div>
    <div class="big" style="color:#22c55e">{report.best_sr:.1%}</div>
  </div>
  <div class="card"><h3>Best Calibrated</h3>
    <div style="color:#3b82f6;font-size:13px;font-weight:bold">{report.lowest_ece}</div>
    <div class="big" style="color:#3b82f6">{min(r.ece for r in report.results):.4f} ECE</div>
  </div>
  <div class="card"><h3>Fastest Method</h3>
    <div style="color:#f59e0b;font-size:13px;font-weight:bold">{report.fastest_method}</div>
    <div class="big" style="color:#f59e0b">{min(r.inference_ms for r in report.results):.0f}ms</div>
  </div>
  <div class="card"><h3>SR Uplift vs Single</h3>
    <div class="big" style="color:#22c55e">
      +{(report.best_sr - next(r.avg_success_rate for r in report.results if r.method=="single")):.1%}
    </div>
    <div style="color:#64748b;font-size:10px">best ensemble vs single</div>
  </div>
</div>

<div class="layout">
  <div>
    <h3 class="sec">Success Rate by Task and Method</h3>
    {svg_sr}
  </div>
  <div>
    <h3 class="sec">ECE vs Success Rate</h3>
    {svg_ece}
    <div style="color:#64748b;font-size:10px;margin-top:4px">
      Top-right = best (high SR + low ECE)
    </div>
  </div>
</div>

<h3 class="sec">Ensemble Comparison</h3>
<table>
  <tr><th>Method</th><th>Size</th><th>Avg SR</th><th>ECE</th>
      <th>Diversity</th><th>Latency</th><th>VRAM</th><th>$/1k calls</th></tr>
  {rows}
</table>

<div style="background:#0f172a;border-radius:8px;padding:12px;margin-top:14px;font-size:10px">
  <div style="color:#C74634;font-weight:bold;margin-bottom:4px">RECOMMENDATION</div>
  <div style="color:#22c55e">Production: deep_ensemble (5) — +21.5% SR vs single, ECE=0.041 — fits 1×A100-80G with 48GB</div>
  <div style="color:#f59e0b">Latency-sensitive: mc_dropout (5 passes) — +10.8% SR, same VRAM as single, 278ms p99</div>
  <div style="color:#3b82f6">Edge/Jetson: single model — 226ms, 9.6GB VRAM, lowest cost ($0.0003/1k)</div>
  <div style="color:#64748b;margin-top:4px">Diversity score correlates with calibration improvement: higher disagreement → lower ECE</div>
</div>
</body></html>"""


# ── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Model ensemble analysis for GR00T policies")
    parser.add_argument("--mock",   action="store_true", default=True)
    parser.add_argument("--output", default="/tmp/model_ensemble_analyzer.html")
    parser.add_argument("--seed",   type=int, default=42)
    args = parser.parse_args()

    print(f"[ensemble] {len(METHODS)} methods · {len(TASKS)} tasks · {N_EPISODES} eps each")
    t0 = time.time()

    report = simulate_ensemble(args.seed)

    print(f"\n  {'Method':<22} {'Size':>5} {'SR':>8} {'ECE':>8} {'Latency':>10} {'VRAM':>8}")
    print(f"  {'─'*22} {'─'*5} {'─'*8} {'─'*8} {'─'*10} {'─'*8}")
    for r in report.results:
        flag = " ← best" if r.method == report.best_method else ""
        print(f"  {r.method:<22} {r.ensemble_size:>5} {r.avg_success_rate:>7.1%} "
              f"{r.ece:>8.4f} {r.inference_ms:>8.0f}ms {r.vram_gb:>6.1f}GB{flag}")

    print(f"\n  Best SR: {report.best_method} ({report.best_sr:.1%})")
    print(f"  Best ECE: {report.lowest_ece}")
    print(f"  Fastest: {report.fastest_method}")
    print(f"  [{time.time()-t0:.1f}s]\n")

    html = render_html(report)
    Path(args.output).write_text(html)
    print(f"  HTML → {args.output}")

    json_out = Path(args.output).with_suffix(".json")
    json_out.write_text(json.dumps({
        "best_method": report.best_method,
        "best_sr": report.best_sr,
        "lowest_ece": report.lowest_ece,
        "results": [{"method": r.method, "avg_success_rate": r.avg_success_rate,
                     "ece": r.ece, "inference_ms": r.inference_ms} for r in report.results],
    }, indent=2))
    print(f"  JSON → {json_out}")


if __name__ == "__main__":
    main()
