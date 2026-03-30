#!/usr/bin/env python3
"""
fine_tune_cost_estimator.py — Pre-run cost estimation for GR00T fine-tuning jobs.

Estimates GPU hours, OCI cost, and time-to-completion before launching training.
Accounts for LoRA vs full fine-tune, demo count, step count, GPU type, and
spot vs on-demand pricing. Helps partners budget and choose the right tier.

Usage:
    python src/training/fine_tune_cost_estimator.py --mock --output /tmp/finetune_cost.html
    python src/training/fine_tune_cost_estimator.py --demos 500 --steps 5000 --gpu A100-80G
"""

import argparse
import json
import math
import time
from dataclasses import dataclass
from pathlib import Path


# ── Config ─────────────────────────────────────────────────────────────────────

@dataclass
class GPUSpec:
    name: str
    price_on_demand: float   # $/hr
    price_spot: float        # $/hr
    throughput_it_s: float   # iterations/sec for GR00T full fine-tune
    lora_speedup: float      # multiplier for LoRA (faster)
    vram_gb: int
    available_regions: list[str]


GPU_SPECS = {
    "A100-80G": GPUSpec("A100-80G", 4.20, 1.47, 2.35, 2.2, 80, ["us-ashburn-1", "us-phoenix-1"]),
    "A10":      GPUSpec("A10",      1.25, 0.44, 1.10, 1.8, 24, ["us-ashburn-1"]),
    "V100-16G": GPUSpec("V100-16G", 1.80, 0.63, 0.75, 1.6, 16, ["us-ashburn-1"]),
    "A100-40G": GPUSpec("A100-40G", 3.10, 1.08, 1.95, 2.1, 40, ["eu-frankfurt-1"]),
}

ALGO_STEP_MULTIPLIER = {
    "BC":         1.0,
    "DAgger":     1.0,    # same per step, but more total steps needed
    "DAgger+Curr": 1.1,   # slight overhead for curriculum checking
    "LoRA+DAgger": 0.45,  # LoRA is much cheaper
}


@dataclass
class CostEstimate:
    gpu_type: str
    fine_tune_type: str    # full / lora
    algo: str
    n_demos: int
    n_steps: int
    gpu_hours: float
    cost_on_demand: float
    cost_spot: float
    wall_time_hr: float
    vram_gb_used: float
    fits_in_vram: bool
    recommended: bool
    notes: str


def estimate(gpu_name: str, fine_tune_type: str, algo: str,
             n_demos: int, n_steps: int) -> CostEstimate:
    gpu = GPU_SPECS[gpu_name]

    # Throughput: LoRA faster, algo multiplier
    base_it_s = gpu.throughput_it_s
    if fine_tune_type == "lora":
        effective_it_s = base_it_s * gpu.lora_speedup
    else:
        effective_it_s = base_it_s

    effective_it_s *= ALGO_STEP_MULTIPLIER.get(algo, 1.0)

    # Wall time and GPU hours
    wall_time_hr = n_steps / (effective_it_s * 3600)
    gpu_hours = wall_time_hr  # 1 GPU

    # Cost
    cost_od = gpu_hours * gpu.price_on_demand
    cost_sp = gpu_hours * gpu.price_spot

    # VRAM estimate: GR00T base = 13.4GB; LoRA keeps 7.7GB; full adds ~0.5GB/100 demos
    base_vram = 7.7 if fine_tune_type == "lora" else 13.4
    demo_vram = n_demos * 0.002   # ~2MB overhead per 100 demos = 0.002 GB
    vram_used = round(base_vram + demo_vram, 1)
    fits = vram_used <= gpu.vram_gb

    # Recommended: fits in VRAM, affordable, and right GPU for algo
    recommended = (fits and cost_od < 50.0 and
                   (fine_tune_type == "lora" or gpu_name in ("A100-80G", "A100-40G")))

    notes_parts = []
    if not fits:
        notes_parts.append(f"⚠ VRAM overflow ({vram_used:.1f}GB > {gpu.vram_gb}GB)")
    if fine_tune_type == "full" and gpu_name == "A10":
        notes_parts.append("⚠ A10 may OOM for full fine-tune >200 demos")
    if cost_od > 20:
        notes_parts.append(f"💡 Use spot to save ${cost_od - cost_sp:.2f}")

    return CostEstimate(
        gpu_type=gpu_name,
        fine_tune_type=fine_tune_type,
        algo=algo,
        n_demos=n_demos,
        n_steps=n_steps,
        gpu_hours=round(gpu_hours, 3),
        cost_on_demand=round(cost_od, 4),
        cost_spot=round(cost_sp, 4),
        wall_time_hr=round(wall_time_hr, 2),
        vram_gb_used=vram_used,
        fits_in_vram=fits,
        recommended=recommended,
        notes="; ".join(notes_parts),
    )


def estimate_all(n_demos: int, n_steps: int, algo: str) -> list[CostEstimate]:
    estimates = []
    for gpu_name in GPU_SPECS:
        for ft in ("full", "lora"):
            estimates.append(estimate(gpu_name, ft, algo, n_demos, n_steps))
    return estimates


# ── HTML report ────────────────────────────────────────────────────────────────

def render_html(estimates: list[CostEstimate], n_demos: int, n_steps: int, algo: str) -> str:
    valid = [e for e in estimates if e.fits_in_vram]
    if not valid:
        valid = estimates
    best = min(valid, key=lambda e: e.cost_spot)
    cheapest_od = min(valid, key=lambda e: e.cost_on_demand)
    fastest = min(valid, key=lambda e: e.wall_time_hr)

    # SVG: cost comparison bar chart
    w, h = 560, 160
    costs_od = [e.cost_on_demand for e in estimates]
    max_cost = max(costs_od) * 1.1
    bar_w = (w - 50) / len(estimates) - 3

    svg = f'<svg width="{w}" height="{h}" style="background:#0f172a;border-radius:8px">'
    svg += f'<line x1="30" y1="{h-20}" x2="{w}" y2="{h-20}" stroke="#334155" stroke-width="1"/>'

    GPU_COLORS = {"A100-80G": "#C74634", "A10": "#3b82f6",
                  "V100-16G": "#64748b", "A100-40G": "#a855f7"}

    for i, e in enumerate(estimates):
        x = 30 + i * (bar_w + 3)
        # On-demand bar
        bh_od = e.cost_on_demand / max_cost * (h - 40)
        col = GPU_COLORS.get(e.gpu_type, "#64748b")
        opacity = "0.9" if e.fits_in_vram else "0.35"
        svg += (f'<rect x="{x:.1f}" y="{h-20-bh_od:.1f}" width="{bar_w:.1f}" '
                f'height="{bh_od:.1f}" fill="{col}" rx="2" opacity="{opacity}"/>')
        # Spot overlay (narrower, brighter)
        bh_sp = e.cost_spot / max_cost * (h - 40)
        svg += (f'<rect x="{x+bar_w*0.3:.1f}" y="{h-20-bh_sp:.1f}" width="{bar_w*0.4:.1f}" '
                f'height="{bh_sp:.1f}" fill="#22c55e" rx="1" opacity="0.8"/>')

        label = f"{e.gpu_type[-5:]}\n{e.fine_tune_type[:4]}"
        svg += (f'<text x="{x+bar_w/2:.1f}" y="{h-4}" fill="{col if e.fits_in_vram else \"#475569\"}" '
                f'font-size="7.5" text-anchor="middle">{e.gpu_type.replace("-80G","").replace("-40G","")}'
                f'/{e.fine_tune_type[:3]}</text>')

        if e.recommended:
            svg += (f'<text x="{x+bar_w/2:.1f}" y="{h-22-bh_od:.1f}" fill="#f59e0b" '
                    f'font-size="9" text-anchor="middle">★</text>')

    svg += '</svg>'

    # Table
    rows = ""
    for e in sorted(estimates, key=lambda x: x.cost_spot if x.fits_in_vram else 9999):
        vram_col = "#22c55e" if e.fits_in_vram else "#ef4444"
        cost_col = "#22c55e" if e.cost_on_demand < 5 else "#f59e0b" if e.cost_on_demand < 20 else "#ef4444"
        hl = ' style="background:#0f2d1c"' if e.recommended else ""
        col = GPU_COLORS.get(e.gpu_type, "#64748b")
        rows += (f'<tr{hl}>'
                 f'<td style="color:{col}">{e.gpu_type}</td>'
                 f'<td style="color:#e2e8f0">{e.fine_tune_type}</td>'
                 f'<td style="color:{vram_col}">{e.vram_gb_used:.1f}GB {"✓" if e.fits_in_vram else "✗"}</td>'
                 f'<td>{e.gpu_hours:.3f}h</td>'
                 f'<td style="color:#64748b">{e.wall_time_hr:.2f}h wall</td>'
                 f'<td style="color:{cost_col}">${e.cost_on_demand:.4f}</td>'
                 f'<td style="color:#22c55e">${e.cost_spot:.4f}</td>'
                 f'<td>{"★ " if e.recommended else ""}{e.notes or "—"}</td></tr>')

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Fine-tune Cost Estimator</title>
<style>
body{{background:#1e293b;color:#e2e8f0;font-family:monospace;margin:0;padding:24px}}
h1{{color:#C74634;margin:0 0 4px}}
.meta{{color:#94a3b8;font-size:12px;margin-bottom:20px}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:20px}}
.card{{background:#0f172a;border-radius:8px;padding:14px}}
.card h3{{color:#94a3b8;font-size:11px;text-transform:uppercase;margin:0 0 4px}}
.big{{font-size:28px;font-weight:bold}}
table{{width:100%;border-collapse:collapse;font-size:12px}}
th{{color:#94a3b8;text-align:left;padding:5px 8px;border-bottom:1px solid #334155}}
td{{padding:4px 8px;border-bottom:1px solid #1e293b}}
</style></head>
<body>
<h1>Fine-tune Cost Estimator</h1>
<div class="meta">
  {n_demos} demos · {n_steps:,} steps · algo: {algo} · {len(estimates)} configs compared
</div>

<div class="grid">
  <div class="card"><h3>Recommended</h3>
    <div class="big" style="color:#f59e0b">{best.gpu_type}</div>
    <div style="color:#64748b;font-size:12px">{best.fine_tune_type} · ${best.cost_spot:.4f} spot</div></div>
  <div class="card"><h3>Cheapest On-Demand</h3>
    <div class="big" style="color:#22c55e">${cheapest_od.cost_on_demand:.4f}</div>
    <div style="color:#64748b;font-size:12px">{cheapest_od.gpu_type} · {cheapest_od.fine_tune_type}</div></div>
  <div class="card"><h3>Fastest</h3>
    <div class="big" style="color:#3b82f6">{fastest.wall_time_hr:.2f}h</div>
    <div style="color:#64748b;font-size:12px">{fastest.gpu_type} · {fastest.fine_tune_type}</div></div>
  <div class="card"><h3>Spot Savings</h3>
    <div class="big" style="color:#22c55e">
      {(1 - best.cost_spot/best.cost_on_demand)*100:.0f}%
    </div>
    <div style="color:#64748b;font-size:12px">vs on-demand</div></div>
</div>

<h3 style="color:#94a3b8;font-size:11px;text-transform:uppercase;margin-bottom:8px">
  Cost Comparison (dark=on-demand, green overlay=spot, ★=recommended, faded=VRAM overflow)
</h3>
{svg}
<div style="color:#64748b;font-size:10px;margin-top:4px;margin-bottom:20px">
  GPU/type labels on x-axis · ★ = recommended (fits VRAM, affordable)
</div>

<table>
  <tr><th>GPU</th><th>Fine-tune</th><th>VRAM</th><th>GPU-hrs</th>
      <th>Wall Time</th><th>On-Demand</th><th>Spot</th><th>Notes</th></tr>
  {rows}
</table>

<div style="color:#64748b;font-size:11px;margin-top:16px">
  LoRA fine-tune: {min(e.cost_on_demand for e in estimates if e.fine_tune_type=="lora"):.4f}–{max(e.cost_on_demand for e in estimates if e.fine_tune_type=="lora"):.4f} on-demand ·
  Full fine-tune: {min(e.cost_on_demand for e in estimates if e.fine_tune_type=="full"):.4f}–{max(e.cost_on_demand for e in estimates if e.fine_tune_type=="full"):.4f}<br>
  OCI A100-80G spot = cheapest GPU per training step. A10 best for LoRA-only with budget constraint.
</div>
</body></html>"""


# ── CLI ────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Fine-tune cost estimator")
    parser.add_argument("--mock",        action="store_true", default=True)
    parser.add_argument("--demos",       type=int, default=500)
    parser.add_argument("--steps",       type=int, default=5000)
    parser.add_argument("--algo",        default="DAgger",
                        choices=list(ALGO_STEP_MULTIPLIER))
    parser.add_argument("--gpu",         default="all")
    parser.add_argument("--fine-tune",   default="all", choices=["all", "full", "lora"])
    parser.add_argument("--output",      default="/tmp/finetune_cost_estimator.html")
    args = parser.parse_args()

    print(f"[cost-est] {args.demos} demos · {args.steps} steps · algo={args.algo}")
    t0 = time.time()

    estimates = estimate_all(args.demos, args.steps, args.algo)

    print(f"\n  {'GPU':<12} {'Type':<6}  {'VRAM':>8}  {'GPU-hrs':>8}  {'On-Demand':>10}  {'Spot':>8}")
    print(f"  {'─'*12} {'─'*6}  {'─'*8}  {'─'*8}  {'─'*10}  {'─'*8}")
    for e in sorted(estimates, key=lambda x: x.cost_spot if x.fits_in_vram else 9999):
        mark = "★" if e.recommended else ("✗" if not e.fits_in_vram else " ")
        print(f"  {e.gpu_type:<12} {e.fine_tune_type:<6}  {e.vram_gb_used:>6.1f}GB  "
              f"{e.gpu_hours:>7.3f}h  ${e.cost_on_demand:>9.4f}  ${e.cost_spot:>7.4f}  {mark}")

    print(f"\n  [{time.time()-t0:.1f}s]\n")

    html = render_html(estimates, args.demos, args.steps, args.algo)
    Path(args.output).write_text(html)
    print(f"  HTML → {args.output}")

    json_out = Path(args.output).with_suffix(".json")
    json_out.write_text(json.dumps(
        [{"gpu": e.gpu_type, "type": e.fine_tune_type, "cost_od": e.cost_on_demand,
          "cost_spot": e.cost_spot, "gpu_hours": e.gpu_hours, "recommended": e.recommended}
         for e in estimates], indent=2))
    print(f"  JSON → {json_out}")


if __name__ == "__main__":
    main()
