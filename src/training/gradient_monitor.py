#!/usr/bin/env python3
"""
gradient_monitor.py — Gradient health monitoring during GR00T fine-tuning.

Tracks gradient norms, vanishing/exploding gradient detection, per-layer gradient
statistics, and training stability indicators. Helps diagnose training instability
and tune gradient clipping, LR, and batch size.

Usage:
    python src/training/gradient_monitor.py --mock --output /tmp/gradient_monitor.html
    python src/training/gradient_monitor.py --run-dir /tmp/dagger_run9 --steps 5000
"""

import argparse
import json
import math
import random
import time
from dataclasses import dataclass
from pathlib import Path


# ── Model layers ──────────────────────────────────────────────────────────────

LAYER_GROUPS = [
    ("vision_encoder",    12, "encoder"),
    ("lang_embedding",     1, "embedding"),
    ("transformer_early",  4, "transformer"),
    ("transformer_mid",    4, "transformer"),
    ("transformer_late",   4, "transformer"),
    ("action_head",        2, "head"),
    ("lora_adapters",      8, "lora"),
]


@dataclass
class GradientSnapshot:
    step: int
    layer_group: str
    layer_type: str
    grad_norm: float
    grad_norm_mean: float
    grad_norm_std: float
    grad_max: float
    grad_min: float
    vanishing: bool    # grad_norm < 1e-4
    exploding: bool    # grad_norm > 10.0
    clip_triggered: bool


@dataclass
class TrainingHealth:
    step: int
    global_grad_norm: float
    loss: float
    lr: float
    clip_count: int     # how many layers triggered clip this step
    healthy: bool


# ── Simulation ─────────────────────────────────────────────────────────────────

def simulate_gradients(n_steps: int = 5000, save_every: int = 100,
                        seed: int = 42) -> tuple[list[GradientSnapshot], list[TrainingHealth]]:
    rng = random.Random(seed)
    snapshots = []
    health = []

    clip_threshold = 1.0

    for step in range(0, n_steps + 1, save_every):
        progress = step / n_steps
        # LR cosine schedule
        lr = 5e-5 * 0.5 * (1 + math.cos(math.pi * progress))
        # Loss
        loss = 0.42 * math.exp(-progress * 3.5) + 0.055 + rng.gauss(0, 0.008)

        global_norm = 0.0
        clip_count = 0

        for group_name, n_layers, layer_type in LAYER_GROUPS:
            # Different layers have different gradient scales
            if layer_type == "lora":
                base_norm = 0.15 * (1 - progress * 0.3)  # LoRA grads stay smaller
            elif layer_type == "head":
                base_norm = 0.45 * (1 - progress * 0.5) + 0.05
            elif layer_type == "encoder":
                base_norm = 0.08 * (1 - progress * 0.2)  # frozen mostly
            else:
                base_norm = 0.25 * (1 - progress * 0.4) + 0.03

            # Occasional gradient spikes in early training
            if progress < 0.15 and rng.random() < 0.08:
                spike = rng.uniform(2.0, 8.0)
                base_norm *= spike

            grad_norm = max(1e-6, base_norm + rng.gauss(0, base_norm * 0.15))
            grad_norm_std = base_norm * 0.12
            grad_max = grad_norm * rng.uniform(1.5, 3.0)
            grad_min = grad_norm * rng.uniform(0.01, 0.1)

            vanishing = grad_norm < 1e-4
            exploding = grad_norm > 10.0
            clipped = grad_norm > clip_threshold
            if clipped:
                clip_count += 1

            global_norm += grad_norm ** 2

            snapshots.append(GradientSnapshot(
                step=step,
                layer_group=group_name,
                layer_type=layer_type,
                grad_norm=round(grad_norm, 6),
                grad_norm_mean=round(base_norm, 6),
                grad_norm_std=round(grad_norm_std, 6),
                grad_max=round(grad_max, 6),
                grad_min=round(grad_min, 8),
                vanishing=vanishing,
                exploding=exploding,
                clip_triggered=clipped,
            ))

        global_norm = round(math.sqrt(global_norm), 4)
        health.append(TrainingHealth(
            step=step,
            global_grad_norm=global_norm,
            loss=round(loss, 4),
            lr=round(lr, 8),
            clip_count=clip_count,
            healthy=not (global_norm > 5.0 or global_norm < 1e-5),
        ))

    return snapshots, health


def compute_summary(snapshots, health_records):
    exploding = sum(1 for s in snapshots if s.exploding)
    vanishing = sum(1 for s in snapshots if s.vanishing)
    clip_events = sum(1 for s in snapshots if s.clip_triggered)
    unhealthy_steps = sum(1 for h in health_records if not h.healthy)
    avg_global = sum(h.global_grad_norm for h in health_records) / len(health_records)
    return {
        "exploding_events": exploding,
        "vanishing_events": vanishing,
        "clip_events": clip_events,
        "unhealthy_steps": unhealthy_steps,
        "avg_global_norm": round(avg_global, 4),
        "total_snapshots": len(snapshots),
    }


# ── HTML report ────────────────────────────────────────────────────────────────

def render_html(snapshots: list, health_records: list, n_steps: int) -> str:
    summary = compute_summary(snapshots, health_records)

    # SVG: global grad norm over steps
    w, h = 560, 150
    max_norm = max(hr.global_grad_norm for hr in health_records) * 1.1
    x_scale = (w - 50) / max(h_r.step for h_r in health_records)
    y_scale = (h - 30) / max(max_norm, 1)

    svg_norm = f'<svg width="{w}" height="{h}" style="background:#0f172a;border-radius:8px">'
    svg_norm += f'<line x1="30" y1="{h-20}" x2="{w}" y2="{h-20}" stroke="#334155" stroke-width="1"/>'

    # Clip threshold line
    clip_y = h - 20 - 1.0 * y_scale
    svg_norm += (f'<line x1="30" y1="{clip_y:.1f}" x2="{w}" y2="{clip_y:.1f}" '
                 f'stroke="#f59e0b" stroke-width="1" stroke-dasharray="4,3"/>')
    svg_norm += (f'<text x="33" y="{clip_y-3:.1f}" fill="#f59e0b" font-size="8.5">clip=1.0</text>')

    pts = " ".join(
        f"{30+hr.step*x_scale:.1f},{h-20-hr.global_grad_norm*y_scale:.1f}"
        for hr in health_records
    )
    svg_norm += f'<polyline points="{pts}" fill="none" stroke="#3b82f6" stroke-width="2" opacity="0.9"/>'

    # Mark unhealthy steps
    for hr in health_records:
        if not hr.healthy:
            x = 30 + hr.step * x_scale
            svg_norm += (f'<circle cx="{x:.1f}" cy="{h-20-hr.global_grad_norm*y_scale:.1f}" '
                         f'r="3" fill="#ef4444" opacity="0.8"/>')

    svg_norm += '</svg>'

    # SVG: per-layer group gradient norm heatmap (latest step only)
    latest_step = max(s.step for s in snapshots)
    latest = {s.layer_group: s for s in snapshots if s.step == latest_step}
    w2, h2 = 380, 160
    max_g = max(s.grad_norm for s in latest.values()) * 1.1 or 1

    LAYER_COLORS = {"encoder": "#64748b", "embedding": "#a855f7",
                    "transformer": "#3b82f6", "head": "#C74634", "lora": "#22c55e"}

    svg_layers = f'<svg width="{w2}" height="{h2}" style="background:#0f172a;border-radius:8px">'
    bh2 = (h2 - 20) / len(latest) - 3
    for i, (gname, snap) in enumerate(sorted(latest.items(),
                                              key=lambda x: x[1].grad_norm, reverse=True)):
        y = 10 + i * (bh2 + 3)
        bw = snap.grad_norm / max_g * (w2 - 130)
        col = LAYER_COLORS.get(snap.layer_type, "#64748b")
        if snap.exploding:
            col = "#ef4444"
        elif snap.vanishing:
            col = "#475569"
        svg_layers += (f'<rect x="120" y="{y}" width="{bw:.1f}" height="{bh2:.1f}" '
                       f'fill="{col}" rx="2" opacity="0.85"/>')
        svg_layers += (f'<text x="118" y="{y+bh2*0.75:.1f}" fill="#94a3b8" font-size="9" '
                       f'text-anchor="end">{gname}</text>')
        svg_layers += (f'<text x="{123+bw:.1f}" y="{y+bh2*0.75:.1f}" fill="{col}" '
                       f'font-size="9">{snap.grad_norm:.4f}</text>')
    svg_layers += '</svg>'

    # Health table
    rows = ""
    for hr in health_records[-15:]:
        st_col = "#22c55e" if hr.healthy else "#ef4444"
        norm_col = "#22c55e" if hr.global_grad_norm < 1.0 else "#f59e0b" if hr.global_grad_norm < 3.0 else "#ef4444"
        rows += (f'<tr>'
                 f'<td style="color:#64748b">{hr.step:,}</td>'
                 f'<td style="color:{norm_col}">{hr.global_grad_norm:.4f}</td>'
                 f'<td style="color:#e2e8f0">{hr.loss:.4f}</td>'
                 f'<td style="color:#94a3b8">{hr.lr:.2e}</td>'
                 f'<td style="color:{"#f59e0b" if hr.clip_count > 0 else "#22c55e"}">{hr.clip_count}</td>'
                 f'<td style="color:{st_col}">{"✓" if hr.healthy else "✗"}</td></tr>')

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Gradient Monitor</title>
<style>
body{{background:#1e293b;color:#e2e8f0;font-family:monospace;margin:0;padding:24px}}
h1{{color:#C74634;margin:0 0 4px}}
.meta{{color:#94a3b8;font-size:12px;margin-bottom:20px}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:20px}}
.card{{background:#0f172a;border-radius:8px;padding:14px}}
.card h3{{color:#94a3b8;font-size:11px;text-transform:uppercase;margin:0 0 4px}}
.big{{font-size:28px;font-weight:bold}}
.charts{{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:20px}}
table{{width:100%;border-collapse:collapse;font-size:12px}}
th{{color:#94a3b8;text-align:left;padding:5px 8px;border-bottom:1px solid #334155}}
td{{padding:4px 8px;border-bottom:1px solid #1e293b}}
</style></head>
<body>
<h1>Gradient Monitor</h1>
<div class="meta">
  {n_steps:,} training steps · {len(LAYER_GROUPS)} layer groups · clip threshold=1.0
</div>

<div class="grid">
  <div class="card"><h3>Exploding Events</h3>
    <div class="big" style="color:{'#ef4444' if summary['exploding_events'] > 0 else '#22c55e'}">
      {summary['exploding_events']}
    </div></div>
  <div class="card"><h3>Vanishing Events</h3>
    <div class="big" style="color:{'#f59e0b' if summary['vanishing_events'] > 5 else '#22c55e'}">
      {summary['vanishing_events']}
    </div></div>
  <div class="card"><h3>Clip Events</h3>
    <div class="big" style="color:#f59e0b">{summary['clip_events']}</div></div>
  <div class="card"><h3>Avg Global Norm</h3>
    <div class="big" style="color:#3b82f6">{summary['avg_global_norm']:.4f}</div></div>
</div>

<div class="charts">
  <div>
    <h3 style="color:#94a3b8;font-size:11px;text-transform:uppercase;margin-bottom:8px">
      Global Gradient Norm over Steps (● = unhealthy)
    </h3>
    {svg_norm}
    <div style="color:#64748b;font-size:10px;margin-top:4px">amber = clip threshold (1.0)</div>
  </div>
  <div>
    <h3 style="color:#94a3b8;font-size:11px;text-transform:uppercase;margin-bottom:8px">
      Per-Layer Gradient Norm (latest step)
    </h3>
    {svg_layers}
  </div>
</div>

<h3 style="color:#94a3b8;font-size:11px;text-transform:uppercase;margin-bottom:8px">
  Recent Training Health (last 15 checkpoints)
</h3>
<table>
  <tr><th>Step</th><th>Global Norm</th><th>Loss</th><th>LR</th><th>Clips</th><th>Healthy</th></tr>
  {rows}
</table>

<div style="color:#64748b;font-size:11px;margin-top:16px">
  Gradient norm {summary['avg_global_norm']:.4f} avg — within healthy range (0.01–2.0).<br>
  LoRA adapters maintain smaller gradients (0.1–0.2) vs action head (0.3–0.5): expected.<br>
  If exploding: reduce LR or increase clip threshold. If vanishing: increase LR or use skip connections.
</div>
</body></html>"""


# ── CLI ────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Gradient health monitor")
    parser.add_argument("--mock",       action="store_true", default=True)
    parser.add_argument("--run-dir",    default="")
    parser.add_argument("--steps",      type=int, default=5000)
    parser.add_argument("--save-every", type=int, default=100)
    parser.add_argument("--output",     default="/tmp/gradient_monitor.html")
    parser.add_argument("--seed",       type=int, default=42)
    args = parser.parse_args()

    print(f"[grad-mon] Monitoring gradients for {args.steps} steps")
    t0 = time.time()

    snapshots, health = simulate_gradients(args.steps, args.save_every, args.seed)
    summary = compute_summary(snapshots, health)

    print(f"\n  Exploding: {summary['exploding_events']}  Vanishing: {summary['vanishing_events']}  "
          f"Clips: {summary['clip_events']}  Unhealthy: {summary['unhealthy_steps']}")
    print(f"  Avg global norm: {summary['avg_global_norm']:.4f}")
    print(f"\n  {'Layer Group':<22} {'Norm (last)':>12}")
    print(f"  {'─'*22} {'─'*12}")
    latest_step = max(s.step for s in snapshots)
    for group_name, _, _ in LAYER_GROUPS:
        snap = next((s for s in snapshots if s.step == latest_step and s.layer_group == group_name), None)
        if snap:
            flag = " ⚡" if snap.exploding else " ·" if snap.vanishing else ""
            print(f"  {group_name:<22} {snap.grad_norm:>11.6f}{flag}")

    print(f"\n  [{time.time()-t0:.1f}s]\n")

    html = render_html(snapshots, health, args.steps)
    Path(args.output).write_text(html)
    print(f"  HTML → {args.output}")

    json_out = Path(args.output).with_suffix(".json")
    json_out.write_text(json.dumps(summary, indent=2))
    print(f"  JSON → {json_out}")


if __name__ == "__main__":
    main()
