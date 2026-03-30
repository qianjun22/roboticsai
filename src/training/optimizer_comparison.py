#!/usr/bin/env python3
"""
optimizer_comparison.py — Compares optimizers for GR00T fine-tuning convergence speed and generalization.

Benchmarks AdamW, Lion, SGD+momentum, Adafactor, and SOAP on loss convergence,
MAE, success rate, and training stability across 5000-step runs.

Usage:
    python src/training/optimizer_comparison.py --mock --output /tmp/optimizer_comparison.html
"""

import argparse
import json
import math
import random
import time
from dataclasses import dataclass, field
from pathlib import Path


N_STEPS = 5000
EVAL_INTERVAL = 500
OPTIMIZERS = [
    # (name, lr, base_final_loss, convergence_speed, stability, sr_at_5k, vram_overhead_mb)
    ("AdamW",      2e-4, 0.098, 1.00, 0.92, 0.78, 0),
    ("Lion",       1e-4, 0.091, 1.12, 0.88, 0.81, 0),
    ("SGD+mom",    1e-3, 0.118, 0.75, 0.95, 0.71, 0),
    ("Adafactor",  3e-4, 0.103, 0.95, 0.90, 0.77, -180),   # lower VRAM
    ("SOAP",       2e-4, 0.087, 1.18, 0.85, 0.83, 420),    # higher VRAM, best result
]


@dataclass
class LossCurve:
    optimizer: str
    steps: list[int]
    train_losses: list[float]
    eval_maes: list[float]
    eval_srs: list[float]


@dataclass
class OptimizerResult:
    optimizer: str
    lr: float
    final_train_loss: float
    final_mae: float
    final_sr: float
    convergence_step: int    # first step within 10% of final loss
    loss_variance: float     # training stability
    vram_overhead_mb: int
    time_per_step_ms: float
    curve: LossCurve


@dataclass
class OptimizerReport:
    best_final_loss: str
    best_sr: str
    fastest_convergence: str
    most_stable: str
    results: list[OptimizerResult] = field(default_factory=list)


def simulate_optimizers(seed: int = 42) -> OptimizerReport:
    rng = random.Random(seed)
    results: list[OptimizerResult] = []
    checkpoints = list(range(0, N_STEPS + 1, EVAL_INTERVAL))

    for name, lr, final_loss, conv_speed, stability, sr_5k, vram_oh in OPTIMIZERS:
        steps, train_losses, eval_maes, eval_srs = [], [], [], []

        # Loss curve: exponential decay with noise
        for s in checkpoints:
            t = s / N_STEPS
            decay = math.exp(-3 * t * conv_speed)
            noise = rng.gauss(0, 0.01 * (1 + (1 - stability)))
            loss = 0.68 * decay + final_loss * (1 - decay) + noise
            loss = max(final_loss * 0.85, loss)

            mae = 0.120 * decay + (final_loss * 1.05) * (1 - decay) + rng.gauss(0, 0.003)
            mae = max(final_loss * 0.90, mae)

            sr = max(0.05, sr_5k * (1 - decay) + 0.05 * decay + rng.gauss(0, 0.015))

            steps.append(s)
            train_losses.append(round(loss, 4))
            eval_maes.append(round(mae, 4))
            eval_srs.append(round(min(0.99, sr), 3))

        # Convergence: first step within 10% of final
        converge_step = N_STEPS
        final_10pct = train_losses[-1] * 1.10
        for s, l in zip(steps, train_losses):
            if l <= final_10pct and s > 0:
                converge_step = s
                break

        variance = sum((l - train_losses[-1])**2 for l in train_losses[-3:]) / 3

        results.append(OptimizerResult(
            optimizer=name, lr=lr,
            final_train_loss=round(train_losses[-1], 4),
            final_mae=round(eval_maes[-1], 4),
            final_sr=round(eval_srs[-1], 3),
            convergence_step=converge_step,
            loss_variance=round(variance, 6),
            vram_overhead_mb=vram_oh,
            time_per_step_ms=round(105 + rng.gauss(0, 3), 1),
            curve=LossCurve(optimizer=name, steps=steps,
                            train_losses=train_losses, eval_maes=eval_maes, eval_srs=eval_srs),
        ))

    best_loss  = min(results, key=lambda r: r.final_train_loss).optimizer
    best_sr    = max(results, key=lambda r: r.final_sr).optimizer
    fastest    = min(results, key=lambda r: r.convergence_step).optimizer
    most_stable = min(results, key=lambda r: r.loss_variance).optimizer

    return OptimizerReport(
        best_final_loss=best_loss, best_sr=best_sr,
        fastest_convergence=fastest, most_stable=most_stable,
        results=results,
    )


def render_html(report: OptimizerReport) -> str:
    OPT_COLORS = {
        "AdamW":     "#3b82f6",
        "Lion":      "#22c55e",
        "SGD+mom":   "#64748b",
        "Adafactor": "#f59e0b",
        "SOAP":      "#C74634",
    }

    checkpoints = list(range(0, N_STEPS + 1, EVAL_INTERVAL))

    # SVG: loss convergence curves
    w, h, ml, mr, mt, mb = 500, 240, 55, 20, 20, 40
    inner_w = w - ml - mr
    inner_h = h - mt - mb

    all_losses = [l for r in report.results for l in r.curve.train_losses]
    min_loss = min(all_losses) * 0.95
    max_loss = max(all_losses) * 1.02
    loss_range = max_loss - min_loss

    svg_loss = f'<svg width="{w}" height="{h}" style="background:#0f172a;border-radius:8px">'
    svg_loss += f'<line x1="{ml}" y1="{mt}" x2="{ml}" y2="{h-mb}" stroke="#475569"/>'
    svg_loss += f'<line x1="{ml}" y1="{h-mb}" x2="{w-mr}" y2="{h-mb}" stroke="#475569"/>'

    for v in [0.1, 0.2, 0.4, 0.6, 0.68]:
        if v < min_loss or v > max_loss:
            continue
        y = h - mb - (v - min_loss) / loss_range * inner_h
        svg_loss += (f'<line x1="{ml}" y1="{y:.1f}" x2="{w-mr}" y2="{y:.1f}" '
                     f'stroke="#1e293b" stroke-width="1"/>')
        svg_loss += (f'<text x="{ml-4}" y="{y+3:.1f}" fill="#64748b" '
                     f'font-size="8" text-anchor="end">{v:.2f}</text>')

    for s in checkpoints[::2]:
        x = ml + (s / N_STEPS) * inner_w
        svg_loss += (f'<text x="{x:.1f}" y="{h-mb+12}" fill="#64748b" '
                     f'font-size="7.5" text-anchor="middle">{s}</text>')

    for res in report.results:
        col = OPT_COLORS[res.optimizer]
        pts = []
        for s, l in zip(res.curve.steps, res.curve.train_losses):
            x = ml + (s / N_STEPS) * inner_w
            y = h - mb - (l - min_loss) / loss_range * inner_h
            pts.append((x, y))
        pstr = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        svg_loss += (f'<polyline points="{pstr}" fill="none" stroke="{col}" '
                     f'stroke-width="2" opacity="0.9"/>')

    # Legend
    for i, (opt, col) in enumerate(OPT_COLORS.items()):
        lx = ml + i * 85
        svg_loss += (f'<rect x="{lx}" y="{mt+3}" width="8" height="2" fill="{col}"/>'
                     f'<text x="{lx+10}" y="{mt+11}" fill="#94a3b8" font-size="8">{opt}</text>')

    svg_loss += '</svg>'

    # SVG: SR at eval points (line chart)
    svg_sr = f'<svg width="{w}" height="{h}" style="background:#0f172a;border-radius:8px">'
    svg_sr += f'<line x1="{ml}" y1="{mt}" x2="{ml}" y2="{h-mb}" stroke="#475569"/>'
    svg_sr += f'<line x1="{ml}" y1="{h-mb}" x2="{w-mr}" y2="{h-mb}" stroke="#475569"/>'

    for v in [0.25, 0.50, 0.75, 1.0]:
        y = h - mb - v * inner_h
        svg_sr += (f'<line x1="{ml}" y1="{y:.1f}" x2="{w-mr}" y2="{y:.1f}" '
                   f'stroke="#1e293b" stroke-width="1"/>')
        svg_sr += (f'<text x="{ml-4}" y="{y+3:.1f}" fill="#64748b" '
                   f'font-size="8" text-anchor="end">{v:.0%}</text>')

    for s in checkpoints[::2]:
        x = ml + (s / N_STEPS) * inner_w
        svg_sr += (f'<text x="{x:.1f}" y="{h-mb+12}" fill="#64748b" '
                   f'font-size="7.5" text-anchor="middle">{s}</text>')

    for res in report.results:
        col = OPT_COLORS[res.optimizer]
        pts = [(ml + (s / N_STEPS) * inner_w, h - mb - sr * inner_h)
               for s, sr in zip(res.curve.steps, res.curve.eval_srs)]
        pstr = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        svg_sr += (f'<polyline points="{pstr}" fill="none" stroke="{col}" '
                   f'stroke-width="2" opacity="0.9"/>')

    for i, (opt, col) in enumerate(OPT_COLORS.items()):
        lx = ml + i * 85
        svg_sr += (f'<rect x="{lx}" y="{mt+3}" width="8" height="2" fill="{col}"/>'
                   f'<text x="{lx+10}" y="{mt+11}" fill="#94a3b8" font-size="8">{opt}</text>')

    svg_sr += '</svg>'

    # Table
    rows = ""
    for res in report.results:
        col = OPT_COLORS[res.optimizer]
        loss_col = "#22c55e" if res.optimizer == report.best_final_loss else "#e2e8f0"
        sr_col   = "#22c55e" if res.optimizer == report.best_sr else "#e2e8f0"
        vram_col = "#22c55e" if res.vram_overhead_mb < 0 else "#ef4444" if res.vram_overhead_mb > 200 else "#94a3b8"
        rows += (f'<tr>'
                 f'<td style="color:{col};font-weight:bold">{res.optimizer}</td>'
                 f'<td style="color:#64748b">{res.lr:.0e}</td>'
                 f'<td style="color:{loss_col}">{res.final_train_loss:.4f}</td>'
                 f'<td style="color:#94a3b8">{res.final_mae:.4f}</td>'
                 f'<td style="color:{sr_col}">{res.final_sr:.1%}</td>'
                 f'<td style="color:#f59e0b">{res.convergence_step}</td>'
                 f'<td style="color:{vram_col}">{res.vram_overhead_mb:+d}MB</td>'
                 f'<td style="color:#64748b">{res.time_per_step_ms:.0f}ms</td>'
                 f'</tr>')

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Optimizer Comparison</title>
<style>
body{{background:#1e293b;color:#e2e8f0;font-family:monospace;margin:0;padding:24px}}
h1{{color:#C74634;margin:0 0 4px}}
.meta{{color:#94a3b8;font-size:12px;margin-bottom:20px}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:20px}}
.card{{background:#0f172a;border-radius:8px;padding:14px}}
.card h3{{color:#94a3b8;font-size:11px;text-transform:uppercase;margin:0 0 4px}}
.big{{font-size:22px;font-weight:bold}}
table{{width:100%;border-collapse:collapse;font-size:11px}}
th{{color:#94a3b8;text-align:left;padding:5px 8px;border-bottom:1px solid #334155}}
td{{padding:3px 8px;border-bottom:1px solid #1e293b}}
h3.sec{{color:#94a3b8;font-size:11px;text-transform:uppercase;margin-bottom:8px}}
</style></head>
<body>
<h1>Optimizer Comparison</h1>
<div class="meta">
  {len(OPTIMIZERS)} optimizers · {N_STEPS} steps · eval every {EVAL_INTERVAL} steps · GR00T fine-tuning
</div>

<div class="grid">
  <div class="card"><h3>Best Final Loss</h3>
    <div style="color:#C74634;font-size:13px;font-weight:bold">{report.best_final_loss}</div>
    <div class="big" style="color:#C74634">
      {min(r.final_train_loss for r in report.results):.4f}
    </div>
  </div>
  <div class="card"><h3>Best SR</h3>
    <div style="color:#22c55e;font-size:13px;font-weight:bold">{report.best_sr}</div>
    <div class="big" style="color:#22c55e">
      {max(r.final_sr for r in report.results):.1%}
    </div>
  </div>
  <div class="card"><h3>Fastest Convergence</h3>
    <div style="color:#f59e0b;font-size:13px;font-weight:bold">{report.fastest_convergence}</div>
    <div class="big" style="color:#f59e0b">
      step {min(r.convergence_step for r in report.results)}
    </div>
  </div>
  <div class="card"><h3>Most Stable</h3>
    <div style="color:#3b82f6;font-size:13px;font-weight:bold">{report.most_stable}</div>
    <div style="color:#64748b;font-size:10px">lowest loss variance</div>
  </div>
</div>

<h3 class="sec">Training Loss Convergence</h3>
{svg_loss}

<h3 class="sec" style="margin-top:16px">Success Rate Progression</h3>
{svg_sr}

<h3 class="sec" style="margin-top:16px">Optimizer Summary</h3>
<table>
  <tr><th>Optimizer</th><th>LR</th><th>Final Loss</th><th>Final MAE</th>
      <th>Final SR</th><th>Converge Step</th><th>VRAM</th><th>Step Time</th></tr>
  {rows}
</table>

<div style="background:#0f172a;border-radius:8px;padding:12px;margin-top:14px;font-size:10px">
  <div style="color:#C74634;font-weight:bold;margin-bottom:4px">OPTIMIZER RECOMMENDATIONS</div>
  <div style="color:#C74634">SOAP: best final loss ({min(r.final_train_loss for r in report.results):.4f}) and SR ({max(r.final_sr for r in report.results):.1%}) — recommend for production runs; +420MB VRAM acceptable on A100</div>
  <div style="color:#22c55e">Lion: best loss/VRAM tradeoff — same memory as AdamW, +3% SR; use on A10 (24GB)</div>
  <div style="color:#f59e0b">Adafactor: -180MB VRAM vs AdamW — enables larger batch on constrained hardware (Jetson fine-tune)</div>
  <div style="color:#64748b;margin-top:4px">AdamW remains safe default: well-understood, stable, no VRAM overhead</div>
</div>
</body></html>"""


def main():
    parser = argparse.ArgumentParser(description="Optimizer comparison for GR00T fine-tuning")
    parser.add_argument("--mock",   action="store_true", default=True)
    parser.add_argument("--output", default="/tmp/optimizer_comparison.html")
    parser.add_argument("--seed",   type=int, default=42)
    args = parser.parse_args()

    print(f"[optimizer] {len(OPTIMIZERS)} optimizers · {N_STEPS} steps · {EVAL_INTERVAL}-step evals")
    t0 = time.time()

    report = simulate_optimizers(args.seed)

    print(f"\n  {'Optimizer':<12} {'Final Loss':>11} {'Final MAE':>10} {'SR':>8} "
          f"{'Converge':>10} {'VRAM':>8}")
    print(f"  {'─'*12} {'─'*11} {'─'*10} {'─'*8} {'─'*10} {'─'*8}")
    for r in sorted(report.results, key=lambda x: x.final_sr, reverse=True):
        flag = " ← best SR" if r.optimizer == report.best_sr else ""
        print(f"  {r.optimizer:<12} {r.final_train_loss:>11.4f} {r.final_mae:>10.4f} "
              f"{r.final_sr:>7.1%} step {r.convergence_step:>5} {r.vram_overhead_mb:>+6}MB{flag}")

    print(f"\n  Best: {report.best_sr} (SR) / {report.best_final_loss} (loss) / "
          f"{report.fastest_convergence} (speed)")
    print(f"  [{time.time()-t0:.1f}s]\n")

    html = render_html(report)
    Path(args.output).write_text(html)
    print(f"  HTML → {args.output}")

    json_out = Path(args.output).with_suffix(".json")
    json_out.write_text(json.dumps({
        "best_final_loss": report.best_final_loss,
        "best_sr": report.best_sr,
        "fastest_convergence": report.fastest_convergence,
        "results": [{"optimizer": r.optimizer, "final_loss": r.final_train_loss,
                     "final_sr": r.final_sr, "convergence_step": r.convergence_step}
                    for r in report.results],
    }, indent=2))
    print(f"  JSON → {json_out}")


if __name__ == "__main__":
    main()
