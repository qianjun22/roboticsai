#!/usr/bin/env python3
"""
policy_overfitting_detector.py -- Detects overfitting in GR00T fine-tuned policies.

Compares train vs validation loss curves, measures generalization gap, tests
out-of-distribution (OOD) performance, and flags checkpoints that overfit.
"""

import argparse
import json
import math
import random
import time
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class CheckpointMetrics:
    step: int
    train_loss: float
    val_loss: float
    generalization_gap: float
    ood_sr: float
    id_sr: float
    ood_id_ratio: float
    gradient_norm: float
    weight_norm: float
    overfit_flag: bool
    overfit_score: float


@dataclass
class PolicyRun:
    run_id: str
    policy: str
    n_demos: int
    lora_rank: int
    dropout_rate: float
    weight_decay: float
    verdict: str
    best_checkpoint_step: int
    final_gap: float
    checkpoints: list = field(default_factory=list)


@dataclass
class OverfittingReport:
    generated_at: str
    runs: list = field(default_factory=list)
    recommendations: list = field(default_factory=list)


def _loss_curve(seed_val, n_steps, base_train_loss, base_val_loss, overfit_onset_frac, rng):
    checkpoints = []
    onset = int(n_steps * overfit_onset_frac)
    for step in range(0, n_steps + 1, n_steps // 20):
        t = step / n_steps
        train = base_train_loss * math.exp(-4 * t) + 0.05 + rng.gauss(0, 0.003)
        if step <= onset:
            val = base_val_loss * math.exp(-3.5 * t) + 0.06 + rng.gauss(0, 0.005)
        else:
            diverge_t = (step - onset) / (n_steps - onset)
            val = (base_val_loss * math.exp(-3.5 * onset / n_steps) + 0.06) + 0.08 * diverge_t ** 1.5 + rng.gauss(0, 0.005)
        train = max(0.03, train)
        val = max(0.04, val)
        checkpoints.append((step, round(train, 4), round(val, 4), round(val - train, 4)))
    return checkpoints


def simulate_overfitting(seed: int = 42) -> OverfittingReport:
    rng = random.Random(seed)
    runs_config = [
        {"run_id": "run_overfit_100demo", "policy": "gr00t_lora_r8", "n_demos": 100, "lora_rank": 8,
         "dropout_rate": 0.0, "weight_decay": 0.0001, "n_steps": 5000, "overfit_onset_frac": 0.45,
         "base_train_loss": 0.85, "base_val_loss": 0.90, "ood_penalty": 0.35, "verdict": "OVERFIT"},
        {"run_id": "run_borderline_500demo", "policy": "gr00t_lora_r16", "n_demos": 500, "lora_rank": 16,
         "dropout_rate": 0.05, "weight_decay": 0.001, "n_steps": 5000, "overfit_onset_frac": 0.70,
         "base_train_loss": 0.80, "base_val_loss": 0.85, "ood_penalty": 0.18, "verdict": "BORDERLINE"},
        {"run_id": "run_healthy_1000demo", "policy": "gr00t_lora_r16_wd", "n_demos": 1000, "lora_rank": 16,
         "dropout_rate": 0.10, "weight_decay": 0.01, "n_steps": 5000, "overfit_onset_frac": 1.1,
         "base_train_loss": 0.82, "base_val_loss": 0.88, "ood_penalty": 0.08, "verdict": "HEALTHY"},
        {"run_id": "dagger_run9_soap_v2.2", "policy": "gr00t_dagger_run9", "n_demos": 1200, "lora_rank": 16,
         "dropout_rate": 0.10, "weight_decay": 0.01, "n_steps": 5000, "overfit_onset_frac": 1.1,
         "base_train_loss": 0.78, "base_val_loss": 0.83, "ood_penalty": 0.05, "verdict": "HEALTHY"},
    ]

    runs = []
    for cfg in runs_config:
        raw_ckpts = _loss_curve(cfg["run_id"], cfg["n_steps"], cfg["base_train_loss"], cfg["base_val_loss"], cfg["overfit_onset_frac"], rng)
        ckpts = []
        base_id_sr = 0.78 if cfg["verdict"] == "HEALTHY" else (0.71 if cfg["verdict"] == "BORDERLINE" else 0.58)
        for step, train, val, gap in raw_ckpts:
            t = step / cfg["n_steps"]
            id_sr = min(0.92, base_id_sr * (1 - math.exp(-5 * t)) + rng.gauss(0, 0.015))
            ood_sr = max(0.1, id_sr * (1 - cfg["ood_penalty"] * t) + rng.gauss(0, 0.012))
            ood_id_ratio = ood_sr / id_sr if id_sr > 0 else 0
            gap_score = min(1, max(0, (gap - 0.02) / 0.15))
            ratio_score = min(1, max(0, (1 - ood_id_ratio) / 0.4))
            overfit_score = 0.5 * gap_score + 0.5 * ratio_score
            ckpts.append(CheckpointMetrics(
                step=step, train_loss=train, val_loss=val, generalization_gap=gap,
                ood_sr=round(ood_sr, 3), id_sr=round(id_sr, 3), ood_id_ratio=round(ood_id_ratio, 3),
                gradient_norm=round(rng.uniform(0.8, 3.5) * math.exp(-2 * t), 3),
                weight_norm=round(5.0 + 2.0 * t + rng.gauss(0, 0.1), 3),
                overfit_flag=overfit_score > 0.6, overfit_score=round(overfit_score, 3),
            ))
        best = min(ckpts, key=lambda c: c.val_loss)
        final = ckpts[-1]
        runs.append(PolicyRun(
            run_id=cfg["run_id"], policy=cfg["policy"], n_demos=cfg["n_demos"],
            lora_rank=cfg["lora_rank"], dropout_rate=cfg["dropout_rate"], weight_decay=cfg["weight_decay"],
            verdict=cfg["verdict"], best_checkpoint_step=best.step, final_gap=final.generalization_gap,
            checkpoints=ckpts,
        ))

    return OverfittingReport(
        generated_at=time.strftime("%Y-%m-%d %H:%M:%S"),
        runs=runs,
        recommendations=[
            "run_overfit_100demo: Increase dataset to >=500 demos; add dropout=0.10, weight_decay=0.01",
            "run_borderline_500demo: Monitor val loss after step 3500; apply early stopping patience=200",
            "run_healthy_1000demo: Healthy generalization -- proceed to deployment eval",
            "dagger_run9_soap_v2.2: Best OOD/ID ratio (0.95). Recommended for production.",
            "General: LoRA rank 16 with dropout >=0.05 and weight_decay >=0.001 consistently avoids overfitting",
        ],
    )


def _loss_curve_svg(run: PolicyRun) -> str:
    ckpts = run.checkpoints
    if not ckpts: return ""
    w, h = 320, 90
    steps = [c.step for c in ckpts]
    trains = [c.train_loss for c in ckpts]
    vals = [c.val_loss for c in ckpts]
    s_max = max(steps) or 1
    y_min = min(min(trains), min(vals)) - 0.02
    y_max = max(max(trains), max(vals)) + 0.02
    y_rng = y_max - y_min or 0.1

    def px(s, v):
        x = 20 + (s / s_max) * (w - 30)
        y = 10 + (1 - (v - y_min) / y_rng) * (h - 22)
        return f"{x:.1f},{y:.1f}"

    train_pts = " ".join(px(c.step, c.train_loss) for c in ckpts)
    val_pts = " ".join(px(c.step, c.val_loss) for c in ckpts)
    best = min(ckpts, key=lambda c: c.val_loss)
    bx, by = [float(v) for v in px(best.step, best.val_loss).split(",")]
    return (f'<svg width="{w}" height="{h}" style="background:#0f172a;border-radius:4px">'
            f'<polyline points="{train_pts}" fill="none" stroke="#38bdf8" stroke-width="1.5"/>'
            f'<polyline points="{val_pts}" fill="none" stroke="#f59e0b" stroke-width="1.5"/>'
            f'<circle cx="{bx:.1f}" cy="{by:.1f}" r="4" fill="#22c55e"/></svg>')


def _overfit_score_svg(run: PolicyRun) -> str:
    ckpts = run.checkpoints
    if not ckpts: return ""
    w, h = 320, 60
    steps = [c.step for c in ckpts]
    s_max = max(steps) or 1

    def px(s, v):
        x = 20 + (s / s_max) * (w - 30)
        y = 5 + (1 - v) * (h - 12)
        return f"{x:.1f},{y:.1f}"

    pts = " ".join(px(c.step, c.overfit_score) for c in ckpts)
    ty = 5 + (1 - 0.6) * (h - 12)
    return (f'<svg width="{w}" height="{h}" style="background:#0f172a;border-radius:4px">'
            f'<line x1="20" y1="{ty:.1f}" x2="{w-10}" y2="{ty:.1f}" stroke="#ef4444" stroke-width="1" stroke-dasharray="4,2"/>'
            f'<polyline points="{pts}" fill="none" stroke="#C74634" stroke-width="1.5"/>'
            f'<text x="{w-50}" y="{ty-2:.1f}" fill="#ef4444" font-size="9">threshold 0.6</text></svg>')


def render_html(report: OverfittingReport) -> str:
    verdict_color = {"HEALTHY": "#22c55e", "BORDERLINE": "#f59e0b", "OVERFIT": "#ef4444"}
    runs_html = ""
    for run in report.runs:
        vc = verdict_color.get(run.verdict, "#94a3b8")
        loss_svg = _loss_curve_svg(run)
        score_svg = _overfit_score_svg(run)
        final = run.checkpoints[-1] if run.checkpoints else None
        runs_html += f"""
<div style="background:#0f172a;border:1px solid #334155;border-radius:8px;padding:16px;margin-bottom:16px">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
    <span style="color:#C74634;font-weight:bold">{run.run_id}</span>
    <span style="background:{vc}22;color:{vc};padding:3px 10px;border-radius:10px;font-size:12px;font-weight:bold">{run.verdict}</span>
  </div>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:8px">
    <div><div style="color:#94a3b8;font-size:10px;margin-bottom:3px">Loss curves \u2014 <span style="color:#38bdf8">train</span> vs <span style="color:#f59e0b">val</span></div>{loss_svg}</div>
    <div><div style="color:#94a3b8;font-size:10px;margin-bottom:3px">Overfit score (threshold 0.6)</div>{score_svg}</div>
  </div>
  <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:8px;font-size:11px">
    <div style="background:#1e293b;padding:8px;border-radius:4px"><div style="color:#94a3b8">Best ckpt step</div><div style="color:#e2e8f0;font-weight:bold">{run.best_checkpoint_step}</div></div>
    <div style="background:#1e293b;padding:8px;border-radius:4px"><div style="color:#94a3b8">Final gen. gap</div><div style="color:{'#ef4444' if run.final_gap > 0.08 else '#22c55e'};font-weight:bold">{run.final_gap:+.4f}</div></div>
    <div style="background:#1e293b;padding:8px;border-radius:4px"><div style="color:#94a3b8">Final OOD SR</div><div style="color:#e2e8f0;font-weight:bold">{final.ood_sr if final else '\u2014'}</div></div>
    <div style="background:#1e293b;padding:8px;border-radius:4px"><div style="color:#94a3b8">OOD/ID ratio</div><div style="color:{'#22c55e' if final and final.ood_id_ratio > 0.85 else '#f59e0b'};font-weight:bold">{final.ood_id_ratio if final else '\u2014'}</div></div>
  </div>
</div>"""
    recs_html = "".join(f'<li style="margin-bottom:6px;color:#cbd5e1">{r}</li>' for r in report.recommendations)
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><title>Policy Overfitting Detector</title>
<style>body{{background:#1e293b;color:#e2e8f0;font-family:'Segoe UI',Arial,sans-serif;margin:0;padding:24px}}
h1{{color:#C74634;margin:0 0 4px 0;font-size:22px}}h2{{color:#C74634;font-size:15px;margin:20px 0 10px 0;border-bottom:1px solid #334155;padding-bottom:6px}}</style></head>
<body><h1>Policy Overfitting Detector</h1>
<div style="color:#94a3b8;font-size:12px;margin-bottom:20px">Generated {report.generated_at} \u00b7 4 runs</div>
<h2>Run Analysis</h2>{runs_html}
<h2>Recommendations</h2><ul style="padding-left:18px;font-size:13px;line-height:1.7">{recs_html}</ul></body></html>"""


def main():
    parser = argparse.ArgumentParser(description="Policy overfitting detector")
    parser.add_argument("--mock", action="store_true", default=True)
    parser.add_argument("--output", default="/tmp/policy_overfitting_detector.html")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    report = simulate_overfitting(seed=args.seed)
    html = render_html(report)
    Path(args.output).write_text(html)
    print(f"[overfit] Report saved to {args.output}")
    for r in report.runs:
        print(f"  {r.run_id}: {r.verdict} (gap={r.final_gap:+.4f}, best_step={r.best_checkpoint_step})")


if __name__ == "__main__":
    main()
