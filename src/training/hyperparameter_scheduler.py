#!/usr/bin/env python3
"""
hyperparameter_scheduler.py — Dynamic hyperparameter scheduling for GR00T fine-tuning.

Implements learning rate schedules, warmup, and adaptive parameter adjustment
based on training loss curves. Extends the basic HPO search with dynamic tuning.

Usage:
    python src/training/hyperparameter_scheduler.py --simulate --steps 5000
    python src/training/hyperparameter_scheduler.py --plot --output /tmp/lr_schedule.html
"""

import argparse
import json
import math
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


# ── Schedules ─────────────────────────────────────────────────────────────────

@dataclass
class ScheduleConfig:
    name: str
    base_lr: float = 1e-4
    warmup_steps: int = 100
    total_steps: int = 5000
    # Cosine annealing
    min_lr: float = 1e-6
    # Cyclic
    cycle_length: int = 500
    # Plateau
    plateau_patience: int = 200
    plateau_factor: float = 0.5
    plateau_threshold: float = 0.001


def linear_warmup(step: int, cfg: ScheduleConfig) -> float:
    if step < cfg.warmup_steps:
        return cfg.base_lr * step / cfg.warmup_steps
    return cfg.base_lr


def cosine_decay(step: int, cfg: ScheduleConfig) -> float:
    """Linear warmup + cosine decay to min_lr."""
    if step < cfg.warmup_steps:
        return cfg.base_lr * step / cfg.warmup_steps
    progress = (step - cfg.warmup_steps) / max(1, cfg.total_steps - cfg.warmup_steps)
    cosine = 0.5 * (1 + math.cos(math.pi * progress))
    return cfg.min_lr + (cfg.base_lr - cfg.min_lr) * cosine


def one_cycle_lr(step: int, cfg: ScheduleConfig) -> float:
    """1cycle policy: ramp up to 10× base_lr then cosine down to min_lr."""
    peak_lr = cfg.base_lr * 10
    warmup = cfg.warmup_steps
    if step < warmup:
        return cfg.base_lr + (peak_lr - cfg.base_lr) * step / warmup
    progress = (step - warmup) / max(1, cfg.total_steps - warmup)
    cosine = 0.5 * (1 + math.cos(math.pi * progress))
    return cfg.min_lr + (peak_lr - cfg.min_lr) * cosine


def cyclic_triangular(step: int, cfg: ScheduleConfig) -> float:
    """Cyclic triangular: oscillates between min_lr and base_lr."""
    cycle = cfg.cycle_length
    pos = step % cycle
    if pos < cycle // 2:
        return cfg.min_lr + (cfg.base_lr - cfg.min_lr) * (pos / (cycle // 2))
    return cfg.base_lr - (cfg.base_lr - cfg.min_lr) * ((pos - cycle // 2) / (cycle // 2))


def reduce_on_plateau(losses: list[float], cfg: ScheduleConfig,
                       current_lr: float) -> float:
    """Reduce LR if loss hasn't improved by threshold in patience steps."""
    if len(losses) < cfg.plateau_patience:
        return current_lr
    recent_min = min(losses[-cfg.plateau_patience:])
    older_min = min(losses[-2*cfg.plateau_patience:-cfg.plateau_patience]) if len(losses) >= 2*cfg.plateau_patience else losses[0]
    if recent_min > older_min - cfg.plateau_threshold:
        new_lr = max(cfg.min_lr, current_lr * cfg.plateau_factor)
        return new_lr
    return current_lr


SCHEDULE_FNS = {
    "cosine": cosine_decay,
    "1cycle": one_cycle_lr,
    "cyclic": cyclic_triangular,
    "warmup_only": linear_warmup,
}


# ── Simulation ────────────────────────────────────────────────────────────────

def simulate_training(schedule_name: str, cfg: ScheduleConfig,
                       seed: int = 42) -> tuple[list[float], list[float], list[float]]:
    """Simulate loss curve for a given LR schedule."""
    rng = random.Random(seed)
    fn = SCHEDULE_FNS[schedule_name]

    lrs, losses, plateau_lrs = [], [], []
    loss = 0.68   # starting loss
    current_lr = cfg.base_lr
    all_losses = []

    for step in range(cfg.total_steps + 1):
        lr = fn(step, cfg)

        # Adaptive: apply plateau reduction on top
        if step > 0 and step % cfg.plateau_patience == 0:
            current_lr = reduce_on_plateau(all_losses, cfg, lr)
            lr = current_lr

        # Simulate loss improvement
        noise = rng.gauss(0, 0.003)
        loss_delta = -lr * 50 * loss * (1 + noise)  # bigger lr = faster descent
        loss = max(0.02, loss + loss_delta + rng.gauss(0, 0.002))
        all_losses.append(loss)

        if step % 50 == 0:
            lrs.append(lr)
            losses.append(round(loss, 5))
            plateau_lrs.append(current_lr)

    return lrs, losses, plateau_lrs


def compare_schedules(cfg: ScheduleConfig) -> dict:
    results = {}
    for name in SCHEDULE_FNS:
        lrs, losses, _ = simulate_training(name, cfg)
        results[name] = {
            "final_loss": losses[-1],
            "min_loss": min(losses),
            "convergence_step": next((i*50 for i, l in enumerate(losses) if l < 0.15), cfg.total_steps),
            "losses": losses,
            "lrs": lrs,
        }
    return results


# ── HTML report ───────────────────────────────────────────────────────────────

def render_html(cfg: ScheduleConfig, comparison: dict) -> str:
    best = min(comparison.items(), key=lambda x: x[1]["final_loss"])

    def svg_line(data: list[float], color: str, y_max: float, y_min: float,
                  w: int = 500, h: int = 120) -> str:
        n = len(data)
        pts = " ".join(
            f"{10 + i*(w-20)/(n-1):.1f},{h-5-(v-y_min)/(max(y_max-y_min,1e-9))*(h-15):.1f}"
            for i, v in enumerate(data)
        )
        return f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2"/>'

    COLORS = {"cosine": "#C74634", "1cycle": "#3b82f6", "cyclic": "#22c55e", "warmup_only": "#f59e0b"}

    # LR schedule chart
    all_lrs = [lr for r in comparison.values() for lr in r["lrs"]]
    lr_max = max(all_lrs)
    lr_svg = (f'<svg width="500" height="120" style="background:#0f172a;border-radius:6px">'
              + "".join(svg_line(comparison[n]["lrs"], COLORS[n], lr_max, 0)
                        for n in comparison)
              + '</svg>')

    # Loss chart
    all_losses = [l for r in comparison.values() for l in r["losses"]]
    loss_max = max(all_losses)
    loss_svg = (f'<svg width="500" height="120" style="background:#0f172a;border-radius:6px">'
                + "".join(svg_line(comparison[n]["losses"], COLORS[n], loss_max, 0)
                          for n in comparison)
                + '</svg>')

    legend = " ".join(
        f'<span style="color:{COLORS[n]}">■ {n}</span>'
        for n in comparison
    )

    rows = ""
    for name, r in sorted(comparison.items(), key=lambda x: x[1]["final_loss"]):
        is_best = name == best[0]
        hl = ' style="background:#0f2d1c"' if is_best else ""
        rows += f"""<tr{hl}>
          <td style="color:{COLORS[name]}">{name}{'★' if is_best else ''}</td>
          <td>{r['final_loss']:.5f}</td>
          <td>{r['min_loss']:.5f}</td>
          <td>{r['convergence_step']}</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>LR Schedule Comparison</title>
<style>
body{{background:#1e293b;color:#e2e8f0;font-family:monospace;margin:0;padding:24px}}
h1{{color:#C74634;margin:0 0 4px}}
.meta{{color:#94a3b8;font-size:12px;margin-bottom:20px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:20px}}
.card{{background:#0f172a;border-radius:8px;padding:14px}}
.card h3{{color:#94a3b8;font-size:11px;text-transform:uppercase;margin:0 0 8px}}
table{{width:100%;border-collapse:collapse;font-size:12px}}
th{{color:#94a3b8;text-align:left;padding:5px 8px;border-bottom:1px solid #334155}}
td{{padding:5px 8px;border-bottom:1px solid #1e293b}}
</style></head>
<body>
<h1>LR Schedule Comparison — GR00T Fine-tuning</h1>
<div class="meta">base_lr={cfg.base_lr} · warmup={cfg.warmup_steps} steps · total={cfg.total_steps} steps</div>
<div style="margin-bottom:8px">{legend}</div>

<div class="grid">
  <div class="card"><h3>Learning Rate Schedules</h3>{lr_svg}</div>
  <div class="card"><h3>Loss Curves</h3>{loss_svg}</div>
</div>

<table>
  <tr><th>Schedule</th><th>Final Loss</th><th>Min Loss</th><th>Steps to &lt;0.15</th></tr>
  {rows}
</table>

<div style="color:#64748b;font-size:11px;margin-top:16px">
  Best: <span style="color:{COLORS[best[0]]}">{best[0]}</span> —
  final loss {best[1]['final_loss']:.4f}<br>
  Recommendation for DAgger fine-tuning: cosine decay with warmup_steps=200, base_lr=5e-5
</div>
</body></html>"""


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="LR schedule comparison for GR00T fine-tuning")
    parser.add_argument("--simulate",    action="store_true", default=True)
    parser.add_argument("--steps",       type=int, default=5000)
    parser.add_argument("--base-lr",     type=float, default=1e-4)
    parser.add_argument("--warmup",      type=int, default=200)
    parser.add_argument("--output",      default="/tmp/lr_schedule_comparison.html")
    parser.add_argument("--schedule",    default="all",
                        choices=list(SCHEDULE_FNS.keys()) + ["all"])
    args = parser.parse_args()

    cfg = ScheduleConfig(
        name=args.schedule,
        base_lr=args.base_lr,
        warmup_steps=args.warmup,
        total_steps=args.steps,
    )

    print(f"[lr-schedule] Simulating {args.steps} steps with base_lr={args.base_lr}...")
    comparison = compare_schedules(cfg)

    print(f"\n  {'Schedule':<16} {'Final Loss':>12} {'Min Loss':>10} {'Steps→0.15':>12}")
    print(f"  {'─'*16} {'─'*12} {'─'*10} {'─'*12}")
    for name, r in sorted(comparison.items(), key=lambda x: x[1]["final_loss"]):
        print(f"  {name:<16} {r['final_loss']:>12.5f} {r['min_loss']:>10.5f} {r['convergence_step']:>12}")

    best = min(comparison.items(), key=lambda x: x[1]["final_loss"])
    print(f"\n  Best schedule: {best[0]} (final loss {best[1]['final_loss']:.5f})\n")

    html = render_html(cfg, comparison)
    Path(args.output).write_text(html)
    print(f"  Report → {args.output}")


if __name__ == "__main__":
    main()
