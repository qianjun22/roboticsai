#!/usr/bin/env python3
"""
loss_landscape_analyzer.py — Loss landscape analysis for GR00T fine-tuned checkpoints.

Visualizes the loss surface around a checkpoint by perturbing weights along random
directions (filter normalization method). Identifies sharp vs flat minima — flat minima
generalize better; sharp minima indicate overfitting or poor hyperparameters.

Usage:
    python src/training/loss_landscape_analyzer.py --mock --output /tmp/loss_landscape_analyzer.html
"""

import argparse
import json
import math
import random
import time
from dataclasses import dataclass, field
from pathlib import Path


# ── Config ────────────────────────────────────────────────────────────────────

CHECKPOINTS_TO_ANALYZE = [
    # (label, description, sharpness, flatness_score, mae_val, mae_train)
    ("run9_step5000",  "DAgger run9 step-5000 (current prod)", 0.08, 0.87, 0.016, 0.011),
    ("run9_step2500",  "DAgger run9 step-2500 (mid-training)", 0.22, 0.64, 0.024, 0.018),
    ("run9_step1000",  "DAgger run9 step-1000 (early)",        0.45, 0.42, 0.041, 0.028),
    ("bc_baseline",    "BC baseline (no DAgger)",              0.18, 0.71, 0.031, 0.022),
]

PERTURBATION_STEPS = 21   # -10 to +10 steps along direction


@dataclass
class LandscapeSlice:
    """1D cross-section of loss surface along a random direction."""
    checkpoint: str
    direction: int          # which random direction (1 or 2)
    alphas: list[float]     # perturbation magnitudes
    losses: list[float]     # loss values along this direction
    min_loss: float
    max_loss: float
    loss_range: float       # max - min (sharpness measure)
    curvature: float        # second derivative at center (positive = bowl = good)


@dataclass
class CheckpointLandscape:
    checkpoint: str
    description: str
    flatness_score: float       # 0-1 (1 = perfectly flat = best generalization)
    sharpness: float            # max loss range across directions
    mae_val: float
    mae_train: float
    overfit_gap: float          # mae_val - mae_train
    basin_width: float          # α range where loss < min_loss + 0.1
    slices: list[LandscapeSlice] = field(default_factory=list)
    recommendation: str = ""


@dataclass
class LandscapeReport:
    n_checkpoints: int
    best_checkpoint: str
    flattest_checkpoint: str
    results: list[CheckpointLandscape] = field(default_factory=list)


# ── Simulation ─────────────────────────────────────────────────────────────────

def _loss_curve(alpha: float, center_loss: float, sharpness: float,
                rng: random.Random) -> float:
    """Simulate loss surface: U-shaped with sharpness controlling steepness."""
    # Flat minimum: loss grows slowly away from center
    # Sharp minimum: loss grows quickly
    base = center_loss + sharpness * (alpha ** 2) * 8
    # Add asymmetry and noise
    asym = rng.gauss(0, sharpness * 0.05) * alpha
    noise = rng.gauss(0, center_loss * 0.02)
    return max(0.001, base + asym + noise)


def simulate_landscape(seed: int = 42) -> LandscapeReport:
    rng = random.Random(seed)
    results = []

    alphas = [i * 0.1 - 1.0 for i in range(PERTURBATION_STEPS)]  # -1.0 to +1.0

    for label, desc, sharpness, flatness, mae_val, mae_train in CHECKPOINTS_TO_ANALYZE:
        center_loss = mae_val + rng.gauss(0, 0.002)
        slices = []

        for direction in range(1, 3):  # 2 random filter-normalized directions
            losses = [_loss_curve(a, center_loss, sharpness, rng) for a in alphas]
            min_l = min(losses)
            max_l = max(losses)

            # Curvature at center (second derivative via finite diff)
            mid = PERTURBATION_STEPS // 2
            h = alphas[1] - alphas[0]
            if mid > 0 and mid < len(losses) - 1:
                curv = (losses[mid+1] - 2*losses[mid] + losses[mid-1]) / (h ** 2)
            else:
                curv = 0.0

            # Basin width: how wide the low-loss region is
            basin = sum(1 for l in losses if l < min_l + 0.1) * h

            slices.append(LandscapeSlice(
                checkpoint=label, direction=direction,
                alphas=alphas, losses=[round(l, 6) for l in losses],
                min_loss=round(min_l, 6), max_loss=round(max_l, 6),
                loss_range=round(max_l - min_l, 6),
                curvature=round(curv, 4),
            ))

        avg_range = sum(s.loss_range for s in slices) / len(slices)
        avg_basin = sum(1 for l in slices[0].losses if l < slices[0].min_loss + 0.1) * h

        if flatness >= 0.80:
            rec = "Flat minimum — excellent generalization; deploy with confidence"
        elif flatness >= 0.60:
            rec = "Moderately flat — good for production; consider more training"
        elif flatness >= 0.40:
            rec = "Somewhat sharp — validate on held-out data before deploy"
        else:
            rec = "Sharp minimum — likely overfit; reduce LR or add regularization"

        results.append(CheckpointLandscape(
            checkpoint=label, description=desc,
            flatness_score=flatness, sharpness=avg_range,
            mae_val=mae_val, mae_train=mae_train,
            overfit_gap=round(mae_val - mae_train, 4),
            basin_width=round(avg_basin, 3),
            slices=slices,
            recommendation=rec,
        ))

    best = min(results, key=lambda r: r.mae_val).checkpoint
    flattest = max(results, key=lambda r: r.flatness_score).checkpoint

    return LandscapeReport(
        n_checkpoints=len(results),
        best_checkpoint=best,
        flattest_checkpoint=flattest,
        results=results,
    )


# ── HTML ───────────────────────────────────────────────────────────────────────

def render_html(report: LandscapeReport) -> str:
    COLORS = ["#3b82f6", "#22c55e", "#f59e0b", "#C74634"]

    # SVG: loss curves for all checkpoints (direction 1)
    w, h = 560, 200
    alphas = [i * 0.1 - 1.0 for i in range(PERTURBATION_STEPS)]
    all_losses = [l for r in report.results for l in r.slices[0].losses]
    min_loss = min(all_losses) * 0.95
    max_loss = max(all_losses) * 1.05
    loss_span = max_loss - min_loss

    x_scale = (w - 60) / (len(alphas) - 1)
    y_scale = (h - 30) / loss_span

    svg_curves = f'<svg width="{w}" height="{h}" style="background:#0f172a;border-radius:8px">'
    svg_curves += f'<line x1="30" y1="{h-20}" x2="{w}" y2="{h-20}" stroke="#334155" stroke-width="1"/>'
    # Zero line (center)
    cx = 30 + (PERTURBATION_STEPS // 2) * x_scale
    svg_curves += (f'<line x1="{cx:.1f}" y1="10" x2="{cx:.1f}" y2="{h-20}" '
                   f'stroke="#475569" stroke-width="1" stroke-dasharray="3,2"/>')

    for i, r in enumerate(report.results):
        losses = r.slices[0].losses
        pts = " ".join(f"{30+j*x_scale:.1f},{h-20-(l-min_loss)*y_scale:.1f}"
                       for j, l in enumerate(losses))
        col = COLORS[i % len(COLORS)]
        width = "2.5" if r.flatness_score >= 0.80 else "1.5"
        svg_curves += (f'<polyline points="{pts}" fill="none" stroke="{col}" '
                       f'stroke-width="{width}" opacity="0.9"/>')

    # Legend
    for i, r in enumerate(report.results):
        col = COLORS[i % len(COLORS)]
        svg_curves += (f'<rect x="{30+i*140}" y="12" width="12" height="3" fill="{col}"/>'
                       f'<text x="{44+i*140}" y="17" fill="#94a3b8" font-size="8.5">'
                       f'{r.checkpoint}</text>')

    svg_curves += '</svg>'

    # SVG: flatness score bar chart
    bw, bh = 380, 130
    max_flat = 1.0
    svg_flat = f'<svg width="{bw}" height="{bh}" style="background:#0f172a;border-radius:8px">'
    bar_h = (bh - 20) / len(report.results) - 5

    for i, r in enumerate(report.results):
        y = 10 + i * (bar_h + 5)
        bar_width = r.flatness_score / max_flat * (bw - 160)
        col = "#22c55e" if r.flatness_score >= 0.80 else "#f59e0b" if r.flatness_score >= 0.60 else "#ef4444"
        svg_flat += (f'<rect x="130" y="{y:.1f}" width="{bar_width:.1f}" height="{bar_h:.1f}" '
                     f'fill="{col}" opacity="0.85" rx="2"/>')
        svg_flat += (f'<text x="128" y="{y+bar_h*0.72:.1f}" fill="#94a3b8" font-size="8.5" '
                     f'text-anchor="end">{r.checkpoint}</text>')
        svg_flat += (f'<text x="{133+bar_width:.1f}" y="{y+bar_h*0.72:.1f}" fill="{col}" '
                     f'font-size="8.5">{r.flatness_score:.2f}</text>')

    svg_flat += '</svg>'

    # Checkpoint cards
    cards = ""
    for i, r in enumerate(report.results):
        col = COLORS[i % len(COLORS)]
        flat_col = "#22c55e" if r.flatness_score >= 0.80 else "#f59e0b" if r.flatness_score >= 0.60 else "#ef4444"
        cards += (f'<div style="background:#0f172a;border-radius:8px;padding:12px;border-left:3px solid {col}">'
                  f'<div style="color:{col};font-size:11px;font-weight:bold">{r.checkpoint}</div>'
                  f'<div style="color:#94a3b8;font-size:10px;margin:2px 0">{r.description}</div>'
                  f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:4px;margin-top:6px;font-size:10px">'
                  f'<div style="color:#64748b">Flatness: <span style="color:{flat_col}">{r.flatness_score:.2f}</span></div>'
                  f'<div style="color:#64748b">MAE val: <span style="color:#e2e8f0">{r.mae_val:.4f}</span></div>'
                  f'<div style="color:#64748b">Basin: <span style="color:#94a3b8">{r.basin_width:.2f}</span></div>'
                  f'<div style="color:#64748b">Overfit: <span style="color:{"#ef4444" if r.overfit_gap > 0.01 else "#22c55e"}">{r.overfit_gap:.4f}</span></div>'
                  f'</div>'
                  f'<div style="color:#64748b;font-size:9px;margin-top:4px">→ {r.recommendation}</div>'
                  f'</div>')

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Loss Landscape Analyzer</title>
<style>
body{{background:#1e293b;color:#e2e8f0;font-family:monospace;margin:0;padding:24px}}
h1{{color:#C74634;margin:0 0 4px}}
.meta{{color:#94a3b8;font-size:12px;margin-bottom:20px}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:20px}}
.card{{background:#0f172a;border-radius:8px;padding:14px}}
.card h3{{color:#94a3b8;font-size:11px;text-transform:uppercase;margin:0 0 4px}}
.big{{font-size:24px;font-weight:bold}}
.charts{{display:grid;grid-template-columns:3fr 2fr;gap:12px;margin-bottom:20px}}
h3.sec{{color:#94a3b8;font-size:11px;text-transform:uppercase;margin-bottom:8px}}
</style></head>
<body>
<h1>Loss Landscape Analyzer</h1>
<div class="meta">
  {report.n_checkpoints} checkpoints · filter-normalized 1D cross-sections · {PERTURBATION_STEPS} perturbation steps
</div>

<div class="grid">
  <div class="card"><h3>Best MAE</h3>
    <div class="big" style="color:#22c55e">{report.best_checkpoint}</div>
  </div>
  <div class="card"><h3>Flattest</h3>
    <div class="big" style="color:#3b82f6">{report.flattest_checkpoint}</div>
    <div style="color:#64748b;font-size:10px">best generalization</div>
  </div>
  <div class="card"><h3>Method</h3>
    <div style="color:#94a3b8;font-size:12px">Filter norm.<br>direction perturbation</div>
  </div>
  <div class="card"><h3>Directions</h3>
    <div class="big" style="color:#64748b">2</div>
    <div style="color:#64748b;font-size:10px">random per checkpoint</div>
  </div>
</div>

<div class="charts">
  <div>
    <h3 class="sec">Loss Curves (Direction 1) — Flat = Better Generalization</h3>
    {svg_curves}
    <div style="color:#64748b;font-size:10px;margin-top:4px">
      Thicker line = flatness ≥ 0.80. Dashed vertical = checkpoint center (α=0).
    </div>
  </div>
  <div>
    <h3 class="sec">Flatness Score (0–1)</h3>
    {svg_flat}
    <div style="color:#64748b;font-size:10px;margin-top:4px">
      Green ≥0.80 · Yellow ≥0.60 · Red &lt;0.60
    </div>
  </div>
</div>

<h3 class="sec">Checkpoint Analysis</h3>
<div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
  {cards}
</div>

<div style="color:#64748b;font-size:11px;margin-top:16px">
  Flat minima (high flatness score) generalize better — wider basin means small perturbations don't degrade performance.<br>
  run9_step5000 is both flattest and lowest MAE — ideal production checkpoint.<br>
  To improve flatness: use SAM optimizer, increase batch size, or add weight noise during training.
</div>
</body></html>"""


# ── CLI ────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Loss landscape analyzer for GR00T checkpoints")
    parser.add_argument("--mock",   action="store_true", default=True)
    parser.add_argument("--output", default="/tmp/loss_landscape_analyzer.html")
    parser.add_argument("--seed",   type=int, default=42)
    args = parser.parse_args()

    print(f"[loss-landscape] Analyzing {len(CHECKPOINTS_TO_ANALYZE)} checkpoints")
    t0 = time.time()

    report = simulate_landscape(args.seed)

    print(f"\n  {'Checkpoint':<22} {'Flatness':>9} {'Sharpness':>10} {'MAE val':>9}  Recommendation")
    print(f"  {'─'*22} {'─'*9} {'─'*10} {'─'*9}  {'─'*35}")
    for r in report.results:
        print(f"  {r.checkpoint:<22} {r.flatness_score:>9.3f} {r.sharpness:>10.5f} "
              f"{r.mae_val:>9.4f}  {r.recommendation[:35]}")

    print(f"\n  Best: {report.best_checkpoint}  Flattest: {report.flattest_checkpoint}")
    print(f"  [{time.time()-t0:.1f}s]\n")

    html = render_html(report)
    Path(args.output).write_text(html)
    print(f"  HTML → {args.output}")

    json_out = Path(args.output).with_suffix(".json")
    json_out.write_text(json.dumps({
        "best_checkpoint": report.best_checkpoint,
        "flattest_checkpoint": report.flattest_checkpoint,
        "checkpoints": [{
            "name": r.checkpoint, "flatness_score": r.flatness_score,
            "sharpness": r.sharpness, "mae_val": r.mae_val,
            "basin_width": r.basin_width,
        } for r in report.results],
    }, indent=2))
    print(f"  JSON → {json_out}")


if __name__ == "__main__":
    main()
